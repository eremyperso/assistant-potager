"""
tests/test_us162_bioagresseurs.py
[US-162] Modéliser les bioagresseurs et leur relation aux cultures

Couverture des critères d'acceptance CA1 → CA13.

CA7 est le seul critère qui ne se démontre pas par un test de code : « les
conditions d'utilisation de `data.eppo.int` sont lues et consignées » est un
acte humain, dont le livrable est `data/referentiel/eppo/SOURCE.md`. Ce fichier
vérifie donc ce qui EST vérifiable de ce CA — que la consignation existe, qu'elle
nomme la licence exacte, et que le registre en porte la conséquence (la source
`eppo` déclarée avec cette licence, l'attribution datée du dernier
téléchargement comme la licence l'exige).

CA13 (couverture des tests) est satisfait par ce fichier lui-même. CA10 (aucune
prescription) et CA11 (aucun narratif) sont vérifiés STRUCTURELLEMENT : ce qui
les garantit n'est pas une consigne de rédaction mais l'absence de colonne où
stocker un dosage ou une description. Le « zéro jeton » du CA2/CA13 est vérifié
activement (réseau coupé + passerelle LLM sous surveillance), pas supposé de
l'absence d'import Groq.
"""
import json
import socket
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import bioagresseurs as svc_bio
from app.services import import_referentiel as svc_import
from app.services import referentiel_sources as svc_sources
from app.services.context import TenantContext
from database.models import (
    Bioagresseur, CultureBioagresseur, CultureConfig, ReferentielSource,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUTRE_POTAGER = 2


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    svc_sources.semer_sources_socle(test_db)
    return test_db


def _seed_culture(db, nom, type_organe="vegetatif", potager_id=None):
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=potager_id)
    db.add(cfg)
    db.commit()
    return cfg


def _manifeste(**blocs):
    """Manifeste minimal `redaction_interne` — origine interne, donc dispensée du
    contrôle de licence (US-161), ce qui laisse ces tests porter sur US-162."""
    base = {"source": {"code": svc_sources.SOURCE_REDACTION_INTERNE}}
    base.update(blocs)
    return base


def _manifeste_ephy(**blocs):
    """Manifeste E-Phy — la source d'import tranchée pour cette US (CA6)."""
    base = {
        "source": {
            "code": svc_sources.SOURCE_EPHY_ANSES,
            "libelle": "Catalogue E-Phy (ANSES)",
            "licence": svc_sources.LICENCE_LICENCE_OUVERTE,
            "attribution": "ANSES — catalogue E-Phy, Licence Ouverte 2.0 (Etalab)",
        }
    }
    base.update(blocs)
    return base


