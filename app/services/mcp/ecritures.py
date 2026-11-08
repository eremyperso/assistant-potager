"""
app/services/mcp/ecritures.py — Enregistrer un geste depuis un assistant IA [US-292]
=====================================================================================
Toute écriture passe par une PROPOSITION (US-259, US-260, US-272), sur le canal `mcp` :

* `proposer_geste` range un geste STRUCTURÉ par le modèle du client — semis, mise en godet,
  plantation, récolte, perte, observation — et rend son récapitulatif, qui dit ce que devient
  le stock (CA1 à CA5). Rien n'est écrit au carnet ;
* `proposer_correction` corrige un geste récent selon les règles d'US-262 (CA11) ;
* `confirmer_proposition` / `abandonner_proposition` font sortir la proposition de l'attente
  par la sortie atomique commune : un seul canal gagne, MCP, la PWA ou Telegram (CA8, CA9).

Le serveur valide, refuse ou demande ; il ne devine jamais (étude §6). Les contrôles sont
ceux de la PWA (`gestes_conversation.controler`), sans parseur ni modèle de langage. Aucune
destruction par ce canal (D5, L7) : une annulation se confirme dans l'application.
"""
from __future__ import annotations

import difflib
import logging
from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.config import FRONTEND_URL
from app.services.compagnon import propositions as svc_propositions
from app.services.mcp.serveur import AppelOutil, Outil, RefusOutil, enregistrer_outil
from database.models import Parcelle, Proposition

log = logging.getLogger("potager")

CANAL = svc_propositions.CANAL_MCP

#: Les gestes qu'un assistant peut proposer (story d'US-292) : une liste fermée.
TYPES_GESTE = ("semis", "mise_en_godet", "plantation", "recolte", "perte", "observation")
_CHAMPS_CORRIGEABLES = ("quantite", "unite", "rang", "culture", "variete", "parcelle", "date")

ORGANE_REPRODUCTEUR = "reproducteur"
_UNITES_POIDS = {"kg": 1000.0, "g": 1.0}
_UNITES_PIEDS = {"plant", "plants", "pied", "pieds", "unite", "unites", "unité", "unités", "piece", "pieces", "pièce", "pièces"}

TEXTE_A_FAIRE = (
    "Montre ce récapitulatif au jardinier, tel quel. Appelle confirmer_proposition seulement "
    "s'il dit oui ; sinon abandonner_proposition. Rien n'est écrit avant."
)
TEXTE_DESTRUCTION = (
    "Une suppression ne se confirme pas depuis un assistant : ouvre la carte dans l'application "
    "pour la confirmer ou l'annuler."
)
TEXTE_A_CONFIRMER_DANS_L_APPLICATION = (
    "Cette proposition se confirme dans l'application (ou dans Telegram) : ouvre la carte."
)


def lien_vers_la_carte() -> str:
    """[CA10] L'application, panneau du compagnon ouvert : les cartes en attente y sont."""
    return f"{FRONTEND_URL.rstrip('/')}/?compagnon=ouvrir"


# ── Aides ─────────────────────────────────────────────────────────────────────
def _texte(arguments: dict, nom: str) -> Optional[str]:
    valeur = (arguments or {}).get(nom)
    if valeur is None:
        return None
    valeur = str(valeur).strip()
    return valeur or None


def _nombre(arguments: dict, nom: str) -> Optional[float]:
    valeur = (arguments or {}).get(nom)
    if valeur in (None, ""):
        return None
    try:
        nombre = float(str(valeur).replace(",", "."))
    except ValueError:
        raise RefusOutil(f"`{nom}` doit être un nombre.", "arguments")
    if nombre < 0:
        raise RefusOutil(f"`{nom}` ne peut pas être négatif.", "arguments")
    return nombre


def _entier(arguments: dict, nom: str) -> Optional[int]:
    nombre = _nombre(arguments, nom)
    if nombre is None:
        return None
    if nombre != int(nombre):
        raise RefusOutil(f"`{nom}` doit être un entier.", "arguments")
    return int(nombre)


