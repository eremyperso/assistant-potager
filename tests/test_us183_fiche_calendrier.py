"""
tests/test_us183_fiche_calendrier.py — Fiche calendrier d'une culture [US-183]
==============================================================================

Volet serveur : ce que la fiche lit en plus de ce que servaient déjà US-070,
US-176 et US-180 — et rien d'autre (aucun nouvel endpoint, aucune écriture) :

- CA4  `actions` : TOUTES les actions dont la phase a une fenêtre pour la zone,
       dans l'ordre du geste — le sélecteur, même hors fenêtre de la semaine
- CA4  point de vigilance : la tuile (US-180) et la fiche lisent la MÊME
       évaluation ; deux niveaux différents au même instant seraient un bug
- CA8  chaque série en terre porte le nom de sa parcelle (fiche ouverte depuis
       Stocks, qui n'a pas la liste des parcelles)

Le volet d'affichage (trois parties, séries, frise, budget de lectures) est
couvert par `frontend/src/lib/ficheCalendrier.test.js` et `confiance.test.js`.

⚠️ Les fenêtres, durées et rusticités écrites ici sont des VALEURS DE TEST.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import previsions_meteo as svc_previsions
from app.services import recalage_calendrier as rec
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)

LE_15_AOUT = date(2027, 8, 15)
LE_5_MAI = date(2027, 5, 5)


@pytest.fixture
def db(test_db):
    """Un potager en zone océanique, deux parcelles nommées."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="Parcelle 1", nom_normalise="parcelle1", potager_id=1),
        Parcelle(id=2, nom="Parcelle 2", nom_normalise="parcelle2", potager_id=1),
    ])
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


def _tomate(db) -> None:
    """Pépinière février-mars, plantation avril-mai, AUCUN semis en place."""
    fiche = CultureConfig(nom="tomate", type_organe_recolte="fruit", rusticite_min_c=5.0)
    db.add(fiche)
    db.flush()
    it = ItineraireCultural(culture_id=fiche.id, nom="standard", nom_normalise="standard", source_id=1)
    db.add(it)
    db.flush()
    for phase, (debut, fin) in {
        cal.PHASE_SEMIS_PEPINIERE: (2, 3), cal.PHASE_PLANTATION: (4, 5), cal.PHASE_RECOLTE: (7, 9),
    }.items():
        db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="oceanique", phase=phase,
                                mois_debut=debut, mois_fin=fin, source_id=1))
    db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_PLANTATION_RECOLTE,
                          jours_min=60, jours_max=80, source_id=1))
    db.commit()


def _meteo(depart: date, tmin: float):
    return svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_DISPONIBLE,
        meteo={"previsions_etendues": [
            {"date": (depart + timedelta(days=i)).isoformat(), "temp_min": tmin,
             "temp_max": tmin + 10, "horizon_jours": i + 1}
            for i in range(14)
        ]},
        source=svc_previsions.SOURCE_CACHE,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — le sélecteur lit toutes les actions qui ont une fenêtre
# ═════════════════════════════════════════════════════════════════════════════
class TestActionsDeLaFiche:
    def test_us183_selecteur_limite_aux_phases_connues(self, db):
        """[Gherkin: Semer ou planter, pré-positionné] Pépinière et plantation, pas
        de semis en place : le sélecteur ne propose que les deux premières."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        assert [a.action for a in lu.actions] == [conf.ACTION_SEMIS_PEPINIERE, conf.ACTION_PLANTATION]

    def test_us183_actions_proposees_meme_hors_fenetre_de_la_semaine(self, db):
        """[CA4] Le 15 août, la tuile se tait (aucune candidate) mais la fiche
        propose toujours ses deux gestes, chacun avec son niveau et ses motifs."""
        _tomate(db)
        lu = conf.confiances_de_culture(db, "tomate", LE_15_AOUT, 1, _meteo(LE_15_AOUT, 14.0))
        assert lu.candidates == []
        assert len(lu.actions) == 2
        assert all(a.etoiles is not None and len(a.motifs) == 5 for a in lu.actions)

    def test_us183_sans_calendrier_aucune_action(self, db):
        """[Gherkin: Aucun calendrier] Aucune fenêtre : aucune action, jamais une estimation."""
        db.add(CultureConfig(nom="ail", type_organe_recolte="bulbe"))
        db.commit()
        lu = conf.confiances_de_culture(db, "ail", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        assert lu.actions == [] and lu.a_calendrier is False

    def test_us183_tuile_et_fiche_lisent_la_meme_evaluation(self, db):
        """[Gherkin: Même confiance que la tuile] Une candidate de la tuile est
        la MÊME évaluation que l'action de la fiche : mêmes étoiles, mêmes motifs."""
        _tomate(db)
        corps = conf.confiances_culture_en_dict(
            conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        )
        par_action = {a["action"]: a for a in corps["actions"]}
        for candidate in corps["candidates"]:
            assert candidate == par_action[candidate["action"]]

    def test_us183_actions_servies_par_la_lecture_groupee(self, db):
        """[CA13] La fiche n'a pas besoin d'un nouvel endpoint : `actions` voyage
        dans la réponse de la lecture groupée d'US-180."""
        _tomate(db)
        corps = conf.confiances_culture_en_dict(
            conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
        )
        assert set(corps) == {"culture", "culture_connue", "a_calendrier", "candidates", "actions"}


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — chaque série porte le nom de sa parcelle
# ═════════════════════════════════════════════════════════════════════════════
def _evt(db, action, culture, jour, parcelle_id, **champs):
    db.add(Evenement(type_action=action, culture=culture, parcelle_id=parcelle_id, potager_id=1,
                     date=datetime.combine(jour, datetime.min.time()), **champs))
    db.commit()


def test_us183_serie_porte_le_nom_de_sa_parcelle(db):
    """[CA8] Deux séries en terre dans deux parcelles : chacune nomme la sienne."""
    _tomate(db)
    _evt(db, "plantation", "tomate", date(2027, 5, 2), 1)
    _evt(db, "plantation", "tomate", date(2027, 5, 30), 2)
    projections = rec.projections_du_plan(db, ["tomate"], 1, date(2027, 6, 15))
    assert {p["parcelle_id"]: p["parcelle_nom"] for p in projections} == {1: "Parcelle 1", 2: "Parcelle 2"}


def test_us183_aucune_serie_aucune_lecture_de_parcelle(db):
    """[CA10] Sans série en terre, rien à nommer — et la réponse reste une liste vide."""
    _tomate(db)
    assert rec.projections_du_plan(db, ["tomate"], 1, date(2027, 6, 15)) == []


def test_us183_lecture_sans_ecriture(db):
    """La fiche lit et projette ; elle n'écrit rien (CA6 : aucun chemin d'écriture)."""
    _tomate(db)
    _evt(db, "plantation", "tomate", date(2027, 5, 2), 1)
    compter = lambda: (db.query(Evenement).count(), db.query(FenetreCulturale).count())
    avant = compter()
    rec.projections_du_plan(db, ["tomate"], 1, date(2027, 6, 15))
    conf.confiances_de_culture(db, "tomate", LE_5_MAI, 1, _meteo(LE_5_MAI, 11.0))
    assert compter() == avant
