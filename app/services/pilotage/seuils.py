"""
app/services/pilotage/seuils.py — Les seuils de contrôle du pilotage LLM et leurs alertes [US-316]
===================================================================================================
Un seuil dit « à partir de quand l'administrateur veut être prévenu » : un indicateur (coût du jour,
jetons d'entrée médians, taux d'erreur…), un périmètre (tous les appels ou un type), une fenêtre en
jours, une comparaison (valeur fixe, ou écart en pourcentage aux 7 jours précédents), une valeur et
une gravité. `evaluer` mesure, ouvre ou résout les alertes, et les notifie.

Règles (testées) :
- **Aucun modèle n'est appelé** [CA5] : toutes les mesures sont des lectures de `conso_tokens` par
  `agregats` (provenances `usage` et `fond` seulement) ; l'évaluation n'écrit jamais de ligne de
  consommation.
- **Échantillon** [CA8] : un indicateur mesuré sur moins de `MIN_APPELS` appels dans sa fenêtre ne
  déclenche rien — et ne résout rien : on ne sait pas.
- **Une alerte ouverte n'est pas renvoyée** [CA7] : au plus une alerte ouverte par seuil (index
  partiel). Le retour à la normale part une fois ; une gravité haute rappelle chaque jour.
- **Un canal ne retient pas l'autre** [CA9] : un canal en échec n'est pas inscrit dans
  `canaux_notifies` ; il est réessayé au passage suivant.
- **`PILOTAGE_ALERTES=non`** [CA11] : tout est évalué et journalisé, rien ne part.
- **Aucun contenu de jardinier** [CA12] : les messages ne portent que des mesures et un lien.
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.services.pilotage import agregats, cout as svc_cout, notifications
from app.services.pilotage.agregats import Filtres, _Cumul, _executer, _filtrer, percentile
from database.models import AlertePilotage, ConsoTokens, SeuilPilotage
from llm.passerelle import ISSUE_ERREUR, ISSUE_OK, ISSUE_QUOTA, UNITE_JETON

log = logging.getLogger("potager")

#: [CA8] En dessous, la valeur d'une fenêtre ne dit rien : aucune alerte.
MIN_APPELS = 20
#: [CA3] La référence d'une comparaison relative : les 7 jours qui précèdent la fenêtre.
JOURS_DE_REFERENCE = 7
#: [CA7] Délai entre deux rappels d'une alerte de gravité haute.
DELAI_RAPPEL = timedelta(hours=24)
#: Les 50 dernières alertes de la vue [CA10].
NB_ALERTES_HISTORIQUE = 50

COMPARAISON_FIXE = "fixe"
COMPARAISON_ECART = "ecart_7j"
COMPARAISONS = (COMPARAISON_FIXE, COMPARAISON_ECART)
GRAVITES = ("haute", "moyenne", "basse")
PERIMETRE_TOUS = "tous"

CANAL_TELEGRAM = "telegram"
CANAL_EMAIL = "email"


class SeuilInvalideError(ValueError):
    """Une modification de seuil refusée (valeur non finie, négative, démesurée…)."""


# ─────────────────────────────────────────────────────────────────────────────
# Les indicateurs surveillables [CA2]
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Indicateur:
    """Ce qu'un seuil peut surveiller.

    - unite    : `eur` | `jetons` | `appels` | `pourcent` | `ms` | `nombre` (celle de la valeur fixe)
    - avec_type: l'indicateur se mesure pour un type d'appel (`agent`…) ; sinon périmètre `tous`
    - additif  : une somme (coût, appels non chiffrés) : sa référence sur 7 jours se ramène à la
                 moyenne quotidienne × la fenêtre ; une médiane, un taux ou un percentile se mesure
                 tel quel sur les 7 jours
    - relatif  : accepte la comparaison `ecart_7j` (la projection de fin de mois n'a pas d'historique)
    - depend_du_cout : n'a de sens que si les appels sont chiffrés (US-309) [CA4]
    - vue      : la vue de la PWA d'administration qui montre l'indicateur [CA6]
    """
    id: str
    libelle: str
    unite: str
    vue: str
    avec_type: bool = False
    additif: bool = False
    relatif: bool = True
    depend_du_cout: bool = False


INDICATEURS: dict[str, Indicateur] = {i.id: i for i in (
    Indicateur("cout_jour", "Coût du jour", "eur", "cout", additif=True, depend_du_cout=True),
    Indicateur("cout_mois_projete", "Coût du mois projeté", "eur", "cout", relatif=False, depend_du_cout=True),
    Indicateur("jetons_entree_mediane", "Jetons d'entrée médians par appel", "jetons", "derives", avec_type=True),
    Indicateur("appels_par_echange", "Appels par échange", "appels", "derives"),
    Indicateur("taux_quota", "Taux de quota", "pourcent", "fiabilite"),
    Indicateur("taux_erreur", "Taux d'erreur", "pourcent", "fiabilite"),
    Indicateur("latence_p95", "Latence P95", "ms", "fiabilite", avec_type=True),
    Indicateur("appels_non_chiffres", "Appels non chiffrés", "nombre", "cout", additif=True, depend_du_cout=True),
)}


#: Les seuils posés au premier passage. Chaque valeur est une PROPOSITION, marquée « à valider » [CA4].
#: (indicateur, périmètre, fenêtre en jours, comparaison, valeur, gravité)
SEUILS_PAR_DEFAUT: tuple[tuple, ...] = (
    ("cout_jour", PERIMETRE_TOUS, 1, COMPARAISON_FIXE, 5.0, "haute"),
    ("cout_mois_projete", PERIMETRE_TOUS, 1, COMPARAISON_FIXE, 100.0, "haute"),
    ("jetons_entree_mediane", "agent", 1, COMPARAISON_ECART, 20.0, "moyenne"),
    ("appels_par_echange", PERIMETRE_TOUS, 1, COMPARAISON_ECART, 30.0, "moyenne"),
    ("taux_quota", PERIMETRE_TOUS, 1, COMPARAISON_FIXE, 5.0, "moyenne"),
    ("taux_erreur", PERIMETRE_TOUS, 1, COMPARAISON_FIXE, 10.0, "haute"),
    ("latence_p95", "agent", 1, COMPARAISON_FIXE, 15000.0, "moyenne"),
    ("appels_non_chiffres", PERIMETRE_TOUS, 1, COMPARAISON_FIXE, 10.0, "basse"),
)


def couts_disponibles() -> bool:
    """[CA4] Vrai si la grille tarifaire (US-309) est chargée : alors seulement les seuils de coût
    sont créés actifs. Une grille absente ou invalide empêche déjà le démarrage ; ce contrôle ne
    protège que l'import (jamais un coût inventé)."""
    try:
        from app.services.pilotage import tarifs
        return bool(tarifs.GRILLE.modeles)
    except Exception:  # noqa: BLE001 — pas de grille : les seuils de coût restent inactifs
        return False


