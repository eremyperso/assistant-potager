"""
tests/test_us235_agent_interpreteur.py
[US-235] Comprendre une commande dictée par l'agent interpréteur, négations comprises.

Couverture des critères CA1 → CA15 et du scénario Gherkin. Le modèle est
TOUJOURS simulé : la passerelle renvoie des appels d'outils prédéfinis. Ce qui
est testé, c'est ce que le code fait de ces appels — catalogue, validateur,
adaptateur, récapitulatif, modes, repli, journal. Le comportement du vrai modèle
se mesure à part (`tools/evaluer_interpreteur_agent.py`, CA15).
"""
from __future__ import annotations

import threading
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import sessionmaker
from telegram.ext import CommandHandler

from app import bot as bot_module
from app import config
from app.services import interpreteur_commandes as interp
from app.services import menu_commandes
from app.services.agent import adaptateurs, catalogue_outils, interpreteur_agent, validation
from app.services.agent.catalogue_outils import OUTIL_CONSULTER, OUTIL_MODIFIER_PARCELLE
from app.services.agent.validation import ContexteValidation, valider_appel
from app.services.context import TenantContext
from database.models import Parcelle, RoutageLog
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("Serre extérieure", "Planche Nord", "Planche Sud", "Tunnel")
NEGATION = "Ma serre extérieure n'est plus une pépinière"


def _sans_gras(texte: str) -> str:
    return texte.replace("*", "")


def _texte(texte: str = "Je te propose ceci.") -> ReponseOutils:
    """[US-257] Le tour où le modèle répond en texte : il clôt la boucle (sans jeton compté)."""
    return ReponseOutils(texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT)


def _valider(texte: str, outil: str, arguments: dict, voisin=None, noms=PARCELLES):
    return valider_appel(
        AppelOutil(outil, arguments),
        ContexteValidation(texte=texte, noms_parcelles=noms, voisin=voisin or (lambda n: None)),
    )


def _reponse(*appels: AppelOutil, statut: str = passerelle.STATUT_OK) -> ReponseOutils:
    return ReponseOutils(
        texte="", modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=statut,
    )


@pytest.fixture
def agent_actif(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")


@pytest.fixture
def parcelles_connues(monkeypatch):
    """Les parcelles du potager, sans base : la lecture réelle a ses propres tests."""
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: (lambda nom: None))


@pytest.fixture
def modele():
    """La passerelle simulée : `modele.return_value = _reponse(...)`."""
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture
def session_de_test(test_db, test_engine, monkeypatch):
    """`SessionLocal` des services branché sur la base SQLite de test."""
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr("database.db.SessionLocal", fabrique)
    return test_db


