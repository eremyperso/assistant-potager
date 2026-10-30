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

## Dire ce qui a été interprété, anticiper la suite [US-252, US-253]

Le récapitulatif distingue trois choses, et ne commente que les deux dernières : ce qui a été dit
tel quel (rien), ce qui a été **rapproché** (une ligne `↪️ dit → retenu`, dans
`CommandeInterpretee.corrections` : valeur corrigée d'US-251, ou nom de parcelle choisi parmi les
voisins — `avec_candidats` garde le mot dit dans `mot_candidat`, `avec` le verse aux corrections) et
ce qui a été **supposé** (une ligne `❔` par caractéristique que la règle écrit en valeur par défaut,
`_lignes_supposees`, lue au registre `vocabulaire_parcelle.non_precisees`). `recapitulatif` et
`recapitulatif_plan` partagent ces deux lecteurs : une commande de règle, une proposition de l'agent
et une étape de plan se présentent pareil.

`app/services/anticipation_commande.py` regarde l'état du potager, sans modèle, et ne lève jamais :

- `avertissements` : pour `parcelle supprimer` et `parcelle modifier actif=non`, les cultures en
  place (`plan.get_occupation`) et les lots de pépinière encore suivis, ajoutés sous le récapitulatif
  par `interpretation._anticiper`. Une information, jamais un blocage.
- `suite_suggeree` : appelée par `interpretation._suggerer_suite` APRÈS l'exécution d'une commande
  confirmée, sur l'état de la base. Une parcelle devenue pépinière sans type donne une commande de
  modification dont `precision.invite` est la question : les boutons existants (`interp:prec`) posent
  la valeur, le récapitulatif habituel attend la confirmation, « Plus tard » (`interp:sans` avec
  `invite`) abandonne la suggestion sans rien écrire. Au plus une suite par commande.

