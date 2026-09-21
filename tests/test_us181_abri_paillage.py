"""
tests/test_us181_abri_paillage.py — Abri et paillage d'une parcelle [US-181]

Critères couverts :
- CA1  vocabulaire fermé, NULL (jamais renseigné) distinct de « aucun »
- CA2  déclaration au bot (`update_parcelle`) et par dictée (grammaire déterministe),
       sans confondre « sous voile » avec la pose d'un voile datée
- CA4  les modulateurs, à un seul endroit du moteur (quatre combinaisons)
- CA5  le motif dit que la parcelle a compté
- CA6  un abri ne déplace pas la fenêtre conseillée (R1)
- CA7  colonnes nullables, migration et rollback fournis
- CA8  aucune autre règle que R2/R3/R4 n'est touchée

⚠️ CA3 (édition depuis l'écran de paramètres de la PWA) est REPORTÉ, à la demande
du jardinier : aucun endpoint d'édition de parcelle n'existe. Seule la LECTURE est
exposée (`GET /plan`, `POST /parcelles`) et n'est pas couverte ici.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import interpreteur_commandes as interp
from app.services import previsions_meteo as svc_previsions
from database.models import (
    CultureConfig, DureeCulturale, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)
from utils.parcelles import normaliser_abri, update_parcelle

RACINE = Path(__file__).resolve().parent.parent
LE_20_AVRIL = date(2027, 4, 20)
#: Assez tôt pour que la dernière gelée moyenne de la zone ne soit pas passée.
TOT_EN_SAISON = date(2027, 3, 10)


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique",
                        latitude=47.2, longitude=-1.55))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, abri="serre"),
        Parcelle(id=3, nom="voile", nom_normalise="voile", potager_id=1, abri="voile"),
        Parcelle(id=4, nom="tunnel", nom_normalise="tunnel", potager_id=1, abri="tunnel"),
        Parcelle(id=5, nom="chassis", nom_normalise="chassis", potager_id=1, abri="chassis"),
        Parcelle(id=6, nom="paillee", nom_normalise="paillee", potager_id=1, paillage=True),
        Parcelle(id=7, nom="sans", nom_normalise="sans", potager_id=1, abri="aucun", paillage=False),
        Parcelle(id=8, nom="serre paillee", nom_normalise="serrepaillee", potager_id=1,
                 abri="serre", paillage=True),
    ])
    test_db.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0",
                                  attribution="Valeurs de test", partageable=True, importee=True))
    fiche = CultureConfig(nom="tomate", type_organe_recolte="fruit", rusticite_min_c=5.0)
    test_db.add(fiche)
    test_db.flush()
    it = ItineraireCultural(culture_id=fiche.id, nom="standard",
                            nom_normalise=cal.normaliser_itineraire("standard"),
                            potager_id=None, source_id=1)
    test_db.add(it)
    test_db.flush()
    for phase, (debut, fin) in {
        cal.PHASE_SEMIS_PEPINIERE: (2, 4), cal.PHASE_PLANTATION: (5, 6),
        cal.PHASE_RECOLTE: (7, 10),
    }.items():
        test_db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="oceanique",
                                     phase=phase, mois_debut=debut, mois_fin=fin, source_id=1))
    test_db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_PLANTATION_RECOLTE,
                               jours_min=60, jours_max=80, source_id=1))
    test_db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_RECOLTE,
                               jours_min=90, jours_max=120, source_id=1))
    test_db.commit()
    return test_db


def _meteo(depart: date, tmin: float, jours: int = 14):
    return svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_DISPONIBLE,
        meteo={"previsions_etendues": [
            {"date": (depart + timedelta(days=i)).isoformat(), "temp_min": tmin,
             "temp_max": tmin + 10, "horizon_jours": i + 1}
            for i in range(jours)
        ]},
        source=svc_previsions.SOURCE_CACHE,
    )


def _motif(c, regle):
    return next(m for m in c.motifs if m.regle == regle)


def _evaluer(db, parcelle_id, action="plantation", jour=LE_20_AVRIL, tmin=-2.0):
    return conf.evaluer(db, "tomate", action, jour, 1, parcelle_id=parcelle_id,
                        lecture_meteo=_meteo(jour, tmin))


# ── CA1 / CA2 — déclaration au bot ───────────────────────────────────────────
class TestDeclaration:
    def test_us181_ca1_vocabulaire_ferme(self):
        assert normaliser_abri("Châssis") == "chassis"
        assert normaliser_abri("sans") == "aucun"
        with pytest.raises(ValueError):
            normaliser_abri("pergola")

    def test_us181_ca1_jamais_renseigne_distinct_de_aucun(self, db):
        assert db.get(Parcelle, 1).abri is None and db.get(Parcelle, 1).paillage is None
        update_parcelle(db, "nord", potager_id=1, abri="aucun", paillage="non")
        p = db.get(Parcelle, 1)
        assert p.abri == "aucun" and p.paillage is False

    def test_us181_ca2_commande_parcelle_modifier(self, db):
        _, modifs = update_parcelle(db, "nord", potager_id=1, abri="serre", paillage="oui")
        p = db.get(Parcelle, 1)
        assert (p.abri, p.paillage) == ("serre", True)
        assert "Abri : serre" in modifs and "Paillage : oui" in modifs

    def test_us181_ca2_valeur_hors_vocabulaire_refusee_sans_ecriture(self, db):
        with pytest.raises(ValueError):
            update_parcelle(db, "nord", potager_id=1, abri="pergola")
        with pytest.raises(ValueError):
            update_parcelle(db, "nord", potager_id=1, paillage="peut-etre")
        assert db.get(Parcelle, 1).abri is None

    def test_us181_ca7_est_pepiniere_pas_reinterprete(self, db):
        update_parcelle(db, "nord", potager_id=1, abri="serre")
        assert db.get(Parcelle, 1).est_pepiniere is False


# ── CA2 — déclaration par dictée ─────────────────────────────────────────────
class TestDictee:
    @pytest.mark.parametrize("phrase,nom,modification", [
        ("la parcelle 2 est sous serre", "2", "abri=serre"),
        ("le rang 3 est sous voile", "rang 3", "abri=voile"),
        ("la parcelle nord est sous châssis", "nord", "abri=chassis"),
        ("la parcelle 2 est sous un tunnel", "2", "abri=tunnel"),
        ("mets la parcelle nord sous tunnel", "nord", "abri=tunnel"),
        ("la parcelle 2 est sans abri", "2", "abri=aucun"),
        ("rang 3 paillé", "rang 3", "paillage=oui"),
        ("la parcelle 2 n'est pas paillée", "2", "paillage=non"),
    ])
    def test_us181_ca2_declaration_reconnue_sans_modele(self, phrase, nom, modification):
        r = interp.interpreter(phrase, autoriser_modele=False)
        assert r is not None and (r.commande, r.sous_commande) == ("parcelle", "modifier")
        assert r.valeurs == {"nom": nom, "modification": modification}
        assert r.origine == interp.ORIGINE_REGLE  # aucun jeton consommé

    @pytest.mark.parametrize("phrase", [
        "j'ai mis un voile sur le rang 3 hier",
        "est-ce que la parcelle 2 est sous serre ?",
        "est-ce que la parcelle 2 est paillée",
    ])
    def test_us181_ca2_pose_datee_et_question_ne_declarent_rien(self, phrase):
        r = interp.interpreter(phrase, autoriser_modele=False)
        assert r is None or r.valeurs.get("modification", "").split("=")[0] not in ("abri", "paillage")


# ── CA4 / CA5 / CA6 — le moteur ──────────────────────────────────────────────
class TestModulateurs:
    def test_us181_ca4_serre_neutralise_gel_annonce_meme_en_pepiniere(self, db):
        c = _evaluer(db, 2, action="semis en pépinière", jour=date(2027, 3, 10))
        m = _motif(c, conf.R3_GEL_ANNONCE)
        assert m.etat == conf.ETAT_GAGNE and m.points == m.points_max
        assert "parcelle sous serre" in m.libelle

    def test_us181_ca4_serre_et_tunnel_levent_r2_r3_r4(self, db):
        for pid in (2, 4):
            c = _evaluer(db, pid)
            for regle in (conf.R2_DERNIERE_GELEE, conf.R3_GEL_ANNONCE, conf.R4_NUITS_DOUCES):
                assert _motif(c, regle).etat == conf.ETAT_GAGNE
                assert "règle sans objet" in _motif(c, regle).libelle

    def test_us181_ca4_voile_ne_leve_pas_la_derniere_gelee(self, db):
        c = _evaluer(db, 3, jour=TOT_EN_SAISON)
        assert _motif(c, conf.R2_DERNIERE_GELEE).etat == conf.ETAT_PERDU
        assert _motif(c, conf.R3_GEL_ANNONCE).etat == conf.ETAT_GAGNE
        assert "parcelle sous voile" in _motif(c, conf.R3_GEL_ANNONCE).libelle
        assert _motif(c, conf.R4_NUITS_DOUCES).etat == conf.ETAT_PERDU  # R4 inchangée

    def test_us181_ca4_chassis_leve_r3_seulement(self, db):
        c = _evaluer(db, 5, jour=TOT_EN_SAISON)
        assert _motif(c, conf.R3_GEL_ANNONCE).etat == conf.ETAT_GAGNE
        assert _motif(c, conf.R2_DERNIERE_GELEE).etat == conf.ETAT_PERDU
        assert _motif(c, conf.R4_NUITS_DOUCES).etat == conf.ETAT_PERDU

    def test_us181_ca4_paillage_leve_r4_seulement(self, db):
        c = _evaluer(db, 6, tmin=-2.0)
        assert _motif(c, conf.R4_NUITS_DOUCES).etat == conf.ETAT_GAGNE
        assert "parcelle paillée" in _motif(c, conf.R4_NUITS_DOUCES).libelle
        assert _motif(c, conf.R3_GEL_ANNONCE).etat == conf.ETAT_PERDU  # évaluée normalement

    def test_us181_ca4_abri_prime_sur_paillage_pour_le_motif(self, db):
        m = _motif(_evaluer(db, 8, tmin=5.0), conf.R4_NUITS_DOUCES)
        assert "sous serre" in m.libelle and "paillée" not in m.libelle

    def test_us181_ca5_motif_dit_que_l_abri_a_compte(self, db):
        m = _motif(_evaluer(db, 2), conf.R3_GEL_ANNONCE)
        assert m.libelle.endswith("parcelle sous serre, règle sans objet")
        assert "Gel annoncé le" in m.libelle  # la raison d'origine reste lisible

    def test_us181_ca6_un_abri_ne_deplace_pas_la_fenetre(self, db):
        c = _evaluer(db, 2, jour=date(2027, 1, 15))
        assert _motif(c, conf.R1_FENETRE).etat == conf.ETAT_PERDU

    @pytest.mark.parametrize("parcelle_id", [None, 1, 7])
    def test_us181_ca4_non_renseigne_et_aucun_ne_modifient_rien(self, db, parcelle_id):
        c = _evaluer(db, parcelle_id)
        assert all("sans objet" not in m.libelle for m in c.motifs)
        assert _motif(c, conf.R3_GEL_ANNONCE).etat == conf.ETAT_PERDU

    def test_us181_ca8_r1_et_r5_jamais_modulees(self, db):
        avec = _evaluer(db, 2)
        sans = _evaluer(db, 1)
        for regle in (conf.R1_FENETRE, conf.R5_SAISON_RESTANTE):
            assert _motif(avec, regle) == _motif(sans, regle)

    def test_us181_ca4_la_table_de_modulation_tient_en_un_endroit(self):
        assert conf.REGLES_ACQUISES_PAR_ABRI["voile"] == {conf.R3_GEL_ANNONCE}
        assert conf.REGLES_ACQUISES_PAR_PAILLAGE == {conf.R4_NUITS_DOUCES}


# ── CA7 — migration ──────────────────────────────────────────────────────────
def test_us181_ca7_migration_nullable_sans_backfill_et_rollback():
    up = (RACINE / "migrations" / "migration_v49.sql").read_text(encoding="utf-8")
    down = (RACINE / "migrations" / "rollback_v49.sql").read_text(encoding="utf-8")
    assert "abri" in up and "paillage" in up
    assert "NOT NULL" not in up and "\nUPDATE " not in up.upper()
    assert "DROP COLUMN IF EXISTS abri" in down and "DROP COLUMN IF EXISTS paillage" in down
