"""
tests/test_us323_contexte_ecran.py — Transmettre à Gaston ce que le jardinier a sous les yeux [US-323]
=====================================================================================================
Le panneau se teste côté frontend (`frontend/src/lib/contexteCompagnon.test.js`) et à l'écran.
Ce fichier tient le serveur :

- C4 / CA2 : le contexte part en identifiants, vérifiés contre le potager actif (404 sans fuite) ;
- C5 / CA3 / CA4 : une précision par défaut — le constat devient une note de la culture, une
  phrase qui nomme une autre parcelle l'emporte ;
- CA5 : sans contexte, rien ne change (les tests d'US-270 et suivantes restent verts) ;
- CA6 : le contexte est gardé avec l'échange ;
- l'agent le lit dans son contexte court (C5).

Aucun appel de modèle : le parseur est simulé, l'agent éteint (`AGENT_MODE=off`).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import normalisation_gestes as svc_normalisation
from app.services.agent import contexte_court as svc_contexte_court
from app.services.compagnon import contexte_ecran as svc_ecran
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.context import TenantContext, default_context
from database.models import CultureConfig, EchangeConversation, Evenement, Parcelle, Proposition
from llm import routeur

RACINE = Path(__file__).resolve().parents[1]
CTX = default_context()
AUTRE_POTAGER = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id + 1, role="owner")

CONSTAT = "feuilles du bas un peu jaunies"
ARROSAGE_SERRE = "j'ai arrosé la serre"
ITEM_ARROSAGE_SERRE = {
    "action": "arrosage", "culture": None, "variete": None, "quantite": None, "unite": None,
    "parcelle": "Serre", "rang": None, "date": None, "commentaire": None,
    "origine_parsing": "deterministe",
}
ARROSE = "arrosé"
ITEM_ARROSE = {**ITEM_ARROSAGE_SERRE, "parcelle": None}


@pytest.fixture(autouse=True)
def sans_modele(monkeypatch):
    """L'agent est éteint : la phrase suit les règles, puis l'orientation."""
    monkeypatch.setattr(config, "AGENT_MODE", "off")
    # Aucune des phrases n'est une commande : l'interpréteur (et son repli modèle) n'y lit rien.
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)


@pytest.fixture
def potager(memoire_compagnon):
    """Planche centrale (5 rangs) où pousse un chou de Bruxelles Groninger, et une serre."""
    with memoire_compagnon() as db:
        centrale = Parcelle(nom="Planche centrale", nom_normalise="planchecentrale", ordre=1, actif=True,
                            potager_id=CTX.potager_id, nb_rangs=5)
        serre = Parcelle(nom="Serre", nom_normalise="serre", ordre=2, actif=True, potager_id=CTX.potager_id)
        ailleurs = Parcelle(nom="Nord", nom_normalise="nord", ordre=1, actif=True,
                            potager_id=AUTRE_POTAGER.potager_id)
        db.add_all([centrale, serre, ailleurs,
                    CultureConfig(nom="chou de bruxelles", type_organe_recolte="végétatif")])
        db.flush()
        db.add(Evenement(
            potager_id=CTX.potager_id, type_action="plantation", culture="chou de Bruxelles",
            variete="Groninger", quantite=12, unite="plants", parcelle_id=centrale.id,
            date=datetime.combine(date.today() - timedelta(days=40), datetime.min.time()),
        ))
        db.commit()
        ids = {"centrale": centrale.id, "serre": serre.id, "ailleurs": ailleurs.id}
    yield memoire_compagnon, ids
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(CultureConfig).delete()
        db.query(EchangeConversation).delete()
        db.commit()


def _contexte_chou(ids, rang=3) -> dict:
    return {"parcelle_id": ids["centrale"], "culture": "chou de Bruxelles", "variete": "Groninger", "rang": rang}


@pytest.fixture
def parseur(monkeypatch):
    """Le parseur déterministe simulé ; le repli modèle ne lit rien d'un constat."""
    connues = {ARROSAGE_SERRE: [ITEM_ARROSAGE_SERRE], ARROSE: [ITEM_ARROSE]}

    def parseur_simule(texte, ctx=None):
        items = connues.get(texte)
        return type("R", (), {"reconnu": items is not None,
                              "items": [dict(i) for i in items] if items else None})()

    monkeypatch.setattr(svc_normalisation, "parser_saisie", parseur_simule)
    monkeypatch.setattr(svc_normalisation, "parse_commande", lambda texte, ctx=None: [])


