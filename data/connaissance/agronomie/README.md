# Corpus `agronomie` — ce que le potager peut avoir, dit avec les mots du jardinier

Deuxième contenu versé dans le socle d'US-098, après `doc_app/` (US-099). Il
répond à la question qui amène réellement un jardinier à écrire à l'assistant :
**« qu'est-ce qu'ils ont ? »** — et à celle qui suit immédiatement, **« qu'est-ce
que je fais ? »**.

Le format est celui d'US-098 — en-tête, `## ` par idée, ligne « On parle aussi
de » dans **chaque** section : voir `../README.md`, et
`docs/RUNBOOK_ALIMENTATION_SOCLE_CONNAISSANCE.md` pour la procédure complète.

```bash
python tools/controler_corpus_agronomie.py --detail      # la relecture, exécutable
python tools/ingerer_connaissance.py --strict --dry-run
python tools/ingerer_connaissance.py
python tools/mesurer_corpus_savoir.py \
    --corpus tests/corpus/us140_questions_diagnostic.csv \
    --racine data/connaissance/agronomie --detail          # classement (CA11)
```

## Le périmètre : dix cultures, pas trente

Les dix cultures les plus présentes dans les données réelles, établies par une
mesure et non par intuition (`docs/VAGUE0_EPIC6_DECISIONS_ET_EXTRACTIONS.md`
§3.1) : **tomate, haricot, courgette, chou, carotte, concombre, cornichon,
poivron, ail, blette**.

L'arbitrage est celui de l'US : une fiche complète représente plusieurs heures
de travail ; dix cultures réellement présentes produisent un assistant utile,
trente produisent un chantier qui n'aboutit pas. La couverture s'étend ensuite
au rythme des questions restées sans réponse (`GET /admin/savoir/lacunes`),
jamais au rythme de l'envie d'exhaustivité.

> ⚠️ **Les rangs 9 et 10 ne sont pas établis par la mesure.** Six cultures sont à
> égalité sur la base de développement — ail, blette, fève, petit pois, poireau,
> épinard — et deux seulement entrent, départagées par ordre alphabétique. La
> mesure est **à rejouer sur la production** ; si elle déplace le classement,
> c'est une fiche à écrire et une à retirer, pas une refonte.

> ⚠️ **`blette` côté jardinier, `bette` côté référentiel.** `culture_config`
> porte « bette » (semé par `migration_v6.sql`), et les fiches s'y rattachent
> sous ce nom : la culture est une **référence**, pas un libellé (règle ⑤ de
> `../README.md`). Le mot du jardinier — blette, poirée — est porté par la ligne
> « On parle aussi de » de chaque section, qui est ce que la recherche
> interroge. Les fichiers gardent le nom `blette-*.md`, celui qu'on cherche
> dans le dossier.

## Le plan imposé — deux fiches par culture, et pas une de plus

CA13 (c) : *« plan de fiche imposé et identique pour toutes, faute de quoi le
découpage en fragments d'US-098 devient irrégulier »*. Le thème est porté par le
**nom du fichier**, `<culture>-<thème>.md`, pour que le plan se lise sur le
dossier sans ouvrir une fiche.

| Fiche | Ce qu'elle porte | Exigence |
|---|---|---|
| `<culture>-problemes.md` | maladies, ravageurs et troubles, décrits par le **symptôme observable** | CA5, CA6, CA9 |
| `<culture>-conduite-recolte.md` | gestes courants d'entretien, de récolte et de conservation | CA5 |

Chaque section porte, sans exception, ses trois lignes de métadonnée :

```markdown
**Intention :** diagnostic
**Organes concernés :** feuille, fruit
**On parle aussi de :** cul noir ; tomate pourrie dessous ; nécrose apicale ; manque de calcium
```

Aucune ne s'affiche : deux d'entre elles sont indexées **au poids du titre**, et
ce sont elles qui décident si la fiche est retrouvée.

## Ce qu'une fiche d'agronomie ne contient jamais

Ces refus ne sont pas des recommandations de style : `tools/controler_corpus_agronomie.py`
les oppose au corpus, et le déploiement l'exécute avant l'ingestion. Une fiche
qui en contient un n'entre pas à l'index.

| Refusé | Pourquoi | Critère |
|---|---|---|
| un chiffre, une unité, une durée, un mois | dates et fenêtres appartiennent au référentiel calendrier (US-068), déclinées par zone climatique ; espacements et profondeurs au référentiel structuré (US-161). Dupliqués ici, ils forment une seconde vérité, fausse pour la moitié des jardiniers | CA7, CA13 (a) |
| une association de cultures, une règle de rotation | ce sont des **arêtes**, portées par `association_culture` et le calcul de rotation (US-163) ; écrites dans une fiche, elles deviennent invisibles du calcul et ne peuvent pas déclencher l'avertissement d'US-167. **Expliquer le mécanisme reste autorisé** | CA7bis |
| un dosage, un produit de traitement | « l'assistant n'est pas un conseiller en traitement » — c'est une limite de responsabilité | CA10 |
| une section de diagnostic sans tournure d'hypothèse | « l'excès d'eau est plus probable qu'une carence », jamais « tes courgettes ont trop d'eau » | CA9 |
| une licence absente ou hors socle | le corpus doit rester propriétaire ; une clause de partage à l'identique le contaminerait irréversiblement | CA2, CA3 |

## Licence et sources

Toutes les fiches sont en **rédaction interne**, écrites de zéro, sous licence
`proprietaire`. Aucun paragraphe n'est repris d'une source tierce. Les
organismes consultés **en lecture** pour la rédaction sont cités en pied de
chaque fiche — Ephytia (INRAE), USDA National Agricultural Library — ce qui est
une trace de travail, pas une reprise de contenu.

