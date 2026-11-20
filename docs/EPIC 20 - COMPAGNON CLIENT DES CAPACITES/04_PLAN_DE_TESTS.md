# 04 — Plan de tests : ce que je mène, à quelle étape

Quatre niveaux de contrôle, du plus rapide au plus coûteux. Les deux premiers tournent à **chaque US**, sans rien consommer ; le
troisième à **chaque porte** (G0 à G5), avec votre accord ; le quatrième quand l'US touche l'écran ou la production.

## 1. Les règles qui valent pour tout l'épic

| Règle | Détail |
|---|---|
| **Environnement de test isolé** | `APP_ENV=pytest_isole` + `DATABASE_URL=sqlite:///…` explicite, jamais `APP_ENV=dev` ni `APP_ENV=test` : `.env.dev` et `.env.test` écrasent `DATABASE_URL` et portent une vraie clé Mistral (récidive du 17/11 : des tables et un utilisateur créés par erreur dans `potager_test`, nettoyés). Un script qui écrit commence par afficher `config.DATABASE_URL` |
| **Modèle simulé en test** | Tous les tests pytest mockent le modèle et la passerelle. **Aucun test à modèle simulé n'est présenté comme une mesure** (un rapport simulé porte « SIMULATION — CE N'EST PAS UNE MESURE ») |
| **Mesure réelle = accord** | Volume d'appels et coût annoncés par `--dry-run`, accord explicite (`--accord <volume>`), clé `MISTRAL_API_KEY_MESURE` distincte de celle du bot |
| **Suite complète une seule fois** | À la fin de chaque US, sortie filtrée sur `FAILED|ERROR|passed|failed`. La suite n'est pas verte à HEAD : je compare à HEAD (worktree à chemin court) pour départager |
| **Rien ne s'écrit dans le potager mesuré** | Lectures dans une transaction annulée, écritures simulées au schéma du registre ; seules les lignes `conso_tokens` sont créées |
| **Un test = un comportement**, nommé `test_us<NNN>_<composant>_<scénario>` avec le critère d'acceptance en docstring |

## 2. Les quatre niveaux

| Niveau | Quand | Contenu | Coût |
|---|---|---|---|
| **T1 — Tests ciblés de l'US** | À chaque US | Un test par critère d'acceptance (nominal, cas limites, erreurs : modèle indisponible, quota, base) ; couverture ≥ 80 % de l'US (`--cov` ciblé) | Nul |
| **T2 — Non-régression ciblée** | À chaque US | Les suites voisines : MCP (US-290 à US-297), propositions et confirmation (US-259 à US-262, US-272, US-289), agent actuel (US-233 à US-287), jeu d'évaluation (US-336, US-337), passerelle (US-092, US-306 à US-309) | Nul |
| **T3 — Mesure du jeu d'évaluation** | À chaque porte | Le jeu joué 3 fois par moteur, avec juge ; rapport avant / après ; critères à 100 % sur tous les passages | Jetons (accord) |
| **T4 — Recette réelle** | US touchant l'écran, Telegram, la base | PWA de dev isolée (API 8011, Vite 5173, SQLite jetable) contrôlée par chrome-devtools à 375 px ; migration jouée sur la base de test puis de dev ; Telegram par le harnais `tests_conv/` | Temps |

## 3. Étapes par US

