"""
tests/test_us337_lanceur_evaluation.py
[US-337] Lancer le jeu d'évaluation sur la chaîne actuelle et sur la boucle cible, avec juge et rapport.

CA7 : le modèle est TOUJOURS simulé ici. Ce qui est testé, c'est l'outil : le jardinier simulé (jamais une valeur
absente de la fiche), les contrôles par le code, les moteurs (lectures dans une transaction annulée, écritures
simulées), le juge, la trace, le rapport (dispersion, régression bloquante), l'accord sur le volume. Seule une
exécution de `tools/evaluer_compagnon.py` avec accord appelle un vrai modèle.
"""
from __future__ import annotations

import json
from dataclasses import replace
from datetime import date

import pytest

from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils
from tools import evaluer_compagnon as lanceur
from tools.jeu_evaluation import campagne, controles, juge as jg, moteurs, rapport
from tools.jeu_evaluation import jeu as j
from tools.jeu_evaluation import utilisateur as u
from tools.jeu_evaluation.trace import AppelTrace, TraceCas, TraceTour

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
JOUR = date(2026, 11, 17)


@pytest.fixture(scope="module")
def le_jeu() -> j.Jeu:
    return j.charger()


def _cas(le_jeu, identifiant: str) -> j.Cas:
    return le_jeu.cas_par_id(identifiant)


def _tour(rang, jardinier="", texte="", propositions=(), executions=(), appels=(), clic="", attente=False) -> TraceTour:
    return TraceTour(rang=rang, jardinier=jardinier, texte=texte, propositions=list(propositions),
                     executions=list(executions), appels=list(appels), clic=clic, proposition_en_attente=attente,
                     etapes=1, tokens_in=1000, tokens_cache=800, latence_ms=900)


def _trace(*tours: TraceTour, cas="X", moteur="capacites", passage=1, simule=False) -> TraceCas:
    return TraceCas(cas=cas, moteur=moteur, passage=passage, tours=list(tours), modele_simule=simule)


def _reponse(*appels: AppelOutil, texte: str = "", statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(texte=texte, modele="mistral/mistral-small-2603", appel_type="agent", tokens_in=1000,
                         tokens_out=50, tokens_cache=700, latence_ms=300, appels=tuple(appels), statut=statut)


def _appel(nom: str, /, **arguments) -> AppelOutil:
    return AppelOutil(nom=nom, arguments=arguments, id=f"id_{nom}")


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — le jardinier simulé ne dit jamais une valeur absente de la fiche
# ═════════════════════════════════════════════════════════════════════════════
FICHE = {"culture": "salade", "parcelle": "planche légumes", "quantite": "12", "unite": "pieds", "date": "demain"}


@pytest.mark.parametrize("question, attendu", [
    ("Quelle culture veux-tu planter ?", "salade"),
    ("Sur quelle parcelle ?", "la planche légumes"),
    ("Combien de plants ?", "12 pieds"),
    ("Pour quand ?", "demain"),
    ("Quelle culture, et sur quelle parcelle ?", "salade, la planche légumes"),
])
def test_ca2_il_repond_depuis_la_fiche(question, attendu):
    assert u.JardinierSimule(FICHE).repondre(question).phrase == attendu


def test_ca2_une_valeur_absente_de_la_fiche_n_est_jamais_donnee():
    sans_quantite = {k: v for k, v in FICHE.items() if k not in ("quantite", "unite")}
    r = u.JardinierSimule(sans_quantite).repondre("Combien de plants ?")
    assert r.phrase == u.REPONSE_INCONNUE and not any(ch.isdigit() for ch in r.phrase)


def test_ca2_un_accord_est_un_oui_ou_un_clic_selon_le_moteur():
    assert u.JardinierSimule(FICHE).repondre("Je te propose de noter ce semis. Tu confirmes ?").phrase == "oui"
    r = u.JardinierSimule(FICHE, mode_confirmation="bouton").repondre("Je te propose de noter ce semis.")
    assert r.clic == "Confirmer" and not r.phrase


def test_ca2_une_valeur_par_defaut_differente_de_la_fiche_est_corrigee_par_la_fiche():
    r = u.JardinierSimule(FICHE).repondre("Je note 10 plants, ça te va ?")
    assert r.phrase == "non, plutôt 12 pieds"


def test_ca2_une_valeur_par_defaut_egale_a_la_fiche_est_acceptee():
    assert u.JardinierSimule(FICHE).repondre("Je note 12 pieds, ça te va ?").phrase == "oui"


def test_ca2_sans_question_le_dialogue_est_fini():
    assert u.JardinierSimule(FICHE).repondre("Voilà, c'est la saison des semis.").fin is True


def test_ca2_seules_les_phrases_interrogatives_demandent_un_champ():
    assert u.champs_demandes("Tu veux planter des salades. Sur quelle parcelle ?") == ["parcelle"]
    assert u.champs_demandes("Quelle culture ? Et pour quand ?") == ["culture", "date"]


def test_ca2_verifier_reponse_refuse_un_chiffre_hors_fiche():
    with pytest.raises(AssertionError):
        u.verifier_reponse("plutôt 15 plants", FICHE)
    u.verifier_reponse("12 pieds demain", FICHE)


def test_ca2_aucun_cas_du_jeu_ne_fait_dire_au_simule_une_valeur_hors_fiche(le_jeu):
    questions = ["Quelle culture ?", "Sur quelle parcelle ?", "Combien ?", "Pour quand ?", "Quelle variété ?",
                 "Je note 10 plants, ça te va ?", "Tu confirmes ?", "Et sinon ?"]
    for c in le_jeu.cas:
        sim = u.JardinierSimule(c.fiche)
        for q in questions:
            r = sim.repondre(q)  # `verifier_reponse` lève si la réponse sort de la fiche
            assert not any(ch.isdigit() for ch in r.phrase) or any(ch.isdigit() for ch in json.dumps(c.fiche))


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — les critères à 100 % sont contrôlés par le code
# ═════════════════════════════════════════════════════════════════════════════
def test_ca4_intention_perdue_une_culture_redemandee_apres_avoir_ete_dite(le_jeu):
    """Le défaut du 14/11 : « quelle culture ? » au tour 5, alors que « des salades » est dit depuis le tour 1."""
    cas = _cas(le_jeu, "B01-F1")
    trace = _trace(_tour(1, "j'aimerai planter des salades", "Je te propose de créer une parcelle."),
                   _tour(5, "demain", "Qu'est-ce que tu veux qu'on te rappelle ? Quelle culture ?"))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.intention_gardee is False
    assert "redemande « culture »" in notes.violations["intention_gardee"][0]


def test_ca4_la_faute_de_frappe_vaut_une_valeur_dite(le_jeu):
    cas = _cas(le_jeu, "B01-F5")  # « je veu plentér de la salad sur ma planche »
    trace = _trace(_tour(1, cas.ouverture, "Quelle culture veux-tu planter ?"))
    assert controles.noter_cas(cas, trace, jour=JOUR).intention_gardee is False


def test_ca4_une_valeur_pas_encore_dite_peut_se_demander(le_jeu):
    cas = _cas(le_jeu, "B01-F4")  # « planter salade » : ni parcelle, ni date
    trace = _trace(_tour(1, cas.ouverture, "Sur quelle parcelle ?"))
    assert controles.noter_cas(cas, trace, jour=JOUR).intention_gardee is True


def test_ca4_rien_d_invente_une_quantite_par_defaut_dans_la_proposition(le_jeu):
    cas = _cas(le_jeu, "B04-F1")
    proposition = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate",
                                                             "quantite": 10, "parcelle": "planche légumes"}}
    trace = _trace(_tour(1, "Je voudrais planter des tomates sur la planche légumes", "Voilà",
                         propositions=[proposition]))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.rien_d_invente is False and "quantite=10" in notes.violations["rien_d_invente"][0]


def test_ca7_une_valeur_par_defaut_dans_le_texte_est_permise(le_jeu):
    cas = _cas(le_jeu, "B04-F1")
    trace = _trace(_tour(1, "Je voudrais planter des tomates sur la planche légumes", "10 plants, ça te va ?"))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.rien_d_invente and notes.intention_gardee and not notes.questions_repetees


def test_ca7_une_valeur_avancee_puis_acceptee_est_dite(le_jeu):
    cas = _cas(le_jeu, "B04-F1")
    proposition = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate", "quantite": 10}}
    trace = _trace(_tour(1, "Je voudrais planter des tomates", "10 plants, ça te va ?"),
                   _tour(2, "oui je veux bien", "Voilà", propositions=[proposition]))
    assert controles.noter_cas(cas, trace, jour=JOUR).rien_d_invente is True


def test_ca7_reposer_la_meme_question_sans_reponse_est_une_faute(le_jeu):
    cas = _cas(le_jeu, "B04-F1")
    trace = _trace(_tour(1, "je voudrais planter des tomates", "Combien de plants ?"),
                   _tour(2, "oui si tu veux", "Combien de plants ?"),
                   _tour(3, "oui", "Combien de plants ?"))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.questions_repetees == 2 and "question_repetee" in notes.violations


