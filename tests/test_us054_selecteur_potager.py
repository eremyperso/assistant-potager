"""
tests/test_us054_selecteur_potager.py — [US-054] Sélecteur de potager en menu déroulant
---------------------------------------------------------------------------------------
Couvre CA1 côté backend : les compteurs de parcelles et de membres exposés par
`GET /potagers` pour que le menu déroulant puisse afficher, par potager, son rôle,
son nombre de parcelles et son nombre de membres.

Le reste de l'US (rendu du menu, troncature, bascule) est purement frontend et
relève de la validation visuelle du QA-tester.
"""
import pytest

from app.services import potager_actif as svc_potager_actif
from database.models import Parcelle, Potager, PotagerMembre, User


def _creer_user(db, email="jardinier@example.com"):
    user = User(email=email, mot_de_passe_hash="x")
    db.add(user)
    db.commit()
    return user


def _creer_potager(db, nom, proprietaire_id, membre_id=None, role="owner"):
    potager = Potager(nom=nom, proprietaire_id=proprietaire_id)
    db.add(potager)
    db.commit()
    db.add(PotagerMembre(user_id=membre_id or proprietaire_id, potager_id=potager.id, role=role))
    db.commit()
    return potager


def _creer_parcelle(db, nom, potager_id, actif=True):
    parcelle = Parcelle(nom=nom, nom_normalise=nom.lower(), potager_id=potager_id, actif=actif)
    db.add(parcelle)
    db.commit()
    return parcelle


# ── CA1 — Comptage des parcelles ──────────────────────────────────────────

def test_us054_ca1_compte_les_parcelles_actives_par_potager(test_db):
    user = _creer_user(test_db)
    potager_a = _creer_potager(test_db, "Jardin nord", user.id)
    potager_b = _creer_potager(test_db, "Jardin sud", user.id)
    _creer_parcelle(test_db, "Planche 1", potager_a.id)
    _creer_parcelle(test_db, "Planche 2", potager_a.id)
    _creer_parcelle(test_db, "Butte", potager_b.id)

    compteurs = svc_potager_actif.compter_parcelles_par_potager(
        test_db, [potager_a.id, potager_b.id]
    )

    assert compteurs[potager_a.id] == 2
    assert compteurs[potager_b.id] == 1


def test_us054_ca1_les_parcelles_desactivees_ne_sont_pas_comptees(test_db):
    """Une parcelle supprimée en douceur (`actif = False`) ne doit plus peser
    dans le compteur affiché à l'utilisateur."""
    user = _creer_user(test_db)
    potager = _creer_potager(test_db, "Jardin", user.id)
    _creer_parcelle(test_db, "Active", potager.id, actif=True)
    _creer_parcelle(test_db, "Supprimee", potager.id, actif=False)

    compteurs = svc_potager_actif.compter_parcelles_par_potager(test_db, [potager.id])

    assert compteurs[potager.id] == 1


def test_us054_ca1_potager_sans_parcelle_absent_du_dictionnaire(test_db):
    """L'appelant doit retomber sur 0 — on ne fabrique pas de clé à 0 côté service."""
    user = _creer_user(test_db)
    potager = _creer_potager(test_db, "Jardin vide", user.id)

    compteurs = svc_potager_actif.compter_parcelles_par_potager(test_db, [potager.id])

    assert compteurs.get(potager.id, 0) == 0


# ── CA1 — Comptage des membres ────────────────────────────────────────────

def test_us054_ca1_compte_tous_les_membres_quel_que_soit_le_role(test_db):
    proprietaire = _creer_user(test_db, "owner@example.com")
    editeur = _creer_user(test_db, "editeur@example.com")
    lecteur = _creer_user(test_db, "lecteur@example.com")
    potager = _creer_potager(test_db, "Jardin partage", proprietaire.id)
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    test_db.add(PotagerMembre(user_id=lecteur.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()

    compteurs = svc_potager_actif.compter_membres_par_potager(test_db, [potager.id])

    assert compteurs[potager.id] == 3


def test_us054_ca1_compteurs_isoles_entre_potagers(test_db):
    """Non-régression multi-tenant : les compteurs d'un potager ne doivent jamais
    inclure les parcelles ou membres d'un autre."""
    user = _creer_user(test_db)
    autre = _creer_user(test_db, "autre@example.com")
    potager_a = _creer_potager(test_db, "Jardin A", user.id)
    potager_b = _creer_potager(test_db, "Jardin B", autre.id)
    _creer_parcelle(test_db, "Planche A", potager_a.id)
    _creer_parcelle(test_db, "Planche B1", potager_b.id)
    _creer_parcelle(test_db, "Planche B2", potager_b.id)

    parcelles = svc_potager_actif.compter_parcelles_par_potager(test_db, [potager_a.id])
    membres = svc_potager_actif.compter_membres_par_potager(test_db, [potager_a.id])

    assert parcelles == {potager_a.id: 1}
    assert membres == {potager_a.id: 1}


# ── Robustesse ────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "fonction",
    [
        svc_potager_actif.compter_parcelles_par_potager,
        svc_potager_actif.compter_membres_par_potager,
    ],
)
def test_us054_liste_vide_ne_declenche_aucune_requete(test_db, fonction):
    """Cas de l'utilisateur sans aucun potager (CA5 de US-046) : pas de requête
    inutile avec un `IN ()` vide, qui est un piège SQL classique."""
    assert fonction(test_db, []) == {}
