"""
app/services/relances_file.py — Inviter à traiter sa file, et savoir se taire [US-224]
--------------------------------------------------------------------------------
Le compagnon **invite** à traiter la file ; il ne l'exécute jamais de lui-même
(CA14). Tout ce module tient dans cette phrase, et dans les bornes qu'elle
impose — parce que la relance est le risque principal de l'US : mal réglée,
elle transforme un service en harcèlement, et le jardinier coupe tout.

La règle retenue donne, au pire, pour une file jamais traitée :

| Quand | Quoi | Combien |
|---|---|---|
| Premier dépôt sur file vide | une invitation | 1 (CA14) |
| Tant que la file n'est pas vide | une relance par demi-journée, sur deux créneaux (matin, fin d'après-midi) | 5 au plus (CA15) |
| Au bout de 3 jours | plus rien | — (CA16) |
| 4 h avant la purge d'un geste | un avertissement, ton distinct | 1 par geste (CA17) |
| À la purge | ce qui a été vidé, et ce que ça décrivait | 1 (CA18) |

Soit **7 messages sur trois jours** dans le pire cas — borné, mais à mesurer à
l'usage avant d'être figé.

Trois garde-fous, non négociables :

* **Jamais à l'heure du dépôt** (CA15) : deux créneaux fixes, matin et fin
  d'après-midi. Un geste déposé à 15 h ne réveille personne à 3 h du matin.
* **Toute activité remet le compteur à zéro** (CA19) — confirmation, abandon,
  simple consultation. Elle ne rallonge en revanche JAMAIS la vie d'un geste :
  la péremption court depuis le dépôt, et rien ne la repousse.
* **La coupure est la soupape** (CA20), et elle ne vide pas la file : les gestes
  restent, les invitations cessent, l'avertissement et la notification de purge
  aussi. Elle se dit et se défait depuis le compagnon, et elle est rappelée sur
  chaque relance — elle ne doit jamais être difficile à trouver.

⚠️ L'envoi suppose une conversation **déjà ouverte par le jardinier** : Telegram
interdit au bot de parler le premier tant que « Démarrer » n'a pas été pressé.
Un compte lié mais jamais démarré ne recevra aucune relance, sans que rien ne le
signale côté serveur (déjà décrit dans `compagnon-telegram.md`).
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.services import file_gestes as svc_file
from app.services import telegram_notify as svc_telegram_notify
from database.models import FileGestesReglage, GesteIntention, Potager, User

log = logging.getLogger("potager")

#: [CA15] « Semestriel » au sens propre du terme — toutes les demi-journées.
#: Deux créneaux quotidiens plausibles, heure locale du serveur : le matin, où
#: l'on prépare sa journée, et la fin d'après-midi, où l'on rentre du jardin.
CRENEAUX_RELANCE: tuple[int, ...] = (9, 18)

#: [CA16] Les relances s'arrêtent au bout de trois jours, qu'elles aient été
#: suivies d'effet ou non. Passé ce délai, le compagnon se tait jusqu'à
#: l'avertissement du CA17.
DUREE_RELANCES_JOURS = 3

#: Deux relances dans le même créneau seraient deux bulles pour une seule
#: demi-journée. La borne est large (le job peut tourner à l'heure près).
_ECART_MINIMAL_HEURES = 6

#: [CA5] Les deux seules actions du niveau 1 — et aucune n'enregistre quoi que
#: ce soit. C'est ce qui rend ce niveau sûr à poser dans une notification.
CB_COMMENCER = "file:commencer"
CB_COUPER = "file:couper"
CB_REPRENDRE = "file:reprendre"

#: [CA5] Le détail des trois premiers gestes, puis « et N autres ». Trois, parce
#: qu'au-delà la notification devient un écran, et qu'un écran se consulte —
#: c'est justement ce que le niveau 1 permet de faire quand on le veut.
NB_GESTES_DETAILLES = 3


# ══════════════════════════════════════════════════════════════════════════════
# Le réglage d'un compte
# ══════════════════════════════════════════════════════════════════════════════
def reglage(db: Session, user_id: int) -> FileGestesReglage:
    """La ligne de réglage de ce compte — créée à la demande, jamais en amont.

    Un compte qui n'a jamais rien déposé n'a pas de ligne : la table ne porte
    que ce qui a eu lieu.
    """
    ligne = (
        db.query(FileGestesReglage)
        .filter(FileGestesReglage.user_id == user_id)
        .first()
    )
    if ligne is None:
        ligne = FileGestesReglage(user_id=user_id, relances_actives=True)
        db.add(ligne)
        db.commit()
        db.refresh(ligne)
    return ligne


def relances_actives(db: Session, user_id: int) -> bool:
    """[CA20] Ce compte accepte-t-il d'être relancé ?"""
    return bool(reglage(db, user_id).relances_actives)


