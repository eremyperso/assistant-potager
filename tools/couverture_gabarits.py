"""
tools/couverture_gabarits.py — [US-243] Couverture des gabarits sur les questions de données
============================================================================================
Rejoue `tests/corpus/us243_couverture_gabarits.csv` contre le catalogue de
familles de `app.services.reponses_chiffrees` et dit, pour chaque question, si
un gabarit la sert, laquelle, et si c'est la bonne.

Trois issues, jamais confondues :
  - **bien servie** : la famille attendue répond ;
  - **non servie**  : aucune famille ne répond — la question descend à l'agent
    SQL puis au modèle (coût, et réponse approximative) ;
  - **mal servie**  : une AUTRE famille répond. C'est la pire : une réponse
    exacte… à une autre question, donnée avec assurance.

Aucun appel modèle, aucune base PostgreSQL : le jeu de données est un potager
de référence en SQLite mémoire, construit ici et partagé avec le test.

    .\\.venv\\Scripts\\python.exe tools/couverture_gabarits.py
    .\\.venv\\Scripts\\python.exe tools/couverture_gabarits.py --corpus autre.csv
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

RACINE = Path(__file__).resolve().parent.parent
CORPUS_DEFAUT = RACINE / "tests" / "corpus" / "us243_couverture_gabarits.csv"

BIEN, NON, MAL = "bien_servie", "non_servie", "mal_servie"
AUCUNE = "aucune"
STATUT_COUVERT, STATUT_A_COUVRIR = "couvert", "a_couvrir"


@dataclass(frozen=True)
class Resultat:
    question: str
    attendu: str
    statut: str
    obtenu: Optional[str]
    issue: str


def construire_potager_de_reference(db, potager_id: int = 1) -> None:
    """Le potager sur lequel le corpus est rejoué : de quoi résoudre des cultures
    et des parcelles nommées, des caractéristiques renseignées ou non, des variétés
    distinctes et une pépinière."""
    from database.models import CultureConfig, Evenement, Parcelle, Potager, PotagerMembre, User

    annee = datetime.now().year
    # [US-249] Un jardinier (id 1) membre de deux potagers : « Maison », l'actif, et
    # « Jardin partagé ». Un troisième, « Voisin », appartient à un autre compte.
    db.add_all([
        User(id=1, nom="Jardinier"), User(id=2, nom="Voisin"),
        Potager(id=potager_id, nom="Maison", proprietaire_id=1),
        Potager(id=potager_id + 1, nom="Jardin partagé", proprietaire_id=1),
        Potager(id=potager_id + 2, nom="Potager du voisin", proprietaire_id=2),
    ])
    db.flush()
    db.add_all([
        PotagerMembre(user_id=1, potager_id=potager_id, role="owner"),
        PotagerMembre(user_id=1, potager_id=potager_id + 1, role="editor"),
        PotagerMembre(user_id=2, potager_id=potager_id + 2, role="owner"),
    ])
    db.add_all([
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="haricot", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="carotte", type_organe_recolte="végétatif", potager_id=None),
        CultureConfig(nom="fraise", type_organe_recolte="reproducteur", potager_id=None),
    ])
    nord = Parcelle(
        nom="NORD", nom_normalise="nord", potager_id=potager_id, actif=True, est_pepiniere=False,
        type_sol="Argileux", nb_rangs=6, longueur_m=12.0, exposition="sud",
        ensoleillement="plein soleil", paillage=True,
    )
    sud = Parcelle(nom="SUD", nom_normalise="sud", potager_id=potager_id, actif=True, est_pepiniere=False)
    serre = Parcelle(
        nom="Serre", nom_normalise="serre", potager_id=potager_id, actif=True, est_pepiniere=True,
        type_pepiniere="chaude", abri="serre",
    )
    db.add_all([nord, sud, serre])
    db.commit()

    def evt(**champs) -> Evenement:
        return Evenement(potager_id=potager_id, **champs)

    db.add_all([
        evt(date=datetime(annee, 5, 1), type_action="plantation", culture="tomate",
            variete="Cœur de bœuf", quantite=12, unite="plants", parcelle_id=nord.id),
        evt(date=datetime(annee, 5, 1), type_action="plantation", culture="tomate",
            quantite=6, unite="plants", parcelle_id=nord.id),
        evt(date=datetime(annee, 5, 2), type_action="plantation", culture="haricot",
            quantite=30, unite="plants", parcelle_id=nord.id),
        evt(date=datetime(annee, 7, 1), type_action="recolte", culture="haricot", quantite=800, unite="g"),
        evt(date=datetime(annee, 7, 8), type_action="recolte", culture="haricot", quantite=600, unite="g"),
        evt(date=datetime(annee, 5, 3), type_action="plantation", culture="courgette",
            quantite=4, unite="plants", parcelle_id=nord.id),
        evt(date=datetime(annee, 7, 3), type_action="recolte", culture="courgette", quantite=2.5, unite="kg"),
        # Carotte végétative entièrement récoltée : plus aucun pied en place.
        evt(date=datetime(annee, 5, 10), type_action="plantation", culture="carotte",
            quantite=12, unite="plants", parcelle_id=nord.id),
        evt(date=datetime(annee, 8, 1), type_action="recolte", culture="carotte", quantite=12, unite="plants"),
        evt(date=datetime(annee, 3, 4), type_action="semis", culture="fraise",
            quantite=50, unite="graines", nb_graines_semees=50),
        evt(date=datetime(annee, 6, 2), type_action="arrosage", culture="tomate"),
    ])
    db.commit()


def lire_corpus(chemin: Path = CORPUS_DEFAUT) -> list[dict]:
    with open(chemin, encoding="utf-8", newline="") as f:
        return [ligne for ligne in csv.DictReader(f) if (ligne.get("question") or "").strip()]


def rejouer(db, ctx, corpus: list[dict]) -> list[Resultat]:
    """Pour chaque question, la famille que le catalogue choisirait — sans exécuter
    l'agrégation : c'est le CHOIX de la famille qu'on mesure, pas son rendu."""
    from app.services import reponses_chiffrees as rc

    resultats: list[Resultat] = []
    for ligne in corpus:
        question, attendu = ligne["question"].strip(), ligne["attendu"].strip() or AUCUNE
        params = rc._extraire_parametres(db, ctx, question)
        famille = rc._choisir_famille(params)
        obtenu = famille.nom if famille else None
        if obtenu is None:
            issue = BIEN if attendu == AUCUNE else NON
        else:
            issue = BIEN if obtenu == attendu else MAL
        resultats.append(Resultat(question, attendu, ligne.get("statut", STATUT_COUVERT), obtenu, issue))
    return resultats


