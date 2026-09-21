"""
tests/test_us194_phase_culture.py — Phase du moment d'une culture en place [US-194]
==================================================================================

La phase — *semée*, *en place*, *en récolte* — est calculée par UNE fonction de
`app/services/recalage_calendrier.py` et exposée par `GET /plan`. Le volet
d'affichage (pastille, légende, libellés, teintes) est couvert par
`frontend/src/lib/phases.test.js`.

Les fenêtres et durées sont des VALEURS DE TEST, pas des données agronomiques.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import import_referentiel as svc_import
from app.services import recalage_calendrier as rec
from database.models import CultureConfig, Evenement, Parcelle, Potager, User


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
        svc_import.importer(db, {"source": _source(),
                                 "cultures_calendriers": [{"culture": culture, **entree}]})


def _evt(db, action, culture, jour, parcelle_id=1, **champs):
    evenement = Evenement(
        type_action=action, culture=culture,
        date=datetime.combine(jour, datetime.min.time()),
        parcelle_id=parcelle_id, potager_id=champs.pop("potager_id", 1), **champs,
    )
    db.add(evenement)
    db.commit()
    return evenement


def _phase(db, culture, date_ref, parcelle_id=1, variete=""):
    """La phase d'une ligne, ou None si elle n'en a pas."""
    return rec.phases_du_plan(db, [culture], 1, date_ref).get((parcelle_id, culture, variete))


# ── CA1, CA5 — la règle : semis, levée attendue, plantation, récolte ─────────
def test_us194_ca1_haricot_seme_en_place_avant_la_levee_est_seme(db):
    """Gherkin : haricot semé le 12 septembre, levée de 8 à 12 jours, vu le 15."""
    _referentiel(db, "haricot", durees={"levee": "8-12", "recolte": "60-80"},
                 fenetres={"oceanique": {"semis_pleine_terre": "mai-septembre"}})
    _evt(db, "semis", "haricot", date(2026, 9, 12), contexte_semis="pleine_terre")

    phase = _phase(db, "haricot", date(2026, 9, 15))
    assert phase["phase"] == rec.PHASE_SEMEE
    assert phase["phase_depuis"] == "2026-09-12"
    assert phase["phase_depuis_nature"] == rec.DEPUIS_SEMIS


def test_us194_ca5_apres_la_levee_attendue_la_ligne_passe_en_place(db):
    """[CA5] La date de début est le DÉBUT de la fourchette de levée, et elle
    reste annoncée comme attendue — jamais comme constatée."""
    _referentiel(db, "haricot", durees={"levee": "8-12", "recolte": "60-80"},
                 fenetres={"oceanique": {"semis_pleine_terre": "mai-septembre"}})
    _evt(db, "semis", "haricot", date(2026, 9, 12), contexte_semis="pleine_terre")

    phase = _phase(db, "haricot", date(2026, 9, 25))
    assert phase["phase"] == rec.PHASE_EN_PLACE
    assert phase["phase_depuis"] == "2026-09-20"  # 12 septembre + 8 jours
    assert phase["phase_depuis_nature"] == rec.DEPUIS_LEVEE_ATTENDUE


def test_us194_ca1_le_jour_exact_de_la_levee_attendue_bascule_en_place(db):
    """Une borne est incluse : le premier jour de levée attendue compte."""
    _referentiel(db, "haricot", durees={"levee": "8-12", "recolte": "60-80"})
    _evt(db, "semis", "haricot", date(2026, 9, 12), contexte_semis="pleine_terre")

    assert _phase(db, "haricot", date(2026, 9, 19))["phase"] == rec.PHASE_SEMEE
    assert _phase(db, "haricot", date(2026, 9, 20))["phase"] == rec.PHASE_EN_PLACE


def test_us194_ca1_semis_sans_delai_de_levee_reste_seme(db):
    """Gherkin : mâche semée le 1er août sans délai de levée, vue le 1er octobre.
    ⚖️ C'est le dernier geste CONNU, pas une supposition."""
    _referentiel(db, "mache", durees={"recolte": "60"},
                 fenetres={"oceanique": {"semis_pleine_terre": "juillet-septembre"}})
    _evt(db, "semis", "mache", date(2026, 8, 1), contexte_semis="pleine_terre")

    phase = _phase(db, "mache", date(2026, 10, 1))
    assert phase["phase"] == rec.PHASE_SEMEE
    assert phase["phase_depuis"] == "2026-08-01"


