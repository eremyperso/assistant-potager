"""
app/services/pilotage/agregats.py — Les agrégats de pilotage sur `conso_tokens` [US-310]
========================================================================================
Source UNIQUE des chiffres de consommation : les routes `/admin/pilotage/...`, et, derrière
elles, les vues de la PWA d'administration (US-312 à US-315), les seuils d'alerte (US-316) et le
bilan périodique (US-317) lisent tous ici. Une seule définition de « un appel », « un jeton
d'entrée », « le taux de cache » : aucun écran n'a sa propre arithmétique.

Principes (décisions D7, D9, D11 du cadrage) :
- **Zéro appel à un modèle** [CA9]. Les percentiles sont calculés en Python, par la méthode du
  rang le plus proche de `metriques_routage._p95` : identiques sous SQLite et PostgreSQL.
- **Provenance** [CA5] : sans filtre explicite, seuls `usage` et `fond` sont comptés. Les mesures,
  les tests et l'historique antérieur à la colonne n'entrent jamais dans un chiffre d'usage par
  accident.
- **Unité** [CA6] : les jetons ne sont sommés que sur les lignes d'unité `jeton`. Les secondes
  d'audio (dictée) et les caractères (voix) sont des mesures distinctes, jamais additionnées.
- **Coût** [US-309] : somme des `cout_micro_eur` figés à l'écriture ; `None` (jamais 0) quand
  aucune ligne n'est chiffrable, et le nombre de lignes non chiffrées est toujours rendu.
- **Lecture de tous les potagers** [CA8] : `conso_tokens` n'est pas sous RLS (voir
  `docs/domaines/pilotage-llm.md`). Cette lecture hors périmètre de potager passe par
  `lecture_toute_la_plateforme()`, explicite et testée, qui REFUSE de s'exécuter si la table
  venait à recevoir une politique RLS — jamais par un `tenant_scope` factice.

Toute la lecture passe par `_executer()` et toute l'addition par `_Cumul` : c'est ce qui rend les
routes cohérentes entre elles à l'unité près. Les sommes et les décomptes sont faits par la base
(GROUP BY, portable SQLite ↔ PostgreSQL) ; seuls les percentiles — médiane, P95 — se calculent en
Python, sur une seule colonne ramenée, car SQLite n'a pas de percentile natif.
"""
from __future__ import annotations

import logging
import math
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterator, Optional, Sequence

from sqlalchemy import case, extract, func, text
from sqlalchemy.orm import Session

from database.models import ConsoTokens, Potager, User
from llm import contexte_appel
from llm.passerelle import UNITE_CARACTERE, UNITE_JETON, UNITE_SECONDE

log = logging.getLogger("potager")

MICRO = 1_000_000

# ─────────────────────────────────────────────────────────────────────────────
# Vocabulaires
# ─────────────────────────────────────────────────────────────────────────────

#: [CA5] Sans filtre de provenance, seuls ces deux-là sont comptés.
PROVENANCES_PAR_DEFAUT: tuple[str, ...] = (
    contexte_appel.PROVENANCE_USAGE,
    contexte_appel.PROVENANCE_FOND,
)

#: Dimensions d'une série [CA2] → colonne de `conso_tokens`.
DIMENSIONS_SERIE: dict[str, str] = {
    "modele": "modele",
    "appel_type": "appel_type",
    "canal": "canal",
    "provenance": "provenance",
    "issue": "issue",
    "version": "version_app",
}

#: Dimensions d'une ventilation [CA3] : celles des séries, plus le potager et l'utilisateur.
DIMENSIONS_VENTILATION: dict[str, str] = {
    **DIMENSIONS_SERIE,
    "potager": "potager_id",
    "utilisateur": "user_id",
}

#: Mesures additives, sommables jour par jour et regroupables par dimension.
MESURES: tuple[str, ...] = (
    "appels",
    "jetons_entree",
    "jetons_sortie",
    "jetons_cache",
    "secondes_audio",
    "caracteres",
    "cout_micro_eur",
)

