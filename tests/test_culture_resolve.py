"""
[feedback US-038] Tests — Résolution culture/variete vers les valeurs canoniques en base.

Repro terrain : Groq extrait culture="haricot", variete="nain" depuis "sur les haricot
nain", alors que la base a déjà "haricot" / "vert nain Contender" — la résolution doit
retrouver la variété existante via mot-clé (sous-chaîne), sans que l'utilisateur n'ait
à dicter le nom exact.
"""
from datetime import datetime

from database.models import Evenement
from utils.culture_resolve import (
    resolve_culture,
    resolve_variete,
    cultures_connues,
    varietes_connues,
    culture_deja_plantee,
)


def _seed(db):
    db.add_all([
        Evenement(type_action="semis", culture="haricot", variete="beurre",
                   quantite=10, unite="graines", date=datetime(2026, 5, 1)),
        Evenement(type_action="semis", culture="haricot", variete="vert nain Contender",
                   quantite=100, unite="graines", date=datetime(2026, 4, 20)),
        Evenement(type_action="semis", culture="tomate", variete="Cœur de bœuf",
                   quantite=5, unite="graines", date=datetime(2026, 2, 1)),
    ])
    db.commit()


def test_cultures_connues_liste_les_cultures_distinctes(test_db):
    _seed(test_db)
    assert cultures_connues(test_db) == ["haricot", "tomate"]


def test_varietes_connues_filtre_par_culture(test_db):
    _seed(test_db)
    varietes = varietes_connues(test_db, "haricot")
    assert varietes == ["beurre", "vert nain Contender"]


# ── culture_deja_plantee ──────────────────────────────────────────────────────
# [bug rapporté] Il était possible d'enregistrer une récolte pour une culture
# jamais semée/plantée dans le potager (hallucination Groq ou faute de frappe
# sur le nom de culture, jamais détectée).

def test_culture_deja_plantee_vrai_si_semis_existant(test_db):
    _seed(test_db)
    assert culture_deja_plantee(test_db, "haricot") is True


def test_culture_deja_plantee_insensible_casse_accents(test_db):
    _seed(test_db)
    assert culture_deja_plantee(test_db, "TOMATE") is True
    assert culture_deja_plantee(test_db, "tomaté") is True


def test_culture_deja_plantee_faux_si_jamais_semee(test_db):
    _seed(test_db)
    assert culture_deja_plantee(test_db, "mangue") is False


def test_culture_deja_plantee_ignore_recolte_seule(test_db):
    """Une récolte ne compte pas comme preuve de plantation — sinon une
    hallucination une fois enregistrée s'auto-validerait pour toujours."""
    test_db.add(Evenement(type_action="recolte", culture="mangue",
                           quantite=1, unite="kg", date=datetime(2026, 6, 1)))
    test_db.commit()
    assert culture_deja_plantee(test_db, "mangue") is False


def test_culture_deja_plantee_vide_ou_none(test_db):
    assert culture_deja_plantee(test_db, "") is True
    assert culture_deja_plantee(test_db, None) is True


def test_resolve_culture_exact(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, "haricot") == "haricot"


def test_resolve_culture_casse_et_accents(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, "HARICOT") == "haricot"
    assert resolve_culture(test_db, "tomaté") == "tomate"


def test_resolve_culture_inconnue_retourne_brute(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, "courgette") == "courgette"


def test_resolve_culture_vide_ou_none(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, None) is None
    assert resolve_culture(test_db, "") == ""


def test_resolve_variete_par_mot_cle_sous_chaine(test_db):
    """Repro terrain : 'nain' doit retrouver 'vert nain Contender' par sous-chaîne."""
    _seed(test_db)
    assert resolve_variete(test_db, "haricot", "nain") == "vert nain Contender"


def test_resolve_variete_exact(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, "haricot", "beurre") == "beurre"


def test_resolve_variete_proche_levenshtein(test_db):
    _seed(test_db)
    # "buerre" à distance 2 de "beurre" (transposition de 2 lettres)
    assert resolve_variete(test_db, "haricot", "buerre") == "beurre"


def test_resolve_variete_inconnue_retourne_brute(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, "haricot", "flageolet") == "flageolet"


def test_resolve_variete_sans_culture_connue_retourne_brute(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, "courgette", "ronde") == "ronde"


def test_resolve_variete_vide_ou_none(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, "haricot", None) is None
    assert resolve_variete(test_db, "haricot", "") == ""
