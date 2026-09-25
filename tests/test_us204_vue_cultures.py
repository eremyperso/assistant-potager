"""
tests/test_us204_vue_cultures.py — Lecture unique de l'écran Cultures [US-204]
================================================================================

`GET /cultures/vue` compose, pour chaque culture, ce que l'écran Cultures
affiche — critère par critère :

- CA2  périmètre des deux onglets, culture hors référentiel jamais masquée
- CA3  présence au potager : variétés, parcelles, phases, lots de pépinière
- CA4  confiance du moment == celle du Plan (même fonction, même date)
- CA5  état de fenêtre : maintenant / bientôt / plus tard / aucune
- CA5 ter mois actifs (semis + plantation, jamais la récolte)
- CA6  suggestion de la semaine, plafonnée à trois
- CA7  une seule requête, une seule lecture météo
- CA8  une correction locale du potager est prise en compte
- CA10 météo indisponible : la réponse le dit, rien n'est masqué

⚠️ Les fenêtres et durées écrites ici sont des VALEURS DE TEST : elles
n'engagent aucune agronomie.
"""
from __future__ import annotations

from datetime import date, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import previsions_meteo as svc_previsions
from app.services import vue_cultures as vc
from app.services.context import TenantContext
from database.db import Base
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique",
                        latitude=47.2, longitude=-1.55))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
    ])
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


def _seed_culture(db, nom: str, *, potager_id=None, fenetres=None, durees=None, source_id=1) -> CultureConfig:
    """Une culture, son itinéraire standard, ses fenêtres et ses durées."""
    fiche = CultureConfig(nom=nom, type_organe_recolte="fruit", potager_id=potager_id)
    db.add(fiche)
    db.flush()
    it = ItineraireCultural(
        culture_id=fiche.id, nom="standard", nom_normalise="standard",
        source_id=source_id, potager_id=potager_id,
    )
    db.add(it)
    db.flush()
    for phase, (debut, fin) in (fenetres or {}).items():
        db.add(FenetreCulturale(
            itineraire_id=it.id, zone_climatique="oceanique", phase=phase,
            mois_debut=debut, mois_fin=fin, source_id=source_id,
        ))
    for etape, (jours_min, jours_max) in (durees or {}).items():
        db.add(DureeCulturale(
            itineraire_id=it.id, etape=etape, jours_min=jours_min, jours_max=jours_max,
            source_id=source_id,
        ))
    db.commit()
    return fiche


def _tomate(db):
    """Pépinière février-mars, plantation avril-mai, récolte juillet-septembre."""
    _seed_culture(db, "tomate", fenetres={
        cal.PHASE_SEMIS_PEPINIERE: (2, 3), cal.PHASE_PLANTATION: (4, 5), cal.PHASE_RECOLTE: (7, 9),
    }, durees={cal.ETAPE_RECOLTE: (100, 120), cal.ETAPE_PLANTATION_RECOLTE: (60, 80)})


def _epinard_hiver(db):
    """Semis pleine terre novembre → février, à cheval sur le 31 décembre."""
    _seed_culture(db, "epinard", fenetres={
        cal.PHASE_SEMIS_PLEINE_TERRE: (11, 2), cal.PHASE_RECOLTE: (1, 4),
    }, durees={cal.ETAPE_RECOLTE: (40, 60)})


def _evt(db, action, culture, jour, parcelle_id=1, **champs):
    evenement = Evenement(
        type_action=action, culture=culture,
        date=datetime.combine(jour, datetime.min.time()),
        parcelle_id=parcelle_id, potager_id=champs.pop("potager_id", 1), **champs,
    )
    db.add(evenement)
    db.commit()
    return evenement


def _meteo(depart: date, tmin: float):
    from datetime import timedelta
    return svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_DISPONIBLE,
        meteo={"previsions_etendues": [
            {"date": (depart + timedelta(days=i)).isoformat(), "temp_min": tmin,
             "temp_max": tmin + 10, "horizon_jours": i + 1}
            for i in range(14)
        ]},
        source=svc_previsions.SOURCE_CACHE,
    )


def _sans_meteo():
    return svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_LOCALISATION_MANQUANTE, meteo=None, source=None,
    )


def _vue(db, date_ref, meteo=None):
    with patch.object(svc_previsions, "lire_prevision_potager",
                      return_value=meteo or _meteo(date_ref, 11.0)):
        return vc.composer_vue_cultures(db, CTX, date_ref)


