"""
tests/test_us211_deplacer_lot.py — Déplacer un lot d'une pépinière à l'autre [US-211]
======================================================================================

- CA1  le geste « deplacement » appartient au référentiel d'actions (US-168)
- CA2  il se dicte sans appel au modèle, sans être confondu avec plantation / mise en godet
- CA3  le lot est désigné par son numéro, par sa culture (un seul), ou choisi
- CA4  la destination est une pépinière, différente de l'emplacement courant
- CA5  récapitulatif, Journal : correction et suppression
- CA6  le déplacement est la première source de l'emplacement courant, à sa date
- CA7  aucun stock, aucun total ne bouge
- CA8  le cycle de vie du lot affiche le déplacement, avec origine et destination

Aucun appel réseau, aucun appel au modèle.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app.bot.enregistrement import _build_action_summary, _build_recap, _build_recap_tts
from app.services import evenements as svc_evenements
from app.services import lots_pepiniere as lots
from app.services import stats as svc_stats
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import parser_saisie
from utils.actions import ACTION_MAP, normalize_action
from utils.dependances_donnee import natures_impactees
from utils.parcelles import calcul_occupation_parcelles
from utils.stock import calcul_godets, calcul_lots_pepiniere
from utils.validation import ACTIONS_VALIDES

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.add(CultureConfig(nom="poireau", type_organe_recolte="végétatif"))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    test_db.add_all([
        Parcelle(id=1, nom="Planche nord", nom_normalise="planchenord", potager_id=1),
        Parcelle(id=2, nom="Serre", nom_normalise="serre", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude"),
        Parcelle(id=3, nom="Châssis froid", nom_normalise="chassisfroid", potager_id=1,
                 est_pepiniere=True, type_pepiniere="froide"),
    ])
    test_db.commit()
    return test_db


def _semis(db, culture="poireau", variete=None, parcelle_id=2, jour=1, numero=119, plants=41):
    e = Evenement(type_action="semis", culture=culture, variete=variete, quantite=100, unite="graines",
                  parcelle_id=parcelle_id, date=datetime(2026, 3, jour), potager_id=1, numero_lot=numero)
    db.add(e)
    db.commit()
    if plants:
        g = Evenement(type_action="mise_en_godet", culture=culture, variete=variete,
                      nb_plants_godets=plants, nb_graines_semees=plants, origine_graines_id=e.id,
                      date=datetime(2026, 3, jour + 9), potager_id=1)
        db.add(g)
        db.commit()
    return e


def _item(**champs) -> dict:
    return {"action": "deplacement", "parcelle": "Châssis froid", "date": "2026-04-28", **champs}


def _deplacer(db, semis, destination="Châssis froid", date_iso="2026-04-28", **champs):
    """Enregistre un déplacement par le chemin de confirmation du bot."""
    parsed = {"action": "deplacement", "parcelle": destination, "date": date_iso,
              "origine_graines_id": semis.id, **champs}
    parcelle = db.query(Parcelle).filter(Parcelle.nom == destination).first()
    return svc_evenements.creer_evenement_confirme(db, CTX, parsed, "passé le lot au châssis", parcelle)


def _lot(db, semis_id, **kw):
    return next(l for l in calcul_lots_pepiniere(db, potager_id=1, **kw) if l["semis_id"] == semis_id)


# ── CA1 — référentiel d'actions ──────────────────────────────────────────────

def test_us211_ca1_le_deplacement_est_au_referentiel():
    assert "deplacement" in ACTION_MAP
    assert "deplacement" in ACTIONS_VALIDES
    assert normalize_action("déplacé") == "deplacement"
    assert normalize_action("deplacement") == "deplacement"


def test_us211_ca1_il_ne_deplace_ni_stock_ni_plan():
    nat = natures_impactees("deplacement")
    assert "stock" not in nat and "plan" not in nat and "pepiniere" in nat


# ── CA2 — dictée déterministe ────────────────────────────────────────────────

class TestDictee:
    def _parse(self, db, phrase):
        return parser_saisie(phrase, CTX, db=db, aujourd_hui=date(2026, 4, 28))

    def test_us211_ca2_passe_le_lot_au_chassis(self, db):
        _semis(db)
        res = self._parse(db, "passé le lot 119 au châssis froid")
        assert res.reconnu, res.raison
        item = res.items[0]
        assert item["action"] == "deplacement"
        assert item["parcelle"] == "Châssis froid"
        assert item["numero_lot_cite"] == 119

    def test_us211_ca2_deplace_les_godets_de_culture(self, db):
        _semis(db)
        res = self._parse(db, "déplacé les godets de poireau sous le châssis froid")
        assert res.reconnu, res.raison
        item = res.items[0]
        assert (item["action"], item["culture"], item["parcelle"]) == ("deplacement", "poireau", "Châssis froid")

    def test_us211_ca2_sorti_de_la_serre_pour_le_chassis(self, db):
        _semis(db)
        res = self._parse(db, "sorti les poireaux de la serre pour le châssis froid")
        assert res.reconnu, res.raison
        item = res.items[0]
        assert (item["action"], item["culture"], item["parcelle"]) == ("deplacement", "poireau", "Châssis froid")

    def test_us211_ca2_pas_de_confusion_avec_la_plantation(self, db):
        _semis(db)
        res = self._parse(db, "planté 10 poireaux planche nord")
        assert res.reconnu, res.raison
        assert res.items[0]["action"] == "plantation"
        # « mis en terre » n'est jamais lu comme un déplacement, reconnu ou non
        res = self._parse(db, "mis en terre 10 poireaux planche nord")
        assert not res.reconnu or res.items[0]["action"] != "deplacement"

    def test_us211_ca2_pas_de_confusion_avec_la_mise_en_godet(self, db):
        _semis(db)
        res = self._parse(db, "mise en godet 40 poireaux sous le châssis froid")
        assert res.reconnu, res.raison
        assert res.items[0]["action"] == "mise_en_godet"
        assert res.items[0]["parcelle"] == "Châssis froid"
        res = self._parse(db, "repiqué 40 poireaux en godet sous le châssis froid")
        assert not res.reconnu or res.items[0]["action"] != "deplacement"

    def test_us211_ca2_sorti_sans_pepiniere_n_est_pas_un_deplacement(self, db):
        _semis(db)
        assert not self._parse(db, "sorti les poireaux").reconnu
        assert not self._parse(db, "sorti les poireaux dans la planche nord").reconnu

    def test_us211_ca2_sorti_de_la_serre_sans_destination_n_est_pas_un_deplacement(self, db):
        _semis(db)
        assert not self._parse(db, "sorti les poireaux de la serre").reconnu

    def test_us211_ca4_lot_cite_vers_une_parcelle_ordinaire_est_lu_puis_refuse(self, db):
        _semis(db)
        res = self._parse(db, "passé le lot 119 dans la planche nord")
        assert res.reconnu, res.raison
        assert res.items[0]["action"] == "deplacement"
        assert res.items[0]["parcelle"] == "Planche nord"


# ── Routage : « pépinière » n'en fait pas une question ───────────────────────

def test_us211_routeur_passe_le_lot_a_la_pepiniere_est_un_geste():
    from llm.routeur import annonce_un_geste, classer_par_regles
    for phrase in ("passé le lot 5 à la pépinière froide", "passé le lot 573 au châssis froid",
                   "sorti les poireaux de la serre pour le châssis"):
        assert classer_par_regles(phrase) == "ACTION", phrase
        assert annonce_un_geste(phrase), phrase


def test_us211_routeur_les_questions_restent_des_questions():
    from llm.routeur import classer_par_regles
    assert classer_par_regles("qu'est-ce qu'il y a en pépinière ?") != "ACTION"
    assert classer_par_regles("où en est le lot 5 ?") != "ACTION"


def test_us211_parseur_a_la_pepiniere_froide(db):
    db.add(Parcelle(id=9, nom="Pépinière froide", nom_normalise="pepiniere froide", potager_id=1,
                    est_pepiniere=True, type_pepiniere="froide"))
    db.commit()
    _semis(db)
    res = parser_saisie("passé le lot 119 à la pépinière froide", CTX, db=db, aujourd_hui=date(2026, 4, 28))
    assert res.reconnu, res.raison
    assert res.items[0]["action"] == "deplacement" and res.items[0]["parcelle"] == "Pépinière froide"


# ── CA3 — désignation du lot ─────────────────────────────────────────────────

def test_us211_ca3_par_numero(db):
    s = _semis(db)
    items = [_item(numero_lot_cite=119)]
    lots.resoudre_references(db, CTX, items)
    assert items[0]["origine_graines_id"] == s.id
    assert items[0]["culture"] == "poireau"
    event = svc_evenements.creer_evenement_confirme(
        db, CTX, items[0], "passé le lot 119 au châssis froid", db.get(Parcelle, 3),
    )
    assert event.type_action == "deplacement" and event.origine_graines_id == s.id
    assert event.parcelle_id == 3 and event.quantite is None


def test_us211_ca3_par_culture_quand_un_seul_lot(db):
    s = _semis(db)
    parsed = _item(culture="poireau")
    lot = svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    assert lot["semis_id"] == s.id
    assert parsed["origine_graines_id"] == s.id and parsed["_lot_numero"] == 119


def test_us211_ca3_plusieurs_lots_il_faut_choisir(db):
    _semis(db, numero=131, jour=1)
    _semis(db, numero=134, jour=5)
    with pytest.raises(svc_evenements.LotIndetermineError):
        svc_evenements.resoudre_lot_deplacement(db, CTX, _item(culture="poireau"))
    candidats = svc_evenements.lots_deplacables(db, CTX, "poireau")
    assert sorted(l["numero_lot"] for l in candidats) == [131, 134]


def test_us211_ca3_lot_inexistant_est_refuse_avec_la_raison(db):
    items = [_item(numero_lot_cite=999)]
    lots.resoudre_references(db, CTX, items)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="Aucun lot n° 999"):
        svc_evenements.resoudre_lot_deplacement(db, CTX, items[0])


def test_us211_ca3_aucun_lot_de_cette_culture(db):
    _semis(db, culture="poireau")
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="Aucun lot de « tomate »"):
        svc_evenements.resoudre_lot_deplacement(db, CTX, _item(culture="tomate"))


def test_us211_ca3_un_lot_sans_plants_n_est_plus_deplacable(db):
    _semis(db, plants=0)   # semé, rien levé, rien de repiqué : graines encore en germination
    assert len(svc_evenements.lots_deplacables(db, CTX, "poireau")) == 1
    s = _semis(db, culture="tomate", numero=120, plants=100)
    db.add(Evenement(type_action="vendu", culture="tomate", quantite=100, origine_graines_id=s.id,
                     date=datetime(2026, 4, 1), potager_id=1))
    db.commit()
    assert svc_evenements.lots_deplacables(db, CTX, "tomate") == []


def test_us211_ca3_lot_de_godets_sans_semis_rattache_par_culture(db):
    db.add(Evenement(type_action="mise_en_godet", culture="poireau", nb_plants_godets=20,
                     nb_graines_semees=20, parcelle_id=2, date=datetime(2026, 3, 10), potager_id=1))
    db.commit()
    parsed = _item(culture="poireau")
    parcelle = db.get(Parcelle, 3)
    event = svc_evenements.creer_evenement_confirme(db, CTX, parsed, "déplacé les poireaux au châssis", parcelle)
    assert event.origine_graines_id is None
    sans = next(l for l in calcul_lots_pepiniere(db, potager_id=1) if l["sans_semis_rattache"])
    assert sans["emplacement"]["nom"] == "Châssis froid"
    assert sans["emplacement"]["origine"] == "deplacement"


# ── CA4 — la destination ─────────────────────────────────────────────────────

def test_us211_ca4_parcelle_ordinaire_refusee_avec_rappel_de_la_plantation(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="plantation"):
        _deplacer(db, s, destination="Planche nord")
    assert db.query(Evenement).filter(Evenement.type_action == "deplacement").count() == 0


def test_us211_ca4_destination_identique_a_l_emplacement_courant(db):
    s = _semis(db, parcelle_id=2)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="déjà dans « Serre »"):
        _deplacer(db, s, destination="Serre")
    assert db.query(Evenement).filter(Evenement.type_action == "deplacement").count() == 0


def test_us211_ca4_destination_absente(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="va où"):
        svc_evenements.resoudre_lot_deplacement(db, CTX, {"action": "deplacement", "origine_graines_id": s.id})


def test_us211_ca4_destination_inconnue(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="Pépinières de votre potager"):
        svc_evenements.resoudre_lot_deplacement(
            db, CTX, {"action": "deplacement", "origine_graines_id": s.id, "parcelle": "Nulle part"},
        )


def test_us211_v1_le_deplacement_partiel_est_rouvert_par_l_us241(db):
    """La limite V1 « lot entier » est levée par US-241 (A32) : 20 godets sur 41 partent,
    le lot est coupé par l'emplacement (tests/test_us241_deplacement_partiel.py)."""
    s = _semis(db)
    _deplacer(db, s, quantite=20)
    lot = _lot(db, s.id)
    assert lot["reparti"]
    assert [(r["nom"], r["godets"]) for r in lot["repartition_godets"]] == [("Serre", 21), ("Châssis froid", 20)]


