"""
tests/test_us174_bioagresseurs_fiche_culture.py
[US-174] Faire entrer les bioagresseurs dans la fiche courte d'une culture

Couverture des critères d'acceptance CA1 → CA13.

Le vrai sujet de cette US n'est pas l'affichage — il tient en dix lignes — mais
le passage de `generer_fiche_courte` d'un service GLOBAL à un service SCOPÉ au
potager (CA6), sans rien rendre privé de ce qui ne l'était pas (CA7). C'est là
que se logerait une fuite entre potagers, et c'est ce que `TestCA6Isolation`
vérifie dans les deux sens.
"""
from unittest.mock import ANY, AsyncMock, MagicMock, patch

import pytest

from app.services import bioagresseurs as svc_bio
from app.services import fiche_culture as svc_fiche
from app.services import referentiel_sources as svc_sources
from app.services.context import TenantContext
from database.models import CultureConfig, FamilleBotanique

CTX = TenantContext(user_id=1, potager_id=1, role="owner")
AUTRE_POTAGER = 2


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def db(test_db):
    svc_sources.semer_sources_socle(test_db)
    return test_db


def _seed_culture(db, nom, famille=None, description=None):
    cfg = CultureConfig(
        nom=nom, type_organe_recolte="reproducteur", description_agronomique=description
    )
    if famille is not None:
        cfg.famille_rel = famille
    db.add(cfg)
    db.commit()
    return cfg


def _seed_famille(db, nom, delai_retour_annees=None):
    from app.services import familles as svc_familles
    famille = FamilleBotanique(
        nom=nom, nom_normalise=svc_familles.normaliser_famille(nom),
        delai_retour_annees=delai_retour_annees,
    )
    db.add(famille)
    db.commit()
    return famille


def _rattacher(db, culture, nom, categorie, frequence, periode=None, potager_id=None):
    svc_bio.enregistrer_bioagresseur(db, nom, categorie, potager_id=potager_id)
    svc_bio.rattacher(
        db, culture, nom, frequence, periode_risque=periode, potager_id=potager_id
    )


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — La rubrique
# ═════════════════════════════════════════════════════════════════════════════

