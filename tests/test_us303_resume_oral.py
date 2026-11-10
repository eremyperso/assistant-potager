"""
tests/test_us303_resume_oral.py — US-303 : résumer la réponse du compagnon pour l'oral

Le résumé parlé (1 à 2 phrases, 300 caractères au plus) est produit à partir du seul
`texte_compagnon` de l'échange, contrôlé (rien d'inventé, rien d'affiché, une carte n'est
jamais dite « enregistrée »), gardé dans `texte_oral` et exposé par `echange_id`.
Aucun appel réseau : la passerelle est simulée ; le jeu de réponses du compagnon est
`tests/corpus/us303_reponses_compagnon.json` (CA9).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app import config
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import echange_pwa as svc_echange
from app.services.context import TenantContext, default_context
from app.services.voix import oral
from app.services.voix import preferences as prefs
from database.models import EchangeConversation, User
from llm import passerelle
from llm.passerelle import LLMIndisponibleError, ReponseLLM

RACINE = Path(__file__).resolve().parents[1]
CTX = default_context()
AUTRE_JARDINIER = TenantContext(user_id=CTX.user_id + 1, potager_id=CTX.potager_id, role="owner")
AUTRE_POTAGER = TenantContext(user_id=CTX.user_id, potager_id=CTX.potager_id + 1, role="owner")
CORPUS = json.loads((RACINE / "tests" / "corpus" / "us303_reponses_compagnon.json").read_text(encoding="utf-8"))
REPONSES = CORPUS["reponses"]
GHERKIN = ("## Arrosage des tomates\nArrosez **au pied**, 2 à 3 litres par pied, le matin. "
           "Évitez le feuillage pour limiter le mildiou. 🍅")
RESUME_GHERKIN = "Arrosez vos tomates au pied le matin, deux à trois litres par pied, sans mouiller les feuilles."


def _llm(texte: str) -> ReponseLLM:
    return ReponseLLM(texte=texte, modele="modele-oral", appel_type="oral")


@pytest.fixture
def modele():
    """Le modèle `oral` simulé ; `modele.return_value` fixe sa réponse."""
    with patch("llm.passerelle.appeler_chat", return_value=_llm(RESUME_GHERKIN)) as appel:
        yield appel


@pytest.fixture
def echange(memoire_compagnon):
    """Retient un échange du jardinier et rend son identifiant."""
    def _noter(texte_compagnon: str, ctx: TenantContext = CTX, **champs) -> int:
        svc_conversations.noter(ctx, "phrase du jardinier", texte_compagnon, canal="pwa", **champs)
        return svc_conversations.dernier_id(ctx)
    return _noter


def _ligne(fabrique, echange_id: int) -> EchangeConversation:
    with fabrique() as db:
        return db.get(EchangeConversation, echange_id)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — migration v72
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Migration:

    def test_us303_ca1_migration_ajoute_texte_oral(self):
        sql = (RACINE / "migrations" / "migration_v72.sql").read_text(encoding="utf-8")
        assert "ALTER TABLE echanges_conversation" in sql
        assert "ADD COLUMN IF NOT EXISTS texte_oral TEXT NULL" in sql

    def test_us303_ca1_rollback(self):
        sql = (RACINE / "migrations" / "rollback_v72.sql").read_text(encoding="utf-8")
        assert "DROP COLUMN IF EXISTS texte_oral" in sql

    def test_us303_ca1_modele(self):
        colonne = EchangeConversation.__table__.c.texte_oral
        assert colonne.nullable is True


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — 1 à 2 phrases, plafond, rien d'inventé, à partir du seul texte du compagnon
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Fidelite:

    def test_us303_ca2_plafond_par_defaut(self):
        assert config.VOIX_ORAL_MAX_CARACTERES == 300

    def test_us303_ca2_le_modele_ne_recoit_que_le_texte_du_compagnon(self, modele):
        oral.resumer(CTX, GHERKIN)
        kwargs = modele.call_args.kwargs
        assert kwargs["message_utilisateur"] == GHERKIN
        assert kwargs["appel_type"] == passerelle.TYPE_ORAL
        assert "phrase du jardinier" not in kwargs["prompt_variable"]

    def test_us303_ca2_resume_fidele_garde(self, modele):
        resume = oral.resumer(CTX, GHERKIN)
        assert (resume.texte, resume.issue) == (RESUME_GHERKIN, oral.ISSUE_MODELE)

    @pytest.mark.parametrize("sortie, motif", [
        ("Arrosez vos tomates avec 5 litres par pied.", "chiffre_invente:5"),
        ("Arrosez vos tomates avec cinq litres par pied.", "chiffre_invente:5"),
        ("Arrosez vos tomates en mai, au pied.", "date_inventee:mai"),
        ("Arrosez vos tomates jeudi, au pied.", "date_inventee:jeudi"),
        ("Arrosez vos tomates au pied, comme le conseille Rustica.", "nom_invente:Rustica"),
    ])
    def test_us303_ca2_fait_invente_refuse(self, sortie, motif):
        assert oral.motif_de_rejet(sortie, GHERKIN, 300, carte=False) == motif

    def test_us303_ca2_sortie_trop_longue_refusee(self, modele):
        modele.return_value = _llm("Arrosez au pied. " * 30)
        resume = oral.resumer(CTX, GHERKIN)
        assert resume.issue == oral.ISSUE_REPLI_REFUSE
        assert len(resume.texte) <= 300

    def test_us303_ca2_nombres_en_lettres(self):
        assert oral.nombres_en_lettres("dix-huit millimètres, quatre-vingts plants, vingt et un jours") == {18, 80, 21}
        assert oral.nombres_en_lettres("une planche, un pied") == set()
        assert oral.nombres_en_lettres("soixante-dix graines") == {70}
        assert oral.nombres_en_lettres("deux cents") == {200}


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — ni Markdown, ni émoji, ni URL, ni crochets ; unités dites
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Oralite:

    def test_us303_ca3_nettoyage(self):
        texte = "## Titre\n**2,5 kg** de tomates 🍅 [emotion=happy] voir https://exemple.fr ou [la fiche](https://x.fr)."
        nettoye = oral.nettoyer_oral(texte)
        for interdit in ("#", "*", "🍅", "[", "]", "https", "exemple.fr"):
            assert interdit not in nettoye
        assert "2,5 kilos" in nettoye and "la fiche" in nettoye

    @pytest.mark.parametrize("brut, attendu", [
        ("3 cm", "3 centimètres"), ("6 m²", "6 mètres carrés"), ("2 L", "2 litres"),
        ("-2 °C", "-2 degrés"), ("85 %", "85 pour cent"), ("20 g", "20 grammes"), ("1,5 m", "1,5 mètres"),
    ])
    def test_us303_ca3_unites_ecrites_pour_etre_dites(self, brut, attendu):
        assert oral.nettoyer_oral(brut) == attendu

    @pytest.mark.parametrize("sortie", [
        "**Arrosez** au pied, deux à trois litres.",
        "- Arrosez au pied, deux à trois litres.",
        "Arrosez au pied 🍅, deux à trois litres.",
        "Arrosez au pied, voir https://exemple.fr.",
        "[emotion=warm] Arrosez au pied, deux à trois litres.",
    ])
    def test_us303_ca3_mise_en_forme_refusee(self, sortie):
        assert oral.motif_de_rejet(sortie, GHERKIN, 300, carte=False) == "mise_en_forme"

    def test_us303_ca3_le_prompt_demande_les_nombres_en_mots(self):
        assert "deux kilos et demi" in oral.PROMPT_FIXE


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — une carte : « Je vous propose … : confirmez à l'écran », jamais « enregistré »
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Carte:
    CARTE = "proposition : Semis de radis · 30 graines · Planche 2"

    def test_us303_ca4_carte_fidele(self, modele):
        modele.return_value = _llm("Je vous propose d'enregistrer trente graines de radis sur la planche deux : "
                                   "confirmez à l'écran.")
        resume = oral.resumer(CTX, self.CARTE, carte=True)
        assert resume.issue == oral.ISSUE_MODELE
        assert resume.texte.startswith("Je vous propose") and resume.texte.endswith("confirmez à l'écran.")

    @pytest.mark.parametrize("sortie", [
        "C'est enregistré : trente graines de radis sur la planche deux.",
        "J'ai noté vos trente graines de radis : confirmez à l'écran.",
        "Je vous propose trente graines de radis, c'est noté : confirmez à l'écran.",
        "Trente graines de radis sur la planche deux.",
    ])
    def test_us303_ca4_carte_jamais_dite_enregistree(self, modele, sortie):
        modele.return_value = _llm(sortie)
        resume = oral.resumer(CTX, self.CARTE, carte=True)
        assert resume.issue == oral.ISSUE_REPLI_REFUSE
        assert resume.texte == "Je vous propose d'enregistrer semis de radis · 30 graines · Planche 2 : confirmez à l'écran." \
            or resume.texte.startswith("Je vous propose d'enregistrer semis de radis")
        assert "enregistré" not in resume.texte and "noté" not in resume.texte

    def test_us303_ca4_repli_tutoie_si_le_texte_tutoie(self):
        texte = "Je te propose de créer la parcelle « Serre nord ». Tu confirmes ?"
        assert oral.repli_proposition(texte, 300) == "Je te propose ceci : confirme à l'écran."

    def test_us303_ca4_echange_porte_une_carte(self, echange, memoire_compagnon):
        geste = _ligne(memoire_compagnon, echange("proposition : Semis de radis", outils=("geste",)))
        commande = _ligne(memoire_compagnon, echange("Voici ce que je te propose.", proposition_id=None))
        assert oral.porte_une_carte(geste) is True
        assert oral.porte_une_carte(commande) is False
        assert oral.porte_une_carte(type("E", (), {"proposition_id": 12, "outils": None, "texte_compagnon": "x"})())


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — réponse déjà courte : reprise nettoyée, sans modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Court:

    def test_us303_ca5_court_sans_modele(self, modele):
        resume = oral.resumer(CTX, "Les fèves se sèment en novembre, à 5 cm de profondeur.")
        modele.assert_not_called()
        assert resume.issue == oral.ISSUE_COURT
        assert resume.texte == "Les fèves se sèment en novembre, à 5 centimètres de profondeur."

    def test_us303_ca5_court_avec_markdown_passe_par_le_modele(self, modele):
        oral.resumer(CTX, "Semez **en novembre**.")
        modele.assert_called_once()

    def test_us303_ca5_une_carte_courte_passe_toujours_par_la_forme_proposee(self, modele):
        modele.return_value = _llm("Je vous propose d'enregistrer un semis de radis : confirmez à l'écran.")
        oral.resumer(CTX, "proposition : Semis de radis", carte=True)
        modele.assert_called_once()


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — modèle indisponible : texte nettoyé, coupé à la dernière phrase complète
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Repli:
    LONG = ("## Semis\n" + "Semez les radis en ligne, à un centimètre de profondeur. " * 8 + "Arrosez ensuite.")

    def test_us303_ca6_repli_coupe_a_la_derniere_phrase(self, caplog):
        with patch("llm.passerelle.appeler_chat", side_effect=LLMIndisponibleError("délai")), \
             caplog.at_level(logging.WARNING, logger="potager"):
            resume = oral.resumer(CTX, self.LONG)
        assert resume.issue == oral.ISSUE_REPLI_INDISPONIBLE
        assert len(resume.texte) <= 300 and resume.texte.endswith(".")
        assert "#" not in resume.texte
        assert "modèle indisponible" in caplog.text

    def test_us303_ca6_couper_sans_phrase_complete(self):
        assert oral.couper("mot " * 200, 50).endswith(".")
        assert len(oral.couper("mot " * 200, 50)) <= 50

    def test_us303_ca6_repli_indisponible_non_garde(self, echange, memoire_compagnon):
        echange_id = echange(self.LONG)
        with patch("llm.passerelle.appeler_chat", side_effect=LLMIndisponibleError("délai")):
            oral.texte_oral(CTX, echange_id)
        assert _ligne(memoire_compagnon, echange_id).texte_oral is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — calculé une seule fois par échange
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7UneFois:

    def test_us303_ca7_seconde_lecture_sans_modele(self, modele, echange, memoire_compagnon):
        echange_id = echange(GHERKIN)
        premier = oral.texte_oral(CTX, echange_id)
        second = oral.texte_oral(CTX, echange_id)
        assert modele.call_count == 1
        assert premier.texte == second.texte == RESUME_GHERKIN
        assert second.issue == oral.ISSUE_DEJA_CALCULE
        assert _ligne(memoire_compagnon, echange_id).texte_oral == RESUME_GHERKIN

    def test_us303_ca7_repli_refuse_garde(self, modele, echange, memoire_compagnon):
        modele.return_value = _llm("Arrosez avec 9 litres.")
        echange_id = echange(GHERKIN)
        oral.texte_oral(CTX, echange_id)
        oral.texte_oral(CTX, echange_id)
        assert modele.call_count == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — echange_id exposé ; échange d'un autre jardinier ou potager introuvable
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8EchangeId:

    def test_us303_ca8_messages_expose_echange_id(self, memoire_compagnon):
        reponse = svc_echange.ReponseCompagnon(texte="Bonjour.")
        with patch.object(svc_echange, "_repondre", side_effect=lambda ctx, t, m: (
                svc_conversations.noter(ctx, t, "Bonjour.", canal="pwa"), reponse)[1]):
            donnees = svc_echange.repondre(CTX, "bonjour").en_donnees()
        assert donnees["echange_id"] == svc_conversations.dernier_id(CTX)
        assert donnees["echange_id"] is not None

    def test_us303_ca8_sans_echange_retenu_echange_id_nul(self, memoire_compagnon):
        with patch.object(svc_echange, "_repondre", return_value=svc_echange.ReponseCompagnon(texte="")):
            assert svc_echange.repondre(CTX, "x").en_donnees()["echange_id"] is None

    def test_us303_ca8_historique_expose_echange_id(self, echange):
        echange_id = echange("Bonjour.")
        with patch("app.services.compagnon.echange_pwa.svc_distribution.messages_du_jardinier", return_value=[]), \
             patch("app.services.compagnon.echange_pwa.cartes_en_cours", return_value=[]), \
             patch("app.services.compagnon.echange_pwa.svc_deux_canaux.telegram_lie", return_value=True), \
             patch("app.services.compagnon.echange_pwa.svc_deux_canaux.invitation_telegram", return_value=False):
            histoire = svc_echange.historique(CTX)
        assert histoire["echanges"][-1]["echange_id"] == echange_id

    @pytest.mark.parametrize("autre", [AUTRE_JARDINIER, AUTRE_POTAGER])
    def test_us303_ca8_echange_d_un_autre_introuvable(self, modele, echange, autre):
        echange_id = echange(GHERKIN)
        with pytest.raises(oral.EchangeIntrouvableError):
            oral.texte_oral(autre, echange_id)
        modele.assert_not_called()


class TestCA8Route:

    @pytest.fixture
    def client(self, test_engine, test_db, memoire_compagnon):
        from app.api import main
        test_db.merge(User(id=CTX.user_id, email="un@exemple.fr"))
        test_db.commit()
        fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
        main.app.dependency_overrides[main.get_current_user_ctx] = lambda: CTX
        with patch.object(main, "SessionLocal", fabrique), \
             patch("llm.passerelle.lister_voix_mistral", return_value=[]):
            with TestClient(main.app) as c:
                yield c, fabrique
        main.app.dependency_overrides.pop(main.get_current_user_ctx, None)

    def _mode_vocal(self, fabrique):
        with fabrique() as db:
            with patch("llm.passerelle.lister_voix_mistral", return_value=[]):
                prefs.enregistrer(db, CTX, mode_vocal=True)

    def test_us303_ca8_route_rend_le_resume(self, client, modele, echange):
        c, fabrique = client
        self._mode_vocal(fabrique)
        echange_id = echange(GHERKIN)
        r = c.get(f"/compagnon/voix/oral/{echange_id}")
        assert r.status_code == 200
        assert r.json() == {"echange_id": echange_id, "texte_oral": RESUME_GHERKIN}

    def test_us303_ca8_route_404_hors_du_compte(self, client, modele, echange):
        c, fabrique = client
        self._mode_vocal(fabrique)
        echange_id = echange(GHERKIN, ctx=AUTRE_JARDINIER)
        assert c.get(f"/compagnon/voix/oral/{echange_id}").status_code == 404
        assert c.get("/compagnon/voix/oral/999999").status_code == 404

    def test_us303_ca8_route_403_sans_mode_vocal(self, client, modele, echange):
        c, _ = client
        assert c.get(f"/compagnon/voix/oral/{echange(GHERKIN)}").status_code == 403
        modele.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — par la passerelle ; jeu d'au moins dix réponses du compagnon, modèle simulé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Corpus:

    def test_us303_ca9_type_oral_declare(self):
        assert passerelle.TYPE_ORAL == "oral" and "oral" in passerelle.TYPES_APPEL
        assert "oral" in config.GROQ_MODELE_PAR_TYPE

    def test_us303_ca9_passe_par_la_passerelle(self):
        source = (RACINE / "app" / "services" / "voix" / "oral.py").read_text(encoding="utf-8")
        assert "passerelle.appeler_chat(" in source
        assert "import groq" not in source and "mistralai" not in source

    def test_us303_ca9_jeu_d_au_moins_dix_reponses(self):
        natures = {r["nature"] for r in REPONSES}
        assert len(REPONSES) >= 10
        assert {"carte", "question", "support"} <= natures
        assert any(len(r["texte"]) > config.VOIX_ORAL_MAX_CARACTERES for r in REPONSES if r["nature"] == "support")

    @pytest.mark.parametrize("cas", [r for r in REPONSES if r["fidele"]], ids=lambda r: r["id"])
    def test_us303_ca9_resume_fidele_accepte(self, modele, cas):
        modele.return_value = _llm(cas["fidele"])
        resume = oral.resumer(CTX, cas["texte"], carte=cas["carte"])
        assert resume.issue == oral.ISSUE_MODELE, oral.motif_de_rejet(cas["fidele"], cas["texte"], 300, cas["carte"])
        assert len(resume.texte) <= 300

    @pytest.mark.parametrize("cas, sortie", [
        (r, s) for r in REPONSES for s in r["infideles"]
    ], ids=lambda v: v["id"] if isinstance(v, dict) else v[:30])
    def test_us303_ca9_resume_infidele_refuse(self, modele, cas, sortie):
        modele.return_value = _llm(sortie)
        resume = oral.resumer(CTX, cas["texte"], carte=cas["carte"])
        assert resume.issue == oral.ISSUE_REPLI_REFUSE
        if cas["carte"]:
            assert "confirm" in resume.texte and "enregistré" not in resume.texte

    @pytest.mark.parametrize("cas", [r for r in REPONSES if not r["fidele"]], ids=lambda r: r["id"])
    def test_us303_ca9_reponse_courte_sans_modele(self, modele, cas):
        resume = oral.resumer(CTX, cas["texte"], carte=cas["carte"])
        modele.assert_not_called()
        assert resume.issue == oral.ISSUE_COURT


# ═════════════════════════════════════════════════════════════════════════════
# Scénario Gherkin
# ═════════════════════════════════════════════════════════════════════════════
def test_us303_gherkin(modele, echange, memoire_compagnon):
    # Given Gaston a répondu "## Arrosage des tomates…"
    echange_id = echange(GHERKIN)
    # When la lecture de cet échange est demandée pour la première fois
    resume = oral.texte_oral(CTX, echange_id)
    # Then le résumé parlé ressemble à "Arrosez vos tomates au pied le matin…"
    assert resume.texte == RESUME_GHERKIN
    # And il est gardé dans texte_oral
    assert _ligne(memoire_compagnon, echange_id).texte_oral == RESUME_GHERKIN
    # When la lecture est demandée une seconde fois / Then aucun appel au modèle n'est fait
    modele.reset_mock()
    oral.texte_oral(CTX, echange_id)
    modele.assert_not_called()
