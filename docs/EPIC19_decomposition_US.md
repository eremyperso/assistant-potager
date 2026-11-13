# ÉPIC 19 — Plan du potager sur vue du dessus : décomposition par US

*État au 13/11/2026. Maquette de référence : `Plan - Pistes.html` (Claude Design, hors `compat.json`).
Numéro d'épic à valider.*

## 1. Vue d'ensemble

- **16 US, 92 points** (US-320 à US-335).
- **Livrées : 10 US, 57 points (62 %)** — toutes en « Revue en cours » dans Jira, **aucune commitée**.
- **Restantes : 6 US, 35 points** — US-330 à US-335.
- Le plan vu du dessus remplace la Vue plan « rangs et places » (US-200 / US-228) et absorbe l'onglet
  Parcelles (US-222). US-203 est absorbée par US-326 (**à fermer dans Jira**).
- Principe directeur : *ce qui manque devient une tâche* — une culture sans parcelle est **listée**,
  jamais dessinée comme un lieu.

## 2. Décomposition, modèle et effort conseillés, état

Modèle / effort : valeurs inscrites dans chaque fiche du backlog (« Modèle / effort conseillé »).

| Ordre réel | US | Titre | Pts | Modèle · effort | Migration | État | Jira |
|---|---|---|---|---|---|---|---|
| 1 | **US-320** | Suivre les étapes d'une culture, prévues puis validées | 8 | **Opus 5.5 · high** | oui (v76) | ✅ Livrée, en Revue | PIA-304 |
| 2 | **US-321** | Dessiner l'étape d'une culture avec un langage visuel commun | 3 | Sonnet 5.5 · medium | non | ✅ Livrée, en Revue | PIA-305 |
| 3 | **US-326** | Enregistrer la géométrie du potager, des parcelles et des rangs | 8 | **Opus 5.5 · high** | oui (v76) | ✅ Livrée, en Revue | PIA-306 |
| 4 | **US-327** | Afficher le plan du potager vu du dessus | 8 | Sonnet 5.5 · high | non | ✅ Livrée, en Revue | PIA-307 |
| 5 | **US-322** | Ouvrir le suivi d'une culture depuis le plan | 5 | Sonnet 5.5 · medium | non | ✅ Livrée, en Revue | PIA-308 |
| 6 | **US-323** | Transmettre à Gaston ce que le jardinier a sous les yeux | 5 | **Opus 5.5 · high** | oui (v77) | ✅ Livrée, en Revue | PIA-309 |
| 7 | **US-324** | Noter ce que je vois avec Gaston, d'un seul bouton | 8 | **Opus 5.5 · high** | non | ✅ Livrée, en Revue | PIA-310 |
| 8 | **US-325** | Placer « Noter » au centre de la barre basse mobile | 2 | Sonnet 5.5 · medium | non | ✅ Livrée, en Revue | PIA-311 |
| 9 | **US-328** | Lister ce qui est à confirmer, à libérer et à placer aujourd'hui | 5 | Sonnet 5.5 · high | non | ✅ Livrée, en Revue | PIA-312 |
| 10 | **US-329** | Parcourir le plan sur mobile dans l'ordre du chemin | 5 | Sonnet 5.5 · medium | non | ✅ Livrée, en Revue | PIA-313 |
| 11 | **US-330** | Ouvrir le détail d'une parcelle dans le plan | 8 | Sonnet 5.5 · high | non | ⏳ À faire | à créer |
| 12 | **US-331** | Lire et modifier les caractéristiques d'une parcelle dans le plan | 3 | Sonnet 5.5 · medium | non (cf. P7) | ⏳ À faire | à créer |
| 13 | **US-332** | Créer, rendre inactive ou supprimer une parcelle avec Gaston | 5 | **Opus 5.5 · high** | non | ⏳ À faire | à créer |
| 14 | **US-333** | Modifier le plan sur ordinateur : poser, dimensionner, orienter | 8 | **Opus 5.5 · high** | non | ⏳ À faire | à créer |
| 15 | **US-334** | Mettre en place le plan d'un potager nouveau ou existant | 3 | Sonnet 5.5 · medium | non | ⏳ À faire | à créer |
| 16 | **US-335** | Poser le plan sur une photo du potager vue du dessus | 8 | **Opus 5.5 · high** | oui | 🔒 Bloquée (RGPD, P2) | à créer |

### Synthèse de production (au plus économique)

| Modèle · effort | US | Points |
|---|---|---|
| Opus 5.5 · high | 320, 323, 324, 326, 332, 333, 335 | 50 |
| Sonnet 5.5 · high | 327, 328, 330 | 21 |
| Sonnet 5.5 · medium | 321, 322, 325, 329, 331, 334 | 21 |

