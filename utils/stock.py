"""
utils/stock.py — Calcul du stock réel des cultures
---------------------------------------------------
[US-002] Adapte le calcul selon le type d'organe récolté :

- "végétatif"    : récolte DESTRUCTIVE
                   stock_plants = plantations - pertes - récoltes
                   Ex : salade, carotte, radis — 1 récolte = 1 plant en moins

- "reproducteur" : récolte CONTINUE
                   stock_plants = plantations - pertes  (récoltes n'affectent PAS le stock)
                   rendement_kg = SUM(récoltes en kg/g)
                   Ex : tomate, courgette — la plante reste vivante

Cette logique est centralisée ici pour être partagée entre bot.py et main.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date, datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import Evenement, CultureConfig, Parcelle


def _cutoff_dt(date_ref: Optional[_date]) -> Optional[datetime]:
    """[US-030] Borne haute inclusive (23:59:59) pour filtrage temporel par date de référence."""
    if date_ref is None:
        return None
    return datetime(date_ref.year, date_ref.month, date_ref.day, 23, 59, 59)


@dataclass
class StockCulture:
    """[US-002] Données de stock agronomique pour une culture donnée."""
    culture:             str
    unite:               str
    type_organe:         Optional[str]   # "végétatif" | "reproducteur" | None

    # Plantations
    plants_plantes:      float = 0.0

    # Pertes (tous types)
    plants_perdus:       float = 0.0

    # Récoltes
    nb_recoltes:         int   = 0
    recoltes_total:      float = 0.0    # somme quantités récoltées
    unite_recolte:       str   = ""

    @property
    def stock_plants(self) -> float:
        """
        [US-002 / CA1 & CA2]
        - végétatif    : stock = plantations - pertes - récoltes
        - reproducteur : stock = plantations - pertes  (récoltes indépendantes)
        - inconnu      : même logique que végétatif (conservateur)
        """
        if self.type_organe == "reproducteur":
            return max(0.0, self.plants_plantes - self.plants_perdus)
        # végétatif ou inconnu
        return max(0.0, self.plants_plantes - self.plants_perdus - self.recoltes_total)

    @property
    def is_reproducteur(self) -> bool:
        return self.type_organe == "reproducteur"


def get_type_organe(db: Session, culture: str) -> Optional[str]:
    """Retourne le type d'organe pour une culture depuis culture_config."""
    cfg = db.query(CultureConfig).filter(CultureConfig.nom == culture).first()
    return cfg.type_organe_recolte if cfg else None


def calcul_stock_cultures(db: Session, date_ref: Optional[_date] = None) -> Dict[str, StockCulture]:
    """
    [US-002] Calcule le stock réel de toutes les cultures plantées.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Retourne un dict { culture: StockCulture } trié par culture.

    Algorithme :
    1. Agréger plantations par (culture, unite) avec rang
    2. Agréger pertes par culture
    3. Agréger récoltes par (culture, unite)
    4. Récupérer le type_organe depuis culture_config
    5. Appliquer la règle végétatif / reproducteur
    """
    cutoff = _cutoff_dt(date_ref)

    # ── 1. Plantations : total = quantite × rang ────────────────────────────
    _q_plant = (
        db.query(
            Evenement.culture,
            Evenement.unite,
            Evenement.quantite,
            Evenement.rang
        )
        .filter(Evenement.type_action == "plantation")
        .filter(Evenement.culture.isnot(None))
    )
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)
    plantations_raw = _q_plant.all()

    plantes: Dict[str, tuple] = {}   # culture → (total_plants, unite)
    for culture, unite, qte, rang in plantations_raw:
        total = (qte or 0) * (rang or 1)
        key = culture
        cur_total, cur_unite = plantes.get(key, (0.0, unite or "plants"))
        plantes[key] = (cur_total + total, unite or cur_unite)

    if not plantes:
        return {}

    # ── 2. Pertes par culture ───────────────────────────────────────────────
    _q_pertes = (
        db.query(Evenement.culture, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "perte")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture)
    )
    if cutoff is not None:
        _q_pertes = _q_pertes.filter(Evenement.date <= cutoff)
    pertes_raw = _q_pertes.all()
    pertes: Dict[str, float] = {c: (q or 0) for c, q in pertes_raw}

    # ── 3. Récoltes par (culture, unite) — normalisées en grammes ──────────
    _UNITE_TO_G = {"kg": 1000.0, "g": 1.0, "mg": 0.001}

    def _to_g(val: float, unite: str) -> float:
        return val * _UNITE_TO_G.get((unite or "").lower(), 1.0)

    def _best_unite(total_g: float) -> tuple:
        if total_g >= 1000:
            return round(total_g / 1000, 2), "kg"
        return round(total_g, 1), "g"

    _q_recoltes = (
        db.query(
            Evenement.culture,
            Evenement.unite,
            func.count(Evenement.id),
            func.sum(Evenement.quantite)
        )
        .filter(Evenement.type_action == "recolte")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.unite)
    )
    if cutoff is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.date <= cutoff)
    recoltes_raw = _q_recoltes.all()
    # Agréger en grammes pour éviter le mélange kg/g
    recoltes_g: Dict[str, tuple] = {}  # culture → (nb, total_g)
    for culture, unite, nb, total in recoltes_raw:
        val_g = _to_g(total or 0.0, unite)
        if culture in recoltes_g:
            prev_nb, prev_g = recoltes_g[culture]
            recoltes_g[culture] = (prev_nb + nb, prev_g + val_g)
        else:
            recoltes_g[culture] = (nb, val_g)

    recoltes: Dict[str, tuple] = {}  # culture → (nb, valeur_lisible, unite)
    for culture, (nb, total_g) in recoltes_g.items():
        val, unite_out = _best_unite(total_g)
        recoltes[culture] = (nb, val, unite_out)

    # ── 4. Construction des objets StockCulture ─────────────────────────────
    result: Dict[str, StockCulture] = {}
    for culture, (total_plants, unite) in sorted(plantes.items()):
        type_organe = get_type_organe(db, culture)
        rec = recoltes.get(culture, (0, 0.0, ""))

        stock = StockCulture(
            culture         = culture,
            unite           = unite or "plants",
            type_organe     = type_organe,
            plants_plantes  = total_plants,
            plants_perdus   = pertes.get(culture, 0.0),
            nb_recoltes     = rec[0],
            recoltes_total  = rec[1],
            unite_recolte   = rec[2],
        )
        result[culture] = stock

    return result


