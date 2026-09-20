**ID :** US-217
**Titre :** Proposer où mettre en terre les plants d'un lot
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux, quand mes godets sont prêts, que l'application me montre les planches où il reste des rangs libres et si leur exposition convient à la culture
Afin de décider où planter sans aller et venir entre la Pépinière et le Plan

**Contexte fonctionnel :**
C'est le lien que les wireframes tracent de la Pépinière vers le Plan (v1 § 4 : « Pépinière → Plan : « mettre en terre » ») : « Le panneau du lot propose les rangs libres du Plan (planche-nord entière, rangs 4–5 de planche-ombre), exposition comparée à celle du référentiel. « Mettre en terre » saisit l'événement de plantation avec parcelle et rang pré-remplis. »

La v2 y ajoutait un calcul de place (« 40 choux à 40 × 40 cm = 6,4 m² → il en resterait 15 en godet ») qui reposait sur la géométrie des parcelles, **reportée** par la v3. Cette US s'en tient donc aux **rangs libres**, tels que la répartition d'US-198 les compte — la même source que la Vue plan : les deux écrans ne peuvent pas dire deux choses différentes de la place qui reste.

**Critères d'acceptance :**

*Les suggestions*
- [ ] CA1 : Pour chaque lot qui a des godets disponibles, `GET /pepiniere/lots` rend ses **suggestions de mise en terre** : les parcelles non pépinières qui ont au moins un rang libre à la date de référence, avec le nombre de rangs libres (et leurs numéros, positions comprises si US-203 est livrée). Le calcul de répartition est fait **une fois** pour toute la lecture, jamais par lot
- [ ] CA2 : Chaque suggestion compare l'**exposition** de la parcelle à celle de la culture (US-161 : plein soleil, mi-ombre, ombre) : *concorde*, *diffère* (« mi-ombre, pour une culture de plein soleil »), ou *non comparable* quand l'une des deux manque ou n'est pas dans ce vocabulaire. Rien n'est supposé
- [ ] CA3 : Ordre : exposition concordante d'abord, puis le plus de rangs libres, puis l'ordre des parcelles. Les parcelles **sans nombre de rangs** viennent ensuite, marquées « rangs libres inconnus », jamais exclues ni comptées comme libres
- [ ] CA4 : Le nombre de plants qui tiendront **n'est pas calculé** et la section le dit une fois : ni espacement, ni surface (plan des épics § 9)
- [ ] CA5 : Les suggestions sont une **lecture** : aucune réservation de rang, aucune écriture

*Dans la fiche du lot*
- [ ] CA6 : La section « Où les mettre » de la fiche du lot (US-216) affiche les **trois** premières suggestions, puis « voir toutes les parcelles » ; chacune porte le nom de la parcelle, ses rangs libres et la comparaison d'exposition, écrite en mots (jamais une coche seule)
- [ ] CA7 : « **Mettre en terre ici** » prépare la plantation pré-remplie (US-196) : lot, culture, variété, parcelle, premier rang libre si les positions sont connues (US-203), godets disponibles proposés comme quantité. L'avertissement de rotation reste celui du compagnon à la confirmation (US-167)
- [ ] CA8 : Aucune parcelle avec un rang libre : la section le dit et garde « Mettre en terre » sans parcelle — le compagnon la demandera
- [ ] CA9 : Un membre en lecture seule voit les suggestions, sans bouton
- [ ] CA10 : La carte « Prêts pour le plan » de l'onglet « Aujourd'hui » (US-215) lit les mêmes rangs libres

*Définition de terminé*
- [ ] CA11 : Les fiches `pepiniere-par-lot.md` (où mettre les plants d'un lot) et `parcelles-et-plan.md` (les rangs libres servent aussi à la pépinière) sont mises à jour (US-099 / CA9)
- [ ] CA12 : Des tests couvrent : rangs libres par parcelle, exclusion des pépinières, parcelle sans nombre de rangs, les trois issues de la comparaison d'exposition, l'ordre, lot sans godet (aucune suggestion), date de référence passée, geste pré-rempli avec et sans position de rang, absence de requête par lot

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), consultation (PWA)
- Migration BDD requise : **non**
- Dépendances : **US-198** (rangs libres), **US-216** (fiche du lot), US-196 (geste pré-rempli), US-161 (exposition de la culture, livrée) ; US-203 pour le rang pré-rempli (optionnelle)
- Impact tokens : zéro
- Point de vigilance : la **rotation** n'est pas évaluée dans les suggestions en V1 ; elle l'est à la confirmation de la plantation (US-167). L'intégrer ici est une extension possible, à décider avec l'onglet Rotation du Plan
- Point de vigilance : **reproducteur vs végétatif** — sans effet sur la suggestion ; il décidera ensuite de la vie du rang (occupé récolte après récolte pour une reproductrice, libéré avec la ligne pour une végétative, US-198)
- Wireframes : v1 § 3 (panneau du lot, note « Où les mettre relie Pépinière et Plan ») ; v2 § 3 (section « Où les mettre »)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Deux planches possibles
  Given le lot 128, 40 choux frisés en godet, culture de plein soleil
  And la planche-nord, plein soleil, a 2 rangs libres
  And la planche-ombre, mi-ombre, a 2 rangs libres
  When j'ouvre la fiche du lot 128
  Then "Où les mettre" propose d'abord la planche-nord, exposition concordante
  And ensuite la planche-ombre, "mi-ombre, pour une culture de plein soleil"
  And la section précise que le nombre de plants qui tiendront n'est pas calculé

Scénario: Mettre en terre ici
  When j'appuie sur "Mettre en terre ici" sur la planche-nord
  Then mon compagnon s'ouvre sur une plantation du lot 128 dans la planche-nord, 40 plants proposés

Scénario: Parcelle sans nombre de rangs
  Given la planche-est n'a pas de nombre de rangs
  When j'ouvre la fiche du lot 128
  Then la planche-est apparaît après les parcelles aux rangs connus, "rangs libres inconnus"

Scénario: Aucun rang libre
  Given toutes les parcelles aux rangs connus sont pleines
  When j'ouvre la fiche du lot 128
  Then "Où les mettre" dit qu'aucun rang libre n'est déclaré
  And "Mettre en terre" reste proposé, la parcelle sera demandée
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `pepiniere`, `plan`
