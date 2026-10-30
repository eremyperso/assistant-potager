"""
tests/test_us279_remplacer_calendrier_personnalise.py — [US-279]

Un calendrier personnalisé (copie faite à la première correction, US-068 /
CA11) ne reçoit plus les mises à jour du référentiel, que l'import n'écrit que
dans le partagé (CA9). `/calendrier maj` dit au jardinier que le référentiel a
évolué DEPUIS sa copie, et lui propose de la remplacer — jamais de fusion.
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.bot import commandes_calendrier as bot_cal
from app.services import calendrier_cultural as cal
from app.services import import_referentiel as svc_import
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError
from database.models import (
    CultureConfig,
    DureeCulturale,
    FenetreCulturale,
    ItineraireCultural,
    Potager,
    User,
)

RACINE = Path(__file__).resolve().parent.parent

CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")
LECTEUR_A = TenantContext(user_id=3, potager_id=1, role="lecteur")


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture
def db(test_db):
    """Deux potagers, zone par défaut (océanique) : le décor de l'isolement."""
    test_db.add_all([User(id=1, email="a@potager.test"), User(id=2, email="b@potager.test")])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    test_db.commit()
    return test_db


def _culture(db, nom, potager_id=None):
    config = CultureConfig(nom=nom, type_organe_recolte="reproducteur", potager_id=potager_id)
    db.add(config)
    db.commit()
    return config


def _importer(db, *entrees):
    manifeste = {
        "source": {
            "code": "wikidata", "libelle": "Wikidata", "licence": "CC0",
            "attribution": "Wikidata — CC0 1.0 Universal (domaine public)",
            "url": "https://www.wikidata.org/", "partageable": True,
        },
        "cultures_calendriers": list(entrees),
    }
    return svc_import.importer(db, manifeste)


def _courgette(plantation="mai", levee="7-10", continental="mai-juin"):
    return {
        "culture": "courgette", "itineraire": "standard",
        "durees": {"levee": levee},
        "fenetres": {
            "oceanique": {"plantation": plantation, "recolte": "juillet-août"},
            "continental": {"plantation": continental},
        },
    }


def _copie(db, potager_id, culture="courgette"):
    return (
        db.query(ItineraireCultural)
        .join(CultureConfig, CultureConfig.id == ItineraireCultural.culture_id)
        .filter(ItineraireCultural.potager_id == potager_id, CultureConfig.nom == culture)
        .first()
    )


@pytest.fixture
def courgette_corrigee(db):
    """La courgette est importée, puis le potager A corrige sa plantation."""
    _culture(db, "courgette")
    _importer(db, _courgette())
    cal.corriger_fenetre(db, CTX_A, "courgette", "plantation", "juin")
    return db


