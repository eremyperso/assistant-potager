"""
app/services/compagnon/gestes_conversation.py — Un geste dit au compagnon, hors Telegram [US-270]
===================================================================================================
Sur Telegram, un geste compris attend dans `_ACTION_PENDING` (mémoire du bot) puis se
confirme au récapitulatif. La PWA n'a pas de bot : un geste dit dans son panneau attend
EN BASE, comme toute proposition (US-259), et se confirme par la même sortie atomique.

Une ligne de `propositions`, nature `geste`, marquée `ecran = 'compagnon'` :

* elle n'appartient PAS à la file d'US-224 (`file_gestes._file` l'exclut) : ni listée par
  `/gestes`, ni relancée, ni périmée par le job horaire — un geste dit n'est pas un geste
  « préparé pour plus tard » ;
* elle vit la durée d'une proposition de conversation (30 minutes) et la précédente est
  REMPLACÉE par la suivante (« non, 4 rangs » en fait une nouvelle) ;
* sa confirmation sort la ligne de l'attente D'ABORD (un seul appel gagne : deux clics, ou
  le portail et un autre onglet, n'écrivent qu'une fois), puis écrit par
  `app.services.gestes.enregistrer_gestes` — le chemin d'écriture que le bot emprunte.

Rien n'est écrit tant que le jardinier n'a pas confirmé.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.services import gestes as svc_gestes
from app.services import lots_pepiniere as svc_lots
from app.services import normalisation_gestes as svc_normalisation
from app.services.compagnon import propositions as svc_propositions
from app.services.context import TenantContext
from app.services.permissions import require_role
from database.models import Proposition
from llm.parseur_deterministe import ORIGINE_LLM
from utils.actions import normalize_action
from utils.culture_resolve import fusionner_culture_variete, resolve_culture, resolve_variete

log = logging.getLogger("potager")

#: La marque des gestes dits en conversation, qui les distingue de la file d'US-224.
ECRAN_COMPAGNON = "compagnon"

#: Les actions dont la quantité est demandée avant de confirmer (US-021 / CA9), comme le bot.
_ACTIONS_QUANTITE_OBLIGATOIRE = ("recolte", "semis", "plantation")


class GesteIntrouvableError(Exception):
    """Aucune proposition de ce numéro pour ce jardinier dans ce potager."""


class GesteDejaTraiteError(Exception):
    """La proposition n'attend plus : confirmée, abandonnée, remplacée ou périmée."""

    def __init__(self, etat: str, canal: Optional[str] = None, traite_le: Optional[datetime] = None):
        self.etat = etat
        self.canal = canal
        self.traite_le = traite_le
        super().__init__(f"Cette proposition n'attend plus (état : {etat}).")


@dataclass(frozen=True)
class GesteDit:
    """Un geste compris, tel que la base le garde."""

    id: int
    code: str
    items: list[dict]
    texte: str
    etat: str
    cree_le: datetime
    expire_le: datetime
    canal: Optional[str] = None
    traite_canal: Optional[str] = None
    traite_le: Optional[datetime] = None
    #: [US-272 / F5] Le potager de la proposition : celui qu'arme sa confirmation, d'où qu'elle vienne.
    potager_id: Optional[int] = None
    user_id: Optional[int] = None

    @property
    def en_attente(self) -> bool:
        return self.etat == svc_propositions.ETAT_EN_ATTENTE

    def expiree(self, maintenant: Optional[datetime] = None) -> bool:
        return self.expire_le <= (maintenant or datetime.utcnow())


@dataclass
class Preparation:
    """Ce que la lecture d'une phrase de geste a produit.

    `items` : les gestes compris, prêts à proposer. `precision` : ce qui manque pour
    en faire un geste (une question à poser, rien n'est proposé). `nature_question` :
    le parseur a reconnu une question plutôt qu'un geste (le canal la renvoie à la cascade).
    """

    items: list[dict] = field(default_factory=list)
    precision: Optional[str] = None
    question: bool = False


