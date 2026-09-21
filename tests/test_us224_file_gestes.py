"""
tests/test_us224_file_gestes.py — La file de gestes en attente [US-224]
========================================================================

US-196 avait le bon principe et le mauvais véhicule : un laissez-passer à usage
unique, quinze minutes, consommé à l'OUVERTURE du lien. Ce fichier surveille
exactement ce que ce véhicule ne tenait pas, et que la file doit tenir :

* **rien n'est écrit avant « Confirmer »** — déposer ne crée aucun événement,
  quel que soit le chemin (CA1) ;
* **un geste ne sort de la file qu'à la confirmation ou à l'abandon explicite**
  (CA8) — ni « Plus tard », ni un délai de confirmation dépassé, ni une
  conversation refermée ne le retirent. C'étaient les trois façons de perdre un
  geste préparé sous US-196 ;
* **la péremption se compte PAR GESTE** (CA3) — confirmer, consulter ou
  reposer un geste ne prolonge jamais les autres, et une file entretenue en
  permanence ne devient pas immortelle ;
* **le refus est motivé** (CA12) — parcelle disparue, potager quitté, rôle
  devenu lecteur : trois phrases distinctes, et le geste quitte la file plutôt
  que d'échouer à chaque reprise ;
* **la relance est bornée** (CA14 à CA20) — une invitation, deux créneaux par
  jour, un arrêt à trois jours, une soupape qui ne vide pas la file ;
* **zéro jeton** — l'item arrive pré-parsé, `pre_parsed_items` court-circuite
  l'appel au modèle.

Le volet purement visuel (bouton masqué pour un lecteur, mention de date,
dépôt sans compagnon activé, doublon signalé) est couvert par
`frontend/src/lib/gestes.test.js`.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import file_gestes as svc
from app.services import relances_file as svc_relances
from app.services import telegram_notify as svc_notify
from app.services.context import TenantContext
from app.services.permissions import PermissionInsuffisanteError, PotagerArchiveError
from database.models import (
    CultureConfig, Evenement, FileGestesReglage, GesteIntention, Parcelle, Potager,
    PotagerMembre, User,
)
from llm.parseur_deterministe import ORIGINE_DETERMINISTE, parser_saisie


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def db(test_db, monkeypatch):
    test_db.add_all([
        User(id=1, email="camille@potager.test"),
        User(id=2, email="dominique@potager.test"),
    ])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    test_db.flush()
    test_db.add_all([
        PotagerMembre(user_id=1, potager_id=1, role="owner"),
        PotagerMembre(user_id=2, potager_id=2, role="owner"),
        Parcelle(id=1, nom="carré nord", nom_normalise="carrenord", potager_id=1),
        Parcelle(id=2, nom="planche B", nom_normalise="plancheb", potager_id=2),
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="epinard", type_organe_recolte="vegetatif", potager_id=None),
    ])
    test_db.commit()
    # `lecture_hors_tenant` et `_ecriture` ouvrent leur PROPRE session : elles
    # tournent côté bot, hors de toute session d'appelant. En test, cette
    # session doit être celle de la base SQLite en mémoire, sinon elles
    # repartent sur une base vide.
    monkeypatch.setattr(svc, "SessionLocal", lambda: test_db)
    monkeypatch.setattr(test_db, "close", lambda: None)
    return test_db


@pytest.fixture
def ctx():
    return TenantContext(user_id=1, potager_id=1, role="owner")


@pytest.fixture
def envois(monkeypatch):
    """Capture les envois sortants — le compagnon ne parle jamais en test.

    Rend la liste des `(chat_id, texte, boutons)` envoyés et celle des éditions,
    parce que le CA20 se joue précisément sur la différence entre les deux :
    une relance REMPLACE la précédente, elle ne l'empile pas.
    """
    envoyes: list[tuple] = []
    edites: list[tuple] = []

    def _envoyer(chat_id, texte, boutons=None, parse_mode=None):
        envoyes.append((chat_id, texte, boutons))
        return 1000 + len(envoyes)

    def _editer(chat_id, message_id, texte, boutons=None, parse_mode=None):
        edites.append((chat_id, message_id, texte))
        return True

    monkeypatch.setattr(svc_notify, "envoyer", _envoyer)
    monkeypatch.setattr(svc_notify, "editer_message", _editer)
    return SimpleNamespace(envoyes=envoyes, edites=edites)


def _nb_evenements(db) -> int:
    return db.query(Evenement).count()


def _lier(db, user_id: int, chat_id: int):
    db.query(User).filter(User.id == user_id).first().telegram_chat_id = chat_id
    db.commit()


def _deposer(db, ctx, **kwargs):
    kwargs.setdefault("action", "semis")
    kwargs.setdefault("culture", "tomate")
    return svc.deposer_geste(db, ctx, **kwargs)


# ══════════════════════════════════════════════════════════════════════════════
# CA1, CA2 — déposer sans écrire
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_depot_ne_cree_aucun_evenement(db, ctx):
    """[CA1] La file n'apparaît ni au Journal, ni dans un stock, ni ailleurs."""
    depot = _deposer(db, ctx, parcelle_id=1, contexte_semis="pepiniere",
                     date="2026-09-19", ecran="plan")

    assert _nb_evenements(db) == 0
    geste = depot.geste
    assert geste.potager_id == 1
    assert geste.etat == svc.ETAT_EN_ATTENTE
    assert geste.traite_le is None
    assert geste.geste["action"] == "semis"
    # La parcelle est stockée par son NOM : c'est ce que le flux du bot sait lire.
    assert geste.geste["parcelle"] == "carré nord"
    # Zéro jeton : l'item se présente comme déjà parsé.
    assert geste.geste["origine_parsing"] == ORIGINE_DETERMINISTE


def test_us224_code_opaque_et_compatible_deep_link(db, ctx):
    """[US-196 / CA3] ≥128 bits d'aléa, préfixe réservé, alphabet de `?start=`."""
    codes = {_deposer(db, ctx, action="plantation").geste.code for _ in range(5)}

    assert len(codes) == 5, "deux dépôts ne doivent jamais rendre le même code"
    for code in codes:
        assert code.startswith(svc.PREFIXE_CODE)
        assert len(code) <= svc.LONGUEUR_MAX_CODE
        assert all(c.isalnum() or c in "_-" for c in code)
        assert len(code) - len(svc.PREFIXE_CODE) >= 22
        # Aucun risque de confusion avec un code de liaison (US-045) : six
        # caractères d'un alphabet majuscule.
        assert len(code) != 6
    assert svc.est_code_geste(list(codes)[0]) is True
    assert svc.est_code_geste("ABCDEF") is False, "un code de liaison n'est pas détourné"