# ── CA5 — récapitulatif, Journal ─────────────────────────────────────────────

def test_us211_ca5_le_recapitulatif_dit_le_lot_d_ou_vers_ou(db):
    s = _semis(db)
    parsed = _item(culture="poireau", origine_graines_id=s.id)
    svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    resume = _build_action_summary([parsed])
    assert "déplacement du lot 119 (poireau) de la serre au châssis froid" in resume
    assert "C'est correct ?" in resume


def test_us211_ca5_le_recapitulatif_final_et_la_voix(db):
    parsed = {"action": "deplacement", "culture": "poireau", "_lot_numero": 119,
              "_emplacement_origine": "Serre", "parcelle": "Châssis froid", "date": "2026-04-28"}
    assert "déplacement du lot 119 (poireau) de la serre au châssis froid" in _build_recap(parsed, 77)
    assert _build_recap_tts(parsed).startswith("Déplacement du lot 119 (poireau)")


def test_us211_ca5_l_origine_inconnue_n_est_pas_devinee(db):
    s = _semis(db, parcelle_id=None)
    parsed = _item(culture="poireau", origine_graines_id=s.id)
    svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    resume = _build_action_summary([parsed])
    # [US-241 / CA13] L'origine inconnue est dite comme telle, jamais devinée.
    assert "déplacement du lot 119 (poireau), emplacement non renseigné, au châssis froid" in resume


