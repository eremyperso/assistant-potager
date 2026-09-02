"""
tests/test_questions_localisation.py
« Où est-ce que ça pousse ? » — les deux questions de localisation que le
catalogue de réponses chiffrées (US-096) ne savait pas lire, alors que
l'association parcelle ↔ culture était déjà acquise (celle de /plan) :

  • « quelles parcelles contiennent des solanacées ? » — par famille botanique
    (référentiel US-067/US-166) ;
  • « sur quelles parcelles je trouve des tomates ? » — par culture, soit la
    question INVERSE d'`occupation_parcelle`.

Constat en usage réel le 02/09/2026 : les deux étaient bien classées
QUESTION_DATA, aucune famille du catalogue ne les reconnaissait, et l'agent SQL
(US-012) les servait avec un « Top cultures — observation » pour la première et
un « Historique observation de tomate » pour la seconde. Deux réponses exactes,
hors sujet, et assez assurées pour que la cascade d'US-093 ne remonte pas d'un
étage — la même cause de fond dans les deux cas : `INTENT_PROMPT` choisit dans
un vocabulaire FERMÉ de gestes et en rend donc toujours un, même quand la
question n'en cite aucun.

Trois corrections, donc trois parties :
  1. chacune des deux questions a désormais sa famille au catalogue ;
  2. les deux sont servies sans aucun appel modèle ;
  3. l'agent SQL écarte un geste que la question ne cite pas partout où ce
     geste dicte la FORME de la réponse — le classement de cultures ET
     l'historique d'un geste, pas seulement le chemin signalé en premier. Là où
     le geste désigne seulement QUEL chiffre est demandé (« Total fraise ? »),
     l'inférence du modèle reste retenue : la couper casserait des questions qui
     marchent.
"""
from datetime import datetime
from unittest.mock import patch

import pytest

from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from database.models import CultureConfig, Evenement, FamilleBotanique, Parcelle
from llm import sql_agent

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
ANNEE = datetime.now().year


@pytest.fixture
def potager(test_db):
    """Deux familles renseignées, trois parcelles, et une culture volontairement
    laissée SANS famille (la courgette) — le référentiel est incomplet dans la
    vraie vie, le jeu de test doit l'être aussi."""
    solanacee = FamilleBotanique(nom="Solanacée", nom_normalise="solanacee",
                                 nom_scientifique="Solanaceae", delai_retour_annees=4)
    alliacee = FamilleBotanique(nom="Alliacée", nom_normalise="alliacee", delai_retour_annees=3)
    test_db.add_all([solanacee, alliacee])
    test_db.commit()

    test_db.add_all([
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur",
                      potager_id=None, famille_id=solanacee.id),
        CultureConfig(nom="poivron", type_organe_recolte="reproducteur",
                      potager_id=None, famille_id=solanacee.id),
        CultureConfig(nom="oignon", type_organe_recolte="végétatif",
                      potager_id=None, famille_id=alliacee.id),
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur", potager_id=None),
    ])
    nord = Parcelle(nom="NORD", nom_normalise="nord", potager_id=1, actif=True, est_pepiniere=False)
    sud = Parcelle(nom="SUD", nom_normalise="sud", potager_id=1, actif=True, est_pepiniere=False)
    ouest = Parcelle(nom="OUEST", nom_normalise="ouest", potager_id=1, actif=True, est_pepiniere=False)
    test_db.add_all([nord, sud, ouest])
    test_db.commit()

    test_db.add_all([
        Evenement(date=datetime(ANNEE, 5, 1), type_action="plantation", culture="tomate",
                  quantite=6, unite="plants", potager_id=1, parcelle_id=nord.id),
        Evenement(date=datetime(ANNEE, 5, 2), type_action="plantation", culture="poivron",
                  quantite=4, unite="plants", potager_id=1, parcelle_id=nord.id),
        Evenement(date=datetime(ANNEE, 5, 3), type_action="plantation", culture="tomate",
                  quantite=3, unite="plants", potager_id=1, parcelle_id=sud.id),
        Evenement(date=datetime(ANNEE, 5, 4), type_action="plantation", culture="oignon",
                  quantite=20, unite="plants", potager_id=1, parcelle_id=ouest.id),
        Evenement(date=datetime(ANNEE, 5, 5), type_action="plantation", culture="courgette",
                  quantite=2, unite="plants", potager_id=1, parcelle_id=ouest.id),
    ])
    test_db.commit()
    return test_db