class TestCA1Rubrique:
    def test_us174_la_fiche_porte_les_bioagresseurs_ordonnes_par_frequence(self, db):
        """[Gherkin: La fiche dit ce qui attaque la culture] Les plus fréquents
        d'abord — l'ordre métier d'US-162, jamais recalculé ici."""
        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "pourriture grise", "champignon", "rare")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")
        _rattacher(db, "tomate", "aleurode", "insecte", "occasionnel")

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert [b.frequence for b in fiche.bioagresseurs] == [
            "courant", "occasionnel", "rare",
        ]
        assert fiche.bioagresseurs[0].nom_commun_fr == "mildiou"

    def test_us174_la_periode_est_portee_quand_elle_est_connue(self, db):
        """[CA2] Une période renseignée est restituée ; une période absente reste
        None — le bot n'affiche alors rien, plutôt que « non renseignée » cinq
        fois de suite."""
        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant", periode="juin-septembre")
        _rattacher(db, "tomate", "aleurode", "insecte", "courant")

        par_nom = {b.nom_commun_fr: b for b in
                   svc_fiche.generer_fiche_courte(db, "tomate").bioagresseurs}

        assert par_nom["mildiou"].periode_risque == "juin-septembre"
        assert par_nom["aleurode"].periode_risque is None

    def test_us174_la_fiche_reste_lisible_sans_bioagresseur(self, db):
        """[CA7] Rien n'est cassé pour une culture qui n'en a aucun : le reste de
        la fiche est rendu à l'identique."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "aubergine", famille=solanacee, description="Plante de soleil")

        fiche = svc_fiche.generer_fiche_courte(db, "aubergine")

        assert fiche.famille == "Solanacée"
        assert fiche.delai_retour_annees == 4
        assert fiche.description_agronomique == "Plante de soleil"
        assert fiche.bioagresseurs == ()


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — Le local se distingue du partagé
# ═════════════════════════════════════════════════════════════════════════════

class TestCA3LocalDistingue:
    def test_us174_un_bioagresseur_local_est_marque_comme_tel(self, db):
        """[CA3] Le jardinier doit savoir lequel est le sien — sans quoi il
        croirait le référentiel partagé plus riche qu'il ne l'est."""
        _seed_culture(db, "chou")
        _rattacher(db, "chou", "piéride", "insecte", "courant")
        _rattacher(db, "chou", "altise de Vitry", "insecte", "rare",
                   potager_id=CTX.potager_id)

        par_nom = {
            b.nom_commun_fr: b
            for b in svc_fiche.generer_fiche_courte(
                db, "chou", potager_id=CTX.potager_id
            ).bioagresseurs
        }

        assert par_nom["piéride"].local is False
        assert par_nom["altise de Vitry"].local is True


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — La fiche courte reste courte
# ═════════════════════════════════════════════════════════════════════════════

class TestCA4Troncature:
    def _seed_beaucoup(self, db, combien):
        _seed_culture(db, "tomate")
        for i in range(combien):
            _rattacher(db, "tomate", f"agresseur {i:02}", "insecte", "courant")

    def test_us174_au_plus_cinq_affiches(self, db):
        """[Gherkin: La fiche reste courte] Quinze bioagresseurs, cinq affichés."""
        self._seed_beaucoup(db, 15)

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert len(fiche.bioagresseurs) == svc_fiche.LIMITE_BIOAGRESSEURS == 5
        assert fiche.bioagresseurs_non_affiches == 10

    def test_us174_rien_n_est_tronque_en_dessous_du_seuil(self, db):
        """[CA4] La troncature ne se déclenche pas pour rien."""
        self._seed_beaucoup(db, 3)

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert len(fiche.bioagresseurs) == 3
        assert fiche.bioagresseurs_non_affiches == 0

    def test_us174_la_troncature_garde_les_plus_frequents(self, db):
        """[CA4] Tronquer ne doit pas retirer l'information la plus utile : ce
        qui arrive souvent survit à la coupe."""
        _seed_culture(db, "tomate")
        for i in range(6):
            _rattacher(db, "tomate", f"rare {i}", "insecte", "rare")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert fiche.bioagresseurs[0].nom_commun_fr == "mildiou"
        assert len(fiche.bioagresseurs) == 5

    def test_us174_le_seuil_est_un_parametre_nomme(self):
        """[CA4] Décision produit révisable, pas une constante enfouie."""
        assert isinstance(svc_fiche.LIMITE_BIOAGRESSEURS, int)
        assert svc_fiche.LIMITE_BIOAGRESSEURS > 0


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — L'absence d'information n'est pas une absence de risque
# ═════════════════════════════════════════════════════════════════════════════

class TestCA5Honnetete:
    def test_us174_aucune_arete_connue_se_lit_comme_telle(self, db):
        """[Gherkin: Culture sans bioagresseur rattaché] `bioagresseurs_connus`
        distingue l'ignorance d'une liste tronquée — sans ce prédicat, un tuple
        vide finirait un jour lu comme « rien ne l'attaque »."""
        _seed_culture(db, "ail")

        fiche = svc_fiche.generer_fiche_courte(db, "ail")

        assert fiche.bioagresseurs_connus is False
        assert fiche.bioagresseurs_non_affiches == 0

    def test_us174_une_arete_suffit_a_rendre_la_rubrique_connue(self, db):
        _seed_culture(db, "ail")
        _rattacher(db, "ail", "rouille des alliacées", "champignon", "courant")

        assert svc_fiche.generer_fiche_courte(db, "ail").bioagresseurs_connus is True

    def test_us174_culture_inconnue_leve_toujours(self, db):
        """[US-164 / CA5] Non-régression : ne pas connaître la culture reste
        distinct de ne rien savoir d'une culture connue."""
        with pytest.raises(LookupError):
            svc_fiche.generer_fiche_courte(db, "salsifis")


# ═════════════════════════════════════════════════════════════════════════════
# CA6, CA7 — L'isolation, qui est le vrai sujet
# ═════════════════════════════════════════════════════════════════════════════

