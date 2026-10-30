"""Commandes dictées par une phrase [US-172] : proposition, complétion, exécution.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from typing import Optional
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CommandHandler, ContextTypes
from database.db import SessionLocal, current_potager_id
from utils.parcelles import normalize_parcelle_name, find_doublon, resolve_parcelle
from app.services.context import TenantContext, current_context, set_current_context
from app.services import menu_commandes as svc_menu_commandes
from app.services import interpreteur_commandes as svc_interpreteur
from app.services import anticipation_commande as svc_anticipation
from app.services.agent import contexte_court as svc_contexte_court
from app.services.compagnon import actions_menees as svc_actions_menees
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import corrections as svc_corrections
from app.services.compagnon import decisions as svc_decisions
from app.services.compagnon import propositions as svc_propositions
from app.services.compagnon.propositions import PropositionConversation
from app.services import liaison_telegram as svc_liaison_telegram
from app.services import potager_actif as svc_potager_actif
from .noyau import _md, log
from .commandes_profil import accueil_premier_contact
from .liaison import CLE_POTAGER_IMPOSE


# ══════════════════════════════════════════════════════════════════════════════
# [US-172] Piloter le bot par une phrase — proposition, complétion, exécution
# ══════════════════════════════════════════════════════════════════════════════
# La reconnaissance vit dans `app/services/interpreteur_commandes.py` ; ce qui
# suit est le seul code Telegram qu'elle exige : proposer, compléter, exécuter.
#
# Point de conception central (CA9) : l'exécution ne réimplémente RIEN. Elle
# retrouve le handler réellement enregistré par introspection de
# `ctx.application`, pose les arguments dans `ctx.args` et l'appelle. Une
# commande dictée traverse donc exactement le même chemin qu'une commande
# tapée — même service, mêmes contrôles de rôle, mêmes messages, mêmes claviers
# contextuels, et le même garde de liaison (CA14), puisque c'est le handler
# ENVELOPPÉ par `_avec_garde_liaison` que l'introspection retrouve.
#
# Aucune table de correspondance nom → fonction n'est tenue ici : elle
# divergerait au premier renommage, et la divergence se paierait en commande
# dictée qui n'exécute rien.
#
# [US-259] La proposition en attente ne vit plus en mémoire du bot : elle est en
# base (`app.services.compagnon.propositions`), commune aux canaux, et survit à
# un redémarrage (CA8). Chaque étape la relit par son code, la met à jour sous ce
# code, et la fait sortir de l'attente de façon atomique (CA3).
#
# [US-260] Le jardinier peut aussi répondre par une phrase (« vas-y », « laisse tomber ») :
# l'agent appelle `confirmer_proposition` / `abandonner_proposition`, le code valide
# l'identifiant, et `_interp_decider` fait ce que le bouton ferait — après avoir relu la
# base. Une action destructrice ne se confirme qu'au bouton.
#
# [US-234] Une proposition est liée à ses boutons par son code
# (`interp:ok:<code>`) et au potager où elle a été faite. Un bouton sous un
# ANCIEN message ne valide jamais la proposition en cours. [US-259 / CA4] Elle
# s'exécute dans SON potager, même si le jardinier a changé de potager actif
# entre-temps : la carte le nomme quand il en a plusieurs.

#: [US-259 / CA5] Une proposition de conversation vit 30 minutes : elle porte des
#: arguments lus dans une phrase, la rejouer bien plus tard n'aurait aucun sens.
_INTERP_TIMEOUT = int(svc_propositions.DUREE_CONVERSATION.total_seconds())  # secondes


_INTERP_MODE_COMPLETION = "interp_completion"

_MSG_DEMANDE_EXPIREE = "⏱ Demande expirée, rien n'a été fait."
_MSG_POTAGER_INCONNU = (
    "⚠️ Impossible de vérifier le potager actif, rien n'a été fait. Redites la demande."
)
_MSG_POTAGER_PERDU = (
    "⚠️ Vous n'avez plus accès au potager de cette demande, rien n'a été fait."
)


def _decoder_callback(data: str) -> tuple[str, Optional[str], Optional[str]]:
    """[US-234 CA1] `interp:<action>[:<rang>]:<id>` → (action, rang, identifiant).

    `cand`, `val` et `prec` [US-250] portent un rang entre l'action et l'identifiant.
    Un bouton sans identifiant — un message envoyé avant US-234 — donne
    `identifiant=None` et sera refusé comme périmé : on ne devine pas à quelle
    proposition il répond.
    """
    morceaux = (data or "").split(":")
    action = morceaux[1] if len(morceaux) > 1 else ""
    if action in ("cand", "val", "prec"):
        rang = morceaux[2] if len(morceaux) > 2 else None
        identifiant = morceaux[3] if len(morceaux) > 3 else None
    else:
        rang = None
        identifiant = morceaux[2] if len(morceaux) > 2 else None
    return action, rang, identifiant or None


def _jardinier_au_clic(update: Update) -> Optional[int]:
    """[US-234 CA3] Le compte relié au chat qui clique, ou None.

    `current_context()` ne convient pas ici : un callback ne passe pas par le
    garde de liaison, il lit donc le contexte par défaut.
    """
    db = None
    try:
        db = SessionLocal()
        return svc_liaison_telegram.resoudre_user_id_pour_chat(db, update.effective_chat.id)
    except Exception:  # noqa: BLE001 — impossible de vérifier : le doute vaut refus
        log.exception("[US-234 CA3] Jardinier illisible au moment du clic")
        return None
    finally:
        if db is not None:
            db.close()


def _contexte_sur(user_id: int, potager_id: int) -> Optional[TenantContext]:
    """[US-259 / CA4] Le contexte du jardinier sur le potager DE LA PROPOSITION, ou None
    s'il n'en est plus membre (ou si on ne peut pas le vérifier)."""
    db = None
    try:
        db = SessionLocal()
        return svc_potager_actif.contexte_sur_potager(db, user_id, potager_id)
    except Exception:  # noqa: BLE001 — impossible de vérifier : le doute vaut refus
        log.exception("[US-259 / CA4] Rôle illisible sur le potager %s", potager_id)
        return None
    finally:
        if db is not None:
            db.close()


def _armer(contexte: TenantContext) -> None:
    """[US-259 / CA4] Le reste du traitement du clic se fait dans ce potager-là."""
    set_current_context(contexte)
    current_potager_id.set(contexte.potager_id)


class _UpdateCommande:
    """Vue d'un `Update` qui expose toujours `.message`.

    Les handlers de commande écrivent via `update.message.reply_text` : appelés
    depuis un callback de bouton, où `update.message` vaut None, ils
    échoueraient. Cette vue substitue le message porteur du clavier et délègue
    tout le reste à l'Update d'origine (`effective_user`, `effective_message`,
    `callback_query`…), pour que le handler ne voie aucune différence.
    """

    def __init__(self, update: Update, message=None):
        self._update = update
        self.message = message or update.message or (
            update.callback_query.message if update.callback_query else None
        )

    def __getattr__(self, nom):
        return getattr(self._update, nom)


class _MessageEcoute:
    """[US-261] Délègue au vrai message et retient ce qui a été répondu.

    Un handler de commande répond au jardinier sans rien rendre : son échec ne se lit que
    dans ses réponses (`actions_menees.statut_des_reponses`).
    """

    def __init__(self, message):
        self._message = message
        self.reponses: list[str] = []

    async def reply_text(self, texte, *args, **kwargs):
        self.reponses.append(str(texte or ""))
        return await self._message.reply_text(texte, *args, **kwargs)

    def __getattr__(self, nom):
        return getattr(self._message, nom)


def _handler_de_commande(ctx: ContextTypes.DEFAULT_TYPE, nom: str):
    """Le handler réellement enregistré pour `/nom`, par introspection (CA6, CA9).

    Même procédé que `_noms_commandes_enregistrees` pour le menu d'US-171 : on
    lit les `CommandHandler` de l'Application plutôt qu'une liste recopiée. Ce
    qui est retourné est le callback ENVELOPPÉ, garde de liaison compris.
    """
    application = getattr(ctx, "application", None)
    for groupe in (getattr(application, "handlers", None) or {}).values():
        for handler in groupe:
            if isinstance(handler, CommandHandler) and nom in handler.commands:
                return handler.callback
    return None


def _resoudre_noms_parcelle(commande):
    """[CA12] Une commande ne s'exécute jamais sur un nom approché.

    `resolve_parcelle` rapproche « planche nord-est » de « Planche Nord »
    (Levenshtein ≤ 2, puis sous-chaîne). C'est le bon comportement pour
    rattacher un geste à une parcelle — et le mauvais pour en supprimer une :
    une suppression exécutée sur la mauvaise parcelle coûte davantage que cent
    phrases non comprises.

    L'exigence est donc l'égalité EXACTE après la normalisation habituelle du
    projet (casse, accents, espaces, tirets — `normalize_parcelle_name`, jamais
    une seconde règle). À défaut, le nom voisin est proposé au jardinier, et la
    valeur dictée est retirée de la commande pour qu'aucun chemin ne puisse
    l'exécuter telle quelle.
    """
    a_verifier = [
        argument for argument in commande.forme.arguments
        if argument.type == svc_menu_commandes.TYPE_PARCELLE
        and commande.valeurs.get(argument.nom)
    ]
    if not a_verifier:
        return commande

    db = SessionLocal()
    try:
        potager_id = current_context().potager_id
        for argument in a_verifier:
            nom_dicte = commande.valeurs[argument.nom]
            exact, _ = find_doublon(db, normalize_parcelle_name(nom_dicte), potager_id=potager_id)
            if exact is not None and exact.actif:
                continue
            voisine = resolve_parcelle(db, nom_dicte, potager_id=potager_id)
            candidats = (voisine.nom,) if voisine is not None else ()
            log.info(
                "[US-172 CA12] Parcelle %r inexacte → %s",
                nom_dicte,
                f"candidat proposé : {voisine.nom!r}" if voisine else "aucun voisin",
            )
            return commande.avec_candidats(argument.nom, candidats)
        return commande
    finally:
        db.close()


def _message_de(update: Update):
    return update.message or (update.callback_query.message if update.callback_query else None)


def _abandonner_precedente(tenant: TenantContext) -> Optional[PropositionConversation]:
    """[US-234 CA7] Une nouvelle demande écrase la précédente : celle-ci n'aura
    jamais de suite, son journal le dit au lieu de rester « proposée ».
    Rend la proposition remplacée, ou None. [US-259] Son passage à `remplacee`
    est fait par `propositions.proposer`, dans la même transaction que la nouvelle."""
    ancienne = svc_propositions.en_attente(tenant.user_id, tenant.potager_id)
    if ancienne is not None:
        svc_interpreteur.persister_journal(
            tenant, ancienne.commande, svc_interpreteur.ISSUE_ABANDONNEE, ancienne.log_id,
        )
        svc_interpreteur.journaliser(ancienne.commande, svc_interpreteur.ISSUE_ABANDONNEE)
        log.info("[US-234] Proposition %s remplacée par une nouvelle demande", ancienne.code)
    return ancienne


def _ecartes_apres(ancienne: Optional[PropositionConversation], nouvelle) -> tuple[str, ...]:
    """[US-238 / CA2] Les noms voisins que le jardinier a laissés de côté.

    Quand une nouvelle proposition de la MÊME commande remplace une proposition
    qui offrait des noms voisins, ces noms n'ont pas été retenus : « non,
    l'autre » ne doit pas les reproposer. Une autre commande repart de zéro.
    """
    if ancienne is None:
        return ()
    precedente = ancienne.commande
    if (
        not isinstance(precedente, svc_interpreteur.CommandeInterpretee)
        or not isinstance(nouvelle, svc_interpreteur.CommandeInterpretee)
        or precedente.forme.cle != nouvelle.forme.cle
        or not precedente.candidats
    ):
        return ()
    return tuple(ancienne.ecartes) + tuple(precedente.candidats)


def _resume_de_proposition(commande) -> str:
    """La proposition en une ligne, telle que l'agent la lit."""
    if isinstance(commande, svc_interpreteur.Plan):
        return " ; ".join(etape.commande_equivalente() for etape in commande.etapes)
    return commande.commande_equivalente()


