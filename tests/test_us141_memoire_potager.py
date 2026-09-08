"""
tests/test_us141_memoire_potager.py
[US-141] Rendre la mémoire du potager consultable en langage naturel

Couverture des critères d'acceptance CA1 → CA13.

Trois partis pris expliquent la forme de ce fichier, et ils viennent de l'US
elle-même plutôt que d'une habitude de test :

- **Le CA9 est le test le plus important de l'US, et il a été écrit en premier**
  (note technique de l'US). La question posée depuis le potager B ne se contente
  pas d'être « une question du même domaine » : elle REPREND MOT POUR MOT la
  note privée du potager A. Une question quelconque ne prouverait rien — elle
  pourrait ne rien retourner par manque de correspondance lexicale, et non par
  isolation. Le test échouerait donc pour une raison différente de celle qu'il
  prétend contrôler.

- **L'isolation est contrôlée comme PROPRIÉTÉ DE LA REQUÊTE, pas seulement des
  données.** Une note bien indexée est invisible d'ailleurs parce qu'elle porte
  un `potager_id`. Le CA8 demande davantage : qu'un fragment de la famille
  `memoire_potager` soit inatteignable depuis la clause de savoir partagé, même
  s'il naissait un jour sans potager. Ce cas pathologique est donc FABRIQUÉ ici,
  en contournant délibérément la validation d'écriture, pour vérifier que la
  lecture le refuse quand même.

- **Le « zéro jeton » du CA7 se démontre.** Un double fait échouer le test dès
  que `llm.passerelle.appeler_chat` est sollicité sur un chemin de mémoire —
  même dispositif que `tests/test_us098_socle_connaissance.py`, et pour la même
  raison : une restitution qui appellerait un modèle reformulerait la note, ce
  que l'arbitrage « extrait fidèle » interdit.

⚠️ Ces tests tournent sur SQLite (`tests/conftest.py`), donc sur le repli de
`app/services/connaissance.py`. Ils protègent la MÉCANIQUE de l'indexation, de
la restitution et de l'isolation — pas la qualité du classement plein texte
français, qui se mesure sur PostgreSQL.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

import pytest

from app.services import cache_questions as cq
from app.services import connaissance, evenements as svc_evenements, memoire_potager
from app.services import potagers as svc_potagers
from app.services import reponses_chiffrees as rc
from app.services.context import TenantContext
from app.services.potager_actif import ETAT_ARCHIVE
from database.models import (
    CultureConfig, Evenement, KnowledgeChunk, KnowledgeDocument, Parcelle, Potager,
    QuestionCache, User,
)
from llm import passerelle, routeur
from llm.passerelle import ReponseLLM
from utils.parcelles import rename_parcelle

CTX_A = TenantContext(user_id=1, potager_id=1, role="owner")
CTX_B = TenantContext(user_id=2, potager_id=2, role="owner")

# La note du potager A, telle que le jardinier l'a écrite. Elle sert de texte de
# référence à tout le fichier : c'est elle qu'on cherche, qu'on cite, et qu'on
# vérifie absente du potager B.
NOTE_A = (
    "La planche du fond reste détrempée trois jours après chaque orage, "
    "les pieds jaunissent par le bas."
)


# ═════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═════════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _cache_classification_propre():
    routeur.vider_cache()
    yield
    routeur.vider_cache()


@pytest.fixture
def base(test_db):
    """Deux potagers, deux jardiniers, une parcelle chacun — le décor minimal
    d'un test d'isolation."""
    test_db.add_all([
        User(id=1, email="a@potager.test"),
        User(id=2, email="b@potager.test"),
    ])
    test_db.flush()
    test_db.add_all([
        Potager(id=1, nom="Jardin A", proprietaire_id=1),
        Potager(id=2, nom="Jardin B", proprietaire_id=2),
    ])
    test_db.add_all([
        CultureConfig(nom="tomate", type_organe_recolte="reproducteur", potager_id=None),
        CultureConfig(nom="courgette", type_organe_recolte="reproducteur", potager_id=None),
    ])
    test_db.flush()
    test_db.add_all([
        Parcelle(id=10, nom="nord", nom_normalise="nord", potager_id=1),
        Parcelle(id=20, nom="nord", nom_normalise="nord", potager_id=2),
    ])
    # `valider_evenement` (US-049) refuse une note sur une culture dont le
    # potager n'a aucune trace : les plantations ci-dessous sont le décor
    # minimal qui rend une note recevable, pas le sujet du test.
    for potager_id, parcelle_id in ((1, 10), (2, 20)):
        for culture in ("tomate", "courgette"):
            test_db.add(Evenement(
                type_action="plantation", culture=culture, parcelle_id=parcelle_id,
                date=datetime(2025, 4, 1), potager_id=potager_id,
            ))
    test_db.commit()
    return test_db


@pytest.fixture
def sans_appel_modele(monkeypatch):
    """[CA7] Fait échouer le test si un modèle est appelé sur un chemin de mémoire."""
    def _interdit(*args, **kwargs):
        raise AssertionError(
            "Un appel au modèle a eu lieu sur la mémoire du potager, "
            "qui doit se lire à coût nul (CA7)"
        )

    monkeypatch.setattr("llm.passerelle.appeler_chat", _interdit)


def _noter(db, ctx, constat, *, parcelle="nord", culture="tomate",
           date="2025-05-12", label="Observation"):
    """Enregistre une note par le chemin RÉEL du bot (US-038), pas en insérant
    un `Evenement` à la main : le CA2 porte précisément sur ce chemin-là."""
    return svc_evenements.creer_evenement_observation(
        db, ctx,
        {"constat": constat, "parcelle": parcelle, "culture": culture, "date": date},
        f"note dictée : {constat}", label,
    )


def _fiche_generale(db, reference, titre, contenu, *, culture_id=None):
    """Une fiche du savoir PARTAGÉ — l'autre registre du CA6."""
    document, _ = connaissance.enregistrer_document(
        db, reference=reference, titre=titre,
        famille=connaissance.FAMILLE_AGRONOMIE, source="Corpus interne",
        niveau_confiance=connaissance.NIVEAU_VERIFIE, empreinte=reference,
        potager_id=None,
    )
    connaissance.remplacer_fragments(db, document, [
        connaissance.FragmentAIngerer(
            reference=f"{reference}#00", ordre=0, intitule=None,
            contenu=contenu, culture_id=culture_id,
            # Comme le fait l'ingestion réelle : sans type, une fiche serait
            # écartée par la restriction de métadonnée (US-098 / CA6) que la
            # note, elle, satisfait — et le mélange des registres du CA6 ne se
            # produirait jamais.
            type=connaissance.detecter_type(contenu),
        )
    ])
    db.commit()
    return document


