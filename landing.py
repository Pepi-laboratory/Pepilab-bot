"""
Landing page Pepi-Lab — v4 SIMPLE
==================================
Affiche les règles → clic → rejoint le groupe directement.
Tracking par clics côté serveur.
"""

import os
import sqlite3
import hashlib
import logging
from datetime import datetime

from flask import Flask, request, render_template_string, redirect, jsonify

app = Flask(__name__)

BOT_USERNAME = os.environ.get("BOT_USERNAME", "Pepilabobot")
GROUP_LINK = os.environ.get("GROUP_LINK", "https://t.me/+d7g_9MFJ1XQxYmQ0")
DB_PATH = os.environ.get("DB_PATH", "clicks.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_clicks_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS clicks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ref_code    TEXT NOT NULL,
            clicked_at  TEXT NOT NULL,
            ip_hash     TEXT,
            accepted    INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    conn.close()


def log_click(ref_code: str, ip: str, accepted: bool = False):
    try:
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO clicks (ref_code, clicked_at, ip_hash, accepted) VALUES (?, ?, ?, ?)",
            (ref_code, datetime.now().isoformat(), ip_hash, 1 if accepted else 0),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erreur log clic: {e}")


LANDING_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Pepi-Lab 🧬</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0a0a1a 0%, #1a1a3e 50%, #0d0d2b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .card {
            background: rgba(255,255,255,0.04);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 24px;
            padding: 40px 28px;
            max-width: 440px;
            width: 100%;
            text-align: center;
        }
        
        .logo { font-size: 52px; margin-bottom: 12px; }
        
        h1 {
            font-size: 26px;
            font-weight: 700;
            margin-bottom: 6px;
            background: linear-gradient(135deg, #a78bfa, #60a5fa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 28px;
            line-height: 1.6;
        }

        .rules {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 16px;
            padding: 24px 20px;
            text-align: left;
            margin-bottom: 28px;
        }

        .rules h2 {
            font-size: 15px;
            font-weight: 600;
            margin-bottom: 16px;
            color: #cbd5e1;
            text-align: center;
        }

        .rule {
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 12px;
            font-size: 14px;
            color: #94a3b8;
            line-height: 1.5;
        }

        .rule:last-child { margin-bottom: 0; }

        .rule .check {
            color: #4ade80;
            font-size: 16px;
            flex-shrink: 0;
            margin-top: 1px;
        }
        
        .btn-join {
            display: inline-block;
            background: linear-gradient(135deg, #4ade80, #22c55e);
            color: #0a0a1a;
            text-decoration: none;
            padding: 18px 32px;
            border-radius: 14px;
            font-size: 17px;
            font-weight: 700;
            width: 100%;
            transition: transform 0.15s, box-shadow 0.15s;
            box-shadow: 0 4px 20px rgba(74,222,128,0.3);
            border: none;
            cursor: pointer;
        }
        
        .btn-join:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 24px rgba(74,222,128,0.4);
        }

        .note {
            margin-top: 20px;
            font-size: 11px;
            color: #475569;
            line-height: 1.5;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🧬</div>
        <h1>Pepi-Lab</h1>
        <p class="subtitle">
            Bienvenue ! Pour rejoindre notre communauté,<br>
            prends connaissance des règles ci-dessous.
        </p>

        <div class="rules">
            <h2>📝 Règles de la communauté</h2>
            <div class="rule">
                <span class="check">✔️</span>
                <span>L'ensemble de notre catalogue est destiné exclusivement à la recherche.</span>
            </div>
            <div class="rule">
                <span class="check">✔️</span>
                <span>Respect et courtoisie obligatoires.</span>
            </div>
            <div class="rule">
                <span class="check">✔️</span>
                <span>Pas de spam ni de démarchage privé.</span>
            </div>
            <div class="rule">
                <span class="check">✔️</span>
                <span>Discrétion absolue exigée.</span>
            </div>
        </div>
        
        <a href="/ref/{{ ref_code }}/accept" class="btn-join">
            ✅ J'accepte — Rejoindre le groupe
        </a>

        <p class="note">
            En cliquant, tu confirmes avoir lu et accepté les règles ci-dessus.
        </p>
    </div>
</body>
</html>
"""


@app.route("/ref/<ref_code>")
def referral_landing(ref_code):
    """Page d'accueil avec les règles."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    log_click(ref_code, client_ip, accepted=False)
    logger.info(f"Vue page: code={ref_code}")
    return render_template_string(LANDING_HTML, ref_code=ref_code)


@app.route("/ref/<ref_code>/accept")
def accept_and_join(ref_code):
    """Le client a accepté les règles — log + redirection vers le groupe."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    log_click(ref_code, client_ip, accepted=True)
    logger.info(f"Accepté + rejoint: code={ref_code}")
    return redirect(GROUP_LINK)


@app.route("/")
def home():
    return redirect(f"https://t.me/{BOT_USERNAME}")


@app.route("/api/recent-accepts")
def recent_accepts():
    """API pour le bot — retourne les derniers clics 'accepté' (10 min)."""
    try:
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(minutes=10)).isoformat()
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT ref_code, clicked_at FROM clicks 
               WHERE accepted = 1 AND clicked_at > ?
               ORDER BY clicked_at DESC LIMIT 20""",
            (cutoff,),
        ).fetchall()
        conn.close()
        return jsonify([{"ref_code": r["ref_code"], "clicked_at": r["clicked_at"]} for r in rows])
    except Exception as e:
        return jsonify([])


init_clicks_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
