"""
app/services/voix/catalogue.py — les voix françaises de Gaston [US-300 / CA4, CA5, CA6]
=======================================================================================
Lues sur l'API Mistral (D2) : une nouvelle voix française publiée par Mistral apparaît
sans redéploiement, au plus tard après 24 h (durée du cache). Si l'API ne répond pas,
les quatre voix connues sont rendues, marquées « liste de secours » : le jardinier ne
voit aucune erreur.

Seules les voix de langue exactement `fr` (Voxtral 3) sont proposées : les variantes
`fr_fr` (« Marie - Sad »…) sont d'anciennes voix de Voxtral 2, que `voxtral-mini-tts-3-0`
n'accepte pas toujours (essai US-298, code 3051).
"""
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from app import config
from app.services.context import TenantContext
from llm import passerelle

log = logging.getLogger("potager")

DUREE_CACHE_S = 24 * 3600
DUREE_CACHE_SECOURS_S = 5 * 60   # on retente vite l'API quand elle a échoué
PHRASE_EXTRAIT = "Bonjour, je suis Gaston, votre compagnon du potager"
LANGUE_FRANCAISE = "fr"


@dataclass(frozen=True)
class VoixFrancaise:
    """Une voix proposée au jardinier. `uuid` sert à relire l'extrait chez Mistral."""

    id: str                      # identifiant à envoyer à la synthèse (slug Mistral)
    nom: str
    genre: Optional[str] = None
    uuid: Optional[str] = None

    def public(self) -> dict:
        # `par_defaut` : la pastille « par défaut » de la maquette (US-301), lue à l'instant
        # de l'appel pour suivre `VOIX_PAR_DEFAUT` sans vider le cache du catalogue.
        return {"id": self.id, "nom": self.nom, "genre": self.genre,
                "par_defaut": self.id == config.VOIX_PAR_DEFAUT}


# Les quatre voix françaises de Voxtral 3 relevées par US-298, si l'API ne répond pas.
VOIX_DE_SECOURS: tuple[VoixFrancaise, ...] = (
    VoixFrancaise("voice_592", "Marie", "female"),
    VoixFrancaise("voice_3137", "Manon", "female"),
    VoixFrancaise("voice_589", "Léa", "female"),
    VoixFrancaise("voice_3141", "Camille", "female"),
)


@dataclass(frozen=True)
class Catalogue:
    voix: tuple[VoixFrancaise, ...]
    liste_de_secours: bool

    def ids(self) -> list[str]:
        return [v.id for v in self.voix]

    def trouver(self, voix_id: str) -> Optional[VoixFrancaise]:
        return next((v for v in self.voix if v.id == voix_id), None)

    def public(self) -> dict:
        return {"voix": [v.public() for v in self.voix], "liste_de_secours": self.liste_de_secours}


_verrou = threading.Lock()
_cache: dict = {"catalogue": None, "expire_a": 0.0}
_extraits: dict[str, bytes] = {}


def reinitialiser_caches() -> None:
    """Vide les caches du catalogue et des extraits (tests, ou après un changement de clé)."""
    with _verrou:
        _cache.update(catalogue=None, expire_a=0.0)
        _extraits.clear()


def _en_voix(element: dict) -> Optional[VoixFrancaise]:
    """Une entrée de l'API → voix française, ou None (autre langue, entrée incomplète)."""
    langues = element.get("languages") or []
    slug, nom = element.get("slug"), element.get("name")
    if LANGUE_FRANCAISE not in langues or not isinstance(slug, str) or not slug \
            or not isinstance(nom, str) or not nom.strip():
        return None
    genre = element.get("gender")
    uuid = element.get("id")
    return VoixFrancaise(slug, nom.strip(), genre if isinstance(genre, str) else None,
                         uuid if isinstance(uuid, str) else None)


def _catalogue_configure() -> Optional[Catalogue]:
    """`VOIX_CATALOGUE` défini → ces voix. Synthèse hors Mistral sans `VOIX_CATALOGUE` →
    la seule `VOIX_PAR_DEFAUT` (les voix Mistral n'auraient aucun sens). Sinon None."""
    if config.VOIX_CATALOGUE:
        return Catalogue(tuple(VoixFrancaise(i, n, g) for i, n, g in config.VOIX_CATALOGUE), False)
    if not passerelle.modele_pour(passerelle.TYPE_VOIX).startswith(passerelle.PREFIXE_MISTRAL):
        log.warning("⚠️  VOIX │ synthèse hors Mistral sans VOIX_CATALOGUE → seule la voix par défaut")
        return Catalogue((VoixFrancaise(config.VOIX_PAR_DEFAUT, config.VOIX_PAR_DEFAUT),), False)
    return None


def _lire_catalogue() -> Catalogue:
    configure = _catalogue_configure()
    if configure is not None:
        return configure
    try:
        voix = tuple(v for v in map(_en_voix, passerelle.lister_voix_mistral()) if v)
    except passerelle.LLMIndisponibleError as e:
        log.info("🔊 VOIX │ catalogue : API des voix indisponible (%s) → liste de secours",
                 type(e).__name__)
        return Catalogue(VOIX_DE_SECOURS, True)
    if not voix:
        log.warning("⚠️  VOIX │ catalogue : aucune voix française rendue par l'API → liste de secours")
        return Catalogue(VOIX_DE_SECOURS, True)
    return Catalogue(voix, False)


def lire_catalogue() -> Catalogue:
    """Les voix françaises, depuis le cache de 24 h ou l'API, sinon la liste de secours."""
    with _verrou:
        maintenant = time.monotonic()
        if _cache["catalogue"] is not None and maintenant < _cache["expire_a"]:
            return _cache["catalogue"]
        catalogue = _lire_catalogue()
        duree = DUREE_CACHE_SECOURS_S if catalogue.liste_de_secours else DUREE_CACHE_S
        _cache.update(catalogue=catalogue, expire_a=maintenant + duree)
        return catalogue


class VoixInconnueDuCatalogue(Exception):
    """La voix demandée n'est pas au catalogue. Porte la liste des voix valides."""

    def __init__(self, voix_id: str, valides: list[str]) -> None:
        self.voix_id, self.valides = voix_id, valides
        super().__init__(f"voix « {voix_id} » absente du catalogue (valides : {', '.join(valides)})")


def extrait(ctx: TenantContext, voix_id: str) -> bytes:
    """[CA6] MP3 court de la voix : l'extrait fourni par Mistral, sinon la phrase d'essai
    synthétisée UNE fois puis gardée en mémoire. Un deuxième appel ne coûte rien.

    Lève `VoixInconnueDuCatalogue`, ou `LLMIndisponibleError` si la synthèse échoue.
    """
    catalogue = lire_catalogue()
    voix = catalogue.trouver(voix_id)
    if voix is None:
        raise VoixInconnueDuCatalogue(voix_id, catalogue.ids())
    with _verrou:
        garde = _extraits.get(voix.id)
    if garde:
        return garde

    audio = None
    if voix.uuid and not catalogue.liste_de_secours:
        audio = passerelle.extrait_voix_mistral(voix.uuid)
    if not audio:
        audio = passerelle.synthetiser(ctx=ctx, texte=PHRASE_EXTRAIT, voix_id=voix.id).audio
    with _verrou:
        _extraits[voix.id] = audio
    return audio
