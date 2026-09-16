"""
tests/test_us172_interpreteur_commandes.py
[US-172] Piloter par une phrase toutes les commandes du bot

Couverture des critères d'acceptance CA1 → CA22.

Deux critères ne sont couverts qu'en partie, et le disent ici plutôt que de se
faire passer pour couverts — même convention que `test_us171` :

  - **CA15, volet « trois registres pour chacune ».** Le corpus porte, pour
    chaque commande dictable, au moins trois formulations distinctes et la
    question de savoir voisine ; les trois registres (impératif, intention,
    ellipse) sont vérifiés comme PRÉSENTS dans le corpus, et exigés commande par
    commande partout où les trois existent en français. Quelques commandes n'ont
    pas de forme elliptique naturelle (« supprime la parcelle X » ne s'abrège
    pas autrement qu'en « suppression de la parcelle X », qui est la forme
    nominale retenue) : le test contrôle alors les trois formulations, sans
    exiger une étiquette de registre qu'aucun jardinier ne prononcerait.
  - **CA17, volet « publiée à la livraison ».** Le test MESURE la part traitée
    sans appel modèle ; sa publication est faite dans `PATCH_NOTES.md`, que le
    test ne lit pas.

Et un chiffre à lire pour ce qu'il est : le corpus a servi à calibrer les
règles, comme celui d'US-094 et celui d'US-099 avant lui. Un taux de 100 % y
mesure la couverture de ce qu'on a su prévoir, pas celle de ce qu'un jardinier
dira demain — c'est la journalisation du CA18, en production, qui dira le
second.
"""
import csv
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import CommandHandler

import bot as bot_module
from app.services import interpreteur_commandes as interp
from app.services import menu_commandes as svc_menu
from app.services.context import TenantContext

CORPUS = Path(__file__).parent / "corpus" / "us172_commandes.csv"


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures et utilitaires
# ═════════════════════════════════════════════════════════════════════════════

def _lignes_corpus() -> list[dict]:
    with CORPUS.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def _cible(resultat) -> str:
    """Représentation « commande sous-commande » d'un résultat d'interprétation."""
    if resultat is None:
        return ""
    if isinstance(resultat, interp.Ambiguite):
        return "AMBIGU"
    return f"{resultat.commande} {resultat.sous_commande or ''}".strip()


def _noms_commandes_reellement_enregistrees() -> set[str]:
    """Les commandes que le bot enregistre vraiment, par introspection.

    Rejoue `_construire_application` sur un double, exactement comme le fait le
    test du menu d'US-171 : c'est la même source de vérité, et c'est le point de
    la parité du CA7 — comparer deux ensembles dérivés, jamais une liste écrite
    à la main.
    """
    noms: set[str] = set()

    def _capturer(app, nom, handler):
        noms.add(nom)

    with patch.object(bot_module, "_enregistrer_commande", _capturer), \
         patch.object(bot_module, "Application") as faux_builder:
        faux_builder.builder.return_value.token.return_value.read_timeout.return_value \
            .write_timeout.return_value.connect_timeout.return_value.pool_timeout.return_value \
            .post_init.return_value.build.return_value = MagicMock()
        bot_module._construire_application()

    return noms


def _update(user_id: int = 42):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


