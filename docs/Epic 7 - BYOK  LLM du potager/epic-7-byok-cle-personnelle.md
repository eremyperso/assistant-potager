# 🔑 ÉPIC 7 — BYOK : la clé et le modèle du jardinier

> **Rédigé le :** 11/09/2026
> **Objet :** structure, architecture et cadre juridique du modèle *Bring Your Own Key*, destinés à
> être exécutés par les agents de développement.
> **Remplace :** `backlog/US-143_brancher-sa-propre-cle-ia.md` (13 points, ÉPIC 3), absorbée et éclatée ici.
> **Convention :** ⚖️ arbitrage · ✅ fait établi ou recommandation ferme · 🔶 point d'attention ·
> 🧪 scénario à tester.

---

## ⚠️ Avertissement de source — à lire avant d'exécuter quoi que ce soit

**Ce document n'a pas lu le dépôt.** Aucun accès au code n'était disponible lors de sa rédaction.
Toutes les références `fichier:ligne` qu'il contient sont **reprises d'US-143**, qui les a établies le
11/09/2026. Elles sont fiables en tant que citations, pas en tant qu'observations de première main.

Conséquence opérationnelle, pour chaque agent : **la première action de toute US de cet Épic est de
vérifier dans le code la référence qui la fonde**, et de signaler l'écart plutôt que de l'absorber.
Les points à revérifier impérativement sont marqués 🔶 et récapitulés au §10.

---

## 1. Pourquoi un Épic, et non une US

US-143 pesait 13 points pour une seule promesse : *« brancher sa clé »*. Ta contrainte en ajoute deux
autres, de nature différente :

1. **le cloisonnement strict** — la clé du jardinier ne doit servir qu'à lui, jamais à un tiers ;
2. **la preuve** — le jardinier doit pouvoir rapprocher, ligne à ligne, ce que l'application a
   consommé sur sa clé avec la facture de son fournisseur.

Ces deux exigences ne sont pas des critères qu'on ajoute à une US : ce sont des propriétés qui se
construisent dans le stockage, dans le point de résolution, dans le cache, dans la journalisation et
dans le contrat. Une US unique les rendrait irrelisables — et le §67 d'US-143 dit déjà l'essentiel :
*les garanties réellement tenables face à « ma clé sera-t-elle détournée ? » sont le périmètre, la
visibilité, la réversibilité et la limitation.* Chacune mérite sa propre livraison et son propre test.

**Décision : ÉPIC 7 — BYOK.** US-143 est retirée d'ÉPIC 3 et ses 21 critères sont répartis, sans perte,
dans les 9 US ci-dessous (tableau de correspondance au §4).

### Numérotation

| Élément | Valeur retenue | Justification |
|---|---|---|
| Numéro d'épic | **7** | 1→4 = `BACKLOG_US_MULTITENANT.md` · 5 = Cycle de vie du potager · 6 = Référentiel de connaissance |
| Bande d'US | **US-170 → US-178** | 100-133 réservée (ancien plan) · 140-143 prise (moteur de réponses V2) · 160-167 prise (Épic 6) |

🔶 **À vérifier avant création des fiches** : qu'aucune US n'occupe déjà 170-178. La bande 140+ a été
attribuée par lots ; une collision se règle en décalant l'Épic entier en 180, jamais en trouant la bande.

---

## 2. Les quatre arbitrages tranchés

### ⚖️ A — Le cache : asymétrie en faveur du jardinier (**remplace le CA16 d'US-143**)

US-143 / CA16 prévoyait que le potager BYOK reste dans le pot commun : *« ses appels peuvent servir à
d'autres potagers »*. **Ce critère est annulé.** Il contredit frontalement l'exigence de cloisonnement.

La règle qui le remplace est asymétrique, et c'est délibéré :

| Sens | Règle | Effet |
|---|---|---|
| **Écriture** | Une réponse produite sur la clé d'un potager n'entre **jamais** dans le cache partagé (`potager_id IS NULL`). Elle est écrite dans le cache **privé** du potager (`potager_id = <son id>`) | ✅ Aucun tiers ne bénéficie d'un token payé par le jardinier |
| **Lecture** | Le potager BYOK continue de lire le cache partagé, alimenté par la plateforme | ✅ Il ne paie pas des appels que la plateforme lui offrait déjà |

**Pourquoi l'asymétrie et non l'isolation totale.** La contrainte porte sur un seul sens : *« il n'est
pas permis que sa clé soit profitable à d'autres »*. Isoler aussi la lecture ne renforcerait aucune
garantie pour le jardinier — cela lui **coûterait** des appels. L'isolation totale serait une punition
présentée comme une protection.

**Ce que l'écran de consentement doit dire**, en toutes lettres : *« Les réponses obtenues avec votre
clé ne sont jamais réutilisées pour un autre potager. Vous continuez en revanche à bénéficier des
réponses déjà payées par la plateforme, ce qui réduit votre consommation. »*

🔶 Effet de bord à traiter : le cache privé fait porter au jardinier le coût de ses propres répétitions
seulement une fois. Vérifier que la RLS couvre `questions_cache` scopé par `potager_id`, sinon la
séparation est déclarative.

### ⚖️ B — Stockage du secret : chiffrement enveloppe applicatif

Pas de coffre-fort managé en v1. AES-256-GCM, une **DEK par potager** scellée par une **KEK** en
variable d'environnement. Aucune dépendance externe, aucun coût récurrent, aucun point de panne
supplémentaire sur un produit encore mono-VPS.

**Mais** l'accès au secret est isolé derrière une interface unique — un module `securite/coffre.py`
exposant trois fonctions et rien d'autre. Le passage ultérieur à Vault ou à un KMS devient le
remplacement de la seule couche KEK, pas une refonte. C'est la raison d'être de la DEK intermédiaire :
sans elle, le chiffrement enveloppe n'apporte rien de plus qu'un chiffrement direct.

### ⚖️ C — Garde-fous : alertes, pas de blocage

Retenu : **budget mensuel indicatif + alertes à 50 / 80 / 100 %**, sans plafond bloquant, sans
coupe-circuit automatique, sans limite de débit applicative.

🔶 **Deux conséquences à assumer explicitement, elles ne sont pas neutres :**

1. **Une alerte a besoin d'un référentiel.** « 50 % » de quoi ? Il faut donc que le jardinier saisisse
   un **budget mensuel de référence** au moment de la configuration. Sans ce champ, le critère
   d'alerte est vide. Il est **déclaratif et non bloquant** : le dépasser n'arrête rien.
