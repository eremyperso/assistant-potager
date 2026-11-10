**ID :** US-317
**Titre :** Recevoir un bilan périodique du pilotage
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux recevoir chaque jour un résumé court et chaque semaine un bilan
Afin de suivre la plateforme sans ouvrir le tableau de bord quand tout va bien

**Contexte fonctionnel :**
Décisions D10 et D11. Le bilan est assemblé par gabarit à partir du service d'agrégats d'US-310 : aucun modèle ne le rédige.

**Critères d'acceptance :**
- [ ] CA1 : Un résumé quotidien est envoyé par Telegram à heure fixe (8 h par défaut, réglable) : appels, jardiniers actifs, coût, taux de succès, latence P95 de l'agent, alertes ouvertes ; chaque chiffre avec son écart à la moyenne des 7 jours précédents.
- [ ] CA2 : Un jour sans appel d'usage produit un résumé d'une ligne qui le dit.
- [ ] CA3 : Un bilan hebdomadaire est envoyé par e-mail le lundi : les mêmes indicateurs sur la semaine et la semaine précédente, répartition du coût par modèle et par type d'appel, coût par jardinier actif, 3 plus fortes variations, alertes de la semaine, versions livrées dans la semaine avec leur médiane de jetons d'entrée par appel agent.
- [ ] CA4 : Le résumé et le bilan ne comptent que les provenances `usage` et `fond` ; le volume de `mesure` est donné sur une ligne à part.
- [ ] CA5 : Les textes sont produits par gabarit, sans appel de modèle ; un test vérifie qu'aucune ligne `conso_tokens` n'est écrite pendant leur production.
- [ ] CA6 : Chaque envoi porte un lien vers la vue correspondante de la PWA d'administration.
- [ ] CA7 : Deux interrupteurs de configuration activent séparément le résumé quotidien et le bilan hebdomadaire (désactivés par défaut) ; la vue « Seuils » d'US-316 les affiche.
- [ ] CA8 : Un envoi échoué est journalisé et n'est pas rejoué plus d'une fois ; un bilan n'est jamais envoyé deux fois pour la même période.
- [ ] CA9 : Le bilan ne contient aucun nom de jardinier ni contenu de message ; un potager est désigné par son identifiant.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (services de pilotage, notifications)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : à l'analyse (trace des bilans envoyés ; peut réutiliser `alertes_pilotage`)
- Dépendances : US-310, US-316 (planification et canaux)
- Décisions liées : D10, D11

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given hier : 84 appels d'usage, 3 jardiniers actifs, 0,04 € et 98 % de succès
And la moyenne des 7 jours précédents est de 60 appels par jour
When il est 8 h
Then je reçois sur Telegram un résumé indiquant 84 appels (+40 %), 3 jardiniers actifs, 0,04 € et 98 % de succès
And aucune ligne n'a été écrite dans conso_tokens pour le produire
```

**Labels GitHub :** `us`, `admin`, `alertes`
