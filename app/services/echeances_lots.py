"""
app/services/echeances_lots.py — Échéances des lots de pépinière [US-214]
-------------------------------------------------------------------------
La Pépinière ne répond plus à « qu'est-ce que j'ai » mais à « qu'est-ce que je
fais maintenant, et dans quel ordre ». Ce module est le SEUL endroit qui calcule,
pour chaque lot et à une date de référence :

  - le repiquage en godet attendu (semis + délai semis → godet, US-213) ;
  - la mise en terre prévue (semis + délai avant plantation, US-068) ;
  - l'endurcissement (compte à rebours, ou pépinière froide, US-208 / US-211) ;
  - la dormance (rien depuis des semaines, alors qu'il reste des plants) ;
  - l'action suggérée et le rang d'urgence ;

puis le résumé du bandeau : à repiquer, à endurcir, prêts pour le plan, à semer.

Lecture seule (CA10) : aucun geste n'est créé, aucun stock ne change, aucun appel
au modèle. Les écrans (US-215, US-216, US-218) recopient ; ils ne recalculent rien.

Règle d'or (CA3, RT2) : **sans la donnée requise, pas d'échéance** — et la raison
est rendue. Aucune valeur par défaut n'est jamais fabriquée.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from utils.stock import LABEL_VARIETE_NON_PRECISEE, graines_restantes   # [US-212]

from app.services import attributs_culture as svc_attributs
from app.services import stock as svc_stock
from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import plan as svc_plan
from app.services import repartition_rangs as svc_rangs
from app.services.context import TenantContext
from database.models import CultureConfig, FenetreCulturale, ItineraireCultural
from utils.culture_resolve import normaliser_culture

log = logging.getLogger("potager")

# ═════════════════════════════════════════════════════════════════════════════
# Décisions produit — UN bloc, corrigeable en un diff (CA1)
# ═════════════════════════════════════════════════════════════════════════════
#: 🧪 [Arbitrage A11] Durée de l'endurcissement, en jours. Hypothèse à confirmer
#: par le PO (plan des épics § 10) : un test la fige pour qu'elle ne change pas
#: par accident.
DUREE_ENDURCISSEMENT_JOURS = 7

#: 🧪 Jours sans aucun geste au-delà desquels un lot qui a encore des graines ou
#: des godets est dit « dormant » — oublié. Même statut que la durée ci-dessus.
SEUIL_DORMANCE_JOURS = 60

#: 🧪 [US-240 / CA6, P15] Une mise en terre prévue dans ce nombre de jours (ou
#: moins) met l'étiquette « Sortir bientôt ». Même statut que les deux ci-dessus.
SEUIL_SORTIR_BIENTOT_JOURS = 15

# ── Vocabulaire des états ────────────────────────────────────────────────────
ETAT_A_VENIR = "a_venir"            # repiquage / mise en terre : avant la fourchette
ETAT_A_REPIQUER = "a_repiquer"      # repiquage : dans la fourchette
ETAT_EN_RETARD = "en_retard"        # repiquage : après la fin de la fourchette
ETAT_ATTEINTE = "atteinte"          # mise en terre : dans la fourchette
ETAT_DEPASSEE = "depassee"          # mise en terre : après la fin de la fourchette
ETAT_PAS_COMMENCE = "pas_commence"  # endurcissement : le compte à rebours n'a pas démarré
ETAT_EN_COURS = "en_cours"          # endurcissement : J+n sur 7
ETAT_TERMINE = "termine"            # endurcissement : J+7 sur 7 atteint
ETAT_FROIDE = "froide"              # endurcissement : « en pépinière froide »

ACTION_REPIQUER = "repiquer"
ACTION_NOTER_LEVEE = "noter_levee"
ACTION_METTRE_EN_TERRE = "mettre_en_terre"
ACTION_CLOTURER = "cloturer"
LIBELLES_ACTIONS: dict[str, str] = {
    ACTION_REPIQUER: "Repiquer",
    ACTION_NOTER_LEVEE: "Noter la levée",
    ACTION_METTRE_EN_TERRE: "Mettre en terre",
    ACTION_CLOTURER: "Clôturer",
}

# Groupes de l'ordre d'urgence (CA6), du plus pressant au plus calme.
GROUPE_RETARD = 0
GROUPE_A_VENIR = 1
GROUPE_SANS_ECHEANCE = 2
GROUPE_DORMANT = 3

_MOIS_COURTS = (
    "janv.", "févr.", "mars", "avr.", "mai", "juin",
    "juil.", "août", "sept.", "oct.", "nov.", "déc.",
)


# ═════════════════════════════════════════════════════════════════════════════
# Petits outils
# ═════════════════════════════════════════════════════════════════════════════
def _jour(valeur) -> Optional[date]:
    """Un datetime, une date ou un texte ISO ramenés à une date — ou None."""
    if valeur is None:
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur
    try:
        return date.fromisoformat(str(valeur)[:10])
    except ValueError:
        return None


def _fmt_jour(jour: date) -> str:
    return f"{jour.day} {_MOIS_COURTS[jour.month - 1]}"


def _cle_culture(nom: Optional[str]) -> str:
    """Nom de culture comparable : casse, accents et pluriel régulier indifférents."""
    mots = normaliser_culture(nom or "").split()
    return " ".join(m[:-1] if len(m) > 3 and m[-1] in "sx" else m for m in mots)


@dataclass(frozen=True)
class _Fourchette:
    """Une fourchette de dates : jamais une date unique fabriquée (CA2)."""
    debut: date
    fin: date

    @property
    def libelle(self) -> str:
        if self.debut == self.fin:
            return f"le {_fmt_jour(self.debut)}"
        return f"entre le {_fmt_jour(self.debut)} et le {_fmt_jour(self.fin)}"


def _fourchette(depart: Optional[date], duree: Optional[cal.DureeLue]) -> Optional[_Fourchette]:
    """Départ + durée du calendrier ; None dès qu'une des deux manque.

    Une mention libre (« vivace ») n'est pas une durée : elle ne donne aucune date.
    """
    if depart is None or duree is None or duree.jours_min is None:
        return None
    haut = duree.jours_max if duree.jours_max is not None else duree.jours_min
    return _Fourchette(depart + timedelta(days=duree.jours_min), depart + timedelta(days=haut))


def _vide(raison: Optional[str] = None) -> dict:
    """Forme d'une échéance sans objet ou sans donnée : `raison` dit pourquoi (CA3)."""
    return {
        "etat": None, "du": None, "au": None, "dans_jours": None,
        "retard_jours": None, "libelle": None, "periode": None, "raison": raison,
    }


def _avec_fourchette(etat: str, f: _Fourchette, libelle: str, **plus) -> dict:
    sortie = _vide()
    sortie.update(
        etat=etat, du=f.debut.isoformat(), au=f.fin.isoformat(),
        libelle=libelle, periode=f.libelle, **plus,
    )
    return sortie


# ═════════════════════════════════════════════════════════════════════════════
# Délais du calendrier — lus une fois par culture, jamais par lot
# ═════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class _Delais:
    godet: Optional[cal.DureeLue]
    mise_en_terre: Optional[cal.DureeLue]


def _delais_de(db: Session, culture: str, potager_id: Optional[int], cache: dict) -> _Delais:
    """Délais de l'itinéraire par défaut de la culture, mémorisés pour la lecture."""
    cle = _cle_culture(culture)
    if cle not in cache:
        calendrier = cal.lire_calendrier(db, culture, potager_id)
        it = calendrier.itineraires[0] if calendrier.itineraires else None
        cache[cle] = _Delais(
            godet=it.duree(cal.ETAPE_SEMIS_GODET) if it else None,
            mise_en_terre=it.duree(cal.ETAPE_REPIQUAGE) if it else None,
        )
    return cache[cle]


# ═════════════════════════════════════════════════════════════════════════════
# Les échéances d'un lot
# ═════════════════════════════════════════════════════════════════════════════
def _a_des_godets(lot: dict) -> bool:
    return (lot.get("stock_residuel_godet") or 0) > 0


