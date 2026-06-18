# US-026 : Vue pépinière — godets en attente de plantation

**En tant que** : Admin  
**Je veux** : voir l'état de ma pépinière — quelles cultures sont en godets, combien de plants, quel taux de réussite  
**Afin que** : je puisse planifier mes plantations à venir sans interroger le bot

## Critères d'acceptation
- [ ] CA1 : La vue affiche 2 tuiles résumé en tête : total godets en stock + taux de réussite moyen (toutes variétés)
- [ ] CA2 : La liste présente une carte compacte par variété : culture, variété, godets restants, nb plantés / nb repiqués
- [ ] CA3 : Le taux de réussite est affiché sous forme d'un **grand chiffre coloré** selon seuil (vert ≥ 80%, orange ≥ 50%, rouge < 50%) + `<Progress />` pour le stock restant — **pas de RadialBarChart**
- [ ] CA4 : Les cultures dont le stock godet est épuisé (tout planté) n'apparaissent pas dans la liste principale
- [ ] CA5 : Un encart "Tout planté" (Shadcn Alert) liste en bas les cultures dont le stock est à zéro
- [ ] CA6 : États gérés : loading skeleton (3-4 cartes fantômes), erreur API, pépinière vide

## Composant UI ciblé
| Élément              | Librairie  | Composant exact                    | Props / variante                                          |
|----------------------|------------|------------------------------------|-----------------------------------------------------------|
| Tuiles résumé        | Shadcn/UI  | Grille 2 × `<Card />` metric       | Total godets + taux moyen — valeur numérique grande       |
| Carte par variété    | Shadcn/UI  | `<Card />` compact                 | Stock restant + % succès en grand chiffre coloré          |
| Barre stock restant  | Shadcn/UI  | `<Progress />`                     | valeur = stock_residuel / nb_godets, couleur teal si 0    |
| Encart "Tout planté" | Shadcn/UI  | `<Alert variant="default" />`      | Icône `CheckCircle` Lucide + noms cultures                |
| Skeleton             | Shadcn/UI  | `<Skeleton />`                     | 3-4 cartes fantômes hauteur fixe                          |

> ⚠️ Le `RadialBarChart` Recharts est **abandonné** pour cette vue : trop coûteux au re-render, illisible < 380px. Remplacé par grand chiffre + Progress bar (validé en maquette + recommandation UX).

## Données affichées
- **Source** : endpoint FastAPI `GET /godets` (**à créer** — exposer `calcul_godets(db)` depuis `utils/stock.py`)
- **Format** : `[{ culture, variete, nb_godets, nb_plants_godets, nb_plantes, stock_residuel, taux_reussite }]`
- **Fréquence refresh** : manuel (icône refresh topbar)

## Risques / Notes techniques
- `GET /godets` absent de `main.py` — **point bloquant backend** à traiter avant le sprint frontend
- Le calcul `taux_reussite` = `nb_plantes / nb_plants_godets × 100` peut être fait côté client si l'endpoint retourne les deux valeurs brutes

**Estimation :** 3 points  
**Dépendances :** US-023  
**Labels GitHub :** `us`, `sprint-frontend`, `frontend`, `consultation`
