-- =============================================================================
-- rollback_v38.sql — Annule migration_v38.sql (registre de sources, US-166)
-- =============================================================================
-- Retire les colonnes de rattachement puis supprime `referentiel_source`.
-- L'ordre importe : les deux FK doivent disparaître avant la table référencée.
--
-- Perte : la traçabilité d'origine (CA1-CA4) et les noms scientifiques importés
-- de Wikidata. Le référentiel lui-même n'est PAS touché — `familles_botaniques`,
-- `culture_config.famille_id` et les délais de retour survivent tels quels :
-- l'application retombe exactement sur le comportement d'US-067, où la famille
-- d'une culture existe sans qu'on sache d'où elle vient.
--
-- ⚠️ À exécuter APRÈS avoir redéployé une version du code qui ne lit plus
-- `referentiel_source` (app/services/referentiel_sources.py,
-- app/services/import_referentiel.py, tools/importer_referentiel.py, et le
-- marquage d'origine dans app/services/familles.py) — sans quoi ces chemins
-- échoueraient en base.
--
-- ⚠️ Conséquence fonctionnelle à assumer avant de rejouer l'import ensuite :
-- sans `source_id`, la règle de non-écrasement des corrections humaines (CA5)
-- n'a plus de mémoire. Un import rejoué après ce rollback repartirait d'une
-- base où toute valeur déjà renseignée est simplement conservée — plus
-- prudente, mais incapable de rafraîchir sa propre donnée.
-- =============================================================================

BEGIN;

DROP INDEX IF EXISTS idx_culture_config_famille_source;

ALTER TABLE culture_config
    DROP COLUMN IF EXISTS famille_source_id;

DROP INDEX IF EXISTS idx_familles_botaniques_source;

ALTER TABLE familles_botaniques
    DROP COLUMN IF EXISTS source_id;

ALTER TABLE familles_botaniques
    DROP COLUMN IF EXISTS nom_scientifique;

DROP TABLE IF EXISTS referentiel_source;

COMMIT;
