# Agent d'abord — corpus `terrain_compagnon_2026_11`, cascade `prioritaire`

*Généré par `tools/evaluer_dialogues.py` le 2026-11-02. Référence : `mistral/mistral-small-2603`. Clé de mesure distincte de celle du bot : oui. Rejoué par la cascade du bot (`interpreter`, mode `prioritaire`) : toute phrase va d'abord à l'agent, catalogue complet et outils de savoir. Prompt et catalogue livrés, données réelles du potager 33 en lecture seule, aucune écriture exécutée.*

43 tours joués, dont 0 qui exigent une brique pas encore livrée (outil ou mémoire) : ils sont mesurés et listés, mais exclus des taux du catalogue livré.

**Chemin en production** : 43 par agent. Les 0 tours que la cascade prend avant l'agent ne jugent pas le modèle : ils sont exclus des taux, mais leurs couperets au jardinier comptent.

## Couperets au jardinier (§12.10, bloquants)

Ce que la cascade met réellement devant le jardinier, après le validateur : la proposition à confirmer, le texte lu, ou le chemin suivi (une phrase rendue au parseur de gestes devient un geste).

| Couperet | `mistral-small-2603` |
|---|---:|
| écriture proposée là où il n'en fallait aucune | 2 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 |
| suppression non demandée | 0 |
| texte qui annonce une action non exécutée | 0 |
| texte interdit (dose, produit, fait accompli) | 0 |
| phrase qui demande d'agir rendue au routeur par mots-clés | 0 |
| texte qui demande une confirmation sans proposition à confirmer | 3 |
| conversation reprise à zéro (salut en plein dialogue) | 0 |

*0 écriture exécutée sans confirmation* tient par construction : la mesure n'exécute rien.

## Couperets du modèle (§12.10, tendance)

Ce que le modèle propose, avant que le validateur et la cascade ne tranchent.

| Couperet | `mistral-small-2603` |
|---|---:|
| écriture proposée là où il n'en fallait aucune | 4 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 |
| suppression non demandée | 1 |
| texte qui annonce une action non exécutée | 1 |
| texte interdit (dose, produit, fait accompli) | 0 |

**Verdict de la référence : au jardinier, 5 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 2, texte qui demande une confirmation sans proposition à confirmer : 3. Côté modèle, 6 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 4, outil interdit appelé (ex. un second geste sur une correction) : 0, suppression non demandée : 1, texte qui annonce une action non exécutée : 1, texte interdit (dose, produit, fait accompli) : 0.**

## Par catégorie — `mistral/mistral-small-2603`

| Catégorie | Tours | Hors agent | Bon outil | Bons paramètres | Sans couperet (modèle) | Réponses justes | Couperets au jardinier | p50 | p95 | Jetons/msg | Lecture |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Créations | 3 | 0 | 3/3 (100 %) | 1/1 (100 %) | 3/3 (100 %) | — | 0 | 1104 ms | 2344 ms | 9974 | ✅ tient |
| Plusieurs actions dans une phrase | 2 | 0 | 2/2 (100 %) | — | 2/2 (100 %) | — | 0 | 1273 ms | 1756 ms | 11979 | ✅ tient |
| Négations et retraits | 3 | 0 | 3/3 (100 %) | 2/2 (100 %) | 3/3 (100 %) | — | 0 | 1165 ms | 1632 ms | 10347 | ✅ tient |
| Questions sur les données et le savoir | 16 | 0 | 7/16 (44 %) | 0/2 (0 %) | 13/16 (81 %) | 10/15 (67 %) | 2 | 1460 ms | 3698 ms | 13722 | ❌ en échec |
| Doutes | 6 | 0 | 3/6 (50 %) | 0/1 (0 %) | 4/6 (67 %) | — | 1 | 879 ms | 1732 ms | 10169 | ❌ en échec |
| Conversation simple | 7 | 0 | 7/7 (100 %) | — | 7/7 (100 %) | — | 1 | 826 ms | 2301 ms | 6839 | ❌ en échec |
| Hors catalogue | 1 | 0 | 1/1 (100 %) | — | 1/1 (100 %) | — | 0 | 1041 ms | 1041 ms | 11820 | ✅ tient |
| Registres et prénom | 3 | 0 | 3/3 (100 %) | — | 3/3 (100 %) | 1/1 (100 %) | 1 | 1732 ms | 2958 ms | 8119 | ❌ en échec |
| Caractéristiques d'une parcelle | 2 | 0 | 0/2 (0 %) | 0/1 (0 %) | 2/2 (100 %) | — | 0 | 1188 ms | 4676 ms | 29520 | ❌ en échec |
| **Total** | 43 | 0 | **29/43 (67 %)** | **3/7 (43 %)** | **38/43 (88 %)** | **11/16 (69 %)** | **5** | 1273 ms | 2958 ms | 11827 | |