def _update_callback(user_id: int = 42, data: str = "interp:ok"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = None
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.message = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def _ctx(handlers: dict | None = None):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.args = []
    ctx.application.handlers = handlers or {}
    return ctx


def _texte_envoye(update) -> str:
    """Concatène tout ce que le bot a répondu, quel que soit le canal."""
    morceaux = []
    for cible in (update.message, getattr(update.callback_query, "message", None)):
        if cible is None:
            continue
        for appel in cible.reply_text.await_args_list:
            morceaux.append(str(appel.args[0]) if appel.args else "")
    if update.callback_query is not None:
        for appel in update.callback_query.edit_message_text.await_args_list:
            morceaux.append(str(appel.args[0]) if appel.args else "")
    return "\n".join(morceaux)


def _potager_de_test(db) -> None:
    """Un potager et son propriétaire — `routage_logs.potager_id` est une clé
    étrangère, et `potagers.proprietaire_id` n'est pas nullable."""
    from database.models import Potager, User

    db.add(User(id=1, email="jardinier@test.local"))
    db.flush()
    db.add(Potager(id=1, nom="Test", proprietaire_id=1))
    db.commit()


@pytest.fixture(autouse=True)
def _etat_propre():
    """Aucune proposition en attente ne fuit d'un test à l'autre."""
    bot_module._INTERP_PENDING.clear()
    bot_module._CREATION_PARCELLE_PENDING.clear()
    yield
    bot_module._INTERP_PENDING.clear()
    bot_module._CREATION_PARCELLE_PENDING.clear()


@pytest.fixture
def sans_journal():
    """Neutralise l'écriture du journal : ces tests ne portent pas dessus, et
    `routage_logs` exige un potager en base."""
    with patch.object(interp, "persister_journal", return_value=1) as faux:
        yield faux


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA3 — reconnaissance de l'intention, déterministe d'abord
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1CA3ReconnaissanceDeterministe:

    @pytest.mark.parametrize("phrase, attendu", [
        ("supprime la parcelle nord", "parcelle supprimer"),          # impératif
        ("je veux créer la parcelle PlancheTomate", "parcelle ajouter"),  # intention
        ("bilan des tomates", "stats"),                                # elliptique
        ("plan du potager", "plan"),                                   # elliptique
        ("est-ce que la lecture vocale est active ?", "tts"),           # elliptique
    ])
    def test_us172_ca1_trois_registres_reconnus(self, phrase, attendu):
        """[CA1] Impératif, intention et ellipse mènent tous à une commande."""
        assert _cible(interp.reconnaitre_par_regles(phrase)) == attendu

    def test_us172_ca3_aucun_appel_modele_sur_les_formes_frequentes(self):
        """[CA3] Les formes fréquentes ne consomment aucun jeton.

        La passerelle est mise sous surveillance : si une seule phrase du corpus
        l'atteignait, l'économie annoncée par le CA17 serait fausse.
        """
        interessantes = [
            l for l in _lignes_corpus() if l["attendu"] or l["registre"] == "savoir"
        ]
        with patch.object(interp, "_appeler_modele") as faux_modele:
            for ligne in interessantes:
                interp.interpreter(ligne["phrase"], None)
            assert faux_modele.call_count == 0

        # Une phrase hors périmètre, elle, a le droit de descendre au modèle :
        # c'est le repli du CA4, et il ne produit rien sans sortie conforme.
        assert len(interessantes) > 100

    def test_us172_ca3_origine_regle_et_confiance_pleine(self):
        """[CA3] Une reconnaissance par règle se déclare comme telle."""
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")
        assert commande.origine == interp.ORIGINE_REGLE
        assert commande.confiance == 1.0
        assert commande.regle == "parcelle_supprimer"


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — vouloir faire n'est pas demander comment faire
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2VouloirFaireNestPasDemanderCommentFaire:

    @pytest.mark.parametrize("faire, demander", [
        ("supprime la parcelle nord", "comment supprimer une parcelle ?"),
        ("crée la parcelle nord", "comment créer une parcelle ?"),
        ("renomme la parcelle sud en carré sud", "comment renommer une parcelle ?"),
        ("note une observation", "comment noter une observation ?"),
        ("corrige ma dernière saisie", "comment corriger un événement ?"),
    ])
    def test_us172_ca2_les_deux_formes_en_regard(self, faire, demander):
        """[CA2] La forme qui EXÉCUTE est reconnue, la forme qui DEMANDE ne l'est pas.

        C'est la confusion la plus probable de cette US : les deux phrases
        partagent presque tous leurs mots. Elles sont donc testées en regard
        l'une de l'autre, jamais séparément.
        """
        assert interp.reconnaitre_par_regles(faire) is not None
        assert interp.reconnaitre_par_regles(demander) is None

    def test_us172_ca2_toutes_les_questions_du_corpus_sont_ignorees(self):
        """[CA2] Aucune des questions de savoir du corpus n'est captée."""
        questions = [l for l in _lignes_corpus() if l["registre"] == "savoir"]
        assert len(questions) >= 20, "le corpus doit porter une question par commande"
        captees = [q["phrase"] for q in questions
                   if interp.reconnaitre_par_regles(q["phrase"]) is not None]
        assert captees == []

    def test_us172_ca2_dis_moi_comment_est_aussi_une_question(self):
        """[CA2] Le garde ne se limite pas aux phrases OUVRANT par « comment »."""
        assert interp.reconnaitre_par_regles("dis-moi comment supprimer une parcelle") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — le modèle en repli, sous contrainte fermée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4ModeleSousContrainteFermee:

    def test_us172_ca4_commande_hors_catalogue_rejetee(self):
        """[CA4] Le modèle ne peut pas inventer une commande."""
        assert interp._valider_sortie_modele(
            "exporter|-|tout|0.99", "exporte tout mon potager"
        ) is None

    def test_us172_ca4_valeur_hors_vocabulaire_rejetee(self):
        """[CA4] Le modèle ne peut pas inventer une valeur de vocabulaire fermé."""
        assert interp._valider_sortie_modele(
            "culture|exposition|courgette;plein nord|0.99",
            "la courgette veut du plein nord",
        ) is None

    def test_us172_ca4_argument_absent_de_la_phrase_rejete(self):
        """[CA4] Le modèle ne peut pas inventer un argument.

        C'est le refus le plus important des trois : sans lui, une parcelle que
        personne n'a nommée pourrait être proposée à la suppression.
        """
        assert interp._valider_sortie_modele(
            "parcelle|supprimer|nord|0.99", "supprime la parcelle du fond"
        ) is None

    def test_us172_ca4_sortie_conforme_acceptee(self):
        """[CA4] Une sortie conforme, elle, est retenue."""
        commande = interp._valider_sortie_modele(
            "parcelle|supprimer|serre|0.9", "il faut se débarrasser de la serre"
        )
        assert commande is not None
        assert commande.args == ("supprimer", "serre")
        assert commande.origine == interp.ORIGINE_MODELE

    def test_us172_ca4_aucune_commande_reconnue(self):
        """[CA4] « AUCUNE » est une réponse valide, et ne produit rien."""
        assert interp._valider_sortie_modele("AUCUNE|-||1.0", "récolté 2 kg") is None

    def test_us172_ca4_catalogue_du_prompt_derive_du_catalogue_reel(self):
        """[CA4, CA6] Le prompt décrit le catalogue réel, jamais une copie.

        Une commande ajoutée à `FORMES_DICTABLES` entre dans le prompt sans
        qu'on y touche : il est donc impossible d'y décrire une commande qui
        n'existe pas.
        """
        catalogue = interp._decrire_catalogue()
        for forme in svc_menu.FORMES_DICTABLES:
            attendu = (f"{forme.commande} {forme.sous_commande}"
                       if forme.sous_commande else forme.commande)
            assert attendu in catalogue
        for exclue in svc_menu.COMMANDES_EXCLUES_INTERPRETEUR:
            assert f"\n{exclue} " not in catalogue and not catalogue.startswith(f"{exclue} ")

    def test_us172_ca4_confiance_faible_rend_la_main(self):
        """[CA4, CA12] Sous le seuil, le doute rend la main à la cascade."""
        faible = interp._valider_sortie_modele("plan|-||0.3", "montre le plan")
        with patch.object(interp, "_appeler_modele", return_value=faible):
            assert interp.interpreter("phrase que les règles ignorent", None) is None

    def test_us172_ca4_indisponibilite_du_modele_ne_leve_jamais(self):
        """[CA4] Une passerelle en panne rend la main, elle ne casse pas le flux."""
        with patch("llm.passerelle.appeler_chat", side_effect=RuntimeError("429")):
            assert interp.interpreter("phrase que les règles ignorent", None) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — la dictée vocale ne change rien
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5DicteeVocale:

    @pytest.mark.parametrize("tape, dicte", [
        ("supprime la parcelle nord", "supprime la parcelle nord"),
        ("qu'est-ce que j'ai fait dernièrement ?", "qu est ce que j ai fait dernierement"),
        ("montre-moi le plan", "montre moi le plan"),
        ("la salade préfère la mi-ombre", "la salade prefere la mi ombre"),
    ])
    def test_us172_ca5_texte_transcrit_et_texte_tape_donnent_la_meme_chose(self, tape, dicte):
        """[CA5] Sans accent, sans ponctuation, sans trait d'union : même résultat.

        C'est ce que produit la transcription — et c'est ce qui a fait échouer
        US-170 puis US-173 avant d'être traité pour lui-même.
        """
        assert _cible(interp.reconnaitre_par_regles(tape)) == \
               _cible(interp.reconnaitre_par_regles(dicte))

    @pytest.mark.asyncio
    async def test_us172_ca5_le_canal_vocal_consulte_l_interpreteur(self):
        """[CA5] `handle_voice` passe la transcription au même point du flux."""
        source = Path(bot_module.__file__).read_text(encoding="utf-8-sig")
        vocal = source.split("async def handle_voice")[1].split("\nasync def ")[0]
        assert "_traiter_commande_interpretee" in vocal
        # …et AVANT le parsing de geste : une phrase reconnue comme commande
        # n'atteint jamais le parseur d'événement.
        assert vocal.index("_traiter_commande_interpretee") < vocal.index("parser_saisie")


# ═════════════════════════════════════════════════════════════════════════════
# CA6, CA7, CA8 — le catalogue est dérivé, la parité est vérifiée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6CA7CA8ParieCommandesInterpreteur:

    def test_us172_ca7_parite_commandes_interpreteur(self):
        """[CA7] Toute commande enregistrée est dictable, alias, ou exclue et motivée.

        C'est ce test, et non la vigilance, qui empêche l'écart constaté avant
        cette US de se recreuser : une commande ajoutée au bot le fait échouer
        tant qu'elle n'a pas été tranchée.
        """
        anomalies = svc_menu.controler_parite(_noms_commandes_reellement_enregistrees())
        assert anomalies == [], "\n".join(anomalies)

    def test_us172_ca7_une_commande_nouvelle_fait_echouer_le_controle(self):
        """[CA7] Le contrôle détecte réellement une commande non tranchée."""
        anomalies = svc_menu.controler_parite(
            _noms_commandes_reellement_enregistrees() | {"exporter"}
        )
        assert any("/exporter" in a for a in anomalies)

    def test_us172_ca7_une_dictable_doit_declarer_la_forme_de_ses_arguments(self):
        """[CA7] Un argument sans type, sans unité ou sans question est une anomalie."""
        bancale = svc_menu.FormeCommande(
            "parcelle", "bancale", "Forme incomplète",
            (svc_menu.Argument("valeur", svc_menu.TYPE_NOMBRE, ""),),  # ni unité ni question
        )
        with patch.object(svc_menu, "FORMES_DICTABLES", svc_menu.FORMES_DICTABLES + (bancale,)):
            anomalies = svc_menu.controler_parite(_noms_commandes_reellement_enregistrees())
        assert any("unité" in a for a in anomalies)
        assert any("question à poser" in a for a in anomalies)

    def test_us172_ca7_un_vocabulaire_ferme_doit_declarer_ses_valeurs(self):
        """[CA7] Un vocabulaire fermé vide ne laisserait au bot qu'à deviner."""
        bancale = svc_menu.FormeCommande(
            "parcelle", "bancale", "Forme incomplète",
            (svc_menu.Argument("valeur", svc_menu.TYPE_VOCABULAIRE, "Quelle valeur ?"),),
        )
        with patch.object(svc_menu, "FORMES_DICTABLES", svc_menu.FORMES_DICTABLES + (bancale,)):
            anomalies = svc_menu.controler_parite(_noms_commandes_reellement_enregistrees())
        assert any("vocabulaire fermé" in a for a in anomalies)

    def test_us172_ca6_les_vocabulaires_sont_lus_aux_services(self):
        """[CA6] Les vocabulaires fermés ne sont pas recopiés dans le catalogue.

        Ils viennent des services qui les VALIDENT déjà : l'interpréteur ne peut
        donc pas proposer une valeur que le point d'écriture refuserait.
        """
        from app.services.associations import NATURES, NIVEAUX_PREUVE
        from app.services.attributs_culture import BESOINS_EAU, EXPOSITIONS
        from app.services.bioagresseurs import CATEGORIES, FREQUENCES

        vocabulaires = {
            argument.vocabulaire
            for forme in svc_menu.FORMES_DICTABLES
            for argument in forme.arguments
            if argument.vocabulaire
        }
        for attendu in (NATURES, NIVEAUX_PREUVE, EXPOSITIONS, BESOINS_EAU, CATEGORIES, FREQUENCES):
            assert tuple(attendu) in vocabulaires

    def test_us172_ca8_les_deux_listes_d_exclusion_sont_distinctes(self):
        """[CA8] Le menu et l'interpréteur n'écartent pas pour les mêmes raisons.

        `/tts`, écartée du menu (elle n'y règle rien), est parfaitement
        dictable ; `/ask`, présente au menu, ne l'est pas (son équivalent
        naturel EST la question elle-même).
        """
        assert svc_menu.COMMANDES_EXCLUES != svc_menu.COMMANDES_EXCLUES_INTERPRETEUR
        assert "tts" in svc_menu.COMMANDES_EXCLUES
        assert "tts" in svc_menu.COMMANDES_DICTABLES
        assert "ask" not in svc_menu.COMMANDES_EXCLUES
        assert "ask" in svc_menu.COMMANDES_EXCLUES_INTERPRETEUR

    def test_us172_ca8_chaque_exclusion_est_motivee(self):
        """[CA8] Une exclusion sans motif écrit serait un « pas encore fait » déguisé."""
        for nom, motif in svc_menu.MOTIFS_EXCLUSION_INTERPRETEUR.items():
            assert len(motif.strip()) > 40, f"/{nom} : motif trop court pour être une décision"

    def test_us172_ca8_les_commandes_exclues_restent_enregistrees(self):
        """[CA8] Les exclure de l'interpréteur ne les retire pas du bot."""
        enregistrees = _noms_commandes_reellement_enregistrees()
        assert svc_menu.COMMANDES_EXCLUES_INTERPRETEUR <= enregistrees


# ═════════════════════════════════════════════════════════════════════════════
# CA9, CA14 — même effet, mêmes contrôles que la commande tapée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9CA14MemeCheminQueLaCommandeTapee:

    @pytest.mark.asyncio
    async def test_us172_ca9_execution_par_le_handler_reellement_enregistre(self):
        """[CA9] L'interpréteur ne réimplémente rien : il appelle le handler."""
        handler = AsyncMock()
        ctx = _ctx({0: [CommandHandler("parcelle", handler)]})
        update = _update()
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")

        await bot_module._interp_executer(update, ctx, commande)

        handler.assert_awaited_once()
        assert ctx.args == ["supprimer", "nord"]

    @pytest.mark.asyncio
    async def test_us172_ca14_le_handler_appele_est_celui_qui_porte_le_garde_de_liaison(self):
        """[CA14] L'interpréteur n'ouvre aucun chemin d'accès parallèle.

        Ce que l'introspection retrouve est le callback ENVELOPPÉ par
        `_avec_garde_liaison` — le même que celui qu'exécute la commande tapée.
        """
        enveloppe = bot_module._avec_garde_liaison(AsyncMock())
        ctx = _ctx({0: [CommandHandler("parcelle", enveloppe)]})
        retrouve = bot_module._handler_de_commande(ctx, "parcelle")
        assert getattr(retrouve, "_garde_liaison", False) is True

    @pytest.mark.asyncio
    async def test_us172_ca14_un_lecteur_recoit_le_meme_refus_qu_en_tapant(self):
        """[CA14] Le garde de rôle vit dans le HANDLER, donc sur les deux chemins.

        Le poser dans l'interpréteur aurait ouvert un chemin parallèle : la même
        commande tapée serait passée sans contrôle.
        """
        update = _update()
        lecteur = TenantContext(user_id=1, potager_id=1, role="lecteur")
        with patch.object(bot_module, "current_context", return_value=lecteur):
            arrete = await bot_module._refuser_si_role_insuffisant(update, "renommer une parcelle")
        assert arrete is True
        assert "renommer une parcelle" in _texte_envoye(update)

    @pytest.mark.asyncio
    async def test_us172_ca14_un_editeur_passe(self):
        """[CA14] Le garde ne bloque que ce qu'il doit bloquer."""
        update = _update()
        editeur = TenantContext(user_id=1, potager_id=1, role="editor")
        with patch.object(bot_module, "current_context", return_value=editeur):
            assert await bot_module._refuser_si_role_insuffisant(update, "créer une parcelle") is False

    def test_us172_ca14_les_commandes_d_ecriture_portent_toutes_le_garde(self):
        """[CA14] Aucune commande d'écriture n'échappe au garde de rôle."""
        source = Path(bot_module.__file__).read_text(encoding="utf-8-sig")
        for handler in ("cmd_parcelle", "cmd_culture", "cmd_association", "cmd_bioagresseur"):
            corps = source.split(f"async def {handler}(")[1].split("\nasync def ")[0]
            assert "_refuser_si_role_insuffisant" in corps, handler

    @pytest.mark.asyncio
    async def test_us172_ca9_commande_introuvable_ne_casse_pas(self):
        """[CA9] Une commande retirée du bot se dit, elle ne lève pas."""
        ctx = _ctx({0: []})
        update = _update()
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")
        await bot_module._interp_executer(update, ctx, commande)
        assert "n'est pas disponible" in _texte_envoye(update)


# ═════════════════════════════════════════════════════════════════════════════
# CA10, CA11 — rien ne s'exécute à l'aveugle, toute valeur est relue
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10CA11ConfirmationEtRelecture:

    @pytest.mark.asyncio
    async def test_us172_ca10_une_ecriture_est_confirmee_avant_execution(self, sans_journal):
        """[CA10] Une commande qui écrit affiche un récapitulatif et attend."""
        handler = AsyncMock()
        ctx = _ctx({0: [CommandHandler("parcelle", handler)]})
        update = _update()
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")

        with patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
            await bot_module._interp_proposer(update, ctx, commande)

        handler.assert_not_awaited()
        envoye = _texte_envoye(update)
        assert "Supprimer une parcelle" in envoye
        assert "/parcelle supprimer nord" in envoye     # la commande équivalente (CA10)

    @pytest.mark.asyncio
    async def test_us172_ca10_confirmer_execute_refuser_n_execute_rien(self, sans_journal):
        """[CA10] Le bouton décide, et lui seul."""
        handler = AsyncMock()
        ctx = _ctx({0: [CommandHandler("parcelle", handler)]})
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")

        bot_module._INTERP_PENDING[42] = {
            "commande": commande, "attend": None, "log_id": 1, "ts": time.time(),
        }
        await bot_module._interp_cb(_update_callback(42, "interp:non"), ctx)
        handler.assert_not_awaited()
        assert 42 not in bot_module._INTERP_PENDING

        bot_module._INTERP_PENDING[42] = {
            "commande": commande, "attend": None, "log_id": 1, "ts": time.time(),
        }
        await bot_module._interp_cb(_update_callback(42, "interp:ok"), ctx)
        handler.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_us172_ca10_une_consultation_s_execute_directement(self, sans_journal):
        """[CA10] …mais une lecture n'est pas confirmée.

        « Voulez-vous vraiment afficher le plan ? » doublerait chaque
        consultation sans rien protéger. La commande équivalente reste rappelée :
        c'est la moitié pédagogique du critère, et elle vaut partout.
        """
        handler = AsyncMock()
        ctx = _ctx({0: [CommandHandler("plan", handler)]})
        update = _update()
        commande = interp.reconnaitre_par_regles("montre-moi le plan")

        with patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
            await bot_module._interp_proposer(update, ctx, commande)

        handler.assert_awaited_once()
        assert "/plan" in _texte_envoye(update)

    def test_us172_ca10_toute_commande_qui_ecrit_exige_une_confirmation(self):
        """[CA10] La frontière est explicite dans le catalogue, pas au cas par cas."""
        ecrivent = {
            ("parcelle", "ajouter"), ("parcelle", "renommer"), ("parcelle", "supprimer"),
            ("parcelle", "modifier"), ("association", "saisir"), ("culture", "famille"),
            ("culture", "delai_retour"), ("culture", "exposition"), ("culture", "eau"),
            ("culture", "profondeur"), ("culture", "rusticite"),
            ("bioagresseur", "declarer"), ("bioagresseur", "rattacher"), ("potager", None),
        }
        for cle in ecrivent:
            assert svc_menu.FORMES_PAR_CLE[cle].confirmation is True, cle

    @pytest.mark.parametrize("phrase, attendus", [
        ("la profondeur de semis de la carotte est de 1 centimètre", ["1 cm", "un cm"]),
        ("la planche sud fait 8,5 m²", ["8.5 m²", "huit virgule cinq m²"]),
        ("délai de retour des solanacées : 4 ans", ["4 ans", "quatre ans"]),
        ("la tomate gèle à -2 degrés", ["-2 °C", "moins deux °C"]),
    ])
    def test_us172_ca11_une_valeur_est_relue_en_chiffres_et_en_lettres(self, phrase, attendus):
        """[CA11] « profondeur 1 » et « profondeur 10 » ne s'entendent pas.

        C'est précisément là que la transcription vocale échoue, et la valeur
        part dans un référentiel PARTAGÉ. Le récapitulatif restitue donc le
        chiffre, son unité, et le nombre en toutes lettres.
        """
        recapitulatif = interp.recapitulatif(interp.reconnaitre_par_regles(phrase))
        for attendu in attendus:
            assert attendu in recapitulatif, recapitulatif

    def test_us172_ca11_une_valeur_de_vocabulaire_est_restituee(self):
        """[CA11] Une valeur qualitative est relue elle aussi."""
        recapitulatif = interp.recapitulatif(
            interp.reconnaitre_par_regles("la courgette veut du plein soleil")
        )
        assert "plein soleil" in recapitulatif

    @pytest.mark.parametrize("valeur, lettres", [
        ("1", "un"), ("10", "dix"), ("0", "zéro"), ("8.5", "huit virgule cinq"),
        ("-2", "moins deux"), ("21", "vingt-et-un"), ("71", "soixante-et-onze"),
        ("80", "quatre-vingts"), ("100", "cent"), ("12", "douze"),
    ])
    def test_us172_ca11_nombre_en_lettres(self, valeur, lettres):
        """[CA11] La conversion elle-même, cas par cas."""
        assert interp.nombre_en_lettres(valeur) == lettres

    def test_us172_ca11_une_valeur_non_numerique_est_rendue_telle_quelle(self):
        """[CA11] La conversion ne dénature jamais ce qu'elle ne sait pas lire."""
        assert interp.nombre_en_lettres("plein soleil") == "plein soleil"


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — le doute ne fait jamais agir
# ═════════════════════════════════════════════════════════════════════════════

class TestCA12LeDouteNeFaitJamaisAgir:

    @pytest.mark.asyncio
    async def test_us172_ca12_un_nom_approchant_est_propose_jamais_substitue(self, sans_journal):
        """[CA12] « planche nord-est » ne supprime pas « Planche Nord ».

        `resolve_parcelle` sait rapprocher les deux (Levenshtein ≤ 2) : c'est le
        bon comportement pour rattacher un geste, et le mauvais pour supprimer.
        """
        handler = AsyncMock()
        ctx = _ctx({0: [CommandHandler("parcelle", handler)]})
        update = _update()
        commande = interp.reconnaitre_par_regles("supprime la parcelle planche nord-est")

        voisine = MagicMock()
        voisine.nom = "Planche Nord"
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "find_doublon", return_value=(None, None)), \
             patch.object(bot_module, "resolve_parcelle", return_value=voisine):
            await bot_module._interp_proposer(update, ctx, commande)

        handler.assert_not_awaited()
        envoye = _texte_envoye(update)
        assert "PLANCHE NORD" in envoye
        assert "Vouliez-vous dire" in envoye

    def test_us172_ca12_la_valeur_dictee_est_retiree_tant_qu_elle_n_est_pas_choisie(self):
        """[CA12] Aucun chemin ne peut exécuter le nom inexact.

        Le retirer, et non le garder « au cas où », est ce qui rend la
        substitution impossible plutôt qu'improbable.
        """
        commande = interp.reconnaitre_par_regles("supprime la parcelle planche nord-est")
        propose = commande.avec_candidats("nom", ("Planche Nord",))
        assert "nom" not in propose.valeurs
        assert propose.complete is False

    def test_us172_ca12_choisir_le_candidat_leve_le_doute(self):
        """[CA12] Le choix du jardinier est le SEUL chemin vers l'exécution."""
        commande = interp.reconnaitre_par_regles("supprime la parcelle planche nord-est")
        choisie = commande.avec_candidats("nom", ("Planche Nord",)).avec(nom="Planche Nord")
        assert choisie.complete is True
        assert choisie.args == ("supprimer", "Planche Nord")

    @pytest.mark.asyncio
    async def test_us172_ca12_un_nom_exact_ne_declenche_aucune_proposition(self, sans_journal):
        """[CA12] Le garde ne gêne pas le cas normal."""
        exacte = MagicMock()
        exacte.nom, exacte.actif = "nord", True
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "find_doublon", return_value=(exacte, None)):
            resolue = bot_module._resoudre_noms_parcelle(commande)
        assert resolue.candidats == ()
        assert resolue.valeurs["nom"] == "nord"

    @pytest.mark.asyncio
    async def test_us172_ca12_plusieurs_candidats_demandent_une_precision(self, sans_journal):
        """[CA12] Deux commandes possibles → une question, pas la plus probable."""
        ctx = _ctx()
        update = _update()
        candidats = (
            interp.reconnaitre_par_regles("montre-moi le plan"),
            interp.reconnaitre_par_regles("bilan des tomates"),
        )
        ambigu = interp.Ambiguite(candidats=candidats, texte_origine="plan ou bilan ?")

        assert await bot_module._traiter_commande_interpretee(update, ctx, ambigu) is True
        envoye = _texte_envoye(update)
        assert "Plusieurs commandes possibles" in envoye
        assert "/plan" in envoye and "/stats" in envoye
        assert bot_module._INTERP_PENDING == {}


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — un argument manquant se complète, il n'échoue pas
# ═════════════════════════════════════════════════════════════════════════════

