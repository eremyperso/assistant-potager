# CONCEPTION — Sécurisation de l'API REST Assistant Potager

> **Statut :** Préconisation technique — En attente de validation PO
> **Date :** 2026-08-18
> **Contexte :** L'API FastAPI déployée sur `potager.eremy.fr` est exposée publiquement. Les routes `/auth/register` et `/docs` (Swagger) permettent la création automatisée de comptes et l'exploration de l'API par des bots.

---

## 1. Diagnostic de la surface d'attaque actuelle

### 1.1 Vecteurs identifiés

| Vecteur | Gravité | Exploitabilité |
|---------|---------|----------------|
| Création massive de comptes (`POST /auth/register`) | 🔴 Haute | Triviale — un `curl` en boucle suffit |
| Swagger/ReDoc exposés en prod (`/docs`, `/redoc`) | 🟡 Moyenne | Facilite la reconnaissance de l'API (endpoints, schémas, modèles) |
| Brute-force login (`POST /auth/login`) | 🟡 Moyenne | Mitigé par JWT short-lived mais pas rate-limité |
| Endpoints métier sans rate-limit | 🟢 Faible | Protégés par JWT, mais un compte valide peut marteler l'API |

### 1.2 Ce qui est déjà en place

- ✅ JWT access token (15 min) + refresh token (30 j) — US-110 implémentée
- ✅ Hash mot de passe (bcrypt/passlib)
- ✅ RLS PostgreSQL + scoping `potager_id` — US-103 implémentée
- ✅ HTTPS via Let's Encrypt + Nginx reverse proxy
- ✅ Brevo configuré pour le transactionnel (infrastructure e-mail existante)
- ❌ Aucun rate limiting (ni Nginx, ni applicatif)
- ❌ Swagger accessible en production
- ❌ Aucune vérification d'e-mail à l'inscription
- ❌ Aucun mécanisme anti-bot (honeypot, CAPTCHA)

---

## 2. Architecture de sécurisation préconisée

### Principe directeur : défense en profondeur, 3 couches

```
Internet
    │
    ▼
┌──────────────────────────────────┐
│  COUCHE 1 — Nginx (rate-limit)   │  ← Bloque le volume brut
│  limit_req_zone par IP            │     avant même d'atteindre Python
└──────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────┐
│  COUCHE 2 — FastAPI (slowapi)    │  ← Rate-limit fin par route
│  + Swagger désactivé en prod     │     + protection Swagger
│  + honeypot anti-bot             │
└──────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────┐
│  COUCHE 3 — Vérification e-mail  │  ← Filtre les comptes fantômes
│  Brevo transactionnel             │     seuls les comptes vérifiés
│  is_verified + token              │     peuvent se connecter
└──────────────────────────────────┘
```

---

## 3. Mesure 1 — Désactivation de Swagger en production

### ⚖️ Arbitrage

Swagger/ReDoc exposé en prod = carte de l'API offerte aux attaquants. Aucune raison de le laisser ouvert : les développeurs utilisent l'environnement dev.

### Implémentation

```python
# main.py — création de l'app FastAPI
import os

ENV = os.getenv("APP_ENV", "dev")

app = FastAPI(
    title="Assistant Potager API",
    docs_url="/docs" if ENV == "dev" else None,
    redoc_url="/redoc" if ENV == "dev" else None,
    openapi_url="/openapi.json" if ENV == "dev" else None,
)
```

### Vérification

```bash
# En prod (APP_ENV=prod)
curl -s -o /dev/null -w "%{http_code}" https://potager.eremy.fr/docs
# Attendu : 404

# En dev (APP_ENV=dev)
curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/docs
# Attendu : 200
```

### Effort : ~5 minutes · Zéro dépendance · Zéro migration

---

## 4. Mesure 2 — Rate Limiting double couche

### 4.1 Couche Nginx (première ligne)

Le rate limiting Nginx est la défense la plus efficace car il rejette les requêtes **avant** qu'elles n'atteignent le processus Python (économie CPU, mémoire, connexions DB).

