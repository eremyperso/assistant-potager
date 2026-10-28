**ID :** US-271
**Titre :** Parler au compagnon depuis la PWA
**Épic :** ÉPIC 15 — Compagnon dans la PWA *(numéro à valider, voir `docs/EPIC - COMPAGNON CONVERSATIONNEL/CADRAGE_COMPAGNON_ACTIF.md`)*

**Story :**
En tant que jardinier
Je veux ouvrir un panneau de conversation depuis n'importe quel écran du portail et y confirmer ce que le compagnon me propose
Afin de noter un geste ou poser une question sans quitter le portail

**Contexte fonctionnel :**
Lot 6 du cadrage (§4.1, D3 : levée d'A16). Aujourd'hui, la PWA dépose un geste préparé dans la file et seul Telegram confirme.

**Critères d'acceptance :**
- [ ] CA1 : Un bouton flottant ouvre un panneau de conversation, avec les modes Normal et Support.
- [ ] CA2 : Les propositions s'affichent en cartes avec [Confirmer] [Corriger] [Abandonner] ; un geste compris se **confirme dans la PWA**.
- [ ] CA3 : Les messages spontanés du compagnon sont rangés dans le panneau.
- [ ] CA4 : Les erreurs (réseau, proposition expirée, déjà traitée) sont affichées en clair.
- [ ] CA5 : Le panneau utilise les container queries et la page les breakpoints Tailwind (`frontend/CLAUDE.md`).
- [ ] CA6 : Le rendu correspond visuellement à la maquette de référence à 375px / 768px / desktop.
- [ ] CA7 : La fiche de `data/connaissance/doc_app/` sur le compagnon décrit le panneau.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation, enregistrement (PWA)
- Migration BDD requise : non
- Dépendances : US-270 ; maquette du panneau à produire avant le développement
- Production conseillée : **Sonnet 5.5, effort `high`** — frontend React sans risque de données (tout passe par l'API) ; l'effort élevé sert au rendu multi-largeur et aux états de carte.

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given le jardinier est sur la vue Plan de la PWA
When il ouvre le panneau et écrit "j'ai arrosé la serre"
Then une carte de proposition s'affiche
When il clique [Confirmer]
Then la carte affiche "✅ Confirmé" et l'arrosage apparaît dans le journal
```

**Labels GitHub :** `us`, `compagnon`, `pwa`, `frontend`