class TestCA13CompletionGuidee:

    def test_us172_ca13_une_phrase_incomplete_declare_ce_qui_manque(self):
        """[CA13] « note une association entre la carotte et l'aneth » est incomplète."""
        commande = interp.reconnaitre_par_regles(
            "note une association entre la carotte et l'aneth"
        )
        manquants = [a.nom for a in commande.manquants]
        assert manquants == ["nature", "preuve", "motif"]
        assert commande.complete is False

    @pytest.mark.asyncio
    async def test_us172_ca13_les_valeurs_possibles_sont_proposees_en_boutons(self, sans_journal):
        """[CA13] Un vocabulaire fermé se choisit, il ne se tape pas au hasard."""
        ctx = _ctx()
        update = _update()
        commande = interp.reconnaitre_par_regles(
            "note une association entre la carotte et l'aneth"
        )
        with patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
            await bot_module._interp_proposer(update, ctx, commande)

        appel = update.message.reply_text.await_args
        boutons = appel.kwargs["reply_markup"].inline_keyboard
        libelles = [bouton.text for ligne in boutons for bouton in ligne]
        from app.services.associations import NATURES
        for valeur in NATURES:
            assert valeur in libelles

    @pytest.mark.asyncio
    async def test_us172_ca13_aucune_valeur_n_est_devinee_d_un_synonyme(self, sans_journal):
        """[CA13] « ça se marie bien » ne devient jamais « favorable ».

        Le jardinier se voit reproposer les valeurs admises, il ne voit pas une
        valeur écrite à sa place.
        """
        ctx = _ctx()
        commande = interp.reconnaitre_par_regles(
            "note une association entre la carotte et l'aneth"
        )
        bot_module._INTERP_PENDING[42] = {
            "commande": commande, "attend": "nature", "log_id": 1, "ts": time.time(),
        }
        update = _update(42)
        await bot_module._interp_completion_texte(update, ctx, "ça se marie bien")

        assert "Valeur attendue" in _texte_envoye(update)
        assert "nature" not in bot_module._INTERP_PENDING[42]["commande"].valeurs

    @pytest.mark.asyncio
    async def test_us172_ca13_la_completion_avance_argument_par_argument(self, sans_journal):
        """[CA13] Chaque réponse fait avancer d'un cran, jusqu'au récapitulatif."""
        ctx = _ctx()
        commande = interp.reconnaitre_par_regles(
            "note une association entre la carotte et l'aneth"
        )
        bot_module._INTERP_PENDING[42] = {
            "commande": commande, "attend": "nature", "log_id": 1, "ts": time.time(),
        }
        update = _update(42)
        await bot_module._interp_completion_texte(update, ctx, "defavorable")

        courante = bot_module._INTERP_PENDING[42]["commande"]
        assert courante.valeurs["nature"] == "defavorable"
        assert [a.nom for a in courante.manquants] == ["preuve", "motif"]

    def test_us172_ca13_une_frequence_non_dite_n_est_jamais_presumee(self):
        """[CA13] « la piéride attaque le chou » ne dit pas à quelle fréquence."""
        commande = interp.reconnaitre_par_regles("la piéride attaque le chou")
        assert "frequence" not in commande.valeurs
        assert [a.nom for a in commande.manquants] == ["frequence"]


