"""
tools/creer_potager_test_rempli.py — Le potager rempli du jeu d'évaluation [US-336 / CA3]
=========================================================================================
Copie dans la base de TEST un potager rempli d'une autre base (par défaut le potager 33 « Potager de recette » de
`potager_dev`) : ses propriétés (ville, coordonnées, zone, plan), ses parcelles, ses gestes, son carnet, ses rappels
et ses itinéraires personnalisés. Rien d'autre : ni échanges, ni propositions, ni journaux, ni consommation.

* **la source n'est que lue** : transaction en lecture seule sur la base source ;
* **jamais sur une vraie base** : la cible doit avoir « test » dans son nom (SQLite accepté), comme le potager neuf ;
* **rejouable** : un second passage retrouve le compte et le potager d'évaluation, les vide, puis recopie.

Utilisation :
    $env:APP_ENV="test"; python tools/creer_potager_test_rempli.py
    python tools/creer_potager_test_rempli.py --source-env .env.dev --source-potager 33

Il affiche les numéros à passer au lanceur (`--potager-rempli`, `--utilisateur-rempli`).
"""
from __future__ import annotations

import argparse
import re
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from tools.creer_potager_test_neuf import BaseNonTestError  # noqa: E402

EMAIL = "eval-compagnon-rempli@test.invalid"
NOM_UTILISATEUR = "Jardinier d'évaluation (potager rempli)"
NOM_POTAGER = "Potager rempli d'évaluation"
SOURCE_ENV = ".env.dev"
SOURCE_POTAGER = 33

#: Propriétés du potager recopiées (la ville et les coordonnées font la météo ; la zone fait la saison).
CHAMPS_POTAGER = ("latitude", "longitude", "ville", "zone_climatique", "altitude", "plan", "compteur_lots",
                  "emprise_longueur_m", "emprise_largeur_m", "angle_deg", "orientation_nord")


@dataclass
class PotagerRempli:
    utilisateur_id: int
    potager_id: int
    cree: bool
    copie: dict = field(default_factory=dict)


def _lignes(source, table: str, potager_id: int, ordre: str = "id") -> list[dict]:
    from sqlalchemy import text

    return [dict(r._mapping) for r in source.execute(
        text(f'SELECT * FROM "{table}" WHERE potager_id = :p ORDER BY {ordre}'), {"p": potager_id})]


def _inserer(db, table_nom: str, valeurs: dict) -> int:
    from sqlalchemy import insert

    from database.models import Base

    from datetime import date, datetime

    from sqlalchemy import Date, DateTime

    table = Base.metadata.tables[table_nom]
    propres = {k: v for k, v in valeurs.items() if k in table.c and k != "id"}
    for k, v in list(propres.items()):  # une base SQLite rend ses dates en texte
        if isinstance(v, str) and isinstance(table.c[k].type, DateTime):
            propres[k] = datetime.fromisoformat(v)
        elif isinstance(v, str) and isinstance(table.c[k].type, Date):
            propres[k] = date.fromisoformat(v[:10])
    return db.execute(insert(table).values(**propres).returning(table.c.id)).scalar_one()


def _remapper_ids(texte: Optional[str], correspondance: dict[int, int]) -> Optional[str]:
    if not texte:
        return texte
    return re.sub(r"\d+", lambda m: str(correspondance.get(int(m.group(0)), m.group(0))), texte)


