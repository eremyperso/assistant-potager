**ID :** US-170  
**Titre :** Confier la décision de nature au routeur et servir les réponses d'absence sans remonter la cascade  
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que mes questions soient reconnues comme des questions même dictées sans point d'interrogation, et qu'un « je n'ai rien enregistré » me soit répondu tel quel plutôt que remplacé par un conseil général
Afin d'obtenir la bonne réponse du premier coup, sans détour par un parsing d'action qui coûte des jetons et se trompe

**Critères d'acceptance :**

*Chantier 3 — le catalogue d'abord (à livrer en premier, il sécurise le chantier 1)*
- [ ] CA1 : Une famille du catalogue répond au nombre de godets produits, agrégée sur les gestes de mise en godet, scopée au potager courant comme toutes les autres familles. « combien de godet de tomate produit cette saison ? » rend un nombre de godets, pas un poids récolté
- [ ] CA2 : Cette famille est consultée **avant** la famille de rendement de saison. L'ordre du catalogue décide de l'aiguillage : placée après, elle ne sera jamais atteinte
- [ ] CA3 : Le motif de la famille de rendement de saison ne capte plus toute phrase contenant le mot « produit ». Il ne retient que les tournures qui désignent réellement une quantité récoltée
- [ ] CA4 : Les questions que le motif large rattrapait légitimement — « qu'est-ce qui a produit cette année ? » en tête — restent aiguillées vers le rendement. Le resserrement est validé contre le corpus de routage existant et les tests d'US-096, pas seulement contre le nouveau cas
- [ ] CA5 : La famille godets a une phrase d'absence juste quand aucun godet n'a été produit, au même titre que les familles existantes

*Chantier 1 — la nature de la demande se décide au routeur, une seule fois*
- [ ] CA6 : Le bot ne décide plus lui-même si un message est une question. Il interroge le routeur, qui possède déjà les règles, la règle de geste, le catalogue, le cache de classification et le modèle en dernier recours, puis suit sa décision
- [ ] CA7 : Une question dictée **sans** point d'interrogation est traitée comme une question. C'est le cas nominal du canal vocal, où le point d'interrogation n'existe pas — la moitié du critère actuel repose sur un signal absent du canal principal
- [ ] CA8 : Les gardes de **conversation** restent consultées avant le routeur, sans exception : modes de correction, mode question en cours, navigation, création de parcelle. Elles ne classifient pas une demande, elles portent un état de dialogue — les déplacer casse les dialogues en cours
- [ ] CA9 : Les gardes qui **classifient** (godets, déplacement, note) passent après le routeur ou disparaissent au profit de familles du catalogue. Le choix est tranché dans l'implémentation et écrit : leur retrait pur casse des parcours de saisie guidée qui n'ont aucun équivalent au catalogue
- [ ] CA10 : Le filet de rerattrapage d'US-011 est **conservé**. Il cesse d'être le chemin nominal mais reste le filet des cas résiduels
- [ ] CA11 : Aucune saisie réelle n'est classée à tort comme question. Vérifié sur le corpus des saisies de production versionné, avec les règles seules du routeur
- [ ] CA12 : Le coût en jetons d'une question reconnue par règle ou par catalogue tombe à zéro, contre un parsing d'action complet aujourd'hui. Mesuré sur les trois formulations relevées le 30/08/2026, qui coûtaient ~8 800 jetons à elles seules

*Chantier 2 — « rien » est une réponse, pas un échec*
- [ ] CA13 : Quand une famille du catalogue a matché **et produit une phrase**, cette phrase est servie au jardinier, y compris lorsqu'elle dit « je n'ai aucune récolte enregistrée ». La cascade ne remonte pas
- [ ] CA14 : La remontée de cascade reste déclenchée quand **aucune famille ne matche** — notamment lorsque la culture citée est inconnue du potager. La distinction se fait d'elle-même : si une famille a matché avec une culture, cette culture existe dans le potager, et « rien enregistré » est exact et non évasif
- [ ] CA15 : Le chemin de l'agent SQL, qui n'a pas de gabarit, continue de remonter : son absence de confiance signifie réellement « je n'ai pas su répondre »
- [ ] CA16 : Le bot ne demande plus au jardinier des données qu'il détient lui-même (nombre de plants, variété, conditions de culture) en réponse à une question portant sur son propre potager

*Traçabilité des révisions et vérification d'ensemble*
- [ ] CA17 : La révision d'**US-093 / CA13** (« le routeur s'insère après la détection de question du bot ») est écrite dans cette US et répercutée dans la documentation du routeur. Elle n'est pas faite en silence
- [ ] CA18 : La révision d'**US-093 / CA6-CA7** et son articulation avec **US-096 / CA7-CA8** (« vide n'est pas zéro », « rendre la main plutôt que conclure ») sont écrites : la révision porte sur *quand* rendre la main, pas sur le principe
- [ ] CA19 : Le retour jardinier d'US-097 montre le chemin réellement emprunté — origine de la décision, famille retenue, jetons consommés — pour chacun des trois cas corrigés
- [ ] CA20 : Hors périmètre, explicitement : l'étage météo. Une question sur la météo passée coûte aujourd'hui des jetons pour répondre que l'historique est inaccessible alors que le fournisseur météo est intégré. Écarté par décision du 30/08/2026, à traiter dans une US dédiée