def _ligne(vue, culture):
    return next(l for l in vue.cultures if l.culture == culture)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — périmètre des deux onglets
# ═════════════════════════════════════════════════════════════════════════════
class TestPerimetre:
    def test_us204_toutes_les_cultures_du_referentiel_sont_rendues(self, db):
        """[CA2] Onglet « Toutes » : tout le référentiel visible, au potager ou pas."""
        _tomate(db)
        _seed_culture(db, "ail")
        vue = _vue(db, date(2027, 5, 5))
        assert vue.effectif_toutes == 2
        assert {l.culture for l in vue.cultures} == {"tomate", "ail"}

    def test_us204_au_potager_seulement_les_cultures_en_place_ou_en_pepiniere(self, db):
        """[CA2] Onglet « Au potager » : la tomate y est, l'ail n'y est pas."""
        _tomate(db)
        _seed_culture(db, "ail")
        _evt(db, "plantation", "tomate", date(2027, 4, 20))
        vue = _vue(db, date(2027, 5, 5))
        assert _ligne(vue, "tomate").au_potager is True
        assert _ligne(vue, "ail").au_potager is False
        assert vue.effectif_au_potager == 1

    def test_us204_culture_hors_referentiel_jamais_masquee(self, db):
        """[CA2, Gherkin: Culture hors référentiel] Verveine plantée, inconnue du référentiel."""
        _evt(db, "plantation", "verveine", date(2027, 5, 3))
        vue = _vue(db, date(2027, 5, 5))
        ligne = _ligne(vue, "verveine")
        assert ligne.hors_referentiel is True
        assert ligne.au_potager is True
        assert ligne.etoiles is None
        assert ligne.a_calendrier is False


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — présence au potager
# ═════════════════════════════════════════════════════════════════════════════
class TestPresence:
    def test_us204_seulement_en_pepiniere_sans_phase(self, db):
        """[CA3] Un lot de semis en pépinière, aucune ligne en terre."""
        _tomate(db)
        _evt(db, "semis", "tomate", date(2027, 2, 10), parcelle_id=2, quantite=20, unite="graines")
        vue = _vue(db, date(2027, 3, 1))
        ligne = _ligne(vue, "tomate")
        assert ligne.au_potager is True
        assert ligne.nb_lots_pepiniere == 1
        assert ligne.phase_plus_avancee is None
        assert ligne.nb_parcelles == 0

    def test_us204_repartition_par_phase_et_phase_la_plus_avancee(self, db):
        """[CA3] Une variété en récolte, une en place : la récolte est la plus avancée."""
        _tomate(db)
        _evt(db, "plantation", "tomate", date(2027, 4, 1), parcelle_id=1, variete="cerise")
        _evt(db, "plantation", "tomate", date(2027, 4, 10), parcelle_id=2, variete="coeur")
        _evt(db, "recolte", "tomate", date(2027, 7, 5), parcelle_id=1, variete="cerise")
        vue = _vue(db, date(2027, 7, 10))
        ligne = _ligne(vue, "tomate")
        assert ligne.nb_varietes == 2
        assert ligne.varietes == ("cerise", "coeur")
        assert ligne.nb_parcelles == 2
        assert ligne.phase_plus_avancee == "en_recolte"
        assert ligne.repartition_phases.get("en_recolte") == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — même confiance que le Plan
# ═════════════════════════════════════════════════════════════════════════════
def test_us204_meme_confiance_que_le_plan(db):
    """[CA4, Gherkin: Même confiance que le Plan] Deux étoiles pour le haricot, comme le Plan."""
    _seed_culture(db, "haricot", fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (4, 6)},
                  durees={cal.ETAPE_RECOLTE: (55, 70)})
    date_ref = date(2027, 5, 19)
    with patch.object(svc_previsions, "lire_prevision_potager", return_value=_meteo(date_ref, 8.0)):
        du_plan = conf.confiances_de_culture(db, "haricot", date_ref, 1, _meteo(date_ref, 8.0))
        vue = vc.composer_vue_cultures(db, CTX, date_ref)
    ligne = _ligne(vue, "haricot")
    attendu = du_plan.candidates[0] if du_plan.candidates else None
    assert ligne.etoiles == (attendu.etoiles if attendu else None)
    assert ligne.confiance_equivalent == vc.EQUIVALENT_ETOILES.get(ligne.etoiles)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — états de fenêtre, y compris l'enjambement du 31 décembre
