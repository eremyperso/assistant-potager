# app/utils/actions.py
from __future__ import annotations
import logging
import re
from unidecode import unidecode

log = logging.getLogger("potager")

# 18 actions canoniques — référentiel unique [US-168 CA1] : c'est
# la seule liste tenue à la main. utils.validation.ACTIONS_VALIDES (vocabulaire
# d'ENTRÉE, ce que Groq peut renvoyer brut dans `action`) en DÉRIVE par
# construction plutôt que de la dupliquer à la main — voir le commentaire de
# ACTIONS_VALIDES pour le sens précis des deux vocabulaires.
ACTION_MAP: dict[str, list[str]] = {
    "recolte": [
        "recolte", "recolter", "recolte de", "recolte des",
        "cueillir", "cueilli", "cueillie",
        "ramasser", "ramasse", "ramassees", "ramasses",
        # [US-168] Absorbées depuis le supplément temporaire du routeur
        # (llm/routeur.py) — pluriel et coquilles de transcription vocale
        # réellement rencontrées en production.
        "recoltes", "ecolte", "recolde",
    ],
    "semis": [
        "semis", "semer", "seme", "semee", "semes", "semees",
        "semi",  # [US-168] idem, forme sans "s" dictée
    ],
    "plantation": [
        "planter", "plante", "plantee", "plantes", "plantees",
        "repiquer", "repique", "repiquee", "repiquees", "repiquage",
        "mise en terre", "mettre en terre", "transplanter",
        "plantations",  # [US-168] idem, pluriel
    ],
    "arrosage": [
        "arrosage", "arroser", "arrose", "arrose", "arrosees",
        "irriguer", "donner de l eau", "donner de l'eau"
    ],
    "desherbage": [
        "desherbage", "desherber", "desherbe", "désherbé",
        "sarcler", "sarclage",
        "enlever les mauvaises herbes", "arracher les herbes"
    ],
    "paillage": [
        "paillage", "pailler", "paillé", "paillis",
        "mettre de la paille", "couvrir le sol", "mulch", "mulcher"
    ],
    "amendement": [
        "amender", "amendement",
        "ajouter du compost", "mettre du compost", "compost",
        "fumier", "terreau", "engrais", "fertiliser", "fertilisation", "fertilisé",
        # [US-168] Absorbées depuis le supplément temporaire du routeur.
        "ajout", "ajoute", "apport", "apporte",
    ],
    "taille": [
        "taille", "tailler", "taillé", "couper", "pincer", "elaguer", "rabattre"
    ],
    "tuteurage": [
        "tuteurage", "tuteurer", "tuteuré", "mettre un tuteur",
        "attacher", "palissage", "palisser"
    ],
    "traitement": [
        "traitement", "traiter", "traité", "pulveriser", "pulverisation",
        "spray", "savon noir", "purin d ortie", "purin d'ortie"
    ],
    "protection": [
        "protection", "proteger", "protege",
        "voile", "filet", "cloche", "tunnel",
        "proteger du gel", "proteger du froid", "anti insectes", "anti-insectes"
    ],
    "observation": [
        "observation", "observer", "observé", "surveiller", "constat", "noter",
        "maladie", "mildiou", "attaque", "gel", "secheresse", "limaces"
    ],
    "perte": [
        "perte", "perdu", "perdue", "perdus", "perdues",
        "mort", "morte", "morts", "mortes",
        "arrache", "arrachee", "arraches", "arrachees",
        "creve", "crevee", "creves", "crevees",
        "disparu", "disparue", "disparus", "disparues"
    ],
    "mise_en_godet": [
        "mise en godet", "mis en godet", "mettre en godet",
        "godet", "godets", "rempotage godet",
        "repique en godet", "repique en godets",
    ],
    "vendu": [
        "vendu", "vendue", "vendus", "vendues",
        "vendre", "vendu a", "vente", "cede", "cedee", "cedees",
        "donne", "donnee", "donnees",
    ],
    "perte_godet": [
        "perte godet", "perdu en godet", "perdu dans le godet",
        "perdu en pepiniere", "perdu pepiniere",
        "perte pepiniere", "perte semis",
        "perdu en semis", "graines perdues", "graines perdus",
    ],
    # [US-168 CA2] Gestes réels attestés en production (Action 0, vague 2),
    # jusqu'ici absents du référentiel et donc silencieusement jetés à la
    # validation (utils/validation.ACTIONS_VALIDES) avant d'atteindre cette
    # normalisation.
    "binage": [
        "binage", "biner", "bine", "binee",
    ],
    "eclaircie": [
        # La forme réellement stockée en base est "eclaircie", pas
        # "eclaircissage" — c'est donc elle la clé canonique ; "eclaircissage"
        # n'est qu'une variante d'entrée, sous peine de laisser la ligne
        # existante orpheline.
        "eclaircie", "eclaircir", "eclairci", "eclaircissage",
    ],
}

