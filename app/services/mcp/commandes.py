"""
app/services/mcp/commandes.py — Gérer parcelles et rappels depuis un assistant IA [US-293]
==========================================================================================
Deux outils :

* `proposer_commande` range une commande NON destructrice en proposition (canal `mcp`) et rend
  son récapitulatif avant → après. Seules les formes qui ont un exécuteur de service sont
  proposables (L6) ; la liste est LUE du registre (`FORMES_DICTABLES` croisé avec `EXECUTEURS`),
  jamais recopiée : une forme ouverte par US-289 CA7 entre ici sans une ligne de plus.
  La confirmation, atomique, est celle d'US-292 (`confirmer_proposition`) ;
* `ouvrir_dans_l_application` rend le lien profond vers l'écran d'une action irréversible
  (suppression, désactivation, annulation de geste, suppression de potager) : rien n'est exécuté (L7).

La validation est celle de l'agent (`agent.validation`) : mêmes refus que dans la PWA et Telegram,
sans modèle de langage. La gestion des membres, des invitations, des rôles, de la clé BYOK et du
compte n'est exposée par aucun outil (L5).
"""
from __future__ import annotations

import logging
from typing import Any, Optional
from urllib.parse import quote, urlencode

from sqlalchemy.orm import Session

from app.config import FRONTEND_URL
from app.services.compagnon import propositions as svc_propositions
from app.services.mcp.ecritures import (
    CANAL, TEXTE_A_FAIRE, TEXTE_DESTRUCTION, _controler_parcelle, _noter_client, _parcelles,
)
from app.services.mcp.serveur import AppelOutil, Outil, RefusOutil, enregistrer_outil

log = logging.getLogger("potager")

TEXTE_DANS_TELEGRAM = "Cette commande se fait encore dans Telegram : tape-la là-bas."
_FAUX = {"non", "false", "0", "faux", "no", "off"}


# ── Le registre : ce qui est proposable ───────────────────────────────────────
def _nom(forme) -> str:
    from app.services.agent.catalogue_outils import nom_de_forme

    return nom_de_forme(forme)


def formes_proposables() -> tuple:
    """[CA1] Les formes non destructrices qui ont un exécuteur de service, lues au registre."""
    from app.services.agent.executeurs import EXECUTEURS
    from app.services.menu_commandes import FORMES_DICTABLES

    return tuple(f for f in FORMES_DICTABLES if f.cle in EXECUTEURS and not f.destructrice)


def _forme_dite(dite: Any):
    """La forme désignée (« parcelle modifier », « /parcelle modifier »), ou None si elle n'existe pas."""
    from app.services.menu_commandes import FORMES_DICTABLES

    cle = " ".join(str(dite or "").lower().replace("/", " ").split())
    return next((f for f in FORMES_DICTABLES if _nom(f) == cle), None)


def lien_vers_l_ecran(ctx, ecran: str, **intention: str) -> str:
    """Le lien profond de la PWA (`/?vue=plan-vue&parcelle=Sud`), potager compris."""
    parametres = {"vue": ecran, **intention, "potager": str(ctx.potager_id)}
    return f"{FRONTEND_URL.rstrip('/')}/?{urlencode(parametres, quote_via=quote)}"


def _commande_a_taper(forme, arguments: dict) -> str:
    morceaux = [f"/{forme.commande}"] + ([forme.sous_commande] if forme.sous_commande else [])
    for argument in forme.arguments:
        valeur = arguments.get(argument.nom)
        morceaux.append(str(valeur) if valeur else f"<{argument.nom}>")
    return " ".join(morceaux)


# ── Lecture des arguments ─────────────────────────────────────────────────────
def _etapes(arguments: dict) -> list[tuple[str, dict]]:
    """Une commande seule (`commande` + `arguments`) ou un plan (`plan`), jamais les deux."""
    plan, commande = arguments.get("plan"), arguments.get("commande")
    if plan and commande:
        raise RefusOutil("Donne `commande` OU `plan`, pas les deux.", "arguments")
    if plan:
        if not isinstance(plan, list) or not all(isinstance(e, dict) for e in plan):
            raise RefusOutil("`plan` : une liste d'étapes {commande, arguments}.", "arguments")
        return [(str(e.get("commande") or ""), e.get("arguments") or {}) for e in plan]
    if not commande:
        raise RefusOutil("Précise `commande` (ex. « parcelle modifier ») et ses `arguments`.", "arguments")
    donnees = arguments.get("arguments") or {}
    if not isinstance(donnees, dict):
        raise RefusOutil("`arguments` : un objet {nom de l'argument: valeur}.", "arguments")
    return [(str(commande), donnees)]


