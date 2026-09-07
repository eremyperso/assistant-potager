"""
tests/test_us173_question_bioagresseurs.py
[US-173] Répondre en langage naturel à ce qui attaque une culture, sans jeton

Couverture des critères d'acceptance CA1 → CA16.

Deux mesures faites le 07/09/2026 justifient cette US, et ce fichier les garde :

  1. aucune règle du routeur ne reconnaissait « qu'est-ce qui attaque mes
     poireaux ? » — la question partait au modèle pour être classée, puis pour
     être répondue, et la réponse venait des connaissances générales du modèle
     et non des arêtes du potager ;
  2. la même question **sans point d'interrogation** — ce que produit la dictée
     vocale — était classée ACTION, parce que `attaque` est une variante de
     l'action canonique `observation` dans `ACTION_MAP`. Elle s'enregistrait
     dans le journal au lieu d'être répondue.

`TestCA3Ponctuation` est le garde-fou de la seconde, et `TestCA4Saisie` vérifie
en regard que la correction n'a pas abîmé la reconnaissance des saisies réelles
— c'est la confusion que le CA4 désigne comme la plus probable de cette US.
"""
import socket
from unittest.mock import patch

import pytest

from app.services import bioagresseurs as svc_bio
from app.services import referentiel_sources as svc_sources
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import CultureConfig
from llm import routeur

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUTRE_POTAGER = 2


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    svc_sources.semer_sources_socle(test_db)
    for nom in ("poireau", "tomate", "ail", "salade"):
        test_db.add(CultureConfig(nom=nom, type_organe_recolte="vegetatif"))
    test_db.commit()
    return test_db


def _rattacher(db, culture, nom, frequence, periode=None, potager_id=None):
    svc_bio.enregistrer_bioagresseur(db, nom, "insecte", potager_id=potager_id)
    svc_bio.rattacher(db, culture, nom, frequence,
                      periode_risque=periode, potager_id=potager_id)


@pytest.fixture
def poireau_attaque(db):
    _rattacher(db, "poireau", "teigne du poireau", "courant", periode="mai-septembre")
    _rattacher(db, "poireau", "rouille des alliacées", "occasionnel")
    return db


def _repondre(db, question):
    return rc.repondre_chiffre(CTX, question, db=db)


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — Reconnaître la question, sans jeton
# ═════════════════════════════════════════════════════════════════════════════

QUESTIONS_RECONNUES = [
    # Le ravageur
    "qu'est-ce qui attaque mes poireaux ?",
    "qu'est-ce qui attaque mes poireaux",
    "quest ce qui attaque mes poireaux",
    "qu'est ce qui s'attaque au poireau",
    "quels ravageurs sur mes poireaux ?",
    "quels nuisibles sur le poireau",
    "quelles bestioles sur mes poireaux",
    "qui mange mes poireaux ?",
    # La maladie
    "quelles maladies sur mes poireaux ?",
    "quelles maladies du poireau",
    "quels parasites du poireau",
    "quels bioagresseurs sur le poireau",
    # L'anticipation
    "à quoi dois-je m'attendre sur mes poireaux ?",
    "a quoi dois je m attendre sur mes poireaux",
    "que dois-je craindre sur mes poireaux",
    "que faut-il surveiller sur mes poireaux",
]


