"""
app/services/compagnon/orchestrateur.py — Où va une phrase du jardinier [US-270]
=================================================================================
Le bot Telegram décidait seul de l'ordre dans lequel une phrase libre est lue
(`app/bot/messages.handle_text`, priorités 2 à 4). La PWA devait recevoir la
MÊME décision : deux assistants qui se contredisent sont exactement ce que le
cadrage (§4.1) veut éviter. L'ordre vit donc ici, une fois (étapes E0 et E1 de
l'étude d'articulation, règles R3 et R5 : *les canaux ne décident rien*).

Deux temps, séparés par ce que seul le canal sait faire — montrer au jardinier :

1. `distribuer` — les gardes du canal, puis l'agent et l'interpréteur de
   commandes. Rend ce que l'interpréteur a lu (`resultat`, à présenter) ou dit
   que le canal a déjà pris la phrase (`pris_par_le_canal`).
2. `orienter` — quand le canal n'a rien eu à présenter : question (cascade
   commune, E0) ou geste (parseur de gestes).

Ce module ne sait rien de Telegram ni de FastAPI. Le canal lui prête ses
recogniseurs (`Canal`) : ce sont eux qui ont des effets de bord (répondre,
armer un flux guidé), et l'ordre de leur appel est ici. Ils peuvent être
synchrones ou asynchrones — le bot passe des coroutines, la PWA des fonctions.

L'ordre, repris du bot sans changement visible :

* mode `prioritaire` (agent d'abord) : gardes de dialogue (profil, carnet) →
  agent ; si l'agent est indisponible, le mode dégradé suit l'ordre habituel ;
* ordre habituel : raccourcis à mots-clés → gardes de dialogue (hors mode
  prioritaire, où elles ont déjà passé) → interpréteur.
"""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from app.services import interpreteur_commandes as svc_interpreteur
from app.services.agent import contexte_court as svc_contexte_court
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext

log = logging.getLogger("potager")

#: Ce que `orienter` décide quand le canal n'a rien eu à présenter.
SUITE_QUESTION = "question"
SUITE_GESTE = "geste"


@dataclass(frozen=True)
class Canal:
    """Ce que le canal prête à l'orchestrateur : de quoi reconnaître et prendre une phrase.

    `dialogue` et `raccourcis` rendent True quand ils ont PRIS la phrase (le canal a
    alors répondu lui-même). `contexte_court` est appelé à chaque consultation de
    l'agent, comme le faisait le bot (la proposition en attente peut avoir changé).
    `boutons_exacts` : les textes de boutons qui ne sont pas des phrases libres et
    restent servis par les raccourcis, même en mode `prioritaire`.
    """

    nom: str
    dialogue: Callable[[str], Any] = lambda texte: False
    raccourcis: Callable[[str], Any] = lambda texte: False
    contexte_court: Callable[[], Any] = lambda: None
    boutons_exacts: frozenset = field(default_factory=frozenset)


@dataclass(frozen=True)
class Distribution:
    """Le résultat de `distribuer`.

    `pris_par_le_canal` : une garde ou un raccourci du canal a répondu ; rien à faire.
    Sinon `resultat` est ce que l'interpréteur a lu — `CommandeInterpretee`, `Plan`,
    `Ambiguite`, `ReponseAgent`, `Aiguillage`, ou `None` (« pas une commande »).
    """

    pris_par_le_canal: bool = False
    garde: Optional[str] = None
    resultat: Any = None
    mode_agent_prioritaire: bool = False


@dataclass(frozen=True)
class Orientation:
    """La suite d'une phrase que le canal n'a pas eu à présenter."""

    vers: str  # SUITE_QUESTION | SUITE_GESTE
    #: La nature que l'agent a donnée à la question ; None, c'est la cascade qui classe.
    nature: Optional[str] = None


async def _attendre(valeur: Any) -> Any:
    return await valeur if inspect.isawaitable(valeur) else valeur


