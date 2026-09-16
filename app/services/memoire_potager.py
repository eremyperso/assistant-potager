"""
app/services/memoire_potager.py — La mémoire du potager [US-141]
================================================================================
Rendre consultable ce que le jardinier a lui-même écrit. Les observations et
notes libres (US-038, US-039) dorment aujourd'hui dans `evenements` : lisibles
par filtre et par date, introuvables par le sens de ce qu'elles disent. Ce
module les verse dans le socle d'US-098, famille `memoire_potager`.

Quatre arbitrages de l'US commandent tout ce fichier :

- **On indexe les notes, pas les événements structurés.** Un semis, une récolte,
  un arrosage se répondent en SQL (US-096), exactement et à coût nul. Les verser
  dans une recherche documentaire donnerait des réponses approximatives sur des
  données parfaitement structurées. `est_memorisable()` est donc restrictif par
  construction : `type_action == "observation"`, et rien d'autre.

- **Extrait fidèle, jamais résumé.** `contenu` est le texte du jardinier,
  recopié. Aucun appel modèle n'existe dans ce module — il n'importe même pas
  `llm.passerelle`. Un résumé ferait perdre à la note sa valeur de preuve et
  coûterait des jetons pour dégrader l'information (CA5, CA7).

- **Pas de mémoire déduite.** Rien ici ne fabrique de note à partir
  d'événements. La mémoire est ce que le jardinier a écrit, rien d'autre.

- **[CA1, CA8] Un fragment de cette famille porte TOUJOURS un `potager_id`.**
  C'est `connaissance.enregistrer_document` qui le refuse — pas ce module — de
  sorte qu'aucun chemin d'écriture, présent ou futur, ne puisse produire une
  note globale. Côté lecture, `connaissance._requete_base` rend une note de
  cette famille structurellement inatteignable depuis la clause de savoir
  partagé. L'isolation n'est pas ici un critère parmi d'autres : c'est la raison
  d'être de l'US, et une note privée qui fuirait vers un autre jardin serait une
  atteinte à la confiance bien plus grave qu'une réponse agronomique
  approximative.

Identité stable, donc reprise rejouable [CA3]
---------------------------------------------
La référence d'un document est dérivée de l'événement
(`memoire/potager-3/evenement-812`) : deux passages de la reprise retrouvent le
même document au lieu d'en créer un second, et l'empreinte fait que le second
n'écrit rien. C'est exactement le mécanisme d'idempotence de `US-098 / CA10`,
réemployé plutôt que réinventé.

Ce que ce module n'est pas
--------------------------
Il n'interroge jamais `knowledge_chunks` : toute lecture passe par
`connaissance.rechercher`, qui est le seul endroit du dépôt où le filtre
d'isolation est posé (US-098 / CA5, vérifié statiquement par
`tests/test_us098_socle_connaissance.py`).
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.services import connaissance
from app.services import rotation as svc_rotation
from database.db import tenant_scope
from database.models import Evenement, KnowledgeDocument, Parcelle, Potager

log = logging.getLogger("potager")


# ─────────────────────────────────────────────────────────────────────────────
# Périmètre [CA1 + arbitrage « on indexe les notes, pas les événements »]
# ─────────────────────────────────────────────────────────────────────────────
TYPE_ACTION_NOTE = "observation"

# Marqueur du bulletin météo quotidien (bot.job_meteo_quotidienne), réemployé
# depuis `rotation` plutôt que redéclaré : deux constantes identiques
# divergeraient au premier changement de libellé, et la divergence ne se verrait
# qu'au moment où la mémoire se remplirait de relevés de température.
BULLETIN_AUTO_METEO = svc_rotation.BULLETIN_AUTO_METEO

# `source` d'un document de mémoire — ce que le jardinier lit sous une réponse
# servie (« _Source : …_ »). Volontairement à la deuxième personne : la phrase
# doit dire d'où vient le texte sans qu'on ait à lui expliquer ce qu'est une
# famille de fragments.
SOURCE_MEMOIRE = "ton carnet du potager"

# [CA5] Une note est ce que le jardinier a écrit : elle est vraie par
# construction, donc `verifie`. C'est ce qui la rend servable telle quelle, à
# coût nul — un `indicatif` la ferait systématiquement redescendre à l'étage de
# raisonnement, qui la reformulerait, ce que l'US interdit explicitement.
NIVEAU_MEMOIRE = connaissance.NIVEAU_VERIFIE

# [Note technique US-141] « Une note très longue est découpée comme n'importe
# quel document (US-098 / CA12) ; une note courte reste un fragment unique. »
# Seuil en caractères, sur le même ordre de grandeur qu'une section de fiche.
TAILLE_MAX_FRAGMENT = 900

# Les traces d'auditabilité accolées à `texte_original` par les corrections
# (`| [CORR 2026-05-12] …`) et les déplacements (`| [DÉPL …] …`) sont de la
# métadonnée d'application, pas la parole du jardinier : elles ne rentrent pas
# dans la mémoire.
_TRACE_AUDIT = re.compile(r"\s*\|\s*\[(?:CORR|D[ÉE]PL)[^\]]*\][^|]*", re.IGNORECASE)

# `creer_evenement_observation` préfixe le constat par la catégorie choisie au
# menu (« [Observation] », « [Maladie / ravageur] »). C'est un classement fait
# par l'application, pas une phrase écrite par le jardinier : il part au TITRE,
# où il aide à retrouver la note, et non dans le texte restitué.
_CATEGORIE = re.compile(r"^\[([^\]]{1,40})\]\s*")

_MOIS = (
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
)

# Le REGISTRE DU RAPPEL — les mots avec lesquels on redemande une note, et qui
# ne sont par construction jamais dans la note elle-même. « Qu'avais-je noté
# sur la parcelle nord l'an dernier ? » porte cinq termes utiles, dont trois
# seulement figurent dans la note et son titre : la question tombait sous le
# seuil de confiance et descendait à l'étage de raisonnement, qui reformulait —
# donc payait des jetons pour dégrader une citation exacte.
#
# C'est exactement le rôle de la ligne « On parle aussi de : » des fiches du
# dépôt (US-098), et le même véhicule est réemployé : `termes_indexation` pèse
# au poids du TITRE et n'entre JAMAIS dans `contenu`. Aucun de ces mots ne peut
# donc être affiché au jardinier comme s'il l'avait écrit.
#
# Génériques à dessein : ils ne distinguent pas les notes ENTRE ELLES — ce sont
# la date, la parcelle et les mots du texte qui s'en chargent — ils font que la
# mémoire soit reconnue comme le bon registre quand on la sollicite.
TERMES_RAPPEL = (
    "note noté noter écrit écrire remarque remarqué constat constaté observé "
    "carnet souvenir dernier dernière an année saison passée précédente avais"
)


def est_memorisable(event: Evenement) -> bool:
    """[CA1] Vrai si cet événement relève de la mémoire du potager.

    Restrictif à dessein : seule une note (`type_action == "observation"`)
    portant réellement du texte entre dans la recherche documentaire. Un
    événement structuré, même commenté, reste du ressort de `US-096` — l'y
    verser rendrait approximatif ce qui est exact.

    **Les bulletins météo quotidiens sont exclus.** Le job météo enregistre son
    relevé comme une `observation` marquée `[AUTO-METEO]` : techniquement une
    note, mais que personne n'a écrite. Sur un potager d'une saison, ils sont
    plusieurs fois plus nombreux que les vraies notes (~96 événements sur 321
    au 25/08/2026) et noieraient la mémoire sous des relevés de température —
    d'autant qu'ils portent le vocabulaire du jardinier (« arrosage »,
    « surveiller les jeunes plants ») sans rien devoir à son observation.
    `rotation` et `rapport_couverture` écartent déjà ce marqueur pour la même
    raison ; c'est le même invariant, appliqué au même endroit du raisonnement.
    """
    if event is None or event.id is None or event.potager_id is None:
        return False
    if (event.type_action or "").strip().lower() != TYPE_ACTION_NOTE:
        return False
    if (event.texte_original or "").strip() == BULLETIN_AUTO_METEO:
        return False
    return bool(texte_note(event))


def texte_note(event: Evenement) -> str:
    """Le texte du jardinier, débarrassé de ce que l'application y a ajouté.

    Ni reformulé ni tronqué : c'est ce texte-là que `restituer()` recopiera
    entre guillemets, et la valeur de preuve d'une note tient à ce qu'elle
    ressort telle qu'elle est entrée.
    """
    brut = (event.commentaire or "").strip()
    if not brut:
        brut = _TRACE_AUDIT.sub("", event.texte_original or "").strip()
    return _CATEGORIE.sub("", brut).strip()


def categorie_note(event: Evenement) -> Optional[str]:
    """La catégorie choisie au menu de saisie (US-038), si elle est là."""
    correspondance = _CATEGORIE.match((event.commentaire or "").strip())
    return correspondance.group(1).strip() if correspondance else None


# ─────────────────────────────────────────────────────────────────────────────
# Identité et libellés [CA3, CA4, CA5]
# ─────────────────────────────────────────────────────────────────────────────
def reference_document(event: Evenement) -> str:
    """[CA3, CA4] Identité STABLE du document, et lien vers l'événement d'origine.

    Elle porte le potager autant que l'événement : c'est ce qui rend une
    référence lisible dans un journal (« de quel jardin vient cette note ? »)
    sans avoir à la rapprocher d'une table.
    """
    return f"memoire/potager-{event.potager_id}/evenement-{event.id}"


def _reference_fragment(reference_doc: str, ordre: int) -> str:
    return f"{reference_doc}#{ordre:02d}"


def date_lisible(valeur: Optional[datetime]) -> str:
    """« 12 mai 2025 » — en toutes lettres, parce que c'est ce mot-là que le
    jardinier emploie dans sa question, et que la recherche est lexicale.
    « 12/05/2025 » n'aurait produit aucun lexème utile."""
    if valeur is None:
        return "date inconnue"
    return f"{valeur.day} {_MOIS[valeur.month - 1]} {valeur.year}"


