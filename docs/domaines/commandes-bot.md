# Commandes du bot Telegram — package `app/bot/`, US-171, US-172

## Le package `app/bot/` (découpage de septembre 2026)

L'ancien `bot.py` monolithique (7 000 lignes) est découpé en modules par
domaine. Lancement : `python -m app.bot`. La carte des modules et leur ordre
d'import sont dans `app/bot/CLAUDE.md`, chargé automatiquement quand on y
travaille.

`app/bot/__init__.py` est une **façade** : elle expose tous les noms de tous
les sous-modules et propage toute affectation d'attribut vers chaque
sous-module qui lie ce nom. C'est ce qui permet aux tests de continuer à écrire
`monkeypatch.setattr(bot_module, "SessionLocal", ...)` ou `patch("app.bot.X")`.
Un test qui lit le source du bot itère sur `bot_module._SOUS_MODULES`.

Pour ajouter une commande : le handler va dans le module `commandes_*.py` de
son domaine (ou un nouveau), l'enregistrement dans
`application._construire_application`, et le catalogue de `menu_commandes.py`
doit trancher (dictable ou exclue) — sinon `controler_parite()` fait échouer
l'intégration continue.

## Menu de commandes natif Telegram [US-171]

Le menu (bouton « Menu » du client Telegram) n'est pas une liste tenue à la main :
il se dérive des `CommandHandler` enregistrés dans `application._construire_application()`.
Une commande ajoutée y entre au redémarrage suivant. Trois décisions, un seul
fichier — `app/services/menu_commandes.py` :

- `COMMANDES_EXCLUES` — ce qui n'entre pas au menu (`/version`, `/delier`, `/tts`)
- `ORDRE_METIER` — l'ordre de lecture des lignes
- `DESCRIPTIONS` — la phrase d'aide (≤ 60 caractères, lisible à 375 px)

Le clavier de raccourcis permanent n'existe plus : `noyau.SANS_CLAVIER`
(`ReplyKeyboardRemove`) le retire activement chez les jardiniers qui l'avaient.
Les claviers contextuels de validation, eux, sont inchangés.

## Un garde de liaison sans exigence de potager — `/rejoindre` [US-087]

Toute commande passe par `_enregistrer_commande`, donc par le garde de liaison :
un chat non relié est renvoyé vers le parcours de liaison. Ce garde exige aussi un
potager résolu (US-046, CA5) — ce qui aurait répondu « vous n'êtes membre d'aucun
potager » à celui qui utilise `/rejoindre` pour en obtenir un. `/rejoindre` figure
donc dans `_COMMANDES_SANS_EXIGENCE_DE_POTAGER` (`app/bot/application.py`) : liaison
exigée, potager non. Ce n'est pas une exemption du garde — `_garde_liaison` reste
posé sur le handler, et `_COMMANDES_SANS_GARDE_LIAISON` (onboarding et identité) ne
change pas.

Le handler (`app/bot/liaison.py`) ne porte aucune règle de validation : il traduit
en message chacune des erreurs d'`accepter_invitation`, appelée par
`potagers.rejoindre_potager`. Le potager actif n'est jamais basculé
silencieusement : y compris quand il n'était que le défaut transitoire de
`resoudre_tenant_context` (plusieurs potagers, aucun choix persisté), que
`accepter_invitation` écraserait sinon.

## Les deux payloads de `/start` [US-091, US-196, US-224]

`/start` accepte un argument, et il en existe désormais **deux familles**. Le
préfixe seul les distingue, en un point unique —
`file_gestes.est_code_geste`, appelé par `cmd_start` :

| Payload | Préfixe | Ce que c'est | Qui le traite |
|---|---|---|---|
| `ABCDEF` | aucun, 6 caractères majuscules sans ambiguïté | code de liaison d'un compte web (US-045, deep-link US-091) | `liaison._demarrer_avec_code` |
| `g<22 caractères>` | `g` minuscule | geste déposé dans la file depuis la PWA (US-196, US-224) | `bot.file_gestes.traiter_code_geste` |

