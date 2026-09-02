"""
tests/test_us094_parseur_deterministe.py
[US-094] Enregistrer les saisies courantes sans appel au LLM

Un test au moins par critère d'acceptance CA1 → CA12. Aucun appel réseau : la
passerelle est interceptée partout, et les deux tests structurants vérifient
justement qu'elle n'est **jamais** sollicitée sur le chemin déterministe.

Les deux tests qui portent l'US :

* `TestCA5Couverture` — la couverture est mesurée sur le corpus de saisies
  RÉELLES versionné dans `tests/corpus/`, pas sur des phrases imaginées.
* `TestCA6Precision` — test différentiel : le corpus porte les champs
  réellement enregistrés par le chemin modèle ; le parseur doit produire les
  mêmes, champ à champ, sur les phrases qu'il prétend couvrir. Les rares
  écarts sont énumérés et justifiés un par un, jamais tolérés en masse.
"""
import csv
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.context import TenantContext
from app.services.evenements import (
    CultureInconnueError,
    _normalize_unite_denombrement,
    _normalize_unite_semis,
    creer_evenement_confirme,
)
from database.models import CultureConfig, Evenement, Parcelle
from llm.parseur_deterministe import (
    GESTES_COUVERTS,
    ORIGINE_DETERMINISTE,
    ORIGINE_LLM,
    parser_saisie,
)
from utils.actions import ACTION_MAP, normalize_action
from utils.date_utils import (
    ANCRAGE_ABSENT,
    ANCRAGE_INCONNU,
    ANCRAGE_RESOLU,
    SOURCE_EXPLICITE,
    SOURCE_RELATIVE_RESOLUE,
    resoudre_ancrage_temporel,
)
from utils.parcelles import normalize_parcelle_name

RACINE = Path(__file__).resolve().parent.parent
CORPUS = RACINE / "tests" / "corpus" / "us094_saisies_reelles.csv"
CATALOGUE = RACINE / "tests" / "corpus" / "us094_catalogue.csv"

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUJOURD_HUI = date(2026, 8, 28)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures — un potager peuplé du catalogue réel
# ─────────────────────────────────────────────────────────────────────────────

