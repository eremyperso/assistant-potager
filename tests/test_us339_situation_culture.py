"""
tests/test_us339_situation_culture.py — La capacité `situation_culture` : « est-ce le moment ? » [US-339]
=======================================================================================================
Le verdict de saison de la fiche culture, toutes actions confondues (CA1), calculé comme la fiche (CA2 :
jeu de cas partagé avec `frontend/src/lib/ficheCulture.test.js`), où en est la culture chez le jardinier
(CA3), ses chiffres (CA4), le geste suivant sans écriture (CA5), `voir_calendrier` aligné (CA5b), une
culture inconnue dite comme telle (CA6), visible du compagnon et du MCP (CA7).

Aucun appel réseau, aucun modèle : base SQLite des tests d'US-290, météo absente (potager non localisé).
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.services import potager_actif as svc_potager_actif
from app.services import previsions_meteo as svc_previsions
from app.services import situation_culture as svc
from app.services.capacites import registre
from app.services.capacites import situation as cap
from database.models import (
    CultureConfig, Evenement, FenetreCulturale, ItineraireCultural, Parcelle, Potager, ReferentielSource,
)
from tests.test_us290_serveur_mcp import (  # noqa: F401 — fixtures et aides partagées
    _appeler, _connecter, _rpc, client, fabrique, jardin,
)

RACINE = Path(__file__).resolve().parents[1]
CORPUS = json.loads((RACINE / "tests/corpus/parite_situation_culture.json").read_text(encoding="utf-8"))
AUJOURD_HUI = date.today()
LE_20_NOVEMBRE = date(2026, 11, 20)


# ═════════════════════════════════════════════════════════════════════════════
# Données
# ═════════════════════════════════════════════════════════════════════════════
def _culture(db, nom: str, organe: str, fenetres: dict[str, tuple[int, int]]) -> None:
    fiche = CultureConfig(nom=nom, type_organe_recolte=organe)
    db.add(fiche)
    db.flush()
    if not fenetres:
        return
    it = ItineraireCultural(culture_id=fiche.id, nom="standard", nom_normalise="standard", source_id=1)
    db.add(it)
    db.flush()
    for phase, (debut, fin) in fenetres.items():
        db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="oceanique", phase=phase,
                                mois_debut=debut, mois_fin=fin, source_id=1))


def _geste(db, potager_id, action, culture, jour, *, quantite, unite, parcelle_id=None, organe=None) -> None:
    db.add(Evenement(type_action=action, culture=culture, quantite=quantite, unite=unite,
                     date=datetime.combine(jour, datetime.min.time()), potager_id=potager_id,
                     parcelle_id=parcelle_id, type_organe_recolte=organe))


@pytest.fixture(autouse=True)
def sans_meteo(monkeypatch):
    """Potager non localisé : aucune prévision, jamais d'appel réseau (US-178 / CA5)."""
    monkeypatch.setattr(svc_previsions, "lire_prevision_potager", lambda potager: svc_previsions.LecturePrevision(
        statut=svc_previsions.STATUT_LOCALISATION_MANQUANTE, meteo=None, source=None))


@pytest.fixture
def referentiel(fabrique, jardin):
    """Zone océanique ; salade (pépinière 2-3, plantation 3-9), laitue, tomate (plantation 5-6), céleri
    sans fenêtre ; une planche, 12 tomates plantées et 3 récoltes cette saison."""
    with fabrique() as db:
        db.get(Potager, jardin["mesanges"]).zone_climatique = "oceanique"
        db.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0", attribution="Valeurs de test",
                                 partageable=True, importee=True))
        db.flush()
        _culture(db, "salade", "végétatif", {"semis_pepiniere": (2, 3), "plantation": (3, 9)})
        _culture(db, "laitue", "végétatif", {"semis_pleine_terre": (3, 8)})
        _culture(db, "tomate", "reproducteur", {"semis_pepiniere": (2, 4), "plantation": (5, 6)})
        _culture(db, "céleri", "végétatif", {})
        planche = Parcelle(nom="planche légumes", nom_normalise="planche legumes", potager_id=jardin["mesanges"],
                           superficie_m2=20)
        db.add(planche)
        db.flush()
        _geste(db, jardin["mesanges"], "plantation", "tomate", AUJOURD_HUI - timedelta(days=90), quantite=12,
               unite="plants", parcelle_id=planche.id)
        for i in range(3):
            _geste(db, jardin["mesanges"], "recolte", "tomate", AUJOURD_HUI - timedelta(days=10 - i), quantite=1.5,
                   unite="kg", parcelle_id=planche.id, organe="reproducteur")
        db.commit()
        return {"planche": planche.id}


