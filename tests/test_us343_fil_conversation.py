"""
tests/test_us343_fil_conversation.py — Le fil complet de la conversation, borné et compacté [US-343]
====================================================================================================
Un bloc par critère d'acceptance (CA1 à CA6), la migration v81 et le scénario Gherkin. Le modèle est simulé :
CA7 (intention gardée à 100 %, jetons par tour, part en cache) se mesure sur le jeu d'évaluation, avec accord.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.services.compagnon import boucle as svc_boucle
from app.services.compagnon import conversations as svc_conversations
from app.services.compagnon import fil as svc_fil
from app.services.context import TenantContext
from database.models import EchangeConversation
from tests.test_us342_boucle_compagnon import ExecuteurEspion, ModeleScripte, _appel, _reponse

RACINE = Path(__file__).resolve().parents[1]
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
T0 = datetime(2026, 11, 14, 9, 0)


def _tour_boucle(n: int, *, culture: str = "salade", minutes: int = 1, base: datetime = T0) -> svc_fil.TourFil:
    """Un tour de la boucle : phrase, lecture avec arguments, résultat daté, réponse."""
    instant = base + timedelta(minutes=minutes * n)
    messages = (
        {"role": "user", "content": f"[14/11 10:{n:02d}] phrase {n}"},
        {"role": "assistant", "content": None, "tool_calls": [{"id": f"a{n}", "type": "function", "function": {
            "name": "situation_culture", "arguments": json.dumps({"culture": culture, "parcelle": "planche sud"})}}]},
        {"role": "tool", "tool_call_id": f"a{n}", "content": svc_fil.contenu_d_outil('{"verdict": "x"}', instant)},
        {"role": "assistant", "content": f"réponse {n}"},
    )
    return svc_fil.TourFil(f"phrase {n}", f"réponse {n}", instant, messages=messages, canal="pwa", id=n)


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — les messages complets de chaque tour
# ═════════════════════════════════════════════════════════════════════════════
def test_ca1_le_fil_garde_phrase_appels_resultats_et_reponse():
    fil = svc_fil.construire([_tour_boucle(1)], T0 + timedelta(minutes=5))
    roles = [m["role"] for m in fil.messages]
    assert roles == ["user", "assistant", "tool", "assistant"]
    appel = fil.messages[1]["tool_calls"][0]["function"]
    assert appel["name"] == "situation_culture" and json.loads(appel["arguments"])["culture"] == "salade"
    assert '{"verdict": "x"}' in fil.messages[2]["content"]


def test_ca1_un_echange_de_l_ancien_moteur_se_relit_en_phrase_et_reponse():
    ancien = svc_fil.TourFil("j'ai semé des radis", "Voici ce que j'ai compris.", T0, canal="telegram")
    assert ancien.en_messages() == [{"role": "user", "content": "j'ai semé des radis"},
                                    {"role": "assistant", "content": "Voici ce que j'ai compris."}]
    assert svc_fil.TourFil("", "Bonjour !", T0).en_messages() == []  # un message spontané seul ne s'insère pas


def test_ca1_le_tour_est_garde_en_base_et_relu(memoire_compagnon):
    tour = _tour_boucle(1)
    svc_fil.noter_tour(CTX, "phrase 1", "réponse 1", list(tour.messages), canal="pwa", outils=("situation_culture",),
                       maintenant=T0)
    relus = svc_fil.lire_tours(CTX, T0 + timedelta(minutes=2))
    assert len(relus) == 1 and list(relus[0].messages) == list(tour.messages)
    # L'ancien moteur lit toujours la phrase et la réponse du même échange (US-259).
    assert [(e.texte, e.resume) for e in svc_conversations.recents(CTX, T0 + timedelta(minutes=2))] == \
        [("phrase 1", "réponse 1")]


def test_ca1_le_tour_de_la_boucle_porte_ses_messages_complets():
    espion = ExecuteurEspion({"situation_culture": {"verdict": "pas_ce_mois_ci"}})
    modele = ModeleScripte(_reponse(_appel("situation_culture", culture="salade")), _reponse(texte="Pas maintenant."))
    tour = svc_boucle.jouer_tour(CTX, "j'aimerai planter des salades", fil=svc_fil.Fil(), executer=espion,
                                 appeler=modele, jour=date(2026, 11, 14), maintenant=T0)
    assert [m["role"] for m in tour.messages] == ["user", "assistant", "tool", "assistant"]
    assert tour.messages[0]["content"] == "[14/11 10:00] j'aimerai planter des salades"
    assert tour.messages[-1] == {"role": "assistant", "content": "Pas maintenant."}


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — des résultats datés ; le validateur relit en base
# ═════════════════════════════════════════════════════════════════════════════
def test_ca2_un_resultat_est_date_a_l_heure_du_jardinier():
    assert svc_fil.contenu_d_outil('{"a": 1}', datetime(2026, 11, 14, 10, 3)) == '[lu le 14/11 10:03] {"a": 1}'
    assert svc_fil.heure_locale(datetime(2026, 11, 14, 9, 3)) == datetime(2026, 11, 14, 10, 3)  # UTC+1 en hiver
    assert svc_fil.heure_locale(datetime(2026, 7, 14, 9, 3)) == datetime(2026, 7, 14, 11, 3)  # UTC+2 en été


def test_ca2_le_prompt_demande_de_relire_une_donnee_ancienne_avant_d_ecrire():
    assert "relis une donnée lue il y a plus de quelques minutes" in svc_boucle.PROMPT_FIXE


def test_ca2_le_validateur_relit_la_base_au_moment_de_proposer(memoire_compagnon, monkeypatch):
    """Le fil peut dire qu'une parcelle existait : la proposition la cherche en base, pas dans le fil."""
    import app.services.capacites  # noqa: F401
    from app.services.capacites import registre

    monkeypatch.setattr("database.db.SessionLocal", memoire_compagnon)
    with memoire_compagnon() as db:
        with pytest.raises(registre.RefusCapacite, match="introuvable|inconnue"):
            registre.appeler(db, CTX, "proposer_geste",
                             {"type": "semis", "culture": "radis", "quantite": 2, "parcelle": "Planche disparue"})


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — 12 tours complets, les plus anciens compactés en faits établis
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("n, compactes, complets", [(1, 0, 1), (12, 0, 12), (13, 6, 7), (18, 6, 12), (19, 12, 7),
                                                     (30, 18, 12)])
