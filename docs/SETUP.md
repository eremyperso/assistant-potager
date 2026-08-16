# SETUP.md


## Project Overview

**Assistant Potager** is an intelligent gardening tracker for amateur gardeners. It combines:
- A **Telegram Bot** (bot.py) for voice/text command input
- A **FastAPI REST API** (main.py) serving a Progressive Web App
- **PostgreSQL** for event storage
- **Groq LLM** (Llama 3.3-70b + Whisper) for natural language parsing and analytics

The core flow: user dictates a gardening event → Groq extracts structured JSON → normalized and stored as an `Evenement` linked to a `Parcelle`.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (uses SQLite in-memory, no PostgreSQL needed)
pytest tests/
pytest tests/test_us006_renommer_parcelle.py   # single test file
pytest tests/ -k "test_name"                   # single test by name

# Apply latest database migration
psql -d potager -f migrations/migration_v12.sql
```

### Lancer le bot Telegram et l'API en local (PowerShell, Windows)

Le shell par défaut est PowerShell, pas bash — `VAR=val cmd` ne fonctionne pas, et
`uvicorn`/`python` doivent venir du venv du projet (`.venv/`), pas du PATH global.

```powershell
cd "C:\Users\eremy\OneDrive - SQLI\Documents\GitHub\assistant-potager"
.\.venv\Scripts\Activate.ps1          # active le venv pour la session courante
$env:APP_ENV = "dev"                  # reste actif pour tout le terminal, une seule fois

# Bot Telegram — pas de --reload possible, il faut arrêter (Ctrl+C) et relancer
# manuellement à chaque modification de bot.py / groq_client.py / config.py
python bot.py

# API FastAPI (http://localhost:8000) — sert aussi le frontend buildé (frontend/dist)
# --reload recharge automatiquement à chaque modification de fichier Python
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
# NB: main.py n'a pas de bloc __main__ — `python main.py` ne lance rien, il faut passer par uvicorn.

# Si Activate.ps1 est bloqué par la politique d'exécution PowerShell, contourner via :
.\.venv\Scripts\python.exe -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Mettre à jour le frontend si l'interface change

Le dashboard React (`frontend/`, Vite) peut tourner de deux façons :

