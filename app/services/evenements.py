"""
app/services/evenements.py — CRUD et requêtes sur Evenement [US-041 / US-042]
-----------------------------------------------------------------------
Centralise tous les accès directs à la table `evenements` auparavant
dispersés dans bot.py et main.py.

[US-042] Toutes les requêtes de lecture filtrent désormais par
`ctx.potager_id`, et toute création d'événement fixe `potager_id` sur la
ligne créée. Les accès par id (`db.get`) sont suivis d'une vérification
d'appartenance au tenant courant — un id d'un autre potager renvoie
None/False, jamais la donnée.
"""
import logging
from typing import Optional

from sqlalchemy import func, or_, and_, select
from sqlalchemy.orm import Session, selectinload

from app.services.context import TenantContext
from app.services.permissions import require_role
from database.models import Evenement, Parcelle
from utils.actions import normalize_action
from utils.date_utils import parse_date
from utils.parcelles import resolve_parcelle
from utils.stock import (
    get_type_organe,
    _find_plantation_sources,
    lots_candidats_mise_en_godet,
    lots_pepiniere_du_couple,
    lot_pepiniere_par_semis,
    calcul_godets_par_culture,
    calcul_stock_par_variete,
    stock_actif_variete,
)

log = logging.getLogger("potager")


class EvenementInvalideError(Exception):
    """[US-049] Classe de base — levée par `valider_evenement` quand un événement ne
    respecte pas les invariants métier du potager. Les appelants (bot.py, main.py)
    attrapent cette exception et la traduisent en message utilisateur — jamais de
    sauvegarde silencieuse d'un événement invalide, quel que soit le chemin
    d'écriture emprunté. Deux sous-classes distinctes pour permettre à l'appelant
    d'appliquer un traitement différent (blocage dur vs correction assistée) sans
    avoir à réévaluer lui-même la règle qui a échoué."""


class CultureInconnueError(EvenementInvalideError):
    """Culture jamais introduite dans le potager (aucun semis/plantation/mise en
    godet) — aucun scénario légitime, blocage dur systématique."""

    def __init__(self, culture: str):
        self.culture = culture
        super().__init__(
            f"Aucune trace de « {culture} » dans ce potager (aucun semis, aucune "
            f"plantation, aucune mise en godet enregistrée)."
        )


class ParcelleInconnueError(EvenementInvalideError):
    """Un nom de parcelle a été fourni mais ne résout vers aucune parcelle réelle du
    potager — distinct de `ParcelleIncoherenteError` (parcelle réelle, mais culture/
    variété jamais associée à elle)."""

    def __init__(self, nom_parcelle: str):
        self.nom_parcelle = nom_parcelle
        super().__init__(f"La parcelle « {nom_parcelle} » n'existe pas dans votre potager.")


class ParcelleIncoherenteError(EvenementInvalideError):
    """Culture/variété sans historique sur la parcelle précise citée, alors que la
    culture existe bien ailleurs dans le potager — peut légitimement être corrigée
    (ex: sélection assistée de la bonne parcelle) plutôt que bloquée sèchement."""

    def __init__(self, culture: str, variete: Optional[str], parcelle_nom: str):
        self.culture = culture
        self.variete = variete
        self.parcelle_nom = parcelle_nom
        label = f"{culture} {variete}" if variete else culture
        super().__init__(f"Aucune trace de « {label} » sur « {parcelle_nom} ».")


class CultureManquanteError(EvenementInvalideError):
    """[fix bug id=351] Action qui porte structurellement sur une culture précise
    (semis/plantation/mise_en_godet/recolte/perte/perte_godet/vendu) mais sans
    culture fournie — l'événement n'a aucun sens (ex: une "mise en godet" de rien,
    cas réel où Groq avait renvoyé culture=null malgré variete="gourmand"
    présente). Volontairement PAS étendue aux actions "zone" (observation,
    paillage, arrosage, désherbage, taille, tuteurage, fertilisation, binage...)
    qui s'appliquent légitimement à une parcelle entière sans viser une culture
    précise — une règle globale casserait ces usages."""

    def __init__(self, action: str):
        self.action = action
        super().__init__(
            f"Impossible d'enregistrer une action « {action} » sans préciser de culture."
        )


class LotGrainesEpuiseesError(EvenementInvalideError):
    """[fix garde-fou graines du lot] Une mise en godet solderait plus de graines
    qu'il n'en reste sur son lot de semis parent.

    Complète `TauxGerminationImpossibleError`, qui ne contrôle qu'UN lot de godet
    isolé (`nb_plants_godets > nb_graines_semees` du même événement) et laisse donc
    passer le cumul : un lot de 10 graines dont 6 sont déjà soldées accepte encore
    10 plants de plus, aboutissant à 16 graines soldées sur 10 semées. US-065/CA4
    avait identifié ce cas mais le SIGNALE seulement en lecture (`incoherence_saisie`) ;
    ce garde-fou empêche d'en créer de nouveaux. Blocage dur : aucun scénario
    biologique ne permet de tirer d'un lot plus de graines qu'il n'en contenait.

    Le contrôle ne s'applique qu'aux godets rattachés à un lot dont la quantité
    semée est connue — un semis sans quantité ne permet aucune déduction, et rien
    ne doit être bloqué sur une information absente.
    """

    def __init__(self, semis_id: int, graines_demandees: int, graines_restantes: int, graines_semees: int):
        self.semis_id = semis_id
        self.graines_demandees = graines_demandees
        self.graines_restantes = graines_restantes
        self.graines_semees = graines_semees
        super().__init__(
            f"Ce lot de semis (#{semis_id}, {graines_semees} graines semées) n'a plus que "
            f"{graines_restantes} graine(s) en germination : impossible d'en solder "
            f"{graines_demandees} de plus. Vérifiez le lot choisi ou la quantité saisie."
        )


