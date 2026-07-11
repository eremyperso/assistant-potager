"""
[US-039] Tests — Affichage des observations sur le dashboard frontend (backend)

Couvre la règle de routage de utils/observations.py::build_observations_index
et les endpoints /plan, /stats, /observations.

CA1 : /plan expose has_observations par parcelle
CA2 : /stats (stock_par_culture) expose has_observations par culture
CA3 : /observations retourne les items selon le filtre (parcelle_id / culture+variete)
CA4 : la résolution du cas 3 réutilise calcul_occupation_parcelles
CA5/CA6 : routage mutuellement exclusif Plan vs Stocks
CA8 : le préfixe [Catégorie] est retiré du texte affiché
"""
import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from database.models import Evenement, Parcelle
from utils.observations import strip_categorie, build_observations_index


# ── strip_categorie ────────────────────────────────────────────────────────

def test_us039_strip_categorie_retire_prefixe():
    assert strip_categorie("[Maladie / ravageur] mildiou sur les feuilles") == "mildiou sur les feuilles"
    assert strip_categorie("[Paillage] paille de blé") == "paille de blé"


def test_us039_strip_categorie_sans_prefixe_inchange():
    assert strip_categorie("texte sans préfixe") == "texte sans préfixe"


def test_us039_strip_categorie_none_ou_vide():
    assert strip_categorie(None) == ""
    assert strip_categorie("") == ""


# ── build_observations_index — cas 1 : parcelle_id renseigné ────────────────

def test_us039_ca1_observation_parcelle_seule(test_db):
    """Cas 1a : parcelle_id renseigné, pas de culture/variete → header parcelle uniquement."""
    p = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
    test_db.add(p)
    test_db.commit()

    ev = Evenement(type_action="observation", parcelle_id=p.id, commentaire="[Arrosage (remarque)] Sol sec",
                    date=datetime(2026, 6, 10))
    test_db.add(ev)
    test_db.commit()

    index = build_observations_index(test_db)

    assert len(index["parcelle"][p.id]) == 1
    assert index["parcelle"][p.id][0]["texte"] == "Sol sec"
    assert index["culture_row"] == {}
    assert index["stocks"] == {}


def test_us039_ca1_observation_parcelle_et_culture_variete(test_db):
    """Cas 1b (règle exclusive) : parcelle_id + culture + variete → ligne culture UNIQUEMENT,
    jamais l'icône parcelle (évite le doublon d'accès dans Plan)."""
    p = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
    test_db.add(p)
    test_db.commit()

    ev = Evenement(type_action="observation", parcelle_id=p.id, culture="tomate", variete="Roma",
                    commentaire="[Maladie / ravageur] mildiou", date=datetime(2026, 6, 10))
    test_db.add(ev)
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["parcelle"] == {}  # [règle exclusive] pas d'icône parcelle
    assert index["culture_row"][(p.id, "tomate", "Roma")][0]["texte"] == "mildiou"
    assert index["stocks"] == {}  # [CA11] jamais dupliqué sur Stocks


def test_us039_orphelin_culture_sans_variete_avec_parcelle(test_db):
    """Cas orphelin : parcelle_id + culture SANS variete → Stocks (pas d'icône parcelle,
    pas de ligne culture précise possible sans variété)."""
    p = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
    test_db.add(p)
    test_db.commit()

    ev = Evenement(type_action="observation", parcelle_id=p.id, culture="courgette", variete=None,
                    commentaire="[Paillage] paille ajoutée", date=datetime(2026, 6, 10))
    test_db.add(ev)
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["parcelle"] == {}
    assert index["culture_row"] == {}
    assert index["stocks"]["courgette"][0]["texte"] == "paille ajoutée"


# ── build_observations_index — cas 2 : culture seule, pas de parcelle ───────

def test_us039_ca2_observation_culture_sans_parcelle(test_db):
    ev = Evenement(type_action="observation", culture="courgette", variete=None, parcelle_id=None,
                    commentaire="[Observation] belle vigueur", date=datetime(2026, 6, 1))
    test_db.add(ev)
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["stocks"]["courgette"][0]["texte"] == "belle vigueur"
    assert index["parcelle"] == {}
    assert index["culture_row"] == {}


# ── build_observations_index — cas 3 : culture+variete sans parcelle ────────

def test_us039_ca3_ca4_resolution_parcelle_unique(test_db):
    """Cas 3 résolu : culture+variete plantée dans UNE seule parcelle → bascule vers Plan."""
    p = Parcelle(nom="Potager centre", nom_normalise="potagercentre", actif=True)
    test_db.add(p)
    test_db.commit()

    # Plantation active donnant du stock à "tomate cerise" sur cette parcelle
    test_db.add(Evenement(
        type_action="plantation", culture="tomate", variete="cerise",
        quantite=6, unite="plants", parcelle_id=p.id, date=datetime(2026, 5, 5),
    ))
    # Note non localisée sur la même culture+variete
    test_db.add(Evenement(
        type_action="observation", culture="tomate", variete="cerise", parcelle_id=None,
        commentaire="[Maladie / ravageur] pucerons", date=datetime(2026, 6, 15),
    ))
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["culture_row"][(p.id, "tomate", "cerise")][0]["texte"] == "pucerons"
    assert "tomate" not in index["stocks"]  # [CA11] pas dupliqué sur Stocks