PAS_JOUR = "jour"
PAS_HEURE = "heure"

#: Durée de période par défaut (jours) quand aucune borne n'est donnée.
PERIODE_DEFAUT_JOURS = 7
#: Garde-fou : une période plus longue est refusée (la lecture est en mémoire).
PERIODE_MAX_JOURS = 400

CLE_ABSENTE = "(aucun)"


class FiltreInvalideError(ValueError):
    """Un filtre ou un paramètre hors vocabulaire : la route le rend en 422."""


class LectureHorsPerimetreError(RuntimeError):
    """`conso_tokens` est protégée par RLS : la lecture de tous les potagers est refusée."""


# ─────────────────────────────────────────────────────────────────────────────
# Lecture hors périmètre de potager [CA8]
# ─────────────────────────────────────────────────────────────────────────────

def table_sous_rls(db: Session) -> bool:
    """Vrai si PostgreSQL protège `conso_tokens` par une politique RLS.

    SQLite (tests) ne connaît pas la RLS : toujours faux. Lit `pg_class.relrowsecurity`, pas
    de présomption sur les migrations."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return False
    actif = db.execute(
        text("SELECT relrowsecurity FROM pg_class WHERE oid = 'conso_tokens'::regclass")
    ).scalar()
    return bool(actif)


@contextmanager
def lecture_toute_la_plateforme(db: Session) -> Iterator[None]:
    """[CA8] Le chemin explicite de la lecture sur tous les potagers.

    L'administrateur de la plateforme pilote la consommation de TOUS les potagers : aucun
    filtre `potager_id` n'est appliqué, par construction. Ce bloc ne contourne rien : il
    constate que la table n'est pas sous RLS (sinon PostgreSQL ne rendrait que le potager du
    scope, ou échouerait) et REFUSE d'aller plus loin si ce n'est plus vrai. Il ne pose
    jamais de `tenant_scope` pour se faire passer pour un potager.
    """
    if table_sous_rls(db):
        raise LectureHorsPerimetreError(
            "conso_tokens est protégée par RLS : la lecture de tous les potagers exige une "
            "décision explicite (rôle dédié), pas un contournement de tenant_scope [US-043]."
        )
    log.info("[pilotage] lecture de conso_tokens sur tous les potagers (administrateur)")
    yield


# ─────────────────────────────────────────────────────────────────────────────
# Filtres et périodes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Filtres:
    """Le périmètre d'une lecture. `depuis` et `jusqu_a` sont des dates INCLUSES."""
    depuis: date
    jusqu_a: date
    provenances: tuple[str, ...] = PROVENANCES_PAR_DEFAUT
    canal: Optional[str] = None
    modele: Optional[str] = None
    appel_type: Optional[str] = None
    potager_id: Optional[int] = None
    #: [US-319] Un seul jardinier (fiche d'un jardinier) ; absent des routes et de `vers_dict`.
    user_id: Optional[int] = None

    @property
    def jours(self) -> int:
        return (self.jusqu_a - self.depuis).days + 1

    def periode_precedente(self) -> "Filtres":
        """La période de même durée qui précède immédiatement, mêmes autres filtres."""
        duree = timedelta(days=self.jours)
        return Filtres(
            depuis=self.depuis - duree, jusqu_a=self.depuis - timedelta(days=1),
            provenances=self.provenances, canal=self.canal, modele=self.modele,
            appel_type=self.appel_type, potager_id=self.potager_id, user_id=self.user_id,
        )

    def vers_dict(self) -> dict:
        return {
            "depuis": self.depuis.isoformat(),
            "jusqu_a": self.jusqu_a.isoformat(),
            "jours": self.jours,
            "provenances": list(self.provenances),
            "canal": self.canal,
            "modele": self.modele,
            "appel_type": self.appel_type,
            "potager_id": self.potager_id,
        }


