"""
tests/test_us313_315_contrat_vues.py — [US-313, US-314, US-315] Les chiffres des vues Coût, Fiabilité et
Dérives sont ceux des routes `/admin/pilotage/{cout,fiabilite,derives}`, à l'unité près.

Même principe que `test_us312_contrat_consommation.py` : un fichier par vue dans
`admin/src/lib/fixtures/` est la réponse réelle des routes sur un jeu de données FIXE.
  - ici (Python) : l'API réelle, sur ce jeu, rend EXACTEMENT ces fichiers ;
  - côté vue (`admin/src/lib/{cout,fiabilite,derives}.test.js`) : ce que l'écran affiche en est tiré.

Régénérer après un changement voulu de l'API :
    REGENERER_FIXTURE_US313_315=1 pytest tests/test_us313_315_contrat_vues.py
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
from app.services.pilotage import cout as svc_cout
from database.db import Base
from database.models import ConsoTokens, Potager, User

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "admin" / "src" / "lib" / "fixtures"
ADMIN = "admin@example.com"
J = date(2026, 11, 10)
PERIODE = f"depuis={J - timedelta(days=6)}&jusqu_a={J}"

# (jour, utilisateur, potager, type, modèle, canal, version, issue, échange, entrée, sortie, cache, latence, coût µ€, heure)
_AGENT_V127 = [  # 3.127.0 : 25 appels d'agent à 6 000 jetons (échantillon suffisant)
    (J - timedelta(days=5 - i % 3), 1 + i % 3, 1 + i % 2, "agent", "mistral/small", "pwa", "3.127.0", "ok", f"x{i}", 6000, 100, 3000, 900, 3000, 9)
    for i in range(25)
]
_AGENT_V128 = [  # 3.128.0 : 22 appels d'agent à 8 900 jetons, deux appels par échange
    (J - timedelta(days=2 - i % 3), 1 + i % 3, 1 + i % 2, "agent", "mistral/small", "pwa", "3.128.0", "ok", f"y{i // 2}", 8900, 120, 4000, 1100, 4500, 14)
    for i in range(22)
]
_LIGNES = _AGENT_V127 + _AGENT_V128 + [
    # des questions (peu d'appels : échantillon faible), un modèle absent de la grille, des échecs
    (J, 1, 1, "question", "mistral/ministral", "telegram", "3.128.0", "ok", "q1", 500, 50, 0, 300, 100, 8),
    (J, 2, 2, "question", "inconnu/modele", "telegram", "3.128.0", "ok", "q2", 400, 40, 0, 250, None, 8),
    (J, 2, 2, "agent", "mistral/small", "pwa", "3.128.0", "quota", "q3", 0, 0, 0, 2000, 0, 14),
    (J - timedelta(days=1), 3, 2, "agent", "mistral/small", "mcp", "3.128.0", "quota", "q4", 0, 0, 0, 2100, 0, 14),
    (J, 4, 2, "voix", "voxtral", "pwa", "3.128.0", "voix_inconnue", "q5", 0, 0, 0, 50, 0, 20),
    (J - timedelta(days=3), 4, 2, "agent", "mistral/small", "telegram", None, "erreur", "q6", 0, 0, 0, 4000, 0, 7),
    (J - timedelta(days=3), 4, 2, "agent", "mistral/small", "telegram", None, "ok", "q7", 1500, 80, 0, 600, 700, 7),
    # masquées par défaut
    (J, 1, 1, "agent", "mistral/small", "outil", "3.128.0", "ok", "m1", 12000, 100, 0, 800, 9000, 11),
]
_PRECEDENTE = [  # semaine précédente, pour l'écart du bandeau
    (J - timedelta(days=8), 1, 1, "agent", "mistral/small", "pwa", "3.126.0", "ok", f"p{i}", 5000, 90, 2000, 800, 2500, 10)
    for i in range(6)
]

_COLONNES = ("date", "user_id", "potager_id", "appel_type", "modele", "canal", "version_app", "issue", "echange_ref",
             "tokens_in", "tokens_out", "tokens_cache", "latence_ms", "cout_micro_eur", "_heure")

_APPELS = {
    "cout": {
        "cout": f"/admin/pilotage/cout?{PERIODE}",
        "serie_par_modele": f"/admin/pilotage/series?mesure=cout_micro_eur&dimension=modele&{PERIODE}",
        "serie_par_canal": f"/admin/pilotage/series?mesure=cout_micro_eur&dimension=canal&{PERIODE}",
        "potagers": f"/admin/pilotage/ventilation?dimension=potager&mesure=cout_micro_eur&limite=10&{PERIODE}",
    },
    "fiabilite": {
        "fiabilite": f"/admin/pilotage/fiabilite?{PERIODE}",
        "serie_issues": f"/admin/pilotage/series?mesure=appels&dimension=issue&{PERIODE}",
    },
    "derives": {
        "derives": f"/admin/pilotage/derives?{PERIODE}",
        "derives_question": f"/admin/pilotage/derives?type_courbe=question&{PERIODE}",
    },
}


@pytest.fixture
def api(monkeypatch):
    from app.api import main

    moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=moteur)
    Session = sessionmaker(bind=moteur)
    with Session() as s:
        s.add_all([
            User(id=1, email=ADMIN, nom="Admin"), User(id=2, email="b@example.com", nom="Bob"),
            User(id=3, email="c@example.com", nom="Chloé"), User(id=4, email="d@example.com", nom="Denis"),
            Potager(id=1, nom="Potager A", proprietaire_id=1), Potager(id=2, nom="Potager B", proprietaire_id=2),
        ])
        for ligne in _LIGNES + _PRECEDENTE:
            v = dict(zip(_COLONNES, ligne))
            heure = v.pop("_heure")
            jour = v["date"]
            fournisseur = v["modele"].split("/")[0] if "/" in v["modele"] else v["modele"]
            s.add(ConsoTokens(
                provenance="mesure" if str(v["echange_ref"]).startswith("m") else "usage",
                unite="jeton", fournisseur=fournisseur,
                tarif_version=None if v["cout_micro_eur"] is None else "2026-11-12",
                cree_le=datetime(jour.year, jour.month, jour.day, heure, 30), **v,
            ))
        s.commit()
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN)
    monkeypatch.setattr(svc_cout, "_aujourd_hui", lambda: J)      # le mois et la projection ne dépendent pas de l'horloge
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client
    moteur.dispose()


def _lire(api, vue: str) -> dict:
    entetes = {"Authorization": f"Bearer {svc_auth.creer_access_token(1)}"}
    sortie = {}
    for nom, chemin in _APPELS[vue].items():
        reponse = api.get(chemin, headers=entetes)
        assert reponse.status_code == 200, (nom, reponse.text)
        sortie[nom] = reponse.json()
    return sortie


@pytest.mark.parametrize("vue", sorted(_APPELS))
def test_us313_315_l_api_rend_exactement_le_contrat_de_la_vue(api, vue):
    lu = _lire(api, vue)
    fichier = FIXTURES / f"{vue}_fixe.json"
    if os.environ.get("REGENERER_FIXTURE_US313_315"):
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(json.dumps(lu, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    assert lu == json.loads(fichier.read_text(encoding="utf-8"))


def test_us313_le_jeu_fixe_dit_ce_que_la_vue_cout_affiche(api):
    c = _lire(api, "cout")["cout"]
    assert c["jardiniers_actifs"] == 4 and c["appels"] == 54
    assert c["lignes_non_chiffrees"] == 1 and c["modeles_non_chiffres"] == [{"modele": "inconnu/modele", "appels": 1}]
    assert c["tarif_version"] == "2026-11-12"
    assert c["mois"]["projection_fin_de_mois_micro_eur"] is not None
    assert c["cout_micro_eur"] == 25 * 3000 + 22 * 4500 + 100 + 700


def test_us314_le_jeu_fixe_dit_ce_que_la_vue_fiabilite_affiche(api):
    f = _lire(api, "fiabilite")["fiabilite"]
    m = f["mesures"]
    assert (m["appels"], m["succes"], m["quota"], m["erreur"]) == (54, 50, 2, 1)
    assert m["autres"] == {"voix_inconnue": 1}
    assert [e["issue"] for e in f["derniers_echecs"]] == ["voix_inconnue", "quota", "quota", "erreur"]


def test_us315_le_jeu_fixe_dit_ce_que_la_vue_derives_affiche(api):
    d = _lire(api, "derives")["derives"]
    assert d["versions"] == ["3.128.0", "3.127.0", None]
    l127 = next(l for l in d["par_version_et_type"] if l["version"] == "3.127.0" and l["appel_type"] == "agent")
    l128 = next(l for l in d["par_version_et_type"] if l["version"] == "3.128.0" and l["appel_type"] == "agent")
    assert (l127["appels"], l127["entree_mediane"]) == (25, 6000.0)
    assert (l128["appels"], l128["entree_mediane"]) == (22, 8900.0)
    assert [r["version"] for r in d["courbe"]["reperes"]] == ["3.127.0", "3.128.0"]
