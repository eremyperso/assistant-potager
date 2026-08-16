"""
tests/test_us065_pepiniere_par_lot.py
[US-065] Pépinière par lot de semis avec un état de germination fiable

Couverture des critères d'acceptance :
  CA1 — lecture par lot (un semis = un lot), lot distinct pour les godets sans semis
  CA2 — graines soldées lot de godet par lot de godet (plus de solde anticipé)
  CA3 — état de germination à trois valeurs (en_cours / close / indeterminee)
  CA4 — incohérence de saisie signalée (plants cumulés > graines semées)
  CA5 — non-régression de calcul_godets() (contrat agrégé inchangé)
  CA6 — cycle de vie demandable pour un lot précis
  CA7 — tous les calculs bornés par la date de référence
  CA8 — déroulé de référence, semis échelonnés, lot orphelin, déclaration manquante

Note QA : US-065 est une US strictement backend (labels `backend`, `pepiniere` ;
« Zone fonctionnelle : analyse (calcul de stock) et consultation »). Aucun fichier
de `frontend/` n'est touché — le volet de validation visuelle à 375/768/1280 px ne
s'applique donc pas ici, il relève d'US-061 qui consomme cette brique de données.
"""
import pytest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement, Parcelle
from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from utils.stock import (
    calcul_godets,
    calcul_lots_pepiniere,
    ETAT_GERMINATION_CLOSE,
    ETAT_GERMINATION_EN_COURS,
    ETAT_GERMINATION_INDETERMINEE,
)

POTAGER_ID = 1


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def db():
    """Session SQLite en mémoire, tables recréées à chaque test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def ctx():
    """Contexte tenant du potager de test."""
    return TenantContext(user_id=1, potager_id=POTAGER_ID, role="owner")


def _semis(db, culture, variete, nb_graines, jour, parcelle_id=None, unite="graines"):
    """Semis en pépinière (aucune parcelle = pépinière, cf. _cond_semis_pleine_terre)."""
    e = Evenement(
        type_action = "semis",
        culture     = culture,
        variete     = variete,
        quantite    = float(nb_graines),
        unite       = unite,
        parcelle_id = parcelle_id,
        date        = datetime(2026, 3, 1) + _jours(jour),
        potager_id  = POTAGER_ID,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _godet(db, culture, variete, nb_plants, jour, nb_graines=None, origine=None):
    """Mise en godet, éventuellement rattachée à un semis parent."""
    e = Evenement(
        type_action        = "mise_en_godet",
        culture            = culture,
        variete            = variete,
        nb_plants_godets   = nb_plants,
        nb_graines_semees  = nb_graines,
        quantite           = float(nb_plants),
        unite              = "plants",
        origine_graines_id = origine.id if origine is not None else None,
        date               = datetime(2026, 3, 1) + _jours(jour),
        potager_id         = POTAGER_ID,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _plantation(db, culture, variete, quantite, jour, sources=None):
    """Plantation, éventuellement chaînée à ses godets sources (US-029)."""
    e = Evenement(
        type_action          = "plantation",
        culture              = culture,
        variete              = variete,
        quantite             = float(quantite),
        unite                = "plants",
        source_evenement_ids = ";".join(str(g.id) for g in sources) if sources else None,
        date                 = datetime(2026, 3, 1) + _jours(jour),
        potager_id           = POTAGER_ID,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _sortie(db, action, culture, variete, quantite, jour):
    """Vente ou perte en godet (jamais chaînée à un lot précis)."""
    e = Evenement(
        type_action = action,
        culture     = culture,
        variete     = variete,
        quantite    = float(quantite),
        unite       = "plants",
        date        = datetime(2026, 3, 1) + _jours(jour),
        potager_id  = POTAGER_ID,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _jours(n):
    from datetime import timedelta
    return timedelta(days=n)


def _lot(lots, lot_id):
    """Retrouve un lot par son identifiant, avec un message clair s'il manque."""
    trouve = [lot for lot in lots if lot["lot_id"] == lot_id]
    assert trouve, f"Lot '{lot_id}' absent de {[lot['lot_id'] for lot in lots]}"
    return trouve[0]


