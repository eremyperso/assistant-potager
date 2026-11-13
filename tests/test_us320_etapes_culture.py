"""
tests/test_us320_etapes_culture.py — Étapes d'une culture, prévues puis validées [US-320]
=========================================================================================

Séquences retenues (arbitrage P3 du 12/11/2026) : semis direct Semé → Levé → En récolte
→ Terminé ; plant Planté → En récolte → Terminé. « Terminé » vient d'une fin de culture
(« culture terminée », « arraché ») ou d'une ligne soldée.

Les durées et fenêtres sont des VALEURS DE TEST, pas des données agronomiques.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import etapes_culture as et
from app.services import evenements as svc_evenements
from app.services import import_referentiel as svc_import
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, Rappel, User
from utils.actions import normalize_action
from utils.parcelles import calcul_occupation_parcelles
from utils.stock import calcul_stock_cultures

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="planche centrale", nom_normalise="planchecentrale", potager_id=1),
        Parcelle(id=2, nom="planche ombre", nom_normalise="plancheombre", potager_id=1),
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
    if entree:
        svc_import.importer(db, {"source": _source(), "cultures_calendriers": [{"culture": culture, **entree}]})


def _evt(db, action, culture, jour, parcelle_id=1, **champs):
    evenement = Evenement(
        type_action=action, culture=culture, date=datetime.combine(jour, datetime.min.time()),
        parcelle_id=parcelle_id, potager_id=champs.pop("potager_id", 1), **champs,
    )
    db.add(evenement)
    db.commit()
    return evenement


def _en_place(db, date_ref):
    parcelles = {p.nom: p.id for p in db.query(Parcelle).all()}
    occupation = calcul_occupation_parcelles(db, date_ref=date_ref, potager_id=1)
    return {
        et.cle_ligne(parcelles[nom], c["culture"], c["variete"])
        for nom, lignes in occupation.items() if nom in parcelles for c in lignes
    }


def _etapes(db, date_ref):
    return et.etapes_du_plan(db, 1, date_ref, _en_place(db, date_ref))


def _ligne(db, culture, date_ref, parcelle_id=1, variete=""):
    lignes, _ = _etapes(db, date_ref)
    return lignes.get((parcelle_id, culture, variete))


def _codes(etapes):
    return [e["code"] for e in etapes["etapes"]]


def _confirmer(db, parsed, texte="test"):
    parcelle = None
    if parsed.get("parcelle"):
        parcelle = db.query(Parcelle).filter(Parcelle.nom == parsed["parcelle"]).first()
    return svc_evenements.creer_evenement_confirme(db, CTX, dict(parsed), texte, parcelle)


@pytest.fixture
def feve(db):
    """Gherkin « La fève du rang 6 » : 40 fèves semées le 2 novembre, levée en 10 jours."""
    _referentiel(db, "feve", durees={"levee": "10-14", "recolte": "150-180"},
                 fenetres={"oceanique": {"semis_pleine_terre": "octobre-novembre"}})
    return _evt(db, "semis", "feve", date(2026, 11, 2), quantite=40, unite="graines",
                contexte_semis="pleine_terre")


# ── CA2, CA3 — séquences et première étape ───────────────────────────────────
def test_us320_ca3_semis_direct_seme_valide_levee_prevue(db, feve):
    etapes = _ligne(db, "feve", date(2026, 11, 5))
    assert _codes(etapes) == [et.ETAPE_SEMEE, et.ETAPE_LEVEE, et.ETAPE_EN_RECOLTE, et.ETAPE_TERMINEE]
    assert etapes["etape"] == et.ETAPE_SEMEE
    assert etapes["etape_statut"] == et.STATUT_VALIDEE
    assert etapes["etape_date"] == "2026-11-02"
    levee = etapes["etapes"][1]
    assert levee["statut"] == et.STATUT_PREVUE
    assert levee["date"] == "2026-11-12"
    assert levee["source"] == et.SOURCE_CALENDRIER
    assert etapes["a_confirmer"] is False


def test_us320_ca2_un_plant_ne_passe_ni_par_seme_ni_par_leve(db):
    _referentiel(db, "tomate", durees={"plantation_recolte": "60"})
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants")
    etapes = _ligne(db, "tomate", date(2026, 5, 20))
    assert _codes(etapes) == [et.ETAPE_PLANTEE, et.ETAPE_EN_RECOLTE, et.ETAPE_TERMINEE]
    assert etapes["etape"] == et.ETAPE_PLANTEE


def test_us320_ca2_aucune_etape_en_fleur_ni_en_croissance(db, feve):
    """Arbitrage P3 : ni « En croissance » ni « En fleur » — aucun geste ne les porte."""
    assert set(et.ETAPES) == {"semee", "levee", "plantee", "en_recolte", "terminee"}


def test_us320_e2_sans_calendrier_aucune_etape_prevue(db):
    _referentiel(db, "radis", organe="végétatif")
    _evt(db, "semis", "radis", date(2026, 9, 1), quantite=100, unite="graines",
         contexte_semis="pleine_terre")
    etapes = _ligne(db, "radis", date(2026, 10, 30))
    assert etapes["etape"] == et.ETAPE_SEMEE
    assert all(e["date"] is None for e in etapes["etapes"][1:])
    assert etapes["a_confirmer"] is False


# ── CA4 — date prévue atteinte : à confirmer, jamais validée seule ────────────
def test_us320_ca4_levee_prevue_atteinte_est_a_confirmer(db, feve):
    """Gherkin : le 12 novembre, la fève est « Levé », statut prévu, à confirmer."""
    etapes = _ligne(db, "feve", date(2026, 11, 12))
    assert etapes["etape"] == et.ETAPE_LEVEE
    assert etapes["etape_statut"] == et.STATUT_PREVUE
    assert etapes["a_confirmer"] is True
    # E3 : rien n'a été écrit, l'étape n'avance pas seule.
    assert db.query(Evenement).filter(Evenement.type_action == "levee").count() == 0


def test_us320_ca4_confirmer_la_levee_valide_l_etape(db, feve):
    """Gherkin : « je confirme la levée par le compagnon » — une levée en pleine terre,
    sans comptage, rattachée au semis direct."""
    event = _confirmer(db, {"action": "levee", "culture": "feve", "date": "2026-11-12"})
    assert event.origine_graines_id == feve.id
    assert event.parcelle_id == 1
    assert event.quantite is None
    etapes = _ligne(db, "feve", date(2026, 11, 12))
    assert etapes["etape"] == et.ETAPE_LEVEE
    assert etapes["etape_statut"] == et.STATUT_VALIDEE
    assert etapes["etape_date"] == "2026-11-12"
    assert etapes["etape_source"] in (et.SOURCE_JARDINIER, et.SOURCE_COMPAGNON)
    assert etapes["a_confirmer"] is False


def test_us320_e4_levee_sur_parcelle_de_pleine_terre_sans_semis_refusee(db):
    _referentiel(db, "carotte", organe="végétatif")
    with pytest.raises(svc_evenements.LeveeRefuseeError, match="aucun semis"):
        _confirmer(db, {"action": "levee", "culture": "carotte", "parcelle": "planche ombre"})


def test_us320_e4_levee_de_pepiniere_exige_toujours_un_nombre(db):
    """US-212 inchangée : en pépinière, le comptage EST le geste."""
    with pytest.raises(svc_evenements.QuantiteManquanteError):
        svc_evenements.valider_evenement(
            db, CTX, action="levee", culture="feve", parcelle=db.get(Parcelle, 3), a_la_creation=True,
        )


# ── CA9 — « Pas encore » ─────────────────────────────────────────────────────
def test_us320_ca9_pas_encore_repousse_de_trois_jours_sans_ecrire_d_etape(db, feve):
    rappel = et.reporter_etape(db, CTX, feve.id, et.ETAPE_LEVEE, aujourd_hui=date(2026, 11, 12))
    assert rappel.echeance_le.date() == date(2026, 11, 15)
    assert rappel.cible_type == "etape_levee" and rappel.cible_id == feve.id
    etapes = _ligne(db, "feve", date(2026, 11, 13))
    assert etapes["a_confirmer"] is False
    assert etapes["etape"] == et.ETAPE_SEMEE
    assert etapes["rappel_le"] == "2026-11-15"
    assert db.query(Evenement).filter(Evenement.type_action == "levee").count() == 0
    # Trois jours plus tard, elle redevient à confirmer.
    assert _ligne(db, "feve", date(2026, 11, 15))["a_confirmer"] is True


def test_us320_ca9_pas_encore_redit_repousse_le_meme_rappel(db, feve):
    et.reporter_etape(db, CTX, feve.id, et.ETAPE_LEVEE, aujourd_hui=date(2026, 11, 12))
    rappel = et.reporter_etape(db, CTX, feve.id, et.ETAPE_LEVEE, aujourd_hui=date(2026, 11, 15))
    assert rappel.echeance_le.date() == date(2026, 11, 18)
    assert db.query(Rappel).count() == 1


def test_us320_ca9_pas_encore_refuse_une_etape_hors_sequence(db):
    plantation = _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants")
    with pytest.raises(et.EtapeError):
        et.reporter_etape(db, CTX, plantation.id, et.ETAPE_LEVEE)
    with pytest.raises(et.EtapeError):
        et.reporter_etape(db, CTX, 9999, et.ETAPE_EN_RECOLTE)


def test_us320_ca9_un_lecteur_ne_reporte_pas(db, feve):
    from app.services.permissions import PermissionInsuffisanteError
    lecteur = TenantContext(user_id=1, potager_id=1, role="viewer")
    with pytest.raises(PermissionInsuffisanteError):
        et.reporter_etape(db, lecteur, feve.id, et.ETAPE_LEVEE)


# ── CA5, CA6 — reproducteur : la récolte ne consomme rien ─────────────────────
def test_us320_ca5_ca6_recoltes_successives_d_un_reproducteur(db):
    """Gherkin « Récoltes successives d'un reproducteur »."""
    _referentiel(db, "haricot", durees={"levee": "8"})
    _evt(db, "plantation", "haricot", date(2026, 6, 1), quantite=30, unite="plants")
    _evt(db, "recolte", "haricot", date(2026, 8, 1), quantite=500, unite="g")
    premiere = _ligne(db, "haricot", date(2026, 8, 2))
    assert premiere["etape"] == et.ETAPE_EN_RECOLTE and premiere["etape_date"] == "2026-08-01"

    _evt(db, "recolte", "haricot", date(2026, 8, 10), quantite=800, unite="g")
    apres = _ligne(db, "haricot", date(2026, 8, 11))
    assert apres["etape"] == et.ETAPE_EN_RECOLTE
    assert apres["etape_date"] == "2026-08-01"
    stock = calcul_stock_cultures(db, date(2026, 8, 11), potager_id=1)["haricot"]
    assert stock.stock_plants == 30
    assert stock.rendement_total == pytest.approx(1.3)