#### Configuration Nginx

```nginx
# /etc/nginx/conf.d/rate-limit.conf (inclus dans le server block)

# Zone de mémoire partagée : 10 Mo ≈ 160 000 adresses IP suivies
# Taux : 2 requêtes/seconde en moyenne par IP sur les routes auth
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=2r/s;

# Zone plus permissive pour les routes API métier
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```

```nginx
# Dans le server block de potager.eremy.fr

# Routes d'authentification — strictement limitées
location /auth/ {
    limit_req zone=auth_limit burst=5 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8001;
    # ... autres directives proxy existantes
}

# Routes API métier — limite raisonnable
location /api/ {
    limit_req zone=api_limit burst=20 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8001;
}

# Bloc catch-all existant
location / {
    proxy_pass http://127.0.0.1:8001;
}
```

#### Paramètres expliqués

| Paramètre | Valeur | Justification |
|-----------|--------|---------------|
| `rate` (auth) | `2r/s` | Un humain ne s'inscrit pas 2 fois par seconde |
| `burst` (auth) | `5` | Tolère un petit pic (formulaire soumis 2 fois, retry JS) |
| `rate` (API) | `10r/s` | Le dashboard charge ~5 requêtes simultanées au chargement |
| `burst` (API) | `20` | Marge pour le chargement initial de la PWA |
| `nodelay` | activé | Les requêtes dans le burst passent immédiatement, pas de mise en file |

#### Test

```bash
# Depuis le serveur ou une machine externe
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://potager.eremy.fr/auth/register \
    -H "Content-Type: application/json" \
    -d '{"email":"bot'$i'@spam.com","password":"test1234","nom":"Bot"}' &
done
wait
# Attendu : les premiers retournent 200/422, puis 429
```

#### Déploiement

```bash
sudo nginx -t          # Valider la syntaxe
sudo systemctl reload nginx   # Appliquer sans coupure
```

### 4.2 Couche FastAPI (slowapi) — rate limiting fin

Nginx protège par IP globalement. `slowapi` permet un contrôle plus fin : par route, par utilisateur authentifié, avec des messages d'erreur JSON propres.

#### Dépendance

```bash
pip install slowapi
```

> `slowapi` est le standard de facto pour le rate limiting FastAPI. Il wrape `limits` (la même lib que Flask-Limiter) et s'intègre nativement avec Starlette.

#### Implémentation

```python
# app/middleware/rate_limit.py

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["60/minute"],        # Limite globale par défaut
    storage_uri="memory://",             # En mémoire (suffisant mono-instance)
    # Évolution future : "redis://localhost:6379" quand Redis sera en place
)

def setup_rate_limiting(app):
    """À appeler dans main.py après création de l'app."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
```

```python
# main.py — intégration

from middleware.rate_limit import limiter, setup_rate_limiting

app = FastAPI(...)
setup_rate_limiting(app)

# Route d'inscription — limite stricte
@app.post("/auth/register")
@limiter.limit("3/hour")           # 3 inscriptions max par heure par IP
async def register(request: Request, ...):
    ...

# Route de login — limite modérée
@app.post("/auth/login")
@limiter.limit("10/minute")        # Anti brute-force
async def login(request: Request, ...):
    ...

# Route de refresh — plus permissive
@app.post("/auth/refresh")
@limiter.limit("30/minute")
async def refresh_token(request: Request, ...):
    ...
```

#### Limites recommandées par route

| Route | Limite | Raison |
|-------|--------|--------|
| `POST /auth/register` | `3/hour` par IP | Un humain ne crée pas 3 comptes en 1 heure |
| `POST /auth/login` | `10/minute` par IP | Marge pour erreur de mot de passe, anti brute-force |
| `POST /auth/refresh` | `30/minute` par IP | Renouvellement JWT automatique par la PWA |
| Routes `/api/*` (défaut) | `60/minute` par IP | Usage normal du dashboard |

