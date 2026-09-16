**ID :** INC-002
**Titre :** Deux séries distinctes de tomate cerise (semis vs plantation) affichent le même calendrier, et la plantation n'indique pas sa propre date
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-16

**Reproduction (jeu de test réalisé) :**
Consultation de la tuile « planche tomate » (parcelle 61, potager 26) sur la
vue Plan. Extrait de la base fourni (`evenements`) pour cette parcelle et la
variété tomate cerise :
- #499 : semis, 2026-02-10, 10 graines, `contexte_semis = pleine_terre`,
  aucun chaînage (pas d'`origine_graines_id`).
- #474 : plantation, 2026-09-08, 12 plants, aucun `origine_graines_id` (pas
  de lot godet/semis rattaché).
- #502 : récolte, 2026-06-08, 2 kg.
- #475 : récolte, 2026-09-08, 10 kg.
- #479 : récolte, 2026-09-09, 2 kg.

**Résultat obtenu :**
La tuile affiche bien deux cartes distinctes pour « Tomate cerise » (« une
autre série en place » sur chacune), ce qui est cohérent avec deux origines
différentes. Mais les deux cartes sont identiques sur le fond :
- les deux indiquent « Semé le 10 février en pleine terre » et « en récolte
  depuis le 8 juin », avec la même frise (mêmes mois colorés) — y compris la
  carte des « 12 plants », qui correspond à l'événement de PLANTATION #474 du
  8 septembre, sans aucun semis ni godet rattaché.
- aucune des deux cartes n'affiche la date de plantation du 8 septembre 2026
  pour l'événement #474 : la seule date de semis (10 février) apparaît, pour
  les deux cartes.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Les deux séries devraient être recalées indépendamment l'une de l'autre. La
carte issue de la plantation #474 (sans chaînage vers un semis) ne devrait
jamais afficher « Semé le 10 février » : elle devrait afficher sa propre
origine, la plantation du 8 septembre 2026, et son propre état de récolte
(à ce jour, aucune récolte ne devrait normalement lui être rattachée, ou en
tout cas pas la même que la série de semis).

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend (`app/services/recalage_calendrier.py`,
  US-070), vue Plan du frontend qui affiche les tuiles calendrier.
- Nature probable : régression logique, probablement dans
  `rattacher_recoltes()` — la fonction rattache chaque récolte à « la plus
  ancienne série ouverte dont l'origine la précède », et une série de tomate
  cerise (organe reproducteur) ne se ferme jamais. Quand deux séries d'une
  même tuile sont ouvertes en même temps (ici : la série semis de février et
  la série plantation de septembre), toutes les récoltes semblent pouvoir
  se rattacher à la première série de la liste au lieu de la série dont elles
  relèvent réellement, ce qui pourrait expliquer que les deux cartes se
  retrouvent avec le même état de récolte affiché. Reste à confirmer par le
  Developer, sans présumer du détail exact.
- Fichiers probablement concernés : `app/services/recalage_calendrier.py`
  (`rattacher_recoltes`, `construire_series`, `projeter_tuile`), et le
  composant frontend qui restitue une tuile par série (probablement
  `frontend/src/views/Plan.jsx` / `frontend/src/lib/calendrier.js`).
- Corpus de connaissance concerné : non.

**Labels :** incident, backend, calendrier, us-070