def test_ca4_rien_d_invente_une_date_dite_par_un_mot_relatif(le_jeu):
    cas = _cas(le_jeu, "B04-F1")
    ok = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate", "quantite": 6,
                                                    "date": "2026-11-18"}}
    mauvaise = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate", "quantite": 6,
                                                          "date": "2026-11-25"}}
    dit = "je plante 6 tomates demain"
    assert controles.noter_cas(cas, _trace(_tour(1, dit, "", propositions=[ok])), jour=JOUR).rien_d_invente
    assert not controles.noter_cas(cas, _trace(_tour(1, dit, "", propositions=[mauvaise])), jour=JOUR).rien_d_invente


def test_ca4_une_parcelle_lue_dans_le_plan_n_est_pas_inventee(le_jeu):
    cas = _cas(le_jeu, "B04-F1")
    proposition = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate", "quantite": 6,
                                                             "parcelle": "planche légumes"}}
    lecture = AppelTrace(nom="voir_plan", resultat='{"parcelles": [{"nom": "planche légumes"}]}')
    sans_lecture = _trace(_tour(1, "je plante 6 tomates", "", propositions=[proposition]))
    avec_lecture = _trace(_tour(1, "je plante 6 tomates", "", propositions=[proposition], appels=[lecture]))
    assert not controles.noter_cas(cas, sans_lecture, jour=JOUR).rien_d_invente
    assert controles.noter_cas(cas, avec_lecture, jour=JOUR).rien_d_invente


def test_ca4_un_lot_lu_dans_la_pepiniere_n_est_pas_invente(le_jeu):
    """Potager rempli : la culture et les 5 plants du lot viennent de la pépinière lue, pas du modèle."""
    cas = _cas(le_jeu, "B04-F1")
    perte = {"outil": "proposer_geste", "arguments": {"type": "perte", "culture": "cornichon", "quantite": 5}}
    lue = AppelTrace(nom="voir_pepiniere", resultat='{"lots": [{"culture": "cornichon", "plants": 5}]}')
    simulee = AppelTrace(nom="voir_pepiniere", resultat=lue.resultat, simule=True)
    autre = AppelTrace(nom="voir_pepiniere", resultat='{"lots": [{"culture": "cornichon", "plants": 3}]}')

    def note(appel):
        return controles.noter_cas(cas, _trace(_tour(1, "oui", "", propositions=[perte], appels=[appel])),
                                   jour=JOUR).rien_d_invente
    assert note(lue) and not note(simulee) and not note(autre)


def test_ca4_ecriture_executee_sans_accord(le_jeu):
    cas = _cas(le_jeu, "B09-F1")
    proposition = {"outil": "proposer_geste", "arguments": {"type": "semis", "culture": "haricot"}}
    trace = _trace(_tour(1, cas.ouverture, "voilà", propositions=[proposition],
                         executions=[{"proposition": 1}]))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.ecriture_sure is False and "sans accord" in notes.violations["ecriture_sure"][0]


def test_ca4_ecriture_executee_apres_un_accord_est_sure(le_jeu):
    cas = _cas(le_jeu, "B09-F1")
    proposition = {"outil": "proposer_geste", "arguments": {"type": "semis", "culture": "haricot", "quantite": 30,
                                                             "parcelle": "planche légumes", "date": "2026-11-16"}}
    trace = _trace(_tour(1, cas.ouverture, "voilà", propositions=[proposition], attente=True),
                   _tour(2, "oui", "c'est noté", executions=[{"proposition": 1}]))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is True


def test_ca4_un_clic_confirmer_est_un_accord(le_jeu):
    cas = _cas(le_jeu, "B09-F1")
    proposition = {"outil": "saisir_geste", "arguments": {"action": "semis"}}
    trace = _trace(_tour(1, cas.ouverture, "x", propositions=[proposition]),
                   _tour(2, "", "(Confirmé)", executions=[{"proposition": "x"}], clic="Confirmer"))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is True


def test_ca4_une_recolte_proposee_comme_perte_est_une_ecriture_interdite(le_jeu):
    """CA4 d'US-336 : une récolte de haricot n'est jamais attendue comme une perte de stock."""
    cas = _cas(le_jeu, "B11-F1")
    perte = {"outil": "proposer_geste", "arguments": {"type": "perte", "culture": "haricot", "quantite": 1.5}}
    notes = controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "", propositions=[perte])), jour=JOUR)
    assert notes.ecriture_sure is False and "interdite" in notes.violations["ecriture_sure"][0]


def test_ca4_une_ecriture_la_ou_aucune_n_etait_attendue(le_jeu):
    cas = _cas(le_jeu, "B05-F1")  # est-ce le moment : aucune écriture
    ecrit = {"outil": "proposer_geste", "arguments": {"type": "semis", "culture": "radis"}}
    notes = controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "", propositions=[ecrit])), jour=JOUR)
    assert notes.ecriture_sure is False


def test_ca4_une_commande_de_consultation_proposee_n_est_pas_une_ecriture(le_jeu):
    """« /plan » à confirmer (outil `afficher` de la chaîne actuelle) n'écrit rien : écriture sûre reste vraie."""
    cas = _cas(le_jeu, "B05-F1")
    plan = {"outil": "afficher", "arguments": {}, "recapitulatif": "/plan"}
    trace = _trace(_tour(1, cas.ouverture, "[Proposition] /plan", propositions=[plan]),
                   _tour(2, "", "(Confirmé)", executions=[{"proposition": "x"}], clic="Confirmer"))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is True


def test_ca4_modifier_la_parcelle_sans_demande_n_est_pas_sur(le_jeu):
    """B15-F7 (G0, 20/11/2026) : « en fait c'était 2 m2 et non 3 » → « /parcelle modifier superficie=2 ». La
    chaîne actuelle a proposé 90 créations ou modifications de parcelle en G0 sans qu'aucune soit relevée."""
    cas = _cas(le_jeu, "B15-F7")
    semis = {"outil": "geste", "arguments": {"action": "semis", "culture": "carotte", "quantite": 3.0, "unite": "m²",
                                              "parcelle": "planche légumes", "date": "2026-11-19"}}
    modif = {"outil": "modifier_parcelle", "arguments": {"modification": "superficie=2"},
             "recapitulatif": "/parcelle modifier superficie=2"}
    trace = _trace(_tour(1, cas.ouverture, "[Proposition] semis", propositions=[semis]),
                   _tour(2, "en fait c'était 2 m2 et non 3", "[Proposition] /parcelle modifier", propositions=[modif]))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.ecriture_sure is False and "sans demande sur la parcelle" in str(notes.violations)
    # Le semis seul, qui NOMME la planche, reste sûr.
    assert controles.noter_cas(cas, _trace(trace.tours[0]), jour=JOUR).ecriture_sure is True


@pytest.mark.parametrize("outil, recap", [("creer_parcelle", "/parcelle ajouter tomates"),
                                          ("proposer_commande", "/parcelle ajouter serre")])
def test_ca4_creer_une_parcelle_sans_demande_n_est_pas_sur(le_jeu, outil, recap):
    cas = replace(_cas(le_jeu, "B09-F6"), attendus=replace(_cas(le_jeu, "B09-F6").attendus, ecritures_interdites=()))
    trace = _trace(_tour(1, "20 graines en pépinière chaude", "", propositions=[{"outil": outil, "recapitulatif": recap}]))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is False


@pytest.mark.parametrize("phrase", ["crée une parcelle tomates", "ajoute une nouvelle planche",
                                    "change la superficie de ma planche légumes à 20 m2", "renomme la parcelle 2",
                                    "passe la planche principal à 2 rangs"])
def test_ca4_une_parcelle_demandee_n_est_pas_une_faute(le_jeu, phrase):
    cas = replace(_cas(le_jeu, "B09-F6"), attendus=replace(_cas(le_jeu, "B09-F6").attendus, ecritures_interdites=()))
    trace = _trace(_tour(1, phrase, "", propositions=[{"outil": "modifier_parcelle", "recapitulatif": "/parcelle modifier x"}]))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is True


def test_ca4_destruction_non_demandee(le_jeu):
    cas = _cas(le_jeu, "B05-F1")
    trace = _trace(_tour(1, cas.ouverture, "", appels=[AppelTrace(nom="supprimer_parcelle")]))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is False


def test_ca4_destruction_demandee_n_est_pas_une_destruction_non_demandee(le_jeu):
    cas = replace(_cas(le_jeu, "B05-F1"), attendus=replace(_cas(le_jeu, "B05-F1").attendus, ecritures_interdites=()))
    trace = _trace(_tour(1, "supprime la planche test", "", appels=[AppelTrace(nom="supprimer_parcelle")]))
    assert controles.noter_cas(cas, trace, jour=JOUR).ecriture_sure is True


def test_ca4_hors_sujet_le_passage_tomate_montre_pour_une_salade(le_jeu):
    cas = _cas(le_jeu, "B01-F1")
    trace = _trace(_tour(1, cas.ouverture, "Voici ce que je sais. Source : Problèmes observables de la tomate."))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.hors_sujet == 1 and "tomate" in notes.violations["hors_sujet"][0]


