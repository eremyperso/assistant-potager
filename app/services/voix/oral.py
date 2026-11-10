"""
app/services/voix/oral.py — résumé parlé d'une réponse du compagnon [US-303]
============================================================================
Décision D6 de l'ÉPIC 17 : Gaston ne lit pas son écran, il dit l'essentiel en une ou deux
phrases. Le résumé est produit à partir du SEUL `texte_compagnon` de l'échange, calculé à la
première demande de lecture puis gardé dans `echanges_conversation.texte_oral` (CA7).

Trois chemins, du moins cher au plus cher :

1. **déjà calculé** (`texte_oral`) : repris tel quel, sans appel (CA7) ;
2. **réponse déjà courte** (sous le plafond, sans Markdown, sans carte) : le texte nettoyé,
   sans appel au modèle (CA5) ;
3. **appel `oral`** par la passerelle (mesure, journal, mode dégradé — CA9), dont la sortie est
   CONTRÔLÉE : aucun chiffre, nom, mois ou jour absent du texte (CA2), ni Markdown, émoji, lien
   ou crochet (CA3), et pour une carte « Je vous propose … : confirmez à l'écran », jamais
   « c'est enregistré » (CA4). Une sortie refusée cède la place au repli.

Repli (CA6) : le texte affiché, nettoyé, coupé à la dernière phrase complète sous le plafond ;
l'issue est journalisée, aucune erreur n'est montrée. Un repli dû à un modèle INDISPONIBLE n'est
pas gardé : la lecture suivante retentera le modèle. Un repli dû à une sortie refusée l'est.

Le prompt de l'agent n'est pas modifié : le résumé est un appel à part, après coup.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from app import config
from app.services.compagnon import conversations as svc_conversations
from app.services.context import TenantContext
from app.services.voix.nettoyage import nettoyer_pour_voix
from llm import passerelle
from llm.passerelle import LLMIndisponibleError

log = logging.getLogger("potager")

# Issues du résumé, journalisées (CA6).
ISSUE_DEJA_CALCULE = "deja_calcule"
ISSUE_COURT = "court"
ISSUE_MODELE = "modele"
ISSUE_REPLI_INDISPONIBLE = "repli_indisponible"
ISSUE_REPLI_REFUSE = "repli_refuse"

PROMPT_FIXE = """Tu prépares ce que Gaston, le compagnon d'un jardinier, va DIRE à voix haute.
On te donne le texte de sa réponse, affiché à l'écran. Tu en écris la version parlée.

Règles, sans exception :
- Une ou deux phrases courtes, naturelles, comme dites de vive voix.
- Reprends UNIQUEMENT ce que dit le texte : aucun fait, chiffre, date, nom, lieu ou conseil qui n'y figure pas. En cas de doute, retire.
- Ni Markdown, ni émoji, ni lien, ni liste, ni texte entre crochets.
- Écris les nombres et les unités pour qu'ils se disent : « 2,5 kg » devient « deux kilos et demi », « 3 cm » devient « trois centimètres ».
- Garde le tutoiement ou le vouvoiement du texte.
- Si le texte propose une action que le jardinier doit encore confirmer (une carte), dis : « Je vous propose … : confirmez à l'écran. » (« Je te propose … : confirme à l'écran. » si le texte tutoie). Ne dis jamais que c'est enregistré, noté ou fait.
- Réponds par le seul texte à dire, sans guillemets ni préambule."""

# ── Nettoyage pour l'oral (CA3) ─────────────────────────────────────────────────
_CROCHETS = re.compile(r"\[[^\]]*\]")
_MARKDOWN = re.compile(r"(^|\n)\s*(#{1,6}\s|[-*•]\s|\d+[.)]\s|>)|\*\*|__|`|\[[^\]]+\]\([^)]+\)|\|")
_LIEN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMOJI = re.compile(r"[\U0001F300-\U0001FFFF\U00002600-\U000027BF]")
_UNITES = [
    (re.compile(r"(?<=\d)\s*°\s*C\b"), " degrés"),
    (re.compile(r"(?<=\d)\s*km/h\b"), " kilomètres à l'heure"),
    (re.compile(r"(?<=\d)\s*m²"), " mètres carrés"),
    (re.compile(r"(?<=\d)\s*kg\b"), " kilos"),
    (re.compile(r"(?<=\d)\s*cm\b"), " centimètres"),
    (re.compile(r"(?<=\d)\s*mm\b"), " millimètres"),
    (re.compile(r"(?<=\d)\s*g\b"), " grammes"),
    (re.compile(r"(?<=\d)\s*[lL]\b"), " litres"),
    (re.compile(r"(?<=\d)\s*m\b"), " mètres"),
    (re.compile(r"(?<=\d)\s*%"), " pour cent"),
]
_FIN_DE_PHRASE = re.compile(r"(?<=[.!?…])\s+")


def nettoyer_oral(texte: str) -> str:
    """[CA3] Texte prêt à dire : sans Markdown, émoji, lien ni crochet ; unités écrites en mots."""
    texte = nettoyer_pour_voix(texte or "")
    texte = _CROCHETS.sub(" ", texte)
    for motif, mot in _UNITES:
        texte = motif.sub(mot, texte)
    return re.sub(r"\s+", " ", texte).strip()


def a_du_markdown(texte: str) -> bool:
    """[CA5] Le texte porte-t-il une mise en forme d'écran (titre, liste, gras, lien, tableau, émoji) ?"""
    return bool(_MARKDOWN.search(texte or "") or _LIEN.search(texte or "") or _EMOJI.search(texte or ""))