def test_us224_duree_de_vie_de_trois_jours(db, ctx):
    """[CA3] Trois jours, et non quinze minutes : on confirme quand on peut."""
    assert svc.DUREE_VIE_JOURS == 3
    geste = _deposer(db, ctx, action="plantation").geste
    restant = geste.expire_le - datetime.utcnow()
    assert timedelta(days=2, hours=23) < restant <= timedelta(days=3)


@pytest.mark.parametrize("action", ["teleporter", "observation"])
def test_us224_action_non_ouverte_refusee(db, ctx, action):
    """[CA2] Hors référentiel, ou dedans mais non ouverte à la PWA : même refus.

    `observation` existe dans `ACTION_MAP` mais porte du texte libre : la liste
    des gestes ouverts est ce qui fait foi, pas l'existence de l'action.
    """
    with pytest.raises(svc.ActionNonOuverteError):
        _deposer(db, ctx, action=action)
    assert db.query(GesteIntention).count() == 0


def test_us224_parcelle_d_un_autre_potager_refusee(db, ctx):
    """[CA2] La parcelle doit appartenir au potager consulté (US-042)."""
    with pytest.raises(svc.ParcelleHorsPotagerError):
        _deposer(db, ctx, parcelle_id=2)
    assert db.query(GesteIntention).count() == 0


def test_us224_lot_d_un_autre_potager_refuse(db, ctx):
    """[CA2] Même contrôle d'appartenance pour un lot de pépinière."""
    db.add(Evenement(id=99, type_action="semis", culture="tomate",
                     date=datetime(2026, 5, 1), potager_id=2))
    db.commit()
    with pytest.raises(svc.LotHorsPotagerError):
        _deposer(db, ctx, lot_id=99)


def test_us224_lecteur_ne_depose_rien(db):
    """[CA24] Un membre en lecture seule est refusé par le SERVEUR (US-047)."""
    lecteur = TenantContext(user_id=1, potager_id=1, role="lecteur")
    with pytest.raises(PermissionInsuffisanteError):
        _deposer(db, lecteur)
    assert db.query(GesteIntention).count() == 0


def test_us224_potager_archive_refuse(db, ctx):
    """[US-083] Déposer un geste que la confirmation rejettera à coup sûr ferait
    attendre pour rien."""
    db.query(Potager).filter(Potager.id == 1).first().etat = "archive"
    db.commit()
    with pytest.raises(PotagerArchiveError):
        _deposer(db, ctx)


def test_us224_item_du_geste_retire_les_champs_internes(db, ctx):
    """Le flux d'enregistrement ne doit jamais recevoir un champ hors contrat."""
    db.add(Evenement(id=7, type_action="semis", culture="tomate",
                     date=datetime(2026, 5, 1), potager_id=1))
    db.commit()
    geste = _deposer(db, ctx, lot_id=7).geste

    assert geste.geste["_lot_id"] == 7
    assert "_lot_id" not in svc.item_du_geste(geste)


# ══════════════════════════════════════════════════════════════════════════════
# CA4 — le doublon est signalé, jamais interdit
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_doublon_signale_mais_depose_quand_meme(db, ctx):
    """[CA4] Semer deux fois la même chose le même jour est un cas réel."""
    premier = _deposer(db, ctx, parcelle_id=1, date="2026-09-21")
    second = _deposer(db, ctx, parcelle_id=1, date="2026-09-21")

    assert premier.doublon is False
    assert second.doublon is True, "l'écran doit pouvoir le DIRE"
    assert db.query(GesteIntention).count() == 2, "et le geste entre quand même"


def test_us224_geste_different_n_est_pas_un_doublon(db, ctx):
    """[CA4] Quatre champs définissent l'identité : action, culture, parcelle, jour."""
    _deposer(db, ctx, culture="tomate", parcelle_id=1, date="2026-09-21")

    assert _deposer(db, ctx, culture="epinard", parcelle_id=1, date="2026-09-21").doublon is False
    assert _deposer(db, ctx, culture="tomate", parcelle_id=1, date="2026-09-20").doublon is False
    assert _deposer(db, ctx, culture="tomate", date="2026-09-21").doublon is False


# ══════════════════════════════════════════════════════════════════════════════
# CA8 — ce qui retire un geste de la file, et ce qui ne le retire pas
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_confirmation_retire_de_la_file(db, ctx):
    """[CA7] *Confirmer* — enregistre et retire de la file."""
    geste = _deposer(db, ctx).geste

    assert svc.confirmer(geste) is True

    db.refresh(geste)
    assert geste.etat == svc.ETAT_CONFIRME
    assert geste.traite_le is not None
    assert svc.compter_en_attente(db, 1) == 0


def test_us224_confirmation_est_idempotente(db, ctx):
    """Deux clics sur « Confirmer » ne produisent pas deux sorties de file."""
    geste = _deposer(db, ctx).geste
    assert svc.confirmer(geste) is True
    assert svc.confirmer(geste) is False


def test_us224_abandon_explicite_retire_de_la_file(db, ctx):
    """[CA7] *Abandonner ce geste* — le retire définitivement, et le dit."""
    geste = _deposer(db, ctx).geste

    assert svc.abandonner(geste) is True

    db.refresh(geste)
    assert geste.etat == svc.ETAT_ABANDONNE
    assert svc.compter_en_attente(db, 1) == 0


def test_us224_lire_par_code_ne_consomme_pas(db, ctx):
    """[CA11] Le lien n'est plus à usage unique : rouvrir redonne le même geste.

    C'est exactement ce qui manquait à US-196, où « Annuler » brûlait le geste
    et où rouvrir répondait « déjà utilisé ».
    """
    code = _deposer(db, ctx).geste.code

    premier = svc.geste_par_code(db, code, user_id=1)
    second = svc.geste_par_code(db, code, user_id=1)

    assert premier.id == second.id
    assert second.etat == svc.ETAT_EN_ATTENTE
    assert svc.compter_en_attente(db, 1) == 1


