# Agent d'abord — corpus `terrain_compagnon_2026_11`, cascade `prioritaire`

*Généré par `tools/evaluer_dialogues.py` le 2026-11-03. Référence : `mistral/mistral-small-2603`. Clé de mesure distincte de celle du bot : oui. Rejoué par la cascade du bot (`interpreter`, mode `prioritaire`) : toute phrase va d'abord à l'agent, catalogue complet et outils de savoir. Prompt et catalogue livrés, données réelles du potager 33 en lecture seule, aucune écriture exécutée.*

43 tours joués, dont 0 qui exigent une brique pas encore livrée (outil ou mémoire) : ils sont mesurés et listés, mais exclus des taux du catalogue livré.

**Chemin en production** : 43 par agent. Les 0 tours que la cascade prend avant l'agent ne jugent pas le modèle : ils sont exclus des taux, mais leurs couperets au jardinier comptent.

## Couperets au jardinier (§12.10, bloquants)

Ce que la cascade met réellement devant le jardinier, après le validateur : la proposition à confirmer, le texte lu, ou le chemin suivi (une phrase rendue au parseur de gestes devient un geste).

| Couperet | `mistral-small-2603` |
|---|---:|
| écriture proposée là où il n'en fallait aucune | 1 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 |
| suppression non demandée | 0 |
| texte qui annonce une action non exécutée | 0 |
| texte interdit (dose, produit, fait accompli) | 0 |
| phrase qui demande d'agir rendue au routeur par mots-clés | 0 |
| texte qui demande une confirmation sans proposition à confirmer | 3 |
| conversation reprise à zéro (salut en plein dialogue) | 1 |

*0 écriture exécutée sans confirmation* tient par construction : la mesure n'exécute rien.

## Couperets du modèle (§12.10, tendance)

Ce que le modèle propose, avant que le validateur et la cascade ne tranchent.

| Couperet | `mistral-small-2603` |
|---|---:|
| écriture proposée là où il n'en fallait aucune | 3 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 |
| suppression non demandée | 1 |
| texte qui annonce une action non exécutée | 0 |
| texte interdit (dose, produit, fait accompli) | 0 |

**Verdict de la référence : au jardinier, 5 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 1, texte qui demande une confirmation sans proposition à confirmer : 3, conversation reprise à zéro (salut en plein dialogue) : 1. Côté modèle, 4 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 3, outil interdit appelé (ex. un second geste sur une correction) : 0, suppression non demandée : 1, texte qui annonce une action non exécutée : 0, texte interdit (dose, produit, fait accompli) : 0.**

## Par catégorie — `mistral/mistral-small-2603`

| Catégorie | Tours | Hors agent | Bon outil | Bons paramètres | Sans couperet (modèle) | Réponses justes | Couperets au jardinier | p50 | p95 | Jetons/msg | Lecture |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Créations | 3 | 0 | 3/3 (100 %) | 1/1 (100 %) | 3/3 (100 %) | — | 0 | 1096 ms | 1676 ms | 10334 | ✅ tient |
| Plusieurs actions dans une phrase | 2 | 0 | 2/2 (100 %) | — | 2/2 (100 %) | — | 0 | 1330 ms | 1915 ms | 12422 | ✅ tient |
| Négations et retraits | 3 | 0 | 3/3 (100 %) | 2/2 (100 %) | 3/3 (100 %) | — | 0 | 930 ms | 1057 ms | 10717 | ✅ tient |
| Questions sur les données et le savoir | 16 | 0 | 9/16 (56 %) | 0/2 (0 %) | 15/16 (94 %) | 11/15 (73 %) | 2 | 1548 ms | 3407 ms | 12672 | ❌ en échec |
| Doutes | 6 | 0 | 3/6 (50 %) | 0/1 (0 %) | 4/6 (67 %) | — | 2 | 1296 ms | 3998 ms | 11594 | ❌ en échec |
| Conversation simple | 7 | 0 | 7/7 (100 %) | — | 7/7 (100 %) | — | 0 | 738 ms | 1975 ms | 7067 | ✅ tient |
| Hors catalogue | 1 | 0 | 1/1 (100 %) | — | 1/1 (100 %) | — | 0 | 1405 ms | 1405 ms | 12278 | ✅ tient |
| Registres et prénom | 3 | 0 | 3/3 (100 %) | — | 3/3 (100 %) | 1/1 (100 %) | 1 | 2465 ms | 6541 ms | 18534 | ❌ en échec |
| Caractéristiques d'une parcelle | 2 | 0 | 0/2 (0 %) | 0/1 (0 %) | 2/2 (100 %) | — | 0 | 1640 ms | 5084 ms | 30499 | ❌ en échec |
| **Total** | 43 | 0 | **31/43 (72 %)** | **3/7 (43 %)** | **40/43 (93 %)** | **12/16 (75 %)** | **5** | 1330 ms | 3998 ms | 12527 | |

