**ID :** US-168  
**Titre :** Unifier le référentiel d'actions et normaliser les unités à l'écriture  
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant que jardinier
Je veux que tous mes gestes soient reconnus et que mes quantités soient comptées dans une seule unité
Afin que les réponses chiffrées ne soient ni fausses, ni muettes sur des saisies que j'ai pourtant dictées

**Critères d'acceptance :**

*Le référentiel d'actions*
- [ ] CA1 : Un seul référentiel fait foi. L'autre en dérive par construction ou disparaît — il n'existe plus deux listes tenues à la main. La forme retenue rend le pipeline entrée → sortie explicite : un vocabulaire d'entrée et un vocabulaire de sortie, documentés comme tels, et non deux listes qu'on croit jumelles
- [ ] CA2 : `binage` et `eclaircie` deviennent des `type_action` canoniques, présents dans les deux vocabulaires. Présents dans un seul, ils restent inatteignables : côté sortie seule, la validation les rejette avant ; côté entrée seule, la normalisation les laisse passer sans les reconnaître
- [ ] CA3 : Un test de cohérence échoue si une valeur canonique d'un vocabulaire est absente de l'autre. C'est ce test, et non la vigilance, qui empêche la divergence de revenir
- [ ] CA4 : Le sort du repli passant de la normalisation d'action est tranché et écrit. Le conserver rend le système tolérant mais laisse entrer des valeurs hors référentiel ; le supprimer rend le système strict mais aveugle aux gestes manquants — c'est lui qui a révélé `binage`. Quel que soit le choix, une action inconnue doit être visible (journal ou métrique), jamais silencieuse

*Les unités*
- [ ] CA5 : `plants` est l'unité canonique de dénombrement ; les 6 lignes en `pied` / `pieds` sont backfillées
- [ ] CA6 : La normalisation d'unité est appliquée à l'ÉCRITURE, pas seulement à la lecture. Une normalisation de lecture laisse la base sale et oblige chaque nouveau consommateur à la refaire — l'Épic 5 lira ces mêmes lignes
- [ ] CA7 : Hors périmètre, explicitement : aucune table `unites`, aucune conversion, aucune unité par défaut par culture, aucune cardinalité. Le périmètre se limite à une décision écrite, une normalisation à l'écriture et un backfill de 6 lignes

*Migration et vérification*
- [ ] CA8 : Migration séparée et idempotente (`IF NOT EXISTS`), rollback documenté, conforme à l'invariant « aucune migration ne rouvre une table modifiée par une autre US en vol »
- [ ] CA9 : Un regroupement par unité sur les 215 saisies de production ne produit plus de doublon sémantique
- [ ] CA10 : Les gabarits d'US-096 rendent le bon chiffre, vérifié sur les cas nommés et non sur le seul regroupement : « quel est mon stock de thym ? » répond 2, et l'unité affichée est la même pour le thym et pour la menthe. US-096 étant livrée, c'est sa sortie qui fait foi, pas la requête intermédiaire
- [ ] CA11 : Le journal « [US-037 CA2] Unités incompatibles » ne se déclenche plus sur `pied` / `pieds` / `plants`. Tant qu'il se déclenche, une quantité est exclue d'un total sans que le jardinier en soit informé
- [ ] CA12 : Une saisie dictant `binage` ou `eclaircie` est enregistrée bout en bout, du message au `type_action` en base — le test traverse la validation ET la normalisation, faute de quoi il ne prouve rien
- [ ] CA13 : Le supplément temporaire des gestes hors référentiel introduit dans le routeur de questions disparaît, ses entrées versées au référentiel unique. Il avait été déclaré provisoire ; cette US est l'échéance

**Notes fonctionnelles :**