def _parcelle(db, nom: str, **champs) -> Parcelle:
    from utils.parcelles import normalize_parcelle_name

    parcelle = Parcelle(nom=nom, nom_normalise=normalize_parcelle_name(nom), potager_id=1,
                        actif=True, **champs)
    db.add(parcelle)
    db.commit()
    return parcelle


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — un catalogue généré, une quinzaine d'outils au plus
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Catalogue:

    def test_us235_ca1_au_plus_quinze_outils(self):
        # [US-262] Le plafond compte aussi les 2 outils de décision et les 2 de correction, offerts à la demande.
        assert len(catalogue_outils.outils()) <= 15
        assert catalogue_outils.NB_OUTILS_MAX == 17

    def test_us235_ca1_chaque_outil_de_commande_vient_d_une_forme_dictable(self):
        """[CA1] Aucun outil écrit à la main : chacun couvre des formes du catalogue."""
        for outil in catalogue_outils.outils():
            if outil.terminal or outil.lecture or outil.signal:
                # [US-237] L'outil de lecture, comme les terminaux, n'écrit rien ; [US-257] le
                # signal du manque au catalogue non plus.
                assert not outil.formes
                continue
            assert outil.formes
            assert all(f in menu_commandes.FORMES_DICTABLES for f in outil.formes)

    def test_us235_ca1_une_commande_ajoutee_au_bot_ajoute_un_outil(self, monkeypatch):
        """[CA1] Ajouter une forme dictable suffit : l'outil apparaît sans une ligne de plus."""
        nouvelle = menu_commandes.FormeCommande(
            "compost", "retourner", "Retourner le compost",
            (menu_commandes.Argument("tas", menu_commandes.TYPE_NOM_LIBRE, "Quel tas ?"),),
        )
        monkeypatch.setattr(catalogue_outils, "FORMES_DICTABLES",
                            (*menu_commandes.FORMES_DICTABLES, nouvelle))
        noms = {o.nom for o in catalogue_outils.generer_outils()}
        assert "retourner_compost" in noms

    def test_us235_ca1_regroupe_par_commande(self):
        """[CA1] Les sous-commandes d'une même commande partagent un outil (`action`)."""
        culture = catalogue_outils.outils_par_nom()["corriger_culture"]
        proprietes = culture.schema["function"]["parameters"]["properties"]
        assert set(proprietes["action"]["enum"]) == {
            "famille", "delai_retour", "exposition", "eau", "profondeur", "rusticite",
        }

    def test_us235_ca1_un_argument_homonyme_de_type_different_est_suffixe(self):
        """[CA1] `valeur` est une exposition ici, un nombre là : deux propriétés distinctes."""
        proprietes = catalogue_outils.outils_par_nom()["corriger_culture"].schema["function"]["parameters"]["properties"]
        assert proprietes["valeur_profondeur"]["type"] == ["number", "null"]
        assert "enum" in proprietes["valeur_exposition"]
        assert "valeur" not in proprietes

    def test_us235_ca1_les_consultations_tiennent_dans_un_outil(self):
        consulter = catalogue_outils.outils_par_nom()[OUTIL_CONSULTER]
        assert all(not f.confirmation for f in consulter.formes)
        enum = consulter.schema["function"]["parameters"]["properties"]["commande"]["enum"]
        assert "meteo" in enum and "parcelle lister" in enum

    def test_us235_ca1_une_destructrice_a_son_propre_outil(self):
        for outil in catalogue_outils.outils():
            if any(f.destructrice for f in outil.formes):
                assert len(outil.formes) == 1
                assert "DESTRUCTRICE" in outil.schema["function"]["description"]

    def test_us235_ca1_les_outils_terminaux_sont_presents(self):
        noms = {o.nom for o in catalogue_outils.outils()}
        assert set(catalogue_outils.OUTILS_TERMINAUX) <= noms

    def test_us235_ca1_le_catalogue_est_stable(self):
        """Un ordre stable garde le préfixe cacheable d'un appel à l'autre."""
        assert catalogue_outils.generer_outils() == catalogue_outils.generer_outils()
        assert catalogue_outils.schemas() == [o.schema for o in catalogue_outils.outils()]


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — /parcelle modifier à champs typés, traduit sans toucher au handler
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2ModifierParcelleType:

    @pytest.fixture
    def proprietes(self):
        outil = catalogue_outils.outils_par_nom()[OUTIL_MODIFIER_PARCELLE]
        return outil.schema["function"]["parameters"]["properties"]

    def test_us235_ca2_pepiniere_est_un_oui_non(self, proprietes):
        assert proprietes["est_pepiniere"]["type"] == ["boolean", "null"]

    def test_us235_ca2_abri_est_une_liste_fermee_du_domaine(self, proprietes):
        from utils.parcelles import ABRIS
        assert proprietes["abri"]["enum"] == [*ABRIS, None]

    def test_us235_ca2_exposition_est_une_liste_fermee(self, proprietes):
        from app.services.parcelles import EXPOSITIONS_PROPOSEES
        assert proprietes["exposition"]["enum"] == [*EXPOSITIONS_PROPOSEES, None]

    def test_us235_ca2_longueur_et_rangs_sont_des_nombres(self, proprietes):
        assert proprietes["longueur_m"]["type"] == ["number", "null"]
        assert proprietes["nb_rangs"]["type"] == ["integer", "null"]

    def test_us235_ca2_tous_les_champs_de_fiche_sont_exposes(self, proprietes):
        from app.services.parcelles import CHAMPS_FICHE
        assert set(CHAMPS_FICHE) <= set(proprietes)
        assert "type_pepiniere" in proprietes

    def test_us235_ca2_negation_traduite_en_cle_valeur(self):
        champ = {c.nom: c for c in catalogue_outils.champs_fiche()}
        assert adaptateurs.modification_parcelle([(champ["est_pepiniere"], False)]) == "pepiniere=non"

    def test_us235_ca2_type_de_pepiniere_porte_par_la_meme_cle(self):
        champ = {c.nom: c for c in catalogue_outils.champs_fiche()}
        assert adaptateurs.modification_parcelle(
            [(champ["est_pepiniere"], True), (champ["type_pepiniere"], "froide")]
        ) == "pepiniere=froide"
        assert adaptateurs.modification_parcelle(
            [(champ["est_pepiniere"], False), (champ["type_pepiniere"], "froide")]
        ) == "pepiniere=non"
        assert adaptateurs.modification_parcelle([(champ["type_pepiniere"], "chaude")]) == "pepiniere=chaude"

    def test_us235_ca2_une_valeur_ne_porte_jamais_d_espace(self):
        champ = {c.nom: c for c in catalogue_outils.champs_fiche()}
        assert adaptateurs.modification_parcelle(
            [(champ["ensoleillement"], "plein soleil")]
        ) == "ensoleillement=plein-soleil"

    def test_us235_ca2_nombres_sans_decimale_inutile(self):
        assert adaptateurs.texte_nombre(6.0) == "6"
        assert adaptateurs.texte_nombre(12.5) == "12.5"

    def test_us235_ca2_plusieurs_champs_un_argument_chacun_pour_le_handler(self):
        """[CA2] Le handler lit `ctx.args[2:]` en `clé=valeur` : chaque champ est un argument."""
        verdict = _valider("la planche nord a 6 rangs et fait 12 m", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "nb_rangs": 6, "longueur_m": 12})
        assert verdict.commande.args == ("modifier", "Planche Nord", "longueur=12", "rangs=6")

    def test_us235_ca2_un_texte_de_regle_reste_un_seul_argument(self):
        """Le découpage ne vaut que pour des `clé=valeur` : une valeur des règles est intacte."""
        commande = interp.reconnaitre_par_regles("la planche nord a 5 rangs")
        assert commande.args[-1] == "rangs=5"

    def test_us235_ca2_les_valeurs_traduites_passent_le_point_d_ecriture(self):
        """[CA2] Ce que l'adaptateur écrit, `update_parcelle` le valide tel quel."""
        from utils.parcelles import valider_champs
        verdict = _valider(
            "la planche nord est plein soleil, sol argileux, abri voile, paillée",
            OUTIL_MODIFIER_PARCELLE,
            {"parcelle": "Planche Nord", "ensoleillement": "plein soleil", "type_sol": "Argileux",
             "abri": "voile", "paillage": True},
        )
        kwargs = dict(m.split("=", 1) for m in verdict.commande.args[2:])
        valider_champs(**kwargs)  # ne lève pas


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — parité formes dictables ↔ outils
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3Parite:

    def test_us235_ca3_parite_verte(self):
        assert catalogue_outils.controler_parite_outils() == []

    def test_us235_ca3_une_forme_sans_outil_fait_echouer(self, monkeypatch):
        sans_meteo = tuple(
            replace(o, formes=tuple(f for f in o.formes if f.commande != "meteo"))
            for o in catalogue_outils.outils()
        )
        monkeypatch.setattr(catalogue_outils, "_CACHE", sans_meteo)
        assert any("/meteo n'a pas d'outil" in a for a in catalogue_outils.controler_parite_outils())

    def test_us235_ca3_un_outil_sans_forme_fait_echouer(self, monkeypatch):
        orphelin = catalogue_outils.Outil("exporter_excel", {"type": "function", "function": {}})
        monkeypatch.setattr(catalogue_outils, "_CACHE", (*catalogue_outils.outils(), orphelin))
        assert any("exporter_excel" in a for a in catalogue_outils.controler_parite_outils())

    def test_us235_ca3_une_forme_couverte_deux_fois_fait_echouer(self, monkeypatch):
        outils = catalogue_outils.outils()
        doublon = replace(outils[0], nom="modifier_parcelle_bis")
        monkeypatch.setattr(catalogue_outils, "_CACHE", (*outils, doublon))
        assert any("plusieurs outils" in a for a in catalogue_outils.controler_parite_outils())

    def test_us235_ca3_trop_d_outils_fait_echouer(self, monkeypatch):
        monkeypatch.setattr(catalogue_outils, "NB_OUTILS_MAX", 3)
        assert any("plafond" in a for a in catalogue_outils.controler_parite_outils())


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — un nom de parcelle existe ; un voisin est proposé, jamais substitué
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4Entites:

    def test_us235_ca4_nom_exact_dit_garde_avec_l_ecriture_de_la_base(self):
        verdict = _valider("ma serre exterieure n'est plus une pepiniere", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "serre extérieure", "est_pepiniere": False})
        assert verdict.commande.valeurs["nom"] == "Serre extérieure"
        assert verdict.commande.complete

    def test_us235_ca4_rattachement_du_modele_propose_jamais_substitue(self):
        """« la serre » → « Serre extérieure » est une déduction : proposée au jardinier."""
        verdict = _valider("la serre n'est plus une pépinière", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Serre extérieure", "est_pepiniere": False})
        commande = verdict.commande
        assert commande.candidats == ("Serre extérieure",)
        assert "nom" not in commande.valeurs
        assert not commande.complete

    def test_us235_ca4_nom_voisin_propose(self):
        verdict = _valider("la planche nordd n'est plus paillée", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "planche nordd", "paillage": False},
                           voisin=lambda nom: "Planche Nord")
        assert verdict.commande.candidats == ("Planche Nord",)
        assert verdict.commande.argument_candidat == "nom"

    def test_us235_ca4_nom_inconnu_demande_une_precision(self):
        verdict = _valider("le potager du fond n'est plus paillé", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "potager du fond", "paillage": False})
        commande = verdict.commande
        assert commande.candidats == ()
        assert commande.argument_candidat == "nom"
        assert not commande.complete

    @pytest.mark.asyncio
    async def test_us235_ca4_le_bot_affiche_la_proposition_du_voisin(self):
        """[CA4] Le bot montre « Vouliez-vous dire… » et n'exécute rien."""
        commande = _valider("la serre n'est plus une pépinière", OUTIL_MODIFIER_PARCELLE,
                            {"parcelle": "Serre extérieure", "est_pepiniere": False}).commande
        update = MagicMock()
        update.effective_user.id = 7
        update.message.reply_text = AsyncMock()
        ctx = MagicMock(user_data={})
        with patch.object(bot_module, "current_context", return_value=CTX), \
             patch.object(interp, "persister_journal", return_value=1):
            await bot_module._interp_proposer(update, ctx, commande)
        texte = update.message.reply_text.await_args.args[0]
        assert "Vouliez-vous dire" in texte and "SERRE EXTÉRIEURE" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — un nombre a été dit, en chiffres ou en lettres
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5Nombres:

    def test_us235_ca5_nombre_en_chiffres(self):
        verdict = _valider("la planche nord a maintenant 6 rangs", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "nb_rangs": 6})
        assert verdict.commande.valeurs["modification"] == "rangs=6"

    def test_us235_ca5_nombre_en_lettres(self):
        verdict = _valider("la planche nord a maintenant six rangs", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "nb_rangs": 6})
        assert verdict.commande.valeurs["modification"] == "rangs=6"

    def test_us235_ca5_decimal_avec_virgule(self):
        verdict = _valider("la planche nord fait 12,5 mètres", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "longueur_m": 12.5})
        assert verdict.commande.valeurs["modification"] == "longueur=12.5"

    def test_us235_ca5_nombre_non_dit_rejete(self):
        verdict = _valider("la planche nord a maintenant 6 rangs", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "nb_rangs": 7})
        assert verdict.commande is None
        assert "n'a pas été dit" in verdict.motif

    def test_us235_ca5_nombre_d_une_autre_commande_non_dit_rejete(self):
        verdict = _valider("corrige la profondeur de semis des carottes", "corriger_culture",
                           {"action": "profondeur", "culture": "carottes", "valeur_profondeur": 2})
        assert verdict.commande is None

    def test_us235_ca5_nombre_dit_d_une_autre_commande(self):
        verdict = _valider("la profondeur de semis des carottes est de 2 cm", "corriger_culture",
                           {"action": "profondeur", "culture": "carottes", "valeur_profondeur": 2})
        assert verdict.commande.commande_equivalente() == "/culture profondeur carottes 2"

    def test_us235_ca5_entier_attendu(self):
        verdict = _valider("la planche nord a 6 rangs", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "nb_rangs": 6.5})
        assert verdict.commande is None

    def test_us235_ca5_un_booleen_n_est_pas_un_nombre(self):
        verdict = _valider("la planche nord a 1 rang", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "nb_rangs": True})
        assert verdict.commande is None


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — une valeur fermée déduite n'est gardée que si son champ est évoqué
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6AncrageDuChamp:

    def test_us235_ca6_type_de_pepiniere_non_dit_retire(self):
        """L'exemple du §3.5 règle 9 : « chaude » n'a pas été dit."""
        verdict = _valider("mets la planche nord en pépinière", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "est_pepiniere": True, "type_pepiniere": "chaude"})
        assert verdict.retires == ("type_pepiniere",)
        assert verdict.commande.valeurs["modification"] == "pepiniere=oui"

    def test_us235_ca6_type_de_pepiniere_dit_garde(self):
        verdict = _valider("la planche nord devient une pépinière chauffée", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "est_pepiniere": True, "type_pepiniere": "chaude"})
        assert verdict.commande.valeurs["modification"] == "pepiniere=chaude"

    def test_us235_ca6_le_nom_de_la_parcelle_n_evoque_pas_un_champ(self):
        """« Serre extérieure » contient « serre », une valeur d'abri : le nom ne compte pas."""
        verdict = _valider(NEGATION, OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Serre extérieure", "est_pepiniere": False, "abri": "serre"})
        assert verdict.retires == ("abri",)
        assert verdict.commande.valeurs["modification"] == "pepiniere=non"

    def test_us235_ca6_valeur_evoquee_par_un_mot_voisin(self):
        verdict = _valider("la planche sud n'est plus paillée", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Sud", "paillage": False})
        assert verdict.commande.valeurs["modification"] == "paillage=non"

    def test_us235_ca6_retrait_par_le_nom_du_champ(self):
        verdict = _valider("retire l'abri de la planche sud", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Sud", "abri": "aucun"})
        assert verdict.commande.valeurs["modification"] == "abri=aucun"

    def test_us235_ca6_tous_les_champs_retires_la_modification_est_demandee(self):
        """Rien d'évoqué : la modification est demandée, rien n'est écrit.
        [US-276] Par une précision, plus par une proposition vide à compléter."""
        verdict = _valider("occupe-toi de la planche nord", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "paillage": True})
        assert verdict.commande is None and verdict.retires == ("paillage",)
        assert verdict.precision == "Que veux-tu changer sur « Planche Nord » ?"

    def test_us235_ca6_valeur_hors_liste_rejetee(self):
        verdict = _valider("la planche nord est sous cloche", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "abri": "cloche"})
        assert verdict.commande is None

    def test_us235_ca6_valeur_de_liste_insensible_a_la_casse(self):
        verdict = _valider("le sol de la planche nord est humifère", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "type_sol": "humifere"})
        assert verdict.commande.valeurs["modification"] == "type_sol=Humifère"

    def test_us235_ca6_vocabulaire_d_une_autre_commande_non_evoque_retire(self):
        """`/bioagresseur rattacher` : une fréquence non dite est retirée, puis demandée."""
        verdict = _valider("le mildiou attaque la tomate", "renseigner_bioagresseur",
                           {"action": "rattacher", "culture": "tomate", "frequence": "courant",
                            "bioagresseur": "mildiou"})
        assert verdict.retires == ("frequence",)
        assert [a.nom for a in verdict.commande.manquants] == ["frequence"]

    def test_us235_ca6_valeur_d_une_autre_commande_hors_liste_rejetee(self):
        verdict = _valider("le mildiou attaque souvent la tomate", "renseigner_bioagresseur",
                           {"action": "rattacher", "culture": "tomate", "frequence": "souvent",
                            "bioagresseur": "mildiou"})
        assert verdict.commande is None

    def test_us235_ca6_un_booleen_doit_etre_un_booleen(self):
        verdict = _valider("la planche nord n'est plus paillée", OUTIL_MODIFIER_PARCELLE,
                           {"parcelle": "Planche Nord", "paillage": "non"})
        assert verdict.commande is None


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — une commande destructrice exige un nom exact, jamais déduit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Destructrice:

    def test_us235_ca7_suppression_sur_nom_exact_dit(self):
        verdict = _valider("supprime la planche nord", "supprimer_parcelle", {"nom": "Planche Nord"})
        assert verdict.commande.complete
        assert verdict.commande.forme.destructrice

    def test_us235_ca7_suppression_sur_nom_deduit_jamais_executable(self):
        """[US-276] Ni proposée avec un candidat : la précision nomme les choix réels."""
        verdict = _valider("supprime la planche", "supprimer_parcelle", {"nom": "Planche Nord"})
        assert verdict.commande is None
        assert verdict.precision == "Quelle parcelle veux-tu supprimer : Planche Nord ou Planche Sud ?"

    def test_us235_ca7_suppression_sur_nom_voisin_jamais_executable(self):
        verdict = _valider("supprime la planche nordest", "supprimer_parcelle", {"nom": "planche nordest"},
                           voisin=lambda nom: "Planche Nord")
        assert verdict.commande is None and "Planche Nord" in verdict.precision

    def test_us235_ca7_renommer_vers_le_meme_nom_demande_le_nouveau(self):
        """La leçon d'US-233 : « renomme la planche nord » → Planche Nord → Planche Nord."""
        verdict = _valider("renomme la planche nord", "renommer_parcelle",
                           {"ancien": "Planche Nord", "nouveau": "Planche Nord"})
        commande = verdict.commande
        assert "nouveau" in verdict.retires
        assert [a.nom for a in commande.manquants] == ["nouveau"]

    def test_us235_ca7_renommer_avec_un_nouveau_nom_dit(self):
        verdict = _valider("renomme la planche nord en planche des courges", "renommer_parcelle",
                           {"ancien": "Planche Nord", "nouveau": "planche des courges"})
        assert verdict.commande.commande_equivalente() == "/parcelle renommer Planche Nord planche des courges"


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le potager est toujours celui du contexte
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Potager:

    def test_us235_ca8_aucune_propriete_ne_porte_le_potager(self):
        for outil in catalogue_outils.outils():
            proprietes = outil.schema["function"].get("parameters", {}).get("properties", {})
            assert not any("potager_id" in p for p in proprietes)

    def test_us235_ca8_un_potager_produit_par_le_modele_est_rejete(self):
        verdict = _valider("supprime la planche nord", "supprimer_parcelle",
                           {"nom": "Planche Nord", "potager_id": 2})
        assert verdict.commande is None
        assert "potager_id" in verdict.motif

    def test_us235_ca8_les_parcelles_lues_sont_celles_du_potager_du_contexte(self, session_de_test):
        _parcelle(session_de_test, "Planche Nord")
        autre = Parcelle(nom="Ailleurs", nom_normalise="ailleurs", potager_id=2, actif=True)
        session_de_test.add(autre)
        session_de_test.commit()
        assert interpreteur_agent.noms_parcelles_du_potager(CTX) == ("Planche Nord",)

    def test_us235_ca8_lecture_impossible_aucun_nom(self, monkeypatch):
        monkeypatch.setattr("database.db.SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        assert interpreteur_agent.noms_parcelles_du_potager(CTX) == ()

    def test_us235_ca8_voisin_lu_dans_le_potager_du_contexte(self, session_de_test):
        _parcelle(session_de_test, "Planche Nord")
        voisin = interpreteur_agent.voisin_en_base(CTX)
        assert voisin("planche nordd") == "Planche Nord"
        assert voisin("rien de tel") is None

    def test_us235_ca8_voisin_base_indisponible(self, monkeypatch):
        monkeypatch.setattr("database.db.SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        assert interpreteur_agent.voisin_en_base(CTX)("planche") is None

    def test_us235_ca8_le_contexte_est_passe_a_la_passerelle(self, modele, parcelles_connues):
        modele.return_value = _reponse(AppelOutil("afficher", {"commande": "meteo"}))
        interpreteur_agent.proposer("et le temps demain", CTX)
        assert modele.call_args.kwargs["ctx"] is CTX


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — pas de seuil de confiance sur ce chemin
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9SeuilDeConfiance:

    def test_us235_ca9_agent_sans_seuil(self, agent_actif, modele, parcelles_connues, monkeypatch):
        monkeypatch.setattr(interp, "SEUIL_CONFIANCE_MODELE", 2.0)
        modele.side_effect = [_reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE,
                                                  {"parcelle": "Serre extérieure", "est_pepiniere": False})), _texte()]
        assert isinstance(interp.interpreter(NEGATION, CTX).proposition, interp.CommandeInterpretee)

    def test_us235_ca9_le_seuil_reste_sur_l_ancien_chemin(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "off")
        faible = interp._construire_commande(
            interp.FORMES_PAR_CLE[("meteo", None)], {}, interp.ORIGINE_MODELE, 0.5, "x")
        with patch.object(interp, "_appeler_modele", return_value=faible):
            assert interp.interpreter("et le ciel aujourd'hui", CTX) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA10, CA11 — la proposition et son récapitulatif
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10CA11Recapitulatif:

    def _recap(self, texte, arguments):
        return interp.recapitulatif(_valider(texte, OUTIL_MODIFIER_PARCELLE, arguments).commande)

    def test_us235_ca10_negation_retire_le_statut_pepiniere(self):
        recap = _sans_gras(self._recap(NEGATION, {"parcelle": "Serre extérieure", "est_pepiniere": False}))
        assert "Je retire le statut pépinière de Serre extérieure" in recap

    def test_us235_ca10_commande_equivalente_affichee(self):
        recap = self._recap(NEGATION, {"parcelle": "Serre extérieure", "est_pepiniere": False})
        assert "`/parcelle modifier Serre extérieure pepiniere=non`" in recap

    def test_us235_ca11_je_passe_a_six_rangs(self):
        recap = _sans_gras(self._recap("la planche nord a maintenant 6 rangs",
                                       {"parcelle": "Planche Nord", "nb_rangs": 6}))
        assert "Je passe le nombre de rangs de Planche Nord à 6." in recap

    def test_us235_ca11_chaque_champ_modifie_est_nomme(self):
        recap = _sans_gras(self._recap(
            "la planche nord fait 12 m, n'est plus paillée et passe sous tunnel",
            {"parcelle": "Planche Nord", "longueur_m": 12, "paillage": False, "abri": "tunnel"}))
        assert "la longueur de Planche Nord à 12 m." in recap
        assert "Je retire le paillage de Planche Nord" in recap
        assert "l'abri de Planche Nord à tunnel" in recap

    @pytest.mark.parametrize("arguments, attendu", [
        ({"paillage": True}, "J'ajoute le paillage à Planche Nord"),
        ({"abri": "aucun"}, "Je retire l'abri de Planche Nord"),
        ({"actif": False}, "Je mets hors service Planche Nord"),
        ({"actif": True}, "Je remets en service Planche Nord"),
        ({"est_pepiniere": True}, "J'ajoute le statut pépinière à Planche Nord"),
        ({"est_pepiniere": True, "type_pepiniere": "froide"}, "Je déclare Planche Nord comme pépinière froide"),
        ({"ensoleillement": "plein soleil"}, "l'ensoleillement de Planche Nord à plein soleil"),
    ])
    def test_us235_ca11_sens_de_chaque_champ(self, arguments, attendu):
        texte = ("la planche nord : paillage, abri, en service, pépinière froide, "
                 "ensoleillement plein soleil")
        recap = _sans_gras(self._recap(texte, {"parcelle": "Planche Nord", **arguments}))
        assert attendu in recap

    def test_us235_ca11_une_cle_inconnue_reste_lisible(self):
        assert "« ordre_bis »" in interp._phrase_modification("X", "ordre_bis", "3")

    def test_us235_ca11_le_recapitulatif_des_regles_ne_change_pas(self):
        """L'ancien récapitulatif (puces) reste celui des règles : aucune régression."""
        recap = interp.recapitulatif(interp.reconnaitre_par_regles("la planche nord a 5 rangs"))
        assert "• nombre de rangs : *5*\n" in recap


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — AGENT_MODE : off, ombre, actif
# ═════════════════════════════════════════════════════════════════════════════
class TestCA12Modes:

    def test_us235_ca12_off_l_agent_n_est_jamais_appele(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "off")
        with patch.object(interpreteur_agent, "proposer") as proposer, \
             patch.object(interpreteur_agent, "lancer_en_arriere_plan") as lancer, \
             patch.object(interp, "_appeler_modele", return_value=None):
            interp.interpreter(NEGATION, CTX)
        proposer.assert_not_called()
        lancer.assert_not_called()

    def test_us235_ca12_mode_inconnu_vaut_off(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "turbo")
        assert interp._mode_agent() == "off"

    def test_us235_ca12_ombre_le_bot_se_comporte_comme_avant(self, monkeypatch):
        monkeypatch.setattr(config, "AGENT_MODE", "ombre")
        ancien = interp._construire_commande(
            interp.FORMES_PAR_CLE[("meteo", None)], {}, interp.ORIGINE_MODELE, 0.9, "x")
        with patch.object(interp, "_appeler_modele", return_value=ancien), \
             patch.object(interpreteur_agent, "lancer_en_arriere_plan") as lancer:
            resultat = interp.interpreter("et le ciel aujourd'hui", CTX)
        assert resultat.origine == interp.ORIGINE_MODELE
        lancer.assert_called_once()

    def test_us235_ca12_ombre_journalise_ce_que_l_agent_aurait_propose(
        self, monkeypatch, modele, parcelles_connues
    ):
        monkeypatch.setattr(config, "AGENT_MODE", "ombre")
        monkeypatch.setattr(interpreteur_agent, "lancer_en_arriere_plan", lambda f: f())
        modele.return_value = _reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE,
                                                  {"parcelle": "Serre extérieure", "est_pepiniere": False}))
        with patch.object(interp, "_appeler_modele", return_value=None), \
             patch.object(interpreteur_agent, "persister_observation") as observation:
            assert interp.interpreter(NEGATION, CTX) is None
        _ctx, texte, resultat = observation.call_args.args
        assert texte == NEGATION
        assert resultat.commande.commande_equivalente() == "/parcelle modifier Serre extérieure pepiniere=non"

    def test_us235_ca12_actif_l_agent_remplace_l_ancien_repli(self, agent_actif, modele, parcelles_connues):
        modele.side_effect = [_reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE,
                                                  {"parcelle": "Serre extérieure", "est_pepiniere": False})), _texte()]
        with patch.object(interp, "_appeler_modele") as ancien:
            resultat = interp.interpreter(NEGATION, CTX)
        ancien.assert_not_called()
        assert resultat.proposition.origine == interp.ORIGINE_AGENT

    def test_us235_ca12_actif_les_regles_passent_avant_l_agent(self, agent_actif, modele):
        """CA15 par construction : ce que les règles reconnaissent ne change pas."""
        resultat = interp.interpreter("la planche nord a 5 rangs", CTX)
        assert resultat.origine == interp.ORIGINE_REGLE
        modele.assert_not_called()

    def test_us235_ca12_actif_une_demande_de_savoir_ne_coute_aucun_appel(self, agent_actif, modele):
        assert interp.interpreter("comment supprimer une parcelle ?", CTX) is None
        modele.assert_not_called()

    def test_us235_ca12_actif_un_geste_ne_va_jamais_a_l_agent(self, agent_actif, modele):
        """A6 : le geste file au parseur de gestes."""
        assert interp.interpreter("récolté 2 kg de tomates", CTX) is None
        modele.assert_not_called()

    def test_us235_ca12_actif_un_nom_de_parcelle_n_est_pas_un_geste(
        self, agent_actif, modele, parcelles_connues
    ):
        """Relevé du 21/10/2026 : « tunnel », mot de geste, est ici le nom de la parcelle."""
        modele.side_effect = [_reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE,
                                                  {"parcelle": "Tunnel", "est_pepiniere": False})), _texte()]
        resultat = interp.interpreter("le tunnel n'est plus une pépinière", CTX)
        assert resultat.proposition.commande_equivalente() == "/parcelle modifier Tunnel pepiniere=non"

    def test_us235_ca12_actif_un_nom_dit_en_partie_n_est_pas_un_geste(self, agent_actif, modele, monkeypatch):
        """Relevé du 28/10/2026 : « ma planche tunnel » nomme TUNNEL CHAUFFÉ."""
        monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("TUNNEL CHAUFFÉ",))
        modele.side_effect = [_texte()]
        interp.interpreter("ma planche tunnel a une superficie de 20m2, longueur de 7m", CTX)
        modele.assert_called()

    def test_us235_ca12_actif_un_geste_reste_un_geste_a_cote_d_un_nom(self, agent_actif, modele, monkeypatch):
        """« tunnel » sans mot de parcelle devant reste un geste, même quand une parcelle s'appelle Tunnel…"""
        monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: ("TUNNEL CHAUFFÉ",))
        assert interp.interpreter("tunnel posé sur les fraises", CTX) is None
        modele.assert_not_called()

    def test_us235_ca12_actif_une_reponse_en_texte_est_rendue_au_bot(self, agent_actif, modele, parcelles_connues):
        """[US-257] L'agent répond en texte : la réponse est rendue au bot, jamais à l'ancien repli."""
        modele.return_value = _texte("Tu as deux pépinières : la Serre extérieure et le Tunnel.")
        with patch.object(interp, "_appeler_modele") as ancien:
            resultat = interp.interpreter("liste mes pépinières", CTX)
        assert isinstance(resultat, interp.ReponseAgent) and "pépinières" in resultat.texte
        ancien.assert_not_called()

    def test_us235_ca12_actif_un_rejet_du_validateur_poursuit_son_chemin(
        self, agent_actif, modele, parcelles_connues
    ):
        modele.return_value = _reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE,
                                                  {"parcelle": "Planche Nord", "nb_rangs": 9}))
        with patch.object(interp, "_appeler_modele") as ancien:
            resultat = interp.interpreter("la planche nord a maintenant six rangs", CTX)
        ancien.assert_not_called()
        # [US-278] Le 9 inventé reste refusé ; le filet propose la valeur DITE.
        assert resultat.proposition.commande_equivalente() == "/parcelle modifier Planche Nord rangs=6"

    def test_us235_ca12_sans_contexte_l_agent_n_est_pas_appele(self, agent_actif, modele):
        with patch.object(interp, "_appeler_modele", return_value=None):
            interp.interpreter(NEGATION, None)
        modele.assert_not_called()

    def test_us235_ca12_l_observation_tourne_a_cote_de_la_reponse(self):
        fini = threading.Event()
        interpreteur_agent.lancer_en_arriere_plan(fini.set)
        assert fini.wait(2)

    def test_us235_ca12_l_observation_ne_leve_jamais(self):
        with patch.object(interpreteur_agent, "proposer", side_effect=RuntimeError("x")):
            interpreteur_agent.observer(NEGATION, CTX)  # ne lève pas


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — modèle indisponible : retour silencieux au comportement actuel
# ═════════════════════════════════════════════════════════════════════════════
class TestCA13Repli:

    @pytest.mark.parametrize("panne", [
        passerelle.QuotaLLMDepasseError("429"),
        passerelle.FournisseurLLMIndisponibleError("panne"),
        passerelle.DelaiLLMDepasseError("délai"),
    ])
    def test_us235_ca13_exception_retour_a_l_ancien_chemin(self, agent_actif, modele, parcelles_connues, panne):
        modele.side_effect = panne
        with patch.object(interp, "_appeler_modele", return_value=None) as ancien:
            assert interp.interpreter(NEGATION, CTX) is None
        ancien.assert_called_once()

    @pytest.mark.parametrize("statut", [passerelle.STATUT_SANS_OUTILS, passerelle.STATUT_APPEL_INVALIDE])
    def test_us235_ca13_outils_non_geres_retour_a_l_ancien_chemin(
        self, agent_actif, modele, parcelles_connues, statut
    ):
        modele.return_value = _reponse(statut=statut)
        ancien_resultat = interp._construire_commande(
            interp.FORMES_PAR_CLE[("meteo", None)], {}, interp.ORIGINE_MODELE, 0.9, "x")
        with patch.object(interp, "_appeler_modele", return_value=ancien_resultat):
            resultat = interp.interpreter("et le ciel aujourd'hui", CTX)
        assert resultat.origine == interp.ORIGINE_MODELE

    def test_us257_aucun_appel_ni_texte_est_une_reponse_vide(self, modele, parcelles_connues):
        """[US-257] Sans outil obligatoire, un tour sans appel est une réponse ; vide, elle n'a
        rien à montrer, et l'interpréteur le dit au jardinier sans tenter un autre modèle."""
        modele.return_value = _reponse()
        resultat = interpreteur_agent.proposer(NEGATION, CTX)
        assert resultat.disponible and resultat.motif == interpreteur_agent.MOTIF_REPONSE_VIDE

    def test_us235_ca13_plusieurs_appels_avec_une_suppression_rien_n_est_propose(
        self, modele, parcelles_connues
    ):
        """[US-237 / CA4] Plusieurs appels forment un plan ; une suppression n'y
        entre pas. [US-257] Le refus revient au modèle ; ce qui passe reste proposé, seul."""
        modele.side_effect = [_reponse(
            AppelOutil(OUTIL_MODIFIER_PARCELLE, {"parcelle": "Serre extérieure", "est_pepiniere": False}),
            AppelOutil("supprimer_parcelle", {"nom": "Planche Nord"}),
        ), _texte("La suppression se demande à part.")]
        # [US-276 / CA3] L'outil destructeur n'est vu que si la phrase dit la destruction.
        resultat = interpreteur_agent.proposer(f"{NEGATION} et supprime la planche nord", CTX)
        assert resultat.plan is None
        assert resultat.commande.commande_equivalente() == "/parcelle modifier Serre extérieure pepiniere=non"
        assert any("que seule" in raison for raison in resultat.refus)
        assert resultat.outils == (OUTIL_MODIFIER_PARCELLE, "supprimer_parcelle")

    def test_us235_ca13_appel_malforme_rejete(self):
        verdict = valider_appel(AppelOutil(OUTIL_MODIFIER_PARCELLE, {}, arguments_valides=False),
                                ContexteValidation(texte=NEGATION, noms_parcelles=PARCELLES))
        assert verdict.commande is None

    def test_us235_ca13_outil_inconnu_rejete(self):
        assert _valider(NEGATION, "exporter_excel", {}).commande is None

    def test_us235_ca13_discriminant_inconnu_rejete(self):
        assert _valider("montre la meteo", OUTIL_CONSULTER, {"commande": "radar"}).commande is None

    def test_us235_ca13_le_prompt_porte_les_parcelles_apres_la_partie_fixe(self, modele, parcelles_connues):
        modele.return_value = _reponse(AppelOutil("hors_perimetre", {"raison": "export"}))
        interpreteur_agent.proposer("exporte en excel", CTX)
        kwargs = modele.call_args.kwargs
        assert kwargs["prompt_fixe"] == interpreteur_agent.PROMPT_FIXE
        assert "Serre extérieure" in kwargs["prompt_variable"]
        # [US-276] Sans verbe de destruction, le catalogue projeté sans destruction.
        assert kwargs["outils"] == catalogue_outils.schemas(catalogue_outils.PROJECTION_SANS_DESTRUCTION)


