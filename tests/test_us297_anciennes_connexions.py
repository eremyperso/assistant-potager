"""[US-297] Ranger les anciennes connexions d'assistants IA sous un lien repliable.

La logique d'affichage (CA1 à CA6) est testée côté frontend par
`frontend/src/lib/assistants.test.js` (`npm test`). Ici : le corpus (CA7) et le
contrat que l'écran consomme (le statut de chaque connexion, rien d'effacé — CA4).
"""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
FICHE = RACINE / "data" / "connaissance" / "doc_app" / "assistants-ia-mcp.md"
ECRAN = RACINE / "frontend" / "src" / "components" / "ModalAssistantsConnectes.jsx"
LOGIQUE = RACINE / "frontend" / "src" / "lib" / "assistants.js"


def _section_revoquer() -> str:
    texte = FICHE.read_text(encoding="utf-8")
    debut = texte.index("## Comment voir et révoquer mes assistants connectés")
    suite = texte.find("\n## ", debut + 1)
    return texte[debut: suite if suite != -1 else len(texte)]


def test_us297_corpus_la_fiche_mentionne_les_anciennes_connexions() -> None:
    """[CA7] La fiche dit où retrouver une connexion révoquée ou expirée."""
    section = _section_revoquer()
    assert "« Anciennes connexions »" in section
    assert "rien n'est effacé" in section


def test_us297_corpus_les_mots_du_jardinier_classent_la_section() -> None:
    """[CA7] « anciennes connexions » figure dans les synonymes de la section."""
    synonymes = next(l for l in _section_revoquer().splitlines() if l.startswith("**On parle aussi de :**"))
    assert "anciennes connexions" in synonymes


def test_us297_l_ecran_ne_supprime_rien() -> None:
    """[CA4] Aucune requête de suppression nouvelle : seul « Révoquer » existe déjà (US-294)."""
    source = ECRAN.read_text(encoding="utf-8")
    assert "connecteurApi.revoquer" in source
    assert "supprimer" not in source.lower()


def test_us297_l_ecran_s_appuie_sur_la_repartition_testee() -> None:
    """[CA1, CA2] L'écran utilise `repartirConnexions` et `libelleAnciennes` (testés en node)."""
    source = ECRAN.read_text(encoding="utf-8")
    assert "repartirConnexions(" in source and "libelleAnciennes(" in source
    assert "aria-expanded={anciennesVisibles}" in source
    assert "export function repartirConnexions" in LOGIQUE.read_text(encoding="utf-8")


def test_us297_le_statut_rendu_par_l_api_suffit() -> None:
    """[CA1] Les trois statuts que l'écran répartit sont ceux que rend `GET /mcp/connexions`."""
    from app.services.mcp import connexions

    assert (connexions.STATUT_ACTIVE, connexions.STATUT_REVOQUEE, connexions.STATUT_EXPIREE) == (
        "active", "revoquee", "expiree",
    )
