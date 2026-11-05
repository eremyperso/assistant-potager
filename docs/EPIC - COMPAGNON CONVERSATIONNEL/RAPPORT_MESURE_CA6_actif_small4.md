# Agent d'abord — corpus `terrain_compagnon_2026_11`, cascade `actif`

*Généré par `tools/evaluer_dialogues.py` le 2026-11-02. Référence : `mistral/mistral-small-2603`. Clé de mesure distincte de celle du bot : oui. Rejoué par la cascade du bot (`interpreter`, mode `actif`) : règles, garde de savoir, filtre des gestes, puis l'agent. Prompt et catalogue livrés, données réelles du potager 33 en lecture seule, aucune écriture exécutée.*

43 tours joués, dont 0 qui exigent une brique pas encore livrée (outil ou mémoire) : ils sont mesurés et listés, mais exclus des taux du catalogue livré.

**Chemin en production** : 19 par agent, 6 par règles, 1 par parseur de gestes, 1 par garde de savoir, 16 par cascade des questions. Les 24 tours que la cascade prend avant l'agent ne jugent pas le modèle : ils sont exclus des taux, mais leurs couperets au jardinier comptent.

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
| texte qui demande une confirmation sans proposition à confirmer | 0 |
| conversation reprise à zéro (salut en plein dialogue) | 1 |

*0 écriture exécutée sans confirmation* tient par construction : la mesure n'exécute rien.

## Couperets du modèle (§12.10, tendance)

Ce que le modèle propose, avant que le validateur et la cascade ne tranchent.

| Couperet | `mistral-small-2603` |
|---|---:|
| écriture proposée là où il n'en fallait aucune | 2 |
| outil interdit appelé (ex. un second geste sur une correction) | 0 |
| suppression non demandée | 1 |
| texte qui annonce une action non exécutée | 0 |
| texte interdit (dose, produit, fait accompli) | 0 |

**Verdict de la référence : au jardinier, 2 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 1, conversation reprise à zéro (salut en plein dialogue) : 1. Côté modèle, 3 couperet(s) franchi(s) — écriture proposée là où il n'en fallait aucune : 2, outil interdit appelé (ex. un second geste sur une correction) : 0, suppression non demandée : 1, texte qui annonce une action non exécutée : 0, texte interdit (dose, produit, fait accompli) : 0.**

## Par catégorie — `mistral/mistral-small-2603`

| Catégorie | Tours | Hors agent | Bon outil | Bons paramètres | Sans couperet (modèle) | Réponses justes | Couperets au jardinier | p50 | p95 | Jetons/msg | Lecture |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Créations | 3 | 2 | 1/1 (100 %) | — | 3/3 (100 %) | — | 0 | 1417 ms | 1417 ms | 3588 | ✅ tient |
| Plusieurs actions dans une phrase | 2 | 0 | 2/2 (100 %) | — | 2/2 (100 %) | — | 0 | 1025 ms | 1162 ms | 10544 | ✅ tient |
| Négations et retraits | 3 | 1 | 2/2 (100 %) | 1/1 (100 %) | 3/3 (100 %) | — | 0 | 641 ms | 1261 ms | 5713 | ✅ tient |
| Questions sur les données et le savoir | 16 | 15 | 1/1 (100 %) | — | 16/16 (100 %) | 1/1 (100 %) | 0 | 1253 ms | 1253 ms | 825 | ✅ tient |
| Doutes | 6 | 1 | 2/5 (40 %) | 0/1 (0 %) | 4/6 (67 %) | — | 2 | 1259 ms | 1303 ms | 7278 | ❌ en échec |
| Conversation simple | 7 | 3 | 4/4 (100 %) | — | 7/7 (100 %) | — | 0 | 536 ms | 869 ms | 2972 | ✅ tient |
| Hors catalogue | 1 | 0 | 1/1 (100 %) | — | 1/1 (100 %) | — | 0 | 1113 ms | 1113 ms | 10388 | ✅ tient |
| Registres et prénom | 3 | 1 | 2/2 (100 %) | — | 3/3 (100 %) | — | 0 | 601 ms | 729 ms | 3464 | ✅ tient |
| Caractéristiques d'une parcelle | 2 | 1 | 1/1 (100 %) | 1/1 (100 %) | 2/2 (100 %) | — | 0 | 1765 ms | 1765 ms | 7912 | ✅ tient |
| **Total** | 43 | 24 | **16/19 (84 %)** | **2/3 (67 %)** | **41/43 (95 %)** | **1/1 (100 %)** | **2** | 1025 ms | 1765 ms | 3797 | |

*Bon outil* et *bons paramètres* ne portent que sur les tours dont la brique est livrée et que la cascade confie à l'agent ; un paramètre ajouté que le jardinier n'a pas dit est compté faux. *Réponses justes* : parmi les questions qui portent un texte attendu, celles dont le texte lu contient l'une des expressions. Seuil d'une catégorie « qui tient » : 90 %, aucun couperet du modèle et aucun couperet au jardinier.