def test_us211_ca5_correction_de_la_destination_au_journal(db):
    s = _semis(db)
    ev = _deplacer(db, s, destination="Châssis froid")
    assert _lot(db, s.id)["emplacement"]["nom"] == "Châssis froid"
    corrige = svc_evenements.corriger_evenement(db, CTX, ev.id, {"parcelle": "Serre", "_parcelle_id": 2}, " | c")
    assert corrige.parcelle_id == 2
    assert _lot(db, s.id)["emplacement"]["nom"] == "Serre"


def test_us211_ca5_correction_vers_une_parcelle_ordinaire_refusee(db):
    s = _semis(db)
    ev = _deplacer(db, s)
    with pytest.raises(svc_evenements.DeplacementRefuseError):
        svc_evenements.corriger_evenement(db, CTX, ev.id, {"parcelle": "Planche nord", "_parcelle_id": 1}, " | c")
    db.rollback()
    assert db.get(Evenement, ev.id).parcelle_id == 3


def test_us211_ca5_suppression_au_journal_rend_l_ancien_emplacement(db):
    s = _semis(db)
    ev = _deplacer(db, s)
    assert svc_evenements.supprimer_evenement(db, CTX, ev.id) is True
    emp = _lot(db, s.id)["emplacement"]
    assert emp["nom"] == "Serre" and emp["origine"] == "semis"