def assurer_seuils_par_defaut(db: Session) -> int:
    """[CA4] Crée les seuils par défaut qui manquent, sans toucher à ceux qui existent (réglés ou non).

    Actifs, sauf ceux qui dépendent du coût tant que la grille tarifaire n'est pas chargée ; tous
    « à valider ». Rend le nombre de seuils créés. Idempotent."""
    existants = {
        (s.indicateur, s.perimetre, s.fenetre_jours, s.comparaison)
        for s in db.query(SeuilPilotage).all()
    }
    chiffre = couts_disponibles()
    crees = 0
    for indicateur, perimetre, fenetre, comparaison, valeur, gravite in SEUILS_PAR_DEFAUT:
        if (indicateur, perimetre, fenetre, comparaison) in existants:
            continue
        actif = chiffre or not INDICATEURS[indicateur].depend_du_cout
        db.add(SeuilPilotage(
            indicateur=indicateur, perimetre=perimetre, fenetre_jours=fenetre, comparaison=comparaison,
            valeur=valeur, gravite=gravite, actif=actif, a_valider=True,
        ))
        crees += 1
    if crees:
        db.commit()
        log.info("[US-316] %d seuil(s) par défaut créé(s) (valeurs à valider)", crees)
    return crees


# ─────────────────────────────────────────────────────────────────────────────
# Mesure
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Mesure:
    """Une valeur d'indicateur sur une fenêtre, et le nombre d'appels qui l'ont produite."""
    valeur: Optional[float]
    nb_appels: int


def _filtres(indicateur: Indicateur, perimetre: str, depuis: date, jusqu_a: date) -> Filtres:
    """Le périmètre de lecture : provenances `usage` et `fond` [CA5], un type d'appel si l'indicateur en porte un."""
    type_appel = perimetre if (indicateur.avec_type and perimetre and perimetre != PERIMETRE_TOUS) else None
    return Filtres(depuis=depuis, jusqu_a=jusqu_a, provenances=agregats.PROVENANCES_PAR_DEFAUT, appel_type=type_appel)


def _colonne_des_appels_reussis(db: Session, filtres: Filtres, colonne, *, jetons_seulement: bool) -> list:
    requete = _filtrer(db.query(colonne), filtres).filter(ConsoTokens.issue == ISSUE_OK)
    if jetons_seulement:
        requete = requete.filter(ConsoTokens.unite == UNITE_JETON)
    return [ligne[0] or 0 for ligne in _executer(db, requete)]