# ═════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — mémorisation à la copie et détection
# ═════════════════════════════════════════════════════════════════════════════
class TestCA1CA2Detection:

    def test_us279_ca2_la_copie_memorise_l_empreinte_du_partage_copie(self, courgette_corrigee):
        db = courgette_corrigee
        copie = _copie(db, 1)
        partage = cal._homologue_partage(db, copie)
        assert copie.empreinte_reference == cal._empreinte(*cal._lignes(db, partage.id))
        assert partage.empreinte_reference is None

    def test_us279_ca1_ma_correction_seule_n_est_pas_une_evolution(self, courgette_corrigee):
        """La copie diffère du partagé (juin ≠ mai), mais le référentiel n'a pas
        bougé : rien n'est proposé."""
        assert cal.ecarts_referentiel(courgette_corrigee, 1) == []

    def test_us279_ca1_une_evolution_du_referentiel_est_detectee(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        ecarts = cal.ecarts_referentiel(db, 1)
        assert [(e.culture, e.itineraire) for e in ecarts] == [("courgette", "standard")]
        lues = {d.libelle: (d.avant, d.apres) for d in ecarts[0].differences}
        assert lues["Plantation"] == ("juin", "mai")                 # la correction, perdue au remplacement
        assert lues["Semis → levée"] == ("7 à 10 jours", "6 à 9 jours")
        assert ecarts[0].autres_zones is False

    def test_us279_ca1_une_evolution_d_une_autre_zone_est_signalee_sans_detail(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(continental="juin"))
        (ecart,) = cal.ecarts_referentiel(db, 1)
        assert ecart.autres_zones is True
        assert [d.libelle for d in ecart.differences] == ["Plantation"]

    def test_us279_ca1_copie_sans_empreinte_listee_si_elle_differe(self, courgette_corrigee):
        db = courgette_corrigee
        copie = _copie(db, 1)
        copie.empreinte_reference = None            # copie d'avant US-279
        db.commit()
        assert len(cal.ecarts_referentiel(db, 1)) == 1

    def test_us279_ca1_copie_sans_empreinte_identique_au_partage_non_listee(self, courgette_corrigee):
        db = courgette_corrigee
        cal.corriger_fenetre(db, CTX_A, "courgette", "plantation", "mai")   # revient au partagé
        copie = _copie(db, 1)
        copie.empreinte_reference = None
        db.commit()
        assert cal.ecarts_referentiel(db, 1) == []

    def test_us279_ca1_copie_identique_au_nouveau_partage_non_listee(self, courgette_corrigee):
        """Le référentiel adopte la correction du jardinier : rien à remplacer."""
        db = courgette_corrigee
        _importer(db, _courgette(plantation="juin"))
        assert cal.ecarts_referentiel(db, 1) == []

    def test_us279_ca1_itineraire_cree_de_zero_jamais_liste(self, db):
        _culture(db, "panais")
        cal.corriger_duree(db, CTX_A, "panais", "levee", "15-25")
        copie = _copie(db, 1, "panais")
        assert copie is not None and copie.empreinte_reference is None
        assert cal.ecarts_referentiel(db, 1) == []
        assert cal.etat_mise_a_jour(db, 1, "panais").statut == cal.STATUT_A_JOUR

    def test_us279_ca1_itineraire_d_un_autre_nom_compare_a_son_homologue(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, {"culture": "courgette", "itineraire": "culture précoce",
                       "durees": {"levee": "5-8"}})
        cal.corriger_duree(db, CTX_A, "courgette", "levee", "6-8", itineraire="culture précoce")
        _importer(db, {"culture": "courgette", "itineraire": "culture précoce",
                       "durees": {"levee": "4-7"}})
        assert [e.itineraire for e in cal.ecarts_referentiel(db, 1)] == ["culture précoce"]

    def test_us279_ca4_etat_dit_pourquoi_il_n_y_a_rien(self, courgette_corrigee):
        db = courgette_corrigee
        _culture(db, "radis")
        assert cal.etat_mise_a_jour(db, 1, "artichaut").statut == cal.STATUT_CULTURE_INCONNUE
        assert cal.etat_mise_a_jour(db, 1, "radis").statut == cal.STATUT_SANS_COPIE
        assert cal.etat_mise_a_jour(db, 1, "courgette").statut == cal.STATUT_A_JOUR
        _importer(db, _courgette(levee="6-9"))
        etat = cal.etat_mise_a_jour(db, 1, "courgettes")      # pluriel dicté
        assert etat.statut == cal.STATUT_ECART and len(etat.ecarts) == 1

    def test_us279_ca1_aucun_potager_aucun_ecart(self, courgette_corrigee):
        assert cal.ecarts_referentiel(courgette_corrigee, None) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA5, CA6, CA9, CA11 — remplacement
# ═════════════════════════════════════════════════════════════════════════════
class TestCA5CA6Remplacement:

    def test_us279_ca5_remplacer_supprime_la_copie_et_retombe_sur_le_partage(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        copie_id = _copie(db, 1).id
        (remplace,) = cal.remplacer_par_referentiel(db, CTX_A, [copie_id])
        assert remplace.culture == "courgette"
        assert _copie(db, 1) is None
        assert db.query(FenetreCulturale).filter(FenetreCulturale.itineraire_id == copie_id).count() == 0
        assert db.query(DureeCulturale).filter(DureeCulturale.itineraire_id == copie_id).count() == 0
        (it,) = cal.lire_calendrier(db, "courgette", 1).itineraires
        assert it.personnalise is False
        assert it.fenetre("plantation").affichage == "mai"
        assert it.duree("levee").affichage == "6 à 9 jours"
        assert cal.ecarts_referentiel(db, 1) == []
        assert cal.etat_mise_a_jour(db, 1, "courgette").statut == cal.STATUT_SANS_COPIE

    def test_us279_ca5_l_autre_potager_garde_sa_copie(self, courgette_corrigee):
        db = courgette_corrigee
        cal.corriger_fenetre(db, CTX_B, "courgette", "plantation", "juillet")
        _importer(db, _courgette(levee="6-9"))
        cal.remplacer_par_referentiel(db, CTX_A, [_copie(db, 1).id])
        assert _copie(db, 2) is not None
        assert cal.lire_calendrier(db, "courgette", 2).itineraires[0].fenetre("plantation").affichage == "juillet"
        assert len(cal.ecarts_referentiel(db, 2)) == 1

    def test_us279_ca5_les_autres_itineraires_de_la_culture_ne_sont_pas_touches(self, courgette_corrigee):
        db = courgette_corrigee
        cal.corriger_duree(db, CTX_A, "courgette", "levee", "5-6", itineraire="sous tunnel")
        _importer(db, _courgette(levee="6-9"))
        (ecart,) = cal.ecarts_referentiel(db, 1)
        cal.remplacer_par_referentiel(db, CTX_A, [ecart.itineraire_id])
        restants = db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).all()
        assert [it.nom for it in restants] == ["sous tunnel"]

    def test_us279_ca6_tout_ou_rien(self, courgette_corrigee):
        """Une copie d'un autre potager dans la liste : rien n'est remplacé."""
        db = courgette_corrigee
        cal.corriger_fenetre(db, CTX_B, "courgette", "plantation", "juillet")
        _importer(db, _courgette(levee="6-9"))
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.remplacer_par_referentiel(db, CTX_A, [_copie(db, 1).id, _copie(db, 2).id])
        assert _copie(db, 1) is not None and _copie(db, 2) is not None

    def test_us279_ca6_tout_ou_rien_copie_deja_a_jour(self, courgette_corrigee):
        db = courgette_corrigee
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"}})
        cal.corriger_duree(db, CTX_A, "tomate", "levee", "8-12")       # à jour : rien n'a évolué
        _importer(db, _courgette(levee="6-9"))
        with pytest.raises(cal.ValeurCalendrierInvalideError, match="suit déjà"):
            cal.remplacer_par_referentiel(db, CTX_A, [_copie(db, 1).id, _copie(db, 1, "tomate").id])
        assert _copie(db, 1) is not None

    def test_us279_ca6_plusieurs_cultures_en_une_fois(self, courgette_corrigee):
        db = courgette_corrigee
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"}})
        cal.corriger_duree(db, CTX_A, "tomate", "levee", "8-12")
        _importer(db, _courgette(levee="6-9"), {"culture": "tomate", "durees": {"levee": "6-12"}})
        ecarts = cal.ecarts_referentiel(db, 1)
        assert [e.culture for e in ecarts] == ["courgette", "tomate"]
        cal.remplacer_par_referentiel(db, CTX_A, [e.itineraire_id for e in ecarts])
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).count() == 0

    def test_us279_ca9_une_nouvelle_correction_recopie_la_version_courante(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        cal.remplacer_par_referentiel(db, CTX_A, [_copie(db, 1).id])
        cal.corriger_fenetre(db, CTX_A, "courgette", "recolte", "août")
        copie = _copie(db, 1)
        partage = cal._homologue_partage(db, copie)
        assert copie.empreinte_reference == cal._empreinte(*cal._lignes(db, partage.id))
        assert cal.lire_calendrier(db, "courgette", 1).itineraires[0].duree("levee").affichage == "6 à 9 jours"
        assert cal.ecarts_referentiel(db, 1) == []

    def test_us279_ca11_le_remplacement_est_journalise(self, courgette_corrigee, caplog):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        with caplog.at_level(logging.INFO, logger="potager"):
            cal.remplacer_par_referentiel(db, CTX_A, [_copie(db, 1).id])
        lignes = [r.getMessage() for r in caplog.records if "[US-279]" in r.getMessage()]
        assert lignes and "courgette" in lignes[0] and "potager_id=1" in lignes[0]
        assert "3 fenêtre(s), 1 durée(s)" in lignes[0]

    def test_us279_ca5_liste_vide_n_ecrit_rien(self, courgette_corrigee):
        assert cal.remplacer_par_referentiel(courgette_corrigee, CTX_A, []) == []

    def test_us279_ca6_erreur_base_en_cours_annule_tout(self, courgette_corrigee):
        """[CA6] La base échoue au moment d'écrire : la transaction est annulée,
        les deux copies restent."""
        db = courgette_corrigee
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"}})
        cal.corriger_duree(db, CTX_A, "tomate", "levee", "8-12")
        _importer(db, _courgette(levee="6-9"), {"culture": "tomate", "durees": {"levee": "6-12"}})
        ids = [e.itineraire_id for e in cal.ecarts_referentiel(db, 1)]
        with patch.object(db, "commit", side_effect=RuntimeError("base indisponible")):
            with pytest.raises(RuntimeError):
                cal.remplacer_par_referentiel(db, CTX_A, ids)
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).count() == 2
        assert len(cal.ecarts_referentiel(db, 1)) == 2


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — garder ma version
# ═════════════════════════════════════════════════════════════════════════════
class TestCA7Garder:

    def test_us279_ca7_garder_ne_repropose_qu_a_la_prochaine_evolution(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        copie_id = _copie(db, 1).id
        cal.garder_version_locale(db, CTX_A, copie_id)
        assert cal.ecarts_referentiel(db, 1) == []
        it = cal.lire_calendrier(db, "courgette", 1).itineraires[0]
        assert it.personnalise is True
        assert it.fenetre("plantation").affichage == "juin"
        assert it.duree("levee").affichage == "7 à 10 jours"     # la copie n'a pas bougé
        _importer(db, _courgette(levee="5-9"))
        assert [e.itineraire_id for e in cal.ecarts_referentiel(db, 1)] == [copie_id]

    def test_us279_ca7_garder_sans_mise_a_jour_en_attente_est_refuse(self, courgette_corrigee):
        db = courgette_corrigee
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.garder_version_locale(db, CTX_A, _copie(db, 1).id)


# ═════════════════════════════════════════════════════════════════════════════
# CA10, CA12 — droits, isolation, import inchangé
# ═════════════════════════════════════════════════════════════════════════════
class TestCA10CA12:

    def test_us279_ca10_un_lecteur_ne_remplace_ni_ne_garde(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        copie_id = _copie(db, 1).id
        with pytest.raises(PermissionInsuffisanteError):
            cal.remplacer_par_referentiel(db, LECTEUR_A, [copie_id])
        with pytest.raises(PermissionInsuffisanteError):
            cal.garder_version_locale(db, LECTEUR_A, copie_id)
        assert _copie(db, 1) is not None

    def test_us279_ca10_un_potager_ne_voit_ni_ne_touche_la_copie_d_un_autre(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        copie_id = _copie(db, 1).id
        assert cal.ecarts_referentiel(db, 2) == []
        assert cal.etat_mise_a_jour(db, 2, "courgette").statut == cal.STATUT_SANS_COPIE
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.remplacer_par_referentiel(db, CTX_B, [copie_id])
        with pytest.raises(cal.ValeurCalendrierInvalideError):
            cal.garder_version_locale(db, CTX_B, copie_id)
        assert _copie(db, 1) is not None and _copie(db, 1).empreinte_reference is not None

    def test_us279_ca12_le_rejeu_de_l_import_laisse_la_copie_intacte(self, courgette_corrigee):
        db = courgette_corrigee
        copie = _copie(db, 1)
        empreinte = copie.empreinte_reference
        _importer(db, _courgette(levee="6-9", plantation="avril"))
        db.refresh(copie)
        assert copie.empreinte_reference == empreinte
        it = cal.lire_calendrier(db, "courgette", 1).itineraires[0]
        assert it.fenetre("plantation").affichage == "juin"
        assert it.duree("levee").affichage == "7 à 10 jours"

    def test_us279_ca2_migration_et_rollback(self):
        migration = (RACINE / "migrations" / "migration_v63.sql").read_text(encoding="utf-8")
        rollback = (RACINE / "migrations" / "rollback_v63.sql").read_text(encoding="utf-8")
        assert "ADD COLUMN IF NOT EXISTS empreinte_reference VARCHAR(64)" in migration
        assert "UPDATE" not in migration.upper()          # aucun backfill
        assert "DROP COLUMN IF EXISTS empreinte_reference" in rollback


# ═════════════════════════════════════════════════════════════════════════════
# CA3, CA4, CA8 — bot
# ═════════════════════════════════════════════════════════════════════════════
def _boutons(appel) -> list[tuple[str, str]]:
    clavier = appel.kwargs.get("reply_markup")
    return [(b.text, b.callback_data) for ligne in clavier.inline_keyboard for b in ligne] if clavier else []


class TestBot:

    async def _commande(self, db, *args, tenant=CTX_A):
        update = MagicMock()
        update.message.reply_text = AsyncMock()
        ctx = MagicMock()
        ctx.args = list(args)
        with patch.object(bot_cal, "SessionLocal", return_value=db), \
             patch.object(bot_cal, "current_context", return_value=tenant):
            await bot_cal.cmd_calendrier(update, ctx)
        return update.message.reply_text

    async def _clic(self, db, donnees, tenant=CTX_A):
        update = MagicMock()
        query = update.callback_query
        query.data = donnees
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.message.reply_text = AsyncMock()
        with patch.object(bot_cal, "SessionLocal", return_value=db), \
             patch.object(bot_cal, "current_context", return_value=tenant):
            await bot_cal._calendrier_maj_cb(update, MagicMock())
        return query

    @pytest.mark.asyncio
    async def test_us279_ca3_rien_a_mettre_a_jour(self, courgette_corrigee):
        envoi = await self._commande(courgette_corrigee, "maj")
        assert "suit déjà le référentiel" in envoi.call_args[0][0]

    @pytest.mark.asyncio
    async def test_us279_ca3_liste_avec_bouton_par_culture_et_tout(self, courgette_corrigee):
        db = courgette_corrigee
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"}})
        cal.corriger_duree(db, CTX_A, "tomate", "levee", "8-12")
        _importer(db, _courgette(levee="6-9"), {"culture": "tomate", "durees": {"levee": "6-12"}})
        envoi = await self._commande(db, "maj")
        texte = envoi.call_args[0][0]
        assert "courgette" in texte and "tomate" in texte
        assert "2 valeurs différentes" in texte          # courgette : plantation + levée
        boutons = _boutons(envoi.call_args)
        assert ("Tout mettre à jour (2)", "calmaj:t") in boutons
        assert ("courgette", f"calmaj:v:{_copie(db, 1).id}") in boutons
        assert _copie(db, 1) is not None                  # lecture seule

    @pytest.mark.asyncio
    async def test_us279_ca3_une_seule_culture_pas_de_bouton_tout(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        envoi = await self._commande(db, "maj")
        assert not any(cb == "calmaj:t" for _, cb in _boutons(envoi.call_args))

    @pytest.mark.asyncio
    async def test_us279_ca4_detail_avant_apres_et_boutons(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        envoi = await self._commande(db, "maj", "courgette")
        texte = envoi.call_args[0][0]
        assert "Plantation : juin → *mai*" in texte
        assert "corrections" in texte and "perdues" in texte
        copie_id = _copie(db, 1).id
        assert _boutons(envoi.call_args) == [
            ("✅ Remplacer par le référentiel", f"calmaj:r:{copie_id}"),
            ("🔒 Garder ma version", f"calmaj:g:{copie_id}"),
        ]

    @pytest.mark.asyncio
    async def test_us279_ca4_culture_sans_ecart_dit_pourquoi(self, courgette_corrigee):
        db = courgette_corrigee
        _culture(db, "radis")
        assert "pas personnalisé" in (await self._commande(db, "maj", "radis")).call_args[0][0]
        assert "n'a pas évolué" in (await self._commande(db, "maj", "courgette")).call_args[0][0]
        assert "Culture inconnue" in (await self._commande(db, "maj", "artichaut")).call_args[0][0]

    @pytest.mark.asyncio
    async def test_us279_ca5_clic_remplacer(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        query = await self._clic(db, f"calmaj:r:{_copie(db, 1).id}")
        assert "remplacé par le référentiel" in query.edit_message_text.call_args[0][0]
        assert _copie(db, 1) is None

    @pytest.mark.asyncio
    async def test_us279_ca6_tout_demande_confirmation_puis_remplace(self, courgette_corrigee):
        db = courgette_corrigee
        _culture(db, "tomate")
        _importer(db, {"culture": "tomate", "durees": {"levee": "7-14"}})
        cal.corriger_duree(db, CTX_A, "tomate", "levee", "8-12")
        _importer(db, _courgette(levee="6-9"), {"culture": "tomate", "durees": {"levee": "6-12"}})

        query = await self._clic(db, "calmaj:t")
        confirmation = query.message.reply_text.call_args
        assert "courgette, tomate" in confirmation[0][0]
        assert ("✅ Tout remplacer (2)", "calmaj:T") in _boutons(confirmation)
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).count() == 2

        query = await self._clic(db, "calmaj:T")
        assert "courgette, tomate" in query.edit_message_text.call_args[0][0]
        assert db.query(ItineraireCultural).filter(ItineraireCultural.potager_id == 1).count() == 0

    @pytest.mark.asyncio
    async def test_us279_ca7_clic_garder(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        query = await self._clic(db, f"calmaj:g:{_copie(db, 1).id}")
        assert "Vous gardez votre calendrier" in query.edit_message_text.call_args[0][0]
        assert cal.ecarts_referentiel(db, 1) == []

    @pytest.mark.asyncio
    async def test_us279_clic_detail_et_annuler(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        query = await self._clic(db, f"calmaj:v:{_copie(db, 1).id}")
        assert "votre calendrier et le référentiel" in query.message.reply_text.call_args[0][0]
        query = await self._clic(db, "calmaj:x")
        assert "je ne change rien" in query.edit_message_text.call_args[0][0]
        assert _copie(db, 1) is not None

    @pytest.mark.asyncio
    async def test_us279_ca10_clic_sur_la_copie_d_un_autre_potager(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        query = await self._clic(db, f"calmaj:r:{_copie(db, 1).id}", tenant=CTX_B)
        assert "Rien n'a été modifié" in query.message.reply_text.call_args[0][0]
        assert _copie(db, 1) is not None

    @pytest.mark.asyncio
    async def test_us279_ca10_clic_d_un_lecteur(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        query = await self._clic(db, f"calmaj:r:{_copie(db, 1).id}", tenant=LECTEUR_A)
        assert query.message.reply_text.call_args[0][0].startswith("⛔")
        assert _copie(db, 1) is not None

    @pytest.mark.asyncio
    async def test_us279_ca6_echec_du_remplacement_dit_au_jardinier(self, courgette_corrigee):
        db = courgette_corrigee
        _importer(db, _courgette(levee="6-9"))
        with patch.object(bot_cal.svc_calendrier, "remplacer_par_referentiel",
                          side_effect=RuntimeError("base indisponible")):
            query = await self._clic(db, f"calmaj:r:{_copie(db, 1).id}")
        assert "rien n'a été modifié" in query.message.reply_text.call_args[0][0]
        assert _copie(db, 1) is not None

    @pytest.mark.asyncio
    async def test_us279_clic_detail_d_une_copie_deja_a_jour(self, courgette_corrigee):
        db = courgette_corrigee
        query = await self._clic(db, f"calmaj:v:{_copie(db, 1).id}")
        assert "suit déjà le référentiel" in query.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_us279_clic_tout_quand_plus_rien_n_attend(self, courgette_corrigee):
        query = await self._clic(courgette_corrigee, "calmaj:t")
        assert "suit déjà le référentiel" in query.edit_message_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_us279_ca7_clic_garder_sans_mise_a_jour(self, courgette_corrigee):
        db = courgette_corrigee
        query = await self._clic(db, f"calmaj:g:{_copie(db, 1).id}")
        assert "Rien n'a été modifié" in query.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_us279_ca8_indice_passif_sur_la_consultation(self, courgette_corrigee):
        db = courgette_corrigee
        assert "Le référentiel a évolué" not in (await self._commande(db, "courgette")).call_args[0][0]
        _importer(db, _courgette(levee="6-9"))
        texte = (await self._commande(db, "courgette")).call_args[0][0]
        assert "Le référentiel a évolué depuis votre copie" in texte
        assert "/calendrier maj courgette" in texte

    @pytest.mark.asyncio
    async def test_us279_usage_mentionne_maj(self, db):
        assert "/calendrier maj" in (await self._commande(db)).call_args[0][0]

    def test_us279_callback_enregistre(self):
        source = (RACINE / "app" / "bot" / "application.py").read_text(encoding="utf-8")
        assert 'CallbackQueryHandler(_calendrier_maj_cb, pattern=r"^calmaj:")' in source
