"""
tools/evaluer_compagnon.py — Le lanceur commun du jeu d'évaluation [US-336, US-337]
===================================================================================
Joue le MÊME jeu (`tests/corpus/jeu_evaluation_compagnon.json`) sur la chaîne actuelle (`--moteur actuel`), sur la
boucle cible à capacités (`--moteur capacites`, le prototype du 14/11 versé au dépôt) ou sur Claude + MCP
(`--moteur claude_mcp`, configuration D), sur le potager neuf ou sur le potager 33 en lecture seule, et rend un
rapport critère par critère.

* un jardinier simulé répond aux questions du compagnon depuis la fiche de besoin, jamais au-delà ;
* les critères à 100 % (intention gardée, rien d'inventé, écriture sûre, hors-sujet) sont contrôlés par le code ;
* « utile » et « aboutit » sont notés par un juge (modèle plus fort, grille écrite) ; ≥ 10 % des cas sont à relire ;
* chaque passage garde la trace complète de chaque tour ; chaque cas est joué au moins 3 fois par moteur ;
* la mesure n'écrit rien dans le potager : lectures dans une transaction annulée, écritures simulées au schéma du
  registre ; seules les lignes `conso_tokens` sont créées, avec la clé `MISTRAL_API_KEY_MESURE`.

Avant tout passage sur un vrai modèle, le lanceur annonce le volume d'appels et le coût estimé et attend un accord
explicite : `--accord N` où N est le volume annoncé (ou la réponse « accord » à l'invite). `--simule` joue sans
modèle : le rapport porte alors un avertissement et rien n'y est une mesure.

Utilisation :
    python tools/evaluer_compagnon.py --dry-run                                  # le plan, le coût, 0 appel
    python tools/evaluer_compagnon.py --simule --moteur capacites --limite 5     # essai sans modèle
    python tools/evaluer_compagnon.py --moteur actuel,capacites --accord 4210    # mesure, volume annoncé accepté
    python tools/evaluer_compagnon.py --comparer avant/resultats_actuel.json apres/resultats_capacites.json

Code de sortie : 0 si aucun critère à 100 % n'est en échec, 1 sinon, 2 si la mesure ne peut pas partir.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

RACINE = Path(__file__).resolve().parent.parent
if str(RACINE) not in sys.path:
    sys.path.insert(0, str(RACINE))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

from tools.jeu_evaluation import campagne, jeu as modele_jeu, moteurs, rapport  # noqa: E402
from tools.jeu_evaluation.juge import APPELS_JUGE_PAR_CAS, MODELE_JUGE, Juge  # noqa: E402

DOSSIER_SORTIE = RACINE / "rapports_evaluation"
DOSSIER_EPIC = RACINE / "docs" / "EPIC - AGENT INTERPRETEUR"
LIGNE_DE_BASE = DOSSIER_EPIC / "RAPPORT_LIGNE_DE_BASE_COMPAGNON.md"
MODELE_PAR_DEFAUT = "mistral/mistral-small-2603"
#: USD par million de jetons (entrée, sortie). Small 4 : grille du 01/11/2026 (`evaluer_dialogues`). Large 3 : tarif
#: public de Mistral, À CONFIRMER — c'est une estimation, pas une facture.
TARIFS = {"mistral/mistral-small-2603": (0.15, 0.60), "mistral/mistral-large-2512": (0.50, 1.50)}

#: Estimations du volume (annoncées avant tout appel, jamais présentées comme mesurées).
ETAPES_PAR_TOUR = {moteurs.MOTEUR_ACTUEL: 2.0, moteurs.MOTEUR_CAPACITES: 2.5, moteurs.MOTEUR_CLAUDE_MCP: 2.5}
TOURS_PAR_CAS = 3.0
JETONS_JUGE = (1500, 120)
JETONS_SORTIE_PAR_APPEL = 150


@dataclass
class PlanMesure:
    cas: int
    moteurs: tuple[str, ...]
    passages: int
    appels_modele: int
    appels_juge: int
    jetons_entree: int
    jetons_sortie: int
    cout_usd: Optional[float]
    modele: str
    modele_juge: str

    @property
    def volume(self) -> int:
        """Le chiffre que l'accord doit reprendre : tous les appels, modèle mesuré et juge."""
        return self.appels_modele + self.appels_juge

    def texte(self, simule: bool = False) -> str:
        coup = "non chiffré (tarif absent)" if self.cout_usd is None else f"≈ {self.cout_usd:.2f} $"
        lignes = [
            "Plan de la mesure" + (" (SIMULÉE : aucun appel, rien n'est une mesure)" if simule else " (rien n'est encore envoyé)") + " :",
            f"  • cas            : {self.cas} × {self.passages} passage(s) × {len(self.moteurs)} moteur(s) "
            f"({', '.join(self.moteurs)})",
            f"  • modèle mesuré  : {self.modele}",
            f"  • appels modèle  : ≈ {self.appels_modele} (≈ {TOURS_PAR_CAS:.0f} tours par cas, plusieurs étapes par tour)",
            f"  • appels juge    : ≈ {self.appels_juge} ({self.modele_juge})" if self.appels_juge else "  • appels juge    : 0 (sans juge)",
            f"  • jetons         : ≈ {self.jetons_entree:,} en entrée, ≈ {self.jetons_sortie:,} en sortie".replace(",", " "),
            f"  • coût estimé    : {coup}",
            f"  • volume annoncé : {self.volume}",
        ]
        return "\n".join(lignes)