def _a_des_graines(lot: dict) -> bool:
    return graines_restantes(lot) > 0   # [US-212] des levés à repiquer comptent


def _est_epuise(lot: dict) -> bool:
    """Des godets ont existé et il n'en reste aucun, ni aucune graine à lever."""
    return (lot.get("nb_mises_en_godet") or 0) > 0 and not _a_des_godets(lot) and not _a_des_graines(lot)


def _levee_notee(lot: dict) -> bool:
    """Une levée a-t-elle été notée sur ce lot ? (US-212 : `nb_leves` n'est pas None —
    un comptage à zéro est un comptage.) Tant qu'aucune ne l'est, « Noter la levée » reste proposée."""
    return lot.get("nb_leves") is not None


def _repiquage(lot: dict, semis: Optional[date], delais: _Delais, ref: date) -> dict:
    """[Table, ligne 1] Repiquage en godet attendu — tant qu'aucun plant n'est en godet."""
    if (lot.get("nb_mises_en_godet") or 0) > 0 or lot.get("sans_semis_rattache"):
        return _vide()
    if semis is None:
        return _vide("date de semis inconnue")
    f = _fourchette(semis, delais.godet)
    if f is None:
        return _vide(f"délai semis → godet non renseigné pour la culture « {lot.get('culture')} »")
    if ref < f.debut:
        jours = (f.debut - ref).days
        return _avec_fourchette(ETAT_A_VENIR, f, f"Repiquage dans {jours} j", dans_jours=jours)
    if ref <= f.fin:
        return _avec_fourchette(ETAT_A_REPIQUER, f, "À repiquer", dans_jours=0)
    retard = (ref - f.fin).days
    return _avec_fourchette(
        ETAT_EN_RETARD, f, f"Repiquage en retard de {retard} j", retard_jours=retard,
    )


def _fourchette_mise_en_terre(lot: dict, semis: Optional[date], delais: _Delais) -> Optional[_Fourchette]:
    return None if lot.get("sans_semis_rattache") else _fourchette(semis, delais.mise_en_terre)


def _raison_mise_en_terre(lot: dict, semis: Optional[date], delais: _Delais) -> Optional[str]:
    """Pourquoi la mise en terre prévue ne se calcule pas — None quand elle se calcule."""
    if lot.get("sans_semis_rattache") or semis is None:
        return "date de semis inconnue"
    if _fourchette(semis, delais.mise_en_terre) is None:
        return f"délai avant plantation non renseigné pour la culture « {lot.get('culture')} »"
    return None


def _mise_en_terre(lot: dict, semis: Optional[date], delais: _Delais, ref: date) -> dict:
    """[Table, ligne 2] Mise en terre prévue — pour un lot qui a des plants en godet."""
    if not _a_des_godets(lot):
        return _vide()
    f = _fourchette_mise_en_terre(lot, semis, delais)
    if f is None:
        return _vide(_raison_mise_en_terre(lot, semis, delais))
    if ref < f.debut:
        jours = (f.debut - ref).days
        return _avec_fourchette(ETAT_A_VENIR, f, f"Mise en terre dans {jours} j", dans_jours=jours)
    if ref <= f.fin:
        return _avec_fourchette(ETAT_ATTEINTE, f, "Mise en terre à faire", dans_jours=0)
    retard = (ref - f.fin).days
    return _avec_fourchette(
        ETAT_DEPASSEE, f, f"Mise en terre en retard de {retard} j", retard_jours=retard,
    )


def _endurcissement(
    lot: dict, mise_en_terre: Optional[_Fourchette], ref: date, raison_mise_en_terre: Optional[str],
) -> dict:
    """[Table, ligne 3 ; CA4] Endurcissement — A11.

    - pépinière chaude ou de type inconnu : compte à rebours de 7 jours qui finit
      au début de la mise en terre prévue ;
    - pépinière froide : on s'endurcit sur place, pas de compte à rebours ;
    - déplacé vers une pépinière froide : le compte à rebours part du jour du
      déplacement. Une fois ses 7 jours écoulés il n'y a plus rien à compter : le
      lot est « en pépinière froide », endurci.
    """
    sortie = {
        "etat": None, "jour": None, "sur": None, "depuis": None, "dans_jours": None,
        "termine": False, "libelle": None, "raison": None,
    }
    if not _a_des_godets(lot):
        return sortie
    sur = DUREE_ENDURCISSEMENT_JOURS
    emplacement = lot.get("emplacement") or {}

    def _compte(jour: int, depuis: date) -> dict:
        jour = min(jour, sur)                       # CA4 : jamais au-delà de J+7 sur 7
        termine = jour >= sur
        sortie.update(
            etat=ETAT_TERMINE if termine else ETAT_EN_COURS, jour=jour, sur=sur,
            depuis=depuis.isoformat(), termine=termine,
            libelle=f"Endurcissement J+{jour}/{sur}",
        )
        return sortie

    if emplacement.get("type_pepiniere") == "froide":
        # [US-241 / CA8] Une partie d'un lot réparti porte sa propre date d'arrivée.
        depuis = emplacement["depuis"] if "depuis" in emplacement else lot.get("date_deplacement")
        depl = _jour(depuis) if emplacement.get("origine") == "deplacement" else None
        ecoule = (ref - depl).days if depl is not None else None
        if ecoule is not None and ecoule < sur:
            return _compte(max(0, ecoule), depl)
        sortie.update(
            etat=ETAT_FROIDE, termine=ecoule is not None, libelle="en pépinière froide",
            depuis=depl.isoformat() if depl is not None and ecoule is not None else None,
        )
        return sortie

    if mise_en_terre is None:
        sortie["raison"] = raison_mise_en_terre
        return sortie
    debut = mise_en_terre.debut - timedelta(days=sur)
    ecoule = (ref - debut).days
    if ecoule < 0:
        sortie.update(
            etat=ETAT_PAS_COMMENCE, dans_jours=-ecoule, depuis=debut.isoformat(),
            libelle=f"Endurcissement dans {-ecoule} j",
        )
        return sortie
    return _compte(ecoule, debut)


def _dormance(lot: dict, mise_en_terre: Optional[_Fourchette], ref: date) -> dict:
    """[Table, ligne 4 ; CA5] Un lot oublié : des plants à sauver, aucun geste depuis
    `SEUIL_DORMANCE_JOURS`, et une mise en terre prévue dépassée ou inconnue. Un lot
    dont la mise en terre n'est pas encore atteinte n'est jamais dormant."""
    dernier = _jour(lot.get("date_dernier_geste"))
    jours = (ref - dernier).days if dernier is not None else None
    en_attente = mise_en_terre is not None and ref <= mise_en_terre.fin
    dormant = (
        (_a_des_graines(lot) or _a_des_godets(lot))
        and jours is not None and jours >= SEUIL_DORMANCE_JOURS
        and not en_attente
    )
    return {
        "est_dormant": dormant, "jours_sans_geste": jours,
        "dernier_geste": dernier.isoformat() if dernier else None,
        "seuil_jours": SEUIL_DORMANCE_JOURS,
        "libelle": f"Dormant — rien depuis {jours} j" if dormant else None,
    }


