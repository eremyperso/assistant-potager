"""
app/services/compagnon/echange_pwa.py — Le compagnon vu de la PWA [US-270]
============================================================================
L'API n'a aucune logique : elle appelle ce module, qui fait pour la PWA ce que
`app/bot/messages.handle_text` fait pour Telegram — par le MÊME orchestrateur
(`orchestrateur.distribuer`, puis `orienter`). Le canal ne décide rien (R5) : il
montre. Ce qu'il sait faire, et ce qu'il ne sait pas :

* une **question** part à la cascade commune (E0) ;
* un **geste** compris devient une carte à confirmer DANS la PWA (levée d'A16) :
  il attend en base (`gestes_conversation`) et s'écrit par `app.services.gestes` ;
* une **commande** ou un **plan** compris sont rangés en base, visibles dans Telegram (US-259).
  [US-289] Ceux qui ont un exécuteur de service (`agent/executeurs` : `/parcelle ajouter|modifier`,
  seuls ou en plan ; corrections) se confirment AUSSI ici, par le même service que le bot. Les
  autres passent par les gestionnaires de commandes du bot, que la PWA n'a pas : la carte le dit
  (`confirmable=False`), elle peut en revanche être abandonnée ;
* les parcours guidés de Telegram (corriger, déplacer, note, godets) n'ont pas
  d'équivalent à l'écran : la phrase va à l'agent, qui les propose en commande.

La réponse porte toujours un texte et, s'il y en a, les cartes en attente.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy import or_

from app.services import interpreteur_commandes as svc_interpreteur
from app.services.agent import executeurs as svc_executeurs
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import corrections as svc_corrections
from app.services.compagnon import decisions as svc_decisions
from app.services.compagnon import deux_canaux as svc_deux_canaux
from app.services.compagnon import distribution as svc_distribution
from app.services.compagnon import gestes_conversation as svc_gestes_dits
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.compagnon import proactivite as svc_proactivite
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from database.models import Proposition
from llm.passerelle import LLMIndisponibleError  # noqa: F401  (remonte à la route : 503)

log = logging.getLogger("potager")

CANAL = svc_propositions.CANAL_PWA

# Ce que la réponse est, pour l'écran.
VERS_REPONSE = "reponse"        # un texte : salutation, précision demandée, refus
VERS_QUESTION = "question"      # la cascade a répondu (savoir, données, raisonnement)
VERS_GESTE = "geste"            # un geste compris : une carte à confirmer
VERS_COMMANDE = "commande"      # une commande ou un plan : une carte, confirmable dans Telegram
VERS_DECISION = "decision"      # « laisse tomber » : la proposition en attente est abandonnée
VERS_ANALYSE = "analyse"        # [US-273] une synthèse en lecture seule, avec ses sources

#: [US-271 / CA1] Les modes du panneau. Normal : l'agent, les gestes, les commandes. Support : le
#: corpus de l'application d'abord, jamais d'écriture (articulation §5.3).
MODE_NORMAL = "normal"
MODE_SUPPORT = "support"
#: [US-273 / CA1] Extra : le bouton « Approfondir » — une analyse en lecture seule, jamais d'écriture.
MODE_ANALYSE = "analyse"
MODES = (MODE_NORMAL, MODE_SUPPORT, MODE_ANALYSE)

TEXTE_COMMANDE_TELEGRAM = (
    "Cette commande se confirme dans Telegram, avec le bouton de sa carte : "
    "la PWA ne sait pas encore l'exécuter. Tu peux la laisser tomber d'ici."
)
TEXTE_REGLAGE_PROFIL = (
    "Les réglages du compagnon (prénom, ton, messages spontanés) se font dans « Mon compagnon », "
    "ou avec /profil dans Telegram."
)


class TexteVideError(ValueError):
    """La phrase est vide : rien à envoyer au compagnon."""


class ModeInconnuError(ValueError):
    """Le mode demandé n'existe pas (ni normal, ni support)."""


class NonConfirmableDansLaPwaError(Exception):
    """La proposition est une commande ou un plan : elle se confirme dans Telegram."""