async def distribuer(texte: str, ctx: Optional[TenantContext], canal: Canal) -> Distribution:
    """[US-270 / CA4] Les gardes du canal, l'agent, puis l'interpréteur de commandes.

    Reprend à l'identique l'ordre de `handle_text` (US-287) : le canal n'a plus à le
    connaître, il fournit ses gardes.
    """
    texte_min = (texte or "").lower()
    agent_prioritaire = svc_interpreteur.agent_prioritaire()
    resultat = svc_interpreteur.CASCADE_HABITUELLE

    # ── [US-287 / CA3] Agent d'abord : la phrase libre va à l'agent AVANT les raccourcis.
    # Restent avant lui : les gardes de dialogue, et les textes EXACTS des boutons.
    if agent_prioritaire and texte_min not in canal.boutons_exacts:
        if await _attendre(canal.dialogue(texte)):
            return Distribution(pris_par_le_canal=True, garde="dialogue", mode_agent_prioritaire=True)
        resultat = svc_interpreteur.agent_d_abord(texte, ctx, contexte_court=canal.contexte_court())

    if resultat is svc_interpreteur.CASCADE_HABITUELLE:
        if await _attendre(canal.raccourcis(texte)):
            return Distribution(pris_par_le_canal=True, garde="raccourci", mode_agent_prioritaire=agent_prioritaire)
        # [US-172] La phrase désigne-t-elle une COMMANDE ? Placé après les flux guidés et
        # AVANT le routeur : une phrase reconnue comme commande n'atteint jamais le parseur.
        # En mode `prioritaire`, le profil et le carnet ont déjà été lus, et l'agent consulté.
        if not agent_prioritaire and await _attendre(canal.dialogue(texte)):
            return Distribution(pris_par_le_canal=True, garde="dialogue")
        resultat = svc_interpreteur.interpreter(
            texte, ctx, contexte_court=canal.contexte_court(), consulter_agent_d_abord=False,
        )
    return Distribution(resultat=resultat, mode_agent_prioritaire=agent_prioritaire)


def presente_par_le_canal(resultat: Any) -> bool:
    """Le résultat est-il une réponse à montrer (et non une simple orientation) ?

    Un `Aiguillage` « question » ou « geste » n'est pas une réponse : l'agent dit où va
    la phrase. Les autres aiguillages sans texte (précision, hors périmètre) tombent sur
    le chemin habituel ; seul `non_compris` se dit. `None` : ce n'est pas une commande.
    """
    if resultat is None:
        return False
    if isinstance(resultat, svc_interpreteur.Aiguillage):
        return resultat.vers == svc_interpreteur.VERS_NON_COMPRIS
    return True


def orienter(resultat: Any, texte: str, ctx: Optional[TenantContext], contexte_ecran: Any = None) -> Orientation:
    """[US-270 / CA4, CA5] Question ou geste, pour une phrase que le canal n'a pas présentée.

    Une question part à la cascade COMMUNE (`routeur.repondre_avec_cascade`, E0) avec la
    nature que l'agent a donnée ; un geste, au parseur. Sans avis de l'agent, le routeur
    décide (US-170) — il porte les règles, le cache de classification et le modèle en
    dernier recours.

    [US-323 / C5, CA3] `contexte_ecran` (PWA) : avec une culture ou une parcelle sous les yeux,
    une phrase qui n'est pas une question est un geste — sans classification par le modèle.
    """
    from llm import routeur  # import local : le routeur importe la base

    aiguillage = resultat if isinstance(resultat, svc_interpreteur.Aiguillage) else None
    if aiguillage is not None and aiguillage.vers == svc_interpreteur.VERS_QUESTION:
        log.info("❓ QUESTION AGENT  : nature=%s", aiguillage.nature_question)
        return Orientation(SUITE_QUESTION, nature=aiguillage.nature_question)
    if aiguillage is not None and aiguillage.vers == svc_interpreteur.VERS_GESTE:
        return Orientation(SUITE_GESTE)
    from app.services.compagnon import contexte_ecran as svc_contexte_ecran

    if svc_contexte_ecran.oriente_vers_un_geste(texte, contexte_ecran):
        log.info("📍 GESTE CONTEXTE  : %s", contexte_ecran.libelle())
        return Orientation(SUITE_GESTE)
    decision = routeur.classer_demande(texte, ctx)
    if decision.nature != routeur.NATURE_ACTION:
        log.info("❓ QUESTION AUTO   : nature=%s → cascade", decision.nature)
        return Orientation(SUITE_QUESTION)
    return Orientation(SUITE_GESTE)