# ── CA8 / CA1 / CA2 / CA3 — déroulé de référence en quatre événements ────────

def test_us065_lots_pepiniere_deroule_reference_quatre_evenements(db) -> None:
    """[CA1, CA2, CA3, CA8] Semis 10 graines → 5 plants sur 5 graines → 2 plants sur
    5 graines → plantation de 5 godets : un seul lot, entièrement soldé à la fin."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    g1 = _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=30, nb_graines=5, origine=s)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=2, jour=45, nb_graines=5, origine=s)
    _plantation(db, "tomate", "Cœur de bœuf", quantite=5, jour=60, sources=[g1])

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 1, "un semis = un lot, les godets ne créent pas de lot supplémentaire"
    lot = lots[0]
    assert lot["semis_id"] == s.id
    assert lot["graines_semees"] == 10
    assert lot["graines_soldees"] == 10          # 5 + 5, lot de godet par lot de godet
    assert lot["graines_en_germination"] == 0
    assert lot["plants_obtenus"] == 7
    assert lot["nb_mises_en_godet"] == 2
    assert lot["nb_plantes"] == 5
    assert lot["stock_residuel_godet"] == 2
    assert lot["taux_germination"] == 70
    assert lot["etat_germination"] == ETAT_GERMINATION_CLOSE
    assert lot["incoherence_saisie"] is False
    assert lot["sans_semis_rattache"] is False


def test_us065_lots_pepiniere_repiquage_echelonne_sans_solde_anticipe(db) -> None:
    """[CA2, CA3] Après le PREMIER repiquage de 5 graines sur 10, il reste 5 graines
    en germination — le semis parent n'est plus soldé d'un coup."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=30, nb_graines=5, origine=s)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["graines_soldees"] == 5
    assert lot["graines_en_germination"] == 5
    assert lot["etat_germination"] == ETAT_GERMINATION_EN_COURS


def test_us065_lots_pepiniere_lot_semé_non_leve_reste_en_cours(db) -> None:
    """[CA3] Un lot sans aucune mise en godet est « en cours », à 0 % — jamais close."""
    # Arrange
    _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["etat_germination"] == ETAT_GERMINATION_EN_COURS
    assert lot["graines_en_germination"] == 10
    assert lot["taux_germination"] == 0


# ── CA1 / CA8 — semis échelonnés d'une même variété ──────────────────────────

def test_us065_lots_pepiniere_semis_echelonnes_suivis_separement(db) -> None:
    """[CA1, CA3, CA8] Gherkin « Deux semis échelonnés suivis séparément » : deux lots
    distincts identifiés par leur date, chacun avec son avancement et son état."""
    # Arrange
    s_mars  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)    # 1er mars
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=7, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)   # 1er avril

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 2
    lot_mars  = _lot(lots, f"semis-{s_mars.id}")
    lot_avril = _lot(lots, f"semis-{s_avril.id}")
    assert lot_mars["date_semis"].date()  == date(2026, 3, 1)
    assert lot_avril["date_semis"].date() == date(2026, 4, 1)
    assert lot_mars["taux_germination"]  == 70
    assert lot_avril["taux_germination"] == 0
    assert lot_mars["etat_germination"]  == ETAT_GERMINATION_CLOSE
    assert lot_avril["etat_germination"] == ETAT_GERMINATION_EN_COURS


def test_us065_lots_pepiniere_plantation_chainee_n_impacte_que_son_lot(db) -> None:
    """[CA1] Une plantation chaînée (US-029) est imputée au lot de ses godets sources,
    pas répartie sur tous les lots de la variété."""
    # Arrange
    s_mars  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    g_mars  = _godet(db, "tomate", "Cœur de bœuf", nb_plants=7, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=6, jour=50, nb_graines=10, origine=s_avril)
    _plantation(db, "tomate", "Cœur de bœuf", quantite=4, jour=60, sources=[g_mars])

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert _lot(lots, f"semis-{s_mars.id}")["nb_plantes"] == 4
    assert _lot(lots, f"semis-{s_mars.id}")["stock_residuel_godet"] == 3
    assert _lot(lots, f"semis-{s_avril.id}")["nb_plantes"] == 0
    assert _lot(lots, f"semis-{s_avril.id}")["stock_residuel_godet"] == 6


