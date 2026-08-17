# Analyse — Refonte de l'interface web (maquette Claude Design "potager 2026")

> Document de cadrage du chantier de refonte. Les §1 à §6 décrivent l'analyse et les
> arbitrages produit ; le **§7 tient à jour le découpage en lots et la répartition des US**
> (rédigées via `.github/agents/Personna PO.agent.md`, implémentées via
> `.github/agents/Orchestrateur-US.agent.md`).
>
> **Dernière mise à jour (15/08/2026)** : lots A (US-052, US-053), A bis (US-054,
> US-055) et A ter (US-056, US-057) implémentés. **Le Lot B est en cours** : sur ses US,
> **US-059 (socle), US-065 (pépinière par lot), US-061 (écran Pépinière) et US-060 (écran
> Plan) sont livrées**, ainsi qu'**US-066** (saisie Telegram, hors lot) ; restent **US-072 et
> US-073 (Stocks, cf. ci-dessous), US-063 (Journal), US-067 (famille botanique) et US-064
> (clôture)** — voir §7.1 et §7.2 pour le détail, §7.3 pour le découpage et §7.4 pour la
> dette d'alias restante (recomptée après les livraisons). Le §5.9 documente les écarts
> assumés entre `web-screens.jsx` et l'écran Pépinière livré, ainsi que la dette de famille
> botanique qu'il ouvre et que **US-067** vient solder ; le §5.10 fait de même pour l'écran
> Plan et la dette de **calendrier cultural** qu'il ouvre, soldée par l'`EPIC_CALENDRIER_CULTURAL`
> (US-068 à US-070). Le §5.6 documente les écarts assumés entre la maquette
> `web-account.jsx` et le menu Compte livré, le §5.7 ceux entre `login-screens.jsx` et
> l'écran de connexion/inscription livré (US-056/US-057 implémentées sans QA dédiée pour
> l'instant — vérification à chaud). Un lot **H — Onboarding « premier potager »** (§5.8,
> US-058) a été ajouté à partir du module `onboarding-screens.jsx`, mais **volontairement
> non prioritaire** (§7.1) : sa fonctionnalité complète dépend des lots C et E — au
> 15/08/2026, aucun des deux n'était encore cadré (voir la révision du 17/08/2026 ci-dessous
> pour l'avancement du Lot C depuis).
>
> **Révision du 15/08/2026 — l'écran Stocks devient l'écran transverse unique des
> cultures.** Une maquette figée (« gel » du 15/08/2026, fichier faisant foi `Potager -
> Application Web - FIGE 2026-08-15.html`) a été produite spécifiquement pour l'écran
> Stocks, à partir du brief `docs/BRIEF_REFONTE_STOCKS_TRANSVERSE.md`. Elle fusionne les
> trois sections aujourd'hui séparées (au potager / semis pleine terre / pépinière) en une
> seule liste groupée par famille botanique, et absorbe l'ambition de l'écran Cultures
> transverse du Lot E. Conséquence : **US-062 et US-071 deviennent caduques**, remplacées
> par **US-072** (données) et **US-073** (écran) — détail au §5.11.
>
> **Révision du 17/08/2026 — le Lot C sort de l'état « à cadrer », est intégralement livré,
> et reçoit un premier enrichissement (US-078).** Quatre US composent le lot : **US-074**
> (recherche de ville unifiée + localisation du potager) et **US-075** (météo web
> personnalisée) sont **implémentées** ; **US-076** (widget météo du Tableau de bord) et
> **US-077** (personnalisation des widgets affichés) le sont également, dans la foulée —
> détail au §5.2 bis, §5.2 ter et §7.1/§7.2. US-074/US-075 ont été menées **sans les étapes
> QA et Patch Notes Writer de l'Orchestrateur** (demande explicite) : le code et ses tests
> pytest sont livrés, mais aucune QA dédiée ne les a encore relues. US-076/US-077 (purement
> frontend) sont, elles, passées par l'étape QA de l'Orchestrateur — **verdict GO** (rapport
> visuel 375/768/1280, dont les états localisation manquante et erreur API ; pas de test
> pytest artificiel pour un changement sans logique serveur).
>
> **US-078** (lever/coucher du soleil, libellés humidité/vent, conseil potager du jour avec
> troncature/dépliage) enrichit ensuite la carte météo déjà livrée par US-076 — cycle complet
> PO → Developer → QA → Documentation cette fois, **verdict QA GO** lui aussi (mêmes
> résolutions, dont un conseil du jour simulé long pour valider la troncature et le dépliage).
> C'est cette exécution qui déclenche enfin l'étape Patch Notes Writer, différée jusqu'ici :
> `PATCH_NOTES.md`/`VERSION` sont mis à jour d'un coup pour l'ensemble des US non encore
> documentées du lot (**US-074 à US-078**, entrée `[v3.34.0]`), plutôt que d'ouvrir une entrée
> par US rétroactivement — US-074/US-075 restent malgré tout sans QA dédiée, point encore
> ouvert (cf. §7.2).

## 1. Source

Maquette importée depuis le projet Claude Design **"potager 2026"**
(`https://claude.ai/design/p/10f5afa7-58f8-4eb0-8dae-ca5834dfff59`), fichier focal
`Potager - Application Web - Proposition.html`, composé de 5 modules React (prototype
statique, données mockées) :

- `web-tokens.jsx` — thèmes clair/sombre, icônes SVG, jeux de données de démo
- `web-parts.jsx` — composants UI atomiques (Card, Btn, Stat, Badge, MonthStrip, TileNav…)
- `web-account.jsx` — **module ajouté depuis la première lecture** : sélecteur de potager
  (`PotagerMenu`), menu compte (`AccountMenu`), et les 3 modales d'administration
  (`ModalPotagers`, `ModalMembres`, `ModalTelegram`) — voir §5.6
- `web-shell.jsx` — coquille applicative (TopBar, PageHeader, BottomNav, GuideModal)
- `web-screens.jsx` — les 7 écrans (Dashboard, Stats, Plan, Cultures, Pépinière, Stocks, Journal)
- `login-screens.jsx` — **module ajouté depuis la deuxième lecture**, fichier focal
  `Potager - Connexion.html` : écran de connexion/inscription scindé (`LoginSplit`),
  formulaire (`AuthForm`, `Field`), connecteurs OAuth (`OAuthRow`) — voir §5.7
- `onboarding-screens.jsx` — **module ajouté depuis la troisième lecture**, fichier focal
  `Potager - Premier potager.html` : assistant de création du premier potager en 4 étapes
  (`Onboarding`, `StepPotager`, `StepParcelle`, `StepCultures`, `StepPret`), affiché juste
  après l'inscription — voir §5.8

> Cette version du document intègre une **itération de la maquette** postérieure à
> l'analyse initiale : ajout du module Compte/Potager ci-dessus, puis deux correctifs de
> responsive (bandeau mobile, retour à la ligne du bandeau d'info, débordement du sélecteur
> de potager). Le §5.6 et le §4 ont été mis à jour en conséquence ; le reste de l'analyse
> (§5.1 à §5.5, §7) reste valable.

C'est un **prototype de démonstration full web responsive** (mobile → desktop via
container queries), pas un export prêt à l'emploi : aucune donnée réelle, pas d'appels API,
pas de gestion multi-tenant/auth. Toute donnée du prototype (`WPARCELLES`, `WCULTURES`,
`WSTOCKS`, etc.) est fictive et à remplacer par les endpoints existants de `main.py`.

## 2. État actuel de l'interface (rappel factuel)

Frontend React/Vite (`frontend/src/`), **mobile-only**, sans librairie de routing (state
`activeTab` dans `App.jsx`).

- **Navigation à un seul niveau** : `TopBar.jsx` (titre + actions transverses, pas de nav)
  + `BottomNav.jsx` (5 onglets à plat : Plan, Stocks, Pépinière, Historique, Stats).
- **Pas de vue "Tableau de bord"** : l'app s'ouvre directement sur `Plan`.
- **Pas de vue "Cultures" transverse** : les cultures sont dispersées entre Plan (par
  parcelle), Stocks (par stock) et Pépinière (par lot en godet).
- **Aucun breakpoint desktop/tablette** : layout contraint en `max-w-md mx-auto`, zéro
  `sm:`/`md:`/`lg:` Tailwind utilisés dans tout `src/`.
- Design tokens existants : variables CSS (`--g-bg`, `--g-acc`, `--g-amb`, `--g-red`…),
  thème clair "parchemin" (beige/vert `#3A6918`) et sombre "kaki forêt" (`#0D1309`), police
  Lora pour les titres, Tailwind + styles inline, icônes `lucide-react`.
- Composants UI dupliqués par vue (`ParcellCard`, `CultureCard`, `StatTile`, `DonutRing`…),
  pas de dossier `components/ui/` unifié.

## 3. Vue d'ensemble des écrans — mapping ancien ↔ nouveau

