# EPPO Global Database — conditions d'utilisation lues et consignées

> **Ce document répond au CA7 d'US-162**, qui en faisait un *préalable bloquant* :
> « Les conditions d'utilisation de `data.eppo.int` sont lues et consignées avant
> tout import de masse. Si elles interdisent la reprise en base, les codes EPPO
> sont saisis à la main sur le périmètre des dix cultures — travail borné —
> plutôt qu'importés. »
>
> **Verdict : elles ne l'interdisent pas. Elles l'autorisent explicitement, y
> compris commercialement.** Le repli manuel prévu par le CA7 n'a pas lieu d'être.

| | |
|---|---|
| **Organisation** | European and Mediterranean Plant Protection Organization (EPPO / OEPP), Paris |
| **Portail de données** | https://data.eppo.int/ |
| **Document de licence** | https://data.eppo.int/data/Open_Licence.pdf |
| **Intitulé exact** | **EPPO Codes Open Data Licence** |
| **Daté du** | 17/11/2014 (mention de pied de page du PDF : « EPPO, Paris - 2014-11-17 ») |
| **Lu et consigné le** | 06/09/2026 |
| **Code registre** | `eppo` (`migrations/migration_v43.sql`, `app/services/referentiel_sources.py`) |

## Ce que la licence accorde

EPPO accorde au « Re-user » un droit **mondial, perpétuel, gratuit et non
exclusif** d'utiliser les codes EPPO. Verbatim des libertés énumérées :

> *To reproduce, copy, publish and transmit the EPPO Codes;*
> *To build upon them in order to create « Derivative information »;*
> *To exploit the EPPO Codes freely or commercially, for example, by combining
> them with other information, or by including them in your own product or
> application.*

Les trois points qui décidaient de l'US sont donc tranchés :

1. **La reprise en base est autorisée** — « reproduce, copy, publish and transmit ».
2. **L'usage commercial est autorisé** — nommément, et jusqu'à l'inclusion « in
   your own product or application », ce qu'est exactement ce référentiel.
3. **Aucune clause de partage à l'identique.** C'est le seul motif d'exclusion
   posé par l'arbitrage §6.3 de la conception (une clause `-SA` contaminerait un
   corpus qui doit rester propriétaire). Cette licence n'en porte pas — même
   raisonnement que l'admission de CC BY 4.0 pour Wind River Greens en US-161.

## Ce que la licence exige — et où c'est tenu dans le code

| Obligation | Où elle est tenue |
|---|---|
| Citer la source, **au moins le nom d'EPPO** | `referentiel_source.attribution` = `Contains EPPO Codes (www.eppo.int) — EPPO Codes Open Data Licence` |
| Citer **la date du dernier téléchargement** | `referentiel_source.date_dernier_import`, recomposée à l'affichage par `referentiel_sources.attribution_affichee` — jamais figée dans la chaîne, qui mentirait au premier rejeu |
| **Ne pas reproduire le logo EPPO** | Aucun visuel EPPO n'est versionné ni affiché ; l'attribution est textuelle |
| Ne pas suggérer un statut officiel ni un aval d'EPPO | L'attribution dit « Contains EPPO Codes », jamais « validé par EPPO » |
| Ne pas travestir le contenu, sa source ni sa date | Les codes sont repris tels quels ; aucun code n'est produit par un modèle de langage (CA10 d'US-140) |

La licence précise aussi qu'EPPO fournit les codes **tels que produits ou reçus**,
sans garantie d'absence d'erreur ni de continuité du service, et que le
ré-utilisateur est seul responsable de sa ré-utilisation. C'est une raison de
plus pour que l'import reste **hors ligne** (CA5) : la disponibilité de
`data.eppo.int` n'a jamais à se trouver sur le chemin de réponse d'un jardinier.

## Ce que ce répertoire contient — et ne contient pas

**Aucune donnée EPPO n'est versionnée à ce jour.** US-162 livre la structure, le
chemin d'import et la traçabilité ; elle ne procède à aucun téléchargement de
masse. Le jour où un extrait sera versionné ici, il suivra la forme de
`data/referentiel/wind_river_greens/` : un extrait **filtré au périmètre**, pas
un dump, avec la recette pour le reconstituer.

En attendant, un code EPPO entre par les deux chemins ordinaires — et c'est
suffisant pour le périmètre des dix cultures :

```bash
# 1. Manifeste versionné (bloc `bioagresseurs`, champ `code_eppo`)
python tools/importer_referentiel.py data/referentiel/bioagresseurs_redaction_interne.json --dry-run
python tools/importer_referentiel.py data/referentiel/bioagresseurs_redaction_interne.json

# 2. Saisie au bot, qui prime sur tout rejeu d'import
#    /bioagresseur declarer <nom> <categorie> [code_eppo]
```

## Reconstituer la lecture de la licence

```bash
curl -sL https://data.eppo.int/data/Open_Licence.pdf -o /tmp/eppo_open_licence.pdf
# Le PDF est la source de vérité. Cette fiche en est la consignation datée,
# pas un substitut : une relecture s'impose avant tout import de masse ultérieur.
```
