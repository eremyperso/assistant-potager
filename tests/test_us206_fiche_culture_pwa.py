"""
tests/test_us206_fiche_culture_pwa.py
[US-206] Composer la fiche d'une culture pour la PWA — référentiel, variétés
cultivées, voisinages, bioagresseurs.

`app.services.fiche_culture.composer_fiche_pwa` réutilise les fonctions de
lecture déjà couvertes par leurs propres US (attributs_culture / US-161,
calendrier_cultural / US-068, US-177, associations / US-163, bioagresseurs /
US-162, US-174, recalage_calendrier / US-194) — ce fichier couvre
l'ASSEMBLAGE et l'honnêteté propres à US-206, pas la logique déjà testée
ailleurs.
"""
from __future__ import annotations

import socket
from datetime import date, datetime

import pytest

from app.services import associations as svc_associations
from app.services import bioagresseurs as svc_bioagresseurs
from app.services import fiche_culture as svc_fiche
from app.services import import_referentiel as svc_import
from database.models import CultureConfig, Evenement, FamilleBotanique, Parcelle, Potager, User


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.add(Potager(id=2, nom="Jardin B", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="planche centrale", nom_normalise="planchecentrale", potager_id=1),
        Parcelle(id=2, nom="planche ombre", nom_normalise="plancheombre", potager_id=1),
        Parcelle(id=3, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
    ])
    test_db.commit()
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


def _seed_famille(db, nom, delai_retour_annees=None):
    famille = FamilleBotanique(nom=nom, nom_normalise=nom.lower(), delai_retour_annees=delai_retour_annees)
    db.add(famille)
    db.commit()
    return famille


def _source():
    return {"code": "wikidata", "libelle": "Source de test", "licence": "CC0",
            "attribution": "Source de test", "url": "https://example.org/", "partageable": True}


def _importer_durees(db, culture, **durees):
    """Pose des durées de référentiel via le manifeste d'import (US-068/US-177)."""
    svc_import.importer(db, {
        "source": _source(),
        "cultures_calendriers": [{"culture": culture, "durees": durees}],
    })


def _evt(db, action, culture, jour, parcelle_id=1, potager_id=1, **champs):
    evenement = Evenement(
        type_action=action, culture=culture,
        date=datetime.combine(jour, datetime.min.time()),
        parcelle_id=parcelle_id, potager_id=potager_id, **champs,
    )
    db.add(evenement)
    db.commit()
    return evenement


DATE_REF = date(2026, 6, 1)


# ═════════════════════════════════════════════════════════════════════════════
# Culture complète — CA1, CA2, CA3, CA4, CA5, CA6, CA7
# ═════════════════════════════════════════════════════════════════════════════

