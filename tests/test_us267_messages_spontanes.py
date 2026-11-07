"""
tests/test_us267_messages_spontanes.py — Les messages spontanés dans Telegram, sans harceler [US-267]
====================================================================================================
Le compagnon écrit de lui-même quand il gèle cette nuit ou qu'une levée n'est pas notée, au
bon moment et sur les sujets choisis. Les règles du distributeur sont des fonctions pures,
testées sans base ni modèle (CA12) ; le passage en base tourne sur SQLite en mémoire, avec
Telegram et le modèle simulés : aucun appel réseau.
"""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import config
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import distributeur as regles
from app.services.compagnon import distribution
from app.services.compagnon import proactivite
from app.services.compagnon import propositions as svc_propositions
from app.services.compagnon import redaction_signal as redaction
from app.services.compagnon import reponse_signal
from app.services.compagnon import signaux as svc_signaux
from app.services.compagnon import veilleur_passage as passage
from app.services.compagnon.redaction_signal import SignalARediger
from app.services.compagnon.veilleur import Signal
from app.services.context import TenantContext
from database.db import Base
from database.models import EnvoiSignal, MessageSpontane, Potager, PotagerMembre, SignalVeilleur, User

RACINE = Path(__file__).resolve().parent.parent
JOUR = datetime(2026, 10, 30)
A_18H = JOUR.replace(hour=18)
A_22H = JOUR.replace(hour=22)
DEMAIN_5H = (JOUR + timedelta(days=1)).replace(hour=5)
DEMAIN_8H = (JOUR + timedelta(days=1)).replace(hour=8)
DEFAUT = regles.Reglages()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 → CA5 — Les règles pures du distributeur (CA12 : sans base, sans modèle)
# ═════════════════════════════════════════════════════════════════════════════
class TestGherkinSilence:
    """Given un gel expirant à 5 h, une plage de silence de 21 h à 8 h."""

    def test_detecte_a_22h_le_message_ne_part_pas_pendant_la_plage(self):
        decision = regles.planifier("meteo", DEMAIN_5H, DEFAUT, A_22H)
        assert decision.etat == regles.ETAT_IGNORE
        assert decision.motif == regles.MOTIF_EXPIRE_PENDANT_SILENCE

    def test_detecte_a_18h_le_message_part_a_18h(self):
        decision = regles.planifier("meteo", DEMAIN_5H, DEFAUT, A_18H)
        assert (decision.etat, decision.mode, decision.envoyer_le) == (regles.ETAT_EN_ATTENTE, "immediat", A_18H)


class TestCA1ThemeCoupe:
    def test_un_signal_d_un_theme_coupe_est_consomme_sans_envoi(self):
        reglages = regles.reglages_depuis({"meteo": {"mode": "coupe"}})
        decision = regles.planifier("meteo", DEMAIN_8H, reglages, A_18H)
        assert (decision.etat, decision.motif) == (regles.ETAT_IGNORE, regles.MOTIF_THEME_COUPE)

    def test_un_signal_deja_expire_n_est_pas_envoye(self):
        decision = regles.planifier("meteo", A_18H, DEFAUT, A_18H)
        assert (decision.etat, decision.motif) == (regles.ETAT_IGNORE, regles.MOTIF_EXPIRE)


class TestCA2ImmediatEtRegroupement:
    def test_un_theme_immediat_hors_silence_part_tout_de_suite(self):
        midi = JOUR.replace(hour=12)
        assert regles.planifier("meteo", DEMAIN_8H, DEFAUT, midi).envoyer_le == midi

    def test_ce_qui_tombe_dans_la_meme_demi_heure_attend_la_fin_de_la_demi_heure(self):
        dernier = JOUR.replace(hour=12)
        maintenant = dernier + timedelta(minutes=10)
        assert regles.report_de_regroupement(dernier, maintenant, DEFAUT, [DEMAIN_8H]) == dernier + timedelta(minutes=30)

    def test_passee_la_demi_heure_rien_n_attend(self):
        dernier = JOUR.replace(hour=12)
        assert regles.report_de_regroupement(dernier, dernier + timedelta(minutes=31), DEFAUT) is None
        assert regles.report_de_regroupement(None, dernier, DEFAUT) is None

    def test_on_n_attend_jamais_au_prix_d_un_signal_perdu(self):
        # La fin de la demi-heure tombe dans le silence (21 h) : il part maintenant.
        dernier = JOUR.replace(hour=20, minute=40)
        assert regles.report_de_regroupement(dernier, dernier + timedelta(minutes=5), DEFAUT, [DEMAIN_8H]) is None
        # Un signal qui expire avant la fin de la demi-heure : il part maintenant.
        dernier = JOUR.replace(hour=12)
        assert regles.report_de_regroupement(
            dernier, dernier + timedelta(minutes=5), DEFAUT, [dernier + timedelta(minutes=20)]) is None


class TestCA3PlageDeSilence:
    def test_en_plage_de_silence_l_envoi_part_a_la_fin_de_la_plage(self):
        decision = regles.planifier("meteo", DEMAIN_8H + timedelta(hours=2), DEFAUT, A_22H)
        assert (decision.etat, decision.envoyer_le) == (regles.ETAT_EN_ATTENTE, DEMAIN_8H)

    def test_apres_minuit_la_fin_de_la_plage_est_le_matin_meme(self):
        a_2h = (JOUR + timedelta(days=1)).replace(hour=2)
        assert regles.fin_du_silence(a_2h, DEFAUT) == DEMAIN_8H

    def test_un_signal_qui_expirerait_avant_le_point_du_matin_part_avant_la_plage(self):
        # Les suivis sont au point du matin par défaut ; celui-ci expire à 5 h : il part à 18 h.
        decision = regles.planifier("suivis", DEMAIN_5H, DEFAUT, A_18H)
        assert (decision.etat, decision.envoyer_le) == (regles.ETAT_EN_ATTENTE, A_18H)

    def test_la_plage_se_regle_et_peut_etre_supprimee(self):
        sans = regles.reglages_depuis(None, 0, 0)
        assert not regles.en_silence(A_22H, sans)
        assert regles.planifier("meteo", DEMAIN_5H, sans, A_22H).envoyer_le == A_22H
        journee = regles.reglages_depuis(None, 13, 14)
        assert regles.en_silence(JOUR.replace(hour=13, minute=30), journee)
        assert not regles.en_silence(JOUR.replace(hour=14), journee)
        assert regles.en_silence(JOUR.replace(hour=21), DEFAUT) and not regles.en_silence(DEMAIN_8H, DEFAUT)


