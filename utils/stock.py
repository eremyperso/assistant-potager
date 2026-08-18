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
from sqlalchemy import func, or_

from database.models import Evenement, CultureConfig, Parcelle


def _cutoff_dt(date_ref: Optional[_date]) -> Optional[datetime]:
    """[US-030] Borne haute inclusive (23:59:59) pour filtrage temporel par date de référence."""
    if date_ref is None:
        return None
    return datetime(date_ref.year, date_ref.month, date_ref.day, 23, 59, 59)


import logging as _logging
_log_stock = _logging.getLogger("potager")

# [migration_v15] parcelles.est_pepiniere classe explicitement une parcelle comme
# serre/pépinière (y compris la parcelle synthétique "Non localisé", migration_v12,
# marquée est_pepiniere=true par migration_v15). Un semis rattaché à une telle
# parcelle reste un semis pépinière tant qu'aucune plantation réelle n'a eu lieu —
# même si son parcelle_id est renseigné. isnot(None) seul ne suffit donc pas pour
# détecter "pleine terre".
def _cond_semis_pleine_terre(evenement_cls, parcelle_cls):
    """[US-037 CA4/CA5] Condition SQL : semis rattaché à une VRAIE parcelle de
    pleine terre (parcelle_id non null ET parcelle non marquée pépinière)."""
    return (
        (evenement_cls.parcelle_id.isnot(None))
        & (parcelle_cls.est_pepiniere.is_(False))
    )


def _resoudre_unite_dominante(
    par_unite: "Dict[str, Dict[str, float]]", contexte: str = "",
) -> "Dict[str, tuple]":
    """
    [US-037 / CA2] Une même culture ne doit JAMAIS voir ses quantités additionnées
    entre unités incompatibles (ex : 100 graines + 2 m² ≠ 102 de quoi que ce soit).

    Reçoit { culture: { unite: total } } et retourne { culture: (total, unite) } en
    ne conservant QUE l'unité dominante (celle au plus grand total cumulé) par
    culture. Les quantités des autres unités sont exclues du total affiché — pas
    additionnées, pas converties — et un warning est loggé pour rester traçable.
    """
    result: Dict[str, tuple] = {}
    for culture, totaux in par_unite.items():
        if not totaux:
            continue
        unite_dominante, total_dominant = max(totaux.items(), key=lambda kv: kv[1])
        if len(totaux) > 1:
            _log_stock.warning(
                "[US-037 CA2] Unités incompatibles pour '%s'%s : %s — seule '%s' (%.2f) est comptée, "
                "les autres unités sont exclues du total (pas additionnées, pas converties)",
                culture, f" ({contexte})" if contexte else "", totaux, unite_dominante, total_dominant,
            )
        result[culture] = (total_dominant, unite_dominante)
    return result


@dataclass
class StockCulture:
    """[US-002] Données de stock agronomique pour une culture donnée.

    [US-036] Les récoltes sont désormais agrégées dans DEUX pools distincts,
    quel que soit le type d'organe :
      - "pièces"  (recoltes_total/unite_recolte/nb_recoltes) : nombre de plants
        récoltés — sert UNIQUEMENT à la déduction de stock (végétatif/inconnu).
      - "poids"   (rendement_total/unite_rendement/nb_recoltes_poids) : kg/g/mg
        récoltés — sert UNIQUEMENT au rendement, pour toute culture (végétatif
        OU reproducteur). Ne doit JAMAIS être mélangé avec le pool "pièces".
    """
    culture:             str
    unite:               str
    type_organe:         Optional[str]   # "végétatif" | "reproducteur" | None

    # Plantations
    plants_plantes:      float = 0.0

    # Pertes (tous types)
    plants_perdus:       float = 0.0

    # Récoltes en pièces (nombre de plants) — déduction de stock
    nb_recoltes:         int   = 0
    recoltes_total:      float = 0.0
    unite_recolte:       str   = ""

    # Récoltes en poids (kg/g) — rendement, indépendant du type d'organe
    nb_recoltes_poids:   int   = 0
    rendement_total:     float = 0.0
    unite_rendement:     str   = ""

    @property
    def stock_plants(self) -> float:
        """
        [US-002 / CA1 & CA2] [US-036 / CA6]
        - végétatif    : stock = plantations - pertes - récoltes (pièces uniquement)
        - reproducteur : stock = plantations - pertes  (récoltes indépendantes)
        - inconnu      : même logique que végétatif (conservateur)

        Le pool "poids" (rendement) n'intervient JAMAIS dans ce calcul, pour
        éviter une double déduction quand une récolte végétative est aussi
        pesée (US-036).
        """
        if self.type_organe == "reproducteur":
            return max(0.0, self.plants_plantes - self.plants_perdus)
        # végétatif ou inconnu
        return max(0.0, self.plants_plantes - self.plants_perdus - self.recoltes_total)

    @property
    def is_reproducteur(self) -> bool:
        return self.type_organe == "reproducteur"


def get_type_organe(db: Session, culture: str, potager_id: Optional[int] = None) -> Optional[str]:
    """Retourne le type d'organe pour une culture depuis culture_config.
    [US-042] potager_id=None (défaut) = comportement historique non scopé, réservé
    aux tests unitaires directs de utils/. Les appelants applicatifs (app/services/)
    passent toujours potager_id=ctx.potager_id — une fiche globale (potager_id NULL)
    reste visible dans tous les cas."""
    q = db.query(CultureConfig).filter(CultureConfig.nom == culture)
    if potager_id is not None:
        q = q.filter(or_(CultureConfig.potager_id == potager_id, CultureConfig.potager_id.is_(None)))
    cfg = q.first()
    return cfg.type_organe_recolte if cfg else None


