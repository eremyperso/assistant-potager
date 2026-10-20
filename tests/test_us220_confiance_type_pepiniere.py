"""
tests/test_us220_confiance_type_pepiniere.py — Le type de pépinière module la
confiance d'un semis en pépinière [US-220]
==============================================================================
Une pépinière chaude tient R2, R3 et R4 ; une pépinière froide (châssis) ne
tient que le gel annoncé ; un type non renseigné garde le comportement d'avant,
avec un avertissement. R1 et R5 ne bougent jamais, et un semis en pleine terre
ou une plantation ne sont pas touchés.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from app.bot import commandes_confiance as bot_conf
from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import echeances_lots as svc_echeances
from app.services import previsions_meteo as svc_previsions
from database.models import (
    CultureConfig, DureeCulturale, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)

RACINE = Path(__file__).resolve().parent.parent
LE_15_FEVRIER = date(2027, 2, 15)
EN_JUILLET = date(2027, 7, 15)
NUITS_A_1_DEGRE = 1.0
NUITS_DOUCES = 12.0

#: Identifiants des parcelles du jeu de test.
NORD, SERRE, CHASSIS, SANS_TYPE = 1, 2, 3, 4


def _pepiniere(pid: int, nom: str, type_p):
    return Parcelle(id=pid, nom=nom, nom_normalise=nom.replace(" ", ""), potager_id=1,
                    est_pepiniere=True, type_pepiniere=type_p)


def _jardin(test_db, *pepinieres: Parcelle):
    """Potager continental (dernière gelée moyenne le 25/04) et une tomate gélive."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="continental",
                        latitude=48.6, longitude=7.75))
    test_db.flush()
    test_db.add(Parcelle(id=NORD, nom="nord", nom_normalise="nord", potager_id=1))
    test_db.add_all(list(pepinieres))
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
        cal.PHASE_SEMIS_PEPINIERE: (2, 4), cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6),
        cal.PHASE_PLANTATION: (5, 6), cal.PHASE_RECOLTE: (7, 10),
    }.items():
        test_db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="continental",
                                     phase=phase, mois_debut=debut, mois_fin=fin, source_id=1))
    test_db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_RECOLTE,
                               jours_min=150, jours_max=170, source_id=1))
    test_db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_PLANTATION_RECOLTE,
                               jours_min=60, jours_max=80, source_id=1))
    test_db.commit()
    return test_db


@pytest.fixture
def chassis_seul(test_db):
    return _jardin(test_db, _pepiniere(CHASSIS, "châssis", "froide"))


@pytest.fixture
def serre_seule(test_db):
    return _jardin(test_db, _pepiniere(SERRE, "serre", "chaude"))


@pytest.fixture
def deux_pepinieres(test_db):
    return _jardin(test_db, _pepiniere(SERRE, "serre", "chaude"),
                   _pepiniere(CHASSIS, "châssis", "froide"))


@pytest.fixture
def sans_type(test_db):
    return _jardin(test_db, _pepiniere(SANS_TYPE, "pépinière", None))


@pytest.fixture
def sans_pepiniere(test_db):
    return _jardin(test_db)


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


@pytest.fixture
def meteo_fraiche(monkeypatch):
    """Des nuits à 1 °C la semaine du 15 février, lues par le cache (jamais le réseau)."""
    monkeypatch.setattr(conf, "_lire_meteo", lambda db, pid: _meteo(LE_15_FEVRIER, NUITS_A_1_DEGRE))


def _motif(c, regle):
    return next(m for m in c.motifs if m.regle == regle)


def _evaluer(db, action="semis_pepiniere", jour=LE_15_FEVRIER, parcelle_id=None, tmin=NUITS_A_1_DEGRE):
    return conf.evaluer(db, "tomate", action, jour, 1, parcelle_id=parcelle_id,
                        lecture_meteo=_meteo(jour, tmin))


