# 02 — Découpage en US, modèle, effort et enchaînement

*Le modèle désigne celui qui **écrit le code** dans Claude Code, au plus économique qui tient. Le compagnon lui-même ne change pas de moteur.*
*Mis à jour le 25/11 (US-358 et US-359 livrées) ; le 24/11 : la version 2 de la maquette donne trois onglets à la Pépinière, ce qui en fait une US à elle seule (US-356), et le Plan passe dans sa propre US (US-360).*

## 1. Principe du découpage : peu d'US, transverses

Le but est d'intégrer vite. Chaque US couvre **une couche qui traverse toutes les vues** (tokens et mode sombre, coquille, compagnon)
ou **un groupe de vues qui partagent les mêmes pièces**. On n'en fait pas une par écran.
Les deux premières posent les briques. Les cinq suivantes peuvent alors avancer **en parallèle**, et les deux dernières ferment.

Le Mot de Gaston n'a pas d'US propre : le composant et sa règle commune sont dans la coquille (US-353),
et chaque US de vue écrit la règle de sa vue.

## 2. Les 10 US

| Vague | US | Titre | Pts | Modèle · effort | Migration | Dépend de | État |
|---|---|---|---|---|---|---|---|
| 1 | **US-352** | Poser les pièces du socle : tokens clairs et sombres, langage d'étape, calendrier, note du carnet, infobulle | 5 | Sonnet 5.5 · **high** | non | — | ✅ Livrée · v3.141.0 · PIA-337 en Revue |
| 1 | **US-353** | Poser la coquille commune : bandeau, en-tête, Mot de Gaston, barre d'outils, règle des temps, Noter rond, panneau droit | 8 | Sonnet 5.5 · **high** | non | US-352 | ✅ Livrée · v3.142.0 · PIA-338 en Revue |
| 2 | **US-354** | Passer le Tableau de bord (figé), les Stocks (avec Récoltes par saison) et le Journal sur le socle | 8 | Sonnet 5.5 · medium | non | US-353 | ✅ Livrée · v3.144.0 · PIA-339 en Revue |
| 2 | **US-355** | Ouvrir partout la fiche commune et refaire Cultures (Au potager, Catalogue) | 8 | Sonnet 5.5 · **high** | non | US-353 | ✅ Livrée · v3.145.0 · PIA-340 en Revue |
| 2 | **US-356** | Passer la Pépinière sur le socle : Parcours, Semer, Lots et fiche du lot | 8 | Sonnet 5.5 · medium | non | US-353 | ✅ Livrée · v3.143.0, onglet Lots remis à la maquette du 25/11 en v3.145.1 · PIA-341 en Revue |
| 2 | **US-360** | Passer le Plan sur le socle | 3 | Sonnet 5.5 · low | non | US-353 | ✅ Livrée · v3.143.0 · PIA-345 en Revue |
| 2 | **US-357** | Refaire l'écran de Gaston : plein écran mobile, panneau droit, carnet en Kalam, carte « À enregistrer » | 5 | Sonnet 5.5 · **high** | non | US-353 | ✅ Livrée · v3.143.0 · PIA-342 en Revue |
| 3 | **US-358** | Ouvrir Gaston déjà renseigné : contexte, phrase d'ouverture et suggestions sans modèle, depuis chaque porte | 5 | Sonnet 5.5 · medium | non | US-355, US-356, US-357 | ✅ Livrée · v3.146.0 · PIA-343 en Revue |
| 3 | **US-359** | Recette visuelle (clair et sombre), nettoyage des composants remplacés, guide et aide | 3 | Sonnet 5.5 · low | non | toutes | ✅ Livrée (recette visuelle partielle) · v3.147.0 · PIA-344 en Revue |
| Suite | **US-361** | Retirer la confiance de la lecture de Cultures et le code de l'ancien écran | 2 | Sonnet 5.5 · low | non | US-355 | 📝 Rédigée (`backlog/US-361_…`) · Jira non créé · à faire |
| | **Total** | | **55** | | **aucune** | | **9 US sur 10 livrées (53 pts sur 55)** |

*État au 25/11/2026 : les neuf US livrées sont implémentées sur la branche `ergo_socle_commun`, **non commitées**, avec leur ticket Jira en « Revue en cours ». US-358 (v3.146.0) et US-359 (v3.147.0) clôturent l'épic, sauf **US-361**, US-de-suite d'US-355 (la lecture de Cultures ne calcule plus la confiance de chaque espèce) : elle est rédigée, sans ticket Jira, et reste à faire. Le total de l'épic est de 55 points avec elle.*
*Réserve sur US-359 : la recette visuelle est **partielle** (mesures du DOM à 375, 768 et 1440 px, en clair et en sombre, sur cinq écrans et un potager vide ; aucune comparaison à la maquette, écran par écran). Voir `03_RECETTE.md`.*
*Le 25/11, la recette de l'utilisateur a fait corriger deux défauts : « Noter » depuis une fiche ouverte refermait Gaston (deux règles du panneau partagé, héritées d'US-353, se fermaient l'une l'autre), et la fiche d'un lot ouverte depuis le Parcours ne menait pas aux Lots (le lien mène maintenant au registre entier, sur la colonne du lot).*
*Le 25/11, la maquette « Socle commun » a changé l'onglet Lots de la Pépinière (même tableau que le Parcours, sans colonne « Tous ») et les icônes de lot et de carte : c'est repris sur US-356, v3.145.1.*

US-360 porte un numéro postérieur à US-359 parce qu'elle a été détachée d'US-356 après la numérotation. Elle appartient à la vague 2.

## 3. Ce que chaque US livre, en une phrase

