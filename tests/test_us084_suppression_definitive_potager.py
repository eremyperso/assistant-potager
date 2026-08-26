"""
tests/test_us084_suppression_definitive_potager.py — [US-084] Supprimer
définitivement un potager avec délai de grâce
--------------------------------------------------------------------------------
Couvre CA1 (archivage préalable obligatoire, owner-only), CA2 (soft-delete sans
destruction), CA3 (décompte réel), CA4 (re-saisie du mot de passe et abandon au
3e échec), CA5 (disparition pour tous les membres + invalidation du potager
actif), CA6 (restauration vers l'état archivé), CA7 (purge physique à J+30 avec
journalisation des volumes), CA8 (purge idempotente et rejouable), CA9
(notification Telegram best-effort) et CA10 (editor/lecteur exclus, API comme
UI — le volet UI relevant de la validation visuelle QA).

Le « CA type » (écran de confirmation visuellement distinct, lisible à
375/768/desktop) n'est pas testable en pytest : il relève du volet frontend du
rapport QA.
"""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import CultureConfig, Evenement, Invitation, Parcelle, Potager, PotagerMembre, User

MOT_DE_PASSE = "motdepasse123"


@pytest.fixture(autouse=True)
def _reset_compteur_echecs():
    """[CA4] Le compteur d'échecs vit dans le process : deux tests ne doivent
    jamais hériter des tentatives l'un de l'autre."""
    svc_potagers._echecs_mot_de_passe.clear()
    yield
    svc_potagers._echecs_mot_de_passe.clear()


@pytest.fixture(autouse=True)
def _telegram_muet(monkeypatch):
    """Aucun appel réseau sortant pendant les tests — CA9 le vérifie explicitement
    en réinstallant son propre espion."""
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: True)


def _creer_user(db, email="jardinier@example.com", mot_de_passe=MOT_DE_PASSE, **kwargs):
    user = User(email=email, mot_de_passe_hash=svc_auth.hash_password(mot_de_passe), **kwargs)
    db.add(user)
    db.commit()
    return user


def _potager_archive(db, owner, nom="Ancien jardin"):
    potager = svc_potagers.creer_potager(db, owner.id, nom)
    svc_potagers.archiver_potager(db, owner.id, potager.id)
    return potager


# ── CA1 — Archivage préalable obligatoire, owner uniquement ─────────────────

def test_ca1_owner_supprime_un_potager_archive(test_db):
    """Scénario Gherkin « Supprimer un potager archivé »."""
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)

    resultat = svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    assert resultat.etat == "supprime"
    assert resultat.supprime_le is not None


def test_ca1_suppression_refusee_sur_un_potager_actif(test_db):
    """Scénario Gherkin « Suppression refusée sur un potager actif »."""
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin en cours d'usage")

    with pytest.raises(svc_potagers.PotagerNonArchiveError) as err:
        svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    assert "archivé" in str(err.value)  # invite à archiver d'abord
    test_db.refresh(potager)
    assert potager.etat == "actif"


def test_ca1_suppression_refusee_sur_un_potager_deja_supprime(test_db):
    """Edge case : rejouer la suppression ne relance pas le délai de grâce."""
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)
    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)
    premiere_date = potager.supprime_le

    with pytest.raises(svc_potagers.PotagerNonArchiveError):
        svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    test_db.refresh(potager)
    assert potager.supprime_le == premiere_date


# ── CA10 — Un editor ou un lecteur ne peut jamais supprimer ─────────────────

@pytest.mark.parametrize("role", ["editor", "lecteur"])
def test_ca10_non_owner_ne_peut_pas_supprimer(test_db, role):
    """Scénario Gherkin « Un editor ne peut pas supprimer » — étendu au lecteur."""
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email=f"{role}@example.com")
    potager = _potager_archive(test_db, owner, "Jardin partagé")
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=potager.id, role=role))
    test_db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.supprimer_potager(test_db, membre.id, potager.id, MOT_DE_PASSE)

    test_db.refresh(potager)
    assert potager.etat == "archive"


def test_ca10_non_membre_ne_peut_pas_supprimer(test_db):
    """Cas d'erreur : un utilisateur totalement étranger au potager."""
    owner = _creer_user(test_db, email="owner@example.com")
    etranger = _creer_user(test_db, email="etranger@example.com")
    potager = _potager_archive(test_db, owner)

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.supprimer_potager(test_db, etranger.id, potager.id, MOT_DE_PASSE)


