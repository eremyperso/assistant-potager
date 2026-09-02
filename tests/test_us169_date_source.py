"""
tests/test_us169_date_source.py
[US-169] Tracer l'origine de la date d'un évènement

Un test au moins par critère d'acceptance CA1 → CA12.

Cette US ne produit aucune nouvelle détection : elle fait descendre jusqu'à
l'écriture une valeur que `llm/parseur_deterministe.py` (US-094) calcule déjà
(chemin déterministe), et déduit celle du chemin modèle de deux signaux déjà
disponibles (`origine_parsing`, `date`) au site d'écriture unique
`app.services.evenements._date_source` — jamais d'un nouveau parsing de texte.
"""
from datetime import date
from pathlib import Path

import pytest

from app.services.context import TenantContext
from app.services.evenements import (
    _date_source,
    creer_evenement_confirme,
    creer_evenement_observation,
)
from database.models import CultureConfig, Evenement
from llm.parseur_deterministe import ORIGINE_DETERMINISTE, ORIGINE_LLM, parser_saisie
from utils.date_utils import (
    SOURCE_EXPLICITE,
    SOURCE_MODELE_INCERTAIN,
    SOURCE_PRESUMEE,
    SOURCE_RELATIVE_RESOLUE,
)

RACINE = Path(__file__).resolve().parent.parent

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUJOURD_HUI = date(2026, 8, 28)


@pytest.fixture
def potager(test_db):
    """Potager de test minimal : la culture 'tomate' connue et introduite,
    suffisant pour que `valider_evenement` (US-049) laisse passer les
    évènements construits ici. Pas de ligne `potagers` — comme dans les
    autres suites, la garde d'archivage laisse passer un potager absent."""
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=1))
    test_db.flush()
    test_db.add(Evenement(type_action="plantation", culture="tomate",
                          date=date(2026, 1, 1), potager_id=1))
    test_db.commit()
    return test_db


# ─────────────────────────────────────────────────────────────────────────────
# CA1, CA2 — la colonne : nullable, texte, sans défaut, migration séparée
# ─────────────────────────────────────────────────────────────────────────────

class TestCA1CA2Colonne:

    def test_ca1_nullable_sans_valeur_par_defaut(self, potager):
        event = Evenement(type_action="observation", commentaire="test",
                          date=date(2026, 8, 28), potager_id=1)
        potager.add(event)
        potager.commit()
        potager.refresh(event)
        assert event.date_source is None

    def test_ca2_migration_existe_separee_et_idempotente(self):
        migration = (RACINE / "migrations" / "migration_v35.sql").read_text(encoding="utf-8")
        rollback = (RACINE / "migrations" / "rollback_v35.sql").read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS date_source" in migration
        assert "DROP COLUMN IF EXISTS date_source" in rollback
        # Ne rouvre pas la migration d'US-094, livrée sur la même table.
        assert "ADD COLUMN IF NOT EXISTS origine_parsing" not in migration
        assert "DROP COLUMN IF EXISTS origine_parsing" not in rollback

    def test_ca2_pas_de_defaut_ni_de_contrainte_not_null(self):
        migration = (RACINE / "migrations" / "migration_v35.sql").read_text(encoding="utf-8")
        ligne_add = next(l for l in migration.splitlines() if "ADD COLUMN" in l)
        assert "DEFAULT" not in ligne_add.upper()
        assert "NOT NULL" not in ligne_add.upper()


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — taxonomie arrêtée avant l'implémentation
# ─────────────────────────────────────────────────────────────────────────────

class TestCA3Taxonomie:

    def test_ca3_quatre_valeurs_distinctes(self):
        """Au minimum : dictée en clair, relative résolue, jamais dictée —
        plus la 4e révélée par l'expérience d'US-094 (chemin modèle
        incertain), explicitement anticipée par CA3."""
        valeurs = {SOURCE_EXPLICITE, SOURCE_RELATIVE_RESOLUE,
                  SOURCE_PRESUMEE, SOURCE_MODELE_INCERTAIN}
        assert valeurs == {"explicite", "relative_resolue", "presumee", "modele_incertain"}

    def test_ca3_explicite_et_relative_resolue_reutilisees_d_us094(self):
        """CA3 n'invente rien pour ces deux valeurs : ce sont celles déjà
        calculées par `resoudre_ancrage_temporel` (US-094)."""
        from utils.date_utils import SOURCE_EXPLICITE as ANCRAGE_EXPLICITE
        from utils.date_utils import SOURCE_RELATIVE_RESOLUE as ANCRAGE_RELATIVE
        assert SOURCE_EXPLICITE == ANCRAGE_EXPLICITE
        assert SOURCE_RELATIVE_RESOLUE == ANCRAGE_RELATIVE


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — aucun backfill, l'historique reste NULL
# ─────────────────────────────────────────────────────────────────────────────

