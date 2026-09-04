"""
database/models.py — Modèles SQLAlchemy pour l'Assistant Potager
-----------------------------------------------------------------
[US-001] Ajout colonne type_organe_recolte sur Evenement
[US-001] Ajout modèle CultureConfig (table culture_config)
[US-040] Ajout socle multi-tenant (User, Potager, PotagerMembre) + potager_id
[US-044] Ajout credentials web (mot_de_passe_hash, email_verifie) sur User
[US-044] Ajout token de vérification d'e-mail (verification_token_*) sur User
[US-045] Ajout modèle LiaisonTelegram (codes de liaison chat_id ⇄ compte web)
[US-046] Ajout User.potager_actif_id (potager sélectionné par l'utilisateur)
[US-048] Ajout modèle Invitation (codes d'invitation à rejoindre un potager)
[US-092] Ajout modèle ConsoTokens (mesure de consommation LLM par potager)
[US-097] Ajout modèles RoutageLog et RoutageRetour (observabilité cascade + retour jardinier)
[US-095] Ajout modèle QuestionCache (table questions_cache — cache de réponses)
[US-166] Ajout modèle ReferentielSource (registre de sources) + rattachement
         source_id sur familles_botaniques et famille_source_id sur culture_config
[US-161] Ajout des attributs agronomiques de conduite sur culture_config
         (exposition, besoin_eau, profondeur_semis_cm, rusticite_min_c) et de
         leur source respective
[US-163] Ajout du modèle AssociationCulture (table association_culture) et
         de l'index composite evenements(parcelle_id, date) pour la rotation
[US-098] Ajout des modèles KnowledgeDocument et KnowledgeChunk (socle de
         connaissance interrogeable en plein texte) + colonnes score_savoir /
         issue_savoir sur routage_logs
"""
from sqlalchemy import Column, Integer, BigInteger, String, Text, Float, Date, DateTime, Boolean, ForeignKey, Index, UniqueConstraint
# [US-098] TSVECTOR est un type du dialecte PostgreSQL ; l'importer ne charge
# aucun pilote (psycopg2 n'est sollicité qu'à la création du moteur). Le
# `with_variant(Text(), "sqlite")` posé sur la colonne laisse les tests tourner
# en SQLite en mémoire, sans branchement dans le modèle.
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.db import Base


class User(Base):
    """[US-040] Utilisateur de la plateforme (compte web et/ou Telegram lié)."""
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True)
    email            = Column(String(255), unique=True, nullable=True)
    telegram_chat_id = Column(BigInteger, unique=True, nullable=True)
    nom              = Column(String(100), nullable=True)
    cree_le          = Column(DateTime, server_default=func.now())

    # [US-044] Credentials web — NULL pour un compte Telegram-only (US-045)
    mot_de_passe_hash = Column(String(255), nullable=True)
    email_verifie     = Column(Boolean, default=False, nullable=False)

    # [US-044] Token de vérification d'e-mail (CA9-CA12) — seul le hash est
    # stocké, jamais la valeur brute (envoyée uniquement dans l'e-mail Brevo).
    # Usage unique : verification_token_utilise_le suit le même pattern que
    # LiaisonTelegram.utilise_le (US-045).
    verification_token_hash      = Column(String(255), nullable=True)
    verification_token_expire_le = Column(DateTime, nullable=True)
    verification_token_utilise_le = Column(DateTime, nullable=True)

    # [US-057] Token de réinitialisation de mot de passe — même principe que
    # verification_token_* ci-dessus (hash seul stocké, usage unique, TTL 1h
    # géré côté service plutôt qu'en base).
    reset_mdp_token_hash      = Column(String(255), nullable=True)
    reset_mdp_token_expire_le = Column(DateTime, nullable=True)
    reset_mdp_token_utilise_le = Column(DateTime, nullable=True)

    # [US-090] Identité fédérée Google — claim `sub` de l'id_token OIDC, stable
    # et opaque (jamais l'e-mail, qui peut changer côté Google). UNIQUE : un
    # même compte Google ne peut être rattaché qu'à un seul utilisateur (CA14).
    # Volontairement PAS de colonne `auth_provider` mono-valuée (CA15) : un
    # compte peut cumuler mot de passe, Google et Telegram — les méthodes
    # actives se déduisent de mot_de_passe_hash / google_sub / telegram_chat_id,
    # et le fournisseur utilisé est une propriété de l'événement de connexion
    # (journalisé), pas de l'utilisateur.
    google_sub = Column(String(255), unique=True, nullable=True)

    # [US-046] Potager actuellement sélectionné — NULL tant qu'aucun choix n'a
    # encore été fait (sélection auto silencieuse si un seul potager, sinon
    # choix explicite via /potager ou le sélecteur PWA).
    potager_actif_id = Column(Integer, ForeignKey("potagers.id"), nullable=True)


