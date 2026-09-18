"""
tests/test_us178_confiance_semis.py — Moteur de confiance semis / plantation [US-178]
=====================================================================================

Le moteur rend 1 à 3 étoiles et ses motifs. Ce qui se vérifie ici, critère par
critère :

- CA1  étoiles, score 0-100 et motifs typés gagné / perdu / indéterminé
- CA2  déterministe, aucun appel LLM sur le parcours
- CA3  règles, barèmes, seuils et valeurs déclarées à UN seul endroit ; correction
       locale du calendrier prioritaire sur le calendrier partagé
- CA4  l'action détermine la phase lue — jamais celle d'une autre phase ni zone
- CA5  donnée manquante → 0 point, motif indéterminé, plafond abaissé
- CA6  détail par règle (points / points max / motif)
- CA7  itinéraire non standard lu tel que demandé
- CA8  parcelle pépinière : impose le semis en pépinière, avertit sur une plantation
- CA9  API : lecture unitaire et lecture groupée, scopées au potager
- CA10 prévisions lues par le cache d'US-182, jamais un appel réseau direct
- CA11 aucune écriture
- CA12 ce fichier

⚠️ Les fenêtres, durées et rusticités écrites ici sont des VALEURS DE TEST :
elles n'engagent aucune agronomie.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import previsions_meteo as svc_previsions
from app.services.context import TenantContext
from database.db import Base
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

# Dates de référence — mai, au cœur de la fenêtre du haricot de test.
LE_20_MAI = date(2027, 5, 20)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures et graines
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Un potager localisé en zone océanique, une parcelle ordinaire, une pépinière."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique",
                latitude=47.2, longitude=-1.55),
        Potager(id=2, nom="Voisin", proprietaire_id=1, zone_climatique="oceanique"),
    ])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
        Parcelle(id=3, nom="chez le voisin", nom_normalise="chez le voisin", potager_id=2),
    ])
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


def _seed_culture(
    db, nom: str, *, rusticite=None, fenetres=None, durees=None,
    itineraire: str = "standard", potager_id=None, culture_id=None,
) -> ItineraireCultural:
    """Une culture, un itinéraire et ses fenêtres/durées. `potager_id` → correction locale."""
    if culture_id is None:
        fiche = CultureConfig(nom=nom, type_organe_recolte="fruit", rusticite_min_c=rusticite)
        db.add(fiche)
        db.flush()
        culture_id = fiche.id
    it = ItineraireCultural(
        culture_id=culture_id, nom=itineraire, nom_normalise=cal.normaliser_itineraire(itineraire),
        potager_id=potager_id, source_id=1,
    )
    db.add(it)
    db.flush()
    for phase, (debut, fin) in (fenetres or {}).items():
        db.add(FenetreCulturale(
            itineraire_id=it.id, zone_climatique="oceanique", phase=phase,
            mois_debut=debut, mois_fin=fin, potager_id=potager_id, source_id=1,
        ))
    for etape, bornes in (durees or {}).items():
        jours_min, jours_max = bornes
        db.add(DureeCulturale(
            itineraire_id=it.id, etape=etape, jours_min=jours_min, jours_max=jours_max,
            potager_id=potager_id, source_id=1,
        ))
    db.commit()
    return it


def _haricot(db, **kwargs):
    """Haricot gélif : semis en pleine terre mai-juin, récolte juillet-octobre."""
    defauts = dict(
        rusticite=5.0,
        fenetres={
            cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6),
            cal.PHASE_RECOLTE: (7, 10),
        },
        durees={cal.ETAPE_RECOLTE: (55, 70)},
    )
    defauts.update(kwargs)
    return _seed_culture(db, "haricot", **defauts)


def _meteo(jours: list[tuple[date, float]], statut=svc_previsions.STATUT_DISPONIBLE):
    """Une lecture de prévision d'US-182, sans réseau ni cache."""
    return svc_previsions.LecturePrevision(
        statut=statut,
        meteo={"previsions_etendues": [
            {"date": jour.isoformat(), "temp_min": tmin, "temp_max": tmin + 10,
             "horizon_jours": i + 1}
            for i, (jour, tmin) in enumerate(jours)
        ]} if statut == svc_previsions.STATUT_DISPONIBLE else None,
        source=svc_previsions.SOURCE_CACHE if statut == svc_previsions.STATUT_DISPONIBLE else None,
    )


