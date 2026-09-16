"""
tests/test_us193_zone_altitude.py — Zone climatique déduite avec l'altitude [US-193]
===================================================================================

- CA1  altitude conservée avec la ville, à la création comme à la modification
- CA2  latitude, longitude et altitude changent ensemble
- CA3  reprise des potagers déjà localisés ; sans altitude, jamais « montagnard »
- CA4  seuil montagnard réglable (700 m par défaut)
- CA5  tableau des villes de référence
- CA6  le choix du jardinier prime ; « auto » revient à la déduction
- CA7  libellé : altitude retenue, ou rappel de la commande sans altitude
- CA8  bot et écran Plan lisent la même zone
- CA9  hors France métropolitaine : aucune zone déduite
- CA10 fiche de connaissance à jour
- CA11 la zone CHOISIE n'est jamais modifiée
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import calendrier_cultural as cal
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from database.db import Base
from database.models import CultureConfig, Potager, User
from utils import altitude as util_altitude

RACINE = Path(__file__).resolve().parent.parent

BRIANCON = (44.90, 6.64, 1326.0)
CHAMONIX = (45.92, 6.87, 1035.0)
RENNES = (48.11, -1.68, 30.0)
PONTARLIER = (46.90, 6.35, 837.0)
REIMS = (49.26, 4.03, 80.0)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    test_db.commit()
    return test_db


def _localiser(db, lat, lon, alt, zone=None):
    potager = db.get(Potager, 1)
    potager.latitude, potager.longitude, potager.altitude = lat, lon, alt
    potager.zone_climatique = zone
    db.commit()
    return potager


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — villes de référence (le tableau fait foi)
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("ville, lat, lon, alt, attendu", [
    ("Brest", 48.39, -4.49, 50, "oceanique"),
    ("Rennes", 48.11, -1.68, 30, "oceanique"),
    ("Bordeaux", 44.84, -0.58, 10, "oceanique"),
    ("Paris", 48.86, 2.35, 35, "oceanique"),
    ("Lille", 50.63, 3.06, 20, "oceanique"),
    ("Toulouse", 43.60, 1.44, 150, "oceanique"),
    ("Reims", 49.26, 4.03, 80, "continental"),
    ("Strasbourg", 48.58, 7.75, 140, "continental"),
    ("Nancy", 48.69, 6.18, 200, "continental"),
    ("Dijon", 47.32, 5.04, 245, "continental"),
    ("Lyon", 45.76, 4.84, 170, "continental"),
    ("Grenoble", 45.19, 5.72, 212, "continental"),
    ("Montpellier", 43.61, 3.88, 30, "mediterraneen"),
    ("Marseille", 43.30, 5.37, 10, "mediterraneen"),
    ("Nice", 43.70, 7.27, 20, "mediterraneen"),
    ("Perpignan", 42.70, 2.90, 30, "mediterraneen"),
    ("Ajaccio", 41.93, 8.74, 20, "mediterraneen"),
    ("Montélimar", 44.56, 4.75, 80, "mediterraneen"),
    ("Briançon", 44.90, 6.64, 1326, "montagnard"),
    ("Chamonix", 45.92, 6.87, 1035, "montagnard"),
    ("Pontarlier", 46.90, 6.35, 837, "montagnard"),
    ("Le Mont-Dore", 45.58, 2.81, 1050, "montagnard"),
])
def test_us193_ca5_villes_de_reference(ville, lat, lon, alt, attendu) -> None:
    """[CA5] Chaque ville du tableau de recette lit la zone attendue."""
    assert cal.zone_depuis_localisation(lat, lon, alt) == attendu, ville


# ═════════════════════════════════════════════════════════════════════════════
# CA3, CA4, CA9 — la règle
# ═════════════════════════════════════════════════════════════════════════════
def test_us193_ca4_seuil_par_defaut_700m() -> None:
    """[CA4] 700 m par défaut, borne incluse."""
    assert cal.seuil_montagnard() == 700
    assert cal.zone_depuis_localisation(47.32, 5.04, 700) == "montagnard"
    assert cal.zone_depuis_localisation(47.32, 5.04, 699) == "continental"


def test_us193_ca4_seuil_reglable_sans_redeploiement(monkeypatch) -> None:
    """[CA4] Le seuil se lit dans la configuration à chaque déduction."""
    import app.config
    monkeypatch.setattr(app.config, "CALENDRIER_SEUIL_MONTAGNARD_M", 600.0)
    # Gérardmer, 670 m : montagnard avec un seuil abaissé.
    assert cal.zone_depuis_localisation(48.07, 6.88, 670) == "montagnard"


def test_us193_ca4_montagnard_quelle_que_soit_la_position() -> None:
    """[CA4] Au-dessus du seuil, même en zone méditerranéenne ou océanique."""
    assert cal.zone_depuis_localisation(43.70, 7.27, 1200) == "montagnard"
    assert cal.zone_depuis_localisation(43.0, 0.1, 900) == "montagnard"


def test_us193_ca3_sans_altitude_jamais_montagnard() -> None:
    """[CA3] Briançon sans altitude connue : pas de montagnard supposé."""
    assert cal.zone_depuis_localisation(BRIANCON[0], BRIANCON[1], None) != "montagnard"
    assert cal.zone_depuis_localisation(BRIANCON[0], BRIANCON[1]) != "montagnard"


@pytest.mark.parametrize("lat, lon, alt", [
    (-0.18, -78.47, 2850),   # Quito
    (40.71, -74.0, 10),      # New York
    (None, 6.64, 1326),
    (44.90, None, 1326),
])
def test_us193_ca9_hors_france_aucune_zone_meme_avec_altitude(lat, lon, alt) -> None:
    """[CA9] Hors métropole ou coordonnées incomplètes : None, altitude connue ou non."""
    assert cal.zone_depuis_localisation(lat, lon, alt) is None


def test_us193_ca9_hors_france_lit_la_zone_par_defaut(db) -> None:
    potager = _localiser(db, -0.18, -78.47, 2850)
    assert cal.zone_effective(potager) == (cal.zone_par_defaut(), cal.ORIGINE_ZONE_DEFAUT)


# ═════════════════════════════════════════════════════════════════════════════
# CA6, CA11 — le choix du jardinier prime
# ═════════════════════════════════════════════════════════════════════════════
def test_us193_ca6_zone_deduite_montagnard(db) -> None:
    potager = _localiser(db, *BRIANCON)
    assert cal.zone_effective(potager) == ("montagnard", cal.ORIGINE_ZONE_LOCALISATION)


def test_us193_ca6_le_choix_du_jardinier_prime_sur_l_altitude(db) -> None:
    """[CA6] Gherkin : Briançon choisi en continental reste continental."""
    _localiser(db, *BRIANCON)
    cal.definir_zone(db, CTX, "continental")
    zone, origine, altitude = cal.zone_et_altitude_du_potager(db, 1)
    assert (zone, origine) == ("continental", cal.ORIGINE_ZONE_JARDINIER)
    assert cal.libelle_zone(zone, origine, altitude) == "continental (choix du jardinier)"


def test_us193_ca6_auto_revient_a_la_deduction_avec_altitude(db) -> None:
    _localiser(db, *BRIANCON, zone="oceanique")
    _, apres = cal.definir_zone(db, CTX, "auto")
    assert apres == ("montagnard", cal.ORIGINE_ZONE_LOCALISATION)


def test_us193_ca11_zone_choisie_jamais_modifiee_par_la_reprise(db) -> None:
    """[CA11] La reprise d'altitude ne touche pas `zone_climatique`."""
    _localiser(db, BRIANCON[0], BRIANCON[1], None, zone="oceanique")
    svc_potagers.renseigner_altitudes_manquantes(db, lambda points: [1326.0] * len(points))
    potager = db.get(Potager, 1)
    assert potager.zone_climatique == "oceanique"
    assert cal.zone_effective(potager) == ("oceanique", cal.ORIGINE_ZONE_JARDINIER)


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — libellés
# ═════════════════════════════════════════════════════════════════════════════
def test_us193_ca7_libelle_avec_altitude() -> None:
    assert (
        cal.libelle_zone("montagnard", cal.ORIGINE_ZONE_LOCALISATION, 1326.4)
        == "montagnard (déduite de la localisation, 1 326 m)"
    )
    assert (
        cal.libelle_zone("continental", cal.ORIGINE_ZONE_LOCALISATION, 80)
        == "continental (déduite de la localisation, 80 m)"
    )


