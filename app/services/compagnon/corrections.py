"""
app/services/compagnon/corrections.py — Corriger ou annuler par une phrase ce qui vient d'être fait [US-262]
=============================================================================================================
« En fait c'était 3 rangs », « annule le dernier semis » : la phrase vise une ACTION
MENÉE (US-261), pas un nouveau geste. L'agent appelle `corriger_action(ref, champs)` ou
`annuler_action(ref)` ; ce module en fait une PROPOSITION avec son récapitulatif
avant → après (CA1), que le jardinier confirme comme toute autre. Rien ne s'exécute
ici avant cette confirmation, et l'exécution passe par le service de la nature
concernée : `evenements.corriger_evenement` / `evenements.supprimer_evenement` (CA2).

Ce qui se corrige : un GESTE (cible `evenement`) encore présent dans le carnet, et une
PARCELLE qu'on vient de créer ou de modifier — la correction devient alors la commande
`/parcelle modifier`, avec sa ligne avant → après (`CLE_AVANT_APRES`). Une correction ne vise
que les candidates auxquelles ses champs s'appliquent : « 8 rangs » ne désigne pas un arrosage.

La désignation est décidée par le CODE quand la phrase la porte :

* « le dernier semis », « ce que je viens de noter » → la plus récente, parmi celles
  que la phrase nomme (culture, type de geste) ou parmi toutes ;
* une annulation qui nomme une culture ou un geste vise l'action nommée, jamais une autre ;
* deux candidates sans désignation → le compagnon demande laquelle EN LES NOMMANT (CA4).

Un champ corrigé suit l'ancrage du validateur : un nombre est dit (en chiffres ou en
lettres), une culture ou une variété est dite, une parcelle existe à l'identique.

[CA3] `passe_avant_le_filtre_geste` : pendant 10 minutes après un geste, une phrase de
correction passe à l'agent AVANT le filtre « geste annoncé » ; « annule… » aussi, tant qu'un
geste des 24 h peut l'être.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from app.services.context import TenantContext
from app.services.menu_commandes import TYPE_TEXTE, Argument, FormeCommande
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from database.db import SessionLocal, tenant_scope

log = logging.getLogger("potager")

COMMANDE = "action"
SOUS_CORRIGER = "corriger"
SOUS_ANNULER = "annuler"

#: [CA3] La fenêtre pendant laquelle une phrase de correction passe avant le filtre « geste annoncé ».
DELAI_CORRECTION = timedelta(minutes=10)

#: Le parcours guidé qui fait la même chose sans phrase — rappelé dans le récapitulatif.
COMMANDE_GUIDEE = "/corriger"

_REF = Argument("ref", TYPE_TEXTE, "Quelle action ?",
                description="La référence de l'action menée (A1, A2…)")
_EVENEMENT = Argument("evenement", TYPE_TEXTE, "Quel geste ?", obligatoire=False)

#: [CA1] Deux formes hors du catalogue dictable : elles ne correspondent à aucune commande
#: du bot. Une correction écrit (confirmation) ; une annulation retire un geste du carnet,
#: elle ne se confirme qu'au bouton (US-260 / CA3).
FORME_CORRIGER = FormeCommande(COMMANDE, SOUS_CORRIGER, "Corriger une action", (_REF, _EVENEMENT))
FORME_ANNULER = FormeCommande(COMMANDE, SOUS_ANNULER, "Annuler une action", (_REF, _EVENEMENT),
                              destructrice=True)

#: Les champs d'un geste qu'une phrase peut corriger, et leur type de valeur.
CHAMP_NOMBRE = "nombre"
CHAMP_ENTIER = "entier"
CHAMP_TEXTE = "texte"
CHAMP_PARCELLE = "parcelle"
CHAMP_DATE = "date"
CHAMPS: dict[str, str] = {
    "quantite": CHAMP_NOMBRE,
    "unite": CHAMP_TEXTE,
    "rang": CHAMP_ENTIER,
    "culture": CHAMP_TEXTE,
    "variete": CHAMP_TEXTE,
    "parcelle": CHAMP_PARCELLE,
    "date": CHAMP_DATE,
}
DESCRIPTIONS_CHAMPS: dict[str, str] = {
    "quantite": "La quantité corrigée (nombre de plants, poids, longueur…)",
    "unite": "L'unité de la quantité corrigée (plants, kg, g, ml…)",
    "rang": "Le nombre de rangs corrigé, d'un geste ou d'une parcelle (« c'était 3 rangs » → 3)",
    "culture": "La culture corrigée, telle que dite",
    "variete": "La variété corrigée, telle que dite",
    "parcelle": "La parcelle corrigée, nommée comme dans la liste des parcelles",
    "date": "La date corrigée, au format AAAA-MM-JJ",
}
_LIBELLES = {"quantite": "quantité", "unite": "unité", "rang": "rangs", "culture": "culture",
             "variete": "variété", "parcelle": "parcelle", "date": "date"}

#: [CA3] Ce qui fait d'une phrase une correction de ce qui précède, plutôt qu'un geste nouveau.
_MARQUES_CORRECTION = re.compile(
    r"\b(?:en fait|en vrai|plutot|finalement|au lieu de|(?:je )?me suis trompe\w*|je voulais dire|"
    r"erreur|oups|pardon|rectifi\w*|corrig\w*|annul\w*|c etait|c est pas|ce n est pas|"
    r"ce n etait pas|c etait pas|pas \w+ mais|non c|non ce|non j)\b|^non\b"
)
#: « Annule le dernier semis » n'annonce jamais un semis, quel que soit le délai.
_ANNULER = re.compile(r"\bannul\w*\b")
#: Une annulation demandée : le verbe qui offre `annuler_action`.
_VERBES_ANNULATION = re.compile(r"\b(?:annul\w*|supprim\w*|effac\w*|retir\w*|enlev\w*)\b")
#: « le dernier semis », « ce que je viens de noter » : la plus récente.
_LA_DERNIERE = re.compile(r"\b(?:derni(?:er|ere)s?|je viens de|tout a l heure|a l instant)\b")
#: Un repère de date : sans lui, une date corrigée n'a pas été dite.
_REPERE_DE_DATE = re.compile(
    r"\d|\b(?:hier|avant hier|aujourd hui|veille|lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche|"
    r"janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\b"
)

#: Les racines par lesquelles une phrase nomme un type de geste (« le semis », « j'ai semé »).
_RACINES_GESTE: dict[str, tuple[str, ...]] = {
    "semis": ("semis", "seme", "semer", "sema"),
    "plantation": ("plant",),
    "recolte": ("recolt", "cueill"),
    "arrosage": ("arros",),
    "mise_en_godet": ("godet", "rempot", "repiqu"),
    "paillage": ("paill",),
    "traitement": ("trait",),
    "desherbage": ("desherb",),
    "perte": ("perte", "perdu"),
    "perte_godet": ("perte", "perdu"),
    "vendu": ("vend", "vente"),
    "observation": ("observ",),
    "taille": ("taill",),
    "levee": ("leve",),
    "deplacement": ("deplac",),
}

TEXTE_AUCUNE_ACTION = (
    "Je ne vois aucun geste récent à corriger. Pour un geste plus ancien, passe par /corriger."
)
TEXTE_LAQUELLE = "Laquelle veux-tu {verbe} ? {liste}"


# ═════════════════════════════════════════════════════════════════════════════
# Reconnaître une phrase de correction
# ═════════════════════════════════════════════════════════════════════════════
def _normalise(texte: str) -> str:
    from app.services.interpreteur_commandes import normaliser

    return normaliser(texte or "")[0]


def ressemble_a_une_correction(texte: str) -> bool:
    """[CA3] « En fait c'était 3 rangs », « annule le dernier semis », « non, des carottes »."""
    return bool(_MARQUES_CORRECTION.search(_normalise(texte)))


