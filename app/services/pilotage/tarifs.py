"""
app/services/pilotage/tarifs.py — Grille tarifaire des appels au modèle [US-309]
================================================================================
Chaque ligne de `conso_tokens` porte son coût estimé, **figé à l'écriture** d'après la
grille en vigueur ce jour-là (`data/tarifs/tarifs_llm.json`). Ce module lit et valide la
grille, et calcule le coût d'un appel. Il ne dépend ni de la base ni de la passerelle.

Règles (décisions D5 et D6 du cadrage de l'ÉPIC 18)
---------------------------------------------------
* La grille est lue **une fois, au démarrage**, jamais en ligne à l'appel. Une grille mal
  formée arrête le démarrage (`GrilleTarifaireInvalideError`), comme un nom de modèle
  invalide (US-308).
* Le coût est en **micro-euros entiers**. Le calcul est exact (`Fraction`, aucun flottant) ;
  l'arrondi, à l'entier le plus proche (demi vers le haut), est fait **une seule fois** sur le
  total de l'appel. Une devise autre que l'euro est convertie au taux fixe daté de la grille.
* Les jetons en cache sont comptés à leur tarif propre et **retirés** des jetons d'entrée au
  plein tarif. Sans tarif de cache publié, ils sont comptés au prix d'entrée : une borne haute,
  jamais un rabais inventé.
* Une ligne en échec qui n'a rien consommé coûte 0. Un modèle absent de la grille (ou dont
  l'unité diffère de celle de la ligne) donne un coût **nul (`None`)**, jamais un coût inventé ;
  la `tarif_version` est renseignée dans tous les cas.
* Le coût est celui du **tarif public**, même quand l'appel est servi par un palier gratuit.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import date
from fractions import Fraction
from typing import Iterable, Optional

log = logging.getLogger("potager")

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
CHEMIN_GRILLE = os.path.join(RACINE, "data", "tarifs", "tarifs_llm.json")

UNITE_JETON = "jeton"
UNITE_SECONDE = "seconde"
UNITE_CARACTERE = "caractere"
UNITES = frozenset({UNITE_JETON, UNITE_SECONDE, UNITE_CARACTERE})

DEVISE_REFERENCE = "EUR"
FOURNISSEUR_GROQ = "groq"
FOURNISSEUR_MISTRAL = "mistral"
PREFIXE_MISTRAL = "mistral"

ISSUE_OK = "ok"
MICRO = 1_000_000

#: Champs de prix admis par unité : (obligatoires, optionnels). Un prix de cache est facultatif,
#: et nul (`null`) quand le fournisseur ne le publie pas.
_CHAMPS_PAR_UNITE: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    UNITE_JETON:     (("prix_entree_par_million", "prix_sortie_par_million"), ("prix_cache_par_million",)),
    UNITE_SECONDE:   ((), ("prix_par_minute", "prix_par_heure")),
    UNITE_CARACTERE: (("prix_par_million_caracteres",), ()),
}


class GrilleTarifaireInvalideError(RuntimeError):
    """La grille tarifaire est mal formée : le démarrage s'arrête."""


@dataclass(frozen=True)
class TarifModele:
    """Le tarif public d'un modèle, dans la devise de la source."""

    fournisseur: str
    modele: str
    unite: str
    devise: str
    prix: dict[str, Fraction] = field(default_factory=dict)
    source: str = ""
    date_releve: str = ""

    def prix_de(self, champ: str) -> Optional[Fraction]:
        return self.prix.get(champ)


@dataclass(frozen=True)
class GrilleTarifaire:
    version: str
    palier_gratuit: str
    taux_pour_1_eur: dict[str, Fraction]   # devise → unités de cette devise pour 1 €
    modeles: dict[tuple[str, str], TarifModele]

    def tarif(self, fournisseur: str, modele: str) -> Optional[TarifModele]:
        return self.modeles.get((fournisseur, modele))


@dataclass(frozen=True)
class Cout:
    """Ce qui est écrit sur la ligne : le fournisseur, le coût (None = non chiffrable), la grille."""

    fournisseur: str
    cout_micro_eur: Optional[int]
    tarif_version: str


# ─────────────────────────────────────────────────────────────────────────────
# Lecture et validation
# ─────────────────────────────────────────────────────────────────────────────
def _decimal(chemin: str, valeur) -> Fraction:
    """Un prix ou un taux : une chaîne décimale positive ou nulle (jamais un flottant JSON)."""
    if not isinstance(valeur, str) or not re.fullmatch(r"\d+(\.\d+)?", valeur.strip()):
        raise GrilleTarifaireInvalideError(
            f"{chemin} : nombre décimal attendu, écrit entre guillemets (valeur lue : {valeur!r})")
    return Fraction(valeur.strip())