def _ailleurs_de(tenant: TenantContext) -> tuple[str, ...]:
    """[US-260 / CA4] Les propositions qui attendent ce jardinier dans un AUTRE potager, nommées."""
    try:
        autres = svc_propositions.en_attente_ailleurs(tenant.user_id, tenant.potager_id)
    except Exception:  # noqa: BLE001 — sans elles, « oui » ne verra qu'une proposition : on ne les ignore pas
        log.exception("[US-260 / CA4] Propositions des autres potagers illisibles")
        return ()
    return tuple(
        f"dans {svc_propositions.potager_a_nommer(p.user_id, p.potager_id) or 'un autre potager'} : "
        f"{_resume_de_proposition(p.commande)}"
        for p in autres
    )


def contexte_court_de(update: Update):
    """[US-238, US-259] Le contexte de la conversation du jardinier qui écrit, ou None.

    [US-260] Il porte l'identifiant de la proposition en attente (que les outils de décision
    reprennent), la dernière proposition traitée quand aucune n'attend, et les propositions
    qui attendent dans un autre potager.

    La proposition en attente est celle de CE jardinier dans CE potager, lue en
    base ; le service la refuse si elle est expirée (CA5). Les 10 derniers
    échanges de la conversation l'accompagnent, même sans proposition. None :
    ni proposition ni conversation en cours, la phrase est une demande nouvelle.
    Une mémoire illisible ne bloque jamais la phrase : elle passe sans contexte.
    """
    tenant = current_context()
    try:
        proposition = svc_propositions.en_attente(tenant.user_id, tenant.potager_id)
    except Exception:  # noqa: BLE001
        log.exception("[US-259] Proposition en attente illisible — phrase traitée sans elle")
        proposition = None
    echanges = svc_conversations.recents(tenant)
    ailleurs = _ailleurs_de(tenant)
    if proposition is None:
        traitee = None
        try:
            derniere = svc_propositions.derniere_traitee(tenant.user_id, tenant.potager_id)
        except Exception:  # noqa: BLE001
            log.exception("[US-260 / CA5] Dernière proposition traitée illisible")
            derniere = None
        if derniere is not None:
            traitee = svc_contexte_court.Traitee(
                code=derniere.code, etat=derniere.etat, resume=_resume_de_proposition(derniere.commande),
                traite_le=derniere.traite_le, canal=derniere.traite_canal or derniere.canal,
            )
        return svc_contexte_court.construire(tenant, echanges=echanges, ailleurs=ailleurs, traitee=traitee)
    return svc_contexte_court.construire(
        tenant, proposition.commande, proposition.ts, proposition.potager_id,
        ecartes=proposition.ecartes, delai=_INTERP_TIMEOUT, echanges=echanges,
        code=proposition.code, ailleurs=ailleurs,
    )