def copier(db, source, *, source_potager: int = SOURCE_POTAGER, email: str = EMAIL,
           url_base: Optional[str] = None) -> PotagerRempli:
    """Le potager rempli dans la base de test, recopié de `source` (connexion à la base source, lue seulement)."""
    from unittest.mock import patch

    from sqlalchemy import text

    from app.services import auth, mode_test, potagers
    from database.db import tenant_scope
    from database.models import Potager, User

    if not mode_test.base_de_test(url_base or str(db.get_bind().url)):
        raise BaseNonTestError("la base visée n'a pas « test » dans son nom : rien n'est créé, rien n'est vidé")

    origine = source.execute(text("SELECT * FROM potagers WHERE id = :p"), {"p": source_potager}).mappings().first()
    if origine is None:
        raise LookupError(f"potager {source_potager} absent de la base source")

    cree = False
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = auth.inscrire_utilisateur(db, email, secrets.token_urlsafe(24), nom=NOM_UTILISATEUR)
        user.email_verifie = True
        db.commit()
        cree = True
    potager = (db.query(Potager).filter(Potager.proprietaire_id == user.id, Potager.nom == NOM_POTAGER)
               .order_by(Potager.id).first())
    if potager is None:
        potager = potagers.creer_potager(db, user.id, NOM_POTAGER)
        cree = True
    for champ in CHAMPS_POTAGER:
        if champ in origine:
            setattr(potager, champ, origine[champ])
    db.commit()
    utilisateur_id, potager_id = user.id, potager.id

    copie: dict[str, int] = {}
    with patch.object(mode_test, "actif", lambda: True):
        with tenant_scope(potager_id):
            mode_test.remettre_a_zero(db, potager_id)
            db.expunge_all()

            parcelles: dict[int, int] = {}
            for p in _lignes(source, "parcelles", source_potager):
                parcelles[p["id"]] = _inserer(db, "parcelles", {**p, "potager_id": potager_id})
            copie["parcelles"] = len(parcelles)

            # Les gestes, dans l'ordre : un geste ne pointe que vers un geste plus ancien (origine des graines).
            evenements: dict[int, int] = {}
            for e in _lignes(source, "evenements", source_potager):
                e = {**e, "potager_id": potager_id,
                     "parcelle_id": parcelles.get(e.get("parcelle_id")),
                     "parcelle_origine_id": parcelles.get(e.get("parcelle_origine_id")),
                     "origine_graines_id": evenements.get(e.get("origine_graines_id"))}
                evenements[e["id"]] = _inserer(db, "evenements", e)
            for ancien, nouveau in evenements.items():
                brut = source.execute(text("SELECT source_evenement_ids FROM evenements WHERE id = :i"),
                                      {"i": ancien}).scalar()
                if brut:
                    db.execute(text("UPDATE evenements SET source_evenement_ids = :s WHERE id = :i"),
                               {"s": _remapper_ids(brut, evenements), "i": nouveau})
            copie["evenements"] = len(evenements)

            for f in _lignes(source, "carnet_faits", source_potager):
                _inserer(db, "carnet_faits", {**f, "potager_id": potager_id, "user_id": utilisateur_id})
            copie["carnet_faits"] = len(_lignes(source, "carnet_faits", source_potager))

            n_rappels = 0
            for r in _lignes(source, "rappels", source_potager):
                cible = {"evenement": evenements, "parcelle": parcelles}.get(r.get("cible_type") or "", {})
                _inserer(db, "rappels", {**r, "potager_id": potager_id, "user_id": utilisateur_id,
                                         "proposition_id": None, "cible_id": cible.get(r.get("cible_id"), None)})
                n_rappels += 1
            copie["rappels"] = n_rappels

            # Les itinéraires personnalisés : la culture et la source se retrouvent par leur nom, pas par leur numéro.
            n_iti = 0
            for i in _lignes(source, "itineraire_cultural", source_potager):
                nom_culture = source.execute(text("SELECT nom FROM culture_config WHERE id = :c"),
                                             {"c": i["culture_id"]}).scalar()
                code_source = source.execute(text("SELECT code FROM referentiel_source WHERE id = :s"),
                                             {"s": i["source_id"]}).scalar()
                culture_id = db.execute(text("SELECT id FROM culture_config WHERE nom = :n"), {"n": nom_culture}).scalar()
                source_id = db.execute(text("SELECT id FROM referentiel_source WHERE code = :c"),
                                       {"c": code_source}).scalar()
                if culture_id is None or source_id is None:
                    print(f"  ⚠️ itinéraire « {i['nom']} » de {nom_culture} non copié : culture ou source absente de la cible")
                    continue
                nouvel = _inserer(db, "itineraire_cultural", {**i, "potager_id": potager_id, "culture_id": culture_id,
                                                              "source_id": source_id})
                for table in ("fenetre_culturale", "duree_culturale"):
                    for ligne in source.execute(text(f'SELECT * FROM "{table}" WHERE itineraire_id = :i'),
                                                {"i": i["id"]}).mappings():
                        _inserer(db, table, {**dict(ligne), "itineraire_id": nouvel, "potager_id": potager_id,
                                             "source_id": source_id})
                n_iti += 1
            copie["itineraires"] = n_iti
            db.commit()
    return PotagerRempli(utilisateur_id, potager_id, cree, copie)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Crée le potager rempli du jeu d'évaluation (US-336)")
    parser.add_argument("--source-env", default=SOURCE_ENV, help=f"fichier .env de la base source (défaut : {SOURCE_ENV})")
    parser.add_argument("--source-potager", type=int, default=SOURCE_POTAGER, help="potager à copier (défaut : 33)")
    parser.add_argument("--email", default=EMAIL, help=f"compte d'évaluation (défaut : {EMAIL})")
    args = parser.parse_args(argv)

    from dotenv import dotenv_values
    from sqlalchemy import create_engine, text

    from database.db import SessionLocal

    url_source = dotenv_values(RACINE / args.source_env).get("DATABASE_URL")
    if not url_source:
        print(f"❌ DATABASE_URL absente de {args.source_env}", file=sys.stderr)
        return 2
    moteur_source = create_engine(url_source)
    db = SessionLocal()
    try:
        with moteur_source.connect() as source:
            if moteur_source.dialect.name == "postgresql":
                source.execute(text("SET TRANSACTION READ ONLY"))
            resultat = copier(db, source, source_potager=args.source_potager, email=args.email)
            source.rollback()
    except (BaseNonTestError, LookupError) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    finally:
        db.close()
        moteur_source.dispose()
    print(f"{'✅ créé' if resultat.cree else '♻️  recopié'} : utilisateur {resultat.utilisateur_id}, potager "
          f"{resultat.potager_id} — " + ", ".join(f"{k} {v}" for k, v in resultat.copie.items()))
    print(f"\nPour le lanceur :\n  --potager-rempli {resultat.potager_id} --utilisateur-rempli {resultat.utilisateur_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