def _champs_modification(donnees: dict) -> dict:
    """Les champs de la fiche d'une parcelle : à plat, ou en `modification` « rangs=3 »."""
    champs = {k: v for k, v in donnees.items() if k not in ("nom", "parcelle", "modification")}
    for morceau in str(donnees.get("modification") or "").split():
        cle, signe, valeur = morceau.partition("=")
        if not signe:
            raise RefusOutil(f"Paramètre invalide : « {morceau} » (attendu : clé=valeur).", "arguments")
        champs[cle] = valeur
    return champs


def _desactive(champs: dict) -> bool:
    """[CA3] `actif=non` (ou `actif: false`) : la mise hors service passe par l'application."""
    for cle, valeur in champs.items():
        if cle in ("actif",) and str(valeur).strip().lower() in _FAUX:
            return True
    return False


def _controler_forme(ctx, nom_dit: str, donnees: dict):
    """[CA2, CA3] La forme, si elle est proposable ; sinon le refus qui dit où la faire."""
    forme = _forme_dite(nom_dit)
    if forme is None:
        proposables = ", ".join(_nom(f) for f in formes_proposables())
        raise RefusOutil(f"Commande inconnue : « {nom_dit} ». Proposables ici : {proposables}.", "commande_inconnue")
    if forme.destructrice:
        raise RefusOutil(
            f"{TEXTE_DESTRUCTION} Appelle ouvrir_dans_l_application (action « supprimer_parcelle » ou "
            f"« annuler_geste ») pour rendre le lien. {lien_vers_l_ecran(ctx, 'plan-vue')}", "destruction")
    if forme.commande == "parcelle" and forme.sous_commande == "modifier" and _desactive(_champs_modification(donnees)):
        raise RefusOutil(
            f"Mettre une parcelle hors service ne se fait pas depuis un assistant. Appelle "
            f"ouvrir_dans_l_application (action « desactiver_parcelle »). {lien_vers_l_ecran(ctx, 'plan-vue')}",
            "destruction")
    if forme not in formes_proposables():
        raise RefusOutil(f"{TEXTE_DANS_TELEGRAM} Commande : {_commande_a_taper(forme, donnees)}", "telegram")
    return forme


# ── Traduction vers les appels d'outil de l'agent (validés comme dans la PWA) ─
def _appel_agent(forme, donnees: dict):
    from app.services.agent.catalogue_outils import OUTIL_CREER_PARCELLE, OUTIL_MODIFIER_PARCELLE, outils
    from llm.passerelle import AppelOutil as AppelModele

    if forme.commande == "parcelle" and forme.sous_commande == "modifier":
        return AppelModele(OUTIL_MODIFIER_PARCELLE, {
            "parcelle": donnees.get("nom") or donnees.get("parcelle"), **_champs_modification(donnees)})
    if forme.commande == "parcelle" and forme.sous_commande == "ajouter":
        return AppelModele(OUTIL_CREER_PARCELLE, {k: v for k, v in donnees.items() if v not in (None, "")})
    # Toute autre forme : l'outil du catalogue qui la couvre, propriété par propriété.
    outil = next((o for o in outils() if forme in o.formes), None)
    if outil is None:
        raise RefusOutil(f"{TEXTE_DANS_TELEGRAM} Commande : {_commande_a_taper(forme, donnees)}", "telegram")
    arguments = {}
    for argument in forme.arguments:
        propriete = outil.propriete(forme, argument.nom)
        if propriete and donnees.get(argument.nom) not in (None, ""):
            arguments[propriete] = donnees[argument.nom]
    if outil.discriminant:
        arguments[outil.discriminant] = next(
            (valeur for valeur, f in outil.valeurs_discriminant.items() if f == forme), None)
    return AppelModele(outil.nom, arguments)


def _phrase(etapes: list[tuple[Any, dict]], dite: Optional[str]) -> str:
    """La « phrase » que l'ancrage de l'agent relit : ce que le jardinier a dit, puis les valeurs transmises
    (noms, libellés des champs et chiffres aux deux formats) — comme `proposer_correction` (US-292)."""
    mots: list[str] = []
    for forme, donnees in etapes:
        mots += [forme.commande, forme.sous_commande or ""]
        for cle, valeur in donnees.items():
            mots += [str(cle).replace("_", " "), str(valeur)]
            if isinstance(valeur, float):
                mots.append(str(valeur).replace(".", ","))
    return " ; ".join(filter(None, [dite, " ".join(m for m in mots if m)]))