def passe_avant_le_filtre_geste(texte: str, ctx: TenantContext, maintenant: Optional[datetime] = None) -> bool:
    """[CA3] La phrase va-t-elle à l'agent avant le filtre « geste annoncé » ?

    * une phrase de correction, dans les 10 minutes qui suivent un geste ;
    * une phrase qui ANNULE (« annule le dernier semis »), tant qu'un geste des 24 h peut l'être :
      elle nomme un geste sans en annoncer un, et le filtre l'enverrait au parseur.
    La marque est lue d'abord : elle ne coûte rien, la lecture des actions si.
    """
    if not ressemble_a_une_correction(texte):
        return False
    from app.services.compagnon import actions_menees

    if _ANNULER.search(_normalise(texte)):
        return any(corrigeable(a) for a in actions_menees.recentes(ctx, maintenant=maintenant))
    return action_recente(ctx, maintenant=maintenant)


def demande_une_annulation(texte: str) -> bool:
    """La phrase demande-t-elle de retirer quelque chose ? Alors `annuler_action` est offert."""
    return bool(_VERBES_ANNULATION.search(_normalise(texte)))


def est_correction(commande) -> bool:
    """Une proposition née de `corriger_action` ou d'`annuler_action`."""
    forme = getattr(commande, "forme", None)
    return forme is not None and forme.commande == COMMANDE


#: Ce qu'une action menée corrige : un geste du carnet, ou la fiche d'une parcelle.
CIBLE_GESTE = "evenement"
CIBLE_PARCELLE = "parcelle"


def corrigeable(action) -> bool:
    """Un geste du carnet (cible `evenement`), ou une parcelle créée ou modifiée dont la fiche
    d'après est connue (« passe la planche principal à 6 rangs ») — pas une suppression."""
    if action.cible_type == CIBLE_GESTE:
        return action.cible_id is not None
    return action.cible_type == CIBLE_PARCELLE and bool(action.apres)


def pour_l_agent_plutot_que_le_raccourci(texte: str, ctx: Optional[TenantContext]) -> bool:
    """« Annuler le dernier semis », « corriger mon semis de radis » : la phrase désigne un geste.
    Avec l'agent actif et un geste récent, elle va à l'agent plutôt qu'au raccourci du bot, qui
    proposerait le dernier enregistrement quel qu'il soit. Le mot seul (« annuler ») garde le raccourci."""
    from app.services.compagnon import actions_menees
    from app.services.interpreteur_commandes import _mode_agent

    if ctx is None or len(_mots(texte)) < 2 or _mode_agent() != "actif":
        return False
    return any(corrigeable(a) for a in actions_menees.recentes(ctx))


