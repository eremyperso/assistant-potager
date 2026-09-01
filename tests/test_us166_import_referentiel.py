"""
tests/test_us166_import_referentiel.py
[US-166] Importer le référentiel structuré et tracer la source de chaque donnée

Couverture des critères d'acceptance CA1 → CA13, à l'exception d'un CA qui ne se
prête pas à un test pytest :

  - CA2, volet migration : le semis SQL du registre et le backfill
    `redaction_interne` sont garantis par `migrations/migration_v38.sql`, jamais
    rejoué en test — les tests tournent sur SQLite en mémoire construit depuis
    `database/models.py` (`Base.metadata.create_all`), pas depuis les migrations
    Postgres. Le semis équivalent côté application
    (`referentiel_sources.semer_sources_socle`, miroir de SOURCES_SOCLE) est lui
    testé ici, et le fichier SQL en est la copie littérale.

CA13 (couverture des tests) est satisfait par ce fichier lui-même.
"""
import json
import socket
from datetime import datetime

import pytest

from app.services import familles as svc_familles
from app.services import import_referentiel as svc_import
from app.services import rapport_couverture as svc_rapport
from app.services import referentiel_sources as svc_sources
from app.services.referentiel_sources import LicenceHorsSocleError
from database.models import CultureConfig, Evenement, FamilleBotanique, ReferentielSource

MANIFESTE_PROJET = "data/referentiel/wikidata_familles.json"


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


@pytest.fixture
def manifeste_wikidata() -> dict:
    """Manifeste minimal sous licence du socle — l'équivalent réduit du fichier projet."""
    return {
        "source": {
            "code": "wikidata",
            "libelle": "Wikidata",
            "licence": "CC0",
            "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
            "url": "https://www.wikidata.org/",
            "partageable": True,
        },
        "familles": [
            {"nom": "Solanacée", "nom_scientifique": "Solanaceae"},
            {"nom": "Astéracée", "nom_scientifique": "Asteraceae"},
        ],
        "cultures_familles": [
            {"culture": "tomate", "famille": "Solanacée"},
            {"culture": "laitue", "famille": "Astéracée"},
            {"culture": "salade", "famille": "Astéracée"},
        ],
    }


def _seed_culture(db, nom, famille=None, potager_id=None):
    config = CultureConfig(nom=nom, type_organe_recolte="reproducteur", potager_id=potager_id)
    if famille is not None:
        config.famille_rel = famille
    db.add(config)
    db.commit()
    return config


