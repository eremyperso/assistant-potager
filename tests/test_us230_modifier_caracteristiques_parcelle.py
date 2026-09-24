"""
tests/test_us230_modifier_caracteristiques_parcelle.py — [US-230] Modifier les
caractéristiques d'une parcelle depuis sa fiche
------------------------------------------------------------------------------
US-229 affiche la carte et **nomme** ce qui manque ; elle s'arrête là. Cette US
ouvre le second chemin d'écriture — le web — pour des champs que le compagnon
sait déjà écrire.

Ce que ce fichier tient, et qui est le cœur de l'US :

- **un seul point d'écriture** : l'API n'a aucune borne à elle, elle appelle
  `utils.parcelles` (CA2, CA3) ;
- **le même refus des deux côtés** : une valeur hors borne envoyée sans passer
  par le formulaire reçoit mot pour mot le message du compagnon (CA5, CA11) ;
- **`NULL` n'est ni `""` ni `false`** (CA6) ;
- **rien n'est écrit à moitié** (CA13) et **un champ non transmis n'est pas
  écrasé** (CA14, E4) ;
- **aucune migration** n'est livrée (CA4).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import parcelles as svc_parcelles
from app.services import potagers as svc_potagers
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError
from database.db import Base
from database.models import Evenement, Parcelle, PotagerMembre, User
from utils.parcelles import create_parcelle, normaliser_type_sol, update_parcelle


# ──────────────────────────────────────────────────────────────────────────────
# Socle
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def _engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(_engine, monkeypatch):
    from app.api import main
    monkeypatch.setattr(main, "SessionLocal", sessionmaker(bind=_engine))
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


@pytest.fixture
def db(_engine):
    session = sessionmaker(bind=_engine)()
    yield session
    session.close()


def _potager(db, email="jardinier@example.com", role="owner"):
    """Un compte web, son potager actif et une planche à corriger."""
    user = svc_auth.inscrire_utilisateur(db, email, "motdepasse123")
    potager = svc_potagers.creer_potager(db, user.id, "Potager de test")
    parcelle = create_parcelle(
        db, "planche_centrale", exposition="Sud", superficie_m2=12.0,
        potager_id=potager.id,
    )
    parcelle.longueur_m = 6.0
    parcelle.nb_rangs = 7
    db.commit()
    return user, potager, parcelle


def _headers(user):
    return {"Authorization": f"Bearer {svc_auth.creer_access_token(user.id)}"}


def _ctx(user, potager, role="owner"):
    return TenantContext(user_id=user.id, potager_id=potager.id, role=role)


# ──────────────────────────────────────────────────────────────────────────────
# CA1 — une route d'écriture, réservée au rôle qui crée déjà une parcelle
# ──────────────────────────────────────────────────────────────────────────────

def test_ca1_patch_parcelle_ecrit_les_champs_transmis(client, db):
    user, potager, parcelle = _potager(db)

    resp = client.patch(
        f"/parcelles/{parcelle.id}",
        json={"type_sol": "Argileux", "nb_rangs": 8},
        headers=_headers(user),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["type_sol"] == "Argileux"
    assert body["nb_rangs"] == 8
    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert relue.type_sol == "Argileux"
    assert relue.nb_rangs == 8


def test_ca1_champ_hors_perimetre_est_refuse_en_le_nommant(client, db):
    """[CA1] La largeur, en particulier : elle se déduit, elle ne se déclare
    pas. Le refus la NOMME plutôt que de renvoyer une erreur de schéma."""
    user, potager, parcelle = _potager(db)

    resp = client.patch(
        f"/parcelles/{parcelle.id}",
        json={"largeur_m": 2.0, "ordre": 3},
        headers=_headers(user),
    )

    assert resp.status_code == 400
    assert "largeur_m" in resp.json()["detail"]
    assert "ordre" in resp.json()["detail"]


def test_ca1_lecteur_ne_peut_pas_modifier(client, db):
    """[E10, CA1] Le rôle est celui qui crée déjà une parcelle (US-058)."""
    owner, potager, parcelle = _potager(db)
    lecteur = svc_auth.inscrire_utilisateur(db, "lecteur@example.com", "motdepasse123")
    db.add(PotagerMembre(user_id=lecteur.id, potager_id=potager.id, role="lecteur"))
    db.commit()

    with pytest.raises(PermissionInsuffisanteError):
        svc_parcelles.modifier_parcelle(
            db, _ctx(lecteur, potager, role="lecteur"), parcelle.id, {"nb_rangs": 8}
        )


def test_ca1_parcelle_d_un_autre_potager_est_introuvable(client, db):
    """[US-042] Le cloisonnement par potager vaut pour l'écriture comme pour la
    lecture : la parcelle d'un autre potager n'existe pas, elle n'est pas
    « interdite »."""
    _, _, parcelle = _potager(db)
    autre = svc_auth.inscrire_utilisateur(db, "autre@example.com", "motdepasse123")
    svc_potagers.creer_potager(db, autre.id, "Autre potager")

    resp = client.patch(
        f"/parcelles/{parcelle.id}", json={"nb_rangs": 3}, headers=_headers(autre)
    )

    assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────────────────────
# CA2, CA3 — un seul point d'écriture : le domaine, jamais le handler
# ──────────────────────────────────────────────────────────────────────────────

def test_ca2_type_sol_et_actif_sont_couverts_par_update_parcelle(db):
    """[CA2] Les deux champs qu'aucune fonction ne couvrait y sont AJOUTÉS,
    avec leurs bornes — et non traités dans le handler."""
    _, potager, parcelle = _potager(db)

    update_parcelle(db, "planche_centrale", potager_id=potager.id,
                    type_sol="argile", actif="false")

    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert relue.type_sol == "Argileux"   # vocabulaire fermé + alias
    assert relue.actif is False


def test_ca3_aucune_borne_n_est_reecrite_dans_l_api(db):
    """[CA3] Garde structurelle : les bornes du domaine n'apparaissent qu'une
    fois, dans `utils/parcelles.py`. Si elles réapparaissent dans `app/api/`
    ou dans le service, ce test le dit."""
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    for chemin in (racine / "app" / "api" / "main.py",
                   racine / "app" / "services" / "parcelles.py"):
        source = chemin.read_text(encoding="utf-8")
        # Les bornes de US-197 et US-225, et le vocabulaire fermé de l'abri.
        for borne in ("NB_RANGS_MIN", "LONGUEUR_MAX", "99", "200.0"):
            assert f"= {borne}" not in source, f"{chemin.name} réécrit une borne"
        assert "ABRIS =" not in source
        assert "TYPES_SOL =" not in source


def test_ca3_aucun_db_query_hors_services(db):
    """[CA3] Rappel d'US-041 sur le fichier que cette US touche."""
    from pathlib import Path

    racine = Path(__file__).resolve().parents[1]
    source = (racine / "app" / "api" / "main.py").read_text(encoding="utf-8")
    bloc = source[source.index("@app.patch(\"/parcelles/{parcelle_id}\")"):]
    bloc = bloc[: bloc.index("@app.patch(\"/potagers/{potager_id}\")")]
    assert "db.query" not in bloc


