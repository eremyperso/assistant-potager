"""
app/services/contexte_semis.py — Contexte d'un semis : pépinière ou pleine terre [US-069]
----------------------------------------------------------------------------------------
Un semis suit l'un de deux itinéraires : semé hors sol, en godet ou en barquette,
puis repiqué (filière `semis → mise en godet → plantation`), ou semé directement
en place. Jusqu'ici les deux s'enregistraient sous le même `type_action`, et la
filière ne se reconstituait qu'après coup — jamais pour un semis de pépinière
consulté avant son repiquage.

Ce module est le SEUL endroit où le contexte se lit, se reconnaît, se propose et
se compte. Il ne modifie aucun calcul existant : le stock continue de se déduire
de la parcelle (`Parcelle.est_pepiniere`, US-037) et du chaînage
`origine_graines_id` (US-029, US-065) — exactement comme avant l'US (CA8).

Quatre décisions, et où elles vivent
------------------------------------
1. **Le contexte n'a de sens que pour un semis (CA1).** `contexte_pour_action`
   rend None pour tout autre geste : c'est lui que les points d'écriture de
   `evenements.py` appellent, création comme correction.
2. **On reconnaît ce qui est DIT, on ne le devine pas (CA2).**
   `detecter_contexte` lit une tournure explicite (« en pépinière », « en
   godets », « en pleine terre », « en place », « semis direct »), sans appel
   modèle. « sous abri » n'y figure pas : une serre peut accueillir un semis en
   pleine terre.
3. **Ce qui n'est pas dit se PROPOSE, jamais ne s'impose (CA3).**
   `proposer_contexte` s'appuie sur deux indices et seulement deux : une
   parcelle déclarée pépinière, puis le référentiel d'US-068 quand il ne connaît
   qu'UNE des deux fenêtres de semis. Un référentiel qui connaît les deux, ou
   aucune, ne propose rien — le semis s'enregistre alors sans contexte. Une
   parcelle ordinaire n'est PAS un indice : un semis de pépinière est rattaché à
   une parcelle comme tout événement, ce qui ne le rend pas « en pleine terre ».
4. **La reprise de l'existant ne suppose rien (CA5).** Elle vit dans
   `migrations/migration_v47.sql`, et nulle part ailleurs : un semis suivi d'une
   mise en godet chaînée devient « pépinière », tous les autres restent sans
   contexte. Les tests exécutent CETTE requête, pas une copie.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date as _date, datetime
from typing import Optional

from sqlalchemy.orm import Session
from unidecode import unidecode

from database.models import Evenement, Parcelle
from utils.actions import normalize_action

log = logging.getLogger("potager")

# ── [CA1] Vocabulaire ────────────────────────────────────────────────────────
#: Valeurs stockées, sans accent — comme `Potager.zone_climatique`.
CONTEXTE_PEPINIERE = "pepiniere"
CONTEXTE_PLEINE_TERRE = "pleine_terre"
CONTEXTES: tuple[str, ...] = (CONTEXTE_PEPINIERE, CONTEXTE_PLEINE_TERRE)

LIBELLES_CONTEXTES: dict[str, str] = {
    CONTEXTE_PEPINIERE: "pépinière",
    CONTEXTE_PLEINE_TERRE: "pleine terre",
}

#: [CA6] Le troisième total, explicite — jamais un silence.
SANS_CONTEXTE = "sans_contexte"
LIBELLE_SANS_CONTEXTE = "sans contexte"

#: Seul geste qui porte un contexte.
ACTION_SEMIS = "semis"

#: Ce que la saisie et la correction tolèrent comme VALEUR (pas comme phrase).
_ALIAS_CONTEXTES: dict[str, str] = {
    "pepiniere": CONTEXTE_PEPINIERE, "godet": CONTEXTE_PEPINIERE, "godets": CONTEXTE_PEPINIERE,
    "barquette": CONTEXTE_PEPINIERE, "hors sol": CONTEXTE_PEPINIERE,
    "pleine terre": CONTEXTE_PLEINE_TERRE, "pleine_terre": CONTEXTE_PLEINE_TERRE,
    "pleineterre": CONTEXTE_PLEINE_TERRE, "pleine-terre": CONTEXTE_PLEINE_TERRE,
    "en place": CONTEXTE_PLEINE_TERRE, "place": CONTEXTE_PLEINE_TERRE,
    "direct": CONTEXTE_PLEINE_TERRE, "semis direct": CONTEXTE_PLEINE_TERRE,
}

#: Valeurs qui EFFACENT le contexte à la correction (CA4).
_MOTS_EFFACEMENT = frozenset({"aucun", "aucune", "sans", "sans contexte", "inconnu", "null", "none", ""})

# ── [CA2] Tournures reconnues dans une phrase ────────────────────────────────
# Texte normalisé (minuscules, sans accent). L'article est facultatif : « en
# godets », « dans des godets », « en pleine terre », « directement en terre ».
_MOTIF_PEPINIERE = (
    r"(?:en|dans\s+(?:la|une|ma|des|les|mes))\s+"
    r"(?:pepinieres?|godets?|barquettes?|caissettes?|terrines?|mottes?|plaques?\s+alveolees?)"
    r"|hors\s+sol"
)
_MOTIF_PLEINE_TERRE = (
    r"en\s+pleine[\s-]+terre|(?:directement\s+)?en\s+place|semis\s+direct|semes?\s+direct"
    r"|directement\s+(?:en|dans\s+la)\s+terre"
)
_RE_PEPINIERE = re.compile(rf"\b(?:{_MOTIF_PEPINIERE})\b")
_RE_PLEINE_TERRE = re.compile(rf"\b(?:{_MOTIF_PLEINE_TERRE})\b")

#: [CA4] Mots qui peuvent entourer un contexte dans une correction sans rien
#: corriger d'autre : « non, c'était plutôt en pépinière, pas en pleine terre ».
_MOTS_CORRECTION_NEUTRES = frozenset({
    "non", "si", "en", "fait", "plutot", "c", "etait", "est", "ce", "cetait", "mettre", "mets",
    "passer", "passe", "corriger", "corrige", "modifier", "changer", "le", "la", "un", "une",
    "semis", "seme", "semee", "semes", "semees", "et", "pas", "ou", "mais", "a", "ete", "fut",
    "il", "elle", "ils", "elles", "les", "j", "ai", "je", "l", "contexte", "filiere",
})


def _normaliser(texte: Optional[str]) -> str:
    s = unidecode((texte or "").lower()).replace("’", "'")
    return re.sub(r"\s+", " ", s).strip()


def normaliser_contexte(valeur: Optional[str]) -> Optional[str]:
    """Valeur de contexte → forme stockée, ou None si elle n'en désigne aucune.

    Lève `ValueError` sur une valeur NON VIDE qui ne désigne rien : un contexte
    mal saisi ne doit jamais s'enregistrer silencieusement comme « aucun ».
    """
    if valeur is None:
        return None
    cle = _normaliser(str(valeur)).replace("_", " ").strip()
    if cle in _MOTS_EFFACEMENT:
        return None
    if cle in _ALIAS_CONTEXTES:
        return _ALIAS_CONTEXTES[cle]
    cle_compacte = cle.replace(" ", "_")
    if cle_compacte in CONTEXTES:
        return cle_compacte
    detecte = detecter_contexte(cle)
    if detecte:
        return detecte
    raise ValueError(
        f"Contexte de semis inconnu : « {valeur} » — attendu : pépinière ou pleine terre."
    )


def libelle_contexte(contexte: Optional[str]) -> str:
    return LIBELLES_CONTEXTES.get(contexte or "", LIBELLE_SANS_CONTEXTE)


def detecter_contexte(texte: Optional[str]) -> Optional[str]:
    """[CA2] Contexte EXPLICITEMENT dit dans la phrase, sinon None.

    Une phrase qui dit les deux (« semé en godets puis en pleine terre ») ne
    tranche rien : None, plutôt qu'un choix arbitraire.
    """
    t = _normaliser(texte)
    if not t:
        return None
    pepiniere = bool(_RE_PEPINIERE.search(t))
    pleine_terre = bool(_RE_PLEINE_TERRE.search(t))
    if pepiniere == pleine_terre:
        return None
    return CONTEXTE_PEPINIERE if pepiniere else CONTEXTE_PLEINE_TERRE


def retirer_tournure_contexte(mots: list[str]) -> tuple[list[str], Optional[str]]:
    """[CA2] Pour la grammaire déterministe (US-094) : retire la tournure de
    contexte des mots d'une saisie, pour qu'elle ne reste pas « non attribuée »
    et ne renvoie pas au modèle une phrase que la grammaire sait lire.

    Les mots doivent être déjà normalisés (minuscules, sans accent). Rien n'est
    retiré si la phrase ne tranche pas (voir `detecter_contexte`).
    """
    phrase = " ".join(mots)
    contexte = detecter_contexte(phrase)
    if contexte is None:
        return mots, None
    motif = _RE_PEPINIERE if contexte == CONTEXTE_PEPINIERE else _RE_PLEINE_TERRE
    restant = motif.sub(" ", phrase)
    return restant.split(), contexte


def correction_contexte_seule(texte: Optional[str]) -> Optional[str]:
    """[CA4] « non, c'était en pépinière » → `pepiniere`, sans appel modèle.

    Ne rend un contexte QUE si la phrase ne dit rien d'autre : « c'était 30
    graines en pépinière » corrige aussi une quantité, et passe par le chemin de
    correction habituel (qui lit ensuite le contexte avec `detecter_contexte`).
    « en pépinière, pas en pleine terre » est lu comme une correction vers la
    pépinière : la tournure niée est retirée avant de trancher.
    """
    t = _normaliser(texte)
    if not t:
        return None
    t = re.sub(r"[,.;:!?']", " ", t)
    # La tournure niée (« pas en pleine terre », « et non en godets ») ne dit
    # pas le contexte voulu : on la retire avant de lire l'autre.
    motif_nie = rf"\b(?:pas|non)\s+(?:{_MOTIF_PEPINIERE}|{_MOTIF_PLEINE_TERRE})\b"
    affirme = re.sub(motif_nie, " ", t)
    contexte = detecter_contexte(affirme)
    if contexte is None:
        return None
    reste = _RE_PLEINE_TERRE.sub(" ", _RE_PEPINIERE.sub(" ", affirme))
    if any(mot not in _MOTS_CORRECTION_NEUTRES for mot in reste.split()):
        return None
    return contexte


def contexte_pour_action(action: Optional[str], contexte: Optional[str]) -> Optional[str]:
    """[CA1] Le contexte retenu pour un événement de ce geste : None pour tout
    ce qui n'est pas un semis, quelle que soit la valeur fournie."""
    if normalize_action(action) != ACTION_SEMIS:
        return None
    try:
        return normaliser_contexte(contexte)
    except ValueError:
        log.warning("[US-069] Contexte de semis illisible %r — enregistré sans contexte", contexte)
        return None


