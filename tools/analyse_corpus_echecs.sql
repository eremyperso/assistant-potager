-- =============================================================
-- analyse_corpus_echecs.sql
-- Extraction du corpus d'échecs de parsing, en vue d'US-092
-- (cascade de classification d'intention du moteur de réponses V2).
--
-- ⚠️ LECTURE SEULE — aucun ALTER, aucun DELETE, aucun UPDATE.
--    Ce n'est PAS une migration : ne jamais renommer en migration_vX,
--    ne jamais déplacer dans migrations/.
--
-- Usage :
--   psql -w "$DATABASE_URL" -v potager=1 -f tools/analyse_corpus_echecs.sql
--   psql -w "$DATABASE_URL" -v potager=1 -f tools/analyse_corpus_echecs.sql --csv -o corpus_echecs.csv
--
-- ⚠️ Le filtre multi-tenant est EXPLICITE et obligatoire.
--    La RLS n'est PAS activée sur `evenements` (vérifié le 25/08/2026 :
--    pg_class.relrowsecurity = false) — rien ne cloisonne les potagers
--    automatiquement. Sans -v potager=<id>, les agrégats mélangent les
--    locataires en silence.
--    Pour un balayage volontairement global : -v potager=-1
--
-- Corrigé le 25/08/2026 (contrôle de vague 0, cf.
-- docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md §6.2) :
--   - `evenements.parcelle` n'existe plus (migration_v12) → parcelle_id + jointure
--   - filtre potager_id ajouté partout
--   - référentiel d'unités : la whitelist inventée est remplacée par une
--     mesure de distribution + détection de variantes non normalisées
--   - motif d'échec « type_action hors référentiel canonique » ajouté
--   - découpage correct des traces [CORR] multi-champs
--   - exclusion systématique des bulletins '[AUTO-METEO]'
-- =============================================================

\set ON_ERROR_STOP on
\pset pager off

-- Filtre tenant réutilisable : -1 = toutes les données.
\if :{?potager}
\else
  \set potager -1
  \echo '⚠️  Aucun -v potager=<id> fourni : balayage GLOBAL, tous potagers confondus.'
\endif


-- -------------------------------------------------------------
-- VOLUMÉTRIE — à lire en premier pour calibrer l'effort
--
-- 📊 Mesures de référence du 25/08/2026 :
--    dev  : 220 événements,   3 traces [CORR], 0 sans type_action
--    PROD : 321 événements,  35 traces [CORR], 2 sans type_action,
--           dont 96 bulletins [AUTO-METEO] — soit 225 saisies réelles
--           et un TAUX DE CORRECTION DE 15,6 %.
--    ⚠️ Contrairement à ce que laissait croire la base de dev, la
--       SOURCE 1 est bien une base exploitable. Ne pas la sous-estimer.
-- -------------------------------------------------------------
WITH perimetre AS (
    SELECT * FROM evenements
    WHERE (:potager = -1 OR potager_id = :potager)
)
SELECT 'total événements'          AS indicateur, count(*) AS valeur FROM perimetre
UNION ALL SELECT 'dont bulletins [AUTO-METEO]', count(*) FROM perimetre
    WHERE texte_original = '[AUTO-METEO]'
UNION ALL SELECT 'avec trace [CORR]',        count(*) FROM perimetre
    WHERE texte_original LIKE '%[CORR%'
UNION ALL SELECT 'sans type_action',         count(*) FROM perimetre
    WHERE type_action IS NULL
UNION ALL SELECT 'type_action hors référentiel', count(*) FROM perimetre
    WHERE type_action IS NOT NULL AND type_action NOT IN (
        'semis','plantation','repiquage','arrosage','desherbage','paillage',
        'amendement','fertilisation','traitement','taille','tuteurage','protection',
        'recolte','perte','observation','mise_en_godet','vendu','perte_godet')
UNION ALL SELECT 'texte interrogatif',       count(*) FROM perimetre
    WHERE texte_original <> '[AUTO-METEO]'
      AND texte_original ~* '(\?|\mpourquoi\M|\mcomment\M|\mcombien\M|c.est quoi|qu.est.ce|y a.t.il)'