def test_ca3_la_fenetre_garde_12_tours_et_compacte_par_blocs(n, compactes, complets):
    tours = [_tour_boucle(i) for i in range(1, n + 1)]
    fil = svc_fil.construire(tours, T0 + timedelta(minutes=n + 1))
    assert (len(fil.tours_compactes), len(fil.tours_complets)) == (compactes, complets)
    assert svc_fil.TOURS_COMPLETS == 12 and svc_fil.BLOC_COMPACTION == 6
    assert bool(fil.resume) == bool(compactes)


def test_ca3_le_resume_dit_les_faits_etablis_et_ce_qui_manque():
    tours = [_tour_boucle(i) for i in range(1, 7)]
    tours.append(svc_fil.TourFil("et pour les tomates ?", "Sur quelle parcelle ?", T0 + timedelta(minutes=7),
                                 messages=None, id=7))
    resume = svc_fil.resumer(tours)
    assert "culture : salade" in resume and "parcelle : planche sud" in resume
    assert "jardinier : « phrase 1 »" in resume and "toi : « réponse 1 »" in resume
    assert "Restait en suspens : « Sur quelle parcelle ? »" in resume


def test_ca3_le_resume_va_dans_la_partie_variable_du_prompt():
    tours = [_tour_boucle(i) for i in range(1, 14)]
    fil = svc_fil.construire(tours, T0 + timedelta(minutes=14))
    variable = svc_boucle.prompt_variable(date(2026, 11, 14), fil)
    assert variable.startswith("\nAujourd'hui : samedi 2026-11-14.") and svc_fil.ENTETE_RESUME in variable


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — troncature écrite, préfixe stable
# ═════════════════════════════════════════════════════════════════════════════
def test_ca4_un_resultat_volumineux_est_tronque_selon_la_regle():
    long = "x" * (svc_fil.RESULTAT_MAX_CARACTERES + 500)
    tronque = svc_fil.tronquer_resultat(long)
    assert tronque.startswith("x" * svc_fil.RESULTAT_MAX_CARACTERES)
    assert tronque.endswith(f"[tronqué : {len(long)} caractères, relis l'outil pour la suite]")
    assert svc_fil.tronquer_resultat("court") == "court"


