"""
tests/test_us197_nb_rangs_parcelle.py — Nombre de rangs d'une parcelle [US-197]

Critères couverts :
- CA1  colonne nullable 1–99, « non renseigné » distinct de « zéro rang », aucun backfill
- CA2  /parcelle modifier rangs=N, rangs=aucun, valeurs refusées sans perte de l'ancienne
- CA3  déclaration en une phrase par la grammaire déterministe, sans appel modèle
- CA4  un geste « sur 3 rangs » n'est pas une déclaration de parcelle
- CA5  /parcelle lister dit le nombre de rangs, ou « rangs non renseignés »
- CA6  GET /plan expose nb_rangs, ordre et est_pepiniere sans rien retirer
- CA7  le nombre de rangs n'entre dans aucun calcul (stock, occupation, confiance)
- CA8  la PWA n'offre aucun champ de saisie
- CA9  le catalogue des commandes connaît la clé ; controler_parite() reste vert
- CA10 fiche de corpus, guide utilisateur et fiche de domaine mis à jour
- CA11 (transverse) : chaque comportement ci-dessus a son test
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import interpreteur_commandes as interp
from app.services import menu_commandes as svc_menu
from database.models import Parcelle, Potager, User
from utils.parcelles import NB_RANGS_MAX, NB_RANGS_MIN, update_parcelle

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="planche nord", nom_normalise="planchenord", potager_id=1),
        Parcelle(id=2, nom="planche sud", nom_normalise="planchesud", potager_id=1, nb_rangs=7),
    ])
    test_db.commit()
    return test_db


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — La colonne : nullable, bornée, jamais backfillée
# ═════════════════════════════════════════════════════════════════════════════

def test_us197_ca1_parcelle_neuve_sans_nombre_de_rangs(db) -> None:
    """CA1 — Une parcelle jamais renseignée porte None, pas 0."""
    parcelle = db.query(Parcelle).filter_by(nom_normalise="planchenord").one()
    assert parcelle.nb_rangs is None


def test_us197_ca1_non_renseigne_n_est_pas_zero(db) -> None:
    """CA1 — « non renseigné » et « zéro rang » ne se confondent pas : zéro est refusé."""
    with pytest.raises(ValueError):
        update_parcelle(db, "planche nord", potager_id=1, rangs="0")
    assert db.query(Parcelle).filter_by(id=1).one().nb_rangs is None


def test_us197_ca1_migration_et_rollback_fournis() -> None:
    """CA1 — migration_v52 ajoute la colonne bornée, rollback_v52 la retire."""
    migration = (RACINE / "migrations" / "migration_v52.sql").read_text(encoding="utf-8")
    rollback = (RACINE / "migrations" / "rollback_v52.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS nb_rangs SMALLINT" in migration
    assert "ck_parcelles_nb_rangs" in migration
    assert "BETWEEN 1 AND 99" in migration
    assert "DROP COLUMN IF EXISTS nb_rangs" in rollback
    # [CA1] Aucun backfill : rien ne pose de valeur sur l'existant.
    assert "UPDATE parcelles" not in migration


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — /parcelle modifier <nom> rangs=…
# ═════════════════════════════════════════════════════════════════════════════

def test_us197_ca2_declarer_un_nombre_de_rangs(db) -> None:
    """CA2 — rangs=5 écrit 5 et le dit dans le récapitulatif."""
    parcelle, modifs = update_parcelle(db, "planche nord", potager_id=1, rangs="5")
    assert parcelle.nb_rangs == 5
    assert any("5" in m and "Rangs" in m for m in modifs)


def test_us197_ca2_revenir_a_non_renseigne(db) -> None:
    """CA2 — rangs=aucun remet la parcelle à « non renseigné »."""
    parcelle, modifs = update_parcelle(db, "planche sud", potager_id=1, rangs="aucun")
    assert parcelle.nb_rangs is None
    assert any("non renseigné" in m for m in modifs)


@pytest.mark.parametrize("valeur", ["0", "100", "-3", "cinq", "4,5", "4.5"])
def test_us197_ca2_valeur_refusee_conserve_la_precedente(db, valeur: str) -> None:
    """CA2 — Hors bornes ou non entière : refus, et la valeur précédente reste."""
    with pytest.raises(ValueError) as erreur:
        update_parcelle(db, "planche sud", potager_id=1, rangs=valeur)
    db.rollback()
    assert db.query(Parcelle).filter_by(id=2).one().nb_rangs == 7
    message = str(erreur.value)
    assert str(NB_RANGS_MIN) in message and str(NB_RANGS_MAX) in message
    assert "rangs=aucun" in message


def test_us197_ca2_bornes_acceptees(db) -> None:
    """CA2 — Les deux bornes du domaine passent."""
    for valeur in (NB_RANGS_MIN, NB_RANGS_MAX):
        parcelle, _ = update_parcelle(db, "planche nord", potager_id=1, rangs=str(valeur))
        assert parcelle.nb_rangs == valeur


def test_us197_ca2_cle_inconnue_toujours_refusee(db) -> None:
    """CA2 — Ajouter « rangs » n'ouvre pas la porte aux clés inconnues."""
    with pytest.raises(ValueError, match="inconnu"):
        update_parcelle(db, "planche nord", potager_id=1, rang="5")


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La même déclaration, en une phrase
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "phrase, attendu",
    [
        ("la planche nord a 5 rangs", "rangs=5"),
        ("la planche centrale fait 4 rangs", "rangs=4"),
        ("je veux que la planche nord ait 12 rangs", "rangs=12"),
        ("la parcelle nord compte 3 rangs", "rangs=3"),
        ("la planche nord a 1 rang", "rangs=1"),
    ],
)
def test_us197_ca3_declaration_par_phrase(phrase: str, attendu: str) -> None:
    """CA3 — La grammaire déterministe traduit la phrase en /parcelle modifier."""
    resultat = interp.interpreter(phrase, autoriser_modele=False)
    assert isinstance(resultat, interp.CommandeInterpretee)
    assert (resultat.commande, resultat.sous_commande) == ("parcelle", "modifier")
    assert resultat.valeurs["modification"] == attendu