def repondre_a_une_question(ctx: TenantContext, question: str, nature: Optional[str] = None):
    """[US-270 / CA5, E0] La cascade des questions, la même pour tous les canaux.

    `/ask` (bot et API) et la phrase interrogative passent ici : une seule réponse
    (R3). Peut lever `LLMIndisponibleError`.
    """
    from llm import routeur

    if nature:
        return routeur.repondre_avec_cascade(
            ctx, question,
            decision=routeur.DecisionRoutage(nature=nature, origine=routeur.ORIGINE_AGENT, confiance=1.0),
        )
    return routeur.repondre_avec_cascade(ctx, question)


def repondre_en_mode_support(ctx: TenantContext, question: str):
    """[US-271 / mode Support, articulation §5.3] Le corpus de l'application d'abord.

    La phrase va droit à la cascade avec la nature `QUESTION_SAVOIR` et la famille `doc_app`
    imposée : ni classification, ni agent, ni écriture possible. C'est le moins cher des modes.
    """
    from app.services import connaissance
    from llm import routeur

    return routeur.repondre_avec_cascade(
        ctx, question,
        decision=routeur.DecisionRoutage(
            nature=routeur.NATURE_QUESTION_SAVOIR, origine=routeur.ORIGINE_AGENT, confiance=1.0),
        famille=connaissance.FAMILLE_DOC_APP,
    )


def analyser_le_potager(ctx: TenantContext, question: str):
    """[US-273 / mode Extra, articulation §5.4] Une analyse approfondie, en lecture seule.

    Commune aux deux canaux (bouton « Approfondir » de la PWA, `/approfondir` du bot) : la boucle
    n'expose que des outils de lecture, elle ne range aucune proposition et n'écrit aucun
    événement. Peut lever `LLMIndisponibleError`.
    """
    from app.services.compagnon import analyse

    return analyse.analyser(question, ctx)


# ═════════════════════════════════════════════════════════════════════════════
# Le contexte que l'agent lit avec la phrase — commun aux canaux
# ═════════════════════════════════════════════════════════════════════════════
#: Délai de la proposition en attente dans le contexte de l'agent (secondes).
DELAI_PROPOSITION_S = int(svc_propositions.DUREE_CONVERSATION.total_seconds())


def resume_de_proposition(commande) -> str:
    """La proposition en une ligne, telle que l'agent la lit."""
    if isinstance(commande, svc_interpreteur.Plan):
        return " ; ".join(etape.commande_equivalente() for etape in commande.etapes)
    return commande.commande_equivalente()


def ailleurs_de(tenant: TenantContext) -> tuple[str, ...]:
    """[US-260 / CA4] Les propositions qui attendent ce jardinier dans un AUTRE potager, nommées."""
    try:
        autres = svc_propositions.en_attente_ailleurs(tenant.user_id, tenant.potager_id)
    except Exception:  # noqa: BLE001 — sans elles, « oui » ne verra qu'une proposition : on ne les ignore pas
        log.exception("[US-260 / CA4] Propositions des autres potagers illisibles")
        return ()
    return tuple(
        f"dans {svc_propositions.potager_a_nommer(p.user_id, p.potager_id) or 'un autre potager'} : "
        f"{resume_de_proposition(p.commande)}"
        for p in autres
    )


