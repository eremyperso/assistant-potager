"""
tests/test_us007_reassocier_culture.py — Tests US-007 : Réassocier une culture à une parcelle
-----------------------------------------------------------------------------------------------
Couverture :
  - CA1  : is_deplacer_request détecte les phrases de déplacement
  - CA2  : aucune plantation trouvée → message erreur + reset mode
  - CA3  : variété unique → saut de l'étape sélection variété
  - CA4  : plusieurs variétés → demande de sélection
  - CA5  : liste des parcelles affichée avec occupation
  - CA6  : parcelle inconnue acceptée (création automatique)
  - CA7  : récapitulatif avant confirmation
  - CA8  : UPDATE groupé + trace [DÉPL ...] dans texte_original
  - CA9  : annulation à tout moment reset le mode
  - CA10 : is_deplacer_request / extract_culture_deplacer
  - CA11 : culture non détectée → mode depl_culture_ask
"""
import pytest
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement, Parcelle
from utils.parcelles import normalize_parcelle_name
from utils.deplacer import is_deplacer_request, extract_culture_deplacer


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def engine():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=eng)
    return eng


@pytest.fixture
def db(engine):
    """Session de test avec remise à zéro entre tests."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def _seed_parcelle(db, nom: str, ordre: int = 1) -> Parcelle:
    p = Parcelle(
        nom=nom,
        nom_normalise=normalize_parcelle_name(nom),
        ordre=ordre,
        actif=True,
    )
    db.add(p)
    db.flush()
    return p


def _seed_plantation(db, culture: str, variete: str | None = None,
                     parcelle: Parcelle | None = None) -> Evenement:
    e = Evenement(
        type_action="plantation",
        culture=culture,
        variete=variete,
        quantite=3.0,
        unite="plants",
        parcelle_id=parcelle.id if parcelle else None,
        texte_original=f"plantation {culture}",
    )
    db.add(e)
    db.flush()
    return e


def _make_update():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    update.message.text = "oui"
    return update


def _make_ctx(mode=None, **extra):
    ctx = MagicMock()
    ctx.user_data = {"mode": mode}
    ctx.user_data.update(extra)
    return ctx


# ── Tests détection (utils/deplacer.py) ──────────────────────────────────────

class TestDetection:
    """[CA1, CA10] Tests des fonctions de détection — importées depuis utils.deplacer."""

    def test_is_deplacer_request_associer(self):
        assert is_deplacer_request("j'ai besoin d'associer ma zone tomate sur une nouvelle parcelle")

    def test_is_deplacer_request_deplacer(self):
        assert is_deplacer_request("déplacer mes carottes sur la parcelle nord")

    def test_is_deplacer_request_rattacher(self):
        assert is_deplacer_request("rattacher mes aubergines à la parcelle est")

    def test_is_deplacer_request_changer_parcelle(self):
        assert is_deplacer_request("changer de parcelle pour mes courgettes")

    def test_is_deplacer_request_reassocier(self):
        assert is_deplacer_request("réassocier mes tomates cerise à la parcelle serre")

    def test_is_deplacer_request_false_action_normale(self):
        """Une action potager normale ne doit pas être détectée comme déplacement."""
        assert not is_deplacer_request("planté des tomates dans la parcelle nord")

    def test_is_deplacer_request_false_recolte(self):
        assert not is_deplacer_request("récolté 2 kg de tomates")

    def test_is_deplacer_request_false_arrosage(self):
        assert not is_deplacer_request("arrosé les courgettes 30 minutes")

    def test_extract_culture_tomate(self):
        assert extract_culture_deplacer(
            "j'ai besoin d'associer ma zone tomate sur une nouvelle parcelle"
        ) == "tomate"

    def test_extract_culture_carottes(self):
        assert extract_culture_deplacer(
            "déplacer mes carottes sur la parcelle nord"
        ) == "carottes"

    def test_extract_culture_courgettes(self):
        assert extract_culture_deplacer(
            "rattacher mes courgettes à la serre"
        ) == "courgettes"

    def test_extract_culture_none_si_phrase_vague(self):
        """Phrase sans nom de culture → None ou mot vide."""
        result = extract_culture_deplacer("j'ai besoin d'associer sur une nouvelle parcelle")
        # "nouvelle" est un mot générique ignoré, "parcelle" aussi
        assert result is None or result in ("nouvelle", "sur", "une")


# ── Tests flux _depl_start ────────────────────────────────────────────────────

class TestDeplStart:
    """[CA2, CA3, CA4, CA11] Tests de _depl_start."""

    @pytest.mark.asyncio
    async def test_ca11_culture_none_demande_explicite(self):
        """[CA11] culture=None → mode depl_culture_ask."""
        from bot import _depl_start
        update = _make_update()
        ctx = _make_ctx()

        with patch("bot.SessionLocal") as MockSession:
            MockSession.return_value.__enter__ = MagicMock()
            await _depl_start(update, ctx, None)

        assert ctx.user_data.get("mode") == "depl_culture_ask"
        update.message.reply_text.assert_called_once()
        texte = update.message.reply_text.call_args[0][0]
        assert "culture" in texte.lower() or "déplacer" in texte.lower()

    @pytest.mark.asyncio
    async def test_ca2_aucune_plantation(self, db):
        """[CA2] Aucune plantation de la culture → message erreur + reset mode."""
        from bot import _depl_start

        update = _make_update()
        ctx = _make_ctx()

        with patch("bot.SessionLocal", return_value=db):
            await _depl_start(update, ctx, "basilic")

        assert ctx.user_data.get("mode") is None
        texte = update.message.reply_text.call_args[0][0]
        assert "basilic" in texte.lower()
        assert "❌" in texte or "aucune" in texte.lower()

    @pytest.mark.asyncio
    async def test_ca3_variete_unique_saut_etape(self, db):
        """[CA3] Une seule variété → passe directement à la liste des parcelles."""
        from bot import _depl_start

        _seed_plantation(db, "carotte", variete="Nantaise")
        db.commit()

        update = _make_update()
        ctx = _make_ctx()

        with patch("bot.SessionLocal", return_value=db), \
             patch("bot.get_all_parcelles", return_value=[]), \
             patch("bot.calcul_occupation_parcelles", return_value={}):
            await _depl_start(update, ctx, "carotte")

        # Mode doit être depl_parcelle_select (saut de l'étape variété)
        assert ctx.user_data.get("mode") == "depl_parcelle_select"
        assert ctx.user_data.get("depl_culture") == "carotte"

    @pytest.mark.asyncio
    async def test_ca4_plusieurs_varietes(self, db):
        """[CA4] Plusieurs variétés → demande de sélection."""
        from bot import _depl_start

        _seed_plantation(db, "tomate", variete="Cœur de Bœuf")
        _seed_plantation(db, "tomate", variete="Cerise")
        db.commit()

        update = _make_update()
        ctx = _make_ctx()

        with patch("bot.SessionLocal", return_value=db):
            await _depl_start(update, ctx, "tomate")

        assert ctx.user_data.get("mode") == "depl_variete_select"
        assert ctx.user_data.get("depl_culture") == "tomate"
        texte = update.message.reply_text.call_args[0][0]
        assert "variété" in texte.lower() or "variete" in texte.lower()


# ── Tests _depl_parcelle_select ───────────────────────────────────────────────

class TestDeplParcelleSelect:
    """[CA5, CA6, CA7] Tests de la sélection de parcelle."""

    @pytest.mark.asyncio
    async def test_ca7_recapitulatif_affiche(self, db):
        """[CA7] Récapitulatif culture/variété/parcelle/nb_records affiché."""
        from bot import _depl_parcelle_select

        parc = _seed_parcelle(db, "SERRE")
        _seed_plantation(db, "tomate", parcelle=parc)
        _seed_plantation(db, "tomate", parcelle=parc)
        db.commit()

        update = _make_update()
        ctx = _make_ctx(
            mode="depl_parcelle_select",
            depl_culture="tomate",
            depl_variete=None,
        )

        with patch("bot.SessionLocal", return_value=db), \
             patch("bot.resolve_parcelle", return_value=parc):
            await _depl_parcelle_select(update, ctx, "serre")

        assert ctx.user_data.get("mode") == "depl_confirm"
        texte = update.message.reply_text.call_args[0][0]
        assert "tomate" in texte.lower()
        assert "SERRE" in texte
        assert "plantation" in texte.lower()

    @pytest.mark.asyncio
    async def test_ca9_annulation_reset(self, db):
        """[CA9] Taper 'annuler' reset le mode."""
        from bot import _depl_parcelle_select

        update = _make_update()
        ctx = _make_ctx(mode="depl_parcelle_select", depl_culture="tomate", depl_variete=None)

        await _depl_parcelle_select(update, ctx, "annuler")

        assert ctx.user_data.get("mode") is None
        texte = update.message.reply_text.call_args[0][0]
        assert "annulé" in texte.lower()

    @pytest.mark.asyncio
    async def test_ca6_parcelle_inconnue_acceptee(self, db):
        """[CA6] Parcelle inconnue acceptée (mode depl_confirm atteint)."""
        from bot import _depl_parcelle_select

        _seed_plantation(db, "tomate")
        db.commit()

        update = _make_update()
        ctx = _make_ctx(mode="depl_parcelle_select", depl_culture="tomate", depl_variete=None)

        with patch("bot.SessionLocal", return_value=db), \
             patch("bot.resolve_parcelle", return_value=None):
            await _depl_parcelle_select(update, ctx, "nouvelle-zone")

        assert ctx.user_data.get("mode") == "depl_confirm"
        assert ctx.user_data.get("depl_parcelle_cible") == "nouvelle-zone"


# ── Tests _depl_confirm ────────────────────────────────────────────────────────

class TestDeplConfirm:
    """[CA8, CA9] Tests de la confirmation et de l'UPDATE."""

    @pytest.mark.asyncio
    async def test_ca8_update_groupe_et_trace(self, db):
        """[CA8] UPDATE groupé + trace [DÉPL ...] dans texte_original."""
        from bot import _depl_confirm

        parc_old = _seed_parcelle(db, "NORD")
        parc_new = _seed_parcelle(db, "SERRE")
        e1 = _seed_plantation(db, "tomate", parcelle=parc_old)
        e2 = _seed_plantation(db, "tomate", parcelle=parc_old)
        db.commit()

        update = _make_update()
        ctx = _make_ctx(
            mode="depl_confirm",
            depl_culture="tomate",
            depl_variete=None,
            depl_parcelle_cible="SERRE",
            depl_parcelle_cible_id=parc_new.id,
            depl_nb_records=2,
        )

        with patch("bot.SessionLocal", return_value=db):
            await _depl_confirm(update, ctx, "oui")

        # Vérifier la mise à jour en base
        db.expire_all()
        updated = db.query(Evenement).filter(Evenement.type_action == "plantation").all()
        for ev in updated:
            assert ev.parcelle_id == parc_new.id, f"Event {ev.id} non migré"
            assert "[DÉPL" in (ev.texte_original or ""), f"Trace manquante sur event {ev.id}"

        assert ctx.user_data.get("mode") is None
        assert ctx.user_data.get("depl_culture") is None

    @pytest.mark.asyncio
    async def test_ca8_update_filtre_par_variete(self, db):
        """[CA8] UPDATE doit cibler uniquement la variété choisie."""
        from bot import _depl_confirm

        parc_old = _seed_parcelle(db, "NORD")
        parc_new = _seed_parcelle(db, "EST")
        e_cerise = _seed_plantation(db, "tomate", variete="Cerise", parcelle=parc_old)
        e_coeur  = _seed_plantation(db, "tomate", variete="Coeur de Boeuf", parcelle=parc_old)
        db.commit()

        update = _make_update()
        ctx = _make_ctx(
            mode="depl_confirm",
            depl_culture="tomate",
            depl_variete="Cerise",
            depl_parcelle_cible="EST",
            depl_parcelle_cible_id=parc_new.id,
            depl_nb_records=1,
        )

        with patch("bot.SessionLocal", return_value=db):
            await _depl_confirm(update, ctx, "oui")

        db.expire_all()
        ev_cerise = db.get(Evenement, e_cerise.id)
        ev_coeur  = db.get(Evenement, e_coeur.id)

        assert ev_cerise.parcelle_id == parc_new.id
        assert "[DÉPL" in (ev_cerise.texte_original or "")
        assert ev_coeur.parcelle_id == parc_old.id  # non modifiée

    @pytest.mark.asyncio
    async def test_ca8_recolte_non_modifiee(self, db):
        """[CA8] Seuls les événements de type plantation sont modifiés, pas les récoltes."""
        from bot import _depl_confirm

        parc_old = _seed_parcelle(db, "NORD")
        parc_new = _seed_parcelle(db, "SUD")

        e_plant = _seed_plantation(db, "tomate", parcelle=parc_old)
        e_recolte = Evenement(
            type_action="recolte",
            culture="tomate",
            parcelle_id=parc_old.id,
            texte_original="récolte tomate",
        )
        db.add(e_recolte)
        db.commit()

        update = _make_update()
        ctx = _make_ctx(
            mode="depl_confirm",
            depl_culture="tomate",
            depl_variete=None,
            depl_parcelle_cible="SUD",
            depl_parcelle_cible_id=parc_new.id,
            depl_nb_records=1,
        )

        with patch("bot.SessionLocal", return_value=db):
            await _depl_confirm(update, ctx, "oui")

        db.expire_all()
        ev_plant   = db.get(Evenement, e_plant.id)
        ev_recolte = db.get(Evenement, e_recolte.id)

        assert ev_plant.parcelle_id == parc_new.id
        assert ev_recolte.parcelle_id == parc_old.id  # non modifiée

    @pytest.mark.asyncio
    async def test_ca9_non_annule(self, db):
        """[CA9] Répondre 'non' annule sans modifier la base."""
        from bot import _depl_confirm

        parc_old = _seed_parcelle(db, "NORD")
        parc_new = _seed_parcelle(db, "SUD")
        e = _seed_plantation(db, "tomate", parcelle=parc_old)
        db.commit()

        update = _make_update()
        ctx = _make_ctx(
            mode="depl_confirm",
            depl_culture="tomate",
            depl_variete=None,
            depl_parcelle_cible="SUD",
            depl_parcelle_cible_id=parc_new.id,
            depl_nb_records=1,
        )

        await _depl_confirm(update, ctx, "non")

        db.expire_all()
        ev = db.get(Evenement, e.id)
        assert ev.parcelle_id == parc_old.id  # non modifiée
        assert ctx.user_data.get("mode") is None

    @pytest.mark.asyncio
    async def test_ca6_nouvelle_parcelle_creee(self, db):
        """[CA6] Parcelle inconnue → créée automatiquement à la confirmation."""
        from bot import _depl_confirm

        e = _seed_plantation(db, "tomate")
        db.commit()

        update = _make_update()
        ctx = _make_ctx(
            mode="depl_confirm",
            depl_culture="tomate",
            depl_variete=None,
            depl_parcelle_cible="NOUVELLE-ZONE",
            depl_parcelle_cible_id=None,
            depl_nb_records=1,
        )

        with patch("bot.SessionLocal", return_value=db):
            await _depl_confirm(update, ctx, "oui")

        nouvelle = db.query(Parcelle).filter(
            Parcelle.nom_normalise == normalize_parcelle_name("NOUVELLE-ZONE")
        ).first()
        assert nouvelle is not None

        db.expire_all()
        ev = db.get(Evenement, e.id)
        assert ev.parcelle_id == nouvelle.id