class AucunLotDisponibleError(EvenementInvalideError):
    """[fix garde-fou graines du lot] Des lots de semis existent pour cette culture,
    mais aucun n'a assez de graines en germination pour porter ce repiquage.

    Sans cette règle, l'épuisement de tous les lots produisait l'effet pervers
    inverse de celui recherché : plus aucun lot candidat → plus aucun rattachement
    → plus rien à contrôler, et la mise en godet passait *orpheline*, sans le
    moindre signalement. Le potager sait pourtant que tous les lots sont soldés.

    Ne s'applique QUE si au moins un lot de pépinière existe pour le couple
    (culture, variété). Aucun semis du tout reste un cas légitime — plants achetés
    en jardinerie, bouture, don — et continue de produire un godet sans parent.
    """

    def __init__(self, culture: str, variete: Optional[str], graines_demandees: int, meilleur_reste: int):
        self.culture = culture
        self.variete = variete
        self.graines_demandees = graines_demandees
        self.meilleur_reste = meilleur_reste
        label = f"{culture} {variete}" if variete else culture
        if meilleur_reste <= 0:
            detail = "tous vos lots de semis sont entièrement soldés"
        else:
            detail = f"le lot le mieux fourni n'a plus que {meilleur_reste} graine(s) en germination"
        super().__init__(
            f"Aucun lot de semis de « {label} » ne peut fournir {graines_demandees} plant(s) : "
            f"{detail}. Enregistrez d'abord le semis correspondant, ou corrigez la quantité."
        )


class LotIndetermineError(EvenementInvalideError):
    """[fix garde-fou graines du lot] Plusieurs lots de semis peuvent porter ce
    repiquage, et aucun n'a été désigné.

    Le jardinier est le seul à savoir de quelle barquette viennent ses plants :
    aucune heuristique ne peut trancher. Enregistrer un godet sans parent « en
    attendant » rouvrirait la porte que `AucunLotDisponibleError` ferme — des lots
    existent et sont capables, seul le choix manque. Le bot pose la question avant
    d'en arriver là (menu inline) ; cette erreur protège les autres canaux et le cas
    où le choix a été escamoté.
    """

    def __init__(self, culture: str, variete: Optional[str], nb_lots: int):
        self.culture = culture
        self.variete = variete
        self.nb_lots = nb_lots
        label = f"{culture} {variete}" if variete else culture
        super().__init__(
            f"{nb_lots} lots de semis de « {label} » peuvent recevoir ce repiquage : "
            f"précisez lequel, il ne peut pas être deviné."
        )


class LotSemisInconnuError(EvenementInvalideError):
    """[fix rattachement lot godet] Un lot de semis a été explicitement désigné pour
    une mise en godet, mais l'identifiant ne correspond à aucun semis du potager
    courant — menu inline expiré, événement supprimé entre-temps, ou identifiant
    d'un autre tenant. Jamais de rattachement silencieux à un autre lot : le lien
    semis → godet porte tout l'avancement de la pépinière (US-065)."""

    def __init__(self, semis_id: int):
        self.semis_id = semis_id
        super().__init__(
            f"Le lot de semis #{semis_id} n'existe pas (ou plus) dans ce potager."
        )


class TauxGerminationImpossibleError(EvenementInvalideError):
    """[fix bug id=355] Une mise en godet ne peut jamais produire plus de plants
    repiqués qu'il n'y avait de graines semées à l'origine (taux de réussite > 100%
    impossible biologiquement) — cas réel : "30 fèves sur 5 graines" enregistré
    tel quel, sans aucun garde-fou, affichant un taux de 600% de réussite. Blocage
    dur : il n'existe aucun scénario légitime où nb_plants_godets > nb_graines_semees."""

    def __init__(self, nb_plants_godets: int, nb_graines_semees: int):
        self.nb_plants_godets = nb_plants_godets
        self.nb_graines_semees = nb_graines_semees
        super().__init__(
            f"{nb_plants_godets} plants en godet pour seulement {nb_graines_semees} "
            f"graines semées : taux de réussite > 100%, impossible."
        )


class StockInsuffisantError(EvenementInvalideError):
    """[fix contrôle quantité perte] Une perte (jardin ou godet) réclame plus de
    plants que ce qu'il reste réellement en stock pour cette culture/variété dans
    ce potager. Sans ce garde-fou, une perte pouvait être enregistrée pour une
    quantité qui dépasse ce qui existe (ex: perte de 5 navets « jaune » alors que
    seuls 2 plants « jaune » sont encore actifs au jardin), ou même pour une
    variété totalement absente du potager. Blocage dur, même logique que les
    autres garde-fous de quantité de ce module (LotGrainesEpuiseesError,
    TauxGerminationImpossibleError) : aucun scénario légitime ne permet de perdre
    plus de plants qu'il n'en reste."""

    def __init__(self, action: str, culture: str, variete: Optional[str], quantite: float, stock_disponible: float):
        self.action = action
        self.culture = culture
        self.variete = variete
        self.quantite = quantite
        self.stock_disponible = stock_disponible
        label = f"{culture} {variete}" if variete else culture
        lieu = "en godet" if action == "perte_godet" else "au jardin"
        super().__init__(
            f"Perte de {quantite:g} « {label} » impossible : il n'y a que "
            f"{stock_disponible:g} plant(s) {lieu} actuellement dans ce potager."
        )