| Écran maquette | Équivalent actuel | Nature du changement |
|---|---|---|
| **Tableau de bord** (vue d'ensemble + météo + à faire + récoltes + journal récent) | **Aucun** | **Nouvelle vue** — création, pas une refonte |
| **Statistiques** (sous-onglet du tableau de bord) | `views/Stats.jsx` | Refonte visuelle + **changement d'architecture** (devient sous-section du Tableau de bord, plus un onglet racine) |
| **Plan** (liste parcelles + détail + sous-tuiles "Vue plan"/"Rotation") | `views/Plan.jsx` | Refonte visuelle + **ajout d'un niveau de sous-navigation** (2 sous-écrans non implémentés dans la maquette : placeholders) |
| **Cultures** (fiches + calendrier par famille botanique) | **Aucune vue dédiée** (dispersé Plan/Stocks/Pépinière) | **Nouvelle vue transverse** — changement d'architecture de l'info, pas juste un habillage |
| **Pépinière** | `views/Pepiniere.jsx` | Refonte visuelle, structure de données proche (stades germination/godet/terre) |
| **Stocks** | `views/Stocks.jsx` | **Changement d'architecture de l'info** (depuis le 15/08/2026, cf. §5.11) — devient l'écran transverse unique des cultures (fusion de 3 sections en un groupement par famille botanique), pas une simple refonte visuelle. Absorbe l'ambition du Lot E (Cultures transverse) |
| **Journal** | `views/Historique.jsx` | Refonte visuelle + **renommage** (Historique → Journal) |

## 4. Changements purement visuels (CSS / breakpoints / thème)

Ces points ne modifient ni la navigation ni le regroupement de l'information — ils sont
adressables écran par écran, indépendamment les uns des autres.

- **Palette et tokens** : nouvelle palette verte "dashboard" (`#4A7C22` clair / `#8EC452`
  sombre) à la place du duo parchemin/kaki forêt actuel. Nécessite de réécrire les tokens
  CSS (`--g-*`) plutôt que de les mapper 1:1 — les noms sémantiques diffèrent aussi
  (`brand`, `brandSoft`, `amber`, `violet` vs `g-acc`, `g-amb`, `g-red`…).
- **Composants atomiques** : `Card`, `Btn` (4 variantes primary/ghost/soft/quiet), `Badge`,
  `Stat`, `ProgressBar`, `MonthStrip`, `SearchField`, `Select` — portage direct possible
  vers un dossier `components/ui/` factorisé (actuellement dupliqués par vue).
- **Responsive — règle tranchée** (gravée dans `CLAUDE.md`) : les breakpoints Tailwind
  (`md:`, `lg:`…) sont réservés à la structure de page globale (bascule bottom nav ↔
  sidebar desktop) ; **tout composant réutisable** (`ParcelleCard`, `ObservationIcon`,
  panneaux, listes…) naît avec `container-type: inline-size` et des `@container` — pas de
  débat au cas par cas pendant le développement des US. Ce n'est donc plus un point ouvert :
  c'est une convention de code à appliquer dès le Lot A (design system).
- **Cartes tableau ↔ cartes mobiles** : le pattern `wstock-table` / `wstock-cards` (Stocks)
  bascule table HTML en desktop / cartes empilées en mobile à contenu identique — c'est un
  changement purement présentationnel, la donnée et la hiérarchie ne changent pas.
- **Bandeaux d'info contextuels** (`InfoBanner`) et infobulles `?` (`Tip`) : ajout d'une
  couche d'aide contextuelle au survol, superposable sans toucher à la structure existante.
- **Police** : Lora conservé pour les titres/valeurs, cohérent avec l'existant.
- **Thème clair/sombre** : mécanisme conservé (toggle), seule la palette change.
- **Correctifs de responsive apportés en itération** (purement CSS, aucun impact fonctionnel) :
  - Bandeau haut en mobile (< 900 px) : seuls le thème et l'avatar restent visibles en
    permanence ; actualisation, notifications et guide basculent dans la première section du
    menu Compte (classe `.wmob-only`, cachée dès 900 px via `@container`). Déconnexion,
    Telegram et gestion des membres restent accessibles depuis ce même menu à 390 px.
  - Bandeau d'information (`InfoBanner`) : sous 620 px, le bouton d'action passe à la ligne
    et prend toute la largeur (`.wbanner-act`), le texte gardant une largeur minimale de
    190 px au lieu d'être écrasé.
  - Sélecteur de potager (`PotagerMenu`) : contraint à sa boîte, nom tronqué en ellipse
    plutôt que débordant sous le menu (`.wpotbtn`, `.wpotname`) ; le libellé "Mon Potager"
    (`.wbrand`) ne réapparaît qu'à partir de 1340 px pour laisser la place au sélecteur en
    tablette paysage.
  - Ces trois points illustrent concrètement la règle « container queries par défaut pour
    tout composant réutilisable » (cf. `CLAUDE.md`) : tous les seuils ci-dessus sont des
    `@container dev (…)`, pas des media queries globales.

## 5. Changements d'architecture de l'information (regroupement, hiérarchie, navigation)

Ces points redéfinissent ce que l'utilisateur voit où, et demandent une réflexion produit
avant tout chiffrage — impact potentiellement fort sur les habitudes des utilisateurs actuels.

### 5.1 Navigation à deux niveaux (rupture structurante)

- **Actuel** : 1 niveau (bottom nav, 5 onglets à plat), pas de header de page.
- **Maquette** : 2 niveaux —
  1. **Navigation principale** dans une top bar verte (6 entrées : Tableau de bord, Plan,
     Cultures, Pépinière, Stocks, Journal), qui bascule en bottom nav sous 900 px (avec un
     bouton "Plus" pour les onglets excédentaires, ici Stocks + Journal).
  2. **Sous-navigation en tuiles** sous le titre de page (ex : Tableau de bord →
     "Vue d'ensemble" / "Statistiques" ; Plan → "Parcelles" / "Vue plan" / "Rotation").
- Conséquence : **Statistiques n'est plus un onglet racine** mais un sous-écran du Tableau
  de bord. Si des utilisateurs ont pris l'habitude d'accéder aux stats en un tap depuis le
  bottom nav actuel, ce changement ajoute un niveau de clic (compensé par le fait que
  Stats devient accessible aussi via un raccourci "Détail"/"Voir" depuis le Tableau de bord).
- Un `PageHeader` générique (titre H1 serif + sous-titre + actions contextuelles) apparaît
  sur tous les écrans, ce qui n'existe pas aujourd'hui (TopBar actuelle n'affiche qu'un
  titre court sans description).

### 5.2 Création d'un "Tableau de bord" (nouvelle vue racine)

- Agrège des informations aujourd'hui déjà présentes ailleurs (météo → nulle part
  actuellement côté frontend bien que `utils/meteo.py` existe côté bot ; à faire cette
  semaine → n'existe pas ; récoltes de la saison → dans Stats ; dernières actions → dans
  Historique) **plus deux éléments réellement nouveaux** :
  - Un module "À faire cette semaine" (todo list dérivée du calendrier cultures) —
    fonctionnalité absente du backend actuel, à spécifier (règles de génération).
  - Un module météo local dans le web (aujourd'hui la météo n'existe que côté bot Telegram,
    job quotidien 5h — `utils/meteo.py`). **Précision produit** : un potager est situé
    géographiquement — il faut donc rattacher une localisation (nom de ville a minima,
    coordonnées idéalement) au potager, pas seulement afficher une météo générique. Ce
    rattachement passera par un **module de recherche de ville unifié** (composant de
    recherche/autocomplete réutilisable, détaillé dans une US dédiée), utilisé à la fois
    pour la création/édition du potager et pour tout futur besoin de géolocalisation.
    Une fois la localisation connue, l'endpoint météo web peut interroger Open-Meteo avec
    les coordonnées du potager pour fournir une grille météo personnalisée (et non plus un
    point fixe codé en dur comme dans `utils/meteo.py` actuellement, probablement lié à une
    seule ville de configuration). **Impact modèle de données** : ajouter les champs de
    localisation sur l'entité Potager (ville, éventuellement latitude/longitude), migration
    à prévoir.
- Devient le point d'entrée par défaut de l'app (remplace `Plan` comme onglet initial) —
  changement de parcours utilisateur, pas seulement d'affichage.

### 5.2 bis Localisation du potager & météo web (US-074, US-075) — mise en œuvre

Les deux premières briques backend que le §5.2 laissait ouvertes — localisation réelle du
potager et météo personnalisée — sont livrées. Trois écarts avec le cadrage initial, tous
des précisions d'implémentation plutôt que des changements de périmètre :

| Point | Cadrage (§5.2, §6) | Livré | Raison |
|---|---|---|---|
| Recherche de ville | « module de recherche de ville unifié » sans précision d'architecture | `VilleSearch` (`frontend/src/components/ui/VilleSearch.jsx`) interroge le géocodage Open-Meteo **directement depuis le navigateur** — aucun endpoint backend de recherche | L'API de géocodage Open-Meteo est gratuite, sans clé, et ouverte en CORS ; passer par le backend n'aurait ajouté qu'un relais sans valeur (pas de donnée sensible, rien à filtrer côté serveur) |
| Fuseau horaire du potager | Non tranché explicitement | `GET /meteo` retombe toujours sur `METEO_TIMEZONE` (Europe/Paris) — `Potager` ne porte pas de colonne fuseau | Application francophone à ce stade ; ajouter un fuseau par potager sans besoin identifié aurait été une colonne spéculative (cf. CLAUDE.md, « ne pas concevoir pour des besoins hypothétiques ») |
| Correction d'un potager déjà créé | « aucun moyen de modifier la localisation d'un potager déjà créé » (constat du problème, §_Contexte fonctionnel_ US-074) | `PATCH /potagers/{id}` (owner uniquement) + entrée « Modifier le potager » dans `PotagerMenu` | C'était un CA explicite d'US-074 (CA4/CA5), pas une extension de périmètre — mentionné ici pour mémoire, `GET /potagers` expose désormais aussi `ville`/`latitude`/`longitude` par potager pour pré-remplir ce formulaire |