class TestCA4AucunBackfill:

    def test_ca4_evenement_historique_reste_a_null(self, potager):
        """Scénario Gherkin : l'historique n'est jamais reconstitué — les
        évènements enregistrés avant cette US gardent date_source à NULL,
        et rien ne tente de la déduire de leur texte original."""
        ancien = potager.query(Evenement).first()
        assert ancien.date_source is None

    def test_ca4_item_sans_signal_connu_ne_devine_rien(self):
        """Un item dont rien n'indique le chemin emprunté ne doit jamais se
        voir attribuer une valeur reconstituée, même si son texte porte une
        date en clair : `_date_source` ne relit jamais `texte_original`."""
        assert _date_source({"action": "observation", "date": "2026-08-20"}) is None


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — le chemin déterministe renseigne la valeur déjà établie
# ─────────────────────────────────────────────────────────────────────────────

class TestCA5CheminDeterministe:

    def test_ca5_date_dictee_en_clair(self, potager):
        """Scénario Gherkin : une date dictée en clair est tracée comme
        telle."""
        item = parser_saisie("récolté 2 kg de tomates le 25 mai", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        assert item["date"] == "2026-05-25"
        assert item["date_source"] == SOURCE_EXPLICITE
        event = creer_evenement_confirme(potager, CTX, item,
                                         "récolté 2 kg de tomates le 25 mai", None)
        assert event.date_source == SOURCE_EXPLICITE

    def test_ca5_date_relative_resolue(self, potager):
        item = parser_saisie("récolté 2 kg de tomates hier", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        assert item["date_source"] == SOURCE_RELATIVE_RESOLUE
        event = creer_evenement_confirme(potager, CTX, item,
                                         "récolté 2 kg de tomates hier", None)
        assert event.date_source == SOURCE_RELATIVE_RESOLUE

    def test_ca5_absence_d_ancrage_est_presumee(self, potager):
        """Scénario Gherkin : une absence d'ancrage est tracée comme
        présumée — sa date retombe sur la convention du projet, jamais sur
        NULL (qui voudrait dire « inconnu »)."""
        item = parser_saisie("récolté 2 kg de tomates", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        assert item["date"] is None
        assert item["date_source"] == SOURCE_PRESUMEE
        event = creer_evenement_confirme(potager, CTX, item,
                                         "récolté 2 kg de tomates", None)
        assert event.date_source == SOURCE_PRESUMEE

    def test_ca5_valeur_deja_calculee_jamais_recalculee(self):
        """CA5 : la valeur est déjà établie par la grammaire ; le site
        d'écriture ne fait que la lire, jamais la recalculer — même si
        `date` et `origine_parsing` du chemin modèle sont aussi présents."""
        item = {"date_source": SOURCE_EXPLICITE, "origine_parsing": ORIGINE_LLM,
                "date": "2026-05-20"}
        assert _date_source(item) == SOURCE_EXPLICITE


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — le chemin modèle n'affirme jamais ce qu'il ne peut pas savoir
# ─────────────────────────────────────────────────────────────────────────────

class TestCA6CheminModele:

    def test_ca6_modele_rend_une_date_origine_incertaine(self, potager):
        """Scénario Gherkin : le chemin modèle n'affirme jamais ce qu'il ne
        sait pas — y compris pour une saisie que la grammaire déterministe
        aurait vue mais jugée illisible (ANCRAGE_INCONNU) : ce cas rejoint
        lui aussi le modèle, et se voit attribuer la même valeur, faute de
        pouvoir le distinguer sans nouveau détecteur (CA6)."""
        item = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg",
                "date": "2026-05-20", "origine_parsing": ORIGINE_LLM}
        assert _date_source(item) == SOURCE_MODELE_INCERTAIN
        event = creer_evenement_confirme(potager, CTX, item,
                                         "récolté 2 kg de tomates il y a une semaine", None)
        assert event.date_source == SOURCE_MODELE_INCERTAIN
        assert event.date_source not in (SOURCE_EXPLICITE, SOURCE_RELATIVE_RESOLUE)

    def test_ca6_modele_sans_date_rejoint_le_site_de_repli(self, potager):
        """Le site de repli existant — celui qui pose déjà « aujourd'hui »
        faute de date — porte pour le chemin modèle la même valeur
        'presumee' que le chemin déterministe : même convention, même
        instrument de mesure."""
        item = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg",
                "origine_parsing": ORIGINE_LLM}
        assert _date_source(item) == SOURCE_PRESUMEE
        event = creer_evenement_confirme(potager, CTX, item,
                                         "récolté 2 kg de tomates", None)
        assert event.date_source == SOURCE_PRESUMEE

    def test_ca6_aucun_nouveau_detecteur_temporel_sur_ce_chemin(self):
        """CA6 : le site d'écriture ne relit jamais le texte — il ne lit que
        la présence ou non d'une date déjà rendue, jamais son contenu."""
        contenu = (RACINE / "app" / "services" / "evenements.py").read_text(encoding="utf-8")
        assert "resoudre_ancrage_temporel" not in contenu


# ─────────────────────────────────────────────────────────────────────────────
# CA7 — un chemin qui ne sait pas conclure reste à NULL
# ─────────────────────────────────────────────────────────────────────────────

class TestCA7CheminInconnuResteNull:

    def test_ca7_item_sans_origine_parsing_reste_a_null(self, potager):
        """Même une date présente ne suffit pas : sans savoir PAR QUEL
        CHEMIN elle est arrivée, aucune valeur n'est devinée."""
        item = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg",
                "date": "2026-05-20"}
        assert _date_source(item) is None
        event = creer_evenement_confirme(potager, CTX, item,
                                         "récolté 2 kg de tomates le 20 mai", None)
        assert event.date_source is None

    def test_ca7_observation_hors_perimetre_du_parseur_reste_a_null(self, potager):
        """Les observations (GESTES_NON_COUVERTS) n'empruntent aucun des
        deux chemins connus : NULL, jamais 'presumee' — les confondre
        rendrait la mesure fausse dans le sens qui arrange."""
        event = creer_evenement_observation(
            potager, CTX, {"culture": "tomate", "constat": "feuilles jaunes"},
            "note sur mes tomates", "NOTE",
        )
        assert event.date_source is None


