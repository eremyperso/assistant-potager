# 🌱 ÉPIC 5 — Calendrier cultural

> **Nom exact pour le Milestone GitHub :** `ÉPIC 5 — Calendrier cultural`
> **Statut :** 📝 Cadré — aucune US implémentée
> **Cadrage arrêté au :** 13/08/2026
> **Volume :** 3 US, 21 points
> **Origine :** cadrage d'US-060 (refonte de l'écran Plan) — la maquette 2026 affiche une frise
> de calendrier sur chaque culture, dont la donnée n'existe nulle part dans l'application.

---

## 1. Le problème

L'application sait **tout** de ce que le jardinier a fait — chaque semis, chaque mise en godet,
chaque plantation, chaque récolte est daté et rattaché à une parcelle — et **rien** de ce qu'il
devrait faire ensuite. `culture_config` ne porte que le type d'organe de récolte, une
description agronomique, l'espacement et la surface au sol par plant. Aucune notion de saison,
de délai, de période conseillée.

Conséquence concrète : devant une parcelle, l'application est incapable de répondre aux deux
questions que le jardinier se pose réellement — **« où en est cette culture ? »** et
**« quand est-ce que je récolte ? »** — alors qu'elle dispose déjà de toutes les dates
nécessaires pour les calculer. Il ne lui manque que le référentiel des durées.

La maquette 2026 propose bien une frise de douze mois par culture, mais avec des mois codés en
dur dans ses données de démonstration, et un découpage (semis / plantation / récolte) qui ne
correspond pas à la réalité horticole.

## 2. La valeur métier

| Bénéfice | Aujourd'hui | Après l'épic |
|---|---|---|
| Savoir quand récolter | Le jardinier estime de mémoire | Date attendue calculée depuis son semis réel |
| Savoir où en est une culture | Rien | Durée restante affichée en jours |
| Échelonner ses semis | Rien | Prochaine plage de semis encore possible |
| Planifier une saison | Affiche papier à côté de l'ordinateur | Fenêtres conseillées adaptées à la zone climatique |
| Distinguer ses filières | Semis pépinière et pleine terre confondus | Deux totaux séparés en statistiques |

## 3. Périmètre

**Dans l'épic :**
- Un référentiel de calendrier et de durées attaché aux cultures, corrigeable sans livraison.
- La distinction pépinière / pleine terre sur l'événement de semis.
- Le recalage du calendrier sur les événements réels d'une parcelle, avec durée restante.
- L'évolution du composant de frise partagé du design system (quatrième état, mois mis en
  évidence paramétrable).

**Hors épic :**
- L'affichage lui-même sur l'écran Plan — c'est **US-060** (Lot B), qui consomme cet épic et
  prévoit un mode dégradé pour vivre sans lui.
- Les alertes et rappels dérivés (« ta courgette est récoltable depuis 5 jours ») — module
  « À faire cette semaine » du **Lot D**.
- Le reste du schéma horticole (exposition, besoin en eau) et la vue « Cultures » transverse —
  **Lot E** (§5.3 de `ANALYSE_REFONTE_UI_WEB_2026.md`).
- La famille botanique — **US-067**, US voisine sur la même table, mais périmètre distinct.
- L'édition du référentiel depuis l'interface web — le bot suffit à l'exigence
  « corrigeable sans livraison ». L'édition web relève du Lot E.

## 4. Arbitrages produit actés

