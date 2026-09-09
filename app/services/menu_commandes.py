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
    "bioagresseur",
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
    "bioagresseur": "Ce qui attaque une culture",
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


# ═════════════════════════════════════════════════════════════════════════════
# [US-172] Catalogue enrichi — ce que l'interpréteur de commandes a besoin de
# savoir en plus du menu
# -----------------------------------------------------------------------------
# Le menu d'US-171 répond à « quelles commandes montrer ? ». L'interpréteur
# répond à « cette phrase désigne-t-elle une commande, et avec quels
# arguments ? ». Les deux se dérivent des MÊMES commandes réellement
# enregistrées (CA6) : c'est pour cela que le catalogue enrichi vit ici, à côté
# du premier, et non dans un module parallèle qui divergerait au premier ajout
# de commande.
#
# Deux listes d'exclusion cohabitent donc dans ce fichier, et c'est délibéré
# (CA8) : elles n'écartent pas pour les mêmes raisons.
#
#   COMMANDES_EXCLUES                le menu écarte ce qui coûte deux gestes au clic
#   MOTIFS_EXCLUSION_INTERPRETEUR    l'interpréteur écarte ce qu'une phrase ne
#                                    peut pas porter
#
# `/tts` illustre l'écart : écartée du menu (elle n'y règle rien), elle est
# parfaitement dictable — « est-ce que la lecture vocale est active ? » appelle
# exactement sa réponse.
# ═════════════════════════════════════════════════════════════════════════════

from dataclasses import dataclass
from typing import Optional

# ── Formes d'arguments (CA6) ────────────────────────────────────────────────
# Ce que l'interpréteur doit savoir d'un argument pour le reconnaître dans une
# phrase, le relire au jardinier (CA11) et refuser une valeur inventée (CA4).
TYPE_NOM_LIBRE   = "nom_libre"    # un nom que le jardinier choisit (parcelle à créer)
TYPE_PARCELLE    = "parcelle"     # doit désigner une parcelle EXISTANTE (CA12)
TYPE_CULTURE     = "culture"      # une culture, résolue par le référentiel habituel
TYPE_FAMILLE     = "famille"      # une famille botanique
TYPE_NOMBRE      = "nombre"       # une valeur chiffrée — TOUJOURS relue (CA11)
TYPE_DATE        = "date"         # résolue par utils.date_utils, jamais par une 2e règle
TYPE_VOCABULAIRE = "vocabulaire"  # valeur d'une liste fermée, proposée en boutons (CA13)
TYPE_TEXTE       = "texte"        # texte libre repris tel quel (un motif d'association)

TYPES_ARGUMENT: frozenset[str] = frozenset({
    TYPE_NOM_LIBRE, TYPE_PARCELLE, TYPE_CULTURE, TYPE_FAMILLE,
    TYPE_NOMBRE, TYPE_DATE, TYPE_VOCABULAIRE, TYPE_TEXTE,
})


@dataclass(frozen=True)
class Argument:
    """Forme attendue d'un argument de commande.

    `unite` n'est pas décorative : c'est elle que le récapitulatif restitue à
    côté du chiffre (CA11), parce que « profondeur 1 » et « profondeur 10 » ne
    s'entendent pas à la dictée et que la seconde écrirait une donnée fausse
    dans un référentiel partagé.
    """
    nom: str
    type: str
    question: str                      # ce qu'on demande si l'argument manque (CA13)
    obligatoire: bool = True
    vocabulaire: tuple[str, ...] = ()
    unite: Optional[str] = None


@dataclass(frozen=True)
class FormeCommande:
    """Une commande (ou sous-commande) dictable et la forme de ses arguments."""
    commande: str
    sous_commande: Optional[str]
    libelle: str                       # ce que le récapitulatif énonce en clair (CA10)
    arguments: tuple[Argument, ...] = ()
    destructrice: bool = False         # jamais exécutée sur un rapprochement approché (CA12)
    #: [CA10] Une commande qui ÉCRIT est confirmée avant exécution, sans
    #: exception. Une commande de pure CONSULTATION ne l'est pas : demander
    #: « voulez-vous vraiment afficher le plan ? » doublerait chaque lecture
    #: sans rien protéger, et rendrait le compagnon plus lourd à la voix qu'au
    #: clavier — l'inverse de ce que cette US cherche. La commande équivalente
    #: reste rappelée dans les deux cas : c'est la moitié pédagogique du CA10,
    #: et elle vaut pour toutes les commandes.
    #: Les parcours guidés (`/note`, `/corriger`, `/vendre`) n'écrivent rien par
    #: eux-mêmes non plus : ils ouvrent un dialogue qui porte sa propre
    #: validation (US-021, US-038), et la doubler d'une confirmation d'entrée
    #: ferait deux « oui » pour un seul geste.
    confirmation: bool = True

    @property
    def cle(self) -> "tuple[str, Optional[str]]":
        return (self.commande, self.sous_commande)


