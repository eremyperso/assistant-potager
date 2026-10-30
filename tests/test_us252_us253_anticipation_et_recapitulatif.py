"""
tests/test_us252_us253_anticipation_et_recapitulatif.py
[US-252] Le récapitulatif dit ce qui a été compris, corrigé et supposé.
[US-253] Anticiper la conséquence ou la suite logique d'une commande.

Le récapitulatif montre la part de la phrase que le compagnon a interprétée à la place du
jardinier (nom rapproché, valeur corrigée, caractéristique laissée vide) ; l'anticipation
signale ce qu'une suppression emporte et propose l'étape qui manque — une information et
une proposition, jamais une action.
"""
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CommandHandler

from app import bot as bot_module
from app.services import anticipation_commande as anticipation
from app.services import interpreteur_commandes as interp
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from database.models import Evenement, Parcelle

_CONTEXTE = TenantContext(user_id=1, potager_id=1, role="owner")


def _lecture(phrase: str):
    resultat = interp.reconnaitre_par_regles(phrase)
    assert isinstance(resultat, interp.CommandeInterpretee), phrase
    return resultat


# ═════════════════════════════════════════════════════════════════════════════
# US-252 — rapproché, corrigé, supposé
# ═════════════════════════════════════════════════════════════════════════════
class TestUS252Recapitulatif:

    def test_us252_ca2_nom_rapproche_montre_avec_le_mot_dit(self):
        """Gherkin : « mon tunnel est une pépinière » → « tunnel → tunnel chauffé »."""
        dite = _lecture("mon tunnel est une pépinière").avec_candidats("nom", ("tunnel chauffé",))
        choisie = dite.avec(nom="tunnel chauffé")
        recap = interp.recapitulatif(choisie)
        assert "tunnel → tunnel chauffé" in recap
        assert choisie.mot_candidat is None  # le mot dit n'est gardé que le temps du choix

    def test_us252_ca3_caracteristique_vide_nommee_avec_la_facon_de_la_donner(self):
        recap = interp.recapitulatif(_lecture("mon tunnel est une pépinière"))
        assert "type de pépinière non précisé (chaude ou froide)" in recap
        assert "tunnel est une pépinière chaude" in recap

    def test_us252_ca4_rien_quand_tout_est_dit_tel_quel(self):
        recap = interp.recapitulatif(_lecture("la serre est une pépinière chaude"))
        assert "↪️" not in recap and "❔" not in recap

    def test_us252_ca4_une_ligne_par_element(self):
        dite = _lecture("mon tunnel est une pépinière").avec_candidats("nom", ("tunnel chauffé",))
        recap = interp.recapitulatif(dite.avec(nom="tunnel chauffé"))
        assert recap.count("↪️") == 1 and recap.count("❔") == 1

    def test_us252_ca2_un_nom_qui_ne_differe_que_par_la_casse_n_est_pas_montre(self):
        dite = _lecture("supprime la parcelle plantation").avec_candidats("nom", ("Plantation",))
        assert "↪️" not in interp.recapitulatif(dite.avec(nom="Plantation"))

    def test_us252_ca5_meme_presentation_pour_un_plan(self):
        etape = _lecture("mon tunnel est une pépinière").avec_candidats("nom", ("tunnel chauffé",))
        etape = etape.avec(nom="tunnel chauffé")
        plan = interp.Plan(etapes=(etape,))
        recap = interp.recapitulatif_plan(plan)
        assert "tunnel → tunnel chauffé" in recap
        assert "type de pépinière non précisé" in recap

    def test_us252_ca5_le_mot_dit_survit_a_la_serialisation(self):
        dite = _lecture("mon tunnel est une pépinière").avec_candidats("nom", ("tunnel chauffé",))
        _, donnees = svc_propositions.serialiser(dite)
        relue = svc_propositions._deserialiser_commande(donnees)
        assert relue.mot_candidat == "tunnel"
        assert "tunnel → tunnel chauffé" in interp.recapitulatif(relue.avec(nom="tunnel chauffé"))


