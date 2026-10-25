"""
tests/test_etat_configuration_demarrage.py — L'état de la configuration au démarrage du bot
===========================================================================================
Le bot affiche, au démarrage, la valeur RETENUE de chaque réglage et d'où elle
vient, pour que l'on contrôle ce que le système retient — sans jamais afficher
un secret.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app import config
from app.bot import application


def _etat() -> str:
    return "\n".join(config.etat_configuration())


def _ligne(nom: str) -> str:
    return next(l for l in config.etat_configuration() if l.strip().startswith(nom))


def test_etat_agent_mode_retenu_et_origine(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "ombre")
    monkeypatch.setenv("AGENT_MODE", "ombre")
    ligne = _ligne("AGENT_MODE")
    assert ": ombre" in ligne and "(défini)" in ligne and "⚠️" not in ligne


def test_etat_agent_mode_absent_est_le_defaut(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "off")
    monkeypatch.delenv("AGENT_MODE", raising=False)
    ligne = _ligne("AGENT_MODE")
    assert ": off" in ligne and "(défaut)" in ligne and "⚠️" not in ligne


def test_etat_agent_mode_invalide_est_signale(monkeypatch):
    """Une faute de frappe retombe sur `off` : l'état le dit au lieu de le taire."""
    monkeypatch.setattr(config, "AGENT_MODE", "off")
    monkeypatch.setenv("AGENT_MODE", "Actfi")
    ligne = _ligne("AGENT_MODE")
    assert ": off" in ligne and "⚠️ « Actfi » non retenu" in ligne


def test_etat_agent_mode_ecrit_en_majuscules_n_est_pas_une_alerte(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")
    monkeypatch.setenv("AGENT_MODE", " ACTIF ")
    assert "⚠️" not in _ligne("AGENT_MODE")


def test_etat_agent_max_tours_invalide_est_signale(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MAX_TOURS", 3)
    monkeypatch.setenv("AGENT_MAX_TOURS", "zéro")
    assert "⚠️ « zéro » non retenu" in _ligne("AGENT_MAX_TOURS")
    monkeypatch.setenv("AGENT_MAX_TOURS", "3")
    assert "⚠️" not in _ligne("AGENT_MAX_TOURS")


def test_etat_les_modeles_par_type_d_appel_sont_listes():
    for type_appel, modele in config.GROQ_MODELE_PAR_TYPE.items():
        assert f"GROQ_MODEL_{type_appel.upper()}" in _etat() and modele in _etat()


def test_etat_les_reglages_numeriques_et_booleens():
    etat = _etat()
    for nom in ("RAG_ACTIF", "RAG_SEUIL_CONFIANCE", "RAG_MAX_PASSAGES", "PREDIAGNOSTIC_SEUIL_SYMPTOME",
                "PREDIAGNOSTIC_MAX_PISTES", "CALENDRIER_ZONE_DEFAUT", "GROQ_TIMEOUT_S"):
        assert nom in etat
    assert "RAG_ACTIF" in etat and ("oui" in _ligne("RAG_ACTIF") or "non" in _ligne("RAG_ACTIF"))


def test_etat_le_fichier_d_environnement_est_nomme_sans_son_contenu():
    assert f".env.{config.APP_ENV}" in _ligne("Fichier d'environnement")


@pytest.mark.parametrize("nom,sentinelle", [
    ("GROQ_API_KEY", "gsk_SENTINELLE_GROQ"),
    ("TELEGRAM_BOT_TOKEN", "1234:SENTINELLE_TELEGRAM"),
    ("DATABASE_URL", "postgresql://u:SENTINELLE_MDP@h/db"),
    ("JWT_SECRET", "SENTINELLE_JWT"),
    ("BREVO_API_KEY", "xkeysib-SENTINELLE_BREVO"),
    ("GOOGLE_CLIENT_ID", "SENTINELLE_GOOGLE_ID"),
    ("GOOGLE_CLIENT_SECRET", "GOCSPX-SENTINELLE"),
    ("ADMIN_EMAIL", "sentinelle@exemple.fr"),
])
def test_etat_aucun_secret_n_est_affiche(monkeypatch, nom, sentinelle):
    monkeypatch.setattr(config, nom, sentinelle)
    etat = _etat()
    assert sentinelle not in etat
    assert "SENTINELLE" not in etat and "gsk_" not in etat
    assert f"{nom:<30}: défini" in etat


def test_etat_un_secret_vide_est_absent(monkeypatch):
    monkeypatch.setattr(config, "BREVO_API_KEY", "")
    monkeypatch.setattr(config, "ADMIN_EMAIL", "")
    assert _ligne("BREVO_API_KEY").endswith(": absent")
    assert _ligne("ADMIN_EMAIL").endswith(": absent")


def test_etat_une_ligne_par_reglage_sans_retour_a_la_ligne_parasite():
    lignes = config.etat_configuration()
    assert all("\n" not in l for l in lignes) and len(lignes) == len(set(lignes))


def test_demarrage_affiche_l_etat_apres_la_meteo_et_avant_pret(capsys):
    application_construite = MagicMock()
    with patch.object(application, "_construire_application", return_value=application_construite):
        application.main()
    sortie = capsys.readouterr().out
    assert "Configuration retenue :" in sortie and "AGENT_MODE" in sortie
    assert sortie.index("Météo") < sortie.index("Configuration retenue") < sortie.index("Bot prêt")
    assert config.TELEGRAM_BOT_TOKEN not in sortie.replace(config.TELEGRAM_BOT_TOKEN[:10], "")
    application_construite.run_polling.assert_called_once()
