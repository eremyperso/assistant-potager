**ID :** US-301
**Titre :** Régler la voix de mon compagnon dans la PWA
**Épic :** ÉPIC 17 — Compagnon vocal dans la PWA *(numéro à valider, voir `docs/EPIC 17 - COMPAGNON VOCAL PWA/ANALYSE_ET_SOLUTION_COMPAGNON_VOCAL.md`)*

**Story :**
En tant que jardinier
Je veux activer le mode vocal, écouter les voix proposées et choisir celle de Gaston
Afin de parler à mon compagnon avec une voix qui me plaît, et de pouvoir tout couper d'un geste

**Contexte fonctionnel :**
Section « Voix » de la fenêtre « Mon compagnon » (`ModalMonCompagnon.jsx`), sur les points d'API d'US-300. Le mode vocal est **éteint par défaut** : sans lui, ni micro ni lecture n'apparaissent dans le panneau.

**Critères d'acceptance :**
- [ ] CA1 : La section « Voix » propose un interrupteur « Mode vocal » (micro et lecture des réponses), éteint par défaut.
- [ ] CA2 : Mode vocal actif, la liste des voix françaises du catalogue s'affiche avec le nom de chaque voix ; la voix choisie est cochée.
- [ ] CA3 : Un bouton ▶ par voix joue son extrait ; lancer un autre extrait arrête le précédent ; l'extrait se joue sur iPhone et iPad (le tap sur ▶ suffit à autoriser le son).
- [ ] CA4 : Un interrupteur « Lire les réponses après une dictée » (actif par défaut) règle la lecture automatique (D5).
- [ ] CA5 : Chaque changement est enregistré aussitôt, avec un retour discret « Enregistré » ; une erreur réseau le dit et remet l'état précédent.
- [ ] CA6 : Si le navigateur ne peut pas enregistrer la voix (pas de `MediaRecorder`, page hors HTTPS), la section le dit en clair (« La dictée demande une connexion sécurisée » / « Ce navigateur ne permet pas la dictée ») ; la lecture des réponses reste réglable.
- [ ] CA7 : Le catalogue de secours (US-300 CA5) est affiché sans alerte.
- [ ] CA8 : Le rendu correspond à la maquette de référence (à produire dans Claude Design) à 375 px, 768 px et sur ordinateur ; la section respecte les container queries du composant (`frontend/CLAUDE.md`).
- [ ] CA9 : Le guide utilisateur (ses deux copies) et une fiche du corpus `doc_app` décrivent le mode vocal et le choix de la voix ; la table « ce qui rend une fiche fausse » du `README.md` de `doc_app` est complétée ; `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : réglages (PWA)
- Migration BDD requise : non
- Dépendances : US-300 ; maquette Claude Design
- Décisions liées : D2, D5
- Fiche du corpus : nouvelle fiche `compagnon-vocal-pwa.md` (ou section de `compagnon-reponses-et-memoire.md`)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given le jardinier ouvre "Mon compagnon" sur son iPhone
And le mode vocal est éteint
When il active "Mode vocal"
Then la liste des voix Marie, Manon, Léa et Camille apparaît
When il appuie sur ▶ à côté de "Léa"
Then l'extrait de Léa se joue au haut-parleur
When il choisit "Léa"
Then "Enregistré" s'affiche
And la voix "voice_589" est retrouvée sur son PC
```

**Labels GitHub :** `us`, `voix`, `pwa`, `compagnon`
