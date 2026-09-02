"""
tests/test_us164_fiche_culture_courte.py
[US-164] Restituer une fiche culture courte au bot sur commande, sans aucun jeton

Couverture des critères d'acceptance CA1 → CA12, à une exception près :

  - CA11 (aucune date, fenêtre de semis ou durée) : garanti structurellement,
    puisque `culture_config` ne porte aucune colonne de calendrier (vérifié par
    `TestCA8CA9Frontieres.test_us161_aucun_attribut_de_calendrier` dans
    `test_us161_attributs_agronomiques.py`) — la fiche ne peut restituer un
    champ qui n'existe pas en base.

CA12 et CA14 (couverture des tests) sont satisfaits par ce fichier lui-même.
"""
import socket
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.services import attributs_culture as svc_attributs
from app.services import fiche_culture as svc_fiche
from app.services.fiche_culture import FicheCourte
from database.models import CultureConfig, FamilleBotanique, ReferentielSource


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


def _seed_culture(db, nom, type_organe="reproducteur", potager_id=None, famille=None, **attributs):
    config = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    if famille is not None:
        config.famille_rel = famille
    for champ, valeur in attributs.items():
        setattr(config, champ, valeur)
    db.add(config)
    db.commit()
    return config


def _seed_famille(db, nom, delai_retour_annees=None, source=None):
    famille = FamilleBotanique(
        nom=nom, nom_normalise=nom.lower(), delai_retour_annees=delai_retour_annees,
    )
    if source is not None:
        famille.source_rel = source
    db.add(famille)
    db.commit()
    return famille


def _seed_source(db, code="wikidata", attribution="Wikidata — CC0 1.0 Universal (domaine public)"):
    source = ReferentielSource(
        code=code, libelle=code, licence="CC0", attribution=attribution, partageable=True, importee=True,
    )
    db.add(source)
    db.commit()
    return source


# ═════════════════════════════════════════════════════════════════════════════
# CA3 / CA6 — service : gabarit assemblé depuis le référentiel, rien de rédigé
# ═════════════════════════════════════════════════════════════════════════════

class TestServiceFicheCourte:
    def test_us164_fiche_complete_assemble_famille_et_attributs(self, db):
        """[Gherkin: Fiche complète en zéro jeton] Famille (US-067) et les
        quatre attributs (US-161) sont assemblés dans une seule fiche."""
        source = _seed_source(db)
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4, source=source)
        _seed_culture(
            db, "tomate", famille=solanacee,
            exposition="plein soleil", besoin_eau="élevé",
            profondeur_semis_cm=1.0, rusticite_min_c=-2.0,
        )

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert fiche.culture == "tomate"
        assert fiche.famille == "Solanacée"
        assert fiche.delai_retour_annees == 4
        assert len(fiche.attributs) == len(svc_attributs.ATTRIBUTS)
        exposition = next(a for a in fiche.attributs if a.cle == "exposition")
        assert exposition.affichage == "plein soleil"

    def test_us164_fiche_partielle_restitue_ce_qui_est_connu(self, db):
        """[Gherkin: Fiche partielle] Seuls la famille et le besoin en eau sont
        renseignés : le reste se lit « non renseigné », rien n'est inventé."""
        solanacee = _seed_famille(db, "Chénopodiacée")
        _seed_culture(db, "blette", famille=solanacee, besoin_eau="moyen")

        fiche = svc_fiche.generer_fiche_courte(db, "blette")

        assert fiche.famille == "Chénopodiacée"
        lus = {a.cle: a for a in fiche.attributs}
        assert lus["besoin_eau"].affichage == "moyen"
        assert lus["exposition"].renseigne is False
        assert lus["exposition"].affichage == svc_attributs.NON_RENSEIGNE
        assert lus["profondeur_semis_cm"].renseigne is False
        assert lus["rusticite_min_c"].renseigne is False

    def test_us164_culture_sans_famille_reste_lisible(self, db):
        """[CA6] Une culture connue mais sans famille renseignée n'est pas une
        anomalie : la fiche se sert quand même, la famille se lit « non
        renseignée », jamais devinée."""
        _seed_culture(db, "topinambour", type_organe="végétatif")

        fiche = svc_fiche.generer_fiche_courte(db, "topinambour")

        assert fiche.famille is None
        assert fiche.delai_retour_annees is None

    def test_us164_culture_inconnue_leve_lookup_error(self, db):
        """[Gherkin: Culture inconnue du référentiel][CA5] Aucune fiche
        `culture_config` du tout : signalé, jamais une fiche voisine forcée."""
        with pytest.raises(LookupError):
            svc_fiche.generer_fiche_courte(db, "artichaut")

    def test_us164_nom_accentue_et_majuscule_resout_vers_la_meme_fiche(self, db):
        """[Gherkin: Nom accentué ou en majuscules][CA12] Casse/accents
        indifférents — même normalisation que partout ailleurs dans le
        référentiel (`utils.culture_resolve.normaliser_culture`)."""
        _seed_culture(db, "céleri", besoin_eau="élevé")

        fiche = svc_fiche.generer_fiche_courte(db, "CELERI")

        assert fiche.culture == "céleri"
        assert next(a for a in fiche.attributs if a.cle == "besoin_eau").affichage == "élevé"


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — description agronomique, renseignée ou honnêtement incomplète
# ═════════════════════════════════════════════════════════════════════════════

