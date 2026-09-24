"""
tests/test_us231_carte_rotation_parcelle.py — Carte « Rotation » de la fiche
parcelle [US-231]

L'application savait déjà évaluer une rotation (US-163) — mais seulement à
l'instant où l'on plante. Cette US donne le même savoir à lire à froid. Ce qui
se vérifie ici est donc d'abord une **non-divergence** :

- CA1  l'historique et le conseil sortent de `app/services/rotation.py`, et la
       carte dit la MÊME chose que l'avertissement de plantation d'US-163 pour
       la même parcelle et la même famille
- CA2  l'historique se lit sur les événements rattachés à la parcelle, bulletins
       météo automatiques exclus, cultures fantômes exclues des antécédents
- CA3  une lecture UNIQUE servie avec l'onglet Parcelles (`GET /plan`) : aucun
       endpoint de plus, aucune requête quand on change de parcelle
- CA4  les règles de rendu R1 à R9, pour ce qui relève du serveur (colonnes,
       conseil, alerte, pépinière) — le dessin se vérifie côté frontend
- CA5  une famille inconnue est nommée ET exclue du calcul
- CA9  les quatre états : aucun antécédent, une seule année, deux familles la
       même année, répétition sur trois ans

Le rendu (R2, R3, R9, CA6, CA7, CA8, CA10) se vérifie dans
`frontend/src/lib/planParcelles.test.js` et sur `/plan-parcelles`.
"""
from __future__ import annotations

from datetime import datetime, date
from pathlib import Path

import pytest

from app.services import familles as svc_familles
from app.services import rotation as svc_rotation
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, FamilleBotanique, Parcelle

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

RACINE = Path(__file__).resolve().parent.parent
API = RACINE / "app" / "api" / "main.py"
LIB = RACINE / "frontend" / "src" / "lib" / "planParcelles.js"
VUE = RACINE / "frontend" / "src" / "views" / "Plan.jsx"


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    return test_db


def _famille(db, nom, delai_retour_annees=None):
    famille = FamilleBotanique(
        nom=nom,
        nom_normalise=svc_familles.normaliser_famille(nom),
        delai_retour_annees=delai_retour_annees,
    )
    db.add(famille)
    db.commit()
    return famille


def _culture(db, nom, famille=None, potager_id=None):
    cfg = CultureConfig(nom=nom, type_organe_recolte="reproducteur", potager_id=potager_id)
    if famille is not None:
        cfg.famille_rel = famille
    db.add(cfg)
    db.commit()
    return cfg


def _parcelle(db, nom, potager_id=1, pepiniere=False):
    parcelle = Parcelle(
        nom=nom, nom_normalise=nom.lower(), potager_id=potager_id,
        est_pepiniere=pepiniere,
    )
    db.add(parcelle)
    db.commit()
    return parcelle


def _evenement(db, parcelle, culture, annee, potager_id=1,
               type_action="plantation", texte_original=None):
    evt = Evenement(
        date=datetime(annee, 5, 1), type_action=type_action, culture=culture,
        parcelle_id=parcelle.id, potager_id=potager_id, texte_original=texte_original,
    )
    db.add(evt)
    db.commit()
    return evt


def _annees(carte):
    return [colonne["annee"] for colonne in carte["campagnes"]]


def _familles_de(carte, annee):
    colonne = next(c for c in carte["campagnes"] if c["annee"] == annee)
    return [f["famille"] for f in colonne["familles"]]