def titre_note(db: Session, event: Evenement) -> str:
    """[CA4, CA5] Ce qui identifie la note : sa date, sa parcelle, sa culture.

    Ce titre est porté par CHAQUE fragment (`titre_document`, US-098 / CA12) et
    indexé au poids du titre : c'est lui qui fait qu'« qu'avais-je noté sur la
    parcelle nord ? » retrouve la note, et c'est lui que la restitution affiche
    au-dessus du texte cité. Les deux besoins sont servis par la même chaîne, ce
    qui interdit qu'ils divergent.
    """
    parties = [f"Note du {date_lisible(event.date)}"]
    parcelle = _nom_parcelle(db, event)
    if parcelle:
        parties.append(f"parcelle {parcelle}")
    if event.culture:
        parties.append(str(event.culture))
    categorie = categorie_note(event)
    if categorie:
        parties.append(categorie)
    return " — ".join(parties)


def _nom_parcelle(db: Session, event: Evenement) -> Optional[str]:
    """Nom courant de la parcelle, relu en base plutôt que mémorisé ailleurs."""
    if not event.parcelle_id:
        return None
    parcelle = db.get(Parcelle, event.parcelle_id)
    return parcelle.nom if parcelle is not None else None


def decouper(texte: str, taille_max: int = TAILLE_MAX_FRAGMENT) -> list[str]:
    """[Note technique] Découpe une note longue, laisse une note courte entière.

    La coupe cherche une fin de paragraphe, puis une fin de phrase, avant de se
    résoudre à couper sur un espace : une note tronquée en plein milieu d'une
    phrase serait citée de travers, et une citation de travers est exactement ce
    que l'arbitrage « extrait fidèle » veut éviter.
    """
    texte = (texte or "").strip()
    if not texte:
        return []
    if len(texte) <= taille_max:
        return [texte]

    morceaux: list[str] = []
    reste = texte
    while len(reste) > taille_max:
        fenetre = reste[:taille_max]
        coupe = fenetre.rfind("\n\n")
        if coupe < taille_max // 3:
            coupe = max(fenetre.rfind(". "), fenetre.rfind("! "), fenetre.rfind("? "))
            coupe = coupe + 1 if coupe >= taille_max // 3 else -1
        if coupe < 0:
            coupe = fenetre.rfind(" ")
        if coupe <= 0:
            coupe = taille_max
        morceaux.append(reste[:coupe].strip())
        reste = reste[coupe:].strip()
    if reste:
        morceaux.append(reste)
    return [m for m in morceaux if m]