- Zone fonctionnelle concernée : enregistrement (normalisation à l'écriture) + analyse (justesse des réponses chiffrées)
- Migration BDD requise : **oui** — backfill des 6 lignes en `pied` / `pieds` vers `plants`, migration séparée et idempotente
- Dépendances :
  - Corrige **US-096** (gabarits sur agrégats SQL, livrée le 26/08/2026) — `unite` et `type_action` sont ses clés d'agrégation
  - Suit l'**Action 0** (rejeux de corpus), dont elle reprend trois constats mesurés
  - Précède **US-094** (parseur déterministe)
- Source : insertion 1 de la vague 2 / piste A (`docs/decisions-prerequis-vague2-piste-a.md` §3)

*Nature de l'US — à lire avant tout découpage*

Le document de décisions présentait cette US comme un prérequis d'US-096, à faire avant pour éviter de réécrire les gabarits. Cet argument est caduc : US-096 a été livrée le 26/08/2026 (9 familles, 93 tests) et le coût que l'insertion devait éviter est engagé. Ce n'est donc plus un prérequis à ordonnancer mais un **correctif de justesse sur du code livré**, ce qui relève sa priorité au lieu de l'abaisser.

*Les réponses fausses, mesurées le 27/08/2026*

| Question posée au gabarit | Réponse rendue | Réalité en base |
|---|---|---|
| « quel est mon stock de thym ? » | « 1 plants » | 2 pieds plantés — 1 en `plants`, 1 en `pied` |
| « quel est mon stock de menthe ? » | « 1 pied » | l'unité affichée change d'une culture à l'autre |

Le garde-fou d'US-037 / CA2 ne ment pas, il sous-déclare en silence : seule l'unité majoritaire est comptée, les autres sont exclues du total — ni additionnées, ni converties, sans que le jardinier en soit averti.

*Les unités — remesurées sur la production (potager 1, 215 saisies hors bulletins `[AUTO-METEO]`)*

| Unité | Lignes |
|---|---:|
| `plants` | 84 |
| `g` | 43 |
| `graines` | 21 |
| `kg` | 15 |
| `pieds` | 3 |
| `pied` | 3 |

L'arbitrage `plants` / `pied(s)` porte sur **84 contre 6** — un usage dominant et six exceptions — et non sur deux usages concurrents à parts comparables (« ~42 % des saisies ») comme l'annonçait le document de décisions, établi le 25/08 sur 225 saisies.

Deux éléments du périmètre annoncé tombent : aucune unité à exposant (`m²`) n'existe en base, la translittération `²` → `2` ne corrigerait rien ; et la dépluralisation ne concerne que `pieds` → `pied`, `plants` étant déjà uniforme.

*Les actions — ce n'est pas une divergence, c'est un pipeline non documenté*

Le vocabulaire d'entrée (validation de l'action parsée) et le vocabulaire de sortie (normalisation) comptent 16 entrées chacun, 14 communes. Ce n'est pas une incohérence : `fertilisation` entre et ressort en `amendement`, `repiquage` entre et ressort en `plantation`. Les deux vocabulaires n'ont aucune raison d'être identiques. Le défaut est que personne ne l'a écrit, d'où trois conséquences mesurées :

- Une saisie hors vocabulaire d'entrée est **silencieusement jetée** : un avertissement est journalisé, l'item retiré, l'évènement jamais enregistré. Ajouter un geste au seul vocabulaire de sortie ne sert donc à rien — la saisie n'atteint jamais la normalisation.
- La normalisation a un **repli passant** : une action inconnue est stockée telle quelle. C'est ainsi que `binage` (1 ligne) et `eclaircie` (1 ligne) figurent en base sans appartenir à aucun des deux vocabulaires, par un chemin d'écriture qui ne valide pas.
- La valeur réellement stockée est **`eclaircie`, pas `eclaircissage`**. Écrire le référentiel sur `eclaircissage`, comme le propose le document de décisions, laisserait la ligne existante orpheline.

*Ce qui reste hors de cette US, et pourquoi*

**La fusion poids + dénombrement sur les récoltes.** Sur une culture végétative la récolte est destructive : arracher 15 betteraves doit retirer 15 pieds du stock (US-002). Le poids ne sait pas le faire, d'où une seconde ligne portant le dénombrement. 7 dictées produisent ainsi deux évènements, et US-096 répond aujourd'hui « Tu as récolté 3.15 kg **et** 50 plants de betterave cette saison (8 récoltes) » — alors qu'il y a eu 4 récoltes et que les 50 plants *sont* les 3,15 kg. Réunir les deux informations sur une seule ligne est le bon geste mais touche le schéma, le parseur, le calcul de stock, les gabarits, l'API et l'affichage : c'est une US de 5 à 8 points. Correctif d'attente retenu : le gabarit de total de récolte déduplique sur le texte original — identique dans chaque paire — pour rendre « 3,15 kg (50 pieds) · 4 récoltes ». La phrase cesse d'être fausse sans attendre.

**Le marqueur « en godet » du classifieur de questions.** Il classe encore « mes plants de poireaux en godet sont tombés au ras de la terre » en question de données : 1 question de savoir sur 44. Arbitrage US-093, à traiter au même endroit mais pas au titre de cette US.

*Point ouvert, non vérifié*

Dans la copie dev, `culture_config` est vide et 46 des 69 récoltes n'ont pas de `type_organe_recolte`. Or ce champ décide si une récolte est destructive ou continue, donc si le dénombrement est nécessaire. Ce constat n'est pas transposable en production : seules `evenements` et `parcelles` y ont été importées. À vérifier avant d'ouvrir l'US de fusion, dont il conditionne le périmètre.

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: une quantité saisie dans une unité minoritaire n'est plus exclue du total
  Given j'ai planté 1 thym enregistré avec l'unité "plants"
    And j'ai planté 1 thym enregistré avec l'unité "pied"
  When je demande "quel est mon stock de thym ?"
  Then la réponse annonce 2 pieds de thym
    And aucun avertissement "[US-037 CA2] Unités incompatibles" n'est journalisé
    And l'unité affichée est la même que pour la menthe

Scénario: un geste hors vocabulaire d'entrée n'est plus jeté en silence
  Given "binage" et "eclaircie" appartiennent au référentiel d'actions unique
  When je dicte "j'ai fait un binage sur la parcelle 3"
  Then l'évènement est enregistré avec le type_action "binage"
    And la saisie a traversé la validation puis la normalisation

Scénario: la divergence entre vocabulaires ne peut plus revenir
  Given une valeur canonique est ajoutée à un seul des deux vocabulaires
  When la suite de tests est exécutée
  Then le test de cohérence du référentiel échoue
```

**Labels GitHub :** `us`, `epic-6`, `enregistrement`, `analyse`, `correctif`
