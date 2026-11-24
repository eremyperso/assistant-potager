"""
app/services/compagnon/fil.py — Le fil complet de la conversation, borné et compacté [US-343]
==============================================================================================
Ce que la boucle à capacités (US-342, `compagnon/boucle.py`) relit à chaque tour : la conversation du
jardinier dans CE potager, commune à Telegram et à la PWA (principe P4, §4.4 de
`ARCHITECTURE_COMPAGNON_CAPACITES.md`).

* **Messages complets** (CA1) : un tour de la boucle garde la phrase, les appels d'outils avec leurs arguments,
  les résultats et la réponse (`echanges_conversation.messages`, migration_v81). Un échange de l'ancien moteur
  (Telegram, avant la bascule) se relit en deux messages : la phrase et la réponse.
* **Résultats datés** (CA2) : chaque résultat d'outil commence par « [lu le JJ/MM HH:MM] ». Le prompt demande de
  relire une donnée de plus de quelques minutes avant d'écrire ; le validateur, lui, relit toujours en base
  (`gestes_conversation.controler` à la proposition, `echange_pwa.confirmer` à l'exécution).
* **Borné** (CA3, arbitrage A3) : les 12 derniers tours de la séance en entier ; au-delà, les plus anciens sont
  compactés PAR BLOCS DE 6 en un résumé des faits établis (culture, parcelle, date, quantité, ce qui restait en
  suspens). Le résumé est calculé par le code, à partir de ce qui a été dit et lu : il n'invente rien et ne coûte
  aucun appel.
* **Préfixe stable** (CA4) : un message gardé ne change plus jamais (date et troncature sont figées à
  l'écriture) ; la frontière de compaction n'avance que par blocs. Le cache du fournisseur sert donc le préfixe
  (prompt, outils, résumé, début du fil) d'un tour à l'autre.
* **Un fil par jardinier et par potager** (CA5) : la lecture filtre sur les deux ; changer de potager actif ouvre
  un autre fil.
* **Reprise le lendemain** (CA6) : une pause de plus de `COMPAGNON_FIL_PAUSE_H` heures clôt la séance ; la
  suivante repart sur le seul résumé de la séance close, tant qu'elle a moins de `COMPAGNON_FIL_REPRISE_H` heures.

Règle de troncature (CA4) : un résultat d'outil de plus de `RESULTAT_MAX_CARACTERES` caractères est coupé à
cette longueur, suivi de « … [tronqué : N caractères, relis l'outil pour la suite] ». Elle s'applique une fois, à
l'écriture : le modèle lit au tour même ce qu'il relira aux tours suivants.

Données personnelles : le fil contient des textes du jardinier ; il vit dans `echanges_conversation`, purgé à
30 jours (`conversations.purger`, RGPD US-132).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app import config
from app.services.context import TenantContext

log = logging.getLogger("potager")

#: [CA3] Les derniers tours gardés en entier (arbitrage A3).
TOURS_COMPLETS = config.COMPAGNON_FIL_TOURS
#: [CA4] La frontière de compaction avance par blocs : le préfixe reste stable entre deux blocs.
BLOC_COMPACTION = 6
#: [CA6] Une pause plus longue clôt la séance ; la séance close n'est relue qu'en résumé…
PAUSE = timedelta(hours=config.COMPAGNON_FIL_PAUSE_H)
#: … tant qu'elle date de moins de ce délai (« reprise le lendemain »).
REPRISE = timedelta(hours=config.COMPAGNON_FIL_REPRISE_H)
#: [CA4] La règle de troncature d'un résultat d'outil.
RESULTAT_MAX_CARACTERES = 6000
#: Au plus ce nombre d'échanges lus en base pour bâtir le fil (largement au-delà d'une séance).
LECTURE_MAX = 120
#: Dans le résumé, une phrase ou une réponse est coupée à cette longueur.
LONGUEUR_RESUME = 160

#: Les arguments d'outil qui disent un fait établi, et leur libellé dans le résumé (CA3).
_FAITS = (("culture", "culture"), ("variete", "variété"), ("parcelle", "parcelle"), ("date", "date"),
          ("quantite", "quantité"), ("type", "geste"))

ENTETE_RESUME = (
    "\nPlus tôt dans cette conversation (résumé des faits établis ; une donnée lue alors se relit avant "
    "d'écrire) :"
)


# ═════════════════════════════════════════════════════════════════════════════
# Un tour, tel que le fil le relit
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class TourFil:
    """Un échange de la conversation : la phrase, la réponse et, pour la boucle à capacités, les messages."""
    texte_jardinier: str
    texte_compagnon: str
    cree_le: datetime
    messages: Optional[tuple[dict, ...]] = None
    canal: str = ""
    proposition_id: Optional[int] = None
    id: Optional[int] = None

    def en_messages(self) -> list[dict]:
        """[CA1] Les messages du tour ; un échange de l'ancien moteur devient phrase + réponse."""
        if self.messages:
            return [dict(m) for m in self.messages]
        sortie: list[dict] = []
        if self.texte_jardinier:
            sortie.append({"role": "user", "content": self.texte_jardinier})
        if self.texte_compagnon:
            sortie.append({"role": "assistant", "content": self.texte_compagnon})
        return sortie if len(sortie) == 2 else []  # un message seul déséquilibrerait le fil