def format_stock_ligne_telegram(s: StockCulture) -> str:
    """
    [US-002 / CA3] Formate une ligne de stock pour /stats Telegram.

    Exemples attendus :
    - végétatif  : "salade : *19 plants* (planté 25, perdu 4, récolté 2)"
    - reproducteur: "tomate : *5 plants actifs* · 8.5 kg récoltés (3 fois)"
    - inconnu    : "carotte : *50 plants* (planté 50)"
    """
    stock = int(s.stock_plants)
    unite = s.unite

    if s.is_reproducteur:
        # Stock = plantes vivantes ; récoltes = rendement cumulé
        base = f"• {s.culture} : *{stock} {unite} actifs*"
        details = [f"planté {int(s.plants_plantes)}"]
        if s.plants_perdus > 0:
            details.append(f"perdu {int(s.plants_perdus)}")

        if s.recoltes_total > 0:
            r_val  = round(s.recoltes_total, 2)
            r_u    = s.unite_recolte or "unités"
            r_nb   = s.nb_recoltes
            base  += f" · *{r_val} {r_u}* récoltés ({r_nb} fois)"

        return base + f" ({', '.join(details)})"

    else:
        # Végétatif : récolte réduit le stock
        base = f"• {s.culture} : *{stock} {unite}*"
        details = [f"planté {int(s.plants_plantes)}"]
        if s.plants_perdus > 0:
            details.append(f"perdu {int(s.plants_perdus)}")
        if s.recoltes_total > 0:
            details.append(f"récolté {int(s.recoltes_total)}")
        return base + f" ({', '.join(details)})"


def calcul_semis(db: Session, date_ref: Optional[_date] = None) -> Dict[str, dict]:
    """
    [US-014 / CA1] Agrège les semis par culture.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Un semis est un stade agronomique (germination/godet) indépendant des plantations.
    Les récoltes sont toujours liées aux plantations, jamais aux semis — on ne les
    croise donc plus ici pour éviter une double attribution incorrecte.

    Retourne un dict { culture: { nb_semis, total_seme, unite, type_organe } }
    """
    cutoff = _cutoff_dt(date_ref)

    _q_semis = (
        db.query(
            Evenement.culture,
            func.count(Evenement.id),
            func.sum(Evenement.quantite),
        )
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture)
    )
    if cutoff is not None:
        _q_semis = _q_semis.filter(Evenement.date <= cutoff)
    semis_raw = _q_semis.all()
    if not semis_raw:
        return {}

    _q_unites = (
        db.query(Evenement.culture, Evenement.unite)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.culture.isnot(None))
        .filter(Evenement.unite.isnot(None))
        .distinct(Evenement.culture)
    )
    if cutoff is not None:
        _q_unites = _q_unites.filter(Evenement.date <= cutoff)
    unites_raw = _q_unites.all()
    unites: Dict[str, str] = {c: u for c, u in unites_raw}

    # Graines consommées par culture : nb_graines_semees si fourni, sinon nb_plants_godets.
    # Règle métier : "5 plants sur 10 graines" → 10 graines consommées (toute la barquette),
    # pas 5. Les graines non germées sont perdues, elles quittent quand même le stock.
    _q_godets = (
        db.query(
            Evenement.culture,
            Evenement.nb_graines_semees,
            Evenement.nb_plants_godets,
        )
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
    )
    if cutoff is not None:
        _q_godets = _q_godets.filter(Evenement.date <= cutoff)
    godets_brut = _q_godets.all()
    graines_consommees: Dict[str, int] = {}
    plants_en_godet: Dict[str, int] = {}
    for culture, nb_g, nb_p in godets_brut:
        consommees = int(nb_g) if nb_g else (int(nb_p) if nb_p else 0)
        plants     = int(nb_p) if nb_p else 0
        graines_consommees[culture] = graines_consommees.get(culture, 0) + consommees
        plants_en_godet[culture]    = plants_en_godet.get(culture, 0) + plants

    # Cultures avec godets : perte_godet y est déjà décomptée dans calcul_godets
    _q_cultures_g = (
        db.query(Evenement.culture)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
        .distinct()
    )
    if cutoff is not None:
        _q_cultures_g = _q_cultures_g.filter(Evenement.date <= cutoff)
    cultures_avec_godets = {row[0].lower() for row in _q_cultures_g.all()}

    # perte_godet pour cultures SANS godet = perte de semences en barquette
    _q_pertes_s = (
        db.query(Evenement.culture, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "perte_godet")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture)
    )
    if cutoff is not None:
        _q_pertes_s = _q_pertes_s.filter(Evenement.date <= cutoff)
    pertes_semis_raw = _q_pertes_s.all()
    pertes_semis_dict: Dict[str, int] = {
        c: int(q or 0) for c, q in pertes_semis_raw
        if c.lower() not in cultures_avec_godets
    }

    # Parcelles de semis pleine terre (parcelle_id non null) par culture
    _q_parcelles_pt = (
        db.query(Evenement.culture, Parcelle.nom)
        .join(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.parcelle_id.isnot(None))
        .filter(Parcelle.actif.is_(True))
    )
    if cutoff is not None:
        _q_parcelles_pt = _q_parcelles_pt.filter(Evenement.date <= cutoff)
    parcelles_pt_raw = _q_parcelles_pt.all()
    parcelles_pt: Dict[str, list] = {}
    for culture_pt, nom_p in parcelles_pt_raw:
        if culture_pt not in parcelles_pt:
            parcelles_pt[culture_pt] = []
        if nom_p not in parcelles_pt[culture_pt]:
            parcelles_pt[culture_pt].append(nom_p)

    result: Dict[str, dict] = {}
    for culture, nb, total in semis_raw:
        total_seme  = total or 0
        consommees  = graines_consommees.get(culture, 0)
        perte_semis = pertes_semis_dict.get(culture, 0)
        result[culture] = {
            "nb_semis":               nb,
            "total_seme":             total_seme,
            "unite":                  unites.get(culture, "graines"),
            "type_organe":            get_type_organe(db, culture),
            "plants_en_godet":        plants_en_godet.get(culture, 0),
            "stock_residuel":         max(0, int(total_seme) - consommees - perte_semis),
            "parcelles_pleine_terre": parcelles_pt.get(culture, []),
        }
    return dict(sorted(result.items()))


