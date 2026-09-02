"""
tests/test_us163_adaptateur_wind_river_associations.py
[US-163] Curation des associations Wind River Greens — traduction, périmètre, doublons

Couvre `app.services.adaptateur_wind_river.curer_associations`, qui transforme
l'extraction brute d'US-161 (`construire_associations`, testée dans
`tests/test_us161_adaptateur_wind_river.py`) en bloc `cultures_associations`
importable. Aucune base de données ici : `curer_associations` ne touche ni la
base ni le réseau, elle transforme une liste de dicts en une autre.

Deux familles de tests :
  - contre les 217 arêtes RÉELLES de `data/referentiel/wind_river_associations.json`,
    en garde-fou de régression (une future mise à jour des CSV source qui
    introduirait un libellé non couvert par CIBLE_COMPAGNONS ou MOTIFS_FR doit
    faire échouer ces tests, pas produire un import silencieusement incomplet) ;
  - contre des arêtes synthétiques, pour isoler chaque règle de curation.
"""
import json
from pathlib import Path

import pytest

from app.services import adaptateur_wind_river as svc_adaptateur

FICHIER_BRUT = (
    Path(__file__).resolve().parent.parent
    / "data" / "referentiel" / "wind_river_associations.json"
)


def _arete(culture, compagnon, nature, motif="peu importe"):
    return {
        "culture": culture, "compagnon_source": compagnon,
        "nature": nature, "motif_source": motif, "niveau_preuve": "traditionnel",
    }


# ═════════════════════════════════════════════════════════════════════════════
# Garde-fous de régression sur la donnée réelle
# ═════════════════════════════════════════════════════════════════════════════

class TestCouvertureSurLaDonneeReelle:
    def _aretes_reelles(self) -> list[dict]:
        if not FICHIER_BRUT.exists():
            pytest.skip(f"{FICHIER_BRUT} absent — régénérer avec tools/adapter_wind_river.py")
        return json.loads(FICHIER_BRUT.read_text(encoding="utf-8"))["cultures_associations"]

    def test_tous_les_compagnons_sources_sont_couverts_par_cible_compagnons(self):
        """Un libellé de compagnon absent de CIBLE_COMPAGNONS n'est ni traduit
        ni écarté explicitement — c'est un trou de couverture, pas un « hors
        périmètre » assumé. Une future mise à jour de companion_plants.csv qui
        introduirait un nouveau libellé doit faire échouer CE test."""
        aretes = self._aretes_reelles()
        manquants = {
            a["compagnon_source"] for a in aretes
            if a["compagnon_source"] not in svc_adaptateur.CIBLE_COMPAGNONS
        }
        assert manquants == set()

    def test_toutes_les_paires_retenues_ont_une_traduction_francaise(self):
        """[CA1] Le motif restitué au jardinier est toujours en français —
        jamais la phrase anglaise de la source, même à défaut de traduction."""
        aretes = self._aretes_reelles()
        _, rapport = svc_adaptateur.curer_associations(aretes)
        assert rapport.motifs_non_traduits == []

    def test_comptage_de_la_curation_sur_la_release_v1_0_0(self):
        """Chiffres figés le 01/09/2026 sur la release v1.0.0 — comme toute
        mesure du projet (US-140, US-161), à mettre à jour explicitement si la
        source ou la table de curation change, jamais en silence."""
        aretes = self._aretes_reelles()
        entrees, rapport = svc_adaptateur.curer_associations(aretes)

        assert rapport.brutes == 217
        assert len(entrees) == 113
        assert rapport.retenues == 113
        assert len(rapport.hors_perimetre) == 65
        assert len(rapport.motifs_recycles) == 4
        assert len(rapport.auto_associations) == 1
        assert rapport.contradictions == ["courgette × Lamiacée"]

    def test_aucune_entree_retenue_n_est_en_anglais(self):
        """Filet de sécurité grossier : aucun motif retenu ne devrait plus
        porter de mot anglais évident échappé de la source."""
        aretes = self._aretes_reelles()
        entrees, _ = svc_adaptateur.curer_associations(aretes)
        mots_anglais_suspects = ("the ", "and ", "with ", "plants", "growth")
        for entree in entrees:
            motif_bas = entree["motif"].lower()
            assert not any(mot in motif_bas for mot in mots_anglais_suspects), entree

    def test_toutes_les_entrees_portent_niveau_preuve_traditionnel(self):
        """La source ne distingue pas l'établi du traditionnel (US-161/§6.5) :
        la curation ne lui fait dire ni plus ni moins que ce qu'elle affirme."""
        aretes = self._aretes_reelles()
        entrees, _ = svc_adaptateur.curer_associations(aretes)
        assert entrees  # non vide, sinon le test suivant est vacueusement vrai
        assert all(e["niveau_preuve"] == "traditionnel" for e in entrees)


