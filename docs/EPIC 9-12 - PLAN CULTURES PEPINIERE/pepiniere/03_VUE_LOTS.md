# Conception fonctionnelle — onglet « Lots » de la Pépinière

> **Statut : ✅ conçu par la maquette « Lots - Journal de saison HF » (Claude Design, 19/10/2026) et
> livré par US-242 (v3.92.0).** Écart assumé avec les orientations ci-dessous : les lots sont groupés par
> **mois de semis**, plus par famille ; le détail des règles vit dans `docs/domaines/pepiniere.md`.

## Orientations retenues (réflexion du 19/10/2026)

- **Registre, sans gestes** (A40) : un bilan de chaque lot ; les gestes passent par la fiche du lot
  (US-216), porte commune avec Parcours.
- **Filtre En cours / Terminés / Tous** : aujourd'hui les lots réglés (#7, #18 à 0 disponible) sont
  mêlés aux lots actifs.
- **Gardés** : chiffres de bilan (semés, obtenus, % de germination et de levée, mis en terre, vendus),
  regroupement par famille, recherche, « Aller au lot n° ».
- **Remplacé** : la frise Germin. › Godet › Terre de chaque carte, qui répète le kanban, cède la place
  aux **dates réelles** de chaque passage.
- **Retiré** : toute idée d'alerte ou d'échéance, portées par Parcours.

## Plan du document à compléter

1. À quoi répond l'onglet
2. Anatomie de l'écran
3. Règles (L1…Ln) : filtre, carte de lot, chiffres de bilan, dates réelles, tri et groupes, recherche
4. Téléphone
5. États, droits, accessibilité
6. Données (ce que `GET /pepiniere/lots` porte déjà, ce qui manque — dates de chaque passage)
7. Écarts entre la maquette et le modèle réel
8. Impacts backlog (US-061, US-215 / CA1, US-216) et US nouvelles