def test_us039_ca3_repli_stocks_si_plusieurs_parcelles(test_db):
    """Cas 3 non résolu : culture+variete plantée dans 2 parcelles → repli sur Stocks."""
    p1 = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
    p2 = Parcelle(nom="Sud", nom_normalise="sud", actif=True)
    test_db.add_all([p1, p2])
    test_db.commit()

    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="cerise",
                           quantite=4, unite="plants", parcelle_id=p1.id, date=datetime(2026, 5, 5)))
    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="cerise",
                           quantite=3, unite="plants", parcelle_id=p2.id, date=datetime(2026, 5, 5)))
    test_db.add(Evenement(type_action="observation", culture="tomate", variete="cerise", parcelle_id=None,
                           commentaire="[Observation] belle floraison", date=datetime(2026, 6, 1)))
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["stocks"]["tomate"][0]["texte"] == "belle floraison"
    assert index["culture_row"] == {}


def test_us039_ca3_repli_stocks_si_aucune_parcelle(test_db):
    """Cas 3 non résolu : culture+variete pas (ou plus) en terre → repli sur Stocks."""
    ev = Evenement(type_action="observation", culture="tomate", variete="noire de Crimée", parcelle_id=None,
                    commentaire="[Observation] semis prévu", date=datetime(2026, 2, 1))
    test_db.add(ev)
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["stocks"]["tomate"][0]["texte"] == "semis prévu"


# ── build_observations_index — cas 4 : hors périmètre ────────────────────────

def test_us039_ca4_cas_hors_perimetre_ignore(test_db):
    """Ni parcelle_id ni culture → n'apparaît dans aucun bucket (reste dans Historique)."""
    ev = Evenement(type_action="observation", culture=None, variete=None, parcelle_id=None,
                    commentaire="[Observation] le compost a besoin d'être retourné", date=datetime(2026, 6, 1))
    test_db.add(ev)
    test_db.commit()

    index = build_observations_index(test_db)

    assert index["parcelle"] == {}
    assert index["culture_row"] == {}
    assert index["stocks"] == {}


# ── Tri chronologique décroissant ────────────────────────────────────────────

def test_us039_tri_plus_recent_en_premier(test_db):
    p = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
    test_db.add(p)
    test_db.commit()

    test_db.add(Evenement(type_action="observation", parcelle_id=p.id, commentaire="[Paillage] ancien",
                           date=datetime(2026, 5, 1)))
    test_db.add(Evenement(type_action="observation", parcelle_id=p.id, commentaire="[Paillage] récent",
                           date=datetime(2026, 6, 15)))
    test_db.commit()

    index = build_observations_index(test_db)
    textes = [o["texte"] for o in index["parcelle"][p.id]]
    assert textes == ["récent", "ancien"]


# ── Endpoints API ─────────────────────────────────────────────────────────────
# Appel direct des fonctions d'endpoint (pas de TestClient) : évite le bug
# d'infra préexistant SQLite in-memory + thread anyio du TestClient qui affecte
# déjà tests/test_api.py indépendamment de cette US.

import main


class TestObservationsEndpoints:

    def test_plan_expose_id_et_has_observations(self, test_db):
        p = Parcelle(nom="Nord", nom_normalise="nord", actif=True, superficie_m2=10)
        test_db.add(p)
        test_db.commit()
        test_db.add(Evenement(type_action="observation", parcelle_id=p.id, commentaire="[Observation] test",
                               date=datetime(2026, 6, 1)))
        test_db.commit()

        with patch('main.SessionLocal', return_value=test_db):
            data = main.get_plan(date_ref=None)

        parcelle = next(x for x in data["parcelles"] if x["nom"] == "Nord")
        assert parcelle["id"] == p.id
        assert parcelle["has_observations"] is True

    def test_plan_has_observations_false_sans_note(self, test_db):
        p = Parcelle(nom="Sud", nom_normalise="sud", actif=True)
        test_db.add(p)
        test_db.commit()

        with patch('main.SessionLocal', return_value=test_db):
            data = main.get_plan(date_ref=None)

        parcelle = next(x for x in data["parcelles"] if x["nom"] == "Sud")
        assert parcelle["has_observations"] is False

    def test_stats_stock_par_culture_expose_has_observations(self, test_db):
        test_db.add(Evenement(type_action="plantation", culture="courgette", quantite=5, unite="plants",
                               date=datetime(2026, 5, 1)))
        test_db.add(Evenement(type_action="observation", culture="courgette", parcelle_id=None,
                               commentaire="[Observation] belle vigueur", date=datetime(2026, 6, 1)))
        test_db.commit()

        with patch('main.SessionLocal', return_value=test_db):
            data = main.stats(date_ref=None)

        stock = next((c for c in data["stock_par_culture"] if c["culture"] == "courgette"), None)
        assert stock is not None
        assert stock["has_observations"] is True

    def test_observations_endpoint_par_parcelle(self, test_db):
        p = Parcelle(nom="Nord", nom_normalise="nord", actif=True)
        test_db.add(p)
        test_db.commit()
        test_db.add(Evenement(type_action="observation", parcelle_id=p.id,
                               commentaire="[Arrosage (remarque)] sol sec", date=datetime(2026, 6, 1)))
        test_db.commit()

        with patch('main.SessionLocal', return_value=test_db):
            data = main.get_observations(parcelle_id=p.id, culture=None, variete=None)

        assert len(data["items"]) == 1
        assert data["items"][0]["texte"] == "sol sec"

    def test_observations_endpoint_par_culture(self, test_db):
        test_db.add(Evenement(type_action="observation", culture="poireau", parcelle_id=None,
                               commentaire="[Paillage] paille ajoutée", date=datetime(2026, 6, 1)))
        test_db.commit()

        with patch('main.SessionLocal', return_value=test_db):
            data = main.get_observations(parcelle_id=None, culture="poireau", variete=None)

        assert data["items"][0]["texte"] == "paille ajoutée"

    def test_observations_endpoint_vide_si_rien(self, test_db):
        with patch('main.SessionLocal', return_value=test_db):
            data = main.get_observations(parcelle_id=None, culture="inexistante", variete=None)

        assert data["items"] == []
