"""
tests/test_us167_avertissement_plantation.py
[US-167] Avertir d'un conflit de rotation ou d'association au moment de la
plantation

Couverture des critères d'acceptance CA1 → CA13 (backlog/US-167_...).

CA11 (temps de réponse mesuré sur la production, pas en test) reste hors de
portée d'un test pytest — même exception que posée par
tests/test_us163_associations_rotation.py pour la mesure de performance.

Le canal « interface web » (CA1) est couvert via POST /parse, qui partage
avec POST /voice le même chemin d'écriture (`creer_evenement_depuis_parse`)
et le même câblage d'avertissement — un test dupliqué sur /voice n'aurait
rien couvert de plus.
"""
import socket
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import associations as svc_associations
from app.services import avertissements_plantation as svc_avert
from app.services import familles as svc_familles
from app.services.context import TenantContext, default_context, set_current_context
from database.models import CultureConfig, Evenement, FamilleBotanique, Parcelle

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures et helpers (mêmes conventions que tests/test_us163_associations_rotation.py)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


def _seed_culture(db, nom, type_organe="reproducteur", potager_id=None, famille=None):
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    if famille is not None:
        cfg.famille_rel = famille
    db.add(cfg)
    db.commit()
    return cfg


def _seed_famille(db, nom, delai_retour_annees=None):
    famille = FamilleBotanique(
        nom=nom,
        nom_normalise=svc_familles.normaliser_famille(nom),
        delai_retour_annees=delai_retour_annees,
    )
    db.add(famille)
    db.commit()
    return famille


def _seed_parcelle(db, nom, potager_id=1):
    parcelle = Parcelle(nom=nom, nom_normalise=nom.lower(), potager_id=potager_id)
    db.add(parcelle)
    db.commit()
    return parcelle


def _seed_evenement(db, parcelle, culture, annee, potager_id=1, type_action="plantation", texte_original=None):
    evt = Evenement(
        date=datetime(annee, 5, 1),
        type_action=type_action,
        culture=culture,
        parcelle_id=parcelle.id,
        potager_id=potager_id,
        texte_original=texte_original,
    )
    db.add(evt)
    db.commit()
    return evt


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA5 — conflit de rotation avéré, message qui cite la cause
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1CA5ConflitRotation:
    def test_conflit_de_rotation_cite_culture_famille_et_delai(self, db):
        """[Gherkin: Conflit de rotation signalé sans blocage]"""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "tomate", annee=2025)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "poivron", campagne_reference=2026
        )

        assert len(messages) == 1
        assert "tomate" in messages[0]
        assert "Solanacée" in messages[0]
        assert "3" in messages[0]
        assert messages[0].startswith("⚠️")


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — silence quand il n'y a positivement rien à signaler
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4SilenceSansConflit:
    def test_aucun_message_si_delai_de_retour_respecte(self, db):
        """[Gherkin: Aucun message quand il n'y a rien à dire]"""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "tomate", annee=2020)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "poivron", campagne_reference=2026
        )

        assert messages == []

    def test_association_favorable_ne_produit_aucun_message(self, db):
        """Seule une association 'défavorable' avertit — favorable/neutre restent muettes."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        lamiacee = _seed_famille(db, "Lamiacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "basilic", famille=lamiacee)
        svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_FAVORABLE,
            "repousse les pucerons", svc_associations.NIVEAU_ETABLI,
        )
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "basilic", annee=2026)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "tomate", campagne_reference=2026
        )

        assert messages == []


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — parcelle sans antécédent connu
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6ParcelleSansAntecedent:
    def test_parcelle_sans_evenement_indique_l_absence_d_antecedent(self, db):
        """[Gherkin: Parcelle sans antécédent] — jamais 'aucun conflit'."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        ouest = _seed_parcelle(db, "OUEST")

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, ouest.id, "tomate", campagne_reference=2026
        )

        assert len(messages) == 1
        assert "antécédent" in messages[0]
        assert "absence de conflit" in messages[0]
        assert messages[0].startswith("ℹ️")


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — famille sans délai de retour renseigné
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7FamilleSansDelaiRetour:
    def test_evaluation_indisponible_si_delai_non_renseigne(self, db):
        """[Gherkin: Famille sans délai de retour]"""
        lamiacee = _seed_famille(db, "Lamiacée", delai_retour_annees=None)
        _seed_culture(db, "basilic", famille=lamiacee)
        nord = _seed_parcelle(db, "NORD")

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "basilic", campagne_reference=2026
        )

        assert len(messages) == 1
        assert "indisponible" in messages[0]
        assert "n'affirme pas" in messages[0]


