**ID :** US-172  
**Titre :** Piloter par une phrase toutes les commandes du bot  
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier
Je veux dire « crée la parcelle PlancheTomate », « la serre est une pépinière », « montre-moi le bilan des tomates », « passe sur le potager de la maison » — et que ce soit fait
Afin de piloter l'application entière avec mes mots, sans avoir à retenir la syntaxe exacte d'une commande, l'ordre de ses arguments ni le vocabulaire attendu pour ses valeurs

**Contexte fonctionnel :**

Le compagnon de terrain sait interpréter **un geste de jardin** dicté en langage naturel — les dix-huit
gestes du référentiel d'actions — et **rien d'autre**. Tout le reste, soit **vingt-trois commandes** et
leurs sous-commandes, n'est atteignable que d'une seule façon : taper la commande exacte, avec ses
arguments dans le bon ordre et, pour plusieurs d'entre elles, avec le vocabulaire fermé attendu
(`/culture exposition courgette plein soleil`, `/association saisir carotte aneth defavorable etabli
concurrence racinaire`). US-171 a rendu ces commandes **visibles** dans le menu natif ; elle ne les a pas
rendues **dictables** — un clic dans le menu dépose `/parcelle` dans la zone de saisie et laisse le
jardinier compléter à la main.

Le décalage est ressenti comme une incohérence, et il est réel :

* « récolté 2 kg de tomates » → compris, enregistré ;
* « crée la parcelle PlancheTomate » → au mieux une **explication** tirée du socle de connaissance
  (US-099), au pire rien.

Répondre « voici comment supprimer une parcelle » à quelqu'un qui vient de demander qu'on la supprime est
la forme la plus agaçante de la non-réponse : l'assistant a compris l'intention, il a la commande sous la
main, et il renvoie une notice.

Même la saisie d'un geste n'est que **partiellement** traitée pour cette raison : une plantation ou une
récolte citant une parcelle qui n'existe pas encore s'arrête au flux de désambiguïsation, faute de pouvoir
créer la parcelle dans la foulée. Le jardinier quitte alors sa phrase, tape une commande de création,
puis redicte son geste.