*Bon outil* et *bons paramètres* ne portent que sur les tours dont la brique est livrée et que la cascade confie à l'agent ; un paramètre ajouté que le jardinier n'a pas dit est compté faux. *Réponses justes* : parmi les questions qui portent un texte attendu, celles dont le texte lu contient l'une des expressions. Seuil d'une catégorie « qui tient » : 90 %, aucun couperet du modèle et aucun couperet au jardinier.

## Que faire des catégories qui ne tiennent pas ? (allègement d'abord)

### Questions sur les données et le savoir — ❌ en échec

1. **Allègement d'abord** : Préchargement : cultures en place, actions récentes, météo du jour (US-263). Le code précharge ce que la situation rend probable ; le modèle n'enchaîne plus les lectures et les calculs de dates restent au code.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

### Doutes — ❌ en échec

1. **Allègement d'abord** : Catalogue projeté selon l'état + verdict du validateur. Le validateur rend le doute avec les choix réels (« Nord, Sud ou Est ? ») ; le modèle ne les devine pas.
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
| `mistral/mistral-small-2603` | 0.15 | 0.6 | 535771 | 470976 (88 %) |

Cache : entrée en cache, USD par million : Ministral 3B 0,01 ; 8B 0,015 ; 14B 0,02 ; Small 4 0,015. Le coût mensuel ci-dessous la compte au plein tarif : c'est un plafond. Dans la colonne ci-dessus, 0 % signifie que l'API ne renvoie pas (ou pas encore) de jetons en cache dans `usage.prompt_tokens_details` : le préfixe fixe (prompt + catalogue) est alors facturé plein tarif à chaque appel.

## Naturel — les textes de l'agent, à noter de 1 à 3 — `mistral/mistral-small-2603`

Critère du lot 1 : ≥ 2,5/3 sur 30 dialogues relus (1 « figé », 2 « correct », 3 « naturel »). 40 texte(s) dans cette mesure. La note est humaine : la colonne est à remplir.