# ── CA2 — Soft-delete : aucune donnée détruite à cet instant ────────────────

def test_ca2_aucune_donnee_detruite_a_la_suppression_logique(test_db):
    owner = _creer_user(test_db)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin plein")
    parcelle = Parcelle(nom="Planche A", nom_normalise="planchea", potager_id=potager.id)
    test_db.add(parcelle)
    test_db.add(Evenement(type_action="recolte", culture="tomate", potager_id=potager.id))
    test_db.commit()
    svc_potagers.archiver_potager(test_db, owner.id, potager.id)

    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    assert test_db.query(Evenement).filter(Evenement.potager_id == potager.id).count() == 1
    assert test_db.query(Parcelle).filter(Parcelle.potager_id == potager.id).count() == 1
    assert test_db.query(PotagerMembre).filter(PotagerMembre.potager_id == potager.id).count() == 1
    assert test_db.query(Potager).filter(Potager.id == potager.id).first() is not None


# ── CA3 — Décompte réel, jamais approximé ──────────────────────────────────

def test_ca3_decompte_reel_de_ce_qui_sera_perdu(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin collectif")
    autre = svc_potagers.creer_potager(test_db, owner.id, "Autre jardin", activer=False)
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=potager.id, role="editor"))
    for i in range(3):
        test_db.add(Parcelle(nom=f"P{i}", nom_normalise=f"p{i}", potager_id=potager.id))
    for _ in range(7):
        test_db.add(Evenement(type_action="semis", culture="carotte", potager_id=potager.id))
    # Bruit : données d'un AUTRE potager, jamais comptées ici.
    test_db.add(Evenement(type_action="semis", culture="radis", potager_id=autre.id))
    test_db.commit()

    impact = svc_potagers.compter_impact_suppression(test_db, owner.id, potager.id)

    assert impact["nb_evenements"] == 7
    assert impact["nb_parcelles"] == 3
    assert impact["nb_membres"] == 2
    # Aucun stockage de photos dans le modèle : le compte réel est nul, pas approximé.
    assert impact["nb_photos"] == 0
    assert impact["delai_grace_jours"] == 30
    assert impact["nom"] == "Jardin collectif"


def test_ca3_decompte_reserve_a_lowner(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    lecteur = _creer_user(test_db, email="lecteur@example.com")
    potager = _potager_archive(test_db, owner)
    test_db.add(PotagerMembre(user_id=lecteur.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.compter_impact_suppression(test_db, lecteur.id, potager.id)


# ── CA4 — Re-saisie du mot de passe, abandon au 3e échec ───────────────────

def test_ca4_mot_de_passe_errone_refuse_la_suppression(test_db):
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)

    with pytest.raises(svc_potagers.MotDePasseInvalideError) as err:
        svc_potagers.supprimer_potager(test_db, owner.id, potager.id, "pas-le-bon")

    assert err.value.tentatives_restantes == 2
    test_db.refresh(potager)
    assert potager.etat == "archive"  # rien n'a bougé


def test_ca4_trois_echecs_consecutifs_abandonnent_loperation(test_db):
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)

    for restantes in (2, 1):
        with pytest.raises(svc_potagers.MotDePasseInvalideError) as err:
            svc_potagers.supprimer_potager(test_db, owner.id, potager.id, "faux")
        assert err.value.tentatives_restantes == restantes

    with pytest.raises(svc_potagers.TropDEchecsMotDePasseError):
        svc_potagers.supprimer_potager(test_db, owner.id, potager.id, "faux")

    test_db.refresh(potager)
    assert potager.etat == "archive"


def test_ca4_un_succes_remet_le_compteur_a_zero(test_db):
    """Un échec isolé ne pénalise pas la suppression suivante, correctement confirmée."""
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)

    with pytest.raises(svc_potagers.MotDePasseInvalideError):
        svc_potagers.supprimer_potager(test_db, owner.id, potager.id, "faux")

    resultat = svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    assert resultat.etat == "supprime"
    assert svc_potagers._echecs_mot_de_passe == {}


def test_ca4_compte_sans_mot_de_passe_web_ne_peut_pas_confirmer(test_db):
    """Edge case : owner Telegram-only (US-045), aucun mot de passe web à re-saisir."""
    owner = User(email=None, telegram_chat_id=777)
    test_db.add(owner)
    test_db.commit()
    potager = _potager_archive(test_db, owner)

    with pytest.raises(svc_potagers.MotDePasseInvalideError):
        svc_potagers.supprimer_potager(test_db, owner.id, potager.id, "peu importe")

    test_db.refresh(potager)
    assert potager.etat == "archive"