def _date(arguments: dict) -> Optional[str]:
    """[CA7] Une date ISO ; une date future est refusée."""
    brut = _texte(arguments, "date")
    if brut is None:
        return None
    try:
        jour = date.fromisoformat(brut[:10])
    except ValueError:
        raise RefusOutil("`date` doit être une date ISO (AAAA-MM-JJ).", "arguments")
    if jour > date.today():
        raise RefusOutil(
            f"Date future refusée ({jour.isoformat()}) : on n'enregistre que ce qui est fait.", "date_future")
    return jour.isoformat()


def _chiffre(valeur: float) -> str:
    """1.7 → « 1,7 » ; 37.0 → « 37 »."""
    texte = f"{valeur:.3f}".rstrip("0").rstrip(".")
    return texte.replace(".", ",")


def _parcelles(db: Session, potager_id: int) -> list[str]:
    return [nom for (nom,) in db.query(Parcelle.nom)
            .filter(Parcelle.potager_id == potager_id, Parcelle.actif.isnot(False)).all()]


def _controler_parcelle(db: Session, potager_id: int, nom: str) -> None:
    """[CA6] Jamais de parcelle créée par un geste : introuvable → les noms proches, rien n'est proposé."""
    from utils.parcelles import resolve_parcelle

    if resolve_parcelle(db, nom, potager_id=potager_id) is not None:
        return
    noms = _parcelles(db, potager_id)
    proches = difflib.get_close_matches(nom, noms, n=3, cutoff=0.5) or noms[:5]
    suite = f" Parcelles proches : {', '.join(proches)}." if proches else " Ce potager n'a aucune parcelle."
    raise RefusOutil(
        f"Parcelle « {nom} » introuvable : aucune proposition créée.{suite} "
        "Une parcelle se crée dans l'application, jamais par un geste.", "parcelle_introuvable")


# ── Ce que devient le stock (CA1 à CA5) ───────────────────────────────────────
def _stock_de(db: Session, ctx, culture: str):
    from app.services import stock as svc_stock
    from utils.culture_resolve import normaliser_culture

    cle = normaliser_culture(culture)
    for nom, stock in svc_stock.calcul_stock_cultures(db, ctx).items():
        if normaliser_culture(nom) == cle:
            return stock
    return None


def _organe(db: Session, ctx, culture: str, stock) -> Optional[str]:
    from utils.stock import get_type_organe

    if stock is not None and stock.type_organe:
        return stock.type_organe
    return get_type_organe(db, culture, ctx.potager_id)


def _cumul(stock, quantite: float, unite: str) -> Optional[tuple[float, float, str]]:
    """Le rendement cumulé avant et après la récolte, dans l'unité du cumul ; None si les unités
    ne se convertissent pas (kg et pièces)."""
    avant = float(stock.rendement_total or 0) if stock is not None else 0.0
    unite_cumul = ((stock.unite_rendement if stock is not None else None) or "").lower() or unite
    if avant == 0 or unite_cumul == unite:
        return avant, avant + quantite, unite
    if unite in _UNITES_POIDS and unite_cumul in _UNITES_POIDS:
        # Le cumul est gardé en grammes : il se dit dans l'unité de la récolte (0,6 → 1,7 kg).
        avant = avant * _UNITES_POIDS[unite_cumul] / _UNITES_POIDS[unite]
        return avant, avant + quantite, unite
    return None