UNION ALL SELECT 'texte_original NULL/vide', count(*) FROM perimetre
    WHERE texte_original IS NULL OR trim(texte_original) = '';


-- -------------------------------------------------------------
-- SOURCE 1 — Les corrections : corpus d'échecs annoté
-- Chaque ligne = une phrase que le bot a mal comprise, avec la
-- correction appliquée derrière.
--
-- Format réel de la trace (bot.py:5191) :
--   <phrase dictée> | [CORR AAAA-MM-JJ] culture: x → y, quantité: 2 → 3
-- Les libellés sont accentués et localisés (variété, quantité, durée).
-- -------------------------------------------------------------
SELECT
    id,
    type_action,
    culture,
    -- phrase dictée d'origine (avant le premier pipe)
    trim(split_part(texte_original, '|', 1))                        AS phrase_dictee,
    -- contenu intégral des corrections (tout ce qui suit le 1er [CORR ...])
    trim(substring(texte_original from '\[CORR[^\]]*\]\s*(.*)$'))   AS corrections,
    length(texte_original)                                          AS taille
FROM evenements
WHERE texte_original LIKE '%[CORR%'
  AND (:potager = -1 OR potager_id = :potager)
ORDER BY id DESC;


-- -------------------------------------------------------------
-- SOURCE 1-bis — Synthèse : quels champs se trompent le plus ?
-- Priorise les efforts de prompt engineering.
--
-- ⚠️ Une trace peut porter PLUSIEURS champs séparés par ', '.
--    D'où le découpage en deux temps (', ' puis ':') — un simple
--    split_part(..., ':', 1) ne compterait que le premier champ.
-- -------------------------------------------------------------
WITH traces AS (
    SELECT id,
           substring(texte_original from '\[CORR[^\]]*\]\s*(.*)$') AS corr
    FROM evenements
    WHERE texte_original LIKE '%[CORR%'
      AND (:potager = -1 OR potager_id = :potager)
),
champs AS (
    SELECT id,
           trim(split_part(trim(item), ':', 1)) AS champ_corrige
    FROM traces, unnest(string_to_array(corr, ', ')) AS item
    WHERE position(':' in item) > 0
)
SELECT champ_corrige, count(*) AS nb_corrections
FROM champs
GROUP BY 1
ORDER BY nb_corrections DESC;


-- -------------------------------------------------------------
-- SOURCE 2 — Enregistrements dégradés : échecs silencieux
-- ⚠️ EXPORTER AVANT le nettoyage prévu au backlog point 5.
--    Une fois supprimés, ce corpus est définitivement perdu.
--
-- ⚠️ `evenements.parcelle` (texte dénormalisé) a été SUPPRIMÉE par
--    migration_v12. La localisation passe par parcelle_id → parcelles.nom.
--
-- 🔶 Mesuré en dev : `type_action IS NULL` ne remonte RIEN, alors que
--    2 lignes portent 'binage', absent de ACTION_MAP comme de
--    ACTIONS_VALIDES. Le motif utile est « hors référentiel », pas « NULL ».
--    ⚠️ Les deux référentiels du code divergent (utils/actions.ACTION_MAP :
--    amendement, protection ; utils/validation.ACTIONS_VALIDES :
--    fertilisation, repiquage). L'union des deux est utilisée ici, faute
--    de mieux — à trancher avant d'en faire une règle.
-- -------------------------------------------------------------
WITH ref_actions AS (
    SELECT unnest(ARRAY[
        'semis','plantation','repiquage','arrosage','desherbage','paillage',
        'amendement','fertilisation','traitement','taille','tuteurage','protection',
        'recolte','perte','observation','mise_en_godet','vendu','perte_godet'
    ]) AS action
)
SELECT
    e.id,
    e.date,
    e.type_action,
    e.culture,
    e.quantite,
    e.unite,
    e.parcelle_id,
    p.nom AS parcelle_nom,
    e.texte_original,
    CASE
        WHEN e.type_action IS NULL                    THEN 'type_action absent'
        WHEN e.type_action NOT IN (SELECT action FROM ref_actions)
                                                      THEN 'type_action hors référentiel'
        WHEN e.culture IS NULL AND e.type_action IN
             ('recolte','semis','plantation')         THEN 'culture absente sur action qui l''exige'
        WHEN e.quantite IS NOT NULL AND e.quantite <= 0 THEN 'quantité nulle ou négative'
        WHEN e.date IS NULL                           THEN 'date absente'
        WHEN e.date > now() + interval '1 day'        THEN 'date future'
        WHEN e.date < date '2020-01-01'               THEN 'date aberrante (trop ancienne)'
        ELSE 'autre'
    END AS motif_echec
