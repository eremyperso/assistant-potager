"""
tests/test_us225_longueur_parcelle.py — Longueur d'une parcelle [US-225]

Critères couverts :
- CA1  colonne nullable 0,5–200, « non renseignée » distinct de « zéro mètre », aucun backfill
- CA2  /parcelle modifier longueur=12 / 12.5 / 12,5 / aucune, valeurs refusées sans perte
- CA3  déclaration en une phrase par la grammaire déterministe, sans appel modèle
- CA4  un semis « 3 mètres de carottes » n'est pas une déclaration de longueur
- CA5  /parcelle lister et l'usage disent la longueur ; le récapitulatif la nomme
- CA6  GET /plan expose longueur_m et la largeur DÉDUITE, marquée comme telle
- CA7  largeur déduite incohérente : signalée, jamais corrigée
- CA8  la longueur n'entre dans aucun calcul (stock, occupation, rendement, confiance)
- CA9  la PWA n'offre aucun champ de saisie
- CA10 le catalogue des commandes connaît la clé ; controler_parite() reste vert
- CA11 fiche de corpus, guide utilisateur et fiches de domaine mis à jour
- CA12 (transverse) : chaque comportement ci-dessus a son test
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import interpreteur_commandes as interp
from app.services import menu_commandes as svc_menu
from database.models import Parcelle, Potager, User
from utils.parcelles import (
    LARGEUR_MIN_PLAUSIBLE,
    LONGUEUR_MAX,
    LONGUEUR_MIN,
    format_longueur,
    largeur_deduite,
    update_parcelle,
)

RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="planche nord", nom_normalise="planchenord",
                 potager_id=1, superficie_m2=16.0),
        Parcelle(id=2, nom="planche centrale", nom_normalise="planchecentrale",
                 potager_id=1, superficie_m2=69.0, longueur_m=12.0),
    ])
    test_db.commit()
    return test_db


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — La colonne : nullable, bornée, jamais backfillée
# ═════════════════════════════════════════════════════════════════════════════

def test_us225_ca1_parcelle_neuve_sans_longueur(db) -> None:
    """CA1 — Une parcelle jamais mesurée porte None, pas 0."""
    parcelle = db.query(Parcelle).filter_by(nom_normalise="planchenord").one()
    assert parcelle.longueur_m is None


def test_us225_ca1_non_renseignee_n_est_pas_zero(db) -> None:
    """CA1 — « zéro mètre » n'existe pas : il est refusé, et rien n'est écrit."""
    with pytest.raises(ValueError):
        update_parcelle(db, "planche nord", potager_id=1, longueur="0")
    assert db.query(Parcelle).filter_by(id=1).one().longueur_m is None


def test_us225_ca1_aucune_longueur_deduite_de_la_superficie(db) -> None:
    """CA1 — Aucun backfill : 16 m² ne donne pas « 4 m de long »."""
    parcelle = db.query(Parcelle).filter_by(id=1).one()
    assert parcelle.superficie_m2 == 16.0
    assert parcelle.longueur_m is None


def test_us225_ca1_bornes_du_domaine() -> None:
    """CA1 — Les bornes sont celles de la migration : 0,5 à 200 m."""
    assert (LONGUEUR_MIN, LONGUEUR_MAX) == (0.5, 200.0)
    migration = (RACINE / "migrations" / "migration_v53.sql").read_text(encoding="utf-8")
    assert "longueur_m NUMERIC(5,1)" in migration
    assert "BETWEEN 0.5 AND 200" in migration
    assert (RACINE / "migrations" / "rollback_v53.sql").exists()


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — /parcelle modifier longueur=…
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "saisie, attendu",
    [
        ("12", 12.0),
        ("12.5", 12.5),
        ("12,5", 12.5),      # la virgule décimale de la dictée française
        ("12 m", 12.0),      # l'unité dictée ne fait pas échouer la saisie
        ("12 mètres", 12.0),
        ("0.5", 0.5),        # borne basse
        ("200", 200.0),      # borne haute
    ],
)
def test_us225_ca2_valeurs_acceptees(db, saisie: str, attendu: float) -> None:
    """CA2 — La commande accepte 12, 12.5 et 12,5."""
    parcelle, modifs = update_parcelle(db, "planche nord", potager_id=1, longueur=saisie)
    assert parcelle.longueur_m == attendu
    assert any("Longueur" in m for m in modifs)


@pytest.mark.parametrize("aucune", ["aucune", "aucun", "non", "vide"])
def test_us225_ca2_retour_a_non_renseignee(db, aucune: str) -> None:
    """CA2 — « longueur=aucune » remet la parcelle à « non renseignée »."""
    parcelle, modifs = update_parcelle(db, "planche centrale", potager_id=1, longueur=aucune)
    assert parcelle.longueur_m is None
    assert "Longueur : non renseignée" in modifs


@pytest.mark.parametrize("saisie", ["0", "0.4", "200.1", "500", "douze", "-12", "12 m2"])
def test_us225_ca2_valeurs_refusees_conservent_la_precedente(db, saisie: str) -> None:
    """CA2 — Refus AVANT affectation : la valeur précédente survit intacte."""
    with pytest.raises(ValueError) as erreur:
        update_parcelle(db, "planche centrale", potager_id=1, longueur=saisie)
    # Le message rappelle la forme attendue, pas seulement « valeur invalide ».
    assert "longueur=" in str(erreur.value)
    assert db.query(Parcelle).filter_by(id=2).one().longueur_m == 12.0


def test_us225_ca2_cle_inconnue_toujours_refusee(db) -> None:
    """CA2 — La clé « largeur » n'existe pas : elle se déduit, elle ne s'écrit pas."""
    with pytest.raises(ValueError) as erreur:
        update_parcelle(db, "planche nord", potager_id=1, largeur="3")
    assert "largeur" in str(erreur.value)


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La même déclaration, en une phrase
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "phrase, attendu",
    [
        ("la planche centrale fait 12 mètres de long", "longueur=12"),
        ("la planche nord mesure 8 m", "longueur=8"),
        ("planche-centrale a des rangs de 12 m", "longueur=12"),
        ("la planche nord fait 12,5 mètres", "longueur=12.5"),
        ("je veux que la planche nord mesure 10 mètres de longueur", "longueur=10"),
    ],
)
def test_us225_ca3_declaration_par_phrase(phrase: str, attendu: str) -> None:
    """CA3 — La grammaire déterministe traduit la phrase en /parcelle modifier."""
    resultat = interp.interpreter(phrase, autoriser_modele=False)
    assert isinstance(resultat, interp.CommandeInterpretee)
    assert (resultat.commande, resultat.sous_commande) == ("parcelle", "modifier")
    assert resultat.valeurs["modification"] == attendu


def test_us225_ca3_aucun_jeton_consomme() -> None:
    """CA3 — Reconnue par une RÈGLE : aucun appel modèle, donc aucun jeton."""
    resultat = interp.interpreter(
        "la planche centrale fait 12 mètres de long", autoriser_modele=False
    )
    assert resultat.origine == interp.ORIGINE_REGLE
    assert resultat.regle.startswith("parcelle_longueur")


def test_us225_ca3_confirmation_avant_ecriture() -> None:
    """CA3 — /parcelle modifier écrit : le catalogue exige la confirmation."""
    forme = {f.cle: f for f in svc_menu.FORMES_DICTABLES}[("parcelle", "modifier")]
    assert forme.confirmation is True


def test_us225_ca3_question_fermee_n_ecrit_pas() -> None:
    """CA3 — « est-ce que la planche nord mesure 8 m ? » interroge, elle ne déclare pas."""
    assert interp.interpreter(
        "est-ce que la planche nord mesure 8 m ?", autoriser_modele=False
    ) is None


def test_us225_ca3_la_superficie_reste_une_superficie() -> None:
    """CA3 — « 12 m² » n'est pas une longueur : les règles de superficie gardent la main."""
    for phrase in (
        "la planche nord fait 12 m2",
        "la superficie de la planche nord fait 12 m",
        "la surface de la planche nord est de 8,5 m²",
    ):
        resultat = interp.interpreter(phrase, autoriser_modele=False)
        assert isinstance(resultat, interp.CommandeInterpretee), phrase
        assert resultat.valeurs["modification"].startswith("superficie="), phrase


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — Un semis en mètres de rang n'est pas une longueur de planche
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "phrase",
    [
        "semé 3 mètres de carottes dans la planche nord",
        "semé 3 m de radis parcelle nord",
        "planté 2 mètres de poireaux dans la planche centrale",
    ],
)
def test_us225_ca4_un_geste_ne_declare_pas_la_planche(phrase: str) -> None:
    """CA4 — Aucun semis en mètres de rang ne devient une modification de parcelle."""
    resultat = interp.interpreter(phrase, autoriser_modele=False)
    if isinstance(resultat, interp.CommandeInterpretee):
        assert (resultat.commande, resultat.sous_commande) != ("parcelle", "modifier"), phrase


