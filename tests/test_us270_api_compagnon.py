"""
tests/test_us270_api_compagnon.py — Ouvrir le compagnon à l'API [US-270]
=========================================================================
La PWA reçoit la MÊME décision que Telegram : l'orchestrateur
(`app/services/compagnon/orchestrateur.py`) range l'ordre de lecture d'une phrase, le bot et
l'API le suivent. Couverture CA1 → CA8 et le scénario Gherkin.

Aucun appel réseau ni modèle : le parseur est simulé (une grammaire sans potager ne lit presque
rien), la cascade des questions est patchée, l'agent est éteint (`AGENT_MODE=off`).
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import config
from app.services import evenements as svc_evenements
from app.services import interpreteur_commandes as interp
from app.services import normalisation_gestes as svc_normalisation
from app.services.compagnon import echange_pwa as svc_echange
from app.services.compagnon import gestes_conversation as svc_gestes_dits
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext, default_context
from database.models import CultureConfig, EchangeConversation, Evenement, Parcelle, Proposition
from llm import routeur

RACINE = Path(__file__).resolve().parents[1]
CTX = default_context()
AUTRE_POTAGER = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id + 1, role="owner")
AUTRE_JARDINIER = TenantContext(user_id=CTX.user_id + 1, potager_id=CTX.potager_id, role="owner")

GHERKIN = "j'ai semé des radis sur la planche sud 2 rangs"
#: Ce que le parseur lit de la phrase du Gherkin — le même pour le bot et pour l'API.
ITEM_GHERKIN = {
    "action": "semis", "culture": "radis", "variete": None, "quantite": 2.0, "unite": "rangs",
    "parcelle": "Sud", "rang": None, "duree_minutes": None, "traitement": None, "date": None,
    "commentaire": None, "nb_graines_semees": None, "nb_plants_godets": None,
    "origine_parsing": "deterministe",
}


@pytest.fixture(autouse=True)
def sans_modele(monkeypatch):
    """L'agent est éteint : la phrase suit les règles, puis le routeur."""
    monkeypatch.setattr(config, "AGENT_MODE", "off")


@pytest.fixture
def potager(memoire_compagnon):
    """Une parcelle « Sud » dans la base du compagnon ; vidée en fin de test."""
    with memoire_compagnon() as db:
        db.add(Parcelle(nom="Sud", nom_normalise="sud", ordre=1, actif=True, potager_id=CTX.potager_id))
        db.add_all([CultureConfig(nom="radis", type_organe_recolte="végétatif"),
                    CultureConfig(nom="tomate", type_organe_recolte="reproducteur")])
        db.commit()
    yield memoire_compagnon
    with memoire_compagnon() as db:
        db.query(Evenement).delete()
        db.query(Parcelle).delete()
        db.query(CultureConfig).delete()
        db.query(EchangeConversation).delete()
        db.commit()


def _parseur(items_par_phrase: dict[str, list[dict]]):
    """Un parseur déterministe simulé : les phrases connues sont reconnues, les autres non."""
    def parseur(texte, ctx=None):
        items = items_par_phrase.get(texte)
        return type("R", (), {"reconnu": items is not None, "items": [dict(i) for i in items] if items else None})()
    return parseur


@pytest.fixture
def parseur_gherkin(monkeypatch):
    fausse = _parseur({GHERKIN: [ITEM_GHERKIN]})
    monkeypatch.setattr(svc_normalisation, "parser_saisie", fausse)
    return fausse


def _nature_action(monkeypatch):
    """Le routeur classe la phrase comme une ACTION (aucun modèle)."""
    decision = routeur.DecisionRoutage(nature=routeur.NATURE_ACTION, origine="regle", confiance=1.0)
    return patch("llm.routeur.classer_demande", return_value=decision)