# ─────────────────────────────────────────────────────────────────────────────
# CA8, CA9 — instrumentation seule
# ─────────────────────────────────────────────────────────────────────────────

class TestCA8CA9Instrumentation:

    def test_ca9_colonne_purement_instrumentale(self):
        """[CA8, CA9] Même invariant, même test que celui déjà en place pour
        `origine_parsing` (US-094 / CA10) : aucun service d'analyse, gabarit
        ou message utilisateur ne lit `date_source`. Scénario Gherkin : la
        colonne reste une instrumentation — aucune réponse ne diffère ni ne
        mentionne l'origine de la date."""
        interdits = [
            "app/services/reponses_chiffrees.py", "app/services/questions.py",
            "app/services/stock.py", "utils/stock.py", "llm/sql_agent.py", "bot.py",
        ]
        for chemin in interdits:
            contenu = (RACINE / chemin).read_text(encoding="utf-8")
            assert "date_source" not in contenu, f"{chemin} lit une colonne d'instrumentation"


# ─────────────────────────────────────────────────────────────────────────────
# CA10 — la mention « date présumée » reste hors périmètre
# ─────────────────────────────────────────────────────────────────────────────

class TestCA10ConfirmationInchangee:

    def test_ca10_aucune_mention_de_presomption_dans_bot(self):
        """Scénario Gherkin : aucun message n'annonce que la date a été
        présumée — toute saisie sans ancrage retombe sur aujourd'hui sans
        que l'affichage change."""
        contenu = (RACINE / "bot.py").read_text(encoding="utf-8").lower()
        assert "présum" not in contenu
        assert "presum" not in contenu


# ─────────────────────────────────────────────────────────────────────────────
# CA11, CA12 — la requête de croisement, seule raison d'être de l'US
# ─────────────────────────────────────────────────────────────────────────────

class TestCA11CA12RequeteDeCroisement:

    def test_ca11_requete_existe_hors_migrations_et_en_lecture_seule(self):
        chemin = RACINE / "tools" / "analyse_date_source.sql"
        assert chemin.exists()
        contenu = chemin.read_text(encoding="utf-8")
        assert "LECTURE SEULE" in contenu
        for mot in ("ALTER TABLE", "DROP TABLE", "DELETE FROM", "UPDATE evenements", "INSERT INTO"):
            assert mot not in contenu.upper()

    def test_ca11_croise_les_traces_corr(self):
        contenu = (RACINE / "tools" / "analyse_date_source.sql").read_text(encoding="utf-8")
        assert "[CORR" in contenu

    def test_ca12_croise_aussi_origine_parsing(self):
        """Les deux colonnes ensemble disent quel CHEMIN se trompe sur les
        dates, pas seulement combien de fois."""
        contenu = (RACINE / "tools" / "analyse_date_source.sql").read_text(encoding="utf-8")
        assert "origine_parsing" in contenu
        assert "date_source" in contenu