# ═════════════════════════════════════════════════════════════════════════════
# CA8, CA9 — conflit d'association avec une culture voisine (même parcelle,
# même campagne)
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8CA9ConflitAssociation:
    def test_association_defavorable_etablie_meme_parcelle_meme_campagne(self, db):
        fabacee = _seed_famille(db, "Fabacée", delai_retour_annees=3)
        amaryllidacee = _seed_famille(db, "Amaryllidacée", delai_retour_annees=3)
        _seed_culture(db, "haricot", famille=fabacee)
        _seed_culture(db, "ail", famille=amaryllidacee)
        svc_associations.enregistrer_association(
            db, "haricot", "ail", svc_associations.NATURE_DEFAVORABLE,
            "inhibition de croissance", svc_associations.NIVEAU_ETABLI,
        )
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "ail", annee=2026)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "haricot", campagne_reference=2026
        )

        assert len(messages) == 1
        assert "ail" in messages[0]
        assert "défavorable" in messages[0]

    def test_association_traditionnelle_formulation_differenciee(self, db):
        """[Gherkin: Association traditionnelle] — formulation distincte d'une
        relation établie (US-163/CA3)."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        cucurbitacee = _seed_famille(db, "Cucurbitacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "courgette", famille=cucurbitacee)
        svc_associations.enregistrer_association(
            db, "tomate", "courgette", svc_associations.NATURE_DEFAVORABLE,
            "concurrence pour l'espace", svc_associations.NIVEAU_TRADITIONNEL,
        )
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "courgette", annee=2026)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "tomate", campagne_reference=2026
        )

        assert len(messages) == 1
        assert "déconseillé par la pratique traditionnelle" in messages[0]

    def test_campagne_differente_n_est_pas_une_voisine(self, db):
        """[CA9] Le grain est la campagne : une culture d'une autre année sur
        la même parcelle n'est pas une 'voisine' d'association."""
        fabacee = _seed_famille(db, "Fabacée", delai_retour_annees=3)
        amaryllidacee = _seed_famille(db, "Amaryllidacée", delai_retour_annees=3)
        _seed_culture(db, "haricot", famille=fabacee)
        _seed_culture(db, "ail", famille=amaryllidacee)
        svc_associations.enregistrer_association(
            db, "haricot", "ail", svc_associations.NATURE_DEFAVORABLE,
            "inhibition de croissance", svc_associations.NIVEAU_ETABLI,
        )
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "ail", annee=2024)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "haricot", campagne_reference=2026
        )

        assert messages == []


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — culture inconnue du référentiel, parcelle non identifiée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA12EntreesNonExploitables:
    def test_culture_totalement_inconnue_ne_produit_aucun_avertissement(self, db):
        """[Gherkin: Culture inconnue du référentiel] — cas réel de production :
        la culture fantôme 'radi', née d'un échec de parsing (notes techniques)."""
        nord = _seed_parcelle(db, "NORD")

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "radi", campagne_reference=2026
        )

        assert messages == []

    def test_parcelle_non_identifiee_ne_produit_aucun_avertissement(self, db):
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, None, "tomate", campagne_reference=2026
        )

        assert messages == []

    def test_culture_vide_ne_produit_aucun_avertissement(self, db):
        nord = _seed_parcelle(db, "NORD")

        messages = svc_avert.evaluer_avertissements_plantation(
            db, CTX, nord.id, "", campagne_reference=2026
        )

        assert messages == []


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — zéro jeton, aucun appel réseau ni modèle
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10ZeroJeton:
    def test_aucun_appel_reseau(self, db, monkeypatch):
        """[Gherkin: Aucun jeton consommé] Toute tentative de sortie réseau fait
        échouer le test — même garde que TestCA11AucunAppelModele d'US-163."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à l'évaluation d'avertissement (CA10)")

        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "tomate", annee=2025)

        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        svc_avert.evaluer_avertissements_plantation(db, CTX, nord.id, "poivron", campagne_reference=2026)

    def test_n_appelle_pas_la_passerelle_llm(self, db):
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")

        with patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            svc_avert.evaluer_avertissements_plantation(db, CTX, nord.id, "tomate", campagne_reference=2026)

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2, CA3 — intégration bot.py : ordre des messages, jamais bloquant,
# aucun nouvel état conversationnel
# ═════════════════════════════════════════════════════════════════════════════

class TestBotIntegrationDoSaveItems:
    """[_do_save_items] Chemin confirmé (US-021) — un seul point d'écriture
    pour toutes les actions confirmées par callback."""

    @pytest.mark.asyncio
    async def test_avertissement_envoye_apres_la_confirmation_avant_next_steps(self):
        """[CA1, CA3] L'avertissement suit la confirmation d'enregistrement et
        précède le message 'Que voulez-vous faire ensuite ?' — jamais l'inverse,
        jamais un nouvel état conversationnel (pas de reply_markup dessus)."""
        import bot as bot_module

        fake_event = MagicMock(id=1, parcelle_id=42)
        update = MagicMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        items = [{"action": "plantation", "culture": "poivron", "quantite": 5,
                  "unite": "plants", "parcelle": "NORD"}]

        set_current_context(CTX)
        try:
            with (
                patch("bot.SessionLocal"),
                patch("bot.resolve_parcelle", return_value=MagicMock(id=42)),
                patch("bot.svc_evenements.creer_evenement_confirme", return_value=fake_event),
                patch("bot.svc_avertissements.evaluer_avertissements_plantation",
                      return_value=["⚠️ conflit de rotation test"]),
            ):
                await bot_module._do_save_items(update, items, "planté 5 poivrons parcelle nord")
        finally:
            set_current_context(default_context())

        calls = update.effective_message.reply_text.call_args_list
        textes = [c.args[0] for c in calls]
        idx_avert = next(i for i, t in enumerate(textes) if "conflit de rotation test" in t)
        # Le récapitulatif d'un item unique contient lui-même la phrase décorative
        # "Que voulez-vous faire ensuite ?" — seul le VRAI prompt de suite porte
        # le clavier (AFTER_RECORD_KEYBOARD), c'est lui qui doit venir après.
        idx_next = next(i for i, c in enumerate(calls) if c.kwargs.get("reply_markup") is not None)
        assert idx_avert < idx_next

        # [CA3] Un simple message, jamais un clavier/callback attaché à l'avertissement.
        avert_call = calls[idx_avert]
        assert avert_call.kwargs.get("reply_markup") is None

    @pytest.mark.asyncio
    async def test_sans_conflit_aucun_message_supplementaire(self):
        """[CA4] Pas d'avertissement à envoyer → aucun message de plus que
        d'habitude (recap + prochaine étape, rien d'autre)."""
        import bot as bot_module

        fake_event = MagicMock(id=1, parcelle_id=42)
        update = MagicMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        items = [{"action": "plantation", "culture": "poivron", "quantite": 5,
                  "unite": "plants", "parcelle": "NORD"}]

        set_current_context(CTX)
        try:
            with (
                patch("bot.SessionLocal"),
                patch("bot.resolve_parcelle", return_value=MagicMock(id=42)),
                patch("bot.svc_evenements.creer_evenement_confirme", return_value=fake_event),
                patch("bot.svc_avertissements.evaluer_avertissements_plantation", return_value=[]),
            ):
                await bot_module._do_save_items(update, items, "planté 5 poivrons parcelle nord")
        finally:
            set_current_context(default_context())

        assert update.effective_message.reply_text.call_count == 2

    @pytest.mark.asyncio
    async def test_action_hors_perimetre_n_evalue_aucun_avertissement(self):
        """[CA1] Seules plantation/semis déclenchent l'évaluation — un arrosage
        n'appelle même pas `evaluer_avertissements_plantation`."""
        import bot as bot_module

        fake_event = MagicMock(id=1, parcelle_id=42)
        update = MagicMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        items = [{"action": "arrosage", "culture": "poivron", "duree_minutes": 10, "parcelle": "NORD"}]

        set_current_context(CTX)
        try:
            with (
                patch("bot.SessionLocal"),
                patch("bot.resolve_parcelle", return_value=MagicMock(id=42)),
                patch("bot.svc_evenements.creer_evenement_confirme", return_value=fake_event),
                patch("bot.svc_avertissements.evaluer_avertissements_plantation") as mock_eval,
            ):
                await bot_module._do_save_items(update, items, "arrosé 10 min parcelle nord")
        finally:
            set_current_context(default_context())

        mock_eval.assert_not_called()

    @pytest.mark.asyncio
    async def test_evenement_toujours_enregistre_malgre_le_conflit(self):
        """[CA2] L'avertissement n'empêche jamais l'enregistrement."""
        import bot as bot_module

        fake_event = MagicMock(id=1, parcelle_id=42)
        update = MagicMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        items = [{"action": "plantation", "culture": "poivron", "quantite": 5,
                  "unite": "plants", "parcelle": "NORD"}]

        set_current_context(CTX)
        try:
            with (
                patch("bot.SessionLocal"),
                patch("bot.resolve_parcelle", return_value=MagicMock(id=42)),
                patch("bot.svc_evenements.creer_evenement_confirme", return_value=fake_event) as mock_creer,
                patch("bot.svc_avertissements.evaluer_avertissements_plantation",
                      return_value=["⚠️ conflit"]),
            ):
                await bot_module._do_save_items(update, items, "planté 5 poivrons parcelle nord")
        finally:
            set_current_context(default_context())

        mock_creer.assert_called_once()


