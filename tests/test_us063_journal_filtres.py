"""
[US-063] Volet backend de la refonte de l'écran Journal.

Deux changements serveur seulement — le reste de l'US est frontend (la conformité
visuelle relève du rapport de validation aux trois résolutions, pas de pytest) :

1. `lister_evenements(action=...)` accepte plusieurs `type_action` séparés par des
   virgules. Les catégories de filtre de la maquette recouvrent en effet plusieurs
   actions réelles (« Pertes » = perte + perte_godet, « Entretien » = six valeurs).
   Filtrer côté client sur la page déjà chargée fausserait la pagination, calculée
   côté serveur : le filtre doit porter sur la requête.
2. `GET /historique` expose `nb_plants_godets` — une mise en godet ne renseigne pas
   `quantite`, son compte réel ne vit que dans ce champ.
"""
from datetime import datetime

import pytest

from app.services.context import TenantContext
from app.services.evenements import lister_evenements
from database.models import Evenement


POTAGER = 1
AUTRE_POTAGER = 2


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=POTAGER, role="owner")


def _evenement(db, type_action, *, culture="Tomate", potager_id=POTAGER, **champs):
    """Événement minimal : seuls les champs utiles au scénario sont renseignés."""
    event = Evenement(
        date=datetime(2026, 8, 18),
        type_action=type_action,
        culture=culture,
        potager_id=potager_id,
        **champs,
    )
    db.add(event)
    db.commit()
    return event


# ── CA3 — le filtre d'action accepte plusieurs types ─────────────────────────


def test_us063_lister_evenements_action_unique_inchangee(test_db, ctx):
    """[CA3] Une valeur seule filtre exactement comme avant la refonte."""
    _evenement(test_db, "recolte")
    _evenement(test_db, "arrosage")

    total, events = lister_evenements(test_db, ctx, action="recolte")

    assert total == 1
    assert [e.type_action for e in events] == ["recolte"]


def test_us063_lister_evenements_action_multiple(test_db, ctx):
    """[CA3] « Pertes » couvre perte ET perte_godet en un seul appel."""
    _evenement(test_db, "perte")
    _evenement(test_db, "perte_godet")
    _evenement(test_db, "recolte")

    total, events = lister_evenements(test_db, ctx, action="perte,perte_godet")

    assert total == 2
    assert {e.type_action for e in events} == {"perte", "perte_godet"}


def test_us063_lister_evenements_action_multiple_espaces_ignores(test_db, ctx):
    """[CA3] Les espaces autour des virgules ne cassent pas le filtre."""
    _evenement(test_db, "perte")
    _evenement(test_db, "perte_godet")

    total, _ = lister_evenements(test_db, ctx, action=" perte , perte_godet ")

    assert total == 2


def test_us063_lister_evenements_action_inconnue_ne_ramene_rien(test_db, ctx):
    """[CA3] Un type absent du potager ne remonte rien — jamais tout l'historique."""
    _evenement(test_db, "recolte")

    total, events = lister_evenements(test_db, ctx, action="type_inexistant")

    assert total == 0
    assert events == []


def test_us063_lister_evenements_action_vide_ne_filtre_pas(test_db, ctx):
    """[CA3] Une chaîne vide équivaut à « toutes les actions », pas à zéro résultat."""
    _evenement(test_db, "recolte")
    _evenement(test_db, "arrosage")

    total, _ = lister_evenements(test_db, ctx, action=",  ,")

    assert total == 2


def test_us063_filtre_multiple_reste_scope_au_potager(test_db, ctx):
    """[CA3] Le filtre multi-valeurs ne contourne pas le cloisonnement multi-tenant."""
    _evenement(test_db, "perte")
    _evenement(test_db, "perte_godet", potager_id=AUTRE_POTAGER)

    total, events = lister_evenements(test_db, ctx, action="perte,perte_godet")

    assert total == 1
    assert events[0].potager_id == POTAGER


# ── CA4 — la pagination reste calculée sur le filtre serveur ──────────────────


def test_us063_pagination_comptee_apres_filtre_multiple(test_db, ctx):
    """[CA4] `total` reflète le filtre, pas le nombre d'événements du potager.

    C'est la raison d'être du filtre multi-valeurs côté serveur : filtrer « Pertes »
    dans le navigateur aurait laissé `total` à 25 et affiché « Page 1 / 2 » pour
    3 résultats.
    """
    for _ in range(22):
        _evenement(test_db, "recolte")
    for _ in range(3):
        _evenement(test_db, "perte")

    total, events = lister_evenements(test_db, ctx, action="perte,perte_godet", limit=20)

    assert total == 3
    assert len(events) == 3


def test_us063_pagination_offset_sur_filtre_multiple(test_db, ctx):
    """[CA4] La seconde page d'un filtre multi-valeurs reprend bien la suite."""
    for _ in range(12):
        _evenement(test_db, "perte")
    for _ in range(12):
        _evenement(test_db, "perte_godet")

    total, page1 = lister_evenements(test_db, ctx, action="perte,perte_godet", limit=20, offset=0)
    _, page2 = lister_evenements(test_db, ctx, action="perte,perte_godet", limit=20, offset=20)

    assert total == 24
    assert len(page1) == 20
    assert len(page2) == 4
    assert {e.id for e in page1}.isdisjoint({e.id for e in page2})


# ── CA1 — le compte d'une mise en godet vit dans nb_plants_godets ─────────────


def test_us063_mise_en_godet_porte_son_compte_sur_nb_plants_godets(test_db, ctx):
    """[CA1] Une mise en godet a un compte exploitable même sans `quantite`.

    Sans ce champ, la phrase du journal se réduisait à « Mise en godet de courgette »
    alors que le lot comptait bien 20 godets.
    """
    _evenement(test_db, "mise_en_godet", culture="Courgette", quantite=None, nb_plants_godets=20)

    _, events = lister_evenements(test_db, ctx, action="mise_en_godet")

    assert events[0].quantite is None
    assert events[0].nb_plants_godets == 20
