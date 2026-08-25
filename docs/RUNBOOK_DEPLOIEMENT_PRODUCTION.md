# RUNBOOK — Déploiement & redéploiement de l'Assistant Potager

> **Statut :** Documentation d'exploitation (ops), reconstituée à partir de
> `docs/SETUP.md`, `infra/*.service`, `.github/workflows/*.yml`,
> `migrations/*.sql`, `config.py`, `main.py`, `bot.py` et
> `docs/CONCEPTION_SECURISATION_API.md`.
> **Date de rédaction :** 2026-08-24 — version applicative au moment de la
> rédaction : `v3.38.0` (voir `VERSION`).
> **Objectif :** permettre de redéployer **l'intégralité** de la solution,
> service par service, y compris **sur une infrastructure entièrement neuve**
> (perte du serveur actuel, changement d'hébergeur, etc.). Toute valeur
> marquée `<...>` est un identifiant/secret à ressaisir — ne jamais versionner
> de valeur réelle dans ce fichier.

---

## 1. Vue d'ensemble

### 1.1 Schéma des services

```
                          ┌─────────────────────────────┐
                          │   Scaleway — Domains & DNS   │
                          │   zone eremy.fr              │
                          │   A     potager.eremy.fr      → IP serveur (prod)
                          │   A     dev.potager.eremy.fr  → IP serveur (dev)
                          │   MX/TXT potager (ImprovMX)   │
                          └───────────────┬───────────────┘
                                          │ résolution DNS
                                          ▼
                    ┌──────────────────────────────────────────┐
                    │   Serveur applicatif (VPS Hetzner Cloud)  │
                    │   Un seul serveur héberge PROD + DEV      │
                    │                                            │
                    │  ┌──────────────────────────────────┐    │
                    │  │ Nginx (reverse proxy + TLS)       │    │
                    │  │ Let's Encrypt (certbot)           │    │
                    │  │  potager.eremy.fr     → :8000     │    │
                    │  │  dev.potager.eremy.fr → :8001     │    │
                    │  └──────────────┬─────────────────────┘    │
                    │                 │                          │
                    │  ┌──────────────▼───────────┐  ┌─────────┐│
                    │  │ potager-prod.service      │  │potager- ││
                    │  │ uvicorn main:app :8000     │  │prod-bot││
                    │  │ (API FastAPI + PWA/dist)   │  │.service ││
                    │  └──────────────┬───────────┘  │(polling)││
                    │  ┌──────────────▼───────────┐  └────┬────┘│
                    │  │ potager-dev.service        │       │     │
                    │  │ uvicorn main:app :8001     │       │     │
                    │  └──────────────┬───────────┘       │     │
                    │  ┌──────────────▼───────────┐  ┌────▼────┐│
                    │  │ potager-dev-bot.service    │  │Telegram ││
                    │  └────────────────────────────┘  │Bot API  ││
                    │                                  └─────────┘│
                    │  ┌────────────────────────────────────┐    │
                    │  │ PostgreSQL 14 (cluster `main`)       │    │
                    │  │  DB potager_dev / potager_prod        │    │
                    │  │  rôle potager_user (owner+migrations) │    │
                    │  │  rôle app_user (RLS, runtime app)     │    │
                    │  └────────────────────────────────────┘    │
                    └──────────────────────────────────────────┘
                                          │
                       ┌──────────────────┼───────────────────┐
                       ▼                  ▼                   ▼
                ┌─────────────┐   ┌──────────────┐   ┌────────────────┐
                │ Groq API    │   │ Brevo (mail  │   │ Google Cloud    │
                │ (LLM+Whisper)│   │ transactionnel)│  │ (OAuth Connexion│
                └─────────────┘   └──────┬───────┘   │ Google)         │
                                          │           └────────────────┘
                                          ▼
                                   ┌──────────────┐
                                   │ ImprovMX     │
                                   │ (redirection │
                                   │ noreply@...) │
                                   └──────┬───────┘
                                          ▼
                                  Boîte Gmail perso
                                  (réception uniquement)

        GitHub (eremyperso/assistant-potager)
          └─ push sur `main`  → .github/workflows/deploy.yml     (PROD)
          └─ push sur `dev`   → .github/workflows/deploy-dev.yml (DEV)
             (connexion SSH vers le VPS via secrets Actions)
```

### 1.2 Tableau récapitulatif — un service, une ligne

| # | Service | Rôle | Hébergeur / origine | Port / URL | Défini par |
|---|---------|------|----------------------|------------|------------|
| 1 | DNS `eremy.fr` | Résolution du domaine, cible l'IP du serveur applicatif | Scaleway (Domains & Web Hosting) | — | Console Scaleway (pas de fichier versionné) |
| 2 | Serveur applicatif | Héberge Nginx, PostgreSQL, API, bot — prod + dev | Hetzner Cloud (VPS) | IP publique + firewall `potager-firewall` | Console Hetzner |
| 3 | Nginx | Reverse proxy + terminaison TLS | Sur le serveur applicatif | 80/443 → 8000 (prod) / 8001 (dev) | `/etc/nginx/...` sur le serveur — **non versionné dans ce dépôt** |
| 4 | Certificats TLS | HTTPS | Let's Encrypt (certbot) | — | Renouvellement auto certbot sur le serveur |
| 5 | PostgreSQL | Stockage des données (événements, utilisateurs, potagers...) | Sur le serveur applicatif (package `postgresql-14`) | 5432 (local ; accès distant restreint par IP) | `migrations/*.sql` |
| 6 | API FastAPI — PROD | Backend REST + sert `frontend/dist` | `potager-prod.service` | `:8000` | `infra/potager-prod.service`, `main.py` |
| 7 | Bot Telegram — PROD | Commandes vocales/texte, jobs météo (05h) + purge (04h) | `potager-prod-bot.service` | polling sortant (aucun port entrant) | `infra/potager-prod-bot.service`, `bot.py` |
| 8 | API FastAPI — DEV | Environnement de recette | `potager-dev.service` | `:8001` | `infra/potager-dev.service` |
| 9 | Bot Telegram — DEV | Bot de recette | `potager-dev-bot.service` | polling sortant | `infra/potager-dev-bot.service` |
| 10 | Frontend React (PWA) | Dashboard web (Vite build statique) | Buildé en CI, servi par l'API (`frontend/dist`) | même origine que l'API | `frontend/`, `.github/workflows/deploy*.yml` |
| 11 | Groq | LLM (parsing NL) + Whisper (transcription vocale) | SaaS externe (API HTTPS) | — | `GROQ_API_KEY` |
| 12 | Brevo | Envoi des e-mails transactionnels (vérification compte, reset mot de passe) | SaaS externe (API HTTPS, jamais SMTP) | — | `BREVO_API_KEY` |
| 13 | ImprovMX | Redirection de `noreply@potager.eremy.fr` vers une boîte Gmail (réception de la confirmation d'expéditeur Brevo) | SaaS externe | — | Enregistrements DNS MX/TXT sur Scaleway |
| 14 | Google Cloud (OAuth) | Connexion "Continuer avec Google" | SaaS externe | — | `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URIS` |
| 15 | Telegram (BotFather) | Fournit le token du bot | SaaS externe | — | `TELEGRAM_BOT_TOKEN` |
| 16 | Open-Meteo | Prévisions météo | SaaS externe, gratuit, sans clé | — | appelé en dur par `bot.py` |
| 17 | GitHub Actions | CI/CD — push `main`/`dev` → déploiement SSH | GitHub | — | `.github/workflows/deploy.yml`, `deploy-dev.yml` |
| 18 | FFmpeg | Conversion MP3→OGG/Opus pour les réponses vocales Telegram | Paquet système sur le serveur | — | dégradé silencieusement si absent |

**Aucun service caché** : c'est la liste exhaustive des dépendances externes et
internes. Toute reconstruction sur une nouvelle infra doit recréer/reconfigurer
chacune de ces 18 lignes.

---

## 2. Comptes et accès requis avant de commencer

Checklist à valider **avant** toute intervention sur une nouvelle infra —
sans l'un de ces accès, une étape plus loin dans ce runbook sera bloquée :

- [ ] Accès admin au dépôt GitHub `eremyperso/assistant-potager` (pour lire le
      code, créer/mettre à jour les secrets Actions)
- [ ] Compte Hetzner Cloud (facturation active) — pour provisionner le VPS et
      son firewall
- [ ] Accès console Scaleway (Domains & Web Hosting) — propriétaire de la
      zone DNS `eremy.fr`
- [ ] Compte Brevo (ou capacité à en recréer un — gratuit, sans CB)
- [ ] Compte ImprovMX (ou capacité à en recréer un — gratuit)
- [ ] Accès à la boîte Gmail personnelle qui reçoit `noreply@potager.eremy.fr`
      (nécessaire pour confirmer l'expéditeur Brevo)
- [ ] Accès Google Cloud Console (projet OAuth existant, ou capacité à en
      créer un nouveau)
- [ ] Accès à `@BotFather` sur Telegram avec le compte propriétaire des bots
      (ou capacité à créer 2 nouveaux bots — prod + dev)
- [ ] Clé API Groq (console.groq.com — gratuite)
- [ ] Une clé SSH dédiée au déploiement CI (sera déposée sur le nouveau
      serveur et son secret privé stocké dans GitHub Actions)

---

## 3. PARTIE A — Reconstruction complète sur une infrastructure neuve

À suivre dans l'ordre : chaque étape dépend des précédentes (le DNS doit
pointer avant de générer un certificat TLS, la base doit exister avant les
migrations, etc.).

### A1 — Provisionner le serveur applicatif (VPS)

1. Créer un VPS Hetzner Cloud (Debian/Ubuntu LTS récent, Python 3.11+
   disponible ou installable). Noter la nouvelle IP publique.
2. Créer/adapter le firewall Hetzner Cloud (`potager-firewall` dans
   l'infra actuelle) avec au minimum :

   | Direction | Port | Source | Justification |
   |-----------|------|--------|----------------|
   | Inbound | 22 (SSH) | IP admin uniquement | Jamais `0.0.0.0/0` |
   | Inbound | 80, 443 | `0.0.0.0/0` | Nginx public (HTTP/HTTPS) |
   | Inbound | 5432 (PostgreSQL) | IP(s) admin uniquement (pgAdmin) | L'API se connecte en `localhost`, ce port n'a **pas** besoin d'être ouvert au public |

3. Installer les paquets système de base :
   ```bash
   sudo apt update && sudo apt install -y python3 python3-venv python3-pip \
     postgresql postgresql-contrib nginx certbot python3-certbot-nginx \
     ffmpeg git rsync
   ```
   `ffmpeg` est nécessaire pour la conversion des réponses vocales Telegram
   (dégradation silencieuse si absent — donc facile à oublier, à vérifier).
4. Créer les répertoires cibles (repris tels quels des workflows CI) :
   ```bash
   sudo mkdir -p /opt/potager-prod /opt/potager-dev
   ```
5. Déposer la clé publique SSH dédiée au déploiement (voir A13) dans
   `~/.ssh/authorized_keys` de l'utilisateur utilisé par la CI
   (`SCALEWAY_USER` — voir remarque de nommage en section 6).

### A2 — PostgreSQL : rôles, bases, accès réseau

1. Créer le rôle propriétaire applicatif (celui qui exécute les migrations,
   propriétaire des tables) :
   ```bash
   sudo -u postgres psql -c "CREATE ROLE potager_user LOGIN PASSWORD '<mot_de_passe_fort>';"
   ```
2. Créer les deux bases, une par environnement (elles cohabitent sur le
   **même cluster** PostgreSQL) :
   ```bash
   sudo -u postgres psql -c "CREATE DATABASE potager_dev  OWNER potager_user;"
   sudo -u postgres psql -c "CREATE DATABASE potager_prod OWNER potager_user;"
   ```
3. Autoriser `potager_user` à créer d'autres rôles (nécessaire pour que la
   migration `migration_v18.sql` puisse créer `app_user` — voir A8) :
   ```bash
   sudo -u postgres psql -c "ALTER ROLE potager_user CREATEROLE;"
   ```
4. Activer l'extension `unaccent` sur chaque base (recherche insensible aux
   accents) :
   ```bash
   sudo -u postgres psql -d potager_dev  -c "CREATE EXTENSION IF NOT EXISTS unaccent;"
   sudo -u postgres psql -d potager_prod -c "CREATE EXTENSION IF NOT EXISTS unaccent;"
   ```
5. Si un accès distant (pgAdmin, tunnel SSH) est nécessaire, reproduire la
   configuration documentée dans `docs/SETUP.md` (§ « Serveur Hetzner… ») :
   - `/etc/postgresql/14/main/postgresql.conf` : `listen_addresses = '*'`,
     `ssl = on`
   - `/etc/postgresql/14/main/pg_hba.conf`, ligne ajoutée :
     `host  potager_dev,potager_prod  potager_user  <IP_CLIENTE>/32  scram-sha-256`
   - `sudo systemctl restart postgresql`
   - Ouvrir le port 5432 dans le firewall Hetzner **uniquement** pour
     `<IP_CLIENTE>/32` (jamais `0.0.0.0/0`)
   - ⚠️ Toute IP cliente qui change casse cet accès des deux côtés
     (`pg_hba.conf` **et** règle firewall) — à refaire alors.

### A3 — DNS : déclarer l'URL cible (Scaleway)

Console Scaleway → **Domains & Web Hosting → Domains & DNS → `eremy.fr` →
DNS Zones**. C'est ici, et uniquement ici, que l'app est « branchée » sur
son nom de domaine — le registrar/zone DNS reste chez Scaleway même si rien
d'autre n'y est hébergé.

1. Créer/mettre à jour l'enregistrement `A` de production, en le pointant
   vers la **nouvelle** IP du serveur (A1) :
   ```
   Type A   Name potager      → <NOUVELLE_IP_SERVEUR>
   ```
2. Créer/mettre à jour l'enregistrement `A` de dev :
   ```
   Type A   Name dev.potager  → <NOUVELLE_IP_SERVEUR>
   ```
3. Laisser en place (ou recréer, voir A11) les enregistrements `MX`/`TXT`
   ImprovMX sur `potager` — sans y toucher lors du changement d'IP, ils sont
   indépendants de l'enregistrement `A`.
4. Propagation DNS : compter jusqu'à quelques heures avant de continuer avec
   Nginx/Let's Encrypt (le challenge HTTP de certbot échoue tant que le DNS
   ne résout pas vers le nouveau serveur).

