"""La file de gestes, vue du compagnon [US-224].

US-196 présentait UN geste, une fois, par un lien à usage unique de quinze
minutes. Ce module présente une FILE, à deux niveaux, aussi souvent qu'on veut :

* **Niveau 1 — la file** (`cmd_gestes`, bouton « Commencer ») : combien de
  gestes attendent, le détail des trois premiers, et deux actions seulement —
  commencer, ou couper les relances. **Aucune action de ce niveau n'enregistre
  quoi que ce soit** (CA5), ce qui est précisément ce qui le rend sûr à poser
  dans une notification.
* **Niveau 2 — le geste** (`presenter_geste`) : le récapitulatif existant
  d'US-021, inchangé — avertissement de rotation (US-167), parcelle ou quantité
  demandée si elle manque —, précédé de sa position (« geste 1 sur 3 ») et
  offrant trois issues nommées sans ambiguïté : *Confirmer*, *Plus tard*,
  *Abandonner ce geste* (CA6, CA7).

Trois chemins y mènent, et un seul code les sert : la commande `/gestes`
(CA10), un lien reçu depuis l'application qui ouvre directement le geste qu'il
désigne (CA11), et le bouton d'une relance.

⚠️ Aucun nouveau chemin d'écriture n'est ouvert ici, et c'est la condition qui
justifie l'US entière : le niveau 2 remet l'item pré-parsé dans
`saisie._parse_and_save`, le chemin du bouton « Enregistrer » d'US-179 à la
lettre. Zéro jeton — `pre_parsed_items` court-circuite l'appel au modèle.
"""
from datetime import datetime as _datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import SessionLocal, current_potager_id
from app.services import file_gestes as svc_file
from app.services import liaison_telegram as svc_liaison_telegram
from app.services import potager_actif as svc_potager_actif
from app.services import relances_file as svc_relances
from app.services.context import set_current_context
from database.models import Potager as _Potager

from .noyau import _md, log


_MSG_NON_LIE = (
    "🔗 *Compagnon pas encore activé*\n\n"
    "Ce lien désigne un geste préparé pour un compte, mais cette conversation "
    "n'est reliée à aucun compte. Activez d'abord le compagnon depuis "
    "l'application : vos gestes vous y attendent, ils ne sont pas perdus."
)

_MSG_FILE_VIDE = (
    "✅ *Aucun geste en attente.*\n\n"
    "Les gestes préparés depuis l'application viennent ici pour être confirmés. "
    "Rien ne vous attend pour l'instant."
)


# ══════════════════════════════════════════════════════════════════════════════
# Niveau 1 — la file
# ══════════════════════════════════════════════════════════════════════════════
def _boutons_niveau_1(relances_coupees: bool) -> InlineKeyboardMarkup:
    """[CA5] Deux actions, des BOUTONS, et aucune n'écrit.

    Le même couple que `relances_file.boutons_file`, aux mêmes données de
    rappel : un bouton posté par une notification et un bouton posté par la
    commande doivent aboutir au même endroit, sinon l'un des deux chemins
    dérive.
    """
    seconde = (
        InlineKeyboardButton("🔔 Reprendre les rappels", callback_data=svc_relances.CB_REPRENDRE)
        if relances_coupees
        else InlineKeyboardButton("🔕 Ne plus me relancer", callback_data=svc_relances.CB_COUPER)
    )
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Commencer", callback_data=svc_relances.CB_COMMENCER)],
        [seconde],
    ])


def _detacher(db, gestes: list) -> list:
    """Sort des gestes de leur session, attributs chargés — et dans cet ordre.

    ⚠️ `noter_activite` (CA19) valide une transaction sur la même session, ce
    qui EXPIRE tous les objets qu'elle porte. Les détacher sans les avoir
    rechargés donnerait des instances dont le premier accès à un attribut
    lèverait `DetachedInstanceError`, une fois la session refermée — c'est-à-dire
    au moment précis où le geste est présenté. Le `refresh` n'est donc pas une
    précaution : c'est ce qui rend le détachement utilisable.
    """
    for geste in gestes:
        db.refresh(geste)
        db.expunge(geste)
    return gestes