@dataclass
class ReponseCompagnon:
    """Ce que le compagnon répond à une phrase : un texte et des cartes en attente."""

    texte: str
    vers: str = VERS_REPONSE
    propositions: list[dict] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    #: Pour le retour 👍/👎 sur une réponse de savoir (US-097 / CA9) ; None sinon.
    routage_log_id: Optional[int] = None
    etage: Optional[str] = None
    #: [US-273 / CA4] Les sources citées par une analyse ; vide pour toute autre réponse.
    sources: list[str] = field(default_factory=list)
    #: [US-273 / CA3] La borne qui a coupé l'analyse (« tours », « jetons »), vide sinon.
    borne: str = ""
    #: [US-303 / CA8] L'échange retenu pour cette réponse : la PWA demande sa lecture par lui.
    echange_id: Optional[int] = None

    def en_donnees(self) -> dict:
        donnees = {
            "texte": self.texte, "vers": self.vers, "propositions": self.propositions,
            "avertissements": self.avertissements, "routage_log_id": self.routage_log_id,
            "etage": self.etage, "echange_id": self.echange_id,
        }
        if self.vers == VERS_ANALYSE:
            donnees["sources"] = self.sources
            donnees["borne"] = self.borne or None
        return donnees


# ═════════════════════════════════════════════════════════════════════════════
# Les cartes
# ═════════════════════════════════════════════════════════════════════════════
def _iso(instant: Optional[datetime]) -> Optional[str]:
    return instant.isoformat() if instant is not None else None


def _suivi(etat: str, traite_canal: Optional[str], traite_le: Optional[datetime], user_id: Optional[int],
           potager_id: Optional[int]) -> dict:
    """[US-272] Ce que la carte dit de plus que son état : où et quand elle a été traitée (CA3),
    et le potager où elle s'exécute quand le jardinier en a plusieurs (CA6 / F5)."""
    potager = (svc_propositions.potager_a_nommer(user_id, potager_id)
               if user_id is not None and potager_id is not None else None)
    return {
        "traite_canal": traite_canal, "traite_le": _iso(traite_le),
        "etat_dit": svc_deux_canaux.texte_etat(etat, traite_canal, traite_le) or None,
        "potager": potager,
    }


def carte_de_geste(geste: svc_gestes_dits.GesteDit, avertissements: Optional[list[str]] = None) -> dict:
    """La carte d'un geste dit : ses lignes, et le droit de le confirmer ici."""
    return {
        **_suivi(geste.etat, geste.traite_canal, geste.traite_le, geste.user_id, geste.potager_id),
        "id": geste.id, "code": geste.code, "nature": svc_propositions.NATURE_GESTE,
        "resume": " ; ".join(svc_gestes_dits.resume(item) for item in geste.items),
        "lignes": [svc_gestes_dits.resume(item) for item in geste.items],
        "items": geste.items, "phrase": geste.texte, "etat": geste.etat, "cree_le": _iso(geste.cree_le),
        "expire_le": _iso(geste.expire_le), "confirmable": geste.en_attente,
        "motif_non_confirmable": None, "avertissements": avertissements or [],
    }


def s_execute_dans_la_pwa(commande: Any) -> bool:
    """[US-289] Cette commande ou ce plan a-t-il un exécuteur de service, sans Telegram ?

    Ceux de `agent/executeurs` (`/parcelle ajouter|modifier`, seuls ou en plan) et les corrections
    (`corrections.executer`). Toute autre forme garde son handler de bot : elle se confirme dans Telegram.
    """
    if isinstance(commande, svc_interpreteur.Plan):
        return bool(commande.etapes) and all(svc_executeurs.admise_dans_un_plan(e) for e in commande.etapes)
    if svc_corrections.est_correction(commande):
        return True
    forme = getattr(commande, "forme", None)
    return forme is not None and forme.cle in svc_executeurs.EXECUTEURS


def carte_de_commande(proposition: svc_propositions.PropositionConversation) -> dict:
    """La carte d'une commande ou d'un plan : confirmable ici quand un exécuteur de service existe
    [US-289], sinon visible ici et confirmable dans Telegram."""
    commande = proposition.commande
    ici = s_execute_dans_la_pwa(commande)
    if isinstance(commande, svc_interpreteur.Plan):
        lignes = [etape.commande_equivalente() for etape in commande.etapes]
    else:
        lignes = [commande.commande_equivalente()]
    return {
        **_suivi(proposition.etat, proposition.traite_canal, proposition.traite_le, proposition.user_id,
                 proposition.potager_id),
        "id": proposition.id, "code": proposition.code, "nature": proposition.nature,
        "resume": " ; ".join(lignes), "lignes": lignes, "items": [], "phrase": None, "etat": proposition.etat,
        "cree_le": _iso(proposition.cree_le), "expire_le": _iso(proposition.expire_le),
        "confirmable": ici and proposition.en_attente,
        "motif_non_confirmable": None if ici else TEXTE_COMMANDE_TELEGRAM, "avertissements": [],
    }