def test_us193_ca7_libelle_sans_altitude_indique_la_commande() -> None:
    libelle = cal.libelle_zone("continental", cal.ORIGINE_ZONE_LOCALISATION, None)
    assert libelle.startswith("continental (déduite de la localisation")
    assert "montagne" in libelle
    assert "/calendrier zone montagnard" in libelle


def test_us193_ca7_libelle_defaut_inchange() -> None:
    assert cal.libelle_zone("oceanique", cal.ORIGINE_ZONE_DEFAUT, 1326) == "océanique (zone par défaut)"


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — le bot (/calendrier)
# ═════════════════════════════════════════════════════════════════════════════
async def _bot(db, *args) -> str:
    from app import bot
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = list(args)
    with patch.object(bot, "SessionLocal", return_value=db), \
         patch.object(bot, "current_context", return_value=CTX):
        await bot.cmd_calendrier(update, ctx)
    return update.message.reply_text.call_args[0][0]


@pytest.mark.asyncio
async def test_us193_bot_potager_de_montagne(db) -> None:
    """Gherkin : Briançon lit « montagnard (déduite de la localisation, 1 326 m) »."""
    _localiser(db, *BRIANCON)
    texte = await _bot(db, "tomate")
    assert "Zone : montagnard (déduite de la localisation, 1 326 m)" in texte