def test_us197_ca3_aucun_jeton_consomme() -> None:
    """CA3 — Reconnue par une RÈGLE : aucun appel modèle, donc aucun jeton."""
    resultat = interp.interpreter("la planche nord a 5 rangs", autoriser_modele=False)
    assert resultat.origine == interp.ORIGINE_REGLE
    assert resultat.regle == "parcelle_rangs"


def test_us197_ca3_confirmation_avant_ecriture() -> None:
    """CA3 — /parcelle modifier écrit : le catalogue exige la confirmation."""
    forme = {f.cle: f for f in svc_menu.FORMES_DICTABLES}[("parcelle", "modifier")]
    assert forme.confirmation is True


def test_us197_ca3_recapitulatif_nomme_les_rangs() -> None:
    """CA3 — Le récapitulatif dit « nombre de rangs », pas « rangs=5 »."""
    resultat = interp.interpreter("la planche nord a 5 rangs", autoriser_modele=False)
    recap = interp.recapitulatif(resultat)
    assert "nombre de rangs" in recap
    assert "cinq" in recap  # [US-172 / CA11] tout nombre est relu en toutes lettres
    assert "rangs=5" in recap  # la commande équivalente, pour l'apprendre


def test_us197_ca3_question_fermee_n_ecrit_pas() -> None:
    """CA3 — « est-ce que la planche nord a 5 rangs ? » interroge, elle ne déclare pas."""
    assert interp.interpreter(
        "est-ce que la planche nord a 5 rangs ?", autoriser_modele=False
    ) is None


