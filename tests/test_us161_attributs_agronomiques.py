"""
tests/test_us161_attributs_agronomiques.py
[US-161] Enrichir la configuration de culture des attributs agronomiques de fiche

Couverture des critères d'acceptance CA1 → CA12, à une exception près :

  - CA1, volet migration : l'ajout des huit colonnes est garanti par
    `migrations/migration_v39.sql`, jamais rejoué en test — les tests tournent
    sur SQLite en mémoire construit depuis `database/models.py`
    (`Base.metadata.create_all`), pas depuis les migrations Postgres. Ce que ce
    fichier vérifie côté modèle est le miroir exact de ce que la migration écrit
    côté schéma.

CA12 (couverture des tests) est satisfait par ce fichier lui-même.
"""
import socket
from datetime import datetime, date
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.services import attributs_culture as svc_attributs
from app.services import import_referentiel as svc_import
from app.services import referentiel_sources as svc_sources
from app.services.attributs_culture import ValeurHorsVocabulaireError
from app.services.referentiel_sources import LicenceHorsSocleError
from database.models import CultureConfig, Evenement, Parcelle


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


@pytest.fixture
def manifeste_attributs() -> dict:
    """Manifeste sous licence du socle portant le seul bloc `cultures_attributs`.

    Les valeurs y sont arbitraires et n'engagent aucune agronomie : ce sont des
    valeurs de test, pas un pré-remplissage — le CA10 interdit précisément qu'un
    chiffre agronomique naisse ailleurs que d'une source ou du jardinier."""
    return {
        "source": {
            "code": "wikidata",
            "libelle": "Wikidata",
            "licence": "CC0",
            "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
            "url": "https://www.wikidata.org/",
            "partageable": True,
        },
        "cultures_attributs": [
            {
                "culture": "carotte",
                "exposition": "plein soleil",
                "besoin_eau": "moyen",
                "profondeur_semis_cm": 1,
                "rusticite_min_c": -5,
            },
            {
                "culture": "courgette",
                "exposition": "plein soleil",
                "besoin_eau": "élevé",
            },
        ],
    }