2. **L'application n'a alors aucun frein dur.** En cas de boucle, de bug ou d'attaque, rien côté
   plateforme n'arrête la consommation — seule la facture le fera. Cela déplace le seul garde-fou réel
   chez le fournisseur du jardinier. La recommandation « clé dédiée, projet dédié, budget propre »
   cesse donc d'être un conseil : elle devient une **condition d'activation**, écrite dans l'écran de
   consentement et rappelée dans les CGU. C'est aussi ce qui rendra défendable la clause de
   responsabilité du §8 — un éditeur qui ne pose aucun plafond mais impose la clé dédiée reste
   cohérent ; un éditeur qui ne fait ni l'un ni l'autre ne l'est pas.

⚖️ **Point rouvrable.** Si tu changes d'avis, le plafond bloquant est **peu coûteux une fois US-174
livrée** (le journal d'imputation donne déjà le cumul de la période) : c'est une condition avant
l'appel, ~20 lignes. Le coupe-circuit automatique, lui, est une vraie US. Je recommande de garder la
porte ouverte en structurant US-175 pour que le plafond bloquant soit un ajout et non une reprise.

### ⚖️ D — Cadre juridique : B2C uniquement

CGU/CGV, politique de confidentialité, écran de consentement horodaté et révocable, liste des
sous-traitants. **Pas de DPA article 28** en v1. Détail au §8.

---

## 3. Découpage en User Stories

**9 US · 42 points estimés.** US-143 en pesait 13 : l'écart tient à la réconciliation facture (US-174,
US-175) et au volet juridique (US-176), absents de la rédaction initiale, ainsi qu'aux dettes
préalables (US-170).

| US | Titre | Pts | Dépend de | Vague |
|---|---|---|---|---|
| **US-170** | Fermer les fuites d'imputation avant toute facturation sur une clé tierce | 3 | — | 0 |
| **US-171** | Coffre applicatif — chiffrement enveloppe des secrets réversibles | 5 | US-170 | 1 |
| **US-172** | Résolution par potager du client et du modèle LLM | 5 | **US-092**, US-171 | 2 |
| **US-173** | Écran de configuration et test de clé | 5 | US-171, US-172 | 2 |
| **US-174** | Journal d'imputation réconciliable avec la facture du fournisseur | 8 | US-172 | 3 |
| **US-175** | Relevé de consommation, export de rapprochement et alertes de budget | 5 | US-174 | 3 |
| **US-176** | Consentement, information et corpus contractuel BYOK | 5 | US-173 | 4 |
| **US-177** | Échec explicite — aucun repli silencieux sur la plateforme | 3 | US-172 | 5 |
| **US-178** | Purge, révocation et réversibilité | 3 | US-171, US-174 | 5 |

**US-092 (passerelle) reste bloquante pour l'Épic entier**, exactement comme pour US-143 : sans point
de passage unique, il n'y a ni résolution centralisée, ni preuve mécanique de périmètre.

**US-170 est la seule qui peut être livrée dès maintenant**, avant US-092. Elle devrait l'être : ce
sont des dettes qui rendent faux, aujourd'hui, deux critères que l'Épic promet.

### US-170 — Fermer les fuites d'imputation *(3 pts, vague 0, aucune dépendance)*

Trois dettes identifiées dans US-143 (§79-80), sans lesquelles les promesses de facturation et de
purge sont fausses :

| Dette | Référence (US-143) | Effet si non corrigée |
|---|---|---|
| `default_context()` retombe sur le **potager #1 en dur** | `app/services/context.py:38-40` | Tout appel sur un chemin non armé est imputé au potager #1. Si celui-ci branche sa clé, il paie la consommation des autres — l'exact contraire de l'Épic |
| `tools/rejeu_corpus.py --mode cascade` a `--potager 1` par défaut | `:259` | Un rejeu de corpus est facturé à un jardinier |
| `conso_tokens` absente de la purge de suppression définitive | `app/services/potagers.py:500-523`, FK `NOT NULL` en `migrations/migration_v31.sql:34` | La suppression d'un potager échoue ou laisse des lignes orphelines ; le CA8 est faux |

🧪 L'ajout à `tests/test_us084_suppression_definitive_potager.py:391-394` (assert sur le dictionnaire
`volumes`) est ce qui garantit qu'aucune table n'est oubliée — pas la vigilance. `potager_llm_config`
et les tables de consentement entreront au même endroit.

### US-171 — Coffre applicatif *(5 pts)*

Isolée délibérément : **c'est le seul composant cryptographique du projet et il n'a aucun précédent.**
US-143 (§78) le dit — `cryptography` n'est présent que transitivement via `python-jose[cryptography]`,
et le seul secret stocké l'est en hachage à sens unique (`database/models.py:61-66`), ce qui ne
transpose pas à une clé qui doit rester réversible.

Mélanger ce module à l'écran de configuration ferait relire quatre cents lignes d'interface pour
trouver un défaut de dix lignes de cryptographie. Il se relit seul.

Livrables : le module, la migration `v46`, le filtre de masquage des journaux, la procédure de rotation
de la KEK, les tests.

### US-172 — Résolution par potager *(5 pts)*

Reprend les CA17, CA18, CA19 et CA21 d'US-143. Détail au §5.

### US-173 — Écran de configuration et test de clé *(5 pts)*

