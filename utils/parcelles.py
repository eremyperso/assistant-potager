"""
utils/parcelles.py — Gestion des parcelles du potager
-------------------------------------------------------
[US_Plan_occupation_parcelles]

Fonctions :
- normalize_parcelle_name  : forme canonique (CA11)
- levenshtein_distance     : distance pure Python (CA12)
- find_doublon             : détection doublons exact / proche (CA10, CA12)
- create_parcelle          : création avec vérification doublon (CA13)
- get_all_parcelles        : liste triée par ordre (CA4)
- calcul_occupation_parcelles : structure d'occupation par parcelle (CA1-CA7)
"""
from __future__ import annotations

import logging
import re
from datetime import date as _date, datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import func
from unidecode import unidecode

from database.models import Evenement, Parcelle
from utils.stock import calcul_stock_cultures, get_type_organe, _cutoff_dt

log = logging.getLogger("potager")


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA11] Normalisation du nom de parcelle
# ──────────────────────────────────────────────────────────────────────────────

def normalize_parcelle_name(nom: str) -> str:
    """
    [CA11] Normalise un nom de parcelle : strip + lower + suppression accents
    + suppression tirets et espaces.

    Exemples :
      "Nord"    → "nord"
      "Côté Est" → "cotéest" → "coteest"
      "nord-est"→ "nordest"
    """
    s = nom.strip().lower()
    s = unidecode(s)               # suppression accents
    s = re.sub(r"[\s\-]+", "", s)  # suppression tirets et espaces
    return s


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA12] Distance de Levenshtein (pure Python)
# ──────────────────────────────────────────────────────────────────────────────

def levenshtein_distance(a: str, b: str) -> int:
    """
    [CA12] Calcule la distance de Levenshtein entre deux chaînes.
    Implémentation pure Python — pas de dépendance externe.
    """
    if a == b:
        return 0
    len_a, len_b = len(a), len(b)
    if len_a == 0:
        return len_b
    if len_b == 0:
        return len_a

    # Optimisation : n'utiliser que deux lignes
    prev = list(range(len_b + 1))
    curr = [0] * (len_b + 1)

    for i in range(1, len_a + 1):
        curr[0] = i
        for j in range(1, len_b + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,        # suppression
                curr[j - 1] + 1,    # insertion
                prev[j - 1] + cost, # substitution
            )
        prev, curr = curr, [0] * (len_b + 1)

    return prev[len_b]


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA10, CA12] Détection doublons
# ──────────────────────────────────────────────────────────────────────────────

def find_doublon(
    db: Session, nom_normalise: str
) -> Tuple[Optional[Parcelle], Optional[Parcelle]]:
    """
    [CA10, CA12] Recherche un doublon exact ou une variante proche (Levenshtein ≤ 2).

    Retourne (exact_match, proche_match) :
    - exact_match  : Parcelle dont nom_normalise == nom_normalise fourni
    - proche_match : Parcelle dont la distance Levenshtein ≤ 2 (si pas d'exact)
    """
    # Doublon exact
    exact = (
        db.query(Parcelle)
        .filter(Parcelle.nom_normalise == nom_normalise)
        .first()
    )
    if exact:
        return exact, None

    # Variante proche (Levenshtein ≤ 2)
    toutes = db.query(Parcelle).filter(Parcelle.actif.is_(True)).all()
    for p in toutes:
        if levenshtein_distance(nom_normalise, p.nom_normalise) <= 2:
            return None, p

    return None, None


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA13] Création d'une parcelle
# ──────────────────────────────────────────────────────────────────────────────

def resolve_parcelle(db: Session, nom: str) -> Optional[Parcelle]:
    """
    Résout un nom de parcelle libre (issu du LLM) vers l'objet Parcelle en base.

    Stratégie :
    1. Correspondance exacte sur nom_normalise → retourne immédiatement
    2. Correspondance proche (Levenshtein ≤ 2) → retourne la variante (log warning)
    3. Aucune correspondance → retourne None

    Args:
        db  : session SQLAlchemy
        nom : nom brut extrait par le LLM (ex : "Ouest", "NORD", "cote est")

    Returns:
        Parcelle correspondante ou None
    """
    if not nom or not nom.strip():
        return None
    nom_normalise = normalize_parcelle_name(nom)
    exact, proche = find_doublon(db, nom_normalise)
    if exact:
        return exact
    if proche:
        log.warning(
            f"[resolve_parcelle] Correspondance approchée : "
            f"{nom!r} → {proche.nom!r} (distance Levenshtein ≤ 2)"
        )
        return proche

    # Correspondance par sous-chaîne : "planchecentrale" contient "centrale"
    # Couvre les cas où l'utilisateur préfixe le nom ("planche-centrale" → "CENTRALE")
    parcelles_actives = db.query(Parcelle).filter(Parcelle.actif == True).all()
    for p in parcelles_actives:
        p_norm = p.nom_normalise
        if p_norm and (p_norm in nom_normalise or nom_normalise in p_norm):
            log.warning(
                f"[resolve_parcelle] Correspondance sous-chaîne : "
                f"{nom!r} → {p.nom!r}"
            )
            return p
    return None