# ── CA6 — emplacement courant ────────────────────────────────────────────────

def test_us211_ca6_le_deplacement_est_la_premiere_source(db):
    s = _semis(db, parcelle_id=2)
    _deplacer(db, s, destination="Châssis froid")
    emp = _lot(db, s.id)["emplacement"]
    assert emp == {"parcelle_id": 3, "nom": "Châssis froid", "type_pepiniere": "froide",
                   "origine": "deplacement"}


def test_us211_ca6_il_l_emporte_sur_une_mise_en_godet_localisee(db):
    s = _semis(db, parcelle_id=2, plants=0)
    db.add(Evenement(type_action="mise_en_godet", culture="poireau", nb_plants_godets=30,
                     nb_graines_semees=30, origine_graines_id=s.id, parcelle_id=2,
                     date=datetime(2026, 3, 12), potager_id=1))
    db.commit()
    _deplacer(db, s, destination="Châssis froid", date_iso="2026-04-28")
    assert _lot(db, s.id)["emplacement"]["origine"] == "deplacement"


def test_us211_ca6_le_dernier_deplacement_l_emporte(db):
    s = _semis(db, parcelle_id=2)
    _deplacer(db, s, destination="Châssis froid", date_iso="2026-04-20")
    _deplacer(db, s, destination="Serre", date_iso="2026-04-25")
    assert _lot(db, s.id)["emplacement"]["nom"] == "Serre"


