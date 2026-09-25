"""
app/services/vue_cultures.py — Lecture unique de l'écran Cultures [US-204]
---------------------------------------------------------------------------
L'écran Cultures (« Mes cultures ») dit *quoi* et *quand*, pas *combien*
(Stocks) : pour chaque culture du référentiel visible par le potager,
présence au potager (US-194, US-065), calendrier de la zone (US-176),
confiance du moment (US-178, US-180) et fenêtre utile.

Composer cela côté front demanderait quatre lectures et recalculerait des
règles dans l'interface (CA7). Ce module compose une lecture UNIQUE côté
serveur, à partir des services existants, sans aucune règle nouvelle
dupliquée : la confiance vient de `confiance_semis.confiances_du_plan`
(exactement celle du Plan et de Stocks, CA4), la présence de
`recalage_calendrier.phases_du_plan` (exactement celle du Plan, US-194), les
lots de `stock.calcul_lots_pepiniere` (exactement ceux de la Pépinière,
US-065).

Une seule lecture météo pour tout l'écran (CA7) : `confiances_du_plan` la lit
une fois, quel que soit le nombre de cultures.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.services import calendrier_cultural as svc_calendrier
from app.services import confiance_semis as svc_confiance
from app.services import familles as svc_familles
from app.services import recalage_calendrier as svc_recalage
from app.services import stock as svc_stock
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement
from utils.culture_resolve import normaliser_culture

#: [CA1, CA5 ter] Les quatre phases du référentiel, dans l'ordre de la frise.
PHASES_ZONE: tuple[str, ...] = (
    svc_calendrier.PHASE_SEMIS_PEPINIERE, svc_calendrier.PHASE_SEMIS_PLEINE_TERRE,
    svc_calendrier.PHASE_PLANTATION, svc_calendrier.PHASE_RECOLTE,
)
#: [CA5] Les trois gestes qu'une fenêtre peut concerner — mêmes noms que les
#: phases du référentiel (`ACTION_* == PHASE_*`, confiance_semis les reprend).
GESTES: tuple[str, ...] = (
    svc_confiance.ACTION_SEMIS_PEPINIERE, svc_confiance.ACTION_SEMIS_PLEINE_TERRE,
    svc_confiance.ACTION_PLANTATION,
)

#: [CA4] Équivalent écrit de l'étoile — décision produit écrite UNE fois, ici,
#: pour cette lecture (le Plan et Stocks en gardent chacun leur propre copie
#: minimale côté front, comme `NIVEAU_COURT` de `frontend/src/lib/confiance.js`).
EQUIVALENT_ETOILES: dict[int, str] = {1: "faible", 2: "moyenne", 3: "élevée"}

#: [CA3] Ordre du cycle, du moins au plus avancé — sert à choisir la phase la
#: plus avancée présente, la même hiérarchie que `PHASES` du front (US-194).
ORDRE_PHASES: tuple[str, ...] = ("semee", "en_place", "en_recolte")

#: [CA6] Décisions produit écrites UNE fois : au plus trois suggestions, à
#: partir de deux étoiles.
PLAFOND_SUGGESTIONS = 3
SEUIL_ETOILES_SUGGESTION = 2

ETAT_MAINTENANT = "maintenant"
ETAT_BIENTOT = "bientot"
ETAT_PLUS_TARD = "plus_tard"
ETAT_AUCUNE = "aucune"
_PRIORITE_ETAT: dict[str, int] = {ETAT_MAINTENANT: 0, ETAT_BIENTOT: 1, ETAT_PLUS_TARD: 2, ETAT_AUCUNE: 3}


@dataclass(frozen=True)
class LigneCulture:
    """[CA1] Une ligne de la vue Cultures — tout ce qu'une carte (US-205) affiche."""

    culture: str
    nom_culture: str
    hors_referentiel: bool
    famille: Optional[str]
    au_potager: bool
    #: [CA1] Mois des quatre phases de la zone — la frise de la carte, telle
    #: quelle (dict vide par phase si la culture n'a pas de calendrier).
    mois_zone: dict[str, list[int]]
    a_calendrier: bool
    #: [CA5 ter] Union des mois de semis et de plantation — le filtre par mois.
    mois_actifs: tuple[int, ...]
    #: [CA3] Présence au potager.
    nb_varietes: int
    #: [US-205 / CA4] Noms des variétés en terre ou en pépinière — la recherche
    #: de l'écran Cultures y porte, en plus du nom de la culture.
    varietes: tuple[str, ...]
    nb_parcelles: int
    repartition_phases: dict[str, int]
    phase_plus_avancee: Optional[str]
    nb_lots_pepiniere: int
    #: [CA4] Confiance du moment — même évaluation que le Plan et Stocks.
    etoiles: Optional[int]
    confiance_equivalent: Optional[str]
    #: [CA5] Fenêtre : état brut, geste brut, mois bruts — le libellé est assemblé au front.
    fenetre_etat: str
    fenetre_geste: Optional[str]
    fenetre_mois: tuple[int, ...]
    #: [CA6] Suggestion de la semaine.
    suggestion: bool = False


