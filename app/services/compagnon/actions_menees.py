"""
app/services/compagnon/actions_menees.py — Ce que le compagnon a fait, pour pouvoir le désigner [US-261]
==========================================================================================================
« Mon dernier semis », « ce que je viens de noter » : une phrase ne peut désigner
que ce dont le compagnon se souvient. Cette mémoire est écrite par le CHEMIN
D'EXÉCUTION — l'enregistrement d'un geste (`evenements`), l'exécuteur d'une étape
de plan (`agent.executeurs`), la commande confirmée au bouton ou à la phrase
(`bot.interpretation`) — et JAMAIS par le modèle (CA2) : aucun outil de l'agent
n'y écrit, et un test le vérifie sur le catalogue et sur le source.

Une entrée dit (CA1) : la nature de l'action, la référence de sa cible en base,
un résumé, les valeurs avant / après quand l'exécuteur les connaît, le canal et
le statut. Seules les entrées RÉUSSIES sont lues : le compagnon ne dit jamais
« tu as supprimé » d'une suppression qui a échoué.

Lecture :

* les 5 dernières des 24 h arrivent à l'agent sous les références `A1`…`A5`,
  balisées comme des données (CA3) — `interpreteur_agent.prompt_variable` ;
* l'outil `lire(quoi="actions")` donne les suivantes (CA4), de `A6` à `A35`
  au plus, sur 7 jours ;
* elles sont propres à un jardinier ET à un potager. Une action faite dans
  Telegram se désigne depuis la PWA, et inversement (CA5, C9) ; celles d'un
  potager ne se voient jamais depuis un autre (CA6, RLS stricte).

Rien ici ne lève : une mémoire indisponible prive l'agent de contexte, elle ne
fait jamais échouer l'écriture qu'elle devait retenir.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.services.context import TenantContext
from database.db import SessionLocal, tenant_scope
from database.models import ActionMenee, Parcelle, Potager

log = logging.getLogger("potager")

NATURE_GESTE = "geste"
NATURE_COMMANDE = "commande"

STATUT_REUSSIE = "reussie"
STATUT_ECHOUEE = "echouee"

CANAL_TELEGRAM = "telegram"
CANAL_PWA = "pwa"
CANAL_INCONNU = "inconnu"

#: Le canal du traitement en cours : posé par le point d'entrée (le bot pour Telegram,
#: le middleware de l'API pour la PWA), lu par l'écriture qui retient l'action. Une
#: `ContextVar`, comme le contexte de tenant : elle suit la tâche asyncio ou la requête.
canal_courant: ContextVar[str] = ContextVar("canal_courant", default=CANAL_INCONNU)

#: [CA3] Les actions transmises à l'agent à chaque phrase : les 5 dernières des 24 h…
NB_DANS_LE_CONTEXTE = 5
FENETRE_CONTEXTE = timedelta(hours=24)
#: [CA4] … et celles que `lire(quoi="actions")` donne au-delà, sur 7 jours.
NB_AU_DELA_MAX = 30
FENETRE_LECTURE = timedelta(days=7)

#: La mémoire est un journal d'aide à la désignation, pas un historique : elle part à 30 jours.
RETENTION_JOURS = 30

_LONGUEUR_RESUME = 240


@dataclass(frozen=True)
class Action:
    """Une action menée, telle que la base la garde."""

    id: int
    nature: str
    resume: str
    canal: str
    cree_le: datetime
    statut: str = STATUT_REUSSIE
    cible_type: Optional[str] = None
    cible_id: Optional[int] = None
    cible_nom: Optional[str] = None
    avant: Optional[dict] = None
    apres: Optional[dict] = None
    proposition_id: Optional[int] = None


@contextmanager
def _session(potager_id: int) -> Iterator[Session]:
    """RLS stricte : une action s'écrit et se lit dans le potager où elle a eu lieu."""
    with tenant_scope(potager_id):
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()


def _depuis_ligne(ligne: ActionMenee) -> Action:
    return Action(
        id=ligne.id, nature=ligne.nature, resume=ligne.resume or "", canal=ligne.canal or CANAL_INCONNU,
        cree_le=ligne.cree_le, statut=ligne.statut, cible_type=ligne.cible_type, cible_id=ligne.cible_id,
        cible_nom=ligne.cible_nom, avant=ligne.avant, apres=ligne.apres, proposition_id=ligne.proposition_id,
    )