⚠️ **Le préfixe est réservé, et c'est la minuscule qui le réserve** :
`liaison_telegram._ALPHABET` est entièrement majuscule, et `lier_chat_id` met en
majuscules avant de chercher. Les deux familles ne peuvent donc pas se
confondre — ni aujourd'hui, ni après un changement de longueur de l'une ou de
l'autre. Un code de liaison inconnu garde son traitement et son message : le
test de préfixe ne détourne jamais un code qui ne lui appartient pas.

⚠️ **Un geste préparé ne s'enregistre pas ici.** `bot.file_gestes` remet l'item
pré-parsé dans `saisie._parse_and_save` — le chemin du bouton « Enregistrer »
d'US-179, à la lettre. Aucun second chemin d'écriture, zéro jeton, et le potager
du geste l'emporte sur le potager actif (bascule faite ET dite, US-088).

⚠️ **Le code n'est plus à usage unique** [US-224 / CA11]. Il désigne un geste de
la file et reste valable tant que ce geste l'est — trois jours. Rouvrir le même
lien redonne le même geste ; c'est ce qui manquait à US-196, où « Annuler »
brûlait le geste et où rouvrir répondait « déjà utilisé ».

## La file de gestes et sa commande — `/gestes` [US-224]

La PWA **dépose**, le compagnon **confirme**, et entre les deux le geste attend.
Trois modules, trois responsabilités qui ne se mélangent pas :

| Module | Ce qu'il porte |
|---|---|
| `app/services/file_gestes.py` | la file elle-même : déposer, lister, sortir (confirmer / abandonner / refuser), vérifier le contexte, périmer |
| `app/services/relances_file.py` | la CADENCE : invitation unique, deux créneaux par jour, arrêt à 3 jours, coupure, avertissement et notification de purge |
| `app/bot/file_gestes.py` | les deux niveaux de présentation, la commande `/gestes`, les callbacks `file:`, et le job horaire |