class LiaisonTelegram(Base):
    """[US-045] Code à usage unique liant un telegram_chat_id à un compte web."""
    __tablename__ = "liaisons_telegram"

    id         = Column(Integer, primary_key=True, index=True)
    code       = Column(String(8), unique=True, nullable=False, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    cree_le    = Column(DateTime, server_default=func.now())
    expire_le  = Column(DateTime, nullable=False)
    utilise_le = Column(DateTime, nullable=True)


class Potager(Base):
    """[US-040] Un potager (jardin partagé) — le tenant de l'application."""
    __tablename__ = "potagers"

    id               = Column(Integer, primary_key=True, index=True)
    nom              = Column(String(100), nullable=False)
    ville            = Column(String(255), nullable=True)  # [US-074] libellé affichable, jamais géocodé côté serveur
    latitude         = Column(Float, nullable=True)
    longitude        = Column(Float, nullable=True)
    proprietaire_id  = Column(Integer, ForeignKey("users.id"), nullable=False)
    plan             = Column(String(20), default="free")
    cree_le          = Column(DateTime, server_default=func.now())
    # [US-080] Cycle de vie du LIEU physique — 'actif' | 'archive' | 'supprime'
    # (valeurs sans accent en base, libellés accentués côté affichage uniquement).
    # Axe indépendant de `plan` : un potager gratuit comme payant peut être archivé.
    etat             = Column(String(20), nullable=False, default="actif", server_default="actif")
    archive_le       = Column(DateTime, nullable=True)   # renseigné par US-083
    supprime_le      = Column(DateTime, nullable=True)   # soft-delete + délai de grâce, US-084


class PotagerMembre(Base):
    """[US-040] Appartenance d'un utilisateur à un potager, avec son rôle."""
    __tablename__ = "potager_membres"

    user_id    = Column(Integer, ForeignKey("users.id"), primary_key=True)
    potager_id = Column(Integer, ForeignKey("potagers.id"), primary_key=True)
    role       = Column(String(10), nullable=False)  # 'owner' | 'editor' | 'lecteur'


class Invitation(Base):
    """[US-048] Code à usage unique invitant un utilisateur à rejoindre un potager
    avec un rôle proposé — même principe que LiaisonTelegram (US-045), TTL plus
    long (jours, pas minutes) car destiné à être partagé hors ligne (e-mail, lien)."""
    __tablename__ = "invitations"

    id            = Column(Integer, primary_key=True, index=True)
    code          = Column(String(8), unique=True, nullable=False, index=True)
    potager_id    = Column(Integer, ForeignKey("potagers.id"), nullable=False)
    invite_par_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    email_invite  = Column(String(255), nullable=True)
    role_propose  = Column(String(10), nullable=False)  # 'editor' | 'lecteur'
    cree_le       = Column(DateTime, server_default=func.now())
    expire_le     = Column(DateTime, nullable=False)
    utilisee_le   = Column(DateTime, nullable=True)


class Evenement(Base):
    __tablename__ = "evenements"

    id             = Column(Integer, primary_key=True, index=True)
    # ⚠️ Plus de server_default : on passe toujours la date explicitement
    # pour respecter "hier", "lundi dernier", etc.
    date           = Column(DateTime, nullable=True, index=True)

    # Action principale
    type_action    = Column(String, index=True)

    # Culture
    culture        = Column(String, index=True)
    variete        = Column(String)

    # Quantité
    quantite       = Column(Float)
    unite          = Column(String)

    # Localisation
    # [migration_v12] colonne parcelle (texte dénormalisé) supprimée — parcelle_id est l'unique référence
    parcelle_id    = Column(Integer, ForeignKey("parcelles.id"), nullable=True, index=True)
    rang           = Column(Integer)   # [migration_v3] INTEGER (pas String)

    # Détails
    duree          = Column(Integer)
    traitement     = Column(String)
    commentaire    = Column(String)

    # Texte original dicté (+ traces [CORR ...])
    texte_original = Column(String)

    # [US-001] Classification agronomique héritée depuis culture_config
    # Valeurs : "végétatif" | "reproducteur" | null
    type_organe_recolte = Column(String, nullable=True)

    # [US_Enregistrer_mise_en_godet] Pépinière : nb graines semées → nb plants obtenus
    nb_graines_semees   = Column(Integer, nullable=True)
    nb_plants_godets    = Column(Integer, nullable=True)

    # [migration_v12] Traçabilité pépinière : événement source (semis → godet → plantation)
    origine_graines_id  = Column(Integer, ForeignKey("evenements.id", ondelete="SET NULL"), nullable=True)

    # [US-029] Chaînage plantation → godet(s) source (IDs séparés par ";" si multi-lots)
    source_evenement_ids = Column(String, nullable=True)

    # [US-094 / CA10 / migration_v34] Chemin qui a produit cet évènement :
    # "deterministe" (grammaire de llm/parseur_deterministe.py, zéro jeton) |
    # "llm" (parsing par le modèle) | NULL (antérieur à l'US).
    # Instrumentation seule : aucune condition métier, aucun gabarit et aucun
    # message utilisateur ne lit cette colonne.
    origine_parsing = Column(String, nullable=True)

    # [US-169 / CA1 / migration_v35] Origine de `date` : "explicite" (dictée en
    # clair) | "relative_resolue" (ex. "hier") | "presumee" (aucun ancrage,
    # convention "aujourd'hui") | "modele_incertain" (date rendue par le
    # modèle, origine non connaissable) | NULL (antérieur à l'US, ou chemin
    # d'écriture qui ne sait pas conclure — jamais deviné, voir CA7).
    # Instrumentation seule, même invariant que `origine_parsing` ci-dessus.
    date_source = Column(String, nullable=True)

    # [US-040] Rattachement tenant, backfillé = potager #1.
    # [US-042 / migration_v17] NOT NULL en production — laissé nullable=True ici
    # (comme Evenement.parcelle_id, cf. CLAUDE.md) pour que les fixtures de tests
    # SQLite existantes n'aient pas à fournir potager_id partout ; le scoping
    # applicatif réel se fait par ctx.potager_id dans app/services/, pas par
    # cette contrainte ORM. La contrainte NOT NULL réelle vit dans le schéma SQL.
    # default=1 (= app.services.context.DEFAULT_POTAGER_ID) : toute création sans
    # potager_id explicite (tests existants, scripts) tombe sur le potager #1,
    # cohérent avec default_context() tant que le multi-potager réel n'existe pas.
    potager_id = Column(Integer, ForeignKey("potagers.id"), nullable=True, default=1)

    # Relation vers la parcelle — permet d'accéder à e.parcelle_rel.nom
    parcelle_rel = relationship("Parcelle", foreign_keys=[parcelle_id])

    __table_args__ = (
        Index("idx_evenements_potager_date", "potager_id", "date"),
        # [US-163/CA12] Historique d'une parcelle par campagne — requête posée
        # par app.services.rotation.evaluer_rotation.
        Index("idx_evenements_parcelle_date", "parcelle_id", "date"),
    )

    @property
    def parcelle(self) -> str | None:
        """Nom de la parcelle (compatibilité avec l'ancien champ texte dénormalisé)."""
        return self.parcelle_rel.nom if self.parcelle_rel else None


class CultureConfig(Base):
    """
    [US-001] Configuration des cultures avec leur type d'organe récolté.

    Permet de distinguer :
    - "végétatif"    : récolte destructive (salade, carotte, radis...)
                       → 1 récolte = 1 plant consommé/détruit
    - "reproducteur" : récolte continue (tomate, courgette, poivron...)
                       → la plante reste en vie, produit plusieurs fois
    """
    __tablename__ = "culture_config"

    id                      = Column(Integer, primary_key=True, index=True)
    nom                     = Column(String, unique=True, index=True, nullable=False)
    type_organe_recolte     = Column(String, nullable=False)   # "végétatif" | "reproducteur"
    description_agronomique = Column(String)
    espacement              = Column(String, nullable=True)    # ex: "30 × 40 cm"
    surface_m2              = Column(Float,  nullable=True)    # surface au sol par plant en m²

    # [US-040] NULL = fiche référentiel globale partagée entre potagers ;
    # non NULL = fiche personnalisée à un potager (le backfill ne force pas
    # cette colonne, contrairement aux tables purement métier)
    potager_id               = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True)

    # [US-067 / CA1] Famille botanique — référence vers la table dédiée, jamais
    # un libellé texte ici : le délai de retour (FamilleBotanique) est un
    # attribut de la FAMILLE, pas de la culture (voir FamilleBotanique
    # ci-dessous). NULL = famille non renseignée, affichée "Autres" (CA3).
    famille_id                = Column(Integer, ForeignKey("familles_botaniques.id"), nullable=True, index=True)
    famille_rel               = relationship("FamilleBotanique", foreign_keys=[famille_id])

    # [US-166 / CA1-CA3] Origine du rattachement `famille_id` — jamais l'origine
    # de la fiche culture_config elle-même, qui naît de la dictée du jardinier.
    # Renseignée que la famille vienne d'un import (`wikidata`) ou d'une
    # correction au bot (`saisie_manuelle`) : il n'existe aucune donnée sans
    # origine. NULL = rattachement antérieur à l'US, origine non connaissable —
    # jamais devinée après coup.
    famille_source_id         = Column(Integer, ForeignKey("referentiel_source.id"), nullable=True, index=True)
    famille_source_rel        = relationship("ReferentielSource", foreign_keys=[famille_source_id])

    # ── [US-161 / CA1, CA2] Attributs agronomiques de conduite ────────────────
    # Rien que des attributs : de la donnée qui s'affiche, se filtre et se trie
    # sans jamais passer par un modèle de langage. Tous nullables — un attribut
    # non renseigné se lit « non renseigné » (CA4), jamais deviné ni moyenné.
    #
    # ⚠️ Aucun attribut de calendrier ici (CA8) : ni fenêtre de semis, ni durée
    # de germination, ni date — ils appartiennent au référentiel calendrier
    # d'US-068. Ni aucune relation (CA9) : associations, rotations et
    # bioagresseurs sont des arêtes (US-162, US-163), pas des colonnes.

    # [CA2] Vocabulaire fermé — app.services.attributs_culture.EXPOSITIONS.
    # Stocké en VARCHAR plutôt qu'en ENUM Postgres : ajouter une valeur au
    # vocabulaire resterait un ALTER TYPE, alors que la validation vit déjà en
    # un seul endroit applicatif que l'import comme le bot traversent.
    exposition                = Column(String, nullable=True)
    # [CA2] Vocabulaire fermé — app.services.attributs_culture.BESOINS_EAU.
    besoin_eau                = Column(String, nullable=True)
    # [CA10] Chiffres : jamais produits par un modèle de langage, exclusivement
    # importés (US-166) ou saisis par le jardinier. L'unité est dans le nom,
    # comme `surface_m2`, pour qu'aucune lecture n'ait à la supposer.
    profondeur_semis_cm       = Column(Float, nullable=True)
    rusticite_min_c           = Column(Float, nullable=True)

    # [CA3] Une source PAR attribut, et non une source de ligne : c'est ce qui
    # permet à une profondeur corrigée à la main de survivre à un rejeu d'import
    # (CA6) sans figer pour autant l'exposition, que l'import doit continuer de
    # rafraîchir. Aucun attribut orphelin : une valeur renseignée porte toujours
    # son origine. NULL = attribut non renseigné.
    exposition_source_id      = Column(Integer, ForeignKey("referentiel_source.id"), nullable=True)
    besoin_eau_source_id      = Column(Integer, ForeignKey("referentiel_source.id"), nullable=True)
    profondeur_semis_source_id = Column(Integer, ForeignKey("referentiel_source.id"), nullable=True)
    rusticite_min_source_id   = Column(Integer, ForeignKey("referentiel_source.id"), nullable=True)