def _ctx(fabrique, jardin):
    with fabrique() as db:
        return svc_potager_actif.contexte_sur_potager(db, jardin["user_id"], jardin["mesanges"])


def _situation(fabrique, jardin, culture: str, quand: date | None = None) -> dict:
    arguments = {"culture": culture, **({"date": quand.isoformat()} if quand else {})}
    with fabrique() as db:
        return registre.appeler(db, _ctx(fabrique, jardin), "situation_culture", arguments)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Un verdict de saison toutes actions confondues
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Verdict:

    def test_us339_gherkin_salades_en_novembre(self, client, fabrique, jardin, referentiel):
        """Le 20/11, aucune salade : pas ce mois-ci, prochaine fenêtre = celle que la fiche affiche."""
        d = _situation(fabrique, jardin, "salades", LE_20_NOVEMBRE)
        assert d["culture"] == "salade" and d["culture_dite"] == "salades"
        assert d["verdict"] == svc.VERDICT_PAS_CE_MOIS
        assert d["prochaine_fenetre"]["fenetre"] in ("février à mars", "mars à septembre")
        assert "Prochaine fenêtre" in d["texte"]
        assert {f["action"] for f in d["fenetres"]} == {"semis_pepiniere", "plantation"}
        assert d["chez_toi"]["etat"] == ["absente"]

    def test_us339_salade_n_est_pas_lue_laitue(self, client, fabrique, jardin, referentiel):
        with fabrique() as db:
            assert cap.resoudre_culture(db, jardin["mesanges"], "salade") == "salade"
            assert cap.resoudre_culture(db, jardin["mesanges"], "Salades") == "salade"
            assert cap.resoudre_culture(db, jardin["mesanges"], "tomattes") == "tomate"

    def test_us339_c_est_le_moment(self, client, fabrique, jardin, referentiel):
        """Mi-mai, la tomate a un geste ouvert. Lequel : celui que la fiche choisit (R1 compte aussi le mois
        voisin d'une fenêtre ; le meilleur score l'emporte), jamais une règle propre au compagnon."""
        d = _situation(fabrique, jardin, "tomate", date(AUJOURD_HUI.year, 5, 15))
        assert d["verdict"] == svc.VERDICT_MAINTENANT and d["geste"] in svc.LIBELLE_ACTION.values()
        assert d["texte"] == f"C'est le moment : {d['geste'].lower()} ({d['fenetre']})."

    def test_us339_connue_sans_fenetre_hors_calendrier(self, client, fabrique, jardin, referentiel):
        d = _situation(fabrique, jardin, "céleri", LE_20_NOVEMBRE)
        assert d["verdict"] == svc.VERDICT_HORS_CALENDRIER and "Hors calendrier connu" in d["texte"]

    def test_us339_sans_culture_ou_date_invalide_est_un_refus(self, client, fabrique, jardin, referentiel):
        with fabrique() as db:
            with pytest.raises(registre.RefusCapacite, match="obligatoire manquant : culture"):
                registre.appeler(db, _ctx(fabrique, jardin), "situation_culture", {})
            with pytest.raises(registre.RefusCapacite, match="date ISO"):
                registre.appeler(db, _ctx(fabrique, jardin), "situation_culture", {"culture": "salade", "date": "demain"})


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Le même choix que la fiche culture
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("cas", CORPUS["cas"], ids=[c["nom"] for c in CORPUS["cas"]])
def test_us339_parite_avec_la_section_maintenant_de_la_fiche(cas):
    """Les mêmes cas que `frontend/src/lib/ficheCulture.test.js` : même état, geste, étoiles, fenêtre."""
    m = svc.section_maintenant(cas["entree"], cas["mois"], cas["confianceLue"])
    assert {k: m.get(k) for k in cas["attendu"]} == cas["attendu"]


def test_us339_le_verdict_sort_des_lectures_de_la_fiche(client, fabrique, jardin, referentiel):
    """Même potager, même climat, même date : la capacité dit ce que la fiche composerait des deux lectures
    qu'elle charge (`/plan/confiances/candidates`, `/plan/calendriers`)."""
    from app.api import main

    ctx = _ctx(fabrique, jardin)
    confiances = main.get_confiances_candidates_plan(culture=["salade"], date_cible=LE_20_NOVEMBRE,
                                                    potager_id=None, ctx=ctx)
    calendriers = main.get_calendriers_plan(culture=["salade"], potager_id=None, date_ref=None, ctx=ctx)
    fiche = svc.section_maintenant(confiances["cultures"]["salade"], calendriers["cultures"]["salade"]["mois"])
    d = _situation(fabrique, jardin, "salade", LE_20_NOVEMBRE)
    assert fiche["etat"] == svc.ETAT_FERMEE
    assert d["prochaine_fenetre"] == {"action": fiche["action"], "geste": fiche["geste"], "fenetre": fiche["fenMois"]}


