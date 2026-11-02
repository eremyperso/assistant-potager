# Agent d'abord — corpus `terrain_compagnon_2026_11`, cascade `prioritaire`

*Généré par `tools/evaluer_dialogues.py` le 2026-11-02. Référence : `mistral/ministral-8b-2512`. Clé de mesure distincte de celle du bot : oui. Rejoué par la cascade du bot (`interpreter`, mode `prioritaire`) : toute phrase va d'abord à l'agent, catalogue complet et outils de savoir. Prompt et catalogue livrés, données réelles du potager 33 en lecture seule, aucune écriture exécutée.*

43 tours joués, dont 0 qui exigent une brique pas encore livrée (outil ou mémoire) : ils sont mesurés et listés, mais exclus des taux du catalogue livré.

**Chemin en production** : 43 par agent. Les 0 tours que la cascade prend avant l'agent ne jugent pas le modèle : ils sont exclus des taux, mais leurs couperets au jardinier comptent.

## Couperets au jardinier (§12.10, bloquants)

Ce que la cascade met réellement devant le jardinier, après le validateur : la proposition à confirmer, le texte lu, ou le chemin suivi (une phrase rendue au parseur de gestes devient un geste).

| Couperet | `ministral-8b-2512` | `ministral-14b-2512` | `mistral-small-2603` |
|---|---:|---:|---:|
| écriture proposée là où il n'en fallait aucune | 1 | 3 | 2 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 | 0 | 0 |
| suppression non demandée | 0 | 0 | 0 |
| texte qui annonce une action non exécutée | 0 | 0 | 0 |
| texte interdit (dose, produit, fait accompli) | 0 | 1 | 0 |
| phrase qui demande d'agir rendue au routeur par mots-clés | 0 | 0 | 0 |
| texte qui demande une confirmation sans proposition à confirmer | 3 | 2 | 4 |
| conversation reprise à zéro (salut en plein dialogue) | 1 | 2 | 0 |

*0 écriture exécutée sans confirmation* tient par construction : la mesure n'exécute rien.

## Couperets du modèle (§12.10, tendance)

Ce que le modèle propose, avant que le validateur et la cascade ne tranchent.

| Couperet | `ministral-8b-2512` | `ministral-14b-2512` | `mistral-small-2603` |
|---|---:|---:|---:|
| écriture proposée là où il n'en fallait aucune | 2 | 4 | 4 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 | 0 | 0 |
| suppression non demandée | 1 | 1 | 1 |
| texte qui annonce une action non exécutée | 3 | 0 | 0 |
| texte interdit (dose, produit, fait accompli) | 0 | 1 | 0 |

**Verdict de la référence : au jardinier, 5 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 1, texte qui demande une confirmation sans proposition à confirmer : 3, conversation reprise à zéro (salut en plein dialogue) : 1. Côté modèle, 6 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 2, outil interdit appelé (ex. un second geste sur une correction) : 0, suppression non demandée : 1, texte qui annonce une action non exécutée : 3, texte interdit (dose, produit, fait accompli) : 0.**

## Par catégorie — `mistral/ministral-8b-2512`

| Catégorie | Tours | Hors agent | Bon outil | Bons paramètres | Sans couperet (modèle) | Couperets au jardinier | p50 | p95 | Jetons/msg | Lecture |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Créations | 3 | 0 | 2/3 (67 %) | 1/1 (100 %) | 3/3 (100 %) | 0 | 2924 ms | 8564 ms | 9982 | ❌ en échec |
| Plusieurs actions dans une phrase | 2 | 0 | 2/2 (100 %) | — | 2/2 (100 %) | 0 | 3648 ms | 4631 ms | 11970 | ✅ tient |
| Négations et retraits | 3 | 0 | 3/3 (100 %) | 1/2 (50 %) | 3/3 (100 %) | 0 | 3659 ms | 4112 ms | 10345 | ❌ en échec |
| Questions sur les données et le savoir | 16 | 0 | 14/16 (88 %) | 0/2 (0 %) | 14/16 (88 %) | 0 | 2165 ms | 5178 ms | 13824 | ❌ en échec |
| Doutes | 6 | 0 | 3/6 (50 %) | 0/1 (0 %) | 4/6 (67 %) | 3 | 1043 ms | 2540 ms | 9134 | ❌ en échec |
| Conversation simple | 7 | 0 | 7/7 (100 %) | — | 7/7 (100 %) | 0 | 870 ms | 4642 ms | 7787 | ✅ tient |
| Hors catalogue | 1 | 0 | 1/1 (100 %) | — | 1/1 (100 %) | 0 | 3292 ms | 3292 ms | 11803 | ✅ tient |
| Registres et prénom | 3 | 0 | 3/3 (100 %) | — | 3/3 (100 %) | 0 | 2482 ms | 19666 ms | 31295 | ✅ tient |
| Caractéristiques d'une parcelle | 2 | 0 | 0/2 (0 %) | 0/1 (0 %) | 1/2 (50 %) | 2 | 5846 ms | 19685 ms | 36479 | ❌ en échec |
| **Total** | 43 | 0 | **35/43 (81 %)** | **2/7 (29 %)** | **38/43 (88 %)** | **5** | 2165 ms | 8564 ms | 13815 | |