| Sujet | Décision | Motif |
|---|---|---|
| **Granularité** | Culture **+ itinéraire cultural** (« culture précoce », « d'été », « d'automne », « d'hiver »). Jamais la variété | « Chou-fleur d'hiver » est une conduite, pas un cultivar. Aucune source horticole ne descend au niveau de la variété — y descendre reviendrait à tout saisir à la main |
| **Climat** | Fenêtres **déclinées par zone climatique** ; le potager porte la sienne, pré-positionnée depuis sa localisation et corrigeable | Les fenêtres décalent de plusieurs semaines entre Lille et Perpignan. Un référentiel unique serait faux pour la majorité des jardiniers |
| **Durées** | **Non déclinées** par zone, communes à toutes | Le délai entre semis et récolte relève de la physiologie de la plante, pas de la latitude. Divise par quatre la donnée à sourcer |
| **Phases** | Semis **en pépinière** / semis **en pleine terre** / récolte — et non semis / plantation / récolte | Modèle des calendriers de semis du commerce. Le repiquage n'est pas une fenêtre autonome : il découle du semis en pépinière |
| **Affichage** | Frise **recalée sur le réel**, avec un quatrième état « en croissance » et la durée restante en clair | Devant une culture déjà en terre, une fenêtre conseillée générique n'apprend rien : le jardinier a semé, il sait quand |
| **Honnêteté** | L'application **n'invente jamais** une date ni une durée. Sans donnée : frise neutre, durée en tiret | Une projection fausse est pire que pas de projection. Une fourchette reste une fourchette, jamais une date certaine |

## 5. Le modèle cible

```
culture_config  ──┬── famille botanique                         [US-067, hors épic]
                  │
                  └── itinéraires culturaux                     [US-068]
                        ├── nom  (standard / précoce / d'été / d'automne / d'hiver)
                        ├── fenêtres, déclinées par zone climatique
                        │     ├── semis en pépinière
                        │     ├── semis en pleine terre
                        │     └── récolte
                        └── durées, communes à toutes les zones
                              ├── semis → levée
                              ├── semis → première récolte
                              └── semis → repiquage   (itinéraire pépinière seulement)

potager ──── zone climatique                                    [US-068]
                pré-positionnée depuis la localisation, corrigeable

evenement (semis) ──── contexte : pépinière | pleine terre      [US-069]
                          détermine la fenêtre applicable et l'ancrage

                          ▼
              projection recalée, calculée à la volée            [US-070]
              aucune donnée stockée, aucune saisie nouvelle
```

**Déjà en place, à ne pas redévelopper :** l'écartement entre plants (`culture_config.espacement`
et `surface_m2`), le chaînage `semis → godet → plantation` (`origine_graines_id`,
`source_evenement_ids` — US-029, US-065, US-066), le calcul « N jours depuis le semis » de
l'écran Pépinière (US-065), et le composant de frise des douze mois avec son code couleur
(`frontend/src/components/ui/MonthStrip.jsx` — US-052).

## 6. Le cas qui sert de référence

Courgette semée **en pleine terre le 12 avril**, référentiel à **10 jours** jusqu'à la levée et
**95 jours** jusqu'à la récolte, parcelle consultée le **15 juin** :

```
   J    F    M    A    M    J    J    A    S    O    N    D
  ░░   ░░   ░░   ██   ▒▒   ▒▒   ▓▓   ▓▓   ▓▓   ▓▓   ░░   ░░
                  ▲              ▲
                  │              └ récolte attendue à partir du 16/07   (12/04 + 95 j)
                  └ semis réel 12/04 · levée attendue ~22/04            (12/04 + 10 j)

  ██ semis    ▒▒ en croissance    ▓▓ récolte    ░░ rien de prévu
  → 64 jours écoulés · 31 jours restants avant récolte
```

Sans cet épic, la même frise afficherait « semis avril-mai, récolte juin-octobre » : vrai pour
la courgette en général, faux pour celle-ci.

## 7. Les User Stories

| US | Titre | Points | Nature | Migration |
|---|---|---|---|---|
| [US-068](../backlog/US-068_referentiel-calendrier-cultural.md) | Constituer le référentiel de calendrier cultural et de durées des cultures | 8 | Donnée de référence | **oui** |
| [US-069](../backlog/US-069_contexte-semis-pepiniere-pleine-terre.md) | Distinguer le semis en pépinière du semis en pleine terre sur l'événement | 5 | Saisie + statistiques | **oui** |
| [US-070](../backlog/US-070_calendrier-recale-evenements-reels.md) | Recaler le calendrier cultural sur les événements réels de la parcelle | 8 | Calcul + affichage | non |

