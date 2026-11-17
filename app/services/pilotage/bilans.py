"""
app/services/pilotage/bilans.py — Le résumé quotidien et le bilan hebdomadaire du pilotage [US-317]
===================================================================================================
Pour suivre la plateforme sans ouvrir le tableau de bord quand tout va bien : un résumé court chaque
matin (Telegram) et un bilan chaque lundi (e-mail).

Règles (testées) :
- **Par gabarit, sans modèle** [CA5] : les textes sont assemblés ici, à partir de `agregats` ; aucune
  ligne `conso_tokens` n'est écrite pendant leur production.
- **Provenances** [CA4] : seuls `usage` et `fond` entrent dans les chiffres ; le volume de `mesure`
  tient sur une ligne à part.
- **Jamais deux fois** [CA8] : la trace `bilans_pilotage` est unique par (type, début de période) ;
  un envoi échoué est rejoué UNE fois (2 tentatives au plus), jamais davantage.
- **Aucun nom, aucun message** [CA9] : que des mesures, des noms de modèle et de type d'appel.
- **Interrupteurs séparés** [CA7] : `PILOTAGE_RESUME_QUOTIDIEN` et `PILOTAGE_BILAN_HEBDO`, éteints par défaut.

Le jour résumé est la VEILLE de l'envoi ; la semaine du bilan est la semaine (lundi→dimanche) qui
précède celui où il part, comparée à la semaine d'avant.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import config
from app.services.pilotage import agregats, cout as svc_cout, notifications, seuils as svc_seuils
from app.services.pilotage.agregats import Filtres, _Cumul, _executer, _filtrer, percentile
from database.models import AlertePilotage, BilanPilotage, ConsoTokens, SeuilPilotage
from llm.passerelle import ISSUE_OK, UNITE_JETON

log = logging.getLogger("potager")

TYPE_QUOTIDIEN = "quotidien"
TYPE_HEBDOMADAIRE = "hebdomadaire"
#: [CA8] Un envoi, un seul rejeu.
MAX_TENTATIVES = 2
JOURS_DE_REFERENCE = 7
TYPE_AGENT = "agent"

_JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")


def _jour(d: date) -> str:
    return f"{_JOURS[d.weekday()]} {d:%d/%m}"


# ─────────────────────────────────────────────────────────────────────────────
# Mesures d'une période
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MesuresPeriode:
    """Ce que le résumé et le bilan lisent d'une période (provenances `usage` et `fond`)."""
    appels: int
    jardiniers_actifs: int
    cout_eur: Optional[float]
    taux_succes: Optional[float]
    latence_p95_agent_ms: Optional[float]
    jetons_mediane_agent: Optional[float]
    appels_par_echange: Optional[float]
    appels_usage: int


def _actifs_par_jour(db: Session, filtres: Filtres) -> dict[date, int]:
    """Jardiniers distincts ayant au moins un appel `usage`, jour par jour."""
    usage = Filtres(depuis=filtres.depuis, jusqu_a=filtres.jusqu_a, provenances=("usage",))
    requete = _filtrer(db.query(ConsoTokens.date, ConsoTokens.user_id), usage).filter(ConsoTokens.user_id.isnot(None)).distinct()
    par_jour: dict[date, int] = {}
    for jour, _ in _executer(db, requete):
        par_jour[jour] = par_jour.get(jour, 0) + 1
    return par_jour


def mesures_periode(db: Session, depuis: date, jusqu_a: date) -> MesuresPeriode:
    filtres = Filtres(depuis=depuis, jusqu_a=jusqu_a)
    cumul = agregats._agreger(db, filtres).get(()) or _Cumul()
    agent = Filtres(depuis=depuis, jusqu_a=jusqu_a, appel_type=TYPE_AGENT)
    latences = svc_seuils._colonne_des_appels_reussis(db, agent, ConsoTokens.latence_ms, jetons_seulement=False)
    entrees = svc_seuils._colonne_des_appels_reussis(db, agent, ConsoTokens.tokens_in, jetons_seulement=True)
    groupes = agregats._agreger(db, filtres, [ConsoTokens.echange_ref])
    par_echange = [c.appels for cle, c in groupes.items() if cle[0]]
    usage = agregats._agreger(db, Filtres(depuis=depuis, jusqu_a=jusqu_a, provenances=("usage",))).get(()) or _Cumul()
    cout = cumul.cout_micro_eur
    return MesuresPeriode(
        appels=cumul.appels,
        jardiniers_actifs=len(svc_cout._jardiniers_actifs(db, filtres)),
        cout_eur=None if cout is None else cout / agregats.MICRO,
        taux_succes=(100.0 * cumul.issues.get(ISSUE_OK, 0) / cumul.appels) if cumul.appels else None,
        latence_p95_agent_ms=percentile(latences, 0.95),
        jetons_mediane_agent=percentile(entrees, 0.5),
        appels_par_echange=percentile(par_echange, 0.5),
        appels_usage=usage.appels,
    )