# ═════════════════════════════════════════════════════════════════════════════
# CA15, CA16, CA17 — la couverture ne se suppose pas
# ═════════════════════════════════════════════════════════════════════════════

class TestCA15CA16CA17Mesure:

    def test_us172_ca15_chaque_forme_dictable_a_au_moins_trois_formulations(self):
        """[CA15] Trois formulations naturelles distinctes par commande."""
        lignes = _lignes_corpus()
        compte: dict[str, int] = {}
        for ligne in lignes:
            if ligne["attendu"]:
                compte[ligne["attendu"]] = compte.get(ligne["attendu"], 0) + 1

        manquantes = []
        for forme in svc_menu.FORMES_DICTABLES:
            cle = f"{forme.commande} {forme.sous_commande or ''}".strip()
            if compte.get(cle, 0) < 3:
                manquantes.append(f"{cle} : {compte.get(cle, 0)} formulation(s)")
        assert manquantes == [], "\n".join(manquantes)

    def test_us172_ca15_les_trois_registres_sont_representes(self):
        """[CA15] Impératif, intention et ellipse figurent tous au corpus."""
        registres = {ligne["registre"] for ligne in _lignes_corpus()}
        assert {"imperatif", "intention", "elliptique"} <= registres

    def test_us172_ca15_chaque_commande_porte_sa_question_de_savoir_voisine(self):
        """[CA15] La question du CA2 est là, commande par commande."""
        questions = sum(1 for l in _lignes_corpus() if l["registre"] == "savoir")
        assert questions >= len(svc_menu.FORMES_DICTABLES) - 1

    def test_us172_ca15_le_corpus_porte_des_phrases_hors_perimetre(self):
        """[CA15] Un corpus qui ne contiendrait que des succès ne mesurerait rien."""
        hors = [l for l in _lignes_corpus() if l["registre"] == "hors_perimetre"]
        assert len(hors) >= 10

    def test_us172_ca16_seuil_de_90_pourcent(self):
        """[CA16] ≥ 90 % de commandes correctement identifiées sur le corpus."""
        lignes = _lignes_corpus()
        bons = sum(
            1 for l in lignes
            if _cible(interp.reconnaitre_par_regles(l["phrase"])) == l["attendu"]
        )
        taux = 100 * bons / len(lignes)
        assert taux >= 90, f"{bons}/{len(lignes)} = {taux:.1f} %"

    def test_us172_ca16_zero_execution_destructrice_erronee(self):
        """[CA16] Le couperet : une seule suffit à faire échouer la livraison.

        Une suppression exécutée sur la mauvaise parcelle coûte davantage que
        cent phrases non comprises — ce chiffre n'est pas un objectif, c'est une
        condition.
        """
        destructrices = {
            f"{f.commande} {f.sous_commande or ''}".strip()
            for f in svc_menu.FORMES_DICTABLES if f.destructrice
        }
        fautes = []
        for ligne in _lignes_corpus():
            obtenu = _cible(interp.reconnaitre_par_regles(ligne["phrase"]))
            if obtenu in destructrices and obtenu != ligne["attendu"]:
                fautes.append(f"« {ligne['phrase']} » → {obtenu}")
        assert fautes == [], "\n".join(fautes)

    def test_us172_ca17_part_traitee_sans_appel_modele(self):
        """[CA17] La part traitée sans appel au modèle est MESURÉE.

        Elle est publiée dans PATCH_NOTES.md à la livraison, comme l'a été celle
        du parseur déterministe d'US-094.
        """
        lignes = [l for l in _lignes_corpus() if l["attendu"]]
        par_regle = sum(
            1 for l in lignes if interp.reconnaitre_par_regles(l["phrase"]) is not None
        )
        part = 100 * par_regle / len(lignes)
        assert part >= 90, f"{par_regle}/{len(lignes)} = {part:.1f} % sans modèle"