# ──────────────────────────────────────────────────────────────────────────────
# CA4 — aucune migration
# ──────────────────────────────────────────────────────────────────────────────

def test_ca4_aucune_colonne_ajoutee(db):
    """[CA4] L'US écrit EXACTEMENT les colonnes qu'US-229 affiche : elle n'en
    ajoute aucune, et n'a donc aucune migration à livrer."""
    colonnes = {c.name for c in Parcelle.__table__.columns}
    ecrites = {
        "nom", "nom_normalise", "superficie_m2", "longueur_m", "nb_rangs",
        "exposition", "type_sol", "abri", "paillage", "est_pepiniere", "actif",
    }
    assert ecrites <= colonnes
    assert "largeur_m" not in colonnes  # la largeur se déduit, elle ne se stocke pas


# ──────────────────────────────────────────────────────────────────────────────
# CA5, CA11 — le même refus que le compagnon, mot pour mot
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "champ_web,valeur,champ_bot",
    [
        ("nb_rangs", 150, "rangs"),
        ("longueur_m", 250.0, "longueur"),
        ("abri", "igloo", "abri"),
    ],
)
def test_ca5_ca11_valeur_hors_borne_recoit_le_message_du_compagnon(
    client, db, champ_web, valeur, champ_bot
):
    """[CA5, CA11] Les attributs `min`/`max` de la maquette sont un confort de
    frappe, JAMAIS la règle : un navigateur qui les ignore se heurte au même
    refus que le compagnon — et au même texte."""
    user, potager, parcelle = _potager(db)

    resp = client.patch(
        f"/parcelles/{parcelle.id}", json={champ_web: valeur}, headers=_headers(user)
    )
    assert resp.status_code == 400
    message_web = resp.json()["detail"]["message"]
    # [E5] Le serveur nomme le champ fautif, pour que l'écran pose le message
    # SOUS lui plutôt qu'en haut de la carte.
    assert resp.json()["detail"]["champ"] == champ_web

    with pytest.raises(ValueError) as refus_bot:
        update_parcelle(db, "planche_centrale", potager_id=potager.id,
                        **{champ_bot: str(valeur)})

    assert message_web == str(refus_bot.value)
    # [CA5] Et rien n'a bougé en base.
    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert (relue.nb_rangs, relue.longueur_m, relue.abri) == (7, 6.0, None)


