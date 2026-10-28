"""[US-278] Le filet des caractéristiques de parcelle, quand l'agent ne propose rien.

Retours de terrain du 28/10/2026 (Ministral 3B) : la même phrase de caractéristiques
donnait, selon le nom de la planche, la bonne proposition, la liste des parcelles ou
un conseil sur les pommes de terre. Le filet lit la parcelle et les valeurs sans
modèle, APRÈS l'agent (US-277 inchangée), et le validateur habituel en fait la
proposition. Aucun appel réseau : la passerelle est simulée (`modele`).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app import config
from app.bot import interpretation as bot_interpretation
from app.services import interpreteur_commandes as interp
from app.services.agent import contexte_court, filet_fiche, interpreteur_agent
from app.services.context import TenantContext
from llm import passerelle
from llm.passerelle import AppelOutil, ReponseOutils

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
PARCELLES = ("PRINCIPAL", "TUNNEL CHAUFFÉ", "PLANT TUBERCULE", "PLANCHE TEST")
TUNNEL = "ma parcelle  tunnel chauffé a une superficie de 20 m2, longueur de 7m et ensoleillement mi-ombre"
TUBERCUL = "ma planche tubercul a une superficie de 20 m2, longueur de 7m et ensoleillement mi-ombre"
PRINCIPAL = "ma planche principal a une superficie de 50m2, longueur de 7m et disposera de 10 rangs"
FOND = "ma planche du fond a une superficie de 12 m2"


def _reponse(*appels: AppelOutil, texte: str = "") -> ReponseOutils:
    return ReponseOutils(
        texte=texte, modele="test", appel_type=passerelle.TYPE_AGENT,
        tokens_in=900, tokens_out=50, latence_ms=400, appels=appels, statut=passerelle.STATUT_OK,
    )


def _texte(texte: str) -> ReponseOutils:
    return _reponse(texte=texte)


def _appel(outil: str, ident: str = "", **arguments) -> AppelOutil:
    return AppelOutil(outil, arguments, id=ident)


def _voisin(nom: str):
    """`resolve_parcelle` simulé : la sous-chaîne, comme le rapprochement habituel."""
    cle = nom.replace(" ", "").lower()
    return next((p for p in PARCELLES if cle and cle in p.replace(" ", "").lower()), None)


@pytest.fixture
def agent_actif(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "actif")


@pytest.fixture
def agent_off(monkeypatch):
    monkeypatch.setattr(config, "AGENT_MODE", "off")


@pytest.fixture
def parcelles_connues(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "noms_parcelles_du_potager", lambda ctx: PARCELLES)
    monkeypatch.setattr(interpreteur_agent, "voisin_en_base", lambda ctx: _voisin)
    monkeypatch.setattr(interp, "_noms_de_parcelle_masques", lambda normalise, ctx: normalise)


@pytest.fixture
def modele():
    with patch.object(passerelle, "appeler_chat_outils") as faux:
        yield faux


@pytest.fixture(autouse=True)
def _sans_effets(monkeypatch):
    monkeypatch.setattr(interpreteur_agent, "persister_reponse", MagicMock())
    monkeypatch.setattr(bot_interpretation, "accueil_premier_contact", AsyncMock())
    contexte_court.oublier_tout()
    bot_interpretation._INTERP_PENDING.clear()
    yield
    contexte_court.oublier_tout()
    bot_interpretation._INTERP_PENDING.clear()


def _filet(phrase: str, noms: tuple[str, ...] = PARCELLES):
    return filet_fiche.proposer(phrase, noms, _voisin)


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — les valeurs lues sans modèle
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Valeurs:

    @pytest.mark.parametrize("phrase, attendu", [
        ("a une superficie de 20 m2", {"superficie_m2": 20}),
        ("fait 20 m²", {"superficie_m2": 20}),
        ("fait 8,5 mètres carrés", {"superficie_m2": 8.5}),
        ("longueur de 7m", {"longueur_m": 7}),
        ("fait 7 mètres de long", {"longueur_m": 7}),
        ("disposera de 10 rangs", {"nb_rangs": 10}),
        ("a dix rangs", {"nb_rangs": 10}),
        ("a dix-sept rangs", {"nb_rangs": 17}),
        ("ensoleillement mi-ombre", {"ensoleillement": "mi-ombre"}),
        ("est en plein soleil", {"ensoleillement": "plein soleil"}),
        ("est à l'ombre", {"ensoleillement": "ombre"}),
        ("exposée plein sud", {"exposition": "Sud"}),
        ("exposition : ouest", {"exposition": "Ouest"}),
    ])
    def test_us278_ca2_valeur_lue(self, phrase, attendu):
        assert filet_fiche.lire_valeurs(phrase) == attendu

    def test_us278_ca2_un_metre_sans_carre_n_est_jamais_une_superficie(self):
        assert filet_fiche.lire_valeurs("20 m2 et 7 m") == {"superficie_m2": 20, "longueur_m": 7}

    def test_us278_ca2_mi_ombre_n_est_pas_lu_comme_ombre(self):
        assert filet_fiche.lire_valeurs("ensoleillement mi ombre")["ensoleillement"] == "mi-ombre"

    def test_us278_ca2_un_point_cardinal_sans_exposition_est_un_nom(self):
        assert filet_fiche.lire_valeurs("la planche est fait 3 rangs") == {"nb_rangs": 3}

    def test_us278_ca2_un_nombre_non_place_est_dit(self):
        filet = _filet("la planche principal a 10 rangs depuis 3 jours")
        assert filet.commande.commande_equivalente() == "/parcelle modifier PRINCIPAL rangs=10"
        assert "Je n'ai pas su placer : 3" in filet.texte


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA3, CA4, CA5 — la parcelle désignée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1CA5Parcelle:

    def test_us278_ca3_parcelle_dite_exactement(self):
        filet = _filet(TUNNEL)
        assert filet.motif == "nom dit"
        assert filet.commande.complete
        assert filet.commande.commande_equivalente() == (
            "/parcelle modifier TUNNEL CHAUFFÉ superficie=20 longueur=7 ensoleillement=mi-ombre")
        assert filet.commande.forme.confirmation  # [CA3] rien n'est écrit sans confirmation

    def test_us278_ca4_parcelle_mal_dite_est_proposee_jamais_substituee(self):
        filet = _filet(TUBERCUL)
        assert filet.motif == "nom rapproché"
        assert filet.commande.candidats == ("PLANT TUBERCULE",)
        assert not filet.commande.complete
        choisie = filet.commande.avec(nom="PLANT TUBERCULE")
        assert choisie.complete
        assert choisie.commande_equivalente() == (
            "/parcelle modifier PLANT TUBERCULE superficie=20 longueur=7 ensoleillement=mi-ombre")

    def test_us278_ca5_aucune_parcelle_trouvee_offre_le_choix(self):
        filet = _filet(FOND)
        assert filet.motif == "choix parmi les parcelles"
        assert filet.commande.candidats == PARCELLES
        assert filet.commande.avec(nom="PRINCIPAL").commande_equivalente() == (
            "/parcelle modifier PRINCIPAL superficie=12")

    def test_us278_ca5_au_dela_de_six_parcelles_le_nom_est_demande(self):
        noms = tuple(f"Carré {n}" for n in "ABCDEFG")
        filet = _filet(FOND, noms)
        assert filet.motif == "nom demandé"
        assert not filet.commande.candidats and filet.commande.argument_candidat is None
        assert [a.nom for a in filet.commande.manquants] == ["nom"]
        assert "superficie=12" in filet.commande.valeurs["modification"]

    def test_us278_ca1_sans_parcelle_designee_pas_de_filet(self):
        assert _filet("une superficie de 20 m2 et 3 rangs") is None

    def test_us278_ca1_sans_valeur_de_fiche_pas_de_filet(self):
        assert _filet("la planche principal est belle") is None

    def test_us278_ca1_le_mot_de_parcelle_ne_compte_pas_comme_valeur(self):
        """« planche test » est un nom : « test » n'est relu ni comme nom ni comme valeur."""
        filet = _filet("ma planche test a 4 rangs")
        assert filet.commande.commande_equivalente() == "/parcelle modifier PLANCHE TEST rangs=4"


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — ce que le filet ne prend jamais
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9NonRegressions:

    def test_us278_ca9_un_geste_reste_un_geste(self):
        assert _filet("semé 3 rangs de carottes sur la planche principal") is None

    def test_us278_ca9_une_question_n_est_pas_prise(self):
        assert _filet("quelle superficie fait la planche principal ?") is None

    def test_us278_ca9_une_creation_ne_devient_pas_une_modification(self):
        assert _filet("crée la planche principal de 6 m") is None
        assert _filet("crée la planche du fond de 6 m") is None   # ni la question du CA5

    def test_us278_ca9_une_ecriture_proposee_par_l_agent_n_est_pas_remplacee(
        self, modele, parcelles_connues
    ):
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "m1", parcelle="PRINCIPAL", nb_rangs=10)),
            _texte("Je te propose 10 rangs."),
        ]
        resultat = interpreteur_agent.proposer("ma planche principal aura 10 rangs", CTX)
        assert resultat.motif == "ok" and "filet_fiche" not in resultat.outils
        assert resultat.texte == "Je te propose 10 rangs."

    def test_us278_ca9_une_phrase_simple_reste_aux_regles(self, agent_actif, modele, parcelles_connues):
        resultat = interp.interpreter("la planche nord a 5 rangs", CTX)
        assert resultat.origine == interp.ORIGINE_REGLE and resultat.regle != interp.REGLE_FILET_FICHE
        modele.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA7 — après l'agent, avec le texte du code
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7ApresLAgent:

    def test_us278_ca7_lecture_repetee_remplacee_par_la_proposition(self, modele, parcelles_connues):
        """Le relevé « tunnel chauffé » : `afficher` deux fois, la liste s'affichait."""
        modele.side_effect = [
            _reponse(_appel("afficher", "a1", commande="parcelle lister")),
            _reponse(_appel("afficher", "a2", commande="parcelle lister")),
            _texte("Voici ce qu'on sait de ta parcelle tunnel chauffé."),
        ]
        resultat = interpreteur_agent.proposer(TUNNEL, CTX)
        assert resultat.motif == "filet"
        assert resultat.commande.sous_commande == "modifier"
        assert resultat.texte == filet_fiche.TEXTE_FILET
        assert resultat.outils[-1] == interp.REGLE_FILET_FICHE

    def test_us278_ca7_texte_hors_sujet_jamais_montre(self, modele, parcelles_connues):
        """Le relevé « tubercul » : le modèle répondait sur les pommes de terre."""
        modele.return_value = _texte("Ah, les pommes de terre ! Tu veux les voir ?")
        resultat = interpreteur_agent.proposer(TUBERCUL, CTX)
        assert "pommes de terre" not in resultat.texte
        assert resultat.commande.candidats == ("PLANT TUBERCULE",)

    def test_us278_ca1_tous_les_appels_refuses(self, modele, parcelles_connues):
        """Un 9 inventé est refusé ; le filet propose le 6 dit."""
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "m1", parcelle="PRINCIPAL", nb_rangs=9)),
            _texte("D'accord."),
            _texte("D'accord."),
        ]
        resultat = interpreteur_agent.proposer("la planche principal a maintenant six rangs", CTX)
        assert resultat.commande.commande_equivalente() == "/parcelle modifier PRINCIPAL rangs=6"

    def test_us278_ca7_le_recapitulatif_est_celui_d_une_modification(self):
        recap = interp.recapitulatif(_filet(TUNNEL).commande)
        assert "Je *passe* la superficie de *TUNNEL CHAUFFÉ* à *20 m²*." in recap
        assert "l'ensoleillement de *TUNNEL CHAUFFÉ* à *mi-ombre*" in recap


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — une valeur de vocabulaire oubliée par l'agent lui est signalée
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6Relance:

    def test_us278_ca6_valeur_de_vocabulaire_non_reprise(self):
        appel = _appel("modifier_parcelle", parcelle="PLANCHE TEST", superficie_m2=10, longueur_m=1)
        phrase = "ma planche test a une superficie de 10 m2, longueur de 1m et ensoleillement mi-ombre"
        assert filet_fiche.valeurs_non_reprises(phrase, [appel], PARCELLES) == ["mi-ombre"]
        appel_complet = _appel("modifier_parcelle", parcelle="PLANCHE TEST", ensoleillement="mi-ombre")
        assert filet_fiche.valeurs_non_reprises(phrase, [appel_complet], PARCELLES) == []

    def test_us278_ca6_la_relance_porte_la_valeur_au_modele(self, modele, parcelles_connues):
        phrase = "ma planche test a une superficie de 10 m2, longueur de 1m et ensoleillement mi-ombre"
        modele.side_effect = [
            _reponse(_appel("modifier_parcelle", "m1", parcelle="PLANCHE TEST", superficie_m2=10, longueur_m=1)),
            _reponse(_appel("modifier_parcelle", "m2", parcelle="PLANCHE TEST", ensoleillement="mi-ombre")),
            _texte("Je te propose de compléter la planche test."),
        ]
        resultat = interpreteur_agent.proposer(phrase, CTX)
        historique = modele.call_args_list[1].kwargs["historique"]
        assert "mi-ombre" in historique[-1]["content"] and "non_repris" in historique[-1]["content"]
        # Le second appel complète le premier (même cible) : une seule proposition, complète.
        assert resultat.commande.commande_equivalente() == (
            "/parcelle modifier PLANCHE TEST superficie=10 longueur=1 ensoleillement=mi-ombre")


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — sans agent
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8SansAgent:

    def test_us278_ca8_agent_off_le_filet_propose(self, agent_off, modele, parcelles_connues):
        with patch.object(interp, "_appeler_modele", return_value=None):
            resultat = interp.interpreter(PRINCIPAL, CTX)
        assert isinstance(resultat, interp.ReponseAgent)
        assert resultat.proposition.origine == interp.ORIGINE_REGLE
        assert resultat.proposition.regle == interp.REGLE_FILET_FICHE
        assert resultat.proposition.commande_equivalente() == (
            "/parcelle modifier PRINCIPAL superficie=50 longueur=7 rangs=10")
        modele.assert_not_called()

    def test_us278_ca8_agent_indisponible_le_filet_propose(self, agent_actif, modele, parcelles_connues):
        modele.side_effect = RuntimeError("quota")
        with patch.object(interp, "_appeler_modele", return_value=None):
            resultat = interp.interpreter(TUNNEL, CTX)
        assert resultat.proposition.regle == interp.REGLE_FILET_FICHE

    def test_us278_ca8_phrase_ecartee_par_les_regles(self, agent_off, parcelles_connues):
        """[US-277 / CA6] Écartée par les règles, elle n'est plus « non traitée »."""
        phrase = "et la planche principal a 4 rangs"
        with patch.object(interp, "_appeler_modele", return_value=None):
            resultat = interp.interpreter(phrase, CTX)
        assert resultat.proposition.commande_equivalente() == "/parcelle modifier PRINCIPAL rangs=4"

    def test_us278_ca8_sans_caracteristique_rien_ne_change(self, agent_off, parcelles_connues):
        with patch.object(interp, "_appeler_modele", return_value=None):
            assert interp.interpreter("la planche principal me plaît beaucoup", CTX) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA4, CA5 — dans le bot : le choix de la parcelle, puis la proposition complète