@pytest.fixture(autouse=True)
def _aucun_appel_modele():
    """La question doit se résoudre à zéro jeton : un appel modèle est un échec."""
    with patch("llm.passerelle.appeler_chat", side_effect=AssertionError(
        "un appel au modèle a eu lieu pour une question chiffrée"
    )):
        yield


# ═════════════════════════════════════════════════════════════════════════════
# La famille du catalogue — reconnaissance
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("question", [
    "quels sont mes parcelles contenant des familles de solanacées ?",  # la question réelle
    "quelles parcelles contiennent des solanacées ?",
    "où sont mes solanacées",                       # sans parcelle citée, sans ponctuation
    "mes parcelles avec des solanacées",
    "quelles planches portent des Solanaceae ?",    # nom scientifique
    "dans quelle parcelle j'ai des solanacée",      # singulier dicté
])
def test_question_famille_botanique_reconnue(potager, question):
    """La question s'identifie à la famille RÉSOLUE contre le référentiel, pas à
    sa grammaire — la dictée ne produit ni accord ni ponctuation fiables."""
    assert rc.reconnait_famille(CTX, question, db=potager) == "parcelles_par_famille"


@pytest.mark.parametrize("question", [
    "pourquoi mes solanacées attrapent le mildiou sur la parcelle NORD ?",
    "faut-il pailler les solanacées ?",
    "comment protéger les solanacées dans mes parcelles ?",
])
def test_savoir_sur_une_famille_rend_la_main(potager, question):
    """Une question de savoir qui cite une famille n'attend pas un inventaire de
    parcelles : elle rend la main à la cascade."""
    assert rc.reconnait_famille(CTX, question, db=potager) != "parcelles_par_famille"


def test_famille_precise_prioritaire(potager):
    """« quand ai-je planté des solanacées ? » cite une famille mais demande une
    date : la famille précise passe avant."""
    assert rc.reconnait_famille(
        CTX, "quand ai-je planté des solanacées ?", db=potager
    ) == "derniere_occurrence"


# ═════════════════════════════════════════════════════════════════════════════
# La réponse — exacte, groupée par parcelle, sans appel modèle
# ═════════════════════════════════════════════════════════════════════════════
def test_reponse_liste_les_parcelles_et_leurs_cultures(potager):
    reponse = rc.repondre_chiffre(
        CTX, "quels sont mes parcelles contenant des familles de solanacées ?", db=potager
    )
    assert reponse is not None
    assert reponse.famille == "parcelles_par_famille"
    assert reponse.present is True
    assert "2 parcelle(s)" in reponse.texte
    assert "NORD" in reponse.texte and "SUD" in reponse.texte
    assert "tomate" in reponse.texte and "poivron" in reponse.texte
    # La parcelle qui ne porte que des cultures d'une AUTRE famille n'y est pas.
    assert "OUEST" not in reponse.texte
    assert "oignon" not in reponse.texte
    # Et surtout : plus jamais le classement hors sujet qui a motivé ce fichier.
    assert "Top cultures" not in reponse.texte


def test_famille_rattachee_mais_absente_des_parcelles_est_une_reponse(potager):
    """CA7 — « aucune parcelle » est une réponse chiffrée légitime dès lors que
    le référentiel SAIT quelles cultures relèvent de la famille."""
    potager.query(Evenement).filter(Evenement.culture == "oignon").delete()
    potager.commit()

    reponse = rc.repondre_chiffre(CTX, "quelles parcelles ont des alliacées ?", db=potager)
    assert reponse is not None
    assert reponse.present is True
    assert "Aucune parcelle" in reponse.texte
    assert "oignon" in reponse.texte      # ce que la famille recouvre, pour lever le doute


def test_famille_sans_culture_rattachee_rend_la_main(potager):
    """CA7/CA8 — le silence du référentiel ne se présente jamais comme un
    constat : sans aucune culture rattachée, la réponse n'est pas confiante et
    la cascade remonte d'un étage."""
    potager.add(FamilleBotanique(nom="Poacée", nom_normalise="poacee"))
    potager.commit()

    reponse = rc.repondre_chiffre(CTX, "quelles parcelles portent des poacées ?", db=potager)
    assert reponse is not None
    assert reponse.present is False
    assert "Aucune fiche culture" in reponse.texte