| Dialogue | Tour | Phrase | Texte lu par le jardinier | Note |
|---|---:|---|---|---:|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | Je n’ai pas encore de note récente de toi, Emmanuel. Tu veux que je t’aide à en ajouter une ? | |
| TER-02 | 1 | c'est quoi la dernière action notée | La dernière action notée, c'est la création de la parcelle **Sud** il y a 4 jours. | |
| TER-03 | 1 | quel est mon dernier semis ? | Ton dernier semis, c'était des radis le 29 octobre, avec 8 graines. | |
| TER-04 | 1 | Quelle météo sur Lyon ? | Pour Lyon, Auvergne-Rhône-Alpes, France : aujourd'hui, Couvert, de 5.4 à 10.3 °C, 0.0 mm de pluie prévus. | |
| TER-04 | 2 | et demain ? | Demain sur ton potager, Emmanuel, c'est encore des averses légères avec des températures entre 5.7 et 9.3 °C et 0.5 mm de pluie prévus. | |
| TER-05 | 1 | quel météo en Belgique ? | Tu parles de quelle ville en Belgique, Emmanuel ? | |
| TER-06 | 1 | est ce que je peux obtenir la météo d'une autre région ? | De quelle ville tu parles, Emmanuel ? | |
| TER-07 | 1 | quel est la date ? | 2026-11-03, Emmanuel ! | |
| TER-08 | 1 | que sais-tu sur moi ? | J’ai dans mon carnet que tu veux une autonomie en tomate, que tu arroses tes salades le matin et le reste le soir, que tu utilises toujours de l’engrais bio, et que ton objectif pour 2027 est de 400 kg de récoltes. | |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | Ton objectif pour 2026 n'est pas enregistré dans le carnet, Emmanuel. Tu m'avais parlé d'autonomie en tomate pour 2027, mais rien pour cette année. Tu veux que je note un objectif 2026 ? | |
| TER-10 | 1 | quels sont mes notes ? | Je te propose d'afficher tes notes du carnet. Tu confirmes ? | |
| TER-11 | 1 | quand dois je arroser mes tomates ? | Avec les averses légères d'aujourd'hui et ton arrosage du soir, Emmanuel, tu risques de trop gaver tes tomates. Tâte la terre au pied avant d'arroser : si elle est encore humide, saute la session. Sinon, un petit coup au pied, sans mouiller les feuilles, et tu gardes tes fruits bien dodus sans les faire éclater. Source : Conduite et récolte de la tomate. | |
| TER-12 | 1 | pour mon objectif d'autonomie, que dois je privilégie ? | Pour viser ton objectif d'autonomie en tomate, Emmanuel, privilégie d'abord la **qualité de la récolte** : cueille tes tomates quand elles ont pris leur couleur et s'assouplissent légèrement sous une pression douce, sans attendre qu'elles ne ramollissent ou ne se fendent. Un fruit cueilli à point continue de mûrir après la récolte, mais un fruit vert et dur mûrit mal.  Ensuite, **stocke-les correctement** : étale-les en une seule couche, à l'abri du soleil et de l'humidité, pour éviter qu'elles ne pourrissent ou ne perdent leur arôme. La source est *Conduite et récolte de la tomate*. | |
| TER-13 | 1 | est ce que je peux semer des tomates ce week-end ? | Pas de chance, Emmanuel, la tomate en pleine terre en ce moment, c'est comme offrir un pull en plein été : ça va pas tenir la route ! Les prévisions annoncent des températures qui descendent sous les 5°C la nuit et un temps couvert, avec même un peu de pluie légère demain.  D'après ce que je trouve, semer des tomates maintenant, ça donne des plants tout maigres et fragiles, même sous abri. Si tu veux vraiment anticiper la saison prochaine, mieux vaut attendre le printemps et préparer tes graines au chaud dès février. Tu veux que je te rappelle ça pour l'an prochain ? Source : Problèmes observables de la tomate. | |
| TER-14 | 1 | mes cultures en pépinière ? | T’as trois lots en pépinière : des courgettes et des tomates (jaune et coeur de boeuf) sous serre, et des cornichons aussi sous serre. Les haricots sont en lot mais pas encore semés. | |
| TER-15 | 1 | liste tout ce que j'ai fais aujourd'hui | Rien de noté pour aujourd'hui, Emmanuel ! Si tu as arrosé ou fait autre chose, je peux l'ajouter. | |
| TER-16 | 1 | que dois je faire ? | Rien de fiable pour novembre, Emmanuel ! Mais si tu veux, on peut regarder comment sécher et garder ton ail après l'arrachage, ou pourquoi tes poivrons perdent leurs fleurs. Dis-moi ! | |
| TER-17 | 1 | Bonsoir | Bonsoir Emmanuel ! Alors, ce potager qui te fait courir après les 400 kg en 2027, tu veux en parler ce soir ? | |
| TER-17 | 2 | En effet , quoi de neuf ? | Pas grand-chose sous la flotte, Emmanuel ! Les averses légères de ce soir vont peut-être calmer tes radis et tes haricots, mais attention à ne pas noyer tes salades demain matin avec ton arrosage habituel. Tu veux qu’on parle de tes tomates ou de tes objectifs pour 2027 ? | |
| TER-18 | 1 | bonjour | Salut Emmanuel ! Alors, on attaque la journée au potager malgré les averses ? | |
| TER-18 | 2 | oui je suis prêt et que puis je faire aujourd'hui alors ? | Aujourd’hui, avec ces averses et ces températures fraîches, y a pas grand-chose à faire en extérieur, mais on peut préparer la suite ! Tu veux qu’on jette un œil à tes tomates ou à tes prochains semis ? | |
| TER-19 | 1 | bonsoir, quel est ton nom ? | Bonsoir Emmanuel ! Je suis ton Assistant Potager, ton carnet de bord pour tout ce qui pousse. | |
| TER-19 | 2 | Merci. | Avec plaisir, Emmanuel ! Tu veux qu’on parle de tes tomates ou d’autre chose qui pousse ? | |
| TER-20 | 1 | Laissez le micro. | Micro coupé, Emmanuel ! Tu peux me parler sans que je te réponde à voix haute. | |
| TER-21 | 1 | Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord, puis une parcelle sud, puis une parcelle ouest, et enfin tu termines par la création d'une parcelle est. | J’ai proposé de créer les parcelles **nord**, **sud** et **ouest** — l’**est** existe déjà, je ne la recrée pas. À toi de confirmer ! | |
| TER-22 | 1 | créé moi une parcelle nord et une parcelle sud | J’ai préparé deux nouvelles parcelles : **Nord** et **Sud**. À toi de confirmer ! | |
| TER-23 | 1 | Est-ce que tu peux renommer la parcelle tunnel en serre chaude ? | J’ai proposé de renommer **tunnel** en **serre chaude** — à toi de confirmer ! | |
| TER-24 | 1 | Mets la serre en pépinière chaude et le tunnel en pépinière froide. | Je te propose de basculer la serre en pépinière chaude et le tunnel en pépinière froide. | |
| TER-26 | 1 | Le sol de ma serre est argileux. | Pour un sol argileux en serre, il faut aérer la terre en profondeur avec une fourche-bêche sans la retourner, et ajouter des matières organiques bien décomposées comme du compost ou du fumier vieilli. Tu peux aussi planter des engrais verts comme la phacélie ou le seigle pour casser la compacité et améliorer le drainage. Source : Problèmes observables de la tomate. | |
| TER-27 | 1 | passe la planche principal à 2 rangs | J’ai proposé de passer la planche **principal** à 2 rangs. À toi de confirmer ! | |
| TER-27 | 2 | non 4 rangs | Proposition : passer la planche **principal** à **4 rangs**. | |
| TER-29 | 1 | Supprime la planche | Tu as dit "planche", mais il y a deux parcelles avec ce mot : **plant tubercule** ou **planche test** ? Laquelle veux-tu supprimer, Emmanuel ? | |
| TER-29 | 2 | la planche test | C'est la planche test, 10 m² avec 5 rangs, toujours en service. Tu veux la supprimer ou la modifier, Emmanuel ? | |
| TER-30 | 1 | Rappelle moi l'événement demain matin | J’ai programmé un rappel pour demain matin sur l’événement, Emmanuel. Tu le verras sur la carte ! | |
| TER-30 | 2 | Oui je veux bien | Ah, je me suis emmêlé les pinceaux ! C’est l’identifiant **"programmer événement demain matin demain"** qui compte, pas l’autre. Je relance la proposition avec le bon identifiant. | |
| TER-31 | 2 | oui | Salut Emmanuel ! T’as un projet pour ton potager ou tu veux juste papoter ? | |
| TER-32 | 1 | Oups, excuse-moi, supprime la dernière commande. | Pas de souci, Emmanuel ! Je l'annule direct. | |
| TER-33 | 1 | vider mon carnet | J’ai préparé l’affichage de ton carnet pour que tu puisses le vider. Dis-moi si tu veux que je te le montre ! | |
| TER-34 | 1 | je veux utiliser de l'engrais chimique pour mes tomates | Ton carnet note que tu utilises toujours de l'engrais bio pour tes cultures, Emmanuel. Si tu veux tester un engrais chimique, je peux chercher des infos sur les différences de résultats ou les risques pour tes tomates. Tu veux que je creuse ? Source : Conduite et récolte de la tomate. | |
| TER-35 | 1 | objectif autonomie en tomate | Une tomate prête a pris la couleur attendue pour sa variété et s'assouplit très légèrement sous une pression douce ; elle se détache sans traction brutale. Source : Conduite et récolte de la tomate. | |