def create_parcelle(
    db: Session,
    nom: str,
    exposition: Optional[str] = None,
    superficie_m2: Optional[float] = None,
) -> Parcelle:
    """
    [CA13] Crée une nouvelle parcelle avec nom_normalise calculé.
    ordre = nombre de parcelles existantes + 1.
    Lève ValueError si un doublon exact existe déjà.
    """
    nom_normalise = normalize_parcelle_name(nom)
    exact, _ = find_doublon(db, nom_normalise)
    if exact:
        raise ValueError(f"La parcelle « {exact.nom.upper()} » existe déjà.")

    nb_existantes = db.query(Parcelle).count()
    parcelle = Parcelle(
        nom=nom,
        nom_normalise=nom_normalise,
        exposition=exposition,
        superficie_m2=superficie_m2,
        ordre=nb_existantes + 1,
        actif=True,
    )
    db.add(parcelle)
    db.commit()
    db.refresh(parcelle)
    log.info(f"[US_Plan_occupation_parcelles] Parcelle créée : {nom!r} (ordre={parcelle.ordre})")
    return parcelle


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles] Mise à jour des métadonnées d'une parcelle
# ──────────────────────────────────────────────────────────────────────────────

_CHAMPS_MODIFIER = {"exposition", "superficie", "ordre"}


def update_parcelle(
    db: Session, nom: str, **kwargs
) -> Tuple[Parcelle, List[str]]:
    """
    Met à jour les métadonnées d'une parcelle existante.

    Paramètres acceptés via kwargs : exposition, superficie (float m²), ordre (int).
    Lève ValueError  si un paramètre est inconnu ou mal typé.
    Lève LookupError si la parcelle est introuvable.

    Retourne (parcelle_mise_a_jour, liste_des_modifs_texte).
    """
    inconnus = set(kwargs) - _CHAMPS_MODIFIER
    if inconnus:
        raise ValueError(
            f"Paramètre(s) inconnu(s) : {', '.join(sorted(inconnus))}. "
            f"Acceptés : exposition, superficie, ordre"
        )

    nom_normalise = normalize_parcelle_name(nom)
    parcelle = (
        db.query(Parcelle)
        .filter(Parcelle.nom_normalise == nom_normalise)
        .first()
    )
    if parcelle is None:
        raise LookupError(nom)

    modifs: List[str] = []
    if "exposition" in kwargs:
        parcelle.exposition = kwargs["exposition"]
        modifs.append(f"Exposition : {kwargs['exposition']}")
    if "superficie" in kwargs:
        try:
            val = float(kwargs["superficie"])
        except (ValueError, TypeError):
            raise ValueError("superficie doit être un nombre décimal (ex : 8.5)")
        parcelle.superficie_m2 = val
        modifs.append(f"Superficie : {val} m²")
    if "ordre" in kwargs:
        try:
            val_ord = int(kwargs["ordre"])
        except (ValueError, TypeError):
            raise ValueError("ordre doit être un entier (ex : 1)")
        parcelle.ordre = val_ord
        modifs.append(f"Ordre : {val_ord}")

    db.commit()
    db.refresh(parcelle)
    log.info(
        f"[US_Plan_occupation_parcelles] Parcelle mise à jour : {parcelle.nom!r} — {modifs}"
    )
    return parcelle, modifs


# ──────────────────────────────────────────────────────────────────────────────
# [US-006] Renommage d'une parcelle avec propagation sur les événements
# ──────────────────────────────────────────────────────────────────────────────

