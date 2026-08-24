"""
tests/test_us090_connexion_google_oidc.py — [US-090] Connexion via Google (OIDC)
-------------------------------------------------------------------------------
Couvre CA1 à CA19 côté serveur : disponibilité conditionnelle du connecteur,
flux Authorization Code + PKCE, anti-CSRF/anti-rejeu, validation réelle de
l'id_token contre un JWKS (paire RSA générée à la volée), création et
rattachement de compte, « mot de passe oublié » sur un compte sans mot de
passe, et absence de tout secret dans les journaux.

Aucun appel réseau sortant : le JWKS est injecté dans le cache du module et
l'échange du code est simulé — la validation cryptographique de l'id_token,
elle, est bien exécutée pour de vrai.

CA1, CA2, CA4 (rendu), CA20 (texte de consentement) relèvent de la validation
visuelle de l'écran d'authentification, pas de pytest.
"""
import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.services import auth as svc_auth
from app.services import oauth_google as svc_oauth
from database.db import Base
from database.models import User

CLIENT_ID = "client-test.apps.googleusercontent.com"
CLIENT_SECRET = "secret-test-jamais-en-clair-cote-navigateur"
REDIRECT_URI = "http://localhost:8000/auth/oauth/google/callback"
KID = "cle-de-test-1"
COOKIE_ETAT = "potager_oauth_google"


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def paire_rsa():
    """Paire RSA de test : la privée signe l'id_token, la publique alimente le
    JWKS injecté — la validation de signature s'exécute donc réellement (CA7)."""
    cle_privee = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_privee = cle_privee.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    pem_publique = cle_privee.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")
    jwk_publique = jwk.construct(pem_publique, algorithm="RS256").to_dict()
    jwk_publique = {
        cle: (valeur.decode("ascii") if isinstance(valeur, bytes) else valeur)
        for cle, valeur in jwk_publique.items()
    }
    jwk_publique["kid"] = KID
    jwk_publique["alg"] = "RS256"
    return pem_privee, jwk_publique


@pytest.fixture
def google_configure(monkeypatch, paire_rsa):
    """[CA9] Identifiants Google injectés comme le ferait l'environnement —
    jamais codés en dur dans le module, qui les relit depuis `config`."""
    _, jwk_publique = paire_rsa
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_ID", CLIENT_ID)
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_SECRET", CLIENT_SECRET)
    monkeypatch.setattr(svc_oauth, "GOOGLE_REDIRECT_URIS", [REDIRECT_URI])
    # JWKS pré-chargé et valide une heure : aucun appel réseau sortant.
    monkeypatch.setattr(
        svc_oauth,
        "_jwks_cache",
        {"cles": [jwk_publique], "expire_le": 9_999_999_999.0},
    )
    return CLIENT_ID


@pytest.fixture
def _oauth_engine():
    """Moteur SQLite partagé entre threads (même motif que test_us044)."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db(_oauth_engine):
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_oauth_engine)
    db = SessionLocal()
    yield db
    db.rollback()
    db.close()


@pytest.fixture
def app_client(_oauth_engine, monkeypatch):
    import main

    TestSessionLocal = sessionmaker(bind=_oauth_engine)
    monkeypatch.setattr(main, "SessionLocal", TestSessionLocal)
    main.app.state.limiter.reset()
    with TestClient(main.app) as c:
        yield c


def _id_token(paire_rsa, nonce, *, sub="google-sub-123", email="jardinier@gmail.com",
              email_verified=True, nom="Pierre Dupont", iss="https://accounts.google.com",
              aud=CLIENT_ID, expire_dans=timedelta(minutes=5)):
    """Forge un id_token Google réaliste, signé avec la clé privée de test."""
    pem_privee, _ = paire_rsa
    maintenant = datetime.now(timezone.utc)
    claims = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": nom,
        "nonce": nonce,
        "iat": maintenant,
        "exp": maintenant + expire_dans,
    }
    return jwt.encode(claims, pem_privee, algorithm="RS256", headers={"kid": KID})


def _armer_flux(app_client):
    """Démarre un flux et pose le cookie d'état signé sur le client de test."""
    demande = svc_oauth.preparer_autorisation()
    app_client.cookies.set(COOKIE_ETAT, svc_oauth.signer_etat(demande))
    return demande