**La règle de consommation est le cœur de l'US** : un geste ne sort de la file
qu'à la **confirmation** ou à l'**abandon explicite**. « Plus tard », un délai de
confirmation dépassé (les 60 s d'US-021), une conversation refermée ou une
relance ignorée le laissent en attente. C'est l'inverse d'US-196, dont le
`consomme_le` était posé à l'OUVERTURE du lien — trois façons d'y perdre un
geste préparé, aucune de le rejouer.

La présentation a **deux niveaux**, et le premier ne peut rien écrire : ses deux
seules actions sont `file:commencer` et `file:couper`, ce qui le rend sûr à
poser dans une notification. Le second est le récapitulatif d'US-021, inchangé,
avec trois issues au lieu de deux (`action_confirm`, `action_plus_tard`,
`action_abandonner`) — « Annuler » disparaît de ce flux parce qu'il ne
distinguait pas « j'annule la confirmation » de « j'annule le geste ».

**La cadence** : une invitation au premier dépôt sur une file vide (et une
seule), puis une relance par demi-journée sur deux créneaux fixes (9 h, 18 h —
jamais à l'heure du dépôt), un arrêt au bout de 3 jours, un avertissement 4 h
avant la purge d'un geste, une notification à la purge. Sept messages au pire
sur trois jours. Toute activité sur la file remet le compteur à zéro sans jamais
rallonger la vie d'un geste. La coupure (`file:couper`) est la soupape : elle
arrête tout **sans vider la file**, et elle est rappelée sur chaque relance.

⚠️ **L'envoi sortant a dû apprendre le clavier** (`telegram_notify.envoyer`,
`editer_message`). Il ne savait poster que du texte brut : suffisant pour
annoncer un archivage, insuffisant pour inviter à traiter une file — sans
clavier, toute invitation dégénère en « envoyez /gestes pour les traiter ».

Un seul job, **horaire** (`app/bot/file_gestes.job_file_gestes`) : l'avertissement
des 4 heures tombe à une heure qui dépend du dépôt de chaque geste, pas d'un
créneau fixe, donc il lui faut une maille plus fine qu'une demi-journée. Les
relances, elles, ne partent qu'aux créneaux — c'est `relances_file.doit_relancer`
qui en juge, jamais la planification.

`/gestes` est **dictable** (US-172) : c'est une consultation, pas un code à
coller, et le niveau 1 qu'elle ouvre n'écrit rien. La règle de reconnaissance
s'appelle `file_gestes` et exige un mot d'attente (`en attente`, `a confirmer`,
`file`) — c'est ce qui la sépare d'`historique`, qui possède déjà « mes derniers
gestes » et dit exactement le contraire : ce qui est FAIT, pas ce qui attend.

`/start` reste exclu de l'interprétation par phrase, ci-dessous : c'est un point
d'entrée à payload, pas une commande qu'on dicte.

## Piloter le bot par une phrase [US-172]

Les 26 commandes du bot ont toutes leur décision : 19 sont DICTABLES pour de
bon, 1 est un alias de sa cible canonique (`/parcelles` = `/parcelle lister`), et
6 sont écartées sur décision motivée (`/ask`, `/start`, `/lier`, `/rejoindre`,
`/delier`, `/version`). `/rejoindre` [US-087] suit le raisonnement de `/lier` : un
code d'invitation est une chaîne à coller, la transcription vocale d'un code est
fausse par construction.
Deux fichiers, et deux seulement :

- `app/services/menu_commandes.py` — le catalogue ENRICHI, à côté de celui du menu d'US-171 dont il se dérive :
  - `FORMES_DICTABLES` — forme des arguments, unités, vocabulaires fermés, `destructrice`, `confirmation`
  - `ALIAS_COMMANDES` — ce qui n'est pas une commande de plus
  - `MOTIFS_EXCLUSION_INTERPRETEUR` — ce qu'une phrase ne peut pas porter, DISTINCTE de `COMMANDES_EXCLUES` (menu), parce que les critères diffèrent (CA8)
  - `controler_parite()` — le test qui échoue tant qu'une commande ajoutée n'est pas tranchée (CA7)
- `app/services/interpreteur_commandes.py` — la RECONNAISSANCE, et rien d'autre

⚠️ Ajouter une commande au bot fait ÉCHOUER l'intégration continue tant qu'elle
n'est ni dictable ni exclue et motivée. C'est voulu : c'est ce test, et non la
vigilance, qui empêche l'écart de se recreuser. Une exclusion motive une
décision DÉFINITIVE, elle n'héberge jamais un « pas encore fait ».

Ce que l'interpréteur ne fait PAS : il ne réimplémente aucun comportement de
commande. Il produit un nom et des arguments, `app/bot/interpretation.py`
retrouve le handler réellement enregistré par introspection de `ctx.application`
et l'appelle avec `ctx.args`. Même service, mêmes contrôles, mêmes messages,
même garde de liaison — et donc mêmes droits (CA9, CA14).

Quatre gardes portent tout le reste, et se lisent dans la docstring du module :

| Garde | Rôle |
|---|---|
| `_est_demande_de_savoir` | « comment supprimer une parcelle ? » explique, « supprime la parcelle nord » agit (CA2) |
| ouverture interrogative | une règle DÉCLARATIVE (« X attaque souvent Y ») est refusée sur une question — sans quoi « qu'est-ce qui attaque mes poireaux ? », servie par gabarit depuis US-173, écrirait au référentiel |
| noms de parcelle | `resolve_parcelle` rapproche à deux lettres près : bon pour rattacher un geste, mauvais pour supprimer. Le voisin est PROPOSÉ, jamais substitué |
| arguments manquants | demandés, boutons à l'appui pour un vocabulaire fermé — jamais devinés d'un synonyme (CA13) |

Confirmation : exigée pour tout ce qui ÉCRIT (`FormeCommande.confirmation`),
pas pour une consultation — « voulez-vous vraiment afficher le plan ? »
doublerait chaque lecture. La commande équivalente est rappelée dans les DEUX
cas : c'est ainsi que le jardinier apprend la syntaxe sans l'apprendre.

### Un bouton ne parle que de sa proposition [US-234]

`_INTERP_PENDING[user_id]` ne garde qu'une proposition par jardinier. Avant
US-234, le bouton envoyait `interp:ok` sans dire laquelle : « Confirmer » sous un
**ancien** message validait donc la demande la plus récente, et le potager
n'était pas retenu (après un `/potager`, la commande s'exécutait dans le nouveau).

