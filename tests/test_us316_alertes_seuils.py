"""
tests/test_us316_alertes_seuils.py — [US-316] Être alerté quand un seuil de contrôle est franchi.

Service `app/services/pilotage/seuils.py` (+ `notifications.py`), routes `/admin/pilotage/seuils`, tâche
`app/bot/pilotage_jobs.py`. Les envois Telegram et e-mail sont simulés : on vérifie ce qui part, pas le réseau.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.services import auth as svc_auth
from app.services.pilotage import notifications, seuils
from database.db import Base
from database.models import AlertePilotage, ConsoTokens, Potager, SeuilPilotage, User

ROOT = Path(__file__).resolve().parent.parent
J = date(2026, 11, 17)
MAINTENANT = datetime(2026, 11, 17, 12, 0)
ADMIN = "admin@example.com"


def _ligne(db, jour: date = J, *, appel_type: str = "agent", modele: str = "mistral/small", tokens_in: int = 100,
           latence_ms: int = 200, issue: str = "ok", provenance: str = "usage", canal: str = "pwa",
           echange_ref: str | None = None, cout: int | None = 1000, user_id: int = 1) -> ConsoTokens:
    ligne = ConsoTokens(
        potager_id=1, user_id=user_id, date=jour, appel_type=appel_type, modele=modele, tokens_in=tokens_in,
        tokens_out=10, tokens_cache=0, latence_ms=latence_ms, issue=issue, provenance=provenance, canal=canal,
        unite="jeton", echange_ref=echange_ref, cout_micro_eur=cout, version_app="3.133.0",
        cree_le=datetime(jour.year, jour.month, jour.day, 10, 30),
    )
    db.add(ligne)
    return ligne


@pytest.fixture
def db(test_db):
    test_db.add_all([
        Potager(id=1, nom="Potager Dupont", proprietaire_id=1),
        User(id=1, email=ADMIN, nom="Alice Dupont", telegram_chat_id=555),
    ])
    test_db.commit()
    return test_db


@pytest.fixture
def envois(monkeypatch):
    """Alertes allumées, Telegram et e-mail simulés ; rend les deux simulacres."""
    telegram, email = MagicMock(return_value=True), MagicMock(return_value=True)
    monkeypatch.setattr(config, "PILOTAGE_ALERTES", True)
    monkeypatch.setattr(config, "ADMIN_EMAIL", ADMIN)
    monkeypatch.setattr(notifications.telegram_notify, "envoyer_message", telegram)
    monkeypatch.setattr(notifications.svc_email, "envoyer_email", email)
    return telegram, email


def _gherkin(db, *, aujourd_hui: int = 8900, appels: int = 60, avant: int = 6000):
    """7 jours de référence à `avant` jetons d'entrée médians, puis le jour courant."""
    for i in range(1, 8):
        for _ in range(5):
            _ligne(db, J - timedelta(days=i), tokens_in=avant)
    for _ in range(appels):
        _ligne(db, J, tokens_in=aujourd_hui)
    db.commit()


def _seuil(db, indicateur: str, perimetre: str = "tous") -> SeuilPilotage:
    seuils.assurer_seuils_par_defaut(db)
    return db.query(SeuilPilotage).filter_by(indicateur=indicateur, perimetre=perimetre).one()


def _evenements(resultats) -> dict:
    return {ev.seuil.indicateur: evt for ev, evt in resultats if evt}


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin
# ═════════════════════════════════════════════════════════════════════════════

