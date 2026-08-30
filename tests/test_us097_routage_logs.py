"""
tests/test_us097_routage_logs.py
[US-097] Observabilité de la cascade de réponses — journal de routage et métriques

Couverture :
  CA1 : une entrée de journal par cascade menée à son terme
  CA2 : question normalisée journalisée, jamais le message brut
  CA3 : rétention 12 mois — purge par ancienneté
  CA4 : aucun secret / contenu de réponse dans le journal
  CA5 : métriques (taux de résolution, latence p95, jetons routage inclus,
        remontée de cascade, taux de service cache, part parseur déterministe)
  CA6 : répartition réelle confrontée aux hypothèses du document d'architecture
  CA7 : point d'accès en lecture réservé à l'administrateur (main.py)
  CA8 : aucune métrique n'appelle un modèle
"""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from app.services import metriques_routage as svc_metriques
from app.services.context import TenantContext
from database.models import ConsoTokens, RoutageLog, RoutageRetour
from llm import passerelle, routeur
from llm.passerelle import ReponseLLM

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture(autouse=True)
def _cache_propre():
    routeur.vider_cache()
    yield
    routeur.vider_cache()


@pytest.fixture
def routage_en_base(test_db):
    """Redirige l'écriture de `routage_logs` vers la base de test — même
    procédé que `conso_en_base` dans test_us092_passerelle_llm.py."""
    with patch("llm.routeur.SessionLocal", lambda: test_db):
        yield test_db


def _reponse_modele(texte: str) -> ReponseLLM:
    return ReponseLLM(
        texte=texte, modele="mock", appel_type=passerelle.TYPE_QUESTION,
        tokens_in=10, tokens_out=20,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CA1, CA2, CA4 — écriture du journal
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca1_entree_journal_creee_apres_reponse_donnee_confiante(routage_en_base):
    """Scénario Gherkin « Chaque demande laisse une trace exploitable »."""
    question = "combien de tomates ai-je récolté cette saison ?"
    with patch(
        "app.services.questions.repondre_question_detaille",
        return_value=("Total tomate récolte : 4 kg", True, None),
    ):
        resultat = routeur.repondre_avec_cascade(CTX, question)

    ligne = routage_en_base.query(RoutageLog).one()
    assert resultat.routage_log_id == ligne.id
    assert ligne.potager_id == CTX.potager_id
    assert ligne.nature == routeur.NATURE_QUESTION_DATA
    assert ligne.etage_resolveur == routeur.ETAGE_DONNEE
    assert ligne.cascade_remontee is False
    assert ligne.latence_ms >= 0
    assert ligne.tokens_consommes == 0  # étage donnée : 0 jeton (CA2 US-093)


def test_us097_ca1_remontee_de_cascade_journalisee(routage_en_base):
    """Scénario Gherkin « Répartition réelle par étage » (préparation) — une
    remontée data → raisonnement est marquée comme telle."""
    question = "combien de physalis ai-je récolté ?"
    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=("Rien trouvé.", False, None),
        ),
        patch("llm.passerelle.appeler_chat", return_value=_reponse_modele("Aucune récolte connue.")),
    ):
        resultat = routeur.repondre_avec_cascade(CTX, question)

    ligne = routage_en_base.query(RoutageLog).one()
    assert ligne.cascade_remontee is True
    assert ligne.etage_resolveur == routeur.ETAGE_RAISONNEMENT
    assert resultat.etage_resolveur == routeur.ETAGE_RAISONNEMENT


def test_us097_ca2_question_normalisee_pas_le_message_brut(routage_en_base):
    question_brute = "Combien de Tomates ai-je RÉCOLTÉ ?!"
    with patch(
        "app.services.questions.repondre_question_detaille",
        return_value=("4 kg", True, None),
    ):
        routeur.repondre_avec_cascade(CTX, question_brute)

    ligne = routage_en_base.query(RoutageLog).one()
    assert ligne.question_normalisee == routeur._normaliser_question(question_brute)
    assert ligne.question_normalisee != question_brute
    assert ligne.question_normalisee.islower()
    assert "?" not in ligne.question_normalisee