def couper(texte: str, plafond: int) -> str:
    """[CA6] Coupe à la dernière phrase complète sous le plafond ; à défaut, au dernier mot, avec un point."""
    texte = (texte or "").strip()
    if len(texte) <= plafond:
        return texte
    retenu = ""
    for phrase in _FIN_DE_PHRASE.split(texte):
        candidat = f"{retenu} {phrase}".strip()
        if len(candidat) > plafond:
            break
        retenu = candidat
    if retenu:
        return retenu
    mots = texte[:plafond - 1].rsplit(" ", 1)[0].rstrip(" ,;:")
    return mots + "."


# ── Ce que porte l'échange ──────────────────────────────────────────────────────
_PREFIXE_PROPOSITION = re.compile(r"^\s*proposition\s*:\s*", re.IGNORECASE)
_TUTOIEMENT = re.compile(r"\b(tu|toi|ton|ta|tes|t'|te)\b", re.IGNORECASE)


def porte_une_carte(echange) -> bool:
    """[CA4] La réponse a-t-elle laissé une proposition à confirmer ?"""
    return bool(
        getattr(echange, "proposition_id", None)
        or "geste" in (getattr(echange, "outils", None) or [])
        or _PREFIXE_PROPOSITION.match(getattr(echange, "texte_compagnon", "") or "")
    )


def tutoie(texte: str) -> bool:
    return bool(_TUTOIEMENT.search(texte or ""))


def repli_proposition(texte: str, plafond: int) -> str:
    """[CA4, CA6] Une carte dite sans modèle : « Je vous propose d'enregistrer … : confirmez à l'écran. »"""
    objet = nettoyer_oral(_PREFIXE_PROPOSITION.sub("", texte or "")).rstrip(" .")
    if _PREFIXE_PROPOSITION.match(texte or ""):
        objet = f"d'enregistrer {objet[:1].lower()}{objet[1:]}" if objet else ""
    elif objet:
        objet = "ceci"
    vous = not tutoie(texte)
    debut, fin = ("Je vous propose", "confirmez à l'écran.") if vous else ("Je te propose", "confirme à l'écran.")
    phrase = f"{debut} {objet} : {fin}" if objet else f"{debut} une action : {fin}"
    if len(phrase) > plafond:
        phrase = f"{debut} une action : {fin}"
    return phrase


# ── Contrôle de la sortie du modèle (CA2, CA3, CA4) ────────────────────────────
_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")
_MOIS = ("janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre",
         "octobre", "novembre", "decembre")
_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
_DEJA_FAIT = re.compile(
    r"c'est (?:enregistr|not|fait)|c’est (?:enregistr|not|fait)|j'ai (?:enregistr|not)|j’ai (?:enregistr|not)"
    r"|est enregistr|a été enregistr|bien enregistr|bien not", re.IGNORECASE)
_PROPOSE = re.compile(r"^je (?:vous|te) propose\b.*:\s*confirme(?:z)? à l[’']écran\.?$", re.IGNORECASE)


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode().lower()


def _mots(texte: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", _sans_accents(texte)))


_VALEURS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
    "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14,
    "quinze": 15, "seize": 16, "vingt": 20, "vingts": 20, "trente": 30, "quarante": 40,
    "cinquante": 50, "soixante": 60, "cent": 100, "cents": 100, "mille": 1000,
}


def nombres_en_lettres(texte: str) -> set[float]:
    """Les nombres écrits en lettres (« dix-huit », « quatre-vingts », « vingt et un »).
    « un » / « une » seuls sont des articles : ils ne comptent que dans un nombre composé."""
    jetons = re.findall(r"[a-z]+", _sans_accents(texte))
    trouves: set[float] = set()
    groupe: list[str] = []

    def valeur(mots: list[str]) -> float:
        total, courant = 0, 0
        for i, mot in enumerate(mots):
            if mot in ("cent", "cents"):
                courant = max(courant, 1) * 100
            elif mot == "mille":
                total += max(courant, 1) * 1000
                courant = 0
            elif mot in ("vingt", "vingts") and i and mots[i - 1] == "quatre":
                courant += 80 - 4
            else:
                courant += _VALEURS[mot]
        return float(total + courant)

    def clore() -> None:
        utiles = [m for m in groupe if m != "et"]
        while utiles and utiles[-1] == "et":
            utiles.pop()
        if utiles and not (len(utiles) == 1 and utiles[0] in ("un", "une")):
            trouves.add(valeur(utiles))
        groupe.clear()

    for mot in jetons:
        if mot in _VALEURS or (mot == "et" and groupe):
            groupe.append(mot)
        else:
            clore()
    clore()
    return trouves