def _fragments_memoire(db, potager_id=None):
    requete = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.famille == connaissance.FAMILLE_MEMOIRE_POTAGER
    )
    if potager_id is not None:
        requete = requete.filter(KnowledgeDocument.potager_id == potager_id)
    return requete.all()


# ═════════════════════════════════════════════════════════════════════════════
# CA1 — famille `memoire_potager`, potager_id JAMAIS nul
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca1_une_note_est_indexee_dans_la_famille_memoire(base, sans_appel_modele):
    """CA1 — la note prend la famille `memoire_potager` et le potager de son auteur."""
    event = _noter(base, CTX_A, NOTE_A)

    documents = _fragments_memoire(base)
    assert len(documents) == 1
    document = documents[0]
    assert document.famille == connaissance.FAMILLE_MEMOIRE_POTAGER
    assert document.potager_id == 1
    assert document.reference == memoire_potager.reference_document(event)


def test_us141_ca1_un_potager_id_nul_est_refuse_a_l_ecriture(base):
    """CA1 — « **jamais** avec un potager_id nul » : le refus est structurel, posé
    au seul point d'écriture de la table, donc vrai de tout chemin d'écriture."""
    with pytest.raises(ValueError, match="memoire_potager"):
        connaissance.enregistrer_document(
            base, reference="memoire/fuite", titre="Note orpheline",
            famille=connaissance.FAMILLE_MEMOIRE_POTAGER, source="x",
            niveau_confiance=connaissance.NIVEAU_VERIFIE, empreinte="e",
            potager_id=None,
        )


def test_us141_ca1_un_bulletin_meteo_automatique_n_entre_pas_dans_la_memoire(base):
    """CA1 — le job météo enregistre son relevé comme une `observation` : c'est
    techniquement une note, mais personne ne l'a écrite.

    Relevé sur une base réelle le 08/09/2026 : la mémoire d'un potager d'une
    saison contenait une écrasante majorité de bulletins de température, qui
    portent le vocabulaire du jardinier (« arrosage », « surveiller les jeunes
    plants ») sans rien devoir à son observation. Ils noient les vraies notes."""
    bulletin = Evenement(
        type_action="observation", parcelle_id=10,
        commentaire="🌧️ Pluie légère · Min 1.1°C / Max 11.3°C · Vent 8.4km/h",
        texte_original=memoire_potager.BULLETIN_AUTO_METEO,
        date=datetime(2026, 3, 27), potager_id=1,
    )
    base.add(bulletin)
    base.commit()

    assert memoire_potager.est_memorisable(bulletin) is False
    assert memoire_potager.synchroniser_evenement(base, bulletin) is False
    assert _fragments_memoire(base) == []
    assert memoire_potager.reprise_initiale(base)["notes"] == 0


def test_us141_ca1_un_bulletin_deja_indexe_est_elague_a_la_reprise(base, sans_appel_modele):
    """CA1 — les bulletins déjà versés dans la mémoire par une version
    antérieure en sortent à la reprise suivante, sans intervention manuelle."""
    bulletin = Evenement(
        type_action="observation", commentaire="🌧️ Pluie légère · Min 1.1°C",
        texte_original=memoire_potager.BULLETIN_AUTO_METEO,
        date=datetime(2026, 3, 27), potager_id=1,
    )
    base.add(bulletin)
    base.flush()
    # Indexé « à l'ancienne », en contournant le filtre qu'on vient de poser.
    document, _ = connaissance.enregistrer_document(
        base, reference=memoire_potager.reference_document(bulletin),
        titre="Note du 27 mars 2026", famille=connaissance.FAMILLE_MEMOIRE_POTAGER,
        source=memoire_potager.SOURCE_MEMOIRE,
        niveau_confiance=memoire_potager.NIVEAU_MEMOIRE, empreinte="ancienne",
        potager_id=1,
    )
    connaissance.remplacer_fragments(base, document, [
        connaissance.FragmentAIngerer(reference="x#00", ordre=0, intitule=None,
                                      contenu="Pluie légère")
    ])
    base.commit()
    assert _fragments_memoire(base)

    rapport = memoire_potager.reprise_initiale(base)

    assert rapport["elaguees"] == 1
    assert _fragments_memoire(base) == []


def test_us141_ca1_un_evenement_structure_n_entre_jamais_dans_la_memoire(base):
    """CA1 + arbitrage tranché — un semis se répond en SQL (US-096). L'indexer
    donnerait une réponse approximative sur une donnée parfaitement structurée."""
    semis = Evenement(type_action="semis", culture="tomate", quantite=20,
                      unite="graines", commentaire="premier semis de la saison",
                      date=datetime(2025, 3, 1), potager_id=1)
    base.add(semis)
    base.commit()

    assert memoire_potager.est_memorisable(semis) is False
    assert memoire_potager.synchroniser_evenement(base, semis) is False
    assert _fragments_memoire(base) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA2 — indexation automatique à l'enregistrement
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca2_l_indexation_est_automatique_a_l_enregistrement(base, sans_appel_modele):
    """CA2 — aucune action du jardinier : la note est cherchable dès son
    enregistrement, sans reprise ni commande intermédiaire."""
    _noter(base, CTX_A, NOTE_A)

    contexte = connaissance.rechercher(base, CTX_A, "planche du fond détrempée après l'orage")
    assert contexte.passages, "la note n'est pas retrouvable juste après sa saisie"
    assert contexte.passages[0].prive is True


def test_us141_ca2_un_echec_d_indexation_ne_fait_pas_echouer_la_note(base, monkeypatch):
    """Note technique — « la note prime sur son index, l'index se rattrape ».

    Perdre une note parce que son indexation a échoué serait irréparable ;
    perdre son index ne coûte qu'une reprise."""
    def _explose(*args, **kwargs):
        raise RuntimeError("index indisponible")

    monkeypatch.setattr(memoire_potager, "synchroniser_evenement", _explose)

    event = _noter(base, CTX_A, NOTE_A)

    assert base.get(Evenement, event.id) is not None
    assert _fragments_memoire(base) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA3 — reprise initiale rejouable, sans doublon
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca3_la_reprise_indexe_les_notes_deja_enregistrees(base, sans_appel_modele):
    """CA3 — des notes antérieures à l'US entrent dans la mémoire."""
    for i in range(3):
        base.add(Evenement(
            type_action="observation", culture="tomate", parcelle_id=10,
            commentaire=f"[Observation] constat numéro {i} sur la planche du fond",
            date=datetime(2024, 6, 1) + timedelta(days=i), potager_id=1,
        ))
    base.commit()

    rapport = memoire_potager.reprise_initiale(base)
    assert rapport["notes"] == 3
    assert rapport["indexees"] == 3
    assert len(_fragments_memoire(base, potager_id=1)) == 3


