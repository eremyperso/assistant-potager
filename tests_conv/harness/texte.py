"""Normalisation de texte commune au parseur, aux assertions et au pilote."""
import re
import unicodedata


def norm(texte: str) -> str:
    """Minuscules, sans accents, sans ponctuation ni émojis, espaces simples.

    « ✅ Confirmer » et « confirmer » se valent ; « j'ai » devient « j ai » des deux côtés."""
    decompose = unicodedata.normalize("NFKD", (texte or "").lower())
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sans_accent)).strip()