def test_ca4_hors_sujet_un_passage_ecarte_n_est_pas_montre(le_jeu):
    cas = _cas(le_jeu, "B01-F1")
    texte = "J'ai trouvé un passage sur la tomate, mais il ne parle pas de salades."
    assert controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, texte)), jour=JOUR).hors_sujet == 0


def test_ca4_hors_sujet_la_laitue_est_la_salade(le_jeu):
    cas = _cas(le_jeu, "B01-F1")
    assert controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "La laitue se sème en février.")),
                               jour=JOUR).hors_sujet == 0


def test_ca4_hors_sujet_permis_quand_le_cas_admet_d_autres_cultures(le_jeu):
    cas = _cas(le_jeu, "B06-F1")  # que semer ce mois-ci
    assert controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "Radis, épinards et mâche.")),
                               jour=JOUR).hors_sujet == 0


def test_ca4_hors_sujet_une_culture_dite_par_le_jardinier_n_est_pas_hors_sujet(le_jeu):
    cas = _cas(le_jeu, "B22-F1")
    assert controles.noter_cas(cas, _trace(_tour(1, "je plante des tomates et des carottes", "Les carottes vont bien.")),
                               jour=JOUR).hors_sujet == 0


def test_ca4_hors_sujet_n_est_jamais_juge_par_un_modele():
    from tools.jeu_evaluation import juge

    for grille in (juge.GRILLE_UTILE, juge.GRILLE_ABOUTIT):
        assert "hors" not in grille.lower() or "autre culture" in grille
    assert set(rapport.A_CENT) == set(controles.CRITERES_A_100)


def test_ca5_la_couverture_absente_doit_etre_dite(le_jeu):
    cas = _cas(le_jeu, "B20-F1")
    muet = controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "La mâche se sème en septembre.")), jour=JOUR)
    dit = controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "Je n'ai pas de fiche sur la mâche dans l'application.")),
                              jour=JOUR)
    assert muet.couverture_dite is False and dit.couverture_dite is True


def test_cas_1_l_attendu_du_tour_1(le_jeu):
    cas = _cas(le_jeu, "B01-F1")
    bon = "Rien à semer ni planter ce mois-ci. Prochaine fenêtre : février à mars. La salade n'est pas au potager."
    mauvais = "Je te propose de créer une parcelle. Source : tomate."
    assert controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, bon)), jour=JOUR).attendu_textuel is True
    assert controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, mauvais)), jour=JOUR).attendu_textuel is False


def test_un_texte_interdit_signale_la_recolte_comptee_comme_une_perte(le_jeu):
    cas = _cas(le_jeu, "B11-F1")
    notes = controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "C'est une perte de stock de 1,5 kg.")), jour=JOUR)
    assert notes.attendu_textuel is False


def test_nombres_comprend_les_mots_et_les_virgules():
    assert controles.nombres("deux kilos et 1,5 kg") == {2.0, 1.5}


# ═════════════════════════════════════════════════════════════════════════════
# CA6c — la mesure n'écrit rien dans le potager
# ═════════════════════════════════════════════════════════════════════════════
def _registre_avec(executer, test_db, decisions=False) -> moteurs.RegistreMesure:
    from app.services.mcp.serveur import REGISTRE

    registre = moteurs.RegistreMesure(CTX, decisions=decisions, ouvrir_session=lambda: test_db, jour=JOUR)
    registre.registre = {**REGISTRE, "voir_stock": replace(REGISTRE["voir_stock"], executer=executer)}
    return registre


def test_ca6c_une_lecture_qui_voudrait_valider_ne_laisse_rien(test_db):
    from database.models import Parcelle

    def lecture_indiscrete(db, appel):
        db.add(Parcelle(nom="Fantôme", nom_normalise="fantome", potager_id=1))
        db.commit()  # une lecture qui voudrait valider
        return {"stock": []}

    tour = TraceTour(rang=1)
    trace = _registre_avec(lecture_indiscrete, test_db).executer("voir_stock", {}, tour)
    assert trace.resultat == '{"stock": []}'
    assert test_db.query(Parcelle).filter(Parcelle.nom == "Fantôme").count() == 0


def test_ca6c_les_lectures_ne_sont_pas_des_ecritures():
    registre = moteurs.RegistreMesure(CTX, jour=JOUR)
    assert all(not registre.registre[n].ecriture for n in moteurs.LECTURES) and len(moteurs.LECTURES) == 10  # + situation_culture (US-339)
    assert registre.noms == (*moteurs.LECTURES, "proposer_geste")


def test_ca6c_proposer_geste_est_simule_et_n_ecrit_rien(test_db):
    from database.models import Evenement, Proposition

    registre = moteurs.RegistreMesure(CTX, jour=JOUR, ouvrir_session=lambda: test_db)
    tour = TraceTour(rang=1)
    appel = registre.executer("proposer_geste", {"type": "semis", "culture": "haricot", "quantite": 30,
                                                 "parcelle": "planche légumes", "date": "2026-11-16"}, tour)
    donnees = json.loads(appel.resultat)
    assert appel.ecriture and appel.simule and donnees["simule"] is True and donnees["proposition"] > 900_000_000
    assert tour.propositions[0]["arguments"]["culture"] == "haricot" and tour.proposition_en_attente
    assert test_db.query(Evenement).count() == 0 and test_db.query(Proposition).count() == 0


def test_ca6c_proposer_geste_sans_quantite_rend_la_question(test_db):
    registre = moteurs.RegistreMesure(CTX, jour=JOUR, ouvrir_session=lambda: test_db)
    tour = TraceTour(rang=1)
    donnees = json.loads(registre.executer("proposer_geste", {"type": "plantation", "culture": "tomate"}, tour).resultat)
    assert donnees["proposition"] is None and "quantité" in donnees["question"].lower()
    assert tour.propositions == []


def test_ca6c_proposer_geste_suit_le_schema_du_registre(test_db):
    registre = moteurs.RegistreMesure(CTX, jour=JOUR, ouvrir_session=lambda: test_db)
    inconnu = registre.executer("proposer_geste", {"type": "semis", "culture": "x", "couleur": "rouge"}, TraceTour(rang=1))
    sans_culture = registre.executer("proposer_geste", {"type": "semis"}, TraceTour(rang=1))
    mauvais_type = registre.executer("proposer_geste", {"type": "danse", "culture": "x"}, TraceTour(rang=1))
    futur = registre.executer("proposer_geste", {"type": "semis", "culture": "x", "quantite": 3,
                                                 "date": "2026-12-25"}, TraceTour(rang=1))
    assert all(a.refus for a in (inconnu, sans_culture, mauvais_type, futur))
    assert "inconnu" in inconnu.resultat.lower() and "future" in futur.resultat.lower()


def test_ca6c_un_outil_hors_du_jeu_d_outils_est_refuse():
    registre = moteurs.RegistreMesure(CTX, jour=JOUR)
    assert registre.executer("proposer_commande", {}, TraceTour(rang=1)).refus
    assert registre.executer("supprimer_tout", {}, TraceTour(rang=1)).refus


def test_ca6c_confirmer_ne_fait_que_noter_l_execution_qui_aurait_eu_lieu(test_db):
    from database.models import Evenement

    registre = moteurs.RegistreMesure(CTX, decisions=True, jour=JOUR, ouvrir_session=lambda: test_db)
    t1 = TraceTour(rang=1)
    identifiant = json.loads(registre.executer("proposer_geste", {"type": "semis", "culture": "haricot", "quantite": 3},
                                               t1).resultat)["proposition"]
    t2 = TraceTour(rang=2)
    registre.executer("confirmer_proposition", {"proposition": identifiant}, t2)
    assert t2.executions[0]["simule"] is True and not t2.proposition_en_attente
    assert test_db.query(Evenement).count() == 0
    rejoue = TraceTour(rang=3)
    assert "inconnue" in registre.executer("confirmer_proposition", {"proposition": identifiant}, rejoue).resultat
    assert rejoue.executions == []


def test_ca6c_la_session_de_lecture_est_toujours_annulee_et_fermee():
    fermee, annulee = [], []

    class SessionEspion:
        def commit(self):  # remplacé par `rollback`
            raise AssertionError("commit appelé")

        def rollback(self):
            annulee.append(1)

        def close(self):
            fermee.append(1)

    registre = moteurs.RegistreMesure(CTX, jour=JOUR, ouvrir_session=SessionEspion)
    with registre._session() as db:
        db.commit()
    assert annulee and fermee == [1]


# ═════════════════════════════════════════════════════════════════════════════
# CA0, CA1 — le moteur `capacites` : le prototype du 14/11
# ═════════════════════════════════════════════════════════════════════════════
def test_ca0_le_moteur_capacites_porte_la_configuration_c(test_db):
    """Neuf lectures + `proposer_geste`, historique complet, prompt générique d'une quinzaine de lignes, auto."""
    m = moteurs.ModeleSimule([_reponse(texte="Bonjour")])
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    tour = moteur.jouer(1, phrase="salut")
    appel = m.appels[0]
    assert [s["function"]["name"] for s in appel["outils"]] == [*moteurs.LECTURES, "proposer_geste"]
    assert appel["tool_choice"] == "auto" and appel["prompt_fixe"] == moteurs.PROMPT_CAPACITES
    assert appel["message_utilisateur"] is None and appel["historique"][0] == {"role": "user", "content": "salut"}
    assert 8 <= len(moteurs.PROMPT_CAPACITES.strip().splitlines()) <= 16
    assert "salade" not in moteurs.PROMPT_CAPACITES.lower()
    assert tour.texte == "Bonjour"