class TestCA4PointDuMatin:
    def test_un_theme_resume_rejoint_le_point_du_matin(self):
        decision = regles.planifier("echeances", DEMAIN_8H + timedelta(days=5), DEFAUT, JOUR.replace(hour=14))
        assert (decision.mode, decision.envoyer_le) == ("resume", DEMAIN_8H)

    def test_l_heure_du_point_du_matin_se_regle(self):
        reglages = regles.reglages_depuis(None, heure_resume=9)
        assert regles.prochain_point_du_matin(JOUR.replace(hour=14), reglages) == DEMAIN_8H.replace(hour=9)

    def test_un_point_regle_dans_la_plage_attend_sa_fin(self):
        reglages = regles.reglages_depuis(None, heure_resume=7)
        assert regles.prochain_point_du_matin(JOUR.replace(hour=14), reglages) == DEMAIN_8H

    def test_passe_l_heure_le_point_est_celui_du_lendemain(self):
        assert regles.prochain_point_du_matin(JOUR.replace(hour=8, minute=30), DEFAUT) == DEMAIN_8H


class TestCA5BasculeApresTroisMessagesSansReaction:
    def test_trois_messages_sans_reaction_font_basculer(self):
        assert regles.doit_basculer("meteo", [None, None, None])
        assert not regles.doit_basculer("meteo", [None, None])
        assert not regles.doit_basculer("meteo", [None, A_18H, None])

    def test_la_bascule_envoie_le_signal_au_point_du_matin_et_l_annonce(self):
        decision = regles.planifier("meteo", DEMAIN_8H + timedelta(hours=2), DEFAUT, JOUR.replace(hour=14),
                                    sans_reaction=True)
        assert (decision.mode, decision.annonce_bascule, decision.envoyer_le) == ("resume", True, DEMAIN_8H)

    def test_le_bilan_du_dimanche_ne_bascule_jamais(self):
        assert not regles.doit_basculer("resume", [None, None, None])

    def test_la_bascule_s_ecrit_comme_automatique(self):
        ecrit = regles.proactivite_avec(None, "meteo", "resume", A_18H, auto=True)
        relu = regles.reglages_depuis(ecrit)
        assert relu.mode("meteo") == "resume" and "meteo" in relu.automatiques
        assert relu.depuis_le("meteo") == A_18H


class TestReglages:
    def test_defauts_du_cadrage(self):
        assert [DEFAUT.mode(t) for t in ("meteo", "rappels", "echeances", "suivis", "suggestions", "resume")] == [
            "immediat", "immediat", "resume", "resume", "resume", "immediat"]
        assert (DEFAUT.silence_debut, DEFAUT.silence_fin, DEFAUT.heure_resume) == (21, 8, 8)

    def test_une_valeur_illisible_retombe_sur_le_defaut_jamais_sur_coupe(self):
        relu = regles.reglages_depuis({"meteo": {"mode": "n'importe"}, "inconnu": "coupe"}, "x", 99, None)
        assert relu.mode("meteo") == "immediat"
        assert (relu.silence_debut, relu.silence_fin, relu.heure_resume) == (21, 8, 8)


def _modules_importes(fichier: Path) -> list[str]:
    modules: list[str] = []
    for noeud in ast.walk(ast.parse(fichier.read_text(encoding="utf-8"))):
        if isinstance(noeud, ast.Import):
            modules.extend(alias.name for alias in noeud.names)
        elif isinstance(noeud, ast.ImportFrom) and noeud.module:
            modules.append(noeud.module)
    return modules


@pytest.mark.parametrize("nom", ["distributeur.py", "reponse_signal.py", "proactivite.py"])
def test_ca12_les_regles_ne_parlent_jamais_au_modele(nom):
    modules = _modules_importes(RACINE / "app/services/compagnon" / nom)
    fautifs = [m for m in modules if m == "llm" or m.startswith("llm.") or m.startswith("app.services.agent")]
    assert not fautifs, f"{nom} importe {fautifs}"


@pytest.mark.parametrize("nom", ["distributeur.py", "distribution.py", "redaction_signal.py", "reponse_signal.py"])
def test_r8_aucun_module_du_distributeur_n_atteint_un_executeur(nom):
    modules = _modules_importes(RACINE / "app/services/compagnon" / nom)
    assert not [m for m in modules if "executeurs" in m or m.startswith("app.bot")]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — La rédaction par l'agent, et le gabarit du code
# ═════════════════════════════════════════════════════════════════════════════
def _gel(**donnees) -> SignalARediger:
    base = {"jour": "2026-10-31", "temp_min": -2.0, "parcelle_id": 12, "parcelle": "Planche Est",
            "cultures": [{"culture": "laitue", "variete": None, "nb_plants": 6.0, "unite": "plants", "seuil_c": -1.0}]}
    base.update(donnees)
    return SignalARediger("meteo", "gel:2026-10-31:parcelle-12", DEMAIN_8H, base, signal_id=1, envoi_id=11)


def _levee(numero: int = 14, envoi_id: int = 21) -> SignalARediger:
    return SignalARediger("suivis", f"levee:lot-{numero}", DEMAIN_8H + timedelta(days=5), {
        "lot_id": "x", "numero": numero, "culture": "tomate", "variete": "cœur de bœuf", "date_semis": "2026-10-18",
        "graines_en_attente": 24, "duree_levee_max_jours": 10, "levee_attendue_le": "2026-10-28",
        "jours_depuis_semis": 12,
    }, signal_id=2, envoi_id=envoi_id)


CTX = TenantContext(user_id=1, potager_id=1)


