"""
tests/test_us315_derive_entre_versions.py — [US-315] Repérer une dérive de consommation d'une version
à l'autre.

Service `app/services/pilotage/derives.py` + route `GET /admin/pilotage/derives`.
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
from app.services.pilotage import agregats, derives
from database.db import Base
from database.models import ConsoTokens, Potager, User

ROOT = Path(__file__).resolve().parent.parent
J = date(2026, 11, 10)
ADMIN = "admin@example.com"


def _ligne(db, jour: date = J, *, version: str | None = "3.128.0", appel_type: str = "agent",
           entree: int = 1000, sortie: int = 100, cache: int = 0, issue: str = "ok",
           provenance: str = "usage", canal: str = "pwa", unite: str = "jeton",
           echange_ref: str | None = None, cout: int | None = None) -> ConsoTokens:
    ligne = ConsoTokens(
        potager_id=1, user_id=1, date=jour, appel_type=appel_type, modele="mistral/small",
        tokens_in=entree, tokens_out=sortie, tokens_cache=cache, latence_ms=200, issue=issue,
        provenance=provenance, canal=canal, unite=unite, version_app=version, echange_ref=echange_ref,
        cout_micro_eur=cout, cree_le=datetime(jour.year, jour.month, jour.day, 10, 0),
    )
    db.add(ligne)
    return ligne


def _filtres(depuis: date = J - timedelta(days=29), jusqu_a: date = J, **kw) -> agregats.Filtres:
    return agregats.construire_filtres(depuis=depuis, jusqu_a=jusqu_a, **kw)


def _rangee(db, n: int, **kw):
    for _ in range(n):
        _ligne(db, **kw)


@pytest.fixture
def db(test_db):
    test_db.add_all([Potager(id=1, nom="Potager A", proprietaire_id=1), User(id=1, nom="Alice", email="a@example.com")])
    test_db.commit()
    return test_db


def _ligne_de(corps: dict, version, appel_type: str) -> dict:
    return next(l for l in corps["par_version_et_type"] if l["version"] == version and l["appel_type"] == appel_type)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — tableau par version et par type
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Tableau:

    def test_us315_ca1_appels_mediane_p95_entree_mediane_sortie_taux_de_cache(self, db):
        for entree, sortie, cache in ((1000, 100, 500), (2000, 200, 1000), (3000, 300, 1500)):
            _ligne(db, entree=entree, sortie=sortie, cache=cache)
        db.commit()
        l = _ligne_de(derives.derives(db, _filtres()), "3.128.0", "agent")
        assert l["appels"] == 3
        assert l["entree_mediane"] == 2000.0 and l["entree_p95"] == 3000.0
        assert l["sortie_mediane"] == 200.0
        assert l["taux_cache"] == pytest.approx(3000 / 6000)

    def test_us315_ca1_un_tableau_par_type_d_appel(self, db):
        _ligne(db, appel_type="agent", entree=8000)
        _ligne(db, appel_type="question", entree=400)
        db.commit()
        corps = derives.derives(db, _filtres())
        assert _ligne_de(corps, "3.128.0", "agent")["entree_mediane"] == 8000.0
        assert _ligne_de(corps, "3.128.0", "question")["entree_mediane"] == 400.0

    def test_us315_ca1_les_dix_dernieres_versions_dans_l_ordre_des_numeros(self, db):
        # 12 versions ; « 3.1000.0 » > « 3.999.0 » (ordre numérique, pas alphabétique)
        versions = [f"3.{n}.0" for n in (100, 99, 98, 97, 96, 95, 94, 93, 92, 91, 90, 1000)]
        for v in versions:
            _ligne(db, version=v)
        db.commit()
        corps = derives.derives(db, _filtres())
        assert corps["versions"][0] == "3.1000.0" and corps["versions"][1] == "3.100.0"
        assert len(corps["versions"]) == 10
        assert "3.90.0" not in corps["versions"] and "3.91.0" not in corps["versions"]
        assert {l["version"] for l in corps["par_version_et_type"]} == set(corps["versions"])

    def test_us315_ca1_seuls_les_appels_reussis_d_unite_jeton_sont_mesures(self, db):
        _ligne(db, entree=5000)
        _ligne(db, entree=0, issue="erreur")                    # un échec n'a pas de jetons
        _ligne(db, appel_type="dictee", entree=30, unite="seconde")
        _ligne(db, appel_type="voix", entree=900, unite="caractere")
        db.commit()
        corps = derives.derives(db, _filtres())
        agent = _ligne_de(corps, "3.128.0", "agent")
        assert agent["appels"] == 1 and agent["entree_mediane"] == 5000.0
        assert {l["appel_type"] for l in corps["par_version_et_type"]} == {"agent"}

    def test_us315_ca1_periode_sans_appel(self, db):
        corps = derives.derives(db, _filtres())
        assert corps["versions"] == [] and corps["par_version_et_type"] == []
        assert corps["par_version_et_canal"] == []
        assert corps["courbe"]["valeurs"] == [None] * 30


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — courbe par jour avec repères
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2Courbe:

    def test_us315_ca2_la_mediane_par_jour_du_type_choisi(self, db):
        _ligne(db, J - timedelta(days=2), entree=1000)
        _ligne(db, J - timedelta(days=2), entree=3000)
        _ligne(db, J - timedelta(days=2), entree=9000)
        _ligne(db, J, entree=8000)
        _ligne(db, J, appel_type="question", entree=50)
        db.commit()
        c = derives.derives(db, _filtres(depuis=J - timedelta(days=4)))["courbe"]
        assert c["appel_type"] == "agent"
        assert c["points"][0] == "2026-11-06" and c["points"][-1] == "2026-11-10"
        assert c["valeurs"] == [None, None, 3000.0, None, 8000.0]
        assert c["appels"] == [0, 0, 3, 0, 1]

    def test_us315_ca2_un_autre_type_au_choix(self, db):
        _ligne(db, appel_type="question", entree=400)
        db.commit()
        c = derives.derives(db, _filtres(depuis=J), appel_type="question")["courbe"]
        assert c["appel_type"] == "question" and c["valeurs"] == [400.0]

    def test_us315_ca2_un_repere_a_la_premiere_apparition_de_chaque_version(self, db):
        _ligne(db, J - timedelta(days=5), version="3.127.0")
        _ligne(db, J - timedelta(days=3), version="3.127.0")
        _ligne(db, J - timedelta(days=3), version="3.128.0")
        _ligne(db, J - timedelta(days=1), version="3.128.0")
        db.commit()
        c = derives.derives(db, _filtres(depuis=J - timedelta(days=4)))["courbe"]
        # 3.127.0 est apparue avant la période (le 5 : hors fenêtre) : pas de repère dans la fenêtre
        assert c["reperes"] == [{"version": "3.128.0", "date": "2026-11-07"}]

    def test_us315_ca2_une_version_apparue_dans_la_fenetre_a_son_repere(self, db):
        _ligne(db, J - timedelta(days=3), version="3.127.0")
        _ligne(db, J - timedelta(days=1), version="3.128.0")
        db.commit()
        c = derives.derives(db, _filtres(depuis=J - timedelta(days=4)))["courbe"]
        assert [r["version"] for r in c["reperes"]] == ["3.127.0", "3.128.0"]
        assert [r["date"] for r in c["reperes"]] == ["2026-11-07", "2026-11-09"]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — par version et par canal, par échange
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3Echanges:

    def test_us315_ca3_appels_par_echange_entree_mediane_cout_median(self, db):
        # pwa, 3.128.0 : trois échanges de 1, 2 et 4 appels ; chaque appel : 1000 jetons, 100 µ€
        for ref, n in (("a", 1), ("b", 2), ("c", 4)):
            _rangee(db, n, echange_ref=ref, cout=100)
        db.commit()
        l = derives.derives(db, _filtres())["par_version_et_canal"][0]
        assert (l["version"], l["canal"], l["echanges"]) == ("3.128.0", "pwa", 3)
        assert l["appels_par_echange_mediane"] == 2.0 and l["appels_par_echange_p95"] == 4.0
        assert l["entree_par_echange_mediane"] == 2000.0
        assert l["cout_par_echange_mediane_micro_eur"] == 200.0

    def test_us315_ca3_le_cout_est_absent_quand_il_n_est_pas_chiffre(self, db):
        _ligne(db, echange_ref="a", cout=None)
        db.commit()
        assert derives.derives(db, _filtres())["par_version_et_canal"][0]["cout_par_echange_mediane_micro_eur"] is None

    def test_us315_ca3_les_echecs_comptent_dans_la_boucle_de_l_agent(self, db):
        _ligne(db, echange_ref="a")
        _ligne(db, echange_ref="a", issue="erreur", entree=0)
        db.commit()
        assert derives.derives(db, _filtres())["par_version_et_canal"][0]["appels_par_echange_mediane"] == 2.0

    def test_us315_ca3_les_lignes_sans_echange_ne_sont_pas_un_echange(self, db):
        _ligne(db, echange_ref=None)
        db.commit()
        assert derives.derives(db, _filtres())["par_version_et_canal"] == []

    def test_us315_ca3_une_ligne_par_version_et_par_canal(self, db):
        _ligne(db, version="3.127.0", canal="pwa", echange_ref="a")
        _ligne(db, version="3.128.0", canal="pwa", echange_ref="b")
        _ligne(db, version="3.128.0", canal="telegram", echange_ref="c")
        db.commit()
        lignes = derives.derives(db, _filtres())["par_version_et_canal"]
        assert [(l["version"], l["canal"]) for l in lignes] == [
            ("3.128.0", "pwa"), ("3.128.0", "telegram"), ("3.127.0", "pwa"),
        ]


# ═════════════════════════════════════════════════════════════════════════════
# CA4, CA5 — comparaison, échantillon faible
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4CA5:

    def test_us315_gherkin_les_deux_versions_se_comparent(self, db):
        _rangee(db, 200, version="3.127.0", entree=6000)
        _rangee(db, 150, version="3.128.0", entree=8900)
        db.commit()
        corps = derives.derives(db, _filtres())
        ancienne, nouvelle = _ligne_de(corps, "3.127.0", "agent"), _ligne_de(corps, "3.128.0", "agent")
        assert (ancienne["appels"], ancienne["entree_mediane"]) == (200, 6000.0)
        assert (nouvelle["appels"], nouvelle["entree_mediane"]) == (150, 8900.0)
        assert round((nouvelle["entree_mediane"] / ancienne["entree_mediane"] - 1) * 100) == 48
        assert not ancienne["echantillon_faible"] and not nouvelle["echantillon_faible"]

    def test_us315_ca4_le_seuil_de_mise_en_evidence_est_dans_la_reponse(self, db):
        corps = derives.derives(db, _filtres())
        assert corps["seuil_ecart"] == 0.20 and corps["seuil_echantillon"] == 20

    def test_us315_ca5_moins_de_vingt_appels_est_un_echantillon_faible(self, db):
        _rangee(db, 19, version="3.127.0")
        _rangee(db, 20, version="3.128.0")
        db.commit()
        corps = derives.derives(db, _filtres())
        assert _ligne_de(corps, "3.127.0", "agent")["echantillon_faible"] is True
        assert _ligne_de(corps, "3.128.0", "agent")["echantillon_faible"] is False

    def test_us315_ca5_l_echantillon_se_juge_par_type(self, db):
        _rangee(db, 30, appel_type="agent")
        _rangee(db, 3, appel_type="question")
        db.commit()
        corps = derives.derives(db, _filtres())
        assert _ligne_de(corps, "3.128.0", "agent")["echantillon_faible"] is False
        assert _ligne_de(corps, "3.128.0", "question")["echantillon_faible"] is True

    def test_us315_ca5_un_echantillon_d_echanges_faible_aussi(self, db):
        for i in range(3):
            _ligne(db, echange_ref=f"e{i}")
        db.commit()
        assert derives.derives(db, _filtres())["par_version_et_canal"][0]["echantillon_faible"] is True


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — provenance mesure
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6Provenance:

    def test_us315_ca6_la_comparaison_peut_porter_sur_les_seules_mesures(self, db):
        _ligne(db, provenance="usage", entree=1000)
        _ligne(db, provenance="mesure", entree=5000)
        db.commit()
        assert _ligne_de(derives.derives(db, _filtres()), "3.128.0", "agent")["entree_mediane"] == 1000.0
        mesure = derives.derives(db, _filtres(provenance="mesure"))
        assert _ligne_de(mesure, "3.128.0", "agent")["entree_mediane"] == 5000.0
        assert mesure["periode"]["provenances"] == ["mesure"]


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — avant suivi des versions
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7SansVersion:

    def test_us315_ca7_les_lignes_sans_version_sont_regroupees_a_part_en_dernier(self, db):
        _ligne(db, version=None, entree=700, echange_ref="h1")
        _ligne(db, version=None, entree=900, echange_ref="h2")
        _ligne(db, version="3.128.0", entree=5000, echange_ref="v1")
        db.commit()
        corps = derives.derives(db, _filtres())
        assert corps["versions"] == ["3.128.0", None]
        assert _ligne_de(corps, None, "agent")["appels"] == 2
        assert [l["version"] for l in corps["par_version_et_type"]] == ["3.128.0", None]
        assert [l["version"] for l in corps["par_version_et_canal"]] == ["3.128.0", None]

    def test_us315_ca7_une_version_vide_est_aussi_avant_le_suivi(self, db):
        _ligne(db, version="", entree=700)
        db.commit()
        assert derives.derives(db, _filtres())["versions"] == [None]

    def test_us315_ca7_une_version_sans_numero_se_range_avant_les_numeros(self):
        assert derives.cle_de_version("dev") < derives.cle_de_version("3.0.0")
        assert derives.cle_de_version("3.9.0") < derives.cle_de_version("3.10.0")


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
        _ligne(s, date.today(), entree=1234, appel_type="question")
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

    def test_us315_sans_jeton_401_jardinier_403(self, api):
        assert api.get("/admin/pilotage/derives").status_code == 401
        assert api.get("/admin/pilotage/derives", headers=_en_tete(2)).status_code == 403

    def test_us315_l_administrateur_lit_les_derives_et_choisit_le_type_de_la_courbe(self, api):
        r = api.get("/admin/pilotage/derives?type_courbe=question", headers=_en_tete(1))
        assert r.status_code == 200, r.text
        assert r.json()["courbe"]["appel_type"] == "question" and r.json()["courbe"]["valeurs"][-1] == 1234.0
        assert api.get("/admin/pilotage/derives", headers=_en_tete(1)).json()["courbe"]["appel_type"] == "agent"

    def test_us315_un_filtre_hors_vocabulaire_422(self, api):
        assert api.get("/admin/pilotage/derives?canal=zzz", headers=_en_tete(1)).status_code == 422

    def test_us315_aucune_ecriture(self, api):
        for methode in (api.post, api.put, api.patch, api.delete):
            assert methode("/admin/pilotage/derives", headers=_en_tete(1)).status_code in (404, 405)

    def test_us315_le_service_n_appelle_aucun_modele(self):
        source = (ROOT / "app/services/pilotage/derives.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(llm\.(groq_client|routeur)|groq|mistralai|openai)", source, re.M)
        assert not re.search(r"appeler_chat|appeler_transcription|get_client", source)
