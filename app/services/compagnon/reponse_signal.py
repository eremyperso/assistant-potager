"""
app/services/compagnon/reponse_signal.py — Répondre à un message spontané [US-267]
=================================================================================
Un message spontané N'ÉCRIT JAMAIS (R8). Ce qui s'écrit à sa suite passe par une phrase
de geste, celle que le jardinier aurait dite, rendue au flux ordinaire des gestes : elle
ouvre un récapitulatif à confirmer, jamais une exécution.

* **Les boutons** (CA7) : « 🧣 Voile posé » sur un gel devient « j'ai posé un voile de
  protection sur Planche Est ». Un bouton sans geste (« Pas encore ») n'écrit rien.
* **La réponse** (CA8) : « oui environ 20 sur 24 » à « Ça a germé ? » sur le lot 14 se
  lit, avec le signal d'origine, comme « levée du lot 14 : 20 ». Ce que le code ne sait pas
  lire ainsi passe à l'agent, avec le message spontané dans son contexte.

Ce module est pur : ni base, ni modèle. Il lit une réponse courte, au vocabulaire fermé,
sur UN signal ; deux signaux qui posent une question dans le même message rendent un
« oui » ambigu, et le code s'abstient.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from unidecode import unidecode

from app.services.compagnon.redaction_signal import (
    GENRE_CANICULE, GENRE_GEL, GENRE_LEVEE, GENRE_METTRE_EN_TERRE, GENRE_RECOLTE, GENRE_REPIQUER,
    GENRE_SECHERESSE, SignalARediger,
)

#: Préfixe des boutons d'un message spontané : `spon:<potager_id>:<envoi_id>:<code>`.
PREFIXE_CALLBACK = "spon"
CODE_REGLAGES = "reglages"
CODE_PLUS_TARD = "plus_tard"

CODE_VOILE = "voile"
CODE_ARROSE = "arrose"
CODE_LEVEE = "levee"
CODE_REPIQUAGE = "repiquage"
CODE_PLANTATION = "plantation"
CODE_RECOLTE = "recolte"

#: Les boutons d'un sujet : le geste à proposer, et « plus tard », qui n'écrit rien.
_BOUTONS: dict[str, tuple[tuple[str, str], ...]] = {
    GENRE_GEL: (("🧣 Voile posé", CODE_VOILE), ("👌 Je m'en occupe", CODE_PLUS_TARD)),
    GENRE_CANICULE: (("💧 J'ai arrosé", CODE_ARROSE),),
    GENRE_SECHERESSE: (("💧 J'ai arrosé", CODE_ARROSE),),
    GENRE_LEVEE: (("🌱 Noter la levée", CODE_LEVEE), ("⏳ Pas encore", CODE_PLUS_TARD)),
    GENRE_REPIQUER: (("🪴 Noter le repiquage", CODE_REPIQUAGE),),
    GENRE_METTRE_EN_TERRE: (("🌿 Noter la mise en terre", CODE_PLANTATION),),
    GENRE_RECOLTE: (("🧺 Noter une récolte", CODE_RECOLTE),),
}
#: Le geste qu'un « oui » accepte, sujet par sujet : celui de la question posée.
_GESTE_DU_OUI: dict[str, str] = {
    GENRE_GEL: CODE_VOILE,
    GENRE_CANICULE: CODE_ARROSE,
    GENRE_SECHERESSE: CODE_ARROSE,
    GENRE_LEVEE: CODE_LEVEE,
    GENRE_REPIQUER: CODE_REPIQUAGE,
    GENRE_METTRE_EN_TERRE: CODE_PLANTATION,
    GENRE_RECOLTE: CODE_RECOLTE,
}
#: Au-delà, les boutons d'un message groupé deviendraient un écran.
NB_SIGNAUX_A_BOUTONS = 4

#: Une réponse courte : au-delà, c'est une phrase à part entière, l'agent la lit.
MOTS_REPONSE_MAX = 8
_OUI = frozenset({
    "oui", "ouais", "ouai", "yes", "ok", "okay", "voila", "fait", "c'est fait", "cest fait",
    "c'est pose", "cest pose", "pose", "oui c'est fait", "oui cest fait", "oui c'est pose",
    "oui cest pose", "oui oui", "bien sur", "evidemment", "oui fait", "c'est bon", "cest bon",
})
_NEGATIONS = re.compile(r"\b(non|pas|rien|aucun|aucune|zero|jamais|nan)\b")
_NOMBRE = re.compile(r"\d+")


@dataclass(frozen=True)
class Bouton:
    libelle: str
    callback: str


def _normaliser(texte: str) -> str:
    brut = unidecode((texte or "").replace("’", "'")).lower().strip()
    return " ".join(re.sub(r"[!.?…,;]+", " ", brut).split())


def callback(potager_id: int, envoi_id: int, code: str) -> str:
    """64 octets au plus (limite Telegram) : quelques nombres et un code court."""
    return f"{PREFIXE_CALLBACK}:{potager_id}:{envoi_id}:{code}"


def lire_callback(donnee: str) -> Optional[tuple[int, int, str]]:
    """`spon:12:345:voile` → (12, 345, "voile") ; None si la donnée est d'une autre forme."""
    morceaux = (donnee or "").split(":")
    if len(morceaux) != 4 or morceaux[0] != PREFIXE_CALLBACK:
        return None
    try:
        return int(morceaux[1]), int(morceaux[2]), morceaux[3]
    except ValueError:
        return None


