---
titre: Guide d'exploitation de l'application
famille: doc_app
source: Guide de l'Assistant Potager
niveau_confiance: a-valider
version: 4.0
# `titre` est indexé au poids d'un titre sur CHAQUE fragment de ce document et
# s'affiche avec la réponse : il évite volontairement « potager » et
# « assistant », mots présents dans presque toutes les questions, qui feraient
# remonter ce document devant les fiches courtes de `data/connaissance/doc_app/`.
# `niveau_confiance: a-valider` est délibéré et non provisoire : un fragment de
# ce document est un chapitre entier, trop long pour être servi mot pour mot
# dans un message. Il descend en contexte vers l'étage de raisonnement, qui
# rédige. Les fiches courtes de doc_app/, elles, sont `verifie` et servies
# telles quelles — c'est leur raison d'être.
# Index de relecture, non indexé (règle 4 de data/connaissance/README.md) :
index_terms:
  - "guide d'utilisation"
  - "manuel de l'application"
  - "aide-mémoire des commandes"
  - "comment ça marche"
---

# 🌿 Guide de l'Assistant Potager

**Version 4.0 — septembre 2026** · *correspond à la version 3.54 de l'application*
*Guide d'exploitation — le compagnon de terrain Telegram et le tableau de bord web*

---

> **Comment lire ce guide**
>
> La **Partie I** explique la solution : à quoi elle sert, ce qu'elle fait et ce qu'elle ne fait pas, et les quelques idées qui expliquent tout le reste.
> La **Partie II** suit l'ordre d'une saison de culture, du premier semis au dernier arrachage, et dit **quoi faire, dans quel ordre, avec quels mots**.
> La **Partie III** est l'aide-mémoire : les 23 commandes, les formulations reconnues, le glossaire et le dépannage.
>
> Si vous débutez, lisez les chapitres 1 à 5 puis suivez la saison. Si vous cherchez une commande précise, allez directement à l'aide-mémoire en Partie III.
>
> **Une convention de rédaction :** chaque section de ce guide répond à **une** question, et se lit sans avoir lu la précédente. C'est ce qui permet de la servir telle quelle au jardinier qui pose cette question-là.

---

# PARTIE I — COMPRENDRE LA SOLUTION

---

## 1. Vue d'ensemble

### 1.1 À quoi sert l'Assistant Potager

L'Assistant Potager est un **carnet de bord de jardinier**, alimenté à la voix depuis le terrain et consultable depuis n'importe quel écran.

Le principe est simple : chaque fois que vous faites quelque chose au potager — semer, arroser, récolter, constater une maladie — vous le dites à voix haute dans Telegram. L'assistant transcrit, comprend, vous montre ce qu'il a compris, et l'enregistre une fois que vous confirmez.

Au fil de la saison, ce carnet se transforme en mémoire exploitable. Vous pouvez alors savoir :

- combien de kilos de tomates vous avez récoltés cette année, et à quelle période ;
- ce qui pousse actuellement dans chaque parcelle, et depuis combien de jours ;
- combien de plants il vous reste en godet, et lesquels attendent d'être mis en terre ;
- quel était l'état de votre potager le 15 mai dernier ;
- quand vous avez traité les rosiers pour la dernière fois, et avec quoi ;
- si la culture que vous vous apprêtez à planter revient trop tôt sur cette planche.

### 1.2 Ce que l'application fait — et ne fait pas

**Ce qu'elle fait bien**

| Domaine | Détail |
|---|---|
| **Saisie terrain** | Dictée vocale mains sales, en langage naturel, sans formulaire |
| **Mémoire fiable** | Tout est daté, structuré, corrigeable, jamais perdu |
| **Traçabilité pépinière** | Chaîne complète graine → godet → plant en terre → récolte, lot par lot |
| **Consultation** | Bilans par culture, par variété, par parcelle, état à une date passée |
| **Rotation et voisinage** | Délai de retour par famille botanique, associations entre cultures, avertissement au moment de planter |
| **Fiches de culture** | Famille, délai de retour, exposition, besoin en eau, profondeur de semis, rusticité |
| **Météo** | Relevé quotidien automatique, historique consultable, conseil du jour |
| **Explication de lui-même** | Une question sur le fonctionnement de l'application reçoit une réponse écrite et relue, pas une improvisation |

**Ce qu'elle ne fait pas**

L'assistant est d'abord **rétrospectif** : il enregistre et restitue ce que vous avez fait. Il commence à vous avertir sur la rotation et le voisinage des cultures, mais il ne pilote pas votre saison. Concrètement, il n'y a aujourd'hui **pas** de :

- calendrier de semis ni de rappel proactif — l'assistant ne vous écrit jamais le premier pour dire « il est temps de semer les poireaux » ;
- diagnostic de maladie à partir d'une photo — les images ne sont pas traitées ;
- prévision de récolte ni calcul de rentabilité ;
- stock de semences ou d'intrants : ce que l'application appelle « stock », c'est le nombre de **pieds en terre** et de **plants en godet**, jamais un sachet de graines dans un tiroir.

Savoir cela vous évitera d'attendre de l'assistant ce qu'il ne peut pas donner — et vous montre où il excelle : **ne jamais oublier ce que vous avez fait**.

### 1.3 Les deux façons d'accéder à l'application

L'Assistant Potager a **deux visages**, qui partagent exactement les mêmes données.

```
                    ┌─────────────────────────┐
                    │   VOTRE CARNET DE BORD  │
                    │      (données uniques)  │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┴──────────────────┐
              │                                     │
      ┌───────┴────────┐                  ┌─────────┴───────┐
      │   TELEGRAM     │                  │  TABLEAU DE BORD│
      │ (le compagnon) │                  │      (web)      │
      ├────────────────┤                  ├─────────────────┤
      │ Au potager     │                  │ Au calme        │
      │ Mains sales    │                  │ Sur écran       │
      │ À la voix      │                  │ Visuel          │
      │ ÉCRIRE         │                  │ LIRE            │
      └────────────────┘                  └─────────────────┘
```

| | **Telegram** | **Tableau de bord web** |
|---|---|---|
| **Quand** | Sur le terrain, pendant l'action | Le soir, au bureau, en planification |
| **Comment** | Vocal ou texte, langage naturel | Navigation tactile, filtres |
| **Sert à** | **Enregistrer** ce que vous faites | **Comprendre** où vous en êtes |
| **Consultation** | Possible, en texte | Bien plus lisible, graphique |
| **Saisie** | Complète | Aucun geste de jardin — seulement le potager, ses parcelles de départ et ses membres |

**Règle pratique :** *tout ce qui s'écrit au jour le jour passe par Telegram, tout ce qui se regarde passe par le web.*

Rien ne vous empêche de consulter depuis Telegram — `/plan`, `/stats` et `/historique` répondent très bien. Mais un plan de parcelles ou une courbe de rendement se lisent nettement mieux sur le tableau de bord.

### 1.4 Comment ça marche, en une page

Quand vous envoyez un message vocal :

1. **Vous parlez** dans Telegram — par exemple *« Récolté 2 kilos de tomates cerise en parcelle nord »*.
2. **L'assistant transcrit** votre voix en texte.
3. **Il identifie votre intention** : est-ce un geste à enregistrer, une question, une demande de statistiques, une correction ?
4. **Il extrait les informations** : le geste (récolte), la culture (tomate), la variété (cerise), la quantité (2), l'unité (kg), la parcelle (nord), la date (aujourd'hui par défaut).
5. **Il vous montre un récapitulatif** et attend votre validation.
6. **Vous confirmez** — et seulement à ce moment l'information est enregistrée.

Cette étape de confirmation est importante : **rien n'est jamais enregistré à votre insu**. Si l'assistant a mal compris, vous annulez et vous redictez.

---

## 2. Les principes de fonctionnement

Quatre notions à comprendre une bonne fois pour toutes. Elles expliquent tout le reste du guide.

### 2.1 Tout est un événement daté

L'assistant ne raisonne pas en « fiches » ou en « stocks » que l'on modifierait. Il raisonne en **événements** : des faits datés, empilés dans l'ordre chronologique.

Vous n'écrivez jamais « j'ai 12 plants de tomates ». Vous écrivez :

- *« Semé 30 graines de tomate Cœur de bœuf »* (le 5 mars)
- *« Mise en godet 24 tomates Cœur de bœuf »* (le 28 mars)
- *« Planté 12 tomates Cœur de bœuf parcelle nord »* (le 3 mai)
- *« Perdu 2 pieds de tomate, gel »* (le 6 mai)

Et l'assistant **calcule** : 12 plantés − 2 perdus = 10 pieds actifs, avec 12 plants encore en godet.

**Conséquence pratique n° 1** : ne « corrigez » pas un stock en essayant de dicter le total. Il n'existe aucun bouton pour cela. Enregistrez l'événement qui a fait bouger le stock (une perte, une récolte, une vente), et le total se recalcule seul.

**Conséquence pratique n° 2** : comme tout est daté, l'assistant peut reconstituer l'état de votre potager **à n'importe quelle date passée**. C'est ce qui permet de répondre à « qu'est-ce qui poussait en parcelle nord le 1er mai ? ».

**Conséquence pratique n° 3** : la date qui compte est celle du **geste**, pas celle de la saisie. Dire « planté hier » range l'événement à hier, y compris dans tous les calculs.

### 2.2 Le cycle de vie d'une culture

L'assistant suit vos plantes de la graine à l'assiette. Chaque étape est un type d'événement différent, et c'est **la succession de ces étapes qui donne des chiffres justes**.

```
   🌱 SEMIS
   « semé 30 graines de tomate Cœur de bœuf »
      │
      │  (germination)
      ▼
   🪴 MISE EN GODET
   « mise en godet 24 tomates Cœur de bœuf »
      │                    → taux de réussite : 24/30 = 80 %
      │
      ├───────────────► 💰 VENTE  « vendu 5 plants de tomate »
      │
      ├───────────────► ❌ PERTE EN GODET  « perdu 2 plants en pépinière »
      │
      ▼
   🌿 PLANTATION
   « planté 12 tomates Cœur de bœuf parcelle nord »
      │                    → stock godet restant : 24 − 12 − 5 − 2 = 5
      │
      ├───────────────► ❌ PERTE  « perdu 2 pieds, gel »
      │
      │  (entretien : arrosage · paillage · binage · éclaircissage
      │               taille · tuteurage · traitement · protection)
      │
      ▼
   🧺 RÉCOLTE
   « récolté 2 kg de tomates Cœur de bœuf parcelle nord »
```

Chaque étape retire automatiquement du stock de l'étape précédente. Le calcul se fait **par couple culture + variété** : planter des courgettes jaunes ne touche pas au stock de courgettes vertes.

