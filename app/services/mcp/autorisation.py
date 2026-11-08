"""
app/services/mcp/autorisation.py — Serveur d'autorisation OAuth 2.1 du canal MCP [US-290]
==========================================================================================

Ce que demandent les connecteurs des assistants grand public (Claude, ChatGPT, Le Chat) :

- métadonnées du serveur d'autorisation (RFC 8414) et de la ressource protégée (RFC 9728) ;
- enregistrement dynamique des clients (RFC 7591) ;
- code d'autorisation + PKCE S256 obligatoire (OAuth 2.1), jeton de rafraîchissement
  à usage unique (rotation) ;
- révocation (RFC 7009).

Le jardinier se connecte avec SON compte (e-mail ou Google) dans la PWA, qui affiche
la page de consentement (CA2, CA3). Entre `/oauth/authorize` et ce consentement, la
demande voyage SIGNÉE (JWT, 15 min) : aucune table de demandes en attente.

Jetons opaques, jamais des JWT : un jeton révoqué ou un compte supprimé doit couper
l'accès dès l'appel suivant (CA8), ce qu'un JWT autoportant ne permet pas. Seule
l'empreinte SHA-256 de chaque secret (jeton, code, secret client) est stockée.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import config
from app.config import JWT_ALGORITHM, JWT_SECRET
from app.services import potager_actif as svc_potager_actif
from database.models import (
    McpAutorisation, McpClient, McpCodeAutorisation, McpJeton, User,
)

log = logging.getLogger("potager")

# ── Vocabulaire ───────────────────────────────────────────────────────────────
PORTEE_LECTURE = "lecture"
PORTEE_ECRITURE = "ecriture"
SCOPE_LECTURE = "potager.lecture"
SCOPE_ECRITURE = "potager.ecriture"
SCOPES_SUPPORTES = [SCOPE_LECTURE, SCOPE_ECRITURE]

TYPE_OAUTH = "oauth"
TYPE_PERSONNEL = "personnel"

JETON_ACCES = "acces"
JETON_RAFRAICHISSEMENT = "rafraichissement"
JETON_PERSONNEL = "personnel"

#: Préfixes lisibles : un jeton collé au mauvais endroit se reconnaît à l'œil.
_PREFIXES = {JETON_ACCES: "mcpa_", JETON_RAFRAICHISSEMENT: "mcpr_", JETON_PERSONNEL: "mcpp_"}
_PREFIXE_CODE = "mcpc_"

METHODES_AUTH_CLIENT = ("none", "client_secret_post", "client_secret_basic")
_TYPE_DEMANDE = "mcp_demande"
_DUREE_DEMANDE = timedelta(minutes=15)
_DUREE_CODE = timedelta(minutes=10)
_HOTES_BOUCLE = {"localhost", "127.0.0.1", "[::1]", "::1"}
_NOM_CLIENT_DEFAUT = "Assistant sans nom"
_MAX_REDIRECT_URIS = 10


class ErreurOAuth(Exception):
    """Une erreur OAuth normalisée (`error`, `error_description`) et son statut HTTP."""

    def __init__(self, code: str, description: str, statut: int = 400):
        super().__init__(description)
        self.code = code
        self.description = description
        self.statut = statut

    def corps(self) -> dict:
        return {"error": self.code, "error_description": self.description}


class ErreurDemandeSansRetour(ErreurOAuth):
    """Client inconnu ou adresse de retour invalide : on ne redirige JAMAIS vers une
    adresse non vérifiée (RFC 6749 §4.1.2.1) ; l'erreur s'affiche au jardinier."""


class ErreurDemandeAvecRetour(ErreurOAuth):
    """Demande invalide mais adresse de retour sûre : l'erreur repart chez le client."""

    def __init__(self, code: str, description: str, redirect_uri: str, state: Optional[str]):
        super().__init__(code, description)
        self.redirection = _ajouter_parametres(
            redirect_uri, {"error": code, "error_description": description, "state": state},
        )


class ConsentementInvalideError(ValueError):
    """Le jardinier a validé un consentement incohérent (aucun potager, potager étranger)."""


@dataclass(frozen=True)
class Connexion:
    """[CA4] Ce qu'un jeton valide autorise, relu à CHAQUE appel."""
    autorisation_id: int
    user_id: int
    client: str
    portee: str
    potager_ids: tuple[int, ...]

    @property
    def ecriture(self) -> bool:
        return self.portee == PORTEE_ECRITURE