def _fragment(reponse):
    """Décode le fragment de l'URL de retour vers la PWA."""
    return {
        cle: valeurs[0]
        for cle, valeurs in parse_qs(urlparse(reponse.headers["location"]).fragment).items()
    }


# ── CA4 — Connecteur masqué si non configuré ───────────────────────────────────

def test_us090_providers_google_masque_si_non_configure(app_client, monkeypatch):
    """[CA4] Sans identifiants Google, le connecteur n'est pas proposé."""
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(svc_oauth, "GOOGLE_REDIRECT_URIS", [])

    resp = app_client.get("/auth/oauth/providers")

    assert resp.status_code == 200
    assert resp.json() == {"google": False}


def test_us090_providers_google_actif_si_configure(app_client, google_configure):
    """[CA4] Identifiants présents → le connecteur est annoncé disponible."""
    assert app_client.get("/auth/oauth/providers").json() == {"google": True}


def test_us090_start_404_si_non_configure(app_client, monkeypatch):
    """[CA4] Le flux lui-même est indisponible, pas en erreur technique."""
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_ID", "")
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_SECRET", "")
    monkeypatch.setattr(svc_oauth, "GOOGLE_REDIRECT_URIS", [])

    assert app_client.get("/auth/oauth/google/start", follow_redirects=False).status_code == 404


def test_us090_ca4_connexion_email_intacte_sans_google(app_client, test_db, monkeypatch):
    """[CA4] Aucun compte Google configuré → la connexion e-mail fonctionne."""
    monkeypatch.setattr(svc_oauth, "GOOGLE_CLIENT_ID", "")
    user = svc_auth.inscrire_utilisateur(test_db, "local@exemple.fr", "motdepasse123")
    user.email_verifie = True
    test_db.commit()

    resp = app_client.post("/auth/login", json={"email": "local@exemple.fr", "mot_de_passe": "motdepasse123"})

    assert resp.status_code == 200
    assert resp.json()["access_token"]


# ── CA5 — Authorization Code + PKCE, secret côté serveur ───────────────────────

