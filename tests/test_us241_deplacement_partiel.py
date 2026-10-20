"""
tests/test_us241_deplacement_partiel.py — Déplacer une partie des godets d'un lot [US-241]
==========================================================================================

- CA1  quantité facultative : sans elle, lot entier (US-211 inchangé) ; tous les godets = entier
- CA2  dicté sans modèle, à côté des formes d'US-211, de la plantation et de la mise en godet chiffrées
- CA3  origine dite, unique, ou demandée par boutons (lot réparti)
- CA4  quantité supérieure à l'origine, nulle, négative : refus, rien d'enregistré
- CA5  les graines ne se déplacent pas en nombre
- CA6  récapitulatif « 6 godets du lot 21 · serre → châssis froid » ; correction, suppression
- CA7  répartition par pépinière, dans l'ordre des dates, à la date de référence
- CA8  endurcissement par emplacement
- CA9  sortie d'un lot réparti : origine demandée, ou portée ; repli « à vérifier » (A41 en suspens)
- CA10 aucun stock ne change
- CA11 le cycle de vie porte quantité, origine, destination
- CA12 dépôt sans destination : le compagnon propose les pépinières, hors l'origine
- CA13 lot sans emplacement : « emplacement non renseigné »
- CA14 ouvert à la PWA, phrase à dicter lue par le parseur
- CA15 /help

Aucun appel réseau, aucun appel au modèle.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest

from app.bot.enregistrement import _build_action_summary, _build_recap_tts
from app.services import echeances_lots as ech
from app.services import evenements as svc_evenements
from app.services import file_gestes
from app.services import lots_pepiniere as lots
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, Parcelle, Potager, User
from llm.parseur_deterministe import parser_saisie
from tests.test_us211_deplacer_lot import _totaux
from utils.stock import calcul_lots_pepiniere

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
SERRE, CHASSIS, PLANCHE = 2, 3, 1
RACINE = Path(__file__).resolve().parent.parent


@pytest.fixture
def db(test_db):
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1))
    test_db.add(CultureConfig(nom="poivron", type_organe_recolte="reproducteur"))
    test_db.add(CultureConfig(nom="tomate", type_organe_recolte="reproducteur"))
    test_db.add_all([
        Parcelle(id=PLANCHE, nom="Planche sud", nom_normalise="planchesud", potager_id=1),
        Parcelle(id=SERRE, nom="Serre chaude", nom_normalise="serrechaude", potager_id=1,
                 est_pepiniere=True, type_pepiniere="chaude"),
        Parcelle(id=CHASSIS, nom="Châssis froid", nom_normalise="chassisfroid", potager_id=1,
                 est_pepiniere=True, type_pepiniere="froide"),
    ])
    test_db.commit()
    return test_db


def _semis(db, culture="poivron", numero=21, godets=16, parcelle_id=SERRE, graines=None, potager_id=1):
    """Lot `numero` : semé le 1er mars, `godets` repiqués le 10 mars (non localisés)."""
    e = Evenement(type_action="semis", culture=culture, quantite=graines if graines is not None else godets,
                  unite="graines", parcelle_id=parcelle_id, date=datetime(2026, 3, 1),
                  potager_id=potager_id, numero_lot=numero)
    db.add(e)
    db.commit()
    if godets:
        db.add(Evenement(type_action="mise_en_godet", culture=culture, nb_plants_godets=godets,
                         nb_graines_semees=godets, origine_graines_id=e.id,
                         date=datetime(2026, 3, 10), potager_id=potager_id))
        db.commit()
    return e


def _deplacer(db, semis, destination="Châssis froid", date_iso="2026-04-20", ctx=CTX, **champs):
    """Enregistre un déplacement par le chemin de confirmation du bot."""
    parsed = {"action": "deplacement", "parcelle": destination, "date": date_iso,
              "origine_graines_id": semis.id, **champs}
    parcelle = db.query(Parcelle).filter(Parcelle.nom == destination, Parcelle.potager_id == ctx.potager_id).first()
    return svc_evenements.creer_evenement_confirme(db, ctx, parsed, "passé au châssis", parcelle)


def _lot(db, semis, **kw):
    return next(l for l in calcul_lots_pepiniere(db, potager_id=semis.potager_id, **kw) if l["semis_id"] == semis.id)


def _rep(db, semis, **kw):
    return [(r["nom"], r["godets"]) for r in _lot(db, semis, **kw)["repartition_godets"]]


def _nb_deplacements(db):
    return db.query(Evenement).filter(Evenement.type_action == "deplacement").count()


# ── CA1 — quantité facultative ──────────────────────────────────────────────

def test_us241_ca1_sans_quantite_le_lot_entier_comme_avant(db):
    s = _semis(db, graines=30)
    ev = _deplacer(db, s)
    lot = _lot(db, s)
    assert ev.quantite is None and ev.parcelle_origine_id is None
    assert _rep(db, s) == [("Châssis froid", 16)]
    assert lot["graines_emplacement"] == "Châssis froid"   # les graines suivent le lot entier
    assert lot["reparti"] is False and lot["emplacement"]["nom"] == "Châssis froid"


def test_us241_ca1_partiel_coupe_le_lot(db):
    s = _semis(db)
    ev = _deplacer(db, s, quantite=6)
    assert (ev.quantite, ev.unite, ev.parcelle_origine_id, ev.parcelle_id) == (6, "godets", SERRE, CHASSIS)
    lot = _lot(db, s)
    assert _rep(db, s) == [("Serre chaude", 10), ("Châssis froid", 6)]
    assert lot["reparti"] is True and lot["repartition_a_verifier"] is False
    assert lot["stock_residuel_godet"] == 16


def test_us241_ca1_quantite_egale_au_disponible_est_un_deplacement_entier(db):
    s = _semis(db, graines=30)
    ev = _deplacer(db, s, quantite=16)
    assert ev.quantite is None
    lot = _lot(db, s)
    assert _rep(db, s) == [("Châssis froid", 16)] and lot["graines_emplacement"] == "Châssis froid"


# ── CA2 — dictée sans modèle ────────────────────────────────────────────────

class TestDictee:
    def _parse(self, db, phrase):
        return parser_saisie(phrase, CTX, db=db, aujourd_hui=date(2026, 4, 20))

    @pytest.mark.parametrize("phrase, quantite, numero, origine", [
        ("passé 6 godets du lot 21 au châssis froid", 6, 21, None),
        ("sorti 6 poivrons de la serre chaude au châssis froid", 6, None, "Serre chaude"),
        ("déplacé 10 godets de poivron sous le châssis froid", 10, None, None),
        ("passé le lot 21 au châssis froid", None, 21, None),          # US-211, sans quantité
        ("déplacé les godets de poivron sous le châssis froid", None, None, None),
    ])
    def test_us241_ca2_formes_reconnues(self, db, phrase, quantite, numero, origine):
        _semis(db)
        res = self._parse(db, phrase)
        assert res.reconnu, (phrase, res.raison)
        item = res.items[0]
        assert item["action"] == "deplacement" and item["parcelle"] == "Châssis froid"
        assert item["quantite"] == quantite
        assert item.get("numero_lot_cite") == numero
        assert item.get("parcelle_origine") == origine

    @pytest.mark.parametrize("phrase, action", [
        ("planté 6 poivrons du lot 21 dans la planche sud", "plantation"),
        ("repiqué 6 poivrons du lot 21 en godet", "mise_en_godet"),
        ("mise en godet 6 poivrons sous le châssis froid", "mise_en_godet"),
    ])
    def test_us241_ca2_pas_de_confusion_avec_les_gestes_chiffres(self, db, phrase, action):
        _semis(db)
        res = self._parse(db, phrase)
        assert res.reconnu, (phrase, res.raison)
        assert res.items[0]["action"] == action

    def test_us241_ca2_un_verbe_familier_sans_destination_reste_ambigu(self, db):
        _semis(db)
        assert not self._parse(db, "sorti 6 poivrons de la serre chaude").reconnu

    def test_us241_ca12_deplacement_explicite_du_lot_sans_destination(self, db):
        _semis(db)
        res = self._parse(db, "déplacement de 6 godets du lot 21")
        assert res.reconnu, res.raison
        item = res.items[0]
        assert (item["action"], item["quantite"], item["parcelle"], item["numero_lot_cite"]) == (
            "deplacement", 6, None, 21)


# ── CA3 — l'origine ─────────────────────────────────────────────────────────

def test_us241_ca3_origine_ambigue_sur_un_lot_reparti(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    parsed = {"action": "deplacement", "parcelle": "Serre chaude", "origine_graines_id": s.id, "quantite": 2}
    with pytest.raises(svc_evenements.OrigineAmbigueError) as e:
        svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    assert [(o["nom"], o["godets"]) for o in e.value.origines] == [("Serre chaude", 10), ("Châssis froid", 6)]


def test_us241_ca3_origine_dite_par_son_nom(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    ev = _deplacer(db, s, destination="Serre chaude", date_iso="2026-04-22", quantite=2,
                   parcelle_origine="Châssis froid")
    assert ev.parcelle_origine_id == CHASSIS
    assert _rep(db, s) == [("Serre chaude", 12), ("Châssis froid", 4)]


def test_us241_ca3_origine_ou_le_lot_n_a_rien_est_refusee(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="aucun godet à cet endroit"):
        _deplacer(db, s, destination="Serre chaude", quantite=2, parcelle_origine="Châssis froid")
    assert _nb_deplacements(db) == 0


# ── CA4, CA5 — refus ────────────────────────────────────────────────────────

def test_us241_ca4_quantite_excessive_dit_le_disponible(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="n'a que 10 godets en « Serre chaude »"):
        _deplacer(db, s, date_iso="2026-04-22", quantite=12, parcelle_origine_id=SERRE)
    assert _nb_deplacements(db) == 1


@pytest.mark.parametrize("quantite", [0, -3, 2.5])
def test_us241_ca4_quantite_nulle_negative_ou_fractionnaire(db, quantite):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError):
        _deplacer(db, s, quantite=quantite)
    assert _nb_deplacements(db) == 0


def test_us241_ca5_les_graines_ne_se_deplacent_pas_en_nombre(db):
    s = _semis(db, godets=0, graines=40)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="aucun godet"):
        _deplacer(db, s, quantite=10)
    assert _nb_deplacements(db) == 0


def test_us241_ca5_un_deplacement_partiel_laisse_les_graines(db):
    s = _semis(db, graines=30)   # 16 repiqués, 14 graines en barquette
    _deplacer(db, s, quantite=6)
    assert _lot(db, s)["graines_emplacement"] == "Serre chaude"


# ── CA6 — récapitulatif, Journal ────────────────────────────────────────────

def test_us241_ca6_le_recapitulatif_dit_quantite_origine_destination(db):
    s = _semis(db)
    parsed = {"action": "deplacement", "parcelle": "Châssis froid", "origine_graines_id": s.id,
              "quantite": 6, "date": "2026-04-20"}
    svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    resume = _build_action_summary([parsed])
    assert "6 godets du lot 21 (poivron) · serre chaude → châssis froid" in resume
    assert _build_recap_tts(parsed).startswith("Déplacement de 6 godets du lot 21")


def test_us241_ca6_correction_de_la_quantite_recalcule(db):
    s = _semis(db)
    ev = _deplacer(db, s, quantite=6)
    svc_evenements.corriger_evenement(db, CTX, ev.id, {"quantite": 8}, " | c")
    assert _rep(db, s) == [("Serre chaude", 8), ("Châssis froid", 8)]


def test_us241_ca6_suppression_rend_le_lot_d_un_seul_tenant(db):
    s = _semis(db)
    ev = _deplacer(db, s, quantite=6)
    assert svc_evenements.supprimer_evenement(db, CTX, ev.id) is True
    lot = _lot(db, s)
    assert _rep(db, s) == [("Serre chaude", 16)] and lot["reparti"] is False


def test_us241_ca6_une_quantite_corrigee_nulle_est_refusee(db):
    s = _semis(db)
    ev = _deplacer(db, s, quantite=6)
    with pytest.raises(svc_evenements.DeplacementRefuseError):
        svc_evenements.corriger_evenement(db, CTX, ev.id, {"quantite": 0}, " | c")


# ── CA7 — répartition dans l'ordre des dates ────────────────────────────────

def test_us241_ca7_retour_d_une_partie_le_lot_redevient_d_un_seul_tenant(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    _deplacer(db, s, destination="Serre chaude", date_iso="2026-04-25", quantite=6, parcelle_origine_id=CHASSIS)
    lot = _lot(db, s)
    assert _rep(db, s) == [("Serre chaude", 16)] and lot["reparti"] is False


def test_us241_ca7_date_de_reference_anterieure(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    assert _rep(db, s, date_ref=date(2026, 4, 19)) == [("Serre chaude", 16)]
    assert _rep(db, s, date_ref=date(2026, 4, 20)) == [("Serre chaude", 10), ("Châssis froid", 6)]


def test_us241_ca7_deplacement_entier_d_un_lot_reparti_regroupe_tout(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    _deplacer(db, s, date_iso="2026-04-25")   # entier, vers le châssis où est déjà une partie
    assert _rep(db, s) == [("Châssis froid", 16)]


def test_us241_ca7_le_parcours_rend_une_etiquette_par_pepiniere(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    lots_ = calcul_lots_pepiniere(db, date(2026, 4, 22), potager_id=1)
    parcours = ech.lire_echeances(db, CTX, lots_, date(2026, 4, 22))["parcours"]
    siennes = sorted(
        (e for e in parcours["etiquettes"] if e["lot"]["id"] == f"semis-{s.id}"),
        key=lambda e: e["fragment"]["rang"],
    )
    assert [(e["emplacement_id"], e["quantites"]["godets"]) for e in siennes] == [(SERRE, 10), (CHASSIS, 6)]
    assert [e["fragment"] for e in siennes] == [{"rang": 1, "total": 2}, {"rang": 2, "total": 2}]


def test_us241_ca7_mise_en_godet_apres_la_coupe(db):
    """Après la coupe, un repiquage non localisé rejoint les graines (serre) ; un repiquage
    localisé va où il le dit."""
    s = _semis(db, graines=40)   # 16 repiqués, 24 graines en barquette à la serre
    _deplacer(db, s, quantite=6)
    db.add_all([
        Evenement(type_action="mise_en_godet", culture="poivron", nb_plants_godets=4, nb_graines_semees=4,
                  origine_graines_id=s.id, date=datetime(2026, 4, 22), potager_id=1),
        Evenement(type_action="mise_en_godet", culture="poivron", nb_plants_godets=3, nb_graines_semees=3,
                  origine_graines_id=s.id, parcelle_id=CHASSIS, date=datetime(2026, 4, 23), potager_id=1),
    ])
    db.commit()
    assert _rep(db, s) == [("Serre chaude", 14), ("Châssis froid", 9)]


def test_us241_ca7_destination_identique_a_l_origine_refusee(db):
    s = _lot_reparti(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="déjà dans « Châssis froid »"):
        _deplacer(db, s, date_iso="2026-04-22", quantite=2, parcelle_origine_id=CHASSIS)


def test_us241_ca3_origine_inconnue_du_potager_refusee(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="n'existe pas"):
        _deplacer(db, s, quantite=2, parcelle_origine="Véranda")


# ── CA8 — endurcissement par emplacement ────────────────────────────────────

def test_us241_ca8_la_partie_sortie_au_froid_s_endurcit_depuis_son_deplacement(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6, date_iso="2026-04-20")
    lots_ = calcul_lots_pepiniere(db, date(2026, 4, 23), potager_id=1)
    parcours = ech.lire_echeances(db, CTX, lots_, date(2026, 4, 23))["parcours"]
    par_lieu = {e["emplacement_id"]: e for e in parcours["etiquettes"] if e["lot"]["id"] == f"semis-{s.id}"}
    froid = par_lieu[CHASSIS]
    assert froid["stade"] == "endurcissement"
    assert froid["echeance"]["endurcissement"] == {"jour": 3, "sur": 7}
    assert froid["echeance"]["debut_regle"] == "2026-04-20"
    assert froid["mention"] == "déplacés le 20 avr."
    assert par_lieu[SERRE]["stade"] == "godet"   # restée au chaud : pas d'endurcissement commencé
    assert par_lieu[SERRE]["mention"] is None


# ── CA9 — sorties d'un lot réparti ──────────────────────────────────────────

def _lot_reparti(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    return s


@pytest.mark.parametrize("action", ["plantation", "perte_godet", "vendu"])
def test_us241_ca9_sortie_sans_origine_la_demande(db, action):
    s = _lot_reparti(db)
    parsed = {"action": action, "culture": "poivron", "quantite": 4, "_lot_numero": 21}
    with pytest.raises(svc_evenements.OrigineAmbigueError) as e:
        svc_evenements.controler_origine_sortie(db, CTX, parsed)
    assert [(o["nom"], o["godets"]) for o in e.value.origines] == [("Serre chaude", 10), ("Châssis froid", 6)]


def test_us241_ca9_perte_qui_cite_son_semis_demande_l_origine(db):
    s = _lot_reparti(db)
    parsed = {"action": "perte_godet", "culture": "poivron", "quantite": 2, "origine_graines_id": s.id}
    with pytest.raises(svc_evenements.OrigineAmbigueError):
        svc_evenements.controler_origine_sortie(db, CTX, parsed)


def test_us241_ca9_plantation_par_culture_au_seul_lot_demande_l_origine(db):
    _lot_reparti(db)
    parsed = {"action": "plantation", "culture": "poivron", "quantite": 2}
    with pytest.raises(svc_evenements.OrigineAmbigueError):
        svc_evenements.controler_origine_sortie(db, CTX, parsed)


def test_us241_ca9_les_autres_gestes_ne_sont_pas_concernes(db):
    _lot_reparti(db)
    assert svc_evenements.controler_origine_sortie(db, CTX, {"action": "arrosage", "culture": "poivron"}) is None


def test_us241_ca9_sortie_avec_origine_portee_ne_demande_rien(db):
    s = _lot_reparti(db)
    parsed = {"action": "plantation", "culture": "poivron", "quantite": 4, "_lot_numero": 21,
              "parcelle_origine_id": CHASSIS}
    assert svc_evenements.controler_origine_sortie(db, CTX, parsed) is None


def test_us241_ca9_lot_d_un_seul_tenant_ne_demande_rien(db):
    _semis(db)
    parsed = {"action": "plantation", "culture": "poivron", "quantite": 4, "_lot_numero": 21}
    assert svc_evenements.controler_origine_sortie(db, CTX, parsed) is None


def test_us241_ca9_la_sortie_retire_a_son_origine(db):
    s = _lot_reparti(db)
    db.add(Evenement(type_action="perte_godet", culture="poivron", quantite=4, unite="plants",
                     origine_graines_id=s.id, parcelle_origine_id=CHASSIS,
                     date=datetime(2026, 4, 22), potager_id=1))
    db.commit()
    lot = _lot(db, s)
    assert _rep(db, s) == [("Serre chaude", 10), ("Châssis froid", 2)]
    assert lot["repartition_a_verifier"] is False and lot["stock_residuel_godet"] == 12


def test_us241_ca9_repli_sans_origine_emplacement_courant_puis_a_verifier(db):
    """A41 en suspens : une sortie sans origine (historique, correction) est retirée d'abord
    de l'emplacement courant (le châssis, dernière destination), et le lot est marqué."""
    s = _lot_reparti(db)
    db.add(Evenement(type_action="perte_godet", culture="poivron", quantite=8, unite="plants",
                     origine_graines_id=s.id, date=datetime(2026, 4, 22), potager_id=1))
    db.commit()
    lot = _lot(db, s)
    assert _rep(db, s) == [("Serre chaude", 8)]
    assert lot["stock_residuel_godet"] == 8
    lot_avant_fin = _lot(db, s, date_ref=date(2026, 4, 21))
    assert lot_avant_fin["repartition_a_verifier"] is False