def estimer(jeu: modele_jeu.Jeu, noms: tuple[str, ...], passages: int, *, modele: str, avec_juge: bool,
            modele_juge: str = MODELE_JUGE) -> PlanMesure:
    """Le volume d'appels, de jetons et le coût de la mesure, avant tout appel."""
    n = len(jeu.cas)
    try:
        from app.services.mcp.serveur import REGISTRE  # l'import remplit le registre

        prefixe = int(len(json.dumps([REGISTRE[x].schema_entree() for x in moteurs.LECTURES if x in REGISTRE])) / 5
                      + len(moteurs.PROMPT_CAPACITES) / 5)
    except Exception:  # noqa: BLE001 — l'estimation ne doit jamais empêcher d'annoncer un volume
        prefixe = 3000
    appels = jetons_in = 0
    for nom in noms:
        par_cas = TOURS_PAR_CAS * ETAPES_PAR_TOUR[nom]
        appels_moteur = int(n * passages * par_cas)
        appels += appels_moteur
        # Le préfixe est relu à chaque étape, l'historique grossit d'environ 600 jetons par tour.
        jetons_in += appels_moteur * (prefixe + 600 * (TOURS_PAR_CAS + 1) / 2)
    # Deux appels par cas : « utile » sur le premier tour, « aboutit » sur le dialogue entier.
    juge = n * passages * len(noms) * APPELS_JUGE_PAR_CAS if avec_juge else 0
    jetons_juge_in, jetons_juge_out = juge * JETONS_JUGE[0], juge * JETONS_JUGE[1]
    sortie = appels * JETONS_SORTIE_PAR_APPEL
    tarif = TARIFS.get(modele)
    tarif_juge = TARIFS.get(modele_juge)
    cout = None
    if tarif and (tarif_juge or not avec_juge) and moteurs.MOTEUR_CLAUDE_MCP not in noms:
        cout = (jetons_in * tarif[0] + sortie * tarif[1]) / 1e6
        if avec_juge and tarif_juge:
            cout += (jetons_juge_in * tarif_juge[0] + jetons_juge_out * tarif_juge[1]) / 1e6
    return PlanMesure(n, noms, passages, appels, juge, int(jetons_in + jetons_juge_in), int(sortie + jetons_juge_out),
                      cout, modele, modele_jeu_juge(avec_juge, modele_juge))


def modele_jeu_juge(avec_juge: bool, modele_juge: str) -> str:
    return modele_juge if avec_juge else "aucun"


def accord_donne(plan: PlanMesure, accord: Optional[int], *, interactif: bool, saisie=input) -> bool:
    """CA7 : un accord explicite sur le volume annoncé. `--accord N` doit reprendre le volume annoncé ; à défaut,
    une réponse « accord » à l'invite quand on est dans un terminal. Rien d'autre ne lance un vrai modèle."""
    if accord is not None:
        return accord == plan.volume
    if not interactif:
        return False
    return saisie(f"Volume annoncé : {plan.volume} appels. Tape « accord » pour lancer : ").strip().lower() == "accord"