### A4 — Reverse proxy Nginx + TLS

> ⚠️ **La configuration Nginx n'est pas versionnée dans ce dépôt.** Seul un
> exemple figure dans `docs/CONCEPTION_SECURISATION_API.md` (rate limiting).
> Avant de perdre l'accès à l'ancien serveur, **sauvegarder
> `/etc/nginx/sites-available/` et `/etc/nginx/conf.d/`** pour repartir d'une
> configuration fidèle plutôt que de la reconstituer de mémoire.

Configuration minimale à reproduire (deux server blocks, un par
environnement), avant activation TLS :

```nginx
# /etc/nginx/sites-available/potager-prod
server {
    listen 80;
    server_name potager.eremy.fr;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```nginx
# /etc/nginx/sites-available/potager-dev
server {
    listen 80;
    server_name dev.potager.eremy.fr;

    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Les en-têtes `X-Real-IP`/`X-Forwarded-For` sont **requis** : sans eux, le
rate limiting applicatif (`slowapi`, voir `main.py`) voit systématiquement
l'IP locale de Nginx et finit par bloquer tous les utilisateurs derrière une
seule IP. Le rate limiting Nginx (`limit_req_zone`) documenté dans
`docs/CONCEPTION_SECURISATION_API.md` §4.1 peut être ajouté en complément —
c'est une préconisation, à valider/reproduire selon ce qui était réellement
actif sur l'ancien serveur.

```bash
sudo ln -s /etc/nginx/sites-available/potager-prod /etc/nginx/sites-enabled/
sudo ln -s /etc/nginx/sites-available/potager-dev  /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# Certificats Let's Encrypt (un par sous-domaine)
sudo certbot --nginx -d potager.eremy.fr
sudo certbot --nginx -d dev.potager.eremy.fr
```

`certbot --nginx` réécrit les server blocks pour ajouter `listen 443 ssl` et
le renouvellement automatique (timer systemd `certbot.timer`, installé par
le paquet — vérifier `systemctl status certbot.timer` après coup).

### A5 — Récupérer le code applicatif depuis GitHub

Reprend exactement la logique du « premier déploiement » de
`.github/workflows/deploy.yml` (utilisable aussi bien pour `main` que pour
`dev` en changeant la branche) :

```bash
cd /opt/potager-prod
git init
git remote add origin https://github.com/eremyperso/assistant-potager.git
git fetch origin main --depth=1
git reset --hard origin/main
git checkout main
```

Pour déployer une version précise plutôt que la tête de `main` (ex. reprise
après incident, ou tag de release existant) :
```bash
git fetch origin --tags
git checkout v3.14.0        # ou tout autre tag/commit publié
```
Même procédure dans `/opt/potager-dev` avec `origin dev`.

### A6 — Environnement Python

```bash
cd /opt/potager-prod   # puis /opt/potager-dev
python3 -m venv venv
venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
```

### A7 — Secrets applicatifs : `.env.prod` / `.env.dev`

Ces fichiers ne sont **jamais** transmis par la CI ni versionnés — ils
doivent être créés **manuellement** sur le serveur, à partir de
`.env.example`, avant le premier démarrage des services. C'est l'étape la
plus facile à oublier lors d'une reconstruction d'infra : sans elle, les
services `systemd` démarrent en boucle (`Restart=on-failure`) car
`config.py` lève une exception dès que `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`,
`DATABASE_URL` ou `JWT_SECRET` sont absents (`os.environ[...]`, pas
`.get()`).

```bash
cp .env.example /opt/potager-prod/.env.prod
cp .env.example /opt/potager-dev/.env.dev
# puis éditer chaque fichier — APP_ENV=prod / APP_ENV=dev respectivement
```

| Variable | Obligatoire | Source / comment obtenir la valeur |
|----------|:---:|---|
| `APP_ENV` | ✅ | `prod` ou `dev` selon le fichier |
| `TELEGRAM_BOT_TOKEN` | ✅ | `@BotFather` → un bot **distinct** par environnement |
| `GROQ_API_KEY` | ✅ | console.groq.com (une clé par environnement recommandé) |
| `DATABASE_URL` | ✅ | `postgresql://<rôle>:<mdp>@localhost:5432/potager_prod` (ou `_dev`) — voir A8 pour le choix du rôle (`potager_user` vs `app_user`) |
| `JWT_SECRET` | ✅ | secret fort généré, ex. `openssl rand -hex 32` — **un par environnement**, jamais partagé prod/dev |
| `JWT_ACCESS_TTL_MIN` | non (défaut 15) | — |
| `JWT_REFRESH_TTL_DAYS` | non (défaut 30) | — |
| `BREVO_API_KEY` | non (mode dégradé si vide) | Brevo → SMTP & API → API Keys — voir A11 |
| `EMAIL_FROM` | non (défaut `noreply@assistant-potager.fr`) | mettre `noreply@potager.eremy.fr` — voir A11 |
| `EMAIL_FROM_NOM` | non (défaut `Assistant Potager`) | — |
| `FRONTEND_URL` | non (défaut `http://localhost:3000`) | **doit** pointer vers l'URL réelle de la PWA (`https://potager.eremy.fr` / `https://dev.potager.eremy.fr`) — sinon les liens de vérification e-mail sont cassés |
| `GOOGLE_CLIENT_ID` | non (connecteur masqué si vide) | Google Cloud Console — voir A12 |
| `GOOGLE_CLIENT_SECRET` | non | Google Cloud Console — voir A12 |
| `GOOGLE_REDIRECT_URIS` | non | `https://potager.eremy.fr/auth/oauth/google/callback` (prod), `https://dev.potager.eremy.fr/auth/oauth/google/callback` (dev) — séparées par des virgules si plusieurs |
| `PWA_URL` | non (texte générique par défaut) | URL affichée dans le message d'onboarding Telegram |

`GROQ_MODEL`, `GROQ_WHISPER_MODEL` et `GROQ_REASONING_EFFORT` sont codés en
dur dans `config.py` (pas de variable d'environnement) — rien à
configurer côté `.env.*` pour eux.

### A8 — Migrations SQL

Appliquer **dans l'ordre numérique** toutes les migrations `migration_v*.sql`
(pas les `rollback_v*.sql`), avec le rôle propriétaire (`potager_user`) :

```bash
cd /opt/potager-prod   # puis /opt/potager-dev avec DATABASE_URL de potager_dev
set -a && source .env.prod && set +a
for migration in $(ls migrations/migration_v*.sql | sort -t v -k2 -n); do
  echo ">>> ${migration}"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 \
    -v app_user_password='<mot_de_passe_app_user>' \
    -f "${migration}"
done
```

Points d'attention critiques :

- **`migration_v18.sql`** crée le rôle non-superuser `app_user` et active la
  Row-Level Security (isolation par `potager_id`) sur `evenements`,
  `parcelles`, `culture_config`. Elle a besoin de la variable psql
  `app_user_password` (passée en `-v`, jamais écrite en clair dans le
  fichier). **`app_user` est un rôle global au cluster** : comme
  `potager_dev` et `potager_prod` partagent le même cluster, ce rôle n'est
  réellement créé qu'une fois — appliquer cette migration sur dev **et**
  prod avec le **même** mot de passe `app_user_password`, sinon la seconde
  exécution ignore silencieusement la valeur fournie (le `CREATE ROLE` ne
  s'exécute que si le rôle n'existe pas encore).
- ⚠️ **Après `migration_v18.sql`, `DATABASE_URL` doit pointer vers `app_user`
  (pas `potager_user`)** pour que la protection RLS soit réellement active
  côté application — tant que l'app se connecte avec le rôle propriétaire
  des tables, PostgreSQL le fait bypasser les policies RLS par défaut
  (comportement standard, pas un bug). Concrètement :
  ```
  DATABASE_URL=postgresql://app_user:<app_user_password>@localhost:5432/potager_prod
  ```
  Les opérations de migration (comme ci-dessus) et les sauvegardes
  continuent, elles, à utiliser `potager_user` — c'est voulu (voir le
  commentaire en tête de `migration_v18.sql`).
- `migration_v24.sql` ajoute les colonnes de vérification d'e-mail
  (nécessaires à A11), `migration_v30.sql` ajoute `users.google_sub`
  (nécessaire à A12) — aucune n'est optionnelle, elles suivent le même flux
  ci-dessus.
- En cas d'erreur en cours de script, les fichiers `rollback_v*.sql`
  (disponibles à partir de `rollback_v16.sql`) permettent de revenir en
  arrière migration par migration.
- La CI (`deploy.yml`/`deploy-dev.yml`) journalise les migrations déjà
  appliquées dans `/opt/potager-<env>/.migrations_applied` pour ne pas les
  rejouer — sur une infra neuve ce fichier n'existe pas encore, donc
  **toutes** les migrations s'appliquent au premier passage : c'est le
  comportement attendu.

### A9 — Build et déploiement du frontend

Le build s'effectue habituellement sur le runner CI (Node préinstallé sur
`ubuntu-latest`), pas sur le serveur applicatif — mais peut se faire depuis
n'importe quelle machine disposant de Node 18+ si la CI n'est pas encore
opérationnelle sur la nouvelle infra :

