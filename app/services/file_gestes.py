"""
app/services/file_gestes.py — La file de gestes en attente [US-224]
--------------------------------------------------------------------------------
La PWA lit ; elle n'écrit pas. Les wireframes des épics 9 à 12 en font une règle
constante, et US-196 avait apporté le chaînon manquant sans ouvrir de second
chemin d'écriture : la PWA **prépare** un geste, le compagnon Telegram le
**confirme**, rien n'est écrit avant « Confirmer ».

Le principe était juste, le véhicule ne tenait pas : un laissez-passer à usage
unique, valable quinze minutes, consommé à l'OUVERTURE du lien. Trois façons d'y
perdre un geste préparé — annuler le récapitulatif, laisser filer les 60 s de
confirmation, refermer la conversation — et aucune de le rejouer.

Ce module remplace ce laissez-passer par une **file**. Ce qu'un écran dépose y
reste jusqu'à confirmation ou abandon explicite ; le jardinier la reprend quand
il veut. Cinq verbes, et rien d'autre :

1. **Déposer** (`deposer_geste`) — valider un geste pré-parsé et le ranger dans
   la file du compte, pour trois jours. Aucun événement écrit, aucun stock
   touché : la file n'apparaît ni au Journal, ni dans une statistique (CA1).
2. **Lire** (`lister_en_attente`, `compter_en_attente`, `geste_par_code`) —
   retrouver ce qui attend, sans rien consommer. Un code reste valide tant que
   le geste l'est (CA11).
3. **Sortir** (`confirmer`, `abandonner`, `refuser`) — et eux seuls retirent un
   geste de la file (CA8). « Plus tard », un délai de confirmation dépassé, une
   conversation refermée : le geste est toujours là.
4. **Vérifier** (`verifier_contexte`) — parcelle supprimée, potager quitté, rôle
   devenu lecteur : un geste dont le contexte a disparu est refusé EN CLAIR,
   avec son motif, et retiré (CA12). Jamais d'écriture silencieuse.
5. **Périmer** (`gestes_a_avertir`, `perimer_gestes`, `supprimer_gestes_sortis`)
   — la péremption se compte PAR GESTE, jamais par pile (CA3).

La cadence des relances, elle, vit dans `app/services/relances_file.py` : c'est
un autre sujet, il a ses propres règles d'arrêt, et les mélanger rendrait les
deux illisibles.

⚠️ **RLS.** La policy de migration_v50 tolère le GUC non armé en LECTURE (le bot
cherche un geste avant de savoir de quel potager il relève — c'est justement ce
que la ligne lui apprend) mais l'exige en ÉCRITURE. US-224 fait du bot un
écrivain sur cette table : il passe donc par `_ecriture(potager_id)`, qui arme
`app.potager_id` sur le potager DU GESTE. La policy reste stricte là où elle
protège, et aucune écriture croisée entre potagers n'est possible.
"""
import logging
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, date as _date
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.permissions import require_potager_non_archive, require_role
from app.services import contexte_semis as svc_contexte_semis
from database.db import tenant_scope, SessionLocal
from database.models import Evenement, GesteIntention, Parcelle, Potager
from llm.parseur_deterministe import ORIGINE_DETERMINISTE
from utils.actions import normalize_action
from app.services.evenements import GESTES_SOL

log = logging.getLogger("potager")


# ─────────────────────────────────────────────────────────────────────────────
# [US-196 / CA3] Le code
# -----------------------------------------------------------------------------
# `secrets.token_urlsafe(16)` : 16 octets = 128 bits d'aléa, rendus en 22
# caractères de l'alphabet `A-Za-z0-9_-`. Avec le préfixe, 23 caractères — très
# en deçà des 64 que Telegram accepte dans `?start=`.
#
# Le préfixe est une MINUSCULE, et c'est ce qui le rend réservé sans registre à
# tenir : `liaisons_telegram.code` (US-045) fait exactement 6 caractères d'un
# alphabet majuscule sans caractère ambigu, et `lier_chat_id` met en majuscules
# avant de chercher. Les deux familles ne peuvent pas se confondre, ni
# aujourd'hui ni après un changement de longueur de l'une ou de l'autre.
#
# [US-224 / CA11] Ce code n'est plus à usage unique : il désigne un geste de la
# file et reste valide tant que ce geste l'est.
# ─────────────────────────────────────────────────────────────────────────────
PREFIXE_CODE = "g"
_OCTETS_ALEA = 16
LONGUEUR_MAX_CODE = 64

#: [CA3] Un geste en attente vit trois jours à compter de SON PROPRE dépôt.
#: Trois jours, et pas quinze minutes : on prépare ses gestes devant l'écran,
#: souvent plusieurs à la suite, et on les confirme quand on a les mains libres.
DUREE_VIE_JOURS = 3

#: [CA17] Un dernier message avant la purge, parce qu'il annonce une perte.
DELAI_AVERTISSEMENT_HEURES = 4

#: [CA18] Un geste sorti de la file (confirmé, abandonné, refusé, périmé) reste
#: visible dans l'application le temps d'être vu : l'envoi sortant est
#: best-effort, la notification de purge peut se perdre, et rien ne doit
#: disparaître en silence. Passé ce délai, la ligne part pour de bon.
RETENTION_SORTIS_HEURES = 48