def test_us224_lien_d_un_autre_compte_ne_retire_rien(db, ctx):
    """[CA12] Un lien qui a fuité ne retire pas son geste à son propriétaire.

    US-196 le consommait ; c'était perdre le geste de quelqu'un parce qu'un
    tiers avait ouvert son lien.
    """
    geste = _deposer(db, ctx).geste

    with pytest.raises(svc.GesteAutreCompteError):
        svc.geste_par_code(db, geste.code, user_id=2)

    db.refresh(geste)
    assert geste.etat == svc.ETAT_EN_ATTENTE
    assert svc.compter_en_attente(db, 1) == 1


def test_us224_code_inconnu_et_geste_deja_traite(db, ctx):
    """[CA11, CA12] Deux refus distincts, jamais un « code invalide » attrape-tout."""
    with pytest.raises(svc.CodeIntrouvableError):
        svc.geste_par_code(db, "gCodeQuiNExistePas", user_id=1)

    geste = _deposer(db, ctx).geste
    svc.confirmer(geste)
    with pytest.raises(svc.GesteDejaTraiteError):
        svc.geste_par_code(db, geste.code, user_id=1)


# ══════════════════════════════════════════════════════════════════════════════
# CA3 — la péremption se compte par geste, jamais par pile
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_peremption_par_geste_et_non_par_pile(db, ctx):
    """[CA3] Un geste déposé mercredi n'est pas emporté par la purge de lundi."""
    lundi = datetime(2026, 9, 14, 10, 0)
    mercredi = datetime(2026, 9, 16, 10, 0)
    vieux = _deposer(db, ctx, culture="tomate", maintenant=lundi).geste
    recent = _deposer(db, ctx, culture="epinard", maintenant=mercredi).geste

    # Jeudi : les trois jours du geste de lundi sont écoulés, pas ceux de mercredi.
    jeudi = lundi + timedelta(days=3, hours=1)
    perimes = svc.gestes_perimes(db, jeudi)

    assert [g.id for g in perimes] == [vieux.id]
    assert [g.id for g in svc.lister_en_attente(db, 1, maintenant=jeudi)] == [recent.id]


def test_us224_confirmer_un_geste_ne_prolonge_pas_les_autres(db, ctx):
    """[CA3, CA19] Une file entretenue en permanence ne devient pas immortelle."""
    depot = datetime(2026, 9, 14, 10, 0)
    a = _deposer(db, ctx, culture="tomate", maintenant=depot).geste
    b = _deposer(db, ctx, culture="epinard", maintenant=depot).geste
    echeance_b = b.expire_le

    svc.confirmer(a, maintenant=depot + timedelta(days=2))
    svc_relances.noter_activite(db, 1, maintenant=depot + timedelta(days=2))

    db.refresh(b)
    assert b.expire_le == echeance_b, "l'activité ne repousse JAMAIS la péremption"


def test_us224_un_geste_perime_n_est_plus_en_attente(db, ctx):
    """[CA3] Même non purgé, un geste périmé ne fait plus partie de la file."""
    depot = datetime(2026, 9, 14, 10, 0)
    _deposer(db, ctx, maintenant=depot)

    apres = depot + timedelta(days=3, minutes=1)
    assert svc.compter_en_attente(db, 1, maintenant=apres) == 0
    with pytest.raises(svc.GestePerimeError):
        svc.geste_par_code(db, db.query(GesteIntention).first().code, 1, maintenant=apres)


def test_us224_geste_sorti_reste_visible_puis_part(db, ctx):
    """[CA18] Un geste vidé reste visible le temps d'être vu — puis la ligne part.

    L'envoi sortant est best-effort : si la notification de purge se perd, il
    ne reste que l'application pour dire ce qui a disparu.
    """
    geste = _deposer(db, ctx).geste
    instant = datetime.utcnow()
    svc.perimer(geste, maintenant=instant)

    assert [g.id for g in svc.lister_sortis_recents(db, 1, maintenant=instant)] == [geste.id]

    tard = instant + timedelta(hours=svc.RETENTION_SORTIS_HEURES + 1)
    svc.supprimer_gestes_sortis(db, maintenant=tard)
    assert db.query(GesteIntention).count() == 0


def test_us224_acquittement_efface_ce_qui_a_ete_vu(db, ctx):
    """[CA18] C'est l'écran qui sait que l'information a été lue."""
    svc.perimer(_deposer(db, ctx).geste)
    assert svc.acquitter_sortis(db, 1) == 1
    assert svc.lister_sortis_recents(db, 1) == []


# ══════════════════════════════════════════════════════════════════════════════
# CA12 — un contexte disparu se refuse en clair
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_parcelle_disparue_refusee_avec_son_motif(db, ctx):
    """[CA12] Jamais un geste fantôme qui échoue à chaque reprise."""
    geste = _deposer(db, ctx, parcelle_id=1).geste
    db.query(Parcelle).filter(Parcelle.id == 1).delete()
    db.commit()

    motif = svc.verifier_contexte(db, geste, user_id=1)

    assert motif is not None and "carré nord" in motif
    svc.refuser(geste, motif)
    db.refresh(geste)
    assert geste.etat == svc.ETAT_ABANDONNE
    assert geste.motif_refus == motif


def test_us224_potager_quitte_refuse(db, ctx):
    """[CA12] Quitter le potager entre le dépôt et la confirmation."""
    geste = _deposer(db, ctx).geste
    db.query(PotagerMembre).filter(
        PotagerMembre.user_id == 1, PotagerMembre.potager_id == 1,
    ).delete()
    db.commit()

    motif = svc.verifier_contexte(db, geste, user_id=1)
    assert motif is not None and "plus membre" in motif


def test_us224_role_devenu_lecteur_refuse(db, ctx):
    """[CA12] Un rôle rétrogradé n'écrit pas — et on le DIT."""
    geste = _deposer(db, ctx).geste
    db.query(PotagerMembre).filter(
        PotagerMembre.user_id == 1, PotagerMembre.potager_id == 1,
    ).first().role = "lecteur"
    db.commit()

    motif = svc.verifier_contexte(db, geste, user_id=1)
    assert motif is not None and "lecteur" in motif


