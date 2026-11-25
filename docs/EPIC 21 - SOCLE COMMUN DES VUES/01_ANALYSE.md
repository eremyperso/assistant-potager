# 01 — Analyse : la maquette « Socle commun · les sept vues » face à la PWA

*Le 24/11/2026, mis à jour le même jour avec la deuxième version de la maquette (Pépinière en trois onglets, mode sombre) et
les réponses aux questions Q1 à Q5. Source : canvas Claude Design « potager 2026 », page `Socle commun - 7 vues.html`
(copie figée dans [maquette/](maquette/Socle%20commun%20-%207%20vues.html), version 1795551044). Données d'exemple au lundi 23 novembre.*

## 1. Ce que dit la maquette

Le carnet suit une seule grammaire, sur mobile (390 × 844) comme sur ordinateur (1440 × 900).
On retrouve sur chaque vue le même en-tête, le même « Mot de Gaston », la même barre d'outils avec la règle des temps,
le même langage d'étape et la même fiche. Un seul bouton rond, **Noter**, ouvre Gaston.

### 1.1 Les six décisions affichées en tête de maquette

| # | Décision | Conséquence pour la PWA |
|---|---|---|
| M1 | **Noter, seule porte vers Gaston.** Le médaillon flottant disparaît sur mobile. Sur ordinateur, le même bouton rond se place en bas à droite | `BoutonCompagnon` (médaillon + bulle d'accueil) est retiré. Noter devient un bouton rond partagé par la barre basse et le bureau |
| M2 | **Kalam = le carnet.** Seul le texte dicté ou écrit par le jardinier est en Kalam, à l'encre bleue (`#2B3A63`) sur papier crème (`#FBF8EF`) | C'est l'inverse de l'usage actuel : le nom « Gaston », le titre des cartes de proposition et « Mode Support » sont aujourd'hui en Kalam. Ils passent en Lora ou en police système |
| M3 | **Repère de vue.** Sur ordinateur, l'onglet actif est une pastille blanche dans le bandeau. Sur mobile, une pastille verte se place derrière l'icône | Restyler `TopBar` et `BottomNav`. Quand la vue active est rangée sous « Plus », ce bouton prend son nom et son icône |
| M4 | **Règle des temps.** Le bouton « Aujourd'hui » de la barre d'outils l'ouvre juste en dessous, dans toutes les vues | `RegleTemps` existe (US-279/US-223) mais s'ouvre par « Parcourir » depuis `DateRefPicker`. On garde un seul bouton date, qui passe en ambre tant qu'on regarde un autre jour |
| M5 | **Plan.** Le découpage de la piste C est repris tel quel : vue du dessus, rangs proportionnels, cartes dans l'ordre du chemin | Déjà livré par l'ÉPIC 19 (US-327, US-329). Il reste à l'aligner sur le socle (en-tête, barre d'outils, légende repliable, appui long) |
| M6 | **Catalogue et récoltes.** Cultures › onglet Catalogue permet d'ajouter une culture via Gaston. Stocks › Récoltes par saison | Ce sont deux écrans nouveaux, construits sur des lectures qui existent déjà (`GET /cultures/vue`, `GET /stats/rendement?annee=`) |
| M7 | **Mode sombre** (version 2) : le bouton lune du bandeau fait passer toutes les vues en sombre (surfaces, textes, Mot de Gaston, carnet). Les couleurs d'étape ne changent pas, et le texte posé dessus reste foncé (`#16210C`) | `useTheme` et la classe `.dark` existent. Les tokens sombres de la maquette (classe `.dk`) les remplacent |

### 1.2 L'anatomie commune d'une page : cinq bandes, toujours dans cet ordre