# ═════════════════════════════════════════════════════════════════════════════
# [CA1] Écrire — réservé au chemin d'exécution
# ═════════════════════════════════════════════════════════════════════════════
def noter(
    ctx: TenantContext, *, nature: str, resume: str, cible_type: Optional[str] = None,
    cible_id: Optional[int] = None, cible_nom: Optional[str] = None,
    avant: Optional[dict] = None, apres: Optional[dict] = None, canal: Optional[str] = None,
    statut: str = STATUT_REUSSIE, proposition_id: Optional[int] = None,
    maintenant: Optional[datetime] = None,
) -> Optional[int]:
    """[CA1] Retient une écriture exécutée ; rend l'identifiant de l'entrée, ou None.

    ⚠️ N'est appelée que par un exécuteur (voir l'en-tête) : le test
    `test_us261_actions_menees` refuse qu'un autre module l'importe.
    """
    try:
        with _session(ctx.potager_id) as db:
            ligne = ActionMenee(
                user_id=ctx.user_id, potager_id=ctx.potager_id, canal=canal or canal_courant.get(),
                nature=nature, cible_type=cible_type, cible_id=cible_id,
                cible_nom=(cible_nom or None) and cible_nom[:120],
                resume=(resume or "")[:_LONGUEUR_RESUME], avant=avant, apres=apres, statut=statut,
                proposition_id=proposition_id, cree_le=maintenant or datetime.utcnow(),
            )
            db.add(ligne)
            db.commit()
            log.info("[US-261 / CA1] Action retenue : id=%s %s %s (%s, potager %s)",
                     ligne.id, nature, statut, ligne.canal, ctx.potager_id)
            return ligne.id
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais l'écriture qu'elle retient
        log.exception("[US-261 / CA1] Action non retenue (potager_id=%s)", ctx.potager_id)
        return None


# ── Les résumés : une ligne, que le jardinier reconnaît ─────────────────────
def _libelle_action(type_action: Optional[str]) -> str:
    return (type_action or "geste").replace("_", " ").strip()


def resume_evenement(event, nom_parcelle: Optional[str] = None) -> str:
    """« semis radis (Cherry Belle), planche Sud, 2 rangs, le 05/05 » — un geste, en une ligne."""
    designation = " ".join(
        morceau for morceau in (
            _libelle_action(getattr(event, "type_action", None)),
            getattr(event, "culture", None) or "",
        ) if morceau
    )
    variete = getattr(event, "variete", None)
    if variete:
        designation += f" ({variete})"
    morceaux = [designation]
    if nom_parcelle:
        morceaux.append(nom_parcelle)
    quantite = getattr(event, "quantite", None)
    if quantite not in (None, ""):
        valeur = int(quantite) if float(quantite) == int(quantite) else quantite
        morceaux.append(" ".join(str(m) for m in (valeur, getattr(event, "unite", None)) if m))
    elif getattr(event, "rang", None):
        morceaux.append(f"{event.rang} rangs")
    jour = getattr(event, "date", None)
    if isinstance(jour, (datetime, date)):
        morceaux.append(f"le {jour.strftime('%d/%m')}")
    return ", ".join(morceaux)


def instantane_evenement(event, nom_parcelle: Optional[str] = None) -> dict:
    """Les valeurs d'un événement, telles qu'enregistrées — vides omises."""
    jour = getattr(event, "date", None)
    valeurs = {
        "action": getattr(event, "type_action", None), "culture": getattr(event, "culture", None),
        "variete": getattr(event, "variete", None), "parcelle": nom_parcelle,
        "quantite": getattr(event, "quantite", None), "unite": getattr(event, "unite", None),
        "rang": getattr(event, "rang", None), "commentaire": getattr(event, "commentaire", None),
        "date": jour.isoformat() if isinstance(jour, (datetime, date)) else None,
    }
    return {cle: valeur for cle, valeur in valeurs.items() if valeur not in (None, "")}