# ═════════════════════════════════════════════════════════════════════════════
def _update(user_id: int):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


async def _afficher(update, filet) -> MagicMock:
    tg_ctx = MagicMock()
    tg_ctx.user_data = {}
    reponse = interp.ReponseAgent(texte=filet.texte, proposition=filet.commande, texte_origine="x")
    with (
        patch.object(bot_interpretation, "current_context", return_value=CTX),
        patch.object(bot_interpretation, "_resoudre_noms_parcelle", side_effect=lambda c: c),
        patch.object(bot_interpretation.svc_interpreteur, "persister_journal", return_value=None),
    ):
        await bot_interpretation._traiter_commande_interpretee(update, tg_ctx, reponse)
    return tg_ctx


@pytest.mark.asyncio
async def test_us278_ca5_le_bot_demande_quelle_parcelle_avec_les_boutons():
    update = _update(31)
    await _afficher(update, _filet(FOND))
    envoye = update.message.reply_text.await_args
    assert "Quelle parcelle ?" in envoye.args[0]
    assert "Vouliez-vous dire" not in envoye.args[0]
    boutons = str(envoye.kwargs["reply_markup"])
    assert all(f"📍 {nom}" in boutons for nom in PARCELLES)


@pytest.mark.asyncio
async def test_us278_ca4_le_choix_mene_a_la_proposition_complete():
    update = _update(32)
    tg_ctx = await _afficher(update, _filet(TUBERCUL))
    assert "PLANT TUBERCULE" in update.message.reply_text.await_args.args[0]

    ident = bot_interpretation._INTERP_PENDING[32]["id"]
    clic = MagicMock()
    clic.effective_user.id = 32
    clic.message = None
    clic.callback_query = AsyncMock()
    clic.callback_query.data = f"interp:cand:0:{ident}"
    clic.callback_query.message = AsyncMock()
    with (
        patch.object(bot_interpretation, "current_context", return_value=CTX),
        patch.object(bot_interpretation, "_potager_actif_au_clic", return_value=1),
        patch.object(bot_interpretation.svc_interpreteur, "persister_journal", return_value=None),
    ):
        await bot_interpretation._interp_cb(clic, tg_ctx)
    commande = bot_interpretation._INTERP_PENDING[32]["commande"]
    assert commande.complete
    assert commande.commande_equivalente() == (
        "/parcelle modifier PLANT TUBERCULE superficie=20 longueur=7 ensoleillement=mi-ombre")
    recap = clic.callback_query.message.edit_text.await_args
    assert "Confirmer" in str(recap.kwargs["reply_markup"])