def test_us097_ca4_aucun_secret_ni_contenu_de_reponse_dans_le_journal(routage_en_base):
    """Le texte de la réponse (qui pourrait contenir un extrait de connaissance)
    ne doit apparaître dans AUCUNE colonne du journal."""
    question = "pourquoi mes tomates jaunissent ?"
    secret_dans_la_reponse = "sk-groq-SECRET-1234 ne doit jamais fuiter"
    with patch("llm.passerelle.appeler_chat", return_value=_reponse_modele(secret_dans_la_reponse)):
        routeur.repondre_avec_cascade(CTX, question)

    ligne = routage_en_base.query(RoutageLog).one()
    valeurs_texte = [
        str(v) for v in (
            ligne.question_normalisee, ligne.nature, ligne.origine_classification,
            ligne.etage_resolveur,
        )
    ]
    assert not any(secret_dans_la_reponse in v for v in valeurs_texte)


def test_us097_ca1_echec_de_reponse_ne_journalise_rien(routage_en_base):
    """Une cascade qui lève (IA indisponible) n'a rien produit : rien à
    journaliser — cohérent avec la note technique (l'écriture ne doit jamais
    faire échouer une réponse, pas l'inverse)."""
    from llm.passerelle import LLMIndisponibleError

    question = "pourquoi mes tomates jaunissent ?"
    with patch("llm.passerelle.appeler_chat", side_effect=LLMIndisponibleError("indispo")):
        with pytest.raises(LLMIndisponibleError):
            routeur.repondre_avec_cascade(CTX, question)

    assert routage_en_base.query(RoutageLog).count() == 0


def test_us097_ecriture_journal_en_echec_ne_casse_pas_la_reponse():
    """[Note technique] Une panne d'écriture du journal ne doit jamais
    empêcher la réponse d'être servie — `routage_log_id` est simplement
    `None`. Panne simulée explicitement (SessionLocal qui lève), plutôt que de
    compter sur l'absence incidente d'une table — cette dernière dépend de
    l'ordre de collecte des tests (bot.py crée déjà `routage_logs` sur
    l'engine réel dès qu'il est importé ailleurs dans la suite)."""
    question = "combien de tomates ai-je récolté cette saison ?"
    with (
        patch(
            "app.services.questions.repondre_question_detaille",
            return_value=("4 kg", True, None),
        ),
        patch("llm.routeur.SessionLocal", side_effect=RuntimeError("base indisponible")),
    ):
        resultat = routeur.repondre_avec_cascade(CTX, question)

    assert resultat.texte == "4 kg"
    assert resultat.routage_log_id is None


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — Métriques, zéro jeton
# ─────────────────────────────────────────────────────────────────────────────

def _log(db, **kwargs):
    defaults = dict(
        potager_id=1, question_normalisee="question", nature=routeur.NATURE_QUESTION_DATA,
        origine_classification=routeur.ORIGINE_REGLE, etage_resolveur=routeur.ETAGE_DONNEE,
        cascade_remontee=False, confiance=1.0, latence_ms=100, tokens_consommes=0,
    )
    defaults.update(kwargs)
    ligne = RoutageLog(**defaults)
    db.add(ligne)
    db.commit()
    db.refresh(ligne)
    return ligne


