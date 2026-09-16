**ID :** US-192
**Titre :** Désactiver, détruire et purger la clé du potager de façon réversible et prouvable
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager ayant branché sa clé
Je veux pouvoir la retirer à tout moment, être certain qu'elle est détruite, et emporter mon relevé avant de supprimer mon potager
Afin de garder la main sur mon engagement financier et de ne rien laisser derrière moi

**Contexte fonctionnel :**
Neuvième et dernière US de l'ÉPIC 7 (document d'épic §7.3 ; « US-178 » dans sa numérotation initiale). Étend le CA8 d'US-143 aux tables nées de l'Épic, et ferme le cycle ouvert par US-184 : la purge de suppression définitive (US-084) doit connaître toutes les tables du BYOK, et c'est l'assertion de test, non la vigilance, qui le garantit.

⚖️ **Arbitrage — que devient le relevé à la suppression du potager ?** Le RGPD et le CA8 disent : purger. Mais le relevé est la **preuve** de ce qui a été consommé sur la clé du jardinier ; un jardinier qui supprime son potager puis conteste sa facture un mois plus tard n'a plus rien, et l'éditeur non plus. **Retenu : purger, mais proposer l'export avant.** La charge de la preuve passe au jardinier, seul arrangement compatible avec son droit à l'effacement. 🔶 Une durée de conservation courte et motivée serait défendable mais contredit l'esprit du CA8 : à faire confirmer par le juriste d'US-190, pas à trancher seul.

**Critères d'acceptance :**

*Désactivation*
- [ ] CA1 : La désactivation, depuis les paramètres du potager, arrête **immédiatement** les appels sur la clé (à la requête suivante, API et bot, sans redémarrage — US-186 / CA6) et **détruit le secret** : la clé chiffrée et la DEK scellée sont effacées, pas seulement marquées. La ligne de configuration survit sans sa clé, pour l'historique (fournisseur, modèle, dates)
- [ ] CA2 : La désactivation vaut retrait du consentement, horodaté (US-190 / CA4)
- [ ] CA3 : Après désactivation, le potager repart sur le client de la plateforme, exactement comme un potager jamais configuré ; le relevé passé reste consultable (US-189 / CA5)
- [ ] CA4 : Réactiver exige une nouvelle saisie, un nouveau test et un nouveau consentement : rien de l'ancienne clé n'est réutilisable, par construction

*Suppression définitive du potager*
- [ ] CA5 : La suppression définitive (US-084) purge la configuration LLM, les consentements et les lignes du journal d'imputation du potager (US-184 / CA6 pour `conso_tokens`). Chaque table entre dans le dictionnaire `volumes` **et** dans l'assertion de `tests/test_us084_suppression_definitive_potager.py`
- [ ] CA6 : L'écran de suppression définitive propose, **avant** confirmation, le téléchargement du relevé complet (CSV + PDF, export « tout le relevé » d'US-189 / CA7), avec une phrase disant qu'il ne sera plus récupérable ensuite. Sans configuration passée, rien n'est proposé
- [ ] CA7 : La purge reste idempotente et rejouable ; le délai de grâce de 30 jours d'US-084 s'applique : pendant ce délai, la configuration est **désactivée et son secret détruit** dès la demande de suppression, même si le potager est finalement restauré (une clé ne dort pas dans un potager en attente d'effacement)

*Preuve*
- [ ] CA8 : Un test vérifie qu'après désactivation, aucune colonne chiffrée ne subsiste en base pour ce potager et qu'aucun appel ne part plus sur l'ancienne clé
- [ ] CA9 : Un test vérifie qu'après purge, aucune ligne des trois tables ne porte le potager, et que l'invariante d'US-188 / CA10 reste vraie sur le reste de la base
- [ ] CA10 : Le rendu de l'écran de suppression correspond visuellement à la maquette de référence à 375px / 768px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (paramètres PWA) | transverse (purge)
- Migration BDD requise : **non**
- Dépendances : **US-185** (coffre), **US-188** (journal), **US-189** (export complet), **US-190** (consentement), **US-084** (suppression définitive, livrée)
- Reprend d'US-143 : CA8 (étendu)
- Impact tokens : zéro
- Point de vigilance : l'archivage d'un potager (US-083, lecture seule) n'est pas une suppression : la configuration y est désactivée et son secret détruit (un potager archivé n'appelle plus le modèle), le relevé reste lisible

**Notes techniques (pour Persona Developer) :**
- La destruction du secret est un UPDATE qui met les colonnes chiffrées à NULL, dans la même transaction que la désactivation ; la contrainte « active ⇒ validée » reste vraie parce que la ligne devient inactive
- Le point d'entrée de purge d'US-084 (`app/services/potagers.py`, dictionnaire `volumes`) est le seul endroit à étendre

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Désactivation détruit la clé
  Given une configuration active
  When le propriétaire la désactive
  Then la clé chiffrée et la DEK scellée sont effacées de la base
  And la question suivante part sur le client de la plateforme
  And le consentement porte une date de retrait

Scénario: Export proposé avant suppression définitive
  Given un potager ayant eu une configuration et un relevé
  When le propriétaire demande la suppression définitive
  Then le téléchargement du relevé complet lui est proposé avant confirmation
  And il est écrit qu'il ne sera plus récupérable ensuite

Scénario: Purge complète
  Given un potager supprimé au-delà du délai de grâce
  When la purge est exécutée
  Then la configuration, les consentements et le journal d'imputation du potager sont effacés
  And les volumes effacés figurent dans le journal de purge

Scénario: Demande de suppression puis restauration
  Given un potager avec une configuration active
  When son propriétaire demande la suppression puis restaure le potager pendant le délai de grâce
  Then la configuration est désactivée et son secret détruit
  And rien ne repart sur l'ancienne clé
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`, `rgpd`, `pwa`
