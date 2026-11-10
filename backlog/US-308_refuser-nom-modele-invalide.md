**ID :** US-308
**Titre :** Refuser un nom de modèle invalide au démarrage
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux qu'une valeur de modèle mal écrite dans `.env` soit refusée au démarrage
Afin qu'une faute de configuration ne devienne pas une panne silencieuse ni une ligne illisible dans la mesure

**Contexte fonctionnel :**
Le 10/11/2026, cinq appels `voix` ont échoué avec le modèle journalisé `mistral/voxtral-mini-tts-3-0            (voix : texte → MP3)` : un commentaire en fin de ligne dans `.env` a été lu comme partie de la valeur. La panne n'a été vue qu'à l'usage, et la ventilation par modèle compte désormais un modèle qui n'existe pas.

**Critères d'acceptance :**
- [ ] CA1 : Chaque variable de modèle par type d'appel (`GROQ_MODEL`, `GROQ_MODEL_<TYPE>`, `GROQ_WHISPER_MODEL` et les variables de dictée et de voix) est validée au chargement de `app/config.py` : pas d'espace, pas de parenthèse, pas de `#`, longueur bornée, préfixe de fournisseur connu ou absent.
- [ ] CA2 : Une valeur invalide arrête le démarrage du bot et de l'API avec un message qui nomme la variable et montre la valeur lue.
- [ ] CA3 : `.env.example` porte les commentaires sur une ligne à part, jamais en fin de ligne de valeur, et le dit.
- [ ] CA4 : Le contrôle de configuration existant (liste de `app/config.py` qui vérifie les variables attendues) couvre ces variables.
- [ ] CA5 : Un test fournit `modele            (commentaire)` et vérifie le refus ; un test fournit chaque valeur par défaut du dépôt et vérifie l'acceptation.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (configuration, passerelle LLM)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : aucune
- Les cinq lignes fautives de l'extraction restent en base ; elles sont en provenance `historique` après US-306.
- `docs/CONFIGURATION/SETUP.md` est mis à jour.

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given .env.dev contient "VOIX_MODELE=mistral/voxtral-mini-tts-3-0   (voix : texte → MP3)"
When je lance python -m app.bot
Then le démarrage s'arrête
And le message nomme VOIX_MODELE et affiche la valeur lue entre guillemets
```

**Labels GitHub :** `us`, `llm`, `configuration`