**CA6 (jamais de valeur inventée) tenu de bout en bout** : `Potager.ville`/`latitude`/`longitude`
restent `null` tant qu'ils n'ont pas été renseignés, aussi bien à la création
(`creer_potager`) qu'à la lecture (`GET /potagers`, `GET /meteo` → `localisation_manquante:
true` plutôt qu'un repli silencieux sur les coordonnées du bot Telegram).

**`fetch_meteo()` (`utils/meteo.py`) généralisée sans rien retirer** : `lat`/`lon`/`timezone`
deviennent des paramètres optionnels (repli sur les constantes globales du bot, comportement
du job 5h et de `/meteo` Telegram strictement inchangé), et le dict retourné gagne
`previsions` (5 jours), `temp_actuelle`, `ressenti`, `humidite`, `vent_actuel_kmh` — des
ajouts, aucune clé existante renommée ni supprimée. `GET /meteo` (nouvel endpoint, distinct
de `GET /meteo/history` qui ne couvre que le passé) expose ces données pour le potager actif.

**Dette restante après US-074/US-075** : le formulaire de création de potager
(`AucunPotager.jsx`) intègre déjà `VilleSearch` mais reste par ailleurs sur les alias `--g-*`
(non retouché, hors périmètre d'US-074) — dette d'alias déjà tracée au §7.4 (non comptée dans
le Lot B, cet écran n'en fait pas partie). La carte météo du Tableau de bord elle-même
(`ScreenDashboard` de la maquette, consommant `GET /meteo`) est livrée par US-076 — voir
§5.2 ter.

### 5.2 ter Widget météo & personnalisation du Tableau de bord (US-076, US-077) — mise en œuvre

Les deux dernières briques du Lot C sont livrées. Le widget météo (`views/Dashboard.jsx`)
porte la carte `ScreenDashboard` de la maquette figée sur `GET /meteo` (US-075) ; la
personnalisation (`ModalPersonnaliserDashboard.jsx` + `hooks/useDashboardWidgets.js`) reste
générique dès sa livraison, conformément au CA5 d'US-077.

| Point | Cadrage (US-076/US-077) | Livré | Raison |
|---|---|---|---|
| Emplacement du bouton « Personnaliser l'affichage » | « en tête d'écran, aux côtés du titre de page » — aucune maquette Claude Design ne couvre ce composant précis | Ajouté dans `PageHeader.jsx`, sur la même ligne que le `<h1>`, visible uniquement quand `view === 'bord'` (pas sur « Statistiques », qui partage la même entrée de navigation) | `PageHeader` est un composant transverse à tous les écrans ; un ajout conditionnel minimal évite de lui inventer une API générique d'actions pour un unique bouton d'un seul écran |
| Partage de l'état entre le bouton (dans `PageHeader`) et la vue `Dashboard` | Non précisé — les deux vivent dans des arbres React distincts, sans provider commun | `useSyncExternalStore` sur un état de module + `localStorage` (`hooks/useDashboardWidgets.js`), plutôt qu'un contexte React | Évite d'imposer un `Provider` supplémentaire à toute l'application pour un besoin de lecture/écriture partagée entre deux composants seulement |
| Widgets encore `Placeholder` (à faire cette semaine, récoltes, dernières interventions) | CA6 : « aucun traitement spécial pour les widgets non encore implémentés » | Le composant `Placeholder` existant (US-053) est réutilisé tel quel dans la grille du Tableau de bord, piloté par le même catalogue que le widget météo | Tenir le CA6 à la lettre : la préférence d'affichage ne distingue pas un widget réel d'un widget en attente de données |
| Repli si `temp_actuelle`/`ressenti`/`humidite`/`vent_actuel_kmh` sont `None` (Open-Meteo « current » indisponible, cf. §5.2 bis) | Non couvert explicitement par les CA | Repli sur `temp_max` pour la température affichée, `—` pour les trois indicateurs secondaires — jamais de valeur inventée (même principe que le CA6 « jamais de valeur inventée » d'US-074) | Cohérence avec la règle déjà posée pour la localisation ; `fetch_meteo()` documente déjà ces trois champs comme potentiellement absents |

**Grille 2×2 en `@container`, pas en breakpoint Tailwind** : `views/Dashboard.jsx` bascule sa
grille de widgets à `@[720px]/dash:grid-cols-2` — même convention que `ScreenPlan`
(`@[900px]/plan`, US-060) — conformément à la règle du CLAUDE.md (« Responsive frontend »).
La largeur de bascule n'est pas dictée par la maquette (dont le prototype ne fige pas de
seuil pour cette grille) ; 720px a été choisi pour que chaque carte du Tableau de bord garde
une largeur confortable en deux colonnes, cohérent avec les seuils déjà retenus ailleurs dans
l'écran (`plan-vue`/`plan-rot` restant en `Placeholder`, cf. §5.3 bis).

### 5.3 Nouvelle vue "Cultures" transverse

- Aujourd'hui, une culture n'a pas de fiche unique : elle est vue à travers le prisme de la
  parcelle (Plan), du stock (Stocks) ou du lot en godet (Pépinière). La maquette introduit
  une **fiche culture agrégée** (famille botanique, durée, exposition, besoin en eau, lieu,
  calendrier des 12 mois semis/plantation/récolte), groupée par famille (Solanacées,
  Cucurbitacées…) avec recherche et filtre par famille.
- **Décision produit** : cette vue s'appuie sur une **agrégation calculée à la volée**
  depuis les données existantes (parcelles, stocks, événements), **sans inclure les
  cultures en pépinière** (un lot en godet n'est pas encore une "culture en place" au sens
  de cette vue — il reste rattaché à l'écran Pépinière). Ce n'est donc pas une nouvelle
  entité front dédiée, mais une lecture transverse des entités déjà en base.
- **Schéma de métadonnées à définir** : les champs affichés par fiche (famille botanique,
  durée de culture, exposition, besoin en eau…) n'existent pas dans le `CultureConfig`
  actuel — il faudra concevoir un schéma plus complet pour cette table (migration à
  prévoir) et déterminer la source de ces données : génération/extraction depuis une base
  de référence horticole existante si une source fiable et réutilisable est identifiée, ou
  interrogation d'une API tierce (à évaluer en atelier technique — ce choix conditionne le
  chiffrage, il n'est pas tranché à ce stade).

### 5.3 bis Sous-écrans du Plan non implémentés dans le prototype

- "Vue plan" (représentation graphique à l'échelle avec glisser-déposer) et "Rotation des
  cultures" (historique 3 ans par famille botanique) n'existent que comme `Placeholder` dans
  le prototype fourni — ce sont des promesses de navigation sans fonctionnalité derrière.
- **Décision produit** : on **positionne l'activité** — les deux entrées de sous-navigation
  sont livrées dès cette refonte (tuiles visibles, écrans en `Placeholder` explicite comme
  dans le prototype) — mais les **vues fonctionnelles spécifiques seront traitées plus
  tard**, dans un chantier séparé avec ses propres US. Ne pas bloquer le Lot B (Plan) sur
  ces deux fonctionnalités.

### 5.4 Renommage Historique → Journal

- Impact mineur mais transverse : label affiché, éventuellement nom de route/variable côté
  front (`views/Historique.jsx`). Le bot Telegram utilise déjà le terme "Journal du potager"
  par endroits — à harmoniser.

### 5.5 Guide d'utilisation intégré (nouveauté, périmètre élargi)

- La maquette ajoute une modale "Guide d'utilisation" accessible depuis la top bar (icône
  `?`), avec sommaire de sections et navigation pas-à-pas — fonctionnalité produit nouvelle,
  absente de l'app actuelle (le bot Telegram a un `/help` textuel, mais rien d'équivalent
  côté web). À traiter comme une fonctionnalité à part entière, pas un détail visuel.
- **Périmètre confirmé et élargi** : il ne s'agit pas seulement d'un guide de navigation web
  (écrans + didacticiel expliquant l'usage de l'interface), mais aussi d'un volet expliquant
  **l'accès au « backoffice » via le bot Telegram** — c'est-à-dire documenter, dans ce même
  guide intégré, comment utiliser le bot (commandes slash, saisie vocale, flux de
  correction…) comme mode de saisie complémentaire à l'interface web. Le guide devient donc
  un point d'entrée pédagogique unique pour les deux surfaces de l'application (web + bot),
  et non un simple mode d'emploi de la navigation web.

### 5.6 Sélecteur de potager & menu Compte (répond au point ouvert « réintégration TopBar »)

La maquette ne laissait initialement aucun équivalent pour le sélecteur de potager, la
gestion des membres, le lien Telegram et la déconnexion (cf. ancien point ouvert n°5). Le
module `web-account.jsx` comble ce manque avec une proposition concrète, structurée en deux
menus distincts + trois modales :

- **Contexte (gauche du bandeau)** — le libellé statique "Mon Potager" devient un vrai
  **sélecteur de potager** (`PotagerMenu`) : menu déroulant listant tous les potagers de
  l'utilisateur avec rôle, nombre de parcelles et de membres, coche sur le potager actif,
  puis deux actions : « Rejoindre un potager » (code d'invitation) et « Tous mes potagers »
  (comparer/basculer). **C'est le seul accès permanent au code d'invitation**, comme dans le
  code actuel (`PotagerSelector.jsx`) — point de continuité important à préserver. Le nom du
  potager actif reste toujours visible, même avec un seul potager.
- **Compte (menu avatar à droite)** — regroupe le personnel (`AccountMenu`) : identité,
  rôle sur le potager actif, « Relier Telegram » avec état visible (relié / à faire),
  « Gérer les membres » (visible uniquement pour le propriétaire), déconnexion, version
  d'API en pied de menu. **L'actualisation manuelle des données** (icône `sync`) est aussi
  remontée ici — elle existait dans le code actuel mais manquait dans la première version de
  la maquette web.
- **Trois modales** portent les actions concrètes :
  - `ModalPotagers` — bascule entre potagers ou rejoindre via code d'invitation.
  - `ModalMembres` — liste des membres + génération d'un code d'invitation (rôle + durée
    d'expiration affichée).
  - `ModalTelegram` — état de la liaison + génération d'un code de liaison à durée limitée
    (10 minutes dans la maquette).

**Point d'attention produit signalé par le designer, à trancher explicitement** : ces trois
modales portent de **vraies actions** (rejoindre, inviter, retirer un membre, générer un
code) — elles sortent donc du cadre « consultation seule » retenu jusqu'ici pour les autres
données du potager dans cette refonte (Lots B à F sont des vues de lecture). L'administration
du potager (membres, invitations, liaison Telegram) ne peut fonctionnellement pas se passer
de ces actions d'écriture. Deux options possibles pour cette phase :
1. Implémenter ces trois modales avec leurs actions réelles dès le Lot A bis (portage direct
   des fonctions déjà existantes dans `PotagerSelector.jsx` / `GestionMembres.jsx` /
   `LierTelegram.jsx`, seul l'habillage change) ;
2. Les livrer en lecture seule pour cette phase (affichage sans les actions d'écriture), et
   reporter le branchement des actions à un lot ultérieur.
**Décision produit (confirmée)** : option 1 retenue — les trois modales portent leurs vraies
actions d'écriture dès le Lot A bis. Ces fonctions existent déjà et sont opérationnelles dans
le code actuel ; il s'agit d'un portage visuel vers le nouveau shell, pas d'un développement
fonctionnel nouveau — contrairement aux Lots C/D/E qui, eux, nécessitent réellement de
nouvelles briques backend. L'administration du potager (membres, invitations, liaison
Telegram) reste donc pleinement utilisable pendant toute la refonte.

#### Mise en œuvre effective du menu Compte (US-055) — écarts assumés avec la maquette

Le composant livré (`frontend/src/components/AccountMenu.jsx`) reprend la structure de
`AccountMenu` (`web-account.jsx`) : bloc identité sur fond `brandSoft`, ligne « Sur ce
potager » + pastille de rôle, intitulé « Compte & liaisons », groupe mobile
(actualisation, notifications), « Relier Telegram » avec pastille d'état, « Gérer les
membres » réservé au propriétaire, déconnexion, version d'API en pied de menu.

Quatre écarts sont volontaires, tous dus à un décalage entre les données mockées de la
maquette et ce que l'application sait réellement produire :

| Point | Maquette | Livré | Raison |
|---|---|---|---|
| Notifications | Entrée mobile « 1 non lue » + icône cloche dans le bandeau desktop | Entrée désactivée « Bientôt disponible », visible à toutes les tailles | La fonctionnalité n'existe nulle part dans l'application (ni composant, ni endpoint). Sans icône cloche en desktop, restreindre l'entrée au mobile la ferait disparaître au-dessus de 900px |
| Guide d'utilisation | Entrée mobile + icône dans le bandeau desktop | Absent | `GuideModal` relève du **Lot F**, non implémenté à ce jour (cf. §5.5) |
| État Telegram | `Relié · @remy_potager` | `Relié` / `Non relié` | `GET /auth/me` n'expose qu'un booléen `telegram_lie` — l'identifiant du chat n'a pas à circuler côté navigateur |
| Horodatage « synchronisé il y a 4 min » | Présent dans le bandeau de pied et le sous-titre d'actualisation | Absent | Aucune donnée de dernière synchronisation n'est suivie côté application |
| Habillage des modales | `ModalTelegram` / `ModalMembres` redessinées (en-tête `brandSoft`, pied explicatif, barre de progression du code…) | ~~`LierTelegram.jsx` / `GestionMembres.jsx` inchangées, encore sur les alias `--g-*`~~ → **résorbé** | US-055 / CA2 et CA3 ne cadraient que le changement de **point d'entrée**, et le restylage était renvoyé au Lot B. Il a en fait été fait dans une itération postérieure : vérification au cadrage du Lot B, ces deux fichiers ne portent plus aucun alias `--g-*`. **Écart clos, sans US dédiée** |

À noter également : la maquette nomme le rôle en lecture seule `viewer`, le backend
`lecteur` (`PotagerMembre.role`). C'est la valeur backend qui fait foi ; les libellés
affichés sont centralisés dans `frontend/src/lib/roles.js`, partagé par `PotagerMenu` et
`AccountMenu`.

Enfin, un seul ajout backend a été nécessaire pour alimenter le bloc identité :
`GET /auth/me` (nom, e-mail, `telegram_lie`), en lecture seule sur des colonnes existantes
de `users`, sans migration ni règle métier nouvelle.

### 5.7 Écran de connexion & inscription (répond au point ouvert « authentification non couverte »)

Le point ouvert n°5 (§6, historique) signalait que l'écran de connexion était le seul
élément de l'application non couvert par la maquette d'origine. Le module `login-screens.jsx`
(fichier focal `Potager - Connexion.html`) comble ce manque avec un écran scindé :

- **Layout** (`LoginSplit`, container queries sur `.device`) : sous 900px, formulaire seul
  en pleine largeur (logo + bouton thème en tête, pied de page compact avec mentions
  légales) ; à partir de 900px, un panneau de marque apparaît à gauche (accroche produit +
  trois repères chiffrés) pendant que le formulaire reste à droite, plafonné à 404px.
- **Formulaire** (`AuthForm`) : bascule Connexion / Créer un compte au sein du même
  composant (pas de changement de route). Connexion = e-mail + mot de passe (avec lien
  « Mot de passe oublié ? »). Inscription = mêmes champs + Prénom + Nom + case à cocher
  CGU/confidentialité. Champ mot de passe avec bouton afficher/masquer (`Field`, icône
  œil) — fonctionnalité déjà présente dans `Auth.jsx` actuel, portage visuel.
- **Connecteurs OAuth** (`OAuthRow`) : trois boutons « Continuer avec Google / Facebook /
  Telegram » au-dessus du séparateur « ou par e-mail », en une colonne avec libellé complet
  sous 420px de conteneur, en trois colonnes avec icône seule à partir de 420px.
- **Thème clair/sombre** : togglable depuis l'écran, cohérent avec le mécanisme existant.

**Écarts assumés entre la maquette et le périmètre retenu pour le lot A ter** (US-056,
US-057) :

| Point | Maquette | Décision retenue | Raison |
|---|---|---|---|
| Repères chiffrés du panneau de gauche | Données d'un potager précis (« 5 parcelles suivies », « 61 plants en pépinière »…) | Accroche produit générique, non personnalisée | L'écran de connexion s'affiche **avant** authentification : aucune donnée de compte n'est disponible à ce stade, contrairement aux écrans internes de l'app |
| Champs Prénom + Nom (inscription) | Deux champs distincts | Un seul champ « Nom » | `User.nom` (`database/models.py`) est une colonne unique — scinder en prénom/nom demanderait une migration hors périmètre d'un simple portage d'écran ; le champ existant suffit à afficher un nom dans le menu Compte (US-055) |
| Connecteurs OAuth (Google/Facebook/Telegram) | Boutons fonctionnels déclenchant une authentification tierce | Boutons affichés mais désactivés (« Bientôt disponible ») | Aucune intégration OAuth n'existe côté backend (enregistrement d'app, credentials, redirection) ; Telegram en particulier a déjà un mécanisme distinct (liaison par code, US-045) qui ne doit pas être confondu avec une connexion initiale par Telegram. Le câblage réel est un chantier séparé, à cadrer ultérieurement |
| Lien « Mot de passe oublié ? » | Présent, sans précision de comportement dans la maquette (prototype statique) | Fonctionnalité réelle à part entière | Aucun mécanisme de réinitialisation n'existe aujourd'hui côté backend — ce n'est pas un simple habillage, d'où une US dédiée (US-057) plutôt qu'une inclusion dans le portage visuel |

Contrairement au menu Compte (§5.6, portage visuel à 90 %), ce lot combine donc un
**portage visuel majoritaire** (US-056) et une **fonctionnalité réellement nouvelle**
(réinitialisation de mot de passe, US-057) — la distinction est reflétée dans le découpage
en deux US plutôt qu'une seule.

### 5.8 Onboarding « premier potager » (nouveauté, dépendante des lots C et E)

Le module `onboarding-screens.jsx` (fichier focal `Potager - Premier potager.html`)
introduit un assistant en 4 étapes affiché juste après la création de compte, réutilisant
le panneau de gauche de l'écran de connexion (§5.7) pour porter la progression :

1. **Votre potager** — nom du potager + commune, avec un encart pour basculer vers la
   saisie d'un code d'invitation si l'utilisateur rejoint un potager existant plutôt que
   d'en créer un.
2. **Première parcelle** — nature de l'espace (pleine terre / pépinière), nom, surface,
   exposition, type de sol.
3. **Cultures** — sélection multiple parmi 12 cultures courantes (Tomate, Courgette,
   Salade, Carotte, Haricot vert, Radis, Pomme de terre, Oignon, Fraise, Poireau,
   Concombre, Betterave), présentée comme un point de départ, le reste étant renvoyé au
   futur écran Cultures (Lot E).
4. **Récapitulatif** — relit les trois étapes précédentes et propose "Entrer dans mon
   potager", avec une suggestion de relier Telegram (US-045) en prochaine étape.

**Analyse de faisabilité au regard du backend actuel** — trois champs de la maquette n'ont
aucun équivalent aujourd'hui :

| Champ maquette | État actuel | Décision retenue pour US-058 |
|---|---|---|
| Commune (étape 1) | `Potager` n'a que `latitude`/`longitude` (`POST /potagers`, US-048), pas de texte libre | ~~Nouvelle colonne `Potager.ville`~~ — **posée entre-temps par US-074** (`migration_v26.sql`, livrée avant US-058) avec sa recherche/autocomplete réelle (`VilleSearch`, géocodage Open-Meteo) : US-058 réutilisera cette colonne et ce composant tels quels, sans rien ajouter ni géocoder elle-même — cf. §5.2 bis |
| Type de sol (étape 2) | Aucun champ équivalent sur `Parcelle` | Nouvelle colonne `Parcelle.type_sol` (texte simple, migration), purement informatif à ce stade — non exploité par le calcul de stock/plan |
| Sélection de cultures (étape 3) | `CultureConfig` n'est créée qu'à la demande, avec un `type_organe_recolte` obligatoire (`app/services/parcelles.py::creer_culture_config`) — jamais pré-semée pour un catalogue de cultures courantes | Sélection **informative uniquement** dans le récapitulatif de cette US — aucune fiche `CultureConfig` ni événement n'est créé à partir des cultures cochées ; le rattachement à de vraies fiches est un point ouvert, à raccorder une fois le schéma `CultureConfig` étendu du Lot E disponible (§5.3) |

Autre écart, mineur : la création de parcelle n'existe aujourd'hui que côté bot Telegram
(`utils/parcelles.create_parcelle`, commande `/parcelle ajouter`) — aucun endpoint web
équivalent n'existe. US-058 introduit donc un premier `POST /parcelles`, qui réutilise
cette même fonction de service (pas de nouvelle règle métier de création de parcelle,
seulement une nouvelle porte d'entrée HTTP).

Contrairement aux lots A ter et A bis (portage visuel de fonctions déjà opérationnelles),
ce lot dépend directement de l'avancement des Lots C (localisation) et E (catalogue de
cultures) pour délivrer sa version pleinement fonctionnelle — d'où sa priorité volontairement
basse (§7.1) : la version décrite ici (US-058) est livrable de façon autonome, mais restera
plus simple que la maquette tant que C et E ne sont pas cadrés.

### 5.9 Écran Pépinière (US-061) — écarts assumés avec la maquette

L'écran livré porte `ScreenPep` (`web-screens.jsx`) sur les données réelles par lot
d'US-065 : barre de filtres, carte de repères en ligne (`N lots actifs` · `N plants en
godet` · `N % germination`), groupes repliables par famille botanique (`GroupHead`), et
carte de lot avec badge de stade solide, nom serif + variété italique, `PlantDonut`,
ligne `date · N jours`, frise `StageBar` à trois segments, décomposition `PlantRatio`,
badge de germination coloré par le taux et lieu du lot.

Deux critères d'acceptance d'US-061 contredisaient la maquette ; ils ont été arbitrés en
faveur de celle-ci :

| Point | US-061 | Maquette | Décision |
|---|---|---|---|
| Barre d'accent latérale colorée par le stock résiduel | CA8 | Absente — la carte a un bord uniforme, le stock est porté par le `PlantDonut` | **CA8 abandonné**, l'accent latéral est supprimé |
| Regroupement des cartes | CA11 — « en attente de mise en place » / « entièrement plantés » | Groupes repliables par **famille botanique** | **Maquette retenue.** Le statut d'un lot reste lisible sur sa carte (badge de stade + compteur à 0), et le bandeau « cultures entièrement plantées » (CA12) est conservé. Du CA11 subsiste ce qui a été explicitement confirmé : **le code couleur du taux de germination** (vert ≥ 80 %, ambre 50–79 %, rouge en dessous), porté par le badge de germination |
| Pourcentage par stade | CA1 — pourcentage **et** quantité pour chacun des trois stades | La frise ne porte que les libellés `Germin. / Godet / Terre` | **Frise maquette stricte.** Les quantités sont portées par `PlantRatio`, le pourcentage par le badge de germination. Les remplissages des trois segments restent les valeurs réelles du CA2 |
| Libellé du badge de taux | CA3 — `Germination X %` en cours, `✓ Réussite X %` une fois close | `Germination N %`, toujours, coloré par le taux | **Maquette retenue.** La distinction en cours / close doublait la même valeur sous deux libellés sans rien apprendre de plus. Seuls les cas où le taux **n'existe pas** gardent un libellé propre : « Germination indéterminée » (déclaration manquante, cf. US-065 CA3) et « Germination inconnue » (aucun semis rattaché) |

**Mise en page des cartes — la règle est intrinsèque, pas par paliers.** `.wpep-grid` vaut
`repeat(auto-fill, minmax(230px, 1fr))` avec une gouttière de 12 px, sans aucun palier :
c'est le seul écran du lot dont la grille ne comporte ni breakpoint ni container query. La
fiche a donc une **largeur calée** — 230 px minimum — et ne s'étire jamais pour occuper la
ligne. Avec la largeur de page de l'application (`max-w-[1320px]` + `px-6`), cela donne
**cinq fiches alignées à 1440 px**, trois à 768 px, une à 375 px, et une rangée incomplète
laisse ses colonnes vides au lieu d'élargir les cartes présentes.

> À retenir pour les US d'écran restantes du Lot B : ne pas transposer ces grilles en
> paliers `grid-cols-*`. Elles sont explicites dans le `<style>` de
> `Potager - Application Web - Proposition.html` et diffèrent d'un écran à l'autre —
> `.wcat-grid` et `.wcult-grid` sont à paliers (`@container dev`), `.wpep-grid` ne l'est pas.

Trois écarts vont dans l'autre sens — la maquette est un prototype à données figées, elle
ne pouvait pas les prévoir :

- **Remplissages de la frise** : le prototype code en dur `100 / 62 / 0` selon le stade.
  L'écran livré y met les pourcentages réels du lot (règle du CA2), la forme restant
  identique.
- **`PlantRatio`** : le prototype écrit « N semés » là où il énumère en réalité des
  plants. Sur données réelles, graines semées et plants obtenus ne coïncident pas (c'est
  précisément le taux de germination) — les deux sont donc distingués : `N semés ·
  N obtenus · N mis en terre · N vendus · N perdus`.
- **Ajouts fonctionnels absents de la maquette, conservés** : sélecteur de date de
  référence (US-030/031) dans la barre de filtres, et ouverture de la timeline de
  traçabilité (US-020/US-029) au clic sur une carte.

Enfin, le regroupement par famille suppose une donnée que le backend n'a pas : la famille
botanique. `frontend/src/lib/familles.js` porte une table de correspondance provisoire,
reprise de `FAM_OF` (`web-tokens.jsx`), avec repli sur « Autres ».

**Dette ouverte, tracée par [US-067](../backlog/US-067_famille-botanique-culture-config.md).**
Cette table est figée dans le code et appariée exactement : sur les données réelles du
potager, `pâtisson`, `petit pois`, `pois gourmand` et `haricot grimpant` tombent dans
« Autres », et **toute culture nouvellement dictée au bot y tombera aussi** jusqu'à une
prochaine livraison. US-067 déplace la famille dans `culture_config` — externalisée,
pré-remplie et corrigeable depuis le bot — et supprime le fichier d'interface. Elle est
rattachée au **Lot B** (elle solde une dette qu'il a créée) et non au Lot E, dont elle
prépare néanmoins la vue « Cultures » : le schéma horticole complet (durée, exposition,
besoin en eau, calendrier) reste, lui, du ressort du Lot E (§5.3).

### 5.10 Écran Plan (US-060) — écarts assumés avec la maquette

L'écran livré porte `ScreenPlan` (`web-screens.jsx`) sur les données réelles de `GET /plan` :
liste des parcelles à gauche sous l'intitulé « Mes parcelles · N », fiche de la parcelle
sélectionnée à droite (nom serif en couleur de marque, pastilles de caractéristiques,
occupation de la surface avec son infobulle), puis carte « Cultures en place » dont chaque
tuile porte le nom, la variété, la quantité, la ligne « famille · durée » et la frise des
douze mois. La pile de cartes autonomes de l'écran précédent disparaît, **barre d'accent
latérale comprise** — comme le CA8 d'US-061 arbitré au §5.9.

**Mise en page — les valeurs de la maquette, pas des paliers au jugé.** Comme pour
`.wpep-grid` (§5.9), les seuils sont ceux du `<style>` de
`Potager - Application Web - Proposition.html` et diffèrent d'un écran à l'autre :
`.wsplit` bascule en deux colonnes `290px` + fluide **à 900 px de conteneur**, alignées en
haut ; `.wcult-grid` passe à deux colonnes **à 640 px** et à trois **à 1400 px** de largeur
de carte. Les deux sont des container queries, jamais des breakpoints d'écran.

Trois écarts vont dans le sens de la maquette, deux dans l'autre — le prototype ne pouvait
pas les prévoir :

| Point | Décision | Motif |
|---|---|---|
| Pastille « Sol » de la fiche | **Omise** | Le type de sol n'existe pas en base — la colonne est posée par US-058, non livrée. Aucun texte de substitution : une pastille vide ne vaut pas mieux qu'une pastille absente |
| Ouverture sur la **deuxième** parcelle (`useState(WPARCELLES[1].id)`) | **Non repris** | Artefact de prototype, destiné à montrer un détail plus fourni. L'écran livré ouvre sur la première (CA1) |
| Mois mis en évidence codé en dur (`CUR_MONTH = 7`) | **Piloté par la date de référence** | Sans quoi l'écran serait dans le passé et la frise dans le présent (US-030/031). `MonthStrip` reçoit un paramètre `moisCourant`, avec repli sur le mois courant pour les autres écrans qui l'utilisent |
| Quantité affichée nue | **Affichée avec son unité** | `GET /plan` renvoie déjà l'unité par culture : une carotte semée sur 2 m² reste en m², jamais convertie en nombre de plants (CA18) |
| Total de plants du sous-titre | **Restreint aux cultures comptées en plants** | Additionner des m² et des graines à des plants produirait un total qui ne veut rien dire (CA6) |

**Fonctions absentes de la maquette, toutes conservées et logées dans la nouvelle mise en
page** : sélecteur de date de référence et filtre culture (barre de filtres), bandeau de
métriques, observations à deux niveaux (parcelle et couple culture + variété), pastille
végétatif/reproducteur avec sa légende — clé de lecture du modèle de stock —, et badge
« Libre » d'une parcelle sans culture, porté à la fois par sa ligne de liste et par son
panneau de détail. Les tuiles de sous-navigation « Vue plan » et « Rotation » restent en
`Placeholder` (Lot G).

Deux corrections de confort, assumées au-delà de la stricte non-régression : une parcelle
retenue par **son nom** garde désormais toutes ses cultures dans le détail (auparavant le
filtre s'appliquait aussi à son contenu, et la parcelle s'affichait vide) ; une exposition
enregistrée sous la chaîne littérale `NULL` par une saisie ancienne n'affiche plus
« Exposition NULL » mais est omise, comme la pastille « Sol ».

**Dette ouverte — le calendrier cultural.** Les frises et la ligne « famille · durée » lisent
une **table de correspondance provisoire** côté interface, `frontend/src/lib/calendrier.js`,
sur le modèle de `familles.js` (§5.9) : les dix cultures de `WCULTURES` reprises telles
quelles, complétées par les calendriers de semis courants pour la France métropolitaine, sur
le même vocabulaire de cultures que la table des familles. Ce sont des **valeurs conseillées
génériques** — elles ne dépendent ni de la parcelle, ni des événements réels, ni de la zone
climatique du potager. Une culture absente de la table s'affiche en **mode dégradé** (frise
entièrement neutre, famille et durée en tiret) : aucune valeur horticole n'est inventée à la
volée, ni pour une culture inconnue ni pour une culture partiellement renseignée.

Le calendrier **réel** — référentiel corrigeable, zones climatiques, contexte de semis
(pépinière vs pleine terre), recalage sur les événements de la parcelle, quatrième état « en
croissance » et durée restante avant récolte — relève en totalité de
[`EPIC_CALENDRIER_CULTURAL`](EPIC_CALENDRIER_CULTURAL.md) : **US-068** (référentiel en base,
qui supprime `calendrier.js`), **US-069** (contexte de semis) et **US-070** (recalage sur le
réel, qui réutilise le paramètre `moisCourant` posé ici). La famille botanique suit le même
chemin avec **US-067**, qui supprime `familles.js`.

### 5.11 Écran Stocks — évolution en écran transverse unique (US-072, US-073)

Contrairement aux autres écrans du Lot B, Stocks n'a **pas** été cadré à iso-fonctionnalité.
Le brief `docs/BRIEF_REFONTE_STOCKS_TRANSVERSE.md` (14/08/2026) acte que l'écran devient le
point d'entrée transverse unique pour tout le suivi des cultures du potager, et une
maquette dédiée a été produite en conséquence puis gelée le 15/08/2026 (`Maquette figée/`
du projet Claude Design, fichier faisant foi `Potager - Application Web - FIGE
2026-08-15.html` ; `web-screens.jsx`, fonction `ScreenStocks`).

**Fusion des trois sections en une seule liste groupée par famille.** L'écran livré
aujourd'hui (`views/Stocks.jsx`) affiche deux sections indépendantes — « Au potager »
(cultures plantées, agrégées par culture) et « En pépinière » (lots en godet, agrégés par
variété) —, avec une ligne « semis pleine terre » glissée dans la première. La maquette
gelée fusionne les trois en une **liste unique**, groupée par **famille botanique** en
premier niveau (confirmé par l'infobulle du filtre : « La famille botanique est le
regroupement principal de cet écran : c'est elle qui commande les rotations de culture »),
l'état (au potager / en pépinière / semis pleine terre) devenant un badge par ligne plutôt
qu'une section. Ce choix tranche explicitement les trois points laissés ouverts par le
brief — calendrier en vue tableau (la maquette gelée n'affiche aucun `MonthStrip` sur cet
écran), niveau de groupement principal (famille, pas état) et coexistence avec l'index
alphabétique (rail secondaire combiné à la recherche, jamais une structure de liste à lui
seul) — plus aucun n'est un point ouvert.

**Absorption de l'écran Cultures transverse (Lot E).** L'ambition d'**US-071** (« Refondre
l'écran Cultures — vue transverse par famille botanique »), rédigée mais jamais implémentée,
est désormais portée par Stocks : une culture en place, quelle que soit sa parcelle, y est
déjà groupée par famille avec la liste de ses parcelles d'origine. US-071 devient donc
**caduque en tant qu'écran séparé** — ses décisions déjà arbitrées (granularité couple
culture + variété, jamais la culture seule ; liste de parcelles plutôt qu'un lieu unique ;
famille et calendrier cultural en mode dégradé sur les tables provisoires existantes ;
exposition et besoin en eau hors périmètre, aucune donnée ni table provisoire) sont reprises
telles quelles par US-072 et US-073 plutôt que rediscutées. Le Lot E, dans son état actuel
(« *à rédiger* », jamais chiffré), perd donc son seul écran dédié ; il ne resterait, si le
besoin se confirme un jour, que la question du schéma horticole étendu de `CultureConfig`
(exposition, besoin en eau, source de données) — indépendante d'un écran.

**US-062 (refonte visuelle de Stocks), déjà rédigée, devient également caduque.** Elle
cadrait Stocks comme un habillage à données inchangées (bascule tableau/cartes, §4) ; ce
cadrage ne couvre plus la fusion des trois sections ni le regroupement par famille, qui sont
un changement réel de structure de l'information. Plutôt que de la retoucher, elle est
remplacée intégralement par deux nouvelles US, sur le modèle déjà appliqué à la Pépinière
(une US de données en amont d'une US d'écran, cf. §7.2) :

- **US-072** — nouvelle agrégation par variété, toutes cultures confondues, avec la liste
  réelle des parcelles d'origine. Aujourd'hui, `GET /stats` (`stock_par_culture`,
  `semis_pleine_terre`) agrège **par culture uniquement** — deux variétés d'une même culture
  y sont fondues en un seul total, sans liste de parcelles. Une fonction de détail par
  variété existe déjà (`utils/stock.py::calcul_stock_par_variete`, portée par
  `US_Stats_detail_par_variete`/US-036/US-037) mais ne traite qu'**une seule culture à la
  fois** et n'est utilisée que par le bot Telegram, jamais exposée en HTTP. US-072
  généralise cette fonction à toutes les cultures d'un appel, lui ajoute la collecte des
  parcelles, et l'expose via un nouvel endpoint. Aucune migration : toute la donnée existe
  déjà sous forme d'événements.
- **US-073** — l'écran lui-même, consommant US-072 : regroupement par famille avec chips de
  filtre, rail alphabétique secondaire, bascule tableau/cartes par container query, bandeau
  de métriques, et les deux ajouts explicitement demandés par l'utilisateur au cadrage —
  l'**export CSV/JSON** (déjà présent dans la maquette gelée, deux boutons dans la barre de
  filtres, générés côté navigateur à partir des données déjà affichées, sans nouvel
  endpoint) et le **lien vers la synthèse des récoltes par variété** (déjà présent dans la
  maquette gelée sous la forme d'un lien « N récoltes » ouvrant une modale — `RecLink` /
  `ModalRecoltes` — listant chronologiquement chaque récolte pesée d'une variété précise,
  alimentée par `GET /historique` filtré par culture et action de récolte).

**Écart de domaine détecté entre la maquette et le modèle métier — décision retenue sans
retour utilisateur, sur le principe déjà appliqué ailleurs (« jamais de valeur inventée »,
cf. §5.9, §5.10).** Les données fictives de la maquette (`WSUIVI`, `web-tokens.jsx`) portent
un champ « vendu » sur toutes les lignes, y compris les cultures déjà « au potager » (ex.
« Tomate Cœur de bœuf … 9 vendus »). Or dans le modèle métier actuel, la vente n'existe que
comme sortie de stock **en pépinière**, avant plantation (US-032, « vente de godet ») :
aucun événement ne permet de vendre un pied déjà planté en pleine terre. US-072 n'expose
donc « vendu » que pour les entrées à l'état pépinière (reprise de `nb_vendus`, déjà
calculé) ; les entrées « au potager » et « semis pleine terre » ne portent pas ce champ —
absent, jamais `0` par défaut, pour ne pas laisser croire qu'une vente a été recherchée et
n'a rien donné.

**Aucune migration BDD dans les deux US.** US-072 est une nouvelle lecture des événements
déjà en base ; US-073 est un écran de consultation. La dette de famille botanique
(`frontend/src/lib/familles.js`, US-067) et celle de calendrier cultural
(`EPIC_CALENDRIER_CULTURAL`) ne sont ni rouvertes ni aggravées : Stocks les lit à l'identique
de Plan et Pépinière, dans leur périmètre déjà tracé.

## 6. Points ouverts / risques à trancher avant découpage en US

Statut mis à jour après relecture et arbitrages produit (voir §5 pour le détail de chaque
décision).

1. **Backend manquant** — ~~localisation du potager (ville + module de recherche unifié)
   pour la météo personnalisée~~ **comblé (17/08/2026)** : `Potager.ville` (migration_v26,
   US-074), `PATCH /potagers/{id}`, module `VilleSearch`, `GET /meteo` (US-075) et le widget
   météo du Tableau de bord avec sa personnalisation (US-076, US-077) sont livrés — détail
   aux §5.2 bis et §5.2 ter. Restent ouverts : schéma étendu de `CultureConfig` (famille
   botanique, durée, exposition, besoin en eau — source à trancher entre base de référence
   existante et API tierce) et règle de génération de la todo-list "à faire cette semaine".
   Sans ces deux briques, la vue Cultures et les trois widgets non météo du Tableau de bord
   (déjà positionnés en `Placeholder`, personnalisables comme le widget météo) ne peuvent
   pas être branchés sur des données réelles — c'est tout le périmètre restant du Lot D.
2. ~~Choix technique responsive~~ — **tranché** : breakpoints Tailwind réservés à la
   structure de page globale, container queries par défaut pour tout composant réutilisable.
   Règle gravée dans `CLAUDE.md` (section « Responsive frontend »), applicable dès le Lot A.
3. ~~Écran d'accueil par défaut~~ — **tranché lors de l'implémentation d'US-053** :
   « Tableau de bord » devient l'écran d'accueil dès maintenant, même si son contenu réel
   relève du Lot D — l'app s'ouvre donc temporairement sur un écran « à venir ». Choix
   assumé : la branche de refonte n'est pas déployée aux utilisateurs avant que le Lot D
   n'ait livré le contenu.
4. ~~Placeholders "Vue plan" et "Rotation"~~ — **tranché** : l'activité (tuiles de
   sous-navigation) est positionnée dans cette refonte, les vues fonctionnelles détaillées
   sont reportées à un chantier séparé.
5. ~~Réintégration des fonctions non couvertes par la maquette~~ — **tranché** : la maquette
   propose désormais un `PotagerMenu` (contexte, gauche) et un `AccountMenu` (compte, droite)
   avec 3 modales dédiées (voir §5.6), **actions d'écriture réelles dès le Lot A bis**
   (décision confirmée — portage des fonctions déjà opérationnelles, pas de développement
   fonctionnel nouveau). ~~L'authentification (écran de connexion complet) reste le seul
   élément non couvert par la maquette~~ — **comblé** : le module `login-screens.jsx` couvre
   désormais l'écran de connexion/inscription (voir §5.7, Lot A ter, US-056/US-057). Seule
   l'authentification OAuth tierce (Google/Facebook/Telegram) reste hors périmètre, affichée
   à l'état désactivé plutôt que développée dans ce lot.
6. **Volet QA visuel** : la checklist ajoutée aux agents Developer/PO/QA-tester (validation
   à 375/768/1280 px via chrome-devtools) s'applique nativement à ce chantier — prévoir une
   maquette de référence exportée (screenshot) par écran et par résolution pour l'US type
   "CA : rendu conforme à la maquette".

## 7. Découpage en lots et répartition des US

### 7.1 Vue d'ensemble des lots

| Lot | Périmètre | Dépend de | US rédigées | Statut |
|---|---|---|---|---|
| **A** | Design system & coquille applicative | — | US-052, US-053 | ✅ Implémenté |
| **A bis** | Sélecteur de potager & menu Compte | A | US-054, US-055 | ✅ Implémenté |
| **A ter** | Écran de connexion & inscription | A | US-056, US-057 | ✅ Implémenté |
| **B** | Refontes visuelles (à iso-fonctionnalité, **sauf Stocks**) | A | US-059 → US-065, **US-067**, **US-072/US-073** | 🔨 **En cours** — US-059, US-065, US-061, US-060 ✅ ; US-072, US-073, US-063, US-067, US-064 à faire |
| **C** | Localisation du potager, météo personnalisée & widget météo du Tableau de bord | A | US-074, US-075, US-076, US-077 | ✅ **Implémenté** — US-074, US-075, US-076, US-077 |
| **D** | Tableau de bord (hors widget météo, cf. Lot C) **+ refonte de l'écran Statistiques** | A, C | *à rédiger* | ⏳ À cadrer |
| **E** | Cultures transverse | A | ~~*à rédiger*~~ | 🚫 **Écran absorbé par Stocks (US-073), cf. §5.11** — ne reste, si besoin futur, que le schéma horticole étendu de `CultureConfig` |
| **F** | Guide d'utilisation intégré | A | *à rédiger* | ⏳ À cadrer |
| **G** | Vues « Vue plan » et « Rotation » | B | *à rédiger* | 🔮 Chantier séparé |
| **H** | Onboarding « premier potager » | A, A ter | US-058 | 📝 Rédigée, à implémenter — **priorité basse** |

Chemin critique : **Lot A bloque tout le reste**. Le **Lot A ter est priorisé juste après
le Lot A** (et A bis, non bloquant) dans l'ordre d'implémentation — il ne dépend que du
design system (A), pas du sélecteur de potager/menu Compte (A bis), mais couvre une surface
utilisateur (l'écran pré-authentification) qui n'a de sens à traiter qu'une fois les tokens
et composants du Lot A disponibles. Les lots B, C, E et F restent ensuite parallélisables ;
seul D dépend de C (météo), et G de B. **Le Lot H (onboarding) est volontairement placé en
fin de portefeuille** : il peut être développé dès que A et A ter sont livrés (aucun blocage
technique), mais sa version pleinement fonctionnelle dépend des Lots C et E (§5.8). **Mise à
jour du 17/08/2026** : le volet localisation du Lot C (recherche de ville, `Potager.ville`)
est désormais livré via US-074 et directement réutilisable par US-058 (cf. §7.3) ; le volet
catalogue de cultures du Lot E reste, lui, non cadré (absorbé par Stocks pour son seul écran,
cf. §5.11 — le schéma horticole étendu de `CultureConfig` qu'attend US-058 n'existe toujours
pas). US-058 reste donc en priorité basse tant que ce second point n'est pas au moins cadré. **Le Lot C a suivi une chaîne de dépendance stricte, désormais intégralement livrée**
— US-074 (localisation) → US-075 (météo, consomme la localisation) → US-076 (widget, consomme
`GET /meteo`) → US-077 (personnalisation, consomme le widget) — le Lot D pourra s'appuyer sur
une météo réelle pour le Tableau de bord dès qu'il sera cadré.

### 7.2 US rédigées — détail

Statut arrêté au 13/08/2026 (v3.31.1). « Implémentée » = livrée sur la branche
`refonte/ui-web-2026-lots` et tracée dans `PATCH_NOTES.md` ; la version de livraison est
indiquée pour pouvoir remonter à l'entrée correspondante.

| US | Titre | Lot | Points | Épic | Statut |
|---|---|---|---|---|---|
| [US-052](../backlog/US-052_design-system-tokens-composants.md) | Fondations du design system (tokens + composants UI) | A | 5 | — | ✅ Implémentée — v3.26.0 |
| [US-053](../backlog/US-053_navigation-deux-niveaux-shell.md) | Coquille applicative en navigation à deux niveaux | A | 8 | — | ✅ Implémentée — v3.26.0 |
| [US-054](../backlog/US-054_selecteur-potager-menu-deroulant.md) | Sélecteur de potager en menu déroulant | A bis | 3 | ÉPIC 2 | ✅ Implémentée — v3.26.0 |
| [US-055](../backlog/US-055_menu-compte-unifie.md) | Menu Compte unifié (Telegram, membres, déconnexion) | A bis | 5 | ÉPIC 2 | ✅ Implémentée — v3.26.0, correctifs v3.27.0 |
| [US-056](../backlog/US-056_refonte-ecran-connexion-inscription.md) | Refonte de l'écran de connexion/inscription | A ter | 8 | ÉPIC 2 | ✅ Implémentée — v3.27.0 |
| [US-057](../backlog/US-057_reinitialisation-mot-de-passe-oublie.md) | Réinitialisation du mot de passe oublié | A ter | 5 | ÉPIC 2 | ✅ Implémentée — v3.27.0 (`migration_v25.sql`) |
| [US-058](../backlog/US-058_onboarding-premier-potager.md) | Assistant de création du premier potager (4 étapes) | H | 8 | ÉPIC 2 | 📝 Rédigée — **priorité basse, cf. §7.1** |
| [US-059](../backlog/US-059_socle-partage-composants-transverses.md) | Migrer les composants transverses de consultation vers le design system | B | 3 | — | ✅ Implémentée — v3.29.0 (42 alias soldés) |
| [US-060](../backlog/US-060_refonte-ecran-plan-parcelles.md) | Refondre l'écran Plan (liste des parcelles et détail) | B | 8 | — | ✅ Implémentée — v3.32.0 (29 alias soldés) ; **écarts assumés et dette de calendrier, cf. §5.10** |
| [US-061](../backlog/US-061_refonte-ecran-pepiniere.md) | Refondre l'écran Pépinière avec les trois stades d'avancement | B | 5 | — | ✅ Implémentée — v3.31.0/v3.31.1 ; **CA8 et CA11 arbitrés en faveur de la maquette, cf. §5.9** |
| [US-062](../backlog/US-062_refonte-ecran-stocks.md) | ~~Refondre l'écran Stocks avec bascule tableau / cartes~~ | B | ~~5~~ | — | 🚫 **Caduque (15/08/2026)** — remplacée par US-072 + US-073, cf. §5.11 |
| [US-063](../backlog/US-063_refonte-ecran-journal.md) | Refondre l'écran Journal | B | 5 | — | 📝 Rédigée — **à implémenter** |
| [US-064](../backlog/US-064_cloture-dette-alias-lot-b.md) | Clôturer la dette d'alias de couleurs sur le périmètre du Lot B | B | 2 | — | 📝 Rédigée — **dernière du lot**, après US-060/063/072/073 |
| [US-065](../backlog/US-065_pepiniere-par-lot-etat-germination.md) | Exposer la pépinière par lot de semis avec un état de germination fiable | B | 8 | — | ✅ Implémentée — v3.30.0 (`GET /pepiniere/lots`, sans migration) |
| [US-066](../backlog/US-066_bot-reclamer-graines-origine-mise-en-godet.md) | Réclamer le nombre de graines d'origine lors d'une mise en godet | — | 3 | — | ✅ Implémentée — v3.30.0, saisie Telegram, hors Lot B |
| [US-067](../backlog/US-067_famille-botanique-culture-config.md) | Externaliser la famille botanique des cultures dans `culture_config` | B | 5 | — | 📝 Rédigée — **dette ouverte par US-061, cf. §5.9** |
| [US-071](../backlog/US-071_refonte-ecran-cultures-transverse.md) | ~~Refondre l'écran Cultures (vue transverse par famille botanique)~~ | E | ~~5~~ | — | 🚫 **Caduque (15/08/2026)** — écran absorbé par Stocks (US-073), cf. §5.11 |
| [US-072](../backlog/US-072_detail-varietes-toutes-cultures-parcelles.md) | Exposer un détail par variété, toutes cultures confondues, avec leurs parcelles d'origine | B | 5 | — | 📝 Rédigée — **remplace US-062, bloquante pour US-073, cf. §5.11** |
| [US-073](../backlog/US-073_refonte-ecran-stocks-transverse.md) | Refondre l'écran Stocks en vue transverse unique, groupée par famille botanique | B | 8 | — | 📝 Rédigée — **remplace US-062, absorbe US-071, cf. §5.11** |
| [US-074](../backlog/US-074_localisation-potager-recherche-ville.md) | Localiser un potager via une recherche de ville unifiée et réutilisable | C | 5 | — | ✅ Implémentée — `migration_v26.sql`, tests pytest ; entrée `PATCH_NOTES.md` [v3.34.0] ; **pas de QA dédiée à ce stade, cf. note du 17/08/2026 et §5.2 bis** |
| [US-075](../backlog/US-075_endpoint-meteo-web-personnalisee.md) | Exposer une météo web personnalisée sur la localisation réelle du potager | C | 5 | — | ✅ Implémentée — `GET /meteo`, tests pytest (dont non-régression bot) ; entrée `PATCH_NOTES.md` [v3.34.0] ; **même réserve QA que US-074, cf. §5.2 bis** |
| [US-076](../backlog/US-076_dashboard-widget-meteo.md) | Afficher le widget météo sur l'écran Vue d'ensemble du Tableau de bord | C | 5 | — | ✅ Implémentée — `views/Dashboard.jsx` ; **QA visuelle GO** (375/768/1280, dont états localisation manquante et erreur API) ; entrée `PATCH_NOTES.md` [v3.34.0], cf. §5.2 ter |
| [US-077](../backlog/US-077_personnaliser-affichage-dashboard.md) | Personnaliser les widgets affichés sur la Vue d'ensemble du Tableau de bord | C | 3 | — | ✅ Implémentée — `ModalPersonnaliserDashboard.jsx`, `hooks/useDashboardWidgets.js` ; **QA visuelle GO**, persistance et verrou CA4 vérifiés ; entrée `PATCH_NOTES.md` [v3.34.0], cf. §5.2 ter |
| [US-078](../backlog/US-078_widget-meteo-conseil-potager-horaires.md) | Enrichir le widget météo (horaires soleil, libellés, conseil potager) | — | 3 | — | ✅ Implémentée — v3.34.0, **hors Lot C** (déjà clos) ; lever/coucher, libellés Humidité/Vent, conseil du jour tronqué/dépliable (`ConseilPotager`, `views/Dashboard.jsx`) ; **QA visuelle GO** (dont troncature/dépliage simulés sur un conseil long) ; cycle complet PO→Dev→QA→Documentation ; aucune migration (champs déjà exposés par US-075) |

**Avancement au 17/08/2026 — 115 points rédigés, 82 livrés (71 %), 33 restants.**
Le total était passé de 94 à 112 points avec la sortie du Lot C de l'état « à cadrer » (4 US
d'un coup, US-074 à US-077, 18 points, toutes livrées le même jour — les deux premières au
cadrage, les deux suivantes juste après, cf. §5.2 bis et §5.2 ter) ; il passe maintenant à
115 avec **US-078** (3 points), enrichissement du widget météo livré dans la foulée, hors
décompte du Lot C (déjà clos) au même titre qu'US-066 pour le Lot B. Le reste de la
décomposition (Lots A/A bis/A ter/B/H) est inchangé depuis le 15/08/2026.

| Ensemble | Points rédigés | Livrés | Restants |
|---|---|---|---|
| Lots A + A bis + A ter | 34 | **34** | 0 |
| Lot B | 49 | **24** (US-059, US-065, US-061, US-060) | 25 (US-072, US-073, US-063, US-067, US-064) |
| Lot C | 18 | **18** (US-074, US-075, US-076, US-077) | 0 |
| US-066 (hors lot, saisie Telegram) | 3 | **3** | 0 |
| US-078 (hors lot, enrichissement Lot C) | 3 | **3** | 0 |
| Lot H (US-058, priorité basse) | 8 | 0 | 8 |

**Total Lot A + A bis + A ter : 34 points, intégralement livrés.** Ordre de dépendance
respecté : US-052 → US-053 → (US-054 ∥ US-055 ∥ US-056) → US-057. **US-058 (Lot H, hors
chemin critique) : 8 points supplémentaires**, dépendant de US-056 (déclenchement juste après
l'écran de connexion) et US-048 (création de potager/invitations, logique réutilisée).

**Total Lot B : 49 points** (36 + US-065 + US-072 + US-073, cf. calcul ci-dessus), **dont 24
livrés**. Ordre de dépendance : US-059 (socle partagé) → (US-060 ∥ [US-072 → US-073] ∥ US-063
∥ [US-065 → US-061 → US-067], parallélisables une fois le socle livré) → US-064 (clôture). La
branche déjà parcourue est celle de la Pépinière (US-065 → US-061), la plus longue du lot ;
**US-067 reste à faire après coup** — elle solde la dette de famille botanique ouverte par
US-061 (§5.9) et n'est pas bloquante pour les écrans restants. **Reste donc à implémenter :
US-072 puis US-073 (Stocks, dans cet ordre — US-073 dépend de US-072), US-063 (Journal) et
US-067**, puis **US-064 en clôture** — cette dernière constate la propreté du périmètre et ne
peut donc être jouée qu'en dernier. **US-066 (3 points) était hors Lot B** : relevant de la
saisie Telegram, elle a été livrée avec US-065 (v3.30.0), ce qui arrête au plus tôt
l'accumulation de lots en état indéterminé dans l'historique.

**Total Lot C : 18 points, intégralement livrés.** Ordre de dépendance strict (pas de
parallélisation possible, contrairement au Lot B) : US-074 (localisation) → US-075 (météo,
lit la localisation posée par US-074) → US-076 (widget, lit `GET /meteo` d'US-075) → US-077
(personnalisation, agit sur le widget d'US-076) — chaîne suivie de bout en bout jusqu'à la
livraison des quatre US. Les quatre ont désormais leur entrée `PATCH_NOTES.md`/`VERSION`
(`[v3.34.0]`, cf. ci-dessous) ; US-074/US-075 restent en revanche sans QA dédiée — point
encore ouvert malgré le lot livré et documenté.

**US-078 (3 points, hors décompte du Lot C) : enrichissement du widget météo, livré le même
jour.** Seule US du lot à avoir suivi le cycle complet de l'Orchestrateur — PO (validation
US existante) → Developer → QA (verdict GO) → Documentation (`PATCH_NOTES.md`/`VERSION`,
`[v3.34.0]`, la même entrée que US-074 à US-077, ouverte à cette occasion pour l'ensemble du
lot non encore documenté).

Le Lot B se voulait **à iso-fonctionnalité** — aucune donnée nouvelle, aucun endpoint
nouveau, aucune migration BDD. Chaque US d'écran porte à ce titre un CA de non-régression
listant nommément les fonctions à préserver, y compris celles absentes de la maquette (date
de référence, observations, bandeaux de métriques, filtres, pagination). **Trois US
dérogent à ce principe** : US-065 (lecture par lot) et US-067 (famille botanique en base),
toutes deux à cause de la Pépinière, et désormais **US-072** (nouvelle agrégation par
variété), à cause de Stocks — cf. §5.11. Stocks et Pépinière sont les deux seuls écrans du
lot dont la maquette suppose des données que l'application n'avait pas ; contrairement à la
Pépinière, l'écart de Stocks n'est pas une correction d'un calcul existant mais un
changement de périmètre assumé (l'écran cesse d'être à iso-fonctionnalité, cf. §5.11).

**Une exception : la Pépinière demandait une brique de données préalable (US-065) — livrée en
v3.30.0.** La maquette
y introduit trois barres d'avancement par lot — **Germination / Godet / Terre** — dont les
pourcentages doivent refléter les quantités réelles de plants à chaque stade (§3, colonne
« stades germination/godet/terre »). Les simulations menées au cadrage ont montré deux
obstacles, tous deux dans les données et non dans l'affichage :

1. **Maille de suivi — décision produit, pas correction d'un défaut.** La pépinière est
   agrégée par couple culture + variété. Ce niveau répond à « où en sont mes tomates Cœur de
   bœuf globalement » — les chiffres agrégés ne sont pas faux — mais pas à la question que se
   pose le jardinier devant sa pépinière : **quel lot est prêt à être repiqué ou planté**.
   Deux semis échelonnés d'une même variété n'en sont pas au même point. **Décision produit :
   un événement de semis = un lot = une carte**, règle délibérément simple. Argument
   corroborant : l'état de germination est par nature une propriété d'un lot semé, pas d'une
   variété — une variété avec un lot terminé et un lot qui lève tout juste n'a pas d'état de
   germination unique. **Point laissé ouvert** : le regroupement de lots semés à des dates
   très rapprochées n'est pas traité, il sera arbitré plus tard à l'usage.
2. **Consommation des graines mal calculée** — `utils/stock.py` solde un semis parent
   entièrement dès le premier repiquage (déduplication par `origine_graines_id`), si bien
   qu'un repiquage échelonné fait sauter l'avancement à sa valeur finale alors qu'il reste
   des graines à lever. L'information manquante existe déjà en base (`nb_graines_semees`,
   le « sur N graines » déjà saisi et affiché dans la timeline) : **aucune migration**, seul
   son usage change.

Ces deux points sont portés par **US-065**, dont US-061 (ramenée à 5 points, habillage seul)
dépend. Contrainte structurante de cette US : `calcul_godets()` et `GET /godets` alimentent
quatre consommateurs — Pépinière, Stocks, `/stats` et les statistiques du bot — leur contrat
agrégé **ne change pas**, la lecture par lot s'ajoute à côté. **Impact nul sur Stocks** (à
l'époque US-062, remplacée depuis par US-072/US-073, cf. §5.11) et sur le Lot D.

**Fiabilité de l'état de germination.** Le système ne peut jamais savoir qu'une graine « a
germé mais n'a pas été mise en godet » : il sait seulement que toutes les graines semées ont
été soldées. Si le jardinier omet le « sur N graines », un lot de 10 graines ayant donné
7 plants tous mis en terre affiche « Terre 70 % » au lieu de 100 %, et n'atteint jamais
100 %. L'erreur va toujours dans le sens prudent — on sous-estime, jamais l'inverse — et les
quantités brutes restent exactes. Garde-fous retenus : **état de germination à trois valeurs**
(en cours / close / **indéterminée**, cette dernière n'étant jamais déguisée en « en cours »)
et **signalement des incohérences d'agrégat** (plus de plants que de graines semées), tous
deux dans US-065 ; plus, en amont, **US-066** — le bot réclame le nombre de graines d'origine
quand il manque, seul garde-fou traitant la cause plutôt que le symptôme. Écartées : la
clôture automatique après délai (elle déclarerait mortes des graines qui lèvent peut-être
encore, fabriquant un faux définitif — pire que l'oubli, puisqu'invisible) et le marquage
visuel des pourcentages provisoires (redondant avec le badge de phase).

US-054 et US-055 sont du **portage visuel pur** : les fonctions sous-jacentes
(`PotagerSelector.jsx`, `GestionMembres.jsx`, `LierTelegram.jsx`) sont déjà livrées et
opérationnelles depuis les US-045 à US-048 — aucun développement métier nouveau. US-056 est
majoritairement un portage visuel (écran de connexion/inscription existant), à l'exception
du champ Nom ajouté à l'inscription. US-057 est en revanche une **fonctionnalité backend
nouvelle** (réinitialisation de mot de passe, migration BDD requise) — voir §5.7. US-058
combine portage (parcours et navigation de la maquette) et petites fondations backend
(`POST /parcelles`, deux colonnes minimales) tout en assumant explicitement de rester plus
simple que la maquette sur la localisation et les cultures, en attendant les Lots C et E —
voir §5.8.

### 7.3 Contenu détaillé des lots non encore découpés en US

- ~~**Lot B — Refontes visuelles (à iso-fonctionnalité, sauf Stocks)**~~ — **découpé, cf. §7.2
  (US-059 → US-065, US-067, US-072/US-073)**, et **en cours d'implémentation**. Périmètre :
  Plan (les tuiles « Vue plan » / « Rotation » restent en `Placeholder` depuis US-053),
  Pépinière, Stocks, Journal. Pas de nouvelle donnée métier, juste nouvel habillage +
  responsive — à l'exception de la Pépinière (US-065, US-067) et, depuis le 15/08/2026, de
  Stocks (US-072, US-073 ; voir plus haut et §5.11 — ce n'est plus un habillage mais une
  fusion des trois sections existantes en une vue transverse par famille botanique). Le
  découpage retenu compte **9 US** et non 4 :
  - une **US de socle en tête de lot** (US-059, ✅ livrée) a migré les six composants
    transverses partagés par les quatre écrans (sélecteur de date de référence, filtre
    culture, bandeau de métriques, panneau d'observations, écrans de chargement et d'erreur —
    42 alias à eux seuls). Sans elle, les quatre US d'écran auraient retouché les mêmes
    fichiers en concurrence ; avec elle, elles sont devenues parallélisables ;
  - quatre **US d'écran** (US-060, US-073, US-063, dont **US-061 ✅ livrée**), chacune portant
    un CA de migration des alias et un CA de non-régression nominatif — les fonctions
    absentes de la maquette (date de référence US-030/031, observations US-039, bandeaux de
    métriques, filtres, pagination) sont **toutes conservées et réhabillées**, aucune perte
    fonctionnelle assumée (Stocks excepté sur le seul point du champ « vendu », cf. §5.11) ;
  - trois **US de données propres à un écran** : US-065 (✅ livrée, lecture par lot) en amont
    d'US-061 et US-067 (à faire, famille botanique en base) en aval, pour la Pépinière —
    cf. §5.9 ; **US-072** (à faire, détail par variété toutes cultures) en amont d'US-073,
    pour Stocks — cf. §5.11 ;
  - une **US de clôture** (US-064, à jouer en dernier) qui constate la propreté du périmètre
    du lot sans supprimer le bloc d'alias (cf. §7.4).
  L'écran **Statistiques est explicitement hors Lot B** : devenant un sous-écran du Tableau
  de bord, sa refonte visuelle est rattachée au Lot D pour éviter de le retoucher deux fois.
- ~~**Lot C — Localisation du potager & météo personnalisée**~~ — **découpé et intégralement
  livré, cf. §7.2 (US-074 → US-075 → US-076 → US-077)**. US-074 (module de recherche de
  ville, colonne `Potager.ville`, `PATCH /potagers/{id}`) et US-075 (`GET /meteo`) — cf. §5.2
  bis — puis US-076 (widget météo du Tableau de bord) et US-077 (personnalisation des
  widgets) — cf. §5.2 ter — sont livrées. **US-074 a posé `Potager.ville` la première** :
  c'est désormais US-058 (§5.8, Lot H, non livrée) qui réutilisera cette colonne plutôt que
  l'inverse — la note du §5.8 anticipait l'ordre de livraison sans le figer.
- **Lot D — Tableau de bord** : todo list « à faire cette semaine », intégration météo
  (dépend du Lot C), agrégats récoltes/journal déjà disponibles ailleurs. Cf. §5.2.
  **Inclut la refonte visuelle de l'écran Statistiques** (`views/Stats.jsx`, 78 alias), qui
  en devient un sous-écran (§5.1), ainsi que la suppression finale du bloc d'alias `--g-*`
  et la migration des trois vues orphelines qui le retiennent encore (cf. §7.4).
- ~~**Lot E — Cultures transverse**~~ : son seul écran (vue agrégée hors pépinière, Cf. §5.3)
  est **absorbé par Stocks** (US-073) depuis le 15/08/2026 — cf. §5.11. Ne reste, si le
  besoin se confirme, que le schéma étendu de `CultureConfig` (migration + choix de la
  source des métadonnées horticoles, exposition/besoin en eau), indépendant d'un écran.
- **Lot F — Guide d'utilisation intégré** : parcours web (navigation) + volet explicatif sur
  l'usage du bot Telegram comme backoffice. Cf. §5.5.
- **Lot G — Vues fonctionnelles détaillées « Vue plan » et « Rotation »** : hors périmètre
  immédiat, chantier séparé une fois le Lot B livré. Cf. §5.3 bis.

### 7.4 Dette technique connue, à résorber pendant le Lot B

Deux points introduits volontairement par le Lot A, à traiter au fil des US du Lot B :

1. **Alias de tokens `--g-*`** : plutôt que réécrire les 391 occurrences des anciens tokens
   dans les 20 fichiers de vues (hors périmètre d'US-052 et à fort risque de régression),
   les noms `--g-bg`, `--g-acc`, `--g-amb`… ont été redéfinis comme **alias pointant vers la
   nouvelle palette**. Toute l'application affiche donc bien les nouvelles couleurs, mais
   chaque US du Lot B doit migrer son écran vers les tokens sémantiques
   (`bg-surface`, `text-txt2`, `border-border`…) et retirer ses références aux alias.

   **Répartition recomptée au 13/08/2026**, après les livraisons d'US-059 et d'US-061. Le
   comptage retient les deux formes d'usage d'un alias — `var(--g-*)` et les classes Tailwind
   dérivées (`bg-g-bg`, `text-g-txt2`…) — comme au cadrage, afin que les chiffres restent
   comparables d'une ligne à l'autre :

   | Fichiers | Occurrences | Traité par | État |
   |---|---|---|---|
   | `Observations.jsx`, `DateRefPicker.jsx`, `MetricStrip.jsx`, `CultureFilter.jsx`, `LoadingSkeleton.jsx`, `ApiError.jsx` | 42 → **0** | **US-059** (socle, en tête de lot) | ✅ soldé (v3.29.0) |
   | `Pepiniere.jsx` | 80 → **0** | **US-061** | ✅ soldé (v3.31.0) |
   | `Plan.jsx` | 29 → **0** | **US-060** | ✅ soldé (v3.32.0) |
   | `Historique.jsx` | **54** | US-063 | ⏳ à faire |
   | `Stocks.jsx` | **39** | **US-073** (remplace US-062, cf. §5.11) | ⏳ à faire |
   | `Stats.jsx` | **78** | **Lot D** (Statistiques devient sous-écran du Tableau de bord) | ⏳ hors Lot B |
   | `AucunPotager.jsx` (23), `PotagerSelector.jsx` (19), `VerifyEmail.jsx` (10) | **52** | **Lot D** (vues orphelines, hors périmètre des 4 écrans du Lot B) | ⏳ hors Lot B |
   | `_DesignSystemPreview.jsx` | **5** | — | Page de contrôle visuel (§7.5), supprimée à la clôture du chantier |

   **Périmètre du Lot B : 93 occurrences restantes sur 244** (Journal, Stocks), les 151
   autres ayant été soldées par US-059, US-061 et US-060. Total tous fichiers confondus :
   **247 occurrences** dans `frontend/src`. Les deux écrans restants n'ont pas bougé depuis
   le cadrage — leurs compteurs sont inchangés, et non revus à la baisse par ricochet des
   US déjà livrées.

   **Conséquence : la clôture du Lot B (US-064) ne supprime pas le bloc d'alias.** Elle
   vérifie que les quatre écrans et les six composants transverses sont propres, et met à
   jour le commentaire du bloc pour recenser nommément les quatre fichiers qui le retiennent
   encore. La suppression effective du bloc d'`index.css` et de `tailwind.config.js` est
   reportée au **Lot D**, qui migrera `Stats.jsx` et les trois vues orphelines.
2. **Vues étirées en desktop** : la contrainte `max-w-md mx-auto` a été retirée d'`App.jsx`
   (exigence de mise en page desktop d'US-053). Les écrans non encore refondus s'étirent
   donc sur toute la largeur disponible sur grand écran — rendu imparfait assumé jusqu'à ce
   que le Lot B leur donne une vraie mise en page multi-colonnes. **Reste concerné au
   13/08/2026 : Stocks, Journal** (et Statistiques, jusqu'au Lot D) ; la Pépinière est sortie
   de cet état avec US-061 (§5.9) et le Plan avec US-060, dont le maître-détail et les
   paliers de grille sont décrits au §5.10.

### 7.5 Pages de contrôle visuel (outillage de développement)

Deux routes hors navigation applicative, ajoutées pour la validation visuelle exigée par les
agents Developer et QA-tester :

- `/design-system` — tous les composants de `components/ui/` isolément (US-052)
- `/shell` — la coquille de navigation sans dépendance aux données métier (US-053).
  Deux paramètres d'URL ajoutés par US-055 pour couvrir les cas du menu Compte sans
  manipuler de compte réel : `?role=owner|editor|lecteur` (conditionne « Gérer les
  membres ») et `?telegram=0|1` (état de la liaison affiché).

À conserver tant que le chantier de refonte est en cours ; à supprimer (avec
`src/views/_DesignSystemPreview.jsx`, `src/views/_ShellPreview.jsx` et le routage
correspondant dans `main.jsx`) à la clôture du chantier.