# ── Outils internes ───────────────────────────────────────────────────────────
def _maintenant() -> datetime:
    """Horloge unique du canal : UTC, sans fuseau (colonnes TIMESTAMP)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def empreinte(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _nouveau_secret(prefixe: str = "") -> str:
    return prefixe + secrets.token_urlsafe(32)


def url_ressource() -> str:
    """L'URL canonique du serveur MCP — celle que le jardinier colle dans son assistant."""
    return f"{config.MCP_URL_PUBLIQUE}/mcp"


def emetteur() -> str:
    return config.MCP_URL_PUBLIQUE


def _ajouter_parametres(url: str, parametres: dict) -> str:
    """Ajoute des paramètres à la query d'une URL en conservant ceux qu'elle porte déjà."""
    morceaux = urlsplit(url)
    query = parse_qsl(morceaux.query, keep_blank_values=True)
    query += [(k, v) for k, v in parametres.items() if v is not None]
    return urlunsplit((morceaux.scheme, morceaux.netloc, morceaux.path, urlencode(query), morceaux.fragment))


def portee_vers_scope(portee: str) -> str:
    return f"{SCOPE_LECTURE} {SCOPE_ECRITURE}" if portee == PORTEE_ECRITURE else SCOPE_LECTURE


# ── Métadonnées (RFC 8414, RFC 9728) ──────────────────────────────────────────
def metadonnees_serveur_autorisation() -> dict:
    base = emetteur()
    return {
        "issuer": base,
        "authorization_endpoint": f"{base}/oauth/authorize",
        "token_endpoint": f"{base}/oauth/token",
        "registration_endpoint": f"{base}/oauth/register",
        "revocation_endpoint": f"{base}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": list(METHODES_AUTH_CLIENT),
        "revocation_endpoint_auth_methods_supported": list(METHODES_AUTH_CLIENT),
        "scopes_supported": SCOPES_SUPPORTES,
        "service_documentation": f"{base}/",
    }


def metadonnees_ressource_protegee() -> dict:
    return {
        "resource": url_ressource(),
        "resource_name": "Assistant Potager",
        "authorization_servers": [emetteur()],
        "scopes_supported": SCOPES_SUPPORTES,
        "bearer_methods_supported": ["header"],
    }


# ── Enregistrement dynamique des clients (RFC 7591) ───────────────────────────
def _redirect_uri_acceptable(uri: str) -> bool:
    """https partout ; http seulement en boucle locale (MCP Inspector, Claude Code)."""
    if not isinstance(uri, str) or len(uri) > 2000:
        return False
    morceaux = urlsplit(uri)
    if morceaux.fragment or not morceaux.netloc:
        return False
    if morceaux.scheme == "https":
        return True
    return morceaux.scheme == "http" and (morceaux.hostname or "") in {h.strip("[]") for h in _HOTES_BOUCLE}