def cartes_en_cours(ctx: TenantContext) -> list[dict]:
    """[CA3] Les cartes qui attendent ce jardinier dans ce potager : gestes dits, commande ou plan."""
    cartes = [carte_de_geste(g) for g in svc_gestes_dits.en_attente(ctx)]
    proposition = svc_propositions.en_attente(ctx.user_id, ctx.potager_id)
    if proposition is not None:
        cartes.append(carte_de_commande(proposition))
    cartes.sort(key=lambda c: c["cree_le"] or "", reverse=True)
    return cartes


def historique(ctx: TenantContext) -> dict:
    """[CA3] Les échanges récents (les mêmes que lit le bot), les cartes en cours et les messages
    spontanés du compagnon [US-271 / CA3]."""
    echanges = svc_conversations.recents_avec_id(ctx)
    return {
        # [US-271 / CA3] Ce que le compagnon a dit de lui-même, rangé avec la conversation.
        "spontanes": svc_distribution.messages_du_jardinier(ctx),
        "echanges": [
            {"jardinier": e.texte, "compagnon": e.resume,
             "ts": datetime.utcfromtimestamp(e.ts).isoformat() + "Z",
             # [US-303 / CA8] ▶ sur une réponse ancienne : sa lecture se demande par cet identifiant.
             "echange_id": echange_id}
            for echange_id, e in echanges
        ],
        "cartes": cartes_en_cours(ctx),
        # [US-272 / CA9] Sans Telegram lié : le panneau seul, et une invitation à l'activer, une fois.
        "telegram_lie": svc_deux_canaux.telegram_lie(ctx.user_id),
        "invitation_telegram": svc_deux_canaux.invitation_telegram(ctx.user_id),
    }


#: [US-272 / CA5] Une carte traitée reste visible ce temps-là : le rafraîchissement du panneau y lit
#: son état réel, qu'elle ait été traitée ici ou dans Telegram.
FENETRE_TRAITEES = timedelta(hours=12)


def cartes_traitees(ctx: TenantContext, maintenant: Optional[datetime] = None) -> list[dict]:
    """[US-272 / CA5] Les cartes sorties de l'attente depuis moins de 12 h, dans ce potager."""
    instant = maintenant or datetime.utcnow()
    with svc_propositions.session_sur(ctx.potager_id) as db:
        lignes = (
            db.query(Proposition.id, Proposition.nature)
            .filter(
                Proposition.user_id == ctx.user_id, Proposition.potager_id == ctx.potager_id,
                Proposition.etat != svc_propositions.ETAT_EN_ATTENTE,
                Proposition.traite_le >= instant - FENETRE_TRAITEES,
                or_(Proposition.nature.in_(svc_propositions.NATURES_CONVERSATION),
                    Proposition.ecran == svc_gestes_dits.ECRAN_COMPAGNON),
            )
            .order_by(Proposition.traite_le.desc(), Proposition.id.desc())
            .limit(20)
            .all()
        )
    cartes: list[dict] = []
    for pid, nature in lignes:
        if nature == svc_propositions.NATURE_GESTE:
            try:
                cartes.append(carte_de_geste(svc_gestes_dits.par_id(ctx, pid)))
            except svc_gestes_dits.GesteIntrouvableError:
                continue
        else:
            proposition = svc_propositions.par_id(pid, ctx.user_id, ctx.potager_id)
            if proposition is not None:
                cartes.append(carte_de_commande(proposition))
    return cartes


def etat(ctx: TenantContext) -> dict:
    """[US-272 / CA5] Ce que le panneau relit à intervalle court, sans WebSocket : l'état réel des cartes
    (en attente ET récemment traitées) et les messages spontanés. Lecture seule, rien n'est noté."""
    return {
        "cartes": cartes_en_cours(ctx),
        "traitees": cartes_traitees(ctx),
        "spontanes": svc_distribution.messages_du_jardinier(ctx),
    }


