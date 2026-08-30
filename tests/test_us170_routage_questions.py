"""
tests/test_us170_routage_questions.py
[US-170] Trois défauts de routage corrigés, mesurés en conditions réelles le
30/08/2026 (docs/ANALYSE_ROUTAGE_QUESTIONS_2026-08-30.md) :

- Chantier 3 (CA1-CA5) : une famille `godets_produits` répond au nombre de
  godets produits, avant `rendement_saison` dans le catalogue, dont le motif
  `\bproduit\b` — bien trop large (« produit » est aussi un nom courant du
  jardinage) — est resserré.
- Chantier 1 (CA6-CA12) : `bot.handle_text` délègue la nature de la demande à
  `routeur.classer_demande()` au lieu de `bot._is_question` (supprimée), dont
  la moitié du critère (le point d'interrogation) est absente de la dictée
  vocale.
- Chantier 2 (CA13-CA16) : `routeur.repondre_avec_cascade` sert la phrase
  produite par une famille du catalogue même quand elle dit « rien
  d'enregistré », au lieu de la jeter et de remonter vers un conseil générique.

CA17/CA18 (traçabilité des révisions US-093/US-096) sont des exigences
documentaires, vérifiées par les docstrings de `llm/routeur.py` et
`app/services/reponses_chiffrees.py` — pas par un test programmatique. CA19
(retour jardinier) est couvert transitivement par les assertions sur
`etage_resolveur` ci-dessous, US-097 gérant déjà l'affichage. CA20 (météo) est
un hors-périmètre explicite : rien à tester.
"""
import csv
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import Evenement
from llm import routeur

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
ANNEE = datetime.now().year


@pytest.fixture(autouse=True)
def _cache_propre():
    """Aucun test ne doit hériter du cache de classification d'un autre."""
    routeur.vider_cache()
    yield
    routeur.vider_cache()


@pytest.fixture(autouse=True)
def _aucun_appel_modele():
    """Les chantiers 1 et 3 promettent un coût nul en jetons pour ces cas :
    un appel modèle inattendu doit faire échouer le test, pas passer inaperçu."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "un appel au modèle a eu lieu alors qu'une règle ou le catalogue devait suffire"
    )):
        yield


def _evenement(**champs) -> Evenement:
    return Evenement(**champs)


# ═════════════════════════════════════════════════════════════════════════════
# Chantier 3 — CA1 à CA5 : famille godets_produits + motif resserré
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def potager_godets(test_db):
    """Tomate mise en godet deux fois cette saison (12 + 8 plants), puis
    récoltée — pour distinguer sans ambiguïté « combien de godets » de
    « combien récolté », le défaut exact du 30/08/2026."""
    test_db.add_all([
        _evenement(date=datetime(ANNEE, 3, 1), type_action="mise_en_godet", culture="tomate",
                   nb_plants_godets=12, potager_id=1),
        _evenement(date=datetime(ANNEE, 3, 15), type_action="mise_en_godet", culture="tomate",
                   nb_plants_godets=8, potager_id=1),
        _evenement(date=datetime(ANNEE, 7, 10), type_action="recolte", culture="tomate",
                   quantite=3.5, unite="kg", potager_id=1),
    ])
    test_db.commit()
    return test_db


def test_us170_ca1_godets_produits_distinct_du_rendement_recolte(potager_godets):
    """CA1 — « combien de godet de tomate produit cette saison ? » rend un
    nombre de godets (20 = 12 + 8), jamais le poids récolté (3,5 kg)."""
    reponse = rc.repondre_chiffre(
        CTX, "combien de godet de tomate produit cette saison ?", db=potager_godets
    )
    assert reponse is not None
    assert reponse.famille == "godets_produits"
    assert reponse.present is True
    assert "20" in reponse.texte
    assert "kg" not in reponse.texte


def test_us170_ca2_godets_produits_precede_rendement_saison_au_catalogue():
    """CA2 — l'ordre du catalogue place godets_produits avant rendement_saison :
    sans lui, rendement_saison capterait la question en premier."""
    noms = [famille.nom for famille in rc.FAMILLES]
    assert "godets_produits" in noms and "rendement_saison" in noms
    assert noms.index("godets_produits") < noms.index("rendement_saison")


def test_us170_ca3_rendement_saison_ne_capte_plus_produit_seul():
    """CA3 — « produit » nom commun (un produit phytosanitaire) ne matche plus
    rendement_saison : avant resserrement, cette question de savoir aurait été
    aiguillée à tort vers un agrégat SQL sans rapport."""
    famille = next(f for f in rc.FAMILLES if f.nom == "rendement_saison")
    normalisee = rc._normaliser("quel produit utiliser contre le mildiou sur mes tomates ?")
    assert not famille.motif.search(normalisee)


def test_us170_ca4_rendement_saison_reste_atteignable_avec_produit_conjugue(potager_godets):
    """CA4 — non-régression du resserrement : une tournure de rendement réel
    (« a bien produit »),  verbe conjugué juste avant « produit », continue
    d'aiguiller vers rendement_saison."""
    reponse = rc.repondre_chiffre(
        CTX, "est-ce que ma tomate a bien produit cette saison ?", db=potager_godets
    )
    assert reponse is not None
    assert reponse.famille == "rendement_saison"


