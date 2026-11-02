"""
app/services/compagnon/distributeur.py — Le moment et la forme d'un message spontané [US-267]
===========================================================================================
Le veilleur détecte (US-266) ; le distributeur décide QUAND et SOUS QUELLE FORME un signal
part vers un jardinier. Il ne décide pas COMBIEN (D2 : pas de plafond) :

1. un signal dont le thème est coupé est consommé sans envoi (CA1) ;
2. un thème `immediat` part tout de suite hors plage de silence, et ce qui tombe dans la
   même demi-heure part dans le même message (CA2) ;
3. en plage de silence, l'envoi attend la fin de la plage, SAUF si le signal expire avant :
   il part alors avant la plage, ou pas du tout s'il est déjà dans la plage (CA3) ;
4. un thème `resume` rejoint le point du matin (8 h, réglable) ; sans signal, pas de point
   du matin (CA4, D7) ;
5. trois messages d'un thème restés sans réaction font passer ce thème au point du matin,
   et le message qui le porte le dit, une fois (CA5).

Ce module est PUR (CA12) : ni base, ni réseau, ni horloge, ni modèle. Les heures sont
celles du potager (Europe/Paris), sans fuseau, comme les signaux. Un test d'AST vérifie
qu'il n'importe ni `llm` ni l'agent : le distributeur ne parle jamais au modèle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Iterable, Optional, Sequence

from app.services.compagnon.veilleur import (
    THEME_ECHEANCES, THEME_METEO, THEME_RAPPELS, THEME_RESUME, THEME_SUGGESTIONS, THEME_SUIVIS,
)

# ═════════════════════════════════════════════════════════════════════════════
# Vocabulaire — le même que `envois_signaux.mode` (CHECK de migration_v66)
# ═════════════════════════════════════════════════════════════════════════════
MODE_IMMEDIAT = "immediat"
MODE_RESUME = "resume"
MODE_COUPE = "coupe"
MODES: tuple[str, ...] = (MODE_IMMEDIAT, MODE_RESUME, MODE_COUPE)

ETAT_EN_ATTENTE = "en_attente"
ETAT_ENVOYE = "envoye"
ETAT_IGNORE = "ignore"

MOTIF_THEME_COUPE = "theme_coupe"
MOTIF_EXPIRE = "expire"
MOTIF_EXPIRE_PENDANT_SILENCE = "expire_pendant_le_silence"

#: Les thèmes qu'on règle, dans l'ordre où `/profil` les montre. `resume` est le bilan du
#: dimanche : il existe toujours, et il se coupe (D7).
THEMES_REGLABLES: tuple[str, ...] = (
    THEME_METEO, THEME_RAPPELS, THEME_ECHEANCES, THEME_SUIVIS, THEME_SUGGESTIONS, THEME_RESUME,
)
#: Cadrage §2 : la météo et les rappels tout de suite, le reste au point du matin. Le bilan
#: du dimanche part à son heure (dimanche 18 h).
MODES_PAR_DEFAUT: dict[str, str] = {
    THEME_METEO: MODE_IMMEDIAT,
    THEME_RAPPELS: MODE_IMMEDIAT,
    THEME_ECHEANCES: MODE_RESUME,
    THEME_SUIVIS: MODE_RESUME,
    THEME_SUGGESTIONS: MODE_RESUME,
    THEME_RESUME: MODE_IMMEDIAT,
}
#: Le bilan n'appelle aucune réponse : son silence ne le fait jamais basculer (CA5).
THEMES_SANS_BASCULE: frozenset[str] = frozenset({THEME_RESUME})

LIBELLES_THEME: dict[str, str] = {
    THEME_METEO: "la météo",
    THEME_RAPPELS: "les rappels",
    THEME_ECHEANCES: "les échéances de la pépinière et des récoltes",
    THEME_SUIVIS: "les suivis (levées, arrosages)",
    THEME_SUGGESTIONS: "les suggestions de semis",
    THEME_RESUME: "le bilan du dimanche",
}
LIBELLES_MODE: dict[str, str] = {
    MODE_IMMEDIAT: "tout de suite",
    MODE_RESUME: "au point du matin",
    MODE_COUPE: "jamais",
}

SILENCE_DEBUT_DEFAUT = 21
SILENCE_FIN_DEFAUT = 8
HEURE_RESUME_DEFAUT = 8
#: [CA2] Ce qui tombe dans la même demi-heure part dans le même message.
FENETRE_REGROUPEMENT = timedelta(minutes=30)
#: [CA5] Messages d'un thème restés sans réaction avant de passer au point du matin.
NB_SANS_REACTION = 3


# ═════════════════════════════════════════════════════════════════════════════
# Les réglages d'un jardinier sur un potager (profil, partie 3)
# ═════════════════════════════════════════════════════════════════════════════
def _heure(valeur, defaut: int) -> int:
    try:
        heure = int(valeur)
    except (TypeError, ValueError):
        return defaut
    return heure if 0 <= heure <= 23 else defaut


def _instant(valeur) -> Optional[datetime]:
    if isinstance(valeur, datetime):
        return valeur
    try:
        return datetime.fromisoformat(str(valeur)) if valeur else None
    except ValueError:
        return None


@dataclass(frozen=True)
class Reglages:
    """Le mode de chaque thème, la plage de silence et l'heure du point du matin."""

    modes: dict = field(default_factory=lambda: dict(MODES_PAR_DEFAUT))
    #: Depuis quand le mode du thème est celui-ci (None : défaut jamais changé). Seuls les
    #: messages envoyés après comptent pour la bascule (CA5).
    depuis: dict = field(default_factory=dict)
    #: [CA5] Les thèmes que le distributeur a fait basculer lui-même, faute de réaction.
    automatiques: frozenset = frozenset()
    silence_debut: int = SILENCE_DEBUT_DEFAUT
    silence_fin: int = SILENCE_FIN_DEFAUT
    heure_resume: int = HEURE_RESUME_DEFAUT

    def mode(self, theme: str) -> str:
        return self.modes.get(theme, MODES_PAR_DEFAUT.get(theme, MODE_RESUME))

    def depuis_le(self, theme: str) -> Optional[datetime]:
        return self.depuis.get(theme)

    @property
    def sans_silence(self) -> bool:
        return self.silence_debut == self.silence_fin