MILDIOU = {
    "nom_commun_fr": "mildiou de la tomate",
    "nom_scientifique": "Phytophthora infestans",
    "categorie": "champignon",
    "code_eppo": "PHYTIN",
}


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Une identité propre
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Identite:
    def test_us162_bioagresseur_porte_les_quatre_champs_d_identite(self, db):
        """[CA1] Nom commun FR, nom scientifique, catégorie et code EPPO."""
        bio, cree = svc_bio.enregistrer_bioagresseur(
            db, nom_commun_fr="Mildiou de la Tomate", categorie="champignon",
            nom_scientifique="Phytophthora infestans", code_eppo="phytin",
        )

        assert cree is True
        assert bio.nom_commun_fr == "Mildiou de la Tomate"
        assert bio.nom_scientifique == "Phytophthora infestans"
        assert bio.categorie == "champignon"
        # Le code EPPO est normalisé en majuscules : c'est une clé, pas un libellé.
        assert bio.code_eppo == "PHYTIN"

    def test_us162_resolution_insensible_a_la_casse_et_aux_accents(self, db):
        """[CA1] Même stratégie que Parcelle.nom_normalise et normaliser_culture."""
        svc_bio.enregistrer_bioagresseur(db, "Nécrose apicale", "carence")

        assert svc_bio.get_bioagresseur(db, "necrose APICALE") is not None

    def test_us162_resolution_par_code_eppo(self, db):
        """[CA1] Le code EPPO est la clé de rapprochement — pas seulement un champ
        d'affichage : il doit résoudre."""
        svc_bio.enregistrer_bioagresseur(db, "mildiou", "champignon", code_eppo="PHYTIN")

        assert svc_bio.get_bioagresseur(db, "phytin").nom_commun_fr == "mildiou"

    @pytest.mark.parametrize("categorie", [
        "champignon", "insecte", "mollusque", "nematode",
        "bacterie", "virus", "abiotique", "carence",
    ])
    def test_us162_les_categories_du_vocabulaire_ferme(self, db, categorie):
        """[CA1] Le vocabulaire annoncé est celui accepté — celui-là, exactement.

        Les six catégories du CA1, plus `mollusque` et `nematode` ajoutés le
        06/09/2026 : sans eux, les limaces et les nématodes à galles tombaient
        en `insecte` faute de case. Le CHECK absent en base est ce qui a rendu
        cet élargissement possible sans migration."""
        bio, _ = svc_bio.enregistrer_bioagresseur(db, f"agresseur {categorie}", categorie)
        assert bio.categorie == categorie

    def test_us162_limace_et_nematode_ne_sont_pas_des_insectes(self, db):
        """[CA1] Le cas qui a motivé l'élargissement — une limace annoncée
        « insecte » fait douter le jardinier de tout le reste."""
        limace, _ = svc_bio.enregistrer_bioagresseur(
            db, "limaces", "mollusque", nom_scientifique="Deroceras reticulatum"
        )
        nematode, _ = svc_bio.enregistrer_bioagresseur(
            db, "nématodes à galles", "nematode", nom_scientifique="Meloidogyne incognita"
        )

        assert limace.categorie == svc_bio.CATEGORIE_MOLLUSQUE
        assert nematode.categorie == svc_bio.CATEGORIE_NEMATODE

    @pytest.mark.parametrize("categorie", ["fongique", "PARASITE", "", None])
    def test_us162_categorie_hors_vocabulaire_refusee_sans_rien_ecrire(self, db, categorie):
        """[CA1] Une valeur refusée ne doit toucher à rien — la validation précède
        toute écriture (même garde que associations._valider)."""
        with pytest.raises(svc_bio.ValeurBioagresseurInvalideError):
            svc_bio.enregistrer_bioagresseur(db, "quelque chose", categorie)

        assert db.query(Bioagresseur).count() == 0

    def test_us162_nom_vide_refuse(self, db):
        """[CA1] Une identité sans nom n'est pas une identité."""
        with pytest.raises(svc_bio.ValeurBioagresseurInvalideError):
            svc_bio.enregistrer_bioagresseur(db, "   ", "insecte")

        assert db.query(Bioagresseur).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — La relation est une table de liaison, lue à zéro jeton
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2Relation:
    def test_us162_liste_ordonnee_par_frequence(self, db):
        """[Gherkin: Ce qui attaque une culture] La liste est restituée, ordonnée
        par fréquence — un ordre MÉTIER (courant d'abord), pas alphabétique."""
        _seed_culture(db, "poireau")
        for nom, frequence in (
            ("rouille du poireau", "rare"),
            ("teigne du poireau", "courant"),
            ("thrips", "occasionnel"),
        ):
            svc_bio.enregistrer_bioagresseur(db, nom, "insecte")
            svc_bio.rattacher(db, "poireau", nom, frequence)

        lus = svc_bio.lire_bioagresseurs(db, "poireau")

        assert [b.frequence for b in lus] == ["courant", "occasionnel", "rare"]
        assert lus[0].nom_commun_fr == "teigne du poireau"

    def test_us162_periode_de_risque_conservee_et_nullable(self, db):
        """[CA2] Une période connue est restituée ; une période inconnue reste
        None — jamais comblée par « toute l'année »."""
        _seed_culture(db, "tomate")
        svc_bio.enregistrer_bioagresseur(db, "mildiou", "champignon")
        svc_bio.enregistrer_bioagresseur(db, "pucerons", "insecte")
        svc_bio.rattacher(db, "tomate", "mildiou", "courant", periode_risque="juin-septembre")
        svc_bio.rattacher(db, "tomate", "pucerons", "occasionnel")

        par_nom = {b.nom_commun_fr: b for b in svc_bio.lire_bioagresseurs(db, "tomate")}

        assert par_nom["mildiou"].periode_risque == "juin-septembre"
        assert par_nom["pucerons"].periode_risque is None

    @pytest.mark.parametrize("frequence", ["souvent", "TRÈS COURANT", "", None])
    def test_us162_frequence_hors_vocabulaire_refusee(self, db, frequence):
        """[CA2] Vocabulaire fermé, validé avant toute écriture."""
        _seed_culture(db, "tomate")
        svc_bio.enregistrer_bioagresseur(db, "mildiou", "champignon")

        with pytest.raises(svc_bio.ValeurBioagresseurInvalideError):
            svc_bio.rattacher(db, "tomate", "mildiou", frequence)

        assert db.query(CultureBioagresseur).count() == 0

    def test_us162_culture_inconnue_jamais_creee(self, db):
        """[CA7 d'US-161, même invariant] Le référentiel s'enrichit, il ne se
        peuple pas de cultures fantômes."""
        svc_bio.enregistrer_bioagresseur(db, "mildiou", "champignon")

        with pytest.raises(svc_bio.CultureInconnueError):
            svc_bio.rattacher(db, "salsifis", "mildiou", "courant")

        assert db.query(CultureConfig).count() == 0

    def test_us162_bioagresseur_inconnu_jamais_fabrique_par_un_rattachement(self, db):
        """[CA1] Une identité se déclare explicitement — un nom inconnu au moment
        d'un rattachement est plus probablement une faute de frappe."""
        _seed_culture(db, "tomate")

        with pytest.raises(svc_bio.BioagresseurInconnuError):
            svc_bio.rattacher(db, "tomate", "mildoiu", "courant")

        assert db.query(Bioagresseur).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Isolation : potager_id nul = partagé, et le local ne remonte jamais
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3Isolation:
    def test_us162_bioagresseur_local_invisible_des_autres_potagers(self, db):
        """[Gherkin: Bioagresseur local à un potager] Un jardinier d'un autre
        potager ne le voit pas."""
        _seed_culture(db, "chou")
        svc_bio.enregistrer_bioagresseur(
            db, "altise de Vitry", "insecte", potager_id=CTX.potager_id
        )
        svc_bio.rattacher(db, "chou", "altise de Vitry", "courant", potager_id=CTX.potager_id)

        chez_lui = svc_bio.lire_bioagresseurs(db, "chou", potager_id=CTX.potager_id)
        chez_l_autre = svc_bio.lire_bioagresseurs(db, "chou", potager_id=AUTRE_POTAGER)

        assert [b.nom_commun_fr for b in chez_lui] == ["altise de Vitry"]
        assert chez_l_autre == []

    def test_us162_le_partage_est_visible_de_tous(self, db):
        """[CA3] `potager_id` NULL = connaissance partagée — le pattern du projet."""
        _seed_culture(db, "tomate")
        svc_bio.enregistrer_bioagresseur(db, "mildiou", "champignon")
        svc_bio.rattacher(db, "tomate", "mildiou", "courant")

        for potager in (None, CTX.potager_id, AUTRE_POTAGER):
            lus = svc_bio.lire_bioagresseurs(db, "tomate", potager_id=potager)
            assert [b.nom_commun_fr for b in lus] == ["mildiou"]

    def test_us162_la_lecture_reunit_partage_et_local_et_les_distingue(self, db):
        """[CA3] Le jardinier voit les deux, et sait lequel est le sien."""
        _seed_culture(db, "chou")
        svc_bio.enregistrer_bioagresseur(db, "piéride", "insecte")
        svc_bio.rattacher(db, "chou", "piéride", "courant")
        svc_bio.enregistrer_bioagresseur(db, "altise locale", "insecte", potager_id=CTX.potager_id)
        svc_bio.rattacher(db, "chou", "altise locale", "rare", potager_id=CTX.potager_id)

        par_nom = {
            b.nom_commun_fr: b
            for b in svc_bio.lire_bioagresseurs(db, "chou", potager_id=CTX.potager_id)
        }

        assert par_nom["piéride"].local is False
        assert par_nom["altise locale"].local is True

    def test_us162_une_saisie_locale_n_est_jamais_promue_au_partage(self, db):
        """[CA3] Ni à la saisie, ni à la correction : la promotion est une
        décision humaine, pas un effet de bord."""
        svc_bio.enregistrer_bioagresseur(db, "altise", "insecte", potager_id=CTX.potager_id)
        svc_bio.enregistrer_bioagresseur(db, "altise", "carence", potager_id=CTX.potager_id)

        lignes = db.query(Bioagresseur).all()
        assert len(lignes) == 1
        assert lignes[0].potager_id == CTX.potager_id

    def test_us162_un_import_n_ecrit_jamais_dans_le_perimetre_d_un_potager(self, db):
        """[CA3, réciproque] La connaissance importée est partagée par définition."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

        assert db.query(Bioagresseur).one().potager_id is None
        assert db.query(CultureBioagresseur).one().potager_id is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Source, licence et attribution par enregistrement
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Tracabilite:
    def test_us162_toute_saisie_porte_une_origine(self, db):
        """[CA4] Aucune identité ni aucune arête anonyme, même saisie au bot."""
        _seed_culture(db, "tomate")
        bio, _ = svc_bio.enregistrer_bioagresseur(db, "mildiou", "champignon")
        arete, _ = svc_bio.rattacher(db, "tomate", "mildiou", "courant")

        saisie = svc_sources.get_source(db, svc_sources.SOURCE_SAISIE_MANUELLE)
        assert bio.source_id == saisie.id
        assert arete.source_id == saisie.id

    def test_us162_l_attribution_accompagne_la_restitution(self, db):
        """[CA4] L'obligation est par enregistrement, pas ligne de README : la
        mention est restituée avec la donnée."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

        lu = svc_bio.lire_bioagresseurs(db, "tomate")[0]

        assert lu.source_code == svc_sources.SOURCE_EPHY_ANSES
        assert "ANSES" in lu.attribution

    def test_us162_les_deux_tables_sont_rattachees_au_registre(self, db):
        """[CA4] `donnees_derivees` doit pouvoir répondre « que faut-il retirer ? »
        six mois plus tard — donc les deux tables sont dans TABLES_RATTACHEES."""
        tables = {t for t, _, _ in svc_sources.TABLES_RATTACHEES}

        assert {"bioagresseur", "culture_bioagresseur"} <= tables

    def test_us162_donnees_derivees_liste_les_bioagresseurs_importes(self, db):
        """[CA4] Le retrait d'une source est une requête, pas une fouille de code."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

        derivees = svc_sources.donnees_derivees(db, svc_sources.SOURCE_EPHY_ANSES)
        tables = {ligne["table"] for ligne in derivees}

        assert {"bioagresseur", "culture_bioagresseur"} <= tables


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Import hors ligne, idempotent, rejouable
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5ImportIdempotent:
    def test_us162_import_rejoue_sans_doublon(self, db):
        """[Gherkin: Import rejoué] Aucun doublon n'est créé, les nouvelles
        entrées sont ajoutées."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "chou")
        premier = _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        )
        svc_import.importer(db, premier)

        # Source « mise à jour » : la même ligne, plus une nouvelle.
        second = _manifeste_ephy(
            bioagresseurs=[MILDIOU, {"nom_commun_fr": "piéride", "categorie": "insecte"}],
            cultures_bioagresseurs=[
                {"culture": "tomate", "bioagresseur": "mildiou de la tomate",
                 "frequence": "courant"},
                {"culture": "chou", "bioagresseur": "piéride", "frequence": "courant"},
            ],
        )
        resultat = svc_import.importer(db, second)

        assert db.query(Bioagresseur).count() == 2
        assert db.query(CultureBioagresseur).count() == 2
        assert resultat.bioagresseurs_crees == ["piéride"]
        assert resultat.rattachements_crees == ["chou × piéride"]

    def test_us162_rejeu_met_a_jour_sans_dupliquer(self, db):
        """[CA5] Rejouer une valeur MODIFIÉE écrase la donnée de l'import lui-même
        — c'est le sens d'un rejeu hebdomadaire."""
        _seed_culture(db, "tomate")
        arete = {"culture": "tomate", "bioagresseur": "mildiou de la tomate",
                 "frequence": "occasionnel"}
        svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU], cultures_bioagresseurs=[arete]
        ))

        arete_corrigee = dict(arete, frequence="courant", periode_risque="juin-septembre")
        resultat = svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU], cultures_bioagresseurs=[arete_corrigee]
        ))

        ligne = db.query(CultureBioagresseur).one()
        assert ligne.frequence == "courant"
        assert ligne.periode_risque == "juin-septembre"
        assert resultat.rattachements_ecrits == ["tomate × mildiou de la tomate"]

    def test_us162_une_saisie_du_jardinier_survit_a_un_rejeu_d_import(self, db):
        """[CA5] Un référentiel importé décrit une moyenne ; le jardinier décrit
        son terrain. Quand les deux divergent, c'est le terrain qui a raison."""
        _seed_culture(db, "tomate")
        svc_bio.enregistrer_bioagresseur(db, "mildiou de la tomate", "champignon")
        svc_bio.rattacher(db, "tomate", "mildiou de la tomate", "rare")

        resultat = svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

        assert db.query(CultureBioagresseur).one().frequence == "rare"
        assert resultat.rattachements_preserves == ["tomate × mildiou de la tomate"]
        assert resultat.bioagresseurs_preserves == ["mildiou de la tomate"]

    def test_us162_dry_run_n_ecrit_rien(self, db):
        """[CA5] Simuler, c'est compter ce qui SERAIT fait."""
        _seed_culture(db, "tomate")
        resultat = svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ), dry_run=True)

        assert resultat.dry_run is True
        assert db.query(Bioagresseur).count() == 0
        assert db.query(CultureBioagresseur).count() == 0

    def test_us162_import_hors_ligne(self, db, monkeypatch):
        """[CA5] Aucune API externe n'est appelée : ni pour la latence, ni pour la
        disponibilité, ni pour le réseau."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à l'import de bioagresseurs (CA5)")

        _seed_culture(db, "tomate")
        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

    def test_us162_identites_importees_avant_les_aretes(self, db):
        """[CA5] Un manifeste complet s'importe en UN passage : une arête dont le
        bioagresseur est déclaré dans le même fichier ne doit pas être ignorée."""
        _seed_culture(db, "tomate")
        resultat = svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

        assert resultat.rattachements_ignores == []
        assert resultat.rattachements_crees == ["tomate × mildiou de la tomate"]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Le socle de licences est fermé
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6SocleFerme:
    def test_us162_source_cc_by_sa_refusee_aucun_bioagresseur_cree(self, db):
        """[Gherkin: Source hors socle refusée] Il est refusé, et AUCUN
        bioagresseur n'est créé."""
        _seed_culture(db, "tomate")
        manifeste = {
            "source": {
                "code": "ephytia_like", "libelle": "Source contaminante",
                "licence": "CC-BY-SA-4.0", "attribution": "…",
            },
            "bioagresseurs": [MILDIOU],
            "cultures_bioagresseurs": [{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        }

        with pytest.raises(svc_sources.LicenceHorsSocleError):
            svc_import.importer(db, manifeste)

        assert db.query(Bioagresseur).count() == 0
        assert db.query(CultureBioagresseur).count() == 0
        # Le refus a lieu AVANT toute écriture : pas même la ligne de registre.
        assert svc_sources.get_source(db, "ephytia_like") is None

    def test_us162_licence_non_etablie_refusee_comme_hors_socle(self, db):
        """[CA6] « Sans dérogation ni "en attendant" » : une licence absente est
        traitée comme une licence hors socle."""
        manifeste = {
            "source": {"code": "inconnue", "libelle": "Sans licence"},
            "bioagresseurs": [MILDIOU],
        }

        with pytest.raises(svc_sources.LicenceHorsSocleError):
            svc_import.importer(db, manifeste)

        assert db.query(Bioagresseur).count() == 0

    def test_us162_ephy_est_bien_une_source_du_socle(self, db):
        """[CA6] E-Phy / ANSES sous Licence Ouverte — la source tranchée de l'US."""
        ephy = svc_sources.get_source(db, svc_sources.SOURCE_EPHY_ANSES)

        assert ephy.licence == svc_sources.LICENCE_LICENCE_OUVERTE
        assert ephy.licence in svc_sources.LICENCES_IMPORTABLES


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Les conditions de data.eppo.int, lues et consignées (préalable bloquant)
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7ConditionsEppo:
    CONSIGNATION = Path("data/referentiel/eppo/SOURCE.md")

    def test_us162_la_consignation_existe_et_nomme_la_licence(self):
        """[CA7] Le préalable bloquant a un livrable : une fiche datée qui nomme
        la licence exacte et son verdict."""
        assert self.CONSIGNATION.exists(), (
            "CA7 est un préalable bloquant : sans consignation lue et datée des "
            "conditions de data.eppo.int, l'US n'est pas livrable."
        )
        texte = self.CONSIGNATION.read_text(encoding="utf-8")

        assert "EPPO Codes Open Data Licence" in texte
        assert "data.eppo.int" in texte

    def test_us162_la_consignation_porte_les_deux_obligations(self):
        """[CA7] Attribution ET date du dernier téléchargement — c'est ce couple
        qui distingue cette licence des autres du socle."""
        texte = self.CONSIGNATION.read_text(encoding="utf-8")

        assert "dernier téléchargement" in texte
        assert "logo" in texte  # l'interdiction de reproduire le logo EPPO

    def test_us162_la_source_eppo_est_au_registre_avec_sa_licence(self, db):
        """[CA7] La lecture des conditions a une conséquence en base, pas
        seulement dans un document."""
        eppo = svc_sources.get_source(db, svc_sources.SOURCE_EPPO)

        assert eppo is not None
        assert eppo.licence == svc_sources.LICENCE_EPPO
        assert "www.eppo.int" in eppo.attribution

    def test_us162_l_attribution_eppo_porte_la_date_du_dernier_import(self, db):
        """[CA7] La licence exige la date de dernier téléchargement. Elle est
        recomposée depuis `date_dernier_import` — une date figée mentirait au
        premier rejeu."""
        assert "téléchargement" not in svc_sources.attribution_affichee(
            db, svc_sources.SOURCE_EPPO
        )

        svc_sources.marquer_import(db, svc_sources.SOURCE_EPPO)

        assert "dernier téléchargement" in svc_sources.attribution_affichee(
            db, svc_sources.SOURCE_EPPO
        )

    def test_us162_un_code_eppo_peut_etre_saisi_a_la_main(self, db):
        """[CA7, repli] Que les conditions autorisent l'import ou non, la saisie
        manuelle sur le périmètre reste possible — le repli existe."""
        bio, _ = svc_bio.enregistrer_bioagresseur(
            db, "mildiou", "champignon", code_eppo="PHYTIN",
            potager_id=CTX.potager_id,
        )

        assert bio.code_eppo == "PHYTIN"


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Le taux d'appariement est mesuré et publié
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8TauxAppariement:
    def _importer(self, db, libelles):
        return svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[{"nom_commun_fr": "mildiou", "categorie": "champignon"}],
            cultures_bioagresseurs=[
                {"culture": libelle, "bioagresseur": "mildiou", "frequence": "courant"}
                for libelle in libelles
            ],
        ))

    def test_us162_taux_mesure_sur_les_libelles_distincts(self, db):
        """[CA8] La mesure porte sur les libellés de la source, appariés ou non."""
        _seed_culture(db, "tomate")
        _seed_culture(db, "chou")

        resultat = self._importer(db, ["tomate", "chou", "quinoa", "amarante"])

        assert len(resultat.appariement_libelles) == 4
        assert set(resultat.appariement_exacts) == {"tomate", "chou"}
        assert set(resultat.appariement_non_apparies) == {"quinoa", "amarante"}
        assert resultat.taux_appariement == pytest.approx(0.5)

    def test_us162_verdict_sous_le_seuil(self, db):
        """[CA8] Sous ~70 %, l'import automatique ne vaut plus la saisie directe —
        et la décision se prend sur la mesure, pas sur l'intention."""
        _seed_culture(db, "tomate")

        resultat = self._importer(db, ["tomate", "quinoa", "amarante"])

        assert resultat.appariement_suffisant is False
        assert "SOUS LE SEUIL" in svc_import.formater_resultat(resultat)

    def test_us162_verdict_au_dessus_du_seuil(self, db):
        """[CA8] Au-dessus, l'import automatique garde son intérêt."""
        for nom in ("tomate", "chou", "carotte"):
            _seed_culture(db, nom)

        resultat = self._importer(db, ["tomate", "chou", "carotte", "quinoa"])

        assert resultat.taux_appariement == pytest.approx(0.75)
        assert resultat.appariement_suffisant is True
        assert "SOUS LE SEUIL" not in svc_import.formater_resultat(resultat)

    def test_us162_aucun_rattachement_ne_se_mesure_pas_zero(self, db):
        """[CA8] Ne rien mesurer et mesurer zéro sont deux choses différentes :
        un manifeste sans rattachement ne doit pas déclencher le verdict d'échec."""
        resultat = svc_import.importer(db, _manifeste_ephy(bioagresseurs=[MILDIOU]))

        assert resultat.taux_appariement is None
        assert resultat.appariement_suffisant is None
        assert "Non mesurable" in svc_import.formater_resultat(resultat)

    def test_us162_le_rapport_est_publie_par_l_import(self, db):
        """[CA8] « Mesuré ET PUBLIÉ » : le compte rendu porte le chiffre et le seuil."""
        _seed_culture(db, "tomate")

        rapport = svc_import.formater_resultat(self._importer(db, ["tomate", "quinoa"]))

        assert "Taux d'appariement" in rapport
        assert "50%" in rapport


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Un rapprochement vernaculaire seul n'est jamais appliqué sans revue
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9RevueHumaine:
    def _importer(self, db, entree):
        return svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[{"nom_commun_fr": "limace", "categorie": "insecte"}],
            cultures_bioagresseurs=[dict(
                {"bioagresseur": "limace", "frequence": "courant"}, **entree
            )],
        ))

    def test_us162_correspondance_manuelle_non_appliquee_sans_revue(self, db):
        """[CA9] `laitue` / `salade` : ni la distance d'édition ni l'inclusion ne
        les rapprochent — ce sont des synonymes. La correspondance se DÉCLARE
        (`culture_en_base`), et reste un rapprochement par nom vernaculaire :
        elle n'est pas appliquée sans revue humaine déclarée."""
        _seed_culture(db, "salade")

        resultat = self._importer(db, {"culture": "laitue", "culture_en_base": "salade"})

        assert db.query(CultureBioagresseur).count() == 0
        assert resultat.appariements_a_revoir == ["laitue × limace → salade"]
        assert resultat.rattachements_crees == []

    def test_us162_haricot_grimpant_est_aussi_un_rapprochement_approche(self, db):
        """[CA9] Le second cas cité par l'US : l'inclusion, que Levenshtein ne
        rapproche pas — et qui est un indice encore plus faible."""
        _seed_culture(db, "haricot")

        resultat = self._importer(db, {"culture": "haricot grimpant"})

        assert db.query(CultureBioagresseur).count() == 0
        assert resultat.appariements_a_revoir == ["haricot grimpant × limace → haricot"]

    def test_us162_revue_humaine_declaree_applique_le_rapprochement(self, db):
        """[CA9] Le drapeau est porté par le FICHIER versionné — donc relu en diff
        git — jamais par un seuil de similarité qui déciderait seul."""
        _seed_culture(db, "salade")

        resultat = self._importer(
            db, {"culture": "laitue", "culture_en_base": "salade", "revue_humaine": True}
        )

        assert resultat.rattachements_crees == ["laitue × limace"]
        assert resultat.appariements_a_revoir == []
        assert db.query(CultureBioagresseur).count() == 1

    def test_us162_un_appariement_exact_n_exige_aucune_revue(self, db):
        """[CA9] La revue vise le rapprochement vernaculaire, pas l'appariement
        exact — sans quoi tout import deviendrait manuel."""
        _seed_culture(db, "salade")

        resultat = self._importer(db, {"culture": "Salade"})

        assert resultat.rattachements_crees == ["Salade × limace"]
        assert resultat.appariements_a_revoir == []

    def test_us162_libelle_sans_aucun_rapprochement_est_ignore(self, db):
        """[CA9, CA7 d'US-161] Ni écrit, ni « à revoir » : simplement ignoré, et
        aucune culture n'est créée."""
        _seed_culture(db, "salade")

        resultat = self._importer(db, {"culture": "quinoa"})

        assert resultat.rattachements_ignores == ["quinoa × limace"]
        assert resultat.appariements_a_revoir == []
        assert db.query(CultureConfig).count() == 1

    def test_us162_le_rapport_dit_quoi_faire_des_lignes_a_revoir(self, db):
        """[CA9] Un compte rendu qui signale sans dire comment débloquer laisse le
        relecteur devant un mur."""
        _seed_culture(db, "salade")

        rapport = svc_import.formater_resultat(
            self._importer(db, {"culture": "laitue", "culture_en_base": "salade"})
        )

        assert "À REVOIR (CA9)" in rapport
        assert "revue_humaine" in rapport


