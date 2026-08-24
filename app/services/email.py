"""
app/services/email.py — Envoi de l'e-mail de vérification via l'API Brevo [US-044]
--------------------------------------------------------------------------------
Aucun SMTP sortant auto-hébergé : Hetzner bloque le port 25 par défaut sur les
VPS Cloud (déblocage sur ticket, au cas par cas) et ses plages d'IP sont
fréquemment blacklistées par les grands webmails — la délivrabilité y serait
mauvaise même en cas de déblocage. On appelle donc l'API HTTPS de Brevo, qui
gère la réputation IP et la délivrabilité à notre place.
"""
import logging

import httpx

from config import BREVO_API_KEY, EMAIL_FROM, EMAIL_FROM_NOM, FRONTEND_URL

log = logging.getLogger("potager")

_BREVO_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT_SECONDES = 10.0


def envoyer_email_verification(destinataire: str, token: str) -> None:
    """[CA9] Envoie l'e-mail de vérification contenant le lien unique (24h).

    Mode dégradé si `BREVO_API_KEY` n'est pas configurée (dev/test) : logue le
    lien au lieu d'appeler l'API, pour ne pas bloquer les tests automatisés ni
    le développement local sans compte Brevo.

    Un échec d'envoi (réseau, API Brevo indisponible) est loggé mais ne lève
    pas d'exception : l'inscription reste valide, l'utilisateur peut redemander
    l'e-mail via /auth/resend-verification.
    """
    lien = f"{FRONTEND_URL}/verifier-email?token={token}"

    if not BREVO_API_KEY:
        log.info(
            "[US-044] Mode dégradé (BREVO_API_KEY absente) — lien de vérification pour %s : %s",
            destinataire, lien,
        )
        return

    payload = {
        "sender": {"name": EMAIL_FROM_NOM, "email": EMAIL_FROM},
        "to": [{"email": destinataire}],
        "subject": "Vérifiez votre adresse e-mail — Assistant Potager",
        "htmlContent": (
            "<p>Bienvenue sur Assistant Potager !</p>"
            "<p>Cliquez sur ce lien pour vérifier votre adresse e-mail (valable 24h) :</p>"
            f'<p><a href="{lien}">{lien}</a></p>'
            "<p>Si vous n'êtes pas à l'origine de cette inscription, ignorez cet e-mail.</p>"
        ),
    }

    try:
        reponse = httpx.post(
            _BREVO_ENDPOINT,
            json=payload,
            headers={"api-key": BREVO_API_KEY, "content-type": "application/json"},
            timeout=_TIMEOUT_SECONDES,
        )
        reponse.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("[US-044] Échec de l'envoi de l'e-mail de vérification à %s : %s", destinataire, exc)


def envoyer_email_reset_mdp(destinataire: str, token: str, definition_initiale: bool = False) -> None:
    """[US-057 / CA1] Envoie l'e-mail de réinitialisation de mot de passe
    contenant le lien unique (1h). Même mode dégradé et même tolérance aux
    échecs d'envoi que envoyer_email_verification ci-dessus.

    [US-090 / CA17] `definition_initiale=True` pour un compte créé via Google,
    qui n'a encore aucun mot de passe : le message l'oriente vers « Continuer
    avec Google » ou lui propose d'en définir un premier — jamais un texte
    laissant penser que son compte n'existe pas."""
    lien = f"{FRONTEND_URL}/reinitialiser-mot-de-passe?token={token}"

    if not BREVO_API_KEY:
        log.info(
            "[US-057] Mode dégradé (BREVO_API_KEY absente) — lien de %s pour %s : %s",
            "définition de mot de passe" if definition_initiale else "réinitialisation",
            destinataire, lien,
        )
        return

    if definition_initiale:
        sujet = "Définir un mot de passe pour votre compte — Assistant Potager"
        contenu = (
            "<p>Votre compte Assistant Potager a été créé avec Google : il n'a pas "
            "encore de mot de passe.</p>"
            "<p>Le plus simple reste de cliquer sur <strong>« Continuer avec Google »</strong> "
            "depuis l'écran de connexion — aucun mot de passe n'est nécessaire.</p>"
            "<p>Si vous préférez en définir un, utilisez ce lien (valable 1 heure) :</p>"
            f'<p><a href="{lien}">{lien}</a></p>'
            "<p>Vous pourrez ensuite vous connecter des deux façons, au choix. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail — "
            "votre compte reste inchangé.</p>"
        )
    else:
        sujet = "Réinitialisation de votre mot de passe — Assistant Potager"
        contenu = (
            "<p>Vous avez demandé la réinitialisation de votre mot de passe.</p>"
            "<p>Cliquez sur ce lien pour choisir un nouveau mot de passe (valable 1 heure) :</p>"
            f'<p><a href="{lien}">{lien}</a></p>'
            "<p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail — "
            "votre mot de passe actuel reste inchangé.</p>"
        )

    payload = {
        "sender": {"name": EMAIL_FROM_NOM, "email": EMAIL_FROM},
        "to": [{"email": destinataire}],
        "subject": sujet,
        "htmlContent": contenu,
    }

    try:
        reponse = httpx.post(
            _BREVO_ENDPOINT,
            json=payload,
            headers={"api-key": BREVO_API_KEY, "content-type": "application/json"},
            timeout=_TIMEOUT_SECONDES,
        )
        reponse.raise_for_status()
    except httpx.HTTPError as exc:
        log.error("[US-057] Échec de l'envoi de l'e-mail de réinitialisation à %s : %s", destinataire, exc)
