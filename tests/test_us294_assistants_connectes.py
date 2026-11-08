"""
tests/test_us294_assistants_connectes.py — Voir et révoquer les assistants IA connectés [US-294]
================================================================================================
Le volet serveur de l'écran « Assistants connectés » : liste (CA1), révocation (CA2), activité (CA3),
jeton personnel (CA4), prévenir les membres d'un potager partagé (CA5), interdire les assistants
externes pour un potager (CA6). Le volet visuel (CA7, CA type) est dans `frontend/src/lib/assistants.test.js`.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services import telegram_notify
from database.models import (
    Evenement, McpAppel, McpAutorisation, Parcelle, Potager, PotagerMembre, User,
)
from tests.test_us290_serveur_mcp import (  # noqa: F401 — fixtures et aides partagées
    _appeler, _connecter, _pwa, _rpc, client, fabrique, jardin,
)
from tests.test_us292_geste_assistant_ia import _donnees, _refus, sessions  # noqa: F401

CHAT_PAUL = 7001


@pytest.fixture
def telegram(monkeypatch):
    faux = SimpleNamespace(envoyes=[])
    monkeypatch.setattr(telegram_notify, "envoyer",
                        lambda chat_id, texte, boutons=None, parse_mode=None: faux.envoyes.append((chat_id, texte)) or 1)
    monkeypatch.setattr(telegram_notify, "editer_message", lambda *a, **k: True)
    return faux


@pytest.fixture
def partage(fabrique, jardin):
    """« Les Mésanges » est partagé : Camille (propriétaire, Telegram lié) et Paul (éditeur)."""
    with fabrique() as db:
        paul = User(email="paul@test.fr", nom="Paul", email_verifie=True)
        db.add(paul)
        db.flush()
        db.add(PotagerMembre(user_id=paul.id, potager_id=jardin["mesanges"], role="editor"))
        db.get(User, jardin["user_id"]).telegram_chat_id = CHAT_PAUL
        db.commit()
        return {**jardin, "paul": paul.id, "paul_jardin": {**jardin, "user_id": paul.id}}


def _connexions(client, user_id):
    reponse = client.get("/mcp/connexions", headers=_pwa(user_id))
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["connexions"]


# ── CA1 : la liste ───────────────────────────────────────────────────────────
class TestCA1Liste:
    def test_us294_chaque_connexion_est_decrite(self, client, jardin, sessions):
        _connecter(client, jardin, ecriture=True, potagers=[jardin["mesanges"], jardin["verger"]])
        (ligne,) = _connexions(client, jardin["user_id"])
        assert ligne["client"] == "Claude" and ligne["type"] == "oauth"
        assert ligne["portee"] == "ecriture" and ligne["portee_libelle"] == "lecture + écriture"
        assert ligne["cree_le"] and ligne["dernier_appel_le"] is None and ligne["statut"] == "active"
        assert [p["nom"] for p in ligne["potagers"]] == ["Les Mésanges", "Le Verger"]

    def test_us294_dernier_appel_apres_un_appel(self, client, jardin, sessions):
        jeton = _connecter(client, jardin)["access_token"]
        _appeler(client, jeton, "lister_potagers")
        assert _connexions(client, jardin["user_id"])[0]["dernier_appel_le"]

    def test_us294_on_ne_voit_que_ses_connexions(self, client, partage, sessions):
        _connecter(client, partage["paul_jardin"])
        assert _connexions(client, partage["user_id"]) == []


# ── CA2 : la révocation ──────────────────────────────────────────────────────
class TestCA2Revocation:
    def test_us294_revoquer_coupe_tout_de_suite(self, client, jardin, sessions):
        jeton = _connecter(client, jardin)["access_token"]
        identifiant = _connexions(client, jardin["user_id"])[0]["id"]
        assert client.delete(f"/mcp/connexions/{identifiant}", headers=_pwa(jardin["user_id"])).json() == {"revoque": True}
        assert _rpc(client, jeton, "tools/list").status_code == 401
        ligne = _connexions(client, jardin["user_id"])[0]
        assert ligne["statut"] == "revoquee" and ligne["revoque_le"]


# ── CA3 : l'activité ─────────────────────────────────────────────────────────
class TestCA3Activite:
    def _activite(self, client, user_id, identifiant):
        reponse = client.get(f"/mcp/connexions/{identifiant}/activite", headers=_pwa(user_id))
        assert reponse.status_code == 200, reponse.text
        return reponse.json()["appels"]

    def test_us294_date_outil_potager_resultat(self, client, jardin, sessions):
        jeton = _connecter(client, jardin)["access_token"]
        _appeler(client, jeton, "lister_potagers")
        _appeler(client, jeton, "proposer_geste", {"type": "semis", "culture": "fève"})  # refusé : portée lecture
        identifiant = _connexions(client, jardin["user_id"])[0]["id"]
        appels = self._activite(client, jardin["user_id"], identifiant)
        assert [a["outil"] for a in appels] == ["proposer_geste", "lister_potagers"]  # le plus récent d'abord
        assert appels[1]["resultat"] == "ok" and appels[0]["resultat"] == "refus"
        assert appels[0]["date"] and appels[0]["geste"] is None

    def test_us294_pas_plus_de_100_appels(self, client, jardin, fabrique, sessions):
        _connecter(client, jardin)
        identifiant = _connexions(client, jardin["user_id"])[0]["id"]
        with fabrique() as db:
            db.add_all([McpAppel(horodatage=datetime.utcnow() - timedelta(minutes=i), user_id=jardin["user_id"],
                                 autorisation_id=identifiant, client="Claude", outil="lister_potagers",
                                 potager_id=jardin["mesanges"], resultat="ok") for i in range(130)])
            db.commit()
        assert len(self._activite(client, jardin["user_id"], identifiant)) == 100

    def test_us294_ecriture_confirmee_renvoie_au_geste(self, client, jardin, fabrique, sessions, telegram):
        with fabrique() as db:
            db.add(Parcelle(nom="Sud", nom_normalise="sud", potager_id=jardin["mesanges"], actif=True))
            db.commit()
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        ident = _donnees(_appeler(client, jeton, "proposer_geste", {
            "type": "plantation", "culture": "tomate", "quantite": 4, "unite": "plants", "parcelle": "Sud",
        }))["proposition"]
        ecrit = _donnees(_appeler(client, jeton, "confirmer_proposition", {"proposition": ident}))
        assert ecrit["enregistres"]
        identifiant = _connexions(client, jardin["user_id"])[0]["id"]
        confirmation = next(a for a in self._activite(client, jardin["user_id"], identifiant)
                            if a["outil"] == "confirmer_proposition")
        assert confirmation["geste"]["id"] == ecrit["enregistres"][0]["event_id"]
        assert len(confirmation["geste"]["date"]) == 10  # AAAA-MM-JJ : le lien vers le Journal filtre sur ce jour
        with fabrique() as db:
            assert db.get(Evenement, confirmation["geste"]["id"]) is not None

    def test_us294_l_activite_d_un_autre_est_introuvable(self, client, partage, sessions):
        _connecter(client, partage["paul_jardin"])
        identifiant = _connexions(client, partage["paul"])[0]["id"]
        assert client.get(f"/mcp/connexions/{identifiant}/activite", headers=_pwa(partage["user_id"])).status_code == 404

    def test_us294_aucun_contenu_dans_l_activite(self, client, jardin, sessions):
        jeton = _connecter(client, jardin)["access_token"]
        _appeler(client, jeton, "chercher_connaissance", {"question": "secret de mon potager"})
        identifiant = _connexions(client, jardin["user_id"])[0]["id"]
        assert "secret" not in str(self._activite(client, jardin["user_id"], identifiant))


# ── CA4 : jeton personnel ────────────────────────────────────────────────────
class TestCA4JetonPersonnel:
    def test_us294_jeton_affiche_une_fois_avec_portee_et_expiration(self, client, jardin, sessions, telegram):
        reponse = client.post("/mcp/jetons-personnels", headers=_pwa(jardin["user_id"]), json={
            "libelle": "MCP Inspector", "ecriture": False, "potager_ids": [jardin["mesanges"]], "duree_jours": 30})
        assert reponse.status_code == 201
        corps = reponse.json()
        assert len(corps["jeton"]) > 20 and corps["connexion"]["expire_le"]
        (ligne,) = _connexions(client, jardin["user_id"])
        assert ligne["type"] == "personnel" and ligne["expire_le"] and ligne["portee"] == "lecture"
        assert corps["jeton"] not in str(ligne)  # jamais relu ensuite


# ── CA5 : potager partagé ────────────────────────────────────────────────────
class TestCA5PotagerPartage:
    def test_us294_les_autres_membres_sont_prevenus(self, client, partage, sessions, telegram):
        _connecter(client, partage["paul_jardin"], potagers=[partage["mesanges"]])
        assert len(telegram.envoyes) == 1
        chat, texte = telegram.envoyes[0]
        assert chat == CHAT_PAUL
        assert "Paul a connecté Claude à ce potager, en lecture" in texte and "Les Mésanges" in texte

    def test_us294_la_portee_ecriture_est_dite(self, client, partage, sessions, telegram):
        _connecter(client, partage["paul_jardin"], ecriture=True)
        assert "en lecture et écriture" in telegram.envoyes[0][1]

    def test_us294_seule_la_premiere_connexion_est_annoncee(self, client, partage, sessions, telegram):
        enregistrement = None
        from tests.test_us290_serveur_mcp import _enregistrer
        enregistrement = _enregistrer(client)
        _connecter(client, partage["paul_jardin"], enregistrement=enregistrement)
        _connecter(client, partage["paul_jardin"], enregistrement=enregistrement)
        assert len(telegram.envoyes) == 1

    def test_us294_potager_non_partage_ne_previent_personne(self, client, jardin, sessions, telegram):
        _connecter(client, jardin)
        assert telegram.envoyes == []

    def test_us294_un_echec_d_envoi_ne_defait_pas_la_connexion(self, client, partage, sessions, monkeypatch):
        def casse(*a, **k):
            raise RuntimeError("réseau")
        monkeypatch.setattr(telegram_notify, "envoyer", casse)
        assert _connecter(client, partage["paul_jardin"])["access_token"]

    def test_us294_l_ecran_membres_le_mentionne(self, client, partage, sessions, telegram):
        _connecter(client, partage["paul_jardin"], ecriture=True)
        membres = client.get(f"/potagers/{partage['mesanges']}/membres", headers=_pwa(partage["user_id"])).json()["membres"]
        par_nom = {m["nom"]: m for m in membres}
        assert par_nom["Paul"]["assistants"] == [{"client": "Claude", "portee": "ecriture"}]
        assert par_nom["Camille"]["assistants"] == []

    def test_us294_une_connexion_revoquee_n_est_plus_mentionnee(self, client, partage, sessions, telegram):
        _connecter(client, partage["paul_jardin"])
        identifiant = _connexions(client, partage["paul"])[0]["id"]
        client.delete(f"/mcp/connexions/{identifiant}", headers=_pwa(partage["paul"]))
        membres = client.get(f"/potagers/{partage['mesanges']}/membres", headers=_pwa(partage["user_id"])).json()["membres"]
        assert all(m["assistants"] == [] for m in membres)


# ── CA6 : interdire les assistants externes ──────────────────────────────────
class TestCA6Interdiction:
    def _interdire(self, client, user_id, potager_id, interdit=True):
        return client.patch(f"/potagers/{potager_id}/assistants-externes", headers=_pwa(user_id), json={"interdit": interdit})

    def test_us294_le_proprietaire_interdit_et_l_appel_suivant_est_refuse(self, client, partage, sessions, telegram):
        jeton = _connecter(client, partage["paul_jardin"], potagers=[partage["mesanges"]])["access_token"]
        assert _donnees(_appeler(client, jeton, "lister_potagers"))["potagers"]
        assert self._interdire(client, partage["user_id"], partage["mesanges"]).json()["assistants_externes_interdits"] is True
        assert "interdit" in _refus(_appeler(client, jeton, "consulter_carnet", {"potager": partage["mesanges"]}))
        assert "interdit" in _refus(_appeler(client, jeton, "consulter_carnet"))  # sans potager nommé : aucun accessible
        assert _donnees(_appeler(client, jeton, "lister_potagers"))["potagers"] == []

    def test_us294_la_connexion_reste_valable_pour_les_autres_potagers(self, client, partage, sessions, telegram, fabrique):
        with fabrique() as db:  # Paul est aussi membre du Verger, qui reste ouvert
            db.add(PotagerMembre(user_id=partage["paul"], potager_id=partage["verger"], role="editor"))
            db.commit()
        jeton = _connecter(client, partage["paul_jardin"], potagers=[partage["mesanges"], partage["verger"]])["access_token"]
        self._interdire(client, partage["user_id"], partage["mesanges"])
        potagers = _donnees(_appeler(client, jeton, "lister_potagers"))["potagers"]
        assert [p["nom"] for p in potagers] == ["Le Verger"]
        assert _rpc(client, jeton, "tools/list").status_code == 200

    def test_us294_la_page_de_consentement_ne_le_propose_plus(self, client, partage, sessions, telegram):
        from tests.test_us290_serveur_mcp import _autoriser, _demande, _enregistrer, _pkce

        self._interdire(client, partage["user_id"], partage["mesanges"])
        _, challenge = _pkce()
        demande = _demande(_autoriser(client, _enregistrer(client)["client_id"], challenge))
        proposes = client.get("/oauth/demande", params={"demande": demande}, headers=_pwa(partage["paul"])).json()["potagers"]
        assert "Les Mésanges" not in [p["nom"] for p in proposes]
        refus = client.post("/oauth/consentement", headers=_pwa(partage["paul"]), json={
            "demande": demande, "accepte": True, "ecriture": False, "potager_ids": [partage["mesanges"]]})
        assert refus.status_code == 400 and "interdit" in refus.json()["detail"]

    def test_us294_un_membre_non_proprietaire_ne_peut_pas(self, client, partage, sessions):
        assert self._interdire(client, partage["paul"], partage["mesanges"]).status_code == 403

    def test_us294_potager_inconnu_ou_etranger(self, client, partage, sessions):
        assert self._interdire(client, partage["user_id"], partage["etranger"]).status_code == 403

    def test_us294_on_peut_rouvrir(self, client, partage, sessions, telegram):
        jeton = _connecter(client, partage["paul_jardin"])["access_token"]
        self._interdire(client, partage["user_id"], partage["mesanges"])
        self._interdire(client, partage["user_id"], partage["mesanges"], interdit=False)
        assert _donnees(_appeler(client, jeton, "lister_potagers"))["potagers"]

    def test_us294_la_liste_des_potagers_porte_le_reglage(self, client, partage, sessions):
        self._interdire(client, partage["user_id"], partage["mesanges"])
        potagers = client.get("/potagers", headers=_pwa(partage["user_id"])).json()["potagers"]
        assert {p["nom"]: p["assistants_externes_interdits"] for p in potagers}["Les Mésanges"] is True

    def test_us294_la_connexion_signale_le_potager_ferme(self, client, partage, sessions, telegram):
        _connecter(client, partage["paul_jardin"])
        self._interdire(client, partage["user_id"], partage["mesanges"])
        (ligne,) = _connexions(client, partage["paul"])
        assert ligne["potagers"][0]["interdit"] is True


# ── Scénario Gherkin ─────────────────────────────────────────────────────────
def test_us294_gherkin(client, partage, sessions, telegram, fabrique):
    """Camille (« editor » ici : Paul) connecte ChatGPT en lecture ; le propriétaire est prévenu,
    interdit, et l'appel suivant est refusé ; sa connexion reste valable pour ses autres potagers."""
    with fabrique() as db:
        db.add(PotagerMembre(user_id=partage["paul"], potager_id=partage["verger"], role="editor"))
        db.commit()
    from tests.test_us290_serveur_mcp import _enregistrer
    chatgpt = _enregistrer(client, client_name="ChatGPT")
    jeton = _connecter(client, partage["paul_jardin"], potagers=[partage["mesanges"], partage["verger"]],
                       enregistrement=chatgpt)["access_token"]
    assert "Paul a connecté ChatGPT à ce potager, en lecture" in telegram.envoyes[0][1]
    client.patch(f"/potagers/{partage['mesanges']}/assistants-externes", headers=_pwa(partage["user_id"]),
                 json={"interdit": True})
    assert "interdit" in _refus(_appeler(client, jeton, "consulter_carnet", {"potager": "Les Mésanges"}))
    assert _donnees(_appeler(client, jeton, "lister_potagers"))["potagers"][0]["nom"] == "Le Verger"