# Les vocabulaires fermés sont LUS aux services qui les valident déjà, jamais
# recopiés ici : une valeur ajoutée à `attributs_culture.EXPOSITIONS` devient
# dictable sans une ligne de plus, et l'interpréteur ne peut pas proposer une
# valeur que le point d'écriture refuserait.
def _vocabulaire(chemin: str, attribut: str) -> tuple[str, ...]:
    """Lit un vocabulaire fermé au service qui le valide — import différé pour
    ne pas créer de cycle (`app.services.associations` importe déjà `llm`)."""
    import importlib
    return tuple(getattr(importlib.import_module(chemin), attribut))


FORMES_DICTABLES: tuple[FormeCommande, ...] = (
    # ── Parcelles ────────────────────────────────────────────────────────────
    FormeCommande(
        "parcelle", "ajouter", "Créer une parcelle",
        (
            Argument("nom", TYPE_NOM_LIBRE, "Quel nom pour cette parcelle ?"),
            Argument("exposition", TYPE_NOM_LIBRE, "Quelle exposition ?", obligatoire=False),
            Argument("superficie", TYPE_NOMBRE, "Quelle superficie ?", obligatoire=False, unite="m²"),
        ),
    ),
    FormeCommande(
        "parcelle", "renommer", "Renommer une parcelle",
        (
            Argument("ancien", TYPE_PARCELLE, "Quelle parcelle renommer ?"),
            Argument("nouveau", TYPE_NOM_LIBRE, "Quel nouveau nom ?"),
        ),
    ),
    FormeCommande(
        "parcelle", "supprimer", "Supprimer une parcelle",
        (Argument("nom", TYPE_PARCELLE, "Quelle parcelle supprimer ?"),),
        destructrice=True,
    ),
    FormeCommande(
        "parcelle", "modifier", "Modifier une parcelle",
        (
            Argument("nom", TYPE_PARCELLE, "Quelle parcelle modifier ?"),
            Argument("modification", TYPE_TEXTE, "Que faut-il modifier ? (par exemple : exposition=sud)"),
        ),
    ),
    FormeCommande("parcelle", "lister", "Lister vos parcelles", confirmation=False),

    # ── Consultation ─────────────────────────────────────────────────────────
    FormeCommande(
        "plan", None, "Afficher le plan d'occupation",
        (
            Argument("parcelle", TYPE_PARCELLE, "Quelle parcelle ?", obligatoire=False),
            Argument("date", TYPE_DATE, "À quelle date ?", obligatoire=False),
        ),
        confirmation=False,
    ),
    FormeCommande(
        "stats", None, "Afficher le bilan chiffré",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?", obligatoire=False),
            Argument("date", TYPE_DATE, "À quelle date ?", obligatoire=False),
        ),
        confirmation=False,
    ),
    FormeCommande("historique", None, "Afficher vos derniers événements", confirmation=False),
    FormeCommande("meteo", None, "Afficher la météo du jour", confirmation=False),
    FormeCommande(
        "fiche", None, "Afficher la fiche d'une culture",
        (Argument("culture", TYPE_CULTURE, "Quelle culture ?"),),
        confirmation=False,
    ),
    FormeCommande(
        "rotation", None, "Vérifier la rotation avant de semer",
        (
            Argument("parcelle", TYPE_PARCELLE, "Sur quelle parcelle ?"),
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
        ),
        confirmation=False,
    ),

    # ── Associations ─────────────────────────────────────────────────────────
    FormeCommande(
        "association", "lister", "Lister les associations d'une culture",
        (Argument("culture", TYPE_CULTURE, "Quelle culture ?"),),
        confirmation=False,
    ),
    FormeCommande(
        "association", "saisir", "Enregistrer une association entre deux cultures",
        (
            Argument("culture_a", TYPE_CULTURE, "Quelle première culture ?"),
            Argument("culture_b", TYPE_CULTURE, "Quelle seconde culture ?"),
            Argument("nature", TYPE_VOCABULAIRE, "Cette association est-elle favorable, défavorable ou neutre ?",
                     vocabulaire=_vocabulaire("app.services.associations", "NATURES")),
            Argument("preuve", TYPE_VOCABULAIRE, "Sur quoi repose-t-elle ?",
                     vocabulaire=_vocabulaire("app.services.associations", "NIVEAUX_PREUVE")),
            Argument("motif", TYPE_TEXTE, "Pour quel motif ?"),
        ),
    ),

    # ── Fiche de culture partagée ────────────────────────────────────────────
    FormeCommande(
        "culture", "attributs", "Lire les attributs d'une culture",
        (Argument("culture", TYPE_CULTURE, "Quelle culture ?"),),
        confirmation=False,
    ),
    FormeCommande(
        "culture", "famille", "Corriger la famille botanique d'une culture",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
            Argument("famille", TYPE_FAMILLE, "Quelle famille botanique ?"),
        ),
    ),
    FormeCommande(
        "culture", "delai_retour", "Corriger le délai de retour d'une famille",
        (
            Argument("famille", TYPE_FAMILLE, "Quelle famille botanique ?"),
            Argument("annees", TYPE_NOMBRE, "Combien d'années ?", unite="ans"),
        ),
    ),
    FormeCommande(
        "culture", "exposition", "Corriger l'exposition d'une culture",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
            Argument("valeur", TYPE_VOCABULAIRE, "Quelle exposition ?",
                     vocabulaire=_vocabulaire("app.services.attributs_culture", "EXPOSITIONS")),
        ),
    ),
    FormeCommande(
        "culture", "eau", "Corriger le besoin en eau d'une culture",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
            Argument("valeur", TYPE_VOCABULAIRE, "Quel besoin en eau ?",
                     vocabulaire=_vocabulaire("app.services.attributs_culture", "BESOINS_EAU")),
        ),
    ),
    FormeCommande(
        "culture", "profondeur", "Corriger la profondeur de semis d'une culture",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
            Argument("valeur", TYPE_NOMBRE, "Quelle profondeur de semis ?", unite="cm"),
        ),
    ),
    FormeCommande(
        "culture", "rusticite", "Corriger la rusticité d'une culture",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
            Argument("valeur", TYPE_NOMBRE, "Quelle température minimale ?", unite="°C"),
        ),
    ),

    # ── Bioagresseurs ────────────────────────────────────────────────────────
    # `lister` est volontairement ABSENTE de cette liste, et ce n'est pas un
    # oubli : « qu'est-ce qui attaque mes poireaux ? » est déjà servie par
    # gabarit à l'étage 1 (US-173), à zéro jeton et sans appel modèle. En faire
    # une commande créerait deux entrées vers le même chemin — le motif exact
    # qui écarte `/ask` de l'interpréteur.
    FormeCommande(
        "bioagresseur", "declarer", "Déclarer un bioagresseur dans ce potager",
        (
            Argument("categorie", TYPE_VOCABULAIRE, "De quelle nature est-il ?",
                     vocabulaire=_vocabulaire("app.services.bioagresseurs", "CATEGORIES")),
            Argument("nom", TYPE_NOM_LIBRE, "Quel est son nom ?"),
        ),
    ),
    FormeCommande(
        "bioagresseur", "rattacher", "Rattacher un bioagresseur à une culture",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?"),
            Argument("frequence", TYPE_VOCABULAIRE, "À quelle fréquence l'attaque-t-il ?",
                     vocabulaire=_vocabulaire("app.services.bioagresseurs", "FREQUENCES")),
            Argument("bioagresseur", TYPE_NOM_LIBRE, "Quel bioagresseur ?"),
        ),
    ),
    FormeCommande("bioagresseur", "orphelins", "Lister les bioagresseurs rattachés à aucune culture",
                  confirmation=False),

    # ── Potager, parcours guidés, confort ────────────────────────────────────
    FormeCommande(
        "potager", None, "Changer de potager actif",
        (Argument("nom", TYPE_NOM_LIBRE, "Quel potager ?", obligatoire=False),),
    ),
    FormeCommande("note", None, "Ouvrir la saisie guidée d'une note", confirmation=False),
    FormeCommande("corriger", None, "Ouvrir le parcours de correction", confirmation=False),
    FormeCommande(
        "vendre", None, "Ouvrir l'enregistrement d'une vente de plants",
        (
            Argument("culture", TYPE_CULTURE, "Quelle culture ?", obligatoire=False),
            Argument("variete", TYPE_NOM_LIBRE, "Quelle variété ?", obligatoire=False),
        ),
        confirmation=False,
    ),
    FormeCommande("tts_on", None, "Activer les réponses vocales", confirmation=False),
    FormeCommande("tts_off", None, "Couper les réponses vocales", confirmation=False),
    FormeCommande("tts", None, "Dire si les réponses vocales sont actives", confirmation=False),
    FormeCommande(
        "help", None, "Afficher l'aide",
        (Argument("domaine", TYPE_NOM_LIBRE, "Sur quel domaine ?", obligatoire=False),),
        confirmation=False,
    ),
)

