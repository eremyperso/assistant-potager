"""
tests/test_us340_que_faire_maintenant.py — La capacité « qu'est-ce que je fais au potager ? » [US-340]
=======================================================================================================
Les gestes du jour classés par urgence (CA1), ce qui se sème ou se plante ce mois-ci avec sa source (CA2), la même
liste que l'écran « Aujourd'hui au potager » (CA3), une récolte répétée = nouvelle cueillette (CA4), un potager neuf
qui le dit (CA5), visible du compagnon et du MCP (CA6).

Aucun appel réseau, aucun modèle : base SQLite des tests d'US-290, météo absente.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.capacites import que_faire as cap
from app.services.capacites import registre
from tests.test_us290_serveur_mcp import (  # noqa: F401 — fixtures et aides partagées
    _appeler, _connecter, _rpc, client, fabrique, jardin,
)
from tests.test_us339_situation_culture import (  # noqa: F401 — même référentiel, même météo absente
    _culture, _ctx, referentiel, sans_meteo,
)

AUJOURD_HUI = date.today()


def _lire(fabrique, jardin, arguments: dict | None = None) -> dict:
    with fabrique() as db:
        return registre.appeler(db, _ctx(fabrique, jardin), "que_faire_maintenant", arguments or {})


def _ligne(culture, etape, etape_date, **plus) -> dict:
    return {"parcelle_id": 1, "parcelle": "planche haricots", "rang": 2, "culture": culture, "variete": None,
            "etape": etape, "etape_libelle": etape.capitalize(), "etape_date": etape_date, **plus}


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Les gestes du jour, classés par urgence
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Gestes:

    def test_us340_gherkin_arrosage_du_jour_puis_cueillette_des_haricots(self):
        taches = {"a_confirmer": [_ligne("haricot", "en_recolte", AUJOURD_HUI.isoformat())], "a_liberer": [],
                  "a_placer": []}
        echeances = {"rappels": [{"objet": "arroser les haricots", "echeance": AUJOURD_HUI.isoformat()}]}
        gestes = cap.gestes_a_faire(taches, echeances, {"haricot"}, AUJOURD_HUI)
        assert [(g["origine"], g["geste"]) for g in gestes] == [
            ("rappel", "arroser les haricots"), ("a_confirmer", "nouvelle cueillette")]

    def test_us340_le_retard_passe_avant_le_jour_puis_ce_qui_attend(self):
        hier, avant = "2026-11-21", "2026-11-12"
        taches = {"a_confirmer": [_ligne("carotte", "en_recolte", hier), _ligne("radis", "en_recolte", avant)],
                  "a_liberer": [{"parcelle": "p", "culture": "pois", "fin_le": avant}],
                  "a_placer": [{"origine": "lot", "culture": "salade", "pepiniere": "serre", "quantite": 6}]}
        echeances = {"lots_a_traiter": [{"lot": 3, "culture": "tomate", "action": "repiquer"}],
                     "rappels": [{"objet": "appeler", "echeance": "2026-11-22"}]}
        gestes = cap.gestes_a_faire(taches, echeances, set(), date(2026, 11, 22))
        assert [g["urgence"] for g in gestes] == sorted(g["urgence"] for g in gestes)
        # retard de 10 jours, retard d'un jour, puis le rappel du jour
        assert [g["culture"] for g in gestes][:3] == ["radis", "carotte", None]
        assert {g["origine"] for g in gestes[3:]} == {"pepiniere", "a_placer", "a_liberer"}

    def test_us340_l_ecran_et_la_capacite_donnent_la_meme_liste(self, client, fabrique, jardin, referentiel):
        """[CA3] `aujourdhui` est `taches_du_jour` de GET /plan, tel quel : même service, même date."""
        from app.api import main

        plan = main.get_plan(date_ref=None, potager_id=None, ctx=_ctx(fabrique, jardin))
        d = _lire(fabrique, jardin)
        assert d["aujourdhui"] == plan["taches_du_jour"]
        assert d["date"] == plan["date_ref_effective"]


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Ce qui se sème ou se plante ce mois-ci, avec sa source
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2SemerOuPlanter:

    def test_us340_chaque_verdict_porte_sa_source(self):
        semis = {"a_semer": [{"culture": "tomate", "fenetre": "février à avril", "varietes_en_stock": ["cœur"]}],
                 "a_semer_sans_graines": ["salade"]}
        lignes = cap.a_semer_ou_planter(semis, [("radis", 2, 5), ("mâche", 8, 10)], [("ail", 10, 11), ("fève", 3, 4)],
                                        3, "océanique")
        assert [(l["culture"], l["geste"]) for l in lignes] == [
            ("tomate", "semer en pépinière"), ("salade", "semer en pépinière"),
            ("radis", "semer en pleine terre"), ("fève", "planter")]
        assert all(l["source"] for l in lignes)
        assert lignes[0]["graines_en_stock"] is True and lignes[1]["graines_en_stock"] is False
        assert lignes[3]["fenetre"] == "mars à avril" and "océanique" in lignes[3]["source"]

    def test_us340_le_mois_se_lit_aujourd_hui(self, client, fabrique, jardin, referentiel):
        d = _lire(fabrique, jardin)
        if AUJOURD_HUI.month in (2, 3):  # la salade se sème en pépinière de février à mars
            assert "salade" in {l["culture"] for l in d["a_semer_ou_planter_ce_mois"]}
        assert d["zone_climatique"]
        assert "Ce mois-ci" in d["texte"] or "Aucune culture à semer" in d["texte"]


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Une récolte répétée est une nouvelle cueillette
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4NouvelleCueillette:

    @pytest.mark.parametrize("etape", ["en_recolte", "terminee"])
    def test_us340_reproductive_jamais_fin_de_culture(self, etape):
        assert cap._geste_a_confirmer(_ligne("tomate", etape, "2026-11-01"), {"tomate"}) == "nouvelle cueillette"

    def test_us340_vegetative_a_une_fin(self):
        assert cap._geste_a_confirmer(_ligne("carotte", "terminee", "2026-11-01"), {"tomate"}) == \
            "fin de culture à confirmer"
        assert cap._geste_a_confirmer(_ligne("carotte", "en_recolte", "2026-11-01"), {"tomate"}) == "récolte possible"
        assert cap._geste_a_confirmer(_ligne("carotte", "levee", "2026-11-01"), set()) == "levee à confirmer"

    def test_us340_la_recolte_attendue_depassee_d_une_reproductive_est_une_cueillette(self):
        gestes = cap.gestes_a_faire({}, {"recoltes_attendues_depassees": [
            {"culture": "tomate", "parcelle_nom": "planche"}, {"culture": "radis", "parcelle_nom": "planche"}]},
            {"tomate"}, AUJOURD_HUI)
        assert sorted(g["geste"] for g in gestes) == ["nouvelle cueillette", "récolte attendue"]

    def test_us340_les_cultures_reproductives_viennent_du_referentiel(self, client, fabrique, jardin, referentiel):
        with fabrique() as db:
            reproductives = cap.cultures_reproductives(db, jardin["mesanges"])
        assert "tomate" in reproductives and "salade" not in reproductives


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Un potager neuf le dit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5PotagerNeuf:

    def test_us340_potager_neuf_ne_rend_que_les_semis_du_mois(self, client, fabrique, jardin):
        d = _lire(fabrique, jardin)
        assert d["potager_neuf"] is True and d["gestes"] == [] and d["nombre_de_gestes"] == 0
        assert "Rien n'est encore en place" in d["texte"]

    def test_us340_potager_garni_n_est_pas_neuf(self, client, fabrique, jardin, referentiel):
        d = _lire(fabrique, jardin)
        assert d["potager_neuf"] is False and "Rien n'est encore en place" not in d["texte"]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Visible du compagnon et du MCP, en lecture seule
# ═════════════════════════════════════════════════════════════════════════════
def test_us340_au_registre_en_lecture_seule_et_dans_les_lectures_du_compagnon():
    from tools.jeu_evaluation import moteurs

    assert registre.REGISTRE["que_faire_maintenant"].ecriture is False
    assert "que_faire_maintenant" in moteurs.LECTURES
    description = registre.REGISTRE["que_faire_maintenant"].description
    assert "Aujourd'hui au potager" in description and "Lecture seule" in description


def test_us340_aucune_ville_en_exemple_dans_la_description():
    description = registre.REGISTRE["que_faire_maintenant"].description.lower()
    assert not any(ville in description for ville in ("lyon", "paris", "nantes", "bordeaux"))


class TestGesteAProposer:
    """22/11 : le gestes qui confirme une étape est dit, sans quantité devinée (6 passages avaient `quantite=1`)."""

    def _gestes(self, etape: str, culture: str, reproductives: set[str]) -> list[dict]:
        return cap.gestes_a_faire({"a_confirmer": [_ligne(culture, etape, "2026-11-04")]}, {}, reproductives,
                                  date(2026, 11, 22))

    def test_us340_une_levee_se_note_en_observation_sans_quantite(self):
        (g,) = self._gestes("levee", "haricot", set())
        assert g["geste_a_proposer"] == {"type": "observation", "note": "levée constatée", "quantite": "aucune"}

    def test_us340_les_autres_etapes_demandent_la_quantite(self):
        for etape, type_geste in (("semee", "semis"), ("plantee", "plantation"), ("en_recolte", "recolte")):
            (g,) = self._gestes(etape, "carotte", set())
            assert g["geste_a_proposer"]["type"] == type_geste
            assert g["geste_a_proposer"]["quantite"] == "à demander au jardinier"

    def test_us340_la_fin_de_culture_n_a_pas_de_geste_a_proposer(self):
        (vegetative,) = self._gestes("terminee", "carotte", {"tomate"})
        assert "geste_a_proposer" not in vegetative
        (reproductive,) = self._gestes("terminee", "tomate", {"tomate"})
        assert reproductive["geste_a_proposer"]["type"] == "recolte"  # nouvelle cueillette, jamais la fin

    def test_us340_la_consigne_n_invite_pas_a_ecrire_et_interdit_de_deviner_une_quantite(self, client, fabrique,
                                                                                      jardin, referentiel):
        d = _lire(fabrique, jardin)
        assert "ne propose pas d'enregistrer" in d["consigne"] and "ne se devine pas" in d["consigne"]
