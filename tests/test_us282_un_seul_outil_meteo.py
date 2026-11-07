"""
tests/test_us282_un_seul_outil_meteo.py — Un seul outil météo pour l'agent [US-282]
===================================================================================
L'outil `meteo` prend un lieu et une période ; `afficher(commande=meteo)` sort du catalogue ;
le texte qui chiffre un lieu non lu est remplacé par celui du code. Aucun modèle, aucun réseau.
"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services.agent import catalogue_outils, savoir
from app.services.agent.catalogue_outils import OUTIL_CONSULTER, OUTIL_METEO
from app.services.context import TenantContext
from utils.geocodage import Lieu

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

LYON = Lieu("Lyon", 45.75, 4.85, "Auvergne-Rhône-Alpes", "France", "Europe/Paris", "PPLA")
BELGIQUE = Lieu("Belgique", 50.64, 4.67, None, "Belgique", "Europe/Brussels", "PCLI")
BRETAGNE = Lieu("Bretagne", 48.2, -2.9, "Bretagne", "France", "Europe/Paris", "ADM1")

PREVISION = {
    "label": "Ciel dégagé", "temp_min": 8.0, "temp_max": 19.0, "precipitations": 0.0,
    "previsions_etendues": [
        {"date": f"2026-11-0{3 + i}", "label": "Pluie légère", "temp_min": 6.0 + i, "temp_max": 12.0 + i,
         "precipitations": 1.5 + i, "horizon_jours": i + 1}
        for i in range(6)
    ],
}
HISTORIQUE = [
    {"date": "2026-10-31", "temp_max": 14.0, "temp_min": 7.0, "precipitations": 4.0},
    {"date": "2026-11-01", "temp_max": 13.0, "temp_min": 6.0, "precipitations": 6.5},
]


@pytest.fixture(autouse=True)
def _reseau_coupe(monkeypatch):
    """Le potager est à 46,0 / 2,0 ; chaque appel météo rend la même prévision. Aucun réseau."""
    monkeypatch.setattr(savoir, "_coordonnees_potager", lambda ctx: (46.0, 2.0))
    appels = []

    def prevision(lat, lon, **kw):
        appels.append((lat, lon, kw))
        return PREVISION

    monkeypatch.setattr("utils.meteo.fetch_meteo", prevision)
    monkeypatch.setattr("utils.meteo.fetch_meteo_history", lambda lat, lon, days=3, **kw: HISTORIQUE)
    return appels


def _lire(arguments: dict, releves: savoir.Releves | None = None) -> dict:
    return json.loads(savoir.executer(OUTIL_METEO, arguments, CTX, releves or savoir.Releves()))


class TestLieuDonne:
    def test_ca1_un_lieu_donne_est_geocode_et_nomme(self, _reseau_coupe):
        releves = savoir.Releves()
        with patch("utils.geocodage.chercher_lieu", return_value=[LYON]) as geocodage:
            brut = _lire({"lieu": "Lyon"}, releves)
        geocodage.assert_called_once_with("Lyon")
        assert brut["donnees"]["lieu"] == "Lyon, Auvergne-Rhône-Alpes, France"
        assert _reseau_coupe[-1][:2] == (45.75, 4.85)          # les coordonnées de Lyon, pas du potager
        assert _reseau_coupe[-1][2] == {"timezone": "Europe/Paris"}
        assert releves.lieux == ["Lyon, Auvergne-Rhône-Alpes, France"]
        assert "Lyon" in releves.resumes[0]

    def test_ca2_sans_lieu_c_est_le_potager_et_il_se_nomme(self, _reseau_coupe):
        releves = savoir.Releves()
        brut = _lire({}, releves)
        assert brut["donnees"]["lieu"] == savoir.LIEU_POTAGER
        assert _reseau_coupe[-1][:2] == (46.0, 2.0)
        assert releves.resumes[0].startswith("Pour ton potager")

    @pytest.mark.parametrize("dit", ["ici", "chez moi", "Mon potager"])
    def test_le_potager_se_dit_de_plusieurs_facons_sans_geocodage(self, dit):
        with patch("utils.geocodage.chercher_lieu") as geocodage:
            assert _lire({"lieu": dit})["donnees"]["lieu"] == savoir.LIEU_POTAGER
        geocodage.assert_not_called()


class TestPeriode:
    def test_ca1_les_derniers_jours_rendent_la_pluie_cumulee(self):
        donnees = _lire({"quand": "passe", "jours": 2})["donnees"]
        assert donnees["pluie_mm_total"] == 10.5 and donnees["jours"] == 2

    def test_ca1_demain_est_le_jour_d_horizon_1(self):
        with patch("utils.geocodage.chercher_lieu", return_value=[LYON]):
            donnees = _lire({"lieu": "Lyon", "quand": "demain"})["donnees"]
        assert donnees["demain"]["date"] == "2026-11-03" and donnees["demain"]["temp_max"] == 12.0
        assert "pluie_mm_total" not in donnees

    def test_ca1_aujourd_hui_ne_rend_pas_l_historique(self):
        donnees = _lire({"quand": "aujourdhui"})["donnees"]
        assert donnees["aujourdhui"]["temps"] == "Ciel dégagé" and "par_jour" not in donnees

    def test_ca1_la_prevision_prend_n_jours_et_cinq_par_defaut(self):
        assert len(_lire({"quand": "prevision"})["donnees"]["previsions"]) == 5
        assert len(_lire({"quand": "prevision", "jours": 2})["donnees"]["previsions"]) == 2
        assert len(_lire({"quand": "prevision", "jours": 99})["donnees"]["previsions"]) == savoir.JOURS_METEO_MAX - 1

    @pytest.mark.parametrize("dit, attendu", [
        ("demain", "demain"), ("Après-demain", "prevision"), ("les prochains jours", "prevision"),
        ("aujourd'hui", "aujourdhui"), ("hier", "passe"), ("n'importe quoi", "passe"), ("", "passe"),
    ])
    def test_quand_est_ramene_a_une_valeur_connue(self, dit, attendu):
        assert savoir._quand({"quand": dit}) == attendu

    def test_la_prevision_indisponible_est_dite_telle_quelle(self, monkeypatch):
        monkeypatch.setattr("utils.meteo.fetch_meteo", lambda *a, **kw: None)
        releves = savoir.Releves()
        assert _lire({"quand": "demain"}, releves) == {"disponible": False} and releves.vide


class TestLieuAbsent:
    @pytest.mark.parametrize("lieux, erreur", [
        ([], savoir.ERREUR_LIEU_INTROUVABLE),
        ([BELGIQUE], savoir.ERREUR_LIEU_TROP_LARGE),
        ([BRETAGNE], savoir.ERREUR_LIEU_TROP_LARGE),
    ])
    def test_ca4_lieu_introuvable_ou_trop_large_on_demande_une_ville(self, lieux, erreur, _reseau_coupe):
        releves = savoir.Releves()
        with patch("utils.geocodage.chercher_lieu", return_value=lieux):
            brut = _lire({"lieu": "la Belgique"}, releves)
        assert brut["erreur"] == erreur and brut["disponible"] is False
        assert "ville" in brut["a_faire"]
        assert releves.vide and not _reseau_coupe           # jamais la météo du potager à la place

    def test_ca4_geocodage_injoignable_n_est_pas_un_lieu_inconnu(self):
        with patch("utils.geocodage.chercher_lieu", return_value=None):
            assert _lire({"lieu": "Lyon"}) == {"disponible": False}

    def test_potager_sans_localisation_reste_une_erreur_lisible(self, monkeypatch):
        monkeypatch.setattr(savoir, "_coordonnees_potager", lambda ctx: None)
        for quand in ("passe", "demain"):
            assert "localisation" in _lire({"quand": quand})["erreur"]


class TestControleDuLieu:
    def _releves_lyon(self) -> savoir.Releves:
        releves = savoir.Releves()
        with patch("utils.geocodage.chercher_lieu", return_value=[LYON]):
            _lire({"lieu": "Lyon", "quand": "demain"}, releves)
        return releves

    def test_ca2_des_chiffres_au_lieu_lu_passent(self):
        texte = "À Lyon, demain, il fera 12.0 °C au plus avec 1.5 mm de pluie."
        assert savoir.controler(texte, self._releves_lyon()) == texte

    def test_ca2_la_region_ou_le_pays_du_lieu_lu_passent(self):
        texte = "En France, à Lyon, 12.0 °C au plus demain."
        assert savoir.controler(texte, self._releves_lyon()) == texte

    def test_ca2_des_chiffres_attribues_a_un_lieu_non_lu_donnent_le_texte_du_code(self):
        releves = self._releves_lyon()
        texte = "À Paris, demain, il fera 12.0 °C au plus."
        assert savoir.lieux_non_releves(texte, releves) == ["Paris"]
        assert savoir.controler(texte, releves) == savoir.texte_du_code(releves)
        assert "Lyon" in savoir.texte_du_code(releves)

    def test_ca2_un_lieu_non_lu_sans_chiffre_passe(self):
        texte = "Je n'ai pas la météo de Paris, mais Lyon est lue."
        assert savoir.controler(texte, self._releves_lyon()) == texte

    def test_ca2_un_mois_n_est_pas_un_lieu(self):
        texte = "Comme en Mars, 12.0 °C au plus demain à Lyon."
        assert savoir.lieux_non_releves(texte, self._releves_lyon()) == []

    def test_ca2_sans_meteo_lue_le_controle_des_lieux_ne_s_applique_pas(self):
        assert savoir.lieux_non_releves("À Paris, 12 °C.", savoir.Releves()) == []


class TestCatalogue:
    def test_ca3_afficher_n_offre_plus_la_meteo(self):
        enum = catalogue_outils.outils_par_nom()[OUTIL_CONSULTER].schema["function"]["parameters"][
            "properties"]["commande"]["enum"]
        assert "meteo" not in enum

    def test_ca3_la_parite_reste_verte_la_commande_reste_dictable(self):
        from app.services.menu_commandes import FORMES_PAR_CLE

        assert catalogue_outils.controler_parite_outils() == []
        assert ("meteo", None) in FORMES_PAR_CLE

    def test_ca1_le_schema_de_meteo_porte_lieu_quand_jours(self):
        schema = next(o.schema for o in catalogue_outils.outils_savoir() if o.nom == OUTIL_METEO)
        proprietes = schema["function"]["parameters"]["properties"]
        assert set(proprietes) == {"lieu", "quand", "jours"}
        # `_schema` rend une propriété facultative nullable : `None` s'ajoute à l'enum.
        assert [v for v in proprietes["quand"]["enum"] if v] == list(savoir.QUAND_VALEURS)
        assert not schema["function"]["parameters"].get("required")

    def test_ca5_le_prechargement_du_potager_ne_change_pas(self, monkeypatch, _reseau_coupe):
        from app.services import previsions_meteo

        previsions_meteo.vider_cache()
        groupes = []
        monkeypatch.setattr("app.services.previsions_meteo.fetch_meteo_groupe",
                            lambda localisations, tz="Europe/Paris": groupes.append(localisations) or [PREVISION])
        monkeypatch.setattr("app.services.stock.calcul_stock_cultures", lambda db, ctx: {})
        releves = savoir.Releves()
        texte = savoir.precharger(CTX, releves)
        assert '"meteo_du_jour"' in texte and '"temp_max": 19.0' in texte
        assert releves.lieux == []                             # le préchargement ne « lit » aucun lieu
        # La météo du jour vient du cache de prévisions : un seul appel réseau pour deux messages,
        # et l'historique de la veille n'est pas demandé.
        savoir.precharger(CTX, savoir.Releves())
        assert len(groupes) == 1
        assert _reseau_coupe == []                             # `fetch_meteo` direct n'est plus appelé
        previsions_meteo.vider_cache()
