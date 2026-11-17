"""
tests/test_us314_qualite_de_service.py — [US-314] Suivre la qualité de service des appels au modèle.

Service `app/services/pilotage/fiabilite.py` + route `GET /admin/pilotage/fiabilite` ; le graphique par
jour des issues est la route `series` (dimension `issue`).
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services.pilotage import agregats, fiabilite
from database.db import Base
from database.models import ConsoTokens, Potager, User

ROOT = Path(__file__).resolve().parent.parent
J = date(2026, 11, 10)
ADMIN = "admin@example.com"


def _ligne(db, jour: date = J, *, appel_type: str = "agent", modele: str = "mistral/small",
           issue: str = "ok", latence_ms: int = 200, provenance: str = "usage", canal: str = "pwa",
           heure: int = 10, minute: int = 30) -> ConsoTokens:
    ligne = ConsoTokens(
        potager_id=1, user_id=1, date=jour, appel_type=appel_type, modele=modele, tokens_in=100,
        tokens_out=10, tokens_cache=0, latence_ms=latence_ms, issue=issue, provenance=provenance,
        canal=canal, unite="jeton",
        cree_le=datetime(jour.year, jour.month, jour.day, heure, minute),
    )
    db.add(ligne)
    return ligne


def _filtres(depuis: date = J, jusqu_a: date = J, **kw) -> agregats.Filtres:
    return agregats.construire_filtres(depuis=depuis, jusqu_a=jusqu_a, **kw)


@pytest.fixture
def db(test_db):
    test_db.add_all([Potager(id=1, nom="Potager A", proprietaire_id=1), User(id=1, nom="Alice", email="a@example.com")])
    test_db.commit()
    return test_db


def _journee_gherkin(db):
    """Aujourd'hui 43 appels dont 30 ok, 5 erreur et 8 voix_inconnue."""
    for i in range(30):
        _ligne(db, latence_ms=100 + i)
    for _ in range(5):
        _ligne(db, issue="erreur", latence_ms=4000)
    for _ in range(8):
        _ligne(db, issue="voix_inconnue", appel_type="voix", modele="voxtral", latence_ms=50)
    db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — bandeau
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Bandeau:

    def test_us314_gherkin_taux_de_succes_et_issues(self, db):
        _journee_gherkin(db)
        f = fiabilite.fiabilite(db, _filtres())
        m = f["mesures"]
        assert m["appels"] == 43 and m["succes"] == 30 and m["erreur"] == 5
        assert round(m["taux_succes"] * 100, 1) == 69.8
        assert m["autres"] == {"voix_inconnue": 8}
        # le graphique du jour montre trois issues dont voix_inconnue
        s = agregats.serie(db, _filtres(), "appels", "issue")
        assert {x["cle"] for x in s["series"]} == {"ok", "erreur", "voix_inconnue"}
        # la liste des derniers échecs nomme le type « voix » et le modèle concerné
        echecs = f["derniers_echecs"]
        assert any(e["appel_type"] == "voix" and e["modele"] == "voxtral" and e["issue"] == "voix_inconnue" for e in echecs)

    def test_us314_ca1_taux_de_quota_et_d_erreur(self, db):
        for issue in ["ok"] * 6 + ["quota"] * 3 + ["erreur"]:
            _ligne(db, issue=issue)
        db.commit()
        m = fiabilite.fiabilite(db, _filtres())["mesures"]
        assert (m["taux_succes"], m["taux_quota"], m["taux_erreur"]) == (0.6, 0.3, 0.1)

    def test_us314_ca1_l_ecart_a_la_periode_precedente(self, db):
        _ligne(db, J, issue="ok")
        _ligne(db, J, issue="quota")
        _ligne(db, J - timedelta(days=1), issue="ok")
        db.commit()
        f = fiabilite.fiabilite(db, _filtres())
        assert f["mesures"]["taux_succes"] == 0.5 and f["mesures_precedentes"]["taux_succes"] == 1.0
        assert f["periode_precedente"]["depuis"] == "2026-11-09"

    def test_us314_ca1_periode_sans_appel_pas_de_division_par_zero(self, db):
        m = fiabilite.fiabilite(db, _filtres())["mesures"]
        assert m["appels"] == 0 and m["taux_succes"] is None and m["latence_p95_ms"] is None
        assert m["issues"] == {}


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — toute issue présente en base
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2IssueInconnue:

    def test_us314_ca2_une_issue_inconnue_de_l_ecran_est_rendue(self, db):
        _ligne(db, issue="ok")
        _ligne(db, issue="une_issue_de_demain")
        db.commit()
        f = fiabilite.fiabilite(db, _filtres())
        assert f["mesures"]["autres"] == {"une_issue_de_demain": 1}
        assert f["mesures"]["issues"] == {"ok": 1, "une_issue_de_demain": 1}
        s = agregats.serie(db, _filtres(), "appels", "issue")
        assert {x["cle"] for x in s["series"]} == {"ok", "une_issue_de_demain"}
        assert f["derniers_echecs"][0]["issue"] == "une_issue_de_demain"