Cette US livre à l'étage 0 de la cascade (`docs/ARCHITECTURE_CIBLE_V2_reponses.md` §2.1 et §3.1) ce qu'il
annonçait sans le fournir : **un interpréteur de commandes**. Le routeur d'US-093 distingue une action
d'une question ; il doit désormais distinguer, à l'intérieur des actions, **le geste au jardin** (qui
produit un événement) de **la commande de gestion** (qui pilote l'application). US-094 a traité le versant
saisie ; celui-ci en est le symétrique.

**Périmètre : la totalité des commandes enregistrées.** Pas un échantillon, pas les seules parcelles. Le
tableau ci-dessous en fait l'inventaire, décision par décision, et le CA7 arme le test qui empêche l'écart
de se recreuser à la prochaine commande ajoutée.

**Critères d'acceptance :**

*Reconnaissance de l'intention de commande*
- [ ] CA1 : Une phrase exprimant la volonté d'agir sur l'application est classée par le routeur comme **commande**, distincte du geste au jardin et des questions — à l'impératif (« supprime la parcelle nord »), à l'intention (« je veux créer la parcelle PlancheTomate »), ou elliptique (« bilan des tomates », « plan du potager », « voix off »)
- [ ] CA2 : **Vouloir faire n'est pas demander comment faire.** « Comment supprimer une parcelle ? » reste une question de savoir servie par le socle de connaissance ; « supprime la parcelle nord » exécute. Les deux formes sont couvertes par le corpus du CA14 et testées en regard l'une de l'autre — c'est la confusion la plus probable de cette US
- [ ] CA3 : La reconnaissance est **déterministe d'abord** : les formes fréquentes sont reconnues par règles, sans aucun appel au modèle ni consommation de jeton, dans le même esprit qu'US-094
- [ ] CA4 : Le modèle n'intervient qu'en repli, et **sous contrainte fermée** : il choisit une commande dans le catalogue existant et en extrait les arguments. Il ne peut ni inventer une commande absente du catalogue, ni inventer un argument absent de la phrase, ni produire une valeur hors du vocabulaire déclaré. Une sortie non conforme est rejetée et traitée comme non comprise
- [ ] CA5 : La dictée vocale ne change rien : l'interpréteur s'applique au texte transcrit comme au texte tapé

*Le catalogue des commandes est dérivé, jamais recopié*
- [ ] CA6 : L'interpréteur s'appuie sur **le catalogue déjà dérivé des commandes réellement enregistrées** (le mécanisme d'US-171), enrichi de ce qui lui manque : pour chaque commande et sous-commande, la **forme attendue de ses arguments** (nom libre, nombre, unité, date, culture, parcelle, ou vocabulaire fermé et ses valeurs). Il n'existe pas de seconde liste de commandes tenue à la main
- [ ] CA7 : **Parité commandes ↔ interpréteur, vérifiée par un test.** Toute commande enregistrée par le bot est soit dictable, soit inscrite dans une liste d'exclusion explicite et motivée, écrite au même endroit que le catalogue. Un test d'intégration continue échoue si une commande n'est ni couverte ni exclue, ou si une commande dictable ne déclare pas la forme de ses arguments. C'est ce test, et non la vigilance, qui empêche l'écart constaté aujourd'hui de se recreuser
- [ ] CA8 : La liste d'exclusion de l'interpréteur est **distincte de celle du menu natif**, parce que les critères diffèrent : le menu écarte ce qui coûte deux gestes au clic, l'interpréteur écarte ce qu'une phrase ne peut pas porter. `/tts`, écartée du menu, est ainsi parfaitement dictable — « est-ce que la lecture vocale est active ? » appelle exactement sa réponse
- [ ] CA9 : Une commande dictée produit **exactement** le même effet que la même commande tapée : même service appelé, mêmes contrôles, mêmes messages, même clavier contextuel. L'interpréteur traduit une phrase en commande, il ne réimplémente aucun comportement

*Rien ne s'exécute à l'aveugle*
- [ ] CA10 : Toute commande interprétée est **confirmée avant exécution**, en réutilisant le flux de validation existant (US-021). Le récapitulatif énonce ce qui va être fait en clair **et** rappelle la commande équivalente — le jardinier apprend la syntaxe sans avoir eu à l'apprendre
- [ ] CA11 : **Une valeur dictée est relue avant d'être écrite.** Pour toute commande qui écrit une valeur (superficie, profondeur, rusticité, délai de retour, quantité vendue, exposition, besoin en eau, type d'association), le récapitulatif restitue la valeur **et son unité**, et tout nombre est restitué en chiffres **et** en toutes lettres. C'est précisément là que la transcription vocale échoue — « profondeur 1 » et « profondeur 10 » ne s'entendent pas, et la seconde écrit une donnée fausse dans un référentiel partagé
- [ ] CA12 : **Le doute ne fait jamais agir.** Une phrase ambiguë ou plusieurs commandes candidates conduisent à une demande de précision proposant les candidats, jamais à l'exécution de la plus probable. Une commande destructrice n'est **jamais** exécutée sur un rapprochement approximatif de nom : si la parcelle ou la culture nommée n'existe pas exactement (à la normalisation habituelle près : casse, accents, espaces, tirets), le nom voisin est **proposé**, jamais substitué
- [ ] CA13 : **Un argument manquant se complète, il n'échoue pas.** Une phrase incomplète (« je veux vendre des plants », « note une association entre la carotte et l'aneth ») enchaîne sur une complétion guidée des arguments manquants, réutilisant les parcours de saisie guidée existants, plutôt que de renvoyer un message d'usage. Une valeur d'un vocabulaire fermé y est proposée en boutons — jamais devinée à partir d'un synonyme approchant
- [ ] CA14 : Les droits sont ceux de la commande tapée : une commande dictée traverse les mêmes contrôles de rôle (US-047) et le même garde de liaison, et un membre sans le droit correspondant reçoit le même refus qu'en la tapant. L'interpréteur n'ouvre aucun chemin d'accès parallèle

