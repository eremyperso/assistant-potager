"""
app/services/import_referentiel.py — Import du référentiel structuré [US-166]
------------------------------------------------------------------------------
Le chemin **unique** par lequel de la connaissance structurée — attributs,
identités, relations — entre dans les tables du référentiel. Le CLI
`tools/importer_referentiel.py` n'est qu'une façade : toute la logique est ici,
testable sans fichier ni terminal.

Frontière avec US-098, à ne pas franchir
----------------------------------------
US-098 ingère du **narratif** dans les tables de connaissance et le rend
cherchable. Ce module importe du **structuré** — colonnes et arêtes — dans les
tables du référentiel. Deux natures de donnée, deux destinations, un seul
principe commun de traçabilité. Aucun outil n'est réécrit en double.

Les quatre invariants de l'import
---------------------------------
1. **Hors ligne (CA8).** Ce module lit un fichier local et écrit en base. Il
   n'importe volontairement ni `requests` ni aucun client HTTP : la récupération
   et le versionnement des données sources sont une opération d'administration
   séparée, jamais un aller-retour réseau pendant qu'un jardinier attend.
2. **Refus à la porte (CA6).** La licence déclarée par le manifeste est
   contrôlée **avant** toute écriture. Hors socle ou non établie : rien n'est
   créé, pas même la source au registre.
3. **Rejouable sans écraser l'humain (CA5).** Les fichiers E-Phy sont mis à jour
   chaque semaine — rejouer doit être banal. L'import n'écrit une valeur que si
   elle est absente, ou s'il l'a lui-même écrite lors d'un passage précédent
   (voir `_peut_ecrire`). Une correction du jardinier est conservée et comptée.
4. **Aucune culture créée (CA7).** L'import enrichit `culture_config`, il ne
   l'alimente jamais. 14 des 54 configurations mesurées le 25/08/2026 ne portent
   déjà aucun événement ; pré-semer un catalogue peuplerait les écrans du
   jardinier de cultures fantômes.

Format du manifeste
-------------------
Un JSON versionné dans `data/referentiel/`, qui porte **avec les données** la
source dont elles viennent — c'est ce qui rend le refus de licence possible sans
convention implicite ni confiance dans le nom du fichier ::

    {
      "source": {"code": …, "libelle": …, "licence": …, "attribution": …,
                 "url": …, "partageable": true},
      "extrait_le": "2026-09-01",
      "familles": [{"nom": …, "nom_scientifique": …, "delai_retour_annees": …}],
      "cultures_familles": [{"culture": "tomate", "famille": "Solanacée"}],
      "cultures_attributs": [{"culture": "carotte", "exposition": "plein soleil",
                              "besoin_eau": "moyen", "profondeur_semis_cm": 1,
                              "rusticite_min_c": -5}],
      "cultures_associations": [{"culture": "tomate", "compagnon": "basilic",
                                 "nature": "favorable", "motif": "répulsif contre pucerons",
                                 "niveau_preuve": "traditionnel"}]
    }

Les blocs de données sont tous facultatifs : une source qui n'apporte que des
familles, que des rattachements ou que des attributs est un manifeste valide.
`ephy_anses` s'enfichera par un bloc supplémentaire quand US-162 aura créé sa
destination — sans second mécanisme d'ingestion.

Le bloc `cultures_associations` [US-163]
-----------------------------------------
`compagnon` est un nom de culture OU de famille botanique — jamais les deux
champs séparés : `app.services.associations._resoudre_cote` essaie une culture
d'abord, une famille ensuite, exactement comme une saisie `/association saisir`
au bot. Ni `culture` ni `compagnon` ne sont jamais créés à la volée (même
invariant que CA7 d'US-161) : l'un des deux absent du référentiel compte la
ligne en `associations_ignorees`, elle n'est pas fabriquée.

La règle de non-écrasement (CA5) porte sur la LIGNE entière, pas sur un champ :
une association déjà saisie par le jardinier (`saisie_manuelle`) n'est jamais
réécrite par un rejeu d'import, quelle que soit la source qui rejoue.

Les blocs `bioagresseurs` et `cultures_bioagresseurs` [US-162]
---------------------------------------------------------------
Deux blocs, parce que ce sont deux natures : une **identité** (`bioagresseurs`)
et une **arête** (`cultures_bioagresseurs`). Les identités s'importent d'abord —
un rattachement dont le bioagresseur n'a pas encore d'identité est compté ignoré,
jamais fabriqué (même invariant que CA7 d'US-161 sur les cultures).

    "bioagresseurs": [{"nom_commun_fr": "mildiou de la tomate",
                       "nom_scientifique": "Phytophthora infestans",
                       "categorie": "champignon", "code_eppo": "PHYTIN"}],
    "cultures_bioagresseurs": [{"culture": "tomate",
                                "bioagresseur": "mildiou de la tomate",
                                "frequence": "courant",
                                "periode_risque": "juin-septembre"}]

Un import n'écrit QUE du partagé (`potager_id` NULL) : c'est la définition même
de la connaissance importée, et le CA3 interdit qu'un ajout local soit promu —
la réciproque vaut, un import ne descend jamais dans le périmètre d'un potager.

**[CA9] Le rapprochement par nom vernaculaire ne s'applique pas seul.** La
résolution de la culture d'un rattachement est EXACTE (nom normalisé) par
défaut. Quand seul un rapprochement approché existe — `laitue` pour `salade`,
`haricot` pour `haricot grimpant`, deux cas réellement présents en base — la
ligne n'est PAS écrite : elle est comptée `appariements_a_revoir`, avec la
culture qu'elle viserait. Elle ne s'écrit qu'une fois relue par un humain, qui
le déclare dans le manifeste :

    {"culture": "salade", "bioagresseur": "limace", "frequence": "courant",
     "revue_humaine": true}

Quand aucune règle textuelle ne peut rapprocher les deux libellés — `laitue` et
`salade` sont des synonymes, pas des variantes d'écriture — la correspondance se
DÉCLARE, et c'est la table de correspondance manuelle que le CA8 désigne comme
mode de repli :

    {"culture": "laitue", "culture_en_base": "salade", "bioagresseur": "limace",
     "frequence": "courant", "revue_humaine": true}

Déclarée ou déduite, elle reste un rapprochement par nom vernaculaire : sans
`revue_humaine`, elle est comptée `appariements_a_revoir` et n'écrit rien.

C'est un drapeau porté par le FICHIER versionné — donc revu en diff git — et non
un seuil de similarité qui déciderait tout seul. Les cucurbitacées, réparties
sur dix libellés distincts, sont la raison pour laquelle ce garde-fou n'est pas
théorique.

**[CA8] Le taux d'appariement est un livrable, pas un journal.** L'import mesure
et publie la part des libellés de culture du manifeste qui retrouvent une
culture réellement présente en base. Sous `SEUIL_APPARIEMENT` (~70 %), l'import
automatique ne vaut plus la saisie directe sur les dix cultures du périmètre :
c'est cette mesure, et non une intention, qui tranche.

Le bloc `cultures_attributs` [US-161]
-------------------------------------
C'est le **seul** chemin de pré-remplissage des attributs agronomiques : « aucun
second mécanisme », comme le pose US-140. Trois règles s'y ajoutent aux quatre
invariants ci-dessus :

- **Périmètre fermé (US-161 / CA7).** Seules les dix cultures du périmètre
  initial (`attributs_culture.CULTURES_PERIMETRE_INITIAL`) sont pré-remplies.
  Toute autre culture du fichier est comptée `cultures_hors_perimetre` et
  ignorée — peupler les écrans de cultures jamais cultivées est un risque
  constaté, pas théorique.
- **Vocabulaire fermé (US-161 / CA2).** Chaque valeur passe par
  `attributs_culture.normaliser_valeur`, exactement comme une saisie au bot. Une
  valeur refusée est journalisée, comptée `attributs_refuses`, et **n'empêche
  pas** les autres attributs de la même culture d'être écrits : un fichier
  source partiellement fautif enrichit ce qu'il peut.
- **Origine par attribut (US-161 / CA3, CA6).** La règle de non-écrasement
  s'applique attribut par attribut et non ligne par ligne : une profondeur
  corrigée au bot survit au rejeu sans geler l'exposition, que l'import doit
  continuer de rafraîchir.

⚠️ Aucune valeur agronomique n'est livrée par US-161, et c'est délibéré : le
CA10 interdit qu'un chiffre soit produit par un modèle de langage. Profondeurs
de semis et rusticités viennent d'une extraction sourcée du socle de licences
(CA6 d'US-166), de la saisie du jardinier au bot, ou du manifeste de rédaction
interne ci-dessous — le mécanisme les attend, il ne les invente pas.

Le manifeste de rédaction interne
---------------------------------
`data/referentiel/attributs_redaction_interne.json` est le gabarit versionné que
le jardinier remplit lui-même. Il déclare `"code": "redaction_interne"` — une
origine que `SOURCES_SOCLE` marque non importée — et échappe donc au contrôle de
licence, qui n'a de sens que pour du contenu tiers. Sa fiche de registre reste
celle du socle : le fichier ne peut pas se donner une licence ni une attribution
de son choix.

Trois propriétés en découlent, et ce sont elles qui justifient le fichier plutôt
que quarante commandes au bot :
- **Versionné** — le diff git est la revue de ce qui change, et les valeurs
  survivent à un `rollback_v39.sql` qui viderait les colonnes.
- **Rejouable** — l'import se relance à l'identique après une reprise de base.
- **Dominé par le terrain** — une correction au bot porte l'origine
  `saisie_manuelle` et survit à tout rejeu du fichier (CA6).

Une valeur laissée à `null` n'écrit rien : le gabarit livré vide est inoffensif.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.services import associations as svc_associations
from app.services import attributs_culture as svc_attributs
from app.services import bioagresseurs as svc_bioagresseurs
from app.services import referentiel_sources as svc_sources
from app.services.familles import normaliser_famille
from app.services.rapport_couverture import SEUIL_APPARIEMENT
from database.models import CultureConfig, FamilleBotanique, ReferentielSource
from utils.culture_resolve import normaliser_culture
from utils.parcelles import levenshtein_distance

#: [US-162 / CA9] Au-delà, deux libellés ne sont plus « proches » — même valeur
#: que `utils.culture_resolve` et `rapport_couverture`, pour que l'import
#: signale exactement ce que la résolution de culture rapprocherait déjà.
_LEVENSHTEIN_MAX = 2

log = logging.getLogger("potager")


class ManifesteInvalideError(Exception):
    """Manifeste illisible ou mal formé — défaut de l'appelant, pas un aléa."""