def test_us197_ca3_valeur_hors_bornes_reconnue_puis_refusee(db) -> None:
    """CA3 — « 200 rangs » est reconnu, puis refusé avec la forme attendue.

    Renvoyer la phrase au modèle aurait coûté un jeton pour aboutir au même
    refus, sans jamais dire au jardinier ce qu'on attendait de lui.
    """
    resultat = interp.interpreter("la planche nord a 200 rangs", autoriser_modele=False)
    assert resultat.valeurs["modification"] == "rangs=200"
    with pytest.raises(ValueError):
        update_parcelle(db, "planche nord", potager_id=1, rangs="200")


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Le rang d'un geste n'est pas le rang d'une planche
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "phrase",
    [
        "planté 4 salades sur 3 rangs dans la planche nord",
        "j'ai semé des haricots rang 3 samedi",
        "semé carottes Nantaise rang 4",
    ],
)
def test_us197_ca4_un_geste_n_est_pas_une_declaration(phrase: str) -> None:
    """CA4 — Un geste qui cite des rangs n'est jamais une commande de parcelle."""
    resultat = interp.interpreter(phrase, autoriser_modele=False)
    assert resultat is None or (resultat.commande, resultat.sous_commande) != (
        "parcelle", "modifier"
    )


def test_us197_ca4_le_corpus_porte_les_deux_formes() -> None:
    """CA4 — Déclaration et geste se lisent CÔTE À CÔTE dans le corpus d'US-172."""
    import csv

    with (RACINE / "tests" / "corpus" / "us172_commandes.csv").open(encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))
    declarations = [l for l in lignes if "rangs" in l["phrase"] and l["attendu"] == "parcelle modifier"]
    gestes = [l for l in lignes if "rangs" in l["phrase"] and l["registre"] == "hors_perimetre"]
    assert declarations, "le corpus doit porter la déclaration du nombre de rangs"
    assert gestes, "le corpus doit porter le geste voisin qui ne doit pas la déclencher"


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — /parcelle lister
# ═════════════════════════════════════════════════════════════════════════════

def _update_ctx(args: list[str]):
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = args
    ctx.user_data = {}
    return update, ctx


@pytest.mark.asyncio
async def test_us197_ca5_lister_dit_le_nombre_de_rangs(db) -> None:
    """CA5 — /parcelle lister affiche les rangs déclarés et signale les absents."""
    update, ctx = _update_ctx(["lister"])
    parcelles = db.query(Parcelle).order_by(Parcelle.id).all()
    with (
        patch("app.bot.SessionLocal", return_value=MagicMock()),
        patch("app.bot.commandes_parcelle.get_all_parcelles", return_value=parcelles),
        patch("app.bot.commandes_parcelle.current_context", return_value=MagicMock(potager_id=1)),
    ):
        from app.bot import cmd_parcelle
        await cmd_parcelle(update, ctx)

    texte = update.message.reply_text.call_args[0][0]
    assert "rangs non renseignés" in texte   # planche nord
    assert "7 rangs" in texte                # planche sud


@pytest.mark.asyncio
async def test_us197_ca5_usage_rappelle_la_cle(db) -> None:
    """CA5 — L'aide de /parcelle montre la forme rangs=5 et rangs=aucun."""
    update, ctx = _update_ctx([])
    from app.bot import cmd_parcelle
    await cmd_parcelle(update, ctx)
    texte = update.message.reply_text.call_args[0][0]
    assert "rangs=5" in texte and "rangs=aucun" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — GET /plan
# ═════════════════════════════════════════════════════════════════════════════

def _parcelle_mock(nom: str, *, nb_rangs=None, ordre=0, pepiniere=False, superficie=None):
    p = MagicMock(spec=Parcelle)
    p.id = abs(hash(nom)) % 1000
    p.nom = nom
    p.exposition = None
    p.superficie_m2 = superficie
    p.abri = None
    p.paillage = None
    p.nb_rangs = nb_rangs
    p.ordre = ordre
    p.est_pepiniere = pepiniere
    p.actif = True
    return p


