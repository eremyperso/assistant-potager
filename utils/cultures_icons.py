"""
utils/cultures_icons.py — Mapping culture → emoji
--------------------------------------------------
Fournit un emoji spécifique pour chaque culture du potager.
Utilisé à la place du générique 🍅/🥬 basé sur le type d'organe.

Couverture : 46 cultures nommées + fallback par type_organe.
"""

# Mapping culture (nom normalisé minuscule) → emoji Unicode
_EMOJI_CULTURE: dict[str, str] = {
    # ── Légumes-feuilles ─────────────────────────────────────────────────────
    "salade":             "🥗",
    "laitue":             "🥬",
    "épinard":            "🌿",
    "épinard perpétuel":  "🌿",
    "mâche":              "🍃",
    "roquette":           "🌿",
    "mesclun":            "🥗",
    "cresson":            "🌿",
    "chou":               "🥦",
    "chou de bruxelles":  "🥦",
    "chou frisé":         "🥬",
    "chou rouge":         "🥬",
    "chou rave":          "🥬",
    "chou-fleur":         "🥦",
    "brocoli":            "🥦",
    "endive":             "🥬",
    "chicorée":           "🥬",
    "oseille":            "🍃",
    "bette":              "🌿",

    # ── Racines & tubercules ──────────────────────────────────────────────────
    "carotte":            "🥕",
    "betterave":          "🫐",
    "radis":              "🌸",
    "navet":              "🌿",
    "panais":             "🥕",
    "scorsonère":         "🌿",
    "salsifis":           "🌿",
    "rutabaga":           "🥔",
    "céleri":             "🌿",
    "céleri-rave":        "🌿",
    "persil racine":      "🌿",
    "topinambour":        "🌿",
    "pomme de terre":     "🥔",
    "patate douce":       "🍠",
    "artichaut":          "🌱",

    # ── Bulbes & alliacées ────────────────────────────────────────────────────
    "oignon":             "🧅",
    "oignon blanc":       "🧅",
    "échalote":           "🧅",
    "ail":                "🧄",
    "ail rose":           "🧄",
    "poireau":            "🌿",
    "ciboulette":         "🌿",

    # ── Fruits potagiers ──────────────────────────────────────────────────────
    "tomate":             "🍅",
    "poivron":            "🫑",
    "aubergine":          "🍆",
    "courgette":          "🥒",
    "concombre":          "🥒",
    "cornichon":          "🥒",
    "pâtisson":           "🎃",
    "potiron":            "🎃",
    "courge butternut":   "🎃",
    "melon":              "🍈",
    "pastèque":           "🍉",

    # ── Légumineuses ─────────────────────────────────────────────────────────
    "haricot":            "🫘",
    "haricot grimpant":   "🫘",
    "petit pois":         "🫛",
    "pois gourmand":      "🫛",
    "fève":               "🫘",

    # ── Asperge ───────────────────────────────────────────────────────────────
    "asperge":            "🌱",

    # ── Fruits rouges & vivaces ───────────────────────────────────────────────
    "fraise":             "🍓",
    "framboise":          "🍇",
    "groseille":          "🍇",
    "cassis":             "🫐",
    "rhubarbe":           "🌿",

    # ── Aromatiques ───────────────────────────────────────────────────────────
    "persil":             "🌿",
    "basilic":            "🌿",
    "thym":               "🌿",
    "romarin":            "🌿",
    "coriandre":          "🌿",
    "aneth":              "🌿",
    "menthe":             "🌿",
    "estragon":           "🌿",
    "sarriette":          "🌿",
    "cerfeuil":           "🌿",

    # ── Fleurs comestibles ────────────────────────────────────────────────────
    "capucine":           "🌸",
    "bourrache":          "🌸",
    "souci":              "🌼",
}

# Fallback par type d'organe
_EMOJI_PAR_ORGANE: dict[str, str] = {
    "reproducteur": "🍅",
    "végétatif":    "🥬",
}
_EMOJI_DEFAUT = "🌱"


def get_emoji_culture(nom: str | None, type_organe: str | None = None) -> str:
    """
    Retourne l'emoji associé à une culture.

    Priorité :
    1. Correspondance exacte dans _EMOJI_CULTURE (insensible à la casse)
    2. Correspondance partielle : le nom de la culture est contenu dans la clé
       ou la clé est contenue dans le nom (gère "courge butternut" ↔ "butternut")
    3. Fallback sur type_organe (🍅 reproducteur / 🥬 végétatif)
    4. 🌱 si aucune info disponible
    """
    if nom:
        key = nom.lower().strip()
        # 1. Exacte
        if key in _EMOJI_CULTURE:
            return _EMOJI_CULTURE[key]
        # 2. Partielle
        for culture_key, emoji in _EMOJI_CULTURE.items():
            if culture_key in key or key in culture_key:
                return emoji
    # 3. Type d'organe
    if type_organe:
        return _EMOJI_PAR_ORGANE.get(type_organe, _EMOJI_DEFAUT)
    return _EMOJI_DEFAUT