@dataclass
class ResultatImport:
    """Ce qu'un import a réellement fait — la matière du compte rendu console."""

    source_code: str = ""
    dry_run: bool = False
    familles_creees: list[str] = field(default_factory=list)
    familles_enrichies: list[str] = field(default_factory=list)
    familles_preservees: list[str] = field(default_factory=list)
    cultures_rattachees: list[str] = field(default_factory=list)
    cultures_preservees: list[str] = field(default_factory=list)
    #: [CA7] Cultures du fichier source absentes de `culture_config` — ignorées,
    #: jamais créées. C'est un compteur attendu, pas une anomalie.
    cultures_ignorees: list[str] = field(default_factory=list)

    # ── [US-161] Attributs agronomiques de conduite ───────────────────────────
    #: Couples « culture.attribut » réellement écrits.
    attributs_ecrits: list[str] = field(default_factory=list)
    #: [US-161 / CA6] Attributs conservés parce qu'ils viennent d'une autre
    #: origine — la saisie du jardinier au premier chef.
    attributs_preserves: list[str] = field(default_factory=list)
    #: [US-161 / CA2] Valeurs hors vocabulaire fermé, refusées à l'écriture.
    attributs_refuses: list[str] = field(default_factory=list)
    #: [US-161 / CA7] Cultures du fichier hors des dix du périmètre initial.
    cultures_hors_perimetre: list[str] = field(default_factory=list)

    # ── [US-163] Associations de cultures ──────────────────────────────────────
    associations_creees: list[str] = field(default_factory=list)
    #: Ligne déjà de cette origine (rejeu), valeur mise à jour.
    associations_ecrites: list[str] = field(default_factory=list)
    #: [CA10] Ligne portant une AUTRE origine (le plus souvent `saisie_manuelle`)
    #: — jamais écrasée par un import, quel qu'il soit.
    associations_preservees: list[str] = field(default_factory=list)
    #: [US-161/CA7, même invariant] Un côté ne désigne ni une culture ni une
    #: famille connue — jamais créée à la volée.
    associations_ignorees: list[str] = field(default_factory=list)
    #: Nature/niveau de preuve/motif hors vocabulaire fermé (CA1, CA2).
    associations_refusees: list[str] = field(default_factory=list)

    # ── [US-162] Bioagresseurs : identités puis arêtes ────────────────────────
    bioagresseurs_crees: list[str] = field(default_factory=list)
    bioagresseurs_ecrits: list[str] = field(default_factory=list)
    #: [CA4] Identité déjà portée par une AUTRE origine — jamais écrasée.
    bioagresseurs_preserves: list[str] = field(default_factory=list)
    #: [CA1] Catégorie hors vocabulaire fermé, ou nom vide.
    bioagresseurs_refuses: list[str] = field(default_factory=list)

    rattachements_crees: list[str] = field(default_factory=list)
    rattachements_ecrits: list[str] = field(default_factory=list)
    rattachements_preserves: list[str] = field(default_factory=list)
    #: Culture ou bioagresseur absent du référentiel — jamais créé à la volée.
    rattachements_ignores: list[str] = field(default_factory=list)
    #: [CA2] Fréquence hors vocabulaire fermé.
    rattachements_refuses: list[str] = field(default_factory=list)
    #: [CA9] Lignes dont la culture ne se rapproche que par nom vernaculaire —
    #: NON écrites, en attente de revue humaine (`"revue_humaine": true`).
    appariements_a_revoir: list[str] = field(default_factory=list)

    # ── [US-162 / CA8] Mesure d'appariement — un livrable, pas un journal ─────
    #: Libellés de culture DISTINCTS portés par le bloc `cultures_bioagresseurs`.
    appariement_libelles: list[str] = field(default_factory=list)
    #: Ceux qui retrouvent une culture en base par nom exact (normalisé).
    appariement_exacts: list[str] = field(default_factory=list)
    #: Ceux qui ne s'y retrouvent que par rapprochement approché (CA9).
    appariement_approches: list[str] = field(default_factory=list)

    @property
    def appariement_non_apparies(self) -> list[str]:
        """Libellés de la source qui ne désignent aucune culture connue."""
        apparies = set(self.appariement_exacts) | set(self.appariement_approches)
        return [libelle for libelle in self.appariement_libelles if libelle not in apparies]

    @property
    def taux_appariement(self) -> Optional[float]:
        """
        [CA8] Part des libellés de la source qui retrouvent une culture en base.

        `None` — et non `0.0` — quand le manifeste ne porte aucun rattachement :
        ne rien mesurer et mesurer zéro sont deux choses différentes, et le
        second déclencherait à tort le verdict « sous le seuil ».
        """
        if not self.appariement_libelles:
            return None
        apparies = len(self.appariement_exacts) + len(self.appariement_approches)
        return apparies / len(self.appariement_libelles)

    @property
    def appariement_suffisant(self) -> Optional[bool]:
        """[CA8] Verdict : l'import automatique vaut-il encore la saisie directe ?"""
        taux = self.taux_appariement
        return None if taux is None else taux >= SEUIL_APPARIEMENT

    @property
    def total_ecritures(self) -> int:
        return (
            len(self.familles_creees)
            + len(self.familles_enrichies)
            + len(self.cultures_rattachees)
            + len(self.attributs_ecrits)
            + len(self.associations_creees)
            + len(self.associations_ecrites)
            + len(self.bioagresseurs_crees)
            + len(self.bioagresseurs_ecrits)
            + len(self.rattachements_crees)
            + len(self.rattachements_ecrits)
        )


