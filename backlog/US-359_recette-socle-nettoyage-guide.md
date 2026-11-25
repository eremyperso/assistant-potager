**ID :** US-359
**Titre :** Recetter les sept vues du socle, retirer les composants remplacés et mettre à jour le guide et l'aide
**Épic :** ÉPIC 21 — Socle commun des vues

**Story :**
En tant que jardinier
Je veux une application dont chaque écran a été vérifié contre la maquette, et un guide qui décrit la navigation que j'ai sous les yeux
Afin de ne trouver ni reste de l'ancienne interface ni aide qui parle d'un bouton disparu

**Contexte fonctionnel :**
Vague 3 de l'ÉPIC 21. Clôture de l'épic. La recette visuelle suit `frontend/CLAUDE.md` (chrome-devtools) et la méthode isolée du projet (base SQLite jetable, API sur 8011, Vite sur 5173). Les serveurs 3000/8000 de l'utilisateur ne sont pas touchés.

**Critères d'acceptance :**
- [ ] CA1 : Chaque écran de la maquette est capturé à **375, 768 et 1440 px** et comparé à la maquette : Tableau de bord, Plan (règle des temps ouverte), Cultures · au potager, Cultures · catalogue, Pépinière · Parcours, Pépinière · Semer, Pépinière · Lots, fiche du lot, Stocks, Récoltes par saison, Journal, Fiche commune, Gaston via Noter, Ajouter une culture. Les écarts restants sont listés dans `docs/EPIC 21 - SOCLE COMMUN DES VUES/03_RECETTE.md`, avec leur capture
- [ ] CA2 : Les mêmes écrans sont capturés **en mode sombre** à 375 et 1440 px et comparés à l'écran « Mode sombre » de la maquette (D12). Les couleurs d'étape sont identiques en clair et en sombre
- [ ] CA3 : Les composants remplacés sont supprimés, avec leurs imports et leurs tests devenus sans objet : `BoutonCompagnon`, `DateRefPicker`, `BarreActivitePlan`, `MonthStrip` (si plus utilisé), l'ancien style de `CarteProposition`, `ModalPersonnaliserDashboard` et `useDashboardWidgets` (D11, si US-354 ne l'a pas fait), et les aperçus `_…Preview` d'écrans disparus. `npm run build` passe, et la suite front passe au moins aussi bien qu'à HEAD
- [ ] CA4 : Le **guide utilisateur** (les deux copies) décrit l'anatomie d'une page, Noter seule porte, la règle des temps par « Aujourd'hui », le menu ⋯ (exports), la fiche commune Suivi / Référence, le catalogue et « Ajouter à mon potager », Récoltes par saison, les trois onglets de la Pépinière et le mode sombre. Les mentions du médaillon, de « Parcourir », des exports en ligne et de la personnalisation du tableau de bord sont retirées
- [ ] CA5 : L'**aide de la vue** (menu ⋯ › Aide de la vue) ouvre la section du guide propre à chaque vue
- [ ] CA6 : La fiche `doc_app` du corpus reprend les mêmes changements. Le corpus est réingéré en dev et en test, et deux questions de mesure le vérifient (« où sont les exports ? », « comment ajouter une culture du catalogue ? »). Il n'y a pas de mesure sur le vrai modèle sans accord
- [ ] CA7 : `PATCH_NOTES.md` et `VERSION` sont mis à jour une seule fois pour l'épic (sauf invocation « sans notes »)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-352 à US-358 et US-360
- Modèle / effort conseillé : **Sonnet 5.5, `low`** — recette, suppression et documentation ; Haiku 5.5 suffirait pour CA4-CA7 seuls ; ni Opus ni Fable ne sont requis

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given l'épic 21 est livré
When le jardinier cherche les exports CSV de ses stocks
Then il les trouve dans le menu ⋯ de la barre d'outils
And le guide le dit au même endroit

When il demande au compagnon "comment j'ajoute une culture qui n'est pas dans mon potager ?"
Then la réponse cite Cultures › Catalogue › Ajouter à mon potager
And elle ne mentionne ni le médaillon ni le bouton "Parcourir"
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `recette`, `documentation`, `socle`