def _noter_echange(resultat) -> None:
    """[US-259 / CA1] Chaque phrase interprétée devient un échange de la conversation,
    avec la proposition qu'elle a laissée en attente, s'il y en a une."""
    try:
        echange = svc_contexte_court.echange_de(resultat)
        if echange is None:
            return
        tenant = current_context()
        propose = isinstance(resultat, (svc_interpreteur.CommandeInterpretee, svc_interpreteur.Plan)) or (
            isinstance(resultat, svc_interpreteur.ReponseAgent) and resultat.proposition is not None
        )
        proposition = svc_propositions.en_attente(tenant.user_id, tenant.potager_id) if propose else None
        svc_conversations.noter(
            tenant, echange.texte, echange.resume, canal=svc_propositions.CANAL_TELEGRAM,
            outils=tuple(getattr(resultat, "outils", ()) or ()),
            proposition_id=proposition.id if proposition is not None else None,
        )
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-259 / CA1] Échange non retenu")


def _entete_potager(proposition: PropositionConversation) -> str:
    """[US-259 / CA4] « 🏡 Potager du bas » au-dessus de la carte, quand le jardinier
    a plusieurs potagers : c'est là que la proposition s'exécutera."""
    nom = svc_propositions.potager_a_nommer(proposition.user_id, proposition.potager_id)
    return f"🏡 _{_md(nom)}_\n" if nom else ""


async def _interp_proposer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, commande, msg=None,
                           preambule: str = "") -> None:
    """Point d'entrée unique d'une commande interprétée : rien ne s'exécute ici.

    Quatre issues possibles, dans cet ordre — le doute d'abord, l'incomplétude
    ensuite, la validation en dernier :
      * un nom de parcelle inexact → les voisins sont proposés (CA12) ;
      * un mot de la phrase que la reconnaissance n'a pas utilisé → il est
        demandé, jamais jeté en silence [US-250] ;
      * un argument obligatoire absent → il est demandé (CA13) ;
      * sinon → récapitulatif et confirmation explicite (CA10, CA11).

    [US-257] `preambule` : le texte rédigé par l'agent, affiché une fois, au-dessus
    de ce que le code montre. Ce qui s'exécute reste le récapitulatif, jamais le texte.
    [US-259] La proposition est rangée en base avant d'être montrée.
    """
    commande = _resoudre_noms_parcelle(commande)
    tenant = current_context()
    ancienne = _abandonner_precedente(tenant)

    if commande.precision is not None:
        # [US-250 / CA6] La question a sa propre ligne de journal, « precision », qui n'est
        # jamais réécrite : la proposition n'en porte aucune tant que le choix n'est pas fait.
        svc_interpreteur.persister_journal(tenant, commande, svc_interpreteur.ISSUE_PRECISION)
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_PRECISION)
        log_id = None
    else:
        log_id = svc_interpreteur.persister_journal(
            tenant, commande, svc_interpreteur.ISSUE_PROPOSEE
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_PROPOSEE)
    proposition = svc_propositions.proposer(
        tenant, commande, log_id=log_id, ecartes=_ecartes_apres(ancienne, commande),
    )
    await _interp_etape_suivante(update, ctx, proposition, msg=msg, preambule=preambule)