# ═════════════════════════════════════════════════════════════════════════════
# Une phrase
# ═════════════════════════════════════════════════════════════════════════════
def _executer(coroutine):
    """Joue la coroutine de l'orchestrateur depuis une route synchrone (sans boucle dans son fil)."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coroutine).result()


def repondre(ctx: TenantContext, texte: str, mode: str = MODE_NORMAL) -> ReponseCompagnon:
    """[US-270 / CA1] Transmet la phrase à l'orchestrateur et rend la réponse et les cartes éventuelles.

    [US-303 / CA8] La réponse porte `echange_id`, l'échange que cette phrase a laissé dans la
    conversation (le dernier écrit pendant l'appel) ; None si aucun ne l'a été.
    """
    avant = svc_conversations.dernier_id(ctx)
    reponse = _repondre(ctx, texte, mode)
    apres = svc_conversations.dernier_id(ctx)
    if apres is not None and apres != avant:
        reponse.echange_id = apres
    return reponse


def _repondre(ctx: TenantContext, texte: str, mode: str = MODE_NORMAL) -> ReponseCompagnon:
    """[US-270 / CA1] Transmet la phrase à l'orchestrateur et rend la réponse et les cartes éventuelles.

    [US-271 / CA1] `mode="support"` : la phrase va droit à la documentation de l'application, sans
    agent ni geste — le mode ne peut rien écrire.

    Peut lever `TexteVideError`, `LLMIndisponibleError` (le canal répond 503),
    `PermissionInsuffisanteError` (un lecteur ne dit pas de geste) ou `PotagerArchiveError`.
    """
    phrase = (texte or "").strip()
    if not phrase:
        raise TexteVideError("Dis-moi quelque chose.")
    if mode not in MODES:
        raise ModeInconnuError(f"Mode inconnu : {mode!r} (attendu : {', '.join(MODES)}).")
    if mode == MODE_SUPPORT:
        return _repondre_en_support(ctx, phrase)
    if mode == MODE_ANALYSE:
        return _repondre_en_analyse(ctx, phrase)

    reglage: list[str] = []

    def _dialogue(t: str) -> bool:
        # « arrête de me parler de la météo » : une proposition de réglage à boutons, côté Telegram.
        if svc_proactivite.lire_phrase(t) is not None:
            reglage.append(TEXTE_REGLAGE_PROFIL)
            return True
        return False

    canal = svc_orchestrateur.Canal(
        nom=CANAL, dialogue=_dialogue,
        contexte_court=lambda: svc_orchestrateur.contexte_court_du_jardinier(ctx),
    )
    distribution = _executer(svc_orchestrateur.distribuer(phrase, ctx, canal))
    if distribution.pris_par_le_canal:
        reponse = ReponseCompagnon(texte=reglage[0] if reglage else "")
        _noter(ctx, phrase, reponse)
        return reponse

    resultat = distribution.resultat
    if svc_orchestrateur.presente_par_le_canal(resultat):
        reponse = _presenter(ctx, phrase, resultat)
        svc_orchestrateur.noter_echange(ctx, resultat, CANAL)
        return reponse

    # Ni commande ni réponse : question (cascade commune) ou geste (parseur).
    svc_orchestrateur.noter_echange(ctx, resultat, CANAL)
    suite = svc_orchestrateur.orienter(resultat, phrase, ctx)
    if suite.vers == svc_orchestrateur.SUITE_QUESTION:
        return _repondre_a_la_question(ctx, phrase, suite.nature)
    return _proposer_un_geste(ctx, phrase)


def _noter(ctx: TenantContext, phrase: str, reponse: ReponseCompagnon, outils: tuple[str, ...] = ()) -> None:
    """[US-259 / CA1] L'échange rejoint la conversation du jardinier, celle que Telegram lira aussi."""
    if not reponse.texte:
        return
    try:
        svc_conversations.noter(ctx, phrase, reponse.texte, canal=CANAL, outils=outils)
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-270] Échange non retenu")


def _repondre_a_la_question(ctx: TenantContext, phrase: str, nature: Optional[str]) -> ReponseCompagnon:
    """[US-270 / CA5] La cascade commune : la même réponse que le bot, avec de quoi la noter 👍/👎."""
    resultat = svc_orchestrateur.repondre_a_une_question(ctx, phrase, nature)
    reponse = ReponseCompagnon(
        texte=resultat.texte, vers=VERS_QUESTION,
        routage_log_id=resultat.routage_log_id, etage=resultat.etage_resolveur,
    )
    _noter(ctx, phrase, reponse, outils=("question",))
    return reponse


