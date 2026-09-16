"""
tests/test_us070_calendrier_recale.py — Calendrier recalé sur les événements réels [US-070]
=========================================================================================

Volet serveur : `app/services/recalage_calendrier.py` et le bloc `projections`
de `GET /plan/calendriers`. Le volet d'affichage (cinquième état de la frise,
libellés au conditionnel) est couvert par `frontend/src/lib/calendrier.test.js`.

Les fenêtres et durées sont des VALEURS DE TEST, pas des données agronomiques.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import import_referentiel as svc_import
from app.services import recalage_calendrier as rec
from database.db import Base
from database.models import CultureConfig, Evenement, Parcelle, Potager, User


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.add(User(id=2, email="b@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.add(Potager(id=2, nom="Jardin B", proprietaire_id=2, zone_climatique="oceanique"))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="sud", nom_normalise="sud", potager_id=1),
        Parcelle(id=3, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _source():
    return {"code": "wikidata", "libelle": "Source de test", "licence": "CC0",
            "attribution": "Source de test", "url": "https://example.org/", "partageable": True}


def _referentiel(db, culture, organe="reproducteur", **entree):
    db.add(CultureConfig(nom=culture, type_organe_recolte=organe, potager_id=None))
    db.commit()
    svc_import.importer(db, {"source": _source(),
                             "cultures_calendriers": [{"culture": culture, **entree}]})


def _evt(db, action, culture, jour, parcelle_id=1, **champs):
    evenement = Evenement(type_action=action, culture=culture, date=datetime.combine(jour, datetime.min.time()),
                          parcelle_id=parcelle_id, potager_id=champs.pop("potager_id", 1), **champs)
    db.add(evenement)
    db.commit()
    return evenement


def _projection(db, culture, date_ref, potager_id=1, **filtre):
    projections = [
        p for p in rec.projections_du_plan(db, [culture], potager_id, date_ref)
        if all(p[k] == v for k, v in filtre.items())
    ]
    assert len(projections) == 1, projections
    return projections[0]


@pytest.fixture
def courgette(db):
    """Gherkin : courgette, 10 jours jusqu'à la levée, 95 jusqu'à la récolte."""
    _referentiel(db, "courgette", durees={"levee": "10", "recolte": "95"},
                 fenetres={"oceanique": {"semis_pleine_terre": "avril-juin", "recolte": "juin-octobre"}})
    _evt(db, "semis", "courgette", date(2026, 4, 12), contexte_semis="pleine_terre")
    return db


@pytest.fixture
def tomate(db):
    _referentiel(db, "tomate", durees={"levee": "7-10", "repiquage": "42-56", "recolte": "120-140"},
                 fenetres={"oceanique": {"semis_pepiniere": "mars-avril", "recolte": "juillet-octobre"}})
    return db


def _filiere_pepiniere(db, semis_le, plante_le, contexte="pepiniere"):
    semis = _evt(db, "semis", "tomate", semis_le, parcelle_id=3, contexte_semis=contexte)
    godet = _evt(db, "mise_en_godet", "tomate", semis_le + timedelta(days=15), parcelle_id=3,
                 origine_graines_id=semis.id)
    return _evt(db, "plantation", "tomate", plante_le, parcelle_id=1, source_evenement_ids=str(godet.id))


# ── CA1 / CA2 / CA3 — ancrage sur un semis en pleine terre ───────────────────
def test_us070_ca2_levee_et_recolte_attendues_depuis_le_semis_reel(courgette):
    p = _projection(courgette, "courgette", date(2026, 6, 15))
    assert p["origine"] == {"action": "semis", "date": "2026-04-12", "contexte": "pleine_terre"}
    assert p["levee_attendue"] == {"debut": "2026-04-22", "fin": "2026-04-22"}
    assert p["recolte_attendue"] == {"debut": "2026-07-16", "fin": "2026-07-16"}
    assert p["etat"] == rec.ETAT_A_VENIR


def test_us070_ca3_duree_restante_en_jours(courgette):
    assert _projection(courgette, "courgette", date(2026, 6, 15))["jours_restants"] == {"min": 31, "max": 31}


def test_us070_ca3_une_fourchette_reste_une_fourchette(db):
    _referentiel(db, "haricot", durees={"recolte": "55-75"},
                 fenetres={"oceanique": {"semis_pleine_terre": "mai-juillet"}})
    _evt(db, "semis", "haricot", date(2026, 5, 2), contexte_semis="pleine_terre")
    p = _projection(db, "haricot", date(2026, 6, 1))
    assert p["recolte_attendue"] == {"debut": "2026-06-26", "fin": "2026-07-16"}
    assert p["jours_restants"] == {"min": 25, "max": 45}


def test_us070_ca3_dans_la_fourchette_le_reste_part_de_zero(db):
    _referentiel(db, "haricot", durees={"recolte": "55-75"})
    _evt(db, "semis", "haricot", date(2026, 5, 2), contexte_semis="pleine_terre")
    p = _projection(db, "haricot", date(2026, 7, 1))
    assert p["etat"] == rec.ETAT_RECOLTE_ATTENDUE
    assert p["jours_restants"] == {"min": 0, "max": 15}


# ── CA7 — quatre états sur la frise ──────────────────────────────────────────
def test_us070_ca7_frise_semis_croissance_recolte(courgette):
    mois = _projection(courgette, "courgette", date(2026, 6, 15))["mois"]
    assert mois["semis_pleine_terre"] == [4]
    assert mois["croissance"] == [5, 6]
    assert mois["recolte"] == [7, 8, 9, 10]
    assert mois["semis_pepiniere"] == [] and mois["plantation"] == []


def test_us070_ca7_croissance_ne_chevauche_aucun_autre_etat(tomate):
    _filiere_pepiniere(tomate, date(2026, 3, 15), date(2026, 5, 10))
    mois = _projection(tomate, "tomate", date(2026, 6, 1))["mois"]
    assert mois["semis_pepiniere"] == [3]
    assert mois["plantation"] == [5]
    assert mois["croissance"] == [4, 6]
    autres = set(mois["semis_pepiniere"]) | set(mois["plantation"]) | set(mois["recolte"])
    assert not set(mois["croissance"]) & autres


# ── CA1 / CA4 — filière pépinière ────────────────────────────────────────────
def test_us070_ca1_origine_retrouvee_par_le_chainage(tomate):
    _filiere_pepiniere(tomate, date(2026, 3, 15), date(2026, 5, 10))
    p = _projection(tomate, "tomate", date(2026, 6, 1))
    assert p["origine"] == {"action": "semis", "date": "2026-03-15", "contexte": "pepiniere"}
    assert p["plantation_reelle"] == "2026-05-10"
    # 15 mars + 56 jours = 10 mai : dans le délai de repiquage, aucun décalage.
    assert p["decalage_plantation_jours"] == 0
    assert p["recolte_attendue"] == {"debut": "2026-07-13", "fin": "2026-08-02"}


def test_us070_ca4_plantation_tardive_decale_la_recolte(tomate):
    _filiere_pepiniere(tomate, date(2026, 3, 15), date(2026, 5, 24))
    p = _projection(tomate, "tomate", date(2026, 6, 1))
    assert p["decalage_plantation_jours"] == 14
    assert p["recolte_attendue"] == {"debut": "2026-07-27", "fin": "2026-08-16"}


def test_us070_ca4_plantation_precoce_avance_la_recolte(tomate):
    _filiere_pepiniere(tomate, date(2026, 3, 15), date(2026, 4, 19))
    p = _projection(tomate, "tomate", date(2026, 6, 1))
    # Au plus tôt conseillé : 15 mars + 42 = 26 avril, planté 7 jours avant.
    assert p["decalage_plantation_jours"] == -7


def test_us070_ca1_semis_chaine_sans_contexte_est_une_pepiniere(tomate):
    """La mise en godet chaînée PROUVE la pépinière (même règle que migration_v47)."""
    _filiere_pepiniere(tomate, date(2026, 3, 15), date(2026, 5, 10), contexte=None)
    p = _projection(tomate, "tomate", date(2026, 6, 1))
    assert p["etat"] == rec.ETAT_A_VENIR
    assert p["origine"]["contexte"] == "pepiniere"


def test_us070_ca1_plusieurs_plantations_d_un_meme_semis_font_une_serie(tomate):
    plantation = _filiere_pepiniere(tomate, date(2026, 3, 15), date(2026, 5, 10))
    _evt(tomate, "plantation", "tomate", date(2026, 5, 12), source_evenement_ids=plantation.source_evenement_ids)
    assert _projection(tomate, "tomate", date(2026, 6, 1))["series_suivantes"] == 0


# ── CA5 — bascule sur la récolte réelle ──────────────────────────────────────
def test_us070_ca5_la_recolte_reelle_remplace_l_attendue(courgette):
    _evt(courgette, "recolte", "courgette", date(2026, 7, 8))
    p = _projection(courgette, "courgette", date(2026, 7, 20))
    assert p["etat"] == rec.ETAT_EN_RECOLTE
    assert p["recolte_reelle"] == {"premiere": "2026-07-08", "derniere": "2026-07-08"}
    assert p["jours_restants"] is None and p["retard_jours"] is None
    assert p["mois"]["recolte"][0] == 7


def test_us070_ca5_recolte_sans_parcelle_rattachee_si_une_seule_parcelle(courgette):
    _evt(courgette, "recolte", "courgette", date(2026, 7, 8), parcelle_id=None)
    assert _projection(courgette, "courgette", date(2026, 7, 20))["etat"] == rec.ETAT_EN_RECOLTE


def test_us070_ca5_recolte_sans_parcelle_ambigue_n_est_rattachee_a_personne(courgette):
    _evt(courgette, "semis", "courgette", date(2026, 4, 12), parcelle_id=2, contexte_semis="pleine_terre")
    _evt(courgette, "recolte", "courgette", date(2026, 7, 8), parcelle_id=None)
    for parcelle_id in (1, 2):
        assert _projection(courgette, "courgette", date(2026, 7, 20), parcelle_id=parcelle_id)["etat"] \
            == rec.ETAT_RECOLTE_DEPASSEE


# ── CA6 — végétatif / reproducteur ───────────────────────────────────────────
@pytest.mark.parametrize("organe, attendu", [
    ("végétatif", [6]),
    ("reproducteur", [6, 7, 8, 9, 10]),
])
def test_us070_ca6_recolte_terminale_ou_etalee(db, organe, attendu):
    _referentiel(db, "laitue", organe=organe, durees={"recolte": "60-70"},
                 fenetres={"oceanique": {"recolte": "mai-octobre"}})
    # 10 avril + 60 à 70 jours : du 9 au 19 juin.
    _evt(db, "semis", "laitue", date(2026, 4, 10), contexte_semis="pleine_terre")
    assert _projection(db, "laitue", date(2026, 5, 1))["mois"]["recolte"] == attendu


def test_us070_ca6_reproducteur_jusqu_a_la_derniere_recolte_constatee(courgette):
    _evt(courgette, "recolte", "courgette", date(2026, 7, 8))
    _evt(courgette, "recolte", "courgette", date(2026, 11, 3))
    assert _projection(courgette, "courgette", date(2026, 11, 5))["mois"]["recolte"] == [7, 8, 9, 10, 11]


def test_us070_ca6_hors_fenetre_la_recolte_ne_s_etire_pas(db):
    _referentiel(db, "courgette", durees={"recolte": "95"},
                 fenetres={"oceanique": {"recolte": "juin-août"}})
    _evt(db, "semis", "courgette", date(2026, 6, 1), contexte_semis="pleine_terre")
    # 1er juin + 95 = 4 septembre, hors fenêtre : pas d'étalement jusqu'en août suivant.
    assert _projection(db, "courgette", date(2026, 6, 15))["mois"]["recolte"] == [9]


# ── CA8 — date de référence ──────────────────────────────────────────────────
def test_us070_ca8_la_duree_restante_suit_la_date_de_reference(courgette):
    assert _projection(courgette, "courgette", date(2026, 6, 15))["jours_restants"]["min"] == 31
    assert _projection(courgette, "courgette", date(2026, 5, 1))["jours_restants"]["min"] == 76


def test_us070_ca8_les_evenements_posterieurs_a_la_date_de_reference_sont_ignores(courgette):
    _evt(courgette, "recolte", "courgette", date(2026, 7, 8))
    assert _projection(courgette, "courgette", date(2026, 6, 15))["etat"] == rec.ETAT_A_VENIR
    # Reculée avant le semis : plus aucune série en place.
    assert rec.projections_du_plan(courgette, ["courgette"], 1, date(2026, 3, 15)) == []


# ── CA9 — prochaine plage de semis ───────────────────────────────────────────
def test_us070_ca9_prochaine_plage_de_semis_tant_que_la_fenetre_court(courgette):
    plage = _projection(courgette, "courgette", date(2026, 5, 15))["prochaine_plage_semis"]
    assert plage["phase"] == "semis_pleine_terre"
    assert (plage["mois_debut"], plage["mois_fin"]) == (5, 6)


def test_us070_ca9_fenetre_terminee_aucune_plage(courgette):
    assert _projection(courgette, "courgette", date(2026, 7, 1))["prochaine_plage_semis"] is None


# ── CA10 — semis échelonnés ──────────────────────────────────────────────────
def test_us070_ca10_projection_sur_la_serie_la_plus_ancienne(db):
    _referentiel(db, "haricot", durees={"recolte": "55-75"})
    _evt(db, "semis", "haricot", date(2026, 5, 30), contexte_semis="pleine_terre")
    _evt(db, "semis", "haricot", date(2026, 5, 2), contexte_semis="pleine_terre")
    p = _projection(db, "haricot", date(2026, 6, 15))
    assert p["origine"]["date"] == "2026-05-02"
    assert p["series_suivantes"] == 1
    # Jamais une moyenne : la fourchette est celle du 2 mai seul.
    assert p["recolte_attendue"] == {"debut": "2026-06-26", "fin": "2026-07-16"}


def test_us070_ca10_serie_vegetative_recoltee_laisse_place_a_la_suivante(db):
    _referentiel(db, "laitue", organe="végétatif", durees={"recolte": "60"})
    _evt(db, "semis", "laitue", date(2026, 3, 1), contexte_semis="pleine_terre")
    _evt(db, "semis", "laitue", date(2026, 4, 1), contexte_semis="pleine_terre")
    _evt(db, "recolte", "laitue", date(2026, 5, 3))
    p = _projection(db, "laitue", date(2026, 5, 10))
    assert p["origine"]["date"] == "2026-04-01"
    assert p["series_suivantes"] == 0


def test_us070_ca10_une_serie_d_il_y_a_plus_d_un_an_n_est_plus_en_place(courgette):
    _evt(courgette, "semis", "courgette", date(2025, 4, 1), contexte_semis="pleine_terre")
    p = _projection(courgette, "courgette", date(2026, 6, 15))
    assert p["origine"]["date"] == "2026-04-12" and p["series_suivantes"] == 0


# ── CA11 — modes dégradés ────────────────────────────────────────────────────
def test_us070_ca11_culture_sans_referentiel(db):
    _evt(db, "semis", "topinambour", date(2026, 4, 1), contexte_semis="pleine_terre")
    p = _projection(db, "topinambour", date(2026, 6, 1))
    assert (p["etat"], p["motif"]) == (rec.ETAT_SANS_RECALAGE, rec.MOTIF_REFERENTIEL_ABSENT)
    assert p["mois"] is None and p["jours_restants"] is None and p["recolte_attendue"] is None


def test_us070_ca11_contexte_de_semis_inconnu_pas_de_recalage(courgette):
    _evt(courgette, "semis", "courgette", date(2026, 4, 20), parcelle_id=2)
    p = _projection(courgette, "courgette", date(2026, 6, 1), parcelle_id=2)
    assert (p["etat"], p["motif"]) == (rec.ETAT_SANS_RECALAGE, rec.MOTIF_CONTEXTE_INCONNU)
    assert p["mois"] is None


def test_us070_ca11_plantation_sans_semis_connu_pas_de_projection(tomate):
    """Amendement d'US-068 : un plant acheté garde la frise CONSEILLÉE (plantation
    comprise) — aucune durée plantation → récolte n'existe (US-177)."""
    _evt(tomate, "plantation", "tomate", date(2026, 5, 10))
    p = _projection(tomate, "tomate", date(2026, 6, 1))
    assert (p["etat"], p["motif"]) == (rec.ETAT_SANS_RECALAGE, rec.MOTIF_PLANTATION_SANS_SEMIS)
    assert p["origine"] == {"action": "plantation", "date": "2026-05-10", "contexte": None}
    assert p["mois"] is None


