"""
tests/test_us317_bilan_periodique.py — [US-317] Recevoir un bilan périodique du pilotage.

Service `app/services/pilotage/bilans.py` (résumé quotidien Telegram, bilan hebdomadaire e-mail), trace
`bilans_pilotage` (v80). Les envois sont simulés ; aucun modèle n'est appelé.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app import config
from app.services.pilotage import bilans, notifications
from database.models import AlertePilotage, BilanPilotage, ConsoTokens, Potager, SeuilPilotage, User

ROOT = Path(__file__).resolve().parent.parent
HIER = date(2026, 11, 16)                       # lundi : le jour résumé
AUJOURDHUI = date(2026, 11, 17)
LUNDI_BILAN = date(2026, 11, 23)                # le bilan du lundi porte sur 16/11 → 22/11
ADMIN = "admin@example.com"


def _ligne(db, jour: date, *, user_id: int = 1, appel_type: str = "agent", modele: str = "mistral/small",
           tokens_in: int = 1000, latence_ms: int = 300, issue: str = "ok", provenance: str = "usage",
           cout: int | None = 1000, echange_ref: str | None = None, version: str = "3.132.0") -> None:
    db.add(ConsoTokens(
        potager_id=1, user_id=user_id, date=jour, appel_type=appel_type, modele=modele, tokens_in=tokens_in,
        tokens_out=10, tokens_cache=0, latence_ms=latence_ms, issue=issue, provenance=provenance, canal="pwa",
        unite="jeton", echange_ref=echange_ref, cout_micro_eur=cout, version_app=version,
        cree_le=datetime(jour.year, jour.month, jour.day, 10, 30),
    ))


@pytest.fixture
def db(test_db):
    test_db.add_all([
        Potager(id=1, nom="Potager Dupont", proprietaire_id=1),
        User(id=1, email=ADMIN, nom="Alice Dupont", telegram_chat_id=555),
        User(id=2, email="bob@example.com", nom="Bob Martin"),
        User(id=3, email="clara@example.com", nom="Clara Petit"),
    ])
    test_db.commit()
    return test_db


@pytest.fixture
def envois(monkeypatch):
    telegram, email = MagicMock(return_value=True), MagicMock(return_value=True)
    monkeypatch.setattr(config, "ADMIN_EMAIL", ADMIN)
    monkeypatch.setattr(config, "PILOTAGE_URL", "https://exemple.test/pilotage")
    monkeypatch.setattr(notifications.telegram_notify, "envoyer_message", telegram)
    monkeypatch.setattr(notifications.svc_email, "envoyer_email", email)
    return telegram, email


def _journee_gherkin(db):
    """Hier : 84 appels d'usage, 3 jardiniers, 0,04 €, 98 % de succès ; 7 jours avant : 60 appels par jour."""
    for i in range(84):
        _ligne(db, HIER, user_id=1 + i % 3, issue="ok" if i >= 2 else "erreur" if i == 0 else "quota", cout=476)
    for j in range(1, 8):
        for i in range(60):
            _ligne(db, HIER - timedelta(days=j), user_id=1 + i % 3, cout=476)
    db.commit()


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin et CA1 — le résumé quotidien
# ═════════════════════════════════════════════════════════════════════════════

