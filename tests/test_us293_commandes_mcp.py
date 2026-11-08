"""
tests/test_us293_commandes_mcp.py — Gérer parcelles et rappels depuis un assistant IA [US-293]
==============================================================================================
Un bloc par critère d'acceptance (CA1 à CA7) et le scénario Gherkin. Les outils sont appelés
par le vrai parcours MCP (jeton OAuth avec écriture, POST /mcp, `tools/call`).
"""
from __future__ import annotations

import pytest

from app.services.mcp import commandes as svc_commandes
from database.models import Parcelle, Proposition
from tests.test_us290_serveur_mcp import _appeler, _noms_outils, client, fabrique, jardin  # noqa: F401
from tests.test_us292_geste_assistant_ia import (  # noqa: F401 — fixtures partagées
    _donnees, _refus, ecrivain, sans_telegram, sessions,
)


@pytest.fixture
def parcelles(fabrique, jardin):
    """« Sud » (2 rangs) et « planche test » dans « Les Mésanges »."""
    with fabrique() as db:
        pid = jardin["mesanges"]
        db.add_all([
            Parcelle(nom="Sud", nom_normalise="sud", potager_id=pid, actif=True, nb_rangs=2),
            Parcelle(nom="planche test", nom_normalise="planchetest", potager_id=pid, actif=True),
        ])
        db.commit()
    return {"pid": pid}


def _proposer(client, jeton, **arguments) -> dict:
    return _appeler(client, jeton, "proposer_commande", arguments)


def _parcelle(fabrique, nom: str):
    with fabrique() as db:
        ligne = db.query(Parcelle).filter(Parcelle.nom == nom).first()
        return None if ligne is None else {"actif": ligne.actif, "nb_rangs": ligne.nb_rangs}


# ── CA1 : la liste vient du registre ─────────────────────────────────────────
class TestCA1Registre:
    def test_us293_formes_lues_du_registre(self):
        from app.services.agent.executeurs import EXECUTEURS

        proposables = {f.cle for f in svc_commandes.formes_proposables()}
        assert proposables == set(EXECUTEURS)
        assert ("parcelle", "supprimer") not in proposables

    def test_us293_une_forme_ajoutee_au_registre_devient_proposable(self, monkeypatch):
        from app.services.agent import executeurs
        from app.services.menu_commandes import FORMES_DICTABLES

        forme = next(f for f in FORMES_DICTABLES if f.cle == ("parcelle", "renommer"))
        monkeypatch.setitem(executeurs.EXECUTEURS, forme.cle, lambda *a: "ok")
        assert forme in svc_commandes.formes_proposables()

    def test_us293_proposer_modifier_une_parcelle(self, client, ecrivain, parcelles, fabrique):
        donnees = _donnees(_proposer(client, ecrivain, commande="parcelle modifier",
                                     arguments={"nom": "Sud", "nb_rangs": 3}))
        assert donnees["proposition"] and donnees["etat"] == "en_attente"
        assert _parcelle(fabrique, "Sud")["nb_rangs"] == 2  # rien n'est écrit

    def test_us293_proposer_creer_une_parcelle(self, client, ecrivain, parcelles):
        donnees = _donnees(_proposer(client, ecrivain, commande="/parcelle ajouter", arguments={"nom": "Nord"}))
        assert donnees["recapitulatif"] == ["Nouvelle parcelle « Nord »"]


# ── CA2 : sans exécuteur → Telegram ──────────────────────────────────────────
class TestCA2SansExecuteur:
    def test_us293_forme_sans_executeur_refusee_avec_la_commande(self, client, ecrivain, parcelles):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle renommer",
                                 arguments={"ancien": "Sud", "nouveau": "Plein sud"}))
        assert "Telegram" in texte and "/parcelle renommer Sud Plein sud" in texte

    def test_us293_commande_inconnue(self, client, ecrivain, parcelles):
        texte = _refus(_proposer(client, ecrivain, commande="potager exploser"))
        assert "inconnue" in texte and "parcelle modifier" in texte


