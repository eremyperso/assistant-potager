"""Inférence et normalisation des items dictés (action, culture, date).

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from llm.groq_client import parse_commande
from llm.parseur_deterministe import ORIGINE_LLM, parser_saisie
from app.services.context import current_context
from datetime import date, timedelta
from .noyau import log


# ── Dictionnaire mots-clés → action ─────────────────────────────────────────
ACTION_KEYWORDS = {
    "arrosage"     : "arrosage",
    "arroser"      : "arrosage",
    "arrosé"       : "arrosage",
    "semis"        : "semis",
    "semé"         : "semis",
    "semer"        : "semis",
    "planté"       : "plantation",
    "planter"      : "plantation",
    "plantation"   : "plantation",
    "récolté"      : "recolte",
    "récolter"     : "recolte",
    "récolte"      : "recolte",
    "cueilli"      : "recolte",
    "ramassé"      : "recolte",
    "repiqué"      : "repiquage",
    "repiquer"     : "repiquage",
    "repiquage"    : "repiquage",
    "traité"       : "traitement",
    "traiter"      : "traitement",
    "traitement"   : "traitement",
    "désherbé"     : "desherbage",
    "désherber"    : "desherbage",
    "desherbage"   : "desherbage",
    "paillé"       : "paillage",
    "pailler"      : "paillage",
    "paillage"     : "paillage",
    "taillé"       : "taille",
    "tailler"      : "taille",
    "taille"       : "taille",
    "tuteuré"      : "tuteurage",
    "tuteurer"     : "tuteurage",
    "tuteurage"    : "tuteurage",
    "fertilisé"    : "fertilisation",
    "fertiliser"   : "fertilisation",
    "fertilisation": "fertilisation",
    "observé"      : "observation",
    "observer"     : "observation",
    "observation"  : "observation",
    "constaté"     : "observation",
    "perdu"        : "perte",
    "perte"        : "perte",
    "mort"         : "perte",
    "arraché"      : "perte",
    "crevé"        : "perte",
}


# ── Légumes connus ────────────────────────────────────────────────────────────
CULTURES_CONNUES = {
    "tomate","tomates","carotte","carottes","courgette","courgettes",
    "salade","salades","laitue","laitues","radis","poireau","poireaux",
    "oignon","oignons","ail","ails","poivron","poivrons","aubergine",
    "aubergines","concombre","concombres","haricot","haricots","petits pois",
    "pois","épinard","épinards","chou","choux","chou-fleur","choux-fleurs",
    "brocoli","brocolis","celeri","céleri","panais","navet","navets",
    "betterave","betteraves","potiron","potirons","courge","courges",
    "mûre","mûres","fraise","fraises","framboise","framboises",
    "patate","patates","pomme de terre","pommes de terre","patate douce",
    "patates douces","maïs","persil","basilic","thym","romarin",
    "poireau","poireaux","échalote","échalotes","melon","melons",
    "pastèque","tomate cerise","tomates cerises",
}


TEMPORAL_MAP = {
    "hier"        : lambda: (date.today() - timedelta(days=1)).isoformat(),
    "avant-hier"  : lambda: (date.today() - timedelta(days=2)).isoformat(),
    "aujourd'hui" : lambda: date.today().isoformat(),
    "aujourd hui" : lambda: date.today().isoformat(),
    "lundi"       : lambda: _last_weekday(0),
    "mardi"       : lambda: _last_weekday(1),
    "mercredi"    : lambda: _last_weekday(2),
    "jeudi"       : lambda: _last_weekday(3),
    "vendredi"    : lambda: _last_weekday(4),
    "samedi"      : lambda: _last_weekday(5),
    "dimanche"    : lambda: _last_weekday(6),
}


def _last_weekday(weekday: int) -> str:
    today = date.today()
    days_ago = (today.weekday() - weekday) % 7 or 7
    return (today - timedelta(days=days_ago)).isoformat()


def _infer_action(texte: str) -> str | None:
    """Déduit l'action depuis le texte si Groq a retourné action=null."""
    words = texte.lower().replace(",", " ").replace(".", " ").split()
    for word in words:
        if word in ACTION_KEYWORDS:
            return ACTION_KEYWORDS[word]
    return None


