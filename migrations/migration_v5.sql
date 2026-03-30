-- Migration v5 — Classification agronomique des cultures (végétatif vs reproducteur)
-- À exécuter UNE SEULE FOIS depuis pgAdmin ou psql
--
-- Cette migration ajoute :
-- 1. Colonne type_organe_recolte à la table evenements
-- 2. Table culture_config avec classification des cultures classiques
-- 3. Données de seed pour 20+ cultures

-- Ajout de la colonne type_organe_recolte
ALTER TABLE evenements ADD COLUMN IF NOT EXISTS type_organe_recolte VARCHAR(255);

-- Création de la table culture_config
CREATE TABLE IF NOT EXISTS culture_config (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) UNIQUE NOT NULL,
    type_organe_recolte VARCHAR(255) NOT NULL,
    description_agronomique TEXT
);

-- Index pour les performances
CREATE INDEX IF NOT EXISTS idx_culture_config_nom ON culture_config(nom);
CREATE INDEX IF NOT EXISTS idx_culture_config_type ON culture_config(type_organe_recolte);

-- Insertion des données de seed (cultures classiques françaises)
INSERT INTO culture_config (nom, type_organe_recolte, description_agronomique) VALUES
-- Légumes-feuilles (végétatif)
('salade', 'végétatif', 'Feuille consommée directement, plante détruite à la récolte'),
('chou', 'végétatif', 'Feuille ou inflorescence, plante généralement détruite'),
('épinard', 'végétatif', 'Feuille, récolte multiple possible mais plante souvent détruite'),
('laitue', 'végétatif', 'Feuille, plante annuelle détruite à la récolte'),

-- Racines (végétatif)
('carotte', 'végétatif', 'Racine pivotante, plante détruite à la récolte'),
('betterave', 'végétatif', 'Racine tubérisée, plante détruite à la récolte'),
('radis', 'végétatif', 'Racine, plante annuelle rapide'),
('navet', 'végétatif', 'Racine, plante bisannuelle mais récolte destructive'),

-- Tiges/bulbes (végétatif)
('oignon', 'végétatif', 'Bulbe, plante détruite à la récolte'),
('poireau', 'végétatif', 'Tige renflée, plante bisannuelle'),
('céleri', 'végétatif', 'Tige et feuilles, récolte destructive'),

-- Fruits (reproducteur)
('tomate', 'reproducteur', 'Fruit issu de la fleur, plante pérenne en serre'),
('poivron', 'reproducteur', 'Fruit, plante annuelle productive'),
('aubergine', 'reproducteur', 'Fruit, plante annuelle'),
('courgette', 'reproducteur', 'Fruit, plante annuelle très productive'),
('concombre', 'reproducteur', 'Fruit, plante annuelle'),
('melon', 'reproducteur', 'Fruit, plante annuelle rampante'),
('haricot', 'reproducteur', 'Gousse (fruit), plante annuelle'),

-- Autres
('brocoli', 'végétatif', 'Inflorescence, plante bisannuelle'),
('chou-fleur', 'végétatif', 'Inflorescence, plante bisannuelle'),
('artichaut', 'végétatif', 'Capitule floral, plante pérenne mais récolte destructive'),
('asperge', 'végétatif', 'Turion, plante pérenne avec récoltes répétées'),

-- Cas particuliers
('pomme de terre', 'végétatif', 'Tubercule souterrain, plante détruite à la récolte'),
('fraise', 'reproducteur', 'Faux-fruit, plante pérenne productive')

ON CONFLICT (nom) DO NOTHING;

-- Mise à jour des événements existants avec le type d'organe récolté
UPDATE evenements 
SET type_organe_recolte = culture_config.type_organe_recolte
FROM culture_config
WHERE evenements.culture = culture_config.nom 
AND evenements.type_organe_recolte IS NULL;

-- Vérification
-- SELECT COUNT(*) as total_cultures FROM culture_config;
-- SELECT type_organe_recolte, COUNT(*) FROM culture_config GROUP BY type_organe_recolte;
-- SELECT culture, type_organe_recolte, COUNT(*) FROM evenements WHERE type_organe_recolte IS NOT NULL GROUP BY culture, type_organe_recolte ORDER BY culture;