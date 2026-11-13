"""
tests/test_us332_retrait_parcelle.py — [US-332] Créer, rendre inactive ou supprimer une parcelle avec Gaston
===========================================================================================================
Le bilan (cultures en place, lots, historique) décide : une parcelle qui a vécu se rend inactive, elle ne se
supprime jamais ; une parcelle vide se supprime réellement. La création posée dans l'éditeur n'écrit
qu'après « Confirmer ». Aucun appel réseau ni modèle.
"""
from __future__ import annotations

import pytest

from app.services import interpreteur_commandes as interp
from app.services import plan_gaston as svc_plan_gaston
from app.services import retrait_parcelle as svc_retrait
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext, default_context
from app.services.permissions import PermissionInsuffisanteError
from database.models import EchangeConversation, Evenement, Parcelle

CTX = default_context()
LECTEUR = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id, role="lecteur")


@pytest.fixture
def potager(memoire_compagnon, monkeypatch):
    """Deux parcelles : « Centrale » (qui a vécu) et « Planche 9 » (créée par erreur, vide)."""
    import database.db as base

    monkeypatch.setattr(base, "SessionLocal", memoire_compagnon)
    with memoire_compagnon() as db:
        centrale = Parcelle(nom="Centrale", nom_normalise="centrale", ordre=1, actif=True, potager_id=CTX.potager_id)
        vide = Parcelle(nom="Planche 9", nom_normalise="planche9", ordre=2, actif=True, potager_id=CTX.potager_id)
        db.add_all([centrale, vide])
        db.flush()
        db.add(Evenement(type_action="plantation", culture="tomate", quantite=8, unite="plants",
                         parcelle_id=centrale.id, potager_id=CTX.potager_id))
        db.commit()
    yield memoire_compagnon
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(EchangeConversation).delete()
        db.commit()


def _parcelle(potager, nom):
    with potager() as db:
        return db.query(Parcelle).filter(Parcelle.nom == nom).first()


# ── Le bilan (R2, R6) ────────────────────────────────────────────────────────
def test_r2_le_bilan_dit_ce_que_la_parcelle_porte(potager):
    with potager() as db:
        centrale = db.query(Parcelle).filter(Parcelle.nom == "Centrale").one()
        vide = db.query(Parcelle).filter(Parcelle.nom == "Planche 9").one()
        b_centrale, b_vide = svc_retrait.bilan(db, CTX, centrale), svc_retrait.bilan(db, CTX, vide)
    assert b_centrale["vide"] is False and b_centrale["nb_gestes"] == 1
    assert b_vide["vide"] is True and b_vide["nb_gestes"] == 0


# ── Supprimer (R4, CA3, CA5) ─────────────────────────────────────────────────
def test_ca3_une_parcelle_qui_a_vecu_n_est_jamais_supprimee(potager):
    with potager() as db:
        with pytest.raises(svc_retrait.ParcelleNonVideError) as erreur:
            svc_retrait.supprimer(db, CTX, "Centrale")
    assert "je ne la supprime pas" in str(erreur.value) and "rendre inactive" in str(erreur.value)
    assert _parcelle(potager, "Centrale") is not None


def test_ca5_la_suppression_d_une_parcelle_vide_est_reelle(potager):
    with potager() as db:
        assert "supprimée" in svc_retrait.supprimer(db, CTX, "Planche 9")
    assert _parcelle(potager, "Planche 9") is None


def test_ca5_une_parcelle_d_un_autre_potager_est_introuvable(potager):
    autre = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id + 99, role="owner")
    with potager() as db:
        with pytest.raises(LookupError):
            svc_retrait.supprimer(db, autre, "Planche 9")


def test_ca6_un_lecteur_ne_supprime_ni_n_inactive(potager):
    with potager() as db:
        with pytest.raises(PermissionInsuffisanteError):
            svc_retrait.supprimer(db, LECTEUR, "Planche 9")
        with pytest.raises(PermissionInsuffisanteError):
            svc_retrait.inactiver(db, LECTEUR, "Centrale")


# ── Rendre inactive (R3, R5, CA4) ────────────────────────────────────────────
def test_r5_inactive_garde_son_historique_et_se_reactive(potager):
    with potager() as db:
        svc_retrait.inactiver(db, CTX, "Centrale")
    centrale = _parcelle(potager, "Centrale")
    assert centrale.actif is False
    with potager() as db:
        assert db.query(Evenement).filter(Evenement.parcelle_id == centrale.id).count() == 1
        svc_retrait.reactiver(db, CTX, "Centrale")
    assert _parcelle(potager, "Centrale").actif is True


def test_ca4_une_parcelle_inactive_sort_des_choix_d_un_nouveau_geste(potager):
    from utils.parcelles import get_all_parcelles, resolve_parcelle

    with potager() as db:
        svc_retrait.inactiver(db, CTX, "Centrale")
        assert resolve_parcelle(db, "Centrale", potager_id=CTX.potager_id) is None
        assert "Centrale" not in [p.nom for p in get_all_parcelles(db, potager_id=CTX.potager_id)]


# ── La demande du plan devient une carte (R1, R2, R3, CA1) ───────────────────
def test_r3_rendre_inactive_ou_supprimer_propose_l_inactivation_pour_une_parcelle_qui_a_vecu(potager):
    centrale = _parcelle(potager, "Centrale")
    reponse = svc_echange.repondre(CTX, "Rendre inactive ou supprimer Centrale", plan={
        "action": "retirer", "parcelle_id": centrale.id})
    carte = reponse.propositions[0]
    assert "je ne la supprime pas" in reponse.texte and "rendre inactive" in reponse.texte
    assert carte["lignes"] == ["/parcelle modifier Centrale actif=non"]
    assert any("Historique et rotation conservés" in ligne for ligne in carte["avertissements"])
    assert carte["confirmable"] is True and _parcelle(potager, "Centrale").actif is True   # rien n'est écrit