# ── CA1 — la table, une seule fois, dans le Barème ───────────────────────────
class TestTable:
    def test_us220_ca1_table_ligne_par_ligne(self):
        R2, R3, R4 = conf.R2_DERNIERE_GELEE, conf.R3_GEL_ANNONCE, conf.R4_NUITS_DOUCES
        assert conf.REGLES_ACQUISES_PAR_TYPE_PEPINIERE == {
            "chaude": {R2, R3, R4},
            "froide": {R3},
            None: {R2, R3, R4},
        }
        assert conf.MOTIF_PEPINIERE_CHAUDE == "pépinière chauffée"
        assert conf.MOTIF_PEPINIERE_FROIDE == (
            "pépinière froide : à l'abri du gel annoncé, pas des nuits fraîches"
        )

    def test_us220_ca1_la_ligne_froide_est_celle_du_chassis(self):
        assert conf.REGLES_ACQUISES_PAR_TYPE_PEPINIERE["froide"] == conf.REGLES_ACQUISES_PAR_ABRI["chassis"]

    def test_us220_ca1_r1_et_r5_absentes_de_toute_ligne(self):
        for regles in conf.REGLES_ACQUISES_PAR_TYPE_PEPINIERE.values():
            assert conf.R1_FENETRE not in regles and conf.R5_SAISON_RESTANTE not in regles

    def test_us220_ca1_table_ecrite_une_seule_fois(self):
        sources = [p for p in (RACINE / "app").rglob("*.py")
                   if "REGLES_ACQUISES_PAR_TYPE_PEPINIERE" in p.read_text(encoding="utf-8")]
        assert [p.name for p in sources] == ["confiance_semis.py"]


# ── Gherkin + CA1 — les trois lignes ─────────────────────────────────────────
class TestTroisLignes:
    def test_us220_semer_des_tomates_au_chassis_froid_en_fevrier(self, chassis_seul):
        c = _evaluer(chassis_seul)
        r3 = _motif(c, conf.R3_GEL_ANNONCE)
        assert r3.etat == conf.ETAT_GAGNE and r3.points == r3.points_max
        assert "pépinière froide" in r3.libelle
        assert r3.libelle == f"Gel annoncé — {conf.MOTIF_PEPINIERE_FROIDE}"
        r4 = _motif(c, conf.R4_NUITS_DOUCES)
        assert r4.etat == conf.ETAT_PERDU and r4.libelle == "Nuits fraîches : levée lente probable"
        # La dernière gelée de la zone (25/04) est évaluée normalement : trop tôt.
        r2 = _motif(c, conf.R2_DERNIERE_GELEE)
        assert r2.etat == conf.ETAT_PERDU
        assert r2.libelle == "Trop tôt : gelées encore possibles dans ta zone"
        assert (c.score, c.etoiles) == (70, 2)

    def test_us220_la_serre_chauffee(self, serre_seule):
        c = _evaluer(serre_seule, parcelle_id=SERRE)
        for regle in (conf.R2_DERNIERE_GELEE, conf.R3_GEL_ANNONCE, conf.R4_NUITS_DOUCES):
            m = _motif(c, regle)
            assert m.etat == conf.ETAT_GAGNE and m.points == m.points_max
            assert m.libelle == f"{m.libelle_regle} — pépinière chauffée"
        assert (c.score, c.etoiles) == (100, 3)
        assert c.pepiniere.nom == "serre" and c.pepiniere.choisie is False
        assert conf.AVERTISSEMENT_TYPE_NON_RENSEIGNE not in c.avertissements

    def test_us220_type_non_renseigne_garde_le_niveau_d_aujourd_hui(self, sans_type):
        c = _evaluer(sans_type)
        assert (c.score, c.etoiles) == (100, 3)
        assert [_motif(c, r).libelle for r in (conf.R2_DERNIERE_GELEE, conf.R3_GEL_ANNONCE,
                                               conf.R4_NUITS_DOUCES)] == [
            "Semis en pépinière : gelée sans objet",
            "Semis en pépinière : gel annoncé sans objet",
            "Semis en pépinière : nuits sans objet",
        ]
        assert conf.AVERTISSEMENT_TYPE_NON_RENSEIGNE in c.avertissements
        assert "la confiance suppose une pépinière chauffée" in conf.AVERTISSEMENT_TYPE_NON_RENSEIGNE

    def test_us220_la_fenetre_ne_bouge_pas(self, serre_seule):
        c = _evaluer(serre_seule, jour=EN_JUILLET, parcelle_id=SERRE)
        assert _motif(c, conf.R1_FENETRE).etat == conf.ETAT_PERDU

    @pytest.mark.parametrize("fixture", ["chassis_seul", "serre_seule", "sans_type", "sans_pepiniere"])
    def test_us220_r1_et_r5_invariantes(self, request, fixture):
        db = request.getfixturevalue(fixture)
        reference = {"R1": ("gagne", 40, "Dans la fenêtre conseillée pour ta zone"),
                     "R5": ("gagne", 10, "La récolte tomberait dans la saison conseillée")}
        c = _evaluer(db)
        for regle, attendu in reference.items():
            m = _motif(c, regle)
            assert (m.etat, m.points, m.libelle) == attendu