class TestResumeQuotidien:

    def test_us317_gherkin_resume_a_8h_sans_ecrire_dans_conso_tokens(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        _journee_gherkin(db)
        avant = db.query(ConsoTokens).count()
        resultat = bilans.passer(db, datetime(2026, 11, 17, 8, 0))
        assert resultat == {"quotidien": "envoye"}
        texte = telegram.call_args.args[1]
        assert telegram.call_args.args[0] == 555
        assert "Appels : 84 (+40 %)" in texte
        assert "Jardiniers actifs : 3" in texte
        assert "0,04 €" in texte
        assert "98 %" in texte
        assert db.query(ConsoTokens).count() == avant

    def test_us317_ca1_les_six_chiffres_avec_leur_ecart(self, db):
        _journee_gherkin(db)
        sujet, texte = bilans.resume_quotidien(db, HIER)
        for libelle in ("Appels", "Jardiniers actifs", "Coût", "Taux de succès", "Latence P95 de l'agent", "Alertes ouvertes"):
            assert libelle in texte, libelle
        assert "(+40 %)" in texte and "pt)" in texte
        assert "lundi 16/11" in sujet

    def test_us317_ca1_alertes_ouvertes_comptees(self, db):
        _journee_gherkin(db)
        db.add(SeuilPilotage(id=1, indicateur="taux_erreur", perimetre="tous", fenetre_jours=1, comparaison="fixe", valeur=1, gravite="haute"))
        db.add(AlertePilotage(seuil_id=1, valeur_mesuree=1, declenchee_le=datetime(2026, 11, 16, 9, 0)))
        db.commit()
        assert "Alertes ouvertes : 1" in bilans.resume_quotidien(db, HIER)[1]

    def test_us317_ca1_l_heure_se_regle(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        monkeypatch.setattr(config, "PILOTAGE_RESUME_HEURE", 9)
        _journee_gherkin(db)
        assert bilans.passer(db, datetime(2026, 11, 17, 8, 59)) == {}
        telegram.assert_not_called()
        assert bilans.passer(db, datetime(2026, 11, 17, 9, 0)) == {"quotidien": "envoye"}

    def test_us317_ca1_huit_heures_par_defaut(self):
        assert config.PILOTAGE_RESUME_HEURE == 8


class TestCA2JourSansAppel:

    def test_us317_ca2_une_ligne_quand_aucun_appel_d_usage(self, db):
        sujet, texte = bilans.resume_quotidien(db, HIER)
        lignes = [l for l in texte.split("\n") if l.strip()]
        assert "aucun appel d'usage" in lignes[0]
        assert len(lignes) <= 3 and "Appels :" not in texte

    def test_us317_ca2_des_appels_de_fond_seuls_ne_font_pas_un_jour_d_usage(self, db):
        for _ in range(5):
            _ligne(db, HIER, provenance="fond", user_id=1)
        db.commit()
        texte = bilans.resume_quotidien(db, HIER)[1]
        assert "aucun appel d'usage" in texte and "5 appels de fond" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — le bilan hebdomadaire
# ═════════════════════════════════════════════════════════════════════════════

def _semaine(db):
    debut, avant = date(2026, 11, 16), date(2026, 11, 9)
    for j in range(7):
        for i in range(10):
            _ligne(db, debut + timedelta(days=j), user_id=1 + i % 2, modele="mistral/small" if i % 2 else "mistral/large",
                   appel_type="agent" if i < 6 else "question", cout=2000, tokens_in=2000, latence_ms=400,
                   echange_ref=f"s{j}{i // 2}", version="3.133.0" if j >= 2 else "3.132.0")
            _ligne(db, avant + timedelta(days=j), user_id=1, cout=1000, tokens_in=1000, latence_ms=200, echange_ref=f"p{j}{i // 2}",
                   version="3.132.0")
    db.add(SeuilPilotage(id=1, indicateur="taux_erreur", perimetre="tous", fenetre_jours=1, comparaison="fixe", valeur=1, gravite="haute"))
    db.add(AlertePilotage(seuil_id=1, valeur_mesuree=12.5, declenchee_le=datetime(2026, 11, 18, 9, 0), resolue_le=datetime(2026, 11, 18, 11, 0)))
    db.commit()


class TestBilanHebdomadaire:

    def test_us317_ca3_la_semaine_ecoulee_lundi_a_dimanche(self):
        assert bilans.semaine_du_bilan(LUNDI_BILAN) == (date(2026, 11, 16), date(2026, 11, 22))
        assert bilans.semaine_du_bilan(date(2026, 11, 29)) == (date(2026, 11, 16), date(2026, 11, 22))

    def test_us317_ca3_contenu_complet(self, db, envois):
        _semaine(db)
        sujet, texte = bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))
        assert "16/11 au 22/11" in sujet
        assert "Appels : 70" in texte and "Semaine précédente : 70 appels" in texte      # même indicateurs, deux semaines
        assert "Répartition du coût par modèle" in texte and "mistral/large" in texte and "mistral/small" in texte
        assert "Répartition du coût par type d'appel" in texte and "  - agent :" in texte and "  - question :" in texte
        assert "Coût par jardinier actif" in texte
        assert "Les 3 plus fortes variations" in texte
        assert "Alertes de la semaine" in texte and "Taux d'erreur : 12,5 %" in texte and "(résolue)" in texte
        assert "Versions livrées dans la semaine" in texte and "v3.133.0 : 2 000 jetons par appel agent" in texte
        assert "https://exemple.test/pilotage/#/consommation" in texte

    def test_us317_ca3_trois_variations_au_plus_les_plus_fortes_d_abord(self, db):
        _semaine(db)
        texte = bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))[1]
        bloc = texte.split("Les 3 plus fortes variations :\n")[1].split("\n\n")[0].split("\n")
        assert 1 <= len(bloc) <= 3
        pourcents = [abs(int(re.search(r"[+−](\d[\d ]*) %", l).group(1).replace(" ", ""))) for l in bloc]
        assert pourcents == sorted(pourcents, reverse=True)

    def test_us317_ca3_une_version_deja_connue_n_est_pas_livree_dans_la_semaine(self, db):
        _semaine(db)
        texte = bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))[1]
        assert "v3.132.0" not in texte.split("Versions livrées dans la semaine :")[1]

    def test_us317_ca3_envoye_par_email_le_lundi(self, db, envois, monkeypatch):
        telegram, email = envois
        monkeypatch.setattr(config, "PILOTAGE_BILAN_HEBDO", True)
        _semaine(db)
        assert bilans.passer(db, datetime(2026, 11, 23, 8, 0)) == {"hebdomadaire": "envoye"}
        assert email.call_args.args[0] == ADMIN and "Bilan hebdomadaire" in email.call_args.args[1]
        telegram.assert_not_called()

    def test_us317_ca3_pas_envoye_un_autre_jour_que_le_lundi(self, db, envois, monkeypatch):
        _, email = envois
        monkeypatch.setattr(config, "PILOTAGE_BILAN_HEBDO", True)
        _semaine(db)
        assert bilans.passer(db, datetime(2026, 11, 24, 12, 0)) == {}
        email.assert_not_called()

    def test_us317_ca3_une_semaine_vide_se_produit_sans_erreur(self, db):
        sujet, texte = bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))
        assert "Aucune alerte cette semaine." in texte and "Aucune nouvelle version observée." in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — provenances
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Provenances:

    def test_us317_ca4_la_mesure_n_entre_pas_dans_les_chiffres_mais_a_sa_ligne(self, db):
        for _ in range(25):
            _ligne(db, HIER, provenance="usage")
        for _ in range(500):
            _ligne(db, HIER, provenance="mesure", cout=5000)
            _ligne(db, HIER, provenance="test", cout=5000)
        db.commit()
        texte = bilans.resume_quotidien(db, HIER)[1]
        assert "Appels : 25" in texte
        assert "Mesures (hors chiffres) : 500 appels" in texte

    def test_us317_ca4_le_fond_compte(self, db):
        for _ in range(10):
            _ligne(db, HIER, provenance="usage")
        for _ in range(5):
            _ligne(db, HIER, provenance="fond")
        db.commit()
        assert "Appels : 15" in bilans.resume_quotidien(db, HIER)[1]

    def test_us317_ca4_sans_mesure_pas_de_ligne_de_mesure(self, db):
        _ligne(db, HIER)
        db.commit()
        assert "Mesures" not in bilans.resume_quotidien(db, HIER)[1]


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — gabarit, aucun modèle
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5SansModele:

    def test_us317_ca5_aucune_ligne_conso_tokens_ecrite_a_la_production(self, db):
        _semaine(db)
        _journee_gherkin(db)
        avant = db.query(ConsoTokens).count()
        bilans.resume_quotidien(db, HIER)
        bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))
        assert db.query(ConsoTokens).count() == avant

    def test_us317_ca5_le_module_n_appelle_aucun_modele(self):
        source = (ROOT / "app/services/pilotage/bilans.py").read_text(encoding="utf-8")
        assert not re.search(r"^\s*(from|import)\s+(llm\.(groq_client|routeur)|groq|mistralai|openai)", source, re.M)
        assert not re.search(r"appeler_chat|appeler_transcription|get_client", source)


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — lien
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6Lien:

    def test_us317_ca6_chaque_envoi_porte_un_lien_vers_la_pwa(self, db, envois):
        _journee_gherkin(db)
        _semaine(db)
        assert "https://exemple.test/pilotage/#/consommation" in bilans.resume_quotidien(db, HIER)[1]
        assert "https://exemple.test/pilotage/#/consommation" in bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))[1]
        assert "https://exemple.test/pilotage/#/consommation" in bilans.resume_quotidien(db, date(2026, 1, 1))[1]   # jour vide


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — interrupteurs
# ═════════════════════════════════════════════════════════════════════════════