*Mesure — la couverture ne se suppose pas*
- [ ] CA15 : Un **corpus de commandes** versionné dans les tests couvre **chaque commande et chaque sous-commande dictable** avec au moins trois formulations naturelles distinctes — une à l'impératif, une à l'intention, une elliptique. Il contient aussi, pour chacune, la question de savoir voisine du CA2, et des phrases hors périmètre à ne pas capter
- [ ] CA16 : Seuil d'acceptation : **≥ 90 % de commandes correctement identifiées** sur ce corpus, et **0 exécution destructrice erronée** — ce second chiffre n'est pas un objectif mais un couperet. Une suppression exécutée sur la mauvaise parcelle coûte davantage que cent phrases non comprises
- [ ] CA17 : La part des commandes traitées **sans appel au modèle** est mesurée et publiée à la livraison, comme l'a été celle du parseur déterministe

*Traçabilité*
- [ ] CA18 : Chaque interprétation est journalisée avec la nature détectée, la commande et la sous-commande retenues, l'origine de la décision (règle ou modèle), la confiance, la latence et l'issue (confirmée, refusée par le jardinier, abandonnée faute de précision) — matière première d'US-097, et seule façon de savoir quelles formulations enrichir ensuite

*Chaînage avec la saisie d'un geste*
- [ ] CA19 : Un geste citant une parcelle inconnue propose sa **création en un geste**, puis enregistre le geste dicté sans faire retaper la phrase : « j'ai planté 3 pieds de tomate sur PlancheTomate » → « La parcelle PlancheTomate n'existe pas. La créer et enregistrer la plantation ? ». Refuser laisse le flux de désambiguïsation actuel se dérouler à l'identique
- [ ] CA20 : Aucune parcelle, aucune culture n'est créée sans cette confirmation explicite. La règle d'US-094 (« une culture ou une parcelle inconnue n'est jamais créée à l'aveugle ») n'est pas assouplie : elle est **outillée**

*Non-régression*
- [ ] CA21 : L'ordre critique des flux de conversation est préservé : modes de correction, mode `ask`, navigation, puis routage. Une phrase envoyée pendant une correction ou une saisie guidée en cours reste traitée par le flux en cours
- [ ] CA22 : Les commandes tapées, les claviers contextuels de validation et le menu natif d'US-171 sont inchangés. Cette US **ajoute** un chemin d'entrée, elle n'en modifie aucun

**Notes fonctionnelles :**

- Zone fonctionnelle concernée : interaction Telegram | enregistrement | consultation
- Migration BDD requise : **non** — aucune table nouvelle. L'interprétation se journalise dans les colonnes d'observabilité de routage déjà en place ; si l'une manque, elle suit l'invariant projet (migration séparée et idempotente, rollback documenté)

*Inventaire — les 23 commandes enregistrées, décision par décision*

Relevé sur les commandes réellement enregistrées par le bot, sous-commandes comprises. C'est cet
inventaire que le test du CA7 rejoue automatiquement ; le tableau en est la trace de décision, pas la
source.

