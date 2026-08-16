"""
tests/test_us072_stock_varietes.py
-----------------------------------
[US-072] Détail par variété, toutes cultures confondues, avec leurs parcelles réelles.

Couvre calcul_stock_varietes() (utils/stock.py) :
- CA1 : une entrée par (culture, variété) réellement présente, aucune entrée fantôme
- CA2 : état parmi potager / semis / pep, mêmes règles qu'aujourd'hui
- CA3 : origine reprise du calcul déjà en place (pépinière / pied_acheté / semis_pleine_terre / non_localisé)
- CA4 : parcelles réelles, jamais un lieu unique ni une parcelle par défaut ; vide pour "pep"
- CA5 : champs numériques repris tels quels des calculs existants
- CA6 : "vendu" uniquement à l'état "pep", jamais 0 par défaut pour potager/semis
- CA7 : filet anti-double-comptage à la granularité variété
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from database.models import Evenement, Parcelle, CultureConfig
from utils.stock import calcul_stock_varietes


@pytest.fixture
def db(test_db):
    return test_db


def _add_parcelle(db, nom, est_pepiniere=False, actif=True):
    p = Parcelle(nom=nom, nom_normalise=nom.lower(), ordre=1, actif=actif, est_pepiniere=est_pepiniere)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _add_culture_config(db, nom, type_organe):
    db.add(CultureConfig(nom=nom, type_organe_recolte=type_organe))
    db.commit()


def _ev(**kwargs):
    kwargs.setdefault("date", datetime.now())
    return Evenement(**kwargs)


def _entry(varietes, culture, variete, etat=None):
    matches = [
        v for v in varietes
        if v["culture"] == culture and v["variete"] == variete and (etat is None or v["etat"] == etat)
    ]
    assert len(matches) == 1, f"attendu 1 entrée pour {culture}/{variete}/{etat}, trouvé {len(matches)} : {matches}"
    return matches[0]


# ══════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin 1 — deux variétés d'une même culture sur des parcelles différentes
# ══════════════════════════════════════════════════════════════════════════════

class TestDeuxVarietesParcellesDifferentes:

    def test_ca1_deux_entrees_distinctes_une_par_variete(self, db):
        maison = _add_parcelle(db, "Maison")
        serre = _add_parcelle(db, "Serre")
        _add_culture_config(db, "tomate", "reproducteur")
        db.add_all([
            _ev(type_action="plantation", culture="tomate", variete="Cœur de bœuf",
                quantite=3, unite="plants", parcelle_id=maison.id),
            _ev(type_action="plantation", culture="tomate", variete="Cerise",
                quantite=2, unite="plants", parcelle_id=serre.id),
        ])
        db.commit()

        result = calcul_stock_varietes(db)
        tomates = [v for v in result if v["culture"] == "tomate"]
        assert len(tomates) == 2

    def test_chacune_liste_uniquement_sa_propre_parcelle(self, db):
        maison = _add_parcelle(db, "Maison")
        serre = _add_parcelle(db, "Serre")
        _add_culture_config(db, "tomate", "reproducteur")
        db.add_all([
            _ev(type_action="plantation", culture="tomate", variete="Cœur de bœuf",
                quantite=3, unite="plants", parcelle_id=maison.id),
            _ev(type_action="plantation", culture="tomate", variete="Cerise",
                quantite=2, unite="plants", parcelle_id=serre.id),
        ])
        db.commit()

        result = calcul_stock_varietes(db)
        coeur = _entry(result, "tomate", "Cœur de bœuf")
        cerise = _entry(result, "tomate", "Cerise")
        assert coeur["parcelles"] == ["Maison"]
        assert cerise["parcelles"] == ["Serre"]
        assert coeur["etat"] == "potager"
        assert cerise["etat"] == "potager"


# ══════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin 2 — une variété plantée dans plusieurs parcelles
# ══════════════════════════════════════════════════════════════════════════════

def test_scenario2_une_variete_plusieurs_parcelles(db):
    maison = _add_parcelle(db, "Maison")
    serre = _add_parcelle(db, "Serre")
    _add_culture_config(db, "tomate", "reproducteur")
    db.add_all([
        _ev(type_action="plantation", culture="tomate", variete="Cœur de bœuf",
            quantite=2, unite="plants", parcelle_id=maison.id),
        _ev(type_action="plantation", culture="tomate", variete="Cœur de bœuf",
            quantite=1, unite="plants", parcelle_id=serre.id),
    ])
    db.commit()

    result = calcul_stock_varietes(db)
    tomates = [v for v in result if v["culture"] == "tomate"]
    assert len(tomates) == 1
    assert set(tomates[0]["parcelles"]) == {"Maison", "Serre"}
    assert tomates[0]["total_entre"] == 3


# ══════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin 3 — variété uniquement en pépinière
# ══════════════════════════════════════════════════════════════════════════════

def test_scenario3_variete_uniquement_en_pepiniere(db):
    _add_culture_config(db, "butternut", "reproducteur")
    db.add(_ev(type_action="mise_en_godet", culture="butternut", variete="Muscade",
                nb_graines_semees=10, nb_plants_godets=10))
    db.add(_ev(type_action="vendu", culture="butternut", variete="Muscade", quantite=2))
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "butternut", "Muscade", etat="pep")
    assert entry["vendu"] == 2
    assert entry["rendement_total"] == 0
    assert entry["parcelles"] == []
    assert entry["origine"] == "pépinière"


# ══════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin 4 — vente absente pour une culture en place
# ══════════════════════════════════════════════════════════════════════════════

def test_scenario4_vendu_absent_pour_culture_au_potager(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "tomate", "reproducteur")
    db.add(_ev(type_action="plantation", culture="tomate", variete="Cœur de bœuf",
                quantite=3, unite="plants", parcelle_id=maison.id))
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "tomate", "Cœur de bœuf")
    assert entry["etat"] == "potager"
    assert entry["vendu"] is None  # [CA6] jamais 0 par défaut


# ══════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin 5 — absence de double comptage (CA7)
# ══════════════════════════════════════════════════════════════════════════════

def test_scenario5_absence_de_double_comptage(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "haricot", "reproducteur")
    db.add_all([
        _ev(type_action="plantation", culture="haricot", variete="Cosse verte",
            quantite=5, unite="pieds", parcelle_id=maison.id),
        _ev(type_action="semis", culture="haricot", variete="Cosse verte",
            quantite=3, unite="pieds", parcelle_id=maison.id),
    ])
    db.commit()

    result = calcul_stock_varietes(db)
    matches = [v for v in result if v["culture"] == "haricot" and v["variete"] == "Cosse verte"]
    assert len(matches) == 1
    assert matches[0]["etat"] == "potager"


# ══════════════════════════════════════════════════════════════════════════════
# CA2/CA7 — semis non localisé = stade "en germination" (calcul_godets), jamais un
# doublon entre état "semis" et état "pep" pour le même semis
# ══════════════════════════════════════════════════════════════════════════════

def test_semis_non_localise_est_deja_couvert_par_pep_jamais_par_semis(db):
    """[CA7] Un semis sans parcelle est un stade "en germination" pour calcul_godets
    (docstring existant) — il ne doit PAS aussi apparaître à l'état "semis", sinon
    la même graine est comptée deux fois une fois les trois états fusionnés (US-073)."""
    _add_culture_config(db, "pois", "reproducteur")
    db.add(_ev(type_action="semis", culture="pois", variete="Nain hâtif",
                quantite=20, unite="graines", parcelle_id=None))
    db.commit()

    result = calcul_stock_varietes(db)
    matches = [v for v in result if v["culture"] == "pois" and v["variete"] == "Nain hâtif"]
    assert len(matches) == 1
    assert matches[0]["etat"] == "pep"
    assert matches[0]["parcelles"] == []


def test_semis_pleine_terre_localise_sans_plantation_devient_semis(db):
    """[CA2/CA7] Un semis pleine terre localisé (parcelle réelle non pépinière),
    sans aucun événement de "plantation" pour cette variété, est déjà fusionné dans
    calcul_stock_cultures (potager) — mais à la granularité variété (CA7), l'état
    affiché est "semis" tant qu'aucune plantation propre n'existe."""
    champ = _add_parcelle(db, "Champ")
    _add_culture_config(db, "pois", "reproducteur")
    db.add(_ev(type_action="semis", culture="pois", variete="Nain hâtif",
                quantite=20, unite="graines", parcelle_id=champ.id))
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "pois", "Nain hâtif")
    assert entry["etat"] == "semis"
    assert entry["parcelles"] == ["Champ"]
    assert entry["origine"] == "semis_pleine_terre"
    assert entry["vendu"] is None


def test_variete_avec_plantation_reste_potager_meme_avec_semis_pt_associe(db):
    """Une variété qui a une plantation propre reste "potager", même si la même
    culture a par ailleurs un semis pleine terre localisé pour une AUTRE variété."""
    champ = _add_parcelle(db, "Champ")
    _add_culture_config(db, "pois", "reproducteur")
    db.add_all([
        _ev(type_action="plantation", culture="pois", variete="Petit provençal",
            quantite=5, unite="pieds", parcelle_id=champ.id),
        _ev(type_action="semis", culture="pois", variete="Nain hâtif",
            quantite=20, unite="graines", parcelle_id=champ.id),
    ])
    db.commit()

    result = calcul_stock_varietes(db)
    assert _entry(result, "pois", "Petit provençal")["etat"] == "potager"
    assert _entry(result, "pois", "Nain hâtif")["etat"] == "semis"


def test_ca3_origine_non_localise_pour_plantation_sans_parcelle(db):
    """[CA3] Une plantation sans parcelle_id (aucune parcelle précisée), sans godet
    ni semis pleine terre par ailleurs, expose l'origine "non_localisé"."""
    _add_culture_config(db, "radis", "végétatif")
    db.add(_ev(type_action="plantation", culture="radis", variete="18 jours",
                quantite=15, unite="plants", parcelle_id=None))
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "radis", "18 jours")
    assert entry["etat"] == "potager"
    assert entry["origine"] == "non_localisé"
    assert entry["parcelles"] == ["Non localisé"]