class TestGherkin:

    def test_us316_gherkin_telegram_email_alerte_ouverte_puis_silence(self, db, envois):
        telegram, email = envois
        _gherkin(db)
        evenements = _evenements(seuils.evaluer(db, maintenant=MAINTENANT))
        assert evenements == {"jetons_entree_mediane": "ouverte"}

        assert telegram.call_count == 1 and email.call_count == 1
        texte = telegram.call_args.args[1]
        assert "8 900" in texte and "+48 %" in texte and "6 000" in texte
        assert "/#/derives" in texte
        assert db.query(AlertePilotage).filter(AlertePilotage.resolue_le.is_(None)).count() == 1

        # L'évaluation suivante mesure encore 8 900 : aucun nouveau message.
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        assert telegram.call_count == 1 and email.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — migration et tables
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Migration:

    def test_us316_ca1_la_migration_cree_les_deux_tables_avec_leurs_colonnes(self):
        sql = (ROOT / "migrations/migration_v79.sql").read_text(encoding="utf-8")
        for colonne in ("indicateur", "perimetre", "fenetre_jours", "comparaison", "valeur", "gravite", "actif",
                        "seuil_id", "valeur_mesuree", "declenchee_le", "resolue_le", "canaux_notifies"):
            assert re.search(rf"\b{colonne}\b", sql), colonne
        assert "CREATE TABLE IF NOT EXISTS seuils_pilotage" in sql
        assert "CREATE TABLE IF NOT EXISTS alertes_pilotage" in sql

    def test_us316_ca1_le_rollback_supprime_les_deux_tables(self):
        sql = (ROOT / "migrations/rollback_v79.sql").read_text(encoding="utf-8")
        assert "DROP TABLE IF EXISTS alertes_pilotage" in sql and "DROP TABLE IF EXISTS seuils_pilotage" in sql
        assert sql.index("alertes_pilotage") < sql.index("seuils_pilotage")  # la table fille d'abord

    def test_us316_ca1_au_plus_une_alerte_ouverte_par_seuil(self, db):
        seuil = _seuil(db, "taux_erreur")
        db.add(AlertePilotage(seuil_id=seuil.id, valeur_mesuree=1, declenchee_le=MAINTENANT))
        db.commit()
        db.add(AlertePilotage(seuil_id=seuil.id, valeur_mesuree=2, declenchee_le=MAINTENANT))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_us316_ca1_une_alerte_resolue_n_empeche_pas_d_en_ouvrir_une_autre(self, db):
        seuil = _seuil(db, "taux_erreur")
        db.add(AlertePilotage(seuil_id=seuil.id, valeur_mesuree=1, declenchee_le=MAINTENANT, resolue_le=MAINTENANT))
        db.add(AlertePilotage(seuil_id=seuil.id, valeur_mesuree=2, declenchee_le=MAINTENANT))
        db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — indicateurs
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2Indicateurs:

    def test_us316_ca2_les_huit_indicateurs_minimum_existent(self):
        assert {
            "cout_jour", "cout_mois_projete", "jetons_entree_mediane", "appels_par_echange",
            "taux_quota", "taux_erreur", "latence_p95", "appels_non_chiffres",
        } <= set(seuils.INDICATEURS)

    def test_us316_ca2_chaque_indicateur_se_mesure(self, db):
        for i in range(30):
            _ligne(db, J, issue="quota" if i < 3 else ("erreur" if i < 6 else "ok"), cout=1_000_000 if i % 2 else None,
                   echange_ref=f"e{i // 3}", latence_ms=100 + i, tokens_in=1000 + i)
        db.commit()
        mesures = {i: seuils.mesurer(db, ind, "tous", J, J, aujourd_hui=J) for i, ind in seuils.INDICATEURS.items()}
        assert mesures["cout_jour"].valeur == pytest.approx(15.0)
        assert mesures["taux_quota"].valeur == pytest.approx(10.0)
        assert mesures["taux_erreur"].valeur == pytest.approx(10.0)
        assert mesures["appels_non_chiffres"].valeur == 15
        assert mesures["appels_par_echange"].valeur == 3
        assert mesures["latence_p95"].valeur is not None and mesures["jetons_entree_mediane"].valeur is not None
        assert mesures["cout_mois_projete"].valeur >= 15.0
        assert all(m.nb_appels == 30 for m in mesures.values() if m is not mesures["cout_mois_projete"])

    def test_us316_ca2_un_indicateur_par_type_ne_lit_que_ce_type(self, db):
        for _ in range(25):
            _ligne(db, J, appel_type="agent", tokens_in=9000)
            _ligne(db, J, appel_type="question", tokens_in=100)
        db.commit()
        agent = seuils.mesurer(db, seuils.INDICATEURS["jetons_entree_mediane"], "agent", J, J)
        assert agent.valeur == 9000 and agent.nb_appels == 25


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — valeur fixe ou écart aux 7 jours précédents
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3Comparaisons:

    def test_us316_ca3_valeur_fixe(self, db):
        for i in range(25):
            _ligne(db, J, issue="erreur" if i < 5 else "ok")
        db.commit()
        ev = seuils.evaluer_seuil(db, _seuil(db, "taux_erreur"), J)   # 20 % > 10 %
        assert ev.franchi is True and ev.valeur == pytest.approx(20.0) and ev.reference is None

    def test_us316_ca3_ecart_aux_7_jours_precedents(self, db):
        _gherkin(db)
        ev = seuils.evaluer_seuil(db, _seuil(db, "jetons_entree_mediane", "agent"), J)
        assert ev.reference == 6000 and ev.ecart_pct == pytest.approx(48.33, abs=0.01) and ev.franchi is True

    def test_us316_ca3_sous_l_ecart_le_seuil_n_est_pas_franchi(self, db):
        _gherkin(db, aujourd_hui=6600)    # +10 %
        ev = seuils.evaluer_seuil(db, _seuil(db, "jetons_entree_mediane", "agent"), J)
        assert ev.franchi is False

    def test_us316_ca3_une_somme_est_ramenee_a_la_moyenne_quotidienne(self, db):
        for i in range(1, 8):   # 7 jours à 1 € chacun
            for _ in range(5):
                _ligne(db, J - timedelta(days=i), cout=200_000)
        for _ in range(25):     # aujourd'hui : 25 appels à 0,2 € = 5 €
            _ligne(db, J, cout=200_000)
        db.commit()
        seuil = SeuilPilotage(indicateur="cout_jour", perimetre="tous", fenetre_jours=1, comparaison="ecart_7j",
                              valeur=100.0, gravite="haute", actif=True)
        db.add(seuil)
        db.commit()
        ev = seuils.evaluer_seuil(db, seuil, J)
        assert ev.reference == pytest.approx(1.0) and ev.ecart_pct == pytest.approx(400.0) and ev.franchi is True

    def test_us316_ca3_sans_reference_le_seuil_n_est_pas_juge(self, db):
        for _ in range(25):
            _ligne(db, J, tokens_in=9000)
        db.commit()
        ev = seuils.evaluer_seuil(db, _seuil(db, "jetons_entree_mediane", "agent"), J)
        assert ev.franchi is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — seuils par défaut
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Defauts:

    def test_us316_ca4_un_seuil_par_indicateur_tous_a_valider(self, db):
        assert seuils.assurer_seuils_par_defaut(db) == len(seuils.SEUILS_PAR_DEFAUT)
        lignes = db.query(SeuilPilotage).all()
        assert {s.indicateur for s in lignes} == set(seuils.INDICATEURS)
        assert all(s.a_valider for s in lignes)

    def test_us316_ca4_sans_grille_les_seuils_de_cout_sont_inactifs(self, db, monkeypatch):
        monkeypatch.setattr(seuils, "couts_disponibles", lambda: False)
        seuils.assurer_seuils_par_defaut(db)
        for s in db.query(SeuilPilotage).all():
            assert s.actif is (not seuils.INDICATEURS[s.indicateur].depend_du_cout), s.indicateur

    def test_us316_ca4_avec_la_grille_les_seuils_de_cout_sont_actifs(self, db):
        seuils.assurer_seuils_par_defaut(db)
        assert seuils.couts_disponibles() is True
        assert all(s.actif for s in db.query(SeuilPilotage).all())

    def test_us316_ca4_idempotent_et_respecte_un_seuil_modifie(self, db):
        seuils.assurer_seuils_par_defaut(db)
        seuil = _seuil(db, "taux_erreur")
        seuils.modifier_seuil(db, seuil.id, valeur=42.0, actif=False)
        assert seuils.assurer_seuils_par_defaut(db) == 0
        db.refresh(seuil)
        assert seuil.valeur == 42.0 and seuil.actif is False and seuil.a_valider is False


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — évaluation périodique, sans modèle, sur usage et fond
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5Evaluation:

    def test_us316_ca5_cadence_par_defaut_quinze_minutes(self):
        assert config.PILOTAGE_EVALUATION_MINUTES == 15

    def test_us316_ca5_la_cadence_se_regle_par_l_environnement(self, monkeypatch):
        monkeypatch.setenv("PILOTAGE_EVALUATION_MINUTES", "5")
        assert config._entier_borne("PILOTAGE_EVALUATION_MINUTES", 15, 1, 1440) == 5
        monkeypatch.setenv("PILOTAGE_EVALUATION_MINUTES", "abc")
        assert config._entier_borne("PILOTAGE_EVALUATION_MINUTES", 15, 1, 1440) == 15

    def test_us316_ca5_l_evaluation_n_ecrit_aucune_ligne_de_consommation(self, db, envois):
        _gherkin(db)
        avant = db.query(ConsoTokens).count()
        seuils.evaluer(db, maintenant=MAINTENANT)
        assert db.query(ConsoTokens).count() == avant

    def test_us316_ca5_le_service_n_appelle_aucun_modele(self):
        for nom in ("seuils", "notifications"):
            source = (ROOT / f"app/services/pilotage/{nom}.py").read_text(encoding="utf-8")
            assert not re.search(r"^\s*(from|import)\s+(llm\.(groq_client|routeur)|groq|mistralai|openai)", source, re.M)
            assert not re.search(r"appeler_chat|appeler_transcription|get_client", source)

    def test_us316_ca5_les_provenances_mesure_et_test_ne_comptent_pas(self, db, envois):
        telegram, _ = envois
        for _ in range(60):
            _ligne(db, J, tokens_in=50_000, provenance="mesure")
            _ligne(db, J, tokens_in=50_000, provenance="test")
        db.commit()
        assert _evenements(seuils.evaluer(db, maintenant=MAINTENANT)) == {}
        telegram.assert_not_called()

    def test_us316_ca5_la_provenance_fond_compte(self, db, envois):
        for _ in range(25):
            _ligne(db, J, provenance="fond", issue="erreur")
        db.commit()
        assert _evenements(seuils.evaluer(db, maintenant=MAINTENANT)).get("taux_erreur") == "ouverte"

    def test_us316_ca5_un_seuil_inactif_n_est_pas_evalue(self, db, envois):
        for _ in range(25):
            _ligne(db, J, issue="erreur")
        db.commit()
        seuils.modifier_seuil(db, _seuil(db, "taux_erreur").id, actif=False)
        assert "taux_erreur" not in _evenements(seuils.evaluer(db, maintenant=MAINTENANT))

    def test_us316_ca5_le_bot_planifie_l_evaluation_et_les_bilans(self):
        source = (ROOT / "app/bot/application.py").read_text(encoding="utf-8")
        assert "job_evaluation_seuils" in source and "PILOTAGE_EVALUATION_MINUTES" in source
        assert "job_bilans_pilotage" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — le message
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6Message:

    def test_us316_ca6_telegram_a_l_administrateur_et_email_a_admin_email(self, db, envois):
        telegram, email = envois
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        assert telegram.call_args.args[0] == 555
        assert email.call_args.args[0] == ADMIN

    def test_us316_ca6_le_message_porte_indicateur_valeur_seuil_fenetre_et_lien(self, db, envois, monkeypatch):
        telegram, email = envois
        monkeypatch.setattr(config, "PILOTAGE_URL", "https://exemple.test/pilotage")
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        texte = telegram.call_args.args[1]
        assert "Jetons d'entrée médians par appel (agent)" in texte           # indicateur
        assert "8 900 jetons" in texte                                        # valeur
        assert "> +20 % par rapport aux 7 jours précédents" in texte          # seuil
        assert "aujourd'hui" in texte and "60 appels" in texte                # fenêtre
        assert "https://exemple.test/pilotage/#/derives" in texte             # lien
        sujet, html = email.call_args.args[1], email.call_args.args[2]
        assert "Seuil franchi" in sujet and '<a href="https://exemple.test/pilotage/#/derives">' in html

    def test_us316_ca6_l_identifiant_telegram_de_repli(self, db, monkeypatch):
        db.query(User).update({"telegram_chat_id": None})
        db.commit()
        monkeypatch.setattr(config, "ADMIN_EMAIL", ADMIN)
        monkeypatch.setattr(config, "ADMIN_TELEGRAM_ID", "")
        assert notifications.identifiant_telegram_admin(db) is None
        monkeypatch.setattr(config, "ADMIN_TELEGRAM_ID", "777")
        assert notifications.identifiant_telegram_admin(db) == 777

    def test_us316_ca6_le_compte_lie_a_admin_email_prime_sur_la_variable(self, db, monkeypatch):
        monkeypatch.setattr(config, "ADMIN_EMAIL", ADMIN)
        monkeypatch.setattr(config, "ADMIN_TELEGRAM_ID", "777")
        assert notifications.identifiant_telegram_admin(db) == 555


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — ouverte, retour à la normale, rappel quotidien
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7CycleDeVie:

    def test_us316_ca7_le_retour_a_la_normale_part_une_seule_fois(self, db, envois):
        telegram, email = envois
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        db.query(ConsoTokens).filter(ConsoTokens.date == J).update({"tokens_in": 6000})
        db.commit()
        evenements = _evenements(seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15)))
        assert evenements == {"jetons_entree_mediane": "resolue"}
        assert telegram.call_count == 2 and "Retour à la normale" in telegram.call_args.args[1]
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=30))
        assert telegram.call_count == 2 and email.call_count == 2
        alerte = db.query(AlertePilotage).one()
        assert alerte.resolue_le is not None and alerte.retour_notifie is True

    def test_us316_ca7_une_nouvelle_alerte_s_ouvre_apres_la_resolution(self, db, envois):
        telegram, _ = envois
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        db.query(ConsoTokens).filter(ConsoTokens.date == J).update({"tokens_in": 6000})
        db.commit()
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        db.query(ConsoTokens).filter(ConsoTokens.date == J).update({"tokens_in": 9000})
        db.commit()
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=30))
        assert db.query(AlertePilotage).count() == 2
        assert telegram.call_count == 3

    def test_us316_ca7_rappel_quotidien_pour_une_gravite_haute(self, db, envois):
        telegram, _ = envois
        for _ in range(25):
            _ligne(db, J, issue="erreur")        # taux d'erreur : gravité haute par défaut
        db.commit()
        seuils.evaluer(db, maintenant=MAINTENANT)
        assert telegram.call_count == 1
        for _ in range(25):                      # le lendemain, la fenêtre « aujourd'hui » a ses propres appels
            _ligne(db, J + timedelta(days=1), issue="erreur")
        db.commit()
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(hours=23))
        assert telegram.call_count == 1
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(hours=25))
        assert telegram.call_count == 2 and "Rappel" in telegram.call_args.args[1]
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(hours=26))
        assert telegram.call_count == 2

    def test_us316_ca7_pas_de_rappel_pour_une_gravite_moyenne(self, db, envois):
        telegram, _ = envois
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(hours=30))
        assert telegram.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — échantillon
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8Echantillon:

    def test_us316_ca8_moins_de_20_appels_ne_declenche_rien(self, db, envois):
        telegram, _ = envois
        for _ in range(19):
            _ligne(db, J, issue="erreur")
        db.commit()
        assert _evenements(seuils.evaluer(db, maintenant=MAINTENANT)) == {}
        telegram.assert_not_called()
        assert db.query(AlertePilotage).count() == 0

    def test_us316_ca8_vingt_appels_suffisent(self, db, envois):
        for _ in range(20):
            _ligne(db, J, issue="erreur")
        db.commit()
        assert _evenements(seuils.evaluer(db, maintenant=MAINTENANT)).get("taux_erreur") == "ouverte"

    def test_us316_ca8_un_echantillon_trop_petit_ne_resout_pas_une_alerte(self, db, envois):
        telegram, _ = envois
        for _ in range(25):
            _ligne(db, J, issue="erreur")
        db.commit()
        seuils.evaluer(db, maintenant=MAINTENANT)
        db.query(ConsoTokens).delete()
        for _ in range(5):
            _ligne(db, J)
        db.commit()
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        assert db.query(AlertePilotage).filter(AlertePilotage.resolue_le.is_(None)).count() == 1
        assert telegram.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — un canal ne retient pas l'autre
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9Canaux:

    def test_us316_ca9_l_echec_de_telegram_n_empeche_pas_l_email(self, db, envois):
        telegram, email = envois
        telegram.return_value = False
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        assert email.call_count == 1
        alerte = db.query(AlertePilotage).one()
        assert alerte.canaux_notifies == "email"

    def test_us316_ca9_une_exception_d_un_canal_est_journalisee_pas_levee(self, db, envois):
        telegram, email = envois
        email.side_effect = RuntimeError("Brevo en panne")
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        assert db.query(AlertePilotage).one().canaux_notifies == "telegram"

    def test_us316_ca9_le_canal_en_echec_est_reessaye_au_passage_suivant(self, db, envois):
        telegram, email = envois
        telegram.return_value = False
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        telegram.return_value = True
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        assert telegram.call_count == 2 and email.call_count == 1       # l'e-mail n'est pas renvoyé
        assert db.query(AlertePilotage).one().canaux_notifies == "email,telegram"

    def test_us316_ca9_l_echec_est_journalise(self, db, envois, caplog):
        telegram, _ = envois
        telegram.return_value = False
        _gherkin(db)
        with caplog.at_level("WARNING", logger="potager"):
            seuils.evaluer(db, maintenant=MAINTENANT)
        assert "non notifié" in caplog.text

    def test_us316_ca9_un_canal_sans_destinataire_n_est_pas_un_echec(self, db, envois, monkeypatch):
        telegram, email = envois
        db.query(User).update({"telegram_chat_id": None})
        db.commit()
        monkeypatch.setattr(config, "ADMIN_TELEGRAM_ID", "")
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        telegram.assert_not_called()
        assert db.query(AlertePilotage).one().canaux_notifies == "email"
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        assert email.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — interrupteur
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11Interrupteur:

    def test_us316_ca11_eteint_par_defaut(self):
        source = (ROOT / "app/config.py").read_text(encoding="utf-8")
        assert re.search(r'PILOTAGE_ALERTES\s*=\s*_booleen_pilotage\("PILOTAGE_ALERTES"\)', source)
        assert re.search(r'os\.environ\.get\(nom, "non"\)', source)

    def test_us316_ca11_eteint_rien_ne_part_mais_l_alerte_est_journalisee(self, db, envois, monkeypatch):
        telegram, email = envois
        monkeypatch.setattr(config, "PILOTAGE_ALERTES", False)
        _gherkin(db)
        assert _evenements(seuils.evaluer(db, maintenant=MAINTENANT)) == {"jetons_entree_mediane": "ouverte"}
        telegram.assert_not_called()
        email.assert_not_called()
        alerte = db.query(AlertePilotage).one()
        assert alerte.canaux_notifies == ""

    def test_us316_ca11_rallume_l_alerte_deja_ouverte_est_notifiee(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_ALERTES", False)
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        monkeypatch.setattr(config, "PILOTAGE_ALERTES", True)
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        assert telegram.call_count == 1

    def test_us316_ca11_pas_de_retour_a_la_normale_sans_alerte_jamais_notifiee(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_ALERTES", False)
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        db.query(ConsoTokens).filter(ConsoTokens.date == J).update({"tokens_in": 6000})
        db.commit()
        monkeypatch.setattr(config, "PILOTAGE_ALERTES", True)
        seuils.evaluer(db, maintenant=MAINTENANT + timedelta(minutes=15))
        telegram.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — aucun contenu de jardinier
# ═════════════════════════════════════════════════════════════════════════════

class TestCA12Confidentialite:

    def test_us316_ca12_aucun_nom_ni_contenu_dans_les_messages(self, db, envois):
        telegram, email = envois
        _gherkin(db)
        seuils.evaluer(db, maintenant=MAINTENANT)
        for texte in (telegram.call_args.args[1], email.call_args.args[1], email.call_args.args[2]):
            assert "Dupont" not in texte and "Alice" not in texte and ADMIN not in texte

    def test_us316_ca12_les_messages_ne_lisent_aucune_table_de_contenu(self):
        source = (ROOT / "app/services/pilotage/seuils.py").read_text(encoding="utf-8")
        assert not re.search(r"Evenement|Observation|EchangeConversation|Conversation|\.nom\b", source)


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — l'API de la vue « Seuils »
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def api(monkeypatch):
    from app.api import main

    moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=moteur)
    Session = sessionmaker(bind=moteur)
    with Session() as s:
        s.add_all([
            User(id=1, email=ADMIN, nom="Admin"), User(id=2, email="jardinier@example.com", nom="Jardinier"),
            Potager(id=1, nom="Potager A", proprietaire_id=1),
        ])
        s.commit()
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN)
    monkeypatch.setattr(config, "ADMIN_EMAIL", ADMIN)
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        client.Session = Session
        yield client
    moteur.dispose()