def mesurer(db: Session, indicateur: Indicateur, perimetre: str, depuis: date, jusqu_a: date,
            *, aujourd_hui: Optional[date] = None) -> Mesure:
    """La valeur de `indicateur` sur [`depuis`, `jusqu_a`] et le nombre d'appels de la fenêtre.

    `valeur` est `None` quand l'indicateur n'est pas calculable (aucun appel, aucun appel chiffré)."""
    filtres = _filtres(indicateur, perimetre, depuis, jusqu_a)
    cumul = agregats._agreger(db, filtres).get(()) or _Cumul()
    n = cumul.appels

    if indicateur.id == "cout_jour":
        c = cumul.cout_micro_eur
        return Mesure(None if c is None else c / agregats.MICRO, n)
    if indicateur.id == "cout_mois_projete":
        jour = aujourd_hui or jusqu_a
        mois = svc_cout._cout(db, svc_cout._fenetre_du_mois(filtres, jour))
        sept = svc_cout._cout(db, replace(filtres, depuis=jour - timedelta(days=svc_cout.JOURS_DE_PROJECTION - 1), jusqu_a=jour))
        projection = svc_cout._projection(mois.cout_micro_eur, sept.cout_micro_eur, jour)
        return Mesure(None if projection is None else projection / agregats.MICRO, mois.appels)
    if indicateur.id == "appels_non_chiffres":
        return Mesure(float(n - cumul.lignes_chiffrees) if n else None, n)
    if indicateur.id == "taux_quota":
        return Mesure(100.0 * cumul.issues.get(ISSUE_QUOTA, 0) / n if n else None, n)
    if indicateur.id == "taux_erreur":
        return Mesure(100.0 * cumul.issues.get(ISSUE_ERREUR, 0) / n if n else None, n)
    if indicateur.id == "jetons_entree_mediane":
        entrees = _colonne_des_appels_reussis(db, filtres, ConsoTokens.tokens_in, jetons_seulement=True)
        return Mesure(percentile(entrees, 0.5), n)
    if indicateur.id == "latence_p95":
        latences = _colonne_des_appels_reussis(db, filtres, ConsoTokens.latence_ms, jetons_seulement=False)
        return Mesure(percentile(latences, 0.95), n)
    if indicateur.id == "appels_par_echange":
        groupes = agregats._agreger(db, filtres, [ConsoTokens.echange_ref])
        appels = [c.appels for cle, c in groupes.items() if cle[0]]
        return Mesure(percentile(appels, 0.5), n)
    raise KeyError(indicateur.id)


@dataclass(frozen=True)
class Evaluation:
    """Le verdict d'un seuil à un instant donné.

    `franchi` : `True`/`False`, ou `None` quand le seuil ne peut pas se juger (échantillon sous
    `MIN_APPELS`, valeur non calculable, référence nulle). Un seuil non jugé ne change rien."""
    seuil: SeuilPilotage
    valeur: Optional[float]
    reference: Optional[float]
    ecart_pct: Optional[float]
    nb_appels: int
    franchi: Optional[bool]
    motif: str = ""


def _reference(db: Session, indicateur: Indicateur, perimetre: str, depuis: date, fenetre: int) -> Optional[float]:
    """[CA3] La valeur des 7 jours qui précèdent la fenêtre ; une somme est ramenée à la fenêtre."""
    fin = depuis - timedelta(days=1)
    debut = fin - timedelta(days=JOURS_DE_REFERENCE - 1)
    valeur = mesurer(db, indicateur, perimetre, debut, fin).valeur
    if valeur is None:
        return None
    return valeur / JOURS_DE_REFERENCE * fenetre if indicateur.additif else valeur


