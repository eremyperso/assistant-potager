"""
app/services/rotation.py — Rotation calculable à la campagne [US-163]
--------------------------------------------------------------------------------
Un conflit de rotation se CALCULE — il ne se rédige pas (CA6). « Quelles
cultures puis-je planter sur la parcelle NORD, sachant que j'y ai eu des
tomates l'an dernier ? » est une requête de graphe croisée avec l'historique
réel d'une parcelle ; aucune recherche plein texte ni vectorielle ne la produit.
Ce module croise trois faits déjà en base — l'historique de la parcelle,
la famille botanique de chaque culture qui y est passée, et le délai de retour
de cette famille (US-067/CA12) — sans qu'aucun ne soit dupliqué dans une fiche
(US-140/CA7bis, docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.2).

**Quatre issues honnêtes, jamais confondues (CA7, CA8) :**
  - `conflit` / `ok` : un antécédent exploitable existe (ou non) pour la même
    famille — le prédicat est calculé, positif ou négatif ;
  - `aucun_antecedent` : la parcelle ne porte AUCUN événement exploitable —
    jamais interprété comme « aucun conflit » (CA8) ;
  - `indisponible` : la culture visée n'a pas de famille connue, ou sa famille
    n'a pas de délai de retour renseigné — jamais interprété comme « aucun
    conflit » non plus (US-067/CA13, réaffirmé ici).

**[CA9] Le calcul raisonne à la CAMPAGNE** (l'année de la date de l'événement),
jamais au jour près. C'est le domaine qui l'impose, et c'est aussi ce qui
protège le calcul d'une donnée de date imparfaite : une saisie sans ancrage
temporel retombe silencieusement sur le jour de saisie (`date_source =
'presumee'`), mais reste juste au niveau de l'année — un raisonnement au jour
près serait bâti sur du sable. Ce module ne filtre donc PAS sur `date_source` :
toute date non nulle est exploitable à ce grain.

**Deux gardes contre le bruit de l'historique réel (notes techniques US-163) :**
  - les bulletins météo automatiques (`texte_original = '[AUTO-METEO]'`, ~96 des
    321 événements mesurés le 25/08/2026) sont exclus : ils ne portent aucune
    culture ;
  - un événement dont la culture ne correspond à AUCUNE fiche `culture_config`
    connue (culture fantôme, ex. 'radi' né d'un échec de parsing) n'est jamais
    traité comme un antécédent établi.

**[CA11] Zéro jeton** : lecture pure de colonnes déjà en base, aucun appel à un
modèle de langage.

**Ce que ce module ne fait pas** : il ne restitue pas de texte figé côté bot.
`EvaluationRotation.message` est un gabarit unique assemblé depuis le
prédicat — CA6 le dit explicitement, le résultat est « un prédicat, exploitable
par une alerte », pas un passage de texte pré-rédigé. La restitution
proactive à la plantation est le périmètre d'US-167, qui réutilise
`evaluer_rotation` sans le réécrire.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services import attributs_culture as svc_attributs
from app.services.context import TenantContext
from app.services.parcelles import lister_cultures_config
from database.models import Evenement
from utils.culture_resolve import normaliser_culture

#: Marqueur exact posé par le job météo quotidien (bot.py::job_meteo_quotidienne).
BULLETIN_AUTO_METEO = "[AUTO-METEO]"

STATUT_CONFLIT = "conflit"
STATUT_OK = "ok"
STATUT_AUCUN_ANTECEDENT = "aucun_antecedent"
STATUT_INDISPONIBLE = "indisponible"


@dataclass(frozen=True)
class EvaluationRotation:
    """[CA6] Le prédicat de rotation — une donnée structurée, exploitable par une
    alerte (US-167), jamais un texte rédigé à l'avance."""

    statut: str
    culture: str
    campagne_reference: int
    famille: Optional[str] = None
    delai_retour_annees: Optional[int] = None
    culture_precedente: Optional[str] = None
    campagne_derniere_occurrence: Optional[int] = None
    motif_indisponible: Optional[str] = None

    @property
    def en_conflit(self) -> bool:
        return self.statut == STATUT_CONFLIT

    @property
    def message(self) -> str:
        """Gabarit unique — un seul endroit qui sait dire ces quatre issues,
        réutilisé tel quel par le bot (`/rotation`) comme par une future
        alerte proactive (US-167)."""
        if self.statut == STATUT_AUCUN_ANTECEDENT:
            return (
                "Je n'ai pas d'antécédent sur cette parcelle : impossible de "
                "vérifier la rotation, je ne conclus pas à l'absence de conflit."
            )
        if self.statut == STATUT_INDISPONIBLE:
            return (
                f"Évaluation de rotation indisponible : {self.motif_indisponible}. "
                "Je n'affirme pas l'absence de conflit."
            )
        if self.statut == STATUT_CONFLIT:
            reste = self.delai_retour_annees - (
                self.campagne_reference - self.campagne_derniere_occurrence
            )
            return (
                f"Conflit de rotation : {self.culture} appartient à la famille "
                f"{self.famille}, déjà présente sur cette parcelle en "
                f"{self.campagne_derniere_occurrence} ({self.culture_precedente}). "
                f"Délai de retour recommandé : {self.delai_retour_annees} an(s) — "
                f"encore {reste} an(s) à attendre."
            )
        return (
            f"Aucun conflit de rotation connu pour {self.culture} sur cette "
            f"parcelle (famille {self.famille}, délai de retour "
            f"{self.delai_retour_annees} an(s))."
        )