| Commande | Sous-commande / arguments | Dictable | Exemple de phrase, ou motif d'exclusion |
|---|---|:---:|---|
| `/parcelle` | `ajouter <nom> [exposition] [superficie]` | ✅ | « crée la parcelle PlancheTomate, plein sud, 12 m² » |
| `/parcelle` | `renommer <ancien> <nouveau>` | ✅ | « renomme planche nord en planche des courges » |
| `/parcelle` | `supprimer <nom>` | ✅ | « supprime la parcelle PlancheTomate » |
| `/parcelle` | `modifier <nom> exposition= superficie= pepiniere=` | ✅ | « la serre est une pépinière », « la planche sud fait 8,5 m² » |
| `/parcelle` | `lister` | ✅ | « liste mes parcelles » |
| `/parcelles` | (alias de `parcelle lister`) | ✅ | même cible canonique que ci-dessus |
| `/plan` | `[parcelle\|date]` | ✅ | « montre-moi le plan », « le plan au 1er mai » |
| `/stats` | `[culture] [date]` | ✅ | « bilan de la saison », « stats des tomates » |
| `/historique` | — | ✅ | « qu'est-ce que j'ai fait dernièrement ? » |
| `/meteo` | — | ✅ | « quel temps fait-il ? » |
| `/fiche` | `<culture>` | ✅ | « fiche de la tomate » |
| `/rotation` | `<parcelle> <culture>` | ✅ | « je peux planter des poivrons sur la nord ? » |
| `/association` | `lister <culture>` | ✅ | « avec quoi associer la carotte ? » |
| `/association` | `saisir <A> <B> <type> <niveau> <motif>` | ✅ | vocabulaire fermé proposé en boutons (CA13) ; motif dicté tel quel |
| `/culture` | `attributs <culture>` | ✅ | « les attributs de la carotte » |
| `/culture` | `famille <culture> <famille>` | ✅ | « le pâtisson est une cucurbitacée » |
| `/culture` | `delai_retour <famille> <années>` | ✅ | « délai de retour des solanacées : 4 ans » — valeur relue (CA11) |
| `/culture` | `exposition\|eau\|profondeur\|rusticite` | ✅ | « la courgette veut du plein soleil » — valeur relue (CA11) |
| `/potager` | — (choix par boutons) | ✅ | « passe sur le potager de la maison » |
| `/note` | (parcours guidé) | ✅ | « je veux noter une observation » |
| `/corriger` | (parcours guidé) | ✅ | « je me suis trompé sur ma dernière saisie » — **ouvre** le parcours, ne corrige pas seul |
| `/vendre` | `[culture] [variété] [quantité]` | ✅ | « je veux vendre des plants » ; avec quantité, c'est un geste (voir arbitrage) |
| `/tts_on` / `/tts_off` | — | ✅ | « lis-moi les réponses », « coupe la voix » |
| `/tts` | — | ✅ | « est-ce que la lecture vocale est active ? » — dictable bien qu'écartée du menu (CA8) |
| `/help` | `[domaine]` | ✅ | « aide », « aide sur les parcelles » |
| `/ask` | `<question>` | ❌ | Son équivalent naturel **est la question elle-même** : une question dictée est déjà aiguillée par le routeur. En faire une commande créerait deux entrées vers le même chemin |
| `/start` | `[code]` | ❌ | Point d'entrée du protocole Telegram (bouton Démarrer), pas une phrase |
| `/lier` | `<code>` | ❌ | Le code de liaison est une chaîne à coller, pas à dicter : la transcription vocale d'un code est fausse par construction |
| `/delier` | — | ❌ | Action rare et destructive **sur l'identité**. La rendre atteignable à une phrase mal transcrite serait un mauvais service — même raisonnement que son exclusion du menu (US-171) |
| `/version` | — | ❌ | Diagnostic sans usage quotidien pour le jardinier |

**Les cinq commandes exclues restent pleinement fonctionnelles à la saisie manuelle.** Les exclure de
l'interpréteur ne les retire pas du bot, exactement comme les exclure du menu ne les en retirait pas.

*Arbitrages tranchés*

- **La vente de plants avec quantité reste un geste, pas une commande.** « J'ai vendu 6 plants de tomate »
  est déjà l'un des dix-huit gestes du référentiel et le restera : il produit un événement. `/vendre`
  dictable ne couvre que la forme sans quantité, qui ouvre le parcours guidé. Deux chemins vers la même
  écriture seraient une divergence en germe.
- **« Corriger » ouvre le parcours, ne corrige jamais seul.** Une phrase de correction dictée entre dans le
  parcours existant, elle ne cible ni ne modifie un événement directement. La correction porte sur des
  données déjà validées une fois : elle mérite le même soin que leur saisie.
- **Les gestes lourds sur le potager restent hors interpréteur, parce qu'ils ne sont pas des commandes du
  bot :** suppression définitive d'un potager, archivage, transfert de propriété, invitation ou retrait
  d'un membre se font depuis l'application web. Cette US ne leur ouvre pas une porte au bot ; elle
  n'ajoute aucune capacité, elle rend dictable ce qui existe déjà.
