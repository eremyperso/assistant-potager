"""
tests/test_us266_veilleur.py — Détecter ce qui mérite un message : le veilleur [US-266]
======================================================================================
Le veilleur repère seul le gel sur les cultures en place, un lot à repiquer, une levée
non notée… sans modèle (R7) et sans rien envoyer : les signaux sont en base et dans les
journaux.

Les détecteurs sont des fonctions pures : leurs tests construisent un `EtatPotager` à la
main, sans base. Le passage (lecture, boucle potager par potager, dédoublonnage) tourne
sur une base SQLite en mémoire ; la météo est simulée, aucun appel réseau.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import alerte_recolte as svc_alerte_recolte
from app.services import calendrier_cultural as cal
from app.services import previsions_meteo as svc_previsions
from app.services.compagnon import signaux as svc_signaux
from app.services.compagnon import veilleur
from app.services.compagnon import veilleur_passage as passage
from app.services.compagnon.veilleur import (
    CultureEnPlace, EtatPotager, FenetreSemis, GesteDuJournal, JourPrevu, LotPepiniere, Signal,
)
from database import db as module_db
from database.db import Base
from database.models import (
    CultureConfig, DureeCulturale, Evenement, FenetreCulturale, ItineraireCultural, Parcelle,
    Potager, Rappel, ReferentielSource, SignalVeilleur,
)

RACINE = Path(__file__).resolve().parent.parent
MAINTENANT = datetime(2026, 10, 27, 12, 0)
AUJOURD_HUI = MAINTENANT.date()
DEMAIN = AUJOURD_HUI + timedelta(days=1)


def _etat(**champs) -> EtatPotager:
    return EtatPotager(potager_id=champs.pop("potager_id", 1), maintenant=champs.pop("maintenant", MAINTENANT), **champs)


def _laitue(**champs) -> CultureEnPlace:
    valeurs = dict(
        culture="laitue", nb_plants=6, age_jours=10, parcelle_id=12, parcelle_nom="Planche Est",
        unite="plants", type_organe="végétatif", date_plantation=AUJOURD_HUI - timedelta(days=10),
        rusticite_min_c=-1.0,
    )
    valeurs.update(champs)
    return CultureEnPlace(**valeurs)


def _cles(signaux: list[Signal]) -> list[str]:
    return [s.cle_unique for s in signaux]


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Un détecteur est une fonction pure
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1DetecteursPurs:
    def test_un_signal_porte_theme_cle_priorite_expiration_et_donnees(self):
        etat = _etat(cultures=(_laitue(),), previsions=(JourPrevu(DEMAIN, temp_min=-2.0, temp_max=6.0),))
        [signal] = veilleur.detecter_gel_canicule(etat)
        assert signal.theme in veilleur.THEMES
        assert signal.priorite in veilleur.PRIORITES
        assert isinstance(signal.expire_le, datetime)
        assert signal.donnees["temp_min"] == -2.0

    def test_meme_etat_meme_resultat(self):
        etat = _etat(cultures=(_laitue(),), previsions=(JourPrevu(DEMAIN, temp_min=-2.0),))
        assert veilleur.detecter(etat) == veilleur.detecter(etat)

    def test_le_module_des_detecteurs_ne_lit_ni_base_ni_reseau(self):
        """Pur au sens strict : ni SQLAlchemy, ni base, ni météo réseau dans `veilleur.py`."""
        arbre = ast.parse((RACINE / "app/services/compagnon/veilleur.py").read_text(encoding="utf-8"))
        modules = _modules_importes(arbre)
        interdits = ("sqlalchemy", "database", "utils.meteo", "app.services.previsions_meteo", "requests", "httpx")
        assert not [m for m in modules if m.startswith(interdits)], modules

    def test_un_detecteur_en_panne_ne_fait_pas_taire_les_autres(self):
        def en_panne(etat):
            raise RuntimeError("boum")
        etat = _etat(cultures=(_laitue(),), previsions=(JourPrevu(DEMAIN, temp_min=-2.0),))
        signaux = veilleur.detecter(etat, (en_panne, veilleur.detecter_gel_canicule))
        assert _cles(signaux) == [f"gel:{DEMAIN.isoformat()}:parcelle-12"]


# ═════════════════════════════════════════════════════════════════════════════
# CA2, CA8 — Les détecteurs livrés, seuils du référentiel
# ═════════════════════════════════════════════════════════════════════════════
class TestGelCanicule:
    def test_gel_sous_la_rusticite_de_la_culture(self):
        etat = _etat(cultures=(_laitue(),), previsions=(JourPrevu(DEMAIN, temp_min=-2.0),))
        [signal] = veilleur.detecter_gel_canicule(etat)
        assert signal.cle_unique == f"gel:{DEMAIN.isoformat()}:parcelle-12"
        assert signal.theme == veilleur.THEME_METEO
        assert signal.priorite == veilleur.PRIORITE_IMMEDIATE
        assert signal.expire_le == datetime.combine(DEMAIN, time(10, 0))
        assert signal.donnees["parcelle"] == "Planche Est"
        assert signal.donnees["cultures"][0] == {
            "culture": "laitue", "variete": None, "nb_plants": 6, "unite": "plants", "seuil_c": -1.0,
        }

    def test_au_dessus_de_la_rusticite_pas_de_gel(self):
        """Le seuil est celui de la culture, pas zéro : un chou à -8 °C ne craint pas -2 °C."""
        chou = _laitue(culture="chou", rusticite_min_c=-8.0)
        etat = _etat(cultures=(chou,), previsions=(JourPrevu(DEMAIN, temp_min=-2.0),))
        assert veilleur.detecter_gel_canicule(etat) == []

    def test_sans_rusticite_connue_aucun_seuil_invente(self):
        etat = _etat(cultures=(_laitue(rusticite_min_c=None),), previsions=(JourPrevu(DEMAIN, temp_min=-6.0),))
        assert veilleur.detecter_gel_canicule(etat) == []

    def test_un_signal_par_jour_et_par_parcelle_qui_cite_les_cultures_exposees(self):
        tomate = _laitue(culture="tomate", rusticite_min_c=3.0)
        chou = _laitue(culture="chou", rusticite_min_c=-8.0)
        ailleurs = _laitue(parcelle_id=None, parcelle_nom=None)
        etat = _etat(cultures=(_laitue(), tomate, chou, ailleurs), previsions=(JourPrevu(DEMAIN, temp_min=-2.0),))
        signaux = veilleur.detecter_gel_canicule(etat)
        assert sorted(_cles(signaux)) == [
            f"gel:{DEMAIN.isoformat()}:parcelle-12", f"gel:{DEMAIN.isoformat()}:sans-parcelle",
        ]
        planche = next(s for s in signaux if s.cle_unique.endswith("parcelle-12"))
        assert [c["culture"] for c in planche.donnees["cultures"]] == ["laitue", "tomate"]

    def test_horizon_et_priorite(self):
        """Au-delà du lendemain, le signal attend ; au-delà de J+3, la prévision n'est pas regardée."""
        previsions = tuple(
            JourPrevu(AUJOURD_HUI + timedelta(days=i), temp_min=-3.0) for i in range(0, 6)
        )
        signaux = veilleur.detecter_gel_canicule(_etat(cultures=(_laitue(),), previsions=previsions))
        priorites = {s.donnees["jour"]: s.priorite for s in signaux}
        assert len(signaux) == veilleur.HORIZON_METEO_JOURS + 1
        assert priorites[AUJOURD_HUI.isoformat()] == veilleur.PRIORITE_IMMEDIATE
        assert priorites[DEMAIN.isoformat()] == veilleur.PRIORITE_IMMEDIATE
        assert priorites[(AUJOURD_HUI + timedelta(days=2)).isoformat()] == veilleur.PRIORITE_NORMALE

    def test_un_jour_passe_n_est_pas_regarde(self):
        hier = JourPrevu(AUJOURD_HUI - timedelta(days=1), temp_min=-5.0)
        assert veilleur.detecter_gel_canicule(_etat(cultures=(_laitue(),), previsions=(hier,))) == []

    def test_canicule_sur_toute_culture_en_place(self):
        jour = JourPrevu(DEMAIN, temp_min=20.0, temp_max=veilleur.SEUIL_CANICULE_C)
        [signal] = veilleur.detecter_gel_canicule(_etat(cultures=(_laitue(rusticite_min_c=None),), previsions=(jour,)))
        assert signal.cle_unique == f"canicule:{DEMAIN.isoformat()}:parcelle-12"
        assert signal.donnees["temp_max"] == veilleur.SEUIL_CANICULE_C

    def test_sans_culture_en_place_rien(self):
        jour = JourPrevu(DEMAIN, temp_min=-10.0, temp_max=40.0)
        assert veilleur.detecter_gel_canicule(_etat(previsions=(jour,))) == []


