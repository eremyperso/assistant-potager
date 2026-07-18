"""
tests/test_coherence_culture_variete_parcelle.py — Non-régression du bug rapporté :

  "j'ai ramassé 2 kilos de tomates cerise, parcelle centrale" (récolte enregistrée
  sur planche-centrale alors que la variété cerise n'a jamais été plantée là,
  sans aucun avertissement) → https://.../US-011 suite.

[Feedback utilisateur] Un premier correctif se contentait d'afficher un
avertissement texte à côté de la parcelle fausse, sans rien changer au
comportement d'enregistrement — insuffisant : si l'utilisateur confirme,
la mauvaise parcelle était quand même sauvegardée. Comportement corrigé :
une incohérence culture/variété↔parcelle fait traiter la parcelle citée
comme si elle n'avait pas été précisée du tout, ce qui redéclenche la
sélection intelligente existante (CA8) — auto-assignation si une seule
parcelle correspond, menu de choix sinon — tout en conservant
l'avertissement dans le récapitulatif final pour expliquer la correction.

Couvre :
  - _build_action_summary affiche l'avertissement de cohérence quand présent
  - _parse_and_save calcule l'avertissement quand culture+variete+parcelle sont
    fournis mais que la combinaison n'a pas d'historique sur la parcelle visée
  - la parcelle incohérente est effectivement remplacée par la bonne (et non
    plus seulement signalée) quand une correspondance unique existe
  - un menu de choix est proposé (pas d'auto-save) quand plusieurs parcelles
    correspondent à la culture/variété réellement recherchée
  - aucun avertissement quand la combinaison est cohérente avec l'historique
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.models import Parcelle, Evenement
from bot import _build_action_summary


# ── _build_action_summary — rendu de l'avertissement ────────────────────────────

def test_summary_affiche_avertissement_coherence():
    items = [{
        "action": "recolte", "culture": "tomate", "variete": "cerise",
        "quantite": 2, "unite": "kg", "parcelle": "planche-centrale",
        "_avertissement_coherence": "⚠️ Aucune trace de *tomate cerise* sur *planche-centrale*.",
    }]
    summary = _build_action_summary(items)
    assert "Aucune trace de" in summary
    assert "tomate cerise" in summary
    assert "C'est correct ?" in summary


def test_summary_sans_avertissement_si_absent():
    items = [{"action": "recolte", "culture": "tomate", "variete": "coeur de boeuf",
              "quantite": 2, "unite": "kg", "parcelle": "planche-centrale"}]
    summary = _build_action_summary(items)
    assert "Aucune trace de" not in summary


# ── _parse_and_save — calcul de l'avertissement ──────────────────────────────────

def _make_update(user_id: int = 1):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    return update


@pytest.fixture
def db_potager_type(test_db):
    """2 parcelles ; tomate coeur de boeuf + noire de crimée sur centrale,
    tomate cerise sur ombre — reproduit exactement le potager du bug rapporté."""
    centrale = Parcelle(nom="planche-centrale", nom_normalise="planchecentrale", ordre=1, actif=True)
    ombre    = Parcelle(nom="planche-ombre",    nom_normalise="plancheombre",    ordre=2, actif=True)
    test_db.add(centrale)
    test_db.add(ombre)
    test_db.commit()

    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="coeur de boeuf",
                           quantite=2, unite="plants", parcelle_id=centrale.id))
    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="noire de crimee",
                           quantite=2, unite="plants", parcelle_id=centrale.id))
    test_db.add(Evenement(type_action="plantation", culture="tomate", variete="cerise",
                           quantite=3, unite="plants", parcelle_id=ombre.id))
    test_db.commit()
    return test_db


@pytest.mark.asyncio
async def test_recolte_variete_hors_parcelle_declenche_avertissement(db_potager_type):
    """[Bug rapporté] variete='cerise' + parcelle='centrale' → avertissement affiché,
    la variété cerise n'ayant d'historique que sur planche-ombre."""
    update = _make_update()
    parsed_item = {
        "action": "recolte", "culture": "tomate", "variete": "cerise",
        "quantite": 2, "unite": "kg", "parcelle": "centrale",
    }

    import bot as bot_module
    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.SessionLocal", return_value=db_potager_type),
    ):
        bot_module._ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "j'ai ramassé 2 kilos de tomates cerise, parcelle centrale")

    assert update.message.reply_text.called
    text_sent = update.message.reply_text.call_args[0][0]
    assert "Aucune trace de" in text_sent
    assert "tomate cerise" in text_sent
    assert "planche-ombre" in text_sent   # indique où la variété existe réellement

    # [Comportement corrigé] La parcelle enregistrée doit être la bonne (planche-ombre,
    # seule correspondance connue), pas celle fournie à tort (centrale) — auto-corrigée
    # silencieusement via CA8 puisqu'une seule parcelle correspond à tomate/cerise.
    assert "Parcelle : *planche-ombre*" in text_sent
    assert "Parcelle : *centrale*" not in text_sent
    bot_module._ACTION_PENDING.pop(1, None)


@pytest.mark.asyncio
async def test_recolte_variete_hors_parcelle_plusieurs_candidates_propose_menu(db_potager_type):
    """Si la variété citée n'a pas d'historique sur la parcelle indiquée mais existe
    sur PLUSIEURS autres parcelles, un menu de choix est proposé — la mauvaise
    parcelle n'est jamais auto-confirmée par défaut, et aucune des deux n'est
    choisie arbitrairement à sa place."""
    from database.models import Parcelle, Evenement
    fond = Parcelle(nom="planche-fond", nom_normalise="planchefond", ordre=3, actif=True)
    db_potager_type.add(fond)
    db_potager_type.commit()
    # La variété cerise existe maintenant sur DEUX parcelles (ombre + fond)
    db_potager_type.add(Evenement(type_action="plantation", culture="tomate", variete="cerise",
                                   quantite=2, unite="plants", parcelle_id=fond.id))
    db_potager_type.commit()

    update = _make_update()
    parsed_item = {
        "action": "recolte", "culture": "tomate", "variete": "cerise",
        "quantite": 2, "unite": "kg", "parcelle": "centrale",   # ← incohérent (cerise n'y est pas)
    }

    import bot as bot_module
    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.SessionLocal", return_value=db_potager_type),
    ):
        bot_module._ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "j'ai ramassé 2 kilos de tomates cerise, parcelle centrale")

    # Deux parcelles (ombre, fond) portent la cerise → menu de sélection, pas d'auto-save
    assert update.message.reply_text.called
    text_sent = update.message.reply_text.call_args[0][0]
    assert "quelle parcelle" in text_sent.lower()
    assert "Parcelle : *planche-centrale*" not in text_sent
    bot_module._ACTION_PENDING.pop(1, None)


@pytest.mark.asyncio
async def test_recolte_variete_coherente_pas_avertissement(db_potager_type):
    """Même culture/parcelle mais variété réellement plantée là → pas d'avertissement."""
    update = _make_update()
    parsed_item = {
        "action": "recolte", "culture": "tomate", "variete": "coeur de boeuf",
        "quantite": 2, "unite": "kg", "parcelle": "centrale",
    }

    import bot as bot_module
    with (
        patch("bot.parse_commande", return_value=[parsed_item]),
        patch("bot._normalize_items", return_value=[parsed_item]),
        patch("bot.SessionLocal", return_value=db_potager_type),
    ):
        bot_module._ACTION_PENDING.pop(1, None)
        await bot_module._parse_and_save(update, "j'ai ramassé 2 kilos de tomates coeur de boeuf, parcelle centrale")

    text_sent = update.message.reply_text.call_args[0][0]
    assert "Aucune trace de" not in text_sent
    bot_module._ACTION_PENDING.pop(1, None)