- **Pas de commandes enchaînées dans une même phrase.** « Crée la parcelle nord et plante-y 6 tomates »
  est hors périmètre : une commande par message. Enchaîner suppose de gérer l'échec du second ordre après
  exécution du premier — une US à part entière.
- **L'interpréteur ne devient pas un agent :** il traduit une phrase en **une** commande du catalogue et
  s'arrête là. Aucune planification, aucune boucle d'outils, aucune décision d'enchaînement autonome.
- **Livraison en deux lots, sans détourner la liste d'exclusion.** Lot 1 : le mécanisme, la consultation
  et les parcelles. Lot 2 : cultures, associations, potager, parcours guidés, confort. Le test de parité
  du CA7 est armé à la fin du lot 2 — la liste d'exclusion motive des décisions définitives, elle
  n'héberge jamais un « pas encore fait ».

*Dépendances*

- **US-171** (menu natif) — bloquante : elle a livré le catalogue dérivé dont celui-ci hérite (CA6)
- **US-093** (routeur) — la nature `commande` s'y ajoute ; l'US ne crée pas de second aiguillage
- **US-094** (parseur déterministe) — même doctrine, même exigence de précision ; la résolution des dates et la normalisation des noms sont celles déjà en place, sans seconde règle
- **US-021** (confirmation) et **US-049** (validation centrale) — réutilisées telles quelles
- **US-033 / US-038** (saisies guidées) — réutilisées pour la complétion d'arguments (CA13)
- **US-047** (rôles et permissions) — CA14
- **US-098 / US-099** (socle de connaissance, corpus de fonctionnement) — l'étage qui répond aux « comment fait-on ? » du CA2. Les fiches `doc_app` décrivant une procédure mentionneront qu'elle est aussi dictable, dans la même livraison
- **US-097** (observabilité) — consomme la journalisation du CA18

*Invariants projet*

Échappement Markdown dans toute nouvelle sortie du bot ; prompts en `.replace()` jamais `.format()` ;
journalisation structurée conservée ; normalisation des noms de parcelle et de culture réutilisée telle
quelle — aucune seconde règle de normalisation dans le projet.

**Notes techniques (pour Persona Developer) :**

- Le catalogue enrichi (formes d'arguments, vocabulaires fermés, exclusions de l'interpréteur) se déclare
  **à côté** du catalogue de menu d'US-171 — `app/services/menu_commandes.py` —, pas dans un module
  parallèle qui divergerait au premier ajout de commande. Les deux listes d'exclusion y cohabitent,
  distinctes et chacune motivée en commentaire (CA8)
- Le test de parité du CA7 se construit comme le contrôle de cohérence `/help` ↔ corpus déjà en place
  (`tools/controler_aide_corpus.py`) : il compare deux ensembles dérivés de l'introspection, il ne relit
  jamais une liste écrite à la main
- Les vocabulaires fermés (`plein soleil|mi-ombre|ombre`, `faible|moyen|élevé`,
  `favorable|defavorable|neutre`, `etabli|traditionnel`) sont déjà validés au point d'écriture des
  services concernés : l'interpréteur s'y adosse, il ne les recopie pas
- Le corpus du CA15 est un fichier versionné qui tourne en intégration continue, sur le modèle des corpus
  de routage (US-093) et de fonctionnement (US-099) — pas un tableur
- L'interpréteur s'insère **après** les gardes de flux de conversation et **avant** le parsing de geste :
  une phrase reconnue comme commande n'atteint jamais le parseur d'événement
- Le CA19 est le seul point où deux flux se rejoignent : prévoir dès la conception que la phrase d'origine
  est conservée pour être rejouée après création de la parcelle, plutôt que reconstruite

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Créer une parcelle en la dictant
  Given un jardinier dont le potager ne contient pas de parcelle "PlancheTomate"
  When il dicte "je veux créer la parcelle PlancheTomate"
  Then le bot lui propose de créer la parcelle et rappelle la commande équivalente
  And après validation la parcelle existe et apparaît au plan d'occupation
  And aucun appel au modèle n'a été nécessaire

