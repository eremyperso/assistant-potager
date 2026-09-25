**ID :** US-206
**Titre :** Composer la fiche d'une culture pour la PWA — référentiel, variétés cultivées, voisinages, bioagresseurs
**Épic :** ÉPIC 11 — Cultures : tout savoir d'une culture *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'application rassemble, pour une culture, ce que dit le référentiel, où je la cultive, avec quoi l'associer et ce qui peut l'attaquer
Afin de trouver tout cela dans une seule fiche, dans l'application comme au bot, avec les mêmes informations

**Contexte fonctionnel :**
La fiche culture du wireframe v1 (§ 2b) empile six sections, « dans l'ordre d'utilité » : *Maintenant*, *Calendrier de la zone*, *Référentiel*, *Variétés cultivées*, *Voisinages*, *Bioagresseurs*. Presque tout existe déjà en base, et le bot sait le composer : `/fiche <culture>` (US-164) restitue famille, délai de retour, caractéristiques de conduite (US-161) et, depuis US-174, les bioagresseurs à surveiller, « en zéro jeton et zéro appel réseau », « par gabarit depuis la donnée déjà en base ». Les associations se lisent par `/association lister` (US-163).

Ce qui manque, c'est une **lecture structurée pour la PWA** : le bot rend du texte, l'écran a besoin de données. Cette US l'expose, en réutilisant les mêmes fonctions de lecture que le bot — jamais une seconde composition.

*Maintenant* et *Calendrier de la zone* ne sont pas dans cette lecture : ils viennent du calendrier et de la confiance déjà lus par l'écran d'origine, ou relus par la fiche (US-207), pour que la fiche culture, la carte Cultures, la pastille du Plan et la fiche calendrier ne puissent jamais afficher deux niveaux différents.

**Critères d'acceptance :**

*Contenu*
- [ ] CA1 : `GET /cultures/{culture}/fiche` (potager et date de référence en paramètres) rend l'**identité** de la culture : nom, famille botanique et son délai de retour — rendus séparément, l'écran les assemblant en « Solanacée · retour 4 ans » —, type d'organe récolté (végétatif ou reproducteur), itinéraires connus
- [ ] CA2 : Les **caractéristiques de conduite** (US-161) — exposition, besoin en eau, profondeur de semis, rusticité minimale — chacune avec sa source ; une caractéristique inconnue vaut « non renseigné », jamais une valeur devinée ni complétée par un modèle
- [ ] CA3 : Les **durées** du référentiel — levée, semis → première récolte, délai avant plantation, plantation → première récolte (US-177), et le délai semis → repiquage en godet quand US-213 est livrée — chacune en fourchette ou « non renseignée ». Une durée absente n'est jamais déduite d'une autre (US-177)
- [ ] CA4 : Les **variétés cultivées** à la date de référence : pour chaque variété, les parcelles où elle est en place avec leur phase (US-194), et les lots de pépinière en cours avec leur numéro (US-209, quand livrée), leur **stade** (« semé en caissette », « en godet ») et leur **emplacement** (la pépinière où ils sont posés, US-210). La fiche affiche « lot #128 · Serre » : les trois valeurs sont rendues séparément, le front les assemble. Une variété seulement en pépinière y figure, avec une liste de parcelles vide — jamais masquée
- [ ] CA5 : Les **voisinages** (US-163) : associations favorables et défavorables, y compris celles saisies au niveau de la famille ; chacune avec la culture ou la famille voisine, son motif et son niveau de preuve, pour que l'écran distingue « défavorable » de « déconseillé par la pratique traditionnelle » (US-163)
- [ ] CA6 : Les **bioagresseurs** (US-162, US-174) : tous ceux rattachés à la culture, les plus fréquents d'abord, avec leur catégorie (« champignon », « insecte », « mollusque », « virus »), leur période de risque **seulement si elle est renseignée** et leur description de symptôme quand elle existe, plus leur nombre total — l'écran n'en affiche que cinq et déplie le reste (US-207 / CA8), la lecture les rend donc **tous en une fois**, jamais par page. Un bioagresseur déclaré localement par **ce** potager y figure ; celui d'un autre potager jamais (US-174 / CA6, CA7)
- [ ] CA7 : Les **attributions** de source des valeurs rendues, dédoublonnées (Wind River Greens, EPPO…)

*Honnêteté et cas limites*
- [ ] CA8 : Une culture **inconnue du référentiel** rend une réponse explicite « fiche absente », sans jamais proposer une culture voisine (US-164) ; ses variétés cultivées restent rendues
- [ ] CA9 : Aucun voisinage connu : la réponse le dit, et le libellé servi rappelle que ce n'est pas une absence de conflit. Aucun bioagresseur rattaché : « je n'ai pas l'information », avec la précision que ce n'est pas une absence de risque (US-162 / CA12)

