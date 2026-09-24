"""
tests/test_us232_journal_sol_parcelle.py — Journal du sol et de l'entretien
d'une parcelle [US-232]

Cette US n'invente **aucun enregistrement** : un paillage, un apport de compost,
un binage sont déjà des événements rattachés à une parcelle. Elle filtre et
regroupe ce qui existe, à l'échelle de la planche.

Ce qui se vérifie ici est donc le DOMAINE, et lui seul :

- CA1  la liste est produite par un service d'`app/services/`, jamais par un
       `db.query` posé dans un handler (règle du test US-041)
- CA2  la liste des gestes « sol et entretien » est définie en UN SEUL endroit,
       et c'est celui-là que la carte ET le filtre du Journal reçoivent
- CA3  elle est servie AVEC l'onglet Parcelles, en une seule lecture pour tout
       le plan : changer de parcelle ne déclenche aucune requête de plus
- CA5  un semis, une plantation et une récolte n'y figurent PAS (S4)
- CA7  « Ajouter » prépare un geste — le geste de sol est donc ouvert à la PWA
- CA10 aucune intervention, une seule, plus de huit : les trois cas

Le rendu (S1 à S8, CA4, CA6, CA8, CA9, CA11) se vérifie dans
`frontend/src/lib/planParcelles.sol.test.js` et sur `/plan-parcelles`.

⚖️ **Livrable annexe** (`GESTES_SOL_SANS_EQUIVALENT`) : les catégories de la
maquette qu'aucun `type_action` ne porte aujourd'hui. Cette US ne les crée pas,
elle les NOMME — chacune relève d'une US à part.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.services import evenements as svc_evenements
from app.services import file_gestes as svc_file_gestes
from app.services.context import TenantContext
from database.models import Evenement, Parcelle, Potager, User
from utils.actions import ACTION_MAP
from utils.parcelles import normalize_parcelle_name

RACINE = Path(__file__).resolve().parent.parent
API = RACINE / "app" / "api" / "main.py"
LIB = RACINE / "frontend" / "src" / "lib" / "planParcelles.js"
VUE = RACINE / "frontend" / "src" / "views" / "Plan.jsx"
JOURNAL = RACINE / "frontend" / "src" / "views" / "Journal.jsx"


def _parcelle(test_db, id_: int, nom: str, potager_id: int) -> None:
    test_db.add(Parcelle(
        id=id_, nom=nom, nom_normalise=normalize_parcelle_name(nom),
        potager_id=potager_id, actif=True,
    ))


@pytest.fixture
def ctx(test_db) -> TenantContext:
    test_db.add(User(id=1, nom="Jardinier", email="j@test", mot_de_passe_hash="x"))
    test_db.add(Potager(id=1, nom="Potager", proprietaire_id=1))
    _parcelle(test_db, 1, "planche_centrale", 1)
    _parcelle(test_db, 2, "tubercule", 1)
    test_db.commit()
    return TenantContext(user_id=1, potager_id=1, role="owner")


def _evenement(test_db, parcelle_id, type_action: str, jour: str, **champs) -> None:
    test_db.add(Evenement(
        potager_id=1, parcelle_id=parcelle_id, type_action=type_action,
        date=datetime.fromisoformat(jour), **champs,
    ))
    test_db.commit()


# ── CA2 : une seule définition, et elle est dans le domaine ──────────────────

def test_ca2_les_gestes_de_sol_existent_tous_dans_le_referentiel_d_actions():
    """[CA2] Aucun nouveau type de geste n'est inventé : chacun est déjà une
    action canonique d'US-168. Une liste qui contiendrait un geste imaginaire
    filtrerait sur du vide sans que rien ne le dise."""
    for geste in svc_evenements.GESTES_SOL:
        assert geste in ACTION_MAP, f"{geste} n'est pas une action du référentiel"


def test_ca2_les_gestes_de_sol_ne_portent_jamais_sur_une_culture():
    """[S4] Un semis, une plantation, une récolte, un arrosage, une taille
    portent sur une CULTURE : ils n'ont rien à faire dans le journal du sol."""
    interdits = {
        "semis", "plantation", "recolte", "arrosage", "taille", "tuteurage",
        "mise_en_godet", "perte", "perte_godet", "vendu", "observation",
        "traitement", "protection", "eclaircie",
    }
    assert not (set(svc_evenements.GESTES_SOL) & interdits)


