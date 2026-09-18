"""
date_utils.py — Dates : conversion de la valeur extraite, et grammaire
d'ancrage temporel déterministe.

Deux responsabilités distinctes :

* `parse_date` — convertit la date déjà extraite (par le modèle ou par le
  parseur déterministe) en `datetime` exploitable par PostgreSQL. Gère
  "2026-03-09" (ISO) et None (→ aujourd'hui).
* `resoudre_ancrage_temporel` — [US-094 / CA2] reconnaît, **sans aucun appel
  au modèle**, les expressions de date courantes d'une phrase dictée et rend
  la date ISO correspondante. Toute expression non couverte est signalée comme
  telle, pour que l'appelant bascule la phrase entière sur le repli LLM plutôt
  que d'inventer une date.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from typing import Optional

from unidecode import unidecode


def parse_date(val) -> datetime:
    """
    Retourne un datetime exploitable pour PostgreSQL.
    - val = "2026-03-09" → datetime(2026, 3, 9)
    - val = None ou invalide → datetime.today() (sécurité)
    """
    if not val:
        return datetime.combine(date.today(), datetime.min.time())
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d")
    except ValueError:
        return datetime.combine(date.today(), datetime.min.time())


# ─────────────────────────────────────────────────────────────────────────────
# [US-094 / CA2] Grammaire d'ancrage temporel — zéro appel modèle
# -----------------------------------------------------------------------------
# Précision avant couverture (arbitrage tranché de l'US) : la grammaire ne
# reconnaît QUE des formes non ambiguës, et signale explicitement quand une
# phrase porte un vocabulaire temporel qu'elle ne sait pas résoudre. Inventer
# une date est le défaut mesuré le plus coûteux de l'application
# (docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §8.1 : la date est le champ le
# plus corrigé, 27,5 % des corrections) — mieux vaut un appel au modèle.
# ─────────────────────────────────────────────────────────────────────────────

ANCRAGE_ABSENT  = "absent"    # aucune expression temporelle dans la phrase
ANCRAGE_RESOLU  = "resolu"    # expression reconnue et datée
ANCRAGE_INCONNU = "inconnu"   # vocabulaire temporel présent, non résoluble

# Origine de la date résolue, au sens de la décision d'instrumentation
# `date_source` (docs/decisions-prerequis-vague2-piste-a.md §4 ; colonne livrée
# par migration_v35 / US-169). Ces deux valeurs sont produites par CETTE
# grammaire (CA5) : elle seule sait si l'ancrage était dicté en clair ou
# relatif.
SOURCE_EXPLICITE        = "explicite"
SOURCE_RELATIVE_RESOLUE = "relative_resolue"

# [US-169 / CA3] Taxonomie `date_source` — arrêtée avant l'implémentation.
# Deux valeurs de plus, produites hors de cette grammaire (au site
# d'écriture, `app.services.evenements._date_source`) :
#
# * SOURCE_PRESUMEE : aucun ancrage dicté, la date retombe sur la convention
#   « aujourd'hui ». Commune aux deux chemins d'écriture — déterministe quand
#   `resoudre_ancrage_temporel` rend ANCRAGE_ABSENT, modèle quand l'item ne
#   porte aucune date (CA6, CA7 : jamais confondue avec NULL/« inconnu »).
# * SOURCE_MODELE_INCERTAIN : le chemin modèle a rendu une date, mais ce
#   chemin ne dit jamais s'il l'a lue en clair ou déduite (table du CA3 dans
#   l'US) — écrire SOURCE_EXPLICITE ou SOURCE_RELATIVE_RESOLUE ici serait une
#   affirmation que rien ne fonde. Englobe délibérément le cas « ancrage vu
#   mais illisible » (ANCRAGE_INCONNU) : cette phrase part elle aussi au
#   modèle, qui ne sait pas plus distinguer explicite/relatif pour elle que
#   pour toute autre — un cinquième repère n'ajouterait qu'un mot pour dire
#   la même incertitude. Le distinguer supposerait de faire transiter l'état
#   du repli déterministe jusqu'à l'appel modèle, explicitement hors
#   périmètre (CA6, notes « hors périmètre » de l'US).
SOURCE_PRESUMEE          = "presumee"
SOURCE_MODELE_INCERTAIN  = "modele_incertain"


@dataclass(frozen=True)
class Ancrage:
    """Résultat de la lecture temporelle d'une phrase."""

    statut: str                      # ANCRAGE_ABSENT | ANCRAGE_RESOLU | ANCRAGE_INCONNU
    date_iso: Optional[str] = None   # renseignée seulement si statut == ANCRAGE_RESOLU
    source: Optional[str] = None     # SOURCE_EXPLICITE | SOURCE_RELATIVE_RESOLUE
    expression: str = ""             # fragment reconnu, à retirer de la phrase
    debut: int = -1                  # bornes du fragment dans le texte normalisé
    fin: int = -1


