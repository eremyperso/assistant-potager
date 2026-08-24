**ID :** US-099
**Titre :** Apprendre à l'assistant à expliquer sa propre application
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux pouvoir demander à l'assistant comment fonctionne l'application, avec mes mots
Afin de comprendre ce que je vois sans chercher dans une aide, et sans avoir à demander à quelqu'un

**Contexte fonctionnel :**
Huitième US issue de `docs/ARCHITECTURE_CIBLE_V2_reponses.md` (§4.1, famille B). C'est le **premier
contenu** versé dans le socle de connaissance livré par US-098, et il est délibérément placé avant
l'agronomie : il ne porte aucun risque de licence, son sujet est parfaitement connu de l'équipe, et
il produit un gain immédiat — un assistant qui sait expliquer sa propre application réduit d'autant
les questions sans réponse.

**Correction du cadrage initial, à ne pas manquer.** Le document d'architecture présente cette
famille comme la plus facile parce que « le guide utilisateur existe déjà » et n'aurait qu'à être
ingéré. **Ce fichier n'existe pas dans le dépôt** au moment de la rédaction de cette US : il est
cité par deux documents de conception comme s'il était disponible, mais aucun fichier de ce nom
n'est présent. Le corpus doit donc être **écrit**, ce qui change la nature de l'effort — travail
éditorial, pas travail d'ingestion. La matière première existe en revanche largement : les textes
d'aide du bot (`/help` et son aide contextuelle par mot-clé, livrés en v2.13.0), les US livrées et
les documents de conception.

**Critères d'acceptance :**

*Contenu*
- [ ] CA1 : Un corpus de fiches Markdown versionnées dans le dépôt couvre au minimum : le calcul du stock, la mise en godet, le chaînage semis → godet → plantation, la distinction entre cultures végétatives et reproductrices, la pépinière par lot, les parcelles et le plan d'occupation, la lecture du journal, le cycle de vie d'un potager (création, archivage, suppression), le partage d'un potager entre membres et leurs rôles, l'activation du compagnon Telegram
- [ ] CA2 : Chaque fiche répond à des **questions réellement posables par un jardinier** (« comment est calculé mon stock ? », « pourquoi mes semis n'apparaissent pas en pépinière ? », « à quoi sert l'archivage ? »), et non à une arborescence de fonctionnalités
- [ ] CA3 : Le vocabulaire est celui du jardinier, pas celui du code : aucun nom de table, de fonction, d'écran technique ou de numéro d'US dans le texte servi
- [ ] CA4 : Les fiches distinguent explicitement ce qui **consomme un pied** de ce qui ne le consomme pas — c'est la source d'incompréhension la plus prévisible de l'application, et une réponse fausse à cet endroit fait douter de tout le stock
- [ ] CA5 : Les fragments sont de famille `doc_app`, avec `potager_id` nul (savoir partagé) et niveau de confiance `verifie`
- [ ] CA6 : Aucune donnée personnelle, aucun exemple tiré d'un potager réel n'apparaît dans ces fiches

*Cohérence avec l'aide existante*
- [ ] CA7 : `/help` reste le **sommaire court** et le corpus en est la **forme longue** : les deux ne se dupliquent pas et ne se contredisent pas. Un contrôle automatisé vérifie que chaque domaine listé par `/help` possède au moins une fiche correspondante
- [ ] CA8 : Une question posée en langage naturel sur le fonctionnement de l'application est traitée par l'étage du savoir, **sans appel au modèle**, avec la source citée

*Tenue dans le temps*
- [ ] CA9 : Une évolution fonctionnelle qui rend une fiche fausse impose la mise à jour de la fiche **dans la même livraison**. Ce point entre dans la définition de terminé du projet — sans quoi le corpus deviendra un mensonge documenté en quelques mois
- [ ] CA10 : Le corpus est ingéré par l'outil d'US-098, de façon rejouable, et son ingestion est intégrée au déploiement au même titre qu'une migration

*Mesure*
- [ ] CA11 : Un jeu d'au moins 20 questions de fonctionnement est vérifié : la bonne fiche ressort dans les trois premiers résultats, et la réponse servie est jugée correcte à la relecture
- [ ] CA12 : Les questions de fonctionnement qui ne trouvent aucune fiche sont remontées par la journalisation (US-097 / CA14) et constituent la liste de rédaction de la version suivante

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation | interaction Telegram
- Migration BDD requise : **non** — le socle de tables est livré par US-098 ; cette US n'apporte que du contenu et son ingestion
- **Arbitrage tranché — écrire le corpus plutôt que d'attendre le guide :** on n'attend pas la rédaction d'un guide utilisateur complet pour alimenter le RAG. Les fiches de connaissance **sont** la documentation utilisateur du projet ; un guide linéaire pourra être composé à partir d'elles plus tard, jamais l'inverse
- **Arbitrage tranché — une fiche par question, pas par écran :** le découpage suit les questions des jardiniers, pas la structure de l'application. Un découpage par écran produirait des fragments que personne ne cherche
- **Arbitrage tranché — pas de génération automatique du corpus par un modèle :** les fiches sont écrites et relues. Un corpus généré serait fluide, invérifiable, et transformerait la base de connaissance en source d'erreurs autorisées
- Dépendances : **US-098** (socle, bloquante). Les fiches décrivant des fonctionnalités non livrées (calendrier cultural, rôles avancés) attendent leur livraison plutôt que d'anticiper
- Invariants projet : échappement Markdown dans les sorties du bot ; journalisation structurée conservée

**Notes techniques (pour Persona Developer) :**
- Les fiches vivent dans un répertoire dédié du dépôt (par exemple `docs/connaissance/app/`), un fichier par sujet, avec en-tête portant titre, famille, source et niveau de confiance — l'outil d'ingestion lit ces en-têtes
- Le contrôle du CA7 doit comparer les domaines déclarés par la commande d'aide au corpus ingéré, et échouer en intégration continue si un domaine n'est plus couvert
- Ne pas recopier le texte de `/help` dans les fiches : le sommaire renvoie vers un contenu, il ne le duplique pas
- L'ingestion au déploiement doit être idempotente et sans effet si le contenu n'a pas changé (US-098 / CA10)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: L'assistant explique le calcul du stock
  Given le corpus de fonctionnement ingéré
  When un jardinier demande "comment est calculé mon stock de tomates ?"
  Then la réponse explique la règle avec ses mots
  And elle cite la fiche dont elle est issue
  And aucun appel au modèle n'a lieu

Scénario: Question sur une notion propre au domaine
  Given un jardinier qui ne comprend pas pourquoi ses haricots ne diminuent pas après récolte
  When il demande pourquoi
  Then la réponse explique la différence entre culture végétative et culture reproductrice

Scénario: Sommaire et corpus alignés
  Given la commande d'aide et le corpus ingéré
  When le contrôle de cohérence est exécuté
  Then chaque domaine du sommaire possède au moins une fiche

Scénario: Fiche mise à jour avec la fonctionnalité
  Given une évolution qui modifie le comportement de l'archivage
  When la livraison est préparée
  Then la fiche correspondante est mise à jour dans la même livraison

Scénario: Question sans fiche remontée pour rédaction
  Given une question de fonctionnement qui ne trouve aucun fragment
  When l'administrateur consulte les questions restées sans réponse
  Then cette question figure dans la liste de rédaction
```

**Labels GitHub :** `us`, `sprint-fiabilite-cout`, `rag`, `connaissance`, `documentation`