def contexte_depuis_saisie(parsed: dict, texte: Optional[str]) -> Optional[str]:
    """[CA1, CA2] Contexte d'un item parsé : celui qu'il porte déjà (grammaire,
    confirmation au bot), sinon celui que dit la phrase. Jamais une proposition
    non confirmée — celle-ci vit dans `_contexte_propose`, lue par le bot seul.

    La CLÉ `contexte_semis` présente, même vide, fait foi : c'est ainsi que le
    bot enregistre « sans préciser » sans que la phrase soit relue derrière lui.
    """
    action = parsed.get("action") or parsed.get("type_action")
    if normalize_action(action) != ACTION_SEMIS:
        return None
    if "contexte_semis" in parsed:
        return contexte_pour_action(action, parsed.get("contexte_semis"))
    return detecter_contexte(texte)


# ── [CA3] Proposition ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Proposition:
    contexte: str
    #: Pourquoi : lu par le jardinier à côté de la proposition.
    motif: str


def proposer_contexte(
    db: Session,
    culture: Optional[str],
    potager_id: Optional[int],
    parcelle: Optional[Parcelle] = None,
) -> Optional[Proposition]:
    """[CA3] Contexte le plus probable d'un semis NON précisé, ou None.

    Deux indices, dans cet ordre :
      1. la parcelle citée est déclarée pépinière → pépinière ;
      2. le référentiel de calendrier (US-068) ne connaît, pour cette culture,
         qu'une seule des deux fenêtres de semis dans la zone du potager (ou une
         durée de repiquage sans aucune fenêtre de pleine terre).
    Rien d'autre : un référentiel qui connaît les deux fenêtres, ou aucune, ne
    tranche pas — et ne lève jamais (CA9).
    """
    if parcelle is not None and getattr(parcelle, "est_pepiniere", False):
        return Proposition(CONTEXTE_PEPINIERE, f"la parcelle {parcelle.nom} est une pépinière")
    if not culture:
        return None
    try:
        from app.services import calendrier_cultural as svc_calendrier

        calendrier = svc_calendrier.lire_calendrier(db, culture, potager_id)
    except Exception as e:  # CA9 : une proposition absente ne bloque rien
        log.warning("[US-069] Proposition de contexte impossible (%s)", type(e).__name__)
        return None
    if not calendrier.culture_connue:
        return None

    pepiniere = pleine_terre = False
    for it in calendrier.itineraires:
        if it.fenetre(svc_calendrier.PHASE_SEMIS_PEPINIERE):
            pepiniere = True
        if it.fenetre(svc_calendrier.PHASE_SEMIS_PLEINE_TERRE):
            pleine_terre = True
        repiquage = it.duree(svc_calendrier.ETAPE_REPIQUAGE)
        if repiquage is not None and repiquage.renseignee:
            pepiniere = True
    if pepiniere == pleine_terre:
        return None
    if pepiniere:
        return Proposition(CONTEXTE_PEPINIERE, f"le calendrier de la culture « {culture} » la sème en pépinière")
    return Proposition(CONTEXTE_PLEINE_TERRE, f"le calendrier de la culture « {culture} » la sème en pleine terre")