def _potager_de_reference(db):
    """La planche du Gherkin : des Solanacées en 2025 ET en 2026."""
    solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
    apiacees = _famille(db, "Apiacées", delai_retour_annees=2)
    _culture(db, "tomate", famille=solanacees)
    _culture(db, "poivron", famille=solanacees)
    _culture(db, "carotte", famille=apiacees)
    planche = _parcelle(db, "planche_centrale")
    _evenement(db, planche, "tomate", annee=2025)
    _evenement(db, planche, "poivron", annee=2026)
    return planche


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — un seul calcul, deux restitutions qui ne peuvent pas se contredire
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1UnSeulCalcul:
    def test_la_carte_et_l_avertissement_de_plantation_disent_la_meme_chose(self, db):
        """[CA1] Pour la même parcelle et la même famille, la carte ne conseille
        JAMAIS ce que l'avertissement de plantation (US-163) refuse — et
        inversement. C'est la raison d'être du service partagé."""
        planche = _potager_de_reference(db)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)
        conseillees = {f["famille"] for f in carte["conseil"]["familles"]}

        for culture, famille in (("tomate", "Solanacées"), ("carotte", "Apiacées")):
            evaluation = svc_rotation.evaluer_rotation(
                db, CTX, planche.id, culture, campagne_reference=2027
            )
            conflit = evaluation.statut == svc_rotation.STATUT_CONFLIT
            assert (famille in conseillees) is not conflit, (
                f"{famille} : conseil={famille in conseillees}, "
                f"statut US-163={evaluation.statut}"
            )

    def test_la_carte_conseille_une_famille_des_que_le_delai_est_ecoule(self, db):
        """[CA1, R4] Le conseil applique le MÊME prédicat : écart entre campagnes
        contre délai de retour de la famille, jamais une règle de son cru."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "tomate", annee=2024)

        # 2024 + 3 ans = 2027 : le délai est écoulé, la famille est conseillée.
        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)
        assert [f["famille"] for f in carte["conseil"]["familles"]] == ["Solanacées"]

        # Un an plus tôt, elle ne l'est pas — comme US-163 le refuserait.
        carte_2026 = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2026)
        assert carte_2026["conseil"]["familles"] == []
        assert svc_rotation.evaluer_rotation(
            db, CTX, planche.id, "tomate", campagne_reference=2026
        ).statut == svc_rotation.STATUT_CONFLIT

    def test_une_famille_sans_delai_de_retour_n_est_jamais_conseillee(self, db):
        """[R4, US-163 / CA13] L'inconnu ne se présente pas comme un feu vert."""
        sans_delai = _famille(db, "Astéracées", delai_retour_annees=None)
        _culture(db, "laitue", famille=sans_delai)
        planche = _parcelle(db, "NORD")

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert carte["conseil"]["familles"] == []
        assert "délai de retour" in carte["conseil"]["mention"]


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — ce qui fait antécédent, et ce qui n'en fait pas
# ═════════════════════════════════════════════════════════════════════════════

class TestCA2HistoriqueLu:
    def test_les_bulletins_meteo_automatiques_sont_exclus(self, db):
        """[CA2] Un bulletin météo ne porte aucune culture : il n'entre pas dans
        l'historique — exactement comme `evaluer_rotation` le fait déjà."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "tomate", annee=2026,
                   texte_original=svc_rotation.BULLETIN_AUTO_METEO)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert carte["aucun_antecedent"] is True
        assert _familles_de(carte, 2026) == []

    def test_une_culture_d_une_autre_parcelle_n_entre_pas(self, db):
        """[CA2] L'historique est celui de CETTE parcelle."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        nord = _parcelle(db, "NORD")
        sud = _parcelle(db, "SUD")
        _evenement(db, sud, "tomate", annee=2026)

        carte = svc_rotation.historique_parcelle(db, CTX, nord.id, campagne_a_venir=2027)

        assert carte["aucun_antecedent"] is True

    def test_tous_les_gestes_rattaches_comptent_comme_un_passage(self, db):
        """[CA2] Plantation comme semis en pleine terre : c'est le rattachement à
        la parcelle qui atteste du passage, pas le verbe employé."""
        apiacees = _famille(db, "Apiacées", delai_retour_annees=2)
        _culture(db, "carotte", famille=apiacees)
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "carotte", annee=2026, type_action="semis")

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert _familles_de(carte, 2026) == ["Apiacées"]