def action_recente(ctx: TenantContext, maintenant: Optional[datetime] = None,
                   delai: timedelta = DELAI_CORRECTION) -> bool:
    """[CA3] Un geste a-t-il été mené pour ce jardinier, dans ce potager, il y a moins de 10 minutes ?"""
    from app.services.compagnon import actions_menees

    return any(corrigeable(a) for a in actions_menees.recentes(ctx, depuis=delai, maintenant=maintenant))


# ═════════════════════════════════════════════════════════════════════════════
# Les actions candidates, et celle que la phrase désigne
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class Candidate:
    """Une action menée corrigeable, avec sa référence (A1…) et sa cible telle qu'elle est en base."""

    ref: str
    action: object          # actions_menees.Action
    evenement_id: Optional[int]
    valeurs: dict           # l'état ACTUEL : du geste (action, culture, quantité…) ou de la fiche de parcelle
    resume: str
    suites: int = 0         # gestes rattachés à celui-ci (mise en godet d'un semis…)
    cible: str = CIBLE_GESTE
    parcelle: Optional[str] = None   # le nom exact, pour une cible parcelle


def _etat_du_geste(db, event) -> dict:
    from database.models import Parcelle

    nom_parcelle = None
    if event.parcelle_id:
        parcelle = db.get(Parcelle, event.parcelle_id)
        nom_parcelle = parcelle.nom if parcelle is not None else None
    jour = event.date.date() if isinstance(event.date, datetime) else event.date
    return {
        "action": event.type_action, "culture": event.culture, "variete": event.variete,
        "quantite": event.quantite, "unite": event.unite, "rang": event.rang,
        "parcelle": nom_parcelle, "date": jour.isoformat() if isinstance(jour, date) else None,
    }


def candidates(ctx: TenantContext, maintenant: Optional[datetime] = None) -> list[Candidate]:
    """Les gestes et les parcelles récemment touchés, encore là, du plus récent au plus ancien.

    Les références sont celles que l'agent a reçues : A1…A5 du contexte, puis A6… de
    `lire(quoi="actions")`. Une cible touchée deux fois n'est candidate qu'une fois, sous sa
    référence la plus récente ; un geste annulé ne l'est plus, une parcelle supprimée non plus.
    """
    from app.services.compagnon import actions_menees
    from database.models import Evenement

    contexte = actions_menees.recentes(ctx, maintenant=maintenant)
    au_dela, premier = actions_menees.au_dela(ctx, maintenant=maintenant)
    references = [(f"A{rang}", a) for rang, a in enumerate(contexte, start=1)]
    references += [(f"A{rang}", a) for rang, a in enumerate(au_dela, start=premier)]
    resultat: list[Candidate] = []
    vus: set[tuple] = set()
    try:
        with tenant_scope(ctx.potager_id):
            db = SessionLocal()
            try:
                for ref, action in references:
                    if not corrigeable(action):
                        continue
                    if action.cible_type == CIBLE_PARCELLE:
                        candidate = _candidate_parcelle(db, ctx, ref, action, vus)
                        if candidate is not None:
                            resultat.append(candidate)
                        continue
                    if (CIBLE_GESTE, action.cible_id) in vus:
                        continue
                    vus.add((CIBLE_GESTE, action.cible_id))
                    event = db.get(Evenement, action.cible_id)
                    if event is None or event.potager_id != ctx.potager_id:
                        continue
                    valeurs = _etat_du_geste(db, event)
                    suites = (db.query(Evenement.id)
                              .filter(Evenement.origine_graines_id == event.id,
                                      Evenement.potager_id == ctx.potager_id)
                              .count())
                    resultat.append(Candidate(
                        ref=ref, action=action, evenement_id=event.id, valeurs=valeurs,
                        resume=actions_menees.resume_evenement(event, valeurs["parcelle"]), suites=suites,
                    ))
            finally:
                db.close()
    except Exception:  # noqa: BLE001 — sans lecture, rien n'est proposé
        log.exception("[US-262] Gestes candidats illisibles (potager_id=%s)", ctx.potager_id)
        return []
    return resultat


def _candidate_parcelle(db, ctx: TenantContext, ref: str, action, vus: set) -> Optional[Candidate]:
    """Une parcelle créée ou modifiée, lue telle qu'elle est maintenant (nom d'après un renommage)."""
    from app.services.compagnon import actions_menees
    from utils.parcelles import normalize_parcelle_name

    nom = (action.apres or {}).get("nom") or action.cible_nom
    cle = (CIBLE_PARCELLE, normalize_parcelle_name(nom or ""))
    if not nom or cle in vus:
        return None
    vus.add(cle)
    fiche = actions_menees.instantane_parcelle(db, ctx.potager_id, nom)
    if not fiche or not fiche.get("actif", True):
        return None
    return Candidate(ref=ref, action=action, evenement_id=None, valeurs=fiche, resume=action.resume,
                     cible=CIBLE_PARCELLE, parcelle=fiche["nom"])


#: « c'était 8 rangs » sur une parcelle : le champ de sa fiche.
_CHAMPS_VERS_FICHE = {"rang": "nb_rangs"}
#: Les champs d'un geste qui valent pour tout geste ; les autres doivent déjà avoir une valeur.
_CHAMPS_DE_TOUT_GESTE = ("culture", "variete", "parcelle", "date")


def _champ_de_fiche(champ: str) -> Optional[str]:
    from app.services.agent.catalogue_outils import champs_fiche

    nom = _CHAMPS_VERS_FICHE.get(champ, champ)
    return nom if nom in {c.nom for c in champs_fiche()} else None