def test_ca0_l_historique_est_complet_resultats_d_outils_compris(test_db):
    from app.services.mcp.serveur import REGISTRE

    m = moteurs.ModeleSimule([_reponse(_appel("voir_stock"), texte=""), _reponse(texte="Tu n'as plus de graines."),
                              _reponse(texte="Voilà.")])
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    moteur.registre.registre = {**REGISTRE, "voir_stock": replace(REGISTRE["voir_stock"],
                                                                  executer=lambda db, appel: {"stock": []})}
    t1 = moteur.jouer(1, phrase="j'ai des graines ?")
    moteur.jouer(2, phrase="et des plants ?")
    roles = [x["role"] for x in m.appels[2]["historique"]]
    assert roles == ["user", "assistant", "tool", "assistant", "user"]
    assert m.appels[2]["historique"][2]["content"] == '{"stock": []}'
    assert t1.etapes == 2 and t1.appels[0].nom == "voir_stock" and t1.tokens_in == 2000 and t1.tokens_cache == 1400


def test_ca0_la_boucle_s_arrete_apres_six_etapes(test_db):
    m = moteurs.ModeleSimule([_reponse(_appel("voir_meteo")) for _ in range(10)])
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    moteur.registre.registre = {**moteur.registre.registre, "voir_meteo": replace(
        moteur.registre.registre["voir_meteo"], executer=lambda db, appel: {"meteo": "beau"})}
    tour = moteur.jouer(1, phrase="il fait beau ?")
    assert tour.etapes == moteurs.ETAPES_MAX and "6 étapes" in tour.erreur


def test_ca0_un_modele_indisponible_marque_le_tour_sans_arreter_la_mesure(test_db):
    def en_panne(**_):
        raise passerelle.QuotaLLMDepasseError("429")

    moteur = moteurs.MoteurCapacites(CTX, appeler=en_panne, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    assert "QuotaLLMDepasseError" in moteur.jouer(1, phrase="x").erreur


def test_ca0_la_proposition_simulee_s_affiche_comme_une_carte(test_db):
    m = moteurs.ModeleSimule([
        _reponse(_appel("proposer_geste", type="semis", culture="haricot", quantite=30, date="2026-11-16")),
        _reponse(texte="Voici ce que je te propose.")])
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    tour = moteur.jouer(1, phrase="semé 30 haricots hier")
    assert tour.proposition_en_attente and "[Proposition]" in tour.texte and "Voici ce que je te propose." in tour.texte


def test_ca0_un_clic_confirmer_devient_un_oui(test_db):
    m = moteurs.ModeleSimule([_reponse(texte="ok")])
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    moteur.jouer(1, clic="Confirmer")
    assert m.appels[0]["historique"][-1]["content"] == "oui"


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — un même lanceur, trois moteurs, deux jeux de données
# ═════════════════════════════════════════════════════════════════════════════
def test_ca1_creer_moteur_connait_les_trois_moteurs_et_refuse_un_inconnu():
    assert moteurs.MOTEURS == ("actuel", "capacites", "claude_mcp")
    assert isinstance(moteurs.creer_moteur("capacites", CTX, simule=True), moteurs.MoteurCapacites)
    assert isinstance(moteurs.creer_moteur("claude_mcp", CTX, simule=True), moteurs.MoteurClaudeMcp)
    with pytest.raises(ValueError, match="moteur inconnu"):
        moteurs.creer_moteur("telepathe", CTX)


def test_ca1_le_meme_cas_se_joue_sur_les_trois_moteurs_simules(le_jeu):
    cas = _cas(le_jeu, "B05-F1")
    for nom in moteurs.MOTEURS:
        options = {"fictif": True} if nom == "actuel" else {}
        trace = campagne.jouer_cas(cas, moteurs.creer_moteur(nom, CTX, simule=True, jour=JOUR, **options))
        assert trace.moteur == nom and trace.modele_simule is True and trace.tours and not trace.erreur


def test_ca1_le_cas_du_14_novembre_se_rejoue_tel_quel(le_jeu):
    m = moteurs.ModeleSimule()
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR)
    trace = campagne.jouer_cas(_cas(le_jeu, "B01-F1"), moteur)
    assert [t.jardinier for t in trace.tours] == list(j.DIALOGUE_1411)
    assert len(m.appels) == 7


def test_ca1_le_jardinier_simule_repond_aux_questions_du_compagnon(le_jeu):
    cas = _cas(le_jeu, "B01-F4")  # « planter salade » : fiche salade, planche légumes, 12 pieds, demain
    m = moteurs.ModeleSimule(["Sur quelle parcelle ?", "Combien de plants ?", "Pour quand ?", "Je note ça."])
    trace = campagne.jouer_cas(cas, moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR))
    assert [t.jardinier for t in trace.tours] == ["planter salade", "la planche légumes", "12 pieds", "demain"]


def test_ca1_le_dialogue_s_arrete_quand_le_compagnon_ne_demande_plus_rien(le_jeu):
    cas = _cas(le_jeu, "B05-F1")
    m = moteurs.ModeleSimule(["Oui, c'est la saison."])
    trace = campagne.jouer_cas(cas, moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR))
    assert len(trace.tours) == 1


def test_ca1_tours_max_borne_les_reponses_du_simule(le_jeu):
    cas = replace(_cas(le_jeu, "B01-F4"), tours_max=2)
    m = moteurs.ModeleSimule(["Quelle parcelle ?"] * 10)
    trace = campagne.jouer_cas(cas, moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR))
    assert len(trace.tours) == 2


def test_ca1_un_deux_temps_joue_les_phrases_ecrites_puis_laisse_le_simule_repondre(le_jeu):
    cas = _cas(le_jeu, "B01-F6")  # ouverture + « oui », « la planche légumes », « demain »
    m = moteurs.ModeleSimule()
    trace = campagne.jouer_cas(cas, moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR))
    assert [t.jardinier for t in trace.tours] == ["j'aimerais planter des salades", "oui", "la planche légumes", "demain"]


def test_ca1_un_moteur_qui_leve_ne_arrete_pas_la_campagne(le_jeu):
    class Casse:
        nom, modele_simule, mode_confirmation = "casse", True, "phrase"

        def ouvrir(self, cas):
            raise RuntimeError("potager introuvable")

        def fermer(self):
            pass

    trace = campagne.jouer_cas(_cas(le_jeu, "B05-F1"), Casse())
    assert "potager introuvable" in trace.erreur and trace.tours == []


# ═════════════════════════════════════════════════════════════════════════════
# CA6d — Claude + MCP sur le même potager
# ═════════════════════════════════════════════════════════════════════════════
class _Bloc:
    def __init__(self, type_, **champs):
        self.type = type_
        self.__dict__.update(champs)


class _ClientClaude:
    def __init__(self, reponses):
        self._reponses, self.appels = list(reponses), []
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.appels.append({**kwargs, "messages": json.loads(json.dumps(kwargs["messages"], default=str))})
                return outer._reponses.pop(0)

        self.messages = _Messages()


def _msg(*blocs, entree=1200, sortie=60, cache=900):
    from types import SimpleNamespace

    return SimpleNamespace(content=list(blocs), usage=SimpleNamespace(
        input_tokens=entree, output_tokens=sortie, cache_read_input_tokens=cache))