def _user_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> "int | None":
    """Le compte web derrière cette conversation — du garde de liaison, ou résolu.

    Les commandes passent par `_avec_garde_liaison`, qui a déjà renseigné
    `tenant_user_id` ; les callbacks, non. Une seule fonction pour les deux, et
    pas de `db.query` dans le handler : la résolution vit dans le service.
    """
    user_id = ctx.user_data.get("tenant_user_id")
    if user_id is not None:
        return user_id
    chat_id = update.effective_chat.id
    db = SessionLocal()
    try:
        return svc_liaison_telegram.resoudre_user_id_pour_chat(db, chat_id)
    finally:
        db.close()


async def _afficher_file(update: Update, user_id: int, editer: bool = False) -> int:
    """[CA5, CA10, CA19] Poste le niveau 1 et rend le nombre de gestes en attente.

    Consulter sa file est une ACTIVITÉ : elle remet le compteur de relance à
    zéro (CA19). Elle ne rallonge en revanche la vie d'aucun geste.
    """
    message = update.effective_message
    with svc_file.lecture_hors_tenant() as db:
        gestes = svc_file.lister_en_attente(db, user_id)
        svc_relances.noter_activite(db, user_id)
        if not gestes:
            texte, boutons = _MSG_FILE_VIDE, None
        else:
            nb = len(gestes)
            entete = (
                f"🌱 *{nb} geste{'s' if nb > 1 else ''} en attente* — préparé"
                f"{'s' if nb > 1 else ''} depuis l'application, pas encore "
                f"enregistré{'s' if nb > 1 else ''}."
            )
            texte = svc_relances.texte_file(db, gestes, entete)
            boutons = _boutons_niveau_1(not svc_relances.relances_actives(db, user_id))

    if editer and update.callback_query:
        await update.callback_query.edit_message_text(
            texte, parse_mode="Markdown", reply_markup=boutons,
        )
    else:
        await message.reply_text(texte, parse_mode="Markdown", reply_markup=boutons)
    return len(gestes)