_MOIS: dict[str, int] = {
    "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
    "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
    "decembre": 12,
}

_JOURS_SEMAINE: dict[str, int] = {
    "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
    "vendredi": 4, "samedi": 5, "dimanche": 6,
}

# Nombres écrits en toutes lettres — bornés volontairement à ce qu'une phrase
# de potager emploie réellement (« il y a trois jours », « neuf plants »).
NOMBRES_LETTRES: dict[str, int] = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
    "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
    "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
}

# Vocabulaire qui SIGNALE une intention temporelle sans que la grammaire sache
# forcément la dater. Sa présence après un échec de résolution déclenche le
# repli LLM (CA2) plutôt qu'un silence qui vaudrait « aujourd'hui ».
_MOTS_TEMPORELS: tuple[str, ...] = (
    tuple(_MOIS) + tuple(_JOURS_SEMAINE) + (
        "hier", "aujourd", "matin", "midi", "soir", "nuit",
        "semaine", "semaines", "mois", "annee", "annees", "an", "ans",
        "dernier", "derniere", "derniers", "dernieres", "prochain", "prochaine",
        "veille", "depuis", "recemment", "jour", "jours", "date",
    )
)


def _normaliser(texte: str) -> str:
    """Minuscules sans accents, apostrophes uniformisées — même esprit que la
    normalisation déjà en place sur les noms de parcelles et de cultures."""
    s = unidecode((texte or "").lower()).replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def _iso(jour: date) -> str:
    return jour.isoformat()


def _dernier_jour_semaine(cible: int, aujourd_hui: date) -> date:
    """« samedi dernier » — la dernière occurrence STRICTEMENT passée."""
    ecart = (aujourd_hui.weekday() - cible) % 7 or 7
    return aujourd_hui - timedelta(days=ecart)


def _prochain_jour_semaine(cible: int, aujourd_hui: date, strict: bool = False) -> date:
    """[US-179] « samedi » — la prochaine occurrence, aujourd'hui compris.

    `strict` la veut STRICTEMENT à venir : c'est « samedi prochain », dit un
    samedi, qui ne désigne pas le jour même.
    """
    ecart = (cible - aujourd_hui.weekday()) % 7
    if strict and ecart == 0:
        ecart = 7
    return aujourd_hui + timedelta(days=ecart)


# Les motifs sont essayés dans cet ordre : le plus spécifique d'abord
# (« avant-hier » avant « hier », sans quoi « hier » mordrait dedans).
_MOTIF_AVANT_HIER   = re.compile(r"\bavant[-\s]?hier\b")
_MOTIF_HIER         = re.compile(r"\bhier\b")
_MOTIF_AUJOURDHUI   = re.compile(r"\b(aujourd'hui|aujourd hui|ce jour|ce matin|cet apres[-\s]midi|ce soir)\b")
_MOTIF_IL_Y_A_JOURS = re.compile(r"\bil y a (\d{1,3}|" + "|".join(NOMBRES_LETTRES) + r")\s+jours?\b")
_MOTIF_SEMAINE_DERN = re.compile(r"\b(?:la\s+)?semaine\s+derniere\b")
_MOTIF_JOUR_DERNIER = re.compile(r"\b(" + "|".join(_JOURS_SEMAINE) + r")\s+dernier\b")
# Le « dernier » qui suit parfois une date dictée (« le 25/05 dernier », « le 6
# mars dernier ») est avalé avec elle : laissé en place, il resterait un mot
# inexpliqué et ferait basculer toute la phrase sur le repli.
_MOTIF_DATE_NUM     = re.compile(
    r"\b(?:le\s+)?(\d{1,2})[/\-](\d{1,2})(?:[/\-](\d{2,4}))?(?:\s+derniers?)?\b"
)
_MOTIF_DATE_MOIS    = re.compile(
    r"\b(?:le\s+)?(\d{1,2}|1er|premier)\s+(" + "|".join(_MOIS) + r")(?:\s+(\d{4}))?(?:\s+derniers?)?\b"
)