def _stock_disponible_perte(
    db: Session, ctx: TenantContext, action_norm: str, culture: str, variete: Optional[str]
) -> float:
    """[fix contrôle quantité perte] Stock actif utilisable pour valider une perte :
    godets en pépinière pour `perte_godet`, plants actifs au jardin pour `perte`.
    Somme sur toutes les variétés si `variete` n'est pas précisé — une perte non
    qualifiée porte sur l'ensemble du stock de la culture, pas sur une seule
    variété."""
    if action_norm == "perte_godet":
        rows = calcul_godets_par_culture(db, culture, potager_id=ctx.potager_id)
        stock_ligne = lambda r: r.get("stock_residuel_godet") or 0
    else:
        rows = calcul_stock_par_variete(db, culture, potager_id=ctx.potager_id)
        stock_ligne = stock_actif_variete
    if variete:
        variete_lower = variete.strip().lower()
        rows = [r for r in rows if (r.get("variete") or "").strip().lower() == variete_lower]
    return sum(stock_ligne(r) for r in rows)


# [US-049] Actions qui introduisent légitimement une nouvelle culture dans le potager
# (identique à _ACTIONS_SOURCE historique de bot.py) — exemptées de la validation,
# c'est justement leur rôle de faire exister la culture pour la première fois.
_ACTIONS_SOURCE_CULTURE = {"semis", "plantation", "mise_en_godet", "vendu", "perte_godet"}

# [fix bug id=351] Actions pour lesquelles une culture est structurellement
# obligatoire — sans elle l'événement ne décrit rien d'exploitable. Sur-ensemble
# de _ACTIONS_SOURCE_CULTURE (+ recolte, perte) : ces deux-là présupposent aussi
# une culture déjà en place, donc passent par la suite de valider_evenement au
# lieu d'un simple retour anticipé, mais doivent tout autant être rejetées si
# culture est vide plutôt que silencieusement laissées passer.
_ACTIONS_CULTURE_OBLIGATOIRE = _ACTIONS_SOURCE_CULTURE | {"recolte", "perte"}


def valider_evenement(
    db: Session,
    ctx: TenantContext,
    *,
    action: Optional[str],
    culture: Optional[str],
    variete: Optional[str] = None,
    parcelle: Optional[Parcelle] = None,
    nom_parcelle_brut: Optional[str] = None,
    quantite: Optional[float] = None,
) -> None:
    """
    [US-049] Garde-fou unique et non contournable — appelé par TOUTE fonction de ce
    module qui crée ou modifie un Evenement, indépendamment du canal (Telegram,
    corrections, notes, API) et du nombre d'items traités dans un même appel.

    Cinq règles :
    0. Si `nom_parcelle_brut` est fourni (un nom de parcelle a été cité) mais que
       `parcelle` est None (la résolution a échoué), la parcelle citée n'existe pas
       dans le potager — `ParcelleInconnueError`. Appliquée quel que soit l'action/
       culture : contrairement aux règles 1-3, ce n'est pas affaire de cohérence
       agronomique mais d'existence pure de la ligne référencée.
    1. [fix bug id=351] Si `culture` est vide ET que l'action fait partie de
       `_ACTIONS_CULTURE_OBLIGATOIRE` (semis, plantation, mise_en_godet, recolte,
       perte, perte_godet, vendu) — `CultureManquanteError`. Ne s'applique PAS aux
       actions "zone" (observation, paillage, arrosage, désherbage...) qui restent
       légitimement culture-optionnelles (comportement inchangé pour elles).
    2-3. Applicables uniquement aux actions qui supposent une culture déjà en place
       (récolte, perte... — cf. `_ACTIONS_SOURCE_CULTURE` pour les actions
       exemptées) :
       2. La culture doit avoir été introduite au moins une fois via un semis, une
          plantation ou une mise en godet — sinon `CultureInconnueError`.
       3. Si une parcelle réelle est fournie, la culture/variété doit avoir un
          historique sur CETTE parcelle précise — sinon `ParcelleIncoherenteError`.
          En pratique, bot.py corrige déjà ce cas en amont via une sélection
          assistée (US-021 CA8) avant d'atteindre ce point ; cette règle est le
          filet de sécurité qui garantit qu'aucun appelant, présent ou futur, ne
          peut persister une incohérence en contournant cette correction.
    4. [fix contrôle quantité perte] Pour `perte`/`perte_godet`, si `quantite` est
       fournie, elle ne peut pas dépasser le stock réellement disponible (plants
       actifs au jardin, ou godets en pépinière) pour cette culture/variété dans
       CE potager — sinon `StockInsuffisantError`. S'applique aussi à `perte_godet`
       bien qu'il fasse partie de `_ACTIONS_SOURCE_CULTURE` : cette exemption ne
       porte que sur l'historique de plantation, pas sur le stock de godets.
    """
    if nom_parcelle_brut and parcelle is None:
        raise ParcelleInconnueError(nom_parcelle_brut)

    from utils.culture_resolve import culture_deja_plantee

    action_norm = normalize_action(action)
    if not culture:
        if action_norm in _ACTIONS_CULTURE_OBLIGATOIRE:
            raise CultureManquanteError(action_norm)
        return

    # [fix contrôle quantité perte] perte_godet quitte la fonction juste après
    # (via _ACTIONS_SOURCE_CULTURE, il n'est jamais soumis à culture_deja_plantee)
    # mais reste soumis au contrôle de stock godet, fait ici avant ce départ.
    if action_norm == "perte_godet" and quantite is not None:
        stock_disponible = _stock_disponible_perte(db, ctx, action_norm, culture, variete)
        if quantite > stock_disponible:
            raise StockInsuffisantError(action_norm, culture, variete, quantite, stock_disponible)

    if action_norm in _ACTIONS_SOURCE_CULTURE:
        return

    if not culture_deja_plantee(db, ctx.potager_id, culture):
        raise CultureInconnueError(culture)

    # `perte` : la culture est confirmée introduite (ligne ci-dessus) avant de
    # contrôler le stock — une culture jamais plantée doit lever
    # CultureInconnueError, pas StockInsuffisantError.
    if action_norm == "perte" and quantite is not None:
        stock_disponible = _stock_disponible_perte(db, ctx, action_norm, culture, variete)
        if quantite > stock_disponible:
            raise StockInsuffisantError(action_norm, culture, variete, quantite, stock_disponible)

    if parcelle is not None:
        from app.services.parcelles import parcelles_avec_culture
        parcelles_ok = parcelles_avec_culture(db, ctx, culture, variete)
        if parcelle.id not in {p.id for p in parcelles_ok}:
            raise ParcelleIncoherenteError(culture, variete, parcelle.nom)


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


