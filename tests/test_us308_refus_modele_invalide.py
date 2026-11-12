"""
tests/test_us308_refus_modele_invalide.py — US-308 : refuser un nom de modèle invalide au démarrage

Le 10/11/2026, un commentaire en fin de ligne de `.env` avait été lu comme partie du nom du
modèle de la voix. Les variables de modèle sont désormais validées au chargement de
`app/config.py` ; une valeur invalide arrête le démarrage.

Aucun appel réseau, aucune base : la validation est pure.
"""
from __future__ import annotations

import importlib
import os
import pathlib
import subprocess
import sys

import pytest

from app import config

# `tests/test_us044_authentification_jwt.py` recharge `app.config` (importlib.reload) : classes et
# fonctions sont redéfinies. On lit donc TOUJOURS `config.<nom>`, jamais un nom importé une fois.
RACINE = pathlib.Path(__file__).resolve().parent.parent
PREFIXES = config.NOMS_FOURNISSEURS_RESERVES | {"oai"}
FAUTIF = "mistral/voxtral-mini-tts-3-0            (voix : texte → MP3)"


def _controler(**variables) -> None:
    """Contrôle `variables` comme si elles étaient l'environnement du processus."""
    config.controler_modeles(variables)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — chaque variable de modèle est validée au chargement
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Regles:

    @pytest.mark.parametrize("valeur,fragment", [
        ("modele avec espace", "espace"),
        ("modele\tavec-tabulation", "espace"),
        ("mistral/x(commentaire)", "parenthèse"),
        ("mistral/x)", "parenthèse"),
        ("mistral/x#note", "#"),
        ("mistral/x→y", "caractère interdit"),
        ("mistral/x;rm", "caractère interdit"),
        ("-commence-par-un-tiret", "caractère interdit"),
        ("a" * (config.LONGUEUR_MODELE_MAX + 1), "caractères (maximum"),
        ("inconnu/modele", "préfixe"),
        ("", "vide"),
    ])
    def test_us308_ca1_valeurs_refusees(self, valeur, fragment):
        motif = config.motif_modele_invalide(valeur, PREFIXES)
        assert motif and fragment in motif

    @pytest.mark.parametrize("valeur", [
        "openai/gpt-oss-120b", "whisper-large-v3-turbo", "mistral/ministral-8b-latest",
        "mistral/mistral-small-2603", "mistral/voxtral-mini-tts-3-0", "groq/compound-mini",
        "meta-llama/llama-4-scout-17b-16e-instruct", "oai/gpt-4o-mini-tts", "modele-sans-prefixe",
        "a" * config.LONGUEUR_MODELE_MAX,
    ])
    def test_us308_ca1_valeurs_acceptees(self, valeur):
        assert config.motif_modele_invalide(valeur, PREFIXES) is None

    def test_us308_ca1_prefixe_absent_accepte_prefixe_declare_accepte(self):
        assert config.motif_modele_invalide("gpt-4o", set()) is None
        assert config.motif_modele_invalide("oai/gpt-4o", {"oai"}) is None
        assert config.motif_modele_invalide("oai/gpt-4o", set()) is not None

    @pytest.mark.parametrize("nom", [
        "GROQ_MODEL", "GROQ_WHISPER_MODEL", "GROQ_MODEL_AGENT", "GROQ_MODEL_CLASSIFICATION",
        "GROQ_MODEL_TRANSCRIPTION", "GROQ_MODEL_DICTEE", "GROQ_MODEL_VOIX", "GROQ_MODEL_ORAL",
        "GROQ_MODEL_COMPAGNON_SIGNAL", "GROQ_MODEL_ANALYSE",
    ])
    def test_us308_ca1_chaque_variable_est_validee(self, nom):
        with pytest.raises(config.ConfigurationInvalideError) as e:
            _controler(**{nom: FAUTIF})
        assert nom in str(e.value)

    def test_us308_ca1_une_variable_de_type_future_est_validee_aussi(self):
        """Un type d'appel ajouté plus tard (`GROQ_MODEL_<NOUVEAU>`) est couvert sans toucher ce code."""
        with pytest.raises(config.ConfigurationInvalideError, match="GROQ_MODEL_NOUVEAU"):
            _controler(GROQ_MODEL_NOUVEAU="x (note)")

    def test_us308_ca1_les_blancs_de_bord_ne_sont_pas_une_faute(self):
        assert config.variables_de_modele({"GROQ_MODEL": "  openai/gpt-oss-120b \n"}) == {"GROQ_MODEL": "openai/gpt-oss-120b"}
        _controler(GROQ_MODEL="  openai/gpt-oss-120b ")

    def test_us308_ca1_une_variable_vide_vaut_non_renseignee(self):
        assert config.variables_de_modele({"GROQ_MODEL_AGENT": "", "GROQ_MODEL": "  "}) == {}
        _controler(GROQ_MODEL_AGENT="")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — une valeur invalide arrête le démarrage, avec la variable et la valeur lue
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Arret:

    def test_us308_ca2_le_message_nomme_la_variable_et_montre_la_valeur(self):
        with pytest.raises(config.ConfigurationInvalideError) as e:
            _controler(GROQ_MODEL_VOIX=FAUTIF)
        message = str(e.value)
        assert "GROQ_MODEL_VOIX" in message
        assert f'valeur lue : "{FAUTIF}"' in message
        assert "démarrage s'arrête" in message

    def test_us308_ca2_toutes_les_fautes_sont_dites_d_un_coup(self):
        with pytest.raises(config.ConfigurationInvalideError) as e:
            _controler(GROQ_MODEL_VOIX=FAUTIF, GROQ_MODEL_AGENT="a b")
        assert "GROQ_MODEL_VOIX" in str(e.value) and "GROQ_MODEL_AGENT" in str(e.value)

    def test_us308_ca2_la_valeur_corrigee_demarre(self):
        _controler(GROQ_MODEL_VOIX="mistral/voxtral-mini-tts-3-0")

    def _lancer(self, tmp_path, **env_supplementaire):
        """Importe VRAIMENT `app.config` dans un processus neuf, comme le fait `python -m app.bot`."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GROQ_", "FOURNISSEUR"))}
        env.update({
            "APP_ENV": "pytest_isole_us308", "GROQ_API_KEY": "x", "TELEGRAM_BOT_TOKEN": "x",
            "DATABASE_URL": "sqlite://", "JWT_SECRET": "x", "PYTHONIOENCODING": "utf-8",
        })
        env.update(env_supplementaire)
        return subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-c", f"import sys; sys.path.insert(0, {str(RACINE)!r}); import app.config"],
            cwd=tmp_path, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )

    def test_us308_ca2_le_chargement_de_la_config_s_arrete_vraiment(self, tmp_path):
        """Scénario Gherkin : un `.env` fautif → l'import de `app.config` (donc le bot et l'API) échoue."""
        resultat = self._lancer(tmp_path, GROQ_MODEL_VOIX=FAUTIF)
        assert resultat.returncode != 0
        assert "config.ConfigurationInvalideError" in resultat.stderr
        assert "GROQ_MODEL_VOIX" in resultat.stderr
        assert f'"{FAUTIF}"' in resultat.stderr

    def test_us308_ca2_la_config_valide_se_charge(self, tmp_path):
        resultat = self._lancer(tmp_path, GROQ_MODEL_VOIX="mistral/voxtral-mini-tts-3-0")
        assert resultat.returncode == 0, resultat.stderr[-500:]

    def test_us308_ca2_le_bot_et_l_api_importent_la_meme_config(self):
        """Le bot et l'API chargent `app.config` : une seule validation les arrête tous les deux."""
        api = (RACINE / "app" / "api" / "main.py").read_text(encoding="utf-8")
        bot = "\n".join(f.read_text(encoding="utf-8") for f in (RACINE / "app" / "bot").glob("*.py"))
        for source in (api, bot):
            assert "from app.config import" in source or "from app import config" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — .env.example : commentaires sur une ligne à part, et il le dit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3EnvExample:

    def test_us308_ca3_le_fichier_le_dit_en_tete(self):
        tete = "\n".join((RACINE / ".env.example").read_text(encoding="utf-8").splitlines()[:12])
        assert "UN COMMENTAIRE VA SUR UNE LIGNE À PART" in tete
        assert "ARRÊTE le démarrage" in tete

    def test_us308_ca3_aucun_commentaire_en_fin_de_ligne_de_valeur(self):
        fautives = []
        for numero, ligne in enumerate((RACINE / ".env.example").read_text(encoding="utf-8").splitlines(), 1):
            brut = ligne.lstrip("# ").strip()
            nom, egal, valeur = brut.partition("=")
            if not egal or not nom.replace("_", "").isalnum() or not nom.isupper():
                continue   # ligne de texte, pas une affectation
            if "#" in valeur or "(" in valeur:
                fautives.append(f"{numero}: {ligne}")
        assert fautives == []

    def test_us308_ca3_les_modeles_de_l_exemple_sont_valides(self):
        valeurs = {}
        for ligne in (RACINE / ".env.example").read_text(encoding="utf-8").splitlines():
            nom, egal, valeur = ligne.lstrip("# ").strip().partition("=")
            if egal and (nom == "GROQ_MODEL" or nom == "GROQ_WHISPER_MODEL" or nom.startswith("GROQ_MODEL_")) and valeur:
                valeurs[nom] = valeur
        assert len(valeurs) >= 6
        assert config.erreurs_modeles(valeurs, PREFIXES) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — le contrôle de configuration de app/config.py couvre ces variables
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4EtatDeLaConfiguration:

    def test_us308_ca4_l_etat_de_configuration_liste_chaque_modele_et_sa_validite(self):
        lignes = "\n".join(config.etat_configuration())
        for nom in ("GROQ_MODEL", "GROQ_WHISPER_MODEL", "GROQ_MODEL_AGENT", "GROQ_MODEL_DICTEE", "GROQ_MODEL_VOIX"):
            ligne = next(l for l in lignes.splitlines() if l.strip().startswith(nom + " "))
            assert "✓ format valide" in ligne, ligne

    def test_us308_ca4_une_valeur_invalide_est_signalee_dans_l_etat(self, monkeypatch):
        monkeypatch.setitem(config.GROQ_MODELE_PAR_TYPE, "voix", FAUTIF)
        lignes = "\n".join(config.etat_configuration())
        assert "INVALIDE" in lignes

    def test_us308_ca4_le_rognage_silencieux_n_existe_plus(self):
        assert not hasattr(config, "nettoyer_modele") and not hasattr(config, "MODELES_ROGNES")


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — le refus de « modele   (commentaire) » et l'acceptation des défauts du dépôt
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Tests:

    def test_us308_ca5_modele_suivi_d_un_commentaire_est_refuse(self):
        with pytest.raises(config.ConfigurationInvalideError):
            _controler(GROQ_MODEL="modele            (commentaire)")

    def test_us308_ca5_chaque_valeur_par_defaut_du_depot_est_acceptee(self):
        """Les défauts écrits dans le code de `app/config.py` : aucune variable posée."""
        env = {k: v for k, v in os.environ.items() if not k.startswith(("GROQ_", "FOURNISSEUR"))}
        env.update({"APP_ENV": "pytest_isole_us308", "GROQ_API_KEY": "x", "TELEGRAM_BOT_TOKEN": "x",
                    "DATABASE_URL": "sqlite://", "JWT_SECRET": "x", "PYTHONIOENCODING": "utf-8"})
        sortie = subprocess.run(
            [sys.executable, "-I", "-X", "utf8", "-c",
             f"import sys; sys.path.insert(0, {str(RACINE)!r}); import json; from app import config;"
             "print(json.dumps({'GROQ_MODEL': config.GROQ_MODEL, 'GROQ_WHISPER_MODEL': config.GROQ_WHISPER_MODEL,"
             "**{'GROQ_MODEL_' + t.upper(): m for t, m in config.GROQ_MODELE_PAR_TYPE.items()}}))"],
            cwd=RACINE / "tests", env=env, capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
        assert sortie.returncode == 0, sortie.stderr[-500:]
        import json
        par_defaut = json.loads(sortie.stdout.strip().splitlines()[-1])
        assert {"GROQ_MODEL", "GROQ_WHISPER_MODEL", "GROQ_MODEL_VOIX", "GROQ_MODEL_DICTEE"} <= set(par_defaut)
        assert config.erreurs_modeles(par_defaut, config.NOMS_FOURNISSEURS_RESERVES) == []

    def test_us308_ca5_les_valeurs_du_processus_de_test_sont_valides(self):
        config.controler_modeles(os.environ)