class TestBotIntegrationParseMulti:
    """[_parse_multi] Sauvegarde directe multi-lignes, sans confirmation —
    second point de sauvegarde du bot, doit lui aussi déclencher l'avertissement."""

    @pytest.mark.asyncio
    async def test_avertissement_envoye_pour_un_semis_direct(self):
        import bot as bot_module

        fake_event = MagicMock(id=1, parcelle_id=42)
        update = MagicMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        parsed_item = {"action": "semis", "culture": "carotte", "quantite": 10,
                        "unite": "graines", "parcelle": "NORD"}

        set_current_context(CTX)
        try:
            with (
                patch("bot.require_role"),
                patch("bot._parser_items", return_value=[parsed_item]),
                patch("bot._normalize_items", return_value=[parsed_item]),
                patch("utils.validation.strip_culture_hallucinee", side_effect=lambda item, ligne: item),
                patch("bot.SessionLocal"),
                patch("bot.svc_evenements.creer_evenement_ligne", return_value=fake_event),
                patch("bot.svc_evenements.compter_evenements", return_value=1),
                patch("bot.svc_avertissements.evaluer_avertissements_plantation",
                      return_value=["ℹ️ pas d'antécédent test"]),
            ):
                await bot_module._parse_multi(update, ["semis 10 graines de carotte parcelle nord"])
        finally:
            set_current_context(default_context())

        calls = update.message.reply_text.call_args_list
        textes = [c.args[0] for c in calls]
        assert any("pas d'antécédent test" in t for t in textes)
        idx_avert = next(i for i, t in enumerate(textes) if "pas d'antécédent test" in t)
        idx_next = next(i for i, c in enumerate(calls) if c.kwargs.get("reply_markup") is not None)
        assert idx_avert < idx_next


