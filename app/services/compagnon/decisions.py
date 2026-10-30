"""
app/services/compagnon/decisions.py — Répondre à une proposition par une phrase [US-260]
========================================================================================
« Vas-y », « non 4 rangs », « laisse tomber » : le jardinier répond à une proposition
sans chercher le bouton, surtout à la voix. Ce module est la seule référence de ce
qu'une phrase a le droit de décider (arbitrage B3 de l'architecture).

La confirmation par phrase passe UNIQUEMENT par un outil, `confirmer_proposition(id)`,
validé contre l'identifiant de la proposition en cours : le texte du modèle seul ne
confirme rien. Les règles sont ici, déterministes, et ne dépendent pas de ce que le
modèle écrit :

* l'identifiant doit être celui de la proposition en attente — ou de la dernière
  traitée, pour répondre « elle l'a déjà été » sans rien refaire (CA1, CA5) ;
* une action DESTRUCTRICE — supprimer une parcelle, la mettre hors service — ne se
  confirme qu'au bouton ; une phrase reçoit l'invitation d'y cliquer (CA3) ;
* sans proposition, ou avec deux candidates, rien ne s'exécute et le compagnon
  demande laquelle (CA4) ;
* une proposition qui attend encore une précision (un nom, une valeur) n'est pas
  prête : elle se complète avant de se confirmer ;
* une phrase qui dit AUTRE CHOSE que la proposition — un nombre, une valeur, une
  parcelle qu'elle ne porte pas — la change : « non 4 rangs » est une correction, pas
  un abandon, et « oui, 4 rangs » ne confirme pas l'ancienne valeur (CA2).

L'abandon n'a aucune de ces restrictions de sécurité : il ne fait rien, il est toujours
permis — sauf qu'une phrase qui corrige est d'abord renvoyée à l'outil de commande.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

ACTION_CONFIRMER = "confirmer"
ACTION_ABANDONNER = "abandonner"
ACTIONS: tuple[str, ...] = (ACTION_CONFIRMER, ACTION_ABANDONNER)

#: Les états d'une proposition sortie de l'attente, au féminin, tels qu'on les dit.
_ETATS_DITS = {
    "confirmee": "confirmée",
    "abandonnee": "abandonnée",
    "remplacee": "remplacée par une nouvelle",
    "perimee": "périmée",
}
_CANAUX_DITS = {"telegram": "dans Telegram", "pwa": "dans l'application"}

#: [CA3] Ce que reçoit une phrase qui confirme une action destructrice.
TEXTE_BOUTON_SEUL = (
    "🔒 Cette action est définitive : je ne la lance pas sur un mot. "
    "Appuie sur ✅ Confirmer sous la carte ci-dessous, ou sur ❌ pour laisser tomber."
)
#: [CA4] « Ok » sans rien en attente : rien ne s'exécute, le compagnon demande.
TEXTE_RIEN_EN_ATTENTE = "Je n'ai rien en attente de ta part. Que veux-tu que je fasse ?"
#: [CA4] Deux propositions candidates : on ne choisit jamais à la place du jardinier.
TEXTE_DEUX_CANDIDATES = (
    "Deux propositions attendent ta réponse, dans des potagers différents : {liste}. "
    "Laquelle veux-tu ? Réponds avec le bouton de sa carte."
)
TEXTE_UNE_AILLEURS = (
    "Rien n'attend dans ce potager, mais une proposition attend dans un autre : {liste}. "
    "Réponds avec le bouton de sa carte."
)
#: Une proposition qui attend un nom ou une valeur n'est pas prête à être confirmée.
TEXTE_PAS_PRETE = (
    "Il me manque encore une information pour cette demande : réponds à la question "
    "de la carte, ou choisis avec ses boutons."
)
TEXTE_ABANDONNEE = "❌ Laissé tomber — rien n'a été fait."
#: [CA2] « Oui, 4 rangs » : la phrase change la proposition ; la confirmer d'un mot lancerait l'ancienne valeur.
TEXTE_VALEUR_A_REPRENDRE = (
    "Tu as dit {valeurs}, et la proposition ne le porte pas : je ne la confirme pas d'un mot. "
    "Redis ta demande en entier, ou appuie sur ✅ Confirmer sous la carte ci-dessous pour la lancer telle quelle."
)


def est_destructrice(proposition) -> bool:
    """[CA3] Supprimer ou mettre hors service : ce qui ne se défait pas d'un mot.

    Une commande, ou un plan dont UNE étape l'est. `actif=non` est l'archivage d'une
    parcelle — la même gravité, par une autre forme de commande.
    """
    etapes = getattr(proposition, "etapes", None)
    if etapes is not None:
        return any(est_destructrice(etape) for etape in etapes)
    forme = getattr(proposition, "forme", None)
    if forme is None:
        return False
    if forme.destructrice:
        return True
    valeurs = getattr(proposition, "valeurs", None) or {}
    if forme.cle == ("parcelle", "modifier"):
        for morceau in (valeurs.get("modification") or "").split():
            cle, _, valeur = morceau.partition("=")
            if cle.strip().lower() == "actif" and valeur.strip().lower() in ("non", "false", "0"):
                return True
    return False


def est_prete(proposition) -> bool:
    """Rien ne manque, aucun nom voisin n'attend de choix : seule la confirmation reste."""
    if getattr(proposition, "etapes", None) is not None:
        return True
    return not (
        getattr(proposition, "manquants", ()) or getattr(proposition, "candidats", ())
        or getattr(proposition, "argument_candidat", None)
        # [US-250] Un mot non compris attend le choix du jardinier : « oui » ne le tranche pas.
        or getattr(proposition, "precision", None)
    )


@dataclass(frozen=True)
class Decision:
    """Ce que le jardinier a décidé, validé par le code : une action et la proposition visée."""

    action: str
    code: str


def heure_locale(instant_utc: datetime) -> str:
    """« 14:32 » à Paris : la base garde des instants UTC naïfs, le jardinier lit l'heure de chez lui."""
    import pytz

    return pytz.utc.localize(instant_utc).astimezone(pytz.timezone("Europe/Paris")).strftime("%H:%M")


def deja_traitee(etat: str, traite_le: Optional[datetime], canal: Optional[str]) -> str:
    """[CA5] « Elle a déjà été confirmée à 14:32, dans Telegram — je ne refais rien. »"""
    dit = _ETATS_DITS.get(etat, etat)
    quand = f" à {heure_locale(traite_le)}" if traite_le is not None else ""
    ou = f", {_CANAUX_DITS[canal]}" if canal in _CANAUX_DITS else ""
    return f"Cette proposition a déjà été {dit}{quand}{ou} : je ne refais rien."


def valeurs_dites(valeurs: list[str]) -> str:
    """[CA2] Ce que la phrase dit en plus, tel qu'on le cite : « 4 », « mi-ombre »."""
    return ", ".join(f"« {valeur} »" for valeur in valeurs)


def texte_valeur_a_reprendre(valeurs: list[str]) -> str:
    """[CA2] Ce que lit le jardinier dont « oui, 4 rangs » voulait confirmer une proposition qu'il change."""
    return TEXTE_VALEUR_A_REPRENDRE.format(valeurs=valeurs_dites(valeurs))


def liste_candidates(descriptions: list[str]) -> str:
    """[CA4] Les propositions candidates, nommées : une seule dans un autre potager, ou plusieurs."""
    if len(descriptions) == 1:
        return TEXTE_UNE_AILLEURS.format(liste=descriptions[0])
    return TEXTE_DEUX_CANDIDATES.format(liste=" ; ".join(descriptions))