# ── CA7 — végétatif : la dernière récolte termine, la ligne est à libérer ────
def test_us320_ca7_derniere_recolte_d_un_vegetatif_termine_et_est_a_liberer(db):
    """Gherkin « Dernière récolte d'un végétatif »."""
    _referentiel(db, "laitue", organe="végétatif")
    _evt(db, "plantation", "laitue", date(2026, 9, 1), quantite=5, unite="plants")
    _evt(db, "recolte", "laitue", date(2026, 10, 20), quantite=5, unite="plants")
    lignes, a_liberer = _etapes(db, date(2026, 10, 21))
    assert (1, "laitue", "") not in lignes
    assert len(a_liberer) == 1
    ligne = a_liberer[0]
    assert ligne["parcelle_id"] == 1 and ligne["culture"] == "laitue"
    assert ligne["etape"] == et.ETAPE_TERMINEE and ligne["etape_date"] == "2026-10-20"
    assert ligne["a_liberer"] is True


def test_us320_e8_une_ligne_soldee_depuis_longtemps_n_est_plus_a_liberer(db):
    _referentiel(db, "laitue", organe="végétatif")
    _evt(db, "plantation", "laitue", date(2026, 3, 1), quantite=5, unite="plants")
    _evt(db, "recolte", "laitue", date(2026, 5, 1), quantite=5, unite="plants")
    _, a_liberer = _etapes(db, date(2026, 5, 1) + timedelta(days=et.JOURS_A_LIBERER_MAX + 1))
    assert a_liberer == []