*Bon outil* et *bons paramètres* ne portent que sur les tours dont la brique est livrée et que la cascade confie à l'agent ; un paramètre ajouté que le jardinier n'a pas dit est compté faux. Seuil d'une catégorie « qui tient » : 90 %, aucun couperet du modèle et aucun couperet au jardinier.

## Situer l'écart (bon outil, tours livrés)

| Catégorie | `ministral-8b-2512` | `ministral-14b-2512` | `mistral-small-2603` |
|---|---:|---:|---:|
| Créations | 2/3 (67 %) | 3/3 (100 %) | 3/3 (100 %) |
| Plusieurs actions dans une phrase | 2/2 (100 %) | 2/2 (100 %) | 2/2 (100 %) |
| Négations et retraits | 3/3 (100 %) | 3/3 (100 %) | 3/3 (100 %) |
| Questions sur les données et le savoir | 14/16 (88 %) ⚠️2 | 13/16 (81 %) ⚠️2 | 12/16 (75 %) ⚠️2 |
| Doutes | 3/6 (50 %) ⚠️3 | 3/6 (50 %) ⚠️3 | 3/6 (50 %) ⚠️3 |
| Conversation simple | 7/7 (100 %) | 7/7 (100 %) | 7/7 (100 %) |
| Hors catalogue | 1/1 (100 %) | 1/1 (100 %) | 1/1 (100 %) |
| Registres et prénom | 3/3 (100 %) | 3/3 (100 %) ⚠️1 | 3/3 (100 %) |
| Caractéristiques d'une parcelle | 0/2 (0 %) ⚠️1 | 0/2 (0 %) | 1/2 (50 %) |

## Que faire des catégories qui ne tiennent pas ? (allègement d'abord)

### Créations — ❌ en échec

1. **Allègement d'abord** : Verdict du validateur renvoyé au modèle (§12.4) + tour de complément. Le validateur dit au modèle quel champ manque ou a été inventé ; la boucle redonne un tour quand une partie de la phrase n'est reprise par aucun appel.
2. **Modèle ensuite, seulement si l'allègement ne suffit pas** : `mistral/ministral-14b-2512` tient la catégorie. Surcoût par rapport à `mistral/ministral-8b-2512` : +0.74 $/mois (régime stable, 50 messages/jour) ; +2.96 $/mois (mois de découverte, 200 messages/jour). Changement par `GROQ_MODEL_AGENT`, sans code.

### Négations et retraits — ❌ en échec

1. **Allègement d'abord** : Verdict du validateur renvoyé au modèle (§12.4). Le validateur refuse un champ à la valeur affirmative quand la phrase est négative ; le verdict revient au modèle, qui se corrige.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Questions sur les données et le savoir — ❌ en échec

1. **Allègement d'abord** : Préchargement : cultures en place, actions récentes, météo du jour (US-263). Le code précharge ce que la situation rend probable ; le modèle n'enchaîne plus les lectures et les calculs de dates restent au code.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Doutes — ❌ en échec

1. **Allègement d'abord** : Catalogue projeté selon l'état + verdict du validateur. Le validateur rend le doute avec les choix réels (« Nord, Sud ou Est ? ») ; le modèle ne les devine pas.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Caractéristiques d'une parcelle — ❌ en échec