# ═════════════════════════════════════════════════════════════════════════════
# US-253 — ce qui dépend de la parcelle (CA1)
# ═════════════════════════════════════════════════════════════════════════════
def _parcelle(db, nom, **champs):
    parcelle = Parcelle(
        nom=nom, nom_normalise=nom.lower().replace(" ", ""), ordre=1, actif=True, potager_id=1, **champs,
    )
    db.add(parcelle)
    db.commit()
    return parcelle


def _planter(db, parcelle, culture, quantite, unite="pieds"):
    db.add(Evenement(
        type_action="plantation", culture=culture, quantite=quantite, unite=unite,
        parcelle_id=parcelle.id, potager_id=1, date=datetime.datetime(2026, 5, 1),
    ))
    db.commit()


class TestUS253Avertissements:

    def test_us253_ca1_supprimer_signale_les_cultures_en_place(self, test_db):
        """Gherkin : « 12 pieds de tomate sont encore en place sur cette parcelle »."""
        plantation = _parcelle(test_db, "plantation")
        _planter(test_db, plantation, "tomate", 12)
        lignes = anticipation.avertissements(test_db, _CONTEXTE, _lecture("supprime la parcelle plantation"))
        assert lignes == ["⚠️ 12 pieds de tomate sont encore en place sur cette parcelle"]

    def test_us253_ca1_archiver_est_signale_comme_supprimer(self, test_db):
        plantation = _parcelle(test_db, "plantation")
        _planter(test_db, plantation, "tomate", 3)
        archivage = _lecture("la serre est une pépinière").avec(nom="plantation", modification="actif=non")
        assert anticipation.avertissements(test_db, _CONTEXTE, archivage)

    def test_us253_ca1_plusieurs_cultures_restent_sur_une_ligne(self, test_db):
        plantation = _parcelle(test_db, "plantation")
        for culture, quantite in (("tomate", 12), ("poivron", 6), ("basilic", 4), ("persil", 2), ("ciboulette", 1)):
            _planter(test_db, plantation, culture, quantite)
        lignes = anticipation.avertissements(test_db, _CONTEXTE, _lecture("supprime la parcelle plantation"))
        assert len(lignes) == 1
        assert "12 pieds de tomate, 6 pieds de poivron, 4 pieds de basilic et 2 autres" in lignes[0]

    def test_us253_ca1_rien_ne_depend_rien_n_est_dit(self, test_db):
        _parcelle(test_db, "plantation")
        assert anticipation.avertissements(test_db, _CONTEXTE, _lecture("supprime la parcelle plantation")) == []

    def test_us253_ca1_une_autre_parcelle_ne_compte_pas(self, test_db):
        _parcelle(test_db, "plantation")
        autre = _parcelle(test_db, "verger")
        _planter(test_db, autre, "pommier", 4)
        assert anticipation.avertissements(test_db, _CONTEXTE, _lecture("supprime la parcelle plantation")) == []

    def test_us253_ca1_une_autre_commande_n_a_pas_d_avertissement(self, test_db):
        plantation = _parcelle(test_db, "plantation")
        _planter(test_db, plantation, "tomate", 12)
        assert anticipation.avertissements(test_db, _CONTEXTE, _lecture("la plantation est une pépinière")) == []

    def test_us253_ca5_une_panne_de_lecture_ne_bloque_pas(self, test_db):
        with patch.object(anticipation.svc_plan, "get_occupation", side_effect=RuntimeError("base")):
            _parcelle(test_db, "plantation")
            assert anticipation.avertissements(test_db, _CONTEXTE, _lecture("supprime la parcelle plantation")) == []