def _seed_evenement(db, culture, texte_original=None, potager_id=1):
    evenement = Evenement(
        date=datetime(2026, 5, 1),
        type_action="semis",
        culture=culture,
        texte_original=texte_original,
        potager_id=potager_id,
    )
    db.add(evenement)
    db.commit()
    return evenement


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — le registre de sources : code, licence, attribution, url, date d'import
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1RegistreDeSources:
    def test_us166_registre_enregistre_licence_attribution_et_url(self, db):
        """[CA1] Une source déclarée porte tout ce qu'il faut pour répondre
        « d'où sort cette information ? » sans consulter un README."""
        source = svc_sources.enregistrer_source(
            db,
            code="wikidata",
            libelle="Wikidata",
            licence=svc_sources.LICENCE_CC0,
            attribution="Wikidata — CC0 1.0 Universal (domaine public)",
            url="https://www.wikidata.org/",
        )

        assert source.code == "wikidata"
        assert source.licence == "CC0"
        assert source.attribution == "Wikidata — CC0 1.0 Universal (domaine public)"
        assert source.url == "https://www.wikidata.org/"
        # Déclarer une source n'est pas l'importer : la date reste vide.
        assert source.date_dernier_import is None

    def test_us166_registre_refuse_une_source_sans_attribution(self, db):
        """[CA1] L'attribution est une obligation par enregistrement : une source
        sans mention n'entre pas au registre, donc rien ne peut en dériver."""
        with pytest.raises(LicenceHorsSocleError):
            svc_sources.enregistrer_source(
                db, code="anonyme", libelle="Anonyme",
                licence=svc_sources.LICENCE_CC0, attribution="   ",
            )
        assert db.query(ReferentielSource).filter_by(code="anonyme").first() is None

    def test_us166_import_date_la_source(self, db, manifeste_wikidata):
        """[CA1] La date du dernier import est posée par l'import lui-même,
        pas à la déclaration de la source."""
        svc_import.importer(db, manifeste_wikidata)

        source = svc_sources.get_source(db, "wikidata")
        assert source.date_dernier_import is not None

    def test_us166_toute_donnee_importee_est_rattachee_a_sa_source(self, db, manifeste_wikidata):
        """[CA1] Aucune famille créée par l'import ne reste sans rattachement."""
        svc_import.importer(db, manifeste_wikidata)

        source = svc_sources.get_source(db, "wikidata")
        familles = db.query(FamilleBotanique).all()
        assert familles
        assert all(f.source_id == source.id for f in familles)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — l'indicateur `partageable`
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2Partageable:
    def test_us166_toutes_les_sources_du_socle_sont_partageables(self, db):
        """[CA2] Option A : le socle retenu aujourd'hui est intégralement
        partageable — aucune source contaminante n'est en base."""
        sources = svc_sources.semer_sources_socle(db)

        assert len(sources) == len(svc_sources.SOURCES_SOCLE)
        assert all(s.partageable for s in sources)

    def test_us166_partageable_peut_valoir_false_sans_migration(self, db):
        """[CA2] La colonne rend l'option B réversiblement atteignable : une
        source non partageable s'enregistre sans changement de schéma, et se
        distingue en une requête de celles qui sont exportables."""
        svc_sources.semer_sources_socle(db)
        svc_sources.enregistrer_source(
            db, code="source_contaminante", libelle="Source à partage à l'identique",
            licence=svc_sources.LICENCE_CC0, attribution="Attribution requise",
            partageable=False,
        )

        exportables = db.query(ReferentielSource).filter_by(partageable=True).all()
        assert "source_contaminante" not in [s.code for s in exportables]
        assert len(exportables) == len(svc_sources.SOURCES_SOCLE)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — les origines non importées : il n'existe aucune donnée sans origine
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3OriginesNonImportees:
    def test_us166_le_registre_reconnait_saisie_et_redaction_interne(self, db):
        """[CA3] Saisie manuelle et rédaction interne sont des origines à part
        entière, marquées comme non importées."""
        svc_sources.semer_sources_socle(db)

        non_importees = db.query(ReferentielSource).filter_by(importee=False).all()
        assert {s.code for s in non_importees} == {"saisie_manuelle", "redaction_interne"}

    def test_us166_correction_au_bot_est_tracee_comme_saisie_manuelle(self, db):
        """[CA3] Une donnée saisie par le jardinier est tracée au même titre
        qu'une donnée importée — la correction de famille au bot porte son origine."""
        _seed_culture(db, "tomate")

        fiches, _ancienne = svc_familles.corriger_famille_culture(db, "tomate", "Solanacée")

        saisie = svc_sources.get_source(db, svc_sources.SOURCE_SAISIE_MANUELLE)
        assert saisie is not None
        assert fiches[0].famille_source_id == saisie.id
        assert fiches[0].famille_rel.source_id == saisie.id

    def test_us166_correction_de_delai_est_tracee_comme_saisie_manuelle(self, db):
        """[CA3] Idem pour la correction d'un délai de retour au bot."""
        db.add(FamilleBotanique(nom="Solanacée", nom_normalise="solanacee", delai_retour_annees=4))
        db.commit()

        famille, _ancien = svc_familles.corriger_delai_retour(db, "Solanacée", 5)

        saisie = svc_sources.get_source(db, svc_sources.SOURCE_SAISIE_MANUELLE)
        assert famille.source_id == saisie.id


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — retirer une source : identifier en une requête tout ce qui en dérive
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4TracabiliteRetraitSource:
    def test_us166_donnees_derivees_liste_familles_et_rattachements(self, db, manifeste_wikidata):
        """[CA4] Une source devenue litigieuse : tout ce qui en dérive est
        identifié, table par table, sans fouiller le code."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, manifeste_wikidata)

        derives = svc_sources.donnees_derivees(db, "wikidata")

        tables = {ligne["table"] for ligne in derives}
        assert tables == {"familles_botaniques", "culture_config"}
        libelles = {ligne["libelle"] for ligne in derives}
        assert {"Solanacée", "Astéracée", "tomate"} <= libelles

    def test_us166_donnees_derivees_distingue_les_sources(self, db, manifeste_wikidata):
        """[CA4] Retirer Wikidata ne doit pas emporter ce qu'a saisi le jardinier :
        les deux origines sont distinguables par la même requête."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, manifeste_wikidata)
        _seed_culture(db, "courgette")
        svc_familles.corriger_famille_culture(db, "courgette", "Cucurbitacée")

        libelles_wikidata = {l["libelle"] for l in svc_sources.donnees_derivees(db, "wikidata")}
        libelles_saisie = {
            l["libelle"] for l in svc_sources.donnees_derivees(db, svc_sources.SOURCE_SAISIE_MANUELLE)
        }

        assert "courgette" not in libelles_wikidata
        assert "Cucurbitacée" not in libelles_wikidata
        assert {"courgette", "Cucurbitacée"} <= libelles_saisie

    def test_us166_source_inconnue_ne_derive_rien(self, db):
        """[CA4] Une source absente du registre ne peut avoir aucune donnée dérivée."""
        assert svc_sources.donnees_derivees(db, "source_jamais_declaree") == []


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — import hors ligne, idempotent, rejouable, non destructeur
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5ImportRejouable:
    def test_us166_import_rejoue_ne_cree_aucun_doublon(self, db, manifeste_wikidata):
        """[CA5][Gherkin: Import rejoué sans doublon] Rejouer est une opération banale."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, manifeste_wikidata)
        apres_premier = db.query(FamilleBotanique).count()

        resultat = svc_import.importer(db, manifeste_wikidata)

        assert db.query(FamilleBotanique).count() == apres_premier
        assert resultat.familles_creees == []
        assert db.query(ReferentielSource).filter_by(code="wikidata").count() == 1

    def test_us166_rejeu_sur_source_mise_a_jour_ajoute_les_nouvelles_entrees(
        self, db, manifeste_wikidata
    ):
        """[CA5][Gherkin: Import rejoué sans doublon] Les nouvelles entrées d'une
        version mise à jour de la source sont ajoutées, les anciennes intactes."""
        svc_import.importer(db, manifeste_wikidata)
        manifeste_wikidata["familles"].append(
            {"nom": "Cucurbitacée", "nom_scientifique": "Cucurbitaceae"}
        )

        resultat = svc_import.importer(db, manifeste_wikidata)

        assert resultat.familles_creees == ["Cucurbitacée"]
        assert db.query(FamilleBotanique).count() == 3

    def test_us166_correction_humaine_preservee_au_rejeu(self, db, manifeste_wikidata):
        """[CA5][Gherkin: Correction humaine préservée] Le jardinier a corrigé un
        attribut à la main : le rejeu le conserve et le signale."""
        svc_import.importer(db, manifeste_wikidata)
        svc_familles.corriger_delai_retour(db, "Solanacée", 7)
        manifeste_wikidata["familles"][0]["delai_retour_annees"] = 3

        resultat = svc_import.importer(db, manifeste_wikidata)

        famille = svc_familles.get_famille(db, "Solanacée")
        assert famille.delai_retour_annees == 7
        assert "Solanacée" in resultat.familles_preservees

    def test_us166_rattachement_corrige_a_la_main_preserve_au_rejeu(self, db, manifeste_wikidata):
        """[CA5] Une culture rattachée à la main à une autre famille que celle du
        fichier source garde le rattachement du jardinier."""
        _seed_culture(db, "tomate")
        svc_familles.corriger_famille_culture(db, "tomate", "Cucurbitacée")

        resultat = svc_import.importer(db, manifeste_wikidata)

        fiche = db.query(CultureConfig).filter_by(nom="tomate").first()
        assert fiche.famille_rel.nom == "Cucurbitacée"
        assert "tomate" in resultat.cultures_preservees
        assert "tomate" not in resultat.cultures_rattachees

    def test_us166_import_enrichit_un_champ_absent(self, db, manifeste_wikidata):
        """[CA5] Enrichir un trou n'est pas écraser : une famille déjà présente
        sans nom scientifique le reçoit de l'import."""
        db.add(FamilleBotanique(nom="Solanacée", nom_normalise="solanacee", delai_retour_annees=4))
        db.commit()

        resultat = svc_import.importer(db, manifeste_wikidata)

        famille = svc_familles.get_famille(db, "Solanacée")
        assert famille.nom_scientifique == "Solanaceae"
        assert famille.delai_retour_annees == 4  # la valeur existante n'a pas bougé
        assert "Solanacée" in resultat.familles_enrichies

    def test_us166_import_rafraichit_sa_propre_donnee(self, db, manifeste_wikidata):
        """[CA5] Une source peut corriger ce qu'elle a elle-même écrit — sans quoi
        une mise à jour hebdomadaire ne servirait à rien."""
        svc_import.importer(db, manifeste_wikidata)
        manifeste_wikidata["familles"][0]["nom_scientifique"] = "Solanaceae Juss."

        svc_import.importer(db, manifeste_wikidata)

        assert svc_familles.get_famille(db, "Solanacée").nom_scientifique == "Solanaceae Juss."

    def test_us166_dry_run_n_ecrit_rien(self, db, manifeste_wikidata):
        """[CA5] La simulation compte ce qui serait fait sans rien écrire."""
        _seed_culture(db, "tomate")

        resultat = svc_import.importer(db, manifeste_wikidata, dry_run=True)

        assert resultat.dry_run is True
        assert resultat.total_ecritures > 0
        assert db.query(FamilleBotanique).count() == 0
        assert db.query(ReferentielSource).filter_by(code="wikidata").first() is None

    def test_us166_manifeste_du_projet_est_importable(self, db):
        """[CA5] Le fichier réellement versionné dans `data/referentiel/` s'importe
        et se rejoue — le test le plus proche de l'usage d'administration."""
        _seed_culture(db, "tomate")

        premier = svc_import.importer_fichier(db, MANIFESTE_PROJET)
        second = svc_import.importer_fichier(db, MANIFESTE_PROJET)

        assert "tomate" in premier.cultures_rattachees
        assert premier.familles_creees
        assert second.familles_creees == []
        assert second.cultures_rattachees == []


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — aucune source hors socle n'est ingérée
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6RefusHorsSocle:
    def test_us166_licence_ccbysa_refusee_et_rien_cree(self, db, manifeste_wikidata):
        """[CA6][Gherkin: Source hors socle refusée] Une clause de partage à
        l'identique contaminerait le corpus : refus, et rien n'est créé."""
        manifeste_wikidata["source"]["code"] = "permapeople"
        manifeste_wikidata["source"]["licence"] = "CC-BY-SA-4.0"

        with pytest.raises(LicenceHorsSocleError):
            svc_import.importer(db, manifeste_wikidata)

        assert db.query(ReferentielSource).count() == 0
        assert db.query(FamilleBotanique).count() == 0

    @pytest.mark.parametrize("licence", [None, "", "   ", "inconnue", "proprietaire"])
    def test_us166_licence_non_etablie_ou_hors_socle_refusee(self, db, manifeste_wikidata, licence):
        """[CA6] « Non établie » et « établie hors socle » sont traitées
        identiquement — ni « en attendant », ni « pour tester ».
        `proprietaire` est refusé à l'import : il ne vaut que pour une origine interne."""
        manifeste_wikidata["source"]["licence"] = licence

        with pytest.raises(LicenceHorsSocleError):
            svc_import.importer(db, manifeste_wikidata)
        assert db.query(FamilleBotanique).count() == 0

    def test_us166_socle_de_licences_ferme(self):
        """[CA6] Le socle importable est fermé, et il énumère ses licences.

        ⚠️ Élargi par US-161 le 01/09/2026 : `CC BY 4.0` s'y ajoute pour Wind
        River Greens. Ce n'est pas un renoncement au CA6 — l'arbitrage §6.3
        n'écarte que le **partage à l'identique**, et CC BY n'a aucune clause
        virale. Le test suivant vérifie que CC-BY-SA reste dehors."""
        assert svc_sources.LICENCES_IMPORTABLES == frozenset({
            "CC0", "Licence Ouverte 2.0", "CC BY 4.0",
        })
        assert "CC-BY-SA-4.0" not in svc_sources.LICENCES_IMPORTABLES

    def test_us166_manifeste_sans_bloc_source_refuse(self, db, tmp_path):
        """[CA6] Un jeu de données qui ne déclare pas sa source ne peut pas être
        tracé, donc pas importé."""
        fichier = tmp_path / "sans_source.json"
        fichier.write_text(json.dumps({"familles": [{"nom": "Solanacée"}]}), encoding="utf-8")

        with pytest.raises(svc_import.ManifesteInvalideError):
            svc_import.importer_fichier(db, fichier)
        assert db.query(FamilleBotanique).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — l'import ne crée aucune configuration de culture
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7AucuneCultureFantome:
    def test_us166_aucune_culture_config_creee(self, db, manifeste_wikidata):
        """[CA7][Gherkin: Aucune culture fantôme créée] Le fichier source couvre
        des cultures absentes du potager : aucune configuration n'est créée."""
        _seed_culture(db, "tomate")

        resultat = svc_import.importer(db, manifeste_wikidata)

        assert db.query(CultureConfig).count() == 1
        assert set(resultat.cultures_ignorees) == {"laitue", "salade"}

    def test_us166_import_enrichit_les_configurations_existantes(self, db, manifeste_wikidata):
        """[CA7] Il enrichit celles qui existent — c'est bien un import utile,
        pas un simple refus généralisé."""
        _seed_culture(db, "tomate")

        svc_import.importer(db, manifeste_wikidata)

        fiche = db.query(CultureConfig).filter_by(nom="tomate").first()
        assert fiche.famille_rel.nom == "Solanacée"
        assert fiche.famille_rel.nom_scientifique == "Solanaceae"

    def test_us166_rattachement_applique_a_toutes_les_fiches_du_meme_nom(
        self, db, manifeste_wikidata
    ):
        """[CA7 + US-067/CA7] La famille est un fait : les deux fiches « tomate »
        (globale et personnalisée) sont rattachées, jamais une seule des deux."""
        _seed_culture(db, "tomate", potager_id=None)
        _seed_culture(db, "Tomate", potager_id=2)

        svc_import.importer(db, manifeste_wikidata)

        fiches = db.query(CultureConfig).all()
        assert all(f.famille_rel is not None and f.famille_rel.nom == "Solanacée" for f in fiches)


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — aucun appel réseau
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8HorsReseau:
    def test_us166_import_et_rapport_n_ouvrent_aucune_socket(
        self, db, manifeste_wikidata, monkeypatch
    ):
        """[CA8][Gherkin: Aucun appel réseau en réponse] Toute tentative de sortie
        réseau fait échouer le test — ingestion hors ligne, exécution hors réseau."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit pendant l'import (CA8)")

        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        _seed_culture(db, "tomate")
        _seed_evenement(db, "tomate")
        svc_import.importer(db, manifeste_wikidata)
        svc_rapport.construire_rapport(db)

    def test_us166_modules_d_import_n_embarquent_aucun_client_http(self):
        """[CA8] La garantie tient au chargement, pas seulement à l'exécution :
        les modules du chemin d'import ne référencent aucun client HTTP."""
        import inspect

        for module in (svc_import, svc_sources, svc_rapport):
            source = inspect.getsource(module)
            for interdit in ("import requests", "import httpx", "urllib.request"):
                assert interdit not in source, f"{module.__name__} référence {interdit}"


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — le rapport de couverture et ses trois états
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9TroisEtatsDeCouverture:
    @pytest.fixture
    def base_mesuree(self, db, manifeste_wikidata):
        """tomate : couverte — laitue : configurée mais non enrichie —
        asperge : configurée jamais utilisée."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "laitue")
        _seed_culture(db, "asperge")
        _seed_evenement(db, "tomate")
        _seed_evenement(db, "laitue")
        manifeste_wikidata["cultures_familles"] = [{"culture": "tomate", "famille": "Solanacée"}]
        svc_import.importer(db, manifeste_wikidata)
        return db

    def test_us166_rapport_distingue_les_trois_etats(self, base_mesuree):
        """[CA9] Couvert, non couvert, et configuré mais jamais utilisé — trois
        états explicites, pas deux et une nuance."""
        rapport = svc_rapport.construire_rapport(base_mesuree)

        assert rapport.couvert == ["tomate"]
        assert rapport.non_couvert == ["laitue"]
        assert rapport.configure_jamais_utilise == ["asperge"]

    def test_us166_configure_jamais_utilise_exclu_du_taux(self, base_mesuree):
        """[CA9] Compter les 14 configurations sans événement comme couvertes
        maquillerait le taux — elles sont hors du dénominateur."""
        rapport = svc_rapport.construire_rapport(base_mesuree)

        assert rapport.total_cultures_presentes == 2
        assert rapport.taux_appariement == 0.5

    def test_us166_bulletins_auto_meteo_exclus_des_statistiques(self, db):
        """[CA9] 30 % des événements de production sont du bruit machine : un
        bulletin `[AUTO-METEO]` ne rend aucune culture « présente »."""
        _seed_evenement(db, "brouillard", texte_original="[AUTO-METEO]")
        _seed_culture(db, "tomate")
        _seed_evenement(db, "tomate", texte_original="j'ai semé des tomates")

        rapport = svc_rapport.construire_rapport(db)

        assert rapport.total_cultures_presentes == 1
        assert "brouillard" not in rapport.cultures_suspectes

    def test_us166_rapport_formate_est_lisible(self, base_mesuree):
        """[CA9] Le rapport est un livrable : sa forme console nomme les trois états."""
        texte = svc_rapport.formater_rapport(svc_rapport.construire_rapport(base_mesuree))

        assert "couvert" in texte
        assert "configuré mais jamais utilisé" in texte
        assert "Taux d'appariement" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — les cultures suspectes
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10CulturesSuspectes:
    def test_us166_culture_inconnue_de_la_configuration_est_suspecte(self, db):
        """[CA10][Gherkin: Culture suspecte signalée] `radi`, né d'une question
        enregistrée comme un événement, est signalé — et aucune fiche n'est créée."""
        _seed_evenement(db, "radi")

        rapport = svc_rapport.construire_rapport(db)

        assert rapport.cultures_suspectes == ["radi"]
        assert db.query(CultureConfig).count() == 0

    def test_us166_culture_suspecte_ne_declenche_aucune_creation_de_fiche(
        self, db, manifeste_wikidata
    ):
        """[CA10] Une culture fantôme issue d'un échec de parsing ne doit JAMAIS
        déclencher la création d'une fiche, même quand l'import passe après elle."""
        _seed_evenement(db, "radi")

        svc_import.importer(db, manifeste_wikidata)

        assert db.query(CultureConfig).count() == 0
        assert svc_rapport.construire_rapport(db).cultures_suspectes == ["radi"]

    def test_us166_culture_suspecte_pese_sur_le_taux(self, db):
        """[CA10] Une suspecte est présente dans l'historique : elle compte au
        dénominateur, sans quoi le taux d'appariement se flatterait tout seul."""
        _seed_culture(db, "tomate", famille=FamilleBotanique(nom="Solanacée", nom_normalise="solanacee"))
        _seed_evenement(db, "tomate")
        _seed_evenement(db, "radi")

        rapport = svc_rapport.construire_rapport(db)

        assert rapport.total_cultures_presentes == 2
        assert rapport.taux_appariement == 0.5


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — les synonymes probables, signalés mais jamais fusionnés
# ═════════════════════════════════════════════════════════════════════════════