class TestCA6Redaction:
    def test_le_gabarit_dit_les_faits_du_signal(self):
        texte = redaction.gabarit(_gel(), JOUR.date())
        assert "demain" in texte and "-2 °C" in texte and "6 plants de laitue" in texte and "Planche Est" in texte
        assert texte.endswith(redaction.QUESTIONS["gel"])
        assert redaction.gabarit(_levee(), JOUR.date()).endswith("Ça a germé ?")

    def test_chaque_detecteur_a_son_gabarit(self):
        for cle, theme, donnees in (
            ("canicule:2026-10-31:parcelle-1", "meteo", {"jour": "2026-10-31", "temp_max": 34.0}),
            ("pluie:2026-10-31", "meteo", {"jour": "2026-10-31", "precipitations_mm": 25.0}),
            ("secheresse:aucun-arrosage:2026-S44", "suivis", {"dernier_arrosage": None, "jours_sans_arrosage_min": 5}),
            ("repiquer:lot-3", "echeances", {"numero": 3, "culture": "chou", "au": "2026-11-05", "en_retard": False}),
            ("mettre_en_terre:lot-3", "echeances", {"numero": 3, "culture": "chou", "au": "2026-10-20", "en_retard": True}),
            ("recolte:parcelle-1:radis:2026-09-01", "echeances", {"culture": "radis", "parcelle": "Nord", "age_jours": 60}),
            ("semis:2026-11", "suggestions", {"cultures": [{"culture": "ail"}, {"culture": "fève"}]}),
            ("bilan:2026-S44", "resume", {"nb_gestes": 4, "par_type": {"arrosage": 3, "recolte": 1},
                                          "recoltes": [{"culture": "radis", "quantite": 1.5, "unite": "kg"}]}),
        ):
            texte = redaction.gabarit(SignalARediger(theme, cle, DEMAIN_8H, donnees), JOUR.date())
            assert texte and "None" not in texte and "?" not in texte.replace(" ?", ""), (cle, texte)

    def test_un_texte_fidele_du_modele_part(self):
        fidele = "Éric, il va geler demain à l'aube : -2 °C. Tes 6 laitues de la Planche Est sont dehors. " \
                 "Tu veux que je note la pose d'un voile ?"
        with patch("llm.passerelle.appeler_chat", return_value=SimpleNamespace(texte=fidele)) as appel:
            rendu = redaction.composer([_gel()], CTX, maintenant=A_18H, prenom="Éric")
        assert rendu.redige and fidele in rendu.texte
        assert appel.call_args.kwargs["appel_type"] == "compagnon_signal"

    @pytest.mark.parametrize("texte_modele", [
        "Gel demain : -2 °C, soit 83 % de risque pour tes 6 laitues.",   # un chiffre absent du signal
        "J'ai noté la pose du voile sur la Planche Est.",                # une action annoncée comme faite
        "",                                                              # rien
        "x" * (redaction.LONGUEUR_MAX + 1),                              # trop long
    ])
    def test_un_texte_infidele_laisse_partir_le_gabarit(self, texte_modele):
        with patch("llm.passerelle.appeler_chat", return_value=SimpleNamespace(texte=texte_modele)):
            rendu = redaction.composer([_gel()], CTX, maintenant=A_18H)
        assert not rendu.redige and redaction.gabarit(_gel(), JOUR.date()) in rendu.texte

    def test_une_panne_du_modele_laisse_partir_le_gabarit(self):
        with patch("llm.passerelle.appeler_chat", side_effect=RuntimeError("panne")):
            rendu = redaction.composer([_gel()], CTX, maintenant=A_18H)
        assert not rendu.redige and "-2 °C" in rendu.texte

    def test_au_dela_de_six_signaux_le_gabarit_part_sans_appel(self):
        with patch("llm.passerelle.appeler_chat") as appel:
            rendu = redaction.composer([_levee(n, n) for n in range(7)], CTX, maintenant=A_18H, resume=True)
        appel.assert_not_called()
        assert rendu.texte.startswith("☀️ Le point du matin")

    def test_la_bascule_se_dit_toujours_avec_le_texte_du_code(self):
        rendu = redaction.composer([_gel()], CTX, maintenant=A_18H, avec_modele=False, bascules=["meteo"])
        assert "la météo" in rendu.texte and "point du matin" in rendu.texte and "/profil" in rendu.texte

    def test_le_moment_est_calcule_par_le_code_pas_par_le_modele(self):
        faits = redaction.donnees_pour_le_modele([_gel()], JOUR.date())
        assert '"quand": "demain"' in faits and '"question"' in faits

    def test_type_d_appel_distinct_dans_la_passerelle(self):
        from llm import passerelle

        assert passerelle.TYPE_COMPAGNON_SIGNAL == "compagnon_signal" in passerelle.TYPES_APPEL
        assert config.GROQ_MODELE_PAR_TYPE["compagnon_signal"]


# ═════════════════════════════════════════════════════════════════════════════
# CA7, CA8 — Les boutons et la réponse
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Boutons:
    def test_les_boutons_ouvrent_une_phrase_de_geste_jamais_une_ecriture(self):
        assert reponse_signal.phrase_du_geste(_gel(), "voile") == "j'ai posé un voile de protection sur Planche Est"
        assert reponse_signal.phrase_du_geste(_levee(), "levee") == "levée du lot 14"
        assert reponse_signal.phrase_du_geste(_gel(), "plus_tard") is None

    def test_les_callbacks_tiennent_dans_la_limite_telegram(self):
        rangees = reponse_signal.boutons(123456, [_gel(), _levee(envoi_id=987654321)])
        donnees = [b.callback for r in rangees for b in r]
        assert all(len(d.encode()) <= 64 for d in donnees)
        assert donnees[-1] == "spon:123456:0:reglages"
        assert reponse_signal.lire_callback("spon:123456:987654321:levee") == (123456, 987654321, "levee")
        assert reponse_signal.lire_callback("sug:oui") is None

    def test_dans_un_message_groupe_chaque_bouton_nomme_son_sujet(self):
        rangees = reponse_signal.boutons(1, [_gel(), _levee()])
        assert "Planche Est" in rangees[0][0].libelle and "lot 14" in rangees[1][0].libelle


