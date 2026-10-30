"""
tests/test_meteo_autre_lieu.py
La météo d'un autre lieu que le potager : « quel temps fait-il à Lyon ? ».

Recette du 30/10/2026 : « quel temps fait-il à Lyon ? » donnait la météo du potager sans un
mot sur Lyon, et « quelle météo à Lyon ? » partait à la cascade des questions, qui répondait
par un fragment de documentation sur les rangs. Le jardinier doit pouvoir interroger son
compagnon sur un lieu qui n'est pas son potager, sans que rien soit enregistré.

Aucun appel réseau : le géocodage et la prévision sont remplacés.
"""
import itertools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from telegram.ext import CommandHandler

from app import bot as bot_module
from app.bot import meteo_jobs
from app.services import interpreteur_commandes as interp
from app.services import meteo_lieu
from app.services.context import TenantContext
from utils import geocodage
from utils.geocodage import Lieu

_CONTEXTE = TenantContext(user_id=1, potager_id=1, role="owner")

LYON = Lieu("Lyon", 45.74846, 4.84671, "Auvergne-Rhône-Alpes", "France", "Europe/Paris")
LYON_ONTARIO = Lieu("Lyon", 43.4, -80.2, "Ontario", "Canada", "America/Toronto")
METEO = {
    "emoji": "☀️", "label": "Ensoleillé", "temp_min": 8, "temp_max": 22, "temp_matin": 12,
    "temp_aprem": 21, "precipitations": 0.0, "proba_pluie": 5, "vent_max_kmh": 18,
    "lever_soleil": "07:12", "coucher_soleil": "19:40", "conseil": "✅ Conditions idéales",
}


def _reponse(corps, statut=200):
    reponse = MagicMock()
    reponse.status_code = statut
    reponse.json.return_value = corps
    reponse.raise_for_status.return_value = None
    return reponse


# ═════════════════════════════════════════════════════════════════════════════
# Le géocodage
# ═════════════════════════════════════════════════════════════════════════════
class TestGeocodage:

    def test_le_lieu_se_dit_avec_sa_region_et_son_pays(self):
        assert LYON.libelle() == "Lyon, Auvergne-Rhône-Alpes, France"
        assert Lieu("Paris", 48.8, 2.3).libelle() == "Paris"

    def test_les_lieux_sont_rendus_dans_l_ordre_d_open_meteo(self):
        corps = {"results": [
            {"name": "Lyon", "latitude": 45.7, "longitude": 4.8, "admin1": "Auvergne-Rhône-Alpes",
             "country": "France", "timezone": "Europe/Paris"},
            {"name": "Lyon", "latitude": 43.4, "longitude": -80.2, "admin1": "Ontario",
             "country": "Canada", "timezone": "America/Toronto"},
        ]}
        with patch.object(geocodage.requests, "get", return_value=_reponse(corps)) as get:
            lieux = geocodage.chercher_lieu("Lyon")
        assert [l.pays for l in lieux] == ["France", "Canada"]
        assert lieux[0].timezone == "Europe/Paris"
        params = get.call_args.kwargs["params"]
        # Les mêmes paramètres que la recherche de ville du frontend.
        assert params["name"] == "Lyon" and params["language"] == "fr" and params["format"] == "json"

    def test_aucun_resultat_est_une_liste_vide(self):
        with patch.object(geocodage.requests, "get", return_value=_reponse({})):
            assert geocodage.chercher_lieu("Zzzzzzqx") == []

    def test_un_service_injoignable_n_est_pas_un_lieu_inconnu(self):
        with patch.object(geocodage.requests, "get", side_effect=requests.ConnectionError("boom")):
            assert geocodage.chercher_lieu("Lyon") is None

    def test_une_entree_malformee_ne_fait_pas_perdre_les_autres(self):
        corps = {"results": [
            {"name": "Sans coordonnées"},
            {"name": "Lyon", "latitude": 45.7, "longitude": 4.8, "country": "France"},
        ]}
        with patch.object(geocodage.requests, "get", return_value=_reponse(corps)):
            assert [l.nom for l in geocodage.chercher_lieu("Lyon")] == ["Lyon"]

    @pytest.mark.parametrize("nom", ["", " ", "L"])
    def test_un_nom_trop_court_n_appelle_pas_le_service(self, nom):
        with patch.object(geocodage.requests, "get") as get:
            assert geocodage.chercher_lieu(nom) == []
        get.assert_not_called()