CA2, CA3, CA6, CA9. Propriétaire seul (rôles d'US-047), test réel minimal avant activation, empreinte
seule affichée, liste des modèles testés distincte des modèles utilisables aux risques du potager.

### US-174 — Journal d'imputation *(8 pts)*

Le cœur de ta demande. Détail au §6. C'est l'US la plus lourde de l'Épic, et c'est normal : c'est elle
qui transforme le CA14 de déclaratif en vérifiable.

### US-175 — Relevé et export *(5 pts)*

Écran PWA, export CSV et PDF du relevé mensuel, budget indicatif et alertes. Détail au §6.4.

### US-176 — Consentement et corpus contractuel *(5 pts)*

CA13 étendu. Détail au §8. **Point de coordination** : le texte de l'écran de consentement dépend des
arbitrages A et C — il annonce la règle de cache asymétrique *et* l'absence de plafond applicatif. Il
ne peut donc pas être rédigé avant que US-172 et US-175 soient stabilisées.

### US-177 — Échec explicite *(3 pts)*

CA10 et CA15. Aucun repli silencieux vers la clé de la plateforme, message désignant la configuration
du potager comme cause probable, fonctions déterministes préservées. Le cas de la clé révoquée côté
fournisseur est traité ici : la date de dernière validation réussie sert à expliquer *depuis quand*.

### US-178 — Purge et réversibilité *(3 pts)*

CA8 étendu. Détail au §7.3, y compris l'arbitrage à trancher sur la conservation du relevé après
suppression du potager.

---

## 4. Correspondance des critères d'US-143

Aucun critère n'est perdu. Un seul est annulé, et il l'est explicitement.

| CA d'US-143 | Devient | US |
|---|---|---|
| CA1 — table `potager_llm_config` | Repris, enrichi (§5.2) | US-171 |
| CA2 — propriétaire seul | Repris tel quel | US-173 |
| CA3 — bouton « Tester la clé » | Repris tel quel | US-173 |
| CA4 — absence de config = aucune rupture | Repris tel quel | US-172 |
| CA5 — chiffrement au repos | Repris, précisé (enveloppe DEK/KEK, AAD) | US-171 |
| CA6 — clé jamais réaffichée | Repris tel quel | US-173 |
| CA7 — fuite de base n'expose rien | Repris comme critère de conception | US-171 |
| CA8 — purge à la suppression du potager | Repris, étendu aux nouvelles tables | US-178 |
| CA9 — modèles testés vs aux risques | Repris tel quel | US-173 |
| CA10 — sortie inexploitable → cause désignée | Repris tel quel | US-177 |
| CA11 — post-traitement identique | Repris tel quel | US-172 |
| CA12 — transcription reste plateforme | Repris tel quel | US-172 / US-176 |
| CA13 — consentement horodaté | Repris, **considérablement étendu** | US-176 |
| CA14 — conso hors quota mutualisé | Repris, **rendu vérifiable** par US-174 | US-174 |
| CA15 — aucun repli silencieux | Repris tel quel | US-177 |
| **CA16 — reste dans le cache partagé** | ⛔ **ANNULÉ** — remplacé par la règle asymétrique (§2.A) | US-172 |
| CA17 — modèle résolu par potager | Repris tel quel | US-172 |
| CA18 — effet à la requête suivante | Repris, mécanisme précisé (§5.3) | US-172 |
| CA19 — exclusion explicite de la transcription | Repris tel quel | US-172 |
| CA20 — le propriétaire voit ce que sa clé a servi | Repris, **c'est la graine d'US-174/175** | US-174, US-175 |
| CA21 — isolation prouvée par un test | Repris, étendu au cache (§2.A) | US-172 |

---

## 5. Architecture — résolution et stockage

### 5.1 Chaîne d'appel

```
Bot Telegram  ─┐
               ├─→  passerelle.repondre(ctx)
API PWA       ─┘         │
                         ├─→ cascade : cache sémantique → SQL → RAG
                         │      └─ répond sans LLM ?  →  FIN, aucune résolution de client
                         │
                         └─→ un appel LLM va réellement partir
                                │
                                ├─→ _resoudre_client(ctx)      ◄── SEUL point d'extension
                                │      ├─ config potager active → client tiers (base_url, clé, modèle)
                                │      └─ sinon                 → client plateforme
                                │
                                ├─→ appel HTTP
                                │
                                └─→ journal d'imputation        ◄── dans un `finally`, cf. §6.2
```

✅ **Principe non négociable — un seul point de branchement.** La résolution se fait au point
d'extension prévu par US-092 (`llm/passerelle.py:246-253`, appelé en `:485` et `:553`). Aucune autre
branche `if config_potager` n'est écrite ailleurs dans le code. C'est ce qui rend le périmètre
**prouvable mécaniquement** par l'audit AST d'US-092, et non simplement affirmé.

✅ **La résolution est paresseuse.** Elle n'est appelée que lorsqu'un appel LLM part réellement. Une
question servie par le cache ou par SQL ne déclenche ni résolution, ni lecture de configuration, ni
ligne de journal. C'est ce qui rend le coût du CA18 négligeable (§5.3).

✅ **Un seul client générique.** Adresse de base, clé et modèle sont trois paramètres. Pas d'adaptateur
par fournisseur — la quasi-totalité des fournisseurs pertinents exposent une interface compatible
OpenAI.

### 5.2 Modèle de données — `migration_v46.sql`

🔶 US-143 (§81) indique que la dernière migration livrée est `migration_v45.sql` (US-165). **À vérifier
au moment de l'implémentation** : le numéro peut avoir bougé.

```sql
-- migration_v46.sql — ÉPIC 7 / US-171
-- Idempotente · rollback documenté en fin de fichier · contrôles post-migration
-- Gabarit : migration_v44.sql

CREATE TABLE IF NOT EXISTS potager_llm_config (
    id                  BIGSERIAL PRIMARY KEY,
    potager_id          INTEGER      NOT NULL REFERENCES potagers(id) ON DELETE CASCADE,

    -- Identification du fournisseur (nommé dans l'écran de consentement)
    fournisseur         TEXT         NOT NULL,
    adresse_base        TEXT         NOT NULL,
    modele              TEXT         NOT NULL,

    -- Secret : chiffrement enveloppe (cf. §5.4)
    dek_scellee         BYTEA        NOT NULL,   -- DEK du potager, scellée par la KEK
    cle_chiffree        BYTEA        NOT NULL,   -- clé API, scellée par la DEK
    cle_empreinte       TEXT         NOT NULL,   -- 4 derniers caractères, pour l'affichage (CA6)

    -- Budget indicatif et alertes (arbitrage C — non bloquant)
    budget_mensuel_eur  NUMERIC(8,2),
    dernier_seuil_alerte SMALLINT,               -- NULL | 50 | 80 | 100, remis à NULL au changement de mois

    -- Cycle de vie
    actif               BOOLEAN      NOT NULL DEFAULT FALSE,
    validee_le          TIMESTAMPTZ,             -- dernière validation réussie (CA3, US-177)
    maj_le              TIMESTAMPTZ  NOT NULL DEFAULT now(),  -- clé de cache client (CA18)
    cree_le             TIMESTAMPTZ  NOT NULL DEFAULT now(),

    CONSTRAINT potager_llm_config_un_par_potager UNIQUE (potager_id),
    CONSTRAINT potager_llm_config_actif_validee
        CHECK (actif = FALSE OR validee_le IS NOT NULL)   -- CA3 : jamais active sans test réussi
);

CREATE INDEX IF NOT EXISTS ix_potager_llm_config_potager
    ON potager_llm_config (potager_id) WHERE actif;

ALTER TABLE potager_llm_config ENABLE ROW LEVEL SECURITY;
-- Policy RLS sur potager_id, sur le gabarit des tables tenant de v18/v42/v43/v45,
-- pour être couverte par tests/test_us043_rls_isolation.py
```

✅ **`UNIQUE (potager_id)`** : une configuration par potager, pas d'historique de clés en base. Une clé
retirée est détruite, jamais archivée — un historique de clés serait un stock de secrets périmés dont
on ne sait plus qui les a révoqués.

✅ **La contrainte `actif ⇒ validee_le IS NOT NULL`** transforme le CA3 en invariant de base plutôt
qu'en discipline applicative. Une clé qui échoue au test ne peut pas devenir active, même par un
chemin de code non prévu.

✅ **`maj_le`** est la clé d'invalidation du cache client (§5.3). Elle doit être mise à jour par
*toute* écriture sur la ligne — trigger, pas discipline.

### 5.3 Prise d'effet sans redémarrage (CA18)

Deux processus (`potager-<env>` et `potager-<env>-bot`) ont chacun leur mémoire. Une invalidation
locale ne suffirait donc pas : elle réintroduirait exactement le défaut du fichier `.env` que cet Épic
supprime.

**Mécanisme retenu — l'invalidation est portée par la clé de cache, pas par un signal :**

```
cle_cache_client = (potager_id, actif, maj_le)
```

`maj_le` est relu **à chaque résolution**. Si la ligne a changé, la clé de cache change, le client
mémorisé est ignoré et un nouveau client est construit. Aucun message inter-processus, aucun
redémarrage, aucune fenêtre d'incohérence entre l'API et le bot.

🔶 **Coût mesuré :** un `SELECT potager_id, actif, maj_le, … FROM potager_llm_config WHERE potager_id = $1`
par **appel LLM réel** — pas par question, la résolution étant paresseuse (§5.1). Index partiel sur
`actif`. Négligeable devant la latence réseau d'un appel LLM (quelques centaines de µs contre quelques
centaines de ms). 🧪 À mesurer malgré tout si la cascade s'avère appeler la résolution avant de savoir
si un appel partira.

