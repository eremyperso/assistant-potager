"""
tests/test_us289_commande_pwa.py — Confirmer une commande dans la PWA [US-289]
==============================================================================
Une commande ou un plan qui a un exécuteur de service (`agent/executeurs` : `/parcelle ajouter`,
`/parcelle modifier`) se confirme dans le panneau compagnon, par le même service que le bot, sans
handler Telegram. Une forme sans exécuteur reste à Telegram.

Aucun appel réseau ni modèle.
"""
from __future__ import annotations

import pytest

from app.services import interpreteur_commandes as interp
from app.services.compagnon import decisions as svc_decisions
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import gestes_conversation as svc_gestes_dits
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext, default_context
from database.models import EchangeConversation, Evenement, Parcelle

CTX = default_context()


@pytest.fixture
def potager(memoire_compagnon, monkeypatch):
    """Une parcelle « Sud » ; les exécuteurs de plan ouvrent la même base que la fixture."""
    import database.db as base

    monkeypatch.setattr(base, "SessionLocal", memoire_compagnon)
    with memoire_compagnon() as db:
        db.add(Parcelle(nom="Sud", nom_normalise="sud", ordre=1, actif=True, potager_id=CTX.potager_id))
        db.commit()
    yield memoire_compagnon
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(EchangeConversation).delete()
        db.commit()


def _modifier(modification: str = "rangs=2") -> interp.CommandeInterpretee:
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", "modifier")],
        {"nom": "Sud", "modification": modification}, interp.ORIGINE_REGLE, 1.0, "passe la sud à 2 rangs",
    )


def _ajouter(nom: str) -> interp.CommandeInterpretee:
    return interp._construire_commande(
        interp.FORMES_PAR_CLE[("parcelle", "ajouter")], {"nom": nom}, interp.ORIGINE_REGLE, 1.0, f"ajoute {nom}",
    )


def _rangs(potager) -> int | None:
    with potager() as db:
        return db.query(Parcelle).filter(Parcelle.nom == "Sud").one().nb_rangs


class TestConfirmer:

    def test_ca1_la_carte_d_une_commande_executable_est_confirmable(self, potager):
        proposition = svc_propositions.proposer(CTX, _modifier(), canal="pwa")
        carte = svc_echange.carte_de_commande(proposition)
        assert carte["confirmable"] is True and carte["motif_non_confirmable"] is None

    def test_ca1_une_forme_sans_executeur_reste_a_telegram(self, potager):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "renommer")], {"ancien": "Sud", "nouveau": "Midi"}, interp.ORIGINE_REGLE, 1.0, "x",
        )
        carte = svc_echange.carte_de_commande(svc_propositions.proposer(CTX, commande, canal="pwa"))
        assert carte["confirmable"] is False and carte["motif_non_confirmable"] == svc_echange.TEXTE_COMMANDE_TELEGRAM

    def test_ca2_confirmer_ecrit_par_le_service_et_le_dit(self, potager):
        proposition = svc_propositions.proposer(CTX, _modifier(), canal="pwa")
        resultat = svc_echange.confirmer(CTX, proposition.id)

        assert resultat.erreur is None and resultat.texte.startswith("✅")
        assert resultat.carte["etat"] == svc_propositions.ETAT_CONFIRMEE
        assert _rangs(potager) == 2
        assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id) is None

    def test_ca2_la_seconde_confirmation_n_ecrit_rien(self, potager):
        proposition = svc_propositions.proposer(CTX, _modifier(), canal="pwa")
        svc_echange.confirmer(CTX, proposition.id)
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
            svc_echange.confirmer(CTX, proposition.id)
        assert refus.value.etat == svc_propositions.ETAT_CONFIRMEE

    def test_ca2_la_proposition_confirmee_ailleurs_n_ecrit_rien(self, potager):
        """Telegram est passé avant : la sortie atomique refuse la PWA, qui n'écrit rien."""
        proposition = svc_propositions.proposer(CTX, _modifier(), canal="pwa")
        svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal="telegram")
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
            svc_echange.confirmer(CTX, proposition.id)
        assert refus.value.canal == "telegram"
        assert _rangs(potager) is None

    def test_ca3_un_refus_du_service_est_dit_et_n_ecrit_rien(self, potager):
        proposition = svc_propositions.proposer(CTX, _modifier("rangs=beaucoup"), canal="pwa")
        resultat = svc_echange.confirmer(CTX, proposition.id)
        assert resultat.erreur and resultat.texte.startswith("❌")
        assert resultat.carte["etat"] == svc_echange.ETAT_ECHOUEE and resultat.carte["confirmable"] is False
        assert _rangs(potager) is None

    def test_ca3_un_lecteur_ne_modifie_rien(self, potager):
        lecteur = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id, role="viewer")
        proposition = svc_propositions.proposer(lecteur, _modifier(), canal="pwa")
        resultat = svc_echange.confirmer(lecteur, proposition.id)
        assert resultat.erreur and _rangs(potager) is None

    def test_ca4_un_plan_s_execute_etape_par_etape(self, potager):
        plan = interp.Plan(etapes=(_ajouter("Nord"), _modifier()))
        proposition = svc_propositions.proposer(CTX, plan, canal="pwa")
        assert svc_echange.carte_de_commande(proposition)["confirmable"] is True

        resultat = svc_echange.confirmer(CTX, proposition.id)
        assert resultat.erreur is None and "1." in resultat.texte and "2." in resultat.texte
        with potager() as db:
            assert {p.nom for p in db.query(Parcelle)} == {"Sud", "Nord"}
        assert _rangs(potager) == 2

    def test_ca5_vas_y_confirme_une_commande_executable(self, potager):
        proposition = svc_propositions.proposer(CTX, _modifier(), canal="pwa")
        reponse = svc_echange._decider(
            CTX, svc_decisions.Decision(svc_decisions.ACTION_CONFIRMER, proposition.code),
        )
        assert reponse.vers == svc_echange.VERS_DECISION and reponse.texte.startswith("✅")
        assert reponse.propositions[0]["etat"] == svc_propositions.ETAT_CONFIRMEE
        assert _rangs(potager) == 2

    def test_ca5_vas_y_ne_lance_jamais_une_action_destructrice(self, potager):
        proposition = svc_propositions.proposer(CTX, _modifier("actif=non"), canal="pwa")
        reponse = svc_echange._decider(
            CTX, svc_decisions.Decision(svc_decisions.ACTION_CONFIRMER, proposition.code),
        )
        assert reponse.texte == svc_decisions.TEXTE_BOUTON_SEUL
        assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id) is not None
        with potager() as db:
            assert db.query(Parcelle).filter(Parcelle.nom == "Sud").one().actif is True

    def test_ca5_vas_y_sur_une_forme_sans_executeur_renvoie_vers_telegram(self, potager):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "renommer")], {"ancien": "Sud", "nouveau": "Midi"}, interp.ORIGINE_REGLE, 1.0, "x",
        )
        proposition = svc_propositions.proposer(CTX, commande, canal="pwa")
        reponse = svc_echange._decider(
            CTX, svc_decisions.Decision(svc_decisions.ACTION_CONFIRMER, proposition.code),
        )
        assert reponse.texte == svc_echange.TEXTE_COMMANDE_TELEGRAM