class TestCA8Reponse:
    def test_gherkin_oui_environ_20_sur_24_devient_la_levee_du_lot(self):
        assert reponse_signal.reformuler([_levee()], "oui environ 20 sur 24") == "levée du lot 14 : 20"

    @pytest.mark.parametrize("texte", ["pas encore", "non rien n'a levé", "aucune", "zéro"])
    def test_une_negation_n_ecrit_rien(self, texte):
        assert reponse_signal.reformuler([_levee()], texte) is None

    def test_une_longue_phrase_passe_telle_quelle_a_l_agent(self):
        texte = "oui mais il y a des limaces partout sur la planche sud depuis lundi dernier"
        assert reponse_signal.reformuler([_levee()], texte) is None

    def test_un_oui_au_gel_propose_le_voile(self):
        assert reponse_signal.reformuler([_gel()], "Oui, c'est posé !") == \
            "j'ai posé un voile de protection sur Planche Est"

    def test_deux_questions_dans_le_message_rendent_un_oui_ambigu(self):
        assert reponse_signal.reformuler([_gel(), _levee()], "oui") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Réglages par phrase confirmée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9PhrasesDeReglage:
    @pytest.mark.parametrize("phrase, attendu", [
        ("arrête de me parler de la météo", ("mode", "meteo", "coupe")),
        ("ne me parle plus des rappels", ("mode", "rappels", "coupe")),
        ("regroupe la météo le matin", ("mode", "meteo", "resume")),
        ("préviens-moi tout de suite pour les levées", ("mode", "suivis", "immediat")),
        ("coupe le bilan", ("mode", "resume", "coupe")),
    ])
    def test_un_theme_et_son_mode(self, phrase, attendu):
        changement = proactivite.lire_phrase(phrase)
        assert (changement.genre, changement.theme, changement.mode) == attendu

    def test_la_plage_de_silence_et_le_point_du_matin(self):
        assert proactivite.lire_phrase("silence de 22h à 7h").en_donnees() == {"genre": "silence", "debut": 22, "fin": 7}
        assert proactivite.lire_phrase("ne m'écris pas entre 22 h et 7 h").debut == 22
        assert proactivite.lire_phrase("pas de silence").en_donnees() == {"genre": "silence", "debut": 0, "fin": 0}
        assert proactivite.lire_phrase("point du matin à 7 h").heure == 7

    @pytest.mark.parametrize("phrase", ["coupe la planche nord", "j'ai semé des radis", "silence de 25h à 7h",
                                        "quel temps fait-il ?"])
    def test_une_autre_phrase_suit_son_chemin(self, phrase):
        assert proactivite.lire_phrase(phrase) is None

    def test_le_bouton_d_un_theme_fait_tourner_les_trois_modes(self):
        assert [proactivite.mode_suivant(m) for m in ("immediat", "resume", "coupe")] == ["resume", "coupe", "immediat"]

    def test_la_proposition_dit_ce_qui_changera(self):
        assert "plus de moi-même sur la météo" in proactivite.texte_changement(proactivite.lire_phrase("coupe la météo"))
        assert "22 h et 7 h" in proactivite.texte_changement(proactivite.lire_phrase("silence de 22h à 7h"))


# ═════════════════════════════════════════════════════════════════════════════
# Le passage en base : CA2, CA4, CA5, CA8, CA10, CA11
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def base(monkeypatch):
    import database.models  # noqa: F401
    moteur = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=moteur)
    fabrique = sessionmaker(bind=moteur, autocommit=False, autoflush=False)
    for module in (svc_signaux, passage, distribution, svc_conversations):
        monkeypatch.setattr(module, "SessionLocal", fabrique)
    monkeypatch.setattr(svc_propositions, "potager_a_nommer", lambda user_id, potager_id: None)
    monkeypatch.setattr(config, "COMPAGNON_PROACTIF", True)
    db = fabrique()
    db.add_all([
        Potager(id=1, nom="Jardin", proprietaire_id=1, etat="actif", latitude=47.2, longitude=-1.55),
        User(id=1, nom="Éric", telegram_chat_id=111),
        User(id=2, nom="Sans Telegram"),
    ])
    db.flush()
    db.add_all([
        PotagerMembre(user_id=1, potager_id=1, role="owner", prenom_compagnon="Éric"),
        PotagerMembre(user_id=2, potager_id=1, role="editor"),
    ])
    db.commit()
    db.close()
    yield fabrique
    moteur.dispose()


class Telegram:
    """Le bot simulé : garde ce qui part, rend un identifiant de message."""

    def __init__(self, en_panne: bool = False):
        self.envoyes: list[tuple] = []
        self.en_panne = en_panne

    def __call__(self, chat_id, texte, boutons=None):
        if self.en_panne:
            return None
        self.envoyes.append((chat_id, texte, boutons))
        return 5000 + len(self.envoyes)


def _signal(cle: str, theme: str, expire: datetime, maintenant: datetime, **donnees) -> None:
    svc_signaux.enregistrer(1, [Signal(theme, cle, "immediat", expire, donnees)], maintenant)


def _lignes(fabrique, modele):
    db = fabrique()
    try:
        lignes = db.query(modele).order_by(modele.id).all()
        db.expunge_all()
        return lignes
    finally:
        db.close()


