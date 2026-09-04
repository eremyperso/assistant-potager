"""
app/services/metriques_routage.py — Métriques de routage, zéro jeton [US-097]
================================================================================
[CA8] Aucune métrique ici n'appelle un modèle : uniquement des agrégations SQL
sur `routage_logs` / `routage_retours` / `conso_tokens`, et un calcul de
percentile fait en Python (portable SQLite ↔ PostgreSQL, les deux backends
utilisés par ce projet — voir tests/conftest.py).

[US-098 / CA14] Deux agrégations de plus, sur les mêmes principes : `resume_savoir`
et `questions_sans_savoir` publient ce à quoi la base de connaissance ne répond
pas. Ce ne sont pas des indicateurs de confort — ce sont eux qui décident du
contenu à écrire dans US-099, US-140 et US-141.

[CA7] Ce module alimente un point d'accès en lecture seule réservé à
l'administrateur (`main.py`). Aucun tableau de bord graphique n'est construit
ici, volontairement — l'écran viendra si, et seulement si, ces chiffres sont
consultés régulièrement.
"""
from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import ConsoTokens, RoutageLog, RoutageRetour
from llm.passerelle import ISSUE_OK, TYPE_PARSING
from llm.routeur import (
    ETAGE_CACHE,
    ETAGE_DONNEE,
    ETAGE_RAISONNEMENT,
    ETAGE_SAVOIR,
    ORIGINE_CACHE,
)
from app.services.connaissance import ISSUE_SERVI, ISSUE_TRANSMIS, ISSUE_VIDE
from app.services.retours import AVIS_NEGATIF

log = logging.getLogger("potager")

# [CA3] Rétention documentée : 12 mois.
RETENTION_JOURS = 365

# [US-095] ETAGE_CACHE en tete : c'est le premier etage traverse par une
# question, et celui dont la part conditionne tout le dimensionnement.
ETAGES_CONNUS: tuple[str, ...] = (ETAGE_CACHE, ETAGE_DONNEE, ETAGE_SAVOIR, ETAGE_RAISONNEMENT)

# [CA6] Hypothèses de répartition du document d'architecture cible
# (docs/ARCHITECTURE_CIBLE_V2_reponses.md §7.1) : ~40 % commande ou cache,
# ~35 % agrégation SQL, ~20 % savoir, ~5 % raisonnement.
HYPOTHESES_REPARTITION: dict[str, float] = {
    "commande_ou_cache": 0.40,
    "agregation_sql": 0.35,
    "savoir": 0.20,
    "raisonnement": 0.05,
}


def _requete_periode(db: Session, depuis: Optional[datetime], jusqu_a: Optional[datetime]):
    requete = db.query(RoutageLog)
    if depuis is not None:
        requete = requete.filter(RoutageLog.cree_le >= depuis)
    if jusqu_a is not None:
        requete = requete.filter(RoutageLog.cree_le <= jusqu_a)
    return requete


def _p95(valeurs: list[int]) -> Optional[float]:
    """Percentile 95, méthode du rang le plus proche — sans dépendance à une
    fonction SQL spécifique à un moteur (SQLite n'a pas PERCENTILE_CONT)."""
    if not valeurs:
        return None
    valeurs_triees = sorted(valeurs)
    rang = max(1, math.ceil(0.95 * len(valeurs_triees)))
    return float(valeurs_triees[rang - 1])