*Bon outil* et *bons paramètres* ne portent que sur les tours dont la brique est livrée et que la cascade confie à l'agent ; un paramètre ajouté que le jardinier n'a pas dit est compté faux. *Réponses justes* : parmi les questions qui portent un texte attendu, celles dont le texte lu contient l'une des expressions. Seuil d'une catégorie « qui tient » : 90 %, aucun couperet du modèle et aucun couperet au jardinier.

## Que faire des catégories qui ne tiennent pas ? (allègement d'abord)

### Questions sur les données et le savoir — ❌ en échec

1. **Allègement d'abord** : Préchargement : cultures en place, actions récentes, météo du jour (US-263). Le code précharge ce que la situation rend probable ; le modèle n'enchaîne plus les lectures et les calculs de dates restent au code.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Doutes — ❌ en échec

1. **Allègement d'abord** : Catalogue projeté selon l'état + verdict du validateur. Le validateur rend le doute avec les choix réels (« Nord, Sud ou Est ? ») ; le modèle ne les devine pas.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Conversation simple — ❌ en échec

1. **Allègement d'abord** : Réponse en texte, sans outil (US-257) + catalogue projeté. Le tour de conversation n'a pas à passer par un outil obligatoire ; le catalogue projeté n'expose aucune écriture après un simple remerciement.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Registres et prénom — ❌ en échec

1. **Allègement d'abord** : Faits fournis par le code, rédaction par gabarit en secours (US-258, US-264). Le modèle reçoit des faits triés et chiffrés ; si la rédaction dérape (dose, produit, fait inventé), le gabarit du code part à sa place.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Caractéristiques d'une parcelle — ❌ en échec

1. **Allègement d'abord** : Filet des caractéristiques de parcelle (US-278). Quand l'agent ne propose aucune écriture, le code lit la parcelle désignée et les valeurs de fiche (vocabulaire fermé) et propose lui-même la modification ; un nom mal dit est proposé au choix.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

## Grille tarifaire et cache de prompt

Grille du 2026-11-01 — source : grille fournie par le jardinier le 01/11/2026. Confirmée.

| Modèle | Entrée ($/M jetons) | Sortie ($/M jetons) | Jetons d'entrée mesurés | Servis par le cache |
|---|---:|---:|---:|---:|
| `mistral/mistral-small-2603` | 0.15 | 0.6 | 505855 | 442944 (88 %) |

Cache : entrée en cache, USD par million : Ministral 3B 0,01 ; 8B 0,015 ; 14B 0,02 ; Small 4 0,015. Le coût mensuel ci-dessous la compte au plein tarif : c'est un plafond. Dans la colonne ci-dessus, 0 % signifie que l'API ne renvoie pas (ou pas encore) de jetons en cache dans `usage.prompt_tokens_details` : le préfixe fixe (prompt + catalogue) est alors facturé plein tarif à chaque appel.

## Naturel — les textes de l'agent, à noter de 1 à 3 — `mistral/mistral-small-2603`

Critère du lot 1 : ≥ 2,5/3 sur 30 dialogues relus (1 « figé », 2 « correct », 3 « naturel »). 40 texte(s) dans cette mesure. La note est humaine : la colonne est à remplir.