class TestPluieSecheresse:
    @staticmethod
    def _chaleur_seche(jours: int = veilleur.JOURS_CHAUDS_SECHERESSE) -> tuple[JourPrevu, ...]:
        return tuple(
            JourPrevu(AUJOURD_HUI + timedelta(days=i), temp_max=30.0, precipitations=0.0) for i in range(jours)
        )

    def test_fortes_pluies(self):
        jour = JourPrevu(DEMAIN, precipitations=25.0)
        [signal] = veilleur.detecter_pluie_secheresse(_etat(previsions=(jour,)))
        assert signal.cle_unique == f"pluie:{DEMAIN.isoformat()}"
        assert signal.theme == veilleur.THEME_METEO
        assert signal.donnees["precipitations_mm"] == 25.0

    def test_pluie_ordinaire_rien(self):
        assert veilleur.detecter_pluie_secheresse(_etat(previsions=(JourPrevu(DEMAIN, precipitations=5.0),))) == []

    def test_secheresse_sans_arrosage_note(self):
        arrose = GesteDuJournal(jour=AUJOURD_HUI - timedelta(days=6), type_action="arrosage")
        etat = _etat(cultures=(_laitue(),), previsions=self._chaleur_seche(), journal=(arrose,))
        [signal] = veilleur.detecter_pluie_secheresse(etat)
        assert signal.theme == veilleur.THEME_SUIVIS
        assert signal.cle_unique == f"secheresse:arrosage-du:{arrose.jour.isoformat()}"
        assert signal.donnees["dernier_arrosage"] == arrose.jour.isoformat()

    def test_jamais_arrose_cle_de_la_semaine(self):
        etat = _etat(cultures=(_laitue(),), previsions=self._chaleur_seche())
        [signal] = veilleur.detecter_pluie_secheresse(etat)
        annee, semaine, _ = AUJOURD_HUI.isocalendar()
        assert signal.cle_unique == f"secheresse:aucun-arrosage:{annee}-S{semaine:02d}"

    def test_arrosage_recent_rien(self):
        arrose = GesteDuJournal(jour=AUJOURD_HUI - timedelta(days=2), type_action="arrosage")
        etat = _etat(cultures=(_laitue(),), previsions=self._chaleur_seche(), journal=(arrose,))
        assert veilleur.detecter_pluie_secheresse(etat) == []

    def test_cumul_de_pluie_inconnu_ne_vaut_pas_sec(self):
        jours = tuple(JourPrevu(AUJOURD_HUI + timedelta(days=i), temp_max=30.0) for i in range(3))
        assert veilleur.detecter_pluie_secheresse(_etat(cultures=(_laitue(),), previsions=jours)) == []

    def test_un_jour_frais_dans_la_serie_rien(self):
        jours = list(self._chaleur_seche())
        jours[1] = JourPrevu(jours[1].jour, temp_max=20.0, precipitations=0.0)
        assert veilleur.detecter_pluie_secheresse(_etat(cultures=(_laitue(),), previsions=tuple(jours))) == []

    def test_sans_culture_pas_de_secheresse(self):
        assert veilleur.detecter_pluie_secheresse(_etat(previsions=self._chaleur_seche())) == []


