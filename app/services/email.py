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