class TestCultureComplete:
    def test_us206_fiche_complete_porte_identite_attributs_et_organe(self, db):
        """[CA1, CA2][Gherkin: Fiche de la tomate] Identité, famille/délai de
        retour rendus séparément, attributs de conduite avec leur source."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "tomate", famille=solanacee, exposition="plein soleil")
        _evt(db, "plantation", "tomate", date(2026, 5, 1), parcelle_id=1)

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", 1, DATE_REF)

        assert fiche.fiche_absente is False
        assert fiche.famille == "Solanacée"
        assert fiche.delai_retour_annees == 4
        assert fiche.type_organe_recolte == "reproducteur"
        exposition = next(a for a in fiche.attributs if a.cle == "exposition")
        assert exposition.affichage == "plein soleil"

    def test_us206_durees_du_referentiel_en_fourchette(self, db):
        """[CA3] Les quatre étapes de durée sont rendues, en fourchette quand
        le référentiel les porte."""
        _seed_culture(db, "tomate")
        _importer_durees(db, "tomate", levee="8-12", recolte="70-90")

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", None, DATE_REF)

        durees = {d.etape: d for d in fiche.durees}
        assert durees["levee"].jours_min == 8 and durees["levee"].jours_max == 12
        assert durees["recolte"].affichage != "—"

    def test_us206_variete_en_place_porte_sa_parcelle_et_sa_phase(self, db):
        """[CA4] Une variété en place restitue sa parcelle et la phase du
        moment (US-194) — même calcul que le Plan."""
        _seed_culture(db, "tomate")
        _evt(db, "plantation", "tomate", date(2026, 5, 1), parcelle_id=1, variete="Roma")

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", 1, DATE_REF)

        variete = next(v for v in fiche.varietes_cultivees if v.variete == "roma")
        assert len(variete.parcelles) == 1
        assert variete.parcelles[0].parcelle_id == 1
        assert variete.parcelles[0].phase == "en_place"

    def test_us206_voisinages_favorables_et_defavorables_avec_niveau_de_preuve(self, db):
        """[CA5][Gherkin: Fiche de la tomate] Associations lues dans les deux
        sens, avec leur niveau de preuve — même distinction que /association."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "basilic")
        _seed_culture(db, "chou")
        svc_associations.enregistrer_association(
            db, "tomate", "basilic", svc_associations.NATURE_FAVORABLE,
            "repousse les pucerons", svc_associations.NIVEAU_ETABLI,
        )
        svc_associations.enregistrer_association(
            db, "tomate", "chou", svc_associations.NATURE_DEFAVORABLE,
            "concurrence racinaire", svc_associations.NIVEAU_TRADITIONNEL,
        )

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", None, DATE_REF)

        assert fiche.associations_connues is True
        formulations = {a.autre_partie: a.formulation for a in fiche.associations}
        assert formulations["basilic"] != formulations["chou"]

    def test_us206_bioagresseurs_rendus_en_une_fois_jamais_tronques(self, db):
        """[CA6] Contrairement à la fiche courte du bot (limite à 5), la fiche
        PWA rend TOUS les bioagresseurs — l'écran gère le repli."""
        _seed_culture(db, "tomate")
        noms = [f"ravageur {i}" for i in range(7)]
        for nom in noms:
            svc_bioagresseurs.enregistrer_bioagresseur(db, nom, "insecte")
            svc_bioagresseurs.rattacher(db, "tomate", nom, "occasionnel")

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", None, DATE_REF)

        assert len(fiche.bioagresseurs) == 7
        assert fiche.bioagresseurs_connus is True

    def test_us206_attributions_dedupliquees(self, db):
        """[CA7] Une seule mention par source, même si plusieurs rubriques la
        citent (famille + attribut, ici)."""
        source = _seed_famille  # placeholder pour lisibilité, non utilisé
        del source
        from database.models import ReferentielSource
        ref_source = ReferentielSource(
            code="wikidata", libelle="wikidata", licence="CC0",
            attribution="Wikidata — CC0 1.0 Universal (domaine public)", partageable=True,
        )
        db.add(ref_source)
        db.commit()
        solanacee = _seed_famille(db, "Solanacée")
        config = _seed_culture(db, "tomate", famille=solanacee, exposition="plein soleil")
        config.famille_source_id = ref_source.id
        config.exposition_source_id = ref_source.id
        db.commit()

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", None, DATE_REF)

        assert fiche.attributions.count("Wikidata — CC0 1.0 Universal (domaine public)") == 1


# ═════════════════════════════════════════════════════════════════════════════
# Honnêteté et cas limites — CA2, CA3, CA8, CA9
# ═════════════════════════════════════════════════════════════════════════════

class TestHonneteteEtCasLimites:
    def test_us206_caracteristique_inconnue_vaut_non_renseigne(self, db):
        """[Gherkin: Caractéristique inconnue][CA2] La rusticité minimale de la
        courgette n'est pas renseignée : elle vaut « non renseigné »."""
        _seed_culture(db, "courgette")

        fiche = svc_fiche.composer_fiche_pwa(db, "courgette", None, DATE_REF)

        rusticite = next(a for a in fiche.attributs if a.cle == "rusticite_min_c")
        assert rusticite.renseigne is False

    def test_us206_duree_absente_reste_un_tiret_jamais_deduite(self, db):
        """[CA3] Une durée absente du référentiel reste « — », jamais déduite
        d'une autre étape (même garde qu'US-177)."""
        _seed_culture(db, "tomate")
        _importer_durees(db, "tomate", recolte="70-90")  # levée non renseignée

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", None, DATE_REF)

        levee = next(d for d in fiche.durees if d.etape == "levee")
        assert levee.jours_min is None
        assert levee.affichage == "—"

    def test_us206_variete_seulement_en_pepiniere_reste_visible(self, db):
        """[Gherkin: Bioagresseur local][CA4] Une variété seulement semée en
        pépinière (sans plantation) figure quand même, avec une liste de
        parcelles vide — jamais masquée."""
        _seed_culture(db, "tomate")
        _evt(db, "semis", "tomate", date(2026, 4, 1), parcelle_id=3, variete="Roma")

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", 1, DATE_REF)

        variete = next(v for v in fiche.varietes_cultivees if v.variete == "roma")
        assert variete.parcelles == ()
        assert variete.lots_pepiniere == ()

    def test_us206_culture_inconnue_rend_fiche_absente_sans_culture_voisine(self, db):
        """[Gherkin: Culture inconnue][CA8] Aucune fiche `culture_config` :
        `fiche_absente` à vrai, jamais une fiche voisine forcée. Ses variétés
        cultivées restent rendues."""
        _evt(db, "plantation", "verveine", date(2026, 5, 1), parcelle_id=1)

        fiche = svc_fiche.composer_fiche_pwa(db, "verveine", 1, DATE_REF)

        assert fiche.fiche_absente is True
        assert fiche.famille is None
        assert fiche.attributs == ()
        assert len(fiche.varietes_cultivees) == 1

    def test_us206_aucun_voisinage_connu_le_dit_explicitement(self, db):
        """[CA9] Aucune association connue : `associations_connues` à faux,
        distinct d'une absence de conflit."""
        _seed_culture(db, "poireau")

        fiche = svc_fiche.composer_fiche_pwa(db, "poireau", None, DATE_REF)

        assert fiche.associations == ()
        assert fiche.associations_connues is False

    def test_us206_aucun_bioagresseur_rattache_le_dit_explicitement(self, db):
        """[CA9] Aucun bioagresseur rattaché : `bioagresseurs_connus` à faux —
        pas une absence de risque, une absence d'information (US-162/CA12)."""
        _seed_culture(db, "poireau")

        fiche = svc_fiche.composer_fiche_pwa(db, "poireau", None, DATE_REF)

        assert fiche.bioagresseurs == ()
        assert fiche.bioagresseurs_connus is False

    def test_us206_bioagresseur_local_d_un_autre_potager_n_y_figure_jamais(self, db):
        """[Gherkin: Bioagresseur local][US-162/CA3] Une arête locale au
        potager A n'est jamais restituée au potager B."""
        _seed_culture(db, "poireau")
        svc_bioagresseurs.enregistrer_bioagresseur(db, "teigne du poireau", "insecte", potager_id=1)
        svc_bioagresseurs.rattacher(db, "poireau", "teigne du poireau", "courant", potager_id=1)

        fiche_a = svc_fiche.composer_fiche_pwa(db, "poireau", 1, DATE_REF)
        fiche_b = svc_fiche.composer_fiche_pwa(db, "poireau", 2, DATE_REF)

        assert any(b.local for b in fiche_a.bioagresseurs)
        assert fiche_b.bioagresseurs == ()