```bash
cd frontend
echo "VITE_API_URL=https://potager.eremy.fr" > .env.local   # prod
# echo "VITE_API_URL=https://dev.potager.eremy.fr" > .env.local  # dev
npm install
npm run build
```

⚠️ `frontend/.env.prod` et `frontend/.env.example` contiennent des valeurs
d'exemple non représentatives (`assistant-potager.example.com`,
`http://localhost:8001`) — c'est bien `.env.local`, généré dynamiquement à
la volée à chaque build (voir `.github/workflows/deploy.yml` ligne
« Build frontend React »), qui fait foi. Ne pas éditer `.env.prod` en
pensant que cela changera l'URL réellement buildée.

Puis déployer le build statique sur le serveur (l'API le sert en priorité
via `frontend/dist`, avec repli sur `static/` — l'ancienne PWA — si absent) :

```bash
rsync -az --delete frontend/dist/ <user>@<serveur>:/opt/potager-prod/frontend/dist/
```

### A10 — Services systemd (API + bot)

Les 4 unités sont versionnées dans `infra/` — à copier telles quelles :

```bash
sudo cp infra/potager-prod.service     /etc/systemd/system/
sudo cp infra/potager-prod-bot.service /etc/systemd/system/
sudo cp infra/potager-dev.service      /etc/systemd/system/
sudo cp infra/potager-dev-bot.service  /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now potager-prod.service potager-prod-bot.service
sudo systemctl enable --now potager-dev.service  potager-dev-bot.service
```

Points à vérifier :
- Les 4 unités tournent avec `User=root` et `WorkingDirectory=/opt/potager-<env>`
  — aucun utilisateur système dédié n'est utilisé actuellement, à reproduire
  tel quel sauf décision explicite de durcissement.
- `EnvironmentFile=/opt/potager-<env>/.env.<env>` : le fichier doit exister
  **avant** le premier démarrage (voir A7), et **toute modification de ce
  fichier nécessite un `systemctl restart`** — il n'est lu qu'au démarrage
  du process (`python-dotenv` dans `config.py`), un simple `reload` ne
  suffit pas.
- Les deux bots (`*-bot.service`) tournent en **polling** Telegram
  (`app.run_polling()` dans `bot.py`) : aucun port entrant, aucun webhook à
  déclarer côté Telegram — seule une sortie HTTPS vers `api.telegram.org`
  est nécessaire.
- Vérification :
  ```bash
  systemctl status potager-prod.service potager-prod-bot.service --no-pager
  journalctl -u potager-prod.service -f
  ```

### A11 — Mail no-reply (Brevo + ImprovMX + DNS)

Chaîne complète, à reconstruire de zéro si les comptes tiers sont perdus.
Référence détaillée déjà présente dans `docs/SETUP.md` (§ « Vérification
d'e-mail — Brevo, ImprovMX, Scaleway DNS ») — résumé actionnable ici :

1. **Compte Brevo** (brevo.com, gratuit, sans CB) :
   - SMTP & API → API Keys → générer une clé par environnement
     (`assistant-potager-dev`, `assistant-potager-prod` — quota gratuit de
     300 mails/jour **partagé** entre toutes les clés du compte)
   - Expéditeurs, domaine, IP → Ajouter un expéditeur :
     `noreply@potager.eremy.fr`, nom affiché « Assistant Potager »
   - Sur la popup d'authentification de domaine → **« Reporter à plus
     tard »** (l'authentification SPF/DKIM est une amélioration de
     délivrabilité optionnelle, pas un prérequis)
   - Cliquer le lien de confirmation reçu sur `noreply@potager.eremy.fr`
     (nécessite l'étape 2 pour pouvoir le recevoir)
2. **Compte ImprovMX** (improvmx.com, gratuit) :
   - Add domain → `potager.eremy.fr`
   - Récupérer les enregistrements `MX` (x2) et `TXT` (SPF) fournis
   - Configurer l'alias `noreply` (ou `*`) → adresse Gmail personnelle de
     réception
3. **Zone DNS Scaleway** (`eremy.fr` → DNS Zones) :
   - Ajouter les `MX`/`TXT` d'ImprovMX sur le nom `potager` — **sans
     toucher** à l'enregistrement `A` (voir A3)
4. **Variables d'environnement**, dans `.env.prod`/`.env.dev` (voir A7) :
   ```
   BREVO_API_KEY=<clé de l'étape 1>
   EMAIL_FROM=noreply@potager.eremy.fr
   EMAIL_FROM_NOM=Assistant Potager
   FRONTEND_URL=<URL réelle de la PWA de cet environnement>
   ```
   `BREVO_API_KEY` vide → mode dégradé : `app/services/email.py` logue le
   lien de vérification en `INFO` au lieu d'appeler l'API. Utilisable
   temporairement le temps de reconfigurer Brevo, mais aucun e-mail réel
   n'est envoyé (inscriptions/reset mot de passe restent fonctionnels via
   les logs uniquement).
5. Vérifier que `migration_v24.sql` (colonnes `verification_token_*`) a bien
   été appliquée (voir A8).

**Diagnostic en cas de panne** (mails non reçus après un redéploiement) :
runbook pas-à-pas déjà rédigé dans `docs/SETUP.md`, section finale
« Diagnostic — emails … non reçus » — reprend `journalctl`, vérification du
`.env.<env>` réellement chargé par le process, test direct de l'API Brevo en
`curl`, puis vérification ImprovMX/DNS.

### A12 — Connexion Google (OAuth)

1. **Console Google Cloud** (console.cloud.google.com) → créer/sélectionner
   un projet dédié.
2. **Écran de consentement OAuth** : type « Externe », renseigner nom,
   e-mail d'assistance, domaine. **Publier l'application** avant la mise en
   prod réelle (en mode « Test », seuls les comptes ajoutés comme testeurs
   peuvent se connecter).
3. **Identifiants → Créer des identifiants → ID client OAuth**, type
   **Application Web**. Déclarer les URI de redirection, **une par
   environnement**, pointant sur l'**API** (jamais le frontend — l'échange
   du code est serveur à serveur) :
   ```
   https://potager.eremy.fr/auth/oauth/google/callback
   https://dev.potager.eremy.fr/auth/oauth/google/callback
   ```
4. Reporter ces valeurs, à l'octet près, dans `GOOGLE_REDIRECT_URIS` (voir
   A7) — toute divergence fait rejeter la requête par la liste blanche
   applicative.