def test_us211_ca6_date_de_reference_anterieure_voit_l_ancien_emplacement(db):
    s = _semis(db, parcelle_id=2)
    _deplacer(db, s, destination="Châssis froid", date_iso="2026-09-20")
    avant = _lot(db, s.id, date_ref=date(2026, 9, 15))["emplacement"]
    apres = _lot(db, s.id, date_ref=date(2026, 9, 25))["emplacement"]
    assert avant["nom"] == "Serre" and avant["origine"] == "semis"
    assert apres["nom"] == "Châssis froid" and apres["origine"] == "deplacement"


def test_us211_ca6_un_deplacement_ne_touche_que_son_lot(db):
    s1 = _semis(db, numero=131, jour=1)
    s2 = _semis(db, numero=134, jour=3)
    _deplacer(db, s1)
    assert _lot(db, s1.id)["emplacement"]["nom"] == "Châssis froid"
    assert _lot(db, s2.id)["emplacement"]["nom"] == "Serre"


# ── CA7 — aucun stock ne bouge ───────────────────────────────────────────────

def _totaux(db):
    r = svc_stats.calculer_stats(db, CTX, None)
    return (
        repr(calcul_godets(db, include_epuises=True, potager_id=1)),
        repr(calcul_godets(db, potager_id=1)),
        repr(r.stocks), repr(r.godets), repr(r.semis), repr(r.cultures_avec_godet),
        r.total_evenements,
        repr(calcul_occupation_parcelles(db, potager_id=1)),
    )


def test_us211_ca7_aucun_stock_ni_total_ne_bouge(db):
    s = _semis(db)
    avant = _totaux(db)
    lot_avant = _lot(db, s.id)
    _deplacer(db, s)
    assert _totaux(db) == avant
    lot_apres = _lot(db, s.id)
    for cle in ("plants_obtenus", "stock_residuel_godet", "graines_semees", "graines_soldees",
                "nb_plantes", "nb_vendus", "nb_pertes_godet", "etat_germination"):
        assert lot_apres[cle] == lot_avant[cle], cle
    assert lot_apres["stock_residuel_godet"] == 41