# ═════════════════════════════════════════════════════════════════════════════
# US-253 — la suite proposée (CA2, CA3, CA4, CA6)
# ═════════════════════════════════════════════════════════════════════════════
class TestUS253Suite:

    def test_us253_ca2_pepiniere_sans_type_propose_chaude_ou_froide(self, test_db):
        """Gherkin : la serre devient pépinière sans type → « Chaude » ou « Froide »."""
        _parcelle(test_db, "serre", est_pepiniere=True)
        suite = anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("la serre est une pépinière"))
        assert suite is not None
        assert suite.precision.options == ("chaude", "froide")
        assert "serre" in suite.precision.question()
        assert not suite.complete  # rien ne s'exécute tant qu'un bouton n'est pas choisi

    def test_us253_ca3_le_choix_repasse_par_la_confirmation(self, test_db):
        _parcelle(test_db, "serre", est_pepiniere=True)
        suite = anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("la serre est une pépinière"))
        choisie = suite.avec_choix(0)
        assert choisie.complete and choisie.forme.confirmation
        assert choisie.valeurs["modification"] == "pepiniere=chaude"
        assert "pépinière chaude" in interp.recapitulatif(choisie)

    def test_us253_ca2_pas_de_suite_quand_le_type_est_donne(self, test_db):
        _parcelle(test_db, "serre", est_pepiniere=True, type_pepiniere="chaude")
        assert anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("la serre est une pépinière chaude")) is None

    def test_us253_ca2_pas_de_suite_si_la_commande_n_a_pas_ecrit(self, test_db):
        _parcelle(test_db, "serre")  # pas une pépinière : l'écriture n'a pas eu lieu
        assert anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("la serre est une pépinière")) is None

    def test_us253_ca2_pas_de_suite_pour_une_autre_commande(self, test_db):
        _parcelle(test_db, "serre", est_pepiniere=True)
        assert anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("supprime la parcelle serre")) is None

    def test_us253_ca5_une_panne_de_lecture_ne_casse_pas_une_commande_executee(self, test_db):
        with patch.object(anticipation, "_parcelle_de", side_effect=RuntimeError("base")):
            assert anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("la serre est une pépinière")) is None

    def test_us253_ca2_la_suite_survit_a_la_serialisation(self, test_db):
        _parcelle(test_db, "serre", est_pepiniere=True)
        suite = anticipation.suite_suggeree(test_db, _CONTEXTE, _lecture("la serre est une pépinière"))
        _, donnees = svc_propositions.serialiser(suite)
        relue = svc_propositions._deserialiser_commande(donnees)
        assert relue.precision.invite == suite.precision.invite


# ═════════════════════════════════════════════════════════════════════════════
# US-253 — côté bot : la suite s'affiche, « Plus tard » n'écrit rien (CA3, CA6)
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


def _ctx(handler):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.args = []
    ctx.application.handlers = {0: [CommandHandler("parcelle", handler)]}
    return ctx


@pytest.fixture
def decor():
    with patch.object(bot_module, "current_context", return_value=_CONTEXTE), \
         patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c), \
         patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
         patch.object(bot_module, "_contexte_sur",
                      side_effect=lambda u, p: TenantContext(user_id=u, potager_id=p, role="owner")), \
         patch.object(interp, "persister_journal", return_value=7):
        yield


def _suite(precision_invite=True):
    return anticipation.interpreteur.CommandeInterpretee(
        commande="parcelle", sous_commande="modifier",
        forme=interp.FORMES_PAR_CLE[("parcelle", "modifier")], valeurs={"nom": "serre"},
        origine=interp.ORIGINE_REGLE, confiance=1.0, regle=interp.REGLE_ANTICIPATION,
        precision=interp.PrecisionDemandee(
            mot="", caracteristique="pepiniere", libelle="type de pépinière",
            options=("chaude", "froide"), invite="*serre* est une pépinière sans type : ?",
        ),
    )


