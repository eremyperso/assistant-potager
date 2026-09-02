"""
tests/test_us067_famille_botanique.py
[US-067] Externaliser la famille botanique des cultures et rendre la rotation calculable

Couverture des critères d'acceptance CA1 → CA14, à l'exception de deux CA qui ne
se prêtent pas à un test pytest :

  - CA2 (pré-remplissage) : garanti par `migrations/migration_v37.sql`
    (`UPDATE ... WHERE famille_id IS NULL`), jamais rejoué en test — les tests
    tournent sur SQLite en mémoire construit depuis `database/models.py`
    (`Base.metadata.create_all`), pas depuis les migrations SQL Postgres.
  - CA8 (suppression de `frontend/src/lib/familles.js`) : changement frontend,
    vérifié par la suppression du fichier et l'absence de toute référence
    restante (`familleDe`, `lib/familles`) dans `frontend/src`.

CA11 (couverture des tests) et CA9 (non-régression) sont satisfaits par ce
fichier lui-même et par le passage de la suite existante sans modification.
"""
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.services import familles as svc_familles
from app.services.context import TenantContext
from app.services.parcelles import creer_culture_config
from database.models import CultureConfig, FamilleBotanique
from utils.culture_resolve import normaliser_culture

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_AUTRE_POTAGER = TenantContext(user_id=2, potager_id=2, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


def _seed_culture_config(db, nom, type_organe="reproducteur", potager_id=None, famille=None):
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    if famille is not None:
        cfg.famille_rel = famille
    db.add(cfg)
    db.commit()
    return cfg


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — table de référence : le libellé n'est écrit qu'une seule fois
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1TableDeReference:
    def test_deux_cultures_partagent_la_meme_fiche_famille(self, db):
        """[CA1] Deux cultures rattachées à la même famille lisent le même libellé —
        le corriger sur la famille le corrige pour les deux, par construction (FK),
        sans qu'aucune des deux fiches culture_config ne porte le texte."""
        solanacee = FamilleBotanique(nom="Solanacée", nom_normalise="solanacee", delai_retour_annees=4)
        db.add(solanacee)
        db.commit()
        _seed_culture_config(db, "tomate", famille=solanacee)
        _seed_culture_config(db, "poivron", famille=solanacee)

        solanacee.nom = "Solanacées (corrigé)"
        db.commit()

        familles = svc_familles.familles_par_culture(db, CTX)
        assert familles["tomate"] == "Solanacées (corrigé)"
        assert familles["poivron"] == "Solanacées (corrigé)"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — culture sans famille : reste utilisable partout
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3FamilleFacultative:
    def test_culture_sans_famille_absente_du_dict_pas_en_erreur(self, db):
        """[CA3] Une culture sans famille n'apparaît simplement pas dans l'index —
        aucune exception, à l'appelant d'appliquer son repli d'affichage ("Autres")."""
        _seed_culture_config(db, "topinambour")

        familles = svc_familles.familles_par_culture(db, CTX)

        assert "topinambour" not in familles

    def test_creation_et_lecture_de_la_fiche_culture_inchangees(self, db):
        """[CA3, CA9] Une fiche sans famille reste lisible/consultable normalement."""
        cfg = _seed_culture_config(db, "topinambour", type_organe="végétatif")

        assert cfg.famille_id is None
        assert cfg.famille_rel is None
        assert cfg.type_organe_recolte == "végétatif"


# ═════════════════════════════════════════════════════════════════════════════
# CA4 / CA6 / CA7 — corriger_famille_culture (service)
# ═════════════════════════════════════════════════════════════════════════════

class TestCorrigerFamilleCulture:
    def test_ca4_confirme_ancienne_et_nouvelle_famille(self, db):
        """[CA4] Retourne l'ancienne famille (None si absente) et applique la nouvelle."""
        _seed_culture_config(db, "pâtisson")

        fiches, ancienne = svc_familles.corriger_famille_culture(db, "pâtisson", "Cucurbitacée")

        assert ancienne is None
        assert len(fiches) == 1
        assert fiches[0].famille_rel.nom == "Cucurbitacée"

    def test_ca4_deuxieme_correction_rapporte_l_ancienne_valeur(self, db):
        """[CA4] Une deuxième correction rapporte la valeur précédente, pas None."""
        _seed_culture_config(db, "pâtisson")
        svc_familles.corriger_famille_culture(db, "pâtisson", "Autres (erreur)")

        _, ancienne = svc_familles.corriger_famille_culture(db, "pâtisson", "Cucurbitacée")

        assert ancienne == "Autres (erreur)"

    def test_ca4_culture_inconnue_leve_lookuperror(self, db):
        """[CA4] Pas de fiche culture_config existante → LookupError, jamais de
        création implicite (type_organe_recolte est NOT NULL, la famille seule
        ne peut pas fonder une fiche)."""
        with pytest.raises(LookupError):
            svc_familles.corriger_famille_culture(db, "inconnue", "Solanacée")

    def test_ca6_insensible_casse_et_accents_sur_la_culture(self, db):
        """[CA6] « CELERI » retrouve la fiche enregistrée sous « céleri »."""
        _seed_culture_config(db, "céleri")

        fiches, _ = svc_familles.corriger_famille_culture(db, "CELERI", "Apiacée")

        assert fiches[0].nom == "céleri"

    def test_ca6_insensible_casse_et_accents_sur_la_famille(self, db):
        """[CA6] « cucurbitacee » (sans accent) rejoint la même fiche que « Cucurbitacée »."""
        _seed_culture_config(db, "courgette")
        _seed_culture_config(db, "pâtisson")
        svc_familles.corriger_famille_culture(db, "courgette", "Cucurbitacée")

        fiches, _ = svc_familles.corriger_famille_culture(db, "pâtisson", "cucurbitacee")

        assert fiches[0].famille_id == db.query(CultureConfig).filter_by(nom="courgette").first().famille_id
        assert db.query(FamilleBotanique).count() == 1  # aucune deuxième fiche créée

    def test_ca7_corrige_toutes_les_fiches_du_meme_nom_tous_potagers(self, db):
        """[CA7] La famille est un fait, pas une préférence de jardinier.
        `culture_config.nom` porte une contrainte UNIQUE globale : deux potagers
        ne peuvent donc jamais avoir chacun une fiche de MÊME orthographe exacte
        — mais rien n'empêche deux orthographes distinctes (casse/accents) de
        coexister, une par potager, chacun l'ayant dictée en premier dans son
        propre référentiel (`cultures_connues` est scopé au potager). La
        correction doit rattraper les deux, insensible à la casse/aux accents
        (CA6), pour ne jamais laisser deux potagers classer la même culture
        différemment."""
        _seed_culture_config(db, "topinambour", potager_id=1)
        _seed_culture_config(db, "Topinambour", potager_id=2)  # même culture, autre orthographe

        fiches, _ = svc_familles.corriger_famille_culture(db, "topinambour", "Astéracée")

        assert len(fiches) == 2
        assert {f.potager_id for f in fiches} == {1, 2}
        assert all(f.famille_rel.nom == "Astéracée" for f in fiches)

        # [CA5] Chaque potager relit la même famille, sans copie locale.
        cible = normaliser_culture("topinambour")
        assert svc_familles.familles_par_culture(db, CTX)[cible] == "Astéracée"
        assert svc_familles.familles_par_culture(db, CTX_AUTRE_POTAGER)[cible] == "Astéracée"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — immédiat, pas de copie mémorisée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5Immediat:
    def test_familles_par_culture_relit_apres_correction(self, db):
        """[CA5] Le regroupement lit la donnée à chaque appel : pas de valeur
        périmée après une correction dans le même processus."""
        cible = normaliser_culture("pâtisson")
        _seed_culture_config(db, "pâtisson")
        assert cible not in svc_familles.familles_par_culture(db, CTX)

        svc_familles.corriger_famille_culture(db, "pâtisson", "Cucurbitacée")

        assert svc_familles.familles_par_culture(db, CTX)[cible] == "Cucurbitacée"


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — création à la volée n'exige pas la famille
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10CreationSansFamille:
    def test_creer_culture_config_sans_famille(self, db):
        """[CA10, CA9] creer_culture_config (clarification végétatif/reproducteur)
        continue de fonctionner sans aucune référence à la famille."""
        cfg = creer_culture_config(db, CTX, "topinambour", "végétatif")

        assert cfg.famille_id is None


# ═════════════════════════════════════════════════════════════════════════════
# CA12 / CA13 / CA14 — délai de retour, porté par la famille
# ═════════════════════════════════════════════════════════════════════════════

class TestDelaiRetour:
    def test_ca12_get_or_create_famille_nouvelle_delai_null(self, db):
        """[CA12] Une famille tout juste créée (via une correction sur une culture
        dont la famille était inconnue du référentiel) n'a pas de délai deviné."""
        famille = svc_familles.get_or_create_famille(db, "Cactacée")

        assert famille.delai_retour_annees is None

    def test_ca12_corriger_delai_retour_confirme_ancienne_valeur(self, db):
        """[CA12, CA14] Corrige le délai et rapporte l'ancienne valeur."""
        famille = FamilleBotanique(nom="Solanacée", nom_normalise="solanacee", delai_retour_annees=3)
        db.add(famille)
        db.commit()

        famille_maj, ancien = svc_familles.corriger_delai_retour(db, "Solanacée", 4)

        assert ancien == 3
        assert famille_maj.delai_retour_annees == 4

    def test_ca12_famille_inconnue_leve_lookuperror(self, db):
        with pytest.raises(LookupError):
            svc_familles.corriger_delai_retour(db, "Inconnue", 3)

    def test_ca13_famille_sans_delai_ne_bloque_aucune_lecture(self, db):
        """[CA13] Une famille sans délai n'empêche aucun affichage : la culture
        reste résolue normalement, la donnée manquante ne fait rien planter."""
        lamiacee = FamilleBotanique(nom="Lamiacée", nom_normalise="lamiacee", delai_retour_annees=None)
        db.add(lamiacee)
        db.commit()
        _seed_culture_config(db, "thym", famille=lamiacee)

        familles = svc_familles.familles_par_culture(db, CTX)

        assert familles["thym"] == "Lamiacée"
        assert lamiacee.delai_retour_annees is None

    def test_ca14_correction_vaut_pour_toutes_les_cultures_de_la_famille(self, db):
        """[CA14] Une seule correction de délai, appliquée à la famille, vaut
        aussitôt pour toutes les cultures qui s'y rattachent — sans les reprendre
        une à une, puisqu'elles partagent la même fiche via la FK."""
        solanacee = FamilleBotanique(nom="Solanacée", nom_normalise="solanacee", delai_retour_annees=3)
        db.add(solanacee)
        db.commit()
        _seed_culture_config(db, "tomate", famille=solanacee)
        _seed_culture_config(db, "poivron", famille=solanacee)
        _seed_culture_config(db, "pomme de terre", famille=solanacee)

        svc_familles.corriger_delai_retour(db, "solanacee", 4)

        cultures = db.query(CultureConfig).filter(CultureConfig.famille_id == solanacee.id).all()
        assert len(cultures) == 3
        assert all(c.famille_rel.delai_retour_annees == 4 for c in cultures)


# ═════════════════════════════════════════════════════════════════════════════
# Handler bot : /culture famille · /culture delai_retour
# ═════════════════════════════════════════════════════════════════════════════

class TestCmdCultureHandler:
    def _make_update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    def _make_ctx(self, args):
        ctx = MagicMock()
        ctx.args = args
        return ctx

    @pytest.mark.asyncio
    async def test_sans_argument_affiche_usage(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx([])

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Usage" in texte

    @pytest.mark.asyncio
    async def test_sous_commande_inconnue_affiche_usage(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["bidule"])

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Usage" in texte

    @pytest.mark.asyncio
    async def test_famille_args_insuffisants(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["famille", "pâtisson"])  # manque la famille

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Usage" in texte

    @pytest.mark.asyncio
    async def test_ca4_famille_succes_confirme_ancien_et_nouveau(self):
        """[CA4] La commande confirme l'ancienne et la nouvelle valeur."""
        from bot import cmd_culture

        fiche_mock = MagicMock()
        fiche_mock.famille_rel.nom = "Cucurbitacée"
        update = self._make_update()
        ctx = self._make_ctx(["famille", "pâtisson", "Cucurbitacée"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_familles.corriger_famille_culture",
                   return_value=([fiche_mock], "Autres")) as mock_corr:
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            mock_corr.assert_called_once_with(ANY, "pâtisson", "Cucurbitacée")
            texte = update.message.reply_text.call_args[0][0]
            assert "Autres" in texte
            assert "Cucurbitacée" in texte

    @pytest.mark.asyncio
    async def test_famille_avec_espaces_reconstituee(self):
        """Un nom de famille à plusieurs mots (ctx.args[2:]) est reconstitué."""
        from bot import cmd_culture

        fiche_mock = MagicMock()
        fiche_mock.famille_rel.nom = "Petit pois précoce"
        update = self._make_update()
        ctx = self._make_ctx(["famille", "petitpois", "Petit", "pois", "précoce"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_familles.corriger_famille_culture",
                   return_value=([fiche_mock], None)) as mock_corr:
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            mock_corr.assert_called_once_with(ANY, "petitpois", "Petit pois précoce")

    @pytest.mark.asyncio
    async def test_famille_culture_inconnue(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["famille", "inconnue", "Solanacée"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_familles.corriger_famille_culture", side_effect=LookupError("inconnue")):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            texte = update.message.reply_text.call_args[0][0]
            assert "Culture inconnue" in texte

    @pytest.mark.asyncio
    async def test_delai_retour_args_insuffisants(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["delai_retour", "Solanacée"])  # manque le nombre d'années

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Usage" in texte

    @pytest.mark.asyncio
    async def test_delai_retour_valeur_non_entiere(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["delai_retour", "Solanacée", "quatre"])

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "entier" in texte.lower()

    @pytest.mark.asyncio
    async def test_delai_retour_valeur_negative(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["delai_retour", "Solanacée", "-1"])

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "entier" in texte.lower()

    @pytest.mark.asyncio
    async def test_ca14_delai_retour_succes_confirme_ancien_et_nouveau(self):
        """[CA14] La commande confirme l'ancien délai et le nouveau."""
        from bot import cmd_culture

        famille_mock = MagicMock()
        famille_mock.nom = "Solanacée"
        update = self._make_update()
        ctx = self._make_ctx(["delai_retour", "Solanacée", "4"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_familles.corriger_delai_retour",
                   return_value=(famille_mock, 3)) as mock_corr:
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            mock_corr.assert_called_once_with(ANY, "Solanacée", 4)
            texte = update.message.reply_text.call_args[0][0]
            assert "3 ans" in texte
            assert "4 ans" in texte

    @pytest.mark.asyncio
    async def test_delai_retour_famille_jamais_renseignee(self):
        """[CA13] Ancien délai None → affiché "non renseigné", pas "None"."""
        from bot import cmd_culture

        famille_mock = MagicMock()
        famille_mock.nom = "Lamiacée"
        update = self._make_update()
        ctx = self._make_ctx(["delai_retour", "Lamiacée", "2"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_familles.corriger_delai_retour",
                   return_value=(famille_mock, None)):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            texte = update.message.reply_text.call_args[0][0]
            assert "non renseigné" in texte
            assert "None" not in texte

    @pytest.mark.asyncio
    async def test_delai_retour_famille_inconnue(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["delai_retour", "Inconnue", "3"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_familles.corriger_delai_retour", side_effect=LookupError("Inconnue")):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            texte = update.message.reply_text.call_args[0][0]
            assert "Famille inconnue" in texte