class TestPassageEnBase:
    def test_gherkin_le_gel_detecte_a_18h_part_a_18h_dans_telegram(self, base):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        telegram = Telegram()
        assert distribution.passer(A_18H, telegram, avec_modele=False) == {1: 1}
        (chat_id, texte, boutons), = telegram.envoyes
        assert chat_id == 111 and "-2 °C" in texte
        assert boutons[0][0] == ("🧣 Voile posé", "spon:1:1:voile")
        assert boutons[-1][0][1] == "spon:1:0:reglages"
        message, panneau = _lignes(base, MessageSpontane)
        # [CA10] L'identifiant du message Telegram est gardé pour réécrire la carte.
        assert (message.telegram_chat_id, message.telegram_message_id, message.genre) == (111, 5001, "signal")
        # [US-272 / CA9] Sans Telegram lié : le message est rangé pour le panneau seul.
        assert (panneau.user_id, panneau.telegram_chat_id, panneau.telegram_message_id) == (2, None, None)
        assert _lignes(base, SignalVeilleur)[0].etat == "envoye"
        envois = {e.user_id: e for e in _lignes(base, EnvoiSignal)}
        assert envois[1].etat == "envoye" and envois[1].message_id == message.id
        assert (envois[2].etat, envois[2].message_id) == ("envoye", panneau.id)

    def test_gherkin_le_gel_detecte_a_22h_ne_part_pas(self, base):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_22H, **_gel().donnees)
        telegram = Telegram()
        distribution.passer(A_22H, telegram, avec_modele=False)
        distribution.passer(DEMAIN_8H, telegram, avec_modele=False)
        assert telegram.envoyes == []
        assert _lignes(base, SignalVeilleur)[0].etat == "ignore"

    def test_ca11_un_signal_n_est_planifie_et_envoye_qu_une_fois(self, base):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        assert distribution.planifier_potager(1, A_18H) == 1
        assert distribution.planifier_potager(1, A_18H) == 0
        telegram = Telegram()
        distribution.envoyer_dus(1, A_18H, telegram, avec_modele=False)
        distribution.envoyer_dus(1, A_18H, telegram, avec_modele=False)
        assert len(telegram.envoyes) == 1 and len(_lignes(base, EnvoiSignal)) == 2

    def test_ca11_compagnon_proactif_eteint_rien_ne_part(self, base, monkeypatch):
        monkeypatch.setattr(config, "COMPAGNON_PROACTIF", False)
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        telegram = Telegram()
        assert distribution.passer(A_18H, telegram, avec_modele=False) == {}
        assert telegram.envoyes == [] and _lignes(base, SignalVeilleur)[0].etat == "detecte"

    def test_ca4_le_point_du_matin_regroupe_et_ne_part_jamais_vide(self, base):
        telegram = Telegram()
        distribution.passer(DEMAIN_8H, telegram, avec_modele=False)
        assert telegram.envoyes == []   # D7 : pas de point du matin sans signal
        midi = JOUR.replace(hour=12)
        _signal("levee:lot-14", "suivis", midi + timedelta(days=7), midi, **_levee().donnees)
        _signal("repiquer:lot-3", "echeances", midi + timedelta(days=7), midi,
                numero=3, culture="chou", au="2026-11-05", en_retard=False)
        distribution.passer(midi, telegram, avec_modele=False)
        assert telegram.envoyes == []
        distribution.passer(DEMAIN_8H, telegram, avec_modele=False)
        (_, texte, boutons), = telegram.envoyes
        assert texte.startswith("☀️ Le point du matin") and "Bonjour Éric" in texte
        assert "lot 14" in texte and "lot 3" in texte and len(boutons) == 3
        assert _lignes(base, MessageSpontane)[0].genre == "resume"
        assert {s.etat for s in _lignes(base, SignalVeilleur)} == {"regroupe"}

    def test_ca2_la_demi_heure_regroupe_le_message_suivant(self, base):
        midi = JOUR.replace(hour=12)
        telegram = Telegram()
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_8H, midi, **_gel().donnees)
        distribution.passer(midi, telegram, avec_modele=False)
        _signal("pluie:2026-10-31", "meteo", DEMAIN_8H + timedelta(hours=16), midi, jour="2026-10-31",
                precipitations_mm=25.0)
        _signal("canicule:2026-10-31:parcelle-1", "meteo", DEMAIN_8H + timedelta(hours=12), midi,
                jour="2026-10-31", temp_max=33.0, parcelle="Nord")
        distribution.passer(midi + timedelta(minutes=10), telegram, avec_modele=False)
        assert len(telegram.envoyes) == 1
        distribution.passer(midi + timedelta(minutes=30), telegram, avec_modele=False)
        assert len(telegram.envoyes) == 2 and "25 mm" in telegram.envoyes[1][1] and "33 °C" in telegram.envoyes[1][1]

    def test_telegram_en_panne_les_envois_reviennent_en_attente(self, base):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        distribution.passer(A_18H, Telegram(en_panne=True), avec_modele=False)
        assert [m for m in _lignes(base, MessageSpontane) if m.user_id == 1] == []
        telegram = Telegram()
        distribution.passer(A_18H + timedelta(minutes=15), telegram, avec_modele=False)
        assert len(telegram.envoyes) == 1

    def test_ca5_trois_messages_sans_reaction_font_passer_le_theme_au_point_du_matin(self, base):
        telegram = Telegram()
        for jour in range(3):
            instant = JOUR.replace(hour=12) + timedelta(days=jour)
            _signal(f"pluie:{jour}", "meteo", instant + timedelta(hours=10), instant, jour="2026-10-31",
                    precipitations_mm=25.0)
            distribution.passer(instant, telegram, avec_modele=False)
        assert len(telegram.envoyes) == 3
        instant = JOUR.replace(hour=12) + timedelta(days=3)
        _signal("pluie:3", "meteo", instant + timedelta(days=2), instant, jour="2026-11-03", precipitations_mm=30.0)
        distribution.passer(instant, telegram, avec_modele=False)
        assert len(telegram.envoyes) == 3      # il attend le point du matin
        db = base()
        membre = db.query(PotagerMembre).filter(PotagerMembre.user_id == 1).one()
        assert membre.proactivite_compagnon["meteo"]["mode"] == "resume"
        assert membre.proactivite_compagnon["meteo"]["auto"] is True
        db.close()
        distribution.passer(instant.replace(hour=8) + timedelta(days=1), telegram, avec_modele=False)
        assert "je te les regroupe désormais dans le point du matin" in telegram.envoyes[-1][1]

    def test_ca5_une_reaction_remet_le_compteur_a_zero(self, base):
        telegram = Telegram()
        for jour in range(3):
            instant = JOUR.replace(hour=12) + timedelta(days=jour)
            _signal(f"pluie:{jour}", "meteo", instant + timedelta(hours=10), instant, jour="2026-10-31",
                    precipitations_mm=25.0)
            distribution.passer(instant, telegram, avec_modele=False)
        dernier = [m for m in _lignes(base, MessageSpontane) if m.user_id == 1][-1]
        assert distribution.noter_reaction(1, 1, dernier.id, dernier.envoye_le + timedelta(minutes=5))
        instant = JOUR.replace(hour=12) + timedelta(days=3)
        _signal("pluie:3", "meteo", instant + timedelta(days=2), instant, jour="2026-11-03", precipitations_mm=30.0)
        distribution.passer(instant, telegram, avec_modele=False)
        assert len(telegram.envoyes) == 4

    def test_ca8_le_message_reste_en_contexte_douze_heures(self, base):
        _signal("levee:lot-14", "suivis", DEMAIN_8H + timedelta(days=7), A_18H, **_levee().donnees)
        db = base()
        db.query(PotagerMembre).filter(PotagerMembre.user_id == 1).one().proactivite_compagnon = {
            "suivis": {"mode": "immediat"}}
        db.commit()
        db.close()
        distribution.passer(JOUR.replace(hour=12), Telegram(), avec_modele=False)
        en_cours = distribution.message_en_contexte(1, 1, JOUR.replace(hour=13))
        assert en_cours is not None and en_cours.signaux[0].donnees["numero"] == 14
        assert en_cours.donnees()["signaux"][0]["question"] == "Ça a germé ?"
        assert distribution.message_en_contexte(1, 1, JOUR.replace(hour=12) + timedelta(hours=13)) is None
        assert distribution.message_en_contexte(1, 2, JOUR.replace(hour=13)) is None
        # Une fois répondu, la conversation continue trente minutes.
        assert distribution.noter_reaction(1, 1, en_cours.message_id, JOUR.replace(hour=13))
        assert distribution.message_en_contexte(1, 1, JOUR.replace(hour=13, minute=20)) is not None
        assert distribution.message_en_contexte(1, 1, JOUR.replace(hour=14)) is None
        assert _lignes(base, SignalVeilleur)[0].etat == "repondu"

    def test_ca8_le_message_entre_dans_la_conversation(self, base):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        distribution.passer(A_18H, Telegram(), avec_modele=False)
        from database.models import EchangeConversation

        echange, panneau = _lignes(base, EchangeConversation)
        assert echange.texte_jardinier == "" and "-2 °C" in echange.texte_compagnon
        assert (echange.canal, panneau.canal) == ("telegram", "pwa")  # [US-272 / CA9]
        assert echange.signal.startswith("spontane:")

    def test_r8_un_signal_redige_ne_produit_aucun_resultat_etape(self, base):
        """Rédaction par le modèle comprise : aucun appel d'outils, aucun exécuteur."""
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        with patch("llm.passerelle.appeler_chat", return_value=SimpleNamespace(texte="Gel demain, -2 °C.")), \
             patch("llm.passerelle.appeler_chat_outils") as outils, \
             patch("app.services.agent.executeurs.executer_plan") as plan, \
             patch("app.services.agent.executeurs.executer_commande", create=True) as commande:
            distribution.passer(A_18H, Telegram())
        outils.assert_not_called(), plan.assert_not_called(), commande.assert_not_called()
        assert _lignes(base, MessageSpontane)[0].redige == "agent"

    def test_purge_a_trente_jours(self, base):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        distribution.passer(A_18H, Telegram(), avec_modele=False)
        svc_signaux.purger(A_18H + timedelta(days=31))
        assert _lignes(base, MessageSpontane) == [] and _lignes(base, EnvoiSignal) == []


