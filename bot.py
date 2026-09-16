"""
Bot Telegram d'Affiliation — Pepi-Lab
======================================
- Affiliation avec tracking anti-perte (Snap/Insta)
- Choix du mode de rémunération (code promo / RIB / crypto)
- Welcoming avec acceptation des règles
- Lien d'invitation permanent vers le groupe privé
- Dashboard admin complet
"""

import os
import sqlite3
import hashlib
import logging
from datetime import datetime

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# ─── Config ───────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = [int(x) for x in os.environ["ADMIN_IDS"].split(",")]
LANDING_URL = os.environ["LANDING_URL"]
BOT_USERNAME = os.environ["BOT_USERNAME"]

# GROUP_CHAT_ID peut être vide au démarrage — utilise /groupid pour le trouver
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))

DB_PATH = os.environ.get("DB_PATH", "affiliates.db")

# ── Texte des règles ──
RULES_TEXT = """Hello, Bienvenu chez Pepi-Lab 🧬

Je suis votre bot d'accueil 🤖
Pour accéder à notre communauté, notre catalogue ou vous informer sur le monde des pepi.

Vous devez prendre en compte les règles suivantes 📝 :

1\\. L'ensemble de notre catalogue est destiné exclusivement à la recherche\\. ✔️
2\\. Respect et courtoisie obligatoires\\. ✔️
3\\. Pas de spam ni de démarchage privé\\. ✔️
4\\. Discrétion absolue exigée\\. ✔️"""

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ─── Base de données ──────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS affiliates (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            last_name       TEXT,
            ref_code        TEXT UNIQUE NOT NULL,
            payment_method  TEXT DEFAULT '',
            payment_details TEXT DEFAULT '',
            awaiting_input  TEXT DEFAULT '',
            created_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS referrals (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            referred_user_id      INTEGER UNIQUE,
            referred_username     TEXT,
            referred_first_name   TEXT,
            referred_last_name    TEXT,
            affiliate_user_id     INTEGER NOT NULL,
            affiliate_ref_code    TEXT NOT NULL,
            source                TEXT DEFAULT 'bot',
            rules_accepted        INTEGER DEFAULT 0,
            invite_link           TEXT DEFAULT '',
            created_at            TEXT NOT NULL,
            FOREIGN KEY (affiliate_user_id) REFERENCES affiliates(user_id)
        );

        CREATE TABLE IF NOT EXISTS clicks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_code    TEXT NOT NULL,
            clicked_at  TEXT NOT NULL,
            ip_hash     TEXT
        );

        CREATE TABLE IF NOT EXISTS pending_welcome (
            user_id             INTEGER PRIMARY KEY,
            affiliate_user_id   INTEGER,
            affiliate_ref_code  TEXT,
            source              TEXT DEFAULT 'bot',
            created_at          TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialisée.")


def generate_ref_code(user_id: int) -> str:
    return hashlib.md5(str(user_id).encode()).hexdigest()[:8]


# ─── Lien d'invitation permanent ──────────────────────────────────────

async def create_group_invite(bot, label: str = "") -> str | None:
    """Lien permanent, usage unique, sans expiration."""
    if not GROUP_CHAT_ID:
        logger.error("GROUP_CHAT_ID non configuré ! Utilise /groupid dans le groupe.")
        return None
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=GROUP_CHAT_ID,
            name=(label[:30] if label else "Nouveau membre"),
            member_limit=1,
        )
        return invite.invite_link
    except Exception as e:
        logger.error(f"Erreur lien d'invitation: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════
#  COMMANDE /groupid — pour trouver l'ID du groupe facilement
# ═══════════════════════════════════════════════════════════════════════

async def cmd_groupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Affiche l'ID du chat — à utiliser dans le groupe pour récupérer le GROUP_CHAT_ID."""
    chat = update.effective_chat
    user = update.effective_user

    await update.message.reply_text(
        f"ℹ️ *Infos de ce chat :*\n\n"
        f"📛 Nom : {chat.title or chat.first_name or '—'}\n"
        f"🆔 Chat ID : `{chat.id}`\n"
        f"👤 Ton ID : `{user.id}`\n\n"
        f"Copie le *Chat ID* et colle-le dans la variable "
        f"`GROUP_CHAT_ID` sur Railway.",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════════════════════════════
#  WELCOMING — Acceptation des règles
# ═══════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args

    if args:
        ref_code = args[0]
        conn = get_db()

        affiliate = conn.execute(
            "SELECT * FROM affiliates WHERE ref_code = ?", (ref_code,)
        ).fetchone()

        if affiliate and affiliate["user_id"] != user.id:
            existing = conn.execute(
                "SELECT * FROM referrals WHERE referred_user_id = ?", (user.id,)
            ).fetchone()

            if not existing:
                # Stocker en attente de validation des règles
                conn.execute(
                    """INSERT OR REPLACE INTO pending_welcome 
                       (user_id, affiliate_user_id, affiliate_ref_code, source, created_at)
                       VALUES (?, ?, ?, 'bot', ?)""",
                    (user.id, affiliate["user_id"], ref_code, datetime.now().isoformat()),
                )
                conn.commit()
                conn.close()

                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "✅ Accepter les règles et rejoindre le groupe",
                        callback_data="accept_rules"
                    )],
                ])
                await update.message.reply_text(
                    RULES_TEXT,
                    parse_mode="MarkdownV2",
                    reply_markup=keyboard,
                )
                return
            else:
                conn.close()
                await update.message.reply_text(
                    f"Hey {user.first_name} ! Tu es déjà membre\\. 👊",
                    parse_mode="MarkdownV2",
                )
                return

        conn.close()

    # /start normal
    await update.message.reply_text(
        f"Salut {user.first_name} ! 👋\n\n"
        f"🔗 Devenir ambassadeur → /monlien\n"
        f"📊 Tes stats → /messtats\n"
        f"💰 Mode de paiement → /paiement\n"
        f"❓ Aide → /aide",
    )


