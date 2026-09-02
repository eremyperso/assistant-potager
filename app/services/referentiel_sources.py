"""
app/services/referentiel_sources.py — Registre des sources du référentiel [US-166]
----------------------------------------------------------------------------------
Ce module est le seul point d'entrée pour déclarer une source, contrôler sa
licence et retrouver ce qui en dérive. L'import (`tools/importer_referentiel.py`)
et les corrections au bot (`app/services/familles.py`) y passent tous les deux :
« aucun second mécanisme », comme le pose US-140.

**Le socle de licences (CA6) est fermé, pas indicatif.** Deux sources d'import
seulement — Wikidata en CC0, E-Phy / ANSES en Licence Ouverte 2.0 — plus les
origines internes en propriétaire. Tout le reste est refusé à la porte, y
compris « en attendant » et « pour tester » : une licence inconnue ou hors socle
lève `LicenceHorsSocleError` **avant** la moindre écriture, et rien n'est créé.
Le motif est dans `docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md` §2.1 — une
clause de partage à l'identique contaminerait un corpus qui doit rester
propriétaire.

**Aucun appel réseau ici (CA8).** Ce module lit et écrit la base, rien d'autre :
le registre décrit des sources, il ne les contacte jamais. La récupération des
fichiers source est une opération d'administration hors ligne, hors du chemin de
réponse au jardinier.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.models import ReferentielSource

# ── Licences du socle (CA6) ──────────────────────────────────────────────────
LICENCE_CC0 = "CC0"
LICENCE_LICENCE_OUVERTE = "Licence Ouverte 2.0"
LICENCE_CC_BY = "CC BY 4.0"
LICENCE_PROPRIETAIRE = "proprietaire"

#: Licences acceptées pour un contenu **importé** — le socle, et lui seul.
#:
#: `CC BY 4.0` a été ajoutée le 01/09/2026 pour Wind River Greens. C'est un
#: élargissement, pas un renoncement : l'arbitrage §6.3 de
#: `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` n'écarte que le
#: **partage à l'identique** (`-SA`), qui contaminerait le corpus. CC BY n'a
#: aucune clause virale — partage, adaptation et usage commercial sont libres —
#: et sa seule contrainte, l'attribution, est déjà une obligation par
#: enregistrement dans ce registre (CA1) et déjà affichée avec la réponse
#: (US-164 / CA7). Le socle refuse donc toujours CC-BY-SA, et toujours ce dont
#: la licence n'est pas établie.
LICENCES_IMPORTABLES: frozenset[str] = frozenset({
    LICENCE_CC0, LICENCE_LICENCE_OUVERTE, LICENCE_CC_BY,
})

#: Licences acceptées au registre, importées ou non. `proprietaire` couvre les
#: origines internes (CA3), qui n'importent rien mais tracent quand même.
LICENCES_SOCLE: frozenset[str] = LICENCES_IMPORTABLES | frozenset({LICENCE_PROPRIETAIRE})

# ── Codes des origines connues ───────────────────────────────────────────────
SOURCE_WIKIDATA = "wikidata"
SOURCE_EPHY_ANSES = "ephy_anses"
SOURCE_WIND_RIVER = "wind_river_greens"
SOURCE_SAISIE_MANUELLE = "saisie_manuelle"
SOURCE_REDACTION_INTERNE = "redaction_interne"

#: Semis du registre — repris tel quel par `migrations/migration_v38.sql`.
#: Les deux dernières entrées sont les origines **non importées** (CA3) : une
#: donnée saisie par le jardinier est tracée au même titre qu'une donnée importée.
SOURCES_SOCLE: tuple[dict, ...] = (
    {
        "code": SOURCE_WIKIDATA,
        "libelle": "Wikidata",
        "licence": LICENCE_CC0,
        "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
        "url": "https://www.wikidata.org/",
        "partageable": True,
        "importee": True,
    },
    {
        "code": SOURCE_EPHY_ANSES,
        "libelle": "Catalogue E-Phy (ANSES)",
        "licence": LICENCE_LICENCE_OUVERTE,
        "attribution": "ANSES — catalogue E-Phy, Licence Ouverte 2.0 (Etalab)",
        "url": "https://www.data.gouv.fr/fr/datasets/donnees-ouvertes-du-catalogue-e-phy-des-produits-phytopharmaceutiques/",
        "partageable": True,
        "importee": True,
    },
    {
        "code": SOURCE_WIND_RIVER,
        "libelle": "Wind River Greens Plant Database",
        "licence": LICENCE_CC_BY,
        # [CA1] Mention EXACTE demandée par le LICENSE du jeu de données. CC BY
        # rend l'attribution obligatoire à l'affichage, pas seulement au dépôt :
        # c'est cette chaîne, avec son lien, qui doit accompagner une réponse
        # qui en dérive (US-164 / CA7).
        "attribution": (
            "Plant variety data from Wind River Greens Plant Database "
            "(https://plants.windrivergreens.com), CC BY 4.0"
        ),
        "url": "https://github.com/bripatch/plant-variety-database",
        "partageable": True,
        "importee": True,
    },
    {
        "code": SOURCE_SAISIE_MANUELLE,
        "libelle": "Saisie du jardinier",
        "licence": LICENCE_PROPRIETAIRE,
        "attribution": "Saisi par le jardinier",
        "url": None,
        "partageable": True,
        "importee": False,
    },
    {
        "code": SOURCE_REDACTION_INTERNE,
        "libelle": "Rédaction interne Assistant Potager",
        "licence": LICENCE_PROPRIETAIRE,
        "attribution": "Assistant Potager — rédaction interne",
        "url": None,
        "partageable": True,
        "importee": False,
    },
)

#: Tables du référentiel structuré rattachées au registre, et colonne portant le
#: rattachement. Une entrée par arête tracée — c'est cette table qui fait de CA4
#: une requête, et non une fouille de code six mois plus tard.
TABLES_RATTACHEES: tuple[tuple[str, str, str], ...] = (
    ("familles_botaniques", "source_id", "nom"),
    ("culture_config", "famille_source_id", "nom"),
    # [US-161 / CA3] Une arête par attribut agronomique : une source litigieuse
    # doit pouvoir être retirée attribut par attribut, sans emporter les trois
    # autres, qui viennent peut-être d'ailleurs — ou du jardinier.
    ("culture_config", "exposition_source_id", "nom"),
    ("culture_config", "besoin_eau_source_id", "nom"),
    ("culture_config", "profondeur_semis_source_id", "nom"),
    ("culture_config", "rusticite_min_source_id", "nom"),
    # [US-163] Une association n'a qu'une seule origine (pas une par côté) :
    # une ligne dans `TABLES_RATTACHEES` suffit, contrairement aux quatre
    # attributs de conduite ci-dessus.
    ("association_culture", "source_id", "motif"),
)


class LicenceHorsSocleError(Exception):
    """[CA6] Licence non établie ou établie hors socle — rien ne doit être créé."""


def verifier_licence_importable(licence: Optional[str]) -> str:
    """
    [CA6] Valide la licence déclarée par une source d'import, ou refuse.

    Refuse aussi bien une licence hors socle (`CC-BY-SA-4.0`) qu'une licence
    absente ou vide — « non établie » et « établie hors socle » sont traitées
    identiquement, faute de quoi un fichier sans en-tête de licence passerait.
    `proprietaire` est refusé ici : il ne vaut que pour une origine interne, qui
    par définition n'importe rien.

    Lève `LicenceHorsSocleError`. Retourne la licence normalisée sinon.
    """
    valeur = (licence or "").strip()
    if valeur not in LICENCES_IMPORTABLES:
        raise LicenceHorsSocleError(
            f"Licence « {valeur or 'non établie'} » hors socle : l'import est refusé et "
            f"rien n'est créé. Licences importables : {', '.join(sorted(LICENCES_IMPORTABLES))} "
            f"(arbitrage option A, docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §2.1)."
        )
    return valeur


def get_source(db: Session, code: str) -> Optional[ReferentielSource]:
    """Retrouve une source par son code stable, ou None."""
    if not code or not code.strip():
        return None
    return (
        db.query(ReferentielSource)
        .filter(ReferentielSource.code == code.strip())
        .first()
    )


def enregistrer_source(
    db: Session,
    code: str,
    libelle: str,
    licence: str,
    attribution: str,
    url: Optional[str] = None,
    partageable: bool = True,
    importee: bool = True,
) -> ReferentielSource:
    """
    [CA1, CA2, CA6] Déclare une source au registre, ou met à jour sa fiche.

    Idempotent (CA5) : rejouer ne crée pas de doublon, le code est unique. La
    licence est contrôlée pour toute source d'import (`importee=True`) ; une
    origine interne n'accepte que `proprietaire`. `date_dernier_import` n'est
    jamais touchée ici — elle est datée par `marquer_import`, à l'issue d'un
    import réellement réussi, pas à la déclaration de la source.
    """
    if importee:
        licence = verifier_licence_importable(licence)
    elif (licence or "").strip() not in LICENCES_SOCLE:
        raise LicenceHorsSocleError(
            f"Licence « {licence or 'non établie'} » hors socle pour l'origine « {code} »."
        )
    if not (attribution or "").strip():
        raise LicenceHorsSocleError(
            f"Source « {code} » sans attribution : l'attribution est une obligation par "
            "enregistrement (CA1), une source sans mention n'entre pas au registre."
        )

    source = get_source(db, code)
    if source is None:
        source = ReferentielSource(code=code.strip())
        db.add(source)

    source.libelle = libelle
    source.licence = licence.strip()
    source.attribution = attribution.strip()
    source.url = url
    source.partageable = partageable
    source.importee = importee
    db.commit()
    return source


def semer_sources_socle(db: Session) -> list[ReferentielSource]:
    """
    [CA1, CA3] Garantit la présence des quatre origines du socle au registre.

    Utile hors PostgreSQL (tests SQLite construits depuis `database/models.py`,
    qui ne rejouent jamais les migrations) et comme filet en tête d'import : une
    donnée ne peut pas être rattachée à une source absente du registre.
    Idempotent.
    """
    return [enregistrer_source(db, **fiche) for fiche in SOURCES_SOCLE]


def garantir_source(db: Session, code: str) -> ReferentielSource:
    """
    [CA3] Retourne une origine du socle, en la créant si le registre ne la porte
    pas encore.

    Sert les chemins d'écriture applicatifs — la correction d'une famille au bot
    doit pouvoir s'attribuer `saisie_manuelle` sans supposer qu'une migration a
    déjà tourné, ni qu'un import a eu lieu. Lève `KeyError` si le code n'est pas
    une origine du socle : c'est un défaut d'appel, pas une donnée à créer à la
    volée.
    """
    source = get_source(db, code)
    if source is not None:
        return source
    fiche = next((f for f in SOURCES_SOCLE if f["code"] == code), None)
    if fiche is None:
        raise KeyError(code)
    return enregistrer_source(db, **fiche)


def marquer_import(db: Session, code: str, horodatage: Optional[datetime] = None) -> ReferentielSource:
    """[CA1] Date le dernier import réussi d'une source. Lève LookupError si inconnue."""
    source = get_source(db, code)
    if source is None:
        raise LookupError(code)
    source.date_dernier_import = horodatage or datetime.now()
    db.commit()
    return source


