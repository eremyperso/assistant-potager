"""
tests/test_us161_adaptateur_wind_river.py
[US-161] Adaptation du jeu de données Wind River Greens (CC BY 4.0)

Trois choses à garantir, dans l'ordre de gravité :

1. **La règle d'agrégation ne produit rien qu'elle ne puisse défendre.** Un
   attribut n'est retenu que sur consensus mesuré ; en dessous, il est écarté et
   reste « non renseigné ». C'est le CA10 appliqué à une source : ne rien
   inventer, y compris par moyenne implicite.
2. **L'élargissement de licence n'ouvre que CC BY.** CC-BY-SA reste refusé, et
   une licence non établie aussi. Un élargissement qui déborde est une
   régression de conformité, pas une commodité.
3. **Ce qui est écarté le reste.** Rusticité, profondeur et calendrier ne
   doivent jamais réapparaître par une évolution distraite de l'adaptateur.
"""
import json

import pytest

from app.services import adaptateur_wind_river as svc_adaptateur
from app.services import attributs_culture as svc_attributs
from app.services import import_referentiel as svc_import
from app.services import referentiel_sources as svc_sources
from app.services.referentiel_sources import LicenceHorsSocleError
from database.models import CultureConfig

MANIFESTE_PROJET = "data/referentiel/wind_river_attributs.json"
ASSOCIATIONS_PROJET = "data/referentiel/wind_river_associations.json"
CSV_PROJET = "data/referentiel/wind_river_greens/varieties.csv"


@pytest.fixture
def db(test_db):
    return test_db


def _cultivar(nom, categorie, soleil="Full sun (6+ hours)", eau="High — consistent moisture needed", **extra):
    ligne = {
        "name": nom, "slug": nom.lower().replace(" ", "-"), "category": categorie,
        "scientific_name": "", "sun_requirement": soleil, "water_requirement": eau,
    }
    ligne.update(extra)
    return ligne


def _seed_culture(db, nom):
    config = CultureConfig(nom=nom, type_organe_recolte="reproducteur")
    db.add(config)
    db.commit()
    return config


# ═════════════════════════════════════════════════════════════════════════════
# La licence — l'élargissement, et ses limites
# ═════════════════════════════════════════════════════════════════════════════

class TestLicenceCCBY:
    def test_us161_cc_by_est_importable(self):
        """CC BY n'a aucune clause virale : partage, adaptation et usage
        commercial libres, attribution seule contrainte."""
        assert svc_sources.verifier_licence_importable("CC BY 4.0") == "CC BY 4.0"

    def test_us161_cc_by_sa_reste_refuse(self):
        """L'arbitrage §6.3 n'a pas changé : le partage à l'identique
        contaminerait un corpus qui doit rester propriétaire."""
        with pytest.raises(LicenceHorsSocleError):
            svc_sources.verifier_licence_importable("CC-BY-SA-4.0")

    def test_us161_une_licence_non_etablie_reste_refusee(self):
        """« Non établie » et « établie hors socle » restent traitées à
        l'identique — un fichier sans en-tête de licence ne passe pas."""
        for licence in (None, "", "   ", "inconnue"):
            with pytest.raises(LicenceHorsSocleError):
                svc_sources.verifier_licence_importable(licence)

    def test_us161_la_source_est_au_registre_avec_son_attribution_exacte(self, db):
        """[US-166 / CA1] CC BY rend la mention obligatoire à l'affichage : elle
        doit être au registre au mot près, pas paraphrasée."""
        svc_sources.semer_sources_socle(db)

        source = svc_sources.get_source(db, svc_sources.SOURCE_WIND_RIVER)

        assert source.licence == "CC BY 4.0"
        assert source.attribution == (
            "Plant variety data from Wind River Greens Plant Database "
            "(https://plants.windrivergreens.com), CC BY 4.0"
        )
        assert source.importee is True
        assert source.partageable is True


# ═════════════════════════════════════════════════════════════════════════════
# La normalisation des valeurs sources
# ═════════════════════════════════════════════════════════════════════════════