def _normalize_unite_semis(unite_brute: Optional[str], texte_original: Optional[str] = None) -> str:
    """Normalise l'unité d'un semis vers 'graines'|'pieds'|'m²' (jamais forcée si m²).

    [fix unité semis hallucinée] Quand `texte_original` est fourni, une unité autre
    que "graines" n'est retenue que si elle est réellement mentionnée dans la
    dictée. Sans unité prononcée ("semis de 50 choux"), Groq renvoie couramment
    "plants" — que la table ci-dessus mappe légitimement sur "pieds" — et le semis
    se retrouve compté en pieds au lieu de graines. Semer, par définition, met des
    graines en terre : c'est le défaut, et il reprend la main dès que l'unité
    inventée n'est pas ancrée dans le texte.

    Sans `texte_original` (appels historiques, tests unitaires d'US-037), le
    comportement d'origine est conservé à l'identique.
    """
    cle = (unite_brute or "").lower().strip()
    canonique = _UNITES_SEMIS_CANONIQUES.get(cle, "graines")

    if texte_original is not None and canonique != "graines":
        from utils.validation import unite_semis_ancree_dans_texte
        if not unite_semis_ancree_dans_texte(canonique, texte_original):
            log.info(
                "[fix unité semis hallucinée] Unité '%s' (→ '%s') absente du texte → "
                "retour au défaut 'graines' | texte=%r",
                unite_brute, canonique, texte_original,
            )
            return "graines"

    return canonique


def _cond_localisation_culture(potager_id: int):
    """Une culture est "localisée" via une 'plantation' OU un 'semis' directement lié
    à une VRAIE parcelle de pleine terre (semis pleine terre). Voir bot.py historique
    [US-037 / migration_v15] pour le détail du raisonnement agronomique.
    [US-042] pepiniere_ids scopé au potager courant — évite qu'un id de parcelle
    pépinière d'un autre potager n'entre dans le NOT IN."""
    pepiniere_ids = select(Parcelle.id).where(
        Parcelle.est_pepiniere.is_(True), Parcelle.potager_id == potager_id
    )
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
    q = db.query(func.count(Evenement.id)).filter(Evenement.potager_id == ctx.potager_id)
    if jusqua is not None:
        from datetime import datetime as _dt
        q = q.filter(Evenement.date <= _dt(jusqua.year, jusqua.month, jusqua.day, 23, 59, 59))
    return q.scalar() or 0


def compter_evenements_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> int:
    """Nombre d'événements rattachés à une parcelle (avant suppression)."""
    return (
        db.query(Evenement)
        .filter(Evenement.parcelle_id == parcelle_id, Evenement.potager_id == ctx.potager_id)
        .count()
    )


# ── Lecture ───────────────────────────────────────────────────────────────────
def get_evenement(db: Session, ctx: TenantContext, evenement_id: int) -> Optional[Evenement]:
    event = db.get(Evenement, evenement_id)
    if event is None or event.potager_id != ctx.potager_id:
        return None
    return event


def dernier_evenement(db: Session, ctx: TenantContext) -> Optional[Evenement]:
    return (
        db.query(Evenement)
        .filter(Evenement.potager_id == ctx.potager_id)
        .order_by(Evenement.id.desc())
        .first()
    )


def evenements_recents(db: Session, ctx: TenantContext, limit: int = 10) -> list[Evenement]:
    return (
        db.query(Evenement)
        .filter(Evenement.potager_id == ctx.potager_id)
        .order_by(Evenement.date.desc())
        .limit(limit)
        .all()
    )


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
    """[US-027] Historique paginé avec filtres — utilisé par GET /historique.

    [US-063] `action` accepte plusieurs types séparés par des virgules
    (`perte,perte_godet`). Les catégories de filtre du journal recouvrent en effet
    plusieurs `type_action` réels — « Entretien » à lui seul en couvre six. Filtrer
    côté client sur la page déjà chargée fausserait la pagination, qui est calculée
    côté serveur : le filtre doit donc porter sur la requête. Une valeur unique
    reste traitée exactement comme avant.
    """
    from sqlalchemy.orm import joinedload

    q = (
        db.query(Evenement)
        .options(joinedload(Evenement.parcelle_rel))
        .filter(Evenement.potager_id == ctx.potager_id)
        .order_by(Evenement.date.desc())
    )
    if action:
        types = [a.strip() for a in str(action).split(",") if a.strip()]
        if types:
            q = q.filter(Evenement.type_action.in_(types))
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
    q = (
        db.query(Evenement)
        .options(selectinload(Evenement.parcelle_rel))
        .filter(Evenement.potager_id == ctx.potager_id)
    )
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
        .filter(Evenement.type_action == "mise_en_godet", Evenement.potager_id == ctx.potager_id)
        .order_by(Evenement.date.desc())
        .all()
    )
    en_attente = []
    for g in godets_all:
        plantation = db.query(Evenement).filter(
            Evenement.type_action == "plantation",
            Evenement.culture == g.culture,
            Evenement.potager_id == ctx.potager_id,
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
        .filter(
            _cond_localisation_culture(ctx.potager_id),
            func.lower(Evenement.culture) == culture.lower(),
            Evenement.potager_id == ctx.potager_id,
        )
        .all()
    )