def _texte(chemin: str, valeur) -> str:
    if not isinstance(valeur, str) or not valeur.strip():
        raise GrilleTarifaireInvalideError(f"{chemin} : texte non vide attendu (valeur lue : {valeur!r})")
    return valeur.strip()


def _date(chemin: str, valeur) -> str:
    texte = _texte(chemin, valeur)
    try:
        date.fromisoformat(texte)
    except ValueError:
        raise GrilleTarifaireInvalideError(f"{chemin} : date AAAA-MM-JJ attendue (valeur lue : {texte!r})") from None
    return texte


def _source(chemin: str, valeur) -> str:
    texte = _texte(chemin, valeur)
    if not texte.startswith(("http://", "https://")):
        raise GrilleTarifaireInvalideError(f"{chemin} : adresse de la page source attendue (valeur lue : {texte!r})")
    return texte


def valider_grille(donnees: object) -> GrilleTarifaire:
    """Construit la grille ou lève `GrilleTarifaireInvalideError` en nommant l'endroit fautif."""
    if not isinstance(donnees, dict):
        raise GrilleTarifaireInvalideError("la grille doit être un objet JSON")
    version = _texte("version", donnees.get("version"))
    palier = _texte("palier_gratuit", donnees.get("palier_gratuit"))
    if donnees.get("devise_reference", DEVISE_REFERENCE) != DEVISE_REFERENCE:
        raise GrilleTarifaireInvalideError(f"devise_reference : « {DEVISE_REFERENCE} » attendu")

    taux: dict[str, Fraction] = {DEVISE_REFERENCE: Fraction(1)}
    for devise, bloc in (donnees.get("taux_change") or {}).items():
        if not isinstance(bloc, dict):
            raise GrilleTarifaireInvalideError(f"taux_change.{devise} : objet attendu")
        valeur = _decimal(f"taux_change.{devise}.pour_1_eur", bloc.get("pour_1_eur"))
        if valeur <= 0:
            raise GrilleTarifaireInvalideError(f"taux_change.{devise}.pour_1_eur : strictement positif attendu")
        _date(f"taux_change.{devise}.date_releve", bloc.get("date_releve"))
        _source(f"taux_change.{devise}.source", bloc.get("source"))
        taux[devise] = valeur

    fournisseurs = donnees.get("fournisseurs")
    if not isinstance(fournisseurs, dict) or not fournisseurs:
        raise GrilleTarifaireInvalideError("fournisseurs : au moins un fournisseur attendu")
    modeles: dict[tuple[str, str], TarifModele] = {}
    for fournisseur, bloc in fournisseurs.items():
        entrees = (bloc or {}).get("modeles") if isinstance(bloc, dict) else None
        if not isinstance(entrees, dict) or not entrees:
            raise GrilleTarifaireInvalideError(f"fournisseurs.{fournisseur}.modeles : au moins un modèle attendu")
        for modele, entree in entrees.items():
            chemin = f"fournisseurs.{fournisseur}.modeles.{modele}"
            if not isinstance(entree, dict):
                raise GrilleTarifaireInvalideError(f"{chemin} : objet attendu")
            unite = entree.get("unite")
            if unite not in UNITES:
                raise GrilleTarifaireInvalideError(f"{chemin}.unite : parmi {sorted(UNITES)} (valeur lue : {unite!r})")
            devise = entree.get("devise")
            if devise not in taux:
                raise GrilleTarifaireInvalideError(
                    f"{chemin}.devise : « {devise} » sans taux de change daté dans taux_change")
            obligatoires, facultatifs = _CHAMPS_PAR_UNITE[unite]
            prix: dict[str, Fraction] = {}
            for champ in obligatoires:
                prix[champ] = _decimal(f"{chemin}.{champ}", entree.get(champ))
            for champ in facultatifs:
                if entree.get(champ) is not None:   # `null` = non publié
                    prix[champ] = _decimal(f"{chemin}.{champ}", entree[champ])
            if unite == UNITE_SECONDE and len({"prix_par_minute", "prix_par_heure"} & set(prix)) != 1:
                raise GrilleTarifaireInvalideError(f"{chemin} : exactement un de prix_par_minute / prix_par_heure")
            modeles[(fournisseur, modele)] = TarifModele(
                fournisseur=fournisseur, modele=modele, unite=unite, devise=devise, prix=prix,
                source=_source(f"{chemin}.source", entree.get("source")),
                date_releve=_date(f"{chemin}.date_releve", entree.get("date_releve")),
            )
    return GrilleTarifaire(version=version, palier_gratuit=palier, taux_pour_1_eur=taux, modeles=modeles)