@pytest.mark.asyncio
async def test_us253_ca2_la_suite_est_proposee_par_boutons_sans_annuler(decor):
    update = _update()
    await bot_module._interp_proposer(update, _ctx(AsyncMock()), _suite())
    boutons = [
        b.text for ligne in update.message.reply_text.await_args.kwargs["reply_markup"].inline_keyboard
        for b in ligne
    ]
    assert boutons == ["Chaude", "Froide", "Plus tard"]


@pytest.mark.asyncio
async def test_us253_ca6_plus_tard_n_ecrit_rien_et_ne_bloque_rien(decor):
    handler = AsyncMock()
    update = _update()
    await bot_module._interp_proposer(update, _ctx(handler), _suite())
    proposition = svc_propositions.en_attente(_CONTEXTE.user_id, _CONTEXTE.potager_id)
    clic = _clic(f"interp:sans:0:{proposition.code}".replace(":0:", ":"))
    await bot_module._interp_cb(clic, _ctx(handler))
    handler.assert_not_awaited()
    assert svc_propositions.en_attente(_CONTEXTE.user_id, _CONTEXTE.potager_id) is None


@pytest.mark.asyncio
async def test_us253_ca3_un_bouton_ne_fait_que_poser_la_valeur(decor):
    handler = AsyncMock()
    update = _update()
    await bot_module._interp_proposer(update, _ctx(handler), _suite())
    proposition = svc_propositions.en_attente(_CONTEXTE.user_id, _CONTEXTE.potager_id)
    clic = _clic(f"interp:prec:0:{proposition.code}")
    await bot_module._interp_cb(clic, _ctx(handler))
    handler.assert_not_awaited()  # le récapitulatif est montré, rien n'est écrit
    texte = str(clic.callback_query.message.edit_text.await_args.args[0])
    assert "pépinière chaude" in texte
    assert svc_propositions.en_attente(_CONTEXTE.user_id, _CONTEXTE.potager_id) is not None


# ═════════════════════════════════════════════════════════════════════════════
# Relevé du 30/10/2026 : « créé moi une parcelle nord et une parcelle sud »
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("phrase", [
    "créé moi une parcelle nord et une parcelle sud",
    "crée une parcelle nord puis une parcelle sud",
    "crée une parcelle nord, une parcelle sud",
])
def test_us252_deux_parcelles_dans_une_phrase_vont_a_l_agent(phrase):
    """Une seconde cible introduite par « une » est une phrase composée : les règles ne la
    lisent pas (sinon la seconde parcelle devenait une partie du nom de la première)."""
    assert interp.phrase_pour_l_agent(phrase, None, interp.reconnaitre_par_regles(phrase))


def test_us252_une_parcelle_simple_reste_aux_regles():
    phrase = "crée une parcelle nord"
    assert not interp.phrase_pour_l_agent(phrase, None, interp.reconnaitre_par_regles(phrase))


# ═════════════════════════════════════════════════════════════════════════════
# Relevé du 30/10/2026 : « Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord… »
# ═════════════════════════════════════════════════════════════════════════════
from app.services.agent.projection import est_interrogative  # noqa: E402


@pytest.mark.parametrize("phrase", [
    "Bon, tu m'entends ? Alors, je veux que tu me crées une parcelle nord, puis une parcelle sud, "
    "puis une parcelle ouest, et enfin tu termines par la création d'une parcelle est.",
    "tu m'entends ? crée une parcelle nord",
])
def test_politesse_interrogative_en_tete_n_empeche_pas_la_demande(phrase):
    """Le « ? » d'une formule d'ouverture ne fait pas de la demande qui suit une question."""
    assert not est_interrogative(phrase)


@pytest.mark.parametrize("phrase", [
    "quelles cultures sont sur la parcelle nord ?",
    "est-ce que je peux supprimer la planche sud ?",
    "tu peux supprimer la planche sud ? oui",
])
def test_une_vraie_question_reste_une_question(phrase):
    assert est_interrogative(phrase)