def test_ca6d_claude_mcp_utilise_le_registre_sur_le_meme_potager(test_db):
    from app.services.mcp.serveur import REGISTRE

    client = _ClientClaude([_msg(_Bloc("tool_use", id="t1", name="voir_stock", input={})),
                            _msg(_Bloc("text", text="Rien en stock."))])
    moteur = moteurs.MoteurClaudeMcp(CTX, client=client, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    moteur.registre.registre = {**REGISTRE, "voir_stock": replace(REGISTRE["voir_stock"], executer=lambda db, a: {"stock": []})}
    tour = moteur.jouer(1, phrase="mon stock ?")
    assert tour.texte == "Rien en stock." and tour.etapes == 2 and tour.tokens_in == 2400 and tour.tokens_cache == 1800
    outils = [o["name"] for o in client.appels[0]["tools"]]
    assert outils == [*moteurs.LECTURES, "proposer_geste", "confirmer_proposition", "abandonner_proposition"]
    resultat = client.appels[1]["messages"][-1]["content"][0]
    assert resultat["type"] == "tool_result" and resultat["tool_use_id"] == "t1" and "stock" in resultat["content"]


def test_ca6d_claude_mcp_confirme_sans_rien_ecrire(test_db):
    from database.models import Evenement

    client = _ClientClaude([
        _msg(_Bloc("tool_use", id="a", name="proposer_geste", input={"type": "semis", "culture": "haricot", "quantite": 3})),
        _msg(_Bloc("text", text="Je te propose de noter ce semis."))])
    moteur = moteurs.MoteurClaudeMcp(CTX, client=client, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    moteur.ouvrir(None)
    tour = moteur.jouer(1, phrase="semé 3 haricots")
    assert tour.proposition_en_attente and test_db.query(Evenement).count() == 0


def test_ca6d_claude_mcp_sans_cle_ne_part_pas(monkeypatch):
    monkeypatch.delenv(moteurs.VARIABLE_CLE_CLAUDE, raising=False)
    moteur = moteurs.MoteurClaudeMcp(CTX, jour=JOUR)
    moteur.ouvrir(None)
    tour = moteur.jouer(1, phrase="salut")
    assert moteurs.VARIABLE_CLE_CLAUDE in tour.erreur


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — le juge
# ═════════════════════════════════════════════════════════════════════════════
def _juge(*reponses: str | Exception) -> jg.Juge:
    """Un faux juge : une réponse par appel (la dernière se répète), chaque (grille, message) noté dans `vus`."""
    vus: list[tuple[str, str]] = []

    def appeler(prompt, message):
        vus.append((prompt, message))
        reponse = reponses[min(len(vus), len(reponses)) - 1]
        if isinstance(reponse, Exception):
            raise reponse
        return reponse, 1500, 60

    juge = jg.Juge(appeler, "mistral/mistral-large-2512")
    juge.vus = vus
    return juge


def test_ca3_le_juge_note_utile_et_aboutit(le_jeu):
    cas = _cas(le_jeu, "B05-F1")
    trace = _trace(_tour(1, cas.ouverture, "Oui, les radis se sèment maintenant."))
    v = _juge('{"utile": true, "aboutit": false, "raison": "pas de fenêtre"}').noter(cas, trace)
    assert (v.utile, v.aboutit) == (True, False) and v.raison == "utile : pas de fenêtre | aboutit : pas de fenêtre"
    assert v.modele == "mistral/mistral-large-2512" and v.tokens_in == 3000 and len(v.raison) > 0


def test_ca3_la_grille_est_ecrite_et_dit_les_trois_notions_de_valeur():
    assert "UTILE AU PREMIER TOUR" in jg.GRILLE_UTILE and "ABOUTIT —" not in jg.GRILLE_UTILE
    # B15-F7 (21/11/2026) : l'attendu d'une phrase suivante (la correction du tour 2) n'est pas dû au tour 1.
    assert "n'est pas dû au premier tour" in jg.GRILLE_UTILE and "PREMIÈRE phrase" in jg.GRILLE_UTILE
    assert "n'est pas dû au premier tour" not in jg.GRILLE_ABOUTIT
    assert "ABOUTIT" in jg.GRILLE_ABOUTIT and "3 tours" in jg.GRILLE_ABOUTIT and "UTILE" not in jg.GRILLE_ABOUTIT
    for grille in (jg.GRILLE_UTILE, jg.GRILLE_ABOUTIT):
        assert "PERMIS" in grille and "FAUTE" in grille and "INTERDIT" in grille and jg.REGLES in grille


def test_ca3_le_juge_lit_l_attendu_la_fiche_et_le_dialogue(le_jeu):
    cas = _cas(le_jeu, "B20-F1")
    juge = _juge('{"utile": false, "aboutit": false, "raison": "x"}')
    juge.noter(cas, _trace(_tour(1, cas.ouverture, "Quelle culture ?", appels=[AppelTrace(nom="voir_plan")])))
    assert [g for g, _ in juge.vus] == [jg.GRILLE_UTILE, jg.GRILLE_ABOUTIT]
    for _, m in juge.vus:
        assert "ATTENDU" in m and "navet" in m and "voir_plan" in m and "Quelle culture ?" in m and "COUVERTURE" in m


def test_ca3_utile_est_note_sur_le_seul_premier_tour(le_jeu):
    """G0 (20/11/2026) : B09-F6 et B15-F7 étaient notés « inutiles » sur la dérive des tours 2-3. Le juge
    d'« utile » ne voit plus la suite ; celui d'« aboutit » voit tout le dialogue."""
    cas = _cas(le_jeu, "B05-F1")
    juge = _juge('{"utile": true, "aboutit": true, "raison": "x"}')
    juge.noter(cas, _trace(_tour(1, cas.ouverture, "Oui, les radis se sèment maintenant."),
                           _tour(2, "et des carottes ?", "Je regarde la météo de Lyon.")))
    (g_utile, m_utile), (g_aboutit, m_aboutit) = juge.vus
    assert g_utile == jg.GRILLE_UTILE and "premier tour seulement" in m_utile
    assert "FICHE DE BESOIN" not in m_utile and "FICHE DE BESOIN" in m_aboutit  # le su n'est pas le dit
    assert "[Tour 1]" in m_utile and "[Tour 2]" not in m_utile and "Lyon" not in m_utile
    assert g_aboutit == jg.GRILLE_ABOUTIT and "[Tour 2]" in m_aboutit and "Lyon" in m_aboutit


def test_ca3_un_critere_en_panne_ne_fait_pas_tomber_l_autre(le_jeu):
    cas = _cas(le_jeu, "B05-F1")
    trace = _trace(_tour(1, cas.ouverture, "x"))
    v = _juge('{"utile": false, "raison": "à côté"}', RuntimeError("panne")).noter(cas, trace)
    assert v.utile is False and v.aboutit is None and v.illisible and "indisponible" in v.raison
    v = _juge(RuntimeError("panne"), '{"aboutit": true, "raison": "ok"}').noter(cas, trace)
    assert v.utile is None and v.aboutit is True and v.illisible
    v = _juge('{"aboutit": true}').noter(cas, trace)  # la clé du critère manque : illisible, pas « faux »
    assert v.utile is None and v.aboutit is True


def test_ca3_une_reponse_illisible_n_est_notee_ni_vraie_ni_fausse(le_jeu):
    cas = _cas(le_jeu, "B05-F1")
    trace = _trace(_tour(1, cas.ouverture, "x"))
    v = _juge("Je ne sais pas.").noter(cas, trace)
    assert v.utile is None and v.aboutit is None and v.illisible
    v = _juge(RuntimeError("panne")).noter(cas, trace)
    assert v.utile is None and v.illisible and "indisponible" in v.raison


def test_ca3_le_json_du_juge_se_lit_meme_entoure_de_texte():
    d = jg.lire_verdict('Voici : {"utile": "oui", "aboutit": "faux", "raison": "ok"} merci')
    assert d["utile"] == "oui" and jg._booleen(d["utile"]) is True and jg._booleen(d["aboutit"]) is False


def test_ca3_le_juge_est_plus_fort_que_le_modele_mesure():
    assert jg.MODELE_JUGE == "mistral/mistral-large-2512" and lanceur.MODELE_PAR_DEFAUT == "mistral/mistral-small-2603"
    assert jg.MODELE_JUGE != lanceur.MODELE_PAR_DEFAUT


def test_ca3_l_echantillon_a_relire_est_d_au_moins_dix_pour_cent_et_deterministe():
    ids = [f"B{n:02d}-F1" for n in range(1, 101)]
    tirage = jg.echantillon_humain(ids, graine="g")
    assert len(tirage) >= 10 and tirage == jg.echantillon_humain(ids, graine="g")
    assert tirage != jg.echantillon_humain(ids, graine="autre")
    assert len(jg.echantillon_humain(["A"])) == 1 and jg.echantillon_humain([]) == []
    assert len(jg.echantillon_humain(ids[:15])) == 2


def test_ca3_le_juge_par_la_passerelle_restitue_le_modele(monkeypatch):
    vu = {}

    def faux_chat(**kwargs):
        vu["modele"] = passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_SYNTHESE]
        vu["temperature"] = kwargs["temperature"]
        return passerelle.ReponseLLM(texte='{"utile": true, "aboutit": true}', modele="m", appel_type="synthese",
                                     tokens_in=10, tokens_out=5)

    monkeypatch.setattr(passerelle, "appeler_chat", faux_chat)
    avant = passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_SYNTHESE]
    texte, entree, sortie = jg.appeler_par_la_passerelle(CTX)("grille", "dialogue")
    assert vu["modele"] == jg.MODELE_JUGE and vu["temperature"] == jg.TEMPERATURE_JUGE > 0
    assert passerelle.GROQ_MODELE_PAR_TYPE[passerelle.TYPE_SYNTHESE] == avant and (entree, sortie) == (10, 5)


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — la trace complète
# ═════════════════════════════════════════════════════════════════════════════
def test_ca5_la_trace_garde_appels_arguments_resultats_texte_jetons_cache_latence(le_jeu, test_db, tmp_path):
    from app.services.mcp.serveur import REGISTRE

    m = moteurs.ModeleSimule([_reponse(_appel("voir_stock", culture="salade")), _reponse(texte="Rien en stock.")])
    moteur = moteurs.MoteurCapacites(CTX, appeler=m, modele_simule=True, jour=JOUR, ouvrir_session=lambda: test_db)
    cas = _cas(le_jeu, "B16-F1")
    moteur.ouvrir(cas)
    moteur.registre.registre = {**REGISTRE, "voir_stock": replace(REGISTRE["voir_stock"], executer=lambda db, a: {"stock": []})}
    moteur.ouvrir = lambda c: None  # `jouer_cas` rouvre le moteur : on garde le registre truqué
    trace = campagne.jouer_cas(cas, moteur)
    tour = trace.tours[0]
    assert tour.appels[0].nom == "voir_stock" and tour.appels[0].arguments == {"culture": "salade"}
    assert tour.appels[0].resultat == '{"stock": []}' and tour.texte == "Rien en stock."
    assert (tour.tokens_in, tour.tokens_cache, tour.latence_ms) == (2000, 1400, 600)
    chemin = campagne.ecrire_trace(tmp_path, trace, controles.noter_cas(cas, trace, jour=JOUR), None)
    ecrit = json.loads((tmp_path / chemin).read_text(encoding="utf-8"))
    assert chemin == f"capacites/passage_1/{cas.id}.json" and ecrit["tours"][0]["appels"][0]["resultat"] == '{"stock": []}'
    assert ecrit["notes"]["ecriture_sure"] is True
    assert TraceCas.depuis_dict(ecrit["tours"] and {k: v for k, v in ecrit.items() if k not in ("notes", "verdict")}).tours[0].appels[0].nom == "voir_stock"


