"""
tools/creer_cultures_referentiel.py — Création des fiches `culture_config` manquantes
-------------------------------------------------------------------------------------
L'import du référentiel (CA7 d'US-161/US-166) ne crée JAMAIS de culture : il rattache
seulement les cultures déjà présentes. Cet outil, volontairement séparé et lancé à la
main (hors chaîne de déploiement), crée les fiches globales (`potager_id` NULL) des
cultures citées par `wikidata_familles.json`, `attributs_redaction_interne.json` et
`calendrier_redaction_interne.json` absentes de `culture_config`, et les rattache à
leur famille (origine `wikidata`).

`culture_config.type_organe_recolte` est obligatoire et ne figure pas dans le JSON des
familles : il vient d'un fichier d'appoint relu par un humain
(`data/creation_cultures/types_organe.json`). Une culture sans type validé n'est
jamais créée.

Utilisation :
    python tools/creer_cultures_referentiel.py --generer-types   # pré-remplit le fichier d'appoint
    python tools/creer_cultures_referentiel.py --dry-run         # simule
    python tools/creer_cultures_referentiel.py                   # crée

Prérequis : les familles doivent exister (lancer d'abord l'import du référentiel).
Idempotent : une culture déjà présente (comparaison normalisée) n'est jamais touchée.
"""
import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.services.familles import normaliser_famille  # noqa: E402

MANIFESTE = RACINE / "data" / "referentiel" / "wikidata_familles.json"
ATTRIBUTS = RACINE / "data" / "referentiel" / "attributs_redaction_interne.json"
CALENDRIER = RACINE / "data" / "referentiel" / "calendrier_redaction_interne.json"
APPOINT = RACINE / "data" / "creation_cultures" / "types_organe.json"
TYPES = ("végétatif", "reproducteur")

# Pré-remplissage indicatif, À RELIRE : on récolte le fruit/la graine (la plante
# continue à produire) pour ces familles, le reste est détruit à la récolte.
FAMILLES_REPRODUCTRICES = {"cucurbitacee", "solanacee", "fabacee", "grossulariacee"}
REPRODUCTRICES_PAR_NOM = {"capucine", "bourrache", "souci", "fraisier", "framboisier"}


def _lire(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8"))


def _entrees() -> list[dict]:
    """Cultures citées par les manifestes du référentiel : {culture, famille|None}.

    La famille vient de wikidata_familles.json ; une culture que seuls les
    attributs ou le calendrier citent est créée sans famille (affichée « Autres »).
    """
    par_cle: dict[str, dict] = {}
    for e in _lire(MANIFESTE)["cultures_familles"]:
        nom = (e.get("culture") or "").strip()
        if nom:
            par_cle[normaliser_famille(nom)] = {"culture": nom, "famille": e.get("famille")}
    autres = (
        [e.get("culture") for e in _lire(ATTRIBUTS)["cultures_attributs"]]
        + [e.get("culture") for e in _lire(CALENDRIER)["cultures_calendriers"]]
    )
    for nom in autres:
        nom = (nom or "").strip()
        if nom and normaliser_famille(nom) not in par_cle:
            par_cle[normaliser_famille(nom)] = {"culture": nom, "famille": None}
    return list(par_cle.values())


def generer_types() -> int:
    """Écrit le fichier d'appoint pré-rempli, sans écraser une relecture existante."""
    entrees = _entrees()
    types: dict = {}
    if APPOINT.is_file():
        types = dict(json.loads(APPOINT.read_text(encoding="utf-8")).get("types", {}))
    for e in entrees:
        culture = e["culture"].strip()
        if culture in types:
            continue
        reproducteur = (
            normaliser_famille(e.get("famille") or "") in FAMILLES_REPRODUCTRICES
            or culture.lower() in REPRODUCTRICES_PAR_NOM
        )
        types[culture] = "reproducteur" if reproducteur else "végétatif"
    APPOINT.parent.mkdir(parents=True, exist_ok=True)
    APPOINT.write_text(
        json.dumps(
            {
                "_lisez_moi": [
                    "Type d'organe récolté des cultures créées par tools/creer_cultures_referentiel.py.",
                    "« végétatif » : la récolte détruit le plant ; « reproducteur » : la plante continue à produire.",
                    "Pré-rempli par famille : RELISEZ chaque ligne puis passez « a_relire » à false.",
                ],
                "a_relire": True,
                "types": types,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"✅ {APPOINT.relative_to(RACINE)} écrit ({len(types)} cultures). À relire, puis « a_relire »: false.")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(description="Crée les fiches culture_config manquantes")
    parser.add_argument("--dry-run", action="store_true", help="Simule, n'écrit rien")
    parser.add_argument("--generer-types", action="store_true", help="Pré-remplit le fichier d'appoint")
    args = parser.parse_args(argv)
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    if args.generer_types:
        return generer_types()

    # Imports tardifs : --generer-types ne doit pas exiger la configuration (.env).
    from app.services import referentiel_sources as svc_sources
    from database.db import SessionLocal
    from database.models import CultureConfig, FamilleBotanique
    from utils.culture_resolve import normaliser_culture

    if not APPOINT.is_file():
        print(f"❌ {APPOINT.relative_to(RACINE)} absent — lancez d'abord --generer-types", file=sys.stderr)
        return 2
    appoint = json.loads(APPOINT.read_text(encoding="utf-8"))
    if appoint.get("a_relire", True):
        print("❌ Fichier d'appoint non validé : relisez-le puis passez « a_relire » à false.", file=sys.stderr)
        return 2
    types = appoint.get("types", {})
    invalides = {c: t for c, t in types.items() if t not in TYPES}
    if invalides:
        print(f"❌ Types invalides (attendu {TYPES}) : {invalides}", file=sys.stderr)
        return 2

    entrees = _entrees()
    db = SessionLocal()
    try:
        source = svc_sources.garantir_source(db, "wikidata")
        familles = {f.nom_normalise: f for f in db.query(FamilleBotanique).all()}
        connues = {normaliser_culture(c.nom) for c in db.query(CultureConfig).all()}

        creees, sans_type, sans_famille = [], [], []
        for e in entrees:
            nom = (e.get("culture") or "").strip()
            cle = normaliser_culture(nom)
            if not nom or cle in connues:
                continue
            famille = None
            if e.get("famille"):
                famille = familles.get(normaliser_famille(e["famille"]))
                if famille is None:
                    sans_famille.append(nom)
                    continue
            if nom not in types:
                sans_type.append(nom)
                continue
            db.add(CultureConfig(
                nom=nom,
                type_organe_recolte=types[nom],
                potager_id=None,
                famille_id=famille.id if famille else None,
                famille_source_id=source.id if famille else None,
            ))
            connues.add(cle)
            creees.append(nom)

        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(f"{'[dry-run] ' if args.dry_run else ''}Cultures créées : {len(creees)}")
        for n in creees:
            print(f"  + {n} ({types[n]})")
        if sans_type:
            print(f"⚠️ Sans type dans l'appoint, non créées : {sans_type}")
        if sans_famille:
            print(f"⚠️ Famille absente de la base (lancez l'import du référentiel d'abord) : {sans_famille}")
        return 1 if (sans_type or sans_famille) else 0
    except Exception as err:
        db.rollback()
        print(f"❌ Création en échec : {err}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