def reglages_depuis(
    proactivite: Optional[dict], silence_debut=None, silence_fin=None, heure_resume=None,
) -> Reglages:
    """Les réglages tels que la base les garde (`potager_membres`) ; une valeur illisible
    retombe sur son défaut, jamais sur « coupé »."""
    modes = dict(MODES_PAR_DEFAUT)
    depuis: dict = {}
    automatiques: set[str] = set()
    for theme, entree in (proactivite or {}).items():
        if theme not in MODES_PAR_DEFAUT:
            continue
        mode = entree.get("mode") if isinstance(entree, dict) else entree
        if mode in MODES:
            modes[theme] = mode
            if isinstance(entree, dict) and _instant(entree.get("le")) is not None:
                depuis[theme] = _instant(entree.get("le"))
            if isinstance(entree, dict) and entree.get("auto"):
                automatiques.add(theme)
    return Reglages(
        modes=modes, depuis=depuis, automatiques=frozenset(automatiques),
        silence_debut=_heure(silence_debut, SILENCE_DEBUT_DEFAUT),
        silence_fin=_heure(silence_fin, SILENCE_FIN_DEFAUT),
        heure_resume=_heure(heure_resume, HEURE_RESUME_DEFAUT),
    )


def proactivite_avec(
    proactivite: Optional[dict], theme: str, mode: str, maintenant: datetime, auto: bool = False,
) -> dict:
    """Le JSON des modes avec `theme` passé à `mode`, daté : rend une NOUVELLE valeur.

    `auto` : c'est le distributeur qui a fait basculer le thème (CA5), pas le jardinier.
    """
    if theme not in MODES_PAR_DEFAUT or mode not in MODES:
        raise ValueError(f"thème ou mode inconnu : {theme!r} / {mode!r}")
    nouveau = {t: (dict(e) if isinstance(e, dict) else {"mode": e}) for t, e in (proactivite or {}).items()}
    nouveau[theme] = {"mode": mode, "le": maintenant.isoformat(timespec="seconds"), "auto": bool(auto)}
    return nouveau


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — La plage de silence ; CA4 — le point du matin
# ═════════════════════════════════════════════════════════════════════════════
def en_silence(instant: datetime, reglages: Reglages) -> bool:
    """La plage est [début, fin[ et peut passer minuit (21 h → 8 h). Début = fin : aucune."""
    if reglages.sans_silence:
        return False
    debut, fin, heure = time(reglages.silence_debut), time(reglages.silence_fin), instant.time()
    if debut < fin:
        return debut <= heure < fin
    return heure >= debut or heure < fin


