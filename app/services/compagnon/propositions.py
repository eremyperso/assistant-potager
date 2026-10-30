"""
app/services/compagnon/propositions.py — Les propositions en base, communes aux canaux [US-259]
================================================================================================
Ce que le compagnon propose et qui attend la réponse du jardinier vit ICI, en
base, et nulle part ailleurs : plus de `_INTERP_PENDING` dans le bot. Une
proposition survit donc à un redémarrage (CA8), et Telegram comme la PWA n'en
sont que deux fenêtres (cadrage §4.7).

Une seule table pour trois natures (CA6) :

* `geste`    — un geste préparé par la PWA, la file d'US-224, lue et relancée par
               `app.services.file_gestes` et `app.services.relances_file` ;
* `commande` — une commande proposée en conversation, ses boutons la nomment par
               son `code` (US-234) ;
* `plan`     — plusieurs commandes confirmées en une fois (US-237).

Ce module est la seule référence de ce qui leur est commun :

* les ÉTATS (CA2) — en_attente, confirmee, abandonnee, perimee, remplacee ;
* la SORTIE de l'attente, ATOMIQUE (CA3) : un `UPDATE … WHERE etat =
  'en_attente'`, dont seul le premier appel modifie une ligne. Deux
  confirmations simultanées, deux clics, un clic dans la PWA et un autre dans
  Telegram : une seule exécution ;
* la DURÉE DE VIE (CA5) — 30 min en conversation, la durée de la file (3 jours)
  une fois notifiée ;
* le POTAGER (CA4) — une proposition porte le sien ; elle se met à jour sous ce
  potager-là (`session_sur`), quel que soit le potager actif du canal.

⚠️ RLS : la policy de `propositions` (migration_v50, renommée par v61) tolère le
GUC non armé en LECTURE, et c'est ce qui permet au bot de retrouver une
proposition par son code avant de savoir de quel potager elle relève. L'écriture
exige le GUC : elle se fait sous le potager DE LA PROPOSITION.
"""
from __future__ import annotations

import logging
import secrets
from contextlib import contextmanager
from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime, timedelta, timezone
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.db import SessionLocal, tenant_scope
from database.models import Proposition

log = logging.getLogger("potager")

NATURE_GESTE = "geste"
NATURE_COMMANDE = "commande"
NATURE_PLAN = "plan"
NATURES: tuple[str, ...] = (NATURE_GESTE, NATURE_COMMANDE, NATURE_PLAN)
#: Les natures nées d'une phrase, que la conversation peut corriger ou remplacer.
NATURES_CONVERSATION: tuple[str, ...] = (NATURE_COMMANDE, NATURE_PLAN)

#: [CA2] Seul `en_attente` attend encore une réponse ; les quatre autres sont des sorties.
ETAT_EN_ATTENTE = "en_attente"
ETAT_CONFIRMEE = "confirmee"
ETAT_ABANDONNEE = "abandonnee"
ETAT_PERIMEE = "perimee"
ETAT_REMPLACEE = "remplacee"
ETATS_SORTIS: tuple[str, ...] = (ETAT_CONFIRMEE, ETAT_ABANDONNEE, ETAT_PERIMEE, ETAT_REMPLACEE)

CANAL_TELEGRAM = "telegram"
CANAL_PWA = "pwa"

#: [CA5] Une proposition faite en conversation vit 30 minutes…
DUREE_CONVERSATION = timedelta(minutes=30)
#: … une proposition NOTIFIÉE prend la durée de la file d'US-224 (F4).
DUREE_NOTIFIEE_JOURS = 3
DUREE_NOTIFIEE = timedelta(days=DUREE_NOTIFIEE_JOURS)
#: Une proposition de conversation sortie de l'attente reste lisible un mois, comme
#: les échanges qui la citent, puis part.
RETENTION_CONVERSATION_JOURS = 30

#: Préfixe d'un code de conversation : `g` est celui des gestes (US-196), qu'un
#: lien `?start=` reconnaît ; les deux familles ne se confondent jamais.
PREFIXE_CODE = "p"
_OCTETS_ALEA = 9  # 12 caractères : `interp:cand:<rang>:<code>` tient dans les 64 de Telegram