def test_ca11_meme_correction_par_les_deux_chemins_meme_etat(client, db):
    """[CA11] Web et compagnon produisent le même état en base."""
    user, potager, parcelle = _potager(db)
    jumelle = create_parcelle(db, "planche_jumelle", superficie_m2=12.0,
                              potager_id=potager.id)
    jumelle.longueur_m = 6.0
    jumelle.nb_rangs = 7
    db.commit()

    client.patch(f"/parcelles/{parcelle.id}",
                 json={"nb_rangs": 9, "longueur_m": 8.5}, headers=_headers(user))
    update_parcelle(db, "planche_jumelle", potager_id=potager.id,
                    rangs="9", longueur="8,5")

    db.expire_all()
    a, b = db.get(Parcelle, parcelle.id), db.get(Parcelle, jumelle.id)
    assert (a.nb_rangs, a.longueur_m) == (b.nb_rangs, b.longueur_m) == (9, 8.5)


# ──────────────────────────────────────────────────────────────────────────────
# CA6 — « Non renseigné » écrit NULL, ni "" ni false
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "champ", ["type_sol", "abri", "paillage", "nb_rangs", "longueur_m"]
)
def test_ca6_non_renseigne_ecrit_bien_null(client, db, champ):
    """[CA6, E2] Le choix « Non renseigné » remet la colonne à NULL — ce qui
    n'est ni une chaîne vide, ni `false` : le silence ne devient jamais une
    déclaration (US-181 / C4)."""
    user, potager, parcelle = _potager(db)
    # On part d'une parcelle entièrement renseignée.
    update_parcelle(db, "planche_centrale", potager_id=potager.id,
                    type_sol="Limoneux", abri="serre", paillage="true")

    resp = client.patch(
        f"/parcelles/{parcelle.id}", json={champ: None}, headers=_headers(user)
    )

    assert resp.status_code == 200
    assert resp.json()[champ] is None
    db.expire_all()
    valeur = getattr(db.get(Parcelle, parcelle.id),
                     {"nb_rangs": "nb_rangs", "longueur_m": "longueur_m"}.get(champ, champ))
    assert valeur is None
    assert valeur is not False
    assert valeur != ""


def test_ca6_paillage_non_reste_une_declaration(client, db):
    """[E2, US-181] « Non » et « Non renseigné » ne se confondent pas."""
    user, potager, parcelle = _potager(db)

    client.patch(f"/parcelles/{parcelle.id}", json={"paillage": False},
                 headers=_headers(user))
    db.expire_all()
    assert db.get(Parcelle, parcelle.id).paillage is False

    client.patch(f"/parcelles/{parcelle.id}", json={"paillage": None},
                 headers=_headers(user))
    db.expire_all()
    assert db.get(Parcelle, parcelle.id).paillage is None


def test_ca6_abri_aucun_n_est_pas_l_absence_d_abri(client, db):
    """[E2, US-181] « Aucun » = le jardinier déclare le plein air. NULL = la
    question n'a jamais été posée."""
    user, potager, parcelle = _potager(db)

    client.patch(f"/parcelles/{parcelle.id}", json={"abri": "Aucun"},
                 headers=_headers(user))
    db.expire_all()
    assert db.get(Parcelle, parcelle.id).abri == "aucun"


# ──────────────────────────────────────────────────────────────────────────────
# E7, E8, E9 — renommage, bascule pépinière, passage en inactive
# ──────────────────────────────────────────────────────────────────────────────

def test_e7_renommer_passe_par_le_renommage_existant(client, db):
    """[E7, CA2] Le renommage reste celui d'US-006 : les événements suivent la
    parcelle, le nom normalisé reste unique par potager."""
    user, potager, parcelle = _potager(db)
    db.add(Evenement(type_action="semis", culture="carotte", parcelle_id=parcelle.id,
                     potager_id=potager.id))
    db.commit()

    resp = client.patch(f"/parcelles/{parcelle.id}",
                        json={"nom": "Planche du milieu"}, headers=_headers(user))

    assert resp.status_code == 200
    assert resp.json()["nom"] == "Planche du milieu"
    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert relue.nom_normalise == "planchedumilieu"
    assert db.query(Evenement).filter(Evenement.parcelle_id == parcelle.id).count() == 1