def _sans_classification():
    """Le routeur ne doit pas être appelé : la classification par le modèle est évitée."""
    return patch("llm.routeur.classer_demande", side_effect=AssertionError("classification appelée"))


# ═════════════════════════════════════════════════════════════════════════════
# C4 / CA2 — des identifiants vérifiés contre le potager actif
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Resolution:

    def test_culture_en_place_noms_relus_en_base(self, potager):
        fabrique, ids = potager
        with fabrique() as db:
            ecran = svc_ecran.resoudre(db, CTX, ids["centrale"], "CHOU DE BRUXELLES", "groninger", 3)
        assert ecran.niveau == svc_ecran.NIVEAU_CULTURE
        assert (ecran.parcelle, ecran.culture, ecran.variete, ecran.rang) == (
            "Planche centrale", "chou de Bruxelles", "Groninger", 3)
        assert ecran.libelle() == "chou de Bruxelles Groninger · Planche centrale, rang 3"

    def test_parcelle_seule(self, potager):
        fabrique, ids = potager
        with fabrique() as db:
            ecran = svc_ecran.resoudre(db, CTX, ids["serre"])
        assert ecran.niveau == svc_ecran.NIVEAU_PARCELLE and ecran.culture is None

    def test_sans_identifiant_tout_le_potager(self, potager):
        fabrique, _ = potager
        with fabrique() as db:
            assert svc_ecran.resoudre(db, CTX) is None

    @pytest.mark.parametrize("champs", [
        {"parcelle_id": "ailleurs"},                                  # parcelle d'un autre potager
        {"parcelle_id": 999_999},                                     # parcelle inexistante
        {"parcelle_id": "centrale", "culture": "tomate"},             # culture pas en place
        {"parcelle_id": "centrale", "culture": "chou de Bruxelles"},  # variété différente
        {"parcelle_id": "centrale", "rang": 100},                     # au-delà de 99
        {"parcelle_id": "centrale", "rang": 0},
        {"culture": "chou de Bruxelles"},                             # culture sans parcelle
        {"rang": 2},
    ])
    def test_identifiant_etranger_refuse(self, potager, champs):
        fabrique, ids = potager
        champs = {k: ids.get(v, v) if k == "parcelle_id" else v for k, v in champs.items()}
        with fabrique() as db, pytest.raises(svc_ecran.ContexteIntrouvableError):
            svc_ecran.resoudre(db, CTX, **champs)

    def test_refus_avant_tout_appel_de_modele(self, potager, parseur):
        _, ids = potager
        with _sans_classification(), pytest.raises(svc_ecran.ContexteIntrouvableError):
            svc_echange.repondre(CTX, CONSTAT, contexte={"parcelle_id": ids["ailleurs"]})