class TestEcheancesLots:
    def test_lot_a_repiquer(self):
        lot = LotPepiniere(
            lot_id="semis-7", numero=4, culture="tomate", date_semis=AUJOURD_HUI - timedelta(days=20),
            action=veilleur.ACTION_REPIQUER, echeance_du=AUJOURD_HUI - timedelta(days=2),
            echeance_au=AUJOURD_HUI + timedelta(days=3),
        )
        [signal] = veilleur.detecter_echeances_lots(_etat(lots=(lot,)))
        assert signal.cle_unique == "repiquer:lot-4"
        assert signal.theme == veilleur.THEME_ECHEANCES
        assert signal.expire_le == datetime.combine(AUJOURD_HUI + timedelta(days=3), time(23, 59))
        assert signal.donnees["en_retard"] is False

    def test_mise_en_terre_en_retard(self):
        lot = LotPepiniere(
            lot_id="semis-8", culture="poivron", action=veilleur.ACTION_METTRE_EN_TERRE,
            echeance_au=AUJOURD_HUI - timedelta(days=4),
        )
        [signal] = veilleur.detecter_echeances_lots(_etat(lots=(lot,)))
        assert signal.cle_unique == "mettre_en_terre:lot-semis-8"
        assert signal.donnees["en_retard"] is True
        assert signal.expire_le == MAINTENANT + veilleur.DUREE_PERTINENCE

    def test_les_autres_actions_ne_sont_pas_des_echeances(self):
        lots = (
            LotPepiniere(lot_id="a", culture="x", action="noter_levee"),
            LotPepiniere(lot_id="b", culture="x", action="cloturer"),
            LotPepiniere(lot_id="c", culture="x", action=None),
        )
        assert veilleur.detecter_echeances_lots(_etat(lots=lots)) == []


class TestRecolteImminente:
    def test_meme_regle_que_le_plan(self):
        mure = _laitue(age_jours=45)
        jeune = _laitue(culture="tomate", type_organe="reproducteur", age_jours=89)
        [signal] = veilleur.detecter_recolte_imminente(_etat(cultures=(mure, jeune)))
        assert signal.cle_unique == f"recolte:parcelle-12:laitue:{mure.date_plantation.isoformat()}"
        assert signal.donnees["seuil_jours"] == 45
        assert signal.theme == veilleur.THEME_ECHEANCES

    def test_un_semis_en_place_n_en_releve_pas(self):
        semis = _laitue(age_jours=200, est_semis=True)
        assert veilleur.detecter_recolte_imminente(_etat(cultures=(semis,))) == []

    def test_organe_inconnu_rien(self):
        assert veilleur.detecter_recolte_imminente(_etat(cultures=(_laitue(type_organe=None, age_jours=500),))) == []


class TestLeveeNonNotee:
    @staticmethod
    def _lot(**champs) -> LotPepiniere:
        valeurs = dict(
            lot_id="semis-3", numero=3, culture="tomate", date_semis=AUJOURD_HUI - timedelta(days=15),
            graines_en_attente=24, duree_levee_max_jours=10,
        )
        valeurs.update(champs)
        return LotPepiniere(**valeurs)

    def test_semis_plus_vieux_que_sa_levee(self):
        [signal] = veilleur.detecter_levee_non_notee(_etat(lots=(self._lot(),)))
        assert signal.cle_unique == "levee:lot-3"
        assert signal.theme == veilleur.THEME_SUIVIS
        assert signal.donnees["levee_attendue_le"] == (AUJOURD_HUI - timedelta(days=5)).isoformat()
        assert signal.donnees["jours_depuis_semis"] == 15

    def test_encore_dans_la_duree_de_levee(self):
        assert veilleur.detecter_levee_non_notee(_etat(lots=(self._lot(duree_levee_max_jours=15),))) == []

    @pytest.mark.parametrize("champs", [
        {"levee_notee": True}, {"graines_en_attente": 0}, {"duree_levee_max_jours": None}, {"date_semis": None},
    ])
    def test_pas_de_signal(self, champs):
        assert veilleur.detecter_levee_non_notee(_etat(lots=(self._lot(**champs),))) == []