def _echeances_du_lot(lot: dict, delais: _Delais, ref: date) -> dict:
    """Toutes les échéances d'un lot, son action suggérée et sa clé d'urgence."""
    semis = _jour(lot.get("date_semis"))
    f_terre = _fourchette_mise_en_terre(lot, semis, delais)
    raison_terre = _raison_mise_en_terre(lot, semis, delais)

    repiquage = _repiquage(lot, semis, delais, ref)
    mise_en_terre = _mise_en_terre(lot, semis, delais, ref)
    endurcissement = _endurcissement(lot, f_terre, ref, raison_terre)
    dormance = _dormance(lot, f_terre, ref)

    # ── Action suggérée : une seule par lot ─────────────────────────────────
    if dormance["est_dormant"]:
        action = ACTION_CLOTURER
    elif repiquage["etat"] in (ETAT_A_REPIQUER, ETAT_EN_RETARD):
        action = ACTION_REPIQUER
    elif (
        endurcissement["etat"] == ETAT_EN_COURS or endurcissement["termine"]
        or mise_en_terre["etat"] in (ETAT_ATTEINTE, ETAT_DEPASSEE)
    ):
        action = ACTION_METTRE_EN_TERRE
    elif _a_des_graines(lot) and repiquage["etat"] == ETAT_A_VENIR and not _levee_notee(lot):
        action = ACTION_NOTER_LEVEE
    else:
        action = None

    # ── Clé d'urgence (CA6) ─────────────────────────────────────────────────
    retards = [
        e["retard_jours"] for e in (repiquage, mise_en_terre)
        if e["etat"] in (ETAT_EN_RETARD, ETAT_DEPASSEE)
    ]
    avant = [e["dans_jours"] for e in (repiquage, mise_en_terre, endurcissement) if e.get("dans_jours") is not None]
    if endurcissement["etat"] == ETAT_EN_COURS:
        avant.append(0)
    numero = lot.get("numero_lot")
    departage = (numero if numero is not None else 10**9, str(lot.get("lot_id") or ""))
    if dormance["est_dormant"]:
        cle = (GROUPE_DORMANT, 0, *departage)
    elif retards:
        cle = (GROUPE_RETARD, -max(retards), *departage)
    elif avant:
        cle = (GROUPE_A_VENIR, min(avant), *departage)
    else:
        cle = (GROUPE_SANS_ECHEANCE, 1 if _est_epuise(lot) else 0, *departage)

    raisons = [
        e["raison"] for e in (repiquage, mise_en_terre, endurcissement) if e.get("raison")
    ]
    return {
        "echeances": {
            "date_reference": ref.isoformat(),
            "repiquage": repiquage,
            "mise_en_terre": mise_en_terre,
            "endurcissement": endurcissement,
            "dormance": dormance,
            # [US-218 / CA3] La fourchette de mise en terre prévue, quel que soit le
            # stade du lot : la frise du Calendrier y arrête la barre d'un lot encore
            # en graines, dont `mise_en_terre` reste vide tant qu'il n'a pas de godet.
            "sortie_prevue": {
                "du": f_terre.debut.isoformat() if f_terre else None,
                "au": f_terre.fin.isoformat() if f_terre else None,
                "raison": raison_terre,
            },
            # Chaque raison une fois : de quoi dire pourquoi une échéance manque.
            "raisons": list(dict.fromkeys(raisons)),
        },
        "action_suggeree": (
            {"code": action, "libelle": LIBELLES_ACTIONS[action]} if action else None
        ),
        "_cle": cle,
    }


# ═════════════════════════════════════════════════════════════════════════════
# Le résumé du bandeau (CA8)
# ═════════════════════════════════════════════════════════════════════════════
def _cultures_a_semer(
    db: Session, potager_id: Optional[int], ref: date, cultures_en_cours: set[str]
) -> list[dict]:
    """
    [CA8] Cultures dont la fenêtre de semis en pépinière de la zone est ouverte à
    `ref` et dont aucun lot n'est en cours.

    « Ouverte » veut dire R1 à son maximum, lue par LA MÊME évaluation que la
    confiance (US-178) : le mois adjacent ne suffit pas. Une présélection SQL
    écarte les cultures sans fenêtre ce mois-ci avant d'évaluer ; elle ne tranche
    jamais — elle ne fait que limiter le nombre d'évaluations, et la météo n'est
    lue qu'une fois, pour toutes (CA9).
    """
    candidates: dict[str, tuple[int, int]] = {}
    for nom, debut, fin in _fenetres_semis_pepiniere(db, potager_id)[1]:
        if ref.month in cal.mois_couverts(debut, fin) and _cle_culture(nom) not in cultures_en_cours:
            candidates.setdefault(nom, (debut, fin))
    if not candidates:
        return []
    return _evaluer_a_semer(db, potager_id, ref, candidates)


def _fenetres_semis_pepiniere(
    db: Session, potager_id: Optional[int],
) -> tuple[str, list[tuple[str, int, int]]]:
    """La zone du potager et ses fenêtres de semis en pépinière `(culture, mois_debut,
    mois_fin)`, par ordre de culture — référentiel commun et cultures du potager."""
    zone, _ = cal.zone_du_potager(db, potager_id)
    requete = (
        db.query(CultureConfig.nom, FenetreCulturale.mois_debut, FenetreCulturale.mois_fin)
        .join(ItineraireCultural, ItineraireCultural.culture_id == CultureConfig.id)
        .join(FenetreCulturale, FenetreCulturale.itineraire_id == ItineraireCultural.id)
        .filter(FenetreCulturale.phase == cal.PHASE_SEMIS_PEPINIERE)
        .filter(FenetreCulturale.zone_climatique == zone)
    )
    if potager_id is not None:
        requete = requete.filter(
            or_(CultureConfig.potager_id.is_(None), CultureConfig.potager_id == potager_id),
            or_(ItineraireCultural.potager_id.is_(None), ItineraireCultural.potager_id == potager_id),
        )
    else:
        requete = requete.filter(
            CultureConfig.potager_id.is_(None), ItineraireCultural.potager_id.is_(None),
        )
    fenetres = [
        (nom, debut, fin) for nom, debut, fin in requete.order_by(CultureConfig.nom).all()
        if debut and fin
    ]
    return zone, fenetres


#: [US-218 / maquette HF] Le calendrier de la bande « Le bon moment pour semer » :
#: le mois de référence et les cinq suivants.
NB_MOIS_CALENDRIER_SEMIS = 6


def _calendrier_semis(db: Session, potager_id: Optional[int], ref: date) -> dict:
    """[US-218 / maquette HF] Quand rien n'est à semer, la bande dit quand ça rouvre :
    pour chaque mois, les cultures dont la fenêtre de semis en pépinière **s'ouvre** ce
    mois-là, et combien de celles déjà citées sont **encore ouvertes** ; puis la
    prochaine ouverture. Calculé ici pour que l'écran ne lise aucun calendrier (RT6).
    Une fenêtre est connue au mois : elle s'ouvre le 1er (RT2)."""
    zone, fenetres = _fenetres_semis_pepiniere(db, potager_id)
    par_culture: dict[str, tuple[str, int, int]] = {}
    for nom, debut, fin in fenetres:
        par_culture.setdefault(_cle_culture(nom), (nom, debut, fin))
    mois: list[dict] = []
    citees: set[str] = set()
    prochaine = None
    for decalage in range(NB_MOIS_CALENDRIER_SEMIS):
        annee, numero = ref.year + (ref.month - 1 + decalage) // 12, (ref.month - 1 + decalage) % 12 + 1
        ouvrent = sorted(
            nom for nom, debut, _ in par_culture.values() if debut == numero
        ) if decalage else []
        encore = sum(
            1 for cle, (nom, debut, fin) in par_culture.items()
            if cle in citees and numero in cal.mois_couverts(debut, fin) and debut != numero
        )
        premier = date(annee, numero, 1)
        if ouvrent and prochaine is None:
            prochaine = {"date": premier.isoformat(), "jours": (premier - ref).days}
        mois.append({
            "mois": f"{annee:04d}-{numero:02d}", "libelle": _MOIS_COURTS[numero - 1],
            "dans_jours": (premier - ref).days if decalage else 0,
            "s_ouvrent": ouvrent, "encore_ouvertes": encore,
        })
        citees.update(_cle_culture(n) for n in ouvrent)
    return {
        "zone": cal.LIBELLES_ZONES.get(zone, zone),
        "mois": mois,
        "prochaine_ouverture": prochaine,
    }