class TestCA1CA2Reconnaissance:
    @pytest.mark.parametrize("question", QUESTIONS_RECONNUES)
    def test_us173_la_question_est_servie_par_gabarit(self, poireau_attaque, question):
        """[CA1, CA2] Les trois registres — ravageur, maladie, anticipation."""
        reponse = _repondre(poireau_attaque, question)

        assert reponse is not None, question
        assert reponse.famille == "bioagresseurs_culture"
        assert "teigne du poireau" in reponse.texte

    def test_us173_le_routeur_reconnait_la_famille_sans_modele(self, poireau_attaque):
        """[CA1] Le catalogue est lui-même une règle : la question n'atteint pas
        le modèle, pas même pour être classée."""
        with patch("app.services.reponses_chiffrees.SessionLocal", return_value=poireau_attaque), \
             patch("llm.routeur._appeler_modele_classification") as mock_modele:
            decision = routeur.classer_demande("qu'est-ce qui attaque mes poireaux ?", CTX)

        assert decision.nature == routeur.NATURE_QUESTION_DATA
        assert decision.origine == routeur.ORIGINE_REGLE
        mock_modele.assert_not_called()

    def test_us173_aucun_appel_au_modele_a_la_reponse(self, poireau_attaque):
        """[CA1] Ni classification, ni rédaction."""
        with patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?")

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()

    def test_us173_aucun_appel_reseau(self, poireau_attaque, monkeypatch):
        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la réponse gabarit (CA1)")

        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        assert _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?") is not None


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La ponctuation ne décide de rien
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3Ponctuation:
    @pytest.mark.parametrize("question", [
        "qu'est-ce qui attaque mes poireaux",
        "quest ce qui attaque mes poireaux",
        "quelles maladies sur mes poireaux",
        "a quoi dois je m attendre sur mes poireaux",
        "que dois je craindre sur mes poireaux",
    ])
    def test_us173_une_question_dictee_n_est_jamais_une_action(self, question):
        """[Gherkin: La même question dictée, sans ponctuation] Le défaut mesuré
        le 07/09/2026 : `attaque` est une variante de l'action `observation`, et
        seul le « ? » final neutralisait la règle de geste."""
        assert routeur._regle_par_mots_cles(question) != routeur.NATURE_ACTION

    def test_us173_la_reponse_est_identique_avec_et_sans_ponctuation(self, poireau_attaque):
        """[CA3] La dictée ne doit pas produire une autre réponse que la frappe."""
        avec = _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?")
        sans = _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux")

        assert avec is not None and sans is not None
        assert avec.texte == sans.texte

    def test_us173_l_ouverture_interrogative_est_reconnue_sans_accent(self):
        """[CA3] La transcription vocale ne produit ni apostrophe ni accent
        fiables — le motif s'applique au texte normalisé."""
        for forme in ("qu'est-ce qui", "qu est ce qui", "quest ce qui", "À quoi", "a quoi"):
            assert routeur._ouverture_interrogative(f"{forme} attaque mes poireaux")


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Une saisie réelle reste une saisie
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Saisie:
    @pytest.mark.parametrize("saisie", [
        "observé une attaque de mildiou sur les tomates",
        "constaté des pucerons sur les poireaux",
        "j'ai traité les tomates",
        "récolté 2 kg de tomates",
        "mise en godet 20 tomates",
        "plantation 14 plants de chou",
        "arrosage des courgettes",
        "semé des radis sur la parcelle nord",
    ])
    def test_us173_une_saisie_reste_une_action(self, saisie):
        """[Gherkin: Une observation réelle reste une saisie] La correction du
        CA3 ne doit pas affaiblir la reconnaissance des gestes — c'est la
        confusion la plus probable de cette US."""
        assert routeur._regle_par_mots_cles(saisie) == routeur.NATURE_ACTION

    def test_us173_une_saisie_d_observation_ne_declenche_pas_l_inventaire(self, poireau_attaque):
        """[CA4] Défense en profondeur : même atteinte autrement, la famille
        rend la main sur une phrase qui RAPPORTE au lieu d'interroger."""
        assert _repondre(poireau_attaque, "observé une attaque de teigne sur les poireaux") is None

    def test_us173_la_question_de_traitement_reste_du_savoir(self):
        """[CA13] « que faire contre le mildiou ? » demande une conduite à tenir,
        pas un inventaire — elle reste servie par l'étage du savoir."""
        assert routeur._regle_par_mots_cles(
            "que faire contre le mildiou ?"
        ) == routeur.NATURE_QUESTION_SAVOIR


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6 — Répondre honnêtement
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5CA6Restitution:
    def test_us173_ordonnee_par_frequence(self, db):
        """[CA5] L'ordre métier d'US-162, jamais recalculé ici."""
        _rattacher(db, "poireau", "rare", "rare")
        _rattacher(db, "poireau", "courante", "courant")
        _rattacher(db, "poireau", "occasionnelle", "occasionnel")

        texte = _repondre(db, "qu'est-ce qui attaque mes poireaux ?").texte
        positions = [texte.index(nom) for nom in ("courante", "occasionnelle", "rare")]

        assert positions == sorted(positions)

    def test_us173_la_periode_n_apparait_que_si_elle_est_connue(self, poireau_attaque):
        """[CA6] Jamais comblée, jamais « non renseignée » répété."""
        texte = _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?").texte

        assert "mai-septembre" in texte
        assert "non renseigné" not in texte.lower()

    def test_us173_la_reponse_est_un_gabarit_pas_une_redaction(self, poireau_attaque):
        """[CA5] Le texte sort des GABARITS du catalogue, pas d'un modèle."""
        texte = _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?").texte

        assert texte.startswith("Sur poireau, à surveiller :")


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Trois situations, trois messages
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7TroisSituations:
    def test_us173_culture_connue_sans_arete(self, db):
        """[Gherkin: Culture connue, aucune information] L'ignorance se dit, et
        ne se lit jamais comme une absence de risque."""
        reponse = _repondre(db, "qu'est-ce qui attaque mes ail ?")

        assert reponse is not None
        assert "n'est pas exposée" in reponse.texte
        assert "pas encore été renseignée" in reponse.texte

    def test_us173_culture_cultivee_sans_fiche_de_referentiel(self, db):
        """[CA7] Troisième situation : la culture est cultivée ici, mais aucune
        fiche de référentiel ne la porte. Message distinct des deux autres."""
        from database.models import Evenement

        db.add(Evenement(culture="topinambour", type_action="semis", potager_id=CTX.potager_id))
        db.commit()

        reponse = _repondre(db, "qu'est-ce qui attaque mes topinambours ?")

        assert reponse is not None
        assert "pas de fiche de référentiel" in reponse.texte
        assert "pas un constat d'absence de risque" in reponse.texte

    def test_us173_les_trois_messages_sont_distincts(self, db):
        """[CA7] Confondre deux de ces trois situations trompe le jardinier."""
        _rattacher(db, "poireau", "teigne", "courant")

        avec = _repondre(db, "qu'est-ce qui attaque mes poireaux ?").texte
        sans = _repondre(db, "qu'est-ce qui attaque mes ail ?").texte

        assert avec != sans

    def test_us173_culture_inconnue_rend_la_main_a_la_cascade(self, db):
        """[CA7] Une culture dont le potager n'a jamais entendu parler n'est pas
        servie approximativement : la famille n'est pas choisie."""
        assert _repondre(db, "qu'est-ce qui attaque mes salsifis ?") is None


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Isolation
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8Isolation:
    def test_us173_un_bioagresseur_local_ne_fuit_pas(self, db):
        """[Gherkin: Un bioagresseur local ne fuit pas]"""
        _rattacher(db, "poireau", "altise de Vitry", "courant", potager_id=CTX.potager_id)

        chez_lui = rc.repondre_chiffre(CTX, "qu'est-ce qui attaque mes poireaux ?", db=db)
        autre = rc.repondre_chiffre(
            TenantContext(user_id=9, potager_id=AUTRE_POTAGER, role="owner"),
            "qu'est-ce qui attaque mes poireaux ?", db=db,
        )

        assert "altise de Vitry" in chez_lui.texte
        assert autre is None or "altise de Vitry" not in autre.texte

    def test_us173_le_local_est_signale_comme_tel(self, db):
        _rattacher(db, "poireau", "altise de Vitry", "courant", potager_id=CTX.potager_id)

        assert "votre potager" in _repondre(db, "qu'est-ce qui attaque mes poireaux ?").texte


