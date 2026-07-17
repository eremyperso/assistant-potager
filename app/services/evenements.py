"""
app/services/evenements.py — CRUD et requêtes sur Evenement [US-041]
-----------------------------------------------------------------------
Centralise tous les accès directs à la table `evenements` auparavant
dispersés dans bot.py et main.py, afin que le scoping par potager_id
(US-042) puisse être ajouté à un seul endroit par fonction.

⚠️ Aucun filtre potager_id ici : le scoping applicatif est le périmètre
de US-042. `ctx: TenantContext` est déjà présent dans chaque signature
pour que l'ajout du filtre ne change aucune signature appelante.
"""
import logging
from typing import Optional

from sqlalchemy import func, or_, and_, select
from sqlalchemy.orm import Session, selectinload

from app.services.context import TenantContext
from database.models import Evenement, Parcelle
from utils.actions import normalize_action
from utils.date_utils import parse_date
from utils.parcelles import resolve_parcelle
from utils.stock import get_type_organe, _find_plantation_sources

log = logging.getLogger("potager")


def _to_float(v):
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(float(v)) if v is not None else None
    except (TypeError, ValueError):
        return None


# [US-037] Unités valides pour un semis, normalisées vers la forme canonique
# stockée en base : "graines" | "pieds" | "m²". Déplacé depuis bot.py (seul
# appelant : creer_evenement_confirme, ex-_do_save_items).
_UNITES_SEMIS_CANONIQUES: dict[str, str] = {
    "graine": "graines", "graines": "graines",
    "pied": "pieds", "pieds": "pieds", "plant": "pieds", "plants": "pieds",
    "m2": "m²", "m²": "m²", "metre carre": "m²", "mètre carré": "m²",
    "metres carres": "m²", "mètres carrés": "m²", "m^2": "m²",
}


def _normalize_unite_semis(unite_brute: Optional[str]) -> str:
    """Normalise l'unité d'un semis vers 'graines'|'pieds'|'m²' (jamais forcée si m²)."""
    cle = (unite_brute or "").lower().strip()
    return _UNITES_SEMIS_CANONIQUES.get(cle, "graines")


def _cond_localisation_culture():
    """Une culture est "localisée" via une 'plantation' OU un 'semis' directement lié
    à une VRAIE parcelle de pleine terre (semis pleine terre). Voir bot.py historique
    [US-037 / migration_v15] pour le détail du raisonnement agronomique."""
    pepiniere_ids = select(Parcelle.id).where(Parcelle.est_pepiniere.is_(True))
    return or_(
        Evenement.type_action == "plantation",
        and_(
            Evenement.type_action == "semis",
            Evenement.parcelle_id.isnot(None),
            Evenement.parcelle_id.notin_(pepiniere_ids),
        ),
    )


# ── Compteurs simples ────────────────────────────────────────────────────────
def compter_evenements(db: Session, ctx: TenantContext, jusqua=None) -> int:
    """Nombre total d'événements (cmd_start, /health, /stats avec date_ref optionnelle)."""
    q = db.query(func.count(Evenement.id))
    if jusqua is not None:
        from datetime import datetime as _dt
        q = q.filter(Evenement.date <= _dt(jusqua.year, jusqua.month, jusqua.day, 23, 59, 59))
    return q.scalar() or 0


def compter_evenements_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> int:
    """Nombre d'événements rattachés à une parcelle (avant suppression)."""
    return db.query(Evenement).filter(Evenement.parcelle_id == parcelle_id).count()


# ── Lecture ───────────────────────────────────────────────────────────────────
def get_evenement(db: Session, ctx: TenantContext, evenement_id: int) -> Optional[Evenement]:
    return db.get(Evenement, evenement_id)


def dernier_evenement(db: Session, ctx: TenantContext) -> Optional[Evenement]:
    return db.query(Evenement).order_by(Evenement.id.desc()).first()


def evenements_recents(db: Session, ctx: TenantContext, limit: int = 10) -> list[Evenement]:
    return db.query(Evenement).order_by(Evenement.date.desc()).limit(limit).all()