class TestCA5MetriquesParEtage:

    def test_us097_ca5_taux_resolution_et_latence_p95_par_etage(self, test_db):
        for latence in [100, 200, 300, 400, 1000]:
            _log(test_db, etage_resolveur=routeur.ETAGE_DONNEE, latence_ms=latence)
        _log(test_db, etage_resolveur=routeur.ETAGE_RAISONNEMENT, latence_ms=500)

        resume = svc_metriques.resume_par_etage(test_db)

        assert resume[routeur.ETAGE_DONNEE]["nb_reponses"] == 5
        assert resume[routeur.ETAGE_DONNEE]["taux_resolution"] == pytest.approx(5 / 6)
        assert resume[routeur.ETAGE_DONNEE]["latence_p95_ms"] == 1000
        assert resume[routeur.ETAGE_RAISONNEMENT]["nb_reponses"] == 1
        # Étage jamais observé (savoir non livré) : présent, à zéro, pas absent.
        assert resume[routeur.ETAGE_SAVOIR]["nb_reponses"] == 0
        assert resume[routeur.ETAGE_SAVOIR]["latence_p95_ms"] is None

    def test_us097_ca5_jetons_moyens_par_question_routage_inclus(self, test_db):
        _log(test_db, tokens_consommes=100)
        _log(test_db, tokens_consommes=300)

        assert svc_metriques.jetons_moyens_par_question(test_db) == pytest.approx(200.0)

    def test_us097_ca5_jetons_moyens_none_si_aucune_donnee(self, test_db):
        assert svc_metriques.jetons_moyens_par_question(test_db) is None

    def test_us097_ca5_taux_remontee_cascade(self, test_db):
        _log(test_db, cascade_remontee=True)
        _log(test_db, cascade_remontee=False)
        _log(test_db, cascade_remontee=False)

        assert svc_metriques.taux_remontee_cascade(test_db) == pytest.approx(1 / 3)

    def test_us097_ca5_taux_service_cache(self, test_db):
        _log(test_db, origine_classification=routeur.ORIGINE_CACHE)
        _log(test_db, origine_classification=routeur.ORIGINE_REGLE)
        _log(test_db, origine_classification=routeur.ORIGINE_MODELE)
        _log(test_db, origine_classification=routeur.ORIGINE_MODELE)

        assert svc_metriques.taux_service_cache(test_db) == pytest.approx(1 / 4)

    def test_us097_ca5_taux_zero_sur_periode_vide(self, test_db):
        assert svc_metriques.taux_remontee_cascade(test_db) == 0.0
        assert svc_metriques.taux_service_cache(test_db) == 0.0

    def test_us097_ca5_part_parseur_deterministe_zero_tant_que_us094_absente(self, test_db):
        """US-094 (parseur déterministe) n'est pas livrée : toute saisie
        d'action mesurée l'est aujourd'hui via l'appel modèle 'parsing'."""
        test_db.add(ConsoTokens(
            potager_id=1, date=datetime.utcnow().date(), appel_type=passerelle.TYPE_PARSING,
            modele="mock", tokens_in=10, tokens_out=5, issue=passerelle.ISSUE_OK,
        ))
        test_db.commit()

        assert svc_metriques.part_parseur_deterministe(test_db) == 0.0

    def test_us097_ca5_part_parseur_deterministe_none_si_aucune_saisie(self, test_db):
        assert svc_metriques.part_parseur_deterministe(test_db) is None


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — Comparaison aux hypothèses du document d'architecture
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca6_repartition_reelle_confrontee_aux_hypotheses(test_db):
    """Scénario Gherkin « Répartition réelle par étage »."""
    for _ in range(6):
        _log(test_db, nature=routeur.NATURE_QUESTION_DATA)
    for _ in range(3):
        _log(test_db, nature=routeur.NATURE_QUESTION_SAVOIR)
    _log(test_db, nature=routeur.NATURE_QUESTION_HYBRIDE)

    resultat = svc_metriques.comparaison_hypotheses(test_db)

    assert resultat["hypotheses"] == svc_metriques.HYPOTHESES_REPARTITION
    assert resultat["reel_par_nature"][routeur.NATURE_QUESTION_DATA] == pytest.approx(0.6)
    assert resultat["reel_par_nature"][routeur.NATURE_QUESTION_SAVOIR] == pytest.approx(0.3)
    assert resultat["reel_par_nature"][routeur.NATURE_QUESTION_HYBRIDE] == pytest.approx(0.1)
    assert "note" in resultat and resultat["note"]


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — Rétention 12 mois
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca3_purge_retention_supprime_les_entrees_expirees(test_db):
    maintenant = datetime.utcnow()
    ancienne = _log(test_db, cree_le=maintenant - timedelta(days=400))
    recente = _log(test_db, cree_le=maintenant - timedelta(days=10))
    test_db.add(RoutageRetour(routage_log_id=ancienne.id, potager_id=1, avis="negatif"))
    test_db.commit()

    nb = svc_metriques.purger_routage_logs_expires(test_db, maintenant=maintenant)

    assert nb == 1
    ids_restants = [l.id for l in test_db.query(RoutageLog).all()]
    assert ids_restants == [recente.id]
    assert test_db.query(RoutageRetour).count() == 0  # le retour rattaché disparaît aussi


