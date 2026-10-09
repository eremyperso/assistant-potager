"""
tests/test_us208_pepiniere_chaude_froide.py — Pépinière chaude ou froide [US-208]

Critères couverts :
- CA1  colonne nullable chaude/froide, contrainte « pas de type hors pépinière », aucun backfill
- CA2  /parcelle modifier pepiniere=chaude / froide / oui / non (qui retire le type)
- CA3  déclaration en une phrase par la grammaire déterministe, confirmée avant écriture
- CA4  /parcelle lister dit « pépinière chaude / froide / (type non renseigné) »
- CA5  GET /plan et GET /pepiniere/lots exposent le type, sans retirer de champ
- CA6  la PWA l'affiche (Vue plan, emplacement d'un lot) sans offrir de le corriger
- CA7  le type ne change aucun calcul
- CA8  catalogue des commandes et parité
- CA9  documentation livrée dans la même livraison
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from app.services import interpreteur_commandes as interp
from app.services import menu_commandes as svc_menu
from database.models import Evenement, Parcelle, Potager, User
from utils.parcelles import (
    TYPES_PEPINIERE,
    _CHAMPS_MODIFIER,
    libelle_pepiniere,
    update_parcelle,
    valider_champs,
)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
        Parcelle(id=2, nom="châssis", nom_normalise="chassis", potager_id=1),
        Parcelle(id=3, nom="véranda", nom_normalise="veranda", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude"),
    ])
    test_db.commit()
    return test_db


def _parcelle(db, id_: int) -> Parcelle:
    return db.query(Parcelle).filter_by(id=id_).one()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — La colonne
# ═════════════════════════════════════════════════════════════════════════════

def test_us208_ca1_pepiniere_sans_type_par_defaut(db) -> None:
    """CA1 — Aucun backfill : une pépinière existante n'est supposée ni chaude ni froide."""
    assert _parcelle(db, 1).type_pepiniere is None
    assert _parcelle(db, 2).type_pepiniere is None


def test_us208_ca1_pas_de_type_hors_pepiniere(db) -> None:
    """CA1 — La contrainte en base refuse un type sur une parcelle qui n'est pas pépinière."""
    chassis = _parcelle(db, 2)
    chassis.type_pepiniere = "froide"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_us208_ca1_vocabulaire_ferme_en_base(db) -> None:
    """CA1 — Seules « chaude » et « froide » passent la contrainte."""
    serre = _parcelle(db, 1)
    serre.type_pepiniere = "tiede"
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_us208_ca1_migration_et_rollback() -> None:
    """CA1 — Migration v54 nullable avec contrainte, rollback fourni."""
    migration = (RACINE / "migrations" / "migration_v54.sql").read_text(encoding="utf-8")
    assert "type_pepiniere VARCHAR(8)" in migration
    assert "ck_parcelles_type_pepiniere" in migration
    assert "UPDATE" not in migration.upper().replace("-- ", "")  # aucun backfill
    assert (RACINE / "migrations" / "rollback_v54.sql").exists()
    assert TYPES_PEPINIERE == ("chaude", "froide")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — /parcelle modifier pepiniere=…
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("valeur, attendu", [
    ("chaude", "chaude"), ("froide", "froide"), ("Chauffée", "chaude"),
])
def test_us208_ca2_valeurs_typees(db, valeur: str, attendu: str) -> None:
    """CA2 — pepiniere=chaude / froide rend la parcelle pépinière typée."""
    parcelle, modifs = update_parcelle(db, "châssis", potager_id=1, pepiniere=valeur)
    assert parcelle.est_pepiniere is True
    assert parcelle.type_pepiniere == attendu
    assert f"Pépinière : pépinière {attendu}" in modifs


def test_us208_ca2_oui_pepiniere_sans_type(db) -> None:
    """CA2 — pepiniere=oui : pépinière sans type (comportement d'avant)."""
    parcelle, modifs = update_parcelle(db, "véranda", potager_id=1, pepiniere="oui")
    assert parcelle.est_pepiniere is True
    assert parcelle.type_pepiniere is None
    assert "Pépinière : pépinière (type non renseigné)" in modifs


def test_us208_ca2_non_retire_le_type(db) -> None:
    """CA2 / Gherkin — pepiniere=non retire le statut ET le type."""
    update_parcelle(db, "châssis", potager_id=1, pepiniere="froide")
    parcelle, modifs = update_parcelle(db, "châssis", potager_id=1, pepiniere="non")
    assert parcelle.est_pepiniere is False
    assert parcelle.type_pepiniere is None
    assert "Pépinière : non" in modifs


