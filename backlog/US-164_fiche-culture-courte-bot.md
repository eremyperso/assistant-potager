**ID :** US-164
**Titre :** Restituer une fiche culture courte au bot sur commande, sans aucun jeton
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux demander `/fiche tomate` au bot et recevoir immédiatement l'essentiel sur cette culture
Afin d'avoir la réponse en plein champ, sur mon téléphone, sans attendre et sans consommer de quota

**Contexte fonctionnel :**
Cinquième US de l'`ÉPIC 6`, rang B4 de la piste B
(`docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.4). C'est le **premier gain visible** de tout
l'épic, et le plan de production recommande explicitement de l'intercaler dès qu'US-161 est
livrée, même si la piste A est en cours : après plusieurs semaines de plomberie invisible,
`/fiche tomate` qui répond instantanément est ce qui maintient l'envie de continuer. C'est une
raison de planification, pas une raison technique — elle n'en est pas moins sérieuse.

**La fiche courte est générée, pas rédigée.** Elle assemble par gabarit les attributs d'US-161, la
famille d'US-067, et les relations d'US-162 et US-163 quand elles existent. Conséquence directe :
elle est **toujours cohérente avec la base**, une correction du référentiel s'y propage
instantanément, et il n'y a **aucun texte à maintenir en double**. C'est aussi ce qui la rend
gratuite : zéro jeton, zéro latence de modèle, zéro risque d'invention.

**Arbitrage déjà tranché — sur commande uniquement**
(`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.4) : pas de restitution spontanée après une
saisie, ni en v1 ni en option. L'ordre critique des flux de `handle_text` est l'invariant le plus
fragile du projet et US-092 va déjà le remuer ; ajouter un branchement post-saisie dans le même
trimestre, pour un gain pédagogique marginal, n'est pas un arbitrage raisonnable.