def _s_applique(candidate: Candidate, champ: str) -> bool:
    """« 8 rangs » ne corrige ni un arrosage, ni un semis compté en graines : le champ corrigé
    doit avoir un sens pour la cible — déjà renseigné sur un geste, ou présent sur la fiche."""
    if candidate.cible == CIBLE_PARCELLE:
        return _champ_de_fiche(champ) is not None
    if champ in _CHAMPS_DE_TOUT_GESTE:
        return True
    valeurs = candidate.valeurs
    if champ == "rang":
        return valeurs.get("rang") not in (None, 0) or (valeurs.get("unite") or "").lower().startswith("rang")
    if champ in ("quantite", "unite"):
        return valeurs.get("quantite") is not None
    return False


def compatibles(liste: list[Candidate], champs) -> list[Candidate]:
    """Les candidates auxquelles tous les champs corrigés s'appliquent."""
    dits = [c for c, v in (champs or {}).items() if v not in (None, "")] if isinstance(champs, dict) else []
    if not dits:
        return list(liste)
    return [c for c in liste if all(_s_applique(c, champ) for champ in dits)]


def _depuis(action) -> timedelta:
    cree_le = getattr(action, "cree_le", None)
    return datetime.utcnow() - cree_le if isinstance(cree_le, datetime) else timedelta.max


#: Les unités qu'une correction dit avec son nombre ; « rangs » désigne le champ `rang`.
_UNITES_DITES = (
    r"rangs?|rangees?|plants?|pieds?|kg|kilos?|grammes?|g|graines?|godets?|litres?|l|metres?|m|ml|cm|bottes?|"
    r"pieces?|unites?"
)
_MOTS_NOMBRES = ("zero", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf", "dix",
                 "onze", "douze", "treize", "quatorze", "quinze", "seize")
_VALEUR_DITE = re.compile(
    r"(?P<avant>\b(?:pas|au lieu de|et non)\s+)?"
    rf"(?P<nombre>\d+(?:[.,]\d+)?|\b(?:{'|'.join(_MOTS_NOMBRES)}|une))\s*(?P<unite>{_UNITES_DITES})\b"
)


def _meme_unite(unite_geste: Optional[str], unite_dite: str) -> bool:
    return bool(unite_geste) and _normalise(unite_geste)[:4].rstrip("s") == unite_dite[:4].rstrip("s")


def valeur_dite(phrase: str) -> Optional[tuple[str, float, str]]:
    """« c'était 2 plants », « oups, huit rangs » → (champ, nombre, unité) ; None si la phrase n'en
    dit aucune, ou en dit plusieurs. Une valeur après « pas » / « au lieu de » est l'ancienne."""
    trouvees = [m for m in _VALEUR_DITE.finditer(_normalise(phrase)) if not m.group("avant")]
    if len(trouvees) != 1:
        return None
    brut, unite = trouvees[0].group("nombre"), trouvees[0].group("unite")
    if brut in _MOTS_NOMBRES or brut == "une":
        nombre = float(_MOTS_NOMBRES.index(brut) if brut != "une" else 1)
    else:
        nombre = float(brut.replace(",", "."))
    champ = "rang" if unite.startswith("rang") else "quantite"
    return champ, (int(nombre) if nombre == int(nombre) else nombre), unite


def _meme_unite_dite(phrase: str, liste: list[Candidate], champs) -> list[Candidate]:
    """« 2 plants » départage une plantation de tomates (en plants) d'un semis de radis (en graines)."""
    if not (isinstance(champs, dict) and champs.get("quantite") not in (None, "")):
        return []
    dite = valeur_dite(phrase)
    if dite is None or dite[0] != "quantite":
        return []
    return [c for c in liste if c.cible == CIBLE_GESTE and _meme_unite(c.valeurs.get("unite"), dite[2])]