# ── CA2 — quelle pépinière ───────────────────────────────────────────────────
class TestChoixDeLaPepiniere:
    def test_us220_ca2_sans_parcelle_la_meilleure_et_nommee(self, deux_pepinieres):
        c = _evaluer(deux_pepinieres)
        assert c.pepiniere.nom == "serre" and c.pepiniere.type == "chaude"
        assert c.pepiniere.choisie is True
        assert c.pepiniere.evaluation == "Évalué pour serre, pépinière chaude"

    def test_us220_ca2_parcelle_pepiniere_prend_son_type(self, deux_pepinieres):
        c = _evaluer(deux_pepinieres, parcelle_id=CHASSIS)
        assert c.pepiniere.nom == "châssis" and c.pepiniere.choisie is False
        assert c.etoiles == 2
        assert c.par_pepiniere == ()   # la parcelle est dite : une seule évaluation

    def test_us220_ca2_parcelle_ordinaire_vaut_sans_parcelle(self, chassis_seul):
        c = _evaluer(chassis_seul, parcelle_id=NORD)
        assert c.pepiniere.nom == "châssis" and c.pepiniere.choisie is True

    def test_us220_ca2_ordre_chaude_puis_non_renseigne_puis_froide(self):
        froide = Parcelle(id=1, nom="a", est_pepiniere=True, type_pepiniere="froide")
        aucun = Parcelle(id=2, nom="b", est_pepiniere=True, type_pepiniere=None)
        chaude = Parcelle(id=3, nom="c", est_pepiniere=True, type_pepiniere="chaude")
        assert conf.meilleure_pepiniere([froide, aucun, chaude]) is chaude
        assert conf.meilleure_pepiniere([froide, aucun]) is aucun
        assert conf.meilleure_pepiniere([froide]) is froide
        assert conf.meilleure_pepiniere([]) is None

    def test_us220_ca2_a_type_egal_la_plus_ancienne(self):
        a = Parcelle(id=7, nom="a", est_pepiniere=True, type_pepiniere="chaude")
        b = Parcelle(id=3, nom="b", est_pepiniere=True, type_pepiniere="chaude")
        assert conf.meilleure_pepiniere([a, b]) is b

    def test_us220_ca2_potager_sans_pepiniere(self, sans_pepiniere):
        c = _evaluer(sans_pepiniere)
        assert (c.score, c.etoiles) == (100, 3)
        assert c.pepiniere is None
        assert conf.AVERTISSEMENT_SANS_PEPINIERE in c.avertissements
        assert conf.AVERTISSEMENT_SANS_PEPINIERE.startswith("Aucune pépinière déclarée")

    def test_us220_ca2_une_pepiniere_d_un_autre_potager_ne_compte_pas(self, sans_pepiniere):
        db = sans_pepiniere
        db.add(User(id=2, email="b@potager.test"))
        db.flush()
        db.add(Potager(id=2, nom="Autre", proprietaire_id=2, zone_climatique="continental"))
        db.flush()
        db.add(Parcelle(id=9, nom="serre", nom_normalise="serre", potager_id=2,
                        est_pepiniere=True, type_pepiniere="froide"))
        db.commit()
        c = _evaluer(db)
        assert c.pepiniere is None and conf.AVERTISSEMENT_SANS_PEPINIERE in c.avertissements

    def test_us220_ca2_pepiniere_inactive_ignoree(self, chassis_seul):
        chassis_seul.get(Parcelle, CHASSIS).actif = False
        chassis_seul.commit()
        c = _evaluer(chassis_seul)
        assert c.pepiniere is None and c.etoiles == 3