def test_r4_une_parcelle_vide_se_propose_a_la_suppression(potager):
    vide = _parcelle(potager, "Planche 9")
    reponse = svc_echange.repondre(CTX, "Supprimer", plan={"action": "retirer", "parcelle_id": vide.id})
    assert reponse.propositions[0]["lignes"] == ["/parcelle supprimer Planche 9"]
    assert "ni culture ni historique" in reponse.texte


def test_r4_confirmer_supprime_pour_de_vrai(potager):
    vide = _parcelle(potager, "Planche 9")
    carte = svc_echange.repondre(CTX, "Supprimer", plan={"action": "retirer", "parcelle_id": vide.id}).propositions[0]
    svc_echange.confirmer(CTX, carte["id"])
    assert _parcelle(potager, "Planche 9") is None


def test_ca3_une_culture_plantee_entre_la_carte_et_la_confirmation_bloque_la_suppression(potager):
    vide = _parcelle(potager, "Planche 9")
    carte = svc_echange.repondre(CTX, "Supprimer", plan={"action": "retirer", "parcelle_id": vide.id}).propositions[0]
    with potager() as db:
        db.add(Evenement(type_action="semis", culture="radis", parcelle_id=vide.id, potager_id=CTX.potager_id))
        db.commit()
    resultat = svc_echange.confirmer(CTX, carte["id"])
    assert resultat.erreur and "je ne la supprime pas" in resultat.erreur
    assert _parcelle(potager, "Planche 9") is not None


def test_ca6_un_lecteur_ne_peut_rien_demander_au_plan(potager):
    centrale = _parcelle(potager, "Centrale")
    with pytest.raises(PermissionInsuffisanteError):
        svc_echange.repondre(LECTEUR, "x", plan={"action": "retirer", "parcelle_id": centrale.id})


def test_ca1_les_phrases_comprises_par_le_compagnon():
    """Créer, rendre inactive, supprimer : trois intentions, mêmes cartes dans la PWA et Telegram."""
    inactive = interp.interpreter("rends inactive la parcelle planche centrale")
    assert (inactive.forme.cle, inactive.valeurs["modification"]) == (("parcelle", "modifier"), "actif=non")
    assert interp.interpreter("réactive la parcelle serre").valeurs["modification"] == "actif=oui"
    assert interp.interpreter("supprime la parcelle planche 9").forme.cle == ("parcelle", "supprimer")
    assert interp.interpreter("crée une parcelle planche 9").forme.cle == ("parcelle", "ajouter")


# ── Créer en la posant (R1, CA2) ─────────────────────────────────────────────
POSEE = {"action": "creer", "forme": "planche", "longueur_m": 3.5, "largeur_m": 3, "x_m": 4, "y_m": 2,
         "sens_rangs": "longueur"}


def test_r1_poser_une_forme_nouvelle_propose_la_carte_et_n_ecrit_rien(potager):
    avant = len(_noms(potager))
    reponse = svc_echange.repondre(CTX, "Créer une planche", plan=POSEE)
    carte = reponse.propositions[0]
    assert carte["lignes"][0].startswith("/parcelle ajouter Planche 3")
    assert any("planche de 3,5 × 3 m · 10,5 m²" in ligne for ligne in carte["avertissements"])
    assert len(_noms(potager)) == avant                        # rien n'existe avant « Confirmer »


def _noms(potager):
    with potager() as db:
        return [p.nom for p in db.query(Parcelle).all()]


def test_ca2_confirmer_cree_la_parcelle_avec_sa_geometrie(potager):
    carte = svc_echange.repondre(CTX, "Créer une planche", plan=POSEE).propositions[0]
    svc_echange.confirmer(CTX, carte["id"])
    creee = _parcelle(potager, "Planche 3")
    assert (creee.forme, creee.x_m, creee.y_m, creee.largeur_m, creee.longueur_m) == ("planche", 4.0, 2.0, 3.0, 3.5)
    assert creee.sens_rangs == "longueur" and creee.superficie_m2 == 10.5


def test_ca2_le_nom_propose_est_unique(potager):
    with potager() as db:
        assert svc_plan_gaston.nom_propose(db, CTX, "planche") == "Planche 3"
        db.add(Parcelle(nom="Planche 3", nom_normalise="planche3", ordre=9, actif=False, potager_id=CTX.potager_id))
        db.commit()
        assert svc_plan_gaston.nom_propose(db, CTX, "planche") != "Planche 3"


def test_ca2_une_geometrie_invalide_est_refusee_avant_la_carte(potager):
    with pytest.raises(svc_plan_gaston.DemandePlanInvalideError):
        svc_echange.repondre(CTX, "x", plan={**POSEE, "forme": "château"})
    assert "Planche 3" not in _noms(potager)


def test_codec_de_la_geometrie_est_reversible():
    champs = {"forme": "bac", "longueur_m": 2.0, "largeur_m": 1.0, "x_m": 1.5, "y_m": 0.5, "nb_rangs": 2}
    assert svc_plan_gaston.decoder(svc_plan_gaston.encoder(champs)) == champs