def _mots(texte: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", _normalise(texte))


def _singulier(mot: str) -> str:
    return mot[:-1] if len(mot) > 3 and mot[-1] in "sx" else mot


def _nomme_la_culture(culture: Optional[str], mots: list[str]) -> bool:
    if not culture:
        return False
    cles = [_singulier(m) for m in _mots(culture) if len(m) > 2]
    singuliers = {_singulier(m) for m in mots}
    return bool(cles) and all(cle in singuliers for cle in cles)


def _nomme_le_geste(type_action: Optional[str], mots: list[str]) -> bool:
    from utils.actions import normalize_action

    action = normalize_action(type_action) or (type_action or "")
    racines = _RACINES_GESTE.get(action) or ((action[:5],) if len(action) >= 5 else ())
    return any(m.startswith(racine) for racine in racines for m in mots)


def nommees(phrase: str, liste: list[Candidate]) -> list[Candidate]:
    """Les candidates que la phrase nomme, par leur culture, leur type de geste ou, pour une
    parcelle modifiée, son nom."""
    mots = _mots(phrase)
    par_parcelle = [c for c in liste if c.cible == CIBLE_PARCELLE
                    and all(m in mots for m in _mots(c.parcelle or "")) and _mots(c.parcelle or "")]
    if par_parcelle:
        return par_parcelle
    par_culture = [c for c in liste if _nomme_la_culture(c.valeurs.get("culture"), mots)]
    par_geste = [c for c in liste if _nomme_le_geste(c.valeurs.get("action"), mots)]
    if par_culture and par_geste:
        # « le semis de radis » : les deux à la fois, quand c'est possible.
        croisees = [c for c in par_culture if c in par_geste]
        return croisees or par_culture
    return par_culture or par_geste


def liste_nommee(liste: list[Candidate]) -> str:
    """[CA4] « A1 : semis radis, Planche Sud, 2 rangs, le 29/10 ; A2 : … »."""
    return " ; ".join(f"{c.ref} : {c.resume}" for c in liste)


@dataclass(frozen=True)
class Designation:
    """La candidate désignée, ou ce qu'il faut répondre."""

    candidate: Optional[Candidate] = None
    #: Lue par le modèle, qui se corrige.
    raison: str = ""
    #: [CA4] Dite au jardinier telle quelle : le code a tranché qu'il faut demander.
    question: Optional[str] = None


def designer(ref: Optional[str], phrase: str, liste: list[Candidate], annulation: bool,
             champs=None) -> Designation:
    """[CA4] La candidate visée par la phrase et la référence du modèle.

    Le code tranche ce que la phrase dit (« le dernier », une culture, un geste, une parcelle) ;
    la référence du modèle ne tranche que ce que la phrase ne dit pas. Une correction ne vise
    que les candidates auxquelles ses champs s'appliquent (`compatibles`) : « 8 rangs » ne
    désigne pas un arrosage. Deux candidates sans désignation : la question nomme les deux.
    """
    verbe = "annuler" if annulation else "corriger"
    if not liste:
        return Designation(raison="aucun geste récent à corriger", question=TEXTE_AUCUNE_ACTION)
    if not annulation:
        liste = compatibles(liste, champs) or liste
        liste = _meme_unite_dite(phrase, liste, champs) or liste
    par_ref = next((c for c in liste if c.ref == (ref or "").strip().upper()), None)
    nommees_ = nommees(phrase, liste)
    if _LA_DERNIERE.search(_normalise(phrase)):
        return Designation(candidate=(nommees_ or liste)[0])
    if par_ref is not None:
        if annulation and nommees_ and par_ref not in nommees_:
            # « annule le semis de carottes » ne retire jamais le radis que le modèle a choisi.
            return Designation(raison=(
                f"la phrase nomme {liste_nommee(nommees_)}, pas {par_ref.ref} : reprends la bonne référence"))
        if annulation and len(nommees_) > 1:
            return Designation(raison="plusieurs actions possibles", question=TEXTE_LAQUELLE.format(
                verbe=verbe, liste=liste_nommee(nommees_)))
        return Designation(candidate=par_ref)
    if len(nommees_) == 1:
        return Designation(candidate=nommees_[0])
    pool = nommees_ or liste
    if len(pool) == 1:
        return Designation(candidate=pool[0])
    if not annulation:
        # « Oups, c'était 2 plants » juste après un geste : celui des 10 dernières minutes, s'il est seul.
        recentes = [c for c in pool if _depuis(c.action) <= DELAI_CORRECTION]
        if len(recentes) == 1:
            return Designation(candidate=recentes[0])
    return Designation(raison="plusieurs actions possibles",
                       question=TEXTE_LAQUELLE.format(verbe=verbe, liste=liste_nommee(pool[:5])))


# ═════════════════════════════════════════════════════════════════════════════
# [CA1] Les champs corrigés, ancrés sur la phrase
# ═════════════════════════════════════════════════════════════════════════════
class _Refus(Exception):
    pass


def _nombre(valeur, entier: bool) -> float:
    try:
        nombre = float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        raise _Refus(f"valeur non numérique : {valeur!r}")
    if nombre < 0 or (entier and nombre != int(nombre)):
        raise _Refus(f"valeur impossible : {valeur!r}")
    return int(nombre) if nombre == int(nombre) else nombre


def _champ_corrige(champ: str, valeur, phrase: str, noms_parcelles: tuple[str, ...]):
    """La valeur d'un champ, ancrée sur la phrase ; lève `_Refus` avec la raison."""
    from app.services.agent.validation import _evoque, _nombre_dit
    from utils.parcelles import normalize_parcelle_name

    nature = CHAMPS[champ]
    if nature in (CHAMP_NOMBRE, CHAMP_ENTIER):
        nombre = _nombre(valeur, entier=nature == CHAMP_ENTIER)
        if not _nombre_dit(float(nombre), phrase):
            raise _Refus(f"{champ} = {nombre} n'est pas dit dans la phrase")
        return nombre
    texte = str(valeur).strip()
    if nature == CHAMP_PARCELLE:
        exacte = next((n for n in noms_parcelles
                       if normalize_parcelle_name(n) == normalize_parcelle_name(texte)), None)
        if exacte is None:
            raise _Refus(f"parcelle « {texte} » inconnue ; parcelles : {', '.join(noms_parcelles) or 'aucune'}")
        if not _evoque([texte], _mots(phrase)):
            raise _Refus(f"la parcelle « {texte} » n'est pas dite dans la phrase")
        return exacte
    if nature == CHAMP_DATE:
        try:
            jour = date.fromisoformat(texte)
        except ValueError:
            raise _Refus(f"date illisible : {texte!r} (format AAAA-MM-JJ)")
        if not _REPERE_DE_DATE.search(_normalise(phrase)):
            raise _Refus("aucune date n'est dite dans la phrase")
        return jour.isoformat()
    if not _evoque([texte], _mots(phrase)):
        raise _Refus(f"{champ} « {texte} » n'est pas dit dans la phrase")
    return texte


def _memes(avant, apres) -> bool:
    if avant is None or apres is None:
        return avant is None and apres is None
    try:
        return abs(float(avant) - float(apres)) < 1e-9
    except (TypeError, ValueError):
        return _normalise(str(avant)) == _normalise(str(apres))


def _champs_corriges(champs, candidate: Candidate, phrase: str,
                     noms_parcelles: tuple[str, ...]) -> dict:
    """Les champs qui CHANGENT, validés. « C'était 3 rangs » sur un geste compté en rangs
    (quantité + unité « rangs ») corrige sa quantité."""
    if not isinstance(champs, dict):
        raise _Refus("champs attendus : un objet {champ: valeur}")
    corriges: dict = {}
    for champ, valeur in champs.items():
        if champ not in CHAMPS or valeur in (None, ""):
            continue
        corriges[champ] = _champ_corrige(champ, valeur, phrase, noms_parcelles)
    actuel = candidate.valeurs
    if ("rang" in corriges and actuel.get("rang") in (None, 0)
            and (actuel.get("unite") or "").lower().startswith("rang") and "quantite" not in corriges):
        corriges["quantite"] = corriges.pop("rang")
    if not corriges:
        raise _Refus("aucun champ corrigé : dis la valeur qui change (quantite, rang, culture, parcelle…)")
    changent = {c: v for c, v in corriges.items() if not _memes(actuel.get(c), v)}
    if not changent:
        raise _Refus("la phrase redit la valeur actuelle : rien ne change")
    return changent


# ═════════════════════════════════════════════════════════════════════════════
# [CA1] La proposition et son récapitulatif avant → après
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class VerdictCorrection:
    commande: object = None             # CommandeInterpretee
    raison: str = ""
    question: Optional[str] = None


def _proposition(forme: FormeCommande, candidate: Candidate, texte: str,
                 champs: Optional[dict] = None):
    from app.services.interpreteur_commandes import ORIGINE_AGENT, CommandeInterpretee

    valeurs = {
        "ref": candidate.ref, "evenement": str(candidate.evenement_id), "resume": candidate.resume,
        "avant": json.dumps(candidate.valeurs, ensure_ascii=False),
    }
    if champs:
        valeurs["champs"] = json.dumps(champs, ensure_ascii=False)
    return CommandeInterpretee(
        commande=COMMANDE, sous_commande=forme.sous_commande, forme=forme, valeurs=valeurs,
        origine=ORIGINE_AGENT, confiance=1.0, texte_origine=texte,
    )


def valider(outil: str, arguments: dict, phrase: str, ctx: TenantContext,
            noms_parcelles: tuple[str, ...] = (), texte_origine: Optional[str] = None) -> VerdictCorrection:
    """[CA1, CA4] Un appel de `corriger_action` / `annuler_action` → proposition, raison ou question."""
    from app.services.agent.catalogue_outils import OUTIL_ANNULER_ACTION

    annulation = outil == OUTIL_ANNULER_ACTION
    arguments = arguments if isinstance(arguments, dict) else {}
    log.info("[US-262] %s(ref=%r, champs=%r)", outil, arguments.get("ref"), arguments.get("champs"))
    designation = designer(arguments.get("ref"), phrase, candidates(ctx), annulation, arguments.get("champs"))
    if designation.candidate is None:
        return VerdictCorrection(raison=designation.raison, question=designation.question)
    candidate = designation.candidate
    texte = texte_origine or phrase
    if candidate.cible == CIBLE_PARCELLE:
        return _corriger_parcelle(candidate, arguments.get("champs"), phrase, texte, annulation, noms_parcelles)
    if annulation:
        if candidate.suites:
            # Un semis dont des godets sont issus : les retirer d'une phrase casserait leur lien.
            return VerdictCorrection(
                raison="ce geste a déjà des suites", question=(
                    f"« {candidate.resume} » a déjà {candidate.suites} geste(s) qui en découlent : "
                    f"je ne l'annule pas d'une phrase. Passe par {COMMANDE_GUIDEE} si tu veux le retirer."))
        log.info("[US-262] Annulation proposée : %s (évènement %s)", candidate.ref, candidate.evenement_id)
        return VerdictCorrection(commande=_proposition(FORME_ANNULER, candidate, texte))
    try:
        champs = _champs_corriges(arguments.get("champs"), candidate, phrase, noms_parcelles)
    except _Refus as refus:
        return VerdictCorrection(raison=str(refus))
    log.info("[US-262] Correction proposée : %s (évènement %s) %s", candidate.ref, candidate.evenement_id, champs)
    return VerdictCorrection(commande=_proposition(FORME_CORRIGER, candidate, texte, champs))


#: [CA1] La ligne avant → après d'une correction de parcelle, portée par la commande `/parcelle
#: modifier` elle-même : `interpreteur_commandes.recapitulatif` la met en tête.
CLE_AVANT_APRES = "correction"


def _dit_fiche(valeur, unite: Optional[str]) -> str:
    if valeur in (None, ""):
        return "—"
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, float) and valeur == int(valeur):
        valeur = int(valeur)
    return f"{valeur} {unite}".strip() if unite else str(valeur)