5. `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/`GOOGLE_REDIRECT_URIS` absents
   ou vides → connecteur Google **totalement masqué** côté PWA
   (`GET /auth/oauth/providers` répond `{"google": false}`) : le reste de
   l'app fonctionne sans ce provisionnement, il peut être fait après coup.
6. Vérifier que `migration_v30.sql` (colonne `users.google_sub`) a bien été
   appliquée (voir A8).

### A13 — CI/CD GitHub Actions : secrets à redéclarer

Sur GitHub → repo `assistant-potager` → **Settings → Secrets and variables →
Actions**, redéclarer (les workflows échouent silencieusement en attente de
connexion SSH sinon) :

| Secret | Contenu |
|--------|---------|
| `SCALEWAY_HOST` | IP ou nom DNS du **nouveau** serveur applicatif |
| `SCALEWAY_USER` | Utilisateur SSH de déploiement sur ce serveur |
| `SCALEWAY_SSH_PRIVATE_KEY` | Clé privée SSH correspondant à la clé publique déposée en A1 |
| `APP_USER_PASSWORD` | Mot de passe de `app_user` (voir A8) — **doit être identique** entre déploiement dev et prod, cf. remarque migration_v18 |

> ⚠️ **Attention au nom des secrets** : ils s'appellent `SCALEWAY_*` pour des
> raisons historiques, mais pointent vers le serveur applicatif **Hetzner**
> (`docs/SETUP.md` confirme l'hébergement Hetzner pour l'app, Scaleway
> n'intervient que pour le DNS). Ne pas se laisser piéger en cherchant un
> serveur Scaleway lors d'une reconstruction — c'est bien l'IP Hetzner de
> A1 qu'il faut mettre dans `SCALEWAY_HOST`.

Une fois ces secrets posés, un simple `git push` sur `main` (prod) ou `dev`
(dev) redéclenche tout le pipeline automatisé (A5 → A10, hors provisionnement
initial déjà fait manuellement en A1-A4/A7/A11/A12).

### A14 — Job de purge planifiée (US-084)

Contrairement à un job de fond classique, **il n'existe pas de cron/timer
systemd séparé** pour la purge des potagers supprimés au-delà du délai de
grâce de 30 jours : elle est planifiée **à l'intérieur du process bot**
(`bot.py`, `app.job_queue.run_daily(job_purge_potagers, time=04:00
Europe/Paris)`), au même titre que le job météo (05:00). Conséquence directe
pour l'exploitation :

- La purge automatique **ne s'exécute que si `potager-prod-bot.service`
  (respectivement `potager-dev-bot.service`) est up** au moment prévu — un
  bot arrêté pendant plusieurs jours ne rattrape pas les purges manquées
  rétroactivement.
- Filet de sécurité manuel disponible à tout moment, indépendant du bot :
  ```bash
  cd /opt/potager-prod
  venv/bin/python tools/purger_potagers.py --dry-run   # liste sans effacer
  venv/bin/python tools/purger_potagers.py             # purge réelle, idempotente
  ```
  utile après une interruption prolongée du bot, ou pour vérifier l'état
  avant une purge automatique.

### A15 — Vérifications post-déploiement (smoke tests)

À dérouler dans l'ordre, prod puis dev :

```bash
# 1. Services actifs
systemctl is-active potager-prod.service potager-prod-bot.service