class TestFenetresSemis:
    def test_les_fenetres_qui_s_ouvrent_ce_mois(self):
        fenetres = (
            FenetreSemis("ail", cal.PHASE_SEMIS_PLEINE_TERRE, 10, 11),
            FenetreSemis("fève", cal.PHASE_SEMIS_PLEINE_TERRE, 10, 12, deja_cultivee=True),
            FenetreSemis("tomate", cal.PHASE_SEMIS_PEPINIERE, 2, 4),
            FenetreSemis("laitue", cal.PHASE_SEMIS_PEPINIERE, 8, 10),   # ouverte, mais pas ce mois-ci
        )
        [signal] = veilleur.detecter_fenetres_semis(_etat(fenetres_semis=fenetres))
        assert signal.cle_unique == "semis:2026-10"
        assert signal.theme == veilleur.THEME_SUGGESTIONS
        assert signal.priorite == veilleur.PRIORITE_RESUME
        assert [c["culture"] for c in signal.donnees["cultures"]] == ["fève", "ail"]
        assert signal.expire_le == datetime(2026, 10, 31, 23, 59)

    def test_aucune_ouverture_rien(self):
        assert veilleur.detecter_fenetres_semis(_etat(fenetres_semis=(FenetreSemis("x", "semis_pepiniere", 3, 4),))) == []

    def test_borne(self):
        fenetres = tuple(FenetreSemis(f"c{i:02d}", "semis_pleine_terre", 10, 11) for i in range(20))
        [signal] = veilleur.detecter_fenetres_semis(_etat(fenetres_semis=fenetres))
        assert len(signal.donnees["cultures"]) == veilleur.NB_FENETRES_MAX
        assert signal.donnees["total"] == 20

    def test_fin_d_annee(self):
        decembre = datetime(2026, 12, 15, 9, 0)
        [signal] = veilleur.detecter_fenetres_semis(
            _etat(maintenant=decembre, fenetres_semis=(FenetreSemis("x", "semis_pepiniere", 12, 2),)),
        )
        assert signal.expire_le == datetime(2026, 12, 31, 23, 59)


class TestBilanSemaine:
    def test_bilan_des_sept_derniers_jours(self):
        journal = (
            GesteDuJournal(AUJOURD_HUI - timedelta(days=8), "semis", "radis"),   # hors semaine
            GesteDuJournal(AUJOURD_HUI - timedelta(days=6), "arrosage"),
            GesteDuJournal(AUJOURD_HUI - timedelta(days=3), "recolte", "tomate", 1.5, "kg"),
            GesteDuJournal(AUJOURD_HUI, "recolte", "tomate", 2.0, "kg"),
            GesteDuJournal(AUJOURD_HUI, "observation", texte_original=veilleur.TEXTE_METEO_AUTO),
        )
        [signal] = veilleur.detecter_bilan_semaine(_etat(journal=journal))
        annee, semaine, _ = AUJOURD_HUI.isocalendar()
        assert signal.cle_unique == f"bilan:{annee}-S{semaine:02d}"
        assert signal.theme == veilleur.THEME_RESUME
        assert signal.donnees["nb_gestes"] == 3
        assert signal.donnees["par_type"] == {"arrosage": 1, "recolte": 2}
        assert signal.donnees["recoltes"] == [{"culture": "tomate", "quantite": 3.5, "unite": "kg"}]

    def test_semaine_vide_pas_de_bilan(self):
        assert veilleur.detecter_bilan_semaine(_etat()) == []

    def test_le_bilan_n_est_pas_dans_le_passage_horaire(self):
        assert veilleur.detecter_bilan_semaine not in veilleur.DETECTEURS_HORAIRES
        assert veilleur.DETECTEURS_HEBDOMADAIRES == (veilleur.detecter_bilan_semaine,)