def noter_evenement(db: Session, ctx: TenantContext, event, *, proposition_id: Optional[int] = None) -> None:
    """[CA1] Un geste enregistré devient une action menée (cible : l'événement, par son id).

    Appelée par `evenements` après le commit de l'événement, avec la session de
    l'appelant : le nom de la parcelle est lu là, l'écriture de l'action se fait
    dans sa propre session — un échec ici ne défait rien. Ne lève jamais.
    """
    try:
        nom_parcelle = None
        if getattr(event, "parcelle_id", None):
            parcelle = db.get(Parcelle, event.parcelle_id)
            nom_parcelle = parcelle.nom if parcelle is not None else None
        noter(
            ctx, nature=NATURE_GESTE, resume=resume_evenement(event, nom_parcelle),
            cible_type="evenement", cible_id=event.id, cible_nom=nom_parcelle,
            apres=instantane_evenement(event, nom_parcelle), proposition_id=proposition_id,
        )
    except Exception:  # noqa: BLE001
        log.exception("[US-261 / CA1] Geste non retenu comme action")


def _nom_parcelle(db: Session, event) -> Optional[str]:
    if not getattr(event, "parcelle_id", None):
        return None
    parcelle = db.get(Parcelle, event.parcelle_id)
    return parcelle.nom if parcelle is not None else None


def instantane_avant_correction(db: Session, event) -> dict:
    """[US-262] Les valeurs d'un geste juste avant qu'il soit corrigé ou retiré — lues par
    `evenements`, qui les rend ensuite à `noter_correction` / `noter_annulation`."""
    try:
        return instantane_evenement(event, _nom_parcelle(db, event))
    except Exception:  # noqa: BLE001
        log.exception("[US-262] Instantané du geste %s illisible", getattr(event, "id", None))
        return {}


def noter_correction(db: Session, ctx: TenantContext, event, avant: dict) -> None:
    """[US-262] Un geste corrigé devient une action menée, avec ses valeurs avant / après.

    Même cible que le geste : « annule-le » le désigne encore. Ne lève jamais."""
    try:
        nom_parcelle = _nom_parcelle(db, event)
        noter(
            ctx, nature=NATURE_GESTE, resume="correction : " + resume_evenement(event, nom_parcelle),
            cible_type="evenement", cible_id=event.id, cible_nom=nom_parcelle,
            avant=avant, apres=instantane_evenement(event, nom_parcelle),
        )
    except Exception:  # noqa: BLE001
        log.exception("[US-262] Correction non retenue comme action")


def noter_annulation(ctx: TenantContext, evenement_id: int, avant: dict, resume: str) -> None:
    """[US-262] Un geste retiré du carnet devient une action menée : le compagnon sait qu'il
    l'a annulé, et ne le propose plus à la correction (sa cible n'existe plus). Ne lève jamais."""
    noter(
        ctx, nature=NATURE_GESTE, resume="annulation : " + (resume or "geste"),
        cible_type="evenement", cible_id=evenement_id, cible_nom=avant.get("parcelle"),
        avant=avant, apres={},
    )


#: Où se lit la cible d'une commande dans ses valeurs (la première renseignée).
_CLES_CIBLE = ("nom", "parcelle", "ancien", "lot", "numero", "culture")


def cible_de(commande) -> Optional[str]:
    valeurs = getattr(commande, "valeurs", None) or {}
    return next((str(valeurs[cle]) for cle in _CLES_CIBLE if valeurs.get(cle)), None)


def resume_commande(commande) -> str:
    """« Supprimer une parcelle : Serre » — le libellé du catalogue et sa cible."""
    libelle = getattr(getattr(commande, "forme", None), "libelle", None) or commande.commande_equivalente()
    cible = cible_de(commande)
    return f"{libelle} : {cible}" if cible else libelle


def noter_commande(
    ctx: TenantContext, commande, *, statut: str = STATUT_REUSSIE, avant: Optional[dict] = None,
    apres: Optional[dict] = None, cible_id: Optional[int] = None, proposition_id: Optional[int] = None,
    canal: Optional[str] = None,
) -> Optional[int]:
    """[CA1] Une commande exécutée (seule, ou étape d'un plan) devient une action menée."""
    return noter(
        ctx, nature=NATURE_COMMANDE, resume=resume_commande(commande), cible_type=commande.forme.commande,
        cible_id=cible_id, cible_nom=cible_de(commande), avant=avant, apres=apres, statut=statut,
        proposition_id=proposition_id, canal=canal,
    )