# ═════════════════════════════════════════════════════════════════════════════
# CA10 / CA11 — Ce que cette US NE dit pas
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10AucunePrescription:
    @pytest.mark.parametrize("modele", [Bioagresseur, CultureBioagresseur])
    def test_us162_aucune_colonne_de_prescription(self, modele):
        """[Gherkin: Aucune prescription de traitement] La garantie n'est pas une
        consigne de rédaction : il n'existe aucune colonne où stocker un dosage,
        un produit ou une conduite à tenir — donc rien à restituer."""
        colonnes = {c.name.lower() for c in modele.__table__.columns}
        interdits = ("dose", "dosage", "produit", "traitement", "posologie",
                     "phytosanitaire", "remede")

        assert not [c for c in colonnes if any(mot in c for mot in interdits)]

    def test_us162_la_restitution_ne_porte_aucune_prescription(self, db):
        """[Gherkin] L'objet restitué n'expose que l'identité, la fréquence, la
        période — et la source officielle."""
        _seed_culture(db, "tomate")
        svc_import.importer(db, _manifeste_ephy(
            bioagresseurs=[MILDIOU],
            cultures_bioagresseurs=[{
                "culture": "tomate", "bioagresseur": "mildiou de la tomate",
                "frequence": "courant",
            }],
        ))

        lu = svc_bio.lire_bioagresseurs(db, "tomate")[0]

        assert set(vars(lu)) == {
            "nom_commun_fr", "nom_scientifique", "categorie", "code_eppo",
            "frequence", "periode_risque", "local", "source_code", "attribution",
        }
        # [Gherkin] « la source officielle est citée »
        assert "ANSES" in lu.attribution


