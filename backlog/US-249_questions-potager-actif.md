**ID :** US-249
**Titre :** Dire quel est mon potager actif
**Épic :** ÉPIC 3 — Fiabilité & coût

**Story :**
En tant que jardinier qui gère plusieurs potagers
Je veux demander « quel est mon potager actif ? » ou « sur quel potager je suis ? »
Afin d'être sûr que mes prochaines saisies iront dans le bon potager

**Contexte fonctionnel :**
Relevé du 21/10/2026 : « quel est mon potager actif ? » est partie à la requête SQL écrite par le modèle, puis au modèle de réponse, qui a répondu « Je ne trouve rien d'enregistré à ce sujet ». Environ 3 800 jetons pour une information que le bot connaît déjà : le potager actif est dans le contexte de chaque message.

**Critères d'acceptance :**
- [ ] CA1 : « quel est mon potager actif ? », « sur quel potager je suis ? », « comment s'appelle mon potager ? » donnent le nom du potager actif.
- [ ] CA2 : Quand le jardinier a accès à plusieurs potagers, la réponse les cite et rappelle la commande pour changer de potager.
- [ ] CA3 : « combien de potagers j'ai ? » donne le nombre de potagers auxquels le jardinier a accès, avec leur nom.
- [ ] CA4 : Seuls les potagers auxquels le jardinier a accès sont cités, jamais ceux d'un autre compte.
- [ ] CA5 : Réponse sans appel modèle ; questions ajoutées au corpus d'US-243.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation
- Migration BDD requise : non
- Dépendances : US-243

**Estimation :** 1 point

**Scénario Gherkin :**
```gherkin
Given un jardinier ayant accès aux potagers "Maison" (actif) et "Jardin partagé"
When il demande "quel est mon potager actif ?"
Then le bot répond que le potager actif est "Maison"
And il cite "Jardin partagé" avec la commande pour changer de potager
```

**Labels GitHub :** `us`, `fiabilite-cout`, `questions`, `multi-tenant`