FROM evenements e
LEFT JOIN parcelles p ON p.id = e.parcelle_id
WHERE (:potager = -1 OR e.potager_id = :potager)
  -- les bulletins météo automatiques ne sont pas des saisies utilisateur
  AND (e.texte_original IS DISTINCT FROM '[AUTO-METEO]')
  AND (
        e.type_action IS NULL
     OR e.type_action NOT IN (SELECT action FROM ref_actions)
     OR (e.culture IS NULL AND e.type_action IN ('recolte','semis','plantation'))
     OR (e.quantite IS NOT NULL AND e.quantite <= 0)
     OR e.date IS NULL
     OR e.date > now() + interval '1 day'
     OR e.date < date '2020-01-01'
  )
ORDER BY motif_echec, e.id DESC;


-- -------------------------------------------------------------
-- SOURCE 3 — Questions avalées comme actions
-- Séquelles du bug « date des récoltes crée un enregistrement »,
-- antérieures au fix de priorité du mode ask.
-- Chaque ligne = un faux négatif de détection INTERROGER.
--
-- ⚠️ Corrigé le 25/08/2026 après la passe production, qui a montré
--    les deux défauts de la regex initiale :
--
--    (a) FAUX POSITIFS — `comment` matchait `commentaire`, présent dans
--        les traces [CORR]. Les 4 seules lignes remontées en prod étaient
--        du bruit pur. D'où les bornes de mot \m…\M.
--
--    (b) FAUX NÉGATIF — la seule vraie question avalée de la production
--        (« Y a t il des radis dans mon jardin », id 10) n'était PAS
--        détectée : ni point d'interrogation, ni marqueur de la liste.
--        Les tournures interrogatives orales sont donc ajoutées : à la
--        dictée vocale, le point d'interrogation n'existe tout simplement
--        pas. Ne jamais s'appuyer dessus.
-- -------------------------------------------------------------
SELECT
    id,
    date,
    type_action,
    culture,
    texte_original
FROM evenements
WHERE (:potager = -1 OR potager_id = :potager)
  AND texte_original IS DISTINCT FROM '[AUTO-METEO]'
  AND texte_original ~* '(\?'
                        -- interrogatifs, en mots entiers
                        '|\mpourquoi\M|\mcomment\M|\mcombien\M|\mquel\M|\mquelle\M|\mquels\M|\mquelles\M'
                        -- tournures orales, sans point d''interrogation
                        '|y a.t.il|y.a.t.il|c.est quoi|qu.est.ce|est.ce qu|dis.moi|montre.moi'
                        '|\mas.tu\M|\mpeux.tu\M|\msais.tu\M)'
ORDER BY id DESC;


-- -------------------------------------------------------------
-- SOURCE 4 — Marqueurs d'incertitude présents en base
--
-- ⚠️ Ce n'est PAS une vérification : `_signal_intent()` n'existe pas
--    encore dans le code. C'est un PRÉ-TEST de faisabilité de la règle
--    prévue par l'architecture cible V2 — « quelle serait sa fausse
--    positivité si on l'écrivait ainsi ? ».
--
-- Liste alignée sur docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md §3.3.
-- Toute modification ici doit être répercutée là-bas, et inversement.
--
-- Résultat attendu : proche de zéro sur des lignes de type ACTION.
-- Chaque ligne remontée est un faux positif potentiel, à examiner.
-- -------------------------------------------------------------
SELECT
    id,
    type_action,
    culture,
    texte_original
