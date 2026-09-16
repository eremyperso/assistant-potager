# Intégration Jira — Guide de configuration et d'utilisation

Ce guide explique comment configurer Jira pour gérer les User Stories depuis Claude Code,
qui fait quoi dans le flux PO → Jira → implémentation, et comment utiliser la CLI
`tools/jira_tracker.py` directement.

## 1. Prérequis

- Compte Atlassian Cloud (gratuit ou payant)
- Un projet Jira pour les US (ce dépôt utilise `PIA`, mais tout projet convient)
- Accès administrateur pour générer un token API

## 2. Générer un token API Jira

1. Allez sur [https://id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
2. Cliquez sur **Create API token**
3. Donnez un label : `claude-code`
4. Copier le token généré (attention, il ne s'affichera qu'une fois)
5. Stocker dans `.env.dev` :

```env
JIRA_API_TOKEN=<votre_token>
```

## 3. Configurer `.env.dev`

Complétez les variables Jira dans votre `.env.dev` :

```env
JIRA_HOST=https://eremy.atlassian.net
JIRA_EMAIL=eremy.perso@gmail.com
JIRA_API_TOKEN=<votre_token_api>
JIRA_PROJECT=PIA
JIRA_ENABLED=true
```

### Explications

| Variable | Description | Défaut dans le code |
|----------|-------------|----------------------|
| `JIRA_HOST` | URL de votre instance Jira Cloud | `https://eremy.atlassian.net` |
| `JIRA_EMAIL` | Email du compte Atlassian | `eremy.perso@gmail.com` |
| `JIRA_API_TOKEN` | Token API généré à l'étape 2 | — (obligatoire, sinon mode dégradé) |
| `JIRA_PROJECT` | Clé du projet Jira | `SCRUM` — **à surcharger en `PIA` sur ce dépôt** |
| `JIRA_ISSUE_TYPE` | Type d'issue créé par `create-issue`/`sync-backlog` | `Story` |
| `JIRA_ENABLED` | `true` pour activer Jira, `false` pour le mode dégradé | `true` |
| `JIRA_STATUS_A_FAIRE` | Libellé Jira du statut `a_faire` | `À faire` |
| `JIRA_STATUS_EN_COURS` | Libellé Jira du statut `en_cours` | `En cours` |
| `JIRA_STATUS_EN_QA` | Libellé Jira du statut `en_qa` | `Revue en cours` |

Les trois `JIRA_STATUS_*` collent au workflow observé sur le projet PIA (libellés en
français) ; à surcharger si votre workflow Jira utilise d'autres libellés (`To Do`,
`In Progress`…), sans toucher au code.

## 4. Vérifier la configuration

Deux scripts distincts, à ne pas confondre :

```powershell
cd "C:\Users\eremy\OneDrive - SQLI\Documents\GitHub\assistant-potager"
.\.venv\Scripts\Activate.ps1

# Smoke-test : imports, normalisation des identifiants/statuts, variables d'env
# présentes — ne fait AUCUN appel réseau, fonctionne même sans token.
python test_jira_setup.py

# Test de connexion réel : appelle l'API Jira, liste les 10 dernières issues
# du projet JIRA_PROJECT — nécessite un token valide.
python test_jira_api.py
```

`test_jira_api.py` doit afficher :
```
🔍 Test de connexion à https://eremy.atlassian.net...
Status: 200
✅ Connecté ! Utilisateur: <votre_nom>

📋 Récupération des issues du projet PIA...
Status: 200
✅ 10 issue(s) trouvée(s):
  • PIA-70: US-079 : Vérifier la création automatique d'un ticket Jira depuis une US [Revue en cours]
  ...
```

## 5. Comprendre le flux — qui fait quoi

**Point important, source de confusion fréquente : Persona PO n'écrit jamais dans Jira.**
Son seul livrable est un fichier `backlog/US-NNN_*.md` — il n'a pas l'outil `execute` et sa
règle absolue lui interdit tout terminal. Créer le ticket Jira est une étape **séparée**,
déclenchée soit par vous manuellement, soit par l'Orchestrateur en filet de sécurité.