class TestCA6Isolation:
    def test_us174_un_bioagresseur_local_ne_fuit_pas_vers_un_autre_potager(self, db):
        """[Gherkin: Un bioagresseur local ne fuit pas d'un potager à l'autre]"""
        _seed_culture(db, "chou")
        _rattacher(db, "chou", "altise de Vitry", "insecte", "courant",
                   potager_id=CTX.potager_id)

        chez_lui = svc_fiche.generer_fiche_courte(db, "chou", potager_id=CTX.potager_id)
        chez_l_autre = svc_fiche.generer_fiche_courte(db, "chou", potager_id=AUTRE_POTAGER)

        assert [b.nom_commun_fr for b in chez_lui.bioagresseurs] == ["altise de Vitry"]
        assert chez_l_autre.bioagresseurs == ()
        assert chez_l_autre.bioagresseurs_connus is False

    def test_us174_sans_potager_seule_la_connaissance_partagee_est_rendue(self, db):
        """[CA6] Le défaut d'un appelant sans contexte : le partagé, rien que lui
        — jamais le local du premier potager venu."""
        _seed_culture(db, "chou")
        _rattacher(db, "chou", "piéride", "insecte", "courant")
        _rattacher(db, "chou", "altise de Vitry", "insecte", "courant",
                   potager_id=CTX.potager_id)

        fiche = svc_fiche.generer_fiche_courte(db, "chou")

        assert [b.nom_commun_fr for b in fiche.bioagresseurs] == ["piéride"]

    def test_us174_le_reste_de_la_fiche_reste_partage(self, db):
        """[CA7] Rendre la fiche consciente du potager ne doit rien rendre privé
        qui ne l'était pas : famille, délai, attributs et description sont
        identiques pour deux potagers différents."""
        solanacee = _seed_famille(db, "Solanacée", delai_retour_annees=4)
        _seed_culture(db, "tomate", famille=solanacee, description="Plante de soleil")
        _rattacher(db, "tomate", "altise de Vitry", "insecte", "courant",
                   potager_id=CTX.potager_id)

        a = svc_fiche.generer_fiche_courte(db, "tomate", potager_id=CTX.potager_id)
        b = svc_fiche.generer_fiche_courte(db, "tomate", potager_id=AUTRE_POTAGER)

        assert (a.culture, a.famille, a.delai_retour_annees, a.description_agronomique) == \
               (b.culture, b.famille, b.delai_retour_annees, b.description_agronomique)
        assert a.attributs == b.attributs
        # Seule la rubrique bioagresseurs diffère — c'est tout le périmètre du scope.
        assert a.bioagresseurs != b.bioagresseurs


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — Une seule mention de source
# ═════════════════════════════════════════════════════════════════════════════

class TestCA8Attributions:
    def test_us174_les_attributions_des_bioagresseurs_rejoignent_les_autres(self, db):
        """[Gherkin: Une seule mention de source] Dédupliquées, dans la même
        liste — jamais une seconde ligne « Source : » séparée."""
        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")

        attributions = svc_fiche.generer_fiche_courte(db, "tomate").attributions

        assert any("jardinier" in a.lower() for a in attributions)
        assert len(attributions) == len(set(attributions))

    def test_us174_une_source_partagee_n_est_citee_qu_une_fois(self, db):
        """[CA8] Trois bioagresseurs de la même origine ne produisent pas trois
        mentions identiques."""
        _seed_culture(db, "tomate")
        for nom in ("mildiou", "aleurode", "pourriture grise"):
            _rattacher(db, "tomate", nom, "champignon", "courant")

        attributions = svc_fiche.generer_fiche_courte(db, "tomate").attributions

        assert len(attributions) == len(set(attributions))

    def test_us174_une_source_seulement_tronquee_n_est_pas_citee(self, db):
        """[CA8] L'obligation d'attribution naît de l'AFFICHAGE : citer la source
        d'une ligne que le jardinier ne voit pas mentionnerait une donnée
        absente de sa réponse."""
        _seed_culture(db, "tomate")
        for i in range(svc_fiche.LIMITE_BIOAGRESSEURS):
            _rattacher(db, "tomate", f"visible {i}", "insecte", "courant")
        # Celui-ci tombe hors de la coupe (fréquence la plus basse) et porte une
        # origine que rien d'autre n'apporte.
        svc_bio.enregistrer_bioagresseur(db, "invisible", "insecte")
        svc_bio.rattacher(db, "tomate", "invisible", "rare",
                          source_code=svc_sources.SOURCE_REDACTION_INTERNE)

        fiche = svc_fiche.generer_fiche_courte(db, "tomate")

        assert fiche.bioagresseurs_non_affiches == 1
        assert not any("rédaction interne" in a.lower() for a in fiche.attributions)


# ═════════════════════════════════════════════════════════════════════════════
# CA9, CA10, CA11 — Ce que la fiche ne fait pas
# ═════════════════════════════════════════════════════════════════════════════

class TestCA9AucunePrescription:
    def test_us174_la_fiche_ne_porte_aucune_prescription(self, db):
        """[Gherkin: La fiche ne prescrit rien] Structurel : l'objet restitué
        n'expose que l'identité, la fréquence et la période."""
        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")

        lu = svc_fiche.generer_fiche_courte(db, "tomate").bioagresseurs[0]

        assert set(vars(lu)) == {
            "nom_commun_fr", "nom_scientifique", "categorie", "code_eppo",
            "frequence", "periode_risque", "local", "source_code", "attribution",
        }


