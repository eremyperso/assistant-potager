"""
tests/test_us309_cout_grille_tarifaire.py — US-309 : chiffrer chaque appel d'après une grille tarifaire

Le coût est calculé par la passerelle à l'écriture de la ligne, en micro-euros entiers, d'après
`data/tarifs/tarifs_llm.json`, et figé : changer la grille ne modifie aucune ligne écrite.
Aucun appel réseau, aucun appel de modèle : les clients sont simulés.
"""
from __future__ import annotations

import ast
import copy
import json
import os
import pathlib
import subprocess
import sys
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app import config
from app.services.context import TenantContext
from app.services.pilotage import chiffrage, tarifs
from app.services.pilotage.tarifs import (
    Cout, GrilleTarifaireInvalideError, charger_grille, chiffrer,
    fournisseur_et_modele, valider_grille,
)
from database.models import ConsoTokens
from llm import contexte_appel, passerelle

RACINE = pathlib.Path(__file__).resolve().parent.parent
CTX = TenantContext(user_id=7, potager_id=3, role="owner")


# ─────────────────────────────────────────────────────────────────────────────
# Grilles de test
# ─────────────────────────────────────────────────────────────────────────────
def _grille_gherkin(version: str = "2026-11", facteur: int = 1) -> dict:
    """La grille du scénario : 0,10 € / M en entrée, 0,30 € en sortie, 0,01 € en cache."""
    def p(valeur: str) -> str:
        return str(round(float(valeur) * facteur, 6))
    return {
        "version": version, "devise_reference": "EUR",
        "palier_gratuit": "Coût au tarif public, même au palier gratuit.",
        "fournisseurs": {"mistral": {"modeles": {"modele-test": {
            "unite": "jeton", "devise": "EUR",
            "prix_entree_par_million": p("0.10"), "prix_sortie_par_million": p("0.30"),
            "prix_cache_par_million": p("0.01"),
            "date_releve": "2026-11-12", "source": "https://exemple.invalid/tarifs",
        }}}},
    }


GRILLE_GHERKIN = valider_grille(_grille_gherkin())
GRILLE_DOUBLE = valider_grille(_grille_gherkin("2026-12", facteur=2))


def _cout(grille, modele="mistral/modele-test", unite="jeton", t_in=0, t_out=0, t_cache=0, issue="ok"):
    return chiffrer(grille, modele, unite, t_in, t_out, t_cache, issue)


def _reponse(tokens_in: int = 100, tokens_out: int = 20, cache: int = 0):
    usage = SimpleNamespace(prompt_tokens=tokens_in, completion_tokens=tokens_out,
                            prompt_tokens_details=SimpleNamespace(cached_tokens=cache))
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="ok", tool_calls=None))],
                           usage=usage)


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    monkeypatch.setattr(contexte_appel, "_en_mode_test", lambda: False)


@pytest.fixture
def conso(test_db):
    with patch("llm.passerelle.SessionLocal", lambda: test_db):
        yield test_db


@pytest.fixture
def appel_mistral():
    """Un appel de chat servi par Mistral (client simulé, modèle de la grille)."""
    faux = MagicMock()
    faux.chat.completions.create.return_value = _reponse()
    with patch("llm.passerelle.modele_pour", lambda t: "mistral/mistral-small-2603"), \
            patch("llm.passerelle._resoudre_client", return_value=faux):
        yield faux


def _chat(appel_type=passerelle.TYPE_AGENT):
    return passerelle.appeler_chat(appel_type=appel_type, ctx=CTX, prompt_fixe="Tu es un assistant.")


def _lignes(db) -> list[ConsoTokens]:
    return db.query(ConsoTokens).order_by(ConsoTokens.id).all()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — migration v75 et colonnes
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Colonnes:

    def test_us309_ca1_migration_et_rollback(self):
        migration = (RACINE / "migrations" / "migration_v75.sql").read_text(encoding="utf-8")
        for fragment in ("fournisseur", "cout_micro_eur", "tarif_version", "BIGINT", "ADD COLUMN IF NOT EXISTS"):
            assert fragment in migration
        rollback = (RACINE / "migrations" / "rollback_v75.sql").read_text(encoding="utf-8")
        for colonne in ("fournisseur", "cout_micro_eur", "tarif_version"):
            assert f"DROP COLUMN IF EXISTS {colonne}" in rollback

    def test_us309_ca1_colonnes_nullables(self):
        colonnes = ConsoTokens.__table__.c
        for nom in ("fournisseur", "cout_micro_eur", "tarif_version"):
            assert colonnes[nom].nullable is True
        assert type(colonnes.cout_micro_eur.type).__name__ == "BigInteger"

    def test_us309_ca1_l_existant_n_est_pas_chiffre_a_la_migration(self, test_db):
        test_db.add(ConsoTokens(potager_id=1, date=date.today(), appel_type="agent", modele="m"))
        test_db.commit()
        ligne = test_db.query(ConsoTokens).one()
        assert (ligne.fournisseur, ligne.cout_micro_eur, ligne.tarif_version) == (None, None, None)

    def test_us309_ca1_un_cout_negatif_est_refuse(self, test_db):
        from sqlalchemy.exc import IntegrityError
        test_db.add(ConsoTokens(potager_id=1, date=date.today(), appel_type="agent", modele="m",
                                cout_micro_eur=-1))
        with pytest.raises(IntegrityError):
            test_db.commit()
        test_db.rollback()