def _campagne(evenement_date) -> Optional[int]:
    """[CA9] La campagne d'un événement est l'année de sa date — jamais plus fin."""
    return evenement_date.year if evenement_date is not None else None


def _familles_id_par_culture(db: Session, ctx: TenantContext) -> dict[str, int]:
    """Culture normalisée → id de sa famille, pour les fiches visibles depuis ce
    potager qui ont une famille renseignée. Une culture absente de ce dict n'a
    pas de famille connue — c'est ce qui exclut une culture fantôme (ex. 'radi')
    de l'historique exploitable, exactement comme une culture absente du
    référentiel : elle ne peut jamais devenir un antécédent établi."""
    configs = lister_cultures_config(db, ctx)
    mapping: dict[str, int] = {}
    for config in configs:
        cle = normaliser_culture(config.nom)
        if cle not in mapping and config.famille_id is not None:
            mapping[cle] = config.famille_id
    return mapping


@dataclass(frozen=True)
class Antecedent:
    """[US-231 / CA1, CA2] Un passage de culture sur une parcelle, ramené à sa
    campagne. `famille_id` à None dit une culture dont la famille botanique est
    inconnue : elle est **gardée** — la carte « Rotation » la nomme (R7) — mais
    elle n'est jamais un antécédent établi, ni pour le conflit d'US-163 ni pour
    l'alerte et le conseil d'US-231."""

    culture: str
    campagne: int
    famille_id: Optional[int] = None


def _requete_antecedents(db: Session, ctx: TenantContext):
    """[Notes techniques US-163] Bulletins météo exclus : aucune culture, donc
    pas un antécédent. Aucun filtre sur `type_action` : un événement rattaché à
    une parcelle et portant une culture atteste d'un passage, quel que soit le
    verbe employé — c'est le rattachement à la parcelle qui fait la preuve, et
    c'est ce qui exclut un semis de pépinière (rattaché à la pépinière, R8)."""
    return db.query(Evenement).filter(
        Evenement.potager_id == ctx.potager_id,
        Evenement.culture.isnot(None),
        Evenement.date.isnot(None),
        or_(
            Evenement.texte_original.is_(None),
            Evenement.texte_original != BULLETIN_AUTO_METEO,
        ),
    )