def test_ca2_tous_les_detecteurs_sont_livres():
    noms = {d.__name__ for d in veilleur.DETECTEURS_HORAIRES + veilleur.DETECTEURS_HEBDOMADAIRES}
    assert noms == {
        "detecter_gel_canicule", "detecter_pluie_secheresse", "detecter_echeances_lots",
        "detecter_recolte_imminente", "detecter_levee_non_notee", "detecter_fenetres_semis",
        "detecter_rappels_echus",
        "detecter_bilan_semaine",
    }


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — `_alerte_recolte` déplacée dans un service
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4AlerteRecolte:
    def test_le_bot_lit_la_regle_du_service(self):
        import app.bot as bot
        assert bot._alerte_recolte is svc_alerte_recolte.alerte_recolte
        assert bot.SEUIL_ALERTE is svc_alerte_recolte.SEUIL_ALERTE

    def test_commandes_plan_ne_la_definit_plus(self):
        arbre = ast.parse((RACINE / "app/bot/commandes_plan.py").read_text(encoding="utf-8"))
        definies = {n.name for n in ast.walk(arbre) if isinstance(n, ast.FunctionDef)}
        affectees = {t.id for n in ast.walk(arbre) if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
        assert "_alerte_recolte" not in definies
        assert "SEUIL_ALERTE" not in affectees

    @pytest.mark.parametrize("organe, age, attendu", [
        ("végétatif", 44, False), ("végétatif", 45, True), ("reproducteur", 89, False),
        ("reproducteur", 90, True), (None, 200, False), ("racine", 500, False),
    ])
    def test_comportement_inchange(self, organe, age, attendu):
        assert svc_alerte_recolte.alerte_recolte(organe, age) is attendu


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — R7 : le veilleur ne parle jamais au modèle (test d'AST)
# ═════════════════════════════════════════════════════════════════════════════
def _modules_importes(arbre: ast.AST) -> list[str]:
    modules: list[str] = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            modules.extend(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            modules.append(noeud.module)
            modules.extend(f"{noeud.module}.{alias.name}" for alias in noeud.names)
    return modules


def test_ca6_aucun_module_du_veilleur_n_importe_llm():
    fichiers = sorted((RACINE / "app/services/compagnon").glob("veilleur*.py"))
    assert {f.name for f in fichiers} >= {"veilleur.py", "veilleur_passage.py"}
    for fichier in fichiers:
        modules = _modules_importes(ast.parse(fichier.read_text(encoding="utf-8")))
        fautifs = [m for m in modules if m == "llm" or m.startswith("llm.") or m.startswith("app.services.agent")]
        assert not fautifs, f"{fichier.name} importe {fautifs} (R7)"


# ═════════════════════════════════════════════════════════════════════════════
# Le passage en base : CA3 (dédoublonnage), CA5 (potager par potager), CA8
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def base(monkeypatch):
    """Une base SQLite partagée par toutes les sessions du test ; rend la fabrique."""
    import database.models  # noqa: F401
    moteur = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=moteur)
    fabrique = sessionmaker(bind=moteur, autocommit=False, autoflush=False)
    monkeypatch.setattr(svc_signaux, "SessionLocal", fabrique)
    monkeypatch.setattr(passage, "SessionLocal", fabrique)
    yield fabrique
    moteur.dispose()


def _meteo(jour_gel: date, temp_min: float = -2.0) -> dict:
    aujourd_hui = jour_gel - timedelta(days=1)
    return {
        "date": aujourd_hui.isoformat(), "temp_min": 4.0, "temp_max": 12.0, "precipitations": 0.0,
        "previsions_etendues": [
            {"date": jour_gel.isoformat(), "temp_min": temp_min, "temp_max": 8.0, "precipitations": 0.0,
             "horizon_jours": 1},
        ],
    }


@pytest.fixture
def meteo(monkeypatch):
    """Les prévisions de chaque potager : -2 °C demain partout, sauf réglage du test."""
    lectures: dict[int, dict] = {}

    def _lire(potagers, maintenant=None):
        return {
            p.id: svc_previsions.LecturePrevision(
                statut=svc_previsions.STATUT_DISPONIBLE,
                meteo=lectures.get(p.id) or _meteo(date.today() + timedelta(days=1)),
            )
            for p in potagers
        }

    monkeypatch.setattr(passage.svc_previsions, "lire_previsions_potagers", _lire)
    return lectures


def _jardin(db, potager_id: int, *, etat: str = "actif", parcelle: str = "Planche Est",
            culture: str = "laitue", nb: float = 6.0) -> Parcelle:
    db.add(Potager(id=potager_id, nom=f"Jardin {potager_id}", proprietaire_id=1, etat=etat,
                   latitude=47.2, longitude=-1.55, zone_climatique="oceanique"))
    db.flush()
    lieu = Parcelle(nom=parcelle, nom_normalise=parcelle.lower().replace(" ", ""), potager_id=potager_id,
                    ordre=1, actif=True)
    db.add(lieu)
    db.flush()
    db.add(Evenement(
        type_action="plantation", culture=culture, quantite=nb, unite="plants", rang=1,
        parcelle_id=lieu.id, potager_id=potager_id, date=datetime.now() - timedelta(days=7),
        type_organe_recolte="végétatif",
    ))
    db.commit()
    return lieu


def _laitue_au_referentiel(db, rusticite: float = -1.0, potager_id=None) -> None:
    db.add(CultureConfig(nom="laitue" if potager_id is None else f"laitue-{potager_id}",
                         type_organe_recolte="végétatif", rusticite_min_c=rusticite, potager_id=potager_id))
    db.commit()


class TestGherkin:
    """Given -2 °C demain à l'aube, 6 laitues sur la planche Est → un signal, pas de doublon, pas d'envoi."""

    def test_scenario(self, base, meteo):
        with base() as db:
            planche = _jardin(db, 1)
            _laitue_au_referentiel(db)
            planche_id = planche.id
        demain = date.today() + timedelta(days=1)

        premier = passage.passer()
        cle = f"gel:{demain.isoformat()}:parcelle-{planche_id}"
        assert premier == {1: [cle]}

        second = passage.passer()
        assert second == {1: []}

        [signal] = svc_signaux.lister(1)
        assert (signal.theme, signal.cle_unique, signal.priorite) == ("meteo", cle, "immediat")
        assert signal.etat == svc_signaux.ETAT_DETECTE   # rien n'est envoyé
        assert signal.donnees["cultures"][0]["nb_plants"] == 6.0
        assert signal.donnees["parcelle"] == "Planche Est"

    def test_aucun_message_n_est_envoye(self, base, meteo):
        """Le passage ne connaît pas Telegram : aucun module du veilleur ne l'importe."""
        for fichier in (RACINE / "app/services/compagnon").glob("veilleur*.py"):
            modules = _modules_importes(ast.parse(fichier.read_text(encoding="utf-8")))
            assert not [m for m in modules if m.startswith(("telegram", "app.bot", "app.services.relances_file"))]


class TestCA3Dedoublonnage:
    def test_meme_cle_un_seul_signal(self, base):
        with base() as db:
            db.add(Potager(id=1, nom="J", proprietaire_id=1))
            db.commit()
        signal = Signal("meteo", "gel:2026-10-28:parcelle-12", "immediat", MAINTENANT)
        assert svc_signaux.enregistrer(1, [signal, signal], MAINTENANT) == ["gel:2026-10-28:parcelle-12"]
        # Les données ont changé (−3 °C au lieu de −2 °C) : c'est le même fait.
        autre = Signal("meteo", "gel:2026-10-28:parcelle-12", "immediat", MAINTENANT, {"temp_min": -3})
        assert svc_signaux.enregistrer(1, [autre], MAINTENANT) == []
        assert len(svc_signaux.lister(1)) == 1

    def test_la_meme_cle_dans_deux_potagers_fait_deux_signaux(self, base):
        with base() as db:
            db.add_all([Potager(id=1, nom="A", proprietaire_id=1), Potager(id=2, nom="B", proprietaire_id=1)])
            db.commit()
        signal = Signal("suggestions", "semis:2026-10", "resume", MAINTENANT)
        assert svc_signaux.enregistrer(1, [signal], MAINTENANT) == ["semis:2026-10"]
        assert svc_signaux.enregistrer(2, [signal], MAINTENANT) == ["semis:2026-10"]

    def test_la_contrainte_unique_tient_si_deux_passages_se_croisent(self, base):
        """La lecture préalable a manqué l'autre passage : la contrainte rattrape, un par un."""
        with base() as db:
            db.add(Potager(id=1, nom="J", proprietaire_id=1))
            db.add(SignalVeilleur(potager_id=1, theme="meteo", cle_unique="a", priorite="normal",
                                  expire_le=MAINTENANT, detecte_le=MAINTENANT))
            db.commit()
        signaux = [Signal("meteo", "a", "normal", MAINTENANT), Signal("meteo", "b", "normal", MAINTENANT)]
        original = svc_signaux.SessionLocal

        class _Aveugle:
            """Une session dont la lecture des clés existantes ne voit rien."""
            def __init__(self):
                self._db = original()

            def query(self, *args):
                requete = self._db.query(*args)
                if args and args[0] is SignalVeilleur.cle_unique:
                    return requete.filter(SignalVeilleur.id < 0)
                return requete

            def __getattr__(self, nom):
                return getattr(self._db, nom)

        with patch.object(svc_signaux, "SessionLocal", _Aveugle):
            assert svc_signaux.enregistrer(1, signaux, MAINTENANT) == ["b"]
        assert sorted(s.cle_unique for s in svc_signaux.lister(1)) == ["a", "b"]


class TestCA5PotagerParPotager:
    def test_chaque_potager_est_lu_sous_son_propre_tenant(self, base, meteo, monkeypatch):
        with base() as db:
            _jardin(db, 1)
            _jardin(db, 2, parcelle="Carré", culture="tomate")
            _laitue_au_referentiel(db)
        armes: list = []
        fabrique = passage.SessionLocal

        def _espion():
            armes.append(module_db.current_potager_id.get())
            return fabrique()

        monkeypatch.setattr(passage, "SessionLocal", _espion)
        passage.passer()
        assert armes == [None, 1, 2]   # la liste des potagers, puis chacun sous son tenant

    def test_aucune_fuite_entre_potagers(self, base, meteo):
        """Le gel menace les laitues du potager 1 ; le potager 2 (des tomates sans rusticité) n'a rien."""
        with base() as db:
            _jardin(db, 1)
            _jardin(db, 2, parcelle="Carré", culture="tomate")
            _laitue_au_referentiel(db)
        resultats = passage.passer()
        assert len(resultats[1]) == 1 and resultats[2] == []
        assert svc_signaux.lister(2) == []

    def test_la_fiche_locale_d_un_autre_potager_ne_sert_pas(self, base, meteo):
        """Une rusticité propre au potager 2 n'expose jamais les cultures du potager 1."""
        with base() as db:
            _jardin(db, 1, culture="radis")
            _jardin(db, 2, culture="tomate")
            db.add(CultureConfig(nom="radis", type_organe_recolte="végétatif", rusticite_min_c=None))
            db.add(CultureConfig(nom="radis-du-voisin", type_organe_recolte="végétatif",
                                 rusticite_min_c=5.0, potager_id=2))
            db.commit()
            rusticites = passage._rusticites(db, 1)
        assert "radis-du-voisin" not in rusticites

    def test_un_potager_archive_ou_supprime_n_est_pas_veille(self, base, meteo):
        with base() as db:
            _jardin(db, 1)
            _jardin(db, 2, etat="archive", parcelle="B")
            db.add(Potager(id=3, nom="Supprimé", proprietaire_id=1, supprime_le=datetime.now()))
            db.commit()
        assert [p.id for p in passage.potagers_a_veiller()] == [1]

    def test_un_potager_en_echec_ne_prive_pas_les_suivants(self, base, meteo, monkeypatch):
        with base() as db:
            _jardin(db, 1)
            _jardin(db, 2, parcelle="Carré")
            _laitue_au_referentiel(db)
        vrai = passage.lire_etat

        def _lire(db, potager, *args):
            if potager.id == 1:
                raise RuntimeError("base indisponible")
            return vrai(db, potager, *args)

        monkeypatch.setattr(passage, "lire_etat", _lire)
        resultats = passage.passer()
        assert 1 not in resultats and len(resultats[2]) == 1

    def test_sans_meteo_les_autres_detecteurs_passent(self, base, monkeypatch):
        with base() as db:
            _jardin(db, 1)

        def _panne(potagers, maintenant=None):
            raise ConnectionError("Open-Meteo injoignable")

        monkeypatch.setattr(passage.svc_previsions, "lire_previsions_potagers", _panne)
        assert passage.passer() == {1: []}

    def test_le_bilan_ne_lit_pas_la_meteo(self, base, monkeypatch):
        with base() as db:
            _jardin(db, 1)
            db.add(Evenement(type_action="arrosage", potager_id=1, date=datetime.now() - timedelta(hours=1)))
            db.commit()
        appel = []
        monkeypatch.setattr(passage.svc_previsions, "lire_previsions_potagers", lambda *a, **k: appel.append(1))
        resultats = passage.passer(veilleur.DETECTEURS_HEBDOMADAIRES, avec_meteo=False)
        assert appel == []
        annee, semaine, _ = date.today().isocalendar()
        assert resultats == {1: [f"bilan:{annee}-S{semaine:02d}"]}


class TestCA8LecturesDuReferentiel:
    @pytest.fixture
    def calendrier(self, base):
        with base() as db:
            _jardin(db, 1, culture="tomate")
            db.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0",
                                     attribution="Valeurs de test", partageable=True, importee=True))
            fiche = CultureConfig(nom="tomate", type_organe_recolte="reproducteur", rusticite_min_c=2.0)
            db.add(fiche)
            db.flush()
            it = ItineraireCultural(culture_id=fiche.id, nom="standard",
                                    nom_normalise=cal.normaliser_itineraire("standard"), source_id=1)
            db.add(it)
            db.flush()
            db.add(DureeCulturale(itineraire_id=it.id, etape=cal.ETAPE_LEVEE, jours_min=6, jours_max=10, source_id=1))
            db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="oceanique",
                                    phase=cal.PHASE_SEMIS_PEPINIERE, mois_debut=2, mois_fin=4, source_id=1))
            db.commit()
        return base

    def test_rusticite_de_la_fiche(self, calendrier):
        with calendrier() as db:
            [culture] = passage.cultures_en_place(db, 1)
        assert culture.culture == "tomate" and culture.rusticite_min_c == 2.0
        assert culture.parcelle_nom == "Planche Est"

    def test_duree_de_levee_du_calendrier(self, calendrier):
        with calendrier() as db:
            assert passage._duree_levee_max(db, "tomate", 1, {}) == 10
            assert passage._duree_levee_max(db, "inconnue", 1, {}) is None

    def test_fenetres_de_la_zone_et_cultures_deja_cultivees(self, calendrier):
        with calendrier() as db:
            [fenetre] = passage.fenetres_de_semis(db, 1)
        assert (fenetre.culture, fenetre.phase, fenetre.mois_debut, fenetre.mois_fin) == (
            "tomate", cal.PHASE_SEMIS_PEPINIERE, 2, 4,
        )
        assert fenetre.deja_cultivee is True

    def test_levee_non_notee_de_bout_en_bout(self, calendrier, meteo):
        """Un semis de tomates en pépinière il y a 15 jours, levée attendue sous 10 jours, rien noté."""
        with calendrier() as db:
            serre = Parcelle(nom="Serre", nom_normalise="serre", potager_id=1, ordre=2, actif=True,
                             est_pepiniere=True)
            db.add(serre)
            db.flush()
            db.add(Evenement(type_action="semis", culture="tomate", quantite=24, unite="graines",
                             parcelle_id=serre.id, potager_id=1, contexte_semis="pepiniere",
                             date=datetime.now() - timedelta(days=15)))
            db.commit()
            [lot] = passage.lots_de_pepiniere(db, passage.TenantContext(user_id=None, potager_id=1), date.today())
        assert lot.duree_levee_max_jours == 10 and lot.levee_notee is False and lot.graines_en_attente == 24
        resultats = passage.passer()
        assert [c for c in resultats[1] if c.startswith("levee:")] == [f"levee:{veilleur._cle_lot(lot)}"]

    def test_journal_sans_la_meteo_automatique(self, base):
        with base() as db:
            _jardin(db, 1)
            db.add(Evenement(type_action="observation", texte_original="[AUTO-METEO]", potager_id=1,
                             date=datetime.now()))
            db.add(Evenement(type_action="arrosage", potager_id=2, date=datetime.now()))
            db.commit()
            journal = passage.journal_recent(db, 1, date.today() - timedelta(days=14))
        assert [g.type_action for g in journal] == ["plantation"]


