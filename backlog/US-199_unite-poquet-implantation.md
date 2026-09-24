**ID :** US-199
**Titre :** Reconnaître le poquet et le mètre de rang comme unités d'implantation
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux pouvoir dire « semé 5 poquets de courge » ou « semé 3 mètres de carottes » et que l'application le comprenne tel quel
Afin que le Plan dessine mes courges en poquets et mes rangs de carottes à leur longueur, au lieu de tout ramener à des plants ou à des mètres carrés

**Contexte fonctionnel :**
La Vue plan V1 (wireframe v3) a trois formes, choisies par le **mode d'implantation** : trait plein pour une culture en rang (« plants, pieds, ml »), trait tramé pour un semis en surface (« m² »), trait segmenté pour une culture en poquets (« un segment = un poquet »). Ce mode se déduit de l'**unité** de la quantité (arbitrage A4, US-198 / R4).

La v2 affirmait que ces unités étaient « déjà présentes ». Elles ne le sont pas : la mesure d'US-168 sur la production ne compte que `plants`, `g`, `graines`, `kg` (et `pied(s)`, normalisés en `plants`), plus `m2` à la dictée. **Sans unité « poquets », le mode poquet ne s'affichera jamais** ; sans mètre de rang, un semis en ligne ne peut se dire qu'en graines ou en m².

Cette US ajoute les deux unités au vocabulaire normalisé à l'écriture (US-168 / CA6), à la dictée comme à la commande. Elle ne convertit rien : un poquet reste un poquet, un mètre reste un mètre.

**Critères d'acceptance :**
- [ ] CA1 : « poquet », « poquets », « trou », « touffe » (au sens de poquet, dans une phrase de semis ou de plantation) sont normalisés **à l'écriture** en `poquets`. « mètre de rang », « mètres linéaires », « mètre de ligne », « ml » sont normalisés en `ml`
- [ ] CA2 : Le parseur déterministe (US-094) et le chemin par le modèle produisent la même unité normalisée ; un test passe les mêmes phrases par les deux chemins
- [ ] CA3 : « m² », « mètres carrés », « m2 » restent `m2` ; « mètre » seul, sans « carré », dans une phrase de semis, est lu `ml`. Le corpus de dictée porte les paires qui se ressemblent (« 2 mètres de carottes » / « 2 mètres carrés de carottes »)
- [ ] CA4 : Les deux unités sont acceptées pour un **semis en pleine terre** et une **plantation** ; pour une mise en godet ou un semis en pépinière, elles sont refusées avec un message qui rappelle les unités attendues
- [ ] CA5 : **Aucune conversion** : un poquet n'est jamais compté en plants ni en graines, un mètre de rang jamais en m². Les règles de stock par unité (unité dominante d'US-037 / CA2, total de plants limité aux plants d'US-060 / CA6) les traitent comme des unités distinctes, et une quantité dans une unité minoritaire n'est pas exclue en silence (US-168 / CA11)
- [ ] CA6 : Une perte ou une récolte exprimée dans la même unité se déduit normalement (« perdu 2 poquets de courge ») ; une récolte en kg d'une culture reproductive en poquets ne touche pas au nombre de poquets
- [ ] CA7 : Le récapitulatif de confirmation du bot écrit l'unité en toutes lettres (« 5 poquets », « 3 m de rang »)
- [ ] CA8 : La PWA écrit les deux unités lisiblement partout où une quantité s'affiche (même principe que `m2` → « m² » d'US-060 / CA18)
- [ ] CA9 : Les fiches `enregistrer-un-geste.md` (quantités et unités) et `stock-plants-calcul.md` (unités qui ne se mélangent pas) ainsi que le guide utilisateur (§ 6.2 et § 6.5) sont mis à jour dans la même livraison (US-099 / CA9)
- [ ] CA10 : Des tests couvrent : chaque variante du CA1, la paire m / m², le refus en pépinière, l'absence de conversion, la déduction d'une perte, l'affichage PWA

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, enregistrement
- Migration BDD requise : **non** — normalisation à l'écriture, aucune donnée existante à reprendre (aucune ligne en poquets ni en mètres aujourd'hui)
- Dépendances : US-168 (normalisation des unités à l'écriture, livrée), US-094 (parseur déterministe, livré)
- Consommateurs : US-198 (déduction du mode d'implantation), US-200 (formes du trait), **US-227 et US-228** (le semis en ligne est le seul geste qui se dessine en **part de rang semée** plutôt qu'en places : sans l'unité `ml`, un rang de carottes reste compté en graines, ce qui donne des « places » discutables — voir US-227 / R12 et R15)
- Impact tokens : zéro sur le chemin déterministe
- Point de vigilance : **reproducteur vs végétatif**. Des courges semées en poquets sont reproductives : les récoltes en kg s'additionnent au rendement de la saison sans toucher aux poquets. Des radis semés sur 3 m de rang sont végétatifs : leur récolte en bottes ou en kg ne réduit pas les mètres — la ligne quitte le plan quand elle est déclarée entièrement récoltée ou perdue, comme aujourd'hui pour les m²
- Point de vigilance : « touffe » est ambigu (une touffe de ciboulette plantée = un poquet ; « une touffe de mauvaises herbes » n'est pas un geste). Il n'est reconnu comme unité que dans une phrase de semis ou de plantation

**Estimation :** 2 points

**Scénario Gherkin :**
```gherkin
Scénario: Semis en poquets
  When le jardinier dicte "semé 5 poquets de courge butternut dans la planche des courges"
  Then le récapitulatif propose un semis de 5 poquets de courge butternut
  And la quantité est enregistrée avec l'unité "poquets"

Scénario: Mètre de rang contre mètre carré
  When le jardinier dicte "semé 3 mètres de carottes dans la planche centrale"
  Then l'unité enregistrée est "ml"
  When le jardinier dicte "semé 2 mètres carrés de carottes dans la planche centrale"
  Then l'unité enregistrée est "m2"

Scénario: Pas de poquet en pépinière
  When le jardinier dicte "mis en godet 4 poquets de tomate"
  Then le bot refuse l'unité et rappelle qu'une mise en godet se compte en plants

Scénario: Récolte d'une culture reproductive en poquets
  Given 3 poquets de potiron en place
  When le jardinier note une récolte de 6 kg de potiron
  Then le potiron compte toujours 3 poquets
  And les 6 kg s'ajoutent au rendement de la saison
```

**Labels GitHub :** `us`, `bot`, `backend`, `enregistrement`, `plan`
