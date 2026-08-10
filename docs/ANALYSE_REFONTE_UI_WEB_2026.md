# Analyse — Refonte de l'interface web (maquette Claude Design "potager 2026")

> Document de cadrage du chantier de refonte. Les §1 à §6 décrivent l'analyse et les
> arbitrages produit ; le **§7 tient à jour le découpage en lots et la répartition des US**
> (rédigées via `.github/agents/Personna PO.agent.md`, implémentées via
> `.github/agents/Orchestrateur-US.agent.md`).
>
> **Dernière mise à jour** : lots A (US-052, US-053) implémentés ; A bis (US-054, US-055)
> rédigé et prêt à implémenter.

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
| **Stocks** | `views/Stocks.jsx` | Refonte visuelle + bascule table (desktop) / cartes (mobile) |
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

## 6. Points ouverts / risques à trancher avant découpage en US

Statut mis à jour après relecture et arbitrages produit (voir §5 pour le détail de chaque
décision).

1. **Backend manquant — confirmé, à spécifier en US** : localisation du potager (ville +
   module de recherche unifié) pour la météo personnalisée, schéma étendu de
   `CultureConfig` (famille botanique, durée, exposition, besoin en eau — source à trancher
   entre base de référence existante et API tierce), règle de génération de la todo-list
   "à faire cette semaine". Sans ces briques, le Tableau de bord et la vue Cultures ne
   peuvent pas être branchés sur des données réelles.
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
   fonctionnel nouveau). L'authentification (écran de connexion complet) reste le seul
   élément non couvert par la maquette et à concevoir séparément.
6. **Volet QA visuel** : la checklist ajoutée aux agents Developer/PO/QA-tester (validation
   à 375/768/1280 px via chrome-devtools) s'applique nativement à ce chantier — prévoir une
   maquette de référence exportée (screenshot) par écran et par résolution pour l'US type
   "CA : rendu conforme à la maquette".

## 7. Découpage en lots et répartition des US

### 7.1 Vue d'ensemble des lots

| Lot | Périmètre | Dépend de | US rédigées | Statut |
|---|---|---|---|---|
| **A** | Design system & coquille applicative | — | US-052, US-053 | ✅ Implémenté |
| **A bis** | Sélecteur de potager & menu Compte | A | US-054, US-055 | 📝 Rédigées, à implémenter |
| **B** | Refontes visuelles à iso-fonctionnalité | A | *à rédiger* | ⏳ À cadrer |
| **C** | Localisation du potager & météo personnalisée | A | *à rédiger* | ⏳ À cadrer |
| **D** | Tableau de bord | A, C | *à rédiger* | ⏳ À cadrer |
| **E** | Cultures transverse | A | *à rédiger* | ⏳ À cadrer |
| **F** | Guide d'utilisation intégré | A | *à rédiger* | ⏳ À cadrer |
| **G** | Vues « Vue plan » et « Rotation » | B | *à rédiger* | 🔮 Chantier séparé |

Chemin critique : **Lot A bloque tout le reste**. Les lots B, C, E et F sont ensuite
parallélisables ; seul D dépend de C (météo), et G de B.

### 7.2 US rédigées — détail

| US | Titre | Lot | Points | Épic | Statut |
|---|---|---|---|---|---|
| [US-052](../backlog/US-052_design-system-tokens-composants.md) | Fondations du design system (tokens + composants UI) | A | 5 | — | ✅ Implémentée |
| [US-053](../backlog/US-053_navigation-deux-niveaux-shell.md) | Coquille applicative en navigation à deux niveaux | A | 8 | — | ✅ Implémentée |
| [US-054](../backlog/US-054_selecteur-potager-menu-deroulant.md) | Sélecteur de potager en menu déroulant | A bis | 3 | ÉPIC 2 | 📝 À implémenter |
| [US-055](../backlog/US-055_menu-compte-unifie.md) | Menu Compte unifié (Telegram, membres, déconnexion) | A bis | 5 | ÉPIC 2 | 📝 À implémenter |

**Total Lot A + A bis : 21 points.** Ordre de dépendance : US-052 → US-053 → (US-054 ∥ US-055).

US-054 et US-055 sont du **portage visuel pur** : les fonctions sous-jacentes
(`PotagerSelector.jsx`, `GestionMembres.jsx`, `LierTelegram.jsx`) sont déjà livrées et
opérationnelles depuis les US-045 à US-048 — aucun développement métier nouveau.

### 7.3 Contenu détaillé des lots non encore découpés en US

- **Lot B — Refontes visuelles à iso-fonctionnalité** : Plan (les tuiles « Vue plan » /
  « Rotation » sont déjà en place depuis US-053, en `Placeholder`), Pépinière, Stocks,
  Journal. Pas de nouvelle donnée métier, juste nouvel habillage + responsive. Découpage
  naturel : une US par écran (4 US).
- **Lot C — Localisation du potager & météo personnalisée** : module de recherche de ville
  unifié, champs de localisation sur l'entité Potager (migration), endpoint météo web basé
  sur la localisation réelle. Cf. §5.2.
- **Lot D — Tableau de bord** : todo list « à faire cette semaine », intégration météo
  (dépend du Lot C), agrégats récoltes/journal déjà disponibles ailleurs. Cf. §5.2.
- **Lot E — Cultures transverse** : schéma étendu `CultureConfig` (migration + choix de la
  source des métadonnées horticoles), vue agrégée hors pépinière. Cf. §5.3.
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
   (`bg-surface`, `text-txt2`, `border-border`…) et retirer ses références aux alias. Une
   fois tous les écrans migrés, supprimer le bloc d'alias de `index.css` et de
   `tailwind.config.js`.
2. **Vues étirées en desktop** : la contrainte `max-w-md mx-auto` a été retirée d'`App.jsx`
   (exigence de mise en page desktop d'US-053). Les écrans non encore refondus s'étirent
   donc sur toute la largeur disponible sur grand écran — rendu imparfait assumé jusqu'à ce
   que le Lot B leur donne une vraie mise en page multi-colonnes.

### 7.5 Pages de contrôle visuel (outillage de développement)

Deux routes hors navigation applicative, ajoutées pour la validation visuelle exigée par les
agents Developer et QA-tester :

- `/design-system` — tous les composants de `components/ui/` isolément (US-052)
- `/shell` — la coquille de navigation sans dépendance aux données métier (US-053)

À conserver tant que le chantier de refonte est en cours ; à supprimer (avec
`src/views/_DesignSystemPreview.jsx`, `src/views/_ShellPreview.jsx` et le routage
correspondant dans `main.jsx`) à la clôture du chantier.