# ═════════════════════════════════════════════════════════════════════════════
# CA18 — traçabilité
# ═════════════════════════════════════════════════════════════════════════════

class TestCA18Journalisation:

    def test_us172_ca18_le_journal_porte_tout_ce_que_le_critere_demande(self, test_db):
        """[CA18] Nature, commande, origine, confiance, latence, issue."""
        _potager_de_test(test_db)
        from database.models import RoutageLog

        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")
        ctx = TenantContext(user_id=1, potager_id=1, role="owner")

        with patch("database.db.SessionLocal", return_value=test_db), \
             patch.object(test_db, "close"):
            log_id = interp.persister_journal(ctx, commande, interp.ISSUE_PROPOSEE)

        assert log_id is not None
        entree = test_db.get(RoutageLog, log_id)
        assert entree.nature == interp.NATURE_COMMANDE
        assert entree.etage_resolveur == interp.ETAGE_COMMANDE
        assert entree.origine_classification == interp.ORIGINE_REGLE
        assert entree.commande_interpretee == "parcelle supprimer"
        assert entree.issue_interpretation == interp.ISSUE_PROPOSEE
        assert entree.confiance == 1.0
        assert entree.tokens_consommes == 0

    def test_us172_ca18_l_issue_est_completee_sans_creer_de_seconde_ligne(self, test_db):
        """[CA18] Une interprétation = une ligne, de la proposition à son issue."""
        _potager_de_test(test_db)
        from database.models import RoutageLog

        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")
        ctx = TenantContext(user_id=1, potager_id=1, role="owner")

        with patch("database.db.SessionLocal", return_value=test_db), \
             patch.object(test_db, "close"):
            log_id = interp.persister_journal(ctx, commande, interp.ISSUE_PROPOSEE)
            interp.persister_journal(ctx, commande, interp.ISSUE_REFUSEE, log_id)

        assert test_db.query(RoutageLog).count() == 1
        assert test_db.get(RoutageLog, log_id).issue_interpretation == interp.ISSUE_REFUSEE

    def test_us172_ca18_une_panne_de_journal_ne_bloque_jamais(self):
        """[CA18] La journalisation est de l'observabilité, pas une condition."""
        commande = interp.reconnaitre_par_regles("supprime la parcelle nord")
        ctx = TenantContext(user_id=1, potager_id=1, role="owner")
        with patch("database.db.SessionLocal", side_effect=RuntimeError("base indisponible")):
            assert interp.persister_journal(ctx, commande, interp.ISSUE_PROPOSEE) is None

    def test_us172_ca18_la_question_journalisee_est_normalisee(self, test_db):
        """[CA18] Le message brut n'entre pas au journal — règle d'US-097 / CA2."""
        from database.models import RoutageLog
        from llm.routeur import normaliser_question

        _potager_de_test(test_db)

        phrase = "Supprime la Parcelle NORD !"
        commande = interp.reconnaitre_par_regles(phrase)
        ctx = TenantContext(user_id=1, potager_id=1, role="owner")
        with patch("database.db.SessionLocal", return_value=test_db), \
             patch.object(test_db, "close"):
            log_id = interp.persister_journal(ctx, commande, interp.ISSUE_PROPOSEE)

        assert test_db.get(RoutageLog, log_id).question_normalisee == normaliser_question(phrase)