1. **Allègement d'abord** : Filet des caractéristiques de parcelle (US-278). Quand l'agent ne propose aucune écriture, le code lit la parcelle désignée et les valeurs de fiche (vocabulaire fermé) et propose lui-même la modification ; un nom mal dit est proposé au choix.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

## Grille tarifaire et cache de prompt

Grille du 2026-11-01 — source : grille fournie par le jardinier le 01/11/2026. Confirmée.

| Modèle | Entrée ($/M jetons) | Sortie ($/M jetons) | Jetons d'entrée mesurés | Servis par le cache |
|---|---:|---:|---:|---:|
| `mistral/ministral-8b-2512` | 0.15 | 0.15 | 588509 | 397312 (68 %) |
| `mistral/ministral-14b-2512` | 0.2 | 0.2 | 530524 | 187648 (35 %) |
| `mistral/mistral-small-2603` | 0.15 | 0.6 | 497378 | 436640 (88 %) |

Cache : entrée en cache, USD par million : Ministral 3B 0,01 ; 8B 0,015 ; 14B 0,02 ; Small 4 0,015. Le coût mensuel ci-dessous la compte au plein tarif : c'est un plafond. Dans la colonne ci-dessus, 0 % signifie que l'API ne renvoie pas (ou pas encore) de jetons en cache dans `usage.prompt_tokens_details` : le préfixe fixe (prompt + catalogue) est alors facturé plein tarif à chaque appel.

## Naturel — les textes de l'agent, à noter de 1 à 3 — `mistral/ministral-8b-2512`

Critère du lot 1 : ≥ 2,5/3 sur 30 dialogues relus (1 « figé », 2 « correct », 3 « naturel »). 41 texte(s) dans cette mesure. La note est humaine : la colonne est à remplir.