def _seed_culture(db, nom, type_organe="reproducteur", potager_id=None, **attributs):
    config = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    for champ, valeur in attributs.items():
        setattr(config, champ, valeur)
    db.add(config)
    db.commit()
    return config


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — le modèle : des attributs de conduite, tous nullables, rien de supprimé
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Modele:
    def test_us161_les_quatre_attributs_existent_et_sont_nullables(self, db):
        """[CA1] Une culture peut naître sans aucun attribut agronomique : ils
        sont tous nullables, aucun n'est obligatoire à la création."""
        config = _seed_culture(db, "topinambour", type_organe="végétatif")

        assert config.exposition is None
        assert config.besoin_eau is None
        assert config.profondeur_semis_cm is None
        assert config.rusticite_min_c is None

    def test_us161_aucune_colonne_existante_n_est_supprimee_ni_renommee(self, db):
        """[CA1] L'invariant de migration incrémentale non cassante : les quatre
        informations d'avant l'US restent lisibles sous le même nom."""
        config = _seed_culture(
            db, "tomate",
            description_agronomique="port indéterminé",
            espacement="50 × 60 cm",
            surface_m2=0.3,
        )

        assert config.type_organe_recolte == "reproducteur"
        assert config.description_agronomique == "port indéterminé"
        assert config.espacement == "50 × 60 cm"
        assert config.surface_m2 == 0.3

    def test_us161_les_quatre_attributs_se_lisent_apres_ecriture(self, db):
        """[CA1] Aller-retour en base : ce qui est écrit se relit tel quel."""
        _seed_culture(
            db, "carotte", type_organe="végétatif",
            exposition="plein soleil", besoin_eau="moyen",
            profondeur_semis_cm=1.0, rusticite_min_c=-5.0,
        )
        db.expire_all()

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition == "plein soleil"
        assert relue.besoin_eau == "moyen"
        assert relue.profondeur_semis_cm == 1.0
        assert relue.rusticite_min_c == -5.0


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — vocabulaire fermé, pas du texte libre
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2VocabulaireFerme:
    @pytest.mark.parametrize("saisie,attendu", [
        ("plein soleil", "plein soleil"),
        ("Plein Soleil", "plein soleil"),
        ("PLEIN  SOLEIL", "plein soleil"),
        ("mi-ombre", "mi-ombre"),
        ("mi ombre", "mi-ombre"),
        ("Mi-Ombre", "mi-ombre"),
        ("ombre", "ombre"),
    ])
    def test_us161_exposition_normalisee_vers_sa_valeur_canonique(self, saisie, attendu):
        """[CA2] Casse, accents et tirets sont indifférents à la SAISIE, mais la
        valeur STOCKÉE est toujours canonique — c'est ce qui rend le filtre et le
        tri possibles, au lieu de renormaliser à l'affichage."""
        assert svc_attributs.normaliser_valeur("exposition", saisie) == attendu

    @pytest.mark.parametrize("saisie,attendu", [
        ("faible", "faible"),
        ("Moyen", "moyen"),
        ("élevé", "élevé"),
        ("eleve", "élevé"),
        ("ELEVE", "élevé"),
    ])
    def test_us161_besoin_eau_normalise_vers_sa_valeur_canonique(self, saisie, attendu):
        """[CA2] Même règle sur le besoin en eau — « eleve » sans accent atteint
        « élevé », mais c'est « élevé » qui est stocké."""
        assert svc_attributs.normaliser_valeur("besoin_eau", saisie) == attendu

    def test_us161_valeur_hors_vocabulaire_refusee(self):
        """[CA2][Gherkin: Valeur hors vocabulaire fermé refusée] « au soleil le
        matin » n'est pas une exposition : la valeur est refusée."""
        with pytest.raises(ValeurHorsVocabulaireError) as err:
            svc_attributs.normaliser_valeur("exposition", "au soleil le matin")

        # Le message énonce ce qui est admis : c'est lui que le jardinier lit.
        assert "plein soleil" in str(err.value)

    def test_us161_besoin_eau_hors_vocabulaire_refuse(self):
        """[CA2] Un besoin en eau « beaucoup » n'entre pas davantage."""
        with pytest.raises(ValeurHorsVocabulaireError):
            svc_attributs.normaliser_valeur("besoin_eau", "beaucoup")

    def test_us161_valeur_refusee_laisse_l_attribut_inchange(self, db):
        """[CA2][Gherkin] L'attribut conserve sa valeur précédente : le refus a
        lieu AVANT toute écriture, jamais après une écriture partielle."""
        _seed_culture(db, "courgette", exposition="mi-ombre")

        with pytest.raises(ValeurHorsVocabulaireError):
            svc_attributs.corriger_attribut(db, "courgette", "exposition", "au soleil le matin")

        db.expire_all()
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "courgette").first()
        assert relue.exposition == "mi-ombre"

    def test_us161_profondeur_accepte_la_virgule_decimale(self):
        """[CA2] Le jardinier tape « 1,5 » et non « 1.5 » — la saisie française
        est acceptée, la valeur stockée reste un nombre."""
        assert svc_attributs.normaliser_valeur("profondeur_semis_cm", "1,5") == 1.5

    def test_us161_profondeur_refuse_un_texte(self):
        """[CA2] Un attribut numérique n'accepte pas de texte libre non plus."""
        with pytest.raises(ValeurHorsVocabulaireError):
            svc_attributs.normaliser_valeur("profondeur_semis_cm", "pas profond")

    @pytest.mark.parametrize("cle,valeur", [
        ("profondeur_semis_cm", 150),   # une profondeur de semis d'1,5 m
        ("profondeur_semis_cm", -3),
        ("rusticite_min_c", -80),
        ("rusticite_min_c", 60),
    ])
    def test_us161_valeur_numerique_invraisemblable_refusee(self, cle, valeur):
        """[CA2] Les bornes écartent la faute de frappe. Elles ne remplacent pas
        une source (CA10) : elles refusent l'absurde, pas l'infondé."""
        with pytest.raises(ValeurHorsVocabulaireError):
            svc_attributs.normaliser_valeur(cle, valeur)

    def test_us161_valeur_vide_efface_l_attribut(self):
        """[CA2/CA4] Effacer un attribut est légitime et bien plus honnête que
        de lui laisser une valeur fausse — `None` reste `None`."""
        assert svc_attributs.normaliser_valeur("exposition", "") is None
        assert svc_attributs.normaliser_valeur("profondeur_semis_cm", None) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — chaque valeur porte sa source ; aucun attribut orphelin
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3TracabiliteDeLaSource:
    def test_us161_une_correction_au_bot_porte_l_origine_saisie_manuelle(self, db):
        """[CA3] Une valeur saisie est tracée au même titre qu'une valeur
        importée : il n'existe aucune donnée sans origine."""
        _seed_culture(db, "carotte")

        svc_attributs.corriger_attribut(db, "carotte", "profondeur_semis_cm", 1)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        origine = svc_sources.get_source(db, svc_sources.SOURCE_SAISIE_MANUELLE)
        assert relue.profondeur_semis_source_id == origine.id

    def test_us161_une_valeur_importee_porte_l_origine_de_l_import(self, db, manifeste_attributs):
        """[CA3] L'import écrit l'origine en même temps que la valeur, sur le
        même attribut — jamais l'un sans l'autre."""
        _seed_culture(db, "carotte")

        svc_import.importer(db, manifeste_attributs)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        wikidata = svc_sources.get_source(db, "wikidata")
        assert relue.exposition_source_id == wikidata.id
        assert relue.besoin_eau_source_id == wikidata.id
        assert relue.profondeur_semis_source_id == wikidata.id
        assert relue.rusticite_min_source_id == wikidata.id

    def test_us161_aucun_attribut_orphelin_apres_import(self, db, manifeste_attributs):
        """[CA3] L'invariant vérifié par la migration : une valeur renseignée
        porte toujours son origine."""
        _seed_culture(db, "carotte")
        _seed_culture(db, "courgette")

        svc_import.importer(db, manifeste_attributs)

        for config in db.query(CultureConfig).all():
            for attribut in svc_attributs.ATTRIBUTS:
                if getattr(config, attribut.colonne) is not None:
                    assert getattr(config, attribut.colonne_source) is not None, (
                        f"{config.nom}.{attribut.cle} renseigné sans origine"
                    )

    def test_us161_effacer_un_attribut_efface_son_origine(self, db):
        """[CA3] Pas de valeur sans source, mais pas davantage de source sans
        valeur : une origine résiduelle rattacherait une source à du vide."""
        _seed_culture(db, "carotte")
        svc_attributs.corriger_attribut(db, "carotte", "exposition", "ombre")

        svc_attributs.corriger_attribut(db, "carotte", "exposition", "")

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition is None
        assert relue.exposition_source_id is None

    def test_us161_les_attributs_remontent_dans_les_donnees_derivees(self, db, manifeste_attributs):
        """[CA3 / US-166 CA4] « Cette source devient litigieuse, que faut-il
        retirer ? » doit rester une requête, y compris pour les attributs."""
        _seed_culture(db, "carotte")
        svc_import.importer(db, manifeste_attributs)

        derivees = svc_sources.donnees_derivees(db, "wikidata")

        colonnes = {ligne["colonne"] for ligne in derivees}
        assert "exposition_source_id" in colonnes
        assert "besoin_eau_source_id" in colonnes
        assert "profondeur_semis_source_id" in colonnes
        assert "rusticite_min_source_id" in colonnes

    def test_us161_la_source_est_restituee_a_la_lecture(self, db, manifeste_attributs):
        """[CA3] Une valeur doit pouvoir être défendue au jardinier : la lecture
        rend l'origine et son attribution, pas seulement la valeur."""
        _seed_culture(db, "carotte")
        svc_import.importer(db, manifeste_attributs)

        lus = {a.cle: a for a in svc_attributs.lire_attributs(db, "carotte")}

        assert lus["exposition"].source_code == "wikidata"
        assert "CC0" in lus["exposition"].attribution


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — un attribut non renseigné s'affiche comme non renseigné
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4NonRenseigne:
    def test_us161_culture_sans_aucun_attribut(self, db):
        """[CA4][Gherkin: Attribut non renseigné] Chaque attribut absent se lit
        « non renseigné » — aucune valeur devinée ni moyennée."""
        _seed_culture(db, "topinambour", type_organe="végétatif")

        lus = svc_attributs.lire_attributs(db, "topinambour")

        assert len(lus) == len(svc_attributs.ATTRIBUTS)
        for attribut in lus:
            assert attribut.valeur is None
            assert attribut.renseigne is False
            assert attribut.affichage == svc_attributs.NON_RENSEIGNE
            assert attribut.source_code is None

    def test_us161_un_attribut_absent_n_est_pas_omis_de_la_lecture(self, db):
        """[CA4] Le jardinier doit VOIR que l'application ne sait pas : un
        attribut absent est listé avec sa mention, jamais retiré de la fiche."""
        _seed_culture(db, "carotte", exposition="plein soleil")

        lus = {a.cle: a for a in svc_attributs.lire_attributs(db, "carotte")}

        assert lus["exposition"].affichage == "plein soleil"
        assert lus["profondeur_semis_cm"].affichage == svc_attributs.NON_RENSEIGNE
        assert lus["rusticite_min_c"].affichage == svc_attributs.NON_RENSEIGNE

    def test_us161_lecture_d_une_culture_inconnue(self, db):
        """[CA4] Une culture sans fiche n'est pas une culture aux attributs
        vides : elle est signalée, jamais inventée."""
        with pytest.raises(LookupError):
            svc_attributs.lire_attributs(db, "kiwano")

    def test_us161_valeur_numerique_formatee_avec_son_unite(self):
        """[CA4] Une profondeur nue serait ambiguë : l'unité accompagne toujours
        la valeur restituée."""
        assert svc_attributs.formater_valeur("profondeur_semis_cm", 1.0) == "1 cm"
        assert svc_attributs.formater_valeur("profondeur_semis_cm", 1.5) == "1.5 cm"
        assert svc_attributs.formater_valeur("rusticite_min_c", -5.0) == "-5 °C"
        assert svc_attributs.formater_valeur("rusticite_min_c", None) == svc_attributs.NON_RENSEIGNE


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — correction depuis le bot, sans livraison ni intervention en base
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5CorrectionService:
    def test_us161_correction_confirme_ancienne_et_nouvelle_valeur(self, db):
        """[CA5] La correction retourne l'avant et l'après — c'est ce que la
        commande confirme au jardinier."""
        _seed_culture(db, "courgette", exposition="mi-ombre")

        _, avant, apres = svc_attributs.corriger_attribut(
            db, "courgette", "exposition", "plein soleil"
        )

        assert avant == "mi-ombre"
        assert apres == "plein soleil"

    def test_us161_correction_d_un_attribut_jamais_renseigne(self, db):
        """[CA5/CA4] Renseigner pour la première fois : l'avant se lit « non
        renseigné », jamais une valeur inventée pour faire joli."""
        _seed_culture(db, "carotte")

        _, avant, apres = svc_attributs.corriger_attribut(
            db, "carotte", "profondeur_semis_cm", "1,5"
        )

        assert avant == svc_attributs.NON_RENSEIGNE
        assert apres == "1.5 cm"

    def test_us161_correction_sur_culture_inconnue(self, db):
        """[CA5] Une culture jamais dictée n'a pas de fiche : `type_organe_recolte`
        est NOT NULL, un attribut ne peut pas créer la fiche seul."""
        with pytest.raises(LookupError):
            svc_attributs.corriger_attribut(db, "kiwano", "exposition", "ombre")

    def test_us161_correction_touche_toutes_les_fiches_de_la_culture(self, db):
        """[CA5 / US-067 CA7] Un attribut agronomique est un fait, pas une
        préférence : corriger une seule fiche laisserait deux potagers avec deux
        vérités concurrentes."""
        _seed_culture(db, "courgette", potager_id=None)
        _seed_culture(db, "Courgette", potager_id=1)

        fiches, _, _ = svc_attributs.corriger_attribut(
            db, "COURGETTE", "besoin_eau", "élevé"
        )

        assert len(fiches) == 2
        assert all(f.besoin_eau == "élevé" for f in fiches)

    def test_us161_resolution_des_alias_de_commande(self):
        """[CA5] Le jardinier tape « eau », pas « besoin_eau » — les alias sont
        des synonymes de commande, jamais des colonnes."""
        assert svc_attributs.resoudre_cle("eau") == "besoin_eau"
        assert svc_attributs.resoudre_cle("Profondeur") == "profondeur_semis_cm"
        assert svc_attributs.resoudre_cle("rusticité") == "rusticite_min_c"
        with pytest.raises(KeyError):
            svc_attributs.resoudre_cle("couleur")


