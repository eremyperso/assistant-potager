"""
app/bot/cartes_compagnon.py — La carte d'un geste dit dans le portail, posée dans Telegram [US-272]
================================================================================================
Un geste dit dans le panneau de la PWA attend en base (US-270) et part aussi dans Telegram, dès
sa création (D13). Ses deux boutons, `cmp:ok:<code>` et `cmp:non:<code>`, le confirment ou le
laissent tomber depuis le téléphone, par le MÊME service que le portail
(`gestes_conversation.confirmer`) : la première réponse l'emporte (F1), le geste s'écrit dans
SON potager quel que soit le potager actif du chat (F5), et rien n'est écrit deux fois.

Aucune logique ici : lire le bouton, armer le bon potager, appeler le service, dire le résultat.
Une commande ou un plan nés dans le portail reprennent les boutons `interp:` (même gestionnaire
que la conversation, `interpretation._interp_cb`).
"""
from __future__ import annotations

from typing import Optional

from telegram import Update
from telegram.ext import ContextTypes

from app.services.compagnon import deux_canaux as svc_deux_canaux
from app.services.compagnon import gestes_conversation as svc_gestes_dits
from app.services.compagnon import propositions as svc_propositions
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from .interpretation import _MSG_DEMANDE_EXPIREE, _MSG_POTAGER_PERDU, _armer, _contexte_sur, _jardinier_au_clic
from .noyau import log

TEXTE_LECTURE_SEULE = "🔒 Tu es en lecture seule sur ce potager : rien n'a été enregistré."


def _decoder(data: str) -> tuple[str, Optional[str]]:
    """`cmp:<ok|non>:<code>` → (action, code)."""
    morceaux = (data or "").split(":")
    return (morceaux[1] if len(morceaux) > 1 else ""), (morceaux[2] if len(morceaux) > 2 else None) or None


def _lignes(geste: svc_gestes_dits.GesteDit) -> str:
    return "\n".join(f"• {svc_gestes_dits.resume(item)}" for item in geste.items)


def texte_apres_confirmation(geste: svc_gestes_dits.GesteDit, resultat) -> str:
    """Ce que devient la carte une fois le geste confirmé ici : écrit, ou refusé en clair."""
    if resultat.complet:
        texte = f"✅ Confirmé\n{_lignes(geste)}"
    else:
        texte = f"❌ {resultat.erreur}"
        if resultat.enregistres:
            texte += "\nDéjà enregistré avant l'erreur : " + ", ".join(
                svc_gestes_dits.resume(item) for item, _ in resultat.enregistres)
    if resultat.avertissements:
        texte += "\n\n" + "\n".join(resultat.avertissements)
    return texte


async def carte_compagnon_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-272 / CA1, CA2] Confirmer ou laisser tomber, dans Telegram, un geste dit dans le portail."""
    query = update.callback_query
    await query.answer()
    action, code = _decoder(query.data)
    user_id = _jardinier_au_clic(update) if code else None
    geste = svc_gestes_dits.par_code(code, user_id)
    if geste is None or action not in ("ok", "non"):
        await query.edit_message_text(_MSG_DEMANDE_EXPIREE, reply_markup=None)
        return
    if not geste.en_attente or geste.expiree():
        log.info("[US-272 / CA2] Geste %s déjà %s → rien d'exécuté", geste.code, geste.etat)
        etat = geste.etat if not geste.en_attente else svc_propositions.ETAT_PERIMEE
        await query.edit_message_text(
            svc_deux_canaux.texte_deja_traitee(etat, geste.traite_canal, geste.traite_le), reply_markup=None,
        )
        return

    # [F5] Le geste s'écrit dans SON potager, le rôle relu sur celui-là.
    contexte = _contexte_sur(user_id, geste.potager_id)
    if contexte is None:
        await query.edit_message_text(_MSG_POTAGER_PERDU, reply_markup=None)
        return
    _armer(contexte)
    try:
        if action == "non":
            svc_gestes_dits.abandonner(contexte, geste.id, canal=svc_propositions.CANAL_TELEGRAM)
            await query.edit_message_text(f"❌ Laissé tomber — rien n'a été fait.\n{_lignes(geste)}", reply_markup=None)
            return
        confirme, resultat = svc_gestes_dits.confirmer(contexte, geste.id, canal=svc_propositions.CANAL_TELEGRAM)
    except svc_gestes_dits.GesteDejaTraiteError as e:
        # [CA2 / F1] Le portail a répondu entre la lecture et le clic : la première réponse l'emporte.
        await query.edit_message_text(svc_deux_canaux.texte_deja_traitee(e.etat, e.canal, e.traite_le), reply_markup=None)
        return
    except (PermissionInsuffisanteError, PotagerArchiveError) as e:
        log.info("[US-272] Geste %s refusé : %s", geste.code, e)
        await query.edit_message_text(TEXTE_LECTURE_SEULE if isinstance(e, PermissionInsuffisanteError) else str(e),
                                      reply_markup=None)
        return
    log.info("[US-272 / CA1] Geste %s confirmé depuis Telegram : %s écrit(s)", geste.code, len(resultat.enregistres))
    await query.edit_message_text(texte_apres_confirmation(confirme, resultat), reply_markup=None)