@pytest.mark.asyncio
async def test_us193_bot_ville_de_plaine_de_l_est(db) -> None:
    """Gherkin : Reims n'est plus lue en océanique."""
    _localiser(db, *REIMS)
    texte = await _bot(db, "tomate")
    assert "Zone : continental (déduite de la localisation, 80 m)" in texte


@pytest.mark.asyncio
async def test_us193_bot_choix_du_jardinier(db) -> None:
    """Gherkin : le choix du jardinier prime sur l'altitude."""
    _localiser(db, *BRIANCON, zone="continental")
    texte = await _bot(db, "tomate")
    assert "Zone : continental (choix du jardinier)" in texte


@pytest.mark.asyncio
async def test_us193_bot_zone_sans_altitude_rappelle_la_commande(db) -> None:
    _localiser(db, BRIANCON[0], BRIANCON[1], None)
    texte = await _bot(db, "zone")
    assert "/calendrier zone montagnard" in texte


@pytest.mark.asyncio
async def test_us193_bot_changement_de_zone_dit_l_altitude(db) -> None:
    _localiser(db, *BRIANCON, zone="oceanique")
    texte = await _bot(db, "zone", "auto")
    assert "montagnard (déduite de la localisation, 1 326 m)" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — même zone au bot et sur l'écran Plan
# ═════════════════════════════════════════════════════════════════════════════
def test_us193_ca8_bot_et_plan_lisent_la_meme_zone(db) -> None:
    _localiser(db, *CHAMONIX)
    calendrier = cal.lire_calendrier(db, "tomate", 1)
    plan = cal.calendriers_du_plan(db, ["tomate"], 1)
    assert (plan["zone_climatique"], plan["zone_climatique_origine"]) == (calendrier.zone, calendrier.zone_origine)
    assert plan["zone_altitude"] == calendrier.zone_altitude == 1035.0
    assert plan["zone_libelle"] == cal.libelle_zone(calendrier.zone, calendrier.zone_origine, calendrier.zone_altitude)
    assert cal.calendrier_en_dict(calendrier)["zone_altitude"] == 1035.0


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — l'altitude suit la ville
# ═════════════════════════════════════════════════════════════════════════════
def _user(db, email="jardinier@potager.test") -> User:
    user = User(email=email, mot_de_passe_hash="x")
    db.add(user)
    db.commit()
    return user


def test_us193_ca1_creation_conserve_l_altitude(test_db) -> None:
    user = _user(test_db)
    potager = svc_potagers.creer_potager(
        test_db, user.id, "Jardin", ville="Briançon", latitude=BRIANCON[0], longitude=BRIANCON[1],
        altitude=BRIANCON[2],
    )
    assert potager.altitude == 1326.0
    assert cal.zone_effective(potager)[0] == "montagnard"


def test_us193_ca1_altitude_sans_coordonnees_ignoree(test_db) -> None:
    user = _user(test_db)
    potager = svc_potagers.creer_potager(test_db, user.id, "Jardin", altitude=1326.0)
    assert potager.altitude is None


def test_us193_ca2_changer_de_ville_met_a_jour_l_altitude(test_db) -> None:
    """Gherkin : Rennes → Chamonix, altitude et zone suivent."""
    user = _user(test_db)
    potager = svc_potagers.creer_potager(
        test_db, user.id, "Jardin", ville="Rennes", latitude=RENNES[0], longitude=RENNES[1], altitude=RENNES[2],
    )
    assert cal.zone_effective(potager)[0] == "oceanique"
    potager = svc_potagers.modifier_potager(
        test_db, user.id, potager.id, ville="Chamonix", latitude=CHAMONIX[0], longitude=CHAMONIX[1],
        altitude=CHAMONIX[2],
    )
    assert potager.altitude == pytest.approx(1035)
    assert cal.zone_effective(potager)[0] == "montagnard"


