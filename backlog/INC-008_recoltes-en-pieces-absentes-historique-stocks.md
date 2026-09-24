**ID :** INC-008
**Titre :** Les récoltes en pièces d'une culture végétative n'apparaissent pas dans l'historique des récoltes de Stocks
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-24

**Reproduction (jeu de test réalisé) :**
Potager courant, parcelle `planche_salade`, culture `salade` (famille
Astéracée, organe de récolte végétatif), sans variété précisée. Plusieurs
récoltes de pieds de salade ont été enregistrées, dont deux le 24/09/2026 :
une récolte de 3 plants puis une récolte de 24 plants, toutes deux en pièces
(unité `plants`), jamais pesées. Consulter ensuite la vue Stocks, ligne
`salade`. Le canal de saisie des récoltes n'est pas précisé.

**Résultat obtenu :**
La ligne `salade` de la vue Stocks ne donne aucun accès aux récoltes : la
colonne « Récolté » affiche `0 kg` et la mention « non pesé » à la place du
lien vers l'historique des récoltes. Aucune des récoltes en pièces n'y est
donc consultable, alors qu'elles sont bien enregistrées au journal. Le
déclarant indique que les récoltes sur cultures végétatives ne sont « plus »
collectées dans cet historique — le comportement antérieur n'est pas décrit.

Capture 1 — vue Stocks, groupe « Astéracée (1) » et sa ligne `salade`
(« Variété non précisée », état « Au potager », origine « PIED ACHETÉ ») :
1 parcelle `planche_salade`, 53 plants, 23 en place, colonnes « Vendu » et
« Perdu » à « — », colonne « Récolté » à `0 kg` / « non pesé ».

Capture 2 — journal du jour, « Aujourd'hui · 24 septembre » : deux entrées
« Récolte de 3 plants de salade » et « Récolte de 24 plants de salade »,
toutes deux rattachées à `planche_salade`.

Les deux captures se recoupent sur le décompte du stock : 53 plants installés,
23 en place, l'écart correspondant aux récoltes en pièces. La déduction de
stock fonctionne donc ; c'est leur **restitution dans l'historique des
récoltes** qui manque.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Les récoltes en pièces d'une culture végétative doivent être consultables
depuis la vue Stocks, comme le sont les récoltes pesées : la ligne `salade`
doit annoncer le nombre de récoltes et ouvrir leur historique chronologique.
Une récolte qui a réellement diminué le stock ne doit pas être absente de
l'historique des récoltes de la culture.

Le format d'affichage d'une récolte non pesée dans cet historique (quantité en
pièces, cumul, cohabitation avec des récoltes pesées de la même culture) reste
à préciser.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Frontend (vue Stocks), API/Backend.
- Nature probable : à investiguer — périmètre de l'historique des récoltes
  probablement restreint aux récoltes pesées.
- Fichiers probablement concernés : `frontend/src/views/Stocks.jsx`
  (`RecLink`, qui ne propose le lien que si `nb_recoltes_poids` est non nul, et
  `ModalRecoltes`, qui ne retient que les unités `kg`/`g`/`mg`, toutes deux
  confirmées présentes) ; `utils/stock.py` (champ `nb_recoltes_poids`, confirmé
  présent).
- Corpus de connaissance concerné : à vérifier par le Developer — une fiche de
  `data/connaissance/doc_app/` décrivant le stock et les récoltes devra être
  mise en cohérence dans la livraison corrective si le comportement change.

**Captures :** C:\Users\eremy\AppData\Local\Temp\claude\c--Users-eremy-OneDrive---SQLI-Documents-GitHub-assistant-potager\8ae02fc4-e0a5-4d0c-a27d-a4af3e91bce2\images\1.png, C:\Users\eremy\AppData\Local\Temp\claude\c--Users-eremy-OneDrive---SQLI-Documents-GitHub-assistant-potager\8ae02fc4-e0a5-4d0c-a27d-a4af3e91bce2\images\2.png

**Labels :** incident, frontend, backend
