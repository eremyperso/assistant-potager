"""[US-269] Enregistrer un geste sans dépendre de Telegram.

Le service `app.services.gestes` écrit les gestes confirmés à partir d'items
structurés ; le bot (`_do_save_items`) l'appelle et ne garde que ses messages.
"""
import ast
import inspect
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import evenements as svc_evenements
from app.services import gestes as svc_gestes
from app.services.context import default_context
from database.db import Base
from database.models import Evenement, Parcelle

RACINE = Path(__file__).resolve().parent.parent

#: Le geste du scénario Gherkin : « semis radis planche Sud 2 rangs ».
GESTE_GHERKIN = {"action": "semis", "culture": "radis", "quantite": 2, "unite": "rangs", "parcelle": "Sud"}
TEXTE_GHERKIN = "semis radis planche Sud 2 rangs"

#: Colonnes propres à chaque écriture : elles diffèrent forcément entre deux enregistrements.
COLONNES_PROPRES_A_L_ECRITURE = {"id"}


def _parcelle_sud(db) -> Parcelle:
    p = Parcelle(nom="Sud", nom_normalise="sud", ordre=1, actif=True)
    db.add(p)
    db.commit()
    return p


def _instantane(ev: Evenement) -> dict:
    """Les colonnes de l'événement, hors identifiant et horodatages d'écriture."""
    valeurs = {}
    for col in Evenement.__table__.columns:
        if col.name in COLONNES_PROPRES_A_L_ECRITURE:
            continue
        v = getattr(ev, col.name)
        if isinstance(v, datetime):   # horodatage d'écriture : seul le jour compte
            v = v.date()
        valeurs[col.name] = v
    return valeurs


def _mock_update():
    update = MagicMock()
    update.effective_message = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    return update


def _remettre_a_zero(db) -> None:
    db.close()
    moteur = db.get_bind()
    Base.metadata.drop_all(bind=moteur)
    Base.metadata.create_all(bind=moteur)


# ── CA1 : un service sans objet Telegram ─────────────────────────────────────

class TestServiceSansTelegram:

    def test_ca1_le_service_n_importe_rien_de_telegram(self):
        """CA1 — `app/services/gestes.py` n'importe ni `telegram` ni le bot."""
        arbre = ast.parse((RACINE / "app" / "services" / "gestes.py").read_text(encoding="utf-8"))
        modules = set()
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.Import):
                modules.update(a.name for a in noeud.names)
            elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                modules.add(noeud.module)
        assert not any(m == "telegram" or m.startswith(("telegram.", "app.bot")) for m in modules)

    def test_ca1_la_signature_ne_prend_aucun_update(self):
        """CA1 — on entre des données structurées : session, contexte, items, texte."""
        params = list(inspect.signature(svc_gestes.enregistrer_gestes).parameters)
        assert params[:4] == ["db", "ctx", "items", "texte"]
        assert "update" not in params

    def test_ca1_enregistre_un_geste_structure(self, test_db):
        """CA1 — Gherkin : le geste est écrit, rattaché à la parcelle, l'item est enrichi."""
        sud = _parcelle_sud(test_db)
        item = dict(GESTE_GHERKIN)

        resultat = svc_gestes.enregistrer_gestes(test_db, default_context(), [item], TEXTE_GHERKIN)

        assert resultat.complet and resultat.erreur is None
        assert len(resultat.enregistres) == 1
        parsed, event_id = resultat.enregistres[0]
        ev = test_db.get(Evenement, event_id)
        assert ev.type_action == "semis" and ev.culture == "radis"
        assert ev.parcelle_id == sud.id
        assert parsed is item and "contexte_semis" in item   # US-069 : le récapitulatif lit l'item enrichi

    def test_ca1_lot_numero_annonce_quand_l_evenement_en_porte_un(self):
        """US-209 — le numéro de lot réellement écrit remonte dans l'item."""
        ev = MagicMock(id=7, contexte_semis=None, numero_lot=3)
        item = {"action": "semis", "culture": "tomate", "quantite": 10}
        with patch.object(svc_evenements, "creer_evenement_confirme", return_value=ev):
            resultat = svc_gestes.enregistrer_gestes(MagicMock(), default_context(), [item], "semis tomate",
                                                     resoudre=lambda *a, **k: None)
        assert item["_lot_numero"] == 3
        assert resultat.enregistres == [(item, 7)]