def test_jours_prevus_aujourd_hui_puis_les_jours_suivants():
    lecture = svc_previsions.LecturePrevision(statut=svc_previsions.STATUT_DISPONIBLE, meteo=_meteo(DEMAIN, -3.5))
    jours = passage.jours_prevus(lecture)
    assert jours[0] == JourPrevu(AUJOURD_HUI, temp_min=4.0, temp_max=12.0, precipitations=0.0)
    assert jours[1] == JourPrevu(DEMAIN, temp_min=-3.5, temp_max=8.0, precipitations=0.0)
    assert passage.jours_prevus(svc_previsions.LecturePrevision(statut=svc_previsions.STATUT_INDISPONIBLE)) == ()
    assert passage.jours_prevus(None) == ()


def test_les_previsions_portent_le_cumul_de_pluie_du_jour():
    from utils import meteo as utils_meteo
    brut = {
        "daily": {
            "time": ["2026-10-27", "2026-10-28"], "weathercode": [3, 61],
            "temperature_2m_max": [12.0, 9.0], "temperature_2m_min": [4.0, 1.0],
            "precipitation_sum": [0.0, 23.4], "precipitation_probability_max": [10, 90],
            "windspeed_10m_max": [10.0, 20.0], "sunrise": ["2026-10-27T08:20"] * 2,
            "sunset": ["2026-10-27T18:30"] * 2,
        },
        "hourly": {"time": [], "temperature_2m": [], "precipitation_probability": []},
    }
    meteo = utils_meteo._analyser_prevision(brut)
    assert meteo["previsions_etendues"][0]["precipitations"] == 23.4


