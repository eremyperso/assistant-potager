# Notes de conception par domaine

Ces fiches sont la forme longue de ce que `CLAUDE.md` ne porte plus à la racine :
les décisions de conception, les garde-fous et les commandes de chaque domaine.
Elles se lisent **à la demande**, quand on touche au domaine concerné — jamais
toutes à la fois.

La table se lit à l'envers : *je touche à ceci, donc je lis cette fiche*.

| Je touche à… | Je lis… |
|---|---|
| `app/services/{familles,attributs_culture,associations,rotation,bioagresseurs,fiche_culture,import_referentiel,adaptateur_wind_river,referentiel_sources}.py`, `data/referentiel/`, `tools/importer_referentiel.py`, `tools/adapter_wind_river.py` | [referentiel-cultures.md](referentiel-cultures.md) |
| `app/services/prediagnostic.py`, `app/services/reponses_chiffrees.py` (famille `bioagresseurs_culture`), `llm/routeur.py` (ouverture interrogative), `data/referentiel/symptomes_*.json` | [prediagnostic.md](prediagnostic.md) |
| `app/services/{calendrier_cultural,contexte_semis,recalage_calendrier,confiance_semis}.py`, `app/bot/commandes_confiance.py`, `utils/date_utils.py` (mode `futur`), `evenements.contexte_semis`, `potagers.zone_climatique`, bloc `cultures_calendriers` du manifeste Wind River | [calendrier-cultural.md](calendrier-cultural.md) |
| `app/bot/` (une commande ajoutée ou retirée), `app/services/menu_commandes.py`, `app/services/interpreteur_commandes.py` | [commandes-bot.md](commandes-bot.md) |
| `app/services/{connaissance,memoire_potager}.py`, `llm/rag.py`, `data/connaissance/`, `tools/ingerer_connaissance.py`, `tools/mesurer_corpus_savoir.py`, `RAG_*` dans `app/config.py` | [socle-connaissance.md](socle-connaissance.md) |
| `migrations/`, `database/models.py` | [migrations.md](migrations.md) |

Une fiche ajoutée ici entre dans cette table dans le même commit.