✅ **Une seule action serveur dans tout l'Épic** : `systemctl restart potager-<env> potager-<env>-bot`
au déploiement d'US-171 et **à chaque rotation de la KEK** — parce que `config.py:1-6` ne lit
l'environnement qu'à l'import. Jamais au branchement d'une clé de jardinier. À documenter dans
`docs/RUNBOOK_DEPLOIEMENT_PRODUCTION.md` (gabarit `JWT_SECRET`, `:354` ; section restart `:470-474`).

### 5.4 Le coffre — `securite/coffre.py`

**Interface unique, trois fonctions, rien d'autre.** Aucun autre module du projet n'importe
`cryptography`. C'est cette contrainte qui rend le remplacement par Vault ou un KMS possible plus tard
sans refonte.

```python
# securite/coffre.py

def sceller(potager_id: int, secret_clair: str) -> tuple[bytes, bytes, str]:
    """Retourne (dek_scellee, cle_chiffree, empreinte)."""

def ouvrir(potager_id: int, dek_scellee: bytes, cle_chiffree: bytes) -> str:
    """Déchiffre au moment de l'appel, jamais avant. Le clair ne quitte pas l'appelant."""

def empreinte(secret_clair: str) -> str:
    """'…8F31' — le seul dérivé du secret qui ait le droit de sortir du module."""
```

**Schéma cryptographique :**

| Élément | Choix | Raison |
|---|---|---|
| Algorithme | AES-256-GCM | Chiffrement authentifié ; un chiffré altéré échoue au déchiffrement au lieu de produire des octets arbitraires |
| KEK | `COFFRE_KEK`, 32 octets, base64, variable d'environnement | Hors base — c'est ce qui satisfait le CA7 : une fuite de la seule base n'expose rien |
| DEK | Une par potager, aléatoire, scellée par la KEK | Rend la rotation de la KEK linéaire (re-sceller N DEK, jamais re-chiffrer N clés) et prépare le KMS |
| **AAD** | **`str(potager_id)` aux deux niveaux** | ✅ **C'est la garantie mécanique contre le mélange de clés** — cf. ci-dessous |
| Nonce | 12 octets aléatoires par opération, préfixés au chiffré | Jamais réutilisé |

✅ **L'AAD est le point le plus important de cette US.** En liant cryptographiquement chaque chiffré à
l'identifiant de son potager, un chiffré déplacé d'une ligne à l'autre — par un bug de requête, une
jointure fautive, une restauration partielle — **ne déchiffre pas**. Il lève. Le risque « utiliser
accidentellement la mauvaise clé pour un autre utilisateur », qui est le premier des risques listés
dans ton cadre BYOK, cesse d'être une question de rigueur applicative et devient une impossibilité
arithmétique.

**Rotation de la KEK** (procédure à écrire dans le runbook, sur le gabarit `JWT_SECRET`) :
génération de la nouvelle KEK → re-scellement de toutes les DEK en une transaction → bascule de la
variable d'environnement → redémarrage des deux services → contrôle. Les clés API elles-mêmes ne sont
jamais re-chiffrées. 🔶 *Un chiffrement dont la clé n'est jamais renouvelable n'est qu'un délai* :
si la procédure n'est pas écrite et rejouée au moins une fois en pré-production, le CA5 n'est pas tenu.

### 5.5 Non-journalisation du secret

Un filtre `logging.Filter` installé sur le logger racine, masquant :
`Authorization`, `api_key`, `sk-*`, `gsk_*`, et tout champ marqué sensible — dans les messages, les
`extra`, **et les traces d'exception**.

🧪 Le test « aucune clé dans les journaux » de `tests/test_us092_passerelle_llm.py:824-846` est
dupliqué et **étendu à trois chemins** : le chemin nominal, le chemin du test de clé (CA3), et le
chemin d'erreur. C'est sur ce dernier que les secrets fuient en pratique — une exception d'un client
HTTP contient souvent l'en-tête de la requête.

✅ Le format de journalisation structuré `HH:MM:SS │ LEVEL │ emoji MESSAGE` est conservé. Aucun bloc
`except` silencieux.

---

## 6. Architecture — imputation et réconciliation

C'est le volet que ta demande ajoute à US-143, et c'est lui qui rend l'engagement vérifiable plutôt
que déclaratif.

### 6.1 Le principe

> Le jardinier doit pouvoir prendre la facture de son fournisseur, ouvrir son relevé dans la PWA, et
> **retrouver chaque ligne**.

Cela impose trois propriétés, dans cet ordre de difficulté :

| Propriété | Ce qu'elle exige | Sans elle |
|---|---|---|
| **Complétude** | Tout appel parti sur sa clé écrit sa ligne, y compris en cas d'erreur | Sa facture est plus élevée que son relevé : il conclut au détournement |
| **Exactitude** | Les compteurs de tokens viennent de la réponse du fournisseur, jamais d'une estimation locale | Les écarts s'accumulent et rendent le rapprochement impossible |
| **Traçabilité** | Chaque ligne porte l'**identifiant de requête retourné par le fournisseur** | Le rapprochement reste global (« ça a l'air cohérent ») au lieu d'être ligne à ligne |