## Que faire des catégories qui ne tiennent pas ? (allègement d'abord)

### Doutes — ❌ en échec

1. **Allègement d'abord** : Catalogue projeté selon l'état + verdict du validateur. Le validateur rend le doute avec les choix réels (« Nord, Sud ou Est ? ») ; le modèle ne les devine pas.
2. **Modèle ensuite** : aucun des modèles comparés ne tient cette catégorie dans cette mesure ; le choix d'un modèle ne suffirait pas.

## Grille tarifaire et cache de prompt

Grille du 2026-11-01 — source : grille fournie par le jardinier le 01/11/2026. Confirmée.

| Modèle | Entrée ($/M jetons) | Sortie ($/M jetons) | Jetons d'entrée mesurés | Servis par le cache |
|---|---:|---:|---:|---:|
| `mistral/mistral-small-2603` | 0.15 | 0.6 | 162397 | 123792 (76 %) |

Cache : entrée en cache, USD par million : Ministral 3B 0,01 ; 8B 0,015 ; 14B 0,02 ; Small 4 0,015. Le coût mensuel ci-dessous la compte au plein tarif : c'est un plafond. Dans la colonne ci-dessus, 0 % signifie que l'API ne renvoie pas (ou pas encore) de jetons en cache dans `usage.prompt_tokens_details` : le préfixe fixe (prompt + catalogue) est alors facturé plein tarif à chaque appel.

## Naturel — les textes de l'agent, à noter de 1 à 3 — `mistral/mistral-small-2603`

Critère du lot 1 : ≥ 2,5/3 sur 30 dialogues relus (1 « figé », 2 « correct », 3 « naturel »). 17 texte(s) dans cette mesure. La note est humaine : la colonne est à remplir.

| Dialogue | Tour | Phrase | Texte lu par le jardinier | Note |
|---|---:|---|---|---:|
| TER-15 | 1 | liste tout ce que j'ai fais aujourd'hui | Aujourd'hui, je n’ai rien enregistré de nouveau dans ton potager, Emmanuel ! Si tu as fait des gestes manuels, je peux les noter pour toi. | |
| TER-17 | 1 | Bonsoir | Bonsoir Emmanuel ! Tu veux qu’on parle de ton potager ou de tes tomates ? | |
| TER-18 | 1 | bonjour | Salut Emmanuel ! Prêt à bricoler ton potager aujourd'hui ? | |
| TER-19 | 2 | Merci. | Avec plaisir, Emmanuel ! Tu veux qu’on parle de tes tomates ou d’autre chose ce soir ? | |
| TER-20 | 1 | Laissez le micro. | Les réponses vocales sont activées, Emmanuel ! Dis-moi ce que tu veux faire au potager. | |
| TER-21 | 1 | Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord, puis une parcelle sud, puis une parcelle ouest, et enfin tu termines par la création d'une parcelle est. | J’ai préparé la création de tes quatre parcelles : nord, sud, ouest et est, chacune avec son exposition. À toi de confirmer ! | |
| TER-22 | 1 | créé moi une parcelle nord et une parcelle sud | J’ai préparé la création des parcelles **Nord** et **Sud** pour toi, Emmanuel. À toi de confirmer ! | |
| TER-24 | 1 | Mets la serre en pépinière chaude et le tunnel en pépinière froide. | J’ai proposé de transformer la serre en pépinière chaude et le tunnel en pépinière froide. À toi de confirmer ! | |
| TER-27 | 2 | non 4 rangs | Je te propose de passer la planche **principal** à **4 rangs**. Tu me dis ? | |
| TER-29 | 1 | Supprime la planche | Tu as dit "planche", mais il y a deux parcelles avec ce mot : **plant tubercule** et **planche test**. Laquelle veux-tu supprimer ? | |
| TER-29 | 2 | la planche test | Ah, la planche test ! Une belle planche de 10 m², bien active. Tu veux en faire quoi, Emmanuel ? | |
| TER-30 | 2 | Oui je veux bien | Ah, je me suis emmêlé les pinceaux ! Le rappel est toujours en attente, dis-moi simplement « oui » pour le valider. | |
| TER-31 | 2 | oui | Salut Emmanuel ! Tu veux qu’on parle de ton potager ou de tes cultures ? | |
| TER-32 | 1 | Oups, excuse-moi, supprime la dernière commande. | Pas de souci, Emmanuel ! Je n’ai rien fait, c’est bon. | |
| TER-33 | 1 | vider mon carnet | Je te propose d'afficher ton carnet pour que tu puisses le vider toi-même. Tu confirmes ? | |
| TER-34 | 1 | je veux utiliser de l'engrais chimique pour mes tomates | Ah, Emmanuel, tu veux peut-être tester autre chose, mais avec ton objectif d'autonomie en tomates, l'engrais bio reste le plus cohérent ! Tu veux en parler avec /ask ? | |
| TER-35 | 1 | objectif autonomie en tomate | Je te propose de retenir ça dans ton carnet. | |