def test_us141_ca3_la_reprise_pose_le_scope_rls_potager_par_potager(base, monkeypatch):
    """CA3 — la reprise est multi-tenant par nature, et les tables de
    connaissance sont sous RLS (migration_v42). Sans scope, PostgreSQL refuse la
    première requête ; avec un scope UNIQUE, la politique `WITH CHECK` refuse
    d'écrire les lignes du second potager. Le scope doit donc changer à chaque
    potager — invisible sous SQLite, fatal en production."""
    from database import db as db_module

    vus: list[int] = []
    scope_reel = db_module.tenant_scope

    @contextmanager
    def _espion(potager_id):
        vus.append(potager_id)
        with scope_reel(potager_id):
            yield

    monkeypatch.setattr(memoire_potager, "tenant_scope", _espion)

    _noter(base, CTX_A, NOTE_A)
    _noter(base, CTX_B, "les courges du fond ont pris le mildiou", culture="courgette")
    memoire_potager.reprise_initiale(base)

    assert vus == [1, 2], f"scope RLS non posé par potager : {vus}"


def test_us141_ca3_la_reprise_est_rejouable_sans_doublon(base, sans_appel_modele):
    """CA3 — le second passage ne crée rien et ne réécrit rien. L'idempotence
    tient à l'identité stable du document, pas à une précaution de l'outil."""
    _noter(base, CTX_A, NOTE_A)
    memoire_potager.reprise_initiale(base)
    avant = base.query(KnowledgeChunk).count()

    rapport = memoire_potager.reprise_initiale(base)

    assert rapport["indexees"] == 0
    assert rapport["inchangees"] == 1
    assert base.query(KnowledgeChunk).count() == avant
    assert len(_fragments_memoire(base)) == 1


def test_us141_ca3_la_reprise_a_blanc_n_ecrit_rien(base, sans_appel_modele):
    """CA3 — `--dry-run` rapporte sans toucher à la base."""
    base.add(Evenement(type_action="observation", commentaire="[Observation] rien",
                       date=datetime(2024, 6, 1), potager_id=1))
    base.commit()

    rapport = memoire_potager.reprise_initiale(base, dry_run=True)

    assert rapport["notes"] == 1
    assert _fragments_memoire(base) == []


def test_us141_ca3_la_reprise_elague_une_memoire_devenue_orpheline(base, sans_appel_modele):
    """CA3 + CA11 — une note disparue hors de la couche services (base
    restaurée, suppression en SQL direct) est rattrapée par la reprise."""
    event = _noter(base, CTX_A, NOTE_A)
    base.query(Evenement).filter(Evenement.id == event.id).delete()
    base.commit()

    rapport = memoire_potager.reprise_initiale(base)

    assert rapport["elaguees"] == 1
    assert _fragments_memoire(base) == []


# ═════════════════════════════════════════════════════════════════════════════
# CA4 — le fragment garde son lien, sa date, sa parcelle et sa culture
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca4_le_fragment_conserve_evenement_date_parcelle_et_culture(base, sans_appel_modele):
    """CA4 — les quatre attaches sont portées par le fragment lui-même."""
    event = _noter(base, CTX_A, NOTE_A)
    fragment = base.query(KnowledgeChunk).one()
    culture = base.query(CultureConfig).filter(CultureConfig.nom == "tomate").one()

    assert str(event.id) in fragment.reference, "lien vers l'événement d'origine perdu"
    assert "12 mai 2025" in fragment.titre_document
    assert "parcelle nord" in fragment.titre_document
    assert fragment.culture_id == culture.id
    assert fragment.potager_id == 1


def test_us141_ca4_une_note_sans_parcelle_reste_indexable(base, sans_appel_modele):
    """CA4 — « quand elle existe » : l'absence de parcelle n'empêche rien."""
    _noter(base, CTX_A, "les semis de courgette lèvent mal cette année",
           parcelle=None, culture="courgette")

    fragment = base.query(KnowledgeChunk).one()
    assert "parcelle" not in fragment.titre_document
    assert connaissance.rechercher(base, CTX_A, "les semis lèvent mal").passages


# ═════════════════════════════════════════════════════════════════════════════
# CA5 — restitution : date, parcelle, extrait FIDÈLE
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca5_la_note_est_restituee_avec_sa_date_et_sa_parcelle(base, sans_appel_modele):
    """CA5 — la réponse servie porte la date, la parcelle et le texte cité."""
    _noter(base, CTX_A, NOTE_A)

    contexte = connaissance.rechercher(base, CTX_A, "planche du fond détrempée après l'orage")
    texte = connaissance.restituer(contexte)

    assert "12 mai 2025" in texte
    assert "parcelle nord" in texte
    assert NOTE_A in texte


def test_us141_ca5_le_texte_restitue_est_fidele_au_texte_saisi(base, sans_appel_modele):
    """CA5 + arbitrage « extrait fidèle » — pas une reformulation. Le texte
    ressort caractère pour caractère, entre guillemets : une note résumée perd
    sa valeur de preuve, qui est toute sa raison d'être."""
    _noter(base, CTX_A, NOTE_A)

    contexte = connaissance.rechercher(base, CTX_A, "planche du fond détrempée après l'orage")

    assert contexte.passages[0].contenu == NOTE_A
    assert f"« {NOTE_A} »" in connaissance.restituer(contexte)


def test_us141_ca5_la_categorie_de_saisie_n_est_pas_prise_pour_la_parole_du_jardinier(base):
    """CA5 — « [Maladie / ravageur] » est un classement fait par l'application.
    Il part au titre, pas dans le texte cité."""
    _noter(base, CTX_A, NOTE_A, label="Maladie / ravageur")

    fragment = base.query(KnowledgeChunk).one()
    assert fragment.contenu == NOTE_A
    assert "Maladie / ravageur" in fragment.titre_document


def test_us141_ca5_le_registre_de_rappel_indexe_sans_jamais_s_afficher(base, sans_appel_modele):
    """CA5 — les mots du rappel (« noté », « l'an dernier ») sont indexés au
    poids du titre pour que la question retrouve la note, et n'entrent JAMAIS
    dans le texte restitué. Un mot d'index affiché serait un mot prêté au
    jardinier — la fidélité de l'extrait tomberait avec lui."""
    _noter(base, CTX_A, NOTE_A)
    fragment = base.query(KnowledgeChunk).one()

    assert "carnet" in (fragment.recherche_fts or ""), "le registre de rappel n'est pas indexé"
    assert "carnet" not in fragment.contenu
    assert "carnet" not in fragment.titre_document

    contexte = connaissance.rechercher(base, CTX_A, "qu'avais-je noté sur la parcelle nord ?")
    texte = connaissance.restituer(contexte)
    for mot in ("carnet", "souvenir", "constate"):
        assert mot not in texte.lower(), f"terme d'indexation affiché au jardinier : {mot}"


