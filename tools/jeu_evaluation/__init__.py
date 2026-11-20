"""
tools/jeu_evaluation — Jeu d'évaluation du compagnon et lanceur commun [US-336, US-337]
======================================================================================
Lot 0 de `docs/EPIC - AGENT INTERPRETEUR/ARCHITECTURE_COMPAGNON_CAPACITES.md` : mesurer avant de
changer. Une pièce par responsabilité :

* `jeu`          — le jeu (besoins × formulations), son format, ses contrôles (US-336) ;
* `utilisateur`  — le jardinier simulé : répond depuis la fiche de besoin, jamais au-delà ;
* `trace`        — la trace complète de chaque tour ;
* `controles`    — les critères à 100 % et les attendus textuels, contrôlés par le code ;
* `juge`         — les critères de sens, notés par un modèle plus fort avec une grille écrite ;
* `moteurs`      — la chaîne actuelle, la boucle à capacités (prototype du 14/11) et Claude + MCP ;
* `rapport`      — critère par critère, dispersion, comparaison avant / après ;
* `tools/evaluer_compagnon.py` — le lanceur en ligne de commande.

Aucune écriture dans le potager : les lectures se font dans une transaction annulée, les écritures sont
simulées au schéma du registre ; seules les lignes `conso_tokens` de la passerelle sont créées.
"""
