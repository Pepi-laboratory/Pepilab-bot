"""
Landing page d'affiliation — Pepi-Lab
======================================
Version corrigée : pas de vérification du code en base,
juste log du clic et redirection vers le bot.
"""

import os
import sqlite3
import hashlib
import logging
from datetime import datetime

from flask import Flask, redirect, request, render_template_string

app = Flask(__name__)

BOT_USERNAME = os.environ.get("BOT_USERNAME", "Pepilabobot")
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
            ip_hash     TEXT
        )
    """)
    conn.commit()
    conn.close()


def log_click(ref_code: str, ip: str):
    try:
        ip_hash = hashlib.sha256(ip.encode()).hexdigest()[:16]
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO clicks (ref_code, clicked_at, ip_hash) VALUES (?, ?, ?)",
            (ref_code, datetime.now().isoformat(), ip_hash),
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
            max-width: 420px;
            width: 100%;
            text-align: center;
        }
        
        .logo { font-size: 52px; margin-bottom: 12px; }
        
        h1 {
            font-size: 24px;
            font-weight: 700;
            margin-bottom: 6px;
            background: linear-gradient(135deg, #a78bfa, #60a5fa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .subtitle {
            color: #94a3b8;
            font-size: 14px;
            margin-bottom: 32px;
            line-height: 1.6;
        }
        
        .btn-telegram {
            display: inline-block;
            background: linear-gradient(135deg, #0088cc, #0066aa);
            color: white;
            text-decoration: none;
            padding: 16px 32px;
            border-radius: 14px;
            font-size: 17px;
            font-weight: 600;
            width: 100%;
            transition: transform 0.15s, box-shadow 0.15s;
            box-shadow: 0 4px 20px rgba(0,136,204,0.3);
        }
        
        .btn-telegram:hover {
            transform: translateY(-1px);
            box-shadow: 0 6px 24px rgba(0,136,204,0.4);
        }
        
        .separator {
            display: flex;
            align-items: center;
            margin: 28px 0;
            color: #475569;
            font-size: 13px;
        }
        
        .separator::before, .separator::after {
            content: '';
            flex: 1;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        
        .separator span { padding: 0 12px; }
        
        .fallback {
            background: rgba(255,255,255,0.03);
            border-radius: 14px;
            padding: 20px;
        }
        
        .fallback p {
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 12px;
            line-height: 1.5;
        }
        
        .code-box {
            background: rgba(96,165,250,0.1);
            border: 1px dashed rgba(96,165,250,0.4);
            border-radius: 10px;
            padding: 14px;
            font-family: 'SF Mono', Monaco, monospace;
            font-size: 20px;
            font-weight: 700;
            letter-spacing: 3px;
            color: #60a5fa;
            cursor: pointer;
        }
        
        .code-box:active { background: rgba(96,165,250,0.2); }
        
        .copy-hint {
            font-size: 11px;
            color: #475569;
            margin-top: 8px;
        }
        
        .steps {
            text-align: left;
            margin-top: 16px;
            list-style: none;
        }
        
        .steps li {
            font-size: 13px;
            color: #94a3b8;
            margin-bottom: 6px;
            padding-left: 28px;
            position: relative;
        }
        
        .steps li::before { position: absolute; left: 0; }
        .steps li:nth-child(1)::before { content: '1️⃣'; }
        .steps li:nth-child(2)::before { content: '2️⃣'; }
        .steps li:nth-child(3)::before { content: '3️⃣'; }
        
        .redirect-notice {
            margin-top: 24px;
            font-size: 12px;
            color: #475569;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">🧬</div>
        <h1>Pepi-Lab</h1>
        <p class="subtitle">
            Bienvenue ! On t'envoie vers notre communauté Telegram.
        </p>
        
        <a href="tg://resolve?domain={{ bot_username }}&start={{ ref_code }}" 
           class="btn-telegram" id="tg-link">
            📲 Ouvrir dans Telegram
        </a>
        
        <div class="separator"><span>Si ça ne s'ouvre pas</span></div>
        
        <div class="fallback">
            <p>Ouvre Telegram, cherche <strong>@{{ bot_username }}</strong> et envoie ce code :</p>
            <div class="code-box" onclick="copyCode()" id="code-box">
                {{ ref_code }}
            </div>
            <div class="copy-hint" id="copy-hint">Appuie pour copier</div>
            
            <ol class="steps">
                <li>Ouvre Telegram</li>
                <li>Cherche @{{ bot_username }}</li>
                <li>Envoie : <strong>/code {{ ref_code }}</strong></li>
            </ol>
        </div>
        
        <p class="redirect-notice" id="redirect-notice">
            Redirection automatique dans <span id="countdown">3</span>s…
        </p>
    </div>

    <script>
        function copyCode() {
            const code = "/code {{ ref_code }}";
            navigator.clipboard.writeText(code).then(() => {
                document.getElementById('copy-hint').textContent = '✅ Copié !';
                setTimeout(() => {
                    document.getElementById('copy-hint').textContent = 'Appuie pour copier';
                }, 2000);
            }).catch(() => {
                const el = document.createElement('textarea');
                el.value = code;
                document.body.appendChild(el);
                el.select();
                document.execCommand('copy');
                document.body.removeChild(el);
                document.getElementById('copy-hint').textContent = '✅ Copié !';
            });
        }

        let seconds = 3;
        const countdownEl = document.getElementById('countdown');
        const timer = setInterval(() => {
            seconds--;
            countdownEl.textContent = seconds;
            if (seconds <= 0) {
                clearInterval(timer);
                window.location.href = "tg://resolve?domain={{ bot_username }}&start={{ ref_code }}";
                setTimeout(() => {
                    window.location.href = "https://t.me/{{ bot_username }}?start={{ ref_code }}";
                }, 1500);
                document.getElementById('redirect-notice').textContent = 
                    "Si Telegram ne s'ouvre pas, utilise le bouton ou le code ci-dessus.";
            }
        }, 1000);
    </script>
</body>
</html>
"""


@app.route("/ref/<ref_code>")
def referral_landing(ref_code):
    """Affiche la page et logge le clic — pas de vérification en base."""
    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
    log_click(ref_code, client_ip)
    logger.info(f"Clic affilié: code={ref_code}")

    return render_template_string(
        LANDING_HTML,
        ref_code=ref_code,
        bot_username=BOT_USERNAME,
    )


@app.route("/")
def home():
    return redirect(f"https://t.me/{BOT_USERNAME}")


# Init DB au démarrage
init_clicks_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