def test_us225_ca4_la_planche_garde_sa_longueur(db) -> None:
    """CA4 — Gherkin : le semis passe, la longueur de la planche ne bouge pas."""
    avant = db.query(Parcelle).filter_by(id=2).one().longueur_m
    resultat = interp.interpreter(
        "semé 3 mètres de carottes dans la planche centrale", autoriser_modele=False
    )
    assert not (
        isinstance(resultat, interp.CommandeInterpretee)
        and resultat.valeurs.get("modification", "").startswith("longueur=")
    )
    assert db.query(Parcelle).filter_by(id=2).one().longueur_m == avant == 12.0


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — /parcelle lister, l'usage et le récapitulatif
# ═════════════════════════════════════════════════════════════════════════════

def _update_ctx(args: list[str]):
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = args
    ctx.user_data = {}
    return update, ctx


@pytest.mark.asyncio
async def test_us225_ca5_lister_dit_la_longueur(db) -> None:
    """CA5 — /parcelle lister affiche la longueur et signale les absentes."""
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
    assert "longueur non renseignée" in texte   # planche nord
    assert "12 m de long" in texte              # planche centrale


@pytest.mark.asyncio
async def test_us225_ca5_usage_rappelle_la_cle(db) -> None:
    """CA5 — L'aide de /parcelle montre la forme longueur=12 et longueur=aucune."""
    update, ctx = _update_ctx([])
    from app.bot import cmd_parcelle
    await cmd_parcelle(update, ctx)
    texte = update.message.reply_text.call_args[0][0]
    assert "longueur=12" in texte and "longueur=aucune" in texte


