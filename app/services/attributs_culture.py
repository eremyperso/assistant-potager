"""
app/services/attributs_culture.py — Attributs agronomiques de conduite [US-161]
--------------------------------------------------------------------------------
Exposition, besoin en eau, profondeur de semis, rusticité minimale : des
**attributs**, c'est-à-dire de la donnée qui s'affiche, se filtre et se trie
sans jamais passer par un modèle de langage. C'est la règle qui gouverne le
découpage de tout l'ÉPIC 6 — *tout ce qui peut être une colonne ou une arête ne
doit jamais être un fragment de texte*. Un attribut rendu par une recherche
plein texte avec un score de 0,72 est une régression : la profondeur de semis
d'un radis est un fait, pas une probabilité.

Ce module est le **seul** point de validation et d'écriture de ces quatre
attributs. L'import du référentiel structuré (`import_referentiel`) et la
correction au bot (`bot.cmd_culture`) y passent tous les deux — « aucun second
mécanisme », comme le pose US-140.

Les quatre règles qu'il fait tenir
----------------------------------
1. **Vocabulaire fermé (CA2).** Exposition et besoin en eau ne sont pas des
   champs de texte libre : une valeur hors vocabulaire est refusée et
   l'attribut conserve sa valeur précédente. Accepter n'importe quelle chaîne
   « pour ne pas bloquer la saisie » coûte deux écrans plus loin — un filtre sur
   l'exposition devient impossible, et le tri de la vue Cultures perd son sens.
2. **Non renseigné se dit (CA4).** Un attribut absent se lit « non renseigné ».
   Il n'est jamais deviné, jamais remplacé par une moyenne, jamais complété par
   un modèle de langage — principe d'honnêteté de l'Épic 5 §4.
3. **La correction du jardinier gagne (CA6).** Toute écriture d'ici s'attribue
   l'origine `saisie_manuelle` sur **le seul attribut corrigé**, ce que l'import
   relit pour ne jamais l'écraser au rejeu suivant. Une source par attribut et
   non par ligne : corriger la profondeur ne doit pas geler l'exposition, que
   l'import doit continuer de rafraîchir.
4. **Aucun chiffre inventé (CA10).** Profondeur et rusticité ne viennent que de
   l'import d'US-166 ou de la saisie du jardinier. Ce module ne calcule aucune
   valeur par défaut et n'appelle aucun modèle.

Ce qui n'entre PAS ici
----------------------
Aucun attribut de **calendrier** (CA8) — fenêtre de semis, durée de germination,
date : ils appartiennent au référentiel calendrier d'US-068, décliné par zone
climatique et recalé sur les événements réels. Aucune **relation** (CA9) —
association, rotation, bioagresseur : ce sont des arêtes (US-162, US-163), pas
des colonnes. Deux vérités concurrentes, dont l'une serait fausse.

Portée d'une correction
-----------------------
Comme la famille botanique (US-067 / CA7), ces attributs sont **partagés** : les
54 lignes de `culture_config` mesurées le 25/08/2026 ne portent aucun
`potager_id`. Une correction s'applique donc à toutes les fiches qui partagent
ce nom de culture et bénéficie à tous les potagers — cohérent pour un fait
agronomique, et assumé comme tel.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session
from unidecode import unidecode

from app.services import referentiel_sources as svc_sources
from database.models import CultureConfig, ReferentielSource
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

#: [CA4] Ce que vaut un attribut absent — une phrase, jamais une valeur moyenne.
NON_RENSEIGNE = "non renseigné"

# ── [CA2] Les deux vocabulaires fermés ───────────────────────────────────────
#: Valeurs canoniques de l'exposition. La casse et les accents sont indifférents
#: à la saisie (« Plein Soleil », « mi ombre »), mais la valeur **stockée** est
#: toujours l'une de ces trois-là : c'est ce qui rend le filtre et le tri
#: possibles côté vue Cultures, au lieu de renormaliser à l'affichage ce qui
#: aurait dû l'être à l'écriture.
EXPOSITIONS: tuple[str, ...] = ("plein soleil", "mi-ombre", "ombre")

#: Valeurs canoniques du besoin en eau.
BESOINS_EAU: tuple[str, ...] = ("faible", "moyen", "élevé")


class ValeurHorsVocabulaireError(ValueError):
    """[CA2] Valeur refusée — l'attribut conserve sa valeur précédente."""