# ═════════════════════════════════════════════════════════════════════════════
# CA14 — le journal porte origine=agent et le nom des outils
# ═════════════════════════════════════════════════════════════════════════════
class TestCA14Journal:

    def test_us235_ca14_proposition_journalisee_origine_et_outils(self, session_de_test):
        commande = _valider(NEGATION, OUTIL_MODIFIER_PARCELLE,
                            {"parcelle": "Serre extérieure", "est_pepiniere": False}).commande
        commande = replace(commande, tokens_consommes=950)
        log_id = interp.persister_journal(CTX, commande, interp.ISSUE_PROPOSEE)
        ligne = session_de_test.get(RoutageLog, log_id)
        assert ligne.origine_classification == "agent"
        assert ligne.outils_agent == OUTIL_MODIFIER_PARCELLE
        assert ligne.tokens_consommes == 950
        assert ligne.commande_interpretee == "parcelle modifier"

    def test_us235_ca14_une_regle_n_a_pas_d_outils(self, session_de_test):
        log_id = interp.persister_journal(
            CTX, interp.reconnaitre_par_regles("la planche nord a 5 rangs"), interp.ISSUE_PROPOSEE)
        ligne = session_de_test.get(RoutageLog, log_id)
        assert ligne.outils_agent is None and ligne.tokens_consommes == 0

    def test_us235_ca14_observation_en_ombre(self, session_de_test):
        resultat = interpreteur_agent.ResultatAgent(
            disponible=True, outils=("poser_question",), motif="aiguillage", latence_ms=420, tokens=980)
        interpreteur_agent.persister_observation(CTX, "quelles sont mes pépinières ?", resultat)
        ligne = session_de_test.query(RoutageLog).one()
        assert (ligne.issue_interpretation, ligne.origine_classification) == ("ombre", "agent")
        assert ligne.outils_agent == "poser_question"
        assert ligne.commande_interpretee is None
        assert ligne.tokens_consommes == 980

    def test_us235_ca14_observation_avec_commande(self, session_de_test):
        commande = _valider(NEGATION, OUTIL_MODIFIER_PARCELLE,
                            {"parcelle": "Serre extérieure", "est_pepiniere": False}).commande
        resultat = interpreteur_agent.ResultatAgent(disponible=True, commande=commande,
                                                    outils=(OUTIL_MODIFIER_PARCELLE,))
        interpreteur_agent.persister_observation(CTX, NEGATION, resultat)
        assert session_de_test.query(RoutageLog).one().commande_interpretee == "parcelle modifier"

    def test_us235_ca14_observation_ne_leve_jamais(self, monkeypatch):
        monkeypatch.setattr("database.db.SessionLocal", MagicMock(side_effect=RuntimeError("base")))
        interpreteur_agent.persister_observation(CTX, "x", interpreteur_agent.ResultatAgent(disponible=False))

    def test_us235_ca14_la_ligne_de_log_nomme_l_outil(self, caplog):
        commande = _valider(NEGATION, OUTIL_MODIFIER_PARCELLE,
                            {"parcelle": "Serre extérieure", "est_pepiniere": False}).commande
        with caplog.at_level("INFO", logger="potager"):
            interp.journaliser(commande, interp.ISSUE_PROPOSEE)
        assert "origine=agent" in caplog.text and OUTIL_MODIFIER_PARCELLE in caplog.text

    def test_us235_ca14_la_proposition_porte_jetons_et_outils(self, modele, parcelles_connues):
        modele.side_effect = [_reponse(AppelOutil(OUTIL_MODIFIER_PARCELLE,
                                                  {"parcelle": "Serre extérieure", "est_pepiniere": False})), _texte()]
        commande = interpreteur_agent.proposer(NEGATION, CTX).commande
        assert commande.outils == (OUTIL_MODIFIER_PARCELLE,)
        assert commande.tokens_consommes == 950

    def test_us235_ca14_migration_et_rollback(self):
        from pathlib import Path
        racine = Path(__file__).resolve().parent.parent / "migrations"
        migration = (racine / "migration_v59.sql").read_text(encoding="utf-8")
        rollback = (racine / "rollback_v59.sql").read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS outils_agent" in migration
        assert "DROP COLUMN IF EXISTS outils_agent" in rollback


