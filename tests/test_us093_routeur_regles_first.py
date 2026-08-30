"""
tests/test_us093_routeur_regles_first.py
[US-093] Router les demandes par des règles avant tout appel au LLM

Couverture des critères d'acceptance CA1 → CA14. Aucun appel réseau : tout
appel modèle est intercepté via `llm.passerelle.appeler_chat`.

Le corpus `CORPUS_ROUTAGE` (CA9) est le livrable versionné exigé par l'US :
~100 formulations réalistes (mêmes tournures que les exemples déjà utilisés
dans `bot._CLASSIFY_PROMPT_FIXE` et dans les US déjà livrées), chacune avec
l'étage attendu. La majorité est résolue par les règles seules (CA2) ; une
frange volontairement ambiguë (aucun motif ne matche) est résolue par un petit
modèle mocké (CA4) ; quelques formulations réellement difficiles restent, en
connaissance de cause, mal aiguillées par les règles — sans quoi le seuil de
90 % (CA10) ne mesurerait rien.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.context import TenantContext
from llm import passerelle, routeur
from llm.passerelle import LLMIndisponibleError, ReponseLLM
from llm.routeur import (
    NATURE_ACTION,
    NATURE_QUESTION_DATA,
    NATURE_QUESTION_HYBRIDE,
    NATURE_QUESTION_SAVOIR,
    DecisionRoutage,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture(autouse=True)
def _cache_propre():
    """Aucun test ne doit hériter du cache de classification d'un autre."""
    routeur.vider_cache()
    yield
    routeur.vider_cache()


def _reponse_modele(texte: str) -> ReponseLLM:
    return ReponseLLM(texte=texte, modele="mock", appel_type=passerelle.TYPE_CLASSIFICATION)


# ─────────────────────────────────────────────────────────────────────────────
# CA9 — Corpus de routage (≥ 100 questions réelles) + seuil 90 %
# ─────────────────────────────────────────────────────────────────────────────

