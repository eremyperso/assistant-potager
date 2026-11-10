**ID :** US-302
**Titre :** Dicter une phrase au compagnon depuis la PWA
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier au potager, les mains occupées ou pleines de terre
Je veux appuyer sur le micro, parler, appuyer de nouveau, et que ma phrase parte à Gaston
Afin de tenir mon carnet et de poser mes questions sans taper

**Contexte fonctionnel :**
Mode « appuyer pour parler » (D3) : un appui démarre l'enregistrement, un second l'arrête, le fichier est transcrit par Voxtral (US-299) puis **envoyé automatiquement** (D4) par le chemin habituel `/compagnon/messages`. Les écritures restent soumises à la carte de confirmation (US-274) : la dictée ne crée jamais de geste sans confirmation.

**Critères d'acceptance :**
- [ ] CA1 : Mode vocal actif (US-301), un bouton 🎤 apparaît à côté de « Envoyer » dans le panneau du compagnon, en vue réduite comme en plein écran ; mode vocal éteint, il n'apparaît pas.
- [ ] CA2 : Au premier appui, le navigateur demande l'accès au micro ; accordé, l'enregistrement démarre et le bouton passe à l'état « écoute » avec la durée écoulée ; un second appui l'arrête.
- [ ] CA3 : L'enregistrement s'arrête seul à `VOIX_DICTEE_DUREE_MAX_S` (60 s par défaut), avec la mention « Durée maximale atteinte », et part en transcription.
- [ ] CA4 : Pendant la transcription, le bouton est en état « transcription » et ne peut pas relancer d'enregistrement ; le micro est libéré dès l'arrêt (le voyant d'enregistrement du système s'éteint).
- [ ] CA5 : `POST /compagnon/voix/transcrire` reçoit le fichier (multipart) et rend `{ texte }` ; il refuse un fichier trop long ou trop lourd (413) et un compte sans mode vocal (403).
- [ ] CA6 : La phrase transcrite apparaît comme une bulle du jardinier marquée 🎤 et part aussitôt à Gaston, comme une phrase tapée (même mode normal, support ou analyse).
- [ ] CA7 : Une transcription vide dit « Je n'ai rien entendu, réessayez » sans rien envoyer ; une transcription de plus de 1 000 caractères est refusée avec « Message trop long, découpez-le ».
- [ ] CA8 : Un micro refusé dit comment le réautoriser (réglages du navigateur) ; un micro absent, une page hors HTTPS ou un navigateur sans `MediaRecorder` remplace le bouton par une explication courte ; la saisie au clavier reste toujours disponible.
- [ ] CA9 : Voxtral indisponible : « La dictée est indisponible pour le moment, écrivez votre message » ; rien n'est perdu de la saisie en cours.
- [ ] CA10 : Si une réponse est en cours de lecture (US-304), elle s'arrête dès l'appui sur 🎤 : le micro ne s'ouvre jamais pendant une lecture.
- [ ] CA11 : Le format d'enregistrement est choisi selon le navigateur (`audio/webm;codecs=opus`, sinon `audio/mp4`, sinon `audio/ogg`) ; la dictée fonctionne sur Chrome, Edge et Firefox (PC), Safari (Mac), Safari et PWA installée (iPad, iPhone), Chrome et PWA installée (Android). Le choix du format, la durée maximale et les états du bouton vivent dans une logique pure testée par `node --test`.
- [ ] CA12 : Le plafond `VOIX_PLAFOND_DICTEES_JOUR` atteint, la dictée dit « Limite de dictées du jour atteinte » (429) ; le clavier reste disponible.
- [ ] CA13 : Le rendu correspond à la maquette de référence à 375 px, 768 px et sur ordinateur ; le bouton est utilisable au pouce (zone tactile d'au moins 44 px).
- [ ] CA14 : Le guide utilisateur (ses deux copies) et la fiche du corpus du compagnon vocal décrivent la dictée et ses limites ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction (PWA), enregistrement par la voix
- Migration BDD requise : non
- Dépendances : US-299, US-300, US-301 ; maquette Claude Design
- Décisions liées : D3, D4, C1, C2, C4
- Fiche du corpus : `compagnon-vocal-pwa.md` (créée par US-301)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le mode vocal est actif sur l'iPhone du jardinier, PWA installée
When il appuie sur 🎤 et dit "j'ai semé 30 graines de radis sur la planche 2"
And appuie de nouveau sur 🎤
Then une bulle "🎤 j'ai semé 30 graines de radis sur la planche 2" apparaît
And Gaston répond par une carte de proposition à confirmer
And aucun semis n'est enregistré avant la confirmation
Given le jardinier a refusé l'accès au micro
When il appuie sur 🎤
Then la PWA lui explique comment réautoriser le micro
And il peut toujours taper son message
```

**Labels GitHub :** `us`, `voix`, `pwa`, `compagnon`, `enregistrement`
