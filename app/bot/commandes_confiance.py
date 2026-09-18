"""Commande /confiance [US-179] — « je peux semer / planter X ce week-end ? ».

US-178 CALCULE la confiance ; ce module la met dans la main du jardinier, là où
la question se pose : au champ, au téléphone, souvent à la voix. Il ne recalcule
rien et n'écrit rien lui-même — trois responsabilités, et trois seulement :

1. **Lire la demande** — culture, action, date, parcelle arrivent déjà découpées
   par l'interpréteur (US-172), qui reconnaît la question à zéro jeton (CA2).
   La commande tapée suit exactement la même forme.
2. **Mettre en mots** — `_formater_reponse` est une fonction PURE : elle prend
   une `Confiance` et rend le message. C'est elle que les tests du CA4 lisent,
   sans Telegram ni base.
3. **Fermer la boucle** — les boutons du CA6 rejoignent le flux d'enregistrement
   EXISTANT (`_parse_and_save`, avec ses items pré-parsés), jamais un second
   chemin d'écriture.

⚖️ Aucun appel modèle n'est introduit ici : la réponse est un gabarit texte, et
c'est une condition de la Definition of Done de l'épic 8.
"""
import time

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes

from database.db import SessionLocal
from utils.parcelles import resolve_parcelle
from app.services.context import current_context
from app.services import confiance_semis as svc_confiance
from app.services import contexte_semis as svc_contexte_semis
from app.services import calendrier_cultural as svc_calendrier
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from llm.parseur_deterministe import ORIGINE_DETERMINISTE
from datetime import date, timedelta

from .noyau import _md, log
from .etat import _CONFIANCE_PENDING, _CONFIANCE_TIMEOUT
from .commandes_calendrier import _fusionner_pleine_terre


USAGE = (
    "*Usage :*\n"
    "  /confiance <culture> <semis|pepiniere|pleine\\_terre|plantation> "
    "\\[date] \\[parcelle]\n\n"
    "_Ou demandez-le simplement :_ « je peux semer des haricots ce week-end ? »"
)

#: [CA6] Nombre de jours dont « Redemander » décale la question. Une valeur, un
#: seul endroit — c'est aussi celle qu'annonce le libellé du bouton.
JOURS_REDEMANDE = 10

#: Ce que chaque état de motif montre en tête de ligne (CA4).
_PUCES: dict[str, str] = {
    svc_confiance.ETAT_GAGNE: "✅",
    svc_confiance.ETAT_PERDU: "❌",
    svc_confiance.ETAT_INDETERMINE: "❔",
}

#: [CA4] L'ordre d'affichage des motifs : ce qui fait gagner, puis ce qui fait
#: perdre, puis ce qu'on ne sait pas. Un jardinier lit d'abord ce qui l'autorise.
_ORDRE_MOTIFS: tuple[str, ...] = (
    svc_confiance.ETAT_GAGNE, svc_confiance.ETAT_PERDU, svc_confiance.ETAT_INDETERMINE,
)

_MOIS_LONGS: tuple[str, ...] = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)


def _jour_en_clair(jour: date) -> str:
    """« 23 mai » — sans l'année quand elle est celle qui court."""
    libelle = f"{jour.day} {_MOIS_LONGS[jour.month - 1]}"
    return libelle if jour.year == date.today().year else f"{libelle} {jour.year}"


def _geste_et_contexte(action: str) -> tuple[str, "str | None"]:
    """Action du moteur de confiance → geste enregistrable + filière d'US-069.

    Les deux vocabulaires existent déjà ; celui-ci est le seul endroit du projet
    qui les met en regard, pour qu'un bouton d'enregistrement n'invente jamais un
    troisième nom d'action.
    """
    if action == svc_confiance.ACTION_PLANTATION:
        return "plantation", None
    if action == svc_confiance.ACTION_SEMIS_PEPINIERE:
        return "semis", svc_contexte_semis.CONTEXTE_PEPINIERE
    if action == svc_confiance.ACTION_SEMIS_PLEINE_TERRE:
        return "semis", svc_contexte_semis.CONTEXTE_PLEINE_TERRE
    return "semis", None