```
1. Persona PO rédige l'US
   └─ backlog/US-NNN_titre-court.md (fichier local uniquement, rien dans Jira)
   ↓
2. VOUS lancez la synchronisation (manuel, indépendant de toute implémentation)
   └─ python tools/jira_tracker.py sync-backlog
      → l'US apparaît dans Jira, statut "À faire"
   ↓
3. Vous organisez vos sprints dans Jira (hors de portée de cet outillage)
   ↓
4. Vous invoquez l'Orchestrateur pour IMPLÉMENTER une US précise déjà choisie
   └─ @Orchestrateur-US-Jira US-066
      ├─ ÉTAPE 0 : retrouve l'issue Jira (déjà créée à l'étape 2 — cas normal)
      ├─ ÉTAPE 2 : python tools/jira_tracker.py US-066 en_cours, puis @Developer
      ├─ ÉTAPE 3 : @Qa-tester, puis python tools/jira_tracker.py US-066 en_qa si OK
      └─ ÉTAPE 4 : Patch Notes Writer → PATCH_NOTES.md + VERSION
   ↓
5. Déploiement (passe l'issue en "Terminé" — hors de portée de cet outillage,
   aucun agent ni commande ne pilote ce statut)
```

**Filet de sécurité** : si vous invoquez `@Orchestrateur-US-Jira US-XXX` sur une US dont le
ticket Jira n'existe pas encore (vous avez sauté l'étape 2, ou l'US vient d'être rédigée à
l'instant), l'Orchestrateur la crée lui-même via `create-issue` avant d'enchaîner — mais ce
n'est jamais le chemin attendu en usage normal, et il ne le fait **que pour l'US demandée**,
jamais pour tout le backlog.

## 6. Guide d'utilisation des agents

### `@Persona PO` — rédiger une US

```
@Persona PO ajouter un rappel météo avant récolte
```
Produit `backlog/US-NNN_titre-court.md`. Ne touche à rien d'autre, ne parle jamais à Jira.

### `@Suivi-US-Jira` — faire apparaître les US dans Jira et suivre leur statut

C'est l'agent à invoquer directement pour du **refinement** (rendre visibles dans Jira des
US déjà rédigées) ou pour une transition de statut isolée, sans passer par tout le cycle
d'implémentation.

```
@Suivi-US-Jira sync-backlog
```
→ Parcourt `backlog/*.md`, crée dans Jira chaque US qui n'y existe pas encore. Idempotent,
rejouable sans dupliquer. Ne déclenche jamais Developer ni QA.