class TestCA7Interrupteurs:

    def test_us317_ca7_desactives_par_defaut(self):
        source = (ROOT / "app/config.py").read_text(encoding="utf-8")
        assert re.search(r'PILOTAGE_RESUME_QUOTIDIEN\s*=\s*_booleen_pilotage\("PILOTAGE_RESUME_QUOTIDIEN"\)', source)
        assert re.search(r'PILOTAGE_BILAN_HEBDO\s*=\s*_booleen_pilotage\("PILOTAGE_BILAN_HEBDO"\)', source)
        assert config.PILOTAGE_RESUME_QUOTIDIEN is False and config.PILOTAGE_BILAN_HEBDO is False

    def test_us317_ca7_rien_ne_part_interrupteurs_eteints(self, db, envois):
        telegram, email = envois
        _journee_gherkin(db)
        assert bilans.passer(db, datetime(2026, 11, 23, 9, 0)) == {}
        telegram.assert_not_called()
        email.assert_not_called()
        assert db.query(BilanPilotage).count() == 0

    def test_us317_ca7_les_deux_interrupteurs_sont_independants(self, db, envois, monkeypatch):
        telegram, email = envois
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        _journee_gherkin(db)
        assert set(bilans.passer(db, datetime(2026, 11, 23, 9, 0))) == {"quotidien"}
        email.assert_not_called()
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", False)
        monkeypatch.setattr(config, "PILOTAGE_BILAN_HEBDO", True)
        assert set(bilans.passer(db, datetime(2026, 11, 23, 9, 30))) == {"hebdomadaire"}

    def test_us317_ca7_la_vue_seuils_les_affiche(self, db, monkeypatch):
        from app.services.pilotage import seuils
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        reglages = seuils.vue_seuils(db)["reglages"]
        assert reglages["resume_quotidien"] is True and reglages["bilan_hebdomadaire"] is False and reglages["resume_heure"] == 8


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — jamais deux fois, un seul rejeu
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8Trace:

    def test_us317_ca8_la_migration_garantit_l_unicite_par_periode(self):
        sql = (ROOT / "migrations/migration_v80.sql").read_text(encoding="utf-8")
        assert "uq_bilans_pilotage_periode UNIQUE (type, periode_debut)" in sql
        assert "DROP TABLE IF EXISTS bilans_pilotage" in (ROOT / "migrations/rollback_v80.sql").read_text(encoding="utf-8")

    def test_us317_ca8_jamais_deux_fois_la_meme_periode(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        _journee_gherkin(db)
        bilans.passer(db, datetime(2026, 11, 17, 8, 0))
        assert bilans.passer(db, datetime(2026, 11, 17, 8, 30)) == {}
        assert bilans.passer(db, datetime(2026, 11, 17, 23, 0)) == {}
        assert telegram.call_count == 1
        ligne = db.query(BilanPilotage).one()
        assert ligne.statut == "envoye" and ligne.tentatives == 1 and ligne.envoye_le is not None

    def test_us317_ca8_la_base_refuse_un_doublon(self, db):
        db.add(BilanPilotage(type="quotidien", periode_debut=HIER, periode_fin=HIER, statut="envoye", tentatives=1))
        db.commit()
        db.add(BilanPilotage(type="quotidien", periode_debut=HIER, periode_fin=HIER, statut="echoue", tentatives=1))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_us317_ca8_un_echec_est_journalise_puis_rejoue_une_seule_fois(self, db, envois, monkeypatch, caplog):
        telegram, _ = envois
        telegram.return_value = False
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        _journee_gherkin(db)
        with caplog.at_level("ERROR", logger="potager"):
            assert bilans.passer(db, datetime(2026, 11, 17, 8, 0)) == {"quotidien": "echoue"}
        assert "échec d'envoi" in caplog.text
        assert bilans.passer(db, datetime(2026, 11, 17, 8, 30)) == {"quotidien": "echoue"}      # le rejeu unique
        assert bilans.passer(db, datetime(2026, 11, 17, 9, 0)) == {}                           # plus jamais
        assert telegram.call_count == 2
        ligne = db.query(BilanPilotage).one()
        assert ligne.statut == "echoue" and ligne.tentatives == 2 and ligne.erreur

    def test_us317_ca8_le_rejeu_qui_reussit_cloture_la_periode(self, db, envois, monkeypatch):
        telegram, _ = envois
        telegram.return_value = False
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        _journee_gherkin(db)
        bilans.passer(db, datetime(2026, 11, 17, 8, 0))
        telegram.return_value = True
        assert bilans.passer(db, datetime(2026, 11, 17, 8, 30)) == {"quotidien": "envoye"}
        assert bilans.passer(db, datetime(2026, 11, 17, 9, 0)) == {}
        assert db.query(BilanPilotage).one().statut == "envoye"

    def test_us317_ca8_un_redemarrage_apres_l_heure_rattrape_le_resume_du_jour(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        _journee_gherkin(db)
        assert bilans.passer(db, datetime(2026, 11, 17, 14, 0)) == {"quotidien": "envoye"}
        assert telegram.call_count == 1

    def test_us317_ca8_chaque_jour_a_son_propre_resume(self, db, envois, monkeypatch):
        telegram, _ = envois
        monkeypatch.setattr(config, "PILOTAGE_RESUME_QUOTIDIEN", True)
        bilans.passer(db, datetime(2026, 11, 17, 8, 0))
        bilans.passer(db, datetime(2026, 11, 18, 8, 0))
        assert db.query(BilanPilotage).count() == 2 and telegram.call_count == 2


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — pas de nom, pas de message
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9Confidentialite:

    def test_us317_ca9_aucun_nom_de_jardinier_ni_adresse_dans_les_textes(self, db):
        _journee_gherkin(db)
        _semaine(db)
        textes = [
            bilans.resume_quotidien(db, HIER)[1],
            bilans.bilan_hebdomadaire(db, date(2026, 11, 16), date(2026, 11, 22))[1],
        ]
        for texte in textes:
            for interdit in ("Alice", "Dupont", "Bob", "Martin", "Clara", "Petit", "@example.com", ADMIN):
                assert interdit not in texte, interdit

    def test_us317_ca9_le_module_ne_lit_ni_noms_ni_messages(self):
        source = (ROOT / "app/services/pilotage/bilans.py").read_text(encoding="utf-8")
        assert not re.search(r"\bUser\b|Potager\b|Evenement|Observation|EchangeConversation|\.nom\b|\.email\b", source)