# ═════════════════════════════════════════════════════════════════════════════
# CA15 — l'outil d'évaluation réelle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA15Evaluation:

    @pytest.fixture
    def ev(self):
        import tools.evaluer_interpreteur_agent as module
        return module

    def test_us235_ca15_corpus_us172_enrichi(self, ev):
        corpus = ev.charger_corpus()
        assert len([p for p in corpus if p.source == "us172"]) >= 200
        assert len([p for p in corpus if p.source == "us235"]) >= 20

    def test_us235_ca15_une_suppression_non_demandee_est_une_erreur(self, ev):
        phrase = ev.Phrase("ma serre n'est plus une pépinière", "parcelle modifier", "commande", "us235")
        supprimer = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "supprimer")], {"nom": "Serre"},
            interp.ORIGINE_AGENT, 1.0, phrase.texte)
        assert ev.destructrice_erronee(phrase, supprimer) is True

    def test_us235_ca15_une_suppression_demandee_n_est_pas_une_erreur(self, ev):
        phrase = ev.Phrase("supprime la parcelle test", "parcelle supprimer", "imperatif", "us172")
        supprimer = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "supprimer")], {"nom": "test"},
            interp.ORIGINE_AGENT, 1.0, phrase.texte)
        assert ev.destructrice_erronee(phrase, supprimer) is False

    def test_us235_ca15_un_nom_inexistant_n_est_pas_executable(self, ev):
        """[US-236 / CA4] « près des tomates » n'est plus lu comme un nom par la règle :
        la phrase passe à l'agent, qui demande laquelle."""
        phrase = ev.Phrase("supprime la parcelle près des tomates", "", "incomplet", "us235")
        assert interp.reconnaitre_par_regles(phrase.texte) is None
        assert ev.destructrice_erronee(phrase, None) is False

    def test_us235_ca15_une_suppression_sans_nom_n_est_pas_executable(self, ev):
        phrase = ev.Phrase("supprime la planche", "", "hors_perimetre", "us235")
        commande = interp._construire_commande(
            interp.FORMES_PAR_CLE[("parcelle", "supprimer")], {}, interp.ORIGINE_AGENT, 1.0, phrase.texte)
        assert ev.destructrice_erronee(phrase, commande) is False

    def test_us235_ca15_regression_des_regles_detectee(self, ev):
        regle = interp.reconnaitre_par_regles("supprime la parcelle test")
        assert ev.regression_regles(regle, None) is True
        assert ev.regression_regles(regle, regle) is False
        assert ev.regression_regles(None, regle) is False

    def test_us235_ca15_regression_sur_une_ambiguite(self, ev):
        ambiguite = interp.Ambiguite(candidats=(interp.reconnaitre_par_regles("supprime la parcelle test"),))
        assert ev.regression_regles(ambiguite, ambiguite) is False
        assert ev.regression_regles(ambiguite, interp.Ambiguite(candidats=())) is True

    @pytest.mark.parametrize("texte, attendu, registre, modification, commande, juste", [
        ("q ?", "", "question", "", None, True),
        ("modifie ma serre", "", "incomplet", "", None, True),
        ("ma serre", "parcelle modifier", "negation", "pepiniere=non", "pepiniere=non", True),
        ("ma serre", "parcelle modifier", "negation", "pepiniere=non", "pepiniere=oui", False),
        ("ma serre", "parcelle modifier", "negation", "", None, False),
    ])
    def test_us235_ca15_juger(self, ev, texte, attendu, registre, modification, commande, juste):
        if commande is not None:
            commande = interp._construire_commande(
                interp.FORMES_PAR_CLE[("parcelle", "modifier")], {"nom": "Serre", "modification": commande},
                interp.ORIGINE_AGENT, 1.0, texte)
        assert ev.juger(ev.Phrase(texte, attendu, registre, "us235", modification), commande) is juste

    def test_us235_ca15_une_phrase_des_regles_ne_coute_aucun_appel(self, ev, agent_actif):
        proposer = MagicMock()
        ligne = ev.evaluer_phrase(ev.Phrase("la planche nord a 5 rangs", "parcelle modifier", "elliptique",
                                            "us172"), CTX, proposer)
        assert ligne.chemin == "regle" and not ligne.regression
        proposer.assert_not_called()

    def test_us235_ca15_un_429_est_attendu_puis_rejoue(self, ev):
        indispo = interpreteur_agent.ResultatAgent(disponible=False, motif="QuotaLLMDepasseError")
        rien = interpreteur_agent.ResultatAgent(disponible=True, outils=("hors_perimetre",), motif="aiguillage")
        proposer = MagicMock(side_effect=[indispo, rien])
        ligne = ev.evaluer_phrase(ev.Phrase("exporte en excel", "", "hors_perimetre", "us235"), CTX,
                                  proposer, dormir=lambda s: None)
        assert (ligne.chemin, ligne.quotas, ligne.juste) == ("agent", 1, True)

    def test_us235_ca15_rapport(self, ev):
        lignes = [
            ev.Ligne(ev.Phrase("a", "", "question", "us235"), "agent", "rien", juste=True, latence_ms=400),
            ev.Ligne(ev.Phrase("b", "parcelle modifier", "negation", "us235", "pepiniere=non"), "agent",
                     "rien", juste=False, latence_ms=900),
        ]
        rapport = ev.rediger_rapport(lignes, "openai/gpt-oss-120b")
        assert "les deux couperets passent" in rapport
        assert "| b | parcelle modifier `pepiniere=non` |" in rapport


