"""
app/services/agent/executeurs.py — Les étapes d'un plan, exécutées par le service [US-237]
========================================================================================
Une commande ISOLÉE s'exécute toujours par son handler (US-172 / CA9). Ce
chemin ne convient pas à un plan : un handler répond un message et rend `None`,
le code ne peut donc pas savoir si l'étape 1 a réussi avant de lancer l'étape 2.

Chaque forme admise dans un plan reçoit ici un EXÉCUTEUR, qui appelle le même
service que son handler et rend un `ResultatEtape`. `SERVICES` dit lequel : le
test de parité (CA8) vérifie que c'est bien la fonction qu'appelle le handler.

Périmètre de départ (A8) : `/parcelle ajouter` et `/parcelle modifier`. Une
forme sans exécuteur reste une commande seule — le validateur la refuse dans un
plan (CA4) — et les commandes destructrices restent hors plan.

Exécution (CA6, CA7) : chaque étape est revalidée contre la base juste avant
d'être exécutée ; la première étape en échec arrête tout. Il n'y a ni reprise
automatique ni retour en arrière : ce qui a réussi reste écrit.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.services.compagnon import actions_menees
from app.services.context import TenantContext
from app.services.interpreteur_commandes import CommandeInterpretee, Plan
from app.services.permissions import PermissionInsuffisanteError, require_role
from utils import parcelles as _parcelles

log = logging.getLogger("potager")

STATUT_REUSSIE = "reussie"
STATUT_ECHOUEE = "echouee"
STATUT_NON_EXECUTEE = "non_executee"

CLE_AJOUTER = ("parcelle", "ajouter")
CLE_MODIFIER = ("parcelle", "modifier")

#: [CA8] Le service de chaque forme admise dans un plan — celui qu'appelle aussi
#: son handler (`app.bot.messages` pour la création confirmée,
#: `app.bot.commandes_parcelle` pour la modification).
SERVICES: dict[tuple, Callable] = {
    CLE_AJOUTER: _parcelles.create_parcelle,
    CLE_MODIFIER: _parcelles.update_parcelle,
}


@dataclass(frozen=True)
class ResultatEtape:
    """[US-237 / CA7] Ce qu'une étape de plan a réellement produit."""

    statut: str
    #: En clair, pour le compte rendu au jardinier — la raison du service en cas d'échec.
    message: str


class _EtapeRefusee(Exception):
    """La revalidation ou le service refuse l'étape : son message est la raison."""


def _parcelle_active(db: Session, ctx: TenantContext, nom: str):
    exact, _ = _parcelles.find_doublon(db, _parcelles.normalize_parcelle_name(nom), potager_id=ctx.potager_id)
    return exact if exact is not None and exact.actif else None


# ═════════════════════════════════════════════════════════════════════════════
# [CA6] Revalidation contre la base, juste avant l'exécution
# ═════════════════════════════════════════════════════════════════════════════
def revalider(db: Session, ctx: TenantContext, commande: CommandeInterpretee) -> Optional[str]:
    """La raison pour laquelle l'étape ne peut plus s'exécuter, ou None.

    La base a pu changer entre la proposition et la confirmation (un autre
    membre du potager, la PWA) : une parcelle créée entre-temps, une autre
    supprimée. Le nom doit exister à l'identique, jamais rapproché (CA12 d'US-172).
    """
    nom = commande.valeurs.get("nom", "")
    if commande.forme.cle == CLE_AJOUTER:
        existante = _parcelle_active(db, ctx, nom)
        if existante is not None:
            return f"la parcelle « {existante.nom} » existe déjà"
        return None
    if commande.forme.cle == CLE_MODIFIER and _parcelle_active(db, ctx, nom) is None:
        return f"la parcelle « {nom} » est introuvable"
    return None


# ═════════════════════════════════════════════════════════════════════════════
# Les exécuteurs — un par forme admise
# ═════════════════════════════════════════════════════════════════════════════
def _executer_ajouter(db: Session, ctx: TenantContext, commande: CommandeInterpretee) -> str:
    require_role(ctx, "editor", "créer une parcelle")
    superficie = commande.valeurs.get("superficie")
    try:
        parcelle = SERVICES[CLE_AJOUTER](
            db, commande.valeurs["nom"],
            exposition=commande.valeurs.get("exposition") or None,
            superficie_m2=float(superficie.replace(",", ".")) if superficie else None,
            potager_id=ctx.potager_id,
        )
    except ValueError as e:
        raise _EtapeRefusee(str(e))
    return f"Parcelle « {parcelle.nom} » créée"


def arguments_modification(commande: CommandeInterpretee) -> dict[str, str]:
    """Les `clé=valeur` de la commande, découpés comme le handler les découpe."""
    kwargs: dict[str, str] = {}
    for morceau in (commande.valeurs.get("modification") or "").split():
        cle, signe, valeur = morceau.partition("=")
        if not signe:
            raise _EtapeRefusee(f"paramètre invalide : {morceau}")
        kwargs[cle.lower().strip()] = valeur.strip()
    return kwargs