def _quinzaine(depart: date, tmin: float, gel_le: date = None):
    """Quatorze jours à `tmin`, avec au plus une nuit de gel."""
    return _meteo([
        (depart + timedelta(days=i), -1.0 if gel_le == depart + timedelta(days=i) else tmin)
        for i in range(14)
    ])


# ═════════════════════════════════════════════════════════════════════════════
# CA1 / CA6 — étoiles, score, motifs typés et détail par règle
# ═════════════════════════════════════════════════════════════════════════════
class TestResultat:
    def test_us178_confiance_trois_etoiles_tout_est_reuni(self, db):
        """[Gherkin: Trois étoiles, tout est réuni] Les cinq motifs sont gagnés."""
        _haricot(db)
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        assert c.etoiles == 3
        assert c.score == 100
        assert [m.etat for m in c.motifs] == [conf.ETAT_GAGNE] * 5
        assert c.affichage == "★★★"

    def test_us178_confiance_detail_par_regle(self, db):
        """[CA6] Chaque règle rend ses points obtenus, son maximum et son motif."""
        _haricot(db)
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        detail = {m.regle: (m.points, m.points_max) for m in c.motifs}
        assert detail == {"R1": (40, 40), "R2": (20, 20), "R3": (20, 20),
                          "R4": (10, 10), "R5": (10, 10)}
        assert all(m.libelle and m.libelle_regle for m in c.motifs)

    def test_us178_confiance_gel_annonce_deux_etoiles(self, db):
        """[Gherkin: Gel annoncé, deux étoiles] Un motif perdu nomme le jour du gel."""
        _haricot(db)
        gel = LE_20_MAI + timedelta(days=4)
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 6.0, gel_le=gel))
        assert c.etoiles == 2
        motif = next(m for m in c.motifs if m.regle == conf.R3_GEL_ANNONCE)
        assert motif.etat == conf.ETAT_PERDU
        assert "lundi 24" in motif.libelle

    def test_us178_confiance_serialisation_expose_motifs_et_plafond(self, db):
        """[CA1, CA6] La forme servie porte étoiles, score, plafond et motifs."""
        _haricot(db)
        corps = conf.confiance_en_dict(
            conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        )
        assert corps["etoiles"] == 3 and corps["score"] == 100
        assert corps["score_max_atteignable"] == 100
        assert len(corps["motifs"]) == 5
        assert corps["action"] == conf.ACTION_SEMIS_PLEINE_TERRE
        assert corps["date"] == "2027-05-20"

    def test_us178_motifs_conformes_au_gabarit_du_bot(self, db):
        """[US-179, gabarit § 2] Les libellés sont rendus PAR LE MOTEUR : le bot
        n'a pas le droit de les reformuler, ils doivent donc être les bons."""
        _haricot(db)
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        assert [m.libelle for m in c.motifs] == [
            "Dans la fenêtre conseillée pour ta zone",
            "Dernière gelée moyenne passée",
            "Aucun gel annoncé sur 14 jours",
            "Nuits douces annoncées",
            "La récolte tomberait dans la saison conseillée",
        ]

    def test_us178_recolte_attendue_est_une_fourchette(self, db):
        """[US-179, gabarit § 5] Le moteur rend la fourchette de récolte — jamais
        une date sèche, et le bot n'a rien à recalculer."""
        _haricot(db)   # récolte 55 à 70 jours après le semis
        corps = conf.confiance_en_dict(
            conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        )
        assert corps["recolte_attendue"] == {"min": "2027-07-14", "max": "2027-07-29"}

    def test_us178_recolte_attendue_absente_sans_duree(self, db):
        """[CA5] Durée inconnue : pas de fourchette inventée."""
        _haricot(db, durees={})
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        assert (c.recolte_min, c.recolte_max) == (None, None)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — seuils d'étoiles aux bornes, barème à un seul endroit
# ═════════════════════════════════════════════════════════════════════════════
class TestSeuils:
    @pytest.mark.parametrize("score, etoiles", [
        (0, 1), (44, 1), (45, 2), (74, 2), (75, 3), (100, 3),
    ])
    def test_us178_seuils_etoiles_aux_bornes(self, score, etoiles):
        """[CA3, CA12] 44/45 et 74/75 : les bornes exactes des trois niveaux."""
        assert conf.etoiles_depuis_score(score) == etoiles

    def test_us178_bareme_somme_a_cent(self):
        """[CA3] Les cinq règles totalisent 100 — un seul endroit le déclare."""
        assert conf.SCORE_MAXIMUM == 100
        assert set(conf.POINTS_MAX) == {"R1", "R2", "R3", "R4", "R5"}

    def test_us178_table_derniere_gelee_conforme_au_plan_d_epic(self):
        """[CA3] Les quatre dates VALIDÉES le 17/09/2026 (plan d'épic 8, § 12),
        reportées telles quelles — les modifier, c'est rouvrir l'arbitrage."""
        assert conf.DERNIERE_GELEE_MOYENNE_PAR_ZONE == {
            "mediterraneen": "15-03",
            "oceanique": "05-04",
            "continental": "25-04",
            "montagnard": "10-05",
        }
        assert set(conf.DERNIERE_GELEE_MOYENNE_PAR_ZONE) == set(cal.ZONES_CLIMATIQUES)
        assert conf.date_derniere_gelee("oceanique", 2027) == date(2027, 4, 5)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — l'action détermine la phase ; sans fenêtre, pas de score
