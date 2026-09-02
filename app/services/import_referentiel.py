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
from app.services import referentiel_sources as svc_sources
from app.services.familles import normaliser_famille
from database.models import CultureConfig, FamilleBotanique, ReferentielSource
from utils.culture_resolve import normaliser_culture

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

    @property
    def total_ecritures(self) -> int:
        return (
            len(self.familles_creees)
            + len(self.familles_enrichies)
            + len(self.cultures_rattachees)
            + len(self.attributs_ecrits)
            + len(self.associations_creees)
            + len(self.associations_ecrites)
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
        "périmètre, %s valeur(s) refusée(s), %s valeur(s) humaine(s) préservée(s)",
        code, len(resultat.familles_creees), len(resultat.familles_enrichies),
        len(resultat.cultures_rattachees), len(resultat.attributs_ecrits),
        len(resultat.associations_creees) + len(resultat.associations_ecrites),
        len(resultat.cultures_ignorees) + len(resultat.associations_ignorees),
        len(resultat.cultures_hors_perimetre),
        len(resultat.attributs_refuses) + len(resultat.associations_refusees),
        len(resultat.familles_preservees) + len(resultat.cultures_preservees)
        + len(resultat.attributs_preserves) + len(resultat.associations_preservees),
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
    )
    lignes.append(
        f"  Valeurs préservées   : {len(preservees)} — {', '.join(preservees) or '—'} "
        "(déjà renseignées par une autre origine)"
    )
    return "\n".join(lignes)
