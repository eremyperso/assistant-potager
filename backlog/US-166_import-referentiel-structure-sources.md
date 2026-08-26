**ID :** US-166
**Titre :** Importer le référentiel structuré et tracer la source de chaque donnée
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant qu'administrateur de la plateforme
Je veux que la connaissance importée entre en base par un chemin unique, rejouable, et que chaque donnée sache d'où elle vient
Afin de pouvoir répondre à tout moment à « d'où sort cette information ? » et « que puis-je publier ? », et de retirer proprement une source dont la licence poserait problème

> **⚠️ US réduite le 25/08/2026** — voir `docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §1.
> La forme initiale (« pipeline d'ingestion + traçabilité », 8 points) **recouvrait US-098**, qui
> livre déjà les tables de connaissance, la recherche plein texte, l'isolation et **l'outil
> d'ingestion du narratif**, ainsi que les CA3 et CA4 d'US-140 sur la source et l'attribution
> affichée. Elle est donc ramenée à ce qu'elle seule apporte : l'import du **référentiel
> structuré** — attributs, identités, relations — et le registre de sources qui le trace.
> Estimation ramenée de 8 à **5 points**. « Aucun second mécanisme », comme le pose US-140.

**Contexte fonctionnel :**
Septième US de l'`ÉPIC 6`, rang B2 de la piste B — première brique livrable après US-067 amendée
(`docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.4).

Deux sources, tranchées et closes (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1,
option A) : **Wikidata** en CC0 pour la taxonomie, **E-Phy / ANSES** en Licence Ouverte pour les
usages et le cadre légal. Rien d'autre. Permapeople, Wikipédia FR, Plants For A Future, Practical
Plants et Growstuff sont exclus de tout import — leur clause de partage à l'identique
contaminerait le corpus de fiches, qui doit rester intégralement propriétaire pour que la
trajectoire commerciale reste ouverte sans réexamen juridique.

**Le principe d'architecture que cette US matérialise :** *ingestion hors ligne, exécution hors
réseau.* Aucune API externe n'est appelée pendant qu'un jardinier attend une réponse — pour la
latence (remplacer un aller-retour Groq par un aller-retour Wikidata annule le gain de la V2), pour
la disponibilité (une fiche culture ne peut pas dépendre de la santé d'un service tiers gratuit ;
Trefle a cessé son service en 2021 avant de revenir), et pour le réseau du poste d'administration.

**Critères d'acceptance :**

*Le registre de sources*
- [ ] CA1 : Un **registre de sources** enregistre, pour chaque source : son code, sa **licence**, l'**attribution** à afficher, son URL et la date du dernier import. Toute donnée importée y est rattachée — l'attribution est une obligation par enregistrement, pas une ligne de README
- [ ] CA2 : Le registre porte l'indicateur **`partageable`**, qui exclut d'un éventuel export toute source contaminante. Il vaut `true` pour l'ensemble des sources retenues aujourd'hui : la colonne existe parce qu'elle rend l'option B de licence **réversiblement atteignable** si une source CC-BY-SA devenait un jour indispensable sur les associations, pour un coût de deux lignes de migration
- [ ] CA3 : Le registre reconnaît aussi les origines **non importées** — saisie manuelle, rédaction interne. Une donnée saisie par le jardinier est tracée au même titre qu'une donnée importée ; il n'existe aucune donnée sans origine
- [ ] CA4 : Retirer une source doit permettre d'**identifier en une requête tout ce qui en dérive**. C'est la seule façon de tenir l'engagement de conformité six mois après l'import, quand plus personne ne se souvient de ce qui venait d'où

*L'import*
- [ ] CA5 : L'import est **hors ligne, idempotent et rejouable** : le lancer deux fois de suite ne crée aucun doublon et n'écrase aucune correction humaine (US-161 / CA6). Les fichiers E-Phy sont mis à jour chaque semaine — rejouer doit être une opération banale
- [ ] CA6 : **Aucune source hors socle n'est ingérée** — ni « en attendant », ni « pour tester ». Toute tentative d'import d'un contenu dont la licence n'est pas établie, ou est établie hors socle, est **refusée** et rien n'est créé
- [ ] CA7 : L'import **ne crée aucune configuration de culture nouvelle**. Il enrichit celles qui existent. La mesure du 25/08/2026 justifie cette contrainte : **14 des 54 configurations existantes ne portent déjà aucun événement**, et pré-semer un catalogue peuplerait les écrans du jardinier de cultures fantômes
- [ ] CA8 : Aucun appel réseau n'a lieu dans un chemin de réponse au jardinier. Les données sources sont récupérées, versionnées et rejouées hors ligne