# ── CA3 — deux types : une évaluation chacun ─────────────────────────────────
class TestDeuxTypes:
    def test_us220_ca3_une_evaluation_par_type(self, deux_pepinieres):
        c = _evaluer(deux_pepinieres)
        assert [(v.pepiniere.type, v.etoiles) for v in c.par_pepiniere] == [("chaude", 3), ("froide", 2)]
        assert c.etoiles == c.par_pepiniere[0].etoiles   # la principale est la meilleure

    def test_us220_ca3_un_seul_type_une_seule_evaluation(self, chassis_seul):
        assert _evaluer(chassis_seul).par_pepiniere == ()

    def test_us220_ca3_chaude_et_non_renseigne_disent_la_meme_chose(self):
        chaude = Parcelle(id=1, nom="a", est_pepiniere=True, type_pepiniere="chaude")
        aucun = Parcelle(id=2, nom="b", est_pepiniere=True, type_pepiniere=None)
        froide = Parcelle(id=3, nom="c", est_pepiniere=True, type_pepiniere="froide")
        assert conf.representants_par_type([chaude, aucun]) == []
        assert conf.representants_par_type([aucun, froide]) == [aucun, froide]
        assert conf.representants_par_type([froide, aucun, chaude]) == [chaude, aucun, froide]

    def test_us220_ca3_forme_servie(self, deux_pepinieres):
        d = conf.confiance_en_dict(_evaluer(deux_pepinieres))
        assert d["pepiniere"] == {"id": SERRE, "nom": "serre", "type": "chaude",
                                  "libelle": "pépinière chaude", "choisie": True,
                                  "evaluation": "Évalué pour serre, pépinière chaude"}
        assert [(n["pepiniere"]["libelle"], n["affichage"]) for n in d["par_pepiniere"]] == [
            ("pépinière chaude", "★★★"), ("pépinière froide", "★★"),
        ]

    def test_us220_ca3_deux_pepinieres_la_carte_a_semer(self, deux_pepinieres, meteo_fraiche):
        a_semer = svc_echeances._cultures_a_semer(deux_pepinieres, 1, LE_15_FEVRIER, set())
        tomate = next(c for c in a_semer if c["culture"] == "tomate")
        par_type = tomate["confiance"]["par_pepiniere"]
        assert [n["pepiniere"]["type"] for n in par_type] == ["chaude", "froide"]
        assert par_type[0]["etoiles"] > par_type[1]["etoiles"]


# ── CA5 — pleine terre et plantation intactes ────────────────────────────────
class TestPleineTerre:
    @pytest.mark.parametrize("action, jour", [("semis_pleine_terre", date(2027, 5, 20)),
                                              ("plantation", date(2027, 5, 20))])
    def test_us220_ca5_pas_de_modulation_par_la_pepiniere(self, deux_pepinieres, action, jour):
        c = _evaluer(deux_pepinieres, action=action, jour=jour, tmin=NUITS_DOUCES)
        assert c.pepiniere is None and c.par_pepiniere == ()
        assert not any("pépinière" in a for a in c.avertissements)
        assert not any("pépinière" in m.libelle for m in c.motifs)

    def test_us220_ca5_plantation_meme_score_avec_ou_sans_pepinieres(self, test_db):
        db = _jardin(test_db)
        jour = date(2027, 5, 20)
        avant = _evaluer(db, action="plantation", jour=jour, tmin=NUITS_DOUCES)
        db.add(_pepiniere(CHASSIS, "châssis", "froide"))
        db.commit()
        apres = _evaluer(db, action="plantation", jour=jour, tmin=NUITS_DOUCES)
        assert (avant.score, avant.motifs) == (apres.score, apres.motifs)


# ── US-181 — l'abri de la parcelle s'ajoute au type ──────────────────────────
def test_us220_l_abri_declare_l_emporte_sur_la_pepiniere_froide(test_db):
    chassis_sous_serre = _pepiniere(CHASSIS, "châssis", "froide")
    chassis_sous_serre.abri = "serre"
    db = _jardin(test_db, chassis_sous_serre)
    c = _evaluer(db, parcelle_id=CHASSIS)
    r4 = _motif(c, conf.R4_NUITS_DOUCES)
    assert r4.etat == conf.ETAT_GAGNE and "parcelle sous serre" in r4.libelle