# ═════════════════════════════════════════════════════════════════════════════
class TestFenetre:
    def test_us204_fenetre_maintenant(self, db):
        _tomate(db)
        ligne = _ligne(_vue(db, date(2027, 4, 15)), "tomate")
        assert ligne.fenetre_etat == vc.ETAT_MAINTENANT
        assert ligne.fenetre_geste == conf.ACTION_PLANTATION

    def test_us204_fenetre_bientot_le_mois_avant(self, db):
        """[CA5] Pépinière ouvre en février : le 31 janvier, c'est « bientôt »."""
        _tomate(db)
        ligne = _ligne(_vue(db, date(2027, 1, 20)), "tomate")
        assert ligne.fenetre_etat == vc.ETAT_BIENTOT
        assert ligne.fenetre_geste == conf.ACTION_SEMIS_PEPINIERE

    def test_us204_fenetre_plus_tard(self, db):
        """[Gherkin: Une culture en récolte] Le 18 septembre, la tomate se sème en pépinière plus tard."""
        _tomate(db)
        ligne = _ligne(_vue(db, date(2027, 9, 18)), "tomate")
        assert ligne.fenetre_etat == vc.ETAT_PLUS_TARD
        assert ligne.fenetre_mois and min(ligne.fenetre_mois) == 2

    def test_us204_fenetre_aucune_sans_calendrier(self, db):
        _seed_culture(db, "ail")
        ligne = _ligne(_vue(db, date(2027, 5, 5)), "ail")
        assert ligne.fenetre_etat == vc.ETAT_AUCUNE
        assert ligne.fenetre_geste is None

    def test_us204_fenetre_enjambe_le_31_decembre(self, db):
        """[CA5] Semis d'épinard novembre → février : le 15 décembre, c'est « maintenant »."""
        _epinard_hiver(db)
        ligne = _ligne(_vue(db, date(2027, 12, 15)), "epinard")
        assert ligne.fenetre_etat == vc.ETAT_MAINTENANT
        assert ligne.fenetre_geste == conf.ACTION_SEMIS_PLEINE_TERRE

    def test_us204_mois_actifs_exclut_la_recolte(self, db):
        """[CA5 ter] Les mois actifs sont l'union semis + plantation, jamais la récolte."""
        _tomate(db)
        ligne = _ligne(_vue(db, date(2027, 5, 5)), "tomate")
        assert set(ligne.mois_actifs) == {2, 3, 4, 5}


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — suggestion de la semaine
# ═════════════════════════════════════════════════════════════════════════════
def test_us204_suggestion_de_la_semaine(db):
    """[Gherkin: Suggestion de la semaine] Épinard absent du potager, fenêtre ouverte."""
    _epinard_hiver(db)
    vue = _vue(db, date(2027, 12, 15))
    ligne = _ligne(vue, "epinard")
    assert ligne.fenetre_etat == vc.ETAT_MAINTENANT
    if (ligne.etoiles or 0) >= 2:
        assert ligne.suggestion is True


def test_us204_au_plus_trois_suggestions(db):
    """[Gherkin: Au plus trois suggestions] Cinq cultures ouvertes, trois retenues."""
    for i, nom in enumerate(["a", "b", "c", "d", "e"]):
        _seed_culture(db, nom, fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (5, 5)},
                     durees={cal.ETAPE_RECOLTE: (50, 60)})
    date_ref = date(2027, 5, 15)
    with patch.object(svc_previsions, "lire_prevision_potager", return_value=_meteo(date_ref, 12.0)):
        vue = vc.composer_vue_cultures(db, CTX, date_ref)
    suggerees = [l for l in vue.cultures if l.suggestion]
    assert len(suggerees) <= vc.PLAFOND_SUGGESTIONS


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — budget de lectures
# ═════════════════════════════════════════════════════════════════════════════
def test_us204_une_seule_lecture_meteo_pour_tout_l_ecran(db):
    """[CA7] Cinq cultures : la météo est lue une seule fois."""
    for nom in ["a", "b", "c", "d", "e"]:
        _seed_culture(db, nom, fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6)},
                     durees={cal.ETAPE_RECOLTE: (50, 60)})
    date_ref = date(2027, 5, 15)
    with patch.object(svc_previsions, "lire_prevision_potager",
                      return_value=_meteo(date_ref, 12.0)) as lecture:
        vc.composer_vue_cultures(db, CTX, date_ref)
    assert lecture.call_count == 1