CORPUS_ROUTAGE: list[tuple[str, str]] = [
    # ── ACTION (verbe d'action en tête, pas de "?") ─────────────────────────
    ("récolté 2 kg de tomates", NATURE_ACTION),
    ("semé des carottes hier", NATURE_ACTION),
    ("planté 12 plants de poivrons en 3 rangs", NATURE_ACTION),
    ("arrosé les courgettes 30 minutes", NATURE_ACTION),
    ("paillé la parcelle nord", NATURE_ACTION),
    ("repiqué 20 plants de laitue", NATURE_ACTION),
    ("traité les tomates contre le mildiou", NATURE_ACTION),
    ("tuteuré les haricots", NATURE_ACTION),
    ("désherbé la parcelle sud", NATURE_ACTION),
    ("taillé les tomates", NATURE_ACTION),
    ("fertilisé le potager", NATURE_ACTION),
    ("observé des pucerons sur les choux", NATURE_ACTION),
    ("cueilli des framboises", NATURE_ACTION),
    ("ramassé les pommes de terre", NATURE_ACTION),
    ("mis en godet 20 tomates saint-pierre", NATURE_ACTION),
    ("/stats", NATURE_ACTION),
    ("/historique", NATURE_ACTION),
    ("/plan", NATURE_ACTION),
    ("/meteo", NATURE_ACTION),
    ("posé un paillage sur les fraises", NATURE_ACTION),
    ("installé un tuteur pour les tomates", NATURE_ACTION),
    ("sorti les plants de la serre", NATURE_ACTION),
    ("appliqué du purin d'ortie sur les tomates", NATURE_ACTION),
    ("constaté une attaque de doryphores", NATURE_ACTION),
    ("arrosage des radis ce matin", NATURE_ACTION),
    ("récolte 500g de carotte nantaise", NATURE_ACTION),
    ("semé des radis dans la parcelle est", NATURE_ACTION),
    ("planté des oignons blancs", NATURE_ACTION),
    ("traité les courgettes contre l'oïdium", NATURE_ACTION),
    ("mis en godet 5 plants de courgettes", NATURE_ACTION),

    # ── QUESTION_DATA (donnée déjà enregistrée dans CE potager) ─────────────
    ("combien de tomates ai-je récolté cette saison ?", NATURE_QUESTION_DATA),
    ("quand ai-je planté mes courgettes ?", NATURE_QUESTION_DATA),
    ("il me reste combien de tomates ?", NATURE_QUESTION_DATA),
    ("stock de carottes ?", NATURE_QUESTION_DATA),
    ("quel est mon stock de poivrons ?", NATURE_QUESTION_DATA),
    ("quelle est ma récolte de blettes ce mois-ci ?", NATURE_QUESTION_DATA),
    ("mes récoltes de blette", NATURE_QUESTION_DATA),
    ("quelle est ma dernière récolte de tomates ?", NATURE_QUESTION_DATA),
    ("quand a eu lieu mon dernier arrosage ?", NATURE_QUESTION_DATA),
    ("quelle est ma dernière plantation ?", NATURE_QUESTION_DATA),
    ("quel était mon dernier semis de radis ?", NATURE_QUESTION_DATA),
    ("quel est l'historique de mes arrosages ?", NATURE_QUESTION_DATA),
    ("historique de ma parcelle nord", NATURE_QUESTION_DATA),
    ("quelle quantité de mes tomates ai-je récolté ?", NATURE_QUESTION_DATA),
    ("quelle est la date de mes semis de carottes ?", NATURE_QUESTION_DATA),
    ("donne-moi la liste de mes plantations de mai", NATURE_QUESTION_DATA),
    ("montre-moi mes semis de radis", NATURE_QUESTION_DATA),
    ("quels sont mes traitements sur les poivrons ?", NATURE_QUESTION_DATA),
    ("combien ai-je perdu de plants ?", NATURE_QUESTION_DATA),
    ("combien j'ai récolté de courgettes cette semaine ?", NATURE_QUESTION_DATA),
    ("quand j'ai semé les radis ?", NATURE_QUESTION_DATA),
    ("il me manque combien de graines de radis ?", NATURE_QUESTION_DATA),
    ("mes stocks de légumes sont à combien ?", NATURE_QUESTION_DATA),
    ("combien de kg de courgettes ai-je récoltés cet été ?", NATURE_QUESTION_DATA),
    ("combien de litres d'eau ai-je utilisés cette semaine ?", NATURE_QUESTION_DATA),
    ("quelle quantité de ma récolte d'oignons ?", NATURE_QUESTION_DATA),
    ("date de ma dernière plantation de haricots", NATURE_QUESTION_DATA),
    ("liste de mon historique de traitements", NATURE_QUESTION_DATA),
    ("mes plantations de ce mois-ci", NATURE_QUESTION_DATA),
    ("mes traitements de la semaine dernière", NATURE_QUESTION_DATA),

    # ── QUESTION_SAVOIR (connaissance générale) ─────────────────────────────
    ("pourquoi mes tomates ont le cul noir ?", NATURE_QUESTION_SAVOIR),
    ("pourquoi mes courgettes jaunissent ?", NATURE_QUESTION_SAVOIR),
    ("pourquoi les feuilles de mes plants jaunissent ?", NATURE_QUESTION_SAVOIR),
    ("pourquoi mon poivron ne fleurit pas ?", NATURE_QUESTION_SAVOIR),
    ("comment fonctionne le calcul du stock ?", NATURE_QUESTION_SAVOIR),
    ("comment planter des tomates cerises ?", NATURE_QUESTION_SAVOIR),
    ("comment semer des carottes en pleine terre ?", NATURE_QUESTION_SAVOIR),
    ("comment soigner le mildiou sur les tomates ?", NATURE_QUESTION_SAVOIR),
    ("comment reconnaitre le mildiou ?", NATURE_QUESTION_SAVOIR),
    ("comment eviter les limaces sur les salades ?", NATURE_QUESTION_SAVOIR),
    ("comment arroser les tomates en été ?", NATURE_QUESTION_SAVOIR),
    ("comment faire une bonne rotation des cultures ?", NATURE_QUESTION_SAVOIR),
    ("c'est quoi le mildiou ?", NATURE_QUESTION_SAVOIR),
    ("qu'est-ce que la mise en godet ?", NATURE_QUESTION_SAVOIR),
    ("à quelle profondeur semer les carottes ?", NATURE_QUESTION_SAVOIR),
    ("quelle est la meilleure période pour semer les radis ?", NATURE_QUESTION_SAVOIR),
    ("quelle distance entre deux pieds de tomates ?", NATURE_QUESTION_SAVOIR),
    ("quelle variété choisir pour un sol argileux ?", NATURE_QUESTION_SAVOIR),
    ("quelle est la différence entre semis et repiquage ?", NATURE_QUESTION_SAVOIR),
    ("que faire contre les pucerons ?", NATURE_QUESTION_SAVOIR),
    ("quel traitement contre le mildiou ?", NATURE_QUESTION_SAVOIR),
    ("comment calculer le stock restant ?", NATURE_QUESTION_SAVOIR),
    ("pourquoi les tomates craquellent après la pluie ?", NATURE_QUESTION_SAVOIR),
    ("comment fonctionne le suivi des godets dans l'application ?", NATURE_QUESTION_SAVOIR),

    # ── QUESTION_HYBRIDE (donnée personnelle + demande de raisonnement) ────
    ("mes courgettes jaunissent et j'ai beaucoup arrosé cette semaine, qu'en penses-tu ?", NATURE_QUESTION_HYBRIDE),
    ("mes tomates ont des taches et j'ai traité hier, que penses-tu ?", NATURE_QUESTION_HYBRIDE),
    ("j'ai perdu plusieurs plants de salade cette semaine, à ton avis pourquoi ?", NATURE_QUESTION_HYBRIDE),
    ("mes plants de poivrons ne poussent plus, un conseil ?", NATURE_QUESTION_HYBRIDE),
    ("j'arrose beaucoup mes tomates mais elles jaunissent, que me conseilles-tu ?", NATURE_QUESTION_HYBRIDE),
    ("mes semis ne lèvent pas depuis 3 semaines, que dois-je faire ?", NATURE_QUESTION_HYBRIDE),
    ("mes courgettes ont des taches blanches, que faire d'après toi ?", NATURE_QUESTION_HYBRIDE),
    ("mes carottes ont un goût amer cette année, à ton avis c'est quoi le problème ?", NATURE_QUESTION_HYBRIDE),
    ("mes plants de tomates sont chétifs cette année, que me conseilles-tu de faire ?", NATURE_QUESTION_HYBRIDE),
    ("j'ai un problème avec mes aubergines, à ton avis qu'est-ce qui cloche ?", NATURE_QUESTION_HYBRIDE),

    # ── Frange ambiguë : aucune règle ne matche → petit modèle (mocké dans le
    # test comme correctement classé, sauf les 3 derniers, volontairement de
    # vrais cas difficiles où même la classification par règles se trompe) ──
    ("est-ce que mes plants de concombre vont bien cette année", NATURE_QUESTION_HYBRIDE),
    ("un point sur mes cultures en ce moment", NATURE_QUESTION_DATA),
    ("des nouvelles de mes tomates", NATURE_QUESTION_DATA),
    ("aide moi à comprendre le rendement de ma parcelle", NATURE_QUESTION_HYBRIDE),
    ("j'aimerais mieux connaître les associations de cultures possibles", NATURE_QUESTION_SAVOIR),
    ("j'aimerais des explications sur la rotation des cultures", NATURE_QUESTION_SAVOIR),
    ("dis moi tout sur le paillage", NATURE_QUESTION_SAVOIR),
    ("je voudrais comprendre pourquoi mes plants de tomates ont des taches noires et ce que je dois faire", NATURE_QUESTION_HYBRIDE),
    ("j'ai arrosé mes tomates ce matin, combien de temps dois-je attendre avant la récolte ?", NATURE_QUESTION_SAVOIR),
    ("stock de connaissances sur le mildiou ?", NATURE_QUESTION_SAVOIR),
]


