"""
tests/test_us199_unite_poquet_implantation.py
[US-199] Reconnaître le poquet et le mètre de rang comme unités d'implantation

Un test au moins par critère d'acceptance CA1 → CA8 (CA9 = documentation, tenue
par `test_us099_corpus_fonctionnement.py` ; l'affichage PWA CA8 est couvert côté
`frontend/src/lib/plan.test.js` et `planVue.test.js`, lancés par `npm test`).

Les unités restent des unités : aucune conversion, jamais (CA5). Le stockage de
la surface est inchangé — `m²` à l'écriture d'un semis, comme depuis US-037.
"""
from datetime import date

import pytest

from app.bot.enregistrement import _build_action_summary
from app.bot.normalisation import _normalize_items
from app.services.context import TenantContext
from app.services.evenements import (
    UniteImplantationRefuseeError,
    _normalize_unite_denombrement,
    _normalize_unite_semis,
    creer_evenement_confirme,
    creer_evenement_godet,
)
from database.models import CultureConfig, Evenement, Parcelle
from llm.parseur_deterministe import parser_saisie
from utils.parcelles import normalize_parcelle_name
from utils.stock import calcul_stock_cultures
from utils.unites_implantation import (
    libelle_unite,
    normaliser_unite_implantation,
    unite_implantation_dans_texte,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUJOURD_HUI = date(2026, 8, 28)


@pytest.fixture
def potager(test_db):
    """Un potager avec une planche de pleine terre, une serre (pépinière) et les
    cultures dont les phrases ont besoin — le parseur refuse toute culture ou
    parcelle inconnue (US-094 / CA4)."""
    test_db.add(Parcelle(id=1, nom="centrale", nom_normalise=normalize_parcelle_name("centrale"),
                         est_pepiniere=False, actif=True, potager_id=1))
    test_db.add(Parcelle(id=2, nom="serre", nom_normalise=normalize_parcelle_name("serre"),
                         est_pepiniere=True, actif=True, potager_id=1))
    for nom, organe in [("carotte", "vegetatif"), ("courge", "reproducteur"),
                        ("potiron", "reproducteur"), ("ciboulette", "vegetatif"),
                        ("radis", "vegetatif"), ("tomate", "reproducteur")]:
        test_db.add(CultureConfig(nom=nom, type_organe_recolte=organe, potager_id=1))
        test_db.add(Evenement(type_action="plantation", culture=nom, quantite=1, unite="plants",
                              date=date(2026, 1, 1), potager_id=1))
    test_db.commit()
    return test_db


def _item(**champs) -> dict:
    base = {"action": "semis", "culture": "courge", "variete": None, "quantite": 5, "unite": None,
            "parcelle": None, "rang": None, "duree_minutes": None, "traitement": None,
            "commentaire": None, "date": "2026-08-01"}
    base.update(champs)
    return base


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — le vocabulaire normalisé à l'écriture
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brute", ["poquet", "poquets", "Poquets", " poquets "])
def test_ca1_poquet_normalise_en_poquets(brute) -> None:
    """CA1 : « poquet(s) », quelle que soit la casse, s'écrit `poquets`."""
    assert normaliser_unite_implantation(brute) == "poquets"


@pytest.mark.parametrize("brute", ["trou", "trous", "touffe", "touffes"])
def test_ca1_trou_et_touffe_sont_des_poquets_en_semis_et_plantation(brute) -> None:
    """CA1 : « trou » et « touffe » valent poquet dans une phrase de semis ou de plantation."""
    assert normaliser_unite_implantation(brute, "semis") == "poquets"
    assert normaliser_unite_implantation(brute, "plantation") == "poquets"


@pytest.mark.parametrize("brute", ["touffe", "trou"])
@pytest.mark.parametrize("geste", ["recolte", "perte", "arrosage", None])
def test_ca1_touffe_hors_semis_et_plantation_n_est_pas_une_unite(brute, geste) -> None:
    """CA1 (vigilance) : « une touffe de mauvaises herbes » n'est pas un geste."""
    assert normaliser_unite_implantation(brute, geste) is None


@pytest.mark.parametrize("brute", [
    "ml", "ML", "mètre de rang", "mètres de rang", "mètre linéaire", "mètres linéaires",
    "mètre de ligne", "mètres de ligne", "m de rang",
])
def test_ca1_metre_de_rang_normalise_en_ml(brute) -> None:
    """CA1 : toutes les façons de dire le mètre de rang s'écrivent `ml`."""
    assert normaliser_unite_implantation(brute) == "ml"


def test_ca1_ecriture_semis_normalise_les_deux_unites() -> None:
    """CA1 : la normalisation d'un semis (`_normalize_unite_semis`) les reconnaît."""
    assert _normalize_unite_semis("trou", "semé 5 trous de courge") == "poquets"
    assert _normalize_unite_semis("mètres de rang", "semé 3 mètres de rang de radis") == "ml"


def test_ca1_ecriture_hors_semis_normalise_les_deux_unites() -> None:
    """CA1 : plantation, perte, récolte — `_normalize_unite_denombrement` aussi."""
    assert _normalize_unite_denombrement("touffes", "plantation") == "poquets"
    assert _normalize_unite_denombrement("poquet", "perte") == "poquets"
    assert _normalize_unite_denombrement("mètres linéaires", "plantation") == "ml"


def test_ca1_les_autres_unites_ne_bougent_pas() -> None:
    """Contre-épreuve : plants, graines et kg traversent inchangés."""
    assert _normalize_unite_denombrement("pieds", "plantation") == "plants"
    assert _normalize_unite_denombrement("kg", "recolte") == "kg"
    assert _normalize_unite_semis("graines", "semé 30 graines de radis") == "graines"


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — chemin déterministe et chemin modèle donnent la même unité
# ─────────────────────────────────────────────────────────────────────────────

PHRASES = [
    # (phrase, geste, unité brute rendue par le modèle, unité attendue des deux côtés)
    ("semé 5 poquets de courge dans la planche centrale", "semis", "poquets", "poquets"),
    ("semé 5 trous de courge dans la planche centrale", "semis", "trou", "poquets"),
    ("planté 2 touffes de ciboulette dans la planche centrale", "plantation", "touffes", "poquets"),
    ("semé 3 mètres de carottes dans la planche centrale", "semis", "mètres", "ml"),
    ("semé 3 mètres de rang de carottes dans la planche centrale", "semis", "mètres de rang", "ml"),
    ("semé 3 mètres linéaires de carottes dans la planche centrale", "semis", "mètres linéaires", "ml"),
    ("semé 3 ml de carottes dans la planche centrale", "semis", "ml", "ml"),
    ("semé 2 mètres carrés de carottes dans la planche centrale", "semis", "m2", "m²"),
]


def _normalise_comme_a_l_ecriture(geste: str, unite, texte: str):
    if geste == "semis":
        return _normalize_unite_semis(unite, texte)
    return _normalize_unite_denombrement(unite, geste)


@pytest.mark.parametrize("phrase,geste,brute,attendue", PHRASES)
def test_ca2_chemin_deterministe_donne_l_unite_attendue(potager, phrase, geste, brute, attendue) -> None:
    """CA2 : la grammaire lit l'unité sans le modèle, puis l'écriture la normalise."""
    resultat = parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI)

    assert resultat.reconnu, resultat.raison
    item = resultat.items[0]
    assert _normalise_comme_a_l_ecriture(geste, item["unite"], phrase) == attendue
    assert item["quantite"] in (2.0, 3.0, 5.0)


