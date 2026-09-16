**ID :** US-185
**Titre :** Sceller les secrets réversibles dans un coffre applicatif à chiffrement enveloppe
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant qu'administrateur de la plateforme
Je veux que la clé d'API d'un jardinier soit stockée chiffrée, liée cryptographiquement à son potager, derrière une interface unique
Afin qu'une fuite de la base n'expose aucune clé et qu'un chiffré déplacé d'un potager à l'autre ne puisse jamais être déchiffré

**Contexte fonctionnel :**
Deuxième US de l'ÉPIC 7 (document d'épic §2.B et §5.2 à §5.5 ; « US-171 » dans sa numérotation initiale). Elle est isolée délibérément : **c'est le seul composant cryptographique du projet et il n'a aucun précédent.** `cryptography` n'est présent que transitivement, et le seul secret stocké aujourd'hui l'est en hachage à sens unique, ce qui ne transpose pas à une clé qui doit rester réversible. Mélanger ce module à l'écran de configuration ferait relire quatre cents lignes d'interface pour trouver un défaut de dix lignes de cryptographie. Il se relit seul.

Arbitrage tranché (§2.B) : **pas de coffre-fort managé en v1.** Chiffrement enveloppe applicatif — une clé de données (DEK) par potager, scellée par une clé maîtresse (KEK) en variable d'environnement. Aucune dépendance externe, aucun coût récurrent. Mais l'accès au secret est isolé derrière une interface de trois fonctions, pour que le passage ultérieur à un gestionnaire de secrets soit le remplacement de la seule couche KEK, pas une refonte. C'est la raison d'être de la DEK intermédiaire.

Reprend et précise les CA1, CA5 et CA7 d'US-143.

**Critères d'acceptance :**

*Modèle de données*
- [ ] CA1 : Une table `potager_llm_config` porte, par potager (**une configuration au plus** par potager, contrainte d'unicité) : fournisseur, adresse de base, modèle, DEK scellée, clé chiffrée, empreinte d'affichage (derniers caractères), budget mensuel indicatif en euros (nullable), dernier seuil d'alerte atteint (nullable), indicateur d'activation, date de dernière validation réussie, date de mise à jour, date de création
- [ ] CA2 : Une contrainte de base interdit qu'une configuration soit active sans date de validation réussie : le CA3 d'US-143 devient un invariant de base, pas une discipline applicative
- [ ] CA3 : La date de mise à jour est renseignée par **toute** écriture sur la ligne (mécanisme de base, pas discipline applicative) : c'est la clé d'invalidation du cache client d'US-186
- [ ] CA4 : La table est sous RLS, sur le gabarit des tables tenant existantes, et couverte par `tests/test_us043_rls_isolation.py`. Une clé retirée est **détruite, jamais archivée** : pas d'historique de clés en base

*Le coffre*
- [ ] CA5 : Un module unique expose trois opérations et rien d'autre : sceller (secret en clair → DEK scellée, clé chiffrée, empreinte), ouvrir (→ secret en clair, au moment de l'appel, jamais avant), empreinte. **Aucun autre module du projet n'importe la bibliothèque cryptographique** — un test l'interdit
- [ ] CA6 : Chiffrement authentifié (AES-256-GCM), nonce aléatoire par opération, KEK de 32 octets hors base en variable d'environnement. Un chiffré altéré échoue au déchiffrement au lieu de produire des octets arbitraires
- [ ] CA7 : L'identifiant du potager est lié cryptographiquement au chiffré (donnée authentifiée additionnelle) **aux deux niveaux** — DEK et clé. Un chiffré rattaché à un autre potager, par bug de requête, jointure fautive ou restauration partielle, **ne déchiffre pas** : il lève. Un test le prouve
- [ ] CA8 : Une fuite de la seule base (dump, sauvegarde, réplique) n'expose aucune clé en clair — c'est le critère par lequel le module est conçu et relu (US-143 / CA7)

