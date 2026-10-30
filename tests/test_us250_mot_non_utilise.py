"""
tests/test_us250_mot_non_utilise.py
[US-250] Ne jamais ignorer en silence une partie de la phrase dictée.

Relevé du 22/10/2026 : « Mon tunnel est une pépinière chaud » était proposé, confirmé
puis exécuté en « pépinière, type non renseigné » — « chaud » avait été jeté sans un
mot. Le contrôle est fait à un seul endroit (`_appliquer_regle`), sur ce que le motif
d'une règle n'a pas consommé ; CA5 le rejoue sur CHAQUE règle qui écrit.

Hors périmètre, assumé : le contrôle ne porte que sur ce qui ÉCRIT (`confirmation`).
Une consultation n'écrit rien et rappelle la commande lue ; « quel temps fait-il ? »
ne mérite pas une question. Le test CA5 garde cette frontière explicite.
"""
import itertools
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CommandHandler

from app import bot as bot_module
from app.services import interpreteur_commandes as interp
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext

_CONTEXTE = TenantContext(user_id=1, potager_id=1, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures et utilitaires
# ═════════════════════════════════════════════════════════════════════════════
def _update(user_id: int = 42):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


def _clic(data: str, user_id: int = 42):
    update = MagicMock()
    update.effective_user.id = user_id
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
    handlers = {0: [CommandHandler("parcelle", handler)]} if handler is not None else {}
    ctx.application.handlers = handlers
    return ctx


def _boutons(update) -> list[tuple[str, str]]:
    """(libellé, callback_data) de chaque bouton du dernier message envoyé."""
    clavier = update.message.reply_text.await_args.kwargs["reply_markup"]
    return [(b.text, b.callback_data) for ligne in clavier.inline_keyboard for b in ligne]


def _texte_envoye(update) -> str:
    return str(update.message.reply_text.await_args.args[0])


def _messages_du_clic(update) -> list:
    """Les appels qui ont écrit au jardinier après un clic : l'étape suivante édite le
    message d'origine (`message.edit_text`), un refus édite la requête (`edit_message_text`)."""
    requete = update.callback_query
    return [*requete.message.edit_text.await_args_list, *requete.edit_message_text.await_args_list]


def _texte_du_clic(update) -> str:
    return "\n".join(str(appel.args[0]) if appel.args else "" for appel in _messages_du_clic(update))


def _boutons_du_clic(update) -> list[tuple[str, str]]:
    claviers = [a.kwargs.get("reply_markup") for a in _messages_du_clic(update)]
    clavier = next((k for k in reversed(claviers) if k is not None), None)
    if clavier is None:
        return []
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
    """Journal fidèle à `persister_journal` : sans `log_id`, une ligne neuve."""
    lignes = itertools.count(10)

    def _ecrire(ctx, commande, issue, log_id=None):
        return log_id if log_id is not None else next(lignes)

    with patch.object(interp, "persister_journal", side_effect=_ecrire) as faux:
        yield faux


def _issues(journal) -> list[tuple[str, object]]:
    return [(appel.args[2], appel.args[3] if len(appel.args) > 3 else None)
            for appel in journal.call_args_list]


def _lecture(phrase: str):
    resultat = interp.reconnaitre_par_regles(phrase)
    assert isinstance(resultat, interp.CommandeInterpretee), phrase
    return resultat


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — jamais présentée comme entièrement comprise
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1PasDeProposition:

    def test_us250_ca1_la_phrase_du_releve_pose_une_question(self):
        """[CA1] « chaud » n'est pas une valeur du type de pépinière que la règle sait lire seule."""
        commande = _lecture("Mon tunnel est une pépinière tiède")
        assert commande.precision is not None
        assert commande.precision.mot == "tiède"
        assert not commande.complete

    def test_us250_ca1_un_mot_parasite_apres_une_valeur_chiffree(self):
        """[CA1] Pas seulement les pépinières : « 5 rangs bidule » ne perd pas « bidule »."""
        commande = _lecture("la planche nord a 5 rangs bidule")
        assert commande.precision is not None and commande.precision.mot == "bidule"
        assert commande.valeurs["modification"] == "rangs=5"
        assert not commande.complete

    def test_us250_ca1_une_phrase_entierement_lue_reste_complete(self):
        """[CA1] Le contrôle ne s'ajoute pas à une phrase dont rien ne reste."""
        commande = _lecture("la planche nord a 5 rangs")
        assert commande.precision is None
        assert commande.complete

    def test_us250_ca1_le_mot_est_cite_tel_que_dit(self):
        """[CA2] Accents et casse du jardinier, pas la forme normalisée."""
        commande = _lecture("ma serre est une pépinière Tiède")
        assert commande.precision.mot == "Tiède"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une question courte, un bouton par valeur, « sans précision »
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Question:

    def test_us250_ca2_la_question_cite_le_mot_et_les_valeurs_connues(self):
        question = _lecture("ma serre est une pépinière tiède").precision.question()
        assert "*chaude*" in question and "*froide*" in question
        assert "tiède" in question
        assert "pour le type de pépinière" in question
        assert question.endswith("laquelle ?")

    def test_us250_ca2_sans_caracteristique_attendue_le_mot_est_seulement_signale(self):
        question = _lecture("la planche nord a 5 rangs bidule").precision.question()
        assert "bidule" in question and "*" not in question

    @pytest.mark.asyncio
    async def test_us250_ca2_un_bouton_par_valeur_sans_precision_et_annuler(self, journal):
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), _lecture("ma serre est une pépinière tiède"))
        ident = _en_attente().code

        assert _boutons(update) == [
            ("Chaude", f"interp:prec:0:{ident}"),
            ("Froide", f"interp:prec:1:{ident}"),
            ("Sans précision", f"interp:sans:{ident}"),
            ("❌ Annuler", f"interp:non:{ident}"),
        ]
        assert "tiède" in _texte_envoye(update)

    @pytest.mark.asyncio
    async def test_us250_ca2_sans_valeur_connue_le_bouton_dit_le_mot_ecarte(self, journal):
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), _lecture("la planche nord a 5 rangs bidule"))
        ident = _en_attente().code
        assert _boutons(update) == [
            ("Continuer sans « bidule »", f"interp:sans:{ident}"),
            ("❌ Annuler", f"interp:non:{ident}"),
        ]

    @pytest.mark.asyncio
    async def test_us250_ca2_les_callback_data_tiennent_dans_64_octets(self, journal):
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), _lecture("ma serre est une pépinière tiède"))
        assert all(len(donnee.encode()) <= 64 for _, donnee in _boutons(update))

    def test_us250_ca2_le_decodage_du_bouton_de_precision(self):
        assert bot_module._decoder_callback("interp:prec:1:a1b2c3") == ("prec", "1", "a1b2c3")
        assert bot_module._decoder_callback("interp:sans:a1b2c3") == ("sans", None, "a1b2c3")


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — un bouton produit la proposition habituelle ; rien n'est écrit avant
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3ChoixDuBouton:

    @pytest.mark.asyncio
    async def test_us250_ca3_scenario_gherkin_choisir_froide_puis_confirmer(self, journal, potager_au_clic):
        """[Gherkin] La question ne modifie rien ; le choix mène au récapitulatif ; la confirmation écrit."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _lecture("ma serre est une pépinière tiède"))
        ident = _en_attente().code
        handler.assert_not_awaited()

        choix = _clic(f"interp:prec:1:{ident}")
        await bot_module._interp_cb(choix, ctx)
        handler.assert_not_awaited()  # le choix ne confirme rien
        assert "froide" in _texte_du_clic(choix)
        assert [donnee for _, donnee in _boutons_du_clic(choix)] == [
            f"interp:ok:{ident}", f"interp:non:{ident}",
        ]
        assert _en_attente().commande.precision is None

        confirmation = _clic(f"interp:ok:{ident}")
        await bot_module._interp_cb(confirmation, ctx)
        handler.assert_awaited_once()
        assert ctx.args == ["modifier", "serre", "pepiniere=froide"]

    @pytest.mark.asyncio
    async def test_us250_ca3_sans_precision_garde_la_commande_lue(self, journal, potager_au_clic):
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _lecture("ma serre est une pépinière tiède"))
        ident = _en_attente().code

        clic = _clic(f"interp:sans:{ident}")
        await bot_module._interp_cb(clic, ctx)
        handler.assert_not_awaited()
        assert [donnee for _, donnee in _boutons_du_clic(clic)] == [
            f"interp:ok:{ident}", f"interp:non:{ident}",
        ]

        await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)
        assert ctx.args == ["modifier", "serre", "pepiniere=oui"]

    @pytest.mark.asyncio
    async def test_us250_ca3_annuler_n_ecrit_rien(self, journal, potager_au_clic):
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _lecture("ma serre est une pépinière tiède"))
        ident = _en_attente().code

        await bot_module._interp_cb(_clic(f"interp:non:{ident}"), ctx)
        handler.assert_not_awaited()
        assert _en_attente() is None

    @pytest.mark.asyncio
    async def test_us250_ca3_oui_ne_tranche_pas_la_question(self, journal):
        """[CA3] Une question en attente n'est pas « prête » : un « oui » tapé ne la confirme pas."""
        from app.services.compagnon import decisions

        await bot_module._interp_proposer(_update(), _ctx(), _lecture("ma serre est une pépinière tiède"))
        assert not decisions.est_prete(_en_attente().commande)

    @pytest.mark.asyncio
    async def test_us250_ca3_un_bouton_de_precision_sans_question_ne_fait_rien(self, journal, potager_au_clic):
        """Un clic sur « prec » d'une proposition qui n'a plus de question : refusé, rien n'est exécuté."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _lecture("la planche nord a 5 rangs"))
        ident = _en_attente().code

        clic = _clic(f"interp:prec:0:{ident}")
        await bot_module._interp_cb(clic, ctx)
        handler.assert_not_awaited()
        assert "invalides" in _texte_du_clic(clic)

    @pytest.mark.asyncio
    async def test_us250_ca3_le_nom_approximatif_se_tranche_avant_le_mot_non_compris(self, journal, potager_au_clic):
        """Le doute sur la parcelle passe d'abord ; la question du mot suit, sans être perdue."""
        ctx = _ctx(AsyncMock())
        commande = _lecture("ma sere est une pépinière tiède").avec_candidats("nom", ("Serre",))
        update = _update()
        await bot_module._interp_proposer(update, ctx, commande)
        ident = _en_attente().code
        assert [donnee for _, donnee in _boutons(update)] == [
            f"interp:cand:0:{ident}", f"interp:non:{ident}",
        ]

        clic = _clic(f"interp:cand:0:{ident}")
        await bot_module._interp_cb(clic, ctx)
        assert [donnee for _, donnee in _boutons_du_clic(clic)] == [
            f"interp:prec:0:{ident}", f"interp:prec:1:{ident}",
            f"interp:sans:{ident}", f"interp:non:{ident}",
        ]
        assert "tiède" in _texte_du_clic(clic)

    def test_us250_ca3_la_proposition_garde_sa_question_apres_un_redemarrage(self):
        """[US-259] La question vit en base avec la proposition : sérialisée, désérialisée, identique."""
        commande = _lecture("ma serre est une pépinière tiède")
        nature, donnees = svc_propositions.serialiser(commande)
        relue = svc_propositions.deserialiser(nature, donnees)
        assert relue.precision == commande.precision


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — la politesse et les liaisons ne déclenchent jamais la question
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4PolitesseSansPortee:

    @pytest.mark.parametrize("suite", [
        "stp", "svp", "merci", "merci beaucoup", "maintenant", "s'il te plaît",
        "s'il vous plaît", "tout de suite", "pour moi", "ok", "alors",
    ])
    def test_us250_ca4_un_mot_de_politesse_n_est_pas_un_mot_perdu(self, suite):
        commande = _lecture(f"mets la serre en pépinière {suite}")
        assert commande.precision is None
        assert commande.valeurs["modification"] == "pepiniere=oui"

    def test_us250_ca4_scenario_gherkin_mets_la_serre_en_pepiniere_stp(self):
        commande = _lecture("mets la serre en pépinière stp")
        assert commande.complete and commande.valeurs == {
            "nom": "serre", "modification": "pepiniere=oui",
        }

    def test_us250_ca4_en_tete_de_phrase(self):
        assert _lecture("alors la planche nord a 5 rangs").precision is None

    def test_us250_ca4_un_vrai_mot_a_cote_de_la_politesse_reste_signale(self):
        assert _lecture("la planche nord a 5 rangs bidule stp").precision.mot == "bidule"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le contrôle vaut pour TOUTES les règles qui écrivent