def test_us241_ca9_repli_marque_a_verifier_quand_le_lot_reste_reparti(db):
    s = _lot_reparti(db)
    db.add(Evenement(type_action="vendu", culture="poivron", quantite=2, unite="plants",
                     origine_graines_id=s.id, date=datetime(2026, 4, 22), potager_id=1))
    db.commit()
    lot = _lot(db, s)
    assert _rep(db, s) == [("Serre chaude", 10), ("Châssis froid", 4)]
    assert lot["repartition_a_verifier"] is True


def test_us241_ca9_plantation_avec_origine_ecrite(db):
    s = _lot_reparti(db)
    parsed = {"action": "plantation", "culture": "poivron", "quantite": 6, "unite": "plants",
              "parcelle": "Planche sud", "date": "2026-04-23", "numero_lot_cite": 21,
              "parcelle_origine_id": CHASSIS}
    lots.resoudre_references(db, CTX, [parsed])
    planche = db.get(Parcelle, PLANCHE)
    ev = svc_evenements.creer_evenement_confirme(db, CTX, parsed, "planté 6 poivrons", planche)
    assert ev.parcelle_origine_id == CHASSIS
    assert _rep(db, s) == [("Serre chaude", 10)]


# ── CA10 — aucun stock ne change ────────────────────────────────────────────

