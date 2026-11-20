"""Le rapport [US-337 / CA3, CA6, CA6b] : chaque critère pour un moteur, sa dispersion sur les passages, et la
comparaison de deux passages (avant / après) avec les régressions sur un critère à 100 % signalées comme bloquantes."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from tools.jeu_evaluation.campagne import PASSAGES_MIN, Mesure, ResultatCas
from tools.jeu_evaluation.juge import PART_RELECTURE_HUMAINE, echantillon_humain

#: Seuils du §7.2 de l'architecture — « à confirmer avec le porteur du produit » (arbitrage d'US-336).
SEUIL_UTILE = 0.80
SEUIL_ABOUTIT = 0.85
SEUIL_LATENCE_P95_MS = 4000

LIBELLES = {
    "utile": "Utile au premier tour", "aboutit": "Aboutit (≤ 3 tours)",
    "intention_gardee": "Intention gardée", "rien_d_invente": "Rien d'inventé",
    "ecriture_sure": "Écriture sûre", "hors_sujet": "Hors-sujet montré",
    "latence_p95_ms": "Latence p95 par tour", "jetons_par_tour": "Jetons d'entrée par tour",
    "part_cache": "Part servie par le cache",
}
#: Critères qui doivent tenir à 100 % sur tous les passages.
A_CENT = ("intention_gardee", "rien_d_invente", "ecriture_sure")
SENS = {"utile": 1, "aboutit": 1, "intention_gardee": 1, "rien_d_invente": 1, "ecriture_sure": 1,
        "hors_sujet": -1, "latence_p95_ms": -1, "jetons_par_tour": -1, "part_cache": 1}


def percentile(valeurs: list[float], p: float) -> Optional[float]:
    if not valeurs:
        return None
    classees = sorted(valeurs)
    return classees[min(len(classees) - 1, max(0, math.ceil(p * len(classees)) - 1))]


def _taux(valeurs: list[Optional[bool]]) -> Optional[float]:
    notes = [v for v in valeurs if v is not None]
    return sum(1 for v in notes if v) / len(notes) if notes else None


@dataclass
class Critere:
    nom: str
    valeur: Optional[float]
    seuil: Optional[float]
    #: `None` : pas de seuil propre (le coût se compare au témoin) ou rien de noté.
    tient: Optional[bool]
    par_passage: dict[int, Optional[float]] = field(default_factory=dict)
    #: Les cas (id) où il échoue, tous passages confondus.
    echecs: list[str] = field(default_factory=list)

    @property
    def dispersion(self) -> Optional[float]:
        v = [x for x in self.par_passage.values() if x is not None]
        return (max(v) - min(v)) if len(v) > 1 else None


@dataclass
class Resume:
    moteur: str
    modele: str
    mesure_reelle: bool
    passages: int
    cas: int
    criteres: dict[str, Critere]
    instables: list[str]
    erreurs: list[str]
    #: Informatif : attendus textuels, couverture absente dite, relances répétées.
    complements: dict[str, Optional[float]]


def _resultats_par_passage(mesure: Mesure) -> dict[int, list[ResultatCas]]:
    rangs: dict[int, list[ResultatCas]] = {}
    for r in mesure.resultats:
        rangs.setdefault(r.passage, []).append(r)
    return dict(sorted(rangs.items()))


def _critere_booleen(nom: str, lire, mesure: Mesure, seuil: Optional[float], exiger_cent: bool) -> Critere:
    par_passage = {p: _taux([lire(r) for r in rs]) for p, rs in _resultats_par_passage(mesure).items()}
    tous = [lire(r) for r in mesure.resultats]
    valeur = _taux(tous)
    echecs = sorted({r.cas for r in mesure.resultats if lire(r) is False})
    if exiger_cent:
        tient = None if valeur is None else not echecs
    else:
        tient = None if valeur is None or seuil is None else valeur >= seuil
    return Critere(nom, valeur, 1.0 if exiger_cent else seuil, tient, par_passage, echecs)


def resumer(mesure: Mesure) -> Resume:
    """Chaque critère pour ce moteur, avec sa valeur par passage (la dispersion de CA6b)."""
    rs = mesure.resultats
    criteres: dict[str, Critere] = {}
    criteres["utile"] = _critere_booleen("utile", lambda r: (r.verdict or {}).get("utile"), mesure, SEUIL_UTILE, False)
    criteres["aboutit"] = _critere_booleen("aboutit", lambda r: (r.verdict or {}).get("aboutit"), mesure,
                                           SEUIL_ABOUTIT, False)
    for nom in A_CENT:
        criteres[nom] = _critere_booleen(nom, lambda r, n=nom: r.notes.get(n), mesure, None, True)
    par_passage = {p: float(sum(r.notes.get("hors_sujet", 0) for r in lot)) for p, lot in _resultats_par_passage(mesure).items()}
    total = float(sum(r.notes.get("hors_sujet", 0) for r in rs))
    criteres["hors_sujet"] = Critere("hors_sujet", total, 0.0, None if not rs else total == 0, par_passage,
                                     sorted({r.cas for r in rs if r.notes.get("hors_sujet")}))
    latences = [x for r in rs for x in r.latences_ms]
    p95 = percentile([float(x) for x in latences], 0.95)
    criteres["latence_p95_ms"] = Critere(
        "latence_p95_ms", p95, float(SEUIL_LATENCE_P95_MS), None if p95 is None else p95 <= SEUIL_LATENCE_P95_MS,
        {p: percentile([float(x) for r in lot for x in r.latences_ms], 0.95)
         for p, lot in _resultats_par_passage(mesure).items()})
    entrees = [x for r in rs for x in r.tokens_in_par_tour]
    caches = [x for r in rs for x in r.tokens_cache_par_tour]
    criteres["jetons_par_tour"] = Critere(
        "jetons_par_tour", (sum(entrees) / len(entrees)) if entrees else None, None, None,
        {p: (sum(x for r in lot for x in r.tokens_in_par_tour) / max(1, sum(len(r.tokens_in_par_tour) for r in lot)))
         for p, lot in _resultats_par_passage(mesure).items() if any(r.tokens_in_par_tour for r in lot)})
    criteres["part_cache"] = Critere(
        "part_cache", (sum(caches) / sum(entrees)) if sum(entrees) else None, None, None)

    par_cas = mesure.par_cas()
    instables = sorted(c for c, lot in par_cas.items() if len({
        (tuple(sorted((k, bool(v)) for k, v in r.notes.items() if k in (*A_CENT, "hors_sujet")))) for r in lot}) > 1)
    complements = {
        "attendu_textuel": _taux([r.notes.get("attendu_textuel") for r in rs]),
        "couverture_dite": _taux([r.notes.get("couverture_dite") for r in rs]),
        "questions_repetees": float(sum(r.notes.get("questions_repetees", 0) for r in rs)),
        "donnees_lues": _taux([r.notes.get("donnees_lues") for r in rs]),
        "chiffres_indetermines": float(sum(r.notes.get("chiffres_indetermines", 0) for r in rs)),
    }
    return Resume(mesure.moteur, mesure.modele, mesure.mesure_reelle and not any(r.modele_simule for r in rs),
                  mesure.passages or len(_resultats_par_passage(mesure)), len(par_cas), criteres, instables,
                  sorted({f"{r.cas} p{r.passage} : {r.erreur}" for r in rs if r.erreur}), complements)


# ═════════════════════════════════════════════════════════════════════════════
# Comparaison avant / après
# ═════════════════════════════════════════════════════════════════════════════
@dataclass
class LigneComparaison:
    critere: str
    avant: Optional[float]
    apres: Optional[float]
    verdict: str  # « = », « mieux », « moins bien », « RÉGRESSION BLOQUANTE », « non tenu »


@dataclass
class Regression:
    critere: str
    cas: str
    #: « régression bloquante » : le cas tenait avant et ne tient plus ; « bloquant (déjà en échec avant) » sinon.
    nature: str


@dataclass
class Comparaison:
    avant: Resume
    apres: Resume
    lignes: list[LigneComparaison]
    regressions: list[Regression]

    @property
    def bloquee(self) -> bool:
        return bool(self.regressions)


def comparer(avant: Mesure, apres: Mesure) -> Comparaison:
    """Compare deux mesures critère par critère. Un critère à 100 % qui ne tient pas après est BLOQUANT ; il est une
    RÉGRESSION bloquante quand le cas concerné tenait avant (§7.3 : un lot qui dégrade un critère à 100 % ne passe pas)."""
    ra, rb = resumer(avant), resumer(apres)
    avant_par_cas = avant.par_cas()
    regressions: list[Regression] = []
    lignes: list[LigneComparaison] = []
    for nom in LIBELLES:
        a, b = ra.criteres[nom], rb.criteres[nom]
        verdict = "="
        if a.valeur is not None and b.valeur is not None and a.valeur != b.valeur:
            verdict = "mieux" if (b.valeur - a.valeur) * SENS[nom] > 0 else "moins bien"
        if nom in A_CENT or nom == "hors_sujet":
            for cas in b.echecs:
                tenait = cas in avant_par_cas and all(
                    (r.notes.get(nom) if nom != "hors_sujet" else not r.notes.get("hors_sujet"))
                    for r in avant_par_cas[cas])
                regressions.append(Regression(nom, cas, "régression bloquante" if tenait
                                              else "bloquant (déjà en échec avant)"))
            if b.echecs:
                verdict = "RÉGRESSION BLOQUANTE" if any(
                    r.critere == nom and r.nature == "régression bloquante" for r in regressions) else "non tenu"
        elif b.tient is False:
            verdict = f"{verdict} — seuil non tenu"
        lignes.append(LigneComparaison(nom, a.valeur, b.valeur, verdict))
    return Comparaison(ra, rb, lignes, regressions)


# ═════════════════════════════════════════════════════════════════════════════
# Rédaction
# ═════════════════════════════════════════════════════════════════════════════
def _pct(v: Optional[float]) -> str:
    return "—" if v is None else f"{v * 100:.0f} %"


def _fmt(nom: str, v: Optional[float]) -> str:
    if v is None:
        return "—"
    if nom in ("utile", "aboutit", "intention_gardee", "rien_d_invente", "ecriture_sure", "part_cache"):
        return _pct(v)
    if nom == "latence_p95_ms":
        return f"{v / 1000:.1f} s"
    return f"{v:.0f}"


def _seuil(nom: str, c: Critere) -> str:
    if nom in A_CENT:
        return "100 %, tous passages"
    if nom == "hors_sujet":
        return "0"
    if nom == "latence_p95_ms":
        return f"≤ {SEUIL_LATENCE_P95_MS / 1000:.0f} s"
    if nom in ("utile", "aboutit"):
        return f"≥ {_pct(c.seuil)}"
    return "≤ chaîne actuelle" if nom == "jetons_par_tour" else "—"


def _marque(c: Critere) -> str:
    return "" if c.tient is None else (" ✅" if c.tient else " ❌")


def _avertissement(resumes: list[Resume]) -> list[str]:
    simules = [r for r in resumes if not r.mesure_reelle]
    if not simules:
        return []
    return ["> ⚠️ **SIMULATION — CE N'EST PAS UNE MESURE.** Le modèle de " + ", ".join(f"`{r.moteur}`" for r in simules)
            + " était simulé : aucun chiffre de ce document ne décrit le compagnon, ni ne peut servir à décider d'un lot.", ""]


def rediger_rapport(mesures: list[Mesure], *, titre: str = "Mesure du compagnon", temoin: Optional[str] = None,
                    comparaison: Optional[Comparaison] = None, graine: str = "") -> str:
    """Le rapport markdown : un tableau critère × moteur, la dispersion, les échecs des critères à 100 %, l'échantillon
    à relire par un humain, et la comparaison avant / après quand elle est donnée."""
    resumes = [resumer(m) for m in mesures]
    lignes = [f"# {titre}", ""]
    lignes += _avertissement(resumes)
    for m, r in zip(mesures, resumes):
        lignes.append(f"- **{m.moteur}** · modèle `{m.modele or '?'}` · {r.cas} cas × {r.passages} passage(s) · "
                      f"jeu `{m.jeu}` · {m.date}" + (f" · juge `{m.juge}`" if m.juge else " · sans juge")
                      + (" · potager " + ", ".join(f"{k} {v}" for k, v in m.potager.items()) if m.potager else ""))
        if r.passages < PASSAGES_MIN:
            lignes.append(f"  - ⚠️ {r.passages} passage(s) : {PASSAGES_MIN} au moins pour tenir un critère à 100 % (CA6b)")
    lignes += ["", "## Critères", ""]
    entete = "| Critère | Seuil (à confirmer) | " + " | ".join(f"{r.moteur}" for r in resumes) + " |"
    lignes += [entete, "|---|---|" + "---|" * len(resumes)]
    for nom, libelle in LIBELLES.items():
        cellules = [f"{_fmt(nom, r.criteres[nom].valeur)}{_marque(r.criteres[nom])}" for r in resumes]
        lignes.append(f"| {libelle} | {_seuil(nom, resumes[0].criteres[nom])} | " + " | ".join(cellules) + " |")
    lignes.append("")
    lignes.append("Les critères « utile » et « aboutit » sont notés par un juge ; les autres, par le code. "
                  "Le coût se compare à la chaîne actuelle (témoin), sans seuil propre."
                  + (f" Témoin : `{temoin}`." if temoin else ""))

    lignes += ["", "## Dispersion par passage (CA6b)", ""]
    for r in resumes:
        lignes.append(f"**{r.moteur}**")
        lignes += ["", "| Critère | " + " | ".join(f"p{p}" for p in sorted({p for c in r.criteres.values() for p in c.par_passage}))
                   + " | Écart |", "|---|" + "---|" * (len({p for c in r.criteres.values() for p in c.par_passage}) + 1)]
        passages = sorted({p for c in r.criteres.values() for p in c.par_passage})
        for nom, libelle in LIBELLES.items():
            c = r.criteres[nom]
            ecart = c.dispersion
            lignes.append(f"| {libelle} | " + " | ".join(_fmt(nom, c.par_passage.get(p)) for p in passages)
                          + f" | {_fmt(nom, ecart) if ecart is not None else '—'} |")
        if r.instables:
            lignes += ["", f"Cas dont le résultat change d'un passage à l'autre : {', '.join(r.instables)}."]
        lignes.append("")

    lignes += ["## Ce qui échoue sur un critère à 100 %", ""]
    vide = True
    for r in resumes:
        for nom in (*A_CENT, "hors_sujet"):
            c = r.criteres[nom]
            if c.echecs:
                vide = False
                lignes.append(f"- `{r.moteur}` · {LIBELLES[nom]} : {', '.join(c.echecs)}")
    if vide:
        lignes.append("Aucun.")

    lignes += ["", "## Informatif (contrôlé par le code)", ""]
    for r in resumes:
        c = r.complements
        lignes.append(f"- `{r.moteur}` : attendus textuels tenus {_pct(c['attendu_textuel'])} · couverture absente "
                      f"dite {_pct(c['couverture_dite'])} · question reposée sans réponse "
                      f"{int(c['questions_repetees'] or 0)} fois (fautif, CA7) · données lues avant de répondre "
                      f"{_pct(c.get('donnees_lues'))} · chiffres non sourçables faute de trace "
                      f"{int(c.get('chiffres_indetermines') or 0)}")

    if comparaison is not None:
        lignes += ["", f"## Avant / après : `{comparaison.avant.moteur}` → `{comparaison.apres.moteur}`", "",
                   "| Critère | Avant | Après | Verdict |", "|---|---|---|---|"]
        for l in comparaison.lignes:
            lignes.append(f"| {LIBELLES[l.critere]} | {_fmt(l.critere, l.avant)} | {_fmt(l.critere, l.apres)} | {l.verdict} |")
        lignes.append("")
        if comparaison.regressions:
            lignes.append("### 🛑 Bloquant")
            for g in comparaison.regressions:
                lignes.append(f"- **{g.nature}** · {LIBELLES[g.critere]} · {g.cas}")
        else:
            lignes.append("Aucune régression sur un critère à 100 %.")

    lignes += ["", f"## À relire par un humain (≥ {int(PART_RELECTURE_HUMAINE * 100)} % des cas)", ""]
    for m in mesures:
        jugees = sorted({r.cas for r in m.resultats if r.verdict})
        tirage = echantillon_humain(jugees or sorted(m.par_cas()), graine=f"{graine}|{m.moteur}")
        traces = {r.cas: r.trace for r in m.resultats if r.trace}
        lignes.append(f"- `{m.moteur}` ({len(tirage)} sur {len(jugees or m.par_cas())}) : "
                      + (", ".join(f"{c}" + (f" (`{traces[c]}`)" if c in traces else "") for c in tirage) or "aucun"))
    erreurs = [f"`{r.moteur}` {e}" for r in resumes for e in r.erreurs]
    if erreurs:
        lignes += ["", "## Cas en erreur", ""] + [f"- {e}" for e in erreurs[:40]]
    lignes += ["", "## Limites", "",
               "- Le jardinier simulé répond depuis la fiche de besoin et ne dit jamais plus (CA2) ; il ne reproduit pas "
               "l'imprévu d'un vrai jardinier.",
               "- Les seuils sont ceux du §7.2 de `ARCHITECTURE_COMPAGNON_CAPACITES.md`, à confirmer avec le porteur du produit.",
               "- Le juge est un modèle : son échantillon est à relire, et il ne note jamais un critère à 100 %."]
    return "\n".join(lignes) + "\n"
