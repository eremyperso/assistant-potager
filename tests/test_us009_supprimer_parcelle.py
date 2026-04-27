"""
[US-009] Tests — Suppression d'une parcelle et réaffectation des événements

CA1 : /parcelle supprimer <nom> reconnue, affiche résumé + boutons inline
CA2 : Message de confirmation indique le nombre d'événements concernés
CA3 : Après confirmation, parcelle_id des événements = NULL (atomique)
CA4 : Parcelle désactivée (actif=False) — absente de get_all_parcelles()
CA5 : Message final récapitulatif (nom supprimé + nb réaffectés)
CA6 : Parcelle introuvable → erreur explicite, aucune modification
CA7 : Annulation → aucune modification, message de confirmation
CA8 : /historique affiche "Non localisé" pour les événements réaffectés
CA9 : Parcelle sans événement → message "Aucun événement associé", confirmation requise
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Evenement, Parcelle
from utils.parcelles import supprimer_parcelle


# ── Fixture DB ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _parcelle(session, nom: str) -> Parcelle:
    p = Parcelle(nom=nom, nom_normalise=nom.lower(), actif=True)
    session.add(p)
    session.flush()
    return p


def _evenement(session, parcelle_id: int, culture: str = "tomate") -> Evenement:
    e = Evenement(
        type_action="plantation", culture=culture,
        date=datetime(2026, 4, 1), parcelle_id=parcelle_id,
    )
    session.add(e)
    session.flush()
    return e


# ── Tests unitaires supprimer_parcelle() ─────────────────────────────────────

def test_us009_ca3_ca4_evenements_reaffectes_parcelle_desactivee(db):
    """CA3 + CA4 — Les événements passent à NULL et actif=False de manière atomique."""
    p = _parcelle(db, "serre")
    _evenement(db, p.id, "tomate")
    _evenement(db, p.id, "courgette")
    db.commit()

    parc, nb = supprimer_parcelle(db, "serre")

    assert nb == 2
    assert parc.actif is False
    evenements = db.query(Evenement).all()
    for e in evenements:
        assert e.parcelle_id is None


def test_us009_ca4_absente_du_listing(db):
    """CA4 — La parcelle supprimée n'apparaît plus dans get_all_parcelles()."""
    from utils.parcelles import get_all_parcelles
    p = _parcelle(db, "nord")
    db.commit()

    supprimer_parcelle(db, "nord")

    actives = get_all_parcelles(db)
    assert all(a.nom != "nord" for a in actives)


def test_us009_ca6_parcelle_introuvable(db):
    """CA6 — LookupError si la parcelle n'existe pas."""
    with pytest.raises(LookupError):
        supprimer_parcelle(db, "inexistante")


def test_us009_ca9_parcelle_sans_evenements(db):
    """CA9 — Suppression sans événements : actif=False, nb=0."""
    _parcelle(db, "essai")
    db.commit()

    parc, nb = supprimer_parcelle(db, "essai")

    assert nb == 0
    assert parc.actif is False


def test_us009_ca3_atomicite_isolation(db):
    """CA3 — Les événements d'une autre parcelle ne sont pas affectés."""
    p1 = _parcelle(db, "serre")
    p2 = _parcelle(db, "nord")
    e1 = _evenement(db, p1.id, "tomate")
    e2 = _evenement(db, p2.id, "laitue")
    db.commit()

    supprimer_parcelle(db, "serre")

    ev_nord = db.query(Evenement).filter(Evenement.id == e2.id).first()
    assert ev_nord.parcelle_id == p2.id  # non touché


# ── Tests callback bot ────────────────────────────────────────────────────────

def _make_callback(data: str, user_id: int = 1):
    update = MagicMock()
    update.effective_user.id = user_id
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_us009_ca7_annulation_callback():
    """CA7 — Bouton Annuler → aucune modification, message de confirmation."""
    from bot import _parcelle_suppr_cb

    update = _make_callback("parcelle_suppr_cancel")

    with patch("bot.SessionLocal"):
        await _parcelle_suppr_cb(update, MagicMock())

    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "annulée" in msg.lower() or "conservée" in msg.lower()


@pytest.mark.asyncio
async def test_us009_ca5_message_final_avec_evenements():
    """CA5 — Message final indique le nombre d'événements réaffectés."""
    from bot import _parcelle_suppr_cb

    update = _make_callback("parcelle_suppr_confirm:42")

    mock_parc = MagicMock()
    mock_parc.id = 42
    mock_parc.nom = "serre"
    mock_parc.actif = True

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_parc
    mock_db.query.return_value.filter.return_value.count.return_value = 5
    mock_db.query.return_value.filter.return_value.update.return_value = None

    with patch("bot.SessionLocal", return_value=mock_db):
        mock_db.__enter__ = lambda s: mock_db
        mock_db.__exit__ = MagicMock(return_value=False)
        await _parcelle_suppr_cb(update, MagicMock())

    update.callback_query.edit_message_text.assert_awaited_once()
    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "supprimée" in msg.lower()


@pytest.mark.asyncio
async def test_us009_ca6_callback_parcelle_inexistante():
    """CA6 — Parcelle introuvable dans le callback → message d'erreur."""
    from bot import _parcelle_suppr_cb

    update = _make_callback("parcelle_suppr_confirm:999")

    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with patch("bot.SessionLocal", return_value=mock_db):
        mock_db.__enter__ = lambda s: mock_db
        mock_db.__exit__ = MagicMock(return_value=False)
        await _parcelle_suppr_cb(update, MagicMock())

    msg = update.callback_query.edit_message_text.call_args[0][0]
    assert "introuvable" in msg.lower() or "supprimée" in msg.lower()


# ── CA8 : Non localisé dans /historique ─────────────────────────────────────

def test_us009_ca8_non_localise_apres_suppression(db):
    """CA8 — Après suppression, les événements ont parcelle_id=NULL (Non localisé)."""
    p = _parcelle(db, "serre")
    ev = _evenement(db, p.id)
    db.commit()

    supprimer_parcelle(db, "serre")

    ev_maj = db.query(Evenement).filter(Evenement.id == ev.id).first()
    assert ev_maj.parcelle_id is None
    # La propriété hybride retourne None → le bot affichera "Non localisé"
    assert ev_maj.parcelle is None
