"""[US-254] Import du référentiel au déploiement."""
import json
from pathlib import Path

import pytest

from tools import importer_referentiel_deploiement as outil

RACINE = Path(__file__).resolve().parent.parent
WORKFLOWS = [".github/workflows/deploy-dev.yml", ".github/workflows/deploy.yml"]


def test_liste_reelle_coherente():
    """CA5 : chaque JSON du dépôt est importé ou explicitement exclu."""
    a_importer, exclus = outil.lire_liste(outil.DOSSIER_REFERENTIEL)
    assert a_importer
    assert all(exclus.values()), "chaque exclusion porte un motif"


def test_fichier_non_liste_refuse(tmp_path):
    (tmp_path / "deploiement.json").write_text(json.dumps({"importer": [], "exclus": {}}))
    (tmp_path / "nouveau.json").write_text("{}")
    with pytest.raises(ValueError, match="nouveau.json"):
        outil.lire_liste(tmp_path)


def test_fichier_liste_introuvable(tmp_path):
    (tmp_path / "deploiement.json").write_text(json.dumps({"importer": ["absent.json"]}))
    with pytest.raises(ValueError, match="absent.json"):
        outil.lire_liste(tmp_path)


def test_manifeste_invalide_arrete_avant_ecriture(tmp_path, capsys):
    """CA2 : code non nul, sans ouvrir de session d'écriture."""
    (tmp_path / "deploiement.json").write_text(json.dumps({"importer": ["x.json"]}))
    (tmp_path / "x.json").write_text("{}")
    assert outil.main(["--dossier", str(tmp_path)]) == 2
    assert "x.json" in capsys.readouterr().err


@pytest.mark.parametrize("chemin", WORKFLOWS)
def test_workflow_importe_apres_corpus(chemin):
    """CA1/CA3 : même étape en dev et en prod, après l'ingestion du corpus."""
    texte = (RACINE / chemin).read_text(encoding="utf-8")
    ingestion = texte.index("tools/ingerer_connaissance.py")
    import_ref = texte.index("tools/importer_referentiel_deploiement.py")
    assert ingestion < import_ref < texte.index("Restart systemd services")