# ── CA8 — fin de culture ─────────────────────────────────────────────────────
def test_us320_ca8_fin_de_culture_d_un_reproducteur(db):
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants")
    _evt(db, "perte", "tomate", date(2026, 7, 1), quantite=1, unite="plants")
    event = _confirmer(db, {"action": "fin_culture", "culture": "tomate", "date": "2026-10-15"})
    assert event.type_action == "fin_culture"
    assert event.parcelle_id == 1
    assert event.quantite == 5   # le reste de la ligne, relu à la confirmation

    jour = date(2026, 10, 16)
    assert calcul_stock_cultures(db, jour, potager_id=1)["tomate"].stock_plants == 0
    assert "planche centrale" not in calcul_occupation_parcelles(db, date_ref=jour, potager_id=1)
    lignes, a_liberer = _etapes(db, jour)
    assert lignes == {} and a_liberer == []   # terminée ET libérée : archivée


def test_us320_ca8_fin_de_culture_ne_vide_que_sa_parcelle(db):
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants", variete="roma")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), parcelle_id=2, quantite=4, unite="plants",
         variete="roma")
    _confirmer(db, {"action": "fin_culture", "culture": "tomate", "parcelle": "planche centrale",
                    "date": "2026-10-15"})
    occupation = calcul_occupation_parcelles(db, date_ref=date(2026, 10, 16), potager_id=1)
    assert "planche centrale" not in occupation
    assert occupation["planche ombre"][0]["nb_plants"] == 4
    assert calcul_stock_cultures(db, date(2026, 10, 16), potager_id=1)["tomate"].stock_plants == 4


