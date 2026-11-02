"""
tools/mesurer_redaction_signaux.py — La mesure du lot 5 : rédiger un signal, fidèlement [US-267 / CA12]
======================================================================================================
Fait rédiger par le VRAI modèle (type d'appel `compagnon_signal`, celui de
`GROQ_MODEL_COMPAGNON_SIGNAL`, sinon de l'agent) un corpus fixe de signaux — un par
détecteur du veilleur, plus un point du matin groupé — et rend, cas par cas :

* le texte rédigé, ou le motif qui l'a écarté au profit du gabarit (chiffre absent du
  signal, action annoncée comme faite, vide, trop long) ;
* le compte des écritures produites : la rédaction est un appel de chat sans outil, et
  l'outil le VÉRIFIE (appel d'outils ou exécuteur = échec immédiat) — « 0 écriture issue
  d'un signal sans confirmation ».

Critère de sortie du lot 5 (cadrage §7) : rédaction fidèle aux données du signal
(chiffres, noms) ; à relire aussi à l'œil, le ton et les noms ne se contrôlent pas tous
par le code.

⚠️ Sans `--dry-run`, chaque cas est UN appel au modèle (11 cas ; quelques centaines de
jetons d'entrée chacun), compté dans `conso_tokens` sur `--potager`.

Utilisation :
    python tools/mesurer_redaction_signaux.py --dry-run          # les faits envoyés, sans appel
    python tools/mesurer_redaction_signaux.py --potager 1        # la mesure, sur le vrai modèle
    python tools/mesurer_redaction_signaux.py --registre gouailleur --prenom Éric
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services import profil_echange  # noqa: E402
from app.services.compagnon import redaction_signal as redaction  # noqa: E402
from app.services.compagnon.redaction_signal import SignalARediger  # noqa: E402
from app.services.context import TenantContext  # noqa: E402

MAINTENANT = datetime(2026, 10, 30, 18, 5)
DEMAIN = (MAINTENANT + timedelta(days=1)).date().isoformat()
EXPIRE = MAINTENANT + timedelta(days=2)


def _signal(theme: str, cle: str, **donnees) -> SignalARediger:
    return SignalARediger(theme, cle, EXPIRE, donnees)


#: Un cas par détecteur, avec des données de la forme exacte que le veilleur produit.
CAS: tuple[tuple[str, tuple[SignalARediger, ...]], ...] = (
    ("gel (§1.3)", (_signal("meteo", f"gel:{DEMAIN}:parcelle-12", jour=DEMAIN, temp_min=-2.0, parcelle_id=12,
                            parcelle="Planche Est", abri=None, cultures=[
                                {"culture": "laitue", "variete": None, "nb_plants": 6.0, "unite": "plants",
                                 "seuil_c": -1.0}]),)),
    ("canicule", (_signal("meteo", f"canicule:{DEMAIN}:parcelle-3", jour=DEMAIN, temp_max=34.0, seuil_c=32.0,
                          parcelle="Serre", cultures=[{"culture": "tomate", "nb_plants": 8.0, "unite": "plants"}]),)),
    ("fortes pluies", (_signal("meteo", f"pluie:{DEMAIN}", jour=DEMAIN, precipitations_mm=24.0, seuil_mm=20.0),)),
    ("sécheresse", (_signal("suivis", "secheresse:arrosage-du:2026-10-22", dernier_arrosage="2026-10-22",
                            jours_sans_arrosage_min=5, cultures=["courgette", "tomate"]),)),
    ("levée non notée (§1.4)", (_signal("suivis", "levee:lot-14", lot_id="x", numero=14, culture="tomate",
                                        variete="cœur de bœuf", date_semis="2026-10-18", graines_en_attente=24,
                                        duree_levee_max_jours=10, levee_attendue_le="2026-10-28",
                                        jours_depuis_semis=12),)),
    ("repiquage", (_signal("echeances", "repiquer:lot-9", numero=9, culture="chou", variete=None,
                           action="repiquer", du="2026-10-28", au="2026-11-04", en_retard=False),)),
    ("mise en terre en retard", (_signal("echeances", "mettre_en_terre:lot-5", numero=5, culture="salade",
                                         action="mettre_en_terre", du="2026-10-10", au="2026-10-20",
                                         en_retard=True),)),
    ("récolte imminente", (_signal("echeances", "recolte:parcelle-2:radis:2026-09-01", culture="radis",
                                   nb_plants=40.0, unite="plants", parcelle="Planche Nord", type_organe="racine",
                                   age_jours=59, seuil_jours=30, date_plantation="2026-09-01"),)),
    ("semis du mois", (_signal("suggestions", "semis:2026-11", mois="2026-11", total=3, cultures=[
        {"culture": "ail", "phase": "semis_pleine_terre", "mois_debut": 11, "mois_fin": 12, "deja_cultivee": True},
        {"culture": "fève", "phase": "semis_pleine_terre", "mois_debut": 11, "mois_fin": 12, "deja_cultivee": False},
        {"culture": "pois", "phase": "semis_pleine_terre", "mois_debut": 11, "mois_fin": 12, "deja_cultivee": False},
    ]),)),
    ("bilan du dimanche", (_signal("resume", "bilan:2026-S44", du="2026-10-24", au="2026-10-30", nb_gestes=9,
                                   par_type={"arrosage": 5, "recolte": 3, "semis": 1},
                                   recoltes=[{"culture": "radis", "quantite": 1.5, "unite": "kg"}]),)),
)


def _cas_groupe() -> tuple[str, tuple[SignalARediger, ...]]:
    """Le point du matin : trois sujets, une question par sujet."""
    return ("point du matin groupé", CAS[4][1] + CAS[5][1] + CAS[7][1])


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--dry-run", action="store_true", help="afficher les faits envoyés, sans appel au modèle")
    parser.add_argument("--potager", type=int, default=1, help="potager imputé dans conso_tokens")
    parser.add_argument("--prenom", default="Éric")
    parser.add_argument("--registre", default=profil_echange.REGISTRE_DEFAUT, choices=profil_echange.REGISTRES)
    args = parser.parse_args()

    ctx = TenantContext(user_id=None, potager_id=args.potager)
    profil = profil_echange.bloc_prompt(profil_echange.Profil(prenom=args.prenom, registre=args.registre))
    aujourd_hui = MAINTENANT.date()
    fideles, ecartes, ecritures = 0, 0, 0

    def _interdit(*_a, **_k):
        raise AssertionError("une rédaction de signal a tenté une écriture (R8)")

    for nom, signaux in CAS + (_cas_groupe(),):
        print(f"\n━━ {nom} " + "━" * max(0, 60 - len(nom)))
        if args.dry_run:
            print(f"   faits : {redaction.donnees_pour_le_modele(signaux, aujourd_hui)}")
            print(f"   gabarit : {' / '.join(redaction.gabarit(s, aujourd_hui) for s in signaux)}")
            continue
        try:
            with patch("llm.passerelle.appeler_chat_outils", side_effect=_interdit), \
                 patch("app.services.agent.executeurs.executer_plan", side_effect=_interdit):
                texte = redaction._rediger(signaux, ctx, profil, aujourd_hui)
        except AssertionError as e:
            ecritures += 1
            print(f"   ❌ {e}")
            continue
        except Exception as e:  # noqa: BLE001 — une panne compte comme un gabarit
            texte = ""
            print(f"   ⚠️ modèle indisponible : {type(e).__name__}")
        motif = redaction.motif_de_rejet(texte, signaux, aujourd_hui)
        if motif is None:
            fideles += 1
            print(f"   ✅ rédigé :\n      {texte.replace(chr(10), chr(10) + '      ')}")
        else:
            ecartes += 1
            print(f"   ↩️ gabarit ({motif}) — texte du modèle :\n      {texte.replace(chr(10), chr(10) + '      ')}")
    if args.dry_run:
        return 0
    total = fideles + ecartes + ecritures
    print(f"\nRédactions fidèles : {fideles}/{total} · gabarit : {ecartes} · écritures issues d'un signal : {ecritures}")
    return 1 if ecritures else 0


if __name__ == "__main__":
    sys.exit(main())
