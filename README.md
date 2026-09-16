# 🤖 Bot Telegram d'Affiliation — Chabrier Nuisibles

Système complet de parrainage/affiliation pour Telegram avec :
- Landing page anti-perte de tracking (Snapchat, Instagram, TikTok)
- Génération de liens d'invitation uniques vers le groupe privé
- Dashboard admin complet

---

## 🏗️ Comment ça marche

```
Affilié partage son lien (Snap, Insta, WhatsApp…)
        ↓
  Landing page web             ← clic enregistré côté serveur ✅
        ↓
  Redirection vers le Bot      ← protocole tg:// (préserve le tracking)
        ↓
  Bot enregistre le parrainage ← nom + ID + username du client & affilié
        ↓
  Bot donne un lien d'invitation unique vers le groupe privé
        ↓
  Notifications → admin + affilié
        ↓
  Si redirection échoue → code de secours à taper manuellement
```

---

## ⚙️ Variables d'environnement

| Variable                 | Description                                    | Exemple                                |
|-------------------------|------------------------------------------------|----------------------------------------|
| `BOT_TOKEN`             | Token du bot (via @BotFather)                  | `7123456789:AAHx...`                   |
| `ADMIN_IDS`             | Ton/tes ID Telegram (virgule si plusieurs)      | `123456789`                            |
| `BOT_USERNAME`          | Username du bot sans @                          | `ChabrierAffiliateBot`                 |
| `GROUP_CHAT_ID`         | ID de ton groupe privé (nombre négatif)         | `-1001234567890`                       |
| `LANDING_URL`           | URL de la landing (Railway te la donne)          | `https://chabrier-ref.up.railway.app`  |
| `INVITE_LINK_EXPIRY_HOURS` | Durée de validité des liens d'invitation (optionnel) | `24` (par défaut)               |
| `DB_PATH`               | Chemin base de données (optionnel)              | `affiliates.db`                        |

### Comment trouver le GROUP_CHAT_ID ?

1. Ajoute le bot @RawDataBot dans ton groupe privé
2. Il va afficher un JSON — cherche `"id": -100...`
3. Copie ce nombre (avec le `-`)
4. Retire @RawDataBot du groupe

### Comment trouver ton ADMIN_ID ?

1. Cherche @userinfobot sur Telegram
2. Envoie /start
3. Il te donne ton ID

---

## 🚀 Déploiement pas à pas

### Étape 1 — Créer un compte GitHub (2 min)

1. Va sur [github.com](https://github.com)
2. Clique "Sign up" → email → mot de passe → username
3. C'est tout, tu en as besoin juste pour héberger le code

### Étape 2 — Mettre le code sur GitHub

1. Connecte-toi sur GitHub
2. Clique le **+** en haut à droite → **New repository**
3. Nom : `affiliate-bot` — laisse "Public" — clique **Create**
4. Clique **"uploading an existing file"**
5. Glisse-dépose les 4 fichiers (bot.py, landing.py, requirements.txt, Procfile)
6. Clique **Commit changes**

### Étape 3 — Déployer sur Railway (5 min, gratuit)

1. Va sur [railway.app](https://railway.app)
2. Connecte-toi avec ton compte GitHub
3. **New Project** → **Deploy from GitHub Repo** → choisis `affiliate-bot`
4. Railway va détecter le Procfile et lancer les 2 services (bot + landing)

### Étape 4 — Ajouter les variables

Dans Railway → ton projet → **Variables** :

```
BOT_TOKEN=colle_ton_token_ici
ADMIN_IDS=ton_id_telegram
BOT_USERNAME=nom_de_ton_bot
GROUP_CHAT_ID=-100xxxxxxxxxx
LANDING_URL=https://affiliate-bot-production.up.railway.app
```

(Railway te donne le LANDING_URL dans Settings → Domains)

### Étape 5 — Ajouter le bot comme admin du groupe

1. Ouvre ton groupe privé Telegram
2. Paramètres → Administrateurs → Ajouter un admin
3. Cherche ton bot → ajoute-le
4. Active la permission **"Inviter des utilisateurs via un lien"**

---

## 📱 Commandes du bot

### Pour les ambassadeurs

| Commande         | Description                              |
|-----------------|------------------------------------------|
| `/monlien`      | Générer son lien d'ambassadeur           |
| `/messtats`     | Voir ses stats (clics, clients, conversion) |
| `/code ABC123`  | Entrer un code de parrainage manuellement|
| `/aide`         | Aide                                     |

### Pour toi (admin)

| Commande    | Description                                       |
|------------|---------------------------------------------------|
| `/stats`   | Dashboard global + stats 24h + top affiliés        |
| `/affilies`| Tous les ambassadeurs avec détails + performances  |
| `/clients` | Tous les clients parrainés avec source du tracking |
| `/export`  | Export CSV complet (ambassadeurs + clients)         |
| `/newlink` | Générer un lien d'invitation manuellement          |

---

## 🔧 Le problème Snapchat/Instagram — résolu en 3 couches

1. **Landing page** → le clic est enregistré AVANT la redirection (côté serveur)
2. **Protocole tg://** → redirige mieux que t.me depuis les navigateurs intégrés
3. **Code de secours** → affiché sur la page si la redirection échoue — le client tape `/code ABC` dans le bot

---

## 📁 Structure du projet

```
affiliate-bot/
├── bot.py             # Bot Telegram (tracking, invitations, notifications, admin)
├── landing.py         # Landing page Flask (anti-perte Snap/Insta)
├── requirements.txt   # Dépendances Python
├── Procfile           # Config Railway (lance bot + landing)
└── README.md          # Ce fichier
```