# ─────────────────────────────────────────────────────────────────────────────
# [US-179] Ancrages TOURNÉS VERS L'AVENIR
# -----------------------------------------------------------------------------
# Toute la grammaire ci-dessus date le PASSÉ : elle sert à rattacher un geste
# déjà fait (« j'ai semé samedi »), et `_construire` refuse explicitement une
# date future. « Je peux semer samedi ? » pose la question inverse, et aucune
# des deux lectures ne peut être la bonne partout — « samedi » vaut la dernière
# occurrence pour un geste fait, la prochaine pour un geste à faire.
#
# D'où un mode, jamais un changement de comportement : `futur=True` est demandé
# par l'appelant qui SAIT poser une question d'avenir (US-179). Sans lui, la
# grammaire se comporte exactement comme avant — aucun appelant existant n'est
# touché, et il n'y a toujours qu'une seule grammaire de dates dans le projet.
# ─────────────────────────────────────────────────────────────────────────────
_MOTIF_APRES_DEMAIN  = re.compile(r"\bapres[-\s]?demain\b")
_MOTIF_DEMAIN        = re.compile(r"\bdemain\b")
_MOTIF_MAINTENANT    = re.compile(r"\b(maintenant|tout de suite|en ce moment|ces jours ci|la tout de suite)\b")
_MOTIF_DANS_JOURS    = re.compile(r"\bdans (\d{1,3}|" + "|".join(NOMBRES_LETTRES) + r")\s+jours?\b")
_MOTIF_DANS_SEMAINES = re.compile(r"\bdans (\d{1,2}|" + "|".join(NOMBRES_LETTRES) + r")\s+semaines?\b")
_MOTIF_SEMAINE_PROCH = re.compile(r"\b(?:la\s+)?semaine\s+prochaine\b")
#: « cette semaine », « en ce moment » — la question porte sur le jour où elle
#: est posée. Une semaine n'est pas une date : c'est aujourd'hui qui la borne,
#: et étaler le score sur sept jours inventerait une précision qu'on n'a pas.
_MOTIF_CETTE_SEMAINE = re.compile(r"\b(?:cette\s+semaine|ce\s+mois\s*ci)\b")
# « ce week-end » : le SAMEDI qui vient. Le dimanche est l'autre moitié du
# week-end, mais c'est le samedi que le jardinier a devant lui quand il pose la
# question, et une fourchette de deux jours ne changerait aucun score.
_MOTIF_WEEK_END      = re.compile(r"\b(?:ce\s+|le\s+|du\s+)?week[-\s]?end\b")
_MOTIF_JOUR_PROCHAIN = re.compile(r"\b(" + "|".join(_JOURS_SEMAINE) + r")\s+(?:prochain|qui vient)\b")
#: « samedi » tout court — la prochaine occurrence. Écarte « samedi dernier »,
#: que `_resoudre_relatif` date déjà, et qui resterait sinon amputé de son mot.
_MOTIF_JOUR_SEUL     = re.compile(
    r"\b(?:ce\s+)?(" + "|".join(_JOURS_SEMAINE) + r")\b(?!\s+dernier)"
)