def lister_evenements(
    db: Session,
    ctx: TenantContext,
    *,
    limit: int = 20,
    offset: int = 0,
    action: Optional[str] = None,
    culture: Optional[str] = None,
    parcelle: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> tuple[int, list[Evenement]]:
    """[US-027] Historique paginé avec filtres — utilisé par GET /historique."""
    from sqlalchemy.orm import joinedload

    q = (
        db.query(Evenement)
        .options(joinedload(Evenement.parcelle_rel))
        .order_by(Evenement.date.desc())
    )
    if action:
        q = q.filter(Evenement.type_action == action)
    if culture:
        q = q.filter(Evenement.culture.ilike(f"%{culture}%"))
    if parcelle:
        q = q.join(Parcelle, Evenement.parcelle_id == Parcelle.id, isouter=True).filter(
            Parcelle.nom.ilike(f"%{parcelle}%")
        )
    if from_date:
        q = q.filter(Evenement.date >= from_date)
    if to_date:
        q = q.filter(Evenement.date <= to_date + " 23:59:59")

    total = q.count()
    events = q.offset(offset).limit(limit).all()
    return total, events


def find_candidates(db: Session, ctx: TenantContext, criteres: dict, limit: int = 3) -> list[Evenement]:
    """[/corriger] Retrouve les événements correspondant aux critères extraits par Groq."""
    q = db.query(Evenement).options(selectinload(Evenement.parcelle_rel))
    if criteres.get("action"):
        q = q.filter(Evenement.type_action == criteres["action"])
    if criteres.get("culture"):
        q = q.filter(Evenement.culture.ilike(f"%{criteres['culture'].strip()}%"))
    if criteres.get("variete"):
        q = q.filter(Evenement.variete.ilike(f"%{criteres['variete'].strip()}%"))
    if criteres.get("parcelle"):
        q = q.join(Parcelle, Evenement.parcelle_id == Parcelle.id, isouter=True).filter(
            Parcelle.nom.ilike(f"%{criteres['parcelle']}%")
        )
    if criteres.get("date_debut"):
        q = q.filter(Evenement.date >= criteres["date_debut"])
    if criteres.get("date_fin"):
        q = q.filter(Evenement.date <= criteres["date_fin"] + " 23:59:59")
    return q.order_by(Evenement.date.desc()).limit(limit).all()


def godets_en_attente(db: Session, ctx: TenantContext) -> list[Evenement]:
    """[/godets] Plants en godet sans plantation postérieure de la même culture."""
    godets_all = (
        db.query(Evenement)
        .filter(Evenement.type_action == "mise_en_godet")
        .order_by(Evenement.date.desc())
        .all()
    )
    en_attente = []
    for g in godets_all:
        plantation = db.query(Evenement).filter(
            Evenement.type_action == "plantation",
            Evenement.culture == g.culture,
        )
        if g.date:
            plantation = plantation.filter(Evenement.date >= g.date)
        if not plantation.first():
            en_attente.append(g)
    return en_attente


def evenements_localises_exact(db: Session, ctx: TenantContext, culture: str) -> list[Evenement]:
    """[US-007] Plantations / semis pleine terre correspondant exactement à `culture`."""
    return (
        db.query(Evenement)
        .filter(_cond_localisation_culture(), func.lower(Evenement.culture) == culture.lower())
        .all()
    )


def evenements_localises_recherche_partielle(db: Session, ctx: TenantContext, motif: str) -> list[Evenement]:
    """[US-007] Recherche partielle (typos/accents/pluriel) sur culture localisée."""
    return (
        db.query(Evenement)
        .filter(_cond_localisation_culture(), func.lower(Evenement.culture).ilike(f"%{motif}%"))
        .all()
    )


def evenements_localises_pour_maj(
    db: Session, ctx: TenantContext, culture: str, variete: Optional[str]
) -> list[Evenement]:
    """[US-007] Plantations / semis pleine terre d'une culture (+ variété optionnelle),
    utilisé pour compter puis réassocier à une nouvelle parcelle."""
    q = db.query(Evenement).filter(
        _cond_localisation_culture(), func.lower(Evenement.culture) == culture.lower()
    )
    if variete is not None:
        q = q.filter(Evenement.variete == variete)
    return q.all()


def liberer_evenements_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> int:
    """[US-009] Compte puis détache (parcelle_id=NULL) tous les événements d'une parcelle
    supprimée. Ne commit pas — l'appelant commit avec la désactivation de la parcelle."""
    nb = db.query(Evenement).filter(Evenement.parcelle_id == parcelle_id).count()
    db.query(Evenement).filter(Evenement.parcelle_id == parcelle_id).update(
        {"parcelle_id": None}, synchronize_session="fetch"
    )
    return nb


def compter_traitements(db: Session, ctx: TenantContext) -> int:
    """[cmd_stats bot.py] Nombre total d'événements de traitement."""
    return db.query(func.count(Evenement.id)).filter(Evenement.type_action == "traitement").scalar()


def traitements_appliques(db: Session, ctx: TenantContext) -> list[tuple[str, int]]:
    """[/stats] Nombre d'applications par produit de traitement."""
    return (
        db.query(Evenement.traitement, func.count(Evenement.id))
        .filter(Evenement.type_action == "traitement")
        .group_by(Evenement.traitement)
        .all()
    )


def cultures_avec_mise_en_godet(db: Session, ctx: TenantContext) -> set[str]:
    """[/stats] Cultures ayant au moins une mise en godet (origine "pépinière")."""
    return {
        row[0].lower()
        for row in db.query(Evenement.culture)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(Evenement.culture.isnot(None))
        .distinct()
        .all()
    }


# ── Écriture ──────────────────────────────────────────────────────────────────
def creer_evenement_depuis_parse(db: Session, ctx: TenantContext, parsed: dict, texte_original: str) -> Evenement:
    """[POST /parse, POST /voice-ACTION] Crée un événement depuis un item parsé par Groq,
    avec héritage automatique de type_organe_recolte depuis culture_config."""
    from database.models import CultureConfig

    nom_parcelle = parsed.get("parcelle")
    parcelle_obj = resolve_parcelle(db, nom_parcelle) if nom_parcelle else None
    event = Evenement(
        type_action=normalize_action(parsed.get("action")),
        culture=parsed.get("culture"),
        variete=parsed.get("variete"),
        quantite=_to_float(parsed.get("quantite")),
        unite=parsed.get("unite"),
        parcelle_id=parcelle_obj.id if parcelle_obj else None,
        rang=parsed.get("rang"),
        duree=_to_int(parsed.get("duree_minutes")),
        traitement=parsed.get("traitement"),
        commentaire=parsed.get("commentaire"),
        texte_original=texte_original,
        date=parse_date(parsed.get("date")),
        nb_graines_semees=_to_int(parsed.get("nb_graines_semees")),
        nb_plants_godets=_to_int(parsed.get("nb_plants_godets")),
    )
    if event.culture:
        cfg = db.query(CultureConfig).filter(CultureConfig.nom == event.culture).first()
        if cfg:
            event.type_organe_recolte = cfg.type_organe_recolte
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def creer_evenement_ligne(db: Session, ctx: TenantContext, parsed: dict, texte_original: str) -> Evenement:
    """[/parse multi-lignes bot.py] Crée un événement pour UNE ligne d'un message multi-actions
    (pas d'héritage type_organe — comportement historique de _parse_multi)."""
    nom_parcelle = parsed.get("parcelle")
    parcelle_obj = resolve_parcelle(db, nom_parcelle) if nom_parcelle else None
    event = Evenement(
        type_action=normalize_action(parsed.get("action")),
        culture=parsed.get("culture"),
        variete=parsed.get("variete"),
        quantite=_to_float(parsed.get("quantite")),
        unite=parsed.get("unite"),
        parcelle_id=parcelle_obj.id if parcelle_obj else None,
        rang=_to_int(parsed.get("rang")),
        duree=_to_int(parsed.get("duree_minutes")),
        traitement=parsed.get("traitement"),
        commentaire=parsed.get("commentaire"),
        texte_original=texte_original,
        date=parse_date(parsed.get("date")),
        nb_graines_semees=_to_int(parsed.get("nb_graines_semees")),
        nb_plants_godets=_to_int(parsed.get("nb_plants_godets")),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def creer_evenement_confirme(db: Session, ctx: TenantContext, parsed: dict, texte: str, parcelle_obj) -> Evenement:
    """[US-021] Sauvegarde effective après confirmation utilisateur (ex-_do_save_items).
    `parcelle_obj` est déjà résolu par l'appelant (qui gère le cas "parcelle inconnue" en
    interrompant le flux Telegram avant d'appeler cette fonction). Mute `parsed` en place
    (unité normalisée, variété héritée) — l'appelant l'utilise ensuite pour le récapitulatif."""
    type_organe_semis: Optional[str] = None
    if normalize_action(parsed.get("action")) == "semis":
        unite_normalisee = _normalize_unite_semis(parsed.get("unite"))
        if unite_normalisee != (parsed.get("unite") or "").lower().strip():
            log.info(
                "[US-037] Unité semis '%s' normalisée en '%s' (culture=%s)",
                parsed.get("unite"), unite_normalisee, parsed.get("culture"),
            )
        parsed["unite"] = unite_normalisee

        culture_semis = (parsed.get("culture") or "").strip()
        if culture_semis:
            type_organe_semis = get_type_organe(db, culture_semis)

    source_evenement_ids: Optional[str] = parsed.get("source_evenement_ids")
    if normalize_action(parsed.get("action")) == "plantation" and parsed.get("culture"):
        variete_src, src_ids = _find_plantation_sources(
            db, parsed["culture"], parsed.get("variete"), float(parsed.get("quantite") or 0),
        )
        if variete_src and not parsed.get("variete"):
            parsed["variete"] = variete_src
            log.info(f"[US-029 CA5] Variété '{variete_src}' héritée du godet → plantation '{parsed['culture']}'")
        if src_ids:
            source_evenement_ids = src_ids
            log.info(f"[US-029 CA7] source_evenement_ids='{src_ids}' pour plantation '{parsed.get('culture')}'")

    event = Evenement(
        type_action=normalize_action(parsed.get("action")),
        culture=parsed.get("culture"),
        variete=parsed.get("variete"),
        quantite=_to_float(parsed.get("quantite")),
        unite=parsed.get("unite"),
        parcelle_id=parcelle_obj.id if parcelle_obj else None,
        rang=_to_int(parsed.get("rang")),
        duree=_to_int(parsed.get("duree_minutes")),
        traitement=parsed.get("traitement"),
        commentaire=parsed.get("commentaire"),
        texte_original=texte,
        date=parse_date(parsed.get("date")),
        nb_graines_semees=_to_int(parsed.get("nb_graines_semees")),
        nb_plants_godets=_to_int(parsed.get("nb_plants_godets")),
        source_evenement_ids=source_evenement_ids,
        type_organe_recolte=type_organe_semis,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(
        f"💾 DB SAVE        : id={event.id} | action={event.type_action} | culture={event.culture} "
        f"| qte={event.quantite} {event.unite or ''} | parcelle={event.parcelle_id} | date={event.date}"
    )
    return event


def creer_evenement_godet(db: Session, ctx: TenantContext, parsed: dict, texte: str) -> Evenement:
    """[US-029] Sauvegarde une mise en godet avec auto-link au semis parent + héritage variété."""
    culture_str = parsed.get("culture") or ""
    variete_str = parsed.get("variete")

    origine_graines_id: Optional[int] = None
    semis_rows = (
        db.query(Evenement.id, Evenement.variete)
        .filter(Evenement.type_action == "semis")
        .filter(func.lower(Evenement.culture) == culture_str.lower())
        .filter(Evenement.culture.isnot(None))
    )
    if variete_str:
        semis_rows = semis_rows.filter(Evenement.variete == variete_str)
    semis_list = semis_rows.order_by(Evenement.date.asc()).all()

    if len(semis_list) == 1:
        origine_graines_id = semis_list[0].id
        if not variete_str and semis_list[0].variete:
            parsed["variete"] = semis_list[0].variete
            variete_str = semis_list[0].variete
            log.info(f"[US-029 CA4] Variété '{variete_str}' héritée du semis id={origine_graines_id} pour '{culture_str}'")
        log.info(f"[US-029 CA3] Godet lié au semis id={origine_graines_id} pour '{culture_str}/{variete_str}'")

    event = Evenement(
        type_action="mise_en_godet",
        culture=culture_str,
        variete=parsed.get("variete"),
        quantite=_to_float(parsed.get("quantite")),
        unite=parsed.get("unite"),
        parcelle_id=None,
        rang=None,
        duree=None,
        traitement=None,
        commentaire=parsed.get("commentaire"),
        texte_original=texte,
        date=parse_date(parsed.get("date")),
        nb_graines_semees=_to_int(parsed.get("nb_graines_semees")),
        nb_plants_godets=_to_int(parsed.get("nb_plants_godets")),
        origine_graines_id=origine_graines_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(f"💾 GODET SAVE : id={event.id} culture={event.culture} variete={event.variete} origine={origine_graines_id}")
    return event


def creer_evenement_observation(db: Session, ctx: TenantContext, fields: dict, texte: str, label: str) -> Evenement:
    """[US-038] Sauvegarde une note/observation comme Evenement(type_action='observation')."""
    parcelle_obj = None
    nom_parcelle = fields.get("parcelle")
    if nom_parcelle:
        parcelle_obj = resolve_parcelle(db, nom_parcelle)
        if parcelle_obj is None:
            log.warning(f"⚠️ [US-038] PARCELLE INCONNUE : {nom_parcelle!r} — note enregistrée sans parcelle")

    event = Evenement(
        type_action=normalize_action("observation"),
        culture=fields.get("culture"),
        variete=fields.get("variete"),
        parcelle_id=parcelle_obj.id if parcelle_obj else None,
        duree=_to_int(fields.get("duree_minutes")),
        traitement=fields.get("traitement"),
        commentaire=f"[{label}] {fields['constat']}",
        texte_original=texte,
        date=parse_date(fields.get("date")),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(f"💾 DB SAVE [US-038] : id={event.id} | culture={event.culture} | parcelle_id={event.parcelle_id}")
    return event


def creer_evenement_perte(db: Session, ctx: TenantContext, item: dict, texte: str) -> Evenement:
    """[perte / perte_godet] Sauvegarde directe depuis un callback inline (ex-_save_perte_item)."""
    event = Evenement(
        type_action=item.get("action"),
        culture=item.get("culture"),
        variete=item.get("variete"),
        quantite=_to_float(item.get("quantite")),
        unite=item.get("unite") or "plants",
        parcelle_id=None,
        commentaire=item.get("commentaire"),
        texte_original=texte,
        date=parse_date(item.get("date")),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(f"💾 PERTE SAVE : id={event.id} action={event.type_action} culture={event.culture} variete={event.variete} qte={event.quantite}")
    return event


def corriger_evenement(db: Session, ctx: TenantContext, evenement_id: int, corrections: dict, trace: str) -> Optional[Evenement]:
    """[/corriger étape 5] Applique les champs modifiés + trace d'auditabilité."""
    event = db.get(Evenement, evenement_id)
    if event is None:
        return None

    mapping = {
        "action": "type_action", "culture": "culture", "variete": "variete",
        "quantite": "quantite", "unite": "unite", "parcelle": "parcelle",
        "rang": "rang", "duree_minutes": "duree", "traitement": "traitement",
        "commentaire": "commentaire",
    }
    for champ, valeur in corrections.items():
        if champ == "_parcelle_id":
            continue
        col = mapping.get(champ, champ)
        if champ == "date":
            setattr(event, "date", parse_date(valeur))
        elif champ == "quantite":
            setattr(event, col, _to_float(valeur))
        elif champ in ("rang", "duree_minutes"):
            setattr(event, col, _to_int(valeur))
        elif champ == "parcelle":
            event.parcelle_id = corrections.get("_parcelle_id")
        elif hasattr(event, col):
            setattr(event, col, valeur)

    event.texte_original = (event.texte_original or "") + trace
    db.commit()
    db.refresh(event)
    return event


def supprimer_evenement(db: Session, ctx: TenantContext, evenement_id: int) -> bool:
    """[/corriger — suppression] Supprime un événement. Retourne False si introuvable."""
    event = db.get(Evenement, evenement_id)
    if event is None:
        return False
    db.delete(event)
    db.commit()
    log.info(f"🗑 SUPPRESSION     : id={evenement_id}")
    return True


def cycle_vie_culture(db: Session, ctx: TenantContext, culture: str, variete: Optional[str]) -> dict:
    """[GET /godets/detail] Cycle de vie complet semis → godets → plantations → ventes/pertes
    pour une (culture, variété)."""
    from sqlalchemy.orm import joinedload

    culture_lower = culture.lower()

    godet_q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "mise_en_godet")
        .filter(func.lower(Evenement.culture) == culture_lower)
    )
    godet_q = godet_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else godet_q.filter(Evenement.variete.is_(None))
    godet_events = godet_q.order_by(Evenement.date.asc()).all()

    godet_ids = {str(g.id) for g in godet_events}

    semis_q = (
        db.query(Evenement)
        .options(joinedload(Evenement.parcelle_rel))
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(or_(Evenement.parcelle_id.is_(None), Parcelle.est_pepiniere.is_(True)))
    )
    semis_q = semis_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else semis_q.filter(Evenement.variete.is_(None))
    semis_events = semis_q.order_by(Evenement.date.asc()).all()

    plantation_candidates = (
        db.query(Evenement)
        .options(joinedload(Evenement.parcelle_rel))
        .filter(Evenement.type_action == "plantation")
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.source_evenement_ids.isnot(None))
        .order_by(Evenement.date.asc())
        .all()
    )
    linked_plantations = [
        p for p in plantation_candidates if godet_ids & set(p.source_evenement_ids.split(";"))
    ]

    vendu_q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "vendu")
        .filter(func.lower(Evenement.culture) == culture_lower)
    )
    vendu_q = vendu_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else vendu_q.filter(Evenement.variete.is_(None))
    vendu_events = vendu_q.order_by(Evenement.date.asc()).all()

    perte_q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "perte_godet")
        .filter(func.lower(Evenement.culture) == culture_lower)
    )
    perte_q = perte_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else perte_q.filter(Evenement.variete.is_(None))
    perte_events = perte_q.order_by(Evenement.date.asc()).all()

    total_plants = sum(g.nb_plants_godets or 0 for g in godet_events)
    total_graines = sum(int(s.quantite or 0) for s in semis_events)
    taux = round(total_plants / total_graines * 100) if total_graines and total_plants else None

    return {
        "semis": semis_events,
        "godets": godet_events,
        "plantations": linked_plantations,
        "ventes": vendu_events,
        "pertes_godet": perte_events,
        "taux_germination": taux,
    }


def deplacer_evenements(
    db: Session, ctx: TenantContext, culture: str, variete: Optional[str], parcelle_id_cible: int, nom_affiche: str
) -> int:
    """[US-007 CA8] Réassocie tous les événements localisés d'une culture (+variété) vers
    une nouvelle parcelle, avec trace d'auditabilité. Retourne le nombre mis à jour."""
    from datetime import date as _date

    events = evenements_localises_pour_maj(db, ctx, culture, variete)
    today = _date.today().isoformat()
    nb_updated = 0
    for event in events:
        ancienne = event.parcelle_rel.nom if event.parcelle_rel else "Non localisé"
        event.parcelle_id = parcelle_id_cible
        trace = f" | [DÉPL {today}] parcelle: {ancienne} → {nom_affiche}"
        event.texte_original = (event.texte_original or "") + trace
        nb_updated += 1
    db.commit()
    log.info(f"[US-007 CA8] UPDATE : {nb_updated} plantation(s) de '{culture}' → parcelle_id={parcelle_id_cible}")
    return nb_updated