def test_us241_ca10_stocks_inchanges(db):
    s = _semis(db)
    avant = _totaux(db)
    _deplacer(db, s, quantite=6)
    _deplacer(db, s, destination="Serre chaude", date_iso="2026-04-22", quantite=2, parcelle_origine_id=CHASSIS)
    assert _totaux(db) == avant


# ── CA11 — cycle de vie ─────────────────────────────────────────────────────

def test_us241_ca11_le_cycle_de_vie_porte_chaque_deplacement_partiel(db):
    s = _semis(db)
    _deplacer(db, s, quantite=6)
    _deplacer(db, s, destination="Serre chaude", date_iso="2026-04-22", quantite=2, parcelle_origine_id=CHASSIS)
    cycle = svc_evenements.cycle_vie_culture(db, CTX, "poivron", None, semis_id=s.id)
    assert [(d["quantite"], d["origine"], d["destination"]) for d in cycle["deplacements"]] == [
        (6, "Serre chaude", "Châssis froid"), (2, "Châssis froid", "Serre chaude"),
    ]


# ── CA12 — sans destination ─────────────────────────────────────────────────

def test_us241_ca12_sans_destination_propose_les_pepinieres_hors_origine(db):
    s = _semis(db)
    parsed = {"action": "deplacement", "origine_graines_id": s.id, "quantite": 6}
    with pytest.raises(svc_evenements.DestinationManquanteError) as e:
        svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    assert [p["nom"] for p in e.value.pepinieres] == ["Châssis froid"]
    assert parsed["_lot_numero"] == 21 and parsed["parcelle_origine_id"] == SERRE


