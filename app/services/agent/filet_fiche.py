"""[US-278] Le filet des caractéristiques de parcelle : quand l'agent ne propose rien.

« ma planche tubercul a une superficie de 20 m2, longueur de 7m et ensoleillement
mi-ombre » : selon le nom de la planche, Ministral 3B proposait la modification,
affichait la liste des parcelles, ou répondait sur les pommes de terre. La phrase
est pourtant lisible sans modèle : une parcelle désignée, et des valeurs de fiche
au vocabulaire fermé (unités, liste d'ensoleillement, points cardinaux).

Le filet passe APRÈS l'agent (ou à sa place quand il est indisponible), jamais
devant : les règles ne lisent toujours que les phrases simples (US-277). Il ne
crée rien et n'écrit rien : il construit l'appel `modifier_parcelle` que le
modèle aurait dû faire, et le validateur habituel en fait la proposition — nom
exact gardé, nom approchant proposé au choix, jamais substitué (US-235 / CA7).
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from typing import Callable, Optional

from unidecode import unidecode

from app.services.agent.catalogue_outils import OUTIL_MODIFIER_PARCELLE
from app.services.agent.validation import (
    NB_CHOIX_MAX,
    ContexteValidation,
    chiffres_non_repris,
    valider_appel,
)
from app.services.interpreteur_commandes import (
    _DESIGNATION_PARCELLE,
    REGLE_FILET_FICHE,
    CommandeInterpretee,
    nombre_en_lettres,
    phrase_sans_noms,
)
from llm.passerelle import AppelOutil
from utils.parcelles import DEFINITIONS_ENSOLEILLEMENT

log = logging.getLogger("potager")

#: [CA7] Ce que lit le jardinier au-dessus du récapitulatif : le texte du code, pas celui du modèle.
TEXTE_FILET = "Je te propose d'enregistrer ces caractéristiques :"

#: [CA9] Une création ne devient jamais une modification, ni une question « Quelle parcelle ? ».
_CREATION = re.compile(r"\b(?:cree[rz]?|creons|ajoute[rz]?|ajoutons|nouvel(?:le)?|nouveau)\b")

#: Ce qui suit le nom désigné : « ma planche tubercul a une superficie… ».
_FIN_DU_NOM = (r"(?=\s+(?:a|fait|fera|mesure|mesurera|est|sera|aura|dispose|disposera|possede"
               r"|comporte|compte|avec|de\s+\d)\b|\s*[,:;.!]|\s+\d|$)")
_NOM_DESIGNE = re.compile(rf"\b{_DESIGNATION_PARCELLE}\s+(?P<nom>.+?){_FIN_DU_NOM}")
_DETERMINANT = re.compile(r"^(?:de\s+la|de\s+l'|du|des|de|d')\s*")


def _nombres_en_lettres() -> dict[str, int]:
    """« dix » → 10 : les nombres de 0 à 100, comme le validateur les accepte (`_nombre_dit`)."""
    table: dict[str, int] = {}
    for n in range(101):
        lettres = unidecode(nombre_en_lettres(str(n)))
        table[lettres] = n
        table[lettres.replace("-", " ")] = n
    return table


_LETTRES = _nombres_en_lettres()
_NOMBRE = (r"(?P<n>\d+(?:[.,]\d+)?|"
           + "|".join(re.escape(m) for m in sorted(_LETTRES, key=len, reverse=True)) + ")")
#: [CA2] Dans cet ordre : une superficie lue n'est plus relue comme une longueur.
_MOTIFS_NOMBRE: tuple[tuple[str, re.Pattern], ...] = (
    ("superficie_m2", re.compile(rf"\b{_NOMBRE}\s*(?:m\s*2|metres?\s+carres?)(?![a-z0-9])")),
    ("longueur_m", re.compile(rf"\b{_NOMBRE}\s*(?:m|metres?)\b(?!\s*carre)")),
    ("nb_rangs", re.compile(rf"\b{_NOMBRE}\s*rangs?\b")),
)
_EXPOSITION = re.compile(
    r"\b(?:exposee?s?|exposition|orientee?s?|orientation)\s*:?\s*"
    r"(?:en\s+plein\s+|plein\s+|au\s+|a\s+l'\s*|a\s+|vers\s+(?:le\s+)?)?(?P<v>sud|nord|est|ouest)\b"
)


def _norme(texte: str) -> str:
    return unidecode((texte or "").replace("’", "'").lower())


def _motif_ensoleillement(valeur: str) -> re.Pattern:
    return re.compile(r"(?<![a-z])" + r"[\s-]*".join(map(re.escape, re.split(r"[\s-]+", _norme(valeur))))
                      + r"(?![a-z])")


#: Les plus longues d'abord : « mi-ombre » avant « ombre ».
_ENSOLEILLEMENTS: tuple[tuple[str, re.Pattern], ...] = tuple(
    (valeur, _motif_ensoleillement(valeur))
    for valeur in sorted(DEFINITIONS_ENSOLEILLEMENT, key=len, reverse=True)
)


def _nombre(brut: str) -> int | float:
    if brut in _LETTRES:
        return _LETTRES[brut]
    valeur = float(brut.replace(",", "."))
    return int(valeur) if valeur.is_integer() else valeur


def lire_valeurs(texte: str) -> dict[str, object]:
    """[CA2] Les valeurs de fiche que la phrase dit, lues sans modèle et sans déduction.

    `texte` est déjà privé du nom de la parcelle. Un mètre sans « carré » est une
    longueur ; une exposition se lit après « exposé(e) » ou « exposition » seulement
    (« planche Est » est un nom, pas une orientation).
    """
    reste = _norme(texte)
    valeurs: dict[str, object] = {}
    for champ, motif in _MOTIFS_NOMBRE:
        trouve = motif.search(reste)
        if trouve:
            valeurs[champ] = _nombre(trouve.group("n"))
            reste = reste[:trouve.start()] + " " + reste[trouve.end():]
    for valeur, motif in _ENSOLEILLEMENTS:
        if motif.search(reste):
            valeurs["ensoleillement"] = valeur
            break
    trouve = _EXPOSITION.search(reste)
    if trouve:
        valeurs["exposition"] = trouve.group("v").capitalize()
    return valeurs


def _forme_du_nom(nom: str) -> re.Pattern:
    mots = re.findall(r"[a-z0-9]+", _norme(nom))
    return re.compile(r"(?<![a-z0-9])" + r"[\s-]*".join(mots) + r"(?![a-z0-9])")


def parcelle_dite(texte: str, noms_parcelles: tuple[str, ...]) -> Optional[str]:
    """Le nom exact d'une parcelle du potager que la phrase dit, le plus long d'abord."""
    phrase = _norme(texte)
    for nom in sorted(noms_parcelles, key=len, reverse=True):
        if re.findall(r"[a-z0-9]+", _norme(nom)) and _forme_du_nom(nom).search(phrase):
            return nom
    return None


def nom_designe(texte: str) -> Optional[str]:
    """« ma planche tubercul a… » → « tubercul » : ce qui suit le mot qui désigne une parcelle."""
    trouve = _NOM_DESIGNE.search(_norme(texte))
    if not trouve:
        return None
    nom = _DETERMINANT.sub("", trouve.group("nom").strip()).strip()
    return nom or None


@dataclass(frozen=True)
class Filet:
    """La proposition du filet, et ce que lit le jardinier au-dessus."""

    commande: CommandeInterpretee
    texte: str
    #: « nom dit », « nom rapproché », « choix parmi les parcelles », « nom demandé ».
    motif: str


def _hors_filet(phrase: str, noms_parcelles: tuple[str, ...]) -> Optional[str]:
    """[CA9] La raison de ne pas tendre le filet, ou None."""
    from app.services.agent.projection import est_interrogative
    from llm.routeur import annonce_un_geste

    if est_interrogative(phrase):
        return "question"
    if _CREATION.search(_norme(phrase)):
        return "création"
    if annonce_un_geste(phrase) and annonce_un_geste(phrase_sans_noms(phrase, noms_parcelles)):
        return "geste"
    return None


def proposer(phrase: str, noms_parcelles: tuple[str, ...],
             voisin: Callable[[str], Optional[str]] = lambda nom: None) -> Optional[Filet]:
    """[CA1 → CA5] La proposition `/parcelle modifier` que la phrase dit, ou None.

    None dès qu'une condition du CA1 manque : pas de parcelle désignée, aucune valeur
    de fiche lisible, ou une phrase que le filet ne doit pas prendre (CA9).
    """
    exacte = parcelle_dite(phrase, noms_parcelles)
    designee = None if exacte else nom_designe(phrase)
    if exacte is None and designee is None:
        return None
    sans_nom = phrase_sans_noms(phrase, (exacte,) if exacte else ())
    if designee:
        sans_nom = re.sub(rf"\b{_DESIGNATION_PARCELLE}\s+{re.escape(designee)}\b", " ", _norme(sans_nom))
    valeurs = lire_valeurs(sans_nom)
    if not valeurs:
        return None
    raison = _hors_filet(phrase, noms_parcelles)
    if raison is not None:
        log.info("🛟 FILET          : %s → pas de filet │ %r", raison, phrase[:80])
        return None

    appel = AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": exacte or designee, **valeurs})
    verdict = valider_appel(appel, ContexteValidation(texte=phrase, noms_parcelles=noms_parcelles,
                                                      voisin=voisin))
    commande = verdict.commande
    if commande is None:
        log.info("🛟 FILET          : rejeté par le validateur (%s) │ %r", verdict.motif, phrase[:80])
        return None

    if commande.candidats:
        motif = "nom rapproché"
    elif commande.argument_candidat is not None:
        # [CA5] Aucune parcelle ne s'approche du nom dit : le choix, ou le nom, est demandé.
        if noms_parcelles and len(noms_parcelles) <= NB_CHOIX_MAX:
            commande, motif = replace(commande, candidats=tuple(noms_parcelles)), "choix parmi les parcelles"
        else:
            argument = next(a for a in commande.forme.arguments if a.nom == commande.argument_candidat)
            commande = replace(commande, candidats=(), argument_candidat=None, manquants=(argument,))
            motif = "nom demandé"
    else:
        motif = "nom dit"
    commande = replace(commande, regle=REGLE_FILET_FICHE)

    texte = TEXTE_FILET
    non_places = [str(n).removesuffix(".0") for n in chiffres_non_repris(phrase, [appel])]
    if non_places:
        texte = f"{TEXTE_FILET}\n(Je n'ai pas su placer : {', '.join(non_places)}.)"
    log.info("🛟 FILET          : %s → %s │ %r", motif, commande.commande_equivalente(), phrase[:80])
    return Filet(commande=commande, texte=texte, motif=motif)


def valeurs_non_reprises(phrase: str, appels, noms_parcelles: tuple[str, ...] = ()) -> list[str]:
    """[CA6] Les valeurs de vocabulaire (ensoleillement, exposition) dites et qu'aucun appel
    ne reprend — le pendant de `chiffres_non_repris`, pour la relance d'US-257."""
    valeurs = lire_valeurs(phrase_sans_noms(phrase, noms_parcelles))
    dites = [str(valeurs[champ]) for champ in ("ensoleillement", "exposition") if champ in valeurs]
    repris = {
        _norme(valeur).replace("-", " ")
        for appel in appels for valeur in (appel.arguments or {}).values() if isinstance(valeur, str)
    }
    return [valeur for valeur in dites if _norme(valeur).replace("-", " ") not in repris]