# ═════════════════════════════════════════════════════════════════════════════
# CA2 / CA10 — la grille du dépôt : contenu, sources, dates
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2CA10Grille:

    def test_us309_ca2_la_grille_du_depot_est_valide(self):
        grille = charger_grille()
        assert grille.version == tarifs.GRILLE.version == "2026-11"
        assert {f for f, _ in grille.modeles} == {"groq", "mistral"}

    def test_us309_ca2_chaque_entree_dit_unite_prix_devise(self):
        for (fournisseur, modele), tarif in tarifs.GRILLE.modeles.items():
            assert tarif.unite in {"jeton", "seconde", "caractere"}, modele
            assert tarif.devise in tarifs.GRILLE.taux_pour_1_eur, modele
            assert tarif.prix, f"{fournisseur}/{modele} sans prix"

    def test_us309_ca2_les_trois_formes_de_prix_sont_representees(self):
        unites = {t.unite for t in tarifs.GRILLE.modeles.values()}
        assert unites == {"jeton", "seconde", "caractere"}
        champs = {c for t in tarifs.GRILLE.modeles.values() for c in t.prix}
        assert {"prix_entree_par_million", "prix_sortie_par_million", "prix_cache_par_million",
                "prix_par_minute", "prix_par_heure", "prix_par_million_caracteres"} <= champs

    def test_us309_ca10_chaque_entree_porte_sa_source_et_sa_date_de_releve(self):
        brut = json.loads((RACINE / "data" / "tarifs" / "tarifs_llm.json").read_text(encoding="utf-8"))
        for fournisseur, bloc in brut["fournisseurs"].items():
            for modele, entree in bloc["modeles"].items():
                assert entree["source"].startswith("https://"), f"{fournisseur}/{modele}"
                date.fromisoformat(entree["date_releve"])
        for devise, taux in brut["taux_change"].items():
            assert taux["source"].startswith("https://") and date.fromisoformat(taux["date_releve"]), devise

    def test_us309_ca10_une_entree_sans_source_ou_sans_date_est_refusee(self):
        for champ in ("source", "date_releve"):
            donnees = _grille_gherkin()
            del donnees["fournisseurs"]["mistral"]["modeles"]["modele-test"][champ]
            with pytest.raises(GrilleTarifaireInvalideError, match=champ):
                valider_grille(donnees)

    def test_us309_ca10_la_page_source_est_une_adresse(self):
        donnees = _grille_gherkin()
        donnees["fournisseurs"]["mistral"]["modeles"]["modele-test"]["source"] = "de mémoire"
        with pytest.raises(GrilleTarifaireInvalideError, match="source"):
            valider_grille(donnees)

    def test_us309_ca2_une_devise_etrangere_exige_son_taux_date(self):
        donnees = _grille_gherkin()
        donnees["fournisseurs"]["mistral"]["modeles"]["modele-test"]["devise"] = "USD"
        with pytest.raises(GrilleTarifaireInvalideError, match="taux"):
            valider_grille(donnees)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — lue au démarrage, jamais en ligne ; mal formée = démarrage arrêté
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Demarrage:

    @pytest.mark.parametrize("mutation,fragment", [
        (lambda d: d.pop("version"), "version"),
        (lambda d: d.pop("palier_gratuit"), "palier_gratuit"),
        (lambda d: d.pop("fournisseurs"), "fournisseurs"),
        (lambda d: d["fournisseurs"]["mistral"]["modeles"]["modele-test"].update(unite="litre"), "unite"),
        (lambda d: d["fournisseurs"]["mistral"]["modeles"]["modele-test"].update(prix_entree_par_million=0.1), "décimal"),
        (lambda d: d["fournisseurs"]["mistral"]["modeles"]["modele-test"].update(prix_sortie_par_million="-1"), "décimal"),
        (lambda d: d["fournisseurs"]["mistral"]["modeles"]["modele-test"].pop("prix_sortie_par_million"), "prix_sortie"),
        (lambda d: d["fournisseurs"]["mistral"]["modeles"]["modele-test"].update(date_releve="12/11/2026"), "date"),
    ])
    def test_us309_ca3_grille_mal_formee_refusee(self, mutation, fragment):
        donnees = copy.deepcopy(_grille_gherkin())
        mutation(donnees)
        with pytest.raises(GrilleTarifaireInvalideError, match=fragment):
            valider_grille(donnees)

    def test_us309_ca3_fichier_absent_ou_json_illisible(self, tmp_path):
        with pytest.raises(GrilleTarifaireInvalideError, match="illisible"):
            charger_grille(str(tmp_path / "absente.json"))
        mauvais = tmp_path / "mauvaise.json"
        mauvais.write_text("{pas du json", encoding="utf-8")
        with pytest.raises(GrilleTarifaireInvalideError, match="JSON invalide"):
            charger_grille(str(mauvais))

    def test_us309_ca3_un_import_avec_grille_cassee_arrete_le_processus(self, tmp_path):
        """Le démarrage s'arrête vraiment : `import llm.passerelle` échoue avec une grille mal formée."""
        racine_factice = tmp_path / "depot"
        (racine_factice / "data" / "tarifs").mkdir(parents=True)
        (racine_factice / "data" / "tarifs" / "tarifs_llm.json").write_text("{}", encoding="utf-8")
        code = (
            "import sys; sys.path.insert(0, %r); from app.services.pilotage import tarifs"
        ) % str(RACINE)
        env = {k: v for k, v in os.environ.items() if not k.startswith("GROQ_")}
        env.update({"APP_ENV": "pytest_isole_us309", "GROQ_API_KEY": "x", "TELEGRAM_BOT_TOKEN": "x",
                    "DATABASE_URL": "sqlite://", "JWT_SECRET": "x"})
        # La grille du dépôt est celle de `CHEMIN_GRILLE` : on la remplace par une grille cassée
        # dans le processus fils, sans toucher au fichier du dépôt.
        code = (
            "import sys; sys.path.insert(0, %r)\n"
            "import builtins, io, json\n"
            "vrai_open = builtins.open\n"
            "def faux_open(chemin, *a, **k):\n"
            "    if str(chemin).endswith('tarifs_llm.json'):\n"
            "        return io.StringIO('{}')\n"
            "    return vrai_open(chemin, *a, **k)\n"
            "builtins.open = faux_open\n"
            "from app.services.pilotage import tarifs\n"
        ) % str(RACINE)
        resultat = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", code], cwd=tmp_path, env=env,
                                  capture_output=True, text=True, encoding="utf-8", timeout=60)
        assert resultat.returncode != 0
        assert "GrilleTarifaireInvalideError" in resultat.stderr

    def test_us309_ca3_la_grille_n_est_jamais_lue_en_ligne_a_l_appel(self, conso, appel_mistral):
        with patch("builtins.open", side_effect=AssertionError("fichier relu à l'appel")), \
                patch("app.services.pilotage.tarifs.charger_grille",
                      side_effect=AssertionError("grille rechargée à l'appel")):
            _chat()
        assert len(_lignes(conso)) == 1

    def test_us309_ca3_le_module_n_importe_aucun_client_reseau(self):
        arbre = ast.parse((RACINE / "app" / "services" / "pilotage" / "tarifs.py").read_text(encoding="utf-8"))
        importes = {n.names[0].name.split(".")[0] for n in ast.walk(arbre) if isinstance(n, ast.Import)}
        importes |= {(n.module or "").split(".")[0] for n in ast.walk(arbre) if isinstance(n, ast.ImportFrom)}
        assert not importes & {"requests", "httpx", "urllib", "aiohttp", "socket", "groq"}


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — le calcul : entiers, cache à son tarif, cache retiré de l'entrée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Calcul:

    def test_us309_ca4_scenario_gherkin_275(self):
        """8 000 jetons d'entrée dont 6 000 en cache et 50 de sortie : 275 micro-euros."""
        cout = _cout(GRILLE_GHERKIN, t_in=8000, t_out=50, t_cache=6000)
        assert cout.cout_micro_eur == 275 and cout.tarif_version == "2026-11"

    def test_us309_ca4_le_cache_est_retire_de_l_entree_au_plein_tarif(self):
        sans_cache = _cout(GRILLE_GHERKIN, t_in=8000, t_out=50).cout_micro_eur          # 800 + 15
        avec_cache = _cout(GRILLE_GHERKIN, t_in=8000, t_out=50, t_cache=6000).cout_micro_eur
        assert sans_cache == 815 and avec_cache == 275 < sans_cache

    def test_us309_ca4_le_cache_est_un_sous_ensemble_de_l_entree(self):
        """Un cache déclaré plus grand que l'entrée ne produit pas de jetons négatifs."""
        assert _cout(GRILLE_GHERKIN, t_in=1000, t_cache=5000).cout_micro_eur == 10    # 1000 × 0,01

    def test_us309_ca4_cache_sans_tarif_publie_au_prix_d_entree(self):
        """Groq ne publie pas de tarif de cache : borne haute, jamais un rabais inventé."""
        sans = _cout(tarifs.GRILLE, "openai/gpt-oss-120b", t_in=1000, t_out=100).cout_micro_eur
        avec = _cout(tarifs.GRILLE, "openai/gpt-oss-120b", t_in=1000, t_out=100, t_cache=600).cout_micro_eur
        assert sans == avec == 189       # (1000 × 0,15 + 100 × 0,60) / 1,1127 = 188,7

    def test_us309_ca4_un_seul_arrondi_sur_le_total(self):
        """Le demi remonte ; l'arrondi porte sur le total, pas sur chaque terme."""
        # 5 jetons à 0,10 €/M = 0,5 µ€ → 1 ; 5 jetons de sortie à 0,30 €/M = 1,5 µ€ → 2 ; ensemble 2,0 → 2
        assert _cout(GRILLE_GHERKIN, t_in=5).cout_micro_eur == 1
        assert _cout(GRILLE_GHERKIN, t_out=5).cout_micro_eur == 2
        assert _cout(GRILLE_GHERKIN, t_in=5, t_out=5).cout_micro_eur == 2

    def test_us309_ca4_le_cout_est_un_entier_python(self):
        cout = _cout(tarifs.GRILLE, "mistral/mistral-small-2603", t_in=123, t_out=45).cout_micro_eur
        assert type(cout) is int

    def test_us309_ca4_conversion_usd_au_taux_fixe_de_la_grille(self):
        # (100 × 0,15 + 20 × 0,6) / 1,1127 = 24,26
        assert _cout(tarifs.GRILLE, "mistral/mistral-small-2603", t_in=100, t_out=20).cout_micro_eur == 24
        assert tarifs.GRILLE.taux_pour_1_eur["USD"] == pytest.approx(1.1127)

    def test_us309_ca4_dictee_a_la_seconde(self):
        # 5 s × 0,0035 $/min / 60 = 291,67 µ$ → / 1,1127 = 262,1 µ€
        cout = _cout(tarifs.GRILLE, "mistral/voxtral-mini-transcribe-3-0", unite="seconde", t_in=5)
        assert cout.cout_micro_eur == 262

    def test_us309_ca4_voix_au_caractere(self):
        # 7 caractères × 13 $/M = 91 µ$ → / 1,1127 = 81,8 µ€
        cout = _cout(tarifs.GRILLE, "mistral/voxtral-mini-tts-3-0", unite="caractere", t_in=7)
        assert cout.cout_micro_eur == 82

    def test_us309_ca4_whisper_a_l_heure(self):
        # 3 600 s = 1 h × 0,04 $ = 40 000 µ$ → / 1,1127 = 35 948,7 µ€ → 35 949
        cout = _cout(tarifs.GRILLE, "whisper-large-v3-turbo", unite="seconde", t_in=3600)
        assert cout.cout_micro_eur == 35949

    def test_us309_ca4_la_passerelle_ecrit_le_cout_a_l_ecriture(self, conso, appel_mistral):
        _chat()
        ligne = _lignes(conso)[0]
        assert (ligne.fournisseur, ligne.cout_micro_eur, ligne.tarif_version) == ("mistral", 24, "2026-11")

    def test_us309_ca4_la_passerelle_deduit_du_cache_de_la_reponse(self, conso, appel_mistral):
        appel_mistral.chat.completions.create.return_value = _reponse(8000, 50, 6000)
        with patch.object(tarifs, "GRILLE", GRILLE_GHERKIN), \
                patch("llm.passerelle.modele_pour", lambda t: "mistral/modele-test"):
            _chat()
        assert _lignes(conso)[0].cout_micro_eur == 275

    def test_us309_ca4_dictee_et_voix_chiffrees_par_la_passerelle(self, conso):
        faux = MagicMock()
        faux.audio.transcriptions.create.return_value = SimpleNamespace(text="bonjour", usage={"prompt_audio_seconds": 4.2})
        faux.post.return_value = {"audio_data": "SUQzZmF1eA=="}
        with patch("llm.passerelle._resoudre_client", return_value=faux), \
                patch("llm.passerelle._client_mesure", return_value=faux), \
                patch("llm.passerelle.modele_pour", lambda t: {"dictee": "mistral/voxtral-mini-transcribe-3-0",
                                                               "voix": "mistral/voxtral-mini-tts-3-0"}[t]):
            passerelle.dicter(ctx=CTX, contenu=b"a", nom_fichier="d.webm", duree_s=4.2)
            passerelle.synthetiser(ctx=CTX, texte="Bonjour", voix_id="v1")
        dictee, voix = _lignes(conso)
        assert (dictee.cout_micro_eur, voix.cout_micro_eur) == (262, 82)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — échec sans jeton = 0 ; modèle absent = NULL, jamais un coût inventé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Limites:

    def test_us309_ca5_echec_sans_jeton_coute_zero(self):
        for issue in ("quota", "delai", "erreur"):
            cout = _cout(GRILLE_GHERKIN, issue=issue)
            assert cout.cout_micro_eur == 0 and cout.tarif_version == "2026-11"

    def test_us309_ca5_echec_d_un_modele_inconnu_coute_zero_aussi(self):
        assert _cout(GRILLE_GHERKIN, "mistral/inconnu", issue="quota").cout_micro_eur == 0

    def test_us309_ca5_modele_absent_de_la_grille_donne_null_et_version(self):
        cout = _cout(GRILLE_GHERKIN, "mistral/inconnu", t_in=1000, t_out=10)
        assert cout.cout_micro_eur is None and cout.tarif_version == "2026-11"
        assert cout.fournisseur == "mistral"

    def test_us309_ca5_unite_differente_de_celle_du_tarif_donne_null(self):
        """La transcription Whisper journalise 0 jeton : la ligne n'est pas chiffrable."""
        cout = _cout(tarifs.GRILLE, "whisper-large-v3-turbo", unite="jeton")
        assert cout.cout_micro_eur is None

    def test_us309_ca5_fournisseur_inconnu_donne_null(self):
        cout = chiffrer(GRILLE_GHERKIN, "oai/gpt-4o", "jeton", 10, 10, 0, "ok", compatibles={"oai"})
        assert cout.cout_micro_eur is None and cout.fournisseur == "oai"

    def test_us309_ca5_la_passerelle_ecrit_null_pour_un_modele_absent(self, conso):
        faux = MagicMock()
        faux.chat.completions.create.return_value = _reponse()
        with patch("llm.passerelle.modele_pour", lambda t: "mistral/modele-inconnu"), \
                patch("llm.passerelle._resoudre_client", return_value=faux):
            _chat()
        ligne = _lignes(conso)[0]
        assert ligne.cout_micro_eur is None and ligne.tarif_version == "2026-11"

    def test_us309_ca5_la_passerelle_ecrit_zero_pour_un_echec(self, conso):
        import groq
        import httpx
        erreur = groq.InternalServerError(
            "panne", response=httpx.Response(503, request=httpx.Request("POST", "https://x.invalid")), body=None)
        faux = MagicMock()
        faux.chat.completions.create.side_effect = erreur
        with patch("llm.passerelle.modele_pour", lambda t: "mistral/mistral-small-2603"), \
                patch("llm.passerelle._resoudre_client", return_value=faux), \
                patch("llm.passerelle.time.sleep"), pytest.raises(passerelle.LLMIndisponibleError):
            _chat()
        assert {l.cout_micro_eur for l in _lignes(conso)} == {0}

    def test_us309_ca5_un_calcul_en_erreur_ne_perd_pas_la_ligne(self, conso, appel_mistral):
        with patch.object(tarifs, "chiffrer", side_effect=RuntimeError("boum")):
            _chat()
        ligne = _lignes(conso)[0]
        assert ligne.cout_micro_eur is None and ligne.tarif_version == "2026-11"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — changer la grille ne modifie aucune ligne déjà écrite
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Fige:

    def test_us309_ca6_scenario_gherkin_la_ligne_garde_275_et_2026_11(self, conso):
        faux = MagicMock()
        faux.chat.completions.create.return_value = _reponse(8000, 50, 6000)
        with patch("llm.passerelle.modele_pour", lambda t: "mistral/modele-test"), \
                patch("llm.passerelle._resoudre_client", return_value=faux):
            with patch.object(tarifs, "GRILLE", GRILLE_GHERKIN):
                _chat()
            avant = _lignes(conso)[0]
            assert (avant.cout_micro_eur, avant.tarif_version) == (275, "2026-11")

            with patch.object(tarifs, "GRILLE", GRILLE_DOUBLE):      # « 2026-12 » double les prix
                _chat()
        conso.expire_all()
        premiere, seconde = _lignes(conso)
        assert (premiere.cout_micro_eur, premiere.tarif_version) == (275, "2026-11")
        assert (seconde.cout_micro_eur, seconde.tarif_version) == (550, "2026-12")

    def test_us309_ca6_aucune_ecriture_de_cout_hors_de_la_passerelle_et_du_rejeu(self):
        """Le coût ne s'écrit qu'à l'écriture de la ligne (passerelle) et par le rejeu de l'historique."""
        ecrivains = []
        for chemin in list((RACINE / "app").rglob("*.py")) + list((RACINE / "llm").rglob("*.py")):
            source = chemin.read_text(encoding="utf-8-sig")
            # agregats.py [US-310], cout.py [US-313], derives.py [US-315], seuils.py [US-316], bilans.py [US-317], acteurs.py [US-319] : lecteurs seuls, ils somment
            # ou classent des coûts déjà figés.
            if "cout_micro_eur" in source and chemin.name not in {
                "passerelle.py", "chiffrage.py", "tarifs.py", "agregats.py", "cout.py", "derives.py", "seuils.py", "bilans.py", "acteurs.py",
            }:
                ecrivains.append(chemin.relative_to(RACINE).as_posix())
        assert ecrivains == []


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — tarif public, même au palier gratuit ; la grille le dit en clair
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7PalierGratuit:

    def test_us309_ca7_la_grille_le_dit_en_clair(self):
        assert "TARIF PUBLIC" in tarifs.GRILLE.palier_gratuit
        assert "palier gratuit" in tarifs.GRILLE.palier_gratuit

    def test_us309_ca7_une_grille_sans_cette_mention_est_refusee(self):
        donnees = _grille_gherkin()
        donnees["palier_gratuit"] = ""
        with pytest.raises(GrilleTarifaireInvalideError, match="palier_gratuit"):
            valider_grille(donnees)

    def test_us309_ca7_le_cout_ne_depend_pas_du_palier_du_compte(self):
        """Le calcul n'a aucune entrée « gratuit / payant » : même tokens, même coût."""
        import inspect
        assert "gratuit" not in " ".join(inspect.signature(chiffrer).parameters)
        assert _cout(GRILLE_GHERKIN, t_in=1000).cout_micro_eur == _cout(GRILLE_GHERKIN, t_in=1000).cout_micro_eur == 100


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — tools/chiffrer_historique.py : simulation par défaut, jamais une ligne chiffrée
# ═════════════════════════════════════════════════════════════════════════════
def _ajouter(db, **champs) -> ConsoTokens:
    base = dict(potager_id=1, date=date.today(), appel_type="agent", modele="mistral/modele-test",
                tokens_in=8000, tokens_out=50, tokens_cache=6000, issue="ok")
    base.update(champs)
    ligne = ConsoTokens(**base)
    db.add(ligne)
    db.commit()
    return ligne