def antecedents_de_parcelle(
    db: Session, ctx: TenantContext, parcelle_id: int
) -> list[Antecedent]:
    """[US-231 / CA1] L'historique exploitable d'UNE parcelle — la lecture que
    `evaluer_rotation` (US-163) et la carte « Rotation » partagent."""
    familles_par_culture = _familles_id_par_culture(db, ctx)
    evenements = _requete_antecedents(db, ctx).filter(
        Evenement.parcelle_id == parcelle_id
    ).all()
    return _en_antecedents(evenements, familles_par_culture)


def _en_antecedents(evenements, familles_par_culture: dict[str, int]) -> list[Antecedent]:
    antecedents: list[Antecedent] = []
    for evenement in evenements:
        campagne = _campagne(evenement.date)
        if campagne is None:
            continue
        antecedents.append(Antecedent(
            culture=evenement.culture,
            campagne=campagne,
            famille_id=familles_par_culture.get(normaliser_culture(evenement.culture)),
        ))
    return antecedents


def evaluer_rotation(
    db: Session,
    ctx: TenantContext,
    parcelle_id: int,
    culture: str,
    campagne_reference: Optional[int] = None,
) -> EvaluationRotation:
    """
    [CA6-CA9] Évalue si planter `culture` sur `parcelle_id` entre en conflit de
    rotation avec l'historique réel de cette parcelle.

    `campagne_reference` par défaut l'année en cours — surchageable pour un
    calcul situé dans le temps (tests, simulation « et si je plantais l'an
    prochain »).
    """
    campagne_reference = (
        campagne_reference if campagne_reference is not None else _date.today().year
    )

    fiches = svc_attributs.fiches_de_culture(db, culture)
    fiche_avec_famille = next((f for f in fiches if f.famille_id is not None), None)
    if not fiches or fiche_avec_famille is None:
        return EvaluationRotation(
            statut=STATUT_INDISPONIBLE,
            culture=culture,
            campagne_reference=campagne_reference,
            motif_indisponible=(
                f"la culture « {culture} » n'est pas rattachée à une famille "
                "botanique connue"
            ),
        )
    famille = fiche_avec_famille.famille_rel
    if famille.delai_retour_annees is None:
        return EvaluationRotation(
            statut=STATUT_INDISPONIBLE,
            culture=culture,
            campagne_reference=campagne_reference,
            famille=famille.nom,
            motif_indisponible=(
                f"le délai de retour de la famille « {famille.nom} » n'est pas renseigné"
            ),
        )

    # [US-231 / CA1] Le MÊME historique que la carte « Rotation » de la fiche
    # parcelle : une seule lecture sait quels événements font antécédent, et
    # les deux restitutions ne peuvent donc pas se contredire.
    antecedents = antecedents_de_parcelle(db, ctx, parcelle_id)

    # [Notes techniques] Une culture inconnue du référentiel (fantôme, ex.
    # 'radi') n'entre jamais dans l'historique exploitable.
    exploitables = [a for a in antecedents if a.famille_id is not None]

    if not exploitables:
        return EvaluationRotation(
            statut=STATUT_AUCUN_ANTECEDENT,
            culture=culture,
            campagne_reference=campagne_reference,
        )

    memes_famille = [
        (a.culture, a.campagne) for a in exploitables
        if a.famille_id == fiche_avec_famille.famille_id and a.campagne <= campagne_reference
    ]
    if not memes_famille:
        return EvaluationRotation(
            statut=STATUT_OK,
            culture=culture,
            campagne_reference=campagne_reference,
            famille=famille.nom,
            delai_retour_annees=famille.delai_retour_annees,
        )

    culture_precedente, campagne_derniere = max(memes_famille, key=lambda t: t[1])
    ecart = campagne_reference - campagne_derniere
    statut = STATUT_CONFLIT if ecart < famille.delai_retour_annees else STATUT_OK
    return EvaluationRotation(
        statut=statut,
        culture=culture,
        campagne_reference=campagne_reference,
        famille=famille.nom,
        delai_retour_annees=famille.delai_retour_annees,
        culture_precedente=culture_precedente,
        campagne_derniere_occurrence=campagne_derniere,
    )