FORMES_PAR_CLE: "dict[tuple[str, Optional[str]], FormeCommande]" = {
    forme.cle: forme for forme in FORMES_DICTABLES
}

# ── Les alias, qui ne sont pas des commandes de plus (CA7) ──────────────────
# `/parcelles` n'a pas de forme dictable à elle : elle EST `/parcelle lister`,
# et le bot la sert d'ailleurs en posant `ctx.args = ["lister"]` avant de
# déléguer. Lui inventer une forme propre dans le catalogue aurait deux effets,
# tous deux faux : la décrire au modèle comme une seconde façon de faire la même
# chose, et exiger du corpus trois formulations qu'aucun jardinier ne dit
# différemment de « liste mes parcelles ».
#
# Un alias est donc COUVERT par sa cible canonique, sans être dictable
# lui-même — et le contrôle de parité vérifie que cette cible existe bien.
ALIAS_COMMANDES: dict[str, tuple[str, Optional[str]]] = {
    "parcelles": ("parcelle", "lister"),
}

COMMANDES_DICTABLES: frozenset[str] = frozenset(f.commande for f in FORMES_DICTABLES)


# ── Ce qu'une phrase ne peut pas porter — décisions du 08/09/2026 (CA7, CA8) ──
# Une commande n'entre ici que sur une décision DÉFINITIVE, jamais parce qu'elle
# n'est « pas encore faite » : c'est la condition pour que le test de parité
# reste un garde-fou et non une formalité. Les cinq commandes ci-dessous restent
# pleinement fonctionnelles à la saisie manuelle — les exclure de l'interpréteur
# ne les retire pas du bot, exactement comme les exclure du menu ne les en
# retirait pas.
MOTIFS_EXCLUSION_INTERPRETEUR: dict[str, str] = {
    "ask": (
        "Son équivalent naturel EST la question elle-même : une question dictée "
        "est déjà aiguillée par le routeur (US-093). En faire une commande "
        "créerait deux entrées vers le même chemin."
    ),
    "start": (
        "Point d'entrée du protocole Telegram (bouton « Démarrer »), pas une phrase."
    ),
    "lier": (
        "Le code de liaison est une chaîne à coller, pas à dicter : la "
        "transcription vocale d'un code est fausse par construction."
    ),
    "delier": (
        "Action rare et destructive SUR L'IDENTITÉ. La rendre atteignable à une "
        "phrase mal transcrite serait un mauvais service — même raisonnement que "
        "son exclusion du menu (US-171)."
    ),
    "version": (
        "Diagnostic sans usage quotidien pour le jardinier."
    ),
}