def effet_sur_le_stock(db: Session, ctx, item: dict) -> str:
    """[CA1–CA5] Ce que le geste fera du stock, dit en clair, à partir du stock de `/stats`.

    Reproductrice : un semis donne des pieds qui produiront plusieurs récoltes ; une récolte ne
    change pas les pieds actifs et s'ajoute au rendement cumulé ; seule une perte les réduit.
    Végétative : un semis crée un stock de pieds à récolter ; une récolte en retire les pieds.
    """
    from utils.actions import normalize_action

    action = normalize_action(item.get("action"))
    culture = item.get("culture") or ""
    quantite = float(item.get("quantite") or 0)
    unite = (item.get("unite") or "").lower()
    stock = _stock_de(db, ctx, culture) if culture else None
    reproductrice = _organe(db, ctx, culture, stock) == ORGANE_REPRODUCTEUR if culture else False
    actifs = float(stock.stock_plants) if stock is not None else 0.0

    if action == "semis":
        if reproductrice:
            return "Chaque graine levée donnera un pied qui produira plusieurs récoltes."
        return "Chaque graine levée donnera un pied, récolté une seule fois : un stock de pieds à récolter."
    if action == "mise_en_godet":
        return "Les godets rejoignent la pépinière ; les pieds actifs au potager ne changent pas."
    if action == "plantation":
        return f"Pieds actifs : {_chiffre(actifs)} → {_chiffre(actifs + quantite)}."
    if action == "recolte":
        if reproductrice:
            pieds = f"Pieds actifs : {_chiffre(actifs)} (inchangé)"
            cumul = _cumul(stock, quantite, unite)
            if cumul is None:
                return f"{pieds}, récolte de {_chiffre(quantite)} {unite} ajoutée au rendement."
            avant, apres, u = cumul
            if avant == 0:
                return f"{pieds}, premier rendement de la saison : {_chiffre(apres)} {u}."
            return f"{pieds}, cumul saison : {_chiffre(avant)} → {_chiffre(apres)} {u}."
        if unite in _UNITES_PIEDS or not unite:
            return f"Pieds restants : {_chiffre(actifs)} → {_chiffre(max(0.0, actifs - quantite))} (pieds arrachés)."
        return (f"Rendement : +{_chiffre(quantite)} {unite}. Les pieds restants ({_chiffre(actifs)}) ne "
                "baissent que si le nombre de pieds arrachés est dit.")
    if action == "perte":
        cause = f" Cause : {item['commentaire']}." if item.get("commentaire") else ""
        return f"Pieds actifs : {_chiffre(actifs)} → {_chiffre(max(0.0, actifs - quantite))}.{cause}"
    return "Le stock ne change pas."


# ── proposer_geste ────────────────────────────────────────────────────────────
def _item(arguments: dict) -> dict:
    type_geste = _texte(arguments, "type")
    if type_geste not in TYPES_GESTE:
        raise RefusOutil(f"`type` doit être l'un de : {', '.join(TYPES_GESTE)}.", "arguments")
    culture = _texte(arguments, "culture")
    if culture is None:
        # La validation centrale (US-011) l'exige, observation comprise.
        raise RefusOutil("Précise la culture (argument `culture`).", "arguments")
    item: dict[str, Any] = {
        "action": type_geste, "culture": culture, "variete": _texte(arguments, "variete"),
        "quantite": _nombre(arguments, "quantite"), "unite": _texte(arguments, "unite"),
        "parcelle": _texte(arguments, "parcelle"), "rang": _entier(arguments, "rang"),
        "date": _date(arguments) or date.today().isoformat(),
        "commentaire": _texte(arguments, "cause") if type_geste == "perte" else _texte(arguments, "note"),
    }
    lot = _entier(arguments, "lot")
    if lot is not None:
        item["numero_lot_cite"] = lot
    return {k: v for k, v in item.items() if v is not None}


def _phrase(item: dict, client: str) -> str:
    """La trace du geste au carnet (`texte_original`) : ce que l'assistant a transmis, et qui (CA12)."""
    morceaux = [item.get("action"), item.get("quantite"), item.get("unite"), item.get("culture"),
                item.get("variete"), f"parcelle {item['parcelle']}" if item.get("parcelle") else None,
                item.get("date"), item.get("commentaire")]
    return f"[{client} via MCP] " + " ".join(str(m) for m in morceaux if m not in (None, ""))