async def _interp_etape_suivante(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                                 proposition: PropositionConversation, msg=None,
                                 preambule: str = "") -> None:
    """Affiche l'étape courante de la proposition en attente."""
    commande = proposition.commande
    message = _message_de(update)
    # [US-234 CA1] Repris par tous les boutons de cette étape.
    ident = proposition.code

    async def _repondre(texte: str, boutons) -> None:
        clavier = InlineKeyboardMarkup(boutons) if boutons else None
        if preambule:
            texte = f"{texte_de_l_agent(preambule)}\n\n{texte}"
        if msg is not None:
            await msg.edit_text(texte, parse_mode="Markdown", reply_markup=clavier)
        else:
            await message.reply_text(texte, parse_mode="Markdown", reply_markup=clavier)

    def _attendre(nom: Optional[str]) -> None:
        """L'argument attendu est gardé avec la proposition : la réponse tapée le retrouve."""
        nonlocal proposition
        if proposition.attend != nom:
            proposition = svc_propositions.mettre_a_jour(
                proposition, commande=commande, attend=nom,
            ) or proposition

    # ── [CA12] Le nom dicté n'existe pas exactement ──────────────────────────
    if commande.candidats or commande.argument_candidat is not None:
        _attendre(commande.argument_candidat)
        boutons = [
            [InlineKeyboardButton(f"📍 {nom}", callback_data=f"interp:cand:{rang}:{ident}")]
            for rang, nom in enumerate(commande.candidats)
        ]
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}")])
        if len(commande.candidats) > 1:
            # [US-278 / CA5] Aucun nom voisin : les parcelles du potager sont offertes au choix.
            texte = "❓ Quelle parcelle ?"
        elif commande.candidats:
            texte = (
                f"❓ Aucune parcelle ne porte exactement ce nom.\n"
                f"Vouliez-vous dire *{_md(commande.candidats[0].upper())}* ?"
            )
        else:
            texte = "❓ Aucune parcelle ne porte ce nom, ni un nom voisin."
        await _repondre(texte, boutons)
        return

    # ── [US-250] Un mot de la phrase n'a pas été utilisé : il se tranche ─────
    # La proposition n'est jamais présentée comme entièrement comprise. Un bouton
    # par valeur connue (US-251 / CA4 : les seules que le mot pourrait désigner),
    # « Sans précision », et « Annuler » : rien n'est écrit avant la confirmation.
    if commande.precision is not None:
        precision = commande.precision
        _attendre(None)
        boutons = [
            [InlineKeyboardButton(valeur[:1].upper() + valeur[1:],
                                  callback_data=f"interp:prec:{rang}:{ident}")]
            for rang, valeur in enumerate(precision.options)
        ]
        if precision.invite:
            # [US-253 / CA6] Une suite proposée se laisse : « Plus tard » ne demande rien.
            boutons.append([InlineKeyboardButton("Plus tard", callback_data=f"interp:sans:{ident}")])
            await _repondre(f"💡 {precision.question()}", boutons)
            return
        sans = "Sans précision" if precision.options else f"Continuer sans « {precision.mot[:24]} »"
        boutons.append([InlineKeyboardButton(sans, callback_data=f"interp:sans:{ident}")])
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}")])
        await _repondre(f"❓ {precision.question()}", boutons)
        return

    # ── [CA13] Un argument manquant se complète, il n'échoue pas ─────────────
    if commande.manquants:
        argument = commande.manquants[0]
        _attendre(argument.nom)
        ctx.user_data['mode'] = _INTERP_MODE_COMPLETION
        if argument.vocabulaire:
            # Une valeur de vocabulaire fermé se choisit, elle ne se devine
            # jamais à partir d'un synonyme approchant.
            boutons = [
                [InlineKeyboardButton(valeur, callback_data=f"interp:val:{rang}:{ident}")]
                for rang, valeur in enumerate(argument.vocabulaire)
            ]
        else:
            boutons = []
        boutons.append([InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}")])
        await _repondre(f"*{commande.forme.libelle}*\n\n{argument.question}", boutons)
        return

    # ── [CA10] Une commande de CONSULTATION s'exécute directement ────────────
    # Elle n'écrit rien : lui demander « voulez-vous vraiment afficher le
    # plan ? » doublerait chaque lecture sans rien protéger. La moitié
    # PÉDAGOGIQUE du CA10 est en revanche servie dans les deux cas — la commande
    # équivalente est rappelée, et c'est ainsi que le jardinier apprend la
    # syntaxe sans avoir eu à l'apprendre.
    if not commande.forme.confirmation:
        ctx.user_data['mode'] = None
        if not svc_propositions.consommer(proposition, svc_propositions.ETAT_CONFIRMEE):
            return
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_CONFIRMEE, proposition.log_id,
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
        await _repondre(f"↪️ `{commande.commande_equivalente()}`", None)
        await _interp_executer(update, ctx, commande)
        return

    # ── [CA10, CA11] Rien de ce qui ÉCRIT ne s'exécute à l'aveugle ───────────
    _attendre(None)
    ctx.user_data['mode'] = None
    entete = (
        "🗑 " if commande.forme.destructrice
        else "✏️ " if svc_corrections.est_correction(commande) else "➕ "
    )
    boutons = [[
        InlineKeyboardButton("✅ Confirmer", callback_data=f"interp:ok:{ident}"),
        InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}"),
    ]]
    # [US-253 / CA1] Ce qui dépend de ce qu'on retire, lu dans les données du potager.
    avertissements = _anticiper(commande)
    await _repondre(
        _entete_potager(proposition) + entete + svc_interpreteur.recapitulatif(commande)
        + ("\n\n" + "\n".join(avertissements) if avertissements else ""),
        boutons,
    )


def _anticiper(commande) -> list[str]:
    """[US-253 / CA1] Les avertissements de la commande, lus en base (jamais bloquants)."""
    db = SessionLocal()
    try:
        return svc_anticipation.avertissements(db, current_context(), commande)
    finally:
        db.close()


async def _suggerer_suite(update: Update, ctx: ContextTypes.DEFAULT_TYPE, commande) -> None:
    """[US-253 / CA2, CA3, CA4, CA6] Après une commande exécutée, au plus UNE suite est proposée.

    Elle est rangée comme n'importe quelle proposition : ses boutons ne font que poser la valeur,
    l'écriture attend la confirmation habituelle, et la phrase suivante la remplace (CA6).
    """
    db = SessionLocal()
    try:
        suite = svc_anticipation.suite_suggeree(db, current_context(), commande)
    finally:
        db.close()
    if suite is not None:
        await _interp_proposer(update, ctx, suite)


async def _interp_executer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, commande,
                           potager_id: Optional[int] = None,
                           proposition_id: Optional[int] = None) -> None:
    """[CA9, CA14] Exécute la commande via le handler réellement enregistré.

    [US-259 / CA4] `potager_id` : le potager de la proposition, que le garde de
    liaison armera pour ce handler à la place du potager actif.
    [US-261 / CA1] Une commande qui écrit est retenue parmi les actions menées, avec ses
    valeurs avant / après : c'est ce chemin d'exécution qui l'écrit, jamais le modèle.
    [US-262 / CA2] Une correction n'a pas de handler : le service de la nature concernée
    (`evenements.corriger_evenement` / `supprimer_evenement`) l'exécute, et retient l'action.
    """
    message = _message_de(update)
    if svc_corrections.est_correction(commande):
        db = SessionLocal()
        try:
            compte_rendu = svc_corrections.executer(db, current_context(), commande)
        finally:
            db.close()
        if message is not None:
            await message.reply_text(compte_rendu)
        return
    handler = _handler_de_commande(ctx, commande.commande)
    if handler is None:
        log.error("[US-172] /%s introuvable parmi les CommandHandler", commande.commande)
        await message.reply_text(
            f"❌ La commande /{commande.commande} n'est pas disponible.",
        )
        return
    log.info(
        "[US-172] Exécution de la commande interprétée : %s%s",
        commande.commande_equivalente(),
        f" (potager {potager_id})" if potager_id is not None else "",
    )
    ctx.args = list(commande.args)
    donnees = ctx.user_data if isinstance(getattr(ctx, "user_data", None), dict) else None
    if potager_id is not None and donnees is not None:
        donnees[CLE_POTAGER_IMPOSE] = potager_id
    tenant = current_context()
    avant = svc_actions_menees.instantane_commande(tenant, commande, apres=False) if commande.forme.confirmation else None
    ecoute = _MessageEcoute(message) if message is not None else None
    try:
        await handler(_UpdateCommande(update, ecoute), ctx)
    finally:
        if donnees is not None:
            donnees.pop(CLE_POTAGER_IMPOSE, None)
    svc_actions_menees.retenir_commande(
        tenant, commande, ecoute.reponses if ecoute is not None else [],
        avant=avant, proposition_id=proposition_id,
    )
    # [US-264 / CA4] Une parcelle supprimée : les gestes qui restent sans planche, comptés par le code.
    from app.services.agent import compte_rendu as svc_compte_rendu

    await _proposer_la_suite(
        update, ctx, svc_compte_rendu.suggerer(svc_compte_rendu.faits_de_commande(commande), tenant),
    )