✅ **L'identifiant de requête du fournisseur est la clé de voûte.** Les API compatibles OpenAI
retournent un `id` dans le corps de la réponse et un identifiant de requête dans les en-têtes. Sans
lui, la réconciliation est une comparaison de totaux ; avec lui, c'est une jointure. **C'est ce détail,
et lui seul, qui fait la différence entre « je te montre mes chiffres » et « tu peux vérifier ».**

🔶 À vérifier par fournisseur au moment de l'implémentation : tous n'exposent pas l'identifiant au même
endroit, et tous ne le font pas figurer sur la facture. Pour ceux qui ne le font pas, le relevé reste
rapprochable par (date, modèle, tokens) — le dire dans l'écran plutôt que de le laisser découvrir.

### 6.2 Extension de `conso_tokens`

🔶 US-143 (§43) indique que `conso_tokens` porte déjà `potager_id`, `user_id`, `modele`, `date` et
`issue` (`database/models.py:734-774`). **Lire la table avant d'écrire la migration** : certaines des
colonnes ci-dessous existent peut-être déjà sous un autre nom.

```sql
-- migration_v47.sql — ÉPIC 7 / US-174
-- Colonne nullable → backfill → contrainte. Ne rouvre aucune table modifiée par une US en vol.

ALTER TABLE conso_tokens
    ADD COLUMN IF NOT EXISTS origine_cle TEXT,                    -- 'plateforme' | 'potager'
    ADD COLUMN IF NOT EXISTS fournisseur TEXT,
    ADD COLUMN IF NOT EXISTS requete_id_fournisseur TEXT,         -- ◄── clé de rapprochement
    ADD COLUMN IF NOT EXISTS tokens_entree INTEGER,
    ADD COLUMN IF NOT EXISTS tokens_sortie INTEGER,
    ADD COLUMN IF NOT EXISTS cout_estime_micro_eur BIGINT,        -- entier : pas de flottant sur de l'argent
    ADD COLUMN IF NOT EXISTS tarif_version TEXT,                  -- ex. 'openai-2026-07-01'
    ADD COLUMN IF NOT EXISTS fonction_appelante TEXT;             -- 'chat' | 'parsing' | 'test_cle' | …

UPDATE conso_tokens SET origine_cle = 'plateforme' WHERE origine_cle IS NULL;

ALTER TABLE conso_tokens
    ALTER COLUMN origine_cle SET NOT NULL,
    ADD CONSTRAINT conso_tokens_origine_cle_valide
        CHECK (origine_cle IN ('plateforme', 'potager'));

CREATE INDEX IF NOT EXISTS ix_conso_tokens_releve
    ON conso_tokens (potager_id, date DESC) WHERE origine_cle = 'potager';
```

✅ **`cout_estime_micro_eur` en entier.** De l'argent ne se stocke pas en flottant, et un coût par
appel se compte en millionièmes d'euro.

✅ **`tarif_version`** figée à l'écriture. Un tarif fournisseur qui change ne doit pas réécrire
rétroactivement le coût estimé d'un appel passé — sinon le relevé d'un mois clos change tout seul, et
la confiance avec.

### 6.3 Les deux garanties, et comment elles se testent

**Garantie de complétude — journalisation dans un `finally`, jamais dans le chemin nominal.**

```python
# llm/passerelle.py — autour de l'appel sortant
ligne = JournalImputation(potager_id=…, origine_cle=…, fonction_appelante=…, debut=…)
try:
    reponse = client.chat.completions.create(...)
    ligne.renseigner_depuis(reponse)          # tokens, requete_id, modèle réellement servi
    ligne.issue = "succes"
    return reponse
except Exception as err:
    ligne.issue = _classer(err)               # 'auth', 'quota', 'timeout', 'refus', …
    raise
finally:
    ligne.enregistrer()                       # ◄── toujours, même en cas d'échec
```

🔶 **Un appel peut être facturé par le fournisseur alors qu'il a échoué côté client** (délai dépassé
après réception, coupure réseau au retour). C'est précisément le cas où le jardinier verra une ligne
sur sa facture sans ligne dans son relevé — donc le cas qui détruit la confiance. La ligne doit être
écrite **avec l'issue**, pas omise. Une ligne « échec, tokens inconnus » est infiniment plus honnête
qu'une ligne absente.

🔶 L'écriture du journal ne doit jamais faire échouer la requête du jardinier. Elle est encapsulée —
mais **jamais silencieuse** : un échec d'écriture est journalisé en `ERROR` avec l'identifiant de
requête du fournisseur, pour être reconstituable.

**Garantie de non-détournement — trois tests, pas trois phrases.**

```gherkin
🧪 Scénario: La clé d'un potager ne sert jamais à un autre
  Given un potager A avec une configuration active et un potager B sans configuration
  When un jardinier du potager B pose une question de raisonnement
  Then l'appel part sur le client de la plateforme
  And aucun appel n'est effectué sur la clé du potager A

🧪 Scénario: Aucune réponse payée par une clé tierce n'entre dans le cache partagé
  Given un potager A avec une configuration active
  When un jardinier du potager A pose une question qui déclenche un appel LLM
  Then la réponse est écrite dans le cache avec potager_id = A
  And aucune ligne de cache créée depuis le début du scénario n'a potager_id NULL

🧪 Scénario: Toute ligne imputée à une clé tierce correspond à une configuration active
  Given un relevé de consommation quelconque
  When on inspecte les lignes origine_cle = 'potager'
  Then chacune a un potager_id dont la configuration était active à l'horodatage de la ligne
```

Le deuxième est le test du nouvel arbitrage A. Le troisième est une **invariante de base** : il peut
tourner en contrôle post-migration et en test de non-régression.

### 6.4 Le relevé — US-175

**Écran PWA, paramètres du potager, section « Consommation de ma clé ».** Accessible au propriétaire
seul, comme la configuration.

| Colonne | Source | Rôle |
|---|---|---|
| Date et heure | `date` | Affichée en heure locale, **totalisée en UTC** (§ci-dessous) |
| Fonction | `fonction_appelante` | Ce qui a déclenché l'appel — la question du jardinier, un parsing, le test de clé |
| Modèle | `modele` | Le modèle **réellement servi**, pas le modèle demandé |
| Tokens entrée / sortie | `tokens_entree`, `tokens_sortie` | Lus dans la réponse du fournisseur |
| Coût estimé | `cout_estime_micro_eur` | Avec le tarif figé (`tarif_version`) |
| Issue | `issue` | Succès, échec d'authentification, quota, délai dépassé… |
| Réf. fournisseur | `requete_id_fournisseur` | **La colonne qui rend le rapprochement possible** |

