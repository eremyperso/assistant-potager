# 🌿 Guide de l'Assistant Potager

**Version 3.14 — Juillet 2026**
*Guide utilisateur complet — Telegram & tableau de bord web*

---

> **Comment lire ce guide**
>
> Les **Parties I et II** vous apprennent à alimenter votre potager au quotidien depuis Telegram, dans l'ordre naturel d'une saison de culture.
> La **Partie III** décrit écran par écran le tableau de bord web, pour consulter et analyser.
> La **Partie IV** rassemble les aide-mémoire : toutes les commandes, le glossaire, le dépannage.
>
> Si vous débutez, lisez les chapitres 1 à 4 puis suivez la saison. Si vous cherchez une commande précise, allez directement à l'aide-mémoire en Partie IV.

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
- quand vous avez traité les rosiers pour la dernière fois, et avec quoi.

### 1.2 Ce que l'application fait — et ne fait pas

**Ce qu'elle fait bien**

| Domaine | Détail |
|---|---|
| **Saisie terrain** | Dictée vocale mains sales, en langage naturel, sans formulaire |
| **Mémoire fiable** | Tout est daté, structuré, corrigeable, jamais perdu |
| **Traçabilité pépinière** | Chaîne complète graine → godet → plant en terre → récolte |
| **Consultation** | Bilans par culture, par parcelle, par date, état à une date passée |
| **Météo** | Relevé quotidien automatique, historique consultable |

**Ce qu'elle ne fait pas encore**

L'assistant est **rétrospectif** : il enregistre et restitue ce que vous avez fait. Il ne vous dit pas encore quoi faire. Concrètement, il n'y a aujourd'hui **pas** de :

- calendrier de semis ou rappels proactifs (« il est temps de semer les poireaux ») ;
- conseils de rotation ou d'association de cultures ;
- diagnostic de maladie à partir d'une photo ;
- prévision de récolte ou calcul de rentabilité.

Savoir cela vous évitera d'attendre de l'assistant ce qu'il ne peut pas donner — et vous montre où il excelle : **ne jamais oublier ce que vous avez fait**.

### 1.3 Les deux façons d'accéder à l'application

L'Assistant Potager a **deux visages**, qui partagent exactement les mêmes données.

```
                    ┌─────────────────────────┐
                    │   VOTRE CARNET DE BORD  │
                    │      (données uniques)  │
                    └───────────┬─────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              │                                   │
      ┌───────▼────────┐                 ┌────────▼────────┐
      │   TELEGRAM     │                 │  TABLEAU DE BORD│
      │   (le bot)     │                 │      (web)      │
      ├────────────────┤                 ├─────────────────┤
      │ Au potager     │                 │ Au calme        │
      │ Mains sales    │                 │ Sur écran       │
      │ À la voix      │                 │ Visuel          │
      │ ÉCRIRE         │                 │ LIRE            │
      └────────────────┘                 └─────────────────┘
```

| | **Telegram** | **Tableau de bord web** |
|---|---|---|
| **Quand** | Sur le terrain, pendant l'action | Le soir, au bureau, en planification |
| **Comment** | Vocal ou texte, langage naturel | Navigation tactile, filtres |
| **Sert à** | **Enregistrer** ce que vous faites | **Comprendre** où vous en êtes |
| **Consultation** | Possible, en texte | Bien plus lisible, graphique |
| **Saisie** | Complète | Aucune (consultation seule) |

**Règle pratique :** *tout ce qui s'écrit passe par Telegram, tout ce qui se regarde passe par le web.*

Rien ne vous empêche de consulter depuis Telegram — `/plan`, `/stats` et `/historique` répondent très bien. Mais un plan de parcelles ou une courbe de rendement se lisent nettement mieux sur le tableau de bord.

### 1.4 Comment ça marche, en une page

Quand vous envoyez un message vocal :