def test_us141_ca5_une_note_tres_longue_est_decoupee_comme_un_document(base):
    """Note technique — « une note très longue est découpée comme n'importe quel
    document ; une note courte reste un fragment unique »."""
    courte = memoire_potager.decouper("Trois limaces ce matin.")
    assert courte == ["Trois limaces ce matin."]

    longue = "Une phrase de constat sur la planche du fond. " * 60
    morceaux = memoire_potager.decouper(longue)
    assert len(morceaux) > 1
    assert all(len(m) <= memoire_potager.TAILLE_MAX_FRAGMENT for m in morceaux)
    # Rien n'est perdu au découpage : une note tronquée serait citée de travers.
    assert "".join(m.replace(" ", "") for m in morceaux) == longue.replace(" ", "")


# ═════════════════════════════════════════════════════════════════════════════
# CA6 — mémoire et savoir général distingués
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca6_les_deux_registres_sont_distingues_a_la_restitution(base, sans_appel_modele):
    """CA6 — « ta note du 12 mai indique… » et « en général… » sont deux
    registres. Les confondre reviendrait à faire dire au jardinier ce qu'il n'a
    pas dit."""
    _noter(base, CTX_A, "les limaces ont dévoré mes jeunes plants cette nuit")
    _fiche_generale(base, "agro/limaces.md", "Limaces",
                    "Les limaces sortent la nuit par temps humide et attaquent les jeunes plants.")

    contexte = connaissance.rechercher(base, CTX_A, "limaces sur les jeunes plants")
    assert any(p.prive for p in contexte.passages)
    assert any(not p.prive for p in contexte.passages)

    texte = connaissance.restituer(contexte)
    assert connaissance.REGISTRE_MEMOIRE in texte
    assert connaissance.REGISTRE_GENERAL in texte


def test_us141_ca6_le_registre_est_porte_par_la_matiere_transmise_au_modele(base):
    """CA6 — l'étiquette de registre est dans le contexte lui-même, pas
    seulement dans le prompt : un modèle à qui l'on donne note et fiche dans un
    bloc indistinct attribuera l'une à l'autre."""
    _noter(base, CTX_A, "les limaces ont dévoré mes jeunes plants cette nuit")
    _fiche_generale(base, "agro/limaces.md", "Limaces",
                    "Les limaces sortent la nuit par temps humide.")

    contexte = connaissance.rechercher(base, CTX_A, "limaces sur les jeunes plants")
    matiere = connaissance.contexte_pour_raisonnement(contexte)

    assert "MÉMOIRE DU POTAGER" in matiere
    assert "SAVOIR GÉNÉRAL" in matiere
    assert "sans la reformuler" in matiere


def test_us141_ca6_le_prompt_de_raisonnement_impose_la_distinction(base):
    """CA6 — la consigne existe aussi côté prompt, en complément de la matière."""
    prompt = routeur._PROMPT_FIXE_RAISONNEMENT
    assert "MÉMOIRE DU POTAGER" in prompt
    assert "en général" in prompt.lower()


def test_us141_ca6_une_reponse_purement_generale_ne_s_etiquette_pas(base, sans_appel_modele):
    """CA6 — l'étiquette signale un MÉLANGE. L'afficher sur une réponse qui
    n'en est pas un en ferait un ornement que plus personne ne lit."""
    _fiche_generale(base, "agro/limaces.md", "Limaces",
                    "Les limaces sortent la nuit par temps humide.")

    contexte = connaissance.rechercher(base, CTX_A, "limaces temps humide")
    texte = connaissance.restituer(contexte)

    assert connaissance.REGISTRE_GENERAL not in texte
    assert connaissance.REGISTRE_MEMOIRE not in texte


# ═════════════════════════════════════════════════════════════════════════════
# CA7 — la restitution ne consomme aucun jeton
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca7_la_lecture_de_la_memoire_coute_zero_jeton(base, sans_appel_modele):
    """CA7 — recherche et restitution ne passent par aucun modèle. Le double
    `sans_appel_modele` fait échouer le test au premier appel."""
    _noter(base, CTX_A, NOTE_A)

    contexte = connaissance.rechercher(base, CTX_A, "planche du fond détrempée après l'orage")
    texte = connaissance.restituer(contexte)

    assert texte and contexte.issue == connaissance.ISSUE_SERVI


def test_us141_ca7_le_module_de_memoire_n_importe_aucun_modele():
    """CA7 — vérification statique : `memoire_potager` ne connaît pas la
    passerelle. Un import suffirait à rendre l'affirmation fragile."""
    from pathlib import Path

    import re as _re

    source = (Path(__file__).resolve().parents[1] / "app" / "services"
              / "memoire_potager.py").read_text(encoding="utf-8")
    imports = _re.findall(r"^\s*(?:from|import)\s+\S+", source, _re.MULTILINE)
    assert not [ligne for ligne in imports
                if "passerelle" in ligne or "groq" in ligne.lower() or "llm" in ligne]


# ═════════════════════════════════════════════════════════════════════════════
# CA8 — l'isolation est une propriété de la REQUÊTE
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca8_la_famille_memoire_est_exclue_de_la_clause_de_savoir_partage(base):
    """CA8 — le SQL émis exclut explicitement la famille du savoir partagé."""
    sql = str(connaissance._requete_base(base, CTX_A).statement).lower()
    assert "famille" in sql, "la clause de savoir partagé ne discrimine pas la famille"
    assert connaissance.FAMILLE_MEMOIRE_POTAGER in str(
        connaissance._requete_base(base, CTX_A).statement.compile(
            compile_kwargs={"literal_binds": True}
        )
    )


def test_us141_ca8_un_fragment_de_memoire_sans_potager_reste_inatteignable(base, sans_appel_modele):
    """CA8 — « un fragment de cette famille ne peut structurellement pas être
    partagé ». Le cas pathologique est FABRIQUÉ en contournant la validation
    d'écriture : c'est la lecture, et elle seule, qui doit le refuser."""
    document = KnowledgeDocument(
        reference="memoire/fabrique", titre="Note sans potager",
        famille=connaissance.FAMILLE_MEMOIRE_POTAGER, source="x",
        niveau_confiance=connaissance.NIVEAU_VERIFIE, empreinte="e", potager_id=None,
    )
    base.add(document)
    base.flush()
    connaissance.remplacer_fragments(base, document, [
        connaissance.FragmentAIngerer(reference="memoire/fabrique#00", ordre=0,
                                      intitule=None, contenu=NOTE_A)
    ])
    base.commit()

    for ctx in (CTX_A, CTX_B):
        contexte = connaissance.rechercher(base, ctx, NOTE_A)
        assert contexte.passages == (), (
            "un fragment de mémoire sans potager a été servi comme du savoir partagé"
        )


