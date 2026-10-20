**ID :** INC-014
**Titre :** La mise en terre d'un lot peut être répétée sans limite et dépasse le nombre de plants en godet
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-16

**Reproduction (jeu de test réalisé) :**
Dans la PWA, onglet Pépinière > Aujourd'hui, ligne du lot n° 8 · Poireau
(50 godets disponibles, SERRE), clic sur le bouton « Mettre en terre ». Le geste
est ajouté à la file des gestes en attente. Le bouton reste actif : le clic a été
répété plusieurs fois, d'où autant de gestes empilés. Côté bot Telegram, la file
est traitée avec la commande `gestes` : pour chaque geste, choix « Commencer »,
choix de la parcelle, puis validation avec le nombre de plants maximum proposé
pour la culture (50). Consultation ensuite de `/stats` et de la fiche du lot
dans la PWA.

**Résultat obtenu :**
- Le bouton « Mettre en terre » reste cliquable après l'ajout du geste à la file
  et la file enregistre autant de gestes que de clics.
- Chaque geste traité côté bot valide la quantité maximale (50), sans tenir
  compte des mises en terre déjà enregistrées ni du stock restant du lot.
- `/stats` affiche « poireau : 250 plants (planté 250) », alors que le lot n° 8
  ne compte que 50 godets (la rubrique Pépinière indique « poireau : 50 plants »).
  Il y a donc 5 mises en terre de 50, soit 200 plants de plus que le lot d'origine.
- Dans la PWA, le détail du lot Poireau montre plusieurs cycles de plantation par
  groupes de 50 poireaux, alors que la fiche du lot n'indique que 50 plants mis
  en terre : les deux vues se contredisent.
- Capture jointe : onglet Aujourd'hui de la pépinière. La ligne « #8 · Poireau »
  indique « 50 godets disponibles » et « Mise en terre +6 j », avec le bouton
  vert « Mettre en terre » actif. La tuile « Prêts pour le plan » annonce
  « 50 plants ». La capture est cohérente avec le texte : le stock n'est pas
  débité et le bouton reste proposé.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
- Le total des plants mis en terre à partir d'un lot ne dépasse jamais le nombre
  de plants disponibles dans ce lot. `/stats` et la fiche du lot doivent rester
  cohérents entre eux.
- Une fois le geste « Mettre en terre » ajouté à la file, le bouton ne doit plus
  permettre d'en empiler un second pour le même lot (désactivé, ou remplacé par un
  état « geste en attente »).
- La PWA propose par défaut la totalité restante du lot. Elle doit aussi permettre
  de mettre en terre un nombre limité de plants, puis de répartir le reste sur
  d'autres parcelles par plusieurs mises en terre successives. Le bot le permet
  déjà (nombre de plants et parcelle choisis).

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Frontend (bouton de geste, file de gestes en attente) ;
  API/Backend (enregistrement du geste et validation du stock restant du lot) ;
  Bot Telegram (reprise des gestes préparés, quantité proposée).
- Nature probable : régression logique — probablement une absence de contrôle du
  restant du lot à l'enregistrement, et une absence d'état « geste déjà en
  attente » côté bouton. À investiguer.
- Fichiers probablement concernés : `frontend/src/components/BoutonGeste.jsx`,
  `frontend/src/lib/gestes.js`, `frontend/src/components/FicheLot.jsx`,
  `app/services/echeances_lots.py`, `app/bot/` (reprise des gestes en attente).
- Lien : INC-003 (file de gestes qui ne dépile pas après confirmation) et INC-013
  (perte de godet non rattachée au lot) touchent la même file de gestes ; ce
  signalement reste distinct (dépassement du stock et bouton toujours actif).
- Corpus de connaissance concerné : non identifié à ce stade — si le correctif
  change le comportement de la mise en terre, relire la table « ce qui rend une
  fiche fausse » de `data/connaissance/doc_app/README.md`.

**Captures :** C:\Users\eremy\AppData\Local\Temp\claude\c--Users-eremy-OneDrive---SQLI-Documents-GitHub-assistant-potager\56bbf5dc-e208-4831-aa02-71030e1fb528\images\1.png

**Labels :** incident, frontend, backend, bot