def test_us065_lots_pepiniere_sorties_non_chainees_imputees_fifo(db) -> None:
    """[CA1] Ventes et pertes en godet ne portent aucun chaînage : elles sont imputées
    au lot le plus ancien d'abord, dans la limite de ses plants disponibles."""
    # Arrange
    s_mars  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=3, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=50, nb_graines=10, origine=s_avril)
    _sortie(db, "vendu", "tomate", "Cœur de bœuf", quantite=5, jour=60)

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert _lot(lots, f"semis-{s_mars.id}")["nb_vendus"] == 3    # lot le plus ancien saturé
    assert _lot(lots, f"semis-{s_avril.id}")["nb_vendus"] == 2   # reliquat sur le suivant
    assert _lot(lots, f"semis-{s_mars.id}")["stock_residuel_godet"] == 0
    assert _lot(lots, f"semis-{s_avril.id}")["stock_residuel_godet"] == 3


# ── CA1 / CA8 — lot sans semis rattaché ──────────────────────────────────────

def test_us065_lots_pepiniere_godets_sans_semis_forment_un_lot_identifie(db) -> None:
    """[CA1, CA8] Les mises en godet sans semis rattaché forment un lot distinct,
    explicitement marqué `sans_semis_rattache`."""
    # Arrange
    _godet(db, "salade", "Batavia", nb_plants=12, jour=10, nb_graines=20, origine=None)

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 1
    lot = lots[0]
    assert lot["sans_semis_rattache"] is True
    assert lot["semis_id"] is None
    assert lot["date_semis"] is None
    assert lot["graines_semees"] == 20        # seul ce que la mise en godet a déclaré
    assert lot["plants_obtenus"] == 12
    assert lot["etat_germination"] == ETAT_GERMINATION_CLOSE
    assert lot["taux_germination"] == 60


def test_us065_lots_pepiniere_lot_orphelin_distinct_du_lot_semé(db) -> None:
    """[CA1] Un godet orphelin ne se fond pas dans le lot semé de la même variété."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=6, jour=20, nb_graines=10, origine=s)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=4, jour=25, nb_graines=8, origine=None)

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 2
    assert _lot(lots, f"semis-{s.id}")["plants_obtenus"] == 6
    orphelin = [lot for lot in lots if lot["sans_semis_rattache"]][0]
    assert orphelin["plants_obtenus"] == 4
    assert orphelin["graines_semees"] == 8


# ── CA3 / CA8 — nombre de graines non déclaré ────────────────────────────────

def test_us065_lots_pepiniere_godet_sans_graines_declarees_etat_indetermine(db) -> None:
    """[CA3, CA8] Gherkin « Nombre de graines non déclaré » : l'état est indéterminé,
    jamais présenté comme un « en cours »."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=30, nb_graines=None, origine=s)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["etat_germination"] == ETAT_GERMINATION_INDETERMINEE
    assert lot["etat_germination"] != ETAT_GERMINATION_EN_COURS
    assert lot["graines_soldees"] == 5          # repli sur le nombre de plants
    assert lot["graines_en_germination"] == 5   # erreur toujours dans le sens prudent