def _recapitulatif(item: dict) -> dict:
    from app.services.compagnon import gestes_conversation as svc_gestes_dits

    return {
        "geste": svc_gestes_dits.libelle_action(item.get("action")), "culture": item.get("culture"),
        "variete": item.get("variete"), "parcelle": item.get("parcelle"), "lot": item.get("_lot_numero"),
        "quantite": item.get("quantite"), "unite": item.get("unite"),
        "date": item.get("date") or date.today().isoformat(), "resume": svc_gestes_dits.resume(item),
    }


def _proposer_geste(db: Session, appel: AppelOutil) -> dict:
    """[CA1–CA7, CA9] Range un geste structuré en proposition ; rien n'est écrit au carnet."""
    from app.services import gestes as svc_gestes
    from app.services.compagnon import deux_canaux as svc_deux_canaux
    from app.services.compagnon import gestes_conversation as svc_gestes_dits

    ctx, client = appel.ctx, appel.connexion.client
    item = _item(appel.arguments)
    if item.get("parcelle"):
        _controler_parcelle(db, ctx.potager_id, item["parcelle"])
    texte = _phrase(item, client)

    preparation = svc_gestes_dits.controler(db, ctx, [item], texte)
    if preparation.precision:
        # [CA7] Ce qui manque revient en question : rien n'est proposé.
        return {"proposition": None, "question": preparation.precision,
                "a_faire": "Pose cette question au jardinier, puis rappelle proposer_geste avec sa réponse."}
    if not preparation.items:
        raise RefusOutil("Ce geste est incomplet ou incohérent : rien n'est proposé.", "geste_invalide")

    items = preparation.items
    effets = [effet_sur_le_stock(db, ctx, i) for i in items]
    avertissements = svc_gestes.evaluer_avertissements(db, ctx, items)
    avertissements += [i["_alerte_lot"] for i in items if i.get("_alerte_lot")]
    db.commit()

    geste = svc_gestes_dits.proposer(ctx, items, texte, canal=CANAL, client=client)
    svc_deux_canaux.apres_creation(geste.id, ctx.potager_id)  # [CA9] la carte part aussi dans Telegram
    log.info("[US-292] Geste proposé par %s : proposition=%s potager=%s", client, geste.id, ctx.potager_id)
    return {
        "proposition": geste.id, "etat": geste.etat, "expire_le": geste.expire_le.isoformat(),
        "recapitulatif": [_recapitulatif(i) for i in items], "stock": " ".join(effets),
        "avertissements": avertissements, "a_faire": TEXTE_A_FAIRE,
    }


# ── proposer_correction ───────────────────────────────────────────────────────
def _champs(arguments: dict) -> dict:
    champs = (arguments or {}).get("champs")
    if not isinstance(champs, dict) or not champs:
        raise RefusOutil("`champs` : un objet des valeurs qui changent, par exemple {\"quantite\": 3}.", "arguments")
    inconnus = set(champs) - set(_CHAMPS_CORRIGEABLES)
    if inconnus:
        raise RefusOutil(f"Champ non corrigeable : {', '.join(sorted(inconnus))}.", "arguments")
    if champs.get("date"):
        _date({"date": champs["date"]})
    return {k: v for k, v in champs.items() if v not in (None, "")}


def _valeurs_dites(champs: dict) -> str:
    """La « phrase » que l'ancrage d'US-262 relit : les valeurs transmises, chiffres aux deux formats."""
    mots = []
    for valeur in champs.values():
        mots.append(str(valeur))
        if isinstance(valeur, float):
            mots.append(str(valeur).replace(".", ","))
    return "correction : " + " ".join(mots)


