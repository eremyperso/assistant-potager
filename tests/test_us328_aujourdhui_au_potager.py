"""
tests/test_us328_aujourdhui_au_potager.py — À confirmer, à libérer, à placer aujourd'hui [US-328]
================================================================================================
Le panneau (listes vides, glisser-déposer au clavier, boutons mobiles) se teste côté frontend
(`frontend/src/lib/aujourdhui.test.js`) et à l'écran. Ce fichier tient le serveur :

- CA1 / CA2 : `GET /plan` sert `taches_du_jour`, à la date de référence, avec le même compte
  « à confirmer » que le filtre du plan (US-327) ;
- CA3 : « À placer » regroupe les lots prêts à planter et les cultures sans parcelle ;
- CA4 / CA5 : une carte posée sur un rang devient une carte de plantation (rang, part du rang,
  lot) SANS modèle — rien n'est écrit avant « Confirmer ».

Aucun appel de modèle : le parseur est simulé, l'agent éteint (`AGENT_MODE=off`).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import normalisation_gestes as svc_normalisation
from app.services import taches_plan as svc_taches
from app.services.compagnon import contexte_ecran as svc_ecran
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.compagnon import placement as svc_placement
from app.services.context import default_context
from database.models import CultureConfig, EchangeConversation, Evenement, Parcelle

CTX = default_context()


# ── Service pur : les trois listes ───────────────────────────────────────────
def _culture(nom, a_confirmer=False, etape="seme", rangs=(2,)):
    return {"culture": nom, "variete": None, "numeros_rangs": list(rangs),
            "etapes": {"etape": etape, "etape_libelle": etape.capitalize(), "etape_date": "2026-11-12",
                       "a_confirmer": a_confirmer, "etapes": []}}


def _parcelles():
    return [
        {"id": 1, "nom": "Planche haricots", "est_pepiniere": False,
         "cultures": [_culture("fève", True, "levee", (3, 1)), _culture("ail")],
         "a_liberer": [{"parcelle_id": 1, "parcelle_nom": "Planche haricots", "culture": "tomate cerise",
                        "variete": None, "etape": "terminee", "etape_date": "2026-10-30",
                        "etapes": [{"code": "terminee", "date": "2026-10-30"}]}]},
        {"id": 2, "nom": "Bac", "est_pepiniere": False, "cultures": [_culture("épinard", True, "levee", ())],
         "a_liberer": []},
        # Une pépinière ne compte jamais dans « À confirmer » (même règle que le filtre).
        {"id": 3, "nom": "Châssis", "est_pepiniere": True, "cultures": [_culture("laitue", True)],
         "a_liberer": []},
    ]


def test_us328_gherkin_a_confirmer_et_a_liberer():
    """Gherkin « Ce qui m'attend aujourd'hui »."""
    t = svc_taches.taches_du_jour(_parcelles(), [], [])
    assert [l["culture"] for l in t["a_confirmer"]] == ["fève", "épinard"]
    assert t["comptes"]["a_confirmer"] == 2
    assert [l["culture"] for l in t["a_liberer"]] == ["tomate cerise"]
    assert t["a_liberer"][0]["fin_le"] == "2026-10-30"


def test_us328_ca2_meme_compte_que_le_filtre_du_plan():
    from app.services import plan as svc_plan

    parcelles = _parcelles()
    t = svc_taches.taches_du_jour(parcelles, [], [])
    assert t["comptes"]["a_confirmer"] == svc_plan.compteurs_filtres(parcelles)[svc_plan.FILTRE_A_CONFIRMER]


def test_us328_a2_parcelle_rang_et_etape_prevue():
    ligne = svc_taches.taches_du_jour(_parcelles(), [], [])["a_confirmer"][0]
    assert ligne["parcelle_id"] == 1 and ligne["parcelle"] == "Planche haricots"
    assert ligne["rang"] == 1                        # le premier rang occupé
    assert ligne["etape"] == "levee"
    assert svc_taches.taches_du_jour(_parcelles(), [], [])["a_confirmer"][1]["rang"] is None


def test_us328_ca3_a_placer_lots_prets_puis_cultures_sans_parcelle():
    lots = [{"lot_id": "s42", "numero_lot": 42, "culture": "fraisier", "variete": "Mara des bois",
             "quantite": 12, "pepiniere": "Châssis"}]
    sans = [{"culture": "courge", "variete": None, "nb_plants": 3, "unite": "plants"}]
    cartes = svc_taches.taches_du_jour([], sans, lots)["a_placer"]
    assert [c["origine"] for c in cartes] == [svc_taches.ORIGINE_LOT, svc_taches.ORIGINE_SANS_PARCELLE]
    assert cartes[0]["numero_lot"] == 42 and cartes[0]["quantite"] == 12
    assert cartes[1]["culture"] == "courge" and cartes[1]["numero_lot"] is None


def test_us328_ca1_listes_vides():
    t = svc_taches.taches_du_jour([], [], [])
    assert t["comptes"] == {"a_confirmer": 0, "a_liberer": 0, "a_placer": 0}


def test_us328_a3_date_de_fin_repli_sur_l_etape_courante():
    assert svc_taches._date_de_fin({"etapes": [], "etape_date": "2026-10-01"}) == "2026-10-01"


# ── Placement : l'item sans modèle ───────────────────────────────────────────
ECRAN = svc_ecran.ContexteEcran(parcelle_id=1, parcelle="Planche haricots", rang=2)


def test_us328_gherkin_phrase_de_placement():
    p = svc_placement.lire_placement({"culture": "fraisiers", "variete": "Mara des bois", "quantite": 12})
    assert svc_placement.phrase_de_placement(p, ECRAN) == "Placer 12 fraisiers Mara des bois · Planche haricots, rang 2"


def test_us328_ca5_item_de_plantation_au_rang_et_lot_cite():
    p = svc_placement.lire_placement({"culture": "fraisier", "quantite": 12, "numero_lot": 42, "part": 1})
    item = svc_placement.items_du_placement(p, ECRAN).items[0]
    assert item["action"] == "plantation" and item["parcelle"] == "Planche haricots"
    assert item["rang_position"] == 2 and item["rang"] is None
    assert item["rang_longueur_m"] is None          # le rang entier
    assert item["numero_lot_cite"] == 42


def test_us328_ca5_part_du_rang_portee_par_l_item():
    p = svc_placement.lire_placement({"culture": "salade", "quantite": 6, "part": 0.5})
    assert svc_placement.items_du_placement(p, ECRAN, 2.0).items[0]["rang_longueur_m"] == 2.0


class _Requete:
    def __init__(self, valeur):
        self.valeur = valeur

    def filter(self, *a):
        return self

    def scalar(self):
        return self.valeur


class _Db:
    def __init__(self, longueur):
        self.longueur = longueur

    def query(self, *a):
        return _Requete(self.longueur)


@pytest.mark.parametrize("longueur,part,attendu", [
    (4.0, 0.5, 2.0), (4.0, 1, None), (4.0, 0.99, None), (None, 0.5, None), (4.0, None, None),
])
def test_us328_ca5_longueur_de_la_part(longueur, part, attendu):
    """[US-326 / P4] Rang entier, part inconnue ou longueur absente : aucune mesure inventée."""
    from app.services import geometrie as svc_geometrie

    assert svc_geometrie.longueur_de_la_part(_Db(longueur), 1, part) == attendu
    assert svc_geometrie.longueur_de_la_part(_Db(longueur), None, part) is None


def test_us328_placement_sans_rang_demande_le_rang():
    p = svc_placement.lire_placement({"culture": "salade"})
    sans_rang = svc_ecran.ContexteEcran(parcelle_id=1, parcelle="Planche haricots")
    assert svc_placement.items_du_placement(p, sans_rang).precision == svc_placement.TEXTE_SANS_RANG
    assert svc_placement.items_du_placement(p, None).precision == svc_placement.TEXTE_SANS_RANG


def test_us328_placement_sans_culture():
    p = svc_placement.lire_placement({"quantite": 3})
    assert svc_placement.items_du_placement(p, ECRAN).precision == svc_placement.TEXTE_SANS_CULTURE


@pytest.mark.parametrize("brut", [{"culture": "x", "part": 0}, {"culture": "x", "part": 1.5},
                                  {"culture": "x", "part": "moitié"}, {"culture": "x", "numero_lot": "a"}, "x"])
def test_us328_placement_mal_forme(brut):
    with pytest.raises(svc_placement.PlacementInvalideError):
        svc_placement.lire_placement(brut)


def test_us328_placement_absent():
    assert svc_placement.lire_placement(None) is None


# ── Route : GET /plan et POST /compagnon/messages ────────────────────────────
@pytest.fixture(autouse=True)
def sans_modele(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "off")
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)
    monkeypatch.setattr(svc_normalisation, "parser_saisie",
                        lambda texte, ctx=None: type("R", (), {"reconnu": False, "items": None})())
    monkeypatch.setattr(svc_normalisation, "parse_commande", lambda texte, ctx=None: [])


def _jour(jours: int) -> datetime:
    return datetime.combine(date.today() - timedelta(days=jours), datetime.min.time())


@pytest.fixture
def potager(memoire_compagnon):
    """Planche haricots (4 m, 3 rangs) : un ail planté ; une courge dite sans parcelle."""
    with memoire_compagnon() as db:
        planche = Parcelle(nom="Planche haricots", nom_normalise="plancheharicots", ordre=1, actif=True,
                           potager_id=CTX.potager_id, nb_rangs=3, longueur_m=4.0)
        db.add_all([planche, CultureConfig(nom="ail", type_organe_recolte="végétatif"),
                    CultureConfig(nom="salade", type_organe_recolte="végétatif")])
        db.flush()
        db.add_all([
            Evenement(potager_id=CTX.potager_id, type_action="plantation", culture="ail", quantite=10,
                      unite="plants", parcelle_id=planche.id, date=_jour(30), rang_position=1),
            Evenement(potager_id=CTX.potager_id, type_action="plantation", culture="courge", quantite=3,
                      unite="plants", parcelle_id=None, date=_jour(5)),
        ])
        db.commit()
        pid = planche.id
    yield memoire_compagnon, pid
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(CultureConfig).delete()
        db.query(EchangeConversation).delete()
        db.commit()


@pytest.fixture
def client(potager):
    from app.api.main import app, get_current_user_ctx

    app.dependency_overrides[get_current_user_ctx] = default_context
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


def test_us328_get_plan_sert_les_taches_du_jour(client, potager, monkeypatch):
    from app.api import main

    monkeypatch.setattr(main, "SessionLocal", potager[0])   # GET /plan lit la même base
    r = client.get("/plan")
    assert r.status_code == 200, r.text
    corps = r.json()
    taches = corps["taches_du_jour"]
    assert set(taches) == {"a_confirmer", "a_liberer", "a_placer", "comptes"}
    assert taches["comptes"]["a_confirmer"] == corps["filtres_plan"]["a_confirmer"]
    # [CA3] La culture sans parcelle est listée dans « À placer ».
    assert any(c["culture"] == "courge" and c["origine"] == "sans_parcelle" for c in taches["a_placer"])


def test_us328_gherkin_glisser_propose_sans_rien_enregistrer(client, potager):
    """Gherkin « Placer des fraisiers de la pépinière » — côté serveur, sans lot réel."""
    memoire, pid = potager
    with memoire() as db:
        avant = db.query(Evenement).count()
    r = client.post("/compagnon/messages", json={
        "texte": "Placer 6 salade · Planche haricots, rang 2",
        "contexte": {"parcelle_id": pid, "rang": 2},
        "placement": {"culture": "salade", "quantite": 6, "part": 0.5},
    })
    assert r.status_code == 200, r.text
    corps = r.json()
    assert corps["texte"].startswith("Placer 6 salade · Planche haricots, rang 2")
    assert len(corps["propositions"]) == 1
    with memoire() as db:
        assert db.query(Evenement).count() == avant     # rien avant « Confirmer »

    c = client.post(f"/compagnon/propositions/{corps['propositions'][0]['id']}/confirmer")
    assert c.status_code == 200, c.text
    with memoire() as db:
        evt = db.query(Evenement).filter(Evenement.culture == "salade").one()
        assert evt.type_action == "plantation" and evt.parcelle_id == pid
        assert evt.rang_position == 2 and evt.rang_longueur_m == 2.0


def test_us328_placement_invalide_422(client, potager):
    _, pid = potager
    r = client.post("/compagnon/messages", json={
        "texte": "x", "contexte": {"parcelle_id": pid, "rang": 2}, "placement": {"culture": "x", "part": 3}})
    assert r.status_code == 422


# ── Lots prêts pour le plan (CA3) et lots en cours du chemin mobile (US-329 / M6) ──
def _lot(numero, godets, graines=0, culture="fraisier"):
    return {"lot_id": f"semis-{numero}", "numero_lot": numero, "culture": culture, "variete": None,
            "parcelle": "Châssis", "stock_residuel_godet": godets, "graines_semees": graines,
            "graines_soldees": 0, "graines_non_soldees": graines}


def test_us328_ca3_lots_prets_meme_regle_que_la_pepiniere(monkeypatch):
    """Un lot sans godet n'est jamais prêt ; mise en terre inconnue = prêt ; « pas encore » = non."""
    from app.services import echeances_lots as svc

    lots = [_lot(3, 12), _lot(1, 0, graines=20), _lot(2, 5)]
    etats = {"semis-3": None, "semis-2": "pas_encore"}
    monkeypatch.setattr(svc.svc_stock, "calcul_lots_pepiniere", lambda db, ctx, d=None: lots)
    monkeypatch.setattr(svc, "_delais_de", lambda *a, **k: None)
    monkeypatch.setattr(svc, "_echeances_du_lot", lambda lot, delais, ref: {
        "echeances": {"mise_en_terre": {"etat": etats.get(lot["lot_id"])}}})
    prets = svc.lots_prets_pour_le_plan(None, CTX, date(2026, 11, 13))
    assert [l["numero_lot"] for l in prets] == [3]
    assert prets[0]["quantite"] == 12 and prets[0]["pepiniere"] == "Châssis"