@dataclass(frozen=True)
class VueCultures:
    zone_climatique: str
    zone_climatique_origine: str
    attributions: tuple[str, ...]
    familles: tuple[str, ...]
    cultures: tuple[LigneCulture, ...]
    effectif_toutes: int
    effectif_au_potager: int
    #: [CA10] Météo indisponible : la confiance de TOUTES les cultures reste
    #: sans étoile, la réponse le dit plutôt que de laisser deviner pourquoi.
    meteo_disponible: bool


def _etat_fenetre(fenetre, date_ref: _date) -> str:
    """
    [CA5] État d'une fenêtre à `date_ref` — même arithmétique que la règle R1
    de la confiance (`confiance_semis._regle_fenetre`) : « maintenant » dans la
    fenêtre, « bientôt » le mois qui la précède (elle s'ouvre le mois
    prochain), « plus tard » sinon. Gère l'enjambement de l'année (ex. fenêtre
    novembre → février) via `mois_debut`/`mois_fin`, jamais une comparaison de
    liste brute qui s'y tromperait.
    """
    if fenetre is None:
        return ETAT_AUCUNE
    if date_ref.month in fenetre.mois:
        return ETAT_MAINTENANT
    avant = fenetre.mois_debut - 1 or 12
    if date_ref.month == avant:
        return ETAT_BIENTOT
    return ETAT_PLUS_TARD


def _fenetre_de_la_culture(itineraire, date_ref: _date) -> tuple[str, Optional[str], tuple[int, ...]]:
    """[CA5] Le meilleur état de fenêtre parmi les trois gestes : maintenant
    avant bientôt avant plus tard avant aucune ; à état égal, l'ordre du geste."""
    if itineraire is None:
        return ETAT_AUCUNE, None, ()
    candidats = []
    for geste in GESTES:
        fenetre = itineraire.fenetre(geste)
        etat = _etat_fenetre(fenetre, date_ref)
        mois = tuple(fenetre.mois) if fenetre is not None else ()
        candidats.append((geste, etat, mois))
    geste, etat, mois = min(candidats, key=lambda c: (_PRIORITE_ETAT[c[1]], GESTES.index(c[0])))
    return etat, (geste if etat != ETAT_AUCUNE else None), mois


def _mois_actifs(itineraire) -> tuple[int, ...]:
    """[CA5 ter] Union des mois de semis (pépinière ou pleine terre) et de
    plantation — jamais la récolte, qui ne se met pas en terre."""
    if itineraire is None:
        return ()
    mois: set[int] = set()
    for phase in (
        svc_calendrier.PHASE_SEMIS_PEPINIERE, svc_calendrier.PHASE_SEMIS_PLEINE_TERRE,
        svc_calendrier.PHASE_PLANTATION,
    ):
        fenetre = itineraire.fenetre(phase)
        if fenetre is not None:
            mois |= set(fenetre.mois)
    return tuple(sorted(mois))


def _lot_en_cours(lot: dict) -> bool:
    """[CA3] Un lot compte comme « en cours » tant qu'il reste quelque chose
    en attente : des graines pas toutes levées, ou des plants encore en godet
    (`stock_residuel_godet`) — un lot entièrement planté, vendu ou perdu ne
    compte plus (mêmes champs que US-065, `calcul_lots_pepiniere`)."""
    return lot.get("etat_germination") == "en_cours" or (lot.get("stock_residuel_godet") or 0) > 0