def evaluer_seuil(db: Session, seuil: SeuilPilotage, aujourd_hui: Optional[date] = None) -> Evaluation:
    """Mesure le seuil et dit s'il est franchi [CA3, CA8]. N'écrit rien."""
    aujourd_hui = aujourd_hui or datetime.now().date()
    indicateur = INDICATEURS.get(seuil.indicateur)
    if indicateur is None:
        return Evaluation(seuil, None, None, None, 0, None, "indicateur inconnu")
    fenetre = max(1, int(seuil.fenetre_jours or 1))
    depuis = aujourd_hui - timedelta(days=fenetre - 1)
    mesure = mesurer(db, indicateur, seuil.perimetre, depuis, aujourd_hui, aujourd_hui=aujourd_hui)

    if mesure.nb_appels < MIN_APPELS:
        return Evaluation(seuil, mesure.valeur, None, None, mesure.nb_appels, None, "échantillon insuffisant")
    if mesure.valeur is None:
        return Evaluation(seuil, None, None, None, mesure.nb_appels, None, "valeur non calculable")

    if seuil.comparaison == COMPARAISON_ECART:
        if not indicateur.relatif:
            return Evaluation(seuil, mesure.valeur, None, None, mesure.nb_appels, None, "comparaison relative non prise en charge")
        reference = _reference(db, indicateur, seuil.perimetre, depuis, fenetre)
        if not reference:
            return Evaluation(seuil, mesure.valeur, reference, None, mesure.nb_appels, None, "aucune référence sur les 7 jours précédents")
        ecart = 100.0 * (mesure.valeur - reference) / reference
        return Evaluation(seuil, mesure.valeur, reference, ecart, mesure.nb_appels, ecart > seuil.valeur)

    return Evaluation(seuil, mesure.valeur, None, None, mesure.nb_appels, mesure.valeur > seuil.valeur)


# ─────────────────────────────────────────────────────────────────────────────
# Mise en forme (partagée par les messages et par l'API)
# ─────────────────────────────────────────────────────────────────────────────

def _nombre(valeur: float, decimales: int = 0) -> str:
    """Nombre à la française : espace pour les milliers, virgule décimale."""
    return f"{valeur:,.{decimales}f}".replace(",", " ").replace(".", ",")


def formater_valeur(indicateur_id: str, valeur: Optional[float]) -> str:
    """La valeur d'un indicateur dans son unité : « 8 900 jetons », « 5,00 € », « 12,5 % »."""
    if valeur is None:
        return "—"
    unite = INDICATEURS[indicateur_id].unite if indicateur_id in INDICATEURS else "nombre"
    if unite == "eur":
        return f"{_nombre(valeur, 2)} €"
    if unite == "jetons":
        return f"{_nombre(valeur)} jetons"
    if unite == "pourcent":
        return f"{_nombre(valeur, 1)} %"
    if unite == "ms":
        return f"{_nombre(valeur)} ms"
    if unite == "appels":
        return f"{_nombre(valeur, 1)} appels"
    return _nombre(valeur)


def formater_ecart(ecart: Optional[float]) -> str:
    """« +48 % » : un écart en pourcentage, signé, sans décimale."""
    if ecart is None:
        return "—"
    return f"{'+' if ecart >= 0 else '−'}{_nombre(abs(ecart))} %"


def libelle_indicateur(seuil: SeuilPilotage) -> str:
    """« Jetons d'entrée médians par appel (agent) »."""
    indicateur = INDICATEURS.get(seuil.indicateur)
    nom = indicateur.libelle if indicateur else seuil.indicateur
    if indicateur and indicateur.avec_type and seuil.perimetre != PERIMETRE_TOUS:
        return f"{nom} ({seuil.perimetre})"
    return nom


def texte_fenetre(seuil: SeuilPilotage) -> str:
    n = int(seuil.fenetre_jours or 1)
    if seuil.indicateur == "cout_mois_projete":
        return "mois en cours"
    return "aujourd'hui" if n == 1 else f"{n} derniers jours"


def texte_seuil(seuil: SeuilPilotage) -> str:
    """Le seuil en une phrase : « > 5,00 € » ou « > +20 % par rapport aux 7 jours précédents »."""
    if seuil.comparaison == COMPARAISON_ECART:
        return f"> +{_nombre(seuil.valeur)} % par rapport aux {JOURS_DE_REFERENCE} jours précédents"
    return f"> {formater_valeur(seuil.indicateur, seuil.valeur)}"


def regle_texte(seuil: SeuilPilotage) -> str:
    """La règle en une phrase [CA10] : « plus de 20 % au-dessus de la moyenne des 7 jours précédents »,
    « plus de 5,00 € aujourd'hui »."""
    if seuil.comparaison == COMPARAISON_ECART:
        return f"plus de {_nombre(seuil.valeur)} % au-dessus de la moyenne des {JOURS_DE_REFERENCE} jours précédents"
    fenetre = texte_fenetre(seuil)
    suffixe = {"aujourd'hui": " aujourd'hui", "mois en cours": " sur le mois en cours (projection)"}.get(fenetre, f" sur les {fenetre}")
    return f"plus de {formater_valeur(seuil.indicateur, seuil.valeur)}{suffixe}"


def lien_vue(seuil: SeuilPilotage) -> str:
    """[CA6] Le lien vers la vue de la PWA d'administration qui montre cet indicateur."""
    indicateur = INDICATEURS.get(seuil.indicateur)
    return f"{config.PILOTAGE_URL}/#/{indicateur.vue if indicateur else 'seuils'}"