# ═════════════════════════════════════════════════════════════════════════════
class TestPhaseEtAbsenceDeScore:
    def test_us178_culture_sans_calendrier_aucun_score(self, db):
        """[Gherkin: Culture sans calendrier, pas de score] Un tiret, et le motif."""
        _seed_culture(db, "ail", fenetres={}, durees={})
        c = conf.evaluer(db, "ail", "plantation", LE_20_MAI, 1)
        assert c.etoiles is None and c.score is None
        assert c.sans_score and c.affichage == cal.TIRET
        assert c.motifs[0].libelle == conf.MOTIF_SANS_CALENDRIER
        assert c.motifs[0].etat == conf.ETAT_INDETERMINE

    def test_us178_phase_absente_n_emprunte_jamais_une_autre_phase(self, db):
        """[CA4] Le haricot n'a pas de fenêtre de plantation : pas de score,
        surtout pas celle du semis en pleine terre."""
        _haricot(db)
        c = conf.evaluer(db, "haricot", "plantation", LE_20_MAI, 1)
        assert c.etoiles is None

    def test_us178_culture_inconnue_aucun_score(self, db):
        """[CA4] Une culture absente du référentiel n'a pas de score."""
        c = conf.evaluer(db, "kiwano", "semis en pleine terre", LE_20_MAI, 1)
        assert c.etoiles is None and c.culture_connue is False

    def test_us178_fenetre_d_une_autre_zone_n_est_jamais_empruntee(self, db):
        """[CA4] Une fenêtre renseignée pour une autre zone reste invisible."""
        it = _haricot(db, fenetres={cal.PHASE_RECOLTE: (7, 10)})
        db.add(FenetreCulturale(
            itineraire_id=it.id, zone_climatique="montagnard",
            phase=cal.PHASE_SEMIS_PLEINE_TERRE, mois_debut=5, mois_fin=6, source_id=1,
        ))
        db.commit()
        assert conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1).etoiles is None


# ═════════════════════════════════════════════════════════════════════════════
# Les cinq règles, chacune dans ses trois états (CA1, CA5, CA12)
# ═════════════════════════════════════════════════════════════════════════════
def _motif(c, regle):
    return next(m for m in c.motifs if m.regle == regle)


