"""
tests/test_us087_bot_rejoindre.py — [US-087] Rejoindre un potager depuis Telegram
avec un code d'invitation
--------------------------------------------------------------------------------
Couvre CA1 (commande enregistrée par le point unique, garde de liaison), CA2 (aide
sans argument), CA3 (`accepter_invitation` réutilisée), CA4 (confirmation), CA5 (un
message par refus), CA6 (potager actif : annoncé ou inchangé), CA7 (casse et
espaces), CA8 (owners liés informés), CA9 (zéro appel Groq) et CA10 (`/help`).
Le handler testé est celui RÉELLEMENT enregistré par `_construire_application` —
garde de liaison compris —, pas un appel direct à `cmd_rejoindre`.

⚠️ Les handlers referment la session (`db.close()`), qui est ici celle du test :
les fixtures exposent donc des identifiants et des codes (valeurs simples), jamais
des instances ORM que le handler détacherait.
"""
import ast
import functools
import inspect
import logging
import textwrap
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import bot as bot_module
from app.bot import _COMMANDES_SANS_GARDE_LIAISON, _construire_application, cmd_help, cmd_rejoindre
from app.services import menu_commandes as svc_menu
from app.services import potager_actif as svc_potager_actif
from app.services import potagers as svc_potagers
from database.models import Evenement, Invitation, Potager, PotagerMembre, User

CHAT = 555


def _creer_user(db, email="jardinier@example.com", **kwargs):
    user = User(email=email, mot_de_passe_hash="x", **kwargs)
    db.add(user)
    db.commit()
    return user


def _membre(db, potager_id, user_id, role):
    db.add(PotagerMembre(user_id=user_id, potager_id=potager_id, role=role))
    db.commit()


def _nb_appartenances(db, user_id):
    return db.query(PotagerMembre).filter(PotagerMembre.user_id == user_id).count()


@functools.lru_cache(maxsize=None)
def _handler_enregistre():
    """Le callback réellement enregistré pour `/rejoindre`, garde de liaison compris.
    (Mis en cache : construire l'Application PTB à chaque test coûterait ~0,5 s pièce.)"""
    app = _construire_application()
    for handlers in app.handlers.values():
        for h in handlers:
            if h.__class__.__name__ == "CommandHandler" and "rejoindre" in h.commands:
                return h.callback
    raise AssertionError("/rejoindre n'est pas enregistrée")


@functools.lru_cache(maxsize=None)
def _noms_commandes_enregistrees():
    app = _construire_application()
    return {nom for handlers in app.handlers.values() for h in handlers
            if h.__class__.__name__ == "CommandHandler" for nom in h.commands}


def _update(chat_id=CHAT):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


def _tg_ctx(*args):
    tg = MagicMock()
    tg.args = list(args)
    tg.user_data = {}
    return tg


async def _rejoindre(test_db, *args, chat_id=CHAT):
    """Envoie `/rejoindre <args>` ; retourne (texte de la première réponse, update)."""
    update = _update(chat_id)
    with patch("app.bot.SessionLocal", return_value=test_db):
        await _handler_enregistre()(update, _tg_ctx(*args))
    reponses = [c[0][0] for c in update.message.reply_text.call_args_list]
    return (reponses[0] if reponses else None), update


@pytest.fixture
def envois(monkeypatch):
    """Capture les messages Telegram sortants (notifications aux owners)."""
    recus = []
    monkeypatch.setattr(
        "app.services.telegram_notify.envoyer_message",
        lambda chat_id, texte: recus.append((chat_id, texte)) or True,
    )
    return recus


@pytest.fixture
def lilas(test_db):
    """« Jardin des Lilas », owner Emmanuel (lié à Telegram, chat 111) ; invitée : Camille,
    liée (chat 555), sans aucun potager."""
    owner = _creer_user(test_db, email="owner@example.com", nom="Emmanuel", telegram_chat_id=111)
    potager = svc_potagers.creer_potager(test_db, owner.id, "Jardin des Lilas")
    invitee = _creer_user(test_db, email="camille@example.com", nom="Camille", telegram_chat_id=CHAT)
    return SimpleNamespace(owner_id=owner.id, potager_id=potager.id, invitee_id=invitee.id)