```
@Suivi-US-Jira US-066 en_cours
```
→ Transition de statut isolée (utile si vous voulez juste refléter un changement d'état
sans repasser par l'Orchestrateur complet).

### `@Orchestrateur-US-Jira` — implémenter une US de bout en bout

```
@Orchestrateur-US-Jira US-066
```
ou simplement :
```
@Orchestrateur-US-Jira 066
```
Enchaîne Developer → QA → Documentation en pilotant les transitions de statut Jira à
chaque étape. C'est l'agent à invoquer quand vous avez choisi **quelle** US implémenter
maintenant (typiquement après avoir organisé vos sprints dans Jira à l'étape 3 du flux
ci-dessus).

Peut aussi être invoqué sur une description libre si l'US n'existe encore ni dans Jira ni
en local — il rédige alors l'US (règles de Persona PO), crée le ticket, puis implémente :
```
@Orchestrateur-US-Jira adapter le stock selon le type d'organe récolté
```

## 7. Référence complète de la CLI `jira_tracker.py`

Toutes les commandes se lancent depuis la racine du dépôt, venv activé :

```powershell
python tools/jira_tracker.py <commande>
```

| Commande | Effet | Exemple |
|---|---|---|
| `<US ou clé Jira> <statut>` | Transition de statut d'une US | `python tools/jira_tracker.py US-066 en_cours` |
| `create-issue <fichier.md>` | Crée le ticket Jira pour **une** US depuis son fichier backlog | `python tools/jira_tracker.py create-issue backlog/US-066_titre.md` |
| `sync-backlog [dossier]` | Crée dans Jira toutes les US du backlog pas encore créées (défaut : `backlog/`) | `python tools/jira_tracker.py sync-backlog` |
| `list-sprints` | Liste les sprints du projet | `python tools/jira_tracker.py list-sprints` |
| `list-sprint <sprint_id>` | Liste les issues d'un sprint | `python tools/jira_tracker.py list-sprint 34` |

### Identifiants d'US acceptés

`normaliser_us()` accepte `66`, `"66"`, `"US-66"`, `"us-066"`, `"US066"` et les normalise
en `US-066`. **Ne jamais passer la clé Jira réelle directement** (`PIA-47`) : la commande
interpréterait `47` comme un numéro d'US et le résoudrait vers `US-047`, ce qui n'est pas ce
que vous voulez. La résolution `US-066 → PIA-47` se fait automatiquement, en interne, par
recherche sur le préfixe du résumé de l'issue — vous n'avez jamais besoin de connaître la
clé Jira réelle.

### Statuts acceptés (transitions)

| Statut logique | Alias reconnus en entrée | Libellé Jira (défaut) |
|---|---|---|
| `a_faire` | `a faire`, `à faire`, `afaire`, `todo`, `to do` | `À faire` |
| `en_cours` | `en cours`, `encours`, `in progress`, `in_progress` | `En cours` |
| `en_qa` | `en qa`, `qa`, `in qa`, `in_qa`, `in review`, `en_review` | `Revue en cours` |

`done`, `réalisé`, `terminé`, `fini` (et variantes) sont **explicitement refusés** — la
colonne finale est appliquée par le déploiement, jamais par cet outil.

### Exemples d'usage courant

```bash
# Créer tous les tickets manquants après une session de rédaction PO
python tools/jira_tracker.py sync-backlog

# Créer le ticket d'une seule US (filet de sécurité, normalement inutile si
# sync-backlog est lancé régulièrement)
python tools/jira_tracker.py create-issue backlog/US-066_reset-mot-de-passe.md

# Faire avancer une US au fil du développement
python tools/jira_tracker.py US-066 en_cours
python tools/jira_tracker.py 66 en_qa          # identifiant numérique nu accepté
python tools/jira_tracker.py US-066 "en cours" # variantes avec espace acceptées

# Consulter les sprints et leur contenu
python tools/jira_tracker.py list-sprints
python tools/jira_tracker.py list-sprint 34
```

### Depuis du code Python

```python
from tools.jira_tracker import update_issue_status, create_issue_from_backlog

update_issue_status("US-066", "en_cours")
create_issue_from_backlog("backlog/US-066_titre-court.md")
```

## 8. Architecture

### Structure des fichiers

```
tools/
└── jira_tracker.py                   # Client Jira REST + CLI (seul point d'accès à l'API)

.github/agents/
├── Orchestrateur-US-Jira.agent.md    # Pilote l'implémentation d'une US via Jira
├── Suivi-US-Jira.agent.md            # Refinement (sync-backlog) + transitions de statut
├── Personna PO.agent.md              # Rédige les US dans backlog/ (jamais Jira)
├── Developer.agent.md                # Implémente ; passe l'US en en_cours avant de coder
└── Qa-tester.agent.md                # Teste ; passe l'US en en_qa si validation OK

test_jira_setup.py                    # Smoke-test config (racine du dépôt, pas de réseau)
test_jira_api.py                      # Test de connexion réel (racine du dépôt)
tests/test_us079_jira_tracker.py      # Tests unitaires create_issue_from_backlog (mocks)
```

L'ancien système basé sur GitHub Issues (`tools/us_tracker.py`,
`Orchestrateur-US.agent.md`, `Suivi-US.agent.md`) a été retiré du dépôt — Jira est
désormais l'unique source de vérité pour le suivi des US.