1. **Vous parlez** dans Telegram — par exemple *« Récolté 2 kilos de tomates cerise en parcelle nord »*.
2. **L'assistant transcrit** votre voix en texte.
3. **Il identifie votre intention** : est-ce une action à enregistrer, une question, une demande de statistiques, une correction ?
4. **Il extrait les informations** : le type d'action (récolte), la culture (tomate), la variété (cerise), la quantité (2), l'unité (kg), la parcelle (nord), la date (aujourd'hui par défaut).
5. **Il vous montre un récapitulatif** et attend votre validation.
6. **Vous confirmez** — et seulement à ce moment l'information est enregistrée.

Cette étape de confirmation est importante : **rien n'est jamais enregistré à votre insu**. Si l'assistant a mal compris, vous annulez et vous redictez.

---

## 2. Les principes de fonctionnement

Trois notions à comprendre une bonne fois pour toutes. Elles expliquent tout le reste du guide.

### 2.1 Tout est un événement daté

L'assistant ne raisonne pas en « fiches » ou en « stocks » que l'on modifierait. Il raisonne en **événements** : des faits datés, empilés dans l'ordre chronologique.

Vous n'écrivez jamais « j'ai 12 plants de tomates ». Vous écrivez :

- *« Semé 30 graines de tomate Cœur de bœuf »* (le 5 mars)
- *« Mise en godet 24 tomates Cœur de bœuf »* (le 28 mars)
- *« Planté 12 tomates Cœur de bœuf parcelle nord »* (le 3 mai)
- *« Perdu 2 pieds de tomate, gel »* (le 6 mai)

Et l'assistant **calcule** : 12 plantés − 2 perdus = 10 pieds actifs, avec 12 plants encore en godet.

**Conséquence pratique n° 1** : ne « corrigez » pas un stock en essayant de dicter le total. Enregistrez l'événement qui a fait bouger le stock (une perte, une récolte, une vente), et le total se recalcule seul.

**Conséquence pratique n° 2** : comme tout est daté, l'assistant peut reconstituer l'état de votre potager **à n'importe quelle date passée**. C'est ce qui permet de répondre à « qu'est-ce qui poussait en parcelle nord le 1ᵉʳ mai ? ».

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
      ├──────────────► 💰 VENTE  « vendu 5 plants de tomate »
      │
      ├──────────────► ❌ PERTE EN GODET  « perdu 2 plants en pépinière »
      │
      ▼
   🌿 PLANTATION
   « planté 12 tomates Cœur de bœuf parcelle nord »
      │                    → stock godet restant : 24 − 12 − 5 − 2 = 5
      │
      ├──────────────► ❌ PERTE  « perdu 2 pieds, gel »
      │
      │  (entretien : arrosage · paillage · taille · tuteurage · traitement)
      │
      ▼
   🧺 RÉCOLTE
   « récolté 2 kg de tomates Cœur de bœuf parcelle nord »
```

Chaque étape retire automatiquement du stock de l'étape précédente. Le calcul se fait **par couple culture + variété** : planter des courgettes jaunes ne touche pas au stock de courgettes vertes.

**Cas particulier — le semis direct.** Certains légumes ne passent jamais par la pépinière : carottes, radis, haricots, épinards. Vous les semez directement en pleine terre. Dans ce cas, il n'y a pas d'étape godet ni d'étape plantation : vous passez du semis directement à la récolte. Précisez-le en dictant : *« semis direct carottes en parcelle B »*.

### 2.3 Les parcelles structurent tout

Une **parcelle** est une zone identifiée de votre potager : une planche, un carré, une serre, un rang. Vous leur donnez les noms que vous voulez — *nord*, *maison*, *planche-oignon*, *B2*.

Mentionner la parcelle dans vos dictées n'est jamais obligatoire, mais **c'est ce qui débloque le plus de valeur** :

- vous pouvez filtrer toutes vos questions par zone ;
- le plan d'occupation vous montre qui pousse où ;
- vous voyez le taux d'occupation de chaque surface ;
- vous préparez vos rotations d'une saison sur l'autre.

Une parcelle peut être marquée comme **pépinière** (une serre, un châssis). Cette distinction compte : un semis rattaché à une pépinière reste considéré comme *en pépinière*, il n'est pas compté comme cultivé en pleine terre.

---

## 3. Le tableau de bord web — accès et principes

### 3.1 Comment y accéder

Le tableau de bord s'ouvre dans un simple navigateur, sur téléphone comme sur ordinateur.

> **⚠️ À COMPLÉTER** — indiquer ici l'URL de production et les modalités d'accès.

### 3.2 L'installer sur votre iPhone

Le tableau de bord est une application web installable : une fois posée sur l'écran d'accueil, elle s'ouvre en plein écran, sans barre de navigateur, exactement comme une application native.

1. Ouvrez l'adresse du tableau de bord dans **Safari** (pas Chrome — l'installation ne fonctionne que depuis Safari sur iPhone).
2. Touchez le bouton **Partager** (le carré avec la flèche vers le haut).
3. Faites défiler et choisissez **« Sur l'écran d'accueil »**.
4. Nommez-la *Potager* et validez.

L'icône apparaît sur votre écran d'accueil. Vous pouvez maintenant l'ouvrir d'un geste.

### 3.3 Les principes de navigation

Le tableau de bord est conçu **pour le pouce** : les onglets sont en bas de l'écran, à portée, plutôt qu'en haut.

- **Cinq onglets** en bas : Plan, Stocks, Pépinière, Historique, Stats.
- **Une barre de titre** en haut, avec un bouton de rafraîchissement et un bouton clair/sombre.
- **Un sélecteur de date** sur chaque écran, pour remonter dans le temps.
- **Un filtre par culture** sur les écrans qui listent des cultures.

Deux thèmes sont disponibles : un mode clair *parchemin* pour le plein soleil, un mode sombre *kaki forêt* pour le soir. Votre choix est mémorisé.

### 3.4 La date de référence — voir le potager dans le passé

C'est la fonction la plus puissante du tableau de bord, et la plus facile à manquer.

En haut de chaque écran, un bouton affiche **« Aujourd'hui »**. Touchez-le : un calendrier s'ouvre, et vous choisissez n'importe quelle date passée. Tous les écrans se recalculent alors comme si vous étiez ce jour-là.

- Le bouton **change de couleur (ambre)** pour vous rappeler en permanence que vous n'êtes plus « en direct ».
- La date **vous suit d'un onglet à l'autre** : réglée sur le Plan, elle reste active sur Stocks, Pépinière et Historique.
- Elle **survit à un rechargement** de page.
- Les dates futures ne sont pas sélectionnables.
- Pour revenir au présent, rouvrez le calendrier et touchez **« Aujourd'hui »**.

**Usages concrets :** comparer l'occupation de vos parcelles à la même date l'an dernier, retrouver l'état de votre pépinière au moment d'une vente de plants, vérifier ce qui poussait avant un arrachage.

Le **filtre par culture**, lui, ne suit pas : il est propre à chaque écran et se remet à zéro quand vous changez d'onglet. C'est volontaire — on filtre pour une consultation ponctuelle, pas pour une session entière.

---

# PARTIE II — LE PARCOURS D'UNE SAISON

Cette partie suit l'ordre chronologique d'une saison de culture. Chaque chapitre correspond à un moment de l'année et vous dit **quoi faire, dans quel ordre, et avec quels mots**.

---

## 4. Premiers pas — les cinq minutes qui comptent

### 4.1 Ouvrir le bot

Ouvrez Telegram, trouvez votre bot Assistant Potager, et envoyez :

```
/start
```

Le bot affiche le menu principal, le nombre d'événements déjà enregistrés, et un clavier de boutons. Ces boutons resteront disponibles en permanence en bas de votre écran.

### 4.2 Dire bonjour à l'aide

```
/help
```

C'est votre référence permanente. Elle liste les actions reconnues, les commandes disponibles et des exemples de phrases.

Vous pouvez aussi demander une **aide ciblée** sur un domaine précis :

```
/help parcelle     /help semis      /help godet
/help recolte      /help stock      /help stats      /help note
```

Chacune donne les variantes de saisie reconnues pour ce domaine, avec des exemples concrets.

### 4.3 Créer vos parcelles — à faire en premier

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

### 4.4 Ajuster une parcelle

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

### 4.5 Renommer et lister

```
/parcelle renommer sud carré-sud
```

Le renommage se propage sur **tout l'historique** : aucun événement passé n'est orphelin.

```
/parcelle lister
/parcelles
```

### 4.6 Votre premier enregistrement

Envoyez un message vocal ou tapez simplement :

```
Récolté 2 kg de tomates cerise parcelle nord
```

Le bot affiche un récapitulatif de ce qu'il a compris, avec deux boutons : **✅ Confirmer** et **❌ Annuler**. Touchez Confirmer. C'est fait.

Vous savez maintenant l'essentiel. Le reste du guide n'est que du détail.

---

## 5. Enregistrer une action — les règles générales

Avant d'entrer dans le détail de chaque type d'action, voici ce qui vaut pour toutes.

### 5.1 Parlez normalement

Vous n'avez pas de syntaxe à apprendre. Ces trois phrases produisent le même enregistrement :

- *« Récolté 2 kg de tomates cerise en parcelle nord »*
- *« J'ai ramassé deux kilos de tomates cerise, parcelle nord »*
- *« Cueilli 2 kilos de cerise, tomates, nord »*

L'assistant reconnaît de nombreux synonymes pour chaque action : *récolter, cueillir, ramasser* ; *planter, repiquer, mettre en terre* ; *arroser, irriguer* ; *fertiliser, amender, mettre du compost*.

### 5.2 Les informations extraites

| Information | Obligatoire | Exemples |
|---|---|---|
| **Type d'action** | oui | récolte, semis, plantation, arrosage… |
| **Culture** | quasi toujours | tomate, courgette, carotte, poivron |
| **Variété** | non | cerise, Nantaise, Cœur de bœuf, Butternut |
| **Quantité** | non | 2.5 · 12 · 30 |
| **Unité** | non | kg, g, litre, plants, pieds, minutes |
| **Parcelle** | non | nord, B2, serre, maison |
| **Rangs** | non | nombre de rangs plantés |
| **Date** | non | par défaut : aujourd'hui |
| **Traitement / produit** | non | savon noir, bouillie bordelaise, purin d'ortie, paille |
| **Commentaire** | non | tout complément libre |

### 5.3 Les dates

| Vous dites | L'assistant comprend |
|---|---|
| *(rien)* | Aujourd'hui |
| *« hier »* | La veille |
| *« avant-hier »* | L'avant-veille |
| *« lundi »* | Le lundi le plus récent |
| *« le 5 mars »* | Le 5 mars de l'année en cours |

**Point d'attention :** si vous rattrapez une saisie de plusieurs semaines, dites explicitement la date (*« le 12 avril »*) plutôt qu'un repère relatif. Les repères relatifs sont calculés par rapport à aujourd'hui, pas par rapport à votre souvenir.

### 5.4 Quantités, unités et rangs

Le **rang** est un multiplicateur : *« planté 4 salades sur 3 rangs »* enregistre **12 plants**, pas 4.

Les unités s'adaptent au contexte : *kg* et *g* pour les récoltes pesées, *plants* et *pieds* pour les comptages, *minutes* pour les durées d'arrosage, *litre* pour les traitements.

### 5.5 Plusieurs actions d'un coup

Séparez-les par un **retour à la ligne**. Une seule dictée peut couvrir toute une matinée :

```
Récolté 3 kg de tomates cerise et 2 courgettes
Arrosé les poivrons 20 minutes
Paillé les aubergines avec de la paille
```

Chaque ligne devient un événement distinct. Le récapitulatif les liste toutes avant confirmation.

### 5.6 Le récapitulatif et la confirmation

**Rien n'est enregistré avant que vous ne validiez.** Systématiquement, le bot affiche ce qu'il a compris et attend.

- **✅ Confirmer** → enregistrement.
- **❌ Annuler** → rien n'est écrit, vous pouvez redicter.
- **Aucune réponse pendant 60 secondes** → la confirmation expire, rien n'est enregistré.

Si vous n'avez pas mentionné de parcelle mais que le contexte en réclame une, le bot vous propose la liste de vos parcelles sous forme de boutons, plus une option « sans parcelle ».

**Lisez toujours le récapitulatif.** C'est votre seul filet de sécurité contre une transcription approximative — et c'est trente fois plus rapide que de corriger après coup.

### 5.7 Ce que l'assistant refuse d'inventer

L'assistant est bridé pour ne jamais compléter ce que vous n'avez pas dit. Si vous dictez *« paillage parcelle nord »* sans mentionner de légume, il n'inventera pas une culture. Le champ reste vide.

De même, si vous dictez le nom approximatif d'une variété (*« nain »*), il cherche d'abord dans les variétés que vous utilisez déjà et retrouve *« vert nain Contender »* plutôt que de créer une variété fantôme.

---

## 6. Semer

*Février à juin, selon les cultures.*

### 6.1 Semis en pépinière

C'est le semis en plateau, en terrine ou en caissette, sous abri.

```
Semis tomates variété Saint-Pierre le 5 mars
J'ai semé 30 graines de basilic en plateau
Semé 50 graines de poivron Corno di Toro en serre
```

**Précisez toujours le nombre de graines.** C'est ce qui permettra de calculer votre taux de réussite à la levée. Sans ce chiffre, l'étape suivante n'a plus de référence.

### 6.2 Semis direct en pleine terre

Pour tout ce qui ne se repique pas : carottes, radis, haricots, épinards, mâche.

```
Semis direct carottes en parcelle B2
Semis radis pleine terre parcelle A3 le 8 avril
Semé des carottes Nantaise sur 2 rangs parcelle A
```

Le mot **« direct »** ou **« pleine terre »** est important : il indique que ce semis ne passera pas par la case pépinière, et qu'aucun godet ne viendra jamais le consommer.

### 6.3 Consulter vos semis

```
Liste de mes semis
Quels semis sont en cours ?
```

---

## 7. Suivre la pépinière

*Mars à mai. C'est la période où l'assistant est le plus utile — et le plus facile à oublier d'alimenter.*

### 7.1 La mise en godet

Quand vos semis ont levé et sont assez forts, vous les repiquez en godets individuels. C'est l'étape charnière entre le plateau et la pleine terre.

```
Mise en godet tomates Saint-Pierre 20 plants
Repiquer 15 plants de poivron en godet le 10 mars
```

**C'est ici que se calcule votre taux de réussite** : 20 plants repiqués sur 30 graines semées = 67 % de réussite. Ce chiffre, accumulé sur plusieurs saisons, vous dira quelles variétés lèvent bien chez vous.

### 7.2 Le rattachement au lot de semis

Si vous avez fait **plusieurs semis de la même variété** à des dates différentes, le bot vous demande de quel lot proviennent les plants, sous forme de boutons :

```
🌱 Lot 15 mars — 12 restantes
🌱 Lot 01 avr — 10 restantes
❌ Annuler
```

Choisissez le bon lot : c'est ce qui permet de suivre le rendement réel de chaque semis. S'il n'y a qu'un seul lot possible, le rattachement est automatique et rien ne vous est demandé.

### 7.3 Vendre ou donner des plants

Si vous produisez plus de plants qu'il ne vous en faut :

```
/vendre tomate Saint-Pierre 5
```

Ou en langage naturel : *« vendu 5 plants de tomate Saint-Pierre »*, *« donné 3 courgettes jaunes »*.

Ces sorties sont déduites de votre stock de godets, exactement comme une plantation. Elles apparaissent distinctement dans le tableau de bord.

### 7.4 Les pertes en pépinière

```
Perdu 4 plants de poivron en godet, fonte des semis
Perte pépinière 10 graines de basilic
```

Distinguer une **perte en godet** d'une **perte au champ** compte : la première touche votre stock de pépinière, la seconde vos pieds en terre.

### 7.5 Consulter la pépinière

```
Liste des godets
Quels plants sont en godet ?
```

Ou, bien plus lisible, l'onglet **Pépinière** du tableau de bord.

---

## 8. Planter

*Avril à juin, après les dernières gelées.*

```
Planté 12 plants de poivrons en 3 rangs
Planté 6 tomates Cœur de bœuf parcelle nord
Repiqué 24 salades en parcelle B
Mis en terre 8 courgettes jaunes parcelle sud
```

### 8.1 Ce qui se passe automatiquement

Chaque plantation **déduit du stock de godets** de la même culture et de la même variété. Vous n'avez rien à faire : dire que vous avez planté suffit à faire baisser votre pépinière.

Le calcul est strict par couple culture + variété. Planter 4 courgettes jaunes ne touche pas au stock de courgettes vertes. Si votre godet a été enregistré sans variété et qu'une seule variété apparaît dans vos plantations, l'assistant fait le rapprochement lui-même.

### 8.2 Précisez la parcelle

C'est le moment où mentionner la parcelle a le plus de valeur : c'est cette information qui alimente votre plan d'occupation pour toute la saison. Si vous devez ne le faire qu'une seule fois, faites-le ici.

### 8.3 La levée des semis directs

Pour les cultures semées directement en pleine terre, il n'y a pas de plantation. Notez la **levée** quand vous voyez sortir les premières pousses :

```
Levée des haricots parcelle B2
```

---

## 9. Entretenir

*Toute la saison.*

Ces actions ne modifient aucun stock. Elles construisent votre historique d'interventions — ce qui, en fin de saison, vous permet de savoir combien de fois vous avez arrosé, avec quoi vous avez traité, et quand.

| Action | Exemples de dictée |
|---|---|
| 💧 **Arrosage** | *« Arrosé les courgettes 30 minutes »* · *« Irrigué la parcelle nord »* |
| 🌾 **Paillage** | *« Paillé les tomates avec de la paille »* · *« Mulch sur les courges »* |
| 🌿 **Désherbage** | *« Désherbé la parcelle des carottes »* · *« Sarclé les rangs de poireaux »* |
| ✂️ **Taille** | *« Taillé les poivrons, supprimé les gourmands »* · *« Pincé les tomates »* |
| 🪵 **Tuteurage** | *« Tuteuré les tomates Cœur de bœuf »* · *« Palissé les haricots »* |
| 🧪 **Traitement** | *« Traité les rosiers au savon noir »* · *« Bouillie bordelaise sur les tomates, 1 litre »* |
| 🛡️ **Protection** | *« Posé un voile sur les salades »* · *« Filet anti-insectes sur les choux »* |
| 🌱 **Amendement** | *« Fertilisé les courges avec du compost »* · *« Épandu du fumier parcelle est »* |

**Toujours nommer le produit** pour les traitements et amendements. C'est la seule façon de retrouver ensuite ce que vous avez appliqué, en quelle quantité et à quelle fréquence.

**Toujours donner la durée** pour les arrosages. C'est ce qui permet de cumuler votre consommation d'eau sur la saison.

---

## 10. Observer et noter

*Toute la saison — le chapitre le plus sous-estimé.*

### 10.1 Pourquoi une note n'est pas une action

Les chapitres précédents décrivent des **actions** : vous avez fait quelque chose. Une **note** décrit un *constat* : vous avez vu quelque chose.

Il n'y a pas de quantité, pas de geste, souvent pas d'unité. Forcer une observation dans le moule d'une action produit des données bancales. C'est pourquoi l'assistant propose un flux dédié, qui vous **pose les bonnes questions** au lieu de vous laisser deviner ce qu'il faut dire.

### 10.2 Déclencher une note

Deux façons, strictement équivalentes :

```
/note
```

Ou dictez simplement :

- *« Je veux noter une observation »*
- *« Je veux noter que le sol est sec sur la parcelle sud »*
- *« Il faut que je note un truc sur les tomates »*
- *« Ajouter une note »*

### 10.3 Choisir la catégorie

Le bot affiche quatre boutons. Le choix détermine la question qu'il vous posera ensuite.

| Catégorie | Pour quoi |
|---|---|
| 🔍 **Observation** | Remarque générale de suivi : croissance, aspect, comportement |
| 🐛 **Maladie / ravageur** | Problème sanitaire détecté |
| 💧 **Arrosage (remarque)** | Constat qualitatif lié à l'eau — **sans** créer d'arrosage réel |
| 🌿 **Paillage** | Constat ou action de paillage informelle |

> **À retenir sur la catégorie Arrosage.** Elle sert à consigner un *constat* — sol sec, sol détrempé, fuite du goutte-à-goutte. Elle **n'enregistre pas un arrosage**. Si vous avez réellement arrosé, dictez une action d'arrosage normale (chapitre 9).

### 10.4 Répondre à la question guidée

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

### 10.5 Ce que l'assistant extrait

De votre réponse libre, il tire automatiquement : la culture, la variété, la parcelle, le constat reformulé, le traitement ou matériau, une durée si pertinente, et une date si vous en mentionnez une (*« hier »*).

Il ne remplit **que** ce que vous avez dit. Le reste reste vide.

Culture et variété sont rapprochées de ce que vous utilisez déjà : si vous dites *« nain »* et que vous cultivez du haricot *« vert nain Contender »*, c'est cette variété qui est retenue.

### 10.6 Annuler

À n'importe quel moment du flux : bouton **❌ Annuler**, ou tapez simplement `annuler`. Rien n'est enregistré.

### 10.7 Où retrouver vos notes

Vos notes ne dorment pas dans un coin. Elles **remontent dans le tableau de bord**, sous forme d'une petite icône de bulle de dialogue :

- Si la note concerne une parcelle → l'icône apparaît **sur la parcelle**, dans l'onglet Plan.
- Si la note concerne une culture sans parcelle précise → l'icône apparaît **sur la culture**, dans l'onglet Stocks.
- Cas malin : si vous notez quelque chose sur une culture et une variété précises **sans dire la parcelle**, et que cette variété n'est cultivée qu'à un seul endroit, l'assistant la rattache tout seul à la bonne parcelle.

Un badge indique le nombre de notes (plafonné à « 10+ »). Un clic déplie un aperçu, paginé par blocs de trois.

### 10.8 Aide dédiée

```
/help note
```

---

## 11. Récolter

*Juin à novembre.*

### 11.1 Récolte ponctuelle

Pour les cultures qui produisent en continu — tomates, courgettes, haricots :

```
Récolté 800 g de tomates en A1
Cueilli 3 courgettes parcelle B2 aujourd'hui
Ramassé 1 kg de haricots verts hier
```

### 11.2 Récolte finale et clôture

Quand vous arrachez tout et que la culture est terminée :

```
Récolte finale haricots parcelle A3
Dernière récolte courgettes B2, culture terminée
```

La mention *finale* ou *terminée* solde le stock de la culture et libère la parcelle pour la suite.

### 11.3 Récolte de graines

Si vous produisez vos propres semences :

```
Récolte graines tomates Saint-Pierre 15 g
Mis de côté graines courge pour semis prochain
```

### 11.4 Consulter l'historique des récoltes

```
Historique récoltes
Mes récoltes du mois de mars
```

---

## 12. Enregistrer les pertes

*Toute la saison. C'est la partie qu'on saute — et c'est celle qui fausse tous les chiffres si on la saute.*

Un stock qui ne baisse jamais est un stock faux. Si vous perdez des pieds, dites-le.

```
Perdu 3 pieds de tomate, gel
Perdu 2 courgettes, limaces
Arraché les poireaux, mildiou
2 salades mortes de sécheresse
```

L'assistant reconnaît de nombreuses formulations : *perdu, mort, arraché, crevé, disparu*.

**Distinguez bien :**

| Situation | Ce que vous dictez |
|---|---|
| Perte de plants **en godet** | *« Perdu 4 plants de poivron en godet »* |
| Perte de pieds **en terre** | *« Perdu 3 pieds de tomate, gel »* |
| Arrachage de fin de saison | *« Arraché toutes les courgettes, fin de saison »* |
| Récolte finale (vous récoltez avant d'arracher) | *« Récolte finale haricots parcelle A3 »* |

Une perte n'est pas un aveu d'échec : c'est une donnée. Sur trois saisons, elle vous dira quelles cultures et quelles parcelles vous coûtent le plus.

---

## 13. Consulter et interroger

*Le soir, à froid.*

### 13.1 Le plan d'occupation

```
/plan
/plan nord
/plan 15/05/2026
```

Ou en langage naturel : *« plan du potager »*, *« qu'est-ce qui pousse en nord ? »*.

Le plan global liste chaque parcelle avec ses cultures actives et leur ancienneté. Le plan détaillé d'une parcelle donne le détail par culture : nombre de plants, date de plantation, jours écoulés.

### 13.2 Les statistiques

```
/stats
/stats tomate
/stats tomate 15/05/2026
```

Ou : *« bilan du potager »*, *« stats tomates »*, *« bilan courgettes cette saison »*, *« synthèse semis »*.

`/stats` seul donne le bilan de saison, séparé entre cultures **végétatives** (dont on mange les feuilles, tiges, racines) et **reproductrices** (dont on mange les fruits ou graines). `/stats <culture>` descend au détail par variété, avec le stock de pépinière associé.

### 13.3 L'historique

```
/historique
```

Les derniers événements enregistrés, du plus récent au plus ancien. Pratique pour vérifier ce que vous venez de saisir.

### 13.4 Poser une question libre

C'est la fonction la plus souple : vous posez une question, l'assistant cherche la réponse dans votre historique.

```
/ask Combien de kg de tomates ai-je récoltés cette saison ?
```

Vous pouvez aussi taper simplement votre question, ou toucher le bouton **🔍 Interroger**.

**Questions qui marchent bien :**

| Type | Exemple |
|---|---|
| Quantité | *« Combien de kg de tomates récoltés cette saison ? »* |
| Date | *« Quand ai-je planté mes courgettes ? »* |
| Dernière fois | *« Dernier arrosage des poivrons »* |
| Bilan | *« Bilan de ma saison de carottes »* |
| Par parcelle | *« Qu'est-ce que j'ai récolté en parcelle nord ? »* |
| Comparaison | *« Quelle parcelle a le plus produit ? »* |

**Formulez des questions complètes.** Une question de trois mots (*« date récoltes »*) fait passer l'assistant en mode question et vous demande de reformuler — deux échanges au lieu d'un. Une question complète est traitée directement.

> **Une limite à connaître.** L'interrogation libre consulte un extrait de votre historique, pas la totalité de vos archives. Sur des questions très larges couvrant plusieurs années, préférez `/stats` et le tableau de bord, qui calculent sur l'ensemble des données.

---

## 14. Corriger une erreur

*Dès que vous vous en apercevez.*

### 14.1 Lancer une correction

```
/corriger
```

Ou dites *« corriger »*, *« modifier »*, ou touchez **✏️ Corriger**.

### 14.2 Le déroulé

**1. Retrouver l'événement.** Décrivez-le : *« la récolte de tomates d'hier »*. Ou tapez simplement **`1`** pour désigner le tout dernier événement enregistré — c'est le cas de loin le plus fréquent.

**2. Choisir parmi les candidats.** Le bot liste ce qu'il a trouvé, numéroté. Vous choisissez.

**3. Dicter la correction** en langage naturel : *« la quantité c'était 3 kg »*, *« c'était en parcelle sud »*, *« c'était avant-hier »*.

**4. Confirmer.** Un récapitulatif montre l'ancienne et la nouvelle valeur. Vous validez.

### 14.3 Exemple

```
Vous : /corriger
Bot  : Décrivez l'événement à corriger (ou tapez 1 pour le dernier)
Vous : 1
Bot  : 📌 Récolte · tomate cerise · 2.0 kg · nord · 17/07/2026
       Que voulez-vous corriger ?
Vous : la quantité c'était 3 kg
Bot  : quantité : 2.0 → 3.0
       [✅ Confirmer] [❌ Annuler]
Vous : ✅ Confirmer
Bot  : ✅ Modification enregistrée.
```

### 14.4 La trace de correction

Chaque correction laisse une **trace horodatée** attachée à l'événement. Rien n'est effacé en silence : vous pouvez toujours savoir ce qui a été modifié, quand, et quelle était la valeur d'origine.

### 14.5 Supprimer

Dites *« supprimer »*, *« effacer »* ou *« annuler »*. Le bot vous propose de corriger ou de supprimer le dernier événement, avec confirmation.

**Réflexe à prendre :** une saisie erronée se corrige mieux qu'elle ne se supprime. Supprimer crée un trou dans votre historique ; corriger le préserve.

---

## 15. Météo et confort

### 15.1 La météo

Chaque matin à 5 h, l'assistant relève automatiquement et silencieusement la météo du jour — températures, précipitations, probabilité de pluie. Vous n'avez rien à faire. Ce relevé alimente l'historique météo consultable dans le tableau de bord.

Pour un relevé manuel immédiat :

```
/meteo
```

### 15.2 Les réponses vocales

L'assistant peut vous répondre à voix haute — pratique quand vous avez les mains dans la terre.

```
/tts        →  état actuel
/tts_on     →  activer
/tts_off    →  désactiver
```

### 15.3 Version installée

```
/version
```

---

## 16. Bonnes pratiques

### ✅ À faire

- **Enregistrez sur le moment**, pas le soir. Une saisie différée est une saisie approximative ou oubliée.
- **Lisez le récapitulatif** avant de confirmer. Trois secondes qui vous économisent une correction.
- **Précisez la variété** systématiquement. C'est ce qui rend les comparaisons entre saisons possibles.
- **Mentionnez la parcelle** au moins à la plantation.
- **Enregistrez les pertes.** Sans elles, tous vos stocks sont faux.
- **Groupez** vos actions d'une même session en une seule dictée multi-lignes.
- **Notez le nombre de graines** au semis : c'est la base de tous vos taux de réussite.

### ❌ À éviter

- Mélanger plusieurs cultures dans une phrase non structurée. Une ligne = une culture.
- Commencer une phrase par un mot de navigation (*corriger*, *stats*, *plan*) si ce n'est pas votre intention.
- Les abréviations peu communes : dites *« courgette »*, pas *« courge »* si vous voulez parler de courgette.
- Vouloir corriger un stock directement. Enregistrez l'événement qui l'a fait bouger.
- Les tirets bas dans les noms de parcelle.

### 🎤 Spécifique au vocal

- Parlez **clairement et posément** — la transcription est bonne, pas magique.
- **Épelez les variétés rares** ou peu courantes.
- Préférez un **environnement calme** : le vent et le moteur de la tondeuse dégradent nettement la transcription.
- Les noms propres de variétés sont le point faible : vérifiez-les au récapitulatif.

---

*Fin de la Partie II. La Partie III décrit écran par écran le tableau de bord web.*