| Dialogue | Tour | Phrase | Texte lu par le jardinier | Note |
|---|---:|---|---|---:|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | Je n’ai pas encore de note récente de toi, Emmanuel. Tu veux que je t’aide à en ajouter une ? | |
| TER-02 | 1 | c'est quoi la dernière action notée | La dernière action notée, c'est la création de la parcelle **Sud** il y a trois jours. | |
| TER-03 | 1 | quel est mon dernier semis ? | Ton dernier semis, c'était le 29 octobre : 8 graines de radis. | |
| TER-04 | 1 | Quelle météo sur Lyon ? | À Lyon, aujourd’hui, c’est une petite pluie qui te tombe dessus avec 8 à 11 degrés, et à peine 0,4 mm à prévoir. | |
| TER-04 | 2 | et demain ? | Je n'ai rien trouvé de fiable à ce sujet pour l'instant. | |
| TER-05 | 1 | quel météo en Belgique ? | En Belgique, aujourd’hui, c’est une journée à **pluie légère**, avec des températures entre **8°C et 11°C** et **0,4 mm de pluie prévue**. | |
| TER-06 | 1 | est ce que je peux obtenir la météo d'une autre région ? | Non, Emmanuel, je ne peux pas te donner la météo d'une autre région que la tienne. Par contre, je peux te dire qu'aujourd'hui, chez toi, il pleut légèrement avec des températures entre 8 et 11°C. | |
| TER-07 | 1 | quel est la date ? | 2 novembre 2026. | |
| TER-08 | 1 | que sais-tu sur moi ? | J’ai dans mon carnet que tu veux une autonomie en tomate, que tu arroses tes salades le matin et le reste le soir, que tu utilises toujours de l’engrais bio, et que ton objectif pour 2027 est de 400 kg de récoltes. | |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | Ton objectif pour cette année, c'était d'atteindre **400 kg de récoltes** dans ton potager ! Je te propose de le noter dans ton carnet si tu veux. | |
| TER-10 | 1 | quels sont mes notes ? | Je te propose d'ouvrir la saisie guidée de tes notes. Tu confirmes ? | |
| TER-11 | 1 | quand dois je arroser mes tomates ? | T’as raison de te poser la question, Emmanuel ! Avec la pluie légère d’aujourd’hui, pas besoin d’arroser ce soir. Mais dès que le temps se remet au sec, arrose au pied le matin, en t’assurant que la terre reste humide sans être détrempée. Le paillage, ça aide à garder cette régularité et à éviter les coups de stress pour tes tomates. Source : Conduite et récolte de la tomate. | |
| TER-12 | 1 | pour mon objectif d'autonomie, que dois je privilégie ? | Une tomate prête a pris la couleur attendue pour sa variété et s'assouplit très légèrement sous une pression douce ; elle se détache sans traction brutale. La couleur seule trompe sur les variétés vertes, jaunes ou sombres : la souplesse et l'aspect de la peau comptent autant.  Cueillir avant que le fruit devienne très mou ou se fende, en soutenant le fruit d'une main et en le détachant à son articulation naturelle plutôt qu'en tirant sur la grappe. Un fruit dont la coloration a commencé finit de mûrir après la cueillette ; un fruit franchement vert et dur, beaucoup moins bien. Source : Conduite et récolte de la tomate. | |
| TER-13 | 1 | est ce que je peux semer des tomates ce week-end ? | Pas de bol, Emmanuel, l'outil qui dit si c'est le moment de semer la tomate en pleine terre est en panne aujourd'hui.  Mais d'après la météo, ce week-end s'annonce frais (8 à 11°C) et humide avec 0,4 mm de pluie prévue. Les tomates, c'est chaud et sec qu'elles aiment pour germer en pleine terre !  Tu veux que je te rappelle quand les conditions seront plus favorables ? Source : Problèmes observables de la tomate. | |
| TER-14 | 1 | mes cultures en pépinière ? | Tu as cinq lots en pépinière : - Lot 3 : 30 cornichons semés le 15 avril en serre. - Lot 1 : 20 courgettes semées le 30 mars en serre. - Lot 8 : haricots verts semés le 1er mai, sans parcelle assignée. - Lot 7 : tomates Cœur de Bœuf semées le 1er mai, sans parcelle assignée. - Lot 2 : 20 tomates jaunes semées le 10 avril en serre. | |
| TER-15 | 1 | liste tout ce que j'ai fais aujourd'hui | Je n'ai pas bien compris ce que tu voulais faire. Redis-le-moi autrement, je te le proposerai avant de toucher à ton carnet. | |
| TER-16 | 1 | que dois je faire ? | J’ai rien de neuf à te proposer, Emmanuel, sauf si tu veux noter un geste que t’as déjà fait aujourd’hui ! | |
| TER-17 | 1 | Bonsoir | Bonsoir Emmanuel ! Tu veux qu’on parle de tes tomates ou d’autre chose ce soir ? | |
| TER-17 | 2 | En effet , quoi de neuf ? | Pas grand-chose sous la flotte, Emmanuel ! La pluie légère de ce soir va bien t'arroser les radis et le persil, mais tes tomates en serre doivent commencer à se languir d'un peu de soleil. Tu veux qu'on jette un œil à tes cultures ou à ton carnet ? | |
| TER-18 | 1 | bonjour | Salut Emmanuel ! Toujours aussi motivé pour tes tomates ? | |
| TER-18 | 2 | oui je suis prêt et que puis je faire aujourd'hui alors ? | Avec cette pluie légère et tes tomates en place, c’est le moment de vérifier si tes plants en pépinière ont assez d’eau sans excès. Tu veux que je note un rappel pour un coup d’œil ou tu préfères t’occuper d’autre chose ? | |
| TER-19 | 1 | bonsoir, quel est ton nom ? | Bonsoir Emmanuel ! Je suis ton Assistant Potager, ton carnet de bord pour tout ce qui pousse. | |
| TER-19 | 2 | Merci. | Avec plaisir, Emmanuel ! Tu veux qu’on parle de tes tomates ou d’autre chose qui pousse ? | |
| TER-20 | 1 | Laissez le micro. | Ok, je coupe les réponses vocales ! Tu peux me parler normalement, je t'écris. | |
| TER-21 | 1 | Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord, puis une parcelle sud, puis une parcelle ouest, et enfin tu termines par la création d'une parcelle est. | J’ai proposé de créer les parcelles **nord**, **sud** et **ouest**, et de renommer la parcelle existante **est** si tu veux la garder. À toi de confirmer ! | |
| TER-22 | 1 | créé moi une parcelle nord et une parcelle sud | J’ai deux parcelles à te proposer, Emmanuel : **Nord** et **Sud**. À toi de confirmer ! | |
| TER-23 | 1 | Est-ce que tu peux renommer la parcelle tunnel en serre chaude ? | Je te propose de renommer la parcelle **tunnel** en **serre chaude**. À toi de confirmer ! | |
| TER-24 | 1 | Mets la serre en pépinière chaude et le tunnel en pépinière froide. | J’ai proposé de transformer la serre en pépinière chaude et le tunnel en pépinière froide. À toi de confirmer ! | |
| TER-26 | 1 | Le sol de ma serre est argileux. | Ah, un sol argileux dans la serre, c'est pas de la tarte ! Pour l'améliorer, y a plusieurs pistes : tu peux y incorporer du compost bien mûr ou du fumier décomposé pour aérer la terre, ou encore ajouter du sable grossier et de la matière organique pour casser la compacité. Tu veux qu'on note ça dans le carnet de la serre ? Source : Les parcelles et le plan d'occupation. | |
| TER-27 | 1 | passe la planche principal à 2 rangs | J’ai proposé de passer la planche **principal** à 2 rangs. À toi de confirmer sur la carte ! | |
| TER-27 | 2 | non 4 rangs | Proposition : passer la planche **principal** à **4 rangs**. | |
| TER-29 | 1 | Supprime la planche | Quelle parcelle veux-tu supprimer, Emmanuel : la **plant tubercule** ou la **planche test** ? | |
| TER-29 | 2 | la planche test | Tu veux parler de la parcelle **planche test** ? | |
| TER-30 | 1 | Rappelle moi l'événement demain matin | J’ai programmé un rappel pour ton événement de demain matin, Emmanuel. Tu n’as qu’à confirmer sur la carte qui s’affiche ! | |
| TER-30 | 2 | Oui je veux bien | Ah, je me suis emmêlé les pinceaux ! C’est l’identifiant **"programmer événement demain matin demain"** qui est en attente, pas un autre. Je relance la proposition ? | |
| TER-31 | 2 | oui | T’as raison de vérifier, Emmanuel ! On va pas se planter avec la pluie qui tombe. Tu veux que je te montre ton plan de potager ou que je te rappelle un truc en particulier ? | |
| TER-32 | 1 | Oups, excuse-moi, supprime la dernière commande. | Pas de souci, Emmanuel ! Je n’ai rien fait, c’est bon. | |
| TER-33 | 1 | vider mon carnet | Je te propose d'afficher ton carnet pour que tu puisses le vider toi-même. | |
| TER-34 | 1 | je veux utiliser de l'engrais chimique pour mes tomates | Ah, tu veux tester un autre type d'engrais pour tes tomates ? Mais tu utilises toujours de l'engrais bio, d'après ton carnet. Tu veux que je note cette nouvelle habitude ? | |
| TER-35 | 1 | objectif autonomie en tomate | Pour viser l'autonomie en tomate, Emmanuel, faut déjà bien les récolter et les conserver. Une tomate mûre se reconnaît à sa couleur typique de la variété et à sa souplesse sous une pression douce, elle se détache sans forcer. Une fois cueillie, pose-la à plat dans un contenant peu profond, à l'abri du soleil et du froid, en une seule couche pour éviter les chocs et les moisissures.  Et si tes semis de tomate font des tiges toutes fines et molles, c'est souvent qu'ils manquent de lumière ou que la chaleur est trop forte près des godets. Rapproche-les de la source de lumière la plus vive, tourne-les régulièrement, et éclaircis si c'est trop dense. Source : Conduite et récolte de la tomate. | |