class TestCA11AucunNarratif:
    @pytest.mark.parametrize("modele", [Bioagresseur, CultureBioagresseur])
    def test_us162_aucune_colonne_de_texte_narratif(self, modele):
        """[CA11] Descriptions et symptômes relèvent d'US-140/US-098 et se
        RATTACHENT à ces identités — cette US ne les duplique pas."""
        colonnes = {c.name.lower() for c in modele.__table__.columns}
        interdits = ("description", "symptome", "symptomes", "biologie",
                     "conduite", "narratif", "texte")

        assert not [c for c in colonnes if any(mot in c for mot in interdits)]


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — L'absence de lien n'est pas une absence de risque
# ═════════════════════════════════════════════════════════════════════════════

class TestCA12AbsenceDeLien:
    def test_us162_culture_sans_bioagresseur_rattache(self, db):
        """[Gherkin: Culture sans bioagresseur rattaché] L'application répond
        qu'elle n'a pas d'information — elle n'en conclut pas que la culture
        n'est pas exposée."""
        _seed_culture(db, "carotte")

        assert svc_bio.lire_bioagresseurs(db, "carotte") == []
        assert "pas encore été renseignée" in svc_bio.MESSAGE_AUCUNE_INFO
        assert "n'est pas exposée" in svc_bio.MESSAGE_AUCUNE_INFO

    def test_us162_culture_inconnue_et_culture_sans_lien_sont_distinguees(self, db):
        """[CA12] Ne rien savoir d'une culture connue et ne pas connaître la
        culture sont deux situations différentes — les confondre trompe."""
        _seed_culture(db, "carotte")

        assert svc_bio.lire_bioagresseurs(db, "carotte") == []
        with pytest.raises(svc_bio.CultureInconnueError):
            svc_bio.lire_bioagresseurs(db, "salsifis")

    def test_us162_bioagresseur_sans_relation_reste_en_base(self, db):
        """[CA12] Il reste en base et se lit comme non rattaché — ni supprimé, ni
        compté comme couverture."""
        svc_bio.enregistrer_bioagresseur(db, "taupin", "insecte")

        assert db.query(Bioagresseur).count() == 1
        assert [b.nom_commun_fr for b in svc_bio.lister_non_rattaches(db)] == ["taupin"]

    def test_us162_un_bioagresseur_rattache_ne_sort_plus_des_orphelins(self, db):
        """[CA12] La liste de travail se vide à mesure que la revue avance."""
        _seed_culture(db, "carotte")
        svc_bio.enregistrer_bioagresseur(db, "mouche de la carotte", "insecte")
        svc_bio.rattacher(db, "carotte", "mouche de la carotte", "courant")

        assert svc_bio.lister_non_rattaches(db) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA2 / CA13 — Zéro jeton, vérifié activement
