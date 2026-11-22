"""
tests/test_us351_lectures_ecrans.py — Trois lectures que la PWA sait déjà, dans le registre [US-351]
====================================================================================================
Voisinages d'une culture = ceux de la fiche culture (CA1) ; ce qui se sème ce mois-ci = la rubrique « Le bon
moment pour semer » de l'onglet Parcours, miroir novembre / mai (CA2) ; ville, zone, abris et pépinières du
potager, ville absente avec son réglage (CA3) ; les trois au registre, lecture seule, visibles des deux clients
(CA4) ; le réglage de la ville dans le guide et le corpus (CA5).

Aucun appel réseau, aucun modèle : base SQLite des tests d'US-290, météo absente.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from app.services.capacites import potager_ecrans as cap
from app.services.capacites import registre
from database.models import AssociationCulture, CultureConfig, FamilleBotanique, Parcelle, Potager
from tests.test_us290_serveur_mcp import (  # noqa: F401 — fixtures et aides partagées
    _appeler, _connecter, _rpc, client, fabrique, jardin,
)
from tests.test_us339_situation_culture import (  # noqa: F401 — même référentiel, même météo absente
    _culture, _ctx, referentiel, sans_meteo,
)

RACINE = Path(__file__).resolve().parents[1]
LECTURES_351 = ("voisinages_culture", "que_semer_ce_mois", "voir_mon_potager")


def _lire(fabrique, jardin, nom: str, arguments: dict | None = None) -> dict:
    with fabrique() as db:
        return registre.appeler(db, _ctx(fabrique, jardin), nom, arguments or {})


@pytest.fixture
def voisinages(fabrique, referentiel):
    """Tomate : poivron et basilic favorables, chou à éviter, famille des Brassicacées à éviter."""
    with fabrique() as db:
        ids = {c.nom: c.id for c in db.query(CultureConfig).all()}
        for nom in ("poivron", "basilic", "chou"):
            db.add(CultureConfig(nom=nom, type_organe_recolte="reproducteur"))
        brassicacees = FamilleBotanique(nom="Brassicacées", nom_normalise="brassicacees")
        db.add(brassicacees)
        db.flush()
        ids = {c.nom: c.id for c in db.query(CultureConfig).all()}
        for autre, nature, niveau in (("poivron", "favorable", "etabli"), ("basilic", "favorable", "traditionnel"),
                                      ("chou", "defavorable", "etabli")):
            db.add(AssociationCulture(culture_a_id=ids["tomate"], culture_b_id=ids[autre], nature=nature,
                                      motif="test", niveau_preuve=niveau, source_id=1))
        db.add(AssociationCulture(culture_a_id=ids["tomate"], famille_b_id=brassicacees.id, nature="defavorable",
                                  motif="test", niveau_preuve="etabli", source_id=1))
        db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Les voisinages de la fiche culture
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Voisinages:

    def test_us351_gherkin_tomate_deux_listes_sans_culture_absente(self, client, fabrique, jardin, voisinages):
        d = _lire(fabrique, jardin, "voisinages_culture", {"culture": "tomates"})
        noms = lambda cle: [v["nom"] for v in d[cle]]  # noqa: E731
        assert sorted(noms("favorables")) == ["basilic", "poivron"] and noms("a_eviter") == ["chou"]
        assert noms("familles_a_eviter") == ["Brassicacées"] and noms("familles_favorables") == []
        tout = str(d).lower()
        assert "pomme de terre" not in tout and "aubergine" not in tout
        assert d["culture"] == "tomate" and d["culture_dite"] == "tomates" and "Ne cite que" in d["consigne"]

    def test_us351_memes_listes_que_la_fiche_culture(self, client, fabrique, jardin, voisinages):
        from app.api import main

        fiche = main.get_fiche_culture(culture="tomate", date_cible=None, potager_id=None, ctx=_ctx(fabrique, jardin))
        d = _lire(fabrique, jardin, "voisinages_culture", {"culture": "tomate"})
        de_la_fiche = {(a["autre_partie"], a["nature"], a["autre_est_famille"]) for a in fiche["associations"]}
        du_compagnon = {(v["nom"], "favorable" if "favorables" in cle else "defavorable", cle.startswith("familles"))
                        for cle in ("favorables", "a_eviter", "familles_favorables", "familles_a_eviter")
                        for v in d[cle]}
        assert du_compagnon == de_la_fiche

    def test_us351_preuve_dite(self, client, fabrique, jardin, voisinages):
        d = _lire(fabrique, jardin, "voisinages_culture", {"culture": "tomate"})
        assert {v["nom"]: v["preuve"] for v in d["favorables"]} == {
            "poivron": "établie", "basilic": "pratique traditionnelle"}

    def test_us351_sans_association_connue_le_dit(self, client, fabrique, jardin, referentiel):
        d = _lire(fabrique, jardin, "voisinages_culture", {"culture": "salade"})
        assert d["favorables"] == [] and d["a_eviter"] == [] and "Aucune association connue" in d["texte"]

    def test_us351_culture_inconnue_et_refus(self, client, fabrique, jardin, referentiel):
        assert _lire(fabrique, jardin, "voisinages_culture", {"culture": "zorglub"})["culture_connue"] is False
        with pytest.raises(registre.RefusCapacite):
            _lire(fabrique, jardin, "voisinages_culture", {})


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Le bon moment pour semer, par le calcul de l'onglet Parcours
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2SemisDuMois:

    def test_us351_miroir_novembre_mai(self, client, fabrique, jardin, referentiel):
        """Salade en pépinière : février-mars ; tomate : février-avril. En novembre, rien ; en mars, les deux."""
        novembre = _lire(fabrique, jardin, "que_semer_ce_mois", {"date": "2025-11-15"})
        assert novembre["a_semer"] == [] and novembre["a_semer_sans_graines"] == []
        assert novembre["texte"].startswith("Aucun semis ce mois-ci") and novembre["mois"] == "novembre"
        mars = _lire(fabrique, jardin, "que_semer_ce_mois", {"date": "2026-03-10"})
        semables = {c["culture"] for c in mars["a_semer"]} | set(mars["a_semer_sans_graines"])
        assert {"salade", "tomate"} <= semables and "Aucun semis" not in mars["texte"]

    def test_us351_meme_calcul_que_la_pepiniere(self, client, fabrique, jardin, referentiel):
        from app.api import main

        parcours = main.get_pepiniere_lots(date_ref=date(2026, 3, 10), potager_id=None,
                                           ctx=_ctx(fabrique, jardin))["parcours"]
        d = _lire(fabrique, jardin, "que_semer_ce_mois", {"date": "2026-03-10"})
        assert [c["culture"] for c in d["a_semer"]] == [c["culture"] for c in parcours["a_semer"]]
        assert d["a_semer_sans_graines"] == [c["culture"] for c in parcours["a_semer_sans_graines"]]

    def test_us351_prochaine_ouverture_mois_vide(self):
        parcours = {"a_semer": [], "a_semer_sans_graines": [], "calendrier_semis": {
            "zone": "Océanique", "prochaine_ouverture": {"date": "2027-02-01", "jours": 72},
            "mois": [{"mois": "2026-11", "s_ouvrent": []}, {"mois": "2026-12", "s_ouvrent": []},
                     {"mois": "2027-01", "s_ouvrent": []}, {"mois": "2027-02", "s_ouvrent": ["salade", "tomate"]}]}}
        d = cap.bon_moment_pour_semer(parcours, date(2026, 11, 20))
        assert d["prochaine_ouverture"] == {"mois": "février", "date": "2027-02-01", "cultures": ["salade", "tomate"]}
        assert d["texte"] == "Aucun semis ce mois-ci. Prochaine ouverture : février (salade, tomate)."

    def test_us351_sans_graines_dit(self):
        d = cap.bon_moment_pour_semer({"a_semer": [{"culture": "radis", "fenetre": "mars à mai",
                                                    "varietes_en_stock": [{"variete": "18 jours"}]}],
                                       "a_semer_sans_graines": [{"culture": "salade"}]}, date(2026, 3, 1))
        assert d["a_semer"][0]["varietes_en_stock"] == ["18 jours"]
        assert d["texte"] == "À semer en pépinière ce mois-ci : radis, salade. Sans graines en stock : salade."

    def test_us351_date_future_ramenee_a_aujourd_hui(self, client, fabrique, jardin, referentiel):
        d = _lire(fabrique, jardin, "que_semer_ce_mois", {"date": "2099-05-01"})
        assert d["date"] == date.today().isoformat() and "ramenée" in d["note"]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Ville, zone, abris et pépinières du potager
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Potager:

    def test_us351_gherkin_sans_serre_ni_ville(self, client, fabrique, jardin, referentiel):
        d = _lire(fabrique, jardin, "voir_mon_potager")
        assert d["ville"] is None and "propose de la régler" in d["ville_absente"]
        assert d["reglage_ville"] == cap.REGLAGE_VILLE and "Paramètres du potager" in d["reglage_ville"]
        assert d["serre_declaree"] is False and d["abris"] == [] and d["pepinieres"] == []
        assert d["parcelles"] == ["planche légumes"] and "Aucun abri" in d["texte"]
        assert "Océanique" in d["zone_climatique"] or "océanique" in d["zone_climatique"].lower()

    def test_us351_serre_pepiniere_chaude_et_ville(self, client, fabrique, jardin, referentiel):
        with fabrique() as db:
            db.get(Potager, jardin["mesanges"]).ville = "Ma commune"
            planche = db.query(Parcelle).filter(Parcelle.nom == "planche légumes").one()
            planche.abri = "serre"
            db.add(Parcelle(nom="semis", nom_normalise="semis", potager_id=jardin["mesanges"], est_pepiniere=True,
                            type_pepiniere="chaude"))
            db.commit()
        d = _lire(fabrique, jardin, "voir_mon_potager")
        assert d["ville"] == "Ma commune" and "ville_absente" not in d and "reglage_ville" not in d
        assert d["abris"] == [{"parcelle": "planche légumes", "abri": "serre"}] and d["serre_declaree"] is True
        assert d["pepinieres"] == [{"parcelle": "semis", "type": "chaude"}] and d["pepiniere_chaude_declaree"]
        assert d["parcelles"] == ["planche légumes"] and "texte" not in d

    def test_us351_aucune_ville_en_exemple_dans_une_description(self):
        """[CA3] « Lyon » cité pour un potager sans ville (B05) : aucune description de capacité ne nomme une ville."""
        villes = re.compile(r"\b(Lyon|Paris|Nantes|Marseille|Lille|Bordeaux|Toulouse|Rennes|Strasbourg|Nice)\b")
        for c in registre.lister():
            assert not villes.search(c.description), c.nom
            assert not villes.search(str(c.schema_entree())), c.nom


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Au registre, lecture seule, visibles des deux clients
# ═════════════════════════════════════════════════════════════════════════════
def test_us351_lectures_au_registre_et_au_mcp(client, fabrique, jardin, referentiel):
    for nom in LECTURES_351:
        assert registre.REGISTRE[nom].ecriture is False, nom
    jeton = _connecter(client, jardin)["access_token"]
    outils = {o["name"]: o for o in _rpc(client, jeton, "tools/list").json()["result"]["tools"]}
    assert set(LECTURES_351) <= set(outils)
    assert all(outils[n]["annotations"]["readOnlyHint"] is True for n in LECTURES_351)
    par_mcp = _appeler(client, jeton, "voir_mon_potager")["structuredContent"]
    assert par_mcp == _lire(fabrique, jardin, "voir_mon_potager")


def test_us351_sous_le_potager_du_jardinier(client, fabrique, jardin, referentiel):
    """Un jeton sur « Le Verger » ne voit pas la planche des Mésanges."""
    with fabrique() as db:
        db.add(Parcelle(nom="verger nord", nom_normalise="verger nord", potager_id=jardin["verger"]))
        db.commit()
    jeton = _connecter(client, jardin, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]
    d = _appeler(client, jeton, "voir_mon_potager", {"potager": jardin["verger"]})["structuredContent"]
    assert d["parcelles"] == ["verger nord"]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Le réglage de la ville est dit au jardinier
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("chemin", [
    "docs/MANUEL/guide assistant.md", "data/connaissance/guide user/guide assistant.md",
    "data/connaissance/doc_app/ville-du-potager.md",
])
def test_us351_guide_et_corpus_disent_ou_regler_la_ville(chemin):
    texte = (RACINE / chemin).read_text(encoding="utf-8")
    assert "Paramètres du potager" in texte and "Ville" in texte and "Localiser" in texte


def test_us351_l_aide_meteo_dit_ou_regler_la_ville():
    from app.bot import aide

    assert "Paramètres du potager" in aide._HELP_METEO and "Localiser" in aide._HELP_METEO


# ═════════════════════════════════════════════════════════════════════════════
# Décisions du porteur du 22/11/2026 (mesure CA6 du 21/11) — B22-F6, B06, B01, B04
# ═════════════════════════════════════════════════════════════════════════════
class TestDecisions2211:

    def test_us351_famille_a_eviter_avec_exemples_du_referentiel(self, client, fabrique, jardin, voisinages):
        """B22-F6 : « la famille des Brassicacées » vient avec deux ou trois cultures du référentiel, jamais une
        culture déjà citée à part, jamais deux « chou », jamais la culture elle-même."""
        with fabrique() as db:
            famille = db.query(FamilleBotanique).filter_by(nom="Brassicacées").one()
            for nom in ("brocoli", "chou frisé", "navet", "radis"):
                db.add(CultureConfig(nom=nom, type_organe_recolte="vegetatif", famille_id=famille.id))
            db.query(CultureConfig).filter_by(nom="chou").update({"famille_id": famille.id})
            db.commit()
        d = _lire(fabrique, jardin, "voisinages_culture", {"culture": "tomate"})
        exemples = d["familles_a_eviter"][0]["exemples"]
        assert exemples == ["brocoli", "navet", "radis"]  # ni « chou » (déjà cité), ni « chou frisé » (même mot)

    def test_us351_une_seule_liste_quand_la_question_ne_porte_que_sur_elle(self, client, fabrique, jardin, voisinages):
        d = _lire(fabrique, jardin, "voisinages_culture", {"culture": "tomate", "sens": "a_eviter"})
        assert d["liste_demandee"] == "a_eviter" and "favorables" not in d and "familles_favorables" not in d
        assert [v["nom"] for v in d["a_eviter"]] == ["chou"] and "seulement à la liste demandée" in d["consigne"]
        tout = _lire(fabrique, jardin, "voisinages_culture", {"culture": "tomate"})
        assert "favorables" in tout and "a_eviter" in tout and "les deux listes" in tout["consigne"]

    def test_us351_semis_du_mois_recoupe_pepiniere_et_pleine_terre(self):
        pepiniere = [("oignon", 1, 2), ("tomate", 2, 4), ("salade", 2, 3)]
        pleine_terre = [("radis", 2, 5), ("carotte", 3, 6), ("mâche", 8, 10)]
        suite = cap.suite_du_calendrier(pepiniere, pleine_terre, date(2026, 11, 22))
        assert suite == [
            {"mois": "janvier", "en_pepiniere": ["oignon"], "en_pleine_terre": []},
            {"mois": "février", "en_pepiniere": ["salade", "tomate"], "en_pleine_terre": ["radis"]},
            {"mois": "mars", "en_pepiniere": [], "en_pleine_terre": ["carotte"]},
        ]
        assert cap._ouverts_ce_mois(pleine_terre, 9) == ["mâche"] and cap._ouverts_ce_mois(pleine_terre, 11) == []

    def test_us351_novembre_dit_rien_sur_les_deux_phases_puis_la_suite(self, client, fabrique, jardin, referentiel):
        d = _lire(fabrique, jardin, "que_semer_ce_mois", {"date": "2025-11-15"})
        assert d["a_semer_pleine_terre"] == []
        assert d["texte"].startswith("Aucun semis ce mois-ci, ni en pépinière ni en pleine terre.")
        assert d["suite_du_calendrier"] and d["suite_du_calendrier"][0]["mois"] == "février"
        assert "février" in d["texte"] and "habitudes" in d and "Ne propose ni rappel" in d["consigne"]

    def test_us351_habitudes_des_saisons_precedentes_seulement(self):
        evenements = [
            {"date": "2025-11-20", "culture": "ail"}, {"date": "2025-12-05", "culture": "fève"},
            {"date": "2026-01-10", "culture": "oignon"},   # janvier dernier : dans les trois mois qui viennent
            {"date": "2026-07-01", "culture": "salade"},   # hors fenêtre de mois
            {"date": "2026-11-10", "culture": "mâche"},    # ce mois-ci : ce n'est pas une habitude
            {"date": "n'importe quoi", "culture": "x"}, {"date": "2025-12-01", "culture": None},
        ]
        h = cap.habitudes_de_saison(evenements, date(2026, 11, 22))
        assert [(x["culture"], x["mois"], x["annees"]) for x in h] == [
            ("ail", "novembre", [2025]), ("fève", "décembre", [2025]), ("oignon", "janvier", [2026])]

    def test_us351_voir_mon_potager_dit_de_lire_le_plan_et_pas_la_ville_pour_la_serre(self, client, fabrique, jardin,
                                                                                    referentiel):
        d = _lire(fabrique, jardin, "voir_mon_potager")
        assert "ICI" in d["consigne"] and "ville n'a rien à voir avec la serre" in d["consigne"]
        assert "Abri" in d["reglage_abri"]
        description = registre.REGISTRE["voir_mon_potager"].description
        assert "serre" in description and "AVANT de lui demander" in description