# ── [US-231] La rotation qui se LIT, à froid, hors du geste ──────────────────
#
# US-163 sait dire « planter ceci ici entre en conflit » — au moment où l'on
# plante. Ce savoir n'existait qu'à cet instant : rien ne le donnait à lire
# posément, quand on prépare la saison. Ce bloc rend visible l'historique que
# `evaluer_rotation` parcourt déjà, et formule le conseil de l'année à venir
# avec le MÊME prédicat (CA1) — écart entre campagnes contre délai de retour de
# la famille. Aucun second calcul, aucune duplication côté frontend (CA1).
#
# ⚖️ Honnêteté avant complétude : une famille inconnue se dit, une année sans
# donnée se dit vide, et une culture sans famille est EXCLUE du conseil comme
# de l'alerte — son absence ne produit jamais un « tout va bien » (R7).

#: [R1] Trois campagnes derrière, puis la campagne à venir.
NB_CAMPAGNES_AFFICHEES = 3

#: [R7] Ce qu'une famille inconnue dit d'elle-même — jamais « Autres ».
MENTION_FAMILLE_INCONNUE = "Famille non renseignée"

#: [R5] Une alerte nomme le nombre d'années en mots, et la fenêtre en tient trois.
_ANNEES_EN_MOTS = {2: "deux", 3: "trois"}


def _familles_du_referentiel(db: Session, ctx: TenantContext) -> dict[int, dict]:
    """id de famille → nom, délai de retour, et les cultures du référentiel qui
    la portent. Une famille sans aucune culture visible depuis ce potager ne peut
    pas être conseillée : on ne conseille pas de semer ce que l'application ne
    connaît pas."""
    familles: dict[int, dict] = {}
    for config in lister_cultures_config(db, ctx):
        if config.famille_id is None or config.famille_rel is None:
            continue
        fiche = familles.setdefault(config.famille_id, {
            "id": config.famille_id,
            "nom": config.famille_rel.nom,
            "delai_retour_annees": config.famille_rel.delai_retour_annees,
            "cultures": [],
        })
        if config.nom not in fiche["cultures"]:
            fiche["cultures"].append(config.nom)
    return familles


def _campagnes_affichees(campagne_a_venir: int) -> list[int]:
    return [
        campagne_a_venir - NB_CAMPAGNES_AFFICHEES + i
        for i in range(NB_CAMPAGNES_AFFICHEES)
    ]


def _colonnes(
    antecedents: list[Antecedent], familles: dict[int, dict], campagnes: list[int]
) -> tuple[list[dict], list[str]]:
    """[R1, R2, R6, R7] Une colonne par campagne, une vignette par famille. Une
    année sans donnée reste une colonne VIDE — elle ne se saute pas (R6)."""
    colonnes: list[dict] = []
    sans_famille: list[str] = []
    for campagne in campagnes:
        vignettes: dict[object, dict] = {}
        for antecedent in [a for a in antecedents if a.campagne == campagne]:
            connue = antecedent.famille_id is not None and antecedent.famille_id in familles
            cle = antecedent.famille_id if connue else None
            vignette = vignettes.setdefault(cle, {
                "famille_id": antecedent.famille_id if connue else None,
                "famille": (
                    familles[antecedent.famille_id]["nom"] if connue
                    else MENTION_FAMILLE_INCONNUE
                ),
                "inconnue": not connue,
                "cultures": [],
            })
            if antecedent.culture not in vignette["cultures"]:
                vignette["cultures"].append(antecedent.culture)
            if not connue and antecedent.culture not in sans_famille:
                sans_famille.append(antecedent.culture)
        # [R2] Les familles nommées d'abord, l'inconnue en dernier : ce n'est pas
        # une famille, c'est une lacune.
        ordonnees = sorted(
            vignettes.values(), key=lambda v: (v["inconnue"], v["famille"].lower())
        )
        colonnes.append({"annee": campagne, "familles": ordonnees})
    return colonnes, sans_famille


