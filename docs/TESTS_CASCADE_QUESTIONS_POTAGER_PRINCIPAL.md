# Jeu de test — cascade de résolution (étages 0bis / 1) sur « Potager principal »

> **Contexte :** voir `docs/ARCHITECTURE_CIBLE_V2_reponses.md` — cascade de résolution des demandes.
> **Potager de test :** *Potager principal* (id 1, base de dev), 31 cultures réellement présentes
> en base au moment de la génération (tomate, courgette, cornichon, courge, salade, blette,
> butternut, oignon, potiron, betterave, carotte, aubergine, basilic, ciboulette, concombre,
> estragon, fenouil, fraise, framboise, menthe, navet, poivron, pâtisson, radis, rhubarbe,
> roquette, rutabaga, thym, échalote…).
> **But :** vérifier le comportement des étages 0bis (cache de questions types) et 1 (agrégations
> SQL) décrits au §3 du document d'architecture, y compris le cas des cultures absentes (§3 de
> cette liste) qui n'est pas traité explicitement dans le document cible.
>
> Cocher `[x]` dans la colonne **Testé** au fur et à mesure, et noter en commentaire tout écart
> (mauvais routage, cache non invalidé, réponse vide silencieuse…).

## 1. Étage 0bis — questions types à mettre en cache (25)

| # | Question | Étage | Testé |
|---|---|---|---|
| 1 | Stock tomates ? | 0bis | [ x] | (mauvais routage)
| 2 | Stock courgettes ? | 0bis | [ ] |
| 3 | Stock cornichons ? | 0bis | [ ] |
| 4 | Dernière récolte de tomates ? | 0bis | [ ] |
| 5 | Dernière récolte de courgettes ? | 0bis | [ ] |
| 6 | Il me reste combien de salades ? | 0bis | [ ] |
| 7 | Combien de blettes en stock ? | 0bis | [ ] |
| 8 | Quand ai-je semé les carottes ? | 0bis | [ ] |
| 9 | Quand ai-je semé les tomates ? | 0bis | [ ] |
| 10 | Quand ai-je planté les courgettes ? | 0bis | [ ] |
| 11 | Stock butternut ? | 0bis | [ ] |
| 12 | Stock potiron ? | 0bis | [ ] |
| 13 | Stock oignons ? | 0bis | [ ] |
| 14 | Dernière récolte de courges ? | 0bis | [ ] |
| 15 | Dernière récolte de cornichons ? | 0bis | [ ] |
| 16 | Il reste des betteraves ? | 0bis | [ ] |
| 17 | Combien de carottes j'ai en stock ? | 0bis | [ ] |
| 18 | Quand ai-je récolté la dernière fois des tomates ? | 0bis | [ ] |
| 19 | Stock aubergines ? | 0bis | [ ] |
| 20 | Stock poivrons ? | 0bis | [ ] |
| 21 | Dernière plantation de salades ? | 0bis | [ ] |
| 22 | Combien j'ai de fraises en stock ? | 0bis | [ ] |
| 23 | Stock radis ? | 0bis | [ ] |
| 24 | Quand ai-je semé les navets ? | 0bis | [ ] |
| 25 | Dernière récolte de betteraves ? | 0bis | [ ] |

## 2. Étage 1 — agrégations SQL sur les données réelles (45)