def definir_relances(db: Session, user_id: int, actives: bool) -> FileGestesReglage:
    """[CA20] Couper les relances — ou les reprendre. La file n'est pas touchée."""
    ligne = reglage(db, user_id)
    ligne.relances_actives = bool(actives)
    db.commit()
    log.info(
        "[US-224 / CA20] Relances %s pour user_id=%s",
        "reprises" if actives else "coupées", user_id,
    )
    return ligne


def noter_activite(db: Session, user_id: int, maintenant: Optional[datetime] = None) -> None:
    """[CA19] Une activité sur la file remet le compteur de relance à zéro.

    Confirmation, abandon, **simple consultation** : les trois comptent. Le
    jardinier qui vient de regarder sa file sait ce qui l'attend — le lui
    redire deux heures plus tard n'apporte rien.

    ⚠️ Ne touche JAMAIS `expire_le` : la péremption du CA3 court depuis le
    dépôt, et une file entretenue en permanence ne doit pas devenir immortelle.
    """
    ligne = reglage(db, user_id)
    ligne.derniere_activite_le = maintenant or datetime.utcnow()
    db.commit()


# ══════════════════════════════════════════════════════════════════════════════
# [CA5] Ce que le niveau 1 dit, et les deux boutons qu'il porte
# ══════════════════════════════════════════════════════════════════════════════
def _nom_potager(db: Session, potager_id: int) -> str:
    potager = db.query(Potager).filter(Potager.id == potager_id).first()
    return potager.nom if potager else f"potager {potager_id}"


def texte_file(db: Session, gestes: list[GesteIntention], entete: str) -> str:
    """Le nombre de gestes en attente, le détail des trois premiers, « et N autres ».

    [CA13] Quand la file couvre plusieurs potagers, les lignes sont groupées par
    potager : un geste s'enregistre dans le potager de son dépôt, et le
    jardinier doit pouvoir le voir avant de commencer.
    """
    nb = len(gestes)
    lignes = [entete, ""]
    groupes = svc_file.par_potager(gestes)
    multi = len(groupes) > 1

    detailles = 0
    for potager_id, gestes_du_potager in groupes.items():
        if multi:
            lignes.append(f"🌻 {_nom_potager(db, potager_id)}")
        for geste in gestes_du_potager:
            if detailles >= NB_GESTES_DETAILLES:
                break
            lignes.append(f"• {svc_file.libelle_court(geste)}")
            detailles += 1
        if detailles >= NB_GESTES_DETAILLES:
            break

    reste = nb - detailles
    if reste > 0:
        lignes.append(f"… et {reste} autre{'s' if reste > 1 else ''}")
    return "\n".join(lignes)


def boutons_file(relances_coupees: bool = False) -> list[list[tuple]]:
    """[CA5] Deux actions, et aucune n'écrit quoi que ce soit.

    Des BOUTONS, pas des commandes à retaper : une invitation qui se termine par
    « envoyez /gestes pour les traiter » perd l'essentiel de son intérêt.
    """
    seconde = (
        ("🔔 Reprendre les rappels", CB_REPRENDRE) if relances_coupees
        else ("🔕 Ne plus me relancer", CB_COUPER)
    )
    return [[("▶️ Commencer", CB_COMMENCER)], [seconde]]


# ══════════════════════════════════════════════════════════════════════════════
# [CA14, CA15] Inviter, puis relancer
# ══════════════════════════════════════════════════════════════════════════════
def _chat_id(db: Session, user_id: int) -> Optional[int]:
    utilisateur = db.query(User).filter(User.id == user_id).first()
    return getattr(utilisateur, "telegram_chat_id", None)


def compagnon_joignable(db: Session, user_id: int) -> bool:
    """[CA21] Ce compte a-t-il un compagnon à qui parler ?

    Ce que l'application demande pour savoir s'il faut inviter à l'activer —
    sans jamais bloquer le dépôt. Une conversation liée mais jamais démarrée
    répond `True` ici : Telegram ne laisse pas le serveur le savoir, et c'est
    un point de vigilance connu de la fiche `compagnon-telegram.md`.
    """
    return _chat_id(db, user_id) is not None


def _envoyer_niveau_1(
    db: Session, user_id: int, chat_id: int, gestes: list[GesteIntention],
    entete: str, remplacer: Optional[int],
) -> Optional[int]:
    """Poste (ou remplace) le niveau 1, et rend l'identifiant du message obtenu.

    [CA20] Chaque relance remplace la précédente. Quand l'édition échoue — le
    jardinier a supprimé la bulle, ou Telegram refuse un contenu identique — on
    repart d'un envoi neuf : mieux vaut une bulle de plus qu'une relance muette.
    """
    texte = texte_file(db, gestes, entete)
    boutons = boutons_file()
    if remplacer is not None and svc_telegram_notify.editer_message(
        chat_id, remplacer, texte, boutons,
    ):
        return remplacer
    return svc_telegram_notify.envoyer(chat_id, texte, boutons)