def _en_geste(ligne: Proposition) -> GesteDit:
    contenu = ligne.contenu or {}
    return GesteDit(
        id=ligne.id, code=ligne.code, items=list(contenu.get("items") or []), texte=contenu.get("texte") or "",
        etat=ligne.etat, cree_le=ligne.cree_le, expire_le=ligne.expire_le, canal=ligne.canal,
        traite_canal=ligne.traite_canal, traite_le=ligne.traite_le,
        potager_id=ligne.potager_id, user_id=ligne.user_id,
    )


def _requete(db, ctx: TenantContext):
    return db.query(Proposition).filter(
        Proposition.nature == svc_propositions.NATURE_GESTE,
        Proposition.ecran == ECRAN_COMPAGNON,
        Proposition.user_id == ctx.user_id,
        Proposition.potager_id == ctx.potager_id,
    )


# ═════════════════════════════════════════════════════════════════════════════
# Lire la phrase — les mêmes étapes que le bot (`saisie._parse_and_save`), sans Telegram
# ═════════════════════════════════════════════════════════════════════════════
def preparer(db, ctx: TenantContext, texte: str) -> Preparation:
    """[US-270 / CA1, CA6] Parse, normalise et contrôle une phrase de geste.

    Le parseur et la normalisation sont ceux du bot (`normalisation_gestes`) ; les contrôles
    qui suivent reprennent, dans l'ordre, ceux de `_parse_and_save` qui ne dépendent pas d'une
    question posée par boutons : rattachement du lot cité, culture hallucinée retirée,
    culture et variété canoniques, validation US-011. Peut lever `LLMIndisponibleError`.

    Ce que le bot demande par boutons (quelle parcelle, quel lot…) devient ici une
    `precision` : le panneau la pose en texte et attend la phrase complète.
    """
    # Une action potager nécessite le droit d'écrire : refusé AVANT tout appel de parsing (US-047).
    require_role(ctx, "editor", "enregistrer d'action")

    items = svc_normalisation.parser_items(texte, ctx)
    for item in items:
        if isinstance(item, dict):
            item.setdefault("origine_parsing", ORIGINE_LLM)
    return controler(db, ctx, items, texte)


def controler(db, ctx: TenantContext, items: list[dict], texte: str) -> Preparation:
    """[US-270, US-292 / CA6, CA7] Les contrôles d'un geste déjà STRUCTURÉ, sans modèle de langage.

    La suite de `preparer` après le parseur : la PWA y passe les items du parseur, le canal MCP
    ceux que le modèle du client a structurés (US-292) — mêmes règles, un seul endroit.
    """
    require_role(ctx, "editor", "enregistrer d'action")
    items = svc_normalisation.normaliser_items(items, texte)
    svc_lots.resoudre_references(db, ctx, items, texte)
    svc_lots.controler_emplacements_godets(db, ctx, items)

    from utils.validation import strip_culture_hallucinee, validate_parsed_action

    items = [strip_culture_hallucinee(item, texte) for item in items]

    for item in items:
        if not item.get("culture"):
            continue
        culture, variete = fusionner_culture_variete(db, ctx.potager_id, item["culture"], item.get("variete"))
        item["culture"], item["variete"] = culture, variete
        item["culture"] = resolve_culture(db, ctx.potager_id, item["culture"])
        if item.get("variete"):
            item["variete"] = resolve_variete(db, ctx.potager_id, item["culture"], item["variete"])

    preparation = Preparation()
    valides: list[dict] = []
    for item in items:
        est_valide, raison = validate_parsed_action(item, texte)
        if est_valide:
            valides.append(item)
        elif "manquante" in raison or "None" in raison:
            preparation.question = True
    items = valides

    if not items:
        return preparation
    premier = items[0]
    if not (premier.get("action") or premier.get("culture") or premier.get("quantite")):
        preparation.precision = (
            "Je n'ai pas compris cette action. Pour enregistrer : « récolté 2 kg de tomates hier » ; "
            "pour interroger : « combien de tomates ai-je récolté ? »."
        )
        return preparation
    if len(items) == 1 and premier.get("action") == "AMBIGUE":
        preparation.precision = (
            "Je n'ai pas bien compris la quantité et les rangs. "
            + (premier.get("commentaire") or "Précise le nombre de plants par rang et le nombre de rangs")
            + " — par exemple : « planter 10 choux-fleurs par rang sur 3 rangs parcelle nord »."
        )
        return preparation
    if (
        len(items) == 1
        and normalize_action(premier.get("action")) in _ACTIONS_QUANTITE_OBLIGATOIRE
        and not premier.get("quantite")
    ):
        preparation.precision = "Quelle quantité ? Redis ta phrase avec la quantité (2 kg, 15 plants, 1 sachet…)."
        return preparation

    # [US-037 / CA7] Semis d'une culture inconnue de CultureConfig : le bot demande par boutons si
    # elle est végétative ou reproductive. La PWA n'a pas ce dialogue : elle le dit, rien n'est proposé.
    if len(items) == 1 and normalize_action(premier.get("action")) == "semis" and premier.get("culture"):
        from utils.stock import get_type_organe

        culture = premier["culture"].strip()
        if get_type_organe(db, culture) is None:
            preparation.precision = (
                f"« {culture.capitalize()} » est une culture que l'application ne connaît pas encore : "
                "il faut dire si elle est végétative (on récolte la plante entière) ou reproductive "
                "(on cueille plusieurs fois). Dis cette phrase une première fois au compagnon dans Telegram, "
                "qui te le demandera."
            )
            return preparation

    # [US-049] Un récapitulatif voué à échouer n'est pas proposé : la validation centrale, qui
    # reste l'autorité à l'écriture, parle avant — avec ses mots.
    refus = _refus_de_validation(db, ctx, items, texte)
    if refus is not None:
        preparation.precision = refus
        return preparation
    preparation.items = items
    return preparation