def donnees_derivees(db: Session, code: str) -> list[dict]:
    """
    [CA4] Tout ce qui dérive d'une source, **en une requête**.

    C'est la réponse opérationnelle à « cette source devient litigieuse, que
    faut-il retirer ? ». Le balayage est piloté par `TABLES_RATTACHEES` et
    assemblé en un seul `UNION ALL` : ajouter une table du référentiel (US-161,
    US-162, US-163) se fait en ajoutant une ligne à ce tuple, sans toucher à
    l'appelant ni multiplier les allers-retours en base.

    Retourne une liste de dicts `{table, colonne, id, libelle}`, triée par table
    puis par identifiant. Liste vide si la source est inconnue au registre —
    aucune donnée ne peut dériver d'une source qui n'y figure pas.
    """
    source = get_source(db, code)
    if source is None:
        return []

    fragments = [
        f"SELECT '{table}' AS table_cible, '{colonne}' AS colonne, "
        f"id AS id_ligne, {libelle} AS libelle FROM {table} WHERE {colonne} = :source_id"
        for table, colonne, libelle in TABLES_RATTACHEES
    ]
    requete = " UNION ALL ".join(fragments) + " ORDER BY table_cible, id_ligne"
    lignes = db.execute(text(requete), {"source_id": source.id}).fetchall()
    return [
        {"table": t, "colonne": c, "id": i, "libelle": libelle}
        for t, c, i, libelle in lignes
    ]


def attribution_affichee(db: Session, code: str) -> Optional[str]:
    """[CA1] Mention à afficher pour une source, ou None si elle est inconnue."""
    source = get_source(db, code)
    return source.attribution if source is not None else None
