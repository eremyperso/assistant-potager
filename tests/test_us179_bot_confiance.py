"""
tests/test_us179_bot_confiance.py — « je peux semer / planter X ? » au bot [US-179]
====================================================================================

US-178 calcule la confiance ; cette US la met dans la main du jardinier. Ce qui
se vérifie ici, critère par critère :

- CA1  la question est reconnue, avec ou sans date, avec ou sans parcelle ;
       « ce week-end » → samedi suivant, « samedi », « le 20 mai », « dans dix jours »
- CA2  reconnaissance par la grammaire déterministe, ZÉRO jeton ; une phrase
       non reconnue rejoint le routeur sans être rejetée
- CA3  action déduite du verbe ; filière demandée en un geste, et seulement
       quand la culture se sème des deux façons
- CA4  culture · action · zone, étoiles, motifs gagnés → perdus → indéterminés,
       récolte attendue en fourchette
- CA5  aucun score possible → un tiret et `/calendrier`, jamais une estimation
- CA6  boutons : enregistrer le geste (flux EXISTANT, confirmation comprise),
       redemander dans dix jours
- CA7  sans parcelle, la réponse porte sur le potager et l'enregistrement la demande
- CA8  corpus de mesure étendu : formulations, phrases hors périmètre, taux
- CA9  échappement Telegram d'un nom de culture à caractère spécial
- CA10 aucun état conversationnel laissé ouvert
- CA11 la fiche d'aide porte la section et ses questions de mesure
- CA12 ce fichier

⚠️ Les fenêtres, durées et rusticités écrites ici sont des VALEURS DE TEST :
elles n'engagent aucune agronomie.
"""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot import commandes_confiance as bot_conf
from app.bot.etat import _CONFIANCE_PENDING
from app.services import calendrier_cultural as cal
from app.services import confiance_semis as conf
from app.services import interpreteur_commandes as interp
from app.services import menu_commandes as svc_menu
from app.services.context import TenantContext
from database.models import (
    CultureConfig, DureeCulturale, FenetreCulturale, ItineraireCultural,
    Parcelle, Potager, ReferentielSource, User,
)

RACINE = Path(__file__).resolve().parent.parent
CORPUS_COMMANDES = RACINE / "tests" / "corpus" / "us172_commandes.csv"
CORPUS_AIDE = RACINE / "tests" / "corpus" / "us099_questions_fonctionnement.csv"
FICHE_AIDE = RACINE / "data" / "connaissance" / "doc_app" / "calendrier-et-zone-climatique.md"

CTX = TenantContext(user_id=1, potager_id=1, role="owner")

#: Un jeudi — toutes les résolutions de date relatives partent de là.
JEUDI = date(2027, 9, 16)
SAMEDI_SUIVANT = date(2027, 9, 18)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Un potager océanique localisé, une parcelle ordinaire, une pépinière."""
    test_db.add(User(id=1, email="a@potager.test"))
    test_db.flush()
    test_db.add(Potager(id=1, nom="Jardin", proprietaire_id=1,
                        zone_climatique="oceanique", latitude=47.2, longitude=-1.55))
    test_db.flush()
    test_db.add_all([
        Parcelle(id=1, nom="planche nord", nom_normalise="planchenord", potager_id=1),
        Parcelle(id=2, nom="serre", nom_normalise="serre", potager_id=1, est_pepiniere=True),
    ])
    test_db.add(ReferentielSource(
        id=1, code="test", libelle="Test", licence="CC0",
        attribution="Valeurs de test", partageable=True, importee=True,
    ))
    test_db.commit()
    return test_db


def _seed(db, nom, *, rusticite=None, fenetres=None, durees=None):
    fiche = CultureConfig(nom=nom, type_organe_recolte="fruit", rusticite_min_c=rusticite)
    db.add(fiche)
    db.flush()
    it = ItineraireCultural(culture_id=fiche.id, nom="standard",
                            nom_normalise="standard", source_id=1)
    db.add(it)
    db.flush()
    for phase, (debut, fin) in (fenetres or {}).items():
        db.add(FenetreCulturale(itineraire_id=it.id, zone_climatique="oceanique",
                                phase=phase, mois_debut=debut, mois_fin=fin, source_id=1))
    for etape, (mini, maxi) in (durees or {}).items():
        db.add(DureeCulturale(itineraire_id=it.id, etape=etape,
                              jours_min=mini, jours_max=maxi, source_id=1))
    db.commit()
    return it


def _haricot(db):
    """Ne se sème QUE en pleine terre — la filière ne se demande donc jamais (CA3)."""
    return _seed(db, "haricot", rusticite=5.0,
                 fenetres={cal.PHASE_SEMIS_PLEINE_TERRE: (5, 9), cal.PHASE_RECOLTE: (7, 11)},
                 durees={cal.ETAPE_RECOLTE: (55, 70)})


def _tomate(db):
    """Se sème des DEUX façons — c'est le cas où la filière se demande (CA3)."""
    return _seed(db, "tomate", rusticite=5.0,
                 fenetres={cal.PHASE_SEMIS_PEPINIERE: (2, 4),
                           cal.PHASE_SEMIS_PLEINE_TERRE: (5, 6),
                           cal.PHASE_PLANTATION: (5, 6),
                           cal.PHASE_RECOLTE: (7, 10)},
                 durees={cal.ETAPE_RECOLTE: (100, 130),
                         cal.ETAPE_PLANTATION_RECOLTE: (60, 80)})


