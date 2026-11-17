"""
tests/test_us313_cout_rentabilite.py — [US-313] Suivre le coût et la rentabilité.

Service `app/services/pilotage/cout.py` + route `GET /admin/pilotage/cout`. Les lignes de
`conso_tokens` sont écrites à la main : ce qu'on vérifie, ce sont les chiffres rendus.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services.pilotage import agregats, cout
from database.db import Base
from database.models import ConsoTokens, Potager, User

ROOT = Path(__file__).resolve().parent.parent
J = date(2026, 11, 10)          # « aujourd'hui » des jeux de données (mardi)
ADMIN = "admin@example.com"
EUR = 1_000_000


def _ligne(db, jour: date = J, *, potager_id: int = 1, user_id: int | None = 1,
           appel_type: str = "agent", modele: str = "mistral/small", tokens_in: int = 100,
           issue: str = "ok", provenance: str = "usage", canal: str = "pwa",
           echange_ref: str | None = None, cout_micro: int | None = 1000,
           tarif_version: str | None = "2026-11-12") -> ConsoTokens:
    ligne = ConsoTokens(
        potager_id=potager_id, user_id=user_id, date=jour, appel_type=appel_type, modele=modele,
        tokens_in=tokens_in, tokens_out=10, tokens_cache=0, latence_ms=200, issue=issue,
        provenance=provenance, canal=canal, unite="jeton", echange_ref=echange_ref,
        cout_micro_eur=cout_micro, tarif_version=tarif_version,
        cree_le=datetime(jour.year, jour.month, jour.day, 10, 30),
    )
    db.add(ligne)
    return ligne


def _filtres(depuis: date = J - timedelta(days=29), jusqu_a: date = J, **kw) -> agregats.Filtres:
    return agregats.construire_filtres(depuis=depuis, jusqu_a=jusqu_a, **kw)


@pytest.fixture
def db(test_db):
    test_db.add_all([
        Potager(id=1, nom="Potager A", proprietaire_id=1),
        Potager(id=2, nom="Potager B", proprietaire_id=2),
        User(id=1, nom="Alice", email="alice@example.com"),
        User(id=2, nom="Bob", email="bob@example.com"),
        User(id=3, nom="Chloé", email="chloe@example.com"),
        User(id=4, nom="Denis", email="denis@example.com"),
    ])
    test_db.commit()
    return test_db


def _quatre_jardiniers(db):
    """Scénario Gherkin : sur 30 jours, 4 jardiniers actifs ont coûté 1,20 € au total."""
    for user_id, micro in ((1, 600_000), (2, 300_000), (3, 200_000), (4, 100_000)):
        _ligne(db, J - timedelta(days=user_id), user_id=user_id, potager_id=1 + user_id % 2, cout_micro=micro)
    db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — bandeau, jardinier actif
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Bandeau:

    def test_us313_gherkin_le_cout_par_jardinier_actif(self, db):
        _quatre_jardiniers(db)
        c = cout.cout(db, _filtres(), aujourd_hui=J)
        assert c["cout_micro_eur"] == 1_200_000
        assert c["jardiniers_actifs"] == 4
        assert c["cout_par_jardinier_actif_micro_eur"] == 300_000        # 0,30 €

    def test_us313_ca1_cout_du_mois_et_projection_de_fin_de_mois(self, db):
        # Mois de novembre (30 jours), aujourd'hui le 10. Sept derniers jours : 4 → 10 nov.
        _ligne(db, date(2026, 11, 1), cout_micro=3000)            # dans le mois, hors des 7 jours
        for jour in range(4, 11):                                  # 7 jours à 1 000
            _ligne(db, date(2026, 11, jour), cout_micro=1000)
        _ligne(db, date(2026, 10, 31), cout_micro=50_000)          # mois précédent : exclu du mois
        db.commit()

        c = cout.cout(db, _filtres(), aujourd_hui=J)

        assert c["mois"]["cout_micro_eur"] == 10_000               # 3 000 + 7 × 1 000
        assert c["mois"]["cout_7_jours_micro_eur"] == 7000
        # reste 20 jours à 1 000 par jour (7 000 / 7)
        assert c["mois"]["projection_fin_de_mois_micro_eur"] == 10_000 + 20 * 1000
        assert c["mois"]["depuis"] == "2026-11-01" and c["mois"]["jusqu_a"] == "2026-11-10"

    def test_us313_ca1_la_projection_ne_depend_pas_de_la_periode_affichee(self, db):
        for jour in range(4, 11):
            _ligne(db, date(2026, 11, jour), cout_micro=1000)
        db.commit()
        court = cout.cout(db, _filtres(depuis=J, jusqu_a=J), aujourd_hui=J)
        long = cout.cout(db, _filtres(), aujourd_hui=J)
        assert court["mois"] == long["mois"]

    def test_us313_ca1_dernier_jour_du_mois_la_projection_est_le_cout_du_mois(self, db):
        fin = date(2026, 11, 30)
        _ligne(db, fin, cout_micro=4000)
        db.commit()
        c = cout.cout(db, _filtres(depuis=fin - timedelta(days=29), jusqu_a=fin), aujourd_hui=fin)
        assert c["mois"]["projection_fin_de_mois_micro_eur"] == c["mois"]["cout_micro_eur"] == 4000

    def test_us313_ca1_sans_ligne_chiffree_rien_n_est_invente(self, db):
        _ligne(db, cout_micro=None)
        db.commit()
        c = cout.cout(db, _filtres(), aujourd_hui=J)
        assert c["cout_micro_eur"] is None and c["cout_par_jardinier_actif_micro_eur"] is None
        assert c["mois"]["cout_micro_eur"] is None and c["mois"]["projection_fin_de_mois_micro_eur"] is None

    def test_us313_ca1_periode_sans_appel(self, db):
        c = cout.cout(db, _filtres(), aujourd_hui=J)
        assert c["appels"] == 0 and c["jardiniers_actifs"] == 0
        assert c["cout_par_jardinier_actif_micro_eur"] is None
        assert c["echanges_par_canal"] == [] and c["modeles_non_chiffres"] == []
        assert c["tarif_version"] is None


class TestCA2JardinierActif:

    def test_us313_ca2_un_jardinier_actif_a_au_moins_une_ligne_usage(self, db):
        _ligne(db, user_id=1, provenance="usage")
        _ligne(db, user_id=2, provenance="mesure")        # une mesure ne rend pas actif
        _ligne(db, user_id=3, provenance="test")
        _ligne(db, user_id=None, provenance="fond")       # un travail de fond n'a pas de jardinier
        db.commit()
        # Même en demandant les mesures, la définition ne change pas.
        for filtres in (_filtres(), _filtres(provenance="usage,fond,mesure,test")):
            assert cout.cout(db, filtres, aujourd_hui=J)["jardiniers_actifs"] == 1

    def test_us313_ca2_hors_periode_n_est_pas_actif(self, db):
        _ligne(db, J - timedelta(days=40), user_id=2)
        _ligne(db, J, user_id=1)
        db.commit()
        assert cout.cout(db, _filtres(), aujourd_hui=J)["jardiniers_actifs"] == 1

    def test_us313_ca2_un_jardinier_compte_une_fois(self, db):
        for _ in range(5):
            _ligne(db, user_id=1)
        db.commit()
        assert cout.cout(db, _filtres(), aujourd_hui=J)["jardiniers_actifs"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA3, CA5 — graphique, classement (routes existantes, mesure coût)
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3CA5Routes:

    def test_us313_ca3_le_cout_par_jour_se_ventile_par_modele_type_canal(self, db):
        _ligne(db, J, modele="m1", appel_type="agent", canal="pwa", cout_micro=500)
        _ligne(db, J, modele="m2", appel_type="question", canal="telegram", cout_micro=200)
        _ligne(db, J - timedelta(days=1), modele="m1", appel_type="agent", canal="pwa", cout_micro=300)
        db.commit()
        for dimension, cles in (("modele", {"m1", "m2"}), ("appel_type", {"agent", "question"}), ("canal", {"pwa", "telegram"})):
            s = agregats.serie(db, _filtres(), "cout_micro_eur", dimension)
            assert {x["cle"] for x in s["series"]} == cles
            assert sum(x["total"] for x in s["series"]) == 1000
            assert len(s["points"]) == 30

    def test_us313_ca5_les_dix_potagers_les_plus_couteux(self, db):
        for i in range(1, 13):
            db.add(Potager(id=100 + i, nom=f"P{i}", proprietaire_id=1))
        db.commit()
        for i in range(1, 13):
            _ligne(db, potager_id=100 + i, cout_micro=i * 1000)
            _ligne(db, potager_id=100 + i, cout_micro=i * 1000)
        db.commit()
        v = agregats.ventilation(db, _filtres(), "potager", "cout_micro_eur", limite=10)
        assert len(v["lignes"]) == 10 and v["nb_valeurs"] == 12
        assert v["lignes"][0]["libelle"] == "P12" and v["lignes"][0]["cout_micro_eur"] == 24_000
        assert v["lignes"][0]["appels"] == 2
        assert v["lignes"][0]["part"] == pytest.approx(24_000 / 156_000)      # sur TOUT le total
        assert v["lignes"][-1]["libelle"] == "P3"


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — coût d'un échange par canal
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Echanges:

    def test_us313_ca4_mediane_p95_maximum_et_appels_par_echange_par_canal(self, db):
        # canal pwa : 3 échanges de 1, 2 et 3 appels à 100 µ€ chacun → 100, 200, 300
        for n, ref in ((1, "a"), (2, "b"), (3, "c")):
            for _ in range(n):
                _ligne(db, canal="pwa", echange_ref=ref, cout_micro=100)
        _ligne(db, canal="telegram", echange_ref="t1", cout_micro=50)
        db.commit()

        lignes = {l["canal"]: l for l in cout.cout(db, _filtres(), aujourd_hui=J)["echanges_par_canal"]}

        pwa = lignes["pwa"]
        assert pwa["nb_echanges"] == 3
        assert pwa["cout_micro_eur"] == {"mediane": 200.0, "p95": 300.0, "maximum": 300.0}
        assert pwa["appels"]["mediane"] == 2.0 and pwa["appels"]["maximum"] == 3.0
        assert lignes["telegram"]["cout_micro_eur"]["mediane"] == 50.0

    def test_us313_ca4_les_lignes_sans_echange_n_en_forment_pas_un(self, db):
        _ligne(db, echange_ref=None)
        db.commit()
        assert cout.cout(db, _filtres(), aujourd_hui=J)["echanges_par_canal"] == []

    def test_us313_ca4_un_echange_non_chiffre_est_signale_pas_compte_a_zero(self, db):
        _ligne(db, echange_ref="a", cout_micro=400)
        _ligne(db, echange_ref="b", cout_micro=None)
        db.commit()
        pwa = cout.cout(db, _filtres(), aujourd_hui=J)["echanges_par_canal"][0]
        assert pwa["nb_echanges"] == 2 and pwa["echanges_non_chiffres"] == 1
        assert pwa["cout_micro_eur"]["mediane"] == 400.0


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — marge
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6Marge:

    def test_us313_ca6_le_cout_de_chaque_jardinier_actif_median_p95_maximum(self, db):
        _quatre_jardiniers(db)         # 0,60 / 0,30 / 0,20 / 0,10 € sur 30 jours
        p = cout.cout(db, _filtres(), aujourd_hui=J)["par_jardinier"]
        assert p["nb"] == 4
        assert p["periode"]["mediane"] == 200_000                  # rang le plus proche
        assert p["periode"]["p95"] == 600_000 and p["periode"]["maximum"] == 600_000

    def test_us313_ca6_le_cout_mensuel_ramene_la_periode_a_trente_jours(self, db):
        _ligne(db, J, user_id=1, cout_micro=700)                   # période de 7 jours
        db.commit()
        p = cout.cout(db, _filtres(depuis=J - timedelta(days=6)), aujourd_hui=J)["par_jardinier"]
        assert p["periode"]["maximum"] == 700
        assert p["mensuel"]["maximum"] == pytest.approx(700 * 30 / 7)

    def test_us313_ca6_un_jardinier_actif_sans_ligne_chiffree_compte_pour_zero(self, db):
        _ligne(db, user_id=1, cout_micro=900)
        _ligne(db, user_id=2, cout_micro=None)
        db.commit()
        p = cout.cout(db, _filtres(), aujourd_hui=J)["par_jardinier"]
        assert p["nb"] == 2 and p["periode"]["mediane"] == 0.0

    def test_us313_ca6_aucun_jardinier_actif_aucune_distribution(self, db):
        p = cout.cout(db, _filtres(), aujourd_hui=J)["par_jardinier"]
        assert p["nb"] == 0 and p["periode"]["mediane"] is None and p["mensuel"]["p95"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7, CA8 — non chiffrés, version de grille
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7CA8:

    def test_us313_ca7_les_appels_non_chiffres_et_leurs_modeles(self, db):
        _ligne(db, modele="inconnu/a", cout_micro=None)
        _ligne(db, modele="inconnu/a", cout_micro=None)
        _ligne(db, modele="inconnu/b", cout_micro=None)
        _ligne(db, modele="mistral/small", cout_micro=100)
        _ligne(db, modele="mistral/small", cout_micro=0, issue="quota")       # un échec à 0 est chiffré
        db.commit()
        c = cout.cout(db, _filtres(), aujourd_hui=J)
        assert c["lignes_non_chiffrees"] == 3
        assert c["modeles_non_chiffres"] == [{"modele": "inconnu/a", "appels": 2}, {"modele": "inconnu/b", "appels": 1}]

    def test_us313_ca7_tout_est_chiffre_rien_a_signaler(self, db):
        _ligne(db, cout_micro=100)
        db.commit()
        c = cout.cout(db, _filtres(), aujourd_hui=J)
        assert c["lignes_non_chiffrees"] == 0 and c["modeles_non_chiffres"] == []

    def test_us313_ca8_la_version_de_grille_dominante(self, db):
        for _ in range(3):
            _ligne(db, tarif_version="2026-11-12")
        _ligne(db, tarif_version="2026-10-01")
        _ligne(db, tarif_version=None, cout_micro=None)
        db.commit()
        c = cout.cout(db, _filtres(), aujourd_hui=J)
        assert c["tarif_version"] == "2026-11-12"
        assert c["versions_tarif"] == {"2026-10-01": 1, "2026-11-12": 3}


# ═════════════════════════════════════════════════════════════════════════════
# Filtres de la coquille
# ═════════════════════════════════════════════════════════════════════════════

class TestFiltres:

    def test_us313_la_provenance_par_defaut_exclut_les_mesures(self, db):
        _ligne(db, provenance="usage", cout_micro=100)
        _ligne(db, provenance="mesure", cout_micro=9000)
        db.commit()
        assert cout.cout(db, _filtres(), aujourd_hui=J)["cout_micro_eur"] == 100
        assert cout.cout(db, _filtres(provenance="mesure"), aujourd_hui=J)["cout_micro_eur"] == 9000

    def test_us313_le_filtre_de_canal_s_applique_au_mois_et_aux_echanges(self, db):
        _ligne(db, canal="pwa", echange_ref="a", cout_micro=100)
        _ligne(db, canal="telegram", echange_ref="b", cout_micro=900)
        db.commit()
        c = cout.cout(db, _filtres(canal="telegram"), aujourd_hui=J)
        assert c["cout_micro_eur"] == 900 and c["mois"]["cout_micro_eur"] == 900
        assert [l["canal"] for l in c["echanges_par_canal"]] == ["telegram"]


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
            User(id=1, email=ADMIN, nom="Admin"),
            User(id=2, email="jardinier@example.com", nom="Jardinier"),
            Potager(id=1, nom="Potager A", proprietaire_id=1),
        ])
        _ligne(s, date.today(), user_id=2, echange_ref="e1", cout_micro=EUR // 10)
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

    def test_us313_sans_jeton_401_jardinier_403(self, api):
        assert api.get("/admin/pilotage/cout").status_code == 401
        assert api.get("/admin/pilotage/cout", headers=_en_tete(2)).status_code == 403

    def test_us313_l_administrateur_lit_le_cout(self, api):
        r = api.get("/admin/pilotage/cout", headers=_en_tete(1))
        assert r.status_code == 200, r.text
        corps = r.json()
        assert corps["cout_micro_eur"] == EUR // 10 and corps["jardiniers_actifs"] == 1
        assert corps["cout_par_jardinier_actif_micro_eur"] == EUR // 10

    def test_us313_un_filtre_hors_vocabulaire_422(self, api):
        assert api.get("/admin/pilotage/cout?canal=zzz", headers=_en_tete(1)).status_code == 422

    def test_us313_aucune_ecriture(self, api):
        for methode in (api.post, api.put, api.patch, api.delete):
            assert methode("/admin/pilotage/cout", headers=_en_tete(1)).status_code in (404, 405)

    def test_us313_le_service_n_appelle_aucun_modele(self):
        import re
        source = (ROOT / "app/services/pilotage/cout.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(llm\.(groq_client|routeur)|groq|mistralai|openai)", source, re.M)
        assert not re.search(r"appeler_chat|appeler_transcription|get_client", source)
