"""
app/services/repartition_rangs.py — Répartition des cultures en rangs [US-198]
------------------------------------------------------------------------------
Seul endroit où le potager est vu **en rangs**. La Vue plan (US-200), le détail
de parcelle (US-222) et la Pépinière (« où mettre les plants », US-217) lisent
tous cette répartition : deux écrans ne peuvent pas compter différemment la
place qui reste.

Lecture seule, en une passe : aucune écriture, aucun stock, aucune projection ni
confiance touchés. Le module ne recalcule ni l'occupation
(`utils.parcelles.calcul_occupation_parcelles`), ni les séries (US-070), ni la
phase du moment (US-194) — il les reçoit déjà calculées et se contente d'y
ajouter la dimension « rang ».

Les deux sens du mot « rang » ne se mélangent jamais :
  - le **nombre de rangs d'une parcelle** (US-197) est un dénominateur déclaré ;
  - le **rang d'un geste** (`Evenement.rang`) est un multiplicateur de quantité
    (« planté 4 salades sur 3 rangs » = 12 plants). Ce n'est pas une position.

La base ne sait donc pas qu'une tomate est « au rang 1 » : les rangs sont
numérotés **dans l'ordre d'installation** des cultures (arbitrage A5), ce que
`mode_numerotation` dit explicitement. Règles R1 à R9 : voir
`docs/domaines/plan-et-rangs.md`.
"""
from __future__ import annotations

import logging
from datetime import date as _date
from typing import Iterable, Optional

from sqlalchemy import case as sa_case
from sqlalchemy.orm import Session

from database.models import Evenement, Parcelle
from utils.stock import _cutoff_dt, calcul_lots_pepiniere

log = logging.getLogger("potager")

# ── Modes d'implantation [R4] ────────────────────────────────────────────────
MODE_RANG = "rang"
MODE_SURFACE = "surface"
MODE_POQUET = "poquet"

# L'unité suffit à décider du mode dans la quasi-totalité des cas (arbitrage A4).
_UNITES_SURFACE = frozenset({"m2", "m²", "metre carre", "metres carres"})
_UNITES_POQUET = frozenset({"poquet", "poquets"})

# Numérotation : un seul mode aujourd'hui — la position réelle d'un rang n'est
# pas connue de la base (US-203, optionnelle, ouvrira `positions` et `mixte`).
NUMEROTATION_ORDRE_INSTALLATION = "ordre_installation"

# Unité par défaut, identique à celle du plan d'occupation qu'on prolonge.
_UNITE_DEFAUT_PLANTATION = "plants"
_UNITE_DEFAUT_SEMIS = "graines"

# ── Places d'un rang [US-227 / R10 à R16] ────────────────────────────────────
#: [R12] Unités qui posent des INDIVIDUS sur le rang : chacun prend une place,
#: quel que soit ce qu'il contient — un poquet de trois graines tient une place.
_UNITES_PLACES = frozenset({
    "plants", "plant", "pied", "pieds", "graines", "graine", "poquet", "poquets",
})
#: [R15] Semis en ligne (US-199) : une LONGUEUR semée, pas des individus. Le rang
#: porte une part semée et des mètres restants, jamais des places — c'est tout
#: l'intérêt de l'unité `ml` : un rang de carottes n'a pas 24 « places ».
_UNITES_LIGNE = frozenset({
    "ml", "metre de rang", "metres de rang", "metre lineaire", "metres lineaires",
})