class TestCA13DescriptionAgronomique:
    def test_us164_description_agronomique_renseignee_est_restituee(self, db):
        """[Gherkin: Description agronomique renseignée][CA13] Champ de texte
        libre indépendant des quatre attributs de conduite d'US-161."""
        _seed_culture(db, "tomate", description_agronomique="port indéterminé")

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert fiche.description_agronomique == "port indéterminé"

    def test_us164_description_agronomique_absente_est_none(self, db):
        """[Gherkin: Description agronomique absente][CA13] Non devinée, non
        omise du modèle : `None` au service, au bot d'en faire « incomplète »."""
        _seed_culture(db, "poivron")

        fiche = svc_fiche.generer_fiche_courte(db, "poivron")

        assert fiche.description_agronomique is None

    def test_us164_description_agronomique_ne_bloque_pas_le_reste_de_la_fiche(self, db):
        """[CA13] Un champ libre en plus ne dégrade rien de ce qui existait déjà."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(
            db, "tomate", famille=solanacee, description_agronomique="port indéterminé",
            exposition="plein soleil",
        )

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert fiche.famille == "Solanacée"
        assert next(a for a in fiche.attributs if a.cle == "exposition").affichage == "plein soleil"
        assert fiche.description_agronomique == "port indéterminé"


class TestCA13CommandeBotDescriptionAgronomique:
    """[CA13][CA14] Le handler Telegram — affichage ou mention « incomplète »."""

    def _make_update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 123
        return update

    def _make_ctx(self, args):
        ctx = MagicMock()
        ctx.args = args
        return ctx

    def _fiche(self, description_agronomique):
        return FicheCourte(
            culture="tomate", famille=None, famille_attribution=None,
            delai_retour_annees=None, description_agronomique=description_agronomique,
            attributs=tuple(
                svc_attributs.AttributLu(
                    cle=a.cle, libelle=a.libelle, valeur=None,
                    affichage=svc_attributs.NON_RENSEIGNE, source_code=None, attribution=None,
                )
                for a in svc_attributs.ATTRIBUTS
            ),
        )

    @pytest.mark.asyncio
    async def test_us164_bot_affiche_la_description_agronomique_renseignee(self):
        """[Gherkin: Description agronomique renseignée]"""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["tomate"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte",
                   return_value=self._fiche("port indéterminé")):
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "port indéterminé" in texte
        assert "incomplète" not in texte

    @pytest.mark.asyncio
    async def test_us164_bot_signale_la_description_agronomique_incomplete(self):
        """[Gherkin: Description agronomique absente][CA13] Jamais omise en
        silence, jamais comblée — même principe d'honnêteté que CA6."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["tomate"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", return_value=self._fiche(None)):
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Description : incomplète" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — attribution affichée avec la réponse
# ═════════════════════════════════════════════════════════════════════════════