*Cohérence avec le bot*
- [ ] CA10 : La lecture réutilise les fonctions de lecture de la fiche du bot (`fiche_culture`, associations, bioagresseurs, attributs) ; un test vérifie que `/fiche <culture>` et `GET /cultures/{culture}/fiche` rendent la même famille, les mêmes caractéristiques et les mêmes bioagresseurs pour un même potager
- [ ] CA11 : Zéro jeton, zéro appel réseau externe, une seule requête HTTP ; lecture seule

*Définition de terminé*
- [ ] CA12 : `docs/domaines/cultures-et-fiche.md` (créée par US-204, ou ici si US-204 n'est pas encore livrée) décrit la lecture et ce qu'elle ne porte pas (calendrier et confiance) ; `docs/domaines/referentiel-cultures.md` mentionne le second consommateur des fonctions de la fiche
- [ ] CA13 : Des tests couvrent : culture complète, caractéristique inconnue, durée absente, variété seulement en pépinière, association de famille, bioagresseur local de ce potager et d'un autre potager, culture inconnue, aucun voisinage, aucun bioagresseur, égalité avec la fiche du bot, date de référence passée

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (lecture)
- Migration BDD requise : **non**
- Dépendances : US-161, US-162, US-163, US-164, US-174 (livrées) ; **US-194** (phase des variétés) ; US-209 et US-213 enrichissent sans bloquer
- Consommateur : US-207 (fiche culture dans la PWA)
- Impact tokens : zéro
- Point de vigilance : aucun **chiffre agronomique** n'est rédigé ici ; tout vient du référentiel structuré, avec sa source (règle du corpus agronomique, US-140)
- Point de vigilance : aucune donnée de phytosanitaire, aucun dosage — il n'existe aucune colonne où en stocker un (US-162 / CA10)
- Wireframe : v1 § 2b « Fiche culture » et ses notes

**Estimation :** 3 points (inchangée au 25/09 : la maquette ne demande aucune donnée nouvelle)

---

## 🆕 Amendement du 25/09/2026 — maquette gelée « Cultures — écran et fiche »

La maquette `Cultures - Ecran et fiche.html` confirme cette lecture **sans l'élargir**. Trois
précisions seulement, toutes de forme :

1. **CA1** — famille et délai de retour rendus séparément ; c'est l'écran qui écrit
   « Solanacée · retour 4 ans » sur une seule ligne du bloc *Référentiel*.
2. **CA4** — un lot se lit « lot #128 · Serre » : numéro **et** emplacement **et** stade.
   L'emplacement vient d'US-210 ; tant qu'elle n'est pas livrée, il est absent, et la fiche
   écrit « lot #128 » seul — jamais « emplacement inconnu » inventé (RT2).
3. **CA6** — la liste complète des bioagresseurs est rendue en une fois, l'écran gérant le
   « + N autres ».

Les neuf entrées du bloc *Référentiel* de la maquette (famille · retour, exposition, besoin en
eau, rusticité minimale, profondeur de semis, levée, délai avant plantation, plantation →
1ʳᵉ récolte, organe récolté) sont exactement CA1 à CA3. Chacune vaut « non renseigné » quand
elle manque, et la maquette le rend visuellement : valeur en gris et en graisse normale.

**Scénario Gherkin :**
```gherkin
Scénario: Fiche de la tomate
  Given la tomate est en récolte dans deux parcelles, une variété en pépinière
  When je lis la fiche de la tomate
  Then elle porte la famille Solanacées, l'exposition "plein soleil" et sa source
  And les variétés cultivées avec leurs parcelles et leur phase, dont la variété en pépinière avec son lot
  And les voisinages favorables et défavorables avec leur niveau de preuve
  And les bioagresseurs, les plus fréquents d'abord

Scénario: Caractéristique inconnue
  Given la rusticité minimale de la courgette n'est pas renseignée
  When je lis la fiche de la courgette
  Then la rusticité vaut "non renseigné"

Scénario: Bioagresseur local
  Given un bioagresseur déclaré sur le poireau par le potager A
  When le potager B lit la fiche du poireau
  Then ce bioagresseur n'y figure pas

Scénario: Culture inconnue
  Given de la verveine plantée, inconnue du référentiel
  When je lis la fiche de la verveine
  Then la réponse indique "fiche absente" sans proposer d'autre culture
  And la variété cultivée et sa parcelle sont rendues
```

**Labels GitHub :** `us`, `backend`, `cultures`, `api`