# ── CA5 — Disparition pour tous les membres, potager actif invalidé ────────

def test_ca5_disparait_de_toutes_les_listes_y_compris_etat_tous(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    potager = _potager_archive(test_db, owner)
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=potager.id, role="editor"))
    test_db.commit()

    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    for user in (owner, membre):
        for filtre in ("actif", "archive", "tous"):
            listes = svc_potager_actif.lister_potagers_utilisateur(test_db, user.id, filtre)
            assert all(p.id != potager.id for p in listes), f"visible pour {user.email} avec etat={filtre}"
    # [CA5 / US-082 CA7] Le détail direct le traite lui aussi comme inexistant.
    assert svc_potager_actif.obtenir_potager(test_db, owner.id, potager.id) is None


def test_ca5_invalide_le_potager_actif_de_chaque_membre_concerne(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin partagé")
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=potager.id, role="editor"))
    membre.potager_actif_id = potager.id
    test_db.commit()
    svc_potagers.archiver_potager(test_db, owner.id, potager.id)
    # L'archivage a déjà invalidé les pointeurs (US-083/CA5) : on les réarme pour
    # vérifier que la suppression fait le même travail de son côté.
    owner.potager_actif_id = potager.id
    membre.potager_actif_id = potager.id
    test_db.commit()

    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    test_db.refresh(owner)
    test_db.refresh(membre)
    assert owner.potager_actif_id is None
    assert membre.potager_actif_id is None


def test_ca5_un_potager_supprime_ne_peut_plus_devenir_actif(test_db):
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)
    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    with pytest.raises(svc_potager_actif.PotagerNonMembreError):
        svc_potager_actif.definir_potager_actif(test_db, owner.id, potager.id)


# ── CA6 — Droit au remords ─────────────────────────────────────────────────

def test_ca6_restaurer_repasse_a_archive_jamais_a_actif(test_db):
    """Scénario Gherkin « Droit au remords »."""
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)
    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    resultat = svc_potagers.restaurer_potager(test_db, owner.id, potager.id)

    assert resultat.etat == "archive"
    assert resultat.supprime_le is None
    # Redevient consultable en lecture seule, jamais activable directement.
    assert svc_potager_actif.obtenir_potager(test_db, owner.id, potager.id)["etat"] == "archive"
    with pytest.raises(svc_potager_actif.PotagerInactifError):
        svc_potager_actif.definir_potager_actif(test_db, owner.id, potager.id)


def test_ca6_corbeille_liste_les_potagers_supprimes_de_lowner(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    supprime = _potager_archive(test_db, owner, "Jardin supprimé")
    archive = _potager_archive(test_db, owner, "Jardin archivé")
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=supprime.id, role="editor"))
    test_db.commit()
    svc_potagers.supprimer_potager(test_db, owner.id, supprime.id, MOT_DE_PASSE)

    corbeille = svc_potagers.lister_potagers_supprimes(test_db, owner.id)

    assert [p["id"] for p in corbeille] == [supprime.id]  # l'archivé n'y est pas
    assert corbeille[0]["purge_prevue_le"] == corbeille[0]["supprime_le"] + timedelta(days=30)
    # [CA6] Seul l'owner peut restaurer : la corbeille d'un editor reste vide.
    assert svc_potagers.lister_potagers_supprimes(test_db, membre.id) == []


def test_ca6_restauration_refusee_sur_un_potager_non_supprime(test_db):
    owner = _creer_user(test_db)
    potager = _potager_archive(test_db, owner)

    with pytest.raises(svc_potagers.PotagerNonSupprimeError):
        svc_potagers.restaurer_potager(test_db, owner.id, potager.id)


def test_ca6_restauration_reservee_a_lowner(test_db):
    owner = _creer_user(test_db, email="owner@example.com")
    editeur = _creer_user(test_db, email="editor@example.com")
    potager = _potager_archive(test_db, owner)
    test_db.add(PotagerMembre(user_id=editeur.id, potager_id=potager.id, role="editor"))
    test_db.commit()
    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    with pytest.raises(PermissionInsuffisanteError):
        svc_potagers.restaurer_potager(test_db, editeur.id, potager.id)


# ── CA7 — Purge physique après 30 jours ────────────────────────────────────

