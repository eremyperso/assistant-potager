# 🧬 Assistant Potager — Référentiel de connaissance des cultures

> **Statut :** 📝 Document de cadrage conceptuel — à décliner en US par l'agent Persona PO
> **Rédigé le :** 25/08/2026
> **Portée :** la connaissance *sur les légumes* — nature de la plante, bioagresseurs, associations,
> rotation — et son intégration à tous les niveaux de service de l'application.
> **Complète :** `ARCHITECTURE_CIBLE_V2_reponses.md` (§4 famille A), `EPIC_CALENDRIER_CULTURAL.md`
> (risque 🔴 « source du référentiel »), `ANALYSE_REFONTE_UI_WEB_2026.md` (§5.3 vue Cultures),
> `BACKLOG_US_MULTITENANT.md` (US-140).
> **Ne remplace aucun** de ces documents : il tranche le point qu'ils laissent tous ouvert.
> **Niveau :** conceptuel — schémas de tables et pseudo-flux, pas de code d'implémentation.
> **Convention de lecture :** ✅ fait établi · 🔶 hypothèse à valider · 🧪 à tester · ⚖️ arbitrage PO requis.

---

## 1. Le problème

L'application est un **journal d'événements** exemplaire : elle sait tout du réel du potager — quoi,
quand, où, combien. Elle ne sait **rien de la plante elle-même**. `culture_config` porte quatre
informations (type d'organe récolté, description agronomique libre, espacement, surface au sol),
et rien d'autre.

Conséquence : trois documents de conception distincts butent tous sur le même mur, chacun de son côté.

| Document | Ce qu'il attend | Ce qu'il constate |
|---|---|---|
| `EPIC_CALENDRIER_CULTURAL.md` (§9) | Fenêtres et durées par culture | Risque 🔴 « source du référentiel », préalable bloquant à US-068 |
| `ARCHITECTURE_CIBLE_V2_reponses.md` (§4.2) | Famille A du RAG : fiches, maladies, associations | 🔶 « point à trancher **avant** de démarrer la famille A » |
| `ANALYSE_REFONTE_UI_WEB_2026.md` (§5.3) | Fiche culture agrégée pour la vue Cultures | « schéma de métadonnées à définir », « choix non tranché à ce stade » |

**Ce n'est pas trois problèmes, c'est un seul.** Traité trois fois séparément, il produira trois
référentiels partiels, trois schémas incompatibles et trois arbitrages de licence divergents. Ce
document le traite une fois, pour les trois.

Et il pose la question de fond, qui n'est pas technique : *l'application n'a rien à dire au jardinier
sur ce qu'il cultive.* Elle enregistre « mildiou » dans un commentaire sans savoir ce qu'est le
mildiou, ni qu'il touche aussi les pommes de terre de la parcelle d'à côté, ni qu'il est favorisé
par la pluviométrie qu'elle affiche déjà sur son propre dashboard.

---

## 2. Analyse de besoin

### 2.1 Les cinq points de consommation

La connaissance ne sert pas un écran, elle en irrigue cinq. C'est **la contrainte de conception
principale** : un modèle taillé pour un seul de ces usages sera inadapté aux quatre autres.

| # | Consommateur | Forme attendue | Contrainte dominante |
|---|---|---|---|
| **1** | **Bot Telegram — fiche** (`/fiche tomate`) | 10 lignes, MarkdownV2, lisible sur iPhone en plein champ | Concision, 0 latence, 0 token |
| **2** | **Bot Telegram — question** (étage 2 RAG) | Passage pertinent + source | Rappel sur vocabulaire imprécis |
| **3** | **PWA — vue Cultures** (Lot E, §5.3) | Fiche riche : famille, exposition, eau, calendrier, associations, bioagresseurs | Complétude, structure stable pour le rendu |
| **4** | **PWA — écran Plan / parcelle** | Avertissement contextuel : « solanacées 2 ans de suite », « ne pas associer à… » | **Calculable**, donc jointure SQL |
| **5** | **Moteur d'insights** (Annexe A V2) | Règle déclenchable : culture × météo × historique → alerte | **Calculable** + déterministe, 0 token |

Les points 4 et 5 sont ceux qui décident du modèle. Les points 1, 2 et 3 se satisferaient de texte
libre ; **4 et 5 exigent de la donnée jointe**. Un moteur de règles ne peut pas déclencher sur une
phrase.

### 2.2 Matrice besoin → nature de donnée → étage de la cascade

Chaque ligne est une question réelle que le jardinier pose ou posera. La colonne « étage » renvoie
à la cascade de `ARCHITECTURE_CIBLE_V2_reponses.md` §2.

| Question type | Nature de donnée requise | Étage | Coût LLM |
|---|---|---|---|
| « c'est quoi une courgette, ça pousse comment ? » | Attributs + narratif court | 0bis / 2 | 0 |
| « quelle famille pour le chou ? » | Attribut (fait taxonomique) | 1 | 0 |
| « je peux planter des tomates ici ? » | **Relation** rotation + historique parcelle | 1 | 0 |
| « avec quoi associer mes carottes ? » | **Relation** association | 1 | 0 |
| « qu'est-ce qui attaque les poireaux ? » | **Relation** culture × bioagresseur | 1 | 0 |
| « mes feuilles de tomate ont des taches brunes » | **Relation** symptôme × bioagresseur, puis narratif | 1 → 2 | 0 |
| « comment je traite le mildiou ? » | Narratif + **relation** légale (produit autorisé jardin amateur) | 2 | 0 |
| « mes courgettes jaunissent et j'ai beaucoup arrosé » | Narratif + événements + météo → synthèse | 3 | réel |

**Lecture de cette matrice :** sur huit besoins, **sept se résolvent à 0 token** — mais seulement si
la connaissance est modélisée en attributs et en relations. Modélisée en texte, les huit remontent
à l'étage 3, et l'application redevient un chatbot cher.

### 2.3 Ce que le besoin n'est pas — périmètre exclu

- **Une encyclopédie botanique.** L'objectif n'est pas de couvrir 400 000 espèces mais les ~30 à 40
  cultures réellement présentes en base. Toute source promettant l'exhaustivité mondiale est un
  faux ami : elle apporte du volume taxonomique et zéro conseil potager.
- **Un identificateur de maladie par photo.** Reste au backlog 🟢 (Groq Vision). Ce document prépare
  toutefois le socle que ce futur module consommera : sans référentiel de bioagresseurs, une
  reconnaissance d'image ne peut rien restituer d'exploitable.
- **Un conseil de traitement engageant.** L'application indique ce qui est *légalement utilisable en
  jardin amateur* et renvoie à la source officielle. Elle ne prescrit pas de dose.
- **Le calendrier et les durées** — c'est l'Épic 5, qui vit dans le **même référentiel** mais reste
  un périmètre d'US distinct. Ce document lui fournit sa table d'accueil, pas son contenu.

---

## 3. La décision structurante : trois natures de connaissance

### 3.1 Attributs, relations, narratif

C'est le cœur du document. La connaissance sur une culture n'est **pas homogène** et ne doit pas
partager un support unique.

```
                        CONNAISSANCE SUR UNE CULTURE
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼                           ▼                           ▼
   ATTRIBUTS                   RELATIONS                    NARRATIF
   (colonnes)                  (graphe)                     (chunks RAG)

   famille botanique           culture × culture            « le mildiou apparaît
   exposition                    (association/antagonisme)     par temps doux et
   besoin en eau               culture × bioagresseur         humide, taches
   profondeur de semis         culture × famille              huileuses puis
   espacement ✅               bioagresseur × symptôme        brunes sur les… »
   type d'organe ✅            famille × famille
   durées      [Épic 5]          (rotation)
   fenêtres    [Épic 5]

   → affichage direct          → CALCUL, alerte,            → recherche FTS,
     0 token                     avertissement contextuel     contexte LLM
                                 0 token                       0 token en lecture
```

| Nature | Volume | Support | Sert à | Qui la produit |
|---|---|---|---|---|
| **Attributs** | ~40 lignes × ~15 colonnes | Tables relationnelles | Afficher, filtrer, trier | Open data + saisie |
| **Relations** | ~400 à 800 arêtes | Tables de liaison | **Calculer, alerter, avertir** | Open data + saisie |
| **Narratif** | ~150 à 300 chunks | `knowledge_chunks` (famille A) | Expliquer, contextualiser le LLM | Rédaction curée |

### 3.2 Pourquoi le « tout RAG » échoue ici

La tentation naturelle est de tout verser dans `knowledge_chunks` : une fiche par culture, une par
maladie, et laisser la recherche faire le tri. Trois raisons de ne pas le faire.

1. **Un RAG ne joint pas.** « Quelles cultures puis-je planter sur la parcelle NORD, sachant que j'y
   ai eu des tomates l'an dernier et des pommes de terre il y a deux ans ? » est une requête de
   graphe croisée avec l'historique. Aucune recherche vectorielle ou lexicale ne produira cette
   réponse — au mieux elle retrouvera un paragraphe générique sur la rotation des solanacées.
2. **Un RAG ne déclenche pas.** Le moteur d'insights de l'Annexe A a besoin d'un prédicat booléen
   (`famille_precedente = famille_envisagee`), pas d'un passage de texte. Une alerte proactive ne
   peut pas naître d'un score de similarité.
3. **Un RAG approxime là où la donnée est exacte.** La famille botanique de la tomate est un fait.
   Le retourner avec un score de confiance de 0,72 est une régression fonctionnelle.

**Règle retenue :** *tout ce qui peut être une colonne ou une arête ne doit jamais être un chunk.*
Le narratif ne porte que ce qui est irréductiblement du texte — description, symptômes, conduite à
tenir. Corollaire : le corpus narratif à rédiger est **beaucoup plus petit** qu'il n'y paraît, ce qui
allège directement le risque 🔴 de l'Épic 5.

### 3.3 Les deux niveaux de fiche découlent du modèle, ils ne se conçoivent pas

Le besoin exprimé — « fiche simplifiée ou détaillée » — n'est pas un choix éditorial à faire deux
fois. C'est une conséquence directe de la séparation ci-dessus.

| Niveau | Composition | Canal | Coût |
|---|---|---|---|
| **Fiche courte** | Attributs + relations, rendus par gabarit | Bot Telegram, tuile PWA | **0 token, jamais fausse** |
| **Fiche détaillée** | Fiche courte + chunks narratifs + calendrier recalé (Épic 5) | PWA vue Cultures | **0 token** en lecture |

La fiche courte est **générée**, pas rédigée. Elle est donc toujours cohérente avec la base, et une
correction du référentiel se propage instantanément aux deux niveaux. Aucun texte à maintenir en
double.

---

## 4. Le modèle cible

### 4.1 Vue d'ensemble

```
culture_config  ✅ existante — devient le pivot du référentiel
├── nom, type_organe_recolte ✅, description_agronomique ✅
├── espacement ✅, surface_m2 ✅
├── famille_id            → FK famille_botanique            [US-160, absorbe US-067]
├── exposition            'plein soleil' | 'mi-ombre'…      [US-161]
├── besoin_eau            'faible' | 'moyen' | 'élevé'      [US-161]
├── profondeur_semis_cm                                     [US-161]
├── rusticite_min_c                                         [US-161]
└── (itinéraires, fenêtres, durées)                         [Épic 5 — US-068]

famille_botanique                                           [US-160]
├── nom               'Solanacées', 'Cucurbitacées'…
├── nom_scientifique  'Solanaceae'
├── delai_retour_ans  INT   ← LE champ qui rend la rotation calculable
└── note_rotation     TEXT

bioagresseur                                                [US-162]
├── code_eppo         VARCHAR UNIQUE NULL  ← clé pivot inter-sources
├── nom_commun_fr     'mildiou de la tomate'
├── nom_scientifique  'Phytophthora infestans'
├── categorie         'champignon'|'insecte'|'bacterie'|'virus'|'abiotique'|'carence'
└── potager_id        INT NULL  ← NULL = partagé (pattern culture_config)

culture_bioagresseur          (relation)                    [US-162]
├── culture_id, bioagresseur_id
├── frequence         'courant' | 'occasionnel' | 'rare'
└── periode_risque    VARCHAR NULL   -- 'juin-septembre'

symptome                                                    [US-165]
├── libelle           'taches brunes sur feuilles'
├── organe            'feuille'|'fruit'|'tige'|'racine'|'plant entier'
└── synonymes         TEXT[]  ← 'feuilles qui jaunissent' → chlorose

symptome_bioagresseur         (relation pondérée)           [US-165]
├── symptome_id, bioagresseur_id
└── poids             FLOAT  ← score de pré-diagnostic, jamais une certitude

association_culture           (relation orientée)           [US-163]
├── culture_a_id, culture_b_id
├── nature            'favorable' | 'defavorable' | 'neutre'
├── motif             TEXT court  -- 'répulsif mouche de la carotte'
└── niveau_preuve     'etabli' | 'traditionnel'  ← ⚠️ voir §6.3

referentiel_source            (traçabilité)                 [US-166]
├── code              'wikidata' | 'ephy_anses' | 'eppo' | 'saisie_manuelle' | 'redaction_interne'
├── licence           'CC0' | 'Licence Ouverte 2.0' | 'CC-BY-SA-4.0' | 'proprietaire'
├── attribution       TEXT   ← mention à afficher, obligatoire pour certaines licences
├── url, date_import
└── partageable       BOOLEAN  ← exclut de tout export les sources contaminantes

knowledge_documents / knowledge_chunks  [V2 §4.2] — famille A alimentée ici
└── + source_id       → FK referentiel_source     ⚠️ AJOUT au schéma V2
    + licence         (dénormalisé pour filtrage direct)
```

### 4.2 Trois ajustements au schéma de `ARCHITECTURE_CIBLE_V2_reponses.md`

1. **`knowledge_documents.source` devient une FK** vers `referentiel_source`, et non un champ texte
   libre. Motif : l'attribution est une obligation juridique par enregistrement, pas une ligne de
   README. Sans cette FK, il devient impossible six mois plus tard de retirer proprement une source
   dont la licence pose problème.
2. **Ajout de `licence` et `partageable`** — permet de répondre en une requête à « que puis-je
   publier / vendre / exporter ? ». Voir §6.3.
3. **`knowledge_chunks.culture` devient `culture_id`** (FK) plutôt qu'un libellé texte. Motif : c'est
   déjà l'erreur corrigée par `migration_v12` sur `evenements.parcelle`. Ne pas la refaire.

### 4.3 Articulation avec l'existant — ce qui ne bouge pas

- ✅ `culture_config` reste la table pivot. **Aucune colonne supprimée, aucune renommée.** Toutes les
  additions sont nullables — invariant projet « migration incrémentale non cassante ».
- ✅ Le pattern `potager_id NULL = connaissance partagée` est celui de la V2 §4.1, réappliqué tel
  quel à `bioagresseur` et aux tables de relation. Un potager peut ainsi ajouter *son* bioagresseur
  local sans polluer les 499 autres.
- ✅ L'action canonique `observation` existe déjà parmi les 12. Le pré-diagnostic (US-165) s'y
  rattache sans nouvelle action.
- ⚠️ **US-067 (famille botanique) est absorbée par US-160.** Le risque « migrations concurrentes sur
  `culture_config` » identifié en Épic 5 §9 disparaît : une seule US touche la colonne.
- ⚠️ **US-140 (base de connaissance cultures + RAG scopé) est recadrée.** Elle décrivait un objectif ;
  ce document en donne le modèle et le découpage. Elle devient US-164 + US-166.

---

## 5. Architecture d'intégration

### 5.1 Principe directeur : ingestion hors ligne, runtime hors réseau

**Décision actée, cohérente avec les invariants du projet :** aucune API externe n'est appelée
pendant qu'un jardinier attend une réponse. Trois raisons, dans cet ordre.

1. **Latence.** L'objectif V2 est de sortir du LLM pour gagner en rapidité. Remplacer un aller-retour
   Groq par un aller-retour Trefle ou Perenual annule le gain.
2. **Disponibilité.** Trefle a cessé son service en mai 2021 avant de revenir ; une fiche culture ne
   peut pas dépendre de la santé d'un tiers gratuit. Le potager, lui, est toujours là.
3. **Réseau.** SentinelOne et le réseau d'entreprise ; le polling sortant est déjà la contrainte
   structurante du bot.

```
┌─────────────── HORS LIGNE — ponctuel, manuel, versionné ────────────────┐
│                                                                         │
│  Sources ouvertes        tools/import_referentiel.py                    │
│  (dumps CSV/XML/JSON) ──────────► normalisation ──► rapprochement ──┐   │
│                                   noms FR           code EPPO       │   │
│                                                                     │   │
│  Rédaction curée ────────────────► validation humaine ──────────────┤   │
│  (voir §6.4)                       niveau_confiance                 │   │
│                                                                     ▼   │
│                                              migration_vXX.sql / seed   │
└─────────────────────────────────────────────────────────────────────┼───┘
                                                                      │
┌─────────────── EN LIGNE — lecture seule, 0 dépendance ──────────────▼───┐
│                                                                         │
│   PostgreSQL : culture_config · bioagresseur · relations · chunks       │
│         │                │                │                             │
│         ▼                ▼                ▼                             │
│   fiche courte      avertissement     recherche FTS                     │
│   (gabarit)         (jointure)        (étage 2)                         │
│   ÉTAGE 1           ÉTAGE 1           ÉTAGE 2                           │
│   0 token           0 token           0 token en lecture                │
└─────────────────────────────────────────────────────────────────────────┘
```

Le script d'import est **idempotent** (`ON CONFLICT DO NOTHING` / `DO UPDATE` selon la table),
rejouable, et produit un rapport de couverture : combien de cultures du potager réel sont
effectivement couvertes, lesquelles ne le sont pas. C'est ce rapport qui pilote la saisie manuelle
résiduelle, pas une intuition.

### 5.2 Le rapprochement des sources — le vrai travail technique

Le point dur n'est ni la collecte ni le stockage : c'est **l'appariement**. « tomate », « Tomate »,
« Solanum lycopersicum », « TOMATE » dans un libellé d'usage E-Phy, « tomato » chez Permapeople.

Trois clés de rapprochement, par ordre de fiabilité décroissante :

| Clé | Fiabilité | Usage |
|---|---|---|
| **Code EPPO** | ✅ élevée | Pivot d'identité des bioagresseurs et des plantes hôtes |
| **Nom scientifique normalisé** | 🔶 moyenne | Rattrapage quand le code EPPO est absent |
| **Nom vernaculaire FR normalisé** | ⚠️ faible | Dernier recours, **toujours** avec revue humaine |

🔶 À vérifier avant chiffrage d'US-162 : les libellés d'usage E-Phy sont structurés
`culture * type de traitement * cible` mais ne semblent pas porter de code EPPO. Une table de
correspondance manuelle sur les ~30 cultures suivies est probablement nécessaire — c'est du travail
borné et fait une seule fois, mais il doit être budgété.

🧪 À tester : le taux d'appariement automatique sur les cultures réelles du potager. En dessous de
~70 %, l'import automatique perd son intérêt face à la saisie directe.

### 5.3 Les chemins de lecture — ce que chaque étage consomme

```
« je plante quoi après mes tomates sur NORD ? »          → ÉTAGE 1, 0 token
   evenements(parcelle NORD, 2 dernières saisons)
     JOIN culture_config JOIN famille_botanique
     → familles présentes + delai_retour_ans
     → cultures dont la famille n'est pas en conflit
     → gabarit de réponse

« qu'est-ce qui attaque mes poireaux ? »                 → ÉTAGE 1, 0 token
   culture_bioagresseur WHERE culture = poireau
     ORDER BY frequence
     → liste + gabarit

« taches brunes sur mes feuilles de tomate »             → ÉTAGE 1 → 2, 0 token
   symptome (FTS + synonymes) → symptome_bioagresseur (poids)
     ∩ culture_bioagresseur(tomate)
     → 2-3 suspicions classées
     → chunk narratif de la plus probable
     → ⚠️ formulation prudente obligatoire : « cela peut évoquer », jamais « c'est »

« mes courgettes jaunissent et j'ai beaucoup arrosé »    → ÉTAGE 3, coût réel
   suspicions (ci-dessus) + événements arrosage + météo + chunks
     → contexte < 1000 tokens → LLM rédige
```

### 5.4 La boucle qui ferme le système

C'est le gain produit le moins visible et le plus fort. L'application détient déjà les deux
extrémités de la chaîne ; le référentiel fournit le maillon manquant.

```
observation          →   pré-diagnostic      →   traitement         →   suivi
(action canonique ✅)    (référentiel)           (action ✅)            (événements ✅)

« taches sur les          « évoque le             « traité au           « 12 jours plus tard,
  feuilles de               mildiou —               cuivre le             plus de nouvelles
  tomate »                  fréquent en             15/06 »               taches »
                            juin-septembre »

         └──────────────────────┴─── enregistré comme une seule histoire ───┘
                        exploitable l'année suivante, sur la même parcelle
```

Aucun concurrent branchant un LLM sur un carnet ne produit cela : il faut détenir l'historique
**et** le référentiel **et** le lien entre les deux. C'est la même thèse que l'Annexe A de la V2,
appliquée à la santé des plantes plutôt qu'au calendrier.

---

## 6. Les sources — état des lieux

**Réponse directe à ta question : non, tu n'as pas de recherche d'API à mener.** Le tour d'horizon
est fait ci-dessous, et la conclusion est qu'aucune API ne sera appelée en production. Ce dont j'ai
besoin de toi est d'une autre nature — c'est le §7.

### 6.1 Tableau d'évaluation

| Source | Ce qu'elle apporte réellement | Licence | Verdict |
|---|---|---|---|
| **Wikidata** | Taxonomie, famille botanique, noms scientifiques et vernaculaires FR | **CC0** (domaine public) | ✅ **Socle taxonomique.** Aucun risque, aucune attribution obligatoire |
| **E-Phy / ANSES** (data.gouv.fr) | ~15 000 produits et surtout leurs **usages** : couples *culture × cible*, mention « jardins amateurs » (EAJ), biocontrôle, agriculture biologique. Mise à jour hebdomadaire, CSV et XML | **Licence Ouverte / Etalab** (attribution simple) | ✅✅ **La pépite.** Seule source officielle, française, réutilisable commercialement, qui donne le lien culture ↔ bioagresseur *et* le cadre légal du traitement |
| **EPPO Global Database** | Nomenclature de ~98 000 espèces, **codes EPPO**, noms communs multilingues, relations hôte-ravageur | Accès libre, inscription gratuite ; conditions d'API à valider | ✅ **Clé pivot d'identité.** 🔶 lire les conditions de `data.eppo.int` avant import de masse |
| **Wikipédia FR** | Description générale, généralités botaniques | CC-BY-SA 4.0 | 🔶 Utilisable **avec** attribution et partage à l'identique — voir §6.3 |
| **Permapeople** | Fiches + **données d'association** + API documentée | **CC-BY-SA 4.0** | ⚖️ Tentant (les associations sont rares en open data) mais contaminant. Décision PO requise |
| **Plants For A Future / Practical Plants / Growstuff** | Fiches, orientation vivaces et permaculture | CC-BY-SA | 🟡 Même contrainte, couverture faible sur le potager annuel français |
| **Ephytia (INRAE)** | **Le meilleur contenu francophone** : fiches maladies et ravageurs par légume, symptômes, biologie, protection, photos | Aucune licence ouverte affichée | ⛔ **Pas d'import.** ✅ Source de lecture de référence pour la rédaction humaine (§6.4) |
| **GBIF** | Taxonomie et occurrences | CC0 / CC-BY | 🟡 Secours taxonomique, faible valeur potagère |
| **Trefle** | API botanique, ~400 000 espèces | AGPL / accès libre | ⛔ Service interrompu en 2021 puis rétabli ; données taxonomiques sans conseil potager. Dépendance non justifiée |
| **Perenual** | API plantes + maladies avec images | Commerciale, quotas, CGU restrictives | ⛔ Dépendance externe + licence + anglophone |
| **Bulletins de Santé du Végétal / FREDON** | Pression parasitaire **régionale et saisonnière** | Variable selon région | 🧪 Piste v2 remarquable : « alerte mildiou en Île-de-France cette semaine ». Hors périmètre initial |
| **Calendriers et ouvrages du commerce** | — | Œuvres protégées | ⛔ Confirmé, cohérent avec Épic 5 §9 |

### 6.2 Stratégie retenue : socle libre + curation propriétaire

```
  COUCHE 1 — FAITS          Wikidata (CC0) + EPPO + E-Phy (Licence Ouverte)
  attributs, identités,     → import automatisé, attribution simple
  relations légales           → aucune contrainte commerciale

  COUCHE 2 — RELATIONS      saisie curée à partir de sources de lecture
  associations, rotation,     (Ephytia, littérature, expérience du potager)
  fréquence des attaques    → propriété de l'application, actif différenciant

  COUCHE 3 — NARRATIF       rédaction assistée, validée humainement (§6.4)
  descriptions, symptômes,  → propriété de l'application
  conduite à tenir
```

Le point important : **les couches 2 et 3 sont l'actif de l'application**, pas un mal nécessaire.
Une donnée que tout le monde peut importer ne différencie personne. Le graphe d'associations recalé
sur les cultures réellement présentes, lui, ne se copie pas.

### 6.3 ⚖️ Arbitrage 1 — accepte-t-on du CC-BY-SA dans le socle ?

**Le fait :** la clause *share alike* impose que toute adaptation redistribuée le soit sous la même
licence. Diffuser une fiche dérivée de Permapeople ou de Wikipédia à des utilisateurs relève de la
communication au public — les obligations s'appliquent donc au **contenu affiché**.

**Ce qui est contaminé :** le corpus de fiches dérivé. **Ce qui ne l'est pas :** le code de
l'application, les données des potagers, le socle CC0 et Licence Ouverte.

| Option | Conséquence | Recommandation |
|---|---|---|
| **A — Zéro CC-BY-SA dans le socle** | Corpus 100 % propriétaire, aucune contrainte de publication. Charge de rédaction plus élevée | ✅ **Recommandée** si la trajectoire SaaS commerciale est confirmée |
| **B — CC-BY-SA accepté, isolé** | `referentiel_source.partageable = false`, fiches concernées affichées avec attribution et licence visibles | 🔶 Acceptable, mais crée deux régimes à maintenir dans l'interface |
| **C — CC-BY-SA sans précaution** | Non-conformité, risque juridique sur l'actif principal | ⛔ Exclu |

C'est précisément le risque déjà noté pour Growstuff dans les principes du projet. La colonne
`partageable` rend l'option B *techniquement* tenable — mais l'option A reste plus simple, et la
différence de charge est plus faible qu'il n'y paraît une fois la couche 1 importée
automatiquement.

### 6.4 ⚖️ Arbitrage 2 — la rédaction assistée du narratif

Le corpus narratif (couche 3) est le point qui a bloqué l'Épic 5 et la famille A. Estimation
réaliste : ~30 cultures + ~40 bioagresseurs courants = **~70 fiches courtes**, soit plusieurs
dizaines d'heures à la main.

**Proposition :** rédiger ces fiches par un passage LLM **hors ligne, une seule fois**, sur la base
d'un plan imposé, puis les **valider humainement** avant de les marquer `niveau_confiance = 'verifie'`.

| Aspect | Position |
|---|---|
| **Licence** | Un texte produit par reformulation de connaissances générales n'est pas une copie d'une œuvre. Le corpus reste propriétaire |
| **Coût** | ~70 fiches × ~1 200 tokens ≈ 85 000 tokens — **une journée de quota, une fois pour toutes** |
| **Risque** | ⚠️ Hallucination. Mitigé par : (a) aucun chiffre produit par le LLM — durées, doses, espacements viennent **exclusivement** de la couche 1 ou de la saisie ; (b) `niveau_confiance = 'indicatif'` par défaut, passage à `'verifie'` uniquement après relecture ; (c) mention de source visible côté utilisateur |
| **Cohérence projet** | Respecte le principe d'honnêteté de l'Épic 5 §4 : *l'application n'invente jamais une date ni une durée*. Ici elle n'invente rien de chiffré — elle reformule du savoir commun |

🔶 Hypothèse à valider par toi : cette approche est-elle acceptable au regard de l'exigence de
qualité que tu poses au référentiel ? Si non, l'alternative est la saisie manuelle progressive via
le bot (déjà prévue en Épic 5 / CA10) — plus lente, mais parfaitement maîtrisée.

### 6.5 ⚠️ Une honnêteté à porter dans le modèle : les associations

Les associations de cultures sont un domaine où **la tradition horticole et la littérature
scientifique divergent souvent**. Certaines relations sont établies (effet répulsif documenté,
concurrence racinaire), d'autres sont traditionnelles sans démonstration.

Verser les deux dans la même table sans distinction reviendrait à faire affirmer à l'application des
choses qu'elle ne peut pas soutenir — exactement ce que l'Épic 5 interdit sur les dates. D'où la
colonne `niveau_preuve ('etabli' | 'traditionnel')`, et une formulation différenciée à l'affichage :
« défavorable » pour l'un, « déconseillé par la pratique traditionnelle » pour l'autre.

---

## 7. Ce que j'attends de toi

Aucune recherche d'API. En revanche, cinq éléments dont je ne dispose pas et qui conditionnent le
chiffrage.

### 7.1 Données à extraire de ta base (bloquant)

```sql
-- [1] Le périmètre réel du référentiel — combien de cultures à couvrir
SELECT culture, COUNT(*) AS nb, MIN(date) AS depuis, MAX(date) AS jusqu_a
FROM   evenements
WHERE  culture IS NOT NULL
GROUP  BY culture
ORDER  BY nb DESC;

-- [2] L'écart entre le vocabulaire réel et culture_config
SELECT DISTINCT e.culture
FROM   evenements e
LEFT   JOIN culture_config cc ON LOWER(e.culture) = LOWER(cc.nom)
WHERE  cc.id IS NULL AND e.culture IS NOT NULL;

-- [3] Le vocabulaire spontané des problèmes — alimente la table `symptome`
SELECT texte_original
FROM   evenements
WHERE  type_action IN ('observation', 'traitement')
   OR  commentaire ILIKE ANY (ARRAY['%maladie%','%puceron%','%mildiou%','%tache%',
                                    '%jaun%','%pourri%','%limace%','%chenille%']);
```

Le point [3] est le plus précieux : il donne **tes** mots, pas ceux d'un manuel. C'est ce qui rendra
le pré-diagnostic (US-165) réellement opérant plutôt que théorique.

### 7.2 Arbitrages à trancher (bloquants)

| # | Question | Renvoi |
|---|---|---|
| 1 | CC-BY-SA dans le socle : option A, B ou C ? | §6.3 |
| 2 | Rédaction assistée du narratif : acceptée ? | §6.4 |
| 3 | Le périmètre initial : les 10 cultures les plus fréquentes, ou les ~30 de `culture_config` ? | §8 |
| 4 | La fiche courte s'affiche-t-elle sur commande (`/fiche`) ou aussi spontanément après une saisie ? | Impact UX bot |

### 7.3 Éléments à fournir (non bloquants)

- Le **guide utilisateur** en Markdown — il alimente la famille B du RAG (V2 §4.1) et son ingestion
  se mutualise avec celle de la famille A. Gain quasi gratuit une fois US-166 livrée.
- Tes **notes personnelles** sur le potager, s'il en existe hors application : elles constituent la
  famille C et, surtout, la couche 2 la plus fiable qui soit — l'observation directe de *ta* parcelle.
- Ta **zone climatique** et la localisation du potager, si déjà arbitrées côté Épic 5 : le référentiel
  s'en sert pour les périodes de risque des bioagresseurs.

---

## 8. Découpage en US proposé

**Nom pour le Milestone GitHub :** `ÉPIC 6 — Référentiel de connaissance des cultures`

| US | Titre | Pts | Nature | Migration |
|---|---|---|---|---|
| **US-160** | Constituer le socle taxonomique et les familles botaniques (absorbe US-067) | 5 | Donnée de référence | **oui** |
| **US-161** | Enrichir `culture_config` des attributs agronomiques de fiche | 5 | Donnée de référence | **oui** |
| **US-162** | Modéliser les bioagresseurs et leur relation aux cultures | 8 | Donnée + import | **oui** |
| **US-163** | Modéliser les associations et la règle de rotation calculable | 8 | Donnée + calcul | **oui** |
| **US-164** | Fiche culture courte au bot (`/fiche`) — 0 token | 5 | Restitution | non |
| **US-165** | Pré-diagnostic déterministe par symptômes sur `observation` | 8 | Calcul + saisie | **oui** |
| **US-166** | Pipeline d'ingestion idempotent et traçabilité des sources | 8 | Outillage | **oui** |
| **US-167** | Avertissement de rotation et d'association à la plantation | 5 | Insight déterministe | non |
| | **Total** | **52** | | |

```
US-166 (pipeline + traçabilité) ──── prérequis technique transverse
   │
   ├──► US-160 (taxonomie) ──┬──► US-161 (attributs) ──► US-164 (fiche courte bot)
   │                          │                              │
   │                          └──► US-163 (associations) ────┤
   │                                     │                   │
   └──► US-162 (bioagresseurs) ──────────┼──► US-165 (pré-diagnostic)
                                          │
                                          └──► US-167 (avertissement plantation)

Épic 5 US-068 ──── même table `culture_config` ── séquencer les migrations
US-140 (backlog Épic 3) ──── recadrée : devient US-164 + US-166
```

**Chemin critique :** US-166 → US-160 → US-162. **Premier gain visible :** US-164, livrable dès
US-161, et qui rend l'épic tangible pour toi en quelques jours.

### 8.1 Séquencement recommandé

| Jalon | Contenu | Ce que le jardinier gagne |
|---|---|---|
| **J1** | US-166 + US-160 | Rien de visible — mais les familles existent, et la rotation devient possible |
| **J2** | US-161 + US-164 | `/fiche tomate` répond en 0 token. **Premier signal fort** |
| **J3** | US-163 + US-167 | L'application l'avertit avant une erreur de rotation ou d'association |
| **J4** | US-162 + US-165 | Une observation de symptôme reçoit une piste, pas un silence |

Recommandation de périmètre initial : **les 10 cultures les plus fréquentes en base**, pas les 30.
Motif — la couverture réelle prime sur l'exhaustivité, le mode dégradé est déjà spécifié
(Épic 5 / CA13), et le rapport de couverture d'US-166 dira objectivement quand élargir.

---

## 9. Impact tokens et performance

| Service | Aujourd'hui | Après l'épic | Étage |
|---|---|---|---|
| « c'est quoi une courgette ? » | ~5 000 tokens (historique complet + LLM) | **0** | 1 |
| « quoi après mes tomates ? » | ~5 000 tokens, réponse générique | **0**, réponse recalée sur la parcelle | 1 |
| « qu'est-ce qui attaque les poireaux ? » | ~5 000 tokens | **0** | 1 |
| « taches brunes sur les feuilles » | ~5 000 tokens | **0** (2-3 suspicions classées) | 1 → 2 |
| Diagnostic multi-facteurs | ~5 000 tokens | ~800 tokens de contexte dense | 3 |
| **Constitution du corpus** | — | ~85 000 tokens, **une seule fois** | hors ligne |

🔶 L'hypothèse de distribution de la V2 (~40 % des questions résolues à l'étage 0bis) devient plus
crédible avec ce référentiel : les questions de connaissance rejoignent les questions de données
dans le domaine du déterministe. Reste à mesurer — la table `routage_logs` recommandée dans la revue
de la V2 est le bon instrument, et elle doit exister **avant** cet épic pour servir de point de
comparaison.