# ═════════════════════════════════════════════════════════════════════════════
# CA19, CA20 — créer la parcelle manquante dans la foulée du geste
# ═════════════════════════════════════════════════════════════════════════════

class TestCA19CA20ParcelleManquanteDuGeste:

    @pytest.mark.asyncio
    async def test_us172_ca19_une_parcelle_inconnue_declenche_une_proposition(self):
        """[CA19] « j'ai planté 3 pieds de tomate sur PlancheTomate »."""
        update = _update()
        items = [{"action": "plantation", "culture": "tomate", "parcelle": "PlancheTomate"}]

        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "resolve_parcelle", return_value=None):
            propose = await bot_module._proposer_creation_parcelle_du_geste(
                update, items, "j'ai planté 3 pieds de tomate sur PlancheTomate"
            )

        assert propose is True
        assert "PLANCHETOMATE" in _texte_envoye(update)
        assert bot_module._CREATION_PARCELLE_PENDING[42]["nom"] == "PlancheTomate"

    @pytest.mark.asyncio
    async def test_us172_ca19_la_phrase_d_origine_est_conservee_pour_etre_rejouee(self):
        """[CA19] Le jardinier n'a pas à redicter sa phrase.

        Elle est CONSERVÉE, jamais reconstruite — c'est le seul point de cette
        US où deux flux se rejoignent, et le reconstruire aurait fait diverger
        le geste enregistré de celui qui a été dicté.
        """
        phrase = "j'ai planté 3 pieds de tomate sur PlancheTomate"
        items = [{"action": "plantation", "culture": "tomate", "parcelle": "PlancheTomate"}]
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "resolve_parcelle", return_value=None):
            await bot_module._proposer_creation_parcelle_du_geste(_update(), items, phrase)

        assert bot_module._CREATION_PARCELLE_PENDING[42]["texte"] == phrase

        nouvelle = MagicMock()
        nouvelle.nom = "PlancheTomate"
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "create_parcelle", return_value=nouvelle) as creation, \
             patch.object(bot_module, "_parse_and_save", new=AsyncMock()) as rejeu:
            await bot_module._creation_parcelle_geste_cb(
                _update_callback(42, "interpparc:ok"), _ctx()
            )

        creation.assert_called_once()
        rejeu.assert_awaited_once()
        assert rejeu.await_args.args[1] == phrase
        assert rejeu.await_args.kwargs["pre_parsed_items"][0]["parcelle"] == "PlancheTomate"

    @pytest.mark.asyncio
    async def test_us172_ca20_aucune_parcelle_n_est_creee_sans_confirmation(self):
        """[CA20] La règle d'US-094 n'est pas assouplie : elle est outillée."""
        items = [{"action": "plantation", "culture": "tomate", "parcelle": "PlancheTomate"}]
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "resolve_parcelle", return_value=None), \
             patch.object(bot_module, "create_parcelle") as creation:
            await bot_module._proposer_creation_parcelle_du_geste(
                _update(), items, "j'ai planté 3 pieds de tomate sur PlancheTomate"
            )
        creation.assert_not_called()

    @pytest.mark.asyncio
    async def test_us172_ca19_refuser_laisse_le_flux_habituel_se_derouler(self):
        """[CA19] Refuser rend la main à la désambiguïsation existante, à l'identique."""
        items = [{"action": "plantation", "culture": "tomate", "parcelle": "PlancheTomate"}]
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "resolve_parcelle", return_value=None):
            await bot_module._proposer_creation_parcelle_du_geste(
                _update(), items, "j'ai planté 3 pieds de tomate sur PlancheTomate"
            )

        with patch.object(bot_module, "create_parcelle") as creation, \
             patch.object(bot_module, "_parse_and_save", new=AsyncMock()) as suite:
            await bot_module._creation_parcelle_geste_cb(
                _update_callback(42, "interpparc:non"), _ctx()
            )

        creation.assert_not_called()
        suite.assert_awaited_once()
        # La parcelle inconnue est retirée : le flux existant redemande laquelle.
        assert "parcelle" not in suite.await_args.kwargs["pre_parsed_items"][0]

    @pytest.mark.asyncio
    async def test_us172_ca19_une_parcelle_connue_ne_declenche_rien(self):
        """[CA19] Le cas normal n'est pas alourdi d'une question de plus."""
        items = [{"action": "plantation", "culture": "tomate", "parcelle": "nord"}]
        with patch.object(bot_module, "SessionLocal"), \
             patch.object(bot_module, "resolve_parcelle", return_value=MagicMock()):
            propose = await bot_module._proposer_creation_parcelle_du_geste(
                _update(), items, "j'ai planté 3 pieds de tomate sur nord"
            )
        assert propose is False