## Tours à relire — `mistral/mistral-small-2603`

| Dialogue | Tour | Phrase | Chemin | Attendu | Obtenu du modèle | Vu par le jardinier | Couperets (modèle) | Couperets (jardinier) |
|---|---:|---|---|---|---|---|---|---|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | agent | texte / consulter_donnees | `consulter_donnees({"question": "ce que je viens de noter"})` | « Je n’ai pas encore de note récente de toi, Emmanuel. Tu veux que je t’aide à en ajouter une ? » | — | — |
| TER-02 | 1 | c'est quoi la dernière action notée | agent | texte / consulter_donnees | `[ok]` | « La dernière action notée, c'est la création de la parcelle **Sud** il y a 4 jours. » | — | — |
| TER-04 | 1 | Quelle météo sur Lyon ? | agent | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | `[ok]` | « Pour Lyon, Auvergne-Rhône-Alpes, France : aujourd'hui, Couvert, de 5.4 à 10.3 °C, 0.0 mm de pluie prévus. » | — | — |
| TER-04 | 2 | et demain ? | agent | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | `[ok]` | « Demain sur ton potager, Emmanuel, c'est encore des averses légères avec des températures entre 5.7 et 9.3 °C et 0.5 mm de pluie prévus. » | — | — |
| TER-07 | 1 | quel est la date ? | agent | texte | `[ok]` | « 2026-11-03, Emmanuel ! » | — | — |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | agent | texte / afficher | `[ok]` | « Ton objectif pour 2026 n'est pas enregistré dans le carnet, Emmanuel. Tu m'avais parlé d'autonomie en tomate pour 2027, mais rien pour cette année. Tu veux que je note un objectif 2026 ? » | — | promesse_sans_proposition |
| TER-13 | 1 | est ce que je peux semer des tomates ce week-end ? | agent | chercher_connaissance / afficher / consulter_donnees / texte | `confiance({"commande": "confiance", "action": "semis_pleine_terre", "culture": "tomate"}) + chercher_connaissance({"question": "semer tomate en pleine terre en automne", "domaine": "jardinage"})` | « Pas de chance, Emmanuel, la tomate en pleine terre en ce moment, c'est comme offrir un pull en plein été : ça va pas tenir la route ! Les prévisions annoncent des températures qui descendent sous les 5°C la nuit et un temps couvert, avec même un peu de pluie légère demain.  D'après ce que je trouve, semer des tomates maintenant, ça donne des plants tout maigres et fragiles, même sous abri. Si tu veux vraiment anticiper la saison prochaine, mieux vaut attendre le printemps et préparer tes graines au chaud dès février. Tu veux que je te rappelle ça pour l'an prochain ? Source : Problèmes observables de la tomate. » | ecriture_sans_attente | promesse_sans_proposition |
| TER-16 | 1 | que dois je faire ? | agent | texte / consulter_donnees / afficher / chercher_connaissance | `chercher_connaissance({"question": "que faire au potager en novembre", "domaine": "jardinage"})` | « Rien de fiable pour novembre, Emmanuel ! Mais si tu veux, on peut regarder comment sécher et garder ton ail après l'arrachage, ou pourquoi tes poivrons perdent leurs fleurs. Dis-moi ! » | — | — |
| TER-25 | 1 | ma serre est une pépinière tiède | agent | texte | `modifier_parcelle({"parcelle": "serre", "est_pepiniere": true, "type_pepiniere": "chaude"})` | (récapitulatif seul) + /parcelle modifier serre pepiniere=oui | — | — |
| TER-26 | 1 | Le sol de ma serre est argileux. | agent | modifier_parcelle `{'parcelle': 'serre', 'type_sol': 'argileux'}` | `[ok]` | « Pour un sol argileux en serre, il faut aérer la terre en profondeur avec une fourche-bêche sans la retourner, et ajouter des matières organiques bien décomposées comme du compost ou du fumier vieilli. Tu peux aussi planter des engrais verts comme la phacélie ou le seigle pour casser la compacité et améliorer le drainage. Source : Problèmes observables de la tomate. » | — | — |
| TER-29 | 1 | Supprime la planche | agent | texte | `supprimer_parcelle({"nom": "planche"})` | « Tu as dit "planche", mais il y a deux parcelles avec ce mot : **plant tubercule** ou **planche test** ? Laquelle veux-tu supprimer, Emmanuel ? » | ecriture_sans_attente, destruction_erronee | — |
| TER-29 | 2 | la planche test | agent | supprimer_parcelle `{'nom': 'planche test'}` | `[ok]` | « C'est la planche test, 10 m² avec 5 rangs, toujours en service. Tu veux la supprimer ou la modifier, Emmanuel ? » | — | — |
| TER-31 | 1 | vide le geste | agent | texte / afficher | `saisir_geste({})` | geste | ecriture_sans_attente | ecriture_sans_attente |
| TER-31 | 2 | oui | agent | texte / afficher | `[ok]` | « Salut Emmanuel ! T’as un projet pour ton potager ou tu veux juste papoter ? » | — | salut_en_cours |
| TER-34 | 1 | je veux utiliser de l'engrais chimique pour mes tomates | agent | texte / chercher_connaissance | `chercher_connaissance({"question": "engrais chimique pour tomates", "domaine": "jardinage"}) + chercher_connaissance({"question": "engrais chimique pour tomates", "domaine": "jardinage"}) + chercher_connaissance({"question": "engrais chimique pour tomates", "domaine": "jardinage"}) + chercher_connaissance({"question": "engrais chimique pour tomates", "domaine": "jardinage"})` | « Ton carnet note que tu utilises toujours de l'engrais bio pour tes cultures, Emmanuel. Si tu veux tester un engrais chimique, je peux chercher des infos sur les différences de résultats ou les risques pour tes tomates. Tu veux que je creuse ? Source : Conduite et récolte de la tomate. » | — | promesse_sans_proposition |