## 9. Mode dégradé

Si `JIRA_API_TOKEN` est absent, `JIRA_ENABLED=false`, ou si l'API Jira est indisponible :
- Les commandes `python tools/jira_tracker.py` **enregistrent** l'action dans les logs
  (niveau `WARNING`) et rendent la main avec un code retour `0`
- Aucune exception n'est levée pour une cause externe — le développement continue
  normalement
- Le suivi n'est pas bloquant, c'est de l'observabilité : une panne de kanban ne doit
  jamais interrompre une implémentation en cours

`create_issue_from_backlog()` retourne alors `None`, `update_issue_status()` retourne
`False` — dans les deux cas, lisez la ligne `WARNING` dans la sortie pour savoir ce qui
aurait dû se passer.

## 10. Dépannage

### Erreur : "JIRA_API_TOKEN absent"

Vérifiez que `.env.dev` contient `JIRA_API_TOKEN=<votre_token>` et qu'il n'est pas vide.

### Erreur : "Impossible de se connecter"

- Vérifiez que `JIRA_HOST` est correct
- Vérifiez que `JIRA_EMAIL` correspond à votre compte Atlassian
- Vérifiez que le token API n'a pas expiré

### Erreur : "US-066 introuvable dans le projet"

- Vérifiez que l'issue existe dans Jira (a-t-elle été créée via `sync-backlog` ou
  `create-issue` ?)
- Vérifiez que le résumé de l'issue commence bien par `US-066 : ...` — la résolution se
  fait sur ce préfixe, pas sur la clé Jira
- Vérifiez que vous avez accès au projet `JIRA_PROJECT`

### Erreur : "Statut « X » indisponible"

Les transitions disponibles dépendent du workflow Jira du projet et de l'état courant de
l'issue (on ne peut pas toujours sauter directement d'un statut à un autre). Si vos
libellés Jira diffèrent des défauts (`À faire` / `En cours` / `Revue en cours`), surchargez
`JIRA_STATUS_A_FAIRE` / `JIRA_STATUS_EN_COURS` / `JIRA_STATUS_EN_QA` dans `.env.dev` plutôt
que de modifier `tools/jira_tracker.py`.

### Erreur 404 sur `list-sprints` : `Not Found for url: .../rest/api/3/board?...`

Bug déjà corrigé dans `tools/jira_tracker.py`, gardé ici en référence : les boards et
sprints vivent sous l'**API Agile** de Jira (`/rest/agile/1.0/board`), pas sous l'API
plateforme (`/rest/api/3/...`) utilisée partout ailleurs dans le fichier — ce sont deux
API REST distinctes côté Atlassian. Si l'erreur réapparaît après une modification du
fichier, c'est probablement qu'un appel a été récrit sur le mauvais préfixe.

## 11. Roadmap future

- [x] Créer des issues Jira depuis Claude Code — `create-issue` / `sync-backlog`
- [ ] Lier automatiquement les branches Git aux issues Jira (au-delà du préfixe `PIA-XX`
      dans les messages de commit, déjà exploité manuellement par l'app GitHub-for-Jira)
- [ ] Générer des releases depuis les issues fermées
- [ ] Intégration avec les commentaires Jira (logs de développement)

**Note sur le Backfill GitHub ↔ Jira** : l'app "GitHub for Jira" ne scanne que le **titre**
et le **body** (description) d'une Pull Request pour y détecter des clés Jira — jamais les
commentaires du fil de discussion. Pour rattacher rétroactivement d'anciennes PR à leurs
tickets Jira, la clé doit être ajoutée dans la description de la PR (`gh pr edit --body`),
pas en commentaire.