def _executer_modifier(db: Session, ctx: TenantContext, commande: CommandeInterpretee) -> str:
    require_role(ctx, "editor", "modifier une parcelle")
    try:
        parcelle, modifs = SERVICES[CLE_MODIFIER](
            db, commande.valeurs["nom"], potager_id=ctx.potager_id,
            **arguments_modification(commande),
        )
    except LookupError:
        raise _EtapeRefusee(f"la parcelle « {commande.valeurs.get('nom', '')} » est introuvable")
    except ValueError as e:
        raise _EtapeRefusee(str(e))
    return f"Parcelle « {parcelle.nom} » mise à jour : {', '.join(modifs) or 'rien à changer'}"


EXECUTEURS: dict[tuple, Callable[[Session, TenantContext, CommandeInterpretee], str]] = {
    CLE_AJOUTER: _executer_ajouter,
    CLE_MODIFIER: _executer_modifier,
}


def admise_dans_un_plan(commande: CommandeInterpretee) -> bool:
    """[CA4] Seules les formes qui ont un exécuteur peuvent entrer dans un plan."""
    return commande.forme.cle in EXECUTEURS and not commande.forme.destructrice


def executer_etape(
    db: Session, ctx: TenantContext, commande: CommandeInterpretee,
    proposition_id: Optional[int] = None,
) -> ResultatEtape:
    """[CA6, CA8] Revalide puis exécute UNE étape. Ne lève jamais.

    [US-261 / CA1] Une étape exécutée est retenue parmi les actions menées, avec les valeurs
    de la parcelle avant / après : c'est CE chemin d'exécution qui l'écrit, jamais le modèle.
    """
    if commande.forme.cle not in EXECUTEURS:
        return _jouer_etape(db, ctx, commande)
    avant = actions_menees.instantane_commande(ctx, commande, apres=False, db=db)
    resultat = _jouer_etape(db, ctx, commande)
    reussie = resultat.statut == STATUT_REUSSIE
    actions_menees.noter_commande(
        ctx, commande,
        statut=actions_menees.STATUT_REUSSIE if reussie else actions_menees.STATUT_ECHOUEE,
        avant=avant if reussie else None,
        apres=actions_menees.instantane_commande(ctx, commande, apres=True, db=db) if reussie else None,
        proposition_id=proposition_id,
    )
    return resultat


def _jouer_etape(db: Session, ctx: TenantContext, commande: CommandeInterpretee) -> ResultatEtape:
    executeur = EXECUTEURS.get(commande.forme.cle)
    if executeur is None:
        return ResultatEtape(STATUT_ECHOUEE, "je ne sais faire celle-ci que seule")
    try:
        raison = revalider(db, ctx, commande)
        if raison is not None:
            raise _EtapeRefusee(raison)
        return ResultatEtape(STATUT_REUSSIE, executeur(db, ctx, commande))
    except _EtapeRefusee as e:
        db.rollback()
        return ResultatEtape(STATUT_ECHOUEE, str(e))
    except PermissionInsuffisanteError as e:
        return ResultatEtape(STATUT_ECHOUEE, str(e))
    except Exception as e:  # noqa: BLE001 — une panne arrête le plan, elle ne le fait pas planter
        log.exception("[US-237] Étape %s en erreur", commande.commande_equivalente())
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return ResultatEtape(STATUT_ECHOUEE, f"erreur inattendue ({type(e).__name__})")


def executer_plan(
    plan: Plan, ctx: TenantContext, proposition_id: Optional[int] = None,
) -> tuple[ResultatEtape, ...]:
    """[CA6, CA7] Les étapes dans l'ordre ; la première en échec arrête la suite.

    Une création signalée « existe déjà » (CA3) est sautée sans arrêter le plan :
    le jardinier l'a vue avant de confirmer.
    """
    from database.db import SessionLocal

    resultats: list[ResultatEtape] = []
    arret = False
    db = SessionLocal()
    try:
        for rang, etape in enumerate(plan.etapes):
            if arret:
                resultats.append(ResultatEtape(STATUT_NON_EXECUTEE, "non exécutée"))
                continue
            if rang in plan.deja_faites:
                resultats.append(ResultatEtape(
                    STATUT_NON_EXECUTEE, f"la parcelle « {etape.valeurs.get('nom', '')} » existait déjà",
                ))
                continue
            resultat = executer_etape(db, ctx, etape, proposition_id=proposition_id)
            log.info(
                "[US-237] Étape %d/%d %s → %s (%s)",
                rang + 1, len(plan.etapes), etape.commande_equivalente(), resultat.statut, resultat.message,
            )
            resultats.append(resultat)
            arret = resultat.statut == STATUT_ECHOUEE
    finally:
        db.close()
    return tuple(resultats)


_PICTOS = {STATUT_REUSSIE: "✅", STATUT_ECHOUEE: "❌", STATUT_NON_EXECUTEE: "⏭"}


def compte_rendu(plan: Plan, resultats: tuple[ResultatEtape, ...]) -> str:
    """[CA7] Chaque étape : ✅ réussie, ❌ échouée avec la raison du service,
    ⏭ non exécutée. Texte brut : la raison vient du service, pas du Markdown."""
    lignes = []
    for rang, (etape, resultat) in enumerate(zip(plan.etapes, resultats)):
        lignes.append(f"{_PICTOS[resultat.statut]} {rang + 1}. {etape.commande_equivalente()} — {resultat.message}")
    if any(r.statut == STATUT_ECHOUEE for r in resultats):
        lignes.append("")
        lignes.append("Les étapes réussies restent faites. Redis la suite quand tu veux.")
    return "\n".join(lignes)