@pytest.mark.parametrize("phrase,geste,brute,attendue", PHRASES)
def test_ca2_chemin_modele_donne_la_meme_unite(potager, phrase, geste, brute, attendue) -> None:
    """CA2 : le modèle rend une forme brute ; récapitulatif et écriture la ramènent
    à la même unité que la grammaire."""
    items = _normalize_items([_item(action=geste, unite=brute)], phrase)

    assert _normalise_comme_a_l_ecriture(geste, items[0]["unite"], phrase) == attendue


@pytest.mark.parametrize("phrase,geste,brute,attendue", PHRASES)
def test_ca2_les_deux_chemins_concordent(potager, phrase, geste, brute, attendue) -> None:
    """CA2 : sur les mêmes phrases, mêmes unités des deux côtés."""
    determ = parser_saisie(phrase, CTX, db=potager, aujourd_hui=AUJOURD_HUI).items[0]
    modele = _normalize_items([_item(action=geste, unite=brute)], phrase)[0]

    assert (_normalise_comme_a_l_ecriture(geste, determ["unite"], phrase)
            == _normalise_comme_a_l_ecriture(geste, modele["unite"], phrase))


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — mètre contre mètre carré
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("brute", ["m2", "m²", "mètre carré", "mètres carrés"])
def test_ca3_surface_reste_une_surface(brute) -> None:
    """CA3 : m², m2, mètres carrés ne sont jamais un mètre de rang."""
    assert normaliser_unite_implantation(brute, "semis") is None
    assert _normalize_unite_semis(brute, "semé 2 mètres carrés de carottes") == "m²"