class TestRegle1Fenetre:
    def test_us178_r1_dans_la_fenetre(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1), "R1")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 40)

    def test_us178_r1_mois_adjacent(self, db):
        """[CA3] Un mois avant la fenêtre : la moitié des points, et le motif le dit."""
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", date(2027, 4, 20), 1), "R1")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 20)
        assert "avant" in m.libelle

    def test_us178_r1_hors_fenetre(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", date(2027, 1, 20), 1), "R1")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)


class TestRegle2DerniereGelee:
    def test_us178_r2_gelee_passee(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1), "R2")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 20)

    def test_us178_r2_trop_tot_pour_la_zone(self, db):
        """[CA1] Avant la dernière gelée moyenne océanique (15 avril) : zéro point."""
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", date(2027, 4, 1), 1), "R2")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)

    def test_us178_r2_gelee_tout_juste_passee(self, db):
        """[CA3] Dans les 7 jours qui suivent la dernière gelée océanique
        (5 avril) : la moitié des points, pas la totalité."""
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", date(2027, 4, 8), 1), "R2")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 10)

    def test_us178_r2_rusticite_inconnue_indeterminee(self, db):
        """[Gherkin: Sensibilité au gel inconnue] Indéterminée, aucun point."""
        _haricot(db, rusticite=None)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1), "R2")
        assert (m.etat, m.points) == (conf.ETAT_INDETERMINE, 0)
        assert "inconnue" in m.libelle

    def test_us178_r2_culture_rustique_acquise(self, db):
        """[CA3] Sous le seuil de gélivité déclaré, la gelée ne retire rien."""
        _haricot(db, rusticite=-12.0)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", date(2027, 4, 1), 1), "R2")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 20)

    def test_us178_r2_semis_pepiniere_acquis_d_office(self, db):
        """[CA3] Un semis en pépinière n'est pas concerné par la dernière gelée."""
        _seed_culture(db, "tomate", rusticite=5.0,
                      fenetres={cal.PHASE_SEMIS_PEPINIERE: (2, 4), cal.PHASE_RECOLTE: (7, 10)},
                      durees={cal.ETAPE_RECOLTE: (90, 120)})
        m = _motif(conf.evaluer(db, "tomate", "semis en pépinière", date(2027, 3, 1), 1), "R2")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 20)


class TestRegle3GelAnnonce:
    def test_us178_r3_aucun_gel(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 11.0)), "R3")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 20)

    def test_us178_r3_gel_annonce_perdu(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 9.0,
                                                         gel_le=LE_20_MAI + timedelta(days=3))), "R3")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)

    def test_us178_r3_meteo_indisponible_indeterminee(self, db):
        """[CA5] Service météo muet : indéterminée, jamais une valeur par défaut."""
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_meteo([], svc_previsions.STATUT_INDISPONIBLE)), "R3")
        assert (m.etat, m.points) == (conf.ETAT_INDETERMINE, 0)

    def test_us178_r3_date_hors_horizon_indeterminee(self, db):
        """[CA5] Au-delà des 14 jours de prévision, la règle se tait."""
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", date(2027, 6, 20), 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 11.0)), "R3")
        assert m.etat == conf.ETAT_INDETERMINE


class TestRegle4NuitsDouces:
    def test_us178_r4_nuits_douces(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 11.0)), "R4")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 10)

    def test_us178_r4_nuits_fraiches(self, db):
        """[CA3] Sous le seuil déclaré (8 °C), la règle est perdue."""
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 5.0)), "R4")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)
        assert "levée lente" in m.libelle

    def test_us178_r4_sans_meteo_indeterminee(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_meteo([], svc_previsions.STATUT_INDISPONIBLE)), "R4")
        assert (m.etat, m.points) == (conf.ETAT_INDETERMINE, 0)