# ═════════════════════════════════════════════════════════════════════════════
# Cohérence avec le bot — CA10
# ═════════════════════════════════════════════════════════════════════════════

class TestCoherenceAvecLeBot:
    def test_us206_meme_famille_attributs_et_bioagresseurs_que_la_fiche_du_bot(self, db):
        """[CA10] `/fiche` (US-164) et `composer_fiche_pwa` partagent la même
        lecture de la famille, des attributs et des bioagresseurs (les cinq
        premiers, ordre identique — seule la troncature diffère, propre à la
        fiche courte du bot)."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "tomate", famille=solanacee, exposition="plein soleil")
        for nom in ("mildiou", "puceron", "aleurode"):
            svc_bioagresseurs.enregistrer_bioagresseur(db, nom, "insecte" if nom != "mildiou" else "champignon")
            svc_bioagresseurs.rattacher(db, "tomate", nom, "courant")

        fiche_bot = svc_fiche.generer_fiche_courte(db, "tomate", potager_id=1)
        fiche_pwa = svc_fiche.composer_fiche_pwa(db, "tomate", 1, DATE_REF)

        assert fiche_pwa.famille == fiche_bot.famille
        assert fiche_pwa.delai_retour_annees == fiche_bot.delai_retour_annees
        assert (
            {a.cle: a.affichage for a in fiche_pwa.attributs}
            == {a.cle: a.affichage for a in fiche_bot.attributs}
        )
        noms_pwa = [b.nom_commun_fr for b in fiche_pwa.bioagresseurs[: len(fiche_bot.bioagresseurs)]]
        noms_bot = [b.nom_commun_fr for b in fiche_bot.bioagresseurs]
        assert noms_pwa == noms_bot


# ═════════════════════════════════════════════════════════════════════════════
# Date de référence et zéro appel réseau — CA4/US-030, CA11
# ═════════════════════════════════════════════════════════════════════════════

class TestDateDeReferenceEtReseau:
    def test_us206_date_de_reference_passee_ignore_les_gestes_posterieurs(self, db):
        """Reculer la date de référence rend l'état exact à cette date — un
        geste postérieur n'existe pas encore pour la lecture (US-030)."""
        _seed_culture(db, "tomate")
        _evt(db, "plantation", "tomate", date(2026, 6, 15), parcelle_id=1, variete="Roma")

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", 1, date(2026, 6, 1))

        assert fiche.varietes_cultivees == ()

    def test_us206_zero_appel_reseau(self, db, monkeypatch):
        """[CA11] Toute tentative de sortie réseau fait échouer le test."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la composition de la fiche (CA11)")

        _seed_culture(db, "tomate", exposition="plein soleil")
        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        fiche = svc_fiche.composer_fiche_pwa(db, "tomate", None, DATE_REF)

        assert fiche.culture == "tomate"