class TestAttributions:
    def test_us164_attribution_de_la_famille_est_restituee(self, db):
        """[CA7] Une famille qui dérive d'une source d'import porte sa mention,
        même quand aucun attribut de conduite n'est renseigné."""
        source = _seed_source(db, code="wikidata", attribution="Wikidata — CC0 1.0 Universal (domaine public)")
        solanacee = _seed_famille(db, "Solanacée", source=source)
        config = _seed_culture(db, "tomate", famille=solanacee)
        config.famille_source_id = source.id
        db.commit()

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert "Wikidata — CC0 1.0 Universal (domaine public)" in fiche.attributions

    def test_us164_attributions_dedupliquees_entre_famille_et_attributs(self, db):
        """[CA7] Une seule mention par source, même si elle couvre à la fois la
        famille et un attribut de conduite."""
        source = _seed_source(db, code="wikidata", attribution="Wikidata — CC0 1.0 Universal (domaine public)")
        solanacee = _seed_famille(db, "Solanacée", source=source)
        config = _seed_culture(db, "tomate", famille=solanacee, exposition="plein soleil")
        config.famille_source_id = source.id
        config.exposition_source_id = source.id
        db.commit()

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert fiche.attributions.count("Wikidata — CC0 1.0 Universal (domaine public)") == 1

    def test_us164_aucune_attribution_sans_source(self, db):
        """Une culture sans aucune donnée importée n'a rien à créditer."""
        _seed_culture(db, "topinambour")

        fiche = svc_fiche.generer_fiche_courte(db, "topinambour")

        assert fiche.attributions == []


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — aucun appel réseau, aucun appel au modèle
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9AucunAppelModele:
    def test_us164_generation_sans_appel_reseau(self, db, monkeypatch):
        """[Gherkin: Fiche complète en zéro jeton][CA9] Toute tentative de
        sortie réseau fait échouer le test."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la génération de fiche (CA9)")

        _seed_culture(db, "courgette", exposition="plein soleil")
        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        fiche = svc_fiche.generer_fiche_courte(db, "courgette")

        assert fiche.culture == "courgette"

    def test_us164_generation_n_appelle_pas_la_passerelle_llm(self, db):
        """[CA9] Ni parsing, ni complétion, ni reformulation — le module n'a
        aucun chemin vers un modèle, y compris sur une culture inconnue."""
        _seed_culture(db, "courgette", exposition="plein soleil")

        with patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            svc_fiche.generer_fiche_courte(db, "courgette")
            with pytest.raises(LookupError):
                svc_fiche.generer_fiche_courte(db, "artichaut")

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 / CA2 / CA5 / CA6 / CA7 — le handler Telegram /fiche
# ═════════════════════════════════════════════════════════════════════════════

class TestCommandeBotFiche:
    def _make_update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 123
        return update

    def _make_ctx(self, args):
        ctx = MagicMock()
        ctx.args = args
        return ctx

    @pytest.mark.asyncio
    async def test_us164_bot_restitue_une_fiche_complete(self):
        """[Gherkin: Fiche complète en zéro jeton] La réponse tient sur un
        message unique, lisible sur téléphone."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["tomate"])

        fiche = FicheCourte(
            culture="tomate", famille="Solanacée", famille_attribution=None,
            delai_retour_annees=4, description_agronomique=None,
            attributs=tuple(
                svc_attributs.AttributLu(
                    cle=a.cle, libelle=a.libelle, valeur="X",
                    affichage="plein soleil" if a.cle == "exposition" else "élevé",
                    source_code=None, attribution=None,
                )
                for a in svc_attributs.ATTRIBUTS
            ),
        )
        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", return_value=fiche) as mock_gen:
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

            mock_gen.assert_called_once_with(ANY, "tomate")
        texte = update.message.reply_text.call_args[0][0]
        assert "tomate" in texte
        assert "Solanacée" in texte
        assert "4 ans" in texte
        # [CA2] Une dizaine de lignes maximum, lisibles sur téléphone.
        assert texte.count("\n") < 12

    @pytest.mark.asyncio
    async def test_us164_bot_reconstitue_un_nom_de_culture_a_plusieurs_mots(self):
        """[CA1] `ctx.args` peut porter plusieurs tokens (« petit pois »)."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["petit", "pois"])

        fiche = FicheCourte(
            culture="petit pois", famille=None, famille_attribution=None,
            delai_retour_annees=None, description_agronomique=None,
            attributs=tuple(
                svc_attributs.AttributLu(
                    cle=a.cle, libelle=a.libelle, valeur=None,
                    affichage=svc_attributs.NON_RENSEIGNE, source_code=None, attribution=None,
                )
                for a in svc_attributs.ATTRIBUTS
            ),
        )
        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", return_value=fiche) as mock_gen:
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

            mock_gen.assert_called_once_with(ANY, "petit pois")

    @pytest.mark.asyncio
    async def test_us164_bot_signale_honnetement_une_culture_inconnue(self):
        """[Gherkin: Culture inconnue du référentiel][CA5] Message d'absence
        explicite, sans proposer de fiche voisine."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["artichaut"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", side_effect=LookupError("artichaut")):
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "n'ai pas de fiche" in texte
        assert "artichaut" in texte

    @pytest.mark.asyncio
    async def test_us164_bot_attribut_absent_affiche_non_renseigne(self):
        """[Gherkin: Fiche partielle][CA6] Les attributs absents se lisent
        « non renseigné », jamais omis ni comblés."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["blette"])

        attributs = [
            svc_attributs.AttributLu(
                cle="besoin_eau", libelle="Besoin en eau", valeur="moyen",
                affichage="moyen", source_code=None, attribution=None,
            )
        ] + [
            svc_attributs.AttributLu(
                cle=a.cle, libelle=a.libelle, valeur=None,
                affichage=svc_attributs.NON_RENSEIGNE, source_code=None, attribution=None,
            )
            for a in svc_attributs.ATTRIBUTS if a.cle != "besoin_eau"
        ]
        fiche = FicheCourte(
            culture="blette", famille="Chénopodiacée", famille_attribution=None,
            delai_retour_annees=None, description_agronomique=None,
            attributs=tuple(attributs),
        )
        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", return_value=fiche):
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert texte.count(svc_attributs.NON_RENSEIGNE) == len(svc_attributs.ATTRIBUTS) - 1

    @pytest.mark.asyncio
    async def test_us164_bot_famille_non_renseignee_est_dite_telle_quelle(self):
        """[CA6] Absence de famille explicitement affichée, pas omise."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["topinambour"])

        fiche = FicheCourte(
            culture="topinambour", famille=None, famille_attribution=None,
            delai_retour_annees=None, description_agronomique=None,
            attributs=tuple(
                svc_attributs.AttributLu(
                    cle=a.cle, libelle=a.libelle, valeur=None,
                    affichage=svc_attributs.NON_RENSEIGNE, source_code=None, attribution=None,
                )
                for a in svc_attributs.ATTRIBUTS
            ),
        )
        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", return_value=fiche):
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Famille : non renseignée" in texte

    @pytest.mark.asyncio
    async def test_us164_bot_attribution_affichee_avec_la_reponse(self):
        """[CA7 / US-166] La mention de source accompagne la réponse."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["tomate"])
        attribution = "Plant variety data from Wind River Greens (…), CC BY 4.0"

        fiche = FicheCourte(
            culture="tomate", famille=None, famille_attribution=None,
            delai_retour_annees=None, description_agronomique=None,
            attributs=tuple(
                svc_attributs.AttributLu(
                    cle=a.cle, libelle=a.libelle,
                    valeur="plein soleil" if a.cle == "exposition" else None,
                    affichage="plein soleil" if a.cle == "exposition" else svc_attributs.NON_RENSEIGNE,
                    source_code="wind_river_greens" if a.cle == "exposition" else None,
                    attribution=attribution if a.cle == "exposition" else None,
                )
                for a in svc_attributs.ATTRIBUTS
            ),
        )
        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", return_value=fiche):
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert attribution in texte
        assert "wind_river_greens" not in texte

    @pytest.mark.asyncio
    async def test_us164_bot_sans_argument_affiche_l_usage(self):
        """Aucun nom de culture fourni : message d'usage, aucune requête base."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx([])

        with patch("bot.svc_fiche_culture.generer_fiche_courte") as mock_gen:
            await cmd_fiche(update, ctx)

        mock_gen.assert_not_called()
        texte = update.message.reply_text.call_args[0][0]
        assert "Usage" in texte

    @pytest.mark.asyncio
    async def test_us164_bot_n_appelle_jamais_le_modele(self):
        """[CA9] Ni sur une fiche connue, ni sur une culture inconnue."""
        from bot import cmd_fiche
        update = self._make_update()
        ctx = self._make_ctx(["artichaut"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_fiche_culture.generer_fiche_courte", side_effect=LookupError("artichaut")), \
             patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            MockSession.return_value = MagicMock()

            await cmd_fiche(update, ctx)

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA4 / CA12 — non-régression du routage : aucune restitution spontanée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4NonRegressionRoutage:
    """[CA4][Gherkin: Aucune restitution spontanée][CA12][Gherkin: Aucune
    régression du routage] Cette US n'ajoute qu'une commande préfixée — les
    flux de `handle_text` (correction, mode question, saisie d'action) ne sont
    pas modifiés."""

    def test_us164_fiche_n_est_pas_appelee_depuis_handle_text(self):
        """[CA4] Le module `fiche_culture` n'est référencé nulle part dans
        `handle_text` — la restitution ne peut donc pas s'y déclencher, par
        construction, sans avoir à mocker tout le flux de saisie."""
        import inspect
        import bot

        source = inspect.getsource(bot.handle_text)

        assert "fiche_culture" not in source
        assert "generer_fiche_courte" not in source
        assert "cmd_fiche" not in source

    def test_us164_commande_fiche_enregistree_avec_le_garde_de_liaison(self):
        """[CA1] `/fiche` passe par le même point d'enregistrement unique que
        toutes les commandes métier (US-045) — aucun chemin d'exception créé
        pour cette US."""
        import bot

        assert "fiche" not in bot._COMMANDES_SANS_GARDE_LIAISON

    @pytest.mark.asyncio
    async def test_us164_flux_de_correction_inchange(self, db):
        """[Gherkin: Aucune régression du routage] `_corr_start` — point
        d'entrée du mode correction — démarre toujours son dialogue exactement
        comme avant cette US : /fiche ne l'a pas touché."""
        import bot
        from app.services.context import default_context, set_current_context

        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 123
        ctx = MagicMock()
        ctx.user_data = {}

        set_current_context(default_context())
        try:
            with patch("bot.SessionLocal", return_value=db):
                await bot._corr_start(update, ctx)
        finally:
            set_current_context(default_context())

        update.message.reply_text.assert_awaited_once()
        assert ctx.user_data.get("mode") == "corr_search"
