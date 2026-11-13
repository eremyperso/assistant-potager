"""
tests/test_us324_noter_gaston.py — Noter ce que je vois avec Gaston, d'un seul bouton [US-324]
==============================================================================================
Le panneau (pastilles, micro, « Retour au plan ») se teste côté frontend
(`frontend/src/lib/noter.test.js`) et à l'écran. Ce fichier tient le serveur :

- CA2 / CA4 : les raccourcis donnent leur geste sans modèle et passent par le flux de
  propositions existant — rien n'est écrit avant « Confirmer » ;
- CA3 : une phrase qui annonce une étape donne une carte à DEUX lignes, la note et l'étape ;
- CA5 : après confirmation, ce qui a changé sur le plan ;
- CA8 : « En fleur », « Culture terminée », « Rang libéré » compris du bot ;
- CA9 : un membre en lecture seule ne note rien.

Aucun appel de modèle : le parseur est simulé, l'agent éteint (`AGENT_MODE=off`).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import normalisation_gestes as svc_normalisation
from app.services.compagnon import contexte_ecran as svc_ecran
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import noter as svc_noter
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.context import TenantContext, default_context
from app.services.permissions import PermissionInsuffisanteError
from database.models import CultureConfig, EchangeConversation, Evenement, Parcelle
from utils.actions import normalize_action

CTX = default_context()
LECTEUR = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id, role="viewer")
LEVEE_GHERKIN = "les fèves ont levé côté allée, rien encore au fond du rang"


@pytest.fixture(autouse=True)
def sans_modele(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "off")
    monkeypatch.setattr(svc_orchestrateur.svc_interpreteur, "interpreter", lambda *a, **k: None)
    # Le parseur ne lit rien : ce que ce fichier vérifie se lit SANS lui.
    monkeypatch.setattr(svc_normalisation, "parser_saisie",
                        lambda texte, ctx=None: type("R", (), {"reconnu": False, "items": None})())
    monkeypatch.setattr(svc_normalisation, "parse_commande", lambda texte, ctx=None: [])


def _jour(jours: int) -> datetime:
    return datetime.combine(date.today() - timedelta(days=jours), datetime.min.time())


@pytest.fixture
def potager(memoire_compagnon):
    """Planche centrale : des fèves semées en pleine terre et des choux kale plantés."""
    with memoire_compagnon() as db:
        centrale = Parcelle(nom="Planche centrale", nom_normalise="planchecentrale", ordre=1, actif=True,
                            potager_id=CTX.potager_id, nb_rangs=5)
        db.add_all([centrale,
                    CultureConfig(nom="fève", type_organe_recolte="reproducteur"),
                    CultureConfig(nom="chou kale", type_organe_recolte="reproducteur")])
        db.flush()
        db.add_all([
            Evenement(potager_id=CTX.potager_id, type_action="semis", culture="fève", quantite=40,
                      unite="graines", parcelle_id=centrale.id, date=_jour(20)),
            Evenement(potager_id=CTX.potager_id, type_action="plantation", culture="chou kale", quantite=6,
                      unite="plants", parcelle_id=centrale.id, date=_jour(60)),
        ])
        db.commit()
        pid = centrale.id
    yield memoire_compagnon, pid
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(CultureConfig).delete()
        db.query(EchangeConversation).delete()
        db.commit()


def _ecran(culture: str | None, pid: int = 1) -> svc_ecran.ContexteEcran:
    return svc_ecran.ContexteEcran(parcelle_id=pid, parcelle="Planche centrale", culture=culture)


def _evenements(fabrique, action: str) -> list[Evenement]:
    with fabrique() as db:
        return db.query(Evenement).filter(Evenement.type_action == action).all()


# ═════════════════════════════════════════════════════════════════════════════
# CA2 / CA4 — les raccourcis, sans modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestRaccourcis:

    @pytest.mark.parametrize("code, action", [
        ("etape_levee", "levee"), ("culture_terminee", "fin_culture"), ("rang_libere", "fin_culture"),
        ("arrose", "arrosage"), ("paille", "paillage"), ("desherbe", "desherbage"),
    ])
    def test_chaque_raccourci_donne_son_geste(self, code, action):
        lecture = svc_noter.items_du_raccourci(code, _ecran("fève"), "")
        assert lecture.precision is None
        item = lecture.items[0]
        assert (item["action"], item["culture"], item["parcelle"]) == (action, "fève", "Planche centrale")
        assert item["date"] == date.today().isoformat()

    def test_un_raccourci_de_culture_sans_culture_demande_le_suivi(self):
        assert svc_noter.items_du_raccourci("etape_levee", _ecran(None), "").precision == svc_noter.TEXTE_SANS_CULTURE
        assert svc_noter.items_du_raccourci("recolte", None, "800 g").precision == svc_noter.TEXTE_SANS_CULTURE

    def test_un_geste_de_parcelle_sur_tout_le_potager_demande_la_parcelle(self):
        assert svc_noter.items_du_raccourci("arrose", None, "Arrosé").precision == svc_noter.TEXTE_PARCELLE

    def test_un_geste_de_parcelle_sur_une_parcelle(self):
        item = svc_noter.items_du_raccourci("paille", _ecran(None), "Paillé").items[0]
        assert (item["action"], item["parcelle"], item["culture"]) == ("paillage", "Planche centrale", None)

    def test_code_inconnu(self):
        with pytest.raises(svc_noter.RaccourciInconnuError):
            svc_noter.items_du_raccourci("semer", _ecran("fève"), "")

    @pytest.mark.parametrize("phrase, attendu", [
        ("800 grammes", (0.8, "kg")), ("800 g", (0.8, "kg")), ("2,5 kg", (2.5, "kg")),
        ("un kilo", (1, "kg")), ("12", (12, "pieces")), ("3 bottes", (3, "bottes")),
        ("rien du tout", None), ("sur 3 rangs", None),
    ])
    def test_ca4_la_quantite_d_une_recolte(self, phrase, attendu):
        assert svc_noter.lire_quantite(phrase) == attendu

    def test_recolte_sans_quantite_la_demande(self):
        assert svc_noter.items_du_raccourci("recolte", _ecran("chou kale"), "Récolte").precision == svc_noter.TEXTE_QUANTITE


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — une phrase qui annonce une étape : la note ET l'étape
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3NoteEtEtape:

    @pytest.mark.parametrize("phrase, etape", [
        (LEVEE_GHERKIN, "levee"), ("ça a levé", "levee"), ("la levée est là", "levee"),
        ("culture terminée, tout est arraché", "fin_culture"), ("rang libéré", "fin_culture"),
        ("arrachées par le vent", None), ("feuilles un peu jaunies", None),
    ])
    def test_etape_annoncee(self, phrase, etape):
        assert svc_noter.etape_annoncee(phrase) == etape

    def test_deux_lignes_sur_la_culture_sous_les_yeux(self):
        note, etape = svc_noter.note_et_etape(LEVEE_GHERKIN, _ecran("fève"))
        assert (note["action"], note["commentaire"]) == ("observation", LEVEE_GHERKIN)
        assert (etape["action"], etape["culture"], etape["date"]) == ("levee", "fève", date.today().isoformat())

    def test_une_autre_culture_citee_l_emporte(self):
        assert svc_noter.note_et_etape("les tomates ont levé", _ecran("fève")) is None

    def test_sans_culture_sous_les_yeux_rien(self):
        assert svc_noter.note_et_etape(LEVEE_GHERKIN, _ecran(None)) is None
        assert svc_noter.note_et_etape(LEVEE_GHERKIN, None) is None

    def test_gherkin_1_une_carte_a_deux_lignes_rien_avant_confirmer(self, potager):
        fabrique, pid = potager
        reponse = svc_echange.repondre(CTX, LEVEE_GHERKIN, contexte={"parcelle_id": pid, "culture": "fève"})
        assert reponse.vers == svc_echange.VERS_GESTE, reponse.texte
        actions = [i["action"] for i in reponse.propositions[0]["items"]]
        assert actions == ["observation", "levee"]
        assert _evenements(fabrique, "levee") == [] and _evenements(fabrique, "observation") == []

    def test_gherkin_1_confirmer_valide_la_levee_et_le_dit(self, potager):
        fabrique, pid = potager
        reponse = svc_echange.repondre(CTX, LEVEE_GHERKIN, contexte={"parcelle_id": pid, "culture": "fève"})
        issue = svc_echange.confirmer(CTX, reponse.propositions[0]["id"])
        assert issue.erreur is None, issue.texte
        assert len(_evenements(fabrique, "levee")) == 1
        assert _evenements(fabrique, "observation")[0].culture == "fève"
        # CA5 : ce qui change sur le plan
        assert issue.annonce == "Fève passe à « Levé » sur le plan."
        assert issue.en_donnees()["annonce"] == issue.annonce


# ═════════════════════════════════════════════════════════════════════════════
# CA4 / CA5 — un raccourci passe par le flux de propositions existant
# ═════════════════════════════════════════════════════════════════════════════
class TestFluxDePropositions:

    def test_gherkin_2_recolte_sur_un_reproducteur(self, potager):
        fabrique, pid = potager
        reponse = svc_echange.repondre(CTX, "800 grammes", contexte={"parcelle_id": pid, "culture": "chou kale"},
                                       raccourci="recolte")
        assert reponse.vers == svc_echange.VERS_GESTE, reponse.texte
        item = reponse.propositions[0]["items"][0]
        assert (item["action"], item["quantite"], item["unite"], item["culture"]) == ("recolte", 0.8, "kg", "chou kale")
        assert _evenements(fabrique, "recolte") == []
        issue = svc_echange.confirmer(CTX, reponse.propositions[0]["id"])
        assert issue.erreur is None, issue.texte
        assert _evenements(fabrique, "recolte")[0].quantite == pytest.approx(0.8)
        assert issue.annonce == "Récolte notée : Chou kale reste « En récolte »."

    def test_culture_terminee_libere_le_rang(self, potager):
        fabrique, pid = potager
        reponse = svc_echange.repondre(CTX, "Culture terminée", contexte={"parcelle_id": pid, "culture": "chou kale"},
                                       raccourci="culture_terminee")
        issue = svc_echange.confirmer(CTX, reponse.propositions[0]["id"])
        assert issue.erreur is None, issue.texte
        assert _evenements(fabrique, "fin_culture")
        assert issue.annonce == "Chou kale est terminée : son rang est libre sur le plan."

    def test_le_raccourci_garde_le_contexte_avec_l_echange(self, potager):
        fabrique, pid = potager
        svc_echange.repondre(CTX, "Levée vue", contexte={"parcelle_id": pid, "culture": "fève"}, raccourci="etape_levee")
        with fabrique() as db:
            echange = db.query(EchangeConversation).order_by(EchangeConversation.id.desc()).first()
        assert echange.contexte["culture"] == "fève"

    def test_raccourci_inconnu_refuse_avant_tout(self, potager):
        _, pid = potager
        with pytest.raises(svc_noter.RaccourciInconnuError):
            svc_echange.repondre(CTX, "x", contexte={"parcelle_id": pid}, raccourci="semer")

    def test_ca9_lecture_seule_rien_n_est_propose(self, potager):
        _, pid = potager
        with pytest.raises(PermissionInsuffisanteError):
            svc_echange.repondre(LECTEUR, "Levée vue", contexte={"parcelle_id": pid, "culture": "fève"},
                                 raccourci="etape_levee")

    def test_annonce_sans_etape_rien(self):
        assert svc_noter.annonce_apres_confirmation([{"action": "arrosage", "culture": None}]) is None
        assert svc_noter.annonce_apres_confirmation([]) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le bot comprend les mêmes gestes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Bot:

    @pytest.mark.parametrize("tournure, action", [
        ("rang libéré", "fin_culture"), ("libéré le rang", "fin_culture"), ("culture terminée", "fin_culture"),
        ("les fèves sont en fleur", "observation"), ("floraison des tomates", "observation"),
        ("récolté des choux-fleurs", "recolte"), ("planté des choux-fleurs", "plantation"),
    ])
    def test_tournures(self, tournure, action):
        assert normalize_action(tournure) == action


# ═════════════════════════════════════════════════════════════════════════════
# La route
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def client(potager):
    from app.api.main import app, get_current_user_ctx

    app.dependency_overrides[get_current_user_ctx] = default_context
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


class TestRoute:

    def test_post_raccourci_puis_confirmer_rend_l_annonce(self, client, potager):
        _, pid = potager
        r = client.post("/compagnon/messages", json={
            "texte": "Levée vue", "raccourci": "etape_levee", "contexte": {"parcelle_id": pid, "culture": "fève"}})
        assert r.status_code == 200, r.text
        carte = r.json()["propositions"][0]
        c = client.post(f"/compagnon/propositions/{carte['id']}/confirmer")
        assert c.status_code == 200, c.text
        assert c.json()["annonce"] == "Fève passe à « Levé » sur le plan."

    def test_raccourci_inconnu_422(self, client, potager):
        _, pid = potager
        r = client.post("/compagnon/messages", json={"texte": "x", "raccourci": "semer", "contexte": {"parcelle_id": pid}})
        assert r.status_code == 422