def _places_du_rang(
    longueur_m: Optional[float], espacement_cm: Optional[float]
) -> Optional[int]:
    """[R10] ⌊ longueur × 100 ÷ espacement ⌋, au minimum 1.

    `None` dès qu'une des deux mesures manque — jamais zéro, jamais une
    estimation : un rang sans longueur ou sans espacement n'a pas de places,
    il en a d'inconnues (R11).
    """
    if not longueur_m or not espacement_cm:
        return None
    return max(1, int(float(longueur_m) * 100 // float(espacement_cm)))


def _mesures_du_rang(
    mode: str,
    unite: Optional[str],
    longueur_m: Optional[float],
    espacement_cm: Optional[int],
    quantite_par_rang: Optional[float],
) -> dict:
    """[R10 à R15] Ce qu'un rang OCCUPÉ porte comme capacité, ou rien de faux.

    Les quatre champs de places sont toujours présents, à `None` quand le calcul
    n'a pas de quoi se faire. Un semis en ligne les laisse tous à `None` et porte
    à la place sa part semée et ses mètres restants.

    ⚠️ `places_prises` est **plafonné aux places du rang** — c'est ce qui se
    dessine sur la piste (US-228) — et l'excédent part dans `depassement_places`
    (R14). La quantité déclarée par le jardinier, elle, n'est jamais retouchée :
    elle reste dans `quantite_par_rang` (US-198 / R3), et
    `places_prises + depassement_places` la redonne toujours.
    """
    cle_unite = (unite or "").strip().lower()
    mesures: dict = {
        "espacement_rang_cm": espacement_cm,
        "places": None,
        "places_prises": None,
        "places_restantes": None,
        "depassement_places": None,
    }

    # [R15] Semis en ligne : le rang se mesure en mètres, pas en pieds.
    if cle_unite in _UNITES_LIGNE:
        metres = float(quantite_par_rang or 0)
        if longueur_m:
            longueur = float(longueur_m)
            mesures["part_semee"] = min(1.0, round(metres / longueur, 2))
            mesures["metres_restants"] = round(max(0.0, longueur - metres), 1)
            mesures["depassement_metres"] = round(max(0.0, metres - longueur), 1)
        else:
            mesures["part_semee"] = None
            mesures["metres_restants"] = None
            mesures["depassement_metres"] = None
        return mesures

    # [R11] Trois cas d'échec, et seulement trois : longueur absente, espacement
    # absent, implantation en surface. Aucun repli, aucun espacement moyen.
    if mode == MODE_SURFACE:
        return mesures
    places = _places_du_rang(longueur_m, espacement_cm)
    if places is None:
        return mesures
    mesures["places"] = places

    # [R12] Une unité qui ne pose pas d'individus (des grammes, des bottes) ne
    # prend pas de places : la capacité du rang reste connue, ce qui l'occupe non.
    if cle_unite not in _UNITES_PLACES:
        return mesures

    declarees = int(quantite_par_rang or 0)
    mesures["places_prises"] = min(declarees, places)
    mesures["places_restantes"] = max(0, places - declarees)   # [R13] jamais négatif
    mesures["depassement_places"] = max(0, declarees - places)  # [R14] signalement
    return mesures



def mode_implantation(unite: Optional[str]) -> str:
    """[R4] Mode d'implantation déduit de la seule unité de quantité."""
    cle = (unite or "").strip().lower()
    if cle in _UNITES_SURFACE:
        return MODE_SURFACE
    if cle in _UNITES_POQUET:
        return MODE_POQUET
    return MODE_RANG


def cle_ligne(parcelle_nom: Optional[str], entree: dict) -> tuple:
    """
    [R1] Clé d'une ligne du plan — culture × variété × unité × nature du geste,
    exactement le regroupement de `calcul_occupation_parcelles`. Aucune ligne
    ajoutée, aucune retirée : la répartition ne fait que s'indexer dessus.
    """
    est_semis = entree.get("type_action") == "semis"
    unite = entree.get("unite") or (
        _UNITE_DEFAUT_SEMIS if est_semis else _UNITE_DEFAUT_PLANTATION
    )
    return (
        parcelle_nom,
        entree.get("culture") or "",
        entree.get("variete") or "",
        unite,
        est_semis,
    )


def _jour(valeur) -> Optional[_date]:
    """Ramène un `datetime` ou une `date` à une date, `None` si rien."""
    if valeur is None:
        return None
    return valeur.date() if hasattr(valeur, "date") else valeur


def _rangs_declares_a_installation(
    db: Session, potager_id: Optional[int], date_ref: Optional[_date],
    installations: Optional[list[dict]] = None,
) -> dict[tuple, int]:
    """
    [R2, CA4, CA5] Nombre de rangs dit à l'installation de chaque ligne, en UNE
    lecture — jamais une requête par parcelle ni par ligne.

    Somme des multiplicateurs `Evenement.rang` **réellement dictés** par les
    gestes d'installation pris en compte à la date de référence : une ligne née
    de deux plantations « sur 2 rangs » puis « sur 1 rang » occupe 3 rangs.

    ⚠️ Les gestes qui ne disent RIEN ne comptent pour rien ici, et la ligne
    retombe sur son rang unique (`repartition_du_plan`). Les compter pour un
    rang chacun — ce que faisait un `coalesce(rang, 1)` — inventait un rang par
    geste : quatre semis de tomate le même jour occupaient quatre rangs de la
    planche, alors que le plan d'occupation n'y voit qu'une seule ligne (R1) et
    que des semis échelonnés ne se séparent jamais (limite assumée du module).
    """
    cutoff = _cutoff_dt(date_ref)
    requete = (
        db.query(
            sa_case((Parcelle.actif.is_(True), Parcelle.nom), else_=None).label("parcelle_nom"),
            Evenement.culture,
            Evenement.variete,
            Evenement.unite,
            Evenement.type_action,
            Evenement.rang,
            Evenement.quantite,
            Evenement.date,
            Evenement.id,
        )
        .outerjoin(Parcelle, Evenement.parcelle_id == Parcelle.id)
        .filter(Evenement.type_action.in_(("plantation", "semis")))
        .order_by(Evenement.date, Evenement.id)
    )
    if potager_id is not None:
        requete = requete.filter(Evenement.potager_id == potager_id)
    if cutoff is not None:
        requete = requete.filter(Evenement.date <= cutoff)

    rangs: dict[tuple, int] = {}
    for parcelle_nom, culture, variete, unite, type_action, rang, quantite, date, identifiant in requete.all():
        est_semis = type_action == "semis"
        cle = (
            parcelle_nom,
            culture or "",
            variete or "",
            unite or (_UNITE_DEFAUT_SEMIS if est_semis else _UNITE_DEFAUT_PLANTATION),
            est_semis,
        )
        rangs[cle] = rangs.get(cle, 0) + int(rang or 0)
        if installations is not None:
            installations.append({
                "cle": cle, "rangs": rang,
                "quantite": (quantite or 0) * (rang or 1),
                "date": date, "id": identifiant,
            })
    return rangs


def _quantite_par_rang(quantite: float, rangs: int, mode: str) -> float:
    """
    [R3] Quantité portée par CHAQUE rang d'une ligne : quantité ÷ rangs, arrondie
    à l'unité pour ce qui se compte, au dixième pour les m², jamais zéro quand la
    quantité ne l'est pas — « 1 plant par rang » est faux de peu, « 0 plant par
    rang » est faux tout court.
    """
    quantite = quantite or 0
    rangs = max(1, rangs)
    brut = quantite / rangs
    if mode == MODE_SURFACE:
        arrondi = round(brut, 1)
        return arrondi if arrondi > 0 or quantite <= 0 else 0.1
    arrondi = round(brut)
    return float(arrondi) if arrondi > 0 or quantite <= 0 else 1.0


def _affectations_par_rang(
    parcelle: Parcelle, entrees: list[dict], rangs_installes: dict[tuple, int],
    installations: list[dict], attributs: dict[str, dict], longueur: Optional[float],
) -> dict[tuple, list[dict]]:
    """[US-198 / CA10-19] Rejoue les plantations implicites sans modifier le journal."""
    gestes_par_ligne: dict[tuple, list[dict]] = {}
    for geste in installations:
        gestes_par_ligne.setdefault(geste["cle"], []).append(geste)
    affectations: dict[tuple, list[dict]] = {}
    capacites: dict[tuple, int] = {}
    actions: list[dict] = []
    for entree in entrees:
        cle = cle_ligne(parcelle.nom, entree)
        affectations[cle] = []
        quantite = entree.get("nb_plants") or 0
        gestes = gestes_par_ligne.get(cle, [])
        capacite = _places_du_rang(
            longueur, (attributs.get((entree.get("culture") or "").lower()) or {}).get("espacement_rang_cm"),
        )
        automatique = (
            not cle[4] and cle[3] in {"plants", "plant", "pied", "pieds"}
            and parcelle.nb_rangs is not None and capacite is not None
            and not parcelle.est_pepiniere
            and (not gestes or any(geste["rangs"] is None for geste in gestes))
            and (not gestes or sum(geste["quantite"] for geste in gestes) == quantite)
        )
        if automatique:
            capacites[cle] = capacite
            actions.extend(gestes or [{
                "cle": cle, "rangs": None, "quantite": quantite,
                "date": entree.get("date_plantation"), "id": 0,
            }])
        else:
            compte = max(1, int(rangs_installes.get(cle, 1) or 1))
            actions.append({
                "cle": cle, "rangs": compte,
                "quantite_fixe": _quantite_par_rang(quantite, compte, mode_implantation(cle[3])),
                "date": entree.get("date_plantation"),
                "id": gestes[0]["id"] if gestes else 0,
            })
    actions.sort(key=lambda action: (
        action["date"].isoformat() if action["date"] else "9999",
        action["id"], action["cle"][1:],
    ))
    numero = 0
    for action in actions:
        cle = action["cle"]
        rangs = affectations[cle]
        if action["rangs"] is not None:
            compte = max(1, int(action["rangs"]))
            quantite = action.get("quantite_fixe", action.get("quantite", 0) / compte)
            for _ in range(compte):
                numero += 1
                rangs.append({"numero": numero, "quantite_par_rang": quantite})
            continue
        residuel = action["quantite"]
        capacite = capacites[cle]
        for rang in rangs:
            ajout = min(residuel, max(0, capacite - rang["quantite_par_rang"]))
            rang["quantite_par_rang"] += ajout
            residuel -= ajout
        while residuel > 0 and numero < parcelle.nb_rangs:
            numero += 1
            ajout = min(residuel, capacite)
            rangs.append({"numero": numero, "quantite_par_rang": ajout})
            residuel -= ajout
        if residuel > 0:
            if not rangs:
                numero += 1
                rangs.append({"numero": numero, "quantite_par_rang": 0})
            rangs[-1]["quantite_par_rang"] += residuel
    return affectations


def _lots_en_cours_par_parcelle(
    db: Session, potager_id: Optional[int], date_ref: Optional[_date]
) -> dict[str, int]:
    """
    [R8] Nombre de lots de semis encore en cours dans chaque parcelle pépinière,
    en UNE lecture. Un lot est « en cours » tant qu'il occupe la pépinière : des
    graines pas encore levées, ou des plants en godet pas encore plantés.
    """
    lots: dict[str, int] = {}
    for lot in calcul_lots_pepiniere(db, date_ref, potager_id=potager_id):
        nom = lot.get("parcelle")
        if not nom:
            continue
        occupe = (lot.get("graines_en_germination") or 0) > 0 or (
            lot.get("stock_residuel_godet") or 0
        ) > 0
        if occupe:
            lots[nom] = lots.get(nom, 0) + 1
    return lots


def repartition_du_plan(
    db: Session,
    parcelles: Iterable[Parcelle],
    occupation: dict,
    potager_id: Optional[int] = None,
    date_ref: Optional[_date] = None,
    attributs_culture: Optional[dict[str, dict]] = None,
) -> dict:
    """
    [US-198 / CA1, CA2, CA3] Répartition en rangs de tout le plan, en lecture seule.

    `occupation` est la structure déjà calculée par
    `utils.parcelles.calcul_occupation_parcelles` — elle n'est jamais recalculée
    ici, ni modifiée.

    [US-227 / CA1, CA6] `attributs_culture` est l'index de fiches culture que
    `GET /plan` lit DÉJÀ (`app.services.plan.attributs_par_culture`), passé tel
    quel : la dérivation d'espacement d'US-226 n'est ni dupliquée ni relue, et
    les places ne coûtent aucune requête supplémentaire. Sans cet index, les
    rangs n'ont simplement pas de places (R11) — rien d'autre ne change.

    Retourne :

    ```
    {
      "lignes":       {clé de ligne: {mode_implantation, rangs, quantite_par_rang,
                                      date_installation, numeros_rangs}},
      "dispositions": {nom de parcelle: {rangs_declares, rangs_occupes, rangs_libres,
                                         depassement, rangs, mode_numerotation,
                                         nb_lots_en_cours}},
      "totaux":       {...},
    }
    ```

    La clé de ligne se reconstruit avec `cle_ligne(nom_parcelle, entree)`.
    """
    parcelles = list(parcelles)
    attributs = attributs_culture or {}
    installations: list[dict] = []
    rangs_installes = _rangs_declares_a_installation(db, potager_id, date_ref, installations)
    pepinieres = {p.nom for p in parcelles if p.est_pepiniere}
    lots_par_parcelle = (
        _lots_en_cours_par_parcelle(db, potager_id, date_ref) if pepinieres else {}
    )

    lignes: dict[tuple, dict] = {}
    dispositions: dict[str, dict] = {}

    # ── Les cultures non localisées [R9] : un bloc à part, sans rang ──────────
    for entree in occupation.get(None, []) or []:
        lignes[cle_ligne(None, entree)] = {
            "mode_implantation": mode_implantation(entree.get("unite")),
            "rangs": None,
            "quantite_par_rang": None,
            "date_installation": _jour(entree.get("date_plantation")),
            "numeros_rangs": [],
        }

    for parcelle in parcelles:
        entrees = list(occupation.get(parcelle.nom, []) or [])

        # [R5] De la plus anciennement installée à la plus récente ; à égalité,
        # par nom de culture — deux lectures du même plan donnent les mêmes rangs.
        entrees.sort(
            key=lambda e: (
                _jour(e.get("date_plantation")) or _date.max,
                (e.get("culture") or "").lower(),
                (e.get("variete") or "").lower(),
            )
        )

        # [US-227 / R10] La longueur est celle de la PARCELLE, partagée par tous
        # ses rangs. Une pépinière n'a pas de places : on n'y plante pas au
        # cordeau, on y fait lever des lots (R8) — ses rangs restent muets.
        longueur = None if parcelle.est_pepiniere else getattr(parcelle, "longueur_m", None)
        # [R16] La capacité d'exemple d'un rang libre se prend sur une culture
        # RÉELLEMENT présente dans cette parcelle — la première installée dont
        # l'espacement est connu — jamais sur un espacement par défaut.
        capacite_exemple: Optional[dict] = None

        affectations = _affectations_par_rang(
            parcelle, entrees, rangs_installes, installations, attributs, longueur,
        )
        rangs_du_plan: list[dict] = []
        numero = 0
        for entree in entrees:
            cle = cle_ligne(parcelle.nom, entree)
            mode = mode_implantation(entree.get("unite"))
            repartition = affectations[cle]
            numeros = [rang["numero"] for rang in repartition]
            rangs = len(numeros)
            numero = max(numero, max(numeros, default=0))

            quantite = _quantite_par_rang(entree.get("nb_plants") or 0, rangs, mode)
            lignes[cle] = {
                "mode_implantation": mode,
                "rangs": rangs,
                "quantite_par_rang": quantite,
                "date_installation": _jour(entree.get("date_plantation")),
                "numeros_rangs": numeros,
            }

            espacement = (
                attributs.get((entree.get("culture") or "").lower()) or {}
            ).get("espacement_rang_cm")
            for affectation in repartition:
                mesures = _mesures_du_rang(
                    mode=mode, unite=cle[3], longueur_m=longueur,
                    espacement_cm=espacement,
                    quantite_par_rang=affectation["quantite_par_rang"],
                )
                if capacite_exemple is None and mesures["places"]:
                    capacite_exemple = {
                        "nombre": mesures["places"], "culture": entree.get("culture"),
                    }
                rangs_du_plan.append({
                    **affectation,
                    "libre": False,
                    "culture": entree.get("culture"),
                    "variete": entree.get("variete"),
                    "unite": cle[3],
                    **mesures,
                })

        rangs_du_plan.sort(key=lambda rang: rang["numero"])
        rangs_occupes = numero
        declares = parcelle.nb_rangs
        # [R6] Sans nombre déclaré, les rangs libres sont « inconnus » (None),
        # jamais zéro : une parcelle non mesurée n'est pas une parcelle pleine.
        rangs_libres = None if declares is None else max(0, declares - rangs_occupes)
        # [R7] Plus de rangs occupés que déclarés : aucune culture n'est masquée,
        # c'est la parcelle qui porte l'écart.
        depassement = 0 if declares is None else max(0, rangs_occupes - declares)

        for n in range(rangs_occupes + 1, (declares or 0) + 1):
            rangs_du_plan.append({
                "numero": n,
                "libre": True,
                "culture": None,
                "variete": None,
                "unite": None,
                # [R16] Un rang libre n'a pas de places : elles dépendraient de ce
                # qu'on y mettrait. Il porte sa longueur, et — si la parcelle
                # abrite déjà une culture d'espacement connu — ce que ce rang
                # donnerait de CETTE culture-là, nommée.
                "longueur_m": longueur,
                "capacite_exemple": capacite_exemple,
            })

        dispositions[parcelle.nom] = {
            "rangs_declares": declares,
            "rangs_occupes": rangs_occupes,
            "rangs_libres": rangs_libres,
            "depassement": depassement,
            "rangs": rangs_du_plan,
            "mode_numerotation": NUMEROTATION_ORDRE_INSTALLATION,
            # [R8] Une pépinière porte ses lots en cours, pas des lignes de semis.
            "nb_lots_en_cours": (
                lots_par_parcelle.get(parcelle.nom, 0) if parcelle.est_pepiniere else None
            ),
        }

    totaux = _totaux(parcelles, dispositions)

    log.info(
        "[US-198] Répartition en rangs : %d parcelles, %d lignes, %d rangs occupés "
        "sur %d déclarés (date_ref=%s)",
        len(parcelles), len(lignes), totaux["rangs_occupes"], totaux["rangs_declares"],
        date_ref.isoformat() if date_ref else "aujourd'hui",
    )
    return {"lignes": lignes, "dispositions": dispositions, "totaux": totaux}


def _totaux(parcelles: list[Parcelle], dispositions: dict[str, dict]) -> dict:
    """
    [CA3] Totaux du plan. Le pourcentage d'occupation en rangs ne mêle jamais une
    parcelle sans dénominateur : une planche sans nombre de rangs déclaré n'entre
    ni au numérateur ni au dénominateur, elle est seulement comptée à part.

    [US-227 / R17, CA4] S'y ajoute le seul total que les places autorisent : le
    nombre de parcelles **sans longueur**, celles dont aucun rang n'est chiffré.
    Aucun total de places, aucun pourcentage de remplissage — une place est une
    capacité de rang, jamais un second taux d'occupation (RT13, arbitrage A25).
    """
    superficie = 0.0
    rangs_declares = 0
    rangs_occupes = 0
    sans_nb_rangs = 0
    sans_longueur = 0
    libres_par_parcelle: list[dict] = []

    for parcelle in parcelles:
        disposition = dispositions.get(parcelle.nom, {})
        superficie += parcelle.superficie_m2 or 0.0
        if getattr(parcelle, "longueur_m", None) is None:
            sans_longueur += 1
        if parcelle.nb_rangs is None:
            sans_nb_rangs += 1
        elif not parcelle.est_pepiniere:
            rangs_declares += parcelle.nb_rangs
            rangs_occupes += disposition.get("rangs_occupes", 0)
        libres_par_parcelle.append({
            "parcelle_id": parcelle.id,
            "parcelle": parcelle.nom,
            "rangs_libres": disposition.get("rangs_libres"),
        })

    return {
        "superficie_totale_m2": round(superficie, 2),
        "rangs_declares": rangs_declares,
        "rangs_occupes": rangs_occupes,
        "occupation_rangs_pct": (
            round(rangs_occupes / rangs_declares * 100) if rangs_declares else None
        ),
        "parcelles_sans_nb_rangs": sans_nb_rangs,
        # [US-227 / R17] Combien de planches n'ont aucun rang chiffré, faute de
        # longueur déclarée. C'est un compte de parcelles, pas de places.
        "parcelles_sans_longueur": sans_longueur,
        "rangs_libres_par_parcelle": libres_par_parcelle,
    }
