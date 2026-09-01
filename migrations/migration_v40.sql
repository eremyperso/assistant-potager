-- =============================================================================
-- migration_v40.sql — Wind River Greens au registre des sources (US-161)
-- =============================================================================
-- Ajoute une ligne au registre d'US-166, et rien d'autre : aucune table, aucune
-- colonne, aucune donnée métier. Miroir SQL de l'entrée ajoutée à
-- `SOURCES_SOCLE` dans app/services/referentiel_sources.py — les deux doivent
-- rester identiques, comme la v38 l'a établi pour les quatre premières.
--
-- ── Pourquoi CC BY 4.0 entre au socle ────────────────────────────────────────
-- L'arbitrage §6.3 de docs/CONCEPTION_REFERENTIEL_CONNAISSANCE_CULTURES.md
-- n'écarte que le **partage à l'identique** (CC-BY-SA), qui contaminerait un
-- corpus devant rester propriétaire. CC BY 4.0 n'a aucune clause virale :
-- partage, adaptation et usage commercial sont libres. Sa seule contrainte est
-- l'attribution — déjà une obligation par enregistrement dans ce registre (CA1)
-- et déjà affichée avec la réponse servie au jardinier (US-164 / CA7).
--
-- Le socle refuse donc toujours CC-BY-SA, et toujours ce dont la licence n'est
-- pas établie. Le contrôle applicatif est dans
-- `referentiel_sources.verifier_licence_importable`, pas dans une contrainte
-- CHECK : l'arbitrage de licence est une décision produit révisable, et cette
-- migration en est la preuve.
--
-- ── L'attribution n'est pas décorative ───────────────────────────────────────
-- CC BY rend la mention obligatoire **à la communication au public**, donc à
-- l'affichage, pas seulement dans un README. La chaîne insérée ici est celle que
-- le fichier LICENSE du jeu de données demande, au mot près. Toute réponse qui
-- dérive de cette source doit la porter.
--
-- ⚠️ Ce que la migration ne fait pas : elle n'importe aucune donnée. Le
-- manifeste `data/referentiel/wind_river_attributs.json` est produit hors ligne
-- par `tools/adapter_wind_river.py` puis joué par `tools/importer_referentiel.py`
-- — jamais par une migration, qui n'est pas rejouable (US-166, notes techniques).
--
-- Idempotent : INSERT ... ON CONFLICT DO NOTHING.
-- Rollback : migrations/rollback_v40.sql
-- =============================================================================

\set ON_ERROR_STOP on

BEGIN;

INSERT INTO referentiel_source (code, libelle, licence, attribution, url, partageable, importee) VALUES
    ('wind_river_greens', 'Wind River Greens Plant Database', 'CC BY 4.0',
     'Plant variety data from Wind River Greens Plant Database (https://plants.windrivergreens.com), CC BY 4.0',
     'https://github.com/bripatch/plant-variety-database', TRUE, TRUE)
ON CONFLICT (code) DO NOTHING;

COMMIT;

-- Vérification post-migration
SELECT code, licence, partageable, importee, attribution
FROM referentiel_source
ORDER BY code;

-- [US-166/CA4] Ce qui dérive de cette source, avant comme après l'import.
SELECT COUNT(*) FILTER (WHERE c.exposition_source_id       = s.id) AS exposition,
       COUNT(*) FILTER (WHERE c.besoin_eau_source_id       = s.id) AS besoin_eau,
       COUNT(*) FILTER (WHERE c.profondeur_semis_source_id = s.id) AS profondeur,
       COUNT(*) FILTER (WHERE c.rusticite_min_source_id    = s.id) AS rusticite
FROM culture_config c
CROSS JOIN referentiel_source s
WHERE s.code = 'wind_river_greens';