def test_ca3_metre_seul_en_semis_est_un_metre_de_rang() -> None:
    """CA3 : « mètre » sans « carré », dans une phrase de semis, se lit `ml`."""
    assert normaliser_unite_implantation("mètres", "semis") == "ml"
    assert unite_implantation_dans_texte("semé 3 mètres de carottes", "semis") == "ml"
    assert unite_implantation_dans_texte("semé 2 mètres carrés de carottes", "semis") is None


def test_ca3_le_modele_qui_dit_m2_pour_des_metres_est_corrige() -> None:
    """CA3 : « 2 mètres de carottes » mal rendu `m²` par le modèle retombe sur `ml`,
    puisque le texte ne dit pas « carrés »."""
    assert _normalize_unite_semis("m²", "semé 2 mètres de carottes") == "ml"


def test_ca3_paire_qui_se_ressemble(potager) -> None:
    """CA3 / Gherkin : « 3 mètres » → ml, « 2 mètres carrés » → m²."""
    metres = parser_saisie("semé 3 mètres de carottes dans la planche centrale",
                           CTX, db=potager, aujourd_hui=AUJOURD_HUI).items[0]
    surface = parser_saisie("semé 2 mètres carrés de carottes dans la planche centrale",
                            CTX, db=potager, aujourd_hui=AUJOURD_HUI).items[0]

    assert _normalize_unite_semis(metres["unite"], "semé 3 mètres de carottes") == "ml"
    assert _normalize_unite_semis(surface["unite"], "semé 2 mètres carrés de carottes") == "m²"


def test_ca3_une_touffe_de_mauvaises_herbes_n_est_pas_un_geste(potager) -> None:
    """CA3 (vigilance) : « touffe » hors semis/plantation ne devient pas poquet —
    la grammaire s'abstient (repli sur le modèle), elle n'invente rien."""
    resultat = parser_saisie("désherbé 2 touffes dans la planche centrale",
                             CTX, db=potager, aujourd_hui=AUJOURD_HUI)

    assert not resultat.reconnu or all(i["unite"] != "poquets" for i in resultat.items)


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — acceptées en pleine terre et en plantation, refusées en pépinière
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("unite,texte", [
    ("poquets", "semé 5 poquets de courge"),
    ("ml", "semé 5 mètres de rang de courge"),
])
def test_ca4_semis_pleine_terre_accepte(potager, unite, texte) -> None:
    """CA4 : un semis en pleine terre se compte en poquets ou en mètres de rang."""
    parsed = _item(unite=unite, parcelle="centrale")

    event = creer_evenement_confirme(potager, CTX, parsed, texte, potager.get(Parcelle, 1))

    assert event.unite == unite
    assert event.quantite == 5.0


@pytest.mark.parametrize("unite", ["poquets", "ml"])
def test_ca4_plantation_accepte(potager, unite) -> None:
    """CA4 : une plantation aussi."""
    parsed = _item(action="plantation", unite=unite, parcelle="centrale")

    event = creer_evenement_confirme(potager, CTX, parsed, "planté", potager.get(Parcelle, 1))

    assert event.unite == unite


@pytest.mark.parametrize("unite,texte", [
    ("poquets", "semé 5 poquets de courge en pépinière"),
    ("ml", "semé 5 mètres de rang de courge en pépinière"),
])
def test_ca4_semis_en_pepiniere_refuse_par_le_contexte(potager, unite, texte) -> None:
    """CA4 : un semis dit « en pépinière » refuse l'unité, et rappelle les graines."""
    parsed = _item(unite=unite, contexte_semis="pepiniere")

    with pytest.raises(UniteImplantationRefuseeError) as exc:
        creer_evenement_confirme(potager, CTX, parsed, texte, None)

    assert "graines" in str(exc.value)


def test_ca4_semis_dans_une_parcelle_pepiniere_refuse(potager) -> None:
    """CA4 : une parcelle marquée pépinière (serre) vaut contexte pépinière."""
    parsed = _item(unite="poquets", parcelle="serre")

    with pytest.raises(UniteImplantationRefuseeError):
        creer_evenement_confirme(potager, CTX, parsed, "semé 5 poquets en serre", potager.get(Parcelle, 2))