def charger_manifeste(chemin: "str | Path") -> dict[str, Any]:
    """
    Lit et valide la structure d'un manifeste d'import.

    Ne contrôle PAS la licence ici : c'est `importer` qui la refuse, pour que le
    refus ait lieu au même endroit que les écritures qu'il empêche.
    """
    fichier = Path(chemin)
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
    except OSError as err:
        raise ManifesteInvalideError(f"Impossible de lire {fichier} : {err}") from err
    except json.JSONDecodeError as err:
        raise ManifesteInvalideError(f"{fichier} : JSON illisible — {err}") from err

    source = contenu.get("source")
    if not isinstance(source, dict) or not source.get("code"):
        raise ManifesteInvalideError(
            f"{fichier} : bloc « source » absent ou sans « code ». Un jeu de données "
            "qui ne déclare pas sa source ne peut pas être tracé, donc pas importé."
        )
    return contenu


def _peut_ecrire(
    valeur_actuelle: Any, source_ligne_id: Optional[int], source_import_id: Optional[int]
) -> bool:
    """
    [CA5] Règle de non-écrasement, appliquée champ par champ.

    L'import écrit si — et seulement si :
    - la valeur est actuellement absente : il **enrichit** un trou, ce qui est
      exactement son rôle ; ou
    - la ligne porte déjà l'origine de la source en cours d'import : il réécrit
      sa propre donnée, ce qui est le sens même d'un rejeu hebdomadaire.

    Toute valeur déjà renseignée par une autre origine est conservée — la saisie
    du jardinier au premier chef, mais aussi la rédaction interne. Le rejeu est
    ainsi banal sans jamais être destructeur.
    """
    if valeur_actuelle is None:
        return True
    return source_ligne_id is not None and source_ligne_id == source_import_id


