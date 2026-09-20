**ID :** US-214
**Titre :** Calculer les échéances d'un lot — repiquage, endurcissement, mise en terre, lot dormant — et ce qu'il y a à faire aujourd'hui
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'application me dise, pour chaque lot de ma pépinière, s'il est à repiquer, à endurcir, prêt à mettre en terre, en retard, ou oublié depuis des semaines
Afin de savoir en ouvrant la Pépinière ce que j'ai à faire aujourd'hui, et dans quel ordre

**Contexte fonctionnel :**
La v2 fait passer la Pépinière « de tableau de bord à outil de travail » : « la question n'est plus « qu'est-ce que j'ai » mais « qu'est-ce que je fais maintenant, et où » ». L'écran s'ouvre sur quatre réponses — **À repiquer**, **À endurcir**, **Prêts pour le plan**, **À semer** — puis sur la liste des lots « du plus urgent au plus calme », chacun avec son échéance (« Repiquage +6 j », « Endurcissement J+3/7 », « Dormant ») et un bouton d'action.

Rien de cela n'est calculé aujourd'hui. Cette US crée le **calcul des échéances**, côté serveur, à un seul endroit, en lecture seule, à partir de ce que les US précédentes ont posé : le délai semis → godet (US-213), le délai avant plantation (`repiquage`, US-068), l'emplacement et son type (US-208, US-210, US-211), la levée (US-212). Elle ne dessine rien : US-215, US-216 et US-218 affichent.

**Les échéances d'un lot, à la date de référence :**

| Échéance | Règle | Donnée requise |
|---|---|---|
| **Repiquage en godet attendu** | date de semis + délai semis → godet (fourchette). Tant que le lot n'a aucun plant en godet : *dans N j* avant la fourchette, *à repiquer* dedans, *en retard de N j* après sa fin | US-213 |
| **Mise en terre prévue** | date de semis + délai avant plantation (fourchette). Concerne un lot qui a des plants en godet | délai `repiquage` (US-068) |
| **Endurcissement** (arbitrage A11) | compte à rebours de **7 jours** avant le début de la mise en terre prévue, « J+n sur 7 », pour un lot en **pépinière chaude ou de type inconnu**. Un lot en **pépinière froide** s'endurcit sur place : « en pépinière froide », pas de compte à rebours. Un déplacement vers une pépinière froide (US-211) démarre l'endurcissement à sa date | US-208, US-211 |
| **Lot dormant** | le lot a encore des graines en germination ou des godets, **aucun geste** depuis **60 jours**, et sa mise en terre prévue est dépassée ou inconnue | journal du lot |

**Action suggérée**, une par lot : *Repiquer* (repiquage à faire ou en retard) · *Noter la levée* (en germination, avant la fourchette de repiquage, aucune levée notée) · *Mettre en terre* (endurcissement en cours ou terminé, ou mise en terre prévue atteinte) · *Clôturer* (dormant) · aucune.

**Critères d'acceptance :**

*Le calcul*
- [ ] CA1 : Les échéances, l'action suggérée et l'ordre d'urgence sont calculés dans **un seul module de service**, en lecture seule, à la date de référence. La durée d'endurcissement (7 jours) et le seuil de dormance (60 jours) sont des **décisions produit** écrites dans un bloc unique, corrigeables en un diff, comme le barème de la confiance (US-178 / CA3)
- [ ] CA2 : Une fourchette reste une fourchette : « repiquage attendu entre le 11 et le 16 septembre », jamais une date unique fabriquée. Le retard se compte depuis la **fin** de la fourchette
- [ ] CA3 : **Sans la donnée requise, pas d'échéance** et la raison est rendue (« délai semis → godet non renseigné pour le chou »), jamais une valeur par défaut (RT2). Un lot sans échéance calculable n'est ni en retard ni dormant par défaut
- [ ] CA4 : L'endurcissement suit la table : chaude ou inconnue → compte à rebours ; froide → « en pépinière froide » ; déplacé vers une pépinière froide → compte à rebours démarré au jour du déplacement. Le compte à rebours ne dépasse jamais « J+7 sur 7 »
- [ ] CA5 : Un lot est **dormant** selon la table ; un lot dont les godets attendent une mise en terre prévue et non encore atteinte ne l'est jamais, quelle que soit la durée sans geste
- [ ] CA6 : **Ordre d'urgence** : les retards, du plus grand au plus petit ; puis les échéances à venir, de la plus proche à la plus lointaine ; puis les lots sans échéance ; les lots dormants en dernier

