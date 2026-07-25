"""
[feedback US-038] Tests — Résolution culture/variete vers les valeurs canoniques en base.

Repro terrain : Groq extrait culture="haricot", variete="nain" depuis "sur les haricot
nain", alors que la base a déjà "haricot" / "vert nain Contender" — la résolution doit
retrouver la variété existante via mot-clé (sous-chaîne), sans que l'utilisateur n'ait
à dicter le nom exact.

[fix isolation multi-tenant] Toutes ces fonctions sont scopées à `potager_id` depuis
le bug rapporté : une récolte pouvait être enregistrée pour une culture jamais plantée
dans le potager courant dès qu'elle existait dans N'IMPORTE QUEL AUTRE potager de la
base (culture_deja_plantee/cultures_connues/varietes_connues ne filtraient jamais par
potager_id). Voir test_culture_deja_plantee_isole_par_potager ci-dessous pour la
reproduction exacte du bug + non-régression.
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

POTAGER_ID = 1


def _seed(db, potager_id=POTAGER_ID):
    db.add_all([
        Evenement(type_action="semis", culture="haricot", variete="beurre",
                   quantite=10, unite="graines", date=datetime(2026, 5, 1), potager_id=potager_id),
        Evenement(type_action="semis", culture="haricot", variete="vert nain Contender",
                   quantite=100, unite="graines", date=datetime(2026, 4, 20), potager_id=potager_id),
        Evenement(type_action="semis", culture="tomate", variete="Cœur de bœuf",
                   quantite=5, unite="graines", date=datetime(2026, 2, 1), potager_id=potager_id),
    ])
    db.commit()


def test_cultures_connues_liste_les_cultures_distinctes(test_db):
    _seed(test_db)
    assert cultures_connues(test_db, POTAGER_ID) == ["haricot", "tomate"]


def test_varietes_connues_filtre_par_culture(test_db):
    _seed(test_db)
    varietes = varietes_connues(test_db, POTAGER_ID, "haricot")
    assert varietes == ["beurre", "vert nain Contender"]


# ── culture_deja_plantee ──────────────────────────────────────────────────────
# [bug rapporté] Il était possible d'enregistrer une récolte pour une culture
# jamais semée/plantée dans le potager (hallucination Groq ou faute de frappe
# sur le nom de culture, jamais détectée).

def test_culture_deja_plantee_vrai_si_semis_existant(test_db):
    _seed(test_db)
    assert culture_deja_plantee(test_db, POTAGER_ID, "haricot") is True


def test_culture_deja_plantee_insensible_casse_accents(test_db):
    _seed(test_db)
    assert culture_deja_plantee(test_db, POTAGER_ID, "TOMATE") is True
    assert culture_deja_plantee(test_db, POTAGER_ID, "tomaté") is True


def test_culture_deja_plantee_faux_si_jamais_semee(test_db):
    _seed(test_db)
    assert culture_deja_plantee(test_db, POTAGER_ID, "mangue") is False


def test_culture_deja_plantee_ignore_recolte_seule(test_db):
    """Une récolte ne compte pas comme preuve de plantation — sinon une
    hallucination une fois enregistrée s'auto-validerait pour toujours."""
    test_db.add(Evenement(type_action="recolte", culture="mangue",
                           quantite=1, unite="kg", date=datetime(2026, 6, 1), potager_id=POTAGER_ID))
    test_db.commit()
    assert culture_deja_plantee(test_db, POTAGER_ID, "mangue") is False


def test_culture_deja_plantee_vide_ou_none(test_db):
    assert culture_deja_plantee(test_db, POTAGER_ID, "") is True
    assert culture_deja_plantee(test_db, POTAGER_ID, None) is True


# ── Isolation multi-tenant [fix bug rapporté] ──────────────────────────────────

def test_culture_deja_plantee_isole_par_potager(test_db):
    """Reproduit exactement le bug rapporté : une tomate plantée dans le potager 2
    ne doit JAMAIS neutraliser le garde-fou pour le potager 1, qui n'a rien planté."""
    test_db.add(Evenement(type_action="plantation", culture="tomate",
                           quantite=3, unite="plants", date=datetime(2026, 5, 1), potager_id=2))
    test_db.commit()

    assert culture_deja_plantee(test_db, 2, "tomate") is True       # potager 2 : planté
    assert culture_deja_plantee(test_db, 1, "tomate") is False      # potager 1 : jamais planté


def test_cultures_connues_isole_par_potager(test_db):
    _seed(test_db, potager_id=1)
    test_db.add(Evenement(type_action="semis", culture="courgette",
                           quantite=5, unite="graines", date=datetime(2026, 5, 1), potager_id=2))
    test_db.commit()

    assert "courgette" not in cultures_connues(test_db, 1)
    assert "courgette" in cultures_connues(test_db, 2)


def test_varietes_connues_isole_par_potager(test_db):
    _seed(test_db, potager_id=1)
    test_db.add(Evenement(type_action="semis", culture="haricot", variete="Contender autre potager",
                           quantite=5, unite="graines", date=datetime(2026, 5, 1), potager_id=2))
    test_db.commit()

    assert "Contender autre potager" not in varietes_connues(test_db, 1, "haricot")
    assert "Contender autre potager" in varietes_connues(test_db, 2, "haricot")


def test_resolve_culture_exact(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, POTAGER_ID, "haricot") == "haricot"


def test_resolve_culture_casse_et_accents(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, POTAGER_ID, "HARICOT") == "haricot"
    assert resolve_culture(test_db, POTAGER_ID, "tomaté") == "tomate"


def test_resolve_culture_inconnue_retourne_brute(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, POTAGER_ID, "courgette") == "courgette"


def test_resolve_culture_vide_ou_none(test_db):
    _seed(test_db)
    assert resolve_culture(test_db, POTAGER_ID, None) is None
    assert resolve_culture(test_db, POTAGER_ID, "") == ""


def test_resolve_variete_par_mot_cle_sous_chaine(test_db):
    """Repro terrain : 'nain' doit retrouver 'vert nain Contender' par sous-chaîne."""
    _seed(test_db)
    assert resolve_variete(test_db, POTAGER_ID, "haricot", "nain") == "vert nain Contender"


def test_resolve_variete_exact(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, POTAGER_ID, "haricot", "beurre") == "beurre"


def test_resolve_variete_proche_levenshtein(test_db):
    _seed(test_db)
    # "buerre" à distance 2 de "beurre" (transposition de 2 lettres)
    assert resolve_variete(test_db, POTAGER_ID, "haricot", "buerre") == "beurre"


def test_resolve_variete_inconnue_retourne_brute(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, POTAGER_ID, "haricot", "flageolet") == "flageolet"


def test_resolve_variete_sans_culture_connue_retourne_brute(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, POTAGER_ID, "courgette", "ronde") == "ronde"


def test_resolve_variete_vide_ou_none(test_db):
    _seed(test_db)
    assert resolve_variete(test_db, POTAGER_ID, "haricot", None) is None
    assert resolve_variete(test_db, POTAGER_ID, "haricot", "") == ""