def test_e7_nom_deja_pris_est_refuse_en_nommant_le_conflit(client, db):
    user, potager, parcelle = _potager(db)
    create_parcelle(db, "Planche du fond", potager_id=potager.id)

    resp = client.patch(f"/parcelles/{parcelle.id}",
                        json={"nom": "planche du fond"}, headers=_headers(user))

    assert resp.status_code == 400
    assert "Planche du fond" in resp.json()["detail"]["message"]
    assert resp.json()["detail"]["champ"] == "nom"
    db.expire_all()
    assert db.get(Parcelle, parcelle.id).nom == "planche_centrale"


def test_e9_passer_en_inactive_reprend_le_retrait_d_us009(client, db):
    """[E9, CA2] `actif=false` n'est pas une colonne à écrire : c'est le retrait
    d'US-009, qui réaffecte les gestes rattachés en « Non localisé »."""
    user, potager, parcelle = _potager(db)
    db.add(Evenement(type_action="semis", culture="carotte", parcelle_id=parcelle.id,
                     potager_id=potager.id))
    db.commit()

    resp = client.patch(f"/parcelles/{parcelle.id}", json={"actif": False},
                        headers=_headers(user))

    assert resp.status_code == 200
    assert resp.json()["actif"] is False
    db.expire_all()
    assert db.get(Parcelle, parcelle.id).actif is False
    assert db.query(Evenement).filter(Evenement.parcelle_id == parcelle.id).count() == 0
    # [E9] La conséquence est DITE, pas seulement subie.
    assert any("Non localisé" in m for m in resp.json()["modifications"])


def test_e8_basculer_en_pepiniere_est_dit(client, db):
    """[E8] Basculer une parcelle en pépinière change son traitement dans le
    calcul des semis en pleine terre — l'API le dit dans ses modifications."""
    user, potager, parcelle = _potager(db)

    resp = client.patch(f"/parcelles/{parcelle.id}", json={"est_pepiniere": True},
                        headers=_headers(user))

    assert resp.status_code == 200
    assert resp.json()["est_pepiniere"] is True
    assert any("épinière" in m for m in resp.json()["modifications"])


# ──────────────────────────────────────────────────────────────────────────────
# E4, CA13, CA14 — un seul appel, rien à moitié, rien d'écrasé
# ──────────────────────────────────────────────────────────────────────────────

def test_ca13_un_champ_fautif_n_ecrit_aucun_des_autres(client, db):
    """[CA13, E5] Une valeur refusée au milieu du lot ne laisse pas derrière
    elle les champs déjà écrits avant elle."""
    user, potager, parcelle = _potager(db)

    resp = client.patch(
        f"/parcelles/{parcelle.id}",
        json={"type_sol": "Argileux", "exposition": "Est", "nb_rangs": 150},
        headers=_headers(user),
    )

    assert resp.status_code == 400
    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert relue.type_sol is None
    assert relue.exposition == "Sud"
    assert relue.nb_rangs == 7


def test_ca14_un_champ_non_transmis_n_est_pas_ecrase(client, db):
    """[CA14, E4] Deux modifications concurrentes : la seconde n'écrase pas
    silencieusement les champs qu'elle n'a pas touchés. E4 le garantit par
    construction — un champ absent du corps n'est pas transmis, et `null` ne
    veut PAS dire « non touché »."""
    user, potager, parcelle = _potager(db)

    client.patch(f"/parcelles/{parcelle.id}", json={"type_sol": "Sableux"},
                 headers=_headers(user))
    client.patch(f"/parcelles/{parcelle.id}", json={"nb_rangs": 9},
                 headers=_headers(user))

    db.expire_all()
    relue = db.get(Parcelle, parcelle.id)
    assert relue.type_sol == "Sableux"   # la seconde écriture ne l'a pas effacé
    assert relue.nb_rangs == 9


def test_e4_corps_vide_est_refuse(client, db):
    user, potager, parcelle = _potager(db)
    resp = client.patch(f"/parcelles/{parcelle.id}", json={}, headers=_headers(user))
    assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────────────────────