def _importer_familles(
    db: Session, familles: list[dict], source: Optional[ReferentielSource], resultat: ResultatImport
) -> None:
    """Crée ou enrichit `familles_botaniques`, sans jamais écraser l'humain (CA5)."""
    source_id = source.id if source is not None else None

    for entree in familles:
        nom = (entree.get("nom") or "").strip()
        if not nom:
            continue
        normalise = normaliser_famille(nom)
        famille = (
            db.query(FamilleBotanique)
            .filter(FamilleBotanique.nom_normalise == normalise)
            .first()
        )

        if famille is None:
            famille = FamilleBotanique(
                nom=nom,
                nom_normalise=normalise,
                nom_scientifique=entree.get("nom_scientifique"),
                delai_retour_annees=entree.get("delai_retour_annees"),
                source_id=source_id,
            )
            db.add(famille)
            resultat.familles_creees.append(nom)
            continue

        modifiee = False
        preservee = False
        for champ in ("nom_scientifique", "delai_retour_annees"):
            proposee = entree.get(champ)
            if proposee is None:
                continue
            if _peut_ecrire(getattr(famille, champ), famille.source_id, source_id):
                if getattr(famille, champ) != proposee:
                    setattr(famille, champ, proposee)
                    modifiee = True
            else:
                preservee = True

        if modifiee:
            # L'origine suit la donnée : une ligne enrichie par l'import porte
            # désormais son code, sans quoi le rejeu suivant ne se reconnaîtrait
            # pas et refuserait de mettre à jour sa propre donnée.
            famille.source_id = source_id
            resultat.familles_enrichies.append(famille.nom)
        if preservee:
            resultat.familles_preservees.append(famille.nom)


def _importer_rattachements_cultures(
    db: Session, rattachements: list[dict], source: Optional[ReferentielSource], resultat: ResultatImport
) -> None:
    """
    [CA7] Rattache des cultures **existantes** à leur famille. Ne crée jamais de
    `culture_config` : une culture absente est comptée `cultures_ignorees` et
    l'import passe à la suivante.
    """
    source_id = source.id if source is not None else None

    familles_par_nom = {f.nom_normalise: f for f in db.query(FamilleBotanique).all()}
    configs_par_culture: dict[str, list[CultureConfig]] = {}
    for config in db.query(CultureConfig).all():
        configs_par_culture.setdefault(normaliser_culture(config.nom), []).append(config)

    for entree in rattachements:
        culture = (entree.get("culture") or "").strip()
        famille_nom = (entree.get("famille") or "").strip()
        if not culture or not famille_nom:
            continue

        famille = familles_par_nom.get(normaliser_famille(famille_nom))
        if famille is None:
            log.warning(
                "[import_referentiel] famille « %s » inconnue pour la culture « %s » — "
                "rattachement ignoré", famille_nom, culture,
            )
            continue

        fiches = configs_par_culture.get(normaliser_culture(culture))
        if not fiches:
            resultat.cultures_ignorees.append(culture)
            continue

        # La famille botanique est un fait, pas une préférence de jardinier
        # (US-067 / CA7) : toutes les fiches portant ce nom sont rattachées,
        # globales comme personnalisées, jamais une seule d'entre elles.
        rattachee, preservee = False, False
        for fiche in fiches:
            if _peut_ecrire(fiche.famille_id, fiche.famille_source_id, source_id):
                if fiche.famille_id != famille.id:
                    fiche.famille_id = famille.id
                    rattachee = True
                fiche.famille_source_id = source_id
            else:
                preservee = True
        if rattachee:
            resultat.cultures_rattachees.append(culture)
        if preservee:
            resultat.cultures_preservees.append(culture)