| Dialogue | Tour | Phrase | Texte lu par le jardinier | Note |
|---|---:|---|---|---:|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | Je te montre ce que tu as écrit dans ton carnet, Emmanuel : tes habitudes d'arrosage et ton usage d'engrais bio. Tu veux que je te le relise en détail ? | |
| TER-02 | 1 | c'est quoi la dernière action notée | Emmanuel, la dernière action notée est bien celle du **renommage de la parcelle "essai potager"** en **tunnel** il y a deux jours. Pas de panique, tout est en ordre ! 😉  Tu veux que je te montre les détails de cette action ou autre chose ? | |
| TER-03 | 1 | quel est mon dernier semis ? | Emmanuel, ton dernier semis, c’était du radis le 29 octobre dernier, avec 8 graines. Pas mal pour une fin d’automne ! | |
| TER-04 | 1 | Quelle météo sur Lyon ? | Il est tombé 0.0 mm de pluie sur les 3 derniers jours. | |
| TER-04 | 2 | et demain ? | Demain, on reste sous couvert avec une température maximale de 14°C et aucune pluie prévue. Pas de gros changements donc, mais les nuits restent fraîches. À surveiller pour tes salades et tes jeunes plants ! | |
| TER-05 | 1 | quel météo en Belgique ? | Il est tombé 0.0 mm de pluie sur les 3 derniers jours. | |
| TER-06 | 1 | est ce que je peux obtenir la météo d'une autre région ? | Emmanuel, je te donne la météo ici, mais pas encore pour une autre région. Si tu veux, je peux te chercher des prévisions pour une ville en particulier ? Dis-moi laquelle ! | |
| TER-07 | 1 | quel est la date ? | Aujourd'hui, c'est le **1er novembre 2026**, Emmanuel. Un peu frais pour les tomates, mais pas trop tard pour réfléchir à l'année prochaine ! | |
| TER-08 | 1 | que sais-tu sur moi ? | Ah, Emmanuel, tu veux te lancer dans l'autonomie en tomates, c'est ça ? Tu arroses tes salades le matin et tes autres cultures le soir, et tu mises sur l'engrais bio. Ton objectif pour 2027, c'est 400 kg de récoltes, pas qu'en tomates ! Tu as déjà des haricots, persil, radis et tomates en place. | |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | Emmanuel, je te propose de voir ce que tu as noté comme objectif pour 2026 dans ton historique. Ça te dit ? | |
| TER-10 | 1 | quels sont mes notes ? | Emmanuel, je te propose d’afficher tes notes pour que tu puisses les consulter. C’est parti ? | |
| TER-11 | 1 | quand dois je arroser mes tomates ? | Il est tombé 0.0 mm de pluie sur les 3 derniers jours. Un sol qui sèche fortement puis reçoit beaucoup d'eau d'un coup impose à la plante des variations brutales. Les fruits peuvent alors se fendre, et le calcium parvient irrégulièrement aux tissus en croissance, ce qui favorise le cul noir. Le problème vient de l'alternance bien plus souvent que d'un manque d'eau absolu.  Arroser au pied, tâter l'humidité sous la surface plutôt que de se fier à l'aspect du dessus, et pailler pour amortir les variations. Les fruits déjà marqués ne se réparent pas, mais une humidité plus régulière protège les suivants. Source : Conduite et récolte de la tomate. | |
| TER-12 | 1 | pour mon objectif d'autonomie, que dois je privilégie ? | Une tomate prête a pris la couleur attendue pour sa variété et s'assouplit très légèrement sous une pression douce ; elle se détache sans traction brutale. La couleur seule trompe sur les variétés vertes, jaunes ou sombres : la souplesse et l'aspect de la peau comptent autant.  Cueillir avant que le fruit devienne très mou ou se fende, en soutenant le fruit d'une main et en le détachant à son articulation naturelle plutôt qu'en tirant sur la grappe. Un fruit dont la coloration a commencé finit de mûrir après la cueillette ; un fruit franchement vert et dur, beaucoup moins bien. Une tomate récoltée continue de respirer et perd peu à peu son eau. Les chocs, l'empilement, la chaleur et l'humidité qui condense sur la peau accélèrent le ramollissement et les moisissures ; le froid, lui, éteint l'arôme sans rien conserver de plus.  Poser les fruits en une seule couche dans un contenant peu profond, à l'abri du soleil direct, et les regarder souvent. Séparer les fruits très mûrs de ceux qui doivent encore évoluer, et écarter tout fruit dont la peau est fendue ou meurtrie avant qu'il n'altère ses voisins. Source : Conduite et récolte de la tomate. | |
| TER-13 | 1 | est ce que je peux semer des tomates ce week-end ? | Emmanuel, le week-end n'est pas encore le bon moment pour semer des tomates en pleine terre ici. L'application te propose de choisir entre un **semis en pépinière** ou une **plantation** pour cette culture. Tu veux que je vérifie les dates idéales pour l'une ou l'autre option ? | |
| TER-14 | 1 | mes cultures en pépinière ? | Emmanuel, ta seule pépinière active est le **tunnel** (type chaud) et la **serre** (type froid). Tu n’as pas encore de cultures en pépinière dans ces espaces, mais c’est le bon endroit pour les démarrer ! Tu veux lancer un semis ou vérifier quelque chose en particulier ? | |
| TER-15 | 1 | liste tout ce que j'ai fais aujourd'hui | Emmanuel, je te propose d'afficher tout ce que tu as fait aujourd'hui dans ton potager. Ça te va ? | |
| TER-16 | 1 | que dois je faire ? | Un rang de haricots qui reste vide alors que les graines déterrées sont molles, brunes et sentent la fermentation a le plus souvent souffert d'une terre trop froide et trop humide : la graine gonfle, ne démarre pas et se laisse envahir. Un semis mangé par un rongeur ou un oiseau laisse au contraire des trous et des débris, pas des graines en place.  Gratter deux ou trois emplacements pour trancher entre graine absente et graine pourrie, puis attendre une terre ressuyée et réchauffée pour ressemer. Un sol qui colle à la bêche est le signe le plus parlant. Source : Problèmes observables du haricot. | |
| TER-17 | 1 | Bonsoir | Salut Emmanuel ! Le temps reste couvert ce soir, mais tes tomates et radis devraient apprécier ton arrosage du soir. Tu veux qu’on parle de quelque chose en particulier ? | |
| TER-17 | 2 | En effet , quoi de neuf ? | Les tomates et radis sont bien arrosés ce soir, et avec le temps couvert, ils devraient pousser comme des champignons ! Tu veux qu’on parle de tes prochains semis ou de tes objectifs pour 2027 ? | |
| TER-18 | 1 | bonjour | Salut Emmanuel ! Tu as vu que le temps est couvert aujourd’hui, avec des températures douces mais pas de pluie prévue. Par contre, les radis et les salades vont adorer ce temps ! | |
| TER-18 | 2 | oui je suis prêt et que puis je faire aujourd'hui alors ? | Je te propose d’afficher la météo détaillée des derniers jours pour mieux adapter tes actions. Ça te va ? 😊 | |
| TER-19 | 1 | bonsoir, quel est ton nom ? | Salut Emmanuel ! Je suis ton Compagnon du Potager, là pour t’aider à garder la main verte ! 🌱 | |
| TER-19 | 2 | Merci. | Avec plaisir, Emmanuel ! Toujours ravi de t'aider à garder ton potager en pleine forme. 🌱 | |
| TER-20 | 1 | Laissez le micro. | D'accord, Emmanuel, je reste là pour toi ! 🌱 | |
| TER-21 | 1 | Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord, puis une parcelle sud, puis une parcelle ouest, et enfin tu termines par la création d'une parcelle est. | Emmanuel, je te propose de créer les parcelles **Nord**, **Sud** et **Ouest**. La parcelle **Est** existe déjà, donc je ne la recrée pas.  Confirme-moi sur la carte ce que tu veux faire ! | |
| TER-22 | 1 | créé moi une parcelle nord et une parcelle sud | Emmanuel, je te propose de créer deux nouvelles parcelles : une appelée **Nord** et une autre appelée **Sud**. Ça te va ? | |
| TER-23 | 1 | Est-ce que tu peux renommer la parcelle tunnel en serre chaude ? | Emmanuel, je te propose de renommer la parcelle "tunnel" en **"serre chaude"** pour mieux refléter son usage. C'est bon pour toi ? | |
| TER-24 | 1 | Mets la serre en pépinière chaude et le tunnel en pépinière froide. | Emmanuel, je te propose de transformer la serre en **pépinière chaude** et le tunnel en **pépinière froide**. C’est parfait pour tes semis d’hiver, non ? 😉  La carte te montre les deux actions à confirmer. | |
| TER-25 | 1 | ma serre est une pépinière tiède | Je vais préciser : tu confirmes que ta serre est bien une **pépinière tiède** ? Si oui, je la note comme ça. | |
| TER-26 | 1 | Le sol de ma serre est argileux. | Emmanuel, un sol argileux en serre peut être un vrai casse-tête, mais pas de panique ! Voici les pièges à éviter et comment les contourner pour tes cultures :  - **Pour les tomates** : Ce sol retient trop l’eau, ce qui peut favoriser les maladies comme le mildiou ou faire pourrir les racines. **À faire** : Améliore le drainage en ajoutant du compost bien décomposé ou du sable grossier en surface, et arrose **par petites doses** en touchant le sol avant d’ajouter de l’eau. Un paillage léger (paille ou tonte séchée) aide aussi à réguler l’humidité.  - **Pour les radis** : Ils détestent les sols gorgés d’eau, ce qui peut les rendre fibreux ou amers. **À faire** : Seme-les en surface, dans un sol légèrement humide mais pas détrempé, et espace les rangs pour une meilleure aération.  - **Pour le persil** : Il craint aussi l’excès d’humidité stagnante. **À faire** : Plante-le dans un sol aéré, avec un bon apport de matière organique, et évite de trop arroser après la plantation.  - **Pour les haricots** : Ils aiment les sols riches mais pas détrempés. **À faire** : Si tu les palisses, vérifie que les tiges ne sont pas en contact prolongé avec un sol humide (risque de pourriture).  En résumé : **aérer le sol, pailler, arroser avec modération et surveiller l’humidité**. Tu veux que je te propose de noter ces conseils dans ton carnet ? 😉 Source : Conduite et récolte du haricot. | |
| TER-27 | 1 | passe la planche principal à 2 rangs | Emmanuel, je te propose de passer la planche **principal** à **2 rangs** pour optimiser l'espace. Confirme-moi si ça te convient ! | |
| TER-27 | 2 | non 4 rangs | Emmanuel, je propose de modifier la planche **principal** pour en faire **4 rangs** au lieu de 2. C'est bon pour toi ? | |
| TER-28 | 1 | j'ai arrosé la planche principal ce soir | D'accord Emmanuel, je note que tu as arrosé la planche principale ce soir. Avec les températures fraîches d'aujourd'hui (entre 5,9°C et 13°C), c'est une bonne pratique pour éviter que l'eau ne gèle dans le sol la nuit. Est-ce que tu as remarqué des différences dans l'état des cultures après cet arrosage ? | |
| TER-29 | 1 | Supprime la planche | Emmanuel, tu as deux parcelles qui commencent par "planche" : la **planche test** et **plant tubercule**. Laquelle veux-tu supprimer ? | |
| TER-29 | 2 | la planche test | Tu veux parler de la **planche test** que tu as mentionnée plus tôt ? Dis-moi ce que tu en penses ou ce que tu veux en faire ! | |
| TER-30 | 2 | Oui je veux bien | Emmanuel, la proposition est toujours en attente : tu veux que je te rappelle l'événement demain matin ? Dis-moi simplement « oui » ou « non ». | |
| TER-31 | 2 | oui | Salut Emmanuel ! Toujours aussi motivé pour ton potager, hein ? Les tomates, ça se prépare bien, non ? | |
| TER-32 | 1 | Oups, excuse-moi, supprime la dernière commande. | Pas de souci, Emmanuel ! Je n’ai rien supprimé de ton côté, c’est juste un oubli de ma part. Dis-moi, tu cherchais à faire quoi exactement ? Je suis là pour t’aider. 😉 | |
| TER-33 | 1 | vider mon carnet | Emmanuel, je vais te montrer ce qu'il y a dans ton carnet pour qu'on puisse tout vider ensemble. C'est ça ? | |
| TER-34 | 1 | je veux utiliser de l'engrais chimique pour mes tomates | Emmanuel, les engrais chimiques peuvent effectivement stimuler la croissance des tomates, mais avec ton objectif d'autonomie et ton usage habituel d'engrais bio, ça pourrait perturber l'équilibre naturel de ton sol et tes autres cultures. De plus, les tomates sont gourmandes en nutriments, et un sol bien préparé avec du compost ou du fumier peut déjà leur offrir ce dont elles ont besoin.  Tu veux essayer un engrais chimique spécifique, ou tu cherches plutôt des alternatives bio pour booster tes tomates ? Je peux te proposer des gestes adaptés à ton sol et à tes objectifs. | |
| TER-35 | 1 | objectif autonomie en tomate | Une tomate prête a pris la couleur attendue pour sa variété et s'assouplit très légèrement sous une pression douce ; elle se détache sans traction brutale. La couleur seule trompe sur les variétés vertes, jaunes ou sombres : la souplesse et l'aspect de la peau comptent autant.  Cueillir avant que le fruit devienne très mou ou se fende, en soutenant le fruit d'une main et en le détachant à son articulation naturelle plutôt qu'en tirant sur la grappe. Un fruit dont la coloration a commencé finit de mûrir après la cueillette ; un fruit franchement vert et dur, beaucoup moins bien. Une tomate prête a pris la couleur attendue pour sa variété et s'assouplit très légèrement sous une pression douce ; elle se détache sans traction brutale. La couleur seule trompe sur les variétés vertes, jaunes ou sombres : la souplesse et l'aspect de la peau comptent autant.  Cueillir avant que le fruit devienne très mou ou se fende, en soutenant le fruit d'une main et en le détachant à son articulation naturelle plutôt qu'en tirant sur la grappe. Un fruit dont la coloration a commencé finit de mûrir après la cueillette ; un fruit franchement vert et dur, beaucoup moins bien. Source : Conduite et récolte de la tomate. | |