def _repondre_en_support(ctx: TenantContext, phrase: str) -> ReponseCompagnon:
    """[US-271] Mode Support : la cascade avec le corpus de l'application imposé."""
    resultat = svc_orchestrateur.repondre_en_mode_support(ctx, phrase)
    reponse = ReponseCompagnon(
        texte=resultat.texte, vers=VERS_QUESTION,
        routage_log_id=resultat.routage_log_id, etage=resultat.etage_resolveur,
    )
    _noter(ctx, phrase, reponse, outils=("support",))
    return reponse


def _repondre_en_analyse(ctx: TenantContext, phrase: str) -> ReponseCompagnon:
    """[US-273] Mode Extra : une boucle de lecture, une synthèse avec ses sources. Aucune carte,
    aucune proposition, aucun événement : l'analyse ne propose des actions qu'en texte (CA5)."""
    resultat = svc_orchestrateur.analyser_le_potager(ctx, phrase)
    reponse = ReponseCompagnon(
        texte=resultat.texte, vers=VERS_ANALYSE,
        sources=list(resultat.sources), borne=resultat.borne,
    )
    _noter(ctx, phrase, reponse, outils=("analyse", *resultat.outils))
    return reponse


def _proposer_un_geste(ctx: TenantContext, phrase: str) -> ReponseCompagnon:
    """Un geste compris devient une carte à confirmer ; ce qui manque devient une question."""
    with svc_propositions.session_sur(ctx.potager_id) as db:
        preparation = svc_gestes_dits.preparer(db, ctx, phrase)
        avertissements: list[str] = []
        if preparation.items:
            avertissements = _avertissements(db, ctx, preparation.items)

    if preparation.question:
        # Le parseur a reconnu une question dans une phrase d'action : elle part à la cascade.
        return _repondre_a_la_question(ctx, phrase, None)
    if preparation.precision or not preparation.items:
        reponse = ReponseCompagnon(texte=preparation.precision or "Je n'ai détecté aucune action à enregistrer.")
        _noter(ctx, phrase, reponse)
        return reponse

    geste = svc_gestes_dits.proposer(ctx, preparation.items, phrase)
    # [US-272 / CA1, CA4] La carte part dans Telegram dès sa création ; celle qu'elle remplace y est réécrite.
    svc_deux_canaux.apres_creation(geste.id, ctx.potager_id)
    reponse = ReponseCompagnon(
        texte="Voici ce que j'ai compris. Je n'écris rien tant que tu n'as pas confirmé.",
        vers=VERS_GESTE, propositions=[carte_de_geste(geste, avertissements)], avertissements=avertissements,
    )
    _noter(ctx, phrase, ReponseCompagnon(texte="proposition : " + reponse.propositions[0]["resume"]),
           outils=("geste",))
    return reponse


def _avertissements(db, ctx: TenantContext, items: list[dict]) -> list[str]:
    """[US-167] Rotation et association, évaluées AVANT toute écriture, montrées sur la carte."""
    from app.services import gestes as svc_gestes

    try:
        return svc_gestes.evaluer_avertissements(db, ctx, items)
    except Exception:  # noqa: BLE001 — un avertissement manqué ne bloque pas la proposition
        log.exception("[US-270] Avertissements de plantation non évalués")
        return []


# ── ce que l'interpréteur a lu ───────────────────────────────────────────────
def _presenter(ctx: TenantContext, phrase: str, resultat: Any) -> ReponseCompagnon:
    if isinstance(resultat, svc_interpreteur.ReponseAgent):
        return _presenter_agent(ctx, resultat)
    if isinstance(resultat, svc_interpreteur.Aiguillage):
        commande = (resultat.message or "/menu").replace("`", "")
        return ReponseCompagnon(texte=(
            "Je n'ai pas réussi à traiter cette demande : je ne l'ai pas comprise, ou le service est "
            f"momentanément indisponible. Rien n'a été fait. Réessaie dans un instant, ou passe par la "
            f"commande : {commande}."
        ))
    if isinstance(resultat, svc_interpreteur.Ambiguite):
        lignes = [f"• {c.forme.libelle} : {c.commande_equivalente()}" for c in resultat.candidats]
        return ReponseCompagnon(texte="Plusieurs commandes sont possibles, laquelle ?\n" + "\n".join(lignes)
                                + "\nReformule, ou tape directement la commande voulue.")
    return _proposer_une_commande(ctx, resultat, preambule="")