@dataclass(frozen=True)
class Fil:
    """Ce que la boucle relit : le résumé des tours compactés (ou vide) et les messages des tours complets."""
    resume: str = ""
    messages: tuple[dict, ...] = ()
    tours_complets: tuple[TourFil, ...] = ()
    tours_compactes: tuple[TourFil, ...] = ()

    @property
    def vide(self) -> bool:
        return not self.resume and not self.messages


# ═════════════════════════════════════════════════════════════════════════════
# Règles pures : datation, troncature, sélection, compaction
# ═════════════════════════════════════════════════════════════════════════════
def heure_locale(instant_utc: datetime) -> datetime:
    """Un instant UTC naïf (celui des tables) à l'heure du jardinier (Europe/Paris), naïf."""
    try:
        from zoneinfo import ZoneInfo

        return instant_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/Paris")).replace(tzinfo=None)
    except Exception:  # noqa: BLE001 — sans base de fuseaux, l'heure UTC reste lisible
        return instant_utc


def date_de_lecture(instant: datetime) -> str:
    """« 14/11 10:03 » ; `instant` est déjà à l'heure du jardinier."""
    return instant.strftime("%d/%m %H:%M")


def tronquer_resultat(texte: str) -> str:
    """[CA4] La règle écrite : au plus `RESULTAT_MAX_CARACTERES` caractères, puis une mention."""
    if len(texte) <= RESULTAT_MAX_CARACTERES:
        return texte
    return (texte[:RESULTAT_MAX_CARACTERES]
            + f"… [tronqué : {len(texte)} caractères, relis l'outil pour la suite]")


def contenu_d_outil(resultat: str, lu_le: datetime) -> str:
    """[CA2, CA4] Le contenu d'un message `tool` : daté (`lu_le` à l'heure du jardinier), puis tronqué. Figé :
    on ne le recalcule jamais."""
    return f"[lu le {date_de_lecture(lu_le)}] {tronquer_resultat(resultat)}"


def _seance(tours: list[TourFil], maintenant: datetime) -> tuple[list[TourFil], list[TourFil]]:
    """[CA6] (séance close à résumer, séance en cours) : la séance en cours remonte depuis le dernier tour tant
    que deux tours se suivent à moins de `PAUSE` ; elle est close si son dernier tour a plus de `PAUSE`."""
    recents = [t for t in tours if maintenant - t.cree_le <= REPRISE]
    if not recents:
        return [], []
    debut = len(recents)
    suivant = maintenant
    for i in range(len(recents) - 1, -1, -1):
        if suivant - recents[i].cree_le > PAUSE:
            break
        debut = i
        suivant = recents[i].cree_le
    return recents[:debut], recents[debut:]