# ── CA5 : même événement par le service que par le bot ───────────────────────

class TestMemeEvenementQueLeBot:

    @pytest.mark.asyncio
    async def test_ca5_le_service_produit_le_meme_evenement_que_le_bot(self, test_db):
        """CA5 — Gherkin : l'événement du service est identique à celui du bot pour la même phrase."""
        from app.bot import _do_save_items

        _parcelle_sud(test_db)
        with patch("app.bot.SessionLocal", return_value=test_db), \
             patch("app.bot.send_voice_reply", new_callable=AsyncMock):
            assert await _do_save_items(_mock_update(), [dict(GESTE_GHERKIN)], TEXTE_GHERKIN) is True
        par_le_bot = _instantane(test_db.query(Evenement).one())

        _remettre_a_zero(test_db)
        _parcelle_sud(test_db)
        resultat = svc_gestes.enregistrer_gestes(test_db, default_context(), [dict(GESTE_GHERKIN)], TEXTE_GHERKIN)
        par_le_service = _instantane(test_db.get(Evenement, resultat.enregistres[0][1]))

        assert par_le_service == par_le_bot


# ── Refus et erreurs ─────────────────────────────────────────────────────────

class TestRefus:

    def test_parcelle_inconnue_rien_n_est_ecrit(self, test_db):
        """La validation centrale refuse : le nom de la parcelle est rendu pour le message du canal."""
        item = {"action": "plantation", "culture": "courgette", "quantite": 10, "unite": "plants", "parcelle": "Ouest"}

        resultat = svc_gestes.enregistrer_gestes(test_db, default_context(), [item], "planter 10 courgettes Ouest")

        assert not resultat.complet
        assert resultat.parcelle_inconnue == "Ouest"
        assert "Ouest" in resultat.erreur
        assert resultat.enregistres == []
        assert test_db.query(Evenement).count() == 0

    def test_le_premier_refus_arrete_les_precedents_sont_rendus(self):
        """Un refus en cours de lot : les items déjà écrits sont rendus, les suivants ne sont pas tentés."""
        db = MagicMock()
        ev = MagicMock(id=11, contexte_semis=None, numero_lot=None)
        items = [{"action": "arrosage", "culture": "tomate"},
                 {"action": "arrosage", "culture": "courgette"},
                 {"action": "arrosage", "culture": "salade"}]
        creer = MagicMock(side_effect=[ev, svc_evenements.EvenementInvalideError("quantité invalide"), ev])
        with patch.object(svc_evenements, "creer_evenement_confirme", creer):
            resultat = svc_gestes.enregistrer_gestes(db, default_context(), items, "arrosages",
                                                     resoudre=lambda *a, **k: None)

        assert resultat.erreur == "quantité invalide"
        assert resultat.parcelle_inconnue is None
        assert resultat.enregistres == [(items[0], 11)]
        assert creer.call_count == 2
        db.rollback.assert_called_once()

    def test_une_erreur_inattendue_annule_et_remonte(self):
        """Base indisponible : rollback, puis l'exception remonte au canal."""
        db = MagicMock()
        with patch.object(svc_evenements, "creer_evenement_confirme", side_effect=RuntimeError("base coupée")):
            with pytest.raises(RuntimeError, match="base coupée"):
                svc_gestes.enregistrer_gestes(db, default_context(), [{"action": "arrosage"}], "arrosé",
                                              resoudre=lambda *a, **k: None)
        db.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_ca2_le_bot_dit_toujours_erreur_base_de_donnees(self):
        """CA2 — même message qu'avant l'extraction quand la base lève."""
        from app.bot import _do_save_items

        update = _mock_update()
        with patch("app.bot.SessionLocal", return_value=MagicMock()), \
             patch.object(svc_evenements, "creer_evenement_confirme", side_effect=RuntimeError("base coupée")):
            ecrit = await _do_save_items(update, [{"action": "arrosage", "culture": "tomate"}], "arrosé les tomates")

        assert ecrit is False
        update.effective_message.reply_text.assert_called_once_with("❌ Erreur base de données : base coupée")

    @pytest.mark.asyncio
    async def test_ca2_le_bot_dit_ce_qui_etait_deja_enregistre(self):
        """CA2 — le message de refus en cours de lot est inchangé (« Déjà enregistré avant l'erreur »)."""
        from app.bot import _do_save_items

        update = _mock_update()
        ev = MagicMock(id=5, contexte_semis=None, numero_lot=None)
        items = [{"action": "arrosage", "culture": "tomate"}, {"action": "arrosage", "culture": "courgette"}]
        with patch("app.bot.SessionLocal", return_value=MagicMock()), \
             patch("app.bot.resolve_parcelle", return_value=None), \
             patch.object(svc_evenements, "creer_evenement_confirme",
                          side_effect=[ev, svc_evenements.EvenementInvalideError("refusé")]):
            ecrit = await _do_save_items(update, items, "arrosages")

        assert ecrit is False
        texte = update.effective_message.reply_text.call_args.args[0]
        assert texte == "❌ refusé\n\n✅ Déjà enregistré avant l'erreur : tomate (n° 5)."


