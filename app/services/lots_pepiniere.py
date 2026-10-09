"""
app/services/lots_pepiniere.py — Référence à un lot de pépinière par son numéro [US-209]
----------------------------------------------------------------------------------------
Le jardinier écrit un numéro court au crayon sur l'étiquette de la barquette et le
dit : « repiqué 40 plants du lot 128 en godet », « #128 », « où en est le lot 128 ».
Ce module est le seul endroit qui sait :

  - LIRE cette référence dans une phrase (`extraire_reference_lot`) — grammaire
    déterministe, aucun appel au modèle (CA5) ;
  - la RÉSOUDRE sur le potager courant et la confronter à ce que le jardinier dit
    (`resoudre_references`) — numéro inconnu ou contradictoire signalé, jamais
    corrigé en silence (CA6) ;
  - RENDRE la fiche d'un lot (`formater_lot_telegram`, CA7).

« lot » suivi d'un nombre n'est une référence que dans une phrase de geste de
pépinière : « 12 lots de godets » est une quantité, et « lots » (pluriel) n'est
jamais lu comme une référence.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from sqlalchemy.orm import Session

from app.services import stock as svc_stock
from app.services.context import TenantContext
from utils.actions import normalize_action
from utils.culture_resolve import normaliser_culture
from utils.parcelles import get_all_parcelles, resolve_parcelle

log = logging.getLogger("potager")

#: Gestes de pépinière qui reconnaissent un lot cité (CA5). Les gestes de
#: déplacement (US-211) et de levée (US-212) s'ajoutent ici quand ils existent.
ACTIONS_AVEC_LOT: frozenset[str] = frozenset({
    "mise_en_godet", "perte_godet", "perte", "vendu", "plantation",
})

# « lot 128 », « le lot 128 », « lot n° 128 », « lot numéro 128 », « #128 ».
_MOTIF_REFERENCE = re.compile(
    r"(?:\blot\s*(?:(?:n|no|num[eé]ro)\s*[°º.]?\s*)?#?|(?<!\w)#)\s*(\d{1,6})(?!\d)",
    re.IGNORECASE,
)
_ARTICLE_AVANT = re.compile(r"\b(?:du|de|le|au|ce|cet)\s*$", re.IGNORECASE)


def extraire_reference_lot(texte: str) -> tuple[str, Optional[int]]:
    """[US-209 / CA5] Détache « lot N » / « #N » d'une phrase.

    Retourne (phrase sans la référence, numéro) — ou (phrase intacte, None). Une
    seule référence est lue : deux numéros dans une phrase sont ambigus et la
    phrase est laissée telle quelle (None), le geste suivra son chemin habituel.
    """
    if not texte:
        return texte, None
    correspondances = list(_MOTIF_REFERENCE.finditer(texte))
    if len(correspondances) != 1:
        return texte, None
    m = correspondances[0]
    # L'article qui introduisait la référence part avec elle (« du lot 128 »).
    avant = _ARTICLE_AVANT.sub("", texte[:m.start()])
    return re.sub(r"\s+", " ", f"{avant} {texte[m.end():]}").strip(), int(m.group(1))


def resoudre_references(db: Session, ctx: TenantContext, items: list[dict], texte: str = "") -> None:
    """[US-209 / CA5, CA6] Rattache chaque geste de pépinière au lot qu'il cite.

    Mute les items en place. Pour un item qui cite un lot (`numero_lot_cite`, posé
    par le parseur déterministe, ou lu dans `texte` pour un item venu du modèle) :

      - lot connu et cohérent → `origine_graines_id` (mise en godet, perte, vente)
        ou `source_evenement_ids` (plantation) pointent sur ce lot ; culture et
        variété manquantes sont reprises du lot ; `_lot_numero` porte le numéro
        pour les récapitulatifs ;
      - lot inconnu, ou d'une autre culture que celle dite → AUCUN rattachement,
        et `_alerte_lot` dit pourquoi au récapitulatif. Le jardinier confirme
        l'enregistrement sans lot, ou annule : rien n'est corrigé en silence.
    """
    cite_dans_texte: Optional[int] = None
    if texte and sum(1 for i in items if isinstance(i, dict)) == 1:
        _, cite_dans_texte = extraire_reference_lot(texte)

    for item in items:
        if not isinstance(item, dict):
            continue
        action = normalize_action(item.get("action"))
        if action not in ACTIONS_AVEC_LOT:
            item.pop("numero_lot_cite", None)
            continue
        numero = item.get("numero_lot_cite")
        if numero is None:
            numero = cite_dans_texte
        if numero is None:
            continue
        numero = int(numero)
        item["numero_lot_cite"] = numero

        lot = svc_stock.lot_pepiniere_par_numero(db, ctx, numero)
        if lot is None:
            item["_alerte_lot"] = (
                f"⚠️ Aucun lot n° {numero} dans ce potager — rien n'est rattaché. "
                "Confirmez pour enregistrer sans lot, ou annulez."
            )
            log.info("[US-209 / CA6] Lot n° %s inconnu (potager %s)", numero, ctx.potager_id)
            continue

        culture_dite = item.get("culture")
        if culture_dite and normaliser_culture(culture_dite) != normaliser_culture(lot["culture"] or ""):
            nom_lot = f"{lot['culture']} {lot['variete']}" if lot.get("variete") else lot["culture"]
            item["_alerte_lot"] = (
                f"⚠️ Le lot n° {numero} est un lot de *{nom_lot}*, pas de *{culture_dite}* — "
                "rien n'est rattaché. Confirmez pour enregistrer sans lot, ou annulez."
            )
            log.info("[US-209 / CA6] Lot n° %s contredit la culture dite (%s ≠ %s)", numero, culture_dite, lot["culture"])
            continue

        item["_lot_numero"] = numero
        if not item.get("culture"):
            item["culture"] = lot["culture"]
        if not item.get("variete") and lot.get("variete"):
            item["variete"] = lot["variete"]
        if action == "plantation":
            ids = svc_stock.ids_godets_du_lot(db, ctx, lot["semis_id"])
            if ids:
                item["source_evenement_ids"] = ";".join(str(i) for i in ids)
        else:
            if action == "perte":
                item["action"] = "perte_godet"   # un lot ne vit qu'en pépinière
            item["origine_graines_id"] = lot["semis_id"]
        log.info("[US-209 / CA5] Geste %s rattaché au lot n° %s (semis %s)", action, numero, lot["semis_id"])


def controler_emplacements_godets(db: Session, ctx: TenantContext, items: list[dict]) -> None:
    """[US-210 / CA1, CA2] Une mise en godet ne se pose que dans une pépinière.

    Mute les items en place. Pour une mise en godet qui nomme une parcelle :

      - pépinière du potager → le nom canonique est retenu ;
      - parcelle ordinaire → la parcelle est RETIRÉE et `_alerte_emplacement` propose
        les pépinières du potager ou « sans emplacement » : le jardinier confirme sans
        emplacement, ou annule et redicte. Jamais enregistrée sur une parcelle ordinaire ;
      - parcelle inconnue → laissée telle quelle, c'est le contrôle d'existence habituel.

    Une mise en godet qui ne nomme rien reste sans parcelle : rien n'est déduit.
    """
    for item in items:
        if not isinstance(item, dict) or normalize_action(item.get("action")) != "mise_en_godet":
            continue
        nom = item.get("parcelle")
        if not nom:
            continue
        parcelle = resolve_parcelle(db, nom, potager_id=ctx.potager_id)
        if parcelle is None:
            continue
        if parcelle.est_pepiniere:
            item["parcelle"] = parcelle.nom
            continue
        pepinieres = [p.nom for p in get_all_parcelles(db, potager_id=ctx.potager_id) if p.est_pepiniere]
        item.pop("parcelle", None)
        propositions = (
            "Pépinières du potager : " + ", ".join(f"*{n}*" for n in pepinieres) + ". "
            if pepinieres else "Ce potager n'a pas encore de pépinière. "
        )
        item["_alerte_emplacement"] = (
            f"⚠️ *{parcelle.nom}* n'est pas une pépinière : on n'y pose pas de godets. "
            f"{propositions}Confirmez pour enregistrer sans emplacement, ou annulez et redites-le."
        )
        log.info("[US-210 / CA2] Mise en godet sur %r refusée : parcelle ordinaire", parcelle.nom)


#: Nombre de lots listés par `/lot` : les plus récents, le filtre par culture fait le reste.
LIMITE_LISTE_LOTS = 15


def _lot_epuise(lot: dict) -> bool:
    return lot.get("stock_residuel_godet", 0) <= 0 and lot.get("graines_en_germination", 0) <= 0


def formater_liste_lots_telegram(lots: list[dict], culture: Optional[str] = None) -> str:
    """[US-209] Liste des lots numérotés du potager — de quoi retrouver un numéro oublié.

    Tous les lots y figurent, les épuisés marqués ⚪ (les autres 🟢). Les plus récents
    d'abord, `LIMITE_LISTE_LOTS` au plus ; `culture` filtre. Le lot « godets sans semis
    rattaché » n'a pas de numéro et n'est pas listé.
    """
    numerotes = [l for l in lots if l.get("numero_lot") is not None]
    if culture:
        voulue = normaliser_culture(culture)
        numerotes = [l for l in numerotes if normaliser_culture(l.get("culture") or "") == voulue]
    if not numerotes:
        return f"Aucun lot de {culture} dans ce potager." if culture else "Aucun lot de pépinière dans ce potager."
    numerotes.sort(key=lambda l: (str(l.get("date_semis") or ""), l["numero_lot"]), reverse=True)
    affiches = numerotes[:LIMITE_LISTE_LOTS]
    titre = f"🌱 *Lots de {culture}*" if culture else "🌱 *Lots de pépinière*"
    lignes = [f"{titre} — {len(affiches)} sur {len(numerotes)}, du plus récent au plus ancien"]
    for lot in affiches:
        nom = lot["culture"] + (f" {lot['variete']}" if lot.get("variete") else "")
        morceaux = [f"*n° {lot['numero_lot']}* {nom}"]
        if lot.get("date_semis"):
            jour = str(lot["date_semis"])[:10]
            morceaux.append(f"semé le {jour[8:10]}/{jour[5:7]}")
        nom_emp = (lot.get("emplacement") or {}).get("nom")
        if nom_emp:
            morceaux.append(nom_emp)
        if _lot_epuise(lot):
            morceaux.append("épuisé")
        else:
            restes = f"{lot['stock_residuel_godet']} plants"
            if lot.get("graines_en_germination"):
                restes += f" + {lot['graines_en_germination']} graines à lever"
            morceaux.append(restes)
        lignes.append(f"{'⚪' if _lot_epuise(lot) else '🟢'} " + " · ".join(morceaux))
    if len(numerotes) > len(affiches):
        lignes.append(f"… et {len(numerotes) - len(affiches)} plus anciens : /lot <culture> pour filtrer.")
    lignes.append("Détail d'un lot : /lot <numéro>")
    return "\n".join(lignes)


def formater_lot_telegram(lot: dict) -> str:
    """[US-209 / CA7] Fiche d'un lot en Markdown Telegram — zéro jeton."""
    nom = lot["culture"] + (f" {lot['variete']}" if lot.get("variete") else "")
    lignes = [f"🌱 *Lot n° {lot['numero_lot']} — {nom}*"]
    if lot.get("date_semis"):
        lignes.append(f"📅 Semé le *{str(lot['date_semis'])[:10]}*")
    emplacement = lot.get("emplacement") or {}
    if emplacement.get("nom"):   # [US-210 / CA5] emplacement COURANT du lot
        lignes.append(f"📍 Emplacement : *{emplacement['nom']}*")
    elif lot.get("parcelle"):
        lignes.append(f"📍 Emplacement : *{lot['parcelle']}*")
    else:
        lignes.append("📍 Emplacement : non précisé")
    lignes.append(f"🫘 Graines semées : *{lot['graines_semees']}*")
    lignes.append(f"🪴 Plants obtenus : *{lot['plants_obtenus']}*")
    lignes.append(f"📦 Plants restants : *{lot['stock_residuel_godet']}*")
    if lot.get("graines_en_germination"):
        lignes.append(f"⏳ Graines pas encore levées : *{lot['graines_en_germination']}*")
    if lot.get("incoherence_saisie"):
        lignes.append("⚠️ Plus de plants que de graines semées : à vérifier.")
    return "\n".join(lignes)