def resume_par_etage(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> dict[str, dict]:
    """[CA5] Taux de résolution et latence p95 par étage ayant produit la
    réponse finale (`etage_resolveur`), sur la période demandée."""
    lignes = (
        _requete_periode(db, depuis, jusqu_a)
        .with_entities(RoutageLog.etage_resolveur, RoutageLog.latence_ms)
        .all()
    )
    total = len(lignes)
    par_etage: dict[str, list[int]] = {etage: [] for etage in ETAGES_CONNUS}
    for etage, latence_ms in lignes:
        par_etage.setdefault(etage, []).append(latence_ms)

    return {
        etage: {
            "nb_reponses": len(latences),
            "taux_resolution": (len(latences) / total) if total else 0.0,
            "latence_p95_ms": _p95(latences),
        }
        for etage, latences in par_etage.items()
    }


def jetons_moyens_par_question(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> Optional[float]:
    """[CA5] Jetons moyens consommés par question, routage (classification)
    inclus — lu directement sur `routage_logs.tokens_consommes`, déjà cumulé
    sur toute la cascade par `llm.passerelle.cumul_mesure_cascade`."""
    moyenne = _requete_periode(db, depuis, jusqu_a).with_entities(
        func.avg(RoutageLog.tokens_consommes)
    ).scalar()
    return float(moyenne) if moyenne is not None else None


def taux_donnees_sans_modele(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> Optional[float]:
    """[US-096 / CA6] Part des questions de données résolues **sans aucun appel
    au modèle** — l'indicateur principal de succès des gabarits sur agrégats SQL.

    Se lit directement sur `routage_logs`, sans colonne nouvelle : une cascade
    dont `tokens_consommes` vaut 0 n'a déclenché aucun appel modèle, pas même la
    classification (le total est cumulé sur toute la cascade par
    `llm.passerelle.cumul_mesure_cascade`). Renvoie `None` si aucune question de
    données n'a été servie sur la période — rien à rapporter, ce qui est
    différent de « 0 % sans modèle ».
    """
    lignes = (
        _requete_periode(db, depuis, jusqu_a)
        .filter(RoutageLog.etage_resolveur == ETAGE_DONNEE)
        .with_entities(RoutageLog.tokens_consommes)
        .all()
    )
    if not lignes:
        return None
    sans_modele = sum(1 for (tokens,) in lignes if not tokens)
    return sans_modele / len(lignes)


def taux_remontee_cascade(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> float:
    """[CA5] Part des questions où l'étage donnée n'a pas su répondre et où le
    raisonnement a pris le relais (US-093 CA7)."""
    requete = _requete_periode(db, depuis, jusqu_a)
    total = requete.count()
    if not total:
        return 0.0
    remontees = requete.filter(RoutageLog.cascade_remontee.is_(True)).count()
    return remontees / total


def taux_service_cache(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> float:
    """[CA5] Part des classifications servies depuis le cache en mémoire du
    routeur (`origine_classification = 'cache'`) plutôt que par une règle ou
    un appel modèle."""
    requete = _requete_periode(db, depuis, jusqu_a)
    total = requete.count()
    if not total:
        return 0.0
    # [US-095] Les reponses servies par l'etage 0bis portent elles aussi
    # `origine_classification = 'cache'` — a juste titre, leur classification
    # vient bien d'un cache. Elles sont exclues ici pour que cet indicateur
    # continue de mesurer ce qu'il annonce : le cache en memoire des
    # CLASSIFICATIONS. Le cache de REPONSES se mesure par
    # `taux_service_cache_reponses()` ci-dessous.
    depuis_cache = (
        requete.filter(RoutageLog.origine_classification == ORIGINE_CACHE)
        .filter(RoutageLog.etage_resolveur != ETAGE_CACHE)
        .count()
    )
    return depuis_cache / total


def taux_service_cache_reponses(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> dict:
    """[US-095 / CA12] Part des questions servies par le cache de RÉPONSES
    (étage 0bis, `etage_resolveur = 'cache'`), confrontée à l'hypothèse de
    dimensionnement.

    L'hypothèse de ~40 % de questions résolues à cet étage est la plus
    structurante du document d'architecture cible (§7.1) : c'est elle qui
    justifie l'existence même de la cascade. L'US impose qu'elle soit
    **vérifiée par la mesure ou corrigée, jamais affirmée** — ce qui est publié
    ici est donc le chiffre observé ET l'écart, sans renormalisation ni
    arrondi flatteur.

    `taux` vaut `None` si aucune question n'a été journalisée sur la période :
    rien à rapporter, ce qui est différent de « 0 % servi depuis le cache ».
    Cette distinction compte : la première itération après le déploiement
    affichera légitimement un taux très bas — un cache vide ne sert rien tant
    qu'il ne s'est pas rempli de ce qui est réellement demandé (aucun
    préchauffage, arbitrage tranché de l'US).
    """
    requete = _requete_periode(db, depuis, jusqu_a)
    total = requete.count()
    if not total:
        return {
            "taux": None,
            "nb_servies": 0,
            "nb_questions": 0,
            "hypothese": HYPOTHESES_REPARTITION["commande_ou_cache"],
            "ecart": None,
        }
    nb_servies = requete.filter(RoutageLog.etage_resolveur == ETAGE_CACHE).count()
    taux = nb_servies / total
    hypothese = HYPOTHESES_REPARTITION["commande_ou_cache"]
    return {
        "taux": taux,
        "nb_servies": nb_servies,
        "nb_questions": total,
        "hypothese": hypothese,
        # Négatif = la mesure est en dessous de l'hypothèse. Publié tel quel :
        # c'est l'hypothèse qui se corrige dans le document, pas la mesure qui
        # s'ajuste ici.
        "ecart": taux - hypothese,
        "note": (
            "L'hypothèse 'commande_ou_cache' du document d'architecture (40 %) "
            "couvre aussi les saisies d'action, qui ne transitent pas par "
            "routage_logs : la comparaison est une borne basse du taux "
            "d'hypothèse, pas une égalité de périmètre."
        ),
    }


def part_parseur_deterministe(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> Optional[float]:
    """[CA5] Part des saisies d'action traitées par un parseur déterministe
    plutôt que par le modèle de langage.

    US-094 (parseur déterministe pour les saisies courantes) n'est pas encore
    livrée : aujourd'hui, TOUTE saisie d'action passe par l'appel modèle
    `appel_type='parsing'` mesuré dans `conso_tokens` (`llm/groq_client.py`).
    Cette fonction renvoie donc honnêtement `0.0` tant qu'aucune saisie
    n'échappe à cet appel — c'est la mesure elle-même qui motivera US-094,
    pas une estimation. Renvoie `None` si aucune saisie d'action n'a été
    mesurée sur la période (rien à rapporter, différent de "0 % déterministe").
    """
    requete = db.query(ConsoTokens).filter(
        ConsoTokens.appel_type == TYPE_PARSING, ConsoTokens.issue == ISSUE_OK
    )
    if depuis is not None:
        requete = requete.filter(ConsoTokens.cree_le >= depuis)
    if jusqu_a is not None:
        requete = requete.filter(ConsoTokens.cree_le <= jusqu_a)
    total_llm = requete.count()
    if not total_llm:
        return None
    return 0.0


def comparaison_hypotheses(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> dict:
    """[CA6] Confronte la répartition réelle par nature de demande aux
    hypothèses 40/35/20/5 du document d'architecture, et publie l'écart tel
    quel — la correction d'une hypothèse invalidée se fait dans le document,
    jamais en la contournant ici (ex. en renormalisant les pourcentages).

    Correspondance approximative, documentée pour ne pas laisser croire à une
    précision qu'elle n'a pas : `routage_logs` ne journalise que les demandes
    dont la cascade va à son terme (`routeur.repondre_avec_cascade`) — les
    commandes d'action, classées par le même `routeur.classer_demande` depuis
    US-170 mais qui ne traversent jamais la cascade, ne transitent pas par
    cette table.
    Le taux réel de la catégorie "commande_ou_cache" ne peut donc PAS être
    déduit d'ici ; seules QUESTION_DATA / QUESTION_SAVOIR / QUESTION_HYBRIDE
    sont mesurables aujourd'hui.
    """
    lignes = (
        _requete_periode(db, depuis, jusqu_a)
        .with_entities(RoutageLog.nature, func.count(RoutageLog.id))
        .group_by(RoutageLog.nature)
        .all()
    )
    total = sum(nb for _, nb in lignes)
    reel = {nature: (nb / total if total else 0.0) for nature, nb in lignes}

    return {
        "hypotheses": dict(HYPOTHESES_REPARTITION),
        "reel_par_nature": reel,
        "note": (
            "routage_logs ne journalise que les demandes classées comme "
            "questions (QUESTION_DATA/QUESTION_SAVOIR/QUESTION_HYBRIDE) ; la "
            "catégorie d'hypothèse 'commande_ou_cache' couvre aussi les "
            "saisies d'action, non mesurées ici tant qu'US-094 n'est pas "
            "livrée. L'étage 2 (savoir, US-098) est branché depuis le "
            "02/09/2026 mais son corpus est vide tant qu'US-099/US-140/US-141 "
            "ne sont pas livrées : sa part observée reste donc nulle par "
            "construction, et non par défaut de mesure."
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# [US-098 / CA14] Ce à quoi la base de connaissance ne répond pas
# ─────────────────────────────────────────────────────────────────────────────
def resume_savoir(
    db: Session, depuis: Optional[datetime] = None, jusqu_a: Optional[datetime] = None
) -> dict:
    """[US-098 / CA14] Répartition des issues de l'étage du savoir sur la
    période, et score moyen par issue.

    Trois issues, trois lectures : `servi` mesure ce que le corpus couvre
    réellement à coût nul, `transmis` ce qu'il couvre à moitié, `vide` ce qu'il
    ne couvre pas du tout. C'est le rapport entre les trois qui dit si l'étage
    mérite de rester actif, pas le volume brut.
    """
    lignes = (
        _requete_periode(db, depuis, jusqu_a)
        .filter(RoutageLog.issue_savoir.isnot(None))
        .with_entities(RoutageLog.issue_savoir, RoutageLog.score_savoir)
        .all()
    )
    total = len(lignes)
    par_issue: dict[str, dict] = {}
    for issue in (ISSUE_SERVI, ISSUE_TRANSMIS, ISSUE_VIDE):
        scores = [score for autre, score in lignes if autre == issue and score is not None]
        nb = sum(1 for autre, _ in lignes if autre == issue)
        par_issue[issue] = {
            "nb": nb,
            "part": round(nb / total, 4) if total else 0.0,
            "score_moyen": round(sum(scores) / len(scores), 4) if scores else None,
        }
    return {"total_recherches": total, "par_issue": par_issue}


def questions_sans_savoir(
    db: Session, limite: int = 20, depuis: Optional[datetime] = None
) -> list[dict]:
    """[US-098 / CA14] Questions que la base de connaissance n'a pas su servir,
    les plus fréquentes d'abord.

    C'est LA liste qui définit le contenu à écrire ensuite (US-099, US-140,
    US-141) : une question posée souvent et jamais servie vaut une fiche, une
    question posée une fois n'en vaut pas forcément une. `issue_savoir='vide'`
    et `'transmis'` sont comptés séparément — « rien trouvé » appelle une fiche
    nouvelle, « trouvé mais pas assez sûr » appelle plutôt de relire l'existante.
    """
    requete = db.query(
        RoutageLog.question_normalisee,
        RoutageLog.issue_savoir,
        func.count(RoutageLog.id),
    ).filter(RoutageLog.issue_savoir.in_((ISSUE_VIDE, ISSUE_TRANSMIS)))
    if depuis is not None:
        requete = requete.filter(RoutageLog.cree_le >= depuis)
    lignes = (
        requete.group_by(RoutageLog.question_normalisee, RoutageLog.issue_savoir)
        .order_by(func.count(RoutageLog.id).desc())
        .limit(limite)
        .all()
    )
    return [
        {"question_normalisee": question, "issue": issue, "nb": nb}
        for question, issue, nb in lignes
    ]


def top_questions_mal_notees(
    db: Session, limite: int = 20, depuis: Optional[datetime] = None
) -> list[dict]:
    """[CA12] Questions les plus souvent jugées mauvaises, regroupées par
    question normalisée — alimente le corpus de routage (US-093/CA9) et la
    liste des lacunes de la base de connaissance."""
    requete = (
        db.query(RoutageLog.question_normalisee, func.count(RoutageRetour.id))
        .join(RoutageRetour, RoutageRetour.routage_log_id == RoutageLog.id)
        .filter(RoutageRetour.avis == AVIS_NEGATIF)
    )
    if depuis is not None:
        requete = requete.filter(RoutageLog.cree_le >= depuis)
    lignes = (
        requete.group_by(RoutageLog.question_normalisee)
        .order_by(func.count(RoutageRetour.id).desc())
        .limit(limite)
        .all()
    )
    return [{"question_normalisee": question, "nb_avis_negatifs": nb} for question, nb in lignes]


def purger_routage_logs_expires(
    db: Session, limite_jours: int = RETENTION_JOURS, maintenant: Optional[datetime] = None
) -> int:
    """[CA3] Supprime les entrées de journal de routage antérieures à la
    rétention documentée (12 mois par défaut), et les avis qui s'y
    rattachaient. Aucune contrainte `ON DELETE CASCADE` dans ce projet (voir
    `app.services.potagers.purger_potager`) : les retours sont supprimés
    explicitement avant les entrées de journal qu'ils référencent.
    """
    seuil = (maintenant or datetime.utcnow()) - timedelta(days=limite_jours)
    ids_expires = [
        ligne.id for ligne in db.query(RoutageLog.id).filter(RoutageLog.cree_le <= seuil).all()
    ]
    if not ids_expires:
        return 0

    db.query(RoutageRetour).filter(
        RoutageRetour.routage_log_id.in_(ids_expires)
    ).delete(synchronize_session=False)
    nb_supprimes = db.query(RoutageLog).filter(
        RoutageLog.id.in_(ids_expires)
    ).delete(synchronize_session=False)
    db.commit()
    log.info(
        "[US-097] Purge rétention routage_logs : %s entrée(s) au-delà de %s jours",
        nb_supprimes, limite_jours,
    )
    return nb_supprimes