class FamilleBotanique(Base):
    """
    [US-067] Table de référence des familles botaniques.

    Table à part plutôt que colonne texte sur `culture_config` (CA1) : le délai
    de retour recommandé est un attribut de la FAMILLE, pas de la culture — en
    colonne sur `culture_config`, il se dupliquerait sur chaque culture de la
    famille et deviendrait incohérent à la première correction (le jardinier
    corrige "Solanacées : 4 ans" sur la tomate, la pomme de terre reste à 3).

    Aucune colonne `potager_id` : une famille botanique est un fait, identique
    quel que soit le potager (CA7) — jamais une préférence de jardinier.
    """
    __tablename__ = "familles_botaniques"

    id                   = Column(Integer, primary_key=True, index=True)
    nom                  = Column(String, unique=True, nullable=False)
    # [CA6] Casse/accents indifférents à la résolution — même stratégie que
    # Parcelle.nom_normalise (strip + lower + unidecode).
    nom_normalise        = Column(String, unique=True, nullable=False, index=True)
    # [CA12/CA13] Délai de retour recommandé, en années. Nullable : une famille
    # sans délai renseigné n'empêche aucun affichage, elle rend seulement
    # l'avertissement de rotation indisponible pour ses cultures (US-163).
    delai_retour_annees  = Column(Integer, nullable=True)

    # [US-166] Nom scientifique de la famille ('Solanaceae') — c'est l'apport
    # propre de Wikidata (CC0) au référentiel structuré, et le champ prévu par
    # `docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md` §4.1. Nullable :
    # une famille saisie au bot n'a aucune raison d'en porter un.
    nom_scientifique     = Column(String, nullable=True)

    # [US-166 / CA1-CA3] Origine de la ligne — import (`wikidata`), saisie du
    # jardinier (`saisie_manuelle`) ou rédaction interne. C'est cette colonne
    # que l'import relit pour ne jamais écraser une correction humaine (CA5) et
    # que la requête de retrait de source suit pour identifier tout ce qui
    # dérive d'une source (CA4).
    source_id            = Column(Integer, ForeignKey("referentiel_source.id"), nullable=True, index=True)
    source_rel           = relationship("ReferentielSource", foreign_keys=[source_id])


