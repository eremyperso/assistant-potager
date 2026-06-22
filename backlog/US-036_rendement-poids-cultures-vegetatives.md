**ID :** US-036
**Titre :** Suivre le rendement en poids des cultures végétatives récoltées en pieds

**Story :**
En tant que jardinier
Je veux pouvoir dicter le poids récolté en plus du nombre de pieds lors d'une récolte de culture végétative (ex : "récolte 2 betteraves 250g")
Afin de suivre le rendement réel en poids de ces cultures, comme c'est déjà possible pour les cultures reproductrices

**Critères d'acceptance :**
- [ ] CA1 : Le bot reconnaît naturellement une récolte végétative dictée avec un nombre de pieds ET un poids ("récolte 2 betteraves 250g", "j'ai récolté 3 salades pour 600 grammes")
- [ ] CA2 : Groq extrait séparément le nombre de pieds récoltés et le poids associé (kg ou g)
- [ ] CA3 : Le bot enregistre **deux événements `recolte` distincts** pour cette même action (même culture/date/parcelle) : un en nombre de pieds (unité "plants"), un en poids (unité kg/g) — pas de nouveau champ, réutilisation de la structure `quantite` + `unite` déjà existante
- [ ] CA4 : Le stock de la culture continue d'être déduit uniquement à partir de l'événement en nombre de pieds (comportement végétatif — récolte destructive — inchangé)
- [ ] CA5 : Le poids récolté (second événement) est cumulé dans le rendement total de la culture, au même titre que pour les cultures reproductrices
- [ ] CA6 : Garde-fou impératif — le calcul du stock de plants ne doit jamais prendre en compte les événements `recolte` exprimés en poids (kg/g), uniquement ceux exprimés en nombre de pieds, pour éviter une double déduction
- [ ] CA7 : `/stats <culture>` (Telegram) et le détail par variété affichent ce rendement cumulé pour une culture végétative ayant des récoltes pesées
- [ ] CA8 : Le graphique "Rendements" du dashboard (timeline mensuelle par culture) inclut désormais aussi les cultures végétatives pesées, pas seulement les reproductrices
- [ ] CA9 : Si seul le nombre de pieds est dicté sans poids (cas actuel), un seul événement est créé comme aujourd'hui : aucune régression, aucun rendement enregistré
- [ ] CA10 : Si un poids est dicté sans nombre de pieds explicite, le bot demande une clarification plutôt que de déduire le stock à l'aveugle

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (bot Telegram) + analyse (stats) + consultation (dashboard frontend)
- Migration BDD requise : **non** — la double entrée (pieds + poids) réutilise la structure actuelle `quantite`/`unite` de la table `evenements`, pas de nouveau champ
- Point d'attention pour le Developer : les deux événements liés à une même action de récolte doivent rester identifiables comme un seul geste métier pour l'utilisateur (ex : affichage groupé dans l'historique), même s'ils sont stockés comme deux lignes distinctes
- Dépendances :
  - Modélisation du type d'organe récolté (distinction végétatif / reproducteur)
  - Logique actuelle de déduction de stock pour le végétatif (récolte = perte de plant)
  - US-028 (graphiques évolution récoltes frontend) — le graphique "Rendements" devra intégrer cette nouvelle donnée pour les cultures végétatives

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le jardinier a planté des betteraves (culture végétative)
When il dicte "récolte 2 betteraves 250 grammes"
Then deux événements recolte sont enregistrés : 2 (unité "plants") et 250 (unité "g")
And le stock de betteraves est réduit de 2 plants, à partir de l'événement en pieds uniquement
And le rendement total de la culture betterave augmente de 250g, à partir de l'événement en poids
And "/stats betterave" affiche le rendement cumulé en plus du nombre de pieds restants
```

**Labels GitHub :** `us`, `sprint-backlog`, `recolte`, `stats`, `bot`