def calcul_stock_cultures(
    db: Session, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> Dict[str, StockCulture]:
    """
    [US-002] Calcule le stock réel de toutes les cultures plantées.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Retourne un dict { culture: StockCulture } trié par culture.

    Algorithme :
    1. Agréger plantations par (culture, unite) avec rang
    1b. [US-037 / CA4, CA5] Agréger les semis pleine terre (parcelle_id non null)
        comme des plantations à part entière — pas de conversion d'unité (m²
        reste m², pieds reste pieds), pas de multiplication par un rang.
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
    if potager_id is not None:
        _q_plant = _q_plant.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)
    plantations_raw = _q_plant.all()

    # [US-037 / CA2] Accumulation PAR unité — jamais directement en un seul total,
    # pour ne jamais additionner des graines avec des m² ou des pieds.
    plantes_par_unite: Dict[str, Dict[str, float]] = {}

    def _accumuler(culture: str, unite: str, total: float) -> None:
        sous_dict = plantes_par_unite.setdefault(culture, {})
        sous_dict[unite] = sous_dict.get(unite, 0.0) + total

    for culture, unite, qte, rang in plantations_raw:
        total = (qte or 0) * (rang or 1)
        _accumuler(culture, unite or "plants", total)

    # ── 1b. [US-037 / CA4, CA5] Semis pleine terre (parcelle_id non null) ───
    # Un semis directement lié à une VRAIE parcelle de pleine terre est un semis à
    # la volée / en terre, pas un semis en barquette destiné à la pépinière (celui-ci
    # n'a pas de parcelle_id, ou est rattaché à une parcelle marquée
    # est_pepiniere=true — serre, pépinière, ou la parcelle factice "Non localisé").
    # Il alimente donc directement le stock, comme une plantation : aucune
    # conversion d'unité (m² reste m², pieds/graines restent tels quels).
    _q_semis_pt = (
        db.query(
            Evenement.culture,
            Evenement.unite,
            Evenement.quantite,
        )
        .join(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.culture.isnot(None))
        .filter(_cond_semis_pleine_terre(Evenement, Parcelle))
    )
    if potager_id is not None:
        _q_semis_pt = _q_semis_pt.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_semis_pt = _q_semis_pt.filter(Evenement.date <= cutoff)
    semis_pt_raw = _q_semis_pt.all()

    for culture, unite, qte in semis_pt_raw:
        _accumuler(culture, unite or "graines", qte or 0.0)

    if not plantes_par_unite:
        return {}

    # [US-037 / CA2] Résolution : une seule unité "dominante" par culture, jamais
    # de somme entre unités différentes (voir _resoudre_unite_dominante).
    plantes = _resoudre_unite_dominante(plantes_par_unite, contexte="plantations+semis pleine terre")

    # ── 2. Pertes par culture ───────────────────────────────────────────────
    _q_pertes = (
        db.query(Evenement.culture, func.sum(Evenement.quantite))
        .filter(Evenement.type_action == "perte")
        .filter(Evenement.culture.isnot(None))
        .group_by(Evenement.culture)
    )
    if potager_id is not None:
        _q_pertes = _q_pertes.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_pertes = _q_pertes.filter(Evenement.date <= cutoff)
    pertes_raw = _q_pertes.all()
    pertes: Dict[str, float] = {c: (q or 0) for c, q in pertes_raw}

    # ── 3. Récoltes par (culture, unite) — séparées en 2 pools ──────────────
    # [US-036] pool "pièces" (déduction de stock) vs pool "poids" (rendement) :
    # un même couple (culture, unite="g") ne doit JAMAIS alimenter le stock,
    # et un couple (culture, unite="plants") ne doit JAMAIS alimenter le rendement.
    _UNITE_TO_G = {"kg": 1000.0, "g": 1.0, "mg": 0.001}

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
    if potager_id is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.date <= cutoff)
    recoltes_raw = _q_recoltes.all()

    recoltes_pieces: Dict[str, tuple] = {}   # culture → (nb, total_pieces)
    recoltes_poids_g: Dict[str, tuple] = {}  # culture → (nb, total_g)
    for culture, unite, nb, total in recoltes_raw:
        unite_l = (unite or "").lower()
        if unite_l in _UNITE_TO_G:
            val_g = (total or 0.0) * _UNITE_TO_G[unite_l]
            prev_nb, prev_g = recoltes_poids_g.get(culture, (0, 0.0))
            recoltes_poids_g[culture] = (prev_nb + nb, prev_g + val_g)
        else:
            prev_nb, prev_total = recoltes_pieces.get(culture, (0, 0.0))
            recoltes_pieces[culture] = (prev_nb + nb, prev_total + (total or 0.0))

    recoltes: Dict[str, tuple] = {  # culture → (nb, valeur_lisible, unite)
        c: (nb, round(total, 1), "plants") for c, (nb, total) in recoltes_pieces.items()
    }
    rendements: Dict[str, tuple] = {}  # culture → (nb, valeur_lisible, unite)
    for culture, (nb, total_g) in recoltes_poids_g.items():
        val, unite_out = _best_unite(total_g)
        rendements[culture] = (nb, val, unite_out)

    # ── 4. Construction des objets StockCulture ─────────────────────────────
    result: Dict[str, StockCulture] = {}
    for culture, (total_plants, unite) in sorted(plantes.items()):
        type_organe = get_type_organe(db, culture, potager_id=potager_id)
        rec = recoltes.get(culture, (0, 0.0, ""))
        rdt = rendements.get(culture, (0, 0.0, ""))

        stock = StockCulture(
            culture           = culture,
            unite             = unite or "plants",
            type_organe       = type_organe,
            plants_plantes    = total_plants,
            plants_perdus     = pertes.get(culture, 0.0),
            nb_recoltes       = rec[0],
            recoltes_total    = rec[1],
            unite_recolte     = rec[2],
            nb_recoltes_poids = rdt[0],
            rendement_total   = rdt[1],
            unite_rendement   = rdt[2],
        )
        result[culture] = stock

    return result


def _fmt_qte_unite(valeur: float, unite: str) -> float | int:
    """[US-037 / CA9] Une surface m² est fractionnable (1.5 m²) — ne jamais tronquer
    en entier comme pour un nombre de plants/graines/pieds. Un m² entier (2.0) s'affiche
    "2", pas "2.0"."""
    if unite == "m²":
        arrondi = round(valeur, 2)
        return int(arrondi) if arrondi == int(arrondi) else arrondi
    return int(valeur)


def format_stock_ligne_telegram(s: StockCulture) -> str:
    """
    [US-002 / CA3] [US-036] [US-037 / CA9] Formate une ligne de stock pour /stats Telegram.

    Exemples attendus :
    - végétatif  : "salade : *19 plants* (planté 25, perdu 4, récolté 2)"
    - végétatif pesé : "betterave : *18 plants* (planté 20, récolté 2) · *0.25 kg* récoltés"
    - reproducteur: "tomate : *5 plants actifs* · 8.5 kg récoltés (3 fois)"
    - reproducteur semé en m² : "haricot : *2 m² actifs* · 1.4 kg récoltés (2 fois)"
    - inconnu    : "carotte : *50 plants* (planté 50)"
    """
    unite = s.unite
    stock = _fmt_qte_unite(s.stock_plants, unite)

    if s.is_reproducteur:
        # Stock = plantes vivantes ; rendement = poids cumulé (pool "poids")
        base = f"• {s.culture} : *{stock} {unite} actifs*"
        details = [f"planté {_fmt_qte_unite(s.plants_plantes, unite)}"]
        if s.plants_perdus > 0:
            details.append(f"perdu {_fmt_qte_unite(s.plants_perdus, unite)}")

        if s.rendement_total > 0:
            r_val  = round(s.rendement_total, 2)
            r_u    = s.unite_rendement or "unités"
            r_nb   = s.nb_recoltes_poids
            base  += f" · *{r_val} {r_u}* récoltés ({r_nb} fois)"

        return base + f" ({', '.join(details)})"

    else:
        # Végétatif : récolte en pièces réduit le stock ; le poids (s'il existe) est un rendement à part
        base = f"• {s.culture} : *{stock} {unite}*"
        details = [f"planté {_fmt_qte_unite(s.plants_plantes, unite)}"]
        if s.plants_perdus > 0:
            details.append(f"perdu {_fmt_qte_unite(s.plants_perdus, unite)}")
        if s.recoltes_total > 0:
            details.append(f"récolté {_fmt_qte_unite(s.recoltes_total, unite)}")
        base += f" ({', '.join(details)})"

        if s.rendement_total > 0:
            r_val = round(s.rendement_total, 2)
            r_u   = s.unite_rendement or "unités"
            base += f" · *{r_val} {r_u}* récoltés"

        return base


def calcul_semis(
    db: Session, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> Dict[str, dict]:
    """
    [US-014 / CA1] Agrège les semis par culture.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Un semis est un stade agronomique (germination/godet) indépendant des plantations.
    Les récoltes sont toujours liées aux plantations, jamais aux semis — on ne les
    croise donc plus ici pour éviter une double attribution incorrecte.

    Retourne un dict { culture: { nb_semis, total_seme, unite, type_organe } }
    """
    cutoff = _cutoff_dt(date_ref)

    # [US-037 / CA2] Lecture brute par (culture, unite) — jamais un SUM SQL global
    # par culture, qui additionnerait à tort des graines et des m² entre eux.
    _q_semis = (
        db.query(Evenement.culture, Evenement.unite, Evenement.quantite)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.culture.isnot(None))
    )
    if potager_id is not None:
        _q_semis = _q_semis.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_semis = _q_semis.filter(Evenement.date <= cutoff)
    semis_rows = _q_semis.all()
    if not semis_rows:
        return {}

    semis_par_unite: Dict[str, Dict[str, float]] = {}
    nb_par_culture_unite: Dict[str, Dict[str, int]] = {}
    for culture, unite, qte in semis_rows:
        u = unite or "graines"
        sous_total = semis_par_unite.setdefault(culture, {})
        sous_total[u] = sous_total.get(u, 0.0) + (qte or 0.0)
        sous_nb = nb_par_culture_unite.setdefault(culture, {})
        sous_nb[u] = sous_nb.get(u, 0) + 1

    # Résolution : une seule unité dominante par culture (voir _resoudre_unite_dominante).
    semis_resolus = _resoudre_unite_dominante(semis_par_unite, contexte="calcul_semis")
    unites: Dict[str, str] = {c: u for c, (_, u) in semis_resolus.items()}

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
    if potager_id is not None:
        _q_godets = _q_godets.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_cultures_g = _q_cultures_g.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_pertes_s = _q_pertes_s.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_pertes_s = _q_pertes_s.filter(Evenement.date <= cutoff)
    pertes_semis_raw = _q_pertes_s.all()
    pertes_semis_dict: Dict[str, int] = {
        c: int(q or 0) for c, q in pertes_semis_raw
        if c.lower() not in cultures_avec_godets
    }

    # Parcelles de semis pleine terre par culture, "Non localisé" inclus.
    # [fix visibilité semis sans parcelle] Un semis sans parcelle_id (aucune
    # parcelle précisée à la dictée) n'est ni une vraie localisation pleine
    # terre, ni rattaché à une parcelle pépinière/serre — il ne doit pas pour
    # autant disparaître de l'affichage : il rejoint le groupe "Non localisé",
    # au même titre que les plantations sans parcelle (CA7, utils/parcelles.py).
    from sqlalchemy import or_ as _sa_or, and_ as _sa_and
    _q_parcelles_pt = (
        db.query(Evenement.culture, Evenement.parcelle_id, Parcelle.nom)
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(_sa_or(
            Evenement.parcelle_id.is_(None),
            _sa_and(Parcelle.est_pepiniere.is_(False), Parcelle.actif.is_(True)),
        ))
    )
    if potager_id is not None:
        _q_parcelles_pt = _q_parcelles_pt.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_parcelles_pt = _q_parcelles_pt.filter(Evenement.date <= cutoff)
    parcelles_pt_raw = _q_parcelles_pt.all()
    parcelles_pt: Dict[str, list] = {}
    for culture_pt, parcelle_id_pt, nom_p in parcelles_pt_raw:
        nom_affiche = nom_p if parcelle_id_pt is not None else "Non localisé"
        if culture_pt not in parcelles_pt:
            parcelles_pt[culture_pt] = []
        if nom_affiche not in parcelles_pt[culture_pt]:
            parcelles_pt[culture_pt].append(nom_affiche)

    result: Dict[str, dict] = {}
    for culture, (total_seme, unite_dominante) in semis_resolus.items():
        nb          = nb_par_culture_unite.get(culture, {}).get(unite_dominante, 0)
        consommees  = graines_consommees.get(culture, 0)
        perte_semis = pertes_semis_dict.get(culture, 0)
        result[culture] = {
            "nb_semis":               nb,
            "total_seme":             total_seme,
            "unite":                  unites.get(culture, "graines"),
            "type_organe":            get_type_organe(db, culture, potager_id=potager_id),
            "plants_en_godet":        plants_en_godet.get(culture, 0),
            "stock_residuel":         max(0, int(total_seme) - consommees - perte_semis),
            "parcelles_pleine_terre": parcelles_pt.get(culture, []),
        }
    return dict(sorted(result.items()))


def calcul_semis_par_culture(
    db: Session, culture: str, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> List[dict]:
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
    if potager_id is not None:
        _q_semis = _q_semis.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_godets_var = _q_godets_var.filter(Evenement.potager_id == potager_id)
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

    # [US-037 / CA2] Accumulation par (variete, unite) — jamais un total qui mélange
    # graines/pieds/m² pour une même variété (voir _resoudre_unite_dominante).
    semis_par_unite_var: Dict[Optional[str], Dict[str, float]] = {}
    nb_par_variete_unite: Dict[Optional[str], Dict[str, int]] = {}
    date_premier_par_variete: Dict[Optional[str], datetime] = {}
    for variete, unite, qte, date_ev in semis_raw:
        u = unite or "graines"
        sous_total = semis_par_unite_var.setdefault(variete, {})
        sous_total[u] = sous_total.get(u, 0.0) + (qte or 0.0)
        sous_nb = nb_par_variete_unite.setdefault(variete, {})
        sous_nb[u] = sous_nb.get(u, 0) + 1
        if date_ev and (
            variete not in date_premier_par_variete
            or date_ev < date_premier_par_variete[variete]
        ):
            date_premier_par_variete[variete] = date_ev

    semis_var_resolus = _resoudre_unite_dominante(semis_par_unite_var, contexte=f"{culture} semis par variété")
    agregat: Dict[Optional[str], dict] = {
        variete: {
            "nb_semis":           nb_par_variete_unite.get(variete, {}).get(unite, 0),
            "total_seme":         total,
            "unite":              unite,
            "date_premier_semis": date_premier_par_variete.get(variete),
        }
        for variete, (total, unite) in semis_var_resolus.items()
    }

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
    db: Session, annee: int, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
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

    _q = (
        db.query(func.date(Evenement.date), func.count(Evenement.id))
        .filter(Evenement.date >= debut)
        .filter(Evenement.date <= fin)
    )
    if potager_id is not None:
        _q = _q.filter(Evenement.potager_id == potager_id)
    rows = _q.group_by(func.date(Evenement.date)).all()
    return {str(jour): nb for jour, nb in rows}


def calcul_rendement_mensuel(
    db: Session, annee: int, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> dict:
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

    _q_rows = (
        db.query(Evenement.culture, Evenement.unite, Evenement.quantite, Evenement.date)
        .filter(Evenement.type_action == "recolte")
        .filter(Evenement.culture.isnot(None))
        .filter(Evenement.date >= debut)
        .filter(Evenement.date <= fin)
    )
    if potager_id is not None:
        _q_rows = _q_rows.filter(Evenement.potager_id == potager_id)
    rows = _q_rows.all()
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
    [US-002 / CA4] [US-036] [US-037 / CA9] Retourne les données de stock sous forme JSON pour l'API /stats.

    Champs distincts selon le type :
    - stock_plants         : plants actuellement en vie (fractionnaire si unite="m²")
    - rendement_total      : total récolté en poids (toujours pour reproducteur ;
                              également pour végétatif si des récoltes pesées existent)
    - unite_rendement      : unité du rendement
    """
    result = []
    for culture, s in stocks.items():
        entry = {
            "culture"            : culture,
            "type_organe"        : s.type_organe or "inconnu",
            "plants_plantes"     : _fmt_qte_unite(s.plants_plantes, s.unite),
            "plants_perdus"      : _fmt_qte_unite(s.plants_perdus, s.unite),
            "stock_plants"       : _fmt_qte_unite(s.stock_plants, s.unite),
            "unite"              : s.unite,
        }
        if s.is_reproducteur or s.rendement_total > 0:
            entry["rendement_total"] = round(s.rendement_total, 3)
            entry["unite_rendement"] = s.unite_rendement or ""
            entry["nb_recoltes"]     = s.nb_recoltes_poids
        result.append(entry)
    return result


# ══════════════════════════════════════════════════════════════════════════════
# [US_Stats_detail_par_variete] Détail par variété
# ══════════════════════════════════════════════════════════════════════════════

def stock_actif_variete(v: dict) -> int:
    """Stock actif au jardin pour une ligne de `calcul_stock_par_variete` : plants
    plantés moins pertes, et moins récoltes déjà prélevées si la culture n'est pas
    reproductrice (une récolte reproductrice ne retire pas le plant du jardin).
    Partagé entre l'affichage bot.py et le garde-fou de quantité de `valider_evenement`."""
    plants = (v.get("plants_plantes") or 0) - (v.get("plants_perdus") or 0)
    if v.get("type_organe") != "reproducteur":
        plants -= (v.get("recoltes_total") or 0)
    return max(0, int(plants))


def calcul_stock_par_variete(
    db: Session, culture: str, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> List[dict]:
    """
    [US_Stats_detail_par_variete / CA3, CA4, CA5, CA6, CA7] [US-036]
    Agrège les événements par variété pour une culture donnée.
    [US-030] date_ref optionnel : limite les événements pris en compte à date <= date_ref.

    Filtre insensible à la casse via func.lower().
    Retourne [] si aucune plantation trouvée pour cette culture.

    [US-036] Les récoltes sont séparées en 2 pools indépendants par variété :
    pièces (nb_recoltes/recoltes_total/unite_recolte, sert au stock) et poids
    (nb_recoltes_poids/rendement_total/unite_rendement, sert au rendement).

    Champs de chaque dict :
      variete, plants_plantes, plants_perdus, nb_recoltes, recoltes_total,
      unite_recolte, nb_recoltes_poids, rendement_total, unite_rendement,
      unite_plant, type_organe, date_premiere_plantation, date_derniere_recolte
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
    if potager_id is not None:
        _q_plant = _q_plant.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)
    plantations_raw = _q_plant.all()

    # [US-037 / CA4, CA5, CA9] Semis pleine terre (parcelle_id non null, hors "Non
    # localisé") par variété — alimente le stock au même titre qu'une plantation,
    # sans conversion d'unité.
    _q_semis_pt = (
        db.query(
            Evenement.variete,
            Evenement.unite,
            Evenement.quantite,
            Evenement.date,
        )
        .join(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "semis")
        .filter(_cond_semis_pleine_terre(Evenement, Parcelle))
    )
    if potager_id is not None:
        _q_semis_pt = _q_semis_pt.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_semis_pt = _q_semis_pt.filter(Evenement.date <= cutoff)
    semis_pt_raw = _q_semis_pt.all()

    # [CA6] Culture inconnue → liste vide
    if not plantations_raw and not semis_pt_raw:
        return []

    # ── 2. Pertes par variété ────────────────────────────────────────────────
    _q_pertes = (
        db.query(Evenement.variete, func.sum(Evenement.quantite))
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.type_action == "perte")
        .group_by(Evenement.variete)
    )
    if potager_id is not None:
        _q_pertes = _q_pertes.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_recoltes = _q_recoltes.filter(Evenement.date <= cutoff)
    recoltes_raw = _q_recoltes.all()

    # ── 4. type_organe depuis culture_config ────────────────────────────────
    _q_cfg = db.query(CultureConfig).filter(func.lower(CultureConfig.nom) == culture_lower)
    if potager_id is not None:
        _q_cfg = _q_cfg.filter(or_(CultureConfig.potager_id == potager_id, CultureConfig.potager_id.is_(None)))
    cfg = _q_cfg.first()
    type_organe: Optional[str] = cfg.type_organe_recolte if cfg else None

    # ── 5. Agrégation plantations + semis pleine terre par variété ──────────
    # [US-037 / CA2] Accumulation PAR unité — jamais un total unique mélangeant
    # graines/pieds/m² pour une même variété (voir _resoudre_unite_dominante).
    plantes_par_unite: Dict[Optional[str], Dict[str, float]] = {}
    date_min_par_variete: Dict[Optional[str], datetime] = {}

    def _accumuler_variete(variete, unite: str, total: float, date_ev) -> None:
        sous_dict = plantes_par_unite.setdefault(variete, {})
        sous_dict[unite] = sous_dict.get(unite, 0.0) + total
        if date_ev and (
            variete not in date_min_par_variete
            or date_ev < date_min_par_variete[variete]
        ):
            date_min_par_variete[variete] = date_ev

    for variete, unite, qte, rang, date_ev in plantations_raw:
        total = (qte or 0) * (rang or 1)
        _accumuler_variete(variete, unite or "plants", total, date_ev)

    # [US-037 / CA4, CA5] Semis pleine terre fusionnés dans le même pool — pas de
    # rang appliqué (un semis à la volée n'a pas de notion de rang), pas de
    # conversion d'unité.
    for variete, unite, qte, date_ev in semis_pt_raw:
        _accumuler_variete(variete, unite or "graines", qte or 0.0, date_ev)

    plantes_resolues = _resoudre_unite_dominante(plantes_par_unite, contexte=f"{culture} par variété")
    plantes: Dict[Optional[str], dict] = {
        variete: {"total": total, "unite": unite, "date_min": date_min_par_variete.get(variete)}
        for variete, (total, unite) in plantes_resolues.items()
    }

    # ── 6. Agrégation récoltes par variété — 2 pools séparés [US-036] ───────
    # pool "pièces" (nombre de plants, sert au stock) vs pool "poids" (kg/g,
    # sert au rendement) — jamais mélangés, même pour une même variété.
    _UNITE_TO_G_V = {"kg": 1000.0, "g": 1.0, "mg": 0.001}

    def _empty_pool_entry(unite: str = "") -> dict:
        return {"nb": 0, "total": 0.0, "unite": unite, "date_max": None}

    def _accumulate(pool: Dict[Optional[str], dict], variete, val, unite, date_ev):
        if variete in pool:
            pool[variete]["nb"]    += 1
            pool[variete]["total"] += val
            if date_ev and (pool[variete]["date_max"] is None or date_ev > pool[variete]["date_max"]):
                pool[variete]["date_max"] = date_ev
        else:
            pool[variete] = {"nb": 1, "total": val, "unite": unite, "date_max": date_ev}

    pieces_brut: Dict[Optional[str], dict] = {}
    poids_g_brut: Dict[Optional[str], dict] = {}
    for variete, unite, qte, date_ev in recoltes_raw:
        unite_l = (unite or "").lower()
        if unite_l in _UNITE_TO_G_V:
            _accumulate(poids_g_brut, variete, (qte or 0) * _UNITE_TO_G_V[unite_l], unite_l, date_ev)
        else:
            _accumulate(pieces_brut, variete, qte or 0, "plants", date_ev)

    def _best_g(total_g: float) -> tuple:
        if total_g >= 1000:
            return round(total_g / 1000, 2), "kg"
        return round(total_g, 1), "g"

    # [CA5] Fusion des récoltes sans variété (None), AVANT conversion d'unité,
    # avec la variété unique plantée si elle existe (sinon conservées séparément).
    varietes_plantees = list(plantes.keys())

    def _merge_none(pool: Dict[Optional[str], dict]) -> None:
        sans_variete = pool.pop(None, None)
        if not sans_variete:
            return
        if len(varietes_plantees) == 1:
            vk = varietes_plantees[0]
            if vk in pool:
                pool[vk]["nb"]    += sans_variete["nb"]
                pool[vk]["total"] += sans_variete["total"]
                if sans_variete["date_max"] and (
                    pool[vk]["date_max"] is None or sans_variete["date_max"] > pool[vk]["date_max"]
                ):
                    pool[vk]["date_max"] = sans_variete["date_max"]
            else:
                pool[vk] = sans_variete
        else:
            # Plusieurs variétés → garder "Variété non précisée" séparément
            pool[None] = sans_variete

    _merge_none(pieces_brut)
    _merge_none(poids_g_brut)

    recoltes: Dict[Optional[str], dict] = {
        v: {"nb": d["nb"], "total": round(d["total"], 1), "unite": "plants", "date_max": d["date_max"]}
        for v, d in pieces_brut.items()
    }
    rendements: Dict[Optional[str], dict] = {}
    for v, d in poids_g_brut.items():
        val, unite_out = _best_g(d["total"])
        rendements[v] = {"nb": d["nb"], "total": val, "unite": unite_out, "date_max": d["date_max"]}

    # ── 7. Construction de la liste de résultats ─────────────────────────────
    result: List[dict] = []
    all_keys = sorted(
        set(list(plantes.keys()) + [v for v in (None,) if v in recoltes or v in rendements]),
        key=lambda v: ("" if v is None else v)
    )
    for vkey in all_keys:
        p  = plantes.get(vkey, {"total": 0, "unite": "plants", "date_min": None})
        r  = recoltes.get(vkey, _empty_pool_entry())
        rp = rendements.get(vkey, _empty_pool_entry())
        dates_recolte = [d for d in (r["date_max"], rp["date_max"]) if d]
        result.append({
            "variete":                  vkey if vkey is not None else "Variété non précisée",
            "plants_plantes":           p["total"],
            "plants_perdus":            pertes.get(vkey, 0.0),
            "nb_recoltes":              r["nb"],
            "recoltes_total":           r["total"],
            "unite_recolte":            r["unite"],
            "nb_recoltes_poids":        rp["nb"],
            "rendement_total":          rp["total"],
            "unite_rendement":          rp["unite"],
            "unite_plant":              p["unite"],
            "type_organe":              type_organe,
            "date_premiere_plantation": p["date_min"],
            "date_derniere_recolte":    max(dates_recolte) if dates_recolte else None,
        })

    return result


# ══════════════════════════════════════════════════════════════════════════════
# [US-072] Détail par variété, toutes cultures confondues, avec parcelles
# ══════════════════════════════════════════════════════════════════════════════

def _parcelles_par_variete(
    db: Session, culture: str, date_ref: Optional[_date] = None, potager_id: Optional[int] = None,
) -> Dict[str, List[str]]:
    """
    [US-072 / CA4] Parcelles où chaque variété d'une culture est effectivement présente,
    déduites des événements réels de plantation et de semis pleine terre — jamais un lieu
    unique ni une parcelle par défaut. "Non localisé" quand l'événement n'a pas de
    parcelle_id ou pointe vers une parcelle soft-deletée (actif=False), même convention
    que utils/parcelles.py::calcul_occupation_parcelles et calcul_semis ci-dessus.

    Retourne { variete_ou_"Variété non précisée": [nom_parcelle, ...] }, sans doublon,
    ordre d'apparition.
    """
    from sqlalchemy import case as sa_case

    cutoff = _cutoff_dt(date_ref)
    culture_lower = culture.lower()
    _parcelle_nom = sa_case((Parcelle.actif.is_(True), Parcelle.nom), else_=None)

    _q_plant = (
        db.query(Evenement.variete, _parcelle_nom)
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "plantation")
        .filter(func.lower(Evenement.culture) == culture_lower)
    )
    if potager_id is not None:
        _q_plant = _q_plant.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)

    _cond_semis = (Evenement.parcelle_id.is_(None)) | _cond_semis_pleine_terre(Evenement, Parcelle)
    _q_semis = (
        db.query(Evenement.variete, _parcelle_nom)
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(_cond_semis)
    )
    if potager_id is not None:
        _q_semis = _q_semis.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_semis = _q_semis.filter(Evenement.date <= cutoff)

    result: Dict[str, List[str]] = {}
    for variete, parcelle_nom in _q_plant.all() + _q_semis.all():
        v_key = variete if variete is not None else "Variété non précisée"
        noms = result.setdefault(v_key, [])
        nom = parcelle_nom or "Non localisé"
        if nom not in noms:
            noms.append(nom)
    return result


def calcul_stock_varietes(
    db: Session, date_ref: Optional[_date] = None, potager_id: Optional[int] = None,
) -> List[dict]:
    """
    [US-072] Détail par variété, toutes cultures confondues, avec leurs parcelles
    d'origine réelles. Généralise calcul_stock_par_variete (une seule culture à la
    fois) à l'ensemble d'un potager en un seul appel, pour alimenter GET /stats/varietes
    (US-073 — écran Stocks transverse).

    [CA2] Trois états, mêmes règles déjà en vigueur pour distinguer stock_par_culture /
    semis_pleine_terre / en_attente dans GET /stats et GET /godets aujourd'hui, mais
    portées à la granularité variété (CA7) :
      - "potager" : la variété a au moins un événement de "plantation" propre.
      - "semis"   : la variété n'a AUCUNE plantation, mais contribue au stock de sa
        culture via un semis pleine terre localisé (parcelle réelle, non pépinière) —
        c'est exactement ce sous-ensemble de calcul_stock_par_variete qui, aujourd'hui,
        n'a pas de section dédiée alors que la culture entière apparaît dans
        stock_par_culture (1b de calcul_stock_cultures fusionne déjà plantation et
        semis pleine terre localisé dans le même total).
        Un semis SANS parcelle n'entre jamais ici : calcul_godets le traite déjà comme
        un stade "en germination" (état "pep") — un semis rattaché à une parcelle ou
        sans parcelle du tout n'est jamais un doublon entre "semis" et "pep" (CA7).
      - "pep"     : variétés encore en godet ou en germination, non plantées —
        calcul_godets (mêmes lignes que GET /godets → en_attente), parcelles
        toujours vides [CA4] : le lieu "pépinière" est déjà porté par l'état.

    Aucune règle métier nouvelle [CA9] : recombine des fonctions de calcul existantes.
    """
    stocks_cultures = calcul_stock_cultures(db, date_ref, potager_id=potager_id)
    cultures_potager = sorted(stocks_cultures.keys())

    semis_data = calcul_semis(db, date_ref, potager_id=potager_id)
    cultures_semis_pt_lower = {
        c.lower() for c, s in semis_data.items() if s.get("parcelles_pleine_terre")
    }

    _q_godet_cultures = (
        db.query(Evenement.culture)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
        .distinct()
    )
    if potager_id is not None:
        _q_godet_cultures = _q_godet_cultures.filter(Evenement.potager_id == potager_id)
    cultures_avec_godet = {row[0].lower() for row in _q_godet_cultures.all()}

    cutoff = _cutoff_dt(date_ref)
    result: List[dict] = []

    # ── États "potager" / "semis" ────────────────────────────────────────────
    for culture in cultures_potager:
        nom_l = culture.lower()
        if nom_l in cultures_avec_godet:
            origine_culture = "pépinière"
        elif nom_l in cultures_semis_pt_lower:
            origine_culture = "semis_pleine_terre"
        else:
            origine_culture = "pied_acheté"

        _q_plant_var = (
            db.query(Evenement.variete)
            .filter(Evenement.type_action == "plantation")
            .filter(func.lower(Evenement.culture) == nom_l)
            .distinct()
        )
        if potager_id is not None:
            _q_plant_var = _q_plant_var.filter(Evenement.potager_id == potager_id)
        if cutoff is not None:
            _q_plant_var = _q_plant_var.filter(Evenement.date <= cutoff)
        varietes_avec_plantation = {
            (row[0] if row[0] is not None else "Variété non précisée") for row in _q_plant_var.all()
        }

        parcelles_var = _parcelles_par_variete(db, culture, date_ref, potager_id)
        for v in calcul_stock_par_variete(db, culture, date_ref, potager_id=potager_id):
            if v["type_organe"] == "reproducteur":
                stock_actuel = max(0.0, v["plants_plantes"] - v["plants_perdus"])
            else:
                stock_actuel = max(0.0, v["plants_plantes"] - v["plants_perdus"] - v["recoltes_total"])
            unite_v = v["unite_plant"] or "plants"
            etat = "potager" if v["variete"] in varietes_avec_plantation else "semis"

            parcelles = parcelles_var.get(v["variete"], [])
            if origine_culture == "pied_acheté" and (not parcelles or all(p == "Non localisé" for p in parcelles)):
                origine = "non_localisé"
            else:
                origine = origine_culture

            result.append({
                "culture":           culture,
                "variete":           v["variete"],
                "etat":              etat,
                "origine":           origine,
                "parcelles":         parcelles,
                "total_entre":       _fmt_qte_unite(v["plants_plantes"], unite_v),
                "unite":             unite_v,
                "stock_actuel":      _fmt_qte_unite(stock_actuel, unite_v),
                "plants_perdus":     _fmt_qte_unite(v["plants_perdus"], unite_v),
                "vendu":             None,
                "rendement_total":   round(v["rendement_total"], 3) if v["rendement_total"] else 0.0,
                "unite_rendement":   v["unite_rendement"],
                "nb_recoltes_poids": v["nb_recoltes_poids"],
            })

    # ── État "pep" ───────────────────────────────────────────────────────────
    godets_tous = calcul_godets(db, include_epuises=True, date_ref=date_ref, potager_id=potager_id)
    en_attente = [
        v for v in godets_tous.values()
        if v["stock_residuel_godet"] > 0 or v.get("graines_en_germination", 0) > 0
    ]
    for g in sorted(en_attente, key=lambda v: (v["culture"], v["variete"] or "")):
        en_godet = g["nb_plants_godets"] > 0
        total_entre = g["nb_plants_godets"] if en_godet else g.get("graines_en_germination", 0)
        stock_actuel = g["stock_residuel_godet"] if en_godet else g.get("graines_en_germination", 0)
        unite_v = "plants" if en_godet else g.get("unite_germination", "graines")
        result.append({
            "culture":           g["culture"],
            "variete":           g["variete"] if g["variete"] is not None else "Variété non précisée",
            "etat":              "pep",
            "origine":           "pépinière",
            "parcelles":         [],
            "total_entre":       total_entre,
            "unite":             unite_v,
            "stock_actuel":      stock_actuel,
            "plants_perdus":     g.get("nb_pertes_godet", 0),
            "vendu":             g.get("nb_vendus", 0),
            "rendement_total":   0.0,
            "unite_rendement":   "",
            "nb_recoltes_poids": 0,
        })

    return result


def calcul_godets(
    db: Session, include_epuises: bool = False, date_ref: Optional[_date] = None,
    potager_id: Optional[int] = None,
) -> Dict[str, dict]:
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
    if potager_id is not None:
        _q_rows = _q_rows.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_rows = _q_rows.filter(Evenement.date <= cutoff)
    rows = _q_rows.all()
    # [fix visibilité semis pépinière] Pas de retour anticipé même si aucun
    # mise_en_godet n'existe : des semis "en germination" peuvent quand même
    # être présents plus bas (voir bloc semis_par_cv en fin de fonction).

    # [US-029] Taux de germination : calculer depuis les semis parents (origine_graines_id)
    # nb_graines_semees sur une mise_en_godet est un champ contextuel par lot, pas le total réel
    _q_links = (
        db.query(Evenement.culture, Evenement.variete, Evenement.origine_graines_id)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
    )
    if potager_id is not None:
        _q_links = _q_links.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_links = _q_links.filter(Evenement.date <= cutoff)
    _godet_links = _q_links.all()
    _semis_ids_all = {r.origine_graines_id for r in _godet_links if r.origine_graines_id}
    _semis_qtites_all: Dict[int, int] = {}
    if _semis_ids_all:
        _q_semis_qte = db.query(Evenement.id, Evenement.quantite).filter(Evenement.id.in_(_semis_ids_all))
        if potager_id is not None:
            _q_semis_qte = _q_semis_qte.filter(Evenement.potager_id == potager_id)
        for sid, sqte in _q_semis_qte.all():
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
    if potager_id is not None:
        _q_plant = _q_plant.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_sorties = _q_sorties.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_vendus = _q_vendus.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_pertes_g = _q_pertes_g.filter(Evenement.potager_id == potager_id)
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

    # [fix visibilité semis pépinière] Un semis rattaché à une parcelle pépinière
    # (serre, "Non localisé"...) ou sans parcelle du tout est un stade "en
    # germination" — pas encore repiqué en godet (mise_en_godet). Sans ce bloc,
    # ces graines ne remontent dans AUCUNE vue : ni "pleine terre" (exclues par
    # _cond_semis_pleine_terre), ni "pépinière" (calculée uniquement depuis
    # mise_en_godet). On les fusionne donc ici dans le même dict que les godets,
    # avec un statut dédié quand aucune mise_en_godet n'existe encore pour ce
    # couple (culture, variete).
    from sqlalchemy import or_ as _sa_or
    _q_semis_pep = (
        db.query(Evenement.culture, Evenement.variete, Evenement.quantite, Evenement.unite)
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.culture.isnot(None))
        .filter(_sa_or(Evenement.parcelle_id.is_(None), Parcelle.est_pepiniere.is_(True)))
    )
    if potager_id is not None:
        _q_semis_pep = _q_semis_pep.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_semis_pep = _q_semis_pep.filter(Evenement.date <= cutoff)
    semis_par_cv: Dict[tuple, Dict[str, float]] = {}
    for culture, variete, qte, unite in _q_semis_pep.all():
        u = unite or "graines"
        sous_total = semis_par_cv.setdefault((culture, variete), {})
        sous_total[u] = sous_total.get(u, 0.0) + (qte or 0.0)

    for (culture, variete), par_unite in semis_par_cv.items():
        unite_dom = max(par_unite, key=par_unite.get)
        total_seme = par_unite[unite_dom]
        consommees = graines_par_cv.get((culture, variete), 0)
        reste = max(0, total_seme - consommees)
        if reste <= 0:
            continue

        key = culture + (f" ({variete})" if variete else "")
        if key in result:
            result[key]["graines_en_germination"] = int(reste)
            result[key]["unite_germination"]      = unite_dom
        else:
            result[key] = {
                "culture":               culture,
                "variete":               variete,
                "nb_godets":             0,
                "nb_graines_semees":     0,
                "nb_plants_godets":      0,
                "nb_plantes":            0,
                "nb_vendus":             0,
                "nb_pertes_godet":       0,
                "stock_residuel_godet":  0,
                "taux_reussite":         None,
                "graines_en_germination": int(reste),
                "unite_germination":      unite_dom,
                "statut":                 "en_germination",
            }

    return dict(sorted(result.items()))


def calcul_godets_par_culture(
    db: Session, culture: str, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> List[dict]:
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
    if potager_id is not None:
        _q_rows = _q_rows.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_links_var = _q_links_var.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_links_var = _q_links_var.filter(Evenement.date <= cutoff)
    _godet_links_var = _q_links_var.all()
    _semis_ids_var = {r.origine_graines_id for r in _godet_links_var if r.origine_graines_id}
    _semis_qtites_var: Dict[int, int] = {}
    if _semis_ids_var:
        _q_semis_qte_var = db.query(Evenement.id, Evenement.quantite).filter(Evenement.id.in_(_semis_ids_var))
        if potager_id is not None:
            _q_semis_qte_var = _q_semis_qte_var.filter(Evenement.potager_id == potager_id)
        for sid, sqte in _q_semis_qte_var.all():
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
    if potager_id is not None:
        _q_plant_var = _q_plant_var.filter(Evenement.potager_id == potager_id)
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
    if potager_id is not None:
        _q_sorties_var = _q_sorties_var.filter(Evenement.potager_id == potager_id)
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
    potager_id: Optional[int] = None,
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
    _q_godet_events = (
        db.query(Evenement.id, Evenement.variete, Evenement.nb_plants_godets, Evenement.date)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.culture.isnot(None))
        .filter(Evenement.nb_plants_godets.isnot(None))
    )
    if potager_id is not None:
        _q_godet_events = _q_godet_events.filter(Evenement.potager_id == potager_id)
    godet_events = _q_godet_events.order_by(Evenement.date.asc().nullsfirst(), Evenement.id.asc()).all()

    if not godet_events:
        return (variete, None)

    # Calculer les consommations déjà enregistrées via source_evenement_ids
    _q_plant_linked = (
        db.query(Evenement.source_evenement_ids, Evenement.quantite)
        .filter(Evenement.type_action == "plantation")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.source_evenement_ids.isnot(None))
    )
    if potager_id is not None:
        _q_plant_linked = _q_plant_linked.filter(Evenement.potager_id == potager_id)
    plant_linked = _q_plant_linked.all()
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


# ══════════════════════════════════════════════════════════════════════════════
# [US-065] Lecture de la pépinière PAR LOT DE SEMIS
#
# Cette lecture s'AJOUTE à calcul_godets() (agrégée par culture + variété), elle
# ne la remplace pas : calcul_godets(), GET /godets, /stats et les statistiques du
# bot conservent exactement leur contrat actuel (CA5).
#
# Deux différences de fond avec la lecture agrégée :
#   1. La maille est l'ÉVÉNEMENT DE SEMIS (un semis = un lot = une carte), et non
#      le couple culture + variété — deux semis échelonnés d'une même variété n'en
#      sont pas au même point (CA1).
#   2. Les graines sont soldées LOT DE GODET PAR LOT DE GODET (nb_graines_semees de
#      chaque mise en godet), au lieu de solder d'un coup la quantité du semis
#      parent dès le premier repiquage comme le fait calcul_godets() (CA2).
# ══════════════════════════════════════════════════════════════════════════════

#: [US-065 / CA3] États de germination — trois valeurs, jamais deux.
ETAT_GERMINATION_EN_COURS     = "en_cours"      # il reste des graines non soldées
ETAT_GERMINATION_CLOSE        = "close"         # toutes les graines semées sont soldées
ETAT_GERMINATION_INDETERMINEE = "indeterminee"  # information manquante, PAS un stade


def _cle_cv(culture: Optional[str], variete: Optional[str]) -> tuple:
    """Clé de regroupement (culture, variété) insensible à la casse."""
    return ((culture or "").lower(), ((variete or "").lower() or None))


def calcul_lots_pepiniere(
    db: Session, date_ref: Optional[_date] = None, potager_id: Optional[int] = None
) -> List[dict]:
    """
    [US-065 / CA1, CA2, CA3, CA4, CA7] État de la pépinière lot de semis par lot de semis.

    Un lot = un événement de semis en pépinière (parcelle absente ou marquée
    `est_pepiniere`), identifié par sa date. Aucun regroupement de lots semés à des
    dates proches : la règle est délibérément la plus simple (CA1). Les mises en
    godet sans semis rattaché (`origine_graines_id` absent ou pointant hors
    pépinière) sont regroupées par couple (culture, variété) dans un lot distinct
    marqué `sans_semis_rattache`.

    [CA2] Les graines soldées d'un lot sont la somme, mise en godet par mise en
    godet, de `nb_graines_semees` (à défaut `nb_plants_godets`) — un repiquage
    échelonné ne solde donc plus le semis parent d'un coup.

    [CA3] `etat_germination` vaut :
      - "indeterminee" : au moins une mise en godet n'a pas déclaré son nombre de
        graines d'origine (ou le lot n'a aucune graine semée connue) — information
        manquante, jamais présentée comme un « en cours » ;
      - "close"        : toutes les graines semées sont soldées ;
      - "en_cours"     : déclarations complètes et graines restant à lever.

    [CA4] `incoherence_saisie` signale un cumul de plants supérieur au nombre de
    graines semées — impossible dans la réalité, non couvert par le garde-fou de
    `app/services/evenements.py` qui ne contrôle qu'un lot de godet à la fois. Les
    valeurs brutes (`plants_obtenus`, `graines_semees`, `taux_germination`) sont
    exposées telles quelles, sans bornage qui masquerait le cas : seul
    `graines_en_germination` est ramené à 0, et jamais silencieusement puisque le
    drapeau l'accompagne.

    [CA7] `date_ref` borne tous les calculs, comme la lecture agrégée.

    Retourne une liste de dicts triés par (culture, variété, date de semis) :
      lot_id, semis_id, culture, variete, date_semis, parcelle, graines_semees,
      unite, graines_soldees, graines_en_germination, plants_obtenus,
      nb_mises_en_godet, date_derniere_mise_en_godet, nb_plantes, nb_vendus,
      nb_pertes_godet, stock_residuel_godet, etat_germination, taux_germination,
      incoherence_saisie, sans_semis_rattache
    """
    from sqlalchemy import or_ as _sa_or

    cutoff = _cutoff_dt(date_ref)

    # ── 1. Les lots : un semis en pépinière = un lot (CA1) ──────────────────
    _q_semis = (
        db.query(Evenement)
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(Evenement.culture.isnot(None))
        .filter(_sa_or(Evenement.parcelle_id.is_(None), Parcelle.est_pepiniere.is_(True)))
    )
    if potager_id is not None:
        _q_semis = _q_semis.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_semis = _q_semis.filter(Evenement.date <= cutoff)
    semis_events = _q_semis.order_by(Evenement.date.asc(), Evenement.id.asc()).all()

    def _nouveau_lot(**champs) -> dict:
        base = {
            "lot_id":                     "",
            "semis_id":                   None,
            "culture":                    None,
            "variete":                    None,
            "date_semis":                 None,
            "parcelle":                   None,
            "graines_semees":             0,
            "unite":                      "graines",
            "graines_soldees":            0,
            "plants_obtenus":             0,
            "nb_mises_en_godet":          0,
            "date_derniere_mise_en_godet": None,
            "nb_plantes":                 0,
            "nb_vendus":                  0,
            "nb_pertes_godet":            0,
            "sans_semis_rattache":        False,
            "_declaration_incomplete":    False,
            "_sorties":                   0,
        }
        base.update(champs)
        return base

    lots: Dict[tuple, dict] = {}
    for s in semis_events:
        lots[("semis", s.id)] = _nouveau_lot(
            lot_id         = f"semis-{s.id}",
            semis_id       = s.id,
            culture        = s.culture,
            variete        = s.variete,
            date_semis     = s.date,
            parcelle       = s.parcelle_rel.nom if s.parcelle_rel else None,
            graines_semees = int(s.quantite or 0),
            unite          = s.unite or "graines",
        )

    # ── 2. Mises en godet rattachées à leur lot, graines soldées lot par lot (CA2) ──
    _q_godets = (
        db.query(
            Evenement.id,
            Evenement.culture,
            Evenement.variete,
            Evenement.nb_graines_semees,
            Evenement.nb_plants_godets,
            Evenement.origine_graines_id,
            Evenement.date,
        )
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
    )
    if potager_id is not None:
        _q_godets = _q_godets.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_godets = _q_godets.filter(Evenement.date <= cutoff)
    godets = _q_godets.order_by(Evenement.date.asc(), Evenement.id.asc()).all()

    godet_lot: Dict[int, tuple] = {}
    for g in godets:
        cle_semis = ("semis", g.origine_graines_id) if g.origine_graines_id else None
        if cle_semis is not None and cle_semis in lots:
            cle = cle_semis
        else:
            # [CA1] Aucun semis rattaché (ou semis hors pépinière / hors date de
            # référence) → lot distinct, explicitement identifié comme tel.
            cle = ("sans_semis", _cle_cv(g.culture, g.variete))
            if cle not in lots:
                suffixe = f"{(g.culture or '').lower()}-{(g.variete or '').lower()}".rstrip("-")
                lots[cle] = _nouveau_lot(
                    lot_id              = f"sans-semis-{suffixe}",
                    culture             = g.culture,
                    variete             = g.variete,
                    sans_semis_rattache = True,
                )

        lot     = lots[cle]
        plants  = int(g.nb_plants_godets or 0)
        declare = g.nb_graines_semees is not None and int(g.nb_graines_semees) > 0
        # [CA2] Repli assumé sur le nombre de plants quand le « sur N graines »
        # manque — repli qui rend justement l'état indéterminé (CA3).
        soldees = int(g.nb_graines_semees) if declare else plants

        lot["graines_soldees"]   += soldees
        lot["plants_obtenus"]    += plants
        lot["nb_mises_en_godet"] += 1
        if not declare:
            lot["_declaration_incomplete"] = True
        if lot["sans_semis_rattache"]:
            # Pas de semis parent : les graines « semées » connues du lot se
            # limitent à ce que les mises en godet ont déclaré.
            lot["graines_semees"] += soldees
        if g.date and (
            lot["date_derniere_mise_en_godet"] is None
            or g.date > lot["date_derniere_mise_en_godet"]
        ):
            lot["date_derniere_mise_en_godet"] = g.date
        godet_lot[g.id] = cle

    if not lots:
        return []

    # ── 3. Sorties de pépinière (plantations, ventes, pertes godet) ─────────
    # Ordre FIFO des lots d'un même couple (culture, variété) : le lot le plus
    # ancien est consommé en premier, comme _find_plantation_sources (US-029 CA8).
    def _cle_tri(cle: tuple) -> tuple:
        lot = lots[cle]
        ref = lot["date_semis"] or lot["date_derniere_mise_en_godet"] or datetime.max
        return (ref, lot["lot_id"])

    lots_par_cv: Dict[tuple, List[tuple]] = {}
    lots_par_culture: Dict[str, List[tuple]] = {}
    for cle, lot in lots.items():
        lots_par_cv.setdefault(_cle_cv(lot["culture"], lot["variete"]), []).append(cle)
        lots_par_culture.setdefault((lot["culture"] or "").lower(), []).append(cle)
    for liste in list(lots_par_cv.values()) + list(lots_par_culture.values()):
        liste.sort(key=_cle_tri)

    def _candidats(culture: Optional[str], variete: Optional[str]) -> List[tuple]:
        """Lots pouvant absorber une sortie. Repli sur la culture entière quand la
        variété ne correspond à aucun lot (sortie sans variété, ou lot sans variété)
        — même esprit que le rattachement CA6/CA6-reverse de calcul_godets()."""
        exacts = lots_par_cv.get(_cle_cv(culture, variete))
        if exacts:
            return exacts
        return lots_par_culture.get((culture or "").lower(), [])

    def _allouer(cle: tuple, quantite: int, champ: str) -> int:
        """Impute au plus `quantite` sorties au lot, dans la limite de ses plants
        encore disponibles. Retourne le reliquat non imputé."""
        lot   = lots[cle]
        dispo = lot["plants_obtenus"] - lot["_sorties"]
        pris  = max(0, min(quantite, dispo))
        if pris:
            lot[champ]      += pris
            lot["_sorties"] += pris
        return quantite - pris

    def _allouer_fifo(culture, variete, quantite: int, champ: str) -> int:
        restant = quantite
        for cle in _candidats(culture, variete):
            if restant <= 0:
                break
            restant = _allouer(cle, restant, champ)
        return restant

    # 3a. Plantations — rattachement explicite via source_evenement_ids (US-029),
    #     repli FIFO pour les plantations antérieures à ce chaînage.
    _q_plant = (
        db.query(
            Evenement.culture,
            Evenement.variete,
            Evenement.quantite,
            Evenement.source_evenement_ids,
            Evenement.date,
        )
        .filter(Evenement.type_action == "plantation")
        .filter(Evenement.culture.isnot(None))
    )
    if potager_id is not None:
        _q_plant = _q_plant.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_plant = _q_plant.filter(Evenement.date <= cutoff)
    plantations = _q_plant.order_by(Evenement.date.asc(), Evenement.id.asc()).all()

    for culture_p, variete_p, qte_p, src_ids, _date_p in plantations:
        restant   = int(qte_p or 0)
        cles_vues: List[tuple] = []
        for part in (src_ids or "").split(";"):
            part = part.strip()
            if not part.isdigit():
                continue
            cle = godet_lot.get(int(part))
            if cle is None or cle in cles_vues:
                continue
            cles_vues.append(cle)
            restant = _allouer(cle, restant, "nb_plantes")
            if restant <= 0:
                break
        if restant > 0:
            _allouer_fifo(culture_p, variete_p, restant, "nb_plantes")

    # 3b. Ventes et pertes en godet — jamais chaînées à un lot précis, imputées FIFO.
    _q_sorties = (
        db.query(
            Evenement.culture,
            Evenement.variete,
            Evenement.type_action,
            Evenement.quantite,
            Evenement.date,
        )
        .filter(Evenement.type_action.in_(["vendu", "perte_godet"]))
        .filter(Evenement.culture.isnot(None))
    )
    if potager_id is not None:
        _q_sorties = _q_sorties.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        _q_sorties = _q_sorties.filter(Evenement.date <= cutoff)
    for culture_s, variete_s, action_s, qte_s, _date_s in _q_sorties.order_by(
        Evenement.date.asc(), Evenement.id.asc()
    ).all():
        champ = "nb_vendus" if action_s == "vendu" else "nb_pertes_godet"
        _allouer_fifo(culture_s, variete_s, int(qte_s or 0), champ)

    # ── 4. État de germination, incohérences, stock résiduel ────────────────
    resultat: List[dict] = []
    for cle in sorted(
        lots,
        key=lambda c: (
            (lots[c]["culture"] or "").lower(),
            (lots[c]["variete"] or ""),
            lots[c]["date_semis"] or lots[c]["date_derniere_mise_en_godet"] or datetime.max,
        ),
    ):
        lot     = lots[cle]
        graines = lot["graines_semees"]
        soldees = lot["graines_soldees"]
        plants  = lot["plants_obtenus"]

        # [US-065 CA3] L'ordre des tests compte. Une déclaration incomplète ne rend
        # le lot indéterminé que tant qu'elle laisse planer un doute sur sa clôture.
        #
        # `graines_soldees` est un MINORANT du nombre réel de graines consommées :
        # quand le « sur N graines » manque, on retient le nombre de plants du lot,
        # or n plants viennent forcément d'au moins n graines. Si ce minorant
        # atteint déjà le nombre semé, plus aucune graine ne peut rester à lever —
        # la clôture est certaine, et la déclaration manquante ne change rien à
        # cette conclusion. La tester après coup marquait « indéterminés » des lots
        # dont le taux de germination était en réalité définitif.
        if graines <= 0:
            etat = ETAT_GERMINATION_INDETERMINEE
        elif soldees >= graines:
            etat = ETAT_GERMINATION_CLOSE
        elif lot["_declaration_incomplete"]:
            etat = ETAT_GERMINATION_INDETERMINEE
        else:
            etat = ETAT_GERMINATION_EN_COURS

        incoherence = graines > 0 and plants > graines
        if incoherence:
            _log_stock.warning(
                "[US-065 CA4] Incohérence de saisie sur le lot %s (%s%s) : %d plants obtenus "
                "pour %d graines semées — valeurs exposées telles quelles, sans bornage",
                lot["lot_id"], lot["culture"], f"/{lot['variete']}" if lot["variete"] else "",
                plants, graines,
            )

        lot["graines_en_germination"] = max(0, graines - soldees)
        lot["etat_germination"]       = etat
        lot["incoherence_saisie"]     = incoherence
        # Barre « Germination » de la maquette : un lot semé mais pas encore levé
        # vaut bien 0 %, pas « inconnu » — seul un lot sans graines connues est None.
        lot["taux_germination"]       = round(plants / graines * 100) if graines else None
        lot["stock_residuel_godet"]   = max(
            0, plants - lot["nb_plantes"] - lot["nb_vendus"] - lot["nb_pertes_godet"]
        )
        lot.pop("_declaration_incomplete", None)
        lot.pop("_sorties", None)
        resultat.append(lot)

    return resultat


def lots_candidats_mise_en_godet(
    db: Session,
    culture: str,
    variete: Optional[str] = None,
    date_ref: Optional[_date] = None,
    potager_id: Optional[int] = None,
    graines_requises: int = 0,
) -> List[dict]:
    """
    [fix rattachement lot godet] Lots de semis en pépinière pouvant encore recevoir
    une mise en godet, du plus ancien au plus récent (FIFO).

    Complète la lecture par lot d'US-065 : celle-ci sait afficher les lots
    séparément, mais rien ne permettait de les ALIMENTER séparément. La déduction
    historique de `creer_evenement_godet` ne rattachait un godet à son semis parent
    que s'il existait exactement UN semis pour la culture — deux semis échelonnés
    d'une même variété laissaient donc `origine_graines_id` à NULL, et aucun des
    deux lots n'avançait.

    Un lot est candidat s'il reste des graines non soldées (`graines_en_germination`),
    ce qui couvre aussi bien l'état « en cours » que l'état « indéterminée » d'un lot
    partiellement repiqué. Les lots sans semis rattaché sont exclus : ils n'ont pas
    de semis parent auquel se lier.

    `graines_requises` restreint aux lots capables d'absorber le repiquage en cours
    — ne rien proposer qui serait refusé à l'écriture par
    `LotGrainesEpuiseesError`. Une mise en godet vient d'UNE barquette, donc d'un
    seul lot : le besoin n'est jamais réparti sur plusieurs lots.
    """
    culture_l = (culture or "").lower()
    variete_l = (variete or "").lower() or None
    seuil = max(1, graines_requises)

    candidats = [
        lot for lot in calcul_lots_pepiniere(db, date_ref, potager_id=potager_id)
        if not lot["sans_semis_rattache"]
        and (lot["culture"] or "").lower() == culture_l
        and lot["graines_en_germination"] >= seuil
        # Filtre STRICT : une variété absente désigne les lots SANS variété, jamais
        # « toutes variétés confondues ». Un lot « bruxelle » n'est pas un lot sans
        # variété — le proposer à un repiquage explicitement déclaré sans variété
        # (US-019, bouton « non précisée ») rattacherait les plants au mauvais lot.
        and ((lot["variete"] or "").lower() or None) == variete_l
    ]
    candidats.sort(key=lambda lot: (lot["date_semis"] or datetime.max, lot["semis_id"]))
    return candidats


def lots_pepiniere_du_couple(
    db: Session,
    culture: str,
    variete: Optional[str] = None,
    date_ref: Optional[_date] = None,
    potager_id: Optional[int] = None,
) -> List[dict]:
    """
    [fix garde-fou graines du lot] Tous les lots de semis EN PÉPINIÈRE d'un couple
    (culture, variété), graines restantes ou non.

    Sert à distinguer deux situations que `lots_candidats_mise_en_godet` confond
    quand elle renvoie une liste vide :
      - il n'existe AUCUN semis pour cette culture → une mise en godet sans parent
        est légitime (plants achetés, bouture, don) ;
      - des lots existent mais sont tous épuisés → une mise en godet supplémentaire
        n'a aucune origine possible et doit être refusée, pas enregistrée orpheline.
    Les semis de PLEINE TERRE restent exclus : ils ne produisent jamais de godet.
    """
    culture_l = (culture or "").lower()
    variete_l = (variete or "").lower() or None

    lots = [
        lot for lot in calcul_lots_pepiniere(db, date_ref, potager_id=potager_id)
        if not lot["sans_semis_rattache"]
        and (lot["culture"] or "").lower() == culture_l
        # Filtre STRICT : une variété absente désigne les lots SANS variété, jamais
        # « toutes variétés confondues ». Un lot « bruxelle » n'est pas un lot sans
        # variété — le proposer à un repiquage explicitement déclaré sans variété
        # (US-019, bouton « non précisée ») rattacherait les plants au mauvais lot.
        and ((lot["variete"] or "").lower() or None) == variete_l
    ]
    lots.sort(key=lambda lot: (lot["date_semis"] or datetime.max, lot["semis_id"]))
    return lots


def lot_pepiniere_par_semis(
    db: Session,
    semis_id: int,
    date_ref: Optional[_date] = None,
    potager_id: Optional[int] = None,
) -> Optional[dict]:
    """
    [fix garde-fou graines du lot] État d'un lot de pépinière désigné par son semis.

    Sert au contrôle de cohérence à l'écriture d'une mise en godet : il faut
    connaître les graines encore non soldées du lot AVANT d'y ajouter un nouveau
    lot de godets. Retourne None si le semis n'est pas un lot de pépinière connu.
    """
    for lot in calcul_lots_pepiniere(db, date_ref, potager_id=potager_id):
        if lot["semis_id"] == semis_id:
            return lot
    return None


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
    [US_Stats_detail_par_variete / CA4] [US-036]
    Formate un bloc variété pour /stats [culture] Telegram.

    Respecte la logique reproducteur (récolte continue) vs végétatif (récolte destructive).
    [US-036] Le rendement (poids) est désormais affiché pour les DEUX types dès qu'il existe,
    indépendamment du nombre de pièces récoltées (pool séparé, jamais mélangé au stock).
    Format date : 'dd mmm' si même année, 'dd mmm YYYY' sinon.
    'en cours' si date_derniere_recolte est None.
    """
    nom              = v["variete"]
    unite_plant      = v["unite_plant"] or "plants"
    plants_plantes   = _fmt_qte_unite(v["plants_plantes"], unite_plant)
    plants_perdus    = _fmt_qte_unite(v["plants_perdus"], unite_plant)
    recoltes_total   = v["recoltes_total"]
    nb_recoltes_poids = v.get("nb_recoltes_poids", 0)
    rendement_total  = v.get("rendement_total", 0.0)
    unite_rendement  = v.get("unite_rendement") or "unités"
    type_organe      = v["type_organe"]
    date_plantation  = v["date_premiere_plantation"]
    date_recolte     = v["date_derniere_recolte"]

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
        # [CA4] Reproducteur : plants actifs + détails si perte + rendement (pool poids) + date
        stock = max(0, plants_plantes - plants_perdus)
        base  = f"  • {stock} {unite_plant} actifs"
        # Détails entre parenthèses uniquement si le stock diffère du total planté (perte)
        if plants_perdus > 0:
            base += f" (planté {plants_plantes}, perdu {plants_perdus})"
        if rendement_total > 0:
            r_val  = round(rendement_total, 2)
            base  += f" · {r_val} {unite_rendement} récoltés ({nb_recoltes_poids} fois)"
        base += date_periode
        lines.append(base)
    else:
        # [CA4][US-036] Végétatif : récolte en pièces destructive + rendement (poids) optionnel
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
        if rendement_total > 0:
            r_val = round(rendement_total, 2)
            base += f" · {r_val} {unite_rendement} récoltés"
        lines.append(base + date_periode)

    return "\n".join(lines)