def test_us225_ca5_recapitulatif_nomme_la_longueur_en_metres() -> None:
    """CA5 — Le récapitulatif nomme la planche, la longueur, et ses mètres.

    L'unité n'est pas décorative : « 12 » et « 12 m² » écriraient deux données
    différentes, et c'est exactement la confusion que la confirmation doit lever.
    """
    resultat = interp.interpreter(
        "la planche centrale fait 12 mètres de long", autoriser_modele=False
    )
    recap = interp.recapitulatif(resultat)
    assert "planche centrale" in recap.lower()
    assert "longueur" in recap
    assert "12 m" in recap
    assert "douze" in recap          # [US-172 / CA11] relu en toutes lettres
    assert "longueur=12" in recap    # la commande équivalente, pour l'apprendre


def test_us225_ca5_format_de_longueur() -> None:
    """CA5 — « 12 m », « 12,5 m », « non renseignée » — jamais « 12.0 m »."""
    assert format_longueur(12.0) == "12 m"
    assert format_longueur(12.5) == "12,5 m"
    assert format_longueur(None) == "non renseignée"


# ═════════════════════════════════════════════════════════════════════════════
# CA6 / CA7 — GET /plan : la longueur servie, la largeur déduite
# ═════════════════════════════════════════════════════════════════════════════

def test_us225_ca6_largeur_deduite_pure() -> None:
    """CA6 — Gherkin : 69 m² sur 12 m de long font 5,75 m de large."""
    assert largeur_deduite(69.0, 12.0) == (5.75, False)


@pytest.mark.parametrize(
    "superficie, longueur",
    [(None, 12.0), (69.0, None), (None, None)],
)
def test_us225_ca6_largeur_absente_si_une_valeur_manque(superficie, longueur) -> None:
    """CA6 — Une largeur ne se suppose pas : il faut les deux valeurs."""
    assert largeur_deduite(superficie, longueur) == (None, False)


def test_us225_ca7_largeur_incoherente_signalee_jamais_corrigee() -> None:
    """CA7 — Gherkin : 2 m² sur 40 m de long — signalé, et la valeur reste."""
    largeur, incoherente = largeur_deduite(2.0, 40.0)
    assert incoherente is True
    assert largeur == 0.05 < LARGEUR_MIN_PLAUSIBLE