# ── Récapitulatif avant → après (CA5) ─────────────────────────────────────────
def _montrer(champ, valeur: Any) -> str:
    from app.services.agent import adaptateurs

    if valeur is None or valeur == "":
        return "non renseigné"
    if champ.type_json == "boolean":
        return "oui" if valeur in (True, "oui", "true") else "non"
    if champ.type_json in ("integer", "number"):
        nombre = adaptateurs.texte_nombre(float(str(valeur).replace(",", ".")))
        # « 2 rangs », « 10 m² » : l'unité du catalogue, à défaut la clé du champ (rangs).
        return f"{nombre} {champ.unite or champ.cle}"
    return str(valeur)


def lignes_avant_apres(db: Session, ctx, commande) -> list[str]:
    """« Sud : 2 rangs → 3 rangs » — une ligne par champ qui change ; les autres formes disent leur effet."""
    from app.services.agent.catalogue_outils import champs_fiche
    from app.services.compagnon import actions_menees

    forme = commande.forme
    valeurs = commande.valeurs or {}
    if forme.commande == "parcelle" and forme.sous_commande == "ajouter":
        details = ", ".join(f"{k} {v}" for k, v in valeurs.items() if k != "nom" and v)
        return [f"Nouvelle parcelle « {valeurs.get('nom')} »" + (f" ({details})" if details else "")]
    if forme.commande == "parcelle" and forme.sous_commande == "modifier":
        nom = valeurs.get("nom")
        avant = actions_menees.instantane_parcelle(db, ctx.potager_id, nom) or {}
        par_cle = {c.cle: c for c in champs_fiche()}
        lignes = []
        for morceau in (valeurs.get("modification") or "").split():
            cle, _, nouvelle = morceau.partition("=")
            champ = par_cle.get(cle)
            if champ is None:
                lignes.append(f"{avant.get('nom') or nom} : {cle} → {nouvelle}")
                continue
            ancienne = avant.get(champ.nom)
            etiquette = "" if champ.type_json in ("integer", "number") else f"{champ.libelle} : "
            lignes.append(
                f"{avant.get('nom') or nom} : {etiquette}{_montrer(champ, ancienne)} → {_montrer(champ, nouvelle)}")
        return lignes or [f"{nom} : rien à changer"]
    return [commande.commande_equivalente()]


# ── proposer_commande ─────────────────────────────────────────────────────────
def _controler_parcelles(db: Session, ctx, formes: list) -> None:
    """[CA7] Une parcelle visée qui n'existe pas (et qu'aucune étape précédente ne crée) : les noms proches,
    rien n'est proposé. Même contrôle que `proposer_geste` (US-292)."""
    from app.services.menu_commandes import TYPE_PARCELLE
    from utils.parcelles import normalize_parcelle_name

    creees: set[str] = set()
    for forme, donnees in formes:
        if forme.cle == ("parcelle", "ajouter") and donnees.get("nom"):
            creees.add(normalize_parcelle_name(str(donnees["nom"])))
        cibles = [donnees.get("nom") or donnees.get("parcelle")] if forme.cle == ("parcelle", "modifier") else [
            donnees.get(a.nom) for a in forme.arguments if a.type == TYPE_PARCELLE]
        for cible in filter(None, cibles):
            if normalize_parcelle_name(str(cible)) not in creees:
                try:
                    _controler_parcelle(db, ctx.potager_id, str(cible))
                except RefusOutil as refus:
                    raise RefusOutil(
                        refus.message.replace("aucune proposition créée", "rien n'est proposé")
                        .replace("Une parcelle se crée dans l'application, jamais par un geste.",
                                 "Pour la créer : proposer_commande « parcelle ajouter »."),
                        refus.motif)


