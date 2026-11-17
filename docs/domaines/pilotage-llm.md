# Pilotage LLM — mesure fiable et coût de chaque appel au modèle

ÉPIC 18 (cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md`). Cette fiche couvre
le **lot 1 (mesure fiable)** et le **lot 2 (coût)** : US-306 à US-309, puis les **agrégats** servis à
l'administrateur (US-310) et la PWA d'administration qui les affiche (US-311, US-312, puis les vues Coût, Fiabilité et Dérives : US-313, US-314, US-315). Le **lot 4** (alertes et bilans : US-316, US-317) est décrit à la section « Alertes, résumé quotidien et bilan
hebdomadaire » ci-dessous.

Tout part de `llm/passerelle.py::_enregistrer_conso`, qui écrit **une ligne de `conso_tokens` par
appel** au modèle, succès comme échec. Ce qu'elle écrit au-delà de l'appel lui-même n'est jamais un
paramètre de fonction métier : c'est un **contexte** (`ContextVar`) posé à l'entrée de l'interaction.

## Le contexte d'appel — `llm/contexte_appel.py`

Sans dépendance à la base ni à la passerelle (importable de partout). Il suit la tâche asyncio ou la
requête, comme `TenantContext` : deux traitements concurrents ne se voient pas.

| Valeur | Posée par | Écrite dans |
|---|---|---|
| **provenance** [US-306] `usage` \| `mesure` \| `test` \| `fond` \| `historique` | `fixer_provenance()` / `provenance()` ; sinon déduite (voir ci-dessous) | `conso_tokens.provenance` |
| **canal** [US-307] `telegram` \| `pwa` \| `mcp` \| `fond` \| `outil` \| `inconnu` | `canal_courant` (le bot, le middleware de l'API, le serveur MCP, `demarrer_outil()`) | `conso_tokens.canal` |
| **échange** [US-307] identifiant de 32 caractères hexadécimaux | `ouvrir_echange()` à l'entrée de chaque interaction ; `reprendre_echange(ref)` | `conso_tokens.echange_ref`, `echanges_conversation.echange_ref` |

**Provenance déduite** quand aucun point d'entrée n'en a posé : mode test (`mode_test.actif()`) →
`test` ; appel sans utilisateur, ou type `compagnon_signal` → `fond` ; sinon `usage`. `historique`
est réservé à la migration v73 (les lignes d'avant la colonne) : aucun code ne peut l'écrire, et
l'existant n'est **jamais reclassé par heuristique**.

**Un échange = une réponse.** Un message Telegram, une requête de l'API, un appel d'outil MCP, une
exécution d'outil de `tools/` ouvrent chacun le leur. Une tâche de fond sans interaction écrit un
identifiant propre à chaque appel. La PWA enchaîne **dictée → message → résumé parlé → voix** sur
plusieurs requêtes : `POST /compagnon/voix/transcrire` rend `echange_ref`, la PWA le renvoie dans
`POST /compagnon/messages`, `conversations.noter` le retient sur l'échange persisté, et la lecture
(`oral.texte_oral`, `lecture.lire_echange`) le reprend. Retrouver les lignes de consommation d'un
échange : `conso_tokens.echange_ref = echanges_conversation.echange_ref` (sans clé étrangère).

**Unité** [US-307] : `passerelle.UNITES_PAR_TYPE` est le **seul** endroit qui dit ce que
`tokens_in` / `tokens_out` comptent (`jeton`, `seconde` pour la dictée, `caractere` pour la voix).
Un type d'appel ajouté à `TYPES_APPEL` sans unité fait échouer `test_us307_ca6_tout_type_d_appel_declare_son_unite`.

**Version** [US-307] : `app.config.VERSION_APP`, le fichier `VERSION` lu une fois au démarrage.

## Les outils de `tools/` qui appellent un modèle

Leur `main()` commence par `contexte_appel.demarrer_outil()` : provenance `mesure`, canal `outil`, et
un échange pour toute l'exécution. `tools/audit_appels_llm.py` (`outils_sans_provenance()`) et le test
`test_us306_ca7_aucun_outil_n_appelle_un_modele_sans_provenance` échouent si un outil qui importe la
passerelle, le routeur ou `groq_client` (ou figure dans `OUTILS_INDIRECTS`) n'a pas fixé sa provenance.
Un outil ajouté qui appelle un modèle par un service doit être déclaré dans `OUTILS_INDIRECTS`.

**Modèle simulé** [US-306 / CA6] : un appel dont la réponse est un objet `unittest.mock` (ou un bloc
`contexte_appel.modele_simule()`) n'écrit **aucune ligne** hors d'une base de session de test (SQLite,
ou nom de base contenant « test »). Les « lignes à 0 jeton et 0 ms » de l'extraction du 10/11 venaient de là.

## Le coût — `data/tarifs/tarifs_llm.json` et `app/services/pilotage/tarifs.py`

Chaque ligne porte `fournisseur`, `cout_micro_eur` (entier) et `tarif_version`, calculés **à
l'écriture**, **figés** : changer la grille ne modifie aucune ligne déjà écrite.

- **Lue une fois au démarrage**, jamais en ligne à l'appel ; une grille mal formée lève
  `GrilleTarifaireInvalideError` et le bot comme l'API ne démarrent pas.
- **Aucun prix de mémoire** : chaque entrée porte `source` (page) et `date_releve`. Le taux de change
  (USD → EUR, BCE) est fixe et daté dans la grille ; aucun appel à un service de change.
- **Tarif public**, même au palier gratuit (le texte `palier_gratuit` de la grille le dit).
- **Arithmétique exacte** (`Fraction`, aucun flottant), un seul arrondi (demi vers le haut) sur le
  total. Les jetons en cache sont comptés à leur tarif et **retirés** des jetons d'entrée au plein
  tarif ; sans tarif de cache publié (Groq), ils sont comptés au prix d'entrée (borne haute).
- **Échec sans jeton = 0. Modèle absent de la grille (ou unité différente) = `NULL`**, avec
  `tarif_version` renseignée : jamais un coût inventé. La transcription Telegram (Whisper) ne
  journalise pas encore sa durée : ses lignes restent sans coût.
- **Ajouter un modèle** : relever son prix sur la page du fournisseur, l'ajouter à la grille avec sa
  source et sa date, et, si la grille change de prix, **changer `version`**. Le test
  `test_us309_ca9_chaque_modele_par_defaut_est_dans_la_grille` échoue si un modèle par défaut de
  `app/config.py` n'y figure pas.
- **Rejouer l'existant** : `python tools/chiffrer_historique.py` (simulation) puis `--appliquer`,
  éventuellement `--grille autre.json`. Ne touche jamais une ligne déjà chiffrée.

## Noms de modèle — `app/config.py` [US-308]

`GROQ_MODEL`, `GROQ_WHISPER_MODEL` et chaque `GROQ_MODEL_<TYPE>` sont validés au chargement :
`config.controler_modeles()`. Une valeur invalide (espace, parenthèse, `#`, caractère hors
`A-Za-z0-9._:@+-/`, plus de 100 caractères, préfixe `<x>/` inconnu) lève `ConfigurationInvalideError`
qui nomme la variable et montre la valeur lue : le démarrage s'arrête. Préfixes connus :
`NOMS_FOURNISSEURS_RESERVES` (Groq, Mistral…) et les `FOURNISSEURS_COMPATIBLES` déclarés. Un commentaire
va sur une ligne à part du `.env`, jamais en fin de ligne de valeur.

