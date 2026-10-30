"""
tests/test_us263_croiser_donnees_meteo_connaissance.py — Croiser potager, météo et connaissance [US-263]
=======================================================================================================
Une question (ou un constat de dégât) peut s'appuyer sur le carnet, la pluie récente et le corpus
agronomique. Trois outils de LECTURE ; le texte du modèle est contrôlé par le code : chiffres lus,
source citée, ni dose ni produit, aucune écriture.

Aucun appel réseau : la passerelle, Open-Meteo et le RAG sont simulés.
"""
from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.agent import catalogue_outils, interpreteur_agent, projection, savoir
from app.services.agent.catalogue_outils import (
    OUTIL_CHERCHER_CONNAISSANCE, OUTIL_CONSULTER_DONNEES, OUTIL_METEO, OUTILS_SAVOIR,
    PROJECTION_SANS_ECRITURE,
)
from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PHRASE = "les limaces ont bouffé toutes mes salades"
SOURCE = "Limaces et escargots au potager"
METEO = {
    "jours": 3, "pluie_mm_total": 24.0,
    "par_jour": [{"date": "2026-10-27", "pluie_mm": 10.0, "temp_max": 14, "temp_min": 8}],
    "aujourdhui": {"temps": "Nuageux", "temp_min": 7.0, "temp_max": 13.0, "pluie_prevue_mm": 0.0},
}


# ═════════════════════════════════════════════════════════════════════════════
# Outillage
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture(autouse=True)
def lectures_simulees(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("Planche Sud",))
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
    monkeypatch.setattr(savoir, "_meteo_du_potager", lambda ctx, jours: dict(METEO))
    monkeypatch.setattr(savoir, "precharger", lambda ctx, releves: "")


def _reponse(texte: str = "", *appels: AppelOutil) -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT, tokens_in=900, tokens_out=50,
        latence_ms=100, appels=tuple(appels), statut=passerelle.STATUT_OK,
    )


def _appel(nom: str, ident: str = "a1", **arguments) -> AppelOutil:
    return AppelOutil(nom, arguments, id=ident)


def _passage(contenu: str = "Ramasser les limaces le soir, protéger les jeunes plants."):
    return SimpleNamespace(titre_document=SOURCE, intitule="Parades", contenu=contenu)


def _boucle(modele, phrase: str, *tours: ReponseOutils):
    modele.side_effect = list(tours)
    return interpreteur_agent.proposer(phrase, CTX, None)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Les trois outils sont au catalogue, en lecture seule
# ═════════════════════════════════════════════════════════════════════════════
class TestCatalogue:
    def test_ca1_trois_outils_de_lecture(self):
        noms = {o.nom for o in catalogue_outils.outils_savoir()}
        assert noms == {OUTIL_CONSULTER_DONNEES, OUTIL_CHERCHER_CONNAISSANCE, OUTIL_METEO}
        assert noms == set(OUTILS_SAVOIR)
        assert all(not o.ecrit and not o.detruit for o in catalogue_outils.outils_savoir())

    def test_ca1_schemas_valides(self):
        for schema in catalogue_outils.schemas_savoir():
            fonction = schema["function"]
            assert fonction["parameters"]["type"] == "object"
            assert "donnée" in fonction["description"]

    def test_ca1_la_parite_du_plafond_tient(self):
        assert catalogue_outils.controler_parite_outils() == []

    def test_ca1_offerts_a_une_question_seulement(self, modele):
        _boucle(modele, "est-ce que j'ai assez arrosé ?", _reponse("Je regarde."))
        noms = {s["function"]["name"] for s in modele.call_args.kwargs["outils"]}
        assert set(OUTILS_SAVOIR) <= noms
        modele.reset_mock()
        _boucle(modele, "crée la planche nord", _reponse("D'accord."))
        noms = {s["function"]["name"] for s in modele.call_args.kwargs["outils"]}
        assert not set(OUTILS_SAVOIR) & noms


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Un constat est une lecture : aucune écriture
# ═════════════════════════════════════════════════════════════════════════════
class TestConstat:
    @pytest.mark.parametrize("phrase", [PHRASE, "mes tomates ont du mildiou", "des pucerons sur les haricots"])
    def test_ca5_un_constat_de_probleme_ne_voit_aucune_ecriture(self, phrase):
        assert projection.projection_pour(phrase) == PROJECTION_SANS_ECRITURE

    @pytest.mark.parametrize("phrase", [
        "j'ai traité les limaces", "j'ai arrosé la planche sud", "supprime la planche sud", "crée la planche nord",
    ])
    def test_ca5_un_geste_ou_une_commande_n_est_pas_un_constat(self, phrase):
        assert not projection.est_un_constat_de_probleme(phrase)

    def test_ca5_une_ecriture_appelee_sur_un_constat_est_refusee(self, modele):
        resultat = _boucle(
            modele, PHRASE,
            _reponse("", _appel("renommer_parcelle", ancien="a", nouveau="b")),
            _reponse("Tu veux que je note les dégâts ?"),
        )
        assert resultat.proposition is None
        assert "note" in resultat.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA2, CA3, CA4 — Les outils, la boucle et le contrôle du texte