def calcul_semis_par_culture(db: Session, culture: str, date_ref: Optional[_date] = None) -> List[dict]:
    """
    [US-014 / CA3, CA4, CA5 | US-017 / CA2] Retourne les semis par variété pour une culture donnée.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Champs de chaque dict : variete, nb_semis, total_seme, unite, date_premier_semis,
                            plants_en_godet, stock_residuel
    Retourne [] si aucun semis trouvé pour cette culture.
    """
    cutoff = _cutoff_dt(date_ref)
    culture_lower = culture.lower()

    _q_semis = (
        db.query(
            Evenement.variete,
            Evenement.unite,
            Evenement.quantite,
            Evenement.date,
        )
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "semis")
    )
    if cutoff is not None:
        _q_semis = _q_semis.filter(Evenement.date <= cutoff)
    semis_raw = _q_semis.all()
    if not semis_raw:
        return []

    # Graines consommées par variété : nb_graines_semees si fourni, sinon nb_plants_godets.
    # "5 plants sur 10 graines" → 10 graines déduites du stock (toute la barquette consommée).
    _q_godets_var = (
        db.query(
            Evenement.variete,
            Evenement.nb_graines_semees,
            Evenement.nb_plants_godets,
        )
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "mise_en_godet")
    )
    if cutoff is not None:
        _q_godets_var = _q_godets_var.filter(Evenement.date <= cutoff)
    godets_brut_var = _q_godets_var.all()
    graines_consommees_var: Dict[Optional[str], int] = {}
    plants_en_godet_var: Dict[Optional[str], int] = {}
    for variete, nb_g, nb_p in godets_brut_var:
        consommees = int(nb_g) if nb_g else (int(nb_p) if nb_p else 0)
        plants     = int(nb_p) if nb_p else 0
        graines_consommees_var[variete] = graines_consommees_var.get(variete, 0) + consommees
        plants_en_godet_var[variete]    = plants_en_godet_var.get(variete, 0) + plants

    agregat: Dict[Optional[str], dict] = {}
    for variete, unite, qte, date_ev in semis_raw:
        if variete not in agregat:
            agregat[variete] = {
                "nb_semis":           0,
                "total_seme":         0.0,
                "unite":              unite or "graines",
                "date_premier_semis": date_ev,
            }
        agregat[variete]["nb_semis"] += 1
        agregat[variete]["total_seme"] += qte or 0.0
        if date_ev and (
            agregat[variete]["date_premier_semis"] is None
            or date_ev < agregat[variete]["date_premier_semis"]
        ):
            agregat[variete]["date_premier_semis"] = date_ev

    result = []
    for variete, d in sorted(agregat.items(), key=lambda x: ("" if x[0] is None else x[0])):
        en_godet   = plants_en_godet_var.get(variete, 0)
        consommees = graines_consommees_var.get(variete, 0)
        result.append({
            "variete":            variete,
            "nb_semis":           d["nb_semis"],
            "total_seme":         d["total_seme"],
            "unite":              d["unite"],
            "date_premier_semis": d["date_premier_semis"],
            "plants_en_godet":    en_godet,
            "stock_residuel":     max(0, int(d["total_seme"]) - consommees),
        })
    return result


def calcul_activite_quotidienne(
    db: Session, annee: int, date_ref: Optional[_date] = None
) -> Dict[str, int]:
    """
    [US_Stats_activite_potager] Compte le nombre d'événements par jour pour une année donnée.
    [US-030] date_ref optionnel : plafonne la borne haute à cette date (sinon 31/12 de l'année).

    Retourne { "YYYY-MM-DD": nb_evenements }, uniquement les jours ayant au moins 1 événement.
    """
    debut = datetime(annee, 1, 1)
    fin_annee = datetime(annee, 12, 31, 23, 59, 59)
    cutoff = _cutoff_dt(date_ref)
    fin = min(fin_annee, cutoff) if cutoff else fin_annee

    rows = (
        db.query(func.date(Evenement.date), func.count(Evenement.id))
        .filter(Evenement.date >= debut)
        .filter(Evenement.date <= fin)
        .group_by(func.date(Evenement.date))
        .all()
    )
    return {str(jour): nb for jour, nb in rows}