def test_us065_lots_pepiniere_une_seule_declaration_manquante_suffit(db) -> None:
    """[CA3] Un seul lot de godet non déclaré rend TOUT le lot indéterminé, même si
    les autres mises en godet ont bien renseigné leur nombre de graines."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=30, nb_graines=5, origine=s)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=2, jour=45, nb_graines=None, origine=s)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["etat_germination"] == ETAT_GERMINATION_INDETERMINEE


def test_us065_lots_pepiniere_declaration_incomplete_mais_graines_toutes_soldees(db) -> None:
    """[CA3] Une déclaration manquante ne rend le lot indéterminé que tant qu'elle
    laisse un doute sur la clôture.

    `graines_soldees` est un minorant : les 4 plants du second lot viennent d'au
    moins 4 graines. Le minorant atteint donc déjà les 10 graines semées, plus
    aucune ne peut rester à lever — la clôture est certaine et le taux définitif,
    même si le « sur N graines » manque sur ce second lot.
    """
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=5, jour=30, nb_graines=6, origine=s)
    _godet(db, "chou", None, nb_plants=4, jour=45, nb_graines=None, origine=s)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["graines_soldees"] == 10           # 6 déclarées + 4 en minorant
    assert lot["etat_germination"] == ETAT_GERMINATION_CLOSE
    assert lot["graines_en_germination"] == 0
    assert lot["taux_germination"] == 90          # 9 plants sur 10 graines, définitif


def test_us065_lots_pepiniere_semis_sans_quantite_est_indetermine(db) -> None:
    """[CA3] Edge case : un semis sans quantité connue ne peut pas être déclaré
    « close » — l'information manque, l'état le dit."""
    # Arrange
    _semis(db, "tomate", "Cœur de bœuf", 0, jour=0)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["etat_germination"] == ETAT_GERMINATION_INDETERMINEE
    assert lot["taux_germination"] is None


# ── CA4 / CA8 — incohérence de saisie ────────────────────────────────────────

def test_us065_lots_pepiniere_incoherence_plus_de_plants_que_de_graines(db) -> None:
    """[CA4, CA8] Gherkin « Incohérence de saisie signalée » : 12 plants pour 10 graines
    semées, cas non couvert par le garde-fou qui ne voit qu'un lot de godet à la fois."""
    # Arrange
    s = _semis(db, "fève", None, 10, jour=0)
    _godet(db, "fève", None, nb_plants=6, jour=20, nb_graines=6, origine=s)
    _godet(db, "fève", None, nb_plants=6, jour=25, nb_graines=6, origine=s)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["incoherence_saisie"] is True
    # [CA4] Valeurs exposées telles quelles, sans bornage qui masquerait le cas
    assert lot["plants_obtenus"] == 12
    assert lot["graines_semees"] == 10
    assert lot["taux_germination"] == 120


def test_us065_lots_pepiniere_pas_d_incoherence_sur_un_lot_normal(db) -> None:
    """[CA4] Le drapeau reste à False tant que les plants ne dépassent pas les graines."""
    # Arrange
    s = _semis(db, "fève", None, 10, jour=0)
    _godet(db, "fève", None, nb_plants=10, jour=20, nb_graines=10, origine=s)

    # Act
    lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["incoherence_saisie"] is False
    assert lot["taux_germination"] == 100


# ── CA7 — date de référence ──────────────────────────────────────────────────