def charger_grille(chemin: Optional[str] = None) -> GrilleTarifaire:
    """Lit la grille du dépôt (ou `chemin`) et la valide. Fichier absent, JSON illisible ou
    grille mal formée : `GrilleTarifaireInvalideError`."""
    chemin = chemin or CHEMIN_GRILLE
    try:
        with open(chemin, encoding="utf-8") as f:
            donnees = json.load(f)
    except OSError as e:
        raise GrilleTarifaireInvalideError(f"grille tarifaire illisible ({chemin}) : {e.strerror or e}") from e
    except json.JSONDecodeError as e:
        raise GrilleTarifaireInvalideError(f"grille tarifaire ({chemin}) : JSON invalide, {e}") from e
    return valider_grille(donnees)


#: La grille en vigueur, lue UNE fois au chargement du module (donc au démarrage du bot et de l'API).
GRILLE: GrilleTarifaire = charger_grille()
log.info("💶 TARIFS │ grille %s chargée │ %d modèles", GRILLE.version, len(GRILLE.modeles))


# ─────────────────────────────────────────────────────────────────────────────
# Calcul
# ─────────────────────────────────────────────────────────────────────────────
def fournisseur_et_modele(modele: str, compatibles: Iterable[str] = ()) -> tuple[str, str]:
    """(fournisseur, identifiant du modèle dans la grille) d'après le modèle journalisé.

    Même règle que la passerelle : `mistral/…` → Mistral, `<nom>/…` d'un fournisseur compatible
    déclaré → ce fournisseur (préfixe retiré) ; tout le reste est servi par Groq, identifiant entier."""
    prefixe, separateur, reste = (modele or "").partition("/")
    if separateur and prefixe == PREFIXE_MISTRAL:
        return FOURNISSEUR_MISTRAL, reste
    if separateur and prefixe in set(compatibles):
        return prefixe, reste
    return FOURNISSEUR_GROQ, modele or ""


def _arrondir(valeur: Fraction) -> int:
    """À l'entier le plus proche, le demi vers le haut (exact, sans flottant)."""
    return int((valeur + Fraction(1, 2)).__floor__())


def _cout_micro_eur(tarif: TarifModele, grille: GrilleTarifaire, quantite_in: int, quantite_out: int,
                    quantite_cache: int) -> int:
    """Coût exact arrondi une fois. Pour une devise D et un prix p (D par million), un volume v coûte
    v × p / taux micro-euros (taux = D pour 1 €)."""
    taux = grille.taux_pour_1_eur[tarif.devise]
    if tarif.unite == UNITE_JETON:
        cache = min(max(quantite_cache, 0), max(quantite_in, 0))     # le cache est un sous-ensemble de l'entrée
        plein = max(quantite_in, 0) - cache
        p_entree = tarif.prix["prix_entree_par_million"]
        p_cache = tarif.prix_de("prix_cache_par_million")
        if p_cache is None:
            p_cache = p_entree            # cache non publié : borne haute, au prix d'entrée
        total = plein * p_entree + cache * p_cache + max(quantite_out, 0) * tarif.prix["prix_sortie_par_million"]
        return _arrondir(Fraction(total) / taux)
    if tarif.unite == UNITE_SECONDE:
        if "prix_par_minute" in tarif.prix:
            par_seconde = tarif.prix["prix_par_minute"] / 60
        else:
            par_seconde = tarif.prix["prix_par_heure"] / 3600
        return _arrondir(max(quantite_in, 0) * par_seconde * MICRO / taux)
    return _arrondir(max(quantite_in, 0) * tarif.prix["prix_par_million_caracteres"] / taux)


def chiffrer(
    grille: GrilleTarifaire, modele: str, unite: str, tokens_in: int, tokens_out: int,
    tokens_cache: int, issue: str, compatibles: Iterable[str] = (),
) -> Cout:
    """[US-309 / CA4, CA5] Fournisseur, coût en micro-euros et version de grille d'une ligne.

    `unite` est celle de la ligne (`jeton` | `seconde` | `caractere`) : elle doit être celle du
    tarif du modèle, sans quoi l'appel n'est pas chiffrable (coût nul, jamais un coût inventé)."""
    fournisseur, cle = fournisseur_et_modele(modele, compatibles)
    if issue != ISSUE_OK and not (tokens_in or tokens_out or tokens_cache):
        return Cout(fournisseur, 0, grille.version)             # rien consommé, rien facturé
    tarif = grille.tarif(fournisseur, cle)
    if tarif is None or tarif.unite != unite:
        return Cout(fournisseur, None, grille.version)
    return Cout(fournisseur, _cout_micro_eur(tarif, grille, tokens_in, tokens_out, tokens_cache), grille.version)