def fin_du_silence(instant: datetime, reglages: Reglages) -> datetime:
    """L'heure où la plage en cours se termine (l'instant lui-même hors plage)."""
    if not en_silence(instant, reglages):
        return instant
    fin = datetime.combine(instant.date(), time(reglages.silence_fin))
    return fin if fin > instant else fin + timedelta(days=1)


def prochain_point_du_matin(instant: datetime, reglages: Reglages) -> datetime:
    """[CA4] Le prochain point du matin après `instant` ; s'il tombe dans la plage de
    silence (point réglé à 7 h, silence jusqu'à 8 h), il attend la fin de la plage."""
    point = datetime.combine(instant.date(), time(reglages.heure_resume))
    if point <= instant:
        point += timedelta(days=1)
    return fin_du_silence(point, reglages)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 → CA5 — La décision pour un signal et un jardinier
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Decision:
    """Le sort d'un signal pour un jardinier : en attente jusqu'à `envoyer_le`, ou ignoré."""

    mode: str
    etat: str
    envoyer_le: datetime
    motif: Optional[str] = None
    #: [CA5] Ce signal fait passer son thème au point du matin : le message le dira.
    annonce_bascule: bool = False


def doit_basculer(theme: str, reactions: Sequence[Optional[datetime]]) -> bool:
    """[CA5] `reactions` : l'heure de réaction des derniers messages de ce thème, du plus
    récent au plus ancien (None = aucune). Trois de suite sans réaction → bascule."""
    if theme in THEMES_SANS_BASCULE or len(reactions) < NB_SANS_REACTION:
        return False
    return all(r is None for r in list(reactions)[:NB_SANS_REACTION])


def planifier(
    theme: str, expire_le: datetime, reglages: Reglages, maintenant: datetime,
    sans_reaction: bool = False,
) -> Decision:
    """[CA1 → CA5] Quand ce signal part-il vers ce jardinier, et sous quelle forme ?

    `sans_reaction` : les trois derniers messages de ce thème sont restés sans réaction
    (`doit_basculer`) ; un thème `immediat` passe alors au point du matin.
    """
    mode = reglages.mode(theme)
    if mode == MODE_COUPE:
        return Decision(MODE_COUPE, ETAT_IGNORE, maintenant, MOTIF_THEME_COUPE)
    if expire_le <= maintenant:
        return Decision(mode, ETAT_IGNORE, maintenant, MOTIF_EXPIRE)
    bascule = mode == MODE_IMMEDIAT and sans_reaction and theme not in THEMES_SANS_BASCULE
    if bascule:
        mode = MODE_RESUME
    if mode == MODE_IMMEDIAT:
        envoyer_le = fin_du_silence(maintenant, reglages)
    else:
        envoyer_le = prochain_point_du_matin(maintenant, reglages)
    if expire_le <= envoyer_le:
        # [CA3] Il ne survivrait pas jusque-là : il part avant la plage… s'il est encore temps.
        if en_silence(maintenant, reglages):
            return Decision(mode, ETAT_IGNORE, maintenant, MOTIF_EXPIRE_PENDANT_SILENCE, bascule)
        envoyer_le = maintenant
    return Decision(mode, ETAT_EN_ATTENTE, envoyer_le, None, bascule)


def report_de_regroupement(
    dernier_envoi: Optional[datetime], maintenant: datetime, reglages: Reglages,
    expirations: Iterable[datetime] = (),
) -> Optional[datetime]:
    """[CA2] Un message est parti il y a moins d'une demi-heure : ce qui arrive maintenant
    attend la fin de la demi-heure et part groupé. None : rien à attendre, il part.

    On n'attend jamais au prix d'un signal perdu : si la fin de la demi-heure tombe dans la
    plage de silence, ou après l'expiration d'un des signaux, il part tout de suite.
    """
    if dernier_envoi is None:
        return None
    fin = dernier_envoi + FENETRE_REGROUPEMENT
    if fin <= maintenant or en_silence(fin, reglages):
        return None
    if any(expire <= fin for expire in expirations):
        return None
    return fin