def _compter(db, modele) -> int:
    return db.query(modele).count()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — POST /compagnon/messages : la phrase, la réponse, les propositions
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Messages:

    def test_gherkin_un_geste_dit_donne_une_carte_a_confirmer(self, potager, parseur_gherkin):
        with _nature_action(None):
            reponse = svc_echange.repondre(CTX, GHERKIN)

        assert reponse.vers == svc_echange.VERS_GESTE
        assert len(reponse.propositions) == 1
        carte = reponse.propositions[0]
        assert carte["nature"] == "geste" and carte["confirmable"] is True
        assert carte["items"][0]["action"] == "semis" and carte["items"][0]["culture"] == "radis"
        assert carte["items"][0]["parcelle"] == "Sud"
        assert "radis" in carte["resume"]

    def test_ca1_rien_n_est_ecrit_avant_la_confirmation(self, potager, parseur_gherkin):
        with _nature_action(None):
            svc_echange.repondre(CTX, GHERKIN)
        with potager() as db:
            assert _compter(db, Evenement) == 0
            assert _compter(db, Proposition) == 1

    def test_ca1_une_question_part_a_la_cascade_commune(self, potager):
        cascade = routeur.ReponseCascade(texte="12 kg de tomates.", etage_resolveur="data", routage_log_id=7)
        with patch("llm.routeur.classer_demande", return_value=routeur.DecisionRoutage(
                nature=routeur.NATURE_QUESTION_DATA, origine="regle", confiance=1.0)), \
             patch("llm.routeur.repondre_avec_cascade", return_value=cascade) as appel:
            reponse = svc_echange.repondre(CTX, "combien de kg de tomates cette saison ?")

        appel.assert_called_once()
        assert reponse.vers == svc_echange.VERS_QUESTION
        assert reponse.texte == "12 kg de tomates."
        assert reponse.routage_log_id == 7 and reponse.etage == "data"
        assert reponse.propositions == []

    def test_ca1_ce_qui_manque_devient_une_question_et_rien_n_est_propose(self, potager, monkeypatch):
        sans_quantite = dict(ITEM_GHERKIN, quantite=None, unite=None)
        monkeypatch.setattr(svc_normalisation, "parser_saisie", _parseur({GHERKIN: [sans_quantite]}))
        with _nature_action(None):
            reponse = svc_echange.repondre(CTX, GHERKIN)
        assert reponse.vers == svc_echange.VERS_REPONSE
        assert "quantité" in reponse.texte.lower()
        assert reponse.propositions == []
        with potager() as db:
            assert _compter(db, Proposition) == 0

    def test_ca1_une_parcelle_inconnue_est_dite_en_clair(self, potager, monkeypatch):
        ailleurs = dict(ITEM_GHERKIN, parcelle="Introuvable")
        monkeypatch.setattr(svc_normalisation, "parser_saisie", _parseur({GHERKIN: [ailleurs]}))
        with _nature_action(None):
            reponse = svc_echange.repondre(CTX, GHERKIN)
        assert reponse.propositions == []
        assert "introuvable" in reponse.texte.lower()

    def test_ca1_une_phrase_vide_est_refusee(self, potager):
        with pytest.raises(svc_echange.TexteVideError):
            svc_echange.repondre(CTX, "   ")

    def test_ca1_un_lecteur_ne_dit_pas_de_geste(self, potager, parseur_gherkin):
        from app.services.permissions import PermissionInsuffisanteError

        lecteur = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id, role="viewer")
        with _nature_action(None), pytest.raises(PermissionInsuffisanteError):
            svc_echange.repondre(lecteur, GHERKIN)

    def test_ca1_un_geste_remplace_le_precedent(self, potager, parseur_gherkin):
        with _nature_action(None):
            premiere = svc_echange.repondre(CTX, GHERKIN).propositions[0]
            seconde = svc_echange.repondre(CTX, GHERKIN).propositions[0]
        assert premiere["id"] != seconde["id"]
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
            svc_gestes_dits.par_id(CTX, premiere["id"]) and svc_gestes_dits.abandonner(CTX, premiere["id"])
        assert refus.value.etat == svc_propositions.ETAT_REMPLACEE
        assert [c["id"] for c in svc_echange.cartes_en_cours(CTX)] == [seconde["id"]]

    def test_ca1_une_commande_comprise_est_rangee_et_visible_dans_telegram(self, potager):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")],
            {"nom": "Sud", "modification": "rangs=2"}, interp.ORIGINE_REGLE, 1.0, "passe la sud à 2 rangs",
        )
        with patch.object(svc_orchestrateur.svc_interpreteur, "interpreter", return_value=commande):
            reponse = svc_echange.repondre(CTX, "passe la sud à 2 rangs")

        assert reponse.vers == svc_echange.VERS_COMMANDE
        carte = reponse.propositions[0]
        assert carte["nature"] == "commande" and carte["confirmable"] is False
        # La proposition est celle que le bot lira aussi (US-259) : même table, même jardinier.
        telegram = svc_propositions.en_attente(CTX.user_id, CTX.potager_id)
        assert telegram is not None and telegram.id == carte["id"] and telegram.canal == "pwa"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — confirmer / abandonner : sortie atomique (règles d'US-259)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Confirmer:

    def _carte(self):
        with _nature_action(None):
            return svc_echange.repondre(CTX, GHERKIN).propositions[0]

    def test_gherkin_confirmer_ecrit_le_geste_et_le_dit(self, potager, parseur_gherkin):
        carte = self._carte()
        resultat = svc_echange.confirmer(CTX, carte["id"])

        assert resultat.erreur is None and resultat.texte.startswith("✅ Confirmé")
        assert resultat.carte["etat"] == svc_propositions.ETAT_CONFIRMEE
        with potager() as db:
            evenement = db.query(Evenement).one()
            assert evenement.type_action == "semis" and evenement.culture == "radis"

    def test_ca2_la_seconde_confirmation_n_ecrit_rien(self, potager, parseur_gherkin):
        carte = self._carte()
        svc_echange.confirmer(CTX, carte["id"])
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
            svc_echange.confirmer(CTX, carte["id"])
        assert refus.value.etat == svc_propositions.ETAT_CONFIRMEE
        with potager() as db:
            assert _compter(db, Evenement) == 1

    def test_ca2_deux_confirmations_simultanees_n_ecrivent_qu_une_fois(self, potager, parseur_gherkin):
        """L'autre clic (autre onglet, Telegram) sort la proposition entre la lecture et la sortie :
        la sortie atomique (`UPDATE … WHERE etat = 'en_attente'`) refuse la seconde, qui n'écrit rien."""
        carte = self._carte()
        with patch.object(svc_gestes_dits, "_controler_en_attente"):     # lue « en attente »…
            with svc_propositions.session_sur(CTX.potager_id) as db:     # … l'autre clic passe avant
                assert svc_propositions.sortir(db, carte["id"], svc_propositions.ETAT_CONFIRMEE, canal="telegram")
            with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
                svc_echange.confirmer(CTX, carte["id"])
        assert refus.value.etat == svc_propositions.ETAT_CONFIRMEE and refus.value.canal == "telegram"
        with potager() as db:
            assert _compter(db, Evenement) == 0

    def test_ca2_abandonner_ne_fait_rien_et_sort_de_l_attente(self, potager, parseur_gherkin):
        carte = self._carte()
        resultat = svc_echange.abandonner(CTX, carte["id"])
        assert resultat.carte["etat"] == svc_propositions.ETAT_ABANDONNEE
        with potager() as db:
            assert _compter(db, Evenement) == 0
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError):
            svc_echange.confirmer(CTX, carte["id"])

    def test_ca2_une_proposition_expiree_n_est_plus_confirmable(self, potager, parseur_gherkin):
        carte = self._carte()
        with potager() as db:
            db.query(Proposition).filter(Proposition.id == carte["id"]).update(
                {"expire_le": Proposition.cree_le})
            db.commit()
        with pytest.raises(svc_gestes_dits.GesteDejaTraiteError) as refus:
            svc_echange.confirmer(CTX, carte["id"])
        assert refus.value.etat == svc_propositions.ETAT_PERIMEE
        with potager() as db:
            assert _compter(db, Evenement) == 0

    def test_ca2_un_refus_d_ecriture_remet_le_geste_en_attente(self, potager, parseur_gherkin):
        carte = self._carte()
        with potager() as db:
            db.query(Parcelle).delete()    # la parcelle a disparu entre la carte et le clic
            db.commit()
        resultat = svc_echange.confirmer(CTX, carte["id"])
        assert resultat.erreur and resultat.texte.startswith("❌")
        assert resultat.carte["etat"] == svc_propositions.ETAT_EN_ATTENTE
        with potager() as db:
            assert _compter(db, Evenement) == 0

    def test_ca2_une_commande_se_confirme_dans_telegram_mais_s_abandonne_ici(self, potager):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")],
            {"nom": "Sud", "modification": "rangs=2"}, interp.ORIGINE_REGLE, 1.0, "passe la sud à 2 rangs",
        )
        proposition = svc_propositions.proposer(CTX, commande, canal="pwa")
        with pytest.raises(svc_echange.NonConfirmableDansLaPwaError):
            svc_echange.confirmer(CTX, proposition.id)
        assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id) is not None   # elle attend toujours

        svc_echange.abandonner(CTX, proposition.id)
        assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id) is None

    def test_ca2_la_file_de_gestes_d_us224_ne_voit_pas_le_geste_dit(self, potager, parseur_gherkin):
        from app.services import file_gestes as svc_file

        self._carte()
        with potager() as db:
            assert svc_file.lister_en_attente(db, CTX.user_id) == []
            assert svc_file.gestes_a_avertir(db) == [] and svc_file.gestes_perimes(db) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — l'historique des échanges et des cartes en cours
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Historique:

    def test_ca3_echanges_recents_et_cartes_en_cours(self, potager, parseur_gherkin):
        with _nature_action(None):
            svc_echange.repondre(CTX, GHERKIN)
        histoire = svc_echange.historique(CTX)
        assert len(histoire["cartes"]) == 1 and histoire["cartes"][0]["nature"] == "geste"
        assert histoire["echanges"] and histoire["echanges"][-1]["jardinier"] == GHERKIN

    def test_ca3_les_echanges_sont_ceux_que_telegram_lira(self, potager, parseur_gherkin):
        with _nature_action(None):
            svc_echange.repondre(CTX, GHERKIN)
        from app.services.compagnon import conversations

        assert conversations.recents(CTX)[-1].texte == GHERKIN

    def test_ca3_une_carte_traitee_n_est_plus_en_cours(self, potager, parseur_gherkin):
        with _nature_action(None):
            carte = svc_echange.repondre(CTX, GHERKIN).propositions[0]
        svc_echange.abandonner(CTX, carte["id"])
        assert svc_echange.historique(CTX)["cartes"] == []


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — parité : un corpus commun donne le même résultat par l'API et par le bot (R3, R5)
# ═════════════════════════════════════════════════════════════════════════════
#: (phrase, ce que les deux canaux doivent décider)
CORPUS_PARITE = [
    ("récolté 2 kg de tomates", "geste"),
    (GHERKIN, "geste"),
    ("combien de kg de tomates cette saison ?", "question"),
    ("pourquoi mes courgettes jaunissent ?", "question"),
    ("quand semer les poireaux ?", "presente"),       # les règles y reconnaissent le calendrier
    ("montre-moi le plan", "presente"),
]
ITEM_TOMATES = dict(ITEM_GHERKIN, action="recolte", culture="tomate", quantite=2.0, unite="kg", parcelle=None)