def test_us170_ca4_bis_corpus_us096_toujours_aiguille_vers_rendement_saison(potager_godets):
    """CA4 — la formulation déjà couverte par le corpus US-096 (sans le mot
    « produit ») n'est pas affectée par le resserrement du motif."""
    reponse = rc.repondre_chiffre(CTX, "où en sont mes tomates ?", db=potager_godets)
    assert reponse is not None
    assert reponse.famille == "rendement_saison"


def test_us170_ca5_godets_produits_a_une_phrase_d_absence_juste(test_db):
    """CA5 — aucune mise en godet enregistrée pour une culture pourtant connue
    du potager (semée) : la phrase dit l'absence, elle ne l'invente pas."""
    test_db.add(_evenement(
        date=datetime(ANNEE, 4, 1), type_action="semis", culture="poireau",
        quantite=30, unite="graines", potager_id=1,
    ))
    test_db.commit()
    reponse = rc.repondre_chiffre(
        CTX, "combien de godet de poireau produit cette saison ?", db=test_db
    )
    assert reponse is not None
    assert reponse.present is False
    assert "aucune mise en godet" in reponse.texte.lower()


# ═════════════════════════════════════════════════════════════════════════════
# Chantier 1 — CA6 à CA12 : la nature de la demande se décide au routeur
# ═════════════════════════════════════════════════════════════════════════════
def _update_texte(texte: str, user_id: int = 999100) -> MagicMock:
    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = texte
    update.effective_user = MagicMock(id=user_id)
    return update


