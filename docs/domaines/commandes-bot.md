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

Mesure et journal :

```bash
psql -d potager -f migrations/migration_v44.sql   # routage_logs : commande + issue
pytest tests/test_us172_interpreteur_commandes.py
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