def test_us065_lots_pepiniere_etat_calcule_a_la_date_de_reference(db) -> None:
    """[CA7] À une date antérieure au second repiquage, le lot est encore « en cours »
    avec 5 graines en germination — l'état est reconstitué, pas figé à aujourd'hui."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    g1 = _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=30, nb_graines=5, origine=s)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=2, jour=45, nb_graines=5, origine=s)
    _plantation(db, "tomate", "Cœur de bœuf", quantite=5, jour=60, sources=[g1])

    # Act — 5 avril 2026 : le premier repiquage a eu lieu, pas le second
    lot = calcul_lots_pepiniere(db, date_ref=date(2026, 4, 5), potager_id=POTAGER_ID)[0]

    # Assert
    assert lot["graines_soldees"] == 5
    assert lot["graines_en_germination"] == 5
    assert lot["plants_obtenus"] == 5
    assert lot["nb_plantes"] == 0
    assert lot["etat_germination"] == ETAT_GERMINATION_EN_COURS


def test_us065_lots_pepiniere_semis_posterieur_absent_a_la_date_de_reference(db) -> None:
    """[CA7] Un lot semé après la date de référence n'apparaît pas."""
    # Arrange
    _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)     # 1er mars
    _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)    # 1er avril

    # Act
    lots = calcul_lots_pepiniere(db, date_ref=date(2026, 3, 15), potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 1
    assert lots[0]["date_semis"].date() == date(2026, 3, 1)


# ── CA1 — isolation tenant et parcelles pépinière ────────────────────────────

def test_us065_lots_pepiniere_scope_par_potager(db) -> None:
    """[CA1] Un lot d'un autre potager n'est jamais retourné (scoping US-042)."""
    # Arrange
    _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    autre = Evenement(
        type_action="semis", culture="tomate", variete="Cœur de bœuf",
        quantite=99.0, unite="graines", date=datetime(2026, 3, 2), potager_id=99,
    )
    db.add(autre)
    db.commit()

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 1
    assert lots[0]["graines_semees"] == 10


def test_us065_lots_pepiniere_exclut_les_semis_pleine_terre(db) -> None:
    """[CA1] Un semis sur une vraie parcelle de pleine terre n'est pas un lot de
    pépinière — il alimente déjà le stock via calcul_stock_cultures (US-037)."""
    # Arrange
    pleine_terre = Parcelle(
        nom="Carré nord", nom_normalise="carrenord",
        est_pepiniere=False, actif=True, potager_id=POTAGER_ID,
    )
    serre = Parcelle(
        nom="Serre", nom_normalise="serre",
        est_pepiniere=True, actif=True, potager_id=POTAGER_ID,
    )
    db.add_all([pleine_terre, serre])
    db.commit()
    _semis(db, "radis", None, 100, jour=0, parcelle_id=pleine_terre.id)
    _semis(db, "tomate", "Cœur de bœuf", 10, jour=0, parcelle_id=serre.id)

    # Act
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)

    # Assert
    assert len(lots) == 1
    assert lots[0]["culture"] == "tomate"
    assert lots[0]["parcelle"] == "Serre"


def test_us065_lots_pepiniere_aucun_evenement_retourne_liste_vide(db) -> None:
    """[CA1] Edge case : pépinière vide → liste vide, jamais d'exception."""
    assert calcul_lots_pepiniere(db, potager_id=POTAGER_ID) == []


# ── CA6 — détail du cycle de vie pour un lot précis ──────────────────────────

def test_us065_cycle_vie_cible_un_lot_precis(db, ctx) -> None:
    """[CA6] Le détail peut cibler le lot affiché, et non plus seulement le couple
    culture + variété : seuls les godets du semis demandé remontent."""
    # Arrange
    s_mars  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    g_mars  = _godet(db, "tomate", "Cœur de bœuf", nb_plants=7, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=6, jour=50, nb_graines=10, origine=s_avril)
    _plantation(db, "tomate", "Cœur de bœuf", quantite=4, jour=60, sources=[g_mars])

    # Act
    cycle = svc_evenements.cycle_vie_culture(
        db, ctx, "tomate", "Cœur de bœuf", semis_id=s_mars.id
    )

    # Assert
    assert [s.id for s in cycle["semis"]]  == [s_mars.id]
    assert [g.id for g in cycle["godets"]] == [g_mars.id]
    assert [p.quantite for p in cycle["plantations"]] == [4.0]
    assert cycle["taux_germination"] == 70


def test_us065_cycle_vie_cible_le_lot_sans_semis_rattache(db, ctx) -> None:
    """[CA6] Le lot orphelin est adressable lui aussi, via `sans_semis_rattache`."""
    # Arrange
    s = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=7, jour=20, nb_graines=10, origine=s)
    g_orphelin = _godet(db, "tomate", "Cœur de bœuf", nb_plants=4, jour=25, nb_graines=8, origine=None)

    # Act
    cycle = svc_evenements.cycle_vie_culture(
        db, ctx, "tomate", "Cœur de bœuf", sans_semis_rattache=True
    )

    # Assert
    assert cycle["semis"] == []
    assert [g.id for g in cycle["godets"]] == [g_orphelin.id]