class TestCA11ZeroJeton:
    def test_us174_aucun_appel_au_modele(self, db):
        """[CA11] La fiche reste gratuite — la rubrique ajoutée est une lecture
        de base, rien d'autre."""
        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")

        with patch("llm.passerelle.appeler_chat") as mock_chat, \
             patch("llm.passerelle.transcrire") as mock_whisper:
            svc_fiche.generer_fiche_courte(db, "tomate", potager_id=CTX.potager_id)

        mock_chat.assert_not_called()
        mock_whisper.assert_not_called()

    def test_us174_aucun_appel_reseau(self, db, monkeypatch):
        import socket

        def _interdit(*args, **kwargs):
            raise AssertionError("appel réseau interdit à la génération de fiche (CA11)")

        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")
        monkeypatch.setattr(socket, "socket", _interdit)
        monkeypatch.setattr(socket, "create_connection", _interdit)

        svc_fiche.generer_fiche_courte(db, "tomate", potager_id=CTX.potager_id)


# ═════════════════════════════════════════════════════════════════════════════
# Couche bot — /fiche
# ═════════════════════════════════════════════════════════════════════════════

class TestCommandeBot:
    def _update(self):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    def _ctx(self, *args):
        ctx = MagicMock()
        ctx.args = list(args)
        return ctx

    def _texte(self, update):
        return update.message.reply_text.await_args.args[0]

    @pytest.mark.asyncio
    async def test_us174_bot_passe_le_potager_courant(self, db):
        """[CA6] Sans ce passage, la fiche servirait le local d'un autre potager."""
        import bot

        _seed_culture(db, "tomate")
        update, ctx = self._update(), self._ctx("tomate")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX), \
             patch.object(bot.svc_fiche_culture, "generer_fiche_courte",
                          wraps=svc_fiche.generer_fiche_courte) as mock_gen:
            await bot.cmd_fiche(update, ctx)

        mock_gen.assert_called_once_with(ANY, "tomate", potager_id=CTX.potager_id)

    @pytest.mark.asyncio
    async def test_us174_bot_affiche_la_rubrique(self, db):
        """[CA1, CA2] Nom, fréquence, période quand elle existe."""
        import bot

        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant",
                   periode="juin-septembre")
        update, ctx = self._update(), self._ctx("tomate")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_fiche(update, ctx)

        texte = self._texte(update)
        assert "À surveiller" in texte
        assert "mildiou" in texte
        assert "courant" in texte
        assert "juin-septembre" in texte

    @pytest.mark.asyncio
    async def test_us174_bot_dit_l_ignorance_plutot_qu_une_rubrique_vide(self, db):
        """[CA5] Jamais « rien ne l'attaque »."""
        import bot

        _seed_culture(db, "ail")
        update, ctx = self._update(), self._ctx("ail")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_fiche(update, ctx)

        texte = self._texte(update)
        assert "À surveiller" in texte
        assert "n'est pas exposée" in texte

    @pytest.mark.asyncio
    async def test_us174_bot_annonce_le_reste_et_la_commande_pour_le_voir(self, db):
        """[CA4] Une troncature muette laisserait croire la liste complète."""
        import bot

        _seed_culture(db, "tomate")
        for i in range(8):
            _rattacher(db, "tomate", f"agresseur {i}", "insecte", "courant")
        update, ctx = self._update(), self._ctx("tomate")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_fiche(update, ctx)

        texte = self._texte(update)
        assert "3 autre(s)" in texte
        assert "/bioagresseur lister tomate" in texte

    @pytest.mark.asyncio
    async def test_us174_bot_marque_le_local(self, db):
        """[CA3] Le jardinier voit ce qui vient de chez lui."""
        import bot

        _seed_culture(db, "chou")
        _rattacher(db, "chou", "altise de Vitry", "insecte", "courant",
                   potager_id=CTX.potager_id)
        update, ctx = self._update(), self._ctx("chou")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_fiche(update, ctx)

        assert "votre potager" in self._texte(update)

    @pytest.mark.asyncio
    async def test_us174_bot_ne_prescrit_rien(self, db):
        """[CA9] Aucun mot de traitement ne peut apparaître : il n'y a rien à
        afficher qui en porte."""
        import bot

        _seed_culture(db, "tomate")
        _rattacher(db, "tomate", "mildiou", "champignon", "courant")
        update, ctx = self._update(), self._ctx("tomate")

        with patch.object(bot, "SessionLocal", return_value=db), \
             patch.object(bot, "current_context", return_value=CTX):
            await bot.cmd_fiche(update, ctx)

        texte = self._texte(update).lower()
        assert not any(mot in texte for mot in ("dose", "dosage", "pulvéris", "produit"))
