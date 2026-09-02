"""
app/services/avertissements_plantation.py — Avertissement de rotation et
d'association à l'enregistrement d'une plantation ou d'un semis [US-167]
--------------------------------------------------------------------------------
Dernière US de l'ÉPIC 6 : elle ne calcule rien de nouveau, elle DÉCLENCHE ce
que US-163 sait déjà calculer (`rotation.evaluer_rotation`, les associations
de `associations.py`) au moment précis où le jardinier a la fourche à la
main — l'enregistrement d'une plantation ou d'un semis. Le référentiel
n'est pas consulté, il se déclenche.

**[CA2, CA3] Jamais bloquant, jamais un nouvel état conversationnel.** Ce
module ne fait qu'évaluer et formuler des messages ; c'est l'appelant
(bot.py, main.py) qui décide de les afficher, toujours APRÈS la confirmation
d'enregistrement, jamais à sa place. Aucune écriture ici — lecture pure.

🔴 **Piège constaté en production (02/09/2026) : n'appeler ceci qu'AVANT
l'écriture de l'événement évalué, jamais après.** L'ordre d'AFFICHAGE (après
la confirmation) est indépendant de l'ordre de CALCUL. Si l'appelant écrit
l'événement puis appelle cette fonction ensuite, `rotation.evaluer_rotation`
retrouve l'événement tout juste créé dans son propre historique de parcelle
et le cite comme son propre antécédent — un faux conflit auto-référentiel
(« tomate déjà présente cette année », elle-même). Les quatre appelants
(bot.py `_do_save_items`/`_parse_multi`, main.py `/parse`/`/voice`) évaluent
donc tous avant d'écrire, et ne font qu'afficher le résultat après.

**[CA4] Liste vide = rien à dire.** Un message qui apparaît à chaque saisie
cesse d'être lu au bout d'une semaine. Le silence n'est donc pas un oubli,
c'est le comportement voulu dès qu'il n'y a positivement rien à signaler —
délai de rotation respecté (`STATUT_OK`), ou aucune culture voisine en
conflit d'association.

**[CA6, CA7] Le silence n'est permis qu'après vérification.** « Je n'ai pas
d'antécédent » et « évaluation indisponible » sont des messages à part
entière (honnêteté de l'Épic 5 §4 appliquée à la rotation, US-163/CA7-CA8) —
seul le cas « antécédent connu, aucun conflit » reste silencieux.

**[CA12] Exception : la culture fantôme.** Une culture totalement absente du
référentiel (`culture_config`) — cas réel en production : `radi`, née d'un
échec de parsing enregistré comme événement — n'a aucune fiche à consulter.
Le silence y est total : pas d'erreur, pas de message honnête à formuler,
puisqu'il n'y a même pas de quoi vérifier qu'il s'agit d'une culture réelle.
Une culture connue mais dont la famille n'est pas rattachée reste, elle,
couverte par CA7 (message « indisponible ») — c'est le même comportement que
`rotation.evaluer_rotation` applique déjà pour `/rotation` (voir
`test_culture_sans_famille_connue_est_egalement_indisponible`,
tests/test_us163_associations_rotation.py).

**« Culture voisine » (CA8 Gherkin, CA9) — ce que ce module peut réellement
observer.** Le modèle de données ne porte aucune position spatiale : une
parcelle est une unité, pas une grille de cases (voir `database.models.Parcelle`
— `ordre` trie l'affichage du plan, il ne place rien dans l'espace). La
lecture retenue est donc l'autre culture déjà enregistrée sur la MÊME
parcelle, à la MÊME campagne (CA9) — c'est la seule notion de « voisinage »
que l'historique réel permet de calculer sans inventer une donnée absente.
"""
from __future__ import annotations

from datetime import date as _date
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.services import associations as svc_associations
from app.services import rotation as svc_rotation
from app.services.attributs_culture import fiches_de_culture
from app.services.context import TenantContext
from database.models import Evenement
from utils.culture_resolve import normaliser_culture

#: [CA1] Seules ces deux actions déclenchent l'avertissement — jamais un
#: arrosage, une récolte ou toute autre action du gabarit à 12 actions.
ACTIONS_DECLENCHANT_AVERTISSEMENT = frozenset({"plantation", "semis"})


