"""
app/services/agent/validation.py — Le validateur de l'agent [US-235 / CA4 → CA9]
================================================================================
« Le modèle propose, le code dispose. » Chaque appel d'outil passe ici avant
tout affichage. Le validateur est déterministe et se teste sans modèle.

L'ancrage selon la NATURE de la valeur (architecture §2.3) — révision
explicite de CA4 d'US-172 :

  | nature                          | règle                                                       |
  |---------------------------------|-------------------------------------------------------------|
  | entité (parcelle)               | dite dans la phrase ET existante en base, à l'identique     |
  | nombre                          | dit dans la phrase, en chiffres ou en lettres — sinon rejet |
  | valeur fermée (oui/non, liste)  | PEUT être déduite, si le champ a été évoqué — sinon retirée |
  | texte libre, nom choisi         | dit dans la phrase — sinon retiré (et demandé s'il manque)  |

Les règles 1 à 6 et 9 du §3.5 :

  1. schéma : outil connu, propriétés connues, types et listes fermées respectés
     — sinon rejet. Une propriété inconnue (un `potager_id` inventé) est un rejet ;
  2. entités : un nom exact est gardé ; un nom voisin ou déduit est PROPOSÉ,
     jamais substitué (CA12 d'US-172) ; un nom inconnu demande une précision ;
  3. nombres : dits, ou rejet ;
  4. destructrice : nom exact et dit — la règle 2 l'assure pour toute commande,
     et `_resoudre_noms_parcelle` (bot) le revérifie avant l'affichage ;
  5. droits : contrôlés à l'exécution par le handler, comme aujourd'hui ;
  6. potager : celui du contexte, toujours — aucune propriété ne le porte ;
  9. valeur fermée : gardée seulement si son champ est évoqué.

S'y ajoute la leçon de la mesure d'US-233 : « renomme la planche nord » a donné
`Planche Nord → Planche Nord`. Un argument qui n'est que la COPIE d'un autre
argument n'est pas une valeur dite : il est retiré, et la complétion le demande.

Un rejet rend `None` : la phrase poursuit son chemin habituel (routeur,
cascade), exactement comme une sortie non conforme de l'ancien repli.

[US-237] Un PLAN (plusieurs écritures dans une phrase) ajoute la règle 7 : les
étapes sont validées dans l'ordre contre un état SIMULÉ — une parcelle créée à
l'étape *n* existe pour les suivantes, une création sur un nom déjà pris est
signalée. Un plan qui ne peut pas être proposé tel quel n'est jamais rendu à
l'ancien chemin : la phrase porte plusieurs demandes, et la règle ou le
routeur n'en verraient qu'une. Une précision est demandée à la place.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from typing import Callable, Optional

from app.services.agent import adaptateurs
from app.services.agent.catalogue_outils import (
    CHAMP_TYPE_PEPINIERE,
    OUTIL_MODIFIER_PARCELLE,
    ChampFiche,
    Outil,
    champs_fiche,
    outils_par_nom,
)
from app.services.interpreteur_commandes import (
    ORIGINE_AGENT,
    CommandeInterpretee,
    Plan,
    _construire_commande,
    nombre_en_lettres,
    normaliser,
)
from app.services.menu_commandes import (
    TYPE_NOMBRE,
    TYPE_PARCELLE,
    TYPE_VOCABULAIRE,
    Argument,
    FormeCommande,
)

log = logging.getLogger("potager")


@dataclass(frozen=True)
class ContexteValidation:
    """Ce que le validateur sait du monde : la phrase et les parcelles du potager.

    `voisin` rend le nom d'une parcelle VOISINE d'un nom inexact (le
    rapprochement habituel, `resolve_parcelle`), ou None.
    """

    texte: str
    noms_parcelles: tuple[str, ...] = ()
    voisin: Callable[[str], Optional[str]] = lambda nom: None


@dataclass(frozen=True)
class Verdict:
    """Le résultat de la validation d'UN appel d'outil."""

    commande: Optional[CommandeInterpretee] = None
    #: "ok", "aiguillage", ou la raison du rejet — écrite au journal.
    motif: str = "ok"
    #: [CA6] Champs fermés retirés faute d'avoir été évoqués.
    retires: tuple[str, ...] = field(default=())


class _Rejet(Exception):
    """Une valeur non conforme : l'appel entier est rejeté, rien n'est rattrapé."""


# ═════════════════════════════════════════════════════════════════════════════
# Ce que dit la phrase
# ═════════════════════════════════════════════════════════════════════════════
def _mots(texte: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normaliser(texte or "")[0])


def _compact(texte: str) -> str:
    """La normalisation des noms de parcelle (casse, accents, espaces, tirets)."""
    from utils.parcelles import normalize_parcelle_name

    return normalize_parcelle_name(texte or "")


def _evoque(termes: list[str], mots_phrase: list[str]) -> bool:
    """[CA6, règle 9] Un terme du champ (son nom, un libellé, une valeur) est-il dit ?

    Comparaison sur les quatre premières lettres, pour que « paillée » évoque le
    paillage et « rang » le nombre de rangs, sans liste de tournures. Un mot de
    trois lettres ou moins se compare entier (« sud », « est »).
    """
    for terme in termes:
        for mot in _mots(terme):
            racine = mot[:4] if len(mot) > 4 else mot
            if any(m.startswith(racine) for m in mots_phrase):
                return True
    return False


def _termes_du_nom(nom: str) -> list[str]:
    """Les mots d'un nom de champ assez longs pour signifier quelque chose
    (`est_pepiniere` → « pepiniere » ; « est » dirait n'importe quelle phrase)."""
    return [mot for mot in re.split(r"[_\s]+", nom) if len(mot) >= 4]


def _nombre_dit(valeur: float, texte: str) -> bool:
    """[CA5, règle 3] Le nombre figure dans la phrase, en chiffres ou en lettres."""
    for brut in re.findall(r"\d+(?:[.,]\d+)?", texte or ""):
        if abs(float(brut.replace(",", ".")) - valeur) < 1e-9:
            return True
    lettres = " ".join(_mots(nombre_en_lettres(adaptateurs.texte_nombre(valeur))))
    phrase = " ".join(_mots(texte))
    return bool(lettres) and f" {lettres} " in f" {phrase} "


_MOTIF_NOMBRE = re.compile(r"\d+(?:[.,]\d+)?")
#: « 20m2 » / « 20 m² » : le 2 est une unité, pas une quantité.
_MOTIF_UNITE_CARREE = re.compile(r"(?<=\d)\s*m(?:2|²)(?!\d)")


def _nombres_de(texte: str) -> set[float]:
    sans_unite = _MOTIF_UNITE_CARREE.sub(" m ", texte or "")
    return {float(brut.replace(",", ".")) for brut in _MOTIF_NOMBRE.findall(sans_unite)}


def chiffres_non_repris(texte: str, appels) -> list[float]:
    """[INC-018] Les nombres que la phrase dit et qu'AUCUN appel ne reprend.

    « crée la planche nord de 20m2 et de longueur 2 m » : l'agent n'a appelé que la création
    (superficie 20) ; le 2 est une demande perdue. Un nombre dit mais absent des arguments est
    le signe, bon marché et sans modèle, qu'il reste quelque chose à demander. Faux positif
    possible (« dans 3 jours ») : il coûte un tour de plus, jamais une écriture.
    """
    repris: set[float] = set()
    for appel in appels:
        for valeur in (appel.arguments or {}).values():
            if isinstance(valeur, bool):
                continue
            if isinstance(valeur, (int, float)):
                repris.add(float(valeur))
            elif isinstance(valeur, str):
                repris |= _nombres_de(valeur)
    return sorted(_nombres_de(texte) - repris)


def _nombre(valeur, entier: bool = False) -> float:
    if isinstance(valeur, bool):
        raise _Rejet("booléen à la place d'un nombre")
    if isinstance(valeur, str):
        try:
            valeur = float(valeur.strip().replace(",", "."))
        except ValueError:
            raise _Rejet(f"{valeur!r} n'est pas un nombre")
    if not isinstance(valeur, (int, float)):
        raise _Rejet(f"{valeur!r} n'est pas un nombre")
    if entier and float(valeur) != int(valeur):
        raise _Rejet(f"{valeur!r} n'est pas un entier")
    return float(valeur)


def _dans_liste(valeur, vocabulaire: tuple[str, ...]) -> str:
    """La valeur canonique de la liste fermée, ou rejet (règle 1)."""
    if not isinstance(valeur, str):
        raise _Rejet(f"{valeur!r} hors de la liste fermée")
    cible = normaliser(valeur.strip())[0]
    for entree in vocabulaire:
        if normaliser(entree)[0] == cible:
            return entree
    raise _Rejet(f"{valeur!r} hors de la liste fermée")


def _texte(valeur) -> str:
    if not isinstance(valeur, (str, int, float)) or isinstance(valeur, bool):
        raise _Rejet(f"{valeur!r} n'est pas un texte")
    return str(valeur).strip()


# ═════════════════════════════════════════════════════════════════════════════
# Les deux familles d'outils
# ═════════════════════════════════════════════════════════════════════════════
def _phrase_sans(texte: str, noms: list[str]) -> list[str]:
    """Les mots de la phrase, privés de ceux du nom de parcelle : « Serre
    extérieure » ne doit pas évoquer l'abri `serre` à elle seule."""
    phrase = normaliser(texte)[0]
    for nom in noms:
        if nom:
            phrase = phrase.replace(normaliser(nom)[0], " ")
    return re.findall(r"[a-z0-9]+", phrase)


def _valeurs_modifier_parcelle(
    arguments: dict, contexte: ContexteValidation
) -> tuple[dict[str, str], list[str]]:
    """[CA2, CA5, CA6] Les champs typés de `parcelle_modifier` → valeurs de la commande."""
    nom = arguments.get("parcelle")
    mots = _phrase_sans(contexte.texte, [str(nom or "")])
    retenus: list[tuple[ChampFiche, object]] = []
    retires: list[str] = []
    for champ in champs_fiche():
        valeur = arguments.get(champ.nom)
        if valeur is None or valeur == "":
            continue
        if champ.type_json == "boolean":
            if not isinstance(valeur, bool):
                raise _Rejet(f"{champ.nom} : {valeur!r} n'est pas un oui / non")
        elif champ.type_json in ("integer", "number"):
            valeur = _nombre(valeur, entier=champ.type_json == "integer")
            if not _nombre_dit(valeur, contexte.texte):
                raise _Rejet(f"{champ.nom} : {adaptateurs.texte_nombre(valeur)} n'a pas été dit")
            retenus.append((champ, valeur))
            continue
        elif champ.vocabulaire:
            valeur = _dans_liste(valeur, champ.vocabulaire)
        else:  # pragma: no cover — tout champ texte de la fiche a une liste
            valeur = _texte(valeur)
        # Valeur FERMÉE (oui / non ou liste) : déductible, si le champ est évoqué.
        termes = [champ.libelle, *_termes_du_nom(champ.nom), champ.cle, *champ.vocabulaire]
        if champ.nom == CHAMP_TYPE_PEPINIERE:
            # Le type n'est évoqué que par lui-même : dans « mets la serre en
            # pépinière », le mot « pépinière » ne dit ni chaude ni froide (règle 9).
            termes = list(champ.vocabulaire)
        if not _evoque(termes, mots):
            retires.append(champ.nom)
            continue
        retenus.append((champ, valeur))

    valeurs: dict[str, str] = {}
    if nom:
        valeurs["nom"] = _texte(nom)
    modification = adaptateurs.modification_parcelle(retenus)
    if modification:
        valeurs["modification"] = modification
    return valeurs, retires


def _valeurs_commande(
    outil: Outil, forme: FormeCommande, arguments: dict, contexte: ContexteValidation
) -> tuple[dict[str, str], list[str]]:
    """Les arguments d'une forme du catalogue, chacun ancré selon sa nature."""
    noms_parcelle = [
        str(arguments.get(outil.propriete(forme, a.nom)) or "")
        for a in forme.arguments if a.type == TYPE_PARCELLE
    ]
    mots = _phrase_sans(contexte.texte, noms_parcelle)
    phrase = normaliser(contexte.texte)[0]
    valeurs: dict[str, str] = {}
    retires: list[str] = []
    for argument in forme.arguments:
        valeur = arguments.get(outil.propriete(forme, argument.nom))
        if valeur is None or valeur == "":
            continue
        if argument.type == TYPE_NOMBRE:
            nombre = _nombre(valeur)
            if not _nombre_dit(nombre, contexte.texte):
                raise _Rejet(f"{argument.nom} : {adaptateurs.texte_nombre(nombre)} n'a pas été dit")
            valeurs[argument.nom] = adaptateurs.texte_nombre(nombre)
        elif argument.type == TYPE_VOCABULAIRE:
            canonique = _dans_liste(valeur, argument.vocabulaire)
            if _evoque([*_termes_du_nom(argument.nom), *argument.vocabulaire], mots):
                valeurs[argument.nom] = canonique
            else:
                retires.append(argument.nom)
        elif argument.type == TYPE_PARCELLE:
            valeurs[argument.nom] = _texte(valeur)  # tranchée par `_resoudre_entites`
        else:
            texte = _texte(valeur)
            if normaliser(texte)[0] in phrase:
                valeurs[argument.nom] = texte
            else:
                log.info("🤖 AGENT          : %s=%r absent de la phrase → retiré", argument.nom, texte)
                retires.append(argument.nom)
    return valeurs, retires


def _retirer_copies(forme: FormeCommande, valeurs: dict[str, str]) -> list[str]:
    """Un argument identique à un autre n'est pas une valeur dite (mesure US-233) :
    « renomme la planche nord » ne renomme pas Planche Nord en Planche Nord."""
    retires: list[str] = []
    vus: dict[str, str] = {}
    for argument in forme.arguments:
        valeur = valeurs.get(argument.nom)
        if not valeur or argument.type in (TYPE_NOMBRE, TYPE_VOCABULAIRE):
            continue
        cle = _compact(valeur)
        if cle in vus:
            log.info(
                "🤖 AGENT          : %s recopie %s (%r) → retiré", argument.nom, vus[cle], valeur
            )
            del valeurs[argument.nom]
            retires.append(argument.nom)
        else:
            vus[cle] = argument.nom
    return retires


def _resoudre_entites(
    commande: CommandeInterpretee, contexte: ContexteValidation
) -> CommandeInterpretee:
    """[CA4, CA7] Un nom de parcelle exact ET dit est gardé, avec l'écriture de la
    base ; sinon le nom voisin est PROPOSÉ, jamais substitué — y compris quand
    c'est le modèle qui l'a rattaché (« la serre » → « Serre extérieure ») :
    ce rattachement est une déduction, et une entité ne se déduit pas."""
    phrase = _compact(contexte.texte)
    par_cle = {_compact(nom): nom for nom in contexte.noms_parcelles}
    for argument in commande.forme.arguments:
        if argument.type != TYPE_PARCELLE or not commande.valeurs.get(argument.nom):
            continue
        dicte = commande.valeurs[argument.nom]
        exact = par_cle.get(_compact(dicte))
        if exact is not None and _compact(exact) in phrase:
            commande = commande.avec(**{argument.nom: exact})
            continue
        candidat = exact or contexte.voisin(dicte)
        log.info(
            "🤖 AGENT          : parcelle %r %s → %s",
            dicte, "déduite" if exact else "inconnue",
            f"proposée : {candidat!r}" if candidat else "précision demandée",
        )
        return commande.avec_candidats(argument.nom, (candidat,) if candidat else ())
    return commande


# ═════════════════════════════════════════════════════════════════════════════
# API
# ═════════════════════════════════════════════════════════════════════════════
def valider_appel(appel, contexte: ContexteValidation) -> Verdict:
    """[CA4 → CA9] Un appel d'outil → une `CommandeInterpretee` à proposer, ou un refus.

    `appel` est un `llm.passerelle.AppelOutil`. Le seuil de confiance de
    l'ancien repli ne s'applique pas (CA9) : un appel d'outil ne porte pas de
    score, et c'est ce validateur, puis le récapitulatif, qui en tiennent lieu.
    """
    outil = outils_par_nom().get(appel.nom)
    if outil is None:
        return Verdict(motif=f"outil inconnu : {appel.nom}")
    if outil.terminal:
        return Verdict(motif="aiguillage")
    if outil.lecture:
        return Verdict(motif="lecture")
    if not appel.arguments_valides or not isinstance(appel.arguments, dict):
        return Verdict(motif="arguments illisibles")

    connues = set(outil.schema["function"]["parameters"]["properties"])
    inconnues = sorted(set(appel.arguments) - connues)
    if inconnues:
        # [CA8, règle 6] Aucune propriété ne porte le potager : une valeur qui
        # prétendrait le choisir est un rejet, pas un réglage.
        return Verdict(motif=f"propriété(s) inconnue(s) : {', '.join(inconnues)}")

    forme = outil.forme_pour(appel.arguments)
    if forme is None:
        return Verdict(motif=f"{appel.nom} : forme indéterminée")

    try:
        if outil.nom == OUTIL_MODIFIER_PARCELLE:
            valeurs, retires = _valeurs_modifier_parcelle(appel.arguments, contexte)
        else:
            valeurs, retires = _valeurs_commande(outil, forme, appel.arguments, contexte)
    except _Rejet as rejet:
        log.info("🤖 AGENT          : %s rejeté — %s", appel.nom, rejet)
        return Verdict(motif=str(rejet))

    retires += _retirer_copies(forme, valeurs)
    commande = _construire_commande(forme, valeurs, ORIGINE_AGENT, 1.0, contexte.texte)
    commande = replace(commande, outils=(appel.nom,))
    commande = _resoudre_entites(commande, contexte)
    if retires:
        log.info("🤖 AGENT          : champ(s) non évoqué(s) retiré(s) : %s", ", ".join(retires))
    return Verdict(commande=commande, retires=tuple(retires))


# ═════════════════════════════════════════════════════════════════════════════
# [US-237] Le plan — règle 7, état simulé
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class VerdictPlan:
    """Le résultat de la validation de plusieurs appels d'écriture."""

    plan: Optional[Plan] = None
    #: La précision à demander quand le plan ne peut pas être proposé (CA4).
    precision: Optional[str] = None
    #: "ok" ou la raison écrite au journal.
    motif: str = "ok"


def _precision_incomplete(rang: int, commande: CommandeInterpretee) -> str:
    if commande.candidats:
        return (
            f"Étape {rang} ({commande.forme.libelle.lower()}) : aucune parcelle ne porte exactement "
            f"ce nom. Voulais-tu dire « {commande.candidats[0]} » ?"
        )
    if commande.manquants:
        return f"Étape {rang} ({commande.forme.libelle.lower()}) : {commande.manquants[0].question}"
    return f"Étape {rang} ({commande.forme.libelle.lower()}) : quelle parcelle ?"


def valider_plan(appels, contexte: ContexteValidation) -> VerdictPlan:
    """[CA2, CA3, CA4] Plusieurs appels d'écriture → un `Plan`, ou la précision à demander.

    Chaque appel passe par `valider_appel` (règles 1 à 6 et 9), avec la liste
    des parcelles ENRICHIE des créations des étapes précédentes : « mets la
    planche nord à 8 m » est accepté après « crée la planche nord » (CA2, CA3).
    Une création sur un nom déjà pris n'est pas dupliquée : elle est gardée,
    signalée, et sera sautée (`Plan.deja_faites`).
    """
    from app.services.agent.executeurs import CLE_AJOUTER, admise_dans_un_plan

    noms = list(contexte.noms_parcelles)
    etapes: list[CommandeInterpretee] = []
    deja_faites: list[int] = []
    for rang, appel in enumerate(appels, start=1):
        verdict = valider_appel(appel, replace(contexte, noms_parcelles=tuple(noms)))
        commande = verdict.commande
        if commande is None:
            log.info("🤖 AGENT          : plan, étape %d rejetée — %s", rang, verdict.motif)
            return VerdictPlan(
                precision=f"Je n'ai pas su relire l'étape {rang} de ta demande. Redis-la en plusieurs fois.",
                motif=f"étape {rang} : {verdict.motif}",
            )
        if not admise_dans_un_plan(commande):
            # [CA4] Seules les formes qui ont un exécuteur de service entrent dans
            # un plan ; une suppression, notamment, reste une commande seule.
            log.info("🤖 AGENT          : plan, étape %d hors plan — %s", rang, commande.commande_equivalente())
            return VerdictPlan(
                precision=(
                    f"« {commande.forme.libelle} » : je ne sais faire celle-ci que seule. "
                    "Dis-la à part, après le reste."
                ),
                motif=f"étape {rang} hors plan : /{commande.commande} {commande.sous_commande or ''}".strip(),
            )
        if not commande.complete:
            return VerdictPlan(precision=_precision_incomplete(rang, commande), motif=f"étape {rang} incomplète")
        if commande.forme.cle == CLE_AJOUTER:
            nom = commande.valeurs.get("nom", "")
            if _compact(nom) in {_compact(n) for n in noms}:
                log.info("🤖 AGENT          : plan, étape %d — %r existe déjà → signalée", rang, nom)
                deja_faites.append(rang - 1)
            else:
                noms.append(nom)
        etapes.append(commande)
    return VerdictPlan(plan=Plan(tuple(etapes), texte_origine=contexte.texte, deja_faites=tuple(deja_faites)))