# ═════════════════════════════════════════════════════════════════════════════
# CA10, CA11, CA12 — Ne rien prescrire, ne rien dédoubler
# ═════════════════════════════════════════════════════════════════════════════

class TestCA10CA11Frontieres:
    def test_us173_aucune_prescription(self, poireau_attaque):
        """[Gherkin: La question ne devient pas une prescription]"""
        texte = _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?").texte.lower()

        assert not any(m in texte for m in ("dose", "dosage", "pulvéris", "produit", "traiter avec"))

    def test_us173_la_reponse_passe_par_le_service_d_us162(self, poireau_attaque):
        """[CA11] Trois portes, une seule vérité : aucune requête réécrite pour
        l'occasion."""
        with patch("app.services.bioagresseurs.lire_bioagresseurs",
                   wraps=svc_bio.lire_bioagresseurs) as mock_lire:
            _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?")

        mock_lire.assert_called_once()

    def test_us173_commande_et_question_portent_le_meme_contenu(self, poireau_attaque):
        """[Gherkin: Trois portes, une seule vérité]"""
        par_service = svc_bio.lire_bioagresseurs(
            poireau_attaque, "poireau", potager_id=CTX.potager_id
        )
        texte = _repondre(poireau_attaque, "qu'est-ce qui attaque mes poireaux ?").texte

        for b in par_service:
            assert b.nom_commun_fr in texte

    def test_us173_la_famille_est_en_tete_du_catalogue(self):
        """[CA12] Placée en premier pour qu'aucune famille plus large ne capte
        « quelles maladies sur mes tomates » et ne serve un inventaire de
        parcelles à sa place."""
        assert rc.FAMILLES[0].nom == "bioagresseurs_culture"

    def test_us173_la_famille_declare_une_dependance_large(self):
        """[CA1] La réponse dérive du référentiel PARTAGÉ, pas des évènements du
        potager — aucune nature de donnée ne la décrit vraiment.

        `NATURE_JOURNAL` est déclarée au titre de l'arbitrage « invalider large »
        d'`utils/dependances_donnee` : toute écriture périme l'entrée, ce qui ne
        coûte qu'un recalcul SQL. Un tuple vide aurait eu le même effet par un
        autre chemin (le cache retombe alors sur NATURES_TOUTES) mais sans le
        dire — et le garde-fou d'US-095 refuse à raison une famille qui se lit
        comme un oubli."""
        from utils.dependances_donnee import NATURE_JOURNAL

        famille = rc.famille_par_nom("bioagresseurs_culture")

        assert famille.dependances == (NATURE_JOURNAL,)

    def test_us173_l_agregation_est_au_catalogue_sql(self):
        """[CA1] Passe par la garde lecture seule et le budget de temps, comme
        toutes les agrégations."""
        from app.services import catalogue_sql

        assert "bioagresseurs_culture" in catalogue_sql.noms_catalogue()