# Petits mots à ignorer au début (langage naturel)
LEADING_NOISE = (
    "j ai", "j'ai", "on a", "on", "je", "tu", "il", "elle", "nous", "vous",
    "aujourd hui", "aujourd'hui", "hier", "ce matin", "cet apres midi", "cet après-midi",
)

def _clean_text(s: str) -> str:
    s = unidecode(s.lower())
    s = s.replace("’", "'")
    # normalise apostrophes / espaces
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def normalize_action(action: str | None) -> str | None:
    """
    Retourne l'action canonique (ex: 'recolte') ou None.
    Stratégie:
      - nettoie la chaîne (minuscules, sans accents)
      - enlève un préfixe de type "j'ai", "aujourd'hui"...
      - match sur startswith puis sur contains
      - fallback : renvoie la version nettoyée (utile pour détecter les nouveaux cas)
    """
    if not action:
        return None

    value = _clean_text(action)

    # retirer un peu de bruit en tête
    for noise in LEADING_NOISE:
        if value.startswith(noise + " "):
            value = value[len(noise):].strip()
            break

    # 0) [fix normalize_action perte_godet] égalité exacte avec une clé canonique
    # elle-même, prioritaire sur le matching flou ci-dessous. Sans cette étape,
    # "perte_godet" (déjà canonique, ex: réémis par bot.py après une
    # désambiguation) se fait absorber par le variant "perte" du canonique
    # "perte" — "perte godet" nettoyé commence bien par "perte" — et retombe à
    # tort sur "perte" au lieu de rester "perte_godet".
    for canonical in ACTION_MAP:
        if value == _clean_text(canonical):
            return canonical

    # 1) startswith (le plus fiable)
    for canonical, variants in ACTION_MAP.items():
        for v in variants:
            v_clean = _clean_text(v)
            if value.startswith(v_clean):
                return canonical

    # 2) contains (plus permissif)
    for canonical, variants in ACTION_MAP.items():
        for v in variants:
            v_clean = _clean_text(v)
            if v_clean and v_clean in value:
                return canonical

    # [US-168 CA4] Repli passant — décision tranchée : CONSERVÉ, pas supprimé.
    # Le supprimer rendrait le système strict mais aveugle aux gestes réels pas
    # encore référencés (c'est ce repli qui a révélé `binage`/`eclaircie` avant
    # cette US). Mais un repli silencieux redevient exactement le défaut qu'il
    # a fallu corriger : toute valeur qui l'atteint est donc désormais journalisée,
    # jamais muette (CA4). En pratique il ne se déclenche plus sur le chemin
    # d'écriture principal — validate_parsed_action rejette déjà tout ce qui
    # n'est pas dans ACTIONS_VALIDES avant que normalize_action() soit appelé —
    # mais reste atteignable par les appels directs (corrections, recherche).
    if value:
        log.warning("[normalize_action] action inconnue, repli passant : '%s' (brut='%s')", value, action)
    return value or None