def evenements_localises_recherche_partielle(db: Session, ctx: TenantContext, motif: str) -> list[Evenement]:
    """[US-007] Recherche partielle (typos/accents/pluriel) sur culture localisée."""
    return (
        db.query(Evenement)
        .filter(
            _cond_localisation_culture(ctx.potager_id),
            func.lower(Evenement.culture).ilike(f"%{motif}%"),
            Evenement.potager_id == ctx.potager_id,
        )
        .all()
    )


def evenements_localises_pour_maj(
    db: Session, ctx: TenantContext, culture: str, variete: Optional[str]
) -> list[Evenement]:
    """[US-007] Plantations / semis pleine terre d'une culture (+ variété optionnelle),
    utilisé pour compter puis réassocier à une nouvelle parcelle."""
    q = db.query(Evenement).filter(
        _cond_localisation_culture(ctx.potager_id),
        func.lower(Evenement.culture) == culture.lower(),
        Evenement.potager_id == ctx.potager_id,
    )
    if variete is not None:
        q = q.filter(Evenement.variete == variete)
    return q.all()


def liberer_evenements_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> int:
    """[US-009] Compte puis détache (parcelle_id=NULL) tous les événements d'une parcelle
    supprimée. Ne commit pas — l'appelant commit avec la désactivation de la parcelle."""
    q = db.query(Evenement).filter(
        Evenement.parcelle_id == parcelle_id, Evenement.potager_id == ctx.potager_id
    )
    nb = q.count()
    q.update({"parcelle_id": None}, synchronize_session="fetch")
    return nb


def compter_traitements(db: Session, ctx: TenantContext) -> int:
    """[cmd_stats bot.py] Nombre total d'événements de traitement."""
    return (
        db.query(func.count(Evenement.id))
        .filter(Evenement.type_action == "traitement", Evenement.potager_id == ctx.potager_id)
        .scalar()
    )


def traitements_appliques(db: Session, ctx: TenantContext) -> list[tuple[str, int]]:
    """[/stats] Nombre d'applications par produit de traitement."""
    return (
        db.query(Evenement.traitement, func.count(Evenement.id))
        .filter(Evenement.type_action == "traitement", Evenement.potager_id == ctx.potager_id)
        .group_by(Evenement.traitement)
        .all()
    )


def cultures_avec_mise_en_godet(db: Session, ctx: TenantContext) -> set[str]:
    """[/stats] Cultures ayant au moins une mise en godet (origine "pépinière")."""
    return {
        row[0].lower()
        for row in db.query(Evenement.culture)
        .filter(Evenement.type_action == "mise_en_godet", Evenement.potager_id == ctx.potager_id)
        .filter(Evenement.culture.isnot(None))
        .distinct()
        .all()
    }