def _inviter(test_db, lilas, role="editor"):
    """Crée une invitation et retourne son CODE (valeur simple)."""
    return svc_potagers.creer_invitation(test_db, lilas.owner_id, lilas.potager_id, role).code


def _modifier_invitation(test_db, code, **champs):
    test_db.query(Invitation).filter(Invitation.code == code).update(champs)
    test_db.commit()


# ── CA1 — Enregistrement unique et garde de liaison standard ────────────────

def test_ca1_rejoindre_est_enregistree_par_le_point_unique_avec_le_garde_de_liaison():
    callback = _handler_enregistre()
    assert getattr(callback, "_garde_liaison", False) is True
    assert "rejoindre" not in _COMMANDES_SANS_GARDE_LIAISON


@pytest.mark.asyncio
async def test_ca1_chat_non_lie_renvoye_vers_la_liaison_sans_rattachement(test_db, lilas):
    """Scénario Gherkin « Chat non lié »."""
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code, chat_id=999)  # chat 999 : lié à personne

    assert "pas encore relié" in texte
    assert _nb_appartenances(test_db, lilas.invitee_id) == 0
    assert test_db.query(Invitation).filter(Invitation.code == code).first().utilisee_le is None


@pytest.mark.asyncio
async def test_ca1_un_utilisateur_lie_sans_aucun_potager_n_est_pas_bloque_par_le_garde(test_db, lilas, envois):
    """Le garde standard répondrait « vous n'êtes membre d'aucun potager » à celui qui
    utilise justement /rejoindre pour en obtenir un : la liaison suffit."""
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code)

    assert "Tu as rejoint" in texte
    assert "aucun potager" not in texte


@pytest.mark.asyncio
async def test_ca1_les_autres_commandes_restent_bloquees_sans_potager(test_db, lilas):
    """Non-régression US-046/CA5 : l'exception ne vaut que pour /rejoindre."""
    app = _construire_application()
    plan = next(h.callback for hs in app.handlers.values() for h in hs
                if h.__class__.__name__ == "CommandHandler" and "plan" in h.commands)
    update = _update()

    with patch("app.bot.SessionLocal", return_value=test_db):
        await plan(update, _tg_ctx())

    assert "aucun potager" in update.message.reply_text.call_args[0][0].lower()


# ── CA2 — Sans argument : l'aide ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ca2_sans_argument_le_bot_explique_le_format_et_ou_trouver_le_code(test_db, lilas):
    """Scénario Gherkin « Commande sans argument »."""
    texte, update = await _rejoindre(test_db)

    assert "/rejoindre VOTRECODE" in texte
    assert "8 caractères" in texte
    assert "ton hôte le génère depuis l'application web" in texte
    assert update.message.reply_text.await_count == 1
    assert _nb_appartenances(test_db, lilas.invitee_id) == 0


# ── CA3, CA4 — Un code valide rattache, avec le rôle prévu ──────────────────

@pytest.mark.asyncio
async def test_ca3_ca4_un_code_valide_rattache_avec_le_role_prevu_et_le_dit(test_db, lilas, envois):
    """Scénario Gherkin « Rejoindre un potager depuis Telegram »."""
    code = _inviter(test_db, lilas, "editor")

    texte, _ = await _rejoindre(test_db, code)

    assert texte.startswith("✅ Tu as rejoint *Jardin des Lilas* en tant qu'éditeur.")
    assert svc_potager_actif.role_utilisateur(test_db, lilas.invitee_id, lilas.potager_id) == "editor"


@pytest.mark.asyncio
async def test_ca4_le_role_lecteur_se_dit_en_francais_courant(test_db, lilas, envois):
    code = _inviter(test_db, lilas, "lecteur")

    texte, _ = await _rejoindre(test_db, code)

    assert "en tant que lecteur" in texte