# ═════════════════════════════════════════════════════════════════════════════
# Gherkin — de la phrase à la parcelle modifiée
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_us235_gherkin_serre_exterieure_n_est_plus_une_pepiniere(
    agent_actif, modele, session_de_test, monkeypatch
):
    # Given la parcelle "Serre extérieure" est une pépinière, And AGENT_MODE vaut actif
    serre = _parcelle(session_de_test, "Serre extérieure", est_pepiniere=True)
    modele.return_value = _reponse(AppelOutil(
        OUTIL_MODIFIER_PARCELLE, {"parcelle": "serre extérieure", "est_pepiniere": False}))

    # When je dis "Ma serre extérieure n'est plus une pépinière"
    resultat = interp.interpreter(NEGATION, CTX)
    update = MagicMock()
    update.effective_user.id = 42
    update.message = AsyncMock()
    update.callback_query = None
    handlers = {0: [CommandHandler("parcelle", bot_module.cmd_parcelle)]}
    ctx = MagicMock(user_data={}, args=[])
    ctx.application.handlers = handlers
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=session_de_test.get_bind())
    with patch.object(bot_module, "current_context", return_value=CTX), \
         patch("app.bot.interpretation.SessionLocal", fabrique), \
         patch.object(interp, "persister_journal", return_value=1):
        assert await bot_module._traiter_commande_interpretee(update, ctx, resultat)

    # Then le bot propose "Je retire le statut pépinière de Serre extérieure"
    recap = update.message.reply_text.await_args.args[0]
    assert "Je retire le statut pépinière de Serre extérieure" in _sans_gras(recap)
    # And il affiche la commande équivalente "/parcelle modifier serre extérieure pepiniere=non"
    assert "/parcelle modifier serre extérieure pepiniere=non" in recap.lower()

    # When je confirme
    from app.services.compagnon import propositions as svc_propositions

    ident = svc_propositions.en_attente(CTX.user_id, CTX.potager_id).code
    clic = MagicMock()
    clic.effective_user.id = 42
    clic.message = None
    clic.callback_query = AsyncMock()
    clic.callback_query.data = f"interp:ok:{ident}"
    clic.callback_query.message = AsyncMock()
    with patch.object(bot_module, "current_context", return_value=CTX), \
         patch.object(bot_module, "_jardinier_au_clic", return_value=CTX.user_id), \
         patch.object(bot_module, "_contexte_sur", return_value=CTX), \
         patch.object(interp, "persister_journal", return_value=1), \
         patch("app.bot.commandes_parcelle.SessionLocal", fabrique), \
         patch("app.bot.commandes_parcelle.current_context", return_value=CTX), \
         patch("app.bot.commandes_parcelle._refuser_si_role_insuffisant", AsyncMock(return_value=False)):
        await bot_module._interp_cb(clic, ctx)

    # Then "Serre extérieure" n'est plus une pépinière
    session_de_test.expire_all()
    assert session_de_test.get(Parcelle, serre.id).est_pepiniere is False
    assert svc_propositions.en_attente(CTX.user_id, CTX.potager_id) is None