def test_us339_fenetre_lisible_et_ordre():
    assert svc.fenetre_lisible([2, 3]) == "février à mars" and svc.fenetre_lisible([5]) == "mai"
    assert svc.fenetre_lisible([]) == svc.TIRET and svc.fenetre_lisible([0, 13, True]) == svc.TIRET
    assert svc.meilleure_action([]) is None
    assert svc.LIBELLE_ACTION.keys() == set(svc.ORDRE_ACTIONS)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 / CA4 — Où en est la culture chez le jardinier, et ses chiffres
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3CA4ChezToi:

    def test_us339_tomate_en_place_et_recoltee(self, client, fabrique, jardin, referentiel):
        d = _situation(fabrique, jardin, "tomate")
        assert "en_place" in d["chez_toi"]["etat"] and "recoltee_cette_saison" in d["chez_toi"]["etat"]
        assert d["chez_toi"]["en_place"][0]["parcelle"] == "planche légumes"
        assert d["chez_toi"]["recoltes_cette_saison"] == 3

    def test_us339_reproductive_pieds_actifs_et_rendement_cumule(self, client, fabrique, jardin, referentiel):
        chiffres = _situation(fabrique, jardin, "tomate")["chiffres"]
        assert chiffres["nature"].startswith("reproductrice") and chiffres["pieds_actifs"] == 12
        assert chiffres["rendement_cumule"]["valeur"] == pytest.approx(4.5)
        assert chiffres["rendement_cumule"]["nb_recoltes"] == 3

    def test_us339_vegetative_pieds_restants(self, client, fabrique, jardin, referentiel):
        with fabrique() as db:
            _geste(db, jardin["mesanges"], "plantation", "salade", AUJOURD_HUI - timedelta(days=20), quantite=10,
                   unite="plants", parcelle_id=referentiel["planche"])
            db.commit()
        chiffres = _situation(fabrique, jardin, "salade")["chiffres"]
        assert chiffres["nature"].startswith("végétative") and chiffres["pieds_restants"] == 10
        assert "pieds_actifs" not in chiffres

    def test_us339_lot_en_pepiniere(self):
        chez_toi = cap._chez_toi(
            "salade", {"parcelles": []},
            {"lots": [{"numero": 4, "culture": "Salade", "variete": "Batavia", "action_suggeree": "mise_en_godet"},
                      {"numero": 5, "culture": "tomate"}]}, [])
        assert chez_toi["etat"] == ["en_pepiniere"] and [lot["lot"] for lot in chez_toi["lots_pepiniere"]] == [4]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Le geste suivant, jamais écrit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5GesteSuivant:
    FERME = {"verdict": svc.VERDICT_PAS_CE_MOIS,
             "prochaine_fenetre": {"geste": "Semer en pépinière", "fenetre": "février à mars"}}
    VIDE = {"etat": ["absente"], "en_place": [], "lots_pepiniere": []}

    def test_us339_absente_hors_saison(self):
        assert cap._geste_suivant(self.FERME, self.VIDE) == "semer en pépinière en février à mars"

    def test_us339_absente_en_saison(self):
        assert cap._geste_suivant({"verdict": svc.VERDICT_MAINTENANT, "geste": "Planter"}, self.VIDE) == "planter"

    def test_us339_en_recolte_puis_lot_puis_en_place(self):
        assert cap._geste_suivant(self.FERME, {**self.VIDE, "en_place": [{"etape": "en_recolte"}]}) == "récolter"
        assert cap._geste_suivant(self.FERME, {**self.VIDE, "lots_pepiniere": [
            {"lot": 4, "action_suggeree": "mise_en_godet"}]}) == "mettre en godet le lot 4"
        assert cap._geste_suivant(self.FERME, {**self.VIDE, "en_place": [{"etape": "en_place"}]}) == \
            "suivre la culture en place"
        assert cap._geste_suivant({"verdict": svc.VERDICT_HORS_CALENDRIER}, self.VIDE) == ""

    def test_us339_n_ecrit_rien(self, client, fabrique, jardin, referentiel):
        with fabrique() as db:
            avant = db.query(Evenement).count()
        d = _situation(fabrique, jardin, "salade", LE_20_NOVEMBRE)
        assert d["geste_suivant"] and "proposer_geste" in d["a_ecrire"]
        with fabrique() as db:
            assert db.query(Evenement).count() == avant
        assert registre.REGISTRE["situation_culture"].ecriture is False