def test_us090_ca5_url_autorisation_code_avec_pkce(google_configure):
    """[CA5] response_type=code + challenge S256 ; jamais de flux implicite."""
    demande = svc_oauth.preparer_autorisation()
    params = parse_qs(urlparse(demande.url).query)

    assert params["response_type"] == ["code"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"][0] and params["code_challenge"][0] != demande.code_verifier
    assert "token" not in params["response_type"]
    assert "id_token" not in params["response_type"]


def test_us090_ca5_client_secret_jamais_dans_lurl_ni_le_cookie(google_configure):
    """[CA5] Le secret ne sort pas du serveur : ni URL d'autorisation, ni cookie."""
    demande = svc_oauth.preparer_autorisation()
    cookie = svc_oauth.signer_etat(demande)

    assert CLIENT_SECRET not in demande.url
    assert CLIENT_SECRET not in cookie


def test_us090_ca5_echange_du_code_cote_serveur_avec_verifier(google_configure):
    """[CA5] L'échange est un POST serveur portant client_secret ET code_verifier."""
    class _Reponse:
        status_code = 200

        @staticmethod
        def json():
            return {"id_token": "jeton-simule"}

    with patch("app.services.oauth_google.httpx.post", return_value=_Reponse()) as post:
        svc_oauth.echanger_code_contre_jetons("le-code", "le-verifier", REDIRECT_URI)

    donnees = post.call_args.kwargs["data"]
    assert donnees["grant_type"] == "authorization_code"
    assert donnees["client_secret"] == CLIENT_SECRET
    assert donnees["code_verifier"] == "le-verifier"
    assert post.call_args.args[0] == svc_oauth.TOKEN_ENDPOINT


def test_us090_ca10_scopes_limites_et_pas_dacces_hors_ligne(google_configure):
    """[CA10] `openid email profile` uniquement, aucun offline access demandé."""
    params = parse_qs(urlparse(svc_oauth.preparer_autorisation().url).query)

    assert params["scope"] == ["openid email profile"]
    assert "access_type" not in params


# ── CA6 — state / nonce / code_verifier ────────────────────────────────────────

def test_us090_ca6_state_et_nonce_aleatoires_a_chaque_demande(google_configure):
    """[CA6] Deux demandes ne partagent ni state, ni nonce, ni code_verifier."""
    a, b = svc_oauth.preparer_autorisation(), svc_oauth.preparer_autorisation()

    assert a.state != b.state and len(a.state) >= 32
    assert a.nonce != b.nonce
    assert a.code_verifier != b.code_verifier


def test_us090_ca6_cookie_detat_signe_et_relu(google_configure):
    """[CA6] Le cookie signé restitue exactement les secrets de la demande."""
    demande = svc_oauth.preparer_autorisation()

    etat = svc_oauth.lire_etat(svc_oauth.signer_etat(demande), demande.state)

    assert etat["code_verifier"] == demande.code_verifier
    assert etat["nonce"] == demande.nonce
    assert etat["redirect_uri"] == REDIRECT_URI


def test_us090_ca6_state_ne_correspondant_pas_au_cookie_rejete(google_configure):
    """[CA6] Anti-CSRF : un state forgé ne passe pas."""
    demande = svc_oauth.preparer_autorisation()

    with pytest.raises(svc_oauth.EtatOAuthInvalideError):
        svc_oauth.lire_etat(svc_oauth.signer_etat(demande), "state-attaquant")


def test_us090_ca6_cookie_absent_ou_altere_rejete(google_configure):
    """[CA6] Cookie manquant ou signature cassée → même refus, sans détail."""
    demande = svc_oauth.preparer_autorisation()
    altere = svc_oauth.signer_etat(demande)[:-3] + "aaa"

    with pytest.raises(svc_oauth.EtatOAuthInvalideError):
        svc_oauth.lire_etat(None, demande.state)
    with pytest.raises(svc_oauth.EtatOAuthInvalideError):
        svc_oauth.lire_etat(altere, demande.state)


def test_us090_ca6_cookie_httponly_samesite_et_jamais_localstorage(app_client, google_configure):
    """[CA6] Le cookie d'état est HttpOnly + SameSite — inaccessible au JS."""
    resp = app_client.get("/auth/oauth/google/start", follow_redirects=False)

    assert resp.status_code == 302
    entete = resp.headers["set-cookie"]
    assert entete.startswith(f"{COOKIE_ETAT}=")
    assert "httponly" in entete.lower()
    assert "samesite=lax" in entete.lower()
    # Ni le code_verifier ni le nonce ne sont exposés en clair à la page.
    assert "code_verifier" not in resp.headers["location"]


# ── CA7 — Validation de l'id_token ─────────────────────────────────────────────

def test_us090_ca7_id_token_valide_accepte(google_configure, paire_rsa):
    """[CA7] Signature JWKS, iss, aud, exp et nonce vérifiés → profil extrait."""
    profil = svc_oauth.valider_id_token(_id_token(paire_rsa, "nonce-1"), "nonce-1")

    assert profil.sub == "google-sub-123"
    assert profil.email == "jardinier@gmail.com"
    assert profil.email_verifie is True
    assert profil.nom == "Pierre Dupont"


def test_us090_ca7_signature_invalide_refusee(google_configure, paire_rsa):
    """[CA7] Un jeton signé par une autre clé est rejeté."""
    autre = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_autre = autre.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("ascii")
    maintenant = datetime.now(timezone.utc)
    jeton = jwt.encode(
        {"iss": "https://accounts.google.com", "aud": CLIENT_ID, "sub": "x",
         "nonce": "n", "iat": maintenant, "exp": maintenant + timedelta(minutes=5)},
        pem_autre, algorithm="RS256", headers={"kid": KID},
    )

    with pytest.raises(svc_oauth.IdTokenInvalideError):
        svc_oauth.valider_id_token(jeton, "n")


def test_us090_ca7_audience_etrangere_refusee(google_configure, paire_rsa):
    """[CA7] Un id_token émis pour une autre application est rejeté."""
    with pytest.raises(svc_oauth.IdTokenInvalideError):
        svc_oauth.valider_id_token(_id_token(paire_rsa, "n", aud="autre-app"), "n")


def test_us090_ca7_emetteur_inattendu_refuse(google_configure, paire_rsa):
    """[CA7] `iss` hors des deux valeurs émises par Google → rejet."""
    with pytest.raises(svc_oauth.IdTokenInvalideError):
        svc_oauth.valider_id_token(_id_token(paire_rsa, "n", iss="https://evil.example"), "n")


def test_us090_ca7_jeton_expire_refuse(google_configure, paire_rsa):
    """[CA7] `exp` dépassé → rejet."""
    with pytest.raises(svc_oauth.IdTokenInvalideError):
        svc_oauth.valider_id_token(_id_token(paire_rsa, "n", expire_dans=timedelta(minutes=-5)), "n")


def test_us090_ca6_nonce_different_refuse(google_configure, paire_rsa):
    """[CA6/CA7] Anti-rejeu : un id_token portant un autre nonce est rejeté."""
    with pytest.raises(svc_oauth.IdTokenInvalideError):
        svc_oauth.valider_id_token(_id_token(paire_rsa, "nonce-emis"), "nonce-attendu")


def test_us090_ca7_jwks_cache_respecte_le_cache_control(google_configure):
    """[CA7] La durée de cache des clés suit l'en-tête Cache-Control de Google."""
    assert svc_oauth._duree_cache("public, max-age=21600, must-revalidate") == 21600
    assert svc_oauth._duree_cache(None) == svc_oauth._JWKS_TTL_DEFAUT
    assert svc_oauth._duree_cache("no-store") == svc_oauth._JWKS_TTL_DEFAUT


# ── CA8 — Liste blanche des redirect_uri ───────────────────────────────────────

def test_us090_ca8_redirect_uri_hors_liste_blanche_rejetee(google_configure):
    """[CA8] Toute URI absente de la configuration est refusée."""
    assert svc_oauth.valider_redirect_uri(REDIRECT_URI) == REDIRECT_URI

    with pytest.raises(svc_oauth.RedirectUriNonAutoriseeError):
        svc_oauth.valider_redirect_uri("https://evil.example/callback")
    with pytest.raises(svc_oauth.RedirectUriNonAutoriseeError):
        # Même hôte, chemin différent : la comparaison est stricte.
        svc_oauth.valider_redirect_uri("http://localhost:8000/autre")


# ── CA9 — Identifiants issus de l'environnement ────────────────────────────────

def test_us090_ca9_identifiants_absents_par_defaut_en_test():
    """[CA9] Aucun identifiant en dur : l'environnement de test n'en a aucun."""
    import config

    assert config.GOOGLE_CLIENT_ID == ""
    assert config.GOOGLE_CLIENT_SECRET == ""
    assert svc_oauth.est_configure() is False


# ── CA11 / CA12 / CA13 / CA14 — Compte, création et rattachement ───────────────

def test_us090_ca11_premiere_connexion_cree_le_compte_sans_mot_de_passe(test_db):
    """[CA11] Compte créé, e-mail vérifié, aucun mot de passe."""
    resultat = svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-1", email="Jardinier@Gmail.com", email_verifie=True, nom="Pierre Dupont",
    )

    assert resultat.evenement == svc_auth.FEDERATION_CREATION
    assert resultat.user.email == "jardinier@gmail.com"
    assert resultat.user.mot_de_passe_hash is None
    assert resultat.user.email_verifie is True
    assert resultat.user.google_sub == "sub-1"