class TestCA5CorrectionBot:
    """[CA5] Le handler Telegram — aucune logique métier, seulement le dialogue."""

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
    async def test_us161_bot_corrige_et_confirme_les_deux_valeurs(self):
        """[CA5] La commande confirme l'ancienne ET la nouvelle valeur."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["exposition", "courgette", "plein", "soleil"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.corriger_attribut",
                   return_value=([MagicMock()], "mi-ombre", "plein soleil")) as mock_corr:
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            # La valeur à plusieurs mots est reconstituée depuis ctx.args[2:].
            mock_corr.assert_called_once_with(ANY, "courgette", "exposition", "plein soleil")
            texte = update.message.reply_text.call_args[0][0]
            assert "mi-ombre" in texte
            assert "plein soleil" in texte

    @pytest.mark.asyncio
    async def test_us161_bot_refuse_une_valeur_hors_vocabulaire(self):
        """[CA2/CA5] Le refus est expliqué au jardinier, et il apprend que rien
        n'a changé."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["exposition", "courgette", "au", "soleil", "le", "matin"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.corriger_attribut",
                   side_effect=ValeurHorsVocabulaireError("valeur non admise")):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            texte = update.message.reply_text.call_args[0][0]
            assert "conserve sa valeur précédente" in texte

    @pytest.mark.asyncio
    async def test_us161_bot_signale_une_culture_inconnue(self):
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["profondeur", "kiwano", "2"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.corriger_attribut", side_effect=LookupError("kiwano")):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            texte = update.message.reply_text.call_args[0][0]
            assert "Culture inconnue" in texte

    @pytest.mark.asyncio
    async def test_us161_bot_arguments_insuffisants_rappelle_les_valeurs_admises(self):
        """[CA2] Le message d'usage énonce le vocabulaire fermé : le jardinier
        n'a pas à le deviner."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["eau", "courgette"])  # valeur manquante

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "faible" in texte and "élevé" in texte

    @pytest.mark.asyncio
    async def test_us161_bot_lit_les_attributs_et_dit_les_absents(self):
        """[CA4] L'affichage porte « non renseigné » pour ce que l'application
        ne sait pas."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["attributs", "topinambour"])

        lus = [
            svc_attributs.AttributLu(
                cle=a.cle, libelle=a.libelle, valeur=None,
                affichage=svc_attributs.NON_RENSEIGNE,
                source_code=None, attribution=None,
            )
            for a in svc_attributs.ATTRIBUTS
        ]
        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.lire_attributs", return_value=lus):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

            texte = update.message.reply_text.call_args[0][0]
            assert texte.count(svc_attributs.NON_RENSEIGNE) == len(svc_attributs.ATTRIBUTS)

    @staticmethod
    def _lus(valeurs, attribution=None):
        """Construit un jeu d'AttributLu, renseignés ou non."""
        return [
            svc_attributs.AttributLu(
                cle=a.cle, libelle=a.libelle, valeur=valeur,
                affichage=svc_attributs.formater_valeur(a.cle, valeur),
                source_code="wind_river_greens" if valeur is not None else None,
                attribution=attribution if valeur is not None else None,
            )
            for a, valeur in zip(svc_attributs.ATTRIBUTS, valeurs)
        ]

    @pytest.mark.asyncio
    async def test_us161_le_message_ne_casse_pas_le_markdown_telegram(self):
        """Régression : le code de source « wind_river_greens » était affiché en
        italique, et Telegram refusait le message — « can't find end of the
        entity ». Aucun identifiant technique ne doit atteindre le rendu, et les
        entités doivent rester appariées."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["attributs", "tomate"])
        lus = self._lus(
            ["plein soleil", "élevé", None, None],
            attribution="Plant variety data from Wind River Greens (…), CC BY 4.0",
        )

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.lire_attributs", return_value=lus):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "_" not in texte, "un underscore nu casse le Markdown Telegram"
        assert texte.count("*") % 2 == 0, "entité gras non fermée"
        assert "wind_river_greens" not in texte

    @pytest.mark.asyncio
    async def test_us161_l_attribution_est_affichee_avec_la_reponse(self):
        """[US-166 / CA1] CC BY oblige à créditer la source AVEC la réponse, pas
        dans un README. Une mention par source, dédupliquée."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["attributs", "tomate"])
        attribution = "Plant variety data from Wind River Greens (…), CC BY 4.0"
        lus = self._lus(["plein soleil", "élevé", None, None], attribution=attribution)

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.lire_attributs", return_value=lus):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert attribution in texte
        # Deux attributs, une seule source : la mention n'est pas répétée.
        assert texte.count(attribution) == 1

    @pytest.mark.asyncio
    async def test_us161_aucune_mention_de_source_si_rien_n_est_renseigne(self):
        """Une culture sans aucune valeur n'a aucune source à créditer : pas de
        pied de message vide."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["attributs", "topinambour"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_attributs.lire_attributs", return_value=self._lus([None] * 4)):
            MockSession.return_value = MagicMock()

            await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Source" not in texte
        assert texte.count(svc_attributs.NON_RENSEIGNE) == len(svc_attributs.ATTRIBUTS)

    @pytest.mark.asyncio
    async def test_us161_sous_commande_inconnue_affiche_l_usage(self):
        """Une sous-commande qui n'est ni un attribut ni une commande connue
        retombe sur l'usage, sans rien écrire."""
        from bot import cmd_culture
        update = self._make_update()
        ctx = self._make_ctx(["couleur", "carotte", "orange"])

        await cmd_culture(update, ctx)

        texte = update.message.reply_text.call_args[0][0]
        assert "Usage" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la correction du jardinier prime sur toute reprise d'import
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6CorrectionPrimeSurImport:
    def test_us161_import_rejoue_conserve_la_correction(self, db, manifeste_attributs):
        """[CA6][Gherkin: La correction du jardinier prime sur l'import] Un
        référentiel importé décrit une moyenne nationale ; le jardinier décrit
        son terrain. Quand les deux divergent, c'est le terrain qui a raison."""
        _seed_culture(db, "carotte")
        svc_attributs.corriger_attribut(db, "carotte", "profondeur_semis_cm", 3)

        resultat = svc_import.importer(db, manifeste_attributs)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.profondeur_semis_cm == 3.0
        assert "carotte.profondeur_semis_cm" in resultat.attributs_preserves

    def test_us161_correction_d_un_attribut_ne_gele_pas_les_autres(self, db, manifeste_attributs):
        """[CA6/CA3] Une source PAR attribut, et non par ligne : corriger la
        profondeur ne doit pas interdire à l'import de renseigner l'exposition."""
        _seed_culture(db, "carotte")
        svc_attributs.corriger_attribut(db, "carotte", "profondeur_semis_cm", 3)

        svc_import.importer(db, manifeste_attributs)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.profondeur_semis_cm == 3.0        # la correction tient
        assert relue.exposition == "plein soleil"      # le reste s'enrichit

    def test_us161_import_rejoue_est_idempotent(self, db, manifeste_attributs):
        """[CA6 / US-166 CA5] Rejouer doit être banal : le second passage
        reconnaît sa propre donnée et ne la compte pas comme une réécriture."""
        _seed_culture(db, "carotte")
        svc_import.importer(db, manifeste_attributs)

        second = svc_import.importer(db, manifeste_attributs)

        assert second.attributs_ecrits == []
        assert second.attributs_preserves == []
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition == "plein soleil"

    def test_us161_import_rafraichit_sa_propre_donnee(self, db, manifeste_attributs):
        """[CA6] La contrepartie : ce que l'import a lui-même écrit, il peut le
        mettre à jour — sinon aucune correction de source ne se propagerait."""
        _seed_culture(db, "carotte")
        svc_import.importer(db, manifeste_attributs)

        manifeste_attributs["cultures_attributs"][0]["exposition"] = "mi-ombre"
        svc_import.importer(db, manifeste_attributs)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition == "mi-ombre"

    def test_us161_correction_posterieure_a_l_import_ecrase_l_import(self, db, manifeste_attributs):
        """[CA6] Le sens inverse : le jardinier corrige APRÈS un import, et c'est
        sa valeur qui reste — l'import ne verrouille rien."""
        _seed_culture(db, "carotte")
        svc_import.importer(db, manifeste_attributs)

        svc_attributs.corriger_attribut(db, "carotte", "exposition", "ombre")
        svc_import.importer(db, manifeste_attributs)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition == "ombre"


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — périmètre des dix cultures, aucune configuration créée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7PerimetreEtAucuneCreation:
    def test_us161_le_perimetre_compte_dix_cultures(self):
        """[CA7] Le périmètre est celui d'US-140 / CA1, mesuré et non intuité."""
        assert len(svc_attributs.CULTURES_PERIMETRE_INITIAL) == 10
        assert "tomate" in svc_attributs.CULTURES_PERIMETRE_INITIAL
        assert "blette" in svc_attributs.CULTURES_PERIMETRE_INITIAL

    def test_us161_appartenance_au_perimetre_insensible_a_la_casse(self):
        """[CA7] Même normalisation que partout ailleurs (casse, accents)."""
        assert svc_attributs.dans_perimetre_initial("Tomate") is True
        assert svc_attributs.dans_perimetre_initial("TOMATE") is True
        assert svc_attributs.dans_perimetre_initial("topinambour") is False

    def test_us161_culture_hors_perimetre_ignoree(self, db, manifeste_attributs):
        """[CA7] Le fichier source peut légitimement être plus large que le
        périmètre : ce qui déborde est compté, pas écrit."""
        _seed_culture(db, "topinambour", type_organe="végétatif")
        manifeste_attributs["cultures_attributs"].append(
            {"culture": "topinambour", "exposition": "mi-ombre"}
        )

        resultat = svc_import.importer(db, manifeste_attributs)

        assert "topinambour" in resultat.cultures_hors_perimetre
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "topinambour").first()
        assert relue.exposition is None

    def test_us161_import_ne_cree_aucune_configuration_de_culture(self, db, manifeste_attributs):
        """[CA7] 14 des 54 configurations mesurées ne portent aucun événement :
        peupler les écrans de cultures jamais cultivées est un risque constaté."""
        _seed_culture(db, "carotte")
        avant = db.query(CultureConfig).count()

        resultat = svc_import.importer(db, manifeste_attributs)

        assert db.query(CultureConfig).count() == avant
        # « courgette » est du périmètre mais absente de culture_config.
        assert "courgette" in resultat.cultures_ignorees

    def test_us161_une_culture_ignoree_n_est_pas_une_anomalie(self, db, manifeste_attributs):
        """[CA7] Le compteur est attendu : l'import n'échoue pas et poursuit."""
        _seed_culture(db, "carotte")

        resultat = svc_import.importer(db, manifeste_attributs)

        assert "carotte.exposition" in resultat.attributs_ecrits
        assert resultat.cultures_ignorees == ["courgette"]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 / CA9 — les frontières : aucun calendrier, aucune relation
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8CA9Frontieres:
    def test_us161_aucun_attribut_de_calendrier(self):
        """[CA8][Gherkin: Aucune date dans les attributs] Ni fenêtre de semis, ni
        durée de germination, ni date : ces données appartiennent au référentiel
        calendrier d'US-068, décliné par zone climatique."""
        interdits = ("date", "duree", "durée", "semis_debut", "semis_fin",
                     "germination", "fenetre", "fenêtre", "mois", "periode")
        colonnes = set(CultureConfig.__table__.columns.keys())

        for colonne in colonnes:
            for interdit in interdits:
                assert interdit not in colonne.lower(), (
                    f"culture_config.{colonne} ressemble à un attribut de calendrier (CA8)"
                )

    def test_us161_aucun_attribut_de_relation(self):
        """[CA9] Ni association, ni rotation, ni bioagresseur : ce sont des
        arêtes (US-162, US-163), pas des colonnes."""
        interdits = ("association", "associe", "rotation", "bioagresseur",
                     "ravageur", "maladie", "compagnon")
        colonnes = set(CultureConfig.__table__.columns.keys())

        for colonne in colonnes:
            for interdit in interdits:
                assert interdit not in colonne.lower(), (
                    f"culture_config.{colonne} ressemble à une relation (CA9)"
                )

    def test_us161_le_referentiel_d_attributs_ne_porte_que_de_la_conduite(self):
        """[CA8/CA9] Les quatre attributs déclarés sont exactement ceux de l'US —
        un cinquième ajouté à la légère se verrait ici."""
        assert {a.cle for a in svc_attributs.ATTRIBUTS} == {
            "exposition", "besoin_eau", "profondeur_semis_cm", "rusticite_min_c",
        }


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — aucun chiffre produit par un modèle de langage
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10AucunModeleDeLangage:
    def test_us161_lecture_sans_appel_reseau(self, db, monkeypatch):
        """[CA10][Gherkin: Attribut restitué sans appel au modèle] Toute tentative
        de sortie réseau fait échouer le test : la lecture est une lecture de
        colonnes, pas un appel au modèle."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la lecture d'attributs (CA10)")

        _seed_culture(db, "courgette", exposition="plein soleil", besoin_eau="élevé")
        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        lus = {a.cle: a for a in svc_attributs.lire_attributs(db, "courgette")}

        assert lus["exposition"].valeur == "plein soleil"
        assert lus["besoin_eau"].valeur == "élevé"

    def test_us161_lecture_n_appelle_pas_la_passerelle_llm(self, db):
        """[CA10] Le garde-fou (a) de l'arbitrage 2 : ni parsing, ni complétion,
        ni reformulation — le module n'a aucun chemin vers un modèle."""
        _seed_culture(db, "courgette", exposition="plein soleil")

        with patch("llm.passerelle.appeler_chat") as mock_chat,              patch("llm.passerelle.transcrire") as mock_whisper:
            svc_attributs.lire_attributs(db, "courgette")
            svc_attributs.corriger_attribut(db, "courgette", "besoin_eau", "élevé")

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()

    def test_us161_aucune_valeur_par_defaut_n_est_calculee(self, db):
        """[CA10/CA4] Le service ne dérive aucune valeur d'une autre culture,
        d'une moyenne ou d'une famille : ce qui n'est pas saisi reste vide."""
        _seed_culture(db, "carotte", profondeur_semis_cm=1.0)
        _seed_culture(db, "chou")

        lus = {a.cle: a for a in svc_attributs.lire_attributs(db, "chou")}

        assert lus["profondeur_semis_cm"].valeur is None


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — aucune régression sur les lectures existantes de culture_config
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11NonRegression:
    def test_us161_type_organe_recolte_inchange(self, db):
        """[CA11] La distinction végétatif/reproducteur, socle du calcul de
        stock, se lit exactement comme avant."""
        vegetative = _seed_culture(db, "carotte", type_organe="végétatif")
        reproductrice = _seed_culture(db, "tomate", type_organe="reproducteur")

        assert vegetative.type_organe_recolte == "végétatif"
        assert reproductrice.type_organe_recolte == "reproducteur"

    def test_us161_calcul_de_stock_inchange_par_les_nouveaux_attributs(self, db):
        """[CA11][Gherkin: Aucun impact sur les écrans existants] Le stock est
        identique avec et sans attributs agronomiques renseignés — ils n'entrent
        dans aucun calcul."""
        from utils.stock import calcul_stock_cultures

        parcelle = Parcelle(nom="P1", nom_normalise="p1", potager_id=1)
        db.add(parcelle)
        db.commit()
        _seed_culture(db, "tomate", type_organe="reproducteur")
        db.add(Evenement(
            date=datetime(2026, 5, 1), type_action="plantation", culture="tomate",
            quantite=6, unite="plants", parcelle_id=parcelle.id, potager_id=1,
        ))
        db.commit()

        avant = calcul_stock_cultures(db, date_ref=date(2026, 6, 1), potager_id=1)
        svc_attributs.corriger_attribut(db, "tomate", "exposition", "plein soleil")
        svc_attributs.corriger_attribut(db, "tomate", "profondeur_semis_cm", 1)
        apres = calcul_stock_cultures(db, date_ref=date(2026, 6, 1), potager_id=1)

        assert ({c: s.stock_plants for c, s in avant.items()}
                == {c: s.stock_plants for c, s in apres.items()})
        assert apres["tomate"].stock_plants == 6.0
        assert apres["tomate"].type_organe == "reproducteur"

    def test_us161_import_de_familles_toujours_fonctionnel(self, db):
        """[CA11 / US-166] Le bloc `cultures_familles` de l'import n'est pas
        affecté par l'ajout du bloc `cultures_attributs`."""
        _seed_culture(db, "tomate")
        manifeste = {
            "source": {
                "code": "wikidata", "libelle": "Wikidata", "licence": "CC0",
                "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
            },
            "familles": [{"nom": "Solanacée", "nom_scientifique": "Solanaceae"}],
            "cultures_familles": [{"culture": "tomate", "famille": "Solanacée"}],
        }

        resultat = svc_import.importer(db, manifeste)

        assert resultat.familles_creees == ["Solanacée"]
        assert resultat.cultures_rattachees == ["tomate"]
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "tomate").first()
        assert relue.famille_rel.nom == "Solanacée"

    def test_us161_manifeste_sans_bloc_attributs_reste_valide(self, db):
        """[CA11] Les blocs sont facultatifs : le manifeste projet d'US-166, qui
        ne porte aucun attribut, s'importe sans changement."""
        _seed_culture(db, "tomate")
        manifeste = {
            "source": {
                "code": "wikidata", "libelle": "Wikidata", "licence": "CC0",
                "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
            },
        }

        resultat = svc_import.importer(db, manifeste)

        assert resultat.attributs_ecrits == []
        assert resultat.cultures_hors_perimetre == []