# ═════════════════════════════════════════════════════════════════════════════
# CA4 / R1, R4, R5, R6, R8 — ce que la carte porte
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4ReglesDeRendu:
    def test_quatre_colonnes_trois_campagnes_puis_l_annee_a_venir(self, db):
        """[R1] Trois campagnes derrière, la campagne à venir devant."""
        planche = _potager_de_reference(db)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert _annees(carte) == [2024, 2025, 2026]
        assert carte["conseil"]["annee"] == 2027
        assert carte["campagne_a_venir"] == 2027

    def test_la_campagne_a_venir_suit_l_annee_en_cours(self, db):
        """[R1] Sans surcharge, la campagne à venir est l'année suivante."""
        assert svc_rotation.campagne_a_venir_par_defaut(date(2026, 9, 24)) == 2027
        assert svc_rotation.campagne_a_venir_par_defaut(date(2026, 1, 2)) == 2027

    def test_alerte_de_repetition_nommee_comptee_et_datee(self, db):
        """[R5, Gherkin] « Solanacées deux années de suite sur cette parcelle.
        À éviter en 2027. » — la famille, le nombre d'années, l'année à éviter."""
        planche = _potager_de_reference(db)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert len(carte["alertes"]) == 1
        alerte = carte["alertes"][0]
        assert alerte["famille"] == "Solanacées"
        assert alerte["annees"] == 2
        assert alerte["annee_a_eviter"] == 2027
        assert alerte["message"] == (
            "Solanacées deux années de suite sur cette parcelle. À éviter en 2027."
        )

    def test_une_seule_alerte_par_famille_en_cause(self, db):
        """[R5] Deux cultures de la même famille la même année ne font pas deux
        alertes : c'est la FAMILLE qui se répète."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        _culture(db, "poivron", famille=solanacees)
        planche = _parcelle(db, "NORD")
        for annee in (2025, 2026):
            _evenement(db, planche, "tomate", annee=annee)
            _evenement(db, planche, "poivron", annee=annee)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert [a["famille"] for a in carte["alertes"]] == ["Solanacées"]

    def test_aucune_alerte_quand_la_repetition_est_interrompue(self, db):
        """[R5] Une répétition ancienne et interrompue n'est plus une répétition
        en cours — le conseil, lui, continue de la voir."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "tomate", annee=2023)
        _evenement(db, planche, "tomate", annee=2024)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert carte["alertes"] == []

    def test_pepiniere_aucune_carte(self, db):
        """[R8] Une rotation n'a pas de sens sur un emplacement de godets."""
        serre = _parcelle(db, "SERRE", pepiniere=True)
        planche = _parcelle(db, "NORD")

        cartes = svc_rotation.historique_du_plan(db, CTX, [serre, planche], campagne_a_venir=2027)

        assert serre.id not in cartes
        assert planche.id in cartes