def _presenter_agent(ctx: TenantContext, reponse: svc_interpreteur.ReponseAgent) -> ReponseCompagnon:
    if reponse.decision is not None:
        return _decider(ctx, reponse.decision)
    if reponse.proposition is not None:
        return _proposer_une_commande(ctx, reponse.proposition, preambule=reponse.texte)
    return ReponseCompagnon(texte=reponse.texte)


def _proposer_une_commande(ctx: TenantContext, commande: Any, preambule: str) -> ReponseCompagnon:
    """Une commande ou un plan compris : rangés en base (Telegram les voit), montrés en carte.

    Incomplète (valeur manquante, nom voisin, mot non compris), elle n'est PAS rangée : le
    compagnon pose sa question, la phrase suivante la reprend (US-250).
    """
    forme = getattr(commande, "forme", None)
    if forme is not None and not forme.confirmation:
        # Une consultation (plan, stats, calendrier…) s'exécute sans confirmation côté Telegram ;
        # le portail a ses écrans pour cela : rien n'est rangé, la carte n'aurait rien à confirmer.
        return ReponseCompagnon(texte=preambule or (
            f"Tu trouveras cela dans l'écran correspondant du portail, ou avec {commande.commande_equivalente()} "
            "dans Telegram."))
    if not svc_decisions.est_prete(commande):
        question = getattr(getattr(commande, "precision", None), "question", None)
        return ReponseCompagnon(texte=preambule or question or (
            "Il me manque une précision pour faire cela. Redis ta demande avec le détail."))

    ancienne = svc_propositions.en_attente(ctx.user_id, ctx.potager_id)
    if ancienne is not None:
        svc_interpreteur.persister_journal(ctx, ancienne.commande, svc_interpreteur.ISSUE_ABANDONNEE, ancienne.log_id)
    log_id = svc_interpreteur.persister_journal(ctx, commande, svc_interpreteur.ISSUE_PROPOSEE)
    proposition = svc_propositions.proposer(ctx, commande, log_id=log_id, canal=CANAL)
    # [US-272 / CA1, CA4] Telegram la reçoit aussi, avec ses boutons ; celle qu'elle remplace y est réécrite.
    svc_deux_canaux.apres_creation(proposition.id, ctx.potager_id)
    carte = carte_de_commande(proposition)
    return ReponseCompagnon(
        texte=preambule or "Voici ce que je te propose.", vers=VERS_COMMANDE, propositions=[carte],
    )


def _decider(ctx: TenantContext, decision: svc_decisions.Decision) -> ReponseCompagnon:
    """[US-260] « Laisse tomber » : la proposition en attente est abandonnée comme par le bouton.

    [US-289] « Vas-y » sur une commande qui a un exécuteur de service : elle s'exécute ici, sauf si
    elle est destructrice (bouton seul, US-260 / CA3). Les autres se confirment dans Telegram."""
    proposition = svc_propositions.par_code(decision.code, ctx.user_id)
    if decision.action == svc_decisions.ACTION_ABANDONNER:
        if proposition is not None and proposition.en_attente:
            if svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE, canal=CANAL):
                svc_interpreteur.persister_journal(
                    ctx, proposition.commande, svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id,
                )
                svc_deux_canaux.reecrire(proposition.id)  # [US-272 / CA3]
        return ReponseCompagnon(texte=svc_decisions.TEXTE_ABANDONNEE, vers=VERS_DECISION)
    if (proposition is not None and proposition.en_attente and proposition.potager_id == ctx.potager_id
            and s_execute_dans_la_pwa(proposition.commande)):
        if svc_decisions.est_destructrice(proposition.commande):
            return ReponseCompagnon(
                texte=svc_decisions.TEXTE_BOUTON_SEUL, vers=VERS_DECISION,
                propositions=[carte_de_commande(proposition)],
            )
        resultat = _confirmer_commande(ctx, proposition)
        return ReponseCompagnon(texte=resultat.texte, vers=VERS_DECISION, propositions=[resultat.carte])
    return ReponseCompagnon(texte=TEXTE_COMMANDE_TELEGRAM, vers=VERS_DECISION)


