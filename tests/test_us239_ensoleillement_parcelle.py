"""
tests/test_us239_ensoleillement_parcelle.py — [US-239] L'ensoleillement d'une
parcelle, distinct de son orientation.

Ce que ce fichier tient :
- vocabulaire fermé et normalisation d'US-161, refus avec la liste et les
  définitions en heures (CA1, CA1 bis) ;
- l'orientation (`exposition`) n'est ni convertie ni déduite (CA2) ;
- la saisie : bot sans modèle (CA4), PWA avec droits (CA5), liste (CA6) ;
- « Où les mettre » compare l'ensoleillement, la meilleure parcelle d'abord
  (CA7, CA7 bis, CA7 ter, CA8) ;
- isolation entre potagers.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import echeances_lots as ech
from app.services import interpreteur_commandes as interp
from app.services import parcelles as svc_parcelles
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import CultureConfig, Evenement, Parcelle, Potager, PotagerMembre, User
from utils.parcelles import (
    DEFINITIONS_ENSOLEILLEMENT, create_parcelle, normaliser_ensoleillement, update_parcelle,
)
from utils.stock import calcul_lots_pepiniere

LE_19_SEPT = date(2026, 9, 19)
CTX = TenantContext(user_id=1, potager_id=1, role="owner")


def _potagers(db, *ids):
    db.add(User(id=1, email="a@potager.test"))
    db.flush()
    db.add_all([Potager(id=i, nom=f"Potager {i}", proprietaire_id=1) for i in ids])
    db.commit()


# ── CA1, CA1 bis — vocabulaire fermé et définitions ──────────────────────────
class TestVocabulaire:
    @pytest.mark.parametrize("saisie, attendu", [
        ("plein soleil", "plein soleil"), ("Plein Soleil", "plein soleil"),
        ("mi ombre", "mi-ombre"), ("Mi-ombre", "mi-ombre"), ("OMBRE", "ombre"),
        ("  ombre ", "ombre"),
    ])
    def test_us239_ca1_normalisation_comme_us161(self, saisie, attendu):
        assert normaliser_ensoleillement(saisie) == attendu

    @pytest.mark.parametrize("saisie", ["sud", "Nord", "sud-est", "soleil le matin", "lumière artificielle"])
    def test_us239_ca1_hors_vocabulaire_refuse_avec_la_liste(self, saisie):
        with pytest.raises(ValueError) as e:
            normaliser_ensoleillement(saisie)
        assert (
            "plein soleil (6 h et plus de soleil direct), mi-ombre (3 à 6 h), "
            "ombre (moins de 3 h)"
        ) in str(e.value)

    def test_us239_ca1bis_les_trois_definitions_en_heures(self):
        assert DEFINITIONS_ENSOLEILLEMENT == {
            "plein soleil": "6 h et plus de soleil direct",
            "mi-ombre": "3 à 6 h",
            "ombre": "moins de 3 h",
        }

    def test_us239_ca1bis_vocabulaires_fiche_porte_les_definitions(self):
        v = svc_parcelles.vocabulaires_fiche()["ensoleillement"]
        assert v["ferme"] is True
        assert [(o["valeur"], o["definition"]) for o in v["options"]] == list(
            DEFINITIONS_ENSOLEILLEMENT.items()
        )


# ── CA2 — l'orientation reste ce qu'elle était ───────────────────────────────
class TestEcriture:
    def test_us239_ca2_orientation_inchangee_et_ensoleillement_non_renseigne(self, test_db):
        _potagers(test_db, 1)
        p = create_parcelle(test_db, "racines", exposition="Nord", potager_id=1)
        assert p.exposition == "Nord" and p.ensoleillement is None

        p, modifs = update_parcelle(test_db, "racines", potager_id=1, ensoleillement="Plein Soleil")
        assert p.ensoleillement == "plein soleil"
        assert p.exposition == "Nord"
        assert modifs == ["Ensoleillement : plein soleil (6 h et plus de soleil direct)"]

    def test_us239_ca1_valeur_refusee_conserve_la_valeur_precedente(self, test_db):
        _potagers(test_db, 1)
        create_parcelle(test_db, "racines", potager_id=1)
        update_parcelle(test_db, "racines", potager_id=1, ensoleillement="ombre")
        with pytest.raises(ValueError):
            update_parcelle(test_db, "racines", potager_id=1, ensoleillement="sud")
        assert test_db.query(Parcelle).one().ensoleillement == "ombre"

    def test_us239_ca2_none_remet_a_non_renseigne(self, test_db):
        _potagers(test_db, 1)
        create_parcelle(test_db, "racines", potager_id=1)
        update_parcelle(test_db, "racines", potager_id=1, ensoleillement="ombre")
        p, modifs = update_parcelle(test_db, "racines", potager_id=1, ensoleillement=None)
        assert p.ensoleillement is None
        assert modifs == ["Ensoleillement : non renseigné"]

    def test_us239_isolation_une_parcelle_d_un_autre_potager_n_est_pas_touchee(self, test_db):
        _potagers(test_db, 1, 2)
        create_parcelle(test_db, "racines", potager_id=1)
        create_parcelle(test_db, "racines", potager_id=2)
        update_parcelle(test_db, "racines", potager_id=2, ensoleillement="ombre")
        par_potager = {p.potager_id: p.ensoleillement for p in test_db.query(Parcelle).all()}
        assert par_potager == {1: None, 2: "ombre"}


# ── CA4 — le bot, sans modèle ────────────────────────────────────────────────
class TestBot:
    @pytest.mark.parametrize("phrase, nom, modification", [
        ("ensoleillement planche racines plein soleil", "planche racines", "ensoleillement=plein-soleil"),
        ("l'ensoleillement de la planche nord est mi-ombre", "planche nord", "ensoleillement=mi-ombre"),
        ("ensoleillement planche racines ombre", "planche racines", "ensoleillement=ombre"),
    ])
    def test_us239_ca4_reconnu_sans_modele(self, phrase, nom, modification):
        r = interp.interpreter(phrase, autoriser_modele=False)
        assert r is not None and (r.commande, r.sous_commande) == ("parcelle", "modifier")
        assert r.valeurs == {"nom": nom, "modification": modification}
        assert r.origine == interp.ORIGINE_REGLE

    def test_us239_gherkin_orientation_reconnue_puis_refusee_au_point_d_ecriture(self, test_db):
        """« sud » n'est pas traduit : la règle le transmet, l'écriture le refuse."""
        r = interp.interpreter("ensoleillement planche racines sud", autoriser_modele=False)
        assert r is not None and r.valeurs["modification"] == "ensoleillement=sud"
        _potagers(test_db, 1)
        create_parcelle(test_db, "planche racines", potager_id=1)
        with pytest.raises(ValueError, match=r"plein soleil \(6 h et plus de soleil direct\)"):
            update_parcelle(test_db, "planche racines", potager_id=1, ensoleillement="sud")

    def test_us239_ca4_recapitulatif_nomme_l_ensoleillement(self):
        r = interp.interpreter("ensoleillement planche racines plein soleil", autoriser_modele=False)
        assert "ensoleillement : *plein-soleil*" in interp.recapitulatif(r)


# ── CA5 — la PWA : droits et réponse ─────────────────────────────────────────
@pytest.fixture
def _engine():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(_engine, monkeypatch):
    from app.api import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_engine))
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def web(_engine):
    session = sessionmaker(bind=_engine)()
    yield session
    session.close()


def _potager_web(db):
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, "Potager de test")
    parcelle = create_parcelle(db, "planche", exposition="Nord", potager_id=potager.id)
    return user, potager, parcelle


class TestPwa:
    def test_us239_ca5_patch_ecrit_l_ensoleillement_sans_toucher_l_orientation(self, client, web):
        user, _, parcelle = _potager_web(web)
        h = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
        r = client.patch(f"/parcelles/{parcelle.id}", json={"ensoleillement": "Mi ombre"}, headers=h)
        assert r.status_code == 200
        assert r.json()["ensoleillement"] == "mi-ombre"
        assert r.json()["exposition"] == "Nord"

    def test_us239_ca5_patch_hors_vocabulaire_400_sous_le_champ(self, client, web):
        user, _, parcelle = _potager_web(web)
        h = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
        r = client.patch(f"/parcelles/{parcelle.id}", json={"ensoleillement": "sud"}, headers=h)
        assert r.status_code == 400
        detail = r.json()["detail"]
        assert detail["champ"] == "ensoleillement"
        assert "ombre (moins de 3 h)" in detail["message"]

    def test_us239_ca5_lecteur_ne_peut_pas_modifier(self, web):
        user, potager, parcelle = _potager_web(web)
        lecteur = TenantContext(user_id=user.id, potager_id=potager.id, role="viewer")
        with pytest.raises(PermissionInsuffisanteError):
            svc_parcelles.modifier_parcelle(web, lecteur, parcelle.id, {"ensoleillement": "ombre"})


# ── CA7 — « Où les mettre » ──────────────────────────────────────────────────
@pytest.fixture
def plan(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.flush()
    test_db.add_all([
        # A : ombre, 4 rangs libres ; B : mi-ombre, 1 rang ; C : plein soleil, 1 rang.
        Parcelle(id=1, nom="A", nom_normalise="a", potager_id=1, nb_rangs=4,
                 ensoleillement="ombre", ordre=1),
        Parcelle(id=2, nom="B", nom_normalise="b", potager_id=1, nb_rangs=1,
                 ensoleillement="mi-ombre", ordre=2),
        Parcelle(id=3, nom="C", nom_normalise="c", potager_id=1, nb_rangs=1,
                 ensoleillement="plein soleil", ordre=3),
        # D : orientation « Sud », ensoleillement non renseigné.
        Parcelle(id=4, nom="D", nom_normalise="d", potager_id=1, nb_rangs=3,
                 exposition="Sud", ordre=4),
        Parcelle(id=5, nom="Serre", nom_normalise="serre", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude", nb_rangs=3, ordre=5),
    ])
    test_db.add(CultureConfig(nom="chou", type_organe_recolte="feuille", exposition="plein soleil"))
    semis = Evenement(
        type_action="semis", culture="chou", quantite=48, unite="graines",
        date=datetime(2026, 8, 1), parcelle_id=5, potager_id=1, numero_lot=1,
    )
    test_db.add(semis)
    test_db.commit()
    test_db.add(Evenement(
        type_action="mise_en_godet", culture="chou", nb_plants_godets=40,
        nb_graines_semees=40, origine_graines_id=semis.id, parcelle_id=5,
        date=datetime(2026, 8, 20), potager_id=1,
    ))
    test_db.commit()
    return test_db


def _suggestions(db):
    lots = calcul_lots_pepiniere(db, LE_19_SEPT, potager_id=1)
    par_lot = ech.lire_echeances(db, CTX, lots, LE_19_SEPT)["par_lot"]
    (resultat,) = [v["ou_mettre"] for v in par_lot.values() if v.get("ou_mettre")]
    return {s["parcelle"]: s for s in resultat["suggestions"]}, [
        s["parcelle"] for s in resultat["suggestions"]
    ]


class TestOuMettre:
    def test_us239_ca7bis_la_meilleure_parcelle_vient_en_premier(self, plan):
        par_nom, ordre = _suggestions(plan)
        # C concordante, B à un cran, A à deux crans (déconseillée), D non comparable.
        assert ordre == ["C", "B", "A", "D"]
        assert par_nom["C"]["exposition"]["libelle"] == "plein soleil, comme la culture le demande"
        assert par_nom["B"]["exposition"]["libelle"] == "mi-ombre, pour une culture de plein soleil"

    def test_us239_ca7ter_deux_crans_deconseille_mais_propose(self, plan):
        par_nom, _ = _suggestions(plan)
        a = par_nom["A"]["exposition"]
        assert a["deconseille"] is True
        assert a["libelle"] == "déconseillé : ombre, pour une culture de plein soleil"

    def test_us239_ca8_ensoleillement_non_renseigne_invite_a_le_declarer(self, plan):
        par_nom, _ = _suggestions(plan)
        d = par_nom["D"]["exposition"]
        assert d["comparaison"] == ech.EXPO_NON_COMPARABLE
        assert d["libelle"] == "ensoleillement de la parcelle non renseigné"
        assert "ensoleillement D plein soleil" in d["invitation"]
        # L'orientation reste affichable, elle n'entre plus dans la comparaison.
        assert par_nom["D"]["orientation"] == "Sud"

    def test_us239_ca7_une_orientation_ne_rend_jamais_concordante(self, plan):
        plan.get(Parcelle, 4).ensoleillement = None
        plan.get(Parcelle, 4).exposition = "plein soleil"  # texte libre, ancien usage
        plan.commit()
        par_nom, _ = _suggestions(plan)
        assert par_nom["D"]["exposition"]["comparaison"] == ech.EXPO_NON_COMPARABLE

    def test_us239_ca7bis_a_rang_egal_le_plus_de_rangs_libres(self, plan):
        plan.get(Parcelle, 2).ensoleillement = "plein soleil"  # B rejoint C
        plan.get(Parcelle, 2).nb_rangs = 3
        plan.commit()
        _, ordre = _suggestions(plan)
        assert ordre[:2] == ["B", "C"]

    def test_us239_culture_sans_exposition_non_comparable(self):
        r = ech.comparer_exposition("plein soleil", None)
        assert r["comparaison"] == ech.EXPO_NON_COMPARABLE
        assert r["libelle"] == "exposition de la culture non renseignée"