def _mock_modele_corpus(**kwargs) -> ReponseLLM:
    """Simule un petit modèle qui classe correctement la frange ambiguë du
    corpus — sauf pour les 3 formulations volontairement difficiles, où les
    règles se trompent avant même d'atteindre le modèle (elles ne l'appellent
    donc jamais : ce mock ne les voit pas)."""
    texte = kwargs.get("message_utilisateur", "")
    attendu = dict(CORPUS_ROUTAGE).get(texte, NATURE_QUESTION_HYBRIDE)
    return _reponse_modele(f"{attendu}|0.9")


def test_us093_ca9_corpus_au_moins_100_questions():
    """CA9 : le corpus compte au moins 100 questions réelles."""
    assert len(CORPUS_ROUTAGE) >= 100


def test_us093_ca9_ca10_taux_bon_aiguillage_et_distribution():
    """CA9/CA10 : taux de bon aiguillage ≥ 90 % sur le corpus, distribution publiée."""
    resultats: list[DecisionRoutage] = []
    with patch("llm.passerelle.appeler_chat", side_effect=_mock_modele_corpus) as mock_modele:
        for texte, _ in CORPUS_ROUTAGE:
            resultats.append(routeur.classer_demande(texte, ctx=CTX))

    corrects = sum(
        1 for (_, attendu), decision in zip(CORPUS_ROUTAGE, resultats)
        if decision.nature == attendu
    )
    taux = corrects / len(CORPUS_ROUTAGE)

    distribution: dict[str, int] = {}
    for decision in resultats:
        distribution[decision.nature] = distribution.get(decision.nature, 0) + 1
    repartition_pct = {n: round(100 * c / len(resultats), 1) for n, c in distribution.items()}

    print(f"\n[US-093 / CA10] Taux de bon aiguillage mesuré : {taux:.1%} sur {len(CORPUS_ROUTAGE)} questions")
    print(f"[US-093 / CA10] Répartition réelle par nature : {repartition_pct}")
    print(f"[US-093 / CA12] Appels modèle consommés sur le corpus : {mock_modele.call_count} / {len(CORPUS_ROUTAGE)}")

    assert taux >= 0.90, f"Taux de bon aiguillage {taux:.1%} sous le seuil de 90 % (CA10)"
    # [CA12] La frange ambiguë (non résolue par règle/cache) reste minoritaire —
    # c'est elle, et elle seule, qui porte le coût de routage réel.
    assert mock_modele.call_count <= 15


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — quatre natures distinctes
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca1_quatre_natures_possibles():
    assert routeur.classer_demande("récolté 2 kg de tomates").nature == NATURE_ACTION
    assert routeur.classer_demande("combien de tomates ai-je récolté ?").nature == NATURE_QUESTION_DATA
    assert routeur.classer_demande("pourquoi mes tomates ont le cul noir ?").nature == NATURE_QUESTION_SAVOIR
    assert routeur.classer_demande("mes tomates jaunissent, qu'en penses-tu ?").nature == NATURE_QUESTION_HYBRIDE


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — règles d'abord, zéro appel modèle sur les formes fréquentes
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca2_regle_recoupe_sans_appel_modele():
    with patch("llm.passerelle.appeler_chat") as mock_modele:
        decision = routeur.classer_demande("il me reste combien de tomates ?")
    mock_modele.assert_not_called()
    assert decision.nature == NATURE_QUESTION_DATA
    assert decision.origine == "regle"
    assert decision.confiance == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# CA3 / CA4 — cache après une classification modèle, jamais reclassée
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca3_ca4_cache_evite_un_second_appel_modele():
    texte = "dis moi tout sur le paillage"  # ne matche aucune règle
    mock_reponse = _reponse_modele(f"{NATURE_QUESTION_SAVOIR}|0.85")

    with patch("llm.passerelle.appeler_chat", return_value=mock_reponse) as mock_modele:
        premiere = routeur.classer_demande(texte, ctx=CTX)
        seconde = routeur.classer_demande(texte, ctx=CTX)

    mock_modele.assert_called_once()  # [CA4] un seul appel modèle malgré 2 classifications
    assert premiere.origine == "modele"
    assert seconde.origine == "cache"
    assert premiere.nature == seconde.nature == NATURE_QUESTION_SAVOIR

    # [CA14] le type d'appel passe par la passerelle, jamais un modèle en dur —
    # le petit modèle rapide est résolu par configuration (GROQ_MODEL_CLASSIFICATION).
    assert mock_modele.call_args.kwargs["appel_type"] == passerelle.TYPE_CLASSIFICATION
    # [CA12] coût borné : le budget reste petit devant celui d'une réponse
    # (400 jetons pour l'étage raisonnement).
    #
    # Le seuil était fixé à 16, calibré sur la réponse attendue
    # « NATURE|confiance » qui tient en 8 jetons. C'était impossible à tenir :
    # `openai/gpt-oss-120b` émet des jetons de raisonnement avant son contenu,
    # et `max_tokens` plafonne les deux ensemble — le contenu revenait
    # systématiquement vide et le routeur repliait sur QUESTION_HYBRIDE/0.0.
    # Ce test passait néanmoins, la passerelle étant simulée : il vérifiait le
    # budget demandé, jamais qu'une classification en revenait. Découvert le
    # 27/08/2026 par le rejeu de corpus (Action 0), sur 210 classifications
    # réelles toutes à confiance 0.00.
    assert mock_modele.call_args.kwargs["max_tokens"] <= 200
    # Le plancher est le vrai garde-fou : sous ~120 jetons, le raisonnement
    # consomme tout le budget et le contenu revient vide.
    assert mock_modele.call_args.kwargs["max_tokens"] >= 120


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — confiance faible → étage le plus tolérant (hybride)
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca5_confiance_faible_bascule_hybride():
    texte = "un point sur mes cultures en ce moment"  # ne matche aucune règle
    mock_reponse = _reponse_modele(f"{NATURE_QUESTION_DATA}|0.3")

    with patch("llm.passerelle.appeler_chat", return_value=mock_reponse):
        decision = routeur.classer_demande(texte, ctx=CTX)

    assert decision.nature == NATURE_QUESTION_HYBRIDE
    assert decision.confiance == 0.3