# ═════════════════════════════════════════════════════════════════════════════
# Le service : lecture seule
# ═════════════════════════════════════════════════════════════════════════════
class TestServiceMeteoLieu:

    def test_la_meteo_est_celle_des_coordonnees_du_lieu(self):
        with patch.object(meteo_lieu.geocodage, "chercher_lieu", return_value=[LYON]), \
             patch.object(meteo_lieu, "fetch_meteo", return_value=METEO) as fetch:
            resultat = meteo_lieu.meteo_du_lieu("Lyon")
        fetch.assert_called_once_with(LYON.latitude, LYON.longitude, "Europe/Paris")
        assert resultat.lieu == LYON and resultat.meteo == METEO
        assert "Ensoleillé" in resultat.commentaire()

    def test_les_homonymes_d_un_autre_pays_sont_signales(self):
        with patch.object(meteo_lieu.geocodage, "chercher_lieu", return_value=[LYON, LYON_ONTARIO]), \
             patch.object(meteo_lieu, "fetch_meteo", return_value=METEO):
            resultat = meteo_lieu.meteo_du_lieu("Lyon")
        assert resultat.lieu == LYON
        assert resultat.homonymes() == "Lyon, Ontario, Canada"

    def test_un_nom_voisin_n_est_pas_un_homonyme(self):
        """Le géocodage rend aussi « Lyons » ou « Saint-Étienne-du-Rouvray » : pas des « Lyon »."""
        voisin = Lieu("Lyons", 32.2, -82.3, "Géorgie", "États-Unis")
        long = Lieu("Lyon-la-Forêt", 49.4, 1.5, "Normandie", "France")
        with patch.object(meteo_lieu.geocodage, "chercher_lieu",
                          return_value=[LYON, voisin, LYON_ONTARIO, long]), \
             patch.object(meteo_lieu, "fetch_meteo", return_value=METEO):
            assert meteo_lieu.meteo_du_lieu("Lyon").homonymes() == "Lyon, Ontario, Canada"

    def test_un_nom_sans_equivoque_ne_signale_rien(self):
        with patch.object(meteo_lieu.geocodage, "chercher_lieu", return_value=[LYON]), \
             patch.object(meteo_lieu, "fetch_meteo", return_value=METEO):
            assert meteo_lieu.meteo_du_lieu("Lyon").homonymes() == ""

    def test_lieu_introuvable(self):
        with patch.object(meteo_lieu.geocodage, "chercher_lieu", return_value=[]), \
             patch.object(meteo_lieu, "fetch_meteo") as fetch:
            with pytest.raises(meteo_lieu.LieuIntrouvable):
                meteo_lieu.meteo_du_lieu("Zzzzzzqx")
        fetch.assert_not_called()

    @pytest.mark.parametrize("geocodage_rend, meteo_rend", [(None, METEO), ([LYON], None)])
    def test_service_indisponible(self, geocodage_rend, meteo_rend):
        with patch.object(meteo_lieu.geocodage, "chercher_lieu", return_value=geocodage_rend), \
             patch.object(meteo_lieu, "fetch_meteo", return_value=meteo_rend):
            with pytest.raises(meteo_lieu.ServiceIndisponible):
                meteo_lieu.meteo_du_lieu("Lyon")

    def test_le_service_ne_touche_pas_la_base(self):
        """La météo d'un lieu de passage ne s'enregistre pas : le module n'importe aucune base."""
        import ast

        arbre = ast.parse(open(meteo_lieu.__file__, encoding="utf-8").read())
        importes = {
            alias.name for noeud in ast.walk(arbre)
            if isinstance(noeud, (ast.Import, ast.ImportFrom)) for alias in noeud.names
        } | {
            noeud.module for noeud in ast.walk(arbre)
            if isinstance(noeud, ast.ImportFrom) and noeud.module
        }
        assert not importes & {"SessionLocal", "save_meteo_observation", "database", "database.db"}