def _evaluer_a_semer(
    db: Session, potager_id: Optional[int], ref: date, candidates: dict[str, tuple[int, int]],
) -> list[dict]:
    """[CA8] Les candidates dont la fenêtre est ouverte au sens de la confiance (R1 au maximum)."""
    evaluations = conf.evaluer_cultures(
        db, list(candidates), conf.ACTION_SEMIS_PEPINIERE, ref, potager_id,
    )
    plein = conf.POINTS_MAX[conf.R1_FENETRE]
    a_semer = []
    for nom, evaluation in evaluations.items():
        r1_au_maximum = any(
            m.regle == conf.R1_FENETRE and m.etat == conf.ETAT_GAGNE and m.points >= plein
            for m in evaluation.motifs
        )
        if evaluation.sans_score or not r1_au_maximum:
            continue
        debut, fin = candidates[nom]
        # [US-240 / CA13] Champs AJOUTÉS : `culture` et `fenetre` restent tels quels.
        a_semer.append({
            "culture": nom, "fenetre": cal.formater_fenetre(debut, fin),
            **_bornes_fenetre(debut, fin, ref),
            # [US-220 / CA7, CA8] L'évaluation du moteur, copiée : même niveau que
            # le Plan, la fiche calendrier et le bot, et un niveau par type de
            # pépinière quand le potager en a de froides et d'autres.
            "confiance": _confiance_a_semer(evaluation),
        })
    return a_semer


def _confiance_a_semer(evaluation: conf.Confiance) -> dict:
    """[US-220 / CA7, CA8] Ce que la carte « À semer » affiche du moteur — rien de recalculé."""
    complete = conf.confiance_en_dict(evaluation)
    return {cle: complete[cle] for cle in ("etoiles", "affichage", "score", "pepiniere", "par_pepiniere")}


def _fin_de_mois(annee: int, mois: int) -> date:
    suivant = date(annee + 1, 1, 1) if mois == 12 else date(annee, mois + 1, 1)
    return suivant - timedelta(days=1)


def _bornes_fenetre(mois_debut: int, mois_fin: int, ref: date) -> dict:
    """[US-240 / CA13, P6] Bornes de la fenêtre qui contient `ref`, ses jours restants
    et sa part écoulée.

    La fenêtre est connue au mois : elle s'ouvre le 1er de son premier mois et se
    ferme le dernier jour de son dernier mois — une borne du référentiel, pas une
    estimation (RT2). Une fenêtre à cheval sur l'année (novembre → février) s'ouvre
    l'année de `ref` si `ref` est dans sa partie d'automne, l'année d'avant sinon.
    La part écoulée compte le jour de référence : 1er sept.–31 oct. lu le 19 oct.
    donne 49 / 61 = 0,8.
    """
    annee_debut = ref.year
    if mois_debut > mois_fin and ref.month <= mois_fin:
        annee_debut -= 1
    annee_fin = annee_debut + (1 if mois_debut > mois_fin else 0)
    du, au = date(annee_debut, mois_debut, 1), _fin_de_mois(annee_fin, mois_fin)
    duree = (au - du).days + 1
    return {
        "du": du.isoformat(), "au": au.isoformat(),
        "periode": f"{_fmt_jour_long(du)}–{_fmt_jour_long(au)}",
        "jours_restants": (au - ref).days,
        "part_ecoulee": round(((ref - du).days + 1) / duree, 2),
    }


def _fmt_jour_long(jour: date) -> str:
    """« 1er sept. », « 31 oct. » — le premier du mois s'écrit « 1er »."""
    return f"{'1er' if jour.day == 1 else jour.day} {_MOIS_COURTS[jour.month - 1]}"


@dataclass
class _LecturePlan:
    """[US-217 / CA1] Ce que la Pépinière lit du Plan, UNE fois par lecture."""

    parcelles: list
    repartition: dict
    attributs: dict[str, dict]


def _lire_le_plan(db: Session, ctx: TenantContext, date_ref: Optional[date]) -> _LecturePlan:
    """[US-214 / CA8, US-217 / CA1] La répartition du Plan (US-198), places
    comprises (US-227) — la même que l'écran Plan, jamais recomptée ici. Les
    fiches culture sont lues une fois, pour l'espacement ET l'exposition."""
    parcelles = svc_plan.get_parcelles(db, ctx)
    occupation = svc_plan.get_occupation(db, ctx, date_ref)
    attributs = svc_plan.attributs_par_culture(db, ctx)
    repartition = svc_rangs.repartition_du_plan(
        db, parcelles, occupation, ctx.potager_id, date_ref, attributs_culture=attributs,
    )
    return _LecturePlan(parcelles=parcelles, repartition=repartition, attributs=attributs)


def _rangs_libres(lecture: _LecturePlan) -> list[dict]:
    """[CA8] Rangs libres du Plan par parcelle. Les pépinières n'ont pas de rangs."""
    ordinaires = {p.id for p in lecture.parcelles if not p.est_pepiniere}
    return [
        entree for entree in lecture.repartition["totaux"]["rangs_libres_par_parcelle"]
        if entree["parcelle_id"] in ordinaires
    ]


# ═════════════════════════════════════════════════════════════════════════════
# [US-217] Où mettre en terre les plants d'un lot
# ═════════════════════════════════════════════════════════════════════════════
EXPO_CONCORDE = "concorde"
EXPO_DIFFERE = "differe"
EXPO_NON_COMPARABLE = "non_comparable"

#: [CA6] Trois suggestions dans la fiche, puis « voir toutes les parcelles ».
NB_SUGGESTIONS_VISIBLES = 3

#: [CA4] Dit une fois par la section, jamais remplacé par une estimation.
MENTION_PLANTS_NON_CALCULES = (
    "Le nombre de plants qui tiendront n'est pas calculé : il faut la longueur de "
    "la parcelle et l'espacement de la culture."
)


def _exposition_canonique(valeur: Optional[str]) -> Optional[str]:
    """Plein soleil, mi-ombre ou ombre (US-161) ; toute autre valeur → None."""
    try:
        return svc_attributs.normaliser_valeur("exposition", valeur)
    except svc_attributs.ValeurHorsVocabulaireError:
        return None


#: [US-239 / CA7 bis] L'échelle sur laquelle l'écart se mesure, en crans.
_ECHELLE_ENSOLEILLEMENT: tuple[str, ...] = ("plein soleil", "mi-ombre", "ombre")


def comparer_exposition(
    parcelle: Optional[str], culture: Optional[str], nom_parcelle: Optional[str] = None,
) -> dict:
    """[US-239 / CA7, CA7 bis, CA7 ter, CA8] Compare l'ENSOLEILLEMENT de la
    parcelle à l'exposition de la fiche de la culture (US-161) — l'orientation
    de la parcelle n'entre plus ici.

    Trois issues, jamais supposées : concordante (écart 0), différente (un cran
    d'écart, ou deux : « déconseillé »), non comparable (l'une des deux valeurs
    n'est pas renseignée). `ecart` mesure les crans sur l'échelle plein soleil →
    mi-ombre → ombre ; `rang` en tire l'ordre de la suggestion (0 = la meilleure,
    3 = non comparable). Le libellé dit toujours l'écart en mots.
    """
    p, c = _exposition_canonique(parcelle), _exposition_canonique(culture)
    if p is None or c is None:
        if p is None:
            raison = "ensoleillement de la parcelle non renseigné"
            # [CA8] La phrase à dire au compagnon, pour le déclarer.
            invitation = (
                f"Dites au compagnon : « ensoleillement {nom_parcelle} plein soleil »"
                if nom_parcelle else "Dites au compagnon : « ensoleillement <parcelle> plein soleil »"
            )
        else:
            raison = "exposition de la culture non renseignée"
            invitation = None
        return {
            "comparaison": EXPO_NON_COMPARABLE, "parcelle": p, "culture": c,
            "ecart": None, "deconseille": False, "rang": 3,
            "libelle": raison, "invitation": invitation,
        }
    ecart = abs(_ECHELLE_ENSOLEILLEMENT.index(p) - _ECHELLE_ENSOLEILLEMENT.index(c))
    if ecart == 0:
        return {
            "comparaison": EXPO_CONCORDE, "parcelle": p, "culture": c,
            "ecart": 0, "deconseille": False, "rang": 0, "invitation": None,
            "libelle": f"{p}, comme la culture le demande",
        }
    culture_dite = "d'ombre" if c == "ombre" else f"de {c}"
    phrase = f"{p}, pour une culture {culture_dite}"
    deconseille = ecart >= 2
    return {
        "comparaison": EXPO_DIFFERE, "parcelle": p, "culture": c,
        "ecart": ecart, "deconseille": deconseille, "rang": ecart, "invitation": None,
        "libelle": f"déconseillé : {phrase}" if deconseille else phrase,
    }


