---
id: SC-211
titre: US-282 B1, B2, B7 — la météo d'une ville nommée, jamais celle du potager
tags: [us282, meteo, recette]
---

PRÉREQUIS : aucun (pas de parcelle ni d'historique). Dépend d'Open-Meteo : une panne réseau
fait échouer le scénario sans que le bot soit en cause. Le lieu de la réponse doit être la
ville demandée, jamais « ton potager ».

## Tour 1 — B1 : météo de Lyon
> quelle météo sur Lyon ?

- texte contient: Lyon
- texte ne contient pas: ton potager
- aucune écriture

## Tour 2 — B2 : prévision de demain à Lyon
> quel temps demain à Lyon ?

- texte contient: Lyon
- texte ne contient pas: ton potager
- aucune écriture

## Tour 3 — B7 : cinq jours à Nantes
> prévisions pour les 5 prochains jours à Nantes

- texte contient: Nantes
- texte ne contient pas: ton potager
- aucune écriture
- ? texte regex: (5|cinq)