# ══════════════════════════════════════════════════════════════════════════════
# La réponse — fonction PURE, testée sans Telegram (CA4, CA5, CA9)
# ══════════════════════════════════════════════════════════════════════════════
def _formater_reponse(confiance: svc_confiance.Confiance, parcelle_nom: "str | None" = None) -> str:
    """[CA4, CA5] Le message rendu au jardinier, et rien d'autre.

    Tout libellé venu des données — culture, parcelle, motifs — traverse `_md` :
    un potager nommé « carré\\_nord » ferait autrement échouer l'envoi Telegram
    entier sur un `Can't parse entities`, et la réponse serait perdue (CA9).
    """
    entete = (
        f"🌱 *{_md(confiance.culture.capitalize())}* · "
        f"{_md(svc_confiance.LIBELLES_ACTIONS[confiance.action])} · "
        f"{_md(svc_calendrier.LIBELLES_ZONES.get(confiance.zone, confiance.zone))}"
    )
    if parcelle_nom:
        entete += f" · {_md(parcelle_nom)}"
    lignes = [entete, f"_{_jour_en_clair(confiance.date_cible)}_", ""]

    # ── [CA5] Sans fenêtre pour cette phase, il n'y a pas de score — un tiret,
    # et ce qu'il faut faire pour qu'il y en ait un. Jamais une estimation.
    if confiance.sans_score:
        lignes.append(f"{svc_confiance.TIRET} {_md(svc_confiance.MOTIF_SANS_CALENDRIER)}.")
        lignes.append(
            f"Complétez-le avec `/calendrier {_md(confiance.culture)}` — "
            "je préfère ne rien dire qu'inventer une date."
        )
        return "\n".join(lignes)

    lignes.append(f"*{confiance.affichage}*")
    lignes.append("")
    for etat in _ORDRE_MOTIFS:
        for motif in confiance.motifs:
            if motif.etat != etat:
                continue
            lignes.append(f"{_PUCES[etat]} {_md(motif.libelle)}")

    lignes.append("")
    if confiance.recolte_min and confiance.recolte_max:
        # [CA4] Une FOURCHETTE, au conditionnel — jamais une date sèche.
        lignes.append(
            f"🌾 Récolte attendue entre le {_jour_en_clair(confiance.recolte_min)} "
            f"et le {_jour_en_clair(confiance.recolte_max)}"
        )
    else:
        lignes.append(f"🌾 Récolte attendue : {svc_confiance.TIRET}")

    for avertissement in confiance.avertissements:
        lignes.append(f"_{_md(avertissement)}_")
    return "\n".join(lignes)


def _boutons(confiance: svc_confiance.Confiance) -> InlineKeyboardMarkup:
    """[CA6] De la recommandation au geste, sans repasser par une commande.

    « Redemander » n'est proposé que s'il y a un score à revoir : sans calendrier,
    la même question dans dix jours rendrait le même tiret.
    """
    geste, _ = _geste_et_contexte(confiance.action)
    libelle = "🌱 Enregistrer le semis" if geste == "semis" else "🌿 Enregistrer la plantation"
    boutons = [[InlineKeyboardButton(libelle, callback_data="conf:enr")]]
    if not confiance.sans_score:
        boutons.append([InlineKeyboardButton(
            f"🔁 Redemander dans {JOURS_REDEMANDE} jours", callback_data="conf:redemande",
        )])
    return InlineKeyboardMarkup(boutons)


# ══════════════════════════════════════════════════════════════════════════════
# Lecture des arguments (CA1, CA3)
# ══════════════════════════════════════════════════════════════════════════════
def _decouper_arguments(args: list) -> "tuple[str, str, str | None, str | None] | None":
    """`<culture> <action> [date] [parcelle]` → les quatre valeurs, ou None.

    L'ACTION est le pivot : elle est obligatoire, et c'est ce qui rend la lecture
    possible. « pomme de terre » et « planche nord » comptent chacune plusieurs
    mots ; sans un jeton connu au milieu, rien ne dirait où finit l'une et où
    commence l'autre. Les règles d'interprétation la renseignent toujours.
    """
    jetons = _fusionner_pleine_terre([str(a) for a in args if str(a).strip()])
    for rang, jeton in enumerate(jetons):
        try:
            action = svc_confiance.normaliser_action(jeton)
        except svc_confiance.ActionInvalideError:
            continue
        if rang == 0:                      # aucune culture avant le pivot
            return None
        culture = " ".join(jetons[:rang])
        reste = jetons[rang + 1:]
        date_iso = None
        if reste:
            try:
                date.fromisoformat(reste[0])
                date_iso, reste = reste[0], reste[1:]
            except ValueError:
                pass
        return culture, action, date_iso, (" ".join(reste) or None)
    return None