# ═════════════════════════════════════════════════════════════════════════════
# Confirmer, abandonner une carte
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class ResultatConfirmation:
    """Ce que la confirmation d'une carte a écrit, ou refusé."""

    carte: dict
    texte: str
    enregistres: list[dict] = field(default_factory=list)
    erreur: Optional[str] = None
    avertissements: list[str] = field(default_factory=list)

    def en_donnees(self) -> dict:
        return {
            "carte": self.carte, "texte": self.texte, "enregistres": self.enregistres,
            "erreur": self.erreur, "avertissements": self.avertissements,
        }


def _est_un_geste_dit(ctx: TenantContext, proposition_id: int) -> bool:
    try:
        svc_gestes_dits.par_id(ctx, proposition_id)
        return True
    except svc_gestes_dits.GesteIntrouvableError:
        return False


def confirmer(ctx: TenantContext, proposition_id: int, canal: str = CANAL) -> ResultatConfirmation:
    """[US-270 / CA2] Confirme une carte : sortie atomique de l'attente, puis écriture (règles d'US-259).

    [US-289] Une commande ou un plan qui a un exécuteur de service s'exécute ici de la même façon ;
    les autres se confirment dans Telegram.

    [US-292] `canal` : `pwa` par défaut, `mcp` quand un assistant IA connecté confirme.

    Lève `GesteIntrouvableError` (404), `GesteDejaTraiteError` (409 : déjà confirmée, abandonnée,
    remplacée ou périmée — la seconde confirmation n'écrit rien) ou `NonConfirmableDansLaPwaError`.
    """
    if not _est_un_geste_dit(ctx, proposition_id):
        return _confirmer_commande(ctx, _commande_par_id(ctx, proposition_id), canal)
    geste, resultat = svc_gestes_dits.confirmer(ctx, proposition_id, canal=canal)
    svc_deux_canaux.reecrire(geste.id)  # [US-272 / CA3] sans effet si le geste est revenu en attente
    enregistres = [{"event_id": eid, "resume": svc_gestes_dits.resume(item)} for item, eid in resultat.enregistres]
    if resultat.complet:
        texte = "✅ Confirmé" if len(enregistres) <= 1 else f"✅ Confirmé — {len(enregistres)} gestes enregistrés"
        return ResultatConfirmation(
            carte=carte_de_geste(geste), texte=texte, enregistres=enregistres,
            avertissements=resultat.avertissements,
        )
    texte = f"❌ {resultat.erreur}"
    if enregistres:
        texte += " — déjà enregistré avant l'erreur : " + ", ".join(e["resume"] for e in enregistres) + "."
    if resultat.parcelle_inconnue:
        texte += f" Crée-la d'abord (/parcelle ajouter {resultat.parcelle_inconnue})."
    return ResultatConfirmation(
        carte=carte_de_geste(geste), texte=texte, enregistres=enregistres, erreur=resultat.erreur,
        avertissements=resultat.avertissements,
    )


def abandonner(ctx: TenantContext, proposition_id: int, canal: str = CANAL) -> ResultatConfirmation:
    """[US-270 / CA2] Laisse tomber une carte (geste ou commande) : sortie atomique, rien n'est écrit."""
    if _est_un_geste_dit(ctx, proposition_id):
        geste = svc_gestes_dits.abandonner(ctx, proposition_id, canal=canal)
        svc_deux_canaux.reecrire(geste.id)  # [US-272 / CA3]
        return ResultatConfirmation(carte=carte_de_geste(geste), texte=svc_decisions.TEXTE_ABANDONNEE)
    proposition = _commande_par_id(ctx, proposition_id)
    if not proposition.en_attente or proposition.expiree():
        raise svc_gestes_dits.GesteDejaTraiteError(
            proposition.etat if proposition.en_attente is False else svc_propositions.ETAT_PERIMEE,
            proposition.traite_canal or proposition.canal, proposition.traite_le,
        )
    if not svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE, canal=canal):
        autre = _commande_par_id(ctx, proposition_id)
        raise svc_gestes_dits.GesteDejaTraiteError(autre.etat, autre.traite_canal or autre.canal, autre.traite_le)
    svc_interpreteur.persister_journal(ctx, proposition.commande, svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id)
    svc_deux_canaux.reecrire(proposition.id)  # [US-272 / CA3]
    return ResultatConfirmation(
        carte=carte_de_commande(_commande_par_id(ctx, proposition_id)), texte=svc_decisions.TEXTE_ABANDONNEE,
    )


