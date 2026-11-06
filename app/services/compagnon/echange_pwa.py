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
* une **commande** ou un **plan** compris sont rangés en base, visibles et
  confirmables dans Telegram (US-259) — leur exécution passe par les gestionnaires
  de commandes du bot, que la PWA n'a pas : la carte le dit (`confirmable=False`),
  elle peut en revanche être abandonnée ;
* les parcours guidés de Telegram (corriger, déplacer, note, godets) n'ont pas
  d'équivalent à l'écran : la phrase va à l'agent, qui les propose en commande.

La réponse porte toujours un texte et, s'il y en a, les cartes en attente.
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.services import interpreteur_commandes as svc_interpreteur
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import decisions as svc_decisions
from app.services.compagnon import distribution as svc_distribution
from app.services.compagnon import gestes_conversation as svc_gestes_dits
from app.services.compagnon import orchestrateur as svc_orchestrateur
from app.services.compagnon import proactivite as svc_proactivite
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from llm.passerelle import LLMIndisponibleError  # noqa: F401  (remonte à la route : 503)

log = logging.getLogger("potager")

CANAL = svc_propositions.CANAL_PWA

# Ce que la réponse est, pour l'écran.
VERS_REPONSE = "reponse"        # un texte : salutation, précision demandée, refus
VERS_QUESTION = "question"      # la cascade a répondu (savoir, données, raisonnement)
VERS_GESTE = "geste"            # un geste compris : une carte à confirmer
VERS_COMMANDE = "commande"      # une commande ou un plan : une carte, confirmable dans Telegram
VERS_DECISION = "decision"      # « laisse tomber » : la proposition en attente est abandonnée

#: [US-271 / CA1] Les modes du panneau. Normal : l'agent, les gestes, les commandes. Support : le
#: corpus de l'application d'abord, jamais d'écriture (articulation §5.3).
MODE_NORMAL = "normal"
MODE_SUPPORT = "support"
MODES = (MODE_NORMAL, MODE_SUPPORT)

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

    def en_donnees(self) -> dict:
        return {
            "texte": self.texte, "vers": self.vers, "propositions": self.propositions,
            "avertissements": self.avertissements, "routage_log_id": self.routage_log_id,
            "etage": self.etage,
        }


# ═════════════════════════════════════════════════════════════════════════════
# Les cartes
# ═════════════════════════════════════════════════════════════════════════════
def _iso(instant: Optional[datetime]) -> Optional[str]:
    return instant.isoformat() if instant is not None else None


def carte_de_geste(geste: svc_gestes_dits.GesteDit, avertissements: Optional[list[str]] = None) -> dict:
    """La carte d'un geste dit : ses lignes, et le droit de le confirmer ici."""
    return {
        "id": geste.id, "code": geste.code, "nature": svc_propositions.NATURE_GESTE,
        "resume": " ; ".join(svc_gestes_dits.resume(item) for item in geste.items),
        "lignes": [svc_gestes_dits.resume(item) for item in geste.items],
        "items": geste.items, "phrase": geste.texte, "etat": geste.etat, "cree_le": _iso(geste.cree_le),
        "expire_le": _iso(geste.expire_le), "confirmable": geste.en_attente,
        "motif_non_confirmable": None, "avertissements": avertissements or [],
    }


