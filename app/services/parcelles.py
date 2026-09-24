"""
app/services/parcelles.py — Requêtes Parcelle / CultureConfig [US-041 / US-042]
-----------------------------------------------------------------------
Complète app/services/evenements.py pour les accès directs à `parcelles`
et `culture_config` qui ne portent pas sur Evenement.

[US-042] Toutes les requêtes filtrent par ctx.potager_id. `culture_config`
reste un cas particulier : une fiche avec potager_id NULL est un
référentiel global partagé (US-040) — elle reste visible dans tous les
potagers, en plus des fiches propres au potager courant.
"""
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services.context import TenantContext
from app.services.permissions import require_role
from database.models import CultureConfig, Evenement, Parcelle
from utils.parcelles import create_parcelle as _create_parcelle
from utils.parcelles import rename_parcelle as _rename_parcelle
from utils.parcelles import update_parcelle as _update_parcelle
from utils.parcelles import valider_champs as _valider_champs
from utils.parcelles import ChampInvalide as _ChampInvalide


def get_parcelle(db: Session, ctx: TenantContext, parcelle_id: int) -> Optional[Parcelle]:
    parcelle = db.get(Parcelle, parcelle_id)
    if parcelle is None or parcelle.potager_id != ctx.potager_id:
        return None
    return parcelle


def creer_parcelle(
    db: Session,
    ctx: TenantContext,
    nom: str,
    exposition: Optional[str] = None,
    superficie_m2: Optional[float] = None,
    est_pepiniere: bool = False,
    type_sol: Optional[str] = None,
) -> Parcelle:
    """[US-058 / CA3, CA5] Première porte d'entrée HTTP pour créer une parcelle
    (jusqu'ici réservé au bot Telegram, `/parcelle ajouter`) — réutilise la même
    fonction de service `utils.parcelles.create_parcelle`, aucune nouvelle règle
    métier. Lève ValueError (doublon) si une parcelle du même nom existe déjà
    dans ce potager — à traduire en 409 côté appelant HTTP."""
    require_role(ctx, "editor", "créer une parcelle")
    return _create_parcelle(
        db, nom,
        exposition=exposition,
        superficie_m2=superficie_m2,
        potager_id=ctx.potager_id,
        est_pepiniere=est_pepiniere,
        type_sol=type_sol,
    )


#: [US-230 / CA1] Ce que la fiche web sait corriger, et la traduction vers les
#: noms de paramètres du point d'écriture du domaine. La **largeur** n'y figure
#: pas : elle se déduit (US-225), elle ne se déclare pas. L'**ordre** non plus :
#: il se règle dans la Vue plan (US-202).
CHAMPS_FICHE: dict[str, str] = {
    "superficie_m2": "superficie",
    "longueur_m": "longueur",
    "nb_rangs": "rangs",
    "exposition": "exposition",
    "type_sol": "type_sol",
    "abri": "abri",
    "paillage": "paillage",
    "est_pepiniere": "pepiniere",
    "actif": "actif",
}


#: [US-230 / E2] L'exposition n'a PAS de vocabulaire fermé en base : elle est un
#: texte libre depuis l'origine, et des potagers en production portent des
#: valeurs que ces cinq propositions ne couvrent pas. La fiche les propose donc
#: sans les imposer — la liste est une aide à la frappe, et la valeur déjà
#: enregistrée reste offerte telle quelle par l'écran.
EXPOSITIONS_PROPOSEES: tuple[str, ...] = ("Sud", "Est", "Ouest", "Nord", "Mi-ombre")


def vocabulaires_fiche() -> dict:
    """[US-230 / CA3] Les listes fermées de la fiche, telles que le DOMAINE les
    définit — l'écran les rend, il ne les écrit pas.

    Chaque entrée porte la valeur envoyée à l'écriture (`valeur`) et le libellé
    lu par le jardinier (`libelle`). `ferme` dit si la liste est une règle
    (abri, type de sol) ou une proposition (exposition).
    """
    from utils.parcelles import ABRIS, LIBELLES_ABRI, TYPES_SOL

    return {
        "abri": {
            "ferme": True,
            "options": [
                {"valeur": cle, "libelle": LIBELLES_ABRI[cle].capitalize()}
                for cle in ABRIS
            ],
        },
        "type_sol": {
            "ferme": True,
            "options": [
                {"valeur": libelle, "libelle": libelle} for libelle in TYPES_SOL.values()
            ],
        },
        "exposition": {
            "ferme": False,
            "options": [{"valeur": v, "libelle": v} for v in EXPOSITIONS_PROPOSEES],
        },
    }


def _texte_booleen(valeur: object) -> object:
    """Les booléens JSON deviennent le « true »/« false » que le domaine lit —
    `None` reste `None`, il veut dire « non renseigné » (CA6)."""
    if valeur is None:
        return None
    if isinstance(valeur, bool):
        return "true" if valeur else "false"
    return str(valeur)