# ═════════════════════════════════════════════════════════════════════════════
# Purge à 30 jours
# ═════════════════════════════════════════════════════════════════════════════
def test_purge_a_trente_jours(base):
    ancien = MAINTENANT - timedelta(days=31)
    with base() as db:
        db.add(Potager(id=1, nom="J", proprietaire_id=1))
        db.add_all([
            SignalVeilleur(potager_id=1, theme="meteo", cle_unique="vieux", priorite="normal",
                           expire_le=ancien, detecte_le=ancien),
            SignalVeilleur(potager_id=1, theme="meteo", cle_unique="recent", priorite="normal",
                           expire_le=MAINTENANT, detecte_le=MAINTENANT - timedelta(days=2)),
            Rappel(user_id=1, potager_id=1, objet="échu", echeance_le=ancien, etat="echu"),
            Rappel(user_id=1, potager_id=1, objet="toujours programmé", echeance_le=ancien, etat="programme"),
        ])
        db.commit()
    assert svc_signaux.purger(MAINTENANT) == 2
    assert [s.cle_unique for s in svc_signaux.lister(1)] == ["recent"]
    with base() as db:
        assert [r.objet for r in db.query(Rappel).all()] == ["toujours programmé"]


def test_le_job_de_purge_efface_les_signaux():
    source = (RACINE / "app/bot/meteo_jobs.py").read_text(encoding="utf-8")
    assert "svc_signaux.purger()" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA7 — La planification du bot
