**ID :** US-161
**Titre :** Enrichir la configuration de culture des attributs agronomiques de fiche
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que chaque culture porte ses caractéristiques de conduite — exposition, besoin en eau, profondeur de semis, rusticité
Afin que l'application puisse me les restituer sans les inventer, et que je puisse les corriger quand elles ne correspondent pas à mon terrain

**Contexte fonctionnel :**
Deuxième US de l'`ÉPIC 6`, déclinaison de `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md`
§4.1, arbitrée par `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` et ordonnancée par
`docs/PLAN_PRODUCTION_EPIC6_REFERENTIEL.md` §4.4 (piste B, rang B3).

`culture_config` porte aujourd'hui quatre informations : type d'organe récolté, description
agronomique libre, espacement, surface au sol. C'est trop peu pour composer une fiche, et c'est la
raison pour laquelle trois documents de conception distincts butent sur le même mur. Cette US
ajoute les attributs manquants — **rien que des attributs**, c'est-à-dire de la donnée qui
s'affiche, se filtre et se trie sans jamais passer par un modèle de langage.

**La règle qui gouverne le découpage de tout l'épic, et donc cette US :** *tout ce qui peut être
une colonne ou une arête ne doit jamais être un fragment de texte.* Un attribut rendu par une
recherche plein texte avec un score de 0,72 est une régression fonctionnelle : la profondeur de
semis d'un radis est un fait, pas une probabilité.

