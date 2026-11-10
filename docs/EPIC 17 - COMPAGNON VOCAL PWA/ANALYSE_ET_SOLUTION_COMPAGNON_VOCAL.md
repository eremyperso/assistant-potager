# Compagnon vocal dans la PWA — analyse et solution

*Étude du 09/11/2026, branche `feature/compagnon-synthese-vocale`. Épic proposé : ÉPIC 17 (numéro à valider).*

## 1. Le besoin

> En tant qu'utilisateur de la PWA, je veux parler à mon compagnon et écouter ses réponses
> au haut-parleur, sur PC, tablette et mobile.

Exigences exprimées :

| # | Exigence | Origine |
|---|---|---|
| E1 | Dicter une phrase au compagnon (transcription audio → texte) | besoin |
| E2 | Écouter la réponse du compagnon au haut-parleur | besoin |
| E3 | Synthèse par Mistral, modèle Voxtral | besoin |
| E4 | Choisir la voix | besoin |
| E5 | Ton (émotion) et rythme par les balises de Voxtral | « l'idéal » |
| E6 | Fonctionner sur PC, tablette et mobile | besoin |
| E7 | Être averti des contraintes avant tout choix | méthode |

## 2. L'existant

### 2.1 Côté bot Telegram

| Élément | Où | Constat |
|---|---|---|
| Synthèse vocale | `utils/tts.py` | gTTS (voix Google Traduction, service non officiel), MP3 → OGG/Opus par FFmpeg, coupe à 400 caractères |
| Interrupteur | `/tts`, `/tts_on`, `/tts_off` | **global** : un fichier `utils/.tts_state.json` pour toute l'instance, tous potagers confondus |
| Transcription | `llm.passerelle.transcrire()` | Groq Whisper (`GROQ_MODEL_TRANSCRIPTION`), mesure et mode dégradé de la passerelle |
| Couplage | `send_voice_reply(update, …)` | dépend de l'objet `Update` de Telegram : inutilisable depuis l'API |

Décision D7 : **le bot reste tel quel** (gTTS, Whisper, interrupteur global). Rien de cette étude ne le modifie.

### 2.2 Côté PWA

| Élément | Où | Constat |
|---|---|---|
| Panneau du compagnon | `frontend/src/components/PanneauCompagnon.jsx` | saisie texte, cartes de proposition, modes normal / support / analyse |
| Logique pure | `frontend/src/lib/compagnon.js` (+ `compagnon.test.js`) | `peutEnvoyer`, `LONGUEUR_MAX = 1000`, fil d'échanges |
| Réglages | `frontend/src/components/ModalMonCompagnon.jsx` | « Mon compagnon » : niveau, objectifs, carnet |
| API | `app/api/main.py` (`/compagnon/messages`, `/historique`, `/etat`…) | aucune logique, tout dans `app/services/compagnon/echange_pwa.py` → orchestrateur commun au bot |
| Échanges | table `echanges_conversation` | `texte_jardinier`, `texte_compagnon`, `signal`, `proposition_id`, `question`, `outils` |
| Vocal | — | **rien** : ni micro, ni lecture. L'ancienne route `/voice` a été retirée par US-274 (elle écrivait sans confirmation) |