def test_us241_ca12_ailleurs_c_est_un_refus_comme_un_autre(db):
    s = _semis(db)
    with pytest.raises(svc_evenements.DeplacementRefuseError, match="va où"):
        _deplacer(db, s, destination=None)


# ── CA13 — lot sans emplacement ─────────────────────────────────────────────

def test_us241_ca13_lot_sans_emplacement_se_deplace_en_partie(db):
    s = _semis(db, parcelle_id=None)
    parsed = {"action": "deplacement", "parcelle": "Châssis froid", "origine_graines_id": s.id,
              "quantite": 6, "date": "2026-04-20"}
    svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    assert "6 godets du lot 21 (poivron) · emplacement non renseigné → châssis froid" in _build_action_summary([parsed])
    _deplacer(db, s, quantite=6)
    assert _rep(db, s) == [(None, 10), ("Châssis froid", 6)]
    cycle = svc_evenements.cycle_vie_culture(db, CTX, "poivron", None, semis_id=s.id)
    assert cycle["deplacements"][0]["origine"] is None   # « emplacement non renseigné » à l'écran


def test_us241_ca13_lot_sans_emplacement_se_range_entier(db):
    s = _semis(db, parcelle_id=None)
    parsed = {"action": "deplacement", "origine_graines_id": s.id}
    with pytest.raises(svc_evenements.DestinationManquanteError) as e:
        svc_evenements.resoudre_lot_deplacement(db, CTX, parsed)
    assert [p["nom"] for p in e.value.pepinieres] == ["Serre chaude", "Châssis froid"]
    _deplacer(db, s)
    assert _rep(db, s) == [("Châssis froid", 16)]


