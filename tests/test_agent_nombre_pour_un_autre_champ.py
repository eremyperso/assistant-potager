"""Un nombre dit n'est pas un nombre pour n'importe quel champ de la fiche.

Relevé du 13/11/2026 : « planter 3 plants d'aubergine sur la planche courges » partait en
`/parcelle modifier planche-courges rangs=3` (le « 3 » était bien dit, mais pas pour les rangs).
"""
from app.services.agent.catalogue_outils import OUTIL_MODIFIER_PARCELLE
from app.services.agent.validation import ContexteValidation, valider_appel
from llm.passerelle import AppelOutil

PARCELLES = ("Planche Courges", "Planche Nord")


def _valider(texte, arguments):
    return valider_appel(
        AppelOutil(OUTIL_MODIFIER_PARCELLE, arguments),
        ContexteValidation(texte=texte, noms_parcelles=PARCELLES, voisin=lambda n: None),
    )


def test_trois_plants_ne_deviennent_pas_trois_rangs():
    verdict = _valider("planter 3 plants d'aubergine sur la planche courges",
                       {"parcelle": "Planche Courges", "nb_rangs": 3})
    assert verdict.commande is None


def test_trois_plants_ne_deviennent_pas_trois_metres():
    verdict = _valider("planter 3 plants d'aubergine sur la planche courges",
                       {"parcelle": "Planche Courges", "longueur_m": 3})
    assert verdict.commande is None


def test_un_nombre_de_rangs_dit_comme_tel_passe():
    verdict = _valider("la planche nord a 4 rangs", {"parcelle": "Planche Nord", "nb_rangs": 4})
    assert verdict.commande is not None and "rangs=4" in verdict.commande.args


def test_une_mesure_avec_son_unite_passe():
    verdict = _valider("la planche nord fait 6 m", {"parcelle": "Planche Nord", "longueur_m": 6})
    assert verdict.commande is not None