# ── [CA7] Fenêtre conseillée applicable ──────────────────────────────────────
def phase_du_contexte(contexte: Optional[str]) -> Optional[str]:
    """[CA7] Phase du référentiel d'US-068 que désigne un contexte, ou None."""
    from app.services import calendrier_cultural as svc_calendrier

    return {
        CONTEXTE_PEPINIERE: svc_calendrier.PHASE_SEMIS_PEPINIERE,
        CONTEXTE_PLEINE_TERRE: svc_calendrier.PHASE_SEMIS_PLEINE_TERRE,
    }.get(contexte or "")


def fenetre_conseillee(db: Session, evenement: Evenement):
    """[CA7] Fenêtre de semis du référentiel qui s'applique à CE semis — celle de
    son contexte, dans la zone de son potager — et qui sert d'ancrage à la
    projection d'US-070. None si le semis n'a pas de contexte (US-070 applique
    alors son mode dégradé), ou si le référentiel n'a pas cette fenêtre : rien
    n'est emprunté à l'autre filière.
    """
    phase = phase_du_contexte(getattr(evenement, "contexte_semis", None))
    if phase is None or evenement.type_action != ACTION_SEMIS or not evenement.culture:
        return None
    from app.services import calendrier_cultural as svc_calendrier

    calendrier = svc_calendrier.lire_calendrier(db, evenement.culture, evenement.potager_id)
    for it in calendrier.itineraires:
        fenetre = it.fenetre(phase)
        if fenetre is not None:
            return fenetre
    return None