# ═════════════════════════════════════════════════════════════════════════════
# C5 / CA3 / CA4 — la précision par défaut
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3CA4Precision:

    def test_ca3_gherkin_un_constat_devient_une_note_sur_le_chou(self, potager, parseur):
        _, ids = potager
        with _sans_classification():
            reponse = svc_echange.repondre(CTX, CONSTAT, contexte=_contexte_chou(ids))
        assert reponse.vers == svc_echange.VERS_GESTE, reponse.texte
        item = reponse.propositions[0]["items"][0]
        assert item["action"] == "observation"
        assert (item["culture"], item["variete"], item["parcelle"]) == ("chou de Bruxelles", "Groninger",
                                                                        "Planche centrale")
        assert item["commentaire"] == CONSTAT and item["date"] == date.today().isoformat()

    def test_ca3_rien_n_est_ecrit_avant_confirmer_puis_la_note_est_sur_la_culture(self, potager, parseur):
        fabrique, ids = potager
        with _sans_classification():
            reponse = svc_echange.repondre(CTX, CONSTAT, contexte=_contexte_chou(ids))
        with fabrique() as db:
            assert db.query(Evenement).filter(Evenement.type_action == "observation").count() == 0
        svc_echange.confirmer(CTX, reponse.propositions[0]["id"])
        with fabrique() as db:
            note = db.query(Evenement).filter(Evenement.type_action == "observation").one()
            assert note.parcelle_id == ids["centrale"]
            assert note.culture.lower() == "chou de bruxelles"

    def test_ca4_une_autre_parcelle_l_emporte(self, potager, parseur):
        _, ids = potager
        with _sans_classification():
            reponse = svc_echange.repondre(CTX, ARROSAGE_SERRE, contexte=_contexte_chou(ids))
        item = reponse.propositions[0]["items"][0]
        assert item["parcelle"] == "Serre"
        assert not item.get("culture")

    def test_un_geste_sans_lieu_va_a_la_culture_sous_les_yeux(self, potager, parseur):
        _, ids = potager
        with _sans_classification():
            reponse = svc_echange.repondre(CTX, ARROSE, contexte=_contexte_chou(ids))
        item = reponse.propositions[0]["items"][0]
        assert (item["action"], item["parcelle"], item["culture"]) == ("arrosage", "Planche centrale",
                                                                       "chou de Bruxelles")

    def test_une_autre_culture_l_emporte(self):
        ecran = svc_ecran.ContexteEcran(parcelle_id=1, parcelle="Planche centrale", culture="chou de Bruxelles")
        items = [{"action": "recolte", "culture": "tomate", "parcelle": None, "quantite": 2}]
        assert svc_ecran.appliquer(items, ecran, "récolté 2 kg de tomates") == items

    def test_parcelle_seule_complete_le_lieu_sans_inventer_de_culture(self):
        ecran = svc_ecran.ContexteEcran(parcelle_id=1, parcelle="Serre")
        items = svc_ecran.appliquer([dict(ITEM_ARROSE)], ecran, ARROSE)
        assert items[0]["parcelle"] == "Serre" and items[0]["culture"] is None
        # Un constat sans culture sous les yeux ne devient pas une note : rien n'est inventé.
        assert svc_ecran.appliquer([], ecran, CONSTAT) == []

    def test_une_question_reste_une_question(self, potager):
        _, ids = potager
        resultat = type("R", (), {"texte": "réponse", "routage_log_id": None, "etage_resolveur": None})()
        decision = routeur.DecisionRoutage(nature=routeur.NATURE_QUESTION_SAVOIR, origine="regle", confiance=1.0)
        with patch("llm.routeur.classer_demande", return_value=decision), \
                patch.object(svc_orchestrateur, "repondre_a_une_question", return_value=resultat):
            reponse = svc_echange.repondre(CTX, "quand récolter les choux ?", contexte=_contexte_chou(ids))
        assert reponse.vers == svc_echange.VERS_QUESTION

    def test_orienter_sans_contexte_classe_comme_avant(self):
        decision = routeur.DecisionRoutage(nature=routeur.NATURE_QUESTION_SAVOIR, origine="regle", confiance=1.0)
        with patch("llm.routeur.classer_demande", return_value=decision) as classer:
            suite = svc_orchestrateur.orienter(None, CONSTAT, CTX)
        assert suite.vers == svc_orchestrateur.SUITE_QUESTION and classer.called


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — sans contexte, rien ne change
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5SansContexte:

    def test_appliquer_sans_contexte_ne_touche_rien(self):
        items = [dict(ITEM_ARROSE)]
        assert svc_ecran.appliquer(items, None, ARROSE) is items

    def test_un_constat_sans_contexte_n_est_pas_note(self, potager, parseur):
        with patch("llm.routeur.classer_demande", return_value=routeur.DecisionRoutage(
                nature=routeur.NATURE_ACTION, origine="regle", confiance=1.0)):
            reponse = svc_echange.repondre(CTX, CONSTAT)
        assert reponse.vers == svc_echange.VERS_REPONSE and not reponse.propositions


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — le contexte est gardé avec l'échange
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Journal:

    def test_l_echange_garde_le_contexte(self, potager, parseur):
        fabrique, ids = potager
        with _sans_classification():
            svc_echange.repondre(CTX, CONSTAT, contexte=_contexte_chou(ids))
        with fabrique() as db:
            echanges = db.query(EchangeConversation).all()
        assert echanges and all(e.contexte for e in echanges)
        assert echanges[-1].contexte == {
            "niveau": "culture", "parcelle_id": ids["centrale"], "parcelle": "Planche centrale",
            "rang": 3, "culture": "chou de Bruxelles", "variete": "Groninger",
        }

    def test_sans_contexte_rien_n_est_garde(self, potager, parseur):
        fabrique, _ = potager
        with patch("llm.routeur.classer_demande", return_value=routeur.DecisionRoutage(
                nature=routeur.NATURE_ACTION, origine="regle", confiance=1.0)):
            svc_echange.repondre(CTX, ARROSAGE_SERRE)
        with fabrique() as db:
            assert all(e.contexte is None for e in db.query(EchangeConversation).all())

    def test_migration_v77_et_son_rollback(self):
        migration = (RACINE / "migrations" / "migration_v77.sql").read_text(encoding="utf-8")
        rollback = (RACINE / "migrations" / "rollback_v77.sql").read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS contexte JSONB NULL" in migration
        assert "DROP COLUMN IF EXISTS contexte" in rollback