Cette US ne crée aucun écran. Elle remplit le contenu que la fiche courte d'US-164 restituera au
bot en zéro jeton, et que la vue « Cultures » du Lot E (`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.3)
consommera ensuite.

**Critères d'acceptance :**

*Le modèle*
- [ ] CA1 : `culture_config` s'enrichit d'attributs agronomiques de conduite — au minimum **exposition**, **besoin en eau**, **profondeur de semis** et **rusticité minimale**. Tous sont **nullables**, aucune colonne existante n'est supprimée ni renommée : c'est l'invariant projet de migration incrémentale non cassante
- [ ] CA2 : Les attributs qualitatifs prennent leurs valeurs dans un **vocabulaire fermé** — exposition parmi `plein soleil` / `mi-ombre` / `ombre`, besoin en eau parmi `faible` / `moyen` / `élevé`. Ce ne sont pas des champs de texte libre : un attribut destiné à être filtré et trié qui accepte n'importe quelle chaîne ne peut plus l'être, et la vue Cultures du Lot E devrait renormaliser à l'affichage ce qui aurait dû l'être à l'écriture
- [ ] CA3 : Chaque valeur renseignée porte **sa source**, rattachée au référentiel de traçabilité d'US-166. Aucun attribut orphelin : une valeur dont on ne sait plus d'où elle vient ne peut ni être défendue au jardinier, ni retirée proprement si sa source devient litigieuse
- [ ] CA4 : Un attribut non renseigné **s'affiche comme non renseigné**. Il n'est jamais deviné, jamais remplacé par une valeur moyenne, jamais complété par un modèle de langage — application directe du principe d'honnêteté de l'Épic 5 §4

*La saisie et la correction*
- [ ] CA5 : Le jardinier peut **corriger un attribut depuis le bot**, sans livraison ni intervention en base, exactement comme il corrige la famille botanique (US-067 / CA4). La commande confirme l'ancienne et la nouvelle valeur
- [ ] CA6 : Une correction du jardinier **prime sur toute reprise d'import ultérieure** : rejouer l'import d'US-166 ne doit jamais écraser une valeur saisie à la main. Sans cette garantie, la première mise à jour du référentiel efface silencieusement le travail de terrain
- [ ] CA7 : Le pré-remplissage est limité aux **dix cultures du périmètre initial** (US-140 / CA1) et **ne crée aucune configuration de culture nouvelle**. La mesure du 25/08/2026 établit que **14 des 54 configurations existantes ne portent aucun événement** : peupler les écrans de cultures jamais cultivées est un risque constaté, pas théorique

*Les frontières — trois vérités concurrentes à ne pas créer*
- [ ] CA8 : Aucun attribut de **calendrier** n'entre ici — ni fenêtre de semis, ni durée de germination, ni date. Ces données appartiennent au référentiel calendrier d'US-068, qui les décline par zone climatique et les recale sur les événements réels. La frontière est celle du CA7 d'US-140, mot pour mot
- [ ] CA9 : Aucune **relation** n'entre ici — ni association, ni règle de rotation, ni bioagresseur. Ce sont des arêtes, pas des colonnes : elles relèvent d'US-162 et d'US-163
- [ ] CA10 : **Aucun chiffre n'est produit par un modèle de langage.** Profondeur de semis et rusticité viennent exclusivement de l'import d'US-166 ou de la saisie du jardinier. C'est le garde-fou (a) de l'arbitrage 2 (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.2), et il s'applique ici sans exception

*Non-régression et tests*
- [ ] CA11 : Aucune régression sur les lectures existantes de `culture_config` — type d'organe de récolte, calcul de stock végétatif/reproducteur, écran Stocks, écran Statistiques et statistiques du bot conservent exactement leur comportement, ce que les tests existants vérifient sans modification
- [ ] CA12 : Des tests couvrent le pré-remplissage, la correction depuis le bot, la primauté de la correction sur un import rejoué (CA6), une culture sans aucun attribut renseigné, le refus d'une valeur hors vocabulaire fermé (CA2), et la non-régression du CA11

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation et enregistrement (métadonnée de culture)
- Migration BDD requise : **oui** — colonnes nullables sur `culture_config` et rattachement à la source. Idempotente, rollback documenté. ⚠️ **Se coordonner avec US-067 et US-068**, qui touchent la même table : trois migrations concurrentes sur `culture_config` sont exactement le travers signalé en Épic 5 §9
- Dépendances : **US-067 amendée** (table de référence des familles, socle de l'épic) et **US-166** (traçabilité des sources, pour le CA3). Prérequis de **US-164**, qui n'a rien à afficher sans elle
- **Arbitrage tranché — vocabulaire fermé plutôt que texte libre :** la tentation est d'accepter n'importe quelle chaîne « pour ne pas bloquer la saisie ». Elle coûte cher deux écrans plus loin : un filtre sur l'exposition devient impossible, et le tri de la vue Cultures perd son sens
- **Arbitrage tranché — la correction du jardinier gagne toujours (CA6) :** un référentiel importé décrit une moyenne nationale ; le jardinier décrit son terrain. Quand les deux divergent, c'est le terrain qui a raison
- Point de vigilance : ces attributs sont **partagés** (`potager_id` nul), comme les 54 lignes actuelles de `culture_config` — la mesure du 25/08/2026 confirme qu'aucune ne porte de `potager_id`. Une correction bénéficie donc à tous les potagers, ce qui est cohérent pour un fait agronomique et doit être assumé comme tel

**Notes techniques (pour Persona Developer) :**
- Le pré-remplissage se fait par le script d'import d'US-166, pas par un script à part — « aucun second mécanisme », comme le pose US-140
- La liste nominative des dix cultures est celle du CA1 d'US-140. ⚠️ Elle est mesurée sur la base de développement et **doit être reconfirmée sur la production** avant le pré-remplissage : les rangs 9 et 10 y sont départagés par ordre alphabétique entre six cultures à égalité

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Attribut restitué sans appel au modèle
  Given une culture "courgette" dont l'exposition est "plein soleil" et le besoin en eau "élevé"
  When ces attributs sont lus pour composer une fiche
  Then ils sont restitués tels quels
  And aucun appel à un modèle de langage n'a lieu

Scénario: Attribut non renseigné
  Given une culture "topinambour" dont aucun attribut agronomique n'est renseigné
  When sa fiche est composée
  Then chaque attribut absent se lit comme non renseigné
  And aucune valeur n'est devinée ni moyennée

Scénario: La correction du jardinier prime sur l'import
  Given une culture "carotte" dont la profondeur de semis a été corrigée à la main par le jardinier
  When le script d'import du référentiel est rejoué
  Then la valeur corrigée est conservée

Scénario: Valeur hors vocabulaire fermé refusée
  Given une tentative d'enregistrer l'exposition "au soleil le matin"
  When la valeur est validée
  Then elle est refusée
  And l'attribut conserve sa valeur précédente

Scénario: Aucune date dans les attributs
  Given le référentiel d'attributs livré
  When les colonnes de culture_config sont relues
  Then aucune ne porte de fenêtre de semis ni de durée de culture

Scénario: Aucun impact sur les écrans existants
  Given un potager avec des cultures végétatives et reproductrices
  When l'écran Stocks, l'écran Statistiques et les statistiques du bot sont consultés
  Then ils affichent exactement les mêmes valeurs qu'avant cette évolution
```

**Labels GitHub :** `us`, `sprint-epic6-referentiel`, `backend`, `cultures`, `referentiel`