class ReferentielSource(Base):
    """
    [US-166] Registre des sources du référentiel — d'où vient chaque donnée.

    Une ligne par origine, importée ou non (CA3) : `wikidata` et `ephy_anses`
    sont des sources d'import ; `saisie_manuelle` (le jardinier corrige au bot)
    et `redaction_interne` (contenu écrit par le projet) n'importent rien mais
    sont des origines à part entière — il n'existe aucune donnée sans origine.

    L'attribution est portée par la ligne, jamais par un README : c'est une
    obligation par enregistrement (CA1), et c'est ce qui rend le retrait d'une
    source répondable six mois plus tard, quand plus personne ne se souvient de
    ce qui venait d'où (CA4, voir `app.services.referentiel_sources.donnees_derivees`).
    """
    __tablename__ = "referentiel_source"

    id                  = Column(Integer, primary_key=True, index=True)
    # [CA1] Code stable, c'est lui que citent les scripts d'import et les
    # requêtes de traçabilité — jamais l'id, qui dépend de l'ordre d'insertion.
    code                = Column(String, unique=True, nullable=False, index=True)
    libelle             = Column(String, nullable=False)
    # [CA6] Valeur du socle uniquement — voir LICENCES_SOCLE dans
    # app/services/referentiel_sources.py, qui refuse tout le reste.
    licence             = Column(String, nullable=False)
    # [CA1] Mention à afficher. NOT NULL : une source sans attribution connue
    # n'entre pas au registre, donc rien ne peut en dériver.
    attribution         = Column(String, nullable=False)
    url                 = Column(String, nullable=True)
    # [CA1] Date du dernier import réussi. NULL pour les origines non importées
    # (CA3) comme pour une source déclarée mais jamais encore rejouée.
    date_dernier_import = Column(DateTime, nullable=True)
    # [CA2] Exclut d'un éventuel export les sources contaminantes. `true` pour
    # toutes les sources retenues aujourd'hui (arbitrage option A,
    # docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §2.1) : la colonne existe
    # pour rendre l'option B réversiblement atteignable, pas parce qu'un cas
    # `false` existe déjà.
    partageable         = Column(Boolean, nullable=False, default=True)
    # [CA3] False = origine non importée (saisie, rédaction interne). C'est
    # aussi ce qui distingue les licences acceptables : `proprietaire` n'est
    # légitime que pour une origine interne, jamais pour un contenu importé.
    importee            = Column(Boolean, nullable=False, default=True)