def _derniere_campagne_par_famille(antecedents: list[Antecedent]) -> dict[int, int]:
    """Toute l'histoire connue, pas seulement la fenêtre affichée : un délai de
    retour de cinq ans se juge sur cinq ans, même si la carte n'en montre trois."""
    dernieres: dict[int, int] = {}
    for antecedent in antecedents:
        if antecedent.famille_id is None:
            continue
        precedente = dernieres.get(antecedent.famille_id)
        if precedente is None or antecedent.campagne > precedente:
            dernieres[antecedent.famille_id] = antecedent.campagne
    return dernieres


def _alertes(
    antecedents: list[Antecedent], familles: dict[int, dict], campagne_a_venir: int
) -> list[dict]:
    """[R5] Une famille présente plusieurs campagnes **consécutives** jusqu'à la
    campagne courante menace l'année à venir : c'est cette répétition-là qui se
    dit, une seule fois par famille en cause. Une répétition ancienne et
    interrompue n'est plus une répétition en cours — le conseil, lui, la voit."""
    campagne_courante = campagne_a_venir - 1
    par_famille: dict[int, set] = {}
    for antecedent in antecedents:
        if antecedent.famille_id is None or antecedent.famille_id not in familles:
            continue
        par_famille.setdefault(antecedent.famille_id, set()).add(antecedent.campagne)

    alertes: list[dict] = []
    for famille_id, campagnes in par_famille.items():
        suite = 0
        while (campagne_courante - suite) in campagnes:
            suite += 1
        if suite < 2:
            continue
        suite = min(suite, NB_CAMPAGNES_AFFICHEES)
        nom = familles[famille_id]["nom"]
        alertes.append({
            "famille_id": famille_id,
            "famille": nom,
            "annees": suite,
            "annee_a_eviter": campagne_a_venir,
            "message": (
                f"{nom} {_ANNEES_EN_MOTS.get(suite, suite)} années de suite sur "
                f"cette parcelle. À éviter en {campagne_a_venir}."
            ),
        })
    return sorted(alertes, key=lambda a: (-a["annees"], a["famille"].lower()))


def _conseil(
    familles: dict[int, dict], dernieres: dict[int, int], campagne_a_venir: int
) -> dict:
    """[R4, CA1] Les familles compatibles pour la campagne à venir — le MÊME
    prédicat qu'`evaluer_rotation` : l'écart entre campagnes comparé au délai de
    retour du référentiel. Une famille sans délai renseigné n'est jamais
    conseillée : l'inconnu ne se présente pas comme un feu vert (US-163 / CA13)."""
    conseillees = []
    for famille in familles.values():
        delai = famille["delai_retour_annees"]
        if delai is None:
            continue
        derniere = dernieres.get(famille["id"])
        if derniere is not None and campagne_a_venir - derniere < delai:
            continue
        conseillees.append({
            "famille_id": famille["id"],
            "famille": famille["nom"],
            "delai_retour_annees": delai,
            "derniere_campagne": derniere,
            "cultures": famille["cultures"],
        })
    conseillees.sort(key=lambda f: f["famille"].lower())
    mention = None
    if not any(f["delai_retour_annees"] is not None for f in familles.values()):
        mention = (
            "Aucun délai de retour n'est renseigné dans le référentiel : je ne "
            f"formule pas de conseil pour {campagne_a_venir}."
        )
    elif not conseillees:
        mention = (
            "Aucune famille du référentiel n'est compatible avec "
            f"{campagne_a_venir} au regard de son délai de retour."
        )
    return {"annee": campagne_a_venir, "familles": conseillees, "mention": mention}


