# Pilotage LLM — mesure fiable et coût de chaque appel au modèle

ÉPIC 18 (cadrage : `docs/EPIC 18 - PILOTAGE LLM/CADRAGE_PILOTAGE_LLM.md`). Cette fiche couvre
le **lot 1 (mesure fiable)** et le **lot 2 (coût)** : US-306 à US-309. Les vues d'administration
(lot 3) et les alertes (lot 4) viendront s'y ajouter.

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

## Pièges

- Les tests ne doivent jamais viser le vrai fournisseur : fixer `llm.passerelle.modele_pour`, ou
  `_resoudre_client`, sinon un `GROQ_MODEL_*` de `.env.test` en `mistral/…` ouvre un appel réseau.
  Lancer pytest avec `APP_ENV=pytest_isole` et une base SQLite explicite.
- `tests/conftest.py` réinitialise le contexte d'appel avant chaque test : appeler `main()` d'un outil
  en cours de test n'a plus de fuite sur les suivants.
- `tests/test_us044_authentification_jwt.py` recharge `app.config` : lire `config.<nom>`, jamais un nom
  importé une fois, dans un test qui dépend des classes ou fonctions du module.
