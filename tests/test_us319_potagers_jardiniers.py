"""
tests/test_us319_potagers_jardiniers.py — [US-319] Suivre la consommation par potager et par jardinier.

Service `app/services/pilotage/acteurs.py` et routes `/admin/pilotage/{potagers,utilisateurs}[/{id}]`.
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

from app import config
from app.services import auth as svc_auth
from app.services.pilotage import acteurs, agregats
from database.db import Base
from database.models import ConsoTokens, Potager, PotagerMembre, User

ROOT = Path(__file__).resolve().parent.parent
J = date(2026, 11, 17)
ADMIN = "admin@example.com"


def _filtres(**kw) -> agregats.Filtres:
    return agregats.Filtres(depuis=kw.pop("depuis", J - timedelta(days=29)), jusqu_a=kw.pop("jusqu_a", J), **kw)


def _ligne(db, potager_id, user_id, *, cout=1000, jour=J, issue="ok", appel_type="agent", canal="pwa",
           provenance="usage", echange_ref=None, tokens_in=100) -> None:
    db.add(ConsoTokens(
        potager_id=potager_id, user_id=user_id, date=jour, appel_type=appel_type, modele="mistral/small",
        tokens_in=tokens_in, tokens_out=10, tokens_cache=0, latence_ms=200, issue=issue, provenance=provenance,
        canal=canal, unite="jeton", echange_ref=echange_ref, cout_micro_eur=cout, version_app="3.133.0",
        cree_le=datetime(jour.year, jour.month, jour.day, 10, 0),
    ))


def _peupler(db) -> None:
    """5 potagers, 3 actifs : « Jardin de la Garenne » a coûté 0,90 € quand la médiane est de 0,20 €."""
    db.add_all([
        User(id=1, email=ADMIN, nom="Alice Secrète", cree_le=datetime(2026, 1, 5)),
        User(id=2, email="bob@example.com", nom="Bob Secret", cree_le=datetime(2026, 2, 6)),
        User(id=3, email="cleo@example.com", nom="Cléo Secrète", cree_le=datetime(2026, 3, 7)),
        User(id=4, email="dormeur@example.com", nom="Dormeur", cree_le=datetime(2026, 4, 8)),
    ])
    db.add_all([
        Potager(id=1, nom="Jardin de la Garenne", proprietaire_id=1), Potager(id=2, nom="Potager du Moulin", proprietaire_id=2),
        Potager(id=3, nom="Les Terrasses", proprietaire_id=3), Potager(id=4, nom="Potager vide", proprietaire_id=4),
        Potager(id=5, nom="Potager endormi", proprietaire_id=4),
    ])
    db.add_all([
        PotagerMembre(user_id=1, potager_id=1, role="owner"), PotagerMembre(user_id=2, potager_id=1, role="editor"),
        PotagerMembre(user_id=2, potager_id=2, role="owner"), PotagerMembre(user_id=3, potager_id=3, role="owner"),
        PotagerMembre(user_id=4, potager_id=4, role="owner"), PotagerMembre(user_id=4, potager_id=5, role="owner"),
    ])
    db.commit()
    # Garenne : 0,90 € (Alice 0,60, Bob 0,20, fond 0,10) ; Moulin : 0,20 € ; Terrasses : 0,10 €.
    for k in range(6):
        _ligne(db, 1, 1, cout=100_000, echange_ref=f"a{k}", canal="pwa" if k % 2 else "telegram")
    for k in range(2):
        _ligne(db, 1, 2, cout=100_000, echange_ref=f"b{k}")
    _ligne(db, 1, None, cout=100_000, provenance="fond", appel_type="compagnon_signal", canal="fond")
    for k in range(2):
        _ligne(db, 2, 2, cout=100_000, echange_ref=f"c{k}")
    _ligne(db, 2, 2, cout=0, issue="erreur", echange_ref="c9")
    _ligne(db, 3, 3, cout=100_000, echange_ref="d0", jour=J - timedelta(days=3))
    # Une mesure et un test ne comptent pas par défaut.
    _ligne(db, 4, 4, cout=5_000_000, provenance="mesure")
    _ligne(db, 4, 4, cout=5_000_000, provenance="test")
    db.commit()


@pytest.fixture
def db(test_db):
    _peupler(test_db)
    return test_db


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin, CA1, CA3, CA7
# ═════════════════════════════════════════════════════════════════════════════

class TestPotagers:

    def test_us319_gherkin_garenne_en_tete_usage_eleve_et_potagers_sans_appel(self, db):
        r = acteurs.potagers(db, _filtres())
        assert r["bandeau"]["potagers_existants"] == 5 and r["bandeau"]["potagers_actifs"] == 3
        premiere = r["lignes"][0]
        assert premiere["libelle"] == "Jardin de la Garenne" and premiere["cout_micro_eur"] == 900_000
        assert premiere["usage_eleve"] is True
        assert r["mediane_cout_micro_eur"] == 200_000
        sans_appel = [l for l in r["lignes"] if not l["actif"]]
        assert {l["libelle"] for l in sans_appel} == {"Potager vide", "Potager endormi"}
        assert all(l["appels"] == 0 and l["cout_micro_eur"] is None for l in sans_appel)

    def test_us319_ca1_mesures_par_potager(self, db):
        garenne = acteurs.potagers(db, _filtres())["lignes"][0]
        assert garenne["membres"] == 2 and garenne["appels"] == 9 and garenne["echanges"] == 8
        assert garenne["jetons_entree"] == 900 and garenne["jetons_sortie"] == 90  # le fond y entre aussi
        assert garenne["part_cout"] == pytest.approx(900_000 / 1_200_000)
        assert garenne["canaux"] == ["fond", "pwa", "telegram"]
        assert garenne["taux_echec"] == 0 and garenne["dernier_appel"] == J.isoformat()

    def test_us319_ca1_taux_d_echec_et_dernier_appel(self, db):
        moulin = next(l for l in acteurs.potagers(db, _filtres())["lignes"] if l["id"] == 2)
        assert moulin["taux_echec"] == pytest.approx(1 / 3)
        terrasses = next(l for l in acteurs.potagers(db, _filtres())["lignes"] if l["id"] == 3)
        assert terrasses["dernier_appel"] == (J - timedelta(days=3)).isoformat()

    def test_us319_ca3_bandeau(self, db):
        b = acteurs.potagers(db, _filtres())["bandeau"]
        assert b["jardiniers_inscrits"] == 4 and b["jardiniers_actifs"] == 3
        assert b["cout_median_par_jardinier_micro_eur"] == 400_000        # Alice 0,60 / Bob 0,40 / Cléo 0,10
        assert b["cout_p95_par_jardinier_micro_eur"] == 600_000
        assert b["part_cout_premier_decile"] == pytest.approx(600_000 / 1_100_000)  # le premier décile = 1 jardinier
        assert b["facteur_usage_eleve"] == 3 and "3 fois la médiane" in b["regle_usage_eleve"]

    def test_us319_ca7_la_regle_est_rendue_et_seuls_les_actifs_la_fixent(self, db):
        r = acteurs.potagers(db, _filtres())
        assert [l["libelle"] for l in r["lignes"] if l["usage_eleve"]] == ["Jardin de la Garenne"]

    def test_us319_ca7_pas_d_usage_eleve_sans_chiffre(self, test_db):
        test_db.add_all([User(id=1, email=ADMIN), Potager(id=1, nom="A", proprietaire_id=1)])
        test_db.commit()
        _ligne(test_db, 1, 1, cout=None)
        test_db.commit()
        r = acteurs.potagers(test_db, _filtres())
        assert r["mediane_cout_micro_eur"] is None and not any(l["usage_eleve"] for l in r["lignes"])

    def test_us319_ca9_provenances_par_defaut_et_filtres(self, db):
        assert next(l for l in acteurs.potagers(db, _filtres())["lignes"] if l["id"] == 4)["appels"] == 0
        mesure = acteurs.potagers(db, _filtres(provenances=("mesure",)))
        assert next(l for l in mesure["lignes"] if l["id"] == 4)["cout_micro_eur"] == 5_000_000
        # Le filtre de canal de la coquille s'applique.
        telegram = acteurs.potagers(db, _filtres(canal="telegram"))
        assert next(l for l in telegram["lignes"] if l["id"] == 1)["appels"] == 3

    def test_us319_ca9_potager_supprime_absent(self, db):
        db.get(Potager, 5).etat = "supprime"
        db.commit()
        assert acteurs.potagers(db, _filtres())["bandeau"]["potagers_existants"] == 4


# ═════════════════════════════════════════════════════════════════════════════
# CA2, CA8
# ═════════════════════════════════════════════════════════════════════════════

class TestUtilisateurs:

    def test_us319_ca2_mesures_par_jardinier(self, db):
        lignes = {l["libelle"]: l for l in acteurs.utilisateurs(db, _filtres())["lignes"]}
        alice = lignes[ADMIN]
        assert alice["appels"] == 6 and alice["cout_micro_eur"] == 600_000 and alice["potagers"] == 1
        assert alice["inscrit_le"] == "2026-01-05" and alice["usage_eleve"] is False  # 0,60 < 3 × 0,40 (médiane des jardiniers actifs)
        assert lignes["bob@example.com"]["potagers"] == 2
        dormeur = lignes["dormeur@example.com"]
        assert dormeur["appels"] == 0 and dormeur["actif"] is False and dormeur["potagers"] == 2

    def test_us319_ca8_taches_automatiques_a_part(self, db):
        r = acteurs.utilisateurs(db, _filtres())
        auto = [l for l in r["lignes"] if l["automatique"]]
        assert len(auto) == 1 and auto[0]["libelle"] == "Tâches automatiques" and auto[0]["cout_micro_eur"] == 100_000
        assert auto[0]["usage_eleve"] is False and auto[0]["id"] is None
        assert r["bandeau"]["jardiniers_inscrits"] == 4  # un compte, pas une ligne de plus
        # ... et rattachées à leur potager.
        assert next(l for l in acteurs.potagers(db, _filtres())["lignes"] if l["id"] == 1)["appels"] == 9

    def test_us319_un_compte_sans_email_n_expose_pas_son_nom(self, db):
        db.add(User(id=9, email=None, nom="Nom Privé"))
        db.commit()
        lignes = acteurs.utilisateurs(db, _filtres())["lignes"]
        assert "Compte sans e-mail (n° 9)" in {l["libelle"] for l in lignes}
        assert "Nom Privé" not in str(lignes)


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6 — fiches
# ═════════════════════════════════════════════════════════════════════════════

class TestFiches:

    def test_us319_ca5_fiche_potager(self, db):
        f = acteurs.fiche_potager(db, _filtres(), 1)
        assert f["potager"]["libelle"] == "Jardin de la Garenne"
        g = f["graphique"]
        assert len(g["points"]) == 30 and g["appels"][-1] == 9 and g["cout_micro_eur"][-1] == 900_000
        assert {t["cle"] for t in f["par_type"]} == {"agent", "compagnon_signal"}
        assert {c["cle"] for c in f["par_canal"]} == {"fond", "pwa", "telegram"}
        assert f["echange"]["nb"] == 8 and f["echange"]["cout_micro_eur"]["mediane"] == 100_000
        assert f["issues"] == {"ok": 9}

    def test_us319_gherkin_part_de_chaque_membre(self, db):
        membres = {m["libelle"]: m for m in acteurs.fiche_potager(db, _filtres(), 1)["membres"]}
        assert membres[ADMIN]["part"] == pytest.approx(600_000 / 900_000) and membres[ADMIN]["role"] == "owner"
        assert membres["bob@example.com"]["part"] == pytest.approx(200_000 / 900_000)
        assert membres["Tâches automatiques"]["automatique"] is True and membres["Tâches automatiques"]["part"] == pytest.approx(1 / 9)
        assert sum(m["part"] for m in membres.values()) == pytest.approx(1)

    def test_us319_ca5_membre_sans_appel_figure_a_zero(self, db):
        db.add(PotagerMembre(user_id=3, potager_id=1, role="lecteur"))
        db.commit()
        membres = {m["libelle"]: m for m in acteurs.fiche_potager(db, _filtres(), 1)["membres"]}
        assert membres["cleo@example.com"]["appels"] == 0 and membres["cleo@example.com"]["part"] == 0

    def test_us319_ca6_fiche_jardinier_repartie_entre_ses_potagers(self, db):
        _ligne(db, 2, 1, cout=300_000, echange_ref="x1")
        db.commit()
        f = acteurs.fiche_utilisateur(db, _filtres(), 1)
        assert f["utilisateur"]["libelle"] == ADMIN
        par_potager = {p["libelle"]: p for p in f["potagers"]}
        assert par_potager["Jardin de la Garenne"]["part"] == pytest.approx(600_000 / 900_000)
        assert par_potager["Potager du Moulin"]["part"] == pytest.approx(300_000 / 900_000)
        assert f["graphique"]["appels"][-1] == 7 and f["issues"] == {"ok": 7}
        assert f["echange"]["nb"] == 7  # les appels de fond (sans utilisateur) n'y sont pas

    def test_us319_fiche_inconnue(self, db):
        assert acteurs.fiche_potager(db, _filtres(), 99) is None
        assert acteurs.fiche_utilisateur(db, _filtres(), 99) is None

    def test_us319_la_fiche_d_un_potager_ne_contient_aucune_donnee_personnelle_autre_que_l_email(self, db):
        texte = str(acteurs.fiche_potager(db, _filtres(), 1)) + str(acteurs.utilisateurs(db, _filtres()))
        for secret in ("Alice Secrète", "Bob Secret", "Cléo Secrète"):
            assert secret not in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — API
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def api(monkeypatch):
    from app.api import main

    moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=moteur)
    Session = sessionmaker(bind=moteur)
    with Session() as s:
        _peupler(s)
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN)
    monkeypatch.setattr(config, "ADMIN_EMAIL", ADMIN)
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client
    moteur.dispose()


def _en_tete(user_id: int) -> dict:
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


ROUTES = ["/admin/pilotage/potagers", "/admin/pilotage/utilisateurs", "/admin/pilotage/potagers/1", "/admin/pilotage/utilisateurs/1"]
PERIODE = {"depuis": "2026-10-19", "jusqu_a": "2026-11-17"}


class TestApi:

    @pytest.mark.parametrize("route", ROUTES)
    def test_us319_ca11_sans_jeton_401_jardinier_403(self, api, route):
        assert api.get(route).status_code == 401
        assert api.get(route, headers=_en_tete(2)).status_code == 403

    @pytest.mark.parametrize("route", ROUTES)
    def test_us319_ca11_lecture_seule(self, api, route):
        for verbe in (api.post, api.put, api.patch, api.delete):
            assert verbe(route, headers=_en_tete(1)).status_code == 405

    def test_us319_ca1_ca2_routes_de_liste(self, api):
        p = api.get("/admin/pilotage/potagers", params=PERIODE, headers=_en_tete(1))
        assert p.status_code == 200, p.text
        assert p.json()["lignes"][0]["libelle"] == "Jardin de la Garenne" and p.json()["bandeau"]["potagers_actifs"] == 3
        u = api.get("/admin/pilotage/utilisateurs", params=PERIODE, headers=_en_tete(1)).json()
        assert any(l["automatique"] for l in u["lignes"])

    def test_us319_ca5_fiche_et_404(self, api):
        f = api.get("/admin/pilotage/potagers/1", params=PERIODE, headers=_en_tete(1))
        assert f.status_code == 200 and f.json()["potager"]["id"] == 1
        assert api.get("/admin/pilotage/potagers/999", params=PERIODE, headers=_en_tete(1)).status_code == 404
        assert api.get("/admin/pilotage/utilisateurs/999", params=PERIODE, headers=_en_tete(1)).status_code == 404

    def test_us319_ca9_filtre_invalide_422(self, api):
        assert api.get("/admin/pilotage/potagers", params={"canal": "x"}, headers=_en_tete(1)).status_code == 422


# ═════════════════════════════════════════════════════════════════════════════
# CA11, CA12 — garde et registre
# ═════════════════════════════════════════════════════════════════════════════

class TestGardes:

    def test_us319_aucun_appel_a_un_modele_ni_ecriture(self):
        source = (ROOT / "app/services/pilotage/acteurs.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+.*(passerelle|groq_client|routeur)", source, re.M)
        assert not re.search(r"\.(add|delete|commit|merge)\(", source)

    def test_us319_ca11_la_lecture_passe_par_le_chemin_hors_perimetre(self, db, monkeypatch):
        appels = []
        monkeypatch.setattr(agregats, "table_sous_rls", lambda _db: appels.append(1) or False)
        acteurs.potagers(db, _filtres())
        assert appels  # `lecture_toute_la_plateforme` a été traversé
        monkeypatch.setattr(agregats, "table_sous_rls", lambda _db: True)
        with pytest.raises(agregats.LectureHorsPerimetreError):
            acteurs.potagers(db, _filtres())

    def test_us319_ca12_registre_rgpd(self):
        fiche = (ROOT / "docs/RGPD/RGPD_PILOTAGE_LLM.md").read_text(encoding="utf-8")
        for attendu in ("conso_tokens", "finalité", "administrateur", "conservation", "adresse e-mail", "contenu de message"):
            assert attendu in fiche, attendu

    def test_us319_ca10_la_vue_n_a_aucune_route_de_contenu(self):
        source = (ROOT / "admin/src/views/Potagers.jsx").read_text(encoding="utf-8")
        assert "/messages" not in source and "/carnet" not in source