async def callback_accept_rules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quand le client clique 'Accepter les règles et rejoindre le groupe'."""
    query = update.callback_query
    await query.answer()
    user = query.from_user

    conn = get_db()

    pending = conn.execute(
        "SELECT * FROM pending_welcome WHERE user_id = ?", (user.id,)
    ).fetchone()

    if not pending:
        await query.edit_message_text("⚠️ Session expirée. Reclique sur ton lien d'invitation.")
        conn.close()
        return

    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ?", (pending["affiliate_user_id"],)
    ).fetchone()

    aff_name = affiliate["first_name"] if affiliate else "inconnu"
    invite_link = await create_group_invite(
        context.bot,
        f"{user.first_name} via {aff_name}"
    )

    conn.execute(
        """INSERT OR IGNORE INTO referrals 
           (referred_user_id, referred_username, referred_first_name, 
            referred_last_name, affiliate_user_id, affiliate_ref_code, 
            source, rules_accepted, invite_link, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
        (
            user.id,
            user.username or "",
            user.first_name or "",
            user.last_name or "",
            pending["affiliate_user_id"],
            pending["affiliate_ref_code"],
            pending["source"],
            invite_link or "",
            datetime.now().isoformat(),
        ),
    )
    conn.execute("DELETE FROM pending_welcome WHERE user_id = ?", (user.id,))
    conn.commit()
    conn.close()

    # ── Notifier l'admin ──
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"🆕 *Nouveau client !*\n\n"
                    f"👤 {user.first_name} {user.last_name or ''}\n"
                    f"📱 @{user.username or 'aucun'}\n"
                    f"🆔 `{user.id}`\n\n"
                    f"🤝 Via : {aff_name} (@{affiliate['username'] or 'aucun'})\n"
                    f"🔗 Code : `{pending['affiliate_ref_code']}`\n"
                    f"✅ Règles acceptées"
                ),
                parse_mode="Markdown",
            )
        except Exception as e:
            logger.error(f"Erreur notif admin: {e}")

    # ── Notifier l'affilié ──
    if affiliate:
        try:
            await context.bot.send_message(
                chat_id=affiliate["user_id"],
                text=(
                    f"🎉 *Nouveau client grâce à toi !*\n"
                    f"👤 {user.first_name} vient de rejoindre via ton lien.\n"
                    f"Continue comme ça 💪"
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass

    # ── Répondre au client ──
    if invite_link:
        await query.edit_message_text(
            f"✅ Règles acceptées ! Bienvenue {user.first_name} !\n\n"
            f"👇 Clique ici pour rejoindre le groupe :\n\n"
            f"🔗 {invite_link}\n\n"
            f"Ce lien est à usage unique et réservé à toi.\n"
            f"Une fois dans le groupe, rendez-vous dans le sujet "
            f"« Passer commande » pour commander !",
        )
    else:
        await query.edit_message_text(
            f"✅ Règles acceptées ! Bienvenue {user.first_name} !\n\n"
            f"⚠️ Problème technique avec le lien d'invitation.\n"
            f"Un admin va te contacter rapidement."
        )


# ═══════════════════════════════════════════════════════════════════════
#  AFFILIATION — Lien + mode de paiement
# ═══════════════════════════════════════════════════════════════════════

async def cmd_monlien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()

    existing = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ?", (user.id,)
    ).fetchone()

    if existing:
        ref_code = existing["ref_code"]
        conn.execute(
            "UPDATE affiliates SET username=?, first_name=?, last_name=? WHERE user_id=?",
            (user.username or "", user.first_name or "", user.last_name or "", user.id),
        )
        conn.commit()

        landing_link = f"{LANDING_URL}/ref/{ref_code}"
        method_label = _payment_label(existing["payment_method"]) if existing["payment_method"] else None

        text = (
            f"🔗 *Ton lien d'ambassadeur :*\n\n"
            f"👉 `{landing_link}`\n\n"
            f"Partage-le partout (Snap, Insta, WhatsApp, TikTok…) !\n\n"
        )
        if method_label:
            text += f"💰 Rémunération : {method_label}\n"
        text += (
            f"📊 Tes stats → /messtats\n"
            f"🔄 Mode de paiement → /paiement"
        )

        await update.message.reply_text(text, parse_mode="Markdown")

        if not existing["payment_method"]:
            await _ask_payment_method(update)

        conn.close()
        return

    # Nouvel affilié
    ref_code = generate_ref_code(user.id)
    conn.execute(
        """INSERT INTO affiliates 
           (user_id, username, first_name, last_name, ref_code, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user.id, user.username or "", user.first_name or "",
         user.last_name or "", ref_code, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    logger.info(f"Nouvel affilié: {user.first_name} (ID:{user.id}) code:{ref_code}")

    landing_link = f"{LANDING_URL}/ref/{ref_code}"
    await update.message.reply_text(
        f"🎉 *Bienvenue dans le programme ambassadeur Pepi-Lab !*\n\n"
        f"🔗 Ton lien :\n👉 `{landing_link}`\n\n"
        f"Partage-le partout — chaque personne qui rejoint via ce lien "
        f"sera comptabilisée à ton nom !\n\n"
        f"📊 Tes stats → /messtats",
        parse_mode="Markdown",
    )
    await _ask_payment_method(update)


def _payment_label(method: str) -> str:
    return {
        "code_promo": "🏷️ Code promo",
        "rib": "🏦 Virement (RIB)",
        "crypto": "₿ Crypto",
    }.get(method, "")


async def _ask_payment_method(update: Update):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️ Code promo", callback_data="pay_code_promo")],
        [InlineKeyboardButton("🏦 Virement (RIB)", callback_data="pay_rib")],
        [InlineKeyboardButton("₿ Crypto (wallet)", callback_data="pay_crypto")],
        [InlineKeyboardButton("⏭️ Plus tard", callback_data="pay_later")],
    ])
    await update.message.reply_text(
        "💰 *Comment veux-tu être rémunéré ?*\n\n"
        "Tu pourras changer à tout moment avec /paiement.",
        parse_mode="Markdown",
        reply_markup=keyboard,
    )


async def cmd_paiement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ?", (user.id,)
    ).fetchone()
    conn.close()

    if not affiliate:
        await update.message.reply_text("Tape /monlien pour devenir ambassadeur d'abord !")
        return

    current = affiliate["payment_method"]
    details = affiliate["payment_details"]

    text = "💰 *Mode de paiement actuel :*\n\n"
    if current:
        text += f"{_payment_label(current)}"
        if details:
            if current == "rib":
                masked = f"{details[:8]}...{details[-4:]}" if len(details) > 12 else details
            elif current == "crypto":
                masked = f"{details[:6]}...{details[-4:]}" if len(details) > 10 else details
            else:
                masked = details
            text += f"\n📋 `{masked}`"
        text += "\n\n🔄 Choisis pour changer :"
    else:
        text += "Non défini\n\nChoisis ton mode :"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🏷️ Code promo", callback_data="pay_code_promo")],
        [InlineKeyboardButton("🏦 Virement (RIB)", callback_data="pay_rib")],
        [InlineKeyboardButton("₿ Crypto (wallet)", callback_data="pay_crypto")],
    ])
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=keyboard)


async def callback_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    conn = get_db()
    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ?", (user.id,)
    ).fetchone()

    if not affiliate:
        await query.edit_message_text("⚠️ Tape /monlien d'abord.")
        conn.close()
        return

    if data == "pay_code_promo":
        conn.execute(
            "UPDATE affiliates SET payment_method='code_promo', payment_details='', awaiting_input='' WHERE user_id=?",
            (user.id,),
        )
        conn.commit()
        conn.close()
        await query.edit_message_text(
            "🏷️ *Code promo sélectionné !*\n\n"
            "Tu recevras des codes promo en guise de rémunération.\n"
            "🔄 Changer → /paiement",
            parse_mode="Markdown",
        )

    elif data == "pay_rib":
        conn.execute(
            "UPDATE affiliates SET payment_method='rib', awaiting_input='rib' WHERE user_id=?",
            (user.id,),
        )
        conn.commit()
        conn.close()
        await query.edit_message_text(
            "🏦 *Virement sélectionné*\n\n"
            "Envoie-moi ton RIB (IBAN) dans le prochain message.",
            parse_mode="Markdown",
        )

    elif data == "pay_crypto":
        conn.execute(
            "UPDATE affiliates SET payment_method='crypto', awaiting_input='crypto' WHERE user_id=?",
            (user.id,),
        )
        conn.commit()
        conn.close()
        await query.edit_message_text(
            "₿ *Crypto sélectionné*\n\n"
            "Envoie-moi ton adresse de wallet dans le prochain message.\n"
            "Précise le réseau (BTC, ETH, USDT TRC20…).",
            parse_mode="Markdown",
        )

    elif data == "pay_later":
        conn.close()
        await query.edit_message_text(
            "👌 Tu pourras configurer ton mode de paiement plus tard avec /paiement."
        )


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Capture le RIB ou wallet quand le bot l'attend."""
    user = update.effective_user
    text = update.message.text.strip()

    # Ignorer les messages dans les groupes (ne traiter qu'en DM)
    if update.effective_chat.type != "private":
        return

    conn = get_db()
    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ? AND awaiting_input != ''",
        (user.id,),
    ).fetchone()

    if not affiliate:
        conn.close()
        return

    input_type = affiliate["awaiting_input"]

    if input_type == "rib":
        clean = text.replace(" ", "").upper()
        if len(clean) < 15:
            await update.message.reply_text(
                "⚠️ Ça ne ressemble pas à un IBAN valide.\n"
                "Renvoie ton IBAN complet ou tape /paiement pour changer."
            )
            conn.close()
            return

        conn.execute(
            "UPDATE affiliates SET payment_details=?, awaiting_input='' WHERE user_id=?",
            (clean, user.id),
        )
        conn.commit()
        conn.close()

        masked = f"{clean[:8]}...{clean[-4:]}" if len(clean) > 12 else clean
        await update.message.reply_text(
            f"✅ *RIB enregistré !*\n📋 `{masked}`\n🔄 Modifier → /paiement",
            parse_mode="Markdown",
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"🏦 RIB enregistré — {user.first_name} @{user.username or '—'}\nIBAN: `{clean}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    elif input_type == "crypto":
        if len(text) < 10:
            await update.message.reply_text("⚠️ Adresse trop courte. Renvoie l'adresse complète.")
            conn.close()
            return

        conn.execute(
            "UPDATE affiliates SET payment_details=?, awaiting_input='' WHERE user_id=?",
            (text, user.id),
        )
        conn.commit()
        conn.close()

        masked = f"{text[:6]}...{text[-4:]}" if len(text) > 10 else text
        await update.message.reply_text(
            f"✅ *Wallet enregistré !*\n📋 `{masked}`\n🔄 Modifier → /paiement",
            parse_mode="Markdown",
        )
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=f"₿ Wallet enregistré — {user.first_name} @{user.username or '—'}\nWallet: `{text}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


# ═══════════════════════════════════════════════════════════════════════
#  CODE MANUEL (fallback Snap/Insta)
# ═══════════════════════════════════════════════════════════════════════

async def cmd_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Envoie le code comme ceci :\n/code ABC123")
        return

    ref_code = context.args[0]
    conn = get_db()

    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE ref_code = ?", (ref_code,)
    ).fetchone()

    if not affiliate:
        conn.close()
        await update.message.reply_text("❌ Code invalide.")
        return
    if affiliate["user_id"] == user.id:
        conn.close()
        await update.message.reply_text("😅 Tu ne peux pas utiliser ton propre code !")
        return

    existing = conn.execute(
        "SELECT * FROM referrals WHERE referred_user_id = ?", (user.id,)
    ).fetchone()
    if existing:
        conn.close()
        await update.message.reply_text("✅ Tu es déjà enregistré !")
        return

    conn.execute(
        """INSERT OR REPLACE INTO pending_welcome 
           (user_id, affiliate_user_id, affiliate_ref_code, source, created_at)
           VALUES (?, ?, ?, 'manual_code', ?)""",
        (user.id, affiliate["user_id"], ref_code, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Accepter les règles et rejoindre le groupe", callback_data="accept_rules")],
    ])
    await update.message.reply_text(
        f"Code reconnu — tu es parrainé par {affiliate['first_name']} !\n\n{RULES_TEXT}",
        parse_mode="MarkdownV2",
        reply_markup=keyboard,
    )


# ═══════════════════════════════════════════════════════════════════════
#  STATS PERSO
# ═══════════════════════════════════════════════════════════════════════

async def cmd_messtats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db()
    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ?", (user.id,)
    ).fetchone()

    if not affiliate:
        conn.close()
        await update.message.reply_text("Tape /monlien pour devenir ambassadeur !")
        return

    ref_code = affiliate["ref_code"]
    clients = conn.execute(
        "SELECT COUNT(*) as c FROM referrals WHERE affiliate_ref_code = ?", (ref_code,)
    ).fetchone()["c"]
    clics = conn.execute(
        "SELECT COUNT(*) as c FROM clicks WHERE ref_code = ?", (ref_code,)
    ).fetchone()["c"]
    recent = conn.execute(
        """SELECT referred_first_name, referred_username, created_at 
           FROM referrals WHERE affiliate_ref_code = ? 
           ORDER BY created_at DESC LIMIT 5""",
        (ref_code,),
    ).fetchall()
    conn.close()

    pay = _payment_label(affiliate["payment_method"]) if affiliate["payment_method"] else "Non défini (/paiement)"
    conv = round(clients / clics * 100, 1) if clics > 0 else 0

    text = (
        f"📊 *Tes stats Pepi-Lab*\n\n"
        f"🔗 Code : `{ref_code}`\n"
        f"👆 Clics : *{clics}*\n"
        f"👥 Clients : *{clients}*\n"
        f"📈 Conversion : *{conv}%*\n"
        f"💰 Paiement : {pay}\n"
    )
    if recent:
        text += "\n🕐 *Derniers :*\n"
        for r in recent:
            d = datetime.fromisoformat(r["created_at"]).strftime("%d/%m/%Y")
            n = r["referred_first_name"]
            u = f" @{r['referred_username']}" if r["referred_username"] else ""
            text += f"  • {n}{u} — {d}\n"

    await update.message.reply_text(text, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════
#  ADMIN
# ═══════════════════════════════════════════════════════════════════════

def is_admin(uid: int) -> bool:
    return uid in ADMIN_IDS


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    ta = conn.execute("SELECT COUNT(*) as c FROM affiliates").fetchone()["c"]
    tr = conn.execute("SELECT COUNT(*) as c FROM referrals").fetchone()["c"]
    tc = conn.execute("SELECT COUNT(*) as c FROM clicks").fetchone()["c"]

    from datetime import timedelta
    y = (datetime.now() - timedelta(hours=24)).isoformat()
    c24 = conn.execute("SELECT COUNT(*) as c FROM clicks WHERE clicked_at>?", (y,)).fetchone()["c"]
    r24 = conn.execute("SELECT COUNT(*) as c FROM referrals WHERE created_at>?", (y,)).fetchone()["c"]

    top = conn.execute("""
        SELECT a.first_name, a.username, a.ref_code, a.payment_method, COUNT(r.id) as cnt
        FROM affiliates a LEFT JOIN referrals r ON a.ref_code = r.affiliate_ref_code
        GROUP BY a.user_id ORDER BY cnt DESC LIMIT 10
    """).fetchall()

    recent = conn.execute("""
        SELECT r.referred_first_name, r.referred_username,
               a.first_name as aff_name, r.source, r.created_at
        FROM referrals r JOIN affiliates a ON r.affiliate_user_id = a.user_id
        ORDER BY r.created_at DESC LIMIT 10
    """).fetchall()
    conn.close()

    conv = round(tr / tc * 100, 1) if tc > 0 else 0
    text = (
        f"📊 *DASHBOARD PEPI-LAB*\n\n"
        f"👥 Ambassadeurs : *{ta}*\n"
        f"🆕 Clients : *{tr}*\n"
        f"👆 Clics : *{tc}*\n"
        f"📈 Conversion : *{conv}%*\n\n"
        f"⏱ *24h :* {c24} clics, {r24} clients\n"
    )
    if top:
        text += "\n🏆 *Top ambassadeurs :*\n"
        for i, t in enumerate(top, 1):
            u = f"@{t['username']}" if t["username"] else ""
            p = _payment_label(t["payment_method"]) if t["payment_method"] else "💰?"
            text += f"  {i}. {t['first_name']} {u} — *{t['cnt']}* | {p}\n"
    if recent:
        text += "\n🕐 *Derniers clients :*\n"
        for r in recent:
            d = datetime.fromisoformat(r["created_at"]).strftime("%d/%m %H:%M")
            src = {"bot": "🔗", "manual_code": "📝"}.get(r["source"], "❓")
            text += f"  {src} {r['referred_first_name']} → via {r['aff_name']} ({d})\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_affilies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    rows = conn.execute("""
        SELECT a.*, COUNT(r.id) as cnt,
               (SELECT COUNT(*) FROM clicks WHERE ref_code=a.ref_code) as clk
        FROM affiliates a LEFT JOIN referrals r ON a.ref_code=r.affiliate_ref_code
        GROUP BY a.user_id ORDER BY cnt DESC
    """).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Aucun ambassadeur.")
        return

    text = "👥 *AMBASSADEURS*\n\n"
    for a in rows:
        u = f"@{a['username']}" if a["username"] else "—"
        d = datetime.fromisoformat(a["created_at"]).strftime("%d/%m/%Y")
        pay = _payment_label(a["payment_method"]) if a["payment_method"] else "❌ Non défini"
        det = ""
        if a["payment_details"]:
            v = a["payment_details"]
            if a["payment_method"] == "rib":
                det = f"\n  📋 `{v}`"
            elif a["payment_method"] == "crypto":
                det = f"\n  📋 `{v}`"
        text += (
            f"• *{a['first_name']} {a['last_name'] or ''}*\n"
            f"  {u} | ID: `{a['user_id']}`\n"
            f"  Code: `{a['ref_code']}` | 👥 {a['cnt']} | 👆 {a['clk']} | {d}\n"
            f"  💰 {pay}{det}\n\n"
        )

    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i+4000], parse_mode="Markdown")


async def cmd_clients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    rows = conn.execute("""
        SELECT r.*, a.first_name as aff_name, a.username as aff_u
        FROM referrals r JOIN affiliates a ON r.affiliate_user_id=a.user_id
        ORDER BY r.created_at DESC LIMIT 30
    """).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Aucun client.")
        return

    text = "🆕 *CLIENTS*\n\n"
    for c in rows:
        d = datetime.fromisoformat(c["created_at"]).strftime("%d/%m/%Y %H:%M")
        u = f"@{c['referred_username']}" if c["referred_username"] else "—"
        src = {"bot": "🔗", "manual_code": "📝"}.get(c["source"], c["source"])
        rules = "✅" if c["rules_accepted"] else "❌"
        text += (
            f"• *{c['referred_first_name']} {c['referred_last_name'] or ''}*\n"
            f"  {u} | ID: `{c['referred_user_id']}`\n"
            f"  Via: {c['aff_name']} | {src} | Règles: {rules} | {d}\n\n"
        )

    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i+4000], parse_mode="Markdown")


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    import csv, io
    conn = get_db()

    aff = conn.execute("""
        SELECT a.user_id, a.username, a.first_name, a.last_name, a.ref_code,
               a.payment_method, a.payment_details, a.created_at, COUNT(r.id) as nb
        FROM affiliates a LEFT JOIN referrals r ON a.ref_code=r.affiliate_ref_code
        GROUP BY a.user_id
    """).fetchall()
    o1 = io.StringIO()
    w1 = csv.writer(o1)
    w1.writerow(["id","username","prenom","nom","code","paiement","details","date","nb_clients"])
    for a in aff:
        w1.writerow([a["user_id"],a["username"],a["first_name"],a["last_name"],
                      a["ref_code"],a["payment_method"],a["payment_details"],a["created_at"],a["nb"]])
    b1 = io.BytesIO(o1.getvalue().encode("utf-8"))
    b1.name = f"ambassadeurs_{datetime.now().strftime('%Y%m%d')}.csv"
    await update.message.reply_document(b1, caption="📄 Ambassadeurs")

    ref = conn.execute("""
        SELECT r.referred_user_id, r.referred_username, r.referred_first_name,
               r.referred_last_name, a.first_name as aff, a.username as aff_u,
               r.source, r.rules_accepted, r.created_at
        FROM referrals r JOIN affiliates a ON r.affiliate_user_id=a.user_id
    """).fetchall()
    o2 = io.StringIO()
    w2 = csv.writer(o2)
    w2.writerow(["id","username","prenom","nom","affilié","aff_username","source","règles","date"])
    for r in ref:
        w2.writerow([r["referred_user_id"],r["referred_username"],r["referred_first_name"],
                      r["referred_last_name"],r["aff"],r["aff_u"],r["source"],
                      "oui" if r["rules_accepted"] else "non",r["created_at"]])
    b2 = io.BytesIO(o2.getvalue().encode("utf-8"))
    b2.name = f"clients_{datetime.now().strftime('%Y%m%d')}.csv"
    await update.message.reply_document(b2, caption="📄 Clients")
    conn.close()


async def cmd_newlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    link = await create_group_invite(context.bot, "Admin manuel")
    if link:
        await update.message.reply_text(f"🔗 `{link}`\nUsage unique, permanent.", parse_mode="Markdown")
    else:
        await update.message.reply_text("❌ Vérifie que le bot est admin du groupe et que GROUP_CHAT_ID est configuré.")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        text = (
            "🤖 *ADMIN*\n"
            "/stats — Dashboard\n"
            "/affilies — Ambassadeurs + paiements\n"
            "/clients — Clients parrainés\n"
            "/export — CSV\n"
            "/newlink — Lien d'invitation manuel\n"
            "/groupid — ID du chat (à taper dans le groupe)\n\n"
            "🔧 *PUBLIC*\n"
            "/monlien — Devenir ambassadeur\n"
            "/messtats — Mes stats\n"
            "/paiement — Mode de rémunération\n"
            "/code ABC — Code manuel\n"
            "/aide — Aide"
        )
    else:
        text = (
            "🤖 *Commandes :*\n\n"
            "/monlien — Mon lien d'ambassadeur\n"
            "/messtats — Mes stats\n"
            "/paiement — Mode de rémunération\n"
            "/code ABC — Code de parrainage\n"
            "/aide — Aide"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CallbackQueryHandler(callback_accept_rules, pattern="^accept_rules$"))
    app.add_handler(CallbackQueryHandler(callback_payment, pattern="^pay_"))

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("monlien", cmd_monlien))
    app.add_handler(CommandHandler("messtats", cmd_messtats))
    app.add_handler(CommandHandler("paiement", cmd_paiement))
    app.add_handler(CommandHandler("code", cmd_code))
    app.add_handler(CommandHandler("groupid", cmd_groupid))
    app.add_handler(CommandHandler("aide", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("affilies", cmd_affilies))
    app.add_handler(CommandHandler("clients", cmd_clients))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(CommandHandler("newlink", cmd_newlink))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    logger.info("Bot Pepi-Lab démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