class TestNormalisation:
    @pytest.mark.parametrize("brut,attendu", [
        ("Full sun (6+ hours)", "plein soleil"),
        ("Full sun", "plein soleil"),
        # Une plage est ramenée à sa borne haute — l'optimum, que le jardinier vise.
        ("Full sun to partial shade (4-6+ hours)", "plein soleil"),
        ("Partial shade (4-6 hours)", "mi-ombre"),
        ("Partial sun", "mi-ombre"),
        ("Full shade", "ombre"),
        ("", None),
        ("Grow lights recommended", None),
    ])
    def test_us161_exposition_normalisee(self, brut, attendu):
        assert svc_adaptateur.normaliser_exposition(brut) == attendu

    @pytest.mark.parametrize("brut,attendu", [
        ("High — consistent moisture needed", "élevé"),
        ("Moderate — regular watering", "moyen"),
        ("Low — drought tolerant once established", "faible"),
        ("Regular, consistent moisture", "moyen"),
        # Les quantités sont ramenées à une catégorie par les seuils.
        ("1 inch per week, consistent moisture", "moyen"),
        ("1-2 inches per week, consistent moisture", "élevé"),
        ("0.5 inch per week", "faible"),
        ("", None),
        ("Water when the mood strikes", None),
    ])
    def test_us161_besoin_eau_normalise(self, brut, attendu):
        assert svc_adaptateur.normaliser_besoin_eau(brut) == attendu

    def test_us161_toute_valeur_produite_franchit_le_vocabulaire_ferme(self):
        """[CA2] Ceinture et bretelles : ce que l'adaptateur produit doit être
        acceptable par la même validation que n'importe quelle saisie."""
        for _, valeur in svc_adaptateur._EXPOSITION_REGLES:
            assert svc_attributs.normaliser_valeur("exposition", valeur) == valeur
        for _, valeur in svc_adaptateur._EAU_REGLES:
            assert svc_attributs.normaliser_valeur("besoin_eau", valeur) == valeur


# ═════════════════════════════════════════════════════════════════════════════
# L'agrégation cultivar → culture : ne rien retenir qu'on ne puisse défendre
# ═════════════════════════════════════════════════════════════════════════════

class TestAgregation:
    def test_us161_consensus_net_retenu(self):
        """Dix cultivars d'accord : la valeur est retenue."""
        lignes = [_cultivar(f"Tomato {i}", "tomato") for i in range(10)]

        manifeste, _, resultat = svc_adaptateur.construire_manifeste(lignes)

        entree = next(e for e in manifeste["cultures_attributs"] if e["culture"] == "tomate")
        assert entree["exposition"] == "plein soleil"
        assert entree["besoin_eau"] == "élevé"

    def test_us161_absence_de_consensus_ecarte_l_attribut(self):
        """Sous le seuil, rien n'est retenu : ni la majorité relative, ni une
        moyenne. L'attribut reste « non renseigné » et se saisit à la main."""
        lignes = (
            [_cultivar(f"A{i}", "tomato", soleil="Full sun") for i in range(5)]
            + [_cultivar(f"B{i}", "tomato", soleil="Partial shade (4-6 hours)") for i in range(5)]
        )

        manifeste, _, resultat = svc_adaptateur.construire_manifeste(lignes)

        entrees = [e for e in manifeste["cultures_attributs"] if e["culture"] == "tomate"]
        assert not entrees or "exposition" not in entrees[0]
        assert any("tomate.exposition" in e and "consensus" in e for e in resultat.attributs_ecartes)

    def test_us161_base_trop_faible_ecarte_l_attribut(self):
        """Un cultivar unanime avec lui-même n'est pas un consensus."""
        lignes = [_cultivar("Ruby Red Chard", "leafy")]

        manifeste, _, resultat = svc_adaptateur.construire_manifeste(lignes)

        assert not [e for e in manifeste["cultures_attributs"] if e["culture"] == "blette"]
        assert any("blette.exposition" in e and "base trop faible" in e
                   for e in resultat.attributs_ecartes)

    def test_us161_le_motif_d_ecartement_est_explicite(self):
        """Un attribut écarté doit dire pourquoi : sans motif, on ne sait pas
        s'il faut le saisir à la main ou corriger l'appariement."""
        lignes = [_cultivar("Solo Chard", "leafy")]

        _, _, resultat = svc_adaptateur.construire_manifeste(lignes)

        assert all("—" in e for e in resultat.attributs_ecartes)


# ═════════════════════════════════════════════════════════════════════════════
# L'appariement — catégorie ET nom, car ni l'une ni l'autre ne suffit
# ═════════════════════════════════════════════════════════════════════════════

