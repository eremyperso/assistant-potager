"""
tests/test_us210_godets_localises.py — Godets rattachés à leur pépinière [US-210]
=================================================================================

- CA1  pépinière dite → rattachée ; non dite → sans parcelle, rien n'est déduit
- CA2  parcelle ordinaire refusée avec proposition, jamais enregistrée
- CA3  la parcelle se corrige depuis le Journal (pépinière oui, ordinaire non)
- CA4  une mise en godet localisée n'est jamais une culture en place
- CA5  emplacement courant d'un lot : godet localisé > semis > non renseigné
- CA6  lot « godets sans semis rattaché »
- CA8  les totaux (stocks, godets, stats) ne bougent pas
- CA9  aucune reprise de l'existant

Aucun appel réseau, aucun appel au modèle.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.services import evenements as svc_evenements
from app.services import lots_pepiniere as lots
from app.services import stats as svc_stats
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import parser_saisie
from utils.parcelles import calcul_occupation_parcelles
from utils.stock import calcul_godets, calcul_lots_pepiniere

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.add(CultureConfig(nom="chou", type_organe_recolte="végétatif"))
    test_db.add(CultureConfig(nom="poireau", type_organe_recolte="végétatif"))
    test_db.add_all([
        Parcelle(id=1, nom="Planche nord", nom_normalise="planchenord", potager_id=1),
        Parcelle(id=2, nom="Serre", nom_normalise="serre", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude"),
        Parcelle(id=3, nom="Châssis froid", nom_normalise="chassisfroid", potager_id=1,
                 est_pepiniere=True, type_pepiniere="froide"),
    ])
    test_db.commit()
    return test_db


def _semis(db, culture="chou", parcelle_id=2, jour=1, **kw):
    e = Evenement(type_action="semis", culture=culture, quantite=100, unite="graines",
                  parcelle_id=parcelle_id, date=datetime(2026, 3, jour), potager_id=1, **kw)
    db.add(e)
    db.commit()
    return e


def _godet(db, culture="chou", parcelle=None, origine=None, jour=10, plants=40):
    parsed = {"culture": culture, "nb_graines_semees": plants, "nb_plants_godets": plants,
              "date": f"2026-03-{jour:02d}", "origine_graines_id": origine}
    if parcelle:
        parsed["parcelle"] = parcelle
    return svc_evenements.creer_evenement_godet(db, CTX, parsed, "mise en godet")


def _lot(db, semis_id=None, **kw):
    return next(l for l in calcul_lots_pepiniere(db, potager_id=1, **kw) if l["semis_id"] == semis_id)


# ── CA1 — pépinière dite, non dite ───────────────────────────────────────────

def test_us210_ca1_pepiniere_dite_est_rattachee(db):
    s = _semis(db)
    g = _godet(db, parcelle="Châssis froid", origine=s.id)
    assert g.parcelle_id == 3


def test_us210_ca1_pepiniere_dite_avec_un_nom_approximatif(db):
    s = _semis(db)
    assert _godet(db, parcelle="chassis froid", origine=s.id).parcelle_id == 3


def test_us210_ca1_non_dite_reste_sans_parcelle_meme_avec_une_seule_pepiniere(db):
    db.query(Parcelle).filter(Parcelle.id == 3).delete()
    db.commit()
    s = _semis(db)
    assert _godet(db, origine=s.id).parcelle_id is None   # rien n'est déduit


class TestParseur:
    def _parse(self, db, phrase):
        return parser_saisie(phrase, CTX, db=db, aujourd_hui=date(2026, 5, 1))

    def test_us210_ca1_sous_le_chassis_froid(self, db):
        res = self._parse(db, "mise en godet 40 choux sous le châssis froid")
        assert res.reconnu, res.raison
        item = res.items[0]
        assert item["action"] == "mise_en_godet"
        assert item["parcelle"] == "Châssis froid"

    def test_us210_ca1_dans_la_serre(self, db):
        res = self._parse(db, "mise en godet de 40 choux dans la serre")
        assert res.reconnu, res.raison
        assert res.items[0]["parcelle"] == "Serre"

    def test_us210_ca1_sans_lieu_pas_de_parcelle(self, db):
        res = self._parse(db, "mise en godet de 30 choux")
        assert res.reconnu, res.raison
        assert not res.items[0].get("parcelle")


# ── CA2 — parcelle ordinaire refusée avec proposition ────────────────────────

def test_us210_ca2_service_refuse_une_parcelle_ordinaire(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.ParcelleNonPepiniereError):
        _godet(db, parcelle="Planche nord", origine=s.id)
    assert db.query(Evenement).filter(Evenement.type_action == "mise_en_godet").count() == 0


def test_us210_ca2_service_refuse_une_parcelle_inconnue(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.ParcelleInconnueError):
        _godet(db, parcelle="Nulle part", origine=s.id)


def test_us210_ca2_recapitulatif_propose_les_pepinieres(db):
    items = [{"action": "mise_en_godet", "culture": "laitue", "parcelle": "planche nord",
              "nb_plants_godets": 20}]
    lots.controler_emplacements_godets(db, CTX, items)
    assert "parcelle" not in items[0]
    alerte = items[0]["_alerte_emplacement"]
    assert "Planche nord" in alerte and "n'est pas une pépinière" in alerte
    assert "Serre" in alerte and "Châssis froid" in alerte
    assert "sans emplacement" in alerte


def test_us210_ca2_une_pepiniere_dite_est_gardee_sous_son_nom_canonique(db):
    items = [{"action": "mise_en_godet", "culture": "chou", "parcelle": "chassis froid"}]
    lots.controler_emplacements_godets(db, CTX, items)
    assert items[0]["parcelle"] == "Châssis froid"
    assert "_alerte_emplacement" not in items[0]


def test_us210_ca2_les_autres_gestes_ne_sont_pas_touches(db):
    items = [{"action": "recolte", "culture": "chou", "parcelle": "planche nord"}]
    lots.controler_emplacements_godets(db, CTX, items)
    assert items[0]["parcelle"] == "planche nord" and "_alerte_emplacement" not in items[0]


def test_us210_ca2_sans_pepiniere_le_message_le_dit(db):
    db.query(Parcelle).filter(Parcelle.est_pepiniere.is_(True)).update(
        {"est_pepiniere": False, "type_pepiniere": None})
    db.commit()
    items = [{"action": "mise_en_godet", "culture": "chou", "parcelle": "serre"}]
    lots.controler_emplacements_godets(db, CTX, items)
    assert "pas encore de pépinière" in items[0]["_alerte_emplacement"]


def test_us210_ca2_le_recapitulatif_affiche_l_alerte(db):
    from app.bot.enregistrement import _build_action_summary
    items = [{"action": "mise_en_godet", "culture": "laitue", "parcelle": "planche nord",
              "nb_plants_godets": 20}]
    lots.controler_emplacements_godets(db, CTX, items)
    assert "n'est pas une pépinière" in _build_action_summary(items)


# ── CA3 — correction depuis le Journal ───────────────────────────────────────

def test_us210_ca3_corriger_vers_une_pepiniere(db):
    s = _semis(db)
    g = _godet(db, origine=s.id)
    ev = svc_evenements.corriger_evenement(db, CTX, g.id, {"parcelle": "Serre", "_parcelle_id": 2}, " | corr")
    assert ev.parcelle_id == 2
    assert _lot(db, s.id)["emplacement"]["nom"] == "Serre"


def test_us210_ca3_corriger_vers_une_parcelle_ordinaire_est_refuse(db):
    s = _semis(db)
    g = _godet(db, origine=s.id)
    with pytest.raises(svc_evenements.ParcelleNonPepiniereError):
        svc_evenements.corriger_evenement(db, CTX, g.id, {"parcelle": "Planche nord", "_parcelle_id": 1}, " | c")
    db.rollback()
    assert db.get(Evenement, g.id).parcelle_id is None


def test_us210_ca3_retirer_la_pepiniere(db):
    s = _semis(db)
    g = _godet(db, parcelle="Serre", origine=s.id)
    ev = svc_evenements.corriger_evenement(db, CTX, g.id, {"parcelle": None}, " | c")
    assert ev.parcelle_id is None


# ── CA4 — jamais une culture en place ────────────────────────────────────────

def test_us210_ca4_une_mise_en_godet_localisee_n_occupe_aucune_parcelle(db):
    s = _semis(db)
    _godet(db, parcelle="Châssis froid", origine=s.id)
    _godet(db, parcelle="Serre", origine=s.id, jour=11)
    occupation = calcul_occupation_parcelles(db, potager_id=1)
    cultures = [ligne["culture"] for lignes in occupation.values() for ligne in lignes]
    assert "chou" not in cultures
    assert not any(k and k.lower() in ("serre", "châssis froid", "chassis froid") for k in occupation)


# ── CA5 / CA6 — emplacement courant ──────────────────────────────────────────

def test_us210_ca5_godet_localise_l_emporte_sur_le_semis(db):
    s = _semis(db, parcelle_id=2)
    _godet(db, parcelle="Châssis froid", origine=s.id)
    emp = _lot(db, s.id)["emplacement"]
    assert emp == {"parcelle_id": 3, "nom": "Châssis froid", "type_pepiniere": "froide",
                   "origine": "mise_en_godet"}


def test_us210_ca5_sans_godet_localise_c_est_le_semis(db):
    s = _semis(db, parcelle_id=2)
    _godet(db, origine=s.id)
    emp = _lot(db, s.id)["emplacement"]
    assert emp["nom"] == "Serre" and emp["type_pepiniere"] == "chaude" and emp["origine"] == "semis"


def test_us210_ca5_semis_sans_parcelle_est_non_renseigne(db):
    s = _semis(db, parcelle_id=None)
    emp = _lot(db, s.id)["emplacement"]
    assert emp["origine"] == "non_renseigne" and emp["nom"] is None and emp["parcelle_id"] is None


def test_us210_ca5_pas_de_supposition_meme_avec_une_seule_pepiniere(db):
    db.query(Parcelle).filter(Parcelle.id == 3).delete()
    db.commit()
    s = _semis(db, parcelle_id=None)
    assert _lot(db, s.id)["emplacement"]["origine"] == "non_renseigne"


def test_us210_ca5_le_dernier_emplacement_dit_l_emporte(db):
    s = _semis(db)
    _godet(db, parcelle="Serre", origine=s.id, jour=10, plants=20)
    _godet(db, parcelle="Châssis froid", origine=s.id, jour=12, plants=20)
    assert _lot(db, s.id)["emplacement"]["nom"] == "Châssis froid"
    # un godet NON localisé, plus récent, ne retire pas l'emplacement dit
    _godet(db, origine=s.id, jour=14, plants=10)
    assert _lot(db, s.id)["emplacement"]["nom"] == "Châssis froid"


def test_us210_ca5_date_de_reference_anterieure_a_la_mise_en_godet(db):
    s = _semis(db, parcelle_id=2)
    _godet(db, parcelle="Châssis froid", origine=s.id, jour=20)
    avant = _lot(db, s.id, date_ref=date(2026, 3, 15))["emplacement"]
    apres = _lot(db, s.id, date_ref=date(2026, 3, 25))["emplacement"]
    assert avant["nom"] == "Serre" and avant["origine"] == "semis"
    assert apres["nom"] == "Châssis froid" and apres["origine"] == "mise_en_godet"


def test_us210_ca6_lot_sans_semis_rattache(db):
    _godet(db, culture="poireau", parcelle="Châssis froid", jour=5)
    _godet(db, culture="poireau", jour=6)
    sans = next(l for l in calcul_lots_pepiniere(db, potager_id=1) if l["sans_semis_rattache"])
    assert sans["emplacement"]["nom"] == "Châssis froid"


def test_us210_ca6_lot_sans_semis_et_sans_emplacement(db):
    _godet(db, culture="poireau")
    sans = next(l for l in calcul_lots_pepiniere(db, potager_id=1) if l["sans_semis_rattache"])
    assert sans["emplacement"]["origine"] == "non_renseigne"


def test_us210_ca5_la_fiche_telegram_dit_l_emplacement_courant(db):
    s = _semis(db, parcelle_id=2)
    _godet(db, parcelle="Châssis froid", origine=s.id)
    fiche = lots.formater_lot_telegram(_lot(db, s.id) | {"numero_lot": 1})
    assert "Emplacement : *Châssis froid*" in fiche


def test_us210_ca5_l_api_expose_l_emplacement(db):
    from app.api.main import _lot_pepiniere_json
    s = _semis(db)
    _godet(db, parcelle="Châssis froid", origine=s.id)
    rendu = _lot_pepiniere_json(_lot(db, s.id), {})
    assert rendu["emplacement"]["type_pepiniere"] == "froide"
    assert rendu["emplacement"]["origine"] == "mise_en_godet"


# ── CA8 — les totaux ne bougent pas ──────────────────────────────────────────

def _totaux(db):
    r = svc_stats.calculer_stats(db, CTX, None)
    return (
        repr(calcul_godets(db, include_epuises=True, potager_id=1)),
        repr(calcul_godets(db, potager_id=1)),
        repr(r.stocks), repr(r.godets), repr(r.cultures_avec_godet),
        repr(calcul_occupation_parcelles(db, potager_id=1)),
    )


def test_us210_ca8_les_totaux_sont_identiques_localises_ou_non(db):
    s = _semis(db)
    _godet(db, parcelle="Châssis froid", origine=s.id, jour=10, plants=40)
    _godet(db, parcelle="Serre", origine=s.id, jour=11, plants=20)
    _godet(db, origine=s.id, jour=12, plants=10)
    localises = _totaux(db)

    db.query(Evenement).filter(Evenement.type_action == "mise_en_godet").update({"parcelle_id": None})
    db.commit()
    assert _totaux(db) == localises


def test_us210_ca8_le_total_du_lot_ne_depend_pas_de_la_pepiniere(db):
    s = _semis(db)
    _godet(db, parcelle="Châssis froid", origine=s.id, jour=10, plants=40)
    _godet(db, origine=s.id, jour=12, plants=20)
    lot = _lot(db, s.id)
    assert lot["plants_obtenus"] == 60 and lot["stock_residuel_godet"] == 60


# ── CA9 — aucune reprise de l'existant ───────────────────────────────────────

def test_us210_ca9_les_godets_existants_restent_sans_parcelle(db):
    s = _semis(db, parcelle_id=2)
    ancien = Evenement(type_action="mise_en_godet", culture="chou", nb_plants_godets=30,
                       nb_graines_semees=30, origine_graines_id=s.id,
                       date=datetime(2026, 3, 9), potager_id=1)
    db.add(ancien)
    db.commit()
    assert db.get(Evenement, ancien.id).parcelle_id is None
    assert _lot(db, s.id)["emplacement"]["nom"] == "Serre"   # lu depuis le semis
