"""
tools/audit_appels_llm.py — Audit du point de passage unique vers le LLM [US-092 / CA1]
=======================================================================================
Vérifie qu'**aucun appel direct au client du fournisseur de modèles ne subsiste**
dans le code applicatif, en dehors de la passerelle `llm/passerelle.py`.

C'est la condition qui rend vraies toutes les US suivantes de la cascade : sans
point de passage unique, la mesure de consommation, le mode dégradé et le
branchement d'une clé par potager (BYOK) devraient être recâblés dans chaque
fonction, et le premier oubli les rendrait faux sans que rien ne le signale.

Usage
-----
    python tools/audit_appels_llm.py          # 0 si conforme, 1 sinon

Le même audit est rejoué par le test
`tests/test_us092_passerelle_llm.py::test_us092_ca1_aucun_appel_direct_hors_passerelle`
— c'est ce qui empêche la règle de se dégrader silencieusement au fil des US.

Périmètre
---------
Code applicatif uniquement. Sont exclus :
  * `llm/passerelle.py`      — la passerelle EST le point de passage autorisé ;
  * ce fichier               — il cite les motifs recherchés ;
  * `tools/mesurer_modeles_llm.py` — banc de mesure du fournisseur nu, lancé à la main ;
  * `tests/`                 — mocker le client est le comportement attendu ;
  * `.venv/`, caches, build frontend.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Fichiers autorisés à parler au fournisseur de modèles (chemins relatifs POSIX).
FICHIERS_AUTORISES = {
    "llm/passerelle.py",
    "tools/audit_appels_llm.py",
    # Banc de mesure des modèles (US-140/US-094) : il mesure le fournisseur NU — sans les
    # relances sur 429 ni l'écriture de `conso_tokens` de la passerelle, qui fausseraient
    # latence et coût. Outil lancé à la main, jamais importé par l'application.
    "tools/mesurer_modeles_llm.py",
}

# Répertoires hors périmètre applicatif.
REPERTOIRES_EXCLUS = {
    ".venv", ".git", "__pycache__", ".pytest_cache", "node_modules",
    "tests", "frontend", "ds-bundle", "maquette front", "static",
}

# Chaînes d'attributs trahissant un appel direct au fournisseur, hors passerelle.
# L'analyse est faite sur l'AST, pas sur le texte : une mention de « Groq » dans
# un commentaire ou une chaîne de caractères n'est pas un appel, et l'audit doit
# rester exécutable sans produire de faux positifs — sinon il finit ignoré.
CHAINES_INTERDITES = {
    ("chat", "completions", "create"):       "appel direct chat.completions.create",
    ("audio", "transcriptions", "create"):   "appel direct audio.transcriptions.create",
}


def _fichiers_a_auditer() -> list[Path]:
    fichiers = []
    for chemin in RACINE.rglob("*.py"):
        relatif = chemin.relative_to(RACINE)
        if any(part in REPERTOIRES_EXCLUS for part in relatif.parts):
            continue
        if relatif.as_posix() in FICHIERS_AUTORISES:
            continue
        fichiers.append(chemin)
    return sorted(fichiers)


def _chaine_attributs(noeud: ast.AST) -> tuple[str, ...]:
    """Reconstruit `a.b.c` en ('a', 'b', 'c') — vide si l'expression n'est pas
    une simple chaîne d'attributs."""
    parties: list[str] = []
    courant = noeud
    while isinstance(courant, ast.Attribute):
        parties.append(courant.attr)
        courant = courant.value
    if isinstance(courant, ast.Name):
        parties.append(courant.id)
    elif not isinstance(courant, (ast.Attribute, ast.Call, ast.Subscript)):
        return ()
    return tuple(reversed(parties))


def _infractions_du_fichier(source: str) -> list[tuple[int, str, str]]:
    """Retourne (ligne, libellé, extrait) pour un fichier source Python."""
    try:
        arbre = ast.parse(source)
    except SyntaxError as e:
        # Un fichier illisible ne doit PAS être silencieusement déclaré conforme :
        # ce serait la porte ouverte à un audit tautologique. On le signale.
        return [(getattr(e, "lineno", 1) or 1, f"fichier non analysable ({e.msg})", "")]

    lignes = source.splitlines()
    trouvees: list[tuple[int, str, str]] = []

    def _extrait(numero: int) -> str:
        return lignes[numero - 1].strip() if 0 < numero <= len(lignes) else ""

    for noeud in ast.walk(arbre):
        libelle = None

        if isinstance(noeud, ast.Import):
            if any(alias.name == "groq" or alias.name.startswith("groq.")
                   for alias in noeud.names):
                libelle = "import direct du SDK groq"
        elif isinstance(noeud, ast.ImportFrom):
            if (noeud.module or "") == "groq" or (noeud.module or "").startswith("groq."):
                libelle = "import direct du SDK groq"
        elif isinstance(noeud, ast.Call):
            cible = noeud.func
            if isinstance(cible, ast.Name) and cible.id == "Groq":
                libelle = "instanciation directe du client Groq"
            else:
                chaine = _chaine_attributs(cible)
                for suffixe, message in CHAINES_INTERDITES.items():
                    if len(chaine) >= len(suffixe) and chaine[-len(suffixe):] == suffixe:
                        libelle = message
                        break

        if libelle:
            trouvees.append((noeud.lineno, libelle, _extrait(noeud.lineno)))

    return trouvees