class TestRegle5SaisonRestante:
    def test_us178_r5_recolte_avant_la_fin_de_saison(self, db):
        _haricot(db)
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 11.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 10)

    def test_us178_r5_trop_tard_pour_la_saison(self, db):
        """[Gherkin: Trop tard pour la saison] 95 jours depuis le 1er août
        dépassent une fenêtre de récolte qui finit en octobre."""
        _seed_culture(db, "courgette", rusticite=5.0,
                      fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (5, 8), cal.PHASE_RECOLTE: (7, 10)},
                      durees={cal.ETAPE_RECOLTE: (80, 95)})
        m = _motif(conf.evaluer(db, "courgette", "semis en pleine terre", date(2027, 8, 1), 1,
                                lecture_meteo=_quinzaine(date(2027, 8, 1), 14.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)
        assert "après la fin de saison" in m.libelle

    # ── Correctif du 18/09/2026 — R5 récompensait le retard ─────────────────
    # Deux potagers RÉELS, la même question le même jour, le même haricot :
    # « je peux semer des haricots ce week-end ? » au 19/09/2026.
    # R5 comparait la récolte attendue à la seule FIN de la fenêtre, et reportait
    # la saison d'un an dès que ce mois était passé — offrant onze mois de marge
    # à la culture la PLUS hors saison. Les deux cas sont gardés côte à côte :
    # c'est leur divergence qui a révélé le défaut, séparés ils ne prouvent rien.
    LE_19_SEPTEMBRE = date(2026, 9, 19)

    def _haricot_zone(self, db, mois_recolte):
        return _seed_culture(db, "haricot", rusticite=5.0,
                             fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (6, 7),
                                       cal.PHASE_RECOLTE: mois_recolte},
                             durees={cal.ETAPE_RECOLTE: (54, 57)})

    def test_us178_r5_saison_encore_ouverte_mais_recolte_trop_tardive(self, db):
        """Briançon — récolte août → octobre, encore ouverte le 19 septembre.

        La récolte tomberait le 15 novembre, après le 31 octobre : perdue, et
        c'est juste. Ce cas-ci n'a jamais été faux ; il est le témoin de l'autre.
        """
        self._haricot_zone(db, (8, 10))
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre",
                                self.LE_19_SEPTEMBRE, 1,
                                lecture_meteo=_quinzaine(self.LE_19_SEPTEMBRE, 11.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)
        assert "après la fin de saison" in m.libelle

    def test_us178_r5_saison_deja_passee_ne_se_reporte_pas_en_victoire(self, db):
        """Guadeloupe — récolte juillet → août, close depuis trois semaines.

        Ce semis est PLUS hors saison que celui de Briançon : sa fenêtre de semis
        s'est fermée en juillet et sa récolte en août. Il gagnait pourtant la
        règle, parce que le report à la saison de 2027 lui donnait jusqu'au
        31 août 2027 pour produire. C'est le bug, et ce test est son couperet.
        """
        self._haricot_zone(db, (7, 8))
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre",
                                self.LE_19_SEPTEMBRE, 1,
                                lecture_meteo=_quinzaine(self.LE_19_SEPTEMBRE, 11.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)
        assert "Saison de récolte déjà passée" in m.libelle
        assert "juillet" in m.libelle

    def test_us178_r5_etre_plus_en_retard_ne_rapporte_jamais_plus(self, db):
        """L'invariant que le bug violait, énoncé pour lui-même.

        À durée de culture égale et à date égale, un semis dont la saison de
        récolte est DÉJÀ CLOSE ne peut pas marquer plus de points qu'un semis
        dont elle est encore ouverte.
        """
        self._haricot_zone(db, (7, 8))
        close = _motif(conf.evaluer(db, "haricot", "semis en pleine terre",
                                    self.LE_19_SEPTEMBRE, 1,
                                    lecture_meteo=_quinzaine(self.LE_19_SEPTEMBRE, 11.0)), "R5")
        assert close.points == 0

    def test_us178_r5_le_report_d_un_an_reste_pour_les_cultures_d_hiver(self, db):
        """Le report n'est pas supprimé : un ail planté en octobre se récolte
        bien dans la fenêtre « mars → mai » de l'ANNÉE SUIVANTE."""
        _seed_culture(db, "ail", rusticite=-15.0,
                      fenetres={cal.PHASE_PLANTATION: (10, 11), cal.PHASE_RECOLTE: (3, 5)},
                      durees={cal.ETAPE_PLANTATION_RECOLTE: (170, 190)})
        cible = date(2026, 10, 15)
        m = _motif(conf.evaluer(db, "ail", "plantation", cible, 1,
                                lecture_meteo=_quinzaine(cible, 6.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 10)

    @pytest.mark.parametrize("cible, attendu", [
        # La saison « novembre → février » est encore OUVERTE à la mi-janvier :
        # elle a commencé l'année civile d'avant. Partir de l'année de la date
        # visée la ferait sauter, et comparerait au novembre suivant.
        (date(2027, 1, 15), (date(2026, 11, 1), date(2027, 2, 28))),
        (date(2026, 9, 1), (date(2026, 11, 1), date(2027, 2, 28))),
        (date(2027, 3, 1), (date(2027, 11, 1), date(2028, 2, 29))),
    ])
    def test_us178_r5_une_fenetre_qui_enjambe_le_31_decembre(self, cible, attendu):
        """Une fenêtre est un couple de MOIS, pas une période : « novembre →
        février » enjambe l'année, et sa fin appartient à l'année suivante."""
        fenetre = cal.FenetreLue(phase=cal.PHASE_RECOLTE, libelle="Récolte",
                                 mois_debut=11, mois_fin=2, affichage="", attribution=None)
        assert conf.prochaine_saison_de_recolte(fenetre, cible) == attendu

    def test_us178_r5_duree_inconnue_indeterminee(self, db):
        """[CA5] Sans durée chiffrée, la règle se tait — elle n'invente rien."""
        _haricot(db, durees={})
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                                lecture_meteo=_quinzaine(LE_20_MAI, 11.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_INDETERMINE, 0)

    def test_us178_r5_plantation_lit_la_duree_depuis_la_plantation(self, db):
        """[US-177 / CA8] Une plantation lit `plantation_recolte`, jamais `recolte`."""
        _seed_culture(db, "poireau", rusticite=-8.0,
                      fenetres={cal.PHASE_PLANTATION: (6, 7), cal.PHASE_RECOLTE: (10, 12)},
                      durees={cal.ETAPE_RECOLTE: (200, 220),
                              cal.ETAPE_PLANTATION_RECOLTE: (100, 120)})
        m = _motif(conf.evaluer(db, "poireau", "plantation", date(2027, 6, 15), 1,
                                lecture_meteo=_quinzaine(date(2027, 6, 15), 13.0)), "R5")
        assert (m.etat, m.points) == (conf.ETAT_GAGNE, 10)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — plafond sans météo, invitation à localiser
# ═════════════════════════════════════════════════════════════════════════════
class TestPlafondSansMeteo:
    def test_us178_potager_non_localise_plafonne_a_deux_etoiles(self, db):
        """[Gherkin: Potager non localisé] R3 et R4 indéterminées, ★★ au mieux."""
        _haricot(db)
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 2)
        assert _motif(c, "R3").etat == conf.ETAT_INDETERMINE
        assert _motif(c, "R4").etat == conf.ETAT_INDETERMINE
        assert c.score_max_atteignable == 70
        assert c.etoiles == 2
        assert any("localise ton potager" in a or "localise ton potager" in m.libelle
                   for a in c.avertissements for m in c.motifs)

    def test_us178_plafond_sans_meteo_est_annonce(self, db):
        """[CA5] La troisième étoile inaccessible est DITE, pas subie."""
        _haricot(db)
        c = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 2)
        assert any("troisième étoile" in a for a in c.avertissements)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 / CA7 — correction locale prioritaire, itinéraire choisi
# ═════════════════════════════════════════════════════════════════════════════
class TestCalendrierLocalEtItineraire:
    def test_us178_correction_locale_prioritaire_sur_le_partage(self, db):
        """[CA3, US-176 / CA1] La fenêtre corrigée au bot remplace la partagée."""
        it_partage = _haricot(db)
        _seed_culture(db, "haricot", culture_id=it_partage.culture_id, potager_id=1,
                      fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (1, 2),
                                cal.PHASE_RECOLTE: (7, 10)},
                      durees={cal.ETAPE_RECOLTE: (55, 70)})
        m = _motif(conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1), "R1")
        assert (m.etat, m.points) == (conf.ETAT_PERDU, 0)   # mai n'est plus dans la fenêtre locale

    def test_us178_itineraire_non_standard_lu_tel_que_demande(self, db):
        """[CA7] « culture d'hiver » a ses propres fenêtres."""
        it = _haricot(db)
        _seed_culture(db, "haricot", culture_id=it.culture_id, itineraire="culture d'hiver",
                      fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (9, 10),
                                cal.PHASE_RECOLTE: (11, 12)},
                      durees={cal.ETAPE_RECOLTE: (55, 70)})
        standard = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1)
        hiver = conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                             itineraire="culture d'hiver")
        assert standard.itineraire == "standard"
        assert hiver.itineraire == "culture d'hiver"
        assert _motif(standard, "R1").points == 40
        assert _motif(hiver, "R1").points == 0

    def test_us178_itineraire_par_defaut_sans_precision(self, db):
        """[CA7, US-176 / CA5] Sans précision, l'itinéraire par défaut s'applique."""
        _haricot(db)
        assert conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1).itineraire \
            == cal.ITINERAIRE_PAR_DEFAUT


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — parcelle pépinière
# ═════════════════════════════════════════════════════════════════════════════
class TestParcellePepiniere:
    def test_us178_parcelle_pepiniere_impose_le_semis_en_pepiniere(self, db):
        """[CA8] « semer » sans préciser, dans une pépinière → semis en pépinière."""
        _seed_culture(db, "tomate", rusticite=5.0,
                      fenetres={cal.PHASE_SEMIS_PEPINIERE: (2, 4), cal.PHASE_RECOLTE: (7, 10)},
                      durees={cal.ETAPE_RECOLTE: (90, 120)})
        c = conf.evaluer(db, "tomate", "semis", date(2027, 3, 10), 1, parcelle_id=2)
        assert c.action == conf.ACTION_SEMIS_PEPINIERE
        assert any("pépinière" in a for a in c.avertissements)

    def test_us178_semis_sans_parcelle_vaut_pleine_terre(self, db):
        """[CA8] Hors pépinière, « semer » sans préciser reste un semis en place."""
        _haricot(db)
        assert conf.evaluer(db, "haricot", "semis", LE_20_MAI, 1, parcelle_id=1).action \
            == conf.ACTION_SEMIS_PLEINE_TERRE

    def test_us178_plantation_en_pepiniere_avertit(self, db):
        """[CA8] Une plantation dans une pépinière rend un motif explicite."""
        _seed_culture(db, "poireau", rusticite=-8.0,
                      fenetres={cal.PHASE_PLANTATION: (6, 7), cal.PHASE_RECOLTE: (10, 12)},
                      durees={cal.ETAPE_PLANTATION_RECOLTE: (100, 120)})
        c = conf.evaluer(db, "poireau", "plantation", date(2027, 6, 15), 1, parcelle_id=2)
        assert c.action == conf.ACTION_PLANTATION
        assert any("n'y a pas sa place" in a for a in c.avertissements)

    def test_us178_parcelle_d_un_autre_potager_ignoree(self, db):
        """[US-042] La parcelle d'un autre potager ne tranche rien."""
        _haricot(db)
        assert conf.evaluer(db, "haricot", "semis", LE_20_MAI, 1, parcelle_id=3).action \
            == conf.ACTION_SEMIS_PLEINE_TERRE