def composer_vue_cultures(db: Session, ctx: TenantContext, date_ref: _date) -> VueCultures:
    """[CA1-CA10] La lecture unique de l'écran Cultures."""
    potager_id = ctx.potager_id

    # ── Référentiel visible par le potager (CA2 « Toutes ») ──────────────────
    fiches_referentiel = (
        db.query(CultureConfig)
        .filter((CultureConfig.potager_id == potager_id) | (CultureConfig.potager_id.is_(None)))
        .order_by(CultureConfig.nom)
        .all()
    )
    noms_referentiel: dict[str, str] = {}
    for f in fiches_referentiel:
        noms_referentiel.setdefault(normaliser_culture(f.nom), f.nom)

    # ── Cultures au potager, y compris hors référentiel (CA2) ────────────────
    requete_evenements = db.query(Evenement.culture).filter(
        Evenement.type_action.in_(["semis", "mise_en_godet", "plantation"]),
        Evenement.culture.isnot(None),
    )
    if potager_id is not None:
        requete_evenements = requete_evenements.filter(Evenement.potager_id == potager_id)
    noms_evenements: dict[str, str] = {}
    for (nom,) in requete_evenements.distinct().all():
        if nom and nom.strip():
            noms_evenements.setdefault(normaliser_culture(nom), nom)

    univers = dict(noms_referentiel)
    univers.update(noms_evenements)  # le nom tel qu'événementé prévaut pour l'affichage

    # ── Une seule lecture des tuiles / phases / lots pour tout l'écran (CA7) ─
    _tuiles, _index = svc_recalage.lire_tuiles(db, univers.keys(), potager_id, date_ref)
    phases = svc_recalage.phases_du_plan(db, univers.keys(), potager_id, date_ref)
    lots = svc_stock.calcul_lots_pepiniere(db, ctx, date_ref=date_ref)

    varietes_par_culture: dict[str, set[str]] = {}
    parcelles_par_culture: dict[str, set[int]] = {}
    phases_par_culture: dict[str, list[str]] = {}
    for (parcelle_id, culture, variete), info in phases.items():
        varietes_par_culture.setdefault(culture, set()).add(variete)
        parcelles_par_culture.setdefault(culture, set()).add(parcelle_id)
        phases_par_culture.setdefault(culture, []).append(info["phase"])

    lots_par_culture: dict[str, int] = {}
    for lot in lots:
        if not _lot_en_cours(lot):
            continue
        cle = normaliser_culture(lot.get("culture") or "")
        if cle:
            lots_par_culture[cle] = lots_par_culture.get(cle, 0) + 1

    au_potager = {
        c for c in univers
        if c in phases_par_culture or lots_par_culture.get(c, 0) > 0
    }

    # ── Familles (US-067) et confiance (US-178, US-180) en une lecture chacune ─
    familles = svc_familles.familles_par_culture(db, ctx)
    confiances = svc_confiance.confiances_du_plan(db, univers.keys(), date_ref, potager_id)
    # [CA10] Pas de seconde lecture météo (CA7) : R3/R4 indéterminées disent déjà
    # que la météo n'a pas pu être lue — la même lecture partagée par toutes les
    # évaluations de `confiances_du_plan` (CA6), jamais relue ici.
    meteo_disponible = not any(
        m.etat == svc_confiance.ETAT_INDETERMINE
        for entree in confiances.values()
        for action in entree.actions
        for m in action.motifs
        if m.regle in (svc_confiance.R3_GEL_ANNONCE, svc_confiance.R4_NUITS_DOUCES)
    )

    zone, origine, altitude = svc_calendrier.zone_et_altitude_du_potager(db, potager_id)
    attributions: list[str] = []
    lignes: list[LigneCulture] = []

    for cle, nom in sorted(univers.items(), key=lambda kv: kv[1].lower()):
        calendrier = svc_calendrier.lire_calendrier(db, nom, potager_id)
        itineraire = calendrier.itineraires[0] if calendrier.itineraires else None
        for fenetre in (itineraire.fenetre(p) for p in PHASES_ZONE) if itineraire else ():
            if fenetre is not None and fenetre.attribution and fenetre.attribution not in attributions:
                attributions.append(fenetre.attribution)

        mois_zone = {
            phase: (itineraire.fenetre(phase).mois if itineraire and itineraire.fenetre(phase) else [])
            for phase in PHASES_ZONE
        }

        phases_lignes = phases_par_culture.get(cle, [])
        phase_plus_avancee = max(phases_lignes, key=ORDRE_PHASES.index) if phases_lignes else None

        entree_confiance = confiances.get(cle)
        meilleure = entree_confiance.candidates[0] if entree_confiance and entree_confiance.candidates else None

        fenetre_etat, fenetre_geste, fenetre_mois = _fenetre_de_la_culture(itineraire, date_ref)

        lignes.append(LigneCulture(
            culture=cle,
            nom_culture=nom,
            hors_referentiel=not calendrier.culture_connue,
            famille=familles.get(nom) or familles.get(cle),
            au_potager=cle in au_potager,
            mois_zone=mois_zone,
            a_calendrier=itineraire is not None,
            mois_actifs=_mois_actifs(itineraire),
            nb_varietes=len(varietes_par_culture.get(cle, ())),
            varietes=tuple(sorted(varietes_par_culture.get(cle, ()))),
            nb_parcelles=len(parcelles_par_culture.get(cle, ())),
            repartition_phases={p: phases_lignes.count(p) for p in ORDRE_PHASES if phases_lignes.count(p) > 0},
            phase_plus_avancee=phase_plus_avancee,
            nb_lots_pepiniere=lots_par_culture.get(cle, 0),
            etoiles=meilleure.etoiles if meilleure else None,
            confiance_equivalent=EQUIVALENT_ETOILES.get(meilleure.etoiles) if meilleure else None,
            fenetre_etat=fenetre_etat,
            fenetre_geste=fenetre_geste,
            fenetre_mois=fenetre_mois,
        ))

    # ── [CA6] Suggestion de la semaine : au plus trois, les mieux notées d'abord ─
    candidates_suggestion = [
        l for l in lignes
        if not l.au_potager and l.fenetre_etat == ETAT_MAINTENANT
        and (l.etoiles or 0) >= SEUIL_ETOILES_SUGGESTION
    ]
    candidates_suggestion.sort(key=lambda l: (-(l.etoiles or 0), l.nom_culture.lower()))
    suggeres = {l.culture for l in candidates_suggestion[:PLAFOND_SUGGESTIONS]}
    if suggeres:
        lignes = [
            l if l.culture not in suggeres else _avec_suggestion(l)
            for l in lignes
        ]

    return VueCultures(
        zone_climatique=zone,
        zone_climatique_origine=origine,
        attributions=tuple(attributions),
        familles=tuple(sorted({f for f in familles.values() if f})),
        cultures=tuple(lignes),
        effectif_toutes=len(univers),
        effectif_au_potager=len(au_potager),
        meteo_disponible=meteo_disponible,
    )


