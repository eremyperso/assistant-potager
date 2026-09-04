# Corpus de connaissance — le contenu vit ici, la base n'en est que l'index

Ce dossier est la **source**. `knowledge_documents` / `knowledge_chunks` en sont
la projection interrogeable, reconstruite à volonté par :

```bash
python tools/ingerer_connaissance.py --dry-run   # rapport seul
python tools/ingerer_connaissance.py             # ingestion réelle, idempotente
python tools/ingerer_connaissance.py --strict    # échoue sur un défaut de découpage
python tools/ingerer_connaissance.py --elaguer   # retire aussi les fiches supprimées du dépôt
```

Arbitrage tranché d'US-098 : **rien ne s'édite en base.** Une fiche se corrige
ici, se relit comme du code, se versionne, puis se réingère. Une interface
d'administration en ligne serait un chantier sans valeur à ce stade.

> **Le dossier est volontairement vide de fiches à ce jour.** US-098 livre le
> contenant. Le contenu arrive avec **US-099** (fonctionnement de
> l'application), **US-140** (agronomie) et **US-141** (mémoire du potager) :
> le travail éditorial est long, la mécanique était courte, il n'y avait aucune
> raison de les livrer ensemble.

## Format d'une fiche

Une fiche couvre **un couple culture × thème** (`tomate-problemes.md`,
`carotte-recolte-conservation.md`), pas une culture entière : le titre du
document est indexé sur chaque fragment, et une fiche « tomate » unique sort
en tête sur toute question contenant le mot « tomate ».

```markdown
---
titre: "Problèmes observables de tomate"
famille: "agronomie"                # agronomie | doc_app | memoire_potager
source: "Rédaction interne"         # ce qui s'affiche « _Source : …_ »
niveau_confiance: "a-valider"       # verifie | indicatif | a-valider
culture: "tomate"                   # facultatif — DOIT exister dans culture_config
type: "maladie"                     # facultatif — maladie, semis, association, rotation…
saison: "ete"                       # facultatif
potager_id: 3                       # facultatif — savoir privé d'un potager (US-141)
theme: "problemes"                  # facultatif — repère éditorial, non indexé
version: "2.0"                      # facultatif — repère éditorial, non indexé
index_terms:                        # index de RELECTURE — non indexé (voir règle 4)
  - "cul noir"
sources:                            # organismes consultés — non indexé
  - organisme: "USDA National Agricultural Library"
    licence: "Domaine public"
---

# Problèmes observables de tomate          ← ignoré : recopie `titre:`

## Mes tomates ont le cul noir ou pourrissent par dessous

**Intention :** diagnostic                 ← retiré du texte servi, NON indexé
**Organes concernés :** fruit              ← retiré du texte servi, INDEXÉ
**On parle aussi de :** cul noir tomate ; nécrose apicale ; manque de calcium

Une idée, répondable telle quelle, sans avoir lu ce qui précède.

## Sources et licence                      ← section ignorée : pied de fiche

- U.S. Department of Agriculture, National Agricultural Library…
```

L'en-tête est lu par un analyseur `clé: valeur` maison — le projet n'ajoute
aucune dépendance YAML. Les blocs en liste sont **traversés sans être lus** :
le schéma n'a qu'un champ `source` scalaire, celui affiché au jardinier.

Rien de ce que l'outil ignore ne disparaît du fichier : le `.md` reste lisible
de bout en bout par un relecteur humain, il n'entre simplement pas à l'index.

## Les cinq règles qui décident de la qualité des réponses

1. **Un titre de niveau 2 = un fragment = une idée répondable.** C'est l'unité
   de recherche et l'unité de réponse : un fragment servi tel quel doit se
   suffire. `--strict` refuse un corpus dont un fragment ouvre par « il faut
   alors… » ou tient en deux lignes. L'intitulé est la **question déguisée** :
   « Mes tomates ont le cul noir » est un bon titre, « Traitement » n'en est
   pas un.
2. **« On parle aussi de » porte les deux registres.** La recherche est
   **lexicale** : un lemme absent de l'index est un rapprochement impossible,
   quelle que soit la qualité du texte. La ligne doit porter les mots du
   jardinier (`cul noir`, `poudre blanche`) **et** ceux de l'agronome
   (`nécrose apicale`, `oïdium`). C'est la règle qui pèse le plus lourd : sur
   le même moteur, sans un changement de code, la mesure passe de 3/12 à
   17/19 en tête selon que ces alias sont écrits ou non.
3. **`niveau_confiance` engage l'application.** Un fragment `verifie` peut être
   servi mot pour mot au jardinier, sans passer par un modèle. Un fragment
   `indicatif` — comme `a-valider`, son synonyme éditorial — ne l'est jamais :
   il descend en contexte vers l'étage de raisonnement, qui peut le nuancer.
   Dans le doute, écrire `a-valider`.
4. **Les alias vont dans la section, pas dans l'en-tête.** `index_terms:` au
   niveau du document n'est pas indexé, et la raison est mesurée : il pèse
   identiquement sur toutes les sections de la fiche, donc il dilue exactement
   ce que les alias de section discriminent (17/19 en tête sans lui, 15/19
   avec). Il garde sa valeur d'index de relecture dans le fichier.
5. **`culture` est résolue en référence, pas stockée en texte.** Le libellé doit
   exister dans `culture_config`, sinon la fiche est refusée. C'est ce qui fait
   qu'une culture renommée depuis le bot n'orpheline aucun fragment.

## Ce qu'une fiche ne contient pas

- **Ni association, ni règle de rotation** (US-140/CA7bis) : ce sont des arêtes
  entre cultures, portées par `association_culture` et le calcul de rotation
  (US-163). Écrites dans une fiche, elles deviendraient une seconde vérité,
  invisible du calcul et impossible à croiser avec l'historique d'une parcelle.
  Une fiche peut en revanche **expliquer** le mécanisme.
- **Ni date, ni fenêtre de calendrier** : elles relèvent du référentiel
  calendrier (US-068).
- **Ni donnée d'un potager** dans une fiche globale : le savoir global est
  partagé par tous les jardins.