# ═════════════════════════════════════════════════════════════════════════════
# CA2 (volet import) — une valeur de fichier hors vocabulaire est refusée
# ═════════════════════════════════════════════════════════════════════════════

class TestImportValeursRefusees:
    def test_us161_import_refuse_une_valeur_hors_vocabulaire(self, db, manifeste_attributs):
        """[CA2] Un fichier source fautif n'écrit pas n'importe quoi : la valeur
        est refusée et comptée, exactement comme une saisie au bot."""
        _seed_culture(db, "carotte")
        manifeste_attributs["cultures_attributs"][0]["exposition"] = "au soleil le matin"

        resultat = svc_import.importer(db, manifeste_attributs)

        assert "carotte.exposition" in resultat.attributs_refuses
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition is None

    def test_us161_une_valeur_refusee_n_empeche_pas_les_autres(self, db, manifeste_attributs):
        """[CA2] Un fichier partiellement fautif enrichit ce qu'il peut — refuser
        la ligne entière perdrait trois attributs valides pour un fautif."""
        _seed_culture(db, "carotte")
        manifeste_attributs["cultures_attributs"][0]["exposition"] = "au soleil le matin"

        svc_import.importer(db, manifeste_attributs)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition is None
        assert relue.besoin_eau == "moyen"
        assert relue.profondeur_semis_cm == 1.0

    def test_us161_dry_run_n_ecrit_aucun_attribut(self, db, manifeste_attributs):
        """[US-166 CA5] La simulation compte ce qui serait fait, sans rien écrire."""
        _seed_culture(db, "carotte")

        resultat = svc_import.importer(db, manifeste_attributs, dry_run=True)

        assert resultat.dry_run is True
        assert "carotte.exposition" in resultat.attributs_ecrits
        db.expire_all()
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition is None

    def test_us161_compte_rendu_console_mentionne_les_attributs(self, db, manifeste_attributs):
        """Le compte rendu d'import rend visibles les quatre compteurs de l'US."""
        _seed_culture(db, "carotte")
        resultat = svc_import.importer(db, manifeste_attributs)

        rendu = svc_import.formater_resultat(resultat)

        assert "Attributs écrits" in rendu
        assert "Hors périmètre" in rendu
        assert "Valeurs refusées" in rendu


