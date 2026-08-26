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
            # utf-8-sig : bot.py porte un BOM hérité — le lire en utf-8 strict
            # ferait échouer l'analyse et sortir le plus gros fichier du périmètre.
            source = chemin.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        relatif = chemin.relative_to(RACINE).as_posix()
        for numero, libelle, extrait in _infractions_du_fichier(source):
            infractions.append((relatif, numero, libelle, extrait))
    return infractions


def main() -> int:
    infractions = auditer()
    if not infractions:
        print("✅ [US-092 / CA1] Aucun appel direct au fournisseur de modèles "
              "hors de llm/passerelle.py.")
        return 0

    print(f"❌ [US-092 / CA1] {len(infractions)} appel(s) direct(s) hors passerelle :")
    for fichier, ligne, libelle, extrait in infractions:
        print(f"  {fichier}:{ligne} — {libelle}\n      {extrait}")
    print("\nCes appels doivent passer par llm/passerelle.py "
          "(appeler_chat / transcrire) pour être typés, imputés et mesurés.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