@pytest.mark.asyncio
async def test_us170_ca6_ca7_question_sans_point_interrogation_atteint_le_routeur():
    """CA6, CA7 — cas nominal du canal vocal : une question dictée SANS point
    d'interrogation est désormais classée par le routeur (bot._is_question,
    dont la moitié du critère reposait sur ce `?`, a disparu)."""
    from bot import handle_text

    update = _update_texte("ma production de tomate")
    ctx = MagicMock()
    ctx.user_data = {}

    decision = routeur.DecisionRoutage(nature=routeur.NATURE_QUESTION_DATA, origine="regle", confiance=1.0)
    with (
        patch("bot._verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch("llm.routeur.classer_demande", return_value=decision) as mock_classer,
        patch("bot._ask_question", new=AsyncMock()) as mock_ask_question,
        patch("bot._parse_and_save", new=AsyncMock()) as mock_parse,
    ):
        await handle_text(update, ctx)

    mock_classer.assert_called_once()
    mock_ask_question.assert_awaited_once_with(update, "ma production de tomate")
    mock_parse.assert_not_called()


@pytest.mark.asyncio
async def test_us170_ca6_action_classee_par_le_routeur_part_toujours_au_parsing():
    """CA6 — non-régression : une saisie réelle, classée ACTION par le routeur,
    continue d'atteindre le parsing normal (aucun détour par _ask_question)."""
    from bot import handle_text

    update = _update_texte("récolté 2 kg de tomates")
    ctx = MagicMock()
    ctx.user_data = {}

    decision = routeur.DecisionRoutage(nature=routeur.NATURE_ACTION, origine="regle", confiance=1.0)
    with (
        patch("bot._verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch("llm.routeur.classer_demande", return_value=decision),
        patch("bot._ask_question", new=AsyncMock()) as mock_ask_question,
        patch("bot._parse_and_save", new=AsyncMock()) as mock_parse,
    ):
        await handle_text(update, ctx)

    mock_ask_question.assert_not_called()
    mock_parse.assert_awaited_once()


@pytest.mark.asyncio
async def test_us170_ca8_gardes_de_conversation_restent_avant_le_routeur():
    """CA8 — non-régression explicite (US-093 / CA13, révisée) : un message reçu
    en pleine correction (mode corr_apply) ne doit jamais atteindre le routeur."""
    from bot import handle_text

    update = _update_texte("combien de tomates ?")
    ctx = MagicMock()
    ctx.user_data = {"mode": "corr_apply", "corr_event_id": 1}

    with (
        patch("bot._verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch("bot._corr_apply", new=AsyncMock()) as mock_corr_apply,
        patch("llm.routeur.classer_demande") as mock_classer,
    ):
        await handle_text(update, ctx)

    mock_corr_apply.assert_awaited_once()
    mock_classer.assert_not_called()


def test_us170_ca9_godets_en_attente_exclut_les_questions_de_production():
    """CA9 — la garde `_is_requete_godets` (liste des godets en attente de
    plantation, sans équivalent catalogue) ne capte plus une question de
    production/rendement, que le catalogue sait désormais servir. Sans cette
    exclusion, la question restait interceptée à la PRIORITÉ 3b, avant même
    d'atteindre le routeur — chantier 3 seul n'aurait rien changé côté bot.py."""
    import bot

    assert bot._is_requete_godets("combien de godet de tomate produit cette saison ?") is False
    # non-régression : la consultation des godets en attente, elle, reste détectée
    assert bot._is_requete_godets("liste des godets en attente") is True
    assert bot._is_requete_godets("quels plants sont en godet") is True
    assert bot._is_requete_godets("voir les godets") is True


@pytest.mark.asyncio
async def test_us170_ca10_filet_us011_conserve():
    """CA10 — le filet de rerattrapage d'US-011 reste intact : une action sans
    `action` détectée après parsing reroute encore vers _ask_question, comme
    chemin résiduel (et non plus comme chemin nominal)."""
    from bot import _parse_and_save

    update = MagicMock()
    update.message = AsyncMock()
    update.callback_query = None

    with (
        patch("bot.require_role"),
        patch("bot._ask_question", new=AsyncMock()) as mock_ask_question,
    ):
        await _parse_and_save(
            update, "ma production de tomate",
            pre_parsed_items=[{"action": None, "culture": "tomate", "quantite": None, "date": None}],
        )

    mock_ask_question.assert_awaited_once_with(update, "ma production de tomate")


def test_us170_ca11_aucune_saisie_reelle_classee_a_tort_comme_question():
    """CA11 — sur les 211 saisies réelles distinctes de production (même
    méthode que docs/ANALYSE_ROUTAGE_QUESTIONS_2026-08-30.md §4), les règles
    seules du routeur (0 jeton) ne classent jamais une action comme question."""
    chemin = Path(__file__).parent / "corpus" / "us094_saisies_reelles.csv"
    with open(chemin, encoding="utf-8") as f:
        textes = sorted({ligne["texte"] for ligne in csv.DictReader(f)})

    faux_positifs = [
        t for t in textes
        if (nature := routeur._regle_par_mots_cles(t)) is not None and nature != routeur.NATURE_ACTION
    ]
    assert faux_positifs == []


def test_us170_ca12_question_reconnue_par_regle_coute_zero_jeton():
    """CA12 — une question désormais servie par le catalogue (godets_produits)
    coûte 0 jeton de classification, contre un parsing d'action complet avant
    US-170 (mesuré ~2 940 jetons le 30/08/2026)."""
    decision = routeur.classer_demande("combien de godet de tomate produit cette saison ?", ctx=None)
    # `ctx=None` : la règle catalogue elle-même dépend d'une base, mais les
    # marqueurs DATA suffisent déjà à classer sans elle — 0 jeton dans tous les cas.
    assert decision.origine == "regle"
    assert decision.confiance == 1.0


# ═════════════════════════════════════════════════════════════════════════════
# Chantier 2 — CA13 à CA16 : « rien » est une réponse, pas un échec
# ═════════════════════════════════════════════════════════════════════════════
def test_us170_ca13_famille_matchee_sans_donnee_ne_remonte_pas():
    """CA13 — une famille du catalogue qui a matché et produit une phrase
    (`chiffree is not None`) est servie telle quelle, même à `present=False` :
    la cascade ne remonte pas vers le raisonnement."""
    chiffree = rc.ReponseChiffree(
        texte="Je n'ai aucune récolte de concombre enregistrée cette saison.",
        famille="rendement_saison", present=False,
        aiguillage={"famille": "rendement_saison", "culture": "concombre", "parcelle": None, "dependances": []},
    )
    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=(chiffree.texte, False, chiffree),
        ),
        patch("llm.passerelle.appeler_chat") as mock_llm,
        patch.object(routeur, "_persister_routage_log", return_value=None),
    ):
        resultat = routeur.repondre_avec_cascade(CTX, "quel ma production de concombre ?")

    mock_llm.assert_not_called()
    assert resultat.texte == "Je n'ai aucune récolte de concombre enregistrée cette saison."
    assert resultat.etage_resolveur == routeur.ETAGE_DONNEE


def test_us170_ca14_aucune_famille_matchee_continue_de_remonter():
    """CA14 — la distinction se fait d'elle-même : sans AUCUNE famille matchée
    (`chiffree is None`) — culture inconnue du potager — la cascade remonte
    encore vers le raisonnement, exactement comme avant US-170."""
    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=("Aucune donnée enregistrée pour physalis / recolte.", False, None),
        ) as mock_data,
        patch("llm.passerelle.appeler_chat", return_value=_reponse_llm("réponse d'expert")),
        patch.object(routeur, "_persister_routage_log", return_value=None),
    ):
        resultat = routeur.repondre_avec_cascade(CTX, "combien de physalis ai-je récolté ?")

    mock_data.assert_called_once()
    assert resultat.texte == "réponse d'expert"
    assert resultat.etage_resolveur == routeur.ETAGE_RAISONNEMENT