# ── Écriture ──────────────────────────────────────────────────────────────────
def creer_evenement_depuis_parse(db: Session, ctx: TenantContext, parsed: dict, texte_original: str) -> Evenement:
    """[POST /parse, POST /voice-ACTION] Crée un événement depuis un item parsé par Groq,
    avec héritage automatique de type_organe_recolte depuis culture_config."""
    require_role(ctx, "editor", "enregistrer d'action")
    from database.models import CultureConfig

    nom_parcelle = parsed.get("parcelle")
    parcelle_obj = resolve_parcelle(db, nom_parcelle, potager_id=ctx.potager_id) if nom_parcelle else None
    valider_evenement(
        db, ctx,
        action=parsed.get("action"), culture=parsed.get("culture"),
        variete=parsed.get("variete"), parcelle=parcelle_obj,
    )
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
        potager_id=ctx.potager_id,
    )
    if event.culture:
        cfg = (
            db.query(CultureConfig)
            .filter(
                CultureConfig.nom == event.culture,
                or_(CultureConfig.potager_id == ctx.potager_id, CultureConfig.potager_id.is_(None)),
            )
            .first()
        )
        if cfg:
            event.type_organe_recolte = cfg.type_organe_recolte
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def creer_evenement_ligne(db: Session, ctx: TenantContext, parsed: dict, texte_original: str) -> Evenement:
    """[/parse multi-lignes bot.py] Crée un événement pour UNE ligne d'un message multi-actions
    (pas d'héritage type_organe — comportement historique de _parse_multi)."""
    require_role(ctx, "editor", "enregistrer d'action")
    nom_parcelle = parsed.get("parcelle")
    parcelle_obj = resolve_parcelle(db, nom_parcelle, potager_id=ctx.potager_id) if nom_parcelle else None
    valider_evenement(
        db, ctx,
        action=parsed.get("action"), culture=parsed.get("culture"),
        variete=parsed.get("variete"), parcelle=parcelle_obj,
    )
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
        potager_id=ctx.potager_id,
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
    require_role(ctx, "editor", "enregistrer d'action")
    type_organe_semis: Optional[str] = None
    if normalize_action(parsed.get("action")) == "semis":
        unite_normalisee = _normalize_unite_semis(parsed.get("unite"), texte)
        if unite_normalisee != (parsed.get("unite") or "").lower().strip():
            log.info(
                "[US-037] Unité semis '%s' normalisée en '%s' (culture=%s)",
                parsed.get("unite"), unite_normalisee, parsed.get("culture"),
            )
        parsed["unite"] = unite_normalisee

        culture_semis = (parsed.get("culture") or "").strip()
        if culture_semis:
            type_organe_semis = get_type_organe(db, culture_semis, potager_id=ctx.potager_id)

    source_evenement_ids: Optional[str] = parsed.get("source_evenement_ids")
    if normalize_action(parsed.get("action")) == "plantation" and parsed.get("culture"):
        variete_src, src_ids = _find_plantation_sources(
            db, parsed["culture"], parsed.get("variete"), float(parsed.get("quantite") or 0),
            potager_id=ctx.potager_id,
        )
        if variete_src and not parsed.get("variete"):
            parsed["variete"] = variete_src
            log.info(f"[US-029 CA5] Variété '{variete_src}' héritée du godet → plantation '{parsed['culture']}'")
        if src_ids:
            source_evenement_ids = src_ids
            log.info(f"[US-029 CA7] source_evenement_ids='{src_ids}' pour plantation '{parsed.get('culture')}'")

    valider_evenement(
        db, ctx,
        action=parsed.get("action"), culture=parsed.get("culture"),
        variete=parsed.get("variete"), parcelle=parcelle_obj,
        nom_parcelle_brut=parsed.get("parcelle"),
        quantite=_to_float(parsed.get("quantite")),
    )

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
        potager_id=ctx.potager_id,
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
    require_role(ctx, "editor", "enregistrer d'action")
    culture_str = parsed.get("culture") or ""
    variete_str = parsed.get("variete")

    # [fix garde-fou graines du lot] Nombre de graines que ce repiquage solde sur son
    # lot parent — même repli qu'US-065/CA2 : le « sur N graines » s'il est déclaré,
    # sinon les plants repiqués. Calculé en tête car il conditionne le choix du lot.
    nb_graines_val = _to_int(parsed.get("nb_graines_semees"))
    nb_plants_val = _to_int(parsed.get("nb_plants_godets"))
    graines_demandees = nb_graines_val or nb_plants_val or 0

    # [fix rattachement lot godet] Trois chemins, dans cet ordre de priorité :
    #   1. lot explicitement désigné par le jardinier (menu inline du bot) ;
    #   2. déduction automatique s'il n'existe qu'un seul lot capable ;
    #   3. aucun lien (godet orphelin) — mais uniquement si la culture n'a AUCUN
    #      lot de semis, sinon c'est un refus (AucunLotDisponibleError).
    # La déduction (2) ne considère plus TOUS les semis de la culture — elle se
    # limite aux lots de PÉPINIÈRE capables d'absorber le repiquage. Un semis de
    # pleine terre ne produit jamais de godet.
    origine_graines_id: Optional[int] = _to_int(parsed.get("origine_graines_id"))
    semis_parent_variete: Optional[str] = None

    if origine_graines_id is not None:
        semis_parent = db.get(Evenement, origine_graines_id)
        if (
            semis_parent is None
            or semis_parent.potager_id != ctx.potager_id
            or semis_parent.type_action != "semis"
        ):
            raise LotSemisInconnuError(origine_graines_id)
        semis_parent_variete = semis_parent.variete
        log.info(
            "[fix rattachement lot godet] Godet rattaché au lot choisi id=%s (%s) pour '%s'",
            origine_graines_id, str(semis_parent.date)[:10], culture_str,
        )
    else:
        candidats = lots_candidats_mise_en_godet(
            db, culture_str, variete_str, potager_id=ctx.potager_id,
            graines_requises=graines_demandees,
        )
        if len(candidats) == 1:
            origine_graines_id   = candidats[0]["semis_id"]
            semis_parent_variete = candidats[0]["variete"]
            log.info(f"[US-029 CA3] Godet lié au semis id={origine_graines_id} pour '{culture_str}/{variete_str}'")
        elif len(candidats) > 1:
            # Ambiguïté non levée en amont. Enregistrer un orphelin ici rouvrirait
            # la porte que `AucunLotDisponibleError` vient de fermer : des lots
            # existent et peuvent porter ce repiquage, seul leur choix manque.
            # Aucun lot n'est tiré au hasard — c'est un refus, pas un contournement.
            log.warning(
                "[fix garde-fou graines du lot] Refus : %d lots candidats pour '%s/%s', "
                "aucun désigné — le lot doit être choisi, jamais deviné",
                len(candidats), culture_str, variete_str,
            )
            raise LotIndetermineError(culture_str, variete_str, len(candidats))
        elif graines_demandees > 0:
            # [fix garde-fou graines du lot] Aucun lot capable. Deux situations que
            # la liste vide ne distingue pas — et dont une seule est légitime.
            tous_les_lots = lots_pepiniere_du_couple(
                db, culture_str, variete_str, potager_id=ctx.potager_id
            )
            if tous_les_lots:
                meilleur_reste = max(lot["graines_en_germination"] for lot in tous_les_lots)
                log.warning(
                    "[fix garde-fou graines du lot] Refus : %d plant(s) de '%s/%s' demandés alors "
                    "qu'aucun des %d lot(s) de semis ne peut les fournir (meilleur reste : %d)",
                    graines_demandees, culture_str, variete_str, len(tous_les_lots), meilleur_reste,
                )
                raise AucunLotDisponibleError(
                    culture_str, variete_str, graines_demandees, meilleur_reste,
                )
            # Aucun semis du tout pour cette culture : godet sans parent légitime
            # (plants achetés, bouture, don) — comportement historique conservé.

    # [US-029 CA4] Héritage de la variété depuis le semis parent, quel que soit le
    # chemin de rattachement emprunté ci-dessus.
    if origine_graines_id is not None and not variete_str and semis_parent_variete:
        parsed["variete"] = semis_parent_variete
        variete_str = semis_parent_variete
        log.info(f"[US-029 CA4] Variété '{variete_str}' héritée du semis id={origine_graines_id} pour '{culture_str}'")

    # [US-049] Appel systématique — "mise_en_godet" est une action source (introduit
    # légitimement une nouvelle culture), donc toujours un no-op ici, mais l'appel
    # reste présent pour que ce point d'écriture ne soit jamais oublié si les règles
    # évoluent (cf. CA5 : parcourir toutes les fonctions d'écriture).
    valider_evenement(db, ctx, action="mise_en_godet", culture=culture_str, variete=variete_str, parcelle=None)

    # [fix bug id=355] nb_plants_godets ne peut jamais dépasser nb_graines_semees
    # (taux de réussite > 100% impossible) — bloqué avant écriture, pas seulement
    # affiché tel quel dans le récapitulatif.
    if nb_graines_val and nb_plants_val and nb_plants_val > nb_graines_val:
        raise TauxGerminationImpossibleError(nb_plants_val, nb_graines_val)

    # [fix garde-fou graines du lot] Contrôle du CUMUL sur le lot parent, que le
    # garde-fou ci-dessus ne voit pas : il ne compare qu'un lot de godet à lui-même.
    # Dès lors que le lot est connu et sa quantité semée renseignée, on ne peut pas
    # en solder plus de graines qu'il n'en reste.
    if origine_graines_id is not None:
        lot_parent = lot_pepiniere_par_semis(db, origine_graines_id, potager_id=ctx.potager_id)
        if lot_parent and lot_parent["graines_semees"] > 0 and graines_demandees > 0:
            restantes = lot_parent["graines_en_germination"]
            if graines_demandees > restantes:
                log.warning(
                    "[fix garde-fou graines du lot] Refus : %d graines demandées sur le lot #%s "
                    "qui n'en a plus que %d (sur %d semées) — culture='%s'",
                    graines_demandees, origine_graines_id, restantes,
                    lot_parent["graines_semees"], culture_str,
                )
                raise LotGrainesEpuiseesError(
                    origine_graines_id, graines_demandees, restantes, lot_parent["graines_semees"],
                )

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
        potager_id=ctx.potager_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(f"💾 GODET SAVE : id={event.id} culture={event.culture} variete={event.variete} origine={origine_graines_id}")
    return event


