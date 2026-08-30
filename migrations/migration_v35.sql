-- =============================================================================
-- migration_v35.sql — Origine de la date d'un évènement (US-169 / CA1, CA2)
-- =============================================================================
-- Ajoute `evenements.date_source` : trace, quand elle est connaissable, la
-- nature de l'ancrage temporel qui a produit `date`.
--
-- Valeurs, arrêtées par CA3 avant l'implémentation (voir aussi
-- utils/date_utils.py, section "Taxonomie date_source") :
--   'explicite'          — date dictée en clair ("le 25 mai")
--   'relative_resolue'   — date relative résolue ("hier", "il y a 3 jours")
--   'presumee'           — aucun ancrage dicté, convention "aujourd'hui"
--   'modele_incertain'   — date rendue par le modèle, origine non connaissable
--   NULL                 — antérieur à l'US, ou chemin d'écriture qui ne sait
--                          pas conclure (CA7 : jamais deviné)
--
-- Séparée de migration_v34.sql (`origine_parsing`, US-094) : les deux colonnes
-- vivent sur la même table mais chaque US a sa propre migration, chacune
-- idempotente et rejouable indépendamment de l'autre.
--
-- À quoi elle sert, et à quoi elle ne sert PAS :
--   * elle donne le DÉNOMINATEUR qui manque pour transformer les traces
--     [CORR] de production (une borne basse de corrections remarquées) en
--     un taux de correction réel, ventilé par origine de date — voir
--     tools/analyse_date_source.sql (CA11, CA12) ;
--   * elle n'est lue par AUCUNE condition métier, aucun gabarit de réponse et
--     aucun message utilisateur (CA8, CA9). Un évènement se comporte
--     exactement pareil quelle que soit sa valeur — c'est de
--     l'instrumentation, pas de l'état.
--
-- NULL n'est pas 'presumee' : NULL signifie "inconnu" (chemin non couvert, ou
-- ligne antérieure à l'US), 'presumee' signifie "on sait qu'aucune date n'a
-- été dictée". Les confondre rendrait la mesure fausse dans le sens qui
-- arrange (CA7).
--
-- Purement additive : colonne nullable, sans défaut, sans contrainte — aucune
-- écriture existante n'a à changer pour rester valide. Aucun backfill,
-- délibérément (CA4) : une valeur reconstituée depuis le texte ne serait pas
-- une observation.
--
-- Idempotent : ADD COLUMN IF NOT EXISTS.
-- Rollback : migrations/rollback_v35.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE evenements
    ADD COLUMN IF NOT EXISTS date_source VARCHAR(20);

COMMENT ON COLUMN evenements.date_source IS
    'US-169/CA1 — explicite | relative_resolue | presumee | modele_incertain | NULL '
    '(antérieur à l''US, ou chemin qui ne sait pas conclure). '
    'Instrumentation seule : jamais lue par une condition métier.';

-- Requête cible : « quelle part des dates est présumée plutôt que dictée,
-- par période ». L'index partiel évite de peser sur les lignes historiques,
-- toutes à NULL.
CREATE INDEX IF NOT EXISTS idx_evenements_date_source
    ON evenements (date_source, date)
    WHERE date_source IS NOT NULL;

COMMIT;

-- Vérification post-migration
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'evenements' AND column_name = 'date_source';

SELECT COALESCE(date_source, '(historique)') AS source, COUNT(*)
FROM evenements
GROUP BY 1
ORDER BY 2 DESC;