La chaîne affichée au jardinier (`source:`) n'est pas rédigée fiche par fiche :
c'est l'`attribution` du registre `app/services/referentiel_sources.py`, seul
endroit où une licence à attribution obligatoire déclare la mention exacte
qu'elle exige. Une fiche qui afficherait autre chose est refusée.

## Niveau de confiance : `a-valider`, sans exception

CA13 (b) : le passage à `verifie` n'a lieu qu'**après relecture par une personne
qui jardine**, fiche par fiche. Ce n'est pas une formalité — c'est un
comportement :

* une fiche `verifie` est servie **mot pour mot**, à zéro jeton ;
* une fiche `a-valider` ne l'est **jamais** : elle descend en contexte vers
  l'étage de raisonnement, qui rédige, et la réponse porte alors une **réserve
  explicite** disant au jardinier que la fiche n'a pas été relue (CA8).

Promouvoir une fiche en `verifie` sans l'avoir relue phrase par phrase revient
donc à servir un texte non vérifié comme faisant autorité, et à supprimer la
réserve qui prévenait.

## Ce que la mesure a donné (CA11, CA12)

66 questions écrites avec les mots d'un jardinier
(`tests/corpus/us140_questions_diagnostic.csv`), dont les **19 entrées du
périmètre v1 de `docs/CORPUS_QUESTIONS_DIAGNOSTIC_CA11.md`, reprises mot pour
mot** — ce corpus-là a été écrit le 25/08/2026, avant les fiches, ce qui est la
seule garantie contre une mesure auto-réalisatrice.

**Résultat sur le repli SQLite : 66/66 dans les trois premiers résultats, dont
64 en tête.** Cible du CA11 : 80 %.

**Conséquence pour le CA12 :** au-dessus du seuil, la question de la **recherche
sémantique** reste fermée. Enrichir le vocabulaire des sections coûte quelques
minutes par fiche et rend le moteur vectoriel inutile à ce stade ; le sujet ne
se rouvre que si une mesure ultérieure repasse sous le seuil malgré ce travail.

> ⚠️ Cette mesure vaut pour le repli SQLite. Celle qui conditionne l'activation
> en production se rejoue contre PostgreSQL, avec `RAG_SEUIL_CONFIANCE`
> réétalonné — voir le §5 du runbook, qui donne l'ordre exact.

## Ce qui rend une fiche fausse — table de relecture

Même règle que pour `doc_app/` : **une évolution qui rend une fiche fausse
impose sa mise à jour dans la même livraison.** La colonne de droite se lit à
l'envers : *j'observe ceci au jardin, donc je relis cette fiche.* Ici, ce qui
périme une fiche n'est pas un changement de code mais un **retour de terrain** —
une observation qui contredit le texte, ou une relecture par une personne qui
jardine.

| Fiche | À relire dès que… |
|---|---|
| `tomate-problemes.md` | un diagnostic de mildiou, de cul noir, d'enroulement, de pucerons ou d'éclatement est démenti par l'observation, ou le comportement des semis change |
| `tomate-conduite-recolte.md` | le palissage, l'ébourgeonnage, la conduite de l'arrosage ou les repères de maturité sont contredits sur le terrain |
| `haricot-problemes.md` | la levée, les taches du feuillage, les pucerons ou la coulure des fleurs se comportent autrement que décrit |
| `haricot-conduite-recolte.md` | le guidage des tiges, la conduite de l'arrosage ou les repères de gousse tendre sont contredits |
| `courgette-problemes.md` | l'oïdium, l'avortement des jeunes fruits, les limaces ou l'excès d'eau se manifestent autrement |
| `courgette-conduite-recolte.md` | l'arrosage au collet, la pollinisation manuelle ou les repères de récolte sont contredits |
| `chou-problemes.md` | la piéride, la hernie, les dépôts du feuillage ou les altises se manifestent autrement |
| `chou-conduite-recolte.md` | le buttage après le vent, l'effeuillage bas ou les repères de pomme ferme sont contredits |
| `carotte-problemes.md` | les racines fourchues, fendues, minées, la levée ou le jaunissement se comportent autrement |
| `carotte-conduite-recolte.md` | l'éclaircissage, le buttage des épaules, l'arrachage ou la préparation au stockage sont contredits |
| `concombre-problemes.md` | l'amertume, la mosaïque, l'oïdium ou l'avortement des jeunes fruits se manifestent autrement |
| `concombre-conduite-recolte.md` | le palissage, la conduite de l'arrosage ou les repères de récolte sont contredits |
| `cornichon-problemes.md` | l'amertume liée à la fréquence de récolte, la mosaïque, l'oïdium ou les fruits difformes se comportent autrement |
| `cornichon-conduite-recolte.md` | la fréquence de récolte, le palissage ou la conservation avant préparation sont contredits |
| `poivron-problemes.md` | la coulure des fleurs, la nécrose apicale, les coups de soleil ou les ravageurs du feuillage se manifestent autrement |
| `poivron-conduite-recolte.md` | le tuteurage à la fourche, la conduite sous abri ou les repères de récolte sont contredits |
| `ail-problemes.md` | la rouille, la pourriture des caïeux, le jaunissement précoce ou la hampe florale se comportent autrement |
| `ail-conduite-recolte.md` | le choix de l'emplacement, le désherbage, les repères d'arrachage ou le séchage sont contredits |
| `blette-problemes.md` | les mineuses, les taches du feuillage, la montaison ou les limaces se manifestent autrement |
| `blette-conduite-recolte.md` | la récolte feuille à feuille, l'arrosage, l'éclaircissage ou la conservation sont contredits |

Toute fiche ajoutée ici entre dans cette table **dans le même commit** :
`tests/test_us140_corpus_agronomique.py` échoue tant que ce n'est pas fait.