def creer_evenement_observation(db: Session, ctx: TenantContext, fields: dict, texte: str, label: str) -> Evenement:
    """[US-038] Sauvegarde une note/observation comme Evenement(type_action='observation')."""
    require_role(ctx, "editor", "enregistrer d'action")
    parcelle_obj = None
    nom_parcelle = fields.get("parcelle")
    if nom_parcelle:
        parcelle_obj = resolve_parcelle(db, nom_parcelle, potager_id=ctx.potager_id)
        if parcelle_obj is None:
            log.warning(f"⚠️ [US-038] PARCELLE INCONNUE : {nom_parcelle!r} — note enregistrée sans parcelle")

    valider_evenement(
        db, ctx,
        action="observation", culture=fields.get("culture"),
        variete=fields.get("variete"), parcelle=parcelle_obj,
    )

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
        potager_id=ctx.potager_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(f"💾 DB SAVE [US-038] : id={event.id} | culture={event.culture} | parcelle_id={event.parcelle_id}")
    return event


def creer_evenement_perte(db: Session, ctx: TenantContext, item: dict, texte: str) -> Evenement:
    """[perte / perte_godet] Sauvegarde directe depuis un callback inline (ex-_save_perte_item)."""
    require_role(ctx, "editor", "enregistrer d'action")
    valider_evenement(
        db, ctx,
        action=item.get("action"), culture=item.get("culture"),
        variete=item.get("variete"), parcelle=None,   # cette fonction ne localise jamais (parcelle_id toujours None)
        quantite=_to_float(item.get("quantite")),
    )
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
        potager_id=ctx.potager_id,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    log.info(f"💾 PERTE SAVE : id={event.id} action={event.type_action} culture={event.culture} variete={event.variete} qte={event.quantite}")
    return event