@dataclass(frozen=True)
class Attribut:
    """Description d'un attribut agronomique : sa colonne, sa source, ses règles."""

    cle: str
    colonne: str
    colonne_source: str
    libelle: str
    #: Non vide pour un attribut qualitatif à vocabulaire fermé (CA2), vide pour
    #: un attribut numérique.
    vocabulaire: tuple[str, ...] = ()
    unite: str = ""
    #: Bornes de vraisemblance des attributs numériques. Elles ne remplacent pas
    #: une source (CA10) : elles écartent la faute de frappe (« 150 » cm de
    #: profondeur de semis), pas l'absence de fondement.
    minimum: Optional[float] = None
    maximum: Optional[float] = None

    @property
    def est_qualitatif(self) -> bool:
        return bool(self.vocabulaire)


#: Le référentiel d'attributs, dans l'ordre où une fiche les présente.
#: Ajouter un attribut agronomique se fait ici **et** dans la migration : le
#: bot, l'import et la lecture le suivent sans une ligne de plus.
ATTRIBUTS: tuple[Attribut, ...] = (
    Attribut(
        cle="exposition",
        colonne="exposition",
        colonne_source="exposition_source_id",
        libelle="Exposition",
        vocabulaire=EXPOSITIONS,
    ),
    Attribut(
        cle="besoin_eau",
        colonne="besoin_eau",
        colonne_source="besoin_eau_source_id",
        libelle="Besoin en eau",
        vocabulaire=BESOINS_EAU,
    ),
    Attribut(
        cle="profondeur_semis_cm",
        colonne="profondeur_semis_cm",
        colonne_source="profondeur_semis_source_id",
        libelle="Profondeur de semis",
        unite="cm",
        minimum=0.0,
        maximum=30.0,
    ),
    Attribut(
        cle="rusticite_min_c",
        colonne="rusticite_min_c",
        colonne_source="rusticite_min_source_id",
        libelle="Rusticité minimale",
        unite="°C",
        minimum=-40.0,
        maximum=20.0,
    ),
)

ATTRIBUTS_PAR_CLE: dict[str, Attribut] = {a.cle: a for a in ATTRIBUTS}

#: Alias tolérés à la saisie au bot — le jardinier tape « eau », pas
#: « besoin_eau ». Ce sont des synonymes de commande, jamais des colonnes.
ALIAS_ATTRIBUTS: dict[str, str] = {
    "exposition": "exposition",
    "expo": "exposition",
    "eau": "besoin_eau",
    "besoin_eau": "besoin_eau",
    "arrosage": "besoin_eau",
    "profondeur": "profondeur_semis_cm",
    "profondeur_semis": "profondeur_semis_cm",
    "profondeur_semis_cm": "profondeur_semis_cm",
    "rusticite": "rusticite_min_c",
    "rusticite_min_c": "rusticite_min_c",
    "gel": "rusticite_min_c",
}

#: [CA7] Les dix cultures du périmètre initial (US-140 / CA1), mesurées le
#: 25/08/2026 : elles portent 53 % des événements réels.
#:
#: ⚠️ Cette liste est mesurée sur la base de **développement** et doit être
#: reconfirmée sur la production avant tout pré-remplissage : les huit premières
#: sont nettes, les rangs 9 et 10 (ail, blette) sont départagés par ordre
#: alphabétique entre six cultures à égalité (ail, blette, fève, petit pois,
#: poireau, épinard).
#:
#: Ce n'est pas une liste indicative : l'import s'y tient et ignore le reste.
#: 14 des 54 configurations existantes ne portent aucun événement — peupler les
#: écrans de cultures jamais cultivées est un risque constaté, pas théorique.
CULTURES_PERIMETRE_INITIAL: tuple[str, ...] = (
    "tomate", "haricot", "courgette", "chou", "carotte",
    "concombre", "cornichon", "poivron", "ail", "blette",
)


@dataclass(frozen=True)
class AttributLu:
    """Un attribut tel qu'une fiche le restitue — valeur, origine, ou son absence."""

    cle: str
    libelle: str
    valeur: Any
    affichage: str
    source_code: Optional[str]
    attribution: Optional[str]

    @property
    def renseigne(self) -> bool:
        return self.valeur is not None


