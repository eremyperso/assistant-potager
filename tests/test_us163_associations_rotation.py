"""
tests/test_us163_associations_rotation.py
[US-163] Modéliser les associations de cultures et rendre la règle de rotation calculable

Couverture des critères d'acceptance CA1 → CA13, à une exception près :

  - CA12 (performance) : « mesuré sur la base de production... à vérifier, pas à
    supposer ». Un test pytest tournant sur SQLite en mémoire ne mesure rien
    d'utile sur un temps de réponse Postgres réel — l'outil de mesure est
    `tools/mesurer_rotation.py`, à exécuter par un opérateur humain contre la
    base de production avant de câbler `evaluer_rotation` dans un chemin
    automatique (US-167). Ce fichier ne prétend donc pas couvrir CA12.

CA13 (couverture des tests) est satisfait par ce fichier lui-même. CA11 (zéro
jeton) est vérifié activement ci-dessous (`TestCA11AucunAppelModele`), pas
seulement supposé de l'absence d'import Groq dans les modules testés.

Une section additionnelle (`TestImportAssociations`) couvre le chemin d'import
ajouté après coup pour alimenter la table depuis Wind River Greens (CC BY 4.0)
— voir `tests/test_us163_adaptateur_wind_river_associations.py` pour la
curation elle-même (traduction, périmètre, doublons).
"""
import socket
from datetime import datetime
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.services import associations as svc_associations
from app.services import familles as svc_familles
from app.services import import_referentiel as svc_import
from app.services import referentiel_sources as svc_sources
from app.services import rotation as svc_rotation
from app.services.associations import EntiteInconnueError, ValeurAssociationInvalideError
from app.services.context import TenantContext
from database.models import AssociationCulture, CultureConfig, Evenement, FamilleBotanique, Parcelle

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


def _seed_culture(db, nom, type_organe="reproducteur", potager_id=None, famille=None):
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    if famille is not None:
        cfg.famille_rel = famille
    db.add(cfg)
    db.commit()
    return cfg


def _seed_famille(db, nom, delai_retour_annees=None):
    famille = FamilleBotanique(
        nom=nom,
        nom_normalise=svc_familles.normaliser_famille(nom),
        delai_retour_annees=delai_retour_annees,
    )
    db.add(famille)
    db.commit()
    return famille


def _seed_parcelle(db, nom, potager_id=1):
    parcelle = Parcelle(nom=nom, nom_normalise=nom.lower(), potager_id=potager_id)
    db.add(parcelle)
    db.commit()
    return parcelle


