**ID :** US-332
**Titre :** Créer, rendre inactive ou supprimer une parcelle avec Gaston
**Épic :** ÉPIC 19 — Plan du potager sur vue du dessus *(numéro à valider)*

**Story :**
En tant que jardinier
Je veux créer une parcelle en la posant sur le plan, et retirer une parcelle sans perdre son historique, toujours après une confirmation de Gaston
Afin de faire évoluer mon potager sans risquer d'effacer par erreur des années de rotation

**Contexte fonctionnel :**
Maquette de référence : `Plan - Pistes.html`, « Rendre inactive ou supprimer… ouvre Gaston » et éditeur (« Poser une forme nouvelle ouvre Gaston : la parcelle n'est créée qu'après confirmation »). Le modèle a déjà le drapeau `actif` d'une parcelle.

**Règles :**

| # | Règle |
|---|---|
| R1 | **Créer** : poser une forme nouvelle dans l'éditeur (US-333) ouvre Gaston avec « Créer une planche de 3,5 × 3 m, rangs dans la longueur, à l'endroit posé ». Carte : nouvelle parcelle (nom proposé « Planche 9 », dimensions, superficie), rangs (sens, nombre à préciser), position. Rien n'est créé avant « Confirmer » |
| R2 | **Rendre inactive ou supprimer…** ouvre Gaston, qui **vérifie les cultures en place et l'historique** |
| R3 | Parcelle avec cultures ou historique : Gaston propose de la **rendre inactive**, pas de la supprimer. Carte : ⏸ Rendre inactive (reste sur le plan, grisée), 🌱 cultures en place (à terminer ou déplacer ensuite), 📚 historique et rotation conservés |
| R4 | La **suppression** n'est proposée que pour une parcelle **sans culture ni historique** (créée par erreur) |
| R5 | Une parcelle inactive reste sur le plan, **grisée**, avec son historique ; elle peut être réactivée par Gaston |
| R6 | Une parcelle pépinière : la vérification porte sur ses **lots** |

**Critères d'acceptance :**
- [ ] CA1 : Les trois intentions — créer, rendre inactive, supprimer — sont comprises du compagnon dans la PWA **et** dans Telegram, avec leur carte de confirmation
- [ ] CA2 : Créer une parcelle depuis l'éditeur enregistre sa géométrie (US-326) en même temps que la parcelle ; son nom proposé est unique dans le potager et modifiable sur la carte
- [ ] CA3 : Pour une parcelle avec cultures ou historique, la suppression n'est jamais proposée ; demandée explicitement, Gaston explique pourquoi et propose l'inactivation
- [ ] CA4 : Une parcelle inactive est exclue des listes de choix de parcelle pour un nouveau geste, mais reste lisible dans l'historique, la rotation et le plan (grisée)
- [ ] CA5 : La suppression d'une parcelle vide est réelle et respecte le scoping par potager et la RLS
- [ ] CA6 : Réservé à un membre éditeur ; un lecteur ne voit pas le bouton
- [ ] CA7 : La fiche d'aide des commandes de parcelle (`/parcelle`) et le guide sont mis à jour, puis le corpus ingéré ; corpus vert
- [ ] CA type : Le rendu correspond visuellement à la maquette de référence en desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (compagnon)
- Migration BDD requise : non (`actif` existe)
- Dépendances : **US-323** (contexte de Gaston), **US-326** (géométrie) ; US-333 pour la création depuis l'éditeur ; US-009 (suppression avec réaffectation, livrée) à confronter
- Modèle / effort conseillé : **Opus 5.5, `high`** — nouvelles intentions du compagnon et suppression de données

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Rendre inactive une parcelle qui a vécu
  Given la planche centrale a 7 cultures en place et un historique
  When je touche "Rendre inactive ou supprimer…"
  Then Gaston propose de la rendre inactive, pas de la supprimer
  When je confirme
  Then elle reste sur le plan, grisée, avec son historique

Scénario: Supprimer une parcelle créée par erreur
  Given la "Planche 9" n'a ni culture ni historique
  When je demande à Gaston de la supprimer
  Then il propose la suppression
  And après confirmation elle disparaît du plan

Scénario: Créer une parcelle en la posant
  Given je pose une planche de 3,5 × 3 m dans l'éditeur
  Then Gaston propose "Planche 9 · 3,5 × 3 m · 10,5 m²"
  And la parcelle n'existe qu'après "Confirmer"
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `bot`, `compagnon`