def test_us320_ca8_fin_de_culture_ambigue_entre_deux_parcelles(db):
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), parcelle_id=2, quantite=4, unite="plants")
    with pytest.raises(svc_evenements.FinCultureAmbigueError) as erreur:
        _confirmer(db, {"action": "fin_culture", "culture": "tomate"})
    assert erreur.value.parcelles == ["planche centrale", "planche ombre"]
    assert db.query(Evenement).filter(Evenement.type_action == "fin_culture").count() == 0


def test_us320_ca8_fin_de_culture_sans_rien_en_place_refusee(db):
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants")
    with pytest.raises(svc_evenements.FinCultureRefuseeError):
        _confirmer(db, {"action": "fin_culture", "culture": "tomate", "parcelle": "planche ombre"})


def test_us320_ca8_arracher_quelques_pieds_reste_une_perte(db):
    """« arraché 2 pieds de tomates malades » : 2 pieds perdus, la culture continue."""
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants")
    event = _confirmer(db, {"action": "fin_culture", "culture": "tomate", "quantite": 2,
                            "unite": "plants", "date": "2026-07-01"})
    assert event.type_action == "perte" and event.quantite == 2
    assert calcul_stock_cultures(db, date(2026, 7, 2), potager_id=1)["tomate"].stock_plants == 4


def test_us320_ca8_fin_de_culture_d_une_parcelle_a_plusieurs_varietes(db):
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=6, unite="plants", variete="roma")
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=3, unite="plants",
         variete="coeur de boeuf")
    _confirmer(db, {"action": "fin_culture", "culture": "tomate", "date": "2026-10-15"})
    fins = db.query(Evenement).filter(Evenement.type_action == "fin_culture").all()
    assert sorted((f.variete, f.quantite) for f in fins) == [("coeur de boeuf", 3), ("roma", 6)]
    assert calcul_stock_cultures(db, date(2026, 10, 16), potager_id=1)["tomate"].stock_plants == 0


def test_us320_ca8_une_fin_de_culture_libere_une_ligne_a_liberer(db):
    _referentiel(db, "laitue", organe="végétatif")
    _evt(db, "plantation", "laitue", date(2026, 9, 1), quantite=5, unite="plants")
    _evt(db, "recolte", "laitue", date(2026, 10, 20), quantite=5, unite="plants")
    _evt(db, "fin_culture", "laitue", date(2026, 10, 22), quantite=0, unite="plants")
    _, a_liberer = _etapes(db, date(2026, 10, 23))
    assert a_liberer == []


def test_us320_ca8_replanter_apres_une_fin_de_culture_repart_a_plante(db):
    _referentiel(db, "tomate")
    _evt(db, "plantation", "tomate", date(2025, 5, 10), quantite=6, unite="plants")
    _confirmer(db, {"action": "fin_culture", "culture": "tomate", "date": "2025-10-15"})
    _evt(db, "plantation", "tomate", date(2026, 5, 10), quantite=4, unite="plants")
    jour = date(2026, 5, 11)
    assert calcul_occupation_parcelles(db, date_ref=jour, potager_id=1)["planche centrale"][0]["nb_plants"] == 4
    etapes = _ligne(db, "tomate", jour)
    assert etapes["etape"] == et.ETAPE_PLANTEE and etapes["etape_date"] == "2026-05-10"


