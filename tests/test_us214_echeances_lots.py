"""
tests/test_us214_echeances_lots.py — Échéances d'un lot de pépinière [US-214]
==============================================================================

La Pépinière dit, lot par lot, ce qu'il y a à faire aujourd'hui. Cette suite
couvre les treize critères d'acceptance :

- CA1  un seul module, lecture seule ; durée d'endurcissement et seuil de dormance
       figés comme décisions produit
- CA2  une fourchette reste une fourchette ; le retard se compte depuis sa fin
- CA3  sans la donnée requise, pas d'échéance — et la raison est rendue
- CA4  endurcissement : chaude / inconnue → compte à rebours, froide → sur place,
       déplacé vers le froid → compte à rebours depuis le déplacement, borné à J+7
- CA5  la dormance et son exclusion
- CA6  l'ordre d'urgence
- CA7  GET /pepiniere/lots ajoute, sans rien retirer
- CA8  le résumé du bandeau
- CA9  une lecture, une météo au plus, aucune requête par lot
- CA10 lecture seule
- CA11 fiche de domaine `docs/domaines/pepiniere.md` dans la table du README
- CA12 fiche `pepiniere-par-lot.md` mise à jour pour le jardinier
- CA13 ce fichier

Les durées écrites ici sont des VALEURS DE TEST : elles n'engagent aucune agronomie.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import echeances_lots as ech
from app.services import previsions_meteo as svc_previsions
from app.services.context import TenantContext
from database.db import Base
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)
from utils.stock import calcul_lots_pepiniere

RACINE = Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")

LE_19_SEPT = date(2026, 9, 19)


# ═════════════════════════════════════════════════════════════════════════════
# Décor
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Deux potagers ; une planche, une serre chaude, un châssis froid, une pépinière sans type."""
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"),
        Potager(id=2, nom="Jardin B", proprietaire_id=2, zone_climatique="oceanique"),
    ])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="Planche nord", nom_normalise="planchenord", potager_id=1, nb_rangs=4),
        Parcelle(id=2, nom="Serre", nom_normalise="serre", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude"),
        Parcelle(id=3, nom="Châssis froid", nom_normalise="chassisfroid", potager_id=1,
                 est_pepiniere=True, type_pepiniere="froide"),
        Parcelle(id=4, nom="Véranda", nom_normalise="veranda", potager_id=1, est_pepiniere=True),
        Parcelle(id=5, nom="Serre B", nom_normalise="serreb", potager_id=2,
                 est_pepiniere=True, type_pepiniere="chaude"),
    ])
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


def _referentiel(db, nom, *, godet=None, terre=None, fenetre=None, itineraire_potager=None, culture_id=None):
    """Une culture, son itinéraire « standard », ses délais et sa fenêtre de semis en pépinière.

    `godet` / `terre` : (jours_min, jours_max). `fenetre` : (mois_debut, mois_fin).
    `itineraire_potager` : l'itinéraire est une correction locale de ce potager.
    """
    if culture_id is None:
        fiche = CultureConfig(nom=nom, type_organe_recolte="fruit")
        db.add(fiche)
        db.flush()
        culture_id = fiche.id
    it = ItineraireCultural(
        culture_id=culture_id, nom="standard", nom_normalise="standard",
        potager_id=itineraire_potager, source_id=1,
    )
    db.add(it)
    db.flush()
    if fenetre:
        db.add(FenetreCulturale(
            itineraire_id=it.id, zone_climatique="oceanique", phase=cal.PHASE_SEMIS_PEPINIERE,
            mois_debut=fenetre[0], mois_fin=fenetre[1], potager_id=itineraire_potager, source_id=1,
        ))
    for etape, bornes in ((cal.ETAPE_SEMIS_GODET, godet), (cal.ETAPE_REPIQUAGE, terre)):
        if bornes:
            db.add(DureeCulturale(
                itineraire_id=it.id, etape=etape, jours_min=bornes[0], jours_max=bornes[1],
                potager_id=itineraire_potager, source_id=1,
            ))
    db.commit()
    return culture_id


def _semis(db, culture, jour: date, *, graines=48, parcelle_id=2, numero=None, potager_id=1):
    e = Evenement(
        type_action="semis", culture=culture, quantite=graines, unite="graines",
        date=datetime(jour.year, jour.month, jour.day), parcelle_id=parcelle_id,
        potager_id=potager_id, numero_lot=numero,
    )
    db.add(e)
    db.commit()
    return e


def _godets(db, semis, jour: date, plants, *, parcelle_id=None):
    e = Evenement(
        type_action="mise_en_godet", culture=semis.culture, nb_plants_godets=plants,
        nb_graines_semees=plants, origine_graines_id=semis.id, parcelle_id=parcelle_id,
        date=datetime(jour.year, jour.month, jour.day), potager_id=semis.potager_id,
    )
    db.add(e)
    db.commit()
    return e


def _deplacer(db, semis, jour: date, parcelle_id):
    e = Evenement(
        type_action="deplacement", culture=semis.culture, origine_graines_id=semis.id,
        parcelle_id=parcelle_id, date=datetime(jour.year, jour.month, jour.day),
        potager_id=semis.potager_id,
    )
    db.add(e)
    db.commit()
    return e


def _lire(db, ref=LE_19_SEPT, ctx=CTX):
    lots = calcul_lots_pepiniere(db, ref, potager_id=ctx.potager_id)
    return ech.lire_echeances(db, ctx, lots, ref)


def _du_lot(lecture, semis):
    return lecture["par_lot"][f"semis-{semis.id}"]