def _suggestions_du_lot(lot: dict, lecture: _LecturePlan) -> list[dict]:
    """[CA1-CA3] Les parcelles où mettre ce lot, dans l'ordre de la fiche.

    Lecture pure (CA5) : aucune réservation. Les places (US-227) d'un rang libre
    se calculent par `_places_du_rang`, la règle même de la Vue plan, avec
    l'espacement de la culture DU LOT — jamais un calcul parallèle. Inconnues,
    la suggestion se dit en rangs libres.
    """
    culture = (lot.get("culture") or "").lower()
    attributs = lecture.attributs.get(culture) or {}
    espacement = attributs.get("espacement_rang_cm")
    dispositions = lecture.repartition["dispositions"]

    connues, inconnues = [], []
    for ordre, parcelle in enumerate(lecture.parcelles):
        if parcelle.est_pepiniere:
            continue
        disposition = dispositions.get(parcelle.nom, {})
        libres = disposition.get("rangs_libres")
        if libres == 0:
            continue
        numeros = [r["numero"] for r in disposition.get("rangs", []) if r.get("libre")]
        places_par_rang = svc_rangs._places_du_rang(getattr(parcelle, "longueur_m", None), espacement)
        suggestion = {
            "parcelle_id": parcelle.id,
            "parcelle": parcelle.nom,
            "rangs_libres": libres,
            "numeros_rangs_libres": numeros,
            # [CA7] Un rang n'est pré-rempli que si sa POSITION est connue (US-203,
            # non livrée) : la numérotation d'installation n'en est pas une.
            "premier_rang_libre": (
                numeros[0] if numeros and disposition.get("mode_numerotation")
                != svc_rangs.NUMEROTATION_ORDRE_INSTALLATION else None
            ),
            "places_par_rang": places_par_rang if libres else None,
            "places_libres": places_par_rang * libres if (places_par_rang and libres) else None,
            # [US-239 / CA7] L'ensoleillement, plus l'orientation (`exposition`) :
            # celle-ci reste affichée telle quelle, elle ne se compare plus.
            "exposition": comparer_exposition(
                parcelle.ensoleillement, attributs.get("exposition"), parcelle.nom,
            ),
            "orientation": parcelle.exposition,
            "_ordre": ordre,
        }
        (connues if libres is not None else inconnues).append(suggestion)

    # [US-239 / CA7 bis] La meilleure parcelle d'abord : concordante, puis un
    # cran, puis deux, puis non comparable. À rang égal, le plus de places libres
    # (US-227), sinon le plus de rangs libres, puis l'ordre des parcelles.
    connues.sort(key=lambda s: (
        s["exposition"]["rang"], -(s["places_libres"] or 0), -s["rangs_libres"], s["_ordre"],
    ))
    # [CA3] Rangs inconnus : après, dans l'ordre des parcelles, jamais exclus.
    for s in connues + inconnues:
        s.pop("_ordre")
    return connues + inconnues


def ou_mettre(lot: dict, lecture: Optional[_LecturePlan]) -> Optional[dict]:
    """[CA1, CA4, CA8] La section « Où les mettre » d'un lot ; None sans godet."""
    if lecture is None or not _a_des_godets(lot):
        return None
    suggestions = _suggestions_du_lot(lot, lecture)
    return {
        "suggestions": suggestions,
        "aucun_rang_libre": not any((s["rangs_libres"] or 0) > 0 for s in suggestions),
        "plants_non_calcules": (
            None if any(s["places_libres"] for s in suggestions) else MENTION_PLANTS_NON_CALCULES
        ),
    }


# ═════════════════════════════════════════════════════════════════════════════
# [US-240] Le parcours du plant — étiquettes, compteurs, dormants, à semer
# ═════════════════════════════════════════════════════════════════════════════
# Les colonnes du kanban (P9), dans l'ordre du parcours.
STADE_LEVEE = "levee"
STADE_GODET = "godet"
STADE_ENDURCISSEMENT = "endurcissement"
STADE_PRET = "pret"
STADES = (STADE_LEVEE, STADE_GODET, STADE_ENDURCISSEMENT, STADE_PRET)

# États d'une étiquette (CA6, P15). `a_repiquer` et `a_sortir` sont les deux
# états « dans la fourchette » que la liste de CA6 ne nommait pas : ils comptent
# dans « à repiquer » et « à sortir » sans être des retards.
ETIQ_REPIQUER_RETARD = "repiquer_retard"
ETIQ_A_REPIQUER = "a_repiquer"
ETIQ_SORTIR_RETARD = "sortir_retard"
ETIQ_A_SORTIR = "a_sortir"
ETIQ_SORTIR_BIENTOT = "sortir_bientot"
ETIQ_ENDURCIR = "endurcir"
ETIQ_ENDURCIT_SUR_PLACE = "endurcit_sur_place"
ETIQ_LEVEE_EN_COURS = "levee_en_cours"
ETIQ_EN_COURS = "en_cours"
ETIQ_DUREE_INCONNUE = "duree_inconnue"

ETATS_A_REPIQUER = (ETIQ_REPIQUER_RETARD, ETIQ_A_REPIQUER)
ETATS_A_SORTIR = (ETIQ_SORTIR_RETARD, ETIQ_A_SORTIR, ETIQ_SORTIR_BIENTOT)
ETATS_ENDURCIT = (ETIQ_ENDURCIR, ETIQ_ENDURCIT_SUR_PLACE)

#: [CA13-CA15, provisoire] Il n'existe pas d'inventaire de sachets (reporté à un
#: épic dédié, décision du 19/10/2026) : « des graines en stock » se lit dans les
#: cultures en cours du potager — une variété dont le stock de l'écran Stocks
#: (`calcul_stock_varietes`) est supérieur à zéro. Le front dit cette source.
SOURCE_STOCK_GRAINES = "cultures_en_cours"


def _graines_en_levee(lot: dict) -> int:
    """[CA2] Graines non soldées : ni repiquées, ni soldées par une clôture (déjà hors
    de `graines_restantes`), ni par une levée terminée — les non-levées d'une levée
    terminée ne lèveront plus, seuls les levés restent à repiquer."""
    return graines_restantes(lot)   # les non-levées d'une levée terminée en sont déjà déduites


def _semis_sans_quantite(lot: dict) -> bool:
    """Un semis dont on ne connaît pas le nombre de graines, jamais repiqué ni soldé :
    il est en levée, sans quantité (on ne l'invente pas)."""
    return (
        (lot.get("graines_semees") or 0) <= 0 and (lot.get("nb_mises_en_godet") or 0) == 0
        and not lot.get("sans_semis_rattache") and not lot.get("cloture")
        and not lot.get("levee_terminee")
    )


def _godets_par_emplacement(lot: dict) -> list[tuple[dict, int, Optional[str]]]:
    """[CA3] Les godets disponibles d'un lot, emplacement par emplacement, avec leur
    mention. [US-241 / CA7, CA8] La répartition vient de `repartition_godets`, calculée
    par `calcul_lots_pepiniere` : un lot coupé par un déplacement chiffré y a une entrée
    par pépinière, chacune avec la date d'arrivée de ses godets (`depuis`), d'où part son
    endurcissement. Un lot construit sans ce champ (tests, mocks) a tous ses godets à son
    emplacement courant (US-210)."""
    godets = int(lot.get("stock_residuel_godet") or 0)
    if godets <= 0:
        return []
    if "repartition_godets" not in lot:
        emplacement = lot.get("emplacement") or {}
        deplace = _jour(lot.get("date_deplacement"))
        mention = (
            f"déplacés le {_fmt_jour_long(deplace)}"
            if emplacement.get("origine") == "deplacement" and deplace is not None else None
        )
        return [(emplacement, godets, mention)]
    resultat = []
    for entree in lot["repartition_godets"]:
        depuis = _jour(entree.get("depuis"))
        emplacement = {
            "parcelle_id": entree.get("parcelle_id"), "nom": entree.get("nom"),
            "type_pepiniere": entree.get("type_pepiniere"),
            # `_endurcissement` lit le départ du compte à rebours au froid ici :
            "origine": "deplacement" if depuis is not None else None,
            "depuis": depuis,
        }
        mention = f"déplacés le {_fmt_jour_long(depuis)}" if depuis is not None else None
        resultat.append((emplacement, int(entree["godets"]), mention))
    return resultat