def test_us208_ca2_true_de_la_fiche_web_garde_le_type(db) -> None:
    """La fiche web (US-230) envoie « true » et ne sait pas dire le type : elle ne l'efface pas."""
    parcelle, _ = update_parcelle(db, "véranda", potager_id=1, pepiniere="true")
    assert parcelle.type_pepiniere == "chaude"
    parcelle, _ = update_parcelle(db, "véranda", potager_id=1, pepiniere="false")
    assert parcelle.type_pepiniere is None


@pytest.mark.parametrize("valeur", ["tiede", "serre", "", "2"])
def test_us208_ca2_valeur_refusee_sans_perte(db, valeur: str) -> None:
    """CA2 — Une valeur hors vocabulaire est refusée et ne touche à rien."""
    with pytest.raises(ValueError, match="chaude, froide, oui ou non"):
        update_parcelle(db, "véranda", potager_id=1, pepiniere=valeur)
    assert _parcelle(db, 3).type_pepiniere == "chaude"
    with pytest.raises(ValueError):
        valider_champs(pepiniere=valeur)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La phrase dictée
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("phrase, attendu", [
    ("la serre est une pépinière chaude", "pepiniere=chaude"),
    ("le châssis est une pépinière froide", "pepiniere=froide"),
    ("la serre est une pépinière chauffée", "pepiniere=chaude"),
    ("ma mini-serre est chauffée", "pepiniere=chaude"),
    ("le châssis est non chauffé", None),
    ("la serre est une pépinière", "pepiniere=oui"),
])
def test_us208_ca3_declaration_par_phrase(phrase: str, attendu) -> None:
    """CA3 — La grammaire déterministe traduit la phrase, sans appel modèle."""
    resultat = interp.interpreter(phrase, autoriser_modele=False)
    if attendu is None:
        # « non chauffé » (masculin) n'est pas un motif : rien n'est inventé.
        assert not (isinstance(resultat, interp.CommandeInterpretee)
                    and "pepiniere" in resultat.valeurs.get("modification", ""))
        return
    assert isinstance(resultat, interp.CommandeInterpretee)
    assert resultat.origine == interp.ORIGINE_REGLE
    assert (resultat.commande, resultat.sous_commande) == ("parcelle", "modifier")
    assert resultat.valeurs["modification"] == attendu


def test_us208_ca3_recapitule_avant_confirmation() -> None:
    """CA3 / Gherkin — Le récapitulatif dit « pépinière chaude » ; la forme exige la confirmation."""
    resultat = interp.interpreter("la serre est une pépinière chaude", autoriser_modele=False)
    recap = interp.recapitulatif(resultat)
    assert "serre" in recap
    assert "pépinière chaude" in recap
    forme = {f.cle: f for f in svc_menu.FORMES_DICTABLES}[("parcelle", "modifier")]
    assert forme.confirmation is True


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — /parcelle lister
# ═════════════════════════════════════════════════════════════════════════════

def test_us208_ca4_libelles() -> None:
    assert libelle_pepiniere(True, "chaude") == "pépinière chaude"
    assert libelle_pepiniere(True, "froide") == "pépinière froide"
    assert libelle_pepiniere(True, None) == "pépinière (type non renseigné)"
    assert libelle_pepiniere(False, None) is None


@pytest.mark.asyncio
async def test_us208_ca4_lister_dit_le_type(db) -> None:
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    ctx = MagicMock(args=["lister"], user_data={})
    parcelles = db.query(Parcelle).order_by(Parcelle.id).all()
    with (
        patch("app.bot.SessionLocal", return_value=MagicMock()),
        patch("app.bot.commandes_parcelle.get_all_parcelles", return_value=parcelles),
        patch("app.bot.commandes_parcelle.current_context", return_value=MagicMock(potager_id=1)),
    ):
        from app.bot import cmd_parcelle
        await cmd_parcelle(update, ctx)
    texte = update.message.reply_text.call_args[0][0]
    assert "pépinière (type non renseigné)" in texte   # serre
    assert "pépinière chaude" in texte                 # véranda


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — Les deux lectures
# ═════════════════════════════════════════════════════════════════════════════

def _parcelle_mock(nom: str, *, pepiniere=False, type_p=None):
    p = MagicMock(spec=Parcelle)
    p.id = abs(hash(nom)) % 1000
    p.nom = nom
    for champ in ("exposition", "superficie_m2", "abri", "paillage", "nb_rangs", "longueur_m"):
        setattr(p, champ, None)
    p.ordre = 0
    p.est_pepiniere = pepiniere
    p.type_pepiniere = type_p
    p.actif = True
    return p