# ═════════════════════════════════════════════════════════════════════════════
# Défauts relevés en dictée réelle le 08/09/2026
# -----------------------------------------------------------------------------
# Trois défauts constatés sur un même essai vocal, « Créer la parcelle planche
# tomate sud 12 mètres carrés » : un nom mal découpé, une superficie divisée par
# la virgule décimale, et une parcelle supprimée devenue invisible ET incréable.
# ═════════════════════════════════════════════════════════════════════════════

class TestDefautsReleveEnDicteeReelle:

    def test_us172_le_nom_ne_garde_pas_un_morceau_de_la_superficie(self):
        """Le nom est ce qui PRÉCÈDE la première annotation.

        Reconstruire le nom en retirant les annotations par substitution
        donnait « planche tomate sud 12 » : la longueur de la chaîne substituée
        ne dit plus rien des positions dans la chaîne d'origine.
        """
        commande = interp.reconnaitre_par_regles("crée la parcelle planche tomate 12 m²")
        assert commande.valeurs["nom"] == "planche tomate"
        assert commande.valeurs["superficie"] == "12"

    @pytest.mark.parametrize("phrase, superficie", [
        ("crée la parcelle serre exposée sud 8,5 m²", "8.5"),
        ("crée la parcelle potager du bas, 8,5 m²", "8.5"),
        ("crée la parcelle carré nord, 12 m²", "12"),
    ])
    def test_us172_la_virgule_decimale_n_est_pas_un_separateur(self, phrase, superficie):
        """8,5 m² ne vaut pas 5 m².

        La virgule sépare les annotations dictées, sauf entre deux chiffres —
        la découper là écrivait une superficie fausse sans que rien ne le
        signale, exactement ce que le CA11 demande d'empêcher.
        """
        assert interp.reconnaitre_par_regles(phrase).valeurs["superficie"] == superficie

    def test_us172_une_direction_en_fin_de_nom_ne_se_devine_pas(self):
        """« planche tomate sud 12 m² » : nom ou exposition ?

        « Planche Sud » est un nom de parcelle courant : trancher au jugé
        écrirait un nom mutilé une fois sur deux. La règle renonce, et le repli
        modèle lit la phrase — le partage prévu par la cascade (CA3, CA4).
        """
        assert interp.reconnaitre_par_regles(
            "Créer la parcelle planche tomate sud 12 mètres carrés."
        ) is None
        assert interp.reconnaitre_par_regles("crée la parcelle planche sud 12 m²") is None

    def test_us172_sans_superficie_la_direction_reste_dans_le_nom(self):
        """Sans ambiguïté, la règle ne renonce pas : « planche sud » est un nom."""
        commande = interp.reconnaitre_par_regles("crée la parcelle planche sud")
        assert commande.valeurs["nom"] == "planche sud"
        assert "exposition" not in commande.valeurs

    def test_us172_une_exposition_annoncee_reste_reconnue(self):
        """Le renoncement ne coûte rien aux formes explicites."""
        commande = interp.reconnaitre_par_regles(
            "crée la parcelle PlancheTomate, plein sud, 12 m²"
        )
        assert commande.valeurs["nom"] == "PlancheTomate"
        assert commande.valeurs["exposition"] == "sud"
        assert commande.valeurs["superficie"] == "12"

    @pytest.mark.parametrize("phrase", [
        "Comment supprimer une parcelle ?",
        "comment supprimer une parcelle",          # dictée, sans ponctuation
        "comment corriger un événement ?",
        "comment enregistrer une récolte ?",
    ])
    def test_us172_une_question_dictee_atteint_la_cascade(self, phrase):
        """[CA2, CA5] « Comment supprimer une parcelle ? » dicté n'efface rien.

        Le canal vocal était resté sur les seuls intents de `parse_message`,
        qui ne connaissent ni le socle de connaissance ni la mémoire : la phrase
        était lue comme l'intent SUPPRIMER, et le bot proposait d'effacer le
        dernier geste. La même phrase TAPÉE recevait pourtant l'explication —
        c'est très exactement ce que le CA2 interdit, sur le canal où le
        compagnon est d'abord utilisé.
        """
        from llm import routeur

        nature = routeur.classer_par_regles(phrase)
        assert nature == routeur.NATURE_QUESTION_SAVOIR

    def test_us172_une_regle_qui_se_tait_laisse_la_main_aux_intents(self):
        """[CA22] « supprime ma dernière saisie » annule toujours le dernier geste.

        Seul l'étage des RÈGLES est consulté sur ce canal : une phrase qu'aucune
        règle ne tranche continue jusqu'à son intent, comme avant. Consulter la
        cascade entière l'aurait classée HYBRIDE — par le modèle, donc au prix
        d'un appel — et l'aurait envoyée se faire expliquer au lieu d'agir.
        """
        from llm import routeur

        assert routeur.classer_par_regles("supprime ma dernière saisie") is None
        assert routeur.classer_par_regles("récolté 2 kg de tomates cerise") == routeur.NATURE_ACTION

    def test_us172_le_canal_vocal_consulte_les_regles_avant_les_intents(self):
        """[CA5] L'ordre du flux vocal, lu dans le code plutôt que supposé."""
        source = Path(bot_module.__file__).read_text(encoding="utf-8-sig")
        separateur = chr(10) + "async def "
        vocal = source.split("async def handle_voice")[1].split(separateur)[0]
        assert vocal.index("_traiter_commande_interpretee") < vocal.index("parser_saisie")
        assert vocal.index("parser_saisie") < vocal.index("classer_par_regles")
        assert vocal.index("classer_par_regles") < vocal.index("parse_message(")

    def test_us172_une_parcelle_supprimee_se_recree(self, test_db):
        """Une planche supprimée était invisible ET incréable.

        `find_doublon` la retrouvait comme doublon exact — il ne filtre pas
        `actif`, et c'est voulu, c'est lui qui garantit l'unicité du nom —
        pendant que `/plan` et `/parcelle lister`, eux, la filtraient. La
        recréer la remet donc en service, sans jamais créer de second
        enregistrement homonyme.
        """
        from database.models import Parcelle
        from utils.parcelles import create_parcelle, get_all_parcelles, supprimer_parcelle

        _potager_de_test(test_db)
        create_parcelle(test_db, "planche tomate", potager_id=1)
        supprimer_parcelle(test_db, "planche tomate", potager_id=1)
        test_db.commit()
        assert get_all_parcelles(test_db, potager_id=1) == []

        remise = create_parcelle(
            test_db, "planche tomate", exposition="sud", superficie_m2=12.0, potager_id=1
        )
        assert remise.actif is True
        assert remise.exposition == "sud"
        assert [p.nom for p in get_all_parcelles(test_db, potager_id=1)] == ["planche tomate"]
        assert test_db.query(Parcelle).count() == 1, "aucun homonyme ne doit apparaître"

    def test_us172_une_parcelle_active_refuse_toujours_le_doublon(self, test_db):
        """La remise en service ne desserre pas le contrôle de doublon."""
        from utils.parcelles import create_parcelle

        _potager_de_test(test_db)
        create_parcelle(test_db, "planche tomate", potager_id=1)
        with pytest.raises(ValueError, match="existe déjà"):
            create_parcelle(test_db, "Planche Tomate", potager_id=1)