def _commande_par_id(ctx: TenantContext, proposition_id: int) -> svc_propositions.PropositionConversation:
    proposition = svc_propositions.par_id(proposition_id, ctx.user_id, ctx.potager_id)
    if proposition is None:
        raise svc_gestes_dits.GesteIntrouvableError(proposition_id)
    return proposition


#: [US-289] L'état d'une carte dont la commande, confirmée, n'a pas pu s'exécuter : rien n'est écrit,
#: la proposition est sortie de l'attente (comme dans Telegram) — le jardinier redit sa demande.
ETAT_ECHOUEE = "echouee"


def _confirmer_commande(ctx: TenantContext, proposition: svc_propositions.PropositionConversation,
                        canal: str = CANAL) -> ResultatConfirmation:
    """[US-289] Confirme une commande ou un plan DANS la PWA, dans l'ordre du bot (interpretation.py) :
    sortie atomique de l'attente, journal, puis exécution par le service — jamais par un handler Telegram.

    Lève `GesteDejaTraiteError` (déjà sortie, expirée ou perdue à la course) et
    `NonConfirmableDansLaPwaError` (aucun exécuteur de service : elle se confirme dans Telegram).
    """
    commande = proposition.commande
    if not proposition.en_attente or proposition.expiree():
        if proposition.en_attente:
            svc_propositions.consommer(proposition, svc_propositions.ETAT_PERIMEE, canal=canal)
        raise svc_gestes_dits.GesteDejaTraiteError(
            proposition.etat if not proposition.en_attente else svc_propositions.ETAT_PERIMEE,
            proposition.traite_canal or proposition.canal, proposition.traite_le,
        )
    if not s_execute_dans_la_pwa(commande):
        raise NonConfirmableDansLaPwaError(TEXTE_COMMANDE_TELEGRAM)
    if not svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE, canal=canal):
        autre = _commande_par_id(ctx, proposition.id)
        raise svc_gestes_dits.GesteDejaTraiteError(autre.etat, autre.traite_canal or autre.canal, autre.traite_le)
    svc_interpreteur.persister_journal(ctx, commande, svc_interpreteur.ISSUE_CONFIRMEE, proposition.log_id)
    svc_deux_canaux.reecrire(proposition.id)  # [US-272 / CA3] la carte Telegram ne propose plus rien
    texte, erreur = _jouer_commande(ctx, proposition)
    carte = carte_de_commande(_commande_par_id(ctx, proposition.id))
    if erreur:
        carte.update(etat=ETAT_ECHOUEE, confirmable=False)
    return ResultatConfirmation(carte=carte, texte=texte, erreur=erreur)


def _jouer_commande(ctx: TenantContext, proposition: svc_propositions.PropositionConversation) -> tuple[str, Optional[str]]:
    """[US-289] Exécute par le service, dans le potager de la proposition. Rend (texte, erreur).

    Les exécuteurs ne lèvent pas : un refus (rôle, parcelle introuvable, valeur invalide) revient en
    `erreur`, et ce qui a réussi avant dans un plan reste écrit (US-237 / CA7).
    """
    from database.db import tenant_scope

    commande = proposition.commande
    if isinstance(commande, svc_interpreteur.Plan):
        with tenant_scope(ctx.potager_id):
            resultats = svc_executeurs.executer_plan(commande, ctx, proposition_id=proposition.id)
        echec = next((r.message for r in resultats if r.statut == svc_executeurs.STATUT_ECHOUEE), None)
        return svc_executeurs.compte_rendu(commande, resultats), echec
    with svc_propositions.session_sur(ctx.potager_id) as db:
        if svc_corrections.est_correction(commande):
            texte = svc_corrections.executer(db, ctx, commande)
            return texte, (texte if texte.startswith(("❌", "⚠️")) else None)
        resultat = svc_executeurs.executer_etape(db, ctx, commande, proposition_id=proposition.id)
    if resultat.statut == svc_executeurs.STATUT_REUSSIE:
        return f"✅ {resultat.message}", None
    return f"❌ {resultat.message}", resultat.message