def enregistrer_client(db: Session, donnees: dict) -> dict:
    """[CA2] Enregistre un client OAuth et rend la réponse RFC 7591.

    Un client public (`none`) s'authentifie par PKCE seul ; un client confidentiel
    reçoit un secret, rendu UNE fois. Sans méthode indiquée, la RFC prévoit
    `client_secret_basic`.
    """
    if not isinstance(donnees, dict):
        raise ErreurOAuth("invalid_client_metadata", "Corps JSON attendu")
    uris = donnees.get("redirect_uris")
    if not isinstance(uris, list) or not uris or len(uris) > _MAX_REDIRECT_URIS:
        raise ErreurOAuth("invalid_redirect_uri", "redirect_uris : une à dix adresses de retour attendues")
    if not all(_redirect_uri_acceptable(u) for u in uris):
        raise ErreurOAuth("invalid_redirect_uri", "Adresse de retour refusée : https, ou http en boucle locale")

    types_reponse = donnees.get("response_types") or ["code"]
    types_octroi = donnees.get("grant_types") or ["authorization_code", "refresh_token"]
    if not set(types_reponse) <= {"code"}:
        raise ErreurOAuth("invalid_client_metadata", "Seul response_type=code est pris en charge")
    if not set(types_octroi) <= {"authorization_code", "refresh_token"}:
        raise ErreurOAuth("invalid_client_metadata", "grant_types : authorization_code et refresh_token seulement")

    methode = donnees.get("token_endpoint_auth_method") or "client_secret_basic"
    if methode not in METHODES_AUTH_CLIENT:
        raise ErreurOAuth("invalid_client_metadata", f"token_endpoint_auth_method non pris en charge : {methode}")

    nom = str(donnees.get("client_name") or "").strip()[:120] or _NOM_CLIENT_DEFAUT
    client_id = "mcp_" + secrets.token_urlsafe(18)
    secret = _nouveau_secret("mcps_") if methode != "none" else None

    client = McpClient(
        client_id=client_id, nom=nom, redirect_uris=list(uris), methode_auth_jeton=methode,
        secret_empreinte=empreinte(secret) if secret else None, cree_le=_maintenant(),
    )
    db.add(client)
    db.commit()
    log.info("[US-290] Client MCP enregistré : %s (%s, %s)", nom, client_id, methode)

    reponse = {
        "client_id": client_id,
        "client_id_issued_at": int(datetime.now(timezone.utc).timestamp()),
        "client_name": nom,
        "redirect_uris": list(uris),
        "grant_types": list(types_octroi),
        "response_types": list(types_reponse),
        "token_endpoint_auth_method": methode,
    }
    if secret:
        reponse["client_secret"] = secret
        reponse["client_secret_expires_at"] = 0
    return reponse


def _client(db: Session, client_id: Optional[str]) -> Optional[McpClient]:
    if not client_id:
        return None
    return db.query(McpClient).filter(McpClient.client_id == client_id).first()


def _retour_enregistre(client: McpClient, redirect_uri: str) -> bool:
    """Correspondance exacte ; en boucle locale, le port peut varier (RFC 8252 §7.3)."""
    if redirect_uri in (client.redirect_uris or []):
        return True
    demande = urlsplit(redirect_uri)
    if demande.scheme != "http" or (demande.hostname or "") not in {h.strip("[]") for h in _HOTES_BOUCLE}:
        return False
    for enregistre in client.redirect_uris or []:
        e = urlsplit(enregistre)
        if (e.scheme, e.hostname, e.path, e.query) == (demande.scheme, demande.hostname, demande.path, demande.query):
            return True
    return False


def authentifier_client(db: Session, client_id: Optional[str], secret: Optional[str]) -> McpClient:
    """[CA2] Le client à l'endpoint de jeton : public (PKCE seul) ou confidentiel (secret)."""
    client = _client(db, client_id)
    if client is None:
        raise ErreurOAuth("invalid_client", "Client inconnu", statut=401)
    if client.methode_auth_jeton != "none":
        if not secret or not client.secret_empreinte or not hmac.compare_digest(
            empreinte(secret), client.secret_empreinte,
        ):
            raise ErreurOAuth("invalid_client", "Authentification du client échouée", statut=401)
    return client


# ── Demande d'autorisation (/oauth/authorize) ─────────────────────────────────
def _ressource_acceptee(resource: Optional[str]) -> bool:
    if not resource:
        return True
    return resource.rstrip("/") in {url_ressource(), emetteur()}