def modifier_parcelle(
    db: Session, ctx: TenantContext, parcelle_id: int, champs: dict
) -> tuple[Parcelle, list[str]]:
    """[US-230 / CA1, CA2, CA3] Corrige les caractéristiques d'une parcelle
    depuis sa fiche web.

    Aucune borne, aucune normalisation de nom, aucun vocabulaire fermé n'est
    écrit ici : tout est **délégué** au point d'écriture du domaine —
    `utils.parcelles.update_parcelle` pour les caractéristiques,
    `rename_parcelle` pour le nom (US-006). Ce service ne fait que trois
    choses : vérifier le rôle, résoudre la parcelle dans le potager courant,
    et valider l'ensemble AVANT d'écrire quoi que ce soit (CA13).

    `champs` ne porte que ce que le jardinier a touché (E4) : un champ absent
    n'est pas transmis, et n'écrase donc rien (CA14).

    Lève PermissionInsuffisanteError, LookupError (parcelle inconnue) ou
    ValueError (valeur refusée, nom déjà pris).
    """
    require_role(ctx, "editor", "modifier une parcelle")
    parcelle = get_parcelle(db, ctx, parcelle_id)
    if parcelle is None:
        raise LookupError(parcelle_id)

    inconnus = set(champs) - set(CHAMPS_FICHE) - {"nom"}
    if inconnus:
        raise ValueError(
            f"Champ(s) non modifiable(s) depuis la fiche : {', '.join(sorted(inconnus))}"
        )

    kwargs = {
        CHAMPS_FICHE[cle]: _texte_booleen(valeur)
        for cle, valeur in champs.items() if cle in CHAMPS_FICHE
    }
    # [CA13] Tout est contrôlé d'abord : une valeur hors borne au milieu du lot
    # ne doit pas laisser derrière elle les champs déjà écrits avant elle.
    # [E5] Le champ fautif repart sous son nom d'API, pour que l'écran pose le
    # message SOUS lui — jamais en haut de la carte.
    try:
        _valider_champs(**kwargs)
    except _ChampInvalide as e:
        vers_api = {v: k for k, v in CHAMPS_FICHE.items()}
        raise _ChampInvalide(vers_api.get(e.champ, e.champ), str(e)) from None

    modifs: list[str] = []
    nouveau_nom = champs.get("nom")
    if nouveau_nom is not None and str(nouveau_nom).strip() != parcelle.nom:
        # [E7, CA2] Le renommage reste celui d'US-006 : unicité du nom
        # normalisé par potager, événements qui suivent la parcelle.
        ancien = parcelle.nom
        try:
            parcelle, _ = _rename_parcelle(
                db, ancien, str(nouveau_nom).strip(), potager_id=ctx.potager_id
            )
        except ValueError as e:
            # [E7] Un nom déjà pris se dit SOUS le champ du nom, avec le nom en
            # conflit nommé — message d'US-006, inchangé.
            raise _ChampInvalide("nom", str(e)) from None
        modifs.append(f"Nom : {ancien} → {parcelle.nom}")

    if kwargs:
        parcelle, autres = _update_parcelle(
            db, parcelle.nom, potager_id=ctx.potager_id, **kwargs
        )
        modifs.extend(autres)
    return parcelle, modifs


def lister_cultures_config(db: Session, ctx: TenantContext) -> list[CultureConfig]:
    """[GET /cultures] Toutes les fiches culture configurées (globales + propres au
    potager courant), triées par nom."""
    return (
        db.query(CultureConfig)
        .filter(or_(CultureConfig.potager_id == ctx.potager_id, CultureConfig.potager_id.is_(None)))
        .order_by(CultureConfig.nom)
        .all()
    )


def get_culture_config(db: Session, ctx: TenantContext, nom: str) -> Optional[CultureConfig]:
    return (
        db.query(CultureConfig)
        .filter(
            CultureConfig.nom == nom,
            or_(CultureConfig.potager_id == ctx.potager_id, CultureConfig.potager_id.is_(None)),
        )
        .first()
    )


def creer_culture_config(db: Session, ctx: TenantContext, nom: str, type_organe: str) -> CultureConfig:
    """[US-037 CA7] Crée une fiche culture minimale suite à la clarification végétatif/reproducteur.
    [US-042] Rattachée au potager courant (fiche personnalisée, pas globale)."""
    cfg = CultureConfig(nom=nom, type_organe_recolte=type_organe, potager_id=ctx.potager_id)
    db.add(cfg)
    db.commit()
    return cfg


def parcelles_avec_culture(db: Session, ctx: TenantContext, culture: str, variete: Optional[str]) -> list[Parcelle]:
    """Parcelles actives distinctes où `culture` (+ variété optionnelle) a été plantée
    ou semée en pleine terre. Réutilise la condition de localisation d'evenements.py."""
    from app.services.evenements import _cond_localisation_culture

    q = (
        db.query(Parcelle)
        .join(Evenement, Evenement.parcelle_id == Parcelle.id)
        .filter(
            Parcelle.actif == True,
            Parcelle.potager_id == ctx.potager_id,
            Evenement.potager_id == ctx.potager_id,
            _cond_localisation_culture(ctx.potager_id),
            Evenement.culture == culture,
        )
    )
    if variete:
        q = q.filter(Evenement.variete == variete)
    return q.distinct().all()