def _importer_attributs_cultures(
    db: Session, entrees: list[dict], source: Optional[ReferentielSource], resultat: ResultatImport
) -> None:
    """
    [US-161 / CA2, CA3, CA6, CA7] Pré-remplit les attributs agronomiques de
    conduite des cultures **existantes** du périmètre initial.

    Quatre refus, dans cet ordre :
    1. Culture hors des dix du périmètre initial → `cultures_hors_perimetre`.
    2. Culture absente de `culture_config` → `cultures_ignorees`, jamais créée.
    3. Valeur hors vocabulaire fermé → `attributs_refuses`, les autres attributs
       de la même culture restent écrits : un fichier source partiellement
       fautif enrichit ce qu'il peut.
    4. Valeur déjà renseignée par une autre origine → `attributs_preserves`.

    Le quatrième est celui qui fait tenir le CA6 : un référentiel importé décrit
    une moyenne nationale, le jardinier décrit son terrain. Quand les deux
    divergent, c'est le terrain qui a raison.
    """
    source_id = source.id if source is not None else None

    configs_par_culture: dict[str, list[CultureConfig]] = {}
    for config in db.query(CultureConfig).all():
        configs_par_culture.setdefault(normaliser_culture(config.nom), []).append(config)

    for entree in entrees:
        culture = (entree.get("culture") or "").strip()
        if not culture:
            continue

        if not svc_attributs.dans_perimetre_initial(culture):
            # [CA7] Pas une anomalie : le périmètre est fermé, et le fichier
            # source peut légitimement être plus large que lui.
            resultat.cultures_hors_perimetre.append(culture)
            continue

        fiches = configs_par_culture.get(normaliser_culture(culture))
        if not fiches:
            # [CA7] Aucune configuration de culture n'est créée ici, jamais.
            resultat.cultures_ignorees.append(culture)
            continue

        for attribut in svc_attributs.ATTRIBUTS:
            if attribut.cle not in entree:
                continue
            try:
                valeur = svc_attributs.normaliser_valeur(attribut.cle, entree[attribut.cle])
            except svc_attributs.ValeurHorsVocabulaireError as err:
                log.warning(
                    "[import_referentiel] %s.%s refusé : %s", culture, attribut.cle, err,
                )
                resultat.attributs_refuses.append(f"{culture}.{attribut.cle}")
                continue
            if valeur is None:
                continue

            # Les attributs agronomiques sont partagés (potager_id NULL sur les
            # 54 lignes mesurées) : toutes les fiches portant ce nom de culture
            # sont traitées, globales comme personnalisées.
            ecrit, preserve = False, False
            for fiche in fiches:
                if _peut_ecrire(
                    getattr(fiche, attribut.colonne),
                    getattr(fiche, attribut.colonne_source),
                    source_id,
                ):
                    if getattr(fiche, attribut.colonne) != valeur:
                        setattr(fiche, attribut.colonne, valeur)
                        ecrit = True
                    # [CA3] L'origine suit la donnée, même quand la valeur est
                    # inchangée : sans quoi le rejeu suivant ne reconnaîtrait
                    # pas sa propre écriture et refuserait de la mettre à jour.
                    setattr(fiche, attribut.colonne_source, source_id)
                else:
                    preserve = True
            if ecrit:
                resultat.attributs_ecrits.append(f"{culture}.{attribut.cle}")
            if preserve:
                resultat.attributs_preserves.append(f"{culture}.{attribut.cle}")


def _importer_associations_cultures(
    db: Session, entrees: list[dict], source: Optional[ReferentielSource], resultat: ResultatImport
) -> None:
    """
    [US-163] Importe des associations culture ↔ culture ou culture ↔ famille.

    Délègue la résolution, la validation et l'écriture à
    `app.services.associations.importer_association` — seul point d'écriture,
    partagé avec `/association saisir` au bot (« aucun second mécanisme »,
    US-140). Aucune culture ni famille n'est créée à la volée : un côté qui ne
    désigne rien de connu est compté `associations_ignorees`, jamais fabriqué.
    """
    if source is None:
        return
    for entree in entrees:
        culture = (entree.get("culture") or "").strip()
        compagnon = (entree.get("compagnon") or "").strip()
        if not culture or not compagnon:
            continue
        libelle = f"{culture} × {compagnon}"

        try:
            statut = svc_associations.importer_association(
                db, culture, compagnon,
                (entree.get("nature") or "").strip(),
                entree.get("motif") or "",
                (entree.get("niveau_preuve") or "").strip(),
                source,
            )
        except svc_associations.EntiteInconnueError:
            resultat.associations_ignorees.append(libelle)
            continue
        except svc_associations.ValeurAssociationInvalideError as err:
            log.warning("[import_referentiel] association %s refusée : %s", libelle, err)
            resultat.associations_refusees.append(libelle)
            continue

        if statut == svc_associations.IMPORT_CREEE:
            resultat.associations_creees.append(libelle)
        elif statut == svc_associations.IMPORT_ECRITE:
            resultat.associations_ecrites.append(libelle)
        elif statut == svc_associations.IMPORT_PRESERVEE:
            resultat.associations_preservees.append(libelle)
        # IMPORT_INCHANGEE : déjà conforme, rien de plus à compter.


def _importer_bioagresseurs(
    db: Session, entrees: list[dict], source: Optional[ReferentielSource], resultat: ResultatImport
) -> None:
    """
    [US-162 / CA1, CA4, CA5] Importe les IDENTITÉS de bioagresseurs — partagées,
    par définition (`potager_id` NULL, CA3).

    Délègue à `app.services.bioagresseurs.importer_bioagresseur`, seul point
    d'écriture, partagé avec la saisie au bot (« aucun second mécanisme »).
    """
    if source is None:
        return
    for entree in entrees:
        nom = (entree.get("nom_commun_fr") or "").strip()
        if not nom:
            continue
        try:
            statut = svc_bioagresseurs.importer_bioagresseur(
                db,
                nom_commun_fr=nom,
                categorie=(entree.get("categorie") or "").strip(),
                source=source,
                nom_scientifique=entree.get("nom_scientifique"),
                code_eppo=entree.get("code_eppo"),
            )
        except svc_bioagresseurs.ValeurBioagresseurInvalideError as err:
            log.warning("[import_referentiel] bioagresseur « %s » refusé : %s", nom, err)
            resultat.bioagresseurs_refuses.append(nom)
            continue

        if statut == svc_bioagresseurs.IMPORT_CREEE:
            resultat.bioagresseurs_crees.append(nom)
        elif statut == svc_bioagresseurs.IMPORT_ECRITE:
            resultat.bioagresseurs_ecrits.append(nom)
        elif statut == svc_bioagresseurs.IMPORT_PRESERVEE:
            resultat.bioagresseurs_preserves.append(nom)