class TestAppariement:
    def test_us161_poivron_ne_capte_pas_les_piments(self):
        """Un piment n'a pas la conduite d'un poivron : la catégorie `pepper`
        seule les confondrait."""
        lignes = [
            _cultivar("Bell Pepper California Wonder", "pepper"),
            _cultivar("Jalapeno Hot Pepper", "pepper"),
            _cultivar("Habanero Chili", "pepper"),
        ]

        par_culture = svc_adaptateur.selectionner_cultivars(lignes)

        assert len(par_culture["poivron"]) == 1

    def test_us161_concombre_et_cornichon_sont_separes(self):
        """Ils partagent la catégorie `cucumber` — seuls les motifs les séparent."""
        lignes = [
            _cultivar("Marketmore 76", "cucumber"),
            _cultivar("Boston Pickling", "cucumber"),
        ]

        par_culture = svc_adaptateur.selectionner_cultivars(lignes)

        assert len(par_culture["concombre"]) == 1
        assert len(par_culture["cornichon"]) == 1

    def test_us161_une_ligne_hors_perimetre_est_ignoree(self):
        """1 972 cultivars amont, dix cultures ici : le reste ne doit jamais
        atterrir dans le manifeste (CA7)."""
        lignes = [_cultivar("Peace Rose", "rose"), _cultivar("Monstera", "houseplant")]

        par_culture = svc_adaptateur.selectionner_cultivars(lignes)

        assert all(not lignes_culture for lignes_culture in par_culture.values())

    def test_us161_le_manifeste_ne_depasse_jamais_le_perimetre(self):
        """[CA7] L'adaptateur ne peut pas produire ce que l'import refuserait."""
        manifeste = json.load(open(MANIFESTE_PROJET, encoding="utf-8"))

        for entree in manifeste["cultures_attributs"]:
            assert svc_attributs.dans_perimetre_initial(entree["culture"])


# ═════════════════════════════════════════════════════════════════════════════
# Les associations — extraites, jamais importées avant US-163
# ═════════════════════════════════════════════════════════════════════════════