# ═════════════════════════════════════════════════════════════════════════════
#: Une phrase que CHAQUE règle qui écrit reconnaît seule (vérifié plus bas).
PHRASES_PAR_REGLE: dict[str, str] = {
    "parcelle_ajouter": "crée la parcelle PlancheTomate",
    "parcelle_renommer": "renomme planche nord en planche des courges",
    "parcelle_supprimer": "supprime la parcelle PlancheTomate",
    "parcelle_pepiniere": "la serre est une pépinière",
    "parcelle_pepiniere_chauffee": "ma mini-serre est chauffée",
    "parcelle_pepiniere_imperatif": "mets la serre en pépinière",
    "parcelle_longueur": "la planche centrale fait 12 mètres de long",
    "parcelle_longueur_rangs": "la planche nord a des rangs de 12 mètres",
    "parcelle_superficie": "la superficie de la planche sud est de 8 m2",
    "parcelle_superficie_verbe": "je veux que la planche sud fasse 8,5 m²",
    "parcelle_exposition": "l'exposition de la parcelle nord est plein sud",
    "parcelle_ensoleillement": "ensoleillement de la planche nord mi-ombre",
    "parcelle_abri": "la planche nord est sous serre",
    "parcelle_abri_imperatif": "mets la planche nord sous tunnel",
    "parcelle_paillage": "la planche nord est paillée",
    "parcelle_rangs": "la planche nord a 5 rangs",
    "association_saisir": "note une association entre la carotte et l'aneth",
    "culture_famille_inverse": "corrige la famille du pâtisson en cucurbitacée",
    "culture_famille": "le pâtisson est une cucurbitacée",
    "culture_delai_retour": "corrige le délai de retour des solanacées à 4 ans",
    "culture_exposition": "je veux que la courgette soit en plein soleil",
    "culture_exposition_imperatif": "mets la courgette en plein soleil",
    "culture_famille_imperatif": "mets le pâtisson en cucurbitacée",
    "culture_eau": "corrige le besoin en eau de la carotte en moyen",
    "culture_eau_verbe": "la courgette a un besoin en eau élevé",
    "culture_profondeur": "corrige la profondeur de semis de la carotte à 1 cm",
    "culture_profondeur_verbe": "la carotte se sème à 1 cm de profondeur",
    "culture_rusticite": "corrige la rusticité de la tomate à -2 degrés",
    "culture_rusticite_verbe": "la tomate gèle à -2 degrés",
    "calendrier_zone": "passe mon potager en zone méditerranéenne",
    "calendrier_fenetre": "corrige la période de semis en pépinière des tomates de février à avril",
    "calendrier_fenetre_plantation": "plantation des poireaux : juin-juillet",
    "calendrier_duree_semis_godet": "délai de repiquage en godet des choux : 10 à 15 jours",
    "calendrier_duree_semis_godet_verbe": "les tomates se mettent en godet 15 à 20 jours après le semis",
    "calendrier_duree_plantation_recolte": "délai de plantation à récolte des tomates : 60 jours",
    "calendrier_duree": "corrige le délai de levée des carottes à 14 jours",
    "calendrier_duree_levee_verbe": "les tomates lèvent en 7 à 14 jours",
    "bioagresseur_declarer": "déclare le bioagresseur teigne du poireau comme insecte",
    "bioagresseur_rattacher": "le mildiou attaque souvent la tomate",
    "bioagresseur_rattacher_imperatif": "rattache le mildiou à la tomate",
    "potager_changer": "passe sur le potager de la maison",
    "potager_lister": "je veux changer de potager",
    # Une consultation dont un mot perdu change la réponse (`controle_mots`) : la météo.
    "meteo": "quel temps fait-il ?",
}
PARASITE = "zorglub"


