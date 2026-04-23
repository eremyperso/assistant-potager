-- Migration v3 : rang devient un nombre de rangs (integer)
-- À exécuter UNE SEULE FOIS dans psql :
--   psql -U potager_user -d potager -f migration_v3.sql

DO $$
BEGIN
  IF (SELECT data_type FROM information_schema.columns
      WHERE table_name = 'evenements' AND column_name = 'rang') != 'integer' THEN
    ALTER TABLE evenements
      ALTER COLUMN rang TYPE INTEGER
      USING CASE
        WHEN rang::text ~ '^[0-9]+$'      THEN rang::text::integer
        WHEN rang::text ~ 'rang_([0-9]+)' THEN (regexp_match(rang::text, 'rang_([0-9]+)'))[1]::integer
        ELSE NULL
      END;
  END IF;
END $$;

COMMENT ON COLUMN evenements.rang IS 'Nombre de rangs plantés. Total plants = quantite × rang';
