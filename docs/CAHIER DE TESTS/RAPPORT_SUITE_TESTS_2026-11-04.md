# Rapport de la suite de tests — 04/11/2026

Contexte : livraison d'US-287 (agent d'abord), non commitée, sur la branche
`agent-mode-prioritaire`, au-dessus d'un arbre de travail qui porte déjà d'autres US
livrées et non commitées (US-259 à US-288).

Rapport HTML complet, test par test : `rapport_tests.html` à la racine du dépôt (ignoré
par git, 6 Mo, à ouvrir dans un navigateur).

## 1. Ce que cette suite teste, et ce qu'elle ne teste pas

La suite `tests/` est le **niveau 1** du projet : elle exécute notre code en simulant
le modèle de langage, Telegram et PostgreSQL (SQLite en mémoire). Elle prouve « si le
modèle répond X, notre code fait Y ». Elle ne dit **rien** de ce que Mistral répond
vraiment.

| Niveau | Outil | Ce qui est réel | Coût | Fait pour US-287 ? |
|---|---|---|---|---|
| 1. Tests pytest | `tests/` | notre code | nul | oui (ce rapport) |
| 2. Mesure sur le vrai modèle | `tools/evaluer_dialogues.py`, `tools/evaluer_agent.py` | notre code + Mistral | jetons | **non** (CA1, attend accord) |
| 3. Bout en bout Telegram | `tests_conv/` (US-288) | tout | jetons | **non** (harnais jamais joué) |
| 4. Recette manuelle | le bot de dev | tout | jetons | **non** |

Pour US-287, le niveau 1 prouve l'aiguillage (la phrase libre atteint l'agent avant les
mots-clés, les boutons et dialogues en cours passent avant, le repli sur 429 simulé,
`/deplacer`). Il ne prouve pas que Mistral Small 4 choisit le bon outil.

## 2. Comment la suite a été lancée

```powershell
$env:APP_ENV = "test"
.\.venv\Scripts\python.exe -m pytest tests/ -q --tb=line -W ignore `
    --html=rapport_tests.html --self-contained-html --junitxml=<fichier>.xml