def corriger_evenement(db: Session, ctx: TenantContext, evenement_id: int, corrections: dict, trace: str) -> Optional[Evenement]:
    """[/corriger étape 5] Applique les champs modifiés + trace d'auditabilité."""
    require_role(ctx, "editor", "corriger un événement")
    event = db.get(Evenement, evenement_id)
    if event is None or event.potager_id != ctx.potager_id:
        return None

    # [US-049] Calcule l'état final (action/culture/variété/parcelle) qu'aurait
    # l'événement APRÈS application des corrections, et le valide AVANT toute
    # mutation — une correction manuelle reste soumise aux mêmes invariants
    # qu'une création (ex: corriger la parcelle vers un endroit incohérent avec
    # la culture/variété doit être refusé, pas seulement pour les nouveaux events).
    action_final   = corrections.get("action", event.type_action)
    culture_final  = corrections.get("culture", event.culture)
    variete_final  = corrections.get("variete", event.variete)
    quantite_final = corrections.get("quantite", event.quantite)
    if "parcelle" in corrections:
        parcelle_id_final = corrections.get("_parcelle_id")
    else:
        parcelle_id_final = event.parcelle_id
    parcelle_final = db.get(Parcelle, parcelle_id_final) if parcelle_id_final else None
    valider_evenement(
        db, ctx,
        action=action_final, culture=culture_final,
        variete=variete_final, parcelle=parcelle_final,
        quantite=_to_float(quantite_final),
    )

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
    require_role(ctx, "editor", "supprimer un événement")
    event = db.get(Evenement, evenement_id)
    if event is None or event.potager_id != ctx.potager_id:
        return False
    db.delete(event)
    db.commit()
    log.info(f"🗑 SUPPRESSION     : id={evenement_id}")
    return True


def cycle_vie_culture(
    db: Session,
    ctx: TenantContext,
    culture: str,
    variete: Optional[str],
    semis_id: Optional[int] = None,
    sans_semis_rattache: bool = False,
) -> dict:
    """[GET /godets/detail] Cycle de vie complet semis → godets → plantations → ventes/pertes
    pour une (culture, variété).

    [US-065 / CA6] Le détail peut désormais être demandé pour UN LOT PRÉCIS et non
    plus seulement pour un couple culture + variété, afin que le panneau de détail
    de la pépinière puisse cibler le lot affiché :
      - `semis_id` : le lot issu de ce semis (le semis lui-même, les mises en godet
        qui s'y rattachent, et les plantations issues de ces godets) ;
      - `sans_semis_rattache=True` : le lot des mises en godet sans semis parent.
    Sans aucun des deux, le comportement historique (agrégé culture + variété) est
    conservé à l'identique.
    """
    from sqlalchemy.orm import joinedload

    culture_lower = culture.lower()
    pid = ctx.potager_id

    godet_q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "mise_en_godet", Evenement.potager_id == pid)
        .filter(func.lower(Evenement.culture) == culture_lower)
    )
    godet_q = godet_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else godet_q.filter(Evenement.variete.is_(None))
    # [US-065 CA6] Restriction au lot demandé
    if semis_id is not None:
        godet_q = godet_q.filter(Evenement.origine_graines_id == semis_id)
    elif sans_semis_rattache:
        godet_q = godet_q.filter(Evenement.origine_graines_id.is_(None))
    godet_events = godet_q.order_by(Evenement.date.asc()).all()

    godet_ids = {str(g.id) for g in godet_events}

    semis_q = (
        db.query(Evenement)
        .options(joinedload(Evenement.parcelle_rel))
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action == "semis", Evenement.potager_id == pid)
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(or_(Evenement.parcelle_id.is_(None), Parcelle.est_pepiniere.is_(True)))
    )
    if semis_id is not None:
        # [US-065 CA6] Un lot = un semis : l'identifiant lève toute ambiguïté, le
        # filtre sur la variété n'a plus lieu d'être (celui sur la culture reste,
        # par sécurité, si la paire demandée est incohérente).
        semis_q = semis_q.filter(Evenement.id == semis_id)
    elif sans_semis_rattache:
        # Lot sans semis parent : par construction, aucun semis à afficher.
        semis_q = semis_q.filter(Evenement.id.is_(None))
    else:
        semis_q = semis_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else semis_q.filter(Evenement.variete.is_(None))
    semis_events = semis_q.order_by(Evenement.date.asc()).all()

    plantation_candidates = (
        db.query(Evenement)
        .options(joinedload(Evenement.parcelle_rel))
        .filter(Evenement.type_action == "plantation", Evenement.potager_id == pid)
        .filter(func.lower(Evenement.culture) == culture_lower)
        .filter(Evenement.source_evenement_ids.isnot(None))
        .order_by(Evenement.date.asc())
        .all()
    )
    linked_plantations = [
        p for p in plantation_candidates if godet_ids & set(p.source_evenement_ids.split(";"))
    ]

    # [US-065 CA6] Ventes et pertes en godet ne portent aucun chaînage vers un lot
    # (ni origine_graines_id, ni source_evenement_ids) : elles restent donc listées
    # au niveau (culture, variété), même quand un lot précis est demandé.
    vendu_q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "vendu", Evenement.potager_id == pid)
        .filter(func.lower(Evenement.culture) == culture_lower)
    )
    vendu_q = vendu_q.filter(func.lower(Evenement.variete) == variete.lower()) if variete else vendu_q.filter(Evenement.variete.is_(None))
    vendu_events = vendu_q.order_by(Evenement.date.asc()).all()

    perte_q = (
        db.query(Evenement)
        .filter(Evenement.type_action == "perte_godet", Evenement.potager_id == pid)
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
    require_role(ctx, "editor", "déplacer des événements")
    from datetime import date as _date

    # [US-049] Appel de cohérence (CA5/CA7), délibérément neutralisé ici : cette
    # fonction sert PRÉCISÉMENT à établir qu'une culture est désormais localisée sur
    # une nouvelle parcelle (correction manuelle d'une association erronée, US-007).
    # action="plantation" (action source) rend l'appel un no-op assumé — appliquer
    # la règle d'incohérence culture ↔ parcelle rejetterait systématiquement
    # l'opération qu'elle a justement pour but de réaliser. `events` ne contient de
    # toute façon que des événements déjà localisés : la culture existe forcément.
    valider_evenement(db, ctx, action="plantation", culture=culture, variete=variete, parcelle=None)

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