@pytest.mark.asyncio
async def test_ca3_le_code_est_consomme_une_seule_fois(test_db, lilas, envois):
    code = _inviter(test_db, lilas)

    await _rejoindre(test_db, code)
    second, _ = await _rejoindre(test_db, code)

    assert "déjà été utilisé" in second
    assert _nb_appartenances(test_db, lilas.invitee_id) == 1


def test_ca3_aucune_regle_de_validation_n_est_dupliquee(test_db, lilas, monkeypatch, envois):
    """Le service délègue à `accepter_invitation` — c'est elle qui décide de la validité."""
    appels = []
    original = svc_potagers.accepter_invitation
    monkeypatch.setattr(
        svc_potagers, "accepter_invitation",
        lambda db, user_id, code: appels.append(code) or original(db, user_id, code),
    )
    code = _inviter(test_db, lilas)

    svc_potagers.rejoindre_potager(test_db, lilas.invitee_id, code)

    assert appels == [code]


# ── CA5 — Chaque refus a son propre message ─────────────────────────────────

@pytest.mark.asyncio
async def test_ca5_code_inconnu(test_db, lilas):
    texte, _ = await _rejoindre(test_db, "ZZZZZZZZ")

    assert "inconnu" in texte
    assert "Traceback" not in texte and "Error" not in texte
    assert _nb_appartenances(test_db, lilas.invitee_id) == 0


@pytest.mark.asyncio
async def test_ca5_code_expire_aucune_appartenance_creee(test_db, lilas):
    """Scénario Gherkin « Code expiré »."""
    code = _inviter(test_db, lilas)
    _modifier_invitation(test_db, code, expire_le=datetime.utcnow() - timedelta(days=1))

    texte, _ = await _rejoindre(test_db, code)

    assert "expiré" in texte and "nouveau" in texte
    assert _nb_appartenances(test_db, lilas.invitee_id) == 0


@pytest.mark.asyncio
async def test_ca5_code_deja_utilise(test_db, lilas):
    code = _inviter(test_db, lilas)
    _modifier_invitation(test_db, code, utilisee_le=datetime.utcnow())

    texte, _ = await _rejoindre(test_db, code)

    assert "déjà été utilisé" in texte
    assert _nb_appartenances(test_db, lilas.invitee_id) == 0


@pytest.mark.asyncio
async def test_ca5_deja_membre_de_ce_potager(test_db, lilas):
    _membre(test_db, lilas.potager_id, lilas.invitee_id, "lecteur")
    code = _inviter(test_db, lilas, "editor")

    texte, _ = await _rejoindre(test_db, code)

    assert "déjà membre" in texte
    # Le rôle existant n'est pas écrasé par celui de l'invitation.
    assert svc_potager_actif.role_utilisateur(test_db, lilas.invitee_id, lilas.potager_id) == "lecteur"


@pytest.mark.asyncio
async def test_ca5_les_quatre_refus_ont_quatre_messages_distincts(test_db, lilas):
    inconnu, _ = await _rejoindre(test_db, "ZZZZZZZZ")
    code_expire = _inviter(test_db, lilas)
    _modifier_invitation(test_db, code_expire, expire_le=datetime.utcnow() - timedelta(days=1))
    code_utilise = _inviter(test_db, lilas)
    _modifier_invitation(test_db, code_utilise, utilisee_le=datetime.utcnow())
    expire, _ = await _rejoindre(test_db, code_expire)
    utilise, _ = await _rejoindre(test_db, code_utilise)
    _membre(test_db, lilas.potager_id, lilas.invitee_id, "lecteur")
    deja, _ = await _rejoindre(test_db, _inviter(test_db, lilas))

    assert len({inconnu, expire, utilise, deja}) == 4


# ── CA6 — Potager actif : annoncé, ou inchangé avec le rappel de /potager ───

@pytest.mark.asyncio
async def test_ca6_premier_potager_rejoint_devient_le_potager_actif(test_db, lilas, envois):
    """Scénario Gherkin « Premier potager rejoint »."""
    code = _inviter(test_db, lilas, "editor")

    texte, _ = await _rejoindre(test_db, code)

    assert test_db.query(User).filter(User.id == lilas.invitee_id).first().potager_actif_id == lilas.potager_id
    assert "C'est maintenant ton potager actif" in texte
    assert "saisir tes événements" in texte