## Tours à relire — `mistral/ministral-8b-2512`

| Dialogue | Tour | Phrase | Chemin | Attendu | Obtenu du modèle | Vu par le jardinier | Couperets (modèle) | Couperets (jardinier) |
|---|---:|---|---|---|---|---|---|---|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | agent | texte / consulter_donnees | `afficher({"commande": "carnet lister"})` | « Je te montre ce que tu as écrit dans ton carnet, Emmanuel : tes habitudes d'arrosage et ton usage d'engrais bio. Tu veux que je te le relise en détail ? » + /carnet lister | annonce_non_executee | — |
| TER-04 | 1 | Quelle météo sur Lyon ? | agent | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | `[ok]` | « Il est tombé 0.0 mm de pluie sur les 3 derniers jours. » | — | — |
| TER-04 | 2 | et demain ? | agent | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | `[ok]` | « Demain, on reste sous couvert avec une température maximale de 14°C et aucune pluie prévue. Pas de gros changements donc, mais les nuits restent fraîches. À surveiller pour tes salades et tes jeunes plants ! » | — | — |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | agent | texte / afficher | `afficher({"commande": "historique", "date": "2026"})` | « Emmanuel, je te propose de voir ce que tu as noté comme objectif pour 2026 dans ton historique. Ça te dit ? » + /historique | annonce_non_executee | — |
| TER-25 | 1 | ma serre est une pépinière tiède | agent | texte | `modifier_parcelle({"parcelle": "serre", "type_pepiniere": "chaude"})` | « Je vais préciser : tu confirmes que ta serre est bien une **pépinière tiède** ? Si oui, je la note comme ça. » | annonce_non_executee | promesse_sans_proposition |
| TER-26 | 1 | Le sol de ma serre est argileux. | agent | modifier_parcelle `{'parcelle': 'serre', 'type_sol': 'argileux'}` | `[ok]` | « Emmanuel, un sol argileux en serre peut être un vrai casse-tête, mais pas de panique ! Voici les pièges à éviter et comment les contourner pour tes cultures :  - **Pour les tomates** : Ce sol retient trop l’eau, ce qui peut favoriser les maladies comme le mildiou ou faire pourrir les racines. **À faire** : Améliore le drainage en ajoutant du compost bien décomposé ou du sable grossier en surface, et arrose **par petites doses** en touchant le sol avant d’ajouter de l’eau. Un paillage léger (paille ou tonte séchée) aide aussi à réguler l’humidité.  - **Pour les radis** : Ils détestent les sols gorgés d’eau, ce qui peut les rendre fibreux ou amers. **À faire** : Seme-les en surface, dans un sol légèrement humide mais pas détrempé, et espace les rangs pour une meilleure aération.  - **Pour le persil** : Il craint aussi l’excès d’humidité stagnante. **À faire** : Plante-le dans un sol aéré, avec un bon apport de matière organique, et évite de trop arroser après la plantation.  - **Pour les haricots** : Ils aiment les sols riches mais pas détrempés. **À faire** : Si tu les palisses, vérifie que les tiges ne sont pas en contact prolongé avec un sol humide (risque de pourriture).  En résumé : **aérer le sol, pailler, arroser avec modération et surveiller l’humidité**. Tu veux que je te propose de noter ces conseils dans ton carnet ? 😉 Source : Conduite et récolte du haricot. » | — | promesse_sans_proposition |
| TER-27 | 2 | non 4 rangs | agent | modifier_parcelle `{'nb_rangs': 4}` | `modifier_parcelle({"parcelle": "principal", "nb_rangs": 4})` | « Emmanuel, je propose de modifier la planche **principal** pour en faire **4 rangs** au lieu de 2. C'est bon pour toi ? » + /parcelle modifier principal rangs=4 | — | — |
| TER-28 | 1 | j'ai arrosé la planche principal ce soir | agent | saisir_geste | `[ok]` | « D'accord Emmanuel, je note que tu as arrosé la planche principale ce soir. Avec les températures fraîches d'aujourd'hui (entre 5,9°C et 13°C), c'est une bonne pratique pour éviter que l'eau ne gèle dans le sol la nuit. Est-ce que tu as remarqué des différences dans l'état des cultures après cet arrosage ? » | — | — |
| TER-29 | 1 | Supprime la planche | agent | texte | `supprimer_parcelle({"nom": "planche"})` | « Emmanuel, tu as deux parcelles qui commencent par "planche" : la **planche test** et **plant tubercule**. Laquelle veux-tu supprimer ? » | ecriture_sans_attente, destruction_erronee | promesse_sans_proposition |
| TER-29 | 2 | la planche test | agent | supprimer_parcelle `{'nom': 'planche test'}` | `[ok]` | « Tu veux parler de la **planche test** que tu as mentionnée plus tôt ? Dis-moi ce que tu en penses ou ce que tu veux en faire ! » | — | — |
| TER-31 | 1 | vide le geste | agent | texte / afficher | `saisir_geste({})` | geste | ecriture_sans_attente | ecriture_sans_attente |
| TER-31 | 2 | oui | agent | texte / afficher | `[ok]` | « Salut Emmanuel ! Toujours aussi motivé pour ton potager, hein ? Les tomates, ça se prépare bien, non ? » | — | salut_en_cours |