def calcul_rendement_mensuel(db: Session, annee: int, date_ref: Optional[_date] = None) -> dict:
    """
    [US_Stats_rendement_timeline] Agrège les récoltes par culture et par mois pour une année donnée.
    [US-030] date_ref optionnel : plafonne la borne haute à cette date (sinon 31/12 de l'année).

    Ne retient que les cultures dont la récolte est mesurée en poids (kg/g/mg) — tout est
    normalisé en kg pour permettre une échelle de comparaison commune entre cultures.
    Les cultures récoltées en unités (pièces) ne sont pas incluses dans ce graphique.

    Retourne :
    {
        "cultures": [
            {
                "culture": str,
                "unite": "kg",
                "total": float,
                "mensuel": { "5": 1.2, "6": 2.0, ... },   # clé = mois (str), en kg
            }, ...
        ],  # triées par total décroissant
        "mois_range": [5, 8],         # premier/dernier mois avec au moins une récolte pesée ([] si aucune)
        "total_general_kg": 14.2,
    }
    """
    debut = datetime(annee, 1, 1)
    fin_annee = datetime(annee, 12, 31, 23, 59, 59)
    cutoff = _cutoff_dt(date_ref)
    fin = min(fin_annee, cutoff) if cutoff else fin_annee

    rows = (
        db.query(Evenement.culture, Evenement.unite, Evenement.quantite, Evenement.date)
        .filter(Evenement.type_action == "recolte")
        .filter(Evenement.culture.isnot(None))
        .filter(Evenement.date >= debut)
        .filter(Evenement.date <= fin)
        .all()
    )
    if not rows:
        return {"cultures": [], "mois_range": [], "total_general_kg": 0.0}

    _UNITE_TO_G = {"kg": 1000.0, "g": 1.0, "mg": 0.001}

    par_culture: Dict[str, dict] = {}
    mois_avec_recolte: set = set()

    for culture, unite, qte, dt in rows:
        if not dt or qte is None:
            continue
        unite_l = (unite or "").lower()
        if unite_l not in _UNITE_TO_G:
            continue  # culture récoltée en pièces : hors périmètre de ce graphique
        mois = dt.month
        mois_avec_recolte.add(mois)
        entry = par_culture.setdefault(culture, {"total_g": 0.0, "mensuel_g": {}})
        val_g = qte * _UNITE_TO_G[unite_l]
        entry["total_g"] += val_g
        entry["mensuel_g"][mois] = entry["mensuel_g"].get(mois, 0.0) + val_g

    cultures_out: List[dict] = []
    total_general_kg = 0.0
    for culture, e in par_culture.items():
        total_kg = round(e["total_g"] / 1000.0, 2)
        mensuel = {str(m): round(g / 1000.0, 2) for m, g in e["mensuel_g"].items()}
        total_general_kg += e["total_g"] / 1000.0
        cultures_out.append({
            "culture": culture,
            "unite":   "kg",
            "total":   total_kg,
            "mensuel": mensuel,
        })

    cultures_out.sort(key=lambda c: c["total"], reverse=True)
    mois_range = [min(mois_avec_recolte), max(mois_avec_recolte)] if mois_avec_recolte else []

    return {
        "cultures":         cultures_out,
        "mois_range":       mois_range,
        "total_general_kg": round(total_general_kg, 2),
    }


def format_stock_stats_json(stocks: Dict[str, StockCulture]) -> dict:
    """
    [US-002 / CA4] Retourne les données de stock sous forme JSON pour l'API /stats.

    Champs distincts selon le type :
    - stock_plants         : plants actuellement en vie
    - rendement_total      : total récolté (reproducteur uniquement)
    - unite_rendement      : unité du rendement
    """
    result = []
    for culture, s in stocks.items():
        entry = {
            "culture"            : culture,
            "type_organe"        : s.type_organe or "inconnu",
            "plants_plantes"     : int(s.plants_plantes),
            "plants_perdus"      : int(s.plants_perdus),
            "stock_plants"       : int(s.stock_plants),
            "unite"              : s.unite,
        }
        if s.is_reproducteur:
            entry["rendement_total"] = round(s.recoltes_total, 3)
            entry["unite_rendement"] = s.unite_recolte or ""
            entry["nb_recoltes"]     = s.nb_recoltes
        result.append(entry)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# [US_Stats_detail_par_variete] Détail par variété
# ══════════════════════════════════════════════════════════════════════════════

