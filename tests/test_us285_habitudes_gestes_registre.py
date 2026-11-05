"""
tests/test_us285_habitudes_gestes_registre.py — [US-285] Habitudes, objectifs et gestes notés, registre
=======================================================================================================
Une habitude n'est jamais présentée comme un geste fait, un objectif porte son année, « la dernière
action » est A1, et aucun registre ne devient grossier. Sans modèle : la passerelle est simulée.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.services import carnet_compagnon as carnet
from app.services.agent import interpreteur_agent as agent
from app.services.agent import savoir
from app.services.compagnon import actions_menees
from app.services.context import TenantContext
from database.models import Evenement

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUJOURDHUI = date(2026, 11, 3)


def _releves(jours=None, contenus=()):
    releves = savoir.Releves()
    releves.jours_des_gestes = jours
    releves.contenus.extend(contenus)
    return releves


# ── CA1 — trois blocs balisés ───────────────────────────────────────────────
class TestBlocs:
    def test_ca1_habitudes_et_objectifs_ont_chacun_leur_bloc(self):
        bloc = carnet.bloc_prompt(carnet.Carnet(
            faits=(carnet.Fait(1, "j'arrose mes salades tous les matins"),),
            objectifs=("400 kg de tomates en 2027", "plus de courges"),
        ))
        assert "<habitudes_jardinier>\nhabitude : j'arrose mes salades tous les matins\n</habitudes_jardinier>" in bloc
        assert "<objectifs_jardinier>" in bloc and "</objectifs_jardinier>" in bloc
        assert "objectif (2027) : 400 kg de tomates en 2027" in bloc

    def test_ca1_un_objectif_sans_annee_le_dit(self):
        bloc = carnet.bloc_prompt(carnet.Carnet(objectifs=("plus de courges",)))
        assert "objectif (année non dite) : plus de courges" in bloc

    def test_ca1_la_consigne_du_carnet_dit_que_l_habitude_n_est_pas_un_geste(self):
        assert "jamais un geste daté" in carnet.CONSIGNE_CARNET

    def test_ca1_les_gestes_notes_portent_leur_date(self, test_db, monkeypatch):
        test_db.add(Evenement(potager_id=1, type_action="semis", culture="radis",
                              date=datetime(2026, 11, 1, 9, 0)))
        test_db.commit()
        monkeypatch.setattr("database.db.SessionLocal", lambda: test_db)
        monkeypatch.setattr(test_db, "close", lambda: None)
        releves = savoir.Releves()
        bloc = savoir.bloc_gestes_notes(CTX, releves, jour=AUJOURDHUI)
        assert "<gestes_notes>" in bloc and "2026-11-01" in bloc and "semis radis" in bloc
        assert '"aucun_geste_aujourdhui": true' in bloc
        assert releves.jours_des_gestes == {"2026-11-01"}

    def test_ca1_sans_geste_aucun_geste_aujourdhui(self, test_db, monkeypatch):
        monkeypatch.setattr("database.db.SessionLocal", lambda: test_db)
        monkeypatch.setattr(test_db, "close", lambda: None)
        releves = savoir.Releves()
        bloc = savoir.bloc_gestes_notes(CTX, releves, jour=AUJOURDHUI)
        assert releves.jours_des_gestes == set()
        assert '"aucun_geste_aujourdhui": true' in bloc


# ── CA2 — un geste daté inventé est renvoyé puis remplacé ───────────────────
class TestGesteDate:
    def test_ca2_le_prompt_prioritaire_dit_qu_une_habitude_n_est_pas_un_geste(self):
        assert "ne les présente jamais comme un geste fait" in agent.PROMPT_FIXE_PRIORITAIRE

    def test_ca2_habitude_presentee_comme_geste_est_detectee(self):
        texte = "T'as juste arrosé tes salades ce matin et tes tomates hier soir."
        assert savoir.geste_date_non_note(texte, _releves(set()), AUJOURDHUI) == 0

    def test_ca2_un_geste_note_ce_jour_la_passe(self):
        texte = "Tu as arrosé tes salades ce matin."
        assert savoir.geste_date_non_note(texte, _releves({"2026-11-03"}), AUJOURDHUI) is None

    def test_ca2_hier_se_controle_sur_la_veille(self):
        hier = (AUJOURDHUI - timedelta(days=1)).isoformat()
        texte = "Tu as semé des radis hier."
        assert savoir.geste_date_non_note(texte, _releves({hier}), AUJOURDHUI) is None
        assert savoir.geste_date_non_note(texte, _releves({"2026-10-20"}), AUJOURDHUI) == 1

    def test_ca2_la_negation_n_est_pas_une_affirmation(self):
        texte = "Tu n'as rien noté aujourd'hui."
        assert savoir.geste_date_non_note(texte, _releves(set()), AUJOURDHUI) is None

    def test_ca2_sans_relecture_des_gestes_rien_n_est_controle(self):
        assert savoir.geste_date_non_note("Tu as arrosé ce matin.", _releves(None), AUJOURDHUI) is None

    def test_ca2_renvoye_une_fois_puis_remplace_par_le_texte_du_code(self):
        releves = _releves(set())
        texte = "Tu as arrosé tes salades ce matin."
        assert savoir.relance_controle(texte, releves, AUJOURDHUI) == savoir.CONSIGNE_GESTE_INVENTE
        assert savoir.relance_controle(texte, releves, AUJOURDHUI) is None
        remplace = savoir.controler(texte, releves, jour=AUJOURDHUI)
        assert remplace == "Je ne vois aucun geste noté aujourd'hui dans ton carnet."
        assert "arrosé" not in remplace

    def test_ca2_scenario_gherkin_aucun_geste_aujourd_hui(self):
        releves = _releves(set())
        assert "aucun geste noté" in savoir.controler("Tu as arrosé tes salades ce matin.", releves, jour=AUJOURDHUI)


# ── CA3 — A1 est la plus récente ────────────────────────────────────────────
class TestDerniereAction:
    def test_ca3_a1_est_la_plus_recente_meme_a_la_meme_seconde(self, test_db):
        test_db.add_all([
            Evenement(potager_id=1, type_action="semis", culture="radis", date=datetime(2026, 11, 3, 8, 0)),
            Evenement(potager_id=1, type_action="arrosage", culture="salade", date=datetime(2026, 11, 3, 8, 0)),
        ])
        test_db.commit()
        from app.services.evenements import evenements_recents
        assert [e.type_action for e in evenements_recents(test_db, CTX)] == ["arrosage", "semis"]

    def test_ca3_les_references_suivent_l_ordre_donne(self):
        maintenant = datetime(2026, 11, 3, 12, 0)
        actions = tuple(
            actions_menees.Action(id=i, nature="semis", resume=f"geste {i}", canal="telegram", cree_le=maintenant - timedelta(hours=i))
            for i in range(1, 4)
        )
        donnees = actions_menees.en_donnees(actions, maintenant=maintenant)
        assert [d["ref"] for d in donnees] == ["A1", "A2", "A3"]
        assert donnees[0]["action"] == "geste 1"

    def test_ca3_le_bloc_dit_que_la_derniere_action_est_a1(self):
        maintenant = datetime(2026, 11, 3, 12, 0)
        action = actions_menees.Action(id=1, nature="semis", resume="geste 1", canal="telegram", cree_le=maintenant)
        assert "« la dernière action notée » est A1" in agent.bloc_actions((action,), maintenant=maintenant)


# ── CA4 — registre : jamais grossier ────────────────────────────────────────
class TestRegistre:
    @pytest.mark.parametrize("texte", [
        "Ah, merde, j'ai cru que t'avais tout noté !",
        "Putain, quelle récolte.",
        "Quel con ce limaçon.",
    ])
    def test_ca4_les_grossieretes_sont_reconnues(self, texte):
        assert savoir.grossierete(texte)

    @pytest.mark.parametrize("texte", ["Ton concombre est beau.", "Un contrat de culture.", "Les conifères du fond"])
    def test_ca4_un_mot_qui_contient_la_racine_n_est_pas_grossier(self, texte):
        assert not savoir.grossierete(texte)

    def test_ca4_reecrit_une_fois_puis_gabarit_du_code(self):
        releves = _releves(None)
        texte = "Ah, merde, rien n'est noté !"
        assert savoir.relance_controle(texte, releves) == savoir.CONSIGNE_REGISTRE
        assert savoir.relance_controle(texte, releves) is None
        assert savoir.controler(texte, releves) == savoir.TEXTE_REGISTRE

    def test_ca4_avec_lectures_le_texte_du_code_reprend_les_lectures(self):
        releves = savoir.Releves()
        releves.ajouter("12 semis", resume="Tu as 12 semis notés.")
        assert savoir.controler("Putain, 12 semis !", releves) == "Tu as 12 semis notés."

    def test_ca4_le_prompt_interdit_la_grossierete_dans_tous_les_registres(self):
        assert "jamais grossier" in agent.PROMPT_FIXE_PRIORITAIRE