def test_us193_ca2_nouvelles_coordonnees_sans_altitude_effacent_l_ancienne(test_db) -> None:
    """[CA2] Jamais l'altitude de l'ancienne ville avec les coordonnées de la nouvelle."""
    user = _user(test_db)
    potager = svc_potagers.creer_potager(
        test_db, user.id, "Jardin", latitude=BRIANCON[0], longitude=BRIANCON[1], altitude=BRIANCON[2],
    )
    potager = svc_potagers.modifier_potager(test_db, user.id, potager.id, latitude=RENNES[0], longitude=RENNES[1])
    assert potager.altitude is None


def test_us193_ca2_renommer_ne_perd_pas_l_altitude(test_db) -> None:
    """Un renommage qui renvoie les mêmes coordonnées sans altitude la conserve."""
    user = _user(test_db)
    potager = svc_potagers.creer_potager(
        test_db, user.id, "Jardin", latitude=BRIANCON[0], longitude=BRIANCON[1], altitude=BRIANCON[2],
    )
    potager = svc_potagers.modifier_potager(
        test_db, user.id, potager.id, nom="Jardin d'en haut", latitude=BRIANCON[0], longitude=BRIANCON[1],
    )
    assert potager.altitude == 1326.0
    potager = svc_potagers.modifier_potager(test_db, user.id, potager.id, nom="Autre nom")
    assert potager.altitude == 1326.0


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — reprise des potagers déjà localisés
# ═════════════════════════════════════════════════════════════════════════════
def test_us193_ca3_reprise_renseigne_l_altitude(db) -> None:
    """Gherkin : Pontarlier sans altitude reçoit la sienne, et lit montagnard."""
    _localiser(db, PONTARLIER[0], PONTARLIER[1], None)
    appels = []

    def fournisseur(points):
        appels.append(points)
        return [837.0]

    assert svc_potagers.renseigner_altitudes_manquantes(db, fournisseur) == (1, 1)
    potager = db.get(Potager, 1)
    assert potager.altitude == pytest.approx(837)
    assert cal.zone_effective(potager) == ("montagnard", cal.ORIGINE_ZONE_LOCALISATION)
    assert appels == [[(PONTARLIER[0], PONTARLIER[1])]]


def test_us193_ca3_reprise_idempotente_et_ciblee(db) -> None:
    """Déjà renseigné ou non localisé : aucun appel, aucune écriture."""
    db.add(Potager(id=2, nom="Sans ville", proprietaire_id=1))
    _localiser(db, *PONTARLIER)
    fournisseur = MagicMock()
    assert svc_potagers.renseigner_altitudes_manquantes(db, fournisseur) == (0, 0)
    fournisseur.assert_not_called()


def test_us193_ca3_reprise_altitude_inconnue_reste_null(db) -> None:
    _localiser(db, PONTARLIER[0], PONTARLIER[1], None)
    assert svc_potagers.renseigner_altitudes_manquantes(db, lambda points: [None]) == (1, 0)
    potager = db.get(Potager, 1)
    assert potager.altitude is None
    assert cal.zone_effective(potager)[0] != "montagnard"


def test_us193_ca3_outil_dry_run(db, capsys) -> None:
    from tools import renseigner_altitude_potagers as outil
    _localiser(db, PONTARLIER[0], PONTARLIER[1], None)
    db.close = MagicMock()
    with patch.object(outil, "SessionLocal", return_value=db), \
         patch.object(outil, "altitudes_depuis_coordonnees") as reseau:
        assert outil.main(["--dry-run"]) == 0
    reseau.assert_not_called()
    assert "1 potager(s)" in capsys.readouterr().out
    assert db.get(Potager, 1).altitude is None


def test_us193_ca3_outil_renseigne(db, capsys) -> None:
    from tools import renseigner_altitude_potagers as outil
    _localiser(db, PONTARLIER[0], PONTARLIER[1], None)
    db.close = MagicMock()
    with patch.object(outil, "SessionLocal", return_value=db), \
         patch.object(outil, "altitudes_depuis_coordonnees", return_value=[837.0]):
        assert outil.main([]) == 0
    assert "1/1" in capsys.readouterr().out
    assert db.get(Potager, 1).altitude == 837.0


# ── utils/altitude.py : Open-Meteo, toujours mocké ───────────────────────────
def test_us193_altitude_open_meteo_nominal() -> None:
    reponse = MagicMock()
    reponse.json.return_value = {"elevation": [1326.0, 30.0]}
    with patch.object(util_altitude.requests, "get", return_value=reponse) as get:
        assert util_altitude.altitudes_depuis_coordonnees([(44.9, 6.64), (48.11, -1.68)]) == [1326.0, 30.0]
    params = get.call_args[1]["params"]
    assert params == {"latitude": "44.9,48.11", "longitude": "6.64,-1.68"}


