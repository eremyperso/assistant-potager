"""
app/services/rapport_couverture.py — Rapport de couverture du référentiel [US-166]
----------------------------------------------------------------------------------
**Un livrable, pas un journal.** Ce rapport est l'instrument de décision de tout
l'ÉPIC 6 : c'est lui, et non une intuition, qui dit s'il faut compléter à la
main, étendre le périmètre au-delà des dix cultures, ou renoncer à l'appariement
automatique. Sans lui, l'extension se ferait au fil de l'envie d'exhaustivité —
le travers explicitement écarté par l'arbitrage des dix cultures.

Il vit dans `app/services/` et non dans le script d'import parce qu'il se
produit indépendamment de tout import (`--rapport-seul`) et qu'il doit être
testable sans fichier source.

Les quatre chiffres qu'il publie
--------------------------------
- **Trois états de couverture** (CA9), qui forment une partition des cultures
  réellement présentes dans l'historique : `couvert`, `non_couvert`, et à part
  `configure_jamais_utilise` — 14 des 54 configurations mesurées le 25/08/2026
  ne portent aucun événement, les compter comme couvertes maquillerait le taux.
- **Cultures suspectes** (CA10) : présentes dans les événements, inconnues de la
  configuration. Le cas d'école de production est `radi`, né de « Y a t il des
  radis dans mon jardin » enregistré comme un événement au lieu d'être reconnu
  comme une question. Une culture fantôme issue d'un échec de parsing est
  signalée pour revue, **jamais** transformée en fiche.
- **Synonymes probables** (CA11) : signalés, jamais fusionnés. Trois indices de
  fiabilité décroissante, portés explicitement par chaque groupe pour qu'un
  relecteur les priorise — le rapprochement par nom vernaculaire est la clé la
  moins fiable des trois.
- **Taux d'appariement** (CA12) : sous ~70 %, l'import automatique perd son
  intérêt face à la saisie directe sur dix cultures.

⚠️ Les bulletins météo automatiques (`texte_original = '[AUTO-METEO]'`) sont
exclus de toute statistique : 96 des 321 événements de production, soit 30 % de
bruit machine. Les compter gonflerait « non couvert » de cultures qui n'ont
jamais été jardinées.

Aucun appel réseau (CA8) : le rapport ne lit que la base.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models import CultureConfig, Evenement
from utils.culture_resolve import normaliser_culture
from utils.parcelles import levenshtein_distance

#: Marqueur des bulletins météo automatiques, à exclure de toute statistique.
TEXTE_AUTO_METEO = "[AUTO-METEO]"

#: [CA12] En dessous, l'import automatique ne vaut plus la saisie directe.
SEUIL_APPARIEMENT = 0.70

#: Distance de Levenshtein sous laquelle deux libellés sont dits proches —
#: même valeur que `utils.culture_resolve`, pour que le rapport signale
#: exactement ce que la résolution de culture rapprocherait déjà.
_LEVENSHTEIN_MAX = 2

INDICE_SOUS_CHAINE = "sous_chaine"
INDICE_LEXICAL = "lexical"
INDICE_MEME_FAMILLE = "meme_famille"

#: Fiabilité décroissante — un relecteur traite les groupes dans cet ordre.
ORDRE_INDICES: tuple[str, ...] = (INDICE_SOUS_CHAINE, INDICE_LEXICAL, INDICE_MEME_FAMILLE)


@dataclass(frozen=True)
class GroupeSynonymes:
    """[CA11] Un groupe de libellés à rapprocher — proposé, jamais fusionné."""
    libelles: tuple[str, ...]
    indice: str
    detail: str = ""


@dataclass
class RapportCouverture:
    """[CA9-CA12] Le rapport, tel qu'il pilote la suite de l'épic."""

    couvert: list[str] = field(default_factory=list)
    non_couvert: list[str] = field(default_factory=list)
    configure_jamais_utilise: list[str] = field(default_factory=list)
    cultures_suspectes: list[str] = field(default_factory=list)
    synonymes_probables: list[GroupeSynonymes] = field(default_factory=list)
    taux_appariement: float = 0.0
    seuil_appariement_atteint: bool = False

    @property
    def total_cultures_presentes(self) -> int:
        """Cultures portant au moins un événement réel — la partition des trois listes."""
        return len(self.couvert) + len(self.non_couvert) + len(self.cultures_suspectes)


def _cultures_avec_evenements(db: Session, potager_id: int | None = None) -> dict[str, str]:
    """
    Cultures portant au moins un événement réel : normalisée → libellé d'origine.

    ⚠️ Exclut les bulletins `[AUTO-METEO]`. `potager_id=None` balaie toute la
    base — le rapport est un outil d'administration du référentiel, qui est
    global (`culture_config.potager_id` est NULL sur la totalité des lignes
    mesurées), pas une vue par jardinier.
    """
    requete = db.query(Evenement.culture, Evenement.texte_original).filter(
        Evenement.culture.isnot(None),
        or_(
            Evenement.texte_original.is_(None),
            Evenement.texte_original != TEXTE_AUTO_METEO,
        ),
    )
    if potager_id is not None:
        requete = requete.filter(Evenement.potager_id == potager_id)

    presentes: dict[str, str] = {}
    for culture, _texte in requete.all():
        cle = normaliser_culture(culture)
        if cle:
            presentes.setdefault(cle, culture.strip())
    return presentes


def _detecter_synonymes(
    presentes: dict[str, str], familles_par_culture: dict[str, str]
) -> list[GroupeSynonymes]:
    """
    [CA11] Trois indices indépendants, aucun automatisme de fusion.

    1. `sous_chaine` — `haricot` / `haricot grimpant`. L'indice le plus sûr : un
       libellé est le préfixe qualifié de l'autre.
    2. `lexical` — Levenshtein ≤ 2 : `courge` / `courgette`. Même seuil que la
       résolution de culture, donc mêmes rapprochements que ceux déjà faits à la
       dictée.
    3. `meme_famille` — `laitue` / `salade`, et les dix libellés de
       cucurbitacées. **Le plus faible des trois** : une famille regroupe aussi
       des cultures parfaitement distinctes (tomate et aubergine). Il est publié
       quand même parce que c'est le seul indice qui rapproche deux mots sans
       aucune parenté lexicale, et parce que le poids cumulé des cucurbitacées
       — au-dessus de la tomate — ne se voit pas autrement.
    """
    groupes: list[GroupeSynonymes] = []
    cles = sorted(presentes)

    for i, a in enumerate(cles):
        for b in cles[i + 1:]:
            if a in b or b in a:
                groupes.append(GroupeSynonymes(
                    libelles=(presentes[a], presentes[b]),
                    indice=INDICE_SOUS_CHAINE,
                    detail="un libellé est contenu dans l'autre",
                ))
            elif levenshtein_distance(a, b) <= _LEVENSHTEIN_MAX:
                groupes.append(GroupeSynonymes(
                    libelles=(presentes[a], presentes[b]),
                    indice=INDICE_LEXICAL,
                    detail=f"distance de Levenshtein {levenshtein_distance(a, b)}",
                ))

    # Regroupement par famille : un groupe par famille, pas une paire par couple —
    # les dix cucurbitacées forment une seule ligne de revue, pas quarante-cinq.
    par_famille: dict[str, list[str]] = {}
    for cle, libelle in presentes.items():
        famille = familles_par_culture.get(cle)
        if famille:
            par_famille.setdefault(famille, []).append(libelle)
    deja_signales = [set(groupe.libelles) for groupe in groupes]
    for famille, libelles in sorted(par_famille.items()):
        # Un groupe de famille qui ne dit rien de plus qu'un rapprochement déjà
        # signalé par un indice plus fiable est tu : « haricot / haricot grimpant »
        # n'a pas besoin d'une seconde ligne de revue.
        if len(libelles) > 1 and not any(set(libelles) <= couvert for couvert in deja_signales):
            groupes.append(GroupeSynonymes(
                libelles=tuple(sorted(libelles)),
                indice=INDICE_MEME_FAMILLE,
                detail=f"famille {famille} — indice le moins fiable, relecture obligatoire",
            ))

    return sorted(groupes, key=lambda g: (ORDRE_INDICES.index(g.indice), g.libelles))


def construire_rapport(db: Session, potager_id: int | None = None) -> RapportCouverture:
    """
    [CA9-CA12] Produit le rapport de couverture depuis l'état courant de la base.

    Une culture est dite **couverte** quand elle porte un événement réel, qu'une
    fiche `culture_config` existe pour elle, et que cette fiche a été enrichie
    par le référentiel structuré (famille botanique renseignée). Une fiche vide
    de tout attribut importé n'est pas une couverture : c'est un nom.
    """
    presentes = _cultures_avec_evenements(db, potager_id)

    configs = db.query(CultureConfig).all()
    config_par_culture: dict[str, CultureConfig] = {}
    for config in configs:
        cle = normaliser_culture(config.nom)
        # Une culture peut porter plusieurs fiches (globale + personnalisée) :
        # la fiche enrichie prime, sans quoi une fiche vide masquerait la couverture.
        existante = config_par_culture.get(cle)
        if existante is None or (existante.famille_id is None and config.famille_id is not None):
            config_par_culture[cle] = config

    familles_par_culture = {
        cle: config.famille_rel.nom
        for cle, config in config_par_culture.items()
        if config.famille_rel is not None
    }

    rapport = RapportCouverture()
    for cle, libelle in sorted(presentes.items()):
        config = config_par_culture.get(cle)
        if config is None:
            # [CA10] Présente dans les événements, inconnue de la configuration :
            # suspecte, signalée, et surtout jamais transformée en fiche.
            rapport.cultures_suspectes.append(libelle)
        elif config.famille_id is not None:
            rapport.couvert.append(libelle)
        else:
            rapport.non_couvert.append(libelle)

    rapport.configure_jamais_utilise = sorted(
        config.nom for cle, config in config_par_culture.items() if cle not in presentes
    )

    rapport.synonymes_probables = _detecter_synonymes(presentes, familles_par_culture)

    total = rapport.total_cultures_presentes
    rapport.taux_appariement = (len(rapport.couvert) / total) if total else 0.0
    rapport.seuil_appariement_atteint = rapport.taux_appariement >= SEUIL_APPARIEMENT
    return rapport


def formater_rapport(rapport: RapportCouverture) -> str:
    """Rend le rapport lisible en console — c'est la forme qu'en voit l'administrateur."""
    lignes: list[str] = ["", "═══ Rapport de couverture du référentiel [US-166] ═══", ""]

    lignes.append(f"Cultures réellement présentes dans l'historique : {rapport.total_cultures_presentes}")
    lignes.append(f"  ✅ couvert                        : {len(rapport.couvert)} — {', '.join(rapport.couvert) or '—'}")
    lignes.append(f"  ⬜ non couvert                    : {len(rapport.non_couvert)} — {', '.join(rapport.non_couvert) or '—'}")
    lignes.append(
        f"  💤 configuré mais jamais utilisé  : {len(rapport.configure_jamais_utilise)} — "
        f"{', '.join(rapport.configure_jamais_utilise) or '—'}"
    )
    lignes.append("")

    lignes.append(f"⚠️  Cultures suspectes (inconnues de la configuration) : {len(rapport.cultures_suspectes)}")
    for libelle in rapport.cultures_suspectes:
        lignes.append(f"     • {libelle} — aucune fiche créée, à revoir manuellement")
    lignes.append("")

    lignes.append(f"🔎 Synonymes probables — à relire, jamais fusionnés : {len(rapport.synonymes_probables)}")
    for groupe in rapport.synonymes_probables:
        lignes.append(f"     • [{groupe.indice}] {' / '.join(groupe.libelles)} ({groupe.detail})")
    lignes.append("")

    verdict = "✅ au-dessus du seuil" if rapport.seuil_appariement_atteint else (
        "❌ SOUS LE SEUIL — la saisie manuelle des dix cultures du périmètre est le repli"
    )
    lignes.append(
        f"📊 Taux d'appariement automatique : {rapport.taux_appariement:.0%} "
        f"(seuil {SEUIL_APPARIEMENT:.0%}) — {verdict}"
    )
    lignes.append("")
    return "\n".join(lignes)