class AssociationCulture(Base):
    """
    [US-163] Association orientée entre deux cultures et/ou familles botaniques.

    Une arête typée (CA1) plutôt qu'un paragraphe dans une fiche — c'est
    précisément ce que US-140/CA7bis interdit d'écrire ailleurs
    (docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §1.2). `nature` porte la
    relation, `motif` le texte court qui la rend compréhensible, `niveau_preuve`
    distingue une relation établie d'une relation seulement traditionnelle
    (CA2) — la formulation différenciée à la restitution (CA3) est portée par
    `app.services.associations.formuler_nature`, pas par une colonne.

    [CA4] Chaque côté référence SOIT une culture (`culture_x_id`) SOIT une
    famille botanique (`famille_x_id`), jamais les deux ni aucun des deux —
    contrôlé par `app.services.associations` à l'écriture, doublé d'un CHECK
    Postgres (`migrations/migration_v41.sql`) non reproduit ici : SQLite (tests)
    n'a pas besoin de cette défense en profondeur, la validation Python suffit.

    [CA5] Le stockage reste ORIENTÉ (une ligne par couple, comme `Evenement`) :
    c'est la LECTURE qui est symétrique — `app.services.associations.lire_associations`
    interroge les deux côtés, jamais la forme de stockage.

    [CA10] `source_id` NOT NULL : aucune arête anonyme. Les associations sont
    saisies, pas importées — l'origine est presque toujours `saisie_manuelle`.
    """
    __tablename__ = "association_culture"

    id             = Column(Integer, primary_key=True, index=True)
    culture_a_id   = Column(Integer, ForeignKey("culture_config.id"), nullable=True, index=True)
    famille_a_id   = Column(Integer, ForeignKey("familles_botaniques.id"), nullable=True, index=True)
    culture_b_id   = Column(Integer, ForeignKey("culture_config.id"), nullable=True, index=True)
    famille_b_id   = Column(Integer, ForeignKey("familles_botaniques.id"), nullable=True, index=True)
    # [CA1] 'favorable' | 'defavorable' | 'neutre'. Vocabulaire fermé validé par
    # app.services.associations, pas par un CHECK — même arbitrage que
    # culture_config.exposition (US-161) : une décision produit révisable.
    nature         = Column(String, nullable=False)
    # [CA1] Motif court en clair — ce qui rend l'avertissement compréhensible
    # plutôt qu'autoritaire ("répulsif contre la mouche de la carotte").
    motif          = Column(String, nullable=False)
    # [CA2] 'etabli' | 'traditionnel'.
    niveau_preuve  = Column(String, nullable=False)
    # [CA10] Traçabilité obligatoire, jamais NULL.
    source_id      = Column(Integer, ForeignKey("referentiel_source.id"), nullable=False, index=True)

    culture_a_rel  = relationship("CultureConfig", foreign_keys=[culture_a_id])
    famille_a_rel  = relationship("FamilleBotanique", foreign_keys=[famille_a_id])
    culture_b_rel  = relationship("CultureConfig", foreign_keys=[culture_b_id])
    famille_b_rel  = relationship("FamilleBotanique", foreign_keys=[famille_b_id])
    source_rel     = relationship("ReferentielSource", foreign_keys=[source_id])


class Parcelle(Base):
    """
    [US_Plan_occupation_parcelles / CA8]
    Représente une parcelle physique du potager.

    - nom_normalise : forme canonique (strip + lower + unidecode + sans tirets/espaces),
                      unique PAR POTAGER (migration_v23) — deux potagers différents
                      peuvent chacun avoir une parcelle "planche-tomate"
    - ordre         : position pour l'affichage trié du plan
    - actif         : permet de désactiver sans supprimer
    - est_pepiniere : [migration_v13] une parcelle pépinière/serre n'est jamais comptée
                      comme "pleine terre" pour un semis, même avec un parcelle_id renseigné
                      (voir utils.stock._cond_semis_pleine_terre)
    - type_sol      : [migration_v28 / US-058] texte libre informatif (ex. "Limoneux"),
                      non exploité par le calcul de stock/plan
    """
    __tablename__ = "parcelles"

    id            = Column(Integer, primary_key=True, index=True)
    nom           = Column(String, nullable=False)
    nom_normalise = Column(String, nullable=False, index=True)
    exposition    = Column(String, nullable=True)
    superficie_m2 = Column(Float, nullable=True)
    ordre         = Column(Integer, default=0)
    actif         = Column(Boolean, default=True, nullable=False)
    est_pepiniere = Column(Boolean, default=False, nullable=False)
    type_sol      = Column(String, nullable=True)

    # [US-040] Rattachement tenant, backfillé = potager #1.
    # [US-042 / migration_v17] NOT NULL en production — voir commentaire équivalent
    # sur Evenement.potager_id (nullable=True + default=1 ORM volontairement conservés).
    potager_id    = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True, default=1)

    __table_args__ = (
        # [migration_v23] Unicité par potager, pas globale — remplace l'ancienne
        # contrainte UNIQUE(nom_normalise) seule (parcelles_nom_normalise_key).
        UniqueConstraint("potager_id", "nom_normalise", name="uq_parcelles_potager_nom_normalise"),
    )