def _en_tete(user_id: int) -> dict:
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


class TestCA10Api:

    def test_us316_ca10_sans_jeton_401_jardinier_403(self, api):
        assert api.get("/admin/pilotage/seuils").status_code == 401
        assert api.get("/admin/pilotage/seuils", headers=_en_tete(2)).status_code == 403
        assert api.patch("/admin/pilotage/seuils/1", json={"actif": False}).status_code == 401
        assert api.patch("/admin/pilotage/seuils/1", json={"actif": False}, headers=_en_tete(2)).status_code == 403

    def test_us316_ca10_liste_des_seuils_avec_defauts_et_interrupteurs(self, api):
        r = api.get("/admin/pilotage/seuils", headers=_en_tete(1))
        assert r.status_code == 200, r.text
        corps = r.json()
        assert len(corps["seuils"]) == len(seuils.SEUILS_PAR_DEFAUT)
        premier = corps["seuils"][0]
        assert {"id", "libelle", "valeur", "unite", "actif", "a_valider", "gravite", "seuil_texte", "fenetre"} <= set(premier)
        assert all(s["a_valider"] for s in corps["seuils"])
        assert corps["reglages"]["alertes"] is False and corps["reglages"]["evaluation_minutes"] == 15
        assert {"resume_quotidien", "bilan_hebdomadaire"} <= set(corps["reglages"])
        assert corps["alertes"] == []

    def test_us316_ca10_modifier_la_valeur_et_l_activation(self, api):
        seuil = api.get("/admin/pilotage/seuils", headers=_en_tete(1)).json()["seuils"][0]
        r = api.patch(f"/admin/pilotage/seuils/{seuil['id']}", json={"valeur": 12.5, "actif": False}, headers=_en_tete(1))
        assert r.status_code == 200, r.text
        assert r.json()["valeur"] == 12.5 and r.json()["actif"] is False and r.json()["a_valider"] is False
        relu = api.get("/admin/pilotage/seuils", headers=_en_tete(1)).json()["seuils"][0]
        assert relu["valeur"] == 12.5 and relu["actif"] is False

    def test_us316_ca10_activer_seul_ne_valide_pas_la_valeur(self, api):
        seuil = api.get("/admin/pilotage/seuils", headers=_en_tete(1)).json()["seuils"][0]
        r = api.patch(f"/admin/pilotage/seuils/{seuil['id']}", json={"actif": False}, headers=_en_tete(1))
        assert r.json()["a_valider"] is True

    @pytest.mark.parametrize("valeur", [-1, 1e12])
    def test_us316_ca10_valeur_invalide_422(self, api, valeur):
        seuil = api.get("/admin/pilotage/seuils", headers=_en_tete(1)).json()["seuils"][0]
        assert api.patch(f"/admin/pilotage/seuils/{seuil['id']}", json={"valeur": valeur}, headers=_en_tete(1)).status_code == 422
        assert api.patch(f"/admin/pilotage/seuils/{seuil['id']}", json={"valeur": "x"}, headers=_en_tete(1)).status_code == 422

    def test_us316_ca10_seuil_inconnu_404(self, api):
        assert api.patch("/admin/pilotage/seuils/9999", json={"actif": True}, headers=_en_tete(1)).status_code == 404

    def test_us316_ca10_historique_des_50_dernieres_alertes(self, api):
        api.get("/admin/pilotage/seuils", headers=_en_tete(1))
        with api.Session() as s:
            seuil = s.query(SeuilPilotage).first()
            for i in range(60):
                s.add(AlertePilotage(seuil_id=seuil.id, valeur_mesuree=i, declenchee_le=datetime(2026, 11, 1) + timedelta(hours=i),
                                     resolue_le=datetime(2026, 11, 1) + timedelta(hours=i, minutes=5)))
            s.commit()
        alertes = api.get("/admin/pilotage/seuils", headers=_en_tete(1)).json()["alertes"]
        assert len(alertes) == 50
        assert alertes[0]["declenchee_le"] > alertes[-1]["declenchee_le"]
        assert {"libelle", "valeur_texte", "declenchee_le", "resolue_le", "canaux_notifies"} <= set(alertes[0])

    def test_us316_ca10_une_alerte_ouverte_se_voit_sur_son_seuil(self, api):
        api.get("/admin/pilotage/seuils", headers=_en_tete(1))
        with api.Session() as s:
            seuil = s.query(SeuilPilotage).first()
            s.add(AlertePilotage(seuil_id=seuil.id, valeur_mesuree=1, declenchee_le=datetime(2026, 11, 17, 9, 0)))
            s.commit()
        premier = api.get("/admin/pilotage/seuils", headers=_en_tete(1)).json()["seuils"][0]
        assert premier["alerte_ouverte_depuis"] == "2026-11-17T09:00:00"

    def test_us316_ca10_les_autres_routes_pilotage_restent_en_lecture_seule(self, api):
        for methode in (api.post, api.put, api.patch, api.delete):
            assert methode("/admin/pilotage/fiabilite", headers=_en_tete(1)).status_code in (404, 405)
        assert api.post("/admin/pilotage/seuils", json={}, headers=_en_tete(1)).status_code in (404, 405)


