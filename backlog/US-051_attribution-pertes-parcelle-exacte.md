**ID :** US-051
**Titre :** Attribuer les pertes et récoltes de plants à leur parcelle exacte dans le plan d'occupation

**Story :**
En tant que jardinier
Je veux que la perte ou la récolte d'une culture ne réduise le nombre de plants affiché que sur la parcelle réellement concernée
Afin de voir dans le plan d'occupation du dashboard un stock par parcelle fiable, cohérent avec le stock global affiché par `/stats`

**Critères d'acceptance :**
- [ ] CA1 : Quand un événement `perte` (ou `récolte` en pièces, culture végétative) précise une `parcelle_id`, seule cette parcelle voit son nombre de plants diminuer dans le plan d'occupation — les autres parcelles portant la même culture/variété ne sont pas affectées.
- [ ] CA2 : Quand un événement `perte`/`récolte` ne précise aucune parcelle, le comportement de secours actuel est conservé : répartition proportionnelle du montant entre toutes les parcelles plantées de cette culture/variété (pour ne jamais faire disparaître la perte du calcul).
- [ ] CA3 : Le total de plants affiché (toutes parcelles confondues) dans le plan d'occupation reste toujours égal au stock global calculé par `/stats` Telegram, quel que soit le nombre de parcelles portant la même culture/variété.
- [ ] CA4 : Une variété plantée sur plusieurs parcelles, avec une perte localisée sur une seule d'entre elles, ne fait plus disparaître à tort le stock des autres parcelles (cas constaté en prod v3.14 sur le basilic, corrigé en urgence par une répartition proportionnelle temporaire dans US précédent — cette US remplace cette approximation par une attribution exacte).
- [ ] CA5 : Un test de non-régression couvre explicitement ce scénario : 2 parcelles avec la même variété, perte localisée sur une seule parcelle via `parcelle_id`, vérification que seule cette parcelle est impactée.
- [ ] CA6 : Aucune régression sur les scénarios existants (perte avec variété unique sur une seule parcelle, perte sans variété, perte sans parcelle précisée).

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (plan d'occupation des parcelles, dashboard)
- Migration BDD requise : non — `Evenement.parcelle_id` existe déjà pour les événements `perte` et `recolte`
- Dépendances : correctif d'urgence déjà livré (répartition proportionnelle des pertes/récoltes "avec variété", v3.14.1 sur `main` / v3.25.1 sur `dev`) — cette US en est le raffinement définitif, remplace la logique de prorata par une attribution directe quand la parcelle est connue
- Fichier concerné (pour référence fonctionnelle uniquement) : logique de calcul du plan d'occupation par parcelle

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario : Perte localisée sur une seule parcelle parmi plusieurs portant la même variété
  Given deux parcelles "A" et "B" plantées chacune de 10 plants de basilic "grand vert"
  And une perte de 10 plants de basilic "grand vert" enregistrée avec la parcelle "A"
  When je consulte le plan d'occupation des parcelles
  Then la parcelle "A" affiche 0 plant de basilic
  And la parcelle "B" affiche toujours 10 plants de basilic
  And le total (0 + 10) correspond au stock global renvoyé par /stats

Scénario : Perte sans parcelle précisée (comportement de secours)
  Given deux parcelles "A" et "B" plantées chacune de 10 plants de basilic "grand vert"
  And une perte de 2 plants de basilic "grand vert" enregistrée sans parcelle précisée
  When je consulte le plan d'occupation des parcelles
  Then la perte est répartie proportionnellement entre "A" et "B"
  And le total affiché sur les deux parcelles reste égal à 18
```

**Labels GitHub :** `us`, `bug`, `stock`, `dashboard`