```

⚠️ **Jamais `APP_ENV=dev` pour pytest.** `app/config.py` charge `.env.{APP_ENV}` en
écrasant les valeurs de `tests/conftest.py`. Avec `dev`, la base devient `potager_dev`
(PostgreSQL local) et la passerelle part sur la vraie API Mistral : les tests de la
passerelle (US-092, US-233) ne simulent que le client Groq.

Incident du jour : un premier lancement en `APP_ENV=dev` a donné 111 échecs en 14 min
et a écrit **49 lignes `conso_tokens` et 2 lignes `routage_logs`** dans `potager_dev`
(potager 1, utilisateur 1, entre 10:10 et 10:44), pour environ 89 000 jetons d'entrée
facturés sur la clé Mistral. Ces lignes fausseraient le relevé de coût du CA5 d'US-287 :
elles sont à supprimer. Correction proposée : forcer `APP_ENV=test` dans `tests/conftest.py`.

## 3. Résultat

| Tests | Réussis | Échecs | Erreurs | Ignorés | Durée |
|---|---|---|---|---|---|
| 7 231 | 7 162 | 51 | 15 | 4 | 3 min 43 |

**Aucun échec n'est causé par US-287.** Le seul qui la touche (US-276) était déjà rouge
avant elle. Les tests d'US-287 et ceux qu'elle pouvait casser (US-171, US-172, US-235,
US-236, INC-018, agent prioritaire) passent, hors l'anomalie `/reset_test` ci-dessous.

## 4. Les échecs, par cause (66 cas, 15 causes)

| # | Cause | Tests | Origine probable | US-287 ? |
|---|---|---|---|---|
| A | `/reset_test` (US-288, enregistrée seulement en `APP_ENV=test`) n'est ni dictable ni exclue et motivée : le contrôle de parité des commandes échoue | 6 : US-087, US-172 CA7, US-197 CA9, US-208 CA8, US-225 CA10, US-268 | US-288 — l'ajouter à `MOTIFS_EXCLUSION_INTERPRETEUR` | non (`/deplacer` passe la parité) |
| B | Fiches `blette-*.md` du corpus agronomique sans culture `blette` dans le `culture_config` du test : l'ingestion refuse le document | 15 : US-140 (14 erreurs + 1 échec) | corpus agronomique / référentiel | non |
| C | `Evenement.parcelle` est devenu une propriété sans setter : les tests qui la posent échouent | 11 : `test_bug_variete_recherche_affichage` | `database/models.py` (modifié, non commité) | non |
| D | Tables absentes (`no such table: evenements`, `culture_config`), réponses 500 | 12 : `test_api` (5), `test_us_mise_en_godet` (5), US-016/017/018, US-024 | tests qui utilisent le `SessionLocal` global sur SQLite en mémoire sans créer les tables | non |
| E | `app/bot/noyau.py:165` attend (`await`) un objet que les tests simulent sans `AsyncMock` | 6 : `test_bot` (3, `cmd_stats`), `test_us_stats_detail_variete` (3) | `noyau.py` devenu asynchrone à cet endroit | non |
| F | Parcours de déplacement US-007 : objet détaché de sa session, nouvelle parcelle non créée | 4 : US-007 | `_depl_confirm` / services d'événements | non (US-287 n'a touché que l'entrée du parcours) |
| G | Garde d'architecture : `nb_rangs` lu par `compagnon/corrections.py`, `longueur_m` lu par `echeances_lots.py` | 2 : US-197 CA7, US-225 CA8 | US-262, US-266 | non |
| H | `tools/mesurer_modeles_llm.py` appelle le SDK Groq en direct, hors passerelle ; relevé de consommation avant/après absent | 2 : US-092 CA1, CA7 | outil de mesure | non |
| I | Catalogue de l'agent trop long : 14 354 caractères pour une limite de 13 723 | 1 : US-276 CA5 | US-28x (14 269 sans US-287 ; `/deplacer` ajoute 85) | contribue de 85 caractères |
| J | `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md` déplacé dans `docs/CAHIER DE TESTS/` | 1 : US-094 CA6 | rangement de la documentation | non |
| K | Six questions de fonctionnement classées 4ᵉ ou 5ᵉ au lieu des trois premiers | 1 : US-099 CA11 | fiches du compagnon (US-265 et suivantes) ; identique sans US-287 | non |
| L | Manifeste Wind River : `plantation` absente, culture non pré-remplie | 2 : US-068 CA26, US-177 CA2 | référentiel `data/referentiel/` | non |
| M | `potager_membres` porte les colonnes du compagnon (`prenom_compagnon`, `silence_fin`…) que le test d'US-040 ne connaît pas | 1 : US-040 CA3 | US-258, US-267 | non |
| N | Le smoke test `health` est absent de `deploy.yml` | 1 : US-005 | workflow de déploiement | non |
| O | Une route inconnue renvoie 200 au lieu de 404 | 1 : US-023 | service du frontend par l'API | non |

## 5. Où sont les corpus et les questions

| Quoi | Où | Sert à |
|---|---|---|
| Corpus « fonctionnement de l'application » | `data/connaissance/doc_app/*.md` (table « ce qui rend une fiche fausse » dans son `README.md`) | réponses du compagnon sur l'appli |
| Corpus agronomique | `data/connaissance/agronomie/*.md` | réponses de jardinage |
| Guide utilisateur | `data/connaissance/guide user/guide assistant.md` (copie de `docs/MANUEL/guide assistant.md`) | aide en ligne, réponses |
| Corpus ingéré | PostgreSQL : `knowledge_documents`, `knowledge_chunks`, cache `questions_cache` ; par `python tools/ingerer_connaissance.py --strict --elaguer --purger-hors-liste` | recherche du compagnon |
| Questions de mesure du corpus | `tests/corpus/us099_questions_fonctionnement.csv` (doc_app), `us140_questions_diagnostic.csv` (agronomie), `us098_questions_savoir.csv`, `us141_questions_memoire.csv` | tests US-099, US-140… (niveau 1, sans modèle) |
| Phrases → commandes | `tests/corpus/us172_commandes.csv` (règles), `us235_agent_commandes.csv`, `us233_agent_echantillon.csv` | interpréteur et agent |
| Dialogues pour la mesure sur le vrai modèle | `tests/corpus/us256_dialogues.json`, `tests/corpus/terrain_compagnon_2026_11.json` | `tools/evaluer_dialogues.py` (niveau 2) |
| Rapports de mesure sur le vrai modèle | `docs/EPIC - COMPAGNON CONVERSATIONNEL/RAPPORT_MESURE_*.md`, `ANALYSE_MESURE_AGENT_D_ABORD.md` | décisions (D14) |
| Scénarios bout en bout | `tests_conv/scenarios/` | `python -m tests_conv` (niveau 3) |

## 6. Relancer depuis un terminal (PowerShell, à la racine du dépôt)

```powershell
.\.venv\Scripts\Activate.ps1
$env:APP_ENV = "test"                      # JAMAIS "dev" pour pytest

# Niveau 1 — gratuit, sans réseau
pytest tests/ -q                                                    # suite complète (~4 min)
pytest tests/ -q --html=rapport_tests.html --self-contained-html   # avec ce rapport HTML
pytest tests/test_us287_basculer_agent_d_abord.py -q              # une US
pytest tests/ -q -k "deplacer"                                      # par mot du nom de test

# Niveau 2 — vrai modèle, FACTURÉ : toujours le --dry-run d'abord
$env:APP_ENV = "dev"
python tools/evaluer_dialogues.py --mode prioritaire --dry-run     # volume et clé, aucun appel
python tools/evaluer_dialogues.py --mode prioritaire --corpus tests/corpus/terrain_compagnon_2026_11.json

# Niveau 3 — vrai Telegram (exige .env.test, bot et compte de test : voir docs/domaines/tests-conversationnels.md)
python -m tests_conv validate                                       # lit les scénarios, n'envoie rien
python -m tests_conv run                                            # annonce le volume ; --go pour envoyer
```

## 7. Annexe — détail test par test

Extrait de l'export JUnit du lancement du 04/11/2026 (message tronqué à 220 caractères).


| Fichier | Nombre |
|---|---|
| `test_us140_corpus_agronomique` | 15 |
| `test_bug_variete_recherche_affichage` | 11 |
| `test_api` | 5 |
| `test_us_mise_en_godet` | 5 |
| `test_us007_reassocier_culture` | 4 |
| `test_bot` | 3 |
| `test_us_stats_detail_variete` | 3 |
| `test_us092_passerelle_llm` | 2 |
| `test_us197_nb_rangs_parcelle` | 2 |
| `test_us225_longueur_parcelle` | 2 |
| `test_us005_deploiement` | 1 |
| `test_us016_017_018_godet_stock` | 1 |
| `test_us023_frontend_api` | 1 |
| `test_us024_plan_frontend` | 1 |
| `test_us040_modele_multitenant` | 1 |
| `test_us068_calendrier_cultural` | 1 |
| `test_us087_bot_rejoindre` | 1 |
| `test_us094_parseur_deterministe` | 1 |
| `test_us099_corpus_fonctionnement` | 1 |
| `test_us172_interpreteur_commandes` | 1 |
| `test_us177_duree_plantation_recolte` | 1 |
| `test_us208_pepiniere_chaude_froide` | 1 |
| `test_us268_rappels` | 1 |
| `test_us276_catalogue_projete` | 1 |

#### `test_api`

| Type | Test | Message |
|---|---|---|
| échec | `test_get_cultures` | sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: culture_config [SQL: SELECT culture_config.id AS culture_config_id, culture_config.nom AS culture_config_nom, culture_config.type_organe_recolte  |
| échec | `test_parse_inherits_type_organe_recolte` | assert 500 == 200 + where 500 = <Response [500 Internal Server Error]>.status_code |
| échec | `test_parse_unknown_culture_no_type` | assert 500 == 200 + where 500 = <Response [500 Internal Server Error]>.status_code |
| échec | `test_health_endpoint` | sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: evenements [SQL: SELECT count(evenements.id) AS count_1 FROM evenements WHERE evenements.potager_id = ? AND (evenements.type_action IS NULL OR ev |
| erreur | `test_health_endpoint` | failed on teardown with "sqlalchemy.exc.ProgrammingError: (sqlite3.ProgrammingError) SQLite objects created in a thread can only be used in that same thread. The object was created in thread id 12660 and this is thread i |

#### `test_bot`

| Type | Test | Message |
|---|---|---|
| échec | `test_cmd_stats_with_perte` | TypeError: object MagicMock can't be used in 'await' expression |
| échec | `test_cmd_stats_with_perte_and_recolte` | TypeError: object MagicMock can't be used in 'await' expression |
| échec | `test_cmd_stats_no_perte` | TypeError: object MagicMock can't be used in 'await' expression |

#### `test_bug_variete_recherche_affichage`

| Type | Test | Message |
|---|---|---|
| échec | `test_variete_presente_dans_criteres` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_filtre_sql_variete_retourne_bonne_variete` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_sans_variete_tous_retournes` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_variete_affichee` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_variete_position_avant_quantite` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_format_complet` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_deux_varietes_distinctes_dans_liste` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_pas_de_parentheses_vides` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_affichage_sans_variete` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_culture_accentuee_retrouvee` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |
| échec | `test_culture_sans_accent_retrouve_non_accentuee_en_base` | AttributeError: property 'parcelle' of 'Evenement' object has no setter |

#### `test_us005_deploiement`

| Type | Test | Message |
|---|---|---|
| échec | `test_contient_smoke_test` | assert 'health' in 'name: Deploy Production\nenv:\n FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true\non:\n push:\n branches: [main]\n work... actor=${{ github.actor }} status=\\${STATUS}\\" \\\n >> /opt/potager-prod/.deploy_his |

#### `test_us007_reassocier_culture`

| Type | Test | Message |
|---|---|---|
| échec | `test_ca8_update_groupe_et_trace` | sqlalchemy.orm.exc.DetachedInstanceError: Instance <Parcelle at 0x12eea687690> is not bound to a Session; attribute refresh operation cannot proceed (Background on this error at: https://sqlalche.me/e/20/bhk3) |
| échec | `test_ca8_update_filtre_par_variete` | sqlalchemy.orm.exc.DetachedInstanceError: Instance <Evenement at 0x12ee8dd56d0> is not bound to a Session; attribute refresh operation cannot proceed (Background on this error at: https://sqlalche.me/e/20/bhk3) |
| échec | `test_ca8_recolte_non_modifiee` | sqlalchemy.orm.exc.DetachedInstanceError: Instance <Evenement at 0x12ee8dd7e30> is not bound to a Session; attribute refresh operation cannot proceed (Background on this error at: https://sqlalche.me/e/20/bhk3) |
| échec | `test_ca6_nouvelle_parcelle_creee` | assert None is not None |

#### `test_us016_017_018_godet_stock`

| Type | Test | Message |
|---|---|---|
| échec | `test_us018_ca1_godets_par_culture` | assert None == 50 |

#### `test_us023_frontend_api`

| Type | Test | Message |
|---|---|---|
| échec | `test_us023_edge_route_inconnue_404` | AssertionError: assert 200 == 404 + where 200 = <Response [200 OK]>.status_code + where <Response [200 OK]> = get('/inexistant') + where get = <starlette.testclient.TestClient object at 0x0000012EEA848270>.get |

#### `test_us024_plan_frontend`

| Type | Test | Message |
|---|---|---|
| échec | `test_us024_ca5_occupation_pct_calcule` | assert None is not None |

#### `test_us040_modele_multitenant`

| Type | Test | Message |
|---|---|---|
| échec | `test_us040_ca3_table_potager_membres_colonnes` | AssertionError: assert {'compagnon_a...mpagnon', ...} == {'potager_id'...e', 'user_id'} Extra items in the left set: 'prenom_compagnon' 'compagnon_accueilli' 'silence_fin' 'heure_resume' 'proactivite_compagnon'... ...Ful |

#### `test_us068_calendrier_cultural`

| Type | Test | Message |
|---|---|---|
| échec | `test_us068_ca26_le_manifeste_versionne_porte_la_plantation_de_la_source` | KeyError: 'plantation' |

#### `test_us087_bot_rejoindre`

| Type | Test | Message |
|---|---|---|
| échec | `test_la_parite_commandes_interpreteur_reste_sans_anomalie` | assert ['/reset_test...TERPRETEUR).'] == [] Left contains one more item: "/reset_test est enregistrée par le bot mais n'est ni dictable (app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une forme dictable (ALIAS |

#### `test_us092_passerelle_llm`

| Type | Test | Message |
|---|---|---|
| échec | `test_us092_ca1_aucun_appel_direct_hors_passerelle` | AssertionError: Appels directs au fournisseur hors passerelle : tools/mesurer_modeles_llm.py:64 — import direct du SDK groq tools/mesurer_modeles_llm.py:65 — import direct du SDK groq tools/mesurer_modeles_llm.py:334 — i |
| échec | `test_us092_ca7_ordre_de_grandeur_consigne` | AssertionError: le relevé de consommation avant/après doit être consigné assert False + where False = exists() + where exists = WindowsPath('C:/Users/eremy/OneDrive - SQLI/Documents/GitHub/assistant-potager/docs/AUDIT_PA |

#### `test_us094_parseur_deterministe`

| Type | Test | Message |
|---|---|---|
| échec | `test_ca6_aucun_faux_positif_sur_le_corpus_de_questions` | FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\eremy\\OneDrive - SQLI\\Documents\\GitHub\\assistant-potager\\docs\\CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md' |

#### `test_us099_corpus_fonctionnement`

| Type | Test | Message |
|---|---|---|
| échec | `test_us099_ca11_la_bonne_fiche_sort_dans_les_trois_premiers` | AssertionError: « comment supprimer un potager dont je ne veux plus ? » → rang 5 « ou voir ce que tu sais deja sur une culture ? » → rang 4 « pourquoi seulement deux étoiles pour mes tomates ? » → rang 4 « combien de tem |

#### `test_us140_corpus_agronomique`

| Type | Test | Message |
|---|---|---|
| erreur | `test_us140_ca5_chaque_culture_est_reellement_interrogeable` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca4_l_attribution_accompagne_la_reponse_servie` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca4_l_attribution_suit_aussi_une_reponse_reecrite` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca6_les_alias_ne_sont_jamais_affiches` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca6_le_mot_populaire_retrouve_le_terme_technique` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca8_le_niveau_de_confiance_est_renseigne_par_fiche` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca8_un_contenu_indicatif_n_est_jamais_servi_mot_pour_mot` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca8_une_reponse_indicative_porte_une_reserve_explicite` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca11_tous_les_fragments_attendus_existent` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca11_la_bonne_fiche_sort_dans_les_trois_premiers` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca12_une_question_hors_perimetre_ne_force_aucune_reponse` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_ca13d_la_mention_de_source_est_visible_cote_utilisateur` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| échec | `test_us140_ca14_la_redaction_ne_touche_jamais_le_chemin_de_reponse` | tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé) |
| erreur | `test_us140_le_corpus_s_ingere_sans_erreur_ni_defaut_de_decoupage` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |
| erreur | `test_us140_reingerer_un_corpus_inchange_n_ecrit_rien` | failed on setup with "tools.ingerer_connaissance.DocumentInvalide: culture 'blette' absente de culture_config — la rattacher au référentiel avant d'ingérer ce document (CA2 : une référence, jamais un libellé)" |

#### `test_us172_interpreteur_commandes`

| Type | Test | Message |
|---|---|---|
| échec | `test_us172_ca7_parite_commandes_interpreteur` | AssertionError: /reset_test est enregistrée par le bot mais n'est ni dictable (app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une forme dictable (ALIAS_COMMANDES), ni explicitement exclue et motivée (MOTIFS_EX |

#### `test_us177_duree_plantation_recolte`

| Type | Test | Message |
|---|---|---|
| échec | `test_us177_ca2_le_manifeste_versionne_porte_la_duree` | AssertionError: la culture du Gherkin est pré-remplie assert 'tomate' in {} |

#### `test_us197_nb_rangs_parcelle`

| Type | Test | Message |
|---|---|---|
| échec | `test_us197_ca7_aucun_moteur_de_calcul_ne_lit_nb_rangs` | AssertionError: nb_rangs lu hors des points prévus : ['app\\services\\compagnon\\corrections.py'] assert not ['app\\services\\compagnon\\corrections.py'] |
| échec | `test_us197_ca9_parite_des_commandes_verte` | assert ['/reset_test...TERPRETEUR).'] == [] Left contains one more item: "/reset_test est enregistrée par le bot mais n'est ni dictable (app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une forme dictable (ALIAS |

#### `test_us208_pepiniere_chaude_froide`

| Type | Test | Message |
|---|---|---|
| échec | `test_us208_ca8_parite_verte` | assert ['/reset_test...TERPRETEUR).'] == [] Left contains one more item: "/reset_test est enregistrée par le bot mais n'est ni dictable (app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une forme dictable (ALIAS |

#### `test_us225_longueur_parcelle`

| Type | Test | Message |
|---|---|---|
| échec | `test_us225_ca8_aucun_moteur_de_calcul_ne_lit_la_longueur` | AssertionError: longueur_m lue hors des points prévus : ['app\\services\\echeances_lots.py'] assert not ['app\\services\\echeances_lots.py'] |
| échec | `test_us225_ca10_parite_des_commandes_verte` | assert ['/reset_test...TERPRETEUR).'] == [] Left contains one more item: "/reset_test est enregistrée par le bot mais n'est ni dictable (app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une forme dictable (ALIAS |

#### `test_us268_rappels`

| Type | Test | Message |
|---|---|---|
| échec | `test_la_parite_des_commandes_reste_verte` | assert ['/reset_test...TERPRETEUR).'] == [] Left contains one more item: "/reset_test est enregistrée par le bot mais n'est ni dictable (app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une forme dictable (ALIAS |

#### `test_us276_catalogue_projete`

| Type | Test | Message |
|---|---|---|
| échec | `test_us276_ca5_le_catalogue_complet_est_plus_court_qu_avant` | AssertionError: assert 14354 < 13723 + where 14354 = _taille('complete') |

#### `test_us_mise_en_godet`

| Type | Test | Message |
|---|---|---|
| échec | `test_ca6_post_parse_sauvegarde_champs_godet` | assert 500 == 200 + where 500 = <Response [500 Internal Server Error]>.status_code |
| échec | `test_ca7_godets_en_attente_retournes` | sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: evenements [SQL: SELECT evenements.culture AS evenements_culture, evenements.variete AS evenements_variete, sum(evenements.nb_graines_semees) AS  |
| échec | `test_ca7_godets_vide_si_aucun` | sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: evenements [SQL: SELECT evenements.culture AS evenements_culture, evenements.variete AS evenements_variete, sum(evenements.nb_graines_semees) AS  |
| échec | `test_ca8_godet_exclu_si_plantation_posterieure` | sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: evenements [SQL: SELECT evenements.culture AS evenements_culture, evenements.variete AS evenements_variete, sum(evenements.nb_graines_semees) AS  |
| échec | `test_ca9_taux_reussite_calcule` | assert None == 80 |

#### `test_us_stats_detail_variete`

| Type | Test | Message |
|---|---|---|
| échec | `test_ca6_culture_inconnue` | TypeError: object MagicMock can't be used in 'await' expression |
| échec | `test_ca3_culture_connue` | TypeError: object MagicMock can't be used in 'await' expression |
| échec | `test_ca2_hint_dans_synthese` | TypeError: object MagicMock can't be used in 'await' expression |