def _lire_catalogue() -> list[dict]:
    with open(CATALOGUE, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _lire_corpus() -> list[dict]:
    with open(CORPUS, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def potager(test_db):
    """Potager de test peuplé des cultures, variétés et parcelles réelles.

    Le parseur refuse par construction toute culture ou parcelle inconnue
    (CA4) : sans ce catalogue, il ne reconnaîtrait rien et la mesure du CA5
    vaudrait zéro pour une raison de fixture, pas de grammaire.
    """
    # Pas de ligne `potagers` : comme dans les autres suites, `potager_id=1`
    # suffit — la garde d'archivage laisse passer un potager absent.
    lignes = _lire_catalogue()
    for i, ligne in enumerate(l for l in lignes if l["type"] == "parcelle"):
        test_db.add(Parcelle(
            id=100 + i, nom=ligne["valeur"],
            nom_normalise=normalize_parcelle_name(ligne["valeur"]),
            est_pepiniere=(ligne["rattachement"] == "pepiniere"),
            actif=True, potager_id=1,
        ))
    for ligne in (l for l in lignes if l["type"] == "culture"):
        test_db.add(CultureConfig(nom=ligne["valeur"], type_organe_recolte="reproducteur",
                                  potager_id=1))
    test_db.flush()

    # Les variétés ne sont connues que par les évènements : on rejoue un
    # évènement d'introduction par couple (culture, variété), ce qui donne au
    # passage à chaque culture l'antériorité que la validation centrale exige.
    for ligne in (l for l in lignes if l["type"] == "culture"):
        test_db.add(Evenement(type_action="plantation", culture=ligne["valeur"],
                              date=date(2026, 1, 1), potager_id=1))
    for ligne in (l for l in lignes if l["type"] == "variete"):
        test_db.add(Evenement(type_action="plantation", culture=ligne["rattachement"],
                              variete=ligne["valeur"], date=date(2026, 1, 1), potager_id=1))
    test_db.commit()
    return test_db


@pytest.fixture(autouse=True)
def _aucun_appel_fournisseur():
    """Filet de sécurité global : tout appel au fournisseur ferait échouer le
    test, où qu'il parte. C'est la preuve du « zéro jeton » du CA11."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
            "appel au modèle interdit sur le chemin déterministe")) as appel:
        yield appel


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — la grammaire reconnaît les formes fréquentes
# ─────────────────────────────────────────────────────────────────────────────

class TestCA1Reconnaissance:

    @pytest.mark.parametrize("phrase,action,culture,quantite,unite", [
        ("récolté 2 kg de tomates",             "recolte",    "tomate",    2.0,  "kg"),
        ("Récolte 500 grammes de courgettes",   "recolte",    "courgette", 500.0, "g"),
        ("Récolte courgette 600g",              "recolte",    "courgette", 600.0, "g"),
        ("plantation 14 plants de tomate",      "plantation", "tomate",    14.0, "plants"),
        ("Plantation de neuf potirons",         "plantation", "potiron",   9.0,  "plants"),
        ("Vendu 12 tomate",                     "vendu",      "tomate",    12.0, "plants"),
        ("perdu 7 plants de salade",            "perte",      "salade",    7.0,  "plants"),
        ("Semi navet 50 graines",               "semis",      "navet",     50.0, "graines"),
        ("récolte un kilo de tomates",          "recolte",    "tomate",    1.0,  "kg"),
    ])
    def test_ca1_formes_frequentes(self, potager, phrase, action, culture, quantite, unite):
        resultat = parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        assert resultat.reconnu, resultat.raison
        item = resultat.items[0]
        assert (item["action"], item["culture"], item["quantite"], item["unite"]) == \
               (action, culture, quantite, unite)

    def test_ca1_action_de_zone_sans_culture(self, potager):
        """« arrosé la parcelle sud » — un geste de zone n'a pas besoin de culture."""
        resultat = parser_saisie("arrosé la parcelle planche-centrale", CTX, db=potager,
                                 aujourd_hui=AUJOURD_HUI)
        assert resultat.reconnu, resultat.raison
        item = resultat.items[0]
        assert item["action"] == "arrosage"
        assert item["culture"] is None
        assert item["parcelle"] == "planche-centrale"

    def test_ca1_variete_reconnue_si_deja_connue_du_potager(self, potager):
        resultat = parser_saisie("Récolte courgettes jaunes 830 grammes", CTX, db=potager,
                                 aujourd_hui=AUJOURD_HUI)
        assert resultat.reconnu, resultat.raison
        assert resultat.items[0]["variete"] == "jaune"

    def test_ca1_phrase_complexe_declare_ne_pas_savoir(self, potager):
        """Scénario Gherkin : « j'ai fait le tour du potager, arraché ce qui
        était monté et remis des salades » — la grammaire rend la main."""
        resultat = parser_saisie(
            "j'ai fait le tour du potager, arraché ce qui était monté et remis des salades",
            CTX, db=potager, aujourd_hui=AUJOURD_HUI,
        )
        assert not resultat.reconnu
        assert resultat.raison

    def test_ca1_item_a_la_meme_forme_que_la_sortie_modele(self, potager):
        """Le format doit être celui de `parse_commande`, sinon tout l'aval
        (normalisation, validation, confirmation) diverge selon le chemin."""
        item = parser_saisie("récolté 2 kg de tomates", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        attendus = {
            "action", "culture", "variete", "quantite", "unite", "parcelle", "rang",
            "duree_minutes", "traitement", "date", "commentaire",
            "nb_graines_semees", "nb_plants_godets", "origine_parsing",
        }
        assert attendus <= set(item)


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — dates courantes résolues, formes non couvertes renvoyées au modèle
# ─────────────────────────────────────────────────────────────────────────────

class TestCA2Dates:

    @pytest.mark.parametrize("phrase,attendue", [
        ("récolté 2 kg de tomates hier",                    "2026-08-27"),
        ("récolté 2 kg de tomates avant-hier",              "2026-08-26"),
        ("récolté 2 kg de tomates avant hier",              "2026-08-26"),
        ("récolté 2 kg de tomates aujourd'hui",             "2026-08-28"),
        ("récolté 2 kg de tomates ce matin",                "2026-08-28"),
        ("récolté 2 kg de tomates il y a trois jours",      "2026-08-25"),
        ("récolté 2 kg de tomates il y a 4 jours",          "2026-08-24"),
        ("récolté 2 kg de tomates la semaine dernière",     "2026-08-21"),
        ("récolté 2 kg de tomates samedi dernier",          "2026-08-22"),
        ("Récolte 2,3 kg de tomates le 8 août dernier",     "2026-08-08"),
        ("plantation 14 plants de tomate le 25/05",         "2026-05-25"),
        ("planté 2 plants de tomate le 01/07/2025",         "2025-07-01"),
    ])
    def test_ca2_expressions_couvertes(self, potager, phrase, attendue):
        resultat = parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        assert resultat.reconnu, resultat.raison
        assert resultat.items[0]["date"] == attendue

    @pytest.mark.parametrize("phrase", [
        "récolté 2 kg de tomates il y a une semaine",
        "plantation 3 plants de tomate en juin 2023",
        "récolté 2 kg de tomates le mois dernier",
    ])
    def test_ca2_expression_non_couverte_bascule_sur_le_modele(self, potager, phrase):
        """Jamais de date inventée : la phrase ENTIÈRE part au repli."""
        resultat = parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        assert not resultat.reconnu

    def test_ca2_aucune_date_dictee_laisse_la_convention_du_projet(self, potager):
        """Sans ancrage, `date` reste None — c'est `parse_date` qui appliquera
        la convention « aujourd'hui », exactement comme sur le chemin modèle."""
        item = parser_saisie("récolté 2 kg de tomates", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        assert item["date"] is None

    def test_ca2_date_future_jamais_presumee(self):
        """Une année sous-entendue qui projetterait la saisie dans le futur est
        refusée plutôt que devinée."""
        ancrage = resoudre_ancrage_temporel("récolte le 25/12", aujourd_hui=AUJOURD_HUI)
        assert ancrage.statut == ANCRAGE_INCONNU

    def test_ca2_trois_issues_de_la_grammaire_temporelle(self):
        assert resoudre_ancrage_temporel("récolte 2 kg de tomates").statut == ANCRAGE_ABSENT
        resolu = resoudre_ancrage_temporel("récolte hier", aujourd_hui=AUJOURD_HUI)
        assert (resolu.statut, resolu.source) == (ANCRAGE_RESOLU, SOURCE_RELATIVE_RESOLUE)
        explicite = resoudre_ancrage_temporel("récolte le 14 juillet", aujourd_hui=AUJOURD_HUI)
        assert (explicite.statut, explicite.source) == (ANCRAGE_RESOLU, SOURCE_EXPLICITE)
        assert resoudre_ancrage_temporel("récolte le mois dernier").statut == ANCRAGE_INCONNU


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — aucune seconde règle de normalisation
# ─────────────────────────────────────────────────────────────────────────────

class TestCA3NormalisationReutilisee:

    def test_ca3_culture_passe_par_la_resolution_existante(self, potager):
        with patch("utils.culture_resolve.resolve_culture",
                   side_effect=lambda db, pid, c: c) as resolve:
            parser_saisie("récolté 2 kg de tomates", CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        assert resolve.called, "le parseur doit réutiliser utils.culture_resolve.resolve_culture"

    def test_ca3_parcelle_passe_par_la_resolution_existante(self, potager):
        with patch("utils.parcelles.resolve_parcelle", wraps=None) as resolve:
            resolve.return_value = None
            resultat = parser_saisie("arrosage parcelle planche-centrale", CTX, db=potager,
                                     aujourd_hui=AUJOURD_HUI)
        assert resolve.called, "le parseur doit réutiliser utils.parcelles.resolve_parcelle"
        assert not resultat.reconnu  # parcelle non résolue → repli (CA4)

    def test_ca3_geste_lu_dans_le_referentiel_unique(self):
        """Aucune liste de gestes concurrente : le périmètre couvert est un
        sous-ensemble strict d'ACTION_MAP (référentiel unique d'US-168)."""
        assert GESTES_COUVERTS <= set(ACTION_MAP)

    def test_ca3_unite_normalisee_a_l_ecriture_pas_dans_le_parseur(self, potager):
        """Le parseur émet la forme brute du modèle ; c'est la couche
        d'écriture qui canonise, une seule fois, pour les deux chemins."""
        item = parser_saisie("perdu 3 pieds de salade", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        assert item["unite"] == "plants"
        assert _normalize_unite_denombrement(item["unite"], item["action"]) == "plants"


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — jamais de culture ni de parcelle créée à l'aveugle
# ─────────────────────────────────────────────────────────────────────────────

class TestCA4RienDeCreeAlAveugle:

    def test_ca4_culture_inconnue_bascule_sur_le_modele(self, potager):
        """Scénario Gherkin : « récolté 1 kg de cardons », cardon inexistant."""
        resultat = parser_saisie("récolté 1 kg de cardons", CTX, db=potager,
                                 aujourd_hui=AUJOURD_HUI)
        assert not resultat.reconnu
        assert "culture" in resultat.raison

    def test_ca4_parcelle_inconnue_bascule_sur_le_modele(self, potager):
        resultat = parser_saisie("arrosage parcelle atlantide", CTX, db=potager,
                                 aujourd_hui=AUJOURD_HUI)
        assert not resultat.reconnu
        assert "parcelle" in resultat.raison

    def test_ca4_variete_inconnue_bascule_sur_le_modele(self, potager):
        """Une variété jamais vue est un mot inexpliqué : on ne l'invente pas."""
        resultat = parser_saisie("Récolte 500 g de tomates ananas noire", CTX, db=potager,
                                 aujourd_hui=AUJOURD_HUI)
        assert not resultat.reconnu

    def test_ca4_aucune_ecriture_en_base_par_le_parseur(self, potager):
        avant = potager.query(Evenement).count()
        parser_saisie("récolté 2 kg de tomates", CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        parser_saisie("récolté 1 kg de cardons", CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        assert potager.query(Evenement).count() == avant
        assert potager.query(CultureConfig).filter(CultureConfig.nom == "cardon").count() == 0


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — couverture mesurée sur des saisies réelles : ≥ 50 %
# ─────────────────────────────────────────────────────────────────────────────

SEUIL_COUVERTURE = 0.50


def _phrases_du_corpus() -> dict[tuple[str, str], list[dict]]:
    groupes: dict[tuple[str, str], list[dict]] = {}
    for ligne in _lire_corpus():
        groupes.setdefault((ligne["texte"], ligne["jour_saisie"]), []).append(ligne)
    return groupes


class TestCA5Couverture:

    def test_ca5_corpus_bien_constitue_de_saisies_reelles(self):
        groupes = _phrases_du_corpus()
        assert len(groupes) >= 200, "corpus tronqué — la mesure ne vaudrait plus rien"
        assert not any("[AUTO-METEO]" in texte for texte, _ in groupes), \
            "les bulletins météo sont des écritures machine, pas des saisies"
        assert not any("[CORR" in texte for texte, _ in groupes), \
            "les traces de correction ne faisaient pas partie de l'entrée du parseur"

    def test_ca5_moitie_des_saisies_traitees_sans_appel_au_modele(self, potager):
        groupes = _phrases_du_corpus()
        reconnues = sum(
            1 for (texte, jour) in groupes
            if parser_saisie(texte, CTX, db=potager,
                             aujourd_hui=date.fromisoformat(jour)).reconnu
        )
        taux = reconnues / len(groupes)
        print(f"\n[US-094 / CA5] couverture déterministe : "
              f"{reconnues}/{len(groupes)} = {taux:.1%}")
        assert taux >= SEUIL_COUVERTURE, (
            f"couverture {taux:.1%} < {SEUIL_COUVERTURE:.0%} "
            f"({reconnues}/{len(groupes)} phrases réelles)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — test différentiel : aucune régression de précision
# ─────────────────────────────────────────────────────────────────────────────
# Le corpus porte les champs RÉELLEMENT enregistrés par le chemin modèle en
# production : c'est la meilleure référence disponible, et la seule qui ne soit
# pas une simulation. Les écarts ci-dessous sont les seuls admis, chacun
# justifié — un écart non listé fait échouer le test.
# ─────────────────────────────────────────────────────────────────────────────

ECARTS_JUSTIFIES: dict[str, str] = {
    # Le référentiel d'actions n'a été unifié qu'à US-168 : ces lignes ont été
    # écrites AVANT que `binage` et `eclaircie` existent, et le modèle les
    # rangeait faute de mieux en `desherbage`. Le parseur rend désormais le
    # geste canonique — c'est une correction, pas une régression, et les
    # saisies postérieures du corpus le confirment (« hier j'ai biné mes
    # ranger de carotte » → binage).
    "binage des carottes": "geste canonisé par US-168",
    "binage fait sur les oignons hier": "geste canonisé par US-168",
    "Éclairci la roquette avant hier": "geste canonisé par US-168",

    # Le prompt de parsing pose `nb_plants_godets` comme champ PRINCIPAL d'une
    # mise en godet, et c'est lui que lit le calcul de stock de pépinière
    # (utils.stock.calcul_godets_par_culture). Le modèle a ici rempli EN PLUS
    # quantite/unite, ce qu'il ne fait sur aucune autre des quinze mises en
    # godet du corpus. Le parseur suit le contrat, pas l'exception.
    "Mise en godet courgettes jaunes 20 plants": "nb_plants_godets est le champ contractuel",

    # Unité de dénombrement implicite : sur la même forme (« Récolte 2 salades »),
    # le modèle a écrit tantôt `plants`, tantôt rien. Le parseur applique la
    # convention tranchée par US-168 — « plants » est l'unité canonique de
    # dénombrement — au lieu de reproduire l'inconstance.
    "Récolte 2 salade hier": "unité de dénombrement canonique (US-168)",

    # Champs complétés APRÈS le parsing par un flux conversationnel existant,
    # que le chemin déterministe emprunte à l'identique : la désambiguïsation
    # perte / perte_godet, et la demande de quantité manquante (US-021 CA9).
    # Le modèle avait produit exactement la même chose que le parseur.
    "Perte de 10 courgette": "complété par la désambiguïsation perte/perte_godet",
    "Récolte cornichon": "quantité demandée après coup (US-021 CA9)",
}


def _valeur(brut: str):
    return brut if brut else None


class TestCA6Precision:

    def test_ca6_aucun_ecart_de_champ_non_justifie(self, potager):
        groupes = _phrases_du_corpus()
        ecarts: list[str] = []
        compares = 0

        for (texte, jour), lignes in groupes.items():
            if any(l["corrigee"] == "1" for l in lignes):
                continue  # valeur corrigée à la main : ce n'est plus la sortie du modèle
            resultat = parser_saisie(texte, CTX, db=potager, aujourd_hui=date.fromisoformat(jour))
            if not resultat.reconnu:
                continue
            compares += 1
            item = resultat.items[0]

            unite = (_normalize_unite_semis(item["unite"], texte)
                     if item["action"] == "semis"
                     else _normalize_unite_denombrement(item["unite"], item["action"]))

            meilleur = None
            for ligne in lignes:
                diffs = []
                if item["action"] != _valeur(ligne["action"]):
                    diffs.append(f"action {item['action']} != {ligne['action']}")
                if item["culture"] != _valeur(ligne["culture"]):
                    diffs.append(f"culture {item['culture']!r} != {ligne['culture']!r}")
                attendue = float(ligne["quantite"]) if ligne["quantite"] else None
                if item["quantite"] != attendue:
                    diffs.append(f"quantite {item['quantite']} != {attendue}")
                if unite != _valeur(ligne["unite"]):
                    diffs.append(f"unite {unite!r} != {ligne['unite']!r}")
                godets = int(ligne["nb_plants_godets"]) if ligne["nb_plants_godets"] else None
                if item["nb_plants_godets"] != godets:
                    diffs.append(f"nb_plants_godets {item['nb_plants_godets']} != {godets}")
                ancrage = resoudre_ancrage_temporel(texte, aujourd_hui=date.fromisoformat(jour))
                if ancrage.source == SOURCE_EXPLICITE and item["date"] != jour:
                    diffs.append(f"date {item['date']} != {jour}")
                if meilleur is None or len(diffs) < len(meilleur):
                    meilleur = diffs
            if meilleur and texte not in ECARTS_JUSTIFIES:
                ecarts.append(f"{texte!r} → {' ; '.join(meilleur)}")

        print(f"\n[US-094 / CA6] phrases comparées champ à champ : {compares}")
        assert compares >= 100, "trop peu de phrases comparées pour que la mesure ait un sens"
        assert not ecarts, "écarts de précision non justifiés :\n" + "\n".join(ecarts)

    def test_ca6_aucun_ecart_justifie_obsolete(self, potager):
        """Un écart justifié qui a disparu doit sortir de la liste : sinon elle
        devient une exemption permanente que plus personne ne relit."""
        groupes = _phrases_du_corpus()
        connus = {texte for texte, _ in groupes}
        obsoletes = set(ECARTS_JUSTIFIES) - connus
        assert not obsoletes, f"écarts justifiés sans phrase correspondante : {obsoletes}"

    def test_ca6_aucun_faux_positif_sur_le_corpus_de_questions(self, potager):
        """Le pire défaut possible : une QUESTION comprise comme une saisie, et
        enregistrée. Les 44 questions du corpus de diagnostic doivent toutes
        tomber au repli."""
        import re
        corpus = (RACINE / "docs" / "CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md").read_text(encoding="utf-8")
        bloc = corpus.split("## Partie 1")[1]
        questions = [m.group(1).split("→")[0].strip()
                     for m in re.finditer(r"^\s*\d+\.\s+(.+)$", bloc, re.M)]
        assert len(questions) >= 40, "corpus de questions non lu correctement"
        faux_positifs = [q for q in questions
                         if parser_saisie(q, CTX, db=potager, aujourd_hui=AUJOURD_HUI).reconnu]
        assert not faux_positifs, f"questions prises pour des saisies : {faux_positifs}"

    @pytest.mark.parametrize("phrase", [
        "récolté 2 betteraves pour 250 grammes",   # deux quantités → découpage en 2 items
        "Semis tomates cœur de bœuf 5*3+5*4 plants",  # arithmétique dictée
        "planter 10 choux sur 3 rangs",             # partage quantité / rang
        "Arrosage oignons et échalotes",            # deux cultures, deux évènements
    ])
    def test_ca6_le_doute_bascule_toujours_vers_le_modele(self, potager, phrase):
        assert not parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI).reconnu


# ─────────────────────────────────────────────────────────────────────────────
# CA7 / CA8 — même validation centrale, même confirmation
# ─────────────────────────────────────────────────────────────────────────────

class TestCA7ValidationCentrale:

    def test_ca7_item_deterministe_traverse_la_validation_centrale(self, potager):
        """La culture existe dans le catalogue mais n'a jamais été introduite
        dans CE potager : la validation d'US-049 doit bloquer l'écriture, quel
        que soit le chemin de parsing."""
        potager.add(CultureConfig(nom="topinambour", type_organe_recolte="végétatif",
                                  potager_id=1))
        potager.commit()
        item = parser_saisie("récolté 2 kg de topinambours", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        with pytest.raises(CultureInconnueError):
            creer_evenement_confirme(potager, CTX, item, "récolté 2 kg de topinambours", None)

    def test_ca7_ecriture_normale_apres_validation(self, potager):
        item = parser_saisie("récolté 2 kg de tomates", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        event = creer_evenement_confirme(potager, CTX, item, "récolté 2 kg de tomates", None)
        assert (event.type_action, event.culture, event.quantite, event.unite) == \
               ("recolte", "tomate", 2.0, "kg")


class TestCA8ConfirmationInchangee:

    def test_ca8_meme_point_d_entree_de_confirmation(self, potager):
        """Le parseur ne court-circuite aucun flux : il alimente `_parse_and_save`
        avec des items pré-parsés, exactement comme le fait déjà le chemin
        modèle (`parse_message`) — donc la même confirmation, le même écran."""
        import bot
        with patch("bot.parser_saisie") as det, patch("bot.parse_commande") as llm:
            det.return_value = type("R", (), {
                "reconnu": True,
                "items": [{"action": "recolte", "culture": "tomate", "origine_parsing":
                           ORIGINE_DETERMINISTE}],
            })()
            with patch("bot.current_context", return_value=CTX):
                items = bot._parser_items("récolté 2 kg de tomates")
        assert llm.call_count == 0
        assert items[0]["origine_parsing"] == ORIGINE_DETERMINISTE

    def test_ca8_repli_modele_marque_son_origine(self, potager):
        import bot
        with patch("bot.parser_saisie") as det, patch("bot.parse_commande") as llm:
            det.return_value = type("R", (), {"reconnu": False, "items": None})()
            llm.return_value = [{"action": "recolte", "culture": "tomate"}]
            with patch("bot.current_context", return_value=CTX):
                items = bot._parser_items("phrase que la grammaire ne sait pas lire")
        assert items[0]["origine_parsing"] == ORIGINE_LLM


# ─────────────────────────────────────────────────────────────────────────────
# CA9 — non-régression des actions canoniques
# ─────────────────────────────────────────────────────────────────────────────

class TestCA9ActionsCanoniques:

    def test_ca9_tout_geste_couvert_normalise_comme_sur_le_chemin_modele(self):
        """Le parseur émet une clé canonique d'ACTION_MAP : elle doit traverser
        `normalize_action` sans bouger, sinon les deux chemins écriraient des
        `type_action` différents pour le même geste."""
        for geste in GESTES_COUVERTS:
            assert normalize_action(geste) == geste

    @pytest.mark.parametrize("phrase,geste", [
        ("Récolte 500 g de tomates",            "recolte"),
        ("Semi 50 graines de navet",            "semis"),
        ("plantation 3 plants de tomate",       "plantation"),
        ("arrosage betteraves",                 "arrosage"),
        ("Désherbage tomate",                   "desherbage"),
        ("Paillage courge",                     "paillage"),
        ("binage des carottes",                 "binage"),
        ("éclaircie des carottes",              "eclaircie"),
        ("fertilisation des tomates",           "amendement"),
        ("Perte 3 salades",                     "perte"),
        ("perte pépinière de 6 courges",        "perte_godet"),
        ("Vente 1 courgette",                   "vendu"),
        ("Mise en godet 20 tomates",            "mise_en_godet"),
    ])
    def test_ca9_gestes_reconnus_sans_derive(self, potager, phrase, geste):
        resultat = parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI)
        assert resultat.reconnu, resultat.raison
        assert resultat.items[0]["action"] == geste

    @pytest.mark.parametrize("geste", ["observation", "traitement"])
    def test_ca9_gestes_volontairement_hors_perimetre(self, geste):
        """`observation` porte du texte libre, `traitement` exige d'identifier
        un produit : aucun des deux ne s'extrait sans deviner."""
        assert geste not in GESTES_COUVERTS
        assert geste in ACTION_MAP  # toujours du référentiel, simplement pas d'ici


# ─────────────────────────────────────────────────────────────────────────────
# CA10 — origine du parsing conservée sur l'évènement
# ─────────────────────────────────────────────────────────────────────────────

class TestCA10Tracabilite:

    def test_ca10_origine_deterministe_ecrite_sur_l_evenement(self, potager):
        item = parser_saisie("récolté 2 kg de tomates", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        assert item["origine_parsing"] == ORIGINE_DETERMINISTE
        event = creer_evenement_confirme(potager, CTX, item, "récolté 2 kg de tomates", None)
        assert event.origine_parsing == ORIGINE_DETERMINISTE

    def test_ca10_origine_modele_ecrite_sur_l_evenement(self, potager):
        item = {"action": "recolte", "culture": "tomate", "quantite": 2, "unite": "kg",
                "origine_parsing": ORIGINE_LLM}
        event = creer_evenement_confirme(potager, CTX, item, "récolté 2 kg de tomates", None)
        assert event.origine_parsing == ORIGINE_LLM

    def test_ca10_historique_reste_a_null_sans_backfill(self, potager):
        """Avant cette US l'information n'existait pas : NULL est la seule
        chose vraie qu'on puisse dire des lignes antérieures."""
        ancien = potager.query(Evenement).first()
        assert ancien.origine_parsing is None

    def test_ca10_colonne_purement_instrumentale(self):
        """Aucune condition métier, aucun gabarit, aucun message ne lit
        `origine_parsing` — sinon ce ne serait plus de l'instrumentation."""
        interdits = ["app/services/reponses_chiffrees.py", "app/services/questions.py",
                     "app/services/stock.py", "utils/stock.py", "llm/sql_agent.py"]
        for chemin in interdits:
            contenu = (RACINE / chemin).read_text(encoding="utf-8")
            assert "origine_parsing" not in contenu, f"{chemin} lit une colonne d'instrumentation"


# ─────────────────────────────────────────────────────────────────────────────
# CA11 — zéro jeton, aucune ligne de consommation
# ─────────────────────────────────────────────────────────────────────────────

class TestCA11ZeroJeton:

    def test_ca11_aucun_appel_au_fournisseur(self, potager, _aucun_appel_fournisseur):
        for texte, jour in list(_phrases_du_corpus())[:60]:
            parser_saisie(texte, CTX, db=potager, aujourd_hui=date.fromisoformat(jour))
        assert _aucun_appel_fournisseur.call_count == 0

    def test_ca11_aucune_ligne_de_consommation(self, potager):
        from database.models import ConsoTokens
        avant = potager.query(ConsoTokens).count()
        item = parser_saisie("récolté 2 kg de tomates", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI).items[0]
        creer_evenement_confirme(potager, CTX, item, "récolté 2 kg de tomates", None)
        assert potager.query(ConsoTokens).count() == avant


# ─────────────────────────────────────────────────────────────────────────────
# CA12 — mode dégradé : la saisie courante survit au 429
# ─────────────────────────────────────────────────────────────────────────────

class TestCA12ModeDegrade:

    def test_ca12_forme_couverte_enregistree_malgre_le_429(self, potager):
        """Scénario Gherkin : un fournisseur qui répond 429 à tout appel. La
        forme couverte s'enregistre normalement, sans message d'indisponibilité."""
        from llm.passerelle import QuotaLLMDepasseError
        import bot

        with patch("bot.parse_commande", side_effect=QuotaLLMDepasseError("429")), \
             patch("bot.current_context", return_value=CTX), \
             patch("llm.parseur_deterministe.parser_saisie") as _:
            # on n'intercepte PAS le vrai parseur : on veut son résultat réel
            pass

        with patch("bot.parse_commande", side_effect=QuotaLLMDepasseError("429")) as llm, \
             patch("bot.current_context", return_value=CTX), \
             patch("database.db.SessionLocal", return_value=potager), \
             patch.object(potager, "close", lambda: None):
            items = bot._parser_items("arrosé la parcelle planche-centrale")

        assert llm.call_count == 0, "le repli modèle n'aurait pas dû être tenté"
        assert items[0]["action"] == "arrosage"

        event = creer_evenement_confirme(
            potager, CTX, items[0], "arrosé la parcelle planche-centrale",
            potager.query(Parcelle).filter(Parcelle.nom == "planche-centrale").first(),
        )
        assert event.id is not None
        assert event.origine_parsing == ORIGINE_DETERMINISTE

    def test_ca12_forme_complexe_recoit_bien_l_indisponibilite(self, potager):
        """La contrepartie : ce que la grammaire ne couvre pas continue de
        dépendre du modèle, et le dit."""
        from llm.passerelle import QuotaLLMDepasseError
        import bot

        with patch("bot.parse_commande", side_effect=QuotaLLMDepasseError("429")), \
             patch("bot.current_context", return_value=CTX), \
             patch("database.db.SessionLocal", return_value=potager), \
             patch.object(potager, "close", lambda: None), \
             pytest.raises(QuotaLLMDepasseError):
            bot._parser_items("j'ai fait le tour du potager et remis quelques trucs")