async def cmd_gestes(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """/gestes — [CA10] Reprendre sa file quand on veut, sans dépendre d'une relance.

    C'est une CONSULTATION : elle ouvre le niveau 1, qui n'écrit rien. C'est ce
    qui la rend dictable au titre d'US-172 — ce n'est pas un code à coller.
    """
    user_id = _user_id(update, ctx)
    if user_id is None:
        await update.message.reply_text(_MSG_NON_LIE, parse_mode="Markdown")
        return
    await _afficher_file(update, user_id)


# ══════════════════════════════════════════════════════════════════════════════
# Niveau 2 — le geste
# ══════════════════════════════════════════════════════════════════════════════
async def _armer_potager(update: Update, ctx: ContextTypes.DEFAULT_TYPE, geste, user_id: int) -> bool:
    """[CA13] Le geste s'enregistre dans le potager de son DÉPÔT.

    Si le potager actif du compagnon est un autre, la bascule est nommée ET
    faite (US-088) : jamais d'écriture silencieuse ailleurs, et le jardinier
    apprend ici que son potager actif vient de changer.
    """
    message = update.effective_message
    db = SessionLocal()
    try:
        tenant_ctx = svc_potager_actif.resoudre_tenant_context(db, user_id)
        if tenant_ctx.potager_id != geste.potager_id:
            tenant_ctx = svc_potager_actif.definir_potager_actif(db, user_id, geste.potager_id)
            potager = db.query(_Potager).filter(_Potager.id == geste.potager_id).first()
            nom = _md(potager.nom) if potager else str(geste.potager_id)
            log.info(
                "[US-224 / CA13] Bascule de potager pour un geste en attente : "
                "user_id=%s → potager_id=%s", user_id, geste.potager_id,
            )
            await message.reply_text(
                f"🌻 Ce geste concerne votre potager *{nom}* — je bascule dessus.",
                parse_mode="Markdown",
            )
    except (svc_potager_actif.AucunPotagerError,
            svc_potager_actif.PotagerNonMembreError,
            svc_potager_actif.PotagerInactifError) as e:
        # [CA12] Le contexte a disparu : refus EN CLAIR, avec son motif, et le
        # geste quitte la file — jamais un fantôme qui échoue à chaque reprise.
        motif = str(e)
        svc_file.refuser(geste, motif)
        await message.reply_text(
            f"⛔ Ce geste ne peut plus être enregistré : {motif}\n"
            "Il a été retiré de votre file, et rien n'a été enregistré."
        )
        return False
    finally:
        db.close()

    ctx.user_data["tenant_user_id"] = user_id
    set_current_context(tenant_ctx)
    current_potager_id.set(tenant_ctx.potager_id)
    return True


async def presenter_geste(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, geste, user_id: int,
    position: int = 1, total: int = 1,
) -> None:
    """[CA6, CA12] Le flux d'enregistrement EXISTANT, avec son item déjà rempli.

    Strictement le corps de `commandes_confiance._enregistrer_le_geste` : rien
    n'est écrit ici, `_parse_and_save` reçoit un item pré-parsé — le contrat du
    parseur déterministe d'US-094 — et déroule ensuite tout ce qu'il déroule
    d'habitude, avertissement de rotation compris.

    Le contrôle de contexte (CA12) est fait AVANT toute présentation : montrer
    un récapitulatif que la confirmation rejettera ferait espérer pour rien.
    """
    message = update.effective_message

    if not await _armer_potager(update, ctx, geste, user_id):
        return

    db = SessionLocal()
    try:
        motif = svc_file.verifier_contexte(db, geste, user_id)
    finally:
        db.close()
    if motif:
        svc_file.refuser(geste, motif)
        log.info("[US-224 / CA12] Geste refusé : id=%s motif=%s", geste.id, motif)
        await message.reply_text(
            f"⛔ Ce geste ne peut plus être enregistré : {motif}.\n"
            "Il a été retiré de votre file, et rien n'a été enregistré."
        )
        await proposer_suivant(update, ctx, user_id)
        return

    from .saisie import _parse_and_save

    item = svc_file.item_du_geste(geste)

    # Le texte d'origine décrit le geste, pas le lien : c'est lui qui sera relu
    # dans l'historique, et c'est lui que la garde anti-hallucination compare à
    # la culture de l'item (US-011 bis). La phrase à dicter fait exactement cet
    # office — un gabarit, un seul endroit où il se compose.
    texte = svc_file.phrase_a_dicter(item)
    if item.get("date"):
        texte += f" le {item['date']}"

    if total > 1:
        # [CA6] La position précède le récapitulatif : le jardinier sait où il
        # en est avant de lire ce qu'on lui demande de confirmer.
        await message.reply_text(f"📋 Geste {position} sur {total}")

    log.info(
        "[US-224 / CA6] Geste de la file présenté à la confirmation : id=%s (%s/%s)",
        geste.id, position, total,
    )
    await _parse_and_save(
        update, texte, pre_parsed_items=[item],
        geste_file={
            "id": geste.id, "potager_id": geste.potager_id,
            "user_id": user_id, "position": position, "total": total,
        },
    )


#: [CA9] Les gestes reposés PENDANT cette session de traitement. Un « Plus
#: tard » laisse le geste dans la file (CA8) — le reproposer aussitôt en
#: ferait une boucle dont on ne sort qu'en abandonnant, exactement l'inverse de
#: ce que le bouton promet. L'ensemble vit dans `user_data` : il disparaît avec
#: la conversation, jamais avec le geste.
_CLE_REPOSES = "file_gestes_reposes"


def _reposes(ctx: ContextTypes.DEFAULT_TYPE) -> set:
    return ctx.user_data.setdefault(_CLE_REPOSES, set())


def reposer_pour_la_session(ctx: ContextTypes.DEFAULT_TYPE, geste_id: int) -> None:
    """[CA8, CA9] « Plus tard » — le geste reste en file, mais passe son tour."""
    _reposes(ctx).add(int(geste_id))


async def proposer_suivant(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int,
) -> None:
    """[CA9] Après un geste, le compagnon annonce ce qui reste et propose le suivant.

    Traiter plusieurs gestes à la suite ne redemande pas le contexte à chaque
    fois. Le jardinier peut s'arrêter à tout moment : le reste demeure en
    attente — c'est le sens du « Plus tard » qui accompagne l'annonce.
    """
    with svc_file.lecture_hors_tenant() as db:
        gestes = _detacher(db, svc_file.lister_en_attente(db, user_id))
    nb = len(gestes)
    if not nb:
        await update.effective_message.reply_text(
            "✅ *Votre file est vide* — plus rien n'attend d'être confirmé.",
            parse_mode="Markdown",
        )
        return

    restants = [g for g in gestes if g.id not in _reposes(ctx)]
    if not restants:
        # Tout ce qui reste a été reposé à l'instant : l'annoncer plutôt que de
        # reproposer en boucle ce que le jardinier vient d'écarter.
        await update.effective_message.reply_text(
            f"👍 Vos *{nb} geste{'s' if nb > 1 else ''}* rest"
            f"{'ent' if nb > 1 else 'e'} en attente. /gestes les rouvre quand vous voulez.",
            parse_mode="Markdown",
        )
        return

    await update.effective_message.reply_text(
        f"📋 Il reste *{nb} geste{'s' if nb > 1 else ''}* en attente.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("▶️ Geste suivant", callback_data=svc_relances.CB_COMMENCER)],
            [InlineKeyboardButton("⏸ Plus tard", callback_data="file:pause")],
        ]),
    )