def _refus_de_validation(db, ctx: TenantContext, items: list[dict], texte: str) -> Optional[str]:
    """Le motif de refus de la validation centrale (US-049) pour l'un des items, ou None."""
    from app.services import evenements as svc_evenements
    from utils.parcelles import resolve_parcelle

    for item in items:
        nom = item.get("parcelle")
        parcelle = resolve_parcelle(db, nom, potager_id=ctx.potager_id) if nom else None
        try:
            svc_evenements.valider_evenement(
                db, ctx, action=normalize_action(item.get("action")), culture=item.get("culture"),
                variete=item.get("variete"), parcelle=parcelle, nom_parcelle_brut=nom,
                quantite=_nombre(item.get("quantite")), unite=item.get("unite"), texte=texte,
                contexte_semis=item.get("contexte_semis"),
                origine_graines_id=item.get("origine_graines_id"),
            )
        except svc_evenements.EvenementInvalideError as e:
            return str(e)
    return None


def _nombre(valeur) -> Optional[float]:
    try:
        return float(valeur) if valeur is not None else None
    except (TypeError, ValueError):
        return None


# ═════════════════════════════════════════════════════════════════════════════
# Proposer, lire, sortir
# ═════════════════════════════════════════════════════════════════════════════
def proposer(
    ctx: TenantContext, items: list[dict], texte: str, *, maintenant: Optional[datetime] = None,
    canal: str = svc_propositions.CANAL_PWA, client: Optional[str] = None,
) -> GesteDit:
    """Range le geste compris en attente de confirmation ; le précédent est REMPLACÉ.

    [US-292] `canal` : `pwa`, ou `mcp` pour un assistant IA externe, dont `client` garde le nom
    (Claude, ChatGPT…) pour la carte et la traçabilité (CA12)."""
    instant = maintenant or datetime.utcnow()
    contenu = {"items": items, "texte": texte}
    if client:
        contenu["client"] = client
    with svc_propositions.session_sur(ctx.potager_id) as db:
        ligne = Proposition(
            code=svc_propositions.generer_code(db), user_id=ctx.user_id, potager_id=ctx.potager_id,
            nature=svc_propositions.NATURE_GESTE, contenu=contenu,
            ecran=ECRAN_COMPAGNON, canal=canal, cree_le=instant,
            expire_le=svc_propositions.expiration(instant, notifiee=False), notifiee=False,
            etat=svc_propositions.ETAT_EN_ATTENTE,
        )
        db.add(ligne)
        db.flush()
        remplacees = (
            _requete(db, ctx)
            .filter(Proposition.etat == svc_propositions.ETAT_EN_ATTENTE, Proposition.id != ligne.id)
            .update(
                {"etat": svc_propositions.ETAT_REMPLACEE, "traite_le": instant, "remplacee_par_id": ligne.id},
                synchronize_session=False,
            )
        )
        db.commit()
        db.refresh(ligne)
        log.info("[US-270] Geste dit rangé : id=%s user_id=%s potager_id=%s (%s item(s), %s remplacé(s))",
                 ligne.id, ctx.user_id, ctx.potager_id, len(items), remplacees)
        return _en_geste(ligne)