class TestCA11SynonymesProbables:
    def test_us166_laitue_et_salade_signalees_sans_fusion(self, db, manifeste_wikidata):
        """[CA11][Gherkin: Synonymes soumis à revue] Le cas mesuré, rapproché par
        la seule clé qui les relie — la famille — et jamais fusionné."""
        _seed_culture(db, "laitue")
        _seed_culture(db, "salade")
        _seed_evenement(db, "laitue")
        _seed_evenement(db, "salade")
        svc_import.importer(db, manifeste_wikidata)

        rapport = svc_rapport.construire_rapport(db)

        groupes = [set(g.libelles) for g in rapport.synonymes_probables]
        assert {"laitue", "salade"} in groupes
        # Aucune fusion : les deux fiches et les deux libellés survivent.
        assert db.query(CultureConfig).count() == 2
        assert {"laitue", "salade"} <= set(rapport.couvert)

    def test_us166_haricot_et_haricot_grimpant_signales_par_sous_chaine(self, db):
        """[CA11] L'indice le plus fiable des trois : un libellé contenu dans l'autre."""
        _seed_culture(db, "haricot")
        _seed_culture(db, "haricot grimpant")
        _seed_evenement(db, "haricot")
        _seed_evenement(db, "haricot grimpant")

        rapport = svc_rapport.construire_rapport(db)

        sous_chaine = [
            g for g in rapport.synonymes_probables
            if g.indice == svc_rapport.INDICE_SOUS_CHAINE
        ]
        assert [set(g.libelles) for g in sous_chaine] == [{"haricot", "haricot grimpant"}]

    def test_us166_cucurbitacees_regroupees_en_une_seule_ligne_de_revue(
        self, db, manifeste_wikidata
    ):
        """[CA11] Les dix libellés de cucurbitacées forment UN groupe à relire,
        pas quarante-cinq paires — c'est ce qui rend leur poids cumulé visible."""
        libelles = [
            "courgette", "cornichon", "concombre", "melon", "potiron",
            "butternut", "courge", "potimarron", "pâtisson", "pastèque",
        ]
        for libelle in libelles:
            _seed_culture(db, libelle)
            _seed_evenement(db, libelle)
        manifeste_wikidata["familles"] = [{"nom": "Cucurbitacée", "nom_scientifique": "Cucurbitaceae"}]
        manifeste_wikidata["cultures_familles"] = [
            {"culture": libelle, "famille": "Cucurbitacée"} for libelle in libelles
        ]
        svc_import.importer(db, manifeste_wikidata)

        rapport = svc_rapport.construire_rapport(db)

        familles = [
            g for g in rapport.synonymes_probables
            if g.indice == svc_rapport.INDICE_MEME_FAMILLE
        ]
        assert len(familles) == 1
        assert set(familles[0].libelles) == set(libelles)

    def test_us166_indice_le_moins_fiable_est_annonce_comme_tel(self, db, manifeste_wikidata):
        """[CA11] Le rapprochement par nom vernaculaire est la clé la moins
        fiable : le rapport le dit, pour que la relecture soit priorisée."""
        _seed_culture(db, "laitue")
        _seed_culture(db, "salade")
        _seed_evenement(db, "laitue")
        _seed_evenement(db, "salade")
        svc_import.importer(db, manifeste_wikidata)

        groupe = svc_rapport.construire_rapport(db).synonymes_probables[0]

        assert groupe.indice == svc_rapport.INDICE_MEME_FAMILLE
        assert "relecture obligatoire" in groupe.detail

    def test_us166_cultures_distinctes_ne_sont_pas_rapprochees(self, db):
        """[CA11] Pas de faux positif lexical : deux cultures sans parenté ni
        famille commune ne sont pas proposées à la fusion."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "poireau")
        _seed_evenement(db, "tomate")
        _seed_evenement(db, "poireau")

        assert svc_rapport.construire_rapport(db).synonymes_probables == []


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — le taux d'appariement automatique
# ═════════════════════════════════════════════════════════════════════════════

class TestCA12TauxAppariement:
    def test_us166_taux_publie_et_seuil_atteint(self, db, manifeste_wikidata):
        """[CA12] Au-dessus d'environ 70 %, l'import automatique tient sa promesse."""
        for nom in ("tomate", "laitue", "salade"):
            _seed_culture(db, nom)
            _seed_evenement(db, nom)
        svc_import.importer(db, manifeste_wikidata)

        rapport = svc_rapport.construire_rapport(db)

        assert rapport.taux_appariement == 1.0
        assert rapport.seuil_appariement_atteint is True

    def test_us166_taux_sous_le_seuil_signale_le_repli_manuel(self, db, manifeste_wikidata):
        """[CA12] En dessous du seuil, l'import perd son intérêt face à la saisie
        directe : le rapport le dit explicitement plutôt que de publier un chiffre nu."""
        for nom in ("tomate", "topinambour", "cardon", "crosne"):
            _seed_culture(db, nom)
            _seed_evenement(db, nom)
        svc_import.importer(db, manifeste_wikidata)

        rapport = svc_rapport.construire_rapport(db)

        assert rapport.taux_appariement == 0.25
        assert rapport.seuil_appariement_atteint is False
        assert "SOUS LE SEUIL" in svc_rapport.formater_rapport(rapport)

    def test_us166_taux_nul_sur_base_vide_sans_division_par_zero(self, db):
        """[CA12] Cas limite : aucune culture présente, aucun plantage."""
        rapport = svc_rapport.construire_rapport(db)

        assert rapport.taux_appariement == 0.0
        assert rapport.total_cultures_presentes == 0

    def test_us166_seuil_documente_a_70_pourcent(self):
        """[CA12] Le seuil de décision est une constante lisible, pas un nombre
        magique enfoui dans une condition."""
        assert svc_rapport.SEUIL_APPARIEMENT == 0.70