def test_us328_ca3_lots_prets_tries_par_numero(monkeypatch):
    from app.services import echeances_lots as svc

    monkeypatch.setattr(svc.svc_stock, "calcul_lots_pepiniere",
                        lambda db, ctx, d=None: [_lot(None, 2), _lot(9, 4), _lot(4, 1)])
    monkeypatch.setattr(svc, "_delais_de", lambda *a, **k: None)
    monkeypatch.setattr(svc, "_echeances_du_lot", lambda lot, delais, ref: {
        "echeances": {"mise_en_terre": {"etat": svc.ETAT_ATTEINTE}}})
    assert [l["numero_lot"] for l in svc.lots_prets_pour_le_plan(None, CTX)] == [4, 9, None]


def test_us329_m6_lots_en_cours_portent_quantite_et_stade(monkeypatch):
    from app.services import repartition_rangs as svc

    monkeypatch.setattr(svc, "calcul_lots_pepiniere", lambda db, d, potager_id=None: [
        _lot(1, 12, graines=20), _lot(2, 0, graines=30, culture="chou"), _lot(3, 0, graines=0)])
    monkeypatch.setattr(svc, "graines_restantes", lambda lot: lot["graines_non_soldees"])
    lots = svc._lots_en_cours_par_parcelle(None, 1, None)["Châssis"]
    assert [(l["numero_lot"], l["quantite"], l["unite"], l["stade"]) for l in lots] == [
        (1, 12, "godets", svc.STADE_LOT_GODET), (2, 30, "graines", svc.STADE_LOT_SEMIS)]