1. **En-tête de page.** Titre en Lora et une ligne de contexte. Des onglets de sous-vue n'apparaissent que pour Tableau de bord, Plan et Cultures : tuiles de 84 × 64 sur ordinateur, pastilles compactes de 36 px sur mobile. L'en-tête ne contient ni export ni aide.
2. **Mot de Gaston.** Ce que Gaston sait pour cet écran, en deux phrases au plus, avec une à trois actions. Les actions qui écrivent ouvrent Gaston déjà renseigné. Le mot est masqué quand Gaston n'a rien à dire, et le jardinier peut le refermer (×).
3. **Barre d'outils**, toujours dans cet ordre : date (« Aujourd'hui »), recherche, Filtrer avec le nombre de filtres actifs, menu ⋯ (exports CSV/JSON, aide de la vue ; les pièces jointes de la maquette sont écartées, D10). Rien d'autre ne s'y ajoute.
4. **Contenu.** C'est la seule bande qui défile. Dès qu'on descend, l'en-tête se resserre (titre en 18 px, ligne de contexte masquée) et le Mot de Gaston tient sur une ligne. Un appui sur ce mot remonte en haut. Le contenu est trié par ce qui demande une action, et chaque culture porte sa pastille d'étape.
5. **Fiche commune.** Toucher une culture, où qu'elle apparaisse, ouvre la même fiche : une feuille sur mobile, un panneau de 400 px à droite sur ordinateur. Elle a deux onglets, Suivi et Référence.

**N. Noter**, rond, au centre de la barre basse. Sa pastille montre ce qui sera noté : l'emoji de la culture ouverte, sinon le micro.

Règle transverse : **une bande sans contenu disparaît.** Elle n'est jamais remplacée par un placeholder.

### 1.3 Les pièces du socle

