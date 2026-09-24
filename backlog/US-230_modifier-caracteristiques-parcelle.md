**ID :** US-230
**Titre :** Modifier les caractéristiques d'une parcelle depuis sa fiche
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux corriger les caractéristiques d'une parcelle directement sur sa fiche — sa longueur, son nombre de rangs, son type de sol, son abri, son statut
Afin de compléter en trente secondes ce que l'application me signale comme manquant, sans avoir à formuler une phrase pour chaque champ

**Contexte fonctionnel :**
Maquette de référence : `Parcelle - Fiche.html` (projet Claude Design `10f5afa7-58f8-4eb0-8dae-ca5834dfff59`), carte « Caractéristiques » en mode édition (bascule `.edit`).

US-229 affiche la carte et **nomme** ce qui manque. Elle s'arrête là : le seul chemin de correction reste la phrase dite au compagnon, une phrase par champ. Un jardinier qui découvre quatre champs vides sur une planche doit dicter quatre phrases — et la fiche est précisément l'endroit où il s'en rend compte.

Cette US rend la carte modifiable sur place : un bouton bascule, les valeurs deviennent des champs de saisie, un second appui enregistre. **La carte ne change ni de place, ni de forme, ni d'ordre** entre les deux modes — c'est le même bloc, pas un formulaire séparé ni une fenêtre modale.

⚖️ **Aucune caractéristique nouvelle, aucune migration.** L'US écrit **exactement** les colonnes qu'US-229 affiche. Elle n'ajoute aucun champ, aucune table, aucune colonne. Ce qu'elle ajoute, c'est un **chemin d'écriture web** pour des champs que le compagnon sait déjà écrire.

⚖️ **Un seul point d'écriture.** Les bornes du domaine — 1 à 99 rangs (US-197), 0,5 à 200 m de longueur (US-225), unicité du nom normalisé par potager, vocabulaire fermé de l'abri (US-181) — sont **déjà** tenues par `utils.parcelles`. L'API ne les réécrit pas : elle les appelle. Les attributs de saisie de la maquette (`min`, `max`, `step`, `maxlength`) sont un confort de frappe, **jamais** la règle : un navigateur qui les ignore doit se heurter au même refus que le compagnon.

⚖️ **Ce qui n'est pas modifiable ici.** La **largeur** ne se saisit pas : elle se déduit, et le mode édition le dit en clair à la place du champ (« Calculée : superficie ÷ longueur »). L'**ordre** d'affichage des parcelles se règle dans la Vue plan (US-202), pas ici.

**Règles de rendu :**

| # | Règle |
|---|---|
| E1 | « Modifier » bascule la carte en édition **sur place** : chaque valeur devient un champ, le bouton devient « Enregistrer » en teinte primaire, un « Annuler » apparaît à côté. Ni fenêtre modale, ni page dédiée, ni déplacement de la carte |
| E2 | Types de saisie : **Nom** texte ; **Superficie**, **Longueur**, **Nombre de rangs** numériques ; **Exposition**, **Type de sol**, **Abri** listes fermées ; **Paillage**, **Pépinière**, **Statut** en oui / non — chaque liste portant un choix « Non renseigné » qui **remet la valeur à `NULL`** (distinct de « Non » et de « Aucun », US-181) |
| E3 | La **largeur** n'est pas saisissable : sa case affiche en édition « Calculée : superficie ÷ longueur », en teinte secondaire. Elle se recalcule à l'enregistrement |
| E4 | **Enregistrement en une fois** : un seul appel porte tous les champs modifiés. Rien n'est écrit champ par champ à la volée, et un champ non touché n'est pas transmis |
| E5 | **Refus d'une valeur** : le message vient du domaine et nomme la borne (« Le nombre de rangs se déclare entre 1 et 99 »), il se place **sous le champ fautif**, les autres modifications sont conservées à l'écran, et la carte reste en édition |
| E6 | **Confirmation** : au retour, la carte repasse en lecture, les états manquants résolus disparaissent, la pastille de l'index (US-229 / C8) se met à jour, et un message bref confirme ce qui a changé |
| E7 | **Renommer** passe par le renommage existant (US-006) : le nom normalisé reste unique par potager, et un nom déjà pris est refusé avec le nom en conflit nommé. Les événements rattachés suivent la parcelle |
| E8 | **Basculer une parcelle en pépinière**, ou l'inverse, est signalé avant enregistrement : cela change son traitement dans le calcul des semis en pleine terre et retire ses rangs de la fiche (US-229 / C9). Une phrase, pas une fenêtre de confirmation |
| E9 | **Passer une parcelle en « Inactive »** reprend le retrait existant (US-009, `actif=False`) et sa réaffectation des gestes ; la conséquence est annoncée avant enregistrement |
| E10 | **Membre en lecture seule** : le bouton « Modifier » n'est pas rendu. Pas grisé, pas présent : la carte est celle d'US-229 |
| E11 | **375 px** : les champs s'empilent en une colonne, « Enregistrer » et « Annuler » restent atteignables sans faire défiler la carte entière, cible d'appui de 44 px |

**Critères d'acceptance :**

