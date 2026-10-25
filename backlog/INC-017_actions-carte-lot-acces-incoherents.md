**ID :** INC-017
**Titre :** Carte de lot (Pépinière > Parcours) : « Repiquer » déclenche le geste, « Noter la levée » ouvre la fiche — accès aux actions incohérents
**Type :** Incident
**Priorité :** Mineur

**Signalé le :** 2026-10-22

**Reproduction (jeu de test réalisé) :**
Frontend, Pépinière, onglet Parcours (tableau par emplacement × étape). Emplacement
« tunnel chauffé » (pépinière chaude), lot #1 Courgette, 20 graines semées le 30 mars,
colonne « En levée ». La carte du lot affiche deux boutons : « Repiquer » et
« Noter la levée ». Appuyer sur chacun des deux.

**Résultat obtenu :**
- « Repiquer » déclenche directement le geste depuis la carte du lot.
- « Noter la levée » ne déclenche pas le geste : il ouvre le volet de détail du lot
  (« #1 · Courgette ») sous le tableau.
- Ce volet de détail propose à son tour toutes les actions du lot, dont
  « Repiquer en godet », « Noter la levée » et « Perte » (bloc « Le geste »), ainsi
  que le bilan et le lien « Journal complet du lot ».

Capture : tableau Parcours, carte #1 Courgette encadrée « #1 · ouvert » dans la
colonne « En levée », boutons « Repiquer » / « Noter la levée » sur la carte, et
volet de détail ouvert en dessous avec les trois gestes. Cohérente avec le texte.

Deux boutons visuellement identiques, côte à côte sur la même carte, ont donc deux
comportements différents (geste immédiat vs navigation vers le détail), et l'action
« Repiquer » est accessible en double (carte et détail) sans logique lisible.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Des accès aux actions logiques et prévisibles : les boutons d'une même carte doivent
avoir un comportement homogène (soit tous déclenchent leur geste, soit la carte
ouvre le détail et les gestes vivent dans le détail). Défaut de conception UX/UI à
revoir : définir où vit chaque action (carte = raccourci du geste suggéré ?
détail = toutes les actions ?) et appliquer cette règle uniformément.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Frontend (`frontend/`)
- Nature probable : défaut de conception UX (câblage des actions de la carte de lot), à
  arbitrer côté design avant correction
- Fichiers probablement concernés : `frontend/src/components/OngletParcours.jsx`
  (carte de lot, plusieurs `BoutonGeste`), `frontend/src/components/FicheLot.jsx`
  (volet de détail, « Noter la levée » US-212), `frontend/src/components/BoutonGeste.jsx`,
  probablement `frontend/src/lib/parcours.js` / `frontend/src/lib/ficheLot.js`
  (action suggérée `noter_levee`)
- Corpus de connaissance concerné : possiblement — si le comportement des boutons
  change, relire la fiche pépinière de `data/connaissance/doc_app/` via la table de
  son `README.md`

**Labels :** incident, frontend, ux