def test_us211_ca7_le_plan_n_est_pas_modifie(db):
    s = _semis(db)
    avant = repr(calcul_occupation_parcelles(db, potager_id=1))
    _deplacer(db, s)
    assert repr(calcul_occupation_parcelles(db, potager_id=1)) == avant


# ── CA8 — cycle de vie ───────────────────────────────────────────────────────

def test_us211_ca8_le_cycle_de_vie_porte_le_deplacement(db):
    s = _semis(db, parcelle_id=2)
    _deplacer(db, s, destination="Châssis froid", date_iso="2026-04-20")
    _deplacer(db, s, destination="Serre", date_iso="2026-04-25")
    cycle = svc_evenements.cycle_vie_culture(db, CTX, "poireau", None, semis_id=s.id)
    deps = cycle["deplacements"]
    assert [(d["origine"], d["destination"]) for d in deps] == [("Serre", "Châssis froid"), ("Châssis froid", "Serre")]


def test_us211_ca8_un_lot_sans_deplacement_n_en_affiche_aucun(db):
    s = _semis(db)
    assert svc_evenements.cycle_vie_culture(db, CTX, "poireau", None, semis_id=s.id)["deplacements"] == []


def test_us211_ca8_le_deplacement_d_un_lot_n_apparait_pas_dans_celui_d_un_autre(db):
    s1 = _semis(db, numero=131, jour=1)
    s2 = _semis(db, numero=134, jour=3)
    _deplacer(db, s1)
    assert svc_evenements.cycle_vie_culture(db, CTX, "poireau", None, semis_id=s2.id)["deplacements"] == []
    assert len(svc_evenements.cycle_vie_culture(db, CTX, "poireau", None, semis_id=s1.id)["deplacements"]) == 1


# ── CA9 — gabarit pré-rempli reconnu par le parseur ──────────────────────────

def test_us211_ca9_le_deplacement_est_ouvert_a_la_pwa():
    from app.services.file_gestes import GESTES_OUVERTS_PWA
    assert "deplacement" in GESTES_OUVERTS_PWA
    assert set(GESTES_OUVERTS_PWA) <= set(ACTION_MAP)   # sous-ensemble strict du référentiel


def test_us211_ca9_la_phrase_a_dicter_est_lue_sans_modele(db):
    from app.services.file_gestes import phrase_a_dicter
    _semis(db)
    phrase = phrase_a_dicter({"action": "deplacement", "culture": "poireau", "parcelle": "Châssis froid"})
    res = parser_saisie(phrase, CTX, db=db, aujourd_hui=date(2026, 4, 28))
    assert res.reconnu, (phrase, res.raison)
    item = res.items[0]
    assert (item["action"], item["culture"], item["parcelle"]) == ("deplacement", "poireau", "Châssis froid")


def test_us211_ca9_le_lot_du_geste_pre_rempli_devient_le_lot_deplace(db):
    from types import SimpleNamespace
    from app.services.file_gestes import item_du_geste
    geste = SimpleNamespace(geste={"action": "deplacement", "culture": "poireau",
                                   "parcelle": "Châssis froid", "_lot_id": 42})
    item = item_du_geste(geste)
    assert item["origine_graines_id"] == 42 and "_lot_id" not in item


def test_us211_ca9_la_phrase_du_recapitulatif_relue_par_le_parseur(db):
    """La phrase que la PWA pré-remplit (« passé le lot 119 au châssis froid ») doit
    être lue par la grammaire déterministe — c'est le contrat du geste pré-rempli."""
    _semis(db)
    res = parser_saisie("passé le lot 119 au châssis froid", CTX, db=db, aujourd_hui=date(2026, 4, 28))
    assert res.reconnu and res.items[0]["action"] == "deplacement"


# ── Parcours du bot : refus motivé, choix du lot ─────────────────────────────

