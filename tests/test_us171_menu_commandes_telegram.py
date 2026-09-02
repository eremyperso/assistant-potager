"""
tests/test_us171_menu_commandes_telegram.py
[US-171] Remplacer le clavier de raccourcis permanent par le menu natif Telegram

Couverture des critères d'acceptance CA1 → CA13.

Deux critères ne sont vérifiables qu'en partie par le code, et le disent ici
plutôt que de se faire passer pour couverts :

  - CA2, volet « tient dans 375 px sans troncature » : la longueur maximale est
    vérifiée automatiquement (`LONGUEUR_MAX_DESCRIPTION`), le rendu réel dans le
    client Telegram ne l'est pas — il relève du contrôle visuel.
  - CA1, volet « le bouton Menu ouvre la liste » : ce que le bot maîtrise, c'est
    l'appel `set_my_commands` et son contenu ; l'affichage lui-même est rendu par
    le client Telegram.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import BotCommand, ReplyKeyboardRemove
from telegram.ext import CommandHandler

import bot as bot_module
from app.services import menu_commandes as svc_menu


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def commandes_du_bot() -> set[str]:
    """Les commandes réellement enregistrées par le bot, par introspection.

    Construire l'Application complète coûte cher et exige un token : on rejoue
    ici l'introspection sur un double qui expose la même structure `handlers`.
    """
    return _noms_commandes_reellement_enregistrees()


def _noms_commandes_reellement_enregistrees() -> set[str]:
    """Lit les noms passés à `_enregistrer_commande` dans `_construire_application`."""
    noms: set[str] = set()

    faux_app = MagicMock()

    def _capturer(app, nom, handler):
        noms.add(nom)

    with patch.object(bot_module, "_enregistrer_commande", _capturer), \
         patch.object(bot_module, "Application") as faux_builder:
        faux_builder.builder.return_value.token.return_value.read_timeout.return_value \
            .write_timeout.return_value.connect_timeout.return_value.pool_timeout.return_value \
            .post_init.return_value.build.return_value = faux_app
        bot_module._construire_application()

    return noms


def _app_avec_commandes(noms: list[str]) -> MagicMock:
    """Double d'Application exposant des `CommandHandler` pour l'introspection."""
    app = MagicMock()
    app.handlers = {0: [CommandHandler(nom, AsyncMock()) for nom in noms]}
    return app


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA6 — le menu est déclaré à Telegram, à chaque démarrage
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1CA6DeclarationDuMenu:

    @pytest.mark.asyncio
    async def test_us171_menu_declare_les_commandes_a_telegram(self) -> None:
        """[CA1] Le démarrage envoie la liste des commandes via set_my_commands."""
        app = _app_avec_commandes(["stats", "historique"])
        app.bot.set_my_commands = AsyncMock()

        await bot_module._publier_menu_commandes(app)

        app.bot.set_my_commands.assert_awaited_once()
        envoyees = app.bot.set_my_commands.await_args.args[0]
        assert all(isinstance(c, BotCommand) for c in envoyees)
        assert {c.command for c in envoyees} == {"stats", "historique"}
        assert all(c.description for c in envoyees)

    @pytest.mark.asyncio
    async def test_us171_menu_rejoue_a_chaque_demarrage(self) -> None:
        """[CA6] La déclaration est câblée sur post_init, donc rejouée à chaque run."""
        with patch.object(bot_module, "Application") as faux:
            constructeur = faux.builder.return_value.token.return_value \
                .read_timeout.return_value.write_timeout.return_value \
                .connect_timeout.return_value.pool_timeout.return_value
            constructeur.post_init.return_value.build.return_value = MagicMock()
            bot_module._construire_application()

        constructeur.post_init.assert_called_once_with(bot_module._publier_menu_commandes)

    @pytest.mark.asyncio
    async def test_us171_commande_nouvelle_entre_au_menu_sans_intervention(self) -> None:
        """[CA6] Une commande inconnue du catalogue entre quand même au menu."""
        entrees = svc_menu.construire_menu({"stats", "toute_nouvelle"})

        noms = [nom for nom, _ in entrees]
        assert "toute_nouvelle" in noms
        description = dict(entrees)["toute_nouvelle"]
        assert description, "une commande sans phrase d'aide doit garder un repli non vide"

    @pytest.mark.asyncio
    async def test_us171_echec_telegram_ne_bloque_pas_le_demarrage(self) -> None:
        """[CA1 / robustesse] Une panne réseau au démarrage est journalisée, pas fatale."""
        app = _app_avec_commandes(["stats"])
        app.bot.set_my_commands = AsyncMock(side_effect=RuntimeError("Telegram indisponible"))

        await bot_module._publier_menu_commandes(app)  # ne doit pas lever


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une phrase d'aide courte, en français, par commande
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2PhrasesDAide:

    def test_us171_chaque_commande_du_menu_a_une_phrase_d_aide(self, commandes_du_bot) -> None:
        """[CA2] Aucune commande du menu ne s'affiche sans description."""
        entrees = svc_menu.construire_menu(commandes_du_bot)

        sans_phrase = [nom for nom, desc in entrees if not desc.strip()]
        assert sans_phrase == []

    def test_us171_phrases_d_aide_redigees_et_non_generees(self, commandes_du_bot) -> None:
        """[CA2] Aucune commande ne se contente du repli technique « Commande /x »."""
        manquantes = sorted(commandes_du_bot - svc_menu.COMMANDES_EXCLUES - set(svc_menu.DESCRIPTIONS))
        assert manquantes == [], f"phrase d'aide à rédiger pour : {manquantes}"

    def test_us171_phrases_d_aide_tiennent_sur_un_ecran_mobile(self) -> None:
        """[CA2] Chaque description reste sous la longueur lisible à 375 px."""
        trop_longues = {
            nom: len(desc)
            for nom, desc in svc_menu.DESCRIPTIONS.items()
            if len(desc) > svc_menu.LONGUEUR_MAX_DESCRIPTION
        }
        assert trop_longues == {}