# ── [CA6] Statistiques ───────────────────────────────────────────────────────
@dataclass
class TotauxContexte:
    culture: str
    saison: int
    pepiniere: int = 0
    pleine_terre: int = 0
    sans_contexte: int = 0
    #: Quantités par unité — jamais additionnées entre unités (US-037 / CA2).
    quantites: dict[str, dict[str, float]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.pepiniere + self.pleine_terre + self.sans_contexte

    def en_dict(self) -> dict:
        return {
            "saison": self.saison,
            "culture": self.culture,
            CONTEXTE_PEPINIERE: self.pepiniere,
            CONTEXTE_PLEINE_TERRE: self.pleine_terre,
            SANS_CONTEXTE: self.sans_contexte,
            "total": self.total,
            "quantites": self.quantites,
        }


def semis_par_contexte(
    db: Session,
    potager_id: int,
    date_ref: Optional[_date] = None,
    saison: Optional[int] = None,
) -> list[TotauxContexte]:
    """[CA6] Trois totaux de semis par culture et par saison : pépinière, pleine
    terre, et sans contexte — ce dernier compté, jamais omis (CA9).

    La saison est l'année du semis. Un semis sans date n'a pas de saison
    connaissable : il est écarté plutôt que rattaché à une année supposée.
    `date_ref` limite aux semis antérieurs (US-030), `saison` à une année.
    """
    requete = (
        db.query(Evenement.culture, Evenement.date, Evenement.contexte_semis, Evenement.quantite, Evenement.unite)
        .filter(Evenement.potager_id == potager_id)
        .filter(Evenement.type_action == ACTION_SEMIS)
        .filter(Evenement.culture.isnot(None))
        .filter(Evenement.date.isnot(None))
    )
    if date_ref is not None:
        requete = requete.filter(Evenement.date <= datetime.combine(date_ref, datetime.max.time()))

    totaux: dict[tuple[int, str], TotauxContexte] = {}
    for culture, date_semis, contexte, quantite, unite in requete.all():
        annee = date_semis.year
        if saison is not None and annee != saison:
            continue
        cle_culture = culture.strip().lower()
        ligne = totaux.setdefault((annee, cle_culture), TotauxContexte(culture=cle_culture, saison=annee))
        cle = contexte if contexte in CONTEXTES else SANS_CONTEXTE
        if cle == CONTEXTE_PEPINIERE:
            ligne.pepiniere += 1
        elif cle == CONTEXTE_PLEINE_TERRE:
            ligne.pleine_terre += 1
        else:
            ligne.sans_contexte += 1
        if quantite:
            par_unite = ligne.quantites.setdefault(cle, {})
            u = unite or "graines"
            par_unite[u] = par_unite.get(u, 0.0) + float(quantite)

    return sorted(totaux.values(), key=lambda t: (-t.saison, t.culture))


def formater_semis_par_contexte_telegram(lignes: list[TotauxContexte], saison: int) -> list[str]:
    """[CA6] Bloc Markdown du bot : trois totaux par culture, le « sans contexte »
    affiché dès qu'il existe. Liste vide si la saison n'a aucun semis."""
    retenues = [l for l in lignes if l.saison == saison]
    if not retenues:
        return []
    sortie = [f"\n🧭 *Semis par filière — saison {saison} :*"]
    for l in retenues:
        parties = [f"🪴 {l.pepiniere} en pépinière", f"🌿 {l.pleine_terre} en pleine terre"]
        if l.sans_contexte:
            parties.append(f"❔ {l.sans_contexte} sans contexte")
        sortie.append(f"  • {l.culture} : " + " · ".join(parties))
    return sortie