# ── CA3 : jamais de destruction ──────────────────────────────────────────────
class TestCA3Destruction:
    def test_us293_suppression_jamais_proposee(self, client, ecrivain, parcelles, fabrique):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle supprimer", arguments={"nom": "planche test"}))
        assert "ouvrir_dans_l_application" in texte
        assert _parcelle(fabrique, "planche test") is not None
        with fabrique() as db:
            assert db.query(Proposition).count() == 0

    @pytest.mark.parametrize("valeur", ["non", False, "false"])
    def test_us293_desactivation_jamais_proposee(self, client, ecrivain, parcelles, valeur):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle modifier",
                                 arguments={"nom": "Sud", "actif": valeur}))
        assert "hors service" in texte

    def test_us293_desactivation_par_modification_texte(self, client, ecrivain, parcelles):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle modifier",
                                 arguments={"nom": "Sud", "modification": "actif=non"}))
        assert "ouvrir_dans_l_application" in texte

    def test_us293_ouvrir_rend_un_lien_profond_sans_rien_executer(self, client, ecrivain, parcelles, fabrique, jardin):
        donnees = _donnees(_appeler(client, ecrivain, "ouvrir_dans_l_application",
                                    {"action": "supprimer_parcelle", "parcelle": "planche test"}))
        assert "vue=plan-vue" in donnees["lien"] and "parcelle=planche%20test" in donnees["lien"]
        assert f"potager={jardin['mesanges']}" in donnees["lien"]
        assert "Rien n'a été fait" in donnees["texte"]
        assert _parcelle(fabrique, "planche test") is not None

    @pytest.mark.parametrize("action,vue", [("annuler_geste", "journal"), ("supprimer_potager", "bord")])
    def test_us293_ouvrir_autres_actions(self, client, ecrivain, parcelles, action, vue):
        assert f"vue={vue}" in _donnees(_appeler(client, ecrivain, "ouvrir_dans_l_application", {"action": action}))["lien"]

    def test_us293_ouvrir_cartes_en_attente(self, client, ecrivain, parcelles):
        lien = _donnees(_appeler(client, ecrivain, "ouvrir_dans_l_application", {"action": "voir_cartes_en_attente"}))["lien"]
        assert "compagnon=ouvrir" in lien

    def test_us293_ouvrir_parcelle_inconnue_ou_absente(self, client, ecrivain, parcelles):
        assert "introuvable" in _refus(_appeler(client, ecrivain, "ouvrir_dans_l_application",
                                                {"action": "supprimer_parcelle", "parcelle": "fantôme"}))
        assert "parcelle" in _refus(_appeler(client, ecrivain, "ouvrir_dans_l_application",
                                             {"action": "supprimer_parcelle"})).lower()

    def test_us293_aucun_outil_destructeur_enregistre(self):
        from app.services.mcp.serveur import REGISTRE

        assert not [o.nom for o in REGISTRE.values() if o.destructeur]


# ── CA4 : membres, invitations, rôles, BYOK, compte ──────────────────────────
class TestCA4Perimetre:
    def test_us293_aucun_outil_pour_membres_roles_cle_compte(self, client, ecrivain):
        interdits = ("membre", "invit", "role", "rôle", "byok", "cle", "clé", "compte", "mot_de_passe", "inviter")
        for nom in _noms_outils(client, ecrivain):
            assert not any(mot in nom for mot in interdits), nom

    def test_us293_les_actions_ouvrables_n_incluent_pas_ces_sujets(self):
        for action in svc_commandes.ACTIONS_DANS_L_APPLICATION:
            assert not any(m in action for m in ("membre", "invit", "role", "byok", "compte"))


# ── CA5 : avant → après, confirmation d'US-292 ───────────────────────────────
class TestCA5Recapitulatif:
    def test_us293_avant_apres(self, client, ecrivain, parcelles):
        donnees = _donnees(_proposer(client, ecrivain, commande="parcelle modifier",
                                     arguments={"nom": "Sud", "nb_rangs": 3}))
        assert donnees["recapitulatif"] == ["Sud : 2 rangs → 3 rangs"]

    def test_us293_confirmer_ecrit_une_fois(self, client, ecrivain, parcelles, fabrique):
        ident = _donnees(_proposer(client, ecrivain, commande="parcelle modifier",
                                   arguments={"nom": "Sud", "nb_rangs": 3}))["proposition"]
        resultat = _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident}))
        assert resultat["erreur"] is None and _parcelle(fabrique, "Sud")["nb_rangs"] == 3
        with fabrique() as db:  # une seconde confirmation ne réécrit rien
            db.query(Parcelle).filter(Parcelle.nom == "Sud").update({"nb_rangs": 9})
            db.commit()
        _appeler(client, ecrivain, "confirmer_proposition", {"proposition": ident})
        assert _parcelle(fabrique, "Sud")["nb_rangs"] == 9

    def test_us293_abandonner_n_ecrit_rien(self, client, ecrivain, parcelles, fabrique):
        ident = _donnees(_proposer(client, ecrivain, commande="parcelle modifier",
                                   arguments={"nom": "Sud", "nb_rangs": 3}))["proposition"]
        _donnees(_appeler(client, ecrivain, "abandonner_proposition", {"proposition": ident}))
        assert _parcelle(fabrique, "Sud")["nb_rangs"] == 2