async def _interp_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — confirmation, refus, choix d'une valeur ou d'un nom voisin."""
    query = update.callback_query
    await query.answer()
    action, rang, identifiant = _decoder_callback(query.data)

    # ── [US-234 CA2] Un bouton ne parle que de SA proposition ────────────────
    # Ni confirmer, ni annuler, ni choisir : un bouton sous un ancien message
    # n'agit jamais sur la proposition en cours, qui reste telle quelle. La
    # proposition qu'il visait a été marquée `remplacee` le jour où une autre
    # a pris sa place (CA7). [US-259 / CA8] Lue en base : un redémarrage du bot
    # entre la proposition et le clic ne change rien.
    user_id = _jardinier_au_clic(update) if identifiant is not None else None
    if identifiant is not None and user_id is None:
        await query.edit_message_text(_MSG_POTAGER_INCONNU, reply_markup=None)
        return
    proposition = svc_propositions.par_code(identifiant, user_id)
    if proposition is None or not proposition.en_attente:
        log.info(
            "[US-234 CA2] Bouton %r : proposition %s → rien d'exécuté",
            query.data, proposition.etat if proposition is not None else "inconnue",
        )
        await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
        return

    commande = proposition.commande
    if action == "non":
        ctx.user_data['mode'] = None
        if not svc_propositions.consommer(
            proposition, svc_propositions.ETAT_ABANDONNEE, canal=svc_propositions.CANAL_TELEGRAM,
        ):
            await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
            return
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_REFUSEE, proposition.log_id,
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_REFUSEE)
        await query.edit_message_text("❌ Annulé — rien n'a été fait.", reply_markup=None)
        return

    # ── [US-259 / CA5] 30 minutes, pas une de plus ───────────────────────────
    if proposition.expiree():
        ctx.user_data['mode'] = None
        if svc_propositions.consommer(proposition, svc_propositions.ETAT_PERIMEE):
            svc_interpreteur.persister_journal(
                current_context(), commande,
                svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id,
            )
        await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
        return

    # ── [US-259 / CA4] La commande s'exécute dans le potager où elle a été dite ─
    # Quel que soit le potager actif au moment du clic : après un `/potager`,
    # « supprime la parcelle nord » vise toujours la parcelle du potager où elle
    # a été dite, et le rôle se relit sur CE potager. Placé avant tout choix (nom
    # voisin, valeur), pour qu'une proposition hors d'accès ne se construise pas.
    contexte = _contexte_sur(user_id, proposition.potager_id)
    if contexte is None:
        log.info(
            "[US-259 / CA4] Potager %s de la proposition %s hors d'accès pour user_id=%s → rien d'exécuté",
            proposition.potager_id, proposition.code, user_id,
        )
        ctx.user_data['mode'] = None
        if svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE):
            svc_interpreteur.persister_journal(
                current_context(), commande,
                svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id,
            )
            svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_ABANDONNEE)
        await query.edit_message_text(_MSG_POTAGER_PERDU, reply_markup=None)
        return
    _armer(contexte)

    # ── [US-237] Un plan n'a qu'une paire de boutons : tout confirmer, annuler ─
    if isinstance(commande, svc_interpreteur.Plan):
        if action != "ok":
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        ctx.user_data['mode'] = None
        if not svc_propositions.consommer(
            proposition, svc_propositions.ETAT_CONFIRMEE, canal=svc_propositions.CANAL_TELEGRAM,
        ):
            await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
            return
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_CONFIRMEE, proposition.log_id,
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
        await _plan_executer(update, commande, query, contexte, proposition_id=proposition.id, ctx=ctx)
        return

    # ── Choix d'un nom voisin proposé (CA12) ─────────────────────────────────
    if action == "cand":
        try:
            choisi = commande.candidats[int(rang)]
        except (TypeError, ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        suite = svc_propositions.mettre_a_jour(
            proposition, commande=commande.avec(**{commande.argument_candidat: choisi}),
            attend=proposition.attend,
        )
        if suite is None:
            await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
            return
        await _interp_etape_suivante(update, ctx, suite, msg=query.message)
        return

    # ── [US-250 / CA2, CA3] Le mot non compris est tranché par un bouton ─────
    # Une valeur choisie, ou « sans précision » : la proposition habituelle suit,
    # avec récapitulatif et confirmation. Elle repart d'une ligne de journal neuve :
    # celle de la question reste « precision », pour que le cas se compte.
    if action in ("prec", "sans"):
        if commande.precision is None:
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        if action == "sans" and commande.precision.invite:
            # [US-253 / CA6] « Plus tard » : la suite est laissée, rien n'est écrit ni demandé.
            svc_propositions.consommer(proposition, svc_propositions.ETAT_ABANDONNEE)
            await query.edit_message_text("👌 C'est noté, on laisse comme ça.", reply_markup=None)
            return
        try:
            suite_commande = (
                commande.avec_choix(int(rang)) if action == "prec" else commande.sans_precision()
            )
        except (TypeError, ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        log_id = svc_interpreteur.persister_journal(
            current_context(), suite_commande, svc_interpreteur.ISSUE_PROPOSEE,
        )
        svc_interpreteur.journaliser(suite_commande, svc_interpreteur.ISSUE_PROPOSEE)
        suite = svc_propositions.mettre_a_jour(
            proposition, commande=suite_commande, attend=None, log_id=log_id,
        )
        if suite is None:
            await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
            return
        await _interp_etape_suivante(update, ctx, suite, msg=query.message)
        return

    # ── Choix d'une valeur de vocabulaire fermé (CA13) ───────────────────────
    if action == "val":
        argument = next(
            (a for a in commande.manquants if a.nom == proposition.attend), None
        )
        if argument is None:
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        try:
            valeur = argument.vocabulaire[int(rang)]
        except (TypeError, ValueError, IndexError):
            await query.edit_message_text("❌ Données invalides.", reply_markup=None)
            return
        suite = svc_propositions.mettre_a_jour(
            proposition, commande=commande.avec(**{argument.nom: valeur}), attend=proposition.attend,
        )
        if suite is None:
            await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
            return
        await _interp_etape_suivante(update, ctx, suite, msg=query.message)
        return

    # ── Confirmation (CA10) ──────────────────────────────────────────────────
    # [US-234 CA4, CA5 ; US-259 CA3] La proposition sort de l'attente AVANT
    # l'exécution, et de façon atomique : un double appui — ou un clic dans la
    # PWA au même instant — ne la trouve plus en attente. Ce qui s'exécute est
    # `commande`, celle qui a été affichée — la phrase n'est jamais réinterprétée.
    if action == "ok":
        ctx.user_data['mode'] = None
        if not svc_propositions.consommer(
            proposition, svc_propositions.ETAT_CONFIRMEE, canal=svc_propositions.CANAL_TELEGRAM,
        ):
            await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
            return
        svc_interpreteur.persister_journal(
            current_context(), commande,
            svc_interpreteur.ISSUE_CONFIRMEE, proposition.log_id,
        )
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
        await query.edit_message_text(
            f"⏳ `{commande.commande_equivalente()}`", parse_mode="Markdown", reply_markup=None
        )
        await _interp_executer(
            update, ctx, commande, potager_id=proposition.potager_id, proposition_id=proposition.id,
        )
        await _suggerer_suite(update, ctx, commande)


async def _interp_decider(update: Update, ctx: ContextTypes.DEFAULT_TYPE, decision, msg=None) -> None:
    """[US-260] Le jardinier répond à une proposition par une phrase : « vas-y », « laisse tomber ».

    Même chemin que le bouton, mêmes garde-fous, et la base fait foi : la proposition est relue
    par son code, sous le jardinier de CE message — pas telle que l'agent l'avait lue. Ce qui
    s'exécute est la commande rangée avec la proposition, jamais la phrase.
    """
    tenant = current_context()
    message = _message_de(update)

    async def _dire(texte: str, markdown: bool = False) -> None:
        if msg is not None:
            await msg.edit_text(texte, parse_mode="Markdown" if markdown else None)
        else:
            await message.reply_text(texte, parse_mode="Markdown" if markdown else None)

    proposition = svc_propositions.par_code(decision.code, tenant.user_id)
    if proposition is None or proposition.potager_id != tenant.potager_id:
        log.info("[US-260 / CA1] Décision %s sur %r : proposition inconnue de ce jardinier → rien d'exécuté",
                 decision.action, decision.code)
        await _dire(_MSG_DEMANDE_EXPIREE)
        return

    async def _deja_traitee() -> None:
        # [CA5] Déjà confirmée (au bouton, dans la PWA) ou abandonnée : où et quand, sans rien refaire.
        relue = svc_propositions.par_code(decision.code, tenant.user_id) or proposition
        log.info("[US-260 / CA5] Proposition %s déjà %s → rien d'exécuté", relue.code, relue.etat)
        await _dire(svc_decisions.deja_traitee(
            relue.etat, relue.traite_le, relue.traite_canal or (relue.canal if relue.traite_le else None),
        ))

    if not proposition.en_attente:
        await _deja_traitee()
        return
    commande = proposition.commande

    # ── [US-259 / CA5] 30 minutes, pas une de plus ───────────────────────────
    if proposition.expiree():
        ctx.user_data['mode'] = None
        if svc_propositions.consommer(
            proposition, svc_propositions.ETAT_PERIMEE, canal=svc_propositions.CANAL_TELEGRAM,
        ):
            svc_interpreteur.persister_journal(
                tenant, commande, svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id,
            )
        await _dire(_MSG_DEMANDE_EXPIREE)
        return

    # ── Abandon : toujours permis, il ne fait rien ───────────────────────────
    if decision.action == svc_decisions.ACTION_ABANDONNER:
        ctx.user_data['mode'] = None
        if not svc_propositions.consommer(
            proposition, svc_propositions.ETAT_ABANDONNEE, canal=svc_propositions.CANAL_TELEGRAM,
        ):
            await _deja_traitee()
            return
        svc_interpreteur.persister_journal(tenant, commande, svc_interpreteur.ISSUE_REFUSEE, proposition.log_id)
        svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_REFUSEE)
        await _dire(svc_decisions.TEXTE_ABANDONNEE)
        return

    # ── [CA3] Une action destructrice ne se confirme qu'au bouton ────────────
    # L'agent l'a déjà refusé ; la base le rejoue, au cas où la proposition aurait changé.
    if svc_decisions.est_destructrice(commande):
        log.info("[US-260 / CA3] Proposition %s destructrice : confirmation par phrase refusée", proposition.code)
        await _remontrer_la_carte(update, ctx, proposition, svc_decisions.TEXTE_BOUTON_SEUL, msg=msg)
        return
    if not svc_decisions.est_prete(commande):
        await _dire(svc_decisions.TEXTE_PAS_PRETE)
        return

    # ── [US-259 / CA4] Dans SON potager, le rôle relu sur celui-là ───────────
    contexte = _contexte_sur(tenant.user_id, proposition.potager_id)
    if contexte is None:
        ctx.user_data['mode'] = None
        if svc_propositions.consommer(
            proposition, svc_propositions.ETAT_ABANDONNEE, canal=svc_propositions.CANAL_TELEGRAM,
        ):
            svc_interpreteur.persister_journal(tenant, commande, svc_interpreteur.ISSUE_ABANDONNEE, proposition.log_id)
            svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_ABANDONNEE)
        await _dire(_MSG_POTAGER_PERDU)
        return
    _armer(contexte)

    # ── Confirmation : sortie de l'attente AVANT l'exécution, atomique (US-259 / CA3) ─
    ctx.user_data['mode'] = None
    if not svc_propositions.consommer(
        proposition, svc_propositions.ETAT_CONFIRMEE, canal=svc_propositions.CANAL_TELEGRAM,
    ):
        await _deja_traitee()
        return
    svc_interpreteur.persister_journal(contexte, commande, svc_interpreteur.ISSUE_CONFIRMEE, proposition.log_id)
    svc_interpreteur.journaliser(commande, svc_interpreteur.ISSUE_CONFIRMEE)
    log.info("[US-260 / CA1] Proposition %s confirmée par une phrase", proposition.code)
    if isinstance(commande, svc_interpreteur.Plan):
        from app.services.agent import executeurs as svc_executeurs

        resultats = svc_executeurs.executer_plan(commande, contexte, proposition_id=proposition.id)
        rendu = await _compte_rendu_du_plan(commande, resultats, contexte)
        await _dire(rendu.texte)
        await _proposer_la_suite(update, ctx, rendu.suggestion)
        return
    await _dire(f"⏳ `{commande.commande_equivalente()}`", markdown=True)
    await _interp_executer(update, ctx, commande, potager_id=proposition.potager_id, proposition_id=proposition.id)


async def _remontrer_la_carte(update: Update, ctx: ContextTypes.DEFAULT_TYPE,
                              proposition: PropositionConversation, invitation: str, msg=None) -> None:
    """[US-260 / CA3] L'invitation à cliquer, et la carte de la proposition REMONTRÉE avec ses
    boutons : le jardinier n'a pas à la chercher plus haut dans la conversation."""
    if isinstance(proposition.commande, svc_interpreteur.Plan):
        await _plan_afficher(update, proposition, msg=msg, preambule=invitation)
    else:
        await _interp_etape_suivante(update, ctx, proposition, msg=msg, preambule=invitation)


