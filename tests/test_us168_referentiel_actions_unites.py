"""
tests/test_us168_referentiel_actions_unites.py
[US-168] Unifier le référentiel d'actions et normaliser les unités à l'écriture

Couvre CA1 → CA13 :
- CA1/CA2/CA3 : un seul référentiel fait foi (ACTION_MAP), ACTIONS_VALIDES en
  dérive par construction ; binage/eclaircie présents dans les deux
  vocabulaires ; un test de cohérence détecterait une régression.
- CA4        : le repli passant de normalize_action est conservé mais journalisé.
- CA5/CA6/CA9/CA11 : normalisation d'unité pied/pieds → plants à l'écriture,
  plus de doublon sémantique au regroupement, plus de garde-fou déclenché.
- CA10       : le gabarit de stock rend le même chiffre et la même unité pour
  deux cultures saisies dans des unités différentes.
- CA12       : une saisie "binage"/"eclaircie" traverse validation ET
  normalisation jusqu'en base.
- CA13       : le routeur n'a plus besoin d'un supplément lexical séparé.
"""
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from app.services.evenements import creer_evenement_confirme, _normalize_unite_denombrement
from database.models import CultureConfig, Evenement, Parcelle
from llm import routeur
from llm.routeur import NATURE_ACTION
from utils.actions import ACTION_MAP, normalize_action
from utils.stock import calcul_stock_cultures
from utils.validation import ACTIONS_VALIDES, validate_parsed_action

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture(autouse=True)
def _cache_routeur_propre():
    routeur.vider_cache()
    yield
    routeur.vider_cache()


# ─────────────────────────────────────────────────────────────────────────────
# CA1 / CA3 — un seul référentiel fait foi, l'autre en dérive par construction
# ─────────────────────────────────────────────────────────────────────────────

def test_ca1_ca3_tout_canonique_de_sortie_est_un_vocabulaire_d_entree_valide():
    """Test de cohérence : un `type_action` canonique (clé de ACTION_MAP) doit
    toujours pouvoir être validé en entrée, sinon il est écrit mais inatteignable
    (c'était le défaut historique de 'amendement'/'protection')."""
    manquants = set(ACTION_MAP.keys()) - ACTIONS_VALIDES
    assert not manquants, f"Canoniques de sortie absents du vocabulaire d'entrée : {manquants}"