**Cas particulier — le semis direct.** Certains légumes ne passent jamais par la pépinière : carottes, radis, haricots, épinards. Vous les semez directement en pleine terre. Dans ce cas, il n'y a ni étape godet ni étape plantation : le semis entre directement au stock de la culture, et vous passez du semis à la récolte. Précisez-le en dictant : *« semis direct carottes en parcelle B »*.

### 2.3 Les parcelles structurent tout

Une **parcelle** est une zone identifiée de votre potager : une planche, un carré, un bac, une butte, une serre, un rang. Vous leur donnez les noms que vous voulez — *nord*, *maison*, *planche-oignon*, *B2*.

Mentionner la parcelle dans vos dictées n'est jamais obligatoire, mais **c'est ce qui débloque le plus de valeur** :

- vous pouvez filtrer toutes vos questions par zone ;
- le plan d'occupation vous montre qui pousse où ;
- vous voyez le taux d'occupation de chaque surface ;
- et surtout, c'est ce rattachement qui rend possible le **calcul de rotation** : sans lui, l'assistant ne peut pas savoir ce qui est passé sur cette planche les saisons précédentes.

Une parcelle peut être marquée comme **pépinière** (une serre, un châssis). Cette distinction compte : un semis rattaché à une pépinière reste considéré comme *en pépinière*, il n'est pas compté comme cultivé en pleine terre.

### 2.4 Un potager à la fois

Un même compte peut tenir **plusieurs potagers** — le jardin de la maison, celui des parents, le carré partagé de l'association. À tout moment, un seul est **actif** : c'est lui que visent vos dictées comme vos questions.

Rien ne se mélange jamais entre deux potagers : ni les parcelles, ni les cultures, ni l'historique, ni les notes. Une question posée dans un potager ne recevra jamais une réponse tirée d'un autre. Le changement de potager actif est un geste explicite (`/potager`), jamais automatique.

Si vous n'avez qu'un potager, vous n'aurez jamais à y penser : il est actif en permanence.

---

## 3. Activer le compagnon de terrain

*Cinq minutes, une seule fois.*

### 3.1 Pourquoi la conversation doit être reliée à un compte

Le bot Telegram ne fonctionne **que** s'il sait à quel compte — et donc à quel potager — la conversation appartient. Tant que ce lien n'existe pas, aucune donnée n'est lue ni enregistrée : le bot répond par un message d'accueil expliquant la marche à suivre, et rien d'autre.

C'est ce qui garantit que vos données ne sont visibles que de vous et des membres de votre potager.

### 3.2 Activer en un geste depuis l'application web

C'est le chemin normal, proposé juste après la création de votre premier potager :

1. Ouvrez l'application web et connectez-vous.
2. Sur l'écran d'accueil (ou dans le menu **Compte**), demandez l'activation du compagnon de terrain.
3. Touchez le bouton proposé — ou scannez le QR code affiché, depuis votre téléphone. La conversation Telegram s'ouvre.
4. Appuyez sur **Démarrer**.

L'assistant vous accueille en nommant votre potager : le lien est établi.

> **Pourquoi faut-il appuyer sur Démarrer ?** Un assistant sur messagerie ne peut jamais engager la conversation le premier. Tant que vous n'avez pas ouvert le dialogue, il lui est techniquement impossible de vous envoyer quoi que ce soit. C'est la raison de ce bouton, et non une formalité — un compte relié qui ne reçoit rien a presque toujours sauté cette étape.

### 3.3 Relier à la main avec un code

Si le bouton ne fonctionne pas (navigateur récalcitrant, téléphone différent de l'ordinateur), l'application affiche aussi un **code d'activation** : six caractères, valable **10 minutes**, utilisable **une seule fois**.

Dans la conversation Telegram, trois façons équivalentes de l'utiliser :

```
/lier VOTRECODE
```

…ou envoyez simplement le code tout seul, ou ouvrez le lien d'activation qui le contient.

Les refus possibles sont explicites : code inconnu, code expiré, code déjà utilisé, ou **conversation déjà reliée à un autre compte**. Dans ce dernier cas, il faut d'abord détacher la conversation de l'ancien compte.

### 3.4 Détacher la conversation

```
/delier
```

Le bot demande confirmation avant d'agir. Le lien entre cette conversation et votre compte est alors rompu : le bot cesse d'accéder à vos potagers.

**Aucune donnée de jardin n'est perdue** — ni les parcelles, ni les événements, ni les notes. Le compte web reste intact, et une nouvelle activation rétablira le lien plus tard, depuis le même téléphone ou un autre.

La même dissociation est disponible depuis le menu **Compte** de l'application web — utile précisément quand vous n'avez plus accès au chat lié (téléphone changé, compte Telegram perdu).

### 3.5 Changer de potager actif

```
/potager
```

Le bot liste vos potagers, le potager actif marqué d'une coche, et vous en changez d'un bouton. Le changement est immédiat et **mémorisé** : vous n'aurez pas à le refaire à la prochaine session.

Si vous n'êtes membre d'aucun potager, le bot vous le dit et vous invite à en créer un ou à en rejoindre un depuis l'application web — c'est là, et seulement là, que se créent les potagers.

---

## 4. Le tableau de bord web — accès et principes

### 4.1 Comment y accéder

Le tableau de bord s'ouvre dans un simple navigateur, sur téléphone comme sur ordinateur.

> **⚠️ À COMPLÉTER** — indiquer ici l'adresse de votre installation et les modalités d'accès.

Vous y créez votre compte (e-mail + mot de passe), vous validez le lien de vérification reçu par e-mail, puis vous créez votre premier potager. Le compagnon Telegram s'active ensuite depuis cet écran (chapitre 3).

### 4.2 L'installer sur votre iPhone

Le tableau de bord est une application web installable : une fois posée sur l'écran d'accueil, elle s'ouvre en plein écran, sans barre de navigateur, exactement comme une application native.

1. Ouvrez l'adresse du tableau de bord dans **Safari** (pas Chrome — l'installation ne fonctionne que depuis Safari sur iPhone).
2. Touchez le bouton **Partager** (le carré avec la flèche vers le haut).
3. Faites défiler et choisissez **« Sur l'écran d'accueil »**.
4. Nommez-la *Potager* et validez.

L'icône apparaît sur votre écran d'accueil. Vous pouvez maintenant l'ouvrir d'un geste.

### 4.3 Les principes de navigation

Le tableau de bord est conçu **pour le pouce** sur téléphone, et s'étale en largeur sur grand écran.

