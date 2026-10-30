"""
tests/test_us251_rapprochement_valeur.py
[US-251] Rapprocher une valeur mal dite du vocabulaire connu et proposer la correction.

« chaud » pour « chaude », « argileuse » pour « argileux » : une variante de genre, de
nombre, d'accent ou de casse n'est pas une valeur inconnue. Elle est rapprochée SANS
modèle, MONTRÉE au récapitulatif (« chaud → chaude ») et jamais écrite en silence.
Une valeur qui irait à deux valeurs, ou à aucune, suit la question d'US-250.
"""
import itertools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CommandHandler

from app import bot as bot_module
from app.services import interpreteur_commandes as interp
from app.services import vocabulaire_parcelle as vocabulaire
from app.services.agent.catalogue_outils import (
    CHAMP_TYPE_PEPINIERE,
    OUTIL_MODIFIER_PARCELLE,
    champs_fiche,
    outils_par_nom,
)
from app.services.agent.validation import ContexteValidation, valider_appel
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from llm.passerelle import AppelOutil

_CONTEXTE = TenantContext(user_id=1, potager_id=1, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Utilitaires (mêmes doubles que les tests de l'interprétation par le bot)
# ═════════════════════════════════════════════════════════════════════════════
def _update():
    update = MagicMock()
    update.effective_user.id = 42
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


def _clic(data: str):
    update = MagicMock()
    update.effective_user.id = 42
    update.message = None
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.message = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def _ctx(handler: AsyncMock | None = None):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.args = []
    ctx.application.handlers = {0: [CommandHandler("parcelle", handler)]} if handler is not None else {}
    return ctx


def _texte_envoye(update) -> str:
    return str(update.message.reply_text.await_args.args[0])


def _boutons(update) -> list[tuple[str, str]]:
    clavier = update.message.reply_text.await_args.kwargs["reply_markup"]
    return [(b.text, b.callback_data) for ligne in clavier.inline_keyboard for b in ligne]


def _en_attente():
    return svc_propositions.en_attente(_CONTEXTE.user_id, _CONTEXTE.potager_id)


@pytest.fixture(autouse=True)
def _decor():
    with patch.object(bot_module, "current_context", return_value=_CONTEXTE), \
         patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
        yield


@pytest.fixture
def potager_au_clic():
    with patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
         patch.object(bot_module, "_contexte_sur",
                      side_effect=lambda u, p: TenantContext(user_id=u, potager_id=p, role="owner")):
        yield


@pytest.fixture
def journal():
    lignes = itertools.count(10)

    def _ecrire(ctx, commande, issue, log_id=None):
        return log_id if log_id is not None else next(lignes)

    with patch.object(interp, "persister_journal", side_effect=_ecrire) as faux:
        yield faux


def _lecture(phrase: str):
    resultat = interp.reconnaitre_par_regles(phrase)
    assert isinstance(resultat, interp.CommandeInterpretee), phrase
    return resultat


def _valider(texte: str, arguments: dict):
    return valider_appel(
        AppelOutil(OUTIL_MODIFIER_PARCELLE, arguments),
        ContexteValidation(texte=texte, noms_parcelles=("Planche Nord",)),
    )


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — une seule liste de valeurs admises, pour les règles et pour l'agent
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1UneSeuleListe:

    def test_us251_ca1_les_listes_viennent_du_domaine(self):
        from utils.parcelles import ABRIS, DEFINITIONS_ENSOLEILLEMENT, TYPES_PEPINIERE, TYPES_SOL

        assert vocabulaire.valeurs_admises("pepiniere") == tuple(TYPES_PEPINIERE)
        assert vocabulaire.valeurs_admises("abri") == tuple(ABRIS)
        assert vocabulaire.valeurs_admises("ensoleillement") == tuple(DEFINITIONS_ENSOLEILLEMENT)
        assert vocabulaire.valeurs_admises("type_sol") == tuple(TYPES_SOL.values())

    def test_us251_ca1_chaque_caracteristique_a_un_libelle_et_une_liste(self):
        registre = vocabulaire.caracteristiques()
        assert {"pepiniere", "abri", "type_sol", "ensoleillement", "exposition"} <= set(registre)
        assert all(c.valeurs and c.libelle for c in registre.values())

    def test_us251_ca1_l_agent_recoit_les_memes_valeurs(self):
        """Les `enum` des outils de l'agent sont les listes du registre, pas des copies."""
        par_nom = {champ.nom: champ for champ in champs_fiche()}
        assert par_nom["type_sol"].vocabulaire == vocabulaire.valeurs_admises("type_sol")
        assert par_nom["abri"].vocabulaire == vocabulaire.valeurs_admises("abri")
        assert par_nom["ensoleillement"].vocabulaire == vocabulaire.valeurs_admises("ensoleillement")
        assert par_nom["exposition"].vocabulaire == vocabulaire.valeurs_admises("exposition")
        assert par_nom[CHAMP_TYPE_PEPINIERE].vocabulaire == vocabulaire.valeurs_admises("pepiniere")

    def test_us251_ca1_le_booleen_est_pepiniere_n_a_pas_de_liste(self):
        """Seul le CHAMP DU TYPE porte « chaude / froide » : le booléen reste oui / non."""
        par_nom = {champ.nom: champ for champ in champs_fiche()}
        assert par_nom["est_pepiniere"].vocabulaire == ()

    def test_us251_ca1_les_regles_lisent_la_meme_liste(self):
        """La règle de pépinière pose sa question avec les valeurs du registre."""
        assert _lecture("ma serre est une pépinière tiède").precision.options == \
            vocabulaire.valeurs_admises("pepiniere")

    def test_us251_ca1_une_valeur_ajoutee_au_domaine_est_connue_des_deux(self):
        """Ajouter une valeur au domaine l'ajoute pour les règles ET pour l'agent."""
        with patch("utils.parcelles.TYPES_PEPINIERE", ("chaude", "froide", "tiede")):
            assert vocabulaire.valeurs_admises("pepiniere") == ("chaude", "froide", "tiede")
            par_nom = {champ.nom: champ for champ in champs_fiche()}
            assert "tiede" in par_nom[CHAMP_TYPE_PEPINIERE].vocabulaire
            assert _lecture("ma serre est une pépinière tiède").precision is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — genre, nombre, accents, casse
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Rapprochement:

    @pytest.mark.parametrize("cle, dit, attendu", [
        ("pepiniere", "chaud", "chaude"),
        ("pepiniere", "froid", "froide"),
        ("pepiniere", "Chaudes", "chaude"),
        ("pepiniere", "FROIDS", "froide"),
        ("type_sol", "argileuse", "Argileux"),
        ("type_sol", "sableuse", "Sableux"),
        ("type_sol", "calcaires", "Calcaire"),
        ("abri", "serres", "serre"),
        ("abri", "tunnels", "tunnel"),
        ("ensoleillement", "ombres", "ombre"),
    ])
    def test_us251_ca2_la_variante_est_rapprochee(self, cle, dit, attendu):
        rapproche = vocabulaire.rapprocher_caracteristique(cle, dit)
        assert rapproche.statut == vocabulaire.CORRIGE
        assert rapproche.valeur == attendu

    @pytest.mark.parametrize("cle, dit, attendu", [
        ("type_sol", "humifere", "Humifère"),
        ("type_sol", "HUMIFÈRE", "Humifère"),
        ("ensoleillement", "mi ombre", "mi-ombre"),
        ("ensoleillement", "Plein-Soleil", "plein soleil"),
        ("abri", "Châssis", "chassis"),
        ("exposition", "sud", "Sud"),
    ])
    def test_us251_ca2_accents_casse_et_tirets_ne_sont_pas_une_correction(self, cle, dit, attendu):
        """Une valeur admise à l'accent, à la casse ou au tiret près est la valeur : rien à montrer."""
        rapproche = vocabulaire.rapprocher_caracteristique(cle, dit)
        assert (rapproche.statut, rapproche.valeur) == (vocabulaire.EXACT, attendu)

    def test_us251_ca2_la_phrase_du_releve(self):
        """[Gherkin] « Mon tunnel est une pépinière chaud » → pépinière chaude, corrigée et dite."""
        commande = _lecture("Mon tunnel est une pépinière chaud")
        assert commande.valeurs == {"nom": "tunnel", "modification": "pepiniere=chaude"}
        assert commande.corrections == (("chaud", "chaude"),)
        assert commande.precision is None and commande.complete

    def test_us251_ca2_froid(self):
        commande = _lecture("ma serre est une pépinière froid")
        assert commande.valeurs["modification"] == "pepiniere=froide"
        assert commande.corrections == (("froid", "froide"),)

    def test_us251_ca2_la_forme_imperative(self):
        commande = _lecture("mets la serre en pépinière chaud")
        assert commande.valeurs["modification"] == "pepiniere=chaude"
        assert commande.corrections == (("chaud", "chaude"),)

    def test_us251_ca2_une_valeur_dite_correctement_n_a_pas_de_correction(self):
        for phrase in ("mets la serre en pépinière chaude", "ma serre est une pépinière froide"):
            commande = _lecture(phrase)
            assert commande.corrections == () and commande.precision is None

    def test_us251_ca2_l_agent_rapproche_aussi(self):
        """[Agent] « argileuse » (le modèle recopie le mot dit) est rapprochée de « Argileux »."""
        verdict = _valider("le sol de la planche nord est argileuse",
                           {"parcelle": "Planche Nord", "type_sol": "argileuse"})
        assert verdict.commande.valeurs["modification"] == "type_sol=Argileux"
        assert verdict.commande.corrections == (("argileuse", "Argileux"),)

    def test_us251_ca2_l_agent_ne_corrige_pas_un_champ_retire(self):
        """Un champ que la phrase n'évoque pas est retiré : il n'a rien corrigé du tout."""
        verdict = _valider("la planche nord a 5 rangs",
                           {"parcelle": "Planche Nord", "nb_rangs": 5, "type_sol": "argileuse"})
        assert verdict.commande.corrections == ()
        assert "type_sol" in verdict.retires


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — le récapitulatif montre la correction ; refuser n'écrit rien
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Recapitulatif:

    def test_us251_ca3_le_recapitulatif_montre_chaud_vers_chaude(self):
        recap = interp.recapitulatif(_lecture("Mon tunnel est une pépinière chaud"))
        assert "chaud → chaude" in recap
        assert "pépinière chaude" in recap
        assert "`/parcelle modifier tunnel pepiniere=chaude`" in recap

    def test_us251_ca3_sans_correction_le_recapitulatif_ne_change_pas(self):
        recap = interp.recapitulatif(_lecture("Mon tunnel est une pépinière chaude"))
        assert "→" not in recap and "↪️" not in recap

    def test_us251_ca3_le_recapitulatif_de_l_agent_montre_aussi_la_correction(self):
        verdict = _valider("le sol de la planche nord est argileuse",
                           {"parcelle": "Planche Nord", "type_sol": "argileuse"})
        assert "argileuse → Argileux" in interp.recapitulatif(verdict.commande)

    @pytest.mark.asyncio
    async def test_us251_ca3_scenario_gherkin_proposer_puis_confirmer(self, journal, potager_au_clic):
        handler = AsyncMock()
        ctx = _ctx(handler)
        update = _update()
        await bot_module._interp_proposer(update, ctx, _lecture("Mon tunnel est une pépinière chaud"))
        ident = _en_attente().code

        assert "chaud → chaude" in _texte_envoye(update)
        assert [donnee for _, donnee in _boutons(update)] == [f"interp:ok:{ident}", f"interp:non:{ident}"]
        handler.assert_not_awaited()

        await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)
        handler.assert_awaited_once()
        assert ctx.args == ["modifier", "tunnel", "pepiniere=chaude"]

    @pytest.mark.asyncio
    async def test_us251_ca3_refuser_n_ecrit_rien(self, journal, potager_au_clic):
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _lecture("Mon tunnel est une pépinière chaud"))
        ident = _en_attente().code

        await bot_module._interp_cb(_clic(f"interp:non:{ident}"), ctx)
        handler.assert_not_awaited()
        assert _en_attente() is None

    def test_us251_ca3_la_correction_survit_a_un_redemarrage(self):
        """[US-259] Ce qui se confirme est ce qui a été montré, correction comprise."""
        commande = _lecture("Mon tunnel est une pépinière chaud")
        nature, donnees = svc_propositions.serialiser(commande)
        assert svc_propositions.deserialiser(nature, donnees).corrections == (("chaud", "chaude"),)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — jamais tranchée entre deux valeurs
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Ambigu:

    def test_us251_ca4_deux_valeurs_proches_ne_sont_pas_tranchees(self):
        rapproche = vocabulaire.rapprocher("chauds", ("chaud", "chaude"))
        assert rapproche.statut == vocabulaire.AMBIGU
        assert rapproche.valeur is None
        assert rapproche.candidats == ("chaud", "chaude")

    def test_us251_ca4_la_question_d_us250_est_posee_avec_les_deux(self):
        registre = {
            **vocabulaire.caracteristiques(),
            "pepiniere": vocabulaire.Caracteristique(
                "pepiniere", "type de pépinière", ("chaud", "chaude"), non_precisees=("oui",),
            ),
        }
        with patch.object(vocabulaire, "caracteristiques", return_value=registre):
            commande = _lecture("ma serre est une pépinière chauds")
        assert commande.precision.options == ("chaud", "chaude")
        assert commande.corrections == ()
        assert commande.valeurs["modification"] == "pepiniere=oui"

    @pytest.mark.asyncio
    async def test_us251_ca4_les_boutons_ne_proposent_que_les_deux(self, journal):
        registre = {
            **vocabulaire.caracteristiques(),
            "pepiniere": vocabulaire.Caracteristique(
                "pepiniere", "type de pépinière", ("chaud", "chaude"), non_precisees=("oui",),
            ),
        }
        with patch.object(vocabulaire, "caracteristiques", return_value=registre):
            commande = _lecture("ma serre est une pépinière chauds")
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), commande)
        assert [libelle for libelle, _ in _boutons(update)] == [
            "Chaud", "Chaude", "Sans précision", "❌ Annuler",
        ]

    def test_us251_ca4_un_choix_ecrit_la_valeur_choisie_sans_correction(self):
        """Le jardinier a tranché : la valeur est la sienne, il n'y a rien à « corriger »."""
        commande = _lecture("ma serre est une pépinière tiède").avec_choix(0)
        assert commande.valeurs["modification"] == "pepiniere=chaude"
        assert commande.corrections == () and commande.precision is None


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — sans rapprochement possible : la question, jamais une valeur devinée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5SansRapprochement:

    @pytest.mark.parametrize("dit", ["tiède", "tiede", "très chaud", "brûlant", "chaudasse"])
    def test_us251_ca5_aucune_valeur_devinee(self, dit):
        rapproche = vocabulaire.rapprocher_caracteristique("pepiniere", dit)
        assert rapproche.statut == vocabulaire.AUCUN and rapproche.valeur is None

    def test_us251_ca5_scenario_gherkin_ma_serre_est_une_pepiniere_tiede(self):
        commande = _lecture("ma serre est une pépinière tiède")
        assert commande.precision.options == ("chaude", "froide")
        assert commande.valeurs["modification"] == "pepiniere=oui"
        assert commande.corrections == ()

    def test_us251_ca5_un_mot_vide_ne_se_rapproche_de_rien(self):
        assert vocabulaire.rapprocher("", ("chaude", "froide")).statut == vocabulaire.AUCUN
        assert vocabulaire.rapprocher("  ", ("chaude", "froide")).statut == vocabulaire.AUCUN

    def test_us251_ca5_un_mot_sans_rapport_avec_la_caracteristique_reste_une_question(self):
        """« 5 rangs bidule » n'attend aucun type : la question ne propose aucune valeur."""
        assert _lecture("la planche nord a 5 rangs bidule").precision.options == ()


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — l'agent ne propose jamais une valeur hors liste
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Agent:

    def test_us251_ca6_le_schema_de_l_outil_fige_les_valeurs(self):
        propriete = outils_par_nom()[OUTIL_MODIFIER_PARCELLE].schema["function"]["parameters"][
            "properties"]["type_sol"]
        assert set(propriete["enum"]) >= set(vocabulaire.valeurs_admises("type_sol"))

    @pytest.mark.parametrize("cle, valeur, phrase", [
        ("type_sol", "boueux", "le sol de la planche nord est boueux"),
        ("abri", "cloche", "la planche nord est sous cloche"),
        ("ensoleillement", "soleil couchant", "l'ensoleillement de la planche nord est soleil couchant"),
    ])
    def test_us251_ca6_le_validateur_refuse_une_valeur_hors_liste(self, cle, valeur, phrase):
        verdict = _valider(phrase, {"parcelle": "Planche Nord", cle: valeur})
        assert verdict.commande is None
        assert "hors de la liste" in verdict.motif

    def test_us251_ca6_une_valeur_proche_de_deux_valeurs_est_refusee(self):
        """Le validateur ne tranche pas non plus : deux valeurs possibles, rejet."""
        registre = {
            **vocabulaire.caracteristiques(),
            "type_sol": vocabulaire.Caracteristique(
                "type_sol", "type de sol", ("Argileux", "Argileuse"),
            ),
        }
        with patch.object(vocabulaire, "caracteristiques", return_value=registre):
            verdict = _valider("le sol de la planche nord est argileuses",
                               {"parcelle": "Planche Nord", "type_sol": "argileuses"})
        assert verdict.commande is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — aucun appel au modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7SansModele:

    def test_us251_ca7_la_lecture_par_les_regles_ne_consomme_aucun_jeton(self):
        commande = _lecture("Mon tunnel est une pépinière chaud")
        assert commande.origine == interp.ORIGINE_REGLE
        assert commande.tokens_consommes == 0 and commande.outils == ()

    def test_us251_ca7_interpreter_ne_consulte_jamais_le_modele(self):
        with patch.object(interp, "_appeler_modele", side_effect=AssertionError("modèle appelé")), \
             patch.object(interp, "_mode_agent", side_effect=AssertionError("agent appelé")):
            resultat = interp.interpreter("Mon tunnel est une pépinière chaud", None)
        assert resultat.valeurs["modification"] == "pepiniere=chaude"
        assert resultat.corrections == (("chaud", "chaude"),)

    def test_us251_ca7_le_module_n_importe_aucune_passerelle(self):
        import app.services.vocabulaire_parcelle as module

        source = open(module.__file__, encoding="utf-8").read()
        assert "passerelle" not in source and "groq" not in source.lower()