def _echeance(
    jours: Optional[int] = None, en_retard: bool = False, du: Optional[str] = None,
    au: Optional[str] = None, debut_regle: Optional[str] = None, raison: Optional[str] = None,
    libelle: Optional[str] = None, endurcissement: Optional[dict] = None,
) -> dict:
    return {
        "jours": jours, "en_retard": en_retard, "du": du, "au": au,
        "debut_regle": debut_regle, "raison": raison, "libelle": libelle,
        "endurcissement": endurcissement,
    }


def _etiquette_levee(lot: dict, echeances: dict, semis: Optional[str]) -> dict:
    """[CA5-CA8] L'étiquette « en levée » d'un lot qui a des graines non soldées."""
    graines = _graines_en_levee(lot)
    deja = int(lot.get("stock_residuel_godet") or 0)
    repiques = int(lot.get("plants_obtenus") or 0)
    partiel = (lot.get("nb_mises_en_godet") or 0) > 0
    # [P17] Les levés de CE fragment : le dernier comptage fait foi pour tout le lot ;
    # un plant repiqué a forcément levé, on ne garde donc que les levés restés en
    # barquette (« 5 levées parmi les 10 graines restantes »), comme le fait le bot.
    nb_leves = lot.get("nb_leves")
    leves = None if nb_leves is None else (max(0, int(nb_leves) - repiques) if partiel else nb_leves)
    quantites = {
        "graines": graines if graines > 0 else None,
        "leves": leves,
        "godets": None, "unite": lot.get("unite") or "graines",
    }
    mention = None
    if partiel:
        mention = f"{deja} déjà en godet" if deja > 0 else (f"{repiques} déjà repiqués" if repiques else None)
        # [A33, CA7] Les graines restantes d'un lot en partie repiqué n'ont plus
        # d'échéance : rien à attendre d'elles, « Noter la levée (terminée) » les solde.
        return {
            "stade": STADE_LEVEE, "etat": ETIQ_LEVEE_EN_COURS, "quantites": quantites,
            "echeance": _echeance(), "mention": mention, "soldable_par_levee_terminee": True,
        }
    rp = echeances["repiquage"]
    if rp["etat"] == ETAT_EN_RETARD:
        etat, ech = ETIQ_REPIQUER_RETARD, _echeance(jours=rp["retard_jours"], en_retard=True)
    elif rp["etat"] == ETAT_A_REPIQUER:
        etat, ech = ETIQ_A_REPIQUER, _echeance(jours=0)
    elif rp["etat"] == ETAT_A_VENIR:
        etat, ech = ETIQ_LEVEE_EN_COURS, _echeance(jours=rp["dans_jours"])
    else:   # [CA8] sans donnée, pas d'échéance : la raison est rendue
        etat, ech = ETIQ_DUREE_INCONNUE, _echeance(raison=rp["raison"])
    if rp["du"]:
        ech.update(du=rp["du"], au=rp["au"], debut_regle=semis, libelle=rp["libelle"])
    return {
        "stade": STADE_LEVEE, "etat": etat, "quantites": quantites, "echeance": ech,
        "mention": mention, "soldable_par_levee_terminee": False,
    }


def _etiquette_godets(
    lot: dict, echeances: dict, endurcissement: dict, godets: int, mention: Optional[str],
    semis: Optional[str],
) -> dict:
    """[CA5, CA6] L'étiquette des godets d'un lot à UN emplacement : la colonne suit la
    table P9 — la mise en terre atteinte prime sur le type de pépinière."""
    mt, sortie = echeances["mise_en_terre"], echeances["sortie_prevue"]
    fourchette = {"du": sortie["du"], "au": sortie["au"]} if sortie["du"] else {}
    regle = {"debut_regle": semis, **fourchette} if fourchette else {}
    jours_avant = mt.get("dans_jours") if mt["etat"] == ETAT_A_VENIR else None
    if mt["etat"] == ETAT_DEPASSEE:
        stade, etat = STADE_PRET, ETIQ_SORTIR_RETARD
        ech = _echeance(jours=mt["retard_jours"], en_retard=True, **regle)
    elif mt["etat"] == ETAT_ATTEINTE:
        stade, etat, ech = STADE_PRET, ETIQ_A_SORTIR, _echeance(jours=0, **regle)
    elif endurcissement["etat"] == ETAT_FROIDE:
        # [A35] En pépinière froide on s'endurcit sur place, sans compte à rebours.
        stade, etat = STADE_ENDURCISSEMENT, ETIQ_ENDURCIT_SUR_PLACE
        ech = _echeance(jours=jours_avant, raison=sortie["raison"], **regle)
    elif endurcissement["etat"] in (ETAT_EN_COURS, ETAT_TERMINE):
        stade, etat = STADE_ENDURCISSEMENT, ETIQ_ENDURCIR
        ech = _echeance(
            jours=jours_avant, du=fourchette.get("du"), au=fourchette.get("au"),
            debut_regle=endurcissement["depuis"], raison=sortie["raison"],
            endurcissement={"jour": endurcissement["jour"], "sur": endurcissement["sur"]},
        )
    elif mt["etat"] is None:
        stade, etat = STADE_GODET, ETIQ_DUREE_INCONNUE
        ech = _echeance(raison=mt["raison"] or sortie["raison"])
    else:
        stade = STADE_GODET
        etat = ETIQ_SORTIR_BIENTOT if jours_avant <= SEUIL_SORTIR_BIENTOT_JOURS else ETIQ_EN_COURS
        ech = _echeance(jours=jours_avant, **regle)
    ech["libelle"] = mt.get("libelle") if stade != STADE_ENDURCISSEMENT else (
        endurcissement.get("libelle") or mt.get("libelle")
    )
    return {
        "stade": stade, "etat": etat,
        "quantites": {"graines": None, "leves": None, "godets": godets, "unite": "godets"},
        "echeance": ech, "mention": mention, "soldable_par_levee_terminee": False,
    }


def _ou_sont_les_graines(lot: dict, pepinieres: dict[str, int]) -> Optional[int]:
    """[US-211] Les graines restent à la parcelle du semis ; un déplacement (qui porte
    sur le lot entier) les emmène. `graines_emplacement` le dit déjà, par son nom ; un
    lot construit sans ce champ (tests, mocks) retombe sur son emplacement courant."""
    if "graines_emplacement" not in lot:
        return (lot.get("emplacement") or {}).get("parcelle_id")
    return pepinieres.get(lot.get("graines_emplacement"))


