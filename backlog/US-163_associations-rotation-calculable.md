**ID :** US-163
**Titre :** Modéliser les associations de cultures et rendre la règle de rotation calculable
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que l'application sache quelles cultures s'associent bien et combien d'années attendre avant de revenir sur une même famille
Afin qu'elle puisse me répondre en tenant compte de ce que j'ai réellement cultivé sur cette parcelle, et non me réciter un principe général

**Contexte fonctionnel :**
Quatrième US de l'`ÉPIC 6` (`docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §4.1),
rang B5 de la piste B (`docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.4).

C'est l'US qui donne son sens à tout l'épic. « Quelles cultures puis-je planter sur la parcelle
NORD, sachant que j'y ai eu des tomates l'an dernier et des pommes de terre il y a deux ans ? » est
une **requête de graphe croisée avec l'historique**. Aucune recherche plein texte ni vectorielle ne
la produira : au mieux elle retrouvera un paragraphe générique sur la rotation des solanacées.
C'est très exactement ce que le CA7bis d'US-140 interdit d'écrire dans une fiche, et ce que cette
US rend calculable à la place.

Le socle est déjà en place : **US-067 amendée** a fait de la famille botanique une table de
référence portant un **délai de retour en années** (CA12). Cette US n'a donc aucune migration de
`culture_config` à rouvrir — c'était précisément l'objet de l'amendement.

**Une conséquence assumée de l'arbitrage de licence** (option A, zéro CC-BY-SA) : les données
d'association sont rares en open data non contaminant. Elles sont donc **saisies, pas importées**.
C'est le coût réel de l'option A — et c'est aussi ce qui en fait un actif propre à l'application :
une donnée que tout le monde peut réimporter ne différencie personne.

**Critères d'acceptance :**

*Les associations*
- [ ] CA1 : L'association entre deux cultures est une **arête typée** portant sa nature (`favorable`, `defavorable`, `neutre`) et un **motif court** en clair — « répulsif contre la mouche de la carotte », « concurrence racinaire ». Le motif est ce qui rend l'avertissement compréhensible plutôt qu'autoritaire
- [ ] CA2 : Chaque association porte son **niveau de preuve** : `etabli` ou `traditionnel`. La tradition horticole et la littérature scientifique divergent souvent sur ce sujet ; verser les deux dans la même table sans distinction reviendrait à faire affirmer à l'application ce qu'elle ne peut pas soutenir — exactement ce que l'Épic 5 interdit sur les dates
- [ ] CA3 : La **formulation est différenciée** à la restitution : « défavorable » pour une relation établie, « déconseillé par la pratique traditionnelle » pour l'autre. Le jardinier doit pouvoir faire la part des choses sans avoir à interroger la base
- [ ] CA4 : Une association peut être portée **au niveau de la famille botanique** et vaut alors pour toutes les cultures qui s'y rattachent. La mesure du 25/08/2026 le justifie : les cucurbitacées se répartissent sur **dix libellés distincts** — courgette, cornichon, concombre, melon, potiron, butternut, courge, potimarron, pâtisson, pastèque — soit plus d'événements que la tomate. Saisir dix fois la même relation garantit qu'elle sera incohérente à la première correction
- [ ] CA5 : La relation se lit **dans les deux sens**. Si A est défavorable à B, interroger B doit le dire aussi. Une orientation de stockage ne doit jamais devenir une asymétrie de réponse

*La rotation calculable*
- [ ] CA6 : Un conflit de rotation se **calcule** — il ne se rédige pas. La règle croise l'historique réel d'une parcelle, la famille botanique de chaque culture qui y est passée, et le délai de retour de cette famille (US-067 / CA12). Le résultat est un prédicat, exploitable par une alerte ; pas un passage de texte
- [ ] CA7 : Une famille **sans délai de retour renseigné** rend l'évaluation indisponible pour ses cultures. L'application dit alors qu'elle ne sait pas ; elle **ne conclut jamais à l'absence de conflit** (US-067 / CA13, réaffirmé ici parce que c'est ici que le calcul a lieu)
- [ ] CA8 : ⚠️ **L'historique est court et la réponse doit le dire.** La mesure du 25/08/2026 établit qu'une **seule campagne** est enregistrée (février à août 2026) : le calcul de rotation est structurellement sans matière jusqu'à la campagne suivante. Une parcelle sans antécédent connu produit « je n'ai pas d'antécédent sur cette parcelle », **jamais** « aucun conflit ». Les deux phrases sont opposées et la seconde serait fausse
- [ ] CA9 : Le calcul raisonne à la **campagne**, pas au jour près. C'est ce que le domaine impose, et c'est aussi ce qui le protège d'une donnée de date imparfaite : la mesure de production du 25/08/2026 montre que **la date est le premier poste de correction de toute l'application** (27,5 % des corrections), une saisie sans ancrage temporel retombant silencieusement sur le jour de saisie. Un raisonnement au jour près serait bâti sur du sable ; un raisonnement à l'année reste juste

*Saisie, traçabilité, coût*
- [ ] CA10 : Les associations sont **saisies et corrigeables**, avec leur source rattachée au référentiel de traçabilité d'US-166 — y compris la valeur `saisie_manuelle`. Aucune arête anonyme
- [ ] CA11 : Ni le calcul de rotation ni la lecture des associations n'appellent un modèle de langage. **Zéro jeton**, sur les deux chemins
- [ ] CA12 : 🧪 Le temps de réponse de la requête de rotation (historique de deux campagnes × culture × famille) est **mesuré sur la base de production** avant d'être câblé dans un chemin synchrone du bot. Attendu sous les 50 ms avec les index existants ; à vérifier, pas à supposer

*Tests*
- [ ] CA13 : Des tests couvrent une association favorable, une défavorable, une traditionnelle et sa formulation propre, la lecture dans les deux sens (CA5), une association portée par la famille (CA4), une parcelle sans antécédent (CA8), une famille sans délai de retour (CA7), et un conflit avéré sur deux campagnes

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse | consultation
- Migration BDD requise : **oui** — table d'associations orientée et sa traçabilité. **Aucune reprise de la migration de `culture_config`** : le délai de retour y est déjà porté par US-067 amendée
- Dépendances : **US-067 amendée** (bloquante — c'est son CA12 qui rend cette US possible sans migration concurrente) et **US-166** (traçabilité). Prérequis de **US-167**, qui restitue au jardinier ce que cette US calcule. Aucune dépendance à une US du moteur V2
- **Arbitrage tranché — la relation sort des fiches** (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §1.2) : une association écrite dans une fiche narrative est un texte. Elle ne peut ni être jointe à l'historique d'une parcelle, ni déclencher un avertissement. Écrite aux deux endroits, elle devient la seconde vérité concurrente que le CA7 d'US-140 interdit par ailleurs. Une fiche peut **expliquer** un mécanisme ; elle n'énonce pas la relation
- **Arbitrage tranché — associations saisies, pas importées :** conséquence directe de l'option A sur la licence. Le coût est réel et il est assumé ; le périmètre initial de dix cultures le rend borné
- **Arbitrage tranché — le niveau de preuve est une colonne, pas une nuance de rédaction :** une nuance rédigée ne se filtre pas. Un jardinier qui ne veut voir que les relations établies doit pouvoir le demander

**Notes techniques (pour Persona Developer) :**
- Le stockage peut rester orienté (une ligne par couple) tant que la **lecture** est symétrique — c'est le CA5 qui compte, pas la forme de stockage
- La requête de rotation joint l'historique des événements à la famille : elle doit exclure les bulletins `[AUTO-METEO]`, qui représentent **96 des 321 événements de production** et ne portent aucune culture
- ⚠️ Une culture fantôme née d'un échec de parsing peut polluer l'historique d'une parcelle : la production porte `radi`, issu de la question « Y a t il des radis dans mon jardin » enregistrée comme un événement. Le calcul de rotation ne doit pas traiter une culture inconnue du référentiel comme un antécédent établi

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Conflit de rotation sur deux campagnes
  Given une parcelle "NORD" ayant porté des tomates la campagne précédente
  And la famille "Solanacée" dont le délai de retour est de 3 ans
  When le jardinier envisage d'y planter des poivrons
  Then l'application signale un conflit de rotation
  And elle cite la culture précédente et la famille en cause

Scénario: Parcelle sans antécédent connu
  Given une parcelle "OUEST" sur laquelle aucun événement n'est enregistré
  When le jardinier envisage d'y planter des tomates
  Then l'application répond qu'elle n'a pas d'antécédent sur cette parcelle
  And elle ne conclut pas à l'absence de conflit

Scénario: Famille sans délai de retour
  Given une culture rattachée à une famille dont le délai de retour n'est pas renseigné
  When une rotation est évaluée pour cette culture
  Then l'application indique que l'évaluation est indisponible
  And elle n'affirme pas l'absence de conflit

Scénario: Association traditionnelle formulée comme telle
  Given une association "defavorable" de niveau de preuve "traditionnel"
  When elle est restituée au jardinier
  Then elle est présentée comme déconseillée par la pratique traditionnelle
  And non comme un fait établi

Scénario: Association lue dans les deux sens
  Given une association défavorable saisie de la carotte vers l'aneth
  When le jardinier interroge les associations de l'aneth
  Then la relation avec la carotte lui est restituée

Scénario: Association portée par la famille
  Given une association défavorable saisie au niveau de la famille "Cucurbitacée"
  When le jardinier interroge les associations du pâtisson
  Then la relation lui est restituée sans avoir été saisie pour le pâtisson

Scénario: Aucun jeton consommé
  Given une évaluation de rotation et une consultation d'associations
  When les deux sont exécutées
  Then aucune n'a nécessité d'appel à un modèle de langage
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `referentiel`, `rotation`