| US | Ce que le jardinier voit après |
|---|---|
| 352 | Les mêmes pastilles d'étape (hachurées si prévues, point orange si dues, « En godet » pour la pépinière), le même calendrier aux six couleurs, le texte du jardinier en Kalam, et un mode sombre fidèle à la maquette |
| 353 | Toutes les vues ont le même en-tête, la même barre d'outils (Aujourd'hui · recherche · Filtrer · ⋯), le Mot de Gaston, l'en-tête qui se resserre au défilement et Noter comme seule porte. Le médaillon a disparu |
| 354 | Le Tableau de bord dit quoi faire aujourd'hui, en quatre sections fixes. Les Stocks ouvrent la comparaison des saisons. Le Journal regroupe les notes du jour en « n notes » |
| 355 | Toucher une culture n'importe où ouvre la même fiche (Suivi / Référence). Cultures trie par ce qui demande une action et présente les 109 espèces du catalogue |
| 356 | La Pépinière a trois onglets : Parcours (matrice emplacement × stade, un stade à la fois sur mobile), Semer (fenêtres ouvertes, cultures écartées, bientôt) et Lots (le même tableau, en colonnes En cours · À régler · Terminés et lignes par mois de semis, cartes de lot communes avec frise des gestes). La fiche du lot a le format de la fiche commune |
| 360 | Le Plan a l'en-tête, la barre d'outils, la légende repliable et l'appui long du socle, ainsi que les raccourcis « 3 à confirmer · 3 à libérer » |
| 357 | Gaston s'ouvre en plein écran sur mobile et à droite sur ordinateur. Ce que je dis s'affiche en Kalam, et ce qui sera écrit s'affiche dans une seule carte « À enregistrer » |
| 358 | Noter depuis une culture, un lot, une action du Mot de Gaston, « Noter la levée », « Semer » ou « Ajouter à mon potager » ouvre Gaston sur le bon sujet, avec la bonne phrase et les bonnes suggestions, sans attendre le modèle |
| 361 | Cultures s'ouvre sans attendre le calcul de la confiance de chaque espèce du référentiel ; rien ne change à l'écran, la confiance d'une seule culture se lit toujours dans l'onglet Référence de sa fiche |
| 359 | Les vues sont vérifiées à 375, 768 et 1440 px, en clair et en sombre. Les anciens composants (dont la personnalisation du tableau de bord) sont retirés, et le guide et l'aide décrivent la nouvelle navigation |

## 4. Enchaînement

```
Vague 1 (séquentielle)      Vague 2 (en parallèle, worktrees séparés)          Vague 3
US-352 ──► US-353 ──┬──► US-354  Tableau de bord · Stocks · Journal ──────────┐
                    ├──► US-355  Fiche commune · Cultures ───────────┐        │
                    ├──► US-356  Pépinière (Parcours · Semer · Lots) ┤        │
                    ├──► US-360  Plan ───────────────────────────────┼────────┼──► US-359
                    └──► US-357  Écran Gaston ───────────────────────┴► US-358 ┘
```

- **Chemin critique : 29 points** (US-352 → 353 → 355 ou 356 → 358 → 359). US-357 avance en même temps que US-355 et US-356.
- La vague 2 regroupe cinq US qui ne touchent pas les mêmes fichiers (vues distinctes, compagnon à part). Elles se mènent dans des worktrees séparés et se fusionnent sans conflit attendu, sauf `navigation.js` et `App.jsx`, que seule US-353 modifie.
- US-356 touche le backend en lecture (deux champs ajoutés à `echeances_lots`, sans migration) ; US-355 ajoute `espacement` à la fiche d'une culture ; US-361 retire des champs de `GET /cultures/vue`.
- US-361 recoupe US-359 / CA3 (suppression des composants remplacés, dont `CarteCulture`) : la première des deux livrée le fait, l'autre le constate.
- Aucune question ne reste ouverte (décisions D8 à D12 du 24/11).

## 5. Synthèse de production

| Modèle · effort | US | Points | Part |
|---|---|---|---|
| Sonnet 5.5 · **high** | 352, 353, 355, 357 | 26 | 47 % |
| Sonnet 5.5 · medium | 354, 356, 358 | 21 | 38 % |
| Sonnet 5.5 · low | 359, 360, 361 | 8 | 15 % |

Justification des `high` :
- **US-352** : on change des tokens (clairs et sombres) et des composants utilisés par toutes les vues, et une erreur de couleur d'étape se propage partout.
- **US-353** : la refonte de la coquille (`App.jsx`, navigation, défilement, panneau partagé) touche chaque écran.
- **US-355** : on fusionne deux fiches (`FicheCulture` et `SuiviCulture`), avec leurs critères d'acceptance hérités (US-207, US-322).
- **US-357** : on retouche l'affichage du chemin de confirmation, et une carte mal reliée peut confirmer la mauvaise proposition.

**Ni Opus ni Fable ne sont requis.** L'épic ne modifie ni la boucle du compagnon, ni le chemin d'écriture, ni le bot. C'est un travail d'interface sur des lectures et des écritures qui existent.

## 6. Ce qui reste hors de l'épic

- Le contenu des vues non dessinées (Statistiques, Paramètres, Pilotage, Onboarding, Connexion) : elles reçoivent la coquille seulement (D6).
- La photo dans Gaston : le bouton « Photo · bientôt » s'affiche désactivé, comme sur la maquette.
- Les pièces jointes : supprimées pour l'instant (D10).
- La personnalisation du tableau de bord : retirée (D11).
- La rotation : l'onglet « Rotation · à venir » est affiché désactivé, comme sur la maquette.