async def _interp_completion_texte(update: Update, ctx: ContextTypes.DEFAULT_TYPE, texte: str) -> None:
    """[CA13] Réponse tapée à un argument demandé.

    Un argument de vocabulaire fermé n'accepte QUE l'une de ses valeurs : la
    saisie est comparée à la normalisation près, jamais rapprochée d'un
    synonyme. Le jardinier qui écrit « ça se marie bien » se voit reproposer les
    boutons plutôt que voir « favorable » écrit à sa place.
    """
    tenant = current_context()
    proposition = svc_propositions.en_attente(tenant.user_id, tenant.potager_id)
    if proposition is None or not proposition.attend:
        ctx.user_data['mode'] = None
        return
    commande = proposition.commande
    argument = next((a for a in commande.manquants if a.nom == proposition.attend), None)
    if argument is None:
        ctx.user_data['mode'] = None
        return

    valeur = (texte or "").strip()
    if argument.vocabulaire:
        normalise, _ = svc_interpreteur.normaliser(valeur)
        correspondance = next(
            (v for v in argument.vocabulaire if svc_interpreteur.normaliser(v)[0] == normalise),
            None,
        )
        if correspondance is None:
            await update.message.reply_text(
                f"❓ Valeur attendue parmi : *{'* · *'.join(argument.vocabulaire)}*",
                parse_mode="Markdown",
            )
            return
        valeur = correspondance

    suite = svc_propositions.mettre_a_jour(
        proposition, commande=commande.avec(**{argument.nom: valeur}), attend=proposition.attend,
    )
    if suite is None:
        ctx.user_data['mode'] = None
        await update.message.reply_text(_MSG_DEMANDE_EXPIREE)
        return
    await _interp_etape_suivante(update, ctx, suite)


