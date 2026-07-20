"""
[fix bug id=355] Une mise en godet enregistrait nb_plants_godets et nb_graines_semees
tels quels, sans aucune vérification de cohérence — cas réel en production :
"mise en godet 30 fèves sur 5 graines" enregistré tel quel, affichant un taux de
réussite de 600% dans le récapitulatif (bot.py::_build_recap). Aucun scénario
légitime ne permet nb_plants_godets > nb_graines_semees (le taux de germination
ne peut pas dépasser 100%).
"""
import pytest

from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from app.services.evenements import TauxGerminationImpossibleError
from database.models import Evenement


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


def test_creer_evenement_godet_rejette_plus_de_plants_que_de_graines(test_db, ctx):
    """Reproduit le cas exact du bug id=355 : 30 plants repiqués pour 5 graines
    semées — doit être rejeté au lieu d'écrire un événement au taux de 600%."""
    parsed = {
        "culture": "feve", "variete": "Aguadulce",
        "nb_graines_semees": 5, "nb_plants_godets": 30,
    }
    with pytest.raises(TauxGerminationImpossibleError):
        svc_evenements.creer_evenement_godet(test_db, ctx, parsed, "mise en godet 30 fèves sur 5 graines")
    assert test_db.query(Evenement).count() == 0


def test_creer_evenement_godet_accepte_taux_normal(test_db, ctx):
    """Non-régression : un taux de réussite <= 100% reste accepté normalement."""
    parsed = {
        "culture": "feve", "variete": "Aguadulce",
        "nb_graines_semees": 10, "nb_plants_godets": 8,
    }
    event = svc_evenements.creer_evenement_godet(test_db, ctx, parsed, "mise en godet 8 fèves sur 10 graines")
    assert event.nb_graines_semees == 10
    assert event.nb_plants_godets == 8


def test_creer_evenement_godet_accepte_egalite(test_db, ctx):
    """100% de réussite (autant de plants que de graines) reste un cas limite valide."""
    parsed = {
        "culture": "feve", "variete": "Aguadulce",
        "nb_graines_semees": 5, "nb_plants_godets": 5,
    }
    event = svc_evenements.creer_evenement_godet(test_db, ctx, parsed, "mise en godet 5 fèves sur 5 graines")
    assert event.nb_plants_godets == 5