def _corriger_parcelle(candidate: Candidate, champs, phrase: str, texte: str, annulation: bool,
                       noms_parcelles: tuple[str, ...]) -> VerdictCorrection:
    """[CA2] Une parcelle qu'on vient de créer ou de modifier se corrige par son service :
    la correction devient la commande `/parcelle modifier`, validée comme un appel de
    `modifier_parcelle`. Le nom de la parcelle vient de l'action désignée, pas de la phrase :
    il est ajouté au texte d'ancrage, les valeurs, elles, doivent être dites."""
    from app.services.agent.catalogue_outils import OUTIL_MODIFIER_PARCELLE, champs_fiche
    from app.services.agent.validation import ContexteValidation, valider_appel
    from llm.passerelle import AppelOutil

    nom = candidate.parcelle
    if annulation:
        return VerdictCorrection(
            raison="une modification de parcelle ne s'annule pas d'un mot",
            question=(f"Pour revenir en arrière sur « {nom} », dis-moi la valeur à remettre "
                      "(par exemple « remets 6 rangs »)."))
    if not isinstance(champs, dict):
        return VerdictCorrection(raison="champs attendus : un objet {champ: valeur}")
    par_nom = {c.nom: c for c in champs_fiche()}
    arguments: dict = {"parcelle": nom}
    for champ, valeur in champs.items():
        fiche = _champ_de_fiche(champ)
        if fiche is not None and valeur not in (None, ""):
            arguments[fiche] = valeur
    if len(arguments) == 1:
        return VerdictCorrection(raison=(
            f"{candidate.ref} est la parcelle « {nom} » : corrige un champ de sa fiche (rang = nombre de rangs…)"))
    verdict = valider_appel(
        AppelOutil(OUTIL_MODIFIER_PARCELLE, arguments),
        ContexteValidation(texte=f"parcelle {nom} ; {phrase}", noms_parcelles=noms_parcelles or (nom,)),
    )
    commande = verdict.commande
    if commande is None or not commande.complete:
        return VerdictCorrection(raison=verdict.precision or verdict.motif or "correction refusée")
    lignes = []
    for cle, valeur in arguments.items():
        champ = par_nom.get(cle)
        if champ is None:
            continue
        avant = candidate.valeurs.get(cle)
        if _memes(avant, valeur):
            continue
        lignes.append(f"{nom} — {champ.libelle} : {_dit_fiche(avant, champ.unite)} → {_dit_fiche(valeur, champ.unite)}")
    if not lignes:
        return VerdictCorrection(raison="la phrase redit la valeur actuelle : rien ne change")
    log.info("[US-262] Correction de la parcelle %r proposée (%s) : %s", nom, candidate.ref, lignes)
    from dataclasses import replace

    return VerdictCorrection(commande=replace(
        commande, valeurs={**commande.valeurs, CLE_AVANT_APRES: " ; ".join(lignes)}, texte_origine=texte,
    ))