@pytest.mark.asyncio
async def test_ca6_un_lecteur_ne_se_voit_pas_promettre_la_saisie(test_db, lilas, envois):
    code = _inviter(test_db, lilas, "lecteur")

    texte, _ = await _rejoindre(test_db, code)

    assert "potager actif" in texte
    assert "saisir tes événements" not in texte
    assert "sans y enregistrer d'événement" in texte


@pytest.mark.asyncio
async def test_ca6_un_potager_actif_existant_n_est_pas_modifie(test_db, lilas, envois):
    """Scénario Gherkin « Utilisateur ayant déjà un potager actif »."""
    vitry = svc_potagers.creer_potager(test_db, lilas.invitee_id, "Jardin de Vitry")
    vitry_id = vitry.id
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code)

    assert test_db.query(User).filter(User.id == lilas.invitee_id).first().potager_actif_id == vitry_id
    assert "Ton potager actif reste *Jardin de Vitry*" in texte
    assert "/potager" in texte
    assert "C'est maintenant ton potager actif" not in texte


@pytest.mark.asyncio
async def test_ca6_le_potager_par_defaut_transitoire_n_est_pas_ecrase(test_db, lilas, envois):
    """Plusieurs potagers, aucun choix persisté : `resoudre_tenant_context` en retient un
    par défaut, non persisté. `accepter_invitation` verrait `potager_actif_id` NULL et
    rendrait actif le potager rejoint : ce serait une bascule silencieuse."""
    nord = Potager(nom="Jardin Nord", proprietaire_id=lilas.invitee_id)
    sud = Potager(nom="Jardin Sud", proprietaire_id=lilas.invitee_id)
    test_db.add_all([nord, sud])
    test_db.commit()
    _membre(test_db, nord.id, lilas.invitee_id, "owner")
    _membre(test_db, sud.id, lilas.invitee_id, "owner")
    assert test_db.query(User).filter(User.id == lilas.invitee_id).first().potager_actif_id is None
    par_defaut = svc_potager_actif.resoudre_tenant_context(test_db, lilas.invitee_id).potager_id
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, lilas.invitee_id)
    assert ctx.potager_id == par_defaut != lilas.potager_id
    assert "Ton potager actif reste" in texte


# ── CA7 — Casse et espaces parasites ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ca7_le_code_est_accepte_quelle_que_soit_sa_casse(test_db, lilas, envois):
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code.lower())

    assert "Tu as rejoint" in texte


@pytest.mark.asyncio
async def test_ca7_les_espaces_parasites_en_debut_et_fin_sont_ignores(test_db, lilas, envois):
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, f"  {code.lower()}  ")

    assert "Tu as rejoint" in texte


@pytest.mark.asyncio
async def test_ca7_seul_le_premier_mot_est_pris_pour_le_code(test_db, lilas, envois):
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code, "merci", "beaucoup")

    assert "Tu as rejoint" in texte


# ── CA8 — Les owners liés à Telegram sont informés ──────────────────────────

@pytest.mark.asyncio
async def test_ca8_les_owners_lies_a_telegram_sont_informes_de_l_arrivee(test_db, lilas, envois):
    second_owner = _creer_user(test_db, email="owner2@example.com", telegram_chat_id=222)
    _membre(test_db, lilas.potager_id, second_owner.id, "owner")
    editeur = _creer_user(test_db, email="editor@example.com", telegram_chat_id=333)
    _membre(test_db, lilas.potager_id, editeur.id, "editor")  # simple éditeur : hors diffusion
    code = _inviter(test_db, lilas, "editor")

    await _rejoindre(test_db, code)

    assert sorted(chat for chat, _ in envois) == [111, 222]
    texte = envois[0][1]
    assert "Camille a rejoint le potager « Jardin des Lilas »" in texte
    assert "Rôle : éditeur" in texte