def _proposer_commande(db: Session, appel: AppelOutil) -> dict:
    """[CA1–CA7] Valide, range en proposition (commande seule ou plan) ; rien n'est exécuté."""
    from dataclasses import replace

    from app.services import interpreteur_commandes as svc_interpreteur
    from app.services.agent.validation import ContexteValidation, valider_plan
    from app.services.compagnon import deux_canaux as svc_deux_canaux
    from utils.parcelles import resolve_parcelle

    ctx, client = appel.ctx, appel.connexion.client
    demandes = _etapes(appel.arguments)
    formes = [(_controler_forme(ctx, nom, donnees), donnees) for nom, donnees in demandes]
    _controler_parcelles(db, ctx, formes)

    def voisin(nom: str) -> Optional[str]:
        trouvee = resolve_parcelle(db, nom, potager_id=ctx.potager_id)
        return trouvee.nom if trouvee is not None else None

    dite = appel.arguments.get("phrase")
    contexte = ContexteValidation(
        texte=_phrase(formes, dite if isinstance(dite, str) else None),
        noms_parcelles=tuple(_parcelles(db, ctx.potager_id)), voisin=voisin,
    )
    verdict = valider_plan([_appel_agent(f, d) for f, d in formes], contexte)
    if verdict.plan is None:
        # [CA7] Valeur invalide, nom déjà pris, parcelle inconnue : la raison, rien n'est écrit.
        raison = verdict.precision or "La commande n'a pas pu être relue."
        log.info("[US-293] Commande refusée pour %s : %s", client, verdict.motif)
        raise RefusOutil(f"{raison} Rien n'est proposé.", "commande_refusee")

    plan = verdict.plan
    commande = replace(plan.etapes[0], texte_origine=f"[{client} via MCP]") if len(plan.etapes) == 1 else \
        replace(plan, texte_origine=f"[{client} via MCP]")
    etapes = commande.etapes if isinstance(commande, svc_interpreteur.Plan) else (commande,)
    incompletes = [e for e in etapes if not e.complete]
    if incompletes:
        manque = incompletes[0]
        question = (manque.manquants[0].question if manque.manquants else
                    f"Aucune parcelle ne porte exactement ce nom. Voulais-tu dire « {manque.candidats[0]} » ?"
                    if manque.candidats else "Quelle parcelle ?")
        return {"proposition": None, "question": question,
                "a_faire": "Pose cette question au jardinier, puis rappelle proposer_commande avec sa réponse."}

    recapitulatif = [ligne for etape in etapes for ligne in lignes_avant_apres(db, ctx, etape)]
    db.commit()

    ancienne = svc_propositions.en_attente(ctx.user_id, ctx.potager_id)
    if ancienne is not None:
        svc_interpreteur.persister_journal(ctx, ancienne.commande, svc_interpreteur.ISSUE_ABANDONNEE, ancienne.log_id)
    log_id = svc_interpreteur.persister_journal(ctx, commande, svc_interpreteur.ISSUE_PROPOSEE)
    proposition = svc_propositions.proposer(ctx, commande, log_id=log_id, canal=CANAL)
    _noter_client(proposition.id, ctx.potager_id, client)
    svc_deux_canaux.apres_creation(proposition.id, ctx.potager_id)
    log.info("[US-293] Commande proposée par %s : proposition=%s potager=%s (%d étape(s))",
             client, proposition.id, ctx.potager_id, len(etapes))
    return {
        "proposition": proposition.id, "etat": proposition.etat, "expire_le": proposition.expire_le.isoformat(),
        "recapitulatif": recapitulatif, "etapes": [e.commande_equivalente() for e in etapes],
        "a_faire": TEXTE_A_FAIRE,
    }


# ── ouvrir_dans_l_application ─────────────────────────────────────────────────
#: action → (écran de la PWA, besoin d'une parcelle, ce que le jardinier y fait)
ACTIONS_DANS_L_APPLICATION = {
    "supprimer_parcelle": ("plan-vue", True, "supprimer la parcelle « {parcelle} »"),
    "desactiver_parcelle": ("plan-vue", True, "mettre la parcelle « {parcelle} » hors service"),
    "annuler_geste": ("journal", False, "annuler un geste du carnet"),
    "supprimer_potager": ("bord", False, "supprimer le potager"),
    "voir_cartes_en_attente": (None, False, "confirmer ou abandonner les propositions en attente"),
}
ECRANS = ("bord", "plan-vue", "cultures", "pepiniere", "stocks", "journal", "stats")


