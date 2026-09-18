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

## Piloter le bot par une phrase [US-172]

Les 24 commandes du bot sont DICTABLES : 18 le sont pour de bon, 1 est un alias
de sa cible canonique (`/parcelles` = `/parcelle lister`), et 5 sont écartées
sur décision motivée (`/ask`, `/start`, `/lier`, `/delier`, `/version`).
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

`tests/corpus/us172_commandes.csv` : 154 formulations de commande, 36 questions
de savoir voisines, 26 phrases hors périmètre — recomptées le 17/09/2026, les
chiffres inscrits ici jusque-là étant restés ceux d'une version antérieure du
corpus. Au 17/09/2026 : 100 % de
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