def test_us065_cycle_vie_sans_lot_reste_agrege(db, ctx) -> None:
    """[CA6] Sans paramètre de lot, le comportement historique (agrégé culture +
    variété) est conservé à l'identique — US-029 n'est pas régressée."""
    # Arrange
    s_mars  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    g_mars  = _godet(db, "tomate", "Cœur de bœuf", nb_plants=7, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)
    g_avril = _godet(db, "tomate", "Cœur de bœuf", nb_plants=6, jour=50, nb_graines=10, origine=s_avril)

    # Act
    cycle = svc_evenements.cycle_vie_culture(db, ctx, "tomate", "Cœur de bœuf")

    # Assert
    assert {s.id for s in cycle["semis"]}  == {s_mars.id, s_avril.id}
    assert {g.id for g in cycle["godets"]} == {g_mars.id, g_avril.id}
    assert cycle["taux_germination"] == 65   # (7 + 6) / (10 + 10)


# ── CA5 — non-régression de la lecture agrégée ───────────────────────────────

def test_us065_ca5_calcul_godets_inchange_sur_semis_echelonnes(db) -> None:
    """[CA5] Gherkin « Aucun impact sur les écrans agrégés » : calcul_godets() conserve
    exactement son contrat agrégé par culture + variété, y compris sa déduplication
    par origine_graines_id — c'est cette lecture qu'utilisent Stocks, /stats et le bot."""
    # Arrange — deux semis échelonnés de la même variété
    s_mars  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=7, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "tomate", "Cœur de bœuf", 10, jour=31)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=6, jour=50, nb_graines=10, origine=s_avril)

    # Act
    agrege = calcul_godets(db, include_epuises=True, potager_id=POTAGER_ID)

    # Assert — une seule entrée agrégée, pas deux lots
    assert list(agrege) == ["tomate (Cœur de bœuf)"]
    entree = agrege["tomate (Cœur de bœuf)"]
    assert entree["nb_godets"] == 2
    assert entree["nb_plants_godets"] == 13
    assert entree["nb_graines_semees"] == 20
    assert entree["stock_residuel_godet"] == 13
    assert entree["taux_reussite"] == 65      # 13 plants / 20 graines des semis parents
    # Le format agrégé n'expose aucun champ de la lecture par lot
    assert "etat_germination" not in entree
    assert "lot_id" not in entree


def test_us065_ca5_calcul_godets_inchange_sur_repiquage_echelonne(db) -> None:
    """[CA5] Sur le déroulé de référence, la lecture agrégée conserve son solde
    anticipé historique (10 graines dès le premier repiquage) — le correctif CA2 est
    strictement réservé à la nouvelle lecture par lot."""
    # Arrange
    s  = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    g1 = _godet(db, "tomate", "Cœur de bœuf", nb_plants=5, jour=30, nb_graines=5, origine=s)
    _godet(db, "tomate", "Cœur de bœuf", nb_plants=2, jour=45, nb_graines=5, origine=s)
    _plantation(db, "tomate", "Cœur de bœuf", quantite=5, jour=60, sources=[g1])

    # Act
    agrege = calcul_godets(db, include_epuises=True, potager_id=POTAGER_ID)
    par_lot = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)[0]

    # Assert — mêmes quantités brutes des deux côtés, seule la maille change
    entree = agrege["tomate (Cœur de bœuf)"]
    assert entree["nb_plants_godets"] == par_lot["plants_obtenus"] == 7
    assert entree["nb_plantes"] == par_lot["nb_plantes"] == 5
    assert entree["stock_residuel_godet"] == par_lot["stock_residuel_godet"] == 2
    assert entree["taux_reussite"] == par_lot["taux_germination"] == 70