def _proposer_correction(db: Session, appel: AppelOutil) -> dict:
    """[CA11] Corrige un geste récent selon US-262 : récapitulatif avant → après, semis à suites refusé."""
    from app.services import interpreteur_commandes as svc_interpreteur
    from app.services.agent.catalogue_outils import OUTIL_CORRIGER_ACTION
    from app.services.compagnon import corrections as svc_corrections
    from app.services.compagnon import deux_canaux as svc_deux_canaux

    ctx = appel.ctx
    champs = _champs(appel.arguments)
    liste = [c for c in svc_corrections.candidates(ctx) if c.cible == svc_corrections.CIBLE_GESTE]
    evenement = _entier(appel.arguments, "evenement")
    if evenement is not None:
        candidate = next((c for c in liste if c.evenement_id == evenement), None)
        if candidate is None:
            raise RefusOutil(
                f"Le geste {evenement} n'est pas parmi les gestes récents corrigeables (7 derniers jours, "
                "encore au carnet).", "correction")
    else:
        designation_dite = " ".join(filter(None, [
            "dernier", _texte(appel.arguments, "type_geste"), _texte(appel.arguments, "culture_du_geste")]))
        designation = svc_corrections.designer(None, designation_dite, liste, False, champs)
        if designation.candidate is None:
            return {"proposition": None, "question": designation.question or designation.raison}
        candidate = designation.candidate
    if candidate.suites:
        raise RefusOutil(
            f"« {candidate.resume} » a déjà {candidate.suites} geste(s) qui en découlent (godets, plantation) : "
            "il ne se corrige pas depuis un assistant. Passe par l'application.", "correction_suites")

    verdict = svc_corrections.valider(
        OUTIL_CORRIGER_ACTION, {"ref": candidate.ref, "champs": champs}, _valeurs_dites(champs), ctx,
        noms_parcelles=tuple(_parcelles(db, ctx.potager_id)),
        texte_origine=f"[{appel.connexion.client} via MCP] correction",
    )
    if verdict.commande is None:
        if verdict.question:
            return {"proposition": None, "question": verdict.question}
        raise RefusOutil(f"Correction refusée : {verdict.raison}.", "correction")
    db.commit()

    ancienne = svc_propositions.en_attente(ctx.user_id, ctx.potager_id)
    if ancienne is not None:
        svc_interpreteur.persister_journal(ctx, ancienne.commande, svc_interpreteur.ISSUE_ABANDONNEE, ancienne.log_id)
    log_id = svc_interpreteur.persister_journal(ctx, verdict.commande, svc_interpreteur.ISSUE_PROPOSEE)
    proposition = svc_propositions.proposer(ctx, verdict.commande, log_id=log_id, canal=CANAL)
    _noter_client(proposition.id, ctx.potager_id, appel.connexion.client)
    svc_deux_canaux.apres_creation(proposition.id, ctx.potager_id)
    return {
        "proposition": proposition.id, "etat": proposition.etat, "expire_le": proposition.expire_le.isoformat(),
        "geste": candidate.resume, "avant_apres": svc_corrections.lignes_avant_apres(verdict.commande),
        "a_faire": TEXTE_A_FAIRE,
    }


def _noter_client(proposition_id: int, potager_id: int, client: str) -> None:
    """[CA12] Le nom du client sur la proposition : la carte Telegram dit « Proposé par Claude »."""
    with svc_propositions.session_sur(potager_id) as db:
        ligne = db.get(Proposition, proposition_id)
        if ligne is not None:
            ligne.contenu = {**(ligne.contenu or {}), "client": client}
            db.commit()


# ── confirmer / abandonner ────────────────────────────────────────────────────
def potager_de_la_proposition(db: Session, connexion, arguments: dict) -> Optional[int]:
    """Sans `potager` dit, une confirmation vise le potager de SA proposition, pas le potager actif."""
    try:
        ident = int((arguments or {}).get("proposition"))
    except (TypeError, ValueError):
        return None
    with svc_propositions.session_sur(None) as lecture:
        ligne = (lecture.query(Proposition.potager_id)
                 .filter(Proposition.id == ident, Proposition.user_id == connexion.user_id).first())
    return ligne[0] if ligne is not None else None