def test_us225_ca7_format_de_largeur() -> None:
    """CA7 — Une largeur absurde se compte en centimètres, sinon le zéro se perd."""
    from utils.parcelles import format_largeur

    assert format_largeur(0.05) == "5 cm"
    assert format_largeur(0.75) == "75 cm"
    assert format_largeur(5.75) == "5,75 m"
    assert format_largeur(0.004) == "moins de 1 cm"
    assert format_largeur(None) == "non déduite"


def test_us225_ca7_le_compagnon_signale_a_la_declaration(db) -> None:
    """CA7 — Relevé de terrain : 100 m sur 5 m² passait sans un mot.

    Le CA7 confie l'alerte à l'écran, mais la confirmation du compagnon est le
    seul moment où le jardinier a la valeur sous les yeux quand il la dit.
    """
    parcelle, modifs = update_parcelle(
        db, "planche nord", potager_id=1, superficie="5", longueur="100"
    )
    alerte = next((m for m in modifs if m.startswith("⚠️")), None)
    assert alerte is not None, modifs
    assert "100 m" in alerte and "5 m²" in alerte and "5 cm" in alerte
    # Signalée, JAMAIS corrigée : la valeur dite par le jardinier est enregistrée.
    assert parcelle.longueur_m == 100.0
    assert parcelle.superficie_m2 == 5.0


def test_us225_ca7_corriger_la_superficie_alerte_aussi(db) -> None:
    """CA7 — L'incohérence a deux côtés : la superficie seule doit alerter."""
    _, modifs = update_parcelle(db, "planche centrale", potager_id=1, superficie="1")
    assert any(m.startswith("⚠️") for m in modifs), modifs


def test_us225_ca7_aucune_alerte_quand_les_valeurs_se_tiennent(db) -> None:
    """CA7 — 69 m² sur 12 m font 5,75 m de large : rien à signaler."""
    _, modifs = update_parcelle(db, "planche centrale", potager_id=1, longueur="12")
    assert not any(m.startswith("⚠️") for m in modifs), modifs


def test_us225_ca7_aucune_alerte_sans_superficie(db) -> None:
    """CA7 — Sans superficie, il n'y a rien à comparer : ni alerte, ni refus."""
    db.query(Parcelle).filter_by(id=1).one().superficie_m2 = None
    db.commit()
    parcelle, modifs = update_parcelle(db, "planche nord", potager_id=1, longueur="100")
    assert parcelle.longueur_m == 100.0
    assert not any(m.startswith("⚠️") for m in modifs), modifs


def test_us225_ca7_l_alerte_ne_bloque_pas_les_autres_modifications(db) -> None:
    """CA7 — Non bloquante : les autres clés de la même commande sont appliquées."""
    parcelle, modifs = update_parcelle(
        db, "planche nord", potager_id=1, longueur="100", exposition="sud"
    )
    assert parcelle.exposition == "sud"
    assert any(m.startswith("⚠️") for m in modifs)


@pytest.mark.asyncio
async def test_us225_ca7_le_bot_affiche_l_alerte(db) -> None:
    """CA7 — L'alerte remonte telle quelle dans la réponse du compagnon."""
    update, ctx = _update_ctx(["modifier", "planche nord", "superficie=5", "longueur=100"])
    with (
        patch("app.bot.SessionLocal", return_value=db),
        patch("app.bot.commandes_parcelle.current_context", return_value=MagicMock(potager_id=1)),
        patch("app.bot.commandes_parcelle._refuser_si_role_insuffisant",
              new=AsyncMock(return_value=False)),
    ):
        from app.bot import cmd_parcelle
        await cmd_parcelle(update, ctx)

    texte = update.message.reply_text.call_args[0][0]
    assert "⚠️" in texte and "5 cm" in texte


def _parcelle_mock(nom: str, *, longueur=None, superficie=None, ordre=0, pepiniere=False):
    p = MagicMock(spec=Parcelle)
    p.id = abs(hash(nom)) % 1000
    p.nom = nom
    p.exposition = None
    p.superficie_m2 = superficie
    p.abri = None
    p.paillage = None
    p.nb_rangs = None
    p.longueur_m = longueur
    p.ordre = ordre
    p.est_pepiniere = pepiniere
    p.actif = True
    return p