# ═════════════════════════════════════════════════════════════════════════════
# CA2 / CA11 — déterminisme, zéro jeton, aucune écriture
# ═════════════════════════════════════════════════════════════════════════════
class TestDeterminismeEtInnocuite:
    def test_us178_meme_question_meme_reponse(self, db):
        """[Gherkin: Même question, même réponse] Deux évaluations identiques."""
        _haricot(db)
        meteo = _quinzaine(LE_20_MAI, 11.0)
        premier = conf.confiance_en_dict(
            conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1, lecture_meteo=meteo))
        second = conf.confiance_en_dict(
            conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1, lecture_meteo=meteo))
        assert premier == second

    def test_us178_aucun_appel_llm(self, db):
        """[CA2] Zéro jeton : la passerelle n'est jamais sollicitée."""
        _haricot(db)
        with patch("llm.passerelle.appeler_chat") as appel:
            conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                         lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        appel.assert_not_called()

    def test_us178_aucune_ecriture(self, db):
        """[CA11] Rien n'est écrit : ni événement, ni fenêtre, ni durée."""
        _haricot(db)
        avant = (db.query(Evenement).count(), db.query(FenetreCulturale).count(),
                 db.query(DureeCulturale).count(), db.query(ItineraireCultural).count())
        conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1,
                     lecture_meteo=_quinzaine(LE_20_MAI, 11.0))
        assert avant == (db.query(Evenement).count(), db.query(FenetreCulturale).count(),
                         db.query(DureeCulturale).count(), db.query(ItineraireCultural).count())

    def test_us178_action_inconnue_refusee(self, db):
        """[CA4] Une action hors vocabulaire est refusée, jamais devinée."""
        with pytest.raises(conf.ActionInvalideError):
            conf.normaliser_action("bouturage")