def _resoudre_futur(texte: str, aujourd_hui: date) -> Optional[Ancrage]:
    """[US-179] Ancrages à venir — « demain », « dans dix jours », « ce week-end »,
    « samedi ». Essayés du plus spécifique au plus général, même règle qu'au-dessus."""
    m = _MOTIF_APRES_DEMAIN.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui + timedelta(days=2)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_DEMAIN.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui + timedelta(days=1)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_MAINTENANT.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_DANS_JOURS.search(texte)
    if m:
        brut = m.group(1)
        nb = int(brut) if brut.isdigit() else NOMBRES_LETTRES[brut]
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui + timedelta(days=nb)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_DANS_SEMAINES.search(texte)
    if m:
        brut = m.group(1)
        nb = int(brut) if brut.isdigit() else NOMBRES_LETTRES[brut]
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui + timedelta(days=7 * nb)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_SEMAINE_PROCH.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui + timedelta(days=7)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_CETTE_SEMAINE.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_WEEK_END.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(_prochain_jour_semaine(_JOURS_SEMAINE["samedi"], aujourd_hui)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_JOUR_PROCHAIN.search(texte)
    if m:
        cible = _JOURS_SEMAINE[m.group(1)]
        return Ancrage(ANCRAGE_RESOLU, _iso(_prochain_jour_semaine(cible, aujourd_hui, strict=True)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_JOUR_SEUL.search(texte)
    if m:
        cible = _JOURS_SEMAINE[m.group(1)]
        return Ancrage(ANCRAGE_RESOLU, _iso(_prochain_jour_semaine(cible, aujourd_hui)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    return None


def _resoudre_relatif(texte: str, aujourd_hui: date) -> Optional[Ancrage]:
    """Ancrages relatifs — « hier », « avant-hier », « il y a N jours »,
    « la semaine dernière », « samedi dernier »."""
    m = _MOTIF_AVANT_HIER.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui - timedelta(days=2)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_HIER.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui - timedelta(days=1)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_AUJOURDHUI.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_IL_Y_A_JOURS.search(texte)
    if m:
        brut = m.group(1)
        nb = int(brut) if brut.isdigit() else NOMBRES_LETTRES[brut]
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui - timedelta(days=nb)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_SEMAINE_DERN.search(texte)
    if m:
        return Ancrage(ANCRAGE_RESOLU, _iso(aujourd_hui - timedelta(days=7)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    m = _MOTIF_JOUR_DERNIER.search(texte)
    if m:
        cible = _JOURS_SEMAINE[m.group(1)]
        return Ancrage(ANCRAGE_RESOLU, _iso(_dernier_jour_semaine(cible, aujourd_hui)),
                       SOURCE_RELATIVE_RESOLUE, m.group(0), m.start(), m.end())

    return None


def _construire(
    annee: int, mois: int, jour: int, aujourd_hui: date,
    futur: bool = False, annee_dite: bool = False,
) -> Optional[date]:
    """Construit la date, ou None si elle est impossible ou du mauvais côté.

    Par défaut (un geste DÉJÀ FAIT), une date future n'est jamais présumée : le
    garde-fou d'US-049 la refuserait de toute façon, et une année sous-entendue
    mal devinée est exactement le genre d'approximation que CA6 interdit.

    [US-179] En mode `futur` — un geste À FAIRE — la lecture s'inverse : « le
    20 mai » demandé en septembre désigne le 20 mai PROCHAIN, et l'année
    sous-entendue bascule d'un an. Une année DITE, elle, ne se corrige jamais :
    « le 20 mai 2025 » pour un semis à venir est une contradiction, et on rend
    la main plutôt que de la trancher."""
    try:
        candidate = date(annee, mois, jour)
    except ValueError:
        return None
    if futur:
        if candidate >= aujourd_hui:
            return candidate
        if annee_dite:
            return None
        try:
            return date(annee + 1, mois, jour)
        except ValueError:
            return None
    return candidate if candidate <= aujourd_hui else None


def _resoudre_absolu(texte: str, aujourd_hui: date, futur: bool = False) -> Optional[Ancrage]:
    """Dates explicitement dictées — « le 25/05 », « le 21/07/2026 »,
    « le 14 juillet », « le 1er juin 2025 ».

    [US-179] `futur` inverse le sens de lecture de l'année sous-entendue."""
    m = _MOTIF_DATE_NUM.search(texte)
    if m:
        jour, mois = int(m.group(1)), int(m.group(2))
        brut_annee = m.group(3)
        if brut_annee is None:
            annee = aujourd_hui.year
        else:
            annee = int(brut_annee)
            if annee < 100:
                annee += 2000
        resolue = _construire(annee, mois, jour, aujourd_hui, futur, brut_annee is not None)
        if resolue is None:
            # Année sous-entendue incohérente, jour/mois impossibles, date
            # du mauvais côté : on ne devine pas, on rend la main au modèle.
            return Ancrage(ANCRAGE_INCONNU, expression=m.group(0), debut=m.start(), fin=m.end())
        return Ancrage(ANCRAGE_RESOLU, _iso(resolue), SOURCE_EXPLICITE,
                       m.group(0), m.start(), m.end())

    m = _MOTIF_DATE_MOIS.search(texte)
    if m:
        brut_jour = m.group(1)
        jour = 1 if brut_jour in ("1er", "premier") else int(brut_jour)
        mois = _MOIS[m.group(2)]
        annee = int(m.group(3)) if m.group(3) else aujourd_hui.year
        resolue = _construire(annee, mois, jour, aujourd_hui, futur, m.group(3) is not None)
        if resolue is None:
            return Ancrage(ANCRAGE_INCONNU, expression=m.group(0), debut=m.start(), fin=m.end())
        return Ancrage(ANCRAGE_RESOLU, _iso(resolue), SOURCE_EXPLICITE,
                       m.group(0), m.start(), m.end())

    return None


def resoudre_ancrage_temporel(
    texte: str, aujourd_hui: Optional[date] = None, futur: bool = False,
) -> Ancrage:
    """[US-094 / CA2] Lit l'ancrage temporel d'une phrase, sans appel au modèle.

    Trois issues, et trois seulement :

    * `ANCRAGE_RESOLU`  — une expression couverte a été reconnue et datée ;
      `expression` porte le fragment à retirer de la phrase avant d'en extraire
      les autres champs.
    * `ANCRAGE_ABSENT`  — la phrase ne contient aucun vocabulaire temporel.
      L'appelant applique alors la convention du projet (date du jour), qui est
      un choix de conception assumé, pas un défaut.
    * `ANCRAGE_INCONNU` — la phrase parle bien de temps, mais dans une forme que
      cette grammaire ne sait pas dater (« il y a une semaine », « en juin
      2023 », « le mois dernier »). L'appelant DOIT basculer la phrase entière
      sur le repli LLM : c'est précisément le cas où présumer coûte cher.

    `aujourd_hui` n'est là que pour rendre les tests déterministes.

    [US-179] `futur=True` est demandé par l'appelant qui pose une question
    d'AVENIR (« je peux semer samedi ? ») : « samedi » y vaut la prochaine
    occurrence et non la dernière, « le 20 mai » le 20 mai prochain, et le
    vocabulaire « demain / dans dix jours / ce week-end » s'ouvre. Sans lui,
    rien ne change pour les appelants qui datent un geste déjà fait.
    """
    aujourd_hui = aujourd_hui or date.today()
    normalise = _normaliser(texte)
    if not normalise:
        return Ancrage(ANCRAGE_ABSENT)

    # L'absolu d'abord : « le 6 mars dernier » porte à la fois une date
    # explicite et le mot « dernier ». C'est la date dictée qui fait foi.
    # L'absolu d'abord, puis — en mode futur seulement — les ancrages à venir,
    # avant les ancrages passés qu'ils ne recouvrent jamais (« samedi dernier »
    # reste daté par `_resoudre_relatif`).
    ancrage = _resoudre_absolu(normalise, aujourd_hui, futur)
    if ancrage is not None:
        return ancrage
    if futur:
        ancrage = _resoudre_futur(normalise, aujourd_hui)
        if ancrage is not None:
            return ancrage
    ancrage = _resoudre_relatif(normalise, aujourd_hui)
    if ancrage is not None:
        return ancrage

    if any(re.search(rf"\b{re.escape(mot)}", normalise) for mot in _MOTS_TEMPORELS):
        return Ancrage(ANCRAGE_INCONNU)

    return Ancrage(ANCRAGE_ABSENT)