## Les agrégats — `app/services/pilotage/agregats.py` et `/admin/pilotage/...` [US-310]

**Source unique** des chiffres de consommation : les quatre routes, les vues de la PWA d'administration
(US-312 à US-315), les seuils (US-316) et le bilan (US-317) lisent ici. Aucun écran n'additionne lui-même.

| Route (lecture seule, `require_admin_user` : 401 sans jeton, 403 sinon) | Rend |
|---|---|
| `GET /admin/pilotage/synthese` | appels, jetons d'entrée / de sortie / en cache, taux de cache, secondes d'audio, caractères, coût, issues, latence P50 et P95, jetons d'entrée médians par appel — pour la période **et** la période précédente de même durée |
| `GET /admin/pilotage/series?mesure=&dimension=&pas=` | une série par jour (par heure sur une journée), chaque pas présent à zéro ; dimension : `modele`, `appel_type`, `canal`, `provenance`, `issue`, `version` |
| `GET /admin/pilotage/ventilation?dimension=&mesure=&limite=` | le classement d'une dimension (dont `potager`, `utilisateur`), avec part, médiane et coût par ligne |
| `GET /admin/pilotage/echanges` | médiane, P95 et maximum du coût, des jetons et du nombre d'appels **par échange** |
| `GET /admin/pilotage/cout` [US-313] | coût de la période, du mois en cours, projection de fin de mois, jardiniers actifs, coût par jardinier actif (médiane, P95, maximum, et ramené à 30 jours), coût d'un échange par canal, lignes non chiffrées et leurs modèles, version de grille dominante |
| `GET /admin/pilotage/fiabilite` [US-314] | décomptes et taux par issue, latences (succès / échecs séparées), par modèle et par type d'appel, grille heure × jour des quotas, 20 derniers échecs — avec la période précédente |
| `GET /admin/pilotage/derives?type_courbe=` [US-315] | par version de l'application (10 dernières + « avant suivi ») : taille des appels par type, courbe journalière d'un type avec repères de version, appels par échange par canal |

