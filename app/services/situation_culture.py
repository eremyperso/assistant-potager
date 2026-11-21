"""
app/services/situation_culture.py — Le verdict de saison d'une culture, celui de la fiche culture [US-339]
=========================================================================================================

« Est-ce le moment de planter des salades ? » La fiche culture de la PWA (section « Maintenant »,
`frontend/src/lib/ficheCulture.js::sectionMaintenant`, US-207) répond en CHOISISSANT parmi deux lectures
du serveur, sans rien recalculer :

- `GET /plan/confiances/candidates` : une évaluation par action (semis en pépinière, semis en place,
  plantation), avec son score et ses règles (`confiance_semis.confiances_du_plan`) ;
- `GET /plan/calendriers` : les mois de chaque phase pour la zone du potager
  (`calendrier_cultural.calendriers_du_plan`).

Ce module fait EXACTEMENT le même choix, côté serveur, pour le compagnon et le MCP (principe R3 de
`07_REGLE_D_UNE_CAPACITE.md`) : le geste le mieux noté de TOUTES les actions, ouvert si sa règle R1
(« dans la fenêtre conseillée ») est gagnée, et la fenêtre de ce geste. La parité est tenue par un jeu
de cas partagé, `tests/corpus/parite_situation_culture.json`, que vérifient à la fois
`tests/test_us339_situation_culture.py` et `frontend/src/lib/ficheCulture.test.js` (CA2) : une
divergence entre la fiche et le compagnon casse l'un des deux.

Aucune lecture en base ici : des fonctions pures sur les réponses des deux lectures.
"""
from __future__ import annotations

from typing import Optional

#: L'ordre du sélecteur de la fiche (`confiance.js::ORDRE_ACTIONS`).
ORDRE_ACTIONS: tuple[str, ...] = ("semis_pepiniere", "semis_pleine_terre", "plantation")

#: Le geste à l'infinitif, comme la fiche le dit (`confiance.js::LIBELLE_ACTION`).
LIBELLE_ACTION: dict[str, str] = {
    "semis_pepiniere": "Semer en pépinière",
    "semis_pleine_terre": "Semer en place",
    "plantation": "Planter",
}

#: À score égal, le geste le plus avancé l'emporte (`calendrier.js::PRIORITE_PHASES` :
#: récolte, plantation, pleine terre, pépinière).
_RANG_DE_PHASE: dict[str, int] = {"plantation": 1, "semis_pleine_terre": 2, "semis_pepiniere": 3}

MOIS_NOMS: tuple[str, ...] = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)
TIRET = "—"

#: Les états de la section « Maintenant » (mêmes noms que la fiche).
ETAT_ILLISIBLE = "illisible"
ETAT_SANS_CALENDRIER = "sans_calendrier"
ETAT_OUVERTE = "ouverte"
ETAT_FERMEE = "fermee"

#: Les verdicts rendus au compagnon (CA1, CA6).
VERDICT_MAINTENANT = "c_est_le_moment"
VERDICT_PAS_CE_MOIS = "pas_ce_mois_ci"
VERDICT_HORS_CALENDRIER = "hors_calendrier_connu"
VERDICT_INCONNUE = "culture_inconnue"


def _rang_de_phase(action: Optional[str]) -> int:
    return _RANG_DE_PHASE.get(action or "", len(_RANG_DE_PHASE) + 1)


def actions_de_fiche(entree: Optional[dict]) -> list[dict]:
    """Les évaluations de la culture, dans l'ordre du sélecteur (`actionsDeFiche`)."""
    def rang(a: dict) -> int:
        return ORDRE_ACTIONS.index(a["action"]) if a.get("action") in ORDRE_ACTIONS else -1
    return sorted((entree or {}).get("actions") or [], key=rang)


def meilleure_action(actions: list[dict]) -> Optional[dict]:
    """La mieux placée (`meilleureCandidate`) : le meilleur score ; à score égal, le geste le plus avancé."""
    gagnante: Optional[dict] = None
    for c in actions:
        if gagnante is None:
            gagnante = c
            continue
        sc, sg = c.get("score") or 0, gagnante.get("score") or 0
        if sc != sg:
            gagnante = c if sc > sg else gagnante
        elif _rang_de_phase(c.get("action")) < _rang_de_phase(gagnante.get("action")):
            gagnante = c
    return gagnante


def fenetre_lisible(mois: Optional[list]) -> str:
    """« février à mars », « mai », ou « — » (`fenetreLisible`) : premier et dernier mois de la liste."""
    valides = [m for m in (mois or []) if isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 12]
    if not valides:
        return TIRET
    debut, fin = valides[0], valides[-1]
    return MOIS_NOMS[debut - 1] if debut == fin else f"{MOIS_NOMS[debut - 1]} à {MOIS_NOMS[fin - 1]}"