def _infer_culture(texte: str) -> str | None:
    """Extrait le légume depuis le texte si Groq a retourné culture=null."""
    t = texte.lower()
    # Chercher d'abord les expressions multi-mots (plus spécifiques)
    for cult in sorted(CULTURES_CONNUES, key=len, reverse=True):
        if cult in t:
            # Retourner au singulier
            return cult.rstrip("s") if cult.endswith("s") and len(cult) > 4 else cult
    return None


def _infer_date(texte: str) -> str | None:
    """Extrait la date depuis le texte si Groq a retourné date=null."""
    t = texte.lower()
    for mot, fn in TEMPORAL_MAP.items():
        if mot in t:
            return fn()
    return None


def _parser_items(texte: str) -> list:
    """[US-094 / CA1] Étage 0 de la saisie : grammaire déterministe, puis repli modèle.

    Un seul point de décision pour tous les chemins de saisie (texte, vocal,
    multi-lignes) — sans quoi la couverture mesurée dépendrait du canal
    emprunté, ce que l'arbitrage « la voix ne change rien » exclut.

    Ne touche à aucune garde en amont : les modes de correction, le mode `ask`
    et la navigation ont déjà tranché quand on arrive ici. Peut lever
    `LLMIndisponibleError` — mais seulement quand le repli modèle a dû être
    tenté, jamais pour une forme couverte par la grammaire (CA12).
    """
    resultat = parser_saisie(texte, current_context())
    if resultat.reconnu:
        return resultat.items

    items = parse_commande(texte, ctx=current_context())
    for item in items:
        if isinstance(item, dict):
            item.setdefault("origine_parsing", ORIGINE_LLM)
    return items


def _normalize_items(items: list, texte_original: str = "") -> list:
    """
    Normalise la réponse Groq :
    1. Si action=null → inférence depuis le texte original
    2. Si culture/quantite sont des listes → explosion en objets séparés
    """
    normalized = []
    for item in items:
        # ── Inférence des champs null depuis le texte original ───────────────
        item = dict(item)
        if texte_original:
            if item.get("action") is None:
                inferred = _infer_action(texte_original)
                if inferred:
                    item["action"] = inferred
                    log.info(f"🔧 ACTION INFÉRÉE  : '{inferred}'")
            if item.get("culture") is None:
                action = item.get("action","")
                if action not in {"arrosage","desherbage","fertilisation"}:
                    inferred = _infer_culture(texte_original)
                    if inferred:
                        item["culture"] = inferred
                        log.info(f"🔧 CULTURE INFÉRÉE : '{inferred}'")
            if item.get("date") is None:
                # N'inférer la date que si le texte source contient un mot temporel explicite
                if texte_original and any(m in texte_original.lower() for m in TEMPORAL_MAP):
                    inferred = _infer_date(texte_original)
                    if inferred:
                        item["date"] = inferred
                        log.info(f"🔧 DATE INFÉRÉE    : '{inferred}'")

        culture  = item.get("culture")
        quantite = item.get("quantite")

        # Cas normal : culture est une string → pas de transformation
        if not isinstance(culture, list):
            normalized.append(item)
            continue

        # Cas Groq défaillant : culture est une liste
        log.warning(f"⚠️  NORMALISATION  : Groq a retourné des listes, explosion en {len(culture)} objets")
        for i, cult in enumerate(culture):
            new_item = dict(item)
            new_item["culture"] = cult
            if isinstance(quantite, list) and i < len(quantite):
                new_item["quantite"] = quantite[i]
            elif isinstance(quantite, list):
                new_item["quantite"] = None
            normalized.append(new_item)

    return normalized