#: [CA3, CA8] Les quatre états d'un geste. Seuls `confirme`, `abandonne` et
#: `perime` le retirent de la file — « Plus tard », un délai de confirmation
#: dépassé ou une relance ignorée le laissent en `en_attente`.
ETAT_EN_ATTENTE = "en_attente"
ETAT_CONFIRME = "confirme"
ETAT_ABANDONNE = "abandonne"
ETAT_PERIME = "perime"
ETATS_SORTIS: tuple[str, ...] = (ETAT_CONFIRME, ETAT_ABANDONNE, ETAT_PERIME)

#: [US-196 / CA2] Les gestes qu'un écran a le droit de préparer — un sous-ensemble
#: strict du référentiel d'actions (US-168), et il le reste. Les gestes introduits
#: plus tard s'ajoutent ici **dans leur propre US**, avec leur gabarit de phrase :
#: levée (US-212), déplacement (US-211), clôture de lot (US-216). Un geste absent
#: de cette liste est refusé même s'il existe dans `ACTION_MAP` : la PWA ne doit
#: pas pouvoir préparer une observation (texte libre) ni un traitement (produit à
#: identifier), que le flux du bot sait mal recevoir pré-rempli.
#:
#: [US-232 / CA7] Les gestes de SOL rejoignent la liste : le bouton « Ajouter »
#: de la carte « Sol et entretien » prépare un paillage, un amendement, un
#: désherbage ou un binage avec la parcelle en contexte. Ils remplissent les
#: deux conditions posées ci-dessus — la grammaire déterministe les reconnaît
#: (« paillage parcelle planche_centrale »), et ils n'ont ni texte libre ni
#: produit à identifier. La liste reste celle du DOMAINE : elle est importée de
#: `evenements.GESTES_SOL`, jamais recopiée.
GESTES_OUVERTS_PWA: tuple[str, ...] = ("semis", "plantation") + GESTES_SOL

#: Écrans reconnus comme origine — champ de MESURE, jamais lu par le flux
#: d'enregistrement. Une valeur inconnue est simplement ignorée, pas refusée :
#: une mesure ne doit pas faire échouer un geste.
ECRANS_CONNUS: tuple[str, ...] = (
    "plan", "stocks", "pepiniere", "journal", "fiche_culture", "dashboard",
)


class ActionNonOuverteError(Exception):
    """[CA2] Action inconnue du référentiel, ou non ouverte à la PWA."""

    def __init__(self, action: Optional[str]):
        self.action = action
        super().__init__(
            f"Le geste « {action or '—'} » ne peut pas être préparé depuis l'application."
        )


class ParcelleHorsPotagerError(Exception):
    """[CA2] Parcelle inexistante, ou appartenant à un autre potager."""

    def __init__(self, parcelle_id: Optional[int]):
        self.parcelle_id = parcelle_id
        super().__init__("Cette parcelle n'appartient pas au potager consulté.")


class LotHorsPotagerError(Exception):
    """[CA2] Lot de pépinière inexistant, ou appartenant à un autre potager."""

    def __init__(self, lot_id: Optional[int]):
        self.lot_id = lot_id
        super().__init__("Ce lot n'appartient pas au potager consulté.")


class CodeIntrouvableError(Exception):
    """[CA11] Code inconnu — jamais déposé, ou tronqué à la copie."""


class GestePerimeError(Exception):
    """[CA3] Le geste désigné a dépassé ses trois jours."""


class GesteDejaTraiteError(Exception):
    """[CA8] Le geste a été confirmé, abandonné ou refusé — il n'attend plus."""


class GesteAutreCompteError(Exception):
    """[CA12] Le lien est ouvert dans une conversation liée à un autre compte."""


@dataclass(frozen=True)
class Depot:
    """Ce qu'un dépôt apprend à son appelant — et rien de plus.

    `doublon` et `file_etait_vide` ne sont PAS des états du geste : ce sont deux
    constats faits au moment du dépôt, que l'API restitue à l'écran (CA4) et à
    la relance (CA14). Les relire plus tard n'aurait aucun sens.
    """
    geste: GesteIntention
    doublon: bool
    file_etait_vide: bool
    nb_en_attente: int


# ══════════════════════════════════════════════════════════════════════════════
# Écrire sous RLS
# ══════════════════════════════════════════════════════════════════════════════
@contextmanager
def _ecriture(potager_id: int) -> Iterator[Session]:
    """Session armée sur le potager DU GESTE, pour une mise à jour de la file.

    C'est ce qui permet de garder le `WITH CHECK` de migration_v50 strict tout
    en laissant le bot écrire : il ne connaît pas le potager au moment où il
    cherche le geste, il le connaît au moment où il le met à jour.
    """
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