def _avec_suggestion(ligne: LigneCulture) -> LigneCulture:
    from dataclasses import replace
    return replace(ligne, suggestion=True)


def vue_cultures_en_dict(vue: VueCultures) -> dict:
    """[US-204] Forme sérialisable de `VueCultures`, servie par l'API."""
    return {
        "zone_climatique": vue.zone_climatique,
        "zone_climatique_origine": vue.zone_climatique_origine,
        "attributions": list(vue.attributions),
        "familles": list(vue.familles),
        "effectif_toutes": vue.effectif_toutes,
        "effectif_au_potager": vue.effectif_au_potager,
        "meteo_disponible": vue.meteo_disponible,
        "cultures": [
            {
                "culture": l.culture,
                "nom_culture": l.nom_culture,
                "hors_referentiel": l.hors_referentiel,
                "famille": l.famille,
                "au_potager": l.au_potager,
                "a_calendrier": l.a_calendrier,
                "mois_zone": l.mois_zone,
                "mois_actifs": list(l.mois_actifs),
                "nb_varietes": l.nb_varietes,
                "varietes": list(l.varietes),
                "nb_parcelles": l.nb_parcelles,
                "repartition_phases": l.repartition_phases,
                "phase_plus_avancee": l.phase_plus_avancee,
                "nb_lots_pepiniere": l.nb_lots_pepiniere,
                "etoiles": l.etoiles,
                "confiance_equivalent": l.confiance_equivalent,
                "fenetre_etat": l.fenetre_etat,
                "fenetre_geste": l.fenetre_geste,
                "fenetre_mois": list(l.fenetre_mois),
                "suggestion": l.suggestion,
            }
            for l in vue.cultures
        ],
    }
