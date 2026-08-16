"""
tests/test_fix_rattachement_lot_godet.py
[fix rattachement lot godet] Choix du lot de semis parent d'une mise en godet

Contexte : US-065 expose la pépinière lot par lot, mais rien ne permettait
d'ALIMENTER un lot précis. `creer_evenement_godet` ne rattachait un godet à son
semis que s'il existait exactement UN semis pour la culture — deux semis
échelonnés laissaient `origine_graines_id` à NULL, et aucun des deux lots
n'avançait.

Couverture :
  - lots_candidats_mise_en_godet : sélection, tri FIFO, exclusions
  - creer_evenement_godet        : lot explicite, déduction, ambiguïté, repli
  - bot                          : menu inline de choix du lot, callback, refus
  - bout en bout                 : seul le lot choisi avance dans la pépinière
"""
import time
from datetime import datetime

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.db import Base
from database.models import Evenement, Parcelle
from app.services.context import TenantContext
from app.services import evenements as svc_evenements
from utils.stock import (
    calcul_lots_pepiniere,
    lots_candidats_mise_en_godet,
    lot_pepiniere_par_semis,
    ETAT_GERMINATION_EN_COURS,
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
    return TenantContext(user_id=1, potager_id=POTAGER_ID, role="owner")


def _semis(db, culture, variete, nb_graines, jour, parcelle_id=None, potager_id=POTAGER_ID):
    e = Evenement(
        type_action="semis", culture=culture, variete=variete,
        quantite=float(nb_graines), unite="graines", parcelle_id=parcelle_id,
        date=datetime(2026, 3, 1) + _j(jour), potager_id=potager_id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _godet(db, culture, variete, nb_plants, jour, nb_graines=None, origine=None):
    e = Evenement(
        type_action="mise_en_godet", culture=culture, variete=variete,
        nb_plants_godets=nb_plants, nb_graines_semees=nb_graines,
        quantite=float(nb_plants), unite="plants",
        origine_graines_id=origine.id if origine is not None else None,
        date=datetime(2026, 3, 1) + _j(jour), potager_id=POTAGER_ID,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def _j(n):
    from datetime import timedelta
    return timedelta(days=n)


def _parsed_godet(culture="chou", variete=None, nb_plants=5, nb_graines=None, **extra):
    """Dict de parsing d'une mise en godet, tel que produit par Groq."""
    base = {
        "action": "mise_en_godet", "culture": culture, "variete": variete,
        "nb_plants_godets": nb_plants, "nb_graines_semees": nb_graines,
        "quantite": float(nb_plants), "unite": "plants",
        "date": None, "commentaire": None,
    }
    base.update(extra)
    return base


# ── lots_candidats_mise_en_godet ─────────────────────────────────────────────

def test_lots_candidats_deux_semis_echelonnes_tries_fifo(db) -> None:
    """Les deux semis de chou du scénario réel sont proposés, du plus ancien au
    plus récent — c'est exactement le cas où la déduction automatique échouait."""
    # Arrange — reproduit la saisie bot : 10 graines le 1er mars, 15 le 1er avril
    s_mars  = _semis(db, "chou", None, 10, jour=0)
    s_avril = _semis(db, "chou", None, 15, jour=31)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "chou", potager_id=POTAGER_ID)

    # Assert
    assert [lot["semis_id"] for lot in candidats] == [s_mars.id, s_avril.id]
    assert [lot["graines_en_germination"] for lot in candidats] == [10, 15]


def test_lots_candidats_exclut_lot_entierement_solde(db) -> None:
    """Un lot dont toutes les graines sont soldées n'a plus rien à recevoir."""
    # Arrange
    s_solde = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=7, jour=20, nb_graines=10, origine=s_solde)
    s_ouvert = _semis(db, "chou", None, 15, jour=31)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "chou", potager_id=POTAGER_ID)

    # Assert
    assert [lot["semis_id"] for lot in candidats] == [s_ouvert.id]