# ═════════════════════════════════════════════════════════════════════════════

class TestZeroJeton:
    def test_us162_restitution_sans_appel_reseau(self, db, monkeypatch):
        """[Gherkin: Ce qui attaque une culture, sans jeton] Toute tentative de
        sortie réseau fait échouer le test."""
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la lecture (US-162/CA2)")

        _seed_culture(db, "poireau")
        svc_bio.enregistrer_bioagresseur(db, "teigne du poireau", "insecte")
        svc_bio.rattacher(db, "poireau", "teigne du poireau", "courant")

        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        assert len(svc_bio.lire_bioagresseurs(db, "poireau")) == 1

    def test_us162_restitution_n_appelle_pas_la_passerelle_llm(self, db):
        """[CA13] « Sans aucun appel au modèle » — ni chat, ni transcription."""
        _seed_culture(db, "poireau")
        svc_bio.enregistrer_bioagresseur(db, "teigne du poireau", "insecte")
        svc_bio.rattacher(db, "poireau", "teigne du poireau", "courant")

        with patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            svc_bio.lire_bioagresseurs(db, "poireau")

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Le gabarit livré et le manifeste versionné
# ═════════════════════════════════════════════════════════════════════════════

class TestGabaritLivre:
    GABARIT = Path("data/referentiel/bioagresseurs_redaction_interne.json")

    def test_us162_le_gabarit_est_livre_vide_et_inoffensif(self, db):
        """[CA11, comme le gabarit d'US-161] Livré vide : l'importer en l'état
        n'écrit rien. Aucune valeur n'est produite par un modèle de langage."""
        manifeste = json.loads(self.GABARIT.read_text(encoding="utf-8"))

        assert manifeste["bioagresseurs"] == []
        assert manifeste["cultures_bioagresseurs"] == []

        resultat = svc_import.importer(db, manifeste)

        assert resultat.total_ecritures == 0
        assert db.query(Bioagresseur).count() == 0

    def test_us162_le_gabarit_declare_une_origine_interne(self, db):
        """Une origine NON importée du socle : elle échappe au contrôle de licence
        parce qu'elle ne porte aucun contenu tiers (US-161)."""
        manifeste = json.loads(self.GABARIT.read_text(encoding="utf-8"))

        assert manifeste["source"]["code"] == svc_sources.SOURCE_REDACTION_INTERNE