class ConsoTokens(Base):
    """
    [US-092 / CA5] Consommation LLM mesurée, une ligne par appel passé par la
    passerelle (`llm/passerelle.py`) — succès comme échec.

    Cette table **mesure**, elle ne plafonne pas : les budgets par potager, le
    blocage au dépassement et l'incitation à l'abonnement relèvent de l'US de
    quotas, qui consommera ces lignes. Nom et colonnes repris du cadrage initial
    d'US-123 pour ne pas créer une table concurrente.

    - date         : jour d'imputation (agrégation quotidienne par potager)
    - appel_type   : classification | parsing | question | synthese | transcription
    - modele       : modèle réellement appelé (les quotas Groq sont par modèle)
    - tokens_cache : [CA6] jetons servis depuis le cache de prompt du fournisseur,
                     distingués des jetons facturés plein tarif — 0 tant que le
                     fournisseur ne les expose pas
    - latence_ms   : durée de l'appel, échecs et nouvelle tentative comprises
    - issue        : ok | quota | delai | erreur
    - user_id      : [CA2] auteur de l'appel, en complément du potager — ajout au
                     cadrage initial, nullable (appels de fond sans utilisateur)
    """
    __tablename__ = "conso_tokens"

    id           = Column(Integer, primary_key=True, index=True)
    potager_id   = Column(Integer, ForeignKey("potagers.id"), nullable=False, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=True)
    date         = Column(Date, nullable=False, index=True)
    appel_type   = Column(String(32), nullable=False, index=True)
    modele       = Column(String(120), nullable=False)
    tokens_in    = Column(Integer, nullable=False, default=0)
    tokens_out   = Column(Integer, nullable=False, default=0)
    tokens_cache = Column(Integer, nullable=False, default=0)
    latence_ms   = Column(Integer, nullable=False, default=0)
    issue        = Column(String(16), nullable=False, default="ok")
    cree_le      = Column(DateTime, server_default=func.now())

    __table_args__ = (
        # Agrégation type « consommation du potager X sur le mois » — c'est la
        # requête que l'US de quotas exécutera à chaque appel.
        Index("idx_conso_tokens_potager_date", "potager_id", "date"),
    )


class RoutageLog(Base):
    """
    [US-097 / CA1] Une ligne par question passée par le routeur
    (`llm/routeur.py::repondre_avec_cascade`) — succès comme remontée de
    cascade.

    - question_normalisee    : [CA2] question NORMALISÉE, jamais le message brut
    - nature                 : ACTION | QUESTION_DATA | QUESTION_SAVOIR | QUESTION_HYBRIDE
    - origine_classification : regle | cache | modele — origine de la DÉCISION
                                de classification (llm.routeur.DecisionRoutage.origine)
    - etage_resolveur        : donnee | savoir | raisonnement — étage ayant
                                produit la réponse FINALE (distinct de la
                                classification : peut différer en cas de
                                remontée de cascade)
    - cascade_remontee       : vrai si l'étage data n'a pas su répondre et que
                                le raisonnement a pris le relais (US-093 CA7)
    - tokens_consommes       : [CA5] jetons consommés pour cette réponse,
                                routage (appel de classification) inclus
    """
    __tablename__ = "routage_logs"

    id                     = Column(Integer, primary_key=True, index=True)
    potager_id             = Column(Integer, ForeignKey("potagers.id"), nullable=False, index=True)
    cree_le                = Column(DateTime, server_default=func.now())
    question_normalisee    = Column(String, nullable=False)
    nature                 = Column(String(20), nullable=False)
    origine_classification = Column(String(10), nullable=False)
    etage_resolveur        = Column(String(20), nullable=False)
    cascade_remontee       = Column(Boolean, nullable=False, default=False)
    confiance              = Column(Float, nullable=True)
    latence_ms             = Column(Integer, nullable=False, default=0)
    tokens_consommes       = Column(Integer, nullable=False, default=0)

    # [US-098 / CA14] Score et issue de la recherche de savoir, quand la
    # question a traversé l'étage 2. Deux colonnes distinctes de `confiance`
    # ci-dessus, qui est la confiance de la CLASSIFICATION : les confondre
    # rendrait illisibles les deux mesures. NULL = étage du savoir non traversé.
    # C'est `issue_savoir = 'vide'` qui répond à « quelles questions ne trouvent
    # rien ? », donc à « que faut-il écrire ensuite ? ».
    score_savoir           = Column(Float, nullable=True)
    issue_savoir           = Column(String(16), nullable=True)

    __table_args__ = (
        Index("idx_routage_logs_potager_date", "potager_id", "cree_le"),
    )


class RoutageRetour(Base):
    """
    [US-097 / CA9-CA11] Avis 👍/👎 du jardinier sur une réponse de savoir ou de
    raisonnement — au plus un par ligne de `routage_logs` (contrainte UNIQUE,
    CA11 : jamais redemandé pour la même réponse).

    potager_id est dénormalisé depuis routage_logs : évite une jointure pour la
    purge potager (CA3) et pour le scoping tenant d'un futur endpoint web.
    """
    __tablename__ = "routage_retours"

    id             = Column(Integer, primary_key=True, index=True)
    routage_log_id = Column(Integer, ForeignKey("routage_logs.id"), nullable=False, unique=True)
    potager_id     = Column(Integer, ForeignKey("potagers.id"), nullable=False, index=True)
    avis           = Column(String(10), nullable=False)  # 'positif' | 'negatif'
    cree_le        = Column(DateTime, server_default=func.now())