def _precision(signal: SignalARediger) -> str:
    d = signal.donnees or {}
    if d.get("numero") is not None:
        return f" · lot {d['numero']}"
    if d.get("parcelle"):
        return f" · {str(d['parcelle'])[:18]}"
    return ""


def boutons(potager_id: int, signaux: Sequence[SignalARediger]) -> list[list[Bouton]]:
    """[CA7] Les boutons d'un message : une rangée par sujet qui en a, puis les réglages.

    Dans un message groupé, chaque bouton nomme son lot ou sa parcelle.
    """
    avec_geste = [s for s in signaux if s.envoi_id is not None and s.genre in _BOUTONS]
    rangees: list[list[Bouton]] = []
    for signal in avec_geste[:NB_SIGNAUX_A_BOUTONS]:
        suffixe = _precision(signal) if len(avec_geste) > 1 else ""
        rangees.append([
            Bouton(libelle + (suffixe if code != CODE_PLUS_TARD else ""), callback(potager_id, signal.envoi_id, code))
            for libelle, code in _BOUTONS[signal.genre]
        ])
    rangees.append([Bouton("⚙️ Régler ces messages", callback(potager_id, 0, CODE_REGLAGES))])
    return rangees


def phrase_du_geste(signal: SignalARediger, code: str, quantite: Optional[int] = None) -> Optional[str]:
    """[CA7] La phrase de geste qu'un bouton (ou un « oui ») rend au flux des gestes ; None :
    rien à écrire. Sans quantité, le flux des gestes la demande lui-même (« Combien ? »)."""
    d = signal.donnees or {}
    culture = d.get("culture")
    numero = d.get("numero")
    parcelle = d.get("parcelle")
    if code == CODE_VOILE and parcelle:
        return f"j'ai posé un voile de protection sur {parcelle}"
    if code == CODE_ARROSE:
        return f"j'ai arrosé {parcelle}" if parcelle else "j'ai arrosé"
    if code == CODE_LEVEE and numero is not None:
        return f"levée du lot {numero} : {quantite}" if quantite is not None else f"levée du lot {numero}"
    if code == CODE_REPIQUAGE and numero is not None and culture:
        return f"mise en godet de {culture} du lot {numero}"
    if code == CODE_PLANTATION and numero is not None and culture:
        return f"plantation de {culture} du lot {numero}"
    if code == CODE_RECOLTE and culture:
        return f"récolte de {culture} sur {parcelle}" if parcelle else f"récolte de {culture}"
    return None


def reformuler(signaux: Sequence[SignalARediger], texte: str) -> Optional[str]:
    """[CA8] La réponse du jardinier, lue avec le signal d'origine ; None : le code ne sait pas
    la lire, elle passe telle quelle (à l'agent, avec le message spontané en contexte).

    Lu ici : un « oui » court au sujet qui pose une question, et le nombre de plants levés
    (« oui environ 20 sur 24 » → « levée du lot 14 : 20 »). Jamais une négation : « rien n'a
    levé », « pas encore » n'écrivent rien.
    """
    questions = [s for s in signaux if s.genre in _GESTE_DU_OUI]
    if len(questions) != 1:
        return None
    signal = questions[0]
    normal = _normaliser(texte)
    if not normal or len(normal.split()) > MOTS_REPONSE_MAX or _NEGATIONS.search(normal):
        return None
    code = _GESTE_DU_OUI[signal.genre]
    nombres = _NOMBRE.findall(normal)
    if signal.genre == GENRE_LEVEE and nombres:
        # « 20 sur 24 », « environ 20 » : le premier nombre dit ce qui a levé.
        return phrase_du_geste(signal, code, int(nombres[0]))
    if normal in _OUI:
        return phrase_du_geste(signal, code)
    return None