def test_us090_ca11_aucun_email_brevo_a_la_creation_verifiee(app_client, google_configure, paire_rsa, test_db):
    """[CA11] Parcours complet : aucun e-mail de vérification n'est envoyé."""
    demande = _armer_flux(app_client)
    jeton = _id_token(paire_rsa, demande.nonce)

    with patch("main.svc_email.envoyer_email_verification") as envoi, \
         patch.object(svc_oauth, "echanger_code_contre_jetons", return_value={"id_token": jeton}):
        resp = app_client.get(
            f"/auth/oauth/google/callback?code=le-code&state={demande.state}",
            follow_redirects=False,
        )

    envoi.assert_not_called()
    fragment = _fragment(resp)
    assert fragment["evenement"] == svc_auth.FEDERATION_CREATION
    assert svc_auth.decoder_access_token(fragment["access_token"])["sub"]
    assert test_db.query(User).filter(User.email == "jardinier@gmail.com").one().google_sub


def test_us090_ca12_rattachement_automatique_sur_email_verifie(test_db):
    """[CA12] Compte local existant + e-mail attesté → rattachement silencieux."""
    local = svc_auth.inscrire_utilisateur(test_db, "jardinier@gmail.com", "motdepasse123", nom="Pierre")
    local.email_verifie = True
    test_db.commit()

    resultat = svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-2", email="jardinier@gmail.com", email_verifie=True, nom="Pierre Dupont",
    )

    assert resultat.evenement == svc_auth.FEDERATION_RATTACHEMENT
    assert resultat.user.id == local.id
    assert test_db.query(User).count() == 1  # aucun doublon