# ═════════════════════════════════════════════════════════════════════════════
# Couche bot — /bioagresseur (dispatch, formatage, erreurs)
# ═════════════════════════════════════════════════════════════════════════════
# Le service est mocké ici : ce qui est vérifié est le CÂBLAGE de la commande
# (parsing de ctx.args, appel du bon service, formatage) — la logique métier est
# couverte ci-dessus. Même stratégie que TestCommandeBotFiche d'US-164.

class TestCommandeBot:
    def _update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    def _ctx(self, *args):
        ctx = MagicMock()
        ctx.args = list(args)
        return ctx

    def _texte(self, update):
        return update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_us162_bot_lister_restitue_la_liste_ordonnee(self, db):
        """[CA2] Le bot affiche ce que le service a déjà ordonné."""
        import bot

        lus = [
            svc_bio.BioagresseurLu(
                nom_commun_fr="teigne du poireau", nom_scientifique="Acrolepiopsis assectella",
                categorie="insecte", code_eppo=None, frequence="courant",
                periode_risque="mai-septembre", local=False,
                source_code="ephy_anses", attribution="ANSES — catalogue E-Phy",
            ),
        ]
        update, ctx = self._update(), self._ctx("lister", "poireau")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot.svc_bioagresseurs, "lire_bioagresseurs", return_value=lus):
            await bot.cmd_bioagresseur(update, ctx)

        texte = self._texte(update)
        assert "teigne du poireau" in texte
        assert "courant" in texte
        assert "ANSES" in texte

    @pytest.mark.asyncio
    async def test_us162_bot_culture_sans_lien_dit_l_ignorance(self, db):
        """[CA12] Le bot ne conclut jamais à l'absence de risque."""
        import bot

        update, ctx = self._update(), self._ctx("lister", "carotte")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot.svc_bioagresseurs, "lire_bioagresseurs", return_value=[]):
            await bot.cmd_bioagresseur(update, ctx)

        assert "n'est pas exposée" in self._texte(update)

    @pytest.mark.asyncio
    async def test_us162_bot_culture_inconnue(self, db):
        """[CA12] Distingué de « aucune information »."""
        import bot

        update, ctx = self._update(), self._ctx("lister", "salsifis")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot.svc_bioagresseurs, "lire_bioagresseurs",
                          side_effect=svc_bio.CultureInconnueError("salsifis")):
            await bot.cmd_bioagresseur(update, ctx)

        assert "Culture inconnue" in self._texte(update)

    @pytest.mark.asyncio
    async def test_us162_bot_declarer_est_toujours_local(self, db):
        """[CA3] Une saisie au bot est locale au potager courant, jamais partagée."""
        import bot

        update, ctx = self._update(), self._ctx("declarer", "insecte", "teigne", "du", "poireau")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot.svc_bioagresseurs, "enregistrer_bioagresseur",
                          return_value=(MagicMock(), True)) as mock_enr, \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_bioagresseur(update, ctx)

        assert mock_enr.call_args.kwargs["potager_id"] == CTX.potager_id
        assert mock_enr.call_args.kwargs["nom_commun_fr"] == "teigne du poireau"

    @pytest.mark.asyncio
    async def test_us162_bot_rattacher_guide_vers_la_declaration(self, db):
        """Un bioagresseur inconnu n'est pas fabriqué : le bot dit quoi faire."""
        import bot

        update, ctx = self._update(), self._ctx("rattacher", "poireau", "courant", "teigne")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot.svc_bioagresseurs, "rattacher",
                          side_effect=svc_bio.BioagresseurInconnuError("teigne")), \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_bioagresseur(update, ctx)

        texte = self._texte(update)
        assert "Bioagresseur inconnu" in texte
        assert "declarer" in texte

    @pytest.mark.asyncio
    async def test_us162_bot_sans_argument_affiche_l_usage(self, db):
        import bot

        update, ctx = self._update(), self._ctx()

        await bot.cmd_bioagresseur(update, ctx)

        assert "/bioagresseur lister" in self._texte(update)

    def test_us162_la_commande_est_enregistree_et_au_menu(self):
        """[US-171] Le menu natif se DÉRIVE des handlers : une commande ajoutée y
        entre au redémarrage — encore faut-il qu'elle porte sa description."""
        from app.services import menu_commandes

        assert "bioagresseur" in menu_commandes.DESCRIPTIONS
        assert "bioagresseur" in menu_commandes.ORDRE_METIER
        assert len(menu_commandes.DESCRIPTIONS["bioagresseur"]) <= 60