def test_us194_ca1_plantation_est_en_place_depuis_la_plantation(db):
    """Un plant mis en terre a levé ailleurs : aucun délai de levée ne s'applique."""
    _referentiel(db, "courgette", durees={"levee": "10", "plantation_recolte": "50"},
                 fenetres={"oceanique": {"plantation": "mai-juin"}})
    _evt(db, "plantation", "courgette", date(2026, 5, 20))

    phase = _phase(db, "courgette", date(2026, 5, 21))
    assert phase["phase"] == rec.PHASE_EN_PLACE
    assert phase["phase_depuis"] == "2026-05-20"
    assert phase["phase_depuis_nature"] == rec.DEPUIS_PLANTATION


def test_us194_ca1_premiere_recolte_puis_nieme_recolte(db):
    """Gherkin : la deuxième cueillette ne déplace pas le début de la récolte."""
    _referentiel(db, "haricot", durees={"levee": "8-12", "recolte": "60-80"})
    _evt(db, "semis", "haricot", date(2026, 9, 12), contexte_semis="pleine_terre")
    _evt(db, "recolte", "haricot", date(2026, 10, 20))

    phase = _phase(db, "haricot", date(2026, 10, 21))
    assert phase["phase"] == rec.PHASE_EN_RECOLTE
    assert phase["phase_depuis"] == "2026-10-20"
    assert phase["phase_depuis_nature"] == rec.DEPUIS_RECOLTE

    _evt(db, "recolte", "haricot", date(2026, 10, 27))
    apres = _phase(db, "haricot", date(2026, 10, 28))
    assert apres["phase"] == rec.PHASE_EN_RECOLTE
    assert apres["phase_depuis"] == "2026-10-20"


# ── CA2 — une ligne sans référentiel a quand même une phase ──────────────────
def test_us194_ca2_plantation_sans_referentiel_est_en_place(db):
    """Gherkin : un pied de verveine planté sans calendrier connu."""
    _evt(db, "plantation", "verveine", date(2026, 5, 3))

    phase = _phase(db, "verveine", date(2026, 7, 1))
    assert phase["phase"] == rec.PHASE_EN_PLACE
    assert phase["phase_depuis"] == "2026-05-03"


def test_us194_ca2_semis_sans_referentiel_est_seme(db):
    _evt(db, "semis", "bourrache", date(2026, 5, 3), contexte_semis="pleine_terre")

    assert _phase(db, "bourrache", date(2026, 7, 1))["phase"] == rec.PHASE_SEMEE


def test_us194_ca2_recolte_notee_sans_referentiel_est_en_recolte(db):
    _evt(db, "plantation", "verveine", date(2026, 5, 3))
    _evt(db, "recolte", "verveine", date(2026, 6, 20))

    phase = _phase(db, "verveine", date(2026, 7, 1))
    assert phase["phase"] == rec.PHASE_EN_RECOLTE
    assert phase["phase_depuis"] == "2026-06-20"


def test_us194_ca2_un_semis_sans_contexte_a_quand_meme_une_phase(db):
    """`sans_recalage` côté projection (contexte inconnu) ≠ absence de phase."""
    _referentiel(db, "radis", durees={"levee": "4-6", "recolte": "25"})
    _evt(db, "semis", "radis", date(2026, 4, 1))  # aucun contexte_semis

    projection = rec.projections_du_plan(db, ["radis"], 1, date(2026, 4, 20))[0]
    assert projection["etat"] == rec.ETAT_SANS_RECALAGE

    assert _phase(db, "radis", date(2026, 4, 20))["phase"] == rec.PHASE_EN_PLACE