def test_ca2_la_liste_est_servie_par_le_plan_et_n_est_pas_recopiee_cote_ecran():
    """[CA2] La carte et le filtre du Journal la reçoivent tous les deux de
    `GET /plan`. Une seconde définition, côté frontend, dériverait."""
    api = API.read_text(encoding="utf-8")
    assert '"gestes_sol": list(svc_evenements.GESTES_SOL)' in api

    for fichier in (LIB, VUE):
        source = fichier.read_text(encoding="utf-8")
        # Aucun des gestes n'est écrit en dur dans la fiche parcelle : ils n'y
        # existent que sous la forme du tableau reçu (`gestes_sol`).
        assert "'desherbage'" not in source, fichier.name
        assert "'binage'" not in source, fichier.name

    # Le Journal, lui, connaît « Entretien » depuis US-063 — une catégorie de
    # FILTRE, plus large et indépendante. Ce qu'il ne fait pas, c'est recomposer
    # la liste de sol : il la reçoit par l'intention, telle quelle.
    journal = JOURNAL.read_text(encoding="utf-8")
    assert "if (gestesFilter) params.action = gestesFilter" in journal


def test_livrable_annexe_les_gestes_de_la_maquette_sans_equivalent_sont_nommes():
    """Livrable annexe : la carte affiche ce que l'application sait
    enregistrer, ni plus ni moins. Ce qu'elle ne sait pas est DIT, pour
    arbitrage produit, jamais inventé au passage."""
    manquants = svc_evenements.GESTES_SOL_SANS_EQUIVALENT
    assert manquants, "le livrable annexe ne peut pas être vide"
    for geste in manquants:
        assert geste.replace(" ", "_") not in ACTION_MAP


# ── CA1, CA5 : ce que le service retient, et ce qu'il écarte ────────────────

def test_ca5_gherkin_paillage_et_compost_sont_listes_le_semis_ne_l_est_pas(test_db, ctx):
    """[Gherkin, CA5, S2] Du plus récent au plus ancien — et le semis de tomate
    n'y figure pas."""
    _evenement(test_db, 1, "paillage", "2026-09-12", rang=1, commentaire="de tonte")
    _evenement(test_db, 1, "amendement", "2026-08-30", quantite=2, unite="brouettes")
    _evenement(test_db, 1, "semis", "2026-09-01", culture="tomate")
    _evenement(test_db, 1, "plantation", "2026-08-01", culture="tomate")
    _evenement(test_db, 1, "recolte", "2026-09-20", culture="tomate")

    sol = svc_evenements.interventions_sol(test_db, ctx)
    lignes = sol[1]["interventions"]
    assert [l["type_action"] for l in lignes] == ["paillage", "amendement"]
    assert [l["date"] for l in lignes] == ["2026-09-12", "2026-08-30"]
    # [S3] Les champs bruts partent tels quels : c'est l'écran qui compose la
    # phrase, pas le service.
    assert lignes[0]["rang"] == 1
    assert lignes[0]["commentaire"] == "de tonte"
    assert lignes[1]["quantite"] == 2 and lignes[1]["unite"] == "brouettes"


def test_ca10_aucune_intervention_une_seule_plus_de_huit(test_db, ctx):
    """[CA10] Les trois états de la carte, à la source."""
    # Aucune : la parcelle est simplement absente — c'est l'écran qui dit S6.
    assert svc_evenements.interventions_sol(test_db, ctx) == {}

    _evenement(test_db, 2, "binage", "2026-06-18")
    sol = svc_evenements.interventions_sol(test_db, ctx)
    assert sol[2]["total"] == 1 and len(sol[2]["interventions"]) == 1
    assert 1 not in sol

    for jour in range(1, 12):
        _evenement(test_db, 1, "paillage", f"2026-03-{jour:02d}")
    sol = svc_evenements.interventions_sol(test_db, ctx)
    # [S5] Huit rendues, le total réel dit qu'il en reste à voir.
    assert len(sol[1]["interventions"]) == svc_evenements.NB_INTERVENTIONS_SOL
    assert sol[1]["total"] == 11