def calcul_stock_par_variete(db: Session, culture: str, date_ref: Optional[_date] = None) -> List[dict]:
    """
    [US_Stats_detail_par_variete / CA3, CA4, CA5, CA6, CA7]
    Agrège les événements par variété pour une culture donnée.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Filtre insensible à la casse via func.lower().
    Retourne [] si aucune plantation trouvée pour cette culture.

    Champs de chaque dict :
      variete, plants_plantes, plants_perdus, nb_recoltes, recoltes_total,
      unite_recolte, unite_plant, type_organe,
      date_premiere_plantation, date_derniere_recolte
    """
    cutoff = _cutoff_dt(date_ref)
    culture_lower = culture.lower()

    # ── 1. Plantations brutes (pour recalculer qte × rang en Python) ────────
    _q_plant = (
        db.query(
            Evenement.variete,
            Evenement.unite,
            Evenement.quantite,
            Evenement.rang,
            Evenement.date,
        )
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "plantation")
    )
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)
    plantations_raw = _q_plant.all()

    # [CA6] Culture inconnue → liste vide
    if not plantations_raw:
        return []

    # ── 2. Pertes par variété ────────────────────────────────────────────────
    _q_pertes = (
        db.query(Evenement.variete, func.sum(Evenement.quantite))
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "perte")
        .group_by(Evenement.variete)
    )
    if cutoff is not None:
        _q_pertes = _q_pertes.filter(Evenement.date <= cutoff)
    pertes_raw = _q_pertes.all()
    pertes: Dict[Optional[str], float] = {v: (q or 0) for v, q in pertes_raw}

    # ── 3. Récoltes brutes par variété (agrégation Python pour gérer multi-unités) ──
    _q_recoltes = (
        db.query(
            Evenement.variete,
            Evenement.unite,
            Evenement.quantite,
            Evenement.date,
        )
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "recolte")
    )
    if cutoff is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.date <= cutoff)
    recoltes_raw = _q_recoltes.all()

    # ── 4. type_organe depuis culture_config ────────────────────────────────
    cfg = (
        db.query(CultureConfig)
        .filter(func.lower(CultureConfig.nom) == culture_lower)
        .first()
    )
    type_organe: Optional[str] = cfg.type_organe_recolte if cfg else None

    # ── 5. Agrégation plantations par variété ───────────────────────────────
    plantes: Dict[Optional[str], dict] = {}
    for variete, unite, qte, rang, date_ev in plantations_raw:
        total = (qte or 0) * (rang or 1)
        if variete in plantes:
            plantes[variete]["total"] += total
            if date_ev and (
                plantes[variete]["date_min"] is None
                or date_ev < plantes[variete]["date_min"]
            ):
                plantes[variete]["date_min"] = date_ev
        else:
            plantes[variete] = {
                "total":    total,
                "unite":    unite or "plants",
                "date_min": date_ev,
            }

    # ── 6. Agrégation récoltes par variété — en grammes pour normaliser ────────
    _UNITE_TO_G_V = {"kg": 1000.0, "g": 1.0, "mg": 0.001}

    recoltes_g: Dict[Optional[str], dict] = {}
    for variete, unite, qte, date_ev in recoltes_raw:
        val_g = (qte or 0) * _UNITE_TO_G_V.get((unite or "").lower(), 1.0)
        if variete in recoltes_g:
            recoltes_g[variete]["nb"]    += 1
            recoltes_g[variete]["total"] += val_g
            if date_ev and (
                recoltes_g[variete]["date_max"] is None
                or date_ev > recoltes_g[variete]["date_max"]
            ):
                recoltes_g[variete]["date_max"] = date_ev
        else:
            recoltes_g[variete] = {
                "nb":       1,
                "total":    val_g,
                "unite":    unite or "",
                "date_max": date_ev,
            }

    def _best_g(total_g: float) -> tuple:
        if total_g >= 1000:
            return round(total_g / 1000, 2), "kg"
        return round(total_g, 1), "g"

    recoltes: Dict[Optional[str], dict] = {}
    for variete, d in recoltes_g.items():
        val, unite_out = _best_g(d["total"])
        recoltes[variete] = {
            "nb":       d["nb"],
            "total":    val,
            "unite":    unite_out,
            "date_max": d["date_max"],
        }

    # ── 7. Construction de la liste de résultats ─────────────────────────────
    # [CA5] None regroupé comme "Variété non précisée"
    # Les récoltes sans variété (None) sont fusionnées avec les variétés plantées
    # si la culture n'a qu'une seule variété plantée, sinon listées séparément.
    recoltes_sans_variete = recoltes.pop(None, None)
    varietes_plantees = list(plantes.keys())
    if recoltes_sans_variete:
        if len(varietes_plantees) == 1:
            # Une seule variété plantée → on rattache les récoltes sans variété à elle
            vk = varietes_plantees[0]
            if vk in recoltes:
                recoltes[vk]["nb"]    += recoltes_sans_variete["nb"]
                recoltes[vk]["total"] += recoltes_sans_variete["total"]
                if recoltes_sans_variete["date_max"] and (
                    recoltes[vk]["date_max"] is None
                    or recoltes_sans_variete["date_max"] > recoltes[vk]["date_max"]
                ):
                    recoltes[vk]["date_max"] = recoltes_sans_variete["date_max"]
                # Renormaliser après fusion
                total_g = recoltes[vk]["total"] * _UNITE_TO_G_V.get(recoltes[vk]["unite"], 1.0)
                val, unite_out = _best_g(total_g)
                recoltes[vk]["total"] = val
                recoltes[vk]["unite"] = unite_out
            else:
                recoltes[vk] = recoltes_sans_variete
        else:
            # Plusieurs variétés → garder "Variété non précisée" séparément (sans plantation)
            recoltes[None] = recoltes_sans_variete

    result: List[dict] = []
    all_keys = sorted(
        set(list(plantes.keys()) + ([None] if None in recoltes else [])),
        key=lambda v: ("" if v is None else v)
    )
    for vkey in all_keys:
        p = plantes.get(vkey, {"total": 0, "unite": "plants", "date_min": None})
        r = recoltes.get(vkey, {"nb": 0, "total": 0.0, "unite": "", "date_max": None})
        result.append({
            "variete":                  vkey if vkey is not None else "Variété non précisée",
            "plants_plantes":           p["total"],
            "plants_perdus":            pertes.get(vkey, 0.0),
            "nb_recoltes":              r["nb"],
            "recoltes_total":           r["total"],
            "unite_recolte":            r["unite"],
            "unite_plant":              p["unite"],
            "type_organe":              type_organe,
            "date_premiere_plantation": p["date_min"],
            "date_derniere_recolte":    r["date_max"],
        })

    return result