*La lecture*
- [ ] CA7 : `GET /pepiniere/lots` ajoute à chaque lot ses échéances, son action suggérée et son rang d'urgence, sans retirer ni renommer aucun champ
- [ ] CA8 : Elle ajoute un **résumé** pour le bandeau de l'écran : lots et plants **à repiquer** ; lots **à endurcir** ; plants **prêts pour le plan** (godets disponibles des lots dont la mise en terre prévue est atteinte ou inconnue), accompagnés des rangs libres du Plan par parcelle quand US-198 est livrée ; cultures **à semer** — la date de référence est **dans** la fenêtre de semis en pépinière de la zone (R1 à son maximum, lue par la même évaluation que la confiance, US-178 ; le mois adjacent ne suffit pas) et aucun lot de cette culture n'est en cours
- [ ] CA9 : Une seule requête, une seule lecture météo au plus pour « À semer » (cache d'US-182) ; aucune requête par lot
- [ ] CA10 : Lecture seule : aucun geste n'est créé, même pour un lot dormant ; aucun stock ne change

*Définition de terminé*
- [ ] CA11 : Une fiche de domaine `docs/domaines/pepiniere.md` consigne la table des échéances, les deux décisions produit, l'ordre d'urgence et les cas sans donnée ; elle entre dans la table de `docs/domaines/README.md`
- [ ] CA12 : La fiche `pepiniere-par-lot.md` explique au jardinier ce que veulent dire « à repiquer », « à endurcir », « prêts pour le plan », « dormant », et pourquoi une échéance peut manquer (US-099 / CA9)
- [ ] CA13 : Des tests couvrent chaque ligne de la table et chaque action suggérée, les fourchettes, l'absence de chaque donnée, les trois cas d'endurcissement, la borne J+7, la dormance et son exclusion, l'ordre d'urgence, le résumé, la date de référence passée, l'isolation entre potagers

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture)
- Migration BDD requise : **non**
- Dépendances : **US-213** (délai semis → godet), **US-208** (type de pépinière), **US-210** (emplacement) — bloquantes pour les échéances qu'elles portent ; US-211 (déplacement), US-212 (levée), US-209 (numéro), US-198 (rangs libres) enrichissent sans bloquer
- Consommateurs : US-215 (Aujourd'hui), US-216 (fiche du lot), US-218 (Calendrier)
- Impact tokens : zéro
- Point de vigilance : les **deux décisions produit** (7 jours, 60 jours) sont des hypothèses à confirmer par le PO (plan des épics § 10) ; un test les fige pour qu'elles ne changent pas par accident
- Point de vigilance : « prêts pour le plan » ne dit rien de la place en m² — la géométrie est reportée ; il dit des plants et des rangs libres, pas une surface
- Wireframes : v1 § 3 (bandeau des trois réponses, note « La question n° 1 ») ; v2 § 3 (bandeau à quatre cartes, liste triée, notes « Le lot dormant » et « L'endurcissement »)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Lot en retard de repiquage
  Given le lot 128, chou frisé semé le 1er septembre, sans plant en godet
  And un délai semis → godet de 10 à 12 jours pour le chou
  When je lis les lots au 19 septembre
  Then le lot 128 est en retard de repiquage de 6 jours
  And son action suggérée est "Repiquer"

Scénario: Délai inconnu
  Given le lot 131, tomate cerise, sans délai semis → godet au référentiel
  When je lis les lots
  Then le lot 131 n'a pas d'échéance de repiquage
  And la raison "délai semis → godet non renseigné pour la tomate" est rendue

Scénario: Endurcissement en pépinière chaude
  Given le lot 119, poireaux en godet dans la serre, pépinière chaude
  And sa mise en terre prévue commence le 26 septembre
  When je lis les lots au 22 septembre
  Then le lot 119 est en endurcissement, J+3 sur 7
  And son action suggérée est "Mettre en terre"

Scénario: Pépinière froide
  Given le même lot 119 déplacé au châssis froid le 10 septembre
  When je lis les lots au 22 septembre
  Then le lot 119 est "en pépinière froide", sans compte à rebours

Scénario: Lot dormant
  Given le lot 103, basilic semé le 12 juin, 6 godets restants, aucun geste depuis 70 jours
  And sa mise en terre prévue est dépassée
  When je lis les lots au 19 septembre
  Then le lot 103 est dormant, en fin de liste, avec l'action "Clôturer"

Scénario: À semer
  Given la fenêtre de semis en pépinière de la laitue d'hiver est ouverte au 19 septembre
  And aucun lot de laitue n'est en cours
  When je lis le résumé
  Then la laitue d'hiver figure parmi les cultures à semer
```

**Labels GitHub :** `us`, `backend`, `pepiniere`, `analyse`