def test_ca4_le_prefixe_reste_stable_d_un_tour_a_l_autre():
    tours = [_tour_boucle(i) for i in range(1, 19)]
    for n in range(13, 18):  # entre deux blocs : résumé identique, messages d'avant inchangés
        avant = svc_fil.construire(tours[:n], T0 + timedelta(minutes=n + 1))
        apres = svc_fil.construire(tours[:n + 1], T0 + timedelta(minutes=n + 2))
        assert apres.resume == avant.resume
        assert apres.messages[:len(avant.messages)] == avant.messages
    # La boucle met prompt et outils en tête, dans un ordre fixe.
    assert svc_boucle.schemas_des_outils() == svc_boucle.schemas_des_outils()


def test_ca4_le_tour_courant_lit_ce_que_le_fil_gardera(monkeypatch):
    long = {"plan": "y" * (svc_fil.RESULTAT_MAX_CARACTERES + 10)}
    modele = ModeleScripte(_reponse(_appel("voir_plan")), _reponse(texte="ok"))
    tour = svc_boucle.jouer_tour(CTX, "le plan ?", fil=svc_fil.Fil(), executer=ExecuteurEspion({"voir_plan": long}),
                                 appeler=modele, jour=date(2026, 11, 14), maintenant=T0)
    vu = modele.appels[1]["historique"][-1]["content"]
    assert "[tronqué" in vu and vu == tour.messages[2]["content"]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — un fil par jardinier et par potager, commun aux deux canaux
# ═════════════════════════════════════════════════════════════════════════════
def test_ca5_un_fil_par_jardinier_et_par_potager_commun_aux_canaux(memoire_compagnon):
    autre_potager = TenantContext(user_id=1, potager_id=2, role="owner")
    autre_jardinier = TenantContext(user_id=2, potager_id=1, role="owner")
    svc_conversations.noter(CTX, "dans la PWA", "ok pwa", canal="pwa", maintenant=T0)
    svc_conversations.noter(CTX, "dans Telegram", "ok telegram", canal="telegram", maintenant=T0 + timedelta(minutes=1))
    svc_conversations.noter(autre_potager, "autre potager", "non", canal="pwa", maintenant=T0)
    svc_conversations.noter(autre_jardinier, "autre jardinier", "non", canal="pwa", maintenant=T0)
    tours = svc_fil.lire_tours(CTX, T0 + timedelta(minutes=2))
    assert [t.texte_jardinier for t in tours] == ["dans la PWA", "dans Telegram"]
    assert [t.texte_jardinier for t in svc_fil.lire_tours(autre_potager, T0 + timedelta(minutes=2))] == ["autre potager"]


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — la reprise le lendemain sur le résumé
# ═════════════════════════════════════════════════════════════════════════════
def test_ca6_apres_une_pause_la_seance_close_n_est_relue_qu_en_resume():
    hier = [_tour_boucle(i, base=T0 - timedelta(hours=14)) for i in range(1, 4)]
    fil = svc_fil.construire(hier, T0)
    assert fil.messages == () and len(fil.tours_compactes) == 3 and "culture : salade" in fil.resume


def test_ca6_la_seance_en_cours_reste_entiere_apres_la_reprise():
    hier = [_tour_boucle(i, base=T0 - timedelta(hours=14)) for i in range(1, 4)]
    aujourd_hui = [_tour_boucle(i, base=T0) for i in range(1, 3)]
    fil = svc_fil.construire(hier + aujourd_hui, T0 + timedelta(minutes=5))
    assert len(fil.tours_compactes) == 3 and len(fil.tours_complets) == 2


def test_ca6_au_dela_de_la_reprise_le_fil_repart_de_zero():
    vieux = [_tour_boucle(1, base=T0 - svc_fil.REPRISE - timedelta(hours=1))]
    assert svc_fil.construire(vieux, T0).vide


def test_ca6_une_pause_courte_ne_clot_pas_la_seance():
    tours = [_tour_boucle(1), _tour_boucle(2, minutes=60)]  # 1 h 59 entre les deux : moins que la pause
    assert len(svc_fil.construire(tours, T0 + timedelta(hours=2, minutes=10)).tours_complets) == 2
    assert svc_fil.PAUSE == timedelta(hours=3)