def expiration(cree_le: datetime, notifiee: bool) -> datetime:
    """[CA5] L'échéance d'une proposition, selon qu'elle a été notifiée ou non."""
    return cree_le + (DUREE_NOTIFIEE if notifiee else DUREE_CONVERSATION)


@contextmanager
def session_sur(potager_id: Optional[int]) -> Iterator[Session]:
    """Session armée sur `potager_id` — celui DE LA PROPOSITION pour toute écriture.

    `None` désarme le GUC : la lecture par code du bot, qui ne sait pas encore
    de quel potager relève le bouton cliqué (voir l'en-tête).
    """
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


# ═════════════════════════════════════════════════════════════════════════════
# [CA3] Sortir de l'attente — atomique, pour toutes les natures
# ═════════════════════════════════════════════════════════════════════════════
def sortir(
    db: Session, proposition_id: int, etat: str, *,
    maintenant: Optional[datetime] = None, motif: Optional[str] = None,
    remplacee_par_id: Optional[int] = None, canal: Optional[str] = None,
) -> bool:
    """Fait sortir une proposition de l'attente ; True pour le SEUL appel qui l'a fait.

    La condition `etat = 'en_attente'` est dans l'UPDATE lui-même, pas dans une
    lecture préalable : deux transactions concurrentes ne peuvent pas toutes deux
    voir la ligne en attente puis la modifier. La seconde ne modifie rien, rend
    False, et son appelant n'exécute rien (règle d'US-234).

    [US-260 / CA5] `canal` : le canal qui fait sortir la proposition de l'attente. Il
    permet de répondre OÙ elle a été traitée à qui la confirme une seconde fois.
    """
    if etat not in ETATS_SORTIS:
        raise ValueError(f"État de sortie inconnu : {etat!r}")
    valeurs: dict = {"etat": etat, "traite_le": maintenant or datetime.utcnow()}
    if motif:
        valeurs["motif_refus"] = motif[:200]
    if remplacee_par_id is not None:
        valeurs["remplacee_par_id"] = int(remplacee_par_id)
    if canal:
        valeurs["traite_canal"] = canal
    nb = (
        db.query(Proposition)
        .filter(Proposition.id == int(proposition_id), Proposition.etat == ETAT_EN_ATTENTE)
        .update(valeurs, synchronize_session=False)
    )
    db.commit()
    if nb:
        log.info("[US-259 / CA3] Proposition sortie de l'attente : id=%s état=%s", proposition_id, etat)
    else:
        log.info("[US-259 / CA3] Proposition id=%s déjà sortie : %s refusé", proposition_id, etat)
    return nb == 1


# ═════════════════════════════════════════════════════════════════════════════
# Une commande ou un plan, rejouables après un redémarrage (CA8)
# ═════════════════════════════════════════════════════════════════════════════
def _champs(classe, donnees: dict) -> dict:
    """Les seuls champs que la classe connaît encore : une ligne écrite avant un
    changement du catalogue reste lisible."""
    connus = {f.name for f in fields(classe)}
    return {cle: valeur for cle, valeur in donnees.items() if cle in connus}


def _serialiser_commande(commande) -> dict:
    return {
        "commande": commande.commande,
        "sous_commande": commande.sous_commande,
        # La forme entière, et pas seulement sa clé : ce qui se confirme est ce qui
        # a été montré, même si le catalogue a changé entre-temps.
        "forme": asdict(commande.forme),
        "valeurs": dict(commande.valeurs),
        "origine": commande.origine,
        "confiance": commande.confiance,
        "regle": commande.regle,
        "latence_ms": commande.latence_ms,
        "texte_origine": commande.texte_origine,
        "manquants": [argument.nom for argument in commande.manquants],
        "candidats": list(commande.candidats),
        "argument_candidat": commande.argument_candidat,
        "outils": list(commande.outils),
        "tokens_consommes": commande.tokens_consommes,
        # [US-250, US-251] La question en attente et les mots rapprochés d'une valeur admise.
        "precision": asdict(commande.precision) if commande.precision is not None else None,
        "corrections": [list(correction) for correction in commande.corrections],
        # [US-252] Le nom tel que dit, gardé jusqu'au choix du nom voisin proposé.
        "mot_candidat": commande.mot_candidat,
    }