#### Réponse en cas de dépassement

```json
HTTP 429 Too Many Requests
{
  "error": "Rate limit exceeded",
  "detail": "3 per 1 hour",
  "retry_after": 2847
}
```

> **Note IP derrière Nginx :** `slowapi` utilise `request.client.host`. Derrière un reverse proxy, c'est l'IP de Nginx (127.0.0.1). Il faut que Nginx transmette l'IP réelle via `X-Forwarded-For` et que FastAPI soit configuré avec `TrustedHostMiddleware` ou que `get_remote_address` lise ce header. Voir section 4.3.

### 4.3 Transmission correcte de l'IP réelle (critique)

Sans cette configuration, **tout le rate limiting applicatif se fait sur 127.0.0.1** — une seule IP pour tous les utilisateurs, ce qui bloque tout le monde dès qu'un seul dépasse la limite.

```nginx
# Dans le location block Nginx (déjà partiellement en place)
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

```python
# main.py — faire confiance au proxy Nginx local
from fastapi.middleware.trustedhost import TrustedHostMiddleware

# OU plus simple : remplacer la key_func de slowapi
from slowapi.util import get_remote_address

def get_real_ip(request: Request) -> str:
    """Récupère l'IP réelle derrière Nginx."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

# Dans rate_limit.py, remplacer :
limiter = Limiter(key_func=get_real_ip, ...)
```

### Effort total mesure 2 : ~1–2 heures · 1 dépendance (slowapi)

---

## 5. Mesure 3 — Vérification d'e-mail à l'inscription

### ⚖️ Arbitrage

C'est la mesure la plus efficace contre la pollution de données : un bot peut inventer des adresses e-mail, mais ne peut pas cliquer sur un lien de vérification. Le rate limiting seul ne protège pas contre un attaquant patient.

### 5.1 Modifications du modèle `users`

#### Migration SQL

```sql
-- migration_vXX.sql — Vérification e-mail

-- Étape 1 : Ajout des colonnes (nullable d'abord, pattern incrémental)
ALTER TABLE users
    ADD COLUMN is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN verification_token VARCHAR(64),
    ADD COLUMN verification_token_expires_at TIMESTAMP;

-- Étape 2 : Marquer les utilisateurs existants comme vérifiés
-- (ils ont déjà prouvé leur identité par usage)
UPDATE users SET is_verified = TRUE WHERE id IS NOT NULL;

-- Étape 3 : Index pour la recherche par token
CREATE INDEX idx_users_verification_token
    ON users(verification_token)
    WHERE verification_token IS NOT NULL;

-- Étape 4 : Nettoyage automatique des comptes non vérifiés (> 48h)
-- À exécuter via un job planifié (APScheduler, cf. US-124)
-- DELETE FROM users
-- WHERE is_verified = FALSE
-- AND created_at < NOW() - INTERVAL '48 hours';
```

#### Modèle SQLAlchemy

```python
# database/models.py — ajouts au modèle User

class User(Base):
    __tablename__ = "users"

    # ... colonnes existantes ...

    is_verified = Column(Boolean, nullable=False, default=False)
    verification_token = Column(String(64), nullable=True)
    verification_token_expires_at = Column(DateTime, nullable=True)
```

### 5.2 Flux d'inscription modifié

```
Utilisateur                    API FastAPI                    Brevo
    │                              │                            │
    ├── POST /auth/register ──────►│                            │
    │   {email, password, nom}     │                            │
    │                              ├── Créer user               │
    │                              │   is_verified=False        │
    │                              │   token=secrets.token_hex  │
    │                              │                            │
    │                              ├── Envoyer e-mail ─────────►│
    │                              │   via Brevo API            │
    │◄── 201 "Vérifiez votre      │                            │
    │    boîte mail"               │                            │
    │                              │                            │
    │   (clic sur le lien)         │                            │
    ├── GET /auth/verify ─────────►│                            │
    │   ?token=abc123...           │                            │
    │                              ├── is_verified = True       │
    │                              │   verification_token = NULL│
    │◄── 200 "Compte activé"      │                            │
    │                              │                            │
    ├── POST /auth/login ─────────►│                            │
    │   {email, password}          │                            │
    │                              ├── Vérifier is_verified     │
    │◄── 200 {access_token, ...}   │   ✅ → JWT                │
    │   OU 403 "E-mail non vérifié"│   ❌ → refus              │
```

### 5.3 Implémentation backend

```python
# services/auth_service.py — modifications

import secrets
from datetime import datetime, timedelta

TOKEN_EXPIRY_HOURS = 48

def generate_verification_token() -> tuple[str, datetime]:
    """Génère un token de vérification et sa date d'expiration."""
    token = secrets.token_urlsafe(32)  # 43 caractères URL-safe
    expires_at = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRY_HOURS)
    return token, expires_at
