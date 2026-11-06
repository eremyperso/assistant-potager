"""[US-269] Enregistrer un geste confirmé, quel que soit le canal.

Le chemin d'écriture des gestes vivait dans `app/bot/enregistrement.py`
(`_do_save_items`) et prenait un `Update` Telegram. Il est ici, sans objet
Telegram : des items structurés entrent (les dictionnaires produits par le
parseur et normalisés par le bot), un `ResultatEnregistrement` sort. Le canal
(bot aujourd'hui, PWA demain — levée d'A16, cadrage §4.6) n'a plus qu'à dire
ce résultat au jardinier.

Contrat repris tel quel du bot (aucun changement visible, CA2) :

* les avertissements de rotation/association sont évalués AVANT toute écriture
  (US-167 : sinon l'événement créé se compte comme son propre antécédent) ;
* une `mise_en_godet` passe toujours par `creer_evenement_godet` (bug id=351) ;
* le premier item refusé arrête la boucle : les précédents restent écrits (chaque
  événement est validé à part) et sont rendus dans `enregistres`, pour que le
  canal puisse le dire et éviter un doublon à la reprise ;
* l'item est enrichi de ce qui a RÉELLEMENT été enregistré (`contexte_semis`,
  `_lot_numero`) : le récapitulatif l'affiche (US-069, US-209).

La session est fournie par l'appelant, qui l'ouvre et la ferme. Une erreur
inattendue (base indisponible…) est remontée après un `rollback`.
"""
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.services import avertissements_plantation as svc_avertissements
from app.services import evenements as svc_evenements
from app.services.context import TenantContext
from utils.actions import normalize_action
from utils import parcelles as _parcelles

log = logging.getLogger("potager")

#: Résolution d'un nom de parcelle libre vers la `Parcelle` en base (ou None).
ResolveurParcelle = Callable[..., object]


def _resolveur_par_defaut(db: Session, nom: str, potager_id: Optional[int] = None):
    """La résolution de `utils.parcelles`, lue à l'appel (et non à l'import)."""
    return _parcelles.resolve_parcelle(db, nom, potager_id=potager_id)


@dataclass
class ResultatEnregistrement:
    """Ce que l'enregistrement a produit, à dire au jardinier par le canal.

    `enregistres` : (item enrichi, id de l'événement) dans l'ordre d'écriture.
    `erreur` : le refus du premier item non écrit (None si tout est écrit).
    `parcelle_inconnue` : le nom de la parcelle introuvable quand c'est la cause du refus.
    """
    enregistres: list[tuple[dict, int]] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)
    erreur: Optional[str] = None
    parcelle_inconnue: Optional[str] = None

    @property
    def complet(self) -> bool:
        """Vrai quand chaque item a été écrit (un geste de la file peut alors en sortir, US-224 / CA7)."""
        return self.erreur is None


def evaluer_avertissements(
    db: Session,
    ctx: TenantContext,
    items: list[dict],
    resoudre: ResolveurParcelle = _resolveur_par_defaut,
) -> list[str]:
    """[US-167 / CA1, CA10] Avertissements de rotation/association des plantations et semis d'un lot.

    À appeler AVANT toute écriture, sur l'historique tel qu'il était avant cette
    sauvegarde : appelé après, l'événement tout juste créé apparaîtrait comme son
    propre antécédent dans `rotation.evaluer_rotation` (faux conflit auto-référentiel,
    constaté en production le 02/09/2026).
    """
    messages: list[str] = []
    for parsed in items:
        if normalize_action(parsed.get("action")) not in svc_avertissements.ACTIONS_DECLENCHANT_AVERTISSEMENT:
            continue
        nom_parcelle = parsed.get("parcelle")
        if not nom_parcelle:
            continue
        parcelle = resoudre(db, nom_parcelle, potager_id=ctx.potager_id)
        if parcelle is None:
            continue
        messages.extend(
            svc_avertissements.evaluer_avertissements_plantation(db, ctx, parcelle.id, parsed.get("culture"))
        )
    return messages


def enregistrer_gestes(
    db: Session,
    ctx: TenantContext,
    items: list[dict],
    texte: str,
    resoudre: ResolveurParcelle = _resolveur_par_defaut,
) -> ResultatEnregistrement:
    """[US-269 / CA1] Écrit les gestes confirmés `items` (dictionnaires structurés) pour `texte`.

    Aucun objet Telegram : le canal fournit la session, le contexte du potager et,
    s'il le souhaite, sa résolution de parcelle (`resoudre`). Le blocage d'une
    parcelle introuvable reste décidé par la validation centrale de
    `creer_evenement_confirme` (US-049) ; la résolution ici ne sert qu'à construire
    l'événement avec le bon `parcelle_id`.
    """
    resultat = ResultatEnregistrement()
    try:
        resultat.avertissements = evaluer_avertissements(db, ctx, items, resoudre)

        for parsed in items:
            nom_parcelle = parsed.get("parcelle")
            parcelle_obj = resoudre(db, nom_parcelle, potager_id=ctx.potager_id) if nom_parcelle else None
            try:
                if normalize_action(parsed.get("action")) == "mise_en_godet":
                    event = svc_evenements.creer_evenement_godet(db, ctx, parsed, texte)
                else:
                    event = svc_evenements.creer_evenement_confirme(db, ctx, parsed, texte, parcelle_obj)
            except svc_evenements.ParcelleInconnueError as e:
                db.rollback()
                log.warning(f"⚠️ PARCELLE INCONNUE : {nom_parcelle!r} — sauvegarde bloquée")
                resultat.erreur = str(e)
                resultat.parcelle_inconnue = nom_parcelle
                return resultat
            except svc_evenements.EvenementInvalideError as e:
                # Filet de sécurité final : l'état du potager a pu changer entre la
                # confirmation et l'écriture.
                db.rollback()
                log.warning(f"❌ ÉVÉNEMENT INVALIDE (écriture) : {e} | texte={texte!r}")
                resultat.erreur = str(e)
                return resultat
            parsed["contexte_semis"] = event.contexte_semis
            if event.numero_lot is not None:
                parsed["_lot_numero"] = event.numero_lot
            resultat.enregistres.append((parsed, event.id))
            log.info(f"💾 [US-269] geste enregistré : id={event.id} | action={parsed.get('action')!r} "
                     f"| culture={parsed.get('culture')!r} | potager={ctx.potager_id}")
    except Exception:
        db.rollback()
        raise
    return resultat