def construire_filtres(
    *,
    depuis: Optional[date] = None,
    jusqu_a: Optional[date] = None,
    provenance: Optional[str] = None,
    canal: Optional[str] = None,
    modele: Optional[str] = None,
    appel_type: Optional[str] = None,
    potager_id: Optional[int] = None,
    aujourd_hui: Optional[date] = None,
) -> Filtres:
    """Valide les paramètres d'une route et rend le `Filtres` correspondant.

    Sans borne : les `PERIODE_DEFAUT_JOURS` derniers jours, aujourd'hui compris. Une seule borne
    donnée : l'autre se déduit (même durée). `provenance` accepte plusieurs valeurs séparées par
    une virgule ; absente, elle vaut `usage` + `fond` [CA5]."""
    fin_du_jour = aujourd_hui or date.today()
    if jusqu_a is None:
        jusqu_a = fin_du_jour if depuis is None else max(depuis, fin_du_jour)
    if depuis is None:
        depuis = jusqu_a - timedelta(days=PERIODE_DEFAUT_JOURS - 1)
    if depuis > jusqu_a:
        raise FiltreInvalideError("`depuis` doit précéder `jusqu_a`")
    if (jusqu_a - depuis).days + 1 > PERIODE_MAX_JOURS:
        raise FiltreInvalideError(f"période limitée à {PERIODE_MAX_JOURS} jours")

    provenances = PROVENANCES_PAR_DEFAUT
    if provenance is not None and provenance.strip():
        demandees = tuple(dict.fromkeys(p.strip() for p in provenance.split(",") if p.strip()))
        inconnues = [p for p in demandees if p not in contexte_appel.PROVENANCES]
        if inconnues:
            raise FiltreInvalideError(
                f"provenance inconnue : {', '.join(inconnues)} "
                f"(attendu parmi {', '.join(sorted(contexte_appel.PROVENANCES))})"
            )
        provenances = demandees

    if canal is not None and canal not in contexte_appel.CANAUX:
        raise FiltreInvalideError(
            f"canal inconnu : {canal} (attendu parmi {', '.join(sorted(contexte_appel.CANAUX))})"
        )
    return Filtres(
        depuis=depuis, jusqu_a=jusqu_a, provenances=provenances,
        canal=canal or None, modele=(modele or None), appel_type=(appel_type or None),
        potager_id=potager_id,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Arithmétique
# ─────────────────────────────────────────────────────────────────────────────

def percentile(valeurs: Sequence[float], q: float) -> Optional[float]:
    """Percentile `q` (0 < q ≤ 1), méthode du rang le plus proche — celle de `_p95` de
    `metriques_routage` [CA9]. `None` sans valeur. Aucune fonction SQL propre à un moteur."""
    if not valeurs:
        return None
    triees = sorted(valeurs)
    rang = max(1, math.ceil(q * len(triees)))
    return float(triees[rang - 1])


class _Cumul:
    """Les mesures d'un groupe de lignes. Un seul endroit où l'on additionne [US-310].

    Alimenté par les lignes agrégées de la base (`fusionner`), puis, pour les percentiles, par
    les listes de latences et de jetons d'entrée (`latences`, `entrees`)."""
    __slots__ = (
        "appels", "jetons_entree", "jetons_sortie", "jetons_cache", "secondes_audio",
        "caracteres", "cout", "lignes_chiffrees", "issues", "latences", "entrees",
    )

    def __init__(self) -> None:
        self.appels = 0
        self.jetons_entree = 0
        self.jetons_sortie = 0
        self.jetons_cache = 0
        self.secondes_audio = 0
        self.caracteres = 0
        self.cout = 0
        self.lignes_chiffrees = 0
        self.issues: dict[str, int] = {}
        self.latences: list[int] = []
        self.entrees: list[int] = []   # jetons d'entrée de chaque appel d'unité `jeton`

    def fusionner(self, issue: str, appels, jetons_entree, jetons_sortie, jetons_cache,
                  secondes, caracteres, cout, chiffrees) -> None:
        """Ajoute un groupe agrégé par la base (une issue donnée)."""
        # `int()` : PostgreSQL rend NUMERIC (donc Decimal) pour SUM(BIGINT) ; SQLite, un entier.
        self.appels += int(appels)
        self.jetons_entree += int(jetons_entree or 0)
        self.jetons_sortie += int(jetons_sortie or 0)
        self.jetons_cache += int(jetons_cache or 0)
        self.secondes_audio += int(secondes or 0)
        self.caracteres += int(caracteres or 0)
        self.cout += int(cout or 0)
        self.lignes_chiffrees += int(chiffrees or 0)
        self.issues[issue] = self.issues.get(issue, 0) + int(appels)

    # ── lectures ────────────────────────────────────────────────────────────
    @property
    def cout_micro_eur(self) -> Optional[int]:
        return self.cout if self.lignes_chiffrees else None

    @property
    def taux_cache(self) -> Optional[float]:
        """Part des jetons d'entrée servie par le cache du fournisseur ; `None` sans jeton."""
        return (self.jetons_cache / self.jetons_entree) if self.jetons_entree else None

    def valeur(self, mesure: str) -> Optional[int]:
        return {
            "appels": self.appels,
            "jetons_entree": self.jetons_entree,
            "jetons_sortie": self.jetons_sortie,
            "jetons_cache": self.jetons_cache,
            "secondes_audio": self.secondes_audio,
            "caracteres": self.caracteres,
            "cout_micro_eur": self.cout_micro_eur,
        }[mesure]

    def vers_dict(self) -> dict:
        cout = self.cout_micro_eur
        return {
            "appels": self.appels,
            "jetons_entree": self.jetons_entree,
            "jetons_sortie": self.jetons_sortie,
            "jetons_cache": self.jetons_cache,
            "taux_cache": self.taux_cache,
            "secondes_audio": self.secondes_audio,
            "caracteres": self.caracteres,
            "cout_micro_eur": cout,
            "cout_eur": None if cout is None else cout / MICRO,
            "lignes_non_chiffrees": self.appels - self.lignes_chiffrees,
            "issues": dict(sorted(self.issues.items())),
            "latence_p50_ms": percentile(self.latences, 0.5),
            "latence_p95_ms": percentile(self.latences, 0.95),
            "jetons_entree_mediane_par_appel": percentile(self.entrees, 0.5),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Lecture
# ─────────────────────────────────────────────────────────────────────────────

def _somme_unite(unite: str, colonne):
    """SUM d'une colonne limitée aux lignes d'une unité [CA6] — 0 plutôt que NULL sans ligne."""
    return func.coalesce(func.sum(case((ConsoTokens.unite == unite, colonne), else_=0)), 0)


#: Les agrégats calculés par la base, dans l'ordre que `_Cumul.fusionner` lit (après l'issue).
_AGREGATS = (
    func.count(),
    _somme_unite(UNITE_JETON, ConsoTokens.tokens_in),
    _somme_unite(UNITE_JETON, ConsoTokens.tokens_out),
    _somme_unite(UNITE_JETON, ConsoTokens.tokens_cache),
    _somme_unite(UNITE_SECONDE, ConsoTokens.tokens_in),
    _somme_unite(UNITE_CARACTERE, ConsoTokens.tokens_in),
    func.sum(ConsoTokens.cout_micro_eur),
    func.count(ConsoTokens.cout_micro_eur),
)


def _filtrer(requete, filtres: Filtres):
    """Le périmètre d'une lecture. La période se lit sur `date` (jour d'imputation, indexé) ;
    aucun filtre `potager_id` sauf celui que l'administrateur demande."""
    requete = requete.filter(
        ConsoTokens.date >= filtres.depuis,
        ConsoTokens.date <= filtres.jusqu_a,
        ConsoTokens.provenance.in_(filtres.provenances),
    )
    if filtres.canal:
        requete = requete.filter(ConsoTokens.canal == filtres.canal)
    if filtres.modele:
        requete = requete.filter(ConsoTokens.modele == filtres.modele)
    if filtres.appel_type:
        requete = requete.filter(ConsoTokens.appel_type == filtres.appel_type)
    if filtres.potager_id is not None:
        requete = requete.filter(ConsoTokens.potager_id == filtres.potager_id)
    if filtres.user_id is not None:
        requete = requete.filter(ConsoTokens.user_id == filtres.user_id)
    return requete


def _executer(db: Session, requete) -> list:
    """Seule porte de lecture de `conso_tokens` du module : toute requête passe par le chemin
    explicite de la lecture hors périmètre de potager [CA8]."""
    with lecture_toute_la_plateforme(db):
        return requete.all()


def _agreger(db: Session, filtres: Filtres, cles: Sequence = ()) -> dict[tuple, _Cumul]:
    """Les mesures du périmètre, regroupées par `cles` (expressions SQL) : un `_Cumul` par
    combinaison de valeurs, sans percentiles. Sans clé : une seule entrée, de clé `()`."""
    requete = _filtrer(db.query(*cles, ConsoTokens.issue, *_AGREGATS), filtres)
    requete = requete.group_by(*cles, ConsoTokens.issue)
    n = len(cles)
    groupes: dict[tuple, _Cumul] = {}
    for ligne in _executer(db, requete):
        groupes.setdefault(tuple(ligne[:n]), _Cumul()).fusionner(*ligne[n:])
    return groupes


def _percentiles(db: Session, filtres: Filtres, cle=None, *, latences: bool = True) -> dict:
    """Les valeurs dont on tire médiane et P95, une seule colonne ramenée à la fois.

    Rend `{clé: {"latences": [...], "entrees": [...]}}` ; `entrees` = jetons d'entrée des seuls
    appels d'unité `jeton` [CA6]. Sans `cle`, tout est sous la clé `()`."""
    cles = (cle,) if cle is not None else ()
    resultat: dict[tuple, dict[str, list[int]]] = {}

    def _liste(cle_groupe: tuple) -> dict[str, list[int]]:
        return resultat.setdefault(cle_groupe, {"latences": [], "entrees": []})

    if latences:
        for ligne in _executer(db, _filtrer(db.query(*cles, ConsoTokens.latence_ms), filtres)):
            _liste(tuple(ligne[:-1]))["latences"].append(ligne[-1] or 0)
    requete = _filtrer(db.query(*cles, ConsoTokens.tokens_in), filtres).filter(ConsoTokens.unite == UNITE_JETON)
    for ligne in _executer(db, requete):
        _liste(tuple(ligne[:-1]))["entrees"].append(ligne[-1] or 0)
    return resultat


# ─────────────────────────────────────────────────────────────────────────────
# CA1 — synthèse
# ─────────────────────────────────────────────────────────────────────────────

def _mesures_de_la_periode(db: Session, filtres: Filtres) -> dict:
    cumul = _agreger(db, filtres).get(()) or _Cumul()
    listes = _percentiles(db, filtres).get(())
    if listes:
        cumul.latences, cumul.entrees = listes["latences"], listes["entrees"]
    return cumul.vers_dict()


def synthese(db: Session, filtres: Filtres) -> dict:
    """[CA1] Les chiffres de la période et ceux de la période précédente de même durée."""
    precedente = filtres.periode_precedente()
    return {
        "periode": filtres.vers_dict(),
        "mesures": _mesures_de_la_periode(db, filtres),
        "periode_precedente": precedente.vers_dict(),
        "mesures_precedentes": _mesures_de_la_periode(db, precedente),
    }


# ─────────────────────────────────────────────────────────────────────────────
# CA2 — séries
# ─────────────────────────────────────────────────────────────────────────────

def _controler_mesure(mesure: str) -> None:
    if mesure not in MESURES:
        raise FiltreInvalideError(f"mesure inconnue : {mesure} (attendu parmi {', '.join(MESURES)})")


def _controler_dimension(dimension: str, autorisees: dict[str, str]) -> str:
    if dimension not in autorisees:
        raise FiltreInvalideError(
            f"dimension inconnue : {dimension} (attendu parmi {', '.join(autorisees)})"
        )
    return autorisees[dimension]


def _cle(valeur) -> object:
    return CLE_ABSENTE if valeur is None else valeur


def _somme(valeurs: Sequence[Optional[int]]) -> Optional[int]:
    presentes = [v for v in valeurs if v is not None]
    return sum(presentes) if presentes else None


def serie(
    db: Session,
    filtres: Filtres,
    mesure: str = "jetons_entree",
    dimension: Optional[str] = None,
    pas: Optional[str] = None,
) -> dict:
    """[CA2] Une série par jour (ou par heure sur une journée) d'une mesure, ventilée ou non.

    Chaque pas de la période est présent, à zéro quand rien n'a été appelé : un jour sans appel
    n'est pas un trou [US-312 / CA8]. Pour `cout_micro_eur`, un pas sans ligne chiffrée vaut
    `None`, pas zéro."""
    _controler_mesure(mesure)
    colonne = _controler_dimension(dimension, DIMENSIONS_SERIE) if dimension else None
    pas = pas or (PAS_HEURE if filtres.jours == 1 else PAS_JOUR)
    if pas not in (PAS_JOUR, PAS_HEURE):
        raise FiltreInvalideError(f"pas inconnu : {pas} (attendu : jour ou heure)")
    if pas == PAS_HEURE and filtres.jours != 1:
        raise FiltreInvalideError("le pas « heure » n'existe que sur une période d'un jour")

    if pas == PAS_JOUR:
        points = [(filtres.depuis + timedelta(days=i)).isoformat() for i in range(filtres.jours)]
        cle_de_pas = ConsoTokens.date
    else:
        points = [f"{h:02d}h" for h in range(24)]
        cle_de_pas = extract("hour", ConsoTokens.cree_le)
    index = {p: i for i, p in enumerate(points)}

    cles = [cle_de_pas] + ([getattr(ConsoTokens, colonne)] if colonne else [])
    groupes: dict[object, dict[int, _Cumul]] = {}
    for (instant, *reste), cumul in _agreger(db, filtres, cles).items():
        position = index[instant.isoformat()] if pas == PAS_JOUR else int(instant or 0)
        cle = _cle(reste[0]) if colonne else "total"
        groupes.setdefault(cle, {})[position] = cumul

    sans_valeur = None if mesure == "cout_micro_eur" else 0
    series = []
    for cle, par_pas in groupes.items():
        valeurs = [(par_pas[i].valeur(mesure) if i in par_pas else sans_valeur) for i in range(len(points))]
        series.append({"cle": cle, "total": _somme(valeurs), "valeurs": valeurs})
    series.sort(key=lambda s: (-(s["total"] or 0), str(s["cle"])))

    total = [
        _somme([s["valeurs"][i] for s in series]) if series else sans_valeur
        for i in range(len(points))
    ]
    return {
        "periode": filtres.vers_dict(), "mesure": mesure, "dimension": dimension, "pas": pas,
        "points": points, "series": series, "total": total,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CA3 — ventilation
# ─────────────────────────────────────────────────────────────────────────────

def _libelles(db: Session, dimension: str, cles: Sequence) -> dict:
    """Libellé lisible des potagers et des utilisateurs (tables hors RLS) ; les autres
    dimensions se lisent telles quelles."""
    ids = [c for c in cles if isinstance(c, int)]
    if not ids:
        return {}
    if dimension == "potager":
        return {i: nom for i, nom in db.query(Potager.id, Potager.nom).filter(Potager.id.in_(ids)).all()}
    if dimension == "utilisateur":
        # Le nom d'affichage, jamais l'adresse e-mail dans un classement.
        return {i: nom for i, nom in db.query(User.id, User.nom).filter(User.id.in_(ids)).all() if nom}
    return {}


def ventilation(
    db: Session,
    filtres: Filtres,
    dimension: str,
    mesure: str = "appels",
    limite: int = 10,
) -> dict:
    """[CA3] Le classement d'une dimension pour une mesure, avec limite.

    Chaque ligne porte aussi les mesures usuelles (appels, jetons d'entrée et de sortie, médiane
    des jetons d'entrée par appel, coût) : les tableaux d'US-312 et US-313 n'ont pas besoin d'un
    second appel. `part` est la part de la ligne dans le total de la mesure sur TOUTE la
    période (pas seulement sur les lignes retenues par la limite)."""
    _controler_mesure(mesure)
    colonne = _controler_dimension(dimension, DIMENSIONS_VENTILATION)
    if not 1 <= limite <= 200:
        raise FiltreInvalideError("limite attendue entre 1 et 200")

    expression = getattr(ConsoTokens, colonne)
    groupes = _agreger(db, filtres, [expression])
    entrees = _percentiles(db, filtres, expression, latences=False)
    for cle, cumul in groupes.items():
        cumul.entrees = entrees.get(cle, {}).get("entrees", [])
    # Une valeur absente (NULL) forme un groupe à part, sous une clé lisible.
    par_cle = {_cle(cle[0]): cumul for cle, cumul in groupes.items()}

    total = _somme([c.valeur(mesure) for c in par_cle.values()])
    classes = sorted(par_cle.items(), key=lambda kv: (-(kv[1].valeur(mesure) or 0), str(kv[0])))
    retenues = classes[:limite]
    libelles = _libelles(db, dimension, [cle for cle, _ in retenues])

    lignes = []
    for cle, cumul in retenues:
        valeur = cumul.valeur(mesure)
        dict_ = cumul.vers_dict()
        lignes.append({
            "cle": cle,
            "libelle": libelles.get(cle, str(cle)),
            "valeur": valeur,
            "part": (valeur / total) if (valeur is not None and total) else None,
            **{k: dict_[k] for k in (
                "appels", "jetons_entree", "jetons_sortie", "jetons_cache", "secondes_audio",
                "caracteres", "cout_micro_eur", "jetons_entree_mediane_par_appel",
            )},
        })
    return {
        "periode": filtres.vers_dict(), "dimension": dimension, "mesure": mesure,
        "total": total, "nb_valeurs": len(classes), "limite": limite, "lignes": lignes,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CA4 — distribution par échange
# ─────────────────────────────────────────────────────────────────────────────

def _distribution(valeurs: Sequence[float]) -> dict:
    return {
        "mediane": percentile(valeurs, 0.5),
        "p95": percentile(valeurs, 0.95),
        "maximum": float(max(valeurs)) if valeurs else None,
    }


def echanges(db: Session, filtres: Filtres) -> dict:
    """[CA4] Ce que coûte UNE réponse : coût, jetons et nombre d'appels par échange.

    Un échange regroupe les appels qui ont servi la même réponse (dictée, agent, résumé parlé,
    voix — `echange_ref`). Les lignes sans échange (avant v74) sont comptées à part, jamais
    rattachées à un échange fictif. Les jetons d'un échange sont ses jetons d'entrée et de
    sortie d'unité `jeton` : l'audio et les caractères n'y entrent pas [CA6]."""
    groupes = _agreger(db, filtres, [ConsoTokens.echange_ref])
    par_echange = {cle[0]: cumul for cle, cumul in groupes.items() if cle[0]}
    sans_echange = sum(c.appels for cle, c in groupes.items() if not cle[0])

    couts = [c.cout_micro_eur for c in par_echange.values() if c.cout_micro_eur is not None]
    jetons = [c.jetons_entree + c.jetons_sortie for c in par_echange.values()]
    appels = [c.appels for c in par_echange.values()]
    return {
        "periode": filtres.vers_dict(),
        "nb_echanges": len(par_echange),
        "lignes_sans_echange": sans_echange,
        "echanges_non_chiffres": len(par_echange) - len(couts),
        "cout_micro_eur": _distribution(couts),
        "jetons": _distribution(jetons),
        "appels": _distribution(appels),
    }