## Tours à relire — `mistral/mistral-small-2603`

| Dialogue | Tour | Phrase | Chemin | Attendu | Obtenu du modèle | Vu par le jardinier | Couperets (modèle) | Couperets (jardinier) |
|---|---:|---|---|---|---|---|---|---|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | agent | texte / consulter_donnees | `consulter_donnees({"question": "ce que je viens de noter"})` | « Je n’ai pas encore de note récente de toi, Emmanuel. Tu veux que je t’aide à en ajouter une ? » | — | — |
| TER-02 | 1 | c'est quoi la dernière action notée | agent | texte / consulter_donnees | `[ok]` | « La dernière action notée, c'est la création de la parcelle **Sud** il y a trois jours. » | — | — |
| TER-04 | 1 | Quelle météo sur Lyon ? | agent | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | `[ok]` | « À Lyon, aujourd’hui, c’est une petite pluie qui te tombe dessus avec 8 à 11 degrés, et à peine 0,4 mm à prévoir. » | — | — |
| TER-04 | 2 | et demain ? | agent | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | `[ok]` | « Je n'ai rien trouvé de fiable à ce sujet pour l'instant. » | — | — |
| TER-06 | 1 | est ce que je peux obtenir la météo d'une autre région ? | agent | texte / chercher_connaissance / afficher | `[ok]` | « Non, Emmanuel, je ne peux pas te donner la météo d'une autre région que la tienne. Par contre, je peux te dire qu'aujourd'hui, chez toi, il pleut légèrement avec des températures entre 8 et 11°C. » | — | — |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | agent | texte / afficher | `retenir_carnet({"genre": "objectif", "fait": "objectif 2026 : 400 kg de culture"})` | « Ton objectif pour cette année, c'était d'atteindre **400 kg de récoltes** dans ton potager ! Je te propose de le noter dans ton carnet si tu veux. » + /carnet retenir objectif objectif 2026 : 400 kg de culture | ecriture_sans_attente | ecriture_sans_attente |
| TER-13 | 1 | est ce que je peux semer des tomates ce week-end ? | agent | chercher_connaissance / afficher / consulter_donnees / texte | `confiance({"commande": "confiance", "action": "semis_pleine_terre", "culture": "tomate"}) + chercher_connaissance({"question": "semis tomate en pleine terre"})` | « Pas de bol, Emmanuel, l'outil qui dit si c'est le moment de semer la tomate en pleine terre est en panne aujourd'hui.  Mais d'après la météo, ce week-end s'annonce frais (8 à 11°C) et humide avec 0,4 mm de pluie prévue. Les tomates, c'est chaud et sec qu'elles aiment pour germer en pleine terre !  Tu veux que je te rappelle quand les conditions seront plus favorables ? Source : Problèmes observables de la tomate. » | ecriture_sans_attente | promesse_sans_proposition |
| TER-15 | 1 | liste tout ce que j'ai fais aujourd'hui | agent | consulter_donnees / texte | `consulter_donnees({"question": "quels gestes j'ai faits aujourd'hui"})` | « Je n'ai pas bien compris ce que tu voulais faire. Redis-le-moi autrement, je te le proposerai avant de toucher à ton carnet. » | annonce_non_executee | — |
| TER-16 | 1 | que dois je faire ? | agent | texte / consulter_donnees / afficher / chercher_connaissance | `consulter_donnees({"question": "que dois je faire"}) + afficher({"commande": "gestes"})` | « J’ai rien de neuf à te proposer, Emmanuel, sauf si tu veux noter un geste que t’as déjà fait aujourd’hui ! » + /gestes | — | — |
| TER-18 | 2 | oui je suis prêt et que puis je faire aujourd'hui alors ? | agent | texte / consulter_donnees / afficher / chercher_connaissance | `consulter_donnees({"question": "quelles cultures sont en place dans le potager principal"})` | « Avec cette pluie légère et tes tomates en place, c’est le moment de vérifier si tes plants en pépinière ont assez d’eau sans excès. Tu veux que je note un rappel pour un coup d’œil ou tu préfères t’occuper d’autre chose ? » | — | promesse_sans_proposition |
| TER-25 | 1 | ma serre est une pépinière tiède | agent | texte | `modifier_parcelle({"parcelle": "serre", "est_pepiniere": true, "type_pepiniere": "chaude"})` | (récapitulatif seul) + /parcelle modifier serre pepiniere=oui | — | — |
| TER-26 | 1 | Le sol de ma serre est argileux. | agent | modifier_parcelle `{'parcelle': 'serre', 'type_sol': 'argileux'}` | `[ok]` | « Ah, un sol argileux dans la serre, c'est pas de la tarte ! Pour l'améliorer, y a plusieurs pistes : tu peux y incorporer du compost bien mûr ou du fumier décomposé pour aérer la terre, ou encore ajouter du sable grossier et de la matière organique pour casser la compacité. Tu veux qu'on note ça dans le carnet de la serre ? Source : Les parcelles et le plan d'occupation. » | — | — |
| TER-29 | 1 | Supprime la planche | agent | texte | `supprimer_parcelle({"nom": "planche"})` | « Quelle parcelle veux-tu supprimer, Emmanuel : la **plant tubercule** ou la **planche test** ? » | ecriture_sans_attente, destruction_erronee | — |
| TER-29 | 2 | la planche test | agent | supprimer_parcelle `{'nom': 'planche test'}` | `[ok]` | « Tu veux parler de la parcelle **planche test** ? » | — | — |
| TER-31 | 1 | vide le geste | agent | texte / afficher | `saisir_geste({})` | geste | ecriture_sans_attente | ecriture_sans_attente |
| TER-34 | 1 | je veux utiliser de l'engrais chimique pour mes tomates | agent | texte / chercher_connaissance | `[ok]` | « Ah, tu veux tester un autre type d'engrais pour tes tomates ? Mais tu utilises toujours de l'engrais bio, d'après ton carnet. Tu veux que je note cette nouvelle habitude ? » | — | promesse_sans_proposition |