def test_ca1_toute_entree_valide_normalise_vers_un_canonique_reel():
    """Chaque mot accepté en entrée doit normaliser vers une clé réelle de
    ACTION_MAP — un vocabulaire d'entrée qui accepte un mot mort serait aussi
    silencieux que la divergence corrigée par cette US."""
    for entree in ACTIONS_VALIDES:
        assert normalize_action(entree) in ACTION_MAP, (
            f"'{entree}' est valide en entrée mais ne normalise vers aucun canonique"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — binage et eclaircie, canoniques dans les deux vocabulaires
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("geste,attendu", [("binage", "binage"), ("eclaircie", "eclaircie")])
def test_ca2_binage_eclaircie_canoniques_des_deux_cotes(geste, attendu):
    assert geste in ACTION_MAP
    assert geste in ACTIONS_VALIDES
    assert normalize_action(geste) == attendu


def test_ca2_eclaircissage_normalise_vers_eclaircie_pas_l_inverse():
    """La valeur réellement stockée en base est 'eclaircie' — 'eclaircissage'
    n'est qu'une variante d'entrée, sous peine de laisser la ligne existante
    orpheline (constat du backlog)."""
    assert normalize_action("eclaircissage") == "eclaircie"
    assert "eclaircissage" not in ACTION_MAP  # ce n'est pas la clé canonique


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — repli passant conservé, mais jamais silencieux
# ─────────────────────────────────────────────────────────────────────────────

def test_ca4_repli_passant_journalise_les_actions_inconnues(caplog):
    with caplog.at_level("WARNING", logger="potager"):
        result = normalize_action("un geste totalement inconnu")
    assert result == "un geste totalement inconnu"  # repli passant conservé
    assert any("repli passant" in r.message for r in caplog.records)


# ─────────────────────────────────────────────────────────────────────────────
# CA5 / CA6 — normalisation d'unité à l'écriture (hors semis)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brut,attendu", [("pied", "plants"), ("pieds", "plants"), ("plants", "plants")])
def test_ca5_ca6_pied_pieds_normalises_en_plants_hors_semis(brut, attendu):
    assert _normalize_unite_denombrement(brut, "plantation") == attendu
    assert _normalize_unite_denombrement(brut, "recolte") == attendu


def test_ca7_semis_garde_sa_propre_convention_pieds():
    """Hors périmètre : la normalisation dénombrement ne touche jamais un
    semis, qui a sa propre convention (US-037, _normalize_unite_semis)."""
    assert _normalize_unite_denombrement("pied", "semis") == "pied"


def test_ca7_autres_unites_inchangees():
    for unite in ("g", "kg", "graines", "m²", None):
        assert _normalize_unite_denombrement(unite, "recolte") == unite


def test_ca6_normalisation_appliquee_a_l_ecriture(test_db):
    """Un événement écrit via le chemin de confirmation (bot.py) stocke déjà
    'plants', jamais 'pied' — la normalisation a lieu à l'écriture, pas
    seulement à la lecture (CA6)."""
    parcelle = Parcelle(nom="Sud", nom_normalise="sud", potager_id=1, actif=True)
    test_db.add(parcelle)
    test_db.commit()
    test_db.add(Evenement(type_action="plantation", culture="thym", quantite=1, unite="plants",
                           potager_id=1, parcelle_id=parcelle.id))
    test_db.commit()

    parsed = {"action": "plantation", "culture": "thym", "quantite": 1, "unite": "pied"}
    event = creer_evenement_confirme(test_db, CTX, parsed, "planté 1 pied de thym", parcelle)

    assert event.unite == "plants"


# ─────────────────────────────────────────────────────────────────────────────
# CA9 / CA10 / CA11 — le regroupement et le gabarit rendent le bon chiffre
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def potager_thym_menthe(test_db):
    """[CA6] Les deux lignes en 'pied'/'plants' passent par le chemin d'écriture
    réel (creer_evenement_confirme) : c'est LUI qui normalise, pas l'agrégation
    (CA7 — aucune conversion à la lecture). Reproduit le cas exact du backlog :
    1 'plants' + 1 'pied' de thym dictés séparément."""
    test_db.add_all([
        CultureConfig(nom="thym", type_organe_recolte="végétatif", potager_id=None),
        CultureConfig(nom="menthe", type_organe_recolte="végétatif", potager_id=None),
    ])
    test_db.commit()
    for unite_brute in ("plants", "pied"):
        parsed = {"action": "plantation", "culture": "thym", "quantite": 1, "unite": unite_brute}
        creer_evenement_confirme(test_db, CTX, parsed, f"planté 1 {unite_brute} de thym", None)
    creer_evenement_confirme(
        test_db, CTX,
        {"action": "plantation", "culture": "menthe", "quantite": 1, "unite": "plants"},
        "planté 1 plants de menthe", None,
    )
    return test_db


def test_ca9_ca11_regroupement_par_unite_sans_doublon_ni_avertissement(potager_thym_menthe, caplog):
    """[US-037 CA2] Le garde-fou ne doit plus se déclencher sur pied/pieds/plants :
    tant qu'il se déclenche, une quantité est exclue du total en silence."""
    with caplog.at_level("WARNING", logger="potager"):
        stocks = calcul_stock_cultures(potager_thym_menthe, potager_id=1)
    assert not any("US-037 CA2" in r.message for r in caplog.records)
    assert stocks["thym"].unite == "plants"
    assert stocks["thym"].stock_plants == 2  # les deux lignes comptées ensemble


def test_ca10_gabarit_stock_meme_chiffre_meme_unite_thym_menthe(potager_thym_menthe):
    """Cas nommé du backlog : « quel est mon stock de thym ? » doit répondre 2,
    avec la même unité affichée que pour la menthe."""
    reponse_thym = rc.repondre_chiffre(CTX, "il me reste combien de thym ?", db=potager_thym_menthe)
    reponse_menthe = rc.repondre_chiffre(CTX, "il me reste combien de menthe ?", db=potager_thym_menthe)

    assert "2 plants" in reponse_thym.texte
    assert "plants" in reponse_menthe.texte


# ─────────────────────────────────────────────────────────────────────────────
# CA12 — binage/eclaircie : de la dictée au type_action en base
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("geste", ["binage", "eclaircie"])
def test_ca12_geste_hors_ancien_referentiel_enregistre_bout_en_bout(test_db, geste):
    texte = f"j'ai fait un {geste} sur la parcelle 3"
    item = {"action": geste, "culture": None, "quantite": None, "unite": None, "date": None}

    # 1. La saisie traverse la validation (utils/validation.py, vocabulaire d'ENTRÉE).
    is_valid, reason = validate_parsed_action(item, texte)
    assert is_valid, reason

    # 2. Puis la normalisation à l'écriture (utils/actions.py, vocabulaire de SORTIE).
    parsed = {"action": geste, "culture": None, "quantite": None, "unite": None, "date": None}
    event = creer_evenement_confirme(test_db, CTX, parsed, texte, None)

    assert event.type_action == geste


# ─────────────────────────────────────────────────────────────────────────────
# CA13 — le routeur n'a plus besoin d'un supplément lexical séparé
# ─────────────────────────────────────────────────────────────────────────────

def test_ca13_supplement_temporaire_du_routeur_a_disparu():
    assert not hasattr(routeur, "_GESTES_HORS_REFERENTIEL")


@pytest.mark.parametrize("texte", [
    "Binage effectué sur les rangs d'oignons il y a 4 jours",
    "eclaircie des carottes ce matin",
])
def test_ca13_gestes_absorbes_restent_route_en_action(texte):
    """Les entrées du supplément disparu (binage, eclaircie...) routent toujours
    correctement une fois versées dans ACTION_MAP, sans appel modèle."""
    with patch("llm.passerelle.appeler_chat") as mock_modele:
        decision = routeur.classer_demande(texte, ctx=CTX)
    mock_modele.assert_not_called()
    assert decision.nature == NATURE_ACTION
    assert decision.origine == "regle"