def _potager_supprime_depuis(db, owner, jours: int, nom="Jardin à purger"):
    """Potager supprimé il y a `jours` jours — la date est reculée directement en
    base plutôt que par un gel du temps : c'est `supprime_le` qui pilote la purge."""
    potager = _potager_archive(db, owner, nom)
    svc_potagers.supprimer_potager(db, owner.id, potager.id, MOT_DE_PASSE)
    potager.supprime_le = datetime.utcnow() - timedelta(days=jours)
    db.commit()
    return potager


def test_ca7_purge_efface_le_potager_et_toutes_ses_donnees(test_db):
    """Scénario Gherkin « Purge après le délai de grâce »."""
    owner = _creer_user(test_db, email="owner@example.com")
    membre = _creer_user(test_db, email="membre@example.com")
    potager = _potager_archive(test_db, owner, "Jardin condamné")
    test_db.add(PotagerMembre(user_id=membre.id, potager_id=potager.id, role="editor"))
    test_db.add(Parcelle(nom="Planche A", nom_normalise="planchea", potager_id=potager.id))
    test_db.add(Evenement(type_action="recolte", culture="tomate", potager_id=potager.id))
    test_db.add(Evenement(type_action="semis", culture="radis", potager_id=potager.id))
    test_db.add(CultureConfig(nom="tomate-maison", type_organe_recolte="reproducteur", potager_id=potager.id))
    test_db.add(Invitation(
        code="ABCD2345", potager_id=potager.id, invite_par_id=owner.id,
        role_propose="editor", expire_le=datetime.utcnow() + timedelta(days=7),
    ))
    test_db.commit()
    svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)
    potager.supprime_le = datetime.utcnow() - timedelta(days=31)
    test_db.commit()

    resultats = svc_potagers.purger_potagers_supprimes(test_db)

    assert len(resultats) == 1
    # [CA7] Volumes journalisés — la seule trace qui subsiste après effacement.
    # [US-097 / CA3] routage_logs/routage_retours purgés avec le potager, à 0 ici (aucun n'en a été créé).
    assert resultats[0]["volumes"] == {
        "evenements": 2, "parcelles": 1, "invitations": 1, "culture_config": 1, "membres": 2,
        "routage_retours": 0, "routage_logs": 0,
    }
    assert test_db.query(Potager).filter(Potager.id == potager.id).first() is None
    assert test_db.query(Evenement).filter(Evenement.potager_id == potager.id).count() == 0
    assert test_db.query(Parcelle).filter(Parcelle.potager_id == potager.id).count() == 0
    assert test_db.query(Invitation).filter(Invitation.potager_id == potager.id).count() == 0
    assert test_db.query(CultureConfig).filter(CultureConfig.potager_id == potager.id).count() == 0
    assert test_db.query(PotagerMembre).filter(PotagerMembre.potager_id == potager.id).count() == 0
    # Aucun orphelin : les pointeurs `potager_actif_id` sont retombés à NULL.
    assert test_db.query(User).filter(User.potager_actif_id == potager.id).count() == 0


def test_ca7_purge_journalise_le_volume_supprime(test_db, caplog):
    owner = _creer_user(test_db)
    potager = _potager_supprime_depuis(test_db, owner, jours=31)

    with caplog.at_level("INFO", logger="potager"):
        svc_potagers.purger_potagers_supprimes(test_db)

    traces = [r.getMessage() for r in caplog.records if "Purge physique" in r.getMessage()]
    assert len(traces) == 1
    assert f"potager_id={potager.id}" in traces[0]
    assert "Jardin à purger" in traces[0]


def test_ca7_purge_ne_touche_pas_les_potagers_actifs_ou_archives(test_db):
    owner = _creer_user(test_db)
    actif = svc_potagers.creer_potager(test_db, owner.id, "Jardin actif")
    archive = _potager_archive(test_db, owner, "Jardin archivé")

    assert svc_potagers.purger_potagers_supprimes(test_db) == []

    assert test_db.query(Potager).filter(Potager.id == actif.id).first() is not None
    assert test_db.query(Potager).filter(Potager.id == archive.id).first() is not None


# ── CA8 — Purge idempotente et rejouable ───────────────────────────────────

def test_ca8_purge_rejouee_ne_leve_aucune_erreur(test_db):
    """Scénario Gherkin « Purge après le délai de grâce », dernier volet."""
    owner = _creer_user(test_db)
    _potager_supprime_depuis(test_db, owner, jours=31)

    premier = svc_potagers.purger_potagers_supprimes(test_db)
    second = svc_potagers.purger_potagers_supprimes(test_db)

    assert len(premier) == 1
    assert second == []  # plus rien à purger, aucune exception