# ═════════════════════════════════════════════════════════════════════════════
# Le manifeste de rédaction interne — la porte, et ce qu'elle ne laisse pas passer
# ═════════════════════════════════════════════════════════════════════════════

MANIFESTE_INTERNE_PROJET = "data/referentiel/attributs_redaction_interne.json"


@pytest.fixture
def manifeste_interne() -> dict:
    """Manifeste d'origine interne — aucune licence du socle d'import."""
    return {
        "source": {
            "code": "redaction_interne",
            "libelle": "Rédaction interne Assistant Potager",
            "licence": "proprietaire",
            "attribution": "Assistant Potager — rédaction interne",
            "url": None,
            "partageable": True,
        },
        "cultures_attributs": [
            {"culture": "carotte", "exposition": "plein soleil",
             "profondeur_semis_cm": 1, "rusticite_min_c": -5},
        ],
    }


class TestManifesteRedactionInterne:
    def test_us161_un_manifeste_interne_est_accepte(self, db, manifeste_interne):
        """Une origine non importée du socle échappe au contrôle de licence :
        elle ne porte aucun contenu tiers, donc rien à contaminer."""
        _seed_culture(db, "carotte")

        resultat = svc_import.importer(db, manifeste_interne)

        assert "carotte.exposition" in resultat.attributs_ecrits
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition == "plein soleil"
        assert relue.profondeur_semis_cm == 1.0

    def test_us161_la_valeur_interne_porte_l_origine_redaction_interne(
        self, db, manifeste_interne
    ):
        """[CA3] Tracée comme les autres : il n'existe aucune donnée sans origine."""
        _seed_culture(db, "carotte")

        svc_import.importer(db, manifeste_interne)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        interne = svc_sources.get_source(db, svc_sources.SOURCE_REDACTION_INTERNE)
        assert relue.exposition_source_id == interne.id
        assert interne.licence == "proprietaire"

    def test_us161_une_source_tierce_ne_peut_pas_se_dire_interne(self, db):
        """LA porte dérobée à ne pas laisser ouverte : un contenu tiers qui
        s'annoncerait interne pour échapper au contrôle de licence. Seuls les
        codes que SOURCES_SOCLE déclare non importés y ont droit — une liste
        fermée, pas un drapeau que le manifeste se donne."""
        _seed_culture(db, "carotte")
        manifeste = {
            "source": {
                "code": "permapeople", "libelle": "Permapeople",
                "licence": "CC-BY-SA-4.0", "attribution": "Permapeople",
                "importee": False,          # le manifeste tente de se dire interne
            },
            "cultures_attributs": [{"culture": "carotte", "exposition": "ombre"}],
        }

        with pytest.raises(LicenceHorsSocleError):
            svc_import.importer(db, manifeste)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition is None

    def test_us161_un_manifeste_interne_ne_peut_pas_se_redefinir(self, db, manifeste_interne):
        """L'origine interne garde la fiche du registre : un fichier ne peut ni
        se donner une autre licence, ni une autre attribution, ni se déclarer
        non partageable."""
        _seed_culture(db, "carotte")
        manifeste_interne["source"]["licence"] = "CC-BY-SA-4.0"
        manifeste_interne["source"]["attribution"] = "Attribution détournée"

        svc_import.importer(db, manifeste_interne)

        interne = svc_sources.get_source(db, svc_sources.SOURCE_REDACTION_INTERNE)
        assert interne.licence == "proprietaire"
        assert interne.attribution == "Assistant Potager — rédaction interne"

    def test_us161_une_correction_au_bot_prime_sur_le_manifeste_interne(
        self, db, manifeste_interne
    ):
        """[CA6] Le terrain gagne contre le référentiel, y compris quand le
        référentiel est rédigé par le projet lui-même."""
        _seed_culture(db, "carotte")
        svc_attributs.corriger_attribut(db, "carotte", "exposition", "ombre")

        resultat = svc_import.importer(db, manifeste_interne)

        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition == "ombre"
        assert "carotte.exposition" in resultat.attributs_preserves

    def test_us161_le_gabarit_livre_est_lisible_et_n_ecrit_rien(self, db):
        """Le fichier livré est vide de valeurs : l'importer tel quel est
        inoffensif. C'est ce qui permet de le versionner avant de le remplir."""
        _seed_culture(db, "carotte")
        manifeste = svc_import.charger_manifeste(MANIFESTE_INTERNE_PROJET)

        resultat = svc_import.importer(db, manifeste)

        assert resultat.attributs_ecrits == []
        assert resultat.attributs_refuses == []
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert relue.exposition is None

    def test_us161_le_gabarit_couvre_exactement_le_perimetre_initial(self):
        """Le gabarit et le garde-fou de code ne peuvent pas diverger : dix
        cultures ici, dix là, les mêmes."""
        manifeste = svc_import.charger_manifeste(MANIFESTE_INTERNE_PROJET)

        cultures = [e["culture"] for e in manifeste["cultures_attributs"]]
        assert len(cultures) == 10
        assert all(svc_attributs.dans_perimetre_initial(c) for c in cultures)

    def test_us161_le_gabarit_ne_declare_que_les_quatre_attributs(self):
        """Une clé inconnue dans le gabarit serait silencieusement ignorée à
        l'import — mieux vaut qu'elle n'y soit jamais."""
        manifeste = svc_import.charger_manifeste(MANIFESTE_INTERNE_PROJET)
        attendues = {"culture"} | {a.cle for a in svc_attributs.ATTRIBUTS}

        for entree in manifeste["cultures_attributs"]:
            assert set(entree) == attendues
