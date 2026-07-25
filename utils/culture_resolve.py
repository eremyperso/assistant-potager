"""
utils/culture_resolve.py — Résolution d'une culture/variété saisie en langage libre
(dictée, extraite par Groq) vers la valeur canonique déjà connue en base.

Même stratégie que utils.parcelles.resolve_parcelle : exact → Levenshtein ≤ 2 →
sous-chaîne (mot-clé). Réutilise la même implémentation Levenshtein pure Python,
pas de nouvelle dépendance.

Contrairement à resolve_parcelle (qui bloque si la parcelle n'existe pas), une
culture/variété non reconnue est conservée telle quelle : contrairement à une
parcelle, une culture peut légitimement être nouvelle (jamais saisie avant).
"""
from unidecode import unidecode

from database.models import Evenement, CultureConfig
from utils.parcelles import levenshtein_distance

_LEVENSHTEIN_MAX = 2


def _normalise(texte: str) -> str:
    return unidecode((texte or "").strip().lower())


def cultures_connues(db, potager_id: int) -> list[str]:
    """Cultures distinctes déjà utilisées (evenements + culture_config), casse d'origine.

    [fix isolation multi-tenant] `evenements` est scopé au potager courant ;
    `culture_config` inclut aussi les entrées globales (`potager_id IS NULL`,
    catalogue partagé), mais jamais celles d'un AUTRE potager précis."""
    from sqlalchemy import or_
    depuis_evenements = (
        db.query(Evenement.culture)
        .filter(Evenement.culture.isnot(None), Evenement.potager_id == potager_id)
        .distinct().all()
    )
    depuis_config = (
        db.query(CultureConfig.nom)
        .filter(or_(CultureConfig.potager_id == potager_id, CultureConfig.potager_id.is_(None)))
        .all()
    )
    noms = {c for (c,) in depuis_evenements if c} | {c for (c,) in depuis_config if c}
    return sorted(noms)


def varietes_connues(db, potager_id: int, culture: str) -> list[str]:
    """Variétés distinctes déjà associées à cette culture (comparaison insensible à la casse),
    [fix isolation multi-tenant] scopées au potager courant."""
    from sqlalchemy import func
    rows = (
        db.query(Evenement.variete)
        .filter(
            func.lower(Evenement.culture) == culture.lower(),
            Evenement.variete.isnot(None),
            Evenement.potager_id == potager_id,
        )
        .distinct()
        .all()
    )
    return sorted({v for (v,) in rows if v})


def _meilleure_correspondance(brut: str, connus: list[str]) -> str | None:
    """Applique le triptyque exact → Levenshtein ≤ 2 → sous-chaîne sur une liste de valeurs connues."""
    cible = _normalise(brut)
    if not cible:
        return None

    for c in connus:
        if _normalise(c) == cible:
            return c

    meilleur, meilleure_dist = None, _LEVENSHTEIN_MAX + 1
    for c in connus:
        d = levenshtein_distance(_normalise(c), cible)
        if d <= _LEVENSHTEIN_MAX and d < meilleure_dist:
            meilleur, meilleure_dist = c, d
    if meilleur:
        return meilleur

    for c in connus:
        cn = _normalise(c)
        if cn and (cn in cible or cible in cn):
            return c

    return None


def culture_deja_plantee(db, potager_id: int, culture: str) -> bool:
    """
    Vrai si `culture` a déjà été introduite dans CE potager via un semis, une
    plantation ou une mise en godet (comparaison insensible à la casse/accents).

    Sert de garde-fou pour les actions qui supposent une culture déjà en place
    (récolte, perte, arrosage...) : contrairement à une parcelle incohérente,
    récolter une culture jamais semée/plantée n'a aucun scénario légitime —
    c'est soit une hallucination Groq, soit une faute de frappe/homonymie.

    [fix isolation multi-tenant] Scopé à `potager_id` — sans ce filtre, une
    culture plantée dans N'IMPORTE QUEL AUTRE potager de la base neutralisait
    ce garde-fou pour tous les potagers (bug rapporté : récolte enregistrée
    sur une culture jamais plantée dans le potager courant).
    """
    if not culture or not culture.strip():
        return True  # rien à vérifier, laisse passer (comportement neutre)
    cible = _normalise(culture)
    rows = (
        db.query(Evenement.culture)
        .filter(
            Evenement.type_action.in_(["semis", "plantation", "mise_en_godet"]),
            Evenement.culture.isnot(None),
            Evenement.potager_id == potager_id,
        )
        .distinct()
        .all()
    )
    return any(_normalise(c) == cible for (c,) in rows)


def resolve_culture(db, potager_id: int, culture_brute: str | None) -> str | None:
    """
    Résout une culture saisie en langage libre vers son nom canonique en base.
    Si aucune correspondance n'est trouvée, retourne la valeur brute telle quelle
    (une culture inconnue peut être légitimement nouvelle, contrairement à une parcelle).
    [fix isolation multi-tenant] Scopé à `potager_id`.
    """
    if not culture_brute or not culture_brute.strip():
        return culture_brute
    match = _meilleure_correspondance(culture_brute, cultures_connues(db, potager_id))
    return match if match else culture_brute.strip()


def resolve_variete(db, potager_id: int, culture_resolue: str | None, variete_brute: str | None) -> str | None:
    """
    Résout une variété saisie en langage libre vers son nom canonique en base,
    parmi les variétés déjà associées à `culture_resolue`. Retourne la valeur
    brute si aucune variété connue ne correspond (culture inconnue, ou variété
    réellement nouvelle pour cette culture).
    [fix isolation multi-tenant] Scopé à `potager_id`.
    """
    if not variete_brute or not variete_brute.strip():
        return variete_brute
    if not culture_resolue:
        return variete_brute.strip()

    connues = varietes_connues(db, potager_id, culture_resolue)
    if not connues:
        return variete_brute.strip()

    match = _meilleure_correspondance(variete_brute, connues)
    return match if match else variete_brute.strip()