def test_ca4_mise_en_godet_refuse_et_rappelle_les_plants(potager) -> None:
    """CA4 / Gherkin : « mis en godet 4 poquets de tomate » — la mise en godet
    efface l'unité, c'est donc la phrase qui la trahit."""
    parsed = _item(action="mise_en_godet", culture="tomate", quantite=None, unite=None,
                   nb_plants_godets=4)

    with pytest.raises(UniteImplantationRefuseeError) as exc:
        creer_evenement_godet(potager, CTX, parsed, "mis en godet 4 poquets de tomate")

    assert "mise en godet" in str(exc.value)
    assert "plants" in str(exc.value)
    assert potager.query(Evenement).filter_by(type_action="mise_en_godet").count() == 0


def test_ca4_mise_en_godet_en_plants_reste_acceptee(potager) -> None:
    """Contre-épreuve : le refus ne touche que les unités d'implantation."""
    parsed = _item(action="mise_en_godet", culture="tomate", quantite=None, unite=None,
                   nb_plants_godets=4)

    event = creer_evenement_godet(potager, CTX, parsed, "mis en godet 4 plants de tomate")

    assert event.nb_plants_godets == 4


def test_ca4_la_grammaire_laisse_le_refus_a_l_ecriture(potager) -> None:
    """CA4 : « mis en godet 4 poquets de tomate » est LU par la grammaire (plus un
    repli « vocabulaire de rangs ») ; c'est la validation centrale qui refuse."""
    resultat = parser_saisie("mis en godet 4 poquets de tomate", CTX, db=potager,
                             aujourd_hui=AUJOURD_HUI)

    assert resultat.reconnu, resultat.raison
    with pytest.raises(UniteImplantationRefuseeError):
        creer_evenement_godet(potager, CTX, resultat.items[0], "mis en godet 4 poquets de tomate")


# ─────────────────────────────────────────────────────────────────────────────
# CA5 — aucune conversion, des unités distinctes
# ─────────────────────────────────────────────────────────────────────────────

def test_ca5_un_poquet_reste_un_poquet(potager) -> None:
    """CA5 : 5 poquets s'enregistrent 5 poquets — ni graines, ni plants."""
    event = creer_evenement_confirme(potager, CTX, _item(unite="poquets", parcelle="centrale"),
                                     "semé 5 poquets de courge", potager.get(Parcelle, 1))

    assert (event.quantite, event.unite) == (5.0, "poquets")


def test_ca5_un_metre_reste_un_metre(potager) -> None:
    """CA5 : 3 m de rang s'enregistrent 3 ml — jamais 3 m²."""
    event = creer_evenement_confirme(potager, CTX, _item(culture="carotte", quantite=3, unite="ml",
                                                         parcelle="centrale"),
                                     "semé 3 mètres de carottes", potager.get(Parcelle, 1))

    assert (event.quantite, event.unite) == (3.0, "ml")


def test_ca5_le_stock_ne_melange_pas_poquets_et_plants(potager) -> None:
    """CA5 : 4 poquets + 3 plants (dont 1 de départ) ne font pas 7 — une seule unité
    compte, celle qui domine (US-037 / CA2), et l'autre n'est pas convertie."""
    potager.add(Evenement(type_action="plantation", culture="potiron", quantite=4, unite="poquets",
                          parcelle_id=1, date=date(2026, 6, 1), potager_id=1))
    potager.add(Evenement(type_action="plantation", culture="potiron", quantite=2, unite="plants",
                          parcelle_id=1, date=date(2026, 6, 2), potager_id=1))
    potager.commit()

    stock = calcul_stock_cultures(potager, potager_id=1)["potiron"]

    assert stock.unite == "poquets"
    assert stock.plants_plantes == 4.0


# ─────────────────────────────────────────────────────────────────────────────
# CA6 — déduction d'une perte, récolte d'une culture reproductive
# ─────────────────────────────────────────────────────────────────────────────

def test_ca6_perte_en_poquets_se_deduit(potager) -> None:
    """CA6 : « perdu 2 poquets de courge » retire 2 poquets des 5."""
    parcelle = potager.get(Parcelle, 1)
    creer_evenement_confirme(potager, CTX, _item(unite="poquets", parcelle="centrale"),
                             "semé 5 poquets de courge", parcelle)

    perte = creer_evenement_confirme(
        potager, CTX, _item(action="perte", quantite=2, unite="poquets", parcelle="centrale"),
        "perdu 2 poquets de courge", parcelle,
    )
    stock = calcul_stock_cultures(potager, potager_id=1)["courge"]

    assert perte.unite == "poquets"
    assert (stock.plants_plantes, stock.plants_perdus) == (5.0, 2.0)
    assert stock.stock_plants == 3.0


