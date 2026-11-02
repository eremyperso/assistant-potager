"""
app/services/compagnon/proactivite.py — Régler les messages spontanés [US-267 / CA9]
===================================================================================
Le profil, partie 3 : pour chaque thème, « tout de suite », « au point du matin » ou
« jamais » ; la plage de silence ; l'heure du point du matin. Rangé par jardinier ET par
potager, comme le prénom et le ton (`potager_membres`).

Deux chemins, une seule écriture :

* **les boutons** de `/profil` : le clic est la confirmation ;
* **une phrase** (« arrête de me parler de la météo », « silence de 22 h à 7 h ») : lue
  ici sans modèle, au vocabulaire fermé, elle devient une PROPOSITION que le jardinier
  confirme (R9). Une phrase qui n'est pas de cette forme n'est pas lue : elle suit son
  chemin ordinaire.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services.compagnon import distributeur as regles
from app.services.compagnon.veilleur import (
    THEME_ECHEANCES, THEME_METEO, THEME_RAPPELS, THEME_RESUME, THEME_SUGGESTIONS, THEME_SUIVIS,
)
from app.services.context import TenantContext
from database.models import PotagerMembre

log = logging.getLogger("potager")

REGLAGE_MODE = "mode"
REGLAGE_SILENCE = "silence"
REGLAGE_POINT_DU_MATIN = "point_du_matin"


@dataclass(frozen=True)
class Changement:
    """Un réglage proposé : un thème et son mode, une plage de silence, ou une heure."""

    genre: str
    theme: Optional[str] = None
    mode: Optional[str] = None
    debut: Optional[int] = None
    fin: Optional[int] = None
    heure: Optional[int] = None

    def en_donnees(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def depuis_donnees(cls, donnees: dict) -> "Changement":
        return cls(**{k: donnees.get(k) for k in ("genre", "theme", "mode", "debut", "fin", "heure")})


# ═════════════════════════════════════════════════════════════════════════════
# Lire et écrire
# ═════════════════════════════════════════════════════════════════════════════
def _membre(db: Session, ctx: TenantContext) -> Optional[PotagerMembre]:
    if ctx.user_id is None:
        return None
    return (db.query(PotagerMembre)
            .filter(PotagerMembre.user_id == ctx.user_id, PotagerMembre.potager_id == ctx.potager_id)
            .first())


def lire(db: Session, ctx: TenantContext) -> regles.Reglages:
    """Les réglages du jardinier sur ce potager ; les défauts s'il n'en a aucun."""
    membre = _membre(db, ctx)
    if membre is None:
        return regles.Reglages()
    return regles.reglages_depuis(membre.proactivite_compagnon, membre.silence_debut,
                                  membre.silence_fin, membre.heure_resume)


def appliquer(db: Session, ctx: TenantContext, changement: Changement, maintenant: datetime) -> Optional[regles.Reglages]:
    """Écrit le réglage ; None sans appartenance ou si le changement est invalide."""
    membre = _membre(db, ctx)
    if membre is None:
        return None
    if changement.genre == REGLAGE_MODE:
        if changement.theme not in regles.MODES_PAR_DEFAUT or changement.mode not in regles.MODES:
            return None
        membre.proactivite_compagnon = regles.proactivite_avec(
            membre.proactivite_compagnon, changement.theme, changement.mode, maintenant)
    elif changement.genre == REGLAGE_SILENCE:
        if not _heure_valide(changement.debut) or not _heure_valide(changement.fin):
            return None
        membre.silence_debut, membre.silence_fin = changement.debut, changement.fin
    elif changement.genre == REGLAGE_POINT_DU_MATIN:
        if not _heure_valide(changement.heure):
            return None
        membre.heure_resume = changement.heure
    else:
        return None
    db.commit()
    log.info("[US-267 / CA9] Réglage des messages spontanés %s (user %s, potager %s)",
             changement.en_donnees(), ctx.user_id, ctx.potager_id)
    return lire(db, ctx)


def mode_suivant(mode: str) -> str:
    """Le bouton d'un thème fait tourner les trois modes : tout de suite → point du matin → jamais."""
    rang = regles.MODES.index(mode) if mode in regles.MODES else -1
    return regles.MODES[(rang + 1) % len(regles.MODES)]


def _heure_valide(heure) -> bool:
    return isinstance(heure, int) and 0 <= heure <= 23


# ═════════════════════════════════════════════════════════════════════════════
# Dire les réglages
# ═════════════════════════════════════════════════════════════════════════════
def _h(heure: int) -> str:
    return f"{heure} h"


def texte_reglages(reglages: regles.Reglages) -> str:
    lignes = ["🔔 Mes messages spontanés, sujet par sujet :"]
    for theme in regles.THEMES_REGLABLES:
        auto = " (réglé par moi, faute de réponse)" if _auto(reglages, theme) else ""
        lignes.append(f"• {regles.LIBELLES_THEME[theme].capitalize()} : "
                      f"{regles.LIBELLES_MODE[reglages.mode(theme)]}{auto}")
    silence = ("aucune" if reglages.sans_silence
               else f"de {_h(reglages.silence_debut)} à {_h(reglages.silence_fin)}")
    lignes.append(f"Plage de silence : {silence}. Point du matin : {_h(reglages.heure_resume)}, "
                  "seulement s'il y a quelque chose à dire.")
    return "\n".join(lignes)


def _auto(reglages: regles.Reglages, theme: str) -> bool:
    """[CA5] Le thème est passé au point du matin faute de réponse, pas par choix."""
    return theme in reglages.automatiques