@pytest.mark.asyncio
async def test_ca8_aucun_owner_lie_aucun_envoi_et_l_adhesion_reussit(test_db, lilas, monkeypatch):
    test_db.query(User).filter(User.id == lilas.owner_id).update({"telegram_chat_id": None})
    test_db.commit()

    def _interdit(*a, **kw):
        raise AssertionError("aucun owner lié : pas d'envoi")

    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", _interdit)
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code)

    assert "Tu as rejoint" in texte


@pytest.mark.asyncio
async def test_ca8_une_panne_telegram_ne_fait_pas_echouer_l_adhesion(test_db, lilas, monkeypatch):
    monkeypatch.setattr("app.services.telegram_notify.envoyer_message", lambda *a, **kw: False)
    code = _inviter(test_db, lilas)

    texte, _ = await _rejoindre(test_db, code)

    assert "Tu as rejoint" in texte


@pytest.mark.asyncio
async def test_ca8_un_refus_ne_notifie_personne(test_db, lilas, envois):
    await _rejoindre(test_db, "ZZZZZZZZ")
    assert envois == []


# ── CA9 — Zéro appel Groq ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ca9_aucune_classification_d_intention_ni_appel_de_modele(test_db, lilas, envois):
    code = _inviter(test_db, lilas)
    with patch("app.bot.classify_intent", side_effect=AssertionError("classification interdite")), \
         patch("app.bot.handle_text", side_effect=AssertionError("flux des messages libres interdit")):
        texte, _ = await _rejoindre(test_db, code)

    assert "Tu as rejoint" in texte


def _identifiants(objet) -> set[str]:
    """Noms et attributs réellement utilisés par le code d'une fonction (docstrings et
    commentaires exclus : un commentaire « aucun appel Groq » n'est pas un appel)."""
    arbre = ast.parse(textwrap.dedent(inspect.getsource(objet)))
    noms = set()
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.Name):
            noms.add(noeud.id.lower())
        elif isinstance(noeud, ast.Attribute):
            noms.add(noeud.attr.lower())
    return noms


def test_ca9_le_handler_et_le_service_ne_referencent_aucun_modele():
    for objet in (cmd_rejoindre, svc_potagers.rejoindre_potager, bot_module.liaison._message_potager_rejoint):
        for nom in _identifiants(objet):
            assert not any(mot in nom for mot in ("groq", "passerelle", "classify_intent")), (objet.__name__, nom)


def test_ca9_la_commande_passe_par_un_commandhandler_pas_par_le_flux_des_messages_libres():
    """Elle n'interfère pas avec les priorités de `handle_text` / `handle_voice`."""
    assert "rejoindre" in _noms_commandes_enregistrees()


# ── CA10 — /help ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ca10_help_mentionne_rejoindre_dans_la_meme_section_que_potager_et_lier():
    update = MagicMock()
    update.message.reply_text = AsyncMock()
    tg = MagicMock()
    tg.args = []

    await cmd_help(update, tg)

    texte = update.message.reply_text.call_args[0][0]
    section = texte.split("*💡 Aide ciblée par domaine*")[0].split("*⌨️ Commandes*")[1]
    noms = [ligne.split()[0] for ligne in section.splitlines() if ligne.startswith("/")]
    assert {"/lier", "/potager", "/rejoindre"} <= set(noms)
    assert "/rejoindre [code] — Rejoindre un potager avec un code d'invitation" in section


# ── Menu natif (US-171) et interpréteur (US-172) ────────────────────────────

def test_rejoindre_entre_au_menu_natif_avec_une_phrase_d_aide_lisible_a_375px():
    menu = svc_menu.construire_menu({"potager", "rejoindre", "lier", "help"})
    entrees = dict(menu)
    assert "rejoindre" in entrees
    assert len(entrees["rejoindre"]) <= svc_menu.LONGUEUR_MAX_DESCRIPTION
    ordre = [nom for nom, _ in menu]
    assert ordre.index("potager") < ordre.index("rejoindre") < ordre.index("lier")