# ═════════════════════════════════════════════════════════════════════════════
# C5 — l'agent lit le contexte d'écran
# ═════════════════════════════════════════════════════════════════════════════
class TestAgent:

    def test_sous_les_yeux_suffit_a_faire_un_contexte(self):
        contexte = svc_contexte_court.construire(CTX, sous_les_yeux={"parcelle": "Serre"})
        assert contexte is not None
        assert contexte.donnees()["sous_les_yeux"] == {"parcelle": "Serre"}
        assert "sous_les_yeux" in contexte.prompt() and "AUTRE culture" in contexte.prompt()

    def test_sans_ecran_le_prompt_ne_change_pas(self):
        contexte = svc_contexte_court.construire(CTX, spontane={"texte": "Il va geler"})
        assert "sous_les_yeux" not in contexte.prompt()

    def test_le_canal_pwa_passe_le_contexte_a_l_agent(self, potager, parseur, monkeypatch):
        _, ids = potager
        vus = []
        reel = svc_orchestrateur.contexte_court_du_jardinier

        def espion(tenant, spontane=None, sous_les_yeux=None):
            vus.append(sous_les_yeux)
            return reel(tenant, spontane=spontane, sous_les_yeux=sous_les_yeux)

        monkeypatch.setattr(svc_orchestrateur, "contexte_court_du_jardinier", espion)
        with _sans_classification():
            svc_echange.repondre(CTX, CONSTAT, contexte=_contexte_chou(ids))
        assert vus and vus[0] == {"parcelle": "Planche centrale", "rang": 3,
                                  "culture": "chou de Bruxelles", "variete": "Groninger"}


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — la route
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def client(potager, parseur):
    from app.api.main import app, get_current_user_ctx

    app.dependency_overrides[get_current_user_ctx] = default_context
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


class TestRoute:

    def test_post_avec_contexte_rend_la_note(self, client, potager):
        _, ids = potager
        with _sans_classification():
            r = client.post("/compagnon/messages", json={"texte": CONSTAT, "contexte": _contexte_chou(ids)})
        assert r.status_code == 200, r.text
        assert r.json()["propositions"][0]["items"][0]["action"] == "observation"

    def test_identifiant_etranger_404_sans_fuite(self, client, potager):
        _, ids = potager
        reponses = [
            client.post("/compagnon/messages", json={"texte": CONSTAT, "contexte": {"parcelle_id": ids["ailleurs"]}}),
            client.post("/compagnon/messages", json={"texte": CONSTAT, "contexte": {"parcelle_id": 999_999}}),
            client.post("/compagnon/messages", json={"texte": CONSTAT, "contexte": {
                "parcelle_id": ids["centrale"], "culture": "tomate"}}),
        ]
        assert {r.status_code for r in reponses} == {404}
        assert {r.json()["detail"] for r in reponses} == {"Contexte introuvable"}

    def test_sans_contexte_la_route_est_inchangee(self, client):
        with patch("llm.routeur.classer_demande", return_value=routeur.DecisionRoutage(
                nature=routeur.NATURE_ACTION, origine="regle", confiance=1.0)):
            r = client.post("/compagnon/messages", json={"texte": ARROSAGE_SERRE})
        assert r.status_code == 200
        assert r.json()["propositions"][0]["items"][0]["parcelle"] == "Serre"