# ══════════════════════════════════════════════════════════════════════════════
# CA1 — aucune entrée fantôme
# ══════════════════════════════════════════════════════════════════════════════

def test_ca1_aucune_entree_pour_culture_jamais_enregistree(db):
    result = calcul_stock_varietes(db)
    assert result == []


def test_ca1_seules_les_cultures_reellement_presentes_apparaissent(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "tomate", "reproducteur")
    _add_culture_config(db, "carotte", "végétatif")  # jamais utilisée
    db.add(_ev(type_action="plantation", culture="tomate", variete="Cerise",
                quantite=2, unite="plants", parcelle_id=maison.id))
    db.commit()

    result = calcul_stock_varietes(db)
    cultures = {v["culture"] for v in result}
    assert cultures == {"tomate"}


# ══════════════════════════════════════════════════════════════════════════════
# CA5 — stock actuel calculé selon type_organe (végétatif vs reproducteur)
# ══════════════════════════════════════════════════════════════════════════════

def test_ca5_stock_actuel_vegetatif_deduit_les_recoltes(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "carotte", "végétatif")
    db.add_all([
        _ev(type_action="plantation", culture="carotte", variete="Nantaise",
            quantite=10, unite="plants", parcelle_id=maison.id),
        _ev(type_action="recolte", culture="carotte", variete="Nantaise",
            quantite=3, unite="plants"),
    ])
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "carotte", "Nantaise")
    assert entry["stock_actuel"] == 7  # 10 planté - 3 récolté (destructif)