def _empreinte(titre: str, morceaux: Iterable[str]) -> str:
    """[CA3] Ce qui fait dire « cette note n'a pas changé ».

    Le titre en fait partie : déplacer une note vers une autre parcelle ne
    touche pas son texte, mais change ce qui est indexé et ce qui est affiché.
    Une empreinte sur le seul contenu laisserait vivre l'ancien titre.
    """
    graine = "\n".join([titre, *morceaux])
    return hashlib.sha256(graine.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# [CA2, CA11] Écriture — un seul point d'entrée, appelé par la couche services
# ─────────────────────────────────────────────────────────────────────────────
def synchroniser_evenement(db: Session, event: Evenement) -> bool:
    """[CA2, CA11] Met l'index en accord avec l'événement, quel qu'ait été le
    changement. Retourne vrai si quelque chose a été écrit.

    Un seul point d'entrée pour les trois cas, plutôt que trois fonctions que
    les appelants devraient choisir correctement :

    - une note vient d'être écrite → elle est indexée ;
    - une note a été corrigée → ses fragments sont remplacés, donc c'est le
      texte corrigé qui ressortira (CA11, scénario Gherkin « Observation
      corrigée ») ;
    - un événement a cessé d'être une note (correction de son action, ou
      commentaire vidé) → son document part. « Aucune mémoire orpheline ne
      survit à la donnée dont elle dérive » vaut aussi pour ce cas-là, moins
      visible qu'une suppression mais tout aussi faux.

    Ne commit pas : l'indexation part dans la transaction de l'écriture qui la
    motive, comme l'invalidation de cache d'US-095. Un enregistrement annulé
    n'indexe donc rien.
    """
    if event is None or event.id is None or event.potager_id is None:
        return False
    if not est_memorisable(event):
        return oublier_evenement(db, event.potager_id, event.id)

    reference = reference_document(event)
    titre = titre_note(db, event)
    morceaux = decouper(texte_note(event))
    document, inchange = connaissance.enregistrer_document(
        db,
        reference=reference,
        titre=titre,
        famille=connaissance.FAMILLE_MEMOIRE_POTAGER,
        source=SOURCE_MEMOIRE,
        niveau_confiance=NIVEAU_MEMOIRE,
        empreinte=_empreinte(titre, morceaux),
        potager_id=event.potager_id,
    )
    if inchange:
        return False

    # [CA4] Le lien vers l'événement d'origine, sa date, sa parcelle et sa
    # culture sont portés par le fragment lui-même : la référence pour
    # l'événement, `titre_document` pour la date et la parcelle, `culture_id`
    # pour la culture. Une réponse peut donc être rattachée à sa source sans
    # jointure et sans état conservé ailleurs.
    culture_id = _culture_id(db, event)
    type_fragment = connaissance.detecter_type(texte_note(event))
    fragments = [
        connaissance.FragmentAIngerer(
            reference=_reference_fragment(reference, ordre),
            ordre=ordre,
            intitule=None,
            contenu=morceau,
            culture_id=culture_id,
            type=type_fragment,
            termes_indexation=TERMES_RAPPEL,
        )
        for ordre, morceau in enumerate(morceaux)
    ]
    ecrits, anciennes = connaissance.remplacer_fragments(db, document, fragments)
    _invalider(db, anciennes)
    log.info(
        "🧠 MÉMOIRE        │ indexée │ potager=%s │ evenement=%s │ %d fragment(s) │ %s",
        event.potager_id, event.id, ecrits, titre,
    )
    return True


def oublier_evenement(db: Session, potager_id: int, evenement_id: int) -> bool:
    """[CA11] Retire de l'index la note d'un événement supprimé — ou d'un
    événement qui n'en est plus une. Retourne vrai si un document est parti.

    Appelée AVANT la suppression de l'événement : après, la référence serait
    toujours reconstructible, mais l'ordre inverse laisserait une fenêtre où la
    ligne n'existe plus et son souvenir si.
    """
    reference = f"memoire/potager-{potager_id}/evenement-{evenement_id}"
    supprimes, references = connaissance.supprimer_document(db, reference)
    if not references:
        return False
    _invalider(db, references)
    log.info(
        "🧠 MÉMOIRE        │ oubliée │ potager=%s │ evenement=%s │ %d fragment(s)",
        potager_id, evenement_id, supprimes,
    )
    return True


def _culture_id(db: Session, event: Evenement) -> Optional[int]:
    """La culture de la note, en RÉFÉRENCE et jamais en libellé (US-098 / CA2).

    Réemploie la résolution de `connaissance`, qui interroge `culture_config` :
    une culture renommée depuis le bot continue donc de retrouver ses notes.
    """
    if not event.culture:
        return None
    from app.services.context import TenantContext

    return connaissance.resoudre_culture(
        db, TenantContext(user_id=None, potager_id=event.potager_id), str(event.culture)
    )


def _invalider(db: Session, references: Iterable[str]) -> None:
    """[US-095 / CA10] Une note qui change fait tomber les réponses qui en
    dérivaient. Sans cela, « qu'avais-je noté sur la parcelle nord ? » servirait
    des mois durant le texte d'avant la correction — exactement le défaut que
    l'US-098 / CA11 a réglé pour les fiches du dépôt."""
    from app.services import cache_questions

    for reference in references:
        try:
            # `commit=False` : l'appelant est au milieu d'une écriture
            # d'observation, c'est lui qui commit.
            cache_questions.invalider_par_fragment(db, reference, commit=False)
        except Exception as e:  # pragma: no cover — l'index prime sur son cache
            log.warning("⚠️ MÉMOIRE        │ invalidation impossible (%s)", type(e).__name__)


# ─────────────────────────────────────────────────────────────────────────────
# [CA3] Reprise initiale — rejouable, sans doublon
# ─────────────────────────────────────────────────────────────────────────────
def notes_a_indexer(db: Session, potager_id: Optional[int] = None) -> list[Evenement]:
    """Les événements qui relèvent de la mémoire, tous potagers ou un seul.

    Lecture d'administration : la reprise n'est pas un chemin jardinier, elle
    n'a pas de `TenantContext` et ne rend aucun texte — elle alimente un index
    dont la lecture, elle, reste filtrée.
    """
    requete = db.query(Evenement).filter(Evenement.type_action == TYPE_ACTION_NOTE)
    if potager_id is not None:
        requete = requete.filter(Evenement.potager_id == potager_id)
    return [event for event in requete.order_by(Evenement.id).all() if est_memorisable(event)]


def documents_memoire(db: Session, potager_id: Optional[int] = None) -> list[KnowledgeDocument]:
    """Les documents de mémoire déjà indexés — matière de l'élagage."""
    requete = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.famille == connaissance.FAMILLE_MEMOIRE_POTAGER
    )
    if potager_id is not None:
        requete = requete.filter(KnowledgeDocument.potager_id == potager_id)
    return requete.order_by(KnowledgeDocument.reference).all()