def test_lots_candidats_inclut_lot_partiellement_repique(db) -> None:
    """Un lot partiellement repiqué reste candidat pour ses graines restantes."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=5, jour=20, nb_graines=4, origine=s)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "chou", potager_id=POTAGER_ID)

    # Assert
    assert len(candidats) == 1
    assert candidats[0]["graines_en_germination"] == 6


def test_lots_candidats_exclut_semis_pleine_terre(db) -> None:
    """Correction du filtre historique : un godet ne provient jamais d'un semis en
    pleine terre, qui ne doit donc ni être proposé ni bloquer la déduction."""
    # Arrange
    terre = Parcelle(nom="Carré nord", nom_normalise="carrenord",
                     est_pepiniere=False, actif=True, potager_id=POTAGER_ID)
    db.add(terre)
    db.commit()
    _semis(db, "chou", None, 100, jour=0, parcelle_id=terre.id)
    s_pepiniere = _semis(db, "chou", None, 10, jour=5)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "chou", potager_id=POTAGER_ID)

    # Assert
    assert [lot["semis_id"] for lot in candidats] == [s_pepiniere.id]


def test_lots_candidats_filtre_sur_la_variete_quand_fournie(db) -> None:
    """Une variété connue restreint les candidats à ses seuls lots."""
    # Arrange
    s_coeur = _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)
    _semis(db, "tomate", "Cerise", 10, jour=5)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "tomate", "Cœur de bœuf", potager_id=POTAGER_ID)

    # Assert
    assert [lot["semis_id"] for lot in candidats] == [s_coeur.id]


def test_lots_candidats_sans_variete_exclut_les_lots_varietaux(db) -> None:
    """Cas réel : « Variété non précisée » et « bruxelle » coexistent pour le chou.
    Un repiquage sans variété ne doit se voir proposer QUE les lots sans variété —
    sinon le menu offre un lot bruxelle à qui vient de répondre « non précisée »."""
    # Arrange
    s_sans_variete = _semis(db, "chou", None, 27, jour=0)
    _semis(db, "chou", "bruxelle", 50, jour=0)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "chou", None, potager_id=POTAGER_ID)

    # Assert
    assert [lot["semis_id"] for lot in candidats] == [s_sans_variete.id]


def test_lots_candidats_exclut_les_autres_potagers(db) -> None:
    """Le scoping tenant s'applique aussi au choix du lot parent."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _semis(db, "chou", None, 10, jour=1, potager_id=99)

    # Act
    candidats = lots_candidats_mise_en_godet(db, "chou", potager_id=POTAGER_ID)

    # Assert
    assert [lot["semis_id"] for lot in candidats] == [s.id]


def test_lot_pepiniere_par_semis_retrouve_le_lot(db) -> None:
    """Le garde-fou d'écriture a besoin de l'état d'un lot précis avant d'y ajouter
    des godets."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=5, jour=20, nb_graines=6, origine=s)

    # Act
    lot = lot_pepiniere_par_semis(db, s.id, potager_id=POTAGER_ID)

    # Assert
    assert lot["graines_en_germination"] == 4
    assert lot_pepiniere_par_semis(db, 999_999, potager_id=POTAGER_ID) is None


# ── creer_evenement_godet — rattachement ─────────────────────────────────────

def test_creer_godet_rattache_le_lot_explicitement_choisi(db, ctx) -> None:
    """Le lot désigné par le jardinier prime sur toute déduction."""
    # Arrange
    _semis(db, "chou", None, 10, jour=0)
    s_avril = _semis(db, "chou", None, 15, jour=31)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(origine_graines_id=s_avril.id), "mise en godet"
    )

    # Assert
    assert event.origine_graines_id == s_avril.id


def test_creer_godet_herite_la_variete_du_lot_choisi(db, ctx) -> None:
    """[US-029 CA4] L'héritage de variété fonctionne aussi via le lot explicite."""
    # Arrange
    _semis(db, "tomate", "Cerise", 10, jour=0)
    s_coeur = _semis(db, "tomate", "Cœur de bœuf", 10, jour=5)
    parsed = _parsed_godet(culture="tomate", origine_graines_id=s_coeur.id)

    # Act
    event = svc_evenements.creer_evenement_godet(db, ctx, parsed, "mise en godet")

    # Assert
    assert event.variete == "Cœur de bœuf"
    assert parsed["variete"] == "Cœur de bœuf"