@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    parcelles = [
        _parcelle_mock("Centrale", nb_rangs=18, ordre=1, superficie=4.0),
        _parcelle_mock("Pepiniere", nb_rangs=3, ordre=2, pepiniere=True),
        _parcelle_mock("Jamais mesuree", ordre=3),
    ]
    occupation = {
        "Centrale": [
            {"culture": "tomate", "variete": "Marmande", "nb_plants": 6.0,
             "type_organe": "reproducteur", "unite": "plants"},
        ],
    }
    app.dependency_overrides[get_current_user_ctx] = default_context
    with (
        patch("app.api.main.SessionLocal", return_value=MagicMock()),
        patch("utils.parcelles.get_all_parcelles", return_value=parcelles),
        patch("utils.parcelles.calcul_occupation_parcelles", return_value=occupation),
    ):
        from fastapi.testclient import TestClient
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_current_user_ctx, None)


def test_us197_ca6_plan_expose_nb_rangs_ordre_et_pepiniere(client_plan) -> None:
    """CA6 — Chaque parcelle porte nb_rangs, ordre et est_pepiniere."""
    parcelles = client_plan.get("/plan").json()["parcelles"]
    par_nom = {p["nom"]: p for p in parcelles}
    assert par_nom["Centrale"]["nb_rangs"] == 18
    assert par_nom["Centrale"]["ordre"] == 1
    assert par_nom["Centrale"]["est_pepiniere"] is False
    assert par_nom["Pepiniere"]["est_pepiniere"] is True
    # [CA1 / Point de vigilance] Une pépinière peut porter des rangs.
    assert par_nom["Pepiniere"]["nb_rangs"] == 3
    # [CA1] Non renseigné se sert tel quel : jamais 0.
    assert par_nom["Jamais mesuree"]["nb_rangs"] is None


def test_us197_ca6_aucun_champ_existant_retire(client_plan) -> None:
    """CA6 — Les champs servis jusqu'ici le sont toujours."""
    parcelle = client_plan.get("/plan").json()["parcelles"][0]
    for champ in ("id", "nom", "exposition", "superficie_m2", "abri", "paillage",
                  "cultures", "occupation_pct", "has_observations", "nb_observations"):
        assert champ in parcelle


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — Aucun calcul ne lit le nombre de rangs
# ═════════════════════════════════════════════════════════════════════════════

def test_us197_ca7_occupation_pct_ignore_les_rangs(client_plan) -> None:
    """CA7 — L'occupation reste une affaire de surface, pas de rangs."""
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    # Centrale : 18 rangs déclarés, mais 4 m² et aucune surface au pied connue.
    assert par_nom["Centrale"]["occupation_pct"] is None
    # Une parcelle sans superficie n'acquiert pas d'occupation par ses rangs.
    assert par_nom["Pepiniere"]["occupation_pct"] is None


def test_us197_ca7_aucun_moteur_de_calcul_ne_lit_nb_rangs() -> None:
    """CA7 — `nb_rangs` ne se lit que là où il se déclare, s'affiche ou se sert.

    Un test de comportement ne prouverait l'absence d'effet que sur les cas
    qu'il énumère ; ce contrôle-ci la prouve à la source. Ajouter `nb_rangs`
    dans un moteur de calcul fait échouer ce test, et c'est le point : la Vue
    plan (US-200) le DESSINE, elle ne le fait entrer dans aucun total.
    """
    autorises = {
        Path("database/models.py"),
        Path("utils/parcelles.py"),
        Path("app/services/interpreteur_commandes.py"),
        Path("app/bot/commandes_parcelle.py"),
        Path("app/api/main.py"),
    }
    fautifs = []
    for chemin in RACINE.glob("**/*.py"):
        relatif = chemin.relative_to(RACINE)
        if relatif.parts[0] in {"tests", ".venv", "migrations", "tools"}:
            continue
        if relatif in autorises:
            continue
        if "nb_rangs" in chemin.read_text(encoding="utf-8"):
            fautifs.append(str(relatif))
    assert not fautifs, f"nb_rangs lu hors des points prévus : {fautifs}"