def _deserialiser_commande(donnees: dict):
    from app.services.interpreteur_commandes import CommandeInterpretee, PrecisionDemandee
    from app.services.menu_commandes import Argument, FormeCommande

    brute = dict(donnees["forme"])
    arguments = tuple(
        Argument(**_champs(Argument, {**a, "vocabulaire": tuple(a.get("vocabulaire") or ())}))
        for a in brute.get("arguments") or ()
    )
    forme = FormeCommande(**_champs(FormeCommande, {**brute, "arguments": arguments}))
    par_nom = {argument.nom: argument for argument in arguments}
    return CommandeInterpretee(**_champs(CommandeInterpretee, {
        **donnees,
        "forme": forme,
        "valeurs": dict(donnees.get("valeurs") or {}),
        "manquants": tuple(par_nom[nom] for nom in donnees.get("manquants") or () if nom in par_nom),
        "candidats": tuple(donnees.get("candidats") or ()),
        "outils": tuple(donnees.get("outils") or ()),
        "precision": (
            PrecisionDemandee(**_champs(PrecisionDemandee, {
                **donnees["precision"], "options": tuple(donnees["precision"].get("options") or ()),
            }))
            if donnees.get("precision") else None
        ),
        "corrections": tuple(tuple(c) for c in donnees.get("corrections") or ()),
    }))


def serialiser(commande) -> tuple[str, dict]:
    """(nature, forme JSON) d'une `CommandeInterpretee` ou d'un `Plan`."""
    from app.services.interpreteur_commandes import Plan

    if isinstance(commande, Plan):
        return NATURE_PLAN, {
            "etapes": [_serialiser_commande(etape) for etape in commande.etapes],
            "texte_origine": commande.texte_origine,
            "latence_ms": commande.latence_ms,
            "deja_faites": list(commande.deja_faites),
            "outils": list(commande.outils),
            "tokens_consommes": commande.tokens_consommes,
        }
    return NATURE_COMMANDE, _serialiser_commande(commande)


def deserialiser(nature: str, donnees: dict):
    """L'inverse de `serialiser` : ce qui se confirme est exactement ce qui a été montré."""
    from app.services.interpreteur_commandes import Plan

    if nature == NATURE_PLAN:
        return Plan(**_champs(Plan, {
            **donnees,
            "etapes": tuple(_deserialiser_commande(e) for e in donnees.get("etapes") or ()),
            "deja_faites": tuple(donnees.get("deja_faites") or ()),
            "outils": tuple(donnees.get("outils") or ()),
        }))
    return _deserialiser_commande(donnees)


# ═════════════════════════════════════════════════════════════════════════════
# La proposition d'une conversation
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class PropositionConversation:
    """Une commande ou un plan proposés en conversation, tels que la base les garde."""

    id: int
    code: str
    user_id: int
    potager_id: int
    nature: str
    commande: object  # CommandeInterpretee | Plan
    etat: str
    cree_le: datetime
    expire_le: datetime
    #: L'argument dont la valeur est demandée au jardinier (complétion guidée).
    attend: Optional[str] = None
    #: La ligne de `routage_logs` qui journalise cette proposition (US-172).
    log_id: Optional[int] = None
    #: [US-238 / CA2] Noms voisins déjà laissés de côté.
    ecartes: tuple[str, ...] = ()
    canal: Optional[str] = None
    traite_le: Optional[datetime] = None
    #: [US-260 / CA5] Le canal qui l'a fait sortir de l'attente.
    traite_canal: Optional[str] = None

    @property
    def en_attente(self) -> bool:
        return self.etat == ETAT_EN_ATTENTE

    def expiree(self, maintenant: Optional[datetime] = None) -> bool:
        return self.expire_le <= (maintenant or datetime.utcnow())

    @property
    def ts(self) -> float:
        """L'instant de la proposition en secondes, comme `time.time()` (contexte court)."""
        return self.cree_le.replace(tzinfo=timezone.utc).timestamp()


