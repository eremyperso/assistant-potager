# Référence humaine — B01 « Planter une salade qui n'est pas au potager »

Session du 18/11/2026, PWA locale (API 8011, base `potager_test`, potager neuf 37, fiches US-348 ingérées),
jouée par le jardinier lui-même. Source : `echanges_conversation`, échanges 248 à 251. Chaîne : actuelle, Mistral Small 4.

| # | Jardinier | Réponse du compagnon | Verdict humain | Motif |
|---|---|---|---|---|
| 248 | salut, dis-moi, est ce que je peux planter des salades en ce moment ? | « …pas en plantation directe en ce moment, il fait trop froid » | **faux** (nuance : il dit « trop froid ») | Il ne peut pas le savoir sans lire la météo : aucun outil météo ni calendrier appelé |
| 249 | dis moi quand c'est possible ? | « …au-dessus de 5°C la nuit » | **faux** | Chiffre inventé (aucune fiche ne le porte) |
| 250 | et pour planter mes pieds de salades en intérieur je dois le faire comment ? | cycle semis → godet → mise en place, source citée | **vrai** | — |
| 251 | pourquoi tu me proposes pas d'utiliser ou d'installer une serre chauffé ? | passage sur le collet au niveau du sol | **faux** | Ne répond pas à la question |

## Ce que ça révèle (à confirmer par la mesure)