# ── CA14 — PWA ──────────────────────────────────────────────────────────────

def test_us241_ca14_depot_avec_quantite_sans_destination(db):
    s = _semis(db)
    depot = file_gestes.deposer_geste(db, CTX, action="deplacement", lot_id=s.id, quantite=6,
                                      emplacement_id=SERRE)
    item = file_gestes.item_du_geste(depot.geste)
    assert (item["quantite"], item["unite"], item["numero_lot_cite"], item["parcelle_origine_id"]) == (
        6, "godets", 21, SERRE)
    assert item["origine_graines_id"] == s.id and item.get("parcelle") is None


def test_us241_ca14_emplacement_d_un_autre_potager_refuse(db):
    s = _semis(db)
    db.add(Potager(id=2, nom="Autre", proprietaire_id=1))
    db.add(Parcelle(id=9, nom="Serre voisine", nom_normalise="serrevoisine", potager_id=2, est_pepiniere=True))
    db.commit()
    with pytest.raises(file_gestes.ParcelleHorsPotagerError):
        file_gestes.deposer_geste(db, CTX, action="deplacement", lot_id=s.id, emplacement_id=9)


@pytest.mark.parametrize("item", [
    {"action": "deplacement", "numero_lot_cite": 21, "quantite": 6, "parcelle": "Châssis froid"},
    {"action": "deplacement", "numero_lot_cite": 21, "quantite": 6},
    {"action": "deplacement", "numero_lot_cite": 21},
])
def test_us241_ca14_la_phrase_a_dicter_est_lue_sans_modele(db, item):
    _semis(db)
    phrase = file_gestes.phrase_a_dicter(item)
    res = parser_saisie(phrase, CTX, db=db, aujourd_hui=date(2026, 4, 20))
    assert res.reconnu, (phrase, res.raison)
    lu = res.items[0]
    assert (lu["action"], lu["numero_lot_cite"], lu["quantite"], lu["parcelle"]) == (
        "deplacement", 21, item.get("quantite"), item.get("parcelle"))