# ── CA6 — le bot ─────────────────────────────────────────────────────────────
class TestBot:
    def test_us220_ca6_reponse_au_chassis_froid(self, chassis_seul):
        texte = bot_conf._formater_reponse(_evaluer(chassis_seul))
        assert "pépinière froide : à l'abri du gel annoncé, pas des nuits fraîches" in texte
        assert "Évalué pour châssis, pépinière froide" in texte
        assert "*★★*" in texte

    def test_us220_ca6_parcelle_dite_pas_de_ligne_evalue_pour(self, serre_seule):
        texte = bot_conf._formater_reponse(_evaluer(serre_seule, parcelle_id=SERRE), "serre")
        assert "Évalué pour" not in texte
        assert "pépinière chauffée" in texte

    def test_us220_ca6_deux_types_un_niveau_chacun(self, deux_pepinieres):
        texte = bot_conf._formater_reponse(_evaluer(deux_pepinieres))
        assert "pépinière chaude ★★★ · pépinière froide ★★" in texte

    def test_us220_ca6_avertissement_type_non_renseigne(self, sans_type):
        texte = bot_conf._formater_reponse(_evaluer(sans_type))
        assert "la confiance suppose une pépinière chauffée" in texte


# ── CA7 / CA11 — une même valeur partout ─────────────────────────────────────
def test_us220_ca7_bot_fiche_et_lecture_groupee_disent_pareil(deux_pepinieres, meteo_fraiche):
    db = deux_pepinieres
    bot = conf.evaluer(db, "tomate", "semis_pepiniere", LE_15_FEVRIER, 1)
    groupee = conf.evaluer_cultures(db, ["tomate"], "semis_pepiniere", LE_15_FEVRIER, 1)["tomate"]
    plan = conf.confiances_du_plan(db, ["tomate"], LE_15_FEVRIER, 1)["tomate"]
    fiche = next(c for c in plan.actions if c.action == conf.ACTION_SEMIS_PEPINIERE)
    a_semer = next(c for c in svc_echeances._cultures_a_semer(db, 1, LE_15_FEVRIER, set())
                   if c["culture"] == "tomate")["confiance"]
    valeurs = {(c.score, c.etoiles, tuple(v.etoiles for v in c.par_pepiniere))
               for c in (bot, groupee, fiche)}
    assert valeurs == {(100, 3, (3, 2))}
    assert (a_semer["score"], a_semer["etoiles"]) == (100, 3)
    assert [n["etoiles"] for n in a_semer["par_pepiniere"]] == [3, 2]


def test_us220_ca7_les_pepinieres_lues_une_fois_pour_l_ecran(deux_pepinieres, meteo_fraiche, monkeypatch):
    appels = []
    lire = conf._pepinieres
    monkeypatch.setattr(conf, "_pepinieres", lambda db, pid: appels.append(pid) or lire(db, pid))
    conf.confiances_du_plan(deux_pepinieres, ["tomate", "carotte", "haricot"], LE_15_FEVRIER, 1)
    assert appels == [1]


# ── CA4 / CA10 — gabarit et documentation ────────────────────────────────────
class TestDocumentation:
    def test_us220_ca4_motifs_au_gabarit_a_la_lettre(self):
        gabarit = (RACINE / "docs" / "EPIC 8-confiance-calendrier"
                   / "GABARIT_REPONSE_CONFIANCE_BOT.md").read_text(encoding="utf-8")
        for texte in (conf.MOTIF_PEPINIERE_FROIDE, conf.AVERTISSEMENT_TYPE_NON_RENSEIGNE,
                      conf.AVERTISSEMENT_SANS_PEPINIERE, "Gel annoncé — pépinière chauffée",
                      *conf.MOTIFS_SANS_OBJET_EN_PEPINIERE.values()):
            assert texte in gabarit, texte
        assert conf.MOTIF_EVALUE_POUR.split("{")[0] in gabarit

    def test_us220_ca10_fiche_de_domaine_porte_la_table(self):
        fiche = (RACINE / "docs" / "domaines" / "calendrier-cultural.md").read_text(encoding="utf-8")
        assert "attend l'abri d'US-181" not in fiche
        assert "REGLES_ACQUISES_PAR_TYPE_PEPINIERE" in fiche
        assert "| froide | évaluée | acquise | évaluée |" in fiche

    def test_us220_ca10_fiche_du_corpus_explique_le_type(self):
        fiche = (RACINE / "data" / "connaissance" / "doc_app"
                 / "calendrier-et-zone-climatique.md").read_text(encoding="utf-8")
        assert "## Pourquoi le type de pépinière change le niveau d'un semis à l'abri" in fiche
        assert "la confiance suppose une pépinière chauffée" in fiche