def taux(resultats: list[Resultat]) -> dict[str, float]:
    """Taux sur les seules questions qui ATTENDENT une famille : un piège « aucune »
    bien tenu ne gonfle pas la couverture. Les mal servies, elles, se comptent
    partout (un piège servi par erreur est une réponse à côté)."""
    attendues = [r for r in resultats if r.attendu != AUCUNE]
    n = len(attendues) or 1
    return {
        BIEN: sum(r.issue == BIEN for r in attendues) / n,
        NON: sum(r.issue == NON for r in attendues) / n,
        MAL: sum(r.issue == MAL for r in resultats) / (len(resultats) or 1),
    }


def construire_session_de_reference():
    """Session SQLite mémoire seedée — jamais de PostgreSQL."""
    # Aucun secret réel : l'outil ne parle ni à Telegram, ni à Groq, ni à PostgreSQL.
    for cle, valeur in (("APP_ENV", "test"), ("TELEGRAM_BOT_TOKEN", "outil"), ("GROQ_API_KEY", "outil"),
                        ("DATABASE_URL", "sqlite:///:memory:"), ("JWT_SECRET", "outil-sans-secret")):
        os.environ.setdefault(cle, valeur)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import database.models  # noqa: F401 — enregistre les tables
    from database.db import Base

    moteur = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=moteur)
    db = sessionmaker(bind=moteur)()
    construire_potager_de_reference(db)
    return db


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="[US-243] Couverture des gabarits de questions de données")
    ap.add_argument("--corpus", type=Path, default=CORPUS_DEFAUT)
    args = ap.parse_args(argv)

    sys.path.insert(0, str(RACINE))
    from app.services.context import TenantContext

    db = construire_session_de_reference()
    try:
        resultats = rejouer(db, TenantContext(user_id=1, potager_id=1, role="owner"), lire_corpus(args.corpus))
    finally:
        db.close()
    t = taux(resultats)
    attendues = [r for r in resultats if r.attendu != AUCUNE]
    print(f"COUVERTURE DES GABARITS — {len(resultats)} questions ({len(attendues)} attendent une famille)")
    print(f"  bien servies : {t[BIEN]:6.1%}")
    print(f"  non servies  : {t[NON]:6.1%}   (descendent à l'agent SQL puis au modèle)")
    print(f"  mal servies  : {t[MAL]:6.1%}   (une AUTRE famille répond)")
    for titre, issue in (("MAL SERVIES", MAL), ("NON SERVIES", NON)):
        lignes = [r for r in resultats if r.issue == issue]
        if lignes:
            print(f"\n— {titre} —")
            for r in lignes:
                print(f"  [{r.statut:9}] attendu={r.attendu:20} obtenu={str(r.obtenu):20} | {r.question}")
    return 1 if any(r.issue == MAL for r in resultats) else 0


if __name__ == "__main__":
    sys.exit(main())