# ═════════════════════════════════════════════════════════════════════════════
# CA3, CA3bis, CA3ter — ce qui entre au menu, ce qui en est écarté
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3PerimetreDuMenu:

    def test_us171_les_commandes_du_quotidien_sont_toutes_au_menu(self, commandes_du_bot) -> None:
        """[CA3] Toute commande enregistrée non explicitement exclue figure au menu."""
        attendues = commandes_du_bot - svc_menu.COMMANDES_EXCLUES
        obtenues = {nom for nom, _ in svc_menu.construire_menu(commandes_du_bot)}

        assert obtenues == attendues

    def test_us171_les_trois_exclusions_decidees_sont_hors_menu(self, commandes_du_bot) -> None:
        """[CA3] /version, /delier et /tts n'apparaissent pas dans le menu."""
        noms = {nom for nom, _ in svc_menu.construire_menu(commandes_du_bot)}

        assert "version" not in noms
        assert "delier" not in noms
        assert "tts" not in noms

    def test_us171_liste_d_exclusion_en_un_seul_endroit(self) -> None:
        """[CA3] L'exclusion se décide dans COMMANDES_EXCLUES, nulle part ailleurs.

        Vidée, la liste laisse entrer les trois commandes : aucune exclusion
        n'est codée en dur ailleurs dans la construction du menu.
        """
        with patch.object(svc_menu, "COMMANDES_EXCLUES", frozenset()):
            noms = {nom for nom, _ in svc_menu.construire_menu({"version", "delier", "tts", "stats"})}

        assert {"version", "delier", "tts"} <= noms

    def test_us171_aucune_commande_morte_au_menu(self) -> None:
        """[CA3] Le menu se dérive des commandes réelles, pas d'une liste recopiée."""
        noms = {nom for nom, _ in svc_menu.construire_menu({"stats"})}

        assert noms == {"stats"}, "une commande non enregistrée ne doit jamais s'afficher"

    def test_us171_commandes_exclues_toujours_servies_par_le_bot(self, commandes_du_bot) -> None:
        """[CA3bis] Retirer du menu ne retire pas du bot : les handlers restent."""
        assert {"version", "delier", "tts"} <= commandes_du_bot

    def test_us171_tts_on_et_off_agissent_en_un_clic(self, commandes_du_bot) -> None:
        """[CA3ter] Le réglage de la voix passe par deux entrées qui agissent, pas par /tts."""
        noms = {nom for nom, _ in svc_menu.construire_menu(commandes_du_bot)}

        assert "tts_on" in noms and "tts_off" in noms
        assert "tts" not in noms


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — l'ordre des lignes suit une logique métier
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4OrdreDuMenu:

    def test_us171_ordre_metier_respecte(self, commandes_du_bot) -> None:
        """[CA4] Les gestes précèdent la consultation, qui précède la configuration."""
        noms = [nom for nom, _ in svc_menu.construire_menu(commandes_du_bot)]

        assert noms.index("note") < noms.index("stats") < noms.index("potager")

    def test_us171_ordre_independant_de_l_ordre_d_enregistrement(self) -> None:
        """[CA4] L'ordre ne suit pas l'ordre d'écriture dans le code."""
        entrees_a = [nom for nom, _ in svc_menu.construire_menu(["potager", "note", "stats"])]
        entrees_b = [nom for nom, _ in svc_menu.construire_menu(["stats", "potager", "note"])]

        assert entrees_a == entrees_b == ["note", "stats", "potager"]

    def test_us171_commande_hors_catalogue_rangee_en_fin(self) -> None:
        """[CA4] Une commande sans rang connu ne s'insère pas au milieu du menu."""
        noms = [nom for nom, _ in svc_menu.construire_menu(["zzz_inconnue", "note", "stats"])]

        assert noms[-1] == "zzz_inconnue"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le menu ne change la sémantique d'aucune commande
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5SemantiqueInchangee:

    def test_us171_le_menu_ne_declare_que_des_noms_de_commandes(self, commandes_du_bot) -> None:
        """[CA5] Une entrée de menu est le nom d'une commande servie, tel quel.

        Le menu n'ajoute ni argument ni variante : cliquer une ligne revient
        exactement à taper la commande à la main.
        """
        for nom, _ in svc_menu.construire_menu(commandes_du_bot):
            assert nom in commandes_du_bot
            assert nom == nom.lower()
            assert " " not in nom and not nom.startswith("/")