def _mention_familles_inconnues(cultures: list[str]) -> Optional[str]:
    """[R7] L'absence se signale en une ligne — et se paie en exclusion, jamais
    en silence."""
    if not cultures:
        return None
    liste = ", ".join(cultures)
    if len(cultures) == 1:
        return (
            f"Famille botanique non renseignée pour {liste} : cette culture "
            "n'entre ni dans l'alerte de répétition ni dans le conseil."
        )
    return (
        f"Famille botanique non renseignée pour {liste} : ces cultures n'entrent "
        "ni dans l'alerte de répétition ni dans le conseil."
    )


def _carte_rotation(
    antecedents: list[Antecedent], familles: dict[int, dict], campagne_a_venir: int
) -> dict:
    colonnes, sans_famille = _colonnes(
        antecedents, familles, _campagnes_affichees(campagne_a_venir)
    )
    exploitables = [a for a in antecedents if a.famille_id is not None]
    dernieres = _derniere_campagne_par_famille(exploitables)
    return {
        "campagne_a_venir": campagne_a_venir,
        "campagnes": colonnes,
        # [R4] La colonne en pointillés — « Conseillé ».
        "conseil": _conseil(familles, dernieres, campagne_a_venir),
        "alertes": _alertes(antecedents, familles, campagne_a_venir),
        "cultures_sans_famille": sans_famille,
        "mention_familles_inconnues": _mention_familles_inconnues(sans_famille),
        # [R6] Aucun antécédent : ce n'est pas « aucun conflit », c'est un
        # silence — et il se dit, sans faire disparaître la colonne de conseil.
        "aucun_antecedent": not exploitables,
        "mention_aucun_antecedent": (
            None if exploitables
            else "Aucune culture enregistrée sur cette parcelle avant "
                 f"{campagne_a_venir - 1}."
        ),
    }


def campagne_a_venir_par_defaut(aujourdhui: Optional[_date] = None) -> int:
    """[R1] La campagne à venir est l'année qui suit l'année en cours."""
    return (aujourdhui or _date.today()).year + 1


def historique_parcelle(
    db: Session,
    ctx: TenantContext,
    parcelle_id: int,
    campagne_a_venir: Optional[int] = None,
) -> dict:
    """[US-231 / CA1, CA2] La carte « Rotation » d'UNE parcelle."""
    return _carte_rotation(
        antecedents_de_parcelle(db, ctx, parcelle_id),
        _familles_du_referentiel(db, ctx),
        campagne_a_venir or campagne_a_venir_par_defaut(),
    )


def historique_du_plan(
    db: Session,
    ctx: TenantContext,
    parcelles,
    campagne_a_venir: Optional[int] = None,
) -> dict[int, dict]:
    """[US-231 / CA3] Les quatre années de TOUTES les parcelles, en une lecture
    unique servie avec l'onglet Parcelles : changer de parcelle ne déclenche
    aucune requête de plus (RT6).

    [R8] Une pépinière n'a pas de rotation — un emplacement de godets ne porte
    pas de succession de familles. Elle n'a donc pas d'entrée ici, et la carte
    n'est pas rendue.
    """
    campagne_a_venir = campagne_a_venir or campagne_a_venir_par_defaut()
    concernees = [p for p in parcelles if not getattr(p, "est_pepiniere", False)]
    if not concernees:
        return {}

    familles = _familles_du_referentiel(db, ctx)
    familles_par_culture = _familles_id_par_culture(db, ctx)
    ids = [p.id for p in concernees]
    evenements = (
        _requete_antecedents(db, ctx)
        .filter(Evenement.parcelle_id.in_(ids))
        .all()
    )

    par_parcelle: dict[int, list] = {identifiant: [] for identifiant in ids}
    for evenement in evenements:
        if evenement.parcelle_id in par_parcelle:
            par_parcelle[evenement.parcelle_id].append(evenement)

    return {
        identifiant: _carte_rotation(
            _en_antecedents(par_parcelle[identifiant], familles_par_culture),
            familles,
            campagne_a_venir,
        )
        for identifiant in ids
    }