@pytest.mark.parametrize("durees", [{"levee": "10"}, {"recolte": "vivace"}])
def test_us070_ca11_duree_de_recolte_absente_ou_mention_jamais_empruntee(db, durees):
    _referentiel(db, "courgette", durees=durees)
    _evt(db, "semis", "courgette", date(2026, 4, 12), contexte_semis="pleine_terre")
    p = _projection(db, "courgette", date(2026, 6, 1))
    assert (p["etat"], p["motif"]) == (rec.ETAT_SANS_RECALAGE, rec.MOTIF_DUREE_RECOLTE_ABSENTE)


# ── CA12 — récolte attendue dépassée ─────────────────────────────────────────
def test_us070_ca12_recolte_depassee_dite_et_non_masquee(courgette):
    p = _projection(courgette, "courgette", date(2026, 7, 31))
    assert p["etat"] == rec.ETAT_RECOLTE_DEPASSEE
    assert p["retard_jours"] == 15
    assert p["mois"]["recolte"]


def test_us070_ca12_evenement_sans_date_ni_parcelle_ne_bloque_rien(courgette):
    courgette.add(Evenement(type_action="semis", culture="courgette", date=None, potager_id=1, parcelle_id=1))
    _evt(courgette, "semis", "courgette", date(2026, 4, 1), parcelle_id=None, contexte_semis="pleine_terre")
    courgette.commit()
    assert _projection(courgette, "courgette", date(2026, 6, 15))["origine"]["date"] == "2026-04-12"


