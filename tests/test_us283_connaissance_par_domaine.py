"""
tests/test_us283_connaissance_par_domaine.py — Séparer l'application et le jardinage [US-283]
=============================================================================================
`chercher_connaissance` cherche dans UN domaine (application, jardinage, carnet), sur une liste
blanche de sources ; sous le seuil il rend « rien de fiable » ; un passage recopié est renvoyé une
fois au modèle, puis remplacé par le texte du code ; une source hors liste n'entre jamais dans
l'index et n'est jamais rendue.

Aucun appel réseau ni modèle réel : la passerelle et, selon le test, le RAG sont simulés.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import connaissance
from app.services.agent import catalogue_outils, interpreteur_agent, savoir
from app.services.agent.catalogue_outils import OUTIL_CHERCHER_CONNAISSANCE
from app.services.context import TenantContext
from database.models import KnowledgeDocument, Potager, User
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils
from tools import ingerer_connaissance as ing

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
RACINE_DEPOT = Path(__file__).resolve().parent.parent
GUIDE = connaissance.SOURCE_GUIDE_APPLICATION
AGRONOMIE = "Assistant Potager — rédaction interne"
AUTOMOBILE = "Assistant Automobile — rédaction interne"
PHRASE_AUTONOMIE = "pour mon objectif d'autonomie, que dois je privilégie ?"

#: Un passage de plus de 25 mots : le modèle le recopie, le contrôle le voit.
PASSAGE_LONG = (
    "Pour viser l'autonomie en tomates, privilégie des variétés productives et échelonne les "
    "plantations afin de récolter sur une longue période, puis conserve le surplus en coulis ou "
    "en bocaux pour couvrir les besoins de la famille pendant tout l'hiver suivant sans racheter."
)


# ═════════════════════════════════════════════════════════════════════════════
# Outillage
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def base(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin A", proprietaire_id=1))
    test_db.commit()
    return test_db


def _document(db, reference: str, titre: str, contenu: str, *, famille: str, source: str,
              potager_id=None, intitule: str = "Section"):
    document, _ = connaissance.enregistrer_document(
        db, reference=reference, titre=titre, famille=famille, source=source,
        niveau_confiance=connaissance.NIVEAU_VERIFIE, empreinte="e1", potager_id=potager_id,
    )
    connaissance.remplacer_fragments(db, document, [connaissance.FragmentAIngerer(
        reference=f"{reference}#00", ordre=0, intitule=intitule, contenu=contenu,
    )])
    db.commit()
    return document


@pytest.fixture
def corpus_mele(base):
    """Le même vocabulaire dans les trois domaines, et une source étrangère au potager."""
    _document(base, "doc_app/plan.md", "Répartir les cultures dans le plan",
              "Le plan répartit les cultures pour ton objectif d'autonomie en tomates et légumes.",
              famille=connaissance.FAMILLE_DOC_APP, source=GUIDE)
    _document(base, "agronomie/tomate.md", "Autonomie en tomates",
              "Pour ton objectif d'autonomie en tomates, privilégie des variétés productives.",
              famille=connaissance.FAMILLE_AGRONOMIE, source=AGRONOMIE)
    _document(base, "memoire/1.md", "Note du 3 mai",
              "Objectif d'autonomie : quinze pieds de tomates cette année.",
              famille=connaissance.FAMILLE_MEMOIRE_POTAGER, source=connaissance.SOURCE_MEMOIRE,
              potager_id=1)
    _document(base, "tests/corpus/automobile/auto.md", "Règles de sécurité automobile",
              "Privilégie la sécurité : objectif d'autonomie de la batterie, tomates écrasées.",
              famille=connaissance.FAMILLE_AGRONOMIE, source=AUTOMOBILE)
    return base


def _sources(contexte) -> set[str]:
    return {passage.source for passage in contexte.passages}


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def boucle_simulee(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("Planche Sud",))
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))
    monkeypatch.setattr(savoir, "precharger", lambda ctx, releves: "")


def _reponse(texte: str = "", *appels: AppelOutil) -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT, tokens_in=900, tokens_out=50,
        latence_ms=100, appels=tuple(appels), statut=passerelle.STATUT_OK,
    )


def _appel_connaissance(domaine: str = "jardinage", question: str = "autonomie tomates") -> AppelOutil:
    return AppelOutil(OUTIL_CHERCHER_CONNAISSANCE, {"question": question, "domaine": domaine}, id="c1")


def _contexte(contenu: str = PASSAGE_LONG, confiance: float = 1.0):
    passage = SimpleNamespace(titre_document="Autonomie en tomates", intitule="Variétés", contenu=contenu)
    return SimpleNamespace(passages=(passage,), confiance=confiance)


def _boucle(modele, phrase: str, *tours: ReponseOutils, contexte=None):
    modele.side_effect = list(tours)
    with patch("app.services.connaissance.rechercher", return_value=contexte or _contexte()) as rechercher:
        resultat = interpreteur_agent.proposer(phrase, CTX, None)
    return resultat, rechercher


def _executer(arguments: dict, contexte=None, releves=None):
    releves = releves if releves is not None else savoir.Releves()
    with patch("app.services.connaissance.rechercher", return_value=contexte or _contexte()) as rechercher:
        brut = json.loads(savoir.executer(OUTIL_CHERCHER_CONNAISSANCE, arguments, CTX, releves))
    return brut, releves, rechercher


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — Un domaine obligatoire, une liste blanche par domaine
# ═════════════════════════════════════════════════════════════════════════════
class TestDomaine:
    def test_us283_ca1_le_schema_exige_le_domaine(self):
        schema = next(s for s in catalogue_outils.schemas_savoir()
                      if s["function"]["name"] == OUTIL_CHERCHER_CONNAISSANCE)["function"]["parameters"]
        assert "domaine" in schema["required"]
        assert schema["properties"]["domaine"]["enum"] == ["application", "jardinage", "carnet"]

    def test_us283_ca1_la_parite_du_plafond_tient(self):
        assert catalogue_outils.controler_parite_outils() == []

    def test_us283_ca1_jardinage_ne_rend_que_l_agronomie(self, corpus_mele):
        contexte = connaissance.rechercher(corpus_mele, CTX, PHRASE_AUTONOMIE, domaine="jardinage")
        assert contexte.passages
        assert _sources(contexte) == {AGRONOMIE}

    def test_us283_ca1_application_ne_rend_que_le_guide(self, corpus_mele):
        contexte = connaissance.rechercher(corpus_mele, CTX, PHRASE_AUTONOMIE, domaine="application")
        assert _sources(contexte) == {GUIDE}

    def test_us283_ca1_carnet_ne_rend_que_les_notes_du_potager(self, corpus_mele):
        contexte = connaissance.rechercher(corpus_mele, CTX, PHRASE_AUTONOMIE, domaine="carnet")
        assert _sources(contexte) == {connaissance.SOURCE_MEMOIRE}

    def test_us283_ca1_le_carnet_d_un_autre_potager_reste_invisible(self, corpus_mele):
        autre = TenantContext(user_id=2, potager_id=2, role="owner")
        assert not connaissance.rechercher(corpus_mele, autre, PHRASE_AUTONOMIE, domaine="carnet").passages

    def test_us283_ca1_un_domaine_inconnu_est_refuse(self, base):
        with pytest.raises(ValueError, match="Domaine inconnu"):
            connaissance.rechercher(base, CTX, "tomates", domaine="automobile")

    def test_us283_ca1_l_outil_transmet_le_domaine(self):
        _, _, rechercher = _executer({"question": "comment fonctionne le carnet ?", "domaine": "application"})
        assert rechercher.call_args.kwargs["domaine"] == "application"

    def test_us283_ca1_le_domaine_se_lit_sans_casse_ni_accent(self):
        _, _, rechercher = _executer({"question": "tomates", "domaine": "Jardinage"})
        assert rechercher.call_args.kwargs["domaine"] == "jardinage"

    @pytest.mark.parametrize("domaine", [None, "", "automobile"])
    def test_us283_ca1_sans_domaine_l_outil_le_redemande(self, domaine):
        arguments = {"question": "tomates", **({"domaine": domaine} if domaine is not None else {})}
        brut, releves, rechercher = _executer(arguments)
        assert brut["erreur"] == "domaine manquant" and "jardinage" in brut["a_faire"]
        assert not rechercher.called and releves.vide


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Sous le seuil : rien de fiable
# ═════════════════════════════════════════════════════════════════════════════
class TestSeuil:
    def test_us283_ca2_sous_le_seuil_rien_de_fiable(self, monkeypatch):
        monkeypatch.setattr("app.config.RAG_SEUIL_CONFIANCE", 0.6)
        brut, releves, _ = _executer({"question": "x", "domaine": "jardinage"}, _contexte(confiance=0.2))
        assert brut["disponible"] is False and brut["fiable"] is False
        assert brut["texte"] == savoir.TEXTE_SANS_DONNEE
        assert brut["passages"] == [] and PASSAGE_LONG not in json.dumps(brut, ensure_ascii=False)
        assert brut["rubriques_proches"] == ["Variétés"]
        assert releves.resumes == [savoir.TEXTE_SANS_DONNEE] and not releves.sources

    def test_us283_ca2_au_seuil_les_passages_sont_rendus(self, monkeypatch):
        monkeypatch.setattr("app.config.RAG_SEUIL_CONFIANCE", 0.6)
        brut, releves, _ = _executer({"question": "x", "domaine": "jardinage"}, _contexte(confiance=0.6))
        assert brut["disponible"] is True
        assert releves.sources == ["Autonomie en tomates"] and releves.passages == [PASSAGE_LONG]

    def test_us283_ca2_rien_de_fiable_le_texte_du_code_le_dit(self, monkeypatch):
        monkeypatch.setattr("app.config.RAG_SEUIL_CONFIANCE", 0.6)
        _, releves, _ = _executer({"question": "x", "domaine": "jardinage"}, _contexte(confiance=0.1))
        assert savoir.controler("Plante 40 pieds.", releves) == savoir.TEXTE_SANS_DONNEE

    def test_us283_ca2_un_corpus_vide_reste_vide(self):
        brut, releves, _ = _executer({"question": "x", "domaine": "jardinage"},
                                     SimpleNamespace(passages=(), confiance=0.0))
        assert brut["disponible"] is False and releves.vide


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Une synthèse, jamais une recopie
# ═════════════════════════════════════════════════════════════════════════════
def _releves_avec_passage() -> savoir.Releves:
    _, releves, _ = _executer({"question": "x", "domaine": "jardinage"})
    return releves


class TestRecopie:
    def test_us283_ca3_vingt_six_mots_consecutifs_sont_une_recopie(self):
        mots = PASSAGE_LONG.split()
        assert savoir.recopie("Voici : " + " ".join(mots[3:29]) + ".", _releves_avec_passage())

    def test_us283_ca3_vingt_cinq_mots_ne_sont_pas_une_recopie(self):
        mots = PASSAGE_LONG.split()
        assert not savoir.recopie(" ".join(mots[3:28]), _releves_avec_passage())

    def test_us283_ca3_casse_accents_et_ponctuation_ne_masquent_pas_la_recopie(self):
        texte = PASSAGE_LONG.upper().replace("é", "e").replace(",", " ;")
        assert savoir.recopie(texte, _releves_avec_passage())

    def test_us283_ca3_sans_passage_rien_n_est_une_recopie(self):
        assert not savoir.recopie(PASSAGE_LONG, savoir.Releves())

    def test_us283_ca3_la_relance_n_est_donnee_qu_une_fois(self):
        releves = _releves_avec_passage()
        assert savoir.relance_recopie(PASSAGE_LONG, releves) == savoir.CONSIGNE_RECOPIE
        assert savoir.relance_recopie(PASSAGE_LONG, releves) is None

    def test_us283_ca3_le_controle_remplace_une_recopie_par_le_texte_du_code(self):
        texte = savoir.controler(PASSAGE_LONG, _releves_avec_passage())
        assert texte.split("\n")[0] == savoir._resume_passage(PASSAGE_LONG) != PASSAGE_LONG
        assert "Source : Autonomie en tomates" in texte

    def test_us283_ca3_le_texte_du_code_cite_le_debut_du_passage(self):
        resume = savoir._resume_passage("Échelonne les plantations. " + PASSAGE_LONG)
        assert resume == "Échelonne les plantations."

    def test_us283_ca3_un_passage_court_est_cite_entier(self):
        assert savoir._resume_passage("Ramasse le soir.") == "Ramasse le soir."

    def test_us283_ca3_la_recopie_est_renvoyee_une_fois_au_modele(self, modele, boucle_simulee):
        synthese = ("Choisis des variétés productives et échelonne tes plantations ; le surplus se "
                    "conserve en coulis. Source : Autonomie en tomates.")
        resultat, _ = _boucle(modele, PHRASE_AUTONOMIE,
                              _reponse("", _appel_connaissance()), _reponse(PASSAGE_LONG), _reponse(synthese))
        assert resultat.texte == synthese
        relance = modele.call_args_list[2].kwargs["historique"][-1]
        assert relance == {"role": "user", "content": savoir.CONSIGNE_RECOPIE}

    def test_us283_ca3_une_seconde_recopie_cede_au_texte_du_code(self, modele, boucle_simulee):
        resultat, _ = _boucle(modele, PHRASE_AUTONOMIE,
                              _reponse("", _appel_connaissance()), _reponse(PASSAGE_LONG), _reponse(PASSAGE_LONG))
        assert resultat.texte != PASSAGE_LONG
        assert "Source : Autonomie en tomates" in resultat.texte
        assert modele.call_count == 3


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Aucune source hors du domaine du potager
# ═════════════════════════════════════════════════════════════════════════════
class TestSourcesHorsListe:
    def test_us283_ca4_la_liste_blanche(self):
        assert connaissance.source_autorisee(connaissance.FAMILLE_DOC_APP, GUIDE)
        assert connaissance.source_autorisee(connaissance.FAMILLE_AGRONOMIE, AGRONOMIE)
        assert connaissance.source_autorisee(connaissance.FAMILLE_MEMOIRE_POTAGER, connaissance.SOURCE_MEMOIRE)
        assert not connaissance.source_autorisee(connaissance.FAMILLE_AGRONOMIE, AUTOMOBILE)
        assert not connaissance.source_autorisee(connaissance.FAMILLE_DOC_APP, AGRONOMIE)

    def test_us283_ca4_le_carnet_garde_sa_source(self):
        from app.services import memoire_potager
        assert memoire_potager.SOURCE_MEMOIRE == connaissance.SOURCE_MEMOIRE

    def test_us283_ca4_l_ingestion_refuse_le_corpus_automobile(self, base):
        chemin = RACINE_DEPOT / "tests/corpus/automobile/auto-security.md"
        with pytest.raises(ing.DocumentInvalide, match="hors liste"):
            ing.ingerer_fichier(base, chemin, RACINE_DEPOT, ing.Rapport())
        assert base.query(KnowledgeDocument).count() == 0

    def test_us283_ca4_le_corpus_du_depot_est_dans_la_liste(self):
        for chemin in (RACINE_DEPOT / "data/connaissance").rglob("*.md"):
            if chemin.name.upper() == "README.MD":
                continue
            entete, _ = ing.lire_entete(chemin.read_text(encoding="utf-8"))
            assert connaissance.source_autorisee(entete["famille"], entete["source"]), chemin.name

    def test_us283_ca4_aucun_domaine_ne_rend_une_source_hors_liste(self, corpus_mele):
        for domaine in connaissance.DOMAINES:
            contexte = connaissance.rechercher(corpus_mele, CTX, "sécurité automobile batterie", domaine=domaine)
            assert AUTOMOBILE not in _sources(contexte)

    def test_us283_ca4_la_purge_retire_les_sources_hors_liste(self, corpus_mele):
        rapport = ing.Rapport()
        retires = ing.purger_hors_liste(corpus_mele, rapport)
        assert retires == ["tests/corpus/automobile/auto.md"] and rapport.supprimes == 1
        sources = {s for (s,) in corpus_mele.query(KnowledgeDocument.source).all()}
        assert sources == {GUIDE, AGRONOMIE, connaissance.SOURCE_MEMOIRE}

    def test_us283_ca4_la_purge_simulee_n_ecrit_rien(self, corpus_mele):
        rapport = ing.Rapport()
        assert ing.purger_hors_liste(corpus_mele, rapport, dry_run=True)
        assert corpus_mele.query(KnowledgeDocument).count() == 4

    def test_us283_ca4_la_purge_est_branchee_au_deploiement(self):
        for fichier in ("scripts/deploy.sh", "scripts/update_dev.ps1",
                        ".github/workflows/deploy.yml", ".github/workflows/deploy-dev.yml"):
            assert "--purger-hors-liste" in (RACINE_DEPOT / fichier).read_text(encoding="utf-8"), fichier


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — La cascade sans domaine ne change pas
# ═════════════════════════════════════════════════════════════════════════════
def test_us283_ca5_sans_domaine_la_recherche_est_inchangee(corpus_mele):
    contexte = connaissance.rechercher(corpus_mele, CTX, PHRASE_AUTONOMIE, limite=10)
    assert {GUIDE, AGRONOMIE} <= _sources(contexte)


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin
# ═════════════════════════════════════════════════════════════════════════════
def test_us283_gherkin_autonomie_jardinage_synthese_et_source(modele, boucle_simulee):
    synthese = "Choisis des variétés productives et conserve le surplus. Source : Autonomie en tomates."
    resultat, rechercher = _boucle(modele, PHRASE_AUTONOMIE,
                                   _reponse("", _appel_connaissance("jardinage")), _reponse(synthese))
    assert rechercher.call_args.kwargs["domaine"] == "jardinage"
    assert resultat.texte == synthese and resultat.proposition is None


def test_us283_gherkin_carnet_de_l_application(modele, boucle_simulee):
    _, rechercher = _boucle(modele, "comment fonctionne le carnet ?",
                            _reponse("", _appel_connaissance("application", "carnet")),
                            _reponse("Le carnet garde ce que tu confirmes. Source : Autonomie en tomates."))
    assert rechercher.call_args.kwargs["domaine"] == "application"