def _classer_comme_le_routeur_des_regles(texte, ctx=None):
    nature = routeur.NATURE_QUESTION_DATA if texte.rstrip().endswith("?") else routeur.NATURE_ACTION
    return routeur.DecisionRoutage(nature=nature, origine="regle", confiance=1.0)


@pytest.fixture
def corpus_hors_ligne(potager, monkeypatch):
    """Le même parseur simulé pour les deux canaux, le même routeur, la même cascade."""
    fausse = _parseur({"récolté 2 kg de tomates": [ITEM_TOMATES], GHERKIN: [ITEM_GHERKIN]})
    monkeypatch.setattr(svc_normalisation, "parser_saisie", fausse)
    monkeypatch.setattr("app.bot.parser_saisie", fausse)
    monkeypatch.setattr(routeur, "classer_demande", _classer_comme_le_routeur_des_regles)
    cascade = routeur.ReponseCascade(texte="Réponse.", etage_resolveur="data", routage_log_id=None)
    monkeypatch.setattr(routeur, "repondre_avec_cascade", lambda *a, **k: cascade)
    from app.services import gestes as svc_gestes

    with potager() as db:        # la tomate a déjà été semée : une récolte est possible
        svc_gestes.enregistrer_gestes(db, CTX, [dict(ITEM_GHERKIN, culture="tomate", parcelle="Sud")], "semis tomate")
    return fausse