def _libelle_gravite(gravite: str) -> str:
    return {"haute": "haute", "moyenne": "moyenne", "basse": "basse"}.get(gravite, gravite)


def _lignes_alerte(seuil: SeuilPilotage, valeur: Optional[float], reference: Optional[float],
                   ecart: Optional[float], nb_appels: int) -> list[str]:
    """Les lignes communes d'une alerte, d'un rappel et d'un retour à la normale : que des mesures."""
    mesure = formater_valeur(seuil.indicateur, valeur)
    if seuil.comparaison == COMPARAISON_ECART and ecart is not None:
        mesure = f"{mesure} ({formater_ecart(ecart)} par rapport à {formater_valeur(seuil.indicateur, reference)})"
    return [
        f"Indicateur : {libelle_indicateur(seuil)}",
        f"Valeur mesurée : {mesure}",
        f"Seuil : {texte_seuil(seuil)}",
        f"Fenêtre : {texte_fenetre(seuil)} · {nb_appels} appels",
        f"Gravité : {_libelle_gravite(seuil.gravite)}",
        f"Voir : {lien_vue(seuil)}",
    ]


def message_alerte(seuil: SeuilPilotage, valeur, reference, ecart, nb_appels: int, *, rappel: bool = False,
                   depuis: Optional[datetime] = None) -> tuple[str, str]:
    """(sujet, texte) du message d'ouverture, ou de rappel quotidien, d'une alerte."""
    if rappel:
        quand = f" depuis le {depuis:%d/%m à %H:%M}" if depuis else ""
        titre = f"🔁 Rappel — alerte toujours ouverte{quand}"
        sujet = f"[Pilotage] Rappel : {libelle_indicateur(seuil)}"
    else:
        titre = "🚨 Seuil franchi"
        sujet = f"[Pilotage] Seuil franchi : {libelle_indicateur(seuil)}"
    return sujet, "\n".join([titre, *_lignes_alerte(seuil, valeur, reference, ecart, nb_appels)])


def message_retour(seuil: SeuilPilotage, valeur, reference, ecart, nb_appels: int) -> tuple[str, str]:
    """(sujet, texte) du message de retour à la normale."""
    sujet = f"[Pilotage] Retour à la normale : {libelle_indicateur(seuil)}"
    return sujet, "\n".join(["✅ Retour à la normale", *_lignes_alerte(seuil, valeur, reference, ecart, nb_appels)])


# ─────────────────────────────────────────────────────────────────────────────
# Alertes : ouverture, rappel, résolution
# ─────────────────────────────────────────────────────────────────────────────

def alerte_ouverte(db: Session, seuil_id: int) -> Optional[AlertePilotage]:
    return (
        db.query(AlertePilotage)
        .filter(AlertePilotage.seuil_id == seuil_id, AlertePilotage.resolue_le.is_(None))
        .first()
    )


def _canaux_notifies(alerte: AlertePilotage) -> set[str]:
    return {c for c in (alerte.canaux_notifies or "").split(",") if c}


def _diffuser(db: Session, sujet: str, texte: str, canaux: set[str]) -> set[str]:
    """Envoie sur chacun des `canaux` ; rend ceux qui ont réussi [CA9]. Un canal ne retient jamais l'autre."""
    return notifications.diffuser(db, sujet, texte, canaux)


def _notifier_alerte(db: Session, alerte: AlertePilotage, ev: Evaluation, maintenant: datetime) -> None:
    """Premier envoi (ou réessai d'un canal en échec) puis rappel quotidien d'une gravité haute."""
    seuil = ev.seuil
    configures = notifications.canaux_configures(db)
    manquants = configures - _canaux_notifies(alerte)
    if manquants:
        sujet, texte = message_alerte(seuil, alerte.valeur_mesuree, alerte.valeur_reference,
                                      _ecart(alerte), alerte.nb_appels)
        reussis = _diffuser(db, sujet, texte, manquants)
        if reussis:
            alerte.canaux_notifies = ",".join(sorted(_canaux_notifies(alerte) | reussis))
        for canal in manquants - reussis:
            log.warning("[US-316] alerte %s : canal %s non notifié (réessai au prochain passage)", alerte.id, canal)
        if reussis and alerte.dernier_rappel_le is None:
            alerte.dernier_rappel_le = maintenant
        return
    if seuil.gravite != "haute" or not _canaux_notifies(alerte):
        return
    derniere = alerte.dernier_rappel_le or alerte.declenchee_le
    if maintenant - derniere >= DELAI_RAPPEL:
        sujet, texte = message_alerte(seuil, ev.valeur, ev.reference, ev.ecart_pct, ev.nb_appels,
                                      rappel=True, depuis=alerte.declenchee_le)
        if _diffuser(db, sujet, texte, configures):
            alerte.dernier_rappel_le = maintenant