def test_isolation_par_potager(potager):
    """L'occupation est celle du potager courant — le voisin ne voit rien."""
    voisin = TenantContext(user_id=2, potager_id=2, role="owner")
    reponse = rc.repondre_chiffre(CTX, "quelles parcelles ont des solanacées ?", db=potager)
    reponse_voisin = rc.repondre_chiffre(voisin, "quelles parcelles ont des solanacées ?", db=potager)
    assert "NORD" in reponse.texte
    assert "NORD" not in reponse_voisin.texte


def test_rejeu_depuis_le_cache_recalcule_la_bonne_famille(potager):
    """[US-095] La famille botanique est redérivée de la phrase vivante, comme
    l'action et la période : une seule entrée de cache sert « solanacées » et
    « alliacées » sans jamais servir la réponse de l'une à l'autre."""
    reconnue = rc.reconnaitre(CTX, "quelles parcelles ont des solanacées ?", db=potager)
    assert reconnue is not None
    aiguillage = rc.aiguillage_de(*reconnue)

    servie = rc.servir_aiguillage(CTX, aiguillage, "quelles parcelles ont des alliacées ?", db=potager)
    assert servie is not None
    assert "OUEST" in servie.texte and "oignon" in servie.texte
    assert "tomate" not in servie.texte


# ═════════════════════════════════════════════════════════════════════════════
# Par culture — la question INVERSE d'`occupation_parcelle`
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("question", [
    "sur quelles parcelles je trouve des tomates ?",   # la question réelle
    "où sont mes tomates",
    "où est ma tomate ?",
    "dans quelle parcelle j'ai des tomates",
    "mes parcelles avec des tomates",
    "où poussent mes tomates ?",
])
def test_question_localisation_culture_reconnue(potager, question):
    """L'association parcelle ↔ culture était déjà acquise (c'est celle de /plan) :
    il ne manquait que de savoir la lire dans ce sens."""
    assert rc.reconnait_famille(CTX, question, db=potager) == "parcelles_par_culture"


def test_localisation_ne_vole_pas_l_inventaire_de_parcelle(potager):
    """Le motif reste étroit : une question qui nomme une parcelle et demande
    ce qu'il y a dessus reste servie par `occupation_parcelle`."""
    assert rc.reconnait_famille(
        CTX, "qu'est-ce qu'il y a dans la parcelle NORD ?", db=potager
    ) == "occupation_parcelle"


def test_localisation_ne_vole_pas_le_rendement(potager):
    """« où EN sont mes tomates ? » demande un rendement, pas un emplacement —
    une lettre sépare les deux questions, et la famille précise passe avant."""
    assert rc.reconnait_famille(CTX, "où en sont mes tomates ?", db=potager) == "rendement_saison"


def test_reponse_liste_les_parcelles_de_la_culture(potager):
    reponse = rc.repondre_chiffre(
        CTX, "sur quelles parcelles je trouve des tomates ?", db=potager
    )
    assert reponse is not None
    assert reponse.famille == "parcelles_par_culture"
    assert reponse.present is True
    assert "2 parcelle(s)" in reponse.texte
    assert "NORD" in reponse.texte and "SUD" in reponse.texte
    assert "6" in reponse.texte and "3" in reponse.texte      # les quantités du plan
    assert "OUEST" not in reponse.texte                       # l'oignon n'y est pour rien
    # Et surtout : plus jamais l'historique d'un geste que personne n'a demandé.
    assert "observation" not in reponse.texte.lower()


def test_culture_connue_mais_nulle_part_en_place(potager):
    """CA7 — « aucune parcelle » est ici un constat EXACT tiré du plan, pas une
    absence de donnée : la réponse reste confiante et la cascade ne remonte pas
    payer un modèle pour redire la même chose."""
    potager.add(CultureConfig(nom="aubergine", type_organe_recolte="reproducteur", potager_id=None))
    potager.commit()

    reponse = rc.repondre_chiffre(CTX, "où sont mes aubergines ?", db=potager)
    assert reponse is not None
    assert reponse.present is True
    assert "aucune parcelle" in reponse.texte.lower()


