# 🌿 Assistant Potager — Conception : cycle de vie du potager

## Création, sélection, switch et archivage d'un potager en contexte multi-tenant

> Document de conception — associé développeur senior.
> Destiné à alimenter la rédaction d'US par l'agent PO (`.github/agents/Personna PO.agent.md`).
> **Suivi d'avancement de l'épic : §7.2** — US rédigées le 2026-08-20 (`backlog/US-080` → `US-088`).
> S'inscrit dans la lignée de `REFLEXION_STRATEGIQUE_multi_utilisateurs.md` (§5.2 auth, §7 trajectoire)
> et complète `BACKLOG_US_MULTITENANT.md` (US-058, US-112, US-114 déjà cadrées mais partielles).
>
> Convention : ✅ fait établi · 🔶 hypothèse · 🧪 à tester · ⚖️ arbitrage produit à trancher.

---

## 1. Le trou dans la raquette — cadrage factuel

### 1.1 Ce qui existe aujourd'hui ✅

**Côté back (`main.py:478`)**
- `POST /potagers` — authentifié, crée un `Potager`, insère `potager_membres` avec rôle `owner`, définit le nouveau potager comme actif de l'utilisateur.
- Signature : `creer_potager(db, user_id, nom, latitude=None, longitude=None)` — accepte déjà `lat/lon`, jamais utilisés en amont.
- **Aucun autre chemin de création** : pas d'auto-création, rien côté bot Telegram.