# ══════════════════════════════════════════════════════════════════════════════
# [US-237] Plusieurs commandes en une phrase — un plan, une confirmation
# ══════════════════════════════════════════════════════════════════════════════
# Un plan ne passe PAS par les handlers : ils répondent un message et rendent
# None, on ne saurait pas si l'étape 1 a réussi avant de lancer l'étape 2. Ses
# étapes passent par les exécuteurs de service (`app.services.agent.executeurs`),
# qui appellent le même service que les handlers et rendent un résultat.

async def _plan_proposer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, plan, msg=None,
                         preambule: str = "") -> None:
    """[CA5] Les étapes numérotées et UNE paire « Tout confirmer » / « Annuler »,
    liée à sa proposition et à son potager (US-234). Rien ne s'exécute ici.
    [US-257] `preambule` : le texte de l'agent, au-dessus des étapes.
    [US-259] Le plan est rangé en base, comme toute proposition."""
    tenant = current_context()
    _abandonner_precedente(tenant)
    log_id = svc_interpreteur.persister_journal(tenant, plan, svc_interpreteur.ISSUE_PROPOSEE)
    svc_interpreteur.journaliser(plan, svc_interpreteur.ISSUE_PROPOSEE)
    proposition = svc_propositions.proposer(tenant, plan, log_id=log_id)
    ctx.user_data['mode'] = None
    await _plan_afficher(update, proposition, msg=msg, preambule=preambule)


async def _plan_afficher(update: Update, proposition: PropositionConversation, msg=None,
                         preambule: str = "") -> None:
    """La carte d'un plan en attente : les étapes et sa paire de boutons, liés à son code."""
    plan = proposition.commande
    ident = proposition.code
    clavier = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Tout confirmer", callback_data=f"interp:ok:{ident}"),
        InlineKeyboardButton("❌ Annuler", callback_data=f"interp:non:{ident}"),
    ]])
    texte = _entete_potager(proposition) + "📋 " + svc_interpreteur.recapitulatif_plan(plan)
    if preambule:
        texte = f"{texte_de_l_agent(preambule)}\n\n{texte}"
    if msg is not None:
        await msg.edit_text(texte, parse_mode="Markdown", reply_markup=clavier)
    else:
        await _message_de(update).reply_text(texte, parse_mode="Markdown", reply_markup=clavier)


#: [US-264] La suite proposée attend dans `user_data` : l'ignorer ne bloque rien (CA6), un redémarrage
#: du bot l'efface sans conséquence.
_CLE_SUGGESTION = "suggestion_suite"
_MSG_SUGGESTION_PERIMEE = "⏱ Cette suggestion n'est plus d'actualité. Redis-moi ce que tu veux faire."


async def _compte_rendu_du_plan(plan, resultats, contexte: TenantContext):
    """[US-264 / CA1, CA2] Le compte rendu rédigé et contrôlé, et la suite utile éventuelle. Hors de la
    boucle d'événements : la rédaction appelle un modèle et la suggestion lit la base."""
    import asyncio

    from app.services.agent import compte_rendu as svc_compte_rendu

    return await asyncio.to_thread(svc_compte_rendu.composer, plan, resultats, contexte)


async def _proposer_la_suite(update: Update, ctx: ContextTypes.DEFAULT_TYPE, suggestion) -> None:
    """[US-264 / CA5, CA6] Au plus une suite, avec [Oui] [Plus tard]. « Oui » la rend à l'agent comme une
    phrase du jardinier : une proposition à confirmer, jamais une exécution."""
    if suggestion is None:
        return
    message = _message_de(update)
    if message is None:
        return
    donnees = ctx.user_data if isinstance(getattr(ctx, "user_data", None), dict) else None
    if donnees is not None:
        donnees[_CLE_SUGGESTION] = suggestion.phrase_oui
    clavier = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Oui", callback_data="sug:oui"),
        InlineKeyboardButton("⏭ Plus tard", callback_data="sug:non"),
    ]])
    await message.reply_text(f"💡 {suggestion.texte}", reply_markup=clavier)


async def _suggestion_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-264 / CA5, CA6] Le clic sur la suite proposée. « Plus tard » n'enregistre rien."""
    query = update.callback_query
    await query.answer()
    donnees = ctx.user_data if isinstance(getattr(ctx, "user_data", None), dict) else {}
    phrase = donnees.pop(_CLE_SUGGESTION, None)
    if (query.data or "") != "sug:oui":
        await query.edit_message_reply_markup(reply_markup=None)
        return
    if not phrase:
        await query.edit_message_text(_MSG_SUGGESTION_PERIMEE, reply_markup=None)
        return
    await query.edit_message_reply_markup(reply_markup=None)
    resultat = svc_interpreteur.interpreter(phrase, current_context(), contexte_court=contexte_court_de(update))
    await _traiter_commande_interpretee(update, ctx, resultat)