# ═════════════════════════════════════════════════════════════════════════════
# INC-018 — un champ facultatif accepte `null` ; une description décrit le champ
# ═════════════════════════════════════════════════════════════════════════════
def _proprietes_de(outil) -> tuple[dict, list[str]]:
    parametres = outil.schema["function"]["parameters"]
    return parametres["properties"], parametres["required"]


class TestINC018SchemaNullable:

    def test_inc018_tout_champ_facultatif_accepte_null(self):
        """Un `null` sur un type strict fait rejeter l'appel entier (400 `tool_use_failed`)."""
        facultatifs = 0
        for outil in catalogue_outils.outils():
            proprietes, requis = _proprietes_de(outil)
            for nom, propriete in proprietes.items():
                if nom in requis:
                    assert propriete["type"] == "string" or "null" not in propriete["type"], (outil.nom, nom)
                    continue
                facultatifs += 1
                assert "null" in propriete["type"], (outil.nom, nom)
                if "enum" in propriete:
                    assert None in propriete["enum"], (outil.nom, nom)
        assert facultatifs > 20

    @pytest.mark.parametrize("type_json", ["number", "integer", "boolean", "string"])
    def test_inc018_chaque_type_est_couvert(self, type_json):
        trouves = {
            p["type"][0]
            for outil in catalogue_outils.outils()
            for nom, p in _proprietes_de(outil)[0].items()
            if nom not in _proprietes_de(outil)[1]
        }
        assert type_json in trouves

    def test_inc018_les_champs_obligatoires_et_discriminants_restent_stricts(self):
        for outil in catalogue_outils.outils():
            proprietes, requis = _proprietes_de(outil)
            for nom in requis:
                assert isinstance(proprietes[nom]["type"], str), (outil.nom, nom)
                assert None not in proprietes[nom].get("enum", ()), (outil.nom, nom)

    def test_inc018_aucune_description_n_est_une_question(self):
        for outil in catalogue_outils.outils():
            for nom, propriete in _proprietes_de(outil)[0].items():
                description = propriete.get("description", "")
                assert not description.rstrip().endswith("?"), (outil.nom, nom, description)

    def test_inc018_la_description_ne_reprend_pas_la_question_du_catalogue(self):
        questions = {a.question for f in menu_commandes.FORMES_DICTABLES for a in f.arguments}
        for outil in catalogue_outils.outils():
            for nom, propriete in _proprietes_de(outil)[0].items():
                description = propriete.get("description", "")
                assert not any(q in description for q in questions), (outil.nom, nom, description)

    def test_inc018_l_exposition_d_une_parcelle_ne_se_deduit_pas_du_nom(self):
        proprietes, _ = _proprietes_de(catalogue_outils.outils_par_nom()["creer_parcelle"])
        description = proprietes["exposition"]["description"]
        assert "exposition de la parcelle" in description.lower()
        assert "ne se déduit pas du nom" in description

    @pytest.mark.parametrize("arguments", [
        {"nom": "Planche Nord", "exposition": None, "superficie_m2": None},
        {"nom": "Planche Nord", "superficie_m2": None},
        {"nom": "Planche Nord", "exposition": "", "superficie_m2": None, "nb_rangs": None},
    ])
    def test_inc018_null_vaut_non_dit_a_la_validation(self, arguments):
        verdict = _valider("crée la planche Nord", "creer_parcelle", arguments)
        assert verdict.commande is not None
        assert verdict.commande.valeurs == {"nom": "Planche Nord"}

    def test_inc018_null_sur_une_modification_de_parcelle(self):
        verdict = _valider(
            "la planche sud a maintenant 6 rangs", OUTIL_MODIFIER_PARCELLE,
            {"parcelle": "Planche Sud", "nb_rangs": 6, "longueur_m": None,
             "est_pepiniere": None, "abri": None, "exposition": None},
        )
        assert verdict.commande is not None
        assert verdict.commande.valeurs["modification"] == "rangs=6"