def test_us093_edge_modele_indisponible_replie_hybride_sans_lever():
    """Une classification modèle qui échoue (Groq indisponible) ne doit jamais
    remonter d'exception au jardinier — repli hybride, confiance nulle."""
    texte = "dis moi tout sur le paillage"

    with patch("llm.passerelle.appeler_chat", side_effect=LLMIndisponibleError("indispo")):
        decision = routeur.classer_demande(texte, ctx=CTX)

    assert decision.nature == NATURE_QUESTION_HYBRIDE
    assert decision.confiance == 0.0
    assert decision.origine == "modele"


# ─────────────────────────────────────────────────────────────────────────────
# CA6 / CA7 / CA8 — remontée de cascade, un seul saut, invisible du jardinier
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca6_ca7_remontee_sur_donnee_absente():
    """Scénario Gherkin : "combien de physalis ai-je récolté ?" sans aucun
    événement de récolte de physalis → re-routée vers le raisonnement, une
    seule fois, sans exception."""
    question = "combien de physalis ai-je récolté ?"
    reponse_raisonnement = _reponse_modele(
        "Aucune récolte de physalis n'est enregistrée cette saison ; c'est une "
        "culture tardive, la récolte n'a peut-être pas encore eu lieu."
    )

    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=("Aucune donnée enregistrée pour physalis / recolte.", False, None),
        ) as mock_data,
        patch("llm.passerelle.appeler_chat", return_value=reponse_raisonnement) as mock_llm,
    ):
        resultat = routeur.repondre_avec_cascade(CTX, question)

    mock_data.assert_called_once()
    mock_llm.assert_called_once()  # [CA7] un seul saut, jamais répété
    assert resultat.texte == reponse_raisonnement.texte
    # [US-097] remontée de cascade correctement journalisée
    assert resultat.etage_resolveur == routeur.ETAGE_RAISONNEMENT
    # [CA8] aucun message intermédiaire — seule la réponse finale est renvoyée
    assert "cherche ailleurs" not in resultat.texte.lower()


