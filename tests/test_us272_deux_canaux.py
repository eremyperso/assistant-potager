"""
tests/test_us272_deux_canaux.py — Une proposition, deux fenêtres : Telegram et la PWA [US-272]
==============================================================================================
Une proposition vit en base ; Telegram et le panneau de la PWA en sont deux fenêtres (cadrage
§4.7, D11 à D13, F1 à F5). Couverture CA1 → CA9 et le scénario Gherkin.

Aucun appel réseau : `telegram_notify.envoyer` / `editer_message` sont simulés, l'envoi est
synchrone (`deux_canaux.SYNCHRONE`), l'agent est éteint, le parseur est simulé.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import config
from app.services import gestes as svc_gestes
from app.services import interpreteur_commandes as interp
from app.services import normalisation_gestes as svc_normalisation
from app.services import telegram_notify
from app.services.compagnon import actions_menees
from app.services.compagnon import corrections
from app.services.compagnon import deux_canaux
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import gestes_conversation as svc_gestes_dits
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext, default_context
from database.db import Base
from database.models import CultureConfig, EchangeConversation, Evenement, Parcelle, Proposition, User
from llm import routeur

CTX = default_context()
CHAT = 111

GHERKIN = "j'ai repiqué 12 tomates sur la planche Sud"
ITEM_GHERKIN = {
    "action": "repiquage", "culture": "tomate", "variete": None, "quantite": 12.0, "unite": "plants",
    "parcelle": "Sud", "rang": None, "duree_minutes": None, "traitement": None, "date": None,
    "commentaire": None, "nb_graines_semees": None, "nb_plants_godets": None,
    "origine_parsing": "deterministe",
}
AUTRE_PHRASE = "j'ai repiqué 10 tomates sur la planche Sud"
ITEM_AUTRE = dict(ITEM_GHERKIN, quantite=10.0)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def sans_modele(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "off")


@pytest.fixture(autouse=True)
def synchrone(monkeypatch):
    """L'envoi Telegram se fait dans l'appel : le test lit son résultat tout de suite."""
    monkeypatch.setattr(deux_canaux, "SYNCHRONE", True)


@pytest.fixture
def telegram(monkeypatch):
    """Telegram simulé : chaque envoi rend un identifiant de message, chaque édition est notée."""
    faux = SimpleNamespace(envoyes=[], edites=[], refuser_edition=False, pendant_envoi=None)

    def envoyer(chat_id, texte, boutons=None, parse_mode=None):
        if faux.pendant_envoi:
            faux.pendant_envoi()
        faux.envoyes.append((chat_id, texte, boutons))
        return 4000 + len(faux.envoyes)

    def editer(chat_id, message_id, texte, boutons=None, parse_mode=None):
        faux.edites.append((chat_id, message_id, texte))
        return not faux.refuser_edition

    monkeypatch.setattr(telegram_notify, "envoyer", envoyer)
    monkeypatch.setattr(telegram_notify, "editer_message", editer)
    return faux


@pytest.fixture
def potager(memoire_compagnon):
    """La planche Sud, les cultures, et un jardinier dont le compagnon Telegram est activé."""
    with memoire_compagnon() as db:
        db.add(User(id=CTX.user_id, nom="Éric", telegram_chat_id=CHAT))
        db.add(Parcelle(nom="Sud", nom_normalise="sud", ordre=1, actif=True, potager_id=CTX.potager_id))
        db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
        db.commit()
    yield memoire_compagnon
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(CultureConfig).delete()
        db.query(EchangeConversation).delete()
        db.query(User).delete()
        db.commit()


@pytest.fixture
def sans_telegram(potager):
    """Le même jardinier, sans compagnon de terrain activé."""
    with potager() as db:
        db.query(User).filter(User.id == CTX.user_id).update({"telegram_chat_id": None})
        db.commit()
    return potager


def _parseur(items_par_phrase: dict[str, list[dict]]):
    def parseur(texte, ctx=None):
        items = items_par_phrase.get(texte)
        return type("R", (), {"reconnu": items is not None, "items": [dict(i) for i in items] if items else None})()
    return parseur


@pytest.fixture
def parseur(monkeypatch):
    monkeypatch.setattr(svc_normalisation, "parser_saisie", _parseur({GHERKIN: [ITEM_GHERKIN], AUTRE_PHRASE: [ITEM_AUTRE]}))


def _action():
    decision = routeur.DecisionRoutage(nature=routeur.NATURE_ACTION, origine="regle", confiance=1.0)
    return patch("llm.routeur.classer_demande", return_value=decision)


def _dire_dans_la_pwa(phrase: str = GHERKIN) -> dict:
    with _action():
        reponse = svc_echange.repondre(CTX, phrase)
    assert reponse.vers == svc_echange.VERS_GESTE, reponse.texte
    return reponse.propositions[0]


def _ligne(fabrique, proposition_id: int) -> Proposition:
    with fabrique() as db:
        ligne = db.get(Proposition, proposition_id)
        db.expunge(ligne)
        return ligne


def _nb_evenements(fabrique) -> int:
    with fabrique() as db:
        return db.query(Evenement).count()


def _commande():
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", "modifier")],
        {"nom": "Sud", "modification": "rangs=2"}, interp.ORIGINE_REGLE, 1.0, "x",
    )


# ── le bot : un clic simulé ─────────────────────────────────────────────────
def _clic(donnee: str):
    query = MagicMock()
    query.data = donnee
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return SimpleNamespace(callback_query=query, effective_chat=SimpleNamespace(id=CHAT),
                           effective_user=SimpleNamespace(id=CHAT))


def _texte_du_clic(update) -> str:
    return update.callback_query.edit_message_text.await_args.args[0]


@pytest.fixture
def bot_cartes(monkeypatch):
    from app.bot import cartes_compagnon

    monkeypatch.setattr(cartes_compagnon, "_jardinier_au_clic", lambda update: CTX.user_id)
    monkeypatch.setattr(cartes_compagnon, "_contexte_sur", lambda user_id, potager_id: TenantContext(
        user_id=user_id, potager_id=potager_id, role="owner"))
    monkeypatch.setattr(cartes_compagnon, "_armer", lambda contexte: None)
    return cartes_compagnon


@pytest.fixture
def bot_interp(monkeypatch):
    from app.bot import interpretation

    monkeypatch.setattr(interpretation, "_jardinier_au_clic", lambda update: CTX.user_id)
    return interpretation


# ═════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin
# ═════════════════════════════════════════════════════════════════════════════
class TestGherkin:

    @pytest.mark.asyncio
    async def test_us272_gherkin_confirme_dans_la_pwa_puis_clic_dans_telegram(
            self, potager, parseur, telegram, bot_cartes):
        # Given le jardinier dit « j'ai repiqué 12 tomates sur la planche Sud » dans la PWA
        carte = _dire_dans_la_pwa()
        # Then une carte apparaît dans le panneau et dans Telegram
        assert carte["etat"] == "en_attente" and carte["confirmable"] is True
        (chat, texte, boutons), = telegram.envoyes
        assert chat == CHAT and "tomate · 12 plants · parcelle Sud" in texte
        assert boutons == [[("✅ Confirmer", f"cmp:ok:{carte['code']}"), ("❌ Annuler", f"cmp:non:{carte['code']}")]]
        # When il confirme dans la PWA
        issue = svc_echange.confirmer(CTX, carte["id"])
        assert issue.carte["etat"] == "confirmee" and len(issue.enregistres) == 1
        # Then la carte Telegram est réécrite « ✅ Confirmé depuis le portail »
        (_, message_id, reecrit), = telegram.edites
        assert message_id == 4001 and reecrit.startswith("✅ Confirmé depuis le portail à ")
        # When il clique ensuite [Confirmer] dans Telegram
        clic = _clic(f"cmp:ok:{carte['code']}")
        await bot_cartes.carte_compagnon_cb(clic, MagicMock())
        # Then il lit « Déjà confirmé depuis le portail » et rien n'est enregistré deux fois
        assert _texte_du_clic(clic).startswith("Déjà confirmé depuis le portail à ")
        assert _nb_evenements(potager) == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — toute proposition née dans la PWA part dans Telegram dès sa création (D13)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1EnvoiDansTelegram:

    def test_us272_ca1_la_carte_garde_son_message_et_prend_trois_jours(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        ligne = _ligne(potager, carte["id"])
        assert (ligne.telegram_chat_id, ligne.telegram_message_id) == (CHAT, 4001)
        # [F4] notifiée : la durée de la file, pas la demi-heure de conversation
        assert ligne.notifiee is True and ligne.expire_le - ligne.cree_le >= timedelta(days=3)
        assert deux_canaux.TEXTE_ORIGINE_PORTAIL in telegram.envoyes[0][1]

    def test_us272_ca1_confirmee_aussitot_la_carte_part_quand_meme_puis_est_reecrite(
            self, potager, parseur, telegram):
        """D13 : confirmée pendant l'envoi, la carte part (journal complet) et suit son état tout de suite."""
        def confirmer_pendant_l_envoi():
            with potager() as db:
                ligne = db.query(Proposition).one()
                svc_propositions.sortir(db, ligne.id, svc_propositions.ETAT_CONFIRMEE, canal="pwa")
        telegram.pendant_envoi = confirmer_pendant_l_envoi
        _dire_dans_la_pwa()
        assert len(telegram.envoyes) == 1
        (_, _, reecrit), = telegram.edites
        assert reecrit.startswith("✅ Confirmé depuis le portail")

    def test_us272_ca1_une_commande_nee_dans_la_pwa_part_avec_les_boutons_de_conversation(self, potager, telegram):
        with patch.object(interp, "persister_journal", return_value=None):
            reponse = svc_echange._proposer_une_commande(CTX, _commande(), preambule="")
        code = reponse.propositions[0]["code"]
        (_, texte, boutons), = telegram.envoyes
        assert "/parcelle modifier" in texte
        assert boutons[0][0] == ("✅ Confirmer", f"interp:ok:{code}")

    def test_us272_ca1_telegram_injoignable_le_panneau_reste_juste(self, potager, parseur, monkeypatch):
        monkeypatch.setattr(telegram_notify, "envoyer", lambda *a, **k: None)
        carte = _dire_dans_la_pwa()
        ligne = _ligne(potager, carte["id"])
        assert ligne.telegram_message_id is None and ligne.notifiee is False
        assert svc_echange.confirmer(CTX, carte["id"]).carte["etat"] == "confirmee"

    def test_us272_ca1_une_erreur_d_envoi_ne_remonte_jamais(self, potager, parseur, monkeypatch):
        def panne(*a, **k):
            raise RuntimeError("réseau")
        monkeypatch.setattr(telegram_notify, "envoyer", panne)
        assert _dire_dans_la_pwa()["etat"] == "en_attente"

    def test_us272_ca1_l_envoi_part_en_arriere_plan_par_defaut(self, potager, parseur, telegram, monkeypatch):
        monkeypatch.setattr(deux_canaux, "SYNCHRONE", False)
        fait = threading.Event()
        vrai = telegram_notify.envoyer
        monkeypatch.setattr(telegram_notify, "envoyer", lambda *a, **k: (vrai(*a, **k), fait.set())[0])
        _dire_dans_la_pwa()
        assert fait.wait(5)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — la première réponse l'emporte, le second reçoit où et quand (F1)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2PremiereReponse:

    def test_us272_ca2_les_textes_du_second(self):
        quand = datetime(2026, 11, 6, 13, 32)   # 14:32 à Paris
        assert deux_canaux.texte_deja_traitee("confirmee", "pwa", quand) == \
            "Déjà confirmé depuis le portail à 14:32 : rien n'est refait."
        assert deux_canaux.texte_deja_traitee("abandonnee", "telegram", quand).startswith(
            "Déjà laissé tomber depuis Telegram à 14:32")
        assert deux_canaux.texte_deja_traitee("remplacee", None, None).startswith("↪️ Remplacée")
        assert deux_canaux.texte_deja_traitee("perimee", None, None) == deux_canaux.TEXTE_PERIMEE

    def test_us272_ca2_confirme_dans_telegram_puis_dans_la_pwa_409(self, potager, parseur, telegram, monkeypatch):
        from app.api.main import app, get_current_user_ctx

        carte = _dire_dans_la_pwa()
        svc_gestes_dits.confirmer(CTX, carte["id"], canal="telegram")
        app.dependency_overrides[get_current_user_ctx] = default_context
        try:
            with TestClient(app) as client:
                reponse = client.post(f"/compagnon/propositions/{carte['id']}/confirmer")
        finally:
            app.dependency_overrides.pop(get_current_user_ctx, None)
        assert reponse.status_code == 409
        detail = reponse.json()["detail"]
        assert detail["etat"] == "confirmee"
        assert detail["message"].startswith("Déjà confirmé depuis Telegram à ")
        assert _nb_evenements(potager) == 1

    @pytest.mark.asyncio
    async def test_us272_ca2_une_commande_confirmee_dans_la_pwa_refusee_au_bouton_telegram(
            self, potager, telegram, bot_interp):
        proposition = svc_propositions.proposer(CTX, _commande(), canal="pwa")
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="pwa")
        clic = _clic(f"interp:ok:{proposition.code}")
        await bot_interp._interp_cb(clic, MagicMock())
        assert _texte_du_clic(clic).startswith("Déjà confirmé depuis le portail à ")

    @pytest.mark.asyncio
    async def test_us272_ca2_laisse_tomber_dans_telegram_rien_n_est_ecrit(self, potager, parseur, telegram, bot_cartes):
        carte = _dire_dans_la_pwa()
        clic = _clic(f"cmp:non:{carte['code']}")
        await bot_cartes.carte_compagnon_cb(clic, MagicMock())
        assert _texte_du_clic(clic).startswith("❌ Laissé tomber")
        assert _ligne(potager, carte["id"]).traite_canal == "telegram"
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
            svc_echange.confirmer(CTX, carte["id"])
        assert refus.value.etat == "abandonnee" and refus.value.canal == "telegram"
        assert _nb_evenements(potager) == 0

    @pytest.mark.asyncio
    async def test_us272_ca2_un_bouton_inconnu_ne_fait_rien(self, potager, bot_cartes):
        clic = _clic("cmp:ok:pinconnu")
        await bot_cartes.carte_compagnon_cb(clic, MagicMock())
        assert "expirée" in _texte_du_clic(clic)

    @pytest.mark.asyncio
    async def test_us272_ca2_un_lecteur_ne_confirme_rien_depuis_telegram(
            self, potager, parseur, telegram, bot_cartes, monkeypatch):
        carte = _dire_dans_la_pwa()
        monkeypatch.setattr(bot_cartes, "_contexte_sur", lambda u, p: TenantContext(user_id=u, potager_id=p, role="lecteur"))
        clic = _clic(f"cmp:ok:{carte['code']}")
        await bot_cartes.carte_compagnon_cb(clic, MagicMock())
        assert _texte_du_clic(clic) == bot_cartes.TEXTE_LECTURE_SEULE
        assert _nb_evenements(potager) == 0

    @pytest.mark.asyncio
    async def test_us272_ca2_hors_d_acces_au_potager_rien_n_est_fait(self, potager, parseur, telegram, bot_cartes,
                                                                    monkeypatch):
        carte = _dire_dans_la_pwa()
        monkeypatch.setattr(bot_cartes, "_contexte_sur", lambda u, p: None)
        clic = _clic(f"cmp:ok:{carte['code']}")
        await bot_cartes.carte_compagnon_cb(clic, MagicMock())
        assert "plus accès" in _texte_du_clic(clic)
        assert _ligne(potager, carte["id"]).etat == "en_attente"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — au changement d'état, la carte est réécrite dans chaque canal (F2)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3CartesReecrites:

    def test_us272_ca3_abandonne_dans_la_pwa_la_carte_telegram_le_dit(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        svc_echange.abandonner(CTX, carte["id"])
        (_, _, texte), = telegram.edites
        assert texte.startswith("❌ Laissé tomber depuis le portail") and "tomate" in texte

    def test_us272_ca3_si_la_reecriture_echoue_le_refus_suffit(self, potager, parseur, telegram):
        telegram.refuser_edition = True
        carte = _dire_dans_la_pwa()
        svc_echange.confirmer(CTX, carte["id"])
        assert len(telegram.edites) == 1      # tentée, refusée, sans erreur
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError):
            svc_gestes_dits.confirmer(CTX, carte["id"], canal="telegram")
        assert _nb_evenements(potager) == 1

    def test_us272_ca3_confirme_dans_telegram_la_carte_du_panneau_le_dit(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        svc_gestes_dits.confirmer(CTX, carte["id"], canal="telegram")
        traitee, = svc_echange.etat(CTX)["traitees"]
        assert traitee["id"] == carte["id"] and traitee["etat"] == "confirmee"
        assert traitee["traite_canal"] == "telegram" and traitee["etat_dit"].startswith("✅ Confirmé depuis Telegram")

    def test_us272_ca3_une_proposition_en_attente_n_est_pas_reecrite(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        assert deux_canaux.reecrire(carte["id"]) is False and telegram.edites == []

    @pytest.mark.asyncio
    async def test_us272_ca3_confirmee_par_une_phrase_dans_telegram_la_carte_est_reecrite(self, potager, telegram,
                                                                                          bot_interp):
        proposition = svc_propositions.proposer(CTX, _commande(), canal="pwa")
        deux_canaux.notifier(proposition.id, CTX.potager_id)
        svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE, canal="telegram")
        ctx = MagicMock()
        ctx.bot.edit_message_text = AsyncMock()
        assert await bot_interp.reecrire_carte(ctx, proposition.id) is True
        kwargs = ctx.bot.edit_message_text.await_args.kwargs
        assert (kwargs["chat_id"], kwargs["message_id"]) == (CHAT, 4001)
        assert kwargs["text"].startswith("❌ Laissé tomber depuis Telegram")

    @pytest.mark.asyncio
    async def test_us272_ca3_une_reecriture_refusee_par_telegram_ne_leve_pas(self, potager, telegram, bot_interp):
        proposition = svc_propositions.proposer(CTX, _commande(), canal="pwa")
        deux_canaux.notifier(proposition.id, CTX.potager_id)
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")
        ctx = MagicMock()
        ctx.bot.edit_message_text = AsyncMock(side_effect=RuntimeError("message trop ancien"))
        assert await bot_interp.reecrire_carte(ctx, proposition.id) is False

    def test_us272_ca3_le_bot_retient_la_carte_qu_il_poste(self, potager, bot_interp):
        proposition = svc_propositions.proposer(CTX, _commande(), canal="telegram")
        bot_interp._retenir_la_carte(proposition, SimpleNamespace(message_id=77, chat=SimpleNamespace(id=CHAT)))
        ligne = _ligne(potager, proposition.id)
        assert (ligne.telegram_chat_id, ligne.telegram_message_id) == (CHAT, 77)
        # Un message simulé (MagicMock) n'est pas retenu.
        bot_interp._retenir_la_carte(proposition, MagicMock())
        assert _ligne(potager, proposition.id).telegram_message_id == 77


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — une proposition remplacée voit sa carte réécrite (F3)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Remplacee:

    def test_us272_ca4_un_geste_redit_remplace_l_ancien_dans_telegram(self, potager, parseur, telegram):
        ancienne = _dire_dans_la_pwa()
        nouvelle = _dire_dans_la_pwa(AUTRE_PHRASE)
        assert _ligne(potager, ancienne["id"]).etat == "remplacee"
        (_, message_id, texte), = telegram.edites
        assert message_id == 4001 and texte.startswith(deux_canaux.TEXTE_REMPLACEE)
        # La nouvelle part dans les deux canaux, avec ses propres boutons.
        assert len(telegram.envoyes) == 2 and f"cmp:ok:{nouvelle['code']}" == telegram.envoyes[1][2][0][0][1]

    def test_us272_ca4_une_commande_remplacee_est_reecrite(self, potager, telegram):
        with patch.object(interp, "persister_journal", return_value=None):
            svc_echange._proposer_une_commande(CTX, _commande(), preambule="")
            svc_echange._proposer_une_commande(CTX, _commande(), preambule="")
        (_, message_id, texte), = telegram.edites
        assert message_id == 4001 and texte.startswith(deux_canaux.TEXTE_REMPLACEE)
        assert "/parcelle modifier" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le panneau montre l'état réel, relu à intervalle court, sans WebSocket
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5EtatReel:

    def test_us272_ca5_la_route_d_etat_rend_cartes_traitees_et_spontanes(self, potager, parseur, telegram):
        from app.api.main import app, get_current_user_ctx

        en_attente = _dire_dans_la_pwa()
        app.dependency_overrides[get_current_user_ctx] = default_context
        try:
            with TestClient(app) as client:
                corps = client.get("/compagnon/etat").json()
        finally:
            app.dependency_overrides.pop(get_current_user_ctx, None)
        assert set(corps) == {"cartes", "traitees", "spontanes"}
        assert [c["id"] for c in corps["cartes"]] == [en_attente["id"]] and corps["traitees"] == []

    def test_us272_ca5_une_carte_traitee_il_y_a_plus_de_douze_heures_n_est_plus_relue(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        svc_echange.confirmer(CTX, carte["id"])
        assert len(svc_echange.cartes_traitees(CTX)) == 1
        assert svc_echange.cartes_traitees(CTX, maintenant=datetime.utcnow() + timedelta(hours=13)) == []

    def test_us272_ca5_la_lecture_d_etat_n_ecrit_rien(self, potager, parseur, telegram):
        _dire_dans_la_pwa()
        with potager() as db:
            avant = db.query(EchangeConversation).count()
        svc_echange.etat(CTX)
        with potager() as db:
            assert db.query(EchangeConversation).count() == avant

    def test_us272_ca5_le_panneau_se_relit_sans_websocket(self):
        from pathlib import Path

        racine = Path(__file__).resolve().parents[1] / "frontend" / "src"
        panneau = (racine / "components" / "PanneauCompagnon.jsx").read_text(encoding="utf-8")
        pastille = (racine / "hooks" / "useNonLusCompagnon.js").read_text(encoding="utf-8")
        assert "etatCompagnon" in panneau and "setInterval" in panneau and "new WebSocket" not in panneau
        assert "INTERVALLE_FERME_MS" in pastille and "new WebSocket" not in pastille


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la carte nomme le potager quand le jardinier en a plusieurs (F5)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Potager:

    def test_us272_ca6_plusieurs_potagers_la_carte_le_nomme(self, potager, parseur, telegram, monkeypatch):
        monkeypatch.setattr(svc_propositions, "potager_a_nommer", lambda u, p: "Potager du bas")
        carte = _dire_dans_la_pwa()
        assert carte["potager"] == "Potager du bas"
        assert telegram.envoyes[0][1].startswith("🏡 Potager du bas\n")

    def test_us272_ca6_un_seul_potager_rien_n_est_nomme(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        assert carte["potager"] is None and "🏡" not in telegram.envoyes[0][1]

    @pytest.mark.asyncio
    async def test_us272_ca6_confirme_dans_telegram_il_s_ecrit_dans_son_potager(
            self, potager, parseur, telegram, bot_cartes, monkeypatch):
        vus = []
        monkeypatch.setattr(bot_cartes, "_contexte_sur", lambda u, p: (vus.append(p), TenantContext(
            user_id=u, potager_id=p, role="owner"))[1])
        carte = _dire_dans_la_pwa()
        await bot_cartes.carte_compagnon_cb(_clic(f"cmp:ok:{carte['code']}"), MagicMock())
        assert vus == [CTX.potager_id]
        with potager() as db:
            assert db.query(Evenement).one().potager_id == CTX.potager_id


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — concurrence : 0 double exécution sur 100 confirmations simultanées
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def base_fichier(tmp_path, monkeypatch):
    """Une base SQLite sur fichier, une connexion par session : de vraies transactions concurrentes."""
    moteur = create_engine(f"sqlite:///{tmp_path / 'us272.db'}", connect_args={"timeout": 30, "check_same_thread": False})
    Base.metadata.create_all(bind=moteur)
    fabrique = sessionmaker(bind=moteur, autocommit=False, autoflush=False)
    monkeypatch.setattr(svc_propositions, "SessionLocal", fabrique)
    yield fabrique
    moteur.dispose()


class TestCA7Concurrence:

    def test_us272_ca7_cent_confirmations_simultanees_une_seule_ecriture(self, base_fichier, monkeypatch):
        with base_fichier() as db:
            db.add(User(id=CTX.user_id, nom="Éric"))
            db.commit()
        geste = svc_gestes_dits.proposer(CTX, [dict(ITEM_GHERKIN)], GHERKIN)
        ecritures = []
        verrou = threading.Lock()

        def enregistrer(db, ctx, items, texte, resoudre=None):
            with verrou:
                ecritures.append(texte)
            return svc_gestes.ResultatEnregistrement(enregistres=[(items[0], 1)])

        monkeypatch.setattr(svc_gestes, "enregistrer_gestes", enregistrer)
        depart = threading.Barrier(100)

        def confirmer(rang: int) -> str:
            canal = "pwa" if rang % 2 else "telegram"   # la moitié depuis chaque fenêtre
            depart.wait()
            try:
                svc_gestes_dits.confirmer(CTX, geste.id, canal=canal)
                return "ecrit"
            except svc_gestes_dits.GesteDejaTraiteError:
                return "refuse"

        with ThreadPoolExecutor(max_workers=100) as pool:
            issues = list(pool.map(confirmer, range(100)))

        assert len(ecritures) == 1
        assert issues.count("ecrit") == 1 and issues.count("refuse") == 99
        with base_fichier() as db:
            assert db.get(Proposition, geste.id).etat == "confirmee"


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — parité : confirmée d'un côté, vue confirmée de l'autre ; la correction suit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Parite:

    def test_us272_ca8_confirmee_dans_la_pwa_vue_confirmee_dans_telegram(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        svc_echange.confirmer(CTX, carte["id"])
        relu = svc_gestes_dits.par_code(carte["code"], CTX.user_id)      # ce que lit le bouton Telegram
        assert (relu.etat, relu.traite_canal) == ("confirmee", "pwa")
        assert telegram.edites[0][2].startswith("✅ Confirmé depuis le portail")

    def test_us272_ca8_confirmee_dans_telegram_vue_confirmee_dans_la_pwa(self, potager, parseur, telegram):
        carte = _dire_dans_la_pwa()
        svc_gestes_dits.confirmer(CTX, carte["id"], canal="telegram")
        assert svc_echange.cartes_en_cours(CTX) == []
        assert svc_echange.etat(CTX)["traitees"][0]["etat"] == "confirmee"

    def test_us272_ca8_en_fait_c_etait_10_corrige_le_geste_confirme_dans_la_pwa(
            self, potager, parseur, telegram, monkeypatch):
        monkeypatch.setattr(corrections, "SessionLocal", potager)
        jeton = actions_menees.canal_courant.set(actions_menees.CANAL_PWA)
        try:
            carte = _dire_dans_la_pwa()
            svc_echange.confirmer(CTX, carte["id"])
        finally:
            actions_menees.canal_courant.reset(jeton)
        action, = actions_menees.recentes(CTX)
        assert action.canal == "pwa" and action.cible_type == "evenement"

        # Dans Telegram : « en fait c'était 10 » vise A1, le geste confirmé dans le portail.
        jeton = actions_menees.canal_courant.set(actions_menees.CANAL_TELEGRAM)
        try:
            verdict = corrections.valider("corriger_action", {"ref": "A1", "champs": {"quantite": 10}},
                                          "en fait c'était 10", CTX, ("Sud",))
            assert verdict.commande is not None, verdict
            with potager() as db:
                texte = corrections.executer(db, CTX, verdict.commande)
        finally:
            actions_menees.canal_courant.reset(jeton)
        assert texte.startswith("✅ Corrigé")
        with potager() as db:
            evenement, = db.query(Evenement).all()
            assert evenement.quantite == 10


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — sans Telegram lié : le panneau seul, et une invitation, une fois
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9SansTelegram:

    def test_us272_ca9_rien_ne_part_dans_telegram(self, sans_telegram, parseur, telegram):
        carte = _dire_dans_la_pwa()
        assert telegram.envoyes == [] and carte["etat"] == "en_attente"
        assert svc_echange.confirmer(CTX, carte["id"]).carte["etat"] == "confirmee"
        assert telegram.edites == []

    def test_us272_ca9_invite_une_seule_fois(self, sans_telegram):
        premiere = svc_echange.historique(CTX)
        assert premiere["telegram_lie"] is False
        assert premiere["invitation_telegram"] == deux_canaux.TEXTE_INVITATION_TELEGRAM
        assert "Activer mon compagnon" in premiere["invitation_telegram"]
        # La même visite la relit (double appel, « Recommencer ») ; une visite suivante, jamais.
        assert svc_echange.historique(CTX)["invitation_telegram"] == deux_canaux.TEXTE_INVITATION_TELEGRAM
        plus_tard = datetime.utcnow() + deux_canaux.DUREE_INVITATION + timedelta(seconds=1)
        assert deux_canaux.invitation_telegram(CTX.user_id, maintenant=plus_tard) is None

    def test_us272_ca9_un_compte_lie_n_est_jamais_invite(self, potager):
        historique = svc_echange.historique(CTX)
        assert historique["telegram_lie"] is True and historique["invitation_telegram"] is None
        with potager() as db:
            assert db.get(User, CTX.user_id).invitation_telegram_le is None

    def test_us272_ca9_les_messages_spontanes_vont_au_panneau(self):
        """Le distributeur range le message sans Telegram (couvert en détail par test_us267)."""
        import inspect
        from app.services.compagnon import distribution

        source = inspect.getsource(distribution._envoyer_message)
        assert "panneau_seul" in source
        assert "MOTIF_SANS_TELEGRAM" not in inspect.getsource(distribution.envoyer_dus)


# ═════════════════════════════════════════════════════════════════════════════
# Gardes de conception
# ═════════════════════════════════════════════════════════════════════════════
class TestConception:

    def test_us272_la_route_d_etat_ne_porte_aucune_logique(self):
        import ast
        import inspect
        from app.api import main

        fonction = ast.parse(inspect.getsource(main.etat_compagnon)).body[0]
        appels = [n for instruction in fonction.body for n in ast.walk(instruction) if isinstance(n, ast.Call)]
        assert len(appels) == 1      # svc_echange_pwa.etat(ctx), rien d'autre

    def test_us272_le_handler_telegram_ne_touche_pas_la_base(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "app" / "bot" / "cartes_compagnon.py").read_text(encoding="utf-8")
        assert "db.query" not in source and "SessionLocal" not in source

    def test_us272_le_bouton_tient_dans_les_64_octets_de_telegram(self, potager, parseur, telegram):
        _dire_dans_la_pwa()
        for rangee in telegram.envoyes[0][2]:
            for _, donnee in rangee:
                assert len(donnee.encode()) <= 64