def test_us170_ca15_agent_sql_sans_famille_et_sans_confiance_remonte_aussi():
    """CA15 — le chemin de l'agent SQL (pas de famille, `chiffree=None`) qui
    n'a lui-même pas su répondre (`confiant=False`) déclenche toujours la
    remontée : son absence de confiance signifie réellement « je n'ai pas su »."""
    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=("Je ne sais pas répondre à cette question.", False, None),
        ),
        patch("llm.passerelle.appeler_chat", return_value=_reponse_llm("réponse d'expert")),
        patch.object(routeur, "_persister_routage_log", return_value=None),
    ):
        resultat = routeur.repondre_avec_cascade(CTX, "une question totalement inclassable")

    assert resultat.etage_resolveur == routeur.ETAGE_RAISONNEMENT


def test_us170_ca16_bot_ne_redemande_pas_des_donnees_quil_detient(test_db):
    """CA16 — bout en bout via le catalogue réel (potager 30 du 30/08/2026,
    reconstitué) : un concombre semé mais jamais récolté ne déclenche plus la
    question « précisez le nombre de plants, leur variété... » — le jardinier
    détient déjà cette information, la lui redemander était le symptôme."""
    test_db.add(_evenement(
        date=datetime(ANNEE, 4, 1), type_action="semis", culture="concombre",
        quantite=6, unite="graines", potager_id=1,
    ))
    test_db.commit()

    reponse = rc.repondre_chiffre(CTX, "quel ma production de concombre ?", db=test_db)

    assert reponse is not None
    assert reponse.present is False
    assert reponse.texte == "Je n'ai aucune récolte de concombre enregistrée cette saison."
    assert "?" not in reponse.texte
    assert "précisez" not in reponse.texte.lower()


def _reponse_llm(texte: str):
    from llm import passerelle
    return passerelle.ReponseLLM(texte=texte, modele="mock", appel_type=passerelle.TYPE_QUESTION)