def _update(user_id: int = 42):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = AsyncMock()
    update.callback_query = None
    return update


def _update_callback(data: str, user_id: int = 42):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message = None
    update.callback_query = AsyncMock()
    update.callback_query.data = data
    update.callback_query.message = AsyncMock()
    return update


def _ctx(*args):
    ctx = MagicMock()
    ctx.args = list(args)
    ctx.user_data = {}
    return ctx


def _texte_envoye(update) -> str:
    morceaux = []
    for cible in (update.message, getattr(update.callback_query, "message", None)):
        if cible is None:
            continue
        for appel in cible.reply_text.await_args_list:
            morceaux.append(str(appel.args[0] if appel.args else appel.kwargs.get("text", "")))
    return "\n".join(morceaux)


def _clavier(update):
    for cible in (update.message, getattr(update.callback_query, "message", None)):
        if cible is None:
            continue
        for appel in reversed(cible.reply_text.await_args_list):
            clavier = appel.kwargs.get("reply_markup")
            if clavier is not None:
                return clavier
    return None


def _libelles(clavier) -> list[str]:
    return [b.text for ligne in clavier.inline_keyboard for b in ligne]


def _callbacks(clavier) -> list[str]:
    return [b.callback_data for ligne in clavier.inline_keyboard for b in ligne]


@pytest.fixture(autouse=True)
def _etat_propre():
    """Aucun test ne doit hériter de la question d'un autre (CA10)."""
    _CONFIANCE_PENDING.clear()
    yield
    _CONFIANCE_PENDING.clear()