def _ecart(alerte: AlertePilotage) -> Optional[float]:
    if not alerte.valeur_reference:
        return None
    return 100.0 * (alerte.valeur_mesuree - alerte.valeur_reference) / alerte.valeur_reference


def _appliquer(db: Session, ev: Evaluation, maintenant: datetime, envoi_actif: bool) -> Optional[str]:
    """Fait suivre au cycle de vie de l'alerte le verdict `ev`. Rend `ouverte`, `rappel`, `resolue`
    ou `None` (rien de neuf)."""
    seuil = ev.seuil
    if ev.franchi is None:
        return None
    ouverte = alerte_ouverte(db, seuil.id)
    evenement = None

    if ev.franchi:
        if ouverte is None:
            ouverte = AlertePilotage(
                seuil_id=seuil.id, valeur_mesuree=ev.valeur, valeur_reference=ev.reference,
                nb_appels=ev.nb_appels, declenchee_le=maintenant, canaux_notifies="",
            )
            db.add(ouverte)
            db.flush()
            evenement = "ouverte"
            log.warning("[US-316] ALERTE ouverte — %s : %s (%s)", libelle_indicateur(seuil),
                        formater_valeur(seuil.indicateur, ev.valeur), texte_seuil(seuil))
        if envoi_actif:
            avant = (ouverte.canaux_notifies, ouverte.dernier_rappel_le)
            _notifier_alerte(db, ouverte, ev, maintenant)
            if evenement is None and ouverte.dernier_rappel_le != avant[1] and ouverte.canaux_notifies == avant[0]:
                evenement = "rappel"
    elif ouverte is not None:
        ouverte.resolue_le = maintenant
        evenement = "resolue"
        log.info("[US-316] alerte résolue — %s : %s", libelle_indicateur(seuil), formater_valeur(seuil.indicateur, ev.valeur))
        if envoi_actif and _canaux_notifies(ouverte) and not ouverte.retour_notifie:
            sujet, texte = message_retour(seuil, ev.valeur, ev.reference, ev.ecart_pct, ev.nb_appels)
            if _diffuser(db, sujet, texte, notifications.canaux_configures(db)):
                ouverte.retour_notifie = True
    db.commit()
    return evenement


def evaluer(db: Session, *, maintenant: Optional[datetime] = None) -> list[tuple[Evaluation, Optional[str]]]:
    """[CA5] Évalue tous les seuils actifs ; rend `(verdict, événement)` pour chacun.

    Ne lit que `conso_tokens` et n'appelle aucun modèle. Un seuil qui échoue (base, mesure) n'arrête
    pas les autres. `PILOTAGE_ALERTES` (lu ici, à chaque passage) décide si quelque chose part [CA11]."""
    maintenant = maintenant or datetime.now()
    assurer_seuils_par_defaut(db)
    envoi_actif = bool(config.PILOTAGE_ALERTES)
    resultats: list[tuple[Evaluation, Optional[str]]] = []
    for seuil in db.query(SeuilPilotage).filter(SeuilPilotage.actif.is_(True)).order_by(SeuilPilotage.id).all():
        try:
            ev = evaluer_seuil(db, seuil, maintenant.date())
            resultats.append((ev, _appliquer(db, ev, maintenant, envoi_actif)))
        except Exception as e:  # noqa: BLE001 — un seuil en échec ne retient pas les autres
            db.rollback()
            log.error("[US-316] évaluation du seuil %s en échec : %s", getattr(seuil, "id", "?"), e)
    return resultats


# ─────────────────────────────────────────────────────────────────────────────
# Lecture et modification pour la vue « Seuils » [CA10]
# ─────────────────────────────────────────────────────────────────────────────

ETAT_FRANCHI = "franchi"
ETAT_NORME = "norme"
ETAT_INSUFFISANT = "nodata"
ETAT_INACTIF = "inactif"


def _etat(seuil: SeuilPilotage, ev: Optional[Evaluation]) -> str:
    if not seuil.actif:
        return ETAT_INACTIF
    if ev is None or ev.franchi is None:
        return ETAT_INSUFFISANT
    return ETAT_FRANCHI if ev.franchi else ETAT_NORME