def selectionner(tours: list[TourFil], maintenant: datetime) -> tuple[list[TourFil], list[TourFil]]:
    """[CA3, CA4, CA6] (tours à compacter, tours gardés en entier), du plus ancien au plus récent.

    Dans la séance en cours, au-delà de `TOURS_COMPLETS`, les plus anciens sont compactés par blocs de
    `BLOC_COMPACTION` : de 13 à 18 tours, 6 compactés ; de 19 à 24, 12 ; etc. La séance close est toute résumée."""
    close, en_cours = _seance(sorted(tours, key=lambda t: (t.cree_le, t.id or 0)), maintenant)
    exces = len(en_cours) - TOURS_COMPLETS
    a_compacter = 0 if exces <= 0 else -(-exces // BLOC_COMPACTION) * BLOC_COMPACTION
    return close + en_cours[:a_compacter], en_cours[a_compacter:]


def _court(texte: str) -> str:
    texte = " ".join((texte or "").split())
    return texte if len(texte) <= LONGUEUR_RESUME else texte[:LONGUEUR_RESUME].rstrip() + "…"


def _appels_du_tour(tour: TourFil) -> list[dict]:
    """Les arguments des appels d'outils du tour (messages `assistant` à `tool_calls`)."""
    arguments: list[dict] = []
    for message in tour.messages or ():
        for appel in message.get("tool_calls") or ():
            try:
                valeurs = json.loads((appel.get("function") or {}).get("arguments") or "{}")
            except (TypeError, ValueError):
                continue
            if isinstance(valeurs, dict):
                arguments.append(valeurs)
    return arguments


def faits_etablis(tours: list[TourFil]) -> dict[str, list[str]]:
    """[CA3] Les faits dits ou lus pendant ces tours, par nature, dans l'ordre et sans doublon : ce que les
    appels d'outils ont porté (culture, parcelle, date, quantité, geste)."""
    faits: dict[str, list[str]] = {}
    for tour in tours:
        for valeurs in _appels_du_tour(tour):
            for cle, libelle in _FAITS:
                valeur = valeurs.get(cle)
                if valeur in (None, "", [], {}):
                    continue
                if cle == "quantite" and valeurs.get("unite"):
                    valeur = f"{valeur} {valeurs['unite']}"
                texte = str(valeur)
                if texte not in faits.setdefault(libelle, []):
                    faits[libelle].append(texte)
    return {k: v for k, v in faits.items() if v}


def resumer(tours: list[TourFil]) -> str:
    """[CA3] Le résumé des tours compactés : un repère par tour (date, phrase, réponse), les faits établis et ce
    qui restait en suspens. Le code l'écrit à partir de ce qui a été dit et lu : rien n'y est inventé."""
    if not tours:
        return ""
    lignes = [ENTETE_RESUME]
    for tour in tours:
        if tour.texte_jardinier or tour.texte_compagnon:
            lignes.append(f"- {date_de_lecture(heure_locale(tour.cree_le))} — jardinier : « {_court(tour.texte_jardinier)} »"
                          f" ; toi : « {_court(tour.texte_compagnon)} »")
    faits = faits_etablis(tours)
    if faits:
        lignes.append("Faits établis : " + " ; ".join(f"{k} : {', '.join(v[-5:])}" for k, v in faits.items()) + ".")
    dernier = tours[-1].texte_compagnon.strip()
    if dernier.endswith("?"):
        lignes.append(f"Restait en suspens : « {_court(dernier)} »")
    return "\n".join(lignes)


def construire(tours: list[TourFil], maintenant: Optional[datetime] = None) -> Fil:
    """[CA1, CA3, CA6] Le fil que la boucle relit, à partir des tours lus (dans n'importe quel ordre)."""
    instant = maintenant or datetime.utcnow()
    compactes, complets = selectionner(list(tours), instant)
    messages: list[dict] = []
    for tour in complets:
        messages.extend(tour.en_messages())
    return Fil(resume=resumer(compactes), messages=tuple(messages), tours_complets=tuple(complets),
               tours_compactes=tuple(compactes))


# ═════════════════════════════════════════════════════════════════════════════
# En base : `echanges_conversation`, par jardinier ET par potager (CA5)
# ═════════════════════════════════════════════════════════════════════════════
def _tour_de(ligne: Any) -> TourFil:
    messages = ligne.messages if isinstance(ligne.messages, list) else None
    return TourFil(
        texte_jardinier=ligne.texte_jardinier or "", texte_compagnon=ligne.texte_compagnon or "",
        cree_le=ligne.cree_le, messages=tuple(messages) if messages else None, canal=ligne.canal or "",
        proposition_id=ligne.proposition_id, id=ligne.id,
    )


def lire_tours(ctx: TenantContext, maintenant: Optional[datetime] = None) -> list[TourFil]:
    """[CA5] Les échanges récents de CE jardinier dans CE potager, du plus ancien au plus récent.
    Une mémoire illisible rend un fil vide : la phrase passe, sans contexte."""
    from app.services.compagnon.conversations import _session
    from database.models import EchangeConversation

    instant = maintenant or datetime.utcnow()
    try:
        with _session(ctx.potager_id) as db:
            lignes = (
                db.query(EchangeConversation)
                .filter(
                    EchangeConversation.user_id == ctx.user_id,
                    EchangeConversation.potager_id == ctx.potager_id,
                    EchangeConversation.cree_le <= instant,
                    EchangeConversation.cree_le >= instant - REPRISE,
                )
                .order_by(EchangeConversation.cree_le.desc(), EchangeConversation.id.desc())
                .limit(LECTURE_MAX)
                .all()
            )
            return [_tour_de(ligne) for ligne in reversed(lignes)]
    except Exception:  # noqa: BLE001 — la mémoire ne casse jamais la réponse
        log.exception("[US-343] Fil illisible (user_id=%s potager_id=%s) — tour sans contexte",
                      ctx.user_id, ctx.potager_id)
        return []


def charger(ctx: TenantContext, maintenant: Optional[datetime] = None) -> Fil:
    """Le fil de ce jardinier dans ce potager, prêt à relire."""
    instant = maintenant or datetime.utcnow()
    fil = construire(lire_tours(ctx, instant), instant)
    log.info("[US-343] Fil : %s tour(s) complet(s), %s compacté(s) (user_id=%s potager_id=%s)",
             len(fil.tours_complets), len(fil.tours_compactes), ctx.user_id, ctx.potager_id)
    return fil


def noter_tour(ctx: TenantContext, phrase: str, texte: str, messages: list[dict], *, canal: str,
               outils: tuple[str, ...] = (), proposition_id: Optional[int] = None,
               contexte: Optional[dict] = None, maintenant: Optional[datetime] = None) -> None:
    """[CA1] Garde le tour complet ; Telegram et l'ancien moteur en relisent la phrase et la réponse."""
    from app.services.compagnon import conversations as svc_conversations

    svc_conversations.noter(ctx, phrase, texte, canal=canal, outils=outils, proposition_id=proposition_id,
                            contexte=contexte, messages=messages, maintenant=maintenant)


@dataclass
class EtatCarte:
    """Une carte proposée plus tôt dans le fil, et ce qu'elle est devenue."""
    proposition_id: int
    resume: str
    etat: str
    dit: str = ""
    traite_le: Optional[datetime] = None


def etat_des_cartes(ctx: TenantContext, fil: Fil) -> list[EtatCarte]:
    """Les propositions laissées par les tours du fil, relues en base : le modèle sait si le jardinier a confirmé
    une carte au bouton (ici ou dans Telegram) sans qu'on le lui dise. Rien ne lève."""
    from app.services.compagnon import gestes_conversation as svc_gestes_dits
    from app.services.compagnon import propositions as svc_propositions
    from app.services.compagnon import deux_canaux as svc_deux_canaux

    ids = []
    for tour in (*fil.tours_compactes, *fil.tours_complets):
        if tour.proposition_id is not None and tour.proposition_id not in ids:
            ids.append(tour.proposition_id)
    etats: list[EtatCarte] = []
    for pid in ids[-5:]:
        try:
            try:
                geste = svc_gestes_dits.par_id(ctx, pid)
                resume = " ; ".join(svc_gestes_dits.resume(i) for i in geste.items)
                etat, canal, le = geste.etat, geste.traite_canal, geste.traite_le
            except svc_gestes_dits.GesteIntrouvableError:
                proposition = svc_propositions.par_id(pid, ctx.user_id, ctx.potager_id)
                if proposition is None:
                    continue
                commande = proposition.commande
                resume = (" ; ".join(e.commande_equivalente() for e in commande.etapes)
                          if hasattr(commande, "etapes") else commande.commande_equivalente())
                etat, canal, le = proposition.etat, proposition.traite_canal, proposition.traite_le
            dit = svc_deux_canaux.texte_etat(etat, canal, le) or etat.replace("_", " ")
            etats.append(EtatCarte(pid, resume, etat, dit, le))
        except Exception:  # noqa: BLE001 — une carte illisible ne prive pas le tour de sa réponse
            log.exception("[US-343] État de la carte %s illisible", pid)
    return etats


def note_des_cartes(etats: list[EtatCarte], depuis: Optional[datetime]) -> str:
    """La note que la boucle joint à la phrase : les cartes du fil traitées DEPUIS le dernier tour (au bouton,
    ici ou dans Telegram). Seule la nouvelle se dit : une carte toujours en attente est déjà dans le fil."""
    nouvelles = [e for e in etats if e.traite_le is not None and (depuis is None or e.traite_le > depuis)]
    if not nouvelles:
        return ""
    lignes = [f"carte n°{e.proposition_id} ({e.resume}) : {e.dit}" for e in nouvelles]
    return "[Lu dans l'application depuis ton dernier message] " + " · ".join(lignes)
