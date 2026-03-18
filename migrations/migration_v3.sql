-- Migration v3 : rang devient un nombre de rangs (integer)
-- À exécuter UNE SEULE FOIS dans psql :
--   psql -U potager_user -d potager -f migration_v3.sql

ALTER TABLE evenements
  ALTER COLUMN rang TYPE INTEGER
  USING CASE
    WHEN rang ~ '^[0-9]+$'       THEN rang::integer   -- "3" → 3
    WHEN rang ~ 'rang_([0-9]+)'  THEN (regexp_match(rang, 'rang_([0-9]+)'))[1]::integer
    ELSE NULL
  END;

COMMENT ON COLUMN evenements.rang IS 'Nombre de rangs plantés. Total plants = quantite × rang';