# 2. API accessible en HTTPS via le domaine (pas juste en localhost)
curl -sf https://potager.eremy.fr/health | grep '"status":"ok"' \
  || curl -sf https://potager.eremy.fr/health

# 3. Frontend servi
curl -sfo /dev/null -w "%{http_code}\n" https://potager.eremy.fr/

# 4. Certificat TLS valide (pas d'avertissement navigateur)
curl -vI https://potager.eremy.fr/ 2>&1 | grep -i "SSL certificate verify"
```

- **5. Bot Telegram** : envoyer `/start` au bot de prod depuis Telegram,
  vérifier une réponse immédiate.
- **6. Inscription + e-mail** : `POST /auth/register` avec une adresse de
  test, vérifier la réception réelle du mail de vérification (pas
  seulement le mode dégradé en logs) — sinon dérouler le diagnostic de
  `docs/SETUP.md`.
- **7. Connexion Google** (si configurée) : `GET /auth/oauth/providers`
  doit renvoyer `{"google": true}`, puis tester un login complet de bout en
  bout.
- **8. RLS active** : confirmer que `DATABASE_URL` pointe bien vers
  `app_user` (voir A8) — `psql "$DATABASE_URL" -c "SELECT current_user;"`
  doit répondre `app_user`, pas `potager_user`.
- **9. Job météo/purge** : dans les logs du bot le lendemain, vérifier les
  lignes `🌅 JOB MÉTÉO planifié` / `🗑️ JOB PURGE planifié` au démarrage.

---

## 4. PARTIE B — Redéploiement courant (infra déjà en place)

### B1 — Automatique (cas normal)

Un simple push sur la branche concernée déclenche tout :
```bash
git push origin main   # → .github/workflows/deploy.yml  (prod)
git push origin dev    # → .github/workflows/deploy-dev.yml (dev)
```
Le pipeline enchaîne : sync code → dépendances Python → build frontend →
rsync du build → extensions PostgreSQL → migrations non encore appliquées →
(ré)installation des unités systemd → restart des services → smoke test →
écriture dans `.deploy_history`. Suivre l'exécution dans l'onglet
**Actions** du dépôt GitHub.

Déclenchement manuel possible sans nouveau commit : onglet Actions →
sélectionner le workflow → **Run workflow**.

### B2 — Manuel (CI indisponible, infra déjà provisionnée)

`deploy.sh` reproduit une partie du pipeline (nécessite `DEPLOY_HOST`,
suppose que `.env.prod`, PostgreSQL, Nginx et les unités systemd existent
déjà — c'est un script de mise à jour de code, pas de provisionnement) :
```bash
DEPLOY_HOST=user@host ./deploy.sh
```
Pour l'environnement dev local en watch continu (poste de développement) :
```powershell
.\update_dev.ps1          # pull + deps + migrations
.\update_dev.ps1 -Force   # tout rejouer même si déjà appliqué
```

---

## 5. Rollback

1. **Application** : `git checkout <tag_ou_commit_précédent>` dans
   `/opt/potager-<env>`, réinstaller les dépendances si `requirements.txt` a
   changé, `systemctl restart potager-<env>.service potager-<env>-bot.service`.
2. **Base de données** : dérouler les `rollback_v*.sql` correspondants dans
   l'ordre **décroissant**, en partant de la dernière migration appliquée
   après la version ciblée. Rollbacks disponibles à partir de
   `rollback_v16.sql` — les migrations antérieures (`v2` à `v15`) n'ont pas
   de rollback versionné, revenir avant elles nécessite une restauration de
   sauvegarde (voir point de vigilance ci-dessous).
3. **Frontend** : rebuild depuis le commit ciblé (A9) + `rsync --delete`.

---

## 6. Points de vigilance identifiés pendant la rédaction de ce runbook

À traiter ou à surveiller, sans bloquer un redéploiement mais à ne pas
perdre de vue pour la résilience de l'infra :

- **Aucune sauvegarde PostgreSQL automatisée** n'existe dans ce dépôt (pas
  de script `pg_dump` planifié, pas de job de sauvegarde). Sur une perte
  totale du serveur, seules les données encore présentes en mémoire d'un
  tunnel pgAdmin ouvert, ou un `pg_dump` manuel fait à temps, permettraient
  de récupérer les données de production. C'est un vrai risque de perte de
  données, distinct de ce runbook (qui ne recrée que la structure/services,
  pas le contenu métier).
- **La configuration Nginx n'est pas versionnée** dans ce dépôt — seul un
  extrait indicatif figure dans `docs/CONCEPTION_SECURISATION_API.md`
  (document marqué « préconisation, en attente de validation PO », donc pas
  garanti représentatif de ce qui tourne réellement). Sauvegarder
  `/etc/nginx/` de l'ancien serveur **avant** toute migration d'infra est le
  seul moyen fiable de reproduire la configuration exacte en place.
- **`app_user` vs `potager_user` dans `DATABASE_URL`** : `migration_v18.sql`
  explicite noir sur blanc que l'application doit se connecter avec
  `app_user` pour que la RLS soit effective, mais le rôle exact configuré
  dans `DATABASE_URL` en production n'a pas pu être vérifié depuis cette
  session (pas d'accès au serveur). **À vérifier explicitement en A15/étape
  8** avant de considérer une nouvelle infra comme sécurisée à l'identique
  de l'ancienne.
- **Swagger (`/docs`/`/redoc`)** : `docs/CONCEPTION_SECURISATION_API.md`
  propose de le désactiver en production (`docs_url=None` si
  `APP_ENV=prod`), mais `main.py` instancie `FastAPI(title=..., version=...)`
  sans ce paramètre — Swagger reste donc accessible publiquement en l'état
  du code étudié pour ce runbook, indépendamment de l'infra.
- **Noms des secrets GitHub Actions** (`SCALEWAY_*`) qui pointent en réalité
  vers un serveur **Hetzner** — piège documenté en A13, à ne pas retomber
  dedans lors d'une reconstruction sous pression.