def _seuil_vers_dict(seuil: SeuilPilotage, ouverte: Optional[AlertePilotage], ev: Optional[Evaluation] = None) -> dict:
    """Un seuil pour la vue : sa définition, sa règle en clair, son état courant et ce qui le justifie.

    `valeur_courante`, `reference` et `ecart_courant` permettent à l'écran de dire, avant d'enregistrer,
    si une autre valeur franchirait le seuil « aujourd'hui »."""
    indicateur = INDICATEURS.get(seuil.indicateur)
    return {
        "id": seuil.id,
        "indicateur": seuil.indicateur,
        "libelle": libelle_indicateur(seuil),
        "perimetre": seuil.perimetre,
        "fenetre_jours": seuil.fenetre_jours,
        "fenetre": texte_fenetre(seuil),
        "comparaison": seuil.comparaison,
        "relatif_possible": bool(indicateur and indicateur.relatif),
        "valeur": seuil.valeur,
        "unite": indicateur.unite if indicateur else "nombre",
        "seuil_texte": texte_seuil(seuil),
        "regle": regle_texte(seuil),
        "gravite": seuil.gravite,
        "actif": bool(seuil.actif),
        "a_valider": bool(seuil.a_valider),
        "depend_du_cout": bool(indicateur and indicateur.depend_du_cout),
        "vue": indicateur.vue if indicateur else None,
        "alerte_ouverte_depuis": ouverte.declenchee_le.isoformat() if ouverte else None,
        "etat": _etat(seuil, ev),
        "valeur_courante": ev.valeur if ev else None,
        "valeur_courante_texte": formater_valeur(seuil.indicateur, ev.valeur) if ev and ev.valeur is not None else None,
        "reference": ev.reference if ev else None,
        "ecart_courant": ev.ecart_pct if ev else None,
        "nb_appels": ev.nb_appels if ev else None,
    }


def _alerte_ouverte_vers_dict(alerte: AlertePilotage, seuil: SeuilPilotage) -> dict:
    """[maquette US-318] Le bloc « alertes ouvertes » : mesuré, seuil, depuis quand, lien vers la vue."""
    ecart = _ecart(alerte)
    return {
        "id": alerte.id,
        "seuil_id": seuil.id,
        "libelle": libelle_indicateur(seuil),
        "gravite": seuil.gravite,
        "mesure_texte": formater_valeur(seuil.indicateur, alerte.valeur_mesuree)
        + (f" ({formater_ecart(ecart)})" if ecart is not None else ""),
        "seuil_texte": texte_seuil(seuil),
        "reference_texte": formater_valeur(seuil.indicateur, alerte.valeur_reference) if alerte.valeur_reference else None,
        "declenchee_le": alerte.declenchee_le.isoformat(),
        "vue": INDICATEURS[seuil.indicateur].vue if seuil.indicateur in INDICATEURS else None,
    }


def _alerte_vers_dict(alerte: AlertePilotage, seuil: Optional[SeuilPilotage]) -> dict:
    ecart = _ecart(alerte)
    return {
        "id": alerte.id,
        "seuil_id": alerte.seuil_id,
        "libelle": libelle_indicateur(seuil) if seuil else "Seuil supprimé",
        "gravite": seuil.gravite if seuil else None,
        "valeur_texte": formater_valeur(seuil.indicateur, alerte.valeur_mesuree) if seuil else str(alerte.valeur_mesuree),
        "ecart_texte": formater_ecart(ecart) if ecart is not None else None,
        "seuil_texte": texte_seuil(seuil) if seuil else None,
        "nb_appels": alerte.nb_appels,
        "declenchee_le": alerte.declenchee_le.isoformat(),
        "resolue_le": alerte.resolue_le.isoformat() if alerte.resolue_le else None,
        "canaux_notifies": sorted(_canaux_notifies(alerte)),
    }


def reglages() -> dict:
    """Les interrupteurs et la cadence, tels que la configuration les porte [US-317 / CA7]."""
    return {
        "alertes": bool(config.PILOTAGE_ALERTES),
        "evaluation_minutes": config.PILOTAGE_EVALUATION_MINUTES,
        "resume_quotidien": bool(config.PILOTAGE_RESUME_QUOTIDIEN),
        "resume_heure": config.PILOTAGE_RESUME_HEURE,
        "bilan_hebdomadaire": bool(config.PILOTAGE_BILAN_HEBDO),
    }


def _evaluation_sans_ecriture(db: Session, seuil: SeuilPilotage, aujourd_hui: date) -> Optional[Evaluation]:
    """L'état courant d'un seuil pour l'écran : une mesure en lecture seule, jamais bloquante."""
    try:
        return evaluer_seuil(db, seuil, aujourd_hui)
    except Exception as e:  # noqa: BLE001 — l'écran s'affiche même si une mesure échoue
        log.error("[US-316] mesure du seuil %s pour la vue en échec : %s", seuil.id, e)
        return None