COMMANDES_EXCLUES_INTERPRETEUR: frozenset[str] = frozenset(MOTIFS_EXCLUSION_INTERPRETEUR)


def controler_parite(noms_commandes: Iterable[str]) -> list[str]:
    """[CA7] Parité commandes enregistrées ↔ interpréteur — liste des anomalies.

    Compare deux ensembles DÉRIVÉS : les commandes réellement enregistrées par
    le bot (introspection des `CommandHandler`) et celles que l'interpréteur
    déclare savoir traiter ou avoir délibérément écartées. Aucune liste écrite à
    la main n'entre dans la comparaison — même procédé que le contrôle de
    cohérence `/help` ↔ corpus (`tools/controler_aide_corpus.py`).

    C'est ce contrôle, et non la vigilance, qui empêche l'écart constaté avant
    cette US de se recreuser à la prochaine commande ajoutée : une commande
    nouvelle est en anomalie tant qu'elle n'est ni dictable ni motivée comme
    exclue.

    Retourne la liste (vide = tout va bien) des anomalies, formulées pour être
    lues telles quelles dans un échec d'intégration continue.
    """
    anomalies: list[str] = []
    enregistrees = set(noms_commandes)

    for nom in sorted(enregistrees):
        if nom in COMMANDES_EXCLUES_INTERPRETEUR:
            continue
        if nom in ALIAS_COMMANDES:
            if ALIAS_COMMANDES[nom] not in FORMES_PAR_CLE:
                cible = " ".join(p for p in ALIAS_COMMANDES[nom] if p)
                anomalies.append(
                    f"/{nom} est déclarée alias de « {cible} », qui n'est pas "
                    f"une forme dictable — l'alias ne couvre donc rien."
                )
            continue
        if nom not in COMMANDES_DICTABLES:
            anomalies.append(
                f"/{nom} est enregistrée par le bot mais n'est ni dictable "
                f"(app.services.menu_commandes.FORMES_DICTABLES), ni alias d'une "
                f"forme dictable (ALIAS_COMMANDES), ni explicitement exclue et "
                f"motivée (MOTIFS_EXCLUSION_INTERPRETEUR)."
            )

    for nom in sorted(set(ALIAS_COMMANDES) - enregistrees):
        anomalies.append(
            f"/{nom} est déclarée alias mais n'est plus enregistrée par le "
            f"bot — entrée à retirer de ALIAS_COMMANDES."
        )

    for nom in sorted(COMMANDES_DICTABLES - enregistrees):
        anomalies.append(
            f"/{nom} est déclarée dictable mais n'est plus enregistrée par le "
            f"bot — entrée à retirer de FORMES_DICTABLES."
        )

    for nom in sorted(COMMANDES_EXCLUES_INTERPRETEUR - enregistrees):
        anomalies.append(
            f"/{nom} est déclarée exclue de l'interpréteur mais n'est plus "
            f"enregistrée par le bot — entrée à retirer de "
            f"MOTIFS_EXCLUSION_INTERPRETEUR."
        )

    # [CA7, second volet] Une commande dictable qui ne déclare pas la forme de
    # ses arguments est une anomalie au même titre : c'est cette déclaration qui
    # permet de relire une valeur avant de l'écrire (CA11), d'en proposer les
    # valeurs possibles en boutons (CA13) et de refuser une valeur inventée (CA4).
    for forme in FORMES_DICTABLES:
        prefixe = f"/{forme.commande} {forme.sous_commande or ''}".strip()
        for arg in forme.arguments:
            if arg.type not in TYPES_ARGUMENT:
                anomalies.append(
                    f"{prefixe} : l'argument « {arg.nom} » déclare un type "
                    f"inconnu ({arg.type!r})."
                )
            if arg.type == TYPE_VOCABULAIRE and not arg.vocabulaire:
                anomalies.append(
                    f"{prefixe} : l'argument « {arg.nom} » est un vocabulaire "
                    f"fermé mais ne déclare aucune valeur — l'interpréteur ne "
                    f"pourrait que la deviner."
                )
            if arg.type == TYPE_NOMBRE and not arg.unite:
                anomalies.append(
                    f"{prefixe} : l'argument chiffré « {arg.nom} » ne déclare "
                    f"pas son unité — le récapitulatif ne pourrait pas la "
                    f"relire (CA11)."
                )
            if not arg.question.strip():
                anomalies.append(
                    f"{prefixe} : l'argument « {arg.nom} » ne déclare pas la "
                    f"question à poser s'il manque (CA13)."
                )

    return anomalies