# ── CA15 — /help ────────────────────────────────────────────────────────────

def test_us241_ca15_l_aide_montre_le_deplacement_partiel():
    from app.bot.aide import _HELP_GODET
    assert "passé 6 godets du lot 128 au châssis froid" in _HELP_GODET
    assert "passé le lot 128 au châssis froid" in _HELP_GODET


# ── Isolation, migration ────────────────────────────────────────────────────

def test_us241_isolation_entre_potagers(db):
    s1 = _semis(db)
    db.add(Potager(id=2, nom="Autre", proprietaire_id=1))
    db.add_all([
        Parcelle(id=12, nom="Serre chaude", nom_normalise="serrechaude", potager_id=2,
                 est_pepiniere=True, type_pepiniere="chaude"),
        Parcelle(id=13, nom="Châssis froid", nom_normalise="chassisfroid", potager_id=2,
                 est_pepiniere=True, type_pepiniere="froide"),
    ])
    db.commit()
    ctx2 = TenantContext(user_id=1, potager_id=2, role="owner")
    s2 = _semis(db, numero=21, parcelle_id=12, potager_id=2)
    _deplacer(db, s2, ctx=ctx2, quantite=6)
    assert _rep(db, s2) == [("Serre chaude", 10), ("Châssis froid", 6)]
    assert _rep(db, s1) == [("Serre chaude", 16)]
    with pytest.raises(svc_evenements.DestinationManquanteError) as e:
        svc_evenements.resoudre_lot_deplacement(db, CTX, {"action": "deplacement", "origine_graines_id": s1.id})
    assert {p["id"] for p in e.value.pepinieres} == {CHASSIS}