def test_us090_ca15_les_deux_methodes_coexistent_apres_rattachement(test_db):
    """[CA15] Après rattachement, mot de passe ET Google fonctionnent."""
    local = svc_auth.inscrire_utilisateur(test_db, "jardinier@gmail.com", "motdepasse123")
    local.email_verifie = True
    test_db.commit()
    svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-2", email="jardinier@gmail.com", email_verifie=True, nom=None,
    )

    # Le mot de passe reste valable…
    assert svc_auth.authentifier_utilisateur(test_db, "jardinier@gmail.com", "motdepasse123").id == local.id
    # …et une nouvelle connexion Google retombe sur le même compte.
    suivant = svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-2", email="jardinier@gmail.com", email_verifie=True, nom=None,
    )
    assert suivant.evenement == svc_auth.FEDERATION_CONNEXION
    assert suivant.user.id == local.id
    # Aucune colonne mono-valuée de fournisseur sur le modèle.
    assert not hasattr(User, "auth_provider")


def test_us090_ca13_rattachement_refuse_si_email_non_atteste(test_db):
    """[CA13] E-mail existant non attesté vérifié → pas de rattachement."""
    svc_auth.inscrire_utilisateur(test_db, "jardinier@exemple.fr", "motdepasse123")

    with pytest.raises(svc_auth.RattachementNonVerifieError):
        svc_auth.connecter_ou_creer_via_google(
            test_db, sub="sub-3", email="jardinier@exemple.fr", email_verifie=False, nom=None,
        )

    assert test_db.query(User).filter(User.google_sub == "sub-3").first() is None


def test_us090_ca13_creation_non_verifiee_repasse_par_brevo(app_client, google_configure, paire_rsa, test_db):
    """[CA13] Création avec e-mail non attesté → compte non vérifié + e-mail Brevo."""
    demande = _armer_flux(app_client)
    jeton = _id_token(paire_rsa, demande.nonce, sub="sub-4", email="flou@workspace.fr", email_verified=False)

    with patch("main.svc_email.envoyer_email_verification") as envoi, \
         patch.object(svc_oauth, "echanger_code_contre_jetons", return_value={"id_token": jeton}):
        resp = app_client.get(
            f"/auth/oauth/google/callback?code=le-code&state={demande.state}",
            follow_redirects=False,
        )

    envoi.assert_called_once()
    fragment = _fragment(resp)
    assert fragment == {"info": "verification_requise"}
    assert "access_token" not in fragment
    assert test_db.query(User).filter(User.email == "flou@workspace.fr").one().email_verifie is False