# ═════════════════════════════════════════════════════════════════════════════
# Régression — bug d'auto-référence constaté en production le 02/09/2026
# ═════════════════════════════════════════════════════════════════════════════
#
# Évaluer APRÈS l'écriture faisait retrouver l'événement tout juste créé dans
# sa propre requête d'historique de parcelle : une première plantation de
# tomate sur une parcelle sans aucun autre antécédent se voyait citée comme
# « déjà présente cette année » — elle-même. Ces tests exercent le VRAI
# chemin (fonctions réelles, pas de mock sur `evaluer_avertissements_plantation`
# ni sur `resolve_parcelle`/`creer_evenement_confirme`) : seuls les tests
# service-layer plus haut, qui appellent `evaluer_avertissements_plantation`
# directement avec un historique déjà écrit, ne pouvaient PAS révéler ce bug
# — il n'existait que dans l'ORDRE d'appel côté bot.py/main.py.

class TestRegressionAutoReferenceProduction:
    @pytest.mark.asyncio
    async def test_premiere_plantation_sur_parcelle_vide_do_save_items(self, db):
        """[bot.py _do_save_items] Une plantation sans aucun antécédent réel ne
        doit jamais se citer elle-même comme conflit de rotation."""
        import bot as bot_module

        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_parcelle(db, "NORD")

        update = MagicMock()
        update.effective_message = AsyncMock()
        update.effective_message.reply_text = AsyncMock()

        items = [{"action": "plantation", "culture": "tomate", "quantite": 3,
                  "unite": "plants", "parcelle": "NORD"}]

        set_current_context(CTX)
        try:
            with patch("bot.SessionLocal", return_value=db):
                await bot_module._do_save_items(update, items, "planté 3 tomates parcelle nord")
        finally:
            set_current_context(default_context())

        textes = [c.args[0] for c in update.effective_message.reply_text.call_args_list]
        assert not any("Conflit de rotation" in t for t in textes)
        assert any("antécédent" in t for t in textes)

    @pytest.mark.asyncio
    async def test_premiere_plantation_sur_parcelle_vide_parse_multi(self, db):
        """[bot.py _parse_multi] Même garantie sur le second point d'écriture."""
        import bot as bot_module

        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_parcelle(db, "NORD")

        update = MagicMock()
        update.message = AsyncMock()
        update.message.reply_text = AsyncMock()

        parsed_item = {"action": "plantation", "culture": "tomate", "quantite": 3,
                        "unite": "plants", "parcelle": "NORD"}

        set_current_context(CTX)
        try:
            with (
                patch("bot.require_role"),
                patch("bot._parser_items", return_value=[parsed_item]),
                patch("bot._normalize_items", return_value=[parsed_item]),
                patch("utils.validation.strip_culture_hallucinee", side_effect=lambda item, ligne: item),
                patch("bot.SessionLocal", return_value=db),
            ):
                await bot_module._parse_multi(update, ["planté 3 tomates parcelle nord"])
        finally:
            set_current_context(default_context())

        textes = [c.args[0] for c in update.message.reply_text.call_args_list]
        assert not any("Conflit de rotation" in t for t in textes)
        assert any("antécédent" in t for t in textes)

    def test_premiere_plantation_sur_parcelle_vide_post_parse(self, db):
        """[main.py POST /parse] Même garantie sur le canal web."""
        from main import TexteRequest, parse as main_parse

        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_parcelle(db, "NORD")

        with (
            patch("main.add_to_rag", MagicMock()),
            patch("main.SessionLocal", return_value=db),
            patch("main.parse_commande", return_value=[{
                "action": "plantation", "culture": "tomate",
                "quantite": 3, "unite": "plants", "parcelle": "NORD",
            }]),
        ):
            data = main_parse(TexteRequest(texte="planté 3 tomates parcelle nord"), ctx=CTX)

        assert not any("Conflit de rotation" in m for m in data["avertissements"])
        assert any("antécédent" in m for m in data["avertissements"])


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — canal web (POST /parse) : mêmes garanties que le canal bot
# ═════════════════════════════════════════════════════════════════════════════