async def _decision_du_bot(phrase: str) -> str:
    """Ce que `handle_text` fait de la phrase : où elle part, sans rien envoyer dans Telegram."""
    from app.bot import messages

    update = MagicMock()
    update.message.text = phrase
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 42
    tg_ctx = MagicMock(user_data={})
    destination: list[str] = []

    async def presenter(update_, ctx_, resultat, msg=None):
        prise = svc_orchestrateur.presente_par_le_canal(resultat)
        if prise:
            destination.append("presente")
        return prise

    with patch.object(messages, "_verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),          patch.object(messages, "current_context", return_value=CTX),          patch.object(messages, "contexte_court_de", return_value=None),          patch.object(messages, "reprendre_reponse", side_effect=lambda u, t: t),          patch.object(messages, "_traiter_commande_interpretee", new=presenter),          patch.object(messages, "_ask_question", new=AsyncMock(side_effect=lambda *a, **k: destination.append("question"))),          patch.object(messages, "_parse_and_save", new=AsyncMock(side_effect=lambda *a, **k: destination.append("geste"))):
        await messages.handle_text(update, tg_ctx)
    assert len(destination) == 1, destination
    return destination[0]


def _decision_de_l_api(phrase: str) -> str:
    vers = svc_echange.repondre(CTX, phrase).vers
    return {svc_echange.VERS_GESTE: "geste", svc_echange.VERS_QUESTION: "question"}.get(vers, "presente")


class TestCA6Parite:

    @pytest.mark.asyncio
    @pytest.mark.parametrize("phrase,attendu", CORPUS_PARITE)
    async def test_ca6_meme_decision_par_le_bot_et_par_l_api(self, corpus_hors_ligne, phrase, attendu):
        bot = await _decision_du_bot(phrase)
        api = _decision_de_l_api(phrase)
        assert bot == api == attendu, f"{phrase!r} : bot={bot} api={api}"

    @pytest.mark.asyncio
    async def test_ca6_gherkin_la_proposition_est_celle_que_le_bot_aurait_faite(
            self, corpus_hors_ligne, memoire_compagnon, monkeypatch):
        """Les items à confirmer sont les mêmes : le bot les range en attente de confirmation, l'API
        dans la carte. (Le bot choisit seul une parcelle quand le geste n'en cite pas — menu ou
        affectation automatique, étape propre à Telegram : le Gherkin cite la sienne.)"""
        from app.bot import etat, saisie

        phrase = GHERKIN

        update = MagicMock()
        update.effective_user.id = 42
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        monkeypatch.setattr("app.bot.SessionLocal", memoire_compagnon)
        monkeypatch.setattr("app.bot.current_context", lambda: CTX)
        etat._ACTION_PENDING.pop(42, None)
        await saisie._parse_and_save(update, phrase)
        du_bot = etat._ACTION_PENDING.pop(42)["items"]

        with _nature_action(None):
            carte = svc_echange.repondre(CTX, phrase).propositions[0]

        cles = ("action", "culture", "variete", "quantite", "unite", "parcelle", "date")
        assert [{k: i.get(k) for k in cles} for i in carte["items"]] == [{k: i.get(k) for k in cles} for i in du_bot]


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — le potager du compte connecté, rien d'un autre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Isolation:

    def _carte(self):
        with _nature_action(None):
            return svc_echange.repondre(CTX, GHERKIN).propositions[0]

    def test_ca7_un_autre_potager_ne_voit_pas_la_carte(self, potager, parseur_gherkin):
        carte = self._carte()
        assert svc_echange.historique(AUTRE_POTAGER)["cartes"] == []
        with pytest.raises(svc_gestes_dits.GesteIntrouvableError):
            svc_echange.confirmer(AUTRE_POTAGER, carte["id"])

    def test_ca7_un_autre_jardinier_ne_peut_ni_confirmer_ni_abandonner(self, potager, parseur_gherkin):
        carte = self._carte()
        with pytest.raises(svc_gestes_dits.GesteIntrouvableError):
            svc_echange.confirmer(AUTRE_JARDINIER, carte["id"])
        with pytest.raises(svc_gestes_dits.GesteIntrouvableError):
            svc_echange.abandonner(AUTRE_JARDINIER, carte["id"])
        with potager() as db:
            assert _compter(db, Evenement) == 0
        assert svc_echange.historique(AUTRE_JARDINIER)["echanges"] == []

    def test_ca7_une_commande_d_un_autre_jardinier_n_existe_pas(self, potager):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")],
            {"nom": "Sud", "modification": "rangs=2"}, interp.ORIGINE_REGLE, 1.0, "x",
        )
        proposition = svc_propositions.proposer(CTX, commande, canal="pwa")
        with pytest.raises(svc_gestes_dits.GesteIntrouvableError):
            svc_echange.abandonner(AUTRE_JARDINIER, proposition.id)
        assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id) is not None