def test_localisation_isolee_par_potager(potager):
    voisin = TenantContext(user_id=2, potager_id=2, role="owner")
    reponse_voisin = rc.repondre_chiffre(voisin, "où sont mes tomates ?", db=potager)
    # Le voisin ne partage ni les parcelles ni les plants — seule la fiche
    # culture globale lui est visible, et elle ne dit rien d'un emplacement.
    assert reponse_voisin is None or "NORD" not in reponse_voisin.texte


# ═════════════════════════════════════════════════════════════════════════════
# L'agent SQL — plus de classement pour un geste que la question ne cite pas
# ═════════════════════════════════════════════════════════════════════════════
def test_agent_sql_refuse_un_geste_non_cite(potager):
    """Le défaut de fond : l'extraction d'intention choisit dans un vocabulaire
    fermé et rend TOUJOURS un geste. Servir un classement sur un geste absent de
    la question produisait une réponse exacte et hors sujet, assez assurée pour
    bloquer la cascade."""
    intent = {"action": "observation", "culture": None, "query_type": "stats"}
    texte, confiant = sql_agent.QueryAgent(potager, potager_id=1).answer_avec_confiance(
        "quels sont mes parcelles contenant des familles de solanacées ?", intent
    )
    assert confiant is False
    assert "Top cultures" not in texte


def test_agent_sql_sert_toujours_un_geste_cite(potager):
    """…sans pour autant casser le classement quand le geste EST cité."""
    potager.add(Evenement(date=datetime(ANNEE, 7, 1), type_action="recolte",
                          culture="tomate", quantite=2, unite="kg", potager_id=1))
    potager.commit()

    intent = {"action": "recolte", "culture": None, "query_type": "stats"}
    texte, confiant = sql_agent.QueryAgent(potager, potager_id=1).answer_avec_confiance(
        "quels légumes ai-je le plus récoltés ?", intent
    )
    assert confiant is True
    assert "Top cultures" in texte


def test_agent_sql_ecarte_le_geste_non_cite_de_l_historique(potager):
    """Le garde ne vaut pas que pour le classement : « sur quelles parcelles je
    trouve des tomates ? » arrivait avec `action="observation"` ET la bonne
    culture, donc par le chemin de l'historique — et rendait « Historique
    observation de tomate »."""
    potager.add(Evenement(date=datetime(ANNEE, 7, 24), type_action="observation",
                          culture="tomate", potager_id=1))
    potager.commit()

    intent = {"action": "observation", "culture": "tomate", "query_type": "historique"}
    texte, _ = sql_agent.QueryAgent(potager, potager_id=1).answer_avec_confiance(
        "sur quelles parcelles je trouve des tomates ?", intent
    )
    assert "Historique observation de tomate" not in texte


def test_agent_sql_sert_l_historique_quand_le_geste_est_cite(potager):
    """…et l'historique reste servi quand le geste, lui, est bien dans la
    question."""
    potager.add(Evenement(date=datetime(ANNEE, 7, 24), type_action="observation",
                          culture="tomate", potager_id=1))
    potager.commit()

    intent = {"action": "observation", "culture": "tomate", "query_type": "historique"}
    texte, confiant = sql_agent.QueryAgent(potager, potager_id=1).answer_avec_confiance(
        "mes observations sur les tomates", intent
    )
    assert confiant is True
    assert "observation de tomate" in texte


def test_agent_sql_retient_le_geste_deduit_quand_il_designe_un_chiffre(potager):
    """La limite du garde, et pourquoi elle est là : « Total fraise ? » n'écrit
    aucun synonyme de « récolte », et l'inférence du modèle y est légitime — le
    geste ne dicte pas la forme de la réponse, il désigne quel chiffre est
    demandé. L'écarter casserait des questions qui marchent."""
    potager.add(Evenement(date=datetime(ANNEE, 5, 1), type_action="recolte",
                          culture="tomate", quantite=1.5, unite="kg", potager_id=1))
    potager.commit()

    intent = {"action": "recolte", "culture": "tomate", "query_type": "quantite"}
    texte, confiant = sql_agent.QueryAgent(potager, potager_id=1).answer_avec_confiance(
        "Total tomate ?", intent
    )
    assert confiant is True
    assert "1.5 kg" in texte