def _contenu(commande, attend: Optional[str], log_id: Optional[int], ecartes) -> tuple[str, dict]:
    nature, forme = serialiser(commande)
    return nature, {"proposition": forme, "attend": attend, "log_id": log_id, "ecartes": list(ecartes)}


def _depuis_ligne(ligne: Proposition) -> PropositionConversation:
    contenu = ligne.contenu or {}
    return PropositionConversation(
        id=ligne.id, code=ligne.code, user_id=ligne.user_id, potager_id=ligne.potager_id,
        nature=ligne.nature, commande=deserialiser(ligne.nature, contenu["proposition"]),
        etat=ligne.etat, cree_le=ligne.cree_le, expire_le=ligne.expire_le,
        attend=contenu.get("attend"), log_id=contenu.get("log_id"),
        ecartes=tuple(contenu.get("ecartes") or ()), canal=ligne.canal, traite_le=ligne.traite_le,
        traite_canal=ligne.traite_canal,
    )


def _lire(ligne: Optional[Proposition]) -> Optional[PropositionConversation]:
    """Une ligne illisible (format d'avant un changement) vaut une proposition absente :
    le jardinier redit sa demande, rien ne s'exécute sur une lecture douteuse."""
    if ligne is None:
        return None
    try:
        return _depuis_ligne(ligne)
    except Exception:  # noqa: BLE001
        log.exception("[US-259] Proposition id=%s illisible — ignorée", ligne.id)
        return None


def generer_code(db: Session, prefixe: str = PREFIXE_CODE, octets: int = _OCTETS_ALEA) -> str:
    """Un code unique dans TOUTE la table, quelle que soit la nature."""
    code = prefixe + secrets.token_urlsafe(octets)
    while db.query(Proposition.id).filter(Proposition.code == code).first() is not None:
        code = prefixe + secrets.token_urlsafe(octets)
    return code


def proposer(
    ctx: TenantContext, commande, *, log_id: Optional[int] = None,
    ecartes: tuple[str, ...] = (), canal: str = CANAL_TELEGRAM,
    maintenant: Optional[datetime] = None,
) -> PropositionConversation:
    """Range une nouvelle proposition de conversation ; la précédente est REMPLACÉE.

    Une seule proposition de conversation attend par jardinier et par potager : « non,
    4 rangs » en fait une nouvelle, avec un nouveau code, et l'ancienne passe à
    `remplacee` (F3) — ses boutons ne valident plus rien (US-234 / CA2). Le
    potager est celui du contexte : c'est lui qu'armera l'exécution (CA4).
    """
    instant = maintenant or datetime.utcnow()
    nature, contenu = _contenu(commande, None, log_id, ecartes)
    with session_sur(ctx.potager_id) as db:
        ligne = Proposition(
            code=generer_code(db), user_id=ctx.user_id, potager_id=ctx.potager_id,
            nature=nature, contenu=contenu, canal=canal, cree_le=instant,
            expire_le=expiration(instant, notifiee=False), notifiee=False, etat=ETAT_EN_ATTENTE,
        )
        db.add(ligne)
        db.flush()
        remplacees = (
            db.query(Proposition)
            .filter(
                Proposition.user_id == ctx.user_id,
                Proposition.potager_id == ctx.potager_id,
                Proposition.nature.in_(NATURES_CONVERSATION),
                Proposition.etat == ETAT_EN_ATTENTE,
                Proposition.id != ligne.id,
            )
            .update(
                {"etat": ETAT_REMPLACEE, "traite_le": instant, "remplacee_par_id": ligne.id},
                synchronize_session=False,
            )
        )
        db.commit()
        db.refresh(ligne)
        log.info(
            "[US-259] Proposition %s rangée : id=%s user_id=%s potager_id=%s canal=%s%s",
            nature, ligne.id, ctx.user_id, ctx.potager_id, canal,
            f" ({remplacees} remplacée(s))" if remplacees else "",
        )
        return _depuis_ligne(ligne)