| US | T1 — tests ciblés (exemples des plus importants) | T2 — non-régression | T3 — mesure | T4 — recette |
|---|---|---|---|---|
| **336** ✅ | 43 tests : exigences du jeu (CA1 à CA9), chargeur strict, contrôle « un cas renouvelable n'est dans aucun exemple de prompt », script du potager neuf rejouable | — | — | Potager neuf créé sur `potager_test` (à jouer) |
| **337** 🟡 | 106 tests : jardinier simulé (jamais hors fiche), critères à 100 % par le code, moteurs, juge, régression bloquante, accord sur le volume | `tools/evaluer_dialogues.py` (US-256) inchangé | **G0 : ligne de base de la chaîne actuelle** (CA8, accord) | Les 9 lectures réelles sur un potager neuf SQLite : fait |
| **338** | **Test de parité** : le serveur MCP et le registre neutre exposent les mêmes capacités, mêmes schémas, mêmes résultats ; le contrat externe du MCP est identique avant / après ; `RegistreMesure` (lanceur) refuse toujours de démarrer si une lecture devient une écriture | Toute la suite MCP (US-290 à US-297), quotas, portée, journal `mcp_appels` | — (rien de visible) | Appel MCP réel par un connecteur de dev : liste des outils et une lecture |
| **339** | Verdict de saison identique à celui de `GET /plan/confiances/candidates` (une seule source) ; cas B01 : « pas ce mois-ci, prochaine fenêtre février à mars, salade absente du potager » ; culture inconnue ; zone climatique ; `avertissement_donnees` | Fiche culture (US-207), calendrier cultural (US-068), confiance semis | **G1** (cas B05 et B01, jeu neuf) | Comparaison avec la fiche Salade de la PWA, côte à côte |
| **340** | Réponse tirée des échéances, des verdicts par culture et de « Aujourd'hui au potager » (US-328) ; potager vide ; potager rempli (33) en lecture seule | US-328, échéances de pépinière | **G1** (B06, B07, B21) | — |
| **341** | Jamais un passage d'une autre culture (cas tomate / salade) ; couverture absente dite (« pas de fiche salade ») ; sans culture : comportement général ; décision colonne ou non au cadrage | RAG (US-098, US-283), `chercher_connaissance` côté MCP | **G1** (B18, B20, B22) | Ingestion de contrôle sur base jetable |
| **342** | Boucle : un tour = un appel, outils, un texte ; 6 étapes au plus ; interrupteur `COMPAGNON_MOTEUR` (ancien moteur intact quand il est éteint) ; texte du modèle non réécrit par le code ; modèle indisponible → repli de la cascade des questions ; `tool_choice="auto"` | Orchestrateur (US-270), panneau PWA (US-271), tests conversationnels (US-288) | **G2** : tout le jeu, `capacites` contre `actuel`, 3 passages | **PWA de dev à 375 px** : le dialogue du 14/11 rejoué à la main, 7 tours, avec chrome-devtools |
| **343** | Fil complet (phrases, appels, arguments, résultats datés, réponses) ; fenêtre glissante de 12 tours (A3) ; compaction en faits établis (culture, parcelle, date, ce qui manque) ; résultat ancien relu avant d'écrire ; migration v81 **et son rollback** ; fil commun Telegram / PWA par jardinier et potager | Conversations (US-259, US-284), `echanges_conversation` | **G2** (coût : jetons d'entrée par tour, part en cache, sur des conversations longues) | Migration jouée sur `potager_test` puis dev ; reprise du fil le lendemain |
| **344** | `proposer_*` crée une proposition ; refus d'une parcelle inconnue, d'une date future, d'une quantité non dite ; carte dans les deux canaux ; confirmation par bouton ou par phrase ; une destruction ne se confirme qu'au bouton ; une récolte de haricot n'est jamais une perte | Gestes (US-269, US-272), commande confirmable dans la PWA (US-289), MCP écritures (US-292, US-293) | **G3** (B02 à B04, B09 à B14) | Carte et boutons dans la PWA de dev ; carte dans Telegram par le harnais |
| **345** | Correction (« non 3 rangs ») ne crée jamais un second geste ; annulation ; rappel ; retenir au carnet ; parité avec l'agent actuel sur les cas TER-27, TER-30 | US-262, US-265, US-268 | **G3** (B15 et cas terrain) | — |
| **346** | Telegram texte et voix passent par la même boucle ; messages spontanés reprennent le fil ; contexte d'écran (US-323) transmis | US-267, US-298 à US-305, US-323, harnais `tests_conv/` | **G4** (jeu rejoué sur Telegram) | Harnais Telethon sur un bot de test (compte, bot et base à fournir) |
| **347** | Plus aucune référence à l'ancien moteur (recherche des symboles retirés) ; imports vérifiés ; documentation à jour ; les commandes tapées, boutons et cascade des questions fonctionnent | **Suite complète comparée à HEAD** | **G5** (mesure finale = G4 ou mieux) | Parcours complet PWA + Telegram |
| **348** | Chaque fiche respecte le gabarit du corpus ; `controler_corpus_agronomie.py` vert ; ingestion idempotente ; les questions de mesure de la fiche trouvent leur passage ; aucune dose ni produit de traitement | `tools/mesurer_corpus_savoir.py` | Mesure du savoir (taux de passages justes) avant / après | **Relecture agronomique par vous** |
| **349** | Les champs « non renseigné » de la fiche culture sont renseignés, avec leur source ; import rejouable | Référentiel (US-193 à US-210), importeur | Verdicts de saison de US-339 sur les cultures complétées | Fiche culture de la PWA |
| **350** | `top_p=1` envoyé avec `temperature=0` pour Large 3 ; `content` en liste lu pour Large 4 ; un test par fournisseur ; Small 4 inchangé | Passerelle (US-092, US-299, US-306 à US-309) | Aucune | Un appel réel court par fournisseur, avec accord |

