-- =============================================================================
-- migration_v13.sql — Correction culture_config : cucurbitacées + espacement/surface
-- =============================================================================
-- Prérequis : migration_culture_surface.sql déjà appliquée (colonnes espacement,
--             surface_m2 déjà présentes sur culture_config).
--
-- Ce script :
--   1. Supprime "courge butternut" (remplacée par entrées spécifiques)
--   2. Ajoute les cucurbitacées manquantes + fenouil + échalote
--   3. Renseigne espacement et surface_m2 sur les nouvelles entrées
--   4. Rétropopule type_organe_recolte NULL dans evenements
--
-- Idempotent : ON CONFLICT (nom) DO NOTHING
-- =============================================================================

-- [1] Supprimer l'entrée mal nommée
DELETE FROM culture_config WHERE nom = 'courge butternut';

-- [2] Ajouter les cucurbitacées manquantes + fenouil + échalote
INSERT INTO culture_config (nom, type_organe_recolte, description_agronomique, espacement, surface_m2) VALUES

-- Pâtissons
('pâtisson panaché',           'reproducteur', 'Cucurbitacée, fruit aplati panaché blanc et vert',      '100 × 120 cm', 1.200),
('pâtisson verruqueux',        'reproducteur', 'Cucurbitacée, surface irrégulière, récolte échelonnée', '100 × 120 cm', 1.200),

-- Citrouilles
('citrouille',                 'reproducteur', 'Cucurbitacée, grand fruit orange, récolte en automne',  '150 × 200 cm', 3.000),
('citrouille de Touraine',     'reproducteur', 'Variété régionale, fruit allongé orange',               '150 × 200 cm', 3.000),

-- Courge spaghetti
('courge spaghetti',           'reproducteur', 'Cucurbitacée à chair filandreuse, 2-3 fruits/plante',   '120 × 150 cm', 1.800),

-- Potirons et variétés
('rouge vif d''Étampes',       'reproducteur', 'Potiron aplati rouge vif décoratif et comestible',      '150 × 150 cm', 2.250),
('jaune gros de Paris',        'reproducteur', 'Potiron jaune-orangé, très gros fruit, variété ancienne','150 × 150 cm', 2.250),
('bleu de Hongrie',            'reproducteur', 'Courge à peau grise-bleue, chair orange fine',          '150 × 150 cm', 2.250),
('blanc de Corné',             'reproducteur', 'Potiron blanc ivoire, chair ferme, bonne conservation', '150 × 150 cm', 2.250),
('noir du Brésil',             'reproducteur', 'Courge à peau très sombre, chair orangée',              '150 × 150 cm', 2.250),
('Atlantic Giant',             'reproducteur', 'Potiron géant de compétition, peut dépasser 100 kg',   '200 × 300 cm', 6.000),
('galeuse d''Eysines',         'reproducteur', 'Potiron verruqueux roux, très sucrée, spécialité gir.', '150 × 150 cm', 2.250),

-- Giraumons
('giraumon',                   'reproducteur', 'Cucurbitacée en forme de toupie, chair fine et sucrée', '120 × 150 cm', 1.800),
('bonnet turc',                'reproducteur', 'Giraumon bicolore orange et vert, décoratif',           '120 × 150 cm', 1.800),

-- Potimarrons et variétés
('potimarron Red Curry',       'reproducteur', 'Potimarron à peau rouge-orange vif, chair dense',       '110 × 135 cm', 1.485),
('potimarron à gros fruits',   'reproducteur', 'Potimarron à fruits plus volumineux',                   '120 × 150 cm', 1.800),

-- Courges musquées et variétés
('courge longue de Nice',      'reproducteur', 'Longue courge verte striée, récolte jeune ou mûre',     '120 × 175 cm', 2.100),
('courge musquée de Provence', 'reproducteur', 'Grande courge aplatie cannelée, chair orange sucrée',   '120 × 175 cm', 2.100),
('courge pleine de Naples',    'reproducteur', 'Longue courge cylindrique verte, chair ferme',          '120 × 175 cm', 2.100),
('courge sucrine du Berry',    'reproducteur', 'Courge musquée compacte, très sucrée',                  '120 × 150 cm', 1.800),
('musqué de Provence',         'reproducteur', 'Alias courge musquée de Provence, aplatie cannelée',    '120 × 175 cm', 2.100),

-- Courges de Hubbard
('hubbard',                    'reproducteur', 'Grande courge en forme de poire, conservation hivernale','150 × 200 cm', 3.000),
('hubbard vert verruqueux',    'reproducteur', 'Hubbard à peau verte bosselée, chair orange fine',      '150 × 200 cm', 3.000),
('hubbard Navajo',             'reproducteur', 'Hubbard à peau gris-bleu lisse, chair très sucrée',     '150 × 200 cm', 3.000),
('hubbard bleu',               'reproducteur', 'Hubbard gris-bleu, gros fruit, conservation excellente','150 × 200 cm', 3.000),
('hubbard Golden',             'reproducteur', 'Hubbard à peau orange-jaune, plus petite',              '150 × 175 cm', 2.625),

-- Butternut et variétés
('butternut Waltham',          'reproducteur', 'Butternut classique, variété de référence',             '120 × 175 cm', 2.100),
('butternut Ponca',            'reproducteur', 'Butternut compact, précoce, idéal potager familial',    '100 × 150 cm', 1.500),
('Neck Pumpkin',               'reproducteur', 'Butternut du sud des USA, très long col',               '120 × 175 cm', 2.100),

-- Manquants dans les données existantes
('fenouil',                    'végétatif',    'Bulbe aromatique anisé, récolte destructive',           '25 × 40 cm',   0.100),
('échalote',                   'végétatif',    'Bulbe alliacée en touffe, récolte destructive',         '15 × 30 cm',   0.045)

ON CONFLICT (nom) DO NOTHING;

-- [3] Renseigner espacement/surface_m2 sur les entrées qui existent déjà
--     (potimarron, butternut, courge, courge musquée, pâtisson insérés par migration_v6
--      sans ces colonnes)
UPDATE culture_config SET espacement = '110 × 135 cm', surface_m2 = 1.485
    WHERE nom = 'potimarron'     AND surface_m2 IS NULL;
UPDATE culture_config SET espacement = '120 × 175 cm', surface_m2 = 2.100
    WHERE nom = 'butternut'      AND surface_m2 IS NULL;
UPDATE culture_config SET espacement = '150 × 200 cm', surface_m2 = 3.000
    WHERE nom = 'courge'         AND surface_m2 IS NULL;
UPDATE culture_config SET espacement = '120 × 175 cm', surface_m2 = 2.100
    WHERE nom = 'courge musquée' AND surface_m2 IS NULL;
UPDATE culture_config SET espacement = '100 × 120 cm', surface_m2 = 1.200
    WHERE nom = 'pâtisson'       AND surface_m2 IS NULL;
UPDATE culture_config SET espacement = '120 × 150 cm', surface_m2 = 1.800
    WHERE nom = 'courge spaghetti' AND surface_m2 IS NULL;

-- [4] Rétropopuler type_organe_recolte NULL dans evenements
UPDATE evenements
SET    type_organe_recolte = cc.type_organe_recolte
FROM   culture_config cc
WHERE  LOWER(evenements.culture) = LOWER(cc.nom)
  AND  evenements.type_organe_recolte IS NULL;

-- [5] Vérification
SELECT nom, espacement, surface_m2, type_organe_recolte
FROM   culture_config
WHERE  surface_m2 IS NULL
ORDER BY nom;
-- Attendu : 0 lignes (toutes les cultures ont une surface)