def en_attente(
    user_id: int, potager_id: int, maintenant: Optional[datetime] = None,
) -> Optional[PropositionConversation]:
    """La proposition de conversation qui attend ce jardinier dans ce potager, ou None.

    Une proposition dont la demi-heure est passée n'attend plus rien (CA5), même
    si personne ne l'a encore marquée périmée.
    """
    instant = maintenant or datetime.utcnow()
    with session_sur(potager_id) as db:
        ligne = (
            db.query(Proposition)
            .filter(
                Proposition.user_id == user_id,
                Proposition.potager_id == potager_id,
                Proposition.nature.in_(NATURES_CONVERSATION),
                Proposition.etat == ETAT_EN_ATTENTE,
                Proposition.expire_le > instant,
            )
            .order_by(Proposition.cree_le.desc(), Proposition.id.desc())
            .first()
        )
        return _lire(ligne)


def par_code(code: Optional[str], user_id: Optional[int]) -> Optional[PropositionConversation]:
    """La proposition de conversation qu'un bouton nomme — dans tous ses états.

    Lue GUC désarmé : le bouton peut viser un autre potager que le potager actif
    (CA4). L'isolation tient au filtre `user_id`, comme pour la file d'US-224.
    """
    if not code or user_id is None:
        return None
    with session_sur(None) as db:
        ligne = (
            db.query(Proposition)
            .filter(
                Proposition.code == code,
                Proposition.user_id == user_id,
                Proposition.nature.in_(NATURES_CONVERSATION),
            )
            .first()
        )
        return _lire(ligne)


def mettre_a_jour(
    proposition: PropositionConversation, *, commande, attend: Optional[str],
    log_id: Optional[int] = None,
) -> Optional[PropositionConversation]:
    """Un nom voisin choisi, une valeur complétée : la proposition s'enrichit EN
    ATTENTE, sous le même code. None si elle n'attend plus.

    [US-250] `log_id` : la ligne du journal qui suit désormais la proposition (une
    question de précision a la sienne, qui reste « precision » pour être comptée)."""
    suivi = log_id if log_id is not None else proposition.log_id
    _, contenu = _contenu(commande, attend, suivi, proposition.ecartes)
    with session_sur(proposition.potager_id) as db:
        nb = (
            db.query(Proposition)
            .filter(Proposition.id == proposition.id, Proposition.etat == ETAT_EN_ATTENTE)
            .update({"contenu": contenu}, synchronize_session=False)
        )
        db.commit()
    return replace(proposition, commande=commande, attend=attend, log_id=suivi) if nb else None


def consommer(
    proposition: PropositionConversation, etat: str,
    maintenant: Optional[datetime] = None, canal: Optional[str] = None,
) -> bool:
    """[CA3] Confirmer, abandonner ou périmer : True pour le seul appel qui l'a fait.

    [US-260 / CA5] `canal` : où elle est traitée, pour le dire à qui la rejoue.
    """
    with session_sur(proposition.potager_id) as db:
        return sortir(db, proposition.id, etat, maintenant=maintenant, canal=canal)


def en_attente_ailleurs(
    user_id: int, potager_id: int, maintenant: Optional[datetime] = None,
) -> tuple[PropositionConversation, ...]:
    """[US-260 / CA4] Les propositions de conversation qui attendent ce jardinier dans UN AUTRE potager.

    Une proposition s'exécute dans SON potager, même après un changement de potager actif
    (US-259 / CA4) : « oui » dit dans un potager peut donc en viser deux. Lue GUC
    désarmé, comme `par_code` ; l'isolation tient au filtre `user_id`.
    """
    instant = maintenant or datetime.utcnow()
    with session_sur(None) as db:
        lignes = (
            db.query(Proposition)
            .filter(
                Proposition.user_id == user_id,
                Proposition.potager_id != potager_id,
                Proposition.nature.in_(NATURES_CONVERSATION),
                Proposition.etat == ETAT_EN_ATTENTE,
                Proposition.expire_le > instant,
            )
            .order_by(Proposition.cree_le.desc(), Proposition.id.desc())
            .all()
        )
        return tuple(p for p in (_lire(ligne) for ligne in lignes) if p is not None)


