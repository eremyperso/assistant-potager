# Analyse consommation des token claude code
De quel cache s'agit-il ?
C'est le cache de prompt de l'API Anthropic, côté serveur. Le modèle ne garde aucune mémoire entre deux appels. Chaque fois que j'appelle un outil (lire un fichier, lancer pytest, faire une modification), Claude Code me renvoie tout le contexte : prompt système, outils, CLAUDE.md, et tous les messages et résultats d'outils depuis le début. La partie déjà envoyée à l'appel précédent est reprise depuis le cache au lieu d'être retraitée, pour environ 10 % du prix normal.

Ton écran et mon chiffre mesurent donc deux choses différentes :

241,8 k : la taille du contexte à cet instant, une photo.
19,2 M : la somme des contextes relus sur les 113 appels. Le contexte a grossi d'environ 40 k à 240 k pendant la session, soit environ 170 k en moyenne, et 113 × 170 k ≈ 19 M.
Le coût dépend donc surtout de la taille du contexte multipliée par le nombre d'allers-retours. Et chaque fichier lu reste dans le contexte pour tous les appels suivants.

Oui, c'est moi qui ai rempli le contexte
Sur cette session, les plus gros postes ont été :

Poste	Taille	Relu à chaque appel
CLAUDE.md	20,4 k	oui, dès le 1er appel → environ 2,3 M sur le total
Définitions des outils	18,7 k	oui → environ 2,1 M
calendrier_cultural.py lu en entier (1 100 lignes)	environ 15 k	à partir du moment où je l'ai lu
recalage_calendrier.py, extraits de bot.py, de l'adaptateur, de l'interpréteur	environ 25 k	idem
Les 4 fichiers .agent.md de l'orchestration	environ 5 k	idem
Sorties pytest, grep, diff	quelques k	idem
Rien que la partie fixe (CLAUDE.md et les outils) représente environ 25 % des 19 M, avant même d'avoir lu une ligne de code.

J'ai aussi mes propres inefficacités : j'ai lu calendrier_cultural.py en entier alors qu'une lecture ciblée aurait suffi, et j'ai lancé la suite complète plusieurs fois pour mesurer la baseline.

L'application qui grossit fera-t-elle grossir la consommation ?
Pas mécaniquement. Je ne charge pas le dépôt, seulement ce que je lis. Une US bien délimitée dans une application de 500 000 lignes peut coûter autant qu'ici.

En revanche, trois choses grossissent bien avec ton projet, et elles sont évitables :

Le CLAUDE.md. Il fait déjà 20 k tokens et gagne une section à chaque US. C'est le coût le plus sournois, parce qu'il est payé à chaque appel de chaque session, même pour une question sans rapport.
Les fichiers monolithiques. bot.py fait plus de 7 500 lignes et interpreteur_commandes.py plus de 2 000. Pour modifier 10 lignes, il faut en lire des centaines autour.
Les règles transverses. Une règle comme « relire le corpus à chaque changement » oblige chaque US à charger plus de contexte.
Les bonnes pratiques, par ordre d'impact
1. Alléger CLAUDE.md, c'est le levier n°1.

Garde à la racine l'essentiel, sous 3 à 5 k tokens : langue, règles non négociables, commandes de base, conventions.
Déplace la documentation propre à chaque US (US-068, US-165, US-172…) dans docs/, ou dans des CLAUDE.md placés dans les sous-dossiers (par exemple app/services/CLAUDE.md). Claude Code ne les charge que lorsqu'il travaille dans ce dossier.
Sur 113 appels, passer de 20 k à 4 k économise environ 1,8 M de tokens par session comme celle-ci.
2. Une US égale une session. Lance /clear entre deux US. Si une session s'allonge, /compact résume l'historique.

3. Des sous-agents pour l'exploration bruyante. Une recherche large ou une suite de tests complète peut tourner dans un sous-agent. Ses lectures restent dans son propre contexte, et seul un résumé revient dans le contexte principal. Il consomme lui-même des tokens, mais il ne gonfle pas les 100 appels suivants.

4. Découper les gros fichiers. Par exemple, un fichier par commande dans bot/handlers/. Des modules plus petits permettent des lectures plus petites, et cela améliore aussi la maintenabilité du code.

5. Des consignes d'efficacité dans tes fichiers agents. Par exemple :

