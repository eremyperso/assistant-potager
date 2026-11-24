"""
tests/test_us341_connaissance_rattachee_culture.py — Rattacher la connaissance à une culture [US-341]
=====================================================================================================
Une question sur la salade ne rend jamais un passage sur la tomate, quelle que soit sa note (CA1, CA2) ; une culture
sans fiche le dit et rend ce que le référentiel en sait (CA3) ; la réponse affichée est celle du modèle, le code n'y
ajoute que la source (CA4) ; le domaine d'US-283 est conservé (CA5) ; la carte de couverture sort du dépôt (CA6).

Aucun appel réseau ni modèle : base SQLite des tests, RAG sur son repli lexical.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services import connaissance
from app.services.agent import savoir
from app.services.capacites import registre
from app.services.capacites.registre import AppelCapacite
from app.services.context import TenantContext
from database.models import (CultureConfig, FamilleBotanique, FenetreCulturale, ItineraireCultural, Potager,
                             ReferentielSource, User)
from tools import carte_couverture_corpus as carte

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AGRONOMIE = "Assistant Potager — rédaction interne"
RACINE = Path(__file__).resolve().parents[1]

#: La tomate a une fiche très bien notée sur « semer en novembre » : c'est le piège du 14/11.
PASSAGE_TOMATE = "Pour semer en novembre sous abri, la tomate demande de la chaleur et beaucoup de lumière."
PASSAGE_SALADE = "La laitue se sème en novembre sous châssis, au frais, en terre fine."
PASSAGE_GENERAL = "Semer en novembre sous abri demande de surveiller l'humidité et d'aérer chaque jour."


@pytest.fixture
def base(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1, zone_climatique="oceanique"))
    test_db.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0", attribution="Test",
                                  partageable=True, importee=True))
    test_db.flush()
    solanacee = FamilleBotanique(nom="Solanacée", nom_normalise="solanacee")
    astera = FamilleBotanique(nom="Astéracée", nom_normalise="asteracee")
    test_db.add_all([solanacee, astera])
    test_db.flush()
    cultures = {}
    for nom, famille in (("tomate", solanacee), ("salade", astera), ("carotte", None)):
        c = CultureConfig(nom=nom, type_organe_recolte="reproducteur" if nom == "tomate" else "végétatif",
                          famille_id=famille.id if famille else None)
        test_db.add(c)
        test_db.flush()
        cultures[nom] = c
    it = ItineraireCultural(culture_id=cultures["salade"].id, nom="standard", nom_normalise="standard", source_id=1)
    test_db.add(it)
    test_db.flush()
    test_db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="oceanique", phase="semis_pepiniere",
                                 mois_debut=2, mois_fin=3, source_id=1))
    test_db.commit()
    return cultures


def _document(db, reference: str, titre: str, contenu: str, *, culture_id=None, famille=connaissance.FAMILLE_AGRONOMIE,
              source: str = AGRONOMIE):
    document, _ = connaissance.enregistrer_document(
        db, reference=reference, titre=titre, famille=famille, source=source,
        niveau_confiance=connaissance.NIVEAU_VERIFIE, empreinte="e1")
    connaissance.remplacer_fragments(db, document, [connaissance.FragmentAIngerer(
        reference=f"{reference}#00", ordre=0, intitule="Semer en novembre", contenu=contenu, culture_id=culture_id)])
    db.commit()


@pytest.fixture
def corpus_sans_fiche_salade(test_db, base):
    """Une fiche sur la tomate (bien notée), un passage général, aucune fiche pour la salade."""
    _document(test_db, "agronomie/tomate-conduite.md", "Conduite de la tomate", PASSAGE_TOMATE,
              culture_id=base["tomate"].id)
    _document(test_db, "agronomie/general-abri.md", "Semer sous abri", PASSAGE_GENERAL)
    return base


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — Jamais le passage d'une autre culture
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1CA2CultureStricte:

    def test_us341_gherkin_aucun_passage_tomate_pour_la_salade(self, test_db, corpus_sans_fiche_salade):
        question = "comment je fais pour semer mes salades en novembre sous abri ?"
        avant = connaissance.rechercher(test_db, CTX, question, domaine=connaissance.DOMAINE_JARDINAGE)
        assert any("tomate" in p.contenu for p in avant.passages)  # le défaut du 14/11, sans restriction stricte
        apres = connaissance.rechercher(test_db, CTX, question, domaine=connaissance.DOMAINE_JARDINAGE,
                                        culture_stricte=True)
        assert apres.passages and all("tomate" not in p.contenu for p in apres.passages)
        assert [p.contenu for p in apres.passages] == [PASSAGE_GENERAL]

    def test_us341_la_culture_se_lit_dans_la_question_ou_se_donne(self, test_db, corpus_sans_fiche_salade):
        assert connaissance.culture_visee(test_db, CTX, "mes salades en novembre").nom == "salade"
        assert connaissance.culture_visee(test_db, CTX, "semer en novembre") is None
        assert connaissance.culture_visee(test_db, CTX, "semer en novembre", "tomates").nom == "tomate"

    def test_us341_la_fiche_de_la_bonne_culture_est_rendue(self, test_db, corpus_sans_fiche_salade):
        r = connaissance.rechercher(test_db, CTX, "semer mes tomates en novembre sous abri",
                                    domaine=connaissance.DOMAINE_JARDINAGE, culture_stricte=True)
        assert PASSAGE_TOMATE in [p.contenu for p in r.passages]

    def test_us341_sans_culture_visee_la_recherche_ne_change_pas(self, test_db, corpus_sans_fiche_salade):
        question = "semer en novembre sous abri"
        assert connaissance.rechercher(test_db, CTX, question, culture_stricte=True).passages == \
            connaissance.rechercher(test_db, CTX, question).passages

    def test_us341_le_domaine_d_us283_est_conserve(self, test_db, corpus_sans_fiche_salade):
        _document(test_db, "doc_app/abri.md", "Le plan et les abris", "Semer sous abri : déclare l'abri de la parcelle.",
                  famille=connaissance.FAMILLE_DOC_APP, source=connaissance.SOURCE_GUIDE_APPLICATION)
        r = connaissance.rechercher(test_db, CTX, "semer mes salades sous abri",
                                    domaine=connaissance.DOMAINE_APPLICATION, culture_stricte=True)
        assert [p.source for p in r.passages] == [connaissance.SOURCE_GUIDE_APPLICATION]


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Sans fiche, le dire et rendre ce que le référentiel sait
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3PasDeFiche:

    def test_us341_une_culture_sans_fiche_le_dit_et_rend_le_referentiel(self, test_db, corpus_sans_fiche_salade):
        d = _capacite(test_db, "chercher_connaissance", {"question": "comment je fais pour mes salades ?",
                                                         "domaine": "jardinage"})
        assert d["fiche_absente"] is True and d["culture"] == "salade"
        assert d["texte"] == "Pas de fiche salade dans l'application."
        ref = d["referentiel"]
        assert ref["famille"] == "Astéracée"
        assert ref["fenetres"] == [{"phase": "semis_pepiniere", "fenetre": ref["fenetres"][0]["fenetre"]}]
        assert "février" in ref["fenetres"][0]["fenetre"].lower() or "fev" in ref["fenetres"][0]["fenetre"].lower()
        assert all("tomate" not in p["texte"] for p in d["passages"])
        assert "rien d'autre" in d["consigne"]

    def test_us341_une_culture_avec_fiche_ne_dit_pas_qu_elle_manque(self, test_db, corpus_sans_fiche_salade):
        d = _capacite(test_db, "chercher_connaissance", {"question": "semer mes tomates en novembre",
                                                         "domaine": "jardinage"})
        assert "fiche_absente" not in d and d["culture"] == "tomate"
        assert any(PASSAGE_TOMATE == p["texte"] for p in d["passages"])

    def test_us341_culture_inconnue_du_referentiel(self, test_db, corpus_sans_fiche_salade):
        d = _capacite(test_db, "chercher_connaissance", {"question": "semer en novembre", "culture": "physalis"})
        assert d["culture_connue"] is False and d["passages"] == []

    def test_us341_savoir_du_referentiel_sans_calendrier(self, test_db, corpus_sans_fiche_salade, base):
        s = connaissance.savoir_du_referentiel(test_db, CTX, base["carotte"])
        assert s["culture"] == "carotte" and s["famille"] is None and s["source"].startswith("référentiel")

    def test_us341_l_outil_de_l_agent_dit_aussi_pas_de_fiche(self, test_db, corpus_sans_fiche_salade, monkeypatch):
        import database.db as base_donnees

        monkeypatch.setattr(base_donnees, "SessionLocal", lambda: _Session(test_db))
        releves = savoir.Releves()
        sortie = json.loads(savoir.chercher_connaissance(
            {"question": "comment je fais pour mes salades ?", "domaine": "jardinage"}, CTX, releves))
        assert sortie["fiche_absente"] is True and sortie["passages"] == []
        assert sortie["texte"] == "Pas de fiche salade dans l'application."
        assert releves.resumes == ["Pas de fiche salade dans l'application."]


class _Session:
    """Une session que `chercher_connaissance` peut fermer sans fermer celle du test."""

    def __init__(self, db):
        self._db = db

    def __getattr__(self, nom):
        return getattr(self._db, nom)

    def close(self):
        pass


def _capacite(db, nom: str, arguments: dict) -> dict:
    return registre.appeler(db, CTX, nom, arguments)


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — La réponse affichée est celle du modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4ReponseDuModele:

    def test_us341_le_code_ne_remplace_plus_le_texte_par_un_resume_de_passage(self):
        releves = savoir.Releves()
        passage = " ".join(f"mot{i}" for i in range(40))
        releves.ajouter(json.dumps({"passages": [{"texte": passage, "source": "Fiche tomate"}]}),
                        resume="Début du passage.", source="Fiche tomate")
        releves.passages.append(passage)
        assert savoir.recopie(passage, releves)
        affiche = savoir.controler(passage, releves)
        assert affiche.startswith(passage) and "Début du passage." not in affiche
        assert affiche.endswith("Source : Fiche tomate.")

    def test_us341_une_dose_reste_remplacee_par_securite(self):
        releves = savoir.Releves()
        releves.ajouter("{}", resume="Ce que l'application sait.", source="Fiche")
        assert savoir.controler("Verse 20 ml de bouillie bordelaise par litre.", releves) != \
            "Verse 20 ml de bouillie bordelaise par litre."


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — La carte de couverture
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6CarteDeCouverture:

    def _fiche(self, dossier: Path, nom: str, culture: str) -> None:
        (dossier / nom).write_text(f'---\ntitre: "{nom}"\nculture: {culture}\n---\n\n# x\n', encoding="utf-8")

    def test_us341_la_carte_dit_qui_a_une_fiche_et_qui_n_en_a_pas(self, tmp_path):
        self._fiche(tmp_path, "tomate-conduite-recolte.md", "tomate")
        self._fiche(tmp_path, "tomate-problemes.md", "tomate")
        self._fiche(tmp_path, "carotte-problemes.md", "carotte")
        (tmp_path / "README.md").write_text("culture: salade", encoding="utf-8")
        lignes = carte.carte(["Tomate", "salade", "carotte"], carte.fiches_du_depot(tmp_path))
        assert [(l["culture"], l["conduite_recolte"], l["problemes"]) for l in lignes] == [
            ("salade", False, False), ("carotte", False, True), ("Tomate", True, True)]
        texte = carte.en_markdown(lignes)
        assert "3 cultures au référentiel : **1 sans aucune fiche**, 1 avec une seule des deux, 1 complètes" in texte
        assert "| salade | ❌ | ❌ |" in texte

    def test_us341_la_carte_du_depot_couvre_les_fiches_existantes(self):
        fiches = carte.fiches_du_depot(RACINE / "data" / "connaissance" / "agronomie")
        assert fiches and all(types <= {"conduite_recolte", "problemes"} for types in fiches.values())

    def test_us341_la_carte_est_dans_le_dossier_de_l_epic(self):
        chemin = RACINE / "docs" / "EPIC 20 - COMPAGNON CLIENT DES CAPACITES" / "08_CARTE_COUVERTURE_CORPUS.md"
        assert "sans aucune fiche" in chemin.read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# Registre
# ═════════════════════════════════════════════════════════════════════════════
def test_us341_la_capacite_annonce_la_culture_et_reste_en_lecture_seule():
    capacite = registre.REGISTRE["chercher_connaissance"]
    assert capacite.ecriture is False and "culture" in capacite.proprietes
    assert "jamais ceux d'une autre" in capacite.description


def test_us341_la_commande_ecrit_la_carte(tmp_path, monkeypatch, capsys):
    (tmp_path / "salade-problemes.md").write_text('---\nculture: salade\n---\n', encoding="utf-8")
    monkeypatch.setattr(carte, "cultures_du_referentiel", lambda: ["salade", "chou"])
    sortie = tmp_path / "carte.md"
    monkeypatch.setattr("sys.argv", ["carte", "--racine", str(tmp_path), "--sortie", str(sortie)])
    assert carte.main() == 0
    assert "| chou | ❌ | ❌ |" in sortie.read_text(encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["carte", "--racine", str(tmp_path)])
    assert carte.main() == 0 and "Carte de couverture" in capsys.readouterr().out


def test_us341_le_conseil_general_d_une_culture_sans_fiche_n_a_aucun_chiffre(test_db, corpus_sans_fiche_salade):
    """22/11 : le « conseil général » du navet donnait « 5 cm » et « 10 cm » 3 fois sur 3."""
    d = _capacite(test_db, "chercher_connaissance", {"question": "comment je fais pour mes salades ?",
                                                     "domaine": "jardinage"})
    assert "aucun chiffre" in d["consigne"] and "aucune dose" in d["consigne"]
