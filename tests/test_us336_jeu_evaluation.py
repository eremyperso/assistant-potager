"""
tests/test_us336_jeu_evaluation.py
[US-336] Constituer le jeu d'évaluation du compagnon : besoins × formulations × tours.

Ce qui est testé : le FICHIER du jeu (chaque critère d'acceptance se lit dans `controler_exigences` et se vérifie
ici sur le vrai fichier), son chargeur, le contrôle « un cas renouvelable n'est dans aucun exemple de prompt », le
script du potager neuf (rejouable, refusé hors base de test) et la documentation du format. Aucun modèle n'est appelé.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from tools.jeu_evaluation import jeu as j

RACINE = Path(__file__).resolve().parent.parent
DOC = RACINE / "docs" / "EPIC - AGENT INTERPRETEUR" / "JEU_EVALUATION_COMPAGNON.md"


@pytest.fixture(scope="module")
def le_jeu() -> j.Jeu:
    return j.charger()


def _par_besoin(jeu: j.Jeu) -> dict[str, list[j.Cas]]:
    rangs: dict[str, list[j.Cas]] = {}
    for c in jeu.cas:
        rangs.setdefault(c.besoin, []).append(c)
    return rangs


# ── CA1 ──────────────────────────────────────────────────────────────────────
def test_le_jeu_tient_toutes_ses_exigences(le_jeu):
    assert j.controler_exigences(le_jeu) == []


def test_ca1_vingt_besoins_et_cinq_formulations_chacun(le_jeu):
    besoins = _par_besoin(le_jeu)
    assert len(besoins) >= 20
    assert all(5 <= len(cas) <= 10 for cas in besoins.values())


def test_ca1_chaque_cas_porte_sa_fiche_et_ses_attendus(le_jeu):
    for c in le_jeu.cas:
        assert isinstance(c.fiche, dict)
        assert c.attendus.bonne_reponse, c.id
        assert c.jeu_de_donnees in j.JEUX_DE_DONNEES


def test_ca1_les_besoins_de_la_story_sont_couverts(le_jeu):
    libelles = " ".join(j.normaliser(b["libelle"]) for b in le_jeu.besoins)
    for attendu in ("planter", "semer", "moment", "ce mois", "que faire", "arroser", "semis", "plantation",
                    "recolte", "perte", "corriger", "stock", "carnet", "symptome", "fonction"):
        assert attendu in libelles, attendu


def test_ca1_les_genres_de_formulation_sont_tous_presents(le_jeu):
    genres = {c.genre for c in le_jeu.cas}
    assert {"directe", "familiere", "incomplete", "faute", "deux_temps", "culture_absente"} <= genres


# ── CA2 : le dialogue du 14/11 est le cas n° 1 ───────────────────────────────
def test_ca2_le_premier_cas_est_le_dialogue_du_14_novembre(le_jeu):
    premier = le_jeu.cas[0]
    assert premier.id == "B01-F1" and premier.genre == "reel"
    assert premier.phrases_ecrites == (
        "j'aimerai planter des salades", "oui si tu veux", "oui je veux bien", "la planche légumes", "demain",
        "des salades", "comment je plante des salades ?")
    assert premier.simule is False and premier.jeu_de_donnees == j.JEU_NEUF
    assert "441 à 447" in premier.source


def test_ca2_l_attendu_du_tour_1(le_jeu):
    attendus = le_jeu.cas[0].attendus_du_tour(1)
    assert attendus is not None
    texte = " ".join(e for g in attendus.textes_attendus for e in g)
    assert "février" in texte and "rien à semer" in texte and "pas au potager" in texte
    assert "tomate" in attendus.textes_interdits


def test_ca2_le_potager_neuf_de_reference_est_calque_sur_le_potager_34(le_jeu):
    neuf = le_jeu.jeux_de_donnees[j.JEU_NEUF]
    assert neuf["parcelles"] == ["planche légumes"]
    assert "20 m²" in neuf["description"] and "plein sud" in neuf["description"]
    assert "océanique" in neuf["description"]


# ── CA3 ──────────────────────────────────────────────────────────────────────
def test_ca3_chaque_cas_dit_son_jeu_de_donnees_et_le_neuf_vient_d_un_script(le_jeu):
    assert {c.jeu_de_donnees for c in le_jeu.cas} == {j.JEU_NEUF, j.JEU_REMPLI, j.JEU_MULTI}
    script = le_jeu.jeux_de_donnees[j.JEU_NEUF]["script"]
    assert (RACINE / script).is_file()
    rempli = le_jeu.jeux_de_donnees[j.JEU_REMPLI]
    assert rempli["potager_id"] and rempli["script"] == "tools/creer_potager_test_rempli.py" and rempli["lecture_seule"] is True


# ── CA4 ──────────────────────────────────────────────────────────────────────
def test_ca4_les_ecritures_d_un_reproducteur_en_pleine_terre(le_jeu):
    couvre = {c.couvre for c in le_jeu.cas if c.culture_type == "reproducteur_pleine_terre"}
    assert {"semis_initial", "premiere_recolte", "nieme_recolte", "fin_de_vie"} <= couvre


def test_ca4_une_recolte_n_est_jamais_attendue_comme_une_perte(le_jeu):
    recoltes = [c for c in le_jeu.cas if c.couvre in ("premiere_recolte", "nieme_recolte")]
    assert recoltes
    for c in recoltes:
        assert "perte" in c.attendus.ecritures_interdites
        assert any("perte de stock" in t for t in c.attendus.textes_interdits)


def test_ca4_les_trois_types_de_culture_sont_joues(le_jeu):
    assert {"vegetatif", "reproducteur_pleine_terre", "reproducteur_plants"} <= {c.culture_type for c in le_jeu.cas}
    cultures = {c.fiche.get("culture") for c in le_jeu.cas}
    assert {"salade", "carotte", "haricot", "tomate"} <= cultures


# ── CA5 ──────────────────────────────────────────────────────────────────────
def test_ca5_au_moins_trois_cas_sans_fiche_agronomique(le_jeu):
    sans_fiche = [c for c in le_jeu.cas if c.attendus.couverture_absente]
    assert len(sans_fiche) >= 3
    assert all(c.fiche.get("culture") for c in sans_fiche)


# ── CA6 ──────────────────────────────────────────────────────────────────────
def test_ca6_un_tiers_des_cas_est_renouvelable(le_jeu):
    part = sum(1 for c in le_jeu.cas if c.renouvelable) / len(le_jeu.cas)
    assert part >= 1 / 3


def test_ca6_aucun_cas_renouvelable_dans_un_exemple_de_prompt(le_jeu):
    """Contrôle automatique sur les VRAIS prompts livrés (agent actuel, boucle à capacités, catalogues)."""
    assert j.controler_renouvelables(le_jeu, j.textes_des_prompts_livres()) == []


def test_ca6_le_controle_attrape_un_exemple_de_prompt_qui_cite_un_cas_renouvelable(le_jeu):
    cas = next(c for c in le_jeu.cas if c.renouvelable and len(c.ouverture.split()) >= 3)
    prompt = f"Exemples : « {cas.ouverture} » → lire le calendrier."
    assert cas.id in j.controler_renouvelables(le_jeu, [prompt])


def test_ca6_un_exemple_inclus_dans_la_phrase_compte_aussi(le_jeu):
    cas = next(c for c in le_jeu.cas if c.renouvelable and len(c.ouverture.split()) >= 3)
    prompt = f"Exemple : \"{cas.ouverture} s'il te plaît\""
    assert cas.id in j.controler_renouvelables(le_jeu, [prompt])


def test_ca6_une_reponse_d_un_mot_n_est_la_propriete_d_aucun_prompt(le_jeu):
    prompt = 'Le jardinier dit « oui » ou « demain ».'
    assert j.controler_renouvelables(le_jeu, [prompt]) == []


def test_ca6_les_cas_non_renouvelables_peuvent_etre_dans_un_prompt(le_jeu):
    cas = next(c for c in le_jeu.cas if not c.renouvelable and len(c.ouverture.split()) >= 3)
    assert j.controler_renouvelables(le_jeu, [f"« {cas.ouverture} »"]) == []


# ── CA7 ──────────────────────────────────────────────────────────────────────
def test_ca7_les_attendus_distinguent_les_trois_notions_de_valeur(le_jeu):
    assert all(c.attendus.valeur_par_defaut in j.VALEURS_PAR_DEFAUT for c in le_jeu.cas)
    ecriture = [c for c in le_jeu.cas if c.categorie == "ecriture"]
    assert ecriture and all(c.attendus.valeur_par_defaut == "permise" for c in ecriture)
    assert all({"culture"} <= set(c.attendus.ne_jamais_redemander) for c in ecriture if c.fiche.get("culture"))


def test_ca7_la_documentation_decrit_les_trois_notions():
    texte = DOC.read_text(encoding="utf-8")
    assert "valeur par défaut" in texte.lower() and "reposer" in texte.lower() and "non dite" in texte
    assert "10 plants, ça te va ?" in texte


# ── CA8 ──────────────────────────────────────────────────────────────────────
def test_ca8_les_quatre_configurations_de_reference(le_jeu):
    configs = {c["id"]: c for c in le_jeu.configurations}
    assert set(configs) == {"A", "B", "C", "D"}
    assert configs["A"]["nom"].startswith("Chaîne actuelle, Small 4")
    assert configs["B"]["modele"] == "mistral/mistral-large-2512"
    assert configs["C"]["moteur"] == "capacites" and configs["D"]["moteur"] == "claude_mcp"
    assert configs["C"]["resultats_14_11"]["jetons_entree_7_tours"] == 51211
    assert configs["A"]["resultats_14_11"]["jetons_entree_7_tours"] == 108894
    assert configs["C"]["resultats_14_11"]["part_cache"] == 0.86
    assert all(c["resultats_14_11"] for c in configs.values())


# ── CA9 : la documentation du format ─────────────────────────────────────────
def test_ca9_la_documentation_decrit_le_format():
    texte = DOC.read_text(encoding="utf-8")
    for champ in ("jeux_de_donnees", "besoins", "formulations", "fiche", "attendus", "ne_jamais_redemander",
                  "ecritures_interdites", "cultures_admises", "couverture_absente", "valeur_par_defaut",
                  "textes_attendus", "textes_interdits", "attendus_tours", "renouvelable", "suite", "simule",
                  "tours_max", "couvre", "culture_type"):
        assert f"`{champ}`" in texte, champ
    assert "## 6. Exemple commenté" in texte and "## 4. Renouvellement" in texte
    for genre in j.GENRES:
        assert f"`{genre}`" in texte, genre


# ── Gherkin ──────────────────────────────────────────────────────────────────
def test_gherkin_le_besoin_planter_des_salades(le_jeu):
    cas = [c for c in le_jeu.cas if c.besoin == "B01"]
    assert len(cas) >= 5
    assert {"deux_temps", "faute"} <= {c.genre for c in cas}
    assert all(c.fiche["culture"] == "salade" and c.fiche["quantite"] == "12" for c in cas)
    for c in cas:
        assert "culture" in c.attendus.ne_jamais_redemander
        assert c.attendus.passages_hors_culture_interdits and not c.attendus.admet_toute_culture


# ── Le chargeur ──────────────────────────────────────────────────────────────
def _jeu_minimal(**surcharges) -> dict:
    base = {"jeux_de_donnees": {"neuf": {"script": "x"}}, "configurations": [], "besoins": [{
        "id": "T1", "libelle": "Test", "categorie": "conseil", "jeu_de_donnees": "neuf", "culture_type": "aucune",
        "fiche": {}, "attendus": {"bonne_reponse": "x"},
        "formulations": [{"genre": "directe", "ouverture": "bonjour"}]}]}
    base["besoins"][0].update(surcharges)
    return base


def _ecrire(tmp_path, brut: dict) -> Path:
    chemin = tmp_path / "jeu.json"
    chemin.write_text(json.dumps(brut, ensure_ascii=False), encoding="utf-8")
    return chemin


def test_le_chargeur_developpe_les_formulations_en_cas(tmp_path):
    jeu = j.charger(_ecrire(tmp_path, _jeu_minimal()))
    assert [c.id for c in jeu.cas] == ["T1-F1"] and jeu.cas[0].tours_max == 4 and jeu.cas[0].simule is True


def test_la_fiche_et_les_attendus_d_une_formulation_surchargent_ceux_du_besoin(tmp_path):
    brut = _jeu_minimal(fiche={"culture": "tomate", "quantite": "6"})
    brut["besoins"][0]["formulations"][0].update({"fiche": {"quantite": "8"}, "couverture_absente": True,
                                                  "attendus": {"ecritures_interdites": ["*"]}})
    c = j.charger(_ecrire(tmp_path, brut)).cas[0]
    assert c.fiche == {"culture": "tomate", "quantite": "8"}
    assert c.attendus.couverture_absente and c.attendus.interdit_toute_ecriture and c.attendus.bonne_reponse == "x"


@pytest.mark.parametrize("surcharge, message", [
    ({"jeu_de_donnees": "autre"}, "jeu de données inconnu"),
    ({"culture_type": "fleur"}, "type de culture inconnu"),
    ({"couvre": "jamais"}, "« couvre » inconnu"),
    ({"inconnue": 1}, "clé"),
    ({"formulations": [{"genre": "bizarre", "ouverture": "x"}]}, "genre inconnu"),
    ({"formulations": [{"genre": "directe", "ouverture": "x", "faute_de_frappe": 1}]}, "clé"),
    ({"attendus": {"bonne_reponse": "x", "ne_jamais_redemandre": ["culture"]}}, "attendus"),
    ({"attendus": {"bonne_reponse": "x", "valeur_par_defaut": "toujours"}}, "valeur_par_defaut"),
])
def test_le_chargeur_refuse_une_faute_de_frappe(tmp_path, surcharge, message):
    with pytest.raises(j.JeuInvalideError, match=message):
        j.charger(_ecrire(tmp_path, _jeu_minimal(**surcharge)))


def test_un_besoin_sans_fiche_est_refuse(tmp_path):
    brut = _jeu_minimal()
    del brut["besoins"][0]["fiche"]
    with pytest.raises(j.JeuInvalideError, match="fiche de besoin"):
        j.charger(_ecrire(tmp_path, brut))


def test_les_exigences_signalent_un_jeu_trop_court(tmp_path):
    ecarts = j.controler_exigences(j.charger(_ecrire(tmp_path, _jeu_minimal())))
    assert any(e.startswith("CA1") for e in ecarts) and any(e.startswith("CA2") for e in ecarts)
    assert any(e.startswith("CA5") for e in ecarts) and any(e.startswith("CA8") for e in ecarts)


def test_les_exigences_signalent_une_recolte_attendue_comme_une_perte(le_jeu):
    cas = [replace(c, attendus=replace(c.attendus, ecritures_interdites=())) if c.couvre == "premiere_recolte" else c
           for c in le_jeu.cas]
    ecarts = j.controler_exigences(replace(le_jeu, cas=tuple(cas)))
    assert any("perte de stock" in e for e in ecarts)


def test_filtrer_retient_besoins_jeu_et_limite(le_jeu):
    assert {c.besoin for c in le_jeu.filtrer(besoins=["B02", "B05"]).cas} == {"B02", "B05"}
    assert {c.jeu_de_donnees for c in le_jeu.filtrer(jeu="rempli").cas} == {"rempli"}
    assert len(le_jeu.filtrer(limite=3).cas) == 3
    assert all(c.renouvelable for c in le_jeu.filtrer(renouvelables=True).cas)


def test_normaliser_ignore_accents_casse_et_ponctuation():
    assert j.normaliser("  Quelle  PLANCHE légumes ?! ") == "quelle planche legumes"


# ── Le potager neuf : script de données de test rejouable ────────────────────
def test_le_script_cree_le_potager_neuf_de_reference(test_db):
    from database.models import Parcelle, Potager
    from tools import creer_potager_test_neuf as script

    r = script.creer_ou_reinitialiser(test_db)
    assert r.cree is True
    potager = test_db.get(Potager, r.potager_id)
    assert potager.zone_climatique == "oceanique" and potager.proprietaire_id == r.utilisateur_id
    parcelles = test_db.query(Parcelle).filter(Parcelle.potager_id == r.potager_id).all()
    assert [(p.nom, p.superficie_m2, p.exposition) for p in parcelles] == [("planche légumes", 20.0, "plein sud")]


def test_le_script_est_rejouable_et_remet_le_potager_a_neuf(test_db):
    from database.models import Evenement, Parcelle
    from tools import creer_potager_test_neuf as script

    premier = script.creer_ou_reinitialiser(test_db)
    parcelle = test_db.get(Parcelle, premier.parcelle_id)
    test_db.add(Evenement(type_action="semis", culture="haricot", quantite=30, parcelle_id=parcelle.id,
                          potager_id=premier.potager_id))
    test_db.add(Parcelle(nom="Serre", nom_normalise="serre", potager_id=premier.potager_id))
    test_db.commit()

    second = script.creer_ou_reinitialiser(test_db)
    assert second.cree is False
    assert (second.utilisateur_id, second.potager_id) == (premier.utilisateur_id, premier.potager_id)
    assert test_db.query(Evenement).filter(Evenement.potager_id == second.potager_id).count() == 0
    noms = [p.nom for p in test_db.query(Parcelle).filter(Parcelle.potager_id == second.potager_id)]
    assert noms == ["planche légumes"]


def test_le_script_refuse_une_base_qui_n_est_pas_de_test(test_db):
    from database.models import Potager
    from tools import creer_potager_test_neuf as script

    avant = test_db.query(Potager).count()
    with pytest.raises(script.BaseNonTestError):
        script.creer_ou_reinitialiser(test_db, url_base="postgresql://u:p@localhost/potager_prod")
    assert test_db.query(Potager).count() == avant


def test_le_script_ne_touche_pas_aux_autres_potagers(test_db):
    from database.models import Parcelle, Potager, User
    from tools import creer_potager_test_neuf as script

    autre = User(email="autre@test.invalid")
    test_db.add(autre)
    test_db.commit()
    voisin = Potager(nom="Voisin", proprietaire_id=autre.id)
    test_db.add(voisin)
    test_db.commit()
    id_voisin = voisin.id
    test_db.add(Parcelle(nom="Verger", nom_normalise="verger", potager_id=id_voisin))
    test_db.commit()
    script.creer_ou_reinitialiser(test_db)
    script.creer_ou_reinitialiser(test_db)  # la session est vidée de ses objets : on ne garde que des identifiants
    assert [p.nom for p in test_db.query(Parcelle).filter(Parcelle.potager_id == id_voisin)] == ["Verger"]


# ── Le potager rempli : copie rejouable d'un potager d'une autre base ────────
def _source_remplie(test_db):
    """Un potager « source » dans la même base SQLite : deux parcelles, trois gestes liés, un fait, un rappel."""
    from datetime import datetime

    from database.models import Evenement, FaitCarnet, Parcelle, Potager, Rappel, User

    proprio = User(email="source@test.invalid")
    test_db.add(proprio)
    test_db.commit()
    pot = Potager(nom="Potager de recette", proprietaire_id=proprio.id, ville="Cormeilles", latitude=48.97,
                  longitude=2.2)
    test_db.add(pot)
    test_db.commit()
    principal = Parcelle(nom="principal", nom_normalise="principal", potager_id=pot.id)
    serre = Parcelle(nom="serre", nom_normalise="serre", potager_id=pot.id, est_pepiniere=True)
    test_db.add_all([principal, serre])
    test_db.commit()
    semis = Evenement(type_action="semis", culture="tomate", quantite=10, parcelle_id=serre.id, potager_id=pot.id)
    test_db.add(semis)
    test_db.commit()
    plantation = Evenement(type_action="plantation", culture="tomate", quantite=6, parcelle_id=principal.id,
                           parcelle_origine_id=serre.id, origine_graines_id=semis.id, potager_id=pot.id,
                           source_evenement_ids=str(semis.id))
    test_db.add(plantation)
    test_db.add(FaitCarnet(user_id=proprio.id, potager_id=pot.id, texte="sol argileux"))
    test_db.commit()
    test_db.add(Rappel(user_id=proprio.id, potager_id=pot.id, objet="voir la levée", echeance_le=datetime(2026, 12, 1),
                       cible_type="evenement", cible_id=semis.id))
    test_db.commit()
    return pot.id


def test_le_script_rempli_copie_le_potager_et_relie_ses_gestes(test_db):
    from database.models import Evenement, Parcelle, Potager, Rappel
    from tools import creer_potager_test_rempli as script

    source_id = _source_remplie(test_db)
    r = script.copier(test_db, test_db.get_bind().connect(), source_potager=source_id)
    assert r.cree and r.potager_id != source_id
    assert r.copie["parcelles"] == 2 and r.copie["evenements"] == 2 and r.copie["carnet_faits"] == 1
    copie = test_db.get(Potager, r.potager_id)
    assert copie.ville == "Cormeilles" and copie.proprietaire_id == r.utilisateur_id
    parcelles = {p.id: p.nom for p in test_db.query(Parcelle).filter(Parcelle.potager_id == r.potager_id)}
    assert sorted(parcelles.values()) == ["principal", "serre"]
    gestes = {e.type_action: e for e in test_db.query(Evenement).filter(Evenement.potager_id == r.potager_id)}
    plantation, semis = gestes["plantation"], gestes["semis"]
    assert parcelles[plantation.parcelle_id] == "principal" and parcelles[plantation.parcelle_origine_id] == "serre"
    assert plantation.origine_graines_id == semis.id and plantation.source_evenement_ids == str(semis.id)
    rappel = test_db.query(Rappel).filter(Rappel.potager_id == r.potager_id).one()
    assert rappel.cible_id == semis.id and rappel.user_id == r.utilisateur_id


def test_le_script_rempli_est_rejouable(test_db):
    from database.models import Evenement
    from tools import creer_potager_test_rempli as script

    source_id = _source_remplie(test_db)
    premier = script.copier(test_db, test_db.get_bind().connect(), source_potager=source_id)
    second = script.copier(test_db, test_db.get_bind().connect(), source_potager=source_id)
    assert second.cree is False and second.potager_id == premier.potager_id
    assert test_db.query(Evenement).filter(Evenement.potager_id == second.potager_id).count() == 2


def test_le_script_rempli_refuse_une_base_qui_n_est_pas_de_test(test_db):
    from database.models import Potager
    from tools import creer_potager_test_rempli as script

    source_id = _source_remplie(test_db)
    avant = test_db.query(Potager).count()
    with pytest.raises(script.BaseNonTestError):
        script.copier(test_db, test_db.get_bind().connect(), source_potager=source_id,
                      url_base="postgresql://u:p@localhost/potager_prod")
    assert test_db.query(Potager).count() == avant


def test_le_jeu_decrit_le_script_du_potager_rempli(le_jeu):
    assert le_jeu.jeux_de_donnees["rempli"]["script"] == "tools/creer_potager_test_rempli.py"


# ── Le potager multi-parcelles (relecture G2) ─────────────────────────────────
def test_le_potager_multi_porte_la_meme_culture_sur_deux_parcelles(test_db):
    from database.models import Evenement, Parcelle
    from tools import creer_potager_test_multi as script

    for _ in range(2):  # rejouable
        resultat = script.creer_ou_reinitialiser(test_db)
        gestes = test_db.query(Evenement).filter(Evenement.potager_id == resultat.potager_id).all()
        assert len(gestes) == 2 and {g.culture for g in gestes} == {"haricot"}
        noms = {p.id: p.nom for p in test_db.query(Parcelle).filter(Parcelle.potager_id == resultat.potager_id)}
        assert {noms[g.parcelle_id] for g in gestes} == {"planche légumes", "planche nord"}


def test_les_cas_multi_parcelles_sont_dans_le_jeu(le_jeu):
    multi = [c for c in le_jeu.cas if c.jeu_de_donnees == j.JEU_MULTI]
    assert {c.besoin for c in multi} == {"B25", "B26"} and len(multi) == 12
    assert le_jeu.jeux_de_donnees[j.JEU_MULTI]["script"] == "tools/creer_potager_test_multi.py"
