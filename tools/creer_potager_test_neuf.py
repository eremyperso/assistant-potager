"""
tools/creer_potager_test_neuf.py — Le potager neuf du jeu d'évaluation [US-336 / CA3]
=====================================================================================
Crée (ou remet dans son état de départ) le compte et le potager de test calqués sur le potager 34 de la mesure du
14/11/2026 : UNE parcelle « planche légumes », 20 m², plein sud, zone océanique, rien en stock, aucun geste, aucun
échange. Le potager neuf du jeu n'est jamais monté à la main dans `potager_test` : on rejoue ce script.

* **rejouable** : un second passage ne recrée rien — il constate le compte et le potager, vide leurs données, et
  remet l'unique parcelle ;
* **jamais sur une vraie base** : le script refuse de tourner si la base visée n'a pas « test » dans son nom
  (SQLite accepté), comme `/reset_test` ;
* il ne touche que le potager du compte d'évaluation, jamais un autre.

Utilisation :
    $env:APP_ENV="test"; python tools/creer_potager_test_neuf.py
    python tools/creer_potager_test_neuf.py --email eval-neuf@test.invalid

Il affiche les numéros à passer au lanceur (`--potager-neuf`, `--utilisateur-neuf`).
"""
from __future__ import annotations

import argparse
import secrets
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

EMAIL = "eval-compagnon-neuf@test.invalid"
NOM_UTILISATEUR = "Jardinier d'évaluation"
NOM_POTAGER = "Potager neuf d'évaluation"
NOM_PARCELLE = "planche légumes"
SUPERFICIE_M2 = 20.0
EXPOSITION = "plein sud"
ZONE_CLIMATIQUE = "oceanique"


class BaseNonTestError(Exception):
    """La base visée n'est pas une base de test : le script ne touche à rien."""


@dataclass(frozen=True)
class PotagerNeuf:
    utilisateur_id: int
    potager_id: int
    parcelle_id: int
    #: Vrai quand le compte ou le potager viennent d'être créés ; faux quand ils existaient et ont été remis à neuf.
    cree: bool
    #: `{table: lignes supprimées}` de la remise à neuf.
    purge: dict


def creer_ou_reinitialiser(db, *, email: str = EMAIL, url_base: Optional[str] = None) -> PotagerNeuf:
    """Le potager neuf dans son état de départ. Idempotent. La session sort de là vidée de ses objets : ne garder
    que les identifiants du résultat."""
    from unittest.mock import patch

    from app.services import auth, mode_test, parcelles, potagers
    from app.services.context import TenantContext
    from database.db import tenant_scope
    from database.models import Potager, User

    # La base écrite, pas la configuration : c'est la connexion de la session qui décide (la config peut être rechargée).
    if not mode_test.base_de_test(url_base or str(db.get_bind().url)):
        raise BaseNonTestError("la base visée n'a pas « test » dans son nom : rien n'est créé, rien n'est vidé")

    cree = False
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = auth.inscrire_utilisateur(db, email, secrets.token_urlsafe(24), nom=NOM_UTILISATEUR)
        user.email_verifie = True
        db.commit()
        cree = True
    potager = (db.query(Potager).filter(Potager.proprietaire_id == user.id, Potager.nom == NOM_POTAGER)
               .order_by(Potager.id).first())
    if potager is None:
        potager = potagers.creer_potager(db, user.id, NOM_POTAGER)
        cree = True
    potager.zone_climatique = ZONE_CLIMATIQUE
    db.commit()

    utilisateur_id, potager_id = user.id, potager.id
    ctx = TenantContext(user_id=utilisateur_id, potager_id=potager_id, role="owner")
    # La remise à zéro de `/reset_test` exige APP_ENV=test ; ce script exige, lui, une base de test (vérifiée plus haut).
    with patch.object(mode_test, "actif", lambda: True):
        with tenant_scope(potager_id):
            purge = mode_test.remettre_a_zero(db, potager_id)
            db.expunge_all()  # la purge a supprimé des lignes que la session croit encore connaître
            parcelle = parcelles.creer_parcelle(db, ctx, NOM_PARCELLE, exposition=EXPOSITION,
                                                superficie_m2=SUPERFICIE_M2)
            db.commit()
            return PotagerNeuf(utilisateur_id, potager_id, parcelle.id, cree, purge)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Crée le potager neuf du jeu d'évaluation (US-336)")
    parser.add_argument("--email", default=EMAIL, help=f"compte d'évaluation (défaut : {EMAIL})")
    args = parser.parse_args(argv)
    from database.db import SessionLocal

    db = SessionLocal()
    try:
        resultat = creer_ou_reinitialiser(db, email=args.email)
    except BaseNonTestError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2
    finally:
        db.close()
    print(f"{'✅ créé' if resultat.cree else '♻️  remis à neuf'} : utilisateur {resultat.utilisateur_id}, "
          f"potager {resultat.potager_id}, parcelle « {NOM_PARCELLE} » ({resultat.parcelle_id})")
    print(f"\nPour le lanceur :\n  --potager-neuf {resultat.potager_id} --utilisateur-neuf {resultat.utilisateur_id}\n"
          f"  (ou JEU_EVAL_POTAGER_NEUF={resultat.potager_id} JEU_EVAL_UTILISATEUR_NEUF={resultat.utilisateur_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
