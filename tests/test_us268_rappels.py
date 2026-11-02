"""
tests/test_us268_rappels.py
[US-268] Proposer et tenir des rappels de suivi : une proposition datée par le référentiel,
une écriture seulement après confirmation, un signal à l'échéance.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import sessionmaker

from app import config
from app.bot import commandes_rappels
from app.services import calendrier_cultural as cal
from app.services import interpreteur_commandes as interp
from app.services.agent import catalogue_outils
from app.services.compagnon import rappels as svc
from app.services.compagnon import veilleur
from app.services.compagnon import veilleur_passage as passage
from app.services.compagnon.distributeur import MODE_COUPE
from app.services.compagnon.redaction_signal import GENRE_RAPPEL, SignalARediger, gabarit
from app.services.context import TenantContext
from database.models import (
    CultureConfig, DureeCulturale, Evenement, ItineraireCultural, PotagerMembre, Rappel, ReferentielSource,
)

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUJOURD_HUI = date(2026, 10, 27)
MAINTENANT = datetime(2026, 11, 3, 9, 30)


@pytest.fixture(autouse=True)
def _membre_et_envoi(test_db, monkeypatch):
    test_db.add(PotagerMembre(user_id=1, potager_id=1, role="owner"))
    test_db.commit()
    monkeypatch.setattr(config, "COMPAGNON_PROACTIF", True)


@pytest.fixture
def radis(test_db):
    """Le référentiel dit : levée du radis en 4 à 7 jours (borne haute : 7)."""
    test_db.add(ReferentielSource(id=1, code="test", libelle="Test", licence="CC0",
                                  attribution="Valeurs de test", partageable=True, importee=True))
    fiche = CultureConfig(nom="radis", type_organe_recolte="racine")
    test_db.add(fiche)
    test_db.flush()
    itineraire = ItineraireCultural(culture_id=fiche.id, nom="standard",
                                    nom_normalise=cal.normaliser_itineraire("standard"), source_id=1)
    test_db.add(itineraire)
    test_db.flush()
    test_db.add(DureeCulturale(itineraire_id=itineraire.id, etape=cal.ETAPE_LEVEE, jours_min=4, jours_max=7, source_id=1))
    test_db.commit()


def _geste(db, action="semis", culture="radis", jour=AUJOURD_HUI) -> Evenement:
    evenement = Evenement(type_action=action, culture=culture, date=datetime.combine(jour, datetime.min.time()),
                          potager_id=1, quantite=2, unite="rangs")
    db.add(evenement)
    db.commit()
    return evenement


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — La proposition vient du référentiel
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1Proposition:
    def test_semis_de_radis_le_27_octobre_propose_le_3_novembre(self, test_db, radis):
        evenement = _geste(test_db)
        proposition = svc.proposer_pour_evenement(test_db, CTX, evenement.id, AUJOURD_HUI)
        assert proposition.echeance == date(2026, 11, 3)
        assert "levée" in proposition.objet and "radis" in proposition.objet
        assert (proposition.cible_type, proposition.cible_id) == ("evenement", evenement.id)

    def test_la_proposition_n_ecrit_rien(self, test_db, radis):
        svc.proposer_pour_evenement(test_db, CTX, _geste(test_db).id, AUJOURD_HUI)
        assert test_db.query(Rappel).count() == 0

    def test_sans_duree_au_referentiel_pas_de_proposition(self, test_db):
        assert svc.proposer_pour_evenement(test_db, CTX, _geste(test_db, culture="inconnue").id, AUJOURD_HUI) is None

    def test_un_geste_sans_rappel_possible_n_en_propose_pas(self, test_db, radis):
        assert svc.proposer_pour_evenement(test_db, CTX, _geste(test_db, action="arrosage").id, AUJOURD_HUI) is None

    def test_une_echeance_deja_passee_n_est_pas_proposee(self, test_db, radis):
        vieux = _geste(test_db, jour=AUJOURD_HUI - timedelta(days=30))
        assert svc.proposer_pour_evenement(test_db, CTX, vieux.id, AUJOURD_HUI) is None

    def test_pas_de_proposition_si_le_distributeur_est_eteint(self, test_db, radis, monkeypatch):
        monkeypatch.setattr(config, "COMPAGNON_PROACTIF", False)
        assert svc.proposer_pour_evenement(test_db, CTX, _geste(test_db).id, AUJOURD_HUI) is None

    def test_un_geste_d_un_autre_potager_n_est_pas_lu(self, test_db, radis):
        autre = TenantContext(user_id=1, potager_id=2, role="owner")
        assert svc.proposer_pour_evenement(test_db, autre, _geste(test_db).id, AUJOURD_HUI) is None


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — Une écriture : seule `programmer` écrit
# ═════════════════════════════════════════════════════════════════════════════
class TestCA2Ecriture:
    def test_programmer_ecrit_le_rappel_a_9_h(self, test_db):
        rappel = svc.programmer(test_db, CTX, "tailler les tomates", date(2026, 11, 7))
        assert rappel.etat == "programme" and rappel.echeance_le == datetime(2026, 11, 7, 9, 0)
        assert rappel.user_id == 1 and rappel.potager_id == 1

    def test_programmer_deux_fois_le_meme_geste_ne_double_pas(self, test_db, radis):
        evenement = _geste(test_db)
        premier = svc.programmer(test_db, CTX, "levée", date(2026, 11, 3), "evenement", evenement.id)
        second = svc.programmer(test_db, CTX, "levée", date(2026, 11, 3), "evenement", evenement.id)
        assert premier.id == second.id and test_db.query(Rappel).count() == 1

    def test_un_rappel_deja_programme_n_est_plus_propose(self, test_db, radis):
        evenement = _geste(test_db)
        svc.programmer(test_db, CTX, "levée", date(2026, 11, 3), "evenement", evenement.id)
        assert svc.proposer_pour_evenement(test_db, CTX, evenement.id, AUJOURD_HUI) is None

    @pytest.mark.parametrize("objet", ["", "   ", None])
    def test_un_objet_vide_est_refuse(self, test_db, objet):
        with pytest.raises(svc.RappelError):
            svc.programmer(test_db, CTX, objet, date(2026, 11, 7))

    def test_un_objet_trop_long_est_refuse(self, test_db):
        with pytest.raises(svc.RappelError, match="trop long"):
            svc.programmer(test_db, CTX, "a" * 201, date(2026, 11, 7))

    def test_trente_rappels_en_attente_au_plus(self, test_db):
        for i in range(svc.RAPPELS_MAX):
            svc.programmer(test_db, CTX, f"rappel {i}", date(2026, 11, 7))
        with pytest.raises(svc.RappelError, match="déjà"):
            svc.programmer(test_db, CTX, "un de trop", date(2026, 11, 7))

    def test_programmer_rappel_est_un_outil_d_ecriture_confirme(self):
        [outil] = [o for o in catalogue_outils.outils() if o.nom == "programmer_rappel"]
        [forme] = outil.formes
        assert forme.cle == ("rappel", "programmer") and forme.confirmation and not forme.destructrice

    def test_la_consultation_des_rappels_ne_demande_pas_de_confirmation(self):
        assert interp.FORMES_PAR_CLE[("rappel", "lister")].confirmation is False


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Le rappel libre : la date est résolue par le code
# ═════════════════════════════════════════════════════════════════════════════
class TestCA3RappelLibre:
    @pytest.mark.parametrize("morceaux,objet,jour", [
        (["tailler", "les", "tomates", "samedi"], "tailler les tomates", date(2026, 11, 7)),
        (["tailler les tomates", "samedi"], "tailler les tomates", date(2026, 11, 7)),
        (["arroser", "dans", "3", "jours"], "arroser", date(2026, 11, 4)),
        (["arroser", "le", "12", "novembre"], "arroser", date(2026, 11, 12)),
        (["tailler", "les", "tomates", "pour", "samedi"], "tailler les tomates", date(2026, 11, 7)),
        (["tailler les tomates", "2026-11-10"], "tailler les tomates", date(2026, 11, 10)),
    ])
    def test_objet_et_jour(self, morceaux, objet, jour):
        assert svc.objet_et_jour(morceaux, date(2026, 11, 1)) == (objet, jour)

    @pytest.mark.parametrize("morceaux", [["arroser"], ["arroser", "bientot"], []])
    def test_sans_jour_reconnu_le_code_ne_devine_pas(self, morceaux):
        with pytest.raises(svc.RappelError):
            svc.objet_et_jour(morceaux, date(2026, 11, 1))

    def test_une_date_passee_est_refusee(self):
        with pytest.raises(svc.RappelError, match="passée"):
            svc.objet_et_jour(["tailler", "2026-10-01"], date(2026, 11, 1))

    def test_une_date_trop_lointaine_est_refusee(self):
        with pytest.raises(svc.RappelError, match="loin"):
            svc.objet_et_jour(["tailler", "2030-01-01"], date(2026, 11, 1))

    def test_la_regle_lit_une_phrase_dite(self):
        commande = interp.interpreter("rappelle-moi de tailler les tomates samedi", autoriser_modele=False)
        assert commande.forme.cle == ("rappel", "programmer")
        assert commande.valeurs["objet"] == "tailler les tomates"
        assert date.fromisoformat(commande.valeurs["date"]) > date.today() - timedelta(days=1)

    def test_la_regle_renonce_sans_jour(self):
        commande = interp.interpreter("rappelle-moi de tailler les tomates", autoriser_modele=False)
        assert commande is None or commande.forme.cle != ("rappel", "programmer")

    def test_la_regle_de_liste(self):
        assert interp.interpreter("mes rappels", autoriser_modele=False).forme.cle == ("rappel", "lister")

    def test_rappels_de_quelque_chose_n_est_pas_la_liste(self):
        commande = interp.interpreter("rappels de vaccins", autoriser_modele=False)
        assert commande is None or commande.forme.cle != ("rappel", "lister")


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — À l'échéance, le veilleur produit un signal « rappels »
# ═════════════════════════════════════════════════════════════════════════════
def _etat(*rappels) -> veilleur.EtatPotager:
    return veilleur.EtatPotager(potager_id=1, maintenant=MAINTENANT, rappels=tuple(rappels))


def _programme(rappel_id=7, echeance=datetime(2026, 11, 3, 9, 0)) -> veilleur.RappelProgramme:
    return veilleur.RappelProgramme(rappel_id, "voir où en est la levée des radis", echeance, "evenement", 12)


class TestCA4Signal:
    def test_un_rappel_echu_donne_un_signal_immediat(self):
        [signal] = veilleur.detecter_rappels_echus(_etat(_programme()))
        assert signal.theme == veilleur.THEME_RAPPELS and signal.priorite == veilleur.PRIORITE_IMMEDIATE
        assert signal.cle_unique == "rappel:7"
        assert signal.donnees["objet"] == "voir où en est la levée des radis"
        assert signal.expire_le > MAINTENANT

    def test_un_rappel_a_venir_ne_donne_rien(self):
        assert veilleur.detecter_rappels_echus(_etat(_programme(echeance=datetime(2026, 11, 4, 9, 0)))) == []

    def test_le_detecteur_fait_partie_du_passage_horaire(self):
        assert veilleur.detecter_rappels_echus in veilleur.DETECTEURS_HORAIRES

    def test_le_signal_est_redige_avec_l_objet(self):
        [signal] = veilleur.detecter_rappels_echus(_etat(_programme()))
        a_rediger = SignalARediger(signal.theme, signal.cle_unique, signal.expire_le, signal.donnees)
        assert a_rediger.genre == GENRE_RAPPEL
        assert "levée des radis" in gabarit(a_rediger, MAINTENANT.date())

    def test_le_passage_lit_les_echus_et_les_clot(self, test_db):
        echu = svc.programmer(test_db, CTX, "voir la levée", date(2026, 11, 3))
        futur = svc.programmer(test_db, CTX, "plus tard", date(2026, 11, 20))
        lus = passage.rappels_echus(test_db, 1, MAINTENANT)
        assert [r.rappel_id for r in lus] == [echu.id]
        assert svc.marquer_echus(test_db, 1, [r.rappel_id for r in lus]) == 1
        test_db.refresh(echu), test_db.refresh(futur)
        assert (echu.etat, futur.etat) == ("echu", "programme")
        assert passage.rappels_echus(test_db, 1, MAINTENANT) == ()


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — /rappels liste et annule
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5ListeEtAnnulation:
    def test_les_rappels_a_venir_dans_l_ordre(self, test_db):
        svc.programmer(test_db, CTX, "b", date(2026, 11, 9))
        svc.programmer(test_db, CTX, "a", date(2026, 11, 5))
        assert [r.objet for r in svc.lister(test_db, CTX)] == ["a", "b"]

    def test_annuler_retire_le_rappel_de_la_liste(self, test_db):
        rappel = svc.programmer(test_db, CTX, "a", date(2026, 11, 5))
        svc.annuler(test_db, CTX, rappel.id)
        assert svc.lister(test_db, CTX) == [] and test_db.query(Rappel).get(rappel.id).etat == "annule"

    def test_un_rappel_annule_ne_donne_pas_de_signal(self, test_db):
        rappel = svc.programmer(test_db, CTX, "a", date(2026, 11, 3))
        svc.annuler(test_db, CTX, rappel.id)
        assert passage.rappels_echus(test_db, 1, MAINTENANT) == ()

    def test_on_n_annule_pas_le_rappel_d_un_autre_potager_ni_un_rappel_inconnu(self, test_db):
        rappel = svc.programmer(test_db, CTX, "a", date(2026, 11, 5))
        with pytest.raises(svc.RappelError):
            svc.annuler(test_db, TenantContext(user_id=1, potager_id=2, role="owner"), rappel.id)
        with pytest.raises(svc.RappelError):
            svc.annuler(test_db, CTX, 9999)

    def test_un_rappel_echu_n_est_plus_annulable(self, test_db):
        rappel = svc.programmer(test_db, CTX, "a", date(2026, 11, 3))
        svc.marquer_echus(test_db, 1, [rappel.id])
        with pytest.raises(svc.RappelError):
            svc.annuler(test_db, CTX, rappel.id)

    def test_la_commande_rappels_est_un_alias_de_la_liste(self):
        from app.services import menu_commandes
        assert menu_commandes.ALIAS_COMMANDES["rappels"] == ("rappel", "lister")


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — Thème coupé : aucune proposition
# ═════════════════════════════════════════════════════════════════════════════
class TestCA6ThemeCoupe:
    def test_theme_coupe_aucune_proposition(self, test_db, radis):
        membre = test_db.query(PotagerMembre).filter_by(user_id=1, potager_id=1).one()
        membre.proactivite_compagnon = {"rappels": {"mode": MODE_COUPE}}
        test_db.commit()
        assert svc.theme_coupe(test_db, CTX) is True
        assert svc.proposer_pour_evenement(test_db, CTX, _geste(test_db).id, AUJOURD_HUI) is None

    def test_theme_actif_par_defaut(self, test_db):
        assert svc.theme_coupe(test_db, CTX) is False


# ═════════════════════════════════════════════════════════════════════════════
# Telegram — proposition, clic, liste
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def bot(test_db, test_engine, monkeypatch):
    fabrique = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    monkeypatch.setattr(commandes_rappels, "SessionLocal", fabrique)
    monkeypatch.setattr(commandes_rappels, "current_context", lambda: CTX)
    return fabrique


def _update(data: str | None = None):
    update = MagicMock()
    message = MagicMock(reply_text=AsyncMock())
    update.message = message
    if data is None:
        update.callback_query = None
    else:
        update.callback_query = MagicMock(data=data, answer=AsyncMock(), edit_message_text=AsyncMock(), message=message)
    return update, message


class TestTelegram:
    @pytest.mark.asyncio
    async def test_la_proposition_a_deux_boutons_et_n_ecrit_rien(self, test_db, radis, bot, monkeypatch):
        monkeypatch.setattr(svc, "date", type("D", (date,), {"today": staticmethod(lambda: AUJOURD_HUI)}))
        evenement = _geste(test_db)
        update, message = _update()
        await commandes_rappels.proposer_rappel(update, [({}, evenement.id)])
        texte = message.reply_text.call_args.args[0]
        clavier = message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard[0]
        assert "3 novembre" in texte and "levée des radis" in texte
        assert [b.text for b in clavier] == ["Oui, rappelle-moi", "Pas la peine"]
        assert test_db.query(Rappel).count() == 0

    @pytest.mark.asyncio
    async def test_aucune_proposition_si_le_distributeur_est_eteint(self, test_db, radis, bot, monkeypatch):
        monkeypatch.setattr(config, "COMPAGNON_PROACTIF", False)
        update, message = _update()
        await commandes_rappels.proposer_rappel(update, [({}, _geste(test_db).id)])
        message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_le_clic_oui_cree_le_rappel_du_3_novembre(self, test_db, radis, bot, monkeypatch):
        monkeypatch.setattr(svc, "date", type("D", (date,), {"today": staticmethod(lambda: AUJOURD_HUI)}))
        evenement = _geste(test_db)
        update, _ = _update(f"rap:o:{evenement.id}")
        await commandes_rappels._rappel_cb(update, MagicMock())
        [rappel] = test_db.query(Rappel).all()
        assert rappel.echeance_le.date() == date(2026, 11, 3) and rappel.cible_id == evenement.id

    @pytest.mark.asyncio
    async def test_le_clic_pas_la_peine_n_ecrit_rien(self, test_db, radis, bot):
        update, _ = _update(f"rap:n:{_geste(test_db).id}")
        await commandes_rappels._rappel_cb(update, MagicMock())
        assert test_db.query(Rappel).count() == 0

    @pytest.mark.asyncio
    async def test_un_double_clic_ne_double_pas_le_rappel(self, test_db, radis, bot, monkeypatch):
        monkeypatch.setattr(svc, "date", type("D", (date,), {"today": staticmethod(lambda: AUJOURD_HUI)}))
        evenement = _geste(test_db)
        for _ in range(2):
            update, _ = _update(f"rap:o:{evenement.id}")
            await commandes_rappels._rappel_cb(update, MagicMock())
        assert test_db.query(Rappel).count() == 1

    @pytest.mark.asyncio
    async def test_la_commande_programme_un_rappel_libre(self, test_db, bot):
        update, message = _update()
        ctx = MagicMock(args=["programmer", "tailler les tomates", (date.today() + timedelta(days=3)).isoformat()])
        await commandes_rappels.cmd_rappel(update, ctx)
        [rappel] = test_db.query(Rappel).all()
        assert rappel.objet == "tailler les tomates"
        assert "C'est noté" in message.reply_text.call_args.args[0]

    @pytest.mark.asyncio
    async def test_la_commande_sans_jour_ne_cree_rien(self, test_db, bot):
        update, message = _update()
        await commandes_rappels.cmd_rappel(update, MagicMock(args=["programmer", "tailler", "bientot"]))
        assert test_db.query(Rappel).count() == 0
        assert "pour quand" in message.reply_text.call_args.args[0]

    @pytest.mark.asyncio
    async def test_la_liste_propose_d_annuler_et_l_annulation_la_met_a_jour(self, test_db, bot):
        rappel = svc.programmer(test_db, CTX, "tailler les tomates", date.today() + timedelta(days=3))
        update, message = _update()
        await commandes_rappels.cmd_rappels(update, MagicMock(args=[]))
        clavier = message.reply_text.call_args.kwargs["reply_markup"].inline_keyboard
        assert clavier[0][0].callback_data == f"rap:a:{rappel.id}"
        update, _ = _update(f"rap:a:{rappel.id}")
        await commandes_rappels._rappel_cb(update, MagicMock())
        test_db.expire_all()
        assert test_db.query(Rappel).get(rappel.id).etat == "annule"

    @pytest.mark.asyncio
    async def test_liste_vide(self, test_db, bot):
        update, message = _update()
        await commandes_rappels.cmd_rappels(update, MagicMock(args=[]))
        assert message.reply_text.call_args.args[0] == commandes_rappels.TEXTE_AUCUN


# ═════════════════════════════════════════════════════════════════════════════
# Câblage — le bot appelle la proposition, enregistre les commandes et les boutons
# ═════════════════════════════════════════════════════════════════════════════
class TestCablage:
    def test_la_proposition_suit_le_compte_rendu_d_un_geste_enregistre(self):
        from app import bot as bot_module

        source = "".join(__import__("inspect").getsource(m) for m in bot_module._SOUS_MODULES)
        assert "await proposer_rappel(update, saved_items)" in source

    def test_les_commandes_et_les_boutons_sont_enregistres(self):
        from app import bot as bot_module

        app = bot_module._construire_application()
        commandes = {c for h in app.handlers[0] for c in getattr(h, "commands", ())}
        motifs = {getattr(getattr(h, "pattern", None), "pattern", "") for h in app.handlers[0]}
        assert {"rappel", "rappels"} <= commandes and "^rap:" in motifs

    def test_la_parite_des_commandes_reste_verte(self):
        from app import bot as bot_module
        from app.services import menu_commandes

        app = bot_module._construire_application()
        noms = {c for h in app.handlers[0] for c in getattr(h, "commands", ())}
        assert menu_commandes.controler_parite(noms) == []