def test_creer_godet_lot_inexistant_rejete(db, ctx) -> None:
    """Un identifiant de lot invalide est refusé — jamais de repli silencieux sur
    un autre lot, le lien porte tout l'avancement de la pépinière."""
    # Arrange
    _semis(db, "chou", None, 10, jour=0)

    # Act / Assert
    with pytest.raises(svc_evenements.LotSemisInconnuError):
        svc_evenements.creer_evenement_godet(
            db, ctx, _parsed_godet(origine_graines_id=999_999), "mise en godet"
        )


def test_creer_godet_lot_d_un_autre_potager_rejete(db, ctx) -> None:
    """Un lot appartenant à un autre potager n'est jamais rattachable."""
    # Arrange
    s_autre = _semis(db, "chou", None, 10, jour=0, potager_id=99)

    # Act / Assert
    with pytest.raises(svc_evenements.LotSemisInconnuError):
        svc_evenements.creer_evenement_godet(
            db, ctx, _parsed_godet(origine_graines_id=s_autre.id), "mise en godet"
        )


def test_creer_godet_deduit_le_lot_unique(db, ctx) -> None:
    """Comportement historique préservé : un seul candidat → rattachement automatique."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)

    # Act
    event = svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(), "mise en godet")

    # Assert
    assert event.origine_graines_id == s.id


def test_creer_godet_ambigu_sans_choix_est_refuse(db, ctx) -> None:
    """Deux candidats et aucun choix → refus. Enregistrer un orphelin « en attendant »
    contournerait le garde-fou : des lots existent et peuvent porter ce repiquage,
    seul leur choix manque. Et aucun lot n'est jamais tiré au hasard."""
    # Arrange
    _semis(db, "chou", None, 10, jour=0)
    _semis(db, "chou", None, 15, jour=31)

    # Act / Assert
    with pytest.raises(svc_evenements.LotIndetermineError) as err:
        svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(), "mise en godet")
    assert err.value.nb_lots == 2


def test_creer_godet_variete_non_precisee_ignore_les_lots_varietaux(db, ctx) -> None:
    """« Sans variété » ne veut pas dire « toutes variétés » : un lot « bruxelle »
    n'est pas candidat pour un repiquage explicitement déclaré sans variété."""
    # Arrange — un seul lot sans variété, plus un lot varietal qui ne doit pas compter
    s_sans_variete = _semis(db, "chou", None, 27, jour=0)
    _semis(db, "chou", "bruxelle", 50, jour=0)

    # Act — un seul candidat réel, donc déduction directe sans ambiguïté
    event = svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(nb_plants=10), "10 choux")

    # Assert
    assert event.origine_graines_id == s_sans_variete.id
    assert event.variete is None


