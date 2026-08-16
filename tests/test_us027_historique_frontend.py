"""
[US-027] Tests — Endpoint GET /historique paginé + filtres date/action.

Vérifie : structure {total, evenements}, pagination offset/limit, filtre action,
filtre dates from/to, état vide, champs par événement.

Note : CA3 (filtre culture client-side) et CA4 (chips UI) sont validés côté frontend.
"""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from fastapi.testclient import TestClient
from datetime import datetime

from database.models import Evenement, Parcelle


# ── Auth [US-044] : neutraliser get_current_user_ctx pour tous les tests ─────
# Ce fichier teste le contrat /historique, pas l'authentification (qui a ses
# propres tests dédiés) — chaque test instancie son propre TestClient(app)
# inline, donc l'override est posé une seule fois ici pour tout le module.

@pytest.fixture(autouse=True)
def _override_auth():
    from main import app, get_current_user_ctx
    from app.services.context import default_context
    app.dependency_overrides[get_current_user_ctx] = default_context
    yield
    app.dependency_overrides.pop(get_current_user_ctx, None)


# ── Factories ─────────────────────────────────────────────────────────────────

def _ev(id, type_action, culture, date="2026-05-15", quantite=None, unite=None, variete=None, parcelle_nom=None):
    e = MagicMock(spec=Evenement)
    e.id             = id
    e.type_action    = type_action
    e.culture        = culture
    e.variete        = variete
    e.quantite       = quantite
    e.unite          = unite
    e.date           = datetime.fromisoformat(date)
    e.traitement     = None
    e.texte_original = None
    # propriété parcelle simulée
    if parcelle_nom:
        p = MagicMock(spec=Parcelle)
        p.nom = parcelle_nom
        e.parcelle_rel = p
        type(e).parcelle = PropertyMock(return_value=parcelle_nom)
    else:
        e.parcelle_rel = None
        type(e).parcelle = PropertyMock(return_value=None)
    return e


EVENTS = [
    _ev(1, "plantation", "tomate",   "2026-05-25", quantite=14, unite="plants", parcelle_nom="planche-centrale"),
    _ev(2, "recolte",    "courgette","2026-05-20", quantite=500, unite="g"),
    _ev(3, "semis",      "carotte",  "2026-04-10"),
]


def _mock_query(events, total=None):
    """Retourne un mock de query SQLAlchemy."""
    q = MagicMock()
    q.options.return_value = q
    q.order_by.return_value = q
    q.filter.return_value = q
    q.join.return_value = q
    q.count.return_value = total if total is not None else len(events)
    q.offset.return_value = q
    q.limit.return_value = q
    q.__iter__ = lambda self: iter(events)
    q.all.return_value = events
    return q


# ── CA1 : structure {total, evenements} ───────────────────────────────────────

def test_us027_ca1_structure_reponse():
    """CA1 — /historique retourne {total: int, evenements: [...]}."""
    from main import app
    db_mock = MagicMock()
    db_mock.query.return_value = _mock_query(EVENTS[:2], total=2)
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            resp = c.get("/historique")
    assert resp.status_code == 200
    body = resp.json()
    assert "total"      in body
    assert "evenements" in body
    assert isinstance(body["evenements"], list)


def test_us027_ca1_champs_par_evenement():
    """CA1 — Chaque événement a date, type_action, culture, variete, quantite, unite, parcelle."""
    from main import app
    db_mock = MagicMock()
    db_mock.query.return_value = _mock_query([EVENTS[0]], total=1)
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            body = c.get("/historique").json()
    ev = body["evenements"][0]
    for field in ("id", "date", "type_action", "culture", "variete", "quantite", "unite", "parcelle"):
        assert field in ev, f"Champ manquant : {field}"


# ── CA2 : pagination offset/limit ─────────────────────────────────────────────

def test_us027_ca2_pagination_offset():
    """CA2 — offset et limit passés en query param sont appliqués."""
    from main import app
    db_mock = MagicMock()
    q = _mock_query(EVENTS[1:], total=3)
    db_mock.query.return_value = q
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            resp = c.get("/historique?limit=20&offset=20")
    assert resp.status_code == 200
    q.offset.assert_called_with(20)
    q.limit.assert_called_with(20)


def test_us027_ca2_total_retourne():
    """CA2 — total reflète le nombre total avant pagination."""
    from main import app
    db_mock = MagicMock()
    db_mock.query.return_value = _mock_query(EVENTS[:1], total=45)
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            body = c.get("/historique").json()
    assert body["total"] == 45


# ── CA4 : filtre action côté serveur ──────────────────────────────────────────

def test_us027_ca4_filtre_action():
    """CA4 — ?action=recolte filtre les événements par type_action."""
    from main import app
    db_mock = MagicMock()
    q = _mock_query([EVENTS[1]], total=1)
    db_mock.query.return_value = q
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            resp = c.get("/historique?action=recolte")
    assert resp.status_code == 200
    q.filter.assert_called()


# ── CA5 : filtre dates from/to ────────────────────────────────────────────────

def test_us027_ca5_filtre_from_date():
    """CA5 — ?from=2026-05-01 filtre les événements à partir de cette date."""
    from main import app
    db_mock = MagicMock()
    q = _mock_query(EVENTS[:2], total=2)
    db_mock.query.return_value = q
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            resp = c.get("/historique?from=2026-05-01")
    assert resp.status_code == 200
    q.filter.assert_called()


def test_us027_ca5_filtre_to_date():
    """CA5 — ?to=2026-05-31 filtre les événements jusqu'à cette date."""
    from main import app
    db_mock = MagicMock()
    q = _mock_query(EVENTS[:1], total=1)
    db_mock.query.return_value = q
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            resp = c.get("/historique?to=2026-05-31")
    assert resp.status_code == 200
    q.filter.assert_called()


# ── CA7 : état vide ───────────────────────────────────────────────────────────

def test_us027_ca7_vide():
    """CA7 — Aucun événement → evenements=[], total=0."""
    from main import app
    db_mock = MagicMock()
    db_mock.query.return_value = _mock_query([], total=0)
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            body = c.get("/historique").json()
    assert body["evenements"] == []
    assert body["total"] == 0


# ── Parcelle présente dans la réponse ─────────────────────────────────────────

def test_us027_parcelle_dans_reponse():
    """CA1 — Le nom de parcelle est retourné via la relation ORM."""
    from main import app
    db_mock = MagicMock()
    db_mock.query.return_value = _mock_query([EVENTS[0]], total=1)
    with patch("main.SessionLocal", return_value=db_mock):
        with TestClient(app) as c:
            body = c.get("/historique").json()
    ev = body["evenements"][0]
    assert ev["parcelle"] == "planche-centrale"
