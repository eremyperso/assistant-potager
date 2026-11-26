"""[US-337] Rejouer l'appréciation sur des traces existantes : l'origine reste intacte, le volume ne compte que ce qui
manque, et rien n'est lancé sans accord."""
from tools import evaluer_compagnon as lanceur
from tools.jeu_evaluation import campagne, controles, jeu as j, rejuger
from tools.jeu_evaluation.juge import Juge
from tools.jeu_evaluation.trace import TraceCas, TraceTour


def _mesure_d_origine(dossier):
    trace = TraceCas("B16-F1", "boucle", 1, tours=[TraceTour(rang=1, jardinier="stock ?", texte="Rien en stock.")])
    chemin = campagne.ecrire_trace(dossier, trace, controles.Notes(), None)
    mesure = campagne.Mesure(moteur="boucle", date="2026-11-23 10:00:00", passages=3, resultats=[
        campagne.ResultatCas(cas="B16-F1", passage=1, besoin="B16", notes={}, trace=chemin)])
    mesure.ecrire(dossier / "resultats_boucle.json")
    return mesure


def test_renoter_garde_l_origine_et_reprend_les_verdicts_deja_obtenus(tmp_path):
    source, sortie = tmp_path / "mesure", tmp_path / "rejuge"
    mesure = _mesure_d_origine(source)
    avant = (source / mesure.resultats[0].trace).read_text(encoding="utf-8")
    assert rejuger.appels_a_faire(mesure, sortie) == 2

    juge = Juge(lambda grille, message: ('{"utile": false, "aboutit": false, "raison": "r"}', 1, 1), "faux")
    notee = rejuger.rejuger(mesure, j.charger(), source=source, sortie=sortie, juge=juge)
    assert notee.resultats[0].verdict["utile"] is False
    assert notee.resultats[0].notes["rien_d_invente"] is False
    assert (source / mesure.resultats[0].trace).read_text(encoding="utf-8") == avant
    assert rejuger.appels_a_faire(mesure, sortie) == 0

    relus = {("boucle", "B16-F1", 1): {"utile": False, "aboutit": True}}
    assert rejuger.accord_avec_l_humain(notee, relus) == {"utile": (1, 1), "aboutit": (0, 1)}


def test_sans_accord_sur_le_volume_rien_n_est_lance(tmp_path, capsys):
    source = tmp_path / "mesure"
    _mesure_d_origine(source)
    code = lanceur.main(["--rejuger", str(source), "--moteur", "boucle", "--accord", "999"])
    assert code == 2 and not (tmp_path / "mesure_rejuge").exists()
    assert "volume annoncé : 2" in capsys.readouterr().out