def calcul_godets(db: Session, include_epuises: bool = False, date_ref: Optional[_date] = None) -> Dict[str, dict]:
    """
    [US_mise_en_godet | US-022 | US-026] Agrège les mise_en_godet par culture/variété.
    Déduit les plantations du stock godet.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Args:
        include_epuises: si True, inclut aussi les entrées avec stock = 0 (tout planté).

    Champs : culture, variete, nb_godets, nb_graines_semees, nb_plants_godets,
             nb_plantes, stock_residuel_godet, taux_reussite
    """
    import logging as _log
    _logger = _log.getLogger("potager")

    cutoff = _cutoff_dt(date_ref)

    _q_rows = (
        db.query(
            Evenement.culture,
            Evenement.variete,
            func.sum(Evenement.nb_graines_semees),
            func.sum(Evenement.nb_plants_godets),
            func.count(Evenement.id),
        )
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_rows = _q_rows.filter(Evenement.date <= cutoff)
    rows = _q_rows.all()

    if not rows:
        return {}

    # [US-029] Taux de germination : calculer depuis les semis parents (origine_graines_id)
    # nb_graines_semees sur une mise_en_godet est un champ contextuel par lot, pas le total réel
    _q_links = (
        db.query(Evenement.culture, Evenement.variete, Evenement.origine_graines_id)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
    )
    if cutoff is not None:
        _q_links = _q_links.filter(Evenement.date <= cutoff)
    _godet_links = _q_links.all()
    _semis_ids_all = {r.origine_graines_id for r in _godet_links if r.origine_graines_id}
    _semis_qtites_all: Dict[int, int] = {}
    if _semis_ids_all:
        for sid, sqte in db.query(Evenement.id, Evenement.quantite).filter(Evenement.id.in_(_semis_ids_all)).all():
            _semis_qtites_all[sid] = int(sqte or 0)
    graines_par_cv: Dict[tuple, int] = {}
    _seen_cv: Dict[tuple, set] = {}
    for r in _godet_links:
        key = (r.culture, r.variete)
        if r.origine_graines_id and r.origine_graines_id not in _seen_cv.get(key, set()):
            _seen_cv.setdefault(key, set()).add(r.origine_graines_id)
            graines_par_cv[key] = graines_par_cv.get(key, 0) + _semis_qtites_all.get(r.origine_graines_id, 0)

    # [US-022] Plantations par (culture, variété)
    _q_plant = (
        db.query(
            Evenement.culture,
            Evenement.variete,
            func.sum(Evenement.quantite),
        )
        .filter(Evenement.type_action == "plantation")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)
    plant_rows = _q_plant.all()
    plantations: Dict[tuple, int] = {(c, v): int(q or 0) for c, v, q in plant_rows}

    # [US-022 / CA6] Plantation sans variété → rattacher à la variété unique par culture
    varietes_par_culture: Dict[str, list] = {}
    for culture, variete, *_ in rows:
        if variete is not None:
            varietes_par_culture.setdefault(culture, []).append(variete)

    for culture in [c for (c, v) in list(plantations) if v is None]:
        nb_sans_var = plantations.pop((culture, None), 0)
        if nb_sans_var > 0:
            varietes = varietes_par_culture.get(culture, [])
            if len(varietes) == 1:
                plantations[(culture, varietes[0])] = plantations.get((culture, varietes[0]), 0) + nb_sans_var
            elif len(varietes) == 0:
                plantations[(culture, None)] = nb_sans_var
            else:
                _logger.warning("[US-022] Plantation sans variété pour '%s' avec %d variétés en godet — ignorée", culture, len(varietes))

    # [CA6-reverse] Godet sans variété + plantation avec variété unique → rattacher
    for culture in {c for c, v, *_ in rows if v is None}:
        varietes_plantees = [(c, v) for (c, v) in list(plantations) if c == culture and v is not None]
        if len(varietes_plantees) == 1:
            c_key, v_key = varietes_plantees[0]
            nb = plantations.pop((c_key, v_key), 0)
            if nb > 0:
                plantations[(culture, None)] = plantations.get((culture, None), 0) + nb
                _logger.info("[US-022 CA6-reverse] Plantation '%s/%s' rattachée au godet sans variété", culture, v_key)

    # [vendu + perte_godet] Sorties de la pépinière hors plantation
    _q_sorties = (
        db.query(Evenement.culture, Evenement.variete, func.sum(Evenement.quantite))
        .filter(Evenement.type_action.in_(["vendu", "perte_godet"]))
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_sorties = _q_sorties.filter(Evenement.date <= cutoff)
    sorties_rows = _q_sorties.all()
    sorties: Dict[tuple, int] = {(c, v): int(q or 0) for c, v, q in sorties_rows}

    # CA6-reverse pour sorties aussi (godet sans variété + sortie avec variété unique)
    for culture in {c for c, v, *_ in rows if v is None}:
        varietes_sorties = [(c, v) for (c, v) in list(sorties) if c == culture and v is not None]
        if len(varietes_sorties) == 1:
            c_key, v_key = varietes_sorties[0]
            nb = sorties.pop((c_key, v_key), 0)
            if nb > 0:
                sorties[(culture, None)] = sorties.get((culture, None), 0) + nb

    # [vendu/perte_godet détail] par (culture, variete) pour exposition dans le résultat
    _q_vendus = (
        db.query(Evenement.culture, Evenement.variete, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "vendu")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_vendus = _q_vendus.filter(Evenement.date <= cutoff)
    vendus_rows = _q_vendus.all()
    vendus: Dict[tuple, int] = {(c, v): int(q or 0) for c, v, q in vendus_rows}

    _q_pertes_g = (
        db.query(Evenement.culture, Evenement.variete, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "perte_godet")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture, Evenement.variete)
    )
    if cutoff is not None:
        _q_pertes_g = _q_pertes_g.filter(Evenement.date <= cutoff)
    pertes_godet_rows = _q_pertes_g.all()
    pertes_godet: Dict[tuple, int] = {(c, v): int(q or 0) for c, v, q in pertes_godet_rows}

    result: Dict[str, dict] = {}
    for culture, variete, tot_g, tot_p, nb in rows:
        nb_p = int(tot_p) if tot_p else 0
        nb_g = int(tot_g) if tot_g else 0
        nb_g_semis = graines_par_cv.get((culture, variete), 0)
        taux = round(nb_p / nb_g_semis * 100) if (nb_g_semis and nb_p) else None
        nb_plantes     = plantations.get((culture, variete), 0)
        nb_vendus_val  = vendus.get((culture, variete), 0)
        nb_pertes_val  = pertes_godet.get((culture, variete), 0)
        stock_residuel = max(0, nb_p - nb_plantes - nb_vendus_val - nb_pertes_val)

        if stock_residuel == 0 and not include_epuises:
            continue

        key = culture + (f" ({variete})" if variete else "")
        result[key] = {
            "culture":              culture,
            "variete":              variete,
            "nb_godets":            nb,
            "nb_graines_semees":    nb_g,
            "nb_plants_godets":     nb_p,
            "nb_plantes":           nb_plantes,
            "nb_vendus":            nb_vendus_val,
            "nb_pertes_godet":      nb_pertes_val,
            "stock_residuel_godet": stock_residuel,
            "taux_reussite":        taux,
        }
    return dict(sorted(result.items()))


def calcul_godets_par_culture(db: Session, culture: str, date_ref: Optional[_date] = None) -> List[dict]:
    """
    [US-018 / CA1, CA2, CA6 | US-022 / CA1-CA6] Retourne les godets actifs par variété.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    stock_residuel_godet = Σ nb_plants_godets (mise_en_godet) − Σ quantite (plantation)
    par couple (culture, variété). Seules les variétés avec stock > 0 sont retournées (CA4).

    Champs : variete, nb_plants_godets, nb_plantes, stock_residuel_godet,
             nb_graines_semees, taux_reussite, nb_godets, date_derniere_mise_en_godet
    """
    import logging as _log
    _logger = _log.getLogger("potager")

    cutoff = _cutoff_dt(date_ref)
    culture_lower = culture.lower()

    _q_rows = (
        db.query(
            Evenement.variete,
            func.sum(Evenement.nb_plants_godets),
            func.sum(Evenement.nb_graines_semees),
            func.count(Evenement.id),
            func.max(Evenement.date),
        )
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.variete)
    )
    if cutoff is not None:
        _q_rows = _q_rows.filter(Evenement.date <= cutoff)
    rows = _q_rows.all()

    if not rows:
        return []

    # [US-029] Taux de germination depuis les semis parents (origine_graines_id)
    _q_links_var = (
        db.query(Evenement.variete, Evenement.origine_graines_id)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.culture.isnot(None))
    )
    if cutoff is not None:
        _q_links_var = _q_links_var.filter(Evenement.date <= cutoff)
    _godet_links_var = _q_links_var.all()
    _semis_ids_var = {r.origine_graines_id for r in _godet_links_var if r.origine_graines_id}
    _semis_qtites_var: Dict[int, int] = {}
    if _semis_ids_var:
        for sid, sqte in db.query(Evenement.id, Evenement.quantite).filter(Evenement.id.in_(_semis_ids_var)).all():
            _semis_qtites_var[sid] = int(sqte or 0)
    graines_par_variete: Dict[Optional[str], int] = {}
    _seen_var: Dict[Optional[str], set] = {}
    for r in _godet_links_var:
        if r.origine_graines_id and r.origine_graines_id not in _seen_var.get(r.variete, set()):
            _seen_var.setdefault(r.variete, set()).add(r.origine_graines_id)
            graines_par_variete[r.variete] = graines_par_variete.get(r.variete, 0) + _semis_qtites_var.get(r.origine_graines_id, 0)

    # [US-022 / CA1] Plantations par variété — à déduire du stock godet
    _q_plant_var = (
        db.query(
            Evenement.variete,
            func.sum(Evenement.quantite),
        )
        .filter(Evenement.type_action == "plantation")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.variete)
    )
    if cutoff is not None:
        _q_plant_var = _q_plant_var.filter(Evenement.date <= cutoff)
    plant_rows = _q_plant_var.all()
    plantations: Dict[Optional[str], int] = {v: int(q or 0) for v, q in plant_rows}

    # [US-022 / CA6] Plantation sans variété → rattacher selon le contexte godet
    nb_plantes_sans_variete = plantations.pop(None, 0)
    ca6_applied = False
    if nb_plantes_sans_variete > 0:
        varietes_avec_godet = [r[0] for r in rows if r[0] is not None]
        if len(varietes_avec_godet) == 0:
            # Godet aussi sans variété → match direct (cas le plus courant)
            plantations[None] = nb_plantes_sans_variete
        elif len(varietes_avec_godet) == 1:
            v_unique = varietes_avec_godet[0]
            plantations[v_unique] = plantations.get(v_unique, 0) + nb_plantes_sans_variete
            ca6_applied = True  # [US-029 CA10] marque pour bloquer CA6-reverse
        else:
            _logger.warning(
                "[US-022] Plantation sans variété pour '%s' avec %d variétés en godet — ignorée du calcul",
                culture, len(varietes_avec_godet),
            )

    # [CA6-reverse] Godet sans variété + plantation avec variété unique → rattacher
    # [US-029 CA10] Ne s'applique PAS si CA6 vient d'attribuer les plants (évite l'annulation mutuelle)
    if not ca6_applied and any(r[0] is None for r in rows):
        varietes_dans_plantations = [v for v in plantations if v is not None]
        if len(varietes_dans_plantations) == 1:
            v_unique = varietes_dans_plantations[0]
            nb = plantations.pop(v_unique, 0)
            if nb > 0:
                plantations[None] = plantations.get(None, 0) + nb
                _logger.info("[US-022 CA6-reverse] Plantation '%s/%s' rattachée au godet sans variété", culture, v_unique)

    # [vendu + perte_godet] Sorties hors plantation
    _q_sorties_var = (
        db.query(Evenement.variete, Evenement.type_action, func.sum(Evenement.quantite))
        .filter(Evenement.type_action.in_(["vendu", "perte_godet"]))
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.variete, Evenement.type_action)
    )
    if cutoff is not None:
        _q_sorties_var = _q_sorties_var.filter(Evenement.date <= cutoff)
    sorties_par_variete_rows = _q_sorties_var.all()
    vendus_var: Dict[Optional[str], int]      = {}
    pertes_godet_var: Dict[Optional[str], int] = {}
    for variete, action, qte in sorties_par_variete_rows:
        if action == "vendu":
            vendus_var[variete] = vendus_var.get(variete, 0) + int(qte or 0)
        else:
            pertes_godet_var[variete] = pertes_godet_var.get(variete, 0) + int(qte or 0)

    # CA6-reverse pour vendu/perte_godet (godet sans variété + sortie avec variété unique)
    if any(r[0] is None for r in rows):
        for d in (vendus_var, pertes_godet_var):
            varietes_non_none = [v for v in d if v is not None]
            if len(varietes_non_none) == 1:
                v_unique = varietes_non_none[0]
                nb = d.pop(v_unique, 0)
                if nb > 0:
                    d[None] = d.get(None, 0) + nb

    result: List[dict] = []
    for variete, tot_p, tot_g, nb, date_max in rows:
        nb_p          = int(tot_p) if tot_p else 0
        nb_g          = int(tot_g) if tot_g else 0
        nb_g_semis    = graines_par_variete.get(variete, 0)
        taux          = round(nb_p / nb_g_semis * 100) if (nb_g_semis and nb_p) else None
        nb_plantes    = plantations.get(variete, 0)
        nb_v          = vendus_var.get(variete, 0)
        nb_pg         = pertes_godet_var.get(variete, 0)
        stock_residuel = max(0, nb_p - nb_plantes - nb_v - nb_pg)

        # [US-022 / CA4] On n'expose que les godets non entièrement plantés
        if stock_residuel == 0:
            continue

        result.append({
            "variete":                    variete,
            "nb_plants_godets":           nb_p,
            "nb_plantes":                 nb_plantes,
            "nb_vendus":                  nb_v,
            "nb_pertes_godet":            nb_pg,
            "stock_residuel_godet":       stock_residuel,
            "nb_graines_semees":          nb_g,
            "taux_reussite":              taux,
            "nb_godets":                  nb,
            "date_derniere_mise_en_godet": date_max,
        })
    return sorted(result, key=lambda x: ("" if x["variete"] is None else x["variete"]))