# ── CA13 — lecture seule, isolation ──────────────────────────────────────────
def test_us070_ca13_aucune_ecriture(courgette):
    avant = [(e.id, e.type_action, e.date, e.contexte_semis) for e in courgette.query(Evenement).all()]
    rec.projections_du_plan(courgette, ["courgette"], 1, date(2026, 6, 15))
    assert not courgette.new and not courgette.dirty and not courgette.deleted
    assert [(e.id, e.type_action, e.date, e.contexte_semis) for e in courgette.query(Evenement).all()] == avant


def test_us070_ca13_les_evenements_d_un_autre_potager_sont_invisibles(courgette):
    assert rec.projections_du_plan(courgette, ["courgette"], 2, date(2026, 6, 15)) == []


def test_us070_seules_les_cultures_demandees_sont_projetees(courgette):
    _evt(courgette, "semis", "radis", date(2026, 4, 12), contexte_semis="pleine_terre")
    assert {p["culture"] for p in rec.projections_du_plan(courgette, ["courgette"], 1, date(2026, 6, 15))} \
        == {"courgette"}


# ── Fonctions pures ──────────────────────────────────────────────────────────
def test_us070_mois_entre_a_cheval_sur_l_annee():
    assert rec._mois_entre(date(2026, 11, 20), date(2027, 2, 1)) == [11, 12, 1, 2]
    assert rec._mois_entre(date(2026, 1, 1), date(2028, 1, 1)) == list(range(1, 13))
    assert rec._mois_entre(date(2026, 5, 1), date(2026, 4, 1)) == []