⚖️ **Le mois de référence est le mois calendaire UTC.** Les fournisseurs facturent en UTC. Afficher
l'heure locale et totaliser en local produirait, chaque mois, un écart de quelques appels entre le
relevé et la facture — un écart minuscule, systématique, et parfaitement suffisant pour détruire la
confiance dans l'outil. L'écran affiche en heure locale, totalise en UTC, **et l'écrit**.

**Mention obligatoire, en toutes lettres sur l'écran et sur les exports :**

> *Coût estimé au tarif public de votre fournisseur en vigueur au \<date\>. Seule la facture émise par
> votre fournisseur fait foi. Ce relevé recense les appels émis par l'application avec votre clé ; il
> ne recense pas les appels que vous auriez émis par ailleurs avec la même clé.*

Cette dernière phrase n'est pas une précaution : c'est la première explication d'un écart légitime, et
elle renvoie directement à la recommandation de la clé dédiée.

**Exports** : CSV (colonnes brutes, pour tableur) et PDF (relevé mensuel présentable). Les deux portent
la mention ci-dessus, la période en UTC, le total et le nombre d'appels.

**Budget et alertes** (arbitrage C) : champ `budget_mensuel_eur` saisi à la configuration ; alertes
Telegram + bandeau PWA à 50 %, 80 % et 100 % du cumul du mois UTC. Une alerte par seuil et par mois
(`dernier_seuil_alerte`, remis à `NULL` au changement de mois). **Aucun blocage.** Le message d'alerte
à 100 % rappelle que l'application n'arrête rien et renvoie vers les plafonds du compte fournisseur.

---

## 7. Périmètre, échec et réversibilité

### 7.1 Ce que le BYOK couvre, et ce qu'il ne couvre pas

| Fonction | v1 | Pourquoi |
|---|---|---|
| Génération de texte (chat, raisonnement) | ✅ Clé du potager | L'objet de l'Épic |
| Parsing d'intention | ✅ Clé du potager | Même point de résolution, même client |
| **Transcription vocale** | ❌ **Toujours la plateforme** | Arbitrage maintenu d'US-143 : gérer la disparité des fournisseurs sur l'audio, pour un quota généreux et un coût faible, n'a aucun intérêt en v1 |
| Embeddings / cache sémantique | ❌ Plateforme | 🔶 **À trancher explicitement dans US-172.** Si le cache sémantique calcule un embedding à chaque question, ce calcul doit-il partir sur la clé du jardinier ? Recommandation : non — c'est de l'infrastructure de plateforme, pas une réponse qui lui est destinée, et la basculer romprait la comparabilité des vecteurs entre potagers |

✅ **L'exclusion de la transcription est écrite au point de résolution, explicitement.** US-143 (CA19)
le dit : `transcrire()` appelle `_resoudre_client(ctx)` exactement comme le chat
(`llm/passerelle.py:553`) — le comportement **par défaut** contredit la règle. Ce n'est donc pas une
abstention qui la tient, mais une ligne de code et un test.

### 7.2 Échec — US-177

✅ **Aucun repli silencieux.** Un repli invisible ferait payer à la plateforme la panne du fournisseur
choisi par l'utilisateur, et enverrait ses données à un service auquel il n'a pas consenti pour cet
appel. L'échec explicite est à la fois plus honnête et moins coûteux.

Le message désigne la configuration du potager comme cause probable et propose deux issues : réessayer,
ou désactiver la configuration. Les fonctions déterministes continuent de fonctionner, comme dans tout
mode dégradé (US-092 / CA10).

Cas particulier de la **clé révoquée côté fournisseur** : échec d'authentification, traité comme
ci-dessus, et `validee_le` permet de dire au jardinier *depuis quand* sa configuration ne fonctionne
plus. 🔶 Ne pas désactiver automatiquement la configuration sur un échec d'authentification : une
coupure réseau du fournisseur produit parfois le même code, et une désactivation automatique ferait
silencieusement repartir les appels sur la plateforme — exactement ce que le CA15 interdit.

### 7.3 Purge et réversibilité — US-178

| Action | Effet |
|---|---|
| **Désactivation** | Arrêt immédiat des appels sur la clé (`actif = FALSE`), **destruction du secret** (`cle_chiffree`, `dek_scellee`). La ligne de configuration survit sans sa clé, pour l'historique. Vaut révocation du consentement (CA13) |
| **Suppression du potager** (US-084) | Purge de `potager_llm_config`, des consentements, et des lignes `conso_tokens` — cf. arbitrage ci-dessous. À ajouter au dictionnaire `volumes` **et** à l'assert de `tests/test_us084_suppression_definitive_potager.py:391-394` |

⚖️ **Arbitrage à trancher : que devient le relevé à la suppression du potager ?**

Le RGPD et le CA8 disent : purger. Mais le relevé est la **preuve** de ce qui a été consommé sur la
clé du jardinier. Un jardinier qui supprime son potager puis conteste sa facture un mois plus tard n'a
plus rien, et l'éditeur non plus.

✅ **Recommandation : purger, mais proposer l'export avant.** L'écran de suppression définitive propose
le téléchargement du relevé complet (CSV + PDF) **avant** confirmation, avec une phrase disant qu'il ne
sera plus récupérable ensuite. La purge reste totale. La charge de la preuve passe au jardinier, ce qui
est le seul arrangement compatible avec son droit à l'effacement.

🔶 À faire confirmer par le juriste au moment d'US-176 : une durée de conservation courte et motivée
(par exemple la durée de contestation de facture du fournisseur) serait juridiquement défendable, mais
elle contredit l'esprit du CA8. Ne pas trancher seul.

---

## 8. Cadre juridique — B2C (US-176)

> 🔶 Je ne suis pas juriste. Ce qui suit est une structure de travail et une liste de points à couvrir,
> pas un avis juridique. La clause de responsabilité du §8.4 en particulier doit être relue par un
> professionnel avant mise en ligne.

### 8.1 Qualification des rôles

En B2C — des jardiniers particuliers, en usage domestique :

| Traitement | Responsable de traitement | Sous-traitant |
|---|---|---|
| Compte, potager, configuration, journaux, relevé, sécurité | **L'éditeur** | Hébergeur |
| Contenus transmis au fournisseur LLM avec la clé du jardinier | **L'éditeur** | Le fournisseur LLM |

