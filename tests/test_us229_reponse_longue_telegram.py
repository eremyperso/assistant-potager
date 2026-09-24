"""
tests/test_us229_reponse_longue_telegram.py
[US-229 / INC-010] Une réponse de savoir peut recopier un fragment tel quel
(CA7 de US-141 : zéro reformulation) au-delà des 4096 caractères que Telegram
accepte sur un `edit_text`/`reply_text`. Sans découpage, `_ask_question`
perdait la réponse trouvée derrière un `❌ Erreur : Message_too_long` (constat
de production du 24/09/2026, question « c'est quoi un rang ? »).

Couverture :
  1. Cas nominal (≤4096) : comportement inchangé, un seul edit_text.
  2. Cas long : premier bloc édité, blocs suivants envoyés en reply_text,
     reconstitution fidèle du texte original.
  3. Régression du bug observé : aucune exception ne remonte au bloc
     `except Exception` englobant.
  4. Les boutons 👍/👎 et « Autre question ou action ? » restent envoyés
     après tous les blocs de la réponse, y compris en cas de découpage.
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from llm import routeur

CTX_PATCH = "app.bot.current_context"


def _make_update():
    update = MagicMock()
    update.effective_user.id = 42
    msg = MagicMock()
    msg.edit_text = AsyncMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock(return_value=msg)
    return update, msg


def _paragraphe(lettre: str, taille: int) -> str:
    """Un « paragraphe » d'une seule ligne, comme une phrase de fiche réelle."""
    return (lettre * taille)


def _textes_reply(update) -> list:
    """Le premier argument positionnel de chaque appel à reply_text."""
    return [appel.args[0] for appel in update.message.reply_text.call_args_list if appel.args]


def _boutons_retour_proposes(update) -> bool:
    for texte in update.message.reply_text.call_args_list:
        markup = texte.kwargs.get("reply_markup")
        if markup is not None and getattr(markup, "inline_keyboard", None):
            callbacks = [b.callback_data for ligne in markup.inline_keyboard for b in ligne]
            if any(cb.startswith("retour_routage:") for cb in callbacks):
                return True
    return False


def _autre_question_proposee(update) -> bool:
    return any("Autre question" in texte for texte in _textes_reply(update))


@pytest.mark.asyncio
async def test_us229_reponse_courte_un_seul_edit_text_inchange():
    """Non-régression : une réponse ≤4096 caractères garde le comportement
    d'avant — un seul edit_text, aucun bloc supplémentaire pour le corps."""
    from app import bot

    update, msg = _make_update()
    reponse = "Une réponse courte de savoir."
    resultat = routeur.ReponseCascade(
        texte=reponse, etage_resolveur=routeur.ETAGE_SAVOIR, routage_log_id=1,
    )

    with (
        patch(CTX_PATCH, return_value=MagicMock()),
        patch("app.bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("app.bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "une question ?")

    assert msg.edit_text.call_count == 1
    assert msg.edit_text.call_args.args[0] == f"🔍 *Réponse :*\n\n{reponse}"
    # Aucun bloc de corps supplémentaire n'est envoyé en reply_text — les
    # seuls reply_text restants sont le message d'attente initial et les
    # invites de fin (boutons, « Autre question »).
    assert not any(reponse in t for t in _textes_reply(update) if t != "🔍 *Analyse de vos données...*")


@pytest.mark.asyncio
async def test_us229_reponse_longue_decoupee_en_blocs_fideles():
    """Une réponse >4096 caractères est éditée sur son premier bloc, puis
    complétée par des reply_text — sans perte ni troncature de contenu."""
    from app import bot
    from app.bot.noyau import _decouper_en_blocs

    update, msg = _make_update()
    # Plusieurs paragraphes réalistes (une ligne chacun), comme une fiche du
    # corpus de connaissance — largement au-delà de 4096 caractères au total.
    paragraphes = [_paragraphe(l, 1200) for l in "ABCDE"]
    reponse = "\n\n".join(paragraphes)
    assert len(f"🔍 *Réponse :*\n\n{reponse}") > 4096

    resultat = routeur.ReponseCascade(
        texte=reponse, etage_resolveur=routeur.ETAGE_SAVOIR, routage_log_id=2,
    )

    with (
        patch(CTX_PATCH, return_value=MagicMock()),
        patch("app.bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("app.bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "une question ?")

    blocs_attendus = _decouper_en_blocs(f"🔍 *Réponse :*\n\n{reponse}")
    assert len(blocs_attendus) > 1, "le texte de test doit forcer un découpage en plusieurs blocs"

    # Un seul edit_text, avec le premier bloc, jamais au-delà de 4096.
    assert msg.edit_text.call_count == 1
    premier_bloc = msg.edit_text.call_args.args[0]
    assert premier_bloc == blocs_attendus[0]
    assert len(premier_bloc) <= 4096

    # Les blocs suivants sont envoyés en reply_text, dans l'ordre, tous ≤4096.
    blocs_envoyes = [t for t in _textes_reply(update) if t in blocs_attendus[1:]]
    assert blocs_envoyes == blocs_attendus[1:]
    assert all(len(b) <= 4096 for b in blocs_envoyes)

    # Reconstitution fidèle : premier bloc + blocs suivants, rejoints par
    # \n, redonne exactement le texte préfixé original (_decouper_en_blocs
    # ne perd ni ne duplique aucune ligne).
    assert "\n".join(blocs_attendus) == f"🔍 *Réponse :*\n\n{reponse}"


@pytest.mark.asyncio
async def test_us229_reponse_tres_longue_ne_leve_pas_message_too_long():
    """Régression du bug observé en production : une réponse de la taille de
    l'ancienne fiche « Compter les rangs occupés... » (6878 caractères) ne
    doit plus jamais remonter au bloc `except Exception` englobant."""
    from app import bot

    update, msg = _make_update()
    paragraphes = [_paragraphe(l, 900) for l in "ABCDEFGH"]  # ~7400 caractères
    reponse = "\n\n".join(paragraphes)
    resultat = routeur.ReponseCascade(
        texte=reponse, etage_resolveur=routeur.ETAGE_SAVOIR, routage_log_id=3,
    )

    with (
        patch(CTX_PATCH, return_value=MagicMock()),
        patch("app.bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("app.bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "c'est quoi un rang ?")

    # L'erreur générique du bloc except englobant ne doit jamais apparaître.
    assert not any("Message_too_long" in t or "❌ Erreur" in t for t in _textes_reply(update))
    assert not any("Message_too_long" in str(appel) for appel in msg.edit_text.call_args_list)


@pytest.mark.asyncio
async def test_us229_boutons_et_relance_apres_tous_les_blocs():
    """Les boutons 👍/👎 et « Autre question ou action ? » restent envoyés
    après la totalité des blocs de réponse, y compris en cas de découpage."""
    from app import bot

    update, msg = _make_update()
    paragraphes = [_paragraphe(l, 1200) for l in "ABCDE"]
    reponse = "\n\n".join(paragraphes)
    resultat = routeur.ReponseCascade(
        texte=reponse, etage_resolveur=routeur.ETAGE_SAVOIR, routage_log_id=4,
    )

    with (
        patch(CTX_PATCH, return_value=MagicMock()),
        patch("app.bot.routeur.repondre_avec_cascade", return_value=resultat),
        patch("app.bot.send_voice_reply", new=AsyncMock()),
    ):
        await bot._ask_question(update, "une question ?")

    assert _boutons_retour_proposes(update)
    assert _autre_question_proposee(update)
