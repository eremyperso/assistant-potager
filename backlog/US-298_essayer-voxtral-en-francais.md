**ID :** US-298
**Titre :** Essayer Voxtral en français avant de construire
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que porteur du produit
Je veux entendre et mesurer Voxtral sur de vraies phrases de potager en français, avec les formats que produisent les navigateurs
Afin de décider sur preuve si les balises d'émotion et de rythme valent d'être construites et quels formats audio il faut convertir

**Contexte fonctionnel :**
La documentation Mistral garantit les balises en anglais seulement (« untested but expected to work » en français), ne liste pas les formats acceptés en transcription et donne des identifiants de modèles incohérents (étude §3, D1, C2, C7). Cette US lève ces trois inconnues avant tout développement.

**Critères d'acceptance :**
- [ ] CA1 : Avant tout appel au vrai Mistral, le volume est annoncé (nombre d'appels, caractères, minutes d'audio, coût estimé, de l'ordre de 0,10 $) et l'accord du jardinier est obtenu ; l'essai se joue en un seul passage.
- [ ] CA2 — **transcription** : cinq phrases de potager dictées (dont deux noms de variétés, un nombre, une date relative « hier ») sont enregistrées dans chacun des formats `audio/webm;codecs=opus`, `audio/mp4` (AAC) et `audio/ogg;codecs=opus`, puis envoyées à `/v1/audio/transcriptions` en `language=fr`. Le rapport dit pour chaque format : accepté ou refusé (code et message), texte obtenu, latence.
- [ ] CA3 — Si un format est refusé, le rapport dit vers quel format FFmpeg le convertir (WAV 16 kHz mono ou MP3), et mesure le surcoût en temps de la conversion.
- [ ] CA4 — **voix** : la liste des voix françaises est lue par l'API (`type=preset`, `language=fr`) ; le rapport donne pour chacune l'identifiant, le nom, le genre s'il est fourni, et l'existence d'un extrait audio.
- [ ] CA5 — **balises** : pour chacune des voix françaises, la même phrase est synthétisée sans balise, puis avec `warm`, `happy`, `urgent`, `curious`, `apologetic`, `confident`, puis avec `[pace=slow]` et `[pace=fast]`. Les fichiers MP3 sont rangés avec une grille d'écoute.
- [ ] CA6 — Le jardinier écoute les échantillons et remplit la grille : pour chaque voix et chaque balise, « audible », « faible » ou « absente », et « artefact » si la balise dégrade la voix ou est prononcée. Le rapport conclut par un **verdict** : balises retenues, voix exclues, ou balises abandonnées (US-305 est alors close sans suite).
- [ ] CA7 : Le rapport relève les identifiants exacts acceptés par l'API (`voxtral-mini-transcribe-3` ou `voxtral-mini-transcribe-3-0`, `voxtral-mini-tts-3-0`), le chemin du point d'API qui liste les voix, la longueur maximale d'entrée de synthèse constatée (essai à 300, 1 500 et 5 000 caractères) et si les modèles audio répondent sur `api.eu.mistral.ai`.
- [ ] CA8 : Le rapport est rangé dans `docs/EPIC 17 - COMPAGNON VOCAL PWA/RAPPORT_ESSAI_VOXTRAL_FR.md` ; les échantillons audio restent hors du dépôt, dans un dossier local nommé dans le rapport ; aucune clé n'apparaît dans le rapport.
- [ ] CA9 : Aucun code de l'application n'est modifié par cette US.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : étude (aucune livraison applicative)
- Migration BDD requise : non
- Dépendances : aucune
- Décisions liées : D1 (balises), C2 (formats), C7 (identifiants)
- Fiche du corpus : aucune (pas de changement de comportement)

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Given le jardinier a donné son accord pour un essai d'environ 0,10 $
When la phrase "Gaston, j'ai récolté 2 kilos de tomates Cœur de bœuf hier" est enregistrée en audio/mp4 depuis Safari
And envoyée à Voxtral Mini Transcribe 3 en français
Then le rapport indique si le format est accepté et le texte transcrit
When la phrase "Attention, gel prévu cette nuit" est synthétisée avec la voix Marie et la balise [emotion=urgent]
Then le jardinier note à l'écoute si l'urgence est audible
And le rapport conclut sur les balises retenues pour US-305
```

**Labels GitHub :** `us`, `etude`, `voix`, `compagnon`