def _seed_evenement(db, parcelle, culture, annee, potager_id=1, type_action="plantation", texte_original=None):
    evt = Evenement(
        date=datetime(annee, 5, 1),
        type_action=type_action,
        culture=culture,
        parcelle_id=parcelle.id,
        potager_id=potager_id,
        texte_original=texte_original,
    )
    db.add(evt)
    db.commit()
    return evt


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — l'association : une arête typée avec un motif court en clair
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1NatureEtMotif:
    def test_association_favorable_avec_motif(self, db):
        """[CA1] Une association favorable porte sa nature et un motif court."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")

        assoc, creee = svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_FAVORABLE,
            "repousse les pucerons", svc_associations.NIVEAU_ETABLI,
        )

        assert creee is True
        assert assoc.nature == "favorable"
        assert assoc.motif == "repousse les pucerons"

    def test_association_defavorable(self, db):
        """[CA1] Une association défavorable est également représentable."""
        _seed_culture(db, "haricot")
        _seed_culture(db, "ail")

        assoc, _ = svc_associations.enregistrer_association(
            db, "haricot", "ail", svc_associations.NATURE_DEFAVORABLE,
            "inhibition de croissance", svc_associations.NIVEAU_ETABLI,
        )

        assert assoc.nature == "defavorable"

    def test_motif_vide_refuse(self, db):
        """[CA1] Le motif est obligatoire : sans lui, l'avertissement redevient autoritaire."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")

        with pytest.raises(ValeurAssociationInvalideError):
            svc_associations.enregistrer_association(
                db, "tomate", "basilic", svc_associations.NATURE_FAVORABLE, "   "
            )
        assert db.query(AssociationCulture).count() == 0

    def test_nature_hors_vocabulaire_refusee_avant_toute_ecriture(self, db):
        """[CA1] Une nature hors du vocabulaire fermé est refusée avant toute écriture."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")

        with pytest.raises(ValeurAssociationInvalideError):
            svc_associations.enregistrer_association(
                db, "tomate", "basilic", "excellente", "motif"
            )
        assert db.query(AssociationCulture).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — le niveau de preuve
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2NiveauDePreuve:
    def test_niveau_preuve_etabli_ou_traditionnel(self, db):
        """[CA2] Les deux niveaux de preuve du vocabulaire fermé sont acceptés."""
        _seed_culture(db, "carotte")
        _seed_culture(db, "poireau")

        assoc, _ = svc_associations.enregistrer_association(
            db, "carotte", "poireau", svc_associations.NATURE_FAVORABLE,
            "répulsif croisé", svc_associations.NIVEAU_TRADITIONNEL,
        )

        assert assoc.niveau_preuve == "traditionnel"

    def test_niveau_preuve_invalide_refuse(self, db):
        """[CA2] Un niveau de preuve hors vocabulaire est refusé."""
        _seed_culture(db, "carotte")
        _seed_culture(db, "poireau")

        with pytest.raises(ValeurAssociationInvalideError):
            svc_associations.enregistrer_association(
                db, "carotte", "poireau", svc_associations.NATURE_FAVORABLE,
                "motif", "peut-etre",
            )


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — formulation différenciée à la restitution
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3FormulationDifferenciee:
    def test_defavorable_etabli_dit_defavorable(self, db):
        """[CA3] Un fait établi se dit tel quel."""
        assert svc_associations.formuler_nature("defavorable", "etabli") == "défavorable"

    def test_defavorable_traditionnel_dit_deconseille_par_la_tradition(self, db):
        """[Gherkin: Association traditionnelle formulée comme telle] Jamais
        présentée comme un fait établi."""
        formulation = svc_associations.formuler_nature("defavorable", "traditionnel")

        assert formulation == "déconseillé par la pratique traditionnelle"
        assert formulation != svc_associations.formuler_nature("defavorable", "etabli")

    def test_lire_associations_restitue_la_formulation_differenciee(self, db):
        """[CA3] La formulation différenciée sort directement de la lecture,
        jamais à recalculer côté appelant (bot ou future PWA)."""
        _seed_culture(db, "carotte")
        _seed_culture(db, "aneth")
        svc_associations.enregistrer_association(
            db, "carotte", "aneth", svc_associations.NATURE_DEFAVORABLE,
            "concurrence racinaire", svc_associations.NIVEAU_TRADITIONNEL,
        )

        lues = svc_associations.lire_associations(db, "carotte")

        assert lues[0].formulation == "déconseillé par la pratique traditionnelle"


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — association portée par la famille botanique
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4AssociationParFamille:
    def test_association_saisie_au_niveau_famille_visible_par_culture_membre(self, db):
        """[Gherkin: Association portée par la famille]"""
        cucurbitacee = _seed_famille(db, "Cucurbitacée", delai_retour_annees=2)
        _seed_culture(db, "patisson", famille=cucurbitacee)
        _seed_culture(db, "pomme de terre")

        svc_associations.enregistrer_association(
            db, "Cucurbitacée", "pomme de terre", svc_associations.NATURE_DEFAVORABLE,
            "sensibilité croisée au mildiou",
        )

        lues = svc_associations.lire_associations(db, "patisson")

        assert len(lues) == 1
        assert lues[0].autre_partie == "pomme de terre"
        assert lues[0].nature == "defavorable"

    def test_association_famille_vaut_pour_toutes_ses_cultures_sans_duplication(self, db):
        """[CA4] Une association saisie une fois au niveau de la famille vaut pour
        TOUTES ses cultures — pas besoin de la ressaisir dix fois (mesure du
        25/08/2026 sur les cucurbitacées)."""
        cucurbitacee = _seed_famille(db, "Cucurbitacée", delai_retour_annees=2)
        _seed_culture(db, "courgette", famille=cucurbitacee)
        _seed_culture(db, "melon", famille=cucurbitacee)
        _seed_culture(db, "persil")

        svc_associations.enregistrer_association(
            db, "Cucurbitacée", "persil", svc_associations.NATURE_NEUTRE,
            "aucune interaction connue",
        )

        assert len(svc_associations.lire_associations(db, "courgette")) == 1
        assert len(svc_associations.lire_associations(db, "melon")) == 1
        assert db.query(AssociationCulture).count() == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — lecture symétrique
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5LectureBidirectionnelle:
    def test_association_lue_dans_les_deux_sens(self, db):
        """[Gherkin: Association lue dans les deux sens]"""
        _seed_culture(db, "carotte")
        _seed_culture(db, "aneth")
        svc_associations.enregistrer_association(
            db, "carotte", "aneth", svc_associations.NATURE_DEFAVORABLE, "concurrence racinaire"
        )

        depuis_aneth = svc_associations.lire_associations(db, "aneth")

        assert len(depuis_aneth) == 1
        assert depuis_aneth[0].autre_partie == "carotte"
        assert depuis_aneth[0].nature == "defavorable"

    def test_correction_dans_l_orientation_inverse_met_a_jour_sans_dupliquer(self, db):
        """[CA5, CA10] Une orientation de stockage ne doit jamais devenir une
        seconde arête concurrente : corriger « aneth, carotte » après avoir
        saisi « carotte, aneth » met à jour la même ligne."""
        _seed_culture(db, "carotte")
        _seed_culture(db, "aneth")
        svc_associations.enregistrer_association(
            db, "carotte", "aneth", svc_associations.NATURE_DEFAVORABLE, "motif initial"
        )

        _, creee = svc_associations.enregistrer_association(
            db, "aneth", "carotte", svc_associations.NATURE_DEFAVORABLE, "motif corrigé"
        )

        assert creee is False
        assert db.query(AssociationCulture).count() == 1
        assert db.query(AssociationCulture).first().motif == "motif corrigé"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la rotation se calcule
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6RotationCalculee:
    def test_conflit_de_rotation_sur_deux_campagnes(self, db):
        """[Gherkin: Conflit de rotation sur deux campagnes]"""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "tomate", annee=2025)

        evaluation = svc_rotation.evaluer_rotation(db, CTX, nord.id, "poivron", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_CONFLIT
        assert evaluation.culture_precedente == "tomate"
        assert evaluation.famille == "Solanacée"
        assert "tomate" in evaluation.message
        assert "Solanacée" in evaluation.message

    def test_aucun_conflit_une_fois_le_delai_de_retour_ecoule(self, db):
        """[CA6] Passé le délai de retour, la même famille ne déclenche plus de conflit."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "tomate", annee=2020)

        evaluation = svc_rotation.evaluer_rotation(db, CTX, nord.id, "poivron", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_OK

    def test_aucun_conflit_si_l_antecedent_est_d_une_autre_famille(self, db):
        """[CA6] Un antécédent d'une AUTRE famille ne déclenche aucun conflit —
        l'historique est connu, il ne contient simplement rien de gênant."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        apiacee = _seed_famille(db, "Apiacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "carotte", famille=apiacee)
        nord = _seed_parcelle(db, "NORD")
        _seed_evenement(db, nord, "carotte", annee=2025)

        evaluation = svc_rotation.evaluer_rotation(db, CTX, nord.id, "tomate", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_OK
        assert evaluation.culture_precedente is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — famille sans délai de retour renseigné
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7FamilleSansDelaiRetour:
    def test_evaluation_indisponible_si_delai_non_renseigne(self, db):
        """[Gherkin: Famille sans délai de retour]"""
        lamiacee = _seed_famille(db, "Lamiacée", delai_retour_annees=None)
        _seed_culture(db, "basilic", famille=lamiacee)
        nord = _seed_parcelle(db, "NORD")

        evaluation = svc_rotation.evaluer_rotation(db, CTX, nord.id, "basilic", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_INDISPONIBLE
        assert "absence de conflit" in evaluation.message
        assert "n'affirme pas" in evaluation.message

    def test_culture_sans_famille_connue_est_egalement_indisponible(self, db):
        """[CA7] Même issue honnête quand c'est la culture, pas seulement sa
        famille, qui manque d'information — jamais interprété comme un conflit
        ni comme son absence."""
        _seed_culture(db, "mystere")
        nord = _seed_parcelle(db, "NORD")

        evaluation = svc_rotation.evaluer_rotation(db, CTX, nord.id, "mystere", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_INDISPONIBLE


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — parcelle sans antécédent connu
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8ParcelleSansAntecedent:
    def test_parcelle_sans_evenement_ne_conclut_pas_a_l_absence_de_conflit(self, db):
        """[Gherkin: Parcelle sans antécédent connu]"""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        ouest = _seed_parcelle(db, "OUEST")

        evaluation = svc_rotation.evaluer_rotation(db, CTX, ouest.id, "tomate", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_AUCUN_ANTECEDENT
        assert "antécédent" in evaluation.message
        assert "absence de conflit" in evaluation.message

    def test_bulletin_meteo_exclu_meme_s_il_portait_une_culture(self, db):
        """[Notes techniques US-163] Un bulletin `[AUTO-METEO]` est exclu par son
        marqueur — il ne représente jamais un antécédent de culture, quelle que
        soit sa colonne `culture`."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        ouest = _seed_parcelle(db, "OUEST")
        _seed_evenement(
            db, ouest, "tomate", annee=2025,
            type_action="observation", texte_original="[AUTO-METEO]",
        )

        evaluation = svc_rotation.evaluer_rotation(db, CTX, ouest.id, "tomate", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_AUCUN_ANTECEDENT

    def test_culture_fantome_non_traitee_comme_antecedent_etabli(self, db):
        """[Notes techniques US-163] Une culture inconnue du référentiel (ex.
        'radi' né d'un échec de parsing) ne pollue jamais l'historique."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        ouest = _seed_parcelle(db, "OUEST")
        _seed_evenement(db, ouest, "radi", annee=2025)  # jamais dictée comme culture_config

        evaluation = svc_rotation.evaluer_rotation(db, CTX, ouest.id, "tomate", campagne_reference=2026)

        assert evaluation.statut == svc_rotation.STATUT_AUCUN_ANTECEDENT


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — raisonnement à la campagne, jamais au jour près
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9RaisonnementParCampagne:
    def test_deux_dates_tres_eloignees_dans_la_meme_annee_sont_une_seule_campagne(self, db):
        """[CA9] Un événement du 1er janvier et une évaluation la même année
        relèvent de la MÊME campagne, quel que soit l'écart en jours."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "poivron", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")
        evt = Evenement(
            date=datetime(2025, 1, 1), type_action="plantation", culture="tomate",
            parcelle_id=nord.id, potager_id=1,
        )
        db.add(evt)
        db.commit()

        evaluation = svc_rotation.evaluer_rotation(db, CTX, nord.id, "poivron", campagne_reference=2025)

        assert evaluation.statut == svc_rotation.STATUT_CONFLIT
        assert evaluation.campagne_derniere_occurrence == 2025


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — saisie, correction, traçabilité
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10SaisieEtTracabilite:
    def test_association_porte_toujours_une_source(self, db):
        """[CA10] Aucune arête anonyme : l'origine `saisie_manuelle` est toujours renseignée."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")

        assoc, _ = svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_FAVORABLE, "motif"
        )

        assert assoc.source_id is not None
        assert assoc.source_rel.code == "saisie_manuelle"

    def test_cote_inconnu_refuse_avant_toute_ecriture(self, db):
        """[CA10] Une culture jamais dictée ni une famille jamais connue ne peut
        pas devenir un côté d'association — jamais créée à la volée."""
        _seed_culture(db, "tomate")

        with pytest.raises(EntiteInconnueError):
            svc_associations.enregistrer_association(
                db, "tomate", "legume-jamais-dicte", svc_associations.NATURE_FAVORABLE, "motif"
            )
        assert db.query(AssociationCulture).count() == 0

    def test_lire_associations_d_une_entite_inconnue_leve(self, db):
        """[CA10] Consulter une culture/famille totalement inconnue est une
        erreur explicite, jamais une liste vide silencieuse."""
        with pytest.raises(EntiteInconnueError):
            svc_associations.lire_associations(db, "culture-totalement-inconnue")


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — zéro jeton, sur les deux chemins
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11AucunAppelModele:
    def test_associations_et_rotation_sans_appel_reseau(self, db, monkeypatch):
        """[Gherkin: Aucun jeton consommé] Toute tentative de sortie réseau fait
        échouer le test."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la saisie/lecture d'association ou à la rotation (CA11)")

        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        _seed_culture(db, "basilic")
        nord = _seed_parcelle(db, "NORD")

        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_FAVORABLE, "motif"
        )
        svc_associations.lire_associations(db, "tomate")
        svc_rotation.evaluer_rotation(db, CTX, nord.id, "tomate", campagne_reference=2026)

    def test_rotation_n_appelle_pas_la_passerelle_llm(self, db):
        """[CA11] Ni parsing, ni complétion, ni reformulation par le modèle."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=3)
        _seed_culture(db, "tomate", famille=solanacee)
        nord = _seed_parcelle(db, "NORD")

        with patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            svc_rotation.evaluer_rotation(db, CTX, nord.id, "tomate", campagne_reference=2026)

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Couche bot — /association et /rotation (dispatch, formatage, erreurs)
# ═════════════════════════════════════════════════════════════════════════════
# Le service est mocké dans cette section : ce qui est vérifié ici est le
# câblage de la commande (parsing de ctx.args, appel du bon service avec les
# bons arguments, formatage de la réponse) — la logique métier elle-même est
# déjà couverte ci-dessus, même stratégie que TestCommandeBotFiche d'US-164.

class _BotCommandeMixin:
    def _make_update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        update.effective_chat.id = 123
        return update

    def _make_ctx(self, args):
        ctx = MagicMock()
        ctx.args = args
        return ctx


class TestCommandeBotAssociation(_BotCommandeMixin):
    @pytest.mark.asyncio
    async def test_sans_argument_affiche_l_usage(self):
        from bot import cmd_association
        update, ctx = self._make_update(), self._make_ctx([])

        await cmd_association(update, ctx)

        assert "Usage" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_lister_appelle_le_service_et_formate_la_reponse(self):
        """[CA5] La formulation différenciée sort telle quelle dans le message."""
        from bot import cmd_association
        update = self._make_update()
        ctx = self._make_ctx(["lister", "carotte"])
        lue = svc_associations.AssociationLue(
            autre_partie="aneth", autre_est_famille=False, nature="defavorable",
            motif="concurrence racinaire", niveau_preuve="etabli",
            formulation="défavorable", source_code="saisie_manuelle",
            attribution="Saisi par le jardinier",
        )

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_associations.lire_associations", return_value=[lue]) as mock_lire:
            MockSession.return_value = MagicMock()
            await cmd_association(update, ctx)
            mock_lire.assert_called_once_with(ANY, "carotte")

        texte = update.message.reply_text.call_args[0][0]
        assert "aneth" in texte
        assert "défavorable" in texte

    @pytest.mark.asyncio
    async def test_lister_entite_inconnue_message_honnete(self):
        from bot import cmd_association
        update = self._make_update()
        ctx = self._make_ctx(["lister", "inconnue"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_associations.lire_associations",
                   side_effect=svc_associations.EntiteInconnueError("inconnue")):
            MockSession.return_value = MagicMock()
            await cmd_association(update, ctx)

        assert "inconnue" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_saisir_arguments_insuffisants_affiche_l_usage_precis(self):
        from bot import cmd_association
        update = self._make_update()
        ctx = self._make_ctx(["saisir", "tomate", "basilic"])

        await cmd_association(update, ctx)

        assert "Usage" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_saisir_appelle_le_service_avec_les_bons_arguments(self):
        from bot import cmd_association
        update = self._make_update()
        ctx = self._make_ctx(
            ["saisir", "carotte", "aneth", "defavorable", "etabli", "concurrence", "racinaire"]
        )

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_associations.enregistrer_association",
                   return_value=(MagicMock(), True)) as mock_enr:
            MockSession.return_value = MagicMock()
            await cmd_association(update, ctx)

            mock_enr.assert_called_once_with(
                ANY, "carotte", "aneth", "defavorable", "concurrence racinaire", "etabli"
            )
        assert "saisie" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_saisir_valeur_invalide_restitue_le_message_du_service(self):
        """[CA1, CA2] Le motif du refus (vocabulaire fermé) atteint le jardinier
        tel quel, jamais une erreur générique."""
        from bot import cmd_association
        update = self._make_update()
        ctx = self._make_ctx(["saisir", "tomate", "basilic", "favorable", "etabli", "motif"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.svc_associations.enregistrer_association",
                   side_effect=svc_associations.ValeurAssociationInvalideError(
                       "« excellente » n'est pas une nature d'association admise."
                   )):
            MockSession.return_value = MagicMock()
            await cmd_association(update, ctx)

        assert "nature d'association admise" in update.message.reply_text.call_args[0][0]


class TestCommandeBotRotation(_BotCommandeMixin):
    @pytest.mark.asyncio
    async def test_arguments_insuffisants_affiche_l_usage(self):
        from bot import cmd_rotation
        update, ctx = self._make_update(), self._make_ctx(["NORD"])

        await cmd_rotation(update, ctx)

        assert "Usage" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_parcelle_inconnue_message_explicite(self):
        from bot import cmd_rotation
        update = self._make_update()
        ctx = self._make_ctx(["INTROUVABLE", "tomate"])

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.resolve_parcelle", return_value=None):
            MockSession.return_value = MagicMock()
            await cmd_rotation(update, ctx)

        assert "Parcelle inconnue" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_rotation_appelle_le_service_et_affiche_le_message_du_predicat(self):
        """[CA6] Le message affiché est celui du prédicat (`EvaluationRotation.message`),
        jamais un texte recomposé côté bot."""
        from bot import cmd_rotation
        update = self._make_update()
        ctx = self._make_ctx(["NORD", "poivron"])
        parcelle = MagicMock(id=42, nom="NORD")
        evaluation = svc_rotation.EvaluationRotation(
            statut=svc_rotation.STATUT_CONFLIT, culture="poivron", campagne_reference=2026,
            famille="Solanacée", delai_retour_annees=3,
            culture_precedente="tomate", campagne_derniere_occurrence=2025,
        )

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.resolve_parcelle", return_value=parcelle), \
             patch("bot.svc_rotation.evaluer_rotation", return_value=evaluation) as mock_eval:
            MockSession.return_value = MagicMock()
            await cmd_rotation(update, ctx)

            mock_eval.assert_called_once_with(ANY, ANY, 42, "poivron")

        texte = update.message.reply_text.call_args[0][0]
        assert evaluation.message in texte

    @pytest.mark.asyncio
    async def test_culture_a_plusieurs_mots_reconstituee(self):
        from bot import cmd_rotation
        update = self._make_update()
        ctx = self._make_ctx(["NORD", "pomme", "de", "terre"])
        parcelle = MagicMock(id=42, nom="NORD")
        evaluation = svc_rotation.EvaluationRotation(
            statut=svc_rotation.STATUT_AUCUN_ANTECEDENT, culture="pomme de terre", campagne_reference=2026,
        )

        with patch("bot.SessionLocal") as MockSession, \
             patch("bot.resolve_parcelle", return_value=parcelle), \
             patch("bot.svc_rotation.evaluer_rotation", return_value=evaluation) as mock_eval:
            MockSession.return_value = MagicMock()
            await cmd_rotation(update, ctx)

            mock_eval.assert_called_once_with(ANY, ANY, 42, "pomme de terre")


# ═════════════════════════════════════════════════════════════════════════════
# Import — alimenter association_culture depuis un manifeste [ajout post-US-163]
# ═════════════════════════════════════════════════════════════════════════════
# Chemin AJOUTÉ après la livraison initiale de l'US, à la demande explicite du
# porteur produit : les associations restent SAISIES en première intention
# (CA10), mais une source déjà au socle sous licence CC BY 4.0 (wind_river_greens,
# US-161) peut désormais aussi les alimenter — après curation humaine, jamais
# brute (voir tests/test_us163_adaptateur_wind_river_associations.py). Ce n'est
# pas un second mécanisme d'écriture : `_importer_associations_cultures`
# délègue à `app.services.associations.importer_association`, qui applique la
# même résolution et la même validation que `/association saisir` au bot.

def _manifeste_associations(entrees: list[dict]) -> dict:
    fiche = next(
        f for f in svc_sources.SOURCES_SOCLE if f["code"] == svc_sources.SOURCE_WIND_RIVER
    )
    return {
        "source": {
            "code": fiche["code"], "libelle": fiche["libelle"], "licence": fiche["licence"],
            "attribution": fiche["attribution"], "url": fiche["url"],
            "partageable": fiche["partageable"],
        },
        "extrait_le": "v1.0.0",
        "cultures_associations": entrees,
    }


class TestImportAssociations:
    def test_import_cree_une_association_absente(self, db):
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "basilic", "nature": "favorable",
             "motif": "répulsif contre pucerons", "niveau_preuve": "traditionnel"}
        ])

        resultat = svc_import.importer(db, manifeste)

        assert resultat.associations_creees == ["tomate × basilic"]
        assoc = db.query(AssociationCulture).one()
        assert assoc.nature == "favorable"
        assert assoc.source_rel.code == "wind_river_greens"

    def test_import_rejoue_est_idempotent(self, db):
        """[US-166/CA5, même invariant que US-161/CA6] Rejouer reconnaît sa
        propre donnée et ne la recompte pas comme une écriture."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "basilic", "nature": "favorable",
             "motif": "répulsif contre pucerons", "niveau_preuve": "traditionnel"}
        ])
        svc_import.importer(db, manifeste)

        second = svc_import.importer(db, manifeste)

        assert second.associations_creees == []
        assert second.associations_ecrites == []
        assert db.query(AssociationCulture).count() == 1

    def test_import_rafraichit_sa_propre_donnee(self, db):
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "basilic", "nature": "favorable",
             "motif": "répulsif contre pucerons", "niveau_preuve": "traditionnel"}
        ])
        svc_import.importer(db, manifeste)

        manifeste["cultures_associations"][0]["motif"] = "améliore la saveur"
        resultat = svc_import.importer(db, manifeste)

        assert resultat.associations_ecrites == ["tomate × basilic"]
        assert db.query(AssociationCulture).one().motif == "améliore la saveur"

    def test_saisie_manuelle_anterieure_prime_sur_l_import(self, db):
        """[CA10, US-161/CA6 même invariant] Le jardinier décrit son terrain ;
        un import généraliste ne l'écrase jamais."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_DEFAVORABLE,
            "observé défavorable chez moi", svc_associations.NIVEAU_ETABLI,
        )
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "basilic", "nature": "favorable",
             "motif": "répulsif contre pucerons", "niveau_preuve": "traditionnel"}
        ])

        resultat = svc_import.importer(db, manifeste)

        assert resultat.associations_preservees == ["tomate × basilic"]
        assoc = db.query(AssociationCulture).one()
        assert assoc.nature == "defavorable"
        assert assoc.motif == "observé défavorable chez moi"

    def test_saisie_manuelle_posterieure_a_l_import_ecrase_l_import(self, db):
        """Le sens inverse : une correction au bot APRÈS un import reste —
        l'import ne verrouille rien (même invariant que US-161/CA6)."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "basilic", "nature": "favorable",
             "motif": "répulsif contre pucerons", "niveau_preuve": "traditionnel"}
        ])
        svc_import.importer(db, manifeste)

        svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_NEUTRE,
            "corrigé par le jardinier", svc_associations.NIVEAU_ETABLI,
        )
        svc_import.importer(db, manifeste)

        assoc = db.query(AssociationCulture).one()
        assert assoc.nature == "neutre"
        assert assoc.motif == "corrigé par le jardinier"

    def test_cote_inconnu_ignore_jamais_cree(self, db):
        """[CA7 d'US-161, même invariant] L'import enrichit le référentiel, il
        ne le peuple pas — une culture jamais dictée n'est jamais créée."""
        _seed_culture(db, "tomate")
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "légume-jamais-dicté", "nature": "favorable",
             "motif": "motif", "niveau_preuve": "traditionnel"}
        ])

        resultat = svc_import.importer(db, manifeste)

        assert resultat.associations_ignorees == ["tomate × légume-jamais-dicté"]
        assert db.query(AssociationCulture).count() == 0

    def test_valeur_hors_vocabulaire_refusee(self, db):
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        manifeste = _manifeste_associations([
            {"culture": "tomate", "compagnon": "basilic", "nature": "excellente",
             "motif": "motif", "niveau_preuve": "traditionnel"}
        ])

        resultat = svc_import.importer(db, manifeste)

        assert resultat.associations_refusees == ["tomate × basilic"]
        assert db.query(AssociationCulture).count() == 0

    def test_association_au_niveau_famille_importee(self, db):
        """[CA4] Le bloc d'import porte aussi les associations de famille."""
        cucurbitacee = _seed_famille(db, "Cucurbitacée", delai_retour_annees=2)
        _seed_culture(db, "courgette", famille=cucurbitacee)
        _seed_culture(db, "pomme de terre")
        manifeste = _manifeste_associations([
            {"culture": "Cucurbitacée", "compagnon": "pomme de terre", "nature": "defavorable",
             "motif": "sensibilité croisée au mildiou", "niveau_preuve": "traditionnel"}
        ])

        svc_import.importer(db, manifeste)

        lues = svc_associations.lire_associations(db, "courgette")
        assert len(lues) == 1
        assert lues[0].autre_partie == "pomme de terre"
