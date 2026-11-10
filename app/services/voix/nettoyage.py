"""
app/services/voix/nettoyage.py — texte prêt à être dit [US-299 / CA5]
=====================================================================
Reprise du nettoyage de `utils/tts.py` (`_strip_markdown`), recopié ici et non
importé : `utils/tts.py` charge gTTS au chargement et sert le bot Telegram, il
reste inchangé (CA8). En plus : les liens nus (`https://…`) sont retirés, une
voix qui épelle une adresse n'apprend rien au jardinier.
"""
import re

_TITRES = re.compile(r"#+\s*")
_EMPHASE = re.compile(r"[*_`]{1,3}")
_LIEN_MARKDOWN = re.compile(r"\[([^\]]+)\]\([^\)]+\)")
_LIEN_NU = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_EMOJIS = re.compile(
    r"[\U0001F300-\U0001FFFF\U00002702-\U000027B0\U0000FE0F\U00002000-\U00002BFF]+"
)
_ESPACES = re.compile(r"\s+")
_ESPACE_AVANT_PONCTUATION_SIMPLE = re.compile(r"\s+([,.])")


def nettoyer_pour_voix(texte: str) -> str:
    """Retire Markdown, émojis et liens d'un texte destiné à la synthèse vocale.

    Le libellé d'un lien Markdown est gardé (`[la fiche](url)` → « la fiche »),
    un lien nu disparaît. Rend une chaîne vide si rien ne reste à dire.
    """
    if not texte:
        return ""
    texte = _TITRES.sub("", texte)
    texte = _LIEN_MARKDOWN.sub(r"\1", texte)
    texte = _LIEN_NU.sub(" ", texte)
    texte = _EMPHASE.sub("", texte)
    texte = _EMOJIS.sub(" ", texte)
    texte = _ESPACES.sub(" ", texte).strip()
    return _ESPACE_AVANT_PONCTUATION_SIMPLE.sub(r"\1", texte)