async def ouvrir_premier_geste(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, user_id: int,
) -> None:
    """[CA5, CA9] Passe du niveau 1 au niveau 2, sur le plus ancien geste en attente.

    Le plus ancien de ceux qui n'ont pas été reposés à l'instant : « Plus tard »
    fait passer un geste derrière les autres, il ne le sort pas de la file.
    """
    with svc_file.lecture_hors_tenant() as db:
        gestes = svc_file.lister_en_attente(db, user_id)
        svc_relances.noter_activite(db, user_id)
        _detacher(db, gestes)
    if not gestes:
        await update.effective_message.reply_text(_MSG_FILE_VIDE, parse_mode="Markdown")
        return

    restants = [g for g in gestes if g.id not in _reposes(ctx)]
    if not restants:
        # Un second tour redonne droit de cité à tout le monde : le jardinier
        # qui redemande sa file après avoir tout reposé veut la revoir, pas
        # s'entendre dire qu'elle est vide alors qu'elle ne l'est pas.
        _reposes(ctx).clear()
        restants = gestes

    await presenter_geste(update, ctx, restants[0], user_id, position=1, total=len(gestes))


# ══════════════════════════════════════════════════════════════════════════════
# [CA11] Un lien ouvre DIRECTEMENT le geste qu'il désigne
# ══════════════════════════════════════════════════════════════════════════════
async def traiter_code_geste(
    update: Update, ctx: ContextTypes.DEFAULT_TYPE, code: str,
) -> None:
    """[CA11, CA12] `/start g<code>` — le geste désigné, sans passer par la file.

    Le lien n'est plus à usage unique : il reste valide tant que le geste l'est.
    Rouvrir le même lien redonne le même geste — c'est exactement ce qui
    manquait à US-196, où « Annuler » brûlait le geste et où rouvrir répondait
    « déjà utilisé ».
    """
    user_id = _user_id(update, ctx)
    if user_id is None:
        await update.message.reply_text(_MSG_NON_LIE, parse_mode="Markdown")
        return

    with svc_file.lecture_hors_tenant() as db:
        try:
            geste = svc_file.geste_par_code(db, code, user_id)
        except svc_file.CodeIntrouvableError:
            await update.message.reply_text(
                "❌ Ce lien ne désigne aucun geste. Il a peut-être été tronqué à la copie — "
                "ouvrez votre file avec /gestes."
            )
            return
        except svc_file.GesteAutreCompteError:
            # Ni le geste, ni la culture, ni le potager ne sont nommés : cette
            # conversation n'a pas à apprendre ce que préparait quelqu'un d'autre.
            await update.message.reply_text(
                "⛔ Ce geste a été préparé depuis un autre compte. Rien n'a été enregistré."
            )
            return
        except svc_file.GesteDejaTraiteError:
            await update.message.reply_text(
                "✅ Ce geste a déjà été traité. Votre file est consultable avec /gestes."
            )
            return
        except svc_file.GestePerimeError:
            await update.message.reply_text(
                f"🗑 Ce geste a été vidé au bout de {svc_file.DUREE_VIE_JOURS} jours sans "
                "avoir été enregistré. Relancez-le depuis l'application."
            )
            return
        total = svc_file.compter_en_attente(db, user_id)
        svc_relances.noter_activite(db, user_id)
        _detacher(db, [geste])

    await presenter_geste(update, ctx, geste, user_id, position=1, total=total)