def test_us224_potager_archive_entre_temps_refuse(db, ctx):
    """[CA12] Un potager archivé après le dépôt est lecture seule."""
    geste = _deposer(db, ctx).geste
    db.query(Potager).filter(Potager.id == 1).first().etat = "archive"
    db.commit()

    motif = svc.verifier_contexte(db, geste, user_id=1)
    assert motif is not None and "archivé" in motif


def test_us224_contexte_intact_ne_refuse_rien(db, ctx):
    """Le contrôle ne doit pas refuser un geste parfaitement jouable."""
    geste = _deposer(db, ctx, parcelle_id=1).geste
    assert svc.verifier_contexte(db, geste, user_id=1) is None


# ══════════════════════════════════════════════════════════════════════════════
# CA25, CA26 — la date du geste
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_date_a_venir_ramenee_au_jour_du_depot(db, ctx):
    """[CA26] La date de référence d'un écran peut être à venir ; le geste, non."""
    geste = _deposer(db, ctx, date="2026-10-15", aujourd_hui=date(2026, 9, 21)).geste
    assert geste.geste["date"] == "2026-09-21"


def test_us224_date_du_depot_survit_a_trois_jours_d_attente(db, ctx):
    """[CA25] Confirmé trois jours plus tard, le geste porte la date du DÉPÔT.

    C'est le jour où le jardinier a agi au potager, pas celui où il a eu les
    mains libres pour le dire.
    """
    geste = _deposer(db, ctx, date="2026-09-19", aujourd_hui=date(2026, 9, 19)).geste

    svc.confirmer(geste, maintenant=datetime(2026, 9, 22, 8, 0))

    db.refresh(geste)
    assert geste.geste["date"] == "2026-09-19"
    assert svc.item_du_geste(geste)["date"] == "2026-09-19"


def test_us224_date_absente_ou_illisible_vaut_le_jour(db, ctx):
    """[CA26] Sans date lisible, le jour — jamais une date inventée."""
    assert svc.date_enregistrable(None, date(2026, 9, 21)) == "2026-09-21"
    assert svc.date_enregistrable("pas une date", date(2026, 9, 21)) == "2026-09-21"


# ══════════════════════════════════════════════════════════════════════════════
# CA5, CA13 — ce que le niveau 1 présente
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_niveau_1_detaille_trois_gestes_puis_compte_le_reste(db, ctx):
    """[CA5] Le détail des trois premiers, puis « et N autres »."""
    for culture in ("tomate", "epinard", "tomate", "epinard", "tomate"):
        _deposer(db, ctx, culture=culture)
    gestes = svc.lister_en_attente(db, 1)

    texte = svc_relances.texte_file(db, gestes, "en-tête")

    assert texte.count("• ") == svc_relances.NB_GESTES_DETAILLES == 3
    assert "… et 2 autres" in texte


def test_us224_niveau_1_groupe_par_potager(db, ctx):
    """[CA13] Un geste s'enregistre dans le potager de son dépôt — et ça se voit."""
    db.add(PotagerMembre(user_id=1, potager_id=2, role="editor"))
    db.commit()
    _deposer(db, ctx, culture="tomate")
    _deposer(db, TenantContext(user_id=1, potager_id=2, role="editor"), culture="epinard")

    texte = svc_relances.texte_file(db, svc.lister_en_attente(db, 1), "en-tête")

    assert "Jardin A" in texte and "Jardin B" in texte


def test_us224_niveau_1_ne_porte_que_deux_actions_et_aucune_n_ecrit(db):
    """[CA5] Commencer, ou couper les relances. Des BOUTONS, pas des commandes."""
    rangees = svc_relances.boutons_file()
    donnees = [donnee for rangee in rangees for _, donnee in rangee]

    assert donnees == [svc_relances.CB_COMMENCER, svc_relances.CB_COUPER]
    assert all(d.startswith("file:") for d in donnees)
    # Aucune n'est une action d'écriture du flux de confirmation (`action_*`).
    assert not any(d.startswith("action_") for d in donnees)


# ══════════════════════════════════════════════════════════════════════════════
# CA14, CA15, CA16, CA19, CA20 — la relance, et sa fin
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_une_seule_invitation_par_session_de_preparation(db, ctx, envois):
    """[CA14] Quatre gestes déposés en quelques minutes → une seule invitation."""
    _lier(db, 1, 555)

    for culture in ("tomate", "epinard", "tomate", "epinard"):
        depot = _deposer(db, ctx, culture=culture)
        svc_relances.inviter_si_premier_depot(db, 1, depot)

    assert len(envois.envoyes) == 1
    assert "attend" in envois.envoyes[0][1]
    assert envois.envoyes[0][2], "l'invitation porte un clavier, pas une commande à retaper"


def test_us224_pas_d_invitation_sans_compagnon_active(db, ctx, envois):
    """[CA21] Le dépôt reste possible ; c'est l'application qui invite à activer."""
    depot = _deposer(db, ctx)

    assert svc_relances.inviter_si_premier_depot(db, 1, depot) is False
    assert envois.envoyes == []
    assert svc.compter_en_attente(db, 1) == 1, "la file se remplit quand même"
    assert svc_relances.compagnon_joignable(db, 1) is False


def test_us224_relance_seulement_sur_un_creneau(db, ctx, envois):
    """[CA15] Deux créneaux par jour — jamais à l'heure exacte du dépôt.

    Un geste déposé à 15 h ne réveille personne à 3 h du matin.
    """
    _lier(db, 1, 555)
    depot = datetime(2026, 9, 21, 15, 0)
    _deposer(db, ctx, maintenant=depot)
    svc_relances.reglage(db, 1).derniere_invitation_le = depot
    db.commit()

    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 3, 0)) is False
    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 9, 0)) is True
    # Deux fois dans le même créneau : une seule bulle.
    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 9, 30)) is False
    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 18, 0)) is True


def test_us224_relance_remplace_la_precedente(db, ctx, envois):
    """[CA20] Chaque relance remplace la précédente, elle ne l'empile pas."""
    _lier(db, 1, 555)
    depot = datetime(2026, 9, 21, 15, 0)
    _deposer(db, ctx, maintenant=depot)
    svc_relances.reglage(db, 1).derniere_invitation_le = depot
    db.commit()

    svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 9, 0))
    svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 18, 0))

    assert len(envois.envoyes) == 1, "un seul envoi neuf"
    assert len(envois.edites) == 1, "la seconde relance ÉDITE la première"