# ── CA3 — une récolte clôt une série végétative ──────────────────────────────
def test_us194_ca3_vegetative_recoltee_la_phase_suit_la_serie_ouverte(db):
    """Récolte partielle d'une végétative : la première série est close, la ligne
    reste en place grâce à la seconde, et la phase est celle de CETTE série."""
    _referentiel(db, "laitue", organe="végétatif", durees={"levee": "5", "recolte": "60-70"},
                 fenetres={"oceanique": {"recolte": "mai-octobre"}})
    _evt(db, "semis", "laitue", date(2026, 4, 1), contexte_semis="pleine_terre")
    _evt(db, "semis", "laitue", date(2026, 6, 1), contexte_semis="pleine_terre")
    _evt(db, "recolte", "laitue", date(2026, 6, 10))

    phase = _phase(db, "laitue", date(2026, 6, 11))
    assert phase["phase"] == rec.PHASE_EN_PLACE       # la 2ᵉ série, semée le 1er juin
    assert phase["phase_depuis"] == "2026-06-06"      # levée attendue de cette série
    assert phase["nb_series"] == 2                    # compté, jamais moyenné


def test_us194_ca3_reproductrice_la_recolte_ne_clot_rien(db):
    """Un haricot reste en récolte à chaque cueillette : le pied reste."""
    _referentiel(db, "haricot", organe="reproducteur", durees={"levee": "8", "recolte": "60"})
    _evt(db, "semis", "haricot", date(2026, 5, 1), contexte_semis="pleine_terre")
    _evt(db, "recolte", "haricot", date(2026, 7, 5))

    assert _phase(db, "haricot", date(2026, 8, 1))["phase"] == rec.PHASE_EN_RECOLTE


# ── CA4 — un semis en pépinière n'est pas une culture en place ───────────────
def test_us194_ca4_semis_en_pepiniere_na_pas_de_phase(db):
    _referentiel(db, "tomate", durees={"levee": "7-10", "recolte": "120"})
    _evt(db, "semis", "tomate", date(2026, 3, 1), parcelle_id=3, contexte_semis="pepiniere")

    assert _phase(db, "tomate", date(2026, 4, 1), parcelle_id=3) is None


def test_us194_ca4_une_plantation_dans_une_parcelle_pepiniere_reste_en_place(db):
    """L'exclusion porte sur le SEMIS de pépinière, pas sur la parcelle."""
    _evt(db, "plantation", "fraise", date(2026, 3, 1), parcelle_id=3)

    assert _phase(db, "fraise", date(2026, 4, 1), parcelle_id=3)["phase"] == rec.PHASE_EN_PLACE


# ── CA7 — la date de référence reconstitue la phase de ce jour-là ────────────
def test_us194_ca7_date_de_reference_anterieure_a_la_recolte(db):
    """Gherkin : courgettes plantées le 20 mai, récoltées le 16 juillet, vues le 10."""
    _referentiel(db, "courgette", durees={"plantation_recolte": "50"},
                 fenetres={"oceanique": {"plantation": "mai-juin", "recolte": "juillet-octobre"}})
    _evt(db, "plantation", "courgette", date(2026, 5, 20))
    _evt(db, "recolte", "courgette", date(2026, 7, 16))

    assert _phase(db, "courgette", date(2026, 7, 10))["phase"] == rec.PHASE_EN_PLACE
    assert _phase(db, "courgette", date(2026, 7, 20))["phase"] == rec.PHASE_EN_RECOLTE


# ── CA1 — une seule fonction, et elle ne lève jamais ─────────────────────────
def test_us194_ca1_la_regle_est_ecrite_dans_une_seule_fonction():
    """[CA1] `phase_de_serie` est le seul endroit où la table de décision vit.
    Aucun autre module — front compris — ne recalcule une phase."""
    import subprocess

    sortie = subprocess.run(
        ["git", "grep", "-l", "-E", r"PHASE_SEMEE|phase_de_serie", "--", "app/", "utils/", "llm/"],
        capture_output=True, text=True,
    )
    fichiers = {ligne for ligne in sortie.stdout.split() if ligne}
    assert fichiers <= {"app/services/recalage_calendrier.py"}, fichiers