def valider_demande(db: Session, params: dict) -> str:
    """[CA2] Valide `/oauth/authorize` et rend la demande SIGNÉE, à porter à la PWA.

    Lève `ErreurDemandeSansRetour` (client ou retour non vérifiés : rien ne repart chez
    le client) ou `ErreurDemandeAvecRetour` (le reste : l'erreur repart chez lui).
    """
    client = _client(db, params.get("client_id"))
    if client is None:
        raise ErreurDemandeSansRetour("invalid_client", "Ce connecteur n'est pas enregistré auprès d'Assistant Potager.")
    redirect_uri = params.get("redirect_uri") or ""
    if not redirect_uri and len(client.redirect_uris or []) == 1:
        redirect_uri = client.redirect_uris[0]
    if not redirect_uri or not _retour_enregistre(client, redirect_uri):
        raise ErreurDemandeSansRetour("invalid_request", "Adresse de retour inconnue pour ce connecteur.")

    state = params.get("state")
    if state is not None and len(state) > 1000:
        raise ErreurDemandeSansRetour("invalid_request", "Paramètre state trop long.")
    if params.get("response_type") != "code":
        raise ErreurDemandeAvecRetour("unsupported_response_type", "response_type=code attendu", redirect_uri, state)
    challenge = params.get("code_challenge") or ""
    if params.get("code_challenge_method") != "S256" or not (43 <= len(challenge) <= 128):
        raise ErreurDemandeAvecRetour("invalid_request", "PKCE S256 obligatoire", redirect_uri, state)
    if not _ressource_acceptee(params.get("resource")):
        raise ErreurDemandeAvecRetour("invalid_target", "Ressource inconnue", redirect_uri, state)

    scopes = set((params.get("scope") or "").split())
    charge = {
        "type": _TYPE_DEMANDE,
        "cid": client.client_id,
        "ruri": redirect_uri,
        "cc": challenge,
        "st": state,
        "ecr": SCOPE_ECRITURE in scopes,
        "exp": datetime.now(timezone.utc) + _DUREE_DEMANDE,
    }
    return jwt.encode(charge, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _lire_demande(jeton_demande: str) -> dict:
    try:
        charge = jwt.decode(jeton_demande or "", JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise ConsentementInvalideError("Demande de connexion expirée ou invalide : relance la connexion depuis ton assistant.")
    if charge.get("type") != _TYPE_DEMANDE:
        raise ConsentementInvalideError("Demande de connexion invalide.")
    return charge


def decrire_demande(db: Session, user_id: int, jeton_demande: str) -> dict:
    """[CA2, CA3] Ce que la page de consentement affiche : l'assistant, la portée, les potagers."""
    charge = _lire_demande(jeton_demande)
    client = _client(db, charge["cid"])
    if client is None:
        raise ConsentementInvalideError("Ce connecteur n'existe plus : relance la connexion depuis ton assistant.")
    utilisateur = db.query(User).filter(User.id == user_id).first()
    potagers = svc_potager_actif.lister_potagers_utilisateur(db, user_id)
    return {
        "client": {"nom": client.nom, "retour": urlsplit(charge["ruri"]).netloc},
        "ecriture_demandee": bool(charge.get("ecr")),
        "potagers": [
            {
                "id": p.id,
                "nom": p.nom,
                "role": svc_potager_actif.role_utilisateur(db, user_id, p.id),
                "actif": utilisateur is not None and utilisateur.potager_actif_id == p.id,
            }
            for p in potagers
            if not p.assistants_externes_interdits  # [US-294 / CA6] la page de consentement ne le propose plus
        ],
    }


def _potagers_consentis(db: Session, user_id: int, potager_ids: list) -> list[int]:
    """Les potagers choisis doivent être des potagers ACTIFS dont le jardinier est membre."""
    if not isinstance(potager_ids, list) or not potager_ids:
        raise ConsentementInvalideError("Choisis au moins un potager.")
    siens = {p.id: p for p in svc_potager_actif.lister_potagers_utilisateur(db, user_id)}
    choisis: list[int] = []
    for pid in potager_ids:
        if not isinstance(pid, int) or isinstance(pid, bool) or pid not in siens:
            raise ConsentementInvalideError("Ce potager ne fait pas partie des tiens.")
        if siens[pid].assistants_externes_interdits:  # [US-294 / CA6]
            raise ConsentementInvalideError(
                f"Le propriétaire du potager « {siens[pid].nom} » a interdit les assistants externes.")
        if pid not in choisis:
            choisis.append(pid)
    return choisis


def consentir(
    db: Session, user_id: int, jeton_demande: str, accepte: bool,
    ecriture: bool = False, potager_ids: Optional[list] = None,
) -> str:
    """[CA2, CA3] La réponse du jardinier : rend l'URL de retour vers son assistant.

    Refus → `error=access_denied`. Accord → une autorisation (portée, potagers) et un
    code à usage unique de 10 minutes, lié au défi PKCE de la demande.
    """
    charge = _lire_demande(jeton_demande)
    client = _client(db, charge["cid"])
    if client is None:
        raise ConsentementInvalideError("Ce connecteur n'existe plus : relance la connexion depuis ton assistant.")
    if not accepte:
        log.info("[US-290] Consentement refusé : user=%s client=%s", user_id, client.client_id)
        return _ajouter_parametres(charge["ruri"], {"error": "access_denied", "state": charge.get("st"), "iss": emetteur()})

    choisis = _potagers_consentis(db, user_id, potager_ids or [])
    autorisation = McpAutorisation(
        user_id=user_id, client_id=client.id, type=TYPE_OAUTH, libelle=client.nom,
        portee=PORTEE_ECRITURE if ecriture else PORTEE_LECTURE, potager_ids=choisis, cree_le=_maintenant(),
    )
    db.add(autorisation)
    db.flush()
    code = _nouveau_secret(_PREFIXE_CODE)
    db.add(McpCodeAutorisation(
        autorisation_id=autorisation.id, empreinte=empreinte(code), code_challenge=charge["cc"],
        redirect_uri=charge["ruri"], expire_le=_maintenant() + _DUREE_CODE,
    ))
    db.commit()
    log.info(
        "[US-290] Connecteur autorisé : user=%s client=%s portée=%s potagers=%s",
        user_id, client.nom, autorisation.portee, choisis,
    )
    from app.services.mcp import connexions as svc_connexions  # [US-294 / CA5] import différé : cycle

    svc_connexions.notifier_nouvelle_connexion(db, autorisation)
    return _ajouter_parametres(charge["ruri"], {"code": code, "state": charge.get("st"), "iss": emetteur()})


# ── Endpoint de jeton (/oauth/token) ──────────────────────────────────────────
def _emettre_paire(db: Session, autorisation: McpAutorisation) -> dict:
    acces = _nouveau_secret(_PREFIXES[JETON_ACCES])
    rafraichissement = _nouveau_secret(_PREFIXES[JETON_RAFRAICHISSEMENT])
    maintenant = _maintenant()
    duree_acces = timedelta(minutes=config.MCP_ACCES_TTL_MIN)
    db.add_all([
        McpJeton(autorisation_id=autorisation.id, type=JETON_ACCES, empreinte=empreinte(acces),
                 expire_le=maintenant + duree_acces, cree_le=maintenant),
        McpJeton(autorisation_id=autorisation.id, type=JETON_RAFRAICHISSEMENT, empreinte=empreinte(rafraichissement),
                 expire_le=maintenant + timedelta(days=config.MCP_RAFRAICHISSEMENT_TTL_JOURS), cree_le=maintenant),
    ])
    db.commit()
    return {
        "access_token": acces,
        "token_type": "Bearer",
        "expires_in": int(duree_acces.total_seconds()),
        "refresh_token": rafraichissement,
        "scope": portee_vers_scope(autorisation.portee),
    }


def _revoquer_autorisation(db: Session, autorisation: McpAutorisation, motif: str) -> None:
    maintenant = _maintenant()
    if autorisation.revoque_le is None:
        autorisation.revoque_le = maintenant
    db.query(McpJeton).filter(
        McpJeton.autorisation_id == autorisation.id, McpJeton.revoque_le.is_(None),
    ).update({McpJeton.revoque_le: maintenant}, synchronize_session=False)
    db.commit()
    log.warning("[US-290] Connecteur révoqué (%s) : autorisation=%s user=%s", motif, autorisation.id, autorisation.user_id)


def _pkce_valide(verifier: Optional[str], challenge: str) -> bool:
    if not verifier or not (43 <= len(verifier) <= 128):
        return False
    calcule = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii", "ignore")).digest()).rstrip(b"=").decode()
    return hmac.compare_digest(calcule, challenge)


def echanger_code(
    db: Session, client: McpClient, code: Optional[str], redirect_uri: Optional[str], code_verifier: Optional[str],
) -> dict:
    """[CA2] Code + vérificateur PKCE → jeton d'accès (1 h) et de rafraîchissement.

    Un code rejoué révoque toute l'autorisation qu'il a produite (OAuth 2.1 §4.1.3) :
    il a forcément fuité.
    """
    ligne = db.query(McpCodeAutorisation).filter(McpCodeAutorisation.empreinte == empreinte(code or "")).first()
    if ligne is None:
        raise ErreurOAuth("invalid_grant", "Code inconnu")
    autorisation = db.query(McpAutorisation).filter(McpAutorisation.id == ligne.autorisation_id).first()
    if ligne.utilise_le is not None:
        if autorisation is not None:
            _revoquer_autorisation(db, autorisation, "code rejoué")
        raise ErreurOAuth("invalid_grant", "Code déjà utilisé")
    if (autorisation is None or autorisation.client_id != client.id or autorisation.revoque_le is not None
            or ligne.expire_le < _maintenant()):
        raise ErreurOAuth("invalid_grant", "Code expiré ou invalide")
    if redirect_uri and redirect_uri != ligne.redirect_uri:
        raise ErreurOAuth("invalid_grant", "Adresse de retour différente de celle de la demande")
    if not _pkce_valide(code_verifier, ligne.code_challenge):
        raise ErreurOAuth("invalid_grant", "Vérificateur PKCE invalide")
    ligne.utilise_le = _maintenant()
    db.commit()
    log.info("[US-290] Code échangé : autorisation=%s client=%s", autorisation.id, client.nom)
    return _emettre_paire(db, autorisation)


def rafraichir(db: Session, client: McpClient, jeton_brut: Optional[str]) -> dict:
    """[CA2, CA8] Rotation : l'ancien jeton de rafraîchissement meurt, une nouvelle paire naît.

    Un jeton de rafraîchissement déjà consommé qui revient a fuité : toute
    l'autorisation est révoquée.
    """
    jeton = db.query(McpJeton).filter(
        McpJeton.empreinte == empreinte(jeton_brut or ""), McpJeton.type == JETON_RAFRAICHISSEMENT,
    ).first()
    if jeton is None:
        raise ErreurOAuth("invalid_grant", "Jeton de rafraîchissement inconnu")
    autorisation = db.query(McpAutorisation).filter(McpAutorisation.id == jeton.autorisation_id).first()
    if autorisation is None or autorisation.client_id != client.id:
        raise ErreurOAuth("invalid_grant", "Jeton de rafraîchissement invalide")
    if jeton.revoque_le is not None:
        if autorisation.revoque_le is None:
            _revoquer_autorisation(db, autorisation, "rafraîchissement rejoué")
        raise ErreurOAuth("invalid_grant", "Connexion révoquée : reconnecte ton assistant")
    if autorisation.revoque_le is not None or jeton.expire_le < _maintenant() or not _utilisateur_existe(db, autorisation.user_id):
        raise ErreurOAuth("invalid_grant", "Connexion expirée ou révoquée : reconnecte ton assistant")
    jeton.revoque_le = _maintenant()
    db.commit()
    return _emettre_paire(db, autorisation)


def revoquer_jeton(db: Session, client: McpClient, jeton_brut: Optional[str]) -> None:
    """[CA8] RFC 7009 : révoque un jeton du client. Un jeton de rafraîchissement emporte
    toute l'autorisation ; un jeton d'accès, lui seul. Jeton inconnu : rien, sans erreur."""
    jeton = db.query(McpJeton).filter(McpJeton.empreinte == empreinte(jeton_brut or "")).first()
    if jeton is None:
        return
    autorisation = db.query(McpAutorisation).filter(McpAutorisation.id == jeton.autorisation_id).first()
    if autorisation is None or autorisation.client_id != client.id:
        return
    if jeton.type == JETON_RAFRAICHISSEMENT:
        _revoquer_autorisation(db, autorisation, "révocation par le client")
    elif jeton.revoque_le is None:
        jeton.revoque_le = _maintenant()
        db.commit()


# ── Jetons personnels (CA9) et révocation depuis la PWA (CA8, US-294) ─────────
def creer_jeton_personnel(
    db: Session, user_id: int, libelle: str, ecriture: bool, potager_ids: list,
    duree_jours: Optional[int] = None,
) -> tuple[McpAutorisation, str]:
    """[CA9] Un jeton pour les clients de développement (MCP Inspector, Claude Code).

    Même modèle qu'une connexion OAuth : une portée, des potagers, une révocation. Le
    jeton n'est rendu qu'ICI, une fois ; seule son empreinte est gardée.
    """
    libelle = (libelle or "").strip()[:120] or "Jeton personnel"
    choisis = _potagers_consentis(db, user_id, potager_ids)
    jours = duree_jours if duree_jours is not None else config.MCP_PERSONNEL_TTL_JOURS
    if not isinstance(jours, int) or isinstance(jours, bool) or not (1 <= jours <= 365):
        raise ConsentementInvalideError("Durée de validité : entre 1 et 365 jours.")
    maintenant = _maintenant()
    autorisation = McpAutorisation(
        user_id=user_id, client_id=None, type=TYPE_PERSONNEL, libelle=libelle,
        portee=PORTEE_ECRITURE if ecriture else PORTEE_LECTURE, potager_ids=choisis, cree_le=maintenant,
    )
    db.add(autorisation)
    db.flush()
    brut = _nouveau_secret(_PREFIXES[JETON_PERSONNEL])
    db.add(McpJeton(
        autorisation_id=autorisation.id, type=JETON_PERSONNEL, empreinte=empreinte(brut),
        expire_le=maintenant + timedelta(days=jours), cree_le=maintenant,
    ))
    db.commit()
    log.info("[US-290] Jeton personnel créé : user=%s « %s » portée=%s", user_id, libelle, autorisation.portee)
    from app.services.mcp import connexions as svc_connexions  # [US-294 / CA5] import différé : cycle

    svc_connexions.notifier_nouvelle_connexion(db, autorisation)
    return autorisation, brut


def decrire_autorisation(db: Session, autorisation: McpAutorisation) -> dict:
    expiration = None
    if autorisation.type == TYPE_PERSONNEL:
        jeton = db.query(McpJeton).filter(McpJeton.autorisation_id == autorisation.id).first()
        expiration = jeton.expire_le.isoformat() if jeton else None
    return {
        "id": autorisation.id,
        "type": autorisation.type,
        "client": autorisation.libelle,
        "portee": autorisation.portee,
        "potager_ids": list(autorisation.potager_ids or []),
        "cree_le": autorisation.cree_le.isoformat() if autorisation.cree_le else None,
        "dernier_appel_le": autorisation.dernier_appel_le.isoformat() if autorisation.dernier_appel_le else None,
        "expire_le": expiration,
        "revoque_le": autorisation.revoque_le.isoformat() if autorisation.revoque_le else None,
    }


def lister_connexions(db: Session, user_id: int) -> list[dict]:
    """Les connecteurs du jardinier, du plus récent au plus ancien (écran d'US-294)."""
    autorisations = (
        db.query(McpAutorisation).filter(McpAutorisation.user_id == user_id)
        .order_by(McpAutorisation.id.desc()).all()
    )
    return [decrire_autorisation(db, a) for a in autorisations]


def revoquer_connexion(db: Session, user_id: int, autorisation_id: int) -> bool:
    """[CA8] Révocation par le jardinier : effective dès l'appel suivant du connecteur."""
    autorisation = db.query(McpAutorisation).filter(
        McpAutorisation.id == autorisation_id, McpAutorisation.user_id == user_id,
    ).first()
    if autorisation is None:
        return False
    _revoquer_autorisation(db, autorisation, "par le jardinier")
    return True


# ── Résolution d'un jeton à chaque appel (CA4, CA8) ───────────────────────────
def _utilisateur_existe(db: Session, user_id: int) -> bool:
    return db.query(User.id).filter(User.id == user_id).first() is not None


def resoudre_jeton(db: Session, jeton_brut: Optional[str]) -> Optional[Connexion]:
    """[CA4, CA8] Le jeton d'un appel MCP → la connexion, ou None.

    Tout est relu en base À CHAQUE APPEL : jeton révoqué ou expiré, autorisation
    révoquée, compte supprimé → None, donc 401, dès l'appel suivant. Un jeton de
    rafraîchissement n'ouvre jamais le serveur MCP.
    """
    if not jeton_brut:
        return None
    jeton = db.query(McpJeton).filter(McpJeton.empreinte == empreinte(jeton_brut)).first()
    if jeton is None or jeton.type not in (JETON_ACCES, JETON_PERSONNEL):
        return None
    if jeton.revoque_le is not None or jeton.expire_le < _maintenant():
        return None
    autorisation = db.query(McpAutorisation).filter(McpAutorisation.id == jeton.autorisation_id).first()
    if autorisation is None or autorisation.revoque_le is not None:
        return None
    if not _utilisateur_existe(db, autorisation.user_id):
        return None
    return Connexion(
        autorisation_id=autorisation.id,
        user_id=autorisation.user_id,
        client=autorisation.libelle,
        portee=autorisation.portee,
        potager_ids=tuple(autorisation.potager_ids or ()),
    )