# ── Règles reprises du bot ───────────────────────────────────────────────────

class TestReglesReprises:

    def test_mise_en_godet_passe_par_creer_evenement_godet(self):
        """Bug id=351 — une mise en godet ne passe jamais par creer_evenement_confirme."""
        ev = MagicMock(id=3, contexte_semis=None, numero_lot=None)
        with patch.object(svc_evenements, "creer_evenement_godet", return_value=ev) as godet, \
             patch.object(svc_evenements, "creer_evenement_confirme") as confirme:
            svc_gestes.enregistrer_gestes(MagicMock(), default_context(),
                                          [{"action": "mise_en_godet", "culture": None, "quantite": 3}],
                                          "mise en godet de 3", resoudre=lambda *a, **k: None)
        godet.assert_called_once()
        confirme.assert_not_called()

    def test_avertissements_evalues_avant_toute_ecriture(self):
        """US-167 — l'avertissement est calculé avant l'écriture, et rendu au canal."""
        suivi = MagicMock()
        ev = MagicMock(id=1, contexte_semis=None, numero_lot=None)
        suivi.evaluer.return_value = ["⚠️ rotation"]
        suivi.creer.return_value = ev
        item = {"action": "plantation", "culture": "tomate", "quantite": 3, "parcelle": "Nord"}
        with patch("app.services.avertissements_plantation.evaluer_avertissements_plantation", suivi.evaluer), \
             patch.object(svc_evenements, "creer_evenement_confirme", suivi.creer):
            resultat = svc_gestes.enregistrer_gestes(MagicMock(), default_context(), [item], "planté 3 tomates",
                                                     resoudre=lambda *a, **k: MagicMock(id=42))
        assert resultat.avertissements == ["⚠️ rotation"]
        noms = [c[0] for c in suivi.mock_calls]
        assert noms.index("evaluer") < noms.index("creer")

    def test_avertissements_ignores_sans_parcelle_resolue(self):
        """Pas de parcelle (absente ou introuvable) : aucun avertissement, aucun appel."""
        with patch("app.services.avertissements_plantation.evaluer_avertissements_plantation") as evaluer:
            sans_nom = svc_gestes.evaluer_avertissements(MagicMock(), default_context(),
                                                         [{"action": "plantation", "culture": "tomate"}])
            introuvable = svc_gestes.evaluer_avertissements(
                MagicMock(), default_context(), [{"action": "plantation", "culture": "tomate", "parcelle": "X"}],
                resoudre=lambda *a, **k: None)
            arrosage = svc_gestes.evaluer_avertissements(
                MagicMock(), default_context(), [{"action": "arrosage", "parcelle": "Nord"}],
                resoudre=lambda *a, **k: MagicMock(id=1))
        assert sans_nom == introuvable == arrosage == []
        evaluer.assert_not_called()

    def test_le_bot_passe_sa_resolution_de_parcelle(self):
        """Le bot fournit sa résolution : `patch("app.bot.resolve_parcelle")` reste effectif."""
        ev = MagicMock(id=1, contexte_semis=None, numero_lot=None)
        parc = MagicMock(id=99)
        from app.bot import enregistrement
        with patch("app.bot.resolve_parcelle", return_value=parc), \
             patch.object(svc_evenements, "creer_evenement_confirme", return_value=ev) as creer:
            svc_gestes.enregistrer_gestes(MagicMock(), default_context(), [{"action": "arrosage", "parcelle": "Nord"}],
                                          "arrosé", resoudre=enregistrement.resolve_parcelle)
        assert creer.call_args.args[4] is parc
