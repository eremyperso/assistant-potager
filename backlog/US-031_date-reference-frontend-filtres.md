**ID :** US-031  
**Titre :** Sélecteur de date de référence global + filtres culture harmonisés

**Story :**  
En tant que jardinier  
Je veux pouvoir choisir une date de référence dans chaque écran de l'application  
Afin de consulter l'état de mon potager à un instant passé, avec le filtre persistant entre les écrans pour ne pas avoir à le resélectionner

---

**Contexte métier :**

La date de référence est un état **global** de l'application : si l'utilisateur choisit "01/05/2025" sur l'écran Plan, ce même filtre doit être actif quand il navigue vers Stocks, Pépinière ou Historique. Il ne doit pas avoir à le resaisir.

La date est contrôlée depuis **chaque écran** (sélecteur dans le header de chaque vue), mais modifie la même valeur globale.

Les filtres **culture** sont quant à eux **locaux par écran** — indépendants entre les vues.

---

**Critères d'acceptance :**

**État global — date de référence :**
- [ ] CA1 : Un `AppContext` React expose `dateRef: Date | null` et `setDateRef(date)` à toute l'application
- [ ] CA2 : `dateRef` est persisté en `localStorage` (clé `potager_date_ref`) — survit à un rechargement de page
- [ ] CA3 : Si `dateRef` est `null` ou absente de localStorage → date du jour utilisée pour tous les appels API
- [ ] CA4 : Toute navigation entre onglets (Plan → Stocks → Pépinière → Historique) conserve la valeur de `dateRef` — aucune réinitialisation

**Composant DateRefPicker (réutilisé sur chaque vue) :**
- [ ] CA5 : Un composant `<DateRefPicker />` est créé et placé dans le **header de chaque vue** (Plan, Stocks, Pépinière, Historique)
- [ ] CA6 : Le composant affiche un `<Button>` compact avec l'icône `Calendar` (Lucide) + la date formatée `DD/MM/YYYY` ou le label `"Aujourd'hui"` si `dateRef === null`
- [ ] CA7 : Clic sur le bouton → `<Popover />` Shadcn contenant un `<Calendar />` Shadcn pour la sélection
- [ ] CA8 : Un bouton `"Aujourd'hui"` dans le popover réinitialise `dateRef` à `null` (= date du jour, label revient à `"Aujourd'hui"`)
- [ ] CA9 : Les dates futures sont désactivées dans le calendrier (pas sélectionnables)
- [ ] CA10 : Quand `dateRef` pointe vers une date passée, le `<Button />` change de variante : fond **amber** (ou `secondary` teinte chaude) pour signaler visuellement qu'on n'est pas "en direct"
- [ ] CA11 : À chaque changement de `dateRef`, tous les écrans actifs rechargent leurs données (refetch API avec le nouveau paramètre `date_ref`)

**Intégration dans chaque vue :**
- [ ] CA12 : Vue **Plan** (`/plan?date_ref=...`) — `DateRefPicker` en haut + filtre culture local (champ `<Input />` texte, côté client)
- [ ] CA13 : Vue **Stocks** (`/stats?date_ref=...`) — `DateRefPicker` en haut + filtre culture local existant (CA5 de US-025) conservé
- [ ] CA14 : Vue **Pépinière** (`/godets?date_ref=...`) — `DateRefPicker` en haut + filtre culture local (champ `<Input />` texte, côté client)
- [ ] CA15 : Vue **Historique** (`/historique?date_ref=...`) — `DateRefPicker` en haut, affiche les 10 événements les plus récents **jusqu'à** `date_ref`
- [ ] CA16 : Vue **Stats** (graphiques) — `DateRefPicker` en haut, les graphiques d'évolution s'arrêtent à `date_ref`

**Filtres culture locaux (harmonisation) :**
- [ ] CA17 : Les vues Plan, Stocks et Pépinière disposent toutes d'un champ `<Input />` de recherche culture avec icône `Search` (Lucide) — même composant, même placement (sous le `DateRefPicker`, au-dessus de la liste)
- [ ] CA18 : Le filtre culture est côté client (pas d'appel API supplémentaire) — filtre les éléments déjà chargés
- [ ] CA19 : Le filtre culture est **remis à zéro** à chaque navigation vers une autre vue (non persisté) — comportement intentionnel

**États gérés :**
- [ ] CA20 : Pendant le rechargement après changement de date → skeleton visible sur la zone de contenu
- [ ] CA21 : Si l'API retourne une erreur avec le nouveau `date_ref` → composant `<ApiError />` avec bouton retry

---

**Composants UI ciblés :**

| Élément | Librairie | Composant exact | Props / variante |
|---|---|---|---|
| Sélecteur date | Shadcn/UI | `<Popover />` + `<Calendar />` | `mode="single"`, `disabled: date > today` |
| Bouton déclencheur | Shadcn/UI | `<Button />` | variante `outline` (aujourd'hui) / `secondary` teinte amber (passé) |
| Icône calendrier | Lucide | `Calendar` | Taille 16px inline dans le bouton |
| Filtre culture | Shadcn/UI | `<Input />` + Lucide `Search` | Placeholder "Filtrer par culture…" |
| Skeleton rechargement | Shadcn/UI | `<Skeleton />` | Hauteur de la zone de contenu active |

---

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : frontend React — `AppContext`, composant `DateRefPicker`, vues Plan/Stocks/Pépinière/Historique/Stats
- Migration BDD requise : **non**
- Dépendances : US-023 (socle), US-030 (endpoints backend acceptant `date_ref`), US-024, US-025, US-026, US-027, US-028
- Le filtre culture de US-025 (CA5 — TanStack Table) est **conservé et harmonisé** visuellement avec les filtres des autres vues — pas de régression
- `dateRef = null` → paramètre `date_ref` absent des appels API (comportement défaut backend = aujourd'hui)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scenario: Sélection date passée depuis l'écran Plan
  Given l'utilisateur est sur la vue Plan avec dateRef = null ("Aujourd'hui")
  When l'utilisateur clique sur le DateRefPicker et sélectionne "01/05/2025"
  Then le bouton affiche "01/05/2025" avec fond amber
  And l'API est appelée avec ?date_ref=2025-05-01
  And les parcelles affichées reflètent l'état au 01/05

Scenario: Navigation vers Stocks — date persistée
  Given dateRef = 2025-05-01 définie sur la vue Plan
  When l'utilisateur navigue vers l'onglet Stocks
  Then le DateRefPicker de la vue Stocks affiche "01/05/2025" (fond amber)
  And l'API /stats est appelée avec ?date_ref=2025-05-01

Scenario: Réinitialisation à aujourd'hui
  Given dateRef = 2025-05-01 active sur la vue Stocks
  When l'utilisateur ouvre le DateRefPicker et clique "Aujourd'hui"
  Then dateRef = null, le bouton redevient "Aujourd'hui" (variante outline)
  And localStorage potager_date_ref est effacé
  And l'API est rappelée sans paramètre date_ref

Scenario: Rechargement de page — persistance
  Given dateRef = 2025-05-01 en localStorage
  When l'utilisateur recharge la page
  Then dateRef est restauré à 2025-05-01
  And tous les écrans chargent leurs données avec cette date

Scenario: Filtre culture local indépendant
  Given la vue Stocks avec un filtre culture "tomate" actif
  When l'utilisateur navigue vers Pépinière puis revient sur Stocks
  Then le filtre culture de Stocks est réinitialisé (vide)
  And le filtre culture de Pépinière est indépendant (vide ou saisi séparément)
```

**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `date-reference`, `filtres`, `ux`