def en_attente(ctx: TenantContext, maintenant: Optional[datetime] = None) -> list[GesteDit]:
    """Les gestes dits qui attendent encore ce jardinier dans ce potager (le plus récent d'abord)."""
    instant = maintenant or datetime.utcnow()
    with svc_propositions.session_sur(ctx.potager_id) as db:
        lignes = (
            _requete(db, ctx)
            .filter(Proposition.etat == svc_propositions.ETAT_EN_ATTENTE, Proposition.expire_le > instant)
            .order_by(Proposition.cree_le.desc(), Proposition.id.desc())
            .all()
        )
        return [_en_geste(ligne) for ligne in lignes]


def par_id(ctx: TenantContext, geste_id: int) -> GesteDit:
    """Le geste dit de ce numéro, dans l'état où il est. Lève `GesteIntrouvableError`.

    Le filtre `user_id` + `potager_id` est celui du COMPTE connecté : une proposition d'un autre
    jardinier ou d'un autre potager n'existe pas ici (CA7).
    """
    with svc_propositions.session_sur(ctx.potager_id) as db:
        ligne = _requete(db, ctx).filter(Proposition.id == int(geste_id)).first()
        if ligne is None:
            raise GesteIntrouvableError(geste_id)
        return _en_geste(ligne)


def par_code(code: Optional[str], user_id: Optional[int]) -> Optional[GesteDit]:
    """[US-272] Le geste dit qu'un bouton Telegram nomme (`cmp:ok:<code>`), dans tous ses états.

    Lu GUC désarmé, comme `propositions.par_code` : le bouton peut viser un autre potager que
    le potager actif du chat (F5). L'isolation tient au filtre `user_id`.
    """
    if not code or user_id is None:
        return None
    with svc_propositions.session_sur(None) as db:
        ligne = (
            db.query(Proposition)
            .filter(
                Proposition.code == code, Proposition.user_id == user_id,
                Proposition.nature == svc_propositions.NATURE_GESTE, Proposition.ecran == ECRAN_COMPAGNON,
            )
            .first()
        )
        return _en_geste(ligne) if ligne is not None else None


def _controler_en_attente(geste: GesteDit) -> None:
    if not geste.en_attente:
        raise GesteDejaTraiteError(geste.etat, geste.traite_canal or geste.canal, geste.traite_le)
    if geste.expiree():
        raise GesteDejaTraiteError(svc_propositions.ETAT_PERIMEE)


def abandonner(ctx: TenantContext, geste_id: int, canal: str = svc_propositions.CANAL_PWA) -> GesteDit:
    """[CA2] Laisse tomber le geste : sortie atomique, rien n'est écrit.

    [US-272] `canal` : où il est laissé tomber (le portail, ou sa carte dans Telegram)."""
    geste = par_id(ctx, geste_id)
    _controler_en_attente(geste)
    with svc_propositions.session_sur(ctx.potager_id) as db:
        sorti = svc_propositions.sortir(
            db, geste.id, svc_propositions.ETAT_ABANDONNEE, canal=canal,
        )
    if not sorti:
        autre = par_id(ctx, geste_id)
        raise GesteDejaTraiteError(autre.etat, autre.traite_canal or autre.canal, autre.traite_le)
    return par_id(ctx, geste_id)


