**ID :** US-038
**Titre :** Saisie guidée de notes/observations par catégorie

**Story :**
En tant que jardinier
Je veux pouvoir noter rapidement une observation de terrain (état sanitaire, arrosage, paillage, remarque générale) en étant guidé par l'assistant IA sur les informations pertinentes à saisir selon la catégorie choisie
Afin de garder une trace fiable et structurée de mes observations sans avoir à me souvenir moi-même de tous les champs utiles à renseigner

**Contexte fonctionnel :**
Aujourd'hui, seules les actions "fortes" (semis, récolte, arrosage réel, etc.) ont un flux de saisie dédié. Il n'existe pas de moyen simple de consigner une remarque qualitative (ex : "mildiou détecté sur les tomates", "sol sec parcelle Nord", "paillage renouvelé") sans forcer artificiellement les champs d'une action existante. Cette US ajoute un flux conversationnel guidé, à la manière de `/corriger`, qui pose les bonnes questions selon la catégorie de note choisie, puis enregistre le résultat comme un `Evenement` classique avec `type_action = "observation"` — **sans aucune modification du modèle de données**.

**Déclencheurs :**
- Commande slash dédiée : `/note`
- Message vocal ou texte libre reconnu via un nouvel intent `NOTE` dans `classify_intent()` (ex: "je veux noter une observation", "il faut que je note un truc sur les tomates")

**Catégories de notes (premier tour de menu, boutons inline) :**
1. 🔍 **Observation** — remarque générale de suivi (croissance, aspect, comportement)
2. 🐛 **Maladie / ravageur** — problème sanitaire détecté
3. 💧 **Arrosage (remarque)** — constat qualitatif lié à l'eau, SANS créer d'événement d'arrosage réel (ex: "sol sec", "fuite goutte-à-goutte")
4. 🌿 **Paillage** — constat ou action de paillage informelle

**Critères d'acceptance :**
- [ ] CA1 : `/note` affiche un menu inline avec les 4 catégories ci-dessus
- [ ] CA2 : Un message vocal/texte classifié `NOTE` par `classify_intent()` déclenche le même menu de catégories
- [ ] CA3 : Après sélection d'une catégorie, l'assistant pose une série de questions guidées adaptées :
  - Toutes catégories : parcelle concernée (optionnel, avec suggestion des parcelles actives), culture/variété concernée (optionnel)
  - **Maladie/ravageur** : nom du problème observé (symptôme), traitement envisagé ou appliqué (optionnel)
  - **Arrosage (remarque)** : constat (ex: sol sec/détrempé), durée constatée si pertinente (optionnel)
  - **Paillage** : matériau utilisé (optionnel), constat/action
  - **Observation** : texte libre uniquement
- [ ] CA4 : L'utilisateur peut répondre en langage naturel à chaque question (pas de format strict imposé) ; Groq est utilisé pour extraire les champs pertinents de la réponse libre
- [ ] CA5 : Un récapitulatif est présenté avant enregistrement (cohérent avec la logique de confirmation existante, US-021) avec boutons ✅ Confirmer / ❌ Annuler
- [ ] CA6 : À la confirmation, un `Evenement` est créé avec :
  - `type_action = "observation"`
  - `culture`, `variete`, `parcelle_id` renseignés si fournis
  - `commentaire` = texte de la note, préfixé par la catégorie entre crochets (ex: `[Maladie] Mildiou détecté sur feuilles basses`)
  - `traitement` = traitement/matériau si applicable (maladie, paillage)
  - `duree` = durée constatée si applicable (arrosage qualitatif)
  - `texte_original` = message brut dicté/tapé par l'utilisateur
  - `date` = date du jour (ou date extraite si mentionnée dans le message, ex: "hier")
- [ ] CA7 : Aucune colonne n'est ajoutée au modèle `Evenement` — tous les champs utilisés existent déjà (`database/models.py`)
- [ ] CA8 : `/help note` affiche l'aide dédiée à cette commande
- [ ] CA9 : L'utilisateur peut annuler le flux à tout moment (bouton ❌ ou commande `/annuler` si existante)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram (nouveau flux conversationnel) + enregistrement
- Migration BDD requise : **non** — réutilisation stricte des colonnes existantes de `Evenement`
- Dépendances : US-021 (confirmation avant enregistrement), US-011 (validation post-parsing)
- Le préfixe de catégorie dans `commentaire` (`[Observation]`, `[Maladie]`, `[Arrosage]`, `[Paillage]`) permet de retrouver/filtrer les notes ultérieurement sans migration, y compris pour un futur `/historique` ou `/ask` filtré par catégorie
- Le canonical action `observation` existe déjà dans `ACTION_MAP` (`utils/actions.py`) — vérifier sa présence et sa normalisation avant implémentation

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Note guidée via commande slash - catégorie Maladie
  Given je suis un utilisateur du bot Telegram
  When j'envoie la commande "/note"
  Then je reçois un menu avec les catégories "Observation", "Maladie / ravageur", "Arrosage (remarque)", "Paillage"

  When je sélectionne "🐛 Maladie / ravageur"
  Then l'assistant me demande la culture/parcelle concernée puis le symptôme observé et le traitement éventuel

  When je réponds "tomates parcelle Nord, mildiou sur les feuilles du bas, j'ai traité au purin d'ortie"
  Then l'assistant extrait culture="tomate", parcelle="Nord", symptôme="mildiou sur les feuilles du bas", traitement="purin d'ortie"
  And un récapitulatif est affiché avec boutons "✅ Confirmer" et "❌ Annuler"

  When je clique sur "✅ Confirmer"
  Then un événement est enregistré avec type_action="observation", culture="tomate", parcelle_id correspondant à "Nord",
       commentaire="[Maladie] mildiou sur les feuilles du bas", traitement="purin d'ortie"

Scénario: Note guidée déclenchée par la voix
  Given je suis un utilisateur du bot Telegram
  When j'envoie un message vocal disant "je veux noter que le sol est sec sur la parcelle Sud"
  Then classify_intent() retourne "NOTE"
  And le menu des catégories de note est affiché

Scénario: Annulation du flux de note
  Given j'ai démarré une saisie de note via "/note"
  When je clique sur "❌ Annuler" avant confirmation
  Then aucun événement n'est enregistré en base
  And je reçois un message confirmant l'annulation
```

**Labels GitHub :** `us`, `sprint-X`, `telegram`, `observation`
