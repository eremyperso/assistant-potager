# US-024 : Vue plan d'occupation des parcelles

**En tant que** : Admin  
**Je veux** : voir sur une page dédiée l'occupation actuelle de chaque parcelle avec les cultures en cours  
**Afin que** : j'aie une vue d'ensemble rapide de ce qui pousse où, depuis mon téléphone au jardin

## Critères d'acceptation
- [ ] CA1 : La vue affiche une carte par parcelle active (nom, exposition, superficie si renseignée)
- [ ] CA2 : Chaque carte liste les cultures actuellement en place avec leur variété et nombre de plants
- [ ] CA3 : Un badge coloré indique le type de culture : vert = végétatif, orange = reproducteur, gris = libre
- [ ] CA4 : Les parcelles sans culture active sont affichées avec le statut "Libre"
- [ ] CA5 : Un bouton "Actualiser" recharge les données depuis l'API — indicateur de chargement visible
- [ ] CA6 : États gérés : loading skeleton (cartes fantômes), erreur API, aucune parcelle enregistrée

## Composant UI ciblé
| Élément             | Librairie  | Composant exact               | Props / variante                                  |
|---------------------|------------|-------------------------------|---------------------------------------------------|
| Carte parcelle      | Shadcn/UI  | `<Card />` + `<CardContent />` | 1 colonne mobile, 2-3 colonnes desktop            |
| Badge type culture  | Shadcn/UI  | `<Badge />`                   | `default`=végétatif, `secondary`=reproducteur     |
| Barre superficie    | Shadcn/UI  | `<Progress />`                | % d'occupation si superficie connue               |
| Skeleton            | Shadcn/UI  | `<Skeleton />`                | Hauteur fixe, 1 par parcelle attendue             |
| Icônes              | Lucide     | `Leaf`, `MapPin`, `Sun`       | Exposition, localisation                          |

## Données affichées
- **Source** : endpoint FastAPI `GET /plan` (existant)
- **Format** : `{ parcelles: [{ nom, exposition, superficie_m2, cultures: [{ culture, variete, nb_plants, type_organe }] }] }`
- **Fréquence refresh** : manuel (bouton)

## Risques / Notes techniques
- Vérifier que `GET /plan` retourne bien les parcelles sans culture (statut "libre") — sinon adapter l'endpoint
- Sur mobile (< 768px) : 1 colonne, cartes empilées — éviter le scroll horizontal

**Estimation :** 3 points  
**Dépendances :** US-023  
**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `consultation`