def _etiquettes_du_lot(
    lot: dict, calcul: dict, delais: _Delais, ref: date, pepinieres: dict[str, int],
) -> list[dict]:
    """[CA2-CA4] Une étiquette par couple (stade, emplacement) qu'occupe le lot, dans
    l'ordre du parcours (levée d'abord), numérotées « rang sur total ».

    `pepinieres` : identifiant par nom, pour les pépinières du potager."""
    echeances = calcul["echeances"]
    semis_jour = _jour(lot.get("date_semis"))
    semis = semis_jour.isoformat() if semis_jour else None
    ids = set(pepinieres.values())

    def _ou(pid: Optional[int]) -> Optional[int]:
        # [P12] Une pépinière inconnue du potager (non dite, archivée) : « Sans emplacement ».
        return pid if pid in ids else None

    etiquettes: list[dict] = []
    if _graines_en_levee(lot) > 0 or _semis_sans_quantite(lot):
        etiquettes.append({
            **_etiquette_levee(lot, echeances, semis),
            "emplacement_id": _ou(_ou_sont_les_graines(lot, pepinieres)),
        })
    f_terre = _fourchette_mise_en_terre(lot, semis_jour, delais)
    raison_terre = _raison_mise_en_terre(lot, semis_jour, delais)
    for emplacement, godets, mention in _godets_par_emplacement(lot):
        # L'endurcissement dépend du type de LA pépinière où sont ces godets.
        endurcissement = _endurcissement({**lot, "emplacement": emplacement}, f_terre, ref, raison_terre)
        etiquettes.append({
            **_etiquette_godets(lot, echeances, endurcissement, godets, mention, semis),
            "emplacement_id": _ou(emplacement.get("parcelle_id")),
        })

    identite = {
        "id": lot.get("lot_id"), "numero": lot.get("numero_lot"),
        "culture": lot.get("culture"), "variete": lot.get("variete"), "date_semis": semis,
    }
    for rang, etiquette in enumerate(etiquettes, start=1):
        etiquette.update(
            id=f"{lot.get('lot_id')}:{etiquette['stade']}:{etiquette['emplacement_id']}",
            lot=identite, fragment={"rang": rang, "total": len(etiquettes)},
        )
    return etiquettes


def _cle_etiquette(etiquette: dict) -> tuple:
    """[CA9, P22] Ordre d'urgence d'US-214 / CA6, appliqué aux étiquettes : retards du
    plus grand au plus petit, échéances de la plus proche à la plus lointaine, puis
    sans échéance. À égalité : numéro de lot, identifiant, rang du fragment."""
    ech = etiquette["echeance"]
    if ech["en_retard"]:
        groupe = (GROUPE_RETARD, -ech["jours"])
    elif ech["jours"] is not None:
        groupe = (GROUPE_A_VENIR, ech["jours"])
    else:
        groupe = (GROUPE_SANS_ECHEANCE, 0)
    numero = etiquette["lot"]["numero"]
    return (*groupe, numero if numero is not None else 10**9, str(etiquette["lot"]["id"] or ""),
            etiquette["fragment"]["rang"])


def _dormant(lot: dict, dormance: dict, pepinieres: set) -> dict:
    """[CA12, P23-P24] Un lot dormant, hors du kanban : ce qui lui reste et depuis quand."""
    graines = _graines_en_levee(lot)
    godets = int(lot.get("stock_residuel_godet") or 0)
    semis = _jour(lot.get("date_semis"))
    pid = (lot.get("emplacement") or {}).get("parcelle_id")
    return {
        "lot": {
            "id": lot.get("lot_id"), "numero": lot.get("numero_lot"), "culture": lot.get("culture"),
            "variete": lot.get("variete"), "date_semis": semis.isoformat() if semis else None,
        },
        "emplacement_id": pid if pid in pepinieres else None,
        "jours_sans_geste": dormance["jours_sans_geste"],
        "dernier_geste": dormance["dernier_geste"],
        "reste": {
            "graines": graines or None, "godets": godets or None,
            "unite": lot.get("unite") or "graines",
        },
        # [A37] « Mettre en terre » n'est proposé au tiroir que si le lot a des godets.
        "a_des_godets": godets > 0,
    }


def _varietes_en_stock(db: Session, ctx: TenantContext, date_ref: Optional[date]) -> dict[str, list[str]]:
    """[CA15] Variétés « en stock » par culture : lignes de l'écran Stocks dont le stock
    est supérieur à zéro — UNE lecture groupée, la règle existante, rien de recalculé.
    Une culture présente avec une variété non précisée est en stock, sans variété citée."""
    par_culture: dict[str, list[str]] = {}
    for ligne in svc_stock.calcul_stock_varietes(db, ctx, date_ref):
        if (ligne.get("stock_actuel") or 0) <= 0:
            continue
        varietes = par_culture.setdefault(_cle_culture(ligne.get("culture")), [])
        variete = ligne.get("variete")
        if variete and variete != LABEL_VARIETE_NON_PRECISEE and variete not in varietes:
            varietes.append(variete)
    return par_culture


def _parcours(
    db: Session, ctx: TenantContext, lots: list[dict], calculs: dict[str, dict],
    delais_par_lot: dict[str, _Delais], a_semer: list[dict], ref: date, date_ref: Optional[date],
    pepinieres: list[dict],
) -> dict:
    """[US-240] Le bloc `parcours` de `GET /pepiniere/lots` : de quoi dessiner le kanban
    emplacement × stade sans rien recalculer côté écran (RT7)."""
    par_nom = {p["nom"]: p["id"] for p in pepinieres}
    ids_pepinieres = set(par_nom.values())
    etiquettes: list[dict] = []
    dormants: list[dict] = []
    for lot in lots:
        calcul = calculs[lot["lot_id"]]
        dormance = calcul["echeances"]["dormance"]
        if dormance["est_dormant"]:
            dormants.append(_dormant(lot, dormance, ids_pepinieres))
            continue
        etiquettes.extend(_etiquettes_du_lot(lot, calcul, delais_par_lot[lot["lot_id"]], ref, par_nom))
    etiquettes.sort(key=_cle_etiquette)
    # [P24] Du plus ancien geste au plus récent.
    dormants.sort(key=lambda d: (
        -(d["jours_sans_geste"] or 0),
        d["lot"]["numero"] if d["lot"]["numero"] is not None else 10**9,
    ))

    # ── Lignes du kanban (CA10, P10-P12) ────────────────────────────────────
    def _ligne(emplacement_id: Optional[int]) -> dict:
        siennes = [e for e in etiquettes if e["emplacement_id"] == emplacement_id]
        a_venir = [
            e for e in siennes
            if e["quantites"]["godets"] and e["stade"] != STADE_PRET and e["echeance"]["du"]
        ]
        prochaine = min(a_venir, key=lambda e: (e["echeance"]["du"], _cle_etiquette(e)), default=None)
        return {
            "nb_lots": len({e["lot"]["id"] for e in siennes}),
            "nb_etiquettes": len(siennes),
            "nb_alertes": sum(1 for e in siennes if e["echeance"]["en_retard"]),
            # [P10] « Rien à sortir aujourd'hui. Prochain : Poireau #24, le 23 oct. »
            "prochaine_sortie": {
                "lot_numero": prochaine["lot"]["numero"], "culture": prochaine["lot"]["culture"],
                "du": prochaine["echeance"]["du"],
            } if prochaine else None,
        }

    lignes = [
        {"id": p["id"], "nom": p["nom"], "type_pepiniere": p.get("type_pepiniere"),
         "superficie_m2": p.get("superficie_m2"), **_ligne(p["id"])}
        for p in pepinieres
    ]
    sans = _ligne(None)

    # ── À semer, limité aux graines dont on dispose (CA13-CA15, A34) ────────
    varietes = _varietes_en_stock(db, ctx, date_ref) if a_semer else {}
    a_semer_stock, sans_graines = [], []
    for culture in a_semer:
        cle = _cle_culture(culture["culture"])
        if cle in varietes:
            a_semer_stock.append({**culture, "varietes_en_stock": varietes[cle]})
        else:
            sans_graines.append({"culture": culture["culture"]})

    def _compteur(etats: tuple) -> dict:
        sel = [e for e in etiquettes if e["etat"] in etats]
        return {"total": len(sel), "retard": any(e["echeance"]["en_retard"] for e in sel)}

    compteurs = {
        "a_repiquer": _compteur(ETATS_A_REPIQUER),
        "a_sortir": _compteur(ETATS_A_SORTIR),
        "endurcit": _compteur(ETATS_ENDURCIT),
        "a_semer": {"total": len(a_semer_stock), "retard": False},
        "dormants": {"total": len(dormants), "retard": False},
    }
    log.info(
        "[US-240] Parcours : potager=%s date=%s étiquettes=%d dormants=%d à semer=%d "
        "(sans graines=%d) pépinières=%d sans emplacement=%d",
        ctx.potager_id, ref, len(etiquettes), len(dormants), len(a_semer_stock),
        len(sans_graines), len(lignes), sans["nb_etiquettes"],
    )
    return {
        "stades": list(STADES),
        "pepinieres": lignes,
        "sans_emplacement": sans if sans["nb_etiquettes"] else None,
        "etiquettes": etiquettes,
        "compteurs": compteurs,
        "a_semer": a_semer_stock,
        "a_semer_sans_graines": sans_graines,
        "source_stock_graines": SOURCE_STOCK_GRAINES,
        "dormants": dormants,
        # [US-218] Quand ça rouvre — lu seulement quand rien n'est à semer ni replié.
        "calendrier_semis": (
            _calendrier_semis(db, ctx.potager_id, ref) if not (a_semer_stock or sans_graines) else None
        ),
    }