# ── CA6 : plan étape par étape ───────────────────────────────────────────────
class TestCA6Plan:
    def test_us293_plan_creation_puis_modification(self, client, ecrivain, parcelles, fabrique):
        donnees = _donnees(_proposer(client, ecrivain, plan=[
            {"commande": "parcelle ajouter", "arguments": {"nom": "Nord"}},
            {"commande": "parcelle modifier", "arguments": {"nom": "Nord", "nb_rangs": 4}},
        ]))
        assert len(donnees["etapes"]) == 2
        resultat = _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": donnees["proposition"]}))
        assert resultat["erreur"] is None and resultat["texte"].count("✅") == 2
        assert _parcelle(fabrique, "Nord")["nb_rangs"] == 4

    def test_us293_commande_et_plan_exclusifs(self, client, ecrivain, parcelles):
        assert "OU" in _refus(_proposer(client, ecrivain, commande="parcelle ajouter", plan=[{"commande": "x"}]))

    def test_us293_plan_arret_a_la_premiere_en_echec(self, client, ecrivain, parcelles, fabrique):
        """Compte rendu ✅ ❌ ⏭ d'US-237 : « planche test » disparaît entre la proposition et la confirmation."""
        donnees = _donnees(_proposer(client, ecrivain, plan=[
            {"commande": "parcelle modifier", "arguments": {"nom": "Sud", "nb_rangs": 3}},
            {"commande": "parcelle modifier", "arguments": {"nom": "planche test", "nb_rangs": 4}},
            {"commande": "parcelle modifier", "arguments": {"nom": "Sud", "nb_rangs": 5}},
        ]))
        with fabrique() as db:
            db.query(Parcelle).filter(Parcelle.nom == "planche test").delete()
            db.commit()
        resultat = _donnees(_appeler(client, ecrivain, "confirmer_proposition", {"proposition": donnees["proposition"]}))
        assert resultat["erreur"] and "✅" in resultat["texte"] and "❌" in resultat["texte"] and "⏭" in resultat["texte"]
        assert _parcelle(fabrique, "Sud")["nb_rangs"] == 3  # la 3e étape n'a pas tourné


# ── CA7 : refus rendu avec sa raison ─────────────────────────────────────────
class TestCA7Refus:
    def test_us293_parcelle_disparue(self, client, ecrivain, parcelles, fabrique):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle modifier",
                                 arguments={"nom": "Fantôme", "nb_rangs": 3}))
        assert "rien n'est proposé" in texte and "Fantôme" in texte and "Sud" in texte
        with fabrique() as db:
            assert db.query(Proposition).count() == 0

    def test_us293_nom_deja_pris(self, client, ecrivain, parcelles, fabrique):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle ajouter", arguments={"nom": "Sud"}))
        assert "existe déjà" in texte and "Rien n'est proposé" in texte
        with fabrique() as db:
            assert db.query(Proposition).count() == 0

    def test_us293_champ_inconnu(self, client, ecrivain, parcelles):
        texte = _refus(_proposer(client, ecrivain, commande="parcelle modifier",
                                 arguments={"nom": "Sud", "couleur": "bleu"}))
        assert "Rien n'est proposé" in texte

    def test_us293_lecteur_ne_propose_pas(self, client, jardin):
        from tests.test_us290_serveur_mcp import _connecter

        jeton = _connecter(client, jardin, ecriture=False, potagers=[jardin["mesanges"]])["access_token"]
        assert "proposer_commande" not in _noms_outils(client, jeton)


# ── Scénario Gherkin ─────────────────────────────────────────────────────────
def test_us293_gherkin(client, ecrivain, parcelles, fabrique):
    # « supprime la planche test » : aucun outil d'écriture n'exécute, un lien est rendu
    assert "ouvrir_dans_l_application" in _refus(
        _proposer(client, ecrivain, commande="parcelle supprimer", arguments={"nom": "planche test"}))
    lien = _donnees(_appeler(client, ecrivain, "ouvrir_dans_l_application",
                             {"action": "supprimer_parcelle", "parcelle": "planche test"}))["lien"]
    assert "vue=plan-vue" in lien and _parcelle(fabrique, "planche test") is not None
    # « passe la sud à 3 rangs » : proposer_commande présente « Sud : 2 rangs → 3 rangs »
    donnees = _donnees(_proposer(client, ecrivain, commande="parcelle modifier",
                                 arguments={"nom": "Sud", "nb_rangs": 3}))
    assert donnees["recapitulatif"] == ["Sud : 2 rangs → 3 rangs"]