def _apparier_culture(
    libelle: str, cultures_connues: dict[str, str]
) -> tuple[Optional[str], bool]:
    """
    [US-162 / CA8, CA9] Rapproche un libellé de culture de la source d'une
    culture réellement présente en base.

    Retourne `(nom de culture en base, exact)` — `(None, False)` si rien ne s'en
    approche. `exact=False` signale un rapprochement par **nom vernaculaire
    seul**, la clé la moins fiable des trois de la conception §7 : il est mesuré
    (CA8) mais jamais appliqué sans revue humaine (CA9).
    """
    cible = normaliser_culture(libelle)
    if cible in cultures_connues:
        return cultures_connues[cible], True
    if not cible:
        return None, False
    for connue_normalisee, nom in cultures_connues.items():
        if levenshtein_distance(cible, connue_normalisee) <= _LEVENSHTEIN_MAX:
            return nom, False
    # `haricot` / `haricot grimpant` : la distance de Levenshtein ne les
    # rapproche pas, l'inclusion oui — et c'est justement le cas que cite le
    # CA9. Rapprochement d'autant plus faible : jamais exact.
    for connue_normalisee, nom in cultures_connues.items():
        if cible and (cible in connue_normalisee or connue_normalisee in cible):
            return nom, False
    return None, False


def _importer_rattachements_bioagresseurs(
    db: Session, entrees: list[dict], source: Optional[ReferentielSource], resultat: ResultatImport
) -> None:
    """
    [US-162 / CA2, CA5, CA8, CA9] Importe les ARÊTES culture × bioagresseur, et
    publie au passage la mesure d'appariement qui décide du sort de l'import
    automatique.

    Trois refus, dans cet ordre :
    1. Libellé de culture ne désignant aucune culture connue → `rattachements_ignores`
       (jamais créée — CA7 d'US-161, même invariant).
    2. Rapprochement par nom vernaculaire seul, sans `"revue_humaine": true` →
       `appariements_a_revoir`, NON écrit (CA9).
    3. Fréquence hors vocabulaire fermé → `rattachements_refuses` (CA2).
    """
    if source is None:
        return

    cultures_connues: dict[str, str] = {}
    for config in db.query(CultureConfig).all():
        cultures_connues.setdefault(normaliser_culture(config.nom), config.nom)

    for entree in entrees:
        libelle_culture = (entree.get("culture") or "").strip()
        bioagresseur = (entree.get("bioagresseur") or "").strip()
        if not libelle_culture or not bioagresseur:
            continue

        # [CA9] `culture_en_base` est la table de correspondance MANUELLE que le
        # CA8 désigne comme mode de repli : le seul moyen d'apparier « laitue »
        # à « salade », que ni la distance d'édition ni l'inclusion ne
        # rapprochent — ce sont des synonymes, pas des variantes d'écriture.
        # Déclarée, elle reste un rapprochement par nom vernaculaire : elle
        # exige `revue_humaine` comme les autres.
        correspondance = (entree.get("culture_en_base") or "").strip()
        if correspondance:
            cible = normaliser_culture(correspondance)
            culture_base, exact = cultures_connues.get(cible), False
        else:
            culture_base, exact = _apparier_culture(libelle_culture, cultures_connues)
        # [CA8] La mesure porte sur les libellés DISTINCTS de la source, qu'ils
        # aboutissent ou non à une écriture : c'est la qualité de la source qui
        # est mesurée, pas le rendement de ce passage.
        if libelle_culture not in resultat.appariement_libelles:
            resultat.appariement_libelles.append(libelle_culture)
            if culture_base is not None and exact:
                resultat.appariement_exacts.append(libelle_culture)
            elif culture_base is not None:
                resultat.appariement_approches.append(libelle_culture)

        libelle = f"{libelle_culture} × {bioagresseur}"

        if culture_base is None:
            resultat.rattachements_ignores.append(libelle)
            continue

        if not exact and not bool(entree.get("revue_humaine")):
            # [CA9] Le rapprochement existe, il est plausible — et c'est
            # précisément pourquoi il ne s'applique pas tout seul.
            log.warning(
                "[import_referentiel] « %s » ne se rapproche de « %s » que par nom "
                "vernaculaire — rattachement en attente de revue humaine (US-162/CA9)",
                libelle_culture, culture_base,
            )
            resultat.appariements_a_revoir.append(f"{libelle} → {culture_base}")
            continue

        try:
            statut = svc_bioagresseurs.importer_rattachement(
                db,
                culture=culture_base,
                bioagresseur=bioagresseur,
                frequence=(entree.get("frequence") or "").strip(),
                source=source,
                periode_risque=entree.get("periode_risque"),
            )
        except (svc_bioagresseurs.CultureInconnueError,
                svc_bioagresseurs.BioagresseurInconnuError):
            resultat.rattachements_ignores.append(libelle)
            continue
        except svc_bioagresseurs.ValeurBioagresseurInvalideError as err:
            log.warning("[import_referentiel] rattachement %s refusé : %s", libelle, err)
            resultat.rattachements_refuses.append(libelle)
            continue

        if statut == svc_bioagresseurs.IMPORT_CREEE:
            resultat.rattachements_crees.append(libelle)
        elif statut == svc_bioagresseurs.IMPORT_ECRITE:
            resultat.rattachements_ecrits.append(libelle)
        elif statut == svc_bioagresseurs.IMPORT_PRESERVEE:
            resultat.rattachements_preserves.append(libelle)