> **⚠️ US amendée le 02/09/2026** — ajoute l'affichage de la **description agronomique**
> (`culture_config.description_agronomique`, champ de texte libre existant depuis US-001,
> indépendant des quatre attributs de conduite d'US-161) dans la fiche courte. CA13 et CA14 sont
> ajoutés ; CA1 à CA12 sont inchangés, y compris ce qui en a déjà été livré. Aucune migration : le
> champ existe déjà en base, seule sa restitution dans la fiche est nouvelle.

**Critères d'acceptance :**

*La commande*
- [ ] CA1 : Une **commande préfixée** restitue la fiche courte d'une culture nommée. Étant préfixée, elle est reconnue au tout premier étage du routage : **zéro jeton, zéro appel réseau, zéro effet de bord**
- [ ] CA2 : La fiche tient en une **dizaine de lignes lisibles sur un téléphone en plein champ**, formatées pour Telegram. La concision n'est pas cosmétique : c'est la contrainte d'usage principale de ce canal
- [ ] CA3 : La fiche est **composée par gabarit** à partir de la donnée du référentiel. Aucun texte de fiche n'est stocké rédigé, et donc aucun texte à resynchroniser quand la donnée change
- [ ] CA4 : ⛔ **Aucune restitution spontanée.** La fiche ne s'affiche jamais d'elle-même après une saisie d'événement. Cette US **n'introduit aucune modification de l'ordre critique** des flux de `handle_text` (modes de correction > mode question > navigation > détection de question > action) ni aucun nouvel état conversationnel

*L'honnêteté de la réponse*
- [ ] CA5 : Une culture **inconnue du référentiel** reçoit une réponse explicite — « je n'ai pas de fiche sur cette culture » — et non une fiche voisine forcée ni une réponse générée. Le corpus de mesure `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` réserve **25 de ses 44 entrées** à ce test d'honnêteté ; c'est un comportement mesuré, pas une intention
- [ ] CA6 : Un attribut **non renseigné est omis ou affiché comme non renseigné**, jamais comblé. Une fiche partielle honnête vaut mieux qu'une fiche complète inventée
- [ ] CA7 : Quand la fiche s'appuie sur une source imposant l'attribution, **la mention est affichée avec la réponse** (US-140 / CA4). Quand elle s'appuie sur une donnée saisie, elle le dit aussi
- [ ] CA8 : Une donnée de niveau `indicatif` est servie **avec sa réserve**, et une association `traditionnelle` avec sa formulation propre (US-163 / CA3). La fiche n'aplatit pas les niveaux de confiance qu'elle a coûté cher à distinguer
- [ ] CA13 *(ajouté 02/09/2026)* : La fiche affiche la **description agronomique** de la culture (`culture_config.description_agronomique`, un champ de texte libre indépendant des quatre attributs de conduite d'US-161) quand elle est renseignée en base. Absente, la fiche l'indique explicitement comme **incomplète** — jamais omise en silence, jamais complétée — même principe d'honnêteté que CA6, appliqué à ce champ

*Coût et périmètre*
- [ ] CA9 : **Aucun appel à un modèle de langage**, dans aucun cas de figure — y compris culture inconnue, y compris fiche vide. Le coût de la commande est journalisé comme nul, conformément à l'invariant projet « impact tokens chiffré pour tout chemin de réponse »
- [ ] CA10 : La commande fonctionne sur les **dix cultures du périmètre initial** ; au-delà, elle applique le CA5 sans dégradation ni erreur. La couverture s'étend au rythme du référentiel, pas de cette US
- [ ] CA11 : La fiche ne contient **ni date, ni fenêtre de semis, ni durée** tant qu'US-068 n'a pas livré le référentiel calendrier. Elle ne les invente pas et n'en emprunte pas à une fiche narrative

*Tests*
- [ ] CA12 : Des tests couvrent une fiche complète, une fiche partielle, une culture inconnue, une culture au nom accentué ou en majuscules (la normalisation est celle déjà appliquée aux noms de culture), l'absence totale d'appel au modèle, et la **non-régression du routage** — les flux de correction, le mode question et la saisie d'action se comportent exactement comme avant
- [ ] CA14 *(ajouté 02/09/2026)* : Des tests couvrent l'affichage de la description agronomique quand elle est renseignée et sa mention **incomplète** quand elle ne l'est pas (CA13)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram | consultation
- Migration BDD requise : **non** — cette US lit, elle n'écrit pas
- Dépendances : **US-161** (les attributs à afficher, bloquante), **US-067 amendée** (la famille). **US-162** et **US-163** l'enrichissent quand elles sont livrées, sans la bloquer : la fiche affiche ce qui existe
- **Arbitrage tranché — commande uniquement, pas de spontané** (§2.4) : 🔶 réouvrable plus tard, en opt-in explicite, une fois la cascade d'US-092 stabilisée. À rattacher alors à cette US, pas à une US nouvelle
- **Arbitrage tranché — générée, pas rédigée :** une fiche rédigée serait à maintenir en double et divergerait de la base à la première correction. Le gabarit garantit la cohérence par construction
- Voisinage : la **fiche détaillée** (fiche courte + narratif + calendrier recalé) est la vue « Cultures » du Lot E PWA (`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.3). Elle n'est pas dans cette US, mais elle consommera le même gabarit et la même donnée — aucun second mécanisme

**Notes techniques (pour Persona Developer) :**
- ⚠️ **Le risque principal de cette US n'est pas la fiche, c'est le routage.** Toute modification de `handle_text` au-delà de l'ajout d'une commande préfixée est hors périmètre. Les tests de non-régression du CA12 sont le vrai livrable de qualité
- La normalisation du nom de culture est celle déjà en place ailleurs — minuscules, sans accents, sans espaces ni tirets
- La commande étant préfixée, elle échappe par construction à la détection d'intention et n'ajoute aucun risque de faux positif dans le flux vocal

**Estimation :** 5 points *(inchangée après l'amendement du 02/09/2026 — réutilise le gabarit déjà en place, aucune migration)*

**Scénario Gherkin :**
```gherkin
Scénario: Fiche complète en zéro jeton
  Given une culture "tomate" dont la famille et les attributs agronomiques sont renseignés
  When le jardinier demande sa fiche au bot
  Then il reçoit une fiche courte lisible sur téléphone
  And aucun appel à un modèle de langage n'a eu lieu

Scénario: Fiche partielle
  Given une culture "blette" dont seuls la famille et le besoin en eau sont renseignés
  When le jardinier demande sa fiche
  Then la fiche restitue ce qui est connu
  And les attributs absents se lisent comme non renseignés

Scénario: Culture inconnue du référentiel
  Given une culture "artichaut" sans fiche au périmètre initial
  When le jardinier demande sa fiche
  Then l'application répond qu'elle n'a pas de fiche sur cette culture
  And elle ne propose pas la fiche d'une culture voisine

Scénario: Aucune restitution spontanée
  Given un jardinier qui enregistre une plantation de tomates
  When l'événement est confirmé
  Then aucune fiche culture ne lui est présentée

Scénario: Nom accentué ou en majuscules
  Given une culture enregistrée sous le nom "céleri"
  When le jardinier demande la fiche de "CELERI"
  Then la fiche du céleri lui est restituée

Scénario: Niveau de confiance conservé
  Given une culture dont une information est de niveau "indicatif"
  When sa fiche est restituée
  Then l'information est servie avec sa réserve explicite

Scénario: Aucune régression du routage
  Given un jardinier en cours de correction d'un événement
  When il poursuit sa correction
  Then le flux de correction se comporte exactement comme avant cette évolution

Scénario: Description agronomique renseignée
  Given une culture "tomate" dont la description agronomique est renseignée en base
  When le jardinier demande sa fiche
  Then la fiche affiche cette description agronomique

Scénario: Description agronomique absente
  Given une culture "poivron" dont la description agronomique n'est pas renseignée en base
  When le jardinier demande sa fiche
  Then la fiche indique que la description agronomique est incomplète
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `bot`, `cultures`, `referentiel`