# ═════════════════════════════════════════════════════════════════════════════
# CA7, CA8, CA12 — le clavier de raccourcis permanent disparaît
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7CA8ClavierPermanentRetire:

    def test_us171_plus_aucun_clavier_permanent_defini(self) -> None:
        """[CA7] Les deux claviers de raccourcis ne sont plus des claviers."""
        assert isinstance(bot_module.MENU_KEYBOARD, ReplyKeyboardRemove)
        assert isinstance(bot_module.AFTER_RECORD_KEYBOARD, ReplyKeyboardRemove)

    def test_us171_retrait_actif_du_clavier_chez_les_utilisateurs_existants(self) -> None:
        """[CA8] Le bot demande explicitement le retrait, il ne se contente pas de ne plus l'envoyer.

        Sans cette demande, un clavier permanent déjà affiché resterait visible
        indéfiniment côté client : c'est tout l'objet de ce critère.
        """
        assert bot_module.MENU_KEYBOARD.remove_keyboard is True
        assert bot_module.AFTER_RECORD_KEYBOARD.remove_keyboard is True

    def test_us171_aucun_bouton_de_raccourci_ne_subsiste_dans_le_source(self) -> None:
        """[CA7] Les libellés des anciens raccourcis ne sont plus émis en clavier."""
        import inspect

        source = inspect.getsource(bot_module)
        declaration = source.split("SANS_CLAVIER = ReplyKeyboardRemove()")[0]

        assert 'KeyboardButton("🎤 Nouvelle action vocale")' not in declaration
        assert 'KeyboardButton("➕ Autre action")' not in declaration

    @pytest.mark.asyncio
    async def test_us171_apres_enregistrement_aucun_clavier_ne_revient(self) -> None:
        """[CA12] Le message d'après enregistrement retire le clavier au lieu d'en poser un."""
        assert bot_module.AFTER_RECORD_KEYBOARD is bot_module.SANS_CLAVIER
        assert isinstance(bot_module.SANS_CLAVIER, ReplyKeyboardRemove)