def importer(db: Session, manifeste: dict[str, Any], dry_run: bool = False) -> ResultatImport:
    """
    [CA5-CA8] Importe un manifeste de référentiel structuré.

    Lève `LicenceHorsSocleError` **avant toute écriture** si la licence déclarée
    n'est pas celle d'une source du socle (CA6) : rien n'est créé, pas même la
    ligne du registre. C'est délibérément la première chose que fait la fonction.

    Seule exception, ajoutée par US-161 : un manifeste dont le `code` est celui
    d'une origine **non importée** du socle (`redaction_interne`) échappe au
    contrôle de licence, parce qu'il ne porte aucun contenu tiers. Sa fiche de
    registre reste celle du socle — le manifeste ne peut ni se donner une autre
    licence, ni une autre attribution.

    `dry_run=True` simule : rien n'est écrit ni commité, la source n'est même pas
    déclarée. Le résultat compte alors ce qui *serait* fait — une ligne comptée
    « créée » en simulation peut donc l'être à nouveau au passage réel.
    """
    bloc_source = manifeste.get("source") or {}
    code = (bloc_source.get("code") or "").strip()

    # [US-161] Une origine INTERNE du socle peut porter un manifeste : c'est le
    # seul chemin versionné pour des valeurs rédigées par le projet lui-même,
    # que le socle de licences d'import (CC0, Licence Ouverte) exclut par
    # construction puisqu'elles ne viennent d'aucune source tierce.
    #
    # La porte est volontairement étroite, et c'est ce qui l'empêche d'être une
    # porte dérobée à CA6 : seuls les codes que `SOURCES_SOCLE` déclare NON
    # importés y ont droit — une liste fermée, pas un drapeau que le manifeste
    # se donnerait à lui-même. Un fichier tiers ne peut donc pas se soustraire
    # au contrôle de licence en s'annonçant interne, et une origine interne ne
    # peut pas se redéfinir : sa licence, son attribution et son URL restent
    # celles du registre, jamais celles que le fichier voudrait s'attribuer.
    fiche_interne = next(
        (f for f in svc_sources.SOURCES_SOCLE
         if f["code"] == code and not f["importee"]),
        None,
    )

    # [CA6] Le refus a lieu ici, avant tout le reste.
    if fiche_interne is None:
        svc_sources.verifier_licence_importable(bloc_source.get("licence"))

    resultat = ResultatImport(source_code=code, dry_run=dry_run)

    if dry_run:
        source = svc_sources.get_source(db, code)
    elif fiche_interne is not None:
        source = svc_sources.garantir_source(db, code)
    else:
        source = svc_sources.enregistrer_source(
            db,
            code=code,
            libelle=bloc_source.get("libelle") or code,
            licence=bloc_source["licence"],
            attribution=bloc_source.get("attribution") or "",
            url=bloc_source.get("url"),
            partageable=bool(bloc_source.get("partageable", True)),
            importee=True,
        )

    _importer_familles(db, manifeste.get("familles") or [], source, resultat)
    db.flush()  # les familles créées doivent porter un id avant les rattachements
    _importer_rattachements_cultures(
        db, manifeste.get("cultures_familles") or [], source, resultat
    )
    _importer_attributs_cultures(
        db, manifeste.get("cultures_attributs") or [], source, resultat
    )
    _importer_associations_cultures(
        db, manifeste.get("cultures_associations") or [], source, resultat
    )
    # [US-162] Les identités AVANT les arêtes : un rattachement dont le
    # bioagresseur n'est pas encore déclaré serait compté ignoré à tort.
    _importer_bioagresseurs(db, manifeste.get("bioagresseurs") or [], source, resultat)
    db.flush()  # les identités créées doivent porter un id avant les arêtes
    _importer_rattachements_bioagresseurs(
        db, manifeste.get("cultures_bioagresseurs") or [], source, resultat
    )

    if dry_run:
        db.rollback()
        log.info("[import_referentiel] simulation « %s » — aucune écriture", code)
        return resultat

    db.commit()
    svc_sources.marquer_import(db, code)
    log.info(
        "[import_referentiel] « %s » : %s famille(s) créée(s), %s enrichie(s), "
        "%s culture(s) rattachée(s), %s attribut(s) écrit(s), %s association(s) "
        "créée(s)/écrite(s), %s ignorée(s) (aucune création, CA7), %s hors "
        "périmètre, %s valeur(s) refusée(s), %s valeur(s) humaine(s) préservée(s), "
        "%s bioagresseur(s) et %s arête(s) culture × bioagresseur écrit(e)s, "
        "%s appariement(s) en attente de revue humaine (US-162/CA9)",
        code, len(resultat.familles_creees), len(resultat.familles_enrichies),
        len(resultat.cultures_rattachees), len(resultat.attributs_ecrits),
        len(resultat.associations_creees) + len(resultat.associations_ecrites),
        len(resultat.cultures_ignorees) + len(resultat.associations_ignorees),
        len(resultat.cultures_hors_perimetre),
        len(resultat.attributs_refuses) + len(resultat.associations_refusees),
        len(resultat.familles_preservees) + len(resultat.cultures_preservees)
        + len(resultat.attributs_preserves) + len(resultat.associations_preservees)
        + len(resultat.bioagresseurs_preserves) + len(resultat.rattachements_preserves),
        len(resultat.bioagresseurs_crees) + len(resultat.bioagresseurs_ecrits),
        len(resultat.rattachements_crees) + len(resultat.rattachements_ecrits),
        len(resultat.appariements_a_revoir),
    )
    return resultat


def importer_fichier(db: Session, chemin: "str | Path", dry_run: bool = False) -> ResultatImport:
    """Charge un manifeste puis l'importe — la porte d'entrée du CLI."""
    return importer(db, charger_manifeste(chemin), dry_run=dry_run)