La passerelle sait déjà servir un modèle Mistral : un modèle préfixé `mistral/` dans
`GROQ_MODEL_<TYPE>` passe par `MISTRAL_API_KEY` (compatible OpenAI pour le chat et la
transcription). La synthèse vocale de Mistral, elle, **n'est pas** au format OpenAI
(réponse JSON avec l'audio en base64, champ `voice_id`) : elle demande un appel dédié.

## 3. L'offre Mistral (documentation lue le 09/11/2026)

### 3.1 Synthèse vocale — Voxtral TTS 3

| Point | Valeur |
|---|---|
| Modèle | `voxtral-mini-tts-3-0` (« Voxtral TTS 3 », marqué *Premier*) ; `voxtral-mini-tts-realtime-3-0` pour le temps réel |
| Point d'appel | `POST https://api.mistral.ai/v1/audio/speech` |
| Champs | `model`, `input` (texte, balises comprises), `voice_id`, `response_format`, `expressiveness` (1,0 à 5,0), `stream`, `phoneme_hints`… Pas de champ vitesse : le rythme passe par balise |
| Sortie | `mp3` (défaut), `opus`, `wav`, `flac`, `pcm` ; mono 24 kHz ; JSON `audio_data` en base64, ou flux SSE `speech.audio.delta` si `stream: true` |
| Langues | 35 langues dont le français ; **la langue est portée par la voix**, pas par un paramètre |
| Voix françaises | **Marie `voice_592`, Manon `voice_3137`, Léa `voice_589`, Camille `voice_3141`** (Voxtral 3) ; anciennes `fr_marie_*` (Voxtral 2) encore acceptées |
| Liste des voix | API `voices.search` (filtres `type=preset`, `language=["fr"]`), extrait audio par `voices.get_sample_audio` |
| Clonage | possible (`ref_audio` ou voix enregistrée) — écarté, voir D2 |
| Prix | 13 $ par million de caractères (1,3 $ en cache) |
| Limite de longueur d'entrée | **non documentée** |
| Ancien modèle | `voxtral-mini-tts-2603` déprécié le 31/10/2026, retiré le 30/04/2027 |

Balises (page « Emotion and pace tags ») :

- syntaxe `[emotion=warm]`, `[pace=slow]`, combinables (une de chaque), valables jusqu'à la balise suivante ;
- 34 émotions : amused, angry, anxious, apologetic, appreciative, assertive, bored, calm, confident, confused, critical, curious, determined, disappointed, disgusted, excited, frustrated, grateful, happy, hopeful, playful, proud, reflective, resigned, sad, sarcastic, skeptical, somber, surprised, tense, tired, urgent, warm, wistful ;
- rythme : `very-slow`, `slow`, `moderate`, `fast`, `very-fast` (une autre page n'en cite que deux, `slow` et `fast` : à vérifier) ;
- hésitations : `[breath]`, `[sigh]`, `[chuckle]`, `[rire]`… ;
- **« Emotion, pace, and disfluency tags work in English »**, en français : « untested but expected to work » ;
- **l'API ne rejette pas une valeur inconnue** : une faute de frappe passe en silence.

### 3.2 Transcription — Voxtral Transcribe 3

| Point | Valeur |
|---|---|
| Modèles | `voxtral-mini-transcribe-3-0` (0,0035 $/min), `voxtral-small-transcribe-3-0` (0,004 $/min), `voxtral-mini-transcribe-realtime-3-0` (0,008 $/min) |
| Point d'appel | `POST https://api.mistral.ai/v1/audio/transcriptions` (multipart : `file`, `model`, `language=fr`) |
| Identifiant | la doc écrit tantôt `voxtral-mini-transcribe-3`, tantôt `…-3-0` : à vérifier |
| Formats d'entrée | **non documentés** (exemples en `.wav` et `.mp3` seulement) |
| Taille ou durée maximale | **non documentée** |
| Temps réel | WebSocket, audio `pcm_s16le` mono 16 kHz, en-tête `Authorization` |

### 3.3 Hébergement et données

Des points d'accès régionaux existent (`api.eu.mistral.ai`), mais la page ne cite **aucun
modèle audio** parmi ceux disponibles par région. L'hébergement européen de l'audio n'est
donc **pas confirmé**. La conservation des requêtes audio n'est pas décrite sur les pages lues.

## 4. Contraintes et décisions

Les contraintes ont été présentées au jardinier avant tout choix (E7) ; ses réponses
fixent les décisions ci-dessous.

| # | Contrainte | Décision |
|---|---|---|
| **D1** | Balises garanties en anglais seulement ; l'API accepte en silence une valeur fausse | **Essai en français d'abord** (US-298), puis balises **posées par des règles** selon la nature de la réponse (US-305). Le modèle de langage ne les pose pas en v1 |
| **D2** | Quatre voix françaises, toutes féminines ; clonage = donnée biométrique | **Liste des voix françaises lue sur l'API** (repli sur les quatre voix connues), avec extrait à écouter. Pas de clonage |
| **D3** | Temps réel : WebSocket avec clé en en-tête (impossible depuis un navigateur), PCM brut, relais serveur, prix × 2,3 | **Appuyer pour parler** : un appui démarre, un second arrête, le fichier part au serveur. Temps réel hors périmètre |
| **D4** | — | **Envoi automatique** de la phrase transcrite (mains libres). Les écritures restent soumises à la carte de confirmation (US-274) |
| **D5** | iOS bloque le son sans geste de l'utilisateur | **Lecture automatique après une dictée** (le tap sur le micro déverrouille le son), **bouton ▶ sur chaque réponse** ; réglage pour couper la lecture automatique |
| **D6** | Coût par caractère, longueur d'entrée non documentée, réponses parfois longues | **Résumé parlé court** (1 à 2 phrases), distinct du texte affiché |
| **D7** | — | **PWA seulement** : le bot Telegram n'est pas modifié |
| **D8** | — | **Pas d'outillage de test dédié** (ni Playwright, ni script de recette, ni matrice dédiée) : chaque US porte ses tests habituels (pytest, `node --test`) |

Contraintes sans décision à prendre, traitées dans la solution :

| # | Contrainte | Traitement |
|---|---|---|
| C1 | Le micro n'est accessible qu'en **contexte sécurisé** (HTTPS ou `localhost`) | prod et `dev.potager` sont en HTTPS ; un accès `http://192.168…` depuis un téléphone masque le micro avec une explication |
| C2 | Formats enregistrés : `audio/webm;codecs=opus` (Chrome, Edge, Firefox, Android), `audio/mp4` AAC (Safari macOS, iPadOS, iOS) ; formats acceptés par Mistral non documentés | l'essai US-298 tranche ; si un format est refusé, **conversion serveur par FFmpeg** vers un format accepté |
| C3 | FFmpeg n'est pas installé par les workflows de déploiement (aucune mention dans `.github/workflows/`) | à vérifier sur les serveurs dev et prod dès US-299 si la conversion est nécessaire |
| C4 | Un haut-parleur qui lit pendant que le micro écoute réenregistre la réponse | la lecture s'arrête dès qu'une dictée démarre ; le micro ne s'ouvre jamais pendant une lecture |
| C5 | Hébergement européen de l'audio non confirmé | inscrit au registre RGPD (US-299) ; l'audio n'est jamais conservé côté Assistant Potager |
| C6 | Modèles marqués *Premier* ; clé de la plateforme | coût porté par la plateforme, plafond quotidien par jardinier en configuration (US-304) |
| C7 | Identifiants de modèles incohérents dans la doc | tous les identifiants viennent de la configuration ; US-298 relève les bons |

## 5. Solution

### 5.1 Vue d'ensemble

```
PWA (PanneauCompagnon)                       API FastAPI                 app/services/voix/            Mistral
─────────────────────────                    ───────────                 ──────────────────            ───────
🎤 appui → MediaRecorder ── fichier audio ─▶ POST /compagnon/voix/       transcription.py ──passerelle.dicter()──▶ /v1/audio/transcriptions
   second appui                               transcrire                  (conversion FFmpeg si besoin)
                         ◀── { texte } ─────
envoi auto ───────────────── texte ───────▶ POST /compagnon/messages    (orchestrateur inchangé)
                         ◀── réponse + echange_id ─
lecture auto ou ▶ ─────────────────────────▶ POST /compagnon/voix/       oral.py   → résumé parlé (LLM, type « oral »)
                                              lecture/{echange_id}       balises.py → [emotion=…][pace=…] par règles
                         ◀── audio/mpeg ────                             synthese.py ──passerelle.synthetiser()──▶ /v1/audio/speech
<audio> joue le MP3
```

Règles du projet respectées : aucune logique dans les routes, aucun `db.query` hors
`app/services/`, tout appel de modèle par `llm.passerelle`, texte arbitraire jamais
synthétisé (la lecture se fait **par identifiant d'échange**, ce qui ferme la porte à une
synthèse vocale gratuite pour n'importe quel texte).

### 5.2 Passerelle (US-299)

Deux nouveaux types d'appel, configurables sans redéploiement comme les autres :

| Type | Variable | Défaut | Fonction |
|---|---|---|---|
| `dictee` | `GROQ_MODEL_DICTEE` | `mistral/voxtral-mini-transcribe-3-0` | `passerelle.dicter(ctx, contenu, nom_fichier, langue="fr")` |
| `voix` | `GROQ_MODEL_VOIX` | `mistral/voxtral-mini-tts-3-0` | `passerelle.synthetiser(ctx, texte, voix_id, format="mp3")` |
| `oral` | `GROQ_MODEL_ORAL` | modèle de `agent` | résumé parlé (US-303), appel de chat ordinaire |

`dictee` est distinct de `transcription` : changer la dictée de la PWA ne touche pas
Telegram (D7). `synthetiser` fait un appel HTTP dédié à `/v1/audio/speech` (format non
OpenAI) mais garde la mesure (`conso_tokens` : caractères envoyés, secondes d'audio,
latence, issue), le journal et l'indisponibilité typée de la passerelle.

### 5.3 Données (US-300, US-303)

| Migration | Contenu |
|---|---|
| v71 (US-300) | table `preferences_voix` : `user_id` (clé), `mode_vocal` (booléen, faux par défaut), `voix_id` (texte, nul = voix par défaut de la configuration), `lecture_auto` (booléen, vrai par défaut), `maj_le`. Préférence **de la personne**, pas du potager |
| v72 (US-303) | colonne `echanges_conversation.texte_oral` (texte, nul) : le résumé parlé, calculé à la première lecture puis réutilisé |

Les numéros suivent la dernière migration présente (v70) ; ils seront recalés si d'autres
migrations arrivent avant.

### 5.4 Points d'API

| Méthode | Chemin | Rôle | US |
|---|---|---|---|
| GET | `/compagnon/voix/catalogue` | voix françaises (nom, identifiant, genre si fourni), cache 24 h, repli sur les quatre voix connues | 300 |
| GET | `/compagnon/voix/catalogue/{voix_id}/extrait` | MP3 court de la voix (extrait Mistral, sinon phrase fixe synthétisée une fois et gardée en cache) | 300 |
| GET / PUT | `/compagnon/voix/preferences` | mode vocal, voix, lecture automatique | 300 |
| POST | `/compagnon/voix/transcrire` | fichier audio (multipart) → `{ texte }` ; refus au-delà de la durée ou de la taille maximale | 302 |
| POST | `/compagnon/voix/lecture/{echange_id}` | MP3 du résumé parlé de cet échange, dans la voix choisie ; 404 hors du compte, 429 au-delà du plafond | 304 |

`/compagnon/messages` et `/compagnon/historique` exposent en plus `echange_id`
(aujourd'hui absent des réponses) : c'est ce qui permet le ▶ sur une réponse ancienne.

### 5.5 Résumé parlé (US-303)

- Produit à partir du **seul** `texte_compagnon` de l'échange : rien d'inventé, pas de chiffre absent du texte.
- 1 à 2 phrases, plafond `VOIX_ORAL_MAX_CARACTERES` (300 par défaut).
- Une carte de proposition se dit « je vous propose … : confirmez à l'écran » (on ne confirme pas à la voix, US-274).
- Sans Markdown, sans émoji, sans URL (reprise du nettoyage de `utils/tts.py`, déplacé dans le service).
- Repli si le modèle est indisponible : le texte affiché nettoyé, coupé à la dernière phrase sous le plafond.

### 5.6 Balises par règles (US-305, si l'essai US-298 est concluant)

Règles lues sur ce que l'orchestrateur a déjà produit pour l'échange (`signal`,
`proposition_id`, `question`, issue d'erreur), dans un fichier de règles versionné :

| Nature de la réponse | Balises (proposition, à affiner après l'essai) |
|---|---|
| alerte du veilleur (gel, canicule, maladie) | `[emotion=urgent]` |
| récolte enregistrée, objectif atteint | `[emotion=happy]` |
| proposition à confirmer | `[emotion=confident]` |
| question en attente | `[emotion=curious]` |
| indisponibilité, erreur, refus | `[emotion=apologetic]` |
| consigne chiffrée (dose, distance, date) | `[pace=slow]` sur la phrase |
| défaut | `[emotion=warm]` |

Les balises sont ajoutées **au moment de la synthèse** : elles ne sont jamais stockées
dans `texte_compagnon` ni `texte_oral`, donc jamais affichées. Une valeur absente des
listes de Mistral est refusée par notre propre contrôle (l'API, elle, l'accepterait en
silence). `VOIX_BALISES=non` les coupe toutes ; une voix jugée mauvaise à l'essai peut en
être exclue.

### 5.7 PWA

| Élément | Rôle | US |
|---|---|---|
| `lib/voix.js` (+ `voix.test.js`) | logique pure : support du navigateur, choix du type MIME, durée maximale, états de la dictée, règles de lecture automatique | 302, 304 |
| `hooks/useDictee.js` | `getUserMedia` + `MediaRecorder`, arrêt automatique à `VOIX_DICTEE_DUREE_MAX_S` (60 s), libération du micro | 302 |
| `hooks/useLecture.js` | un seul `<audio>` partagé, déverrouillé au premier tap (iOS), une lecture à la fois | 304 |
| `PanneauCompagnon.jsx` | bouton 🎤 à côté de « Envoyer », bulle « 🎤 » pour une phrase dictée, ▶ / ⏹ sur les réponses de Gaston | 302, 304 |
| `ModalMonCompagnon.jsx` | section « Voix » : mode vocal, choix de la voix avec extrait, lecture automatique | 301 |

États du bouton micro : *disponible* → *écoute* (avec durée écoulée) → *transcription* →
*disponible*. Le bouton est **masqué** quand le mode vocal est éteint, et **remplacé par
une explication** quand le navigateur ne peut pas enregistrer (pas de `MediaRecorder`,
contexte non sécurisé, micro refusé ou absent).

### 5.8 Supports visés

| Support | Enregistrement | Lecture | Point d'attention |
|---|---|---|---|
| PC — Chrome, Edge | WebM/Opus | MP3 | — |
| PC — Firefox | WebM/Opus (ou Ogg) | MP3 | — |
| Mac — Safari | MP4/AAC | MP3 | format à valider (C2) |
| iPad — Safari, PWA installée | MP4/AAC | MP3 | son seulement après un geste (D5) ; permission micro redemandée selon les versions |
| iPhone — Safari, PWA installée | MP4/AAC | MP3 | idem iPad ; mode silencieux du téléphone qui coupe le son |
| Android — Chrome, PWA installée | WebM/Opus | MP3 | — |

Le MP3 est choisi en sortie parce qu'il est lu partout, Safari compris.

## 6. Coût estimé

| Poste | Hypothèse | Coût |
|---|---|---|
| Dictée | 10 s | 0,0006 $ |
| Résumé parlé | ~400 jetons d'entrée, 80 de sortie | négligeable |
| Synthèse | 200 caractères | 0,0026 $ |
| **Un échange vocal** | | **≈ 0,3 centime** |
| Jardinier actif | 30 échanges vocaux par jour | ≈ 0,10 $ par jour |
| Extrait de voix | 4 voix, une fois, mis en cache | < 0,01 $ |

Plafond par jardinier : `VOIX_PLAFOND_LECTURES_JOUR` (100 par défaut) et
`VOIX_PLAFOND_DICTEES_JOUR` (100 par défaut).

## 7. RGPD

- L'audio dicté part chez Mistral AI (sous-traitant déjà présent pour le chat) puis est jeté ; aucun fichier n'est gardé côté Assistant Potager, ni sur disque ni en base.
- Le texte transcrit suit le sort des échanges du compagnon (déjà couverts par `RGPD_CARNET_COMPAGNON.md`).
- Hébergement européen de l'audio non confirmé (C5) : à dire tel quel dans le registre.
- Pas de clonage, donc pas de donnée biométrique.
- La préférence de voix est une donnée de la personne : supprimée avec le compte.

## 8. Hors périmètre

- Bot Telegram (D7) : gTTS, Whisper et l'interrupteur global restent tels quels.
- Transcription en temps réel et synthèse en flux (D3) : candidates d'une suite si la latence déçoit.
- Clonage de voix (D2).
- Balises posées par le modèle de langage (D1) : candidate d'une suite si les règles sont trop pauvres.
- Confirmer une carte à la voix (« vas-y ») : la confirmation reste un geste à l'écran.
- Outillage de test dédié (D8).

## 9. Découpage

| US | Titre | Dépend de | Points |
|---|---|---|---|
| US-298 | Essayer Voxtral en français | — | 2 |
| US-299 | Transcrire et synthétiser par Voxtral dans la passerelle | US-298 | 5 |
| US-300 | Mémoriser les préférences vocales et lister les voix | US-299 | 3 |
| US-301 | Régler la voix de mon compagnon | US-300 | 3 |
| US-302 | Dicter une phrase au compagnon | US-299, US-300, US-301 | 5 |
| US-303 | Résumer la réponse pour l'oral | US-299 | 3 |
| US-304 | Écouter la réponse de Gaston | US-300, US-302, US-303 | 5 |
| US-305 | Donner le ton et le rythme par des règles | US-298 (verdict), US-304 | 3 |

Total : 29 points. Ordre de livraison : 298 → 299 → 300 → 301 → 302 → 303 → 304 → 305.
US-301, US-302 et US-304 ont un rendu à l'écran : la maquette est à produire dans Claude
Design avant leur développement.

### 9.1 Modèle Claude et effort conseillés pour l'implémentation

Réglage de la session Claude Code qui développe l'US (`/model`, niveau d'effort). Règle
retenue : **Opus** quand l'US touche un composant partagé, un comportement propre à un
navigateur ou la fidélité d'une réponse de modèle de langage ; **Sonnet** quand elle suit
un schéma déjà présent dans le dépôt. Haiku n'est conseillé pour aucune : chaque US
engage les règles du projet (passerelle, services, corpus `doc_app`, container queries).

| US | Modèle | Effort | Pourquoi |
|---|---|---|---|
| US-298 | Sonnet 5.5 | medium | script jetable d'appels réels et rapport ; peu de code, pas de code applicatif. L'exigence porte sur la rigueur du rapport, pas sur la conception |
| US-299 | Opus 5.5 | high | modifie la passerelle, commune à tout l'IA ; appel non OpenAI à intégrer sans casser la mesure, le journal, le mode dégradé ni la transcription Telegram ; conversion FFmpeg et nettoyage des fichiers en cas d'erreur |
| US-300 | Sonnet 5.5 | medium | migration, service et routes sur des schémas déjà présents (préférences, cache) ; vigilance sur le cloisonnement par personne et la liste de secours |
| US-301 | Sonnet 5.5 | medium | section de réglages dans une fenêtre existante, d'après la maquette ; seul point délicat : l'extrait audio sur iPhone |
| US-302 | Opus 5.5 | high | `MediaRecorder` et `getUserMedia` diffèrent selon les navigateurs (formats, permissions, iOS, PWA installée) ; machine d'états du bouton, libération du micro, envoi automatique sans contourner la confirmation |
| US-303 | Opus 5.5 | high | fidélité du résumé (aucun fait inventé, propositions jamais dites « enregistrées ») : prompt et jeu de réponses réelles à construire avec soin ; migration v72 et exposition d'`echange_id` |
| US-304 | Opus 5.5 | high | lecture audio sur iOS (déverrouillage par geste), une lecture à la fois, arrêt avant ouverture du micro, cache invalidé au changement de voix, plafond quotidien |
| US-305 | Sonnet 5.5 | medium | fichier de règles et contrôle des valeurs au chargement ; logique simple une fois le verdict d'US-298 connu |

L'effort `xhigh` ou `max` n'est pas nécessaire : aucune US ne demande une exploration large
du dépôt. On peut monter d'un cran si une US bute sur un défaut propre à un navigateur
(US-302, US-304) ou si le résumé d'US-303 échoue au jeu de réponses réelles.

## 10. Sources

- [Text to Speech — vue d'ensemble](https://docs.mistral.ai/studio/audio/text-to-speech/overview)
- [Speech generation](https://docs.mistral.ai/studio/audio/text-to-speech/generate-speech)
- [Emotion and pace tags](https://docs.mistral.ai/studio/audio/text-to-speech/emotion-tags)
- [Voices](https://docs.mistral.ai/studio/audio/text-to-speech/voices)
- [Voice cloning](https://docs.mistral.ai/studio/audio/text-to-speech/voice-cloning)
- [Speech to text](https://docs.mistral.ai/studio/audio/speech-to-text/overview)
- [Transcribe files](https://docs.mistral.ai/studio/audio/speech-to-text/transcribe-files)
- [Audio formats](https://docs.mistral.ai/studio/audio/specs-and-limits/audio-formats)
- [Limits](https://docs.mistral.ai/studio/audio/specs-and-limits/limits)
- [Languages](https://docs.mistral.ai/studio/audio/specs-and-limits/languages)
- [Models](https://docs.mistral.ai/getting-started/models)
- [Regional inference](https://docs.mistral.ai/inference/regional-inference)
- [API pricing](https://docs.mistral.ai/inference/pricing)