```
US-068 (référentiel) ──┬──→ US-069 (contexte semis) ──┬──→ US-070 (recalage) ──→ US-060 affiche
                       │                               │
                       │    fournit l'itinéraire       │   ne stocke rien :
                       │    probable et les fenêtres   │   lit et projette
                       └───────────────────────────────┘

US-067 (famille botanique) ── indépendante, même table `culture_config`
                              → séquencer les migrations si menées en parallèle
```

**Chemin critique :** US-068 → US-070. US-069 est livrable seule pour sa partie statistique
(CA6), mais conditionne la justesse du recalage : sans elle, US-070 applique son mode dégradé
et affiche les fenêtres génériques sans les recaler.

## 8. Séquencement

| Jalon | Contenu | Ce que le jardinier gagne |
|---|---|---|
| **J1** | US-068 | Les fenêtres conseillées s'affichent, adaptées à sa zone. Utile en planification |
| **J2** | US-069 | Ses statistiques distinguent enfin les deux filières de semis |
| **J3** | US-070 | La frise parle de **son** potager : date de récolte attendue et jours restants |

US-060 (écran Plan, Lot B) est **indépendante de ce séquencement** : elle est livrable avant,
pendant ou après, son CA8 prévoyant la cascade de dégradés `recalé → conseillé → neutre`.

## 9. Risques

| Risque | Niveau | Traitement |
|---|---|---|
| **Source du référentiel** — les calendriers de semis du commerce sont des œuvres protégées ; les réutiliser tels quels n'est probablement pas licite | 🔴 Élevé | À trancher **avant** de démarrer US-068 : identifier une source réutilisable (licence ouverte), ou saisir à la main les ~30 cultures réellement suivies. C'est le principal aléa de chiffrage de l'épic |
| **Couverture du pré-remplissage** — une culture non couverte tombe en mode dégradé | 🟡 Moyen | Assumé et spécifié (US-068 / CA13). Le bot permet de compléter au fil de l'eau (CA10) |
| **Le CA3 d'US-069 alourdit la saisie vocale** — demander le contexte à chaque semis casserait la fluidité | 🟡 Moyen | Spécifié : proposition en un seul geste de confirmation, sinon enregistrement sans contexte et correction ultérieure |
| **Évolution d'un composant partagé** — US-070 modifie `MonthStrip`, utilisé par plusieurs écrans | 🟢 Faible | Ajout d'un état et paramétrage du mois mis en évidence : rétrocompatible, tous les usages en héritent |
| **Migrations concurrentes** — US-067 et US-068 touchent `culture_config` | 🟢 Faible | Séquencer les deux fichiers de migration si les US sont menées en parallèle |

## 10. Definition of Done de l'épic

- [ ] Les trois US sont livrées, leurs CA cochés et leurs tests passants.
- [ ] Le référentiel est pré-rempli pour **toutes les cultures réellement présentes** dans le
      potager de production, sans aucune culture fantôme créée.
- [ ] Le jardinier peut corriger fenêtres, durées et contexte de semis **depuis le bot**, sans
      livraison ni intervention en base.
- [ ] L'écran Plan affiche la frise recalée pour au moins une culture réelle du potager, avec sa
      durée restante, et le mode dégradé est vérifié sur une culture sans référentiel.
- [ ] Aucune régression sur le calcul de stock, l'écran Stocks, l'écran Statistiques ni les
      statistiques du bot.
- [ ] Aucune date ni durée inventée nulle part : toute absence de donnée se lit comme telle.

## 11. À faire au démarrage de l'épic

- Trancher la **source du référentiel** (risque 🔴 ci-dessus) — c'est le préalable à US-068.
- Ajouter `ÉPIC 5 — Calendrier cultural` à la liste des épics définis de
  `.github/agents/Personna PO.agent.md`, pour que le Milestone GitHub soit assigné
  automatiquement aux prochaines US du périmètre.
- Référencer ce document dans `docs/00_INDEX_NAVIGATION.md`.
- Positionner US-068, US-069 et US-070 en `Todo` sur le kanban (`python tools/us_tracker.py`).
- Supprimer `backlog/US_Distinguer_semis_pepiniere_pleine_terre.md`, remplacée par US-069.