« Chercher d'abord (grep), lire ensuite uniquement les plages utiles. »
« Lancer seulement les tests ciblés ; la suite complète une seule fois en fin de QA, avec une sortie filtrée. »
Garder les fichiers .agent.md courts, puisqu'ils sont lus à chaque orchestration.
6. Ne pas laisser la session en pause trop longtemps. Le cache expire après un délai d'inactivité. Après une longue pause, tout le contexte est réécrit en cache, ce qui coûte plus cher qu'une simple relecture.

Si tu veux, je peux commencer par le point 1 : proposer un découpage de ton CLAUDE.md actuel, avec ce qui reste à la racine et ce qui part dans docs/ ou dans des CLAUDE.md de sous-dossiers.


# Ce qui a été fait par fable 5.1

Les quatre chantiers sont livrés dans le répertoire de travail, rien n'est commité (conformément à ta règle). La suite complète est au même niveau qu'avant intervention : aucun nouvel échec, et 5 tests de déploiement qui échouaient avant sont désormais verts.

Résultat des tests
Avant	Après
Réussis	3 009	3 037
Échecs + erreurs	58	53
Nouveaux échecs		0
Les 53 échecs restants existaient déjà sur la branche avant mon intervention (US-140 en SQLite, test_bot stats, test_us005 smoke test du workflow, etc.). La liste de référence est dans mon scratchpad si tu veux la comparer.

1. CLAUDE.md allégé
Le fichier racine passe de 733 lignes (environ 20 000 jetons) à 145 lignes (environ 2 400 jetons). Rien n'est perdu : le contenu est redistribué.

docs/domaines/ : six fiches de conception (référentiel, pré-diagnostic, calendrier, commandes du bot, socle de connaissance, migrations) avec un README.md « je touche à ceci, donc je lis cette fiche ».
CLAUDE.md de sous-dossiers, chargés seulement quand on y travaille : app/bot/CLAUDE.md, app/services/CLAUDE.md, data/CLAUDE.md, frontend/CLAUDE.md, tests/CLAUDE.md.
Une section « Efficacité de contexte » en tête du fichier racine.
2. bot.py découpé en package app/bot/
22 modules par domaine, générés par analyse AST sans cycle d'import (noyau, état, normalisation, aide, liaison, enregistrement, godets, pertes, notes, saisie, questions, interprétation, correction, déplacement, cinq modules de commandes, météo et jobs, messages, application). Lancement par python -m app.bot.

Le point clé : 38 fichiers de tests posent des monkeypatch directement sur le module bot (209 fois sur SessionLocal). Plutôt que de réécrire ces tests, app/bot/init.py est une façade qui expose tous les noms et propage chaque affectation d'attribut vers les sous-modules concernés. Les tests existants fonctionnent sans modification de leur logique.

3. Consignes d'efficacité dans les agents
Section « Efficacité de contexte » ajoutée à Developer, QA, Orchestrateur, Analyste-Incident et Patch Notes Writer (chercher avant de lire, tests ciblés, diffs par fichier, une seule fiche de domaine par US). La structure projet du Developer, obsolète, est réécrite.

4. Arborescence et déploiement
main.py → app/api/main.py, config.py → app/config.py (le .env est cherché dans le répertoire courant, puis à la racine).
update_dev.ps1 et deploy.sh → scripts/ ; les deux vérificateurs Jira → tools/verifier_jira_*.py.
Supprimés : bot.py, bot_meteo_patch.py, config.py.example, .coverage ; rapport_tests.html et htmlcov/ désormais ignorés par git.
Déploiement : les quatre unités systemd de infra/ pointent sur python -m app.bot et uvicorn app.api.main:app, et sont réinstallées par les workflows à chaque déploiement. Le hook post-merge, scripts/deploy.sh (aligné sur les vrais services potager-prod*), README, SETUP et RUNBOOK sont à jour.
VERSION passe à 3.67.0 avec une entrée en tête de PATCH_NOTES.md.
Points d'attention avant de commiter
Le travail US-177 non commité est mêlé à cette restructuration dans le même arbre de travail. Si tu veux deux commits distincts, il faudra les séparer à la main ; je n'ai pas commité pour te laisser ce choix.
llm/, database/ et utils/ restent à la racine : je ne les ai pas déplacés sous app/, pour limiter le risque de régression. C'est une suite possible.
tools/audit_appels_llm.py signale tools/mesurer_modeles_llm.py (appel Groq direct) : c'était déjà le cas avant, je n'y ai pas touché.
Sur les serveurs, rien à faire : le prochain déploiement réinstalle les unités systemd. Une vérification à la main du premier redémarrage du bot dev reste prudente.