def test_us197_ca7_stock_et_confiance_intacts() -> None:
    """CA7 — Ni le stock ni la confiance ne connaissent le nombre de rangs."""
    for module in ("utils/stock.py", "app/services/confiance_semis.py",
                   "app/services/reponses_chiffrees.py"):
        assert "nb_rangs" not in (RACINE / module).read_text(encoding="utf-8")


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — La PWA n'offre aucun champ de saisie
# ═════════════════════════════════════════════════════════════════════════════

def test_us197_ca8_aucune_saisie_dans_la_pwa() -> None:
    """CA8 — Règle RT1 : la déclaration reste au backoffice (le bot)."""
    sources = list((RACINE / "frontend" / "src").glob("**/*.jsx"))
    sources += list((RACINE / "frontend" / "src").glob("**/*.js"))
    ecrivains = [
        str(f.relative_to(RACINE)) for f in sources
        if "nb_rangs" in f.read_text(encoding="utf-8")
    ]
    assert not ecrivains, f"la PWA ne doit offrir aucun champ de rangs : {ecrivains}"


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Le catalogue des commandes
# ═════════════════════════════════════════════════════════════════════════════

def test_us197_ca9_le_catalogue_connait_la_cle() -> None:
    """CA9 — Toute clé acceptée à l'écriture a son libellé au récapitulatif."""
    from utils.parcelles import _CHAMPS_MODIFIER

    assert "rangs" in _CHAMPS_MODIFIER
    for cle in _CHAMPS_MODIFIER:
        assert cle in interp._LIBELLES_MODIFICATION, f"clé sans libellé : {cle}"
        assert cle in interp._UNITES_MODIFICATION, f"clé sans unité déclarée : {cle}"


def test_us197_ca9_la_forme_dictable_cite_les_rangs() -> None:
    """CA9 — La relance vocale d'un argument manquant propose la nouvelle clé."""
    forme = {f.cle: f for f in svc_menu.FORMES_DICTABLES}[("parcelle", "modifier")]
    question = {a.nom: a.question for a in forme.arguments}["modification"]
    assert "rangs" in question


def test_us197_ca9_parite_des_commandes_verte() -> None:
    """CA9 — Aucune commande ajoutée ni retirée : la parité tient."""
    from app.bot import application as bot_application

    noms: set[str] = set()

    def _capturer(app, nom, handler):
        noms.add(nom)

    with (
        patch.object(bot_application, "_enregistrer_commande", _capturer),
        patch.object(bot_application, "Application") as faux,
    ):
        faux.builder.return_value.token.return_value.read_timeout.return_value \
            .write_timeout.return_value.connect_timeout.return_value.pool_timeout.return_value \
            .post_init.return_value.build.return_value = MagicMock()
        bot_application._construire_application()

    assert svc_menu.controler_parite(noms) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — La documentation livrée dans la même livraison
# ═════════════════════════════════════════════════════════════════════════════

def test_us197_ca10_fiche_de_corpus_a_jour() -> None:
    """CA10 — La fiche parcelles-et-plan porte la nouvelle section (US-099 / CA9)."""
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "parcelles-et-plan.md").read_text(
        encoding="utf-8"
    )
    assert "## Dire combien de rangs compte une parcelle" in fiche
    assert "rangs non renseignés" in fiche
    # Les deux sens du mot « rang » sont distingués explicitement.
    assert "multiplicateur" in fiche


def test_us197_ca10_guide_utilisateur_a_jour() -> None:
    """CA10 — Le § 21.4 du guide cite la clé et sa remise à zéro."""
    guide = (RACINE / "data" / "connaissance" / "guide user" / "guide assistant.md").read_text(
        encoding="utf-8"
    )
    assert "rangs=aucun" in guide


def test_us197_ca10_fiche_de_domaine_migrations_a_jour() -> None:
    """CA10 — docs/domaines/migrations.md décrit la migration v52."""
    fiche = (RACINE / "docs" / "domaines" / "migrations.md").read_text(encoding="utf-8")
    assert "v52 [US-197]" in fiche
    assert "nb_rangs" in fiche
