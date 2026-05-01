"""
utils/deplacer.py — Helpers de détection et d'extraction pour le flux DÉPLACER (US-007)
"""
import re

# [US-007] Mots-clés déclencheurs du flux DÉPLACER (réassociation culture → parcelle)
_DEPLACER_KEYWORDS = (
    "associer", "déplacer", "deplacer", "changer de parcelle", "changer parcelle",
    "déménager", "demenager", "rattacher", "affecter", "réassocier", "reassocier",
    "mettre sur une autre parcelle", "nouvelle parcelle", "autre parcelle",
)

# Mots génériques à ignorer lors de l'extraction de la culture
_MOTS_GENERIQUES = {
    "ma", "mon", "mes", "la", "le", "les", "une", "un", "sur", "dans",
    "de", "du", "des", "zone", "parcelle", "nouvelle", "autre", "toutes",
    "culture", "cultures", "plant", "plants", "plantation", "plantations",
}


def is_deplacer_request(texte: str) -> bool:
    """[US-007 / CA1, CA10] Retourne True si la phrase correspond à une demande de réassociation culture→parcelle."""
    t = texte.lower().strip()
    return any(kw in t for kw in _DEPLACER_KEYWORDS)


def extract_culture_deplacer(texte: str) -> str | None:
    """
    [US-007 / CA1] Extrait la culture depuis une phrase de déplacement.
    Ex : "associer ma zone tomate sur une nouvelle parcelle" → "tomate"
    Ex : "déplacer mes carottes sur la parcelle nord" → "carottes"
    Retourne None si aucune culture détectée.
    """
    t = texte.lower().strip()
    m = re.search(
        r'(?:associer?|d[eé]placer?|changer?|r[eé]associer?|affecter?|rattacher?|d[eé]m[eé]nager?)\s+'
        r'(?:mes?\s+|mon\s+|ma\s+|la\s+|le\s+|les?\s+)?'
        r'(?:zone\s+|parcelle\s+|cultures?\s+|plant(?:s|ation)?(?:s)?\s+)?'
        r'([a-zàâçéèêëîïôûùüÿæœ]+)',
        t,
    )
    if m:
        word = m.group(1)
        if word not in _MOTS_GENERIQUES:
            return word
    return None