def test_ca5_stock_actuel_reproducteur_ignore_les_recoltes_pieces(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "tomate", "reproducteur")
    db.add_all([
        _ev(type_action="plantation", culture="tomate", variete="Cerise",
            quantite=4, unite="plants", parcelle_id=maison.id),
        _ev(type_action="recolte", culture="tomate", variete="Cerise",
            quantite=0.5, unite="kg"),
    ])
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "tomate", "Cerise")
    assert entry["stock_actuel"] == 4  # récolte en poids n'affecte pas le stock de pieds
    # [comportement existant _best_g] sous 1kg cumulé, la valeur reste exprimée en grammes
    assert entry["rendement_total"] == 500.0
    assert entry["unite_rendement"] == "g"


# ══════════════════════════════════════════════════════════════════════════════
# CA3 — origine pépinière prioritaire sur semis_pleine_terre
# ══════════════════════════════════════════════════════════════════════════════

def test_ca3_origine_pepiniere_si_passage_par_godet(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "poivron", "reproducteur")
    db.add_all([
        _ev(type_action="mise_en_godet", culture="poivron", variete="Doux",
            nb_graines_semees=5, nb_plants_godets=5),
        _ev(type_action="plantation", culture="poivron", variete="Doux",
            quantite=5, unite="plants", parcelle_id=maison.id),
    ])
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "poivron", "Doux", etat="potager")
    assert entry["origine"] == "pépinière"


def test_ca3_origine_pied_achete_sans_godet_ni_semis(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "fraisier", "reproducteur")
    db.add(_ev(type_action="plantation", culture="fraisier", variete="Gariguette",
                quantite=6, unite="plants", parcelle_id=maison.id))
    db.commit()

    result = calcul_stock_varietes(db)
    entry = _entry(result, "fraisier", "Gariguette")
    assert entry["origine"] == "pied_acheté"


# ══════════════════════════════════════════════════════════════════════════════
# [US-030] date_ref
# ══════════════════════════════════════════════════════════════════════════════

def test_date_ref_limite_les_evenements_pris_en_compte(db):
    maison = _add_parcelle(db, "Maison")
    _add_culture_config(db, "tomate", "reproducteur")
    hier = datetime.now() - timedelta(days=10)
    demain = datetime.now() + timedelta(days=5)
    db.add_all([
        _ev(type_action="plantation", culture="tomate", variete="Ancienne",
            quantite=2, unite="plants", parcelle_id=maison.id, date=hier),
        _ev(type_action="plantation", culture="tomate", variete="Future",
            quantite=2, unite="plants", parcelle_id=maison.id, date=demain),
    ])
    db.commit()

    result = calcul_stock_varietes(db, date_ref=datetime.now().date())
    varietes = {v["variete"] for v in result if v["culture"] == "tomate"}
    assert varietes == {"Ancienne"}