# ── Tests _depl_variete_select ────────────────────────────────────────────────

class TestDeplVarieteSelect:
    """[CA4] Tests de la sélection de variété."""

    @pytest.mark.asyncio
    async def test_toutes_les_varietes(self):
        """'toutes' → depl_variete = None."""
        from bot import _depl_variete_select

        update = _make_update()
        ctx = _make_ctx(mode="depl_variete_select", depl_culture="tomate")

        with patch("bot.get_all_parcelles", return_value=[]), \
             patch("bot.calcul_occupation_parcelles", return_value={}), \
             patch("bot.SessionLocal"):
            await _depl_variete_select(update, ctx, "toutes")

        assert ctx.user_data.get("depl_variete") is None
        assert ctx.user_data.get("mode") == "depl_parcelle_select"

    @pytest.mark.asyncio
    async def test_variete_specifique(self):
        """Nom de variété → depl_variete = nom."""
        from bot import _depl_variete_select

        update = _make_update()
        ctx = _make_ctx(mode="depl_variete_select", depl_culture="tomate")

        with patch("bot.get_all_parcelles", return_value=[]), \
             patch("bot.calcul_occupation_parcelles", return_value={}), \
             patch("bot.SessionLocal"):
            await _depl_variete_select(update, ctx, "Cerise")

        assert ctx.user_data.get("depl_variete") == "Cerise"
        assert ctx.user_data.get("mode") == "depl_parcelle_select"

    @pytest.mark.asyncio
    async def test_annulation_reset(self):
        """'annuler' → reset du mode."""
        from bot import _depl_variete_select

        update = _make_update()
        ctx = _make_ctx(mode="depl_variete_select", depl_culture="tomate")

        await _depl_variete_select(update, ctx, "annuler")

        assert ctx.user_data.get("mode") is None
