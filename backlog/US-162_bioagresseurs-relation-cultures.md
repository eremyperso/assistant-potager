**ID :** US-162
**Titre :** Modéliser les bioagresseurs et leur relation aux cultures
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que l'application sache ce qui attaque chacune de mes cultures
Afin qu'elle me réponde en une seconde et sans se tromper quand je demande à quoi je dois m'attendre sur mes poireaux, au lieu de me servir des généralités

**Contexte fonctionnel :**
Troisième US de l'`ÉPIC 6` (`docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §4.1),
positionnée en vague 3 par `docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.5.

L'application enregistre aujourd'hui « mildiou » dans un commentaire **sans savoir ce qu'est le
mildiou**, ni qu'il touche aussi les pommes de terre de la parcelle d'à côté, ni qu'il est favorisé
par la pluviométrie qu'elle affiche déjà sur son propre tableau de bord. Cette US crée le chaînon
manquant : une identité pour chaque bioagresseur, et une **arête** entre lui et les cultures qu'il
attaque.

C'est une US de **structure et d'import**, pas de rédaction. Le texte explicatif — description,
symptômes, conduite à tenir — reste porté par le corpus narratif d'US-140 et le socle d'US-098.
Ici on livre ce qui se joint et se calcule : « qu'est-ce qui attaque le poireau » doit se résoudre
par une requête, à zéro jeton, et non par une recherche de similarité.

**La source est déjà tranchée** (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1, option A) :
**E-Phy / ANSES** sous Licence Ouverte est la pépite de cet épic — seule source officielle,
française, réutilisable commercialement, qui donne à la fois le lien *culture × cible* et le cadre
légal du traitement. **Ephytia (INRAE)**, meilleur contenu francophone sur le sujet, reste une
source de **lecture** pour la rédaction humaine et **jamais** une source d'import : aucune licence
ouverte n'y est affichée.

**Critères d'acceptance :**

*Le modèle*
- [ ] CA1 : Un bioagresseur possède une **identité propre** : nom commun français, nom scientifique, catégorie (`champignon`, `insecte`, `bacterie`, `virus`, `abiotique`, `carence`) et, quand il existe, son **code EPPO** — la seule clé de rapprochement fiable entre sources
- [ ] CA2 : La relation **culture × bioagresseur** est une table de liaison, jamais un texte. Elle porte la **fréquence** (`courant` / `occasionnel` / `rare`) et, si connue, la période de risque. C'est cette table qui rend la question « qu'est-ce qui attaque mes poireaux » résoluble à zéro jeton
- [ ] CA3 : Le pattern d'isolation du projet est réappliqué tel quel : `potager_id` nul signifie **connaissance partagée**. Un potager peut ajouter *son* bioagresseur local sans polluer les autres, et cet ajout local n'est jamais promu au partagé automatiquement
- [ ] CA4 : Chaque enregistrement porte **sa source, sa licence et son attribution**, rattachées au référentiel de traçabilité d'US-166 — obligation juridique par enregistrement, pas ligne de README

*L'import et son honnêteté*
- [ ] CA5 : L'import est **hors ligne, idempotent et rejouable**. Aucune API externe n'est appelée pendant qu'un jardinier attend une réponse : ni pour la latence, ni pour la disponibilité, ni pour le réseau — c'est la décision actée du §5.1 de la conception
- [ ] CA6 : Seules les sources du socle tranché sont ingérées : **E-Phy / ANSES** (Licence Ouverte) et **Wikidata** (CC0). Toute source CC-BY-SA est refusée à l'ingestion, sans dérogation ni « en attendant ». Ephytia reste hors import
- [ ] CA7 : 🔶 **Les conditions d'utilisation de `data.eppo.int` sont lues et consignées avant tout import de masse.** Si elles interdisent la reprise en base, les codes EPPO sont saisis à la main sur le périmètre des dix cultures — travail borné — plutôt qu'importés. Ce point est un **préalable bloquant** de l'US, pas une note de bas de page
- [ ] CA8 : Le **taux d'appariement** entre les libellés de la source et les cultures réellement présentes en base est **mesuré et publié** par l'import. En dessous d'environ 70 %, l'import automatique perd son intérêt face à la saisie directe et la table de correspondance manuelle sur les dix cultures du périmètre devient le mode nominal. La décision se prend sur la mesure, pas sur l'intention
- [ ] CA9 : Un rapprochement obtenu par **nom vernaculaire** seul — la clé la moins fiable — n'est jamais appliqué sans **revue humaine**. Les cas connus le montrent : `laitue` et `salade`, `haricot` et `haricot grimpant` coexistent en base et désignent vraisemblablement la même chose, tandis que les cucurbitacées se répartissent sur **dix libellés distincts**

*Ce que cette US ne dit pas*
- [ ] CA10 : **Aucun dosage, aucune recommandation d'emploi d'un produit phytosanitaire.** L'application peut indiquer qu'un traitement est *légalement utilisable en jardin amateur* — l'information est dans E-Phy — et renvoie alors à la source officielle. Elle ne prescrit rien. C'est le CA10 d'US-140, réaffirmé ici parce que c'est ici que la donnée entre
- [ ] CA11 : Aucun **texte narratif** n'est produit par cette US. Les descriptions et symptômes rédigés relèvent d'US-140 et sont ingérés par US-098 ; cette US livre les identités et les arêtes sur lesquelles ce texte viendra se rattacher
- [ ] CA12 : Un bioagresseur sans relation connue à une culture du périmètre **reste en base et se lit comme non rattaché**. L'absence de lien n'est jamais présentée comme une absence de risque

*Mesure et tests*
- [ ] CA13 : Des tests couvrent l'import idempotent rejoué deux fois sans doublon, le refus d'une source hors socle, l'isolation d'un bioagresseur local à son potager, la restitution de la liste des bioagresseurs d'une culture **sans aucun appel au modèle**, et le cas d'une culture du périmètre sans bioagresseur rattaché

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation
- Migration BDD requise : **oui** — tables `bioagresseur` et relation culture × bioagresseur, avec leur rattachement à la source. Idempotente, rollback documenté
- Dépendances : **US-166** (traçabilité des sources et outil d'import, bloquante) et **US-067 amendée** (le pivot de culture). ⚠️ La **structure** ne dépend d'aucune US du moteur V2 ; seule l'**exploitation narrative** attend US-098. Prérequis de **US-165**, qui sans la relation culture × bioagresseur n'a rien à classer
- **Arbitrage tranché — structure d'abord, texte ensuite :** livrer les tables sans le narratif produit déjà un service complet (« qu'est-ce qui attaque le poireau »), à zéro jeton, testable et mesurable. L'inverse — le texte sans les arêtes — ne produit rien de joignable et remonte tout à l'étage LLM
- **Arbitrage tranché — E-Phy oui, Ephytia non :** le meilleur contenu francophone du domaine n'affiche aucune licence ouverte. Le tentation de « juste s'en inspirer un peu » à l'import est exactement ce que le CA6 interdit. Il reste lisible par un humain qui rédige, ce qui est licite et suffisant
- Risque 🟡 identifié en conception §10 : **l'appariement des sources**. Les libellés d'usage E-Phy sont structurés *culture × type de traitement × cible* et ne semblent pas porter de code EPPO. Le CA8 en fait une mesure et non une supposition, et le repli manuel est chiffré : ~30 cultures suivies, dix au périmètre initial

**Notes techniques (pour Persona Developer) :**
- Le rapport d'appariement du CA8 est un livrable de l'US au même titre que les tables : c'est lui qui décide si l'import automatique est conservé ou remplacé par la correspondance manuelle
- Les fichiers E-Phy sont mis à jour chaque semaine ; l'import doit pouvoir être rejoué sans dédoublonner à la main, d'où l'exigence d'idempotence du CA5
- ⚠️ Rappel de mesure : la production porte **96 bulletins `[AUTO-METEO]` sur 321 événements**. Toute requête qui parcourt l'historique pour évaluer une couverture doit les exclure explicitement, faute de quoi près d'un tiers du corpus analysé est du bruit machine

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Ce qui attaque une culture, sans jeton
  Given une culture "poireau" reliée à plusieurs bioagresseurs avec leur fréquence
  When le jardinier demande ce qui attaque ses poireaux
  Then la liste est restituée, ordonnée par fréquence
  And aucun appel à un modèle de langage n'a lieu

Scénario: Import rejoué
  Given un import de bioagresseurs déjà réalisé
  When le script d'import est rejoué sur une source mise à jour
  Then aucun doublon n'est créé
  And les nouvelles entrées sont ajoutées

Scénario: Source hors socle refusée
  Given un jeu de données sous licence CC-BY-SA
  When son import est tenté
  Then il est refusé
  And aucun bioagresseur n'est créé

Scénario: Bioagresseur local à un potager
  Given un bioagresseur ajouté pour le potager "Jardin de Vitry"
  When un jardinier d'un autre potager consulte les bioagresseurs de la même culture
  Then le bioagresseur local ne lui est pas restitué

Scénario: Culture sans bioagresseur rattaché
  Given une culture du périmètre pour laquelle aucune relation n'est connue
  When le jardinier demande ce qui l'attaque
  Then l'application répond qu'elle n'a pas d'information pour cette culture
  And elle n'en conclut pas que la culture n'est pas exposée

Scénario: Aucune prescription de traitement
  Given un bioagresseur pour lequel E-Phy référence des produits utilisables en jardin amateur
  When l'information est restituée au jardinier
  Then aucun dosage ni recommandation d'emploi n'est donné
  And la source officielle est citée
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `referentiel`, `agronomie`
