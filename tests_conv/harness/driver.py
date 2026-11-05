"""Pilote Telegram (Telethon) : joue le jardinier devant le bot de test.

Un tour = un envoi (message ou clic) puis l'attente de la fin de la réponse **par
quiescence** : plus aucun message ni édition pendant `quiescence_s`, avec un plafond
global. Les éditions comptent, car le bot affiche souvent « … » puis remplace par la
réponse, ou modifie le récapitulatif après un clic.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from .assertions import Observation
from .config import Config
from .texte import norm

log = logging.getLogger("conv")

#: nombre de messages du bot gardés en mémoire pour retrouver un bouton à cliquer
MEMOIRE_BOUTONS = 12


class BoutonIntrouvable(Exception):
    pass


@dataclass
class _Vue:
    """Messages du bot vus pendant le tour en cours, indexés par identifiant (édition = remplacement)."""
    messages: dict = field(default_factory=dict)
    dernier_evenement: float = 0.0
    premier_evenement: float = 0.0


class PiloteTelegram:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.client = TelegramClient(StringSession(cfg.session), cfg.api_id, cfg.api_hash,
                                     connection_retries=8, retry_delay=2)
        self._vue = _Vue()
        self._recents: dict = {}      # id → message, pour retrouver un bouton d'un tour précédent
        self._bot = None
        self._dernier_envoi = 0.0
        self.mon_id: int = 0

    async def __aenter__(self) -> "PiloteTelegram":
        await self.client.connect()
        if not await self.client.is_user_authorized():
            raise RuntimeError("Session Telethon refusée : refaire `python -m tests_conv session`")
        moi = await self.client.get_me()
        self.mon_id = moi.id
        self._bot = await self.client.get_entity(self.cfg.bot)
        self.client.add_event_handler(self._sur_message, events.NewMessage(from_users=self._bot, incoming=True))
        self.client.add_event_handler(self._sur_message, events.MessageEdited(from_users=self._bot))
        return self

    async def __aexit__(self, *exc) -> None:
        await self.client.disconnect()

    # ── réception ───────────────────────────────────────────────────────────
    async def _sur_message(self, event) -> None:
        maintenant = time.monotonic()
        m = event.message
        self._vue.messages[m.id] = m
        self._recents[m.id] = m
        for ancien in sorted(self._recents)[:-MEMOIRE_BOUTONS]:
            del self._recents[ancien]
        self._vue.dernier_evenement = maintenant
        if not self._vue.premier_evenement:
            self._vue.premier_evenement = maintenant

    # ── envoi ───────────────────────────────────────────────────────────────
    async def _avec_patience(self, fabrique):
        """Rejoue l'appel après un FloodWait (le délai imposé) ou une coupure réseau passagère."""
        for essai in range(4):
            try:
                return await fabrique()
            except FloodWaitError as e:
                log.warning("FloodWait : attente de %s s", e.seconds)
                await asyncio.sleep(e.seconds + 1)
            except (ConnectionError, OSError) as e:
                log.warning("Coupure réseau (%s), nouvel essai %s/3", e, essai + 1)
                await asyncio.sleep(2 * (essai + 1))
        raise RuntimeError("Telegram injoignable après 4 essais")

    async def _respecter_debit(self) -> None:
        attente = self.cfg.pause_s - (time.monotonic() - self._dernier_envoi)
        if attente > 0:
            await asyncio.sleep(attente)
        self._dernier_envoi = time.monotonic()

    async def _attendre_fin_de_reponse(self, debut: float) -> bool:
        """Rend True si au moins un message est arrivé."""
        while True:
            await asyncio.sleep(0.2)
            maintenant = time.monotonic()
            v = self._vue
            if maintenant - debut > self.cfg.plafond_tour_s:
                return bool(v.messages)
            if not v.messages:
                if maintenant - debut > self.cfg.premiere_reponse_s:
                    return False
            elif maintenant - v.dernier_evenement >= self.cfg.quiescence_s:
                return True

    def _observation(self, debut: float, repondu: bool) -> Observation:
        obs = Observation(silence=not repondu)
        v = self._vue
        obs.latence_s = (v.premier_evenement - debut) if v.premier_evenement else self.cfg.premiere_reponse_s
        for _, m in sorted(v.messages.items()):
            if m.message:
                obs.messages.append(m.message)
            for rangee in (m.buttons or []):
                obs.boutons.extend(b.text for b in rangee)
        return obs

    async def _tour(self, action) -> Observation:
        await self._respecter_debit()
        self._vue = _Vue()
        debut = time.monotonic()
        await self._avec_patience(action)
        repondu = await self._attendre_fin_de_reponse(debut)
        return self._observation(debut, repondu)

    async def envoyer(self, texte: str) -> Observation:
        return await self._tour(lambda: self.client.send_message(self._bot, texte))

    async def cliquer(self, libelle: str) -> Observation:
        cible = norm(libelle)
        for _, m in sorted(self._recents.items(), reverse=True):
            for i, rangee in enumerate(m.buttons or []):
                for j, bouton in enumerate(rangee):
                    if cible in norm(bouton.text):
                        return await self._tour(lambda m=m, i=i, j=j: self._clic(m, i, j))
        vus = [b.text for m in self._recents.values() for r in (m.buttons or []) for b in r]
        raise BoutonIntrouvable(f"bouton « {libelle} » introuvable (boutons récents : {', '.join(vus) or 'aucun'})")

    async def _clic(self, message, i: int, j: int) -> None:
        try:
            await message.click(i, j)
        except asyncio.TimeoutError:
            # le bot n'a pas répondu à la requête de rappel : ce qu'il a fait se lit dans ses messages
            log.warning("Clic sans réponse de rappel (délai) — la réponse éventuelle est lue quand même")

    async def reinitialiser(self) -> bool:
        """`/reset_test` : vrai si le bot répond RESET_OK (état mémoire et base vidés)."""
        obs = await self.envoyer("/reset_test")
        return "RESET_OK" in obs.texte