class TestAssociations:
    def test_us161_les_associations_sont_extraites_avec_leur_nature(self):
        lignes = [_cultivar("Cherokee Purple", "tomato")]
        compagnons = [
            {"variety_slug": "cherokee-purple", "companion_name": "Basil",
             "relationship": "beneficial", "reason": "Repels aphids"},
            {"variety_slug": "cherokee-purple", "companion_name": "Fennel",
             "relationship": "harmful", "reason": "Inhibits growth"},
        ]

        _, associations, resultat = svc_adaptateur.construire_manifeste(lignes, compagnons)

        natures = {a["compagnon_source"]: a["nature"]
                   for a in associations["cultures_associations"]}
        assert natures == {"Basil": "favorable", "Fennel": "defavorable"}
        assert resultat.associations == 2

    def test_us161_une_paire_contradictoire_est_ecartee(self):
        """[§6.5] La source dit bénéfique ici, nuisible là : on ne tranche pas à
        sa place — c'est exactement ce que le niveau de preuve sert à éviter."""
        lignes = [_cultivar("A", "tomato"), _cultivar("B", "tomato")]
        compagnons = [
            {"variety_slug": "a", "companion_name": "Fennel",
             "relationship": "beneficial", "reason": "x"},
            {"variety_slug": "b", "companion_name": "Fennel",
             "relationship": "harmful", "reason": "y"},
        ]

        _, associations, resultat = svc_adaptateur.construire_manifeste(lignes, compagnons)

        assert associations["cultures_associations"] == []
        assert "tomate × Fennel" in resultat.associations_contradictoires

    def test_us163_le_manifeste_porte_les_associations_curees_pas_les_brutes(self):
        """[US-163] La curation (traduction, périmètre, doublons — voir
        tests/test_us163_adaptateur_wind_river_associations.py) rejoint
        désormais le manifeste principal : import unique, une seule commande.
        Le fichier séparé (`associations`, ici) reste l'extraction BRUTE, en
        anglais, non canonicalisée — jamais ce que le manifeste porte."""
        lignes = [_cultivar("Cherokee Purple", "tomato")]
        compagnons = [{"variety_slug": "cherokee-purple", "companion_name": "Basil",
                       "relationship": "beneficial", "reason": "x"}]

        manifeste, associations, _ = svc_adaptateur.construire_manifeste(lignes, compagnons)

        assert manifeste["cultures_associations"] == [
            {"culture": "tomate", "compagnon": "basilic", "nature": "favorable",
             "motif": svc_adaptateur.MOTIFS_FR[("tomate", "basilic")],
             "niveau_preuve": "traditionnel"}
        ]
        # Le fichier séparé reste brut : libellé anglais, motif anglais tel quel.
        assert associations["cultures_associations"] == [
            {"culture": "tomate", "compagnon_source": "Basil", "nature": "favorable",
             "motif_source": "x", "niveau_preuve": "traditionnel"}
        ]

    def test_us161_sans_compagnons_aucun_fichier_d_associations(self):
        """Pas de CSV de compagnons, pas de fichier : rien n'est produit à vide."""
        manifeste, associations, _ = svc_adaptateur.construire_manifeste(
            [_cultivar("Cherokee Purple", "tomato")]
        )

        assert associations is None
        assert "cultures_associations" not in manifeste

    def test_us161_le_fichier_d_associations_annonce_ce_qu_il_vaut(self):
        """Il doit dire qu'il est brut : un fichier de données qui ne signale pas
        ses défauts finira par être pris pour de la donnée validée. [US-163]
        Il pointe aussi vers la version curée, désormais ailleurs."""
        associations = json.load(open(ASSOCIATIONS_PROJET, encoding="utf-8"))
        avertissement = " ".join(associations["_lisez_moi"])

        assert associations["revise"] is False
        assert "BRUTE" in avertissement
        assert "n'est PAS un manifeste d'import" in avertissement
        assert "cultures_associations" in avertissement  # pointeur vers le bloc curé
        # Les quatre défauts mesurés le 01/09/2026 sont nommés, pas résumés.
        for defaut in ("doublonn", "contradiction", "AUTRE plante", "auto-association"):
            assert defaut in avertissement

    def test_us161_le_fichier_d_associations_n_est_pas_importable(self, db):
        """Garde-fou : passé par erreur à l'import, il ne déclare aucun bloc
        connu et n'écrit donc rien — plutôt qu'écrire à moitié."""
        _seed_culture(db, "tomate")

        resultat = svc_import.importer_fichier(db, ASSOCIATIONS_PROJET)

        assert resultat.attributs_ecrits == []
        assert resultat.total_ecritures == 0
        relue = db.query(CultureConfig).filter(CultureConfig.nom == "tomate").first()
        assert relue.exposition is None

    def test_us161_le_niveau_de_preuve_reste_traditionnel(self):
        """[§6.5] La source ne distingue pas l'établi du traditionnel : ne rien
        affirmer de plus qu'elle."""
        lignes = [_cultivar("Cherokee Purple", "tomato")]
        compagnons = [{"variety_slug": "cherokee-purple", "companion_name": "Basil",
                       "relationship": "beneficial", "reason": "x"}]

        _, associations, _ = svc_adaptateur.construire_manifeste(lignes, compagnons)

        assert all(a["niveau_preuve"] == "traditionnel"
                   for a in associations["cultures_associations"])


# ═════════════════════════════════════════════════════════════════════════════
# Ce qui est écarté doit le rester
# ═════════════════════════════════════════════════════════════════════════════

class TestFrontieres:
    def test_us161_aucune_rusticite_produite(self):
        """`usda_zone_min` décrit la pérennité, pas la culture : les tomates du
        jeu de données sont en « zones 10-11 ». En dériver un chiffre serait en
        dériver un faux (CA10)."""
        manifeste = json.load(open(MANIFESTE_PROJET, encoding="utf-8"))

        for entree in manifeste["cultures_attributs"]:
            assert "rusticite_min_c" not in entree

    def test_us161_aucune_profondeur_produite(self):
        """Elle est absente du jeu de données — aucune colonne."""
        manifeste = json.load(open(MANIFESTE_PROJET, encoding="utf-8"))

        for entree in manifeste["cultures_attributs"]:
            assert "profondeur_semis_cm" not in entree

    def test_us161_aucun_attribut_de_calendrier(self):
        """[CA8] Le calendrier amont est en zones USDA nord-américaines : il ne
        peut pas se substituer au référentiel calendrier d'US-068."""
        manifeste = json.load(open(MANIFESTE_PROJET, encoding="utf-8"))
        interdits = ("date", "mois", "semis_debut", "fenetre", "duree", "calendrier", "zone")

        for entree in manifeste["cultures_attributs"]:
            for cle in entree:
                assert not any(mot in cle.lower() for mot in interdits)

    def test_us161_l_adaptateur_ne_lit_aucune_colonne_ecartee(self):
        """Le garde-fou structurel : seules deux colonnes sources sont lues.
        En ajouter une doit être un geste délibéré, visible dans ce test."""
        assert set(svc_adaptateur.NORMALISEURS) == {"exposition", "besoin_eau"}
        colonnes = {colonne for colonne, _ in svc_adaptateur.NORMALISEURS.values()}
        assert colonnes == {"sun_requirement", "water_requirement"}


