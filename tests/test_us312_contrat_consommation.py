"""
tests/test_us312_contrat_consommation.py — [US-312 / CA10] Les chiffres de la vue Consommation sont
ceux de `GET /admin/pilotage/synthese`, à l'unité près.

Le contrat tient en un fichier : `admin/src/lib/fixtures/consommation_fixe.json`, la réponse des cinq
routes que lit la vue sur un jeu de données FIXE.
  - ici (Python) : l'API réelle, sur ce jeu, rend EXACTEMENT ce fichier ;
  - côté vue (`admin/src/lib/consommation.test.js`) : ce que l'écran affiche est tiré de ce fichier.
Si l'API change de forme ou de valeur, ce test échoue avant que l'écran ne mente.

Régénérer après un changement voulu de l'API : `REGENERER_FIXTURE_US312=1 pytest tests/test_us312_...`.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from database.db import Base
from database.models import ConsoTokens, Potager, User

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "admin" / "src" / "lib" / "fixtures" / "consommation_fixe.json"
ADMIN = "admin@example.com"
J = date(2026, 11, 10)

# (jour, type, modèle, canal, provenance, unité, entrée, sortie, cache, latence, issue, échange, coût µ€)
_PERIODE = [
    (date(2026, 11, 4), "agent", "mistral/small", "pwa", "usage", "jeton", 8000, 100, 5000, 900, "ok", "a1", 4000),
    (date(2026, 11, 4), "agent", "mistral/small", "pwa", "usage", "jeton", 9000, 150, 5000, 1100, "ok", "a2", 4500),
    (date(2026, 11, 4), "question", "mistral/ministral", "telegram", "usage", "jeton", 500, 50, 0, 300, "ok", "a3", 100),
    # 5 novembre : aucun appel — le jour doit apparaître à zéro
    (date(2026, 11, 6), "agent", "mistral/small", "pwa", "usage", "jeton", 7000, 120, 4000, 1000, "ok", "a4", 3500),
    (date(2026, 11, 6), "classification", "mistral/ministral", "telegram", "usage", "jeton", 450, 20, 0, 200, "ok", "a5", 60),
    (date(2026, 11, 7), "agent", "mistral/small", "mcp", "usage", "jeton", 10000, 200, 6000, 1300, "erreur", "a6", 5000),
    (date(2026, 11, 8), "dictee", "voxtral", "pwa", "usage", "seconde", 20, 0, 0, 800, "ok", "a7", 30),
    (date(2026, 11, 8), "dictee", "voxtral", "pwa", "usage", "seconde", 30, 0, 0, 900, "ok", "a7", 45),
    (date(2026, 11, 8), "voix", "voxtral", "pwa", "usage", "caractere", 1200, 0, 0, 700, "ok", "a7", 20),
    (date(2026, 11, 9), "agent", "mistral/small", "pwa", "fond", "jeton", 6000, 90, 3000, 950, "ok", "a8", 3000),
    (date(2026, 11, 10), "agent", "mistral/small", "telegram", "usage", "jeton", 8500, 110, 5500, 1050, "ok", "a9", 4200),
    # provenances masquées par défaut
    (date(2026, 11, 7), "agent", "mistral/small", "outil", "mesure", "jeton", 99999, 999, 0, 5000, "ok", "m1", 9000),
    (date(2026, 11, 8), "agent", "mistral/small", "outil", "test", "jeton", 88888, 888, 0, 4000, "ok", "t1", 8000),
]
_PRECEDENTE = [
    (date(2026, 10, 29), "agent", "mistral/small", "pwa", "usage", "jeton", 7000, 100, 3000, 900, "ok", "p1", 3500),
    (date(2026, 10, 30), "agent", "mistral/small", "pwa", "usage", "jeton", 6500, 90, 3500, 950, "ok", "p2", 3300),
    (date(2026, 11, 2), "question", "mistral/ministral", "telegram", "usage", "jeton", 400, 40, 0, 250, "ok", "p3", 80),
]

_COLONNES = ("date", "appel_type", "modele", "canal", "provenance", "unite", "tokens_in", "tokens_out",
             "tokens_cache", "latence_ms", "issue", "echange_ref", "cout_micro_eur")

# Les cinq lectures de la vue, dans l'ordre où elle les fait.
_APPELS = {
    "synthese": "/admin/pilotage/synthese",
    "serie_entree": "/admin/pilotage/series?mesure=jetons_entree",
    "serie_cache": "/admin/pilotage/series?mesure=jetons_cache",
    "serie_entree_par_modele": "/admin/pilotage/series?mesure=jetons_entree&dimension=modele",
    "par_type": "/admin/pilotage/ventilation?dimension=appel_type&mesure=jetons_entree&limite=20",
    "par_modele": "/admin/pilotage/ventilation?dimension=modele&mesure=jetons_entree&limite=20",
    "synthese_avec_mesures": "/admin/pilotage/synthese?provenance=usage,fond,mesure,test",
}
_PERIODE_PARAMS = f"depuis={J - timedelta(days=6)}&jusqu_a={J}"


@pytest.fixture
def api(monkeypatch):
    from app.api import main

    moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=moteur)
    Session = sessionmaker(bind=moteur)
    with Session() as s:
        s.add_all([User(id=1, email=ADMIN, nom="Admin"), Potager(id=1, nom="Potager A", proprietaire_id=1)])
        for ligne in _PERIODE + _PRECEDENTE:
            valeurs = dict(zip(_COLONNES, ligne))
            jour = valeurs["date"]
            s.add(ConsoTokens(
                potager_id=1, user_id=1, version_app="3.130.0", fournisseur="mistral",
                cree_le=datetime(jour.year, jour.month, jour.day, 10, 30), **valeurs,
            ))
        s.commit()
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN)
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client
    moteur.dispose()


def _lire(api) -> dict:
    entetes = {"Authorization": f"Bearer {svc_auth.creer_access_token(1)}"}
    sortie = {}
    for nom, chemin in _APPELS.items():
        reponse = api.get(f"{chemin}{'&' if '?' in chemin else '?'}{_PERIODE_PARAMS}", headers=entetes)
        assert reponse.status_code == 200, (nom, reponse.text)
        sortie[nom] = reponse.json()
    return sortie


def test_us312_ca10_l_api_rend_exactement_le_contrat_de_la_vue(api):
    lu = _lire(api)
    if os.environ.get("REGENERER_FIXTURE_US312"):
        FIXTURE.parent.mkdir(parents=True, exist_ok=True)
        FIXTURE.write_text(json.dumps(lu, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    attendu = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert lu == attendu


def test_us312_ca10_le_jeu_fixe_dit_ce_que_la_vue_affiche(api):
    """Contrôles croisés sur le jeu fixe : ce sont les valeurs que le test JS relit à l'écran."""
    lu = _lire(api)
    m = lu["synthese"]["mesures"]
    assert m["appels"] == 11                       # 13 lignes − mesure − test
    assert m["jetons_entree"] == 8000 + 9000 + 500 + 7000 + 450 + 10000 + 6000 + 8500
    assert (m["secondes_audio"], m["caracteres"]) == (50, 1200)
    assert lu["synthese"]["mesures_precedentes"]["appels"] == 3
    # le jour sans appel est présent, à zéro
    serie = lu["serie_entree"]
    assert "2026-11-05" in serie["points"] and serie["total"][serie["points"].index("2026-11-05")] == 0
    # les mesures et les tests n'entrent dans aucun des chiffres par défaut
    assert lu["synthese_avec_mesures"]["mesures"]["appels"] == 13
    assert sum(serie["total"]) == m["jetons_entree"]