async def _plan_executer(update: Update, plan, query, contexte: TenantContext,
                         proposition_id: Optional[int] = None, ctx: Optional[ContextTypes.DEFAULT_TYPE] = None) -> None:
    """[CA6, CA7] Exécute les étapes dans l'ordre, dans le potager DU PLAN
    (US-259 / CA4), et remplace le récapitulatif par le compte rendu.
    [US-261] Chaque étape exécutée est retenue parmi les actions menées.
    [US-264] Le compte rendu dit ce qui a vraiment été fait ; la suite utile, s'il y en a une,
    arrive dans un message à part."""
    from app.services.agent import executeurs as svc_executeurs

    resultats = svc_executeurs.executer_plan(plan, contexte, proposition_id=proposition_id)
    rendu = await _compte_rendu_du_plan(plan, resultats, contexte)
    # Texte brut : les raisons viennent du service, elles ne sont pas du Markdown.
    await query.edit_message_text(rendu.texte, reply_markup=None)
    if ctx is not None:
        await _proposer_la_suite(update, ctx, rendu.suggestion)


def texte_de_l_agent(texte: str) -> str:
    """[US-257] Le texte rédigé par l'agent, sûr dans un message Markdown : un `_`,
    un `*` ou un accent grave qu'il écrirait casserait le message entier."""
    return _md((texte or "").replace("*", "").replace("`", "")).strip()


def texte_aiguillage(aiguillage) -> Optional[str]:
    """[INC-018] Ce que le bot répond quand une demande d'agir n'a pas été traitée ;
    None pour une question ou un geste, que le flux suit.

    [US-257 / CA6] Plus aucun texte figé ne répond pour l'agent : une précision ou
    une demande hors catalogue est une `ReponseAgent`, rédigée par lui."""
    if aiguillage.vers == svc_interpreteur.VERS_NON_COMPRIS:
        # [INC-018] Une demande d'agir que ni l'agent ni l'ancien repli n'ont traitée : on le
        # dit, au lieu de laisser le routeur répondre à côté (la liste des lots en pépinière).
        return (
            "🙏 Je n'ai pas réussi à traiter cette demande : je ne l'ai pas comprise, "
            "ou le service est momentanément indisponible.\n\n"
            "_Rien n'a été fait._ Réessaie dans un instant, ou passe par la commande : "
            f"`{(aiguillage.message or '/menu').replace('`', '')}`."
        )
    return None


async def _suivre_aiguillage(message, aiguillage, msg=None) -> bool:
    """[US-236, INC-018] Une demande d'agir non traitée reçoit sa réponse ici, et rien
    n'est proposé ni exécuté. Une question ou un geste rend False : le flux
    appelant les envoie à la cascade ou au parseur, sans reclasser (CA2, CA3)."""
    texte = texte_aiguillage(aiguillage)
    if texte is None:
        return False
    log.info("[US-236] Aiguillage %s → %s", aiguillage.vers, aiguillage.message or "-")
    if msg is not None:
        await msg.edit_text(texte, parse_mode="Markdown")
    else:
        await message.reply_text(texte, parse_mode="Markdown")
    return True


async def _repondre_agent(update: Update, ctx: ContextTypes.DEFAULT_TYPE, reponse, msg=None) -> bool:
    """[US-257] La réponse de l'agent : son texte, et sa proposition s'il en fait une.

    Une proposition passe par le chemin habituel (récapitulatif, boutons, complétion),
    le texte de l'agent au-dessus. Sans proposition, le texte est la réponse : une
    salutation, une vraie question qui nomme les choix, ce que l'application ne sait
    pas faire. Il part en texte brut — c'est le modèle qui l'a écrit.
    """
    if reponse.decision is not None:
        # [US-260] « Vas-y », « laisse tomber » : la décision validée par le code, exécutée comme le bouton.
        await _interp_decider(update, ctx, reponse.decision, msg=msg)
    elif isinstance(reponse.proposition, svc_interpreteur.Plan):
        await _plan_proposer(update, ctx, reponse.proposition, msg=msg, preambule=reponse.texte)
    elif reponse.proposition is not None:
        await _interp_proposer(update, ctx, reponse.proposition, msg=msg, preambule=reponse.texte)
    elif reponse.bouton_seul and await _invite_a_cliquer(update, ctx, reponse, msg):
        pass
    else:
        log.info("[US-257] Réponse de l'agent (%s) : %r", ", ".join(reponse.outils) or "texte seul",
                 reponse.texte[:80])
        if msg is not None:
            await msg.edit_text(reponse.texte)
        else:
            await _message_de(update).reply_text(reponse.texte)
    # [US-258 / CA1] Le premier échange avec le compagnon demande comment appeler le jardinier.
    await accueil_premier_contact(update, ctx)
    return True


async def _invite_a_cliquer(update: Update, ctx: ContextTypes.DEFAULT_TYPE, reponse, msg=None) -> bool:
    """[US-260 / CA3] Une action destructrice dite d'un mot : l'invitation et la carte remontrée.
    False si la proposition n'attend plus — la réponse part alors en texte simple."""
    tenant = current_context()
    proposition = svc_propositions.en_attente(tenant.user_id, tenant.potager_id)
    if proposition is None:
        return False
    await _remontrer_la_carte(update, ctx, proposition, reponse.texte, msg=msg)
    return True


async def _traiter_commande_interpretee(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, resultat, msg=None
) -> bool:
    """Aiguille un résultat d'interprétation. Retourne True s'il a été pris en charge.

    [CA12] Une ambiguïté — plusieurs commandes reconnues dans la même phrase —
    n'exécute pas la plus probable : elle demande laquelle.
    """
    if resultat is None:
        return False
    try:
        return await _aiguiller(update, ctx, resultat, msg)
    finally:
        # [US-238 / CA1, US-259 / CA1] Chaque phrase interprétée devient un échange,
        # que l'agent lira avec la phrase suivante — dans ce canal ou dans l'autre.
        _noter_echange(resultat)


async def _aiguiller(update: Update, ctx: ContextTypes.DEFAULT_TYPE, resultat, msg=None) -> bool:
    message = _message_de(update)
    if isinstance(resultat, svc_interpreteur.ReponseAgent):
        return await _repondre_agent(update, ctx, resultat, msg=msg)
    if isinstance(resultat, svc_interpreteur.Aiguillage):
        return await _suivre_aiguillage(message, resultat, msg=msg)
    if isinstance(resultat, svc_interpreteur.Plan):
        await _plan_proposer(update, ctx, resultat, msg=msg)
        return True
    if isinstance(resultat, svc_interpreteur.Ambiguite):
        lignes = ["❓ *Plusieurs commandes possibles* — laquelle ?", ""]
        for candidat in resultat.candidats:
            lignes.append(f"• {candidat.forme.libelle} : `{candidat.commande_equivalente()}`")
        lignes.append("")
        lignes.append("_Reformulez, ou tapez directement la commande voulue._")
        texte = "\n".join(lignes)
        log.info(
            "[US-172 CA12] Ambiguïté (%s) → précision demandée",
            ", ".join(c.commande for c in resultat.candidats),
        )
        if msg is not None:
            await msg.edit_text(texte, parse_mode="Markdown")
        else:
            await message.reply_text(texte, parse_mode="Markdown")
        return True

    await _interp_proposer(update, ctx, resultat, msg=msg)
    return True