**Notes fonctionnelles :**

- Zone fonctionnelle concernée : interaction Telegram (aiguillage des messages) + consultation (justesse des réponses chiffrées)
- Migration BDD requise : **non** — aucune structure nouvelle, la famille godets agrège des évènements déjà enregistrés
- Dépendances :
  - Révise **US-093** (routeur règles-first) — CA13 sur la position du routeur, CA6-CA7 sur la remontée de cascade
  - Étend **US-096** (réponses chiffrées sur gabarits SQL) — une famille de plus, un motif resserré ; l'US prévoit explicitement cette extension
  - S'articule avec **US-097** (observabilité de la cascade) pour la vérification
  - Indépendante d'**US-095** (cache de questions) : les trois défauts lui sont antérieurs et le cache fonctionne
- Source : `docs/ANALYSE_ROUTAGE_QUESTIONS_2026-08-30.md`, essais en conditions réelles du 30/08/2026

*Pourquoi une seule US pour trois chantiers*

Les chantiers 1 et 3 sont couplés dans un sens dangereux : faire atteindre le routeur à la
question godets **avant** que le catalogue sache y répondre transforme une réponse hors
sujet (la liste des godets en attente de plantation) en une réponse fausse d'apparence
juste (un poids récolté présenté comme un nombre de godets). Livrer le chantier 1 seul
dégrade donc la qualité perçue. Le chantier 2 est indépendant, mais il porte la même
promesse — répondre juste plutôt que répondre à côté — et se vérifie sur le même corpus.

L'ordre d'implémentation est imposé : **chantier 3, puis chantier 1, puis chantier 2**.

*Les mesures qui motivent l'US (30/08/2026, rejouables sans base de production ni appel modèle)*

| Mesure | Résultat |
|---|---|
| Questions du corpus de routage rejetées par la détection actuelle, **avec** le `?` | 8/74 — 11 % |
| Les mêmes, dictées **sans** `?` (cas nominal vocal) | 41/74 — 55 % |
| Saisies réelles classées ACTION par règle seule, 0 jeton | 204/211 — 97 % |
| Saisies réelles classées à tort comme question | **0** |
| Saisies réelles sans règle applicable | 7 — ~200 jetons chacune, contre 2 830 aujourd'hui |

Échantillon de questions aujourd'hui rejetées telles quelles : « mes traitements de la
semaine dernière », « un point sur mes cultures en ce moment », « des nouvelles de mes
tomates », « dis moi tout sur le paillage ». Une des 7 saisies sans règle — « Y a t il des
radis dans mon jardin » — est en réalité une question aujourd'hui enregistrée comme action.

Coût relevé le 30/08/2026 : trois questions de rendement à ~2 940 jetons chacune que le
catalogue sert à 0, et quatre formulations d'une question sans donnée à 1 087 jetons cumulés
pour un conseil d'agronomie hors sujet.

*Le défaut du chantier 2, en une phrase*

La phrase juste est **déjà produite** par le catalogue — « Je n'ai aucune récolte de
concombre enregistrée cette saison. » — puis jetée, parce que l'absence de donnée est
signalée par le même drapeau que l'incapacité à répondre. Deux situations très différentes
partagent aujourd'hui un seul signal : *je ne sais pas répondre* (monter d'un étage a du
sens) et *je sais répondre, et la réponse est « rien »* (monter d'un étage remplace une
réponse exacte par une réponse hors sujet).

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: une question dictée sans point d'interrogation atteint le routeur
  Given un potager avec 8 récoltes de tomate enregistrées cette saison
  When le jardinier dicte "ma production de tomate"
  Then le routeur classe la demande comme une question de données
  And le catalogue rend le rendement cumulé de tomate
  And aucun parsing d'action n'a été déclenché
  And le coût de la réponse est de 0 jeton

Scénario: une culture semée mais sans récolte reçoit la réponse exacte
  Given un potager où le concombre est semé mais n'a donné aucune récolte
  When le jardinier demande "quel ma production de concombre ?"
  Then la réponse est "Je n'ai aucune récolte de concombre enregistrée cette saison."
  And la cascade n'est pas remontée vers le raisonnement
  And le bot ne demande pas au jardinier le nombre de plants qu'il a

Scénario: une culture absente du potager remonte toujours la cascade
  Given un potager où aucun physalis n'a jamais été semé ni planté
  When le jardinier demande "combien de physalis ai-je récolté ?"
  Then aucune famille du catalogue ne matche
  And la cascade remonte vers le raisonnement pour formuler une réponse utile

Scénario: la question godets rend un nombre de godets
  Given un potager avec des mises en godet de tomate enregistrées cette saison
  When le jardinier demande "combien de godet de tomate produit cette saison ?"
  Then la réponse porte sur le nombre de godets produits
  And elle ne rend ni la liste des godets en attente de plantation, ni un poids récolté

Scénario: une saisie réelle reste une saisie
  Given un jardinier qui dicte ses gestes du jour
  When il dicte "j'ai récolté 300 g de haricots sur la parcelle 3"
  Then la demande est classée comme une action
  And l'évènement est enregistré normalement
```

**Labels GitHub :** `us`, `sprint-epic-6`, `routage`, `consultation`