def construire_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Lanceur du jeu d'évaluation du compagnon (US-336, US-337)")
    p.add_argument("--jeu", type=Path, default=modele_jeu.JEU, help="fichier du jeu")
    p.add_argument("--moteur", default=moteurs.MOTEUR_CAPACITES,
                   help=f"un ou plusieurs de : {', '.join(moteurs.MOTEURS)} (séparés par des virgules ; le premier est le témoin)")
    p.add_argument("--modele", default=MODELE_PAR_DEFAUT, help="modèle mesuré (moteurs actuel et capacites)")
    p.add_argument("--modele-claude", default=moteurs.MODELE_CLAUDE, help="modèle de la configuration D")
    p.add_argument("--passages", type=int, default=campagne.PASSAGES_MIN, help="passages par cas et par moteur (≥ 3)")
    p.add_argument("--besoin", help="ne jouer que ces besoins (B01,B05…)")
    p.add_argument("--donnees", choices=modele_jeu.JEUX_DE_DONNEES, help="ne jouer que ce jeu de données")
    p.add_argument("--limite", type=int, default=0, help="ne jouer que les N premiers cas retenus")
    p.add_argument("--potager-neuf", type=int, default=_entier_env("JEU_EVAL_POTAGER_NEUF"))
    p.add_argument("--utilisateur-neuf", type=int, default=_entier_env("JEU_EVAL_UTILISATEUR_NEUF"))
    p.add_argument("--potager-rempli", type=int, help="défaut : celui du jeu (potager 33)")
    p.add_argument("--utilisateur-rempli", type=int, help="défaut : celui du jeu")
    p.add_argument("--sans-juge", action="store_true", help="ne note que les critères du code")
    p.add_argument("--modele-juge", default=MODELE_JUGE)
    p.add_argument("--dry-run", action="store_true", help="le plan, le volume, le coût : aucun appel")
    p.add_argument("--accord", type=int, help="accord explicite : le volume annoncé par --dry-run")
    p.add_argument("--simule", action="store_true", help="modèle simulé : aucun appel, rien n'est une mesure")
    p.add_argument("--sortie", type=Path, help="dossier des traces et résultats (défaut : rapports_evaluation/<date>)")
    p.add_argument("--rapport", type=Path, help="fichier du rapport markdown (défaut : <sortie>/rapport.md)")
    p.add_argument("--comparer", nargs=2, metavar=("AVANT", "APRES"), type=Path,
                   help="compare deux fichiers de résultats, sans rien jouer")
    p.add_argument("--verser-ligne-de-base", action="store_true",
                   help="verse le rapport de la chaîne actuelle dans le dossier de l'épic (mesure réelle seulement)")
    p.add_argument("--pause", type=float, default=0.5, help="secondes entre deux tours")
    p.add_argument("--detail", action="store_true")
    return p


def _entier_env(nom: str) -> Optional[int]:
    brut = (os.environ.get(nom) or "").strip()
    return int(brut) if brut.isdigit() else None


def _contexte(jeu: modele_jeu.Jeu, args, donnees: str, simule: bool):
    from app.services.context import TenantContext

    if simule:
        return TenantContext(user_id=1, potager_id=1, role="owner")
    if donnees == modele_jeu.JEU_NEUF:
        if not (args.potager_neuf and args.utilisateur_neuf):
            raise SystemExit(
                "Le potager neuf se crée avec `python tools/creer_potager_test_neuf.py` ; passe ensuite ses numéros "
                "par --potager-neuf et --utilisateur-neuf (ou JEU_EVAL_POTAGER_NEUF / JEU_EVAL_UTILISATEUR_NEUF).")
        return TenantContext(user_id=args.utilisateur_neuf, potager_id=args.potager_neuf, role="owner")
    d = jeu.jeux_de_donnees.get(modele_jeu.JEU_REMPLI, {})
    potager = args.potager_rempli or d.get("potager_id")
    utilisateur = args.utilisateur_rempli or d.get("utilisateur_id")
    if not (potager and utilisateur):
        raise SystemExit("Le potager rempli attend --potager-rempli et --utilisateur-rempli.")
    return TenantContext(user_id=utilisateur, potager_id=potager, role="owner")