def instantane_parcelle(db: Session, potager_id: int, nom: Optional[str]) -> Optional[dict]:
    """La fiche d'une parcelle (nom exact, rôle actif ou non), pour comparer avant / après.

    Les champs sont ceux de l'outil `modifier_parcelle`, projetés de la même source
    (`catalogue_outils.champs_fiche`) : aucune liste n'est tenue ici. None si la parcelle
    n'existe pas ou n'est pas lisible.
    """
    if not nom:
        return None
    try:
        from app.services.agent.catalogue_outils import champs_fiche
        from utils.parcelles import find_doublon, normalize_parcelle_name

        parcelle, _ = find_doublon(db, normalize_parcelle_name(nom), potager_id=potager_id)
        if parcelle is None:
            return None
        valeurs = {"nom": parcelle.nom, "actif": bool(parcelle.actif)}
        for champ in champs_fiche():
            valeur = getattr(parcelle, champ.nom, None)
            if valeur is not None:
                valeurs[champ.nom] = valeur
        return valeurs
    except Exception:  # noqa: BLE001 — un instantané manquant n'empêche pas de retenir l'action
        log.exception("[US-261] Instantané de la parcelle %r illisible", nom)
        return None


def instantane_commande(
    ctx: TenantContext, commande, *, apres: bool, db: Optional[Session] = None,
) -> Optional[dict]:
    """La fiche de la parcelle qu'une commande touche, avant ou après elle — None pour les autres formes.

    Seules les commandes sur une parcelle ont des valeurs avant / après lisibles ici ; les autres
    gardent leur résumé et leur cible (CA1 : « quand l'exécuteur les connaît »).
    """
    forme = commande.forme
    if forme.commande != "parcelle":
        return None
    sous = forme.sous_commande
    if (apres and sous == "supprimer") or (not apres and sous == "ajouter"):
        return None
    valeurs = commande.valeurs or {}
    nom = valeurs.get("nouveau") if (apres and sous == "renommer") else cible_de(commande)
    if db is not None:
        return instantane_parcelle(db, ctx.potager_id, nom)
    try:
        with _session(ctx.potager_id) as session:
            return instantane_parcelle(session, ctx.potager_id, nom)
    except Exception:  # noqa: BLE001
        log.exception("[US-261] Instantané de la commande illisible")
        return None


#: Ce qu'un handler de commande écrit quand il n'a rien fait : l'échec est lu dans sa réponse,
#: puisqu'il répond au jardinier sans rendre de résultat.
MARQUES_D_ECHEC = ("❌", "⚠️", "🚫", "⛔", "🙏")


def statut_des_reponses(reponses: list[str]) -> str:
    """`echouee` si une réponse du handler porte une marque d'échec, `reussie` sinon.

    ⚠️ Un handler qui ne répond rien passe pour réussi : la mémoire peut retenir à tort une
    action refusée en silence, jamais l'inverse — elle ne dit donc « fait » que d'un handler
    qui est allé au bout sans se plaindre.
    """
    return STATUT_ECHOUEE if any(r.lstrip().startswith(MARQUES_D_ECHEC) for r in reponses) else STATUT_REUSSIE


def retenir_commande(
    ctx: TenantContext, commande, reponses: list[str], *, avant: Optional[dict] = None,
    proposition_id: Optional[int] = None,
) -> Optional[int]:
    """[CA1] Une commande confirmée et jouée par son handler : retenue avec ses valeurs avant / après.

    Une commande de consultation n'écrit rien et n'est pas retenue.
    """
    if not commande.forme.confirmation:
        return None
    statut = statut_des_reponses(reponses)
    apres = instantane_commande(ctx, commande, apres=True) if statut == STATUT_REUSSIE else None
    return noter_commande(ctx, commande, statut=statut, avant=avant, apres=apres, proposition_id=proposition_id)