def test_ca8_purge_epargne_un_potager_encore_dans_son_delai_de_grace(test_db):
    owner = _creer_user(test_db)
    recent = _potager_supprime_depuis(test_db, owner, jours=29, nom="Supprimé hier ou presque")
    ancien = _potager_supprime_depuis(test_db, owner, jours=30, nom="Pile au terme du délai")

    resultats = svc_potagers.purger_potagers_supprimes(test_db)

    assert [r["potager_id"] for r in resultats] == [ancien.id]
    survivant = test_db.query(Potager).filter(Potager.id == recent.id).first()
    assert survivant is not None and survivant.etat == "supprime"


def test_ca8_purge_dun_potager_inexistant_est_sans_effet(test_db):
    """Cas d'erreur : purge ciblée sur un identifiant déjà effacé."""
    assert svc_potagers.purger_potager(test_db, 4242) == {"potager_id": 4242, "purge": False}


def test_ca6_ca8_potager_restaure_echappe_definitivement_a_la_purge(test_db):
    """La restauration ne se contente pas de changer l'état : elle efface
    `supprime_le`, donc la purge ne peut plus le sélectionner."""
    owner = _creer_user(test_db)
    potager = _potager_supprime_depuis(test_db, owner, jours=31)

    svc_potagers.restaurer_potager(test_db, owner.id, potager.id)
    resultats = svc_potagers.purger_potagers_supprimes(test_db)

    assert resultats == []
    assert test_db.query(Potager).filter(Potager.id == potager.id).first() is not None


# ── CA9 — Notification Telegram best-effort ────────────────────────────────

def test_ca9_notifie_les_autres_membres_lies_a_telegram(test_db, monkeypatch):
    owner = _creer_user(test_db, email="owner@example.com", nom="Emmanuel")
    lie = _creer_user(test_db, email="lie@example.com", telegram_chat_id=555)
    non_lie = _creer_user(test_db, email="nonlie@example.com")
    potager = _potager_archive(test_db, owner, "Jardin de tous")
    test_db.add(PotagerMembre(user_id=lie.id, potager_id=potager.id, role="editor"))
    test_db.add(PotagerMembre(user_id=non_lie.id, potager_id=potager.id, role="lecteur"))
    test_db.commit()

    appels = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: appels.append((chat_id, texte)) or True,
    )

    potager = svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    assert len(appels) == 1  # l'acteur ne se notifie pas lui-même
    chat_id, texte = appels[0]
    assert chat_id == 555
    assert "Emmanuel" in texte              # l'auteur
    assert "Jardin de tous" in texte        # le nom du potager
    purge_le = svc_potagers.date_purge_prevue(potager)
    assert purge_le.strftime("%d/%m/%Y") in texte  # la date effective de purge


def test_ca9_panne_telegram_ne_fait_jamais_echouer_la_suppression(test_db, monkeypatch):
    """Cas d'erreur : `envoyer_message` est best-effort et absorbe déjà ses
    propres pannes réseau — la suppression aboutit quoi qu'il arrive."""
    owner = _creer_user(test_db, email="owner@example.com")
    lie = _creer_user(test_db, email="lie@example.com", telegram_chat_id=555)
    potager = _potager_archive(test_db, owner)
    test_db.add(PotagerMembre(user_id=lie.id, potager_id=potager.id, role="editor"))
    test_db.commit()
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: False)

    resultat = svc_potagers.supprimer_potager(test_db, owner.id, potager.id, MOT_DE_PASSE)

    assert resultat.etat == "supprime"


# ── Endpoints web ──────────────────────────────────────────────────────────

