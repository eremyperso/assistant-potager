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