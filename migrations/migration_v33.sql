-- =============================================================================
-- migration_v33.sql — Backfill unité de dénombrement pied/pieds → plants
-- (US-168 CA5, CA6, CA8, CA9, CA11)
-- =============================================================================
-- `plants` est l'unité canonique de dénombrement (84 lignes en production
-- contre 6 en pied/pieds pour la même réalité). La normalisation à l'écriture
-- (app/services/evenements.py::_normalize_unite_denombrement) couvre déjà
-- toute nouvelle saisie ; cette migration corrige les lignes historiques
-- restées en pied/pieds, pour qu'un GROUP BY unite ne les sépare plus de leur
-- culture et que le garde-fou [US-037 CA2]
-- (utils/stock.py::_resoudre_unite_dominante) cesse de les exclure en
-- silence du total.
--
-- Ne touche jamais un semis : "pieds" y désigne un semis en poquets, une
-- convention distincte établie par US-037 et hors périmètre de cette US
-- (CA7) — la condition type_action <> 'semis' l'exclut explicitement.
--
-- Réversible : les valeurs d'origine sont conservées dans la table
-- _backfill_v33_unite_avant avant d'être écrasées (voir rollback_v33.sql).
--
-- Idempotente : une ré-exécution ne trouve plus aucune ligne pied/pieds hors
-- semis (déjà passées à 'plants'), donc ne modifie plus rien ; l'INSERT de
-- sauvegarde est lui-même protégé par ON CONFLICT DO NOTHING.
-- Rollback : migrations/rollback_v33.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS _backfill_v33_unite_avant (
    evenement_id INTEGER PRIMARY KEY REFERENCES evenements(id),
    unite_avant  VARCHAR
);

INSERT INTO _backfill_v33_unite_avant (evenement_id, unite_avant)
SELECT id, unite
FROM evenements
WHERE lower(unite) IN ('pied', 'pieds')
  AND type_action <> 'semis'
ON CONFLICT (evenement_id) DO NOTHING;

UPDATE evenements
SET unite = 'plants'
WHERE lower(unite) IN ('pied', 'pieds')
  AND type_action <> 'semis';

COMMIT;

-- Vérification post-migration
SELECT type_action, unite, COUNT(*)
FROM evenements
WHERE lower(unite) IN ('pied', 'pieds', 'plants')
GROUP BY type_action, unite
ORDER BY type_action, unite;

SELECT COUNT(*) AS nb_lignes_backfillees FROM _backfill_v33_unite_avant;