def _etat_fenetre(evaluation: dict) -> Optional[str]:
    """L'état de la règle R1 (« dans la fenêtre conseillée ») d'une évaluation."""
    return next((m.get("etat") for m in evaluation.get("motifs") or [] if m.get("regle") == "R1"), None)


def section_maintenant(entree: Optional[dict], mois_par_phase: Optional[dict], confiance_lue: bool = True) -> dict:
    """[CA2] Ce que la section « Maintenant » de la fiche culture affiche, champ pour champ
    (`sectionMaintenant`) : `etat`, `geste`, `etoiles`, `fenMois`, plus `action` (la clé du geste)."""
    if not confiance_lue:
        return {"etat": ETAT_ILLISIBLE}
    actions = actions_de_fiche(entree)
    if not (entree or {}).get("a_calendrier") or not actions:
        return {"etat": ETAT_SANS_CALENDRIER}
    meilleure = meilleure_action(actions)
    return {
        "etat": ETAT_OUVERTE if _etat_fenetre(meilleure) == "gagne" else ETAT_FERMEE,
        "action": meilleure.get("action"),
        "geste": LIBELLE_ACTION.get(meilleure.get("action"), ""),
        "etoiles": meilleure.get("etoiles"),
        "fenMois": fenetre_lisible((mois_par_phase or {}).get(meilleure.get("action"))),
    }


def fenetres(mois_par_phase: Optional[dict]) -> list[dict]:
    """Toutes les fenêtres de semis et de plantation de la zone, dans l'ordre du sélecteur."""
    return [
        {"action": a, "geste": LIBELLE_ACTION[a], "mois": list((mois_par_phase or {}).get(a) or []),
         "fenetre": fenetre_lisible((mois_par_phase or {}).get(a))}
        for a in ORDRE_ACTIONS if (mois_par_phase or {}).get(a)
    ]


def verdict(entree: Optional[dict], mois_par_phase: Optional[dict], culture: str,
            mois_courant: Optional[int] = None) -> dict:
    """[CA1, CA5b, CA6] Le verdict de saison toutes actions confondues, avec sa phrase.

    - culture absente du référentiel → `culture_inconnue`, sans verdict inventé ;
    - connue mais sans fenêtre pour la zone → `hors_calendrier_connu` ;
    - sinon le choix de la fiche : `c_est_le_moment` (geste et fenêtre) ou `pas_ce_mois_ci` (prochaine
      fenêtre = celle du geste le mieux noté, comme « Prochaine fenêtre » sur la fiche).
    Jamais « indéterminé » : une culture qui a une fenêtre sur l'une de ses actions a un verdict.
    """
    if entree is not None and entree.get("culture_connue") is False:
        return {"verdict": VERDICT_INCONNUE,
                "texte": f"« {culture} » n'est pas dans le référentiel des cultures : je n'ai pas de calendrier."}
    maintenant = section_maintenant(entree, mois_par_phase)
    toutes = fenetres(mois_par_phase)
    if maintenant["etat"] == ETAT_SANS_CALENDRIER:
        if toutes:
            # [CA5b] Repli rare : le calendrier a des fenêtres que les confiances n'ont pas évaluées. Le verdict
            # se lit alors sur le mois seul (la règle R1, sans météo) : jamais « indéterminé ».
            ouvertes = [f for f in toutes if mois_courant in f["mois"]]
            if ouvertes:
                f = ouvertes[-1]
                return {"verdict": VERDICT_MAINTENANT, "geste": f["geste"], "action": f["action"],
                        "fenetre": f["fenetre"], "fenetres": toutes,
                        "texte": f"C'est le moment : {f['geste'].lower()} ({f['fenetre']})."}
            return {"verdict": VERDICT_PAS_CE_MOIS, "fenetres": toutes,
                    "texte": f"Pas ce mois-ci. Fenêtres pour {culture} : "
                             + " ; ".join(f"{f['geste'].lower()} {f['fenetre']}" for f in toutes) + "."}
        return {"verdict": VERDICT_HORS_CALENDRIER,
                "texte": f"Hors calendrier connu : aucune fenêtre de semis ni de plantation pour {culture} "
                         "dans la zone du potager."}
    geste, fenetre = maintenant["geste"], maintenant["fenMois"]
    if maintenant["etat"] == ETAT_OUVERTE:
        return {"verdict": VERDICT_MAINTENANT, "geste": geste, "action": maintenant["action"],
                "fenetre": fenetre, "etoiles": maintenant["etoiles"], "fenetres": toutes,
                "texte": f"C'est le moment : {geste.lower()} ({fenetre})."}
    return {"verdict": VERDICT_PAS_CE_MOIS, "fenetres": toutes,
            "prochaine_fenetre": {"action": maintenant["action"], "geste": geste, "fenetre": fenetre},
            "texte": f"Rien à semer ni planter ce mois-ci. Prochaine fenêtre : {geste.lower()} {fenetre}."}