# ═════════════════════════════════════════════════════════════════════════════
# La reconnaissance : « quel temps fait-il à Lyon ? » est une commande, pas une question de savoir
# ═════════════════════════════════════════════════════════════════════════════
def _lecture(phrase: str):
    resultat = interp.interpreter(phrase, None)
    assert isinstance(resultat, interp.CommandeInterpretee), phrase
    return resultat


class TestReconnaissance:

    @pytest.mark.parametrize("phrase, lieu", [
        ("quel temps fait il à Lyon ?", "Lyon"),            # le journal du 30/10
        ("quelle météo à Lyon ?", "Lyon"),                   # le journal du 30/10
        ("quelle est la météo à Lyon ?", "Lyon"),
        ("quel temps fait-il à Lyon", "Lyon"),
        ("la météo de Lyon", "Lyon"),
        ("météo à Lyon stp", "Lyon"),
        ("quel temps fait-il à Lyon aujourd'hui ?", "Lyon"),
        ("il va pleuvoir à Marseille ?", "Marseille"),
        ("quelle est la météo à Saint-Étienne ?", "Saint-Étienne"),
        ("quel temps fait-il à Bourg-en-Bresse ?", "Bourg-en-Bresse"),
        ("météo à La Rochelle", "La Rochelle"),
        ("il va pleuvoir au Havre ?", "Le Havre"),
        ("quel temps fait-il aux Sables-d'Olonne ?", "Les Sables-d'Olonne"),
        ("quel temps fait-il à L'Isle-Adam ?", "L'Isle-Adam"),
    ])
    def test_le_lieu_dit_devient_l_argument_de_la_commande(self, phrase, lieu):
        commande = _lecture(phrase)
        assert (commande.commande, commande.regle) == ("meteo", "meteo")
        assert commande.valeurs == {"lieu": lieu}
        assert commande.precision is None and commande.complete
        assert commande.commande_equivalente() == f"/meteo {lieu}"

    @pytest.mark.parametrize("phrase", [
        "quel temps fait-il ?", "la météo", "quelle météo ?", "météo du jour",
        "quel temps fait-il aujourd'hui ?",
    ])
    def test_sans_lieu_c_est_la_meteo_du_potager(self, phrase):
        commande = _lecture(phrase)
        assert commande.valeurs == {} and commande.precision is None
        assert commande.commande_equivalente() == "/meteo"

    @pytest.mark.parametrize("phrase", [
        "quel temps fait-il dans la serre ?", "quel temps fait-il dans mon potager ?",
        "météo dans le tunnel", "quel temps fait-il chez moi ?".replace("chez moi", "ici"),
    ])
    def test_une_partie_du_potager_n_est_pas_un_lieu_a_chercher(self, phrase):
        """« dans la serre » ne va pas chercher un village nommé Serre."""
        assert _lecture(phrase).valeurs == {}

    def test_un_autre_jour_est_signale(self):
        """La météo donnée est celle du jour : « demain » n'est pas perdu en silence."""
        commande = _lecture("quel temps fait-il à Lyon demain ?")
        assert commande.valeurs == {"lieu": "Lyon"}
        assert commande.precision.mot == "demain" and not commande.complete

    def test_un_lieu_sans_preposition_est_signale_et_la_note_dit_comment_le_dire(self):
        commande = _lecture("météo Lyon")
        assert commande.precision.mot == "Lyon"
        assert "« à Lyon »" in commande.precision.question()

    def test_la_phrase_n_est_plus_une_question_de_savoir(self):
        """Avant : `phrase interrogative → cascade des questions` → un fragment sur les rangs."""
        with patch.object(interp, "_mode_agent", return_value="actif"), \
             patch("app.services.agent.interpreteur_agent.proposer",
                   side_effect=AssertionError("l'agent n'a pas à être consulté")):
            resultat = interp.interpreter("quelle météo à Lyon ?", _CONTEXTE)
        assert isinstance(resultat, interp.CommandeInterpretee)
        assert resultat.valeurs == {"lieu": "Lyon"}

    def test_le_lieu_est_un_argument_facultatif_du_catalogue(self):
        forme = interp.FORMES_PAR_CLE[("meteo", None)]
        assert [(a.nom, a.obligatoire) for a in forme.arguments] == [("lieu", False)]
        assert not forme.confirmation  # une consultation : aucune écriture à confirmer