🧪 À tester : le temps de réponse de la requête de rotation (jointure `evenements` × `culture_config`
× `famille_botanique` sur deux saisons). Attendu < 50 ms avec les index existants ; à vérifier sur
la base de production avant de la câbler dans un chemin synchrone du bot.

---

## 10. Risques

| Risque | Niveau | Traitement |
|---|---|---|
| **Le pré-diagnostic est pris pour un diagnostic** — le jardinier traite sur une suspicion | 🔴 Élevé | Formulation imposée (« cela peut évoquer », jamais « c'est »), 2-3 hypothèses toujours affichées, renvoi systématique à la source. À inscrire comme CA bloquant d'US-165 |
| **Appariement des sources insuffisant** — les libellés E-Phy ne se rattachent pas aux cultures | 🟡 Moyen | 🧪 mesurer le taux d'appariement avant de chiffrer US-162 ; table de correspondance manuelle sur ~30 cultures en repli |
| **Contamination de licence** | 🟡 Moyen | `referentiel_source.partageable` + arbitrage §6.3 tranché **avant** US-166 |
| **Hallucination du narratif** | 🟡 Moyen | Aucun chiffre issu du LLM ; `niveau_confiance` ; relecture avant `'verifie'` |
| **Charge de curation sous-estimée** — le travers déjà relevé dans la revue de la V2 | 🟡 Moyen | Périmètre initial à 10 cultures ; rapport de couverture d'US-166 comme instrument de décision |
| **Migrations concurrentes sur `culture_config`** (Épic 5, US-067) | 🟢 Faible | US-067 absorbée par US-160 ; séquencer avec US-068 |
| **Associations traditionnelles présentées comme des faits** | 🟢 Faible | `niveau_preuve` + formulation différenciée (§6.5) |

---

## 11. Definition of Done de l'épic

- [ ] Les huit US sont livrées, leurs CA cochés et leurs tests passants.
- [ ] Le référentiel couvre **toutes les cultures réellement présentes** dans le potager de
      production ; le rapport de couverture le démontre, sans culture fantôme créée.
- [ ] `/fiche <culture>` répond au bot en **0 token** et la fiche détaillée s'affiche en PWA.
- [ ] Une plantation en conflit de rotation déclenche un avertissement avant enregistrement.
- [ ] Une observation de symptôme produit au moins une piste sur les 10 cultures du périmètre, et
      un message honnête de non-couverture ailleurs.
- [ ] Chaque enregistrement importé porte sa source, sa licence et son attribution.
- [ ] L'arbitrage de licence est tranché, documenté, et aucune source non conforme n'est en base.
- [ ] Aucune régression sur le stock, les écrans Stocks et Statistiques, ni les statistiques du bot.
- [ ] **Aucun fait inventé nulle part** : toute absence de donnée se lit comme telle, toute
      suspicion se lit comme une suspicion.

---

## 12. À faire au démarrage de l'épic

- Trancher les **quatre arbitrages du §7.2** — préalable à US-166.
- Produire les **trois extractions SQL du §7.1** — préalable au chiffrage d'US-160 et US-162.
- 🔶 Lire les conditions d'utilisation de `data.eppo.int` avant tout import de masse.
- Ajouter `ÉPIC 6 — Référentiel de connaissance des cultures` à la liste des épics de
  `.github/agents/Personna PO.agent.md`.
- Marquer **US-067 comme absorbée** par US-160, et **recadrer US-140** en US-164 + US-166 dans
  `BACKLOG_US_MULTITENANT.md`.
- Référencer ce document dans `docs/00_INDEX_NAVIGATION.md` et le citer en source de
  `EPIC_CALENDRIER_CULTURAL.md` (il lève son risque 🔴).
- Positionner US-160 à US-167 en `Todo` sur le kanban (`python tools/us_tracker.py`).