def test_us070_chainage_ne_rapproche_jamais_par_culture_ou_date():
    semis = rec.Geste(1, "semis", date(2026, 3, 1), 3, "tomate")
    plantation = rec.Geste(2, "plantation", date(2026, 5, 1), 1, "tomate")
    assert rec.semis_chaine(plantation, {1: semis, 2: plantation}) is None


# ── API ──────────────────────────────────────────────────────────────────────
@pytest.fixture
def _moteur_api():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_api(_moteur_api, monkeypatch):
    import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_moteur_api))
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client


def test_us070_api_projections_servies_avec_le_calendrier(client_api, _moteur_api):
    from app.services import auth as svc_auth

    session = sessionmaker(bind=_moteur_api)()
    user = svc_auth.inscrire_utilisateur(session, "jardinier@example.com", "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    session.close()
    potager_id = client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete).json()["id"]

    session = sessionmaker(bind=_moteur_api)()
    session.add(Parcelle(id=10, nom="nord", nom_normalise="nord", potager_id=potager_id))
    session.commit()
    _referentiel(session, "courgette", durees={"recolte": "95"})
    _evt(session, "semis", "courgette", date(2026, 4, 12), parcelle_id=10,
         contexte_semis="pleine_terre", potager_id=potager_id)
    session.close()

    corps = client_api.get(
        "/plan/calendriers?culture=courgette&date_ref=2026-06-15", headers=entete
    ).json()
    assert corps["date_ref_effective"] == "2026-06-15"
    assert corps["cultures"]["courgette"]["duree_recolte"] == "95 jours"
    [projection] = corps["projections"]
    assert (projection["parcelle_id"], projection["culture"]) == (10, "courgette")
    assert projection["jours_restants"] == {"min": 31, "max": 31}

    # Une date de référence future est bornée à aujourd'hui, comme `/plan`.
    futur = (date.today() + timedelta(days=30)).isoformat()
    corps = client_api.get(f"/plan/calendriers?culture=courgette&date_ref={futur}", headers=entete).json()
    assert corps["date_ref_effective"] == date.today().isoformat()