# ═════════════════════════════════════════════════════════════════════════════
def test_ca5_job_horaire_et_bilan_du_dimanche():
    from app.bot.application import _construire_application
    app = _construire_application()
    jobs = {job.name: job for job in app.job_queue.jobs()}
    assert "veilleur" in jobs and "veilleur_bilan_semaine" in jobs
    # [CA7] La file de gestes n'a plus son propre rendez-vous : elle est le thème « suivis ».
    assert "file_gestes" not in jobs
    assert jobs["veilleur"].trigger.interval == timedelta(hours=1)
    bilan = str(jobs["veilleur_bilan_semaine"].trigger)
    assert "hour='18'" in bilan and "minute='0'" in bilan and "day_of_week='sun'" in bilan


class TestCA7SuivisRattaches:
    @pytest.mark.asyncio
    async def test_le_passage_horaire_porte_la_file_de_gestes_puis_les_detecteurs(self):
        from app.bot import veilleur_jobs
        ordre: list[str] = []
        file = AsyncMock(side_effect=lambda ctx: ordre.append("file"))
        with patch.object(veilleur_jobs, "job_file_gestes", file), \
             patch.object(veilleur_jobs.svc_veilleur_passage, "passer",
                          side_effect=lambda *a: ordre.append(("passer", a))):
            await veilleur_jobs.job_veilleur(object())
        assert ordre == ["file", ("passer", (veilleur.DETECTEURS_HORAIRES,))]
        file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_une_panne_des_detecteurs_ne_retient_pas_la_file(self):
        from app.bot import veilleur_jobs
        file = AsyncMock()
        with patch.object(veilleur_jobs, "job_file_gestes", file), \
             patch.object(veilleur_jobs.svc_veilleur_passage, "passer", side_effect=RuntimeError("boum")):
            await veilleur_jobs.job_veilleur(object())   # ne lève pas
        file.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_le_bilan_passe_les_detecteurs_hebdomadaires_sans_meteo(self):
        from app.bot import veilleur_jobs
        with patch.object(veilleur_jobs.svc_veilleur_passage, "passer") as passer:
            await veilleur_jobs.job_bilan_semaine(object())
        passer.assert_called_once_with(veilleur.DETECTEURS_HEBDOMADAIRES, None, False)

    def test_la_file_garde_son_propre_job_inchange(self):
        """Le comportement de la file vit toujours dans `job_file_gestes` : rien n'y a été déplacé."""
        from app.bot import file_gestes
        source = (RACINE / "app/bot/file_gestes.py").read_text(encoding="utf-8")
        assert "async def job_file_gestes" in source
        assert "svc_relances.relancer" in source and "svc_relances.avertir" in source
        assert callable(file_gestes.job_file_gestes)