def inviter_si_premier_depot(
    db: Session, user_id: int, depot: "svc_file.Depot",
    maintenant: Optional[datetime] = None,
) -> bool:
    """[CA14] Une invitation au premier dépôt sur une file vide, et une seule.

    Les gestes déposés à la suite pendant la même session de préparation n'en
    déclenchent aucune autre : c'est `depot.file_etait_vide` qui le dit, et
    c'est un constat fait au dépôt, pas un état relu plus tard.

    Rend `True` si une invitation est partie. Ne lève jamais : un compagnon
    injoignable ne doit pas faire échouer un dépôt (CA21).
    """
    if not depot.file_etait_vide:
        return False
    if not relances_actives(db, user_id):
        return False
    chat_id = _chat_id(db, user_id)
    if chat_id is None:
        # [CA21] Sans compagnon activé, le dépôt reste possible et la file se
        # remplit. C'est l'application qui invitera à activer, pas nous.
        log.info("[US-224 / CA21] Dépôt sans compagnon activé : user_id=%s", user_id)
        return False

    gestes = svc_file.lister_en_attente(db, user_id, maintenant=maintenant)
    instant = maintenant or datetime.utcnow()
    message_id = _envoyer_niveau_1(
        db, user_id, chat_id, gestes,
        "🌱 *Un geste vous attend* — préparé depuis l'application, pas encore enregistré.",
        remplacer=None,
    )
    ligne = reglage(db, user_id)
    ligne.derniere_invitation_le = instant
    ligne.derniere_relance_le = instant
    ligne.message_relance_id = message_id
    db.commit()
    log.info(
        "[US-224 / CA14] Invitation envoyée : user_id=%s (%s geste(s), message_id=%s)",
        user_id, len(gestes), message_id,
    )
    return message_id is not None


def _ancre_relances(ligne: FileGestesReglage, gestes: list[GesteIntention]) -> datetime:
    """Depuis quand compte-t-on les trois jours de relance ? [CA16, CA19]

    La dernière activité si elle existe (une consultation remet le compteur à
    zéro), sinon la première invitation, sinon le dépôt le plus ancien — le cas
    d'une file remplie alors que les relances étaient coupées.
    """
    candidats = [d for d in (ligne.derniere_activite_le, ligne.derniere_invitation_le) if d]
    if candidats:
        return max(candidats)
    return min(geste.cree_le for geste in gestes)


def doit_relancer(
    ligne: FileGestesReglage, gestes: list[GesteIntention], maintenant: datetime,
) -> bool:
    """[CA15, CA16, CA19, CA20] Ce compte doit-il être relancé MAINTENANT ?

    Quatre conditions, toutes nécessaires : des gestes en attente, des relances
    non coupées, un créneau, et moins de trois jours depuis la dernière
    activité. Aucune n'est une préférence : chacune ferme une façon documentée
    de rendre le compagnon insupportable.
    """
    if not gestes or not ligne.relances_actives:
        return False
    if maintenant.hour not in CRENEAUX_RELANCE:
        return False
    if ligne.derniere_relance_le is not None and (
        maintenant - ligne.derniere_relance_le < timedelta(hours=_ECART_MINIMAL_HEURES)
    ):
        return False
    return maintenant - _ancre_relances(ligne, gestes) < timedelta(days=DUREE_RELANCES_JOURS)


def relancer(
    db: Session, user_id: int, maintenant: Optional[datetime] = None,
) -> bool:
    """[CA15, CA20] Repose l'invitation, en remplaçant la précédente.

    Rend `True` si une relance est partie. Le calendrier est décidé par
    `doit_relancer`, jamais ici : cette fonction envoie, elle ne juge pas.
    """
    instant = maintenant or datetime.utcnow()
    gestes = svc_file.lister_en_attente(db, user_id, maintenant=instant)
    ligne = reglage(db, user_id)
    if not doit_relancer(ligne, gestes, instant):
        return False
    chat_id = _chat_id(db, user_id)
    if chat_id is None:
        return False

    nb = len(gestes)
    entete = (
        f"🌱 *{nb} geste{'s' if nb > 1 else ''} en attente* — préparé"
        f"{'s' if nb > 1 else ''} depuis l'application, pas encore enregistré"
        f"{'s' if nb > 1 else ''}."
    )
    message_id = _envoyer_niveau_1(
        db, user_id, chat_id, gestes, entete, remplacer=ligne.message_relance_id,
    )
    ligne.derniere_relance_le = instant
    ligne.message_relance_id = message_id
    db.commit()
    log.info(
        "[US-224 / CA15] Relance envoyée : user_id=%s (%s geste(s), message_id=%s)",
        user_id, nb, message_id,
    )
    return message_id is not None