def derniere_traitee(
    user_id: int, potager_id: int, maintenant: Optional[datetime] = None,
    delai: timedelta = DUREE_CONVERSATION,
) -> Optional[PropositionConversation]:
    """[US-260 / CA5] La dernière proposition de ce jardinier, dans ce potager, confirmée ou
    abandonnée depuis moins de `delai` — celle qu'un « oui » tardif viserait encore.

    Une proposition remplacée n'est pas retenue : sa remplaçante est celle dont on parle.
    """
    instant = maintenant or datetime.utcnow()
    with session_sur(potager_id) as db:
        ligne = (
            db.query(Proposition)
            .filter(
                Proposition.user_id == user_id,
                Proposition.potager_id == potager_id,
                Proposition.nature.in_(NATURES_CONVERSATION),
                Proposition.etat.in_((ETAT_CONFIRMEE, ETAT_ABANDONNEE)),
                Proposition.traite_le >= instant - delai,
            )
            .order_by(Proposition.traite_le.desc(), Proposition.id.desc())
            .first()
        )
        return _lire(ligne)


def marquer_notifiee(proposition_id: int, potager_id: int) -> bool:
    """[CA5 / F4] Une proposition envoyée en notification peut se traiter le soir :
    elle prend la durée de la file d'US-224, comptée depuis sa création."""
    with session_sur(potager_id) as db:
        ligne = (
            db.query(Proposition)
            .filter(Proposition.id == int(proposition_id), Proposition.etat == ETAT_EN_ATTENTE)
            .first()
        )
        if ligne is None:
            return False
        ligne.notifiee = True
        ligne.expire_le = max(ligne.expire_le, expiration(ligne.cree_le, notifiee=True))
        db.commit()
        log.info("[US-259 / CA5] Proposition id=%s notifiée : attend jusqu'au %s", ligne.id, ligne.expire_le)
        return True


def potager_a_nommer(user_id: int, potager_id: int) -> Optional[str]:
    """[CA4 / F5] Le nom du potager d'une proposition, quand le jardinier en a plusieurs.

    Une proposition s'exécute dans SON potager, même si le jardinier a changé de
    potager actif entre-temps : la carte le nomme pour qu'il sache où elle agira.
    None s'il n'a qu'un potager — ou si la lecture échoue : ce n'est qu'un libellé.
    """
    from app.services.potager_actif import lister_potagers_utilisateur

    try:
        with session_sur(potager_id) as db:
            potagers = lister_potagers_utilisateur(db, user_id)
    except Exception:  # noqa: BLE001
        log.exception("[US-259 / CA4] Potagers de user_id=%s illisibles", user_id)
        return None
    if len(potagers) < 2:
        return None
    return next((p.nom for p in potagers if p.id == potager_id), None)


def purger(maintenant: Optional[datetime] = None) -> int:
    """Efface les propositions de conversation de plus de 30 jours, quel que soit leur état.

    Les gestes de la file ont leur propre rétention (`file_gestes.supprimer_gestes_sortis`).
    """
    limite = (maintenant or datetime.utcnow()) - timedelta(days=RETENTION_CONVERSATION_JOURS)
    with session_sur(None) as db:
        nb = (
            db.query(Proposition)
            .filter(Proposition.nature.in_(NATURES_CONVERSATION), Proposition.cree_le < limite)
            .delete(synchronize_session=False)
        )
        db.commit()
    if nb:
        log.info("[US-259] %s proposition(s) de conversation effacée(s) après %s jours", nb,
                 RETENTION_CONVERSATION_JOURS)
    return nb
