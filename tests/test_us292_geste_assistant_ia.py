"""
tests/test_us292_geste_assistant_ia.py — Enregistrer un geste depuis un assistant IA [US-292]
==============================================================================================
Un bloc par critère d'acceptance (CA1 à CA12) et le scénario Gherkin. Les outils sont appelés
par le vrai parcours MCP (jeton OAuth avec écriture, POST /mcp, `tools/call`). Telegram est
simulé et l'envoi des cartes est synchrone.
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services import telegram_notify
from app.services.compagnon import deux_canaux
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from app.services.mcp import ecritures as svc_ecritures
from app.services.mcp import serveur as svc_serveur
from sqlalchemy.orm import sessionmaker
from database.models import ActionMenee, CultureConfig, Evenement, Parcelle, Proposition, User
from tests.test_us290_serveur_mcp import (  # noqa: F401 — fixtures et aides partagées
    _appeler, _connecter, _pwa, _rpc, client, fabrique, jardin,
)

AUJOURD_HUI = date.today()
CHAT = 4242
ECRITURES = ("proposer_geste", "proposer_correction", "confirmer_proposition", "abandonner_proposition")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def sessions(fabrique, monkeypatch):
    """Tous les services ouvrent leurs sessions sur la base du test, Telegram en synchrone."""
    for module in list(sys.modules.values()):
        nom = getattr(module, "__name__", "") or ""
        if nom.startswith(("app.", "utils.", "llm.", "database.")) and isinstance(getattr(module, "SessionLocal", None), sessionmaker):
            monkeypatch.setattr(module, "SessionLocal", fabrique)
    monkeypatch.setattr(deux_canaux, "SYNCHRONE", True)


@pytest.fixture
def telegram(monkeypatch, fabrique, jardin):
    """Le compagnon Telegram de Camille est activé ; chaque envoi et chaque édition sont notés."""
    with fabrique() as db:
        db.get(User, jardin["user_id"]).telegram_chat_id = CHAT
        db.commit()
    faux = SimpleNamespace(envoyes=[], edites=[])

    def envoyer(chat_id, texte, boutons=None, parse_mode=None):
        faux.envoyes.append((chat_id, texte, boutons))
        return 9000 + len(faux.envoyes)

    def editer(chat_id, message_id, texte, boutons=None, parse_mode=None):
        faux.edites.append((chat_id, message_id, texte))
        return True

    monkeypatch.setattr(telegram_notify, "envoyer", envoyer)
    monkeypatch.setattr(telegram_notify, "editer_message", editer)
    return faux


@pytest.fixture
def sans_telegram(monkeypatch):
    monkeypatch.setattr(telegram_notify, "envoyer", lambda *a, **k: None)
    monkeypatch.setattr(telegram_notify, "editer_message", lambda *a, **k: True)


@pytest.fixture
def ecrivain(client, jardin, sans_telegram):
    """Un jeton avec écriture sur « Les Mésanges » (Camille y est propriétaire)."""
    return _connecter(client, jardin, ecriture=True, potagers=[jardin["mesanges"], jardin["verger"]])["access_token"]


@pytest.fixture
def mesanges(fabrique, jardin):
    """La planche Est : 37 fèves plantées (reproductrice), 0,6 kg déjà récoltés ; 20 laitues (végétative)."""
    with fabrique() as db:
        pid = jardin["mesanges"]
        db.add_all([
            CultureConfig(nom="fève", type_organe_recolte="reproducteur"),
            CultureConfig(nom="laitue", type_organe_recolte="végétatif"),
            CultureConfig(nom="haricot", type_organe_recolte="reproducteur"),
        ])
        planche = Parcelle(nom="Planche Est", nom_normalise="plancheest", potager_id=pid, actif=True)
        db.add(planche)
        db.flush()
        jour = datetime.combine(AUJOURD_HUI - timedelta(days=30), datetime.min.time())
        db.add_all([
            Evenement(type_action="plantation", culture="fève", quantite=37, unite="plants", date=jour,
                      potager_id=pid, parcelle_id=planche.id),
            Evenement(type_action="plantation", culture="laitue", quantite=20, unite="plants", date=jour,
                      potager_id=pid, parcelle_id=planche.id),
        ])
        db.commit()
        return {"planche": planche.id, "pid": pid}


@pytest.fixture
def cumul_06(fabrique, mesanges):
    with fabrique() as db:
        db.add(Evenement(type_action="recolte", culture="fève", quantite=0.6, unite="kg",
                         date=datetime.combine(AUJOURD_HUI - timedelta(days=3), datetime.min.time()),
                         potager_id=mesanges["pid"], parcelle_id=mesanges["planche"], type_organe_recolte="reproducteur"))
        db.commit()


def _donnees(resultat: dict) -> dict:
    assert resultat.get("isError") is not True, resultat
    return resultat["structuredContent"]


def _refus(resultat: dict) -> str:
    assert resultat.get("isError") is True, resultat
    return resultat["content"][0]["text"]


def _nb(fabrique, modele, **filtres) -> int:
    with fabrique() as db:
        return db.query(modele).filter_by(**filtres).count()


def _proposer(client, jeton, **arguments) -> dict:
    return _appeler(client, jeton, "proposer_geste", arguments)


def _ctx(jardin) -> TenantContext:
    return TenantContext(user_id=jardin["user_id"], potager_id=jardin["mesanges"], role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Une proposition, rien au carnet, un récapitulatif qui dit le stock
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Proposition:

    def test_us292_proposer_geste_n_ecrit_rien_au_carnet(self, client, fabrique, ecrivain, mesanges):
        avant = _nb(fabrique, Evenement)
        donnees = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1.1, unite="kg",
                                     parcelle="Planche Est"))
        assert isinstance(donnees["proposition"], int) and donnees["etat"] == "en_attente"
        assert _nb(fabrique, Evenement) == avant

    def test_us292_le_recapitulatif_dit_tout_le_geste(self, client, ecrivain, mesanges):
        jour = (AUJOURD_HUI - timedelta(days=1)).isoformat()
        donnees = _donnees(_proposer(client, ecrivain, type="plantation", culture="fève", variete="Aguadulce",
                                     quantite=12, unite="plants", parcelle="Planche Est", date=jour))
        (recap,) = donnees["recapitulatif"]
        assert (recap["geste"], recap["culture"], recap["variete"], recap["parcelle"]) == \
               ("plantation", "fève", "Aguadulce", "Planche Est")
        assert (recap["quantite"], recap["unite"], recap["date"]) == (12, "plants", jour)
        assert donnees["stock"] and "confirmer_proposition" in donnees["a_faire"]

    def test_us292_un_refus_de_la_validation_centrale_est_rendu(self, client, fabrique, ecrivain, mesanges):
        """Une récolte d'une variété jamais plantée : la validation d'US-049 parle, rien n'est proposé."""
        donnees = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", variete="Aguadulce",
                                     quantite=1, unite="kg", parcelle="Planche Est"))
        assert donnees["proposition"] is None and "Aucune trace" in donnees["question"]
        assert _nb(fabrique, Proposition) == 0

    def test_us292_type_hors_liste_refuse(self, client, ecrivain, mesanges):
        assert "type" in _refus(_proposer(client, ecrivain, type="arrachage_total", culture="fève"))

    def test_us292_culture_obligatoire(self, client, ecrivain, mesanges):
        assert "culture" in _refus(_proposer(client, ecrivain, type="recolte", quantite=1))
        assert "culture" in _refus(_proposer(client, ecrivain, type="observation", note="pucerons"))

    def test_us292_observation_datee_du_jour(self, client, ecrivain, mesanges):
        donnees = _donnees(_proposer(client, ecrivain, type="observation", culture="fève", note="pucerons"))
        assert donnees["recapitulatif"][0]["date"] == AUJOURD_HUI.isoformat()
        assert donnees["stock"] == "Le stock ne change pas."


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Semis initial
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Semis:

    def test_us292_semis_reproductif(self, client, ecrivain, mesanges):
        donnees = _donnees(_proposer(client, ecrivain, type="semis", culture="fève", quantite=40, unite="graines",
                                     parcelle="Planche Est"))
        assert donnees["stock"] == "Chaque graine levée donnera un pied qui produira plusieurs récoltes."

    def test_us292_semis_vegetatif(self, client, ecrivain, mesanges):
        donnees = _donnees(_proposer(client, ecrivain, type="semis", culture="laitue", quantite=30, unite="graines",
                                     parcelle="Planche Est"))
        assert "stock de pieds à récolter" in donnees["stock"]

    def test_us292_semis_culture_inconnue_revient_avec_une_question(self, client, ecrivain, mesanges):
        donnees = _donnees(_proposer(client, ecrivain, type="semis", culture="quinoa", quantite=10, unite="graines"))
        assert donnees["proposition"] is None and "végétative" in donnees["question"]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Première récolte
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3PremiereRecolte:

    def test_us292_premiere_recolte_reproductive(self, client, ecrivain, mesanges):
        stock = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=0.6, unite="kg"))["stock"]
        assert stock == "Pieds actifs : 37 (inchangé), premier rendement de la saison : 0,6 kg."

    def test_us292_recolte_vegetative_retire_les_pieds(self, client, ecrivain, mesanges):
        stock = _donnees(_proposer(client, ecrivain, type="recolte", culture="laitue", quantite=5, unite="plants"))["stock"]
        assert stock == "Pieds restants : 20 → 15 (pieds arrachés)."

    def test_us292_recolte_vegetative_pesee_ne_devine_pas_les_pieds(self, client, ecrivain, mesanges):
        stock = _donnees(_proposer(client, ecrivain, type="recolte", culture="laitue", quantite=2, unite="kg"))["stock"]
        assert "+2 kg" in stock and "nombre de pieds arrachés" in stock


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — N-ième récolte : le cumul s'allonge, les pieds ne bougent pas
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4NiemeRecolte:

    def test_us292_nieme_recolte_s_ajoute_au_cumul(self, client, ecrivain, cumul_06):
        stock = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1.1, unite="kg"))["stock"]
        assert stock == "Pieds actifs : 37 (inchangé), cumul saison : 0,6 → 1,7 kg."

    def test_us292_cumul_converti_en_grammes(self, client, ecrivain, cumul_06):
        stock = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=400, unite="g"))["stock"]
        assert "cumul saison : 600 → 1000 g" in stock

    def test_us292_une_recolte_n_est_jamais_une_perte(self, client, fabrique, ecrivain, cumul_06):
        ident = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1.1, unite="kg"))["proposition"]
        _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        stats = _donnees(_appeler(client, ecrivain, "voir_statistiques", {"culture": "fève"}))
        (feve,) = stats["cultures"]
        assert feve["pieds_actifs"] == 37 and feve["pieds_perdus"] == 0
        cumul = feve["rendement_cumule"]
        assert cumul["valeur"] == pytest.approx(1.7 if cumul["unite"] == "kg" else 1700)

    def test_us292_unites_incompatibles(self, client, ecrivain, cumul_06):
        stock = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=3, unite="poignées"))["stock"]
        assert "inchangé" in stock and "ajoutée au rendement" in stock


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Fin de vie : seule une perte réduit les pieds actifs
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Perte:

    def test_us292_perte_reduit_les_pieds_avec_sa_cause(self, client, ecrivain, mesanges):
        stock = _donnees(_proposer(client, ecrivain, type="perte", culture="fève", quantite=3, unite="plants",
                                   cause="gel"))["stock"]
        assert stock == "Pieds actifs : 37 → 34. Cause : gel."

    def test_us292_perte_sans_cause(self, client, ecrivain, mesanges):
        stock = _donnees(_proposer(client, ecrivain, type="perte", culture="fève", quantite=2, unite="plants"))["stock"]
        assert stock == "Pieds actifs : 37 → 35."

    def test_us292_plantation_ajoute_des_pieds(self, client, ecrivain, mesanges):
        stock = _donnees(_proposer(client, ecrivain, type="plantation", culture="fève", quantite=3, unite="plants",
                                   parcelle="Planche Est"))["stock"]
        assert stock == "Pieds actifs : 37 → 40."


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Parcelle inconnue : jamais créée, noms proches, aucune proposition
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6ParcelleInconnue:

    def test_us292_parcelle_introuvable_nomme_les_proches(self, client, fabrique, ecrivain, mesanges):
        texte = _refus(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1, unite="kg",
                                 parcelle="Serre du fond"))
        assert "introuvable" in texte and "Planche Est" in texte
        assert _nb(fabrique, Proposition) == 0
        assert _nb(fabrique, Parcelle) == 1

    def test_us292_potager_sans_parcelle(self, client, fabrique, jardin, sans_telegram):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        texte = _refus(_proposer(client, jeton, type="plantation", culture="fève", quantite=3, parcelle="Nord"))
        assert "aucune parcelle" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Quantité de pépinière obligatoire ; date future refusée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Controles:

    def test_us292_semis_sans_quantite_revient_avec_la_question(self, client, fabrique, ecrivain, mesanges):
        donnees = _donnees(_proposer(client, ecrivain, type="semis", culture="fève"))
        assert donnees["proposition"] is None and "Quelle quantité" in donnees["question"]
        assert _nb(fabrique, Proposition) == 0

    def test_us292_date_future_refusee(self, client, fabrique, ecrivain, mesanges):
        demain = (AUJOURD_HUI + timedelta(days=1)).isoformat()
        assert "Date future" in _refus(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1,
                                                 unite="kg", date=demain))
        assert _nb(fabrique, Proposition) == 0

    @pytest.mark.parametrize("arguments", [
        {"date": "hier"}, {"quantite": "beaucoup"}, {"quantite": -2}, {"rang": 1.5},
    ])
    def test_us292_arguments_invalides(self, client, ecrivain, mesanges, arguments):
        _refus(_proposer(client, ecrivain, type="recolte", culture="fève", unite="kg", **{"quantite": 1, **arguments}))


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Confirmer : services, sortie atomique, une seule écriture
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Confirmer:

    def _proposition(self, client, jeton) -> int:
        return _donnees(_proposer(client, jeton, type="recolte", culture="fève", quantite=1.1, unite="kg",
                                  parcelle="Planche Est"))["proposition"]

    def test_us292_confirmer_ecrit_une_fois(self, client, fabrique, ecrivain, mesanges):
        ident = self._proposition(client, ecrivain)
        donnees = _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        assert donnees["etat"] == "confirmee" and len(donnees["enregistres"]) == 1
        assert _nb(fabrique, Evenement, type_action="recolte") == 1

    def test_us292_seconde_confirmation_mcp_n_ecrit_rien(self, client, fabrique, ecrivain, mesanges):
        ident = self._proposition(client, ecrivain)
        _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        texte = _refus(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        assert texte.startswith("Déjà confirmé depuis l'assistant IA à ")
        assert _nb(fabrique, Evenement, type_action="recolte") == 1

    def test_us292_confirmee_dans_la_pwa_puis_par_mcp(self, client, fabrique, jardin, ecrivain, mesanges):
        ident = self._proposition(client, ecrivain)
        reponse = client.post(f"/compagnon/propositions/{ident}/confirmer", headers=_pwa(jardin["user_id"]))
        assert reponse.status_code == 200, reponse.text
        texte = _refus(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        assert texte.startswith("Déjà confirmé depuis le portail à ")
        assert _nb(fabrique, Evenement, type_action="recolte") == 1

    def test_us292_confirmee_par_mcp_puis_dans_la_pwa(self, client, jardin, ecrivain, mesanges):
        ident = self._proposition(client, ecrivain)
        _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        reponse = client.post(f"/compagnon/propositions/{ident}/confirmer", headers=_pwa(jardin["user_id"]))
        assert reponse.status_code == 409
        assert "depuis l'assistant IA" in reponse.text

    def test_us292_proposition_inconnue(self, client, ecrivain, mesanges):
        assert "Aucune proposition" in _refus(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": 999}))

    def test_us292_proposition_obligatoire(self, client, ecrivain, mesanges):
        _refus(_appeler(client, ecrivain, "confirmer_proposition", {}))

    def test_us292_abandonner_n_ecrit_rien(self, client, fabrique, ecrivain, mesanges):
        ident = self._proposition(client, ecrivain)
        donnees = _donnees(_appeler(client, ecrivain, "abandonner_proposition", {"proposition": ident}))
        assert donnees["etat"] == "abandonnee"
        assert "Déjà laissé tomber" in _refus(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        assert _nb(fabrique, Evenement, type_action="recolte") == 0

    def test_us292_abandonner_inconnue(self, client, ecrivain, mesanges):
        _refus(_appeler(client, ecrivain, "abandonner_proposition", {"proposition": 999}))

    def test_us292_une_nouvelle_proposition_remplace_la_precedente(self, client, ecrivain, mesanges):
        premiere = self._proposition(client, ecrivain)
        self._proposition(client, ecrivain)
        assert "Remplacée" in _refus(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": premiere}))

    def test_us292_confirmer_vise_le_potager_de_la_proposition(self, client, fabrique, jardin, ecrivain, mesanges):
        ident = self._proposition(client, ecrivain)
        with fabrique() as db:
            connexion = SimpleNamespace(user_id=jardin["user_id"])
            assert svc_ecritures.potager_de_la_proposition(db, connexion, {"proposition": ident}) == jardin["mesanges"]
            assert svc_ecritures.potager_de_la_proposition(db, connexion, {"proposition": "x"}) is None
            assert svc_ecritures.potager_de_la_proposition(db, SimpleNamespace(user_id=jardin["autre_id"]),
                                                           {"proposition": ident}) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — La proposition apparaît aussi dans la PWA et dans Telegram
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9DeuxFenetres:

    def test_us292_la_carte_part_dans_telegram(self, client, jardin, mesanges, telegram):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        _donnees(_proposer(client, jeton, type="recolte", culture="fève", quantite=1.1, unite="kg"))
        (chat, texte, boutons) = telegram.envoyes[-1]
        assert chat == CHAT and "🤖 Proposé par Claude" in texte
        assert boutons and "cmp:ok:" in boutons[0][0][1]

    def test_us292_la_carte_est_dans_le_panneau_de_la_pwa(self, client, jardin, ecrivain, mesanges):
        ident = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1.1, unite="kg"))["proposition"]
        from app.services.compagnon import echange_pwa

        cartes = echange_pwa.cartes_en_cours(_ctx(jardin))
        assert [c["id"] for c in cartes] == [ident] and cartes[0]["confirmable"] is True

    def test_us292_confirmee_par_mcp_la_carte_telegram_est_reecrite(self, client, jardin, mesanges, telegram):
        jeton = _connecter(client, jardin, ecriture=True)["access_token"]
        ident = _donnees(_proposer(client, jeton, type="recolte", culture="fève", quantite=1.1, unite="kg"))["proposition"]
        _donnees(_appeler(client, jeton, "confirmer_proposition", {"proposition": ident}))
        assert telegram.edites and telegram.edites[-1][2].startswith("✅ Confirmé depuis l'assistant IA à ")


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — Indication « écriture » ; aucune destruction par ce canal
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10Destruction:

    def test_us292_les_outils_d_ecriture_portent_l_indication(self, client, ecrivain):
        outils = {o["name"]: o for o in _rpc(client, ecrivain, "tools/list").json()["result"]["tools"]}
        for nom in ECRITURES:
            assert outils[nom]["annotations"]["readOnlyHint"] is False, nom
            assert outils[nom]["annotations"]["destructiveHint"] is False, nom

    def test_us292_invisibles_en_lecture_seule(self, client, jardin, sans_telegram):
        jeton = _connecter(client, jardin)["access_token"]
        noms = {o["name"] for o in _rpc(client, jeton, "tools/list").json()["result"]["tools"]}
        assert not noms & set(ECRITURES)

    def test_us292_lecteur_refuse(self, client, jardin, sans_telegram):
        jeton = _connecter(client, jardin, ecriture=True, potagers=[jardin["verger"]])["access_token"]
        assert "lecteur" in _refus(_proposer(client, jeton, type="observation", culture="fève", note="x", potager="Le Verger"))

    def test_us292_une_annulation_ne_se_confirme_pas_par_mcp(self, client, fabrique, jardin, ecrivain, mesanges):
        from app.services.compagnon import corrections

        with fabrique() as db:
            evenement = db.query(Evenement).filter_by(culture="fève").first().id
        candidate = corrections.Candidate(ref="A1", action=None, evenement_id=evenement,
                                          valeurs={"action": "plantation", "culture": "fève"}, resume="plantation fève")
        commande = corrections._proposition(corrections.FORME_ANNULER, candidate, "annule")
        proposition = svc_propositions.proposer(_ctx(jardin), commande, canal=svc_propositions.CANAL_PWA)
        texte = _refus(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": proposition.id}))
        assert "suppression" in texte and "?compagnon=ouvrir" in texte
        assert _nb(fabrique, Evenement, id=evenement) == 1
        with fabrique() as db:
            assert db.get(Proposition, proposition.id).etat == "en_attente"

    def test_us292_aucun_outil_destructeur_enregistrable(self):
        with pytest.raises(ValueError):
            svc_serveur.enregistrer_outil(svc_serveur.Outil(
                nom="supprimer_geste", titre="x", description="x", executer=lambda db, a: None,
                ecriture=True, destructeur=True))


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — proposer_correction (règles d'US-262)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA11Correction:

    def _noter(self, client, jeton, **arguments) -> int:
        ident = _donnees(_proposer(client, jeton, **arguments))["proposition"]
        enregistres = _donnees(_appeler(client, jeton, "confirmer_proposition", {"proposition": ident}))["enregistres"]
        return enregistres[0]["event_id"]

    def test_us292_correction_avant_apres_puis_confirmation(self, client, fabrique, ecrivain, mesanges):
        evenement = self._noter(client, ecrivain, type="plantation", culture="fève", quantite=4, unite="plants",
                                parcelle="Planche Est")
        donnees = _donnees(_appeler(client, ecrivain, "proposer_correction", {"champs": {"quantite": 6}}))
        assert donnees["proposition"] and any("4" in l and "6" in l for l in donnees["avant_apres"])
        _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": donnees["proposition"]}))
        with fabrique() as db:
            assert db.get(Evenement, evenement).quantite == 6

    def test_us292_correction_par_identifiant(self, client, ecrivain, mesanges):
        evenement = self._noter(client, ecrivain, type="recolte", culture="fève", quantite=1, unite="kg")
        donnees = _donnees(_appeler(client, ecrivain, "proposer_correction",
                                    {"evenement": evenement, "champs": {"quantite": 1.5}}))
        assert donnees["proposition"]

    def test_us292_correction_geste_ancien_refusee(self, client, ecrivain, mesanges):
        texte = _refus(_appeler(client, ecrivain, "proposer_correction", {"evenement": 1, "champs": {"quantite": 3}}))
        assert "récents" in texte

    def test_us292_correction_sans_geste_recent_est_une_question(self, client, ecrivain, mesanges):
        donnees = _donnees(_appeler(client, ecrivain, "proposer_correction", {"champs": {"quantite": 3}}))
        assert donnees["proposition"] is None and donnees["question"]

    def test_us292_correction_semis_a_suites_refusee(self, client, fabrique, jardin, ecrivain, mesanges):
        semis = self._noter(client, ecrivain, type="semis", culture="fève", quantite=12, unite="graines",
                            parcelle="Planche Est")
        with fabrique() as db:
            db.add(Evenement(type_action="mise_en_godet", culture="fève", nb_plants_godets=6, origine_graines_id=semis,
                             potager_id=jardin["mesanges"], date=datetime.combine(AUJOURD_HUI, datetime.min.time())))
            db.commit()
        texte = _refus(_appeler(client, ecrivain, "proposer_correction", {"evenement": semis, "champs": {"quantite": 10}}))
        assert "découlent" in texte

    def test_us292_redire_la_meme_valeur_est_refuse(self, client, ecrivain, mesanges):
        self._noter(client, ecrivain, type="plantation", culture="fève", quantite=4, unite="plants", parcelle="Planche Est")
        assert "rien ne change" in _refus(_appeler(client, ecrivain, "proposer_correction", {"champs": {"quantite": 4}}))

    @pytest.mark.parametrize("champs", [{}, {"couleur": "bleu"}, {"date": "2999-01-01"}, "3 rangs"])
    def test_us292_champs_invalides(self, client, ecrivain, mesanges, champs):
        _refus(_appeler(client, ecrivain, "proposer_correction", {"champs": champs}))


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — Traçabilité : canal mcp, nom du client, actions menées
# ═════════════════════════════════════════════════════════════════════════════
class TestCA12Tracabilite:

    def test_us292_le_geste_porte_le_client_et_le_canal(self, client, fabrique, ecrivain, mesanges):
        ident = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1.1, unite="kg"))["proposition"]
        evenement = _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))["enregistres"][0]["event_id"]
        with fabrique() as db:
            assert db.get(Evenement, evenement).texte_original.startswith("[Claude via MCP]")
            action = db.query(ActionMenee).filter_by(cible_type="evenement", cible_id=evenement).one()
            assert action.canal == "mcp"
            proposition = db.get(Proposition, ident)
            assert (proposition.canal, proposition.traite_canal, proposition.contenu["client"]) == ("mcp", "mcp", "Claude")

    def test_us292_le_geste_est_designable_depuis_les_autres_canaux(self, client, jardin, ecrivain, mesanges):
        from app.services.compagnon import actions_menees

        ident = _donnees(_proposer(client, ecrivain, type="recolte", culture="fève", quantite=1.1, unite="kg"))["proposition"]
        _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        recentes = actions_menees.recentes(_ctx(jardin))
        assert recentes and recentes[0].canal == "mcp"

    def test_us292_le_journal_mcp_ne_garde_pas_les_arguments(self, client, fabrique, ecrivain, mesanges):
        from database.models import McpAppel

        _proposer(client, ecrivain, type="observation", culture="fève", note="secret-de-jardin")
        with fabrique() as db:
            ligne = db.query(McpAppel).order_by(McpAppel.id.desc()).first()
            assert (ligne.outil, ligne.resultat) == ("proposer_geste", "ok")
            assert "secret" not in json.dumps({c.name: str(getattr(ligne, c.name)) for c in ligne.__table__.columns})


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin
# ═════════════════════════════════════════════════════════════════════════════
def test_us292_gherkin_encore_un_kilo_de_feves(client, fabrique, jardin, cumul_06, telegram):
    """Given 37 pieds actifs de fèves, 0,6 kg cumulés ; When « encore 1,1 kg de fèves » ;
    Then « pieds actifs : 37 (inchangé), cumul saison : 1,7 kg » ; When il confirme ; Then une seule
    récolte, canal mcp, et la carte « ✅ Confirmé » dans la PWA et dans Telegram."""
    jeton = _connecter(client, jardin, ecriture=True)["access_token"]
    donnees = _donnees(_proposer(client, jeton, type="recolte", culture="fève", quantite=1.1, unite="kg"))
    assert donnees["stock"] == "Pieds actifs : 37 (inchangé), cumul saison : 0,6 → 1,7 kg."

    _donnees(_appeler(client, jeton, "confirmer_proposition", {"proposition": donnees["proposition"]}))
    _refus(_appeler(client, jeton, "confirmer_proposition", {"proposition": donnees["proposition"]}))
    assert _nb(fabrique, Evenement, type_action="recolte", culture="fève") == 2  # 0,6 kg + 1,1 kg

    from app.services.compagnon import echange_pwa

    (carte,) = [c for c in echange_pwa.cartes_traitees(_ctx(jardin)) if c["id"] == donnees["proposition"]]
    assert carte["etat_dit"].startswith("✅ Confirmé")
    assert telegram.edites[-1][2].startswith("✅ Confirmé")
