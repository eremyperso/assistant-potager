**ID :** INC-007
**Titre :** Une récolte redistribue les salades entre les rangs et libère des rangs à tort
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-09-23

**Reproduction (jeu de test réalisé) :**
Vue plan, parcelle `planche_salade` (complément de répartition progressive
US-198). La parcelle possède 5 rangs, une longueur de 4 m, une superficie de
5 m² et une largeur de 1,25 m. La capacité affichée est de 13 salades par
rang.

Avant manipulation :

| Rang | Culture | Quantité |
|---|---|---:|
| R1 | Salade | 13 plants |
| R2 | Salade | 13 plants |
| R3 | Betterave | 12 pieds |
| R4 | Salade | 13 plants |
| R5 | Salade | 14 plants |

Le plan affiche 5 rangs occupés, 53 salades et « 1 en trop » sur R5.

Demander une récolte de 3 salades sans préciser de rang, puis consulter le
plan. Le canal et la formulation exacte de saisie ne sont pas précisés.

**Résultat obtenu :**
- R1 : 25 salades, « 12 en trop ».
- R2 : 25 salades, « 12 en trop ».
- R3 : 12 pieds de betterave, inchangé.
- R4 et R5 : libres.
- Compteur : 3 rangs occupés.

Le total de 50 salades est correct, mais la redistribution fait perdre le
suivi des quantités par rang.

Deux captures avant/après ont été fournies par le déclarant et correspondent
aux valeurs ci-dessus (non jointes en fichiers locaux à cette fiche — voir
section Captures).

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
- R1 : 13 salades.
- R2 : 13 salades.
- R3 : 12 pieds de betterave, inchangé.
- R4 : 13 salades.
- R5 : 11 salades, sans dépassement.
- Compteur : 5 rangs occupés.

Lorsqu'aucun rang n'est précisé pour la récolte, retirer depuis le dernier
rang de cette culture, puis remonter ses rangs si nécessaire. Ne pas
redistribuer uniformément les plants ni modifier les autres cultures.

Le traitement d'un rang entièrement vidé reste à préciser ; ce scénario ne
le couvre pas.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : API/Backend, Frontend (Vue plan).
- Nature probable : régression logique — à investiguer.
- Fichiers probablement concernés : `app/services/repartition_rangs.py`
  (fonctions `_affectations_par_rang` et `repartition_du_plan`, confirmées
  présentes) ; `frontend/src/lib/planVue.js` (fonction `rangsDeLaCarte`,
  confirmée présente).
- Corpus de connaissance concerné : oui — `data/connaissance/doc_app/parcelles-et-plan.md`
  à mettre en cohérence dans la livraison corrective.

**Labels :** incident, backend, frontend