@pytest.fixture
def _auth_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def app_client(_auth_engine, monkeypatch):
    import main
    TestSessionLocal = sessionmaker(bind=_auth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _compte_web(db, email="jardinier@example.com"):
    return svc_auth.inscrire_utilisateur(db, email, MOT_DE_PASSE)


def _auth_header(user_id):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


def _potager_archive_http(client, headers, nom="Jardin à supprimer"):
    potager_id = client.post("/potagers", json={"nom": nom}, headers=headers).json()["id"]
    client.post(f"/potagers/{potager_id}/archiver", headers=headers)
    return potager_id


def test_endpoint_impact_puis_suppression_puis_restauration(app_client, _auth_engine):
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _compte_web(db)
    headers = _auth_header(user.id)
    db.close()
    potager_id = _potager_archive_http(app_client, headers)

    # [CA3] Décompte avant confirmation
    resp = app_client.get(f"/potagers/{potager_id}/impact-suppression", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["nb_membres"] == 1
    assert resp.json()["delai_grace_jours"] == 30

    # [CA1, CA2] Suppression logique
    resp = app_client.request(
        "DELETE", f"/potagers/{potager_id}", json={"mot_de_passe": MOT_DE_PASSE}, headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["etat"] == "supprime"
    assert resp.json()["supprime_le"] is not None
    assert resp.json()["purge_prevue_le"] is not None

    # [CA5] Invisible partout, y compris etat=tous
    assert all(p["id"] != potager_id for p in app_client.get("/potagers?etat=tous", headers=headers).json()["potagers"])
    assert app_client.get(f"/potagers/{potager_id}", headers=headers).status_code == 403

    # [CA6] Corbeille puis restauration
    corbeille = app_client.get("/potagers/corbeille", headers=headers).json()
    assert [p["id"] for p in corbeille["potagers"]] == [potager_id]
    resp = app_client.post(f"/potagers/{potager_id}/restaurer", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["etat"] == "archive"
    assert resp.json()["supprime_le"] is None
    assert app_client.get("/potagers/corbeille", headers=headers).json()["potagers"] == []


def test_endpoint_suppression_refusee_sur_potager_actif(app_client, _auth_engine):
    """[CA1] 409 : les droits sont là, c'est l'état qui bloque."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _compte_web(db)
    headers = _auth_header(user.id)
    db.close()
    potager_id = app_client.post("/potagers", json={"nom": "Jardin actif"}, headers=headers).json()["id"]

    resp = app_client.request(
        "DELETE", f"/potagers/{potager_id}", json={"mot_de_passe": MOT_DE_PASSE}, headers=headers,
    )

    assert resp.status_code == 409


def test_endpoint_suppression_refuse_un_editor(app_client, _auth_engine):
    """[CA10] Refus explicite côté API, indépendamment de l'UI."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    owner = _compte_web(db, email="owner@example.com")
    editeur = _compte_web(db, email="editor@example.com")
    headers_owner = _auth_header(owner.id)
    headers_editeur = _auth_header(editeur.id)
    db.close()
    potager_id = _potager_archive_http(app_client, headers_owner, "Jardin partagé")

    db = SessionLocal()
    db.add(PotagerMembre(user_id=editeur.id, potager_id=potager_id, role="editor"))
    db.commit()
    db.close()

    resp = app_client.request(
        "DELETE", f"/potagers/{potager_id}", json={"mot_de_passe": MOT_DE_PASSE}, headers=headers_editeur,
    )
    assert resp.status_code == 403
    # [CA10] Le décompte lui est également refusé.
    assert app_client.get(f"/potagers/{potager_id}/impact-suppression", headers=headers_editeur).status_code == 403


def test_endpoint_mot_de_passe_errone_puis_abandon(app_client, _auth_engine):
    """[CA4] Codes distincts : tentative refusée, puis opération abandonnée."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _compte_web(db)
    headers = _auth_header(user.id)
    db.close()
    potager_id = _potager_archive_http(app_client, headers)

    for attendu in (2, 1):
        resp = app_client.request(
            "DELETE", f"/potagers/{potager_id}", json={"mot_de_passe": "faux"}, headers=headers,
        )
        assert resp.status_code == 403
        assert resp.json()["detail"]["code"] == "mot_de_passe_invalide"
        assert resp.json()["detail"]["tentatives_restantes"] == attendu

    resp = app_client.request(
        "DELETE", f"/potagers/{potager_id}", json={"mot_de_passe": "faux"}, headers=headers,
    )
    assert resp.status_code == 403
    assert resp.json()["detail"]["code"] == "trop_d_echecs"

    # Le potager n'a pas bougé.
    assert app_client.get(f"/potagers/{potager_id}", headers=headers).json()["etat"] == "archive"


def test_endpoint_corbeille_nest_pas_captee_par_la_route_detail(app_client, _auth_engine):
    """Non-régression d'ordre de déclaration : /potagers/corbeille doit précéder
    /potagers/{potager_id}, sinon FastAPI répond 422 sur « corbeille »."""
    SessionLocal = sessionmaker(bind=_auth_engine)
    db = SessionLocal()
    user = _compte_web(db)
    headers = _auth_header(user.id)
    db.close()

    resp = app_client.get("/potagers/corbeille", headers=headers)

    assert resp.status_code == 200
    assert resp.json() == {"potagers": [], "delai_grace_jours": 30}