| # | Question | Étage | Testé |
|---|---|---|---|
| 26 | Combien de kilos de tomates ai-je récoltés cette année ? | 1 | [ ] |
| 27 | Combien de tomates récoltées cet été ? | 1 | [ ] |
| 28 | Combien de courgettes récoltées au total ? | 1 | [ ] |
| 29 | Combien de cornichons récoltés depuis le début ? | 1 | [ ] |
| 30 | Combien de courges récoltées ce mois-ci ? | 1 | [ ] |
| 31 | Quel est le total de mes pertes sur les tomates ? | 1 | [ ] |
| 32 | Combien de pieds de tomates ai-je plantés ? | 1 | [ ] |
| 33 | Combien de rangs de carottes ai-je semés ? | 1 | [ ] |
| 34 | Quelle quantité de blettes ai-je récoltée ? | 1 | [ ] |
| 35 | Combien de butternuts ai-je récoltées cette saison ? | 1 | [ ] |
| 36 | Combien de potirons ai-je récoltés cette année ? | 1 | [ ] |
| 37 | Combien d'oignons ai-je récoltés ? | 1 | [ ] |
| 38 | Combien de betteraves ai-je récoltées au total ? | 1 | [ ] |
| 39 | Quelle est ma récolte totale de salades ? | 1 | [ ] |
| 40 | Combien de fois ai-je arrosé les tomates ce mois-ci ? | 1 | [ ] |
| 41 | Combien de fois ai-je désherbé la parcelle nord ? | 1 | [ ] |
| 42 | Combien de fois ai-je biné cette saison ? | 1 | [ ] |
| 43 | Combien de graines de carottes ai-je semées ? | 1 | [ ] |
| 44 | Combien de plants de tomates ai-je mis en godet ? | 1 | [ ] |
| 45 | Combien de pertes de godets ai-je eues sur les courgettes ? | 1 | [ ] |
| 46 | Quelle est ma dernière observation sur les cornichons ? | 1 | [ ] |
| 47 | Quand ai-je fait mon dernier paillage ? | 1 | [ ] |
| 48 | Combien de kilos de courgettes ai-je vendus ? | 1 | [ ] |
| 49 | Quel a été mon meilleur mois de récolte pour les tomates ? | 1 | [ ] |
| 50 | Combien de récoltes de cornichons ai-je faites cette saison ? | 1 | [ ] |
| 51 | Combien d'événements ai-je enregistrés sur les tomates au total ? | 1 | [ ] |
| 52 | Combien de fois ai-je traité les courgettes ? | 1 | [ ] |
| 53 | Quelle quantité totale de courges ai-je récoltée cet automne ? | 1 | [ ] |
| 54 | Combien de récoltes ai-je faites en juillet ? | 1 | [ ] |
| 55 | Combien de récoltes ai-je faites en août ? | 1 | [ ] |
| 56 | Quelle culture ai-je le plus récoltée cette année ? | 1 | [ ] |
| 57 | Quelle culture ai-je le plus arrosée ? | 1 | [ ] |
| 58 | Combien de kilos de blettes ai-je récoltés cette saison ? | 1 | [ ] |
| 59 | Combien de fois ai-je semé des carottes cette année ? | 1 | [ ] |
| 60 | Quand ai-je planté les aubergines ? | 1 | [ ] |
| 61 | Combien d'aubergines ai-je récoltées ? | 1 | [ ] |
| 62 | Quand ai-je semé le basilic ? | 1 | [ ] |
| 63 | Combien de poivrons ai-je récoltés cet été ? | 1 | [ ] |
| 64 | Combien de fraises ai-je récoltées ce printemps ? | 1 | [ ] |
| 65 | Combien de framboises ai-je récoltées ? | 1 | [ ] |
| 66 | Combien de radis ai-je récoltés ce mois-ci ? | 1 | [ ] |
| 67 | Quand ai-je semé la roquette ? | 1 | [ ] |
| 68 | Combien de fois ai-je éclairci mes semis de carottes ? | 1 | [ ] |
| 69 | Quel a été mon premier semis de l'année ? | 1 | [ ] |
| 70 | Combien d'échalotes ai-je récoltées ? | 1 | [ ] |
| 71 | Combien de navets ai-je récoltés ? | 1 | [ ] |
| 72 | Combien de rhubarbe ai-je récoltée ? | 1 | [ ] |
| 73 | Combien de pâtissons ai-je récoltés ? | 1 | [ ] |
| 74 | Combien de rutabagas ai-je récoltés ? | 1 | [ ] |
| 75 | Combien de concombres ai-je récoltés cette saison ? | 1 | [ ] |
| 76 | Quel est le total de mes amendements cette année ? | 1 | [ ] |
| 77 | Combien de commentaires ai-je ajoutés sur les tomates ? | 1 | [ ] |
| 78 | Combien d'événements sur la parcelle sud ce mois-ci ? | 1 | [ ] |
| 79 | Combien de récoltes totales tous légumes confondus cette année ? | 1 | [ ] |
| 80 | Quelle est la culture avec le plus de pertes ? | 1 | [ ] |

## 3. Cultures absentes du potager — test « aucune donnée » (20)

Aucune de ces cultures n'a d'événement en base pour ce potager : sert à vérifier que l'étage 1
répond proprement (« aucune donnée pour cette culture ») plutôt qu'un résultat vide silencieux
ou un mauvais routage vers l'étage 3.

| # | Question | Étage | Testé |
|---|---|---|---|
| 81 | Stock pommes de terre ? | 0bis / 1 | [ ] |
| 82 | Combien de pommes de terre ai-je récoltées ? | 1 | [ ] |
| 83 | Quand ai-je semé les poireaux ? | 1 | [ ] |
| 84 | Stock haricots ? | 0bis / 1 | [ ] |
| 85 | Combien de haricots ai-je récoltés cette année ? | 1 | [ ] |
| 86 | Dernière récolte de petits pois ? | 0bis / 1 | [ ] |
| 87 | Combien d'épinards ai-je récoltés ? | 1 | [ ] |
| 88 | Stock d'ail ? | 0bis / 1 | [ ] |
| 89 | Quand ai-je planté les artichauts ? | 1 | [ ] |
| 90 | Combien de choux ai-je récoltés ? | 1 | [ ] |
| 91 | Stock de persil ? | 0bis / 1 | [ ] |
| 92 | Combien de céleris ai-je récoltés ? | 1 | [ ] |
| 93 | Quand ai-je semé le melon ? | 1 | [ ] |
| 94 | Combien de pastèques ai-je récoltées ? | 1 | [ ] |
| 95 | Stock de brocolis ? | 0bis / 1 | [ ] |
| 96 | Combien de choux-fleurs ai-je récoltés ? | 1 | [ ] |
| 97 | Quand ai-je semé la mâche ? | 1 | [ ] |
| 98 | Combien de cresson ai-je récolté ? | 1 | [ ] |
| 99 | Combien de panais ai-je récoltés ? | 1 | [ ] |
| 100 | Combien d'asperges ai-je récoltées ? | 1 | [ ] |

## Ce que ce jeu de test couvre

- **§1 (1-25)** : `app/services/cache_questions.py` — motif + template mémorisés, réponse servie
  sans second appel SQL/LLM (US-095). Vérifier aussi l'**invalidation événementielle** en
  enchaînant une saisie (« récolté 2kg tomates ») juste après une des questions 1-4.
- **§2 (26-80)** : `app/services/reponses_chiffrees.py` — gabarits sur agrégats SQL réels sans
  appel modèle (US-096), valeurs vérifiables directement en base.
- **§3 (81-100)** : point non traité explicitement dans `ARCHITECTURE_CIBLE_V2_reponses.md` —
  réponse propre sur culture absente plutôt qu'un silence ou un mauvais routage vers l'étage 3.