- **Cinq écrans de consultation** : Tableau de bord (vue d'ensemble et statistiques), Plan, Pépinière, Stocks et Journal. En bandeau haut sur ordinateur, en barre d'onglets basse sur téléphone.
- **Trois écrans annoncés mais pas encore disponibles** : Cultures, Vue plan à l'échelle et Rotation. Ils affichent ce qu'ils contiendront plutôt qu'un lien mort — en attendant, `/fiche` et `/rotation` répondent depuis Telegram.
- **Un sélecteur de date de référence** en tête d'écran, pour remonter dans le temps.
- **Un filtre par culture** sur les écrans qui listent des cultures.
- **Un thème clair et un thème sombre**, votre choix est mémorisé.

### 4.4 La date de référence — voir le potager dans le passé

C'est la fonction la plus puissante du tableau de bord, et la plus facile à manquer.

En haut de l'écran, un bouton affiche **« Aujourd'hui »**. Touchez-le : un calendrier s'ouvre, et vous choisissez n'importe quelle date passée. Les écrans se recalculent alors comme si vous étiez ce jour-là.

- Le bouton **change de couleur (ambre)** pour vous rappeler en permanence que vous n'êtes plus « en direct ».
- La date **vous suit d'un écran à l'autre** : réglée sur le Plan, elle reste active sur Stocks et Pépinière.
- Elle **survit à un rechargement** de page.
- Les dates futures ne sont pas sélectionnables.
- Pour revenir au présent, rouvrez le calendrier et touchez **« Aujourd'hui »**.
- L'écran **Journal** fait exception : il a son propre filtre de date, indépendant.

**Usages concrets :** comparer l'occupation de vos parcelles à la même date l'an dernier, retrouver l'état de votre pépinière au moment d'une vente de plants, vérifier ce qui poussait avant un arrachage.

La même chose est possible depuis Telegram, en donnant une date à `/plan` ou `/stats` :

```
/plan 15/05/2026
/stats tomate 2026-05-15
```

Le **filtre par culture**, lui, ne suit pas : il est propre à chaque écran et se remet à zéro quand vous changez de section. C'est volontaire — on filtre pour une consultation ponctuelle, pas pour une session entière.

---

# PARTIE II — LE PARCOURS D'UNE SAISON

Cette partie suit l'ordre chronologique d'une saison de culture. Chaque chapitre correspond à un moment de l'année et vous dit **quoi faire, dans quel ordre, et avec quels mots**.

---

## 5. Premiers pas — les cinq minutes qui comptent

### 5.1 Ouvrir la conversation et trouver les commandes

Une fois le compagnon activé (chapitre 3), ouvrez la conversation et envoyez :

```
/start
```

L'assistant vous accueille, rappelle le nombre d'événements déjà enregistrés dans votre potager et l'état de la synthèse vocale.

**Où sont les commandes ?** Dans le **menu natif de Telegram** : le bouton **Menu**, à gauche de la zone de saisie. Il liste toutes les commandes du bot avec, pour chacune, une phrase d'explication. Une commande touchée est insérée dans la zone de saisie, prête à être complétée.

> Il n'y a plus de clavier de boutons permanent en bas de l'écran : il occupait l'espace en permanence pour proposer cinq raccourcis, là où le menu en propose vingt sans rien masquer. Les boutons de validation, eux, n'ont pas changé — ils apparaissent au moment où l'assistant vous pose une question, et disparaissent après.

### 5.2 L'aide en ligne

```
/help
```

C'est votre référence permanente. Elle liste les gestes reconnus, les commandes disponibles et des exemples de phrases.

Vous pouvez aussi demander une **aide ciblée** sur un domaine précis :

```
/help parcelle    /help semis     /help godet
/help recolte     /help stock     /help stats
/help note        /help culture   /help fiche
```

Chacune donne les variantes de saisie reconnues pour ce domaine, avec des exemples concrets. Un mot-clé inconnu vous renvoie la liste des mots-clés valides plutôt qu'une erreur.

**`/help` est un sommaire, pas un manuel.** Pour une explication plus longue, posez simplement la question en toutes lettres : *« comment est calculé mon stock ? »*, *« pourquoi mon semis n'apparaît pas en pépinière ? »*. L'assistant sait expliquer son propre fonctionnement (section 15.5).

### 5.3 Créer vos parcelles — à faire en premier

**C'est la seule chose qu'il faut vraiment configurer avant de commencer.** Tout le reste s'apprend en marchant.

```
/parcelle ajouter nord
/parcelle ajouter nord sud 12.5
```

Les paramètres se donnent dans cet ordre : **nom**, puis **exposition**, puis **superficie en m²**. Seul le nom est obligatoire.

Le bot vous montre les parcelles existantes et demande confirmation avant de créer. Il détecte aussi les doublons proches : si vous avez déjà une parcelle *Serre Froide* et que vous tapez *Serre-froide*, il vous alerte plutôt que de créer un doublon silencieux.

**Conseils de nommage :**

- Restez courts et prononçables — vous allez les dicter des centaines de fois.
- Évitez les tirets bas (`_`) qui perturbent l'affichage.
- Préférez des noms évocateurs (*planche-oignon*, *maison*) aux codes abstraits (*P3*) : vous les reconnaîtrez mieux dans six mois.
- Les noms sont insensibles à la casse et aux accents.

Les parcelles se créent aussi depuis l'application web, mais uniquement pendant l'assistant de création du potager. Ensuite, c'est ici, depuis le compagnon de terrain, que la vie des parcelles se gère.

### 5.4 Ajuster une parcelle

```
/parcelle modifier nord exposition=sud
/parcelle modifier nord superficie=8.5
/parcelle modifier nord exposition=sud superficie=8.5
/parcelle modifier serre pepiniere=true
```

| Paramètre | Valeurs | Effet |
|---|---|---|
| `exposition=` | nord, sud, est, ouest, mi-ombre, ombre, plein-soleil | Information affichée sur le plan |
| `superficie=` | m², décimal (`8.5`) | Permet le calcul du taux d'occupation |
| `ordre=` | entier (`1`) | Position dans l'affichage du plan |
| `pepiniere=` | `true` / `false` | Marque une serre ou un châssis |

**Le paramètre `pepiniere` mérite une seconde d'attention.** Un semis rattaché à une parcelle déclarée pépinière reste un semis à couvert, en attente de repiquage — il n'est jamais compté comme une culture en place au jardin. Sans cette déclaration, semer dans sa serre en la nommant reviendrait à dire qu'on a semé en pleine terre, et le stock s'en trouverait faussé dès la première barquette.

### 5.5 Lister, renommer, supprimer

```
/parcelle lister
/parcelles
```

```
/parcelle renommer sud carré-sud
```

Le renommage se propage sur **tout l'historique** : aucun événement passé n'est orphelin, et l'ancien nom disparaît partout, y compris sur les gestes anciens.

```
/parcelle supprimer serre-1
```

La suppression demande confirmation, puis retire la parcelle des listes et du plan — **sans effacer aucun événement**. Les gestes qui s'y rattachaient restent au journal et basculent sous la mention « Non localisé ». Rien n'est perdu du passé de la planche, ni les récoltes qu'on y a faites, ni les cultures qui s'y sont succédé.

### 5.6 Votre premier enregistrement

Envoyez un message vocal ou tapez simplement :

```
Récolté 2 kg de tomates cerise parcelle nord
```

Le bot affiche un récapitulatif de ce qu'il a compris, avec deux boutons : **✅ Confirmer** et **❌ Annuler**. Touchez Confirmer. C'est fait.

Vous savez maintenant l'essentiel. Le reste du guide n'est que du détail.

---

## 6. Enregistrer un geste — les règles générales

Avant d'entrer dans le détail de chaque type de geste, voici ce qui vaut pour tous.

### 6.1 Parlez normalement

Vous n'avez pas de syntaxe à apprendre. Ces trois phrases produisent le même enregistrement :

- *« Récolté 2 kg de tomates cerise en parcelle nord »*
- *« J'ai ramassé deux kilos de tomates cerise, parcelle nord »*
- *« Cueilli 2 kilos de cerise, tomates, nord »*

L'assistant reconnaît de nombreux synonymes pour chaque geste : *récolter, cueillir, ramasser* ; *planter, repiquer, mettre en terre* ; *arroser, irriguer* ; *fertiliser, amender, mettre du compost*. La liste complète est en Partie III, section 22.

Écrire donne exactement le même résultat que dicter : la voix n'est qu'un confort quand on a les mains prises.

### 6.2 Les informations extraites

| Information | Obligatoire | Exemples |
|---|---|---|
| **Geste** | oui | récolte, semis, plantation, arrosage… |
| **Culture** | quasi toujours | tomate, courgette, carotte, poivron |
| **Variété** | non | cerise, Nantaise, Cœur de bœuf, Butternut |
| **Quantité** | non | 2.5 · 12 · 30 |
| **Unité** | non | kg, g, graines, plants, pieds, m², minutes |
| **Parcelle** | non | nord, B2, serre, maison |
| **Rangs** | non | nombre de rangs plantés |
| **Date** | non | par défaut : aujourd'hui |
| **Traitement / produit** | non | savon noir, bouillie bordelaise, purin d'ortie, paille |
| **Commentaire** | non | tout complément libre |

### 6.3 Les dix-huit gestes reconnus

| Famille | Gestes |
|---|---|
| **Multiplication** | semis · mise en godet · plantation |
| **Entretien** | arrosage · paillage · désherbage · binage · éclaircissage · taille · tuteurage · traitement · protection · amendement |
| **Sorties** | récolte · perte au jardin · perte en pépinière · vente de plants |
| **Constat** | observation |

Un geste qui ne figure pas dans cette liste n'est pas enregistré : l'assistant préfère vous le dire plutôt que d'inventer une catégorie. Si vous avez fait quelque chose qui n'entre dans aucune case, consignez-le en **observation** (chapitre 11).

### 6.4 Les dates

| Vous dites | L'assistant comprend |
|---|---|
| *(rien)* | Aujourd'hui |
| *« hier »* | La veille |
| *« avant-hier »* | L'avant-veille |
| *« lundi »* | Le lundi le plus récent |
| *« le 5 mars »* | Le 5 mars de l'année en cours |

**Point d'attention :** si vous rattrapez une saisie de plusieurs semaines, dites explicitement la date (*« le 12 avril »*) plutôt qu'un repère relatif. Les repères relatifs sont calculés par rapport à aujourd'hui, pas par rapport à votre souvenir.

Sans date dictée, le geste est daté du jour de la saisie — ce qui reste une supposition et non une certitude. C'est la raison pour laquelle les calculs de rotation raisonnent à la saison plutôt qu'au jour près.

### 6.5 Quantités, unités et rangs

Le **rang** est un multiplicateur : *« planté 4 salades sur 3 rangs »* enregistre **12 plants**, pas 4.

Les unités s'adaptent au contexte : *kg* et *g* pour les récoltes pesées, *graines* pour les semis, *plants* et *pieds* pour les comptages, *m²* pour un semis à la volée, *minutes* pour les durées d'arrosage, *litre* pour les traitements.

**Une unité n'est jamais convertie en une autre.** Deux mètres carrés de haricots semés à la volée restent deux mètres carrés : personne ne devine combien de pieds en sortiront. C'est aussi pour cela qu'il vaut mieux rester constant dans ses unités pour une même culture (voir la section 15.6, sur les totaux qui semblent faux).

### 6.6 Plusieurs gestes d'un coup

Séparez-les par un **retour à la ligne**. Une seule dictée peut couvrir toute une matinée :

```
Récolté 3 kg de tomates cerise et 2 courgettes
Arrosé les poivrons 20 minutes
Paillé les aubergines avec de la paille
```

Chaque ligne devient un événement distinct. Le récapitulatif les liste toutes avant confirmation.

### 6.7 Le récapitulatif et la confirmation

**Rien n'est enregistré avant que vous ne validiez.** Systématiquement, le bot affiche ce qu'il a compris et attend.

- **✅ Confirmer** → enregistrement.
- **❌ Annuler** → rien n'est écrit, vous pouvez redicter.
- **Aucune réponse pendant 60 secondes** → la confirmation expire, rien n'est enregistré.

Si vous n'avez pas mentionné de parcelle mais que le contexte en réclame une, le bot vous propose la liste de vos parcelles sous forme de boutons, plus une option « sans parcelle ». Le délai de 60 secondes couvre l'ensemble du dialogue, sélection de parcelle comprise.

**Lisez toujours le récapitulatif.** C'est votre seul filet de sécurité contre une transcription approximative — et c'est trente fois plus rapide que de corriger après coup.

### 6.8 Ce que l'assistant refuse d'inventer

L'assistant est bridé pour ne jamais compléter ce que vous n'avez pas dit. Si vous dictez *« paillage parcelle nord »* sans mentionner de légume, il n'inventera pas une culture : le champ reste vide.

De même, si vous dictez le nom approximatif d'une variété (*« nain »*), il cherche d'abord dans les variétés que vous utilisez déjà et retrouve *« vert nain Contender »* plutôt que de créer une variété fantôme.

Enfin, il refuse d'enregistrer une récolte, une perte ou un arrosage sur une culture **jamais semée ni plantée dans ce potager** : c'est presque toujours le signe d'une transcription fautive. Il vous le dit au lieu d'écrire une ligne fausse.

### 6.9 Si vous êtes membre en lecture seule

Sur un potager partagé, un membre en **lecture seule** peut tout consulter — plan, stock, journal, bilans, questions — mais ne peut rien enregistrer, corriger ni supprimer. Une tentative de saisie reçoit immédiatement un message expliquant que le rôle ne le permet pas. Les rôles sont détaillés au chapitre 18.

---

## 7. Semer

*Février à juin, selon les cultures.*

### 7.1 Semis en pépinière

C'est le semis en plateau, en terrine ou en caissette, sous abri.

```
Semis tomates variété Saint-Pierre le 5 mars
J'ai semé 30 graines de basilic en plateau
Semé 50 graines de poivron Corno di Toro en serre
```

**Précisez toujours le nombre de graines.** C'est ce qui permettra de calculer votre taux de réussite à la levée. Sans ce chiffre, l'étape suivante n'a plus de référence, et le lot restera marqué comme « germination indéterminée ».

Un semis est considéré comme fait **à couvert** dans deux cas : aucune parcelle n'est indiquée, ou la parcelle indiquée est déclarée serre / pépinière. Il rejoint alors la pépinière, et **n'entre pas** dans le stock de la culture — rien n'est encore en terre au jardin.

### 7.2 Semis direct en pleine terre

Pour tout ce qui ne se repique pas : carottes, radis, haricots, épinards, mâche.

```
Semis direct carottes en parcelle B2
Semis radis pleine terre parcelle A3 le 8 avril
Semé des carottes Nantaise sur 2 rangs parcelle A
Semé 2 m² de haricots à la volée parcelle sud
```

Rattaché à une parcelle ordinaire, le semis est compris comme un semis **en place** : il entre directement au stock de la culture, et aucun godet ne viendra jamais le consommer.

Une surface se dicte telle quelle (`2 m²`) et est conservée telle quelle : elle n'est jamais convertie en nombre de pieds.

### 7.3 Si la culture est inconnue de l'assistant

Lorsque vous semez une culture qu'il ne connaît pas encore, l'assistant vous demande si l'on en mange **la feuille, la tige ou la racine** (culture *végétative*) ou bien **le fruit ou la graine** (culture *reproductrice*). Ce n'est pas une coquetterie de botaniste : c'est ce qui décidera si une récolte fait baisser le stock ou non (chapitre 12).

### 7.4 Consulter vos semis

```
Liste de mes semis
Quels semis sont en cours ?
/stats
```

---

## 8. Suivre la pépinière

*Mars à mai. C'est la période où l'assistant est le plus utile — et le plus facile à oublier d'alimenter.*

### 8.1 Un lot de semis, c'est quoi

Chaque semis fait à couvert forme un **lot** à lui seul, identifié par sa date. Deux semis de la même variété faits à deux semaines d'écart restent deux lots distincts, jamais fondus en une seule ligne : c'est ce qui permet de voir lequel a levé et lequel se fait attendre.

La pépinière se lit ainsi lot par lot, avec pour chacun sa date, sa culture, sa variété, le nombre de graines de départ et ce qu'il en reste.

### 8.2 La mise en godet

Quand vos semis ont levé et sont assez forts, vous les repiquez en godets individuels. C'est l'étape charnière entre le plateau et la pleine terre.

```
Mise en godet tomates Saint-Pierre 20 plants
Mis en godet 24 tomates sur 30 graines
Repiquer 15 plants de poivron en godet le 10 mars
```

**C'est ici que se calcule votre taux de réussite** : 20 plants repiqués sur 30 graines semées = 67 %. Ce chiffre, accumulé sur plusieurs saisons, vous dira quelles variétés lèvent bien chez vous.

**Ce que le repiquage retire au semis d'origine.** Repiquer solde les **graines** du lot, pas seulement les plants obtenus : vingt plants repiqués depuis une barquette de trente graines soldent les trente graines, les dix qui n'ont pas levé quittant la pépinière avec elles. Un repiquage en plusieurs fois ne solde à chaque passage que ce qui a été déclaré.

### 8.3 Les questions que le bot peut vous poser

Trois cas où l'assistant préfère demander plutôt que deviner :

- **De quel lot viennent ces plants ?** Si plusieurs semis de la même variété ont encore des graines en germination, il vous propose les lots sous forme de boutons, avec le nombre de graines restantes :

```
🌱 Lot 15 mars — 12 restantes
🌱 Lot 01 avr — 10 restantes
❌ Annuler
```

- **Combien de graines à l'origine ?** Si le lot ne le sait pas, il vous le demande, en rappelant le lot concerné. Vous pouvez passer outre en une action explicite : l'avancement du lot restera alors *indéterminé*, plutôt que faussé par une valeur inventée.
- **Quelle variété ?** Si plusieurs variétés de la culture sont en pépinière, il vous fait choisir ; s'il n'y en a qu'une, il la remplit tout seul.

S'il n'y a qu'un seul lot possible, le rattachement est automatique et rien ne vous est demandé.

### 8.4 Vendre ou donner des plants

Si vous produisez plus de plants qu'il ne vous en faut :

```
/vendre tomate Saint-Pierre 5
```

Ou en langage naturel : *« vendu 5 plants de tomate Saint-Pierre »*, *« donné 3 courgettes jaunes »*.

Ces sorties sont déduites de votre stock de godets, exactement comme une plantation. Elles apparaissent distinctement dans le tableau de bord. Cette distinction évite de gonfler la production d'une saison avec des plants qui ont fini dans le jardin de quelqu'un d'autre.

### 8.5 Les pertes en pépinière

```
Perdu 4 plants de poivron en godet, fonte des semis
Perte pépinière 10 graines de basilic
```

Distinguer une **perte en godet** d'une **perte au champ** compte : la première touche votre stock de pépinière, la seconde vos pieds en terre.

### 8.6 Les états d'un lot

| État | Ce qu'il signifie |
|---|---|
| **En cours** | Des graines restent à lever, et les repiquages ont tous été déclarés complètement |
| **Clos** | Tout a été soldé : plus rien n'est attendu de ce lot |
| **Indéterminé** | Un repiquage n'a pas dit de combien de graines il venait — l'information manque |

L'état *indéterminé* n'est jamais présenté comme un lot en cours : une information manquante ne se transforme pas en attente prometteuse.

**Un lot qui affiche plus de plants que de graines** est signalé comme une incohérence de saisie, et non rogné discrètement à 100 %. Les valeurs sont montrées telles qu'elles ont été saisies, pour que le geste fautif puisse être retrouvé et corrigé.

### 8.7 Des godets sans semis d'origine

Des plants mis en godet sans qu'aucun semis ne leur soit rattaché — achetés, donnés, ou repiqués sans qu'on précise leur origine — forment un lot à part, par culture et par variété. Il se comporte comme les autres pour la plantation, mais n'affiche ni date de semis ni taux de réussite, faute de point de départ connu.

### 8.8 Consulter la pépinière

```
Liste des godets
Quels plants sont en godet ?
/stats tomate
```

Ou, bien plus lisible, l'écran **Pépinière** du tableau de bord, qui montre chaque lot avec sa frise Germination → Godet → Terre.

---

## 9. Planter

*Avril à juin, après les dernières gelées.*

```
Planté 12 plants de poivrons en 3 rangs
Planté 6 tomates Cœur de bœuf parcelle nord
Repiqué 24 salades en parcelle B
Mis en terre 8 courgettes jaunes parcelle sud
```

### 9.1 Ce qui se passe automatiquement

Chaque plantation **déduit du stock de godets** de la même culture et de la même variété. Vous n'avez rien à faire : dire que vous avez planté suffit à faire baisser votre pépinière.

Le calcul est strict par couple culture + variété. Planter 4 courgettes jaunes ne touche pas au stock de courgettes vertes. Si votre godet a été enregistré sans variété et qu'une seule variété apparaît dans vos plantations, l'assistant fait le rapprochement lui-même.

Quand tous les godets d'une variété ont été plantés, la ligne tombe à zéro et disparaît de la pépinière — sans que rien ne soit effacé du journal.

### 9.2 Précisez la parcelle

C'est le moment où mentionner la parcelle a le plus de valeur : c'est cette information qui alimente votre plan d'occupation pour toute la saison, **et qui rend possible le calcul de rotation** des années suivantes. Si vous ne devez le faire qu'une seule fois, faites-le ici.

### 9.3 L'avertissement de rotation

Juste après l'enregistrement d'une plantation ou d'un semis, l'assistant vérifie l'historique réel de la parcelle et vous signale, le cas échéant :

- un **conflit de rotation** — une culture de la même famille botanique est revenue trop tôt sur cette planche ;
- une **association défavorable** avec une culture déjà en place cette même saison.

Trois choses à savoir :

1. **L'avertissement ne bloque jamais l'enregistrement.** Le jardinier décide, l'assistant informe.
2. **Il dit aussi quand il ne sait pas** : « je n'ai pas d'antécédent sur cette parcelle », « évaluation indisponible » (famille sans délai de retour connu). Une absence d'information n'est jamais présentée comme une absence de conflit.
3. **Il se tait quand tout va bien.** Quand l'antécédent est connu et que le délai est tenu, aucun message n'apparaît — un avertissement qui s'affiche à chaque saisie cesse d'être lu au bout d'une semaine.

Pour vérifier **avant** de planter plutôt qu'après, voir le chapitre 16 (`/rotation`).

### 9.4 Et pour les semis directs ?

Un semis fait directement en pleine terre est déjà « en place » : il n'y a pas de plantation à enregistrer ensuite, et le stock de la culture est alimenté dès le semis.

Si vous voulez garder trace de la levée, consignez-la comme une **observation** (`/note`, catégorie Observation) : *« les haricots de la parcelle B2 ont levé »*. Il n'existe pas de geste « levée » — l'assistant refuserait d'enregistrer ce qu'il ne sait pas nommer.

---

## 10. Entretenir

*Toute la saison.*

Ces gestes ne modifient aucun stock. Ils construisent votre historique d'interventions — ce qui, en fin de saison, vous permet de savoir combien de fois vous avez arrosé, avec quoi vous avez traité, et quand.

| Geste | Exemples de dictée |
|---|---|
| 💧 **Arrosage** | *« Arrosé les courgettes 30 minutes »* · *« Irrigué la parcelle nord »* |
| 🌾 **Paillage** | *« Paillé les tomates avec de la paille »* · *« Mulch sur les courges »* |
| 🌿 **Désherbage** | *« Désherbé la parcelle des carottes »* · *« Sarclé les rangs de poireaux »* |
| 🪓 **Binage** | *« Biné les rangs de haricots »* · *« Binage parcelle est »* |
| ✂️ **Éclaircissage** | *« Éclairci les carottes de la planche nord »* |
| ✂️ **Taille** | *« Taillé les poivrons, supprimé les gourmands »* · *« Pincé les tomates »* |
| 🪵 **Tuteurage** | *« Tuteuré les tomates Cœur de bœuf »* · *« Palissé les haricots »* |
| 🧪 **Traitement** | *« Traité les rosiers au savon noir »* · *« Bouillie bordelaise sur les tomates, 1 litre »* |
| 🛡️ **Protection** | *« Posé un voile sur les salades »* · *« Filet anti-insectes sur les choux »* |
| 🌱 **Amendement** | *« Fertilisé les courges avec du compost »* · *« Épandu du fumier parcelle est »* |

**Toujours nommer le produit** pour les traitements et amendements. C'est la seule façon de retrouver ensuite ce que vous avez appliqué, en quelle quantité et à quelle fréquence.

**Toujours donner la durée** pour les arrosages. C'est ce qui permet de cumuler votre consommation d'eau sur la saison.

---

## 11. Observer et noter

*Toute la saison — le chapitre le plus sous-estimé.*

### 11.1 Pourquoi une note n'est pas un geste

Les chapitres précédents décrivent des **gestes** : vous avez fait quelque chose. Une **note** décrit un *constat* : vous avez vu quelque chose.

Il n'y a pas de quantité, pas de geste, souvent pas d'unité. Forcer une observation dans le moule d'un geste produit des données bancales. C'est pourquoi l'assistant propose un flux dédié, qui vous **pose les bonnes questions** au lieu de vous laisser deviner ce qu'il faut dire.

### 11.2 Déclencher une note

Deux façons, strictement équivalentes :

```
/note
```

Ou dictez simplement :

- *« Je veux noter une observation »*
- *« Je veux noter que le sol est sec sur la parcelle sud »*
- *« Il faut que je note un truc sur les tomates »*
- *« Ajouter une note »*

### 11.3 Choisir la catégorie

Le bot affiche quatre boutons. Le choix détermine la question qu'il vous posera ensuite.

| Catégorie | Pour quoi |
|---|---|
| 🔍 **Observation** | Remarque générale de suivi : croissance, aspect, comportement |
| 🐛 **Maladie / ravageur** | Problème sanitaire détecté |
| 💧 **Arrosage (remarque)** | Constat qualitatif lié à l'eau — **sans** créer d'arrosage réel |
| 🌿 **Paillage** | Constat ou action de paillage informelle |

> **À retenir sur la catégorie Arrosage.** Constater que le sol est sec n'est pas arroser. Cette catégorie consigne un *constat* — sol sec, sol détrempé, fuite du goutte-à-goutte — et **n'ajoute aucun apport d'eau** à l'historique de la parcelle. Le « dernier arrosage » reste celui que vous avez réellement fait et dicté comme tel. La même distinction vaut pour la note de paillage.

### 11.4 Répondre à la question guidée

Selon la catégorie, le bot pose une question adaptée. Vous répondez **en langage naturel**, d'un seul bloc, sans format imposé.

**Exemple complet — Maladie / ravageur**

```
Vous  : /note

Bot   : 📝 Nouvelle note
        Quelle catégorie souhaites-tu noter ?
        [🔍 Observation] [🐛 Maladie / ravageur]
        [💧 Arrosage]    [🌿 Paillage]

Vous  : 🐛 Maladie / ravageur

Bot   : Décris le problème sanitaire observé : culture/parcelle
        concernée, symptôme constaté, et le traitement appliqué
        ou envisagé si tu en as un.

Vous  : tomates parcelle Nord, mildiou sur les feuilles du bas,
        j'ai traité au purin d'ortie

Bot   : 📋 Récapitulatif
        Catégorie  : 🐛 Maladie / ravageur
        Culture    : tomate
        Parcelle   : Nord
        Constat    : mildiou sur les feuilles du bas
        Traitement : purin d'ortie
        Date       : aujourd'hui

        [✅ Confirmer]  [❌ Annuler]

Vous  : ✅ Confirmer

Bot   : ✅ Note enregistrée.
```

**Exemple — Arrosage (remarque)**

```
Vous : 💧 Arrosage (remarque)
Bot  : Décris ton constat lié à l'arrosage : parcelle concernée,
       état du sol (sec/détrempé...), durée constatée si pertinent.
Vous : sol sec sur la parcelle Sud
```

**Exemple — Paillage**

```
Vous : 🌿 Paillage
Bot  : Décris ton constat ou action de paillage : parcelle/culture
       concernée, matériau utilisé si pertinent.
Vous : paillage renouvelé sur les courgettes avec de la paille
```

**Exemple — Observation générale**

```
Vous : 🔍 Observation
Bot  : Décris ton observation (parcelle et culture concernées
       si besoin) :
Vous : les poireaux de la parcelle est se développent beaucoup
       plus vite que ceux de la maison cette année
```

### 11.5 Ce que l'assistant extrait

De votre réponse libre, il tire automatiquement : la culture, la variété, la parcelle, le constat reformulé, le traitement ou matériau, une durée si pertinente, et une date si vous en mentionnez une (*« hier »*).

Il ne remplit **que** ce que vous avez dit. Le reste reste vide.

Culture et variété sont rapprochées de ce que vous utilisez déjà : si vous dites *« nain »* et que vous cultivez du haricot *« vert nain Contender »*, c'est cette variété qui est retenue.

### 11.6 Annuler

À n'importe quel moment du flux : bouton **❌ Annuler**, ou tapez simplement `annuler`. Rien n'est enregistré.

### 11.7 Où retrouver vos notes

Vos notes ne dorment pas dans un coin. Elles **remontent dans le tableau de bord**, sous forme d'une petite icône de bulle de dialogue :

- Si la note concerne une parcelle → l'icône apparaît **sur la parcelle**, dans l'écran Plan.
- Si la note concerne une culture sans parcelle précise → l'icône apparaît **sur la culture**, dans l'écran Stocks.
- Cas malin : si vous notez quelque chose sur une culture et une variété précises **sans dire la parcelle**, et que cette variété n'est cultivée qu'à un seul endroit, l'assistant la rattache tout seul à la bonne parcelle.

Un badge indique le nombre de notes (plafonné à « 10+ »). Un clic déplie un aperçu, paginé par blocs de trois. Les notes figurent aussi au journal, avec leur catégorie.

### 11.8 Aide dédiée

```
/help note
```

---

## 12. Récolter

*Juin à novembre.*

### 12.1 Récolte ponctuelle

```
Récolté 800 g de tomates en A1
Cueilli 3 courgettes parcelle B2 aujourd'hui
Ramassé 1 kg de haricots verts hier
```

### 12.2 Pourquoi le stock ne baisse pas toujours quand vous récoltez

C'est la question la plus fréquente, et la réponse tient en une distinction.

**Les cultures reproductrices** produisent plusieurs fois sans mourir : on en mange le fruit ou la gousse, et le pied continue de pousser. Tomate, courgette, haricot, concombre, poivron, aubergine. Prendre un fruit ne retire **aucun** pied du jardin : le nombre de pieds reste identique après la cueillette, et c'est le poids cumulé qui augmente. Voir le compteur immobile n'est pas un oubli de l'assistant, c'est la réalité du jardin.

**Les cultures végétatives** ne se récoltent qu'une fois : on en mange la feuille, la racine ou le bulbe, et le pied disparaît avec elle. Salade, carotte, radis, poireau, oignon, pomme de terre. Chaque récolte retire alors du stock autant de pieds qu'il en a été récolté.

C'est cette différence, et elle seule, qui explique que deux cultures récoltées le même jour ne se comportent pas de la même façon au compteur.

### 12.3 Peser une culture qu'on compte en pieds

Une salade se compte en pieds, mais on peut vouloir en connaître le poids. Les deux comptes coexistent sans jamais se mêler :

- le **rendement** additionne les poids récoltés, en kilos ou en grammes — il vaut pour toutes les cultures ;
- le **stock** compte les pieds récoltés à la pièce, et ne sert qu'à retrancher.

Dictez les deux si vous les avez : *« récolté 2 betteraves 250 g »* enregistre à la fois deux pieds en moins et 250 g de rendement. Si vous ne donnez qu'un poids sur une culture végétative, le bot vous demande combien de pieds ont été récoltés, plutôt que de risquer une déduction de stock fausse.

### 12.4 Récolte de graines

Si vous produisez vos propres semences :

```
Récolte graines tomates Saint-Pierre 15 g
Mis de côté graines courge pour semis prochain
```

### 12.5 Consulter l'historique des récoltes

```
Historique récoltes
Mes récoltes du mois de mars
/stats tomate
```

---

## 13. Enregistrer les pertes et clore une culture

*Toute la saison. C'est la partie qu'on saute — et c'est celle qui fausse tous les chiffres si on la saute.*

### 13.1 Un stock qui ne baisse jamais est un stock faux

Si vous perdez des pieds, dites-le.

```
Perdu 3 pieds de tomate, gel
Perdu 2 courgettes, limaces
Arraché les poireaux, mildiou
2 salades mortes de sécheresse
```

L'assistant reconnaît de nombreuses formulations : *perdu, mort, arraché, crevé, disparu*.

Une perte retire des pieds du stock **sans rien ajouter à la production** : c'est ce qui distingue un pied dévoré par les limaces d'un pied effectivement consommé. Elle vaut pour toutes les cultures, reproductrices comprises.

**Distinguez bien :**

| Situation | Ce que vous dictez |
|---|---|
| Perte de plants **en godet** | *« Perdu 4 plants de poivron en godet »* |
| Perte de pieds **en terre** | *« Perdu 3 pieds de tomate, gel »* |
| Fin de culture, arrachage | *« Arraché les 8 pieds de courgette, fin de saison »* |

### 13.2 Comment libérer une parcelle en fin de culture

Une culture reste affichée sur le plan **tant qu'il lui reste des pieds**. Pour une culture végétative, récolter suffit : le dernier pied récolté fait disparaître la ligne, et la parcelle réapparaît comme disponible.

Pour une culture **reproductrice**, la récolte ne retire aucun pied — les tomates resteront donc affichées sur la planche jusqu'à ce que vous disiez ce qui leur est arrivé. En fin de saison, dictez l'arrachage :

```
Arraché les 8 pieds de tomate parcelle nord, fin de saison
```

Il n'existe pas de formule magique du type « récolte finale » qui solderait la culture toute seule : c'est le geste réel — l'arrachage — qui la clôt, comme au jardin.

### 13.3 Une perte n'est pas un aveu d'échec

C'est une donnée. Sur trois saisons, elle vous dira quelles cultures et quelles parcelles vous coûtent le plus — et elle est indispensable au calcul de rotation, qui a besoin de savoir quand une planche s'est libérée.

---

## 14. Corriger, supprimer, déplacer

*Dès que vous vous en apercevez.*

### 14.1 Corriger un geste mal compris

```
/corriger
```

Ou dites *« corriger »*, *« modifier »*.

**Le déroulé :**

1. **Retrouver l'événement.** Décrivez-le : *« la récolte de tomates d'hier »*. Ou tapez simplement **`1`** pour désigner le tout dernier événement enregistré — c'est le cas de loin le plus fréquent.
2. **Choisir parmi les candidats.** Le bot liste ce qu'il a trouvé, numéroté. Vous choisissez.
3. **Dicter la correction** en langage naturel : *« la quantité c'était 3 kg »*, *« c'était en parcelle sud »*, *« c'était avant-hier »*.
4. **Confirmer.** Un récapitulatif montre l'ancienne et la nouvelle valeur. Vous validez.

La correction porte sur le seul champ visé, et tous les calculs qui en dépendent — stock, pépinière, bilans — s'ajustent aussitôt.

**Exemple**

```
Vous : /corriger
Bot  : Décrivez l'événement à corriger (ou tapez 1 pour le dernier)
Vous : 1
Bot  : 📋 Récolte · tomate cerise · 2.0 kg · nord · 17/07/2026
       Que voulez-vous corriger ?
Vous : la quantité c'était 3 kg
Bot  : quantité : 2.0 → 3.0
       [✅ Confirmer] [❌ Annuler]
Vous : ✅ Confirmer
Bot  : ✅ Modification enregistrée.
```

### 14.2 La trace de correction

Chaque correction laisse une **trace horodatée** attachée à l'événement. Rien n'est effacé en silence : vous pouvez toujours savoir ce qui a été modifié, quand, et quelle était la valeur d'origine.

### 14.3 Supprimer un enregistrement

Dites *« supprimer »*, *« effacer »* ou *« annuler »*. Le bot vous propose de corriger ou de supprimer le dernier événement, avec confirmation. La suppression retire définitivement le geste des calculs : stock, pépinière et bilans se recalculent immédiatement sans lui.

**Réflexe à prendre :** une saisie erronée se corrige mieux qu'elle ne se supprime. Supprimer crée un trou dans votre historique ; corriger le préserve.

### 14.4 Déplacer une culture vers une autre parcelle

Vous avez enregistré vos plantations sans parcelle, ou sur la mauvaise planche ? Plutôt que de corriger les événements un par un :

```
Déplacer mes tomates sur la parcelle nord
Associer ma zone courgette sur une nouvelle parcelle
Rattacher les salades à la parcelle B2
```

Le bot vous guide :

1. si plusieurs variétés existent, il vous demande laquelle est concernée (une seule variété → il enchaîne directement) ;
2. il liste vos parcelles avec leur occupation actuelle (🟢 libre / 🌱 occupée) ;
3. une parcelle inconnue est acceptée : elle sera créée à la confirmation ;
4. un récapitulatif annonce la culture, la variété, la parcelle cible et le nombre de plantations concernées ;
5. après confirmation, **toutes les plantations concernées** basculent d'un coup, et une trace du déplacement est conservée.

Annulable à tout moment en disant *« annuler »*, *« menu »* ou *« retour »*.

### 14.5 Qui peut corriger

Corriger et supprimer demandent d'être au moins **éditeur** du potager. Un membre en lecture seule peut tout consulter sans rien modifier (chapitre 18).

---

## 15. Consulter et interroger

*Le soir, à froid — ou les pieds dans la boue, ça marche aussi.*

### 15.1 Le plan d'occupation

```
/plan
/plan nord
/plan 15/05/2026
```

Ou en langage naturel : *« plan du potager »*, *« qu'est-ce qui pousse en nord ? »*.

Le plan global liste chaque parcelle avec ses cultures actives et leur ancienneté. Le plan détaillé d'une parcelle donne le détail par culture : nombre de plants, date de plantation, jours écoulés.

Une culture n'y figure **que tant qu'il en reste des pieds**. Entièrement récoltée ou arrachée, elle disparaît et la parcelle réapparaît comme disponible. Les cultures dont la parcelle n'a jamais été précisée sont regroupées sous « Non localisé ».

### 15.2 Les statistiques

```
/stats
/stats tomate
/stats tomate 15/05/2026
```

Ou : *« bilan du potager »*, *« stats tomates »*, *« bilan courgettes cette saison »*, *« synthèse semis »*.

`/stats` seul donne le bilan de saison, séparé entre cultures **végétatives** (dont on mange les feuilles, tiges, racines) et **reproductrices** (dont on mange les fruits ou graines), suivi des **semis en cours** et de l'état de la **pépinière**.

`/stats <culture>` descend au détail **par variété** : ce qui a été planté, ce qui reste, ce qui a été récolté et depuis quand — plus les semis et les godets de cette culture, avec ce qu'il reste de chaque lot. C'est la façon de savoir laquelle de deux variétés a le mieux donné, information qu'un total par culture noie forcément.

Tout y est recalculé à la demande depuis les gestes enregistrés : aucune valeur n'est figée.

### 15.3 Le journal

```
/historique
```

Les **10 derniers événements** enregistrés, du plus récent au plus ancien. Pratique pour vérifier ce que vous venez de saisir.

Pour aller plus loin — filtrer par type de geste, par culture ou par date, remonter page par page, exporter en tableur — passez par l'écran **Journal** du tableau de bord. L'export reprend exactement ce qui est à l'écran, filtres appliqués : ce qui est exporté est donc ce qui a été relu.

### 15.4 Poser une question libre

C'est la fonction la plus souple : vous posez une question, l'assistant cherche la réponse.

```
/ask Combien de kg de tomates ai-je récoltés cette saison ?
```

Vous pouvez aussi taper (ou dicter) simplement votre question, sans commande.

**Questions qui marchent bien :**

| Type | Exemple |
|---|---|
| Quantité | *« Combien de kg de tomates récoltés cette saison ? »* |
| Date | *« Quand ai-je planté mes courgettes ? »* |
| Dernière fois | *« Dernier arrosage des poivrons »* |
| Bilan | *« Bilan de ma saison de carottes »* |
| Par parcelle | *« Qu'est-ce que j'ai récolté en parcelle nord ? »* |
| Par famille | *« Quelles parcelles contiennent des solanacées ? »* |
| Localisation | *« Sur quelles parcelles je trouve des tomates ? »* |
| Comparaison | *« Quelle parcelle a le plus produit ? »* |

**Formulez des questions complètes.** Une question de trois mots (*« date récoltes »*) fait passer l'assistant en mode question et vous demande de reformuler — deux échanges au lieu d'un.

**Quand la donnée manque, il le dit** : « je n'ai aucune récolte de concombre enregistrée » est une réponse exacte, pas un échec. Il ne vous avancera jamais un chiffre approximatif à la place.

> **Une limite à connaître.** Sur des questions très larges couvrant plusieurs années, l'interrogation libre travaille sur un extrait récent de votre historique. Pour un total de longue période, préférez `/stats` et le tableau de bord, qui calculent sur l'ensemble des données.

### 15.5 Ce que l'assistant sait expliquer de lui-même

Vous pouvez lui poser des questions sur **le fonctionnement de l'application**, dans vos mots :

- *« Comment est calculé mon stock ? »*
- *« Pourquoi mon stock de tomates ne baisse pas quand je récolte ? »*
- *« Pourquoi mon semis n'apparaît pas dans la pépinière ? »*
- *« Comment corriger une saisie ? »*
- *« Combien de temps ai-je pour revenir en arrière après une suppression de potager ? »*

Ces réponses sont tirées d'un corpus écrit et relu, pas improvisées : le texte servi est celui d'un document de référence, et l'assistant indique la fiche dont il provient. Notez la nuance avec `/help`, qui reste un **sommaire** : `/help` énumère les commandes, une question posée en toutes lettres vous donne l'explication.

Sur une réponse de ce type, deux boutons 👍 / 👎 vous permettent de dire si elle vous a servi. C'est le seul moyen qu'a l'assistant de savoir ce qu'il explique mal.

### 15.6 Ce que « stock » veut dire ici — et pourquoi un total peut sembler faux

Dans cette application, le **stock** d'une culture, c'est le nombre de **pieds vivants au jardin**, auquel s'ajoute, séparément, le nombre de **plants en godet**. Ce n'est jamais un stock de semences : il n'existe pas d'inventaire de sachets de graines, ni d'alerte de réapprovisionnement.

Ce stock ne se saisit pas : il se déduit des gestes. Plantations et semis en place ajoutent, pertes retirent, récoltes retirent aussi lorsque récolter arrache le pied.

**Si un total vous paraît faux**, la cause la plus fréquente est un mélange d'unités. Cent graines et deux mètres carrés ne font pas cent deux de quoi que ce soit : quand une culture a été saisie tantôt d'une façon, tantôt d'une autre, seule l'unité la plus représentée est comptée, les autres étant exclues plutôt que converties au jugé. Reprendre les gestes concernés dans le journal pour les ramener à une même unité rétablit un total juste.

La deuxième cause, c'est une perte jamais déclarée : un stock qui ne baisse jamais est un stock faux (chapitre 13).

---

## 16. Cultures, familles, rotation et associations

*Avant de semer, et au moment de planter.*

### 16.1 Consulter la fiche d'une culture

```
/fiche tomate
/fiche CELERI
```

Une fiche courte rassemble ce qui est connu de la culture : sa **famille botanique**, le **délai de retour** à respecter avant de la refaire au même endroit, et ses conditions de conduite — **exposition**, **besoin en eau**, **profondeur de semis**, **rusticité minimale**. La source de chaque information est indiquée.

Casse et accents sont indifférents. Ce qui n'est pas renseigné s'affiche comme **non renseigné** : l'assistant ne devine jamais, ne moyenne jamais, et une culture inconnue est annoncée comme telle plutôt que remplacée par une voisine approchante.

La réponse est immédiate et ne coûte rien : elle est assemblée à la lecture depuis le référentiel, sans passer par aucun modèle.

### 16.2 Consulter et corriger les caractéristiques de conduite

```
/culture attributs carotte
```

```
/culture exposition courgette plein soleil
/culture eau tomate moyen
/culture profondeur carotte 1
/culture rusticite poireau -15
```

- **exposition** : `plein soleil` · `mi-ombre` · `ombre`
- **eau** : `faible` · `moyen` · `élevé`
- **profondeur** : en centimètres
- **rusticité** : en degrés Celsius

Une valeur hors de ces listes est refusée, et la caractéristique garde sa valeur précédente. Les variantes de saisie (casse, accents, tirets, virgule décimale) sont acceptées, mais seule la valeur canonique est enregistrée.

**Votre correction prime sur tout.** Une valeur que vous avez saisie à la main n'est jamais réécrite par une reprise du référentiel, caractéristique par caractéristique : corriger la profondeur de semis n'empêche pas l'exposition de continuer à être rafraîchie.

### 16.3 Corriger la famille botanique et le délai de retour

```
/culture famille pâtisson Cucurbitacée
/culture delai_retour Solanacée 4
```

La famille se corrige culture par culture — la culture doit avoir été dictée au moins une fois pour être connue. Le **délai de retour**, lui, se corrige au niveau de la **famille** et s'applique aussitôt à toutes les cultures qui en font partie : ce délai est un fait de la famille, pas de chaque légume pris isolément.

Ces corrections s'appliquent sans attendre une nouvelle version de l'application.

### 16.4 Pourquoi la famille décide de la rotation

Deux cultures d'une même famille épuisent le sol de la même façon et partagent les mêmes maladies : c'est la famille, et non le légume, qui commande le délai avant de revenir au même endroit.

L'assistant croise donc trois choses : l'**historique réel** de la parcelle, la **famille** de tout ce qui y est passé, et le **délai propre** à cette famille. Le raisonnement se fait à la **saison** plutôt qu'au jour près, parce qu'une date de saisie approximative reste juste à ce grain-là.

Sont écartés de cet historique les bulletins météo automatiques et les cultures inconnues du référentiel : ils ne sont jamais traités comme un antécédent établi.

### 16.5 Vérifier une parcelle avant de planter

```
/rotation NORD poivron
```

La réponse dit si le délai de retour est tenu, et sur quel antécédent elle se fonde. Trois issues possibles, jamais confondues :

- **conflit** — une culture de la même famille est passée là trop récemment, avec l'année et la culture en cause ;
- **rien à signaler** — le délai est tenu ;
- **je ne peux pas conclure** — aucun antécédent connu sur cette parcelle, ou famille sans délai de retour renseigné. Ce n'est pas une absence de conflit, et c'est dit comme tel.

Le même calcul se déclenche automatiquement au moment d'enregistrer une plantation ou un semis (section 9.3).

### 16.6 Les associations entre cultures

```
/association lister carotte
```

Liste les cultures et familles à associer ou à éloigner de celle-ci, avec le motif et le niveau de preuve. L'affichage distingue deux registres, et ne les confond jamais :

- **défavorable** — association établie ;
- **déconseillé par la pratique traditionnelle** — transmis par l'usage, sans démonstration.

Une association saisie au niveau d'une **famille** vaut pour toutes les cultures qui s'y rattachent : il n'y a pas à la ressaisir légume par légume.

### 16.7 Saisir ou corriger une association

```
/association saisir carotte aneth defavorable etabli concurrence racinaire
/association saisir tomate basilic favorable traditionnel repousse les pucerons
```

L'ordre des arguments : **culture A**, **culture B**, **nature** (`favorable` · `defavorable` · `neutre`), **niveau de preuve** (`etabli` · `traditionnel`), puis le **motif** en clair.

Une association est lue dans les deux sens quel que soit l'ordre de saisie. La ressaisir dans l'autre sens met à jour la ligne existante au lieu d'en créer une seconde, contradictoire.

---

## 17. Météo et confort

### 17.1 La météo

Chaque matin à 5 h, l'assistant relève automatiquement et silencieusement la météo du jour — températures, précipitations, probabilité de pluie. Vous n'avez rien à faire. Ce relevé alimente l'historique météo consultable dans le tableau de bord.

Pour un relevé manuel immédiat :

```
/meteo
```

Sur le tableau de bord, le widget météo affiche en plus le lever et le coucher du soleil, la prévision à 5 jours et un **conseil potager du jour** (arrosage, gel, vent…) calculé sur la localisation réelle de votre potager. Pensez à renseigner la commune du potager depuis l'écran de paramètres, sans quoi la météo affichée n'est pas la vôtre.

### 17.2 Les réponses vocales

L'assistant peut vous répondre à voix haute — pratique quand vous avez les mains dans la terre et le téléphone au fond d'une poche.

```
/tts        →  état actuel
/tts_on     →  activer
/tts_off    →  désactiver
```

Le texte reste envoyé dans tous les cas : la voix s'ajoute, elle ne remplace rien. L'état choisi est mémorisé et rappelé au démarrage de la conversation.

### 17.3 Version installée

```
/version
```

Affiche la version déployée, le commit et l'environnement. Utile pour un signalement de bug.

---

## 18. Partager son potager

*Depuis l'application web — le compagnon Telegram suit automatiquement.*

### 18.1 Inviter quelqu'un

Le propriétaire d'un potager produit un **code d'invitation**, valable une semaine et utilisable une seule fois. La personne invitée crée son compte si elle n'en a pas, puis saisit ce code pour rejoindre le jardin.

Le rôle est choisi **au moment de l'invitation** : on décide en invitant si l'on ouvre la porte à quelqu'un qui saisira, ou à quelqu'un qui regardera.

### 18.2 Ce que chaque rôle permet

| Rôle | Peut faire |
|---|---|
| **Propriétaire** | Tout : inviter, retirer des membres, modifier le potager, l'archiver, le supprimer |
| **Éditeur** | Enregistrer, corriger et supprimer des gestes — mais ni les membres, ni l'existence du potager |
| **Lecture seule** | Consulter le plan, le stock, le journal, les bilans, poser des questions — sans jamais rien écrire |

Une action refusée le dit explicitement, en nommant le rôle qui manque. Sur Telegram, le refus arrive avant même que la phrase ne soit analysée.

### 18.3 Retirer quelqu'un

Le propriétaire peut retirer un membre à tout moment. La personne perd **immédiatement** l'accès, mais ce qu'elle a enregistré reste au journal : retirer un accès n'efface pas une saison de travail. Si ce potager était celui qu'elle consultait, elle bascule simplement sur un autre de ses jardins, ou sur aucun.

### 18.4 Ce que les autres voient — et ne voient pas

Le partage ne concerne que le potager sur lequel on a été invité. Un membre ne voit **rien** des autres jardins de la personne qui l'a invité, et réciproquement. Ce cloisonnement vaut aussi pour les questions posées à l'assistant, qui ne répond jamais avec les données d'un jardin auquel on n'a pas accès.

---

## 19. Créer, archiver et supprimer un potager

*Depuis l'application web.*

### 19.1 Créer un potager

L'assistant de création vous guide en quatre étapes : nom et commune, première parcelle (nature, nom, surface, exposition, type de sol), sélection de cultures courantes, puis récapitulatif avant validation. Vous pouvez aussi rejoindre un potager existant par code d'invitation depuis cet écran, sans terminer les étapes restantes.

### 19.2 Archiver

Archiver un potager le met en **lecture seule** : tout reste consultable, plus rien ne s'y écrit. C'est ce qu'on fait d'un jardin qu'on ne cultive plus mais dont on veut garder la mémoire, sans risquer d'y enregistrer une récolte par erreur en croyant être ailleurs.

L'archivage est réversible à tout moment, et rendre l'écriture possible à nouveau reste un geste délibéré. Seul le propriétaire peut archiver.

### 19.3 Supprimer — et le délai de trente jours

Un potager doit d'abord être **archivé** avant de pouvoir être supprimé : on ne supprime jamais un jardin en cours d'usage. La suppression demande de retaper votre mot de passe, puis ouvre un **délai de trente jours** pendant lequel rien n'est détruit.

Pendant ce mois, le propriétaire peut faire machine arrière depuis la corbeille : le potager revient alors à l'état archivé, consultable, et il faudra le désarchiver pour y écrire de nouveau.

**Passé les trente jours**, le potager et tout ce qu'il contenait sont effacés pour de bon : parcelles, gestes, cultures, notes. Cet effacement est définitif et ne se rattrape pas. Les autres potagers du compte ne sont jamais touchés.

---

## 20. Bonnes pratiques

### ✅ À faire

- **Enregistrez sur le moment**, pas le soir. Une saisie différée est une saisie approximative ou oubliée.
- **Lisez le récapitulatif** avant de confirmer. Trois secondes qui vous économisent une correction.
- **Précisez la variété** systématiquement. C'est ce qui rend les comparaisons entre saisons possibles.
- **Mentionnez la parcelle** au moins à la plantation : c'est elle qui alimente le plan et la rotation.
- **Notez le nombre de graines** au semis : c'est la base de tous vos taux de réussite.
- **Enregistrez les pertes et les arrachages.** Sans eux, tous vos stocks sont faux et vos planches restent occupées pour rien.
- **Restez constant dans vos unités** pour une même culture.
- **Groupez** vos gestes d'une même session en une seule dictée multi-lignes.

### ❌ À éviter

- Mélanger plusieurs cultures dans une phrase non structurée. Une ligne = une culture.
- Commencer une phrase par un mot de navigation (*corriger*, *stats*, *plan*, *supprimer*) si ce n'est pas votre intention.
- Les abréviations peu communes : dites *« courgette »*, pas *« courge »* si vous voulez parler de courgette.
- Vouloir corriger un stock directement. Enregistrez le geste qui l'a fait bouger.
- Les tirets bas dans les noms de parcelle.

### 🎤 Spécifique au vocal

- Parlez **clairement et posément** — la transcription est bonne, pas magique.
- **Épelez les variétés rares** ou peu courantes.
- Préférez un **environnement calme** : le vent et le moteur de la tondeuse dégradent nettement la transcription.
- Les noms propres de variétés sont le point faible : vérifiez-les au récapitulatif.
- La dictée ne produit ni ponctuation ni accents fiables — ce n'est pas grave : l'assistant reconnaît les questions sans point d'interrogation et retrouve les mots sans leurs accents.

---

# PARTIE III — AIDE-MÉMOIRE

---

## 21. Toutes les commandes

Les 23 commandes du compagnon de terrain. Toutes sont accessibles depuis le bouton **Menu** de Telegram, à gauche de la zone de saisie — sauf trois, volontairement écartées du menu mais parfaitement fonctionnelles à la saisie : `/version`, `/delier` et `/tts`.

### 21.1 Enregistrer

| Commande | Ce qu'elle fait |
|---|---|
| `/note` | Noter une observation, guidé pas à pas (4 catégories) |
| `/corriger` | Corriger ou supprimer un événement |
| `/vendre <culture> [variété] <quantité>` | Enregistrer une vente de plants — ex. `/vendre tomate cerise 5` |

Tout le reste s'enregistre **sans commande**, en dictant ou en écrivant la phrase (chapitre 6).

### 21.2 Consulter

| Commande | Ce qu'elle fait |
|---|---|
| `/plan` | Plan d'occupation de toutes les parcelles |
| `/plan <parcelle>` | Détail d'une parcelle — ex. `/plan nord` |
| `/plan <date>` | Plan à une date passée — ex. `/plan 15/05/2026` |
| `/stats` | Bilan de saison : stock, semis en cours, pépinière |
| `/stats <culture>` | Détail par variété d'une culture |
| `/stats <culture> <date>` | Détail à une date passée |
| `/historique` | Les 10 derniers événements |
| `/ask <question>` | Poser une question sur le potager |
| `/meteo` | Relevé météo immédiat |

### 21.3 Cultures et référentiel

| Commande | Ce qu'elle fait |
|---|---|
| `/fiche <culture>` | Fiche courte : famille, délai de retour, exposition, eau, profondeur, rusticité |
| `/culture attributs <culture>` | Les quatre caractéristiques de conduite et leur source |
| `/culture exposition <culture> <plein soleil\|mi-ombre\|ombre>` | Corriger l'exposition |
| `/culture eau <culture> <faible\|moyen\|élevé>` | Corriger le besoin en eau |
| `/culture profondeur <culture> <cm>` | Corriger la profondeur de semis |
| `/culture rusticite <culture> <°C>` | Corriger la rusticité minimale |
| `/culture famille <culture> <famille>` | Corriger la famille botanique |
| `/culture delai_retour <famille> <années>` | Corriger le délai de retour d'une famille entière |
| `/association lister <culture>` | Cultures à associer ou à éloigner |
| `/association saisir <A> <B> <favorable\|defavorable\|neutre> <etabli\|traditionnel> <motif>` | Saisir ou corriger une association |
| `/rotation <parcelle> <culture>` | Vérifier la rotation avant de planter |

### 21.4 Parcelles

| Commande | Ce qu'elle fait |
|---|---|
| `/parcelle lister` · `/parcelles` | Lister les parcelles |
| `/parcelle ajouter <nom> [exposition] [m²]` | Créer une parcelle |
| `/parcelle modifier <nom> clé=valeur…` | Modifier `exposition`, `superficie`, `ordre`, `pepiniere` |
| `/parcelle renommer <ancien> <nouveau>` | Renommer, avec propagation sur tout l'historique |
| `/parcelle supprimer <nom>` | Retirer une parcelle — les événements passent en « Non localisé » |

### 21.5 Compte et potager

| Commande | Ce qu'elle fait |
|---|---|
| `/start` | Accueil et état du potager |
| `/start <code>` | Activation directe depuis un lien de l'application web |
| `/lier <code>` | Relier cette conversation à votre compte |
| `/delier` | Détacher cette conversation du compte |
| `/potager` | Changer de potager actif |

### 21.6 Confort et aide

| Commande | Ce qu'elle fait |
|---|---|
| `/tts` | État de la synthèse vocale |
| `/tts_on` · `/tts_off` | Activer / couper les réponses vocales |
| `/help` | Aide générale |
| `/help <domaine>` | Aide ciblée : `parcelle` · `semis` · `godet` · `recolte` · `stock` · `stats` · `note` · `culture` · `fiche` |
| `/version` | Version déployée, commit, environnement |

---

## 22. Les formulations reconnues

Vous n'avez rien à apprendre par cœur : cette table sert à lever un doute, pas à réciter. Casse, accents et pluriels sont indifférents.

| Geste enregistré | Dites par exemple |
|---|---|
| **Récolte** | récolté · récolte · cueilli · cueillir · ramassé · ramasser |
| **Semis** | semé · semer · semis · semis direct · pleine terre · à la volée |
| **Mise en godet** | mise en godet · mis en godet · repiqué en godet · rempotage godet |
| **Plantation** | planté · planter · repiqué · repiquage · mis en terre · transplanté |
| **Arrosage** | arrosé · arroser · irrigué · donné de l'eau |
| **Désherbage** | désherbé · désherber · sarclé · sarclage · enlevé les mauvaises herbes |
| **Binage** | biné · biner · binage |
| **Éclaircissage** | éclairci · éclaircir · éclaircie · éclaircissage |
| **Paillage** | paillé · pailler · paillis · mulch · mis de la paille · couvert le sol |
| **Amendement** | amendé · fertilisé · compost · fumier · terreau · engrais · apport |
| **Taille** | taillé · tailler · pincé · coupé · élagué · rabattu |
| **Tuteurage** | tuteuré · mis un tuteur · attaché · palissé · palissage |
| **Traitement** | traité · pulvérisé · savon noir · purin d'ortie · bouillie bordelaise |
| **Protection** | protégé · voile · filet · cloche · tunnel · anti-insectes · protégé du gel |
| **Observation** | observé · constaté · surveillé · maladie · mildiou · limaces · gel |
| **Perte au jardin** | perdu · mort · arraché · crevé · disparu |
| **Perte en pépinière** | perdu en godet · perdu en pépinière · perte pépinière · graines perdues |
| **Vente de plants** | vendu · vendre · vente · donné · cédé |

### 22.1 Les phrases qui ne sont pas des enregistrements

Certaines phrases sont comprises comme une **navigation** plutôt que comme un geste. C'est voulu, et c'est pourquoi il vaut mieux ne pas commencer une dictée par ces mots-là si l'on veut enregistrer quelque chose.

| Vous dites | L'assistant ouvre |
|---|---|
| *« plan du potager »*, *« qu'est-ce qui pousse en nord ? »* | Le plan d'occupation |
| *« bilan du potager »*, *« stats tomates »*, *« synthèse semis »* | Les statistiques |
| *« historique »*, *« mes derniers événements »* | Le journal |
| *« corriger »*, *« modifier »* | Le parcours de correction |
| *« supprimer »*, *« effacer »*, *« annuler »* | La suppression du dernier événement |
| *« je veux noter une observation »* | La saisie guidée de note |
| *« déplacer mes tomates sur la parcelle nord »* | Le déplacement de culture |
| *« combien… »*, *« quand… »*, *« quelle… »* | Une réponse à votre question |

---

## 23. Glossaire

**Association (favorable / défavorable / neutre)** — Ce que deux cultures voisines se font l'une à l'autre. Une association *établie* est démontrée ; une association *traditionnelle* est transmise par l'usage. L'assistant ne confond jamais les deux.

**Culture reproductrice** — Culture dont on consomme le fruit ou la graine, et dont le pied continue de produire après la récolte : tomate, courgette, haricot, concombre, poivron. Récolter n'y fait pas baisser le stock de pieds.

**Culture végétative** — Culture dont on consomme la feuille, la tige, la racine ou le bulbe, et dont le pied disparaît à la récolte : salade, carotte, radis, poireau, oignon, pomme de terre. Récolter y fait baisser le stock.

**Date de référence** — Date à laquelle on demande de figer le calcul, pour consulter le potager tel qu'il était ce jour-là. La date qui compte est celle du geste, jamais celle de la saisie.

**Délai de retour** — Nombre d'années à attendre avant de refaire une culture de la même famille au même endroit. C'est une propriété de la **famille**, pas du légume.

**Éditeur** — Membre d'un potager qui peut enregistrer, corriger et supprimer des gestes, mais ne gère ni les membres ni le potager lui-même.

**Famille botanique** — Groupe de cultures qui épuisent le sol de la même façon et partagent les mêmes maladies (solanacées, cucurbitacées, fabacées…). C'est l'unité de raisonnement de la rotation.

**Godet** — Plant repiqué individuellement, en attente d'être mis en terre. Le stock de godets se déduit tout seul des plantations et des ventes.

**Lot de semis** — Un semis fait à couvert, identifié par sa date. Deux semis de la même variété à deux dates restent deux lots distincts.

**Non localisé** — Mention qui regroupe les gestes dont la parcelle n'a jamais été précisée, ou dont la parcelle a été supprimée depuis.

**Parcelle** — Unité de lieu du potager : planche, carré, bac, butte, serre, rang. Elle porte l'historique qui rend la rotation calculable.

**Parcelle pépinière** — Parcelle déclarée comme serre ou châssis. Un semis qui s'y rattache reste à couvert et n'entre pas au stock du jardin.

**Potager actif** — Celui que visent vos dictées et vos questions quand vous en tenez plusieurs. Il se change explicitement, jamais tout seul.

**Rendement** — Poids cumulé récolté sur une culture. Distinct du stock, et jamais calculé à partir de lui.

**Stock** — Nombre de pieds vivants au jardin, plus, séparément, le nombre de plants en godet. Jamais un stock de semences.

---

## 24. Dépannage

| Symptôme | Cause la plus fréquente | Ce qu'il faut faire |
|---|---|---|
| Le bot ne répond que par un message d'accueil | La conversation n'est pas reliée à un compte | Activer le compagnon depuis l'application web (chapitre 3) |
| « Vous n'êtes membre d'aucun potager » | Compte relié mais sans potager | Créer ou rejoindre un potager depuis l'application web |
| Le bot dit que le rôle ne permet pas d'enregistrer | Vous êtes en lecture seule sur ce potager | Demander le rôle éditeur au propriétaire |
| Mon stock de tomates ne baisse pas quand je récolte | La tomate est une culture reproductrice | Normal : le pied reste. Le rendement, lui, augmente (section 12.2) |
| Mon semis n'apparaît pas dans la pépinière | Il a été rattaché à une parcelle de plein champ | Corriger la parcelle du geste, ou déclarer cette parcelle `pepiniere=true` |
| Un total paraît faux ou incomplet | Deux unités mélangées sur la même culture | Ramener les gestes concernés à une même unité (section 15.6) |
| Une culture arrachée reste affichée sur le plan | L'arrachage n'a jamais été dicté | Enregistrer la perte / l'arrachage (section 13.2) |
| Un lot affiche « germination indéterminée » | Le nombre de graines d'origine n'a jamais été donné | Le préciser à la prochaine mise en godet, ou corriger le semis |
| Un lot affiche plus de plants que de graines | Incohérence de saisie signalée volontairement | Retrouver le geste fautif dans le journal et le corriger |
| Ma phrase a été comprise comme une question | Elle commence par un mot de navigation | Reformuler en commençant par le geste : *« récolté… »* |
| Une culture est refusée à l'enregistrement | Elle n'a jamais été semée ni plantée dans ce potager | Enregistrer d'abord le semis ou la plantation, ou vérifier la transcription |
| Le récapitulatif a disparu sans rien enregistrer | Les 60 secondes de confirmation ont expiré | Redicter la phrase |
| Le code d'activation est refusé | Code expiré (10 min), déjà utilisé, ou conversation déjà reliée | Générer un nouveau code ; si la conversation est liée ailleurs, la délier d'abord |
| La météo affichée n'est pas celle de mon jardin | La commune du potager n'est pas renseignée | La renseigner dans les paramètres du potager |
| Aucun avertissement de rotation n'apparaît | Soit tout va bien, soit rien n'est connu de la parcelle | Vérifier explicitement avec `/rotation <parcelle> <culture>` |

---

## 25. Ce guide et la base de connaissance

Ce guide est la **source** du corpus que l'assistant consulte pour répondre aux questions sur son propre fonctionnement. Les fiches de ce corpus en dérivent : elles reprennent ce qui est écrit ici, découpé en sections autonomes et rédigé dans le vocabulaire du jardinier.

Deux conséquences pratiques :

1. **Une section de ce guide doit se comprendre seule.** Elle doit répondre à une question qu'un jardinier pose réellement, sans supposer la lecture de la section précédente. C'est la raison des redites assumées d'un chapitre à l'autre.
2. **Une évolution de l'application qui rend une section fausse impose sa correction dans la même livraison.** Un guide faux est plus nuisible qu'un guide absent, parce qu'il est servi au jardinier comme vérifié — mot pour mot, sans qu'aucun modèle ne vienne le nuancer.

Le guide ne décrit pas encore le tableau de bord web **écran par écran** : la Partie web se limite ici à l'accès, aux principes de navigation et à la date de référence. Les fonctions du web qui n'ont pas d'équivalent sur Telegram — export du journal, gestion des membres, cycle de vie du potager — sont documentées au fil des chapitres concernés.

---

*Fin du guide — Assistant Potager, septembre 2026.*