## Tours à relire — `mistral/mistral-small-2603`

| Dialogue | Tour | Phrase | Chemin | Attendu | Obtenu du modèle | Vu par le jardinier | Couperets (modèle) | Couperets (jardinier) |
|---|---:|---|---|---|---|---|---|---|
| TER-01 | 1 | ce que je viens de noter , c'était quoi ? | cascade des questions | texte / consulter_donnees | — | question | — | — |
| TER-02 | 1 | c'est quoi la dernière action notée | garde de savoir | texte / consulter_donnees | — | réponse de savoir | — | — |
| TER-03 | 1 | quel est mon dernier semis ? | cascade des questions | consulter_donnees / texte | — | question | — | — |
| TER-04 | 1 | Quelle météo sur Lyon ? | règles | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | — | /meteo Lyon | — | — |
| TER-04 | 2 | et demain ? | cascade des questions | afficher `{'commande': 'meteo', 'lieu': 'lyon'}` | — | question | — | — |
| TER-05 | 1 | quel météo en Belgique ? | cascade des questions | afficher / texte | — | question | — | — |
| TER-06 | 1 | est ce que je peux obtenir la météo d'une autre région ? | cascade des questions | texte / chercher_connaissance / afficher | — | question | — | — |
| TER-07 | 1 | quel est la date ? | cascade des questions | texte | — | question | — | — |
| TER-08 | 1 | que sais-tu sur moi ? | cascade des questions | texte / afficher | — | question | — | — |
| TER-09 | 1 | rappel moi quel a été mon objectif cette année ? | cascade des questions | texte / afficher | — | question | — | — |
| TER-10 | 1 | quels sont mes notes ? | cascade des questions | afficher / consulter_donnees / texte | — | question | — | — |
| TER-11 | 1 | quand dois je arroser mes tomates ? | cascade des questions | chercher_connaissance / consulter_donnees / texte | — | question | — | — |
| TER-12 | 1 | pour mon objectif d'autonomie, que dois je privilégie ? | cascade des questions | chercher_connaissance / consulter_donnees / texte | — | question | — | — |
| TER-13 | 1 | est ce que je peux semer des tomates ce week-end ? | règles | chercher_connaissance / afficher / consulter_donnees / texte | — | /confiance tomates semis 2026-11-07 | — | — |
| TER-14 | 1 | mes cultures en pépinière ? | cascade des questions | consulter_donnees / afficher / texte | — | question | — | — |
| TER-16 | 1 | que dois je faire ? | cascade des questions | texte / consulter_donnees / afficher / chercher_connaissance | — | question | — | — |
| TER-17 | 2 | En effet , quoi de neuf ? | cascade des questions | texte / consulter_donnees / afficher / meteo | — | question | — | — |
| TER-18 | 2 | oui je suis prêt et que puis je faire aujourd'hui alors ? | cascade des questions | texte / consulter_donnees / afficher / chercher_connaissance | — | question | — | — |
| TER-19 | 1 | bonsoir, quel est ton nom ? | cascade des questions | texte | — | question | — | — |
| TER-23 | 1 | Est-ce que tu peux renommer la parcelle tunnel en serre chaude ? | règles | renommer_parcelle `{'ancien': 'tunnel', 'nouveau': 'serre chaude'}` | — | /parcelle renommer tunnel serre chaude | — | — |
| TER-25 | 1 | ma serre est une pépinière tiède | règles | texte | — | /parcelle modifier serre pepiniere=oui | — | — |
| TER-27 | 1 | passe la planche principal à 2 rangs | règles | modifier_parcelle `{'parcelle': 'principal', 'nb_rangs': 2}` | — | /parcelle modifier passe la planche principal rangs=2 | — | — |
| TER-28 | 1 | j'ai arrosé la planche principal ce soir | parseur de gestes | saisir_geste | — | parseur de gestes | — | — |
| TER-29 | 1 | Supprime la planche | agent | texte | `supprimer_parcelle({"nom": "planche"})` | « Tu as dit "planche", mais il y a deux parcelles avec ce mot : **plant tubercule** et **planche test**. Laquelle veux-tu supprimer ? » | ecriture_sans_attente, destruction_erronee | — |
| TER-29 | 2 | la planche test | agent | supprimer_parcelle `{'nom': 'planche test'}` | `[ok]` | « Ah, la planche test ! Une belle planche de 10 m², bien active. Tu veux en faire quoi, Emmanuel ? » | — | — |
| TER-30 | 1 | Rappelle moi l'événement demain matin | règles | programmer_rappel / texte | — | /rappel programmer l'événement matin 2026-11-03 | — | — |
| TER-31 | 1 | vide le geste | agent | texte / afficher | `saisir_geste({})` | geste | ecriture_sans_attente | ecriture_sans_attente |
| TER-31 | 2 | oui | agent | texte / afficher | `[ok]` | « Salut Emmanuel ! Tu veux qu’on parle de ton potager ou de tes cultures ? » | — | salut_en_cours |
