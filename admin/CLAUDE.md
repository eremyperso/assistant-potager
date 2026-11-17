# admin — PWA d'administration « Pilotage » (Vite + React)

Application **distincte** de celle des jardiniers (`frontend/`), réservée à `ADMIN_EMAIL`, installable
sur téléphone. Elle lit les routes `/admin/pilotage/...` (voir `docs/domaines/pilotage-llm.md`).

```powershell
cd admin
npm install        # une seule fois ; installer AUSSI frontend/ (sa config Tailwind est étendue ici)
npm run dev        # http://localhost:3001/pilotage/ — API via VITE_API_URL (défaut http://localhost:8001)
npm test           # node --test : formats, périodes, filtres, client, service worker, contrat de la vue
npm run build      # génère admin/dist, servi par l'API sous /pilotage/ (app/api/main.py)
```

Sans `admin/dist`, l'API ne sert rien sous `/pilotage/`. Toute modification exige `npm run build`
pour être visible via l'API ; `npm run dev` suffit pour itérer.

## Règles

- **Servie sous `/pilotage/` uniquement** : `vite.config.js` fixe `base: '/pilotage/'`, le manifeste
  (`public/manifest.webmanifest`) et le service worker (`public/sw.js`) n'ont pas d'autre portée. Les
  routes du jardinier et `/admin/...` ne changent pas.
- **Rien du jardinier n'est importé** : ni composant, ni vue, ni contexte de `frontend/src`. Sont
  *partagés* — par fichier, jamais copiés — la configuration Tailwind (`tailwind.config.js` étend
  `../frontend/tailwind.config.js`) et les jetons de l'identité visuelle (`src/index.css` importe
  `frontend/src/index.css` et `brand.css`). Le paquet du frontend ne contient, lui, aucun module d'ici
  (`tests/test_us311_pwa_administration.py`).
- **Connexion existante** : mêmes routes `/auth/...`, mêmes clés `localStorage` que le jardinier
  (`lib/client.js`). L'accès se décide sur `GET /auth/me` (champ `administrateur`) : un compte qui n'est
  pas l'administrateur voit « Accès réservé » et n'envoie **aucune** requête `/admin/...`.
- **Aucune réponse `/admin/...` en cache ni sur l'appareil** : le service worker ne met en cache que la
  coquille (`strategie()` de `sw.js`, testée) ; les dernières valeurs ne vivent qu'en mémoire
  (`hooks/useDonnees.js`). Hors ligne, l'application s'ouvre et dit qu'elle n'a pas de données.
- **Filtres dans l'adresse** : période, provenance, canal, modèle dans la requête (`lib/filtres.js`),
  vue dans le fragment (`#/consommation`). Un défaut n'apparaît pas dans l'adresse.
- **Chiffres** : toute arithmétique est côté API. `lib/consommation.js` ne fait que des écarts, des
  regroupements « Autres » (cinq séries, puis « Autres ») et la mise en forme française (`lib/format.js` :
  « 1 204 », « 68,4 % », « 0,042 € »).
- **Maquette de référence (US-318, Claude Design)** : projet « Pilotage - PWA administration » — coquille,
  vue Consommation, vue Seuils, 375 / 768 / 1280 px, clair et sombre. Navigation dans le bandeau dès 900 px
  (`nav:`), barre basse en dessous ; barre d'outils (période, filtres, « mis à jour à… », rafraîchir) sous le
  bandeau ; seuil de page `tab` (600 px) : 3 colonnes de chiffres et tableaux au lieu de cartes.
- **Jamais la couleur seule** : un écart défavorable porte une flèche et le mot « défavorable » ; une pastille
  d'alerte porte son nombre. Les séries sont des **alias** des teintes de l'application (`--serie-1..5` =
  bleu, ambre, vert, violet, sable ; `--serie-autres` = gris), même ordre dans la légende, l'empilement et
  le tableau ; au-delà de cinq, « Autres ». **Seul jeton ajouté à l'identité : `--brand-soft-strong`** (la part
  servie par le cache), dans `src/index.css`.
- **Responsive** : breakpoints Tailwind (`nav:`, 900 px) pour la page seulement ; seuil `tab:` (600 px) ; container queries
  (`@container`, `@lg:`) pour tout composant. Utilisable à 360 px, sans défilement horizontal.
- Tout `import.meta.env` vit dans `src/config.js` : les modules de `src/lib/` restent testables sous Node.
- Ajouter une vue : la déclarer dans `lib/navigation.js`, l'ajouter à `VUES_LIVREES` dans `App.jsx`. Les
  vues non livrées s'ouvrent sur `VueEnAttente`. Livrées : Consommation, Coût (US-313), Fiabilité (US-314),
  Dérives (US-315), Potagers et jardiniers (US-319), Seuils (US-316 : seule vue qui écrit — `client.modifier`, PATCH — et qui n'a ni période ni filtres). Une vue = `views/X.jsx` (chargement par `useDonnees` + `CadreVue`) + `lib/x.js` (mise en forme,
  testée) ; les composants de la maquette (`ChiffreCle`, `Graphique`, `TableauDonnees`, `CarteGraphique`,
  `GrilleChaleur`, `Segments`) ne prennent que des propriétés additionnelles, jamais de variante visuelle.
- Un tableau passe en cartes sous un seuil de **container query** qui dépend de son nombre de colonnes
  (`TableauDonnees`) : 8 colonnes ne tiennent pas à 768 px.

## Contrat avec l'API

`src/lib/fixtures/{consommation,cout,fiabilite,derives}_fixe.json` sont les réponses réelles des routes sur un jeu de données fixe.
`tests/test_us312_contrat_consommation.py` et `tests/test_us313_315_contrat_vues.py` vérifient que l'API les rend
à l'identique ; les `*.test.js` vérifient que l'écran en tire les mêmes chiffres. Après un changement voulu de
l'API : `REGENERER_FIXTURE_US312=1 pytest tests/test_us312_contrat_consommation.py` ou
`REGENERER_FIXTURE_US313_315=1 pytest tests/test_us313_315_contrat_vues.py`.

## Validation visuelle

Auto-contrôle à 375 / 768 / 1280 px avant de déclarer terminé (Chrome headless via CDP si l'extension
n'est pas connectée) ; la validation finale est du QA.