def carte_de_commande(proposition: svc_propositions.PropositionConversation) -> dict:
    """La carte d'une commande ou d'un plan : visible ici, confirmable dans Telegram."""
    commande = proposition.commande
    if isinstance(commande, svc_interpreteur.Plan):
        lignes = [etape.commande_equivalente() for etape in commande.etapes]
    else:
        lignes = [commande.commande_equivalente()]
    return {
        "id": proposition.id, "code": proposition.code, "nature": proposition.nature,
        "resume": " ; ".join(lignes), "lignes": lignes, "items": [], "phrase": None, "etat": proposition.etat,
        "cree_le": _iso(proposition.cree_le), "expire_le": _iso(proposition.expire_le),
        "confirmable": False, "motif_non_confirmable": TEXTE_COMMANDE_TELEGRAM, "avertissements": [],
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
    echanges = svc_conversations.recents(ctx)
    return {
        # [US-271 / CA3] Ce que le compagnon a dit de lui-même, rangé avec la conversation.
        "spontanes": svc_distribution.messages_du_jardinier(ctx),
        "echanges": [
            {"jardinier": e.texte, "compagnon": e.resume,
             "ts": datetime.utcfromtimestamp(e.ts).isoformat() + "Z"}
            for e in echanges
        ],
        "cartes": cartes_en_cours(ctx),
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
    carte = carte_de_commande(proposition)
    return ReponseCompagnon(
        texte=preambule or "Voici ce que je te propose.", vers=VERS_COMMANDE, propositions=[carte],
    )


def _decider(ctx: TenantContext, decision: svc_decisions.Decision) -> ReponseCompagnon:
    """[US-260] « Laisse tomber » : la proposition en attente est abandonnée comme par le bouton.
    « Vas-y » sur une commande : elle se confirme dans Telegram."""
    if decision.action == svc_decisions.ACTION_ABANDONNER:
        proposition = svc_propositions.par_code(decision.code, ctx.user_id)
        if proposition is not None and proposition.en_attente:
            if svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE, canal=CANAL):
                svc_interpreteur.persister_journal(
                    ctx, proposition.commande, svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id,
                )
        return ReponseCompagnon(texte=svc_decisions.TEXTE_ABANDONNEE, vers=VERS_DECISION)
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


def confirmer(ctx: TenantContext, proposition_id: int) -> ResultatConfirmation:
    """[US-270 / CA2] Confirme une carte : sortie atomique de l'attente, puis écriture (règles d'US-259).

    Lève `GesteIntrouvableError` (404), `GesteDejaTraiteError` (409 : déjà confirmée, abandonnée,
    remplacée ou périmée — la seconde confirmation n'écrit rien) ou `NonConfirmableDansLaPwaError`.
    """
    if not _est_un_geste_dit(ctx, proposition_id):
        _lever_si_commande(ctx, proposition_id)
    geste, resultat = svc_gestes_dits.confirmer(ctx, proposition_id)
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


def abandonner(ctx: TenantContext, proposition_id: int) -> ResultatConfirmation:
    """[US-270 / CA2] Laisse tomber une carte (geste ou commande) : sortie atomique, rien n'est écrit."""
    if _est_un_geste_dit(ctx, proposition_id):
        geste = svc_gestes_dits.abandonner(ctx, proposition_id)
        return ResultatConfirmation(carte=carte_de_geste(geste), texte=svc_decisions.TEXTE_ABANDONNEE)
    proposition = _commande_par_id(ctx, proposition_id)
    if not proposition.en_attente or proposition.expiree():
        raise svc_gestes_dits.GesteDejaTraiteError(
            proposition.etat if proposition.en_attente is False else svc_propositions.ETAT_PERIMEE,
            proposition.traite_canal or proposition.canal, proposition.traite_le,
        )
    if not svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE, canal=CANAL):
        autre = _commande_par_id(ctx, proposition_id)
        raise svc_gestes_dits.GesteDejaTraiteError(autre.etat, autre.traite_canal or autre.canal, autre.traite_le)
    svc_interpreteur.persister_journal(ctx, proposition.commande, svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id)
    return ResultatConfirmation(
        carte=carte_de_commande(_commande_par_id(ctx, proposition_id)), texte=svc_decisions.TEXTE_ABANDONNEE,
    )


def _commande_par_id(ctx: TenantContext, proposition_id: int) -> svc_propositions.PropositionConversation:
    proposition = svc_propositions.par_id(proposition_id, ctx.user_id, ctx.potager_id)
    if proposition is None:
        raise svc_gestes_dits.GesteIntrouvableError(proposition_id)
    return proposition


def _lever_si_commande(ctx: TenantContext, proposition_id: int) -> None:
    """Une commande ou un plan existe : il se confirme dans Telegram ; sinon, rien de ce numéro."""
    proposition = _commande_par_id(ctx, proposition_id)
    if not proposition.en_attente:
        raise svc_gestes_dits.GesteDejaTraiteError(
            proposition.etat, proposition.traite_canal or proposition.canal, proposition.traite_le)
    raise NonConfirmableDansLaPwaError(TEXTE_COMMANDE_TELEGRAM)