class TestCA9ReglagesEnBase:
    def test_appliquer_ecrit_dans_le_profil_du_couple(self, base):
        db = base()
        ctx = TenantContext(user_id=1, potager_id=1)
        reglages = proactivite.appliquer(db, ctx, proactivite.lire_phrase("coupe la météo"), A_18H)
        assert reglages.mode("meteo") == "coupe"
        reglages = proactivite.appliquer(db, ctx, proactivite.lire_phrase("silence de 22h à 7h"), A_18H)
        assert (reglages.silence_debut, reglages.silence_fin) == (22, 7)
        reglages = proactivite.appliquer(db, ctx, proactivite.lire_phrase("point du matin à 9h"), A_18H)
        assert reglages.heure_resume == 9
        assert proactivite.lire(db, TenantContext(user_id=2, potager_id=1)).mode("meteo") == "immediat"
        assert proactivite.appliquer(db, TenantContext(user_id=9, potager_id=1),
                                     proactivite.lire_phrase("coupe la météo"), A_18H) is None
        db.close()

    def test_un_theme_coupe_par_reglage_n_envoie_plus_rien(self, base):
        db = base()
        proactivite.appliquer(db, TenantContext(user_id=1, potager_id=1),
                              proactivite.lire_phrase("arrête de me parler de la météo"), A_18H)
        db.close()
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        telegram = Telegram()
        distribution.passer(A_18H, telegram, avec_modele=False)
        assert telegram.envoyes == []
        # [US-272 / CA9] Le jardinier sans Telegram, qui n'a rien coupé, le lit dans son panneau.
        assert [m.user_id for m in _lignes(base, MessageSpontane)] == [2]

    def test_le_texte_des_reglages(self):
        texte = proactivite.texte_reglages(regles.reglages_depuis(
            {"meteo": {"mode": "resume", "auto": True}}, 22, 7))
        assert "La météo : au point du matin (réglé par moi, faute de réponse)" in texte
        assert "de 22 h à 7 h" in texte


# ═════════════════════════════════════════════════════════════════════════════
# Le bot : boutons, réponse, réglages
# ═════════════════════════════════════════════════════════════════════════════
def _update_bouton(donnee: str):
    message = MagicMock()
    message.reply_text = AsyncMock()
    query = MagicMock(data=donnee, message=message)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    return SimpleNamespace(callback_query=query, message=None, effective_user=SimpleNamespace(id=111))