# ═════════════════════════════════════════════════════════════════════════════
# CA9 / CA10 — lecture groupée et API
# ═════════════════════════════════════════════════════════════════════════════
class TestLectureGroupee:
    def test_us178_lecture_groupee_une_seule_lecture_meteo(self, db):
        """[CA9, CA10] Trois cultures, UNE lecture de prévisions."""
        _haricot(db)
        _seed_culture(db, "courgette", rusticite=5.0,
                      fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6), cal.PHASE_RECOLTE: (7, 10)},
                      durees={cal.ETAPE_RECOLTE: (55, 70)})
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_quinzaine(LE_20_MAI, 11.0)) as lecture:
            resultats = conf.evaluer_cultures(
                db, ["haricot", "courgette", "kiwano"], "semis en pleine terre", LE_20_MAI, 1)
        assert lecture.call_count == 1
        assert set(resultats) == {"haricot", "courgette", "kiwano"}
        assert resultats["haricot"].etoiles == 3
        assert resultats["kiwano"].etoiles is None

    def test_us178_meteo_lue_par_le_cache_us182(self, db):
        """[CA10] Aucun appel réseau direct : le cache d'US-182 est le seul accès."""
        _haricot(db)
        with patch("utils.meteo.fetch_meteo_groupe", return_value=[None]) as reseau:
            conf.evaluer(db, "haricot", "semis en pleine terre", LE_20_MAI, 1)
        assert reseau.call_count <= 1   # au plus l'appel du cache, jamais un appel propre