*Écriture*
- [ ] CA1 : Une route d'écriture sur une parcelle est exposée par l'API, réservée au rôle qui crée déjà une parcelle (`POST /parcelles`, US-058) ; elle accepte les champs de US-229 / C2 sauf la largeur, et **rejette tout autre champ** en le nommant
- [ ] CA2 : Elle délègue à `utils.parcelles` — `update_parcelle` pour les champs qu'il couvre déjà, ses fonctions existantes pour le renommage (US-006) et le retrait (US-009). Les champs qu'aucune fonction ne couvre encore (`type_sol`, `actif`) y sont **ajoutés au même point d'écriture**, avec leurs bornes, et non traités dans le handler
- [ ] CA3 : Aucune borne, aucune normalisation de nom, aucun vocabulaire fermé n'est réécrit dans `app/api/` ni dans le frontend. Aucun `db.query` hors `app/services/` (test US-041)
- [ ] CA4 : **Aucune migration n'est livrée**, aucune colonne ajoutée
- [ ] CA5 : Une valeur hors borne envoyée **sans passer par le formulaire** (attributs HTML contournés) est refusée par l'API avec le même message que le compagnon — un test le vérifie pour les rangs, la longueur et l'abri
- [ ] CA6 : Mettre un champ à « Non renseigné » écrit bien `NULL`, et non une chaîne vide ni `false` — vérifié pour `type_sol`, `abri`, `paillage`, `nb_rangs`, `longueur_m`

*Rendu et interaction*
- [ ] CA7 : Les règles E1 à E11 sont appliquées
- [ ] CA8 : « Annuler » restaure les valeurs d'origine sans appel réseau ; quitter l'onglet en cours d'édition demande confirmation plutôt que de perdre la saisie silencieusement
- [ ] CA9 : Après enregistrement, la Vue plan et l'en-tête de la fiche reflètent la nouvelle valeur **sans rechargement complet** : changer le nombre de rangs change immédiatement « N rangs occupés sur M » (US-222)
- [ ] CA10 : Le rendu correspond visuellement à la maquette `Parcelle - Fiche.html`, modes lecture et édition, à 375 px / 768 px / desktop

*Cohérence avec le compagnon*
- [ ] CA11 : Une même correction faite par le web et par le compagnon produit **le même état en base et le même message de refus** — un test compare les deux chemins pour le nombre de rangs et la longueur
- [ ] CA12 : Une modification faite depuis le web est visible dans les réponses du compagnon sans délai ni cache à invalider à la main

*États*
- [ ] CA13 : Échec réseau pendant l'enregistrement : la saisie est conservée, l'erreur est affichée, une relance est proposée, et rien n'est écrit à moitié
- [ ] CA14 : Deux modifications concurrentes sur la même parcelle : la seconde n'écrase pas silencieusement des champs qu'elle n'a pas touchés (E4 le garantit par construction) — un test le vérifie

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation + enregistrement (PWA, onglet Parcelles) et API
- Migration BDD requise : **non**
- Dépendances : US-229 (la carte en lecture), US-006 (renommage), US-009 (retrait / statut), US-058 (création et rôle), US-181 (abri, paillage), US-197 (bornes des rangs), US-225 (bornes de la longueur)
- À livrer **avant** la refonte de l'écran Cultures (US-205 à US-207)
- Corpus : `data/connaissance/doc_app/parcelles-et-plan.md` — le web devient un second chemin d'écriture des caractéristiques, à dire dans la même livraison (US-099 / CA9)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Given la parcelle "planche_centrale" n'a pas de type de sol et déclare 7 rangs
When j'appuie sur "Modifier", je choisis "Argileux" et je passe le nombre de rangs à 8
And j'appuie sur "Enregistrer"
Then la carte repasse en lecture avec "Argileux" et "8"
And l'état manquant du type de sol a disparu, ainsi que la pastille de l'index
And l'en-tête dit "3 rangs occupés sur 8"

Given je suis en mode édition sur "planche_centrale"
When je saisis 150 dans le nombre de rangs et j'enregistre
Then le message "Le nombre de rangs se déclare entre 1 et 99" s'affiche sous ce champ
And mes autres modifications sont toujours à l'écran
And rien n'a été écrit en base

Given je suis membre en lecture seule du potager
When j'ouvre la fiche de "planche_centrale"
Then le bouton "Modifier" n'est pas affiché
```

**Labels GitHub :** `us`, `sprint-X`, `frontend`, `api`, `parcelles`

---

## ⚠️ AMENDEMENT du 24/09/2026 — la fiche parcelle ne porte plus le détail des cultures

Origine : maquette `Parcelle - Fiche.html`, détaillée dans l'amendement de
**US-222**, qui fait foi. La fiche d'une parcelle porte désormais un simple
**bandeau d'occupation** (« N rangs occupés sur M », les noms des cultures) et
un bouton « Voir les cultures dans le Plan → » : plus aucune tuile de culture,
plus aucun rang libre actionnable.

- L'US elle-même est **inchangée** : elle ne portait que la carte
  « Caractéristiques », que l'amendement conserve entièrement.
- Une seule adhérence tombe : **CA9** se vérifie désormais sur le **bandeau
  d'occupation** (« 3 rangs occupés sur 8 ») et non sur des tuiles de rang.

### Écarts assumés à la livraison du 24/09/2026

- **E2, exposition** : la colonne `parcelles.exposition` est un texte libre
  depuis l'origine, et des potagers en production portent des valeurs hors des
  cinq propositions de la maquette. La liste est donc servie par le domaine
  comme une **proposition** (`ferme: false`), et la valeur déjà enregistrée y
  reste offerte : une liste d'aide ne doit pas faire disparaître une déclaration
  du jardinier. Fermer ce vocabulaire demanderait sa propre US, avec la reprise
  des valeurs existantes.
- **E8** : la bascule pépinière est annoncée par une phrase avant
  enregistrement, comme demandé ; le retrait des rangs de la fiche qu'elle
  mentionne suit l'amendement ci-dessus.
