**ID :** US-184
**Titre :** Fermer les fuites d'imputation avant toute facturation sur une clé tierce
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant qu'administrateur de la plateforme
Je veux qu'aucun appel au modèle ne puisse être imputé à un potager qui ne l'a pas déclenché
Afin que, le jour où un jardinier branche sa propre clé, il ne paie jamais la consommation d'un autre

**Contexte fonctionnel :**
Première US de l'ÉPIC 7 (`docs/Epic 7 - BYOK  LLM du potager/epic-7-byok-cle-personnelle.md`, §3 « US-170 » dans la numérotation initiale du document, décalée ici en US-184 parce que la bande 170-178 était déjà occupée). Elle est la **seule de l'Épic livrable dès maintenant** et devrait l'être : trois dettes, héritées d'US-143 et **revérifiées dans le code le 15/09/2026**, rendent faux aujourd'hui deux engagements que l'Épic promet — « votre clé ne sert qu'à vous » et « la suppression de votre potager efface tout ».

| Dette | Constat au 15/09/2026 | Effet si non corrigée |
|---|---|---|
| Le contexte par défaut désigne un potager réel | `app/services/context.py:38-40` — `default_context()` retourne `DEFAULT_POTAGER_ID` en dur, commenté « transition US-040 → US-110/112 » | Tout appel sur un chemin non armé est imputé à ce potager. S'il branche sa clé, il paie pour les autres — l'exact contraire de l'Épic |
| Le rejeu de corpus facture un jardinier | `tools/rejeu_corpus.py:259` — `--potager` a `default=1` | Un rejeu de corpus en mode cascade est facturé à un potager de production |
| La mesure de consommation survit à la purge | `app/services/potagers.py:500` — le dictionnaire `volumes` de la suppression définitive ne contient pas `conso_tokens`, dont la clé étrangère vers `potagers` est `NOT NULL` (`migrations/migration_v31.sql`) | La suppression définitive (US-084) échoue ou laisse des lignes orphelines |

Cette US ne construit rien de nouveau : elle solde. Mais elle est la condition sans laquelle US-188 (journal d'imputation) inscrirait des mensonges dans le relevé du jardinier.

**Critères d'acceptance :**

*Aucune imputation par défaut*
- [ ] CA1 : Aucun contexte « par défaut » ne désigne un potager réel. Un appel LLM sans contexte résolu est **refusé** par la passerelle (garde existante d'US-092 / CA2, `ContexteAppelManquantError`), jamais imputé à un potager de repli
- [ ] CA2 : Tous les points d'appel qui reposaient sur le contexte par défaut sont recensés et rattachés au contexte réel de la requête ou de l'Update Telegram (mécanisme d'US-046). La liste des points recensés figure dans les notes de livraison
- [ ] CA3 : Un test vérifie qu'aucune fonction du code applicatif ne retourne un contexte désignant un potager réel sans qu'il ait été résolu depuis l'utilisateur (test « aucun contexte par défaut ne désigne un potager réel »)

*Outils d'exploitation*
- [ ] CA4 : Le rejeu de corpus n'a **plus de potager par défaut** : l'argument est obligatoire, et l'outil refuse de tourner sur un potager dont une configuration de clé personnelle est active (contrôle inerte tant qu'US-185 n'est pas livrée, mais écrit dès maintenant)
- [ ] CA5 : Le rejeu de corpus consomme sur un potager **technique** dédié aux mesures, jamais sur un potager de jardinier ; l'identifiant de ce potager technique est un réglage d'environnement, pas une constante

*Purge*
- [ ] CA6 : La suppression définitive d'un potager (US-084) purge ses lignes de `conso_tokens` ; la table entre dans le dictionnaire `volumes` **et** dans l'assertion de `tests/test_us084_suppression_definitive_potager.py` (ligne 392 au 15/09/2026). C'est cette assertion, et non la vigilance, qui garantit qu'aucune table n'est oubliée — les tables des US suivantes de l'Épic entreront au même endroit
- [ ] CA7 : La purge reste idempotente et rejouable (US-084 / CA8)

*Vérification*
- [ ] CA8 : Une requête d'invariant est livrée et documentée : aucune ligne de `conso_tokens` ne porte un potager qui n'existait pas à sa date d'écriture, et aucune ligne récente ne porte le potager technique hors des fenêtres de rejeu

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse (contexte tenant, mesure de consommation, purge)
- Migration BDD requise : **non**
- Dépendances : **aucune** — livrable avant toute autre US de l'Épic. Prérequis d'US-188 et d'US-192
- Remplace : les deux dettes « fuites d'imputation » et la dette « `conso_tokens` absente de la purge » des notes techniques d'US-143
- Impact tokens : zéro — aucun appel ajouté ; les rejeux de corpus changent seulement de potager d'imputation
- Point de vigilance : le commentaire « transition US-040 → US-110/112 » du contexte par défaut date du plan multi-tenant initial. Cette US ferme cette transition : ce n'est pas un contournement de plus

**Notes techniques (pour Persona Developer) :**
- Le garde d'US-092 refuse déjà un appel sans `potager_id` : la correction consiste à ne plus **fabriquer** de contexte, pas à ajouter un contrôle
- `bot.py` appelle historiquement le contexte par défaut dans des fonctions utilitaires sans `ctx` : la résolution par contextvar d'US-046 est le mécanisme à généraliser, pas un rethreading manuel
- Le potager technique du CA5 est un potager ordinaire, marqué comme tel, exclu des statistiques de plateforme et du futur relevé d'US-189

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Aucun appel n'est imputé à un potager de repli
  Given un chemin de code qui ne résout aucun contexte de tenant
  When il tente un appel au modèle
  Then l'appel est refusé avant tout octet réseau
  And aucune ligne de consommation n'est écrite sur le potager numéro 1

Scénario: Le rejeu de corpus ne facture aucun jardinier
  Given l'outil de rejeu de corpus lancé sans argument de potager
  When il démarre
  Then il s'arrête en expliquant que le potager technique doit être désigné
  And aucun appel n'est parti

Scénario: La purge efface la mesure de consommation
  Given un potager ayant des lignes de consommation
  When sa suppression définitive est exécutée
  Then ses lignes de consommation sont effacées
  And le volume effacé figure dans le journal de purge
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`, `rgpd`
