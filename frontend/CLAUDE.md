# frontend — dashboard React (Vite)

```powershell
cd frontend
npm install        # une seule fois / après changement de dépendances
npm run dev        # http://localhost:3000, hot reload, API via .env.local (VITE_API_URL)
npm run build      # génère frontend/dist, servi par l'API FastAPI (app/api/main.py)
```

`app/api/main.py` sert `frontend/dist` en priorité (repli sur `static/` si le
build est absent) : toute modification de l'UI exige `npm run build` pour être
visible via l'API ; `npm run dev` suffit pour itérer.

## Responsive — partage breakpoints Tailwind / container queries (NON NÉGOCIABLE)

Décidé lors de la refonte UI 2026 (`docs/ANALYSE_REFONTE_UI_WEB_2026.md`) :

- **Breakpoints Tailwind (`md:`, `lg:`…)** : réservés à la structure de page
  globale — afficher/masquer la bottom tab bar, basculer entre layout mobile et
  layout desktop avec sidebar. Seule couche qui répond à « quelle est la taille
  de l'écran ? ».
- **Container queries (`@container`)** : règle par défaut pour tout composant
  réutilisable (`ParcelleCard`, `ObservationIcon`, panneaux, listes…). Un
  composant destiné à plus d'un contexte de layout naît avec
  `container-type: inline-size` sur son wrapper, sans discussion au cas par cas.

## Validation visuelle

Toute US à impact visuel se vérifie via chrome-devtools à 375 px au minimum
avant d'être déclarée terminée (auto-contrôle ; la validation finale est du QA).
Maquettes de référence : projet Claude Design (voir mémoire du projet).
