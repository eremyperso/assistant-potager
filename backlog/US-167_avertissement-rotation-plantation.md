**ID :** US-167
**Titre :** Avertir d'un conflit de rotation ou d'association au moment de la plantation
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux être prévenu au moment où j'enregistre une plantation si cette parcelle a porté la même famille récemment, ou si la culture voisine s'associe mal
Afin d'être averti **avant** l'erreur plutôt que de la comprendre trois mois plus tard

**Contexte fonctionnel :**
Dernière US de l'`ÉPIC 6` (`docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §4.1),
rang B6 de la piste B (`docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.4).

C'est l'US qui rend l'épic **utile plutôt que documentaire**. Toutes les précédentes remplissent
un référentiel ; celle-ci le fait parler au bon moment — celui où le jardinier a la fourche à la
main. Le référentiel n'est pas consulté : il se déclenche.

Aucun concurrent branchant un modèle de langage sur un carnet de jardin ne produit cela. Il faut
détenir l'**historique**, le **référentiel**, et le **lien entre les deux** — c'est précisément
l'actif que les six US précédentes ont construit.

**Ce n'est pas une contradiction avec l'arbitrage 4 de la vague 0** (`/fiche` sur commande
uniquement, pas de restitution spontanée) : ce qui y est écarté, c'est la **fiche pédagogique**
non demandée après une saisie. Un avertissement de conflit est d'une autre nature — c'est une
alerte sollicitée par l'action elle-même, pas un contenu poussé. La contrainte que l'arbitrage 4
protégeait reste néanmoins entière et vaut ici : **ne pas toucher à l'ordre critique des flux**,
et n'introduire aucun nouvel état conversationnel.

**Critères d'acceptance :**

*Le déclenchement*
- [ ] CA1 : L'avertissement se déclenche à l'**enregistrement d'une plantation ou d'un semis** rattaché à une parcelle, sur les deux canaux — bot et interface web
- [ ] CA2 : 🔴 **L'avertissement n'empêche jamais l'enregistrement.** L'événement est enregistré, l'avertissement l'accompagne. Le jardinier sait des choses que l'application ignore ; elle l'informe, elle ne l'arbitre pas
- [ ] CA3 : L'avertissement **n'introduit aucun nouvel état conversationnel** et ne modifie pas l'ordre critique des flux de `handle_text`. C'est un message qui suit la confirmation d'enregistrement, pas une question qui attend une réponse — l'invariant le plus fragile du projet n'est pas rouvert pour cette US
- [ ] CA4 : Aucun avertissement n'est produit sans conflit à signaler. Un message qui apparaît à chaque saisie cesse d'être lu au bout d'une semaine

*Ce que l'avertissement dit — et ce qu'il ne dit pas*
- [ ] CA5 : Un conflit de rotation cite **ce qui l'a causé** : la culture précédente, sa famille, la campagne concernée et le délai de retour. « Solanacées deux ans de suite, tomate ici la campagne dernière, délai recommandé 3 ans » et non « attention à la rotation »
- [ ] CA6 : ⚠️ **Une parcelle sans antécédent connu produit « je n'ai pas d'antécédent sur cette parcelle », jamais « aucun conflit ».** La mesure du 25/08/2026 rend ce critère central et non théorique : une **seule campagne** est enregistrée (février à août 2026), le calcul de rotation est donc structurellement sans matière jusqu'à la campagne suivante. Les deux formulations sont opposées et la seconde serait fausse
- [ ] CA7 : Une famille sans délai de retour renseigné rend l'évaluation indisponible pour ses cultures, et l'avertissement le dit (US-067 / CA13). L'application n'a le droit de se taire que si elle a vérifié
- [ ] CA8 : Un conflit d'**association** est formulé selon son niveau de preuve : « défavorable » pour une relation établie, « déconseillé par la pratique traditionnelle » pour l'autre (US-163 / CA3). Les deux ne sont pas la même information et ne se présentent pas de la même façon
- [ ] CA9 : L'avertissement raisonne à la **campagne**, jamais au jour près (US-163 / CA9). Outre que c'est ce que le domaine impose, c'est ce qui protège l'avertissement d'une donnée de date imparfaite : la mesure de production établit que **la date est le premier poste de correction de toute l'application** (27,5 % des corrections), une phrase sans ancrage temporel retombant silencieusement sur le jour de saisie

*Coût et robustesse*
- [ ] CA10 : L'avertissement est **entièrement déterministe** : jointure sur l'historique, la famille et le délai de retour. **Zéro jeton**, y compris quand aucun conflit n'est trouvé
- [ ] CA11 : 🧪 Le temps ajouté au chemin d'enregistrement est **mesuré sur la base de production** et reste imperceptible. Un avertissement utile qui ralentit chaque saisie serait payé plus cher qu'il ne rapporte. En cas de dépassement, l'avertissement est déporté hors du chemin synchrone plutôt que dégradé
- [ ] CA12 : Une culture inconnue du référentiel, ou une parcelle non identifiée, **n'empêche jamais l'enregistrement** et ne produit aucun avertissement erroné. Le cas est réel : la production porte la culture fantôme `radi`, issue d'une question enregistrée comme un événement

*Tests*
- [ ] CA13 : Des tests couvrent un conflit de rotation avéré, une parcelle sans antécédent (CA6), une famille sans délai de retour (CA7), un conflit d'association traditionnel et sa formulation, une saisie sans conflit qui ne produit aucun message (CA4), une culture inconnue (CA12), et la **non-régression du flux d'enregistrement** sur les deux canaux

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement | interaction Telegram
- Migration BDD requise : **non** — cette US lit ce que US-163 et US-067 ont modélisé
- Dépendances : **US-163** (le calcul, bloquante) et **US-067 amendée** (le délai de retour). Aucune dépendance au moteur V2
- **Arbitrage tranché — avertir, jamais bloquer (CA2) :** l'application ne connaît ni le sol, ni la météo locale, ni les raisons du jardinier. Un blocage sur une règle générale contre une décision informée serait une régression d'usage, pas une protection
- **Arbitrage tranché — le silence n'est pas une réponse (CA6) :** sur une base d'une seule campagne, l'écrasante majorité des plantations n'auront **aucun antécédent**. Si l'application répond « aucun conflit » dans ce cas, elle affirme quelque chose de faux dès le premier jour et perd la confiance qu'elle cherche à construire. Dire « je ne sais pas » est le seul comportement tenable — c'est le principe d'honnêteté de l'Épic 5 §4 appliqué à la rotation
- 🔶 Le référentiel s'enrichira de campagne en campagne : la valeur de cette US **croît avec le temps**, et elle est presque nulle la première année. C'est une raison de la livrer tôt, pas tard — l'historique ne se rattrape pas

**Notes techniques (pour Persona Developer) :**
- La requête d'antécédents doit exclure les bulletins `[AUTO-METEO]` (96 des 321 événements de production) et ne considérer que les événements portant une culture et une parcelle
- Le seuil de perception du CA11 se mesure sur les données réelles, pas sur le jeu de test : la production porte 321 événements, l'ordre de grandeur y est encore favorable et le restera longtemps
- L'avertissement s'affiche **après** la confirmation d'enregistrement, jamais à sa place : l'ordre des messages fait partie du contrat de cette US

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Conflit de rotation signalé sans blocage
  Given une parcelle "NORD" ayant porté des tomates la campagne précédente
  And la famille "Solanacée" dont le délai de retour est de 3 ans
  When le jardinier enregistre une plantation de poivrons sur cette parcelle
  Then l'événement est enregistré
  And un avertissement cite la tomate, la famille Solanacée et le délai recommandé

Scénario: Parcelle sans antécédent
  Given une parcelle "OUEST" sans aucun événement enregistré
  When le jardinier y enregistre une plantation de tomates
  Then l'événement est enregistré
  And l'application indique qu'elle n'a pas d'antécédent sur cette parcelle
  And elle n'affirme pas l'absence de conflit

Scénario: Aucun message quand il n'y a rien à dire
  Given une parcelle dont l'antécédent connu ne présente aucun conflit
  When le jardinier y enregistre une plantation
  Then l'événement est enregistré
  And aucun avertissement n'est affiché

Scénario: Famille sans délai de retour
  Given une culture rattachée à une famille sans délai de retour renseigné
  When le jardinier l'enregistre sur une parcelle ayant porté la même famille
  Then l'application indique que l'évaluation de rotation est indisponible

Scénario: Association traditionnelle
  Given une association défavorable de niveau de preuve "traditionnel" entre deux cultures voisines
  When le jardinier enregistre la seconde à côté de la première
  Then l'avertissement la présente comme déconseillée par la pratique traditionnelle

Scénario: Culture inconnue du référentiel
  Given une culture absente du référentiel
  When le jardinier enregistre sa plantation
  Then l'événement est enregistré normalement
  And aucun avertissement erroné n'est produit

Scénario: Aucun jeton consommé
  Given une plantation enregistrée sur une parcelle avec antécédents
  When l'avertissement est évalué
  Then aucun appel à un modèle de langage n'a eu lieu
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `bot`, `rotation`
