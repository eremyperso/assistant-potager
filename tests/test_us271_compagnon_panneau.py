"""
tests/test_us271_compagnon_panneau.py — Parler au compagnon depuis la PWA [US-271] (partie serveur)
===================================================================================================
Le panneau est du React (`frontend/src/components/PanneauCompagnon.jsx`, sa logique dans
`frontend/src/lib/compagnon.js`, testée par `npm test`). Ce que le panneau exige du SERVEUR :

* CA1 — les deux modes : Normal (agent, gestes) et Support (la documentation de l'application
  d'abord, jamais d'écriture) ;
* CA3 — les messages spontanés du compagnon, rangés dans le panneau avec la conversation ;
* CA4 — les erreurs en clair : proposition expirée, déjà traitée.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import connaissance
from app.services.compagnon import distribution as svc_distribution
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.context import TenantContext, default_context
from database.models import Evenement, MessageSpontane
from llm import routeur

CTX = default_context()
AUTRE_JARDINIER = TenantContext(user_id=CTX.user_id + 1, potager_id=CTX.potager_id, role="owner")


@pytest.fixture(autouse=True)
def sans_modele(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "off")


@pytest.fixture
def messages(memoire_compagnon, monkeypatch):
    """Les messages spontanés vivent dans la base du compagnon ; vidée en fin de test."""
    monkeypatch.setattr(svc_distribution, "SessionLocal", memoire_compagnon)
    yield memoire_compagnon
    with memoire_compagnon() as db:
        db.query(MessageSpontane).delete()
        db.commit()


def _message(db, user_id=CTX.user_id, potager_id=CTX.potager_id, texte="Les tomates ont soif.",
             il_y_a=timedelta(hours=2)):
    db.add(MessageSpontane(
        potager_id=potager_id, user_id=user_id, genre="signal", themes=["arrosage"], texte=texte,
        redige="gabarit", envoye_le=datetime.utcnow() - il_y_a,
    ))
    db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — le mode Support : le corpus de l'application d'abord, rien d'écrit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1ModeSupport:

    def test_ca1_support_impose_la_famille_doc_app_a_la_cascade(self, memoire_compagnon):
        cascade = routeur.ReponseCascade(texte="Dans Mon compagnon.", etage_resolveur="savoir", routage_log_id=9)
        with patch("llm.routeur.repondre_avec_cascade", return_value=cascade) as appel, \
             patch("llm.routeur.classer_demande") as classer:
            reponse = svc_echange.repondre(CTX, "où efface-t-on le carnet ?", mode="support")

        classer.assert_not_called()                      # ni classification, ni agent
        _, noyau = appel.call_args.args, appel.call_args.kwargs
        assert noyau["famille"] == connaissance.FAMILLE_DOC_APP
        assert noyau["decision"].nature == routeur.NATURE_QUESTION_SAVOIR
        assert reponse.vers == svc_echange.VERS_QUESTION and reponse.propositions == []
        assert reponse.texte == "Dans Mon compagnon." and reponse.routage_log_id == 9

    def test_ca1_support_ne_peut_rien_ecrire_meme_sur_une_phrase_de_geste(self, memoire_compagnon):
        cascade = routeur.ReponseCascade(texte="Voici l'aide.", etage_resolveur="savoir", routage_log_id=None)
        with patch("llm.routeur.repondre_avec_cascade", return_value=cascade), \
             patch("app.services.normalisation_gestes.parser_saisie") as parseur:
            reponse = svc_echange.repondre(CTX, "j'ai semé des radis sur la planche sud", mode="support")
        parseur.assert_not_called()
        assert reponse.propositions == []
        with memoire_compagnon() as db:
            assert db.query(Evenement).count() == 0

    def test_ca1_le_mode_normal_reste_le_defaut(self, memoire_compagnon):
        cascade = routeur.ReponseCascade(texte="12 kg.", etage_resolveur="data", routage_log_id=None)
        with patch("llm.routeur.classer_demande", return_value=routeur.DecisionRoutage(
                nature=routeur.NATURE_QUESTION_DATA, origine="regle", confiance=1.0)) as classer, \
             patch("llm.routeur.repondre_avec_cascade", return_value=cascade):
            svc_echange.repondre(CTX, "combien de kg de tomates ?")
        classer.assert_called_once()

    def test_ca1_un_mode_inconnu_est_refuse(self, memoire_compagnon):
        with pytest.raises(svc_echange.ModeInconnuError):
            svc_echange.repondre(CTX, "bonjour", mode="extra")

    def test_ca1_la_route_accepte_le_mode_et_refuse_l_inconnu(self, memoire_compagnon):
        from app.api.main import app, get_current_user_ctx

        app.dependency_overrides[get_current_user_ctx] = default_context
        cascade = routeur.ReponseCascade(texte="L'aide.", etage_resolveur="savoir", routage_log_id=None)
        try:
            with TestClient(app) as client, patch("llm.routeur.repondre_avec_cascade", return_value=cascade) as appel:
                ok = client.post("/compagnon/messages", json={"texte": "comment ça marche ?", "mode": "support"})
                assert ok.status_code == 200 and ok.json()["texte"] == "L'aide."
                assert appel.call_args.kwargs["famille"] == connaissance.FAMILLE_DOC_APP
                refus = client.post("/compagnon/messages", json={"texte": "bonjour", "mode": "extra"})
                assert refus.status_code == 422
        finally:
            app.dependency_overrides.pop(get_current_user_ctx, None)

    def test_ca1_la_cascade_sans_famille_garde_son_comportement(self):
        """Sans `famille`, la cascade appelle la recherche comme avant (aucun changement visible)."""
        import inspect

        assert inspect.signature(routeur.repondre_avec_cascade).parameters["famille"].default is None
        assert inspect.signature(svc_orchestrateur.repondre_a_une_question).parameters["nature"].default is None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — les messages spontanés rangés dans le panneau
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3MessagesSpontanes:

    def test_ca3_l_historique_porte_les_messages_spontanes(self, messages):
        with messages() as db:
            _message(db, texte="Les tomates ont soif.", il_y_a=timedelta(hours=5))
            _message(db, texte="Pense aux semis.", il_y_a=timedelta(hours=1))
        histoire = svc_echange.historique(CTX)
        assert [m["texte"] for m in histoire["spontanes"]] == ["Les tomates ont soif.", "Pense aux semis."]
        assert histoire["spontanes"][0]["themes"] == ["arrosage"] and histoire["spontanes"][0]["reagi"] is False

    def test_ca3_ils_sont_propres_au_jardinier_et_au_potager(self, messages):
        with messages() as db:
            _message(db, user_id=AUTRE_JARDINIER.user_id, texte="Pour un autre.")
            _message(db, potager_id=CTX.potager_id + 1, texte="Dans un autre potager.")
        assert svc_echange.historique(CTX)["spontanes"] == []
        assert svc_echange.historique(AUTRE_JARDINIER)["spontanes"][0]["texte"] == "Pour un autre."

    def test_ca3_au_plus_dix_messages_les_plus_recents(self, messages):
        with messages() as db:
            for i in range(14):
                _message(db, texte=f"message {i}", il_y_a=timedelta(minutes=100 - i))
        textes = [m["texte"] for m in svc_echange.historique(CTX)["spontanes"]]
        assert len(textes) == 10 and textes[-1] == "message 13" and textes[0] == "message 4"


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — les erreurs en clair
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4ErreursEnClair:

    def test_ca4_une_proposition_deja_traitee_dit_ou_et_quand(self, memoire_compagnon):
        from app.api.main import app, get_current_user_ctx
        from app.services import interpreteur_commandes as interp
        from app.services.compagnon import propositions as svc_propositions

        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")],
            {"nom": "Sud", "modification": "rangs=2"}, interp.ORIGINE_REGLE, 1.0, "x",
        )
        proposition = svc_propositions.proposer(CTX, commande, canal="telegram")
        svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE, canal="telegram")

        app.dependency_overrides[get_current_user_ctx] = default_context
        try:
            with TestClient(app) as client:
                reponse = client.post(f"/compagnon/propositions/{proposition.id}/abandonner")
        finally:
            app.dependency_overrides.pop(get_current_user_ctx, None)
        assert reponse.status_code == 409
        detail = reponse.json()["detail"]
        assert detail["code"] == "deja_traitee" and detail["etat"] == "abandonnee"
        assert "dans Telegram" in detail["message"] and "abandonnée" in detail["message"]