def test_ca6_recolte_en_kg_ne_touche_pas_aux_poquets(potager) -> None:
    """CA6 / Gherkin : 3 poquets de potiron, 6 kg récoltés — toujours 3 poquets, et
    les 6 kg vont au rendement."""
    parcelle = potager.get(Parcelle, 1)
    creer_evenement_confirme(potager, CTX, _item(culture="potiron", quantite=3, unite="poquets",
                                                 parcelle="centrale"),
                             "semé 3 poquets de potiron", parcelle)
    creer_evenement_confirme(
        potager, CTX, _item(action="recolte", culture="potiron", quantite=6, unite="kg",
                            parcelle="centrale"),
        "récolté 6 kg de potiron", parcelle,
    )

    stock = calcul_stock_cultures(potager, potager_id=1)["potiron"]

    assert stock.stock_plants == 3.0
    assert stock.unite == "poquets"
    assert stock.rendement_total == 6.0


# ─────────────────────────────────────────────────────────────────────────────
# CA7 — le récapitulatif du bot écrit l'unité en toutes lettres
# ─────────────────────────────────────────────────────────────────────────────

def test_ca7_recapitulatif_poquets() -> None:
    """CA7 : « 5 poquets »."""
    texte = _build_action_summary([_item(unite="poquets", parcelle="centrale")])

    assert "5 poquets" in texte


def test_ca7_recapitulatif_metre_de_rang() -> None:
    """CA7 : « 3 m de rang », pas « 3 ml »."""
    texte = _build_action_summary([_item(culture="carotte", quantite=3, unite="ml",
                                         parcelle="centrale")])

    assert "3 m de rang" in texte
    assert "ml" not in texte


def test_ca7_libelle_un_poquet_au_singulier() -> None:
    """CA7 : « 1 poquet »."""
    assert libelle_unite("poquets", 1) == "poquet"
    assert libelle_unite("poquets", 5) == "poquets"
    assert libelle_unite("plants", 5) == "plants"


def test_ca7_recapitulatif_multi_actions() -> None:
    """CA7 : même écriture quand plusieurs gestes sont confirmés d'un coup."""
    texte = _build_action_summary([
        _item(unite="poquets", parcelle="centrale"),
        _item(culture="carotte", quantite=3, unite="ml", parcelle="centrale"),
    ])

    assert "5 poquets" in texte
    assert "3 m de rang" in texte


# ─────────────────────────────────────────────────────────────────────────────
# Correction — l'unité corrigée à la main prend la même forme normalisée
# ─────────────────────────────────────────────────────────────────────────────

def test_ca1_correction_de_l_unite_m_donne_ml(potager) -> None:
    """CA1 : cas réel — « corriger » puis « 4 m » sur un semis (id=553) écrivait `m`.
    La correction passe par la même table qu'une création."""
    from app.services.evenements import corriger_evenement

    event = creer_evenement_confirme(potager, CTX, _item(culture="carotte", quantite=2, unite="ml",
                                                         parcelle="centrale"),
                                     "semer 2 mètres de carotte", potager.get(Parcelle, 1))

    corrige = corriger_evenement(potager, CTX, event.id, {"quantite": 4, "unite": "m"}, " | corr")

    assert (corrige.quantite, corrige.unite) == (4.0, "ml")


def test_ca1_correction_de_l_unite_en_poquets(potager) -> None:
    """CA1 : « unité poquet » corrige en `poquets` ; une unité ordinaire est laissée telle quelle."""
    from app.services.evenements import corriger_evenement

    event = creer_evenement_confirme(potager, CTX, _item(unite="graines", parcelle="centrale"),
                                     "semé 5 graines de courge", potager.get(Parcelle, 1))

    assert corriger_evenement(potager, CTX, event.id, {"unite": "poquet"}, "").unite == "poquets"
    assert corriger_evenement(potager, CTX, event.id, {"unite": "kg"}, "").unite == "kg"


def test_ca4_correction_vers_poquets_refusee_en_pepiniere(potager) -> None:
    """CA4 : corriger l'unité d'un semis en pépinière vers `poquets` est refusé."""
    from app.services.evenements import corriger_evenement

    event = creer_evenement_confirme(potager, CTX, _item(unite="graines", contexte_semis="pepiniere"),
                                     "semé 5 graines de courge en pépinière", None)

    with pytest.raises(UniteImplantationRefuseeError):
        corriger_evenement(potager, CTX, event.id, {"unite": "poquets"}, "")