def test_us241_migration_et_rollback():
    migration = (RACINE / "migrations" / "migration_v58.sql").read_text(encoding="utf-8")
    rollback = (RACINE / "migrations" / "rollback_v58.sql").read_text(encoding="utf-8")
    assert "ADD COLUMN IF NOT EXISTS parcelle_origine_id" in migration
    assert "ON DELETE SET NULL" in migration
    assert "DROP COLUMN IF EXISTS parcelle_origine_id" in rollback


# ── Bot : questions par boutons ─────────────────────────────────────────────

class _Reponses:
    def __init__(self):
        self.textes: list[str] = []
        self.claviers: list = []

    async def reply_text(self, texte, **kw):
        self.textes.append(texte)
        self.claviers.append(kw.get("reply_markup"))


class _SessionNonFermee:
    def __init__(self, db):
        self._db = db

    def __getattr__(self, nom):
        return getattr(self._db, nom)

    def close(self):
        pass


def _update_factice():
    from types import SimpleNamespace
    msg = _Reponses()
    return SimpleNamespace(effective_message=msg, effective_user=SimpleNamespace(id=7)), msg


@pytest.fixture
def bot_db(db, monkeypatch):
    from app.bot import godets
    monkeypatch.setattr(godets, "SessionLocal", lambda: _SessionNonFermee(db))
    monkeypatch.setattr(godets, "current_context", lambda: CTX)
    yield db
    from app.bot.etat import _DEPLACEMENT_LOT_PENDING
    _DEPLACEMENT_LOT_PENDING.clear()


def _boutons(msg):
    return [(b.text, b.callback_data) for ligne in msg.claviers[-1].inline_keyboard for b in ligne]


@pytest.mark.asyncio
async def test_us241_bot_origine_demandee_par_boutons(bot_db):
    from app.bot.etat import _DEPLACEMENT_LOT_PENDING
    from app.bot.godets import _preparer_deplacement
    s = _lot_reparti(bot_db)
    update, msg = _update_factice()
    parsed = {"action": "deplacement", "parcelle": "Serre chaude", "origine_graines_id": s.id, "quantite": 2}
    assert await _preparer_deplacement(update, parsed, "passé 2 godets du lot 21 à la serre") is True
    assert ("Serre chaude (10)", f"deplorig:{SERRE}") in _boutons(msg)
    assert ("Châssis froid (6)", f"deplorig:{CHASSIS}") in _boutons(msg)
    assert _DEPLACEMENT_LOT_PENDING[7]["question"] == "origine"


@pytest.mark.asyncio
async def test_us241_bot_destination_demandee_par_boutons(bot_db):
    from app.bot.godets import _preparer_deplacement
    s = _semis(bot_db)
    update, msg = _update_factice()
    parsed = {"action": "deplacement", "origine_graines_id": s.id}
    assert await _preparer_deplacement(update, parsed, "déplacement du lot 21") is True
    assert ("Châssis froid", f"depldest:{CHASSIS}") in _boutons(msg)
    assert all(not c.startswith(f"depldest:{SERRE}") for _, c in _boutons(msg))


