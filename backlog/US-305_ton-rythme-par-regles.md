**ID :** US-305
**Titre :** Donner le ton et le rythme de Gaston par des règles
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier qui écoute Gaston
Je veux qu'il ait le ton juste : pressant pour une alerte de gel, content pour une belle récolte, posé pour une consigne chiffrée
Afin de saisir à l'oreille l'importance de ce qu'il me dit

**Contexte fonctionnel :**
**Conditionnée au verdict d'US-298** : si l'essai conclut que les balises ne s'entendent pas en français, cette US est close sans suite. Les balises Voxtral (`[emotion=…]`, `[pace=…]`) sont posées par des **règles** selon la nature de la réponse (D1), jamais par le modèle de langage en v1. Elles sont ajoutées au moment de la synthèse : ni stockées, ni affichées (étude §5.6).

**Critères d'acceptance :**
- [ ] CA1 : Un fichier de règles versionné associe une nature de réponse à ses balises, à partir de ce que l'orchestrateur a déjà produit (`signal`, `proposition_id`, `question`, issue d'erreur) : alerte du veilleur → `urgent` ; récolte enregistrée → `happy` ; proposition à confirmer → `confident` ; question en attente → `curious` ; indisponibilité ou refus → `apologetic` ; défaut → `warm`. Les valeurs sont celles retenues par le verdict d'US-298.
- [ ] CA2 : Une phrase du résumé qui porte une consigne chiffrée (dose, distance, profondeur, date) est précédée de `[pace=slow]` si ce rythme a été retenu à l'essai.
- [ ] CA3 : Les balises ne figurent jamais dans `texte_compagnon`, `texte_oral`, l'historique ni l'affichage ; elles ne sont ajoutées qu'au texte envoyé à la synthèse.
- [ ] CA4 : Toute valeur absente des listes de Mistral (34 émotions, rythmes relevés par US-298) est refusée au chargement des règles, avec un message qui nomme la règle fautive ; l'API, elle, l'accepterait en silence.
- [ ] CA5 : `VOIX_BALISES=non` coupe toutes les balises sans redéploiement ; une voix exclue par le verdict d'US-298 est toujours lue sans balise.
- [ ] CA6 : Une balise n'est jamais prononcée : le jardinier n'entend ni « crochet », ni « emotion », ni « urgent » lu comme un mot.
- [ ] CA7 : Le cache de lecture d'US-304 tient compte des balises : changer une règle produit un nouveau son pour la lecture suivante.
- [ ] CA8 : Une écoute de contrôle, une phrase par règle sur chaque voix retenue, est faite par le jardinier avec son accord (volume et coût annoncés, un seul passage) ; son verdict est ajouté au rapport d'US-298.
- [ ] CA9 : La fiche du corpus du compagnon vocal dit que le ton varie selon la nature de la réponse ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (service voix)
- Migration BDD requise : non
- Dépendances : US-298 (verdict), US-304
- Décisions liées : D1
- Fiche du corpus : `compagnon-vocal-pwa.md`

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le verdict d'US-298 retient "urgent" pour la voix Marie
And le veilleur a émis une alerte de gel affichée par Gaston
When le jardinier appuie sur ▶ sous cette alerte
Then le texte envoyé à la synthèse commence par "[emotion=urgent]"
And le texte affiché ne contient aucune balise
Given VOIX_BALISES vaut "non"
When la même alerte est lue
Then aucune balise n'est envoyée
```

**Labels GitHub :** `us`, `voix`, `compagnon`