class _Reponses:
    def __init__(self):
        self.textes: list[str] = []
        self.claviers: list = []

    async def reply_text(self, texte, **kw):
        self.textes.append(texte)
        self.claviers.append(kw.get("reply_markup"))


def _update_factice():
    from types import SimpleNamespace
    msg = _Reponses()
    return SimpleNamespace(effective_message=msg, effective_user=SimpleNamespace(id=7)), msg


@pytest.fixture
def bot_db(db, monkeypatch):
    """Le bot ouvre ses propres sessions : on lui rend la session de test, sans la fermer."""
    from app.bot import godets
    monkeypatch.setattr(godets, "SessionLocal", lambda: _SessionNonFermee(db))
    monkeypatch.setattr(godets, "current_context", lambda: CTX)
    return db


class _SessionNonFermee:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, nom):
        return getattr(self._db, nom)

    def close(self):
        pass


@pytest.mark.asyncio
async def test_us211_bot_refus_motive_avant_le_recapitulatif(bot_db):
    from app.bot.godets import _preparer_deplacement
    _semis(bot_db)
    update, msg = _update_factice()
    parsed = _item(numero_lot_cite=119, parcelle="Planche nord")
    lots.resoudre_references(bot_db, CTX, [parsed])
    interrompu = await _preparer_deplacement(update, parsed, "passé le lot 119 dans la planche nord")
    assert interrompu is True
    assert "plantation" in msg.textes[0]


@pytest.mark.asyncio
async def test_us211_bot_un_seul_lot_le_flux_continue(bot_db):
    from app.bot.godets import _preparer_deplacement
    _semis(bot_db)
    update, msg = _update_factice()
    parsed = _item(culture="poireau")
    assert await _preparer_deplacement(update, parsed, "passé les poireaux au châssis froid") is False
    assert msg.textes == []
    assert parsed["_lot_numero"] == 119 and parsed["_emplacement_origine"] == "Serre"


@pytest.mark.asyncio
async def test_us211_bot_plusieurs_lots_propose_les_boutons(bot_db):
    from app.bot.etat import _DEPLACEMENT_LOT_PENDING
    from app.bot.godets import _preparer_deplacement
    _semis(bot_db, numero=131, jour=1)
    _semis(bot_db, numero=134, jour=5)
    update, msg = _update_factice()
    parsed = _item(culture="poireau")
    assert await _preparer_deplacement(update, parsed, "déplacé les poireaux sous le châssis froid") is True
    boutons = [b.callback_data for ligne in msg.claviers[0].inline_keyboard for b in ligne]
    assert len([b for b in boutons if b.startswith("deplot:")]) == 2 and "deplot_cancel" in boutons
    assert 7 in _DEPLACEMENT_LOT_PENDING
    _DEPLACEMENT_LOT_PENDING.clear()


# ── Destination dite par son type, ou par un nom composé (retour de terrain) ─

def _potager_serres(db):
    db.query(Parcelle).filter(Parcelle.id.in_([2, 3])).delete()
    db.add_all([
        Parcelle(id=2, nom="SERRE", nom_normalise="serre", potager_id=1, est_pepiniere=True, type_pepiniere="chaude"),
        Parcelle(id=3, nom="serre extérieure", nom_normalise="serreexterieure", potager_id=1,
                 est_pepiniere=True, type_pepiniere="froide"),
    ])
    db.commit()


@pytest.mark.parametrize("phrase", [
    "déplacé les godets de poireau à la pépinière froide",
    "déplacé les godets de poireau au châssis froid",
    "déplacé les godets de poireau à la serre extérieure",
])
def test_us211_destination_par_type_ou_nom_compose(db, phrase):
    _potager_serres(db)
    _semis(db, parcelle_id=2)
    res = parser_saisie(phrase, CTX, db=db, aujourd_hui=date(2026, 4, 28))
    assert res.reconnu, (phrase, res.raison)
    assert res.items[0]["parcelle"] == "serre extérieure"