def reprise_initiale(
    db: Session,
    potager_id: Optional[int] = None,
    *,
    elaguer: bool = True,
    dry_run: bool = False,
) -> dict[str, int]:
    """[CA3] Indexe les notes déjà enregistrées. Rejouable, sans doublon.

    Le « sans doublon » ne tient pas à une précaution prise ici : il tient à ce
    que la référence du document soit dérivée de l'événement. Un second passage
    retrouve le même document et, à empreinte égale, n'écrit rien — c'est le
    mécanisme d'US-098 / CA10, pas une seconde implémentation.

    `elaguer` retire les documents de mémoire dont l'événement a disparu sans
    passer par `oublier_evenement` (base restaurée, suppression en SQL direct) :
    la reprise est aussi le filet qui rattrape ces cas-là.

    ⚠️ **Le scope RLS est posé POTAGER PAR POTAGER** (US-043, migration_v42).
    Sans lui, sous PostgreSQL, la première requête sur `knowledge_documents`
    lève « unrecognized configuration parameter app.potager_id » — le fail-fast
    voulu par US-043 / CA5. Et un scope unique ne suffirait pas non plus : la
    politique `WITH CHECK` n'autorise à écrire QUE les lignes du potager
    courant, donc traiter plusieurs potagers dans un seul scope échouerait dès
    le second. La reprise est par nature multi-tenant : elle doit donc changer
    de scope, et clore sa transaction entre chaque — `SET LOCAL` n'est émis
    qu'à l'ouverture d'une transaction (`database.db._arm_rls_potager_setting`).

    Les potagers sont énumérés depuis `potagers`, table volontairement HORS RLS :
    les lire depuis `evenements` exigerait un scope qu'on cherche justement à
    déterminer.
    """
    if potager_id is None:
        cibles = [pid for (pid,) in db.query(Potager.id).order_by(Potager.id).all()]
    else:
        cibles = [potager_id]

    total = {"notes": 0, "indexees": 0, "inchangees": 0, "elaguees": 0}
    for cible in cibles:
        # Clôt la transaction courante pour que la suivante s'ouvre DANS le
        # scope — seul instant où le GUC de session est armé.
        db.commit()
        with tenant_scope(cible):
            partiel = _reprise_potager(db, cible, elaguer=elaguer, dry_run=dry_run)
        for cle, valeur in partiel.items():
            total[cle] += valeur
    return total