def auditer() -> list[tuple[str, int, str, str]]:
    """Retourne la liste des infractions : (fichier, ligne, motif, extrait).

    Une liste vide vaut conformité au CA1.
    """
    infractions: list[tuple[str, int, str, str]] = []
    for chemin in _fichiers_a_auditer():
        try:
            # utf-8-sig : l'ancien bot.py portait un BOM hérité — le lire en utf-8 strict
            # ferait échouer l'analyse et sortir le plus gros fichier du périmètre.
            source = chemin.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        relatif = chemin.relative_to(RACINE).as_posix()
        for numero, libelle, extrait in _infractions_du_fichier(source):
            infractions.append((relatif, numero, libelle, extrait))
    return infractions


# ─────────────────────────────────────────────────────────────────────────────
# [US-306 / CA4, CA7] Provenance des appels faits depuis `tools/`
# -----------------------------------------------------------------------------
# Un outil qui appelle un modèle écrit des lignes dans `conso_tokens`. Sans
# provenance fixée, elles seraient comptées comme de l'usage de jardinier : c'est
# toute la raison d'être de ce contrôle. « Appeler la passerelle » se lit dans les
# imports de l'outil lui-même (la fermeture transitive des imports est trop large :
# presque tout `tools/` atteint la passerelle sans jamais l'exécuter).
# ─────────────────────────────────────────────────────────────────────────────
MODULES_DU_MODELE = ("llm.passerelle", "llm.routeur", "llm.groq_client")

#: Outils qui appellent un modèle sans importer ces modules (ils passent par un service).
OUTILS_INDIRECTS = frozenset({"mesurer_corpus_savoir.py", "mesurer_redaction_signaux.py"})

#: Hors contrôle : l'audit lui-même, et le banc du fournisseur nu qui ne passe pas par la
#: passerelle (donc n'écrit aucune ligne dans `conso_tokens`).
OUTILS_EXCLUS_PROVENANCE = frozenset({"audit_appels_llm.py", "mesurer_modeles_llm.py"})


def _importe_le_modele(arbre: ast.AST) -> bool:
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Import):
            if any(a.name in MODULES_DU_MODELE for a in noeud.names):
                return True
        elif isinstance(noeud, ast.ImportFrom):
            module = noeud.module or ""
            if module in MODULES_DU_MODELE:
                return True
            if module == "llm" and any(f"llm.{a.name}" in MODULES_DU_MODELE for a in noeud.names):
                return True
    return False


def _fixe_la_provenance(arbre: ast.AST) -> bool:
    """Vrai si le fichier appelle `fixer_provenance(...)`, `demarrer_outil()` ou ouvre `provenance(...)`."""
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Call):
            chaine = _chaine_attributs(noeud.func)
            if chaine and chaine[-1] in {"fixer_provenance", "provenance", "demarrer_outil"}:
                return True
    return False


def outils_appelant_un_modele() -> list[str]:
    """Noms des fichiers de `tools/` qui ont un point d'entrée (`__main__`) et appellent
    un modèle : import direct de la passerelle ou du routeur, ou liste `OUTILS_INDIRECTS`."""
    trouves = []
    for chemin in sorted((RACINE / "tools").glob("*.py")):
        if chemin.name in OUTILS_EXCLUS_PROVENANCE:
            continue
        source = chemin.read_text(encoding="utf-8-sig")
        if "__main__" not in source:
            continue
        arbre = ast.parse(source)
        if chemin.name in OUTILS_INDIRECTS or _importe_le_modele(arbre):
            trouves.append(chemin.name)
    return trouves


def outils_sans_provenance() -> list[str]:
    """[US-306 / CA7] Outils qui appellent un modèle sans avoir fixé la provenance."""
    return [
        nom for nom in outils_appelant_un_modele()
        if not _fixe_la_provenance(ast.parse((RACINE / "tools" / nom).read_text(encoding="utf-8-sig")))
    ]


def main() -> int:
    sans_provenance = outils_sans_provenance()
    if sans_provenance:
        print(f"❌ [US-306 / CA7] {len(sans_provenance)} outil(s) appellent un modèle sans fixer la provenance :")
        for nom in sans_provenance:
            print(f"  tools/{nom} — appeler contexte_appel.fixer_provenance(PROVENANCE_MESURE) dans main()")
        return 1
    infractions = auditer()
    if not infractions:
        print("✅ [US-092 / CA1] Aucun appel direct au fournisseur de modèles "
              "hors de llm/passerelle.py.")
        return 0

    print(f"❌ [US-092 / CA1] {len(infractions)} appel(s) direct(s) hors passerelle :")
    for fichier, ligne, libelle, extrait in infractions:
        print(f"  {fichier}:{ligne} — {libelle}\n      {extrait}")
    print("\nCes appels doivent passer par llm/passerelle.py "
          "(appeler_chat / appeler_chat_outils / transcrire) pour être typés, imputés et mesurés.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
