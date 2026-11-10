# Rapport d'essai Voxtral en français (US-298)

Essai réalisé le 10/11/2026, en un seul passage, avec l'accord du jardinier (volume annoncé : environ 0,15 $). Aucun code de l'application n'a été modifié.

- Échantillons audio, scripts et résultats bruts : dossier **local** `C:\Users\eremy\essai_voxtral_fr\` (hors dépôt) : `tts\` (MP3), `enregistrements\` (dictées), `resultats_tts.json`, `resultats_stt.json`, `grille_ecoute.csv`.
- Aucune clé n'apparaît dans ce rapport.

## Verdict

1. **Balises d'émotion (`[emotion=…]`) : à abandonner en l'état.** Le jardinier ne retrouve pas les intonations attendues sur les quatre voix françaises et juge les balises « pas très convaincantes ». US-305 ne doit pas poser de balises d'émotion sur ces voix. *Verdict proposé, à confirmer par le jardinier.*
2. **Balise de rythme (`[pace=slow|fast]`) : retenue seulement pour Manon**, où elle ralentit et accélère nettement. Sur Marie, le résultat est « pas lent / pas rapide » ; sur Lea et Camille, aucun effet noté.
3. **Prononciation du mot « Attention » : défaut général**, relevé sur les quatre voix avec balise : accent anglais, ou mot écorché (Manon, `confident`). Marie `urgent`, `curious`, `apologetic` et `confident` sont « plus audibles mais encore mal prononcés ». Le défaut n'a été relevé que sur les fichiers avec balise ; le fichier de référence sans balise n'a pas été noté et doit être réécouté pour savoir si la balise en est la cause.
4. Aucune voix n'est exclue pour artefact : aucune balise n'a été prononcée ni n'a dégradé la voix.
5. **Transcription : les trois formats testés sont acceptés** (voir ci-dessous) ; aucune conversion FFmpeg n'est nécessaire.

### Pistes non testées
- Les six voix `Marie - Sad / Neutral / Happy / Excited / Curious / Angry` (langue `fr_fr`) portent l'émotion dans la voix et ne passent pas par une balise : elles méritent une écoute avant d'abandonner toute intonation.
- Le défaut sur « Attention » vient peut-être de la langue de la voix (sélection de la langue non maîtrisée côté API) : à essayer avec une phrase sans ce mot, et avec la voix `Marie - Neutral`.

## Identifiants et points d'API (CA7)

| Élément | Constat |
|---|---|
| Modèle de synthèse | `voxtral-mini-tts-3-0` et `voxtral-mini-tts-3` fonctionnent. `voxtral-mini-tts-2603` et `voxtral-mini-tts-latest` sont **refusés** : 400, code 3051, « voice is not supported for speech v1 » |
| Modèle de transcription | `voxtral-mini-transcribe-3` et `voxtral-mini-transcribe-3-0` fonctionnent, réponse équivalente |
| Synthèse | `POST /v1/audio/speech`, corps `model`, `input`, `voice_id` (`voice` est aussi accepté), `response_format: mp3` ; réponse JSON avec `audio_data` en base64 |
| Transcription | `POST /v1/audio/transcriptions`, `model`, `language=fr`, fichier en multipart |
| Liste des voix | `GET /v1/audio/voices?limit=100&type=preset`. Le filtre `language=fr` est **ignoré** ; sans `limit`, la page est de 10 voix sur 66 |
| Longueur d'entrée | 300, 1 500 et 5 000 caractères passent ; latence 3,4 s, 6,8 s et 8,3 s. La limite maximale n'a pas été atteinte |
| Région EU | `api.eu.mistral.ai` liste les mêmes modèles et la synthèse y répond (200, 4,2 s) |

## Voix françaises (CA4)

Quatre voix `fr`, toutes féminines, sans extrait audio exposé par la liste ni description :

| Nom | Identifiant | Genre |
|---|---|---|
| Marie | `01a1536e-a46c-7101-b6e9-1ebda46309fd` | féminin |
| Manon | `01a151d2-8c33-7781-a14d-bd91dd8426cc` | féminin |
| Lea | `01a151d2-8c29-766d-9ca2-30f33707cef6` | féminin |
| Camille | `01a151d2-8c1f-75cf-8cdf-20f328c00764` | féminin |

Six autres voix en `fr_fr` (variantes `Marie - <émotion>`) existent ; elles n'ont pas été synthétisées.

## Balises : résultat d'écoute (CA5, CA6)

Phrase : « Attention, gel prévu cette nuit : pense à couvrir les tomates. » Les 36 MP3 ont été synthétisés (4 voix × sans balise, 6 émotions, 2 rythmes), tous en 200, en 1 à 2,5 s. Le fichier de référence sans balise n'a pas été noté.

| Voix | Émotions | `pace=slow` | `pace=fast` | Remarque d'écoute |
|---|---|---|---|---|
| Marie | pas d'intonation attendue | pas plus lent | pas plus rapide | « Attention » à l'accent anglais sur `warm` et `happy`, mal prononcé sur les autres |
| Manon | pas d'intonation attendue | plus lent | plus rapide | `confident` : « Attention » écorché, la voix passe très vite dessus |
| Lea | pas d'intonation attendue | non noté | non noté | « Attention » à l'accent anglais partout |
| Camille | pas d'intonation attendue | non noté | non noté | « Attention » à l'accent anglais partout |

Le tableau de saisie renseigne « audible » pour les 32 combinaisons et « artefact : non » partout ; cette colonne dit qu'une différence est perçue, pas que l'intonation voulue est obtenue. Le verdict ci-dessus s'appuie sur les remarques.

## Transcription (CA2, CA3)

Cinq phrases dictées, `language=fr`, modèle `voxtral-mini-transcribe-3`. Tous les envois ont reçu un code 200.

| Format | Origine | Résultat |
|---|---|---|
| `audio/webm;codecs=opus` | Chrome | accepté |
| `audio/ogg;codecs=opus` | Firefox | accepté |
| AAC dans mp4 | **`.m4a` enregistré sur macOS (QuickTime/Dictaphone)** | accepté |

**Réserve :** le format `audio/mp4` produit par Safari n'a pas été testé. Le Mac disponible porte Safari 13.1.2, dont `MediaRecorder` est absent, donc la dictée dans le navigateur était impossible. Le `.m4a` natif contient le même codec AAC et vaut comme indication, pas comme preuve du comportement du navigateur ; à confirmer avec Safari sur iPhone depuis la PWA.

Latence : 0,6 à 1,1 s par phrase, sans écart net entre formats. Aucune conversion FFmpeg n'a été nécessaire, donc aucun surcoût de conversion à mesurer.

| Phrase attendue | webm | ogg | m4a |
|---|---|---|---|
| 1. 2 kilos de tomates Cœur de bœuf, hier | « deux kilos de tomates cœur de bœuf hier » | idem | « **2** kilos de tomates cœur de bœuf hier » |
| 2. carottes Nantaise, radis Flamboyant | « carottes nantaises et radis flamboyants » | idem | idem |
| 3. courgettes Black Beauty, dix minutes | « arrosé **tes** courgettes », « dix minutes » | juste, « dix minutes » | juste, « **10** minutes » |
| 4. douze poireaux | juste | juste | juste |
| 5. gel prévu cette nuit | juste | juste | juste |

À retenir :
- Une première passe a donné « j'ai le prévu » sur l'ogg pour la phrase 5 ; une seconde passe donne « gel prévu ». Le résultat varie entre deux envois du même fichier sur les mots courts.
- Les nombres sortent tantôt en lettres (webm, ogg), tantôt en chiffres (m4a) : l'application doit accepter les deux.
- Les noms de variétés restent justes pour « Black Beauty » et « Cœur de bœuf » ; « Nantaise » et « Flamboyant » sont mis au pluriel dans les trois formats. La date relative « hier » est bien reconnue.

## Conséquences pour la suite

- **US-305 (balises) :** ne pas poser de balises d'émotion en l'état ; décision du jardinier à prendre sur la clôture sans suite ou sur l'essai des voix `Marie - <émotion>`.
- **Transcription :** aucune conversion de format à prévoir pour webm, ogg et AAC ; vérifier `audio/mp4` depuis un navigateur Safari récent.
- **Identifiants :** utiliser `voxtral-mini-tts-3-0` et `voxtral-mini-transcribe-3`, et ne pas se fier aux alias `-2603` et `-latest` en synthèse.