# ═════════════════════════════════════════════════════════════════════════════
# Règles de curation isolées, sur des arêtes synthétiques
# ═════════════════════════════════════════════════════════════════════════════

class TestHorsPerimetre:
    def test_compagnon_ornemental_ecarte(self):
        """Une ornementale (Marigold) n'a ni culture ni famille à laquelle se
        rattacher légitimement dans ce référentiel de potager."""
        entrees, rapport = svc_adaptateur.curer_associations(
            [_arete("tomate", "Marigold", "favorable")]
        )
        assert entrees == []
        assert rapport.hors_perimetre == ["tomate × Marigold"]

    def test_arbre_ecarte(self):
        entrees, rapport = svc_adaptateur.curer_associations(
            [_arete("tomate", "Black Walnut", "defavorable")]
        )
        assert entrees == []
        assert rapport.hors_perimetre == ["tomate × Black Walnut"]


class TestMotifsRecycles:
    def test_motif_recycle_documente_par_l_audit_ecarte(self):
        """[Audit du 01/09/2026] tomate × Hot Peppers : le motif source décrit
        les feuilles d'une aubergine, pas de la tomate. (« Catnip » et
        « Alyssum », également cités par l'audit, sont déjà écartés comme hors
        périmètre avant même d'atteindre cette règle — voir
        TestHorsPerimetre — donc pas de bon exemple ici.)"""
        entrees, rapport = svc_adaptateur.curer_associations(
            [_arete("tomate", "Hot Peppers", "favorable")]
        )
        assert entrees == []
        assert rapport.motifs_recycles == ["tomate × Hot Peppers"]

    def test_meme_compagnon_legitime_pour_une_autre_culture_n_est_pas_ecarte(self, monkeypatch):
        """[Notes techniques] Le retrait cible la PAIRE (culture, compagnon),
        jamais le libellé seul — « Mint » n'est exclu que pour haricot, pas
        pour une autre culture. Traduction injectée pour isoler cette seule
        règle, indépendamment de la couverture réelle de MOTIFS_FR."""
        monkeypatch.setitem(svc_adaptateur.MOTIFS_FR, ("chou", "menthe"), "répulsif générique")
        entrees, rapport = svc_adaptateur.curer_associations(
            [_arete("chou", "Mint", "favorable")]
        )
        assert rapport.motifs_recycles == []
        assert len(entrees) == 1
        assert entrees[0]["compagnon"] == "menthe"


class TestAutoAssociation:
    def test_culture_associee_a_elle_meme_ecartee(self):
        """[Audit du 01/09/2026] tomate × Tomatoes = favorable : une culture
        n'est jamais son propre compagnon."""
        entrees, rapport = svc_adaptateur.curer_associations(
            [_arete("tomate", "Tomatoes", "favorable")]
        )
        assert entrees == []
        assert rapport.auto_associations == ["tomate × Tomatoes"]


class TestContradictionApresFusionDesDoublons:
    def test_contradiction_masquee_par_deux_libelles_devient_visible(self):
        """[Audit du 01/09/2026] C'est EXACTEMENT le défaut relevé pour
        courgette × herbes aromatiques : « Aromatic Herbs » (favorable) et
        « Aromatic herbs (Sage) » (défavorable) sont deux libellés distincts
        pour le MÊME compagnon canonique (famille Lamiacée) — la contradiction
        n'est visible qu'après fusion, et la paire entière est écartée plutôt
        que tranchée à la place de la source (§6.5)."""
        entrees, rapport = svc_adaptateur.curer_associations([
            _arete("courgette", "Aromatic Herbs", "favorable"),
            _arete("courgette", "Aromatic herbs (Sage)", "defavorable"),
        ])
        assert entrees == []
        assert rapport.contradictions == ["courgette × Lamiacée"]

    def test_deux_libelles_du_meme_compagnon_en_accord_sont_fusionnes_sans_perte(self):
        """Le cas courant : deux libellés (singulier/pluriel) du même
        compagnon, d'accord sur la nature, ne comptent que pour UNE arête."""
        entrees, rapport = svc_adaptateur.curer_associations([
            _arete("tomate", "Basil", "favorable"),
        ])
        assert len(entrees) == 1
        assert rapport.contradictions == []


class TestVocabulaireFamille:
    def test_compagnon_generique_rattache_a_une_famille(self):
        """[CA4] « Brassicas » ne désigne aucune culture précise — la famille
        botanique est la cible défendable."""
        entrees, _ = svc_adaptateur.curer_associations(
            [_arete("tomate", "Brassicas", "defavorable")]
        )
        assert len(entrees) == 1
        assert entrees[0]["compagnon"] == "Brassicacée"