*Le rapport de couverture — le livrable qui pilote la suite*
- [ ] CA9 : Chaque import produit un **rapport de couverture** qui distingue explicitement trois états : **couvert**, **non couvert**, et **configuré mais jamais utilisé**. C'est ce rapport, et non une intuition, qui décide de la saisie manuelle résiduelle et de l'extension du périmètre au-delà des dix cultures
- [ ] CA10 : Le rapport signale les **cultures suspectes** — présentes dans les événements mais inconnues de la configuration. La production en porte un cas d'école : `radi`, né de la phrase « Y a t il des radis dans mon jardin » enregistrée comme un événement au lieu d'être reconnue comme une question. Une culture fantôme issue d'un échec de parsing ne doit **jamais** déclencher la création d'une fiche
- [ ] CA11 : Le rapport signale les **synonymes probables** pour revue humaine, sans jamais fusionner automatiquement. Les cas mesurés : `laitue` / `salade`, `haricot` / `haricot grimpant`, et les **dix libellés de cucurbitacées** qui cumulent à eux seuls plus d'événements que la tomate. Le rapprochement par nom vernaculaire est la clé la moins fiable des trois — jamais sans relecture
- [ ] CA12 : Le **taux d'appariement automatique** est publié par le rapport. En dessous d'environ 70 % sur les cultures réellement présentes, l'import automatique perd son intérêt face à la saisie directe : le repli est une table de correspondance manuelle sur les dix cultures du périmètre — travail borné, fait une seule fois

*Tests*
- [ ] CA13 : Des tests couvrent l'import rejoué sans doublon, le refus d'une source hors socle, la préservation d'une correction humaine lors d'un rejeu, l'absence de création de configuration de culture, la production du rapport de couverture dans ses trois états, et la remontée d'une culture suspecte

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : outillage d'administration — aucune surface utilisateur nouvelle
- Migration BDD requise : **oui** — registre de sources et rattachement depuis les tables du référentiel. Idempotente, rollback documenté
- Dépendances : **US-067 amendée** (la table de familles est la première cible d'import). **Aucune dépendance bloquante au moteur V2** : cette US porte son propre script d'import structuré et peut être livrée avant US-098. Prérequis de **US-161**, **US-162** et **US-163**, qui toutes rattachent leur donnée à son registre
- **Frontière avec US-098, à ne pas franchir :** US-098 ingère du **narratif** dans les tables de connaissance et le rend cherchable. Cette US importe du **structuré** — colonnes et arêtes — dans les tables du référentiel. Deux natures de donnée, deux destinations, un seul principe commun de traçabilité. Aucun outil n'est réécrit en double
- **Arbitrage tranché — option A sur la licence :** le corpus reste 100 % propriétaire, sans contrainte de publication ni de partage à l'identique, et l'interface n'a qu'un seul régime d'attribution à maintenir. Contrepartie assumée : les associations sont **saisies** et non importées (US-163)
- **Arbitrage tranché — le rapport de couverture est un livrable, pas un journal :** c'est l'instrument de décision de tout l'épic. Sans lui, l'extension du périmètre se ferait au fil de l'envie d'exhaustivité — le travers explicitement écarté par l'arbitrage des dix cultures

**Notes techniques (pour Persona Developer) :**
- Le script vit dans `tools/`, **jamais** dans `migrations/` : il est rejouable et ne fait pas partie de la séquence de migration
- ⚠️ Toute statistique tirée de l'historique pour le rapport de couverture doit **exclure les bulletins `[AUTO-METEO]`** : 96 des 321 événements de production, soit 30 % de bruit machine
- 🔶 Les conditions d'utilisation de `data.eppo.int` restent à lire avant tout import de masse de codes EPPO — préalable porté par US-162 / CA7, mais c'est ce script qui les consommerait

**Estimation :** 5 points *(8 initialement, réduite le 25/08/2026 — recouvrement avec US-098)*

**Scénario Gherkin :**
```gherkin
Scénario: Import rejoué sans doublon
  Given un import du référentiel structuré déjà réalisé
  When le script est rejoué sur une version mise à jour de la source
  Then aucun doublon n'est créé
  And les nouvelles entrées sont ajoutées

Scénario: Correction humaine préservée
  Given un attribut de culture corrigé à la main par le jardinier
  When l'import est rejoué
  Then la valeur corrigée est conservée

Scénario: Source hors socle refusée
  Given un jeu de données sous licence CC-BY-SA
  When son import est tenté
  Then il est refusé
  And aucune donnée n'est créée

Scénario: Aucune culture fantôme créée
  Given un référentiel source couvrant des cultures absentes du potager
  When l'import est exécuté
  Then aucune configuration de culture nouvelle n'est créée

Scénario: Culture suspecte signalée
  Given un événement portant la culture "radi", inconnue de la configuration
  When le rapport de couverture est produit
  Then cette culture est signalée comme suspecte
  And aucune fiche n'est créée pour elle

Scénario: Synonymes soumis à revue
  Given les cultures "laitue" et "salade" toutes deux présentes en base
  When le rapport de couverture est produit
  Then elles sont signalées comme synonymes probables
  And aucune fusion automatique n'a lieu

Scénario: Traçabilité d'une source à retirer
  Given une source dont la licence devient litigieuse
  When on interroge la base sur cette source
  Then toutes les données qui en dérivent sont identifiées

Scénario: Aucun appel réseau en réponse
  Given un jardinier qui consulte une fiche culture
  When la réponse est produite
  Then aucune API externe n'a été appelée
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `referentiel`, `outillage`