def test_us224_relances_s_arretent_au_bout_de_trois_jours(db, ctx, envois):
    """[CA16] Qu'elles aient été suivies d'effet ou non, elles cessent."""
    _lier(db, 1, 555)
    depot = datetime(2026, 9, 21, 15, 0)
    # Déposé avec une longue durée de vie pour isoler la règle d'ARRÊT des
    # relances de celle de la péremption : ce test ne parle que de la première.
    geste = _deposer(db, ctx, maintenant=depot).geste
    geste.expire_le = depot + timedelta(days=30)
    svc_relances.reglage(db, 1).derniere_invitation_le = depot
    db.commit()

    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 23, 9, 0)) is True
    # Quatrième jour : le compagnon se tait.
    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 25, 9, 0)) is False


def test_us224_activite_remet_le_compteur_de_relance_a_zero(db, ctx, envois):
    """[CA19] Une simple consultation suffit — et ne rallonge aucun geste."""
    _lier(db, 1, 555)
    depot = datetime(2026, 9, 21, 15, 0)
    geste = _deposer(db, ctx, maintenant=depot).geste
    geste.expire_le = depot + timedelta(days=30)
    svc_relances.reglage(db, 1).derniere_invitation_le = depot
    db.commit()

    # Sans activité, les relances seraient éteintes au quatrième jour.
    svc_relances.noter_activite(db, 1, maintenant=datetime(2026, 9, 24, 12, 0))

    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 25, 9, 0)) is True


def test_us224_couper_les_relances_ne_vide_pas_la_file(db, ctx, envois):
    """[CA20] Les gestes restent, les invitations cessent — c'est la soupape."""
    _lier(db, 1, 555)
    for culture in ("tomate", "epinard", "tomate", "epinard"):
        _deposer(db, ctx, culture=culture)

    svc_relances.definir_relances(db, 1, actives=False)

    assert svc.compter_en_attente(db, 1) == 4, "les quatre gestes sont toujours là"
    assert svc_relances.relancer(db, 1, maintenant=datetime(2026, 9, 22, 9, 0)) is False
    assert svc_relances.avertir(db, 1, svc.lister_en_attente(db, 1)) is False
    assert svc_relances.notifier_purge(db, 1, svc.lister_en_attente(db, 1)) is False
    assert envois.envoyes == []

    # Et elle se défait : le réglage n'est pas un aller simple.
    svc_relances.definir_relances(db, 1, actives=True)
    assert db.query(FileGestesReglage).filter_by(user_id=1).first().relances_actives is True


# ══════════════════════════════════════════════════════════════════════════════
# CA17, CA18 — l'avertissement, et la purge annoncée
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_avertissement_quatre_heures_avant_la_purge(db, ctx, envois):
    """[CA17] Un ton distinct d'une relance : il annonce une PERTE."""
    _lier(db, 1, 555)
    depot = datetime(2026, 9, 21, 10, 0)
    _deposer(db, ctx, maintenant=depot)

    trop_tot = depot + timedelta(days=2)
    assert svc.gestes_a_avertir(db, trop_tot) == []

    echeance = depot + timedelta(days=3) - timedelta(hours=2)
    a_avertir = svc.gestes_a_avertir(db, echeance)
    assert len(a_avertir) == 1

    assert svc_relances.avertir(db, 1, a_avertir, maintenant=echeance) is True
    texte = envois.envoyes[-1][1]
    assert "Dernière occasion" in texte and "vidés" in texte
    assert "tomate" in texte, "l'avertissement NOMME les gestes concernés"

    # [CA17] Une seule fois par geste.
    assert svc.gestes_a_avertir(db, echeance) == []


def test_us224_purge_annoncee_et_rien_enregistre(db, ctx, envois):
    """[CA18] Ce qui a été vidé, et ce que cela décrivait."""
    _lier(db, 1, 555)
    depot = datetime(2026, 9, 21, 10, 0)
    _deposer(db, ctx, culture="tomate", maintenant=depot)
    _deposer(db, ctx, culture="epinard", maintenant=depot)

    apres = depot + timedelta(days=3, minutes=1)
    perimes = svc.gestes_perimes(db, apres)
    vides = [g for g in perimes if svc.perimer(g, maintenant=apres)]

    assert svc_relances.notifier_purge(db, 1, vides) is True
    texte = envois.envoyes[-1][1]
    assert "2 gestes" in texte
    assert "tomate" in texte and "epinard" in texte
    assert "Rien n'a été enregistré" in texte
    assert _nb_evenements(db) == 0


def test_us224_echec_d_envoi_de_purge_journalise_et_porte_par_l_application(db, ctx, monkeypatch, caplog):
    """[CA18] Cette notification n'a pas de seconde chance : son échec se sait.

    L'information reste alors portée par l'application — le geste périmé y est
    toujours listé comme tel.
    """
    _lier(db, 1, 555)
    monkeypatch.setattr(svc_notify, "envoyer", lambda *a, **k: None)
    geste = _deposer(db, ctx).geste
    svc.perimer(geste)

    with caplog.at_level("WARNING", logger="potager"):
        assert svc_relances.notifier_purge(db, 1, [geste]) is False

    assert "PERDUE" in caplog.text
    assert [g.id for g in svc.lister_sortis_recents(db, 1)] == [geste.id]


# ══════════════════════════════════════════════════════════════════════════════
# US-196 / CA9 — les gabarits de phrase passent le parseur déterministe
# ══════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("geste", [
    {"action": "semis", "culture": "tomate", "contexte_semis": "pepiniere"},
    {"action": "semis", "culture": "tomate", "contexte_semis": "pleine_terre"},
    {"action": "semis", "culture": "epinard", "contexte_semis": "pleine_terre",
     "parcelle": "carré nord"},
    {"action": "plantation", "culture": "tomate"},
    {"action": "plantation", "culture": "tomate", "parcelle": "carré nord"},
])
def test_us224_gabarit_de_phrase_reconnu_sans_appel_modele(db, ctx, geste):
    """Chaque gabarit passe dans le parseur — sinon la phrase proposée au
    jardinier coûterait un appel au modèle, l'exact contraire du but."""
    item = svc.construire_item(**geste)
    phrase = svc.phrase_a_dicter(item)

    resultat = parser_saisie(phrase, ctx, db=db)

    assert resultat.reconnu, f"{phrase!r} retombe sur le modèle : {resultat.raison}"
    lu = resultat.items[0]
    assert lu["action"] == geste["action"]
    assert lu["culture"] == geste["culture"]
    if geste.get("contexte_semis"):
        assert lu["contexte_semis"] == geste["contexte_semis"]
    if geste.get("parcelle"):
        assert lu["parcelle"] == geste["parcelle"]


