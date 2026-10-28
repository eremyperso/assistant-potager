**ID :** US-265
**Titre :** Tenir le carnet du compagnon
**Épic :** ÉPIC 14 — Compagnon actif : profil, mémoire et initiative *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux que le compagnon retienne mes habitudes et mes objectifs quand je les lui dis, et que je puisse voir, corriger ou effacer ce qu'il sait
Afin qu'il ne me propose plus ce qui ne me correspond pas, en gardant la main sur mes données

**Contexte fonctionnel :**
Lot 4 du cadrage (§1.6, §2, profil partie 2). Le carnet retient ce que le jardinier a **dit au compagnon** de lui-même ; il est distinct de la mémoire du potager d'US-141 (notes). Il est personnel, non partagé entre membres (D9).

**Critères d'acceptance :**
- [ ] CA1 : L'outil `retenir(fait)` est classé en écriture : il produit une proposition (« Je retiens ça : tu arroses le soir. [OK, retiens-le] [Non] »), jamais une écriture d'office (R9).
- [ ] CA2 : Un fait fait 200 caractères au plus ; un profil en porte 30 au plus, avec sa date et l'échange d'origine.
- [ ] CA3 : `/carnet` (bot) et l'écran « Mon compagnon » (réglages de la PWA) listent les faits et permettent de modifier, d'oublier un fait ou de tout oublier.
- [ ] CA4 : Les faits sont injectés en partie variable, balisés comme données ; un fait contenant une consigne est sans effet (R10, test d'injection).
- [ ] CA5 : Le niveau (`debutant` / `confirme`) est déduit de l'activité puis **proposé** au jardinier (D6) ; les objectifs de saison (3 au plus) sont réglables.
- [ ] CA6 : La fiche RGPD (`docs/RGPD/`) mentionne le carnet : droit d'accès, d'effacement, absence de catégorie sensible demandée.
- [ ] CA7 : Mesure du lot 4 : 0 fait écrit sans confirmation ; injection sans effet.
- [ ] CA8 : L'écran « Mon compagnon » respecte les container queries (`frontend/CLAUDE.md`) et le rendu à 375px / 768px / desktop.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, consultation (PWA)
- Migration BDD requise : oui (table des faits, `potager_id` + RLS ; colonnes niveau et objectifs du profil)
- Dépendances : US-258, US-259
- Production conseillée : **Sonnet 5.5, effort `medium`** — CRUD confirmé sur un modèle de proposition déjà en place, plus un écran de réglages.

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given un jardinier sans fait au carnet
When il écrit "j'arrose toujours le soir, jamais le matin"
Then le compagnon propose de retenir "tu arroses le soir"
And rien n'est écrit tant qu'il n'a pas cliqué [OK, retiens-le]

When il demande /carnet puis clique [Tout oublier]
Then le carnet est vide
```

**Labels GitHub :** `us`, `compagnon`, `profil`, `rgpd`