@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    parcelles = [
        _parcelle_mock("Serre", pepiniere=True, type_p="chaude"),
        _parcelle_mock("Veranda", pepiniere=True),
        _parcelle_mock("Nord"),
    ]
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=parcelles),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value={}),
    ):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


def test_us208_ca5_plan_expose_le_type(client_plan) -> None:
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    assert par_nom["Serre"]["type_pepiniere"] == "chaude"
    assert par_nom["Veranda"]["type_pepiniere"] is None
    assert par_nom["Nord"]["type_pepiniere"] is None
    for champ in ("est_pepiniere", "nb_rangs", "longueur_m", "abri", "disposition"):
        assert champ in par_nom["Serre"]


def test_us208_ca5_lots_exposent_le_type(db) -> None:
    """CA5 — Chaque lot porte le type de sa pépinière, None sans emplacement."""
    from utils.stock import calcul_lots_pepiniere

    db.add_all([
        Evenement(type_action="semis", culture="tomate", quantite=20, unite="graines",
                  date=date(2026, 2, 10), parcelle_id=3, potager_id=1),
        Evenement(type_action="semis", culture="poivron", quantite=10, unite="graines",
                  date=date(2026, 2, 11), parcelle_id=None, potager_id=1),
    ])
    db.commit()
    lots = {l["culture"]: l for l in calcul_lots_pepiniere(db, potager_id=1)}
    assert lots["tomate"]["type_pepiniere"] == "chaude"
    assert lots["tomate"]["parcelle"] == "véranda"
    assert lots["poivron"]["type_pepiniere"] is None
    assert "parcelle" in lots["poivron"]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — La PWA lit, n'écrit pas
# ═════════════════════════════════════════════════════════════════════════════

def test_us208_ca6_pwa_affiche_sans_corriger() -> None:
    src = RACINE / "frontend" / "src"
    assert "emplacementLot(lot)" in (src / "views" / "Pepiniere.jsx").read_text(encoding="utf-8")
    assert "typePepiniere" in (src / "components" / "ui" / "CartePlanParcelle.jsx").read_text(encoding="utf-8")
    ECRITURE = ("<input", "onChange", "JSON.stringify", "body:", "value=")
    fautifs = [
        f"{f.relative_to(RACINE)}:{n}"
        for f in list(src.glob("**/*.jsx")) + list(src.glob("**/*.js"))
        for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if "type_pepiniere" in ligne and any(m in ligne for m in ECRITURE)
    ]
    assert not fautifs, fautifs


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Aucun calcul ne lit le type
# ═════════════════════════════════════════════════════════════════════════════

def test_us208_ca7_aucun_moteur_ne_lit_le_type() -> None:
    """CA7 — Le type ne se lit que là où il se déclare, s'affiche ou se sert."""
    autorises = {
        Path("database/models.py"), Path("utils/parcelles.py"),
        Path("app/bot/commandes_parcelle.py"), Path("app/api/main.py"),
        # Le lot COPIE le type pour l'exposer (CA5) ; aucun calcul ne le lit.
        Path("utils/stock.py"),
    }
    fautifs = []
    for chemin in RACINE.glob("**/*.py"):
        relatif = chemin.relative_to(RACINE)
        if relatif.parts[0] in {"tests", ".venv", "migrations", "tools"} or relatif in autorises:
            continue
        if "type_pepiniere" in chemin.read_text(encoding="utf-8"):
            fautifs.append(str(relatif))
    assert not fautifs, f"type_pepiniere lu hors des points prévus : {fautifs}"
    stock = (RACINE / "utils" / "stock.py").read_text(encoding="utf-8")
    code = [l for l in stock.splitlines() if "type_pepiniere" in l and not l.strip().startswith("#")]
    # valeur par défaut + copie (US-208) ; + l'emplacement courant du lot (US-210 / CA5) :
    # sa docstring, la copie depuis la pépinière des godets, depuis celle du semis, et
    # la valeur vide. Toujours des copies : aucune condition ne porte sur le type.
    assert len(code) == 6, code