def test_us224_lien_profond_ne_transporte_que_le_code(db, ctx):
    """Aucun nom de culture, aucune donnée du potager dans l'adresse."""
    geste = _deposer(db, ctx, parcelle_id=1, contexte_semis="pepiniere").geste

    lien = svc.lien_profond(geste.code, "MonPotagerBot")

    assert lien == f"https://t.me/MonPotagerBot?start={geste.code}"
    for fuite in ("tomate", "carré", "carre", "pepiniere"):
        assert fuite not in lien
    # Identifiant du bot introuvable : pas de lien cassé, la phrase suffit.
    assert svc.lien_profond(geste.code, None) is None
    assert svc.lien_profond(geste.code, "") is None


# ══════════════════════════════════════════════════════════════════════════════
# CA6, CA7, CA9, CA13 — le compagnon présente, enchaîne, et n'écrit pas
# ══════════════════════════════════════════════════════════════════════════════
def _update_telegram(chat_id: int = 555):
    """Update Telegram minimal — `reply_text` capture les messages envoyés."""
    message = SimpleNamespace(reply_text=AsyncMock())
    return SimpleNamespace(
        effective_chat=SimpleNamespace(id=chat_id),
        effective_user=SimpleNamespace(first_name="Camille", id=555),
        effective_message=message,
        message=message,
        callback_query=None,
    )


def _textes(update) -> str:
    return " ".join(str(appel.args[0]) for appel in update.message.reply_text.await_args_list)


@pytest.fixture
def bot(db, monkeypatch):
    """Le module bot, avec sa session pointée sur la base du test et le flux
    d'enregistrement remplacé par un espion — c'est précisément la frontière
    qu'on veut observer : ce que la file remet dans le flux EXISTANT."""
    from app.bot import file_gestes as bot_file
    from app.bot import saisie

    monkeypatch.setattr(bot_file, "SessionLocal", lambda: db)
    espion = AsyncMock()
    monkeypatch.setattr(saisie, "_parse_and_save", espion)
    return SimpleNamespace(module=bot_file, parse_and_save=espion, db=db)


@pytest.mark.asyncio
async def test_us224_geste_presente_par_le_flux_existant(bot, ctx):
    """[CA6] Item pré-parsé, zéro jeton, et rien d'écrit avant « Confirmer »."""
    _lier(bot.db, 1, 555)
    geste = _deposer(bot.db, ctx, parcelle_id=1, contexte_semis="pepiniere",
                     date="2026-09-19").geste
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.traiter_code_geste(update, ctx_tg, geste.code)

    bot.parse_and_save.assert_awaited_once()
    kwargs = bot.parse_and_save.await_args.kwargs
    items = kwargs["pre_parsed_items"]
    assert len(items) == 1
    assert items[0]["action"] == "semis"
    assert items[0]["parcelle"] == "carré nord"
    assert items[0]["date"] == "2026-09-19"
    # `pre_parsed_items` court-circuite l'appel au modèle : zéro jeton.
    assert items[0]["origine_parsing"] == ORIGINE_DETERMINISTE
    # [CA7] Le geste de la file voyage jusqu'au clavier de confirmation : c'est
    # lui qui fait afficher *Confirmer / Plus tard / Abandonner*.
    assert kwargs["geste_file"]["id"] == geste.id
    assert _nb_evenements(bot.db) == 0


@pytest.mark.asyncio
async def test_us224_ouvrir_un_lien_ne_retire_pas_le_geste(bot, ctx):
    """[CA8, CA11] Ouvrir, fermer, rouvrir : le geste est toujours là."""
    _lier(bot.db, 1, 555)
    geste = _deposer(bot.db, ctx).geste
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.traiter_code_geste(update, ctx_tg, geste.code)
    await bot.module.traiter_code_geste(update, ctx_tg, geste.code)

    assert bot.parse_and_save.await_count == 2
    assert svc.compter_en_attente(bot.db, 1) == 1


@pytest.mark.asyncio
async def test_us224_position_annoncee_quand_plusieurs_gestes(bot, ctx):
    """[CA6] « Geste 1 sur 3 » précède le récapitulatif."""
    _lier(bot.db, 1, 555)
    for culture in ("tomate", "epinard", "tomate"):
        _deposer(bot.db, ctx, culture=culture)
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.ouvrir_premier_geste(update, ctx_tg, 1)

    assert "Geste 1 sur 3" in _textes(update)


@pytest.mark.asyncio
async def test_us224_enchainement_annonce_ce_qui_reste(bot, ctx):
    """[CA9] Après un geste, le compagnon annonce le reste et propose le suivant."""
    _lier(bot.db, 1, 555)
    a = _deposer(bot.db, ctx, culture="tomate").geste
    _deposer(bot.db, ctx, culture="epinard")
    _deposer(bot.db, ctx, culture="tomate", date="2026-01-01")
    svc.confirmer(a)
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.proposer_suivant(update, ctx_tg, 1)

    assert "reste" in _textes(update) and "2 gestes" in _textes(update)


@pytest.mark.asyncio
async def test_us224_file_vide_le_dit(bot, ctx):
    """[CA9] Le jardinier doit savoir qu'il a fini."""
    _lier(bot.db, 1, 555)
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.proposer_suivant(update, ctx_tg, 1)

    assert "file est vide" in _textes(update)