def _regles_controlees() -> list[interp.Regle]:
    """Les règles dont les mots non utilisés sont contrôlés : celles qui écrivent, et les
    consultations qui le demandent (`controle_mots`)."""
    return [
        r for r in interp._REGLES
        if interp.FORMES_PAR_CLE[(r.commande, r.sous_commande)].confirmation or r.controle_mots
    ]


def _appliquer(regle: interp.Regle, phrase: str):
    normalise, index = interp.normaliser(phrase)
    return interp._appliquer_regle(regle, phrase, normalise, index)


class TestCA5ToutesLesRegles:

    def test_us250_ca5_chaque_regle_controlee_a_sa_phrase(self):
        """Une règle ajoutée sans phrase d'exemple fait échouer ce test : elle ne passerait pas le contrôle."""
        assert {r.nom for r in _regles_controlees()} == set(PHRASES_PAR_REGLE)

    @pytest.mark.parametrize("nom", sorted(PHRASES_PAR_REGLE))
    def test_us250_ca5_la_phrase_d_exemple_est_lue_par_sa_regle_sans_reste(self, nom):
        regle = next(r for r in interp._REGLES if r.nom == nom)
        commande = _appliquer(regle, PHRASES_PAR_REGLE[nom])
        assert commande is not None, f"{nom} ne reconnaît pas sa propre phrase d'exemple"
        assert commande.precision is None and commande.corrections == ()

    @pytest.mark.parametrize("nom", sorted(PHRASES_PAR_REGLE))
    def test_us250_ca5_aucune_regle_ne_perd_un_mot_parasite_en_silence(self, nom):
        """Avec un mot de plus en fin de phrase, la règle ou bien décline, ou bien pose la
        question, ou bien garde le mot dans une valeur que le récapitulatif montre."""
        regle = next(r for r in interp._REGLES if r.nom == nom)
        commande = _appliquer(regle, f"{PHRASES_PAR_REGLE[nom]} {PARASITE}")
        if commande is None:
            return
        dit_dans_une_valeur = any(PARASITE in str(v).lower() for v in commande.valeurs.values())
        assert commande.precision is not None or dit_dans_une_valeur, (
            f"{nom} a perdu « {PARASITE} » sans le dire : {commande.valeurs}"
        )

    def test_us250_ca5_les_consultations_sont_exemptees_sauf_demande_de_la_regle(self):
        """Ce qui n'écrit pas n'est contrôlé que si la règle le demande (`controle_mots`) :
        « qu'ai-je fait hier ? » ou « corrige ma dernière saisie » laissent des mots sans
        que la réponse en change, une question y serait une fausse alerte."""
        exemptees = {r.nom for r in interp._REGLES} - set(PHRASES_PAR_REGLE)
        assert {"parcelle_lister", "historique", "corriger"} <= exemptees
        assert "meteo" not in exemptees
        assert _lecture("qu'ai-je fait hier ?").precision is None

    def test_us250_ca5_la_meteo_dit_ce_qu_elle_ne_sait_pas_lire(self):
        """Recette du 30/10/2026 : « quel temps fait-il à Lyon ? » donnait la météo du potager
        sans un mot sur Lyon. Le lieu est désormais lu (tests/test_meteo_autre_lieu.py) ; ce que la
        règle ne sait toujours pas lire — un lieu sans préposition — est dit, jamais perdu."""
        commande = _lecture("météo Lyon")
        assert commande.precision is not None and commande.precision.mot == "Lyon"
        question = commande.precision.question()
        assert "« Lyon »" in question and "pour une ville (« à Lyon »)" in question
        assert not commande.complete

    def test_us250_ca5_la_meteo_dit_qu_elle_ignore_le_jour(self):
        assert _lecture("quel temps fait-il demain ?").precision.mot == "demain"
        assert _lecture("quel temps fait-il à Lyon demain ?").precision.mot == "demain"

    @pytest.mark.parametrize("phrase", [
        "quel temps fait-il ?", "quel temps fait-il aujourd'hui ?", "quel temps va-t-il faire ?",
        "la météo", "la météo du jour", "météo aujourd'hui", "montre les prévisions",
        "il va pleuvoir ?", "quel temps fait-il stp", "quel temps fait-il à Lyon ?",
    ])
    def test_us250_ca5_la_meteo_ne_pose_pas_de_question_sans_mot_perdu(self, phrase):
        assert _lecture(phrase).precision is None

    @pytest.mark.asyncio
    async def test_us250_ca5_continuer_sans_le_jour_donne_la_meteo_du_jour(self, journal, potager_au_clic):
        """Le bouton « Continuer sans » exécute la consultation (rien à confirmer, rien d'écrit)."""
        handler = AsyncMock()
        ctx = MagicMock()
        ctx.user_data = {}
        ctx.args = []
        ctx.application.handlers = {0: [CommandHandler("meteo", handler)]}
        update = _update()
        await bot_module._interp_proposer(update, ctx, _lecture("quel temps fait-il demain ?"))
        ident = _en_attente().code
        assert [libelle for libelle, _ in _boutons(update)] == ["Continuer sans « demain »", "❌ Annuler"]
        assert "météo du jour" in _texte_envoye(update)
        handler.assert_not_awaited()

        await bot_module._interp_cb(_clic(f"interp:sans:{ident}"), ctx)
        handler.assert_awaited_once()

    def test_us250_ca5_la_note_survit_a_la_serialisation(self):
        commande = _lecture("quel temps fait-il demain ?")
        nature, donnees = svc_propositions.serialiser(commande)
        assert svc_propositions.deserialiser(nature, donnees).precision.note == commande.precision.note != ""

    def test_us250_ca5_le_controle_ne_depend_pas_de_la_phrase_complete(self):
        """Le mot parasite en TÊTE de phrase est contrôlé aussi, pas seulement en fin."""
        regle = next(r for r in interp._REGLES if r.nom == "parcelle_exposition")
        commande = _appliquer(regle, f"{PARASITE} l'exposition de la parcelle nord est plein sud")
        assert commande is not None and commande.precision.mot == PARASITE


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — le journal consigne « précision demandée » et le mot non compris
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Journal:

    @pytest.mark.asyncio
    async def test_us250_ca6_la_question_a_sa_ligne_precision_jamais_reecrite(self, journal, potager_au_clic):
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _lecture("ma serre est une pépinière tiède"))
        ident = _en_attente().code
        assert _issues(journal) == [(interp.ISSUE_PRECISION, None)]

        await bot_module._interp_cb(_clic(f"interp:prec:0:{ident}"), ctx)
        # Le choix ouvre une ligne neuve « proposee » ; celle de la question reste « precision ».
        assert _issues(journal)[1] == (interp.ISSUE_PROPOSEE, None)
        assert _en_attente().log_id == 11

        await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)
        assert _issues(journal)[-1] == (interp.ISSUE_CONFIRMEE, 11)

    @pytest.mark.asyncio
    async def test_us250_ca6_annuler_la_question_ne_reecrit_pas_sa_ligne(self, journal, potager_au_clic):
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _lecture("ma serre est une pépinière tiède"))
        ident = _en_attente().code
        await bot_module._interp_cb(_clic(f"interp:non:{ident}"), ctx)
        assert _issues(journal)[-1] == (interp.ISSUE_REFUSEE, None)

    @pytest.mark.asyncio
    async def test_us250_ca6_le_mot_non_compris_est_ecrit_au_journal(self, journal, caplog):
        with caplog.at_level(logging.INFO, logger="potager"):
            await bot_module._interp_proposer(
                _update(), _ctx(), _lecture("ma serre est une pépinière tiède"),
            )
        lignes = [r.getMessage() for r in caplog.records if "mot non compris" in r.getMessage()]
        assert len(lignes) == 1
        assert "'tiède'" in lignes[0] and "issue=precision" in lignes[0]
        assert "caracteristique=pepiniere" in lignes[0]
        assert "regle=parcelle_pepiniere" in lignes[0]

    def test_us250_ca6_la_decouverte_du_mot_est_aussi_journalisee_a_la_lecture(self, caplog):
        with caplog.at_level(logging.INFO, logger="potager"):
            _lecture("la planche nord a 5 rangs bidule")
        assert any("mot non utilisé 'bidule'" in r.getMessage() for r in caplog.records)

    def test_us250_ca6_l_issue_tient_dans_la_colonne_du_journal(self):
        """`routage_logs.issue_interpretation` est un String(16) : « precision » y tient."""
        from database.models import RoutageLog

        assert len(interp.ISSUE_PRECISION) <= RoutageLog.__table__.c.issue_interpretation.type.length


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — les phrases du relevé rejoignent le corpus
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Corpus:

    def test_us250_ca7_les_phrases_du_releve_sont_au_corpus_de_l_interpreteur(self):
        import csv
        from pathlib import Path

        corpus = Path(__file__).parent / "corpus" / "us172_commandes.csv"
        with corpus.open(encoding="utf-8") as fichier:
            phrases = {ligne["phrase"]: ligne["attendu"] for ligne in csv.DictReader(fichier)}
        for phrase in (
            "Mon tunnel est une pépinière chaud",
            "ma serre est une pépinière tiède",
            "mets la serre en pépinière stp",
        ):
            assert phrases.get(phrase) == "parcelle modifier", phrase