def confirmer(
    ctx: TenantContext, geste_id: int, canal: str = svc_propositions.CANAL_PWA,
) -> tuple[GesteDit, svc_gestes.ResultatEnregistrement]:
    """[CA2] Confirme le geste : il sort de l'attente D'ABORD, puis s'écrit.

    Une seule confirmation écrit (règle d'US-234 / US-259 : `UPDATE … WHERE etat = 'en_attente'`).
    Si l'écriture est refusée, la proposition revient en attente avec ce qui reste à écrire —
    un geste ne disparaît jamais sans trace —, et le refus est rendu au canal en clair.

    [US-272] `canal` : le portail, ou la carte du geste dans Telegram (F1 : le premier l'emporte).
    """
    geste = par_id(ctx, geste_id)
    _controler_en_attente(geste)
    require_role(ctx, "editor", "enregistrer d'action")

    with svc_propositions.session_sur(ctx.potager_id) as db:
        sorti = svc_propositions.sortir(
            db, geste.id, svc_propositions.ETAT_CONFIRMEE, canal=canal,
        )
    if not sorti:
        # Un autre clic, un autre onglet ou Telegram a confirmé entre-temps.
        autre = par_id(ctx, geste_id)
        raise GesteDejaTraiteError(autre.etat, autre.traite_canal or autre.canal, autre.traite_le)

    items = [dict(item) for item in geste.items]
    try:
        with svc_propositions.session_sur(ctx.potager_id) as db:
            resultat = svc_gestes.enregistrer_gestes(db, ctx, items, geste.texte)
    except Exception:
        _rouvrir(ctx, geste.id, geste.items)
        raise
    if not resultat.complet:
        ecrits = len(resultat.enregistres)
        _rouvrir(ctx, geste.id, geste.items[ecrits:])
    return par_id(ctx, geste_id), resultat


def _rouvrir(ctx: TenantContext, geste_id: int, items_restants: list[dict]) -> None:
    """Remet le geste en attente avec les seuls items non écrits (refus ou erreur d'écriture)."""
    with svc_propositions.session_sur(ctx.potager_id) as db:
        ligne = _requete(db, ctx).filter(Proposition.id == int(geste_id)).first()
        if ligne is None:
            return
        contenu = dict(ligne.contenu or {})
        contenu["items"] = items_restants
        ligne.contenu = contenu
        ligne.etat = svc_propositions.ETAT_EN_ATTENTE
        ligne.traite_le = None
        ligne.traite_canal = None
        db.commit()
        log.warning("[US-270] Geste id=%s remis en attente : %s item(s) non écrit(s)", geste_id, len(items_restants))


#: Comment se DIT une action à l'écran (la clé du référentiel n'a ni accent ni espace).
_LIBELLES_ACTION: dict[str, str] = {
    "recolte": "récolte", "mise_en_godet": "mise en godet", "perte_godet": "perte de godets",
    "cloture_lot": "clôture de lot", "levee": "levée", "desherbage": "désherbage",
    "fertilisation": "fertilisation", "deplacement": "déplacement", "repiquage": "repiquage",
}


def libelle_action(action: Optional[str]) -> str:
    """L'action dite en clair : « récolte », « mise en godet »…"""
    cle = normalize_action(action) or (action or "")
    return _LIBELLES_ACTION.get(cle, cle.replace("_", " "))


def resume(item: dict) -> str:
    """Le geste en une ligne, pour la carte : « semis · radis · 2 rangs · planche sud »."""
    morceaux = [
        libelle_action(item.get("action")),
        " ".join(filter(None, [item.get("culture"), item.get("variete")])),
        " ".join(filter(None, [
            str(item["quantite"]).rstrip("0").rstrip(".") if isinstance(item.get("quantite"), float)
            else (str(item["quantite"]) if item.get("quantite") is not None else None),
            item.get("unite"),
        ])),
        f"rang {item['rang']}" if item.get("rang") else None,
        f"parcelle {item['parcelle']}" if item.get("parcelle") else None,
        item.get("date"),
    ]
    return " · ".join(m for m in morceaux if m)