# ═════════════════════════════════════════════════════════════════════════════
# CA3, CA4 — par modèle et par type
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3CA4Tableaux:

    def test_us314_ca3_ca4_memes_colonnes_par_modele_et_par_type(self, db):
        _ligne(db, modele="m1", appel_type="agent", latence_ms=100)
        _ligne(db, modele="m1", appel_type="agent", latence_ms=300)
        _ligne(db, modele="m1", appel_type="question", issue="quota", latence_ms=2000)
        _ligne(db, modele="m2", appel_type="agent", issue="delai", latence_ms=9000)
        _ligne(db, modele="m2", appel_type="agent", issue="erreur", latence_ms=1)
        db.commit()

        f = fiabilite.fiabilite(db, _filtres())

        modeles = {l["cle"]: l for l in f["par_modele"]}
        assert (modeles["m1"]["appels"], modeles["m1"]["succes"], modeles["m1"]["quota"]) == (3, 2, 1)
        assert (modeles["m2"]["appels"], modeles["m2"]["erreur"], modeles["m2"]["delai"]) == (2, 1, 1)
        assert modeles["m1"]["latence_p50_ms"] == 100.0 and modeles["m1"]["latence_p95_ms"] == 300.0
        types = {l["cle"]: l for l in f["par_type"]}
        assert types["agent"]["appels"] == 4 and types["question"]["quota"] == 1
        colonnes = {"appels", "succes", "quota", "erreur", "delai", "latence_p50_ms", "latence_p95_ms"}
        assert colonnes <= set(f["par_modele"][0]) and colonnes <= set(f["par_type"][0])

    def test_us314_ca3_les_tableaux_sont_coherents_avec_le_bandeau(self, db):
        _journee_gherkin(db)
        f = fiabilite.fiabilite(db, _filtres())
        assert sum(l["appels"] for l in f["par_modele"]) == f["mesures"]["appels"]
        assert sum(l["appels"] for l in f["par_type"]) == f["mesures"]["appels"]

    def test_us314_ca3_les_plus_sollicites_d_abord(self, db):
        _ligne(db, modele="petit")
        for _ in range(3):
            _ligne(db, modele="grand")
        db.commit()
        assert [l["cle"] for l in fiabilite.fiabilite(db, _filtres())["par_modele"]] == ["grand", "petit"]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — grille heure × jour
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5Grille:

    def test_us314_ca5_les_quotas_par_modele_heure_et_jour(self, db):
        _ligne(db, J, issue="quota", modele="m1", heure=14)
        _ligne(db, J, issue="quota", modele="m1", heure=14, minute=50)
        _ligne(db, J - timedelta(days=2), issue="quota", modele="m1", heure=3)
        _ligne(db, J, issue="quota", modele="m2", heure=23)
        _ligne(db, J, issue="ok", modele="m1", heure=14)                      # pas un quota
        _ligne(db, J - timedelta(days=7), issue="quota", modele="m1", heure=5)   # hors des 7 jours
        db.commit()

        g = fiabilite.fiabilite(db, _filtres(depuis=J - timedelta(days=29)))["grille_quota"]

        assert g["jours"][0] == "2026-11-04" and g["jours"][-1] == "2026-11-10" and len(g["jours"]) == 7
        modeles = {m["modele"]: m for m in g["modeles"]}
        assert modeles["m1"]["total"] == 3 and modeles["m1"]["maximum"] == 2
        assert modeles["m1"]["cellules"][6][14] == 2           # aujourd'hui, 14 h
        assert modeles["m1"]["cellules"][4][3] == 1            # il y a deux jours, 3 h
        assert modeles["m2"]["cellules"][6][23] == 1
        assert len(modeles["m1"]["cellules"]) == 7 and len(modeles["m1"]["cellules"][0]) == 24
        assert [m["modele"] for m in g["modeles"]] == ["m1", "m2"]

    def test_us314_ca5_sans_quota_la_grille_est_vide(self, db):
        _ligne(db)
        db.commit()
        assert fiabilite.fiabilite(db, _filtres())["grille_quota"]["modeles"] == []

    def test_us314_ca5_les_filtres_s_appliquent_a_la_grille(self, db):
        _ligne(db, issue="quota", canal="pwa")
        _ligne(db, issue="quota", canal="telegram")
        db.commit()
        g = fiabilite.fiabilite(db, _filtres(canal="telegram"))["grille_quota"]
        assert g["modeles"][0]["total"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — derniers échecs
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6DerniersEchecs:

    def test_us314_ca6_les_vingt_derniers_echecs_du_plus_recent_au_plus_ancien(self, db):
        for i in range(25):
            _ligne(db, issue="erreur", heure=i % 24, minute=i)
        _ligne(db, issue="ok")
        db.commit()
        echecs = fiabilite.fiabilite(db, _filtres())["derniers_echecs"]
        assert len(echecs) == 20
        horodatages = [e["cree_le"] for e in echecs]
        assert horodatages == sorted(horodatages, reverse=True)
        assert all(e["issue"] != "ok" for e in echecs)

    def test_us314_ca6_heure_type_modele_issue_canal_latence_et_rien_d_autre(self, db):
        _ligne(db, issue="quota", appel_type="agent", modele="m1", canal="telegram", latence_ms=2000)
        db.commit()
        echec = fiabilite.fiabilite(db, _filtres())["derniers_echecs"][0]
        assert set(echec) == {"cree_le", "date", "appel_type", "modele", "issue", "canal", "latence_ms"}
        assert (echec["appel_type"], echec["modele"], echec["issue"], echec["canal"], echec["latence_ms"]) == \
               ("agent", "m1", "quota", "telegram", 2000)
        assert echec["cree_le"].startswith("2026-11-10T10:30")

    def test_us314_ca6_aucun_contenu_de_message_dans_la_reponse(self, db):
        _ligne(db, issue="erreur")
        db.commit()
        corps = str(fiabilite.fiabilite(db, _filtres()))
        assert not re.search(r"message|contenu|prompt|texte", corps, re.I)


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — latence des seuls appels réussis
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7Latence:

    def test_us314_ca7_la_latence_ne_compte_que_les_appels_reussis(self, db):
        for ms in (100, 200, 300):
            _ligne(db, latence_ms=ms)
        for ms in (2000, 6000):
            _ligne(db, issue="quota", latence_ms=ms)
        db.commit()
        m = fiabilite.fiabilite(db, _filtres())["mesures"]
        assert m["latence_p50_ms"] == 200.0 and m["latence_p95_ms"] == 300.0
        assert m["latence_echecs_p50_ms"] == 2000.0 and m["latence_echecs_p95_ms"] == 6000.0

    def test_us314_ca7_sans_succes_pas_de_latence_inventee(self, db):
        _ligne(db, issue="erreur", latence_ms=700)
        db.commit()
        m = fiabilite.fiabilite(db, _filtres())["mesures"]
        assert m["latence_p50_ms"] is None and m["latence_echecs_p50_ms"] == 700.0


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — filtres de la coquille
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8Filtres:

    def test_us314_ca8_provenance_canal_modele_s_appliquent(self, db):
        _ligne(db, provenance="usage", canal="pwa", modele="m1", issue="ok")
        _ligne(db, provenance="mesure", canal="pwa", modele="m1", issue="quota")
        _ligne(db, provenance="usage", canal="telegram", modele="m2", issue="erreur")
        db.commit()
        assert fiabilite.fiabilite(db, _filtres())["mesures"]["appels"] == 2             # mesure masquée
        assert fiabilite.fiabilite(db, _filtres(provenance="mesure"))["mesures"]["quota"] == 1
        assert fiabilite.fiabilite(db, _filtres(canal="telegram"))["mesures"]["erreur"] == 1
        assert fiabilite.fiabilite(db, _filtres(modele="m1"))["mesures"]["appels"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# Route
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
        _ligne(s, date.today(), issue="quota")
        s.commit()
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN)
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client
    moteur.dispose()


def _en_tete(user_id: int) -> dict:
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


class TestRoute:

    def test_us314_sans_jeton_401_jardinier_403(self, api):
        assert api.get("/admin/pilotage/fiabilite").status_code == 401
        assert api.get("/admin/pilotage/fiabilite", headers=_en_tete(2)).status_code == 403

    def test_us314_l_administrateur_lit_la_fiabilite(self, api):
        r = api.get("/admin/pilotage/fiabilite", headers=_en_tete(1))
        assert r.status_code == 200, r.text
        assert r.json()["mesures"]["quota"] == 1
        assert r.json()["derniers_echecs"][0]["issue"] == "quota"

    def test_us314_un_filtre_hors_vocabulaire_422(self, api):
        assert api.get("/admin/pilotage/fiabilite?provenance=zzz", headers=_en_tete(1)).status_code == 422

    def test_us314_aucune_ecriture(self, api):
        for methode in (api.post, api.put, api.patch, api.delete):
            assert methode("/admin/pilotage/fiabilite", headers=_en_tete(1)).status_code in (404, 405)

    def test_us314_le_service_n_appelle_aucun_modele(self):
        source = (ROOT / "app/services/pilotage/fiabilite.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(llm\.(groq_client|routeur)|groq|mistralai|openai)", source, re.M)
        assert not re.search(r"appeler_chat|appeler_transcription|get_client", source)