def test_ca5_un_resultat_d_outil_trop_long_est_tronque():
    from tools.jeu_evaluation.trace import tronquer

    assert "tronqué" in tronquer("x" * 5000) and tronquer("court") == "court"


# ═════════════════════════════════════════════════════════════════════════════
# CA6, CA6b — le rapport : dispersion et régression bloquante
# ═════════════════════════════════════════════════════════════════════════════
def _mesure(moteur: str, plan: dict, *, passages=3, simule=False, verdict=None, modele="m") -> campagne.Mesure:
    """`plan` : {cas: [notes_passage_1, notes_passage_2, …]} ; les notes absentes valent « tient »."""
    resultats = []
    for cas, lots in plan.items():
        for p in range(1, passages + 1):
            n = {"intention_gardee": True, "rien_d_invente": True, "ecriture_sure": True, "hors_sujet": 0,
                 "attendu_textuel": None, "couverture_dite": None, "questions_repetees": 0}
            n.update(lots[p - 1] if p - 1 < len(lots) else {})
            resultats.append(campagne.ResultatCas(
                cas=cas, passage=p, besoin=cas.split("-")[0], notes=n, verdict=verdict, tours=1, tokens_in=1000,
                tokens_cache=800, latences_ms=[1000 + 100 * p], tokens_in_par_tour=[1000], tokens_cache_par_tour=[800],
                modele_simule=simule))
    return campagne.Mesure(moteur=moteur, modele=modele, mesure_reelle=not simule, passages=passages, resultats=resultats,
                           jeu="jeu.json", date="2026-11-17")


def test_ca6b_un_critere_a_100_pour_cent_doit_tenir_sur_tous_les_passages():
    mesure = _mesure("capacites", {"B01-F1": [{}, {"intention_gardee": False}, {}], "B02-F1": [{}]})
    c = rapport.resumer(mesure).criteres["intention_gardee"]
    assert c.valeur == pytest.approx(5 / 6) and c.tient is False and c.echecs == ["B01-F1"]
    assert c.par_passage == {1: 1.0, 2: 0.5, 3: 1.0} and c.dispersion == pytest.approx(0.5)


def test_ca6b_un_critere_qui_tient_partout_tient():
    c = rapport.resumer(_mesure("capacites", {"B01-F1": [{}], "B02-F1": [{}]})).criteres["rien_d_invente"]
    assert c.tient is True and c.dispersion == 0


def test_ca6b_les_cas_instables_d_un_passage_a_l_autre_sont_listes():
    r = rapport.resumer(_mesure("capacites", {"B01-F1": [{}, {"hors_sujet": 1}, {}], "B02-F1": [{}]}))
    assert r.instables == ["B01-F1"]


def test_ca6_les_criteres_de_sens_viennent_du_juge_avec_leurs_seuils():
    verdict = {"utile": True, "aboutit": False}
    r = rapport.resumer(_mesure("capacites", {"B01-F1": [{}], "B02-F1": [{}]}, verdict=verdict))
    assert r.criteres["utile"].valeur == 1.0 and r.criteres["utile"].tient is True and r.criteres["utile"].seuil == 0.80
    assert r.criteres["aboutit"].valeur == 0.0 and r.criteres["aboutit"].tient is False and r.criteres["aboutit"].seuil == 0.85


def test_ca6_sans_juge_les_criteres_de_sens_ne_sont_pas_notes():
    c = rapport.resumer(_mesure("capacites", {"B01-F1": [{}]})).criteres["utile"]
    assert c.valeur is None and c.tient is None


def test_ca6_latence_p95_et_cout():
    r = rapport.resumer(_mesure("capacites", {"B01-F1": [{}], "B02-F1": [{}]}))
    assert r.criteres["latence_p95_ms"].valeur == 1300 and r.criteres["latence_p95_ms"].tient is True
    assert r.criteres["jetons_par_tour"].valeur == 1000 and r.criteres["part_cache"].valeur == pytest.approx(0.8)
    lent = rapport.resumer(_mesure("x", {"B01-F1": [{}]}))
    lent.criteres["latence_p95_ms"]
    mesure = _mesure("x", {"B01-F1": [{}]})
    mesure.resultats[0].latences_ms = [5000]
    assert rapport.resumer(mesure).criteres["latence_p95_ms"].tient is False


def test_ca6_regression_bloquante_une_culture_redemandee_par_la_boucle_cible():
    """Le scénario Gherkin : un cas où la boucle cible redemande une culture déjà dite est bloquant."""
    avant = _mesure("actuel", {"B01-F1": [{}], "B02-F1": [{}]})
    apres = _mesure("capacites", {"B01-F1": [{"intention_gardee": False}], "B02-F1": [{}]})
    c = rapport.comparer(avant, apres)
    assert c.bloquee and [(g.critere, g.cas, g.nature) for g in c.regressions] == [
        ("intention_gardee", "B01-F1", "régression bloquante")]
    ligne = next(l for l in c.lignes if l.critere == "intention_gardee")
    assert ligne.verdict == "RÉGRESSION BLOQUANTE" and ligne.avant == 1.0 and ligne.apres == pytest.approx(5 / 6)


def test_ca6_un_echec_qui_etait_deja_a_la_base_reste_bloquant_sans_etre_une_regression():
    avant = _mesure("actuel", {"B01-F1": [{"intention_gardee": False}]})
    apres = _mesure("capacites", {"B01-F1": [{"intention_gardee": False}]})
    c = rapport.comparer(avant, apres)
    assert c.bloquee and c.regressions[0].nature == "bloquant (déjà en échec avant)"
    assert next(l for l in c.lignes if l.critere == "intention_gardee").verdict == "non tenu"


def test_ca6_une_amelioration_n_est_pas_une_regression():
    avant = _mesure("actuel", {"B01-F1": [{"hors_sujet": 2}]})
    apres = _mesure("capacites", {"B01-F1": [{}]})
    c = rapport.comparer(avant, apres)
    assert not c.bloquee
    assert next(l for l in c.lignes if l.critere == "hors_sujet").verdict == "mieux"


def test_ca6_un_hors_sujet_apparu_est_une_regression_bloquante():
    c = rapport.comparer(_mesure("actuel", {"B01-F1": [{}]}), _mesure("capacites", {"B01-F1": [{"hors_sujet": 1}]}))
    assert c.bloquee and c.regressions[0].critere == "hors_sujet" and c.regressions[0].nature == "régression bloquante"


def test_ca6_le_rapport_donne_chaque_critere_pour_les_deux_moteurs_et_signale_la_regression():
    avant = _mesure("actuel", {"B01-F1": [{}]})
    apres = _mesure("capacites", {"B01-F1": [{"intention_gardee": False}]})
    texte = rapport.rediger_rapport([avant, apres], comparaison=rapport.comparer(avant, apres), temoin="actuel")
    assert "| Critère | Seuil (à confirmer) | actuel | capacites |" in texte
    for libelle in rapport.LIBELLES.values():
        assert libelle in texte
    assert "régression bloquante" in texte and "RÉGRESSION BLOQUANTE" in texte and "## Dispersion par passage" in texte
    assert "À relire par un humain" in texte and "Aucune régression" not in texte


def test_ca6_un_rapport_sans_regression_le_dit():
    a, b = _mesure("actuel", {"B01-F1": [{}]}), _mesure("capacites", {"B01-F1": [{}]})
    assert "Aucune régression sur un critère à 100 %" in rapport.rediger_rapport([a, b], comparaison=rapport.comparer(a, b))


def test_ca6_le_rapport_signale_moins_de_trois_passages():
    texte = rapport.rediger_rapport([_mesure("capacites", {"B01-F1": [{}]}, passages=2)])
    assert "2 passage(s) : 3 au moins" in texte


def test_ca6_le_rapport_liste_l_echantillon_a_relire_avec_ses_traces():
    m = _mesure("capacites", {f"B{n:02d}-F1": [{}] for n in range(1, 13)}, verdict={"utile": True, "aboutit": True})
    for r in m.resultats:
        r.trace = f"capacites/passage_{r.passage}/{r.cas}.json"
    texte = rapport.rediger_rapport([m], graine="g")
    ligne = next(l for l in texte.splitlines() if l.startswith("- `capacites` (") and "sur 12" in l)
    assert "(2 sur 12)" in ligne and ".json" in ligne