class QuestionCache(Base):
    """
    [US-095 / CA1] Réponse mémorisée — étage 0bis de la cascade
    (`llm/routeur.py::repondre_avec_cascade`), servie par
    `app/services/cache_questions.py`.

    Deux natures de réponse, qu'il ne faut jamais confondre :

    - `type_reponse='template_sql'` : seuls le motif et l'**aiguillage** sont
      mémorisés (`template` = famille du catalogue + culture + parcelle, en
      JSON). Les valeurs sont recalculées à chaque service par l'étage des
      données (US-096) : la réponse est donc juste *par construction*,
      personnalisée à chaque appel, et coûte zéro jeton (CA3).
    - `type_reponse='figee'` : `reponse_figee` est le texte servi tel quel,
      réservé au savoir général. `potager_id` est alors NULL — l'entrée est
      partageable entre tous les potagers (CA1), ce qui est précisément la
      raison pour laquelle elle ne peut contenir aucune donnée de potager
      (CA8, contrôle à l'écriture dans le service).

    **Deux natures de réponse, donc deux espaces de clés** (CA2) :

    - `cle_aiguillage` (`famille|culture|parcelle`) est la clé des entrées
      `template_sql`. Elle est bornée par construction — quelques centaines de
      valeurs pour un potager — là où l'espace des formulations ne l'est pas.
      « quel est ma production de concombre », « ma production de concombre » et
      « production de concombre » sont trois phrases pour une seule question :
      une seule ligne. Corrigé le 29/08/2026 après constat en usage réel, où
      ces trois formulations avaient créé trois lignes et servi zéro réponse.
    - `motif_normalise` est la clé des entrées `figee` — pour du savoir général
      il n'existe aucun aiguillage, la phrase est tout ce qu'on a. Sur une
      entrée `template_sql`, la colonne reste renseignée mais ne sert qu'à
      l'**audit** : elle dit quelle formulation a créé l'entrée.

    - motif_normalise : question normalisée par `llm.routeur.normaliser_question`,
                        la MÊME fonction que le routeur, jamais une variante (CA2)
    - source_etage    : sql | rag | llm — étage ayant produit la réponse, pour audit
    - culture         : [CA4] culture dont dérive l'entrée, NULL si elle porte
                        sur l'ensemble du potager (stock global, rendement global)
    - natures         : [CA4] natures de donnée dont dérive l'entrée, encadrées
                        de « | » (ex. `|stock|recolte|journal|`) — support de
                        l'invalidation événementielle (CA5), voir
                        `utils/dependances_donnee.py`
    - fragment_id     : [CA10] fragment de connaissance dont une réponse figée
                        est issue ; NULL tant qu'US-098 n'existe pas
    - valide_jusqu_au : [CA11] écartée à la lecture au-delà, nettoyée au fil de
                        l'eau — aucun job planifié n'est ajouté pour cela
    """
    __tablename__ = "questions_cache"

    id              = Column(Integer, primary_key=True, index=True)
    # Nullable : NULL = savoir général partageable entre tous les potagers.
    potager_id      = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True)
    motif_normalise = Column(String(500), nullable=False)
    # [US-095 / CA2] Clé des entrées `template_sql` — NULL sur une entrée figée,
    # qui n'a pas d'aiguillage.
    cle_aiguillage  = Column(String(300), nullable=True)
    type_reponse    = Column(String(16), nullable=False)
    template        = Column(String, nullable=True)
    reponse_figee   = Column(String, nullable=True)
    source_etage    = Column(String(8), nullable=False)
    culture         = Column(String(120), nullable=True)
    natures         = Column(String(200), nullable=False, default="")
    # [US-098] Sans borne, comme `KnowledgeChunk.reference` dont c'est le report.
    # VARCHAR(120) (migration_v36) refusait 19 des 96 fragments du premier corpus
    # agronomique réel — une réponse dérivée de l'un d'eux échouait à la
    # mémorisation sur un DataError, donc repayait un appel modèle à chaque fois.
    fragment_id     = Column(String, nullable=True)
    valide_jusqu_au = Column(DateTime, nullable=True)
    cree_le         = Column(DateTime, server_default=func.now(), default=func.now())

    __table_args__ = (
        # Requête de service d'une réponse paramétrée : « ce potager a-t-il déjà
        # répondu à cette question, quelle qu'en soit la formulation ? »
        Index("idx_questions_cache_aiguillage", "cle_aiguillage", "potager_id"),
        # Requête de service d'une réponse figée : la phrase est la seule clé.
        Index("idx_questions_cache_motif", "motif_normalise", "potager_id"),
    )