def test_us141_ca8_une_fiche_globale_reste_partagee(base, sans_appel_modele):
    """CA8 — l'exclusion ne porte QUE sur la mémoire : le savoir agronomique
    global continue de servir tous les jardins."""
    _fiche_generale(base, "agro/limaces.md", "Limaces",
                    "Les limaces sortent la nuit par temps humide.")

    for ctx in (CTX_A, CTX_B):
        assert connaissance.rechercher(base, ctx, "limaces temps humide").passages


# ═════════════════════════════════════════════════════════════════════════════
# CA9 — aucune fuite entre potagers (le test le plus important de l'US)
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca9_une_note_du_potager_a_est_invisible_du_potager_b(base, sans_appel_modele):
    """CA9 — la question du potager B reprend MOT POUR MOT la note du potager A.

    Une question quelconque ne prouverait rien : elle pourrait ne rien retourner
    par simple absence de correspondance lexicale, et le test passerait pour de
    mauvaises raisons. La preuve tient à ce que la MÊME question, posée depuis A,
    retourne bien la note."""
    _noter(base, CTX_A, NOTE_A)

    contexte_a = connaissance.rechercher(base, CTX_A, NOTE_A)
    assert contexte_a.passages, "la question de contrôle ne retrouve même pas la note chez son auteur"
    assert contexte_a.passages[0].contenu == NOTE_A

    contexte_b = connaissance.rechercher(base, CTX_B, NOTE_A)
    assert contexte_b.passages == (), "fuite de la mémoire du potager A vers le potager B"
    assert contexte_b.issue == connaissance.ISSUE_VIDE


def test_us141_ca9_deux_potagers_notent_la_meme_chose_sans_se_voir(base, sans_appel_modele):
    """CA9 — le cas le plus piégeux : deux jardins, la même parcelle « nord »,
    le même symptôme. Chacun ne doit voir que sa propre note."""
    _noter(base, CTX_A, "la parcelle nord est détrempée, les tomates jaunissent")
    _noter(base, CTX_B, "la parcelle nord est détrempée, les tomates jaunissent")

    for ctx, potager_id in ((CTX_A, 1), (CTX_B, 2)):
        contexte = connaissance.rechercher(base, ctx, "parcelle nord détrempée tomates jaunissent")
        assert contexte.passages
        references = {p.reference for p in contexte.passages}
        assert all(f"potager-{potager_id}/" in r for r in references), (
            f"le potager {potager_id} voit la note d'un autre jardin : {references}"
        )


def test_us141_ca9_une_note_ne_devient_jamais_une_reponse_partagee(base):
    """CA9 — corollaire côté cache : une réponse dérivée d'une note n'est jamais
    mémorisée en savoir partagé (`potager_id = NULL`), où tout le monde la
    lirait. Le contrôle est posé sur la PROVENANCE, en amont — un contrôle
    textuel ne rattraperait la fuite qu'au hasard des mots."""
    _noter(base, CTX_A, NOTE_A)

    contexte = connaissance.rechercher(base, CTX_A, NOTE_A)
    assert contexte.passages and not contexte.contexte_partageable

    routeur._memoriser_reponse(
        CTX_A, NOTE_A,
        routeur.DecisionRoutage(nature=routeur.NATURE_QUESTION_SAVOIR,
                                origine=routeur.ORIGINE_REGLE, confiance=1.0),
        routeur.ETAGE_SAVOIR, None, "Ta planche du fond reste détrempée.", contexte,
    )
    assert base.query(QuestionCache).count() == 0


# ═════════════════════════════════════════════════════════════════════════════
# CA10 — un membre qui quitte le potager perd l'accès, sans traitement dédié
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca9_une_question_de_memoire_n_est_jamais_memorisee(base, monkeypatch):
    """CA9 — une question qui demande à relire une note n'a AUCUNE réponse
    générale, pas même quand la recherche ne trouve rien.

    Relevé en usage le 08/09/2026 : « je ne trouve aucune note enregistrée »
    avait été mémorisé en savoir PARTAGÉ (`potager_id = NULL`) et servi ensuite
    à tous les potagers, y compris à ceux qui avaient des notes. Le contrôle par
    passage privé ne pouvait pas l'attraper : il ne se déclenche que si un
    passage privé a été retenu, or le cas dangereux est l'inverse."""
    for module in (routeur, cq, rc):
        monkeypatch.setattr(module, "SessionLocal", lambda: base)

    routeur._memoriser_reponse(
        CTX_A, "quelle note précédente avais-je sur ce potager ?",
        routeur.DecisionRoutage(nature=routeur.NATURE_QUESTION_SAVOIR,
                                origine=routeur.ORIGINE_REGLE, confiance=1.0),
        routeur.ETAGE_RAISONNEMENT, None,
        "Je ne trouve aucune note enregistrée à ce sujet.", None,
    )

    assert base.query(QuestionCache).count() == 0


def test_us141_ca9_une_entree_de_cache_deja_ecrite_n_est_plus_servie(base, monkeypatch):
    """CA9 — refuser d'écrire ne suffit pas : les entrées mémorisées AVANT ce
    garde-fou resteraient servies quatre-vingt-dix jours durant, court-circuitant
    la recherche. Une question de mémoire ne consulte donc plus le cache du
    tout, ce qui les fait expirer d'elles-mêmes sans purge manuelle."""
    from app.services import cache_questions

    for module in (routeur, cq, rc):
        monkeypatch.setattr(module, "SessionLocal", lambda: base)

    question = "quelle note précédente avais-je sur ce potager ?"
    cache_questions.memoriser_figee(
        base, CTX_A, question, "Je ne trouve aucune note enregistrée.",
        source_etage=cache_questions.SOURCE_LLM,
    )
    base.commit()
    assert cache_questions.servir(CTX_A, question) is not None, "décor invalide"

    _noter(base, CTX_A, NOTE_A)
    recu: dict = {}

    def _capter(*args, **kwargs):
        recu["message"] = kwargs.get("message_utilisateur", "")
        return ReponseLLM(texte="Ta note du 12 mai indique…", modele="mock",
                          appel_type=passerelle.TYPE_QUESTION, tokens_in=1, tokens_out=1)

    monkeypatch.setattr("llm.passerelle.appeler_chat", _capter)

    reponse = routeur.repondre_avec_cascade(CTX_A, question)

    assert reponse.etage_resolveur != routeur.ETAGE_CACHE, (
        "l'entrée figée a court-circuité la recherche : la mémoire n'a jamais été consultée"
    )
    # La note a bien été retrouvée et transmise, au lieu de la non-réponse figée.
    assert NOTE_A in recu.get("message", "")


