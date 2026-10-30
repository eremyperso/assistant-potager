"""
tests/test_us234_confirmation_liee_proposition.py
[US-234] Lier la confirmation d'une commande dictée à la proposition qu'elle valide.

Couverture des critères d'acceptance CA1 → CA7 + le scénario Gherkin. Le
correctif touche `app/bot/interpretation.py` ; les tests d'US-172 qui couvrent
le délai d'expiration, les noms voisins et la complétion (CA6) restent dans
`test_us172_interpreteur_commandes.py` et sont rejoués à chaque livraison.

Un point à lire pour ce qu'il est : le jardinier « au moment du clic » est lu
en base par `_jardinier_au_clic` (un callback ne passe pas par le garde de
liaison, donc `current_context()` y vaut le contexte par défaut), et son rôle
sur le potager de la proposition par `_contexte_sur`. Ces tests les remplacent
par des doubles ; leur lecture réelle est couverte au niveau des services.

[US-259] La proposition en attente est lue en base (`propositions.en_attente`),
plus dans `_INTERP_PENDING` ; et CA3 suit désormais CA4 d'US-259 : une proposition
s'exécute dans SON potager, quel que soit le potager actif au moment du clic.
"""
import itertools
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CommandHandler

from app import bot as bot_module
from app.services import interpreteur_commandes as interp
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from database.models import Proposition

_CONTEXTE_POTAGER_1 = TenantContext(user_id=1, potager_id=1, role="owner")


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


def _texte_du_clic(update) -> str:
    return "\n".join(
        str(appel.args[0]) if appel.args else ""
        for appel in update.callback_query.edit_message_text.await_args_list
    )


def _boutons(update) -> list[str]:
    """`callback_data` de tous les boutons du dernier message envoyé."""
    clavier = update.message.reply_text.await_args.kwargs["reply_markup"]
    return [b.callback_data for ligne in clavier.inline_keyboard for b in ligne]


def _suppression():
    return interp.reconnaitre_par_regles("supprime la parcelle test")


def _creation():
    return interp.reconnaitre_par_regles("crée la parcelle carré nord")


def _en_attente(potager_id: int = 1):
    """[US-259] La proposition qui attend le jardinier 1 dans ce potager, lue en base."""
    return svc_propositions.en_attente(_CONTEXTE_POTAGER_1.user_id, potager_id)


@pytest.fixture(autouse=True)
def _decor():
    """Contexte du potager 1 à la proposition ; les noms de parcelle ne sont
    pas résolus en base (ce n'est pas l'objet de ces tests)."""
    with patch.object(bot_module, "current_context", return_value=_CONTEXTE_POTAGER_1), \
         patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
        yield


def _sur(user_id, potager_id):
    return TenantContext(user_id=user_id, potager_id=potager_id, role="owner")


@pytest.fixture
def potager_au_clic():
    """Le jardinier 1 clique ; il est membre du potager de la proposition."""
    with patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
         patch.object(bot_module, "_contexte_sur", side_effect=_sur) as faux:
        yield faux


@pytest.fixture
def journal():
    """Journal des interprétations, fidèle à `persister_journal` : une écriture
    SANS `log_id` crée une ligne (10, 11…), une écriture AVEC `log_id` complète
    cette ligne et rend le même identifiant."""
    lignes = itertools.count(10)

    def _ecrire(ctx, commande, issue, log_id=None):
        return log_id if log_id is not None else next(lignes)

    with patch.object(interp, "persister_journal", side_effect=_ecrire) as faux:
        yield faux


def _vieillir(code: str) -> None:
    """[US-259 / CA5] La demi-heure de la proposition est passée."""
    with svc_propositions.session_sur(1) as db:
        db.query(Proposition).filter(Proposition.code == code).update(
            {"expire_le": datetime.utcnow() - timedelta(seconds=1)}, synchronize_session=False)
        db.commit()