def test_us093_ca6_pas_de_remontee_si_donnee_deja_exploitable():
    """Une réponse data confiante ne déclenche aucune remontée (pas d'appel LLM)."""
    question = "combien de tomates ai-je récolté cette saison ?"
    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=("Total tomate récolte : 4 kg", True, None),
        ),
        patch("llm.passerelle.appeler_chat") as mock_llm,
    ):
        resultat = routeur.repondre_avec_cascade(CTX, question)

    mock_llm.assert_not_called()
    assert resultat.texte == "Total tomate récolte : 4 kg"
    # [US-097] pas de remontée : l'étage donnée a directement résolu la demande
    assert resultat.etage_resolveur == routeur.ETAGE_DONNEE


def test_us093_edge_echec_llm_sur_etage_data_nest_pas_une_remontee():
    """[CA6] La remontée est déclenchée par un retour explicite « pas de
    donnée », jamais par une exception : une panne LLM sur l'extraction
    d'intention (étage data) doit se propager telle quelle, exactement comme
    avant cette US (US-092 / CA9, CA10), pas être avalée en silence."""
    question = "combien de tomates ai-je récolté cette saison ?"
    with patch(
        "app.services.questions.repondre_question_detaille",
        side_effect=LLMIndisponibleError("quota dépassé"),
    ):
        with pytest.raises(LLMIndisponibleError):
            routeur.repondre_avec_cascade(CTX, question)