def rename_parcelle(
    db: Session,
    ancien_nom: str,
    nouveau_nom: str,
) -> Tuple[Parcelle, int]:
    """
    [US-006] Renomme une parcelle et propage le nouveau nom sur tous les événements liés.
    La mise à jour est atomique (un seul commit).

    Args:
        db         : session SQLAlchemy
        ancien_nom : nom actuel (résolution via nom_normalise, insensible casse/accents)
        nouveau_nom: nouveau nom souhaité

    Returns:
        (parcelle_mise_a_jour, nb_evenements_modifies)

    Raises:
        LookupError : si ancien_nom ne correspond à aucune parcelle connue
        ValueError  : si nouveau_nom est déjà utilisé par une autre parcelle
    """
    # Résolution de l'ancienne parcelle via nom_normalise
    parcelle = resolve_parcelle(db, ancien_nom)
    if parcelle is None:
        raise LookupError(ancien_nom)

    # Vérification que le nouveau nom n'est pas déjà utilisé par une autre parcelle
    nouveau_normalise = normalize_parcelle_name(nouveau_nom)
    conflit = (
        db.query(Parcelle)
        .filter(
            Parcelle.nom_normalise == nouveau_normalise,
            Parcelle.id != parcelle.id,
        )
        .first()
    )
    if conflit is not None:
        raise ValueError(f"Ce nom est déjà utilisé par une autre parcelle : {conflit.nom!r}")

    ancien_nom = parcelle.nom

    # [migration_v12] la colonne evenements.parcelle n'existe plus :
    # les événements sont liés via parcelle_id — compter suffit, pas besoin de propager
    nb_evenements = (
        db.query(Evenement)
        .filter(Evenement.parcelle_id == parcelle.id)
        .count()
    )

    # Mise à jour de la parcelle elle-même
    parcelle.nom = nouveau_nom
    parcelle.nom_normalise = nouveau_normalise

    db.commit()
    db.refresh(parcelle)

    log.info(
        f"[US-006] Parcelle renommée : {ancien_nom!r} → {nouveau_nom!r} "
        f"({nb_evenements} événements liés)"
    )
    return parcelle, nb_evenements


# ──────────────────────────────────────────────────────────────────────────────
# [US-009] Suppression (soft-delete) d'une parcelle
# ──────────────────────────────────────────────────────────────────────────────

def supprimer_parcelle(db: Session, nom: str) -> Tuple[Parcelle, int]:
    """
    [US-009] Soft-delete d'une parcelle : actif=False + réaffectation atomique
    des événements liés (parcelle_id → NULL).

    Returns:
        (parcelle, nb_evenements_reaffectes)

    Raises:
        LookupError : si la parcelle est introuvable ou déjà supprimée
    """
    parcelle = resolve_parcelle(db, nom)
    if parcelle is None:
        raise LookupError(nom)

    nb = db.query(Evenement).filter(Evenement.parcelle_id == parcelle.id).count()
    db.query(Evenement).filter(Evenement.parcelle_id == parcelle.id).update(
        {"parcelle_id": None}, synchronize_session="fetch"
    )
    parcelle.actif = False
    db.commit()

    log.info(f"[US-009] Parcelle supprimée : {parcelle.nom!r} — {nb} événements réaffectés en Non localisé")
    return parcelle, nb


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA4] Liste des parcelles
# ──────────────────────────────────────────────────────────────────────────────

def get_all_parcelles(db: Session) -> List[Parcelle]:
    """
    [CA4] Retourne toutes les parcelles actives triées par ordre croissant.
    """
    return (
        db.query(Parcelle)
        .filter(Parcelle.actif.is_(True))
        .order_by(Parcelle.ordre)
        .all()
    )


# ──────────────────────────────────────────────────────────────────────────────
# [US_Plan_occupation_parcelles / CA1-CA7] Structure d'occupation
# ──────────────────────────────────────────────────────────────────────────────