class TestApiParseCanalWeb:
    """Appelle `main.parse()` directement, comme une fonction Python normale,
    plutôt que via TestClient/HTTP : `/parse` est un handler FastAPI SYNCHRONE,
    donc exécuté par Starlette dans un thread de threadpool sous TestClient — un
    problème préexistant et sans rapport avec cette US fait qu'une nouvelle
    connexion SQLite `:memory:` y est alors invisible aux données déjà écrites
    par ce test (`tests/test_api.py` échoue de la même façon, avant comme après
    ce changement — voir l'historique git). Appeler le handler en direct reste
    dans le même thread et couvre exactement la même logique."""

    def test_post_parse_plantation_avec_conflit_retourne_l_avertissement(self, db):
        """[CA1] Le déclenchement fonctionne aussi sur le canal web, sans
        modifier le contrat JSON existant (champ additif)."""
        from main import TexteRequest, parse as main_parse

        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "tomate", annee=2025)

        with (
            patch("main.add_to_rag", MagicMock()),
            patch("main.SessionLocal", return_value=db),
            patch("main.parse_commande", return_value=[{
                "action": "plantation", "culture": "poivron",
                "quantite": 5, "unite": "plants", "parcelle": "NORD",
            }]),
        ):
            data = main_parse(TexteRequest(texte="planté 5 poivrons parcelle nord"), ctx=CTX)

        assert data["success"] is True
        assert "avertissements" in data
        assert any("Solanacée" in m for m in data["avertissements"])

    def test_post_parse_sans_conflit_avertissements_vide(self, db):
        """[CA4, CA1] Non-régression : le flux d'enregistrement normal n'est pas
        affecté ; un arrosage n'est même pas une action déclenchante (US-167
        ne concerne que plantation/semis), donc rien n'est affiché."""
        from main import TexteRequest, parse as main_parse

        _seed_culture(db, "tomate")
        _seed_evenement(db, _seed_parcelle(db, "NORD"), "tomate", annee=2026)

        with (
            patch("main.add_to_rag", MagicMock()),
            patch("main.SessionLocal", return_value=db),
            patch("main.parse_commande", return_value=[{
                "action": "arrosage", "culture": "tomate", "duree_minutes": 10,
            }]),
        ):
            data = main_parse(TexteRequest(texte="arrosé les tomates"), ctx=CTX)

        assert data["success"] is True
        assert data["avertissements"] == []