# ═════════════════════════════════════════════════════════════════════════════
# Les routes HTTP (CA1, CA2, CA3, CA5)
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def client(potager, parseur_gherkin):
    from app.api.main import app, get_current_user_ctx

    app.dependency_overrides[get_current_user_ctx] = default_context
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


class TestRoutes:

    def test_post_messages_puis_confirmer_puis_historique(self, client):
        with _nature_action(None):
            reponse = client.post("/compagnon/messages", json={"texte": GHERKIN})
        assert reponse.status_code == 200
        carte = reponse.json()["propositions"][0]

        confirmation = client.post(f"/compagnon/propositions/{carte['id']}/confirmer")
        assert confirmation.status_code == 200
        assert confirmation.json()["texte"].startswith("✅ Confirmé")

        encore = client.post(f"/compagnon/propositions/{carte['id']}/confirmer")
        assert encore.status_code == 409 and encore.json()["detail"]["code"] == "deja_traitee"

        histoire = client.get("/compagnon/historique").json()
        assert histoire["cartes"] == [] and histoire["echanges"]

    def test_abandonner_puis_proposition_inconnue(self, client):
        with _nature_action(None):
            carte = client.post("/compagnon/messages", json={"texte": GHERKIN}).json()["propositions"][0]
        assert client.post(f"/compagnon/propositions/{carte['id']}/abandonner").status_code == 200
        assert client.post("/compagnon/propositions/999999/confirmer").status_code == 404

    def test_texte_vide_donne_422(self, client):
        assert client.post("/compagnon/messages", json={"texte": "  "}).status_code == 422

    def test_modele_indisponible_donne_503_avec_le_message_de_repli(self, client):
        from llm.passerelle import MESSAGE_REPLI_IA, LLMIndisponibleError

        with patch("llm.routeur.classer_demande", return_value=routeur.DecisionRoutage(
                nature=routeur.NATURE_QUESTION_DATA, origine="regle", confiance=1.0)), \
             patch("llm.routeur.repondre_avec_cascade", side_effect=LLMIndisponibleError("429")):
            reponse = client.post("/compagnon/messages", json={"texte": "combien de tomates ?"})
        assert reponse.status_code == 503 and reponse.json()["detail"] == MESSAGE_REPLI_IA

    def test_commande_non_confirmable_donne_409_explicite(self, client):
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "modifier")],
            {"nom": "Sud", "modification": "rangs=2"}, interp.ORIGINE_REGLE, 1.0, "x",
        )
        proposition = svc_propositions.proposer(CTX, commande, canal="pwa")
        reponse = client.post(f"/compagnon/propositions/{proposition.id}/confirmer")
        assert reponse.status_code == 409 and reponse.json()["detail"]["code"] == "confirmable_dans_telegram"


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — la distribution est extraite ; le bot l'appelle sans changement visible
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Extraction:

    def test_ca4_handle_text_delegue_a_l_orchestrateur(self):
        from app.bot import messages

        source = inspect.getsource(messages.handle_text)
        assert "svc_orchestrateur.distribuer(" in source and "svc_orchestrateur.orienter(" in source
        # Plus aucun appel direct à l'agent, à l'interpréteur ni au routeur dans le handler.
        for interdit in ("svc_interpreteur.agent_d_abord(", "svc_interpreteur.interpreter(",
                         "routeur.classer_demande("):
            assert interdit not in source

    @pytest.mark.asyncio
    async def test_ca4_l_ordre_agent_raccourcis_dialogue_interpreteur(self, monkeypatch):
        """Mode ordinaire : raccourcis, dialogue, puis l'interpréteur ; chaque garde peut prendre la phrase."""
        appels: list[str] = []

        def garde(nom, prend):
            async def _garde(texte):
                appels.append(nom)
                return prend
            return _garde

        monkeypatch.setattr(interp, "interpreter", lambda *a, **k: appels.append("interpreteur") or None)
        canal = svc_orchestrateur.Canal(nom="test", dialogue=garde("dialogue", False),
                                        raccourcis=garde("raccourcis", False))
        distribution = await svc_orchestrateur.distribuer("bonjour", CTX, canal)
        assert appels == ["raccourcis", "dialogue", "interpreteur"] and distribution.resultat is None

        appels.clear()
        canal = svc_orchestrateur.Canal(nom="test", dialogue=garde("dialogue", False),
                                        raccourcis=garde("raccourcis", True))
        distribution = await svc_orchestrateur.distribuer("annuler", CTX, canal)
        assert appels == ["raccourcis"] and distribution.pris_par_le_canal

    @pytest.mark.asyncio
    async def test_ca4_en_prioritaire_le_dialogue_puis_l_agent_avant_les_raccourcis(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "prioritaire")
        appels: list[str] = []
        monkeypatch.setattr(interp, "agent_d_abord", lambda *a, **k: appels.append("agent") or None)

        async def dialogue(texte):
            appels.append("dialogue")
            return False

        async def raccourcis(texte):
            appels.append("raccourcis")
            return False

        canal = svc_orchestrateur.Canal(nom="test", dialogue=dialogue, raccourcis=raccourcis,
                                        boutons_exacts=frozenset({"annuler"}))
        await svc_orchestrateur.distribuer("bonjour", CTX, canal)
        assert appels == ["dialogue", "agent"]       # l'agent a répondu : les raccourcis ne sont pas lus
        appels.clear()
        await svc_orchestrateur.distribuer("annuler", CTX, canal)   # le texte exact d'un bouton
        assert appels == ["raccourcis"]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — /ask passe par la cascade commune (E0)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Ask:

    def test_ca5_ask_api_passe_par_la_cascade(self, client):
        cascade = routeur.ReponseCascade(texte="Bientôt.", etage_resolveur="savoir", routage_log_id=3)
        with patch("llm.routeur.repondre_avec_cascade", return_value=cascade) as appel:
            reponse = client.post("/ask", json={"texte": "quand semer les poireaux ?"})
        appel.assert_called_once()
        assert reponse.json() == {"reponse": "Bientôt.", "routage_log_id": 3, "etage": "savoir"}

    @pytest.mark.asyncio
    async def test_ca5_ask_bot_passe_par_la_meme_fonction(self):
        from app.bot import questions

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        cascade = routeur.ReponseCascade(texte="Bientôt.", etage_resolveur="data", routage_log_id=None)
        with patch.object(svc_orchestrateur, "repondre_a_une_question", return_value=cascade) as commun, \
             patch.object(questions, "send_voice_reply", new=AsyncMock()), \
             patch.object(questions, "current_context", return_value=CTX):
            await questions._ask_question(update, "quand semer les poireaux ?", "QUESTION_SAVOIR")
        commun.assert_called_once_with(CTX, "quand semer les poireaux ?", "QUESTION_SAVOIR")


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — aucune logique métier dans les routes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8SansLogiqueDansLesRoutes:

    def _routes_compagnon(self) -> list[ast.FunctionDef]:
        arbre = ast.parse((RACINE / "app" / "api" / "main.py").read_text(encoding="utf-8"))
        retenues = []
        for noeud in ast.walk(arbre):
            if isinstance(noeud, ast.FunctionDef):
                for deco in noeud.decorator_list:
                    if isinstance(deco, ast.Call) and getattr(deco.func, "attr", "") in ("post", "get") \
                            and deco.args and isinstance(deco.args[0], ast.Constant) \
                            and str(deco.args[0].value).startswith(("/compagnon/messages", "/compagnon/propositions",
                                                                    "/compagnon/historique")):
                        retenues.append(noeud)
        return retenues

    def test_ca8_quatre_routes_et_aucune_requete_directe(self):
        routes = self._routes_compagnon()
        assert len(routes) == 4
        for route in routes:
            source = ast.unparse(route)
            for interdit in ("db.query", "SessionLocal", "session.query", ".commit("):
                assert interdit not in source, f"{route.name} : {interdit}"
            assert "svc_echange_pwa." in source

    def test_ca8_les_services_du_compagnon_n_importent_ni_telegram_ni_le_bot_ni_fastapi(self):
        for nom in ("orchestrateur", "echange_pwa", "gestes_conversation"):
            arbre = ast.parse((RACINE / "app" / "services" / "compagnon" / f"{nom}.py").read_text(encoding="utf-8"))
            modules = set()
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    modules.update(a.name for a in noeud.names)
                elif isinstance(noeud, ast.ImportFrom) and noeud.module:
                    modules.add(noeud.module)
            assert not any(m == "telegram" or m.startswith(("telegram.", "app.bot", "fastapi", "app.api"))
                           for m in modules), nom


class TestCultureAbsenteDeLaConfiguration:

    def test_us037_ca7_une_culture_inconnue_est_dite_et_rien_n_est_propose(self, potager, parseur_gherkin):
        """Le bot demande par boutons si la culture est végétative ou reproductive ; la PWA le dit."""
        with potager() as db:
            db.query(CultureConfig).delete()
            db.commit()
        with _nature_action(None):
            reponse = svc_echange.repondre(CTX, GHERKIN)
        assert reponse.propositions == [] and "ne connaît pas encore" in reponse.texte