@contextmanager
def lecture_hors_tenant() -> Iterator[Session]:
    """Session GUC RLS DÉSARMÉ, pour les lectures du bot [US-196].

    ⚠️ Le seul endroit du projet, avec `liaison_telegram`, qui le fait. Le bot
    lit la file d'un COMPTE — qui peut couvrir plusieurs potagers (CA13) — alors
    qu'il a déjà armé `app.potager_id` sur le potager par défaut au dispatch de
    l'Update. La policy de migration_v50 tolère le GUC non armé en lecture pour
    ce seul cas ; l'isolation est alors portée par le filtre `user_id` et, pour
    un accès par code, par les 128 bits de ce code. Tout chemin qui a un
    contexte tenant — l'API — reste strictement isolé.
    """
    with tenant_scope(None):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


# ══════════════════════════════════════════════════════════════════════════════
# Déposer
# ══════════════════════════════════════════════════════════════════════════════
def _generer_code(db: Session) -> str:
    code = PREFIXE_CODE + secrets.token_urlsafe(_OCTETS_ALEA)
    while db.query(GesteIntention).filter(GesteIntention.code == code).first() is not None:
        code = PREFIXE_CODE + secrets.token_urlsafe(_OCTETS_ALEA)
    return code


def date_enregistrable(date_demandee: Optional[str], aujourd_hui: Optional[_date] = None) -> str:
    """[CA26] Un geste ne se date jamais dans le futur — AU MOMENT DU DÉPÔT.

    La date de référence d'un écran peut l'être — on consulte volontiers le
    plan « dans trois semaines ». Le geste, lui, décrit ce que le jardinier
    vient de faire : une date à venir est ramenée au jour du dépôt. La PWA
    applique la même règle pour pouvoir le DIRE sur le bouton ; celle-ci est le
    garde-fou serveur, pour que la règle tienne quel que soit l'appelant.

    ⚠️ Cette règle s'applique au DÉPÔT, et à lui seul. Un geste confirmé trois
    jours plus tard garde la date de son dépôt (CA25) : c'est le jour où le
    jardinier a agi au potager, pas celui où il a eu les mains libres pour le
    dire. Une file *asynchrone*, donc, et pas une file *programmée* — la
    programmation d'un geste à venir suppose une notion de « prévu » distincte
    de « fait », qui touche le stock, le plan et les statistiques, et relève
    d'une autre US (arbitrage CA26).
    """
    jour = aujourd_hui or _date.today()
    if not date_demandee:
        return jour.isoformat()
    try:
        demandee = _date.fromisoformat(str(date_demandee)[:10])
    except ValueError:
        return jour.isoformat()
    if demandee > jour:
        log.info(
            "[US-224 / CA26] Date à venir ramenée au jour du dépôt : %s → %s",
            demandee.isoformat(), jour.isoformat(),
        )
        return jour.isoformat()
    return demandee.isoformat()


def _valider_parcelle(db: Session, ctx: TenantContext, parcelle_id: Optional[int]) -> Optional[str]:
    """[CA2] Résout l'identifiant en NOM de parcelle, dans le potager consulté.

    Le nom, et pas l'identifiant : le flux du bot ne connaît que des noms — il
    les re-résout lui-même à la confirmation (`saisie._parse_and_save`), ce qui
    garde une seule règle de résolution dans le projet, celle d'US-006. C'est
    aussi ce qui rend `verifier_contexte` possible : une parcelle supprimée
    entre le dépôt et la confirmation ne se résout plus, et le geste est refusé
    en clair plutôt qu'enregistré ailleurs (CA12).
    """
    if parcelle_id is None:
        return None
    parcelle = (
        db.query(Parcelle)
        .filter(Parcelle.id == int(parcelle_id), Parcelle.potager_id == ctx.potager_id)
        .first()
    )
    if parcelle is None:
        log.warning(
            "[US-224 / CA2] Parcelle refusée : id=%s hors du potager %s",
            parcelle_id, ctx.potager_id,
        )
        raise ParcelleHorsPotagerError(parcelle_id)
    return parcelle.nom


def _valider_lot(db: Session, ctx: TenantContext, lot_id: Optional[int]) -> Optional[int]:
    """[CA2] Un lot de pépinière est un événement de semis du potager consulté.

    Rien n'en est fait ici : aucun geste ouvert à la PWA à ce stade ne porte sur
    un lot (ils arrivent avec US-216/US-217). La validation existe quand même,
    pour que le jour où un écran enverra `lot`, il traverse déjà le même contrôle
    d'appartenance que la parcelle.
    """
    if lot_id is None:
        return None
    lot = (
        db.query(Evenement)
        .filter(Evenement.id == int(lot_id), Evenement.potager_id == ctx.potager_id)
        .first()
    )
    if lot is None:
        log.warning(
            "[US-224 / CA2] Lot refusé : id=%s hors du potager %s", lot_id, ctx.potager_id,
        )
        raise LotHorsPotagerError(lot_id)
    return lot.id