@pytest.mark.asyncio
async def test_us224_bascule_de_potager_faite_et_dite(bot):
    """[CA13] Le geste s'enregistre dans le potager de SON dépôt — et ça se dit."""
    db = bot.db
    db.add(PotagerMembre(user_id=1, potager_id=2, role="editor"))
    db.query(User).filter(User.id == 1).first().potager_actif_id = 1
    db.commit()
    _lier(db, 1, 555)

    geste = _deposer(db, TenantContext(user_id=1, potager_id=2, role="editor"),
                     action="plantation").geste
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.traiter_code_geste(update, ctx_tg, geste.code)

    assert "Jardin B" in _textes(update), "la bascule doit nommer le potager"
    assert db.query(User).filter(User.id == 1).first().potager_actif_id == 2
    bot.parse_and_save.assert_awaited_once()


@pytest.mark.asyncio
async def test_us224_parcelle_disparue_refusee_et_retiree(bot, ctx):
    """[CA12] Refusé en clair, retiré de la file, et rien d'enregistré."""
    _lier(bot.db, 1, 555)
    geste = _deposer(bot.db, ctx, parcelle_id=1).geste
    bot.db.query(Parcelle).filter(Parcelle.id == 1).delete()
    bot.db.commit()

    update, ctx_tg = _update_telegram(), MagicMock(user_data={})
    await bot.module.traiter_code_geste(update, ctx_tg, geste.code)

    textes = _textes(update)
    assert "ne peut plus être enregistré" in textes and "carré nord" in textes
    bot.parse_and_save.assert_not_awaited()
    assert svc.compter_en_attente(bot.db, 1) == 0
    assert _nb_evenements(bot.db) == 0


@pytest.mark.asyncio
async def test_us224_conversation_non_liee_dit_que_les_gestes_attendent(bot, ctx):
    """[CA21] Le lien ouvert dans une conversation sans compte — rien n'est perdu."""
    _deposer(bot.db, ctx)
    update, ctx_tg = _update_telegram(chat_id=999), MagicMock(user_data={})

    await bot.module.traiter_code_geste(update, ctx_tg, db_code(bot.db))

    textes = _textes(update)
    assert "Compagnon pas encore activé" in textes
    assert "ne sont pas perdus" in textes
    bot.parse_and_save.assert_not_awaited()


def db_code(db) -> str:
    return db.query(GesteIntention).first().code


@pytest.mark.asyncio
async def test_us224_geste_perime_dit_qu_il_a_ete_vide(bot, ctx):
    """[CA3, CA18] Jamais un « code invalide » sec pour un geste qui a expiré."""
    _lier(bot.db, 1, 555)
    depot = datetime.utcnow() - timedelta(days=4)
    geste = _deposer(bot.db, ctx, maintenant=depot).geste
    update, ctx_tg = _update_telegram(), MagicMock(user_data={})

    await bot.module.traiter_code_geste(update, ctx_tg, geste.code)

    assert "vidé" in _textes(update)
    bot.parse_and_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_us224_consulter_la_file_est_une_activite(bot, ctx):
    """[CA10, CA19] /gestes ouvre le niveau 1 et remet le compteur à zéro."""
    _lier(bot.db, 1, 555)
    _deposer(bot.db, ctx)
    update, ctx_tg = _update_telegram(), MagicMock(user_data={"tenant_user_id": 1})

    await bot.module.cmd_gestes(update, ctx_tg)

    assert "1 geste en attente" in _textes(update)
    assert svc_relances.reglage(bot.db, 1).derniere_activite_le is not None


# ══════════════════════════════════════════════════════════════════════════════
# CA7, CA8 — les trois issues du récapitulatif
# ══════════════════════════════════════════════════════════════════════════════
def test_us224_trois_issues_nommees_sans_ambiguite(db):
    """[CA7] « Annuler » disparaît de ce flux : il ne distinguait pas les deux cas."""
    from app.bot.enregistrement import _boutons_confirmation

    items = [{"action": "plantation", "culture": "tomate",
              "date": date.today().isoformat()}]
    clavier = _boutons_confirmation(items, geste_file={"id": 1, "potager_id": 1})
    libelles = [b.text for rangee in clavier.inline_keyboard for b in rangee]
    donnees = [b.callback_data for rangee in clavier.inline_keyboard for b in rangee]

    assert any("Confirmer" in t for t in libelles)
    assert any("Plus tard" in t for t in libelles)
    assert any("Abandonner ce geste" in t for t in libelles)
    assert not any(t.strip().endswith("Annuler") for t in libelles)
    assert set(donnees) == {"action_confirm", "action_plus_tard", "action_abandonner"}


def test_us224_date_du_depot_corrigeable_depuis_le_recapitulatif(db):
    """[CA25] La date s'affiche en clair, et un bouton la corrige — s'il sert.

    Un geste déposé aujourd'hui n'a rien à corriger : le bouton n'apparaît pas,
    parce qu'une option sans effet est une option à lire pour rien.
    """
    from app.bot.enregistrement import _boutons_confirmation, _build_action_summary

    hier = (date.today() - timedelta(days=2)).isoformat()
    items = [{"action": "semis", "culture": "tomate", "date": hier}]
    geste_file = {"id": 1, "potager_id": 1}

    assert f"📅 Date : *{hier}*" in _build_action_summary(items)

    donnees = [b.callback_data
               for rangee in _boutons_confirmation(items, geste_file).inline_keyboard
               for b in rangee]
    assert "action_dater_aujourdhui" in donnees

    aujourd_hui = [{"action": "semis", "culture": "tomate", "date": date.today().isoformat()}]
    donnees = [b.callback_data
               for rangee in _boutons_confirmation(aujourd_hui, geste_file).inline_keyboard
               for b in rangee]
    assert "action_dater_aujourdhui" not in donnees


def test_us224_saisie_dictee_garde_confirmer_annuler(db):
    """Le flux d'US-021 est INCHANGÉ hors de la file : pas de régression."""
    from app.bot.enregistrement import _boutons_confirmation

    clavier = _boutons_confirmation([{"action": "plantation", "culture": "tomate"}])
    donnees = [b.callback_data for rangee in clavier.inline_keyboard for b in rangee]

    assert donnees == ["action_confirm", "action_cancel"]