🔶 **Point de vigilance, et il est contre-intuitif.** Le fait que le jardinier paie l'appel ne le rend
pas responsable de traitement, et ne sort pas l'éditeur de la chaîne. C'est l'éditeur qui décide de la
finalité (répondre à une question de jardinage) et des moyens essentiels (quel prompt, quelles données
du potager sont jointes, quelle fonction déclenche l'appel). Le jardinier ne choisit que le
prestataire d'exécution. **L'éditeur reste responsable de traitement pour les contenus, exactement
comme en mode plateforme.** Le BYOK change qui paie, pas qui décide.

Le corollaire est celui que ton cadre énonce : *tant que l'application peut utiliser la clé, l'éditeur
est responsable de la sécurité et de la loyauté de cette utilisation.* C'est l'ossature de tout l'Épic.

⚠️ Si un potager venait à être exploité par une structure — école, association, exploitation agricole —
la qualification changerait et un DPA article 28 deviendrait nécessaire. **Hors périmètre v1.** À
inscrire au registre des risques produit, pas au backlog.

### 8.2 Écran de consentement (CA13 étendu)

Recueilli **avant** la première activation, horodaté, versionné, révocable par désactivation.

```sql
-- migration_v48.sql — ÉPIC 7 / US-176
CREATE TABLE IF NOT EXISTS consentement_byok (
    id              BIGSERIAL PRIMARY KEY,
    potager_id      INTEGER      NOT NULL REFERENCES potagers(id) ON DELETE CASCADE,
    user_id         INTEGER      NOT NULL REFERENCES users(id),
    fournisseur     TEXT         NOT NULL,
    version_texte   TEXT         NOT NULL,     -- ex. 'byok-v1-2026-09'
    donne_le        TIMESTAMPTZ  NOT NULL DEFAULT now(),
    revoque_le      TIMESTAMPTZ
);
```

✅ **`version_texte` est indispensable.** Un consentement recueilli sur un texte qu'on ne peut plus
reproduire ne prouve rien. Le texte de chaque version est conservé dans le dépôt, jamais réécrit en
place.

⚖️ **Ne pas enregistrer l'adresse IP.** C'est une donnée personnelle dont la conservation devrait être
justifiée et limitée, pour une valeur probatoire quasi nulle face à un utilisateur authentifié dont on
horodate l'action. Le couple (user_id, horodatage, version) suffit.

**Le texte doit dire, en français simple et sans renvoi en note :**

1. le **fournisseur choisi, nommé**, et que les données du potager lui seront transmises selon ses
   propres conditions ;
2. que la **transcription vocale reste assurée par la plateforme**, même avec une clé branchée ;
3. la **règle de cache**, dans les deux sens : ses réponses ne servent à personne d'autre ; il continue
   de bénéficier de celles payées par la plateforme ;
4. que l'application **ne bloque rien** en cas de dépassement — les alertes informent, seuls les
   plafonds de son compte fournisseur arrêtent ;
5. la **recommandation de la clé dédiée** : clé créée pour cette application, dans un projet ou espace
   de travail séparé, avec son propre budget, permissions minimales, jamais une clé réutilisée
   ailleurs ;
6. que **l'éditeur détient la clé en clair au moment de l'appel** et ce qu'il fait pour la protéger —
   cf. §8.3 ;
7. qu'il peut **désactiver à tout moment**, ce qui détruit la clé et vaut retrait du consentement ;
8. qu'il peut **consulter et exporter** ce que sa clé a servi.

### 8.3 Ce qu'on promet, et ce qu'on ne promet pas

C'est le paragraphe le plus important de l'écran, et il doit être écrit **sans marketing**.

✅ **Ce qui est garanti, et prouvé par un test :**

- **Périmètre** — un seul point de résolution dans le code, prouvé mécaniquement par l'audit AST
  d'US-092. La clé ne peut pas partir ailleurs.
- **Liaison** — chaque clé est liée cryptographiquement à son potager (AAD). Elle ne peut pas
  déchiffrer dans le contexte d'un autre.
- **Non-propagation** — aucune réponse payée par sa clé n'entre dans le cache partagé (test §6.3).
- **Non-journalisation** — la clé n'apparaît dans aucun journal, y compris sur les chemins d'erreur
  (test §5.5).
- **Visibilité** — chaque appel est tracé et consultable (US-174/175).
- **Réversibilité** — désactivation immédiate, destruction de la clé.
- **Limitation** — la transcription et les embeddings ne partent jamais sur sa clé.

❌ **Ce qui n'est pas garanti, et qui doit être écrit :**

> Au moment de l'appel, le serveur de l'application détient votre clé en clair — c'est techniquement
> nécessaire pour l'utiliser. Le chiffrement protège contre une fuite de la base de données, pas
> contre l'éditeur lui-même. Les garanties ci-dessus reposent sur le code, les tests et l'engagement
> contractuel, pas sur une impossibilité technique. C'est pourquoi nous recommandons une clé dédiée
> à budget limité.

🔶 US-143 (§67) le note : le rôle propriétaire de la base n'est pas soumis à la RLS
(`migrations/migration_v18.sql:106-107`). Ne pas laisser l'écran suggérer le contraire.

### 8.4 Corpus contractuel

| Document | Ce qu'il doit contenir de nouveau |
|---|---|
| **CGU / CGV** | Le jardinier fournit sa clé et reste titulaire de son compte fournisseur · la facturation lui est directement imputée par ce fournisseur · l'éditeur ne revend pas de tokens · les fonctions susceptibles d'appeler sa clé, énumérées · l'absence de plafond applicatif et l'obligation de clé dédiée · les limites de responsabilité · la procédure en cas de consommation indue · les modalités de remboursement en cas d'erreur imputable à l'application |
| **Politique de confidentialité** | Le fournisseur LLM comme destinataire · les finalités · les durées de conservation (configuration, relevé, consentements) · les transferts hors EEE · le sort des prompts et réponses |
| **Liste des sous-traitants** | Hébergeur · fournisseur LLM par défaut de la plateforme · fournisseurs LLM tiers en BYOK · supervision et journaux · Telegram |
| **Registre des traitements** | Une entrée « configuration LLM utilisateur » et une entrée « relevé de consommation » |

**Clause de responsabilité proposée** — ⚠️ **à faire relire par un juriste**, en particulier sur les
plafonds d'indemnisation et la charge de la preuve du préjudice :

> L'utilisateur reste titulaire de son compte et de sa clé API. Les consommations sont facturées
> directement par le fournisseur du modèle. L'application utilise la clé exclusivement pour les
> requêtes initiées par l'utilisateur ou pour les traitements automatiques qu'il a explicitement
> activés. Chaque consommation est tracée et consultable. L'utilisateur peut désactiver sa clé et
> demander sa suppression à tout moment. L'éditeur demeure responsable des consommations indues
> résultant d'une défaillance de l'application, d'un usage non autorisé ou d'une insuffisance de
> sécurité qui lui est imputable.

🔶 Une exclusion totale de responsabilité en cas de bug, de mauvaise isolation ou de fuite de clé
serait juridiquement fragile — et commercialement contre-productive sur un produit dont l'argument est
précisément le cloisonnement.

---

## 9. Ce que chaque agent doit produire

| US | Fichiers attendus | Tests attendus |
|---|---|---|
| US-170 | `app/services/context.py`, `tools/rejeu_corpus.py`, `app/services/potagers.py` | Complément à `test_us084_suppression_definitive_potager.py` · test « aucun contexte par défaut ne désigne un potager réel » |
| US-171 | `securite/coffre.py`, `migrations/migration_v46.sql`, filtre de journalisation, `docs/RUNBOOK_DEPLOIEMENT_PRODUCTION.md` (rotation KEK) | Aller-retour sceller/ouvrir · **échec de déchiffrement avec un mauvais `potager_id`** · rotation de KEK rejouée · aucune clé dans les journaux (3 chemins) |
| US-172 | `llm/passerelle.py` (`_resoudre_client`, `modele_pour`), écriture du cache | Isolation A/B · cache partagé jamais alimenté par une clé tierce · transcription toujours plateforme · nouvelle clé effective sans redémarrage · audit AST : un seul point de résolution |
| US-173 | Endpoints `PUT/DELETE /potagers/{id}/llm-config`, `POST …/llm-config/test`, écran PWA | Propriétaire seul · clé invalide jamais activée · clé jamais réaffichée · aucune réponse d'API ne contient la clé |
| US-174 | `migrations/migration_v47.sql`, journal d'imputation dans la passerelle | Ligne écrite même en cas d'échec · tokens issus de la réponse fournisseur · invariante « origine_cle=potager ⇒ config active » |
| US-175 | Endpoint de relevé, export CSV/PDF, écran PWA, alertes | Totalisation en UTC · une alerte par seuil et par mois · mention légale présente dans les deux exports |
| US-176 | `migrations/migration_v48.sql`, textes versionnés dans le dépôt, CGU/CGV, politique de confidentialité, liste de sous-traitants | Consentement obligatoire avant activation · les huit mentions du §8.2 présentes dans le texte · désactivation = révocation horodatée |
| US-177 | `llm/passerelle.py` (chemins d'erreur), messages | Aucun appel plateforme après échec du fournisseur du potager · fonctions déterministes préservées · pas de désactivation automatique sur erreur d'authentification |
| US-178 | `app/services/potagers.py`, écran de suppression définitive | Purge complète des trois tables · export proposé avant confirmation · désactivation détruit le secret |

### Règles de conduite pour les agents

1. **Une seule US à la fois.** US-172 touche le point de passage de toutes les réponses du produit.
2. **Vérifier la référence avant de l'utiliser.** Chaque `fichier:ligne` de ce document vient d'US-143,
   pas d'une lecture du code. Un écart se signale, il ne s'absorbe pas.
3. **Vérifier le dernier numéro de migration** avant d'en créer une. Les numéros v46/v47/v48 proposés
   ici supposent que v45 est la dernière livrée — 🔶 à confirmer.
4. **Aucune migration ne rouvre une table modifiée par une US en vol.**
5. **Chiffrer tout appel LLM ajouté ou modifié** (tokens, tier de routage, effet sur les limites Groq).
   Pour cet Épic : un seul appel ajouté, le test de clé, sur la clé du jardinier — jamais sur celle de
   la plateforme.
6. **Ne jamais présenter une inférence comme une observation.**

---

## 10. Points à vérifier dans le code avant de démarrer

Récapitulatif des 🔶 de ce document. Aucune US ne démarre avant que la ligne qui la concerne soit levée.

| # | À vérifier | Bloque |
|---|---|---|
| 1 | Aucune US n'occupe déjà la bande US-170 → US-178 | La création des fiches |
| 2 | `migration_v45.sql` est bien la dernière livrée | US-171, US-174, US-176 |
| 3 | Colonnes réellement présentes dans `conso_tokens` (`database/models.py:734-774`) | US-174 |
| 4 | La RLS couvre-t-elle `questions_cache` scopé par `potager_id` ? | US-172 (arbitrage A) |
| 5 | `_resoudre_client` est-il appelé **avant** ou **après** que la cascade ait décidé qu'un appel LLM partira ? | US-172 (coût du CA18) |
| 6 | Le cache sémantique calcule-t-il un embedding par question, et sur quel client ? | US-172 (§7.1) |
| 7 | Les trois dettes d'US-170 sont-elles toujours présentes ? | US-170 |
| 8 | Le format de réponse des clients HTTP utilisés expose-t-il l'identifiant de requête du fournisseur ? | US-174 (§6.1) |

---

## 11. Séquencement

```
US-170 ────────────────────────────────►  (livrable dès maintenant, hors US-092)
                                    │
                    US-092 (passerelle, bloquante) ────┐
                                    │                  │
                                US-171 ────────────────┤
                                    │                  │
                                US-172 ◄───────────────┘
                                 │   │
                         US-173 ◄┘   └► US-174 ──► US-175
                            │                        │
                            └──► US-176 ◄────────────┘
                                    │
                          US-177 ───┴─── US-178
```

**Jalon de vérification à mi-parcours**, après US-174 : dérouler un rapprochement réel entre un relevé
et une facture de fournisseur sur un compte de test. Si le rapprochement ligne à ligne n'est pas
possible à ce moment-là, US-175 est à revoir **avant** d'être écrite, pas après.

---

## 12. Risques

| Risque | Gravité | Traitement |
|---|---|---|
| **US-092 glisse** — l'Épic entier est bloqué derrière elle | 🔴 Élevée | US-170 est livrable en attendant. Ne pas commencer US-171 « pour avancer » : son intérêt dépend du point de résolution |
| **Le rapprochement facture s'avère impossible** chez le fournisseur visé (pas d'identifiant sur la facture) | 🟡 Moyenne | Jalon §11. Le relevé reste rapprochable par (date, modèle, tokens) — le dire dans l'écran plutôt que de le laisser découvrir |
| **La rotation de KEK n'est jamais rejouée** — le chiffrement devient un délai | 🟡 Moyenne | Test de rotation dans US-171, pas seulement une procédure écrite |
| **Absence de plafond bloquant** — une boucle facture le jardinier | 🟡 Moyenne | Arbitrage C assumé. Clé dédiée en condition d'activation. Le plafond bloquant reste peu coûteux à ajouter après US-174 |
| **La clause de responsabilité n'est pas relue par un juriste** avant mise en ligne | 🟡 Moyenne | US-176 ne se clôt pas sans cette relecture |
| **Le cache privé fait exploser la table `questions_cache`** — N potagers × leurs répétitions | 🟢 Faible | La purge à 90 jours existe déjà. 🧪 À mesurer si le nombre de potagers BYOK croît |
| **Un fournisseur exotique casse le post-traitement** | 🟢 Faible, et c'est prévu | CA10/CA11 : post-traitement identique, message désignant la configuration |