# ═════════════════════════════════════════════════════════════════════════════
class TestReponseCroisee:
    def _tours(self, texte_final: str):
        return (
            _reponse("", _appel(OUTIL_METEO, "m1", jours=3),
                     _appel(OUTIL_CHERCHER_CONNAISSANCE, "c1", question="limaces salades")),
            _reponse(texte_final),
        )

    def _connaissance(self):
        contexte = SimpleNamespace(passages=(_passage(),))
        return patch("app.services.connaissance.rechercher", return_value=contexte)

    def test_gherkin_la_reponse_cite_la_pluie_et_la_source(self, modele):
        texte = (f"Il est tombé 24.0 mm ces trois derniers jours, les limaces adorent ça. Ramasse-les le soir "
                 f"et protège les jeunes plants. ({SOURCE}) Tu veux que je note les dégâts ?")
        with self._connaissance():
            resultat = _boucle(modele, PHRASE, *self._tours(texte))
        assert resultat.proposition is None
        assert "24" in resultat.texte and SOURCE in resultat.texte
        assert resultat.outils == (OUTIL_METEO, OUTIL_CHERCHER_CONNAISSANCE)

    def test_ca2_un_chiffre_absent_des_lectures_donne_le_texte_du_code(self, modele):
        with self._connaissance():
            resultat = _boucle(modele, PHRASE, *self._tours("Il a plu 40 mm, c'est énorme."))
        assert "40" not in resultat.texte
        assert "24.0 mm" in resultat.texte

    def test_ca3_la_source_est_ajoutee_quand_le_modele_l_oublie(self, modele):
        with self._connaissance():
            resultat = _boucle(modele, PHRASE, *self._tours("Ramasse-les le soir."))
        assert f"Source : {SOURCE}" in resultat.texte

    @pytest.mark.parametrize("texte", [
        "Mets 5 g de produit par litre.", "Passe de la bouillie bordelaise.", "Diluez dans l'eau.",
    ])
    def test_ca4_aucune_dose_ni_produit(self, modele, texte):
        with self._connaissance():
            resultat = _boucle(modele, PHRASE, *self._tours(texte))
        assert not savoir.donne_une_dose_ou_un_produit(resultat.texte)
        assert "24.0 mm" in resultat.texte

    def test_ca5_aucune_ecriture_aucun_enregistrement(self, modele):
        with self._connaissance():
            resultat = _boucle(modele, PHRASE, *self._tours("Je peux noter les dégâts si tu veux, 24.0 mm."))
        assert resultat.commande is None and resultat.plan is None and resultat.aiguillage is None

    def test_un_texte_sans_outil_de_savoir_passe_tel_quel(self, modele):
        resultat = _boucle(modele, "est-ce qu'il faut espacer à 50 cm ?", _reponse("Oui, environ 50 cm."))
        assert resultat.texte == "Oui, environ 50 cm."

    def test_ca1_une_lecture_sans_texte_du_modele_se_dit_par_le_code(self, modele):
        with self._connaissance():
            resultat = _boucle(modele, PHRASE, *self._tours(""))
        assert "24.0 mm" in resultat.texte