## 4. Les mesures aux portes

Chaque mesure suit le même protocole :

1. `python tools/evaluer_compagnon.py --dry-run --moteur actuel,capacites` : plan, volume, coût. **Vous donnez l'accord**, ou non.
2. Lancement avec `--accord <volume>`, clé de mesure, juge Large 3, **3 passages par moteur**, potager neuf et potager 33.
3. Lecture du rapport : critères à 100 % **sur tous les passages**, dispersion par passage, cas instables, cas en échec.
4. **Échantillon de 10 % à relire** (une quinzaine de cas par moteur) : je vous le propose avec les traces ; vous tranchez.
5. Comparaison avant / après (`--comparer`) : toute régression sur un critère à 100 % est **bloquante**, même si le critère était
   déjà en échec avant.
6. Rapport versé dans `docs/EPIC - AGENT INTERPRETEUR/` (la ligne de base seulement) ; traces dans `rapports_evaluation/`
   (hors dépôt).

| Mesure | Moteurs | Volume indicatif | Coût indicatif |
|---|---|---|---|
| G0 | `actuel` | ≈ 2 800 appels (134 cas × 3 passages × ≈ 3 tours × 2 étapes, plus 402 appels du juge) | ≈ 1,3 $ |
| G1 à G5 | `capacites` seul (témoin déjà mesuré), ou `actuel` + `capacites` si le jeu a changé | ≈ 3 400 à 6 200 appels | ≈ 1,6 à 3 $ |
| Configuration D (option) | `claude_mcp` | ≈ 3 400 appels | selon le tarif Anthropic (non intégré) |

Ces ordres de grandeur sont des **estimations du lanceur**, jamais des factures : le `--dry-run` donne le chiffre à valider.

## 5. Les besoins du jeu que les mesures couvrent

Le jeu (24 besoins) répartit les portes ainsi :

| Porte | Besoins mesurés |
|---|---|
| G0, G1 | B01 (salade, dialogue du 14/11), B05 (est-ce le moment), B06 (que semer), B07 (que faire), B18 (symptôme), B19 (fonction de l'application), B20 (culture sans fiche), B21, B22, B23, B24 (lectures) |
| G2 | Les 24 besoins, lecture et conseil |
| G3 | Écritures : B02, B03, B04 (semer, planter), B09, B10 (noter), B11, B12 (première et N-ième récolte), B13 (fin de vie), B14 (perte), B15 (correction) |
| G4 | Les 24 besoins, rejoués sur Telegram ; dialogues terrain TER-xx (corpus d'US-280) |
| G5 | Les 24 besoins, une dernière fois |

Critères suivis à chaque porte : utile au premier tour (≥ 80 %), aboutit en 3 tours (≥ 85 %), intention gardée, rien d'inventé,
écriture sûre (100 % sur tous les passages), hors-sujet montré (0), latence p95 (≤ 4 s), coût (≤ chaîne actuelle).