**Côté front**
- `AucunPotager.jsx` — écran unique déclenché par `PotagerGate` (dans `App.jsx`) quand `aucunPotager === true`. Un champ `nom`, appel `creerPotager(nom.trim())`.
- `PotagerMenu` (sélecteur haut de page) — propose « Rejoindre un potager » (code d'invitation) et « Tous mes potagers » (bascule). **Aucun bouton « Créer »**.

**Côté bot Telegram**
- ❌ Rien. Aucune commande, aucune notion de potager exposée à l'utilisateur, aucun moyen de switcher.

### 1.2 Ce qui a été cadré mais reste partiel

| US existante | Ce qu'elle couvre | Ce qui manque |
|---|---|---|
| **US-058** (Onboarding « premier potager ») | Assistant PWA 4 étapes (potager + parcelle + cultures) affiché après inscription | Ne traite **que le premier** potager. Rien pour créer le second, le troisième, etc. Priorité basse assumée (§7.1 de l'analyse UI). |
| **US-112** (Potager actif) | Concept de `users.potager_actif_id`, commande `/potager` avec boutons inline, sélecteur PWA | Ne dit rien de la **création** ni de l'**archivage**. Ne clarifie pas ce qu'est un potager (lieu ? saison ?). |
| **US-114** (Invitations & onboarding self-service) | Création de potager depuis la PWA + invitations de membres + retrait | Cadrée avant analyse UI ; à réconcilier avec `PotagerMenu` et l'écran `AucunPotager`. |

### 1.3 Symptôme : trois angles morts

1. **Fonctionnel** — un utilisateur avec un potager ne peut pas en créer un second depuis l'UI.
2. **Cross-canal** — le bot est aveugle au concept de potager multiple ; incohérence future si un utilisateur a plusieurs potagers dans la PWA mais que le bot en pointe un seul de manière opaque.
3. **Conceptuel** — personne n'a défini **ce qu'est un potager du point de vue métier**. Sans ça, on va coder une UX qui autorise n'importe quoi (« créer un potager par saison », « créer un potager par culture », etc.) et ruiner l'intérêt du multi-tenant.

> **Ordre du raisonnement dans ce document.** On tranche d'abord la question métier (§2) ; on en déduit les cas d'usage légitimes (§3) ; on répartit front/bot (§4) ; on décrit le cycle de vie complet (§5) ; on liste les impacts techniques (§6) ; on découpe en US (§7) ; on isole les points ouverts (§8).

---

## 2. Question fondamentale — qu'est-ce qu'un potager ?

### 2.1 Trois modélisations candidates

| Modèle | Un potager = | Conséquence pratique |
|---|---|---|
| **A. Potager-lieu** | Un lieu géographique physique persistant, avec ses parcelles réelles | Un utilisateur en a rarement plus d'un ; multi-potager = lieux distincts (résidence principale + résidence secondaire, jardin partagé, etc.) |
| **B. Potager-saison** | Une campagne culturale annuelle (« mon potager 2026 ») | Un utilisateur en crée un chaque année ; l'historique multi-saison devient une agrégation entre potagers |
| **C. Potager-projet** | Une expérience ou un thème (« mon carré aromatiques », « potager d'école ») | Prolifération incontrôlée ; le tenant devient une entité arbitraire |

### 2.2 Arbitrage — pourquoi le modèle A gagne

**Pour A (potager-lieu)** :
- ✅ Cohérent avec les champs déjà présents : `nom`, `latitude`, `longitude` → un potager a une **localisation**, une localisation ne se déplace pas d'une saison à l'autre.
- ✅ Cohérent avec la cible du multi-tenant (`REFLEXION_STRATEGIQUE §3`) : *« 500 users / 100 potagers ≈ 5 personnes par jardin »* — les jardins sont **partagés dans le temps**, pas régénérés chaque année.
- ✅ Cohérent avec la valeur produit : **rotation, compagnonnage et bilan multi-saison** (§2.B/C de la réflexion stratégique) n'ont de sens **qu'en regardant la même parcelle sur plusieurs années**. Créer un nouveau potager par saison **casse** la rotation par construction.
- ✅ Cohérent avec la météo par potager (US-124) : une localisation par potager, pas une localisation par saison.
- ✅ Cohérent avec le pricing (US-133) : un plan payant *« potagers multiples »* n'a de valeur que si les potagers représentent quelque chose de rare et signifiant (des lieux distincts), pas si l'utilisateur en crée un par saison mécaniquement.

**Contre B (potager-saison)** :
- ❌ Explose la volumétrie tenant : 500 users × 3 saisies/an = 1 500 potagers dès la 2ᵉ année, pas 100 comme dimensionné.
- ❌ Duplique les parcelles physiques à chaque saison, sans lien référentiel.
- ❌ Rend la rotation impossible à calculer sans logique inter-potagers ad hoc.
- ❌ Le bilan multi-saison devient une jointure entre tenants — contraire à l'isolation RLS (US-103).

**Contre C (potager-projet)** :
- ❌ Encourage la prolifération, dilue le sens du tenant, empêche tout dimensionnement.
- ❌ Aucun besoin exprimé aujourd'hui : les projets peuvent être portés par des **parcelles** ou des **étiquettes**, pas par un tenant complet.

### 2.3 Décision produit ⚖️

> **Un potager = un LIEU physique persistant, partagé par ses membres, hébergeant des parcelles réelles.**
>
> **La saison n'est PAS un tenant. C'est un attribut temporel implicite** (dérivé des dates des événements et de la date d'ouverture/clôture d'un cycle cultural — cf. `EPIC_CALENDRIER_CULTURAL` et notion de saison à formaliser dans US_Base_fiches_cultures).

**Corollaires immédiats :**
- Un utilisateur **standard** aura **UN** potager toute sa vie (celui de son jardin).
- Un utilisateur **atypique** en aura 2 ou 3 (résidence secondaire, jardin partagé collectif, etc.).
- Créer un nouveau potager doit être une **action peu fréquente** et **explicite** — pas un flux d'auto-service anodin.
- Le bilan multi-saison sera résolu **à l'intérieur d'un potager** (par découpage temporel des événements), pas par jointure entre potagers.

---

## 3. Cas d'usage cibles et anti-cas

### 3.1 Cas d'usage légitimes (à supporter) 🔶

| # | Persona | Situation | Fréquence estimée |
|---|---|---|---|
| **U1** | Le potagiste standard | UN potager, son jardin | ~85 % des users |
| **U2** | Le propriétaire deux résidences | Résidence principale + secondaire (météos et parcelles distinctes) | ~5 % |
| **U3** | Le membre d'un jardin partagé | Son potager perso + un potager associatif où il n'est qu'`editor` | ~5 % |
| **U4** | Le potagiste engagé | Son potager + celui d'un parent/ami dont il aide à gérer | ~3 % |
| **U5** | L'utilisateur en migration | Ancien potager (archivé) + nouveau (déménagement) | ~2 %, situationnel |

**Volumétrie déduite** : moyenne 1,15 potager/user × 500 users ≈ **575 potagers**. Compatible avec la cible 100 (le chiffre 100 était probablement une estimation basse — à recalibrer, mais **rien ne casse**). 🧪

### 3.2 Anti-cas explicites (à refuser ou décourager)

| Anti-cas | Pourquoi le refuser | Traitement UX |
|---|---|---|
| « Un potager par saison » | Casse la rotation, dilue le tenant | Ne pas exposer de « nouvelle saison » comme création de potager. Prévoir plutôt une notion de **cycle saisonnier interne** au potager. |
| « Un potager par culture » | Absurde métier | Aucun bouton n'encourage ça. Le concept est **parcelles**, pas potagers. |
| « Un potager de test » | Pollue le compte, gonfle la conso Groq | Prévoir un mode « brouillon » ou un **potager de démo** géré côté produit, pas un vrai tenant par utilisateur. 🔶 (à débattre) |
| « Un potager par membre » | Anti-collaboratif, à l'opposé du modèle 5 personnes/jardin | Le partage se fait par **invitation** (US-114), pas par duplication. |

### 3.3 Anti-cas ambigus — à trancher explicitement ⚖️

- **Cas migration de saison** : un utilisateur veut « repartir à zéro » en gardant l'historique. Est-ce (a) un nouveau potager + archivage de l'ancien, ou (b) une clôture de saison **dans** le même potager ?
  - **Recommandation** : (b), via une notion de « clôture de saison » à venir (`EPIC_CALENDRIER_CULTURAL` — cf. `US-064` clôture Lot B). Le potager reste, la saison bascule.
- **Cas déménagement réel** : l'utilisateur a physiquement changé de jardin.
  - **Recommandation** : (a) archivage de l'ancien + création du nouveau. C'est bien un lieu différent.

---

## 4. Répartition Front ⇄ Bot — principe directeur

### 4.1 Rappel du positionnement des deux canaux

D'après le principe stratégique du projet (memories, `REFLEXION_STRATEGIQUE §5.3`) :

- **PWA React = interface commerciale principale** — tout ce qui est CRUD lourd, configuration, RGPD, billing, gestion des membres.
- **Bot Telegram = couche de capture terrain** — vocal mains libres en extérieur, prise rapide d'événements, consultation succincte.

Ce principe n'a pas de raison d'être remis en cause pour la gestion des potagers.

### 4.2 Application au cycle de vie du potager

| Action | PWA | Bot Telegram | Justification |
|---|---|---|---|
| **Créer un potager** | ✅ Complet (formulaire riche : nom, ville, lat/lon, parcelles initiales) | ❌ Non exposé | Création rare + champs multiples + géolocalisation = friction inadaptée au vocal. Le bot reçoit une invitation, pas une commande de création. |
| **Voir la liste de ses potagers** | ✅ `PotagerMenu` (déroulé) | ✅ `/potager` (boutons inline, US-112) | Consultation légère, adaptée aux deux canaux. |
| **Switcher de potager actif** | ✅ Clic dans `PotagerMenu` | ✅ Clic sur bouton inline `/potager` | Action fréquente et rapide — doit être identique dans les deux canaux pour éviter la confusion. |
| **Renommer un potager** | ✅ Menu de gestion | ❌ Non exposé | Action rare, saisie textuelle inconfortable en vocal. |
| **Modifier la localisation** | ✅ Menu de gestion (avec géocodage éventuel) | ❌ Non exposé | Champs structurés, hors périmètre vocal. |
| **Archiver un potager** (soft-delete) | ✅ Menu de gestion (double confirmation) | ❌ Non exposé | Action sensible, jamais dans le flux terrain. |
| **Supprimer définitivement** | ✅ Menu de gestion (owner uniquement, mot de passe re-demandé) | ❌ Non exposé | Action destructive irréversible ; RGPD. |
| **Inviter un membre** | ✅ (`ModalMembres`, US-055) | ❌ Génération de code uniquement | Codes affichés uniquement dans la PWA (canal sécurisé, copie facile). |
| **Rejoindre un potager via code** | ✅ (`ModalPotagers`, US-055) | 🔶 Envisageable : `/rejoindre <code>` | Le bot peut accepter un code textuel court (6 caractères). À trancher : utile ou redondant avec la PWA ? Recommandation : oui, car un nouvel utilisateur pourrait recevoir le code par un canal externe (SMS, mail, oral) et être plus à l'aise dans Telegram. |
| **Notification de changement de potager actif** | Bandeau visible en haut | Message texte de confirmation | Cohérence : le user sait toujours **où il écrit**. |

### 4.3 Règle transverse : cohérence du potager actif entre canaux

> ✅ **Le potager actif est UNIQUE par utilisateur** (colonne `users.potager_actif_id`, US-112). Si l'utilisateur switche dans la PWA, le bot suit au message suivant, et inversement.

Implications :
- Le bot lit `users.potager_actif_id` **à chaque message** (pas de cache local par `chat_id`) — cf. §6.2.
- Un changement de potager actif via un canal doit être **visible** dans l'autre à la prochaine interaction (ex. le bot annonce « Tu écris maintenant sur *Potager de Bretagne* »).

**Cas limite** : que se passe-t-il si un membre est **retiré** d'un potager (par un owner) alors que c'était son potager actif ? Réponse : le back invalide `potager_actif_id`, bascule automatiquement sur un autre potager auquel il appartient encore, ou passe à `NULL` s'il n'en a plus. Bot et PWA affichent un message clair au prochain accès. Cf. US-113 CA sur retrait de membre.

---

## 5. Cycle de vie complet du potager

### 5.1 États d'un potager

```
     ┌─────────┐        ┌─────────┐        ┌──────────┐        ┌───────────┐
     │  DRAFT  │──────► │  ACTIF  │──────► │ ARCHIVÉ  │──────► │ SUPPRIMÉ  │
     └─────────┘        └─────────┘        └──────────┘        └───────────┘
       (optionnel)         (par défaut)      (soft-delete)       (hard-delete
                                                                  irréversible)
```

| État | Description | Actions autorisées | Visibilité |
|---|---|---|---|
| `DRAFT` 🔶 | Créé dans l'assistant, pas encore finalisé (parcelles/membres à ajouter) | Édition, finalisation, suppression | Owner uniquement |
| `ACTIF` | Utilisation normale | Toutes selon rôle | Tous les membres |
| `ARCHIVÉ` | Lecture seule ; données conservées ; n'apparaît plus dans le sélecteur par défaut | Lecture, désarchivage, suppression | Membres, mais filtré du sélecteur (case « voir les archivés ») |
| `SUPPRIMÉ` | Physiquement supprimé après un délai de grâce (ex. 30 j) — cf. RGPD, US-132 | — | Personne |

⚖️ **À trancher** : l'état `DRAFT` est-il utile ? Alternative : la création est **atomique** (le potager naît `ACTIF` avec au moins un membre `owner` — c'est l'utilisateur qui le crée). Si oui, supprimer `DRAFT`.

**Recommandation** : supprimer `DRAFT` — la création atomique est plus simple et évite les potagers fantômes. L'assistant US-058 collecte les données en front puis fait UN appel de création.

### 5.2 Parcours utilisateur — création d'un potager

**Cas #1 — Premier potager (post-inscription)** — cf. US-058 (déjà cadrée, priorité basse)
- Assistant 4 étapes dans la PWA : potager → parcelle → cultures → récapitulatif.
- L'utilisateur devient `owner`, le potager devient son `potager_actif_id`.

**Cas #2 — Potager additionnel (nouveau parcours à créer)** — **le trou identifié**
- Entrée : bouton **« Créer un nouveau potager »** dans `PotagerMenu` (à ajouter, aujourd'hui absent).
- Formulaire similaire à l'étape 1 de US-058 (nom, ville, lat/lon), sans forcer parcelles ni cultures (le user est déjà expérimenté, il complètera ensuite).
- Choix explicite : *« Faire de ce potager mon potager actif dès maintenant ? »* [Oui / Plus tard].
- Confirmation, retour au `PotagerMenu` avec le nouveau potager visible.

**Cas #3 — Rejoindre un potager existant** — cf. US-114 (déjà cadrée) + `ModalPotagers` (US-055 déjà livrée)
- Saisie d'un code d'invitation reçu par un owner.
- Rôle imposé par l'invitation (`editor` par défaut, `lecteur` sur choix de l'owner).

### 5.3 Parcours utilisateur — switch de potager actif

**PWA** — cf. US-112
- Clic sur `PotagerMenu` → liste des potagers → sélection.
- Toutes les vues (Dashboard, Plan, Stocks…) se rechargent avec le nouveau `TenantContext`.
- Bandeau confirmant « Tu es sur *Potager X* ».

**Telegram** — cf. US-112
- Commande `/potager` → boutons inline listant les potagers (avec 🟢 sur l'actif).
- Clic → message de confirmation « OK, tu écris maintenant sur *Potager X* (Y membres, Z parcelles) ».
- Si un seul potager : `/potager` renvoie simplement le nom (pas de sélecteur, cohérent avec US-112 « si un seul potager, sélection auto silencieuse »).

### 5.4 Parcours utilisateur — archivage & suppression

**Archivage (owner uniquement)**
- Menu de gestion du potager (dans PWA, à concevoir — pas dans `AccountMenu`, plutôt dans un nouvel écran « Paramètres du potager »).
- Double confirmation : « L'archiver le rend inaccessible en écriture. Tu pourras le désarchiver plus tard. »
- Si c'était le potager actif → bascule automatique sur un autre potager, ou retour à `AucunPotager` s'il n'y en a pas d'autre.

**Suppression définitive (owner uniquement, RGPD)**
- Uniquement depuis un potager déjà `ARCHIVÉ` (obligation de passer par l'étape intermédiaire).
- Re-saisie du mot de passe.
- Message explicite : « Cette action supprime définitivement N événements, M parcelles, K photos. Irréversible après 30 jours de délai de grâce. »
- Notification aux autres membres.
- Cf. US-132 (RGPD) pour le traitement du dernier owner qui supprime son propre compte.

### 5.5 Cas particuliers ⚖️

| Situation | Comportement proposé |
|---|---|
| L'owner unique quitte le potager (ne se supprime pas, mais quitte) | Interdit tant qu'il n'a pas désigné un autre owner. Le back refuse. Message clair côté UI. |
| L'owner unique supprime son compte (RGPD) | Cf. US-132 : soit transfert automatique à un autre membre (le plus ancien `editor`), soit suppression du potager. **Recommandation** : transfert avec notification, suppression si aucun membre restant. |
| Un membre est retiré alors que c'est son potager actif | Back invalide `potager_actif_id`, propose un autre potager, ou `AucunPotager` si vide. Le bot le dit au prochain message. |
| Un membre change son propre rôle | Impossible par principe. Seul un `owner` peut changer les rôles. |
| Un `lecteur` tente d'inviter | Refusé côté services (`require_role('owner')` sur les invitations). |

---

## 6. Impacts techniques

### 6.1 Modèle de données — ajouts

Sur la table `potagers` (US-100 + extension) :

```sql
ALTER TABLE potagers
  ADD COLUMN ville         VARCHAR(120) NULL,  -- cf. US-058 (déjà prévu)
  ADD COLUMN etat          VARCHAR(20)  NOT NULL DEFAULT 'actif'
                           CHECK (etat IN ('actif', 'archivé', 'supprimé')),
  ADD COLUMN archive_le    TIMESTAMP NULL,
  ADD COLUMN supprime_le   TIMESTAMP NULL,  -- soft-delete + délai de grâce
  ADD COLUMN plan          VARCHAR(20)  NOT NULL DEFAULT 'free';  -- cf. US-123/133
```

Index recommandé :
```sql
CREATE INDEX idx_potager_membres_user_etat
  ON potager_membres (user_id)
  INCLUDE (potager_id)
  WHERE potager_id IN (SELECT id FROM potagers WHERE etat = 'actif');
```
(à confirmer selon la charge — l'index simple `(user_id, potager_id)` suffit probablement à cette échelle. 🧪)

### 6.2 API REST — endpoints à ajouter

| Endpoint | Méthode | Rôle requis | Description |
|---|---|---|---|
| `/potagers` | GET | membre | Liste tous les potagers du user avec leur rôle, état, nombre de membres, nombre de parcelles. Filtres : `etat=actif|archivé|tous`. |
| `/potagers` | POST | authentifié | ✅ Existe déjà. À enrichir : accepter `ville`, `latitude`, `longitude`. |
| `/potagers/{id}` | GET | membre | Détails d'un potager (nom, ville, coord, membres, rôle du user courant). |
| `/potagers/{id}` | PATCH | owner | Modifier nom / ville / lat / lon. |
| `/potagers/{id}/archiver` | POST | owner | Passe `etat = 'archivé'`, `archive_le = now()`. |
| `/potagers/{id}/desarchiver` | POST | owner | Retour à `actif`. |
| `/potagers/{id}` | DELETE | owner | Soft-delete : `etat = 'supprimé'`, `supprime_le = now()`. Purge physique après 30 j (job de fond US-124). |
| `/potagers/{id}/actif` | PUT | membre | Définit ce potager comme potager actif du user courant. |
| `/potagers/{id}/quitter` | POST | membre non-owner | Le user se retire de ses potager_membres (interdit pour un owner unique). |

### 6.3 Bot Telegram — commandes à exposer

| Commande | Rôle | Comportement |
|---|---|---|
| `/potager` | tout membre | ✅ Cf. US-112. Liste + boutons inline pour switcher. Si 1 seul potager, affiche simplement le nom. |
| `/rejoindre <code>` | tout | 🔶 À trancher : ajouter au bot ? Recommandation OUI (nouvel utilisateur qui reçoit un code par SMS/mail préfère souvent Telegram à ouvrir la PWA). |
| ❌ Pas de `/creer` | — | Création réservée à la PWA (voir §4.2). |
| ❌ Pas de `/archiver` ni `/supprimer` | — | Idem. Actions sensibles → PWA. |

**Point critique de flux** ⚠️ : dans `bot.py`, la vérification du potager actif doit être placée **avant** les priorités actuelles des flux `handle_text` / `handle_voice` (cf. règle d'ordre critique dans BACKLOG §7 des invariants). Structure cible :

```
PRIORITÉ 0 — utilisateur non lié (US-111) → refus + onboarding
PRIORITÉ 0 bis — utilisateur sans potager actif → invitation à en choisir un
PRIORITÉ 1 — modes correction actifs
PRIORITÉ 2 — mode ask actif
PRIORITÉ 3 — mots-clés NAV
PRIORITÉ 4 — _is_question
PRIORITÉ 5 — _parse_and_save
```

### 6.4 Front PWA — modifications minimales

**Composants à modifier**
- `PotagerMenu` (dans `web-account.jsx` livré) : **ajouter une entrée « + Créer un nouveau potager »** dans le déroulé, entre la liste et « Tous mes potagers ». C'est **le point d'entrée manquant**.
- `PotagerGate` (dans `App.jsx`) : conserver son comportement actuel (bascule sur `AucunPotager` si aucun potager). Éventuellement l'étendre pour gérer le cas « le potager actif a été archivé/supprimé pendant la session » → bascule silencieuse sur un autre potager ou sur `AucunPotager`.

**Nouveaux écrans**
- **Écran « Paramètres du potager »** (nouveau) : accessible depuis un lien dans `PotagerMenu` sur le potager actif. Regroupe : renommer, modifier localisation, archiver, supprimer, quitter. Réservé à l'owner sauf « quitter » (tout membre non-owner). 🔶 À concevoir visuellement dans un lot dédié (cohérent avec le style Lot B).
- **Modale « Créer un nouveau potager »** : formulaire léger (nom, ville, lat/lon optionnelle) + case « Le rendre actif dès maintenant ». Beaucoup plus simple que l'assistant US-058 (pas de parcelles ni de cultures — le user complètera ensuite dans les écrans dédiés).

**Composants inchangés**
- `AucunPotager.jsx` — reste le point d'entrée du premier potager. Peut évoluer plus tard vers l'assistant complet US-058.
- `ModalPotagers` (US-055) — inchangée pour la partie « rejoindre par code » ; on peut y ajouter le bouton « Créer un nouveau potager » comme deuxième chemin, en miroir de l'entrée dans `PotagerMenu`.

### 6.5 Impact sur le TenantContext et la couche services

Rien de neuf : le `TenantContext(user_id, potager_id, role)` cadré en US-101 fonctionne à l'identique. La seule chose à s'assurer :

- Toute lecture qui liste les potagers d'un user doit **respecter `etat`** (par défaut, ne retourne que `actif` sauf demande explicite).
- Le service `switcher_potager_actif(user_id, potager_id)` doit vérifier que le user est bien membre du potager cible ET que ce potager n'est pas `supprimé`.

---

## 7. Découpage en User Stories suggéré

Les US ont été **rédigées** par l'agent PO le 2026-08-20 dans `backlog/`, au format habituel
(critères d'acceptance + Gherkin). Le §7.2 ci-dessous est le **tableau de suivi de référence** de
l'épic : il est mis à jour à chaque livraison.

⚠️ **Numérotation** : ce document raisonnait sur la trame abandonnée `US-100 → US-133`
(`BACKLOG_US_MULTITENANT.md`). Les US réelles suivent la numérotation du backlog livré et occupent
**US-080 → US-088** (dernier numéro pris avant elles : US-079). La correspondance avec le découpage
initialement proposé (US-150 → US-157) figure en §7.4.

### 7.1 Épic dédié — « Cycle de vie du potager »

**Positionnement dans la trajectoire** : postérieur à US-046 (potager actif) et US-048 (invitations),
antérieur à la facturation Stripe/freemium. Les US sont regroupées dans un épic dédié,
**ÉPIC 5 — Cycle de vie du potager**, déclaré dans `.github/agents/Personna PO.agent.md` à la suite
des quatre épics de `BACKLOG_US_MULTITENANT.md`.

> **Numéro d'épic** : le numéro 3 est déjà pris par `ÉPIC 3 — Fiabilité & maîtrise du coût`
> (Redis, LLM à étages, quotas, jobs de fond, Alembic — §120 du backlog multi-tenant), dont la
> trajectoire est indépendante. Le nouvel épic prend donc le numéro **5**. La branche de travail
> `epic-3-cycle-vie-potager` conserve son nom, antérieur à cet arbitrage — son « 3 » ne désigne pas
> le numéro d'épic.

### 7.2 ÉPIC 5 — Cycle de vie du potager

**Statuts** : 📋 à faire · 🚧 en cours · ✅ livrée (indiquer la version `PATCH_NOTES.md`).
**Total : 31 points** — 9 US.

| US | Titre | Description | Effort | Dépendances | Statut | Jira |
|---|---|---|---|---|---|---|
| **US-080** | Modéliser le cycle de vie d'un potager | Colonnes `potagers.etat` (`actif`/`archive`/`supprime`), `archive_le`, `supprime_le` ; backfill à `actif` ; filtrage par état par défaut dans les services et `GET /potagers?etat=` ; un potager non actif ne peut plus être le potager actif. Aucun changement visible pour l'utilisateur. | 3 | US-040, US-046, US-054 | 📋 | — |
| **US-081** | Créer un potager additionnel depuis la PWA | Entrée « + Créer un nouveau potager » dans `PotagerMenu` et « Tous mes potagers » ; modale légère (nom + `VilleSearch`) ; case « en faire mon potager actif » ; encart « nouvelle saison ≠ nouveau potager ». **Résout le trou fonctionnel principal du §1.3.** | 3 | US-080, US-054, US-074, US-048 | 📋 | — |
| **US-082** | Écran « Paramètres du potager » | Regroupe identité (nom/localisation, US-074 absorbée), membres (US-048 intégrée) et une « zone sensible » qui accueille les actions de cycle de vie ; nouvel endpoint `GET /potagers/{id}` ; lecture seule pour `editor`/`lecteur`. | 5 | US-080, US-074, US-048, US-047, US-052/053 | 📋 | — |
| **US-083** | Archiver et désarchiver un potager | `POST /potagers/{id}/archiver` et `/desarchiver` (owner) ; archivé = **lecture seule** gardée dans les services ; invalidation du potager actif de chaque membre concerné ; filtre « voir les archivés » ; notification Telegram des membres. | 5 | US-080, US-082, US-047, US-045 | 📋 | — |
| **US-084** | Supprimer définitivement (délai de grâce 30 j) | `DELETE /potagers/{id}` refusé hors état archivé ; décompte réel de ce qui sera perdu ; re-saisie du mot de passe ; soft-delete puis purge physique idempotente à J+30 ; restauration possible pendant le délai. | 5 | US-080, US-083, US-082, US-044 | 📋 | — |
| **US-085** | Changer le rôle d'un membre / transférer la propriété | **US non prévue par ce document** (cf. §7.5) : aucun mécanisme de changement de rôle n'existe aujourd'hui. Permet la promotion `owner`, la correction `lecteur`↔`editor`, et pose la garde « dernier owner » réutilisée par US-084 et US-086. | 3 | US-047, US-048, US-082 | 📋 | — |
| **US-086** | Quitter un potager | `POST /potagers/{id}/quitter` ; refusé au dernier owner (renvoi vers US-085) ; invalidation du potager actif ; les données saisies restent dans le potager. | 2 | US-085, US-048, US-082 | 📋 | — |
| **US-087** | Bot — commande `/rejoindre <code>` | Seule action de cycle de vie exposée au bot (§4.2) ; réutilise `accepter_invitation()` sans dupliquer de règle ; messages dédiés par cas d'échec ; ne bascule le potager actif que si l'utilisateur n'en avait aucun. Zéro token Groq. | 2 | US-045, US-048, US-046 | 📋 | — |
| **US-088** | Cohérence bot ⇄ PWA du potager actif | Le bot annonce **une seule fois** tout changement de potager actif venu du web, en distinguant bascule volontaire et bascule subie (archivage) ; symétrie côté `PotagerGate`. Silencieux pour un utilisateur mono-potager. | 3 | US-046, US-080, US-083 | 📋 | — |

### 7.3 Ordre de livraison recommandé

```
US-080 (modèle) ──► US-081 (créer additionnel)
       │
       ├──► US-082 (paramètres) ──► US-083 (archivage) ──► US-084 (suppression)
       │                                   ▲                        ▲
       │                    US-085 (rôles / propriété) ─────────────┘
       │                                   └──► US-086 (quitter)
       │
       ├──► US-088 (cohérence actif)
       └──► US-087 (bot /rejoindre)   [livrable en parallèle, dépend seulement de l'existant]
```

**Chemin critique produit** : `US-080 → US-081` (résout le trou fonctionnel principal). Le reste peut
être livré itérativement. `US-085` est un **pré-requis dur** de `US-086` et du transfert RGPD (§5.5).

### 7.4 Correspondance avec le découpage initialement proposé

| Proposition d'origine | US réelle | Écart |
|---|---|---|
| US-150 — Modèle d'état | **US-080** | Périmètre identique ; valeurs d'état sans accent en base (`archive`, `supprime`), libellés accentués à l'affichage. |
| US-151 — Créer un potager additionnel | **US-081** | Identique. Quota freemium laissé hors périmètre (§8.4 non tranché), emplacement du message prévu. |
| US-152 — Écran « Paramètres » | **US-082** | **Rescopée** : renommer/localiser est déjà livré par US-074 (`PATCH /potagers/{id}` + `ModalModifierPotager`). L'US devient un regroupement, pas une création de fonctionnalité. |
| US-153 — Archivage / désarchivage | **US-083** | Identique + notification Telegram des membres (arbitrage §8.7 tranché : oui). |
| US-154 — Suppression définitive | **US-084** | Identique + droit au remords explicite (restauration pendant le délai de grâce). |
| — | **US-085** | **Ajout** — voir §7.5. |
| US-155 — Quitter un potager | **US-086** | Identique, mais dépend désormais de US-085 pour le cas de l'owner unique. |
| US-156 — Bot `/rejoindre` | **US-087** | Identique. Garde de liaison US-045 exigée (un chat non lié est renvoyé vers `/lier`). |
| US-157 — Cohérence bot ⇄ PWA | **US-088** | **Rescopée à la baisse** : la lecture de `users.potager_actif_id` à chaque message et la priorité 0 bis sont **déjà implémentées** (US-046). Reste la visibilité du changement et la symétrie PWA. |

### 7.5 Écart de cadrage relevé à la rédaction — US-085

Le §5.5 pose la règle « l'owner unique ne peut quitter son potager qu'après avoir désigné un autre
owner », et le §8.6 prévoit un transfert de propriété au titre du RGPD. Or **aucun mécanisme de
changement de rôle n'existe** : le rôle est figé au moment de l'invitation (`invitations.role_propose`,
US-048) et `app/services/potagers.py` sait inviter, lister et retirer un membre — jamais promouvoir.

Sans US-085, US-086 enferme définitivement tout owner unique et le transfert RGPD est irréalisable.
D'où son ajout, avec une décision de modèle : **plusieurs owners sont autorisés** sur un potager
(`potager_membres` ne l'interdit pas), le transfert consistant à promouvoir puis, éventuellement, à se
rétrograder soi-même — jamais à laisser le potager orphelin.

---

## 8. Points ouverts à trancher explicitement ⚖️

1. **État `DRAFT` du potager** — à supprimer du modèle si la création est atomique. **Recommandation : oui, retirer.** Justifié §5.1.
2. **Anti-cas « potager de test »** — offre-t-on un potager de démo (données factices, non facturé) ? Impact pricing/marketing.
3. **Volumétrie cible** — recalibrer les « 100 potagers » à ~575 (§3.1) ? Si oui, mettre à jour `REFLEXION_STRATEGIQUE §6`.
4. **Plan freemium** — le plan `free` autorise-t-il 1 potager, N potagers, N potagers `actifs` en simultané ? Cadre `US-133` mais impacte l'UX de US-151. **Recommandation : 1 potager actif en free, N potagers actifs en payant. Les potagers archivés ne comptent pas.**
5. **Commande `/rejoindre` sur le bot** — indispensable (US-156) ou nice-to-have ? **Recommandation : indispensable** — un nouveau user reçoit typiquement le code par un canal externe et Telegram est son premier contact concret avec l'app.
6. **Traitement du dernier owner qui supprime son compte** — cf. US-132 RGPD. Transfert automatique au plus ancien `editor`, ou suppression du potager ? À expliciter dans US-132 en cohérence avec ce doc.
7. **Notification de changement d'état** — quand un potager est archivé par un owner, notifie-t-on les autres membres via Telegram ? **Recommandation : oui, message texte informatif.** Aligner avec US-124 (jobs de fond).
8. **Migration de saison vs déménagement** — clarifier dans la doc utilisateur (`guide_assistant_potager.md`) que **changer de saison ≠ créer un potager**. La clôture de saison relève de `EPIC_CALENDRIER_CULTURAL`. Prévoir un encart dans US-151 : « Tu veux redémarrer une nouvelle saison sur ton potager ? Utilise la clôture de saison, pas la création d'un nouveau potager. »

---

## 9. Invariants à rappeler dans chaque US découlant de ce doc

Reprise des invariants transverses de `BACKLOG_US_MULTITENANT.md §7`, avec spécificités :

1. Aucune US ne casse le comportement existant : un utilisateur actuel avec 1 potager doit continuer à l'utiliser sans changement perceptible.
2. Migrations SQL en fichier `migration_vX.sql` séparé, idempotentes, rollback documenté.
3. Toute lecture des potagers d'un user filtre par `etat = 'actif'` sauf demande explicite (`etat=archivé` ou `etat=tous`).
4. Toute action `owner`-only est doublement contrôlée : côté service (`require_role('owner')` — US-113) **et** côté API (dépendance FastAPI).
5. Le potager actif est **cohérent entre canaux** : bot et PWA lisent la même source (`users.potager_actif_id`).
6. Ordre critique des flux Telegram préservé (priorités 0 → 5), avec P0 bis ajouté pour « sans potager actif ».
7. Compatibilité SentinelOne : polling, pas de webhook.
8. `.replace()` sur les prompts Groq (jamais `.format()`), `db.get()` (jamais `db.query().get()`), logging structuré préservé.

---

## 10. Résumé exécutif — ce qui doit être décidé pour avancer

Trois décisions produit à valider par Emmanuel avant que l'agent PO ne rédige les US :

1. ⚖️ **Un potager = un lieu physique persistant** (modèle A du §2). Refus explicite du modèle « potager par saison ». → **Impacte l'ensemble du reste du doc.**
2. ⚖️ **Création réservée à la PWA**, consultation/switch dans les deux canaux, commande `/rejoindre` ajoutée au bot. → **Cadre la répartition front/bot (§4).**
3. ⚖️ **Cycle de vie à 3 états** : `actif` → `archivé` → `supprimé` (avec délai de grâce). Pas de `DRAFT`. → **Simplifie US-150.**

✅ **Arbitrages tranchés et US rédigées** (2026-08-20) : les trois décisions ci-dessus ont été retenues
telles que recommandées, et le découpage a été décliné en **9 US formelles** (`backlog/US-080` à
`US-088`, 31 points), suivies dans le tableau du **§7.2**. Chemin critique : **US-080 → US-081**, qui
résout immédiatement le trou fonctionnel identifié.

Points ouverts **encore non tranchés** et sans US associée : le potager de démo (§8.2), la
recalibration de la volumétrie cible (§8.3), le plafond freemium (§8.4, laissé hors périmètre
d'US-081) et l'encart de documentation utilisateur « saison ≠ potager » (§8.8, dont la partie produit
est couverte par US-081/CA6).

---

*Fin du document. Le §7.2 est le tableau de suivi vivant de l'épic — le mettre à jour à chaque
livraison d'US (statut, version `PATCH_NOTES.md`, clé Jira).*
