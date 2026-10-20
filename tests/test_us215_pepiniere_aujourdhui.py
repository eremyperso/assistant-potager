"""[US-215] La donnée de la pastille d'une pépinière unique.

L'onglet « Aujourd'hui » a été retiré par US-218 (CA29) : son écran, sa lib et sa
page de contrôle n'existent plus, leurs garde-fous sont repris par
`tests/test_us218_pepiniere_parcours.py`. Reste ici ce qui survit : la superficie et
le type servis par `GET /pepiniere/lots` (CA2), que la barre de « Ma pépinière »
affiche toujours.
"""
from pathlib import Path

import pytest

from app.services import lots_pepiniere
from app.services.context import TenantContext
from database.models import Parcelle, Potager, User

RACINE = Path(__file__).resolve().parents[1]
SRC = RACINE / "frontend" / "src"
CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([Potager(id=1, nom="A", proprietaire_id=1), Potager(id=2, nom="B", proprietaire_id=2)])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True,
                 superficie_m2=2.5, type_pepiniere="chaude"),
        Parcelle(id=3, nom="chassis", nom_normalise="chassis", potager_id=2, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _lire(chemin: str) -> str:
    return (SRC / chemin).read_text(encoding="utf-8")


# ── CA2 — la pastille d'une pépinière unique ─────────────────────────────────

def test_us215_ca2_pepinieres_portent_superficie_et_type(db) -> None:
    """CA2 — superficie et type copiés pour la pastille, potager consulté seulement."""
    assert lots_pepiniere.pepinieres_du_potager(db, CTX) == [
        {"id": 2, "nom": "serre", "superficie_m2": 2.5, "type_pepiniere": "chaude"},
    ]


def test_us215_ca2_type_absent_rendu_vide(db) -> None:
    """CA2 / RT2 — un type non renseigné reste vide, jamais supposé."""
    serre = db.get(Parcelle, 2)
    serre.type_pepiniere = None
    serre.superficie_m2 = None
    db.commit()
    p = lots_pepiniere.pepinieres_du_potager(db, CTX)[0]
    assert p["type_pepiniere"] is None and p["superficie_m2"] is None