def _reprise_potager(
    db: Session, potager_id: int, *, elaguer: bool, dry_run: bool,
) -> dict[str, int]:
    """La reprise d'UN potager, à l'intérieur de son scope RLS."""
    rapport = {"notes": 0, "indexees": 0, "inchangees": 0, "elaguees": 0}
    attendues: set[str] = set()

    for event in notes_a_indexer(db, potager_id):
        rapport["notes"] += 1
        attendues.add(reference_document(event))
        if dry_run:
            continue
        if synchroniser_evenement(db, event):
            rapport["indexees"] += 1
        else:
            rapport["inchangees"] += 1

    if elaguer:
        for document in documents_memoire(db, potager_id):
            if document.reference in attendues:
                continue
            rapport["elaguees"] += 1
            if not dry_run:
                _, references = connaissance.supprimer_document(db, document.reference)
                _invalider(db, references)

    if not dry_run:
        db.commit()
    log.info(
        "🧠 MÉMOIRE        │ reprise │ potager=%s │ notes=%d indexées=%d inchangées=%d élaguées=%d%s",
        potager_id,
        rapport["notes"], rapport["indexees"], rapport["inchangees"], rapport["elaguees"],
        " (à blanc)" if dry_run else "",
    )
    return rapport


def reindexer_parcelle(db: Session, potager_id: int, parcelle_id: int) -> int:
    """Réindexe les notes d'une parcelle — son nom vient de changer.

    Le nom de la parcelle est DANS le titre indexé (c'est ce qui fait retrouver
    « la parcelle nord »), donc un renommage le périme. Le rattraper coûte une
    poignée de fragments ; ne pas le rattraper afficherait au jardinier une
    parcelle qui n'existe plus sous ce nom, et rendrait sa note introuvable sous
    le nom qu'il emploie désormais.
    """
    notes = (
        db.query(Evenement)
        .filter(
            Evenement.type_action == TYPE_ACTION_NOTE,
            Evenement.potager_id == potager_id,
            Evenement.parcelle_id == parcelle_id,
        )
        .all()
    )
    return sum(1 for event in notes if synchroniser_evenement(db, event))