Fable n'est requis pour aucune US. Opus est réservé à ce qui écrit des données ou touche la boucle de
l'agent : chemin d'écriture, migration, nouvelles intentions du compagnon, interactions directes
transactionnelles, données personnelles.

## 3. Ordre d'implémentation

### 3.1 Déjà réalisé (dans l'ordre des dépendances)

```
US-320 étapes ─┬─► US-321 langage visuel ─┐
               │                           ├─► US-327 plan ─┬─► US-322 suivi ─────────┐
US-326 géométrie ───────────────────────────┘                ├─► US-328 Aujourd'hui ─┐ ├─► US-329 plan mobile
                                                             │                        │ │
US-323 contexte de Gaston ─► US-324 Noter ─► US-325 barre basse                       ┘ ┘
```

### 3.2 Reste à faire

```
US-327 + US-322 ─► US-330 détail parcelle ─► US-331 caractéristiques
US-323 + US-326 ─► US-332 créer / inactiver / supprimer (Gaston) ─► US-333 éditeur ─► US-334 mise en place
                                                                                  └─► US-335 photo (bloquée P2)
```

| Rang | US | Pourquoi à cette place |
|---|---|---|
| 1 | **US-330** | Débloquée (US-327 et US-322 livrées). Remplace l'onglet Parcelles ; le nom d'une parcelle ouvre aujourd'hui encore l'ancien onglet, et « Détail » (mobile, US-329) y renvoie en attendant. |
| 2 | **US-331** | Dépend d'US-330 ; arbitrage P7 (champ « type ») à trancher avant. |
| 3 | **US-332** | Débloquée (US-323, US-326 livrées) ; indépendante d'US-330, parallélisable. Doit précéder US-333 : l'éditeur crée ses formes par ce chemin. |
| 4 | **US-333** | Dépend d'US-326, US-327 et d'US-332 pour une forme nouvelle. |
| 5 | **US-334** | Dépend d'US-333 : mise en place du plan avec l'éditeur. |
| 6 | **US-335** | À traiter en dernier : dépend d'US-333 **et** de l'arbitrage RGPD P2 (stockage d'une photo = donnée personnelle). |

## 4. Arbitrages

| # | Sujet | État |
|---|---|---|
| P1 | Cultures ou Pépinière sous « Plus » | Tranché : **Cultures sous Plus** (US-325) |
| P2 | RGPD de la photo de fond | **Ouvert — bloque US-335** |
| P3 | Étapes par type de culture | Tranché : semis direct Semé → Levé → En récolte → Terminé ; plant Planté → En récolte → Terminé (US-320) |
| P4 | Rang partagé : fraction ou mètres | Tranché : la **position** du rang, et la part en mètres seulement si la longueur de la parcelle est connue (US-326, US-328) |
| P6 | Ordre du chemin | Tranché : `Parcelle.ordre` (US-329) |
| P7 | Champ « forme / type » de parcelle | Colonne `forme` posée par US-326 ; à confirmer avant US-331 |

## 5. Points d'attention sur l'existant

- **Rien n'est commité** : les dix US sont dans l'arbre de travail de `feature/pwa-plan-vue-parcelle`,
  mêlées à d'autres livraisons.
- **Sans `PATCH_NOTES.md` ni `VERSION`** : demande explicite (« sans notes ») ; à régulariser à la
  livraison.
- **Migrations** : v76 jouée en dev et en test ; **v77 (contexte des échanges) jouée nulle part**.
- **Maquette non comparée** : le rendu a été vérifié à 375 / 768 / 1280 px, mais jamais comparé point par
  point à « Plan - Pistes » — verdict QA : *GO avec réserves*.
- **Corpus de connaissance** : fiches mises à jour, **ingestion non lancée**.
- **Recette sur le vrai modèle** : US-323 (CA7) et US-324 non faites (accord requis avant tout appel
  réel) ; US-328 construit sa proposition de placement sans modèle, donc non concernée.
- **Jira** : à créer pour US-330 à US-335 ; US-203 à fermer.
- **Écran Parcelles** : le nom d'une parcelle (plan, mobile) ouvre toujours l'ancien onglet tant
  qu'US-330 n'est pas livrée.

## 6. Prochaine étape recommandée

1. Valider la comparaison avec la maquette sur les écrans livrés (US-321 à US-329) avant d'empiler
   US-330.
2. Commiter par lots cohérents (socle 320 / 321 / 326, puis suivi et Gaston 322 à 325, puis plan 327 à
   329), puis régulariser `PATCH_NOTES.md` et `VERSION`.
3. Enchaîner US-330 → US-331, en parallèle US-332.
4. Trancher P2 (RGPD) avant d'engager US-335.