def test_us090_ca14_un_sub_google_ne_sert_quun_seul_compte(test_db):
    """[CA14] Le `sub` est unique — deux connexions retombent sur le même compte."""
    premier = svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-5", email="a@gmail.com", email_verifie=True, nom=None,
    )
    second = svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-5", email="a@gmail.com", email_verifie=True, nom=None,
    )

    assert second.user.id == premier.user.id
    assert second.evenement == svc_auth.FEDERATION_CONNEXION
    assert test_db.query(User).filter(User.google_sub == "sub-5").count() == 1


def test_us090_ca16_deux_adresses_donnent_deux_comptes_distincts(test_db):
    """[CA16] Aucune fusion implicite entre deux adresses différentes."""
    local = svc_auth.inscrire_utilisateur(test_db, "jardinier@exemple.fr", "motdepasse123")
    local.email_verifie = True
    test_db.commit()

    federe = svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-6", email="jardinier@gmail.com", email_verifie=True, nom=None,
    )

    assert federe.user.id != local.id
    assert test_db.query(User).count() == 2
    # Les deux comptes restent fonctionnels, chacun avec sa méthode.
    assert svc_auth.authentifier_utilisateur(test_db, "jardinier@exemple.fr", "motdepasse123").id == local.id
    assert federe.user.mot_de_passe_hash is None


def test_us090_identite_google_sans_email_refusee(test_db):
    """Cas limite : un id_token sans e-mail ne permet pas d'identifier un compte."""
    with pytest.raises(svc_auth.EmailGoogleAbsentError):
        svc_auth.connecter_ou_creer_via_google(test_db, sub="sub-7", email=None, email_verifie=True, nom=None)


# ── CA3 — Échecs et abandons ───────────────────────────────────────────────────

def test_us090_ca3_consentement_refuse_ramene_a_la_connexion(app_client, google_configure, test_db):
    """[CA3] `error=access_denied` (refus, fenêtre fermée, accès révoqué)."""
    resp = app_client.get("/auth/oauth/google/callback?error=access_denied", follow_redirects=False)

    assert resp.status_code == 302
    assert resp.headers["location"].startswith("http://localhost:3000/auth/callback#")
    assert _fragment(resp) == {"erreur": "acces_refuse"}
    assert test_db.query(User).count() == 0


def test_us090_ca3_state_invalide_ramene_a_la_connexion(app_client, google_configure, test_db):
    """[CA3/CA6] Cookie d'état absent → message clair, aucun compte créé."""
    app_client.cookies.clear()
    resp = app_client.get("/auth/oauth/google/callback?code=x&state=y", follow_redirects=False)

    assert _fragment(resp) == {"erreur": "etat_invalide"}
    assert test_db.query(User).count() == 0


def test_us090_ca3_echec_dechange_ramene_a_la_connexion(app_client, google_configure, test_db):
    """[CA3] Google refuse l'échange (accès révoqué, code consommé) → message clair."""
    demande = _armer_flux(app_client)

    with patch.object(
        svc_oauth, "echanger_code_contre_jetons",
        side_effect=svc_oauth.EchangeCodeError("refus"),
    ):
        resp = app_client.get(
            f"/auth/oauth/google/callback?code=le-code&state={demande.state}",
            follow_redirects=False,
        )

    assert _fragment(resp) == {"erreur": "echec_google"}
    assert test_db.query(User).count() == 0