def test_us193_altitude_open_meteo_indisponible() -> None:
    """Panne réseau : des None, jamais d'exception."""
    with patch.object(util_altitude.requests, "get", side_effect=requests.ConnectionError("hors ligne")):
        assert util_altitude.altitudes_depuis_coordonnees([(44.9, 6.64)]) == [None]


def test_us193_altitude_open_meteo_reponse_incoherente() -> None:
    reponse = MagicMock()
    reponse.json.return_value = {"elevation": [1326.0]}
    with patch.object(util_altitude.requests, "get", return_value=reponse):
        assert util_altitude.altitudes_depuis_coordonnees([(44.9, 6.64), (48.1, -1.6)]) == [None, None]


def test_us193_altitude_open_meteo_par_lots_de_100() -> None:
    reponse = MagicMock()
    reponse.json.side_effect = [{"elevation": [1.0] * 100}, {"elevation": [2.0] * 5}]
    with patch.object(util_altitude.requests, "get", return_value=reponse) as get:
        resultat = util_altitude.altitudes_depuis_coordonnees([(45.0, 5.0)] * 105)
    assert get.call_count == 2
    assert resultat == [1.0] * 100 + [2.0] * 5


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2, CA8 — API
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def api(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(bind=engine)
    from app.api import main
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(main, "SessionLocal", Session)
    main.app.state.limiter.reset()
    db = Session()
    user = svc_auth.inscrire_utilisateur(db, "jardinier@example.com", "motdepasse123")
    entete = {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}
    db.close()
    with TestClient(main.app) as client:
        yield client, entete
    engine.dispose()


def test_us193_api_creation_et_lecture_de_l_altitude(api) -> None:
    client, entete = api
    resp = client.post(
        "/potagers",
        json={"nom": "Jardin", "ville": "Briançon", "latitude": BRIANCON[0], "longitude": BRIANCON[1],
              "altitude": BRIANCON[2]},
        headers=entete,
    )
    assert resp.status_code == 201
    potager = client.get("/potagers", headers=entete).json()["potagers"][0]
    assert potager["altitude"] == pytest.approx(1326)
    assert (potager["zone_climatique"], potager["zone_climatique_origine"]) == ("montagnard", "localisation")
    detail = client.get(f"/potagers/{potager['id']}", headers=entete).json()
    assert detail["altitude"] == pytest.approx(1326)


def test_us193_api_changer_de_ville(api) -> None:
    client, entete = api
    potager_id = client.post(
        "/potagers",
        json={"nom": "Jardin", "ville": "Rennes", "latitude": RENNES[0], "longitude": RENNES[1], "altitude": 30},
        headers=entete,
    ).json()["id"]
    body = client.patch(
        f"/potagers/{potager_id}",
        json={"ville": "Chamonix", "latitude": CHAMONIX[0], "longitude": CHAMONIX[1], "altitude": CHAMONIX[2]},
        headers=entete,
    ).json()
    assert body["altitude"] == pytest.approx(1035)
    assert (body["zone_climatique"], body["zone_climatique_origine"]) == ("montagnard", "localisation")


# ═════════════════════════════════════════════════════════════════════════════
# Livraison : migration, déploiement, fiche (CA3, CA10)
# ═════════════════════════════════════════════════════════════════════════════
def test_us193_migration_et_rollback() -> None:
    migration = (RACINE / "migrations" / "migration_v48.sql").read_text(encoding="utf-8")
    rollback = (RACINE / "migrations" / "rollback_v48.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS altitude" in migration
    assert "DROP COLUMN IF EXISTS altitude" in rollback


@pytest.mark.parametrize("chemin", [
    ".github/workflows/deploy.yml", ".github/workflows/deploy-dev.yml", "scripts/update_dev.ps1",
])
def test_us193_ca3_reprise_lancee_apres_les_migrations(chemin) -> None:
    contenu = (RACINE / chemin).read_text(encoding="utf-8")
    assert "tools/renseigner_altitude_potagers.py" in contenu
    assert contenu.index("migration_v") < contenu.index("tools/renseigner_altitude_potagers.py")


def test_us193_ca10_fiche_de_connaissance_a_jour() -> None:
    fiche = (RACINE / "data" / "connaissance" / "doc_app" / "calendrier-et-zone-climatique.md").read_text(
        encoding="utf-8"
    )
    assert "altitude" in fiche
    assert "700 mètres" in fiche
    assert "prime toujours" in fiche
    assert "la zone montagnarde n'est jamais supposée, puisque la position seule" not in fiche