*Rotation de la KEK*
- [ ] CA9 : Une procédure de rotation est écrite dans le runbook de production, sur le gabarit documentaire de `JWT_SECRET` : nouvelle KEK → re-scellement de toutes les DEK en une transaction → bascule de la variable d'environnement → redémarrage des deux services → contrôle. Les clés API elles-mêmes ne sont jamais re-chiffrées
- [ ] CA10 : La rotation est **rejouée par un test** (deux KEK, N potagers, tout déchiffre après rotation, rien ne déchiffre avec l'ancienne KEK). Un chiffrement dont la clé n'est jamais renouvelable n'est qu'un délai

*Non-journalisation*
- [ ] CA11 : Un filtre de journalisation installé sur le logger racine masque les en-têtes d'autorisation, les champs de clé, les préfixes de clé connus des fournisseurs et tout champ marqué sensible — dans les messages, les données additionnelles **et les traces d'exception**
- [ ] CA12 : Le test « aucune clé dans les journaux » d'US-092 (`tests/test_us092_passerelle_llm.py`, autour de la ligne 839 au 15/09/2026) est dupliqué et étendu à **trois chemins** : nominal, test de clé, erreur. C'est sur le chemin d'erreur que les secrets fuient en pratique — une exception de client HTTP contient souvent l'en-tête de la requête
- [ ] CA13 : Le format de journalisation structuré du projet est conservé ; aucun bloc d'exception silencieux

*Exploitation*
- [ ] CA14 : Le déploiement de cette US est la **seule action serveur de tout l'Épic**, avec chaque rotation de KEK : un redémarrage des deux services, parce que la configuration ne lit l'environnement qu'à l'import. Jamais au branchement d'une clé de jardinier. Le runbook le dit

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse (sécurité, stockage)
- Migration BDD requise : **oui** — `migration_v48.sql` (v47 est la dernière livrée au 15/09/2026, à reconfirmer à l'implémentation), idempotente, rollback documenté, contrôles post-migration, sur le gabarit de `migration_v44.sql`
- Dépendances : **US-184** (fuites d'imputation, à livrer avant), **US-092** (passerelle — **livrée**, vérifié le 15/09/2026)
- Reprend d'US-143 : CA1 (enrichi), CA5 (précisé), CA7
- Impact tokens : zéro
- Point de vigilance : la table naît **avant** l'écran qui la remplit (US-187). Entre les deux, elle est vide et inerte

**Notes techniques (pour Persona Developer) :**
- Le module de coffre est le seul endroit où `cryptography` est importé ; l'audit AST d'US-092 fournit le gabarit d'un test qui l'interdit ailleurs
- La donnée authentifiée additionnelle est l'identifiant du potager, aux deux niveaux : c'est le point le plus important de l'US — le mélange de clés cesse d'être une question de rigueur applicative pour devenir une impossibilité arithmétique
- Le runbook de production est aujourd'hui `docs/RUNBOOK/RUNBOOK_DEPLOIEMENT_PRODUCTION.md` (gabarit `JWT_SECRET` ligne 354, redémarrage lignes 472 et 677 au 15/09/2026) — le chemin diffère de celui cité par US-143
- Le rôle propriétaire de la base n'est pas soumis à la RLS (`migration_v18.sql`) : le coffre protège contre la fuite de base, pas contre l'éditeur. US-190 le dira au jardinier ; cette US ne doit rien laisser suggérer du contraire dans sa documentation

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Aller-retour d'un secret
  Given une clé d'API en clair et un potager
  When elle est scellée puis ouverte pour ce potager
  Then le clair retrouvé est identique
  And la base ne contient que la DEK scellée, la clé chiffrée et l'empreinte

Scénario: Un chiffré déplacé ne déchiffre pas
  Given une clé scellée pour le potager A
  When on tente de l'ouvrir dans le contexte du potager B
  Then le déchiffrement échoue
  And aucun octet en clair n'est produit

Scénario: Rotation de la clé maîtresse
  Given trois potagers avec une clé scellée sous la KEK 1
  When la procédure de rotation vers la KEK 2 est jouée
  Then les trois clés s'ouvrent sous la KEK 2
  And aucune ne s'ouvre sous la KEK 1
  And aucune clé d'API n'a été re-chiffrée

Scénario: Aucune clé dans les journaux sur le chemin d'erreur
  Given une configuration dont le fournisseur refuse la connexion
  When l'appel échoue et l'exception est journalisée
  Then la clé n'apparaît ni dans le message ni dans la trace
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`
