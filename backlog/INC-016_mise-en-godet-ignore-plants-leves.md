**ID :** INC-016
**Titre :** La mise en godet d'un lot est plafonnée par les graines semées, pas par les plants levés restants
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-20

**Reproduction (jeu de test réalisé) :**
Lot n° 4 · Tomate jaune, semé le 21 septembre en SERRE (pépinière chaude) :
20 graines semées, 18 levées notées. Une mise en godet de 15 plants avait déjà
été enregistrée sur ce lot.
Dans le bot Telegram, traitement de la file des gestes (`gestes`) :
1. Geste « mise en godet » de tomate jaune sur le lot n° 4 (file id=119). Le bot
   réclame le nombre de plants en indiquant « il reste 5 graines » ; saisie : 5.
   Godet enregistré (id=635, rattaché au semis 518).
2. Geste « plantation » de 15 plants de tomate jaune sur le lot n° 4 (file
   id=120), parcelle « tubercule », confirmé (événement id=636).

Extrait du journal :
```
[US-066] Nombre de graines réclamé pour le lot #518 (5 restantes)
[US-066] Nombre de graines saisi : 5
💾 GODET SAVE : id=635 culture=tomate variete=jaune origine=518
[US-212 / CA9] Incohérence de saisie sur le lot semis-518 (tomate) : 20 plants repiqués pour 18 levés — valeurs exposées telles quelles, sans bornage
```

**Résultat obtenu :**
- Le maximum proposé à la mise en godet est calculé comme « graines semées −
  plants déjà en godet » (20 − 15 = 5), sans tenir compte du nombre de graines
  effectivement levées (18).
- La mise en godet de 5 plants est acceptée : le lot compte alors 20 plants
  repiqués pour 18 levés. L'incohérence est détectée (avertissement US-212 / CA9
  répété dans le journal) mais n'empêche ni ne signale rien au jardinier.
- Capture jointe : fiche du lot « #4 · Tomate jaune » dans la PWA. Le bilan
  affiche « 20 semées · 18 levés · 5 en godet · 15 en terre », soit 20 plants
  passés en godet puis en terre pour 18 levés. La pastille indique « 5 godets ·
  sortir bientôt » ; « Où les mettre » propose planche racines et tubercule.
  La capture est cohérente avec le journal.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Lorsque des levées ont été notées sur le lot, le nombre de plants repiquables en
godet doit être plafonné par les plants levés restants (levés − déjà repiqués,
ici 18 − 15 = 3), et non par les graines semées. Il ne doit pas être possible de
repiquer en godet plus de plants que de graines levées disponibles.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (saisie du nombre en mise en godet) et
  calcul de stock du lot (utilitaire partagé).
- Nature probable : régression logique — la capacité de repiquage s'appuierait
  sur les graines restantes au lieu des levés restants.
- Fichiers probablement concernés : `app/bot/godets.py` (demande du nombre,
  appels à `graines_restantes`), `utils/stock.py` (`graines_restantes`, l. ~1775).
  Voisin de INC-014 (mise en terre au-delà des godets disponibles), sur l'étape
  précédente du parcours — symptôme distinct, pas un doublon.
- Corpus de connaissance concerné : oui — relire `data/connaissance/doc_app/semis-godet-plantation.md`
  et `data/connaissance/doc_app/pepiniere-par-lot.md` si la règle de plafonnement change.

**Labels :** incident, bot, pepiniere