```powershell
# Mode dev — hot reload instantané, pointe sur l'API via frontend/.env.local (VITE_API_URL)
cd frontend
npm install        # une seule fois / après changement de dépendances
npm run dev        # http://localhost:3000

# Mode "comme en prod" — l'API FastAPI sert le build statique
cd frontend
npm run build       # génère frontend/dist
# puis (re)démarrer l'API pour qu'elle serve le nouveau build :
cd ..
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

`main.py` sert `frontend/dist` en priorité (fallback sur `static/` si le build React est absent) —
toute modification de l'UI nécessite un `npm run build` avant de se refléter via l'API,
le mode `npm run dev` (port 3000) suffit pour itérer rapidement sans rebuild.

### Redéployer l'environnement dev local (pull + deps + migrations)

```powershell
.\update_dev.ps1
.\update_dev.ps1 -SkipPull   # depuis un hook git
.\update_dev.ps1 -Force      # tout rejouer
```

## Environment Setup

Copy `.env.example` to `.env.dev` and fill in:
- `APP_ENV` — `dev` or `prod`
- `TELEGRAM_BOT_TOKEN`
- `GROQ_API_KEY`
- `DATABASE_URL` — PostgreSQL connection string

Config is loaded from `.env.{APP_ENV}` via `config.py`.

## Architecture

### Entry Points

**bot.py** — Telegram bot. Handles voice notes (transcribed via Whisper) and text commands. Runs a daily 5am job to fetch weather via Open-Meteo.

#### Telegram Bot — Commandes slash

| Commande | Paramètres | Description |
|----------|------------|-------------|
| `/start` | — | Menu principal + compteur d'événements |
| `/help` | `[parcelle\|semis\|godet\|recolte\|stock\|stats]` | Aide générale ou ciblée par mot-clé |
| `/version` | — | Affiche la version de l'app (`bot.py:458`) |
| `/stats` | — | Statistiques saison (végétatif vs reproducteur) |
| `/stats <culture>` | `<culture>` | Détail par variété pour une culture donnée |
| `/stats <culture> <date>` | `[culture] [JJ/MM/AAAA\|AAAA-MM-JJ]` | Stats à une date de référence (`bot.py:3191`) |
| `/historique` | — | 10 derniers événements |
| `/ask` | `[question en langage naturel]` | Question analytique (ou saisie interactive si sans arg) |
| `/corriger` | — | Lancer le flux de correction d'un événement existant |
| `/plan` | — | Plan d'occupation global du potager |
| `/plan <parcelle>` | `<nom_parcelle>` | Plan filtré sur une parcelle spécifique |
| `/plan <date>` | `[JJ/MM/AAAA\|AAAA-MM-JJ]` | État du potager à une date de référence (`bot.py:2677`) |
| `/parcelle ajouter <nom> [exposition] [superficie]` | `<nom> [exposition] [superficie_m2]` | Créer une parcelle (détection de doublons) |
| `/parcelle modifier <nom> clé=valeur …` | `<nom> exposition=X superficie=X ordre=X` | Modifier les métadonnées |
| `/parcelle renommer <ancien> <nouveau>` | `<ancien_nom> <nouveau_nom>` | Renommer (propagation sur tout l'historique) |
| `/parcelle lister` | — | Lister toutes les parcelles actives |
| `/parcelles` | — | Alias de `/parcelle lister` (`bot.py:4665`) |
| `/vendre <culture> [variété] <quantité>` | `<culture> [variété] <quantité>` | Enregistrer une vente de plants pépinière (`bot.py:4585`) |
| `/meteo` | — | Déclencher la météo manuellement (job auto à 05h00) |
| `/tts` | — | Afficher l'état de la synthèse vocale |
| `/tts_on` | — | Activer les réponses vocales |
| `/tts_off` | — | Désactiver les réponses vocales |

#### Clavier inline (boutons persistants)

Menu principal : `🎤 Nouvelle action vocale` · `🔍 Interroger` · `📋 Historique` · `📊 Stats` · `✏️ Corriger`

Après enregistrement : `➕ Autre action` · `🔍 Interroger mes données` · `📋 Historique` · `🏠 Menu principal`

#### Callbacks inline (patterns, `bot.py:4670`)

| Pattern | Déclencheur |
|---------|-------------|
| `godet_*` | Sélection de variété lors d'une mise en godet |
| `recolte_*` | Sélection de variété lors d'une récolte |
| `vendu_*` | Sélection de variété lors d'une vente |
| `perte_*` | Confirmation de perte |
| `action_*` | Confirmation d'une action enregistrée |
| `parcelle_suppr_*` | Confirmation de suppression de parcelle |

#### Intents vocaux reconnus (classification Groq)

`ACTION` · `INTERROGER` · `STATS` · `HISTORIQUE` · `PLAN` · `CORRIGER` · `SUPPRIMER` · `MENU` · `NOUVELLE`

#### Messages non-slash (handlers, `bot.py:4686`)

| Type | Pipeline |
|------|----------|
| **Message vocal** | Transcription Whisper → classification intent → action correspondante |
| **Message texte libre** | Même pipeline que vocal (classification intent → action) |



### Documentation disponible

Tous les docs sont dans `docs/` :
- `docs/00_INDEX_NAVIGATION.md` — guide de navigation
- `docs/RESUME_EXECUTIF_1PAGE.md` — synthèse 5 min
- `docs/SCHEMAS_ARCHITECTURE_ASCII.md` — diagrammes avant/après + TEST MATRIX
- `docs/PLAN_IMPLEMENTATION_20h.md` — code exact à implémenter (référence quotidienne)
- `docs/AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` — contexte complet

### Quick Start

1. Lire `docs/RESUME_EXECUTIF_1PAGE.md` (5 min)
2. Implémenter `docs/PLAN_IMPLEMENTATION_20h.md` → section Jour 1–2
3. Tester via `docs/SCHEMAS_ARCHITECTURE_ASCII.md` → TEST MATRIX


## Base de données — Serveur Scaleway

PostgreSQL hébergé sur un VPS Scaleway. Deux bases en production :

| Base | Owner | Usage |
|------|-------|-------|
| `potager_dev` | `potager_user` | Environnement de développement |
| `potager_prod` | `potager_user` | Environnement de production |

### Accès local via tunnel SSH

```powershell
# Ouvrir le tunnel (laisser tourner)
ssh -L 5433:localhost:5432 root@<IP_SERVEUR> -N
```

Puis dans pgAdmin (ou tout client PostgreSQL) :
- Host : `localhost`
- Port : `5433`
- Username : `potager_user`
- DB dev : `potager_dev` / DB prod : `potager_prod`

### Serveur Hetzner (`162.55.57.49`) — accès direct sans tunnel

PostgreSQL 14 (cluster `main`), mêmes bases/owner que ci-dessus. Accès direct configuré
depuis pgAdmin, restreint à l'IP fixe du poste client (whitelist, pas d'ouverture publique).

Conf côté serveur (déjà appliquée, à reproduire si le serveur est réinstallé) :

1. `/etc/postgresql/14/main/postgresql.conf` :
   ```
   listen_addresses = '*'
   ssl = on
   ```
2. `/etc/postgresql/14/main/pg_hba.conf` (ligne ajoutée en bas) :
   ```
   host    potager_dev,potager_prod    potager_user    <IP_CLIENTE>/32    scram-sha-256
   ```
3. `systemctl restart postgresql`
4. Hetzner Cloud Firewall (`potager-firewall`, console web, pas depuis le serveur) :
   règle inbound TCP port `5432`, source = `<IP_CLIENTE>/32` (jamais `0.0.0.0/0`)

⚠️ Si l'IP publique du poste client change, il faut mettre à jour à la fois la ligne
`pg_hba.conf` et la règle du firewall Hetzner, sinon la connexion est refusée.

pgAdmin (sans tunnel) : Host `162.55.57.49`, Port `5432`, Username `potager_user`,
SSL mode `Require`.



## Vérification d'e-mail (US-044) — Brevo, ImprovMX, Scaleway DNS

Chaîne de services impliquée dans l'inscription web (`POST /auth/register` →
mail de vérification → `GET /auth/verify-email`). Documentée ici pour pouvoir
tout reconfigurer à l'identique en cas de perte totale d'accès à ces comptes
tiers — les secrets eux-mêmes (clé API Brevo) ne sont **jamais** dans ce
fichier, uniquement dans `.env.dev` / `.env.prod` (non versionnés).

### Vue d'ensemble de l'architecture

```
Utilisateur → PWA → API FastAPI (serveur Hetzner)
                        │
                        │ POST https://api.brevo.com/v3/smtp/email
                        ▼
                     Brevo (envoi du mail de vérification)
                        │
                        ▼
              noreply@potager.eremy.fr (adresse expéditrice)
                        │  redirection (pas de vraie boîte mail)
                        ▼
                  ImprovMX → boîte Gmail personnelle
                  (sert uniquement à recevoir le mail de
                   confirmation d'expéditeur envoyé par Brevo)

DNS de eremy.fr → géré chez Scaleway (Domains & Web Hosting > Domains & DNS)
Serveur applicatif (bot + API + PWA) → hébergé chez Hetzner (VPS Cloud)
```

Point clé : **le domaine `eremy.fr` est enregistré et son DNS géré chez
Scaleway**, alors que le serveur applicatif tourne chez **Hetzner** — deux
hébergeurs distincts. L'enregistrement DNS `A` de `potager.eremy.fr` pointe
vers le serveur Hetzner (site + API) ; les enregistrements `MX`/`TXT` ajoutés
pour ImprovMX coexistent avec lui sans conflit.

### Pourquoi Brevo plutôt qu'un SMTP auto-hébergé

Hetzner bloque le port 25 sortant par défaut sur ses VPS Cloud (anti-spam ;
déblocage possible sur ticket après ~1 mois d'ancienneté, au cas par cas) et
ses plages d'IP sont fréquemment blacklistées par les grands webmails — la
délivrabilité y serait mauvaise même débloqué. Brevo (société française,
hébergement UE, 300 mails/jour gratuits à vie) est donc appelé exclusivement
via son API HTTPS (`app/services/email.py`), jamais via SMTP sortant depuis
le VPS.

### Reconfiguration de zéro (perte totale d'accès)

1. **Compte Brevo** (brevo.com, gratuit, sans CB) :
   - Créer le compte, confirmer l'e-mail
   - **SMTP & API → API Keys** : générer une clé API par environnement
     (`assistant-potager-dev`, `assistant-potager-prod`) — le quota gratuit
     de 300 mails/jour est partagé entre toutes les clés d'un même compte
   - **Expéditeurs, domaine, IP → Expéditeurs → Ajouter un expéditeur** :
     `noreply@potager.eremy.fr`, nom affiché `Assistant Potager`
   - Sur la popup "Authentifier votre domaine maintenant ?" → **"Reporter à
     plus tard"** (l'authentification complète du domaine — SPF/DKIM via
     enregistrements DNS individuels, jamais la délégation NS qui casserait
     le site web — est une amélioration de délivrabilité optionnelle, pas un
     prérequis)
   - Cliquer le lien de confirmation reçu sur `noreply@potager.eremy.fr`
     (voir étape ImprovMX ci-dessous pour pouvoir le recevoir)

2. **Compte ImprovMX** (improvmx.com, gratuit) — redirection de mail, sans
   héberger de vraie boîte :
   - **Add domain** → `potager.eremy.fr`
   - Récupérer les enregistrements `MX` (x2, priorités 10/20) et `TXT` (SPF)
     affichés par ImprovMX
   - Les ajouter dans la zone DNS Scaleway (voir étape 3), avec `Name` =
     `potager` (pas le domaine complet — Scaleway complète avec `.eremy.fr`)
   - Configurer l'alias `noreply` (ou `*`) → adresse Gmail personnelle de
     réception

3. **Zone DNS Scaleway** (console.scaleway.com → Domains & Web Hosting →
   Domains & DNS → `eremy.fr` → onglet **DNS Zones**) :
   - Ajouter les enregistrements MX/TXT d'ImprovMX (étape 2) sur le nom
     `potager`, **sans toucher** à l'enregistrement `A` existant qui pointe
     `potager.eremy.fr` vers le serveur Hetzner
   - Le domaine lui-même (registrar + zone DNS) reste chez Scaleway même si
     rien d'autre n'y est hébergé — ne pas chercher ce domaine côté Hetzner

4. **Variables d'environnement** à renseigner dans `.env.dev` / `.env.prod`
   (jamais commitées, cf. `.gitignore`) :
   ```
   BREVO_API_KEY=<clé générée à l'étape 1, une par environnement>
   EMAIL_FROM=noreply@potager.eremy.fr
   EMAIL_FROM_NOM=Assistant Potager
   FRONTEND_URL=<URL de la PWA — http://localhost:3000 en dev>
   ```
   `BREVO_API_KEY` vide → mode dégradé (`app/services/email.py` logue le
   lien de vérification au lieu d'appeler l'API), utilisable sans aucun des
   comptes ci-dessus tant qu'un envoi réel n'est pas nécessaire.

5. **Migration BDD** : `migrations/migration_v24.sql` (colonnes
   `verification_token_*` sur `users`) doit être rejouée si la base est
   reconstruite de zéro — `update_dev.ps1` s'en charge automatiquement en dev.

## Déploiement & Docker

### ⚠️ IMPORTANT — Protocole de déploiement

**JAMAIS** faire `pg_dump > file.sql` + import manuel. Cela crée des problèmes d'encodage (UTF-8 vs WIN1252) et de collation imprévisibles.

### ✅ Solution recommandée : Docker Compose

**TODO** — À mettre en place ASAP avant le prochain déploiement :

1. Créer `Dockerfile` (Python + dépendances)
2. Créer `docker-compose.yml` (API + PostgreSQL)
3. Utiliser **scripts de migration versionnés** (Alembic), pas de dumps manuels
4. Toutes les config via variables d'env (`.env.local`, `.env.prod`)

**Bénéfices** :
- ✅ Encodage UTF-8 natif (Linux)
- ✅ Marche identique Windows/Mac/Linux
- ✅ Zéro soucis de collation
- ✅ Redéploiement = `docker-compose up`
- ✅ Pas de stato "c'était bon sur ma machine"

**Effort estimé** : 4h (une seule fois)

**Retour sur investissement** : éviter 10h+ de galère lors du prochain déploiement