def formater_resultat(resultat: ResultatImport) -> str:
    """Compte rendu console d'un import."""
    entete = f"Import « {resultat.source_code} »" + (" — SIMULATION, rien n'a été écrit" if resultat.dry_run else "")
    lignes = ["", entete, "─" * len(entete)]
    lignes.append(f"  Familles créées      : {len(resultat.familles_creees)} — {', '.join(resultat.familles_creees) or '—'}")
    lignes.append(f"  Familles enrichies   : {len(resultat.familles_enrichies)} — {', '.join(resultat.familles_enrichies) or '—'}")
    lignes.append(f"  Cultures rattachées  : {len(resultat.cultures_rattachees)} — {', '.join(resultat.cultures_rattachees) or '—'}")
    lignes.append(
        f"  Cultures ignorées    : {len(resultat.cultures_ignorees)} — "
        f"{', '.join(resultat.cultures_ignorees) or '—'} (absentes de culture_config, jamais créées)"
    )
    lignes.append(
        f"  Attributs écrits     : {len(resultat.attributs_ecrits)} — "
        f"{', '.join(resultat.attributs_ecrits) or '—'}"
    )
    lignes.append(
        f"  Associations créées  : {len(resultat.associations_creees)} — "
        f"{', '.join(resultat.associations_creees) or '—'}"
    )
    lignes.append(
        f"  Associations écrites : {len(resultat.associations_ecrites)} — "
        f"{', '.join(resultat.associations_ecrites) or '—'} (rejeu, valeur modifiée)"
    )
    lignes.append(
        f"  Associations ignorées : {len(resultat.associations_ignorees)} — "
        f"{', '.join(resultat.associations_ignorees) or '—'} "
        "(culture ou famille absente du référentiel, jamais créée)"
    )
    lignes.append(
        f"  Hors périmètre       : {len(resultat.cultures_hors_perimetre)} — "
        f"{', '.join(resultat.cultures_hors_perimetre) or '—'} "
        "(hors des dix cultures du périmètre initial, US-161/CA7)"
    )
    refusees = resultat.attributs_refuses + resultat.associations_refusees
    lignes.append(
        f"  Valeurs refusées     : {len(refusees)} — "
        f"{', '.join(refusees) or '—'} (hors vocabulaire fermé, US-161/CA2, US-163/CA1-CA2)"
    )
    preservees = (
        resultat.familles_preservees + resultat.cultures_preservees
        + resultat.attributs_preserves + resultat.associations_preservees
        + resultat.bioagresseurs_preserves + resultat.rattachements_preserves
    )
    lignes.append(
        f"  Valeurs préservées   : {len(preservees)} — {', '.join(preservees) or '—'} "
        "(déjà renseignées par une autre origine)"
    )

    # ── [US-162] Bioagresseurs : identités, arêtes, et la mesure qui décide ───
    lignes.append("")
    lignes.append("  Bioagresseurs [US-162]")
    lignes.append(
        f"    Identités créées   : {len(resultat.bioagresseurs_crees)} — "
        f"{', '.join(resultat.bioagresseurs_crees) or '—'}"
    )
    lignes.append(
        f"    Identités écrites  : {len(resultat.bioagresseurs_ecrits)} — "
        f"{', '.join(resultat.bioagresseurs_ecrits) or '—'} (rejeu, valeur modifiée)"
    )
    lignes.append(
        f"    Arêtes créées      : {len(resultat.rattachements_crees)} — "
        f"{', '.join(resultat.rattachements_crees) or '—'}"
    )
    lignes.append(
        f"    Arêtes écrites     : {len(resultat.rattachements_ecrits)} — "
        f"{', '.join(resultat.rattachements_ecrits) or '—'} (rejeu, valeur modifiée)"
    )
    lignes.append(
        f"    Arêtes ignorées    : {len(resultat.rattachements_ignores)} — "
        f"{', '.join(resultat.rattachements_ignores) or '—'} "
        "(culture ou bioagresseur absent du référentiel, jamais créé)"
    )
    lignes.append(
        f"    Valeurs refusées   : "
        f"{len(resultat.bioagresseurs_refuses) + len(resultat.rattachements_refuses)} — "
        f"{', '.join(resultat.bioagresseurs_refuses + resultat.rattachements_refuses) or '—'} "
        "(catégorie ou fréquence hors vocabulaire fermé, CA1/CA2)"
    )
    lignes.append(
        f"    À REVOIR (CA9)     : {len(resultat.appariements_a_revoir)} — "
        f"{', '.join(resultat.appariements_a_revoir) or '—'}"
    )
    if resultat.appariements_a_revoir:
        lignes.append(
            "      ↳ rapprochement par nom vernaculaire seul : NON écrit. Relire, puis "
            'ajouter "revue_humaine": true à la ligne du manifeste pour l\'appliquer.'
        )

    # [CA8] La mesure d'appariement — le livrable qui décide si l'import
    # automatique est conservé ou remplacé par la correspondance manuelle.
    taux = resultat.taux_appariement
    lignes.append("")
    lignes.append("  Taux d'appariement des libellés de culture [US-162 / CA8]")
    if taux is None:
        lignes.append(
            "    Non mesurable : ce manifeste ne porte aucun rattachement culture × "
            "bioagresseur. Ne rien mesurer n'est pas mesurer zéro."
        )
    else:
        lignes.append(
            f"    {len(resultat.appariement_exacts) + len(resultat.appariement_approches)}"
            f"/{len(resultat.appariement_libelles)} libellés appariés — {taux:.0%} "
            f"(seuil de décision : {SEUIL_APPARIEMENT:.0%})"
        )
        lignes.append(
            f"      • exacts    : {len(resultat.appariement_exacts)} — "
            f"{', '.join(resultat.appariement_exacts) or '—'}"
        )
        lignes.append(
            f"      • approchés : {len(resultat.appariement_approches)} — "
            f"{', '.join(resultat.appariement_approches) or '—'} "
            "(nom vernaculaire seul, revue humaine requise — CA9)"
        )
        lignes.append(
            f"      • non appariés : {len(resultat.appariement_non_apparies)} — "
            f"{', '.join(resultat.appariement_non_apparies) or '—'}"
        )
        if resultat.appariement_suffisant:
            lignes.append(
                "    ✅ Au-dessus du seuil : l'import automatique garde son intérêt "
                "face à la saisie directe."
            )
        else:
            lignes.append(
                "    ⚠️ SOUS LE SEUIL : l'import automatique ne vaut plus la saisie "
                "directe. La table de correspondance manuelle sur les dix cultures du "
                "périmètre devient le mode nominal (US-162 / CA8)."
            )

    return "\n".join(lignes)