# ═════════════════════════════════════════════════════════════════════════════
# La commande : /meteo Lyon
# ═════════════════════════════════════════════════════════════════════════════
def _update():
    update = MagicMock()
    update.effective_user.id = 42
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    update.effective_message = update.message
    update.callback_query = None
    return update


def _ctx(args=None, handler=None):
    ctx = MagicMock()
    ctx.user_data = {}
    ctx.args = args if args is not None else []
    ctx.application.handlers = {0: [CommandHandler("meteo", handler)]} if handler is not None else {}
    return ctx


@pytest.fixture
def journal():
    lignes = itertools.count(10)

    def _ecrire(ctx, commande, issue, log_id=None):
        return log_id if log_id is not None else next(lignes)

    with patch.object(interp, "persister_journal", side_effect=_ecrire) as faux:
        yield faux


class TestCommande:

    @pytest.mark.asyncio
    async def test_la_phrase_execute_slash_meteo_lyon_directement(self, journal):
        """Une consultation : rien à confirmer, la commande équivalente est rappelée puis exécutée."""
        handler = AsyncMock()
        ctx = _ctx(handler=handler)
        update = _update()
        with patch.object(bot_module, "current_context", return_value=_CONTEXTE), \
             patch.object(bot_module, "_resoudre_noms_parcelle", side_effect=lambda c: c):
            await bot_module._interp_proposer(update, ctx, _lecture("quel temps fait il à Lyon ?"))
        handler.assert_awaited_once()
        assert ctx.args == ["Lyon"]
        assert "/meteo Lyon" in str(update.message.reply_text.await_args_list[0].args[0])

    @pytest.mark.asyncio
    async def test_le_handler_donne_la_meteo_du_lieu_sans_rien_enregistrer(self):
        resultat = meteo_lieu.MeteoLieu(LYON, METEO, (LYON_ONTARIO,))
        msg = AsyncMock()
        update = _update()
        update.message.reply_text = AsyncMock(return_value=msg)
        with patch.object(meteo_jobs.svc_meteo_lieu, "meteo_du_lieu", return_value=resultat), \
             patch.object(meteo_jobs, "save_meteo_observation") as sauver, \
             patch.object(meteo_jobs, "SessionLocal") as base:
            await meteo_jobs.cmd_meteo(update, _ctx(["Lyon"]))
        sauver.assert_not_called()
        base.assert_not_called()
        texte = msg.edit_text.await_args.args[0]
        assert "Lyon, Auvergne-Rhône-Alpes, France" in texte
        assert "Ensoleillé" in texte and "Min 8°C / Max 22°C" in texte
        assert "Il existe aussi : Lyon, Ontario, Canada" in texte
        assert "Non enregistrée" in texte

    @pytest.mark.asyncio
    async def test_un_lieu_inconnu_est_dit_sans_deviner(self):
        msg = AsyncMock()
        update = _update()
        update.message.reply_text = AsyncMock(return_value=msg)
        with patch.object(meteo_jobs.svc_meteo_lieu, "meteo_du_lieu",
                          side_effect=meteo_lieu.LieuIntrouvable("Zzzzqx")):
            await meteo_jobs.cmd_meteo(update, _ctx(["Zzzzqx"]))
        assert "Je ne trouve pas de lieu nommé « Zzzzqx »" in msg.edit_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_un_service_injoignable_est_dit(self):
        msg = AsyncMock()
        update = _update()
        update.message.reply_text = AsyncMock(return_value=msg)
        with patch.object(meteo_jobs.svc_meteo_lieu, "meteo_du_lieu",
                          side_effect=meteo_lieu.ServiceIndisponible("x")):
            await meteo_jobs.cmd_meteo(update, _ctx(["Lyon"]))
        assert "Impossible de récupérer la météo de ce lieu" in msg.edit_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_un_lieu_en_plusieurs_mots_reste_un_seul_lieu(self):
        msg = AsyncMock()
        update = _update()
        update.message.reply_text = AsyncMock(return_value=msg)
        with patch.object(meteo_jobs.svc_meteo_lieu, "meteo_du_lieu",
                          return_value=meteo_lieu.MeteoLieu(LYON, METEO)) as service:
            await meteo_jobs.cmd_meteo(update, _ctx(["La Rochelle"]))
            await meteo_jobs.cmd_meteo(update, _ctx(["La", "Rochelle"]))
        assert [appel.args[0] for appel in service.call_args_list] == ["La Rochelle", "La Rochelle"]

    def test_sans_argument_le_lieu_demande_est_vide(self):
        assert meteo_jobs._lieu_demande(_ctx([])) == ""
        assert meteo_jobs._lieu_demande(MagicMock()) == ""  # un contexte sans liste d'arguments