⚠️ La longueur et le nombre de rangs ne sont pas suggérés : ce ne sont pas des valeurs fermées, un
bouton ne peut pas les porter (reste d'US-253 / CA2).

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

Le paquet `app/services/agent/` : `catalogue_outils` (15 outils GÉNÉRÉS depuis
`FORMES_DICTABLES` et les caractéristiques de parcelle ; `controler_parite_outils()`
échoue si une forme n'a pas d'outil), `projection` (les outils que le modèle voit
selon la phrase, US-276), `adaptateurs` (outil typé → `clé=valeur`),
`validation`, `interpreteur_agent` (l'appel, le mode ombre).

### Le catalogue nommé par verbe et projeté selon la phrase [US-276]

Un outil porte le nom de son verbe, tiré du libellé de la forme (`creer_parcelle`,
`supprimer_parcelle`, `afficher`, `renseigner_calendrier`), et sa description
commence par lui. Une commande dont une forme a déjà son outil (la modification
typée, la suppression) n'est plus regroupée : `parcelle(action=…)` faisait inventer
`parcelle(action="supprimer")` au 3B. Renommer un outil change les attendus de
`tests/corpus/us233_agent_echantillon.csv` et `us256_dialogues.json`.

Trois projections, et pas une de plus (`PROJECTIONS`), dans l'ordre du catalogue,
destructeurs en queue pour que « sans destruction » en soit un préfixe :

| Phrase | Projection |
|---|---|
| interrogative : « ? », « est-ce que », « comment », « quand », « peux-tu », demande de procédure — sauf formule de demande + verbe d'action (`demande_d_agir`) | `sans_ecriture` : `afficher`, `lire`, outils de réponse (pas `saisir_geste`) |
| verbe de destruction (`VERBES_DE_DESTRUCTION`, la liste de la règle `parcelle_supprimer`) dans la phrase ou son contexte court | `complete` |
| toute autre | `sans_destruction` |

Un outil appelé hors de sa projection est écarté (journal « hors projection »).
`creer_parcelle` prend les caractéristiques de la fiche : `validation.deplier_creations`
en fait `ajouter` (avec superficie et exposition, que la forme porte) puis
`modifier_parcelle` (le reste), donc un plan. Deux règles du validateur s'ajoutent :
une suppression dont le nom n'est pas exact ET dit devient une précision qui nomme les
choix (aucun candidat proposé) ; les mots d'un nom de parcelle non dit en entier
n'évoquent aucun champ, et une modification qui ne garde rien devient une précision.

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
**Exception US-262** : une phrase de correction dans les 10 min qui suivent un geste,
ou une phrase en « annul… » tant qu'un geste des 24 h peut l'être, passe à l'agent
(voir « Corriger ou annuler une action menée » plus bas).

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
| `non_compris` [INC-018] | `interpretation._suivre_aiguillage` | « 🙏 Je n'ai pas réussi à traiter cette demande… Rien n'a été fait » + la commande à taper (`message`) ; produit par `interpreter()`, jamais par un outil |

[US-257] `precision` et `hors_perimetre` ne sont plus produits par l'agent (les
constantes restent pour le contexte court) : `texte_aiguillage` n'a plus de texte
figé pour eux. Depuis US-257, l'aiguillage `question` vient d'`interpreter()`
(phrase interrogative, sans appel au modèle) et `geste` de l'outil `saisir_geste`.

### L'agent répond en texte — `ReponseAgent` [US-257]

`interpreteur_agent.proposer` est une boucle **conversationnelle**
(`tool_choice="auto"`, au plus `AGENT_MAX_TOURS` = 6 appels, puis un appel
`tool_choice="none"` si le dernier tour n'a pas rédigé). `interpreter()` rend une
`ReponseAgent(texte, proposition, outils, manque_catalogue)` ; le bot
(`interpretation._repondre_agent`) envoie le texte seul (texte brut, c'est le
modèle qui l'a écrit) ou le place, échappé (`texte_de_l_agent`), au-dessus du
récapitulatif et des boutons habituels (`_interp_proposer` / `_plan_proposer`,
argument `preambule`, affiché une fois).

- **Outils retirés** : `poser_question`, `demander_precision`, `hors_perimetre`.
  Reste `saisir_geste` (terminal) et entre `manque_catalogue(demande)`, un signal
  sans effet, journalisé `hors_perimetre` (`persister_reponse`). Un refus du
  validateur sans proposition est journalisé `precision`. « merci » n'écrit rien.
- **Verdict au modèle** (`Propositions.juger`) : chaque écriture est validée avec
  celles déjà retenues (état simulé du plan) ; le message `tool` dit « proposée »
  (commande ou étapes) ou « refusée » avec la raison, et le modèle se corrige dans
  la boucle. Un appel sur la même cible (outil + parcelle) complète ou corrige le
  précédent au lieu de doubler (« non 4 rangs »).
- **Rien de perdu (CA4, US-250)** : le verdict signale, une fois, ce que la phrase
  dit et qu'aucun appel ne reprend — un nombre (`chiffres_non_repris`), une
  demande au-delà du nombre d'appels ou un verbe à un seul outil sans son appel
  (`validation.demandes_non_reprises` : crée, supprime, renomme), la proposition
  en attente qu'une suite « et … aussi » prolonge. Une phrase qui demande d'agir
  et ne reçoit qu'un texte est relancée une fois (`demandes_sans_appel`). Le
  signal porte sur la phrase dite, pas sur le contexte : « non 4 rangs » ne
  signale pas le 3 qu'il remplace.
- **Contrôle des annonces (CA5)** : `annonce_une_action` (« c'est fait », « j'ai
  noté »…) et `decrit_une_proposition` (« voici ce que je propose » sans appel)
  sont déterministes. Devant une proposition, une annonce est retirée (le
  récapitulatif parle seul) ; sans proposition, le modèle reçoit une fois
  `CORRECTION_ANNONCE` / `CORRECTION_PROPOSITION`, puis `TEXTE_RIEN_FAIT` remplace.
- **Questions** : en `actif`, une phrase `projection.est_interrogative` part à la
  cascade des questions (`Aiguillage(question)`, 0 appel) tant que l'agent n'a
  pas les lectures d'US-263.
- **Réponse vide** (`MOTIF_REPONSE_VIDE`) : ni texte ni proposition → `_non_compris`
  (message explicite si la phrase demande d'agir), jamais l'ancien repli.
- **Réversible** : `AGENT_MODE` inchangé (`off`, `ombre` qui journalise aussi le
  texte, `actif`). La mesure de livraison est `tools/evaluer_dialogues.py`
  (pseudo-attendus `texte` et `aucune_ecriture`, section « Naturel » à noter).

⚠️ Une désignation relative n'est pas un nom (`_DESIGNATION_RELATIVE` dans
`_nom_plausible`) : « supprime la parcelle près des tomates » n'est plus
reconnue par la règle `parcelle_supprimer`, elle passe à l'agent qui demande
laquelle. Une parcelle réellement nommée « Près du puits » se supprime donc par
la commande tapée, ou par l'agent.

### Le filet des caractéristiques de parcelle — `filet_fiche` [US-278]

Retours de terrain du 28/10/2026 (Ministral 3B) : « ma planche X a une superficie
de 20 m2, longueur de 7m et ensoleillement mi-ombre » donnait, selon X, la bonne
proposition, la liste des parcelles (`afficher` répété) ou une réponse sur les
pommes de terre (« tubercul » pris pour une culture). `app/services/agent/filet_fiche.py`
lit la phrase **sans modèle** et construit l'appel `modifier_parcelle` que le
modèle aurait dû faire ; `valider_appel` en fait la proposition, comme d'habitude.

- **Après l'agent, jamais devant** : US-277 inchangée, les règles ne lisent que
  les phrases simples. `interpreteur_agent._filet` (début de `_conclure`) le tend
  quand la boucle finit sans écriture proposée (texte, lecture, refus) ; une
  écriture de l'agent n'est jamais remplacée. `interpreteur_commandes._filet_fiche`
  le tend quand il n'y a pas d'agent (`off`, panne, quota) ni de repli qui propose,
  et sur une phrase écartée par les règles (US-277 / CA6) : il rend une
  `ReponseAgent` d'origine `regle`, `regle = REGLE_FILET_FICHE`.
- **Déclenchement** : une parcelle désignée (nom exact du potager, ou « planche /
  parcelle / carré / butte / bande » suivi d'un nom) ET au moins une valeur lue :
  superficie (m2, m², mètres carrés), longueur (m, mètres), rangs, ensoleillement
  (`DEFINITIONS_ENSOLEILLEMENT`), exposition (après « exposé(e) » / « exposition »
  seulement : « planche Est » est un nom). Nombres en chiffres ou en lettres.
  Jamais sur une question, une création, ni un geste (`annonce_un_geste`).
- **Nom** : exact → proposition directe ; approchant (`resolve_parcelle`) →
  candidat au bouton « 📍 », jamais substitué ; rien → « ❓ Quelle parcelle ? »
  avec les parcelles en boutons (≤ `NB_CHOIX_MAX`), sinon le nom est demandé
  (`manquants`). Les valeurs lues restent dans la proposition.
- **Texte** : `TEXTE_FILET` du code remplace celui du modèle ; un nombre que le
  filet n'a rattaché à aucun champ est dit (« je n'ai pas su placer : 3 »).
- **Relance (CA6)** : `filet_fiche.valeurs_non_reprises` ajoute au signal « non
  repris » d'US-257 une valeur de vocabulaire dite et oubliée (« mi-ombre »).
- Le récapitulatif d'une proposition du filet est celui d'une modification de
  l'agent (« Je passe la superficie de X à 20 m². »), quelle que soit son origine.

### Un mot que la règle n'a pas utilisé — `PrecisionDemandee` [US-250, US-251]

Relevé du 22/10/2026 : « Mon tunnel est une pépinière chaud » était confirmé puis
écrit en « pépinière, type non renseigné » — une règle reconnaît le début d'une
phrase et laisse le reste. Le contrôle est à UN endroit, `_appliquer_regle`, et vaut
donc pour toutes les règles à la fois :

- **Ce qui est contrôlé** : les mots que le motif n'a pas consommés (avant et après
  `trouve.span()`), moins la politesse et les liaisons sans portée
  (`_MOTS_SANS_PORTEE`, `_EXPRESSIONS_SANS_PORTEE` : stp, merci, maintenant, « s'il te
  plaît »…). Pour les commandes qui ÉCRIVENT (`forme.confirmation`), et pour les
  consultations dont la règle déclare `controle_mots=True` : seule la météo, où un mot
  perdu (« demain », un lieu sans préposition) change la réponse sans que rien ne le dise
  (recette du 30/10/2026 ; `_NOTES_DU_RESTE` dit ce que la règle sait faire à la place).
  Les autres consultations restent exemptées : mesuré sur le corpus, les étendre toutes
  poserait une question à 12 phrases naturelles (« qu'ai-je fait hier ? », « corrige ma
  dernière saisie »…) dont la réponse ne change pas. Une règle dont le motif doit
  laisser des mots *légitimes* (« … 15 à 20 jours après le semis », « … du jour ») les
  consomme dans son motif, sinon elle poserait une question à tort.
- **`CommandeInterpretee.precision`** (`PrecisionDemandee`) : le mot tel que dit, la
  caractéristique attendue, les valeurs offertes. Tant qu'elle est posée, `complete`
  est faux et `decisions.est_prete` aussi : « oui » tapé ne la tranche pas.
- **Bot** : `_interp_etape_suivante` pose la question après les noms voisins et avant
  les arguments manquants. Boutons `interp:prec:<rang>:<id>` (une valeur),
  `interp:sans:<id>` (« Sans précision »), `interp:non:<id>`. Le choix passe par
  `CommandeInterpretee.avec_choix` / `sans_precision`, puis la proposition habituelle.
- **Journal (CA6)** : la question a SA ligne `routage_logs` (`issue = precision`,
  jamais réécrite, `log_id=None` sur la proposition) ; le choix ouvre une ligne
  `proposee` neuve (`propositions.mettre_a_jour(log_id=…)`). Le mot non compris est
  dans la ligne de log `mot non compris=…` — pas de colonne : `issue_interpretation`
  est un `String(16)` et la story exclut toute migration.
- **Les phrases du relevé** sont au corpus `tests/corpus/us172_commandes.csv`, et
  `tests/test_us250_mot_non_utilise.py` rejoue CHAQUE règle qui écrit avec un mot
  parasite (`PHRASES_PAR_REGLE` : une règle ajoutée sans phrase d'exemple échoue).

**Rapprocher une valeur mal dite** (`app/services/vocabulaire_parcelle.py`, US-251) :
le registre des caractéristiques à valeurs admises (type de pépinière, abri, type de
sol, ensoleillement, exposition) est LU au domaine (`parcelles.vocabulaires_fiche()`,
`utils.parcelles.TYPES_PEPINIERE`) à chaque appel, et sert aux règles ET à l'agent
(`catalogue_outils.champs_fiche` en tire les `enum` de ses outils) : une seule liste.

- `rapprocher(dit, valeurs)` rend `exact`, `corrige`, `ambigu` ou `aucun`, sans
  modèle. Une variante de genre, de nombre, d'accent, de tiret ou de casse se
  rapproche (« chaud » → chaude, « argileuse » → Argileux) ; deux valeurs proches ou
  aucune ne sont JAMAIS tranchées : la question d'US-250 est posée, avec les deux
  valeurs pour l'ambiguïté et toutes les valeurs pour l'inconnu.
- Dans une règle : `@_regle(…, caracteristique="pepiniere")` déclare la caractéristique
  dont la valeur est FACULTATIVE en fin de phrase. Tant que la règle a écrit la valeur
  par défaut (`Caracteristique.non_precisees`, « oui »), le mot restant est rapproché
  (`_lire_restes`). La correction va dans `CommandeInterpretee.corrections` et le
  récapitulatif la montre (« ↪️ chaud → chaude »), règle ou agent.
- Dans l'agent : `validation._dans_liste(…, corrections)` rapproche une variante unique
  d'une valeur de la liste ; hors liste, ou proche de deux valeurs, le rejet reste.
- ⚠️ Un nouveau champ à liste de valeurs entre dans le registre
  (`vocabulaire_parcelle.caracteristiques`) ; le booléen `est_pepiniere` n'a pas de
  liste, seul le champ du TYPE porte « chaude / froide ».

### La météo d'un autre lieu que le potager — `/meteo <lieu>`

Recette du 30/10/2026 : « quel temps fait-il à Lyon ? » donnait la météo du potager sans un
mot sur Lyon, et « quelle météo à Lyon ? » (rien de reconnu, donc `est_interrogative` →
cascade des questions) recevait un fragment de documentation sur les rangs.

- **La commande** : `/meteo` gagne un argument FACULTATIF `lieu` (`menu_commandes.FORMES_DICTABLES`,
  `TYPE_TEXTE`). Sans lieu : la météo du potager actif, enregistrée comme avant. Avec un lieu :
  `cmd_meteo` → `_meteo_d_un_autre_lieu` → `app/services/meteo_lieu.meteo_du_lieu`, en lecture
  seule — ni `save_meteo_observation`, ni cache, ni base (`test_meteo_autre_lieu` le garde).
- **Le géocodage** : `utils/geocodage.chercher_lieu`, Open-Meteo, mêmes paramètres que
  `VilleSearch.jsx` (un lieu dit au compagnon et une ville choisie à l'écran se résolvent pareil).
  Le premier résultat (le plus peuplé) est retenu, et la réponse le NOMME avec sa région et son
  pays (« Lyon, Auvergne-Rhône-Alpes, France ») ; les homonymes de même nom ailleurs sont dits
  (« Il existe aussi : Lyon, Mississippi, États-Unis »). Injoignable ≠ introuvable : deux messages.
- **La règle `meteo`** capte le lieu après une préposition (`_LIEU_DIT`) : « à Lyon », « de Lyon »,
  « au Havre » (→ Le Havre), « aux Sables-d'Olonne » (→ Les Sables-d'Olonne), « à La Rochelle ».
  `_PAS_UN_LIEU` écarte le potager et ses parties : « dans la serre » reste la météo du potager.
  Elle précède l'`est_interrogative` de `interpreter()` : une question de météo n'atteint plus
  la cascade.
- **Où la commande est documentée** (à tenir ensemble quand elle change) : `/help meteo`
  (`aide._HELP_METEO`, domaine `meteo` de `_HELP_DOMAINES`, couvert par `domaines_aide: meteo`
  de la fiche `enregistrer-un-geste.md` — `tools/controler_aide_corpus.py`), la liste générale
  de `/help`, la description du menu natif (`menu_commandes`), le guide utilisateur en DEUX
  copies (`data/connaissance/guide user/`, celle que lit le RAG, et `docs/MANUEL/`),
  `docs/CONFIGURATION/SETUP.md`. Le RAG ne la voit qu'après `tools/ingerer_connaissance.py`
  (fait par `scripts/update_dev.ps1`).
- **Ce qui n'est pas fait** : un autre jour que le jour même (« demain ») est signalé par
  `controle_mots` (`Continuer sans « demain »`), pas donné en silence ; un lieu sans préposition
  (« météo Lyon ») aussi. `fetch_meteo` rend pourtant 14 jours : le jour est la suite naturelle.

### Le prénom et le ton du compagnon — `/profil` [US-258]

`app/services/profil_echange.py` (service, validation, bloc de prompt) et
`app/bot/commandes_profil.py` (accueil, `/profil`, boutons `profil:`). Profil rangé
par `(user_id, potager_id)`, en colonnes de `potager_membres` (migration v60).

- **Premier contact** : après la première réponse de l'agent (`_repondre_agent`),
  une seule fois, le bot propose le `first_name` Telegram et les trois registres.
  Le prénom n'est écrit qu'après le bouton.
- **« appelle-moi X »** : reconnu par `phrase_de_profil` AVANT l'interpréteur, sans
  modèle. C'est une proposition (Oui / Non), pas une écriture (R9).
- **Validation** (`valider_prenom`) : lettres, espaces, tirets, 30 caractères,
  deux mots au plus. Cette dernière borne est ce qui refuse « Ignore tes règles »
  (CA5) ; la balise de donnée est la seconde ligne de défense.
- **Prompt** : `prompt_variable(..., profil=)` ajoute `<profil_jardinier>` APRÈS la
  date et les parcelles ; la partie fixe ne porte que la consigne de lecture. Le
  registre change le ton, jamais les faits ni les prudences (CA7).
- `/profil` est exclue de l'interpréteur (`MOTIFS_EXCLUSION_INTERPRETEUR`).

### Reprendre le référentiel du calendrier — `/calendrier maj` [US-279]

Sous-commande de `/calendrier` (aucune commande ajoutée au menu natif), boutons
`calmaj:` dans `app/bot/commandes_calendrier.py`, logique dans
`calendrier_cultural` (`ecarts_referentiel`, `etat_mise_a_jour`,
`remplacer_par_referentiel`, `garder_version_locale`). Le clic sur ✅ est la
confirmation : rien n'est écrit avant. Non dictable (décision du 28/10/2026).
Détail : `docs/domaines/calendrier-cultural.md`, § « Reprendre le référentiel ».

### Une demande d'agir qui échoue est dite, pas routée [INC-018]

En `actif`, si l'agent est indisponible ou rejeté (appel `tool_use_failed`,
validateur) ET que l'ancien repli ne propose rien (ou sous le seuil 0,7),
`interpreter()` rend `Aiguillage(vers='non_compris')` quand la phrase **demande
d'agir** (`demande_d_agir` : verbe d'action en tête, impératif ou « peux-tu / je
veux » ; une phrase en « ? » sans cette formule est une question). Sans cela, le
routeur par mots-clés prenait « Créez la planche Nord… » pour une question de
données et répondait la liste des lots en pépinière (confiance 1,00).

- Les règles de commande et le parseur de gestes restent des raccourcis, avant l'agent.
- Une déclaration garde le chemin d'avant (routeur), sauf si elle dit des caractéristiques
  d'une parcelle (« la planche nord a maintenant 6 rangs ») : le filet d'US-278 les propose.
- `/ask` garde la cascade : ce chemin ne passe pas par `interpreter()`.
- `off` et `ombre` ne changent pas. Un `non_compris` n'entre pas dans le contexte court.
- **Tour de complément** : un tour sans `lire` clôt la boucle, et gpt-oss-120b n'émet souvent
  qu'un appel d'écriture par réponse (« crée la planche nord de 20m2 et de longueur 2 m »
  ne créait que la planche). `validation.chiffres_non_repris` compare les nombres dits aux
  arguments appelés (l'unité de « m2 » est ignorée) ; un nombre perdu accorde UN tour de
  plus, où seules les écritures sont retenues (un doute tardif n'annule rien). Sans modèle
  ni écriture ; un faux positif coûte un appel. Ne couvre pas une seconde demande sans
  nombre (« …et mets la serre en pépinière ») : couvert depuis US-257 (verdict au modèle, ci-dessus).
- Le schéma des outils accepte `null` pour un champ facultatif (« non dit », retiré
  par le validateur) : un type strict faisait rejeter l'appel par le serveur ; la
  génération rejetée est journalisée (`llm.passerelle`, WARNING).

### Plusieurs commandes en une phrase — `Plan` [US-237]

`interpreteur_agent.proposer` est une boucle d'au plus `AGENT_MAX_TOURS` appels
(`historique` de `passerelle.appeler_chat_outils`). L'outil `lire` (parcelle,
parcelles, lot, culture — `agent/lecture.py`, potager du contexte, résultat en
JSON sous `donnees`) est exécuté et renvoyé au modèle ; une écriture reçoit
son verdict (US-257, ci-dessus) et n'est **jamais** exécutée dans la boucle ; un
tour sans appel la clôt.

| Écritures retenues | Proposition de la `ReponseAgent` |
|---|---|
| `saisir_geste` en tête | `Aiguillage(geste)` (US-236), pas de `ReponseAgent` |
| une écriture | `CommandeInterpretee`, proposition simple (CA9) |
| plusieurs écritures | `validation.valider_plan` → `Plan` ; une étape refusée reste hors du plan, le modèle lit pourquoi |

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

### Répondre à une proposition par une phrase [US-260]

« Vas-y », « laisse tomber » : deux outils de DÉCISION, `confirmer_proposition(id)` et
`abandonner_proposition(id)` (`catalogue_outils.outils_decision()`), hors du catalogue
généré mais comptés dans `NB_OUTILS_MAX` (13 + 2 + 2 de correction = 17, US-262). Ils ne sont offerts QUE si
`ContexteCourt.decidable` (une proposition attend, vient d'être traitée, ou attend dans un
autre potager) ; leur consigne est dans la partie variable (`ContexteCourt._consigne_decision`),
jamais dans `PROMPT_FIXE`. Le texte du modèle seul ne confirme rien (B3).

`Propositions._decider` (agent) valide contre le CONTEXTE : identifiant = celui de la
proposition en attente (ou de la dernière traitée), pas de nouvelle écriture dans le même
message, pas de deux candidates, proposition prête (aucun nom ni valeur en attente). Une décision
acceptée CLÔT la boucle et sort en `ResultatAgent.decision` → `ReponseAgent.decision` ; un refus dont
le code dicte la réponse (`decisions.TEXTE_*`) sort en `texte`, que le modèle ne réécrit pas.

⚠️ **Rien ne s'exécute dans l'agent.** `bot/interpretation._interp_decider` relit la proposition par son
code SOUS LE JARDINIER du message, la sort de l'attente (`consommer(…, canal="telegram")`, atomique)
puis fait ce que le bouton fait. Une destruction (`decisions.est_destructrice` : forme
`destructrice`, ou `/parcelle modifier actif=non`) ne se confirme jamais par une phrase : l'agent
refuse (`bouton_seul`), le bot REMONTRE la carte avec ses boutons (`_remontrer_la_carte`), et
`_interp_decider` rejoue le refus contre la base. L'abandon n'a aucune restriction de sécurité. Une proposition
déjà traitée répond où et quand (`traite_canal`, heure de Paris) sans rien refaire.

⚠️ **Une décision ne reprend rien** (recette du 29/10/2026 : sur Mistral Small 4, « non 4 rangs » appelait
`abandonner_proposition`). `Propositions._dit_en_plus` lit la phrase SANS modèle — nombres en chiffres
(`chiffres_non_repris`) et en lettres avec leur unité (`filet_fiche.lire_valeurs`), valeur de vocabulaire,
parcelle nommée, hors noms de parcelle — et en retranche ce que la proposition visée (en attente, ou la
dernière traitée) porte déjà. S'il reste quelque chose, la décision est écartée UNE fois
(`RAISON_DECISION_AVEC_VALEURS` : le modèle reprend avec l'outil de commande, modèle de `_lecture_a_ecarter`).
S'il y tient, l'abandon passe (il ne fait rien) ; une confirmation ne passe JAMAIS : le code répond
`decisions.TEXTE_VALEUR_A_REPRENDRE` et le bot remontre la carte (`bouton_seul`), pour qu'un « oui, 4 rangs »
ne lance pas les 2 rangs de la carte. Faux positif connu : « oui, à 18 h » coûte un clic.

⚠️ **Le modèle est un prérequis.** Les outils de décision supposent un modèle qui appelle les outils de façon
fiable. Recette du 29/10/2026 : `mistral/mistral-small-2603` confirme, abandonne et refuse la destruction comme
prévu ; Ministral 3B répond en texte et n'appelle ni `confirmer_proposition` ni `abandonner_proposition`. Les
tests de `test_us260_*` simulent le modèle : ils ne prouvent pas qu'un modèle donné appelle l'outil.

### Retenir les actions menées [US-261]

`app/services/compagnon/actions_menees.py` : une entrée par écriture exécutée, écrite par le
CHEMIN D'EXÉCUTION — `evenements.creer_evenement_*` (six, après le commit), `executeurs.executer_etape`
(étape de plan, avec avant / après de la parcelle), `bot/interpretation._interp_executer` (commande
confirmée au bouton ou à la phrase ; l'échec du handler se lit dans ses réponses,
`_MessageEcoute`). Jamais par un outil : le test `test_us261_ca2_*` refuse qu'un autre module importe
`noter*`. Le canal vient d'une `ContextVar` posée à l'entrée (`_arm_tenant_context`, middleware API).
L'agent reçoit les 5 dernières des 24 h sous `A1`…`A5` (`interpreteur_agent.bloc_actions`, balisées
comme données) ; `lire(quoi="actions")` donne les suivantes (`A6`…, 7 jours). Seules les `reussie` sont
lues. Par jardinier ET par potager, RLS stricte.

[US-262] Une correction ou une annulation exécutée par `evenements.corriger_evenement` /
`supprimer_evenement` est retenue elle aussi (`noter_correction`, `noter_annulation`, nature
`geste`, même cible) — quel que soit le chemin : phrase, `/corriger`, API.

### Corriger ou annuler une action menée [US-262]

« En fait c'était 3 rangs », « annule le dernier semis » : `app/services/compagnon/corrections.py`.
Deux outils d'ÉCRITURE, hors catalogue généré : `corriger_action(ref, champs)` (offert dès qu'une
des actions A1…A5 est un geste) et `annuler_action(ref)` (en plus, si la phrase demande de retirer :
`demande_une_annulation`). Jamais sur une question (`sans_ecriture`). La consigne est dans la partie
VARIABLE (`CONSIGNE_CORRECTION`, ajoutée à `bloc_actions`) : `PROMPT_FIXE` inchangé.

| Étape | Où | Règle |
|---|---|---|
| Candidates | `corrections.candidates` | gestes (cible `evenement`) encore au carnet et parcelles créées ou modifiées (cible `parcelle`, fiche d'après connue, encore active), A1…A5 puis A6…, une cible touchée deux fois une seule fois (référence la plus récente) |
| Compatibilité | `corrections.compatibles` | une correction ne vise que les candidates auxquelles TOUS ses champs s'appliquent : un champ de geste déjà renseigné (`rang`, `quantite`), culture / variété / parcelle / date pour tout geste, un champ de fiche pour une parcelle (`rang` → `nb_rangs`) ; aucune → toutes. Recette du 29/10 (Ministral 8B) : « en fait c'était 8 rangs » après une modification de parcelle demandait laquelle entre deux arrosages et un semis en graines |
| Désignation | `corrections.designer` | « le dernier » → la plus récente (parmi celles que la phrase nomme) ; une ANNULATION qui nomme une culture ou un geste ne vise que lui ; sans désignation et plusieurs candidates → question du CODE qui les nomme (CA4), boucle close (`texte_code`) |
| Champs | `corrections._champs_corriges` | ancrage du validateur : nombre dit (chiffres ou lettres), texte dit, parcelle exacte, date `AAAA-MM-JJ` + repère dans la phrase ; seuls les champs qui CHANGENT ; « 3 rangs » sur un geste compté en `rangs` corrige `quantite` |
| Proposition | `CommandeInterpretee` de forme `action corriger` / `action annuler` | rangée comme une commande (nature `commande`, pas de migration) ; `commande_equivalente` / `recapitulatif` délèguent à `corrections` : « Semis radis : 2 rangs → 3 rangs » ; annuler est `destructrice` → bouton seul (US-260) ; un semis qui a des suites (`origine_graines_id`) ne s'annule pas d'une phrase |
| Parcelle | `corrections._corriger_parcelle` | la correction DEVIENT `/parcelle modifier` (appel `modifier_parcelle` passé à `valider_appel`, nom de la parcelle ajouté au texte d'ancrage car il vient de l'action, valeurs dites) ; `valeurs["correction"]` porte l'avant → après que `recapitulatif` met en tête ; exécutée par le handler comme toute commande ; une annulation de parcelle demande la valeur à remettre |
| Exécution | `bot/interpretation._interp_executer` → `corrections.executer` | geste relu : disparu ou changé depuis la proposition → rien ; sinon `corriger_evenement` (mêmes invariants qu'une création) ou `supprimer_evenement` |

⚠️ **Le modèle qui décrit sans appeler** (recette du 29/10, Ministral 8B : « Proposition : /corriger — Plantation tomate : 5 plants → 2 plants. Confirme-moi » en TEXTE, sans carte ; « oui » ne confirmait rien). Trois parades, dans l'ordre : `_PROPOSITION_DECRITE` reconnaît « Proposition : », « confirme-moi » et « N … → » ; une phrase de correction sans aucun appel reçoit UNE relance qui nomme l'outil (`CORRECTION_SANS_APPEL_ACTION`, avant les relances génériques) ; si la boucle finit sans écriture, `_filet_correction` (début de `_conclure`) appelle `corrections.filet` : la valeur dite est lue SANS modèle (`valeur_dite` : « 2 plants », « huit rangs », une seule valeur, celle après « pas » / « au lieu de » ignorée) et passe par `corrections.valider` comme un appel sans référence. Une correction aboutit donc toujours à une carte avec ses boutons, que « oui » peut confirmer. La désignation départage aussi par l'unité dite (« plants » écarte un semis en graines) et, sans autre indice, par le seul geste des 10 dernières minutes.

⚠️ **CA6 — pas de second geste.** `Propositions.geste_a_ecarter` renvoie UNE fois au modèle un
`saisir_geste` fait sur une phrase de correction (`ressemble_a_une_correction`) quand `corriger_action`
est offert ; s'il y tient, le geste passe. Une correction ne se mélange à aucune autre écriture.

⚠️ **CA3 — avant le filtre « geste annoncé ».** `interpreteur_commandes._correction_d_une_action_recente`
(agent `actif` seulement) : marque de correction (« en fait », « finalement », « non… », « je me suis
trompé », « annule »…) ET geste mené il y a moins de `DELAI_CORRECTION` (10 min) ; une phrase en
« annul… » passe tant qu'un geste des 24 h est corrigeable (« annule le dernier semis » est un geste
annoncé pour `annonce_un_geste`). Un geste nouveau sans marque garde le filtre. Le raccourci
« annuler… / corriger… » de `handle_text` (PRIORITÉ 3) cède à l'interpréteur quand la phrase a plus
d'un mot et qu'un geste récent existe (`pour_l_agent_plutot_que_le_raccourci`) : sinon « annuler le
dernier semis » proposait le dernier enregistrement, quel qu'il soit.

⚠️ Les tests (`test_us262_*`) simulent le modèle. La mesure du lot 2 (CA6 : bonne action ≥ 95 %,
0 second geste) se fait sur le vrai modèle avec `tools/evaluer_dialogues.py`, avec accord.

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