def _cle_comparaison(valeur: str) -> str:
    """Casse, accents, tirets et espaces multiples indifférents à la saisie.

    « Plein Soleil », « plein  soleil » et « mi ombre » atteignent leur valeur
    canonique ; « au soleil le matin » n'atteint rien et sera refusé (CA2)."""
    sans_accent = unidecode((valeur or "").strip().lower())
    return " ".join(sans_accent.replace("-", " ").split())


def normaliser_valeur(cle: str, valeur: Any) -> Any:
    """
    [CA2, CA10] Valide une valeur et retourne sa forme canonique, ou refuse.

    Qualitatif : la valeur doit atteindre le vocabulaire fermé, casse et accents
    indifférents. Numérique : entier ou décimal, virgule acceptée (« 1,5 »),
    borné au vraisemblable. Dans les deux cas, `None` reste `None` — effacer un
    attribut est légitime, et bien plus honnête que de lui donner une moyenne.

    Lève `ValeurHorsVocabulaireError`, dont le message énonce ce qui est admis :
    c'est ce message que le jardinier lit dans le bot.
    """
    attribut = ATTRIBUTS_PAR_CLE.get(cle)
    if attribut is None:
        raise KeyError(cle)

    if valeur is None or (isinstance(valeur, str) and not valeur.strip()):
        return None

    if attribut.est_qualitatif:
        cible = _cle_comparaison(str(valeur))
        for canonique in attribut.vocabulaire:
            if _cle_comparaison(canonique) == cible:
                return canonique
        raise ValeurHorsVocabulaireError(
            f"« {str(valeur).strip()} » n'est pas une valeur admise pour "
            f"{attribut.libelle.lower()}. Valeurs possibles : "
            f"{', '.join(attribut.vocabulaire)}."
        )

    try:
        nombre = float(str(valeur).strip().replace(",", "."))
    except (TypeError, ValueError):
        raise ValeurHorsVocabulaireError(
            f"{attribut.libelle} attend un nombre en {attribut.unite} "
            f"(reçu : « {valeur} »)."
        ) from None
    if attribut.minimum is not None and nombre < attribut.minimum:
        raise ValeurHorsVocabulaireError(
            f"{attribut.libelle} : {nombre:g} {attribut.unite} est hors du "
            f"vraisemblable (entre {attribut.minimum:g} et {attribut.maximum:g} "
            f"{attribut.unite})."
        )
    if attribut.maximum is not None and nombre > attribut.maximum:
        raise ValeurHorsVocabulaireError(
            f"{attribut.libelle} : {nombre:g} {attribut.unite} est hors du "
            f"vraisemblable (entre {attribut.minimum:g} et {attribut.maximum:g} "
            f"{attribut.unite})."
        )
    return nombre


def formater_valeur(cle: str, valeur: Any) -> str:
    """[CA4] Rend une valeur lisible, ou dit qu'elle n'est pas renseignée."""
    if valeur is None:
        return NON_RENSEIGNE
    attribut = ATTRIBUTS_PAR_CLE[cle]
    if attribut.est_qualitatif:
        return str(valeur)
    return f"{float(valeur):g} {attribut.unite}".strip()


def resoudre_cle(nom: str) -> str:
    """Résout un nom d'attribut saisi au bot vers sa clé canonique.

    Lève `KeyError` si le nom ne désigne aucun attribut — le bot en fait un
    message d'usage, jamais une écriture au hasard."""
    cle = ALIAS_ATTRIBUTS.get(_cle_comparaison(nom).replace(" ", "_"))
    if cle is None:
        raise KeyError(nom)
    return cle


def dans_perimetre_initial(culture: str) -> bool:
    """[CA7] La culture fait-elle partie des dix du périmètre de pré-remplissage ?"""
    cible = normaliser_culture(culture)
    return any(cible == normaliser_culture(c) for c in CULTURES_PERIMETRE_INITIAL)