| Pièce | Spécification de la maquette | Existant |
|---|---|---|
| Pastille d'étape (`stk`) | Carré arrondi de 40 px (30 px en petit), fond aux couleurs de l'étape, pictogramme de 21 px. **Hachuré = prévu, à confirmer** (rayures à −45°, filet `#6B7B55`). **Point orange `#D9822B` = dû aujourd'hui ou en retard** | `EtapeCulture`, `PastillePhase`, `lib/etapes.js` (US-321) : mêmes libellés et pictogrammes. Couleurs et formes à aligner |
| Puce d'étape (`stc`) | Pilule avec pictogramme et libellé ; « · prévu » en variante hachurée | Partiel |
| Couleurs d'étape | Semé `#E6CFA2` · Levé/Planté/**En godet** `#CDE9A6` · En croissance `#86C163` · En fleur `#F4D35E` · En récolte `#F2A54A` · Terminé `#DADAD2`. La version 2 ajoute le pictogramme **En godet** (un godet et deux feuilles), utilisé par les stades de la pépinière : En levée → Levé, En godet → En godet, Endurcissement → En croissance, Prêt à sortir → Planté | À reprendre dans les tokens. Aujourd'hui, `lib/parcours.js` a sa propre palette de stades |
| Mode sombre | `--bg #11160F`, `--surface #1A2117`, `--alt #232C1F`, `--bd #323D2C`, `--brand #7DB548`, `--brand-text #A8D072`, `--txt #E6ECDD`, `--txt2 #AEB9A3`, `--ink #B9C8F2`, `--paper #24211A`, etc. Les cases de calendrier gardent leurs couleurs claires, et le plan est atténué (`brightness .8`) | Tokens sombres actuels à remplacer |
| Calendrier 12 mois (`cal`) | Douze cases de 9 px aux six couleurs, le mois courant cerclé. Le survol (ou l'appui long) donne « nov. (ce mois-ci) · récolte ». Ce même calendrier sert dans Cultures, le catalogue et la fiche Référence | `MonthStrip` (palette propre), à remplacer |
| Infobulle d'étape | Survol à la souris, **appui long de 380 ms au doigt** sur une pastille, un rang ou un mois | Absente sur mobile |
| Note du carnet (`note`) | Papier crème, méta « 🎤 Dicté · aujourd'hui · Fève » ou « ✎ Écrit · 5 nov. », texte en Kalam 16,5 px | Absente comme composant |
| Mot de Gaston (`mg`) | Fond `brand-soft`, visage de Gaston de 40 px, « Gaston · ce matin », 1 à 3 actions en pilules (la principale en vert plein), × de 30 px | Absent. `AujourdhuiPotager` (US-328) et `BandeauFile` jouent une partie du rôle |
| Barre d'outils (`tb`) | Contrôles de 40 px : date, recherche flexible, Filtrer + compteur, ⋯. Sous 520 px de conteneur, Filtrer se réduit à l'icône | Dispersée : `DateRefPicker`, `BarreActivitePlan`, `SearchField`, `CultureFilter`, exports en ligne dans Stocks et Journal |
| Règle des temps | Encart sous la barre d'outils. Il se glisse au doigt ou à la souris avec inertie ; la molette et ← → marchent sur ordinateur (Maj = 7 jours). Toucher un mois y saute, ‹ › avancent d'un jour. Libellé en police système 14 px sur une ligne, « il y a 11 j », bouton « Aujourd'hui » et × | `RegleTemps.jsx` + `lib/regleTemps.js` : la mécanique existe, c'est le point d'entrée qui change |
| Navigation | Bandeau en dégradé `#2F5416 → #4E8226`, 60 px de haut. Barre basse avec « ind » de 56 × 30 et Noter de 62 px qui déborde de 30 px | `TopBar`, `BottomNav` (US-325 : Accueil, Plan, Noter, Pépinière, Plus) |

## 2. Les sept vues

| Vue | Question à laquelle elle répond | Contenu dessiné | Mot de Gaston d'exemple |
|---|---|---|---|
| **Tableau de bord** | Que faire aujourd'hui ? | Onglets Vue d'ensemble / Statistiques. Deux colonnes sur ordinateur : « À faire aujourd'hui · n », « Récoltes possibles · n » (Tout voir), « Météo · 3 jours » (le gel en ambre), « Dernières notes du carnet » (Kalam, lien Journal). Le tableau de bord n'a pas de barre d'outils | « Gel annoncé samedi (−2 °C). Voilez la mâche… » → *Voir les levées*, *Noter le voilage* |
| **Plan** | Où en est chaque parcelle ? | Onglets Plan / Rotation · à venir (désactivé). Bandeau « Au 23 novembre · fond photo · 25 × 15 m ». Sur mobile : plan réduit, « Légende » repliable, « 3 à confirmer » et « 3 à libérer », puis les cartes de parcelles dans l'ordre du chemin. La carte d'une pépinière renvoie à Ma pépinière. Sur ordinateur : plan à 42 px/m, rose des vents, échelle de 5 m, légende complète | « 3 rangs à libérer… un engrais vert de seigle peut encore y être semé » → *Voir les rangs*, *Noter* |
| **Cultures · Au potager** | Où en sont mes cultures ? | Onglets « Au potager · 25 » et « Catalogue · 109 ». Légende du calendrier repliable. Groupes : À confirmer, En récolte, En croissance, Semé ou planté, Terminé · rang à libérer. Chaque carte montre la pastille, le nom, la variété, l'état (en orange s'il est dû), le calendrier et l'emplacement | « 3 levées à confirmer. L'épinard a 2 semaines de retard » → *Confirmer la fève* |
| **Cultures · Catalogue** | Que puis-je ajouter ? | Les 109 espèces, groupées par prochaine fenêtre de semis : « À semer d'ici mars », « Plus tard dans la saison », « Déjà au potager ». En bas : « Une culture absente du catalogue ? Dites-la à Gaston ». La barre d'outils n'a pas de bouton date | « Le céleri-rave se sème en mars… » → *Ajouter le céleri-rave* |
| **Pépinière · Parcours** (v2) | Que semer, où en sont mes plants ? | Trois onglets d'en-tête : **Parcours**, **Semer · n**, **Lots · n**. Parcours = **emplacement × stade**. Sur ordinateur, c'est une matrice : une ligne par emplacement (Serre chaude, Châssis froid, Sans emplacement « à ranger », chaque ligne teintée), et une colonne par stade (En levée, En godet, Endurcissement, Prêt à sortir · n). Sur mobile, **un stade à la fois**, avec défilement aimanté et points, et les lots groupés par emplacement dans la colonne. Carte de lot : emoji, nom, n°, « variété · quantité · semé le … », alerte orange (« pas levé après 34 j »), note en Kalam | « **2 lots à régler** : l'oignon blanc n'a pas levé après 34 jours, le chou-fleur attend un emplacement. » → *Ranger le chou-fleur*, *Voir les lots* |
| **Pépinière · Semer** (v2) | Le bon moment pour semer | La bande « bon moment pour semer » devient un onglet. **Fenêtre ouverte · n** (« fenêtre ouverte · graines en stock · aucun lot de la culture en cours ») : une tuile par culture avec « reste 7 j », une barre de la part de fenêtre écoulée, les dates de la fenêtre, le type de pépinière, les variétés et un bouton **Semer** (qui ouvre Gaston). Puis **Fenêtre ouverte, mais rien à semer · n** (« Graines épuisées : à racheter », « Un lot est déjà en cours (#59) »). Puis **Bientôt** (« dans 45 j · semis en pépinière froide à partir du 7 janv. ») | « **3 cultures sont dans leur fenêtre** et vous avez les graines. L'oignon blanc ferme dans 7 jours. » → *Semer l'oignon blanc* |
| **Pépinière · Lots** (v2) | Le registre de la saison | Bilan « 18 lots cette saison · 14 en cours dont 2 à régler · 4 terminés, 34 plants sortis vers le potager ». Filtres En cours / À régler / Terminés / Tous avec leurs comptes : boutons segmentés sur ordinateur, points glissés sur mobile (comme le Parcours). Lots groupés par mois de semis. Une ligne = n°, pastille de stade, culture · variété, emplacement · quantité · date, **frise des gestes datés**, alerte. « Registre sans geste : on agit depuis le Parcours ou par Noter » | « **2 lots à régler** : … » → *Voir les lots à régler* (filtre) |
| **Fiche du lot** (v2) | Tout sur ce lot | Feuille ou panneau droit. « Lot #57 · Oignon blanc », variété · quantité, stade en puce, emplacement, alerte, **Noter** et **Voir au Parcours**, « Gestes datés » en frise, « Carnet du lot » en Kalam | — |
| **Stocks** | Qu'ai-je, que vais-je manquer ? | Quatre chiffres : unités au potager, godets à replanter, **kg récoltés (tuile cliquable → Récoltes par saison)**, unités perdues. Cartes par famille avec pastille, quantité et unité. Familles et ordre alphabétique passent dans Filtrer, les exports dans ⋯ | « 14 godets de chou pommé attendent une place… je l'y propose ? » → *Oui, proposer* |
| **Stocks › Récoltes par saison** | Comment se compare cette saison ? | Feuille ou panneau. Une barre par année (2024, 2025, 2026). Toucher une année affiche ses cultures en barres. Mention : « Le détail mois par mois reste dans Tableau de bord › Statistiques » | — |
| **Journal** | Qu'est-il arrivé ? | Jours en capitales. Les notes du jour sont regroupées en « n notes » : la première en Kalam, puis « + n autres ». Les notes sans texte sont comptées, pas listées. Gestes en ligne (récolte, paillage, perte) | « Cette semaine : 1 récolte (1,2 kg), 1 paillage et 6 notes, dont 4 dictées. » (sans action) |
| **Fiche commune** | Tout sur cette culture | En-tête (emoji 52 px, nom en Lora 21 px, variété · quantité), « Planche centrale · rang 3 — Voir au plan → », étape courante « depuis le … », total récolté et nombre de récoltes, **Noter** (ou « Noter la levée » si l'étape est prévue). Onglets **Suivi** (Étapes en frise verticale, Carnet de la culture = Journal filtré, Origine) et **Référence** (calendrier de l'espèce, espacement, rotation) | — |
| **Fiche catalogue** | Cette espèce, avant de l'avoir | Pilule « Pas encore au potager » ou « Au potager », fenêtre de semis, *Ajouter à mon potager* (ou *Ouvrir la culture en place*). Calendrier, variétés du catalogue, espacement, famille (« Gaston choisira une parcelle qui respecte la rotation ») | — |

## 3. Le compagnon : ce que montrent les exemples

La maquette refait l'écran de Gaston. C'est le plus gros écart avec l'existant (`PanneauCompagnon.jsx`, 786 lignes,
construit sur la maquette `Compagnon.html` pour US-271).

### 3.1 Forme

| Élément | Maquette | Existant |
|---|---|---|
| Ouverture | **Mobile : plein écran** (feuille qui occupe tout l'écran). **Ordinateur : panneau droit de 400 px**, à la place de la fiche. Le bouton Noter flottant disparaît tant que Gaston est ouvert | Panneau propre, ouvert par le médaillon ou par Noter |
| En-tête | Visage de 38 px, « Gaston » en Lora 17 px, sous-titre « connaît votre potager et la météo », × | Nom en Kalam 24 px |
| Contexte | Bandeau `alt` : « 🫘 Fève · Planche centrale · rang 6 » et × pour le retirer | Existe (US-323 : « À propos de… », Préciser) : restyler |
| Bulle de Gaston | Fond `alt`, coin bas-gauche de 5 px, 88 % de large au plus | Bulle avec avatar |
| Bulle du jardinier | **Papier crème, texte en Kalam**, méta « 🎤 Dicté · 0:06 » ou « ✎ Écrit » | Bulle standard |
| Carte de proposition | « **À enregistrer** » sur fond `brand-soft` et bord vert de 1,5 px. Chaque écriture est une ligne : pastille d'étape (hachurée si prévue) + « **Levée** · Fève, Planche centrale · rang 6 · aujourd'hui » ; une note au carnet s'affiche avec sa citation en Kalam. Boutons **Corriger** et **Confirmer** | `CarteProposition` : une carte par proposition, titre en Kalam, bord pointillé |
| Suggestions | Pilules de 34 px **selon le contexte** : levée prévue → « J'ai vu la levée », « Pas encore » ; en récolte → « Récolte », « Note » ; terminé → « Libérer le rang », « Note » ; catalogue → les variétés ; sans contexte → « Récolte », « Semis », « Observation ». Toujours en dernier : « Photo · bientôt », désactivé | Absentes |
| Saisie | Champ pilule de 44 px « Écrire à Gaston… » et **micro rond de 54 px** en dégradé vert | Saisie + dictée (US-302), écoute (US-304) |

### 3.2 Les trois scénarios dessinés

1. **Levée à confirmer, ouvert depuis la fiche (« Noter la levée »)** : Gaston ouvre sur « Vous êtes sur fève. Dites ce que vous voyez, ou touchez une suggestion. » Le jardinier dicte. Gaston répond « C'est la levée prévue aujourd'hui. Je l'enregistre avec votre note », puis une carte à deux lignes (Levée + Note au carnet), et le jardinier confirme.
2. **Culture ouverte, sans étape due** : « Vous êtes sur chou de Bruxelles, en récolte. Une récolte, une observation ? » avec les suggestions Récolte et Note.
3. **Ajouter depuis le catalogue** : le jardinier écrit « Ajouter le céleri-rave à mon potager ». Gaston répond « Bonne idée. Semer en pépinière chaude en mars : je prévois le semis et un rappel. Quelle variété ? », avec une carte « Nouvelle culture · Céleri-rave, Monarch » (pastille Semé hachurée) + « Rappel · semis en pépinière le 2 mars », et les variétés en suggestions. **Ajouter ne crée rien directement**, il faut confirmer.

### 3.3 Règles à tenir

- **Rien n'est écrit sans Confirmer.** Le chemin proposer → confirmer → exécuter (A16, US-344) reste tel quel. La carte à plusieurs lignes est une présentation : chaque ligne reste une proposition confirmée par le chemin existant.
- **La phrase d'ouverture et les suggestions ne coûtent aucun appel au modèle.** Elles se déduisent du contexte (culture, étape, échéance, fiche catalogue). Le modèle ne répond qu'au premier message envoyé.
- Le moteur (actuel ou `COMPAGNON_MOTEUR=capacites`, US-342) ne change pas dans cet épic : il reçoit le contexte d'écran (US-323) et les messages, comme aujourd'hui.

## 4. Écarts avec la PWA

| Domaine | Ce qui existe et se garde | Ce qui change | Ce qui manque |
|---|---|---|---|
| Tokens | Fond, marque, dégradé du bandeau (identiques) | Couleurs d'étape, ambre « autre jour », orange « dû », encre et papier du carnet, violet pépinière | — |
| Coquille | `App.jsx`, `NavigationContext`, `navigation.js` (NAV, NAV_MOBILE, Plus) | En-tête fixe et contenu seul défilant, resserrement au défilement, pastilles de repère, Noter rond sur ordinateur, panneau droit partagé fiche/Gaston | Composants `MotDeGaston`, `BarreOutils`, `MenuVue` |
| Plan | Vue du dessus, `PlanMobile`, `DetailParcelle`, éditeur (US-326→333) | Onglets Plan / Rotation · à venir revenus dans l'en-tête (US-330 les avait retirés), légende repliable, « n à confirmer / n à libérer » | — |
| Cultures | `GET /cultures/vue`, cartes, frise, fiches (US-204/206/207) | Groupes par action, onglets Au potager / Catalogue, filtres familles déplacés dans Filtrer | Écran Catalogue |
| Fiche | `FicheCulture` (6 sections), `SuiviCulture` (US-322), `FicheCalendrier` | **Une seule fiche** : Suivi (= `SuiviCulture`) + Référence (= contenu de `FicheCulture`) | — |
| Pépinière | `OngletParcours` (kanban emplacement × stade, bande « bon moment pour semer »), `OngletLots` (registre, filtres En cours / À régler / Terminés), `FicheLot` | Trois onglets d'en-tête. La bande des semis devient l'onglet Semer. Matrice sur ordinateur, un stade à la fois sur mobile, filtres des lots en points sur mobile. Fiche du lot au format de la fiche commune | Dans Semer : les cultures **écartées** avec leur motif (lot en cours, graines épuisées) et **plusieurs** prochaines ouvertures. Ce sont des champs à ajouter à la lecture existante (`echeances_lots`), sans migration |
| Stocks | 4 repères, familles, exports | Exports dans ⋯, familles dans Filtrer, tuile kg cliquable | Feuille Récoltes par saison (lecture existante, une par année) |
| Journal | `GET /historique`, regroupements | Notes regroupées en « n notes » + Kalam, notes vides comptées | — |
| Compagnon | Fil, propositions, dictée, voix, contexte d'écran, file des gestes | Forme complète (§3.1), plein écran mobile, panneau droit sur ordinateur | Suggestions et phrase d'ouverture selon le contexte, carte à plusieurs lignes |
| Backend | Toutes les lectures nécessaires existent | Deux champs ajoutés à la lecture du parcours de la pépinière (onglet Semer) | **Aucune migration. Aucune route nouvelle** |

## 5. Décisions proposées

| # | Décision | Pourquoi |
|---|---|---|
| D1 | **Le Mot de Gaston est calculé sans modèle**, à partir des lectures déjà chargées par la vue (tâches du plan, météo, lots, stocks, historique) et des signaux du veilleur (`GET /compagnon/etat`). Une règle par vue, qui donne au plus deux phrases et trois actions | Zéro jeton par affichage d'écran, aucune dérive, et testable |
| D2 | Kalam est réservée au texte du jardinier. Le nom de Gaston, les titres de carte et « Mode Support » passent en Lora | Décision M2 de la maquette |
| D3 | Un seul bouton date par vue (« Aujourd'hui »), qui ouvre la règle des temps sous la barre d'outils. `DateRefPicker` et `BarreActivitePlan` disparaissent | Décision M4 de la maquette |
| D4 | La fiche commune remplace l'ouverture séparée de `FicheCulture` et de `SuiviCulture`. `FicheCalendrier` reste empilable depuis Référence | Une seule fiche, d'où qu'on vienne |
| D5 | Le médaillon flottant (`BoutonCompagnon`, bulle d'accueil) est supprimé. Le compteur de messages non lus (US-272) passe sur la pastille de Noter | Décision M1 de la maquette |
| D6 | Les vues non dessinées (Statistiques, Paramètres, Pilotage, Onboarding, Connexion) reçoivent la coquille sans refonte de contenu | Périmètre tenu |
| D7 | Sous 900 px, la PWA garde la mise en page mobile (barre basse), et donc aussi à 768 px. Au-delà, mise en page ordinateur | Règle existante (`frontend/CLAUDE.md`) ; la maquette ne dessine pas 768 px |
| D8 | **Pépinière en trois onglets** (Parcours, Semer, Lots), selon la version 2 de la maquette | Réponse à Q1 |
| D9 | **Ajout depuis le catalogue** : la carte « À enregistrer » propose le **rappel de semis** (US-345). Si une variété est donnée, elle propose aussi l'ajout de la variété au référentiel du potager. La ligne « Nouvelle culture » ne s'affiche que si une écriture correspondante existe | Réponse à Q2 : recommandation retenue |
| D10 | **Pièces jointes supprimées** pour l'instant : l'entrée n'existe pas dans le menu ⋯ | Réponse à Q3 |
| D11 | **Tableau de bord figé sur la maquette.** La personnalisation (US-078, `ModalPersonnaliserDashboard`, `useDashboardWidgets`) est retirée | Réponse à Q4 |
| D12 | **Mode sombre réactivé** avec les tokens sombres de la version 2 de la maquette, sur toutes les vues | Réponse à Q5 |

## 6. Questions ouvertes

Les cinq questions sont tranchées le 24/11/2026 (décisions D8 à D12). Il n'en reste aucune.