async def _repondre(update: Update, texte: str, clavier=None) -> None:
    message = update.message or (update.callback_query.message if update.callback_query else None)
    await message.reply_text(texte, parse_mode="Markdown", reply_markup=clavier)


# ══════════════════════════════════════════════════════════════════════════════
# /confiance
# ══════════════════════════════════════════════════════════════════════════════
async def cmd_confiance(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /confiance — Est-ce le moment de semer ou de planter cette culture ? (US-179)

    Forme : `/confiance <culture> <semis|pepiniere|pleine_terre|plantation>
    [AAAA-MM-JJ] [parcelle]`. La même question se dicte en clair — « je peux
    semer des haricots ce week-end ? » — et emprunte alors ce même handler, par
    l'interpréteur d'US-172 (CA2).

    Aucune logique métier ici : le score vient de `app.services.confiance_semis`,
    la filière probable de `app.services.contexte_semis` (US-069).
    """
    lecture = _decouper_arguments(list(ctx.args or []))
    if lecture is None:
        await _repondre(update, USAGE)
        return
    culture, action, date_iso, parcelle_nom = lecture
    date_cible = date.fromisoformat(date_iso) if date_iso else date.today()
    await _evaluer_et_repondre(update, ctx, culture, action, date_cible, parcelle_nom)


async def _evaluer_et_repondre(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE,
    culture: str, action: str, date_cible: date, parcelle_nom: "str | None",
    msg=None,
) -> None:
    """Résout la parcelle, tranche la filière (CA3), évalue, répond (CA4, CA6)."""
    db = SessionLocal()
    try:
        tenant_ctx = current_context()
        parcelle = (
            resolve_parcelle(db, parcelle_nom, potager_id=tenant_ctx.potager_id)
            if parcelle_nom else None
        )
        if parcelle_nom and parcelle is None:
            # [CA7] Une parcelle nommée mais introuvable ne se remplace pas en
            # douce par le potager entier : le jardinier apprend qu'elle manque,
            # et la réponse qui suit dit sur quoi elle porte.
            log.info("[US-179] Parcelle %r inconnue → évaluation au potager", parcelle_nom)
            await _repondre(
                update,
                f"📍 Aucune parcelle « {_md(parcelle_nom)} » — je réponds pour le potager entier.",
            )
            parcelle_nom = None

        # ── [CA3] La filière, en un seul geste ──────────────────────────────
        # Même mécanique qu'US-069 : le référentiel tranche quand il ne connaît
        # qu'une seule façon de semer cette culture, et c'est la règle — aucune
        # question n'est posée dans ce cas. Il n'y a d'interrogatoire que quand
        # les deux fenêtres existent vraiment.
        if action == svc_confiance.ACTION_SEMIS:
            proposition = svc_contexte_semis.proposer_contexte(
                db, culture, tenant_ctx.potager_id, parcelle
            )
            if proposition is not None:
                action = f"semis_{proposition.contexte}"
                log.info(
                    "[US-179 / CA3] Filière tranchée sans question : %s (%s)",
                    action, proposition.motif,
                )
            else:
                await _demander_filiere(update, ctx, culture, date_cible, parcelle_nom, msg)
                return

        confiance = svc_confiance.evaluer(
            db, culture, action, date_cible,
            potager_id=tenant_ctx.potager_id,
            parcelle_id=parcelle.id if parcelle is not None else None,
        )
    except (PermissionInsuffisanteError, PotagerArchiveError) as e:
        await _repondre(update, f"⛔ {e}")
        return
    finally:
        db.close()

    # [CA10] Ce qui survit à la réponse tient dans ce seul dictionnaire, borné
    # dans le temps — jamais un `ctx.user_data['mode']`, qui capturerait la
    # commande suivante du jardinier.
    _CONFIANCE_PENDING[update.effective_user.id] = {
        "culture": culture, "action": confiance.action,
        "date": confiance.date_cible.isoformat(), "parcelle": parcelle_nom,
        "ts": time.time(),
    }
    texte = _formater_reponse(confiance, parcelle_nom)
    clavier = _boutons(confiance)
    if msg is not None:
        await msg.edit_text(texte, parse_mode="Markdown", reply_markup=clavier)
    else:
        await _repondre(update, texte, clavier)


async def _demander_filiere(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE,
    culture: str, date_cible: date, parcelle_nom: "str | None", msg=None,
) -> None:
    """[CA3] Les deux fenêtres de semis existent : la filière se choisit en un appui."""
    _CONFIANCE_PENDING[update.effective_user.id] = {
        "culture": culture, "action": svc_confiance.ACTION_SEMIS,
        "date": date_cible.isoformat(), "parcelle": parcelle_nom, "ts": time.time(),
    }
    clavier = InlineKeyboardMarkup([
        [InlineKeyboardButton("🪴 En pépinière", callback_data="conf:filiere:pepiniere")],
        [InlineKeyboardButton("🌿 En pleine terre", callback_data="conf:filiere:pleine_terre")],
    ])
    texte = (
        f"🌱 *{_md(culture.capitalize())}* se sème des deux façons dans votre zone.\n"
        "Laquelle vous intéresse ?"
    )
    log.info("[US-179 / CA3] Filière demandée pour %r", culture)
    if msg is not None:
        await msg.edit_text(texte, parse_mode="Markdown", reply_markup=clavier)
    else:
        await _repondre(update, texte, clavier)


# ══════════════════════════════════════════════════════════════════════════════
# Boutons (CA3, CA6)
# ══════════════════════════════════════════════════════════════════════════════
async def _confiance_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Callback inline — filière choisie, enregistrement, ou question décalée."""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    pending = _CONFIANCE_PENDING.get(user_id)

    if pending is None or time.time() - pending["ts"] > _CONFIANCE_TIMEOUT:
        _CONFIANCE_PENDING.pop(user_id, None)
        await query.edit_message_text("⏱ Question expirée. Reposez-la.", reply_markup=None)
        return

    culture = pending["culture"]
    date_cible = date.fromisoformat(pending["date"])
    parcelle_nom = pending.get("parcelle")

    # ── [CA3] Filière choisie : la même évaluation, cette fois tranchée ──────
    if query.data.startswith("conf:filiere:"):
        action = f"semis_{query.data.rsplit(':', 1)[1]}"
        await query.edit_message_reply_markup(reply_markup=None)
        await _evaluer_et_repondre(update, ctx, culture, action, date_cible, parcelle_nom)
        return

    # ── [CA6] La même question, dix jours plus tard ──────────────────────────
    if query.data == "conf:redemande":
        await query.edit_message_reply_markup(reply_markup=None)
        await _evaluer_et_repondre(
            update, ctx, culture, pending["action"],
            date_cible + timedelta(days=JOURS_REDEMANDE), parcelle_nom,
        )
        return

    # ── [CA6] De la recommandation à l'enregistrement, en un appui ───────────
    if query.data == "conf:enr":
        _CONFIANCE_PENDING.pop(user_id, None)
        await _enregistrer_le_geste(update, pending)


async def _enregistrer_le_geste(update: Update, pending: dict) -> None:
    """[CA6] Le flux d'enregistrement EXISTANT, avec son item déjà rempli.

    Rien n'est écrit ici : `_parse_and_save` reçoit un item pré-parsé — le même
    contrat que le parseur déterministe d'US-094 — et déroule ensuite tout ce
    qu'il déroule d'habitude, confirmation comprise (CA6). Aucun jeton n'est
    consommé : `pre_parsed_items` court-circuite l'appel au modèle.

    [CA7] Une parcelle absente n'est pas devinée : elle reste `None`, et c'est
    le flux existant qui la demande, comme pour n'importe quelle autre saisie.
    """
    from .saisie import _parse_and_save

    geste, contexte = _geste_et_contexte(pending["action"])
    item: dict = {
        "action": geste,
        "culture": pending["culture"],
        "variete": None,
        "quantite": None,
        "unite": None,
        "parcelle": pending.get("parcelle"),
        "rang": None,
        "duree_minutes": None,
        "traitement": None,
        "date": pending["date"],
        "commentaire": None,
        "nb_graines_semees": None,
        "nb_plants_godets": None,
        "origine_parsing": ORIGINE_DETERMINISTE,
    }
    if contexte is not None:
        item["contexte_semis"] = contexte

    # Le texte d'origine de l'événement décrit le geste, pas la question : c'est
    # lui qui sera relu dans l'historique, et c'est aussi lui que la garde
    # anti-hallucination compare à la culture de l'item (US-011 bis).
    texte = f"{geste} de {pending['culture']} le {pending['date']}"
    if pending.get("parcelle"):
        texte += f" parcelle {pending['parcelle']}"
    log.info("[US-179 / CA6] Enregistrement depuis la confiance : %s", texte)
    await _parse_and_save(update, texte, pre_parsed_items=[item])