@pytest.fixture
def client_plan():
    from app.api.main import app, get_current_user_ctx
    from app.services.context import default_context

    parcelles = [
        _parcelle_mock("Centrale", longueur=12.0, superficie=69.0, ordre=1),
        _parcelle_mock("Sans longueur", superficie=16.0, ordre=2),
        _parcelle_mock("Sans superficie", longueur=8.0, ordre=3),
        _parcelle_mock("Petit carre", longueur=40.0, superficie=2.0, ordre=4),
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


def test_us225_ca6_plan_expose_longueur_et_largeur_deduite(client_plan) -> None:
    """CA6 — longueur_m servie telle quelle, largeur_m déduite et marquée comme telle."""
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    centrale = par_nom["Centrale"]
    assert centrale["longueur_m"] == 12.0
    assert centrale["largeur_m"] == 5.75
    assert centrale["largeur_deduite"] is True
    assert centrale["largeur_incoherente"] is False


def test_us225_ca6_plan_sans_longueur_ni_largeur(client_plan) -> None:
    """CA6 — Non renseignée se sert tel quel : jamais 0, et pas de largeur."""
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    assert par_nom["Sans longueur"]["longueur_m"] is None
    assert par_nom["Sans longueur"]["largeur_m"] is None
    assert par_nom["Sans longueur"]["largeur_deduite"] is False
    # Une longueur sans superficie ne produit aucune largeur non plus.
    assert par_nom["Sans superficie"]["longueur_m"] == 8.0
    assert par_nom["Sans superficie"]["largeur_m"] is None


def test_us225_ca7_plan_signale_la_largeur_incoherente(client_plan) -> None:
    """CA7 — Incohérence NON bloquante : servie, signalée, jamais corrigée."""
    par_nom = {p["nom"]: p for p in client_plan.get("/plan").json()["parcelles"]}
    carre = par_nom["Petit carre"]
    assert carre["longueur_m"] == 40.0          # la valeur du jardinier, intacte
    assert carre["largeur_incoherente"] is True


def test_us225_ca6_aucun_champ_existant_retire(client_plan) -> None:
    """CA6 — Les champs servis jusqu'ici le sont toujours."""
    parcelle = client_plan.get("/plan").json()["parcelles"][0]
    for champ in ("id", "nom", "exposition", "superficie_m2", "abri", "paillage",
                  "nb_rangs", "ordre", "est_pepiniere", "cultures", "occupation_pct",
                  "has_observations", "nb_observations", "disposition"):
        assert champ in parcelle


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Aucun calcul ne lit la longueur
# ═════════════════════════════════════════════════════════════════════════════

def test_us225_ca8_aucun_moteur_de_calcul_ne_lit_la_longueur() -> None:
    """CA8 — `longueur_m` ne se lit que là où elle se déclare, s'affiche ou se sert.

    Un test de comportement ne prouverait l'absence d'effet que sur les cas
    qu'il énumère ; ce contrôle-ci la prouve à la source. L'ajouter dans un
    moteur de calcul fait échouer ce test, et c'est le point.
    """
    autorises = {
        Path("database/models.py"),
        Path("utils/parcelles.py"),
        Path("app/services/interpreteur_commandes.py"),
        Path("app/bot/commandes_parcelle.py"),
        Path("app/api/main.py"),
        # [US-227] La longueur est devenue la base des places d'un rang — elle
        # se lit donc aussi dans la répartition, et nulle part ailleurs.
        Path("app/services/repartition_rangs.py"),
    }
    fautifs = []
    for chemin in RACINE.glob("**/*.py"):
        relatif = chemin.relative_to(RACINE)
        if relatif.parts[0] in {"tests", ".venv", "migrations", "tools"}:
            continue
        if relatif in autorises:
            continue
        if "longueur_m" in chemin.read_text(encoding="utf-8"):
            fautifs.append(str(relatif))
    assert not fautifs, f"longueur_m lue hors des points prévus : {fautifs}"


def test_us225_ca8_stock_occupation_rendement_et_confiance_intacts() -> None:
    """CA8 — Ni le stock, ni le rendement, ni la confiance ne connaissent la longueur."""
    for module in ("utils/stock.py", "app/services/confiance_semis.py",
                   "app/services/reponses_chiffrees.py", "app/services/stats.py"):
        assert "longueur_m" not in (RACINE / module).read_text(encoding="utf-8")


def test_us225_ca8_occupation_pct_ignore_la_longueur(client_plan) -> None:
    """CA8 — L'occupation reste une affaire de surface, sans aucune culture ici."""
    for parcelle in client_plan.get("/plan").json()["parcelles"]:
        assert parcelle["occupation_pct"] is None


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — La PWA n'offre aucun champ de saisie (RT1)
# ═════════════════════════════════════════════════════════════════════════════

def test_us225_ca9_aucune_saisie_dans_la_pwa() -> None:
    """CA9 — La Vue plan LIT la longueur ; ce qui reste interdit, c'est de l'ÉCRIRE."""
    ECRITURE = ("<Field", "<input", "onChange", "JSON.stringify", "body:", "value=")
    sources = list((RACINE / "frontend" / "src").glob("**/*.jsx"))
    sources += list((RACINE / "frontend" / "src").glob("**/*.js"))
    ecrivains = [
        f"{f.relative_to(RACINE)}:{n}"
        for f in sources
        for n, ligne in enumerate(f.read_text(encoding="utf-8").splitlines(), 1)
        if ("longueur_m" in ligne or "largeur_m" in ligne)
        and any(marqueur in ligne for marqueur in ECRITURE)
    ]
    assert not ecrivains, f"la PWA ne doit offrir aucun champ de longueur : {ecrivains}"


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — Le catalogue des commandes
# ═════════════════════════════════════════════════════════════════════════════

def test_us225_ca10_le_catalogue_connait_la_cle() -> None:
    """CA10 — Toute clé acceptée à l'écriture a son libellé et son unité."""
    from utils.parcelles import _CHAMPS_MODIFIER

    assert "longueur" in _CHAMPS_MODIFIER
    for cle in _CHAMPS_MODIFIER:
        assert cle in interp._LIBELLES_MODIFICATION, f"clé sans libellé : {cle}"
        assert cle in interp._UNITES_MODIFICATION, f"clé sans unité déclarée : {cle}"
    # Des mètres, jamais des mètres carrés.
    assert interp._UNITES_MODIFICATION["longueur"] == "m"


def test_us225_ca10_la_forme_dictable_cite_la_longueur() -> None:
    """CA10 — La relance vocale d'un argument manquant propose la nouvelle clé."""
    forme = {f.cle: f for f in svc_menu.FORMES_DICTABLES}[("parcelle", "modifier")]
    question = {a.nom: a.question for a in forme.arguments}["modification"]
    assert "longueur" in question


def test_us225_ca10_parite_des_commandes_verte() -> None:
    """CA10 — Aucune commande ajoutée ni retirée : la parité tient."""
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
# CA11 — La documentation livrée dans la même livraison (US-099 / CA9)
# ═════════════════════════════════════════════════════════════════════════════

def test_us225_ca11_fiche_de_corpus_a_jour() -> None:
    """CA11 — La fiche parcelles-et-plan porte la longueur et la largeur déduite."""
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "parcelles-et-plan.md").read_text(
        encoding="utf-8"
    )
    assert "## Dire combien de rangs compte une parcelle" in fiche
    assert "longueur non renseignée" in fiche
    assert "le même nombre" in fiche          # longueur de parcelle = longueur de rang
    assert "allées" in fiche                  # c'est la longueur UTILE
    assert "ne se déclare jamais" in fiche    # la largeur se déduit


def test_us225_ca11_guide_utilisateur_a_jour() -> None:
    """CA11 — Le § 21.4 du guide cite la clé et sa remise à « non renseignée »."""
    guide = (RACINE / "data" / "connaissance" / "guide user" / "guide assistant.md").read_text(
        encoding="utf-8"
    )
    assert "longueur=aucune" in guide


def test_us225_ca11_fiches_de_domaine_a_jour() -> None:
    """CA11 — migrations.md décrit la v53 ; plan-et-rangs.md dit la longueur unique."""
    migrations = (RACINE / "docs" / "domaines" / "migrations.md").read_text(encoding="utf-8")
    assert "v53 [US-225]" in migrations
    assert "longueur_m" in migrations

    domaine = (RACINE / "docs" / "domaines" / "plan-et-rangs.md").read_text(encoding="utf-8")
    assert "une longueur unique" in domaine
    assert "largeur_deduite" in domaine