# ═════════════════════════════════════════════════════════════════════════════
# CA5 / R7 — une famille inconnue se dit, et s'exclut
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5FamilleInconnue:
    def test_nommee_dans_sa_colonne_et_exclue_du_calcul(self, db):
        """[CA5, R7, Gherkin] La vignette dit « Famille non renseignée », et
        cette culture n'entre ni dans l'alerte ni dans le conseil : l'absence ne
        produit jamais un faux « tout va bien »."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        _culture(db, "topinambour")  # aucune famille renseignée
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "topinambour", annee=2025)
        _evenement(db, planche, "topinambour", annee=2026)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert _familles_de(carte, 2026) == [svc_rotation.MENTION_FAMILLE_INCONNUE]
        assert carte["cultures_sans_famille"] == ["topinambour"]
        assert "topinambour" in carte["mention_familles_inconnues"]
        # Deux années de suite, et pourtant aucune alerte : on ne sait pas de
        # quelle famille il s'agit, donc on n'affirme rien.
        assert carte["alertes"] == []
        assert [f["famille"] for f in carte["conseil"]["familles"]] == ["Solanacées"]

    def test_une_culture_fantome_est_dite_sans_famille(self, db):
        """[R7] Une culture absente du référentiel (ex. « radi », née d'un échec
        de parsing) n'est pas devinée : elle est nommée sans famille."""
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "radi", annee=2026)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert _familles_de(carte, 2026) == [svc_rotation.MENTION_FAMILLE_INCONNUE]
        assert carte["aucun_antecedent"] is True


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — les quatre états de la carte
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9QuatreEtats:
    def test_parcelle_sans_antecedent(self, db):
        """[R6] La carte le dit en une phrase, et garde sa colonne de conseil."""
        apiacees = _famille(db, "Apiacées", delai_retour_annees=2)
        _culture(db, "carotte", famille=apiacees)
        planche = _parcelle(db, "NORD")

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert carte["aucun_antecedent"] is True
        assert carte["mention_aucun_antecedent"] == (
            "Aucune culture enregistrée sur cette parcelle avant 2026."
        )
        assert all(colonne["familles"] == [] for colonne in carte["campagnes"])
        assert [f["famille"] for f in carte["conseil"]["familles"]] == ["Apiacées"]

    def test_parcelle_avec_une_seule_annee(self, db):
        """[R6] Les années sans donnée restent des colonnes vides — elles ne se
        sautent pas, et l'année renseignée ne remonte pas à leur place."""
        apiacees = _famille(db, "Apiacées", delai_retour_annees=2)
        _culture(db, "carotte", famille=apiacees)
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "carotte", annee=2025)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert _annees(carte) == [2024, 2025, 2026]
        assert _familles_de(carte, 2024) == []
        assert _familles_de(carte, 2025) == ["Apiacées"]
        assert _familles_de(carte, 2026) == []
        assert carte["aucun_antecedent"] is False

    def test_deux_familles_la_meme_annee(self, db):
        """[R2] Plusieurs familles la même année = plusieurs vignettes, chacune
        portant SES cultures."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        apiacees = _famille(db, "Apiacées", delai_retour_annees=2)
        _culture(db, "tomate", famille=solanacees)
        _culture(db, "carotte", famille=apiacees)
        planche = _parcelle(db, "NORD")
        _evenement(db, planche, "tomate", annee=2026)
        _evenement(db, planche, "carotte", annee=2026)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)
        colonne = next(c for c in carte["campagnes"] if c["annee"] == 2026)

        assert [f["famille"] for f in colonne["familles"]] == ["Apiacées", "Solanacées"]
        assert [f["cultures"] for f in colonne["familles"]] == [["carotte"], ["tomate"]]

    def test_repetition_sur_trois_ans(self, db):
        """[R5] Trois campagnes de suite : l'alerte compte trois années."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        planche = _parcelle(db, "NORD")
        for annee in (2024, 2025, 2026):
            _evenement(db, planche, "tomate", annee=annee)

        carte = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert carte["alertes"][0]["annees"] == 3
        assert "trois années de suite" in carte["alertes"][0]["message"]
        assert carte["conseil"]["familles"] == []


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — une lecture unique, servie avec l'onglet Parcelles
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3LectureUnique:
    def test_une_seule_lecture_pour_toutes_les_parcelles(self, db):
        """[CA3, RT6] `historique_du_plan` sert TOUTES les parcelles d'un coup :
        changer de parcelle dans l'onglet ne déclenche aucune requête de plus."""
        solanacees = _famille(db, "Solanacées", delai_retour_annees=3)
        _culture(db, "tomate", famille=solanacees)
        nord = _parcelle(db, "NORD")
        sud = _parcelle(db, "SUD")
        _evenement(db, nord, "tomate", annee=2026)

        cartes = svc_rotation.historique_du_plan(db, CTX, [nord, sud], campagne_a_venir=2027)

        assert set(cartes) == {nord.id, sud.id}
        assert _familles_de(cartes[nord.id], 2026) == ["Solanacées"]
        assert cartes[sud.id]["aucun_antecedent"] is True

    def test_le_plan_et_la_parcelle_rendent_la_meme_carte(self, db):
        """[CA3] La lecture groupée n'est pas un second calcul : elle rend
        exactement ce que la lecture d'une parcelle rendrait."""
        planche = _potager_de_reference(db)

        groupee = svc_rotation.historique_du_plan(
            db, CTX, [planche], campagne_a_venir=2027
        )[planche.id]
        seule = svc_rotation.historique_parcelle(db, CTX, planche.id, campagne_a_venir=2027)

        assert groupee == seule

    def test_aucun_endpoint_dedie_la_rotation_voyage_avec_get_plan(self, db):
        """[CA3] Aucun appel de plus n'est ajouté à l'onglet Parcelles : le bloc
        `rotation` part avec `GET /plan`."""
        source = API.read_text(encoding="utf-8")

        assert "svc_rotation.historique_du_plan(db, use_ctx, parcelles)" in source
        assert '"rotation": rotations.get(p.id),' in source
        assert "/parcelles/{parcelle_id}/rotation" not in source


# ═════════════════════════════════════════════════════════════════════════════
# CA1 (frontend) — rien ne se recalcule dans l'écran
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1AucunCalculFrontend:
    def test_le_frontend_ne_recalcule_ni_alerte_ni_conseil(self):
        """[CA1] Le module de rendu lit `alertes`, `conseil` et les mentions tels
        que le serveur les formule — il ne les reconstruit pas."""
        lib = LIB.read_text(encoding="utf-8")

        assert "rotation.alertes" in lib
        assert "rotation.mention_aucun_antecedent" in lib
        # Aucun délai de retour comparé côté écran : le prédicat vit au serveur.
        assert "delai_retour_annees <" not in lib
        assert "années de suite" not in lib

    def test_la_carte_est_rendue_apres_les_caracteristiques(self):
        """[Amendement du 24/09/2026] « Rotation » se place juste après
        « Caractéristiques », dans la colonne qu'elle partage avec « Sol et
        entretien » — et n'est pas rendue pour une pépinière (R8)."""
        vue = VUE.read_text(encoding="utf-8")

        assert "<CarteRotation" in vue
        assert vue.index("<CarteCaracteristiques") < vue.index("<CarteRotation")
        assert vue.index("<CarteRotation") < vue.index("<CarteSol")
        assert "{rotation && <CarteRotation" in vue
