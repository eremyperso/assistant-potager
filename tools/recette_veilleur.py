"""
tools/recette_veilleur.py — Faire passer le veilleur à la main, météo réelle ou simulée [US-266]
==============================================================================================
Outil de recette : il fait tourner le VRAI veilleur (`veilleur_passage.lire_etat`,
`veilleur.detecter`, `signaux.enregistrer`) sur la base de l'environnement courant
(`APP_ENV`), pour un potager ou pour tous les potagers actifs. Il ne contient aucune
logique de détection.

Une seule chose change par rapport au job du bot : la météo peut être SIMULÉE. Les
températures et la pluie viennent d'Open-Meteo et ne se dictent pas ; pour valider
le gel, la canicule, les fortes pluies ou la sécheresse, l'outil remplace la
prévision par un profil choisi (`--meteo gel --valeur -3 --jour 1`). Tout le reste
(cultures en place, rusticités, lots, calendrier, journal) est lu en base.

Par défaut, rien n'est écrit : l'outil affiche l'état lu et les signaux qui seraient
créés. `--ecrire` les enregistre comme le ferait le job (même dédoublonnage).

Utilisation :
    python tools/recette_veilleur.py --potager 3                         # météo douce, lecture seule
    python tools/recette_veilleur.py --potager 3 --meteo gel --valeur -2 # gel demain à -2 °C
    python tools/recette_veilleur.py --potager 3 --meteo gel --ecrire    # … et enregistrer
    python tools/recette_veilleur.py --potager 3 --meteo reelle          # la vraie prévision
    python tools/recette_veilleur.py --potager 3 --bilan --ecrire        # le bilan du dimanche
    python tools/recette_veilleur.py --potager 3 --date 2027-02-15       # « aujourd'hui » décalé
    python tools/recette_veilleur.py --potager 3 --lister                # signaux en base
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import previsions_meteo as svc_previsions  # noqa: E402
from app.services.compagnon import signaux as svc_signaux  # noqa: E402
from app.services.compagnon import veilleur  # noqa: E402
from app.services.compagnon import veilleur_passage as passage  # noqa: E402
from database.db import SessionLocal, tenant_scope  # noqa: E402

PROFILS = ("douce", "gel", "canicule", "pluie", "secheresse", "reelle")
VALEURS_PAR_DEFAUT = {"gel": -2.0, "canicule": 35.0, "pluie": 25.0, "secheresse": 30.0}
NB_JOURS_SIMULES = 6


def prevision_simulee(profil: str, aujourd_hui: date, valeur: float, jour_cible: int) -> svc_previsions.LecturePrevision:
    """Une prévision au format de `utils.meteo` : journée douce partout, sauf ce que le profil change."""
    jours = []
    for i in range(NB_JOURS_SIMULES + 1):
        jour = {"date": (aujourd_hui + timedelta(days=i)).isoformat(),
                "temp_min": 8.0, "temp_max": 16.0, "precipitations": 0.5}
        if profil == "gel" and i == jour_cible:
            jour["temp_min"] = valeur
        elif profil == "canicule" and i == jour_cible:
            jour["temp_max"] = valeur
        elif profil == "pluie" and i == jour_cible:
            jour["precipitations"] = valeur
        elif profil == "secheresse" and i < veilleur.JOURS_CHAUDS_SECHERESSE:
            jour.update(temp_max=valeur, precipitations=0.0)
        jours.append(jour)
    meteo = {**jours[0], "previsions_etendues": [{**j, "horizon_jours": i} for i, j in enumerate(jours) if i]}
    return svc_previsions.LecturePrevision(statut=svc_previsions.STATUT_DISPONIBLE, meteo=meteo, source="simulation")


def _afficher_etat(etat: veilleur.EtatPotager) -> None:
    print(f"\n── Potager {etat.potager_id} · « aujourd'hui » = {etat.aujourd_hui.isoformat()} ──")
    print(f"Cultures en place ({len(etat.cultures)}) :")
    for c in etat.cultures:
        rusticite = f"{c.rusticite_min_c:g} °C" if c.rusticite_min_c is not None else "inconnue"
        print(f"  · {c.culture:<16} {c.nb_plants:g} {c.unite or 'plants':<7} parcelle={c.parcelle_nom or '—':<14}"
              f" (id {c.parcelle_id}) J+{c.age_jours:<4} organe={c.type_organe or '—':<12}"
              f" rusticité={rusticite}{' [semis]' if c.est_semis else ''}")
    print(f"Lots de pépinière ({len(etat.lots)}) :")
    for lot in etat.lots:
        print(f"  · lot {lot.numero if lot.numero is not None else lot.lot_id} {lot.culture:<12}"
              f" semé le {lot.date_semis} action={lot.action or '—'} échéance={lot.echeance_du}→{lot.echeance_au}"
              f" levée notée={'oui' if lot.levee_notee else 'non'} graines en attente={lot.graines_en_attente}"
              f" levée max={lot.duree_levee_max_jours if lot.duree_levee_max_jours is not None else 'inconnue'} j")
    print("Prévisions lues :")
    for j in etat.previsions:
        print(f"  · {j.jour.isoformat()} min={j.temp_min} max={j.temp_max} pluie={j.precipitations} mm")
    arrosages = [g.jour.isoformat() for g in etat.journal if g.type_action == "arrosage"]
    print(f"Journal ({len(etat.journal)} geste(s) sur {passage.JOURS_DE_JOURNAL} j) ; "
          f"arrosages : {', '.join(arrosages) or 'aucun'}")
    ouvrent = sorted({f.culture for f in etat.fenetres_semis if f.mois_debut == etat.aujourd_hui.month})
    print(f"Fenêtres de semis connues : {len(etat.fenetres_semis)} ; s'ouvrent ce mois-ci : "
          f"{', '.join(ouvrent) or 'aucune'}")


def _afficher_signaux(signaux: list[veilleur.Signal]) -> None:
    print(f"\nSignaux détectés ({len(signaux)}) :")
    for s in signaux:
        donnees = json.dumps(s.donnees, ensure_ascii=False)
        print(f"  🔔 [{s.theme}] {s.cle_unique}  priorité={s.priorite}  expire={s.expire_le:%Y-%m-%d %H:%M}")
        print(f"     {donnees[:300]}{'…' if len(donnees) > 300 else ''}")


def _lister(potager_id: int) -> None:
    lignes = svc_signaux.lister(potager_id)
    print(f"\nSignaux en base pour le potager {potager_id} ({len(lignes)}) :")
    for s in lignes:
        print(f"  · {s.detecte_le:%Y-%m-%d %H:%M} [{s.theme}] {s.cle_unique} priorité={s.priorite} "
              f"état={s.etat} expire={s.expire_le:%Y-%m-%d %H:%M}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Recette du veilleur (US-266) : météo réelle ou simulée")
    parser.add_argument("--potager", type=int, help="Identifiant du potager (défaut : tous les potagers actifs)")
    parser.add_argument("--meteo", choices=PROFILS, default="douce", help="Profil de prévision (défaut : douce)")
    parser.add_argument("--valeur", type=float, help="°C pour gel/canicule/sécheresse, mm pour pluie")
    parser.add_argument("--jour", type=int, default=1, help="Jour visé par le profil : 0 = aujourd'hui, 1 = demain…")
    parser.add_argument("--date", help="Décale « aujourd'hui » (AAAA-MM-JJ) pour les fenêtres de semis et le bilan")
    parser.add_argument("--bilan", action="store_true", help="Passe le détecteur du bilan de la semaine")
    parser.add_argument("--ecrire", action="store_true", help="Enregistre les signaux (sinon, lecture seule)")
    parser.add_argument("--lister", action="store_true", help="Liste seulement les signaux déjà en base")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    logging.getLogger("potager").setLevel(logging.INFO if args.ecrire else logging.WARNING)

    potagers = passage.potagers_a_veiller()
    if args.potager is not None:
        potagers = [p for p in potagers if p.id == args.potager]
        if not potagers:
            print(f"❌ Potager {args.potager} introuvable ou non actif (archivé, supprimé).")
            return 1
    if args.lister:
        for p in potagers:
            _lister(p.id)
        return 0

    maintenant = passage.maintenant_local()
    if args.date:
        maintenant = datetime.combine(date.fromisoformat(args.date), maintenant.time())
    detecteurs = veilleur.DETECTEURS_HEBDOMADAIRES if args.bilan else veilleur.DETECTEURS_HORAIRES
    reelles = svc_previsions.lire_previsions_potagers(potagers) if args.meteo == "reelle" else {}
    valeur = args.valeur if args.valeur is not None else VALEURS_PAR_DEFAUT.get(args.meteo, 0.0)
    print(f"Météo : {args.meteo}" + ("" if args.meteo in ("douce", "reelle") else f" ({valeur:g}, jour +{args.jour})")
          + f" · détecteurs : {'bilan' if args.bilan else 'horaires'} · {'ÉCRITURE' if args.ecrire else 'lecture seule'}")

    for p in potagers:
        lecture = reelles.get(p.id) if args.meteo == "reelle" else prevision_simulee(
            args.meteo, maintenant.date(), valeur, args.jour,
        )
        with tenant_scope(p.id):
            db = SessionLocal()
            try:
                etat = passage.lire_etat(db, p, maintenant, lecture)
            finally:
                db.close()
        _afficher_etat(etat)
        signaux = veilleur.detecter(etat, detecteurs)
        _afficher_signaux(signaux)
        if args.ecrire:
            crees = svc_signaux.enregistrer(p.id, signaux, maintenant)
            print(f"\n✍️  {len(crees)} signal(aux) créé(s), {len(signaux) - len(crees)} déjà en base (même fait).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