class TestINC018ChampsFacultatifs:
    """Un champ que le jardinier peut ne pas dire est annoncé tel dans le schéma : sans cela,
    le modèle demande une exposition pour « crée la planche Est » (mesuré, INC-018)."""

    @staticmethod
    def _description(outil: str, propriete: str) -> str:
        proprietes, _ = _proprietes_de(catalogue_outils.outils_par_nom()[outil])
        return proprietes[propriete]["description"]

    def test_inc018_exposition_et_superficie_a_la_creation_sont_facultatives(self):
        assert self._description("creer_parcelle", "exposition").startswith("FACULTATIF. ")
        assert self._description("creer_parcelle", "superficie_m2").startswith("FACULTATIF. ")

    def test_inc018_le_nom_a_creer_ne_l_est_pas(self):
        assert not self._description("creer_parcelle", "nom").startswith("FACULTATIF")
        assert not self._description("supprimer_parcelle", "nom").startswith("FACULTATIF")

    def test_inc018_un_champ_obligatoire_dans_une_forme_ne_l_est_pas_dans_l_outil(self):
        """`culture` est facultative pour le bilan mais obligatoire pour la fiche : l'outil
        `consulter` les réunit, le champ n'est donc pas annoncé facultatif."""
        assert not self._description("afficher", "culture").startswith("FACULTATIF")
        assert self._description("afficher", "date").startswith("FACULTATIF. ")

    def test_inc018_le_marquage_vient_de_obligatoire(self):
        for forme in menu_commandes.FORMES_DICTABLES:
            for argument in forme.arguments:
                if argument.obligatoire:
                    continue
                for outil in catalogue_outils.outils():
                    if forme in outil.formes:
                        propriete = outil.propriete(forme, argument.nom)
                        assert propriete in _proprietes_de(outil)[0]
