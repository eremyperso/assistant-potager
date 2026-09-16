**ID :** US-181
**Titre :** Déclarer l'abri et le paillage d'une parcelle et les faire peser sur la confiance
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux dire à l'application qu'une parcelle est sous serre, sous tunnel, sous châssis ou sous voile, et si elle est paillée
Afin que la confiance tienne compte de la protection réelle de mes cultures au lieu de traiter ma serre comme un rang en plein vent

**Contexte fonctionnel :**
La parcelle porte déjà `est_pepiniere` (migration v13), `exposition` et `type_sol` (migration v28, US-058). Elle ne sait pas si elle est **abritée** ni **paillée** — les deux paramètres que le jardinier cite en premier quand on lui demande pourquoi il sème plus tôt que le voisin. Le moteur de confiance (US-178) applique donc à une serre les mêmes règles de gel et de nuits fraîches qu'à la pleine terre.

Cette US ajoute ces deux attributs, **déclarés par le jardinier** au bot ou depuis l'écran de paramètres du potager, et les branche sur le moteur comme **modulateurs de règles** : un abri neutralise ou atténue la règle de gel annoncé et celle des nuits fraîches, un paillage n'agit que sur les nuits fraîches. Aucune simulation, aucun décalage de température calculé : un abri déclaré rend la règle non pertinente, il ne « réchauffe » pas la prévision.

⚖️ L'abri est **un attribut de la parcelle, pas de l'événement**. Un voile posé puis retiré en cours de saison relève du journal (événement d'entretien, hors périmètre) ; ici, c'est l'état déclaré de la parcelle qui compte, corrigeable à tout moment.

**Critères d'acceptance :**
- [ ] CA1 : Une parcelle porte un **abri** parmi un vocabulaire fermé — aucun, voile, châssis, tunnel, serre — et un **paillage** oui / non. Les deux sont nullables : une parcelle jamais renseignée reste « non renseigné », distinct de « aucun abri »
- [ ] CA2 : Les deux attributs se déclarent au **bot** par la commande de parcelle existante (`/parcelle …`) et par dictée (« la parcelle 2 est sous serre », « rang 3 paillé »), reconnus par la grammaire déterministe sans appel au modèle ; l'interpréteur ne confond pas « sous voile » (abri) avec la pose d'un voile datée (« j'ai mis un voile sur le rang 3 hier », qui reste un enregistrement d'action s'il est reconnu, sinon rejoint le flux habituel)
- [ ] CA3 : Les deux attributs sont modifiables depuis l'**écran de paramètres** du potager de la PWA (US-082) et lus par l'API de parcelles existante, sans nouvel endpoint
- [ ] CA4 : Le moteur de confiance (US-178) applique les modulateurs, **à un seul endroit**, dans son tableau de règles : serre ou tunnel → R3 (gel annoncé) et R4 (nuits fraîches) acquises d'office, avec le motif « parcelle abritée » ; châssis ou voile → R3 acquise, R4 inchangée ; paillage → R4 acquise, R3 inchangée. « Non renseigné » et « aucun » ne modifient rien. La règle R2 (dernière gelée de la zone) n'est **pas** modulée par un voile ou un châssis, seulement par une serre ou un tunnel
- [ ] CA5 : Un motif modulé le dit en clair dans le résultat (« Aucun gel annoncé — parcelle sous serre, règle sans objet ») ; le jardinier voit que l'abri a compté, et non que la météo était clémente
- [ ] CA6 : L'action *plantation* sous serre ou tunnel reste soumise à la fenêtre conseillée (R1) : un abri ne rend pas une plantation de janvier recommandée. Un test le garantit
- [ ] CA7 : Migration : colonnes nullables, aucun backfill (pas de supposition sur l'existant), rollback fourni ; `est_pepiniere` n'est pas réinterprété comme un abri
- [ ] CA8 : Aucune régression sur le calcul de stock, l'écran Stocks, la pépinière ni les statistiques — ces attributs ne pilotent rien d'autre que la confiance
- [ ] CA9 : La fiche d'aide des parcelles du corpus « fonctionnement de l'application » est relue et corrigée dans la même livraison (US-099 / CA9)
- [ ] CA10 : Des tests couvrent : déclaration au bot et par dictée du CA2 avec la non-confusion, édition depuis l'écran de paramètres, les quatre combinaisons de modulateurs du CA4, le motif du CA5, la fenêtre maintenue du CA6, la non-régression du CA8

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (parcelle), analyse (moteur)
- Migration BDD requise : **oui** — `parcelles.abri` (VARCHAR court, nullable, vocabulaire validé au point d'écriture comme pour `fenetre_culturale.phase`) et `parcelles.paillage` (BOOLEAN nullable). Numéro à lire dans `migrations/` au démarrage — dernier constaté sur la branche de référence : v47
- Dépendances : **US-178** (moteur, bloquante), **US-082** (écran de paramètres, à vérifier livrée), US-058 (attributs de parcelle existants)
- Impact tokens : zéro (grammaire déterministe pour la déclaration, moteur déterministe pour l'effet)
- Point de vigilance : la table des modulateurs du CA4 est une **décision produit**, pas une mesure ; elle est documentée à côté des pondérations d'US-178 et corrigeable au même endroit
- Point de vigilance : ne pas coupler l'abri à `est_pepiniere`. Une pépinière est souvent abritée, pas toujours ; une serre sert souvent de pépinière, pas toujours. Deux attributs, deux sens
- Point laissé ouvert : un abri **saisonnier** (voile posé de mars à mai) serait mieux porté par le journal. Hors périmètre v1

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: Déclarer une serre par dictée
  When le jardinier dicte "la parcelle 2 est sous serre"
  Then la parcelle 2 porte l'abri "serre"
  And aucun jeton n'a été consommé

Scénario: L'abri neutralise le gel annoncé
  Given une parcelle sous serre
  And une prévision de -2 °C dans 3 jours
  When le jardinier demande la confiance pour semer des tomates en pépinière dans cette parcelle
  Then la règle de gel annoncé est marquée "gagné" avec le motif "parcelle sous serre"

Scénario: Un voile ne suffit pas contre la dernière gelée de la zone
  Given une parcelle sous voile en zone continentale
  And une dernière gelée moyenne déclarée au 10 mai pour cette zone
  When le jardinier demande la confiance pour planter des tomates le 20 avril
  Then la règle de dernière gelée n'est pas acquise
  And la règle de gel annoncé est acquise avec le motif "parcelle sous voile"

Scénario: Le paillage n'agit que sur les nuits fraîches
  Given une parcelle paillée sans abri
  And des nuits à 5 °C annoncées et aucun gel
  When le jardinier demande la confiance pour semer des haricots en place
  Then la règle des nuits fraîches est acquise avec le motif "parcelle paillée"
  And la règle de gel annoncé est évaluée normalement

Scénario: Un abri ne déplace pas la fenêtre
  Given une parcelle sous serre
  When le jardinier demande la confiance pour planter des tomates le 15 janvier
  Then la règle de fenêtre conseillée est marquée "perdu"

Scénario: Parcelle jamais renseignée
  Given une parcelle dont l'abri n'a jamais été déclaré
  When le jardinier demande une confiance dans cette parcelle
  Then aucune règle n'est modulée
  And le résultat ne mentionne pas d'abri
```

**Labels GitHub :** `us`, `backend`, `bot`, `pwa`, `parcelles`