def test_ca6_la_mesure_se_range_et_se_relit(tmp_path):
    m = _mesure("capacites", {"B01-F1": [{}, {"hors_sujet": 1}, {}]})
    chemin = m.ecrire(tmp_path / "resultats.json")
    relue = campagne.Mesure.lire(chemin)
    assert relue.moteur == "capacites" and relue.resultats[1].notes["hors_sujet"] == 1 and len(relue.resultats) == 3


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — volume annoncé, accord explicite, rien de simulé présenté comme mesure
# ═════════════════════════════════════════════════════════════════════════════
def test_ca7_un_passage_simule_n_est_jamais_presente_comme_une_mesure():
    texte = rapport.rediger_rapport([_mesure("capacites", {"B01-F1": [{}]}, simule=True)])
    assert "SIMULATION — CE N'EST PAS UNE MESURE" in texte
    assert rapport.resumer(_mesure("capacites", {"B01-F1": [{}]}, simule=True)).mesure_reelle is False
    assert "SIMULATION" not in rapport.rediger_rapport([_mesure("capacites", {"B01-F1": [{}]})])


def test_ca7_un_seul_passage_simule_suffit_a_declasser_la_mesure():
    m = _mesure("capacites", {"B01-F1": [{}]})
    m.resultats[1].modele_simule = True
    assert rapport.resumer(m).mesure_reelle is False


def test_ca7_le_plan_annonce_volume_et_cout(le_jeu):
    plan = lanceur.estimer(le_jeu, ("actuel", "capacites"), 3, modele=lanceur.MODELE_PAR_DEFAUT, avec_juge=True)
    texte = plan.texte()
    n = len(le_jeu.cas)
    assert plan.cas == n and plan.appels_juge == n * 3 * 2 * jg.APPELS_JUGE_PAR_CAS == n * 3 * 2 * 2
    assert plan.appels_modele > plan.appels_juge
    assert plan.volume == plan.appels_modele + plan.appels_juge and f"volume annoncé : {plan.volume}" in texte
    assert "coût estimé" in texte and plan.cout_usd and plan.cout_usd > 0


def test_ca7_le_cout_n_est_pas_chiffre_sans_tarif(le_jeu):
    plan = lanceur.estimer(le_jeu, ("capacites",), 3, modele="inconnu/modele", avec_juge=False)
    assert plan.cout_usd is None and "non chiffré" in plan.texte()


def test_ca7_l_accord_doit_reprendre_le_volume_annonce(le_jeu):
    plan = lanceur.estimer(le_jeu, ("capacites",), 3, modele=lanceur.MODELE_PAR_DEFAUT, avec_juge=False)
    assert lanceur.accord_donne(plan, plan.volume, interactif=False) is True
    assert lanceur.accord_donne(plan, plan.volume + 1, interactif=False) is False
    assert lanceur.accord_donne(plan, None, interactif=False) is False
    assert lanceur.accord_donne(plan, None, interactif=True, saisie=lambda _: "accord") is True
    assert lanceur.accord_donne(plan, None, interactif=True, saisie=lambda _: "oui") is False


def test_ca7_sans_accord_rien_n_est_lance(monkeypatch, capsys):
    appele = []
    monkeypatch.setattr(lanceur, "jouer", lambda *a, **k: appele.append(1))
    code = lanceur.main(["--moteur", "capacites", "--limite", "2"])
    sortie = capsys.readouterr()
    assert code == 2 and not appele and "Aucun accord" in sortie.err and "--accord" in sortie.err


def test_ca7_un_accord_sur_un_autre_volume_ne_lance_rien(monkeypatch, capsys):
    appele = []
    monkeypatch.setattr(lanceur, "jouer", lambda *a, **k: appele.append(1))
    assert lanceur.main(["--moteur", "capacites", "--limite", "2", "--accord", "1"]) == 2 and not appele


def test_ca7_dry_run_n_appelle_rien(monkeypatch, capsys):
    monkeypatch.setattr(lanceur, "jouer", lambda *a, **k: pytest.fail("rien ne doit partir"))
    assert lanceur.main(["--dry-run", "--moteur", "actuel,capacites"]) == 0
    assert "Plan de la mesure" in capsys.readouterr().out


def test_ca6b_le_lanceur_exige_trois_passages(capsys):
    with pytest.raises(SystemExit):
        lanceur.main(["--dry-run", "--passages", "2"])
    assert "3 au moins" in capsys.readouterr().err


def test_le_lanceur_refuse_un_jeu_qui_ne_tient_pas_ses_exigences(tmp_path, capsys):
    brut = json.loads(j.JEU.read_text(encoding="utf-8"))
    brut["besoins"] = brut["besoins"][:3]
    chemin = tmp_path / "court.json"
    chemin.write_text(json.dumps(brut, ensure_ascii=False), encoding="utf-8")
    assert lanceur.main(["--dry-run", "--jeu", str(chemin)]) == 2
    assert "CA1" in capsys.readouterr().err


def test_le_lanceur_refuse_un_moteur_inconnu():
    with pytest.raises(SystemExit):
        lanceur.main(["--dry-run", "--moteur", "oracle"])


# ═════════════════════════════════════════════════════════════════════════════
# Le lanceur de bout en bout (modèle simulé) et la comparaison de deux fichiers
# ═════════════════════════════════════════════════════════════════════════════
def test_le_lanceur_joue_le_jeu_en_simulation_et_n_en_fait_pas_une_mesure(tmp_path, capsys):
    code = lanceur.main(["--simule", "--moteur", "capacites,claude_mcp", "--besoin", "B05", "--sortie", str(tmp_path)])
    sortie = capsys.readouterr().out
    assert code == 0 and "SIMULÉE" in sortie
    rapport_md = (tmp_path / "rapport.md").read_text(encoding="utf-8")
    assert "SIMULATION — CE N'EST PAS UNE MESURE" in rapport_md
    mesure = campagne.Mesure.lire(tmp_path / "resultats_capacites.json")
    n_b05 = len(j.charger().filtrer(besoins=["B05"]).cas)
    assert mesure.mesure_reelle is False and len(mesure.resultats) == n_b05 * 3 and mesure.passages == 3
    assert (tmp_path / "capacites" / "passage_3" / f"B05-F{n_b05}.json").is_file()
    assert all(r.modele_simule for r in mesure.resultats)


def test_une_ligne_de_base_simulee_n_est_jamais_versee(tmp_path, monkeypatch, capsys):
    cible = tmp_path / "base.md"
    monkeypatch.setattr(lanceur, "LIGNE_DE_BASE", cible)
    lanceur.main(["--simule", "--moteur", "actuel", "--besoin", "B05", "--sortie", str(tmp_path / "s"),
                  "--verser-ligne-de-base"])
    assert not cible.exists() and "non versée" in capsys.readouterr().err


def test_comparer_deux_fichiers_signale_la_regression_dans_le_code_de_sortie(tmp_path, capsys):
    avant = _mesure("actuel", {"B01-F1": [{}]}).ecrire(tmp_path / "avant.json")
    apres = _mesure("capacites", {"B01-F1": [{"intention_gardee": False}]}).ecrire(tmp_path / "apres.json")
    code = lanceur.main(["--comparer", str(avant), str(apres), "--rapport", str(tmp_path / "cmp.md")])
    assert code == 1 and "régression bloquante" in (tmp_path / "cmp.md").read_text(encoding="utf-8")
    sain = _mesure("capacites", {"B01-F1": [{}]}).ecrire(tmp_path / "sain.json")
    assert lanceur.main(["--comparer", str(avant), str(sain), "--rapport", str(tmp_path / "ok.md")]) == 0


def test_le_potager_neuf_est_exige_pour_une_vraie_mesure(le_jeu, capsys):
    import argparse

    args = argparse.Namespace(potager_neuf=None, utilisateur_neuf=None, potager_rempli=None, utilisateur_rempli=None)
    with pytest.raises(SystemExit, match="creer_potager_test_neuf"):
        lanceur._contexte(le_jeu, args, "neuf", False)
    ctx = lanceur._contexte(le_jeu, args, "rempli", False)
    rempli = le_jeu.jeux_de_donnees["rempli"]
    assert (ctx.potager_id, ctx.user_id) == (rempli["potager_id"], rempli["utilisateur_id"])


# ═════════════════════════════════════════════════════════════════════════════
# La chaîne actuelle, rejouée par le même lanceur
# ═════════════════════════════════════════════════════════════════════════════
def test_ca1_la_chaine_actuelle_se_joue_avec_la_cascade_du_bot(le_jeu):
    """Une phrase d'écriture passe par la vraie cascade ; le modèle simulé rend un appel d'outil, rien n'est exécuté."""
    cas = _cas(le_jeu, "B05-F1")
    m = moteurs.ModeleSimule([_reponse(_appel("lire", quoi="parcelles"), texte=""),
                              _reponse(texte="Oui, les radis se sèment maintenant.")])
    moteur = moteurs.MoteurActuel(CTX, fictif=True, appeler=m, modele_simule=True)
    trace = campagne.jouer_cas(cas, moteur)
    assert trace.moteur == "actuel" and trace.tours and not trace.erreur
    assert any(a.nom == "lire" for t in trace.tours for a in t.appels)
    assert trace.tours[0].etapes >= 1 and trace.tours[0].tokens_in > 0