@pytest.mark.asyncio
async def test_us241_bot_plantation_d_un_lot_reparti_demande_l_origine(bot_db):
    from app.bot.godets import _preparer_origine_sortie
    _lot_reparti(bot_db)
    update, msg = _update_factice()
    parsed = {"action": "plantation", "culture": "poivron", "quantite": 6, "_lot_numero": 21}
    assert await _preparer_origine_sortie(update, parsed, "planté 6 poivrons du lot 21") is True
    assert "d'où viennent les godets" in msg.textes[0]
    assert [t for t, _ in _boutons(msg)][:2] == ["Serre chaude (10)", "Châssis froid (6)"]


@pytest.mark.asyncio
async def test_us241_bot_le_choix_reprend_le_geste(bot_db, monkeypatch):
    from types import SimpleNamespace
    from app.bot import godets, saisie
    s = _lot_reparti(bot_db)
    update, msg = _update_factice()
    parsed = {"action": "deplacement", "parcelle": "Serre chaude", "origine_graines_id": s.id, "quantite": 2}
    await godets._preparer_deplacement(update, parsed, "passé 2 godets")
    repris = {}

    async def _parse_and_save(update, texte, pre_parsed_items=None, geste_file=None):
        repris["items"] = pre_parsed_items

    monkeypatch.setattr(saisie, "_parse_and_save", _parse_and_save)
    edits = []

    async def _edit(texte, **kw):
        edits.append(texte)

    async def _answer(*a, **kw):
        return None

    query = SimpleNamespace(data=f"deplorig:{CHASSIS}", answer=_answer, edit_message_text=_edit)
    cb_update = SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=7))
    await godets._deplacement_lot_cb(cb_update, None)
    assert repris["items"][0]["parcelle_origine_id"] == CHASSIS
    assert "Châssis froid" in edits[0]


async def _choisir(godets, donnee):
    from types import SimpleNamespace
    edits = []

    async def _edit(texte, **kw):
        edits.append(texte)

    async def _answer(*a, **kw):
        return None

    query = SimpleNamespace(data=donnee, answer=_answer, edit_message_text=_edit)
    await godets._deplacement_lot_cb(SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=7)), None)
    return edits


@pytest.mark.asyncio
async def test_us241_bot_le_choix_de_la_destination_reprend_le_geste(bot_db, monkeypatch):
    from app.bot import godets, saisie
    s = _semis(bot_db)
    update, _ = _update_factice()
    await godets._preparer_deplacement(update, {"action": "deplacement", "origine_graines_id": s.id}, "déplacement")
    repris = {}

    async def _parse_and_save(update, texte, pre_parsed_items=None, geste_file=None):
        repris["items"] = pre_parsed_items

    monkeypatch.setattr(saisie, "_parse_and_save", _parse_and_save)
    edits = await _choisir(godets, f"depldest:{CHASSIS}")
    assert repris["items"][0]["parcelle"] == "Châssis froid" and "Châssis froid" in edits[0]


@pytest.mark.asyncio
async def test_us241_bot_annuler_laisse_le_geste_dans_la_file(bot_db):
    from app.bot import godets
    s = _semis(bot_db)
    update, _ = _update_factice()
    await godets._preparer_deplacement(update, {"action": "deplacement", "origine_graines_id": s.id},
                                       "déplacement", geste_file=object())
    edits = await _choisir(godets, "deplot_cancel")
    assert "reste dans votre file" in edits[0]


@pytest.mark.asyncio
async def test_us241_bot_aucune_autre_pepiniere(bot_db):
    from app.bot import godets
    bot_db.query(Parcelle).filter(Parcelle.id == CHASSIS).delete()
    bot_db.commit()
    s = _semis(bot_db)
    update, msg = _update_factice()
    assert await godets._preparer_deplacement(update, {"action": "deplacement", "origine_graines_id": s.id}, "d") is True
    assert "Aucune autre pépinière" in msg.textes[0]


@pytest.mark.asyncio
async def test_us241_bot_un_clavier_perime_ne_repond_pas_a_une_autre_question(bot_db):
    from types import SimpleNamespace
    from app.bot import godets
    s = _semis(bot_db)
    update, _ = _update_factice()
    await godets._preparer_deplacement(update, {"action": "deplacement", "origine_graines_id": s.id}, "déplacement")
    edits = []

    async def _edit(texte, **kw):
        edits.append(texte)

    async def _answer(*a, **kw):
        return None

    query = SimpleNamespace(data=f"deplorig:{SERRE}", answer=_answer, edit_message_text=_edit)
    await godets._deplacement_lot_cb(SimpleNamespace(callback_query=query, effective_user=SimpleNamespace(id=7)), None)
    assert "n'est plus actif" in edits[0]
