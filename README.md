# Assistant Potager 🌿

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green.svg)](https://fastapi.tiangolo.com/)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-blue.svg)](https://core.telegram.org/bots)
[![Groq](https://img.shields.io/badge/Groq-LLM-orange.svg)](https://groq.com/)

Un assistant intelligent pour jardiniers amateurs, combinant un bot Telegram, une API web FastAPI et une interface PWA. Suivez vos plantations, pertes, récoltes et recevez des conseils météorologiques personnalisés grâce à l'IA Groq.

## ✨ Fonctionnalités

- **Bot Telegram** : Commandes vocales et textuelles pour enregistrer vos actions de jardinage
- **Transcription vocale** : Utilise Groq Whisper pour convertir la voix en texte
- **Analyse IA** : Parsing intelligent des commandes avec Llama 3.3
- **Base de données** : Stockage PostgreSQL des événements de jardinage
- **Statistiques** : Calcul automatique du stock réel (plantations - pertes - récoltes)
- **Questions analytiques** : Posez des questions sur votre historique via /ask
- **Météo intégrée** : Conseils basés sur les prévisions Open-Meteo
- **Synthèse vocale** : Réponses audio avec gTTS
- **Interface PWA** : Application web progressive pour consultation mobile
- **API REST** : Endpoints pour intégration tierce

## 🚀 Installation

### Prérequis

- Python 3.8+
- PostgreSQL
- FFmpeg (pour la conversion audio)
- Clés API : Groq et Telegram Bot Token

### Étapes d'installation

1. **Clonez le repository**
   ```bash
   git clone https://github.com/votre-username/assistant-potager.git
   cd assistant-potager
   ```

2. **Installez les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configurez la base de données**
   - Créez une base PostgreSQL nommée `potager`
   - Exécutez les migrations :
     ```bash
     psql -d potager -f migrations/migration_v4.sql
     ```

4. **Configurez les variables d'environnement**
   - Copiez `config.py.example` vers `config.py`
   - Éditez `config.py` avec vos clés API :
     ```python
     GROQ_API_KEY = "votre-cle-groq"
     TELEGRAM_BOT_TOKEN = "votre-token-telegram"
     DATABASE_URL = "postgresql://user:password@localhost/potager"
     ```

5. **Installez FFmpeg** (requis pour les voice notes Telegram)
   - Windows : `winget install ffmpeg`
   - Linux : `sudo apt install ffmpeg`
   - macOS : `brew install ffmpeg`

## ⚙️ Configuration

Le fichier `config.py` contient toutes les configurations nécessaires :

- `GROQ_API_KEY` : Clé API Groq (gratuite)
- `TELEGRAM_BOT_TOKEN` : Token du bot Telegram
- `DATABASE_URL` : URL de connexion PostgreSQL
- `GROQ_MODEL` : Modèle LLM (défaut: llama-3.3-70b-versatile)
- `GROQ_WHISPER_MODEL` : Modèle Whisper (défaut: whisper-large-v3-turbo)

## 📱 Utilisation

### Bot Telegram

1. **Démarrez le bot**
   ```bash
   python bot.py
   ```

2. **Commandes disponibles**
   - **Messages vocaux/textes** : Enregistrez vos actions (ex: "J'ai planté 10 tomates")
   - `/ask <question>` : Questions analytiques (ex: "/ask Combien de plants de tomates me restent-il ?")
   - `/stats` : Statistiques rapides du jardin
   - `/historique [filtre]` : Derniers événements (optionnel: plante, action, date)
   - `/tts` : État de la synthèse vocale
   - `/tts_on` / `/tts_off` : Activer/désactiver les réponses vocales

### API Web

1. **Démarrez le serveur**
   ```bash
   python main.py
   ```
   L'API sera accessible sur http://localhost:8000

2. **Endpoints principaux**
   - `GET /health` : Vérification de l'état de l'API
   - `POST /parse` : Parser une commande vocale
   - `POST /ask` : Poser une question analytique
   - `GET /stats` : Statistiques JSON
   - `GET /historique` : Historique des événements
   - `GET /` : Interface PWA

### Interface Web (PWA)

Accédez à http://localhost:8000 pour utiliser l'interface web progressive.

## 🧪 Tests

Lancez les tests avec pytest :
```bash
pytest tests/
```

## 📊 Base de données

Le schéma inclut une table `evenements` avec :
- `id` : Identifiant unique
- `date` : Date de l'événement
- `plante` : Nom de la plante/culture
- `action` : Type d'action (plantation, perte, récolte, etc.)
- `quantite` : Quantité concernée
- `details` : Informations supplémentaires

## 📋 User Stories

État d'implémentation des User Stories du projet, reconstitué à partir de `PATCH_NOTES.md`, de l'historique Git et de `docs/BACKLOG_US_MULTITENANT.md`.

### US numérotées classiques

| US | Fonctionnalité | Implémenté | Version |
|---|---|---|---|
| US-004 | Séparation environnements dev/prod (`.env`) | ✅ Oui | v2.3.0 |
| US-005 | Déploiement automatisé Scaleway | ✅ Oui | v2.4.0 |
| US-006 | Renommer une parcelle (propagation historique) | ✅ Oui | v2.14.0 |
| US-007 | Réassocier/déplacer une culture vers une autre parcelle | ✅ Oui | v2.25.0 |
| US-008 | Commande `/version` | ✅ Oui | v2.15.0 |
| US-009 | Supprimer une parcelle (soft-delete) | ✅ Oui | v2.23.0 |
| US-010 | Classification intent (question vs action) | ✅ Oui | v2.16.0 (fix v2.19.0) |
| US-011 | Validation post-parsing / anti-hallucination | ✅ Oui | v2.17.0 (fixes v2.19.0, v3.14.0) |
| US-012 | Agent SQL pour questions analytiques | ✅ Oui | v2.17.0 |
| US-014 | `/stats [culture]` — semis visibles par culture | ✅ Oui | v2.18.0 / v2.19.0 |
| US-016 | Sémantique mise en godet (graines vs plants) | ✅ Oui | v2.20.0 |
| US-017 | Stock résiduel de semis par variété | ✅ Oui | v2.20.0 |
| US-018 | Section Pépinière dans `/stats <culture>` | ✅ Oui | v2.20.0 |
| US-019 | Sélection assistée de variété (mise en godet) | ✅ Oui | v2.21.0 |
| US-021 | Confirmation avant enregistrement (✅/❌) | ✅ Oui | v2.22.0 (+ v2.24.0, v3.7.2) |
| US-022 | Déduction stock godet lors de plantation | ✅ Oui | v2.27.0 |
| US-023 | Dashboard frontend React/Vite (socle) | ✅ Oui | v3.0.0 |
| US-024 | Vue Plan (dashboard) | ✅ Oui | v3.1.0 |
| US-025 | Vue Stocks cultures (dashboard) | ✅ Oui | v3.2.0 |
| US-026 | Vue Pépinière (dashboard) | ✅ Oui | v3.4.0 |
| US-027 | Vue Historique (dashboard) | ✅ Oui | v3.3.0 |
| US-029 | Chaînage semis → godet → plantation | ✅ Oui | v3.5.0 / v3.6.0 |
| US-030 | Paramètre `date_ref` sur les endpoints | ✅ Oui | v3.7.0 |
| US-031 | Sélecteur de date de référence global (PWA) | ✅ Oui | v3.8.0 |
| US-036 | Rendement en poids (cultures végétatives) | ✅ Oui | v3.11.0 |
| US-037 | Semis en m² / statut pépinière sur parcelle | ✅ Oui | v3.12.0 / v3.13.0 |
| US-038 | Commande `/note` — observations guidées | ✅ Oui | v3.14.0 |
| US-039 | Affichage des notes dans le dashboard | ✅ Oui | v3.14.0 |
| US-049 | Validation centrale non contournable | ✅ Oui | v3.18.1 |

### US nommées (sans numéro, `US_xxx`)

| US | Fonctionnalité | Implémenté | Version |
|---|---|---|---|
| US_Commande_help_aide_mobile | Commande `/help` | ✅ Oui | v2.9.0 |
| US_Enregistrer_mise_en_godet | Enregistrement mise en godet + taux germination | ✅ Oui | v2.10.0 |
| US_Stats_detail_par_variete | `/stats [culture]` détail par variété | ✅ Oui | v2.11.0 |
| US_Plan_occupation_parcelles | `/plan`, `/parcelle ajouter/modifier/lister` | ✅ Oui | v2.12.0 / v2.13.0 |
| US_Aide_contextuelle_par_commande | `/help <mot-clé>` | ✅ Oui | v2.13.0 |
| US_Afficher_synthese_semis_dans_stats | Synthèse semis dans `/stats` | ✅ Oui | v2.8.0 |

### Épic Multi-tenant (`docs/BACKLOG_US_MULTITENANT.md`)

> ⚠️ Le backlog planifie la numérotation **US-100 à US-133**, mais l'implémentation réelle a suivi une numérotation différente (**US-040 à US-049**) pour les mêmes chantiers.

| US backlog | US réellement livrée | Fonctionnalité | Implémenté | Version |
|---|---|---|---|---|
| US-100 | US-040 | Socle multi-tenant (`users`/`potagers`/`potager_membres`) | ✅ Oui | v3.15.0 |
| US-101 | US-041 | Couche `services/` partagée bot ⇄ PWA | ✅ Oui | v3.16.0 |
| US-102 | US-042 | Scoping systématique par `potager_id` | ✅ Oui | v3.17.0 |
| US-103 | US-043 | Row-Level Security PostgreSQL | ✅ Oui | v3.18.0 |
| US-110 | US-044 | Authentification web JWT | ✅ Oui | v3.19.0 |
| US-111 | US-045 | Liaison Telegram ⇄ compte web | ✅ Oui | v3.20.0 |
| US-112 | US-046 | Sélection du potager actif | ✅ Oui | v3.21.0 |
| US-113 | — | Rôles & permissions (owner/editor/lecteur) | ❌ Non | — |
| US-114 | — | Invitations & onboarding self-service | ❌ Non | — |
| US-120 | — | État conversationnel persistant (Redis) | ❌ Non | — |
| US-121 | — | LLM à étages + parsing déterministe + cache | ❌ Non | — |
| US-122 | — | RAG scopé et pré-agrégé pour `/ask` | ❌ Non | — |
| US-123 | — | Quotas tokens & rate-limiting par tenant | ❌ Non | — |
| US-124 | — | Jobs de fond par potager (météo, sauvegardes) | ❌ Non | — |
| US-125 | — | Migrations Alembic + CI/CD | ❌ Non | — |
| US-130 | — | PostgreSQL managé + sauvegardes auto | ❌ Non | — |
| US-131 | — | Observabilité (Sentry, métriques) | ❌ Non | — |
| US-132 | — | RGPD & conformité | ❌ Non | — |
| US-133 | — | Facturation Stripe (freemium) | ❌ Non | — |

## 🤝 Contribution

Les contributions sont les bienvenues ! 

1. Forkez le projet
2. Créez une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Commitez vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Pushez vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une Pull Request

### Structure du projet
- `bot.py` : Bot Telegram principal
- `main.py` : API FastAPI
- `database/` : Modèles et connexion DB
- `llm/` : Client Groq et prompts
- `utils/` : Utilitaires (actions, dates, météo, TTS)
- `static/` : Fichiers PWA
- `tests/` : Tests unitaires
- `migrations/` : Scripts SQL de migration

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙏 Remerciements

- [Groq](https://groq.com/) pour l'API LLM gratuite et rapide
- [Open-Meteo](https://open-meteo.com/) pour les données météo gratuites
- [FastAPI](https://fastapi.tiangolo.com/) pour le framework web
- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) pour le bot Telegram

---

*Fait avec ❤️ pour les jardiniers passionnés*</content>
<parameter name="filePath">c:\Users\eremy\Documents\GitHub\assistant-potager\README.md