def test_us141_ca10_un_membre_parti_n_atteint_plus_la_memoire(base, sans_appel_modele):
    """CA10 — « le filtre de potager courant suffit, et l'US le vérifie plutôt
    que de le supposer ». Le jardinier 2 a quitté le potager 1 : son contexte
    courant ne le nomme plus, donc la mémoire du potager 1 lui est fermée — sans
    qu'aucune ligne de code n'ait été écrite pour ce cas."""
    _noter(base, CTX_A, NOTE_A)

    ctx_apres_depart = TenantContext(user_id=2, potager_id=2, role="owner")
    contexte = connaissance.rechercher(base, ctx_apres_depart, NOTE_A)

    assert contexte.passages == ()


def test_us141_ca10_sans_potager_courant_la_memoire_ne_se_lit_pas(base):
    """CA10 — pas de repli silencieux : sans tenant, une recherche n'est pas
    isolable, donc elle n'a pas lieu."""
    with pytest.raises(ValueError):
        connaissance.rechercher(base, TenantContext(user_id=2, potager_id=None), NOTE_A)


# ═════════════════════════════════════════════════════════════════════════════
# CA11 — cycle de vie : aucune mémoire orpheline
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca11_une_note_corrigee_restitue_le_texte_corrige(base, sans_appel_modele):
    """CA11 + Gherkin « Observation corrigée » — c'est le texte corrigé qui
    ressort, pas celui d'avant."""
    event = _noter(base, CTX_A, NOTE_A)

    svc_evenements.corriger_evenement(
        base, CTX_A, event.id,
        {"commentaire": "[Observation] En fait c'est le mildiou, pas l'excès d'eau."},
        " | [CORR 2025-05-13] commentaire",
    )

    fragment = base.query(KnowledgeChunk).one()
    assert "mildiou" in fragment.contenu
    assert "détrempée" not in fragment.contenu

    contexte = connaissance.rechercher(base, CTX_A, "mildiou")
    assert contexte.passages and "mildiou" in contexte.passages[0].contenu


def test_us141_ca11_une_note_supprimee_ne_laisse_aucune_memoire(base, sans_appel_modele):
    """CA11 — « aucune mémoire orpheline ne survit à la donnée dont elle dérive »."""
    event = _noter(base, CTX_A, NOTE_A)
    assert _fragments_memoire(base)

    assert svc_evenements.supprimer_evenement(base, CTX_A, event.id) is True

    assert _fragments_memoire(base) == []
    assert base.query(KnowledgeChunk).count() == 0
    assert connaissance.rechercher(base, CTX_A, NOTE_A).passages == ()


def test_us141_ca11_un_evenement_qui_cesse_d_etre_une_note_perd_sa_memoire(base, sans_appel_modele):
    """CA11 — cas moins visible qu'une suppression, tout aussi faux : l'action
    est corrigée, l'événement n'est plus une note, sa mémoire doit partir."""
    event = _noter(base, CTX_A, NOTE_A)
    assert _fragments_memoire(base)

    svc_evenements.corriger_evenement(base, CTX_A, event.id, {"action": "arrosage"},
                                      " | [CORR 2025-05-13] action")

    assert _fragments_memoire(base) == []


def test_us141_ca11_une_reponse_figee_derivee_d_une_note_tombe_avec_elle(base, sans_appel_modele):
    """CA11 — la correction fait tomber les réponses mémorisées qui en
    dérivaient. Sans cela, le texte d'avant la correction serait servi des mois
    durant — le défaut réglé par US-098 / CA11 pour les fiches du dépôt."""
    from app.services import cache_questions

    event = _noter(base, CTX_A, NOTE_A)
    reference = base.query(KnowledgeChunk).one().reference
    cache_questions.memoriser_figee(
        base, CTX_A, "planche du fond", "Réponse dérivée de la note.",
        source_etage=cache_questions.SOURCE_RAG, fragment_id=reference,
    )
    base.commit()
    assert base.query(QuestionCache).count() == 1

    svc_evenements.corriger_evenement(
        base, CTX_A, event.id,
        {"commentaire": "[Observation] Finalement la planche a séché."},
        " | [CORR] texte",
    )

    assert base.query(QuestionCache).count() == 0


def test_us141_ca11_un_renommage_de_parcelle_reindexe_les_notes(base, sans_appel_modele):
    """CA11 — le nom de la parcelle est DANS le titre indexé. Un renommage le
    périme des deux côtés : la note devient introuvable sous le nom employé
    désormais, et s'affiche sous un nom qui n'existe plus."""
    _noter(base, CTX_A, NOTE_A)

    rename_parcelle(base, "nord", "carré du fond", potager_id=1)

    fragment = base.query(KnowledgeChunk).one()
    assert "carré du fond" in fragment.titre_document
    assert connaissance.rechercher(base, CTX_A, "qu'avais-je noté sur le carré du fond").passages


# ═════════════════════════════════════════════════════════════════════════════
# CA12 — la purge d'un potager emporte sa mémoire
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca12_la_purge_du_potager_emporte_sa_memoire(base, sans_appel_modele):
    """CA12 — « au même titre que ses événements, purge comprise » (US-084)."""
    _noter(base, CTX_A, NOTE_A)
    _fiche_generale(base, "agro/limaces.md", "Limaces", "Les limaces sortent la nuit.")
    assert _fragments_memoire(base, potager_id=1)

    rapport = svc_potagers.purger_potager(base, 1)

    assert rapport["purge"] is True
    assert rapport["volumes"]["knowledge_chunks"] >= 1
    assert _fragments_memoire(base) == []
    # Le savoir global n'appartient à personne : il ne part pas avec un potager.
    assert base.query(KnowledgeDocument).filter(
        KnowledgeDocument.famille == connaissance.FAMILLE_AGRONOMIE
    ).count() == 1


# ═════════════════════════════════════════════════════════════════════════════
# CA13 — un potager archivé garde sa mémoire, en lecture seule
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_ca13_un_potager_archive_conserve_sa_memoire_consultable(base, sans_appel_modele):
    """CA13 — « l'archivage met le potager en pause, il n'efface pas son
    histoire ». La lecture reste ouverte, l'écriture non."""
    _noter(base, CTX_A, NOTE_A)
    base.get(Potager, 1).etat = ETAT_ARCHIVE
    base.commit()

    contexte = connaissance.rechercher(base, CTX_A, "planche du fond détrempée")
    assert contexte.passages, "la mémoire d'un potager archivé doit rester consultable"
    assert NOTE_A in connaissance.restituer(contexte)


