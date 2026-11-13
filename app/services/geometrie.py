"""
[US-326] Géométrie du potager, de ses parcelles et de la position des rangs.

Ce module est le SEUL point d'écriture de la géométrie (bornes, vocabulaire,
superficie déduite) et le seul à dire si une position de rang est acceptable.
`GET /plan` lit la géométrie par `geometrie_parcelle` / `geometrie_potager` ;
la position des rangs, elle, est appliquée par `repartition_rangs`.

Règles de l'US :

- **G1** — une seule source : longueur (`Parcelle.longueur_m`, US-225), largeur et
  sens des rangs se posent sur le plan ; la superficie s'en déduit (L × l).
- **G2** — une superficie DÉCLARÉE est gardée tant que le jardinier n'a pas aligné
  sa fiche : l'écart est signalé (`ecart_superficie`), jamais corrigé en silence.
  Une fiche alignée (ou vide) suit ensuite la géométrie à chaque changement.
- **G4 / P4** — un rang n'est partagé entre plusieurs cultures que si la parcelle a
  une longueur ; sans elle, un rang porte UNE culture (arbitrage du 12/11/2026).
- **G6** — aucune géométrie n'est inventée : x et y nuls = parcelle « à placer ».
- **P7** — `forme` est un champ libre de toute cohérence avec `abri` et le type
  de pépinière (chaude / froide) : la géométrie ne lit ni l'un ni l'autre.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Optional

from sqlalchemy.orm import Session

from database.models import Parcelle, Potager
from app.services.context import TenantContext
from app.services.permissions import require_role

log = logging.getLogger("potager")

# ── Vocabulaire ──────────────────────────────────────────────────────────────
FORMES: tuple[str, ...] = ("planche", "bac", "butte", "serre", "pepiniere")
SENS_LONGUEUR = "longueur"
SENS_TRAVERS = "travers"
SENS_RANGS: tuple[str, ...] = (SENS_LONGUEUR, SENS_TRAVERS)
ORIENTATIONS: tuple[str, ...] = ("n", "ne", "e", "se", "s", "so", "o", "no")

POSITION_MAX = 2000.0
LARGEUR_MIN, LARGEUR_MAX = 0.1, 200.0
EMPRISE_MIN, EMPRISE_MAX = 1.0, 2000.0
#: Tolérance d'alignement superficie ↔ L × l (arrondis d'affichage).
TOLERANCE_SUPERFICIE = 0.05

#: Champs de géométrie d'une parcelle, acceptés par `PATCH /parcelles/{id}` (CA2).
#: La longueur n'y figure pas : c'est le champ de fiche `longueur_m` (G1).
CHAMPS_GEOMETRIE_PARCELLE: tuple[str, ...] = (
    "forme", "x_m", "y_m", "largeur_m", "rotation_deg", "sens_rangs",
)
#: Demande d'aligner la superficie de la fiche sur la géométrie posée (G2).
CHAMP_ALIGNER = "aligner_superficie"
CHAMPS_GEOMETRIE_POTAGER: tuple[str, ...] = (
    "emprise_longueur_m", "emprise_largeur_m", "angle_deg", "orientation_nord",
)

_ALIAS_FORME = {"pépinière": "pepiniere", "planches": "planche", "bacs": "bac",
                "buttes": "butte", "serres": "serre"}
_ALIAS_SENS = {"dans la longueur": SENS_LONGUEUR, "en long": SENS_LONGUEUR,
               "en travers": SENS_TRAVERS, "dans la largeur": SENS_TRAVERS}
_ALIAS_ORIENTATION = {"nord": "n", "nord-est": "ne", "est": "e", "sud-est": "se",
                      "sud": "s", "sud-ouest": "so", "ouest": "o", "nord-ouest": "no",
                      "w": "o", "nw": "no", "sw": "so"}


class GeometrieInvalideError(ValueError):
    """Valeur de géométrie refusée. `champ` nomme le champ d'API fautif (E5 d'US-230)."""

    def __init__(self, champ: str, message: str) -> None:
        super().__init__(message)
        self.champ = champ


class PositionRangRefuseeError(ValueError):
    """[US-326 / CA5, P4] Position de rang impossible : rang inexistant, parcelle
    absente ou pépinière, ou rang déjà pris sans longueur de parcelle pour le partager."""


# ── Lecture des valeurs ──────────────────────────────────────────────────────

def _nombre(champ: str, valeur, mini: float, maxi: float, *, max_exclu: bool = False,
            decimales: int = 1) -> Optional[float]:
    if valeur is None:
        return None
    try:
        nombre = round(float(str(valeur).replace(",", ".")), decimales)
    except (TypeError, ValueError):
        raise GeometrieInvalideError(champ, f"{champ} : un nombre est attendu") from None
    hors = nombre < mini or (nombre >= maxi if max_exclu else nombre > maxi)
    if hors:
        borne = f"de {mini:g} à {maxi:g}" + (" exclu" if max_exclu else "")
        raise GeometrieInvalideError(champ, f"{champ} : valeur {borne} attendue (reçu {nombre:g})")
    return nombre


def _angle(champ: str, valeur) -> Optional[float]:
    """Un angle se ramène dans [0, 360[ : 360 = 0, −90 = 270."""
    if valeur is None:
        return None
    try:
        nombre = float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        raise GeometrieInvalideError(champ, f"{champ} : un angle en degrés est attendu") from None
    return round(nombre % 360, 1)


def _vocabulaire(champ: str, valeur, permis: tuple[str, ...], alias: dict) -> Optional[str]:
    if valeur is None:
        return None
    cle = str(valeur).strip().lower()
    cle = alias.get(cle, cle)
    if cle not in permis:
        raise GeometrieInvalideError(champ, f"{champ} : valeurs permises {', '.join(permis)}")
    return cle


def valider_geometrie_parcelle(champs: dict) -> dict:
    """[CA2] Normalise les champs de géométrie d'une parcelle, SANS rien écrire.

    Lève GeometrieInvalideError au premier champ refusé. x et y vont ensemble :
    une parcelle est placée ou ne l'est pas (G6), jamais à moitié.
    """
    propres: dict = {}
    if "forme" in champs:
        propres["forme"] = _vocabulaire("forme", champs["forme"], FORMES, _ALIAS_FORME)
    for axe in ("x_m", "y_m"):
        if axe in champs:
            propres[axe] = _nombre(axe, champs[axe], 0.0, POSITION_MAX, decimales=2)
    if ("x_m" in propres) != ("y_m" in propres) or (
        "x_m" in propres and (propres["x_m"] is None) != (propres["y_m"] is None)
    ):
        raise GeometrieInvalideError(
            "x_m", "x_m et y_m se donnent ensemble : une parcelle est placée ou à placer"
        )
    if "largeur_m" in champs:
        propres["largeur_m"] = _nombre("largeur_m", champs["largeur_m"], LARGEUR_MIN, LARGEUR_MAX)
    if "rotation_deg" in champs:
        propres["rotation_deg"] = _angle("rotation_deg", champs["rotation_deg"])
    if "sens_rangs" in champs:
        propres["sens_rangs"] = _vocabulaire("sens_rangs", champs["sens_rangs"], SENS_RANGS, _ALIAS_SENS)
    return propres


# ── Superficie (G1, G2) ──────────────────────────────────────────────────────

def superficie_posee(longueur_m: Optional[float], largeur_m: Optional[float]) -> Optional[float]:
    """[G1] L × l, au dixième ; None tant que l'une des deux manque."""
    if not longueur_m or not largeur_m:
        return None
    return round(float(longueur_m) * float(largeur_m), 1)


def _aligne(superficie: Optional[float], posee: Optional[float]) -> bool:
    return posee is not None and superficie is not None and abs(superficie - posee) <= TOLERANCE_SUPERFICIE


def recalculer_superficie(
    parcelle: Parcelle, *, avant: tuple, superficie_dite: bool, aligner: bool,
) -> Optional[str]:
    """[G1, G2] Après une écriture de géométrie, recalcule la superficie si — et
    seulement si — la fiche suivait la géométrie, était vide, ou si le jardinier
    demande l'alignement. Une superficie DITE dans le même appel l'emporte.

    `avant` = (longueur, largeur, superficie) d'avant l'écriture. Rend la ligne de
    modification, ou None si rien n'a changé.
    """
    if superficie_dite:
        return None
    posee = superficie_posee(parcelle.longueur_m, parcelle.largeur_m)
    if posee is None:
        return None
    longueur_avant, largeur_avant, superficie_avant = avant
    suivait = superficie_avant is None or _aligne(
        superficie_avant, superficie_posee(longueur_avant, largeur_avant)
    )
    if not (suivait or aligner) or _aligne(parcelle.superficie_m2, posee):
        return None
    parcelle.superficie_m2 = posee
    log.info("[US-326] Superficie de %r alignée sur la géométrie : %s m²", parcelle.nom, posee)
    return f"Superficie : {superficie_avant if superficie_avant is not None else '—'} → {posee:g} m²"


def ecart_superficie(parcelle: Parcelle) -> Optional[dict]:
    """[G2] « Surface posée 60 m², fiche parcelle 69 m² » — None sans écart."""
    posee = superficie_posee(parcelle.longueur_m, parcelle.largeur_m)
    if posee is None or parcelle.superficie_m2 is None or _aligne(parcelle.superficie_m2, posee):
        return None
    return {"posee_m2": posee, "fiche_m2": parcelle.superficie_m2}


# ── Écriture ─────────────────────────────────────────────────────────────────

def appliquer_geometrie_parcelle(parcelle: Parcelle, propres: dict) -> list[str]:
    """Écrit des champs DÉJÀ validés (`valider_geometrie_parcelle`). Pas de commit."""
    modifs: list[str] = []
    for champ, valeur in propres.items():
        if getattr(parcelle, champ) != valeur:
            modifs.append(f"{champ} : {getattr(parcelle, champ)} → {valeur}")
            setattr(parcelle, champ, valeur)
    if modifs:
        log.info("[US-326] Géométrie de la parcelle %r : %s", parcelle.nom, "; ".join(modifs))
    return modifs


def modifier_geometrie_potager(db: Session, ctx: TenantContext, champs: dict) -> Potager:
    """[US-326] Emprise, angle et orientation du nord du potager courant.

    Réservé à un éditeur. Tout est validé avant la moindre écriture.
    """
    require_role(ctx, "editor", "modifier la géométrie du potager")
    inconnus = set(champs) - set(CHAMPS_GEOMETRIE_POTAGER)
    if inconnus:
        raise GeometrieInvalideError(sorted(inconnus)[0], f"Champ(s) inconnu(s) : {', '.join(sorted(inconnus))}")
    propres: dict = {}
    for axe in ("emprise_longueur_m", "emprise_largeur_m"):
        if axe in champs:
            propres[axe] = _nombre(axe, champs[axe], EMPRISE_MIN, EMPRISE_MAX)
    if "angle_deg" in champs:
        propres["angle_deg"] = _angle("angle_deg", champs["angle_deg"])
    if "orientation_nord" in champs:
        propres["orientation_nord"] = _vocabulaire(
            "orientation_nord", champs["orientation_nord"], ORIENTATIONS, _ALIAS_ORIENTATION,
        )
    potager = db.query(Potager).filter(Potager.id == ctx.potager_id).first()
    if potager is None:
        raise LookupError(ctx.potager_id)
    for champ, valeur in propres.items():
        setattr(potager, champ, valeur)
    db.commit()
    log.info("[US-326] Géométrie du potager %s : %s", ctx.potager_id, propres)
    return potager


# ── Enregistrer le plan d'un coup (US-333 / CA3) ─────────────────────────────

#: Ce que l'éditeur peut écrire sur une parcelle : sa géométrie, sa longueur (champ de fiche, G1), son
#: nombre de rangs, et la demande d'aligner la superficie de la fiche (G2, jamais seule).
CHAMPS_EDITEUR: tuple[str, ...] = (
    *CHAMPS_GEOMETRIE_PARCELLE, "longueur_m", "nb_rangs", CHAMP_ALIGNER,
)


class PlanRefuseError(GeometrieInvalideError):
    """[US-333 / CA3, E6] Le plan est refusé EN ENTIER : `parcelle` dit laquelle, `champ` quel champ."""

    def __init__(self, parcelle: str, champ: str, message: str) -> None:
        super().__init__(champ, message)
        self.parcelle = parcelle


def _rangs_occupes(db: Session, ctx: TenantContext, parcelles: list[Parcelle]) -> dict[int, int]:
    """Les rangs occupés de chaque parcelle, par la MÊME répartition que `GET /plan` (US-198)."""
    from app.services import plan as svc_plan
    from app.services import repartition_rangs as svc_rangs

    occupation = svc_plan.get_occupation(db, ctx)
    repartition = svc_rangs.repartition_du_plan(db, parcelles, occupation, ctx.potager_id, _date.today())
    return {
        p.id: int(((repartition["dispositions"].get(p.nom) or {}).get("rangs_occupes")) or 0) for p in parcelles
    }


def enregistrer_plan(db: Session, ctx: TenantContext, parcelles: list[dict], potager: Optional[dict] = None) -> dict:
    """[US-333 / CA3] Écrit en UN seul appel la géométrie de toutes les parcelles modifiées et celle du potager.

    Tout est validé avant la moindre écriture, puis tout est écrit sous un seul `commit` : un refus
    n'écrit rien (`PlanRefuseError`, avec la parcelle et le champ). Pour chaque parcelle : géométrie
    (US-326), longueur, nombre de rangs — jamais sous le nombre de rangs occupés (E6) — et
    `aligner_superficie`, que l'éditeur n'envoie que sur le bouton « Mettre la fiche à 60 m² » (CA4).
    Rend `{"parcelles": n, "modifications": [...]}`. Réservé à un éditeur.
    """
    from utils.parcelles import ChampInvalide, valider_champs

    require_role(ctx, "editor", "modifier le plan")
    ids = [int(demande.get("id") or 0) for demande in parcelles]
    chargees = {
        p.id: p for p in db.query(Parcelle).filter(Parcelle.potager_id == ctx.potager_id, Parcelle.id.in_(ids)).all()
    } if ids else {}
    manquantes = [i for i in ids if i not in chargees]
    if manquantes:
        raise LookupError(manquantes[0])

    plan_valide: list[tuple[Parcelle, dict, dict, dict]] = []
    for demande in parcelles:
        parcelle = chargees[int(demande["id"])]
        champs = {cle: valeur for cle, valeur in demande.items() if cle != "id"}
        inconnus = sorted(set(champs) - set(CHAMPS_EDITEUR))
        if inconnus:
            raise PlanRefuseError(parcelle.nom, inconnus[0], f"Champ(s) non modifiable(s) sur le plan : {', '.join(inconnus)}")
        try:
            propres = valider_geometrie_parcelle(champs)
            fiche: dict = {}
            if "longueur_m" in champs:
                fiche["longueur"] = None if champs["longueur_m"] is None else str(champs["longueur_m"])
            if "nb_rangs" in champs:
                fiche["rangs"] = None if champs["nb_rangs"] is None else str(champs["nb_rangs"])
            valider_champs(**{cle: valeur for cle, valeur in fiche.items() if valeur is not None})
        except GeometrieInvalideError as e:
            raise PlanRefuseError(parcelle.nom, e.champ, f"{parcelle.nom} : {e}") from None
        except ChampInvalide as e:
            raise PlanRefuseError(parcelle.nom, {"longueur": "longueur_m", "rangs": "nb_rangs"}.get(e.champ, e.champ),
                                  f"{parcelle.nom} : {e}") from None
        plan_valide.append((parcelle, champs, propres, fiche))

    a_verifier = [p for p, champs, _, _ in plan_valide if champs.get("nb_rangs") is not None]
    if a_verifier:
        occupes = _rangs_occupes(db, ctx, a_verifier)
        for parcelle, champs, _, _ in plan_valide:
            if champs.get("nb_rangs") is not None and int(champs["nb_rangs"]) < occupes.get(parcelle.id, 0):
                raise PlanRefuseError(
                    parcelle.nom, "nb_rangs",
                    f"{parcelle.nom} : {occupes[parcelle.id]} rang{'s' if occupes[parcelle.id] > 1 else ''} "
                    f"occupé{'s' if occupes[parcelle.id] > 1 else ''} : on ne peut pas descendre à {int(champs['nb_rangs'])}.",
                )

    potager_propre: dict = {}
    if potager:
        inconnus = sorted(set(potager) - set(CHAMPS_GEOMETRIE_POTAGER))
        if inconnus:
            raise PlanRefuseError("", inconnus[0], f"Champ(s) inconnu(s) : {', '.join(inconnus)}")
        try:
            for axe in ("emprise_longueur_m", "emprise_largeur_m"):
                if axe in potager:
                    potager_propre[axe] = _nombre(axe, potager[axe], EMPRISE_MIN, EMPRISE_MAX)
            if "angle_deg" in potager:
                potager_propre["angle_deg"] = _angle("angle_deg", potager["angle_deg"])
            if "orientation_nord" in potager:
                potager_propre["orientation_nord"] = _vocabulaire(
                    "orientation_nord", potager["orientation_nord"], ORIENTATIONS, _ALIAS_ORIENTATION)
        except GeometrieInvalideError as e:
            raise PlanRefuseError("", e.champ, str(e)) from None

    modifications: list[str] = []
    for parcelle, champs, propres, fiche in plan_valide:
        avant = (parcelle.longueur_m, parcelle.largeur_m, parcelle.superficie_m2)
        modifs = appliquer_geometrie_parcelle(parcelle, propres)
        if "longueur_m" in champs and parcelle.longueur_m != champs["longueur_m"]:
            parcelle.longueur_m = None if champs["longueur_m"] is None else float(champs["longueur_m"])
            modifs.append(f"longueur_m : {avant[0]} → {parcelle.longueur_m}")
        if "nb_rangs" in champs and parcelle.nb_rangs != champs["nb_rangs"]:
            modifs.append(f"nb_rangs : {parcelle.nb_rangs} → {champs['nb_rangs']}")
            parcelle.nb_rangs = None if champs["nb_rangs"] is None else int(champs["nb_rangs"])
        ligne = recalculer_superficie(
            parcelle, avant=avant, superficie_dite=False, aligner=bool(champs.get(CHAMP_ALIGNER)))
        if ligne:
            modifs.append(ligne)
        modifications.extend(f"{parcelle.nom} — {m}" for m in modifs)
    if potager_propre:
        proprietaire = db.query(Potager).filter(Potager.id == ctx.potager_id).first()
        if proprietaire is None:
            raise LookupError(ctx.potager_id)
        for champ, valeur in potager_propre.items():
            setattr(proprietaire, champ, valeur)
        modifications.append(f"potager — {', '.join(potager_propre)}")
    db.commit()
    log.info("[US-333 / CA3] Plan enregistré (potager %s) : %d parcelle(s), %d modification(s)",
             ctx.potager_id, len(plan_valide), len(modifications))
    return {"parcelles": len(plan_valide), "modifications": modifications}


# ── Lecture pour GET /plan (G6, CA3) ─────────────────────────────────────────

def _valeur(objet, champ: str):
    """Une valeur de colonne simple, ou None — jamais un objet de substitution
    (une parcelle de test sans la colonne ne doit rien inventer, G6)."""
    valeur = getattr(objet, champ, None)
    return valeur if isinstance(valeur, (int, float, str)) and not isinstance(valeur, bool) else None


def largeur_posee(parcelle) -> Optional[float]:
    """[G1] La largeur POSÉE sur le plan, ou None (la déduction d'US-225 reste le repli)."""
    valeur = _valeur(parcelle, "largeur_m")
    return float(valeur) if isinstance(valeur, (int, float)) else None


def geometrie_parcelle(parcelle: Parcelle) -> dict:
    """[G6, CA3] La géométrie d'une parcelle telle que le plan la dessine.

    Une parcelle non placée est listée « à placer », SANS coordonnées : ni x ni y,
    ni position par défaut. Ses dimensions connues restent données.
    """
    x, y = _valeur(parcelle, "x_m"), _valeur(parcelle, "y_m")
    placee = x is not None and y is not None
    longueur, largeur = _valeur(parcelle, "longueur_m"), largeur_posee(parcelle)
    posee = superficie_posee(longueur, largeur)
    fiche = _valeur(parcelle, "superficie_m2")
    return {
        "forme": _valeur(parcelle, "forme"),
        "placee": placee,
        "a_placer": not placee,
        "x_m": x if placee else None,
        "y_m": y if placee else None,
        "longueur_m": longueur,
        "largeur_m": largeur,
        "rotation_deg": _valeur(parcelle, "rotation_deg"),
        "sens_rangs": _valeur(parcelle, "sens_rangs"),
        "superficie_posee_m2": posee,
        "ecart_superficie": (
            {"posee_m2": posee, "fiche_m2": fiche}
            if posee is not None and fiche is not None and not _aligne(fiche, posee) else None
        ),
    }


def geometrie_potager(potager: Optional[Potager]) -> dict:
    """[US-326] Emprise, angle et nord du potager ; tout à None s'il n'est pas posé."""
    return {
        champ: (getattr(potager, champ, None) if potager is not None else None)
        for champ in CHAMPS_GEOMETRIE_POTAGER
    }


def geometrie_du_potager(db: Session, potager_id: Optional[int]) -> dict:
    """[US-326] La géométrie du potager courant, plus les vocabulaires du plan
    (formes, sens des rangs, orientations) : l'écran ne les recopie jamais."""
    potager = db.query(Potager).filter(Potager.id == potager_id).first() if potager_id else None
    return {
        **geometrie_potager(potager),
        "vocabulaires": {
            "formes": list(FORMES), "sens_rangs": list(SENS_RANGS),
            "orientations": list(ORIENTATIONS),
        },
    }


# ── Position du rang d'une culture (CA5, G4, P4) ─────────────────────────────

def _nom_ligne(rang: dict) -> str:
    return " ".join(x for x in (rang.get("culture"), rang.get("variete")) if x) or "une culture"


def verifier_position_rang(
    db: Session,
    potager_id: Optional[int],
    *,
    parcelle: Optional[Parcelle],
    culture: Optional[str],
    variete: Optional[str],
    rang_position: Optional[int],
    rang_multiplicateur: Optional[int] = None,
    rang_longueur_m: Optional[float] = None,
    date_ref: Optional[_date] = None,
) -> None:
    """[CA5, G4, P4] Refuse une position de rang impossible AVANT d'écrire le geste.

    - une position exige une parcelle, qui n'est pas une pépinière ;
    - les rangs visés (position … position + multiplicateur − 1) existent si la
      parcelle déclare son nombre de rangs ;
    - une longueur occupée exige la longueur de la parcelle, et ne la dépasse pas ;
    - **P4** : un rang déjà POSÉ par une autre culture ne se partage que si la
      parcelle a une longueur — sinon, une culture par rang. Avec une longueur,
      les longueurs dites sur ce rang ne dépassent pas celle de la parcelle.

    Une culture placée par la seule numérotation d'installation (G3) n'est pas un
    obstacle : elle n'a pas de position réelle, elle prend le rang libre suivant.
    """
    if rang_position is None and rang_longueur_m is None:
        return
    if rang_position is None:
        raise PositionRangRefuseeError("Une longueur de rang se donne avec le numéro du rang (« au rang 3 »).")
    if parcelle is None:
        raise PositionRangRefuseeError(f"Au rang {rang_position} de quelle parcelle ?")
    if parcelle.est_pepiniere:
        raise PositionRangRefuseeError(f"{parcelle.nom} est une pépinière : ses rangs ne se numérotent pas.")
    nb = max(1, int(rang_multiplicateur or 1))
    dernier = rang_position + nb - 1
    if rang_position < 1 or dernier > 99:
        raise PositionRangRefuseeError("Un rang se numérote de 1 à 99.")
    if parcelle.nb_rangs is not None and dernier > parcelle.nb_rangs:
        raise PositionRangRefuseeError(
            f"{parcelle.nom} a {parcelle.nb_rangs} rang{'s' if parcelle.nb_rangs > 1 else ''} : "
            f"pas de rang {dernier}."
        )
    longueur = parcelle.longueur_m
    if rang_longueur_m is not None:
        if longueur is None:
            raise PositionRangRefuseeError(
                f"{parcelle.nom} n'a pas de longueur : une longueur de rang ne peut pas s'y mesurer."
            )
        if not 0 < rang_longueur_m <= longueur:
            raise PositionRangRefuseeError(
                f"Les rangs de {parcelle.nom} font {longueur:g} m : {rang_longueur_m:g} m ne tiennent pas."
            )

    # Ce que porte déjà chaque rang visé, d'après LA répartition du plan.
    from utils.parcelles import calcul_occupation_parcelles
    from app.services.repartition_rangs import repartition_du_plan, SOURCE_JARDINIER

    occupation = calcul_occupation_parcelles(db, date_ref, potager_id=potager_id)
    disposition = repartition_du_plan(db, [parcelle], occupation, potager_id, date_ref)[
        "dispositions"
    ].get(parcelle.nom) or {}
    meme_ligne = ((culture or "").lower(), (variete or "").lower())
    for numero in range(rang_position, dernier + 1):
        autres = [
            r for r in disposition.get("rangs", [])
            if r.get("numero") == numero and not r.get("libre")
            and r.get("position_source") == SOURCE_JARDINIER
            and ((r.get("culture") or "").lower(), (r.get("variete") or "").lower()) != meme_ligne
        ]
        if not autres:
            continue
        if longueur is None:
            raise PositionRangRefuseeError(
                f"Le rang {numero} de {parcelle.nom} porte déjà {_nom_ligne(autres[0])} : "
                f"sans longueur de parcelle, un rang ne porte qu'une culture. "
                f"Donnez la longueur de {parcelle.nom} pour partager ce rang."
            )
        dits = sum(r.get("part_m") or 0 for r in autres if r.get("part_source") == SOURCE_JARDINIER)
        if rang_longueur_m is not None and dits + rang_longueur_m > longueur + 1e-6:
            raise PositionRangRefuseeError(
                f"Le rang {numero} de {parcelle.nom} fait {longueur:g} m, dont {dits:g} m déjà pris : "
                f"{rang_longueur_m:g} m de plus ne tiennent pas."
            )


#: [US-328 / CA5] Au-delà, la part offerte n'est plus une fraction du rang : le rang entier.
PART_ENTIERE = 0.98


def longueur_de_la_part(db: Session, parcelle_id: Optional[int], part: Optional[float]) -> Optional[float]:
    """[US-328 / CA5, US-326 / P4] La longueur occupée sur un rang PARTAGÉ, en mètres.

    Une carte « À placer » posée sur un segment libre ne prend que la part libre du rang :
    elle se mesure ici, sur la longueur de la parcelle (la même que celle des places, US-227).
    None : rang entier, part inconnue, ou longueur non déclarée — aucune mesure inventée.
    """
    if part is None or part >= PART_ENTIERE or parcelle_id is None:
        return None
    longueur = db.query(Parcelle.longueur_m).filter(Parcelle.id == parcelle_id).scalar()
    if not longueur:
        return None
    return round(float(longueur) * float(part), 1)