def contexte_court_du_jardinier(tenant: TenantContext, spontane: Optional[dict] = None,
                                sous_les_yeux: Optional[dict] = None):
    """[US-238, US-259, US-270] Le contexte de la conversation du jardinier qui écrit, ou None.

    Le même pour Telegram et la PWA (R3, R5) : la proposition en attente de CE jardinier dans
    CE potager, lue en base ; les 10 derniers échanges ; la dernière proposition traitée quand
    aucune n'attend ; les propositions des autres potagers. `spontane` : le message spontané
    auquel il répond (US-267 / CA8), que seul le canal sait désigner. Une mémoire illisible ne
    bloque jamais la phrase : elle passe sans contexte.

    [US-323 / C5] `sous_les_yeux` : le contexte d'écran de la PWA, vérifié (`contexte_ecran`).
    """
    try:
        proposition = svc_propositions.en_attente(tenant.user_id, tenant.potager_id)
    except Exception:  # noqa: BLE001
        log.exception("[US-259] Proposition en attente illisible — phrase traitée sans elle")
        proposition = None
    echanges = svc_conversations.recents(tenant)
    ailleurs = ailleurs_de(tenant)
    # [US-284 / CA2] La question que le compagnon vient de poser, 10 minutes au plus.
    question = svc_contexte_court.question_de(echanges)
    if proposition is None:
        traitee = None
        try:
            derniere = svc_propositions.derniere_traitee(tenant.user_id, tenant.potager_id)
        except Exception:  # noqa: BLE001
            log.exception("[US-260 / CA5] Dernière proposition traitée illisible")
            derniere = None
        if derniere is not None:
            traitee = svc_contexte_court.Traitee(
                code=derniere.code, etat=derniere.etat, resume=resume_de_proposition(derniere.commande),
                traite_le=derniere.traite_le, canal=derniere.traite_canal or derniere.canal,
            )
        return svc_contexte_court.construire(tenant, echanges=echanges, ailleurs=ailleurs, traitee=traitee,
                                             spontane=spontane, question=question,
                                             sous_les_yeux=sous_les_yeux)
    return svc_contexte_court.construire(
        tenant, proposition.commande, proposition.ts, proposition.potager_id,
        ecartes=proposition.ecartes, delai=DELAI_PROPOSITION_S, echanges=echanges,
        code=proposition.code, ailleurs=ailleurs, spontane=spontane, question=question,
        sous_les_yeux=sous_les_yeux,
    )


def noter_echange(ctx: TenantContext, resultat: Any, canal: str, contexte: Optional[dict] = None) -> None:
    """[US-259 / CA1, US-284] Chaque phrase interprétée devient un échange de la conversation,
    avec la proposition qu'elle a laissée en attente, s'il y en a une — dans ce canal ou l'autre.

    Une phrase qui ne laisse aucun échange (rien compris) efface la question en attente : elle l'a
    lue, elle l'a consommée (CA4).

    [US-323 / CA6] `contexte` : le contexte d'écran de la phrase, gardé avec l'échange.
    """
    try:
        echange = svc_contexte_court.echange_de(resultat)
        if echange is None:
            svc_conversations.clore_question(ctx)
            return
        propose = isinstance(resultat, (svc_interpreteur.CommandeInterpretee, svc_interpreteur.Plan)) or (
            isinstance(resultat, svc_interpreteur.ReponseAgent) and resultat.proposition is not None
        )
        proposition = svc_propositions.en_attente(ctx.user_id, ctx.potager_id) if propose else None
        svc_conversations.noter(
            ctx, echange.texte, echange.resume, canal=canal,
            outils=tuple(getattr(resultat, "outils", ()) or ()),
            proposition_id=proposition.id if proposition is not None else None,
            question=echange.question, contexte=contexte,
        )
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-259 / CA1] Échange non retenu")
