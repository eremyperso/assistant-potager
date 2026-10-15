**ID :** INC-013
**Titre :** Perte de godet du lot n° 7 non rattachée au lot : affichée dans le cycle de vie de tous les lots de la même culture
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-15

**Reproduction (jeu de test réalisé) :**
Depuis l'application, un geste `perte_godet chou (2026-10-15)` est préparé puis confirmé dans le bot Telegram.
Le bot demande « Combien de plants avez-vous perdus ? — Lot n° 7 · 01/09/2026 : il reste 100 plant(s) en godet », l'utilisateur répond `10`.
Le bot confirme « C'est noté ! (ID #605) … Lot : n° 7 ».
Ensuite, ouverture de la fiche « Cycle de vie » des lots #5 et #7 (chou frisé) dans l'application.

**Résultat obtenu :**
- Le message de confirmation annonce bien « Lot : n° 7 », mais l'événement #605 est enregistré en base avec `numero_lot` NULL et `source_evenement_ids` NULL (seul `origine_graines_id` = 580, le semis du lot 7, est renseigné). Les mises en godet #577, #594, #600, #604 ont aussi `numero_lot` NULL.
- Capture 1 (cycle de vie du lot #5, semis #558 du 09/10/2026) : la ligne « Perte pépinière #605 — 10 plants perdus — 15/10/2026 » apparaît alors que cette perte concerne le lot 7, pas le lot 5.
- Capture 2 (cycle de vie du lot #7, semis #580 du 01/09/2026) : la même perte #605 apparaît, ce qui est attendu.
- La perte est donc visible dans la fiche détail de tous les lots de la même culture/variété, comme si elle leur était commune.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
La perte #605 est rattachée au seul lot n° 7 (celui annoncé par le bot) : elle n'apparaît que dans le cycle de vie du lot #7 et jamais dans celui du lot #5 (ni d'aucun autre lot).

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend (enregistrement du geste puis construction du cycle de vie) ; Bot Telegram (confirmation de lot) ; affichage Frontend de la fiche de lot en aval.
- Nature probable : donnée erronée en base (le rattachement au lot choisi n'est pas persisté sur l'événement) combinée à un regroupement par culture/variété à la lecture — à investiguer.
- Fichiers probablement concernés : `app/services/evenements.py` (`cycle_vie_culture`, enregistrement des `perte_godet`, `_lot_numero`), `app/services/lots_pepiniere.py`, `app/bot/godets.py`, `app/bot/enregistrement.py`, `frontend/src/components/FicheLot.jsx`.
- Corpus de connaissance concerné : oui probable — `data/connaissance/doc_app/pepiniere-par-lot.md` à relire si le comportement du rattachement change.

**Labels :** incident, backend, bot, pepiniere