def _issues(journal) -> list[tuple[str, object]]:
    """(issue, log_id) de chaque écriture du journal, dans l'ordre."""
    return [(appel.args[2], appel.args[3] if len(appel.args) > 3 else None)
            for appel in journal.call_args_list]


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — un identifiant court, repris par tous les boutons
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1IdentifiantDeProposition:

    @pytest.mark.asyncio
    async def test_us234_ca1_confirmer_et_annuler_portent_l_identifiant(self, journal):
        """[CA1] Les deux boutons du récapitulatif nomment leur proposition."""
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), _suppression())

        ident = _en_attente().code
        assert ident
        assert _boutons(update) == [f"interp:ok:{ident}", f"interp:non:{ident}"]

    @pytest.mark.asyncio
    async def test_us234_ca1_l_identifiant_tient_dans_callback_data(self, journal):
        """[CA1] Telegram borne `callback_data` à 64 octets : « court » se vérifie."""
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), _suppression())
        assert all(len(b.encode()) <= 64 for b in _boutons(update))

    @pytest.mark.asyncio
    async def test_us234_ca1_les_noms_voisins_portent_l_identifiant(self, journal):
        """[CA1] Choisir un nom voisin s'adresse à SA proposition."""
        commande = _suppression().avec_candidats("nom", ("Test Nord",))
        update = _update()
        with patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
            await bot_module._interp_proposer(update, _ctx(), commande)

        ident = _en_attente().code
        assert _boutons(update) == [f"interp:cand:0:{ident}", f"interp:non:{ident}"]

    @pytest.mark.asyncio
    async def test_us234_ca1_les_valeurs_a_choisir_portent_l_identifiant(self, journal):
        """[CA1] Choisir une valeur de vocabulaire fermé s'adresse à SA proposition."""
        commande = interp.reconnaitre_par_regles("note une association entre la carotte et l'aneth")
        update = _update()
        await bot_module._interp_proposer(update, _ctx(), commande)

        ident = _en_attente().code
        boutons = _boutons(update)
        assert boutons[-1] == f"interp:non:{ident}"
        assert boutons[:-1] and all(
            b.startswith("interp:val:") and b.endswith(f":{ident}") for b in boutons[:-1]
        )

    @pytest.mark.asyncio
    async def test_us234_ca1_deux_propositions_successives_n_ont_pas_le_meme_identifiant(self, journal):
        """[CA1] Sans cela, le bouton de la première parlerait de la seconde."""
        await bot_module._interp_proposer(_update(), _ctx(), _suppression())
        premier = _en_attente().code
        await bot_module._interp_proposer(_update(), _ctx(), _creation())
        assert _en_attente().code != premier

    def test_us234_ca1_le_decodage_des_boutons(self):
        """[CA1] `interp:<action>[:<rang>]:<id>` — et un ancien bouton sans id."""
        d = bot_module._decoder_callback
        assert d("interp:ok:a1b2c3") == ("ok", None, "a1b2c3")
        assert d("interp:non:a1b2c3") == ("non", None, "a1b2c3")
        assert d("interp:cand:2:a1b2c3") == ("cand", "2", "a1b2c3")
        assert d("interp:val:0:a1b2c3") == ("val", "0", "a1b2c3")
        # Boutons d'avant US-234 : pas d'identifiant, donc jamais reconnus.
        assert d("interp:ok") == ("ok", None, None)
        assert d("interp:non") == ("non", None, None)
        assert d("interp:cand:1") == ("cand", "1", None)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — un bouton périmé n'exécute rien (+ scénario Gherkin)
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2BoutonPerime:

    @pytest.mark.asyncio
    async def test_us234_gherkin_l_ancien_bouton_n_execute_rien(self, journal, potager_au_clic):
        """[Gherkin] « supprime test » proposé, puis « crée carré nord » proposé :
        « Confirmer » sous la première ne fait rien, la seconde reste confirmable."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        id_suppression = _en_attente().code
        creation = _creation()
        await bot_module._interp_proposer(_update(), ctx, creation)
        id_creation = _en_attente().code

        ancien = _clic(f"interp:ok:{id_suppression}")
        await bot_module._interp_cb(ancien, ctx)

        handler.assert_not_awaited()
        assert "Demande expirée, rien n'a été fait" in _texte_du_clic(ancien)
        # La seconde proposition est intacte…
        assert _en_attente().code == id_creation

        # …et c'est seulement SA confirmation qui crée la parcelle.
        await bot_module._interp_cb(_clic(f"interp:ok:{id_creation}"), ctx)
        handler.assert_awaited_once()
        assert ctx.args == list(creation.args)

    @pytest.mark.asyncio
    async def test_us234_ca2_un_bouton_sans_identifiant_est_refuse(self, journal, potager_au_clic):
        """[CA2] Un message envoyé avant US-234 ne dit pas à quelle proposition il répond."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        clic = _clic("interp:ok")
        await bot_module._interp_cb(clic, ctx)

        handler.assert_not_awaited()
        assert "Demande expirée, rien n'a été fait" in _texte_du_clic(clic)
        assert _en_attente().code == ident

    @pytest.mark.asyncio
    async def test_us234_ca2_un_ancien_annuler_n_annule_pas_la_proposition_en_cours(self, journal, potager_au_clic):
        """[CA2] « Annuler » sous un ancien message ne retire pas la demande actuelle."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ancien_id = _en_attente().code
        await bot_module._interp_proposer(_update(), ctx, _creation())
        courant = _en_attente().code

        clic = _clic(f"interp:non:{ancien_id}")
        await bot_module._interp_cb(clic, ctx)

        assert "Demande expirée, rien n'a été fait" in _texte_du_clic(clic)
        assert _en_attente().code == courant

    @pytest.mark.asyncio
    async def test_us234_ca2_un_ancien_choix_de_nom_ne_modifie_pas_la_proposition_en_cours(self, journal, potager_au_clic):
        """[CA2] Choisir un voisin sous un vieux message ne réécrit pas la demande actuelle."""
        ctx = _ctx(AsyncMock())
        proposee = _suppression().avec_candidats("nom", ("Test Nord",))
        await bot_module._interp_proposer(_update(), ctx, proposee)
        ancien_id = _en_attente().code
        courante = _creation()
        await bot_module._interp_proposer(_update(), ctx, courante)

        await bot_module._interp_cb(_clic(f"interp:cand:0:{ancien_id}"), ctx)

        assert _en_attente().commande == courante

    @pytest.mark.asyncio
    async def test_us234_ca2_aucune_proposition_en_cours_expire_aussi(self, potager_au_clic):
        """[CA2] Bouton orphelin (redémarrage du bot, proposition déjà traitée)."""
        handler = AsyncMock()
        clic = _clic("interp:ok:a1b2c3")
        await bot_module._interp_cb(clic, _ctx(handler))

        handler.assert_not_awaited()
        assert "Demande expirée, rien n'a été fait" in _texte_du_clic(clic)

    @pytest.mark.asyncio
    async def test_us234_ca2_un_bouton_perime_ne_touche_pas_au_mode_de_completion(self, journal, potager_au_clic):
        """[CA2] Le jardinier en train de répondre à une question n'en est pas sorti."""
        ctx = _ctx(AsyncMock())
        commande = interp.reconnaitre_par_regles("note une association entre la carotte et l'aneth")
        await bot_module._interp_proposer(_update(), ctx, commande)
        assert ctx.user_data["mode"] == bot_module._INTERP_MODE_COMPLETION

        await bot_module._interp_cb(_clic("interp:ok:ancien"), ctx)

        assert ctx.user_data["mode"] == bot_module._INTERP_MODE_COMPLETION


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — le potager de la proposition, pas celui du moment du clic
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3PotagerRetenu:

    @pytest.mark.asyncio
    async def test_us234_ca3_la_proposition_retient_le_potager_actif(self, journal):
        """[CA3] Le potager est lu au moment de la proposition."""
        autre = TenantContext(user_id=1, potager_id=7, role="owner")
        with patch.object(bot_module, "current_context", return_value=autre):
            await bot_module._interp_proposer(_update(), _ctx(), _suppression())
        assert _en_attente(7).potager_id == 7

    @pytest.mark.asyncio
    async def test_us234_ca3_la_commande_s_execute_dans_le_potager_de_la_proposition(self, journal):
        """[CA3, US-259 / CA4] « supprime la parcelle test » dit dans le potager 1, confirmé
        alors que le potager actif est le 2 : elle s'exécute dans le 1, celui où elle a été dite."""
        vu: list = []

        async def handler(update, ctx):
            vu.append(ctx.user_data.get(bot_module.CLE_POTAGER_IMPOSE))

        ctx = _ctx(None)
        ctx.application.handlers = {0: [CommandHandler("parcelle", handler)]}
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        with patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
             patch.object(bot_module, "_contexte_sur", side_effect=_sur) as contexte:
            await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)

        contexte.assert_called_once_with(1, 1)
        assert vu == [1], "le garde de liaison arme le potager DE LA PROPOSITION"
        assert bot_module.CLE_POTAGER_IMPOSE not in ctx.user_data, "il ne vaut que pour cette exécution"

    @pytest.mark.asyncio
    async def test_us234_ca3_hors_d_acces_rien_n_est_execute(self, journal):
        """[CA3, US-259 / CA4] Le jardinier n'est plus membre du potager de la proposition :
        rien ne s'exécute, et le contrôle précède le choix d'un nom voisin."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(
            _update(), ctx, _suppression().avec_candidats("nom", ("Test Nord",))
        )
        ident = _en_attente().code

        clic = _clic(f"interp:cand:0:{ident}")
        with patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
             patch.object(bot_module, "_contexte_sur", return_value=None):
            await bot_module._interp_cb(clic, ctx)

        assert "plus accès au potager" in _texte_du_clic(clic)
        assert "rien n'a été fait" in _texte_du_clic(clic)
        assert _en_attente() is None
        assert ctx.user_data["mode"] is None

    @pytest.mark.asyncio
    async def test_us234_ca3_jardinier_illisible_rien_n_est_execute(self, journal):
        """[CA3] Faute de pouvoir vérifier, on n'exécute pas : le contrôle ne présume rien."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        clic = _clic(f"interp:ok:{ident}")
        with patch.object(bot_module, "_jardinier_au_clic", return_value=None):
            await bot_module._interp_cb(clic, ctx)

        handler.assert_not_awaited()
        assert "Impossible de vérifier le potager actif" in _texte_du_clic(clic)

    @pytest.mark.asyncio
    async def test_us234_ca3_annuler_reste_possible_hors_d_acces(self, journal):
        """[CA3] Annuler n'écrit rien : il ne dépend pas du potager."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        clic = _clic(f"interp:non:{ident}")
        with patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
             patch.object(bot_module, "_contexte_sur", return_value=None):
            await bot_module._interp_cb(clic, ctx)

        assert "Annulé" in _texte_du_clic(clic)
        assert _en_attente() is None

    def test_us234_ca3_les_lectures_au_clic_ne_levent_jamais(self):
        """[CA3] Une panne de lecture donne None (donc un refus), jamais une exception."""
        update = _update()
        update.effective_chat.id = 99
        with patch("database.db.SessionLocal", side_effect=RuntimeError("base indisponible")), \
             patch.object(bot_module, "SessionLocal", side_effect=RuntimeError("base indisponible")):
            assert bot_module._jardinier_au_clic(update) is None
            assert bot_module._contexte_sur(5, 3) is None

    def test_us234_ca3_le_jardinier_se_lit_par_le_chat(self):
        """[CA3] Chat → utilisateur, par le service du garde de liaison."""
        update = _update()
        update.effective_chat.id = 99
        base = MagicMock()
        with patch.object(bot_module, "SessionLocal", return_value=base), \
             patch.object(bot_module.svc_liaison_telegram, "resoudre_user_id_pour_chat",
                          return_value=5) as chat:
            assert bot_module._jardinier_au_clic(update) == 5

        chat.assert_called_once_with(base, 99)
        base.close.assert_called_once()

    def test_us234_ca3_le_role_se_lit_sur_le_potager_de_la_proposition(self):
        """[US-259 / CA4] Le rôle est relu sur LE potager de la proposition, pas l'actif."""
        base = MagicMock()
        attendu = TenantContext(user_id=5, potager_id=3, role="editor")
        with patch.object(bot_module, "SessionLocal", return_value=base), \
             patch.object(bot_module.svc_potager_actif, "contexte_sur_potager",
                          return_value=attendu) as service:
            assert bot_module._contexte_sur(5, 3) is attendu

        service.assert_called_once_with(base, 5, 3)
        base.close.assert_called_once()

    def test_us234_ca3_chat_non_lie_donne_none(self):
        """[CA3] Pas d'utilisateur derrière le chat : refus."""
        update = _update()
        update.effective_chat.id = 99
        with patch.object(bot_module, "SessionLocal", return_value=MagicMock()), \
             patch.object(bot_module.svc_liaison_telegram, "resoudre_user_id_pour_chat",
                          return_value=None):
            assert bot_module._jardinier_au_clic(update) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — retirée avant l'exécution : pas de double exécution
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4PasDeDoubleExecution:

    @pytest.mark.asyncio
    async def test_us234_ca4_un_double_appui_n_execute_qu_une_fois(self, journal, potager_au_clic):
        """[CA4] Le second appui trouve la proposition déjà retirée."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)
        second = _clic(f"interp:ok:{ident}")
        await bot_module._interp_cb(second, ctx)

        handler.assert_awaited_once()
        assert "Demande expirée, rien n'a été fait" in _texte_du_clic(second)

    @pytest.mark.asyncio
    async def test_us234_ca4_la_proposition_est_retiree_avant_l_execution(self, journal, potager_au_clic):
        """[CA4] Au moment où le handler tourne, plus rien n'est en attente — un
        message rejoué pendant l'exécution ne peut pas la relancer."""
        vu_pendant_l_execution: list[bool] = []

        async def handler(update, ctx):
            vu_pendant_l_execution.append(_en_attente() is not None)

        ctx = _ctx(None)
        ctx.application.handlers = {0: [CommandHandler("parcelle", handler)]}
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)

        assert vu_pendant_l_execution == [False]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — ce qui s'exécute est la commande affichée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5CommandeAffichee:

    @pytest.mark.asyncio
    async def test_us234_ca5_la_commande_executee_est_celle_du_recapitulatif(self, journal, potager_au_clic):
        """[CA5] Mêmes arguments que ceux affichés, aucune réinterprétation de la phrase."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        commande = _creation()
        update = _update()
        await bot_module._interp_proposer(update, ctx, commande)
        affiche = update.message.reply_text.await_args.args[0]
        ident = _en_attente().code

        with patch.object(interp, "interpreter") as reinterpretation, \
             patch.object(interp, "reconnaitre_par_regles") as regles:
            await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)

        handler.assert_awaited_once()
        assert ctx.args == list(commande.args)
        assert commande.commande_equivalente() in affiche
        reinterpretation.assert_not_called()
        regles.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — le reste se comporte comme avant
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6ComportementsConserves:

    @pytest.mark.asyncio
    async def test_us234_ca6_une_proposition_expiree_n_execute_rien(self, journal, potager_au_clic):
        """[CA6] Le délai d'expiration joue toujours, et il est journalisé abandonné."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code
        _vieillir(ident)

        clic = _clic(f"interp:ok:{ident}")
        await bot_module._interp_cb(clic, ctx)

        handler.assert_not_awaited()
        assert "Demande expirée, rien n'a été fait" in _texte_du_clic(clic)
        assert _issues(journal)[-1] == (interp.ISSUE_ABANDONNEE, 10)

    @pytest.mark.asyncio
    async def test_us234_ca6_choisir_un_nom_voisin_fait_avancer_la_meme_proposition(self, journal, potager_au_clic):
        """[CA6, CA12 US-172] Le choix remplace le nom, l'identifiant reste celui de la demande."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(
            _update(), ctx, _suppression().avec_candidats("nom", ("Test Nord",))
        )
        ident = _en_attente().code

        clic = _clic(f"interp:cand:0:{ident}")
        await bot_module._interp_cb(clic, ctx)

        courante = _en_attente()
        assert courante.code == ident
        assert courante.commande.valeurs["nom"] == "Test Nord"

    @pytest.mark.asyncio
    async def test_us234_ca6_la_completion_texte_garde_la_meme_proposition(self, journal, potager_au_clic):
        """[CA6, CA13 US-172] Répondre à une question ne change ni l'identifiant ni le potager retenu."""
        ctx = _ctx(AsyncMock())
        commande = interp.reconnaitre_par_regles("note une association entre la carotte et l'aneth")
        await bot_module._interp_proposer(_update(), ctx, commande)
        avant = _en_attente()

        await bot_module._interp_completion_texte(_update(), ctx, "defavorable")

        apres = _en_attente()
        assert (apres.code, apres.potager_id) == (avant.code, avant.potager_id)
        assert apres.commande.valeurs["nature"] == "defavorable"


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — le journal dit « abandonnée »
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Journal:

    @pytest.mark.asyncio
    async def test_us234_ca7_une_proposition_remplacee_est_journalisee_abandonnee(self, journal):
        """[CA7] Sa ligne de journal reçoit l'issue, au lieu de rester « proposée »."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        await bot_module._interp_proposer(_update(), ctx, _creation())

        assert _issues(journal) == [
            (interp.ISSUE_PROPOSEE, None),       # 1re demande → ligne 10
            (interp.ISSUE_ABANDONNEE, 10),       # remplacée → sa ligne est complétée
            (interp.ISSUE_PROPOSEE, None),       # 2e demande → ligne 11
        ]
        assert _en_attente().log_id == 11

    @pytest.mark.asyncio
    async def test_us234_ca7_une_premiere_demande_n_abandonne_rien(self, journal):
        """[CA7] Pas de proposition précédente : une seule ligne, « proposée »."""
        await bot_module._interp_proposer(_update(), _ctx(), _suppression())
        assert _issues(journal) == [(interp.ISSUE_PROPOSEE, None)]

    @pytest.mark.asyncio
    async def test_us234_ca7_un_potager_hors_d_acces_est_journalise_abandonne(self, journal):
        """[CA7] Refusée par CA3 : abandonnée, sur la ligne de SA proposition."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        with patch.object(bot_module, "_jardinier_au_clic", return_value=1), \
             patch.object(bot_module, "_contexte_sur", return_value=None):
            await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)

        assert _issues(journal)[-1] == (interp.ISSUE_ABANDONNEE, 10)

    @pytest.mark.asyncio
    async def test_us234_ca7_un_bouton_perime_n_ecrit_rien_au_journal(self, journal, potager_au_clic):
        """[CA7] Refusé par CA2 : la proposition qu'il visait a été journalisée à son
        remplacement ; celle en cours reste « proposée », elle n'est pas touchée."""
        ctx = _ctx(AsyncMock())
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ancien_id = _en_attente().code
        await bot_module._interp_proposer(_update(), ctx, _creation())
        ecritures = journal.call_count

        await bot_module._interp_cb(_clic(f"interp:ok:{ancien_id}"), ctx)

        assert journal.call_count == ecritures

    @pytest.mark.asyncio
    async def test_us234_ca7_la_confirmation_reste_journalisee_confirmee(self, journal, potager_au_clic):
        """[CA7] Le chemin nominal est inchangé : proposée, puis confirmée sur la même ligne."""
        handler = AsyncMock()
        ctx = _ctx(handler)
        await bot_module._interp_proposer(_update(), ctx, _suppression())
        ident = _en_attente().code

        await bot_module._interp_cb(_clic(f"interp:ok:{ident}"), ctx)

        assert _issues(journal) == [
            (interp.ISSUE_PROPOSEE, None),
            (interp.ISSUE_CONFIRMEE, 10),
        ]
        handler.assert_awaited_once()