def _nombres(texte: str) -> set[float]:
    """Tous les nombres d'un texte, en chiffres comme en lettres."""
    chiffres = {float(n.replace(",", ".")) for n in _NOMBRE.findall(texte or "")}
    return chiffres | nombres_en_lettres(texte)


def motif_de_rejet(resume: str, source: str, plafond: int, carte: bool) -> Optional[str]:
    """Pourquoi la sortie du modèle n'est pas dite ; None si elle est fidèle."""
    if not resume.strip():
        return "vide"
    if len(resume) > plafond:
        return "trop_long"
    if a_du_markdown(resume) or _CROCHETS.search(resume):
        return "mise_en_forme"
    nombres_source = _nombres(source)
    for n in sorted(_nombres(resume)):
        # « deux kilos et demi » dit 2,5 : le 2 se lit avant le « demi ».
        if n not in nombres_source and n + 0.5 not in nombres_source:
            return f"chiffre_invente:{n:g}"
    mots_source = _mots(source)
    for mot in _mots(resume):
        if (mot in _MOIS or mot in _JOURS) and mot not in mots_source:
            return f"date_inventee:{mot}"
    # Un nom propre (majuscule hors début de phrase) doit venir du texte.
    for nom in re.findall(r"(?<![.!?…]\s)(?<!^)\b([A-ZÉÈÀÂÎÔÛÇ][\wéèêàâîôûç-]+)", resume.strip()):
        if _sans_accents(nom) not in mots_source and nom.lower() not in ("gaston", "je"):
            return f"nom_invente:{nom}"
    if carte:
        if _DEJA_FAIT.search(resume):
            return "carte_dite_enregistree"
        if not _PROPOSE.match(resume.strip()):
            return "carte_sans_confirmation"
    return None


@dataclass(frozen=True)
class ResumeOral:
    texte: str
    issue: str


class EchangeIntrouvableError(LookupError):
    """[CA8] L'échange n'existe pas pour ce jardinier dans ce potager (la PWA répond 404)."""


def _appeler_modele(ctx: TenantContext, texte: str, carte: bool, plafond: int) -> str:
    nature = "Le texte propose une action à confirmer (carte)." if carte else \
        "Le texte ne propose aucune action à confirmer."
    reponse = passerelle.appeler_chat(
        appel_type=passerelle.TYPE_ORAL, ctx=ctx, prompt_fixe=PROMPT_FIXE,
        prompt_variable=f"\n{nature}\nLongueur maximale : {plafond} caractères.\n",
        message_utilisateur=texte, max_tokens=220, reasoning=False,
    )
    return (reponse.texte or "").strip().strip('"«» ').strip()


def resumer(ctx: TenantContext, texte_compagnon: str, *, carte: bool = False,
            plafond: Optional[int] = None) -> ResumeOral:
    """Le résumé parlé d'un texte du compagnon (sans lecture ni écriture en base)."""
    plafond = plafond or config.VOIX_ORAL_MAX_CARACTERES
    nettoye = nettoyer_oral(texte_compagnon)
    # [CA5] Réponse déjà courte, sans mise en forme ni carte : le texte nettoyé, sans modèle.
    if not carte and len(texte_compagnon or "") <= plafond and not a_du_markdown(texte_compagnon):
        return ResumeOral(nettoye, ISSUE_COURT)

    repli = repli_proposition(texte_compagnon, plafond) if carte else couper(nettoye, plafond)
    try:
        brut = _appeler_modele(ctx, texte_compagnon, carte, plafond)
    except LLMIndisponibleError as e:
        log.warning("🔊 VOIX │ résumé parlé : modèle indisponible (%s) → repli", type(e).__name__)
        return ResumeOral(repli, ISSUE_REPLI_INDISPONIBLE)
    resume = re.sub(r"\s+", " ", brut)
    motif = motif_de_rejet(resume, texte_compagnon, plafond, carte)
    if motif:
        log.warning("🔊 VOIX │ résumé parlé refusé (%s) → repli", motif)
        return ResumeOral(repli, ISSUE_REPLI_REFUSE)
    return ResumeOral(nettoyer_oral(resume), ISSUE_MODELE)


def texte_oral(ctx: TenantContext, echange_id: int) -> ResumeOral:
    """[CA1, CA7, CA8] Le résumé parlé de l'échange, calculé une seule fois puis gardé.

    Lève `EchangeIntrouvableError` pour un échange d'un autre jardinier ou d'un autre potager.
    """
    echange = svc_conversations.lire(ctx, echange_id)
    if echange is None:
        raise EchangeIntrouvableError(echange_id)
    if echange.texte_oral:
        return ResumeOral(echange.texte_oral, ISSUE_DEJA_CALCULE)

    resume = resumer(ctx, echange.texte_compagnon, carte=porte_une_carte(echange))
    if resume.issue != ISSUE_REPLI_INDISPONIBLE and resume.texte:
        svc_conversations.retenir_texte_oral(ctx, echange_id, resume.texte)
    log.info("🔊 VOIX │ résumé parlé │ échange=%s │ %s │ %d caractères",
             echange_id, resume.issue, len(resume.texte))
    return resume