def _noms_moteurs(args, parser) -> tuple[str, ...]:
    noms = tuple(n.strip() for n in args.moteur.split(",") if n.strip())
    inconnus = [n for n in noms if n not in moteurs.MOTEURS]
    if not noms or inconnus:
        parser.error(f"moteur inconnu : {', '.join(inconnus) or args.moteur}")
    return noms


def controler_le_jeu(jeu: modele_jeu.Jeu) -> list[str]:
    """Les écarts du jeu avec la story, plus les cas renouvelables cités dans un prompt (CA6)."""
    ecarts = modele_jeu.controler_exigences(jeu)
    fautifs = modele_jeu.controler_renouvelables(jeu, modele_jeu.textes_des_prompts_livres())
    if fautifs:
        ecarts.append(f"CA6 : cas renouvelables cités dans un exemple de prompt : {', '.join(fautifs)}")
    return ecarts


def jouer(args, jeu: modele_jeu.Jeu, noms: tuple[str, ...], dossier: Path) -> list[campagne.Mesure]:
    """Les passages réels (ou simulés) : un `Mesure` par moteur."""
    from llm import contexte_appel, passerelle
    from tools import evaluer_dialogues as ed

    simule = args.simule
    contexte_appel.demarrer_outil()  # provenance « mesure », canal « outil »
    cle = None if simule else ed.cle_de_mesure()
    if not simule:
        ed.verifier_modeles([args.modele] + ([] if args.sans_juge else [args.modele_juge]))
    jour = date.today()
    mesures: list[campagne.Mesure] = []
    modele_initial = passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT]
    from contextlib import ExitStack

    with ExitStack() as pile:
        if cle:
            pile.enter_context(ed.cle_branchee(cle))
        if not simule:
            passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT] = args.modele
            passerelle.reinitialiser_capacites_outils()
        try:
            juge = None
            if not args.sans_juge and not simule:
                from tools.jeu_evaluation.juge import appeler_par_la_passerelle

                ctx_juge = _contexte(jeu, args, modele_jeu.JEU_REMPLI if not args.potager_neuf else modele_jeu.JEU_NEUF, False)
                juge = Juge(appeler_par_la_passerelle(ctx_juge, args.modele_juge), args.modele_juge, jour=jour)
            for nom in noms:
                print(f"\n▶ {nom}")
                contextes: dict = {}
                actifs: dict = {}

                def moteur_pour(cas, nom=nom, contextes=contextes, actifs=actifs):
                    if cas.jeu_de_donnees not in actifs:
                        contextes[cas.jeu_de_donnees] = _contexte(jeu, args, cas.jeu_de_donnees, simule)
                        options = {"modele": args.modele_claude} if nom == moteurs.MOTEUR_CLAUDE_MCP else {}
                        if nom == moteurs.MOTEUR_ACTUEL:
                            options["fictif"] = simule
                        actifs[cas.jeu_de_donnees] = moteurs.creer_moteur(
                            nom, contextes[cas.jeu_de_donnees], simule=simule, jour=jour, **options)
                    return actifs[cas.jeu_de_donnees]

                mesure = campagne.Mesure(
                    moteur=nom, modele=(args.modele_claude if nom == moteurs.MOTEUR_CLAUDE_MCP else args.modele),
                    mesure_reelle=not simule, jeu=str(args.jeu.name), date=campagne.maintenant(),
                    passages=args.passages, juge=(juge.modele if juge else ""),
                    potager={k: v for k, v in (("neuf", args.potager_neuf), ("rempli", args.potager_rempli or 33))
                             if v and any(c.jeu_de_donnees == k for c in jeu.cas)})
                for passage in range(1, args.passages + 1):
                    print(f" passage {passage}/{args.passages}")
                    mesure.resultats += campagne.jouer_passage(
                        jeu, moteur_pour, passage=passage, dossier=dossier, juge=juge, jour=jour, pause_s=0 if simule else args.pause,
                        detail=print if args.detail else (lambda _: None))
                mesure.ecrire(dossier / f"resultats_{nom}.json")
                mesures.append(mesure)
        finally:
            passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_AGENT] = modele_initial
            passerelle.reinitialiser_capacites_outils()
    return mesures