def test_us211_destination_par_type_ambigue_n_est_pas_devinee(db):
    _potager_serres(db)
    db.add(Parcelle(id=4, nom="Abri nord", nom_normalise="abrinord", potager_id=1,
                    est_pepiniere=True, type_pepiniere="froide"))
    db.commit()
    from utils.parcelles import resolve_pepiniere_par_type
    assert resolve_pepiniere_par_type(db, "pépinière froide", 1) is None
    assert resolve_pepiniere_par_type(db, "pépinière chaude", 1).nom == "SERRE"


def test_us211_modele_dit_pepiniere_froide_resolu_par_le_type(db):
    _potager_serres(db)
    s = _semis(db, parcelle_id=2)
    parsed = {"action": "deplacement", "culture": "poireau", "parcelle": "pépinière froide"}
    svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    assert parsed["parcelle"] == "serre extérieure" and parsed["origine_graines_id"] == s.id


def test_us211_deplacer_de_l_us007_ne_capte_pas_un_lot():
    from utils.deplacer import is_deplacer_request
    assert not is_deplacer_request("déplacer les godets du lot 5 à la pépinière froide")
    assert is_deplacer_request("déplacer mes carottes sur la parcelle nord")


# ── Répartition graines / godets rendue lisible ──────────────────────────────

def _lot_reparti(db):
    """Semé à la serre (chaude), 20 godets posés au châssis froid, 30 graines à lever."""
    s = _semis(db, parcelle_id=2, plants=0)
    db.add(Evenement(type_action="mise_en_godet", culture="poireau", nb_plants_godets=20,
                     nb_graines_semees=20, origine_graines_id=s.id, parcelle_id=3,
                     date=datetime(2026, 3, 12), potager_id=1))
    db.commit()
    return s


def test_us211_repartition_graines_et_godets_distinctes(db):
    s = _lot_reparti(db)
    lot = _lot(db, s.id)
    assert lot["graines_emplacement"] == "Serre"
    assert lot["godets_par_emplacement"] == [{"nom": "Châssis froid", "plants": 20}]
    assert lot["emplacement"]["nom"] == "Châssis froid"   # inchangé : dernier emplacement dit


def test_us211_repartition_dite_dans_la_fiche_telegram(db):
    s = _lot_reparti(db)
    fiche = lots.formater_lot_telegram(_lot(db, s.id))
    assert "20 godet(s) : à *Châssis froid*" in fiche
    assert "Graines pas encore levées : à *Serre*" in fiche


def test_us211_repartition_un_seul_endroit_rien_a_dire(db):
    s = _semis(db, parcelle_id=2)   # 41 godets non localisés mais semis à la serre
    assert lots.repartition_lot(_lot(db, s.id)) == [] or "non précisé" in " ".join(lots.repartition_lot(_lot(db, s.id)))


def test_us211_repartition_apres_deplacement_tout_est_a_destination(db):
    s = _lot_reparti(db)
    _deplacer(db, s, destination="Serre", date_iso="2026-04-28")
    lot = _lot(db, s.id)
    assert lot["graines_emplacement"] == "Serre"
    assert lot["godets_par_emplacement"] == [{"nom": "Serre", "plants": 20}]
    assert lots.repartition_lot(lot) == []


def test_us211_repartition_les_totaux_ne_bougent_pas(db):
    s = _lot_reparti(db)
    avant = _totaux(db)
    lot = _lot(db, s.id)
    assert lot["stock_residuel_godet"] == 20 and lot["plants_obtenus"] == 20
    db.query(Evenement).filter(Evenement.type_action == "mise_en_godet").update({"parcelle_id": None})
    db.commit()
    assert _totaux(db) == avant


def test_us211_detail_du_lot_expose_la_parcelle_de_chaque_godet(db):
    s = _lot_reparti(db)
    cycle = svc_evenements.cycle_vie_culture(db, CTX, "poireau", None, semis_id=s.id)
    assert [g.parcelle_rel.nom for g in cycle["godets"]] == ["Châssis froid"]