# ═════════════════════════════════════════════════════════════════════════════
# Le planificateur
# ═════════════════════════════════════════════════════════════════════════════

class TestPlanificateur:

    def test_us316_la_tache_evalue_sur_sa_propre_session(self, db, envois, monkeypatch):
        from app.bot import pilotage_jobs
        _gherkin(db)
        monkeypatch.setattr(pilotage_jobs, "SessionLocal", lambda: db)
        monkeypatch.setattr(db, "close", lambda: None)
        assert pilotage_jobs.passer_evaluation() >= 1

    def test_us316_les_modules_du_pilotage_sont_dans_le_paquet_du_bot(self):
        import app.bot as bot
        assert hasattr(bot, "job_evaluation_seuils") and hasattr(bot, "job_bilans_pilotage")


# ═════════════════════════════════════════════════════════════════════════════
# Vue « Seuils » : états, règle en clair, alertes ouvertes, édition complète (maquette d'US-318)
# ═════════════════════════════════════════════════════════════════════════════

class TestVueSeuils:

    def test_us316_vue_etat_courant_de_chaque_seuil(self, db, envois):
        _gherkin(db)
        seuils.evaluer(db, maintenant=datetime.now())
        vue = {s["indicateur"]: s for s in seuils.vue_seuils(db)["seuils"]}
        med = vue["jetons_entree_mediane"]
        assert med["etat"] == "franchi" and med["valeur_courante"] == 8900 and med["reference"] == 6000
        assert med["ecart_courant"] == pytest.approx(48.33, abs=0.01)
        assert med["regle"] == "plus de 20 % au-dessus de la moyenne des 7 jours précédents"
        assert vue["taux_erreur"]["etat"] == "norme"          # 60 appels, aucune erreur
        assert vue["appels_par_echange"]["etat"] == "nodata"  # pas d'échange en base

    def test_us316_vue_un_seuil_inactif_est_dit_inactif(self, db):
        seuils.assurer_seuils_par_defaut(db)
        seuils.modifier_seuil(db, _seuil(db, "taux_erreur").id, actif=False)
        vue = {s["indicateur"]: s for s in seuils.vue_seuils(db)["seuils"]}
        assert vue["taux_erreur"]["etat"] == "inactif" and vue["taux_erreur"]["valeur_courante"] is None

    def test_us316_vue_alertes_ouvertes_en_tete(self, db, envois, monkeypatch):
        monkeypatch.setattr(config, "PILOTAGE_URL", "https://exemple.test/pilotage")
        _gherkin(db)
        seuils.evaluer(db, maintenant=datetime.now())
        ouvertes = seuils.vue_seuils(db)["alertes_ouvertes"]
        assert len(ouvertes) == 1
        assert ouvertes[0]["mesure_texte"] == "8 900 jetons (+48 %)" and ouvertes[0]["vue"] == "derives"
        assert ouvertes[0]["reference_texte"] == "6 000 jetons"

    def test_us316_vue_sans_etats_ne_mesure_rien(self, db, envois):
        _gherkin(db)
        seuils.evaluer(db, maintenant=datetime.now())
        legere = seuils.vue_seuils(db, avec_etats=False)
        assert len(legere["alertes_ouvertes"]) == 1
        assert all(s["valeur_courante"] is None for s in legere["seuils"])

    def test_us316_modifier_comparaison_fenetre_gravite(self, db):
        seuil = _seuil(db, "taux_erreur")
        r = seuils.modifier_seuil(db, seuil.id, comparaison="ecart_7j", fenetre_jours=3, gravite="basse", valeur=50)
        assert (r["comparaison"], r["fenetre_jours"], r["gravite"], r["valeur"]) == ("ecart_7j", 3, "basse", 50.0)

    @pytest.mark.parametrize("champ,valeur", [("comparaison", "autre"), ("gravite", "critique"), ("fenetre_jours", 0), ("fenetre_jours", 32)])
    def test_us316_modifier_valeurs_hors_vocabulaire_refusees(self, db, champ, valeur):
        with pytest.raises(seuils.SeuilInvalideError):
            seuils.modifier_seuil(db, _seuil(db, "taux_erreur").id, **{champ: valeur})

    def test_us316_la_projection_de_fin_de_mois_n_a_pas_de_comparaison_relative(self, db):
        with pytest.raises(seuils.SeuilInvalideError):
            seuils.modifier_seuil(db, _seuil(db, "cout_mois_projete").id, comparaison="ecart_7j")

    def test_us316_une_definition_en_double_est_refusee(self, db):
        seuils.assurer_seuils_par_defaut(db)
        db.add(SeuilPilotage(indicateur="taux_erreur", perimetre="tous", fenetre_jours=3, comparaison="fixe", valeur=1, gravite="basse"))
        db.commit()
        origine = db.query(SeuilPilotage).filter_by(indicateur="taux_erreur", fenetre_jours=1).one()
        with pytest.raises(seuils.SeuilInvalideError):
            seuils.modifier_seuil(db, origine.id, fenetre_jours=3)
        assert db.get(SeuilPilotage, origine.id).fenetre_jours == 1

    def test_us316_api_patch_etendu_et_lecture_legere(self, api):
        seuil = api.get("/admin/pilotage/seuils?etats=false", headers=_en_tete(1)).json()["seuils"][0]
        r = api.patch(f"/admin/pilotage/seuils/{seuil['id']}", json={"gravite": "basse", "fenetre_jours": 7}, headers=_en_tete(1))
        assert r.status_code == 200 and r.json()["gravite"] == "basse" and r.json()["fenetre_jours"] == 7
        assert api.patch(f"/admin/pilotage/seuils/{seuil['id']}", json={"gravite": "x"}, headers=_en_tete(1)).status_code == 422