def main(argv: Optional[list[str]] = None) -> int:
    parser = construire_parser()
    args = parser.parse_args(argv)

    if args.comparer:
        avant, apres = (campagne.Mesure.lire(c) for c in args.comparer)
        comparaison = rapport.comparer(avant, apres)
        texte = rapport.rediger_rapport([avant, apres], titre="Comparaison avant / après", comparaison=comparaison,
                                        temoin=avant.moteur)
        if args.rapport:
            args.rapport.parent.mkdir(parents=True, exist_ok=True)
            args.rapport.write_text(texte, encoding="utf-8")
            print(f"Rapport écrit : {args.rapport}")
        else:
            print(texte)
        return 1 if comparaison.bloquee else 0

    noms = _noms_moteurs(args, parser)
    if args.passages < campagne.PASSAGES_MIN:
        parser.error(f"--passages : {campagne.PASSAGES_MIN} au moins par moteur (CA6b)")
    jeu = modele_jeu.charger(args.jeu)
    ecarts = controler_le_jeu(jeu)
    if ecarts:
        print("❌ Le jeu ne tient pas ses exigences :", *ecarts, sep="\n  - ", file=sys.stderr)
        return 2
    jeu = jeu.filtrer(besoins=[b.strip() for b in args.besoin.split(",")] if args.besoin else (),
                      jeu=args.donnees or "", limite=args.limite)
    if not jeu.cas:
        parser.error("aucun cas retenu")

    plan = estimer(jeu, noms, args.passages, modele=args.modele, avec_juge=not args.sans_juge and not args.simule,
                   modele_juge=args.modele_juge)
    print(plan.texte(args.simule))
    if args.dry_run:
        return 0
    if not args.simule and not accord_donne(plan, args.accord, interactif=sys.stdin.isatty()):
        print(f"\n❌ Aucun accord sur le volume annoncé ({plan.volume} appels) : rien n'est lancé. "
              f"Relance avec --accord {plan.volume}.", file=sys.stderr)
        return 2

    dossier = args.sortie or DOSSIER_SORTIE / campagne.horodatage()
    try:
        mesures = jouer(args, jeu, noms, dossier)
    except Exception as e:  # noqa: BLE001 — clé absente, modèle hors Mistral, potager inconnu
        print(f"\n❌ {e}", file=sys.stderr)
        return 2

    comparaison = rapport.comparer(mesures[0], mesures[1]) if len(mesures) > 1 else None
    texte = rapport.rediger_rapport(mesures, titre="Mesure du compagnon", temoin=mesures[0].moteur if len(mesures) > 1 else None,
                                    comparaison=comparaison, graine=dossier.name)
    chemin = args.rapport or dossier / "rapport.md"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(texte, encoding="utf-8")
    print(f"\nRapport écrit : {chemin}\nTraces : {dossier}")

    if args.verser_ligne_de_base:
        base = next((m for m in mesures if m.moteur == moteurs.MOTEUR_ACTUEL), None)
        if base is None or not base.mesure_reelle:
            print("⚠️ Ligne de base non versée : il faut une mesure RÉELLE de la chaîne actuelle.", file=sys.stderr)
        else:
            LIGNE_DE_BASE.write_text(rapport.rediger_rapport(
                [base], titre="Ligne de base de la chaîne actuelle", graine=dossier.name), encoding="utf-8")
            print(f"Ligne de base versée : {LIGNE_DE_BASE}")
    en_echec = any(not c.tient for r in map(rapport.resumer, mesures) for k, c in r.criteres.items()
                   if k in rapport.A_CENT and c.tient is not None) or (comparaison is not None and comparaison.bloquee)
    return 1 if en_echec else 0


if __name__ == "__main__":
    sys.exit(main())