Scénario: Supprimer une parcelle demande une confirmation explicite
  Given une parcelle "PlancheTomate" portant des gestes enregistrés
  When le jardinier dicte "supprime la parcelle PlancheTomate"
  Then le bot énonce ce qui va être fait, y compris le devenir des gestes rattachés
  And rien n'est supprimé tant qu'il n'a pas validé
  When il refuse
  Then la parcelle est intacte et le refus est journalisé

Scénario: Demander comment faire n'exécute rien
  Given un jardinier qui demande "comment supprimer une parcelle ?"
  When le message est traité
  Then il reçoit l'explication issue du socle de connaissance
  And aucune commande n'est exécutée ni proposée à la validation

Scénario: Déclarer une pépinière sans connaître la syntaxe clé=valeur
  Given une parcelle "serre" existante
  When le jardinier dicte "la serre est une pépinière"
  Then le bot propose la modification correspondante et rappelle la commande équivalente
  And après validation les semis qui s'y rattachent sont comptés comme semis à couvert

Scénario: Une valeur chiffrée dictée est relue avant écriture
  Given un jardinier qui dicte "la profondeur de semis de la carotte est de 1 centimètre"
  When le bot lui présente la modification
  Then la valeur est restituée en chiffres et en toutes lettres avec son unité
  And rien n'est écrit au référentiel tant qu'il n'a pas validé

Scénario: Un argument manquant se complète au lieu d'échouer
  Given un jardinier qui dicte "je veux noter une association entre la carotte et l'aneth"
  When l'interpréteur constate qu'il manque le type et le niveau de preuve
  Then les valeurs possibles lui sont proposées en boutons
  And aucune valeur n'est devinée à partir d'un synonyme approchant

Scénario: Un nom approchant n'est jamais supprimé à la place d'un autre
  Given un potager contenant la parcelle "Planche Nord"
  When le jardinier dicte "supprime la parcelle planche nord-est"
  Then aucune suppression n'est exécutée
  And le bot propose "Planche Nord" comme candidat à confirmer

Scénario: Les droits sont ceux de la commande tapée
  Given un membre ayant un rôle de lecture seule
  When il dicte "renomme la parcelle nord en parcelle des courges"
  Then il reçoit le même refus que s'il avait tapé la commande
  And aucune modification n'est enregistrée

Scénario: Changer de potager actif à la voix
  Given un jardinier membre de deux potagers
  When il dicte "passe sur le potager de la maison"
  Then le bot lui propose de changer de potager actif
  And après validation les commandes suivantes portent sur ce potager

Scénario: Créer la parcelle manquante dans la foulée du geste
  Given un jardinier dont le potager ne contient pas de parcelle "PlancheTomate"
  When il dicte "j'ai planté 3 pieds de tomate sur PlancheTomate"
  Then le bot propose de créer la parcelle et d'enregistrer la plantation
  And après validation la parcelle existe et le geste y est rattaché
  And il n'a pas eu à redicter sa phrase

Scénario: Une commande exclue de l'interpréteur reste utilisable à la main
  Given un jardinier qui dicte "délie mon compte"
  When le message est traité
  Then aucune dissociation n'est engagée
  And le bot lui indique le chemin délibéré pour le faire
  When il tape /delier
  Then la commande se déroule comme avant cette US

Scénario: Une commande nouvellement ajoutée au bot n'échappe pas au contrôle
  Given une commande ajoutée au bot et enregistrée comme les autres
  When l'intégration continue s'exécute
  Then le test de parité échoue tant qu'elle n'est ni dictable ni explicitement exclue
  And il échoue aussi si elle est dictable sans déclarer la forme de ses arguments

Scénario: L'ordre des flux de conversation est préservé
  Given un jardinier en cours de correction d'un événement
  When il envoie un message qui ressemble à une commande
  Then le mode correction reste prioritaire
  And l'interpréteur n'intercepte pas le message
```

**Labels GitHub :** `us`, `interaction-telegram`, `llm`, `enregistrement`, `ergonomie`