# ═════════════════════════════════════════════════════════════════════════════
# Les cartes traitées depuis le dernier tour
# ═════════════════════════════════════════════════════════════════════════════
def test_seule_une_carte_traitee_depuis_le_dernier_tour_se_dit():
    etats = [svc_fil.EtatCarte(1, "semis de radis", "confirmee", "✅ Confirmé depuis le portail", T0),
             svc_fil.EtatCarte(2, "semis de fèves", "confirmee", "✅ Confirmé", T0 - timedelta(hours=1)),
             svc_fil.EtatCarte(3, "récolte", "en_attente", "en attente", None)]
    note = svc_fil.note_des_cartes(etats, depuis=T0 - timedelta(minutes=5))
    assert "carte n°1 (semis de radis)" in note and "n°2" not in note and "n°3" not in note
    assert svc_fil.note_des_cartes([], None) == ""


# ═════════════════════════════════════════════════════════════════════════════
# Migration v81 et RGPD
# ═════════════════════════════════════════════════════════════════════════════
def test_migration_v81_ajoute_la_colonne_messages_et_son_rollback_la_retire():
    sql = (RACINE / "migrations" / "migration_v81.sql").read_text(encoding="utf-8")
    rollback = (RACINE / "migrations" / "rollback_v81.sql").read_text(encoding="utf-8")
    assert "ALTER TABLE echanges_conversation ADD COLUMN IF NOT EXISTS messages JSONB NULL" in sql
    assert "DROP COLUMN IF EXISTS messages" in rollback
    assert "messages" in EchangeConversation.__table__.columns


def test_rgpd_le_fil_est_purge_avec_les_echanges(memoire_compagnon):
    from app.services.compagnon import conversations

    svc_fil.noter_tour(CTX, "vieux", "vieux", list(_tour_boucle(1).messages), canal="pwa",
                       maintenant=datetime.utcnow() - timedelta(days=31))
    with memoire_compagnon() as db:
        from database.models import Potager

        if db.get(Potager, 1) is None:
            db.add(Potager(id=1, nom="P", proprietaire_id=1, etat="actif"))
            db.commit()
    assert conversations.purger() >= 1
    with memoire_compagnon() as db:
        assert db.query(EchangeConversation).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin — l'intention reste dans le fil
# ═════════════════════════════════════════════════════════════════════════════
def test_gherkin_au_tour_5_le_compagnon_relit_les_salades_du_tour_1(memoire_compagnon, monkeypatch):
    """Given « j'aimerai planter des salades » au tour 1, la situation de la salade lue / When « sur la planche
    sud » au tour 5 / Then le modèle relit, dans le fil, la phrase et l'appel du tour 1 (il n'a pas à redemander la
    culture). Ce que Small 4 en fait se mesure (CA7) ; ici, on vérifie ce qu'il reçoit."""
    monkeypatch.setattr("database.db.SessionLocal", memoire_compagnon)
    phrases = ["j'aimerai planter des salades", "oui", "en pleine terre", "plutôt une dizaine", "sur la planche sud"]
    modele = ModeleScripte(_reponse(_appel("situation_culture", culture="salade")),
                           *[_reponse(texte=f"réponse {i}") for i in range(1, 6)])
    espion = ExecuteurEspion({"situation_culture": {"verdict": "pas_ce_mois_ci"}})
    monkeypatch.setattr(svc_boucle, "executeur_du_registre", lambda ctx: espion)
    from llm import passerelle

    monkeypatch.setattr(passerelle, "appeler_chat_outils", modele)
    for phrase in phrases:
        svc_boucle.repondre(CTX, phrase, canal="pwa")
    historique = modele.appels[-1]["historique"]
    contenus = [m.get("content") or "" for m in historique]
    assert contenus[0].endswith("j'aimerai planter des salades")
    appel = next(m for m in historique if m.get("tool_calls"))["tool_calls"][0]["function"]
    assert appel["name"] == "situation_culture" and json.loads(appel["arguments"]) == {"culture": "salade"}
    assert contenus[-1].endswith("sur la planche sud")
    assert sum(1 for m in historique if m["role"] == "user") == 5
