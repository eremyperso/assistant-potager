**ID :** US-299
**Titre :** Transcrire et synthétiser par Voxtral dans la passerelle
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier qui utilisera la voix dans la PWA
Je veux que la transcription de ma voix et la voix de mon compagnon passent par le même chemin mesuré que le reste de l'IA
Afin que le vocal soit fiable, que son coût soit visible et qu'une panne de Mistral ne bloque jamais le texte

**Contexte fonctionnel :**
Socle sans écran des US suivantes (étude §5.2). La synthèse vocale de Mistral n'est pas au format OpenAI : elle demande un appel dédié, mais garde la mesure, le journal et l'indisponibilité typée de la passerelle. Le bot Telegram n'est pas touché (D7).

**Critères d'acceptance :**
- [ ] CA1 : Un nouveau type d'appel `dictee` (variable `GROQ_MODEL_DICTEE`, défaut `mistral/voxtral-mini-transcribe-3-0` ou l'identifiant relevé par US-298) transcrit un fichier audio en texte, en français.
- [ ] CA2 : Un nouveau type d'appel `voix` (variable `GROQ_MODEL_VOIX`, défaut `mistral/voxtral-mini-tts-3-0`) rend un MP3 à partir d'un texte et d'un identifiant de voix ; une voix inconnue de Mistral (404 `invalid_voice`) rend une erreur typée distincte d'une indisponibilité.
- [ ] CA3 : Chaque appel `dictee` et `voix` est journalisé et compté dans `conso_tokens` avec son type, son modèle, sa latence et son issue ; la dictée porte la durée d'audio, la synthèse le nombre de caractères envoyés.
- [ ] CA4 : Sans `MISTRAL_API_KEY`, en délai dépassé ou en erreur 5xx, l'appel rend l'indisponibilité typée de la passerelle, jamais une exception brute ; la PWA pourra dire « la voix est indisponible, écrivez votre message ».
- [ ] CA5 : Un service `app/services/voix/` porte la dictée et la synthèse ; il est le seul point d'entrée des routes à venir. Le nettoyage du texte (Markdown, émojis, liens) de `utils/tts.py` y est repris sans modifier `utils/tts.py`.
- [ ] CA6 : Si US-298 a constaté un format refusé, le service le convertit par FFmpeg avant envoi ; sans FFmpeg, l'erreur est typée et dit quel format manque. La présence de FFmpeg sur les serveurs dev et prod est vérifiée et notée au runbook.
- [ ] CA7 : L'audio reçu n'est jamais écrit en base ; un fichier temporaire éventuel est supprimé après l'appel, y compris en cas d'erreur.
- [ ] CA8 : Le type `transcription` (Telegram, Groq Whisper) et `utils/tts.py` (gTTS) sont inchangés : un test le vérifie.
- [ ] CA9 : `.env.example` documente `GROQ_MODEL_DICTEE` et `GROQ_MODEL_VOIX` en commentaire ; l'affichage de la configuration au démarrage les liste.
- [ ] CA10 : Le registre RGPD décrit le traitement : audio dicté envoyé à Mistral AI puis jeté, hébergement européen de l'audio non confirmé (étude §7).

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : socle IA (passerelle)
- Migration BDD requise : non (sauf si le type d'appel de `conso_tokens` est une liste fermée en base : ajout de `dictee` et `voix`)
- Dépendances : US-298 (identifiants, formats)
- Décisions liées : D7, C2, C3, C5, C7
- Fiche du corpus : aucune (pas de comportement visible)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given GROQ_MODEL_VOIX vaut "mistral/voxtral-mini-tts-3-0"
When le service synthétise "Bonjour, je suis Gaston" avec la voix "voice_592"
Then il rend un MP3 non vide
And une ligne conso_tokens de type "voix" porte 23 caractères et l'issue "ok"
Given MISTRAL_API_KEY est vide
When le service tente une dictée
Then il rend l'indisponibilité typée de la passerelle
And la transcription Telegram par Groq Whisper fonctionne toujours
```

**Labels GitHub :** `us`, `voix`, `passerelle-llm`, `compagnon`