FROM evenements
WHERE (:potager = -1 OR potager_id = :potager)
  AND texte_original IS DISTINCT FROM '[AUTO-METEO]'
  AND texte_original ~* '(je pense|je crois|je suppose|para.t.il|d.apr.s|on m.a dit|jamais su|jamais .t. s.r|peut.[- ]?tre|s.rement|pass. tout seul)'
ORDER BY id DESC;


-- -------------------------------------------------------------
-- SOURCE 5 — Cultures aberrantes : hallucinations du LLM
-- Valeurs de culture apparues une ou deux fois = suspectes
-- (faute Whisper, hallucination Groq, ou nom de parcelle contaminé
--  en culture — cf. « parcelle planche haricot »).
--
-- 🔶 À croiser avec culture_config : une culture absente de la table
--    de configuration est un signal plus fort qu'une simple rareté.
-- -------------------------------------------------------------
SELECT
    e.culture,
    count(*)                                      AS occurrences,
    bool_or(cc.id IS NOT NULL)                    AS connue_de_culture_config,
    min(e.id)                                     AS premier_id,
    (array_agg(e.texte_original ORDER BY e.id))[1] AS exemple_texte
FROM evenements e
LEFT JOIN culture_config cc ON lower(cc.nom) = lower(e.culture)
WHERE e.culture IS NOT NULL
  AND (:potager = -1 OR e.potager_id = :potager)
  AND e.texte_original IS DISTINCT FROM '[AUTO-METEO]'
GROUP BY e.culture
HAVING count(*) <= 2
ORDER BY occurrences, e.culture;


-- -------------------------------------------------------------
-- SOURCE 6 — Unités : distribution réelle et variantes non normalisées
--
-- ⚠️ Il n'existe AUCUN référentiel d'unités canonique dans le code
--    (seul utils.validation.unite_semis_ancree_dans_texte cadre le cas
--    des semis). Toute whitelist écrite ici serait inventée : la version
--    précédente de ce script signalait 6 valeurs légitimes sur 11 comme
--    « hallucinations », et ratait la seule vraie anomalie.
--
-- On mesure donc la DISTRIBUTION, et on isole les variantes qui se
-- confondent une fois normalisées (dev : `m2` et `m²` coexistent).
-- Établir le référentiel canonique est un préalable, pas un sous-produit.
-- -------------------------------------------------------------
SELECT
    unite,
    count(*) AS occurrences
FROM evenements
WHERE unite IS NOT NULL
  AND (:potager = -1 OR potager_id = :potager)
GROUP BY unite
ORDER BY occurrences DESC, unite;

-- Variantes qui désignent vraisemblablement la même unité
-- (comparaison sur minuscules sans caractères non alphanumériques).
WITH normalisees AS (
    SELECT
        unite,
        -- les exposants typographiques sont translittérés AVANT le nettoyage,
        -- sans quoi 'm²' se normalise en 'm' et ne rejoint jamais 'm2'
        -- 1. exposants typographiques translittérés AVANT le nettoyage,
        --    sans quoi 'm²' se normalise en 'm' et ne rejoint jamais 'm2'
        -- 2. pluriel simple retiré : la production porte 'pied' (3) ET
        --    'pieds' (4), que la première version ne regroupait pas
        regexp_replace(
            lower(regexp_replace(translate(unite, '²³', '23'), '[^a-zA-Z0-9]', '', 'g')),
            's$', '')                                         AS forme_normalisee,
        count(*) AS occurrences
    FROM evenements
    WHERE unite IS NOT NULL
      AND (:potager = -1 OR potager_id = :potager)
    GROUP BY 1, 2
)
SELECT
    forme_normalisee,
    count(*)                                   AS nb_variantes,
    string_agg(unite || ' (' || occurrences || ')', ', ' ORDER BY occurrences DESC) AS variantes
FROM normalisees
GROUP BY forme_normalisee
HAVING count(*) > 1
ORDER BY nb_variantes DESC;