1. **Affirmation sans donnée** (#248) : une conclusion de saison/température sans appel à la météo ni au calendrier.
2. **Chiffre inventé** (#249) : le critère automatique « rien d'inventé » n'a rien relevé sur le dialogue rejoué du 14/11.
   À vérifier : un tel chiffre échappe-t-il au contrôle du code ?
3. **Passage hors-propos** (#251) : le texte d'une fiche est resservi sans lien avec la question posée.
4. Ce qui tient : la conduite de la salade, quand la question la vise exactement (#250).

## Bonne réponse attendue (dite par le jardinier, 18/11/2026)

À « est-ce que je peux planter des salades en ce moment ? », le compagnon doit :

1. **lire la météo** du potager ;
2. **vérifier les périodes conseillées** dans le calendrier de la salade ;
3. **croiser les deux** pour donner la réponse la plus adaptée, en **précisant les risques de planter aujourd'hui** ;
4. **proposer la serre chauffée** si le jardinier en dispose ; **sinon, dire ce qu'il fera à la place** ;
5. **proposer la prochaine fenêtre la plus favorable**.

### Ce qui se vérifie par le code (critères traduits)

| Élément attendu | Contrôle possible |
|---|---|
| lecture de la météo | l'outil météo (ou la capacité équivalente) est appelé dans le tour |
| lecture du calendrier | la capacité de calendrier / `situation_culture` est appelée |
| aucun chiffre hors données | tout chiffre cité vient de la météo, du calendrier ou d'une fiche |
| risque dit | le texte nomme un risque (froid, gel, reprise) |
| serre | le plan du potager est lu ; la proposition dépend de la présence d'une pépinière chaude |
| prochaine fenêtre | une période est donnée, issue du calendrier |

### Dépendances

- **US-339** (`situation_culture`) : le verdict de saison et la prochaine fenêtre.
- **US-340** : la liste de ce qu'il y a à faire.
- **US-349** : la fenêtre de **plantation** de la salade n'est pas dans le référentiel ; sans elle, les points 2 et 5 ne peuvent
  pas être tenus.

---

## Variante « fiche complète » : la tomate (même question, même jour)

Session du 18/11/2026 à 17:15, même onglet, **sans remise à zéro** entre la salade et la tomate (l'historique de 30 minutes contenait
encore la conversation sur la salade : essai non propre). Échanges 252 à 255. Données de la tomate en océanique : semis en pépinière
février-mars, plantation mai, récolte juillet-septembre, plein soleil, besoin en eau élevé.

| # | Jardinier | Réponse du compagnon | Verdict humain | Motif |
|---|---|---|---|---|
| 252 | est ce que je peux planter des pieds de tomates en ce moment dans mon potager ? | « Non, pas en ce moment, les températures sont trop basses… attends le printemps » | **peut passer** | Juste en novembre, mais ni météo ni calendrier lus : s'il répond la même chose en été, c'est faux |
| 253 | si je veux planter des pieds de tomate et pas semer, tu me proposes quoi ? | « attendre le printemps… préparer tes plants en intérieur » | **faux** (pas assez précis) | Il aurait dû ressortir le calendrier (plantation en mai) |
| 254 | je dispose d'une serre chauffé, est ce possible alors ? | « Oui, tu peux planter tes **salades** maintenant ! » | **faux** | Le contexte est perdu : la tomate est devenue salade |
| 255 | tu ne me proposes pas de les ajouter dans ma serre chauffé ? | « …installer tes **salades** en serre chauffée ? Je regarde ça. » | **faux** | Même perte de contexte, et « je regarde ça » sans aucun outil appelé |

### Ce que ça ajoute

1. **Même avec des données complètes, il ne lit pas le calendrier** (#252, #253) : le problème n'est pas seulement le référentiel vide
   de la salade, c'est que la capacité de calendrier n'est pas appelée.
2. **Perte du fil** (#254, #255) : le sujet change de culture au milieu de la conversation. À confirmer sur une trace propre,
   car l'historique contenait la salade.
3. **Test miroir à créer** : la réponse doit **dépendre de la date**. La même phrase posée à la bonne saison (mai) doit donner un
   « oui » ; poser la même question un jour de novembre et un jour de mai, et exiger deux réponses différentes.
4. **Promesse sans action** : « je regarde ça » sans appel d'outil.

### Protocole : remettre le potager neuf à zéro entre deux scénarios

`python tools/creer_potager_test_neuf.py` vide les échanges ; sans cela l'historique glissant fausse le scénario suivant.

---

## Tomate, trace propre (potager neuf remis à zéro avant la session)

Session du 18/11/2026 à 17:22. Échanges 256 à 260. Aucun historique d'un autre scénario : la dérive vers la salade a disparu,
elle venait donc de l'historique mélangé.

| # | Jardinier | Réponse du compagnon | Outils appelés | Verdict humain | Motif |
|---|---|---|---|---|---|
| 256 | salut, est-ce que je peux planter des pieds de tomates en ce moment ? | « Pas maintenant… au printemps quand les gelées sont passées. Je te rappelle ? » | confiance, chercher_connaissance, meteo | **pas précis** | Les outils sont appelés mais rien n'en ressort : ni date de plantation, ni température, ni risque |
| 257 | si je veux planter des pieds et pas semer, tu me proposes quoi ? | « Attends le printemps… prépare la planche, ajoute du compost » | chercher_connaissance | **faux** | Pas de calendrier ; un conseil de préparation hors sujet |
| 258 | je dispose d'une serre chauffée, est-ce possible alors ? | « Oui, tu peux planter en ce moment, surveille la lumière et la température » | chercher_connaissance | **faux** | Le plan du potager n'est pas lu ; le conseil vient de la fiche *Problèmes* |
| 259 | tu ne me proposes pas de les ajouter dans ma serre chauffée ? | « Tu as déjà une serre chauffée dans tes parcelles ? » | creer_parcelle | **faux** | Il redemande ce que le jardinier vient de dire et ne lit pas ses parcelles |
| 260 | non | « Tu ne veux plus parler de tes pieds de tomates ? » | — | **faux** | Le « non » répond à sa propre question ; il perd le fil |

### Comportement attendu au tour 259 (dit par le jardinier)

Le compagnon est le mieux placé pour savoir si une serre chauffée est déclarée : il **lit le plan** et répond, par exemple
« Je vois que tu n'as pas de serre chauffée dans ton potager. Veux-tu la déclarer ? ». Il ne demande jamais au jardinier ce
que le potager lui dit déjà.

### Constat du jardinier

Hors le premier tour, la réponse est celle d'un LLM seul : aucune consultation des caractéristiques du potager, de la météo ni
du calendrier ; seule la recherche dans les fiches d'agronomie est faite, quand des mots-clés s'y trouvent. Le texte de la
réponse n'utilise pas les résultats des outils appelés au tour 256.

### Critères tirés des deux sessions (salade et tomate)

| Critère | Observé |
|---|---|
| Le plan du potager est lu avant de poser une question sur ce qu'il contient | jamais (#258, #259) |
| Un résultat d'outil appelé se retrouve dans le texte (date, température, fenêtre) | non (#256) |
| Aucun chiffre qui ne vienne ni d'un outil ni d'une fiche | violé (« 5°C », B01 #249) |
| La réponse change avec la date (même phrase en mai et en novembre) | non testé, à créer |
| Le sujet de la conversation (la culture) tient d'un tour à l'autre | oui sur trace propre, non avec historique mélangé |
| Une réponse oui/non du jardinier est comprise comme réponse à la question posée | non (#260) |
| Aucune promesse « je regarde ça » sans appel d'outil | violé (#255) |

---

## B05 — « Savoir si c'est le moment pour une culture » (radis), trace propre

Session du 18/11/2026 à 17:30, potager neuf remis à zéro avant. Échanges 261 à 265. Référentiel du radis en océanique :
semis en pleine terre mars à mai, récolte mai à novembre. Une seule formulation jouée, puis dérive vers les parcelles.

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain | Motif |
|---|---|---|---|---|---|
| 261 | salut, je veux semer des radis ce WE, c'est bon pour toi ? | « Le radis se sème bien en novembre… À **Lyon**, les températures restent douces… » | chercher_connaissance, meteo ×2 | **faux** | Il parle d'une ville qui n'a aucun lien avec le potager |
| 262 | oui | « La parcelle existe déjà, je ne peux pas la recréer. » | creer_parcelle | **faux** | Il se contredit |
| 263 | mais quelle parcelle alors ? | « Je vais te proposer une nouvelle parcelle pour tes radis. » | — | **faux** | Il ne dit pas que « planche légumes » existe |
| 264 | mais rappelle moi les parcelles dont je dispose ? | carte `/parcelle lister` | afficher | **faux** | Il propose une commande au lieu de lire le plan |
| 265 | oui je t'écoute | « Comment veux-tu appeler ta parcelle de radis ? » | creer_parcelle | **faux** | Il repart sur la création d'une parcelle |

### Constats

1. **Lieu inventé pour la météo** : le potager 37 n'a ni ville ni coordonnées (zone océanique seulement), et le compagnon cite Lyon.
   Piste à vérifier : la description de l'outil `meteo` (`app/services/agent/catalogue_outils.py`, ligne 834) donne « Lyon » comme
   exemple de la valeur du paramètre `ville` ; le modèle a pu recopier l'exemple. À confirmer sur les arguments réellement envoyés.
2. **Plan non lu** (déjà vu en B01) : la parcelle « planche légumes » existe, le compagnon propose d'en créer une autre.
3. **Verdict de saison non fondé sur le calendrier** (radis : semis mars-mai, pas novembre dans le référentiel), non tranché par le jardinier.

### À compléter

- La bonne réponse attendue à « je veux semer des radis ce WE, c'est bon pour toi ? » (non donnée pour l'instant).

### Bonne réponse attendue à B05 (dite par le jardinier, 18/11/2026)

- **Radis en novembre : non** (le référentiel donne le semis en pleine terre de mars à mai en océanique).
- La zone océanique du potager de test a été posée par `creer_potager_test_neuf.py` (copie du potager 34 de la mesure du 14/11),
  ce n'est pas une valeur par défaut du compagnon. En revanche **le potager n'a pas de ville** : sans localisation, la météo locale
  est impossible. Le compagnon doit le **dire** (« je n'ai pas de ville pour ton potager, je ne peux pas lire la météo ») et proposer
  de la renseigner, au lieu de citer une ville au hasard.
- Le verdict de saison, lui, se fonde sur la zone et le calendrier, sans avoir besoin de la météo.

---

## B20 — « Cultiver une culture sans fiche » (topinambour), trace propre

Session du 18/11/2026 à 21:40, potager neuf remis à zéro avant. Échanges 266 à 269. Aucune fiche de topinambour.

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain | Constat (à confirmer par le jardinier) |
|---|---|---|---|---|---|
| 266 | j'aimerai cultiver des topinambours | « Je n'ai pas encore de conseil fiable… Veux-tu que je te parle des concombres ? » | chercher_connaissance | **faux** | Dit l'absence de fiche (bon réflexe) ; propose une culture sans lien |
| 267 | non je veux cultiver la topinambour | `/parcelle ajouter topinambour` | chercher_connaissance, creer_parcelle | **faux** | « Cultiver » compris comme « créer une parcelle » |
| 268 | non pas la parcelle mais la culture | « De quelle culture veux-tu que je te parle ? » | — | **faux** | Redemande la culture déjà nommée deux fois |
| 269 | topinambour | `/parcelle ajouter topinambour` | chercher_connaissance, creer_parcelle | **faux** | Retombe sur la parcelle |

### Bonne réponse attendue à B20 (dite par le jardinier, 18/11/2026)

Ici « fiche culture » désigne la fiche du référentiel (`culture_config` et ses déclinaisons par zone), pas seulement les fiches de conseils.

1. Le compagnon **vérifie si la fiche culture existe pour la zone du potager**.
2. Si elle **existe pour une autre zone** : il le dit et **propose de la copier (dupliquer) pour la zone du potager**.
3. Il propose ensuite au jardinier de **compléter ou modifier** les informations de cette fiche.
4. Il propose alors de **l'ajouter en plantation**, comme demandé.
5. Si la fiche **n'existe dans aucune zone** : il propose de **créer la fiche** et demande au jardinier de **la compléter**, puis propose de l'ajouter en plantation.

### Ce qui se vérifie par le code

| Élément attendu | Contrôle possible |
|---|---|
| lecture du référentiel pour la zone | un outil/capacité de lecture de `culture_config` et de ses fenêtres est appelé |
| distinction « absente de cette zone » / « absente partout » | le texte dit laquelle, d'après les données |
| duplication proposée | une proposition de copie de fiche existe (capacité absente aujourd'hui) |
| création de fiche proposée | idem pour la création |
| pas de confusion culture / parcelle | aucune proposition `/parcelle ajouter` sur une demande de culture |
| pas de culture sans lien proposée | aucune autre culture offerte en remplacement non demandé |

### Constat sur l'existant

Le compagnon n'a ni capacité de duplication de fiche culture, ni de création de fiche : B20 demande donc une capacité nouvelle,
à rattacher à l'épic (US-338 registre, US-345 ou une US dédiée à créer).

---

## B04 — « Planter une culture en plants » (tomate), trace propre

Session du 18/11/2026 à 21:57 (une première tentative, effacée, avait été rejouée). Potager neuf remis à zéro avant. Échanges 272-273,
proposition 266 confirmée (canal pwa), événement 670 écrit.

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain | Motif |
|---|---|---|---|---|---|
| 272 | j'ai planté hier 5 plants de tomate, tu peux l'enregistrer | aiguillé vers geste | — | **vrai** | — |
| 273 | (même phrase) | proposition : plantation · tomate · 5 plants · 2026-11-17 | geste | **à moitié** | Culture, quantité, date (« hier ») justes ; **parcelle non demandée** |

Événement écrit : plantation, tomate, 5, 17/11/2026, `parcelle_id` **vide**.

### Bonne réponse attendue à B04 (dite par le jardinier, 18/11/2026)

- Le compagnon **demande sur quelle parcelle affecter la plantation**, au lieu de l'écrire sans parcelle.
- Constat du jardinier : **les cultures hors parcelle ne sont plus accessibles** dans l'application aujourd'hui ; une plantation
  sans parcelle devient donc invisible pour lui. (À vérifier à l'écran : cela rend l'oubli de parcelle grave, pas seulement incomplet.)

### Ce qui se vérifie par le code

| Élément attendu | Contrôle possible |
|---|---|
| parcelle demandée | la proposition d'une plantation sans parcelle déclenche une question, ou porte une parcelle lue dans le plan |
| rien d'écrit sans parcelle | aucun événement de plantation avec `parcelle_id` vide après confirmation |
| culture / quantité / date relative | la proposition porte tomate, 5, la date d'hier |
| écriture sûre | aucun événement avant confirmation |

Critère déjà couvert par le jeu : « écriture sûre ». Critère à **ajouter** : « plantation rattachée à une parcelle ».

---

## B09 — « Noter un semis déjà fait » (carottes), trace propre

Session du 18/11/2026 à 22:0x, potager neuf remis à zéro avant. Échanges 274 à 277, proposition 267 confirmée (création de parcelle).
Résultat en base : **aucun événement de semis** ; une parcelle « pépinière chaude » créée (potager 37 : « planche légumes » + « pépinière chaude »).

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain | Motif |
|---|---|---|---|---|---|
| 274 | j'ai semé des carottes ce matin | aiguillé vers geste | — | **vrai** | — |
| 275 | (même phrase) | « Quelle quantité ? Redis ta phrase avec la quantité… » | — | **faux** | Fait redire toute la phrase ; ne vérifie pas la fiche de culture |
| 276 | 20 graines en pépinière chaude | `/parcelle ajouter pépinière chaude` | lire, creer_parcelle | **faux** | Prend le lieu de semis pour une parcelle à créer |
| 277 | mais tu n'as pas enregistré mon semi de carotte ? | « Aucun geste n'est en attente… dis-moi ce que tu as fait » | lire | **faux** | Fil perdu : demande de tout redire |

### Bonne réponse attendue à B09 (dite par le jardinier, 18/11/2026)

- Pour la carotte, le compagnon **se réfère à la fiche de culture** et **détermine si le semis en pépinière est possible**.
- Si **seul le semis en pleine terre** est possible, il **le précise** au jardinier.
- Il **n'anticipe jamais la création d'une parcelle** (« serre chauffée » / « pépinière chaude ») que le jardinier n'a pas demandée.
- Jugement d'ensemble : « tout le comportement est à revoir ».

### Ce qui se vérifie par le code

| Élément attendu | Contrôle possible |
|---|---|
| fiche de culture lue | le référentiel de la carotte est lu avant de traiter le lieu de semis |
| mode de semis dit | si la carotte n'a que le semis en pleine terre, le texte le dit |
| aucune création de parcelle non demandée | aucune proposition `/parcelle ajouter` sur une phrase de semis |
| fil gardé | la culture et la date déjà dites ne sont pas redemandées ; seule la quantité manquante l'est |
| écriture aboutie | après la quantité, une proposition de semis est faite (culture, quantité, date) |

### Constat

Un enchaînement de trois erreurs sur un geste courant : la phrase initiale est bien aiguillée (#274), puis le fil est perdu dès
la demande de quantité (#275), un lieu devient une parcelle (#276), et le semis n'est jamais écrit (#277). Aucune confirmation
de la création de parcelle n'était souhaitée par le jardinier.

---

## B15 — « Corriger ce qui vient d'être noté » (semis de carottes), trace propre

Session du 18/11/2026, potager neuf remis à zéro avant. Échanges 278 à 280, propositions 268 (geste) et 269 (correction) confirmées.
Résultat en base : **un seul événement** (671), semis, carotte, **2 m²**, parcelle planche légumes, 17/11/2026. Aucun second geste.

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain |
|---|---|---|---|---|
| 278 | j'ai semé des carottes hier sur la planche légumes sur 3 m2 | aiguillé vers geste | — | **vrai** |
| 279 | (même phrase) | proposition : semis · carotte · 3 m² · parcelle planche légumes · 2026-11-17 | geste | **vrai** |
| 280 | en fait c'était 2 m2 et non 3 | proposition : /corriger — Semis carotte : 3 m² → 2 m² | corriger_action | **vrai** |

### Ce que ça montre

- Premier scénario **entièrement juste**. Quand le jardinier donne tous les éléments dans sa phrase (culture, parcelle, quantité, date),
  le chemin « geste puis correction » tient : parcelle reprise de la phrase, « hier » compris, correction sur le bon geste, rien redemandé.
- Contraste avec B09 (même type de geste, semis de carottes) : la différence est que **B15 donne la parcelle et la quantité dès
  la première phrase**. Le compagnon réussit quand rien ne manque ; il échoue dès qu'il doit demander ou lire un complément (B04, B09).
- Variante non jouée : correction sans redire la culture, ou plusieurs gestes récents.

---

## B22 — « Associations et voisinage d'une culture » (tomate), trace propre

Session du 18/11/2026, potager neuf remis à zéro avant. Échange 281. Question posée par le jardinier avec ses mots :
« je veux planter des tomates mais je me demandais si je devais éviter certaines cultures de proximité ? des compagnons à éviter ? »

| # | Réponse du compagnon | Outils | Verdict humain |
|---|---|---|---|
| 281 | « …pommes de terre, aubergines et poivrons (même famille, mêmes maladies)… fèves et choux à surveiller… Source : Conduite et récolte de la tomate. » | chercher_connaissance ×6 | **faux** |

### Ce que le jardinier a donné comme référence (fiche de la zone « tomate », 18/11/2026)

| Bons voisins (+) | Mauvais voisins (−) |
|---|---|
| basilic, Lamiacée (famille), ciboulette, laitue, persil, ail, carotte, poivron | chou, concombre, Brassicacée (famille), fenouil |

### Écarts constatés avec cette fiche

| Réponse du compagnon | Ce que dit la fiche de la zone |
|---|---|
| poivron à éviter | **poivron est un bon voisin (+)** : contradiction |
| chou « à surveiller, moins souvent cité » | chou est à éviter (−), ainsi que toute la famille des Brassicacées |
| pomme de terre, aubergine, fèves à éviter | **absents** de la fiche |
| concombre, fenouil non cités | à éviter (−) |
| aucun bon voisin cité | huit bons voisins listés |
| source : « Conduite et récolte de la tomate » | cette fiche de conseils ne contient **aucun** passage sur les voisinages (vérifié) |

### Bonne réponse attendue à B22

- Le compagnon **lit les associations de la culture dans la fiche de la zone du potager** (données structurées), pas le texte libre des fiches de conseils.
- Il **restitue les deux listes** : à éviter (chou, concombre, fenouil, et la famille des Brassicacées) et favorables (basilic, ciboulette,
  laitue, persil, ail, carotte, poivron, et la famille des Lamiacées), même si la question ne portait que sur « à éviter ».
- Il **ne cite aucune culture absente de la fiche** et **ne cite pas une source qui ne contient pas l'information**.
- Les familles (Lamiacée, Brassicacée) sont dites comme familles, pas comme des cultures.

### Ce qui se vérifie par le code

| Élément attendu | Contrôle possible |
|---|---|
| lecture des associations | la capacité d'association (table `association_culture`, US-163) est appelée pour la culture et la zone |
| listes fidèles | chaque culture citée « à éviter » / « favorable » figure dans la bonne liste de la fiche |
| rien d'inventé | aucune culture citée qui ne figure dans aucune liste |
| source juste | la source citée contient bien l'information ; sinon pas de source |
| aucune contradiction | une culture « + » en base n'est jamais présentée comme à éviter |

### Constat

Les données existent déjà et sont fiables (table `association_culture`, US-163, fiche de zone). Le compagnon ne les consulte pas :
il passe par la recherche de texte (`chercher_connaissance`) et complète avec ce que le modèle sait, en citant une source qui ne le dit pas.
C'est le cas typique d'un **outil de lecture à brancher** (capacité « associations »), pas d'un problème de modèle.

---

## B06 — « Que semer ce mois-ci », trace propre

Session du 18/11/2026, potager neuf remis à zéro avant (zone océanique, pas de ville). Échange 282.

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain |
|---|---|---|---|---|
| 282 | Bon, je sème quoi en ce moment ? | « En novembre, les semis en pleine terre sont rares… en intérieur ou sous abri si tu as une serre… prépare tes semis de mâche, épinard ou betterave pour les prochaines semaines… Source : Problèmes observables de la mâche. » | chercher_connaissance, afficher | **à moitié** |

### Vérification faite sur le référentiel (zone océanique, 18/11/2026)

- Aucune culture n'a de fenêtre de semis qui couvre novembre.
- Betterave : semis en pleine terre mars-mai ; la proposer « pour les prochaines semaines » est faux.
- Mâche et épinard : aucune fenêtre de semis renseignée (manque US-349).
- Source citée : fiche de problèmes de la mâche, qui ne parle pas du calendrier de semis.

### Bonne réponse attendue à B06 (dite par le jardinier, 18/11/2026)

- Le compagnon s'appuie sur **la vue Pépinière de l'application**, qui dispose, pour la zone du potager, de la rubrique
  **« le bon moment pour semer »**.
- Pour novembre, cette rubrique est **vide** : le compagnon doit **dire qu'il n'y a aucun semis à faire en novembre** pour la zone,
  et non proposer une liste de cultures.
- La réponse du compagnon doit donc **coïncider avec ce que la vue Pépinière affiche** pour le mois.

### Ce qui se vérifie par le code

| Élément attendu | Contrôle possible |
|---|---|
| source unique des semis du mois | la liste citée est celle que renvoie le service qui alimente la vue Pépinière (« bon moment pour semer ») |
| cohérence avec l'application | toute culture citée figure dans cette liste ; mois vide → réponse « aucun » |
| rien d'inventé | aucune culture dont la fenêtre ne couvre pas le mois |
| source juste | la source citée porte bien sur le calendrier |
| mois différent, réponse différente | même question posée un mois où la liste est non vide : la liste change (test miroir) |

### Constat

Même cause que B22 : la donnée existe déjà dans l'application (rubrique de la vue Pépinière), le compagnon ne la lit pas et
reconstitue une réponse par recherche de texte. À brancher comme capacité de lecture, avec l'application comme référence.

---

## B19 — « Trouver une fonction de l'application » (parcelle, ville de la météo), trace propre

Session du 18/11/2026, potager neuf remis à zéro avant (une parcelle « planche légumes », pas de ville). Échanges 283 à 289.
Proposition 270 (créer « une autre ») abandonnée : rien créé. Le potager n'a toujours ni ville ni coordonnées.

| # | Jardinier | Réponse du compagnon | Outils | Verdict humain | Motif |
|---|---|---|---|---|---|
| 283 | comment ajouter une parcelle dans mon potager ? | « Tu as déjà une parcelle nommée *planche légumes*… la modifier ou en créer une autre ? » | creer_parcelle | **à moitié** | Lit le plan (bien), mais propose d'agir au lieu d'expliquer |
| 284 | une autre | `/parcelle ajouter une autre` | creer_parcelle | **faux** | Prend « une autre » pour le nom de la parcelle |
| 285 | non. as tu l'aide pour l'ajout d'une parcelle ? | `/help` | afficher | **à moitié** | Incomplet : il n'affiche pas l'aide |
| 286 | oui | « proposition confirmée par le jardinier » | confirmer_proposition | **faux** | — |
| 287 | comment je règle ma ville pour la météo ? | « …nommer la ville dans ta phrase… ex. « Quelle météo à Lyon ? » Source : Guide d'exploitation » | chercher_connaissance | **faux** | Ne dit pas comment **ajouter ou modifier la ville associée au potager** |
| 288 | quel est la météo ? | « Je ne peux pas te donner la météo du potager sans savoir où il se trouve. Dans quelle ville ? » | meteo | **vrai** | — |
| 289 | paris | « À Paris, aujourd'hui, il pleut légèrement, entre 11,6 °C et 15,3 °C… » | meteo | **vrai** | — |

### Bonne réponse attendue à B19 (dite par le jardinier, 18/11/2026)

- À « comment ajouter une parcelle ? » : **expliquer et afficher l'aide** correspondante, pas seulement proposer de créer.
- À « comment régler la ville pour la météo ? » : **dire comment ajouter ou modifier la ville associée au potager** (pas comment demander
  la météo d'une ville ponctuelle). L'emplacement exact du réglage dans l'application reste à écrire ici par le jardinier.
- Quand la ville est inconnue et qu'on demande la météo : **le dire et demander la ville** (#288, juste), puis donner la météo (#289, juste).

### Ce qui se vérifie par le code

| Élément attendu | Contrôle possible |
|---|---|
| aide affichée | la réponse à « comment… » contient l'aide (ou le chemin dans l'application), pas seulement une proposition de commande |
| pas de création déguisée | aucune proposition `/parcelle ajouter` sur une question « comment ajouter » |
| réponse à la bonne question | « régler la ville du potager » ≠ « demander la météo d'une ville » : le texte parle du réglage du potager |
| ville inconnue dite | la météo sans ville renvoie la demande de ville (déjà tenu) |
| lecture du plan | la parcelle existante est citée (déjà tenu en #283) |

### Constats

- Deux comportements **justes** et à garder : dire qu'il manque la ville avant de donner la météo (#288, #289), et lire le plan (#283).
- Une même confusion revient (B09, B19) : un mot du jardinier (« une autre », « pépinière chaude ») est pris pour **le nom d'une parcelle**.
- Un « non » ou un « oui » n'est pas rattaché à la bonne proposition en attente (#285, #286).
- Hypothèse « Lyon » (B05) renforcée : l'exemple « Quelle météo à Lyon ? » est dans le guide cité ; à confirmer sur les arguments envoyés à l'outil.
- Remarque de l'assistant non validée par le jardinier : après « paris », le compagnon n'a pas proposé d'enregistrer la ville au potager. Le jardinier a jugé #289 vrai.

---

## SYNTHÈSE de la session du 18/11/2026 (9 scénarios joués par le jardinier)

| Scénario | Résultat | Cause principale |
|---|---|---|
| B15 corriger un geste | **juste** (3/3) | rien ne manquait dans la phrase |
| B04 planter en plants | à moitié | parcelle non demandée, plantation écrite sans parcelle |
| B06 que semer ce mois-ci | à moitié | liste inventée ; la vue Pépinière dit « aucun » en novembre |
| B01 salade / tomate | faux | météo, calendrier, plan non lus ; « 5°C » inventé |
| B05 radis | faux | « Lyon » cité ; plan non lu |
| B20 culture sans fiche | faux (4/4) | confond culture et parcelle ; pas de duplication/création de fiche |
| B09 noter un semis | faux (3/4) | lieu pris pour une parcelle ; semis jamais écrit |
| B22 voisinages | faux | table des associations non lue ; poivron dit à éviter ; fausse source |
| B19 trouver une fonction | à moitié (2 vrais, 2 à moitié, 3 faux) | ne dit pas où régler la ville du potager ; « oui »/« non » mal rattachés |

### Causes communes

1. **Les données de l'application ne sont pas lues** (plan, calendrier, vue Pépinière, associations, fiche de zone) : B01, B04, B05, B06, B19, B20, B22.
2. **Le modèle complète seul** : chiffre inventé (B01), cultures et source fausses (B22, B06), ville inventée « Lyon » (B05, B19).
3. **Le fil se perd** : un mot devient le nom d'une parcelle (B09, B19, B20), un oui/non n'est pas rattaché à la bonne question (B01, B19).
4. **Des actions non demandées** : création de parcelle (B09, B19, B20), écriture sans parcelle (B04).
5. **Ce qui tient** : geste complet puis correction (B15), dire que la ville manque (B19), lire le plan parfois (B19), fiche de conduite quand la question la vise (B01 #250).

### Capacités à brancher (d'après les références du jardinier)

| Capacité | État |
|---|---|
| associations d'une culture | donnée existante (`association_culture`, US-163) |
| « bon moment pour semer » du mois (vue Pépinière) | donnée existante dans l'application |
| situation de culture : verdict, risque, prochaine fenêtre | US-339 (fenêtre de plantation : US-349) |
| lecture du plan, de la serre déclarée | à brancher |
| réglage de la ville du potager, aide de l'application | à brancher ; emplacement du réglage à documenter |
| dupliquer / créer une fiche culture pour la zone | **absente**, capacité nouvelle |

### Critères à ajouter au jeu d'évaluation

plantation rattachée à une parcelle ; aucune création de parcelle non demandée ; cohérence avec la vue de l'application ;
source citée qui contient l'information ; réponse différente selon la date (test miroir) ; oui/non rattaché à la bonne question.

### Restes à décider

- Ligne de base G0 : mesure du 18/11 non versionnée ; ces références humaines la complètent et la corrigent (le juge automatique notait « utile » presque toujours à 0).
- Comparer le juge automatique à ces verdicts humains (quelques centimes, accord nécessaire).
- B01-F1 rejoué à l'identique (14/11) : passer en simulé, garder la trace comme témoin.
- Non joués : B02, B03, B10 à B14 (neuf) ; B07, B08, B16 à B18, B21, B23, B24 (potager rempli à construire).
