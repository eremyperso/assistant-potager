"""
tests/test_fix_unite_semis_hallucinee.py
[fix unité semis hallucinée] Une unité de semis que le jardinier n'a pas prononcée

Cas réel : « semi de 50 chou variété bruxelle le 1 mars » → Groq renvoie
`unite: "plants"` faute d'unité dans la phrase, que `_UNITES_SEMIS_CANONIQUES`
mappe légitimement sur « pieds » (US-037, semis en poquets). Résultat : un semis
de 50 graines compté en 50 pieds.

Semer met des graines en terre par définition ; « pieds » et « m² » restent des
exceptions valides, mais seulement si elles sont réellement dites.
"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from app.services.evenements import _normalize_unite_semis
from utils.validation import unite_semis_ancree_dans_texte

POTAGER_ID = 1


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=POTAGER_ID, role="owner")


# ── L'unité inventée retombe sur le défaut ───────────────────────────────────

def test_unite_plants_non_prononcee_retombe_sur_graines() -> None:
    """Le cas réel : aucune unité dans la phrase, « plants » inventé par Groq."""
    assert _normalize_unite_semis("plants", "semi de 50 chou variété bruxelle le 1 mars") == "graines"


def test_unite_m2_non_prononcee_retombe_sur_graines() -> None:
    """Même règle pour la surface : une unité non dite n'est pas une unité."""
    assert _normalize_unite_semis("m²", "semis de 50 choux") == "graines"


# ── Les unités réellement dites sont préservées (US-037 intact) ──────────────

@pytest.mark.parametrize("texte", [
    "semé 20 pieds de haricot",
    "semis de 20 plants de chou",
    "semé 12 poquets de haricots",
])
def test_unite_pieds_prononcee_est_conservee(texte) -> None:
    """Le semis en poquets/pieds reste un cas légitime dès qu'il est énoncé."""
    assert _normalize_unite_semis("plants", texte) == "pieds"


@pytest.mark.parametrize("texte", [
    "semé 2 m² de radis",
    "semis de 2 m2 de carottes",
    "semé 3 mètres carrés de mâche",
])
def test_unite_surface_prononcee_est_conservee(texte) -> None:
    """Le semis à la volée sur une surface (US-037) n'est pas dégradé."""
    assert _normalize_unite_semis("m²", texte) == "m²"


def test_unite_graines_prononcee_est_conservee() -> None:
    """L'unité par défaut n'a rien à prouver."""
    assert _normalize_unite_semis("graines", "semis de 50 graines de chou") == "graines"


# ── Rétrocompatibilité : sans texte, comportement d'origine ─────────────────

@pytest.mark.parametrize("brute,attendu", [
    ("plants", "pieds"), ("plant", "pieds"), ("pieds", "pieds"),
    ("m2", "m²"), ("m²", "m²"),
    ("graines", "graines"), (None, "graines"), ("kg", "graines"),
])
def test_sans_texte_le_comportement_us037_est_inchange(brute, attendu) -> None:
    """Les appelants historiques et les tests d'US-037 ne voient aucun changement."""
    assert _normalize_unite_semis(brute) == attendu


# ── Ancrage : la brique de décision ─────────────────────────────────────────

def test_ancrage_graines_toujours_vrai() -> None:
    """« graines » est le défaut : il n'a jamais besoin d'être ancré."""
    assert unite_semis_ancree_dans_texte("graines", "semis de 50 choux") is True


def test_ancrage_insensible_aux_accents_et_a_la_casse() -> None:
    assert unite_semis_ancree_dans_texte("m²", "Semé 3 MÈTRES CARRÉS de mâche") is True


def test_ancrage_ne_confond_pas_un_mot_englobant() -> None:
    """Comparaison mot à mot, pas sous-chaîne : « piedmont » ne contient pas « pied »
    au sens d'une unité."""
    assert unite_semis_ancree_dans_texte("pieds", "semis de 50 choux au piedmont") is False


# ── Bout en bout ────────────────────────────────────────────────────────────

def test_bout_en_bout_semis_sans_unite_est_enregistre_en_graines(db, ctx) -> None:
    """Le semis exact de la session de test finit bien en graines."""
    # Arrange
    texte = "semi de 50 chou variété bruxelle le 1 mars"
    parsed = {
        "action": "semis", "culture": "chou", "variete": "bruxelle",
        "quantite": 50, "unite": "plants", "date": "2026-03-01",
        "parcelle": None, "rang": None, "duree_minutes": None,
        "traitement": None, "commentaire": None,
    }

    # Act
    event = svc_evenements.creer_evenement_confirme(db, ctx, parsed, texte, None)

    # Assert
    assert event.unite == "graines"
    assert event.quantite == 50.0
    # `parsed` est muté en place — le récapitulatif Telegram affiche la même unité
    assert parsed["unite"] == "graines"


def test_bout_en_bout_semis_en_surface_reste_en_m2(db, ctx) -> None:
    """Contre-épreuve : un semis à la volée réellement dicté en m² n'est pas dégradé."""
    # Arrange
    texte = "semé 2 m² de radis le 1 mars"
    parsed = {
        "action": "semis", "culture": "radis", "variete": None,
        "quantite": 2, "unite": "m2", "date": "2026-03-01",
        "parcelle": None, "rang": None, "duree_minutes": None,
        "traitement": None, "commentaire": None,
    }

    # Act
    event = svc_evenements.creer_evenement_confirme(db, ctx, parsed, texte, None)

    # Assert
    assert event.unite == "m²"
    assert event.quantite == 2.0
