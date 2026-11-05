"""
tests/test_us288_tests_conversationnels.py
[US-288] Harnais de scénarios conversationnels joués sur Telegram (`tests_conv/`)

Ce fichier teste tout ce qui ne demande NI Telegram NI modèle : le format des scénarios,
les vérifications, le verdict, les rapports, et le mode test du bot (`/reset_test`).
Le pilote Telethon lui-même ne se teste que contre un vrai bot de test
(`python -m tests_conv run --id SC-000 --go`).
"""
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import mode_test as svc_mode_test
from database.models import Evenement, Parcelle, Potager, User
from tests_conv.harness import assertions as ass
from tests_conv.harness import parser, report
from tests_conv.harness.runner import (ECHEC, REUSSI, SURVEILLER, ResultatPassage, ResultatScenario,
                                       ResultatTour, nombre_de_messages)

SCENARIOS = Path(__file__).resolve().parent.parent / "tests_conv" / "scenarios"

VALIDE = """---
id: SC-900
titre: Exemple
tags: [critique]
passages: 2
seuil: 0.5
parcelles: [Serre]
---
Commentaire libre.

## Tour 1
> j'ai planté
> 12 tomates

- texte contient: tomate
- ? bouton: Confirmer
- aucune écriture

## Tour 2 — confirmation
[clic] Confirmer

- événement: culture=tomate, quantite=12
"""


def _ecrire(tmp_path, texte, nom="sc.md"):
    f = tmp_path / nom
    f.write_text(texte, encoding="utf-8")
    return f


# ── parseur ──────────────────────────────────────────────────────────────────
def test_parseur_lit_un_scenario_complet(tmp_path):
    sc = parser.charger(_ecrire(tmp_path, VALIDE))
    assert (sc.id, sc.passages, sc.seuil, sc.parcelles, sc.tags) == ("SC-900", 2, 0.5, ("Serre",), ("critique",))
    assert [t.numero for t in sc.tours] == [1, 2]
    assert sc.tours[0].message == "j'ai planté\n12 tomates"
    assert sc.tours[1].clic == "Confirmer" and sc.tours[1].titre == "confirmation"
    assert [v.genre for v in sc.tours[0].verifications] == ["texte_contient", "bouton", "aucune_ecriture"]
    assert [v.bloquante for v in sc.tours[0].verifications] == [True, False, True]


def test_les_scenarios_livres_sont_valides():
    scenarios = parser.charger_dossier(SCENARIOS)
    assert scenarios and len({s.id for s in scenarios}) == len(scenarios)