def construire_item(
    *,
    action: str,
    culture: Optional[str] = None,
    variete: Optional[str] = None,
    quantite: Optional[float] = None,
    unite: Optional[str] = None,
    parcelle: Optional[str] = None,
    rang: Optional[str] = None,
    date: Optional[str] = None,
    contexte_semis: Optional[str] = None,
) -> dict:
    """[CA2] L'item pré-parsé, au contrat de `llm.parseur_deterministe`.

    Exactement la forme que `commandes_confiance._enregistrer_le_geste` compose
    déjà pour le bouton d'US-179 — tous les champs présents, `None` compris,
    parce que c'est ce que `_normalize_items` attend. `origine_parsing` dit d'où
    il vient : déterministe, donc zéro jeton.
    """
    item: dict = {
        "action": action,
        "culture": culture,
        "variete": variete,
        "quantite": quantite,
        "unite": unite,
        "parcelle": parcelle,
        "rang": rang,
        "duree_minutes": None,
        "traitement": None,
        "date": date,
        "commentaire": None,
        "nb_graines_semees": None,
        "nb_plants_godets": None,
        "origine_parsing": ORIGINE_DETERMINISTE,
    }
    if contexte_semis is not None:
        item["contexte_semis"] = contexte_semis
    return item


def _meme_geste(item_a: dict, item_b: dict) -> bool:
    """[CA4] Même action, même culture, même parcelle, même jour.

    Les quatre champs de la définition de l'US, et pas un de plus : la variété
    ou la quantité distinguent deux gestes qu'on veut justement voir signalés
    comme identiques (« j'ai déjà déposé ce semis, avec une autre quantité ? »).
    """
    def _cle(item: dict) -> tuple:
        return (
            normalize_action(item.get("action")),
            (item.get("culture") or "").strip().lower() or None,
            (item.get("parcelle") or "").strip().lower() or None,
            item.get("date"),
        )
    return _cle(item_a) == _cle(item_b)


def deposer_geste(
    db: Session,
    ctx: TenantContext,
    *,
    action: Optional[str],
    culture: Optional[str] = None,
    variete: Optional[str] = None,
    quantite: Optional[float] = None,
    unite: Optional[str] = None,
    parcelle_id: Optional[int] = None,
    rang: Optional[str] = None,
    lot_id: Optional[int] = None,
    date: Optional[str] = None,
    contexte_semis: Optional[str] = None,
    ecran: Optional[str] = None,
    aujourd_hui: Optional[_date] = None,
    maintenant: Optional[datetime] = None,
) -> Depot:
    """[CA1, CA2, CA3, CA4] Dépose un geste dans la file, sans rien écrire d'autre.

    Le dépôt n'écrit aucun événement : la file n'apparaît ni au Journal, ni dans
    un stock, ni dans une statistique (CA1). Il ne dépend PAS d'un compagnon
    activé (CA21) : on prépare sa journée d'abord, on active une fois.

    Lève `PermissionInsuffisanteError` (lecteur), `ActionNonOuverteError`,
    `ParcelleHorsPotagerError` ou `LotHorsPotagerError` — aucune de ces erreurs
    ne laisse la moindre trace en base.
    """
    # [CA24] Garde de rôle d'abord : un lecteur ne dépose rien, pas même un
    # geste en attente. Même garde et même message que le bot (US-047). Un
    # potager archivé est refusé ici aussi : déposer un geste que la
    # confirmation rejettera à coup sûr ferait attendre pour rien (US-083).
    require_role(ctx, "editor", "enregistrer d'action")
    require_potager_non_archive(db, ctx, "enregistrer d'action")

    geste = normalize_action(action)
    if geste is None or geste not in GESTES_OUVERTS_PWA:
        log.warning("[US-224 / CA2] Geste refusé : %r (normalisé : %r)", action, geste)
        raise ActionNonOuverteError(action)

    parcelle_nom = _valider_parcelle(db, ctx, parcelle_id)
    lot = _valider_lot(db, ctx, lot_id)
    filiere = svc_contexte_semis.normaliser_contexte(contexte_semis) if geste == "semis" else None

    item = construire_item(
        action=geste, culture=culture, variete=variete, quantite=quantite,
        unite=unite, parcelle=parcelle_nom, rang=rang,
        date=date_enregistrable(date, aujourd_hui), contexte_semis=filiere,
    )
    if lot is not None:
        # Hors contrat du parseur : rangé à part pour que `_parse_and_save` ne
        # reçoive jamais un champ qu'il ne connaît pas (cf. `item_du_geste`).
        item["_lot_id"] = lot

    instant = maintenant or datetime.utcnow()

    # [CA18] La purge des lignes SORTIES vit ici plutôt que dans une tâche
    # planifiée : la table ne grossit que quand on la sollicite. Les gestes
    # PÉRIMÉS, eux, ne sont pas touchés ici — c'est le job qui les annonce
    # avant de les retirer, et le silence est précisément ce que le CA18
    # interdit.
    supprimer_gestes_sortis(db, maintenant=instant)

    en_attente = lister_en_attente(db, ctx.user_id, maintenant=instant)
    doublon = any(_meme_geste(item, existant.geste or {}) for existant in en_attente)
    if doublon:
        # [CA4] Signalé, pas interdit : semer deux fois la même chose le même
        # jour est un cas réel, et un écran qui refuserait le second dépôt
        # obligerait à passer par le bot — le détour que l'US supprime.
        log.info(
            "[US-224 / CA4] Doublon signalé : user_id=%s geste=%s culture=%s",
            ctx.user_id, item["action"], item.get("culture"),
        )

    intention = GesteIntention(
        code=_generer_code(db),
        user_id=ctx.user_id,
        potager_id=ctx.potager_id,
        geste=item,
        ecran=ecran if ecran in ECRANS_CONNUS else None,
        cree_le=instant,
        # [CA3] Trois jours à compter de CE dépôt. Jamais l'échéance de la pile.
        expire_le=instant + timedelta(days=DUREE_VIE_JOURS),
        etat=ETAT_EN_ATTENTE,
    )
    db.add(intention)
    db.commit()
    db.refresh(intention)
    # Jamais le code lui-même dans les journaux (point de vigilance de l'US) —
    # l'identifiant de ligne suffit à retracer un dépôt.
    log.info(
        "[US-224 / CA1] Geste déposé : id=%s user_id=%s potager_id=%s geste=%s écran=%s "
        "(file : %s en attente)",
        intention.id, ctx.user_id, ctx.potager_id, item["action"], intention.ecran,
        len(en_attente) + 1,
    )
    return Depot(
        geste=intention,
        doublon=doublon,
        # [CA14] Une invitation part au PREMIER dépôt sur une file vide, et une
        # seule : les gestes déposés à la suite pendant la même session de
        # préparation n'en déclenchent aucune autre.
        file_etait_vide=not en_attente,
        nb_en_attente=len(en_attente) + 1,
    )