class TestBot:
    def test_ca7_le_bouton_part_au_flux_des_gestes(self, base, monkeypatch):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        telegram = Telegram()
        distribution.passer(A_18H, telegram, avec_modele=False)
        voile = telegram.envoyes[0][2][0][0][1]
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as saisie:
            asyncio.run(bot._spontane_cb(_update_bouton(voile), MagicMock()))
        saisie.assert_awaited_once()
        assert saisie.await_args.args[1] == "j'ai posé un voile de protection sur Planche Est"
        assert [m for m in _lignes(base, MessageSpontane) if m.user_id == 1][0].reaction_le is not None

    def test_ca7_plus_tard_n_ecrit_rien(self, base, monkeypatch):
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        telegram = Telegram()
        distribution.passer(A_18H, telegram, avec_modele=False)
        plus_tard = telegram.envoyes[0][2][0][1][1]
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        update = _update_bouton(plus_tard)
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as saisie:
            asyncio.run(bot._spontane_cb(update, MagicMock()))
        saisie.assert_not_awaited()
        update.callback_query.message.reply_text.assert_awaited_with(bot.MSG_RIEN)

    def test_un_bouton_d_un_autre_potager_ne_fait_rien(self, monkeypatch):
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=2))
        monkeypatch.setattr(bot.svc_propositions, "potager_a_nommer", lambda u, p: "Jardin partagé")
        update = _update_bouton("spon:1:5:voile")
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as saisie:
            asyncio.run(bot._spontane_cb(update, MagicMock()))
        saisie.assert_not_awaited()
        assert "/potager" in update.callback_query.message.reply_text.await_args.args[0]

    def test_gherkin_la_reponse_au_message_devient_la_levee_a_confirmer(self, base, monkeypatch):
        _signal("levee:lot-14", "suivis", DEMAIN_8H + timedelta(days=7), A_18H, **_levee().donnees)
        midi = JOUR.replace(hour=12)
        distribution.passer(midi, Telegram(), avec_modele=False)
        distribution.passer(DEMAIN_8H, Telegram(), avec_modele=False)
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        monkeypatch.setattr(distribution.veilleur_passage, "maintenant_local", lambda: DEMAIN_8H + timedelta(hours=1))
        update = SimpleNamespace(message=SimpleNamespace(reply_to_message=None))
        assert bot.reprendre_reponse(update, "oui environ 20 sur 24") == "levée du lot 14 : 20"
        assert [m for m in _lignes(base, MessageSpontane) if m.user_id == 1][0].reaction_le is not None
        # Sans message spontané en cours, la phrase passe telle quelle.
        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=2, potager_id=1))
        assert bot.reprendre_reponse(update, "oui environ 20 sur 24") == "oui environ 20 sur 24"

    def test_ca8_le_message_spontane_entre_dans_le_contexte_de_l_agent(self):
        from app.services.agent import contexte_court

        contexte = contexte_court.construire(CTX, spontane={"texte": "Ça a germé ?", "signaux": [{"numero": 14}]})
        assert contexte is not None and contexte.donnees()["message_spontane"]["signaux"][0]["numero"] == 14
        assert "message_spontane" in contexte.prompt() and "Tu as écrit de toi-même" in contexte.prompt()
        assert "Tu as écrit de toi-même" not in contexte_court.construire(
            CTX, echanges=(contexte_court.Echange("a", "b", 0.0),)).prompt()

    def test_ca9_une_phrase_de_reglage_est_proposee_puis_confirmee(self, base, monkeypatch):
        from app.bot import commandes_profil as bot

        monkeypatch.setattr(bot, "SessionLocal", base)
        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        message = MagicMock()
        message.reply_text = AsyncMock()
        ctx = SimpleNamespace(user_data={})
        assert asyncio.run(bot.phrase_de_profil(SimpleNamespace(message=message, callback_query=None), ctx,
                                                "arrête de me parler de la météo"))
        assert "C'est bon ?" in message.reply_text.await_args.args[0]
        db = base()
        assert proactivite.lire(db, CTX).mode("meteo") == "immediat"   # rien d'écrit avant le « Oui »
        db.close()
        update = _update_bouton("profil:pok")
        asyncio.run(bot._profil_cb(update, ctx))
        db = base()
        assert proactivite.lire(db, CTX).mode("meteo") == "coupe"
        db.close()

    def test_ca9_le_bouton_d_un_theme_ecrit_au_clic(self, base, monkeypatch):
        from app.bot import commandes_profil as bot

        monkeypatch.setattr(bot, "SessionLocal", base)
        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        update = _update_bouton("profil:pt:echeances")
        asyncio.run(bot._profil_cb(update, SimpleNamespace(user_data={})))
        db = base()
        assert proactivite.lire(db, CTX).mode("echeances") == "coupe"
        db.close()
        assert "au point du matin" not in update.callback_query.edit_message_text.await_args.args[0].split("\n")[3]

    def test_le_distributeur_est_planifie_par_le_bot(self):
        from app.bot import application

        app = application._construire_application()
        noms = {job.name for job in app.job_queue.jobs()}
        assert {"distributeur", "veilleur", "veilleur_bilan_semaine"} <= noms
        motifs = [getattr(h, "pattern", None) for groupe in app.handlers.values() for h in groupe]
        assert any(m is not None and m.pattern == "^spon:" for m in motifs)