@pytest.mark.parametrize("texte, fragment", [
    ("pas d'entête\n", "commencer par un en-tête"),
    ("---\nid: X\n", "jamais refermé"),
    ("---\ntitre: T\n---\n## Tour 1\n> a\n", "`id` est obligatoire"),
    ("---\nid: X\ntitre: T\npassages: 0\n---\n## Tour 1\n> a\n", "`passages`"),
    ("---\nid: X\ntitre: T\nseuil: 1.5\n---\n## Tour 1\n> a\n", "`seuil`"),
    ("---\nid: X\ntitre: T\n---\ntexte seul\n", "aucun tour"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n- aucune écriture\n", "un message"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n[clic] b\n", "un message"),
    ("---\nid: X\ntitre: T\n---\n## Tour 2\n> a\n", "se numérotent"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n- inventé: x\n", "vérification inconnue"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n- texte contient:\n", "demande une valeur"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n- texte regex: (\n", "expression régulière"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n- aucune écriture: oui\n", "ne prend pas de valeur"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n- événement: couleur=rouge\n", "champ=valeur"),
    ("---\nid: X\ntitre: T\n---\n## Tour 1\n> a\n- latence max: vite\n", "nombre de secondes"),
])
def test_parseur_refuse_un_scenario_mal_forme_en_disant_ou(tmp_path, texte, fragment):
    with pytest.raises(parser.ScenarioInvalide) as e:
        parser.charger(_ecrire(tmp_path, texte))
    assert fragment in str(e.value) and "sc.md:" in str(e.value)


def test_parseur_refuse_deux_scenarios_de_meme_id(tmp_path):
    _ecrire(tmp_path, VALIDE, "a.md")
    _ecrire(tmp_path, VALIDE, "b.md")
    with pytest.raises(parser.ScenarioInvalide, match="déjà pris"):
        parser.charger_dossier(tmp_path)


# ── vérifications ────────────────────────────────────────────────────────────
def _v(genre, valeur="", bloquante=True):
    return parser.Verification(genre, valeur, bloquante)


def test_verifications_de_texte_ignorent_accents_casse_et_emojis():
    obs = ass.Observation(messages=["✅ Récapitulatif : 12 TOMATES à la Serre"], boutons=["✅ Confirmer", "❌ Annuler"])
    assert ass.evaluer(_v("texte_contient", "tomate"), obs).ok
    assert ass.evaluer(_v("texte_contient", "recapitulatif"), obs).ok
    assert not ass.evaluer(_v("texte_contient", "courgette"), obs).ok
    assert ass.evaluer(_v("texte_absent", "erreur"), obs).ok
    assert ass.evaluer(_v("texte_regex", r"\d+ tomates"), obs).ok
    assert ass.evaluer(_v("bouton", "confirmer"), obs).ok
    assert not ass.evaluer(_v("bouton", "Plus tard"), obs).ok
    assert not ass.evaluer(_v("aucun_bouton"), obs).ok


def test_verifications_de_base_comparent_nombres_et_textes():
    evt = {"type_action": "plantation", "culture": "Tomate", "quantite": 12.0, "parcelle": "Serre", "rang": None}
    obs = ass.Observation(evenements=[evt], actions=1, outils=("proposer_commande",))
    assert ass.evaluer(_v("ecriture", "plantation"), obs).ok
    assert not ass.evaluer(_v("ecriture", "semis"), obs).ok
    assert ass.evaluer(_v("evenement", "culture=tomate, quantite=12, parcelle=serre"), obs).ok
    assert ass.evaluer(_v("evenement", "quantite=12.0"), obs).ok
    assert not ass.evaluer(_v("evenement", "quantite=13"), obs).ok
    assert not ass.evaluer(_v("evenement", "rang=4"), obs).ok
    assert not ass.evaluer(_v("aucune_ecriture"), obs).ok
    assert ass.evaluer(_v("aucune_ecriture"), ass.Observation()).ok
    assert ass.evaluer(_v("outil", "proposer_commande"), obs).ok
    assert not ass.evaluer(_v("outil", "lire"), obs).ok


def test_latence_et_juge():
    assert ass.evaluer(_v("latence_max", "10"), ass.Observation(latence_s=4.2)).ok
    assert not ass.evaluer(_v("latence_max", "3,5s"), ass.Observation(latence_s=4.2)).ok
    assert ass.evaluer(_v("juge", "ton aimable"), ass.Observation()).ok is None  # non évalué, ni vert ni rouge


# ── verdict ──────────────────────────────────────────────────────────────────
def _scenario(seuil, passages_ok):
    sc = parser.Scenario("SC-1", "t", Path("x.md"), (parser.Tour(1, "", "a"),), seuil=seuil)
    res = ResultatScenario(sc)
    for i, ok in enumerate(passages_ok, start=1):
        obs = ass.Observation(messages=["r"])
        verifs = [ass.Resultat(_v("texte_contient", "z"), ok, "")]
        res.passages.append(ResultatPassage(i, [ResultatTour(sc.tours[0], obs, verifs)]))
    return res


def test_verdict_reussi_surveiller_echec():
    assert _scenario(0.6, [True, True, True]).statut == REUSSI
    assert _scenario(0.6, [True, True, False]).statut == SURVEILLER
    assert _scenario(0.6, [True, False, False]).statut == ECHEC
    assert _scenario(1.0, [True, False]).statut == ECHEC


def test_un_tour_sans_reponse_ou_un_critere_informatif_ne_se_confondent_pas():
    tour = parser.Tour(1, "", "a")
    muet = ResultatTour(tour, ass.Observation(silence=True), [])
    assert not muet.ok
    info = ResultatTour(tour, ass.Observation(messages=["r"]), [ass.Resultat(_v("bouton", "x", bloquante=False), False)])
    assert info.ok


def test_volume_annonce_compte_la_remise_a_zero():
    sc = parser.charger_dossier(SCENARIOS)
    attendu = sum(s.passages * (len(s.tours) + 1) for s in sc)
    assert nombre_de_messages(sc) == attendu
    assert nombre_de_messages(sc, passages=1) == sum(len(s.tours) + 1 for s in sc)


# ── rapports ─────────────────────────────────────────────────────────────────
def test_rapports_json_html_junit(tmp_path):
    ok, ko = _scenario(1.0, [True]), _scenario(1.0, [False])
    ko.scenario = parser.Scenario("SC-2", "ko <b>", Path("y.md"), ko.scenario.tours, seuil=1.0)
    infos = {"date": "2026-11-03T10:00:00", "version_bot": "3.0", "commit": "abc", "agent_mode": "prioritaire",
             "modele_agent": "mistral/x", "jetons": {"entree": 1, "sortie": 2, "cache": 0}}
    chemins = report.ecrire(tmp_path / "r", [ok, ko], infos)
    donnees = json.loads(chemins["json"].read_text(encoding="utf-8"))
    assert [s["statut"] for s in donnees["scenarios"]] == [REUSSI, ECHEC]
    page = chemins["html"].read_text(encoding="utf-8")
    assert "SC-1" in page and "ko &lt;b&gt;" in page and "<b>" not in page.split("SC-2")[1].split("</h2>")[0]
    suite = ET.parse(chemins["junit"]).getroot()
    assert suite.get("tests") == "2" and suite.get("failures") == "1"
    assert len(suite.findall("testcase/failure")) == 1


# ── mode test du bot ─────────────────────────────────────────────────────────
def test_base_de_test_exige_test_dans_le_nom():
    assert svc_mode_test.base_de_test("postgresql://u:p@h:5432/potager_test")
    assert svc_mode_test.base_de_test("sqlite:///:memory:")
    assert not svc_mode_test.base_de_test("postgresql://u:p@h:5432/potager")
    assert not svc_mode_test.base_de_test("postgresql://test:p@h:5432/potager")  # « test » dans l'utilisateur ne compte pas


def test_remise_a_zero_refusee_hors_mode_test(test_db):
    with patch.object(svc_mode_test, "APP_ENV", "dev"):
        with pytest.raises(svc_mode_test.ModeTestInactifError):
            svc_mode_test.remettre_a_zero(test_db, 1)


def test_remise_a_zero_ne_touche_que_le_potager_vise(test_db):
    user = User(email="jardinier@example.org")
    test_db.add(user)
    test_db.flush()
    for pid in (1, 2):
        test_db.add(Potager(id=pid, nom=f"P{pid}", proprietaire_id=user.id))
    test_db.flush()
    for pid in (1, 2):
        p = Parcelle(nom="Serre", nom_normalise="serre", potager_id=pid)
        test_db.add(p)
        test_db.flush()
        test_db.add(Evenement(type_action="plantation", culture="tomate", parcelle_id=p.id, potager_id=pid))
    test_db.commit()
    with patch.object(svc_mode_test, "APP_ENV", "test"):
        bilan = svc_mode_test.remettre_a_zero(test_db, 1)
    assert bilan["evenements"] == 1 and bilan["parcelles"] == 1
    assert test_db.query(Evenement).filter_by(potager_id=1).count() == 0
    assert test_db.query(Evenement).filter_by(potager_id=2).count() == 1
    assert test_db.query(Potager).count() == 2  # le potager lui-même est conservé


def test_reset_test_enregistree_seulement_en_mode_test():
    from app.bot import application
    noms = lambda app: {c for hs in app.handlers.values() for h in hs if h.__class__.__name__ == "CommandHandler"
                        for c in h.commands}
    with patch.object(application, "APP_ENV", "dev"):
        assert "reset_test" not in noms(application._construire_application())
    with patch.object(application, "APP_ENV", "test"):
        app = application._construire_application()
    assert "reset_test" in noms(app)
    from app.services import menu_commandes
    assert "reset_test" in menu_commandes.COMMANDES_EXCLUES


def test_vider_etats_en_attente():
    from app.bot import etat, mode_test
    etat._ACTION_PENDING[42] = {"x": 1}
    etat._NOTE_PENDING[42] = {"y": 2}
    assert mode_test.vider_etats_en_attente() >= 2
    assert not etat._ACTION_PENDING and not etat._NOTE_PENDING


@pytest.mark.asyncio
async def test_commande_reset_test_refuse_hors_mode_test():
    from app.bot import mode_test
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    with patch.object(svc_mode_test, "APP_ENV", "prod"):
        await mode_test.cmd_reset_test(update, MagicMock())
    assert "réservée au mode test" in update.message.reply_text.call_args.args[0]


# ── pilote (client Telethon simulé : la logique de tour, pas le réseau) ──────
class _Bouton:
    def __init__(self, text):
        self.text = text


class _Message:
    def __init__(self, id, texte, boutons=()):
        self.id, self.message = id, texte
        self.buttons = [[_Bouton(b) for b in boutons]] if boutons else None
        self.clics, self.apres_clic = [], None

    async def click(self, i, j):
        self.clics.append((i, j))
        if self.apres_clic:
            await self.apres_clic()


class _Evenement:
    def __init__(self, message):
        self.message = message


def _pilote(reponses):
    """Pilote dont le « client » répond à chaque envoi par les `reponses` (liste de listes de messages)."""
    pytest.importorskip("telethon")
    from tests_conv.harness.config import Config
    from tests_conv.harness.driver import PiloteTelegram
    cfg = Config(1, "h", "", "bot", quiescence_s=0.3, premiere_reponse_s=1.0, plafond_tour_s=3.0, pause_s=0.0)
    pilote = PiloteTelegram(cfg)
    file = list(reponses)

    class Client:
        async def send_message(self, _bot, _texte):
            for m in file.pop(0):
                await pilote._sur_message(_Evenement(m))

    pilote.client = Client()
    return pilote


@pytest.mark.asyncio
async def test_pilote_une_edition_remplace_le_message_et_les_boutons_sont_releves():
    pilote = _pilote([[_Message(1, "…"), _Message(1, "Récap : 12 tomates", ("✅ Confirmer", "❌ Annuler"))]])
    obs = await pilote.envoyer("j'ai planté 12 tomates")
    assert obs.messages == ["Récap : 12 tomates"] and obs.boutons == ["✅ Confirmer", "❌ Annuler"]
    assert not obs.silence and obs.latence_s < 1.0


@pytest.mark.asyncio
async def test_pilote_clique_un_bouton_du_tour_precedent_par_son_libelle():
    recap = _Message(1, "Récap", ("✅ Confirmer", "❌ Annuler"))
    pilote = _pilote([[recap]])

    async def reponse_au_clic():
        await pilote._sur_message(_Evenement(_Message(2, "Enregistré")))
    recap.apres_clic = reponse_au_clic
    await pilote.envoyer("dictée")
    obs = await pilote.cliquer("confirmer")
    assert recap.clics == [(0, 0)]
    assert obs.messages == ["Enregistré"]


@pytest.mark.asyncio
async def test_pilote_bouton_introuvable_et_silence():
    from tests_conv.harness.driver import BoutonIntrouvable
    pilote = _pilote([[], ])
    obs = await pilote.envoyer("bonjour")
    assert obs.silence and obs.messages == []
    with pytest.raises(BoutonIntrouvable, match="Confirmer"):
        await pilote.cliquer("Confirmer")