def volume_mesure(db: Session, depuis: date, jusqu_a: date) -> int:
    """[CA4] Le nombre d'appels de provenance `mesure` (campagnes d'évaluation), donné à part."""
    f = Filtres(depuis=depuis, jusqu_a=jusqu_a, provenances=("mesure",))
    return (agregats._agreger(db, f).get(()) or _Cumul()).appels


def _reference_7_jours(db: Session, jour: date) -> MesuresPeriode:
    """Les 7 jours qui précèdent `jour` : sommes ramenées à un jour moyen, taux et percentiles tels quels."""
    fin = jour - timedelta(days=1)
    debut = fin - timedelta(days=JOURS_DE_REFERENCE - 1)
    brut = mesures_periode(db, debut, fin)
    actifs = _actifs_par_jour(db, Filtres(depuis=debut, jusqu_a=fin))
    moyenne_actifs = sum(actifs.get(debut + timedelta(days=i), 0) for i in range(JOURS_DE_REFERENCE)) / JOURS_DE_REFERENCE
    return MesuresPeriode(
        appels=brut.appels / JOURS_DE_REFERENCE,
        jardiniers_actifs=moyenne_actifs,
        cout_eur=None if brut.cout_eur is None else brut.cout_eur / JOURS_DE_REFERENCE,
        taux_succes=brut.taux_succes,
        latence_p95_agent_ms=brut.latence_p95_agent_ms,
        jetons_mediane_agent=brut.jetons_mediane_agent,
        appels_par_echange=brut.appels_par_echange,
        appels_usage=brut.appels_usage / JOURS_DE_REFERENCE,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mise en forme
# ─────────────────────────────────────────────────────────────────────────────

def _entier(v: float) -> str:
    return svc_seuils._nombre(v)


def _pourcent(v: Optional[float]) -> str:
    """« 98 % » : un taux de succès se lit au point près."""
    return "—" if v is None else f"{svc_seuils._nombre(v, 0)} %"


def _ecart_relatif(valeur: Optional[float], reference: Optional[float]) -> Optional[float]:
    if valeur is None or not reference:
        return None
    return 100.0 * (valeur - reference) / reference


def _texte_ecart(ecart: Optional[float]) -> str:
    return "" if ecart is None else f" ({svc_seuils.formater_ecart(ecart)})"


def _texte_ecart_points(valeur: Optional[float], reference: Optional[float]) -> str:
    if valeur is None or reference is None:
        return ""
    delta = valeur - reference
    return f" ({'+' if delta >= 0 else '−'}{svc_seuils._nombre(abs(delta), 1)} pt)"


def _lignes_chiffres(m: MesuresPeriode, ref: MesuresPeriode, *, libelle_ref: str) -> list[str]:
    """Les six chiffres du résumé, chacun avec son écart à la référence [CA1]."""
    fv = svc_seuils.formater_valeur
    return [
        f"Appels : {_entier(m.appels)}{_texte_ecart(_ecart_relatif(m.appels, ref.appels))}",
        f"Jardiniers actifs : {_entier(m.jardiniers_actifs)}{_texte_ecart(_ecart_relatif(m.jardiniers_actifs, ref.jardiniers_actifs))}",
        f"Coût : {fv('cout_jour', m.cout_eur)}{_texte_ecart(_ecart_relatif(m.cout_eur, ref.cout_eur))}",
        f"Taux de succès : {_pourcent(m.taux_succes)}{_texte_ecart_points(m.taux_succes, ref.taux_succes)}",
        f"Latence P95 de l'agent : {fv('latence_p95', m.latence_p95_agent_ms)}"
        f"{_texte_ecart(_ecart_relatif(m.latence_p95_agent_ms, ref.latence_p95_agent_ms))}",
    ]


def _alertes_ouvertes(db: Session) -> int:
    return db.query(func.count(AlertePilotage.id)).filter(AlertePilotage.resolue_le.is_(None)).scalar() or 0


def lien_vue(vue: str) -> str:
    """[CA6] Le lien vers la vue correspondante de la PWA d'administration."""
    return f"{config.PILOTAGE_URL}/#/{vue}"


# ─────────────────────────────────────────────────────────────────────────────
# Résumé quotidien
# ─────────────────────────────────────────────────────────────────────────────

def resume_quotidien(db: Session, jour: date) -> tuple[str, str]:
    """(sujet, texte) du résumé du `jour` donné, comparé aux 7 jours qui le précèdent [CA1, CA2, CA4, CA6].

    Un jour sans appel d'usage tient en une ligne [CA2]. Le volume de `mesure` est une ligne à part."""
    m = mesures_periode(db, jour, jour)
    sujet = f"Pilotage — {_jour(jour)}"
    mesure = volume_mesure(db, jour, jour)
    ligne_mesure = f"Mesures (hors chiffres) : {_entier(mesure)} appels" if mesure else None

    if m.appels_usage == 0:
        ligne = f"📊 {_jour(jour).capitalize()} : aucun appel d'usage."
        if m.appels:
            ligne = f"📊 {_jour(jour).capitalize()} : aucun appel d'usage ({_entier(m.appels)} appels de fond)."
        lignes = [ligne]
        if ligne_mesure:
            lignes.append(ligne_mesure)
        ouvertes = _alertes_ouvertes(db)
        if ouvertes:
            lignes.append(f"Alertes ouvertes : {ouvertes}")
        lignes.append(f"Voir : {lien_vue('consommation')}")
        return sujet, "\n".join(lignes)

    ref = _reference_7_jours(db, jour)
    lignes = [f"📊 Pilotage — {_jour(jour)} (écart à la moyenne des {JOURS_DE_REFERENCE} jours précédents)"]
    lignes += _lignes_chiffres(m, ref, libelle_ref="7 jours")
    lignes.append(f"Alertes ouvertes : {_alertes_ouvertes(db)}")
    if ligne_mesure:
        lignes.append(ligne_mesure)
    lignes.append(f"Voir : {lien_vue('consommation')}")
    return sujet, "\n".join(lignes)


# ─────────────────────────────────────────────────────────────────────────────
# Bilan hebdomadaire
# ─────────────────────────────────────────────────────────────────────────────

def semaine_du_bilan(aujourd_hui: date) -> tuple[date, date]:
    """La semaine (lundi → dimanche) qui précède celle de `aujourd_hui`."""
    lundi = aujourd_hui - timedelta(days=aujourd_hui.weekday())
    return lundi - timedelta(days=7), lundi - timedelta(days=1)


def _repartition_cout(db: Session, filtres: Filtres, colonne, total: Optional[float]) -> list[str]:
    groupes = agregats._agreger(db, filtres, [colonne])
    lignes = []
    for cle, cumul in groupes.items():
        if cumul.cout_micro_eur is None:
            continue
        lignes.append((cle[0] or agregats.CLE_ABSENTE, cumul.cout_micro_eur / agregats.MICRO))
    lignes.sort(key=lambda l: (-l[1], str(l[0])))
    sortie = []
    for nom, euros in lignes[:8]:
        part = f" · {_entier(100.0 * euros / total)} %" if total else ""
        sortie.append(f"  - {nom} : {svc_seuils.formater_valeur('cout_jour', euros)}{part}")
    return sortie


def _plus_fortes_variations(m: MesuresPeriode, avant: MesuresPeriode) -> list[str]:
    """[CA3] Les 3 indicateurs dont la variation relative est la plus forte."""
    fv = svc_seuils.formater_valeur
    candidats = [
        ("Appels", m.appels, avant.appels, _entier),
        ("Jardiniers actifs", m.jardiniers_actifs, avant.jardiniers_actifs, _entier),
        ("Coût", m.cout_eur, avant.cout_eur, lambda v: fv("cout_jour", v)),
        ("Latence P95 de l'agent", m.latence_p95_agent_ms, avant.latence_p95_agent_ms, lambda v: fv("latence_p95", v)),
        ("Jetons d'entrée médians par appel agent", m.jetons_mediane_agent, avant.jetons_mediane_agent,
         lambda v: fv("jetons_entree_mediane", v)),
        ("Appels par échange", m.appels_par_echange, avant.appels_par_echange, lambda v: fv("appels_par_echange", v)),
    ]
    variations = []
    for nom, valeur, reference, fmt in candidats:
        ecart = _ecart_relatif(valeur, reference)
        if ecart is not None:
            variations.append((abs(ecart), f"  - {nom} : {fmt(valeur)} contre {fmt(reference)} ({svc_seuils.formater_ecart(ecart)})"))
    variations.sort(key=lambda v: -v[0])
    return [ligne for _, ligne in variations[:3]] or ["  - Aucune variation mesurable."]


def _alertes_de_la_semaine(db: Session, debut: date, fin: date) -> list[str]:
    bornes = (datetime.combine(debut, datetime.min.time()), datetime.combine(fin + timedelta(days=1), datetime.min.time()))
    alertes = (
        db.query(AlertePilotage, SeuilPilotage).join(SeuilPilotage, SeuilPilotage.id == AlertePilotage.seuil_id)
        .filter(AlertePilotage.declenchee_le >= bornes[0], AlertePilotage.declenchee_le < bornes[1])
        .order_by(AlertePilotage.declenchee_le).all()
    )
    if not alertes:
        return ["  - Aucune alerte cette semaine."]
    lignes = []
    for alerte, seuil in alertes:
        etat = "résolue" if alerte.resolue_le else "toujours ouverte"
        lignes.append(
            f"  - {alerte.declenchee_le:%d/%m} · {svc_seuils.libelle_indicateur(seuil)} : "
            f"{svc_seuils.formater_valeur(seuil.indicateur, alerte.valeur_mesuree)} ({etat})"
        )
    return lignes


def _versions_livrees(db: Session, debut: date, fin: date) -> list[str]:
    """[CA3] Les versions vues pour la première fois dans la semaine, avec leur médiane de jetons
    d'entrée par appel agent."""
    premieres = _executer(db, db.query(ConsoTokens.version_app, func.min(ConsoTokens.date))
                          .filter(ConsoTokens.version_app.isnot(None)).group_by(ConsoTokens.version_app))
    versions = sorted(v for v, premier in premieres if debut <= premier <= fin)
    if not versions:
        return ["  - Aucune nouvelle version observée."]
    agent = Filtres(depuis=debut, jusqu_a=fin, appel_type=TYPE_AGENT)
    lignes = []
    for version in versions:
        requete = (
            _filtrer(db.query(ConsoTokens.tokens_in), agent)
            .filter(ConsoTokens.version_app == version, ConsoTokens.unite == UNITE_JETON, ConsoTokens.issue == ISSUE_OK)
        )
        mediane = percentile([l[0] or 0 for l in _executer(db, requete)], 0.5)
        lignes.append(f"  - v{version} : {svc_seuils.formater_valeur('jetons_entree_mediane', mediane)} par appel agent")
    return lignes


def bilan_hebdomadaire(db: Session, debut: date, fin: date) -> tuple[str, str]:
    """(sujet, texte) du bilan de la semaine [`debut`, `fin`], comparée à la semaine d'avant [CA3, CA4, CA6]."""
    avant_debut, avant_fin = debut - timedelta(days=7), debut - timedelta(days=1)
    m, avant = mesures_periode(db, debut, fin), mesures_periode(db, avant_debut, avant_fin)
    fv = svc_seuils.formater_valeur
    sujet = f"Bilan hebdomadaire du pilotage — {debut:%d/%m} au {fin:%d/%m}"

    lignes = [f"📈 Bilan du pilotage — semaine du {debut:%d/%m} au {fin:%d/%m} (contre {avant_debut:%d/%m} au {avant_fin:%d/%m})", ""]
    lignes += _lignes_chiffres(m, avant, libelle_ref="semaine précédente")
    lignes.append(f"Semaine précédente : {_entier(avant.appels)} appels · {_entier(avant.jardiniers_actifs)} jardiniers actifs · "
                  f"{fv('cout_jour', avant.cout_eur)}")
    mesure = volume_mesure(db, debut, fin)
    if mesure:
        lignes.append(f"Mesures (hors chiffres) : {_entier(mesure)} appels")

    filtres = Filtres(depuis=debut, jusqu_a=fin)
    lignes += ["", "Répartition du coût par modèle :"] + (_repartition_cout(db, filtres, ConsoTokens.modele, m.cout_eur) or ["  - Aucun appel chiffré."])
    lignes += ["", "Répartition du coût par type d'appel :"] + (_repartition_cout(db, filtres, ConsoTokens.appel_type, m.cout_eur) or ["  - Aucun appel chiffré."])
    if m.cout_eur is not None and m.jardiniers_actifs:
        lignes += ["", f"Coût par jardinier actif : {fv('cout_jour', m.cout_eur / m.jardiniers_actifs)}"]
    lignes += ["", "Les 3 plus fortes variations :"] + _plus_fortes_variations(m, avant)
    lignes += ["", "Alertes de la semaine :"] + _alertes_de_la_semaine(db, debut, fin)
    lignes += ["", "Versions livrées dans la semaine :"] + _versions_livrees(db, debut, fin)
    lignes += ["", f"Voir : {lien_vue('consommation')}"]
    return sujet, "\n".join(lignes)


# ─────────────────────────────────────────────────────────────────────────────
# Envoi, trace, jamais deux fois
# ─────────────────────────────────────────────────────────────────────────────

def trace(db: Session, type_bilan: str, debut: date) -> Optional[BilanPilotage]:
    return db.query(BilanPilotage).filter_by(type=type_bilan, periode_debut=debut).first()


def a_envoyer(db: Session, type_bilan: str, debut: date) -> bool:
    """[CA8] Faux si ce bilan est déjà parti, ou s'il a déjà été tenté `MAX_TENTATIVES` fois."""
    t = trace(db, type_bilan, debut)
    return t is None or (t.statut != "envoye" and t.tentatives < MAX_TENTATIVES)


def envoyer_bilan(db: Session, type_bilan: str, debut: date, fin: date, sujet: str, texte: str, canal: str) -> str:
    """Envoie le bilan sur `canal` et tient la trace. Rend `envoye`, `echoue` ou `deja_traite`.

    Une période n'est jamais envoyée deux fois ; un échec est journalisé et rejoué une seule fois."""
    if not a_envoyer(db, type_bilan, debut):
        return "deja_traite"
    reussi = bool(notifications.diffuser(db, sujet, texte, [canal]))
    ligne = trace(db, type_bilan, debut)
    if ligne is None:
        ligne = BilanPilotage(type=type_bilan, periode_debut=debut, periode_fin=fin, statut="echoue", tentatives=0)
        db.add(ligne)
    ligne.tentatives = (ligne.tentatives or 0) + 1
    ligne.statut = "envoye" if reussi else "echoue"
    ligne.envoye_le = datetime.now() if reussi else ligne.envoye_le
    ligne.erreur = None if reussi else f"échec d'envoi sur {canal}"[:200]
    try:
        db.commit()
    except IntegrityError:  # un autre processus a écrit la trace entre-temps : rien n'est renvoyé
        db.rollback()
        return "deja_traite"
    if reussi:
        log.info("[US-317] bilan %s du %s envoyé (%s)", type_bilan, debut, canal)
        return "envoye"
    log.error("[US-317] bilan %s du %s : échec d'envoi sur %s (tentative %d/%d)", type_bilan, debut, canal,
              ligne.tentatives, MAX_TENTATIVES)
    return "echoue"


def passer(db: Session, maintenant: Optional[datetime] = None) -> dict[str, str]:
    """Ce que le planificateur fait à chaque passage : envoyer ce qui est dû et pas encore parti.

    - résumé quotidien : `PILOTAGE_RESUME_QUOTIDIEN`, à partir de `PILOTAGE_RESUME_HEURE`, pour la veille, par Telegram ;
    - bilan hebdomadaire : `PILOTAGE_BILAN_HEBDO`, le lundi à partir de la même heure, pour la semaine écoulée, par e-mail.

    Le planificateur passe plusieurs fois par heure : un envoi échoué est donc rejoué au passage suivant
    (une fois), un redémarrage du bot n'oublie pas le résumé du jour, et la trace empêche tout doublon."""
    maintenant = maintenant or datetime.now()
    resultat: dict[str, str] = {}
    if maintenant.hour < config.PILOTAGE_RESUME_HEURE:
        return resultat
    aujourd_hui = maintenant.date()

    if config.PILOTAGE_RESUME_QUOTIDIEN:
        veille = aujourd_hui - timedelta(days=1)
        if a_envoyer(db, TYPE_QUOTIDIEN, veille):
            sujet, texte = resume_quotidien(db, veille)
            resultat[TYPE_QUOTIDIEN] = envoyer_bilan(db, TYPE_QUOTIDIEN, veille, veille, sujet, texte, notifications.CANAL_TELEGRAM)

    if config.PILOTAGE_BILAN_HEBDO and aujourd_hui.weekday() == 0:
        debut, fin = semaine_du_bilan(aujourd_hui)
        if a_envoyer(db, TYPE_HEBDOMADAIRE, debut):
            sujet, texte = bilan_hebdomadaire(db, debut, fin)
            resultat[TYPE_HEBDOMADAIRE] = envoyer_bilan(db, TYPE_HEBDOMADAIRE, debut, fin, sujet, texte, notifications.CANAL_EMAIL)
    return resultat