def _ouvrir_dans_l_application(db: Session, appel: AppelOutil) -> dict:
    """[CA3] Un lien profond vers l'écran et l'action ; rien n'est exécuté, rien n'est écrit."""
    from utils.parcelles import resolve_parcelle

    ctx, arguments = appel.ctx, appel.arguments
    action, ecran = arguments.get("action"), arguments.get("ecran")
    if action is None and ecran is None:
        raise RefusOutil("Précise `action` (ex. supprimer_parcelle) ou `ecran`.", "arguments")
    if action is not None and action not in ACTIONS_DANS_L_APPLICATION:
        raise RefusOutil(f"Action inconnue : {action}. Possibles : {', '.join(ACTIONS_DANS_L_APPLICATION)}.", "arguments")
    if ecran is not None and ecran not in ECRANS:
        raise RefusOutil(f"Écran inconnu : {ecran}. Possibles : {', '.join(ECRANS)}.", "arguments")

    intention: dict[str, str] = {}
    cible = ecran
    faire = "consulter cet écran"
    if action is not None:
        cible, besoin_parcelle, faire = ACTIONS_DANS_L_APPLICATION[action]
        nom = arguments.get("parcelle")
        if besoin_parcelle:
            if not nom:
                raise RefusOutil("Précise la parcelle (argument `parcelle`).", "arguments")
            trouvee = resolve_parcelle(db, str(nom), potager_id=ctx.potager_id)
            if trouvee is None:
                raise RefusOutil(f"Parcelle « {nom} » introuvable dans ce potager.", "parcelle_introuvable")
            intention["parcelle"] = trouvee.nom
            faire = faire.format(parcelle=trouvee.nom)
        if cible is None:  # les cartes en attente : le panneau du compagnon
            from app.services.mcp.ecritures import lien_vers_la_carte

            lien = lien_vers_la_carte()
        else:
            lien = lien_vers_l_ecran(ctx, cible, **intention)
    else:
        lien = lien_vers_l_ecran(ctx, cible)
    log.info("[US-293] Lien rendu à %s : %s (%s)", appel.connexion.client, action or ecran, ctx.potager_id)
    return {
        "lien": lien,
        "texte": f"Ouvre ce lien dans l'application pour {faire}. Rien n'a été fait : "
                 "l'action se confirme là-bas, au bouton.",
    }


# ── Déclarations ──────────────────────────────────────────────────────────────
def _description_proposables() -> str:
    from app.services.menu_commandes import FORMES_DICTABLES  # noqa: F401 — registre lu à l'import

    return ", ".join(_nom(f) for f in formes_proposables())


enregistrer_outil(Outil(
    nom="proposer_commande", titre="Proposer une commande",
    description=(
        "Prépare une commande NON destructrice de l'application (créer ou modifier une parcelle, et les "
        "commandes qui s'y ajoutent) et rend son récapitulatif avant → après. RIEN n'est exécuté : montre le "
        "récapitulatif au jardinier, puis appelle confirmer_proposition s'il dit oui. Commandes proposables : "
        f"{_description_proposables()}. Une suppression, une mise hors service ou une annulation ne se "
        "proposent jamais : appelle ouvrir_dans_l_application. Pour plusieurs commandes, donne `plan` : elles "
        "s'exécutent dans l'ordre et s'arrêtent à la première en échec. Une commande qui n'est pas encore "
        "faisable ici est refusée avec la commande à taper dans Telegram."
    ),
    proprietes={
        "commande": {"type": "string", "description": "La forme, ex. « parcelle modifier »."},
        "arguments": {
            "type": "object",
            "description": ("Les arguments de la forme, par nom. Pour « parcelle modifier » : `nom` de la parcelle "
                            "existante, puis les champs de sa fiche (ex. {\"nom\": \"Sud\", \"rangs\": 3}). "
                            "Pour « parcelle ajouter » : `nom`, et si dits `exposition`, `superficie`."),
        },
        "plan": {
            "type": "array", "description": "Plusieurs commandes dans l'ordre : une liste de {commande, arguments}.",
            "items": {"type": "object", "properties": {"commande": {"type": "string"}, "arguments": {"type": "object"}},
                      "required": ["commande"]},
        },
        "phrase": {"type": "string", "description": "Ce que le jardinier a dit, mot pour mot, si tu l'as."},
    },
    executer=_proposer_commande, ecriture=True, idempotent=False,
))
enregistrer_outil(Outil(
    nom="ouvrir_dans_l_application", titre="Ouvrir dans l'application",
    description=(
        "Rend le lien vers l'écran de l'application où se fait une action irréversible : supprimer ou mettre "
        "hors service une parcelle, annuler un geste, supprimer le potager, ou confirmer les propositions en "
        "attente. N'exécute rien : le jardinier confirme au bouton, dans l'application."
    ),
    proprietes={
        "action": {"type": "string", "enum": list(ACTIONS_DANS_L_APPLICATION), "description": "L'action à faire dans l'application."},
        "parcelle": {"type": "string", "description": "La parcelle visée (supprimer_parcelle, desactiver_parcelle)."},
        "ecran": {"type": "string", "enum": list(ECRANS), "description": "Ou simplement un écran à ouvrir."},
    },
    executer=_ouvrir_dans_l_application,
))
