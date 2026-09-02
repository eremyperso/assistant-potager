"""
app/services/menu_commandes.py — Catalogue du menu de commandes Telegram [US-171]
--------------------------------------------------------------------------------
Le menu natif Telegram (bouton « Menu » à gauche de la zone de saisie) remplace
le clavier de raccourcis permanent qui occupait le bas de l'écran. Ce module
décide de **ce que le menu affiche**, jamais de ce que le bot sait faire.

Point de conception central (CA6) : le menu n'est **pas** une liste tenue à la
main. Il se dérive des commandes réellement enregistrées par le bot — une
commande ajoutée à `_construire_application()` apparaît au menu au redémarrage
suivant, sans qu'on ait à y penser. Ce module n'apporte que trois décisions :

* ce qui est **écarté** du menu — `COMMANDES_EXCLUES` (CA3), un seul endroit ;
* dans quel **ordre** les lignes se lisent — `ORDRE_METIER` (CA4) ;
* avec quelle **phrase d'aide** — `DESCRIPTIONS` (CA2).

Aucune dépendance à `python-telegram-bot` ici : la construction du menu se teste
sans bot ni réseau, et `bot.py` se contente de traduire le résultat en
`BotCommand`.
"""

from __future__ import annotations

import logging
from typing import Iterable

log = logging.getLogger("potager")

# Une entrée de menu doit rester lisible d'un coup d'œil sur un écran mobile de
# 375 px sans troncature (CA2). Telegram tolère 256 caractères ; ce n'est pas la
# contrainte technique qui décide ici, c'est la largeur de l'écran du jardinier.
LONGUEUR_MAX_DESCRIPTION = 60

# ── Ce qui n'entre pas au menu — décisions du 02/09/2026 (CA3) ───────────────────
# Liste d'exclusion unique et explicite : une commande nouvellement ajoutée entre
# au menu par défaut, et n'en sort que par une ligne ajoutée ici. Les commandes
# exclues restent pleinement fonctionnelles à la saisie manuelle (CA3bis) — les
# retirer du menu ne les retire pas du bot.
COMMANDES_EXCLUES: frozenset[str] = frozenset({
    "version",  # diagnostic sans usage quotidien ; la version se consulte en ligne
    "delier",   # action rare et destructive : à garder délibérée, pas à mettre en avant
    "tts",      # ne règle rien — affiche l'état puis renvoie vers /tts_on ou /tts_off,
                # donc deux gestes là où une entrée de menu n'en coûte qu'un (CA3ter).
                # Ce sont /tts_on et /tts_off qui entrent au menu.
})

# ── Dans quel ordre le menu se lit (CA4) ────────────────────────────────────────
# Logique métier, jamais l'ordre d'écriture dans le code : les gestes du
# quotidien d'abord, la consultation ensuite, la configuration après, l'aide en
# fin de liste — c'est là qu'on la cherche quand on ne trouve pas le reste.
# Une commande absente de ce tuple se range à la fin, par ordre alphabétique.
ORDRE_METIER: tuple[str, ...] = (
    # Gestes du quotidien
    "note",
    "corriger",
    "vendre",
    # Consultation
    "stats",
    "historique",
    "plan",
    "ask",
    "fiche",
    "association",
    "rotation",
    "meteo",
    # Configuration du potager et du compte
    "parcelle",
    "parcelles",
    "culture",
    "potager",
    "lier",
    "tts_on",
    "tts_off",
    # Découverte
    "start",
    "help",
)

# ── La phrase d'aide d'une ligne (CA2) ──────────────────────────────────────────
# Écrite pour le jardinier, pas pour le développeur : ce que la commande lui
# donne, dans son vocabulaire — celui des domaines métier de l'aide en ligne.
DESCRIPTIONS: dict[str, str] = {
    "note":        "Noter une observation, guidé pas à pas",
    "corriger":    "Corriger ou supprimer un événement",
    "vendre":      "Enregistrer une vente de plants",
    "stats":       "Bilan chiffré de la saison",
    "historique":  "Vos 10 derniers événements",
    "plan":        "Plan d'occupation de vos parcelles",
    "ask":         "Poser une question sur votre potager",
    "fiche":       "Fiche agronomique courte d'une culture",
    "association": "Cultures à associer ou à éloigner",
    "rotation":    "Vérifier la rotation avant de semer",
    "meteo":       "Météo du jour et conseil potager",
    "parcelle":    "Créer, renommer ou lister vos parcelles",
    "parcelles":   "Lister vos parcelles",
    "culture":     "Corriger la fiche d'une culture",
    "potager":     "Changer de potager actif",
    "lier":        "Relier ce chat à votre compte web",
    "tts_on":      "Activer les réponses vocales",
    "tts_off":     "Couper les réponses vocales",
    "start":       "Revenir à l'accueil",
    "help":        "Aide en ligne, par domaine",
}


def _description(nom: str) -> str:
    """Phrase d'aide d'une commande, avec repli explicite.

    Une commande sans description reste affichée — le menu doit rester complet
    (CA3) — mais le repli est volontairement peu flatteur et journalisé : c'est
    le rappel qu'il manque une phrase, pas une valeur acceptable à laisser.
    """
    description = DESCRIPTIONS.get(nom)
    if description is None:
        log.warning(
            "⌨️  MENU TELEGRAM  : /%s n'a pas de phrase d'aide — "
            "ajouter une entrée dans app.services.menu_commandes.DESCRIPTIONS",
            nom,
        )
        return f"Commande /{nom}"
    return description


def construire_menu(noms_commandes: Iterable[str]) -> list[tuple[str, str]]:
    """Construit les entrées du menu à partir des commandes réellement enregistrées.

    `noms_commandes` vient de l'introspection des `CommandHandler` du bot, jamais
    d'une liste recopiée : c'est ce qui garantit qu'aucune commande morte ne
    figure au menu et qu'une commande nouvelle y entre d'elle-même (CA3, CA6).

    Retourne une liste de couples `(nom, description)` ordonnée selon
    `ORDRE_METIER` (CA4).
    """
    retenues = {nom for nom in noms_commandes if nom not in COMMANDES_EXCLUES}

    # Une description qui ne correspond plus à aucune commande enregistrée signale
    # une commande retirée du bot sans nettoyage ici — sans effet sur le menu rendu
    # (il se dérive des commandes réelles), mais à corriger.
    for orpheline in sorted(set(DESCRIPTIONS) - set(noms_commandes)):
        log.warning(
            "⌨️  MENU TELEGRAM  : /%s a une phrase d'aide mais n'est plus "
            "enregistrée par le bot — entrée à retirer de DESCRIPTIONS",
            orpheline,
        )

    rang = {nom: i for i, nom in enumerate(ORDRE_METIER)}
    ordonnees = sorted(retenues, key=lambda nom: (rang.get(nom, len(rang)), nom))

    return [(nom, _description(nom)) for nom in ordonnees]
