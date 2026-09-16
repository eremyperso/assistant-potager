**ID :** INC-001
**Titre :** Une culture en pépinière est affichée « plantée » sans aucune plantation réelle
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-16

**Reproduction (jeu de test réalisé) :**
Semis de graines de tomate variété « coeur de boeuf » en pépinière (événement
#495, 15/03/2026, parcelle 65 — SERRE, contexte_semis = pépinière), puis mise
en godet des graines germées quelques semaines plus tard (événement #496,
15/04/2026, 10 plants sur 10 graines, rattaché au semis #495 via
`origine_graines_id`). Aucune plantation n'a été réalisée ni enregistrée pour
cet itinéraire.

**Résultat obtenu :**
Dans la vue liste des cultures/pépinière, la vignette « Tomate · coeur de
boeuf » datée du 15/03/2026 (185 jours) affiche le badge « Terre », une
barre de progression Germination/Godet/Terre entièrement remplie, et la
mention « 10 semés · 10 obtenus · 10 mis en terre ». En ouvrant le détail de
cet itinéraire précis (« Cycle de vie — semis du 15/03/2026 »), seules deux
étapes apparaissent (Semis #495, Lot godet #496, taux de germination 100 %)
et le détail affiche explicitement « Pas encore planté ». Les deux vues, pour
le même itinéraire, se contredisent : la vignette annonce une mise en terre
que le détail — qui liste les événements réellement rattachés — dément.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Tant qu'aucun événement de plantation n'est rattaché à cet itinéraire de
semis, la vignette ne devrait afficher ni le badge « Terre » ni de quantité
« mis en terre » : elle devrait rester au stade « Godet », cohérente avec le
détail du cycle de vie et avec le journal d'événements réel.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend (`utils/stock.py`, agrégation pépinière),
  servie à la vue liste des cultures du frontend.
- Nature probable : erreur d'agrégation côté backend (le champ `nb_plantes`
  remonté semble déjà faux), pas un défaut d'affichage pur.
- Fichiers probablement concernés : `utils/stock.py`, fonction
  `calcul_lots_pepiniere` — à confirmer par le Developer.
- Corpus de connaissance concerné : non.

**Captures :** C:\Users\eremy\Downloads\data-1789543814189.csv

**Labels :** incident, backend, pepiniere, agregation
