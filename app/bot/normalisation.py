"""Inférence et normalisation des items dictés (action, culture, date).

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
from llm.groq_client import parse_commande
from llm.parseur_deterministe import ORIGINE_LLM, parser_saisie
from app.services.context import current_context
from app.services import normalisation_gestes as svc_normalisation
# [US-270] Les constantes et l'inférence vivent dans le service, communes au bot et à l'API.
from app.services.normalisation_gestes import (  # noqa: F401
    ACTION_KEYWORDS, CULTURES_CONNUES, TEMPORAL_MAP,
    _infer_action, _infer_culture, _infer_date, _last_weekday,
)
from .noyau import log


def _parser_items(texte: str) -> list:
    """[US-094 / CA1] Étage 0 de la saisie : grammaire déterministe, puis repli modèle.

    [US-270] Le code est dans `normalisation_gestes.parser_items`, partagé avec l'API ; les
    parseurs passés sont ceux de CE module, que les tests remplacent.
    """
    return svc_normalisation.parser_items(
        texte, current_context(), parseur=parser_saisie, modele=parse_commande,
    )


def _normalize_items(items: list, texte_original: str = "") -> list:
    """Normalise la réponse du parseur — voir `normalisation_gestes.normaliser_items` [US-270]."""
    return svc_normalisation.normaliser_items(items, texte_original)