def test_creer_godet_lot_entierement_solde_est_refuse(db, ctx) -> None:
    """Un lot sans graine restante n'est pas un parent — mais le godet ne passe pas
    orphelin pour autant : le potager sait que toutes les graines sont soldées."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=7, jour=20, nb_graines=10, origine=s)

    # Act / Assert
    with pytest.raises(svc_evenements.AucunLotDisponibleError) as err:
        svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(), "second repiquage")
    assert err.value.meilleur_reste == 0
    assert "entièrement soldés" in str(err.value)


def test_creer_godet_semis_pleine_terre_n_est_plus_parent(db, ctx) -> None:
    """Correction du filtre historique : un semis en pleine terre ne devient jamais
    le parent d'un godet, même s'il est le seul semis de la culture."""
    # Arrange
    terre = Parcelle(nom="Carré nord", nom_normalise="carrenord",
                     est_pepiniere=False, actif=True, potager_id=POTAGER_ID)
    db.add(terre)
    db.commit()
    _semis(db, "radis", None, 100, jour=0, parcelle_id=terre.id)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(culture="radis"), "mise en godet"
    )

    # Assert
    assert event.origine_graines_id is None


def test_creer_godet_sans_aucun_semis_reste_orphelin(db, ctx) -> None:
    """Edge case : aucune trace de semis → godet enregistré sans parent (inchangé)."""
    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(culture="courgette"), "mise en godet"
    )

    # Assert
    assert event.origine_graines_id is None


# ── Garde-fou : pas plus de graines soldées que le lot n'en contient ────────

def test_garde_fou_refuse_plus_de_graines_que_le_lot_n_en_a(db, ctx) -> None:
    """Cas réel : lot de 10 graines dont 6 déjà soldées, puis « mise en godet 10 plants
    de chou » — le garde-fou existant ne voit rien (nb_graines_semees absent), le
    cumul sur le lot le refuse."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=5, jour=20, nb_graines=6, origine=s)

    # Act / Assert
    with pytest.raises(svc_evenements.LotGrainesEpuiseesError) as err:
        svc_evenements.creer_evenement_godet(
            db, ctx,
            _parsed_godet(nb_plants=10, origine_graines_id=s.id),
            "mise en godet 10 plants de chou",
        )
    assert err.value.graines_restantes == 4
    assert err.value.graines_demandees == 10
    assert "4 graine" in str(err.value)


def test_garde_fou_accepte_exactement_le_reste(db, ctx) -> None:
    """La borne est inclusive : solder les 4 dernières graines est légitime."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=5, jour=20, nb_graines=6, origine=s)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(nb_plants=4, origine_graines_id=s.id), "4 choux en godet"
    )

    # Assert
    assert event.origine_graines_id == s.id
    lot = [l for l in calcul_lots_pepiniere(db, potager_id=POTAGER_ID) if l["semis_id"] == s.id][0]
    assert lot["graines_en_germination"] == 0


def test_garde_fou_refuse_sur_le_nombre_de_graines_declare(db, ctx) -> None:
    """Le contrôle porte sur les graines SOLDÉES, pas sur les plants : 3 plants « sur
    6 graines » soldent 6 graines, alors qu'il n'en reste que 4."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=5, jour=20, nb_graines=6, origine=s)

    # Act / Assert
    with pytest.raises(svc_evenements.LotGrainesEpuiseesError):
        svc_evenements.creer_evenement_godet(
            db, ctx,
            _parsed_godet(nb_plants=3, nb_graines=6, origine_graines_id=s.id),
            "3 choux en godet sur 6 graines",
        )


def test_garde_fou_muet_si_quantite_du_semis_inconnue(db, ctx) -> None:
    """Un semis sans quantité ne permet aucune déduction : ne jamais bloquer sur une
    information absente."""
    # Arrange
    s = _semis(db, "chou", None, 0, jour=0)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(nb_plants=10, origine_graines_id=s.id), "10 choux en godet"
    )

    # Assert
    assert event.origine_graines_id == s.id


def test_garde_fou_muet_sur_un_godet_sans_lot(db, ctx) -> None:
    """Sans lot parent, il n'existe aucune quantité de référence — rien à contrôler."""
    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(culture="courgette", nb_plants=50), "50 courgettes en godet"
    )

    # Assert
    assert event.origine_graines_id is None
    assert event.nb_plants_godets == 50


def test_garde_fou_existant_reste_prioritaire(db, ctx) -> None:
    """Le contrôle intra-événement (plants > graines du même lot de godet) continue
    de s'appliquer, avec son message dédié."""
    # Arrange
    _semis(db, "chou", None, 10, jour=0)

    # Act / Assert
    with pytest.raises(svc_evenements.TauxGerminationImpossibleError):
        svc_evenements.creer_evenement_godet(
            db, ctx, _parsed_godet(nb_plants=8, nb_graines=5), "8 choux sur 5 graines"
        )


