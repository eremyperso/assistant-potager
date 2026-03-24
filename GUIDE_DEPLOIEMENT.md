# 🌿 Assistant Potager — Guide de Déploiement & Exploitation

**Version :** 2.0 — Mars 2026  
**Stack :** Python 3.11+ · Groq (Whisper + LLaMA) · Telegram Bot · PostgreSQL · FastAPI

---

## 📁 Structure du projet

```
assistant-potager/app/
├── bot.py                  ← Bot Telegram principal (POINT D'ENTRÉE)
├── main.py                 ← API FastAPI (optionnel, PWA)
├── config.py               ← Clés API + connexion base
├── requirements.txt        ← Dépendances Python
│
├── database/
│   ├── db.py               ← Connexion SQLAlchemy
│   └── models.py           ← Modèle table evenements
│
├── llm/
│   └── groq_client.py      ← Parsing Groq + questions analytiques
│
├── utils/
│   ├── actions.py          ← Normalisation actions potager
│   └── date_utils.py       ← Conversion dates
│
├── migrations/
│   ├── migration_v2.sql    ← Ajout colonnes v2
│   ├── migration_v3.sql    ← rang INTEGER
│   └── migration_v4.sql    ← Suppression colonne produit
│
└── static/                 ← PWA iPhone (optionnel)
    ├── index.html
    └── manifest.json
```

---

## ⚙️ 1. PRÉREQUIS

### Python
```
Python 3.11 ou supérieur
https://www.python.org/downloads/
```
Vérifier : `python --version`

### PostgreSQL
```
PostgreSQL 14+
https://www.postgresql.org/download/windows/
```
Vérifier : `psql --version`

### Comptes nécessaires
| Service | URL | Usage |
|---------|-----|-------|
| Groq | https://console.groq.com | Transcription Whisper + LLM |
| Telegram BotFather | @BotFather sur Telegram | Créer le bot |

---

## 🗄️ 2. BASE DE DONNÉES

### Créer la base (une seule fois)
```sql
-- Dans pgAdmin ou psql :
CREATE USER potager_user WITH PASSWORD 'Potager#2026';
CREATE DATABASE potager OWNER potager_user;
GRANT ALL PRIVILEGES ON DATABASE potager TO potager_user;
```

### Créer la table (une seule fois)
```sql
-- Se connecter à la base potager, puis :
CREATE TABLE evenements (
    id              SERIAL PRIMARY KEY,
    date            TIMESTAMP,
    type_action     VARCHAR(50),
    culture         VARCHAR(100),
    variete         VARCHAR(100),
    quantite        FLOAT,
    unite           VARCHAR(30),
    parcelle        VARCHAR(100),
    rang            INTEGER,
    duree           INTEGER,
    traitement      VARCHAR(200),
    commentaire     TEXT,
    texte_original  TEXT
);
```

### Migrations (si base existante)
```bash
# Appliquer dans l'ordre si mise à jour depuis v1 :
psql -U potager_user -d potager -f migrations/migration_v2.sql
psql -U potager_user -d potager -f migrations/migration_v3.sql
psql -U potager_user -d potager -f migrations/migration_v4.sql
```

---

## 🔑 3. CONFIGURATION

### Éditer config.py
```python
# config.py — adapter ces 3 valeurs :

DATABASE_URL = "postgresql://potager_user:Potager#2026@localhost/potager"

GROQ_API_KEY = "gsk_VOTRE_CLE_GROQ_ICI"
# → Obtenir sur : https://console.groq.com/keys

TELEGRAM_BOT_TOKEN = "VOTRE_TOKEN_TELEGRAM_ICI"
# → Obtenir via @BotFather : /newbot
```

### Alternative — Variables d'environnement (recommandé)
```bat
REM Windows — ajouter dans votre profil ou lancer.bat :
set GROQ_API_KEY=gsk_votre_cle
set TELEGRAM_BOT_TOKEN=votre_token
```

---

## 📦 4. INSTALLATION DES DÉPENDANCES

```bash
# Dans le dossier app/ :
pip install -r requirements.txt
```

### requirements.txt (contenu)
```
fastapi==0.115.0
uvicorn[standard]==0.30.0
groq>=0.13.0
python-telegram-bot==21.6
sqlalchemy==2.0.36
psycopg2-binary==2.9.10
unidecode==1.3.8
python-dotenv==1.0.1
```

---

## 🚀 5. LANCEMENT

### ▶️ Terminal 1 — Bot Telegram (OBLIGATOIRE)
```bash
cd C:\Users\eremy\Documents\assistant-potager\app
python bot.py
```

**Logs attendus au démarrage :**
```
🌿 Assistant Potager — Bot Telegram démarré
📊 Base : XX événements en base
✅ Bot en écoute...
```

### ▶️ Terminal 2 — API FastAPI (OPTIONNEL)
```bash
cd C:\Users\eremy\Documents\assistant-potager\app
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

**Accès :**
- API : http://localhost:8000
- Documentation Swagger : http://localhost:8000/docs
- PWA iPhone : http://[VOTRE-IP-LOCAL]:8000

---

## 🪟 6. LANCEMENT AUTOMATIQUE WINDOWS (optionnel)

### Créer lancer_bot.bat
```bat
@echo off
title Assistant Potager - Bot Telegram
cd /d C:\Users\eremy\Documents\assistant-potager\app
set GROQ_API_KEY=gsk_VOTRE_CLE_ICI
set TELEGRAM_BOT_TOKEN=VOTRE_TOKEN_ICI
echo 🌿 Démarrage Assistant Potager...
python bot.py
pause
```

### Démarrage automatique avec Windows (Task Scheduler)
```
1. Ouvrir : Planificateur de tâches (taskschd.msc)
2. Créer une tâche de base
3. Déclencheur : Au démarrage de Windows
4. Action : Démarrer un programme
   Programme : C:\Users\eremy\Documents\assistant-potager\app\lancer_bot.bat