def test_us097_ca3_purge_retention_rejouable_sans_rien_a_purger(test_db):
    _log(test_db, cree_le=datetime.utcnow())
    assert svc_metriques.purger_routage_logs_expires(test_db) == 0


# ─────────────────────────────────────────────────────────────────────────────
# CA8 — Zéro jeton : aucune fonction de ce module n'appelle un modèle
# ─────────────────────────────────────────────────────────────────────────────

def test_us097_ca8_metriques_zero_jeton(test_db):
    _log(test_db)
    with patch("llm.passerelle.appeler_chat") as mock_llm:
        svc_metriques.resume_par_etage(test_db)
        svc_metriques.jetons_moyens_par_question(test_db)
        svc_metriques.taux_remontee_cascade(test_db)
        svc_metriques.taux_service_cache(test_db)
        svc_metriques.part_parseur_deterministe(test_db)
        svc_metriques.comparaison_hypotheses(test_db)
        svc_metriques.top_questions_mal_notees(test_db)
    mock_llm.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# CA7 — Point d'accès en lecture réservé à l'administrateur (main.py)
# -----------------------------------------------------------------------------
# `require_admin_user` est une fonction Python ordinaire (dépendance FastAPI) :
# on l'appelle directement, sans passer par TestClient — cette base de code
# n'a pas d'engine SQLite partagé entre threads pour les tests d'endpoint
# complets (limitation préexistante, voir les échecs déjà présents sur
# tests/test_api.py hors de toute modification US-097).
# ─────────────────────────────────────────────────────────────────────────────

class TestCA7AccesAdministrateur:

    def test_us097_ca7_admin_reconnu_par_email(self, monkeypatch):
        from fastapi import HTTPException
        from main import require_admin_user
        from database.models import User

        monkeypatch.setattr("main.ADMIN_EMAIL", "admin@example.com")
        admin = User(id=1, email="Admin@Example.com")  # casse différente : insensible à la casse
        assert require_admin_user(admin) is admin

    def test_us097_ca7_non_admin_refuse(self, monkeypatch):
        from fastapi import HTTPException
        from main import require_admin_user
        from database.models import User

        monkeypatch.setattr("main.ADMIN_EMAIL", "admin@example.com")
        autre = User(id=2, email="jardinier@example.com")
        with pytest.raises(HTTPException) as err:
            require_admin_user(autre)
        assert err.value.status_code == 403

    def test_us097_ca7_admin_email_absent_refuse_tout_le_monde(self, monkeypatch):
        from fastapi import HTTPException
        from main import require_admin_user
        from database.models import User

        monkeypatch.setattr("main.ADMIN_EMAIL", "")
        with pytest.raises(HTTPException) as err:
            require_admin_user(User(id=1, email="admin@example.com"))
        assert err.value.status_code == 403

    def test_us097_ca7_metriques_endpoint_retourne_un_dict_pas_un_gabarit_html(self, test_db):
        """[Arbitrage tranché] Un point d'accès JSON documenté, pas un écran :
        appel direct de la fonction d'endpoint (même limitation TestClient que
        ci-dessus), elle doit renvoyer une structure de données brute."""
        from unittest.mock import patch as _patch
        import main as main_module

        with _patch("main.SessionLocal", return_value=test_db):
            corps = main_module.admin_routage_metriques(_admin=None)
        assert isinstance(corps, dict)
        assert "par_etage" in corps and "comparaison_hypotheses" in corps