# ══════════════════════════════════════════════════════════════════════════════
# Lire
# ══════════════════════════════════════════════════════════════════════════════
def _requete_en_attente(db: Session, user_id: int, maintenant: datetime):
    return (
        db.query(GesteIntention)
        .filter(
            GesteIntention.user_id == user_id,
            GesteIntention.etat == ETAT_EN_ATTENTE,
            GesteIntention.expire_le > maintenant,
        )
        .order_by(GesteIntention.cree_le.asc(), GesteIntention.id.asc())
    )


def lister_en_attente(
    db: Session,
    user_id: int,
    potager_id: Optional[int] = None,
    maintenant: Optional[datetime] = None,
) -> list[GesteIntention]:
    """[CA5, CA13] Les gestes qui attendent, du plus ancien au plus récent.

    Tous potagers confondus par défaut : la file est celle d'un COMPTE, et le
    niveau 1 de la présentation les groupe par potager quand il y en a
    plusieurs. Un geste périmé n'en fait plus partie, même s'il n'a pas encore
    été purgé — la péremption se compte par geste (CA3).
    """
    requete = _requete_en_attente(db, user_id, maintenant or datetime.utcnow())
    if potager_id is not None:
        requete = requete.filter(GesteIntention.potager_id == potager_id)
    return requete.all()


def compter_en_attente(
    db: Session, user_id: int, potager_id: Optional[int] = None,
    maintenant: Optional[datetime] = None,
) -> int:
    """[CA22] Combien de gestes attendent — le chiffre que l'application montre.

    En permanence et sur tous les écrans concernés : une file invisible serait
    une file oubliée.
    """
    requete = _requete_en_attente(db, user_id, maintenant or datetime.utcnow())
    if potager_id is not None:
        requete = requete.filter(GesteIntention.potager_id == potager_id)
    return requete.count()


def lister_sortis_recents(
    db: Session, user_id: int, maintenant: Optional[datetime] = None,
) -> list[GesteIntention]:
    """[CA18] Ce qui a quitté la file récemment, et ce que c'était.

    L'envoi sortant du compagnon est best-effort : il n'échoue jamais
    bruyamment, un message perdu l'est sans bruit. Acceptable pour une relance
    — il y en aura une autre — mais pas pour la notification de purge, qui n'a
    pas de seconde chance. L'information est donc portée AUSSI par
    l'application : un geste purgé y reste visible comme tel, le temps d'être
    vu, puis `supprimer_gestes_sortis` le retire.
    """
    instant = maintenant or datetime.utcnow()
    return (
        db.query(GesteIntention)
        .filter(
            GesteIntention.user_id == user_id,
            GesteIntention.etat.in_(ETATS_SORTIS),
            GesteIntention.traite_le.isnot(None),
            GesteIntention.traite_le > instant - timedelta(hours=RETENTION_SORTIS_HEURES),
        )
        .order_by(GesteIntention.traite_le.desc())
        .all()
    )


def comptes_avec_file(db: Session, maintenant: Optional[datetime] = None) -> list[int]:
    """[CA15] Les comptes dont la file n'est pas vide — ceux qu'on peut relancer.

    Balayage par état plutôt que par jointure sur `users` : la relance est une
    conséquence de la file, pas une propriété du compte, et un compte sans
    geste en attente n'a aucune raison d'être visité.
    """
    instant = maintenant or datetime.utcnow()
    lignes = (
        db.query(GesteIntention.user_id)
        .filter(
            GesteIntention.etat == ETAT_EN_ATTENTE,
            GesteIntention.expire_le > instant,
        )
        .distinct()
        .all()
    )
    return [ligne[0] for ligne in lignes]


def par_potager(gestes: list[GesteIntention]) -> dict[int, list[GesteIntention]]:
    """[CA13] Quand la file couvre plusieurs potagers, le niveau 1 les groupe."""
    groupes: dict[int, list[GesteIntention]] = {}
    for geste in gestes:
        groupes.setdefault(geste.potager_id, []).append(geste)
    return groupes