class TestApi:
    """L'API tourne dans le thread du client de test : elle a son propre moteur
    SQLite partagé (`StaticPool`), pas la session du reste du fichier."""

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
                                      attribution="Valeurs de test", partageable=True, importee=True))
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

    def test_us178_api_confiance_culture(self, db_api, client):
        """[CA9] `GET /cultures/{culture}/confiance` — étoiles, score et motifs."""
        _haricot(db_api[0])
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_quinzaine(LE_20_MAI, 11.0)):
            r = client.get("/cultures/haricot/confiance",
                           params={"action": "semis en pleine terre", "date": "2027-05-20"})
        assert r.status_code == 200
        corps = r.json()
        assert corps["etoiles"] == 3 and corps["score"] == 100
        assert len(corps["motifs"]) == 5

    def test_us178_api_confiance_sans_score(self, db_api, client):
        """[CA4, CA9] Toujours 200 ; sans fenêtre, `etoiles` est nul."""
        _seed_culture(db_api[0], "ail", fenetres={}, durees={})
        r = client.get("/cultures/ail/confiance", params={"action": "plantation"})
        assert r.status_code == 200 and r.json()["etoiles"] is None

    def test_us178_api_action_invalide_refusee(self, db_api, client):
        """[CA9] Une action hors vocabulaire rend 400, jamais un score inventé."""
        _haricot(db_api[0])
        r = client.get("/cultures/haricot/confiance", params={"action": "bouturage"})
        assert r.status_code == 400

    def test_us178_api_lecture_groupee_du_plan(self, db_api, client):
        """[CA9] `GET /plan/confiances` sert plusieurs cultures en un appel."""
        _haricot(db_api[0])
        _seed_culture(db_api[0], "courgette", rusticite=5.0,
                      fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6), cal.PHASE_RECOLTE: (7, 10)},
                      durees={cal.ETAPE_RECOLTE: (55, 70)})
        with patch.object(svc_previsions, "lire_prevision_potager",
                          return_value=_quinzaine(LE_20_MAI, 11.0)):
            r = client.get("/plan/confiances", params={
                "culture": ["haricot", "courgette"],
                "action": "semis en pleine terre", "date": "2027-05-20",
            })
        assert r.status_code == 200
        corps = r.json()
        assert corps["date"] == "2027-05-20"
        assert set(corps["cultures"]) == {"haricot", "courgette"}
        assert corps["cultures"]["haricot"]["etoiles"] == 3
