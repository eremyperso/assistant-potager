**ID :** US-282
**Titre :** Un seul outil météo pour l'agent : ici ou ailleurs, passé ou prévision
**Épic :** ÉPIC 13 — Agent interpréteur *(à valider)*

**Story :**
En tant que jardinier
Je veux demander au compagnon la météo de Lyon, de demain ou des cinq prochains jours, avec mes mots
Afin d'obtenir la météo du bon endroit, et jamais celle de mon potager présentée comme celle d'une autre ville

**Contexte fonctionnel :**
Mesure du 01/11/2026 (`ANALYSE_MESURE_AGENT_D_ABORD.md` §4). À « Quelle météo sur Lyon ? », les trois modèles répondent avec la pluie **du potager** (« Il est tombé 0.0 mm de pluie sur les 3 derniers jours »), et le 14B l'écrit même « Hier à Lyon… ». « quel météo en Belgique ? » donne la météo du potager présentée comme celle de la Belgique.
La cause est le catalogue : l'outil `meteo` de l'agent ne lit que **l'historique** du potager (`jours`, passé). La météo d'un autre lieu (US-251) existe, mais cachée dans `afficher(commande=meteo, lieu=…)`, et aucun modèle ne l'y trouve. Deux chemins pour une même intention, dont le plus visible est faux.

**Critères d'acceptance :**
- [ ] CA1 — L'outil `meteo` de l'agent prend `lieu` (facultatif, le potager par défaut) et `quand` : les N derniers jours, aujourd'hui, demain, ou N jours de prévision. Il s'appuie sur `utils/meteo` et le géocodage d'US-251.
- [ ] CA2 — Chaque donnée rendue nomme son lieu (« Lyon (69) », « ton potager »). Le contrôle du texte (`savoir.controler`) refuse un texte qui attribue des chiffres à un lieu absent des relevés : le texte du code le remplace.
- [ ] CA3 — `afficher(commande=meteo)` sort du catalogue de l'agent. La commande `/meteo` reste pour le jardinier. Un seul chemin pour l'agent.
- [ ] CA4 — Lieu introuvable ou trop large (« la Belgique ») : l'agent demande une ville. Il ne donne jamais la météo du potager à la place.
- [ ] CA5 — Le préchargement de la météo du jour du potager (US-263) ne change pas.
- [ ] CA6 — Remesure sur Small 4, avec accord et en un seul passage : TER-04, TER-05 et TER-06 du corpus de terrain sont justes, sur le texte attendu (US-280 / CA6).
- [ ] CA7 — La fiche `data/connaissance/doc_app/compagnon-telegram.md` dit que le compagnon donne la météo d'un autre lieu et les prévisions. `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.
- [ ] CA8 — Tests sans modèle : lieu donné, lieu absent, prévision, lieu introuvable, et texte qui attribue au mauvais lieu.

**Hors périmètre :**
- La commande `/meteo` elle-même : inchangée, donc ni aide, ni guide, ni menu à reprendre.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : agent interpréteur (outils de savoir)
- Migration BDD requise : non
- Dépendances : US-280 ; US-251 (météo d'un autre lieu, géocodage)
- Code concerné : `app/services/agent/savoir.py` (`meteo`, `controler`), `app/services/agent/catalogue_outils.py` (`_outils_savoir`, enum d'`afficher`), `utils/meteo.py`
- Production conseillée : **Sonnet 5.5, effort `medium`**

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
When le jardinier écrit "Quelle météo sur Lyon ?"
Then l'agent appelle meteo(lieu="Lyon")
And la réponse nomme Lyon et donne la météo de Lyon

When le jardinier écrit "et demain ?"
Then l'agent appelle meteo(lieu="Lyon", quand="demain")

When le jardinier écrit "quel météo en Belgique ?"
Then l'agent demande quelle ville
```

**Labels GitHub :** `us`, `agent-interpreteur`, `compagnon`, `meteo`