def test_les_interventions_d_un_autre_potager_ne_franchissent_pas_la_cloison(test_db, ctx):
    """Un journal de sol reste celui de SON potager (US-041)."""
    test_db.add(Potager(id=2, nom="Voisin", proprietaire_id=1))
    _parcelle(test_db, 3, "chez-le-voisin", 2)
    test_db.commit()
    test_db.add(Evenement(
        potager_id=2, parcelle_id=3, type_action="paillage",
        date=datetime.fromisoformat("2026-09-12"),
    ))
    test_db.commit()
    assert svc_evenements.interventions_sol(test_db, ctx) == {}


def test_une_intervention_non_localisee_n_est_rattachee_a_aucune_parcelle(test_db, ctx):
    """Un paillage dont la parcelle n'a jamais été dite n'est prêté à aucune
    planche : il reste dans le Journal, pas dans une fiche."""
    _evenement(test_db, None, "paillage", "2026-09-12")
    assert svc_evenements.interventions_sol(test_db, ctx) == {}


def test_us030_la_date_de_reference_borne_le_journal_du_sol(test_db, ctx):
    """[US-030] Consulter le plan à une date passée ne montre pas un paillage
    qui n'avait pas encore eu lieu."""
    _evenement(test_db, 1, "paillage", "2026-09-12")
    _evenement(test_db, 1, "binage", "2026-06-18")
    sol = svc_evenements.interventions_sol(test_db, ctx, jusqua="2026-07-01")
    assert [l["type_action"] for l in sol[1]["interventions"]] == ["binage"]


# ── CA1, CA3 : servi avec l'onglet Parcelles, en une seule lecture ──────────

def test_ca1_le_filtre_vit_dans_le_service_pas_dans_le_handler():
    """[CA1, test US-041] Le filtre est un `db.query` du service, jamais un
    `db.query` posé dans `app/api/main.py`."""
    api = API.read_text(encoding="utf-8")
    assert "svc_evenements.interventions_sol(db, use_ctx" in api
    assert "GESTES_SOL" in (RACINE / "app" / "services" / "evenements.py").read_text(encoding="utf-8")


def test_ca3_une_seule_lecture_pour_tout_le_plan(test_db, ctx):
    """[CA3, RT6] Le service rend TOUTES les parcelles d'un coup : changer de
    parcelle dans l'onglet ne doit déclencher aucune requête de plus."""
    _evenement(test_db, 1, "paillage", "2026-09-12")
    _evenement(test_db, 2, "amendement", "2026-09-10")
    sol = svc_evenements.interventions_sol(test_db, ctx)
    assert set(sol) == {1, 2}


# ── CA7 : « Ajouter » prépare un geste ──────────────────────────────────────

def test_ca7_les_gestes_de_sol_sont_ouverts_a_la_pwa():
    """[CA7] Le bouton « Ajouter » prépare un geste avec la parcelle en
    contexte. Sans cette ouverture, il serait refusé par le domaine."""
    for geste in svc_evenements.GESTES_SOL:
        assert geste in svc_file_gestes.GESTES_OUVERTS_PWA


def test_ca7_la_phrase_de_repli_est_celle_que_la_carte_propose():
    """[S7] « Ou dites au compagnon : paillage parcelle planche_centrale » — la
    phrase affichée et celle que la file construit sont la MÊME."""
    phrase = svc_file_gestes.phrase_a_dicter({
        "action": "paillage", "parcelle": "planche_centrale",
    })
    assert phrase == "paillage parcelle planche_centrale"