def texte_changement(changement: Changement) -> str:
    """La proposition dite au jardinier, avant sa confirmation."""
    if changement.genre == REGLAGE_MODE:
        sujet = regles.LIBELLES_THEME.get(changement.theme, changement.theme)
        if changement.mode == regles.MODE_COUPE:
            return f"Je ne t'écris plus de moi-même sur {sujet}. C'est bon ?"
        if changement.mode == regles.MODE_RESUME:
            return f"Je te regroupe {sujet} dans le point du matin. C'est bon ?"
        return f"Je te préviens tout de suite pour {sujet}. C'est bon ?"
    if changement.genre == REGLAGE_SILENCE:
        if changement.debut == changement.fin:
            return "Plus de plage de silence : je t'écris à toute heure quand c'est utile. C'est bon ?"
        return f"Je ne t'écris pas de moi-même entre {_h(changement.debut)} et {_h(changement.fin)}. C'est bon ?"
    return f"Ton point du matin arrivera à {_h(changement.heure)}. C'est bon ?"


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — Lire une phrase de réglage, sans modèle
# ═════════════════════════════════════════════════════════════════════════════
_THEMES_DITS: tuple[tuple[str, str], ...] = (
    (r"meteo|gel|gelees?|canicules?|pluies?|orages?", THEME_METEO),
    (r"rappels?", THEME_RAPPELS),
    (r"echeances?|repiquages?|pepiniere|recoltes?", THEME_ECHEANCES),
    (r"suivis?|levees?|arrosages?", THEME_SUIVIS),
    (r"suggestions?|idees? de semis|semis du mois|fenetres? de semis", THEME_SUGGESTIONS),
    (r"bilans?", THEME_RESUME),
)
_THEME = "(?P<theme>[a-z' ]+?)"
_DE = "(?:de |d'|des |du )"

#: Une phrase par forme, chacune avec son groupe `theme` ; le thème est lu par `_theme`.
_FORMES_MODE: tuple[tuple[re.Pattern, str], ...] = tuple(
    (re.compile(motif), mode) for motif, mode in (
        (rf"^(?:arrete|cesse) de me parler {_DE}{_THEME}$", regles.MODE_COUPE),
        (rf"^ne me parle plus {_DE}{_THEME}$", regles.MODE_COUPE),
        (rf"^(?:coupe|stop|plus de messages? (?:sur|pour|de)) {_THEME}$", regles.MODE_COUPE),
        (rf"^regroupe(?:-moi)? {_THEME} (?:le matin|dans le point du matin|au point du matin)$",
         regles.MODE_RESUME),
        (rf"^{_THEME} (?:dans le|au) point du matin$", regles.MODE_RESUME),
        (rf"^(?:previens|avertis|alerte)-moi (?:tout de suite|directement|immediatement) "
         rf"(?:pour|de|sur) {_THEME}$", regles.MODE_IMMEDIAT),
        (rf"^reparle-moi {_DE}{_THEME}$", regles.MODE_IMMEDIAT),
        (rf"^{_THEME} tout de suite$", regles.MODE_IMMEDIAT),
    )
)
_SILENCE = re.compile(
    r"^(?:silence|ne m'ecris pas|pas de messages?|ne me derange pas) "
    r"(?:de|entre) (?P<debut>\d{1,2}) ?h(?:eures?)? (?:a|et|jusqu'a) (?P<fin>\d{1,2}) ?h(?:eures?)?$"
)
_SANS_SILENCE = re.compile(r"^(?:pas de|aucune?|plus de) (?:plage de )?silence$")
_POINT_DU_MATIN = re.compile(
    r"^(?:le )?(?:point du matin|resume du matin|resume) (?:a|vers) (?P<heure>\d{1,2}) ?h(?:eures?)?$")


def _normaliser(texte: str) -> str:
    brut = unidecode((texte or "").replace("’", "'")).lower().strip()
    return " ".join(re.sub(r"[!.?…;]+", " ", brut).split())


def _theme(dit: str) -> Optional[str]:
    dit = (dit or "").strip()
    for motif, theme in _THEMES_DITS:
        if re.fullmatch(rf"(?:les? |la |l'|des |du |de |d')?(?:{motif})(?: s)?", dit):
            return theme
    return None


def lire_phrase(texte: str) -> Optional[Changement]:
    """[CA9] « arrête de me parler de la météo » → couper la météo ; None si la phrase n'est
    pas un réglage des messages spontanés (elle suit alors son chemin ordinaire)."""
    normal = _normaliser(texte)
    if not normal or len(normal) > 120:
        return None
    if _SANS_SILENCE.match(normal):
        return Changement(REGLAGE_SILENCE, debut=0, fin=0)
    if (trouve := _SILENCE.match(normal)) is not None:
        debut, fin = int(trouve["debut"]), int(trouve["fin"])
        return Changement(REGLAGE_SILENCE, debut=debut, fin=fin) if debut <= 23 and fin <= 23 else None
    if (trouve := _POINT_DU_MATIN.match(normal)) is not None:
        heure = int(trouve["heure"])
        return Changement(REGLAGE_POINT_DU_MATIN, heure=heure) if heure <= 23 else None
    for motif, mode in _FORMES_MODE:
        trouve = motif.match(normal)
        theme = _theme(trouve["theme"]) if trouve is not None else None
        if theme is not None:
            return Changement(REGLAGE_MODE, theme=theme, mode=mode)
    return None
