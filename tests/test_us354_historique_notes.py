"""
[US-354 / CA7] GET /historique rend le texte des notes (`commentaire`) et le rang.

Le Journal regroupe les notes du jour et montre la première en Kalam : il lui faut le texte que le
jardinier a dicté ou écrit. Jusqu'ici l'endpoint ne le renvoyait pas. Lecture seule : aucune
migration, aucune route nouvelle, aucun filtre ajouté.
"""
from datetime import datetime
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from fastapi.testclient import TestClient

from database.models import Evenement, Parcelle


@pytest.fixture(autouse=True)
def _override_auth():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context
    app.dependency_overrides[get_current_user_ctx] = default_context
    yield
    app.dependency_overrides.pop(get_current_user_ctx, None)


def _evenement(id, type_action, commentaire=None, rang=None, parcelle="Planche centrale"):
    e = MagicMock(spec=Evenement)
    e.id = id
    e.type_action = type_action
    e.culture = "fève"
    e.variete = None
    e.quantite = None
    e.unite = None
    e.nb_plants_godets = None
    e.traitement = None
    e.commentaire = commentaire
    e.rang = rang
    e.date = datetime.fromisoformat("2026-11-23")
    p = MagicMock(spec=Parcelle)
    p.nom = parcelle
    e.parcelle_rel = p
    type(e).parcelle = PropertyMock(return_value=parcelle)
    return e


def _lire(evenements):
    from app.api.main import app
    with patch("app.api.main.svc_evenements.lister_evenements", return_value=(len(evenements), evenements)):
        return TestClient(app).get("/historique").json()


def test_une_note_rend_son_texte():
    r = _lire([_evenement(1, "observation", commentaire="Les fèves pointent sur tout le rang.")])
    assert r["evenements"][0]["commentaire"] == "Les fèves pointent sur tout le rang."


def test_une_note_sans_texte_rend_null_et_un_geste_rend_son_rang():
    r = _lire([_evenement(1, "observation", commentaire=None), _evenement(2, "recolte", rang=3)])
    assert r["evenements"][0]["commentaire"] is None
    assert r["evenements"][1]["rang"] == 3


def test_les_champs_d_origine_restent_servis():
    r = _lire([_evenement(1, "paillage")])
    ev = r["evenements"][0]
    for cle in ("id", "date", "type_action", "culture", "variete", "quantite", "unite", "nb_plants_godets", "parcelle", "traitement"):
        assert cle in ev, cle