def calcul_occupation_parcelles(db: Session, date_ref: Optional[_date] = None) -> Dict[Optional[str], list]:
    """
    [CA1-CA7] Calcule la structure d'occupation du potager par parcelle.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Retourne un dict :
    {
        "NORD": [
            {
                "culture": "tomate",
                "variete": "Cœur de Bœuf",
                "nb_plants": 3.0,
                "unite": "plants",
                "type_organe": "reproducteur",
                "date_plantation": datetime,
                "age_jours": 27,
            },
            ...
        ],
        None: [...]   # [CA7] cultures sans parcelle renseignée
    }

    Seules les cultures avec stock > 0 sont incluses.
    Groupées par (culture, variete, parcelle) depuis les événements de plantation.
    """
    cutoff = _cutoff_dt(date_ref)
    ref_day = date_ref if date_ref is not None else datetime.now().date()

    # ── 1. Cultures actives (stock > 0) ──────────────────────────────────────
    stocks = calcul_stock_cultures(db, date_ref)
    cultures_actives = {c for c, s in stocks.items() if s.stock_plants > 0}

    # ── 2. Événements de plantation pour cultures actives ────────────────────
    # Parcelle.nom retourné uniquement si actif=True — les parcelles soft-deletées
    # tombent dans le groupe None (Non localisé) comme les events sans parcelle_id.
    from sqlalchemy import case as sa_case
    _q_rows = (
        db.query(
            Evenement.culture,
            Evenement.variete,
            sa_case((Parcelle.actif.is_(True), Parcelle.nom), else_=None).label("parcelle_nom"),
            Evenement.quantite,
            Evenement.rang,
            Evenement.unite,
            Evenement.date,
        )
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "plantation")
        .filter(Evenement.culture.in_(list(cultures_actives)))
        .order_by(Evenement.date)
    )
    if cutoff is not None:
        _q_rows = _q_rows.filter(Evenement.date <= cutoff)
    rows = _q_rows.all()

    # ── 3. Agrégation par (culture, variete, parcelle) — plantations ─────────
    groupes: Dict[tuple, dict] = {}

    for culture, variete, parcelle, quantite, rang, unite, date_evt in rows:
        variete_norm = variete or ""
        key = (culture, variete_norm, parcelle)
        total = (quantite or 0) * (rang or 1)

        if key not in groupes:
            groupes[key] = {
                "culture": culture,
                "variete": variete_norm,
                "nb_plants": 0.0,
                "unite": unite or "plants",
                "date_premiere": date_evt,
            }

        groupes[key]["nb_plants"] += total

        if date_evt and (
            groupes[key]["date_premiere"] is None
            or date_evt < groupes[key]["date_premiere"]
        ):
            groupes[key]["date_premiere"] = date_evt

    # ── 3b. Semis pleine terre (parcelle_id non null) ─────────────────────────
    # Un semis avec parcelle_id = semé directement en pleine terre (pas pépinière).
    # Traité séparément des plantations — pas de filtre cultures_actives.
    _q_semis_pt = (
        db.query(
            Evenement.culture,
            Evenement.variete,
            sa_case((Parcelle.actif.is_(True), Parcelle.nom), else_=None).label("parcelle_nom"),
            Evenement.quantite,
            Evenement.unite,
            Evenement.date,
        )
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.parcelle_id.isnot(None))
        .order_by(Evenement.date)
    )
    if cutoff is not None:
        _q_semis_pt = _q_semis_pt.filter(Evenement.date <= cutoff)
    semis_pt_rows = _q_semis_pt.all()

    groupes_semis: Dict[tuple, dict] = {}
    for culture, variete, parcelle, quantite, unite, date_evt in semis_pt_rows:
        variete_norm = variete or ""
        unite_norm = unite or "graines"
        # [US-037 / CA2] L'unité fait partie de la clé de regroupement — jamais de
        # somme entre graines/pieds/m² pour une même culture+variété+parcelle.
        key = (culture, variete_norm, parcelle, unite_norm)
        total = quantite or 0

        if key not in groupes_semis:
            groupes_semis[key] = {
                "culture": culture,
                "variete": variete_norm,
                "nb_plants": 0.0,
                "unite": unite_norm,
                "date_premiere": date_evt,
            }

        groupes_semis[key]["nb_plants"] += total

        if date_evt and (
            groupes_semis[key]["date_premiere"] is None
            or date_evt < groupes_semis[key]["date_premiere"]
        ):
            groupes_semis[key]["date_premiere"] = date_evt

    # ── 4. Construction du résultat final ─────────────────────────────────────
    today = ref_day  # [US-030] calcul d'âge relatif à la date de référence

    # Pertes par (culture, variete_norm) pour corriger les nb_plants affichés dans le plan.
    # Les pertes sans variete sont attribuées à toutes les varietes de la culture
    # proportionnellement à leur poids dans le total planté.
    _q_pertes = (
        db.query(Evenement.culture, Evenement.variete, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "perte")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_pertes = _q_pertes.filter(Evenement.date <= cutoff)
    pertes_raw = _q_pertes.all()
    pertes_var: Dict[tuple, float] = {}
    pertes_sans_variete: Dict[str, float] = {}
    for c, v, q in pertes_raw:
        if v:
            pertes_var[(c, v)] = pertes_var.get((c, v), 0) + (q or 0)
        else:
            pertes_sans_variete[c] = pertes_sans_variete.get(c, 0) + (q or 0)

    # Récoltes par (culture, variete_norm) — uniquement pour cultures végétatives.
    # Pour végétatif : récolter = arracher → diminue le nombre de pieds en terre.
    # Pour reproducteur : la plante reste, les récoltes n'affectent pas l'occupation.
    # [US-036 / CA6] Ne compter QUE les récoltes en nombre de pièces (unité hors
    # kg/g/mg) — une récolte pesée (rendement) ne doit jamais réduire le nombre
    # de pieds en terre, sous peine de double déduction avec l'événement "pièces".
    _UNITES_POIDS = ("kg", "g", "mg")
    _q_recoltes = (
        db.query(Evenement.culture, Evenement.variete, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "recolte")
        .filter(Evenement.culture.isnot(None))
        .filter(~func.lower(func.coalesce(Evenement.unite, "")).in_(_UNITES_POIDS))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.date <= cutoff)
    recoltes_raw = _q_recoltes.all()
    recoltes_var: Dict[tuple, float] = {}
    recoltes_sans_variete: Dict[str, float] = {}
    for c, v, q in recoltes_raw:
        if v:
            recoltes_var[(c, v)] = recoltes_var.get((c, v), 0) + (q or 0)
        else:
            recoltes_sans_variete[c] = recoltes_sans_variete.get(c, 0) + (q or 0)

    # Totaux plantés par culture (toutes varietes) pour distribution proportionnelle
    total_plante_par_culture: Dict[str, float] = {}
    for (c, v, _p), d in groupes.items():
        total_plante_par_culture[c] = total_plante_par_culture.get(c, 0) + d["nb_plants"]

    def _perte_pour_groupe(culture: str, variete: str, nb_plants: float) -> float:
        """Retourne la part de perte + récolte à déduire pour ce groupe."""
        total_c = total_plante_par_culture.get(culture, 0)

        perte = pertes_var.get((culture, variete), 0)
        perte_globale = pertes_sans_variete.get(culture, 0)
        if perte_globale > 0 and total_c > 0:
            perte += perte_globale * (nb_plants / total_c)

        perte += recoltes_var.get((culture, variete), 0)
        recolte_globale = recoltes_sans_variete.get(culture, 0)
        if recolte_globale > 0 and total_c > 0:
            perte += recolte_globale * (nb_plants / total_c)

        return perte

    result: Dict[Optional[str], list] = {}

    for (culture, variete, parcelle), data in groupes.items():
        stock = stocks.get(culture)
        # [CA1] Ne garder que les cultures avec stock actif
        if not stock or stock.stock_plants <= 0:
            continue

        nb_plantes_brut = data["nb_plants"]
        nb_plants = round(max(0.0, nb_plantes_brut - _perte_pour_groupe(culture, variete, nb_plantes_brut)))
        if nb_plants <= 0:
            continue

        date_plantation = data["date_premiere"]
        if date_plantation and hasattr(date_plantation, "date"):
            age_jours = (today - date_plantation.date()).days
        elif date_plantation:
            age_jours = (today - date_plantation).days
        else:
            age_jours = 0

        entree = {
            "culture": culture,
            "variete": variete,
            "nb_plants": nb_plants,
            "unite": data["unite"],
            "type_organe": stock.type_organe,           # [CA3] pour seuil alerte
            "date_plantation": date_plantation,
            "age_jours": max(0, age_jours),
        }

        if parcelle not in result:
            result[parcelle] = []
        result[parcelle].append(entree)

    # ── 4b. Semis pleine terre dans le résultat ───────────────────────────────
    for (culture, variete, parcelle, _unite_cle), data in groupes_semis.items():
        date_semis = data["date_premiere"]
        if date_semis and hasattr(date_semis, "date"):
            age_jours = (today - date_semis.date()).days
        elif date_semis:
            age_jours = (today - date_semis).days
        else:
            age_jours = 0

        entree_semis = {
            "culture": culture,
            "variete": variete,
            "nb_plants": data["nb_plants"],
            "unite": data["unite"],
            "type_organe": get_type_organe(db, culture),
            "date_plantation": date_semis,
            "age_jours": max(0, age_jours),
            "type_action": "semis",     # distingue des plantations dans l'affichage
        }

        if parcelle not in result:
            result[parcelle] = []
        result[parcelle].append(entree_semis)

    log.info(
        f"[US_Plan_occupation_parcelles] calcul_occupation_parcelles : "
        f"{sum(len(v) for v in result.values())} cultures actives, "
        f"{len(result)} parcelles"
    )
    return result
