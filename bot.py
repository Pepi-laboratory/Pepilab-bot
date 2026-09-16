"""
Bot Telegram — Pepi-Lab
========================
- Affiliation (génération de liens, stats)
- Notification quand quelqu'un rejoint le groupe
- Mode de paiement (code promo / RIB / crypto)
- Système de cagnotte (CRM affiliés)
"""

import os
import sqlite3
import hashlib
import logging
from datetime import datetime, timedelta

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ChatMemberUpdated,
)
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

# ─── Config ───────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_IDS = [int(x) for x in os.environ["ADMIN_IDS"].split(",")]
LANDING_URL = os.environ["LANDING_URL"]
BOT_USERNAME = os.environ["BOT_USERNAME"]
GROUP_CHAT_ID = int(os.environ.get("GROUP_CHAT_ID", "0"))
DB_PATH = os.environ.get("DB_PATH", "affiliates.db")

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
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS affiliates (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            last_name       TEXT,
            ref_code        TEXT UNIQUE NOT NULL,
            payment_method  TEXT DEFAULT '',
            payment_details TEXT DEFAULT '',
            awaiting_input  TEXT DEFAULT '',
            cagnotte        REAL DEFAULT 0,
            created_at      TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS group_joins (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER,
            username        TEXT,
            first_name      TEXT,
            last_name       TEXT,
            joined_at       TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()
    logger.info("DB initialisée.")


def generate_ref_code(user_id: int) -> str:
    return hashlib.md5(str(user_id).encode()).hexdigest()[:8]


# ═══════════════════════════════════════════════════════════════════════
#  DÉTECTION NOUVEAU MEMBRE DANS LE GROUPE
# ═══════════════════════════════════════════════════════════════════════

async def track_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Détecte quand quelqu'un rejoint le groupe et notifie l'admin."""
    result = update.chat_member
    if result is None:
        return

    # Vérifier que c'est bien notre groupe
    if result.chat.id != GROUP_CHAT_ID:
        return

    old = result.old_chat_member
    new = result.new_chat_member

    # Nouveau membre (était pas membre → est membre maintenant)
    if old.status in ("left", "kicked") and new.status in ("member", "restricted"):
        user = new.user

        # Ignorer les bots
        if user.is_bot:
            return

        # Logger dans la base
        conn = get_db()
        conn.execute(
            """INSERT OR IGNORE INTO group_joins 
               (user_id, username, first_name, last_name, joined_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user.id, user.username or "", user.first_name or "",
             user.last_name or "", datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()

        logger.info(f"Nouveau membre: {user.first_name} (ID:{user.id})")

        # ── Notifier l'admin ──
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"🆕 *Nouveau membre dans le groupe !*\n\n"
                        f"👤 {user.first_name} {user.last_name or ''}\n"
                        f"📱 @{user.username or 'aucun username'}\n"
                        f"🆔 `{user.id}`\n"
                        f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    ),
                    parse_mode="Markdown",
                )
            except Exception as e:
                logger.error(f"Erreur notif admin: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  COMMANDES DE BASE
# ═══════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Salut {user.first_name} ! 👋\n\n"
        f"🔗 Devenir ambassadeur → /monlien\n"
        f"📊 Tes stats → /messtats\n"
        f"💰 Mode de paiement → /paiement\n"
        f"🏦 Ma cagnotte → /macagnotte\n"
        f"❓ Aide → /aide",
    )


async def cmd_groupid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    await update.message.reply_text(
        f"ℹ️ *Infos :*\n"
        f"📛 {chat.title or chat.first_name or '—'}\n"
        f"🆔 Chat ID : `{chat.id}`\n"
        f"👤 Ton ID : `{user.id}`",
        parse_mode="Markdown",
    )


# ═══════════════════════════════════════════════════════════════════════
#  AFFILIATION
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
        pay = _payment_label(existing["payment_method"]) if existing["payment_method"] else None

        text = (
            f"🔗 *Ton lien d'ambassadeur :*\n\n"
            f"👉 `{landing_link}`\n\n"
            f"Partage-le partout (Snap, Insta, WhatsApp, TikTok…) !\n\n"
        )
        if pay:
            text += f"💰 Rémunération : {pay}\n"
        text += f"📊 Stats → /messtats\n🏦 Cagnotte → /macagnotte\n🔄 Paiement → /paiement"

        await update.message.reply_text(text, parse_mode="Markdown")
        if not existing["payment_method"]:
            await _ask_payment_method(update)
        conn.close()
        return

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

    landing_link = f"{LANDING_URL}/ref/{ref_code}"
    await update.message.reply_text(
        f"🎉 *Bienvenue dans le programme ambassadeur Pepi-Lab !*\n\n"
        f"🔗 Ton lien :\n👉 `{landing_link}`\n\n"
        f"Partage-le partout — chaque personne qui rejoint via ce lien "
        f"sera comptabilisée à ton nom !\n\n"
        f"📊 Stats → /messtats\n🏦 Cagnotte → /macagnotte",
        parse_mode="Markdown",
    )
    await _ask_payment_method(update)


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
    pay = _payment_label(affiliate["payment_method"]) if affiliate["payment_method"] else "Non défini (/paiement)"
    cagnotte = affiliate["cagnotte"] or 0

    conn.close()

    text = (
        f"📊 *Tes stats Pepi-Lab*\n\n"
        f"🔗 Code : `{ref_code}`\n"
        f"💰 Paiement : {pay}\n"
        f"🏦 Cagnotte : *{cagnotte:.2f}€*\n\n"
        f"_Partage ton lien et suis tes stats ici !_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ═══════════════════════════════════════════════════════════════════════
#  CAGNOTTE
# ═══════════════════════════════════════════════════════════════════════

async def cmd_macagnotte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """L'affilié vérifie sa cagnotte."""
    user = update.effective_user
    conn = get_db()
    affiliate = conn.execute(
        "SELECT * FROM affiliates WHERE user_id = ?", (user.id,)
    ).fetchone()
    conn.close()

    if not affiliate:
        await update.message.reply_text("Tape /monlien pour devenir ambassadeur !")
        return

    cagnotte = affiliate["cagnotte"] or 0
    pay = _payment_label(affiliate["payment_method"]) if affiliate["payment_method"] else "Non défini"

    await update.message.reply_text(
        f"🏦 *Ta cagnotte Pepi-Lab*\n\n"
        f"💰 Solde : *{cagnotte:.2f}€*\n"
        f"💳 Mode de paiement : {pay}\n\n"
        f"🔄 Changer le mode → /paiement",
        parse_mode="Markdown",
    )


async def cmd_cagnotte_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin : /cagnotte @username +10 ou /cagnotte @username -5 ou /cagnotte (voir tout)."""
    if not is_admin(update.effective_user.id):
        return

    args = context.args

    # /cagnotte sans argument → voir toutes les cagnottes
    if not args:
        conn = get_db()
        rows = conn.execute("""
            SELECT user_id, first_name, username, cagnotte, payment_method, payment_details
            FROM affiliates
            ORDER BY cagnotte DESC
        """).fetchall()
        conn.close()

        if not rows:
            await update.message.reply_text("Aucun ambassadeur. Les gens doivent faire /monlien d'abord.")
            return

        text = "🏦 *CAGNOTTES*\n\n"
        total = 0
        for r in rows:
            u = f"@{r['username']}" if r["username"] else f"ID:`{r['user_id']}`"
            pay = _payment_label(r["payment_method"]) if r["payment_method"] else "❌"
            c = r["cagnotte"] or 0
            total += c
            text += f"• *{r['first_name']}* {u} → *{c:.2f}€* | {pay}\n"
        text += f"\n💰 Total à payer : *{total:.2f}€*"

        await update.message.reply_text(text, parse_mode="Markdown")
        return

    # /cagnotte @username +10
    if len(args) < 2:
        await update.message.reply_text(
            "Usage :\n"
            "`/cagnotte` → voir toutes les cagnottes\n"
            "`/cagnotte @username +10` → ajouter 10€\n"
            "`/cagnotte @username -5` → retirer 5€\n"
            "`/cagnotte @username =0` → remettre à 0",
            parse_mode="Markdown",
        )
        return

    target = args[0].replace("@", "").strip()
    amount_str = args[1].strip()

    conn = get_db()

    # Chercher par user_id d'abord (le plus fiable)
    affiliate = None
    if target.isdigit():
        affiliate = conn.execute(
            "SELECT * FROM affiliates WHERE user_id = ?", (int(target),)
        ).fetchone()

    # Sinon par username
    if not affiliate:
        affiliate = conn.execute(
            "SELECT * FROM affiliates WHERE username = ? COLLATE NOCASE", (target,)
        ).fetchone()

    # Sinon par prénom
    if not affiliate:
        affiliate = conn.execute(
            "SELECT * FROM affiliates WHERE first_name = ? COLLATE NOCASE", (target,)
        ).fetchone()

    # Sinon par code affilié
    if not affiliate:
        affiliate = conn.execute(
            "SELECT * FROM affiliates WHERE ref_code = ? COLLATE NOCASE", (target,)
        ).fetchone()

    if not affiliate:
        conn.close()
        await update.message.reply_text(f"❌ Ambassadeur '{target}' introuvable.")
        return

    old_cagnotte = affiliate["cagnotte"] or 0

    if amount_str.startswith("="):
        new_cagnotte = float(amount_str[1:])
    elif amount_str.startswith("+"):
        new_cagnotte = old_cagnotte + float(amount_str[1:])
    elif amount_str.startswith("-"):
        new_cagnotte = old_cagnotte - float(amount_str[1:])
    else:
        try:
            new_cagnotte = old_cagnotte + float(amount_str)
        except ValueError:
            conn.close()
            await update.message.reply_text("❌ Montant invalide.")
            return

    conn.execute(
        "UPDATE affiliates SET cagnotte = ? WHERE user_id = ?",
        (new_cagnotte, affiliate["user_id"]),
    )
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"✅ *Cagnotte mise à jour*\n\n"
        f"👤 {affiliate['first_name']} @{affiliate['username'] or '—'}\n"
        f"💰 {old_cagnotte:.2f}€ → *{new_cagnotte:.2f}€*",
        parse_mode="Markdown",
    )

    # Notifier l'affilié
    try:
        diff = new_cagnotte - old_cagnotte
        if diff > 0:
            emoji = "🎉"
            sign = "+"
        elif diff < 0:
            emoji = "📤"
            sign = ""
        else:
            emoji = "🔄"
            sign = ""

        await context.bot.send_message(
            chat_id=affiliate["user_id"],
            text=(
                f"{emoji} *Mise à jour de ta cagnotte Pepi-Lab*\n\n"
                f"💰 {sign}{diff:.2f}€\n"
                f"🏦 Nouveau solde : *{new_cagnotte:.2f}€*"
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  PAIEMENT
# ═══════════════════════════════════════════════════════════════════════

def _payment_label(method: str) -> str:
    return {"code_promo": "🏷️ Code promo", "rib": "🏦 RIB", "crypto": "₿ Crypto"}.get(method, "")


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
        await update.message.reply_text("Tape /monlien d'abord !")
        return

    current = affiliate["payment_method"]
    details = affiliate["payment_details"]

    text = "💰 *Mode de paiement actuel :*\n\n"
    if current:
        text += _payment_label(current)
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
            "🏷️ *Code promo sélectionné !*\n🔄 Changer → /paiement",
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
            "🏦 *Virement sélectionné*\n\nEnvoie-moi ton IBAN dans le prochain message.",
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
            "₿ *Crypto sélectionné*\n\nEnvoie-moi ton adresse wallet + réseau (BTC, ETH, USDT TRC20…).",
            parse_mode="Markdown",
        )
    elif data == "pay_later":
        conn.close()
        await query.edit_message_text("👌 Tu pourras configurer plus tard avec /paiement.")


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if update.effective_chat.type != "private":
        return

    text = update.message.text.strip()
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
            await update.message.reply_text("⚠️ IBAN trop court. Réessaie ou /paiement pour changer.")
            conn.close()
            return
        conn.execute(
            "UPDATE affiliates SET payment_details=?, awaiting_input='' WHERE user_id=?",
            (clean, user.id),
        )
        conn.commit()
        conn.close()
        masked = f"{clean[:8]}...{clean[-4:]}" if len(clean) > 12 else clean
        await update.message.reply_text(f"✅ *RIB enregistré !*\n📋 `{masked}`", parse_mode="Markdown")
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=f"🏦 RIB — {user.first_name} @{user.username or '—'}\n`{clean}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass

    elif input_type == "crypto":
        if len(text) < 10:
            await update.message.reply_text("⚠️ Adresse trop courte. Réessaie.")
            conn.close()
            return
        conn.execute(
            "UPDATE affiliates SET payment_details=?, awaiting_input='' WHERE user_id=?",
            (text, user.id),
        )
        conn.commit()
        conn.close()
        masked = f"{text[:6]}...{text[-4:]}" if len(text) > 10 else text
        await update.message.reply_text(f"✅ *Wallet enregistré !*\n📋 `{masked}`", parse_mode="Markdown")
        for aid in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=aid,
                    text=f"₿ Wallet — {user.first_name} @{user.username or '—'}\n`{text}`",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


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
    tj = conn.execute("SELECT COUNT(*) as c FROM group_joins").fetchone()["c"]
    total_cagnotte = conn.execute("SELECT COALESCE(SUM(cagnotte),0) as s FROM affiliates").fetchone()["s"]

    y = (datetime.now() - timedelta(hours=24)).isoformat()
    j24 = conn.execute("SELECT COUNT(*) as c FROM group_joins WHERE joined_at>?", (y,)).fetchone()["c"]

    top = conn.execute("""
        SELECT first_name, username, ref_code, payment_method, cagnotte
        FROM affiliates ORDER BY cagnotte DESC LIMIT 10
    """).fetchall()

    recent = conn.execute("""
        SELECT first_name, username, joined_at
        FROM group_joins ORDER BY joined_at DESC LIMIT 10
    """).fetchall()
    conn.close()

    text = (
        f"📊 *DASHBOARD PEPI-LAB*\n\n"
        f"👥 Ambassadeurs : *{ta}*\n"
        f"🆕 Membres groupe : *{tj}*\n"
        f"💰 Cagnottes totales : *{total_cagnotte:.2f}€*\n\n"
        f"⏱ *24h :* {j24} nouveaux membres\n"
    )
    if top:
        text += "\n🏆 *Ambassadeurs :*\n"
        for i, t in enumerate(top, 1):
            u = f"@{t['username']}" if t["username"] else ""
            c = t["cagnotte"] or 0
            text += f"  {i}. {t['first_name']} {u} — *{c:.2f}€*\n"
    if recent:
        text += "\n🕐 *Derniers membres :*\n"
        for r in recent:
            d = datetime.fromisoformat(r["joined_at"]).strftime("%d/%m %H:%M")
            u = f"@{r['username']}" if r["username"] else ""
            text += f"  • {r['first_name']} {u} ({d})\n"

    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_affilies(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn = get_db()
    rows = conn.execute("SELECT * FROM affiliates ORDER BY cagnotte DESC").fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Aucun ambassadeur.")
        return

    text = "👥 *AMBASSADEURS*\n\n"
    for a in rows:
        u = f"@{a['username']}" if a["username"] else "—"
        d = datetime.fromisoformat(a["created_at"]).strftime("%d/%m/%Y")
        pay = _payment_label(a["payment_method"]) if a["payment_method"] else "❌"
        c = a["cagnotte"] or 0
        det = ""
        if a["payment_details"]:
            det = f"\n  📋 `{a['payment_details']}`"
        text += (
            f"• *{a['first_name']} {a['last_name'] or ''}*\n"
            f"  {u} | ID: `{a['user_id']}`\n"
            f"  Code: `{a['ref_code']}` | 💰 {pay} | 🏦 {c:.2f}€ | {d}{det}\n\n"
        )
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i+4000], parse_mode="Markdown")


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    import csv, io
    conn = get_db()

    aff = conn.execute("SELECT * FROM affiliates").fetchall()
    o1 = io.StringIO()
    w1 = csv.writer(o1)
    w1.writerow(["id","username","prenom","nom","code","paiement","details","cagnotte","date"])
    for a in aff:
        w1.writerow([a["user_id"],a["username"],a["first_name"],a["last_name"],
                      a["ref_code"],a["payment_method"],a["payment_details"],
                      a["cagnotte"],a["created_at"]])
    b1 = io.BytesIO(o1.getvalue().encode("utf-8"))
    b1.name = f"ambassadeurs_{datetime.now().strftime('%Y%m%d')}.csv"
    await update.message.reply_document(b1, caption="📄 Ambassadeurs")

    joins = conn.execute("SELECT * FROM group_joins ORDER BY joined_at DESC").fetchall()
    o2 = io.StringIO()
    w2 = csv.writer(o2)
    w2.writerow(["id","username","prenom","nom","rejoint_le"])
    for j in joins:
        w2.writerow([j["user_id"],j["username"],j["first_name"],j["last_name"],j["joined_at"]])
    b2 = io.BytesIO(o2.getvalue().encode("utf-8"))
    b2.name = f"membres_{datetime.now().strftime('%Y%m%d')}.csv"
    await update.message.reply_document(b2, caption="📄 Membres du groupe")
    conn.close()


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if is_admin(user.id):
        text = (
            "🤖 *ADMIN*\n"
            "/stats — Dashboard\n"
            "/affilies — Ambassadeurs + paiements\n"
            "/cagnotte — Voir toutes les cagnottes\n"
            "/cagnotte @user +10 — Ajouter 10€\n"
            "/cagnotte @user -5 — Retirer 5€\n"
            "/cagnotte @user =0 — Reset\n"
            "/export — CSV\n"
            "/groupid — ID du chat\n\n"
            "🔧 *PUBLIC*\n"
            "/monlien — Devenir ambassadeur\n"
            "/messtats — Mes stats\n"
            "/macagnotte — Mon solde\n"
            "/paiement — Mode de rémunération\n"
            "/aide — Aide"
        )
    else:
        text = (
            "🤖 *Commandes :*\n\n"
            "/monlien — Mon lien d'ambassadeur\n"
            "/messtats — Mes stats\n"
            "/macagnotte — Ma cagnotte\n"
            "/paiement — Mode de rémunération\n"
            "/aide — Aide"
        )
    await update.message.reply_text(text, parse_mode="Markdown")


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Détection nouveaux membres dans le groupe
    app.add_handler(ChatMemberHandler(track_new_member, ChatMemberHandler.CHAT_MEMBER))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_payment, pattern="^pay_"))

    # Commandes publiques
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("monlien", cmd_monlien))
    app.add_handler(CommandHandler("messtats", cmd_messtats))
    app.add_handler(CommandHandler("macagnotte", cmd_macagnotte))
    app.add_handler(CommandHandler("paiement", cmd_paiement))
    app.add_handler(CommandHandler("groupid", cmd_groupid))
    app.add_handler(CommandHandler("aide", cmd_help))
    app.add_handler(CommandHandler("help", cmd_help))

    # Commandes admin
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("affilies", cmd_affilies))
    app.add_handler(CommandHandler("cagnotte", cmd_cagnotte_admin))
    app.add_handler(CommandHandler("export", cmd_export))

    # Texte libre (RIB / wallet)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))

    logger.info("Bot Pepi-Lab démarré !")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