def test_garde_fou_refuse_aussi_le_lot_deduit_automatiquement(db, ctx) -> None:
    """Le contrôle ne dépend pas du canal : il s'applique aussi sans intervention du
    jardinier. En déduction, le lot trop petit est écarté avant d'être choisi, d'où
    le message « aucun lot ne peut fournir » plutôt que « ce lot est épuisé »."""
    # Arrange — un seul lot, 1 graine restante, on en demande 5
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=9, jour=20, nb_graines=9, origine=s)

    # Act / Assert
    with pytest.raises(svc_evenements.AucunLotDisponibleError) as err:
        svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(nb_plants=5), "5 choux en godet")
    assert err.value.meilleur_reste == 1


def test_garde_fou_lot_choisi_devenu_insuffisant_est_refuse(db, ctx) -> None:
    """`LotGrainesEpuiseesError` couvre le choix EXPLICITE d'un lot devenu trop
    petit — menu affiché puis état modifié entre-temps, ou appel direct au service."""
    # Arrange
    s = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=9, jour=20, nb_graines=9, origine=s)

    # Act / Assert
    with pytest.raises(svc_evenements.LotGrainesEpuiseesError) as err:
        svc_evenements.creer_evenement_godet(
            db, ctx, _parsed_godet(nb_plants=5, origine_graines_id=s.id), "5 choux en godet"
        )
    assert err.value.graines_restantes == 1


def test_garde_fou_n_empeche_pas_le_second_lot(db, ctx) -> None:
    """Un lot saturé ne bloque pas les autres : le second lot reste utilisable."""
    # Arrange
    s_mars  = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=9, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "chou", None, 7, jour=31)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(nb_plants=5, nb_graines=7, origine_graines_id=s_avril.id), "5 choux"
    )

    # Assert
    assert event.origine_graines_id == s_avril.id


# ── Garde-fou : plus aucun lot capable ≠ godet orphelin ─────────────────────

def test_garde_fou_refuse_quand_tous_les_lots_sont_epuises(db, ctx) -> None:
    """Séquence réelle : les deux lots de chou sont soldés, puis « mise en godet de
    5 plants de chou ». Sans cette règle, l'absence de candidat supprimait le
    rattachement — donc le contrôle — et le godet passait orphelin, en silence."""
    # Arrange — lot de mars soldé, lot d'avril soldé
    s_mars = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=8, jour=20, nb_graines=10, origine=s_mars)
    s_avril = _semis(db, "chou", None, 7, jour=31)
    _godet(db, "chou", None, nb_plants=5, jour=40, nb_graines=7, origine=s_avril)

    # Act / Assert
    with pytest.raises(svc_evenements.AucunLotDisponibleError) as err:
        svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(nb_plants=5), "5 choux en godet")
    assert err.value.graines_demandees == 5
    assert err.value.meilleur_reste == 0


def test_garde_fou_refuse_quand_aucun_lot_n_est_assez_grand(db, ctx) -> None:
    """Deux lots ont encore des graines, mais aucun n'en a assez : une mise en godet
    vient d'UNE barquette, le besoin n'est jamais réparti sur deux lots."""
    # Arrange — 2 restantes sur mars, 3 sur avril, on demande 4
    s_mars = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=8, jour=20, nb_graines=8, origine=s_mars)
    s_avril = _semis(db, "chou", None, 7, jour=31)
    _godet(db, "chou", None, nb_plants=4, jour=40, nb_graines=4, origine=s_avril)

    # Act / Assert
    with pytest.raises(svc_evenements.AucunLotDisponibleError) as err:
        svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(nb_plants=4), "4 choux en godet")
    assert err.value.meilleur_reste == 3
    assert "3 graine" in str(err.value)