```

```python
# routes/auth.py — route register modifiée

@app.post("/auth/register", status_code=201)
@limiter.limit("3/hour")
async def register(request: Request, data: RegisterSchema, db: Session = Depends(get_db)):
    # ... validation existante (email unique, password hash) ...

    token, expires_at = generate_verification_token()

    user = User(
        email=data.email,
        nom=data.nom,
        password_hash=hash_password(data.password),
        is_verified=False,
        verification_token=token,
        verification_token_expires_at=expires_at,
    )
    db.add(user)
    db.commit()

    # Envoi e-mail via Brevo
    await send_verification_email(user.email, user.nom, token)

    return {
        "message": "Compte créé. Vérifiez votre boîte mail pour activer votre compte.",
        "email": user.email,
    }
```

```python
# routes/auth.py — nouvelle route de vérification

@app.get("/auth/verify-email")
async def verify_email(token: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.verification_token == token
    ).first()

    if not user:
        raise HTTPException(404, "Lien de vérification invalide.")

    if user.verification_token_expires_at < datetime.utcnow():
        raise HTTPException(410, "Lien expiré. Demandez un nouveau lien.")

    if user.is_verified:
        raise HTTPException(400, "Ce compte est déjà vérifié.")

    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires_at = None
    db.commit()

    # Option A : Rediriger vers la page de connexion PWA
    return RedirectResponse(
        url=f"{FRONTEND_URL}/login?verified=true",
        status_code=302,
    )
    # Option B : Réponse JSON si on veut un écran intermédiaire
    # return {"message": "Compte activé avec succès. Vous pouvez vous connecter."}
```

```python
# routes/auth.py — login modifié (ajout du garde is_verified)

@app.post("/auth/login")
@limiter.limit("10/minute")
async def login(request: Request, data: LoginSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "E-mail ou mot de passe incorrect.")

    if not user.is_verified:
        raise HTTPException(
            403,
            "Votre e-mail n'a pas été vérifié. "
            "Consultez votre boîte mail ou demandez un nouveau lien."
        )

    # ... génération JWT existante ...
```

```python
# routes/auth.py — renvoi du lien de vérification

@app.post("/auth/resend-verification")
@limiter.limit("2/hour")
async def resend_verification(
    request: Request, data: EmailSchema, db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == data.email).first()

    if not user or user.is_verified:
        # Réponse identique pour ne pas révéler l'existence d'un compte
        return {"message": "Si ce compte existe, un e-mail a été envoyé."}

    token, expires_at = generate_verification_token()
    user.verification_token = token
    user.verification_token_expires_at = expires_at
    db.commit()

    await send_verification_email(user.email, user.nom, token)

    return {"message": "Si ce compte existe, un e-mail a été envoyé."}
```

### 5.4 Envoi e-mail via Brevo

```python
# services/email_service.py

import httpx
import os

BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "noreply@eremy.fr")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Assistant Potager")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://potager.eremy.fr")