class TestCA8Historique:

    def test_us309_ca8_simulation_par_defaut_n_ecrit_rien(self, test_db):
        _ajouter(test_db)
        bilan = chiffrage.rejouer_cout(test_db, GRILLE_GHERKIN)
        assert (bilan.examinees, bilan.chiffrees, bilan.cout_total_micro_eur) == (1, 1, 275)
        assert bilan.appliquer is False and bilan.lignes_ecrites == 0
        test_db.expire_all()
        ligne = test_db.query(ConsoTokens).one()
        assert (ligne.cout_micro_eur, ligne.tarif_version, ligne.fournisseur) == (None, None, None)

    def test_us309_ca8_appliquer_chiffre_et_marque_par_la_version_de_la_grille(self, test_db):
        _ajouter(test_db)
        chiffrage.rejouer_cout(test_db, GRILLE_GHERKIN, appliquer=True)
        ligne = test_db.query(ConsoTokens).one()
        assert (ligne.cout_micro_eur, ligne.tarif_version, ligne.fournisseur) == (275, "2026-11", "mistral")

    def test_us309_ca8_ne_touche_jamais_une_ligne_deja_chiffree(self, test_db):
        chiffree = _ajouter(test_db, cout_micro_eur=999, tarif_version="2026-10", fournisseur="mistral")
        sans_tarif_en_direct = _ajouter(test_db, cout_micro_eur=None, tarif_version="2026-10", modele="mistral/inconnu")
        vierge = _ajouter(test_db)
        bilan = chiffrage.rejouer_cout(test_db, GRILLE_DOUBLE, appliquer=True)
        assert bilan.examinees == 1
        test_db.expire_all()
        assert (chiffree.cout_micro_eur, chiffree.tarif_version) == (999, "2026-10")
        assert (sans_tarif_en_direct.cout_micro_eur, sans_tarif_en_direct.tarif_version) == (None, "2026-10")
        assert (vierge.cout_micro_eur, vierge.tarif_version) == (550, "2026-12")

    def test_us309_ca8_idempotent(self, test_db):
        _ajouter(test_db)
        chiffrage.rejouer_cout(test_db, GRILLE_GHERKIN, appliquer=True)
        second = chiffrage.rejouer_cout(test_db, GRILLE_DOUBLE, appliquer=True)
        assert second.examinees == 0
        assert test_db.query(ConsoTokens).one().cout_micro_eur == 275

    def test_us309_ca8_modele_absent_reste_sans_cout_et_est_liste(self, test_db):
        _ajouter(test_db, modele="mistral/voxtral-mini-tts-3-0            (voix : texte → MP3)", unite="caractere",
                 tokens_in=30, tokens_out=0, tokens_cache=0, issue="erreur")
        _ajouter(test_db, modele="mistral/inconnu")
        bilan = chiffrage.rejouer_cout(test_db, GRILLE_GHERKIN, appliquer=True)
        assert bilan.sans_tarif == 2 and bilan.chiffrees == 0
        assert "mistral/inconnu" in bilan.modeles_sans_tarif
        assert {l.cout_micro_eur for l in test_db.query(ConsoTokens).all()} == {None}

    def test_us309_ca8_utilise_l_unite_de_la_ligne(self, test_db):
        _ajouter(test_db, appel_type="voix", modele="mistral/voxtral-mini-tts-3-0", unite="caractere",
                 tokens_in=7, tokens_out=0, tokens_cache=0)
        chiffrage.rejouer_cout(test_db, tarifs.GRILLE, appliquer=True)
        assert test_db.query(ConsoTokens).one().cout_micro_eur == 82

    def test_us309_ca8_l_outil_est_en_simulation_par_defaut(self, test_db, capsys):
        from tools import chiffrer_historique
        _ajouter(test_db)
        with patch.object(chiffrer_historique, "SessionLocal", lambda: test_db), \
                patch.object(test_db, "close"), patch.object(tarifs, "GRILLE", GRILLE_GHERKIN):
            assert chiffrer_historique.main([]) == 0
        sortie = capsys.readouterr().out
        assert "SIMULATION" in sortie and "examinées : 1" in sortie
        test_db.expire_all()
        assert test_db.query(ConsoTokens).one().tarif_version is None

    def test_us309_ca8_l_outil_ecrit_avec_appliquer_et_une_grille_donnee(self, test_db, tmp_path, capsys):
        from tools import chiffrer_historique
        chemin = tmp_path / "grille.json"
        chemin.write_text(json.dumps(_grille_gherkin("2026-12", facteur=2)), encoding="utf-8")
        _ajouter(test_db)
        with patch.object(chiffrer_historique, "SessionLocal", lambda: test_db), patch.object(test_db, "close"):
            assert chiffrer_historique.main(["--grille", str(chemin), "--appliquer"]) == 0
        assert "ÉCRITURE" in capsys.readouterr().out
        test_db.expire_all()
        ligne = test_db.query(ConsoTokens).one()
        assert (ligne.cout_micro_eur, ligne.tarif_version) == (550, "2026-12")

    def test_us309_ca8_l_outil_refuse_une_grille_mal_formee(self, tmp_path, capsys):
        from tools import chiffrer_historique
        chemin = tmp_path / "cassee.json"
        chemin.write_text("{}", encoding="utf-8")
        assert chiffrer_historique.main(["--grille", str(chemin)]) == 2
        assert "version" in capsys.readouterr().out

    def test_us309_ca8_l_outil_n_appelle_aucun_modele(self):
        import tools.audit_appels_llm as audit
        assert "chiffrer_historique.py" not in audit.outils_appelant_un_modele()


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — tout modèle par défaut de app/config.py est dans la grille
# ═════════════════════════════════════════════════════════════════════════════
def _modeles_par_defaut_du_depot() -> dict[str, str]:
    """Les modèles retenus quand AUCUNE variable n'est posée : un processus neuf, environnement vide."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("GROQ_", "FOURNISSEUR"))}
    env.update({"APP_ENV": "pytest_isole_us309", "GROQ_API_KEY": "x", "TELEGRAM_BOT_TOKEN": "x",
                "DATABASE_URL": "sqlite://", "JWT_SECRET": "x"})
    code = (
        "import sys; sys.path.insert(0, %r); import json; from app import config;"
        "print(json.dumps({'GROQ_MODEL': config.GROQ_MODEL, 'GROQ_WHISPER_MODEL': config.GROQ_WHISPER_MODEL,"
        "**{'GROQ_MODEL_' + t.upper(): m for t, m in config.GROQ_MODELE_PAR_TYPE.items()}}))"
    ) % str(RACINE)
    sortie = subprocess.run([sys.executable, "-I", "-X", "utf8", "-c", code], cwd=RACINE / "tests", env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert sortie.returncode == 0, sortie.stderr[-400:]
    return json.loads(sortie.stdout.strip().splitlines()[-1])


class TestCA9ModelesParDefaut:

    def test_us309_ca9_chaque_modele_par_defaut_est_dans_la_grille(self):
        manquants = []
        for variable, modele in _modeles_par_defaut_du_depot().items():
            fournisseur, cle = fournisseur_et_modele(modele)
            if tarifs.GRILLE.tarif(fournisseur, cle) is None:
                manquants.append(f"{variable}={modele}")
        assert not manquants, f"modèles par défaut absents de data/tarifs/tarifs_llm.json : {manquants}"

    def test_us309_ca9_le_test_voit_bien_un_modele_absent(self):
        """Garde-fou : sans lui, le test précédent pourrait ne rien vérifier."""
        fournisseur, cle = fournisseur_et_modele("mistral/modele-ajoute-sans-tarif")
        assert tarifs.GRILLE.tarif(fournisseur, cle) is None

    def test_us309_ca9_les_modeles_proposes_par_env_example_sont_dans_la_grille(self):
        proposes = {}
        for ligne in (RACINE / ".env.example").read_text(encoding="utf-8").splitlines():
            nom, egal, valeur = ligne.lstrip("# ").strip().partition("=")
            if egal and valeur and (nom in {"GROQ_MODEL", "GROQ_WHISPER_MODEL"} or nom.startswith("GROQ_MODEL_")):
                proposes[nom] = valeur.strip()
        assert proposes
        # Exemples de BASCULE vers un autre fournisseur ou un système agentique, laissés en commentaire
        # dans `.env.example` : non tarifés tant qu'ils ne sont pas adoptés. Un exemple ajouté sans
        # tarif ni exception explicite ici fait échouer ce test.
        exemples_non_adoptes = {"oai/gpt-4o-mini-transcribe", "oai/gpt-4o-mini-tts", "groq/compound-mini"}
        manquants = [f"{n}={m}" for n, m in proposes.items()
                     if m not in exemples_non_adoptes
                     and tarifs.GRILLE.tarif(*fournisseur_et_modele(m)) is None]
        assert not manquants, manquants

    def test_us309_ca9_chaque_type_d_appel_a_une_unite_qui_correspond_au_tarif_de_son_modele_par_defaut(self):
        defauts = _modeles_par_defaut_du_depot()
        for type_appel in ("dictee", "voix"):
            tarif = tarifs.GRILLE.tarif(*fournisseur_et_modele(defauts[f"GROQ_MODEL_{type_appel.upper()}"]))
            assert tarif.unite == passerelle.unite_pour(type_appel)


class TestFournisseurDuModele:

    @pytest.mark.parametrize("modele,attendu", [
        ("mistral/mistral-small-2603", ("mistral", "mistral-small-2603")),
        ("openai/gpt-oss-120b", ("groq", "openai/gpt-oss-120b")),
        ("whisper-large-v3-turbo", ("groq", "whisper-large-v3-turbo")),
        ("groq/compound-mini", ("groq", "groq/compound-mini")),
    ])
    def test_us309_fournisseur_et_modele(self, modele, attendu):
        assert fournisseur_et_modele(modele) == attendu

    def test_us309_fournisseur_compatible_declare(self):
        assert fournisseur_et_modele("oai/gpt-4o-mini-tts", {"oai"}) == ("oai", "gpt-4o-mini-tts")
        assert fournisseur_et_modele("oai/gpt-4o-mini-tts") == ("groq", "oai/gpt-4o-mini-tts")

    def test_us309_la_regle_est_celle_de_la_passerelle(self):
        for modele in ("mistral/x", "openai/gpt-oss-120b", "whisper-large-v3-turbo"):
            fournisseur, cle = fournisseur_et_modele(modele)
            assert passerelle._modele_envoye(modele) == (cle if fournisseur != "groq" else modele)