def test_garde_fou_choisit_le_seul_lot_assez_grand(db, ctx) -> None:
    """Le filtrage par capacité lève l'ambiguïté quand un seul lot peut porter le
    repiquage : pas de question, rattachement direct au bon lot."""
    # Arrange — 2 restantes sur mars, 7 sur avril, on demande 5
    s_mars = _semis(db, "chou", None, 10, jour=0)
    _godet(db, "chou", None, nb_plants=8, jour=20, nb_graines=8, origine=s_mars)
    s_avril = _semis(db, "chou", None, 7, jour=31)

    # Act
    event = svc_evenements.creer_evenement_godet(db, ctx, _parsed_godet(nb_plants=5), "5 choux")

    # Assert
    assert event.origine_graines_id == s_avril.id


def test_garde_fou_laisse_passer_une_culture_sans_aucun_semis(db, ctx) -> None:
    """Cas légitime préservé : plants achetés, bouture ou don — aucun semis n'existe
    pour cette culture, le godet sans parent reste autorisé."""
    # Arrange — des lots de chou existent, mais on met des courgettes en godet
    _semis(db, "chou", None, 10, jour=0)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(culture="courgette", nb_plants=12), "12 courgettes en godet"
    )

    # Assert
    assert event.origine_graines_id is None
    assert event.nb_plants_godets == 12


def test_garde_fou_variete_sans_semis_reste_autorisee(db, ctx) -> None:
    """Même raisonnement à la maille variété : « Cerise » n'a aucun lot, même si
    « Cœur de bœuf » en a."""
    # Arrange
    _semis(db, "tomate", "Cœur de bœuf", 10, jour=0)

    # Act
    event = svc_evenements.creer_evenement_godet(
        db, ctx, _parsed_godet(culture="tomate", variete="Cerise", nb_plants=6), "6 cerises"
    )

    # Assert
    assert event.origine_graines_id is None
    assert event.variete == "Cerise"


@pytest.mark.asyncio
async def test_bot_menu_ne_propose_que_les_lots_capables() -> None:
    """Le menu ne promet jamais un choix que l'écriture refuserait : avec un seul lot
    assez fourni, aucune question n'est posée."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _demander_lot_godet_si_ambigu
    _GODET_LOT_PENDING.clear()
    update, message = _mock_update()
    captures = {}

    def _faux_candidats(db, ctx, culture, variete, graines_requises=0):
        captures["graines_requises"] = graines_requises
        return [lot for lot in _LOTS_DEUX if lot["graines_en_germination"] >= max(1, graines_requises)]

    # Act — 12 plants : seul le lot de 15 graines peut porter
    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lots_candidats_mise_en_godet", side_effect=_faux_candidats),
    ):
        pose = await _demander_lot_godet_si_ambigu(update, _parsed_godet(nb_plants=12), "12 choux")

    # Assert
    assert captures["graines_requises"] == 12
    assert pose is False
    message.reply_text.assert_not_called()


# ── Bout en bout — seul le lot choisi avance ─────────────────────────────────

def test_bout_en_bout_seul_le_lot_choisi_avance(db, ctx) -> None:
    """Le scénario exact demandé : repiquer sur le lot le plus ancien en laissant
    l'état du lot suivant intact, pour la même culture."""
    # Arrange — les deux semis de chou du test réel
    s_mars  = _semis(db, "chou", None, 10, jour=0)
    s_avril = _semis(db, "chou", None, 15, jour=31)

    # Act — repiquage de 6 plants sur 6 graines du lot de mars
    svc_evenements.creer_evenement_godet(
        db, ctx,
        _parsed_godet(nb_plants=6, nb_graines=6, origine_graines_id=s_mars.id),
        "6 choux en godet sur 6 graines",
    )
    lots = calcul_lots_pepiniere(db, potager_id=POTAGER_ID)
    lot_mars  = [lot for lot in lots if lot["semis_id"] == s_mars.id][0]
    lot_avril = [lot for lot in lots if lot["semis_id"] == s_avril.id][0]

    # Assert — le lot de mars avance…
    assert lot_mars["plants_obtenus"] == 6
    assert lot_mars["graines_en_germination"] == 4
    assert lot_mars["taux_germination"] == 60
    # …et celui d'avril est rigoureusement intact
    assert lot_avril["plants_obtenus"] == 0
    assert lot_avril["graines_en_germination"] == 15
    assert lot_avril["taux_germination"] == 0
    assert lot_avril["etat_germination"] == ETAT_GERMINATION_EN_COURS


