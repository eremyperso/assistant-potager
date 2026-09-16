"""États conversationnels en attente (dictionnaires partagés) et leurs délais d'expiration.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""


# ── [US-019] SÉLECTION VARIÉTÉ MISE EN GODET ────────────────────────────────────
# Stocke les items mise_en_godet en attente de sélection de variété {user_id: {parsed, texte, ts}}
_GODET_PENDING: dict[int, dict] = {}


_GODET_TIMEOUT = 60  # secondes


# [vendu/perte_godet] Disambiguation perte jardin vs pépinière {user_id: {item, texte, godets, ts}}
_PERTE_PENDING: dict[int, dict] = {}


_PERTE_TIMEOUT = 90  # secondes


# [US-021] Actions en attente de confirmation {user_id: {items, texte, ts}}
_ACTION_PENDING: dict[int, dict] = {}


_ACTION_TIMEOUT = 60  # secondes


# [US-038] Notes en attente de confirmation {user_id: {categorie, fields, texte, ts}}
_NOTE_PENDING: dict[int, dict] = {}


_NOTE_TIMEOUT = 60  # secondes


_UNITES_SEMIS_VALIDES: frozenset[str] = frozenset({"graine", "graines", "plant", "plants"})


# [US-037] La normalisation d'unité de semis ("graines"|"pieds"|"m²") vit désormais
# dans app/services/evenements.py (seul appelant : creer_evenement_confirme).

_RECOLTE_PENDING: dict[int, dict] = {}


_RECOLTE_TIMEOUT = 60  # secondes


_VENDU_PENDING: dict[int, dict] = {}


_VENDU_TIMEOUT  = 60  # secondes


_QUANTITE_PENDING: dict[int, dict] = {}


_QUANTITE_TIMEOUT = 60  # secondes


# [US-036 CA10] Récolte végétative pesée sans nombre de pieds → clarification {user_id: {items, texte, ts}}
_RECOLTE_PIECES_PENDING: dict[int, dict] = {}


_RECOLTE_PIECES_TIMEOUT = 60  # secondes


# [US-037 CA7] Semis d'une culture absente de CultureConfig → clarification végétatif/reproducteur
_SEMIS_CULTURE_PENDING: dict[int, dict] = {}


_SEMIS_CULTURE_TIMEOUT = 90  # secondes


# [fix rattachement lot godet] Plusieurs lots de semis candidats → choix du lot parent
_GODET_LOT_PENDING: dict[int, dict] = {}


_GODET_LOT_TIMEOUT = 120  # secondes


# [US-066] Mise en godet sans « sur N graines » → réclamation du nombre d'origine
_GODET_GRAINES_PENDING: dict[int, dict] = {}


_GODET_GRAINES_TIMEOUT = 180  # secondes


# ── [US-021] CONFIRMATION AVANT ENREGISTREMENT ──────────────────────────────────

# Actions qui créent la présence d'une culture (source) → liste complète des parcelles
_ACTIONS_SOURCE = {"plantation", "semis", "mise_en_godet", "vendu", "perte_godet"}