def _find_plantation_sources(
    db: Session,
    culture: str,
    variete: str | None,
    quantite: float,
) -> tuple[str | None, str | None]:
    """
    [US-029 CA5/CA7/CA8] Trouve la variété héritée et les IDs de godets sources pour une plantation.

    - Si variete=None et 1 seule variété active en godet → hérite la variété (CA5)
    - Allocation FIFO : consomme les lots les plus anciens en premier (CA8)
    - Si plusieurs lots nécessaires → IDs séparés par ";" dans source_evenement_ids (CA7)

    Retourne (variete_resolue, source_evenement_ids_str).
    Retourne (None, None) si la variété est ambiguë (plusieurs variétés, menu inline requis).
    """
    import logging as _log
    _logger = _log.getLogger("potager")

    culture_lower = culture.lower()

    # Charger tous les godets pour cette culture, FIFO (plus ancien d'abord)
    godet_events = (
        db.query(Evenement.id, Evenement.variete, Evenement.nb_plants_godets, Evenement.date)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.culture.isnot(None))
        .filter(Evenement.nb_plants_godets.isnot(None))
        .order_by(Evenement.date.asc().nullsfirst(), Evenement.id.asc())
        .all()
    )

    if not godet_events:
        return (variete, None)

    # Calculer les consommations déjà enregistrées via source_evenement_ids
    plant_linked = (
        db.query(Evenement.source_evenement_ids, Evenement.quantite)
        .filter(Evenement.type_action == "plantation")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.source_evenement_ids.isnot(None))
        .all()
    )
    consumed: dict[int, float] = {}
    for src_ids_str, p_qte in plant_linked:
        for part in (src_ids_str or "").split(";"):
            try:
                gid = int(part.strip())
                consumed[gid] = consumed.get(gid, 0.0) + float(p_qte or 0)
            except ValueError:
                pass

    # Stock résiduel par godet
    residuel: dict[int, float] = {
        g.id: max(0.0, float(g.nb_plants_godets) - consumed.get(g.id, 0.0))
        for g in godet_events
    }

    # Résolution variété si None (CA5)
    if variete is None:
        varietes_actives = {
            g.variete for g in godet_events
            if g.variete is not None and residuel.get(g.id, 0.0) > 0
        }
        if len(varietes_actives) == 1:
            variete = next(iter(varietes_actives))
            _logger.info("[US-029 CA5] Variété unique déduite depuis godet : '%s' pour '%s'", variete, culture)
        elif len(varietes_actives) == 0:
            return (None, None)
        else:
            return (None, None)  # Ambiguïté : menu inline requis en amont

    # Allocation FIFO sur les godets de la variété (CA8)
    godets_variete = [
        g for g in godet_events
        if g.variete == variete and residuel.get(g.id, 0.0) > 0
    ]

    if not godets_variete:
        return (variete, None)  # variété connue mais plus de stock godet actif

    remaining   = float(quantite)
    source_ids: list[str] = []
    for g in godets_variete:
        if remaining <= 0:
            break
        if residuel[g.id] > 0:
            source_ids.append(str(g.id))
            remaining -= residuel[g.id]

    return (variete, ";".join(source_ids) if source_ids else None)