#: [CA6] Le texte du filet : le récapitulatif du code parle, la carte porte les boutons.
TEXTE_FILET = "Je corrige ce que tu viens de noter :"


def filet(phrase: str, ctx: TenantContext, noms_parcelles: tuple[str, ...] = ()) -> Optional[VerdictCorrection]:
    """[CA1, CA6] Le modèle n'a appelé aucun outil sur une phrase de correction (recette du 29/10 :
    Ministral 8B écrit « Proposition : … confirme-moi » sans appel, et « oui » ne confirme rien).
    Le code lit lui-même la valeur dite (« 2 plants », « huit rangs ») et fait la proposition, avec
    sa carte et ses boutons. Sans valeur lisible, ou sans phrase de correction : None."""
    if not ressemble_a_une_correction(phrase):
        return None
    dite = valeur_dite(phrase)
    if dite is None:
        return None
    champ, nombre, _ = dite
    log.info("[US-262] Filet de correction : %s = %s lu dans %r", champ, nombre, phrase[:80])
    return valider("corriger_action", {"champs": {champ: nombre}}, phrase, ctx, noms_parcelles)


def _lus(commande) -> tuple[dict, dict]:
    valeurs = commande.valeurs or {}
    avant = json.loads(valeurs.get("avant") or "{}")
    champs = json.loads(valeurs.get("champs") or "{}")
    return avant, champs


def _dit(champ: str, valeur, etat: dict) -> str:
    """Une valeur telle qu'on la relit : « 3 rangs », « 2 kg », « 29/10/2026 »."""
    if valeur in (None, ""):
        return "—"
    if isinstance(valeur, float) and valeur == int(valeur):
        valeur = int(valeur)
    if champ == "rang":
        return f"{valeur} rangs"
    if champ == "quantite":
        unite = etat.get("unite")
        return f"{valeur} {unite}".strip() if unite else str(valeur)
    if champ == "date":
        try:
            return date.fromisoformat(str(valeur)).strftime("%d/%m/%Y")
        except ValueError:
            return str(valeur)
    return str(valeur)


def _designation_courte(etat: dict) -> str:
    """« Semis radis » — le geste et sa culture, majuscule en tête."""
    texte = " ".join(m for m in ((etat.get("action") or "geste").replace("_", " "), etat.get("culture") or "") if m)
    return texte[:1].upper() + texte[1:]