def fiches_de_culture(db: Session, culture: str) -> list[CultureConfig]:
    """Toutes les fiches `culture_config` portant ce nom de culture (CA6 d'US-067).

    Globales comme personnalisées : un attribut agronomique est un fait, jamais
    une préférence de jardinier — corriger une seule fiche laisserait deux
    potagers avec deux vérités."""
    cible = normaliser_culture(culture)
    return [c for c in db.query(CultureConfig).all() if normaliser_culture(c.nom) == cible]


def lire_attributs(db: Session, culture: str) -> list[AttributLu]:
    """
    [CA4] Les quatre attributs d'une culture, **sans aucun appel au modèle**.

    Lecture pure : une lecture de colonnes et de leur origine, rien d'autre.
    C'est ce que la fiche courte d'US-164 restituera au bot en zéro jeton.

    Un attribut absent est retourné avec `valeur=None` et l'affichage
    « non renseigné » — il n'est ni omis de la liste, ni deviné : le jardinier
    doit voir que l'application ne sait pas.

    Lève `LookupError` si aucune fiche n'existe pour cette culture.
    """
    fiches = fiches_de_culture(db, culture)
    if not fiches:
        raise LookupError(culture)

    # Une culture peut porter plusieurs fiches (globale + personnalisée) : la
    # première qui renseigne l'attribut le donne, même stratégie que le rapport
    # de couverture — une fiche vide ne masque pas une fiche remplie.
    lus: list[AttributLu] = []
    for attribut in ATTRIBUTS:
        valeur, source_id = None, None
        for fiche in fiches:
            candidate = getattr(fiche, attribut.colonne)
            if candidate is not None:
                valeur = candidate
                source_id = getattr(fiche, attribut.colonne_source)
                break
        source = None
        if source_id is not None:
            source = (
                db.query(ReferentielSource)
                .filter(ReferentielSource.id == source_id)
                .first()
            )
        lus.append(AttributLu(
            cle=attribut.cle,
            libelle=attribut.libelle,
            valeur=valeur,
            affichage=formater_valeur(attribut.cle, valeur),
            source_code=source.code if source is not None else None,
            attribution=source.attribution if source is not None else None,
        ))
    return lus


def corriger_attribut(
    db: Session, culture: str, cle: str, valeur: Any
) -> tuple[list[CultureConfig], str, str]:
    """
    [CA5, CA6] Corrige un attribut depuis le bot — sans livraison ni intervention
    en base, exactement comme la famille botanique (US-067 / CA4).

    Écrit l'origine `saisie_manuelle` sur le **seul attribut corrigé** : l'import
    du référentiel la relira et conservera la valeur au prochain rejeu (CA6),
    sans pour autant se voir interdire de rafraîchir les trois autres.

    Lève `LookupError` si la culture n'a aucune fiche `culture_config` — elle
    doit avoir été dictée au moins une fois, `type_organe_recolte` étant NOT NULL.
    Lève `ValeurHorsVocabulaireError` **avant toute écriture** si la valeur est
    hors vocabulaire (CA2) : l'attribut conserve alors sa valeur précédente.

    Retourne (fiches modifiées, affichage avant, affichage après).
    """
    attribut = ATTRIBUTS_PAR_CLE.get(cle)
    if attribut is None:
        raise KeyError(cle)

    # [CA2] La validation précède la résolution de la culture comme l'écriture :
    # une valeur refusée ne doit toucher à rien.
    canonique = normaliser_valeur(cle, valeur)

    fiches = fiches_de_culture(db, culture)
    if not fiches:
        raise LookupError(culture)

    avant = formater_valeur(cle, getattr(fiches[0], attribut.colonne))
    origine = svc_sources.garantir_source(db, svc_sources.SOURCE_SAISIE_MANUELLE).id
    for fiche in fiches:
        setattr(fiche, attribut.colonne, canonique)
        # Effacer un attribut efface aussi son origine : il n'existe pas de
        # valeur sans source, mais pas davantage de source sans valeur.
        setattr(fiche, attribut.colonne_source, origine if canonique is not None else None)
    db.commit()

    apres = formater_valeur(cle, canonique)
    log.info(
        "[US-161] Attribut corrigé : '%s'.%s : %s → %s (%s fiche(s), origine saisie_manuelle)",
        culture, cle, avant, apres, len(fiches),
    )
    return fiches, avant, apres