def est_code_geste(payload: Optional[str]) -> bool:
    """[US-196] Ce payload de `/start` est-il un code de geste ?

    Le préfixe seul décide — un code de liaison (US-045) garde intégralement
    son traitement, y compris quand il est inconnu : ce test ne doit jamais
    détourner un code qui ne nous appartient pas.
    """
    if not payload:
        return False
    candidat = payload.strip()
    return (
        candidat.startswith(PREFIXE_CODE)
        and len(candidat) > len(PREFIXE_CODE)
        and len(candidat) <= LONGUEUR_MAX_CODE
    )


def geste_par_code(
    db: Session, code: str, user_id: Optional[int],
    maintenant: Optional[datetime] = None,
) -> GesteIntention:
    """[CA11] Le geste que ce lien désigne — sans le consommer.

    C'est la différence de fond avec `consommer_intention` d'US-196 : ouvrir le
    lien ne retire rien de la file, et le rouvrir répond la même chose. Le lien
    reste valide tant que le geste l'est.

    Lève `CodeIntrouvableError`, `GesteAutreCompteError`, `GesteDejaTraiteError`
    ou `GestePerimeError` — quatre refus, tous motivés (CA12).
    """
    instant = maintenant or datetime.utcnow()
    geste = db.query(GesteIntention).filter(GesteIntention.code == code.strip()).first()
    if geste is None:
        log.info("[US-224 / CA11] Code de geste inconnu")
        raise CodeIntrouvableError("Code de geste inconnu")

    if user_id is None or geste.user_id != user_id:
        # Ni le geste, ni la culture, ni le potager ne seront nommés à
        # l'appelant : cette conversation n'a pas à apprendre ce que préparait
        # quelqu'un d'autre. Et rien n'est marqué : le geste appartient à son
        # propriétaire, un lien qui a fuité ne le lui retire pas.
        log.warning(
            "[US-224 / CA12] Geste ouvert par un autre compte : "
            "id=%s déposé par user_id=%s, ouvert par user_id=%s",
            geste.id, geste.user_id, user_id,
        )
        raise GesteAutreCompteError("Ce geste a été déposé par un autre compte")

    if geste.etat != ETAT_EN_ATTENTE:
        log.info("[US-224 / CA8] Geste déjà sorti de la file : id=%s état=%s", geste.id, geste.etat)
        raise GesteDejaTraiteError(geste.etat)

    if geste.expire_le <= instant:
        log.info("[US-224 / CA3] Geste périmé : id=%s", geste.id)
        raise GestePerimeError("Ce geste a dépassé ses trois jours")

    return geste


def geste_par_id(
    db: Session, geste_id: int, user_id: int, maintenant: Optional[datetime] = None,
) -> Optional[GesteIntention]:
    """Le geste en attente d'identifiant donné, pour ce compte — ou `None`.

    Le filtre `user_id` n'est pas décoratif : c'est lui qui tient l'isolation
    quand la lecture se fait GUC désarmé (voir `lecture_hors_tenant`).
    """
    instant = maintenant or datetime.utcnow()
    return (
        db.query(GesteIntention)
        .filter(
            GesteIntention.id == int(geste_id),
            GesteIntention.user_id == user_id,
            GesteIntention.etat == ETAT_EN_ATTENTE,
            GesteIntention.expire_le > instant,
        )
        .first()
    )


def item_du_geste(geste: GesteIntention) -> dict:
    """L'item tel que `saisie._parse_and_save` l'attend — sans les champs internes.

    `_lot_id` est stocké avec le geste mais n'appartient pas au contrat du
    parseur : il est retiré ici, à l'unique frontière où l'item repasse dans le
    flux d'enregistrement.
    """
    return {k: v for k, v in (geste.geste or {}).items() if not k.startswith("_")}


# ══════════════════════════════════════════════════════════════════════════════
# Sortir de la file
# ══════════════════════════════════════════════════════════════════════════════
def _sortir(
    geste_id: int, potager_id: int, etat: str, motif: Optional[str] = None,
    maintenant: Optional[datetime] = None,
) -> bool:
    """Retire un geste de la file, sous le potager qui est le sien.

    Idempotent : un geste déjà sorti n'est pas re-sorti, et la fonction rend
    `False` — deux clics sur « Confirmer » ne produisent pas deux événements.
    """
    instant = maintenant or datetime.utcnow()
    with _ecriture(potager_id) as db:
        geste = (
            db.query(GesteIntention)
            .filter(
                GesteIntention.id == int(geste_id),
                GesteIntention.etat == ETAT_EN_ATTENTE,
            )
            .first()
        )
        if geste is None:
            return False
        geste.etat = etat
        geste.traite_le = instant
        if motif:
            geste.motif_refus = motif[:200]
        db.commit()
        log.info("[US-224 / CA8] Geste sorti de la file : id=%s état=%s", geste_id, etat)
        return True


def confirmer(geste: GesteIntention, maintenant: Optional[datetime] = None) -> bool:
    """[CA7] *Confirmer* — enregistre et retire de la file.

    Appelée APRÈS l'écriture de l'événement, jamais avant : si l'enregistrement
    échoue, le geste doit rester en attente plutôt que disparaître sans trace.
    """
    return _sortir(geste.id, geste.potager_id, ETAT_CONFIRME, maintenant=maintenant)