def test_us194_ca1_phase_de_serie_sans_itineraire_ne_leve_pas(db):
    """Sans référentiel du tout, la fonction rend une phase plutôt qu'une erreur."""
    semis = rec.Geste(id=1, action="semis", jour=date(2026, 5, 1), parcelle_id=1,
                      culture="mache", contexte_semis="pleine_terre")
    serie = rec.Serie(semis=semis, plantation=None, contexte="pleine_terre")

    phase, depuis, nature = rec.phase_de_serie(serie, [], None, date(2026, 9, 1))
    assert (phase, depuis, nature) == (rec.PHASE_SEMEE, date(2026, 5, 1), rec.DEPUIS_SEMIS)


# ── CA6, CA8 — l'exposition par `GET /plan` ─────────────────────────────────
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
    """Un potager réel, une parcelle, une courgette plantée puis récoltée."""
    from app.services import auth as svc_auth

    session = sessionmaker(bind=_moteur_api)()
    user = svc_auth.inscrire_utilisateur(session, "jardinier@example.com", "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    session.close()
    potager_id = client_api.post("/potagers", json={"nom": "Jardin"}, headers=entete).json()["id"]

    session = sessionmaker(bind=_moteur_api)()
    session.add(Parcelle(id=10, nom="nord", nom_normalise="nord", potager_id=potager_id))
    session.commit()
    _referentiel(session, "courgette", durees={"plantation_recolte": "50"})
    _evt(session, "plantation", "courgette", date(2026, 5, 20), parcelle_id=10,
         potager_id=potager_id, quantite=3, unite="plants", variete="Ronde de Nice")
    _evt(session, "recolte", "courgette", date(2026, 7, 16), parcelle_id=10,
         potager_id=potager_id, quantite=2, unite="kg", variete="Ronde de Nice")
    session.close()
    return entete


def _ligne(client_api, entete, date_ref):
    parcelles = client_api.get(f"/plan?date_ref={date_ref}", headers=entete).json()["parcelles"]
    cultures = [c for p in parcelles if p["id"] == 10 for c in p["cultures"]]
    assert len(cultures) == 1, cultures
    return cultures[0]


def test_us194_ca6_get_plan_expose_la_phase_de_chaque_ligne(client_api, potager_api):
    ligne = _ligne(client_api, potager_api, "2026-07-20")
    assert ligne["phase"] == rec.PHASE_EN_RECOLTE
    assert ligne["phase_depuis"] == "2026-07-16"
    assert ligne["phase_depuis_nature"] == rec.DEPUIS_RECOLTE
    assert ligne["nb_series"] == 1


def test_us194_ca7_get_plan_a_une_date_anterieure_ne_voit_pas_la_recolte(client_api, potager_api):
    ligne = _ligne(client_api, potager_api, "2026-07-10")
    assert ligne["phase"] == rec.PHASE_EN_PLACE
    assert ligne["phase_depuis"] == "2026-05-20"


def test_us194_ca6_aucun_champ_existant_nest_retire(client_api, potager_api):
    """[CA6] L'écran Parcelles actuel n'est pas modifié : tout ce qu'il lisait
    hier est encore là aujourd'hui."""
    ligne = _ligne(client_api, potager_api, "2026-07-20")
    attendus = {
        "culture", "variete", "nb_plants", "unite", "type_organe",
        "surface_m2_par_plant", "famille", "nb_observations", "has_observations",
    }
    assert attendus <= set(ligne)


def test_us194_ca8_les_autres_reponses_sont_inchangees(client_api, potager_api):
    """[CA8] Aucune écriture, aucun calcul de stock, de projection ni de
    confiance n'est modifié."""
    entete = potager_api
    avant = {
        chemin: client_api.get(chemin, headers=entete).json()
        for chemin in (
            "/plan/calendriers?culture=courgette&date_ref=2026-07-20",
            "/godets",
            "/stats",
        )
    }
    # Rejouer `/plan` (qui calcule les phases) ne doit rien changer à ces trois-là.
    client_api.get("/plan?date_ref=2026-07-20", headers=entete)
    for chemin, corps in avant.items():
        assert client_api.get(chemin, headers=entete).json() == corps, chemin
    # La phase ne DÉBORDE pas non plus : elle n'est servie que par `/plan`.
    for chemin, corps in avant.items():
        assert "phase_depuis" not in str(corps), chemin