# ══════════════════════════════════════════════════════════════════════════════
# [CA17, CA18] La fin de vie d'un geste — ce qui n'a pas de seconde chance
# ══════════════════════════════════════════════════════════════════════════════
def texte_avertissement(gestes: list[GesteIntention]) -> str:
    """[CA17] Ton distinct d'une relance ordinaire : il annonce une PERTE.

    Il nomme les gestes concernés — pas un compte, des gestes : « 2 gestes vont
    être vidés » ne dit pas au jardinier s'il tient à les garder.
    """
    lignes = [
        "⏳ *Dernière occasion* — ces gestes préparés vont être vidés dans "
        f"{svc_file.DELAI_AVERTISSEMENT_HEURES} heures, sans avoir été enregistrés :",
        "",
    ]
    lignes += [f"• {svc_file.libelle_court(geste)}" for geste in gestes]
    lignes.append("")
    lignes.append("Traitez-les maintenant si vous y tenez.")
    return "\n".join(lignes)


def texte_purge(gestes: list[GesteIntention]) -> str:
    """[CA18] Ce qui a été vidé, et ce que cela décrivait.

    Rien ne disparaît en silence : un geste préparé et jamais confirmé doit
    laisser une trace de son sort, sans quoi le jardinier croira l'avoir
    enregistré. La phrase finale est là pour ça, et elle est explicite.
    """
    nb = len(gestes)
    lignes = [
        f"🗑 *{nb} geste{'s' if nb > 1 else ''} préparé{'s' if nb > 1 else ''} "
        f"{'ont' if nb > 1 else 'a'} été vidé{'s' if nb > 1 else ''}* "
        "au bout de trois jours :",
        "",
    ]
    lignes += [f"• {svc_file.libelle_court(geste)}" for geste in gestes]
    lignes.append("")
    lignes.append("⚠️ Rien n'a été enregistré. Relancez-les depuis l'application si besoin.")
    return "\n".join(lignes)


def avertir(
    db: Session, user_id: int, gestes: list[GesteIntention],
    maintenant: Optional[datetime] = None,
) -> bool:
    """[CA17, CA20] L'avertissement des quatre heures — muet si les relances sont coupées."""
    if not gestes or not relances_actives(db, user_id):
        return False
    chat_id = _chat_id(db, user_id)
    if chat_id is None:
        return False
    envoye = svc_telegram_notify.envoyer(
        chat_id, texte_avertissement(gestes), boutons_file(),
    ) is not None
    if envoye:
        for geste in gestes:
            svc_file.marquer_averti(geste, maintenant=maintenant)
        log.info(
            "[US-224 / CA17] Avertissement envoyé : user_id=%s (%s geste(s))",
            user_id, len(gestes),
        )
    return envoye


def notifier_purge(db: Session, user_id: int, gestes: list[GesteIntention]) -> bool:
    """[CA18] Dire ce qui a été vidé — la seule notification sans seconde chance.

    ⚠️ L'envoi sortant est best-effort : il n'échoue jamais bruyamment, un
    message perdu l'est sans bruit. Acceptable pour une relance — il y en aura
    une autre — mais pas pour celle-ci, dont la perte produit exactement le
    malentendu que le CA18 veut éviter. L'échec est donc journalisé en
    `warning`, et l'information est portée AUSSI par l'application : les gestes
    périmés y restent visibles comme tels (`file_gestes.lister_sortis_recents`)
    jusqu'à ce que le jardinier les acquitte.

    Envoyée même quand les relances sont coupées ? Non : le CA20 le dit
    explicitement — couper arrête aussi l'avertissement et cette notification.
    C'est la contrepartie assumée de la coupure, et l'application reste là.
    """
    if not gestes:
        return False
    if not relances_actives(db, user_id):
        log.info(
            "[US-224 / CA20] Purge silencieuse (relances coupées) : user_id=%s, %s geste(s) — "
            "l'application reste seule à le dire", user_id, len(gestes),
        )
        return False
    chat_id = _chat_id(db, user_id)
    if chat_id is None:
        return False
    if svc_telegram_notify.envoyer(chat_id, texte_purge(gestes)) is not None:
        log.info("[US-224 / CA18] Purge annoncée : user_id=%s (%s geste(s))", user_id, len(gestes))
        return True
    log.warning(
        "[US-224 / CA18] Notification de purge PERDUE pour user_id=%s (%s geste(s)) — "
        "l'information ne passera plus que par l'application",
        user_id, len(gestes),
    )
    return False