@pytest.fixture(autouse=True)
def _meteo_sans_reseau(monkeypatch):
    """Aucune prévision réelle : la lecture météo est comptée et rendue « indisponible »."""
    appels = []

    def _lecture(db, potager_id):
        appels.append(potager_id)
        return svc_previsions.LecturePrevision(statut=svc_previsions.STATUT_LOCALISATION_MANQUANTE)

    monkeypatch.setattr(conf, "_lire_meteo", _lecture)
    return appels


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — un seul module, deux décisions produit figées
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Decisions:

    def test_us214_ca1_les_deux_decisions_produit_sont_figees(self):
        """Un changement involontaire de l'une des deux casse ce test, pas la Pépinière."""
        assert ech.DUREE_ENDURCISSEMENT_JOURS == 7
        assert ech.SEUIL_DORMANCE_JOURS == 60

    def test_us214_ca1_l_endurcissement_suit_la_decision_produit(self, db, monkeypatch):
        """La durée n'est écrite qu'à un endroit : la changer déplace le compte à rebours."""
        _referentiel(db, "poireau", terre=(42, 56))
        s = _semis(db, "poireau", date(2026, 8, 15))
        _godets(db, s, date(2026, 9, 1), 20, parcelle_id=2)
        monkeypatch.setattr(ech, "DUREE_ENDURCISSEMENT_JOURS", 10)
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert (e["jour"], e["sur"]) == (6, 10)    # début de la mise en terre le 26, moins 10 j

    def test_us214_ca1_aucun_calcul_hors_du_module_de_service(self):
        """Ni l'API ni le stock ne portent la règle : ils la recopient."""
        for chemin in ("app/api/main.py", "utils/stock.py"):
            source = (RACINE / chemin).read_text(encoding="utf-8")
            assert "DUREE_ENDURCISSEMENT_JOURS" not in source and "SEUIL_DORMANCE_JOURS" not in source


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — repiquage : la fourchette reste une fourchette
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Repiquage:

    def test_us214_ca2_gherkin_lot_en_retard_de_repiquage(self, db):
        _referentiel(db, "chou frisé", godet=(10, 12))
        s = _semis(db, "chou frisé", date(2026, 9, 1), numero=128)
        lot = _du_lot(_lire(db), s)
        r = lot["echeances"]["repiquage"]
        assert r["etat"] == ech.ETAT_EN_RETARD and r["retard_jours"] == 6
        assert lot["action_suggeree"] == {"code": "repiquer", "libelle": "Repiquer"}

    def test_us214_ca2_la_fourchette_est_rendue_telle_quelle(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 9, 1))
        r = _du_lot(_lire(db), s)["echeances"]["repiquage"]
        assert (r["du"], r["au"]) == ("2026-09-11", "2026-09-13")
        assert r["periode"] == "entre le 11 sept. et le 13 sept."

    def test_us214_ca2_une_valeur_unique_n_est_pas_une_fourchette_inventee(self, db):
        _referentiel(db, "chou", godet=(10, 10))
        s = _semis(db, "chou", date(2026, 9, 1))
        r = _du_lot(_lire(db), s)["echeances"]["repiquage"]
        assert r["du"] == r["au"] == "2026-09-11" and r["periode"] == "le 11 sept."

    @pytest.mark.parametrize("ref, etat, dans, retard", [
        (date(2026, 9, 5), ech.ETAT_A_VENIR, 6, None),        # avant la fourchette
        (date(2026, 9, 11), ech.ETAT_A_REPIQUER, 0, None),    # premier jour
        (date(2026, 9, 13), ech.ETAT_A_REPIQUER, 0, None),    # dernier jour : pas encore en retard
        (date(2026, 9, 14), ech.ETAT_EN_RETARD, None, 1),     # le retard part de la FIN
    ])
    def test_us214_ca2_les_bornes_de_la_fourchette(self, db, ref, etat, dans, retard):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 9, 1))
        r = _du_lot(_lire(db, ref), s)["echeances"]["repiquage"]
        assert r["etat"] == etat and r["dans_jours"] == dans and r["retard_jours"] == retard

    def test_us214_ca2_plus_d_echeance_de_repiquage_des_qu_un_plant_est_en_godet(self, db):
        _referentiel(db, "chou", godet=(10, 12), terre=(42, 56))
        s = _semis(db, "chou", date(2026, 9, 1))
        _godets(db, s, date(2026, 9, 12), 20, parcelle_id=2)
        r = _du_lot(_lire(db), s)["echeances"]["repiquage"]
        assert r["etat"] is None and r["raison"] is None

    def test_us214_ca2_la_date_de_reference_passee_reconstitue_l_echeance(self, db):
        """Au 5 septembre, le repiquage n'était pas encore attendu ; un geste du 12 n'existe pas."""
        _referentiel(db, "chou", godet=(10, 12), terre=(42, 56))
        s = _semis(db, "chou", date(2026, 9, 1))
        _godets(db, s, date(2026, 9, 12), 20, parcelle_id=2)
        passe = _du_lot(_lire(db, date(2026, 9, 5)), s)["echeances"]["repiquage"]
        assert passe["etat"] == ech.ETAT_A_VENIR and passe["dans_jours"] == 6


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — sans la donnée, pas d'échéance, et la raison
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3SansDonnee:

    def test_us214_ca3_gherkin_delai_inconnu(self, db):
        _referentiel(db, "tomate cerise", terre=(42, 56))      # pas de délai semis → godet
        s = _semis(db, "tomate cerise", date(2026, 9, 10), numero=131)
        lot = _du_lot(_lire(db), s)
        r = lot["echeances"]["repiquage"]
        assert r["etat"] is None and r["du"] is None
        assert r["raison"] == "délai semis → godet non renseigné pour la culture « tomate cerise »"
        assert r["raison"] in lot["echeances"]["raisons"]
        assert lot["action_suggeree"] is None

    def test_us214_ca3_aucune_valeur_par_defaut_n_est_fabriquee(self, db):
        """Ni la levée ni le délai avant plantation ne servent de délai de godet."""
        _referentiel(db, "poireau", terre=(42, 56))
        s = _semis(db, "poireau", date(2026, 7, 1))
        r = _du_lot(_lire(db), s)["echeances"]["repiquage"]
        assert r["etat"] is None and r["retard_jours"] is None

    def test_us214_ca3_culture_inconnue_du_referentiel(self, db):
        s = _semis(db, "cardon", date(2026, 9, 10))
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["repiquage"]["etat"] is None
        assert "cardon" in lot["echeances"]["repiquage"]["raison"]

    def test_us214_ca3_une_mention_libre_n_est_pas_une_duree(self, db):
        fiche = _referentiel(db, "ail")
        it = db.query(ItineraireCultural).filter_by(culture_id=fiche).first()
        db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_SEMIS_GODET,
                              mention="vivace", source_id=1))
        db.commit()
        s = _semis(db, "ail", date(2026, 9, 1))
        assert _du_lot(_lire(db), s)["echeances"]["repiquage"]["etat"] is None

    def test_us214_ca3_pas_de_mise_en_terre_sans_delai_avant_plantation(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 9, 1))
        _godets(db, s, date(2026, 9, 12), 20, parcelle_id=2)
        e = _du_lot(_lire(db), s)["echeances"]
        assert e["mise_en_terre"]["etat"] is None
        assert e["mise_en_terre"]["raison"] == "délai avant plantation non renseigné pour la culture « chou »"
        assert e["endurcissement"]["etat"] is None
        assert e["endurcissement"]["raison"] == e["mise_en_terre"]["raison"]

    def test_us214_ca3_lot_sans_semis_rattache_sans_echeance_de_semis(self, db):
        """Des godets arrivés sans semis : aucune date de semis, aucune échéance fabriquée."""
        _referentiel(db, "poireau", godet=(10, 12), terre=(42, 56))
        db.add(Evenement(type_action="mise_en_godet", culture="poireau", nb_plants_godets=10,
                         date=datetime(2026, 9, 1), potager_id=1, parcelle_id=2))
        db.commit()
        lecture = _lire(db)
        (lot,) = lecture["par_lot"].values()
        assert lot["echeances"]["mise_en_terre"]["etat"] is None
        assert lot["echeances"]["raisons"] == ["date de semis inconnue"]
        assert lot["action_suggeree"] is None

    def test_us214_ca3_un_lot_recent_sans_echeance_n_est_ni_en_retard_ni_dormant(self, db):
        s = _semis(db, "cardon", date(2026, 9, 10))
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["dormance"]["est_dormant"] is False
        assert lot["echeances"]["repiquage"]["retard_jours"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Mise en terre prévue
# ═════════════════════════════════════════════════════════════════════════════
class TestMiseEnTerre:

    @pytest.mark.parametrize("ref, etat", [
        (date(2026, 10, 1), ech.ETAT_A_VENIR),     # semis + 42 = 12 octobre
        (date(2026, 10, 12), ech.ETAT_ATTEINTE),
        (date(2026, 10, 26), ech.ETAT_ATTEINTE),   # semis + 56 = 26 octobre
        (date(2026, 10, 27), ech.ETAT_DEPASSEE),
    ])
    def test_us214_mise_en_terre_est_une_fourchette(self, db, ref, etat):
        _referentiel(db, "chou", terre=(42, 56))
        s = _semis(db, "chou", date(2026, 8, 31))
        _godets(db, s, date(2026, 9, 10), 20, parcelle_id=2)
        m = _du_lot(_lire(db, ref), s)["echeances"]["mise_en_terre"]
        assert m["etat"] == etat and (m["du"], m["au"]) == ("2026-10-12", "2026-10-26")

    def test_us214_mise_en_terre_depassee_se_compte_depuis_la_fin(self, db):
        _referentiel(db, "chou", terre=(42, 56))
        s = _semis(db, "chou", date(2026, 8, 31))
        _godets(db, s, date(2026, 10, 20), 20, parcelle_id=2)        # geste récent : pas dormant
        m = _du_lot(_lire(db, date(2026, 10, 30)), s)["echeances"]["mise_en_terre"]
        assert m["retard_jours"] == 4

    def test_us214_mise_en_terre_n_existe_que_pour_un_lot_avec_des_godets(self, db):
        _referentiel(db, "chou", godet=(10, 12), terre=(42, 56))
        s = _semis(db, "chou", date(2026, 9, 1))
        m = _du_lot(_lire(db), s)["echeances"]["mise_en_terre"]
        assert m["etat"] is None and m["raison"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — endurcissement : chaude, inconnue, froide, déplacé vers le froid
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Endurcissement:

    def _poireaux(self, db, *, parcelle_id=2):
        """Mise en terre prévue du 26 septembre au 10 octobre (semis du 15 août, 42-56 j)."""
        _referentiel(db, "poireau", terre=(42, 56))
        s = _semis(db, "poireau", date(2026, 8, 15), parcelle_id=parcelle_id, numero=119)
        _godets(db, s, date(2026, 9, 5), 20, parcelle_id=parcelle_id)
        return s

    def test_us214_ca4_gherkin_endurcissement_en_pepiniere_chaude(self, db):
        s = self._poireaux(db)
        lot = _du_lot(_lire(db, date(2026, 9, 22)), s)
        e = lot["echeances"]["endurcissement"]
        assert (e["etat"], e["jour"], e["sur"]) == (ech.ETAT_EN_COURS, 3, 7)
        assert e["libelle"] == "Endurcissement J+3/7" and e["depuis"] == "2026-09-19"
        assert lot["action_suggeree"]["code"] == "mettre_en_terre"

    def test_us214_ca4_type_inconnu_compte_comme_chaude(self, db):
        s = self._poireaux(db, parcelle_id=4)                         # Véranda : sans type
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert (e["etat"], e["jour"]) == (ech.ETAT_EN_COURS, 3)

    def test_us214_ca4_pas_encore_commence(self, db):
        s = self._poireaux(db)
        e = _du_lot(_lire(db, date(2026, 9, 15)), s)["echeances"]["endurcissement"]
        assert e["etat"] == ech.ETAT_PAS_COMMENCE and e["dans_jours"] == 4 and e["jour"] is None

    @pytest.mark.parametrize("ref, jour", [
        (date(2026, 9, 19), 0), (date(2026, 9, 25), 6), (date(2026, 9, 26), 7),
        (date(2026, 10, 8), 7),                     # bien après : le compteur reste à J+7
    ])
    def test_us214_ca4_le_compte_a_rebours_ne_depasse_jamais_sept(self, db, ref, jour):
        s = self._poireaux(db)
        e = _du_lot(_lire(db, ref), s)["echeances"]["endurcissement"]
        assert e["jour"] == jour and e["sur"] == 7
        assert e["termine"] is (jour == 7)

    def test_us214_ca4_gherkin_pepiniere_froide_deplace(self, db):
        """Déplacé au châssis froid le 10 septembre, lu le 22 : les 7 jours sont écoulés,
        le lot est « en pépinière froide », sans compte à rebours."""
        s = self._poireaux(db)
        _deplacer(db, s, date(2026, 9, 10), parcelle_id=3)
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert e["etat"] == ech.ETAT_FROIDE and e["libelle"] == "en pépinière froide"
        assert e["jour"] is None and e["sur"] is None and e["termine"] is True

    def test_us214_ca4_deplace_vers_le_froid_demarre_a_sa_date(self, db):
        s = self._poireaux(db)
        _deplacer(db, s, date(2026, 9, 20), parcelle_id=3)
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert (e["etat"], e["jour"], e["sur"]) == (ech.ETAT_EN_COURS, 2, 7)
        assert e["depuis"] == "2026-09-20"

    def test_us214_ca4_deplace_au_froid_le_jour_meme_commence_a_zero(self, db):
        s = self._poireaux(db)
        _deplacer(db, s, date(2026, 9, 22), parcelle_id=3)
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert (e["etat"], e["jour"]) == (ech.ETAT_EN_COURS, 0)

    def test_us214_ca4_pepiniere_froide_d_origine_pas_de_compte_a_rebours(self, db):
        s = self._poireaux(db, parcelle_id=3)
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert e["etat"] == ech.ETAT_FROIDE and e["libelle"] == "en pépinière froide"
        assert e["jour"] is None and e["termine"] is False

    def test_us214_ca4_deplace_du_froid_vers_le_chaud_retrouve_le_compte_a_rebours(self, db):
        s = self._poireaux(db, parcelle_id=3)
        _deplacer(db, s, date(2026, 9, 18), parcelle_id=2)
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert (e["etat"], e["jour"]) == (ech.ETAT_EN_COURS, 3)

    def test_us214_ca4_pas_d_endurcissement_sans_plant_en_godet(self, db):
        _referentiel(db, "poireau", terre=(42, 56))
        s = _semis(db, "poireau", date(2026, 8, 15))
        e = _du_lot(_lire(db, date(2026, 9, 22)), s)["echeances"]["endurcissement"]
        assert e["etat"] is None and e["raison"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — dormance et son exclusion
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Dormance:

    def _basilic(self, db, dernier_geste: date, *, semis=date(2026, 6, 12), plants=6):
        _referentiel(db, "basilic", terre=(30, 40))
        s = _semis(db, "basilic", semis, graines=plants, numero=103)
        _godets(db, s, dernier_geste, plants, parcelle_id=2)
        return s

    def test_us214_ca5_gherkin_lot_dormant(self, db):
        s = self._basilic(db, date(2026, 7, 11))              # 70 jours avant le 19 septembre
        lecture = _lire(db)
        lot = _du_lot(lecture, s)
        d = lot["echeances"]["dormance"]
        assert d["est_dormant"] and d["jours_sans_geste"] == 70 and d["seuil_jours"] == 60
        assert lot["action_suggeree"] == {"code": "cloturer", "libelle": "Clôturer"}
        assert lot["rang_urgence"] == len(lecture["par_lot"])  # dernier de la liste

    @pytest.mark.parametrize("dernier_geste, dormant", [
        (date(2026, 7, 21), True),       # 60 jours : le seuil est atteint
        (date(2026, 7, 22), False),      # 59 jours
    ])
    def test_us214_ca5_la_borne_du_seuil(self, db, dernier_geste, dormant):
        s = self._basilic(db, dernier_geste)
        assert _du_lot(_lire(db), s)["echeances"]["dormance"]["est_dormant"] is dormant

    def test_us214_ca5_un_geste_recent_reveille_le_lot(self, db):
        s = self._basilic(db, date(2026, 6, 25))
        _deplacer(db, s, date(2026, 9, 10), parcelle_id=3)
        d = _du_lot(_lire(db), s)["echeances"]["dormance"]
        assert d["est_dormant"] is False and d["jours_sans_geste"] == 9

    def test_us214_ca5_une_plantation_est_un_geste(self, db):
        s = self._basilic(db, date(2026, 6, 25), plants=10)
        godet = db.query(Evenement).filter_by(type_action="mise_en_godet").first()
        db.add(Evenement(type_action="plantation", culture="basilic", quantite=4, unite="plants",
                         source_evenement_ids=str(godet.id), parcelle_id=1,
                         date=datetime(2026, 9, 15), potager_id=1))
        db.commit()
        d = _du_lot(_lire(db), s)["echeances"]["dormance"]
        assert d["est_dormant"] is False and d["dernier_geste"] == "2026-09-15"

    def test_us214_ca5_mise_en_terre_a_venir_jamais_dormant(self, db):
        """Des godets qui attendent une mise en terre prévue dans le futur ne sont pas oubliés,
        quelle que soit la durée sans geste."""
        _referentiel(db, "poireau", terre=(120, 150))
        s = _semis(db, "poireau", date(2026, 6, 1), graines=10)
        _godets(db, s, date(2026, 6, 10), 10, parcelle_id=2)       # 101 jours sans geste
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["mise_en_terre"]["etat"] == ech.ETAT_A_VENIR
        assert lot["echeances"]["dormance"]["est_dormant"] is False
        assert lot["action_suggeree"] is None or lot["action_suggeree"]["code"] != "cloturer"

    def test_us214_ca5_mise_en_terre_dans_la_fourchette_n_est_pas_dormant(self, db):
        _referentiel(db, "poireau", terre=(60, 150))
        s = _semis(db, "poireau", date(2026, 6, 1), graines=10)
        _godets(db, s, date(2026, 6, 10), 10, parcelle_id=2)
        assert _du_lot(_lire(db), s)["echeances"]["dormance"]["est_dormant"] is False

    def test_us214_ca5_mise_en_terre_inconnue_et_rien_depuis_60_jours_est_dormant(self, db):
        _referentiel(db, "poireau")
        s = _semis(db, "poireau", date(2026, 6, 1), graines=10)
        _godets(db, s, date(2026, 6, 10), 10, parcelle_id=2)
        assert _du_lot(_lire(db), s)["echeances"]["dormance"]["est_dormant"] is True

    def test_us214_ca5_un_lot_epuise_n_est_pas_dormant(self, db):
        _referentiel(db, "basilic", terre=(30, 40))
        s = _semis(db, "basilic", date(2026, 6, 12), graines=6)
        g = _godets(db, s, date(2026, 6, 20), 6, parcelle_id=2)
        db.add(Evenement(type_action="plantation", culture="basilic", quantite=6, unite="plants",
                         source_evenement_ids=str(g.id), parcelle_id=1,
                         date=datetime(2026, 7, 1), potager_id=1))
        db.commit()
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["dormance"]["est_dormant"] is False
        assert lot["action_suggeree"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Action suggérée — une par lot
# ═════════════════════════════════════════════════════════════════════════════
class TestActionSuggeree:

    def test_us214_action_repiquer_a_repiquer_et_en_retard(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        a_temps = _semis(db, "chou", date(2026, 9, 8))             # fourchette 18-20 septembre
        retard = _semis(db, "chou", date(2026, 9, 1))
        lecture = _lire(db)
        assert _du_lot(lecture, a_temps)["action_suggeree"]["code"] == "repiquer"
        assert _du_lot(lecture, retard)["action_suggeree"]["code"] == "repiquer"

    def test_us214_action_noter_la_levee_avant_la_fourchette(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 9, 15))
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["repiquage"]["etat"] == ech.ETAT_A_VENIR
        assert lot["action_suggeree"] == {"code": "noter_levee", "libelle": "Noter la levée"}

    def test_us214_action_noter_la_levee_pas_si_une_levee_est_notee(self, db, monkeypatch):
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 9, 15))
        monkeypatch.setattr(ech, "_levee_notee", lambda lot: True)
        assert _du_lot(_lire(db), s)["action_suggeree"] is None

    def test_us214_action_mettre_en_terre_quand_la_mise_en_terre_est_atteinte(self, db):
        _referentiel(db, "chou", terre=(10, 30))
        s = _semis(db, "chou", date(2026, 9, 1))
        _godets(db, s, date(2026, 9, 10), 20, parcelle_id=3)       # pépinière froide : pas de compte à rebours
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["mise_en_terre"]["etat"] == ech.ETAT_ATTEINTE
        assert lot["action_suggeree"]["code"] == "mettre_en_terre"

    def test_us214_action_aucune_en_pepiniere_froide_avant_la_mise_en_terre(self, db):
        _referentiel(db, "chou", terre=(60, 80))
        s = _semis(db, "chou", date(2026, 9, 1))
        _godets(db, s, date(2026, 9, 10), 20, parcelle_id=3)
        assert _du_lot(_lire(db), s)["action_suggeree"] is None

    def test_us214_action_une_seule_par_lot_dormant_prime(self, db):
        """Un lot oublié, aussi en retard de repiquage : « Clôturer », pas « Repiquer »."""
        _referentiel(db, "chou", godet=(10, 12))
        s = _semis(db, "chou", date(2026, 7, 1))
        lot = _du_lot(_lire(db), s)
        assert lot["echeances"]["repiquage"]["etat"] == ech.ETAT_EN_RETARD
        # Des graines à lever, 80 jours sans geste, mise en terre inconnue : dormant.
        assert lot["echeances"]["dormance"]["est_dormant"] is True
        assert lot["action_suggeree"]["code"] == "cloturer"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — ordre d'urgence
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Ordre:

    def test_us214_ca6_retards_puis_a_venir_puis_sans_echeance_puis_dormants(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _referentiel(db, "laitue", godet=(10, 12))
        _referentiel(db, "basilic", terre=(30, 40))
        retard_6 = _semis(db, "chou", date(2026, 9, 1))             # fin le 13 : +6 j
        retard_10 = _semis(db, "chou", date(2026, 8, 28))           # fin le 9 : +10 j
        dans_6 = _semis(db, "laitue", date(2026, 9, 15))            # début le 25 : dans 6 j
        dans_9 = _semis(db, "laitue", date(2026, 9, 18))            # début le 28 : dans 9 j
        sans = _semis(db, "cardon", date(2026, 9, 10))
        dormant = _semis(db, "basilic", date(2026, 6, 12), graines=6)
        _godets(db, dormant, date(2026, 7, 11), 6, parcelle_id=2)

        lecture = _lire(db)
        ordre = sorted(lecture["par_lot"], key=lambda k: lecture["par_lot"][k]["rang_urgence"])
        attendu = [f"semis-{e.id}" for e in (retard_10, retard_6, dans_6, dans_9, sans, dormant)]
        assert ordre == attendu
        assert [lecture["par_lot"][k]["rang_urgence"] for k in ordre] == [1, 2, 3, 4, 5, 6]

    def test_us214_ca6_un_lot_epuise_passe_apres_les_lots_actifs_sans_echeance(self, db):
        _referentiel(db, "basilic", terre=(30, 40))
        epuise = _semis(db, "basilic", date(2026, 6, 12), graines=6)
        g = _godets(db, epuise, date(2026, 6, 20), 6, parcelle_id=2)
        db.add(Evenement(type_action="plantation", culture="basilic", quantite=6, unite="plants",
                         source_evenement_ids=str(g.id), parcelle_id=1,
                         date=datetime(2026, 7, 1), potager_id=1))
        db.commit()
        actif = _semis(db, "cardon", date(2026, 9, 10))
        lecture = _lire(db)
        assert _du_lot(lecture, actif)["rang_urgence"] < _du_lot(lecture, epuise)["rang_urgence"]

    def test_us214_ca6_a_echeance_egale_le_numero_de_lot_departage(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        deuxieme = _semis(db, "chou", date(2026, 9, 1), numero=7)
        premier = _semis(db, "chou", date(2026, 9, 1), numero=3)
        lecture = _lire(db)
        assert _du_lot(lecture, premier)["rang_urgence"] < _du_lot(lecture, deuxieme)["rang_urgence"]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le résumé du bandeau
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Resume:

    def test_us214_ca8_a_repiquer_compte_les_lots_et_les_plants(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 9, 1), graines=48)            # en retard
        _semis(db, "chou", date(2026, 9, 8), graines=30)            # dans la fourchette
        _semis(db, "chou", date(2026, 9, 17), graines=12)           # pas encore
        r = _lire(db)["resume"]["a_repiquer"]
        assert r == {"lots": 2, "plants": 78}

    def test_us214_ca8_a_endurcir(self, db):
        _referentiel(db, "poireau", terre=(42, 56))
        en_cours = _semis(db, "poireau", date(2026, 8, 15))
        _godets(db, en_cours, date(2026, 9, 5), 20, parcelle_id=2)
        trop_tot = _semis(db, "poireau", date(2026, 9, 1))
        _godets(db, trop_tot, date(2026, 9, 8), 20, parcelle_id=2)
        froid = _semis(db, "poireau", date(2026, 8, 15), parcelle_id=3)
        _godets(db, froid, date(2026, 9, 5), 20, parcelle_id=3)
        assert _lire(db, date(2026, 9, 22))["resume"]["a_endurcir"] == {"lots": 1}

    def test_us214_ca8_prets_pour_le_plan_compte_les_godets_disponibles(self, db):
        _referentiel(db, "chou", terre=(10, 30))
        _referentiel(db, "poireau")                                  # mise en terre inconnue : prêt
        _referentiel(db, "celeri", terre=(100, 120))                # à venir : pas prêt
        a = _semis(db, "chou", date(2026, 9, 1), graines=20)
        _godets(db, a, date(2026, 9, 10), 20, parcelle_id=3)
        b = _semis(db, "poireau", date(2026, 9, 1), graines=15)
        _godets(db, b, date(2026, 9, 10), 15, parcelle_id=3)
        c = _semis(db, "celeri", date(2026, 9, 1), graines=8)
        _godets(db, c, date(2026, 9, 10), 8, parcelle_id=3)
        pret = _lire(db)["resume"]["prets_pour_le_plan"]
        assert (pret["lots"], pret["plants"]) == (2, 35)

    def test_us214_ca8_prets_pour_le_plan_deduit_ce_qui_est_deja_plante(self, db):
        _referentiel(db, "chou", terre=(10, 30))
        s = _semis(db, "chou", date(2026, 9, 1), graines=20)
        g = _godets(db, s, date(2026, 9, 10), 20, parcelle_id=3)
        db.add(Evenement(type_action="plantation", culture="chou", quantite=5, unite="plants",
                         source_evenement_ids=str(g.id), parcelle_id=1,
                         date=datetime(2026, 9, 15), potager_id=1))
        db.commit()
        assert _lire(db)["resume"]["prets_pour_le_plan"]["plants"] == 15

    def test_us214_ca8_prets_pour_le_plan_porte_les_rangs_libres_du_plan(self, db):
        _referentiel(db, "chou", terre=(10, 30))
        s = _semis(db, "chou", date(2026, 9, 1), graines=20)
        _godets(db, s, date(2026, 9, 10), 20, parcelle_id=3)
        rangs = _lire(db)["resume"]["prets_pour_le_plan"]["rangs_libres_par_parcelle"]
        nord = next(r for r in rangs if r["parcelle"] == "Planche nord")
        assert nord["rangs_libres"] == 4
        assert all(r["parcelle"] not in {"Serre", "Châssis froid", "Véranda"} for r in rangs)

    def test_us214_ca8_sans_plant_pret_le_plan_n_est_pas_calcule(self, db, monkeypatch):
        def _interdit(*a, **k):
            raise AssertionError("le Plan ne doit pas être relu sans plant prêt")
        monkeypatch.setattr(ech, "_rangs_libres", _interdit)
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 9, 1))
        assert _lire(db)["resume"]["prets_pour_le_plan"]["rangs_libres_par_parcelle"] == []

    def test_us214_ca8_gherkin_a_semer(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(8, 10))
        a_semer = _lire(db)["resume"]["a_semer"]
        assert [c["culture"] for c in a_semer["cultures"]] == ["laitue d'hiver"]
        assert a_semer["total"] == 1

    def test_us214_ca8_a_semer_le_mois_adjacent_ne_suffit_pas(self, db):
        _referentiel(db, "laitue d'hiver", fenetre=(10, 12))         # octobre : un mois après le 19 sept.
        _referentiel(db, "mache", fenetre=(6, 8))                    # août : un mois avant
        assert _lire(db)["resume"]["a_semer"]["cultures"] == []

    def test_us214_ca8_a_semer_pas_si_un_lot_de_la_culture_est_en_cours(self, db):
        _referentiel(db, "laitue", godet=(10, 12), fenetre=(8, 10))
        _referentiel(db, "mache", fenetre=(8, 10))
        _semis(db, "laitue", date(2026, 9, 15))
        noms = [c["culture"] for c in _lire(db)["resume"]["a_semer"]["cultures"]]
        assert noms == ["mache"]

    def test_us214_ca8_a_semer_un_lot_epuise_n_empeche_pas_de_resemer(self, db):
        _referentiel(db, "laitue", fenetre=(8, 10))
        s = _semis(db, "laitue", date(2026, 8, 1), graines=6)
        g = _godets(db, s, date(2026, 8, 12), 6, parcelle_id=2)
        db.add(Evenement(type_action="plantation", culture="laitue", quantite=6, unite="plants",
                         source_evenement_ids=str(g.id), parcelle_id=1,
                         date=datetime(2026, 8, 20), potager_id=1))
        db.commit()
        assert [c["culture"] for c in _lire(db)["resume"]["a_semer"]["cultures"]] == ["laitue"]

    def test_us214_ca8_a_semer_ne_lit_que_la_zone_du_potager(self, db):
        fiche = _referentiel(db, "laitue")
        it = db.query(ItineraireCultural).filter_by(culture_id=fiche).first()
        db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="continental",
                                phase=cal.PHASE_SEMIS_PEPINIERE, mois_debut=8, mois_fin=10, source_id=1))
        db.commit()
        assert _lire(db)["resume"]["a_semer"]["cultures"] == []


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — une lecture, une météo au plus, aucune requête par lot
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Requetes:

    def test_us214_ca9_une_seule_lecture_meteo_pour_toutes_les_cultures_a_semer(self, db, _meteo_sans_reseau):
        for nom in ("laitue", "mache", "epinard"):
            _referentiel(db, nom, fenetre=(8, 10))
        _lire(db)
        assert len(_meteo_sans_reseau) == 1

    def test_us214_ca9_aucune_meteo_sans_culture_candidate(self, db, _meteo_sans_reseau):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 9, 1))
        _lire(db)
        assert _meteo_sans_reseau == []

    def test_us214_ca9_le_nombre_de_requetes_ne_depend_pas_du_nombre_de_lots(self, db):
        _referentiel(db, "chou", godet=(10, 12), terre=(42, 56))
        for jour in (1, 2, 3):
            s = _semis(db, "chou", date(2026, 9, jour))
            _godets(db, s, date(2026, 9, jour + 10), 5, parcelle_id=2)

        def _compter(lots):
            instructions = []
            moteur = db.get_bind()

            def _ecouter(conn, cursor, statement, *a):
                instructions.append(statement)

            event.listen(moteur, "before_cursor_execute", _ecouter)
            try:
                ech.lire_echeances(db, CTX, lots, LE_19_SEPT)
            finally:
                event.remove(moteur, "before_cursor_execute", _ecouter)
            return len(instructions)

        trois = _compter(calcul_lots_pepiniere(db, LE_19_SEPT, potager_id=1))
        for jour in range(4, 13):
            s = _semis(db, "chou", date(2026, 9, jour))
            _godets(db, s, date(2026, 9, jour + 5), 5, parcelle_id=2)
        douze = _compter(calcul_lots_pepiniere(db, LE_19_SEPT, potager_id=1))
        assert douze == trois


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — lecture seule
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10LectureSeule:

    def test_us214_ca10_aucun_geste_cree_meme_pour_un_lot_dormant(self, db):
        _referentiel(db, "basilic", terre=(30, 40))
        s = _semis(db, "basilic", date(2026, 6, 12), graines=6)
        _godets(db, s, date(2026, 7, 11), 6, parcelle_id=2)
        avant = db.query(Evenement).count()
        _lire(db)
        db.expire_all()
        assert db.query(Evenement).count() == avant
        assert not db.new and not db.dirty and not db.deleted

    def test_us214_ca10_aucun_stock_ne_change(self, db):
        _referentiel(db, "chou", godet=(10, 12), terre=(42, 56))
        s = _semis(db, "chou", date(2026, 9, 1))
        _godets(db, s, date(2026, 9, 12), 20, parcelle_id=2)
        avant = [
            {k: v for k, v in lot.items() if k != "emplacement"}
            for lot in calcul_lots_pepiniere(db, LE_19_SEPT, potager_id=1)
        ]
        _lire(db)
        apres = [
            {k: v for k, v in lot.items() if k != "emplacement"}
            for lot in calcul_lots_pepiniere(db, LE_19_SEPT, potager_id=1)
        ]
        assert avant == apres