_MOIS_FR = [
    "jan", "fév", "mar", "avr", "mai", "juin",
    "juil", "aoû", "sep", "oct", "nov", "déc",
]


def _fmt_date_variete(dt: Optional[datetime], current_year: int) -> str:
    """Formate une date en 'dd mmm' (même année) ou 'dd mmm YYYY'."""
    if dt is None:
        return "?"
    mois = _MOIS_FR[dt.month - 1]
    if dt.year == current_year:
        return f"{dt.day:02d} {mois}"
    return f"{dt.day:02d} {mois} {dt.year}"


def format_variete_bloc_telegram(v: dict) -> str:
    """
    [US_Stats_detail_par_variete / CA4]
    Formate un bloc variété pour /stats [culture] Telegram.

    Respecte la logique reproducteur (récolte continue) vs végétatif (récolte destructive).
    Format date : 'dd mmm' si même année, 'dd mmm YYYY' sinon.
    'en cours' si date_derniere_recolte est None.
    """
    nom            = v["variete"]
    plants_plantes = int(v["plants_plantes"])
    plants_perdus  = int(v["plants_perdus"])
    nb_recoltes    = v["nb_recoltes"]
    recoltes_total = v["recoltes_total"]
    unite_recolte  = v["unite_recolte"] or "unités"
    unite_plant    = v["unite_plant"] or "plants"
    type_organe    = v["type_organe"]
    date_plantation = v["date_premiere_plantation"]
    date_recolte    = v["date_derniere_recolte"]

    is_repr      = (type_organe == "reproducteur")
    current_year = datetime.now().year

    # Calcul de la période pour affichage inline
    date_periode = ""
    if date_plantation:
        date_debut = _fmt_date_variete(date_plantation, current_year)
        date_fin   = _fmt_date_variete(date_recolte, current_year) if date_recolte else "en cours"
        date_periode = f" · 🗓️ {date_debut} → {date_fin}"

    lines = [f"🔸 *{nom}*"]

    if is_repr:
        # [CA4] Reproducteur : plants actifs + détails si perte + rendement + date
        stock = max(0, plants_plantes - plants_perdus)
        base  = f"  • {stock} {unite_plant} actifs"
        # Détails entre parenthèses uniquement si le stock diffère du total planté (perte)
        if plants_perdus > 0:
            base += f" (planté {plants_plantes}, perdu {plants_perdus})"
        if recoltes_total > 0:
            r_val  = round(recoltes_total, 2)
            base  += f" · {r_val} {unite_recolte} récoltés ({nb_recoltes} fois)"
        base += date_periode
        lines.append(base)
    else:
        # [CA4] Végétatif : récolte destructive + détails si différence + date
        stock = max(0, plants_plantes - plants_perdus - int(recoltes_total))
        base  = f"  • {stock} {unite_plant}"
        # Détails uniquement si stock != plants_plantes (perte ou récolte destructive)
        if plants_perdus > 0 or recoltes_total > 0:
            details = [f"planté {plants_plantes}"]
            if plants_perdus > 0:
                details.append(f"perdu {plants_perdus}")
            if recoltes_total > 0:
                details.append(f"récolté {int(recoltes_total)}")
            base += f" ({', '.join(details)})"
        lines.append(base + date_periode)

    return "\n".join(lines)