# ═════════════════════════════════════════════════════════════════════════════
# QA — cas limites et pannes
# ═════════════════════════════════════════════════════════════════════════════
class TestQACasLimitesEtPannes:
    def test_us267_distribution_un_potager_en_panne_ne_prive_pas_les_suivants(self, base, monkeypatch):
        db = base()
        db.add(Potager(id=2, nom="Autre", proprietaire_id=1, etat="actif"))
        db.add(PotagerMembre(user_id=1, potager_id=2, role="owner"))
        db.commit()
        db.close()
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        vrai = distribution.planifier_potager

        def planifier(potager_id, maintenant):
            if potager_id == 2:
                raise RuntimeError("base indisponible")
            return vrai(potager_id, maintenant)

        monkeypatch.setattr(distribution, "planifier_potager", planifier)
        telegram = Telegram()
        assert distribution.passer(A_18H, telegram, avec_modele=False) == {1: 1}

    def test_us267_distribution_un_signal_propre_a_un_jardinier_ne_va_qu_a_lui(self, base):
        db = base()
        db.add(User(id=3, nom="Autre", telegram_chat_id=333))
        db.add(PotagerMembre(user_id=3, potager_id=1, role="editor"))
        db.add(SignalVeilleur(potager_id=1, user_id=3, theme="rappels", cle_unique="rappel:1", priorite="immediat",
                              expire_le=DEMAIN_8H, donnees={"objet": "vérifier la levée"}, etat="detecte",
                              detecte_le=A_18H))
        db.commit()
        db.close()
        telegram = Telegram()
        distribution.passer(A_18H, telegram, avec_modele=False)
        assert [chat for chat, _, _ in telegram.envoyes] == [333]
        assert "vérifier la levée" in telegram.envoyes[0][1]

    def test_us267_distribution_un_membre_parti_ne_recoit_plus_rien(self, base):
        midi = JOUR.replace(hour=12)
        _signal("levee:lot-14", "suivis", midi + timedelta(days=7), midi, **_levee().donnees)
        distribution.passer(midi, Telegram(), avec_modele=False)
        db = base()
        db.query(PotagerMembre).filter(PotagerMembre.user_id == 1).delete()
        db.commit()
        db.close()
        telegram = Telegram()
        distribution.passer(DEMAIN_8H, telegram, avec_modele=False)
        assert telegram.envoyes == []
        assert {e.motif for e in _lignes(base, EnvoiSignal) if e.user_id == 1} == {"plus_membre"}

    def test_us267_distribution_un_lecteur_ne_recoit_pas_de_message(self, base):
        db = base()
        db.query(PotagerMembre).filter(PotagerMembre.user_id == 1).one().role = "lecteur"
        db.commit()
        db.close()
        _signal("gel:2026-10-31:parcelle-12", "meteo", DEMAIN_5H, A_18H, **_gel().donnees)
        telegram = Telegram()
        distribution.passer(A_18H, telegram, avec_modele=False)
        assert telegram.envoyes == []

    def test_us267_contexte_une_base_illisible_ne_bloque_pas_la_phrase(self, monkeypatch):
        monkeypatch.setattr(distribution, "SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        assert distribution.message_en_contexte(1, 1, A_18H) is None
        assert distribution.noter_reaction(1, 1, 5, A_18H) is False
        assert distribution.message_en_contexte(1, None, A_18H) is None

    def test_us267_bouton_un_message_purge_est_perime(self, base, monkeypatch):
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        update = _update_bouton("spon:1:999:voile")
        asyncio.run(bot._spontane_cb(update, MagicMock()))
        update.callback_query.message.reply_text.assert_awaited_with(bot.MSG_PERIME)

    def test_us267_bouton_reglages_ouvre_les_reglages(self, base, monkeypatch):
        from app.bot import commandes_profil
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        monkeypatch.setattr(commandes_profil, "SessionLocal", base)
        update = _update_bouton("spon:1:0:reglages")
        asyncio.run(bot._spontane_cb(update, MagicMock()))
        texte = update.callback_query.message.reply_text.await_args.args[0]
        assert texte.startswith("🔔 Mes messages spontanés") and "La météo : tout de suite" in texte

    def test_us267_bouton_un_callback_illisible_ne_fait_rien(self, monkeypatch):
        from app.bot import messages_spontanes as bot

        monkeypatch.setattr(bot, "current_context", lambda: TenantContext(user_id=1, potager_id=1))
        update = _update_bouton("spon:x:y")
        asyncio.run(bot._spontane_cb(update, MagicMock()))
        update.callback_query.message.reply_text.assert_not_awaited()

    def test_us267_job_une_panne_ne_tue_jamais_le_bot(self, monkeypatch):
        from app.bot import messages_spontanes as bot
        from app.bot import veilleur_jobs

        panne = MagicMock(side_effect=RuntimeError("panne"))
        monkeypatch.setattr(bot.svc_distribution, "passer", panne)
        asyncio.run(bot.job_distributeur(MagicMock()))
        monkeypatch.setattr(veilleur_jobs, "job_file_gestes", AsyncMock())
        monkeypatch.setattr(veilleur_jobs.svc_veilleur_passage, "passer", MagicMock())
        asyncio.run(veilleur_jobs.job_veilleur(MagicMock()))
        assert panne.call_count == 2   # le job du distributeur, puis la détection du veilleur

    def test_us267_profil_les_boutons_silence_et_matin_expliquent_la_phrase(self, monkeypatch):
        from app.bot import commandes_profil as bot

        monkeypatch.setattr(bot, "current_context", lambda: CTX)
        for action, attendu in (("silence", bot.TEXTE_CHANGER_SILENCE), ("matin", bot.TEXTE_CHANGER_MATIN)):
            update = _update_bouton(f"profil:{action}")
            asyncio.run(bot._profil_cb(update, SimpleNamespace(user_data={})))
            update.callback_query.message.reply_text.assert_awaited_with(attendu)

    def test_us267_profil_une_proposition_expiree_n_ecrit_rien(self, base, monkeypatch):
        from app.bot import commandes_profil as bot

        monkeypatch.setattr(bot, "SessionLocal", base)
        monkeypatch.setattr(bot, "current_context", lambda: CTX)
        update = _update_bouton("profil:pok")
        asyncio.run(bot._profil_cb(update, SimpleNamespace(user_data={})))
        assert "plus d'actualité" in update.callback_query.edit_message_text.await_args.args[0]

    def test_us267_profil_non_abandonne_la_proposition(self, monkeypatch):
        from app.bot import commandes_profil as bot

        monkeypatch.setattr(bot, "current_context", lambda: CTX)
        ctx = SimpleNamespace(user_data={bot._CLE_REGLAGE_EN_ATTENTE: {"genre": "mode", "theme": "meteo",
                                                                      "mode": "coupe"}})
        asyncio.run(bot._profil_cb(_update_bouton("profil:non"), ctx))
        assert bot._CLE_REGLAGE_EN_ATTENTE not in ctx.user_data

    def test_us267_profil_affiche_le_bouton_des_messages_spontanes(self):
        from app.bot import commandes_profil as bot

        boutons = [b.callback_data for rangee in bot._clavier_profil().inline_keyboard for b in rangee]
        assert "profil:proactif" in boutons
        assert "Messages spontanés" in bot.texte_profil(None)

    def test_us267_aide_le_domaine_alertes(self):
        from app.bot import aide

        assert "alertes" in aide._HELP_DOMAINES
        assert aide._HELP_CONTEXTUEL["notifications"] is aide._HELP_ALERTES
        assert "silence de 22 h à 7 h" in aide._HELP_ALERTES

    def test_us267_reponse_un_oui_sans_question_n_ecrit_rien(self):
        pluie = SignalARediger("meteo", "pluie:2026-10-31", DEMAIN_8H, {"jour": "2026-10-31", "precipitations_mm": 25})
        assert reponse_signal.reformuler([pluie], "oui") is None
        assert reponse_signal.reformuler([_gel()], "") is None
        assert reponse_signal.reformuler([_gel()], "d'accord merci beaucoup") is None