async def send_verification_email(to_email: str, to_name: str, token: str):
    """Envoie l'e-mail de vérification via l'API Brevo v3."""
    verification_url = f"{FRONTEND_URL}/auth/verify-email?token={token}"

    payload = {
        "sender": {
            "name": BREVO_SENDER_NAME,
            "email": BREVO_SENDER_EMAIL,
        },
        "to": [{"email": to_email, "name": to_name}],
        "subject": "Activez votre compte Assistant Potager 🌱",
        "htmlContent": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2 style="color: #2d5016;">Bienvenue sur Assistant Potager !</h2>
                <p>Bonjour {to_name},</p>
                <p>Cliquez sur le bouton ci-dessous pour activer votre compte :</p>
                <a href="{verification_url}"
                   style="display: inline-block; padding: 12px 24px;
                          background-color: #1D9E75; color: white;
                          text-decoration: none; border-radius: 6px;
                          font-weight: bold;">
                    Activer mon compte
                </a>
                <p style="margin-top: 24px; font-size: 0.85em; color: #666;">
                    Ce lien expire dans 48 heures.<br>
                    Si vous n'avez pas créé de compte, ignorez cet e-mail.
                </p>
            </div>
        """,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            json=payload,
            headers={
                "api-key": BREVO_API_KEY,
                "Content-Type": "application/json",
            },
        )
        if response.status_code not in (200, 201):
            # Log l'erreur mais ne bloque pas l'inscription
            import logging
            logging.error(f"Brevo send failed: {response.status_code} {response.text}")
```

### 5.5 Adaptation frontend (PWA)

```javascript
// frontend/src/lib/api.js — ajouts

export const api = {
    // ... existant ...

    // Auth — nouvelles routes
    register:     (data) => post('/auth/register', data),
    resendVerify: (data) => post('/auth/resend-verification', data),
}

// Ajout de la méthode POST
async function post(path, body) {
    const res = await fetch(`${BASE}${path}`, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `Erreur API ${res.status}`)
    }
    return res.json()
}
```

```
Écran d'inscription (après soumission) :

┌─────────────────────────────────┐
│                                 │
│  📩 Vérifiez votre boîte mail  │
│                                 │
│  Un e-mail d'activation a été  │
│  envoyé à example@mail.com     │
│                                 │
│  [Renvoyer le lien]            │
│                                 │
│  Le lien expire dans 48h.      │
│                                 │
└─────────────────────────────────┘
```

### Effort total mesure 3 : ~3–4 heures · Dépendance : httpx (ou sib-api-v3-sdk)

---

## 6. Mesure bonus — Honeypot anti-bot (optionnel, sans dépendance)

Un CAPTCHA (reCAPTCHA, Turnstile) ajoute une dépendance externe et dégrade l'UX. Un honeypot est invisible pour les humains et piège 80–90% des bots basiques.

### Principe

Ajouter un champ caché dans le formulaire d'inscription. Un humain ne le remplit jamais (il ne le voit pas). Un bot qui parse le HTML et remplit tous les champs le remplira.

```python
# routes/auth.py — dans le schéma d'inscription

class RegisterSchema(BaseModel):
    email: str
    password: str
    nom: str
    website: str = ""  # Champ honeypot — ne doit JAMAIS être rempli

@app.post("/auth/register")
async def register(request: Request, data: RegisterSchema, ...):
    # Piège honeypot
    if data.website:
        # Log silencieux + réponse factice (ne pas révéler la détection)
        logger.warning(f"Honeypot triggered from {get_real_ip(request)}")
        return {"message": "Compte créé. Vérifiez votre boîte mail."}

    # ... inscription réelle ...
```

```html
<!-- Frontend — champ caché via CSS, pas via type="hidden" -->
<!-- Les bots modernes ignorent type="hidden" mais pas le CSS -->
<div style="position: absolute; left: -9999px;" aria-hidden="true">
  <label for="website">Ne pas remplir</label>
  <input type="text" name="website" id="website" tabindex="-1" autocomplete="off" />
</div>
```

### Effort : ~15 minutes · Zéro dépendance

---

## 7. Récapitulatif et plan d'exécution

### Priorisation

| # | Mesure | Effort | Impact | Dépendances |
|---|--------|--------|--------|-------------|
| 1 | Swagger désactivé en prod | 5 min | 🟡 Anti-reconnaissance | Aucune |
| 2a | Rate limit Nginx | 20 min | 🔴 Anti brute-force L1 | Config Nginx |
| 2b | Rate limit slowapi | 1h | 🔴 Anti brute-force L2 | `slowapi` |
| 3 | Honeypot anti-bot | 15 min | 🟡 Anti-bot basique | Aucune |
| 4 | Vérification e-mail Brevo | 3–4h | 🔴 Anti-pollution | `httpx`, migration SQL |

### Découpage en User Stories

Ces mesures s'intègrent naturellement dans le backlog existant :

| US existante | Mesures absorbées |
|-------------|-------------------|
| **US-110** (Auth web) — enrichissement | Mesures 1 (Swagger), 2b (slowapi), 3 (honeypot) |
| **Nouvelle US-110b** — Vérification e-mail | Mesure 4 complète |
| **Config Nginx** (hors US, tâche ops) | Mesure 2a |

### Variables d'environnement à ajouter

```bash
# .env.prod — ajouts
APP_ENV=prod                              # Mesure 1
BREVO_API_KEY=xkeysib-...                 # Mesure 4
BREVO_SENDER_EMAIL=noreply@eremy.fr       # Mesure 4
BREVO_SENDER_NAME=Assistant Potager       # Mesure 4
FRONTEND_URL=https://potager.eremy.fr     # Mesure 4
```

### Dépendances Python à ajouter

```
# requirements.txt — ajouts
slowapi>=0.1.9
httpx>=0.27.0     # Si pas déjà présent (utilisé pour Brevo)
```

---

## 8. Ce qui est hors périmètre (et pourquoi)

| Mesure | Raison de l'exclusion |
|--------|----------------------|
| reCAPTCHA / Cloudflare Turnstile | Dépendance externe, dégrade l'UX mobile, le honeypot suffit pour la volumétrie actuelle |
| OAuth Google / Facebook | Déjà dans le backlog comme évolution post-US-110, pas un sujet de sécurisation |
| WAF (Web Application Firewall) | Surdimensionné pour un VPS STARDUST1-S mono-application |
| Fail2ban | Pertinent à terme mais le rate limiting Nginx couvre 95% du besoin |
| IP blacklisting | Inefficace contre les bots distribués, maintenance manuelle |

---

## 9. Métriques de succès

Après déploiement, mesurer sur 30 jours :

| Métrique | Avant | Cible |
|----------|-------|-------|
| Comptes créés non vérifiés | N/A | < 5% des inscriptions |
| Requêtes 429 (rate limited) | 0 | > 0 confirme que la protection fonctionne |
| Comptes fantômes dans `users` | À auditer | 0 (nettoyage auto 48h) |
| Temps de réponse `/auth/register` | baseline | +50ms max (envoi e-mail async) |

---

## 10. Cohérence avec le backlog existant

| Référence backlog | Lien |
|-------------------|------|
| US-110 — Auth web | Rate-limit basique mentionné dans le périmètre → cette conception le détaille |
| US-123 — Quotas tokens & rate-limiting par tenant | Concerne le rate limiting **métier** (tokens LLM), pas l'auth — complémentaire |
| US-125 — Alembic + CI/CD | La migration de vérification e-mail sera la première migration Alembic si US-125 est livrée avant |
| US-004 — Environnements dev/prod | `APP_ENV` conditionne déjà Swagger — cohérent |

---

> **Marqueurs de statut :**
> - ✅ Fait établi — architecture et stack confirmées
> - ⚖️ Arbitrage — honeypot vs CAPTCHA, slowapi vs middleware custom
> - 🔶 Hypothèse — le honeypot couvre 80–90% des bots (à mesurer)
> - 🧪 À tester — charge réelle du rate limiting Nginx sur STARDUST1-S