# ═════════════════════════════════════════════════════════════════════════════
# Les outils eux-mêmes
# ═════════════════════════════════════════════════════════════════════════════
class TestOutils:
    def test_meteo_rend_la_pluie_lue(self):
        releves = savoir.Releves()
        brut = json.loads(savoir.executer(OUTIL_METEO, {"jours": 3}, CTX, releves))
        assert brut["donnees"]["pluie_mm_total"] == 24.0
        assert "24.0 mm" in releves.resumes[0]

    def test_meteo_sans_localisation_est_une_erreur_lisible(self, monkeypatch):
        monkeypatch.setattr(savoir, "_meteo_du_potager", lambda ctx, jours: None)
        releves = savoir.Releves()
        brut = json.loads(savoir.executer(OUTIL_METEO, {}, CTX, releves))
        assert brut["disponible"] is False and releves.vide

    def test_meteo_ne_leve_jamais(self, monkeypatch):
        def panne(ctx, jours):
            raise RuntimeError("réseau")
        monkeypatch.setattr(savoir, "_meteo_du_potager", panne)
        assert json.loads(savoir.executer(OUTIL_METEO, {}, CTX, savoir.Releves()))["disponible"] is False

    def test_jours_bornes(self):
        assert savoir._bornes_jours({"jours": 99}) == savoir.JOURS_METEO_MAX
        assert savoir._bornes_jours({"jours": "x"}) == savoir.JOURS_METEO_DEFAUT
        assert savoir._bornes_jours({"jours": 0}) == savoir.JOURS_METEO_DEFAUT

    def test_consulter_donnees_passe_par_la_cascade_chiffree(self):
        releves = savoir.Releves()
        with patch("app.services.questions.repondre_question_detaille", return_value=("12 tomates récoltées", True, None)):
            brut = json.loads(savoir.executer(OUTIL_CONSULTER_DONNEES, {"question": "combien de tomates ?"}, CTX, releves))
        assert brut["donnees"]["reponse"] == "12 tomates récoltées"
        assert 12.0 in savoir._nombres_de(releves.contenus[0])

    def test_consulter_donnees_sans_reponse_ne_releve_rien(self):
        releves = savoir.Releves()
        with patch("app.services.questions.repondre_question_detaille", return_value=("", False, None)):
            brut = json.loads(savoir.executer(OUTIL_CONSULTER_DONNEES, {"question": "?"}, CTX, releves))
        assert brut["disponible"] is False and releves.vide

    def test_chercher_connaissance_garde_la_source(self):
        releves = savoir.Releves()
        with patch("app.services.connaissance.rechercher", return_value=SimpleNamespace(passages=(_passage(),))):
            brut = json.loads(savoir.executer(OUTIL_CHERCHER_CONNAISSANCE, {"question": "limaces"}, CTX, releves))
        assert brut["passages"][0]["source"] == SOURCE
        assert releves.sources == [SOURCE]

    def test_chercher_connaissance_corpus_vide(self):
        releves = savoir.Releves()
        with patch("app.services.connaissance.rechercher", return_value=SimpleNamespace(passages=())):
            brut = json.loads(savoir.executer(OUTIL_CHERCHER_CONNAISSANCE, {"question": "x"}, CTX, releves))
        assert brut["disponible"] is False and releves.vide

    def test_une_question_vide_n_appelle_rien(self):
        for nom in (OUTIL_CONSULTER_DONNEES, OUTIL_CHERCHER_CONNAISSANCE):
            assert "erreur" in json.loads(savoir.executer(nom, {}, CTX, savoir.Releves()))


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Le préchargement en partie variable
# ═════════════════════════════════════════════════════════════════════════════
class TestPrechargement:
    def test_ca6_cultures_et_meteo_du_jour_en_partie_variable(self, monkeypatch, modele):
        def precharger(ctx, releves):
            releves.precharges.append('{"cultures_en_place": ["Laitue"]}')
            return '\n<situation_potager>{"cultures_en_place": ["Laitue"]}</situation_potager>\n'
        monkeypatch.setattr(savoir, "precharger", precharger)
        _boucle(modele, "où en sont mes salades ?", _reponse("Bien."))
        prompt = modele.call_args.kwargs["prompt_variable"]
        assert "<situation_potager>" in prompt and "Laitue" in prompt and "consulter_donnees" in prompt

    def test_ca6_sans_savoir_offert_la_partie_variable_est_inchangee(self, modele):
        _boucle(modele, "crée la planche nord", _reponse("D'accord."))
        assert "situation_potager" not in modele.call_args.kwargs["prompt_variable"]

    def test_ca6_precharger_ne_leve_jamais(self, monkeypatch):
        monkeypatch.undo()
        with patch("app.services.agent.savoir._meteo_du_potager", side_effect=RuntimeError):
            with patch("database.db.SessionLocal", side_effect=RuntimeError):
                assert savoir.precharger(CTX, savoir.Releves()) == ""

    def test_les_chiffres_precharges_sont_permis_sans_declencher_le_controle(self):
        releves = savoir.Releves()
        releves.precharges.append('{"meteo_du_jour": {"temp_max": 13.0}}')
        assert savoir.controler("Il fait 13 degrés, plante à 40 cm.", releves) == "Il fait 13 degrés, plante à 40 cm."
        assert savoir.nombres_inventes("Il fait 13 degrés.", releves) == []


class TestControle:
    def test_les_nombres_de_la_phrase_et_de_la_date_sont_permis(self):
        releves = savoir.Releves()
        releves.ajouter('{"donnees": 1}', resume="Un.")
        assert savoir.nombres_inventes("Le 30 octobre, tes 5 rangs.", releves, "mes 5 rangs", date(2026, 10, 30)) == []

    def test_sans_resume_le_texte_du_code_avoue_n_avoir_rien(self):
        releves = savoir.Releves()
        releves.ajouter('{"x": 1}')
        assert savoir.texte_du_code(releves) == savoir.TEXTE_SANS_DONNEE