# ══════════════════════════════════════════════════════════════════════════════
# Contrat HTTP — GET /pepiniere/lots et GET /godets/detail
#
# Même stratégie que tests/test_us026_pepiniere_frontend.py : SessionLocal et la
# fonction de calcul sont mockées, pour tester le contrat de l'endpoint sans
# dépendre d'une base réelle (problème de thread SQLite avec TestClient).
# ══════════════════════════════════════════════════════════════════════════════

_LOT_MOCK = {
    "lot_id":                      "semis-12",
    "semis_id":                    12,
    "culture":                     "tomate",
    "variete":                     "Cœur de bœuf",
    "date_semis":                  datetime(2026, 3, 1),
    "parcelle":                    "Serre",
    "graines_semees":              10,
    "unite":                       "graines",
    "graines_soldees":             5,
    "graines_en_germination":      5,
    "plants_obtenus":              5,
    "nb_mises_en_godet":           1,
    "date_derniere_mise_en_godet": datetime(2026, 3, 31),
    "nb_plantes":                  0,
    "nb_vendus":                   0,
    "nb_pertes_godet":             0,
    "stock_residuel_godet":        5,
    "etat_germination":            ETAT_GERMINATION_EN_COURS,
    "taux_germination":            50,
    "incoherence_saisie":          False,
    "sans_semis_rattache":         False,
}


@pytest.fixture
def client_lots():
    """Client HTTP avec la lecture par lot mockée et l'authentification neutralisée."""
    from unittest.mock import MagicMock, patch
    from fastapi.testclient import TestClient
    from main import app, get_current_user_ctx
    from app.services.context import default_context

    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.calcul_lots_pepiniere", return_value=[_LOT_MOCK]),
    ):
        yield TestClient(app)
    app.dependency_overrides.clear()


def test_us065_endpoint_pepiniere_lots_expose_les_lots(client_lots) -> None:
    """[CA1, CA3] GET /pepiniere/lots retourne les lots avec leur état de germination."""
    # Act
    reponse = client_lots.get("/pepiniere/lots")

    # Assert
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["total"] == 1
    lot = corps["lots"][0]
    assert lot["lot_id"] == "semis-12"
    assert lot["etat_germination"] == ETAT_GERMINATION_EN_COURS
    assert lot["graines_en_germination"] == 5
    assert lot["incoherence_saisie"] is False
    # Dates sérialisées en YYYY-MM-DD, comme les autres endpoints du dashboard
    assert lot["date_semis"] == "2026-03-01"
    assert lot["date_derniere_mise_en_godet"] == "2026-03-31"


def test_us065_endpoint_pepiniere_lots_date_ref_bornee_a_aujourdhui(client_lots) -> None:
    """[CA7] Une date de référence future est ramenée à aujourd'hui, comme GET /godets."""
    # Act
    reponse = client_lots.get("/pepiniere/lots", params={"date_ref": "2099-01-01"})

    # Assert
    assert reponse.status_code == 200
    assert reponse.json()["date_ref_effective"] == date.today().isoformat()


def test_us065_endpoint_godet_detail_transmet_le_lot_cible() -> None:
    """[CA6] GET /godets/detail relaie semis_id au service et le rappelle en réponse."""
    from unittest.mock import MagicMock, patch
    from fastapi.testclient import TestClient
    from main import app, get_current_user_ctx
    from app.services.context import default_context

    cycle_vide = {
        "semis": [], "godets": [], "plantations": [],
        "ventes": [], "pertes_godet": [], "taux_germination": None,
    }
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("main.SessionLocal", return_value=MagicMock()),
        patch("app.services.evenements.cycle_vie_culture", return_value=cycle_vide) as mock_cycle,
    ):
        client = TestClient(app)
        # Act
        reponse = client.get("/godets/detail", params={"culture": "tomate", "semis_id": 12})
    app.dependency_overrides.clear()

    # Assert
    assert reponse.status_code == 200
    assert reponse.json()["semis_id"] == 12
    assert mock_cycle.call_args.kwargs["semis_id"] == 12
    assert mock_cycle.call_args.kwargs["sans_semis_rattache"] is False
