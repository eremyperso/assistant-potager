**ID :** US-330
**Titre :** Ouvrir le détail d'une parcelle dans le plan
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux ouvrir une parcelle directement sur le plan — ce qui y pousse, ses caractéristiques, sa rotation, son entretien
Afin de ne plus passer par un onglet « Parcelles » séparé qui répète ce que le plan sait déjà

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Parcelle dans le Plan : fusionner la vue Parcelles ». Avis de la maquette : **oui, avec trois garde-fous** — une seule source pour la géométrie (US-326), garder une liste, un lien direct vers une parcelle.

**Navigation qui en découle :**
- Tuiles du Plan : **Plan** et **Rotation · à venir** — « Vue plan » et « Parcelles » fusionnent
- Bascule **« Plan | Liste »** dans la même vue : la liste sert à une parcelle non placée, à la recherche et aux lecteurs d'écran
- Le **panneau de droite suit la sélection** : rien → « Aujourd'hui » (US-328) ; une parcelle → **Parcelle** ; une culture → **Suivi** (US-322), avec un retour « ‹ Planche centrale » vers sa parcelle
- La parcelle choisie est **cerclée** sur le plan
- Mobile : « Détail » sur la carte d'une parcelle ouvre sa **feuille plein écran** ; toucher un rang y ouvre la culture par-dessus

**Le détail d'une parcelle :**

| # | Bloc | Contenu |
|---|---|---|
| D1 | En-tête | pictogramme, nom, « Planche · 60 m² · 8 rangs » (ou « Pépinière froide · 3 lots ») |
| D2 | Géométrie | « Sur le plan : 12 × 5 m, rangs dans la longueur », bouton **« Ajuster sur le plan »** (ouvre l'éditeur, US-333, ordinateur seulement) |
| D3 | Onglet **En place** | « 7 rangs occupés sur 8 · 1 à confirmer », puis une ligne par culture (même ligne que la liste mobile, US-329) et les rangs libres ; pour une pépinière, onglet **Lots** vers « Ma pépinière » |
| D4 | Onglet **Caractéristiques** | US-331 |
| D5 | Onglet **Rotation** | années et familles, conseil de l'année suivante — contenu d'US-231 ; « Vue détaillée dans la tuile Rotation (à venir) » |
| D6 | Onglet **Entretien** | journal du sol d'US-232, et un bouton **« Noter »** qui ouvre Gaston sur la parcelle (US-324) |

**Critères d'acceptance :**
- [ ] CA1 : L'écran Plan n'a plus que les tuiles « Plan » et « Rotation · à venir » ; l'ancien sous-onglet « Parcelles » n'existe plus, et `frontend/src/navigation.js` le dit
- [ ] CA2 : Toucher le nom d'une parcelle, « Voir la parcelle » depuis un suivi, ou « Détail » sur mobile ouvre D1 à D6
- [ ] CA3 : Le contenu des onglets Rotation et Entretien réutilise les composants d'US-231 et d'US-232, sans second dessin
- [ ] CA4 : La bascule « Plan | Liste » rend la même sélection dans les deux modes ; la liste inclut les parcelles non placées
- [ ] CA5 : **Lien direct** : une adresse du type `/?vue=plan&parcelle=12` (US-195) ouvre le plan avec ce détail ; les anciens liens vers l'onglet Parcelles (Cultures, Stocks, Gaston, fiche lot « où les mettre ») y sont redirigés
- [ ] CA6 : Retour à l'état exact (US-195 / CA8) : onglet de détail, mode Plan ou Liste, sélection
- [ ] CA7 : La fiche `parcelles-et-plan.md` et le guide sont réécrits ; corpus vert ; la régression (disparition de l'onglet Parcelles) est annoncée dans les patch notes
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence à 375 px / 768 px / desktop ; vérification chrome-devtools

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA)
- Migration BDD requise : non
- Dépendances : **US-327** (plan), **US-322** (suivi) ; US-229 à US-232 (fiche parcelle, livrées), US-195 (liens, livrée)
- Remplace le rendu d'US-222 (onglet Parcelles) ; `views/Plan.jsx` est démonté, ses composants Rotation / Sol / Caractéristiques sont repris
- Modèle / effort conseillé : Sonnet 5.5, `high` — remplacement d'un écran livré, redirections de liens, état de navigation

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Ouvrir une parcelle depuis le plan
  Given je suis sur le Plan, sur ordinateur
  When je touche le nom "Planche centrale"
  Then elle est cerclée sur le plan
  And le panneau de droite affiche son onglet "En place" : 7 rangs occupés sur 8

Scénario: Revenir d'une culture à sa parcelle
  Given le détail de la planche centrale est ouvert
  When je touche le chou de Bruxelles
  Then son suivi s'ouvre avec le retour "‹ Planche centrale"

Scénario: Un ancien lien vers l'onglet Parcelles
  Given un lien de la fiche lot pointe vers l'onglet Parcelles, planche haricots
  When je l'ouvre
  Then le Plan s'ouvre avec le détail de la planche haricots
```

**Labels GitHub :** `us`, `frontend`, `pwa`, `plan`, `navigation`