def lignes_avant_apres(commande) -> list[str]:
    """[CA1] « Semis radis : 2 rangs → 3 rangs », une ligne par champ qui change."""
    avant, champs = _lus(commande)
    apres = {**avant, **champs}
    titre = _designation_courte(avant)
    lignes = []
    for champ, valeur in champs.items():
        if champ == "unite" and "quantite" in champs:
            continue   # dite avec la quantité
        libelle = "" if champ in ("rang", "quantite") else f" — {_LIBELLES.get(champ, champ)}"
        lignes.append(f"{titre}{libelle} : {_dit(champ, avant.get(champ), avant)} → {_dit(champ, valeur, apres)}")
    return lignes


def _md(texte: str) -> str:
    return re.sub(r"([_*`\[])", r"\\\1", texte or "")


def recapitulatif(commande) -> str:
    """[CA1] Ce que la confirmation fera, en clair : avant → après, ou le geste retiré."""
    resume = (commande.valeurs or {}).get("resume") or "ce geste"
    if commande.sous_commande == SOUS_ANNULER:
        lignes = [f"*Annuler* : {_md(resume)}", "", "Le geste sera retiré du carnet."]
    else:
        lignes = ["*Corriger*", *(f"• {_md(ligne)}" for ligne in lignes_avant_apres(commande))]
    lignes += ["", f"Sans moi : `{COMMANDE_GUIDEE}`"]
    return "\n".join(lignes)


def commande_equivalente(commande) -> str:
    """Une ligne qui dit la correction, pour le journal, le contexte de l'agent et l'attente."""
    resume = (commande.valeurs or {}).get("resume") or ""
    if commande.sous_commande == SOUS_ANNULER:
        return f"{COMMANDE_GUIDEE} — annuler {resume}".strip()
    return f"{COMMANDE_GUIDEE} — " + " ; ".join(lignes_avant_apres(commande))


# ═════════════════════════════════════════════════════════════════════════════
# [CA2] L'exécution, après confirmation, par le service de la nature concernée
# ═════════════════════════════════════════════════════════════════════════════
TEXTE_DISPARU = "❌ Ce geste n'est plus dans le carnet : rien n'a été fait."
TEXTE_A_CHANGE = (
    "⚠️ Ce geste a changé depuis la proposition ({champ}) : rien n'a été fait. Redis ta correction."
)


def executer(db, ctx: TenantContext, commande) -> str:
    """[CA2] Corrige ou retire le geste, et rend ce que le jardinier lit.

    Le geste est relu : s'il a disparu ou changé depuis la proposition, rien n'est fait. Une
    correction passe par `evenements.corriger_evenement` (mêmes invariants qu'une création :
    `valider_evenement`) ; une annulation par `evenements.supprimer_evenement`.
    """
    from app.services import evenements as svc_evenements
    from database.models import Evenement

    try:
        evenement_id = int((commande.valeurs or {}).get("evenement") or 0)
    except ValueError:
        evenement_id = 0
    event = db.get(Evenement, evenement_id) if evenement_id else None
    if event is None or event.potager_id != ctx.potager_id:
        log.info("[US-262 / CA2] Évènement %s introuvable dans le potager %s → rien d'exécuté",
                 evenement_id, ctx.potager_id)
        return TEXTE_DISPARU
    avant, champs = _lus(commande)
    actuel = _etat_du_geste(db, event)
    for champ in (champs or avant):
        if not _memes(actuel.get(champ), avant.get(champ)):
            log.info("[US-262 / CA2] Évènement %s : %s a changé → rien d'exécuté", evenement_id, champ)
            return TEXTE_A_CHANGE.format(champ=_LIBELLES.get(champ, champ))
    resume = (commande.valeurs or {}).get("resume") or ""
    try:
        if commande.sous_commande == SOUS_ANNULER:
            if not svc_evenements.supprimer_evenement(db, ctx, evenement_id):
                return TEXTE_DISPARU
            log.info("[US-262 / CA2] Évènement %s annulé par une phrase", evenement_id)
            return f"🗑 Annulé : {resume} — retiré du carnet."
        corrections = dict(champs)
        if "parcelle" in corrections:
            from utils.parcelles import find_doublon, normalize_parcelle_name

            parcelle, _ = find_doublon(db, normalize_parcelle_name(corrections["parcelle"]),
                                       potager_id=ctx.potager_id)
            if parcelle is None:
                return f"❌ La parcelle « {corrections['parcelle']} » n'existe plus : rien n'a été fait."
            corrections["_parcelle_id"] = parcelle.id
        lignes = lignes_avant_apres(commande)
        trace = f"\n[corrigé par phrase {datetime.now().strftime('%d/%m/%Y %H:%M')} : {' ; '.join(lignes)}]"
        corrige = svc_evenements.corriger_evenement(db, ctx, evenement_id, corrections, trace)
        if corrige is None:
            return TEXTE_DISPARU
        log.info("[US-262 / CA2] Évènement %s corrigé par une phrase : %s", evenement_id, champs)
        return "✅ Corrigé : " + " ; ".join(lignes)
    except (ValueError, svc_evenements.EvenementInvalideError, PermissionInsuffisanteError,
            PotagerArchiveError) as e:
        # `valider_evenement` refuse (culture jamais plantée, contexte impossible…), le rôle ne
        # le permet pas, le potager est archivé : rien n'est écrit.
        db.rollback()
        log.info("[US-262 / CA2] Correction de l'évènement %s refusée : %s", evenement_id, e)
        return f"❌ {e}"