# ─────────────────────────────────────────────────────────────────────────────
# CA11 — chaque décision porte nature / origine / confiance / latence
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca11_decision_journalisable():
    decision = routeur.classer_demande("récolté 2 kg de tomates")
    assert isinstance(decision, DecisionRoutage)
    assert decision.nature in {
        NATURE_ACTION, NATURE_QUESTION_DATA, NATURE_QUESTION_SAVOIR, NATURE_QUESTION_HYBRIDE,
    }
    assert decision.origine in {"regle", "cache", "modele"}
    assert isinstance(decision.confiance, float)
    assert isinstance(decision.latence_ms, int) and decision.latence_ms >= 0


# ─────────────────────────────────────────────────────────────────────────────
# CA13 — non-régression : le routeur ne s'insère jamais avant les gardes de
# conversation existantes (modes corr_*, mode ask, navigation, _is_question)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_us093_ca13_mode_correction_prioritaire_sur_le_routeur():
    """Un message qui ressemble à une question, reçu en pleine correction
    (mode corr_apply), doit rester traité par `_corr_apply` — le routeur ne
    doit jamais être atteint dans ce cas (CA13 / non-régression)."""
    from bot import handle_text

    update = MagicMock()
    update.message = AsyncMock()
    update.message.text = "combien de tomates ?"
    update.effective_user = MagicMock(id=999001)

    ctx = MagicMock()
    ctx.user_data = {"mode": "corr_apply", "corr_event_id": 1}

    with (
        patch("bot._verifier_liaison_ou_onboarding", new=AsyncMock(return_value=True)),
        patch("bot._corr_apply", new=AsyncMock()) as mock_corr_apply,
        patch("bot._ask_question", new=AsyncMock()) as mock_ask_question,
        patch("llm.routeur.classer_demande") as mock_classer,
    ):
        await handle_text(update, ctx)

    mock_corr_apply.assert_awaited_once()
    mock_ask_question.assert_not_called()
    mock_classer.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# CA14 — bascule vers le petit modèle configurable, jamais en dur
# ─────────────────────────────────────────────────────────────────────────────