Filtres communs : `depuis`, `jusqu_a` (dates incluses ; défaut 7 jours glissants), `provenance` (une ou
plusieurs, séparées par une virgule), `canal`, `modele`, `appel_type`, `potager_id`. Une valeur hors
vocabulaire → 422.

- **Provenance** : sans filtre, seules `usage` et `fond` sont comptées ; `mesure`, `test` et `historique`
  ne sont jamais mêlées à un chiffre d'usage par accident. `provenance=mesure` ne compte QUE les mesures.
- **Unité** : les jetons ne sont sommés que sur les lignes d'unité `jeton` ; secondes d'audio et
  caractères sont des mesures distinctes. Le taux de cache est `jetons_cache / jetons_entree` (les jetons
  en cache sont inclus dans les jetons d'entrée).
- **Coût** : `None` (jamais 0) quand aucune ligne de la période n'est chiffrée ; `lignes_non_chiffrees`
  dit combien manquent.
- **Période** lue sur `conso_tokens.date` (jour d'imputation, indexé) ; le pas horaire lit `cree_le`.
- **Percentiles en Python** (rang le plus proche, comme `metriques_routage._p95`) : identiques sous SQLite
  et PostgreSQL. Les sommes et décomptes sont faits par la base (`GROUP BY`) ; seule une colonne est
  ramenée pour les percentiles. Budget : 90 jours sur 100 000 lignes en moins d'une seconde (test).
- **Lecture de tous les potagers** : `conso_tokens` n'est pas sous RLS. La lecture hors périmètre passe
  par `lecture_toute_la_plateforme()`, qui **refuse** de s'exécuter (`LectureHorsPerimetreError`) si
  PostgreSQL signale la table sous RLS ; le module ne pose jamais de `tenant_scope` factice. Si un jour une
  politique RLS est ajoutée à `conso_tokens`, la lecture d'administration devra passer par un rôle dédié,
  pas par un contournement.
- **Index** (migration v78) : `(date, provenance)` et `cree_le` ; `echange_ref` l'était déjà (v74).
- **Les trois routes de vue** (`cout.py`, `fiabilite.py`, `derives.py`, dans `app/services/pilotage/`) lisent par
  `agregats._filtrer` / `_executer` / `_agreger` : mêmes filtres, mêmes provenances par défaut, même chemin de
  lecture hors RLS. Définitions testées et affichées par l'écran :
  - **Jardinier actif** : au moins une ligne `usage` sur la période, quelle que soit la provenance demandée.
  - **Projection** : coût du mois à ce jour + moyenne des 7 derniers jours × jours restants ; le mois et la
    projection ne dépendent pas de la période choisie (seul l'instant de référence, `cout._aujourd_hui`).
  - **Coût mensuel d'un jardinier** : son coût sur la période × 30 / nombre de jours.
  - **Taux de succès / quota / erreur** : appels de l'issue ÷ tous les appels (une issue inconnue compte au
    dénominateur). **Latence** : appels réussis seulement ; celle des échecs est rendue à part.
  - **Dérives** : appels réussis d'unité `jeton` ; un échange = tous ses appels, échecs compris ; en dessous de
    20 appels (ou échanges) → `echantillon_faible` ; écart mis en évidence au-delà de 20 % (`seuil_ecart`).
- **Ajouter une dimension ou une mesure** : l'ajouter à `DIMENSIONS_*` / `MESURES` et à `_Cumul.valeur` —
  les trois routes qui la lisent la prennent ensemble.

## La PWA d'administration « Pilotage » — `admin/` [US-311, US-312]

Application **séparée** de celle des jardiniers (Vite + React, `admin/`, règles dans `admin/CLAUDE.md`),
servie par l'API sous **`/pilotage/`** (montage statique de `admin/dist`, rien si non construit).
Manifeste et service worker limités à ce chemin ; le service worker ne garde que la coquille, jamais une
réponse `/admin/...` (hors ligne : « pas de données »).

- **Accès** : connexion et jetons du jardinier (mêmes clés `localStorage`). La décision se prend sur
  `GET /auth/me` → `administrateur` (`app.api.main.est_administrateur`, la même règle que
  `require_admin_user`) : un autre compte voit « Accès réservé » et n'envoie aucune requête `/admin/...`.
- **Maquette** : US-318 (projet Claude Design « Pilotage - PWA administration »). Seul jeton ajouté à l'identité :
  `--brand-soft-strong` ; les couleurs de séries sont des alias des teintes existantes.
- **Coquille** : navigation entre six vues (Consommation, Coût, Fiabilité, Dérives livrées ; Potagers,
  Seuils : voir plus bas ; Potagers s'ouvre sur un écran d'attente), période (aujourd'hui, 7, 30, 90 jours, personnalisée) et
  filtres provenance / canal / modèle gardés dans l'adresse. La vue du jour se rafraîchit toutes les
  60 s onglet visible ; en panne d'API, les dernières valeurs (en mémoire seulement) restent affichées
  avec leur âge.
- **Vue Consommation** (US-312) : cinq chiffres clés avec écart à la période précédente (le mot
  « défavorable » accompagne l'icône), graphique par jour (par heure sur « aujourd'hui ») avec la part du
  cache distinguée, « Ventiler par » cache / modèle / type / canal (cinq séries + « Autres »), tableaux par
  type d'appel et par modèle, bloc audio à part. Un rappel dit que seules `usage` et `fond` sont comptées.
  Les chiffres sont ceux de `GET /admin/pilotage/synthese` : le contrat est
  `admin/src/lib/fixtures/consommation_fixe.json`, vérifié des deux côtés (voir `admin/CLAUDE.md`).
- **Vues Coût, Fiabilité, Dérives** (US-313 à US-315) : sans maquette propre, elles réutilisent les composants de la
  vue Consommation (`ChiffreCle`, `Graphique`, cartes, segments) ; `TableauDonnees`, `GrilleChaleur`,
  `CarteGraphique` et `CadreVue` sont les seuls ajoutés, dans le même style. Le prix d'abonnement de la vue Coût
  reste sur l'appareil (`localStorage`, clé `pilotage_prix_abonnement`), jamais envoyé. Contrats :
  `admin/src/lib/fixtures/{cout,fiabilite,derives}_fixe.json`, vérifiés par
  `tests/test_us313_315_contrat_vues.py` (`REGENERER_FIXTURE_US313_315=1` pour les régénérer).
- **Déploiement** : étapes « Build admin PWA (Pilotage) » des workflows `deploy.yml` / `deploy-dev.yml`,
  après le build du frontend (sa config Tailwind étend celle de `frontend/`) ; runbook A9 bis.

## Alertes, résumé quotidien et bilan hebdomadaire — `seuils.py`, `bilans.py`, `notifications.py` [US-316, US-317]

Trois modules de `app/services/pilotage/`, sans appel de modèle (garde de test sur leurs imports), qui lisent
`conso_tokens` par `agregats` (provenances `usage` et `fond` seulement) et n'y écrivent jamais.

- **Seuils** (`seuils_pilotage`, v79) : indicateur + périmètre (`tous` ou un type d'appel) + fenêtre en jours (1 = aujourd'hui,
  la mesure lit `conso_tokens.date`, au jour près) + comparaison (`fixe`, ou `ecart_7j` = écart en % à la valeur des 7 jours
  précédant la fenêtre ; une somme est ramenée à la moyenne quotidienne × la fenêtre) + valeur + gravité + actif.
  `seuils.INDICATEURS` est le seul endroit qui dit ce qui est surveillable (coût du jour, coût du mois projeté, jetons d'entrée
  médians par appel d'un type, appels par échange, taux de quota, taux d'erreur, latence P95 d'un type, appels non chiffrés).
  La projection de fin de mois n'accepte que la valeur fixe (pas d'historique comparable).
- **Seuils par défaut** : posés par le code au premier passage (`assurer_seuils_par_defaut`, idempotent, jamais écrasés), tous
  **« à valider »** ; ceux qui dépendent du coût ne sont actifs que si la grille tarifaire (US-309) est chargée. Changer la
  **valeur** d'un seuil le valide ; l'activer seul ne le valide pas.
- **Évaluation** (`seuils.evaluer`) : toutes les `PILOTAGE_EVALUATION_MINUTES` (15) par `job_evaluation_seuils`
  (`app/bot/pilotage_jobs.py`), avec le mécanisme du veilleur du compagnon : le bot est le seul processus de tâches de fond,
  aucune unité systemd. Moins de **20 appels** dans la fenêtre : rien n'est déclenché **ni résolu** (on ne sait pas).
- **Cycle d'une alerte** (`alertes_pilotage`) : au plus UNE alerte ouverte par seuil (index partiel `uq_alertes_pilotage_ouverte`) ;
  rien n'est renvoyé tant qu'elle est ouverte ; le retour à la normale part **une fois** ; une gravité **haute** rappelle toutes
  les 24 h. Un canal en échec n'est pas inscrit dans `canaux_notifies` et est réessayé au passage suivant, sans renvoyer l'autre.
- **`PILOTAGE_ALERTES=non`** (défaut) : tout est évalué et journalisé, rien ne part ; allumé plus tard, les alertes déjà ouvertes
  sont notifiées. Aucun message ne contient de contenu ni de nom de jardinier : des mesures et un lien.
- **Destinataires** (`notifications.py`) : Telegram → le compte lié à `ADMIN_EMAIL`, sinon `ADMIN_TELEGRAM_ID` ; e-mail →
  `ADMIN_EMAIL` par Brevo (`email.envoyer_email`, qui rend si l'envoi a réussi). Liens : `PILOTAGE_URL` (défaut
  `FRONTEND_URL` + `/pilotage`) + `/#/<vue>`.
- **Résumé quotidien** (Telegram, `PILOTAGE_RESUME_QUOTIDIEN`, à partir de `PILOTAGE_RESUME_HEURE` = 8 h, pour la veille) et **bilan
  hebdomadaire** (e-mail, `PILOTAGE_BILAN_HEBDO`, le lundi, pour la semaine écoulée comparée à la précédente) : textes par gabarit,
  les `mesure` sur une ligne à part, trace `bilans_pilotage` (v80) UNIQUE par (type, début de période). Le planificateur passe
  toutes les 30 minutes : un redémarrage rattrape le résumé du jour, un envoi échoué est rejoué **une seule fois**, jamais deux envois.
- **API** : `GET /admin/pilotage/seuils` (seuils avec état courant `franchi|norme|nodata|inactif`, alertes ouvertes, 50 dernières alertes,
  canaux joignables, interrupteurs ; `?etats=false` ne mesure rien, pour la pastille de la navigation) et
  `PATCH /admin/pilotage/seuils/{id}` (activation, valeur, comparaison, fenêtre, gravité ; 422 hors vocabulaire ou définition en double).
  Seule route d'écriture de `/admin/pilotage/`.
- **Vue « Seuils »** de la PWA (`admin/src/views/Seuils.jsx`, `components/PanneauSeuil.jsx`, `lib/seuils.js`), d'après l'écran B de la
  maquette d'US-318 : alertes ouvertes en tête, liste des seuils (règle en une phrase, gravité, état avec icône, interrupteur), feuille
  montante / panneau latéral de modification (la règle se relit et dit si elle serait franchie maintenant), envois périodiques et
  historique. **Écarts à la maquette** : les interrupteurs des envois périodiques sont en lecture seule (ils relèvent de la
  configuration du serveur, US-317 / CA7) ; les fenêtres sont en jours (1, 3, 7), pas en heures.

## Potagers et jardiniers — `acteurs.py` [US-319]

Qui consomme quoi, par `agregats` (mêmes filtres, mêmes provenances `usage` + `fond`, même lecture hors périmètre) ; les tables
`potagers`, `potager_membres` et `users` ne donnent que nom de potager, e-mail, rôle, décomptes et date d'inscription (registre :
`docs/RGPD/RGPD_PILOTAGE_LLM.md`). Aucun contenu de message, aucun nom d'affichage.

- **Routes** (lecture seule, `require_admin_user`) : `GET /admin/pilotage/potagers`, `/utilisateurs` (listes + bandeau), `/potagers/{id}`,
  `/utilisateurs/{id}` (fiches). Tous les potagers non supprimés et tous les comptes y figurent, à zéro sans appel.
- **Actif** : au moins une ligne `usage` sur la période. **Usage élevé** : coût > 3 × la médiane des coûts des actifs de même nature
  (`FACTEUR_USAGE_ELEVE`, valeur de départ à valider). **Tâches automatiques** : appels sans utilisateur, une ligne à part côté jardiniers,
  rattachés à leur potager côté potagers. Premier décile : au moins un jardinier actif.
- `Filtres.user_id` (fiche d'un jardinier) n'est ni une route ni dans `vers_dict`.
- **Vue** (`admin/src/views/Potagers.jsx`, `lib/acteurs.js`) : sans maquette propre, composants de la vue Consommation ; `TableauDonnees`
  accepte `surOuvrir` et `usageEleve`. Liste → fiche en état local.

## Pièges

- Les tests ne doivent jamais viser le vrai fournisseur : fixer `llm.passerelle.modele_pour`, ou
  `_resoudre_client`, sinon un `GROQ_MODEL_*` de `.env.test` en `mistral/…` ouvre un appel réseau.
  Lancer pytest avec `APP_ENV=pytest_isole` et une base SQLite explicite.
- `tests/conftest.py` réinitialise le contexte d'appel avant chaque test : appeler `main()` d'un outil
  en cours de test n'a plus de fuite sur les suivants.
- `tests/test_us044_authentification_jwt.py` recharge `app.config` : lire `config.<nom>`, jamais un nom
  importé une fois, dans un test qui dépend des classes ou fonctions du module.