def test_us090_ca3_reseau_indisponible_ne_remonte_pas_derreur_brute(google_configure):
    """[CA3] Une panne réseau devient une erreur métier, pas une trace httpx."""
    import httpx

    with patch("app.services.oauth_google.httpx.post", side_effect=httpx.ConnectError("boom")):
        with pytest.raises(svc_oauth.EchangeCodeError):
            svc_oauth.echanger_code_contre_jetons("code", "verifier", REDIRECT_URI)


def test_us090_ca13_rattachement_refuse_ramene_un_message(app_client, google_configure, paire_rsa, test_db):
    """[CA3/CA13] Le refus de rattachement a son propre message d'écran."""
    svc_auth.inscrire_utilisateur(test_db, "jardinier@exemple.fr", "motdepasse123")
    demande = _armer_flux(app_client)
    jeton = _id_token(paire_rsa, demande.nonce, sub="sub-8", email="jardinier@exemple.fr", email_verified=False)

    with patch.object(svc_oauth, "echanger_code_contre_jetons", return_value={"id_token": jeton}):
        resp = app_client.get(
            f"/auth/oauth/google/callback?code=le-code&state={demande.state}",
            follow_redirects=False,
        )

    assert _fragment(resp) == {"erreur": "email_non_verifie"}


# ── CA10 / CA18 — Jetons applicatifs, rien de Google conservé ──────────────────

def test_us090_ca10_jetons_applicatifs_us044(app_client, google_configure, paire_rsa, test_db):
    """[CA10] La fédération produit les jetons maison, pas ceux de Google."""
    demande = _armer_flux(app_client)
    jeton = _id_token(paire_rsa, demande.nonce, sub="sub-9", email="jetons@gmail.com")

    with patch.object(svc_oauth, "echanger_code_contre_jetons",
                      return_value={"id_token": jeton, "access_token": "google-at", "refresh_token": "google-rt"}):
        resp = app_client.get(
            f"/auth/oauth/google/callback?code=le-code&state={demande.state}",
            follow_redirects=False,
        )

    fragment = _fragment(resp)
    user = test_db.query(User).filter(User.email == "jetons@gmail.com").one()
    assert svc_auth.decoder_access_token(fragment["access_token"])["sub"] == str(user.id)
    assert svc_auth.decoder_refresh_token(fragment["refresh_token"])["sub"] == str(user.id)
    # Aucun jeton Google ne se retrouve dans la réponse ni en base.
    assert "google-at" not in resp.headers["location"]
    assert "google-rt" not in resp.headers["location"]
    assert not [c for c in User.__table__.columns if "token" in c.name and "google" in c.name]


def test_us090_ca18_aucune_revocation_cote_google():
    """[CA18] La déconnexion reste locale : aucun appel de révocation Google."""
    import inspect

    source = inspect.getsource(svc_oauth)
    assert "revoke" not in source
    assert "/revoke" not in inspect.getsource(svc_auth)


# ── CA17 — Mot de passe oublié sur un compte sans mot de passe ─────────────────

def test_us090_ca17_compte_google_recoit_un_lien_de_definition(test_db):
    """[CA17] Un compte sans mot de passe est éligible — en définition initiale."""
    svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-10", email="google-only@gmail.com", email_verifie=True, nom=None,
    )

    resultat = svc_auth.demander_reset_mot_de_passe(test_db, "google-only@gmail.com")

    assert resultat is not None
    token, definition_initiale = resultat
    assert definition_initiale is True
    assert token


def test_us090_ca17_email_oriente_vers_google(test_db):
    """[CA17] Le message reçu parle de Google et de la définition d'un mot de
    passe — jamais d'un compte inexistant."""
    from app.services import email as svc_email

    with patch.object(svc_email, "BREVO_API_KEY", "cle-test"), \
         patch("app.services.email.httpx.post") as post:
        svc_email.envoyer_email_reset_mdp("google-only@gmail.com", "jeton", definition_initiale=True)

    payload = post.call_args.kwargs["json"]
    assert "Google" in payload["htmlContent"]
    assert "mot de passe" in payload["subject"].lower()