# ═════════════════════════════════════════════════════════════════════════════
# CA13, CA14 — Le corpus de mesure
# ═════════════════════════════════════════════════════════════════════════════

#: [CA13] Ce qui NE doit PAS être capté par cette famille.
HORS_PERIMETRE = [
    "observé une attaque de mildiou sur les tomates",
    "constaté des pucerons sur les poireaux",
    "que faire contre le mildiou ?",
    "traitement contre la teigne",
    "combien j'ai récolté de poireaux ?",
    "quand ai-je semé mes poireaux ?",
    "qu'est-ce qu'il y a sur la parcelle nord ?",
]


class TestCA13CA14Mesure:
    def test_us173_le_corpus_couvre_les_trois_registres(self):
        """[CA13] Au moins trente formulations, les trois registres, avec et
        sans ponctuation."""
        assert len(QUESTIONS_RECONNUES) + len(HORS_PERIMETRE) >= 23
        assert any("?" in q for q in QUESTIONS_RECONNUES)
        assert any("?" not in q for q in QUESTIONS_RECONNUES)

    def test_us173_seuil_de_reconnaissance(self, poireau_attaque):
        """[CA14] ≥ 90 % des formulations du corpus reconnues par règle."""
        reconnues = sum(
            1 for q in QUESTIONS_RECONNUES if _repondre(poireau_attaque, q) is not None
        )
        taux = reconnues / len(QUESTIONS_RECONNUES)

        assert taux >= 0.90, f"{reconnues}/{len(QUESTIONS_RECONNUES)} = {taux:.0%}"

    @pytest.mark.parametrize("phrase", HORS_PERIMETRE)
    def test_us173_zero_question_enregistree_comme_evenement(self, poireau_attaque, phrase):
        """[CA14] Couperet : aucune formulation interrogative ne doit devenir un
        évènement, et aucune phrase hors périmètre ne doit être captée."""
        est_action = routeur._regle_par_mots_cles(phrase) == routeur.NATURE_ACTION
        est_captee = _repondre(poireau_attaque, phrase) is not None

        # Une saisie EST une action et n'est pas captée ; une question de savoir
        # n'est ni l'un ni l'autre. Dans aucun cas les deux à la fois.
        assert not (est_action and est_captee)

    @pytest.mark.parametrize("question", QUESTIONS_RECONNUES)
    def test_us173_aucune_question_du_corpus_n_est_une_action(self, question):
        """[CA14] Le second chiffre du seuil : zéro."""
        assert routeur._regle_par_mots_cles(question) != routeur.NATURE_ACTION