def vue_seuils(db: Session, *, avec_etats: bool = True) -> dict:
    """[CA10] La liste des seuils (avec leur état courant), les alertes ouvertes, les 50 dernières
    alertes et les interrupteurs. `avec_etats=False` saute la mesure de chaque seuil (la pastille de
    la navigation n'a besoin que des alertes ouvertes).

    Ne lit que des seuils, des alertes et `conso_tokens` : aucune donnée de jardinier, aucun modèle,
    aucune écriture hormis la création des seuils par défaut au premier appel."""
    assurer_seuils_par_defaut(db)
    aujourd_hui = datetime.now().date()
    ouvertes = {a.seuil_id: a for a in db.query(AlertePilotage).filter(AlertePilotage.resolue_le.is_(None)).all()}
    seuils = db.query(SeuilPilotage).order_by(SeuilPilotage.id).all()
    par_id = {s.id: s for s in seuils}
    alertes = (
        db.query(AlertePilotage)
        .order_by(AlertePilotage.declenchee_le.desc(), AlertePilotage.id.desc())
        .limit(NB_ALERTES_HISTORIQUE)
        .all()
    )
    configures = notifications.canaux_configures(db)
    return {
        "reglages": reglages(),
        "canaux": {"telegram": CANAL_TELEGRAM in configures, "email": CANAL_EMAIL in configures},
        "seuils": [
            _seuil_vers_dict(s, ouvertes.get(s.id),
                             _evaluation_sans_ecriture(db, s, aujourd_hui) if (s.actif and avec_etats) else None)
            for s in seuils
        ],
        "alertes_ouvertes": [
            _alerte_ouverte_vers_dict(a, par_id[a.seuil_id])
            for a in sorted(ouvertes.values(), key=lambda a: a.declenchee_le, reverse=True) if a.seuil_id in par_id
        ],
        "alertes": [_alerte_vers_dict(a, par_id.get(a.seuil_id)) for a in alertes],
    }


def modifier_seuil(db: Session, seuil_id: int, *, actif: Optional[bool] = None, valeur: Optional[float] = None,
                   comparaison: Optional[str] = None, fenetre_jours: Optional[int] = None,
                   gravite: Optional[str] = None) -> Optional[dict]:
    """[CA10] Active ou désactive un seuil, change sa valeur, sa comparaison, sa fenêtre ou sa gravité.
    `None` si le seuil n'existe pas.

    Changer la valeur vaut validation : le seuil n'est plus « à valider ». Une valeur non finie ou
    négative, une comparaison ou une gravité inconnue, une fenêtre hors de 1 à 31 jours, ou une
    définition qui existe déjà : `SeuilInvalideError`."""
    seuil = db.get(SeuilPilotage, seuil_id)
    if seuil is None:
        return None
    indicateur = INDICATEURS.get(seuil.indicateur)
    if valeur is not None:
        if isinstance(valeur, bool) or not isinstance(valeur, (int, float)) or not math.isfinite(valeur) or valeur < 0:
            raise SeuilInvalideError("la valeur doit être un nombre positif ou nul")
        if valeur > 1e9:
            raise SeuilInvalideError("la valeur est démesurée")
        seuil.valeur = float(valeur)
        seuil.a_valider = False
    if comparaison is not None:
        if comparaison not in COMPARAISONS:
            raise SeuilInvalideError(f"comparaison inconnue : {comparaison}")
        if comparaison == COMPARAISON_ECART and indicateur and not indicateur.relatif:
            raise SeuilInvalideError("cet indicateur ne se compare qu'à une valeur fixe")
        seuil.comparaison = comparaison
    if gravite is not None:
        if gravite not in GRAVITES:
            raise SeuilInvalideError(f"gravité inconnue : {gravite}")
        seuil.gravite = gravite
    if fenetre_jours is not None:
        if isinstance(fenetre_jours, bool) or not isinstance(fenetre_jours, int) or not 1 <= fenetre_jours <= 31:
            raise SeuilInvalideError("la fenêtre va de 1 à 31 jours")
        seuil.fenetre_jours = fenetre_jours
    if actif is not None:
        seuil.actif = bool(actif)
    seuil.modifie_le = datetime.now()
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise SeuilInvalideError("un seuil identique existe déjà") from e
    ouverte = alerte_ouverte(db, seuil.id)
    ev = _evaluation_sans_ecriture(db, seuil, datetime.now().date()) if seuil.actif else None
    return _seuil_vers_dict(seuil, ouverte, ev)