def _pepinieres_du_potager(db: Session, ctx: TenantContext) -> list[dict]:
    """Les pépinières du potager, dans l'ordre des parcelles, vides comprises (CA10)."""
    return [
        {"id": p.id, "nom": p.nom, "superficie_m2": p.superficie_m2, "type_pepiniere": p.type_pepiniere}
        for p in svc_plan.get_parcelles(db, ctx) if p.est_pepiniere
    ]


# ═════════════════════════════════════════════════════════════════════════════
# Point d'entrée
# ═════════════════════════════════════════════════════════════════════════════
def lire_echeances(
    db: Session, ctx: TenantContext, lots: list[dict], date_ref: Optional[date] = None,
    pepinieres: Optional[list[dict]] = None,
) -> dict:
    """
    [CA1-CA10] Échéances, action suggérée et rang d'urgence de chaque lot, plus le
    résumé du bandeau. `lots` est la sortie de `calcul_lots_pepiniere` à la même
    date : rien n'est relu lot par lot, les délais du calendrier le sont par
    culture, et la météo au plus une fois (CA9).

    `date_ref` absent = aujourd'hui. Retourne :

    ```
    {
      "date_reference": "2026-09-19",
      "par_lot": {lot_id: {"echeances": {...}, "action_suggeree": {...}|None,
                           "rang_urgence": 1}},
      "resume":  {"a_repiquer": {...}, "a_endurcir": {...},
                  "prets_pour_le_plan": {...}, "a_semer": {...}},
      "parcours": {...},   # [US-240] le kanban emplacement × stade (`_parcours`)
    }
    ```

    `pepinieres` : celles du potager (`{id, nom, superficie_m2, type_pepiniere}`),
    quand l'appelant les a déjà lues ; sinon elles le sont ici, une fois.
    """
    ref = date_ref or date.today()
    cache: dict = {}
    calculs: dict[str, dict] = {}
    delais_par_lot: dict[str, _Delais] = {}
    for lot in lots:
        delais = _delais_de(db, lot.get("culture") or "", ctx.potager_id, cache)
        delais_par_lot[lot["lot_id"]] = delais
        calculs[lot["lot_id"]] = _echeances_du_lot(lot, delais, ref)

    # Rang : 1 = le plus pressant. Un seul tri, sur la clé calculée plus haut.
    ordre = sorted(calculs, key=lambda lot_id: calculs[lot_id]["_cle"])
    rangs = {lot_id: i + 1 for i, lot_id in enumerate(ordre)}
    # [US-217 / CA1] Le Plan est lu UNE fois pour toute la lecture, et seulement si
    # un lot a des godets : jamais une répartition par lot.
    lecture = _lire_le_plan(db, ctx, date_ref) if any(_a_des_godets(l) for l in lots) else None
    par_id = {lot["lot_id"]: lot for lot in lots}
    par_lot = {
        lot_id: {
            "echeances": c["echeances"], "action_suggeree": c["action_suggeree"],
            "rang_urgence": rangs[lot_id],
            "ou_mettre": ou_mettre(par_id[lot_id], lecture),
        }
        for lot_id, c in calculs.items()
    }

    # ── Résumé ──────────────────────────────────────────────────────────────
    a_repiquer = [
        lot for lot in lots
        if par_lot[lot["lot_id"]]["echeances"]["repiquage"]["etat"] in (ETAT_A_REPIQUER, ETAT_EN_RETARD)
    ]
    a_endurcir = [
        lot for lot in lots
        if par_lot[lot["lot_id"]]["echeances"]["endurcissement"]["etat"] == ETAT_EN_COURS
    ]

    def _pret(lot: dict) -> bool:
        """Des godets, et une mise en terre prévue atteinte ou inconnue."""
        if not _a_des_godets(lot):
            return False
        e = par_lot[lot["lot_id"]]["echeances"]
        if e["mise_en_terre"]["etat"] in (ETAT_ATTEINTE, ETAT_DEPASSEE):
            return True
        return e["mise_en_terre"]["etat"] is None  # inconnue : jamais « pas encore »

    prets = [lot for lot in lots if _pret(lot)]
    plants_prets = sum(int(lot.get("stock_residuel_godet") or 0) for lot in prets)

    cultures_en_cours = {
        _cle_culture(lot.get("culture"))
        for lot in lots
        if (_a_des_godets(lot) or _a_des_graines(lot))
        or ((lot.get("nb_mises_en_godet") or 0) == 0 and not lot.get("sans_semis_rattache"))
    }
    a_semer = _cultures_a_semer(db, ctx.potager_id, ref, cultures_en_cours)

    resume = {
        "a_repiquer": {
            "lots": len(a_repiquer),
            # [US-212] Les plants LEVÉS quand la levée est notée, sinon les graines semées.
            "plants": sum(
                int(lot["nb_leves"] if lot.get("nb_leves") is not None else (lot.get("graines_semees") or 0))
                for lot in a_repiquer
            ),
        },
        "a_endurcir": {"lots": len(a_endurcir)},
        "prets_pour_le_plan": {
            "lots": len(prets),
            "plants": plants_prets,
            # [US-217 / CA10] Les mêmes rangs libres que « Où les mettre ».
            "rangs_libres_par_parcelle": _rangs_libres(lecture) if (prets and lecture) else [],
        },
        "a_semer": {"cultures": a_semer, "total": len(a_semer)},
    }
    log.info(
        "[US-214] Échéances : potager=%s date=%s lots=%d à repiquer=%d à endurcir=%d "
        "prêts=%d (%d plants) à semer=%d",
        ctx.potager_id, ref, len(lots), len(a_repiquer), len(a_endurcir),
        len(prets), plants_prets, len(a_semer),
    )
    parcours = _parcours(
        db, ctx, lots, calculs, delais_par_lot, a_semer, ref, date_ref,
        pepinieres if pepinieres is not None else _pepinieres_du_potager(db, ctx),
    )
    return {"date_reference": ref.isoformat(), "par_lot": par_lot, "resume": resume, "parcours": parcours}


def echeances_d_un_lot(
    db: Session, ctx: TenantContext, lot: dict, date_ref: Optional[date] = None,
) -> dict:
    """[US-216 / CA2] Échéances et action suggérée d'UN lot — de quoi servir sa fiche
    par `GET /pepiniere/lots/{numero}` sans relire la pépinière entière.

    Même calcul que `lire_echeances` (`_echeances_du_lot`), un seul lot : pas de
    résumé de bandeau ni de rang d'urgence, qui se définissent par rapport aux
    autres lots. Les délais du calendrier sont lus pour cette seule culture.
    """
    ref = date_ref or date.today()
    delais = _delais_de(db, lot.get("culture") or "", ctx.potager_id, {})
    calcul = _echeances_du_lot(lot, delais, ref)
    lecture = _lire_le_plan(db, ctx, date_ref) if _a_des_godets(lot) else None
    return {
        "echeances": calcul["echeances"], "action_suggeree": calcul["action_suggeree"],
        # [US-217 / CA6] La fiche ouverte par son numéro porte aussi « Où les mettre ».
        "ou_mettre": ou_mettre(lot, lecture),
    }