# ═════════════════════════════════════════════════════════════════════════════
# CA9, CA10 — les parcours restent atteignables, la découverte pointe le menu
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9CA10ContinuiteDesParcours:

    @pytest.mark.parametrize("bouton_retire, commande_equivalente", [
        ("📋 Historique", "historique"),
        ("📊 Stats", "stats"),
        ("✏️ Corriger", "corriger"),
        ("📝 Note", "note"),
        ("🔍 Interroger", "ask"),
        ("🔍 Interroger mes données", "ask"),
        ("🏠 Menu principal", "start"),
    ])
    def test_us171_chaque_bouton_retire_a_son_equivalent_au_menu(
        self, bouton_retire, commande_equivalente, commandes_du_bot
    ) -> None:
        """[CA9] Bouton par bouton, le parcours reste atteignable depuis le menu."""
        noms = {nom for nom, _ in svc_menu.construire_menu(commandes_du_bot)}

        assert commande_equivalente in noms, f"« {bouton_retire} » n'a plus de chemin"

    def test_us171_bouton_nouvelle_action_vocale_reste_couvert(self) -> None:
        """[CA9] « Nouvelle action vocale » n'avait pas de commande : le geste reste direct.

        Dicter un message vocal est le geste nominal du bot, disponible sans
        aucune commande — le bouton n'était qu'une invite.
        """
        assert hasattr(bot_module, "handle_voice")

    def test_us171_start_oriente_vers_le_menu(self) -> None:
        """[CA10] /start ne renvoie plus vers des boutons mais vers le menu."""
        import inspect

        source = inspect.getsource(bot_module.cmd_start)

        assert "Ou utilisez les boutons ci-dessous" not in source
        assert "menu" in source.lower()

    def test_us171_help_annonce_le_menu(self) -> None:
        """[CA10] L'aide en ligne désigne le menu comme accès aux commandes."""
        import inspect

        source = inspect.getsource(bot_module.cmd_help)

        assert "bouton *Menu*" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA11, CA13 — les claviers contextuels de validation sont intacts
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11CA13ClaviersContextuelsIntacts:

    def test_us171_clavier_de_confirmation_de_delier_intact(self) -> None:
        """[CA11] Le clavier de confirmation de dissociation reste un vrai clavier."""
        from telegram import ReplyKeyboardMarkup

        assert isinstance(bot_module._DELIER_CLAVIER_CONFIRMATION, ReplyKeyboardMarkup)

    def test_us171_clavier_de_categories_de_note_intact(self) -> None:
        """[CA11] La saisie guidée de note garde son clavier de catégories."""
        from telegram import ReplyKeyboardMarkup

        assert isinstance(bot_module._NOTE_CATEGORY_KEYBOARD, ReplyKeyboardMarkup)

    def test_us171_boutons_inline_de_validation_intacts(self) -> None:
        """[CA11] Les boutons de confirmation d'un événement sont inchangés."""
        import inspect

        source = inspect.getsource(bot_module)

        assert 'callback_data="action_confirm"' in source
        assert 'callback_data="action_cancel"' in source