def abandonner(geste: GesteIntention, maintenant: Optional[datetime] = None) -> bool:
    """[CA7, CA23] *Abandonner ce geste* — le retire définitivement, et le dit.

    Le libellé « Annuler » d'US-196 disparaît de ce flux : il ne permettait pas
    de distinguer « j'annule la confirmation » de « j'annule le geste », et
    c'est cette confusion qui faisait perdre des gestes préparés.
    """
    return _sortir(geste.id, geste.potager_id, ETAT_ABANDONNE, maintenant=maintenant)


def refuser(geste: GesteIntention, motif: str, maintenant: Optional[datetime] = None) -> bool:
    """[CA12] Le contexte a disparu — refusé en clair, avec son motif, et retiré.

    Jamais d'écriture silencieuse, jamais un geste fantôme qui échoue à chaque
    reprise de la file.
    """
    return _sortir(geste.id, geste.potager_id, ETAT_ABANDONNE, motif=motif, maintenant=maintenant)


# ══════════════════════════════════════════════════════════════════════════════
# [CA12] Le contexte a-t-il tenu depuis le dépôt ?
# ══════════════════════════════════════════════════════════════════════════════
def verifier_contexte(db: Session, geste: GesteIntention, user_id: int) -> Optional[str]:
    """Le motif de refus de ce geste, ou `None` s'il peut être joué.

    Quatre façons pour un contexte de disparaître entre le dépôt et la
    confirmation, et une phrase pour chacune — jamais un « erreur » sec qui
    laisserait le jardinier sans savoir quoi refaire :

    * le potager a été archivé ou supprimé ;
    * le compte n'en est plus membre ;
    * son rôle y est devenu lecteur ;
    * la parcelle (ou le lot) citée par le geste n'existe plus.

    La lecture se fait sur la session fournie : l'appelant sait s'il a un
    contexte tenant (l'API) ou non (le bot).
    """
    from app.services import potager_actif as svc_potager_actif

    potager = db.query(Potager).filter(Potager.id == geste.potager_id).first()
    if potager is None:
        return "le potager de ce geste n'existe plus"
    if getattr(potager, "etat", None) and potager.etat != "actif":
        return f"le potager « {potager.nom} » est archivé (lecture seule)"

    role = svc_potager_actif.role_utilisateur(db, user_id, geste.potager_id)
    if role is None:
        return f"vous n'êtes plus membre du potager « {potager.nom} »"
    if role not in ("owner", "editor"):
        return f"votre rôle sur « {potager.nom} » est devenu lecteur"

    item = geste.geste or {}
    nom_parcelle = (item.get("parcelle") or "").strip()
    if nom_parcelle:
        from utils.parcelles import resolve_parcelle
        if resolve_parcelle(db, nom_parcelle, potager_id=geste.potager_id) is None:
            return f"la parcelle « {nom_parcelle} » n'existe plus"

    lot_id = item.get("_lot_id")
    if lot_id is not None:
        lot = (
            db.query(Evenement)
            .filter(Evenement.id == int(lot_id), Evenement.potager_id == geste.potager_id)
            .first()
        )
        if lot is None:
            return "le lot de pépinière de ce geste n'existe plus"

    return None


# ══════════════════════════════════════════════════════════════════════════════
# [CA3, CA17, CA18] Périmer
# ══════════════════════════════════════════════════════════════════════════════
def gestes_a_avertir(db: Session, maintenant: Optional[datetime] = None) -> list[GesteIntention]:
    """[CA17] Les gestes dont la purge tombe dans moins de quatre heures.

    Un seul avertissement par geste (`avertissement_le`), et par geste et non
    par pile : deux gestes déposés à deux jours d'écart ont deux échéances.
    """
    instant = maintenant or datetime.utcnow()
    return (
        db.query(GesteIntention)
        .filter(
            GesteIntention.etat == ETAT_EN_ATTENTE,
            GesteIntention.avertissement_le.is_(None),
            GesteIntention.expire_le > instant,
            GesteIntention.expire_le <= instant + timedelta(hours=DELAI_AVERTISSEMENT_HEURES),
        )
        .order_by(GesteIntention.expire_le.asc())
        .all()
    )


def marquer_averti(geste: GesteIntention, maintenant: Optional[datetime] = None) -> None:
    """[CA17] L'avertissement est parti — il ne repartira pas pour ce geste."""
    instant = maintenant or datetime.utcnow()
    with _ecriture(geste.potager_id) as db:
        ligne = db.query(GesteIntention).filter(GesteIntention.id == geste.id).first()
        if ligne is not None and ligne.avertissement_le is None:
            ligne.avertissement_le = instant
            db.commit()


def gestes_perimes(db: Session, maintenant: Optional[datetime] = None) -> list[GesteIntention]:
    """[CA3] Les gestes en attente dont les trois jours sont écoulés."""
    instant = maintenant or datetime.utcnow()
    return (
        db.query(GesteIntention)
        .filter(
            GesteIntention.etat == ETAT_EN_ATTENTE,
            GesteIntention.expire_le <= instant,
        )
        .order_by(GesteIntention.user_id.asc(), GesteIntention.expire_le.asc())
        .all()
    )