@pytest.mark.asyncio
async def test_us224_plus_tard_repose_le_geste_et_le_dit(db, ctx, monkeypatch):
    """[CA7, CA8] « Plus tard » repose le geste dans la file, et le DIT."""
    from app.bot import enregistrement

    geste = _deposer(db, ctx).geste
    query = SimpleNamespace(data="action_plus_tard", answer=AsyncMock(),
                            edit_message_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query, effective_user=SimpleNamespace(id=555),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    ctx_tg = MagicMock(user_data={})
    enregistrement._ACTION_PENDING[555] = {
        "items": [{"action": "semis"}], "texte": "semis", "ts": 1e12,
        "geste_file": {"id": geste.id, "potager_id": 1, "user_id": 1,
                       "position": 1, "total": 1},
    }

    await enregistrement._action_confirm_cb(update, ctx_tg)

    assert "reste dans votre file" in query.edit_message_text.await_args.args[0]
    # Relu depuis la base, et non par `refresh` : le compagnon a détaché ce
    # geste de la session en annonçant la suite — ce que la session partagée du
    # test rend visible, et que deux processus distincts masqueraient.
    relu = db.query(GesteIntention).filter(GesteIntention.id == geste.id).first()
    assert relu.etat == svc.ETAT_EN_ATTENTE
    assert svc.compter_en_attente(db, 1) == 1


@pytest.mark.asyncio
async def test_us224_abandonner_retire_le_geste_et_le_dit(db, ctx):
    """[CA7] « Abandonner ce geste » le retire définitivement, et le DIT."""
    from app.bot import enregistrement

    geste = _deposer(db, ctx).geste
    query = SimpleNamespace(data="action_abandonner", answer=AsyncMock(),
                            edit_message_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query, effective_user=SimpleNamespace(id=555),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    enregistrement._ACTION_PENDING[555] = {
        "items": [{"action": "semis"}], "texte": "semis", "ts": 1e12,
        "geste_file": {"id": geste.id, "potager_id": 1, "user_id": 1,
                       "position": 1, "total": 1},
    }

    await enregistrement._action_confirm_cb(update, MagicMock(user_data={}))

    assert "abandonné" in query.edit_message_text.await_args.args[0].lower()
    db.refresh(geste)
    assert geste.etat == svc.ETAT_ABANDONNE
    assert _nb_evenements(db) == 0


@pytest.mark.asyncio
async def test_us224_delai_de_confirmation_depasse_laisse_le_geste_en_file(db, ctx):
    """[CA8] La troisième façon de perdre un geste sous US-196 disparaît.

    Une minute d'hésitation, un appel qui passe : le récapitulatif expire, le
    geste reste.
    """
    from app.bot import enregistrement

    geste = _deposer(db, ctx).geste
    query = SimpleNamespace(data="action_confirm", answer=AsyncMock(),
                            edit_message_text=AsyncMock())
    update = SimpleNamespace(
        callback_query=query, effective_user=SimpleNamespace(id=555),
        effective_message=SimpleNamespace(reply_text=AsyncMock()),
    )
    enregistrement._ACTION_PENDING[555] = {
        "items": [{"action": "semis"}], "texte": "semis",
        "ts": 0,  # très ancien : le délai est largement dépassé
        "geste_file": {"id": geste.id, "potager_id": 1, "user_id": 1,
                       "position": 1, "total": 1},
    }

    await enregistrement._action_confirm_cb(update, MagicMock(user_data={}))

    message = query.edit_message_text.await_args.args[0]
    assert "expirée" in message and "toujours en attente" in message
    db.refresh(geste)
    assert geste.etat == svc.ETAT_EN_ATTENTE
    assert svc.compter_en_attente(db, 1) == 1


# ══════════════════════════════════════════════════════════════════════════════
# INC-003 — une clarification (CA9) ne doit pas faire perdre `geste_file`
# ══════════════════════════════════════════════════════════════════════════════
# Reproduction observée le 21/09/2026 : un semis de la file sans quantité
# demandait "Quelle quantité ?", la réponse était bien enregistrée, mais le
# geste restait `en_attente` — `_QUANTITE_PENDING` perdait `geste_file` en
# route, si bien que `_action_confirm_cb` ne pouvait plus retrouver le geste
# à retirer de la file (CA8) : /gestes le représentait indéfiniment.
@pytest.mark.asyncio
async def test_inc003_quantite_manquante_garde_le_geste_file(monkeypatch):
    from app.bot import messages, saisie

    espion = AsyncMock()
    monkeypatch.setattr(messages, "_parse_and_save", espion)
    monkeypatch.setattr(messages, "_verifier_liaison_ou_onboarding", AsyncMock(return_value=True))

    geste_file = {"id": 5, "potager_id": 1, "user_id": 1, "position": 1, "total": 2}
    saisie._QUANTITE_PENDING[555] = {
        "items": [{"action": "semis", "culture": "tomate"}],
        "texte": "semis tomate", "ts": 0, "geste_file": geste_file,
    }
    update = SimpleNamespace(
        message=SimpleNamespace(text="10 graines"),
        effective_user=SimpleNamespace(id=555),
    )

    try:
        await messages.handle_text(update, SimpleNamespace(user_data={}))
    finally:
        saisie._QUANTITE_PENDING.pop(555, None)

    espion.assert_awaited_once()
    assert espion.await_args.kwargs["geste_file"] == geste_file


@pytest.mark.asyncio
async def test_inc003_nb_pieds_manquant_garde_le_geste_file(monkeypatch):
    """[US-036 CA10] Même relais, pour la récolte végétative pesée sans nombre
    de pieds — la même perte de `geste_file` s'y produisait."""
    from app.bot import messages, saisie

    espion = AsyncMock()
    monkeypatch.setattr(messages, "_parse_and_save", espion)
    monkeypatch.setattr(messages, "_verifier_liaison_ou_onboarding", AsyncMock(return_value=True))

    geste_file = {"id": 9, "potager_id": 1, "user_id": 1, "position": 1, "total": 1}
    saisie._RECOLTE_PIECES_PENDING[555] = {
        "items": [{"action": "recolte", "culture": "epinard", "quantite": "2", "unite": "kg"}],
        "texte": "recolte epinard 2 kg", "ts": 0, "geste_file": geste_file,
    }
    update = SimpleNamespace(
        message=SimpleNamespace(text="6 pieds"),
        effective_user=SimpleNamespace(id=555),
    )

    try:
        await messages.handle_text(update, SimpleNamespace(user_data={}))
    finally:
        saisie._RECOLTE_PIECES_PENDING.pop(555, None)

    espion.assert_awaited_once()
    assert espion.await_args.kwargs["geste_file"] == geste_file