def _ident(arguments: dict) -> int:
    ident = _entier(arguments, "proposition")
    if ident is None:
        raise RefusOutil("Précise la proposition (argument `proposition`).", "arguments")
    return ident


def _destructrice(commande: Any) -> bool:
    """[CA10, L7] Une annulation de geste (ou toute forme destructrice) ne se confirme pas ici."""
    from app.services import interpreteur_commandes as svc_interpreteur

    commandes = commande.etapes if isinstance(commande, svc_interpreteur.Plan) else [commande]
    return any(getattr(getattr(c, "forme", None), "destructrice", False) for c in commandes)


def _deja_traitee(erreur) -> RefusOutil:
    from app.services.compagnon import deux_canaux as svc_deux_canaux

    return RefusOutil(svc_deux_canaux.texte_deja_traitee(erreur.etat, erreur.canal, erreur.traite_le), "deja_traitee")


def _confirmer_proposition(db: Session, appel: AppelOutil) -> dict:
    """[CA8, CA10] Sortie atomique puis exécution par les services ; une seconde confirmation n'écrit rien."""
    from app.services.compagnon import echange_pwa as svc_echange
    from app.services.compagnon import gestes_conversation as svc_gestes_dits

    ctx, ident = appel.ctx, _ident(appel.arguments)
    if not svc_echange._est_un_geste_dit(ctx, ident):
        proposition = svc_propositions.par_id(ident, ctx.user_id, ctx.potager_id)
        if proposition is None:
            raise RefusOutil(f"Aucune proposition {ident} dans ce potager.", "introuvable")
        if _destructrice(proposition.commande):
            raise RefusOutil(f"{TEXTE_DESTRUCTION} {lien_vers_la_carte()}", "destruction")
    try:
        resultat = svc_echange.confirmer(ctx, ident, canal=CANAL)
    except svc_gestes_dits.GesteIntrouvableError:
        raise RefusOutil(f"Aucune proposition {ident} dans ce potager.", "introuvable")
    except svc_gestes_dits.GesteDejaTraiteError as erreur:
        raise _deja_traitee(erreur)
    except svc_echange.NonConfirmableDansLaPwaError:
        raise RefusOutil(f"{TEXTE_A_CONFIRMER_DANS_L_APPLICATION} {lien_vers_la_carte()}", "non_confirmable")
    log.info("[US-292] Proposition %s confirmée par %s : %s", ident, appel.connexion.client,
             "erreur" if resultat.erreur else "écrite")
    return {
        "proposition": ident, "etat": resultat.carte.get("etat"), "texte": resultat.texte,
        "enregistres": resultat.enregistres, "erreur": resultat.erreur,
        "avertissements": resultat.avertissements,
    }


def _abandonner_proposition(db: Session, appel: AppelOutil) -> dict:
    """[CA10] Laisse tomber la proposition : aucun effet en base."""
    from app.services.compagnon import echange_pwa as svc_echange
    from app.services.compagnon import gestes_conversation as svc_gestes_dits

    ctx, ident = appel.ctx, _ident(appel.arguments)
    try:
        resultat = svc_echange.abandonner(ctx, ident, canal=CANAL)
    except svc_gestes_dits.GesteIntrouvableError:
        raise RefusOutil(f"Aucune proposition {ident} dans ce potager.", "introuvable")
    except svc_gestes_dits.GesteDejaTraiteError as erreur:
        raise _deja_traitee(erreur)
    return {"proposition": ident, "etat": resultat.carte.get("etat"), "texte": resultat.texte}


# ── Déclarations ──────────────────────────────────────────────────────────────
_PROPOSITION = {"proposition": {"type": "integer", "description": "L'identifiant rendu par proposer_geste ou proposer_correction."}}