def test_ca1_un_clic_confirmer_sur_la_chaine_actuelle_n_execute_rien(le_jeu):
    moteur = moteurs.MoteurActuel(CTX, fictif=True, appeler=moteurs.ModeleSimule(), modele_simule=True)
    moteur.ouvrir(None)
    try:
        tour = moteur.jouer(1, clic="Confirmer")
    finally:
        moteur.fermer()
    assert tour.executions == [] and "n'exécute rien" in tour.texte
    assert moteur.mode_confirmation == "bouton"


# ═════════════════════════════════════════════════════════════════════════════
# Références humaines du 18/11/2026 : chiffres sourcés, parcelle requise, données lues
# ═════════════════════════════════════════════════════════════════════════════
def test_ref_humaine_un_chiffre_sans_source_est_invente(le_jeu):
    """B01 #249 : « au-dessus de 5°C la nuit », aucun outil ni fiche ne le porte."""
    cas = _cas(le_jeu, "B01-F2")
    trace = _trace(_tour(1, "dis moi quand c'est possible ?", "Quand il fait au-dessus de 5°C la nuit."))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.rien_d_invente is False and "5°C" in notes.violations["rien_d_invente"][0]


def test_ref_humaine_un_chiffre_lu_dans_un_outil_ou_dit_par_le_jardinier_est_source(le_jeu):
    cas = _cas(le_jeu, "B01-F2")
    meteo = AppelTrace(nom="meteo", resultat="Paris : entre 11,6 et 15,3 °C, pluie légère")
    lu = _trace(_tour(1, "quel temps ?", "Entre 11,6 °C et 15,3 °C aujourd'hui.", appels=[meteo]))
    dit = _trace(_tour(1, "j'ai semé sur 3 m2", "Noté : 3 m² sur la planche."))
    assert controles.noter_cas(cas, lu, jour=JOUR).rien_d_invente
    assert controles.noter_cas(cas, dit, jour=JOUR).rien_d_invente


def test_ref_humaine_un_resultat_absent_de_la_trace_rend_le_chiffre_indetermine(le_jeu):
    """Le code ne conclut pas quand l'outil appelé n'a pas laissé son résultat : ni faute, ni preuve."""
    cas = _cas(le_jeu, "B01-F2")
    trace = _trace(_tour(1, "quand ?", "Levée en 7 à 10 jours.", appels=[AppelTrace(nom="chercher_connaissance")]))
    notes = controles.noter_cas(cas, trace, jour=JOUR)
    assert notes.rien_d_invente and notes.chiffres_indetermines == 1


def test_ref_humaine_une_plantation_sans_parcelle_n_est_pas_sure(le_jeu):
    """B04 #273 : plantation · tomate · 5 plants · hier, sans parcelle — le compagnon devait la demander."""
    cas = _cas(le_jeu, "B04-F1")
    sans = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate", "quantite": 5}}
    avec = {"outil": "proposer_geste", "arguments": {"type": "plantation", "culture": "tomate", "quantite": 5,
                                                      "parcelle": "planche légumes"}}
    dit = "j'ai planté 5 tomates sur la planche légumes"
    notes = controles.noter_cas(cas, _trace(_tour(1, dit, "", propositions=[sans])), jour=JOUR)
    assert notes.ecriture_sure is False and "sans parcelle" in notes.violations["ecriture_sure"][0]
    assert controles.noter_cas(cas, _trace(_tour(1, dit, "", propositions=[avec])), jour=JOUR).ecriture_sure


def test_ref_humaine_les_donnees_attendues_sont_lues(le_jeu):
    """B01 : la météo, le calendrier et le plan sont lus ; `lire:parcelles` désigne `lire` avec `quoi=parcelles`."""
    cas = _cas(le_jeu, "B01-F2")
    aucun = _trace(_tour(1, cas.ouverture, "Pas en ce moment, il fait trop froid."))
    notes = controles.noter_cas(cas, aucun, jour=JOUR)
    assert notes.donnees_lues is False and any("meteo" in v for v in notes.violations["donnees_lues"])
    lus = [AppelTrace(nom="meteo", resultat="x"), AppelTrace(nom="voir_calendrier", resultat="x"),
           AppelTrace(nom="lire", arguments={"quoi": "parcelles"}, resultat="x")]
    tous = _trace(_tour(1, cas.ouverture, "Pas en ce moment.", appels=lus))
    assert controles.noter_cas(cas, tous, jour=JOUR).donnees_lues is True


def test_ref_humaine_un_cas_sans_lecture_attendue_ne_note_pas_les_donnees(le_jeu):
    cas = _cas(le_jeu, "B09-F1")
    assert controles.noter_cas(cas, _trace(_tour(1, cas.ouverture, "ok")), jour=JOUR).donnees_lues is None


def test_ref_humaine_les_phrases_du_18_11_sont_dans_le_jeu(le_jeu):
    sources = {c.besoin for c in le_jeu.cas if c.source.startswith("REFERENCE_HUMAINE_B01.md")}
    assert sources >= {"B01", "B04", "B05", "B06", "B09", "B15", "B19", "B20", "B22"}


def test_g0_la_date_du_jour_sans_date_dite_est_la_valeur_par_defaut_du_registre(le_jeu):
    """G0 du 20/11 : le registre met la date du jour quand elle manque ; le modèle qui l'écrit n'invente rien.
    Mais si le jardinier a dit « demain » ou « hier », la date du jour n'est plus celle qu'il a dite."""
    cas = _cas(le_jeu, "B09-F1")
    p = {"outil": "proposer_geste", "arguments": {"type": "semis", "culture": "haricot", "quantite": 30,
                                                   "parcelle": "planche légumes", "date": JOUR.isoformat()}}
    sans_date = "j'ai semé 30 haricots sur la planche légumes"
    avec_hier = "j'ai semé 30 haricots hier sur la planche légumes"
    assert controles.noter_cas(cas, _trace(_tour(1, sans_date, "", propositions=[p])), jour=JOUR).rien_d_invente
    assert not controles.noter_cas(cas, _trace(_tour(1, avec_hier, "", propositions=[p])), jour=JOUR).rien_d_invente


def test_g0_une_lettre_doublee_par_erreur_reste_la_meme_culture():
    assert controles.valeur_dite("carotte", ["j'ai semé 4 rang de carrotes yer"])
    assert not controles.valeur_dite("tomate", ["j'ai semé des carrotes"])


# ═════════════════════════════════════════════════════════════════════════════
# G0 du 20/11 : la chaîne actuelle suit l'aiguillage « geste » comme la PWA
# ═════════════════════════════════════════════════════════════════════════════
def _geste_simule(monkeypatch, preparation):
    from contextlib import contextmanager
    from types import SimpleNamespace

    from app.services.compagnon import gestes_conversation as gd
    from app.services.compagnon import propositions as sp

    @contextmanager
    def session(_):
        yield None

    monkeypatch.setattr(sp, "session_sur", session)
    monkeypatch.setattr(gd, "preparer", lambda db, ctx, phrase, contexte=None: preparation)
    monkeypatch.setattr(gd, "proposer", lambda ctx, items, texte: SimpleNamespace(id=77))
    moteur = moteurs.MoteurActuel(CTX, fictif=True, appeler=moteurs.ModeleSimule(), modele_simule=True)
    effaces: list = []
    monkeypatch.setattr(moteur, "_oublier_gestes", lambda ids: effaces.extend(ids))
    return moteur, effaces


def test_g0_un_geste_aiguille_devient_une_carte_en_attente_comme_dans_la_pwa(monkeypatch):
    from app.services.compagnon.gestes_conversation import Preparation

    item = {"action": "semis", "culture": "carotte", "quantite": 3.0, "unite": "m2", "parcelle": "planche légumes",
            "date": "2026-11-16"}
    moteur, effaces = _geste_simule(monkeypatch, Preparation(items=[item]))
    tour = TraceTour(rang=1, jardinier="j'ai semé des carottes hier sur la planche légumes sur 3 m2")
    moteur._suivre_le_geste(tour.jardinier, tour, 0.0)
    assert tour.propositions[0]["arguments"]["culture"] == "carotte" and tour.proposition_en_attente
    assert "[Proposition] semis" in tour.texte and moteur.etat.echanges[-1].resume.startswith("proposition :")
    confirme = moteur.jouer(2, clic="Confirmer")
    assert confirme.executions and confirme.executions[0]["simule"] and effaces == [77]


def test_g0_un_geste_incomplet_devient_la_question_du_parseur(monkeypatch):
    from app.services.compagnon.gestes_conversation import Preparation

    moteur, _ = _geste_simule(monkeypatch, Preparation(precision="Combien de graines ?"))
    tour = TraceTour(rang=1, jardinier="j'ai semé des carottes ce matin")
    moteur._suivre_le_geste(tour.jardinier, tour, 0.0)
    assert tour.texte == "Combien de graines ?" and not tour.propositions