# ═════════════════════════════════════════════════════════════════════════════
# Isolation entre potagers
# ═════════════════════════════════════════════════════════════════════════════
class TestIsolation:

    def test_us214_isolation_les_lots_d_un_autre_potager_ne_figurent_pas(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        a = _semis(db, "chou", date(2026, 9, 1), potager_id=1)
        b = _semis(db, "chou", date(2026, 9, 1), potager_id=2, parcelle_id=5)
        lecture_a = _lire(db, ctx=CTX)
        lecture_b = _lire(db, ctx=CTX_B)
        assert list(lecture_a["par_lot"]) == [f"semis-{a.id}"]
        assert list(lecture_b["par_lot"]) == [f"semis-{b.id}"]

    def test_us214_isolation_la_correction_d_un_potager_n_est_jamais_lue_par_l_autre(self, db):
        """Le délai de godet corrigé pour le potager B ne déplace pas l'échéance du potager A."""
        fiche = _referentiel(db, "chou", godet=(10, 12))
        _referentiel(db, "chou", godet=(20, 25), culture_id=fiche, itineraire_potager=2)
        a = _semis(db, "chou", date(2026, 9, 1), potager_id=1)
        b = _semis(db, "chou", date(2026, 9, 1), potager_id=2, parcelle_id=5)
        ra = _du_lot(_lire(db, ctx=CTX), a)["echeances"]["repiquage"]
        rb = _du_lot(_lire(db, ctx=CTX_B), b)["echeances"]["repiquage"]
        assert (ra["du"], ra["au"]) == ("2026-09-11", "2026-09-13")
        assert (rb["du"], rb["au"]) == ("2026-09-21", "2026-09-26")

    def test_us214_isolation_le_resume_ne_compte_que_les_lots_du_potager(self, db):
        _referentiel(db, "chou", godet=(10, 12))
        _semis(db, "chou", date(2026, 9, 1), graines=10, potager_id=1)
        _semis(db, "chou", date(2026, 9, 1), graines=99, potager_id=2, parcelle_id=5)
        assert _lire(db, ctx=CTX)["resume"]["a_repiquer"] == {"lots": 1, "plants": 10}


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — l'API ajoute, sans rien retirer
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def _moteur_api():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client_api(_moteur_api, monkeypatch):
    from app.api import main

    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_moteur_api))
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client


