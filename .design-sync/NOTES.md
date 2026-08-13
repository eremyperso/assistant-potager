# Notes de sync — Assistant Potager UI

## Contexte du repo

- Le design system n'est pas un package séparé : c'est `frontend/src/components/ui/`
  (barrel `index.js`), à l'intérieur de l'app Vite `assistant-potager-dashboard`.
  Pas de build dédié, pas de `.d.ts` — JS/JSX pur avec JSDoc.
- `--entry` pointe directement sur `frontend/src/components/ui/index.js` (pas de
  dist). `cfg.componentSrcMap` liste les 23 exports (dont les sous-composants
  `CardHead`, `PopItem`/`PopHead`/`PopSep`, `MonthStripLegend`) car sans `.d.ts`
  la découverte automatique par exports ne trouve rien — c'est le mécanisme
  documenté pour ce cas (`componentSrcMap` = knob d'inclusion explicite).
- `useGroups` (export nommé depuis `GroupHead.jsx`) est exclu automatiquement
  (pas PascalCase) — normal, ce n'est pas un composant.

## CSS compilé séparément (Tailwind CLI)

Le CSS n'est PAS pris dans `frontend/dist/` (hashé, dépend d'un build complet).
À la place :
```
cd frontend && npx tailwindcss -c tailwind.config.js -i src/index.css -o .ds-build/tailwind.css
```
`cfg.cssEntry = ".ds-build/tailwind.css"` (bounded à `PKG_DIR` = `frontend/`,
donc le fichier DOIT rester sous `frontend/`). `frontend/.gitignore` ignore
`.ds-build/`. **Regénérer ce fichier avant tout re-sync** si `tailwind.config.js`
ou les classes utilisées dans `src/**/*.{js,jsx}` ont changé — le build du
convertisseur ne le fait pas tout seul.

## Pas de Playwright installé — QA visuelle manuelle faite à la place

L'utilisateur a décliné l'installation de Playwright/Chromium (~200 Mo).
`package-validate.mjs` a tourné avec `--no-render-check`. En remplacement,
QA visuelle manuelle via les outils `mcp__chrome-devtools__*` (navigation +
screenshot + lecture console sur `http://127.0.0.1:<port>/components/general/<Name>/<Name>.html`,
servi par `node .ds-sync/storybook/http-serve.mjs ./ds-bundle`) sur les 23
composants. Résultat : 22/23 floor cards s'affichent proprement (certaines
vides faute de contenu réaliste, normal), un seul crash réel :

- **RoleSelect** : `options.find(...)` sur une prop `options` sans défaut →
  `TypeError` au montage sans props réalistes. Fixé via une preview authored
  (`.design-sync/previews/RoleSelect.tsx`, 2 exports avec les vraies options
  `ROLES_INVITABLES` portées de `GestionMembres.jsx`).

**Ce run n'a PAS de vérification automatisée (`[RENDER]` gate) sur les 22
autres composants** — seulement une QA manuelle ponctuelle. Un futur re-sync
avec Playwright installé pourrait révéler d'autres cas comme RoleSelect
(prop sans défaut qui casse au montage) parmi les composants non encore
authored.

## Périmètre choisi

Scope volontairement minimal (décision utilisateur) : seul RoleSelect a une
preview authored ; les 22 autres composants restent en floor card. C'est un
état honnête et non un échec — authorable composant par composant à tout
futur re-sync, sans perdre RoleSelect (`grades`/preview carried forward).

## Re-sync risks

- `.ds-build/tailwind.css` est un artefact généré localement, non committé —
  s'il n'existe pas au moment du re-sync, `cssEntry` sera introuvable
  (`! cssEntry: … not found — skipped`) et le bundle perdra tout son style.
  Toujours régénérer AVANT `package-build.mjs` (commande ci-dessus).
- Aucun render-check automatisé n'a jamais tourné sur ce repo — les 22 floor
  cards n'ont eu qu'une QA visuelle ponctuelle à la date de ce sync, pas une
  vérification reproductible. Installer Playwright au prochain re-sync pour
  avoir enfin le gate mécanique complet.
- `componentSrcMap` doit être mis à jour à la main si `components/ui/index.js`
  gagne ou perd un export (nouveau composant, renommage) — rien ne le
  détecte automatiquement puisqu'il n'y a pas de `.d.ts`.
