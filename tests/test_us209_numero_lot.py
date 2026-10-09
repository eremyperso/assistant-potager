"""
tests/test_us209_numero_lot.py — Numéroter les lots de semis [US-209]
=====================================================================

- CA1  numéro court, unique par potager, ordre de création, jamais réutilisé
- CA2  attribué à l'enregistrement, sans collision (test de concurrence)
- CA3  reprise de l'existant : la requête DE LA MIGRATION est exécutée, idempotente
- CA4  correction de filière dans les deux sens
- CA5  référence « lot 128 » dans chaque geste de pépinière, sans modèle
- CA6  numéro inconnu ou contradictoire signalé, jamais corrigé en silence
- CA7  /lot et la phrase « où en est le lot 128 ? »
- CA8  les récapitulatifs affichent le numéro
- CA9  lecture par numéro (service et API)
- CA13 ce fichier, dont l'isolation entre potagers

Aucun appel réseau, aucun appel au modèle.
"""
from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.services import lots_pepiniere as lots
from app.services import stock as svc_stock
from app.services.context import TenantContext
from database.db import Base
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import parser_saisie

RACINE = Path(__file__).resolve().parent.parent
MIGRATION = RACINE / "migrations" / "migration_v55.sql"
CTX = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")


@pytest.fixture
def db(test_db):
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    for nom in ("chou", "tomate", "carotte"):
        test_db.add(CultureConfig(nom=nom, type_organe_recolte="végétatif"))
    test_db.add_all([
        Parcelle(id=1, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
        Parcelle(id=3, nom="serre b", nom_normalise="serreb", potager_id=2, est_pepiniere=True),
    ])
    test_db.commit()
    return test_db


def _semis(db, culture="chou", variete=None, parcelle_id=2, potager_id=1, quand=datetime(2026, 4, 1),
           quantite=48.0, contexte=None):
    ev = Evenement(type_action="semis", culture=culture, variete=variete, quantite=quantite,
                   unite="graines", parcelle_id=parcelle_id, date=quand, potager_id=potager_id,
                   contexte_semis=contexte)
    db.add(ev)
    db.commit()
    return ev


def _godet(db, semis, plants=40, graines=48, potager_id=1):
    ev = Evenement(type_action="mise_en_godet", culture=semis.culture, variete=semis.variete,
                   nb_plants_godets=plants, nb_graines_semees=graines, origine_graines_id=semis.id,
                   potager_id=potager_id, date=datetime(2026, 4, 20))
    db.add(ev)
    db.commit()
    return ev


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — le numéro
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1:

    def test_us209_ca1_numeros_dans_l_ordre_de_creation_a_partir_de_1(self, db):
        a, b, c = _semis(db), _semis(db, "tomate"), _semis(db, "carotte")
        assert [a.numero_lot, b.numero_lot, c.numero_lot] == [1, 2, 3]

    def test_us209_ca1_le_numero_n_est_jamais_l_identifiant_technique(self, db):
        _semis(db, potager_id=2, parcelle_id=3)           # id 1, lot 1 de B
        ev = _semis(db)                                    # id 2, lot 1 de A
        assert ev.id == 2 and ev.numero_lot == 1

    def test_us209_ca1_jamais_reutilise_apres_suppression(self, db):
        a, b = _semis(db), _semis(db)
        db.delete(b)
        db.commit()
        c = _semis(db)
        assert (a.numero_lot, c.numero_lot) == (1, 3)

    def test_us209_ca1_un_semis_de_pleine_terre_n_a_pas_de_numero(self, db):
        assert _semis(db, parcelle_id=1).numero_lot is None

    def test_us209_ca1_un_semis_sans_parcelle_est_un_lot(self, db):
        assert _semis(db, parcelle_id=None).numero_lot == 1

    def test_us209_ca1_seul_un_semis_porte_un_numero(self, db):
        godet = _godet(db, _semis(db))
        assert godet.numero_lot is None

    def test_us209_ca1_la_lecture_par_lot_expose_le_numero(self, db):
        semis = _semis(db)
        _godet(db, semis)
        lot = svc_stock.calcul_lots_pepiniere(db, CTX)[0]
        assert lot["numero_lot"] == semis.numero_lot == 1

    def test_us209_ca1_le_lot_sans_semis_rattache_n_a_pas_de_numero(self, db):
        db.add(Evenement(type_action="mise_en_godet", culture="chou", nb_plants_godets=5,
                         potager_id=1, date=datetime(2026, 4, 20)))
        db.commit()
        lot = svc_stock.calcul_lots_pepiniere(db, CTX)[0]
        assert lot["sans_semis_rattache"] is True and lot["numero_lot"] is None

    def test_us209_ca1_compteur_par_potager(self, db):
        _semis(db)
        _semis(db)
        _semis(db, potager_id=2, parcelle_id=3)
        assert db.get(Potager, 1).compteur_lots == 2
        assert db.get(Potager, 2).compteur_lots == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — attribué à l'enregistrement, sans collision
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2:

    def test_us209_ca2_plusieurs_semis_dans_la_meme_transaction(self, db):
        evs = [Evenement(type_action="semis", culture="chou", quantite=10, unite="graines",
                         parcelle_id=2, potager_id=1, date=datetime(2026, 4, 1)) for _ in range(4)]
        db.add_all(evs)
        db.commit()
        assert sorted(e.numero_lot for e in evs) == [1, 2, 3, 4]

    def test_us209_ca2_le_numero_fait_partie_de_la_transaction(self, db):
        ev = Evenement(type_action="semis", culture="chou", quantite=10, unite="graines",
                       parcelle_id=2, potager_id=1, date=datetime(2026, 4, 1))
        db.add(ev)
        db.flush()
        assert ev.numero_lot == 1
        db.rollback()                                   # le compteur recule avec la transaction
        assert _semis(db).numero_lot == 1

    def test_us209_ca2_concurrence_aucun_doublon(self, tmp_path):
        """Huit sessions simultanées sur la même base : tous les numéros sont distincts."""
        moteur = create_engine(
            f"sqlite:///{tmp_path / 'lots.db'}", connect_args={"timeout": 60}, poolclass=NullPool,
        )
        Base.metadata.create_all(bind=moteur)
        fabrique = sessionmaker(bind=moteur, autoflush=False)
        with fabrique() as s:
            s.add(User(id=1, email="a@potager.test"))
            s.flush()
            s.add(Potager(id=1, nom="A", proprietaire_id=1))
            s.commit()

        erreurs: list = []

        def semer():
            try:
                for _ in range(5):
                    with fabrique() as s:
                        s.add(Evenement(type_action="semis", culture="chou", quantite=1,
                                        unite="graines", potager_id=1, date=datetime(2026, 4, 1)))
                        s.commit()
            except Exception as e:  # pragma: no cover - remonté par l'assertion
                erreurs.append(e)

        fils = [threading.Thread(target=semer) for _ in range(8)]
        [f.start() for f in fils]
        [f.join() for f in fils]
        assert not erreurs
        with fabrique() as s:
            numeros = [r[0] for r in s.execute(text("SELECT numero_lot FROM evenements"))]
        assert sorted(numeros) == list(range(1, 41))

    def test_us209_ca2_index_unique_par_potager(self, db):
        _semis(db)
        db.add(Evenement(type_action="semis", culture="chou", potager_id=1, parcelle_id=2,
                         numero_lot=1, date=datetime(2026, 4, 2)))
        with pytest.raises(Exception):
            db.commit()
        db.rollback()


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — reprise de l'existant
# ═════════════════════════════════════════════════════════════════════════════
def _requete_reprise() -> list[str]:
    sql = MIGRATION.read_text(encoding="utf-8")
    m = re.search(r"-- -- REPRISE:DEBUT --(.*?)-- -- REPRISE:FIN --", sql, re.S)
    assert m, "marqueurs REPRISE absents de migration_v55.sql"
    return [r.strip() for r in m.group(1).split(";") if r.strip()]


def _rejouer_reprise(db) -> None:
    for requete in _requete_reprise():
        db.execute(text(requete))
    db.commit()


def _semis_non_numerote(db, **kw):
    """Un semis tel que l'avait enregistré l'application AVANT cette US."""
    ev = _semis(db, **kw)
    db.execute(text("UPDATE evenements SET numero_lot = NULL WHERE id = :i"), {"i": ev.id})
    db.execute(text("UPDATE potagers SET compteur_lots = 0"))
    db.commit()
    db.expire_all()
    return ev


class TestCA3:

    def test_us209_ca3_reprise_potager_par_potager_dans_l_ordre_des_dates(self, db):
        tard = _semis_non_numerote(db, quand=datetime(2026, 5, 1))
        tot = _semis_non_numerote(db, quand=datetime(2026, 3, 1))
        autre = _semis_non_numerote(db, potager_id=2, parcelle_id=3, quand=datetime(2026, 6, 1))
        _rejouer_reprise(db)
        assert (tot.numero_lot, tard.numero_lot, autre.numero_lot) == (1, 2, 1)

    def test_us209_ca3_reprise_idempotente(self, db):
        a = _semis_non_numerote(db, quand=datetime(2026, 3, 1))
        b = _semis_non_numerote(db, quand=datetime(2026, 4, 1))
        _rejouer_reprise(db)
        avant = (a.numero_lot, b.numero_lot)
        _rejouer_reprise(db)
        db.expire_all()
        assert (a.numero_lot, b.numero_lot) == avant == (1, 2)

    def test_us209_ca3_reprise_continue_apres_le_plus_grand_numero(self, db):
        deja = _semis(db)                                         # lot 1
        nouveau = _semis_non_numerote(db)
        db.execute(text("UPDATE evenements SET numero_lot = 7 WHERE id = :i"), {"i": deja.id})
        db.commit()
        db.expire_all()
        _rejouer_reprise(db)
        assert deja.numero_lot == 7 and nouveau.numero_lot == 8

    def test_us209_ca3_reprise_aligne_le_compteur_sans_jamais_le_baisser(self, db):
        _semis_non_numerote(db)
        _rejouer_reprise(db)
        assert db.get(Potager, 1).compteur_lots == 1
        db.execute(text("UPDATE potagers SET compteur_lots = 50 WHERE id = 1"))
        db.commit()
        _rejouer_reprise(db)
        assert db.get(Potager, 1).compteur_lots == 50

    def test_us209_ca3_reprise_ne_numerote_que_l_ensemble_des_lots(self, db):
        pleine_terre = _semis_non_numerote(db, parcelle_id=1)
        corrige = _semis_non_numerote(db, contexte="pleine_terre")
        lot = _semis_non_numerote(db)
        _rejouer_reprise(db)
        assert pleine_terre.numero_lot is None and corrige.numero_lot is None
        assert lot.numero_lot == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — correction de filière
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4:

    def test_us209_ca4_pepiniere_vers_pleine_terre_garde_son_numero_et_quitte_la_liste(self, db):
        semis = _semis(db)
        assert len(svc_stock.calcul_lots_pepiniere(db, CTX)) == 1
        semis.contexte_semis = "pleine_terre"
        db.commit()
        assert semis.numero_lot == 1
        assert svc_stock.calcul_lots_pepiniere(db, CTX) == []

    def test_us209_ca4_changement_de_parcelle_vers_pleine_terre(self, db):
        semis = _semis(db)
        semis.parcelle_id = 1
        db.commit()
        assert semis.numero_lot == 1
        assert svc_stock.calcul_lots_pepiniere(db, CTX) == []

    def test_us209_ca4_pleine_terre_vers_pepiniere_recoit_un_numero(self, db):
        _semis(db)                                                 # lot 1
        semis = _semis(db, parcelle_id=1)
        assert semis.numero_lot is None
        semis.parcelle_id = 2
        db.commit()
        assert semis.numero_lot == 2

    def test_us209_ca4_retour_en_pepiniere_ne_renumerote_pas(self, db):
        semis = _semis(db)
        semis.contexte_semis = "pleine_terre"
        db.commit()
        semis.contexte_semis = "pepiniere"
        db.commit()
        assert semis.numero_lot == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — référence au lot, sans modèle
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("phrase,numero", [
    ("lot 128", 128), ("le lot 128", 128), ("du lot 128", 128), ("#128", 128),
    ("lot n° 128", 128), ("lot numéro 128", 128), ("Lot128", 128),
])
def test_us209_ca5_formes_de_reference(phrase, numero):
    assert lots.extraire_reference_lot(f"repiqué 40 plants {phrase} en godet")[1] == numero


def test_us209_ca5_douze_lots_de_godets_est_une_quantite():
    assert lots.extraire_reference_lot("vendu 12 lots de godets")[1] is None


def test_us209_ca5_deux_numeros_sont_ambigus():
    assert lots.extraire_reference_lot("le lot 5 et le lot 6")[1] is None


class TestParseur:
    """La grammaire déterministe lit la référence — le parseur ne rend jamais la main au modèle."""

    def _parse(self, db, phrase):
        return parser_saisie(phrase, CTX, db=db, aujourd_hui=datetime(2026, 5, 1).date())

    def test_us209_ca5_mise_en_godet(self, db):
        res = self._parse(db, "repiqué 40 plants du lot 128 en godet")
        assert res.reconnu, res.raison
        item = res.items[0]
        assert item["action"] == "mise_en_godet" and item["numero_lot_cite"] == 128
        assert item["nb_plants_godets"] == 40

    @pytest.mark.parametrize("phrase,action", [
        ("perdu 5 plants de chou du lot 128", "perte"),
        ("vendu 6 plants de chou #128", "vendu"),
        ("planté 10 plants de chou du lot 128", "plantation"),
    ])
    def test_us209_ca5_autres_gestes_de_pepiniere(self, db, phrase, action):
        res = self._parse(db, phrase)
        assert res.reconnu, res.raison
        assert res.items[0]["numero_lot_cite"] == 128
        assert res.items[0]["action"] == action

    def test_us209_ca5_un_geste_hors_pepiniere_ne_lit_pas_de_lot(self, db):
        res = self._parse(db, "récolté 3 kg de tomate lot 128")
        assert not res.reconnu or "numero_lot_cite" not in res.items[0]


class TestRattachement:

    def _lot(self, db):
        semis = _semis(db, "chou", "frisé")
        return semis

    def test_us209_ca5_mise_en_godet_rattachee_au_lot_cite(self, db):
        semis = self._lot(db)
        autre = _semis(db, "chou", "frisé", quand=datetime(2026, 4, 5))   # deux candidats : ambigu sans le numéro
        items = [{"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 40,
                  "nb_graines_semees": 48, "numero_lot_cite": semis.numero_lot}]
        lots.resoudre_references(db, CTX, items)
        assert items[0]["origine_graines_id"] == semis.id != autre.id
        assert items[0]["_lot_numero"] == semis.numero_lot
        assert "_alerte_lot" not in items[0]

    def test_us209_ca5_culture_reprise_du_lot_quand_elle_n_est_pas_dite(self, db):
        semis = self._lot(db)
        items = [{"action": "mise_en_godet", "nb_plants_godets": 40, "numero_lot_cite": 1}]
        lots.resoudre_references(db, CTX, items)
        assert items[0]["culture"] == "chou" and items[0]["variete"] == "frisé"

    def test_us209_ca5_perte_et_vente_imputees_au_lot_cite(self, db):
        a = _semis(db)
        b = _semis(db, quand=datetime(2026, 4, 5))
        _godet(db, a, plants=20, graines=24)
        _godet(db, b, plants=20, graines=24)
        for numero, action in ((b.numero_lot, "perte_godet"), (b.numero_lot, "vendu")):
            item = {"action": action, "culture": "chou", "quantite": 3, "unite": "plants",
                    "numero_lot_cite": numero}
            lots.resoudre_references(db, CTX, [item])
            db.add(Evenement(type_action=action, culture="chou", quantite=3, unite="plants",
                             origine_graines_id=item["origine_graines_id"], potager_id=1,
                             date=datetime(2026, 5, 1)))
        db.commit()
        par_numero = {l["numero_lot"]: l for l in svc_stock.calcul_lots_pepiniere(db, CTX)}
        assert par_numero[b.numero_lot]["nb_pertes_godet"] == 3 and par_numero[b.numero_lot]["nb_vendus"] == 3
        # sans la citation, le FIFO aurait imputé ces sorties au lot le plus ancien
        assert par_numero[a.numero_lot]["nb_pertes_godet"] == 0 and par_numero[a.numero_lot]["nb_vendus"] == 0

    def test_us209_ca5_une_perte_citant_un_lot_devient_une_perte_en_godet(self, db):
        self._lot(db)
        item = {"action": "perte", "culture": "chou", "quantite": 2, "numero_lot_cite": 1}
        lots.resoudre_references(db, CTX, [item])
        assert item["action"] == "perte_godet"

    def test_us209_ca5_plantation_chainee_au_lot_cite(self, db):
        a = _semis(db)
        b = _semis(db, quand=datetime(2026, 4, 5))
        ga, gb = _godet(db, a, 20, 24), _godet(db, b, 20, 24)
        item = {"action": "plantation", "culture": "chou", "quantite": 10, "unite": "plants",
                "numero_lot_cite": b.numero_lot}
        lots.resoudre_references(db, CTX, [item])
        assert item["source_evenement_ids"] == str(gb.id) != str(ga.id)

    def test_us209_ca5_un_geste_sans_lot_n_est_pas_touche(self, db):
        self._lot(db)
        item = {"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 4}
        lots.resoudre_references(db, CTX, [item])
        assert "origine_graines_id" not in item and "_alerte_lot" not in item

    def test_us209_ca5_le_modele_n_est_pas_sollicite(self, db):
        with patch("llm.passerelle.appeler_groq", side_effect=AssertionError("modèle sollicité"), create=True):
            self._lot(db)
            items = [{"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 4, "numero_lot_cite": 1}]
            lots.resoudre_references(db, CTX, items)
        assert items[0]["_lot_numero"] == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — inconnu ou contradictoire
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6:

    def test_us209_ca6_numero_inconnu_signale_sans_rattachement(self, db):
        _semis(db)
        item = {"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 4, "numero_lot_cite": 999}
        lots.resoudre_references(db, CTX, [item])
        assert "999" in item["_alerte_lot"]
        assert "origine_graines_id" not in item and "_lot_numero" not in item

    def test_us209_ca6_scenario_numero_contradictoire(self, db):
        _semis(db, "chou", "frisé")
        item = {"action": "mise_en_godet", "culture": "tomate", "nb_plants_godets": 10, "numero_lot_cite": 1}
        lots.resoudre_references(db, CTX, [item])
        assert "chou frisé" in item["_alerte_lot"] and "tomate" in item["_alerte_lot"]
        assert item["culture"] == "tomate"                       # rien n'est corrigé en silence
        assert "origine_graines_id" not in item

    def test_us209_ca6_l_alerte_est_au_recapitulatif(self):
        from app.bot.enregistrement import _build_action_summary
        resume = _build_action_summary([{"action": "mise_en_godet", "culture": "tomate",
                                          "_alerte_lot": "⚠️ Le lot n° 1 est un lot de chou"}])
        assert "Le lot n° 1 est un lot de chou" in resume


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — /lot
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7:

    def test_us209_ca7_fiche_du_lot(self, db):
        semis = _semis(db, "chou", "frisé")
        _godet(db, semis, plants=40, graines=48)
        fiche = lots.formater_lot_telegram(svc_stock.lot_pepiniere_par_numero(db, CTX, 1))
        for attendu in ("Lot n° 1", "chou frisé", "2026-04-01", "serre", "48", "40"):
            assert attendu in fiche

    @pytest.mark.parametrize("phrase", [
        "où en est le lot 128 ?", "montre-moi le lot 128", "lot 128", "affiche le lot n° 128",
    ])
    def test_us209_ca7_la_phrase_est_une_commande_sans_modele(self, phrase):
        from app.services.interpreteur_commandes import interpreter
        res = interpreter(phrase, CTX, autoriser_modele=False)
        assert res is not None and res.commande_equivalente() == "/lot 128"

    def test_us209_ca7_la_commande_est_tranchee_au_catalogue(self):
        """Dictable ; la parité menu / bot / catalogue est vérifiée par test_us172 (controler_parite)."""
        from app.services import menu_commandes as menu
        assert any(f.commande == "lot" and not f.confirmation for f in menu.FORMES_DICTABLES)
        assert "lot" in menu.DESCRIPTIONS

    @pytest.mark.asyncio
    async def test_us209_ca7_cmd_lot_repond_avec_la_fiche(self, db):
        from app.bot.godets import cmd_lot
        _semis(db, "chou")
        update, ctx = MagicMock(), MagicMock(args=["1"])
        update.message.reply_text = AsyncMock()
        with patch("app.bot.godets.SessionLocal", return_value=db), \
             patch("app.bot.godets.current_context", return_value=CTX), \
             patch.object(db, "close"):
            await cmd_lot(update, ctx)
        assert "Lot n° 1" in update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_us209_ca7_cmd_lot_numero_inconnu_ou_absent(self, db):
        from app.bot.godets import cmd_lot
        for args, attendu in ((["999"], "Aucun lot n° 999"), ([], "Aucun lot de pépinière")):
            update, ctx = MagicMock(), MagicMock(args=args)
            update.message.reply_text = AsyncMock()
            with patch("app.bot.godets.SessionLocal", return_value=db), \
                 patch("app.bot.godets.current_context", return_value=CTX), \
                 patch.object(db, "close"):
                await cmd_lot(update, ctx)
            assert attendu in update.message.reply_text.await_args.args[0]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — récapitulatifs
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8:

    def test_us209_ca8_le_recap_d_un_semis_annonce_le_lot(self):
        from app.bot.enregistrement import _build_recap
        assert "n° 128" in _build_recap({"action": "semis", "culture": "chou", "_lot_numero": 128}, 9)

    def test_us209_ca8_le_recap_d_une_mise_en_godet_cite_le_lot(self):
        from app.bot.enregistrement import _build_recap
        recap = _build_recap({"action": "mise_en_godet", "culture": "chou", "nb_plants_godets": 4,
                              "_lot_numero": 128}, 9)
        assert "n° 128" in recap

    def test_us209_ca8_le_resume_avant_confirmation_cite_le_lot(self):
        from app.bot.enregistrement import _build_action_summary
        assert "n° 128" in _build_action_summary([{"action": "vendu", "culture": "chou", "_lot_numero": 128}])


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — lecture par numéro (service et API) · isolation entre potagers
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9:

    def test_us209_ca9_lecture_par_numero(self, db):
        _semis(db, "chou")
        assert svc_stock.lot_pepiniere_par_numero(db, CTX, 1)["culture"] == "chou"
        assert svc_stock.lot_pepiniere_par_numero(db, CTX, 2) is None

    def test_us209_isolation_le_lot_5_de_l_autre_potager_n_est_jamais_trouve(self, db):
        for _ in range(5):
            _semis(db, "chou", potager_id=1, parcelle_id=2)
        _semis(db, "tomate", potager_id=2, parcelle_id=3)
        for _ in range(4):
            _semis(db, "carotte", potager_id=2, parcelle_id=3)
        assert svc_stock.lot_pepiniere_par_numero(db, CTX, 5)["culture"] == "chou"
        assert svc_stock.lot_pepiniere_par_numero(db, CTX_B, 5)["culture"] == "carotte"
        assert svc_stock.lot_pepiniere_par_numero(db, CTX_B, 6) is None

    def test_us209_isolation_une_reference_ne_rattache_pas_au_lot_d_un_autre_potager(self, db):
        _semis(db, "tomate", potager_id=2, parcelle_id=3)
        item = {"action": "mise_en_godet", "culture": "tomate", "nb_plants_godets": 4, "numero_lot_cite": 1}
        lots.resoudre_references(db, CTX, [item])
        assert "origine_graines_id" not in item and "Aucun lot n° 1" in item["_alerte_lot"]

    @pytest.fixture
    def client(self):
        """Même stratégie que test_us065 : SessionLocal et la lecture sont substituées
        (un TestClient tourne dans un autre thread que la base SQLite en mémoire)."""
        from fastapi.testclient import TestClient
        from app.api.main import app, get_current_user_ctx
        app.dependency_overrides[get_current_user_ctx] = lambda: CTX
        with patch("app.api.main.SessionLocal", return_value=MagicMock()):
            yield TestClient(app)
        app.dependency_overrides.clear()

    _LOT = {
        "lot_id": "semis-7", "semis_id": 7, "numero_lot": 128, "culture": "chou", "variete": "frisé",
        "date_semis": datetime(2026, 4, 1), "date_derniere_mise_en_godet": None, "parcelle": "serre",
        "sans_semis_rattache": False,
    }

    def test_us209_ca9_api_liste_expose_le_numero(self, client):
        with patch("app.services.stock.calcul_lots_pepiniere", return_value=[dict(self._LOT)]):
            corps = client.get("/pepiniere/lots").json()
        assert corps["lots"][0]["numero_lot"] == 128

    def test_us209_ca9_api_un_lot_par_son_numero(self, client):
        with patch("app.services.stock.lot_pepiniere_par_numero", return_value=dict(self._LOT)) as lecture:
            reponse = client.get("/pepiniere/lots/128")
        assert reponse.status_code == 200
        assert reponse.json()["numero_lot"] == 128 and reponse.json()["date_semis"] == "2026-04-01"
        assert lecture.call_args.args[2] == 128

    def test_us209_ca9_api_lot_inconnu(self, client):
        with patch("app.services.stock.lot_pepiniere_par_numero", return_value=None):
            reponse = client.get("/pepiniere/lots/128")
        assert reponse.status_code == 404
        assert reponse.json()["detail"] == "Aucun lot n° 128 dans ce potager"


# ═════════════════════════════════════════════════════════════════════════════
# CA10 / CA11 — la PWA (les règles d'affichage sont testées par `npm test`)
# ═════════════════════════════════════════════════════════════════════════════
class TestPwa:

    def test_us209_ca10_ca11_l_ecran_porte_le_numero_et_le_champ(self):
        source = (RACINE / "frontend" / "src" / "views" / "Pepiniere.jsx").read_text(encoding="utf-8")
        assert "libelleNumeroLot(lot)" in source
        assert "Aller au lot n°" in source
        assert "api.pepiniereLot(" in source

    def test_us209_ca11_l_adresse_ouvre_le_lot_par_son_numero(self):
        source = (RACINE / "frontend" / "src" / "views" / "Pepiniere.jsx").read_text(encoding="utf-8")
        assert "l.numero_lot === numero" in source


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — définition de terminé
# ═════════════════════════════════════════════════════════════════════════════
class TestDefinitionDeTermine:

    def test_us209_ca12_la_migration_et_son_rollback_existent(self):
        assert MIGRATION.exists() and (RACINE / "migrations" / "rollback_v55.sql").exists()

    def test_us209_ca12_les_fiches_citent_le_numero_de_lot(self):
        base = RACINE / "data" / "connaissance" / "doc_app"
        for fiche in ("pepiniere-par-lot.md", "semis-godet-plantation.md", "enregistrer-un-geste.md"):
            assert "numéro" in (base / fiche).read_text(encoding="utf-8").lower(), fiche
            assert "lot 128" in (base / fiche).read_text(encoding="utf-8"), fiche

    def test_us209_ca12_le_domaine_migrations_decrit_v55(self):
        assert "v55" in (RACINE / "docs" / "domaines" / "migrations.md").read_text(encoding="utf-8")


def test_us209_ca5_culture_du_lot_non_retiree_comme_hallucinee():
    """« repiqué 5 plants du lot 4 en godet » : la culture vient du lot, pas du texte."""
    from utils.validation import strip_culture_hallucinee
    item = {"action": "mise_en_godet", "culture": "tomate", "_lot_numero": 4}
    assert strip_culture_hallucinee(item, "repiqué 5 plants du lot 4 en godet")["culture"] == "tomate"
    sans_lot = {"action": "mise_en_godet", "culture": "tomate"}
    assert strip_culture_hallucinee(sans_lot, "repiqué 5 plants en godet")["culture"] is None


# ═════════════════════════════════════════════════════════════════════════════
# Liste des lots — retrouver un numéro oublié
# ═════════════════════════════════════════════════════════════════════════════
class TestListeDesLots:

    def _lots(self, db):
        return svc_stock.calcul_lots_pepiniere(db, CTX)

    def test_us209_liste_tous_les_lots_epuises_marques(self, db):
        actif = _semis(db, "chou", "frisé")
        solde = _semis(db, "tomate", None)
        solde.quantite = 20
        db.commit()
        _godet(db, solde, plants=20, graines=20)
        db.add(Evenement(type_action="perte_godet", culture="tomate", quantite=20,
                         date=datetime(2026, 5, 1), potager_id=1))
        db.commit()
        texte = lots.formater_liste_lots_telegram(self._lots(db))
        assert "n° 1* chou frisé" in texte and "n° 2* tomate" in texte
        ligne_tomate = next(l for l in texte.splitlines() if "tomate" in l)
        ligne_chou = next(l for l in texte.splitlines() if "chou" in l)
        assert ligne_tomate.startswith("⚪") and "épuisé" in ligne_tomate
        assert ligne_chou.startswith("🟢") and "épuisé" not in ligne_chou

    def test_us209_liste_filtre_par_culture_pluriel_accepte(self, db):
        _semis(db, "chou", "frisé")
        _semis(db, "tomate", None)
        texte = lots.formater_liste_lots_telegram(self._lots(db), "tomates")
        assert "tomate" in texte and "chou" not in texte
        assert lots.formater_liste_lots_telegram(self._lots(db), "poireau") == "Aucun lot de poireau dans ce potager."

    def test_us209_liste_limitee_aux_15_plus_recents(self, db):
        for i in range(18):
            db.add(Evenement(type_action="semis", culture="chou", quantite=10, unite="graines",
                             parcelle_id=2, date=datetime(2026, 3, 1 + i), potager_id=1))
        db.commit()
        texte = lots.formater_liste_lots_telegram(self._lots(db))
        assert "15 sur 18" in texte and "n° 18*" in texte and "n° 4*" in texte
        assert "n° 3*" not in texte and "3 plus anciens" in texte

    def test_us209_liste_ignore_les_godets_sans_semis_et_l_autre_potager(self, db):
        _godet_orphelin = Evenement(type_action="mise_en_godet", culture="poireau", nb_plants_godets=5,
                                    nb_graines_semees=5, date=datetime(2026, 4, 1), potager_id=1)
        db.add(_godet_orphelin)
        db.commit()
        assert lots.formater_liste_lots_telegram(self._lots(db)) == "Aucun lot de pépinière dans ce potager."

    @pytest.mark.parametrize("phrase,attendu", [
        ("mes lots", "/lot"),
        ("liste des lots", "/lot"),
        ("quels sont mes lots", "/lot"),
        ("lots de tomate", "/lot tomate"),
        ("montre-moi mes lots de chou", "/lot chou"),
    ])
    def test_us209_liste_phrase_est_une_commande_sans_modele(self, phrase, attendu):
        from app.services.interpreteur_commandes import interpreter
        res = interpreter(phrase, CTX, autoriser_modele=False)
        assert res is not None and res.commande_equivalente() == attendu

    def test_us209_liste_une_quantite_n_est_pas_une_commande(self):
        from app.services.interpreteur_commandes import interpreter
        res = interpreter("12 lots de godets", CTX, autoriser_modele=False)
        assert res is None or res.commande != "lot"

    @pytest.mark.asyncio
    async def test_us209_cmd_lot_sans_numero_liste_et_filtre(self, db):
        from app.bot.godets import cmd_lot
        _semis(db, "chou", "frisé")
        _semis(db, "tomate", None)
        for args, present, absent in (([], "chou", None), (["tomate"], "tomate", "chou")):
            update, ctx = MagicMock(), MagicMock(args=args)
            update.message.reply_text = AsyncMock()
            with patch("app.bot.godets.SessionLocal", return_value=db),                  patch("app.bot.godets.current_context", return_value=CTX),                  patch.object(db, "close"):
                await cmd_lot(update, ctx)
            envoye = update.message.reply_text.await_args.args[0]
            assert present in envoye and (absent is None or absent not in envoye)