# ═════════════════════════════════════════════════════════════════════════════
# [US-098] Socle de connaissance — le contenant, pas le contenu
# ═════════════════════════════════════════════════════════════════════════════
class KnowledgeDocument(Base):
    """
    [US-098 / CA1] Document de connaissance versionné dans le dépôt.

    Le contenu vit dans le dépôt, la base en est l'INDEX (arbitrage tranché de
    l'US) : ces lignes sont produites exclusivement par
    `tools/ingerer_connaissance.py` à partir de fichiers Markdown relus et
    corrigés comme du code. Rien ne s'édite en base.

    `potager_id` NULL = savoir global partagé entre tous les potagers ; non NULL
    = savoir privé d'un potager (US-141). Motif déjà éprouvé sur
    `culture_config` (CA3) — une seule fiche « tomate » sert tous les jardins.
    """
    __tablename__ = "knowledge_documents"

    id               = Column(Integer, primary_key=True, index=True)
    potager_id       = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True)

    # [CA10] Identité STABLE du document — chemin relatif du .md dans le dépôt.
    # C'est elle qui rend l'ingestion idempotente : sans identité stable, un
    # rejeu créerait un second document au lieu de retrouver le premier.
    reference        = Column(String, nullable=False, unique=True, index=True)

    titre            = Column(String, nullable=False)
    # agronomie | doc_app | memoire_potager — vocabulaire fermé validé par
    # app.services.connaissance.FAMILLES, pas par un CHECK en base : même
    # arbitrage que `culture_config.exposition` (migration_v39), un vocabulaire
    # fermé mais révisable sans ALTER TYPE.
    famille          = Column(String, nullable=False, index=True)
    source           = Column(String, nullable=False)
    # verifie | indicatif — app.services.connaissance.NIVEAUX_CONFIANCE.
    niveau_confiance = Column(String, nullable=False)

    # [CA10] SHA-256 du fichier source : « ce document a-t-il changé ? » sans
    # comparer le texte entier, et sans réécrire des fragments identiques.
    empreinte        = Column(String, nullable=False)

    cree_le          = Column(DateTime, server_default=func.now(), default=func.now())
    mis_a_jour_le    = Column(DateTime, server_default=func.now(), default=func.now(),
                              onupdate=func.now())

    fragments        = relationship(
        "KnowledgeChunk", back_populates="document",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class KnowledgeChunk(Base):
    """
    [US-098 / CA2] Fragment autonome d'un document — l'unité de la recherche.

    [CA12] Un fragment porte une idée répondable à lui seul, et conserve le
    titre de son document (`titre_document`) : un fragment qui n'a de sens
    qu'avec le précédent est un défaut de découpage, pas une fatalité du format.

    [CA2 amendé le 25/08/2026 — docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md
    §1.3] La culture est une RÉFÉRENCE (`culture_id`), jamais un libellé : un
    libellé ici serait l'erreur corrigée par `migration_v12` sur
    `evenements.parcelle`, et une culture renommée depuis le bot orphelinerait
    silencieusement ses fragments (CA2bis).

    ⚠️ `app/services/connaissance.py` est le SEUL point d'écriture de cette
    table : `recherche_fts` est maintenu à l'écriture, une insertion faite
    ailleurs laisserait le vecteur vide, donc le fragment introuvable.
    """
    __tablename__ = "knowledge_chunks"

    id             = Column(Integer, primary_key=True, index=True)
    document_id    = Column(Integer, ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
                            nullable=False, index=True)

    # [CA2, CA5] Dénormalisé depuis le document : le filtre d'isolation se pose
    # alors sur la table interrogée, sans jointure — une jointure oubliée est un
    # chemin de fuite, une colonne absente n'en est pas un.
    potager_id     = Column(Integer, ForeignKey("potagers.id"), nullable=True, index=True)

    # [CA11] Identité stable du fragment, reportée dans
    # `questions_cache.fragment_id` : c'est par elle qu'une réingestion invalide
    # les réponses figées qui en dérivaient (US-095 / CA10).
    reference      = Column(String, nullable=False, unique=True, index=True)

    ordre          = Column(Integer, nullable=False, default=0)
    # [CA12] Contexte du titre du document conservé sur CHAQUE fragment : c'est
    # ce qui rend « arroser deux fois par semaine » lisible sans le document.
    titre_document = Column(String, nullable=False)
    intitule       = Column(String, nullable=True)
    contenu        = Column(Text, nullable=False)

    culture_id     = Column(Integer, ForeignKey("culture_config.id"), nullable=True, index=True)
    culture_rel    = relationship("CultureConfig", foreign_keys=[culture_id])

    # maladie | semis | association | rotation… — vocabulaire ouvert : il sert à
    # restreindre une recherche (CA6), jamais à valider une saisie.
    type           = Column(String, nullable=True, index=True)
    saison         = Column(String, nullable=True)

    # [CA4] TSVECTOR sous PostgreSQL, texte indexable sous SQLite (tests) — voir
    # `app.services.connaissance` pour les deux chemins. Maintenu à l'ÉCRITURE,
    # jamais recalculé par requête (note technique de l'US), et jamais par un
    # trigger ni une colonne GENERATED : le projet tourne aussi sur SQLite.
    recherche_fts  = Column(TSVECTOR().with_variant(Text(), "sqlite"), nullable=True)

    # [CA2] Créée, nullable et INUTILISÉE — aucune lecture, aucune écriture nulle
    # part dans le code. Pas de pgvector à ce stade (arbitrage tranché) : la
    # colonne existe pour éviter de rouvrir cette table le jour où la recherche
    # sémantique sera décidée, décision suspendue à la mesure du CA13.
    embedding      = Column(Text, nullable=True)

    document       = relationship("KnowledgeDocument", back_populates="fragments")
