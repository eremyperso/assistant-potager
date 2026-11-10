**ID :** US-314
**Titre :** Suivre la qualité de service des appels au modèle
**Épic :** ÉPIC 18 — Pilotage LLM

**Story :**
En tant qu'administrateur de la plateforme
Je veux voir les échecs, les quotas atteints et les latences par modèle et par type d'appel
Afin de savoir ce que le jardinier subit et quel fournisseur sature le premier

**Contexte fonctionnel :**
Vue « Fiabilité » de la PWA d'administration. Dans l'extraction du 10/11/2026 : 135 appels en `quota`, 79 en `erreur`, 8 en `voix_inconnue`, 1 en `delai` ; des séries de quotas à 2 secondes d'attente chacune pendant les campagnes du 23/10 et du 05/11.

**Critères d'acceptance :**
- [ ] CA1 : Un bandeau donne le taux de succès, le taux de quota, le taux d'erreur et la latence P50 et P95 de la période, avec l'écart à la période précédente.
- [ ] CA2 : Un graphique par jour empile les issues ; toute issue présente en base est affichée, y compris une valeur inconnue de l'écran.
- [ ] CA3 : Un tableau par modèle donne : appels, succès, quota, erreur, délai, latence P50 et P95.
- [ ] CA4 : Un tableau par type d'appel donne les mêmes colonnes.
- [ ] CA5 : Une grille heure × jour montre le nombre d'appels en `quota` par modèle sur les 7 derniers jours.
- [ ] CA6 : Les 20 derniers échecs sont listés (heure, type, modèle, issue, canal, latence), sans aucun contenu de message.
- [ ] CA7 : La latence est calculée sur les seuls appels réussis ; la latence des échecs est donnée à part.
- [ ] CA8 : Les filtres de la coquille (période, provenance, canal, modèle) s'appliquent.
- [ ] CA9 : Le rendu réutilise sans variante les composants de la maquette de référence de la vue Consommation (US-318) et reste conforme à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA d'administration)
- Cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md` (numéro d'épic à valider)
- Migration BDD requise : non
- Dépendances : US-310, US-311, US-312 (composants), US-318 (maquette)
- Les métriques de routage existantes (`/admin/routage/metriques`) ne sont pas reprises ici ; une vue « Routage et savoir » pourra suivre.

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Given aujourd'hui 43 appels dont 30 ok, 5 erreur et 8 voix_inconnue
When j'ouvre la vue Fiabilité sur "aujourd'hui"
Then le taux de succès affiche 69,8 %
And le graphique montre trois issues dont "voix_inconnue"
And la liste des derniers échecs nomme le type "voix" et le modèle concerné
```

**Labels GitHub :** `us`, `pwa`, `admin`, `observabilite`