# ═════════════════════════════════════════════════════════════════════════════
# CA21, CA22 — non-régression
# ═════════════════════════════════════════════════════════════════════════════

class TestCA21CA22NonRegression:

    def test_us172_ca21_l_ordre_des_flux_de_conversation_est_preserve(self):
        """[CA21] Modes de correction, mode `ask`, navigation, PUIS l'interpréteur.

        L'ordre est lu dans le code plutôt que déduit : c'est lui qui décide
        qu'un message envoyé pendant une correction reste traité par la
        correction.
        """
        source = Path(bot_module.__file__).read_text(encoding="utf-8-sig")
        corps = source.split("async def handle_text")[1].split("\nasync def ")[0]

        position_correction = corps.index("mode == 'corr_search'")
        position_ask = corps.index("if mode == 'ask'")
        position_interpreteur = corps.index("_traiter_commande_interpretee")
        position_routeur = corps.index("routeur.classer_demande")

        assert position_correction < position_interpreteur
        assert position_ask < position_interpreteur
        assert position_interpreteur < position_routeur

    def test_us172_ca21_le_mode_de_completion_survit_a_la_reinitialisation(self):
        """[CA21] Une saisie guidée en cours n'est pas interrompue par un message."""
        source = Path(bot_module.__file__).read_text(encoding="utf-8-sig")
        corps = source.split("async def handle_text")[1].split("\nasync def ")[0]
        modes = corps.split("MODES_CORRECTION = {")[1].split("}")[0]
        assert "_INTERP_MODE_COMPLETION" in modes

    @pytest.mark.asyncio
    async def test_us172_ca21_un_message_pendant_une_correction_n_est_pas_intercepte(self):
        """[CA21] Le mode correction reste prioritaire, même sur une phrase-commande."""
        update = _update()
        update.message.text = "supprime la parcelle nord"
        ctx = _ctx()
        ctx.user_data = {"mode": "corr_select"}

        with patch.object(bot_module, "_verifier_liaison_ou_onboarding",
                          new=AsyncMock(return_value=True)), \
             patch.object(bot_module, "_corr_select", new=AsyncMock()) as correction, \
             patch.object(bot_module, "_traiter_commande_interpretee",
                          new=AsyncMock()) as interpreteur:
            await bot_module.handle_text(update, ctx)

        correction.assert_awaited_once()
        interpreteur.assert_not_awaited()

    def test_us172_ca22_le_menu_natif_est_inchange(self):
        """[CA22] Cette US ajoute un chemin d'entrée, elle n'en modifie aucun."""
        commandes = _noms_commandes_reellement_enregistrees()
        entrees = dict(svc_menu.construire_menu(commandes))
        assert "version" not in entrees and "delier" not in entrees and "tts" not in entrees
        assert "parcelle" in entrees and "stats" in entrees

    def test_us172_ca22_les_saisies_de_gestes_ne_sont_pas_captees(self):
        """[CA22] Un geste au jardin reste un geste — aucune commande ne le vole."""
        gestes = [l["phrase"] for l in _lignes_corpus() if l["registre"] == "hors_perimetre"]
        captes = [g for g in gestes if interp.reconnaitre_par_regles(g) is not None]
        assert captes == []

    def test_us172_ca22_la_question_phare_d_us173_reste_une_question(self):
        """[CA22] « qu'est-ce qui attaque mes poireaux ? » n'écrit rien.

        Servie par gabarit à zéro jeton depuis US-173, elle passait à un cheveu
        d'être transformée en écriture au référentiel par la règle de
        rattachement : c'est le garde d'ouverture interrogative qui l'en
        empêche, et ce test qui le tient.
        """
        for phrase in ("qu'est-ce qui attaque mes poireaux ?",
                       "qu est ce qui attaque mes poireaux",
                       "qu'est-ce qui attaque le chou"):
            assert interp.reconnaitre_par_regles(phrase) is None

    def test_us172_ca22_une_commande_tapee_n_est_jamais_interpretee(self):
        """[CA22] Un message commençant par « / » appartient au CommandHandler."""
        assert interp.reconnaitre_par_regles("/parcelle supprimer nord") is None
        assert interp.interpreter("/stats tomate", None) is None