# E3, CA9 — la largeur se recalcule, elle ne se saisit pas
# ──────────────────────────────────────────────────────────────────────────────

def test_e3_largeur_recalculee_a_l_enregistrement(client, db):
    """[E3, CA2 d'US-229] La largeur n'est pas saisissable : elle se déduit, et
    la réponse la porte déjà déduite pour que l'écran n'ait rien à recalculer."""
    user, potager, parcelle = _potager(db)

    resp = client.patch(f"/parcelles/{parcelle.id}", json={"longueur_m": 4.0},
                        headers=_headers(user))

    assert resp.json()["largeur_m"] == pytest.approx(3.0)  # 12 m² ÷ 4 m
    assert resp.json()["largeur_incoherente"] is False


def test_e3_largeur_absurde_est_signalee_jamais_corrigee(client, db):
    """[US-225 / CA7] On dit que la valeur est à vérifier, on ne corrige aucune
    des deux."""
    user, potager, parcelle = _potager(db)

    resp = client.patch(f"/parcelles/{parcelle.id}", json={"longueur_m": 150.0},
                        headers=_headers(user))

    assert resp.json()["longueur_m"] == pytest.approx(150.0)
    assert resp.json()["largeur_incoherente"] is True
    assert any("⚠️" in m for m in resp.json()["modifications"])


# ──────────────────────────────────────────────────────────────────────────────
# CA12 — visible par le compagnon sans délai
# ──────────────────────────────────────────────────────────────────────────────

def test_ca12_modification_web_visible_par_le_compagnon(client, db):
    """[CA12] Aucun cache à invalider à la main : les deux chemins lisent la
    même table."""
    user, potager, parcelle = _potager(db)

    client.patch(f"/parcelles/{parcelle.id}", json={"nb_rangs": 4},
                 headers=_headers(user))

    from utils.parcelles import resolve_parcelle
    db.expire_all()
    vue_compagnon = resolve_parcelle(db, "planche centrale", potager_id=potager.id)
    assert vue_compagnon.nb_rangs == 4


# ──────────────────────────────────────────────────────────────────────────────
# Vocabulaire fermé du type de sol
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("dit,stocke", [
    ("argileux", "Argileux"), ("ARGILE", "Argileux"), ("sablonneux", "Sableux"),
    ("humifère", "Humifère"), ("Limoneux", "Limoneux"),
])
def test_type_sol_normalise_vers_le_vocabulaire_ferme(dit, stocke):
    assert normaliser_type_sol(dit) == stocke


def test_type_sol_hors_vocabulaire_est_refuse_en_disant_le_vocabulaire():
    with pytest.raises(ValueError) as e:
        normaliser_type_sol("béton")
    assert "argileux" in str(e.value)


# ──────────────────────────────────────────────────────────────────────────────
# Scénario Gherkin
# ──────────────────────────────────────────────────────────────────────────────

def test_gherkin_corriger_le_sol_et_les_rangs_en_un_appel(client, db):
    """Given planche_centrale n'a pas de type de sol et déclare 7 rangs
    When je choisis « Argileux » et je passe le nombre de rangs à 8
    Then la fiche repasse en lecture avec « Argileux » et « 8 »"""
    user, potager, parcelle = _potager(db)
    assert parcelle.type_sol is None

    resp = client.patch(
        f"/parcelles/{parcelle.id}",
        json={"type_sol": "Argileux", "nb_rangs": 8},
        headers=_headers(user),
    )

    assert resp.status_code == 200
    body = resp.json()
    assert (body["type_sol"], body["nb_rangs"]) == ("Argileux", 8)
    # [CA9] L'en-tête pourra dire « N rangs occupés sur 8 » sans recharger.
    assert body["nb_rangs"] == 8


def test_gherkin_rangs_hors_borne_ne_perd_pas_les_autres_saisies(client, db):
    """Given je suis en mode édition
    When je saisis 150 dans le nombre de rangs et j'enregistre
    Then le message nomme la borne, et rien n'a été écrit en base"""
    user, potager, parcelle = _potager(db)

    resp = client.patch(
        f"/parcelles/{parcelle.id}",
        json={"type_sol": "Argileux", "nb_rangs": 150},
        headers=_headers(user),
    )

    assert resp.status_code == 400
    assert "1 à 99" in resp.json()["detail"]["message"]
    assert resp.json()["detail"]["champ"] == "nb_rangs"
    db.expire_all()
    assert db.get(Parcelle, parcelle.id).type_sol is None