class TestCA7Api:

    def _jardin(self, client, moteur):
        """Un compte, son potager, une culture et un lot en retard de repiquage."""
        from app.services import auth as svc_auth

        session = sessionmaker(bind=moteur)()
        user = svc_auth.inscrire_utilisateur(session, "jardinier@example.com", "motdepasse123")
        entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
        client.post("/potagers", json={"nom": "Jardin"}, headers=entete)
        potager = session.query(Potager).filter(Potager.proprietaire_id == user.id).first()
        potager.zone_climatique = "oceanique"
        session.add(ReferentielSource(
            id=1, code="test", libelle="Test", licence="CC0",
            attribution="Valeurs de test", partageable=True, importee=True,
        ))
        fiche = CultureConfig(nom="chou", type_organe_recolte="fruit")
        session.add(fiche)
        session.flush()
        it = ItineraireCultural(culture_id=fiche.id, nom="standard", nom_normalise="standard", source_id=1)
        session.add(it)
        session.flush()
        session.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_SEMIS_GODET,
                                   jours_min=10, jours_max=12, source_id=1))
        session.add(Evenement(type_action="semis", culture="chou", quantite=48, unite="graines",
                              date=datetime(2026, 9, 1), potager_id=potager.id, numero_lot=128))
        session.commit()
        session.close()
        return entete

    def test_us214_ca7_les_lots_gagnent_echeances_action_et_rang(self, client_api, _moteur_api):
        entete = self._jardin(client_api, _moteur_api)
        corps = client_api.get("/pepiniere/lots", params={"date_ref": "2026-09-19"}, headers=entete).json()
        lot = corps["lots"][0]
        assert lot["echeances"]["repiquage"]["etat"] == "en_retard"
        assert lot["echeances"]["repiquage"]["retard_jours"] == 6
        assert lot["action_suggeree"] == {"code": "repiquer", "libelle": "Repiquer"}
        assert lot["rang_urgence"] == 1

    def test_us214_ca7_aucun_champ_existant_n_est_retire_ni_renomme(self, client_api, _moteur_api):
        entete = self._jardin(client_api, _moteur_api)
        corps = client_api.get("/pepiniere/lots", params={"date_ref": "2026-09-19"}, headers=entete).json()
        assert {"lots", "total", "date_ref_effective"} <= set(corps)
        champs = {
            "lot_id", "semis_id", "numero_lot", "culture", "variete", "date_semis", "parcelle",
            "type_pepiniere", "graines_semees", "unite", "graines_soldees", "plants_obtenus",
            "nb_mises_en_godet", "date_derniere_mise_en_godet", "nb_plantes", "nb_vendus",
            "nb_pertes_godet", "sans_semis_rattache", "graines_en_germination", "etat_germination",
            "incoherence_saisie", "taux_germination", "stock_residuel_godet", "emplacement",
            "graines_emplacement", "godets_par_emplacement", "famille",
        }
        assert champs <= set(corps["lots"][0])
        assert corps["lots"][0]["date_semis"] == "2026-09-01"

    def test_us214_ca8_la_reponse_porte_le_resume(self, client_api, _moteur_api):
        entete = self._jardin(client_api, _moteur_api)
        corps = client_api.get("/pepiniere/lots", params={"date_ref": "2026-09-19"}, headers=entete).json()
        assert set(corps["resume"]) == {"a_repiquer", "a_endurcir", "prets_pour_le_plan", "a_semer"}
        assert corps["resume"]["a_repiquer"] == {"lots": 1, "plants": 48}

    def test_us214_ca7_les_dates_de_geste_sont_en_iso_court(self, client_api, _moteur_api):
        entete = self._jardin(client_api, _moteur_api)
        lot = client_api.get("/pepiniere/lots", params={"date_ref": "2026-09-19"}, headers=entete).json()["lots"][0]
        assert lot["date_dernier_geste"] == "2026-09-01" and lot["date_deplacement"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA11, CA12 — la documentation fait partie de la livraison
# ═════════════════════════════════════════════════════════════════════════════
class TestDocumentation:

    def test_us214_ca11_la_fiche_de_domaine_existe_et_est_dans_la_table(self):
        fiche = RACINE / "docs" / "domaines" / "pepiniere.md"
        assert fiche.exists()
        texte = fiche.read_text(encoding="utf-8")
        for attendu in ("7 jours", "60 jours", "ordre d'urgence", "Sans donnée", "app/services/echeances_lots.py"):
            assert attendu.lower() in texte.lower(), attendu
        readme = (RACINE / "docs" / "domaines" / "README.md").read_text(encoding="utf-8")
        assert "[pepiniere.md](pepiniere.md)" in readme and "echeances_lots" in readme

    def test_us214_ca12_la_fiche_jardinier_explique_les_etats(self):
        texte = (RACINE / "data" / "connaissance" / "doc_app" / "pepiniere-par-lot.md").read_text(
            encoding="utf-8").lower()
        for mot in ("à repiquer", "à endurcir", "prêts pour le plan", "dormant"):
            assert mot in texte, mot
        assert "échéance" in texte and "non renseign" in texte