# ── Bot — menu inline de choix du lot ────────────────────────────────────────

def _mock_update(user_id=42):
    """Update Telegram minimal, compatible contexte message ET callback."""
    update = MagicMock()
    message = AsyncMock()
    update.message = message
    update.effective_message = message
    update.effective_user = MagicMock(id=user_id)
    return update, message


_LOTS_DEUX = [
    {"semis_id": 374, "date_semis": datetime(2026, 3, 1), "graines_en_germination": 10,
     "culture": "chou", "variete": None},
    {"semis_id": 375, "date_semis": datetime(2026, 4, 1), "graines_en_germination": 15,
     "culture": "chou", "variete": None},
]


@pytest.mark.asyncio
async def test_bot_deux_lots_declenchent_le_menu_inline() -> None:
    """Deux lots candidats → question posée avec un bouton par lot, et l'appelant
    est prié de s'arrêter (aucun enregistrement immédiat)."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _demander_lot_godet_si_ambigu
    from telegram import InlineKeyboardMarkup
    _GODET_LOT_PENDING.clear()
    update, message = _mock_update()
    parsed = _parsed_godet()

    # Act
    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lots_candidats_mise_en_godet", return_value=_LOTS_DEUX),
    ):
        pose = await _demander_lot_godet_si_ambigu(update, parsed, "5 choux en godet")

    # Assert
    assert pose is True
    assert 42 in _GODET_LOT_PENDING
    markup = message.reply_text.call_args[1]["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    libelles = [b[0].text for b in markup.inline_keyboard]
    assert "01/03/2026 — 10 graines restantes" in libelles
    assert "01/04/2026 — 15 graines restantes" in libelles
    _GODET_LOT_PENDING.clear()


@pytest.mark.asyncio
async def test_bot_lot_unique_ne_declenche_pas_de_question() -> None:
    """Un seul candidat : la déduction automatique suffit, aucune question."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _demander_lot_godet_si_ambigu
    _GODET_LOT_PENDING.clear()
    update, message = _mock_update()

    # Act
    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lots_candidats_mise_en_godet", return_value=_LOTS_DEUX[:1]),
    ):
        pose = await _demander_lot_godet_si_ambigu(update, _parsed_godet(), "5 choux en godet")

    # Assert
    assert pose is False
    message.reply_text.assert_not_called()
    assert _GODET_LOT_PENDING == {}