def test_us090_ca17_definir_puis_utiliser_un_premier_mot_de_passe(test_db):
    """[CA17] Le lien permet réellement de définir un premier mot de passe."""
    svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-11", email="google-only@gmail.com", email_verifie=True, nom=None,
    )
    token, _ = svc_auth.demander_reset_mot_de_passe(test_db, "google-only@gmail.com")

    svc_auth.reinitialiser_mot_de_passe(test_db, token, "nouveaumotdepasse1")

    user = svc_auth.authentifier_utilisateur(test_db, "google-only@gmail.com", "nouveaumotdepasse1")
    assert user.google_sub == "sub-11"  # les deux méthodes coexistent (CA15)


def test_us090_ca17_compte_telegram_only_reste_hors_perimetre(test_db):
    """[CA17] Un compte Telegram-only (ni mot de passe ni Google) reste ignoré."""
    test_db.add(User(email="telegram@exemple.fr", telegram_chat_id=42))
    test_db.commit()

    assert svc_auth.demander_reset_mot_de_passe(test_db, "telegram@exemple.fr") is None


def test_us090_ca17_reponse_api_reste_generique(app_client, test_db):
    """[CA17] Anti-énumération préservée : même réponse quel que soit le compte."""
    svc_auth.connecter_ou_creer_via_google(
        test_db, sub="sub-12", email="google-only@gmail.com", email_verifie=True, nom=None,
    )

    connu = app_client.post("/auth/mot-de-passe-oublie", json={"email": "google-only@gmail.com"})
    inconnu = app_client.post("/auth/mot-de-passe-oublie", json={"email": "personne@exemple.fr"})

    assert connu.status_code == inconnu.status_code == 200
    assert connu.json() == inconnu.json()


# ── CA19 — Aucun secret dans les journaux ──────────────────────────────────────

def test_us090_ca19_filtre_masque_les_secrets_des_logs_dacces():
    """[CA19] Le code d'autorisation est masqué avant écriture dans les logs."""
    import main

    filtre = main._FiltreSecretsOAuth()
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, "", 0,
        '%s - "%s %s HTTP/%s" %d',
        ("127.0.0.1", "GET", "/auth/oauth/google/callback?code=4/0AX-SECRET&state=abc", "1.1", 302),
        None,
    )

    filtre.filter(record)

    assert "4/0AX-SECRET" not in record.getMessage()
    assert "code=[masqué]" in record.getMessage()
    assert "state=abc" in record.getMessage()  # non sensible, conservé pour le diagnostic


def test_us090_ca19_aucun_secret_dans_les_logs_du_parcours(
    app_client, google_configure, paire_rsa, test_db, caplog
):
    """[CA19] Un parcours complet ne logue ni le code, ni l'id_token, ni le verifier."""
    demande = _armer_flux(app_client)
    jeton = _id_token(paire_rsa, demande.nonce, sub="sub-13", email="logs@gmail.com")

    with caplog.at_level(logging.DEBUG, logger="potager"), \
         patch.object(svc_oauth, "echanger_code_contre_jetons", return_value={"id_token": jeton}):
        app_client.get(
            f"/auth/oauth/google/callback?code=code-tres-secret&state={demande.state}",
            follow_redirects=False,
        )

    assert "code-tres-secret" not in caplog.text
    assert jeton not in caplog.text
    assert demande.code_verifier not in caplog.text
    assert CLIENT_SECRET not in caplog.text


def test_us090_ca19_evenement_journalise_avec_user_id_et_fournisseur(test_db, caplog):
    """[CA19] Chaque événement d'authentification est tracé : user_id + fournisseur."""
    with caplog.at_level(logging.INFO, logger="potager"):
        resultat = svc_auth.connecter_ou_creer_via_google(
            test_db, sub="sub-14", email="trace@gmail.com", email_verifie=True, nom=None,
        )

    assert f"user_id={resultat.user.id}" in caplog.text
    assert "fournisseur=google" in caplog.text
    assert "trace@gmail.com" not in caplog.text