| Élément | Règle |
|---|---|
| `callback_data` | `interp:ok:<id>`, `interp:non:<id>`, `interp:cand:<rang>:<id>`, `interp:val:<rang>:<id>` ; `<id>` = 6 caractères hexadécimaux (`_nouvel_id_proposition`), toujours différent de celui de la proposition remplacée |
| Entrée de `_INTERP_PENDING` | porte `id` et `potager_id` (celui du `TenantContext` au moment de la proposition) |
| Bouton dont l'id n'est pas celui de la proposition en cours, ou sans id (message d'avant US-234) | rien n'est exécuté, « Demande expirée, rien n'a été fait » ; la proposition en cours **n'est pas touchée** (y compris pour « Annuler ») |
| Potager actif au clic ≠ `potager_id` de la proposition | rien n'est exécuté, la proposition est retirée et journalisée `abandonnee` ; « Annuler » reste possible |
| Nouvelle proposition pendant qu'une autre attend | l'ancienne est journalisée `abandonnee` avant d'être écrasée |

⚠️ Le potager « au moment du clic » ne se lit **pas** par `current_context()` : un
callback ne passe pas par le garde de liaison (`_arm_tenant_context`, groupe -1,
n'arme que le GUC RLS par défaut), il y lirait le contexte par défaut.
`_potager_actif_au_clic` le relit par le chat (`resoudre_user_id_pour_chat` puis
`resoudre_tenant_context`) et rend `None` s'il ne peut pas — ce qui vaut refus,
jamais exécution présumée. Tout nouveau callback qui écrit doit faire de même.

### L'agent interpréteur remplace le repli modèle [US-235]

`interpreter()` garde son ordre : garde de savoir → règles → filtre « geste
annoncé » → **repli**. Seul le repli change, selon `AGENT_MODE` (lu à chaque
phrase, `app/config.py`) :

| Mode | Repli |
|---|---|
| `off` (défaut du code) | l'ancien `_appeler_modele` (format texte, seuil 0,7), comme avant |
| `ombre` | l'ancien repli répond ; l'agent est consulté **à côté** (fil d'arrière-plan) et ce qu'il aurait proposé est journalisé (`issue_interpretation = 'ombre'`) |
| `actif` | l'agent, sans seuil de confiance (CA9) ; s'il est indisponible (429, panne, outils non gérés, appel malformé), l'ancien repli (CA13) ; **si lui non plus ne propose rien et que la phrase demande d'agir, un message explicite** (INC-018, voir plus bas), jamais le routeur |

Le paquet `app/services/agent/` : `catalogue_outils` (13 outils GÉNÉRÉS depuis
`FORMES_DICTABLES` et les caractéristiques de parcelle ; `controler_parite_outils()`
échoue si une forme n'a pas d'outil), `adaptateurs` (outil typé → `clé=valeur`),
`validation`, `interpreteur_agent` (l'appel, le mode ombre).

⚠️ **Révision de CA4 d'US-172** : l'ancrage mot pour mot devient un ancrage
selon la NATURE de la valeur (`validation.py`) :

| Nature | Règle |
|---|---|
| parcelle | dite ET existante à l'identique ; un rattachement du modèle (« la serre » → « Serre extérieure ») est PROPOSÉ, jamais substitué |
| nombre | dit en chiffres ou en lettres, sinon l'appel est rejeté |
| oui / non, liste fermée | **déductible** (« n'est plus une pépinière » → `pepiniere=non`), si le champ est évoqué (son nom, son libellé ou une valeur, sur 4 lettres) ; sinon retiré |
| texte libre, nom choisi | dit, sinon retiré puis demandé ; une copie d'un autre argument (`Planche Nord → Planche Nord`) est retirée |

**Gel des règles (A3)** : plus de nouvelle règle de commande pour couvrir une
tournure. Une tournure ratée devient une ligne de `tests/corpus/us235_agent_commandes.csv`,
mesurée par `tools/evaluer_interpreteur_agent.py` (0 destructrice erronée et 0
régression exigées). Exception : une commande destructrice fréquente.

Le récapitulatif d'une modification proposée par l'agent dit le sens de chaque
champ (« Je *retire* le statut pépinière de *Serre extérieure* »), celui des
règles garde ses puces. Plusieurs `clé=valeur` deviennent plusieurs arguments du
handler (`CommandeInterpretee.args`).

⚠️ Le filtre « geste annoncé » passe AVANT l'agent : « retire le paillage de la
planche sud » s'ouvre sur un mot de geste et n'atteint jamais l'agent. US-236
a gardé cet ordre (CA9 : les filtres sans modèle passent avant l'agent).

### L'agent dit où va la phrase — `Aiguillage` [US-236]

En `actif`, un outil terminal n'est plus jeté : `interpreter()` rend un
`Aiguillage(vers, nature_question, message)` et le bot le suit **sans** repasser
par `routeur.classer_demande` (les mots-clés du routeur ne servent plus qu'aux
phrases que l'agent n'a pas prises : `off`, `ombre`, et en `actif` indisponible ou
rejet du validateur pour une phrase qui ne demande PAS d'agir — CA8, INC-018).

| `vers` | Qui le traite | Effet |
|---|---|---|
| `question` | `messages.py` (texte et voix) | `_ask_question(…, nature=…)` → `repondre_avec_cascade(decision=…)`, origine `agent` ; nature illisible → la cascade classe elle-même |
| `geste` | `messages.py` | droit à `_parse_and_save`, sans routeur ni `parse_message` |
| `precision` | `interpretation._suivre_aiguillage` | « ❓ <question du modèle> — Rien n'a été fait » ; aucune proposition en attente |
| `hors_perimetre` | `interpretation._suivre_aiguillage` | « 🤷 Je ne sais pas encore faire ça (<raison>) » |
| `non_compris` [INC-018] | `interpretation._suivre_aiguillage` | « 🙏 Je n'ai pas réussi à traiter cette demande… Rien n'a été fait » + la commande à taper (`message`) ; produit par `interpreter()`, jamais par un outil |

Précision et hors périmètre écrivent une ligne `routage_logs`
(`issue_interpretation` = `precision` / `hors_perimetre`, `outils_agent` = l'outil) :
`SELECT question_normalisee FROM routage_logs WHERE issue_interpretation = 'hors_perimetre'`
est la liste des demandes de fonctionnalité. Le texte du modèle est échappé
(`_md`) avant d'entrer dans le message Markdown.

⚠️ Une désignation relative n'est pas un nom (`_DESIGNATION_RELATIVE` dans
`_nom_plausible`) : « supprime la parcelle près des tomates » n'est plus
reconnue par la règle `parcelle_supprimer`, elle passe à l'agent qui demande
laquelle. Une parcelle réellement nommée « Près du puits » se supprime donc par
la commande tapée, ou par l'agent.

### Une demande d'agir qui échoue est dite, pas routée [INC-018]

En `actif`, si l'agent est indisponible ou rejeté (appel `tool_use_failed`,
validateur) ET que l'ancien repli ne propose rien (ou sous le seuil 0,7),
`interpreter()` rend `Aiguillage(vers='non_compris')` quand la phrase **demande
d'agir** (`demande_d_agir` : verbe d'action en tête, impératif ou « peux-tu / je
veux » ; une phrase en « ? » sans cette formule est une question). Sans cela, le
routeur par mots-clés prenait « Créez la planche Nord… » pour une question de
données et répondait la liste des lots en pépinière (confiance 1,00).

- Les règles de commande et le parseur de gestes restent des raccourcis, avant l'agent.
- Une déclaration (« la planche nord a 6 rangs ») garde le chemin d'avant (routeur).
- `/ask` garde la cascade : ce chemin ne passe pas par `interpreter()`.
- `off` et `ombre` ne changent pas. Un `non_compris` n'entre pas dans le contexte court.
- **Tour de complément** : un tour sans `lire` clôt la boucle, et gpt-oss-120b n'émet souvent
  qu'un appel d'écriture par réponse (« crée la planche nord de 20m2 et de longueur 2 m »
  ne créait que la planche). `validation.chiffres_non_repris` compare les nombres dits aux
  arguments appelés (l'unité de « m2 » est ignorée) ; un nombre perdu accorde UN tour de
  plus, où seules les écritures sont retenues (un doute tardif n'annule rien). Sans modèle
  ni écriture ; un faux positif coûte un appel. Ne couvre pas une seconde demande sans
  nombre (« …et mets la serre en pépinière ») : reste US-250.
- Le schéma des outils accepte `null` pour un champ facultatif (« non dit », retiré
  par le validateur) : un type strict faisait rejeter l'appel par le serveur ; la
  génération rejetée est journalisée (`llm.passerelle`, WARNING).

### Plusieurs commandes en une phrase — `Plan` [US-237]

`interpreteur_agent.proposer` est une boucle d'au plus `AGENT_MAX_TOURS` appels
(`historique` de `passerelle.appeler_chat_outils`). L'outil `lire` (parcelle,
parcelles, lot, culture — `agent/lecture.py`, potager du contexte, résultat en
JSON sous `donnees`) est exécuté et renvoyé au modèle ; une écriture reçoit
« noté » et n'est **jamais** exécutée dans la boucle ; un tour sans lecture ou
un outil terminal la clôt.

| Appels retenus | Résultat |
|---|---|
| terminal en tête, ou `demander_precision` après des écritures | `Aiguillage` (US-236) |
| une écriture | `CommandeInterpretee`, proposition simple (CA9) |
| plusieurs écritures | `validation.valider_plan` → `Plan`, ou `Aiguillage(precision)` |

`valider_plan` passe chaque appel par `valider_appel` avec la liste des parcelles
**enrichie des créations précédentes** (règle 7) ; une création sur un nom pris
va dans `Plan.deja_faites` (signalée, sautée). Une étape sans exécuteur
(suppression, renommage, tout sauf `/parcelle ajouter|modifier`) refuse le plan :
« je ne sais faire celle-ci que seule ». Un plan refusé ne retourne jamais à
l'ancien chemin, qui n'en verrait qu'une commande.

Le bot (`interpretation._plan_proposer`) affiche `recapitulatif_plan` et une
seule paire `interp:ok:<id>` / `interp:non:<id>` (US-234). À la confirmation,
`_plan_executer` relit le `TenantContext` au clic (`_contexte_au_clic`) et
appelle `agent/executeurs.executer_plan` : **pas les handlers**, qui rendent
`None`. Chaque étape est revalidée en base (nom exact, jamais rapproché), la
première `echouee` arrête la suite, `compte_rendu` rend ✅ ❌ ⏭ en texte brut.
`executeurs.SERVICES` pointe les mêmes fonctions que les handlers
(`create_parcelle` de `messages.py`, `update_parcelle` de `commandes_parcelle.py`) :
le test de parité échoue si l'un des deux change de service. Journal : une ligne
par plan, `commande_interpretee = "plan parcelle ajouter,modifier,…"` (64 car.).

### Corriger ou prolonger la dernière demande — `ContexteCourt` [US-238]

« Non, l'autre », « et la planche sud aussi » ne se comprennent qu'à la lumière de
la proposition en attente. `app/services/agent/contexte_court.py` la résume :
`ContexteCourt(commandes, texte_origine, candidats, ecartes, echanges)`, rendu en
JSON dans la partie **variable** du message système (`prompt_variable(…,
contexte_court=)`), avec les consignes de correction. Sans proposition en attente le
message système reste celui qui a été mesuré (US-233, US-235) : les consignes ne sont
PAS dans `PROMPT_FIXE`.

| Borne | Où elle tient |
|---|---|
| CA1 : proposition + 3 échanges, tronqués | `NB_ECHANGES_MAX`, `LONGUEUR_MAX` (tronqué par le début : la dernière phrase est à la fin) |
| CA5 : hors délai, demande nouvelle | `construire` rend None après `_INTERP_TIMEOUT` (300 s) ; les échanges plus vieux sont oubliés |
| CA6 : un jardinier, un potager | la proposition vient de `_INTERP_PENDING[user_id]` ; `construire` refuse un autre `potager_id` ; les échanges sont rangés par `(user_id, potager_id)` |

Le bot construit le contexte (`interpretation.contexte_court_de(update)`, texte **et**
voix) et le passe à `interpreter(…, contexte_court=)`, que seul l'agent en mode
`actif` lit. Chaque phrase interprétée (`_traiter_commande_interpretee`) est notée
comme un échange par `contexte_court.noter_resultat`.

⚠️ **L'ancrage reste celui du validateur.** `proposer` ancre sur « phrase d'origine
de la proposition ; nouvelle phrase » : « et la planche sud aussi » reprend le « 6 »
dit plus tôt, mais un nombre dit nulle part reste refusé. La phrase d'origine du
résultat est cette phrase combinée, donc `Plan.texte_origine` et le journal portent la
demande complète — et une prolongation de prolongation garde ses valeurs.

⚠️ **« L'autre » est une déduction : elle est proposée, jamais substituée.** Le nom
n'a pas été dit, `_resoudre_entites` le range en candidat et le jardinier le valide
d'un bouton. `pending["ecartes"]` (voir `_ecartes_apres`) garde les voisins déjà
refusés d'une proposition à l'autre ; `_conclure` n'en repropose aucun et demande
« Laquelle ? ». La nouvelle proposition remplace l'ancienne par le chemin d'US-234
(`_abandonner_precedente` : journal `abandonnee`, nouvel identifiant de boutons).

Mesure et journal :

```bash
psql -d potager -f migrations/migration_v44.sql   # routage_logs : commande + issue
psql -d potager -f migrations/migration_v59.sql   # routage_logs.outils_agent [US-235]
pytest tests/test_us172_interpreteur_commandes.py tests/test_us235_agent_interpreteur.py tests/test_us236_aiguillage_agent.py tests/test_us237_plan_agent.py tests/test_us238_contexte_court.py
python tools/evaluer_interpreteur_agent.py --dry-run   # puis sans --dry-run : vrai modèle
```

`tests/corpus/us172_commandes.csv` : 162 formulations de commande, 36 questions
de savoir voisines, 27 phrases hors périmètre — recomptées le 22/09/2026 (les
chiffres d'avant le 17/09/2026 étaient restés ceux d'une version antérieure du
corpus).

⚠️ Une règle DÉCLARATIVE se juge sur ce qu'elle refuse autant que sur ce qu'elle
reconnaît, et le nombre de rangs d'une planche [US-197] en est le cas d'école :
« la planche nord **a** 5 rangs » déclare la planche, « planté 4 salades **sur**
3 rangs dans la planche nord » compte un geste de 12 plants. Le mot « rang » est
le même, le verbe ne l'est pas — `parcelle_rangs` exige un verbe d'état ou de
possession collé au nombre. Le corpus porte les deux formes CÔTE À CÔTE : c'est
lui, et non la relecture du motif, qui empêche la confusion de revenir. Au 17/09/2026 : 100 % de
reconnaissance, 0 exécution destructrice erronée, 100 % sans appel modèle.
Ce chiffre mesure ce qu'on a su prévoir ; c'est `issue_interpretation` en
production qui dira quelles formulations enrichir ensuite (CA18).

## Deux lectures justes de la même phrase — `_ARBITRAGES` [US-179]

« Je peux semer des tomates sur la planche nord ? » est à la fois une question de
ROTATION (quels antécédents — US-163) et de SAISON (est-ce le moment — US-179).
Jusqu'ici, deux commandes reconnues dans une phrase rendaient une `Ambiguite` et
le bot demandait laquelle : c'est le bon réflexe quand l'une des deux ÉCRIT.
Quand les deux ne font que LIRE, c'est un geste de plus sur la question la plus
fréquente de l'application.

`interpreteur_commandes._ARBITRAGES` déclare donc, paire par paire, celle qui
répond — et la table est ÉCRITE, jamais déduite de l'ordre de déclaration des
règles, qu'un bloc déplacé dans le fichier renverserait. Arbitrage du
17/09/2026 : `{confiance, rotation} → confiance`. La rotation garde `/rotation`
et sa formulation explicite (« vérifie la rotation des tomates sur la planche
nord »), que `rotation_explicite` reconnaît seule. Une paire dont l'une des deux
commandes écrit n'entre PAS dans cette table.

## Reconnaître une question d'opportunité sans capter une saisie [US-179]

Quatre règles (`confiance_modal`, `confiance_moment`, `confiance_jugement`,
`confiance_ou_attendre`) traduisent « je peux semer des haricots ce week-end ? »
en `/confiance`. Aucune ne reconnaît un verbe de semis NU : il faut une modalité.
Sans cette exigence, elles capteraient la saisie — le geste le plus fréquent du
bot — et écriraient un événement que le jardinier n'a pas fait.

Le garde 1 (`_est_demande_de_savoir`) s'efface devant elles, et devant elles
seules : « peut-on semer des haricots ? » s'ouvre comme une demande de procédure
sans en être une. `_est_question_d_opportunite` est assemblé des mêmes briques
que les règles, pour que le garde et elles ne puissent pas diverger.

Détail et décisions : `docs/domaines/calendrier-cultural.md`, § « Je peux semer ? ».

## `/lot <numéro>` — consulter un lot de pépinière [US-209]

Commande de pure consultation (zéro jeton, `confirmation=False`), **dictable** :
« où en est le lot 128 ? », « montre-moi le lot 128 », « lot 128 » — règle
`lot_pepiniere` de l'interpréteur (`n°` y arrive sous la forme `ndeg`, c'est
`unidecode`). Le numéro est cherché dans le potager courant seulement
(`stock.lot_pepiniere_par_numero`) ; la fiche est rendue par
`app/services/lots_pepiniere.formater_lot_telegram`. Le handler (`cmd_lot`,
dans `app/bot/godets.py`) n'a aucune logique métier.

**Liste des lots** : `/lot` sans numéro (ou `/lot tomate`, « mes lots », « lots de tomate » — règle `liste_lots`) rend `lots_pepiniere.formater_liste_lots_telegram` : lots numérotés seulement, les 15 plus récents (`LIMITE_LISTE_LOTS`), épuisés marqués ⚪, filtre par culture. Même forme `lot` au catalogue (numéro et culture facultatifs) ; `cmd_lot` distingue un numéro d'une culture.

La **référence** à un lot dans une phrase de geste (« repiqué 40 plants du lot
128 en godet », « #128 ») est lue par le parseur déterministe
(`extraire_reference_lot`, avant la normalisation qui effacerait le `#`) puis
résolue au récapitulatif (`resoudre_references`, appelé par `saisie.py`) : lot
connu et cohérent → rattachement (`origine_graines_id` pour godet / perte / vente,
`source_evenement_ids` pour une plantation) ; inconnu ou contradictoire →
`_alerte_lot` au récapitulatif, aucun rattachement. « lot » n'est une référence
que pour `ACTIONS_AVEC_LOT` : US-211 (déplacement) et US-212 (levée) y ajoutent
leur geste.

**Pépinière d'une mise en godet** (US-210). Un godet se pose dans une pépinière
DITE (« mise en godet de 40 choux sous le châssis froid » : `châssis` est un
marqueur de parcelle du parseur déterministe et fait partie du nom). Le contrôle
est `lots_pepiniere.controler_emplacements_godets`, appelé par `saisie.py` après
`resoudre_references` : pépinière → nom canonique retenu ; parcelle ordinaire →
parcelle retirée et `_alerte_emplacement` (pépinières proposées, « sans
emplacement ») ; non dite → rien n'est déduit. Le refus d'écriture est la règle 7
de `valider_evenement` (`ParcelleNonPepiniereError`), donc aussi pour la
correction du Journal. `creer_evenement_godet` écrit `parcelle_id`. L'emplacement
courant d'un lot (`calcul_lots_pepiniere#emplacement`) : dernier déplacement
(US-211, à venir), sinon dernière mise en godet localisée, sinon parcelle du
semis, sinon non renseigné — il n'entre dans aucun total (`calcul_godets`, stocks
et `/stats` agrègent toujours par culture et variété).