5. Cocher : Exécuter même si l'utilisateur n'est pas connecté
```

---

## 💾 7. SAUVEGARDE POSTGRESQL

### Sauvegarde manuelle
```bash
pg_dump -U potager_user potager > backup_potager_$(date +%Y%m%d).sql
```

### Sauvegarde automatique Windows (Task Scheduler)
```bat
REM backup_potager.bat
@echo off
set DATE_STR=%date:~6,4%%date:~3,2%%date:~0,2%
pg_dump -U potager_user potager > C:\Backups\potager_%DATE_STR%.sql
```
Planifier : tous les jours à 2h du matin

### Restauration
```bash
psql -U potager_user -d potager < backup_potager_20260312.sql
```

---

## 📊 8. MONITORING & LOGS

### Logs console bot.py
```
HH:MM:SS │ INFO  │ 💬 MESSAGE TEXTE  : texte reçu
HH:MM:SS │ INFO  │ 🎤 TRANSCRIPTION  : texte Whisper
HH:MM:SS │ INFO  │ 🧭 INTENT         : 'texte' → ACTION/CORRIGER/...
HH:MM:SS │ INFO  │ 🤖 GROQ PARSING   : [JSON]
HH:MM:SS │ INFO  │ 💾 DB SAVE        : id=xx | action=... | culture=...
HH:MM:SS │ INFO  │ ✏️ CORRECTIONS    : {"champ": valeur}
HH:MM:SS │ INFO  │ 🗑 SUPPRESSION    : id=xx
HH:MM:SS │ WARNING│ ⚠️ JSON VIDE     : phrase non reconnue
HH:MM:SS │ ERROR │ ❌ ERREUR PARSING : détail
```

### Vérifier la base directement
```sql
-- Derniers événements
SELECT id, date::date, type_action, culture, quantite, unite
FROM evenements ORDER BY id DESC LIMIT 20;

-- Événements corrigés (trace dans texte_original)
SELECT id, texte_original FROM evenements 
WHERE texte_original LIKE '%CORR%';

-- Nettoyage entrées parasites (action null)
DELETE FROM evenements WHERE type_action IS NULL;
```

---

## 🔧 9. MODÈLES GROQ UTILISÉS

| Usage | Modèle | Pourquoi |
|-------|--------|---------|
| Transcription vocale | `whisper-large-v3-turbo` | Meilleure précision français |
| Classification intent | `llama-3.3-70b-versatile` | Robustesse NAV commands |
| Parsing action | `llama-3.3-70b-versatile` | Extraction JSON fiable |
| Questions analytiques | `llama-3.3-70b-versatile` | Réponses précises |
| Recherche correction | `llama-3.3-70b-versatile` | Extraction critères |

**Quota Groq Free Tier :**
- ~100 000 tokens/jour pour llama-3.3-70b
- Réinitialisation quotidienne automatique
- Commandes simples : ~400 tokens | Questions analytiques : ~5 000 tokens

**Optimisation possible (si quota insuffisant) :**
```python
# Dans config.py, ajouter :
GROQ_MODEL_FAST = "llama-3.1-8b-instant"  # pour classify_intent uniquement
```

---

## ☁️ 10. DÉPLOIEMENT ORACLE CLOUD (futur)

### Prérequis Oracle Cloud Always Free
```
- Compte Oracle Cloud Free Tier
- VM : Ampere A1 (ARM) 4 OCPU / 24 Go RAM (gratuit permanent)
- OS : Ubuntu 22.04
```

### Installation sur le VPS
```bash
# Sur le VPS Oracle :
sudo apt update && sudo apt install -y python3-pip postgresql

# Cloner depuis GitHub
git clone https://github.com/votre-compte/assistant-potager.git
cd assistant-potager/app

# Installer dépendances
pip3 install -r requirements.txt

# Variables d'environnement
export GROQ_API_KEY="gsk_..."
export TELEGRAM_BOT_TOKEN="..."

# Lancer en arrière-plan (systemd recommandé)
python3 bot.py &
```

### Flux de déploiement continu
```
PC Local → git push → GitHub → git pull → Oracle VPS
```

---

## 🆘 11. DÉPANNAGE

| Erreur | Cause | Solution |
|--------|-------|---------|
| `Connection refused (5432)` | PostgreSQL arrêté | Démarrer PostgreSQL |
| `Invalid token` Telegram | Token incorrect | Vérifier config.py |
| `Rate limit 429` Groq | Quota journalier atteint | Attendre réinitialisation (~24h) |
| `Can't parse entities` Telegram | Markdown invalide dans réponse | Corrigé v2 — fallback sans markdown |
| `JSON decode error` | Groq retourne texte vide | Vérifier clé API Groq |
| Action enregistrée sans type | Groq n'a pas reconnu l'action | Reformuler avec verbe explicite |

---

*Assistant Potager v2 — Emmanuel — Mars 2026*