# ══════════════════════════════════════════════════════════════════════════════
# Les boutons du niveau 1
# ══════════════════════════════════════════════════════════════════════════════
async def file_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[CA5, CA20] Commencer, couper les relances, les reprendre, s'arrêter.

    Aucune de ces actions n'enregistre quoi que ce soit — c'est la garantie du
    niveau 1, et c'est ce qui permet de poser ces boutons dans une notification
    sans risque d'écriture au doigt glissé.
    """
    query = update.callback_query
    await query.answer()
    donnee = query.data

    user_id = _user_id(update, ctx)
    if user_id is None:
        await query.edit_message_text(_MSG_NON_LIE.replace("*", ""))
        return

    if donnee == svc_relances.CB_COMMENCER:
        await ouvrir_premier_geste(update, ctx, user_id)
        return

    if donnee == "file:pause":
        # [CA8] Le jardinier s'arrête : rien ne quitte la file.
        await query.edit_message_text(
            "👍 Vos gestes restent en attente. Reprenez-les quand vous voulez avec /gestes."
        )
        return

    if donnee in (svc_relances.CB_COUPER, svc_relances.CB_REPRENDRE):
        actives = donnee == svc_relances.CB_REPRENDRE
        with svc_file.lecture_hors_tenant() as db:
            svc_relances.definir_relances(db, user_id, actives)
            nb = svc_file.compter_en_attente(db, user_id)
        if actives:
            await query.edit_message_text(
                f"🔔 Rappels repris. {nb} geste(s) en attente.\n"
                "Vous pouvez les recouper à tout moment depuis cette liste."
            )
        else:
            # [CA20] Couper les relances ne vide PAS la file, et le message le
            # dit : c'est la moitié de l'intérêt de la soupape.
            await query.edit_message_text(
                f"🔕 Je ne vous relancerai plus.\n\n"
                f"Vos {nb} geste(s) restent en attente — /gestes les rouvre quand "
                f"vous voulez. Ils seront vidés au bout de "
                f"{svc_file.DUREE_VIE_JOURS} jours, sans autre rappel."
            )
        return


# ══════════════════════════════════════════════════════════════════════════════
# [CA15, CA16, CA17, CA18] Le rendez-vous horaire de la file
# ══════════════════════════════════════════════════════════════════════════════
async def job_file_gestes(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Un seul job, toutes les heures — trois échéances qui n'ont pas la même maille.

    * **La relance** (CA15) est semestrielle au sens propre : deux créneaux
      quotidiens. Elle ne part donc que si l'heure courante en est un, et
      `relances_file.doit_relancer` en juge seul.
    * **L'avertissement** (CA17) tombe quatre heures avant la purge d'un geste,
      donc à une heure qui dépend du dépôt : il lui faut une maille plus fine
      qu'une demi-journée, d'où l'heure.
    * **La purge** (CA18) suit, et ce qu'elle vide est annoncé.

    Trois jobs distincts auraient été trois planifications à tenir alignées
    pour une seule et même file. Le prix de ce choix est un réveil horaire qui,
    la plupart du temps, ne fait rien : une requête sur un index, et il se
    rendort.

    ⚠️ Comme `job_purge_potagers`, ce job tourne hors dispatch Telegram : il
    n'a pas de potager actif, et n'en veut pas — la file est celle d'un COMPTE,
    elle peut couvrir plusieurs potagers (CA13). Les lectures se font donc GUC
    désarmé, et chaque écriture s'arme sur le potager de son geste.
    """
    maintenant = _datetime.utcnow()
    try:
        with svc_file.lecture_hors_tenant() as db:
            # [CA17] D'abord avertir : un geste averti puis purgé dans la même
            # heure aurait reçu ses deux messages, dans le bon ordre.
            a_avertir = svc_file.gestes_a_avertir(db, maintenant)
            for user_id, gestes in _grouper_par_compte(a_avertir).items():
                svc_relances.avertir(db, user_id, gestes, maintenant=maintenant)

            # [CA3, CA18] Puis périmer, et DIRE ce qui a été vidé. Rien ne
            # disparaît en silence : un geste préparé et jamais confirmé doit
            # laisser une trace de son sort.
            perimes = svc_file.gestes_perimes(db, maintenant)
            for user_id, gestes in _grouper_par_compte(perimes).items():
                vides = [geste for geste in gestes if svc_file.perimer(geste, maintenant)]
                if vides:
                    svc_relances.notifier_purge(db, user_id, vides)

            # [CA15, CA16] Enfin relancer, pour les seules files non vides.
            for user_id in svc_file.comptes_avec_file(db, maintenant):
                svc_relances.relancer(db, user_id, maintenant=maintenant)
    except Exception as e:  # noqa: BLE001 — un job de fond ne tue jamais le bot
        log.error("❌ JOB FILE GESTES : %s", e)


def _grouper_par_compte(gestes: list) -> dict:
    """Les gestes d'un même compte partent dans UN message, pas un par geste."""
    groupes: dict = {}
    for geste in gestes:
        groupes.setdefault(geste.user_id, []).append(geste)
    return groupes