# ═════════════════════════════════════════════════════════════════════════════
# CA5b — voir_calendrier aligné, schéma inchangé
# ═════════════════════════════════════════════════════════════════════════════
def test_us339_voir_calendrier_porte_le_verdict(client, fabrique, jardin, referentiel):
    jeton = _connecter(client, jardin)["access_token"]
    r = _appeler(client, jeton, "voir_calendrier", {"culture": "salade", "date": LE_20_NOVEMBRE.isoformat()})
    situation = r["structuredContent"]["situation"]
    assert situation["verdict"] == svc.VERDICT_PAS_CE_MOIS and "indetermin" not in json.dumps(situation)
    outils = {o["name"]: o for o in _rpc(client, jeton, "tools/list").json()["result"]["tools"]}
    assert {"culture", "date", "action"} <= set(outils["voir_calendrier"]["inputSchema"]["properties"])
    assert set(registre.REGISTRE["voir_calendrier"].proprietes) == {"culture", "date", "action"}


@pytest.mark.parametrize("entree, mois, attendu", [
    ({"a_calendrier": False, "actions": []}, {"plantation": [11, 12]}, svc.VERDICT_MAINTENANT),
    ({"a_calendrier": False, "actions": []}, {"plantation": [3, 4]}, svc.VERDICT_PAS_CE_MOIS),
])
def test_us339_jamais_indetermine_quand_une_fenetre_existe(entree, mois, attendu):
    assert svc.verdict(entree, mois, "ail", mois_courant=11)["verdict"] == attendu


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Culture inconnue : dite, sans verdict inventé
# ═════════════════════════════════════════════════════════════════════════════
def test_us339_culture_inconnue(client, fabrique, jardin, referentiel):
    d = _situation(fabrique, jardin, "zorglub")
    assert d["verdict"] == svc.VERDICT_INCONNUE and "pas dans le référentiel" in d["texte"]
    assert "fenetres" not in d and "prochaine_fenetre" not in d and "avertissement_donnees" in d


def test_us339_verdict_inconnu_par_les_confiances():
    assert svc.verdict({"culture_connue": False}, {}, "x")["verdict"] == svc.VERDICT_INCONNUE


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Visible du compagnon et du MCP, même réponse
# ═════════════════════════════════════════════════════════════════════════════
def test_us339_meme_reponse_par_le_mcp_et_par_le_compagnon(client, fabrique, jardin, referentiel):
    jeton = _connecter(client, jardin)["access_token"]
    noms = {o["name"] for o in _rpc(client, jeton, "tools/list").json()["result"]["tools"]}
    assert "situation_culture" in noms and "situation_culture" in {c.nom for c in registre.lister(ecriture=False)}
    par_mcp = _appeler(client, jeton, "situation_culture", {"culture": "salade", "date": "2026-11-20"})
    assert par_mcp["structuredContent"] == _situation(fabrique, jardin, "salade", LE_20_NOVEMBRE)


def test_us339_description_est_une_question_de_jardinier():
    """R1 de `07_REGLE_D_UNE_CAPACITE.md` : une question de jardinier, pas une commande."""
    c = registre.REGISTRE["situation_culture"]
    assert "est-ce le moment" in c.description.lower() and "/" not in c.description


def test_us339_pas_ce_mois_donne_toutes_les_fenetres_et_le_risque(client, fabrique, jardin, referentiel):
    """22/11 : Small 4 recopie `texte` ; la plantation et la raison du « pas maintenant » y sont donc, pas seulement
    la prochaine fenêtre (B04-F8 ne disait jamais « mai », B01-F8 jamais le froid)."""
    d = _situation(fabrique, jardin, "tomate", LE_20_NOVEMBRE)
    assert d["verdict"] == svc.VERDICT_PAS_CE_MOIS and d["texte"].startswith("Rien à semer ni planter ce mois-ci.")
    assert "Toutes les fenêtres" in d["texte"] and "mai à juin" in d["texte"]
    assert "semer en pépinière février à avril" in d["texte"]
    assert "froid" in d["texte"] and "gel" in d["texte"]


def test_us339_c_est_le_moment_garde_son_texte(client, fabrique, jardin, referentiel):
    d = _situation(fabrique, jardin, "salade", date(2026, 3, 10))
    assert d["verdict"] == svc.VERDICT_MAINTENANT and "Toutes les fenêtres" not in d["texte"]