# ═════════════════════════════════════════════════════════════════════════════
# [CA3, CA4, CA5, CA6] Lire — pour désigner
# ═════════════════════════════════════════════════════════════════════════════
def recentes(
    ctx: TenantContext, *, depuis: timedelta = FENETRE_CONTEXTE, limite: int = NB_DANS_LE_CONTEXTE,
    decalage: int = 0, maintenant: Optional[datetime] = None,
) -> tuple[Action, ...]:
    """Les actions réussies de CE jardinier dans CE potager, de la plus récente à la plus ancienne.

    `decalage` saute les plus récentes : `lire(quoi="actions")` reprend là où le contexte s'arrête.
    """
    instant = maintenant or datetime.utcnow()
    try:
        with _session(ctx.potager_id) as db:
            lignes = (
                db.query(ActionMenee)
                .filter(
                    ActionMenee.potager_id == ctx.potager_id,
                    ActionMenee.user_id == ctx.user_id,
                    ActionMenee.statut == STATUT_REUSSIE,
                    ActionMenee.cree_le >= instant - depuis,
                    ActionMenee.cree_le <= instant,
                )
                .order_by(ActionMenee.cree_le.desc(), ActionMenee.id.desc())
                .offset(decalage)
                .limit(limite)
                .all()
            )
            return tuple(_depuis_ligne(ligne) for ligne in lignes)
    except Exception as e:  # noqa: BLE001 — sans mémoire, l'agent répond sans « A1… »
        log.warning("[US-261] Actions illisibles (%s) : user_id=%s potager_id=%s",
                    type(e).__name__, ctx.user_id, ctx.potager_id)
        return ()


def au_dela(ctx: TenantContext, maintenant: Optional[datetime] = None) -> tuple[tuple[Action, ...], int]:
    """[CA4] → (les actions que le contexte ne porte pas, rang de la première : `A{rang}`)."""
    deja = len(recentes(ctx, maintenant=maintenant))
    return (
        recentes(ctx, depuis=FENETRE_LECTURE, limite=NB_AU_DELA_MAX, decalage=deja, maintenant=maintenant),
        deja + 1,
    )


def il_y_a(ecart: timedelta) -> str:
    """« à l'instant », « il y a 12 min », « il y a 3 h », « il y a 2 j »."""
    minutes = int(ecart.total_seconds() // 60)
    if minutes < 1:
        return "à l'instant"
    if minutes < 60:
        return f"il y a {minutes} min"
    if minutes < 24 * 60:
        return f"il y a {minutes // 60} h"
    return f"il y a {minutes // (24 * 60)} j"


def en_donnees(
    actions: tuple[Action, ...], premier_rang: int = 1, maintenant: Optional[datetime] = None,
) -> list[dict]:
    """[CA3] Les actions sous leurs références opaques `A1`…, prêtes à être balisées comme données.

    Les valeurs avant / après n'accompagnent que les modifications : pour une création,
    le résumé dit déjà tout.
    """
    instant = maintenant or datetime.utcnow()
    donnees: list[dict] = []
    for rang, action in enumerate(actions, start=premier_rang):
        entree: dict = {
            "ref": f"A{rang}", "action": action.resume, "canal": action.canal,
            "quand": il_y_a(instant - action.cree_le),
        }
        if action.avant is not None:
            entree["avant"] = action.avant
            entree["apres"] = action.apres
        donnees.append(entree)
    return donnees


def purger(maintenant: Optional[datetime] = None) -> int:
    """Efface les actions de plus de 30 jours, potager par potager (RLS stricte)."""
    limite = (maintenant or datetime.utcnow()) - timedelta(days=RETENTION_JOURS)
    with tenant_scope(None):
        db = SessionLocal()
        try:
            potagers = [ligne[0] for ligne in db.query(Potager.id).all()]
        finally:
            db.close()
    total = 0
    for potager_id in potagers:
        with _session(potager_id) as db:
            nb = (
                db.query(ActionMenee)
                .filter(ActionMenee.potager_id == potager_id, ActionMenee.cree_le < limite)
                .delete(synchronize_session=False)
            )
            db.commit()
            total += nb
    if total:
        log.info("[US-261] %s action(s) menée(s) effacée(s) après %s jours", total, RETENTION_JOURS)
    return total