def evaluer_avertissements_plantation(
    db: Session,
    ctx: TenantContext,
    parcelle_id: Optional[int],
    culture: Optional[str],
    campagne_reference: Optional[int] = None,
) -> list[str]:
    """
    [CA1-CA9, CA12] Messages à afficher après l'enregistrement d'une
    plantation ou d'un semis. Liste vide = rien à signaler (CA4) — cette
    fonction ne lève jamais et n'appelle jamais de modèle de langage (CA10).

    Combine deux évaluations, jamais réécrites :
      - le conflit de rotation (`rotation.evaluer_rotation`, US-163) ;
      - le conflit d'association avec les cultures déjà en place sur la même
        parcelle, cette même campagne (voir docstring du module).
    """
    culture = (culture or "").strip()
    if not culture or parcelle_id is None:
        # [CA12] Rien d'identifié à vérifier — silence, jamais une supposition.
        return []

    if not fiches_de_culture(db, culture):
        # [CA12] Culture fantôme : aucune fiche à consulter, donc rien
        # d'honnête à dire — le silence ici ne prétend rien, il constate.
        return []

    campagne_reference = (
        campagne_reference if campagne_reference is not None else _date.today().year
    )

    messages: list[str] = []

    evaluation = svc_rotation.evaluer_rotation(db, ctx, parcelle_id, culture, campagne_reference)
    if evaluation.statut == svc_rotation.STATUT_CONFLIT:
        messages.append(f"⚠️ {evaluation.message}")
    elif evaluation.statut in (svc_rotation.STATUT_AUCUN_ANTECEDENT, svc_rotation.STATUT_INDISPONIBLE):
        messages.append(f"ℹ️ {evaluation.message}")
    # STATUT_OK : rien à dire (CA4) — un antécédent existe et ne pose pas conflit.

    messages.extend(
        _conflits_association_voisinage(db, ctx, parcelle_id, culture, campagne_reference)
    )

    return messages


def _conflits_association_voisinage(
    db: Session,
    ctx: TenantContext,
    parcelle_id: int,
    culture: str,
    campagne_reference: int,
) -> list[str]:
    """
    [CA8, CA9] Cultures « défavorables » (US-163) déjà en place sur la même
    parcelle, cette même campagne — voir la docstring du module pour la
    définition de « voisine » retenue ici. Silencieux si `culture` ne désigne
    rien de connu pour `associations.lire_associations` (déjà écarté plus
    haut par CA12, gardé ici par défense) ou si aucune association
    défavorable ne s'applique aux voisines trouvées.
    """
    cible = normaliser_culture(culture)

    # Même garde que `rotation.evaluer_rotation` : bulletins météo automatiques
    # exclus (aucune culture réelle), et seuls les événements datés et rattachés
    # à une culture sont exploitables.
    evenements = (
        db.query(Evenement)
        .filter(
            Evenement.potager_id == ctx.potager_id,
            Evenement.parcelle_id == parcelle_id,
            Evenement.culture.isnot(None),
            Evenement.date.isnot(None),
            or_(
                Evenement.texte_original.is_(None),
                Evenement.texte_original != svc_rotation.BULLETIN_AUTO_METEO,
            ),
        )
        .all()
    )

    voisines: list[str] = []
    vues: set[str] = {cible}
    for evenement in evenements:
        if evenement.date.year != campagne_reference:
            continue
        nom_norm = normaliser_culture(evenement.culture)
        if nom_norm in vues:
            continue
        vues.add(nom_norm)
        voisines.append(evenement.culture)

    if not voisines:
        return []

    try:
        associations = svc_associations.lire_associations(db, culture)
    except svc_associations.EntiteInconnueError:
        return []

    defavorables = [a for a in associations if a.nature == svc_associations.NATURE_DEFAVORABLE]
    if not defavorables:
        return []

    messages: list[str] = []
    for voisine in voisines:
        voisine_norm = normaliser_culture(voisine)
        familles_voisine: Optional[set[str]] = None
        for assoc in defavorables:
            if assoc.autre_est_famille:
                if familles_voisine is None:
                    familles_voisine = {
                        fiche.famille_rel.nom
                        for fiche in fiches_de_culture(db, voisine)
                        if fiche.famille_rel is not None
                    }
                if assoc.autre_partie not in familles_voisine:
                    continue
            elif normaliser_culture(assoc.autre_partie) != voisine_norm:
                continue
            # [CA8 US-163/CA3] Formulation déjà différenciée par niveau de
            # preuve — jamais la même phrase pour un fait établi et une
            # pratique traditionnelle non démontrée.
            messages.append(
                f"⚠️ Association avec {voisine} (déjà en place sur cette "
                f"parcelle cette campagne) : {assoc.formulation} — {assoc.motif}."
            )

    return messages
