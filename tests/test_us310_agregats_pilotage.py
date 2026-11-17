"""
tests/test_us310_agregats_pilotage.py — [US-310] Exposer les agrégats de pilotage à l'administrateur.

Service `app/services/pilotage/agregats.py` + routes `/admin/pilotage/{synthese,series,ventilation,echanges}`.
Les lignes de `conso_tokens` sont écrites à la main : ce qu'on vérifie, ce sont les chiffres rendus.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import metriques_routage
from app.services.pilotage import agregats
from database.db import Base, tenant_scope
from database.models import ConsoTokens, Potager, User

ROOT = Path(__file__).resolve().parent.parent
J = date(2026, 11, 10)          # « aujourd'hui » des jeux de données
ADMIN = "admin@example.com"


# ─────────────────────────────────────────────────────────────────────────────
# Jeux de données
# ─────────────────────────────────────────────────────────────────────────────

def _ligne(db, jour: date = J, *, potager_id: int = 1, user_id: int | None = 1,
           appel_type: str = "agent", modele: str = "mistral/small", tokens_in: int = 100,
           tokens_out: int = 10, tokens_cache: int = 0, latence_ms: int = 200,
           issue: str = "ok", provenance: str = "usage", canal: str = "pwa",
           unite: str = "jeton", echange_ref: str | None = None, cout: int | None = None,
           version_app: str | None = "3.130.0", heure: int = 10) -> ConsoTokens:
    ligne = ConsoTokens(
        potager_id=potager_id, user_id=user_id, date=jour, appel_type=appel_type, modele=modele,
        tokens_in=tokens_in, tokens_out=tokens_out, tokens_cache=tokens_cache,
        latence_ms=latence_ms, issue=issue, provenance=provenance, canal=canal, unite=unite,
        echange_ref=echange_ref, cout_micro_eur=cout, version_app=version_app,
        cree_le=datetime(jour.year, jour.month, jour.day, heure, 30),
    )
    db.add(ligne)
    return ligne


def _filtres(depuis: date = J - timedelta(days=6), jusqu_a: date = J, **kw) -> agregats.Filtres:
    return agregats.construire_filtres(depuis=depuis, jusqu_a=jusqu_a, **kw)


@pytest.fixture
def db(test_db):
    test_db.add_all([
        Potager(id=1, nom="Potager A", proprietaire_id=1),
        Potager(id=2, nom="Potager B", proprietaire_id=2),
        User(id=1, nom="Alice", email="alice@example.com"),
        User(id=2, nom="Bob", email="bob@example.com"),
    ])
    test_db.commit()
    return test_db


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — synthèse
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Synthese:

    def test_us310_ca1_les_chiffres_de_la_periode(self, db):
        _ligne(db, tokens_in=1000, tokens_out=100, tokens_cache=400, latence_ms=100, cout=50)
        _ligne(db, tokens_in=2000, tokens_out=300, tokens_cache=600, latence_ms=300, cout=70)
        _ligne(db, tokens_in=3000, tokens_out=0, latence_ms=900, issue="quota", cout=0)
        db.commit()

        m = agregats.synthese(db, _filtres())["mesures"]

        assert m["appels"] == 3
        assert (m["jetons_entree"], m["jetons_sortie"], m["jetons_cache"]) == (6000, 400, 1000)
        assert m["taux_cache"] == pytest.approx(1000 / 6000)
        assert m["cout_micro_eur"] == 120 and m["cout_eur"] == pytest.approx(0.00012)
        assert m["issues"] == {"ok": 2, "quota": 1}
        assert m["latence_p50_ms"] == 300.0 and m["latence_p95_ms"] == 900.0
        assert m["jetons_entree_mediane_par_appel"] == 2000.0

    def test_us310_ca1_la_periode_precedente_a_la_meme_duree(self, db):
        _ligne(db, J, tokens_in=500)
        _ligne(db, J - timedelta(days=7), tokens_in=100)     # 1er jour précédent
        _ligne(db, J - timedelta(days=13), tokens_in=200)    # dernier jour précédent
        _ligne(db, J - timedelta(days=14), tokens_in=9999)   # avant : hors des deux périodes
        db.commit()

        corps = agregats.synthese(db, _filtres())

        assert corps["periode_precedente"]["depuis"] == "2026-10-28"
        assert corps["periode_precedente"]["jusqu_a"] == "2026-11-03"
        assert corps["mesures"]["jetons_entree"] == 500
        assert corps["mesures_precedentes"]["jetons_entree"] == 300
        assert corps["mesures_precedentes"]["appels"] == 2

    def test_us310_ca1_periode_sans_appel_ni_division_par_zero(self, db):
        m = agregats.synthese(db, _filtres())["mesures"]
        assert m["appels"] == 0 and m["taux_cache"] is None
        assert m["cout_micro_eur"] is None and m["latence_p95_ms"] is None
        assert m["issues"] == {}

    def test_us310_ca1_cout_nul_quand_aucune_ligne_n_est_chiffree(self, db):
        """Sans US-309 (ou modèle hors grille) le coût est None, jamais 0 inventé."""
        _ligne(db, cout=None)
        _ligne(db, cout=None)
        db.commit()
        m = agregats.synthese(db, _filtres())["mesures"]
        assert m["cout_micro_eur"] is None and m["cout_eur"] is None
        assert m["lignes_non_chiffrees"] == 2

    def test_us310_ca1_un_cout_partiel_est_signale(self, db):
        _ligne(db, cout=40)
        _ligne(db, cout=None)
        db.commit()
        m = agregats.synthese(db, _filtres())["mesures"]
        assert m["cout_micro_eur"] == 40 and m["lignes_non_chiffrees"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — séries
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2Series:

    def test_us310_ca2_une_serie_par_jour_avec_les_jours_vides_a_zero(self, db):
        _ligne(db, J, tokens_in=300)
        _ligne(db, J, tokens_in=200)
        _ligne(db, J - timedelta(days=2), tokens_in=50)
        db.commit()

        s = agregats.serie(db, _filtres(), mesure="jetons_entree")

        assert len(s["points"]) == 7 and s["points"][-1] == "2026-11-10" and s["pas"] == "jour"
        assert s["total"] == [0, 0, 0, 0, 50, 0, 500]
        assert s["series"][0]["cle"] == "total"

    @pytest.mark.parametrize("dimension,colonne,valeurs", [
        ("modele", "modele", ("mistral/small", "groq/llama")),
        ("appel_type", "appel_type", ("agent", "synthese")),
        ("canal", "canal", ("pwa", "telegram")),
        ("provenance", "provenance", ("usage", "fond")),
        ("issue", "issue", ("ok", "erreur")),
        ("version", "version_app", ("3.130.0", "3.129.0")),
    ])
    def test_us310_ca2_ventilee_par_chaque_dimension(self, db, dimension, colonne, valeurs):
        _ligne(db, tokens_in=100, **{colonne: valeurs[0]})
        _ligne(db, tokens_in=40, **{colonne: valeurs[1]})
        db.commit()

        s = agregats.serie(db, _filtres(), mesure="jetons_entree", dimension=dimension)

        assert {x["cle"]: x["total"] for x in s["series"]} == {valeurs[0]: 100, valeurs[1]: 40}
        assert s["series"][0]["cle"] == valeurs[0]          # la plus grosse d'abord
        assert sum(s["total"]) == 140

    def test_us310_ca2_par_heure_sur_une_journee(self, db):
        _ligne(db, J, tokens_in=10, heure=8)
        _ligne(db, J, tokens_in=20, heure=8)
        _ligne(db, J, tokens_in=5, heure=23)
        db.commit()

        s = agregats.serie(db, _filtres(depuis=J, jusqu_a=J), mesure="jetons_entree")

        assert s["pas"] == "heure" and len(s["points"]) == 24
        assert s["total"][8] == 30 and s["total"][23] == 5 and sum(s["total"]) == 35

    def test_us310_ca2_le_pas_heure_exige_une_seule_journee(self, db):
        with pytest.raises(agregats.FiltreInvalideError):
            agregats.serie(db, _filtres(), pas="heure")

    @pytest.mark.parametrize("kw", [
        {"mesure": "nimporte"}, {"dimension": "potager"}, {"dimension": "inconnue"}, {"pas": "mois"},
    ])
    def test_us310_ca2_parametre_hors_vocabulaire_refuse(self, db, kw):
        with pytest.raises(agregats.FiltreInvalideError):
            agregats.serie(db, _filtres(), **kw)

    def test_us310_ca2_serie_de_cout_distingue_zero_et_inconnu(self, db):
        _ligne(db, J, cout=30)
        _ligne(db, J - timedelta(days=1), cout=None)
        db.commit()
        s = agregats.serie(db, _filtres(), mesure="cout_micro_eur")
        assert s["total"][-1] == 30 and s["total"][-2] is None and s["total"][0] is None

    def test_us310_ca2_la_somme_de_la_serie_est_celle_de_la_synthese(self, db):
        for i in range(7):
            _ligne(db, J - timedelta(days=i), tokens_in=100 + i, modele=f"m{i % 2}")
        db.commit()
        f = _filtres()
        assert sum(agregats.serie(db, f, "jetons_entree", "modele")["total"]) == \
            agregats.synthese(db, f)["mesures"]["jetons_entree"]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — ventilation
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3Ventilation:

    def test_us310_ca3_classement_par_potager_avec_libelle_et_part(self, db):
        _ligne(db, potager_id=1, tokens_in=600)
        _ligne(db, potager_id=2, tokens_in=300)
        _ligne(db, potager_id=2, tokens_in=100)
        db.commit()

        v = agregats.ventilation(db, _filtres(), "potager", mesure="jetons_entree")

        assert [(l["cle"], l["libelle"], l["valeur"]) for l in v["lignes"]] == [
            (1, "Potager A", 600), (2, "Potager B", 400)]
        assert v["total"] == 1000 and v["lignes"][0]["part"] == pytest.approx(0.6)

    def test_us310_ca3_classement_par_utilisateur_sans_adresse_email(self, db):
        for utilisateur in (1, 1, 1, 2, 2, None):
            _ligne(db, user_id=utilisateur, provenance="fond" if utilisateur is None else "usage")
        db.commit()

        v = agregats.ventilation(db, _filtres(), "utilisateur", mesure="appels")

        assert [(l["libelle"], l["valeur"]) for l in v["lignes"]][:2] == [("Alice", 3), ("Bob", 2)]
        assert any(l["cle"] == agregats.CLE_ABSENTE for l in v["lignes"])
        assert "@" not in str(v)

    def test_us310_ca3_la_limite_coupe_mais_la_part_reste_sur_le_total(self, db):
        for i, jetons in enumerate((500, 300, 200)):
            _ligne(db, modele=f"m{i}", tokens_in=jetons)
        db.commit()

        v = agregats.ventilation(db, _filtres(), "modele", mesure="jetons_entree", limite=2)

        assert [l["cle"] for l in v["lignes"]] == ["m0", "m1"]
        assert v["nb_valeurs"] == 3 and v["total"] == 1000
        assert v["lignes"][1]["part"] == pytest.approx(0.3)

    def test_us310_ca3_chaque_ligne_porte_les_colonnes_des_tableaux_de_la_vue(self, db):
        _ligne(db, appel_type="agent", tokens_in=100, tokens_out=10)
        _ligne(db, appel_type="agent", tokens_in=300, tokens_out=30)
        db.commit()
        ligne = agregats.ventilation(db, _filtres(), "appel_type")["lignes"][0]
        assert (ligne["appels"], ligne["jetons_entree"], ligne["jetons_sortie"]) == (2, 400, 40)
        assert ligne["jetons_entree_mediane_par_appel"] == 100.0

    @pytest.mark.parametrize("kw", [{"dimension": "inconnue"}, {"dimension": "modele", "mesure": "x"},
                                    {"dimension": "modele", "limite": 0}, {"dimension": "modele", "limite": 201}])
    def test_us310_ca3_parametre_hors_vocabulaire_refuse(self, db, kw):
        with pytest.raises(agregats.FiltreInvalideError):
            agregats.ventilation(db, _filtres(), **kw)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — distribution par échange
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Echanges:

    def test_us310_ca4_distribution_par_echange(self, db):
        # échange a : 2 appels, 150 jetons, 30 µ€ ; b : 1 appel, 20 jetons, 10 µ€ ; c : 1 appel, 1000 jetons, 500 µ€
        _ligne(db, echange_ref="a", tokens_in=100, tokens_out=10, cout=10)
        _ligne(db, echange_ref="a", tokens_in=30, tokens_out=10, cout=20)
        _ligne(db, echange_ref="b", tokens_in=15, tokens_out=5, cout=10)
        _ligne(db, echange_ref="c", tokens_in=900, tokens_out=100, cout=500)
        _ligne(db, echange_ref=None, tokens_in=7)       # avant v74 : à part
        db.commit()

        e = agregats.echanges(db, _filtres())

        assert e["nb_echanges"] == 3 and e["lignes_sans_echange"] == 1
        assert e["appels"] == {"mediane": 1.0, "p95": 2.0, "maximum": 2.0}
        assert e["jetons"] == {"mediane": 150.0, "p95": 1000.0, "maximum": 1000.0}
        assert e["cout_micro_eur"] == {"mediane": 30.0, "p95": 500.0, "maximum": 500.0}

    def test_us310_ca4_audio_et_caracteres_ne_comptent_pas_dans_les_jetons_de_l_echange(self, db):
        _ligne(db, echange_ref="a", tokens_in=100, tokens_out=10)
        _ligne(db, echange_ref="a", unite="seconde", appel_type="dictee", tokens_in=45, tokens_out=0)
        _ligne(db, echange_ref="a", unite="caractere", appel_type="voix", tokens_in=2000, tokens_out=0)
        db.commit()
        e = agregats.echanges(db, _filtres())
        assert e["jetons"]["maximum"] == 110.0 and e["appels"]["maximum"] == 3.0

    def test_us310_ca4_sans_echange_rien_n_est_invente(self, db):
        e = agregats.echanges(db, _filtres())
        assert e["nb_echanges"] == 0
        assert e["jetons"] == {"mediane": None, "p95": None, "maximum": None}

    def test_us310_ca4_echanges_non_chiffres_signales(self, db):
        _ligne(db, echange_ref="a", cout=10)
        _ligne(db, echange_ref="b", cout=None)
        db.commit()
        e = agregats.echanges(db, _filtres())
        assert e["echanges_non_chiffres"] == 1 and e["cout_micro_eur"]["maximum"] == 10.0


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — filtres et provenance par défaut
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5Filtres:

    def test_us310_ca5_scenario_gherkin_provenance_par_defaut_puis_mesure(self, db):
        for _ in range(100):
            _ligne(db, provenance="usage")
        for _ in range(400):
            _ligne(db, provenance="mesure")
        db.commit()

        assert agregats.synthese(db, _filtres())["mesures"]["appels"] == 100
        assert agregats.synthese(db, _filtres(provenance="mesure"))["mesures"]["appels"] == 400

    def test_us310_ca5_sans_filtre_seuls_usage_et_fond_sont_comptes(self, db):
        for provenance in ("usage", "fond", "mesure", "test", "historique"):
            _ligne(db, provenance=provenance)
        db.commit()
        f = _filtres()
        assert f.provenances == ("usage", "fond")
        assert agregats.synthese(db, f)["mesures"]["appels"] == 2

    def test_us310_ca5_plusieurs_provenances_separees_par_une_virgule(self, db):
        for provenance in ("usage", "mesure", "test"):
            _ligne(db, provenance=provenance)
        db.commit()
        assert agregats.synthese(db, _filtres(provenance="usage,test"))["mesures"]["appels"] == 2

    @pytest.mark.parametrize("filtre,attendu", [
        ({"canal": "telegram"}, 1), ({"modele": "groq/llama"}, 1),
        ({"appel_type": "synthese"}, 1), ({"potager_id": 2}, 1),
    ])
    def test_us310_ca5_chaque_filtre_restreint(self, db, filtre, attendu):
        _ligne(db, canal="pwa", modele="mistral/small", appel_type="agent", potager_id=1)
        _ligne(db, canal="telegram", modele="groq/llama", appel_type="synthese", potager_id=2)
        db.commit()
        assert agregats.synthese(db, _filtres(**filtre))["mesures"]["appels"] == attendu

    def test_us310_ca5_les_filtres_s_appliquent_aussi_a_la_periode_precedente(self, db):
        _ligne(db, J - timedelta(days=8), canal="telegram")
        _ligne(db, J - timedelta(days=8), canal="pwa")
        db.commit()
        corps = agregats.synthese(db, _filtres(canal="telegram"))
        assert corps["mesures_precedentes"]["appels"] == 1

    @pytest.mark.parametrize("kw", [
        {"provenance": "n_importe_quoi"}, {"provenance": "usage,x"}, {"canal": "fax"},
        {"depuis": J, "jusqu_a": J - timedelta(days=1)}, {"depuis": J - timedelta(days=500), "jusqu_a": J},
    ])
    def test_us310_ca5_filtre_invalide_refuse(self, kw):
        with pytest.raises(agregats.FiltreInvalideError):
            agregats.construire_filtres(**{"depuis": J - timedelta(days=6), "jusqu_a": J, **kw})

    def test_us310_ca5_periode_par_defaut_sept_jours_glissants(self):
        f = agregats.construire_filtres(aujourd_hui=J)
        assert (f.depuis, f.jusqu_a, f.jours) == (J - timedelta(days=6), J, 7)


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — unités
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6Unites:

    def test_us310_ca6_les_jetons_ne_somment_que_les_lignes_d_unite_jeton(self, db):
        _ligne(db, tokens_in=1000, tokens_out=100)
        _ligne(db, appel_type="dictee", unite="seconde", tokens_in=60, tokens_out=0)
        _ligne(db, appel_type="voix", unite="caractere", tokens_in=2500, tokens_out=0)
        db.commit()

        m = agregats.synthese(db, _filtres())["mesures"]

        assert (m["jetons_entree"], m["jetons_sortie"]) == (1000, 100)
        assert m["secondes_audio"] == 60 and m["caracteres"] == 2500
        assert m["appels"] == 3

    def test_us310_ca6_la_mediane_des_jetons_par_appel_ignore_audio_et_caracteres(self, db):
        _ligne(db, tokens_in=100)
        _ligne(db, tokens_in=300)
        _ligne(db, unite="seconde", tokens_in=9000)
        db.commit()
        assert agregats.synthese(db, _filtres())["mesures"]["jetons_entree_mediane_par_appel"] == 100.0

    def test_us310_ca6_le_taux_de_cache_se_calcule_sur_les_seuls_jetons(self, db):
        _ligne(db, tokens_in=1000, tokens_cache=500)
        _ligne(db, unite="seconde", tokens_in=1000, tokens_cache=0)
        db.commit()
        assert agregats.synthese(db, _filtres())["mesures"]["taux_cache"] == 0.5

    def test_us310_ca6_les_mesures_distinctes_se_demandent_a_part(self, db):
        _ligne(db, unite="seconde", appel_type="dictee", tokens_in=60)
        _ligne(db, unite="caractere", appel_type="voix", tokens_in=500)
        db.commit()
        f = _filtres()
        assert sum(agregats.serie(db, f, "secondes_audio")["total"]) == 60
        assert sum(agregats.serie(db, f, "caracteres")["total"]) == 500
        assert sum(agregats.serie(db, f, "jetons_entree")["total"]) == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — routes protégées, en lecture seule
# ═════════════════════════════════════════════════════════════════════════════

ROUTES = ["/admin/pilotage/synthese", "/admin/pilotage/series",
          "/admin/pilotage/ventilation?dimension=modele", "/admin/pilotage/echanges"]


@pytest.fixture
def api(monkeypatch):
    """TestClient sur un moteur SQLite partagé entre threads, avec un admin, un jardinier et des lignes."""
    from app.api import main

    moteur = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(bind=moteur)
    Session = sessionmaker(bind=moteur)
    with Session() as s:
        s.add_all([
            User(id=1, email=ADMIN, nom="Admin"),
            User(id=2, email="jardinier@example.com", nom="Jardinier"),
            Potager(id=1, nom="Potager A", proprietaire_id=1),
            Potager(id=2, nom="Potager B", proprietaire_id=2),
        ])
        for provenance, n in (("usage", 3), ("mesure", 4)):
            for i in range(n):
                _ligne(s, J, provenance=provenance, potager_id=1 + i % 2, echange_ref=f"{provenance}{i}")
        s.commit()
    monkeypatch.setattr(main, "SessionLocal", Session)
    monkeypatch.setattr(main, "ADMIN_EMAIL", ADMIN)
    main.app.state.limiter.reset()
    with TestClient(main.app) as client:
        yield client
    moteur.dispose()


def _en_tete(user_id: int) -> dict:
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user_id)}"}


class TestCA7Acces:

    @pytest.mark.parametrize("chemin", ROUTES)
    def test_us310_ca7_sans_jeton_401(self, api, chemin):
        assert api.get(chemin).status_code == 401

    @pytest.mark.parametrize("chemin", ROUTES)
    def test_us310_ca7_un_jardinier_recoit_403(self, api, chemin):
        assert api.get(chemin, headers=_en_tete(2)).status_code == 403

    @pytest.mark.parametrize("chemin", ROUTES)
    def test_us310_ca7_l_administrateur_lit(self, api, chemin):
        reponse = api.get(chemin + ("&" if "?" in chemin else "?") + f"depuis={J}&jusqu_a={J}",
                          headers=_en_tete(1))
        assert reponse.status_code == 200, reponse.text

    def test_us310_ca7_scenario_gherkin_http(self, api):
        params = f"?depuis={J - timedelta(days=6)}&jusqu_a={J}"
        admin = api.get("/admin/pilotage/synthese" + params, headers=_en_tete(1)).json()
        assert admin["mesures"]["appels"] == 3
        mesure = api.get("/admin/pilotage/synthese" + params + "&provenance=mesure", headers=_en_tete(1)).json()
        assert mesure["mesures"]["appels"] == 4
        assert api.get("/admin/pilotage/synthese" + params, headers=_en_tete(2)).status_code == 403

    @pytest.mark.parametrize("chemin", ROUTES)
    def test_us310_ca7_aucune_ecriture(self, api, chemin):
        base = chemin.split("?")[0]
        for methode in (api.post, api.put, api.patch, api.delete):
            assert methode(base, headers=_en_tete(1)).status_code == 405

    @pytest.mark.parametrize("chemin,fragment", [
        ("/admin/pilotage/synthese?provenance=x", "provenance"),
        ("/admin/pilotage/series?mesure=x", "mesure"),
        ("/admin/pilotage/series?dimension=potager", "dimension"),
        ("/admin/pilotage/ventilation?dimension=x", "dimension"),
        ("/admin/pilotage/ventilation", ""),
        ("/admin/pilotage/synthese?canal=fax", "canal"),
        ("/admin/pilotage/synthese?depuis=2026-11-10&jusqu_a=2026-11-01", "depuis"),
    ])
    def test_us310_ca7_parametre_invalide_422(self, api, chemin, fragment):
        reponse = api.get(chemin, headers=_en_tete(1))
        assert reponse.status_code == 422 and fragment in reponse.text

    def test_us310_ca7_les_routes_rendent_le_meme_total(self, api):
        params = f"depuis={J}&jusqu_a={J}&provenance=usage,mesure"
        h = _en_tete(1)
        synthese = api.get(f"/admin/pilotage/synthese?{params}", headers=h).json()["mesures"]
        serie = api.get(f"/admin/pilotage/series?{params}&mesure=jetons_entree", headers=h).json()
        ventilation = api.get(f"/admin/pilotage/ventilation?{params}&dimension=potager&mesure=jetons_entree",
                              headers=h).json()
        assert sum(serie["total"]) == ventilation["total"] == synthese["jetons_entree"] == 700


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — lecture de tous les potagers, par un chemin explicite
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8LectureHorsPerimetre:

    def test_us310_ca8_lit_tous_les_potagers_meme_sous_un_scope_de_potager(self, db):
        _ligne(db, potager_id=1)
        _ligne(db, potager_id=2)
        _ligne(db, potager_id=2)
        db.commit()
        with tenant_scope(1):
            assert agregats.synthese(db, _filtres())["mesures"]["appels"] == 3

    def test_us310_ca8_refuse_si_la_table_est_sous_rls(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute.return_value.scalar.return_value = True
        assert agregats.table_sous_rls(db) is True
        with pytest.raises(agregats.LectureHorsPerimetreError), agregats.lecture_toute_la_plateforme(db):
            pytest.fail("la lecture ne doit pas s'ouvrir")

    def test_us310_ca8_postgresql_sans_rls_sur_la_table_la_lecture_s_ouvre(self):
        db = MagicMock()
        db.get_bind.return_value.dialect.name = "postgresql"
        db.execute.return_value.scalar.return_value = False
        with agregats.lecture_toute_la_plateforme(db):
            pass

    def test_us310_ca8_aucune_migration_ne_met_conso_tokens_sous_rls(self):
        for chemin in sorted((ROOT / "migrations").glob("migration_v*.sql")):
            sql = chemin.read_text(encoding="utf-8")
            assert not re.search(r"ALTER TABLE\s+conso_tokens\s+ENABLE ROW LEVEL SECURITY", sql, re.I), chemin.name
            assert not re.search(r"CREATE POLICY[^;]*ON\s+conso_tokens", sql, re.I), chemin.name

    def test_us310_ca8_le_service_ne_contourne_jamais_tenant_scope(self):
        source = (ROOT / "app" / "services" / "pilotage" / "agregats.py").read_text(encoding="utf-8")
        code = "\n".join(l for l in source.splitlines() if not l.lstrip().startswith("#"))
        assert "tenant_scope(" not in code and "current_potager_id" not in code
        assert "lecture_toute_la_plateforme" in code

    def test_us310_ca8_la_lecture_passe_par_le_chemin_explicite(self, db):
        with patch.object(agregats, "lecture_toute_la_plateforme", wraps=agregats.lecture_toute_la_plateforme) as chemin:
            agregats.synthese(db, _filtres())
        assert chemin.call_count >= 2          # au moins une lecture par période (courante, précédente)


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — zéro appel au modèle, percentiles en Python
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9ZeroModele:

    def test_us310_ca9_aucun_appel_au_modele(self, db):
        _ligne(db)
        db.commit()
        with patch("llm.passerelle.appeler_chat") as chat, patch("llm.passerelle._resoudre_client") as client:
            agregats.synthese(db, _filtres())
            agregats.serie(db, _filtres(), dimension="modele")
            agregats.ventilation(db, _filtres(), "modele")
            agregats.echanges(db, _filtres())
        chat.assert_not_called()
        client.assert_not_called()

    def test_us310_ca9_le_service_n_importe_ni_la_passerelle_d_appel_ni_un_client(self):
        source = (ROOT / "app" / "services" / "pilotage" / "agregats.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(llm\.(groq_client|routeur)|groq|mistralai|openai)", source, re.M)
        assert not re.search(r"appeler_chat|appeler_transcription|get_client", source)

    @pytest.mark.parametrize("valeurs", [[], [7], [3, 1, 2], list(range(1, 21)), [5, 5, 5, 100]])
    def test_us310_ca9_le_p95_est_celui_de_metriques_routage(self, valeurs):
        assert agregats.percentile(valeurs, 0.95) == metriques_routage._p95(valeurs)

    def test_us310_ca9_mediane_par_rang_le_plus_proche(self):
        assert agregats.percentile([10, 20, 30, 40], 0.5) == 20.0
        assert agregats.percentile([10, 20, 30], 0.5) == 20.0
        assert agregats.percentile([], 0.5) is None

    def test_us310_ca9_aucune_fonction_sql_de_percentile(self):
        source = (ROOT / "app" / "services" / "pilotage" / "agregats.py").read_text(encoding="utf-8")
        assert not re.search(r"percentile_cont|percentile_disc|\bNTILE\b", source, re.I)


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — performance et index
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10Performance:

    def test_us310_ca10_quatre_vingt_dix_jours_sur_cent_mille_lignes_sous_la_seconde(self, db):
        debut = J - timedelta(days=89)
        modeles = ["mistral/small", "mistral/large", "groq/llama"]
        types = ["agent", "synthese", "classification", "question"]
        lignes = [
            {"potager_id": 1 + i % 5, "user_id": 1 + i % 7, "date": debut + timedelta(days=i % 90),
             "appel_type": types[i % 4], "modele": modeles[i % 3], "tokens_in": 500 + i % 900,
             "tokens_out": 50 + i % 100, "tokens_cache": i % 300, "latence_ms": 100 + i % 2000,
             "issue": "ok" if i % 20 else "erreur", "provenance": "usage" if i % 10 else "fond",
             "echange_ref": f"e{i // 3}", "canal": "pwa" if i % 2 else "telegram", "unite": "jeton",
             "version_app": "3.130.0", "cout_micro_eur": 100 + i % 50,
             "cree_le": datetime.combine(debut + timedelta(days=i % 90), datetime.min.time()) + timedelta(hours=i % 24)}
            for i in range(100_000)
        ]
        db.execute(ConsoTokens.__table__.insert(), lignes)
        db.commit()
        f = _filtres(depuis=debut, jusqu_a=J)

        for nom, lecture in {
            "synthese": lambda: agregats.synthese(db, f),
            "series": lambda: agregats.serie(db, f, "jetons_entree", "modele"),
            "ventilation": lambda: agregats.ventilation(db, f, "appel_type"),
            "echanges": lambda: agregats.echanges(db, f),
        }.items():
            t0 = time.perf_counter()
            resultat = lecture()
            duree = time.perf_counter() - t0
            assert resultat
            assert duree < 1.0, f"{nom} : {duree:.2f} s"

    def test_us310_ca10_les_index_sont_dans_la_migration_et_dans_le_modele(self):
        sql = (ROOT / "migrations" / "migration_v78.sql").read_text(encoding="utf-8")
        for index in ("idx_conso_tokens_date_provenance", "idx_conso_tokens_cree_le"):
            assert f"CREATE INDEX IF NOT EXISTS {index}" in sql
        noms = {i.name for i in ConsoTokens.__table__.indexes}
        assert {"idx_conso_tokens_date_provenance", "idx_conso_tokens_cree_le"} <= noms

    def test_us310_ca10_l_index_d_echange_existe_deja(self):
        assert any(c.name == "echange_ref" and c.index for c in ConsoTokens.__table__.columns)

    def test_us310_ca10_migration_idempotente_et_rollback(self):
        assert "IF NOT EXISTS" in (ROOT / "migrations" / "migration_v78.sql").read_text(encoding="utf-8")
        rollback = (ROOT / "migrations" / "rollback_v78.sql").read_text(encoding="utf-8")
        assert rollback.count("DROP INDEX IF EXISTS") == 2


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — aucune requête hors services ; OpenAPI régénéré
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11Couche:

    def test_us310_ca11_aucun_db_query_hors_services(self):
        fichiers = [ROOT / "app" / "api" / "main.py", *(ROOT / "app" / "bot").glob("*.py")]
        motif = re.compile(r"\.query\(\s*(ConsoTokens|Potager|User)\b[^)]*\)[^\n]*conso|\.query\(\s*ConsoTokens\b")
        for chemin in fichiers:
            assert not motif.search(chemin.read_text(encoding="utf-8")), chemin.name

    def test_us310_ca11_les_routes_n_ouvrent_pas_de_requete_sql(self):
        source = (ROOT / "app" / "api" / "main.py").read_text(encoding="utf-8")
        debut = source.index("# ── Pilotage de la consommation du modèle [US-310]")
        fin = source.index('@app.get("/stats")')
        bloc = source[debut:fin]
        assert not re.search(r"\.query\(|\.execute\(|\.filter\(", bloc)

    def test_us310_ca11_openapi_decrit_les_quatre_routes(self):
        import json

        chemins = json.loads((ROOT / "docs" / "openapi.json").read_text(encoding="utf-8"))["paths"]
        for route in ("synthese", "series", "ventilation", "echanges"):
            assert f"/admin/pilotage/{route}" in chemins and "get" in chemins[f"/admin/pilotage/{route}"]
            assert set(chemins[f"/admin/pilotage/{route}"]) == {"get"}

    def test_us310_la_fiche_de_domaine_decrit_les_agregats(self):
        fiche = (ROOT / "docs" / "domaines" / "pilotage-llm.md").read_text(encoding="utf-8")
        assert "agregats.py" in fiche and "/admin/pilotage" in fiche