def test_us093_ca14_appel_modele_configurable_via_passerelle():
    """Le routeur ne code jamais un nom de modèle en dur : il passe par
    `appel_type=TYPE_CLASSIFICATION`, résolu par la passerelle (US-092 / CA3)
    depuis `GROQ_MODEL_CLASSIFICATION` — un repli vers le grand modèle est donc
    une simple variable d'environnement, jamais une livraison de code."""
    texte = "dis moi tout sur le paillage"
    mock_reponse = _reponse_modele(f"{NATURE_QUESTION_SAVOIR}|0.8")

    with patch("llm.passerelle.appeler_chat", return_value=mock_reponse) as mock_modele:
        routeur.classer_demande(texte, ctx=CTX)

    _, kwargs = mock_modele.call_args
    assert kwargs["appel_type"] == passerelle.TYPE_CLASSIFICATION
    assert "modele" not in kwargs  # jamais de nom de modèle forcé depuis le routeur


# ─────────────────────────────────────────────────────────────────────────────
# Action 0 (vague 2) — une saisie dictée qui nomme un geste est une ACTION
# -----------------------------------------------------------------------------
# Le rejeu du corpus de production du 27/08/2026 a montré que 28 saisies sur
# 205 étaient classées QUESTION_DATA : `_VERBES_ACTION` teste un PRÉFIXE et
# rate donc les formes nominales (« plantation 14 plants… »), tandis que les
# marqueurs DATA sont testés par sous-chaîne n'importe où dans la phrase —
# « mise en godet 20 tomates » tombait sur le marqueur « en godet » ajouté par
# US-096. Conséquence : le jardinier recevait un agrégat SQL au lieu de voir
# son évènement enregistré.
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("texte", [
    "Mise en godet 20 tomate",
    "mise en godet 8 plants de blette sur 20 le 13/04",
    "plantation 14 plants de tomate coeur de boeuf le 25/05",
    "Binage effectué sur les rangs d'oignons il y a 4 jours",
    "Vente 1 courgette",
    "Perte 3 salades le 22/5",
    "Récolte 500 grammes de courgettes.",
])
def test_action0_saisie_dictee_nommant_un_geste_reste_une_action(texte):
    """Aucun appel modèle : la règle doit trancher seule, à coût nul."""
    with patch("llm.passerelle.appeler_chat") as mock_modele:
        decision = routeur.classer_demande(texte, ctx=CTX)
    mock_modele.assert_not_called()
    assert decision.nature == NATURE_ACTION
    assert decision.origine == "regle"


@pytest.mark.parametrize("texte", [
    "qu'est-ce qu'il y a en pépinière ?",
    "combien de plants de tomate en godet ?",
    "quel est le rendement de la saison ?",
])
def test_action0_questions_chiffrees_us096_restent_data(texte):
    """La règle geste ne doit pas manger les formulations qu'US-096 sert par
    gabarit : ce sont elles qui ont motivé l'ajout des marqueurs DATA."""
    with patch("llm.passerelle.appeler_chat") as mock_modele:
        decision = routeur.classer_demande(texte, ctx=CTX)
    mock_modele.assert_not_called()
    assert decision.nature == NATURE_QUESTION_DATA


@pytest.mark.parametrize("texte", [
    "pourquoi mes tomates jaunissent",
    "comment planter des poireaux",
])
def test_action0_marqueurs_savoir_gardent_la_priorite_sur_le_geste(texte):
    """« comment **planter** des poireaux » nomme un geste mais demande un
    savoir : les marqueurs explicites sont testés avant la règle geste."""
    with patch("llm.passerelle.appeler_chat") as mock_modele:
        decision = routeur.classer_demande(texte, ctx=CTX)
    mock_modele.assert_not_called()
    assert decision.nature == NATURE_QUESTION_SAVOIR


def test_action0_geste_en_subordonnee_ne_declenche_pas_la_regle():
    """Le geste doit être en tête. Dans une subordonnée de contexte, il décrit
    un repère temporel, pas la demande — cas mesuré sur le corpus CA11."""
    assert routeur._regle_par_geste(
        "mes asperges ont des petites bêtes noires sur les tiges après la récolte"
    ) is None
