
---

## BESOIN BRUT

Créer une interface web de visualisation des données techniques du potager, permettant à l'admin de consulter l'état du jardin, l'historique des actions et les indicateurs clés issus de l'application Assistant Potager.

---

## CONTRAINTES TECHNIQUES

| Contrainte            | Détail                                                                 |
|-----------------------|------------------------------------------------------------------------|
| **Infrastructure**    | VPS Scaleway — 1 Go RAM, plusieurs services actifs (FastAPI, PostgreSQL, uvicorn) |
| **Déploiement front** | Netlify (build statique) ou VPS selon complexité                       |
| **Performance**       | Pas de critère strict — privilégier la stabilité sur la rapidité       |
| **Appels API**        | Via endpoints FastAPI existants — pas d'accès direct à la BDD côté front |
| **Auth**              | Simple (token statique ou session) — admin seul, pas de gestion de rôles |

---

## CONVENTIONS UI/UX (non négociables)

Tout développement front doit respecter ces choix de librairies. Aucun composant custom n'est autorisé si une librairie couvre le besoin.

| Rôle              | Librairie / Outil     | Remarque                                      |
|-------------------|-----------------------|-----------------------------------------------|
| Design system     | **Tailwind CSS**      | Classes utilitaires uniquement, pas de CSS custom |
| Composants UI     | **Shadcn/UI**         | Badge, Alert, DataTable, Progress, Toast      |
| Graphiques        | **Recharts**          | AreaChart, LineChart, BarChart, RadialBar     |
| Icônes            | **Lucide React**      | Cohérence visuelle garantie                   |
| Tables filtrables | **TanStack Table**    | Via composant DataTable Shadcn                |

### Standard de rendu visuel

- Références : style **Vercel Analytics** (densité d'info, lisibilité) et **Tremor.so** (composants data-centric)
- Palette : tons verts et bruns cohérents avec le domaine potager
- Responsive : **mobile-first** — 1 colonne < 768px, 2-3 colonnes desktop
- États obligatoires sur chaque composant : `loading skeleton`, `erreur`, `données vides`
- Dark/light mode : supporté dès la phase 1

---

## CATALOGUE COMPOSANTS PAR TYPE DE DONNÉE

Le PO doit s'appuyer sur ce catalogue pour renseigner la section "Composant UI ciblé" de chaque US.

| Type de donnée            | Librairie   | Composant recommandé               | Exemple d'usage potager                     |
|---------------------------|-------------|------------------------------------|---------------------------------------------|
| Évolution temporelle      | Recharts    | `<AreaChart />` / `<LineChart />`  | Température serre, arrosage cumulé          |
| Comparaison par catégorie | Recharts    | `<BarChart />`                     | Rendement par variété, semis vs récoltes    |
| Indicateur d'état courant | Shadcn/UI   | `<Badge />` + `<Progress />`       | Humidité sol, stade de croissance           |
| Inventaire / tableau      | Shadcn/UI   | `<DataTable />` (TanStack)         | Liste semis, planning récoltes              |
| Alerte / seuil critique   | Shadcn/UI   | `<Alert />` + `<Toast />`          | Gel prévu, stock critique, seuil arrosage   |
| Taux / proportion         | Recharts    | `<RadialBarChart />`               | Taux de germination, taux de réussite semis |

---

## QUESTIONS DE CADRAGE — À TRAITER AVANT GÉNÉRATION DES US

Le PO doit répondre aux questions suivantes et intégrer les réponses dans le contexte de chaque US produite.

1. **Données prioritaires** : parmi température serre, historique arrosage, stocks semis, stades de croissance, alertes — lesquelles constituent le MVP ?
2. **Fréquence de mise à jour** : rafraîchissement manuel (bouton), automatique (polling toutes X minutes), ou temps réel (WebSocket) ?
3. **Appareil principal** : l'admin consulte-t-il principalement sur desktop ou mobile (téléphone au jardin) ?
4. **Horizon temporel des graphiques** : 7 jours, 30 jours, saison complète — quelle granularité par défaut ?
5. **Durée de vie** : MVP rapide à valider en 1 sprint, ou socle évolutif prévu sur plusieurs mois ?

---

## TEMPLATE US OBLIGATOIRE

Chaque US générée doit strictement respecter cette structure.

```markdown
# US : [Titre court]

**En tant que** : Admin
**Je veux** : [action observable]
**Afin que** : [valeur métier ou gain concret]

## Critères d'acceptation
- [ ] ...
- [ ] États gérés : loading skeleton, erreur API, données vides

## Composant UI ciblé
| Élément       | Librairie   | Composant exact         | Props / variante        |
|---------------|-------------|-------------------------|-------------------------|
| [ex: graphe]  | Recharts    | `<AreaChart />`         | données : endpoint /... |
| [ex: badge]   | Shadcn/UI   | `<Badge variant="...">' | vert=ok, rouge=alerte   |

## Données affichées
- **Source** : endpoint FastAPI `/api/...` (à créer si inexistant)
- **Format** : JSON `{ clé: valeur }`
- **Fréquence refresh** : [manuel / polling Xmin / WebSocket]

## Risques / Notes techniques
- [impact RAM VPS si polling fréquent, etc.]
```