enregistrer_outil(Outil(
    nom="proposer_geste", titre="Proposer un geste",
    description=(
        "Prépare l'enregistrement d'un geste au carnet (semis, mise en godet, plantation, récolte, perte, "
        "observation) et rend son récapitulatif, qui dit ce que devient le stock. RIEN n'est écrit : le "
        "jardinier doit lire le récapitulatif et dire oui, puis appelle confirmer_proposition. Une parcelle "
        "inconnue n'est jamais créée ; une date future est refusée."
    ),
    proprietes={
        "type": {"type": "string", "enum": list(TYPES_GESTE), "description": "Le geste."},
        "culture": {"type": "string", "description": "La culture (fève, tomate…)."},
        "variete": {"type": "string", "description": "La variété, si elle est dite."},
        "quantite": {"type": "number", "minimum": 0, "description": "La quantité dite (obligatoire pour semis, plantation, récolte)."},
        "unite": {"type": "string", "description": "L'unité : graines, plants, kg, g, rangs, godets…"},
        "parcelle": {"type": "string", "description": "Le nom d'une parcelle existante."},
        "lot": {"type": "integer", "description": "Le numéro du lot de pépinière visé (mise en godet, plantation)."},
        "rang": {"type": "integer", "minimum": 1, "description": "Le nombre de rangs, s'il est dit."},
        "date": {"type": "string", "description": "Date du geste, ISO (AAAA-MM-JJ) ; aujourd'hui par défaut."},
        "cause": {"type": "string", "description": "Pour une perte : sa cause, si elle est dite."},
        "note": {"type": "string", "description": "Pour une observation : ce qui est observé."},
    },
    requis=("type", "culture"), executer=_proposer_geste, ecriture=True, idempotent=False,
))
enregistrer_outil(Outil(
    nom="proposer_correction", titre="Proposer une correction",
    description=(
        "Prépare la correction d'un geste récent (« en fait c'était 3 rangs ») et rend le récapitulatif "
        "avant → après. Le geste visé : `evenement` (identifiant lu dans consulter_carnet), sinon le plus "
        "récent du type et de la culture dits. RIEN n'est écrit avant confirmer_proposition."
    ),
    proprietes={
        "champs": {
            "type": "object", "description": "Les valeurs qui changent.",
            "properties": {
                "quantite": {"type": "number"}, "unite": {"type": "string"}, "rang": {"type": "integer"},
                "culture": {"type": "string"}, "variete": {"type": "string"}, "parcelle": {"type": "string"},
                "date": {"type": "string", "description": "AAAA-MM-JJ"},
            },
            "additionalProperties": False,
        },
        "evenement": {"type": "integer", "description": "L'identifiant du geste à corriger."},
        "type_geste": {"type": "string", "description": "Le type du geste visé (semis, recolte…)."},
        "culture_du_geste": {"type": "string", "description": "La culture du geste visé."},
    },
    requis=("champs",), executer=_proposer_correction, ecriture=True, idempotent=False,
))
enregistrer_outil(Outil(
    nom="confirmer_proposition", titre="Confirmer une proposition",
    description=(
        "Écrit au carnet une proposition que le jardinier a acceptée, une seule fois. Une proposition déjà "
        "traitée (ici, dans l'application ou dans Telegram) n'est pas refaite. Une suppression ne se "
        "confirme jamais ici : le lien vers l'application est rendu."
    ),
    proprietes=dict(_PROPOSITION), requis=("proposition",), executer=_confirmer_proposition,
    ecriture=True, idempotent=False, potager_de=potager_de_la_proposition,
))
enregistrer_outil(Outil(
    nom="abandonner_proposition", titre="Abandonner une proposition",
    description="Laisse tomber une proposition en attente : rien n'est écrit.",
    proprietes=dict(_PROPOSITION), requis=("proposition",), executer=_abandonner_proposition,
    ecriture=True, idempotent=False, potager_de=potager_de_la_proposition,
))