# ── CA12 — le vocabulaire du bot ─────────────────────────────────────────────
@pytest.mark.parametrize("dit", ["arraché", "arrachées", "culture terminée", "fin de culture", "fin_culture"])
def test_us320_ca12_les_phrases_de_fin_de_culture(dit):
    assert normalize_action(dit) == "fin_culture"


@pytest.mark.parametrize("dit,attendu", [("perdu", "perte"), ("mortes", "perte"), ("crevé", "perte")])
def test_us320_ca12_la_perte_garde_son_vocabulaire(dit, attendu):
    assert normalize_action(dit) == attendu


def test_us320_ca12_fin_du_mois_n_est_pas_une_fin_de_culture():
    from llm.parseur_deterministe import _extraire_geste, _normaliser
    geste, _ = _extraire_geste(_normaliser("a la fin du mois j'ai semé des radis").split())
    assert geste != "fin_culture"


def test_us320_ca12_le_parseur_reconnait_arrache():
    from llm.parseur_deterministe import _extraire_geste, _normaliser
    geste, _ = _extraire_geste(_normaliser("arraché les tomates de la serre").split())
    assert geste == "fin_culture"


# ── CA1 — l'API ──────────────────────────────────────────────────────────────
@pytest.fixture
def _moteur_api():
    from database.db import Base

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_api(_moteur_api, monkeypatch):
    from fastapi.testclient import TestClient
    from app.api import main

    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_moteur_api))
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client


@pytest.fixture
def potager_api(client_api, _moteur_api):
    from app.services import auth as svc_auth

    session = sessionmaker(bind=_moteur_api)()
    user = svc_auth.inscrire_utilisateur(session, "jardinier@example.com", "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    session.close()
    potager_id = client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete).json()["id"]

    session = sessionmaker(bind=_moteur_api)()
    session.add(Parcelle(id=10, nom="nord", nom_normalise="nord", potager_id=potager_id))
    session.commit()
    _referentiel(session, "feve", durees={"levee": "10"})
    _referentiel(session, "laitue", organe="végétatif")
    semis = _evt(session, "semis", "feve", date(2026, 11, 2), parcelle_id=10, potager_id=potager_id,
                 quantite=40, unite="graines", contexte_semis="pleine_terre")
    _evt(session, "plantation", "laitue", date(2026, 9, 1), parcelle_id=10, potager_id=potager_id,
         quantite=5, unite="plants")
    _evt(session, "recolte", "laitue", date(2026, 11, 1), parcelle_id=10, potager_id=potager_id,
         quantite=5, unite="plants")
    serie_id = semis.id
    session.close()
    return entete, serie_id


def _parcelle(client_api, entete, date_ref):
    parcelles = client_api.get(f"/plan?date_ref={date_ref}", headers=entete).json()["parcelles"]
    return next(p for p in parcelles if p["id"] == 10)


def test_us320_ca1_get_plan_expose_les_etapes_et_les_lignes_a_liberer(client_api, potager_api):
    entete, serie_id = potager_api
    parcelle = _parcelle(client_api, entete, "2026-11-12")
    feve = next(c for c in parcelle["cultures"] if c["culture"] == "feve")
    assert feve["etapes"]["serie_id"] == serie_id
    assert feve["etapes"]["etape"] == "levee"
    assert feve["etapes"]["a_confirmer"] is True
    # La phase d'US-194 reste servie à côté (CA10).
    assert feve["phase"] is not None
    assert [l["culture"] for l in parcelle["a_liberer"]] == ["laitue"]


def test_us320_ca9_post_pas_encore(client_api, potager_api):
    entete, serie_id = potager_api
    reponse = client_api.post("/plan/etapes/pas-encore", json={"serie_id": serie_id, "etape": "levee"},
                              headers=entete)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["rappel_le"] == (date.today() + timedelta(days=3)).isoformat()
    inconnue = client_api.post("/plan/etapes/pas-encore", json={"serie_id": 99999, "etape": "levee"},
                               headers=entete)
    assert inconnue.status_code == 404