def test_us208_ca7_lots_identiques_quel_que_soit_le_type(db) -> None:
    """CA7 — Stock d'un lot : même résultat en pépinière chaude, froide ou sans type."""
    from utils.stock import calcul_lots_pepiniere

    db.add(Evenement(type_action="semis", culture="tomate", quantite=20, unite="graines",
                     date=date(2026, 2, 10), parcelle_id=1, potager_id=1))
    db.commit()
    resultats = []
    for valeur in ("oui", "chaude", "froide"):
        update_parcelle(db, "serre", potager_id=1, pepiniere=valeur)
        lot = calcul_lots_pepiniere(db, potager_id=1)[0]
        lot.pop("type_pepiniere")
        lot["emplacement"] = {**lot["emplacement"], "type_pepiniere": None}   # copie d'affichage (US-210)
        resultats.append(lot)
    assert resultats[0] == resultats[1] == resultats[2]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Catalogue
# ═════════════════════════════════════════════════════════════════════════════

def test_us208_ca8_catalogue() -> None:
    assert "pepiniere" in _CHAMPS_MODIFIER
    assert "pepiniere" in interp._LIBELLES_MODIFICATION
    assert "pepiniere" in interp._UNITES_MODIFICATION


def test_us208_ca8_parite_verte() -> None:
    from app.bot import application as bot_application

    noms: set[str] = set()
    with (
        patch.object(bot_application, "_enregistrer_commande",
                     lambda app, nom, handler: noms.add(nom)),
        patch.object(bot_application, "Application") as faux,
    ):
        faux.builder.return_value.token.return_value.read_timeout.return_value \
            .write_timeout.return_value.connect_timeout.return_value.pool_timeout.return_value \
            .post_init.return_value.build.return_value = MagicMock()
        bot_application._construire_application()
    assert svc_menu.controler_parite(noms) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Documentation
# ═════════════════════════════════════════════════════════════════════════════

def test_us208_ca9_documentation() -> None:
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "parcelles-et-plan.md").read_text(encoding="utf-8")
    assert "pépinière chaude" in fiche and "pépinière froide" in fiche
    assert "pepiniere=froide" in fiche
    migrations = (RACINE / "docs" / "domaines" / "migrations.md").read_text(encoding="utf-8")
    assert "v54" in migrations and "type_pepiniere" in migrations
    guide = (RACINE / "docs" / "MANUEL" / "guide assistant.md").read_text(encoding="utf-8")
    assert "pepiniere=chaude" in guide


# ═════════════════════════════════════════════════════════════════════════════
# Retours de recette du 07/10/2026 (hors CA d'US-208)
# ═════════════════════════════════════════════════════════════════════════════

def test_recette_plantation_sans_variete_jamais_prise_au_lot(db) -> None:
    """Une plantation « tomate » sans variété n'est pas imputée au lot « jaune »,
    ni à un lot sans variété : seuls culture ET variété identiques relient."""
    from utils.stock import calcul_lots_pepiniere

    db.add_all([
        Evenement(id=518, type_action="semis", culture="tomate", variete="jaune", quantite=20,
                  unite="graines", date=date(2026, 9, 21), parcelle_id=1, potager_id=1),
        Evenement(id=519, type_action="semis", culture="tomate", quantite=5,
                  unite="graines", date=date(2026, 9, 22), parcelle_id=1, potager_id=1),
        Evenement(type_action="mise_en_godet", culture="tomate", variete="jaune",
                  nb_plants_godets=5, nb_graines_semees=5, source_evenement_ids="518",
                  date=date(2026, 10, 7), potager_id=1),
        Evenement(type_action="mise_en_godet", culture="tomate",
                  nb_plants_godets=4, nb_graines_semees=5, source_evenement_ids="519",
                  date=date(2026, 10, 7), potager_id=1),
        Evenement(type_action="plantation", culture="tomate", quantite=15, unite="plants",
                  date=date(2026, 10, 8), parcelle_id=2, potager_id=1),
        Evenement(type_action="plantation", culture="tomate", variete="jaune", quantite=2,
                  unite="plants", date=date(2026, 10, 9), parcelle_id=2, potager_id=1),
    ])
    db.commit()
    lots = {l["variete"]: l for l in calcul_lots_pepiniere(db, potager_id=1)}
    assert lots["jaune"]["nb_plantes"] == 2     # seule la plantation « jaune »
    assert lots[None]["nb_plantes"] == 0        # sans variété ↔ sans variété : non relié


def test_recette_une_saisie_de_geste_n_est_jamais_soumise_au_modele_comme_commande() -> None:
    """« plantation 9 plants de tomate le 15/05 » partait en /confiance par le modèle."""
    with patch.object(interp, "_appeler_modele") as modele:
        for phrase in ("plantation 9 plants de tomate le 15/05",
                       "plantation 9 plants de tomate en date du 15/05"):
            assert interp.interpreter(phrase) is None
        modele.assert_not_called()