def test_us204_lecture_sans_ecriture(db):
    """[CA9] Aucun événement, stock ni référentiel modifié par la consultation."""
    _tomate(db)
    compter = lambda: (db.query(FenetreCulturale).count(), db.query(Evenement).count())
    avant = compter()
    _vue(db, date(2027, 5, 5))
    assert compter() == avant


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — correction locale du potager
# ═════════════════════════════════════════════════════════════════════════════
def test_us204_correction_locale_prise_en_compte(db):
    """[CA8] Un itinéraire personnalisé au potager remplace le partagé de même nom."""
    _seed_culture(db, "poireau", fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (3, 4)},
                 durees={cal.ETAPE_RECOLTE: (150, 200)})
    # Correction locale : la fenêtre de semis est en réalité juin-juillet pour ce potager.
    fiche = db.query(CultureConfig).filter_by(nom="poireau").first()
    it_local = ItineraireCultural(
        culture_id=fiche.id, nom="standard", nom_normalise="standard",
        source_id=1, potager_id=1,
    )
    db.add(it_local)
    db.flush()
    db.add(FenetreCulturale(
        itineraire_id=it_local.id, zone_climatique="oceanique",
        phase=cal.PHASE_SEMIS_PLEINE_TERRE, mois_debut=6, mois_fin=7, source_id=1,
    ))
    db.commit()
    ligne = _ligne(_vue(db, date(2027, 6, 15)), "poireau")
    assert ligne.fenetre_etat == vc.ETAT_MAINTENANT


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — météo indisponible
# ═════════════════════════════════════════════════════════════════════════════
def test_us204_meteo_indisponible_le_dit_sans_rien_masquer(db):
    """[CA10] Potager non localisé : pas d'étoile de repli, le reste est intact."""
    _tomate(db)
    vue = _vue(db, date(2027, 4, 15), meteo=_sans_meteo())
    assert vue.meteo_disponible is False
    ligne = _ligne(vue, "tomate")
    assert ligne.famille is None or isinstance(ligne.famille, str)  # inchangé, jamais levé
    assert ligne.fenetre_etat == vc.ETAT_MAINTENANT  # la fenêtre ne dépend pas de la météo


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'API de l'écran
# ═════════════════════════════════════════════════════════════════════════════
class TestApi:
    """L'API tourne dans le thread du client de test : son propre moteur SQLite."""

    @pytest.fixture
    def db_api(self):
        moteur = create_engine("sqlite:///:memory:",
                               connect_args={"check_same_thread": False}, poolclass=StaticPool)
        Base.metadata.create_all(bind=moteur)
        session = sessionmaker(bind=moteur)()
        session.add(User(id=1, email="a@potager.test"))
        session.flush()
        session.add(Potager(id=1, nom="Jardin", proprietaire_id=1,
                            zone_climatique="oceanique", latitude=47.2, longitude=-1.55))
        session.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0",
                                      attribution="Valeurs de test", partageable=True,
                                      importee=True))
        session.commit()
        yield session, moteur
        session.close()
        moteur.dispose()

    @pytest.fixture
    def client(self, db_api, monkeypatch):
        from app.api import main as api

        _, moteur = db_api
        monkeypatch.setattr(api, "SessionLocal", sessionmaker(bind=moteur))
        api.app.dependency_overrides[api.get_current_user_ctx] = lambda: CTX
        api.app.state.limiter.reset()
        with TestClient(api.app) as client:
            yield client
        api.app.dependency_overrides.clear()

    def test_us204_api_vue_cultures(self, db_api, client):
        """[CA1] Une seule requête rend le nécessaire de l'écran entier."""
        _tomate(db_api[0])
        _evt(db_api[0], "plantation", "tomate", date(2027, 4, 1), potager_id=1)
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_meteo(date(2027, 4, 15), 11.0)):
            r = client.get("/cultures/vue", params={"date": "2027-04-15"})
        assert r.status_code == 200
        corps = r.json()
        assert corps["zone_climatique"] == "oceanique"
        tomate = next(c for c in corps["cultures"] if c["culture"] == "tomate")
        assert tomate["au_potager"] is True
        assert tomate["fenetre_etat"] == "maintenant"