def test_us141_ca13_un_potager_archive_n_accepte_plus_de_nouvelle_note(base):
    """CA13 — lecture seule : la pause vaut pour l'écriture, y compris celle qui
    alimenterait la mémoire."""
    from app.services.permissions import PotagerArchiveError

    base.get(Potager, 1).etat = ETAT_ARCHIVE
    base.commit()

    with pytest.raises(PotagerArchiveError):
        _noter(base, CTX_A, "une note de trop")


# ═════════════════════════════════════════════════════════════════════════════
# Aiguillage — sans lui, tout le reste est inatteignable depuis Telegram
# -----------------------------------------------------------------------------
# Ces tests manquaient à la première livraison, et leur absence cachait un trou :
# la question phare de l'US portait `sur la parcelle`, un marqueur de DONNÉE, et
# partait à l'étage SQL — qui n'a aucune famille capable de rendre un texte
# libre. Toute la mémoire était correctement indexée, correctement isolée, et
# parfaitement injoignable. Un test de service ne pouvait pas le voir : il
# appelait `rechercher()` directement, en court-circuitant le routeur.
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("question", [
    "qu'avais-je noté sur la parcelle nord l'an dernier ?",
    # Dictée : le point d'interrogation n'existe pas à la voix, et « noter » est
    # une variante du geste `observation` (US-173 / CA3). Sans antériorité sur
    # la règle de geste, cette question s'ENREGISTRERAIT dans le journal.
    "qu'avais-je noté sur la parcelle nord l'an dernier",
    "que disait ma note sur la parcelle nord ?",
    "mes notes sur les limaces",
    "j'avais remarqué quoi sur les courgettes",
    # Formulation RÉELLE, relevée en usage le 08/09/2026 : le verbe de rappel et
    # le nom de l'écrit y sont séparés par un adjectif, et aucune locution figée
    # ne l'attrapait. Le modèle la classait QUESTION_DATA à 0,94, l'étage SQL
    # n'avait rien à en faire, et la réponse partait en raisonnement — trois
    # appels modèle pour ne pas trouver une note pourtant indexée.
    "quelle note précédente avais-je sur ce potager ?",
    "quelles notes avais-je prises ?",
    "quelle note avais-je laissée sur la parcelle nord ?",
    "montre-moi mes notes précédentes",
    "quelles sont mes dernières observations ?",
    "les notes que j'avais prises en juillet",
    # Passé composé, relevé en usage le 08/09/2026 : « j'ai noté » et non
    # « j'avais noté ». Aucun mot ne le distingue d'une saisie — seule
    # l'ouverture interrogative le fait (voir le test d'ambiguïté ci-dessous).
    "qu'est ce que j'ai noté ?",
    "qu'est ce que j'ai noté",
    "qu'est-ce que j'ai écrit sur les tomates ?",
])
def test_us141_aiguillage_une_question_de_memoire_atteint_l_etage_du_savoir(question):
    """CA5 — la mémoire n'est consultée que sur la branche QUESTION_SAVOIR
    (`repondre_avec_cascade`). Une question de mémoire classée autrement n'a
    aucun moyen d'atteindre l'index, quelle que soit la qualité de celui-ci."""
    assert routeur._regle_par_mots_cles(question) == routeur.NATURE_QUESTION_SAVOIR


@pytest.mark.parametrize("question,attendu", [
    # Un comptage reste un comptage : le catalogue chiffré répond en SQL, à
    # coût nul et exactement. Le capter ici dégraderait une réponse juste.
    ("combien de tomates ai-je récolté cette saison ?", "QUESTION_DATA"),
    ("où en sont mes semis ?", "QUESTION_DATA"),
    ("combien de plants dans la parcelle nord ?", "QUESTION_DATA"),
    ("quelle quantité de mes tomates ai-je récoltée ?", "QUESTION_DATA"),
    ("quelle est ma dernière récolte ?", "QUESTION_DATA"),
    # Une saisie reste une saisie.
    ("mise en godet 20 tomates", "ACTION"),
    ("j'ai observé une attaque de mildiou sur les tomates", "ACTION"),
    # Le fonctionnement de l'application reste du fonctionnement.
    ("comment noter une observation ?", "QUESTION_SAVOIR"),
    ("pourquoi mes tomates ont le cul noir ?", "QUESTION_SAVOIR"),
])
def test_us141_aiguillage_les_autres_natures_sont_intactes(question, attendu):
    """CA5, revers — le motif exige un nom d'écrit ET une marque de rappel.
    L'une sans l'autre ne suffit pas : sinon il volerait des questions que
    d'autres étages servent mieux, et plus exactement."""
    assert routeur._regle_par_mots_cles(question) == attendu


@pytest.mark.parametrize("saisie", [
    # LE cas ambigu : les mêmes mots, dans le même ordre, pour un geste.
    "j'ai noté que le sol est sec",
    "j'ai noté un début de mildiou sur les tomates",
    # Formulation réelle d'une note dictée le 08/09/2026.
    "je constate des tâches jaunes sur mes feuilles de tomate",
])
def test_us141_aiguillage_une_saisie_au_passe_compose_reste_une_saisie(saisie):
    """CA5 — « j'ai noté que le sol est sec » ENREGISTRE une note ; « qu'est-ce
    que j'ai noté ? » en RELIT une. Les mots sont les mêmes, seule l'ouverture
    interrogative les sépare — le même discriminant qu'US-173 / CA3, et pour la
    même raison : à la dictée vocale, le point d'interrogation n'existe pas.

    Sans cette garde, verser « j'ai noté » dans les marques de rappel aurait
    fait basculer toute saisie commençant ainsi vers une question, et le geste
    du jardinier se serait perdu."""
    assert routeur._est_rappel_de_note(saisie) is False
    assert routeur._regle_par_mots_cles(saisie) != routeur.NATURE_QUESTION_SAVOIR


def test_us141_aiguillage_un_comptage_de_notes_reste_un_comptage():
    """CA5, revers — « combien d'observations ai-je faites ? » porte le nom de
    l'écrit mais aucune marque de rappel : ce n'est pas une relecture, c'est un
    dénombrement. Il doit continuer de descendre vers le catalogue chiffré."""
    assert routeur._regle_par_mots_cles("combien d'observations ai-je faites ?") is None
    assert routeur._est_rappel_de_note("combien d'observations ai-je faites ?") is False


def test_us141_le_prompt_interdit_de_citer_ses_propres_etiquettes():
    """Relevé en usage le 08/09/2026 : faute de cette consigne, le modèle
    répondait « aucune "MÉMOIRE DU POTAGER" ne m'a été fournie » — il servait au
    jardinier le vocabulaire interne du prompt, et lui exposait un rouage qui ne
    le concerne pas."""
    prompt = routeur._PROMPT_FIXE_RAISONNEMENT
    assert "ne les cite JAMAIS dans ta réponse" in prompt
    assert "t'a été fourni" in prompt