def perimer(geste: GesteIntention, maintenant: Optional[datetime] = None) -> bool:
    """[CA3, CA18] Marque un geste périmé — sans le supprimer tout de suite.

    La ligne survit `RETENTION_SORTIS_HEURES` : c'est elle que l'application
    montre pour dire ce qui a été vidé, quand la notification du CA18 s'est
    perdue en chemin.
    """
    return _sortir(
        geste.id, geste.potager_id, ETAT_PERIME,
        motif="jamais confirmé dans les trois jours", maintenant=maintenant,
    )


def supprimer_gestes_sortis(db: Session, maintenant: Optional[datetime] = None) -> int:
    """[CA18] Efface les gestes sortis de la file depuis assez longtemps.

    Vit dans le chemin du dépôt plutôt que dans une tâche planifiée : la table
    ne grossit que quand on la sollicite, et un geste sorti depuis deux jours
    n'apprend plus rien à personne.
    """
    instant = maintenant or datetime.utcnow()
    limite = instant - timedelta(hours=RETENTION_SORTIS_HEURES)
    nb = (
        db.query(GesteIntention)
        .filter(
            GesteIntention.etat.in_(ETATS_SORTIS),
            GesteIntention.traite_le.isnot(None),
            GesteIntention.traite_le < limite,
        )
        .delete(synchronize_session=False)
    )
    if nb:
        db.commit()
        log.info("[US-224 / CA18] %s geste(s) sorti(s) effacé(s) après rétention", nb)
    return nb


def acquitter_sortis(db: Session, user_id: int) -> int:
    """[CA18] Le jardinier a vu ce qui avait été vidé — la trace peut partir.

    Appelée depuis l'application, jamais depuis le bot : c'est l'écran qui sait
    que l'information a été lue.
    """
    nb = (
        db.query(GesteIntention)
        .filter(
            GesteIntention.user_id == user_id,
            GesteIntention.etat.in_(ETATS_SORTIS),
        )
        .delete(synchronize_session=False)
    )
    if nb:
        db.commit()
        log.info("[US-224 / CA18] %s geste(s) sorti(s) acquitté(s) par user_id=%s", nb, user_id)
    return nb


# ══════════════════════════════════════════════════════════════════════════════
# [US-196 / CA9] La phrase équivalente à dicter, et le lien
# ══════════════════════════════════════════════════════════════════════════════
def phrase_a_dicter(item: dict) -> str:
    """« semis de tomate en pépinière parcelle carré nord ».

    Deux exigences, tenues par construction plutôt que par relecture :

    * la phrase doit être reconnue par `llm.parseur_deterministe` **sans appel
      au modèle** — d'où l'ordre geste / culture / filière / parcelle, qui est
      celui de sa grammaire, et l'absence de tout vocabulaire de rangs, qu'elle
      renvoie délibérément au modèle ;
    * elle ne porte **pas de date**. La grammaire présume « aujourd'hui » sans
      ancrage, et c'est exactement ce que veut dire le jardinier qui la dicte
      maintenant. Écrire une date que la grammaire lirait mal ferait retomber la
      phrase sur le modèle — le contraire du but.

    C'est un repli, pas un double du geste : le bouton reste le chemin normal.
    """
    geste = item.get("action") or ""
    morceaux: list[str] = [geste]
    culture = (item.get("culture") or "").strip()
    if culture:
        morceaux.append(f"de {culture.lower()}")
    filiere = item.get("contexte_semis")
    if geste == "semis" and filiere in svc_contexte_semis.LIBELLES_CONTEXTES:
        morceaux.append(f"en {svc_contexte_semis.LIBELLES_CONTEXTES[filiere]}")
    parcelle = (item.get("parcelle") or "").strip()
    if parcelle:
        morceaux.append(f"parcelle {parcelle.lower()}")
    return " ".join(morceaux)


def libelle_court(geste: GesteIntention) -> str:
    """[CA5] Une ligne de file : geste, culture, parcelle, date.

    Quatre champs, ceux que le CA5 nomme — assez pour reconnaître son geste
    dans une liste, pas assez pour croire l'avoir déjà enregistré.
    """
    item = geste.geste or {}
    morceaux = [str(item.get("action") or "geste")]
    if item.get("culture"):
        morceaux.append(str(item["culture"]))
    if item.get("parcelle"):
        morceaux.append(f"— {item['parcelle']}")
    if item.get("date"):
        morceaux.append(f"({item['date']})")
    return " ".join(morceaux)


def lien_profond(code: str, bot_username: Optional[str]) -> Optional[str]:
    """[CA11] `https://t.me/<bot>?start=<code>` — le lien ne transporte QUE le code.

    `None` quand l'identifiant public du bot est introuvable (même repli que
    `GET /auth/me`, US-091) : la PWA propose alors la seule phrase à dicter,
    plutôt qu'un lien cassé.
    """
    if not bot_username:
        return None
    return f"https://t.me/{bot_username.lstrip('@')}?start={code}"