# ═════════════════════════════════════════════════════════════════════════════
# Le manifeste projet, de bout en bout
# ═════════════════════════════════════════════════════════════════════════════

class TestManifesteProjet:
    def test_us161_le_manifeste_projet_s_importe(self, db):
        """De bout en bout, sur le vrai fichier : CSV → manifeste → base."""
        for nom in ("tomate", "carotte", "courgette"):
            _seed_culture(db, nom)

        resultat = svc_import.importer_fichier(db, MANIFESTE_PROJET)

        carotte = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert carotte.exposition == "plein soleil"
        assert carotte.besoin_eau == "moyen"
        source = svc_sources.get_source(db, svc_sources.SOURCE_WIND_RIVER)
        assert carotte.exposition_source_id == source.id
        assert resultat.attributs_refuses == []

    def test_us161_le_manifeste_projet_ne_cree_aucune_culture(self, db):
        """[CA7] Neuf cultures dans le manifeste, une seule en base : les huit
        autres sont ignorées, jamais créées."""
        _seed_culture(db, "tomate")

        resultat = svc_import.importer_fichier(db, MANIFESTE_PROJET)

        assert db.query(CultureConfig).count() == 1
        assert len(resultat.cultures_ignorees) >= 1

    def test_us161_une_correction_au_bot_prime_sur_wind_river(self, db):
        """[CA6] Le terrain gagne : la moyenne nord-américaine ne réécrit pas ce
        que le jardinier a corrigé."""
        _seed_culture(db, "carotte")
        svc_attributs.corriger_attribut(db, "carotte", "besoin_eau", "faible")

        resultat = svc_import.importer_fichier(db, MANIFESTE_PROJET)

        carotte = db.query(CultureConfig).filter(CultureConfig.nom == "carotte").first()
        assert carotte.besoin_eau == "faible"
        assert "carotte.besoin_eau" in resultat.attributs_preserves

    def test_us161_le_manifeste_projet_ne_porte_que_des_blocs_importables(self):
        """Sur le vrai fichier : uniquement des blocs que l'import sait lire —
        attributs de conduite (US-161) et associations curées (US-163)."""
        manifeste = json.load(open(MANIFESTE_PROJET, encoding="utf-8"))

        assert "cultures_attributs" in manifeste
        assert "cultures_associations" in manifeste
        assert manifeste["cultures_associations"]  # non vide sur le vrai fichier
        # Le motif est en français, jamais la phrase anglaise de la source.
        assert all(
            entree["compagnon"] and entree["motif"]
            for entree in manifeste["cultures_associations"]
        )

    def test_us161_le_manifeste_projet_porte_l_attribution_cc_by(self):
        """CC BY oblige à créditer : le manifeste doit être auto-portant, donc
        vérifiable sans la base."""
        manifeste = json.load(open(MANIFESTE_PROJET, encoding="utf-8"))

        assert manifeste["source"]["licence"] == "CC BY 4.0"
        assert "windrivergreens.com" in manifeste["source"]["attribution"]
        assert manifeste["extrait_le"] == "v1.0.0"

    def test_us161_le_csv_versionne_est_l_extrait_du_perimetre(self):
        """L'extrait versionné et l'appariement du code ne peuvent pas diverger :
        toute ligne du CSV doit correspondre à une culture du périmètre."""
        import csv as _csv

        with open(CSV_PROJET, encoding="utf-8", newline="") as flux:
            lignes = list(_csv.DictReader(flux))
        par_culture = svc_adaptateur.selectionner_cultivars(lignes)

        assert sum(len(v) for v in par_culture.values()) == len(lignes)