# ═════════════════════════════════════════════════════════════════════════════
# L'aide : /help meteo, la liste générale, le menu natif — et le corpus qui la double
# ═════════════════════════════════════════════════════════════════════════════
class TestAide:

    @staticmethod
    async def _aide(*args):
        from app.bot import aide

        update = _update()
        ctx = MagicMock()
        ctx.args = list(args)
        await aide.cmd_help(update, ctx)
        return str(update.message.reply_text.await_args.args[0])

    @pytest.mark.asyncio
    @pytest.mark.parametrize("mot_cle", ["meteo", "météo", "Meteo"])
    async def test_help_meteo_donne_les_deux_usages(self, mot_cle):
        texte = await self._aide(mot_cle)
        assert "Aide — Météo" in texte
        assert "/meteo\n" in texte and "/meteo Lyon" in texte
        assert "quel temps fait-il à Lyon ?" in texte
        assert "rien n'est enregistré" in texte           # lecture seule, dit
        assert "« demain » est signalé" in texte          # la limite, dite

    @pytest.mark.asyncio
    async def test_la_liste_generale_montre_l_argument_de_la_ville(self):
        texte = await self._aide()
        assert "/meteo [ville]" in texte
        assert "meteo" in texte.split("Aide ciblée par domaine")[1].split("Exemple")[0]

    def test_meteo_est_un_domaine_d_aide_couvert_par_le_corpus(self):
        """`/help` annonce « meteo » : une fiche du corpus doit le couvrir (US-099 / CA7)."""
        from app.bot import aide
        from tools import controler_aide_corpus

        assert "meteo" in aide._HELP_DOMAINES
        fiche = open("data/connaissance/doc_app/enregistrer-un-geste.md", encoding="utf-8").read()
        assert "domaines_aide: meteo" in fiche.split("---")[1]
        assert controler_aide_corpus.main([]) == 0

    def test_le_menu_natif_dit_que_la_meteo_a_deux_usages(self):
        from app.services import menu_commandes

        description = menu_commandes.DESCRIPTIONS_MENU["meteo"] if hasattr(
            menu_commandes, "DESCRIPTIONS_MENU") else None
        if description is None:  # le nom de la table n'est pas un contrat : on la retrouve par sa valeur
            description = next(v for v in vars(menu_commandes).values()
                               if isinstance(v, dict) and "meteo" in v and isinstance(v["meteo"], str))["meteo"]
        assert "ville" in description and len(description) <= 256