def test_rejoindre_est_exclue_de_l_interpreteur_sur_decision_motivee():
    assert "rejoindre" in svc_menu.COMMANDES_EXCLUES_INTERPRETEUR
    assert "dicter" in svc_menu.MOTIFS_EXCLUSION_INTERPRETEUR["rejoindre"]
    assert "rejoindre" not in svc_menu.COMMANDES_DICTABLES


def test_la_parite_commandes_interpreteur_reste_sans_anomalie():
    assert svc_menu.controler_parite(_noms_commandes_enregistrees()) == []


# ── Notes techniques — Markdown et confidentialité du code ──────────────────

@pytest.mark.asyncio
async def test_le_nom_du_potager_est_echappe_pour_markdown(test_db, lilas, envois):
    """Non-régression US-007 : un `_` dans le nom ne doit pas casser le Markdown Telegram."""
    test_db.query(Potager).filter(Potager.id == lilas.potager_id).update({"nom": "Jardin_des_Lilas"})
    test_db.commit()
    code = _inviter(test_db, lilas)

    texte, update = await _rejoindre(test_db, code)

    assert "Jardin\\_des\\_Lilas" in texte
    assert update.message.reply_text.call_args[1]["parse_mode"] == "Markdown"


@pytest.mark.asyncio
async def test_le_code_d_invitation_n_est_jamais_journalise(test_db, lilas, envois, caplog):
    code = _inviter(test_db, lilas)
    caplog.set_level(logging.DEBUG)

    await _rejoindre(test_db, code)
    await _rejoindre(test_db, code)  # second essai : refusé, même exigence

    assert code not in caplog.text
    assert code.lower() not in caplog.text


# ── Service : détails de l'adhésion ─────────────────────────────────────────

def test_rejoindre_potager_retourne_de_quoi_repondre(test_db, lilas, envois):
    code = _inviter(test_db, lilas, "editor")

    adhesion = svc_potagers.rejoindre_potager(test_db, lilas.invitee_id, code)

    assert adhesion.potager_id == lilas.potager_id
    assert adhesion.potager_nom == "Jardin des Lilas"
    assert adhesion.role == "editor" and adhesion.role_libelle == "éditeur"
    assert adhesion.peut_ecrire is True and adhesion.devenu_actif is True
    assert adhesion.potager_actif_nom is None


def test_rejoindre_potager_un_lecteur_ne_peut_pas_ecrire(test_db, lilas, envois):
    code = _inviter(test_db, lilas, "lecteur")

    adhesion = svc_potagers.rejoindre_potager(test_db, lilas.invitee_id, code)

    assert adhesion.peut_ecrire is False


def test_rejoindre_potager_un_potager_archive_n_est_jamais_annonce_comme_actif(test_db, lilas, envois):
    code = _inviter(test_db, lilas)
    svc_potagers.archiver_potager(test_db, lilas.owner_id, lilas.potager_id)

    adhesion = svc_potagers.rejoindre_potager(test_db, lilas.invitee_id, code)

    assert adhesion.devenu_actif is False


def test_l_arrivee_par_la_pwa_ne_notifie_toujours_personne(test_db, lilas, envois):
    """La notification est propre à la porte d'entrée Telegram : le comportement de
    `accepter_invitation` (US-048), lui, ne change pas."""
    code = _inviter(test_db, lilas)

    svc_potagers.accepter_invitation(test_db, lilas.invitee_id, code)

    assert envois == []


def test_la_saisie_qui_suit_l_adhesion_se_rattache_au_potager_rejoint(test_db, lilas, envois):
    """Le potager devenu actif sert bien de contexte à la saisie qui suit."""
    code = _inviter(test_db, lilas, "editor")
    svc_potagers.rejoindre_potager(test_db, lilas.invitee_id, code)

    ctx = svc_potager_actif.resoudre_tenant_context(test_db, lilas.invitee_id)
    test_db.add(Evenement(type_action="semis", culture="carotte", potager_id=ctx.potager_id))
    test_db.commit()

    assert ctx.potager_id == lilas.potager_id
    assert ctx.role == "editor"