def _lignes_corpus() -> list[dict]:
    with CORPUS_COMMANDES.open(encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def _confiance(**kwargs) -> conf.Confiance:
    """Une `Confiance` de test, sans base ni moteur — pour les gabarits purs."""
    defauts = dict(
        culture="haricot", culture_connue=True, action=conf.ACTION_SEMIS_PLEINE_TERRE,
        date_cible=date(2027, 5, 20), zone="oceanique", itineraire="standard",
        etoiles=2, score=60, motifs=[], score_max_atteignable=100, avertissements=[],
    )
    defauts.update(kwargs)
    return conf.Confiance(**defauts)


def _motif(regle, etat, libelle, points=0):
    return conf.Motif(regle=regle, libelle_regle=conf.LIBELLES_REGLES[regle],
                      etat=etat, libelle=libelle, points=points,
                      points_max=conf.POINTS_MAX[regle])


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — la question est reconnue, datée, située
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1LaQuestionEstReconnue:

    @pytest.mark.parametrize("phrase", [
        "je peux semer des haricots ce week-end ?",
        "est-ce que je peux semer des carottes demain ?",
        "est-ce qu'on peut semer les épinards maintenant ?",
        "peut-on planter les poireaux cette semaine ?",
        "puis-je semer la mâche dans dix jours ?",
        "c'est le moment de planter les tomates ?",
        "c'est le bon moment pour semer des radis ?",
        "est-ce le moment de semer des épinards ?",
        "est-ce une bonne idée de semer des haricots demain ?",
        "c'est trop tôt pour semer des tomates ?",
        "est-ce trop tard pour semer des carottes ?",
        "faut-il semer les haricots maintenant ?",
        "ça vaut le coup de semer des haricots samedi ?",
        "je sème les carottes ce week-end ou j'attends ?",
    ])
    def test_us179_ca1_les_formulations_sont_reconnues(self, phrase):
        """[CA1] Modale, jugement, moment, alternative : les quatre registres."""
        resultat = interp.reconnaitre_par_regles(phrase)
        assert resultat is not None, phrase
        assert resultat.commande == "confiance"

    def test_us179_ca1_sans_date_la_commande_n_en_porte_aucune(self):
        """[CA1] Pas de date dictée, pas de date inventée : c'est le handler qui
        applique la convention du projet (aujourd'hui), et lui seul."""
        commande = interp.reconnaitre_par_regles("je peux semer des haricots ?")
        assert "date" not in commande.valeurs

    @pytest.mark.parametrize("expression, attendue", [
        ("ce week-end", SAMEDI_SUIVANT),
        ("samedi", SAMEDI_SUIVANT),
        ("demain", JEUDI + timedelta(days=1)),
        ("dans dix jours", JEUDI + timedelta(days=10)),
        ("le 20 mai", date(2028, 5, 20)),          # mai est passé : le mai PROCHAIN
    ])
    def test_us179_ca1_les_dates_sont_celles_de_l_avenir(self, expression, attendue):
        """[CA1] La grammaire de dates du projet, lue en mode AVENIR.

        C'est le point où cette US a dû ÉTENDRE `utils.date_utils` : jusqu'ici,
        toute sa grammaire datait le passé (« samedi » = samedi dernier), parce
        qu'elle ne servait qu'à rattacher un geste déjà fait.
        """
        from utils.date_utils import resoudre_ancrage_temporel

        with patch("utils.date_utils.date") as faux_jour:
            faux_jour.today.return_value = JEUDI
            faux_jour.side_effect = date
            ancrage = resoudre_ancrage_temporel(expression, JEUDI, futur=True)
        assert ancrage.date_iso == attendue.isoformat(), expression

    def test_us179_ca1_le_passe_reste_le_passe_pour_un_geste_fait(self):
        """[CA1] Le mode futur est un MODE : sans lui, rien ne change pour le
        parseur de saisie, qui date des gestes déjà faits (US-094)."""
        from utils.date_utils import resoudre_ancrage_temporel

        assert resoudre_ancrage_temporel("samedi dernier", JEUDI).date_iso == "2027-09-11"
        assert resoudre_ancrage_temporel("hier", JEUDI).date_iso == "2027-09-15"

    def test_us179_ca1_la_parcelle_nommee_est_lue(self):
        """[CA1] Le marqueur de parcelle du parseur déterministe, et lui seul."""
        commande = interp.reconnaitre_par_regles(
            "je peux semer des haricots planche nord ce week-end ?"
        )
        assert commande.valeurs["culture"] == "haricots"
        assert commande.valeurs["parcelle"] == "planche nord"

    def test_us179_ca1_un_rang_est_un_endroit_dans_une_question(self):
        """[CA1] Scénario Gherkin — « rang 3 » nomme une parcelle, pas une quantité.

        Dans une SAISIE, « trois rangs de carottes » porte une quantité, et le
        parseur déterministe refuse justement de trancher. Dans une QUESTION
        d'opportunité, aucune quantité n'est en jeu.
        """
        commande = interp.reconnaitre_par_regles(
            "je peux semer des haricots rang 3 ce week-end ?"
        )
        assert commande.valeurs["culture"] == "haricots"
        assert commande.valeurs["parcelle"] == "rang 3"

    def test_us179_ca1_garde_fou_annee_deja_passee_ne_pollue_pas_la_culture(self):
        """[Garde-fou] « le 10 avril 2026 » demandé après cette date (année DITE,
        donc jamais corrigée d'un an par `_construire`, date_utils.py) ne doit
        plus se retrouver collé au nom de la culture. La règle renonce plutôt
        que de produire une culture absurde évaluée en silence à aujourd'hui —
        la phrase rejoint alors le routeur de questions (CA2)."""
        with patch("utils.date_utils.date") as faux_jour:
            faux_jour.today.return_value = date(2026, 9, 18)
            faux_jour.side_effect = date
            commande = interp.reconnaitre_par_regles(
                "je peux semer des carottes le 10 avril 2026 ?"
            )
        assert commande is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — reconnue sans jeton, non reconnue sans silence
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2ZeroJeton:

    def test_us179_ca2_aucune_formulation_n_atteint_le_modele(self):
        """[CA2] La passerelle est mise sous surveillance : une seule phrase qui
        l'atteindrait rendrait fausse l'économie annoncée par l'US."""
        phrases = [l["phrase"] for l in _lignes_corpus() if l["attendu"] == "confiance"]
        assert len(phrases) >= 20
        with patch.object(interp, "_appeler_modele") as faux_modele:
            for phrase in phrases:
                interp.interpreter(phrase, None)
            assert faux_modele.call_count == 0

    def test_us179_ca2_origine_regle_et_confiance_pleine(self):
        commande = interp.reconnaitre_par_regles("je peux semer des haricots ce week-end ?")
        assert commande.origine == interp.ORIGINE_REGLE
        assert commande.confiance == 1.0
        assert commande.regle.startswith("confiance_")

    def test_us179_ca2_une_phrase_non_reconnue_rejoint_le_routeur(self):
        """[CA2] Scénario Gherkin — « tu penses quoi des haricots en ce moment ? »
        n'est pas captée ici : elle continue son chemin, elle n'est pas rejetée."""
        assert interp.reconnaitre_par_regles(
            "tu penses quoi des haricots en ce moment ?"
        ) is None

    @pytest.mark.parametrize("phrase", [
        "j'ai semé des haricots rang 3 samedi",
        "je sème les carottes ce week-end",
        "j'ai planté les tomates hier",
        "semis de haricots planche nord",
    ])
    def test_us179_ca2_un_enregistrement_n_est_pas_une_question(self, phrase):
        """[CA2, CA8] Le risque central de l'US : capter la SAISIE, qui est le
        geste le plus fréquent du bot. Aucune règle ne reconnaît un verbe de
        semis nu — « je sème les carottes ce week-end » reste une déclaration,
        et seule l'alternative (« ou j'attends ? ») en fait une question."""
        assert interp.reconnaitre_par_regles(phrase) is None

    def test_us179_ca2_comment_semer_reste_une_demande_de_procedure(self):
        """[CA2] Le garde 1 d'US-172 ne s'efface QUE devant une modalité."""
        assert interp.reconnaitre_par_regles("comment semer des haricots ?") is None
        assert interp.reconnaitre_par_regles("comment savoir si c'est le moment de semer ?") is None

    def test_us179_ca2_quand_semer_reste_une_question_de_calendrier(self):
        """[CA2] « quand semer » demande la PÉRIODE, « je peux semer » un AVIS."""
        assert interp.reconnaitre_par_regles("quand semer les haricots ?").commande == "calendrier"


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — l'action vient du verbe, la filière se demande en un geste
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3ActionEtFiliere:

    @pytest.mark.parametrize("phrase, action", [
        ("je peux semer des haricots ?", conf.ACTION_SEMIS),
        ("je peux planter des tomates ?", conf.ACTION_PLANTATION),
        ("je peux repiquer les poireaux ?", conf.ACTION_PLANTATION),
        ("je peux semer des tomates en pépinière ?", conf.ACTION_SEMIS_PEPINIERE),
        ("je peux semer des haricots en pleine terre ?", conf.ACTION_SEMIS_PLEINE_TERRE),
    ])
    def test_us179_ca3_l_action_est_deduite_du_verbe(self, phrase, action):
        assert interp.reconnaitre_par_regles(phrase).valeurs["action"] == action

    def test_us179_ca3_planter_en_pleine_terre_reste_une_plantation(self):
        """[CA3] Une filière dite ne vaut que pour un semis."""
        commande = interp.reconnaitre_par_regles("je peux planter les tomates en pleine terre ?")
        assert commande.valeurs["action"] == conf.ACTION_PLANTATION

    @pytest.mark.asyncio
    async def test_us179_ca3_une_seule_filiere_ne_pose_aucune_question(self, db):
        """[CA3] Même règle qu'US-069 : le référentiel ne connaît qu'une façon de
        semer le haricot, donc rien n'est demandé. La fluidité est un critère."""
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        texte = _texte_envoye(update)
        assert "des deux façons" not in texte
        assert "semis en pleine terre" in texte

    @pytest.mark.asyncio
    async def test_us179_ca3_deux_filieres_demandent_en_un_seul_geste(self, db):
        """[CA3] Scénario Gherkin — la tomate se sème des deux façons : deux
        boutons, et la réponse de confiance suit ce seul geste."""
        _tomate(db)
        update, ctx = _update(), _ctx("tomate", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        clavier = _clavier(update)
        assert _callbacks(clavier) == ["conf:filiere:pepiniere", "conf:filiere:pleine_terre"]

        suite = _update_callback("conf:filiere:pleine_terre")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf._confiance_cb(suite, _ctx())
        assert "semis en pleine terre" in _texte_envoye(suite)

    @pytest.mark.asyncio
    async def test_us179_ca3_une_parcelle_pepiniere_impose_la_filiere(self, db):
        """[CA3] « Une parcelle pépinière nommée dans la phrase impose le semis
        en pépinière » — la règle vit dans le moteur (US-178 / CA8), pas ici."""
        _tomate(db)
        update, ctx = _update(), _ctx("tomate", "semis", "2027-03-15", "serre")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        texte = _texte_envoye(update)
        assert "des deux façons" not in texte
        assert "semis en pépinière" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — ce que la réponse affiche, et dans quel ordre
# ═════════════════════════════════════════════════════════════════════════════
class TestCA4LaReponse:

    def test_us179_ca4_l_entete_porte_culture_action_et_zone(self):
        texte = bot_conf._formater_reponse(_confiance())
        premiere = texte.splitlines()[0]
        assert "Haricot" in premiere
        assert "semis en pleine terre" in premiere
        assert "océanique" in premiere

    def test_us179_ca4_les_etoiles_sont_affichees(self):
        assert "★★" in bot_conf._formater_reponse(_confiance(etoiles=2))
        assert "★★★" in bot_conf._formater_reponse(_confiance(etoiles=3))

    def test_us179_ca4_les_motifs_vont_des_gagnes_aux_indetermines(self):
        """[CA4] Gagnés, puis perdus, puis indéterminés — chacun sur sa ligne.

        Un jardinier lit d'abord ce qui l'autorise ; l'ordre inverse ferait d'une
        réponse à deux étoiles un refus.
        """
        confiance = _confiance(motifs=[
            _motif(conf.R2_DERNIERE_GELEE, conf.ETAT_INDETERMINE, "Sensibilité au gel inconnue"),
            _motif(conf.R4_NUITS_DOUCES, conf.ETAT_PERDU, "Nuits fraîches"),
            _motif(conf.R1_FENETRE, conf.ETAT_GAGNE, "Dans la fenêtre conseillée", 40),
        ])
        lignes = [
            l for l in bot_conf._formater_reponse(confiance).splitlines()
            if l and l[0] in "✅❌❔"
        ]
        assert [l[0] for l in lignes] == ["✅", "❌", "❔"]
        assert lignes[0].endswith("Dans la fenêtre conseillée")

    def test_us179_ca4_la_recolte_est_une_fourchette(self):
        """[CA4] Deux bornes, jamais une date sèche. L'année n'est rappelée que
        lorsqu'elle n'est pas celle qui court — « je peux semer en novembre ? »
        récolte l'an prochain, et le taire serait trompeur."""
        texte = bot_conf._formater_reponse(_confiance(
            recolte_min=date(2027, 8, 12), recolte_max=date(2027, 8, 26),
        ))
        assert "entre le 12 août 2027 et le 26 août 2027" in texte

        cette_annee = date.today() + timedelta(days=30)
        texte = bot_conf._formater_reponse(_confiance(
            recolte_min=cette_annee, recolte_max=cette_annee + timedelta(days=14),
        ))
        assert str(cette_annee.year) not in texte

    def test_us179_ca4_sans_duree_la_recolte_est_un_tiret(self):
        """[CA4] « … ou un tiret » — jamais une date de remplacement."""
        assert f"Récolte attendue : {conf.TIRET}" in bot_conf._formater_reponse(_confiance())

    def test_us179_ca4_la_parcelle_figure_dans_l_entete(self):
        texte = bot_conf._formater_reponse(_confiance(), parcelle_nom="planche nord")
        assert "planche nord" in texte.splitlines()[0]

    def test_us179_ca4_les_avertissements_sont_rendus(self):
        """[CA5 d'US-178] Le plafond sans météo se voit, il ne se déduit pas."""
        texte = bot_conf._formater_reponse(_confiance(
            avertissements=["Météo indisponible : localise ton potager"],
        ))
        assert "localise ton potager" in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — sans calendrier, pas d'estimation
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5SansScore:

    def test_us179_ca5_ni_etoile_ni_date_mais_la_marche_a_suivre(self):
        confiance = _confiance(
            culture="ail", etoiles=None, score=None, score_max_atteignable=0,
            motifs=[_motif(conf.R1_FENETRE, conf.ETAT_INDETERMINE, conf.MOTIF_SANS_CALENDRIER)],
        )
        texte = bot_conf._formater_reponse(confiance)
        assert "★" not in texte
        assert conf.TIRET in texte
        assert "/calendrier ail" in texte
        assert "Récolte attendue" not in texte

    @pytest.mark.asyncio
    async def test_us179_ca5_scenario_gherkin_l_ail_sans_fenetre(self, db):
        """[CA5] Scénario Gherkin — aucune fenêtre pour l'ail dans cette zone."""
        _seed(db, "ail", fenetres={}, durees={})
        update, ctx = _update(), _ctx("ail", "plantation", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        texte = _texte_envoye(update)
        assert "★" not in texte
        assert "/calendrier ail" in texte

    def test_us179_ca5_aucun_bouton_pour_redemander_sans_score(self):
        """[CA5] Reposer dans dix jours une question sans calendrier rendrait le
        même tiret : le bouton ne s'affiche pas."""
        confiance = _confiance(etoiles=None, score=None, score_max_atteignable=0, motifs=[])
        assert "conf:redemande" not in _callbacks(bot_conf._boutons(confiance))
        assert "conf:enr" in _callbacks(bot_conf._boutons(confiance))


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — de la recommandation au geste, sans nouveau chemin d'écriture
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6DuConseilAuGeste:

    @pytest.mark.asyncio
    async def test_us179_ca6_la_reponse_porte_ses_deux_boutons(self, db):
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        libelles = _libelles(_clavier(update))
        assert "🌱 Enregistrer le semis" in libelles
        assert f"🔁 Redemander dans {bot_conf.JOURS_REDEMANDE} jours" in libelles

    @pytest.mark.asyncio
    async def test_us179_ca6_enregistrer_emprunte_le_flux_existant(self, db):
        """[CA6] Scénario Gherkin — le flux d'enregistrement EXISTANT s'ouvre,
        culture, date, parcelle et filière déjà remplies, confirmation comprise.

        Ce qui se vérifie est précisément qu'aucun second chemin d'écriture n'est
        créé : c'est `_parse_and_save` qui est appelé, avec un item pré-parsé —
        donc sans appel au modèle non plus.
        """
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20", "planche nord")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)

        clic = _update_callback("conf:enr")
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as faux_flux:
            await bot_conf._confiance_cb(clic, _ctx())
        faux_flux.assert_awaited_once()
        item = faux_flux.await_args.kwargs["pre_parsed_items"][0]
        assert item["action"] == "semis"
        assert item["culture"] == "haricot"
        assert item["date"] == "2027-05-20"
        assert item["parcelle"] == "planche nord"
        assert item["contexte_semis"] == "pleine_terre"

    @pytest.mark.asyncio
    async def test_us179_ca6_planter_enregistre_une_plantation_sans_filiere(self, db):
        """[CA6] Une plantation ne porte aucune filière de semis."""
        _tomate(db)
        update, ctx = _update(), _ctx("tomate", "plantation", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        clic = _update_callback("conf:enr")
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as faux_flux:
            await bot_conf._confiance_cb(clic, _ctx())
        item = faux_flux.await_args.kwargs["pre_parsed_items"][0]
        assert item["action"] == "plantation"
        assert "contexte_semis" not in item

    @pytest.mark.asyncio
    async def test_us179_ca6_redemander_decale_de_dix_jours(self, db):
        """[CA6] La même évaluation, décalée — pas une autre question."""
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)

        clic = _update_callback("conf:redemande")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf._confiance_cb(clic, _ctx())
        assert "30 mai" in _texte_envoye(clic)
        assert _CONFIANCE_PENDING[42]["date"] == "2027-05-30"

    @pytest.mark.asyncio
    async def test_us179_ca6_une_question_expiree_ne_s_enregistre_pas(self, db):
        """[CA6] Une recommandation périmée ne doit pas écrire : la météo qui la
        motivait a changé."""
        clic = _update_callback("conf:enr")
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as faux_flux:
            await bot_conf._confiance_cb(clic, _ctx())
        faux_flux.assert_not_awaited()
        clic.callback_query.edit_message_text.assert_awaited()


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — sans parcelle, la réponse porte sur le potager
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7SansParcelle:

    @pytest.mark.asyncio
    async def test_us179_ca7_sans_parcelle_l_entete_n_en_nomme_aucune(self, db):
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        assert "planche nord" not in _texte_envoye(update)

    @pytest.mark.asyncio
    async def test_us179_ca7_l_enregistrement_laisse_le_flux_demander_la_parcelle(self, db):
        """[CA7] La parcelle reste `None` : c'est le flux existant qui la demande,
        comme pour n'importe quelle autre saisie. Rien n'est deviné ici."""
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        clic = _update_callback("conf:enr")
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()) as faux_flux:
            await bot_conf._confiance_cb(clic, _ctx())
        assert faux_flux.await_args.kwargs["pre_parsed_items"][0]["parcelle"] is None

    @pytest.mark.asyncio
    async def test_us179_ca7_une_parcelle_inconnue_est_dite_pas_remplacee(self, db):
        """[CA7] Une parcelle nommée mais introuvable ne devient pas le potager
        entier en silence."""
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20", "chez", "le", "voisin")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        assert "Aucune parcelle" in _texte_envoye(update)


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — le corpus de mesure
# ═════════════════════════════════════════════════════════════════════════════
class TestCA8Corpus:

    def test_us179_ca8_au_moins_vingt_formulations(self):
        lignes = [l for l in _lignes_corpus() if l["attendu"] == "confiance"]
        assert len(lignes) >= 20, f"{len(lignes)} formulations"

    def test_us179_ca8_au_moins_cinq_phrases_hors_perimetre_proches(self):
        """[CA8] Un corpus qui ne porterait que des succès ne mesurerait rien.

        Les phrases retenues partagent la culture ET le verbe des questions :
        ce sont les voisines qui peuvent réellement être confondues.
        """
        hors = [
            l for l in _lignes_corpus()
            if l["registre"] == "hors_perimetre"
            and any(mot in l["phrase"] for mot in ("sem", "plant", "repiq"))
        ]
        assert len(hors) >= 5, f"{len(hors)} phrases hors périmètre proches"

    def test_us179_ca8_taux_de_reconnaissance_consigne(self):
        """[CA8] Le taux de reconnaissance — 100 % au 17/09/2026, publié dans
        PATCH_NOTES.md à la livraison."""
        lignes = [l for l in _lignes_corpus() if l["attendu"] == "confiance"]
        reconnues = sum(
            1 for l in lignes
            if getattr(interp.reconnaitre_par_regles(l["phrase"]), "commande", None) == "confiance"
        )
        assert reconnues == len(lignes), f"{reconnues}/{len(lignes)}"

    def test_us179_ca8_taux_de_faux_positifs_consigne(self):
        """[CA8] Le taux de faux positifs — 0 au 17/09/2026. Une saisie captée
        par cette US écrirait un événement que le jardinier n'a pas fait."""
        faux = [
            l["phrase"] for l in _lignes_corpus()
            if l["attendu"] != "confiance"
            and getattr(interp.reconnaitre_par_regles(l["phrase"]), "commande", None) == "confiance"
        ]
        assert faux == [], "\n".join(faux)


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — la réponse part toujours
# ═════════════════════════════════════════════════════════════════════════════
class TestCA9Echappement:

    def test_us179_ca9_un_nom_a_caractere_special_est_echappe(self):
        """[CA9] Un underscore non échappé fait échouer l'envoi Telegram ENTIER
        sur un `Can't parse entities` : la réponse est perdue, pas dégradée."""
        texte = bot_conf._formater_reponse(
            _confiance(culture="pomme_de_terre"), parcelle_nom="carré_nord",
        )
        assert "Pomme\\_de\\_terre" in texte
        assert "carré\\_nord" in texte

    def test_us179_ca9_les_motifs_aussi_sont_echappes(self):
        confiance = _confiance(motifs=[
            _motif(conf.R1_FENETRE, conf.ETAT_GAGNE, "Fenêtre pleine_terre atteinte", 40),
        ])
        assert "pleine\\_terre" in bot_conf._formater_reponse(confiance)


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — rien ne reste ouvert
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10AucunEtatResiduel:

    @pytest.mark.asyncio
    async def test_us179_ca10_aucun_mode_conversationnel_n_est_pose(self, db):
        """[CA10] `ctx.user_data['mode']` capturerait la commande suivante du
        jardinier : cette US n'en pose jamais."""
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        assert ctx.user_data == {}

    @pytest.mark.asyncio
    async def test_us179_ca10_l_enregistrement_referme_la_question(self, db):
        _haricot(db)
        update, ctx = _update(), _ctx("haricot", "semis", "2027-05-20")
        with patch.object(bot_conf, "SessionLocal", return_value=db):
            await bot_conf.cmd_confiance(update, ctx)
        assert 42 in _CONFIANCE_PENDING
        with patch("app.bot.saisie._parse_and_save", new=AsyncMock()):
            await bot_conf._confiance_cb(_update_callback("conf:enr"), _ctx())
        assert 42 not in _CONFIANCE_PENDING


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — la fiche d'aide, et ses questions de mesure
# ═════════════════════════════════════════════════════════════════════════════
class TestCA11FicheAide:

    def test_us179_ca11_la_fiche_porte_la_section(self):
        texte = FICHE_AIDE.read_text(encoding="utf-8")
        assert "## Savoir si c'est le moment de semer ou de planter" in texte
        assert "## Sur quoi repose le niveau d'étoiles avant de semer" in texte

    def test_us179_ca11_au_moins_deux_questions_de_mesure(self):
        with CORPUS_AIDE.open(encoding="utf-8") as fichier:
            servies = [
                l for l in csv.DictReader(fichier)
                if "savoir-si-c-est-le-moment" in l["fragment_attendu"]
                or "sur-quoi-repose-le-niveau" in l["fragment_attendu"]
            ]
        assert len(servies) >= 2, f"{len(servies)} question(s) de mesure"


# ═════════════════════════════════════════════════════════════════════════════
# Catalogue — la commande est tranchée, l'arbitrage est écrit
# ═════════════════════════════════════════════════════════════════════════════
class TestCatalogueEtArbitrage:

    def test_us179_la_commande_est_dictable_et_sans_confirmation(self):
        """[US-172 / CA7] Une commande ajoutée doit être tranchée. Celle-ci est
        une CONSULTATION : lui demander « voulez-vous vraiment ? » doublerait
        chaque question."""
        forme = svc_menu.FORMES_PAR_CLE[("confiance", None)]
        assert forme.confirmation is False
        assert forme.destructrice is False
        assert [a.nom for a in forme.arguments] == ["culture", "action", "date", "parcelle"]

    def test_us179_l_arbitrage_avec_la_rotation_est_declare(self):
        """La confiance répond à « je peux semer X sur Y ? » — arbitrage produit
        du 17/09/2026. La rotation garde sa formulation explicite."""
        assert interp._ARBITRAGES[frozenset({"confiance", "rotation"})] == "confiance"
        assert interp.reconnaitre_par_regles(
            "je peux semer des haricots sur la planche nord ?"
        ).commande == "confiance"
        assert interp.reconnaitre_par_regles(
            "vérifie la rotation des tomates sur la planche nord"
        ).commande == "rotation"

    def test_us179_la_lecture_des_arguments_pivote_sur_l_action(self):
        """Une culture et une parcelle en plusieurs mots se lisent sans ambiguïté
        parce que l'action les sépare."""
        assert bot_conf._decouper_arguments(
            ["pomme", "de", "terre", "plantation", "2027-04-20", "planche", "nord"]
        ) == ("pomme de terre", conf.ACTION_PLANTATION, "2027-04-20", "planche nord")

    def test_us179_sans_action_la_commande_tapee_montre_son_usage(self):
        assert bot_conf._decouper_arguments(["haricot"]) is None