@pytest.mark.asyncio
async def test_bot_lot_deja_choisi_ne_redemande_jamais() -> None:
    """Anti-boucle : une fois le choix fait (lot désigné OU refus explicite), la
    question n'est plus reposée."""
    # Arrange
    from bot import _demander_lot_godet_si_ambigu
    update, message = _mock_update()

    # Act
    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lots_candidats_mise_en_godet", return_value=_LOTS_DEUX),
    ):
        avec_lot   = await _demander_lot_godet_si_ambigu(
            update, _parsed_godet(origine_graines_id=374), "t")
        apres_refus = await _demander_lot_godet_si_ambigu(
            update, _parsed_godet(_lot_choisi=True), "t")

    # Assert
    assert avec_lot is False
    assert apres_refus is False
    message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_bot_callback_lot_choisi_transmet_l_origine() -> None:
    """Le callback fixe `origine_graines_id` puis relance la sauvegarde."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _godet_lot_cb
    parsed = _parsed_godet()
    _GODET_LOT_PENDING[42] = {
        "parsed": parsed, "texte": "5 choux en godet", "ts": time.time(),
        "labels": {374: "01/03/2026"},
    }
    update, _ = _mock_update()
    update.callback_query = AsyncMock()
    update.callback_query.data = "godetlot:374"

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_lot_cb(update, MagicMock())

    # Assert
    assert parsed["origine_graines_id"] == 374
    assert parsed["_lot_choisi"] is True
    mock_save.assert_awaited_once()
    assert 42 not in _GODET_LOT_PENDING


@pytest.mark.asyncio
async def test_bot_menu_sans_echappatoire_je_ne_sais_pas() -> None:
    """Le menu n'offre que les lots et « Annuler » : pas de bouton qui enregistrerait
    un godet orphelin alors que des lots existent et peuvent le porter."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _demander_lot_godet_si_ambigu
    _GODET_LOT_PENDING.clear()
    update, message = _mock_update()

    # Act
    with (
        patch("bot.SessionLocal", return_value=MagicMock()),
        patch("app.services.stock.lots_candidats_mise_en_godet", return_value=_LOTS_DEUX),
    ):
        await _demander_lot_godet_si_ambigu(update, _parsed_godet(), "5 choux en godet")

    # Assert
    markup = message.reply_text.call_args[1]["reply_markup"]
    callbacks = [b[0].callback_data for b in markup.inline_keyboard]
    assert "godetlot:__aucun__" not in callbacks
    assert callbacks == ["godetlot:374", "godetlot:375", "godetlot_cancel"]
    _GODET_LOT_PENDING.clear()


@pytest.mark.asyncio
async def test_bot_callback_annulation_n_enregistre_rien() -> None:
    """Annuler ne sauvegarde aucun événement."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _godet_lot_cb
    _GODET_LOT_PENDING[42] = {
        "parsed": _parsed_godet(), "texte": "t", "ts": time.time(), "labels": {},
    }
    update, _ = _mock_update()
    update.callback_query = AsyncMock()
    update.callback_query.data = "godetlot_cancel"

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_lot_cb(update, MagicMock())

    # Assert
    mock_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_callback_expire_ne_sauvegarde_pas() -> None:
    """Timeout dépassé → message d'annulation, aucun enregistrement."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _GODET_LOT_TIMEOUT, _godet_lot_cb
    _GODET_LOT_PENDING[42] = {
        "parsed": _parsed_godet(), "texte": "t",
        "ts": time.time() - _GODET_LOT_TIMEOUT - 1, "labels": {},
    }
    update, _ = _mock_update()
    update.callback_query = AsyncMock()
    update.callback_query.data = "godetlot:374"

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_lot_cb(update, MagicMock())

    # Assert
    mock_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_bot_callback_sans_pending_ne_sauvegarde_pas() -> None:
    """Cas d'erreur : plus aucun contexte en mémoire (redémarrage du bot)."""
    # Arrange
    from bot import _GODET_LOT_PENDING, _godet_lot_cb
    _GODET_LOT_PENDING.clear()
    update, _ = _mock_update()
    update.callback_query = AsyncMock()
    update.callback_query.data = "godetlot:374"

    # Act
    with patch("bot._save_godet_item", new=AsyncMock()) as mock_save:
        await _godet_lot_cb(update, MagicMock())

    # Assert
    mock_save.assert_not_awaited()


def test_bot_les_deux_motifs_de_callback_ne_se_recouvrent_pas() -> None:
    """Garde-fou de routage : `^godet_` (variété, US-019) et `^godetlot` (lot) sont
    disjoints — un clic sur un lot ne doit jamais atterrir dans le handler variété."""
    import re

    motif_variete = re.compile(r"^godet_")
    motif_lot     = re.compile(r"^godetlot")

    assert motif_lot.match("godetlot:374")
    assert motif_lot.match("godetlot_cancel")
    assert not motif_variete.match("godetlot:374")
    assert not motif_variete.match("godetlot_cancel")
    assert not motif_lot.match("godet_var:Cerise")
    assert not motif_lot.match("godet_confirm")