def test_us141_aiguillage_une_question_de_memoire_ne_cherche_que_dans_la_memoire(base, sans_appel_modele):
    """CA5 — le REGISTRE de la recherche est fixé par la question, pas deviné
    sur le texte, et il ne se relâche jamais.

    Relevé en production le 08/09/2026 : « qu'ai-je noté sur les tomates ? »
    rendait trois fiches d'agronomie sur la tomate et pas une seule note. Le
    corpus général est bien plus vaste que la mémoire d'un potager, et bien plus
    riche du vocabulaire même de la question — il remporte le classement à tous
    les coups. Aucun réglage de score ne répare cela : il faut retirer la
    concurrence, pas espérer la gagner."""
    _noter(base, CTX_A, "les feuilles de tomate ont des taches jaunes")
    _fiche_generale(base, "agro/tomate-problemes.md", "Problèmes de la tomate",
                    "Des taches sur les feuilles de tomate évoquent le mildiou. "
                    "La tomate se soigne mal une fois la tomate atteinte.")

    question = "qu'est ce que j'ai noté sur les tomates ?"
    assert routeur._est_rappel_de_note(question), "décor invalide"

    contexte = connaissance.rechercher(
        base, CTX_A, question, famille=connaissance.FAMILLE_MEMOIRE_POTAGER)

    assert contexte.passages, "la mémoire ne rend rien"
    assert all(p.prive for p in contexte.passages), (
        "une fiche générale s'est glissée dans une question de mémoire : "
        f"{[p.titre_document for p in contexte.passages]}"
    )


def test_us141_ca6_une_question_qui_n_est_pas_un_rappel_garde_les_deux_registres(base, sans_appel_modele):
    """CA6 — la restriction ne vaut QUE pour le rappel d'une note. « Que faire
    contre les limaces ? » n'est pas une demande de relecture : elle a le droit
    de croiser la mémoire et le savoir général, et de les distinguer."""
    question = "limaces sur les jeunes plants"
    assert routeur._est_rappel_de_note(question) is False

    _noter(base, CTX_A, "les limaces ont dévoré mes jeunes plants cette nuit")
    _fiche_generale(base, "agro/limaces.md", "Limaces",
                    "Les limaces sortent la nuit par temps humide.")

    contexte = connaissance.rechercher(base, CTX_A, question)
    assert any(p.prive for p in contexte.passages)
    assert any(not p.prive for p in contexte.passages)


def test_us141_bout_en_bout_la_note_est_servie_a_cout_nul(base, monkeypatch):
    """CA2 → CA7 — le parcours réel du jardinier, de la question à la réponse.

    Aucun modèle n'est appelé : la classification passe par une règle, et la
    restitution recopie la note. Le test échoue si un jeton est consommé."""
    _noter(base, CTX_A, NOTE_A)
    for module in (routeur, cq, rc):
        monkeypatch.setattr(module, "SessionLocal", lambda: base)
    monkeypatch.setattr("llm.passerelle.appeler_chat", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("la mémoire doit se servir sans appel modèle (CA7)")
    ))

    reponse = routeur.repondre_avec_cascade(
        CTX_A, "qu'avais-je noté sur la parcelle nord l'an dernier ?")

    assert reponse.etage_resolveur == routeur.ETAGE_SAVOIR
    assert "12 mai 2025" in reponse.texte
    assert "parcelle nord" in reponse.texte
    assert NOTE_A in reponse.texte


def test_us141_bout_en_bout_aucune_fuite_par_la_cascade(base, monkeypatch):
    """CA9 — le parcours complet depuis le potager B, sur la question qui
    correspond exactement à la note du potager A. La cascade ne doit rien en
    laisser passer, ni par l'index, ni par le cache de réponses."""
    _noter(base, CTX_A, NOTE_A)
    for module in (routeur, cq, rc):
        monkeypatch.setattr(module, "SessionLocal", lambda: base)
    monkeypatch.setattr(
        "llm.passerelle.appeler_chat",
        lambda *a, **k: ReponseLLM(texte="Je n'ai rien à ce sujet.", modele="mock",
                                   appel_type=passerelle.TYPE_QUESTION,
                                   tokens_in=1, tokens_out=1),
    )

    reponse = routeur.repondre_avec_cascade(CTX_B, "que disait ma note sur la parcelle nord ?")

    assert NOTE_A not in reponse.texte
    assert "détrempée" not in reponse.texte
    assert reponse.etage_resolveur != routeur.ETAGE_SAVOIR


# ═════════════════════════════════════════════════════════════════════════════
# Scénarios Gherkin de l'US
# ═════════════════════════════════════════════════════════════════════════════
def test_us141_gherkin_retrouver_une_note_ancienne(base, sans_appel_modele):
    """Given une observation saisie l'an dernier sur la parcelle nord
    When le jardinier demande « qu'avais-je noté sur la parcelle nord ? »
    Then la note lui est restituée avec sa date et sa parcelle
    And le texte restitué est fidèle à ce qu'il avait écrit."""
    _noter(base, CTX_A, NOTE_A, date="2025-05-12")

    contexte = connaissance.rechercher(base, CTX_A, "qu'avais-je noté sur la parcelle nord ?")
    texte = connaissance.restituer(contexte)

    assert contexte.passages and contexte.passages[0].prive
    assert "12 mai 2025" in texte and "parcelle nord" in texte
    assert NOTE_A in texte


def test_us141_gherkin_aucune_fuite_entre_potagers(base, sans_appel_modele):
    """Given une note privée du potager A
    When un membre du potager B pose une question qui correspond exactement
    Then aucun résultat issu du potager A ne lui est retourné."""
    _noter(base, CTX_A, NOTE_A)
    assert connaissance.rechercher(base, CTX_B, NOTE_A).passages == ()


def test_us141_gherkin_memoire_et_savoir_general_distingues(base, sans_appel_modele):
    """Given une note du jardinier sur des limaces et une fiche générale
    When il pose une question sur les limaces
    Then la réponse distingue ce qu'il a noté de ce qui est vrai en général."""
    _noter(base, CTX_A, "les limaces ont dévoré mes jeunes plants cette nuit")
    _fiche_generale(base, "agro/limaces.md", "Limaces",
                    "Les limaces sortent la nuit par temps humide et attaquent les jeunes plants.")

    texte = connaissance.restituer(
        connaissance.rechercher(base, CTX_A, "limaces jeunes plants")
    )

    assert connaissance.REGISTRE_MEMOIRE in texte
    assert connaissance.REGISTRE_GENERAL in texte
    assert texte.index(connaissance.REGISTRE_MEMOIRE) != texte.index(connaissance.REGISTRE_GENERAL)
