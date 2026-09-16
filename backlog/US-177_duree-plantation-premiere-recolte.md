**ID :** US-177
**Titre :** Ajouter la durée plantation → première récolte au référentiel de calendrier cultural
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux que l'application connaisse, pour chaque culture, le délai entre la mise en place d'un plant et sa première récolte
Afin qu'un plant acheté en jardinerie ou sorti de ma pépinière ait lui aussi une récolte attendue, et pas seulement les cultures que j'ai semées moi-même

**Contexte fonctionnel :**
Le référentiel d'US-068 porte trois durées, toutes comptées **depuis le semis** : levée, première récolte, repiquage (`calendrier_cultural.ETAPES`). L'amendement du 15/09/2026 a ajouté une *fenêtre* de plantation par zone, mais aucune *durée* depuis la plantation. Conséquence, notée comme point ouvert dans US-068 et US-070 : pour une tomate achetée en godet et plantée le 10 mai, l'application n'a aucune origine de semis et **ne peut rien projeter** — la frise reste neutre et la durée en tiret, alors que c'est le geste que font la plupart des jardiniers.

La donnée existe dans la source déjà au socle : `SOURCE.md` consigne que `days_to_harvest` de Wind River Greens compte **depuis la plantation** pour les cultures élevées à l'abri — c'est précisément le motif pour lequel il avait été rejeté sur tomate et poivron pour la durée semis → récolte. Ce qui était un défaut pour une étape devient la bonne donnée pour celle-ci.

Aucune migration : `duree_culturale.etape` est un `VARCHAR(20)` sans CHECK de vocabulaire (arbitrage explicite de `migration_v46`, lignes 50-53), validé par le seul point d'écriture `calendrier_cultural.py`. À vérifier en implémentation contre le schéma de production, pas à supposer.

**Critères d'acceptance :**
- [ ] CA1 : Le référentiel porte une quatrième étape de durée, **plantation → première récolte**, exprimée comme les autres en fourchette de jours ou en mention libre, commune à toutes les zones climatiques
- [ ] CA2 : Cette étape est **pré-remplie depuis la source déjà au socle** pour les cultures dont `days_to_harvest` compte depuis la plantation, avec les mêmes règles de rejet que les autres durées (médiane, seuils de cultivars) ; elle n'est **jamais** déduite par soustraction de la durée de repiquage à la durée semis → récolte
- [ ] CA3 : Une culture qui ne se plante pas (semis direct seulement) ne porte pas cette étape ; une culture qui se plante sans se semer chez soi (ail, pomme de terre, fraise) peut la porter seule, sans durée de levée ni de repiquage
- [ ] CA4 : Le jardinier peut la **corriger au bot** avec la sous-commande de durée existante (`/calendrier duree <culture> plantation-recolte …`), correction propre à son potager, prioritaire sur le calendrier partagé et jamais écrasée par un rejeu de l'import
- [ ] CA5 : L'interpréteur de commandes reconnaît la dictée « délai entre la plantation et la récolte des tomates : 60 à 80 jours » comme cette durée, sans la confondre avec la durée `repiquage` (semis → plantation) ni avec une fenêtre
- [ ] CA6 : La forme de lecture exposée par l'API (`GET /cultures/{culture}/calendrier`) rend cette étape avec le même libellé lisible que les autres (« 60 à 80 jours », « vivace ») ou l'omet quand elle n'est pas renseignée. Aucun consommateur existant ne change de comportement
- [ ] CA7 : Le recalage d'US-070 utilise cette durée pour une culture dont l'événement d'origine est une **plantation sans semis connu** : la première récolte attendue est projetée depuis la date réelle de plantation. Une culture plantée dont la durée n'est pas renseignée reste en mode dégradé, jamais projetée depuis une durée empruntée
- [ ] CA8 : Quand une culture a **à la fois** un semis chaîné et une plantation, la projection depuis le semis (durée `recolte`) reste la référence ; la durée de cette US ne sert qu'en l'absence d'origine de semis. La règle est écrite à un seul endroit et testée
- [ ] CA9 : La fiche d'aide `calendrier-et-zone-climatique.md` est relue et corrigée dans la même livraison (US-099 / CA9), et le corpus de mesure reste classé
- [ ] CA10 : Des tests couvrent : pré-remplissage depuis la source, rejet de la déduction par soustraction, culture plantée seule, correction au bot isolée par potager, dictée du CA5 contre les deux confusions, projection depuis plantation, priorité du semis du CA8, non-régression de la forme de lecture

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (référentiel, bot), consultation (projection)
- Migration BDD requise : **non** (vocabulaire d'étape sans contrainte, à vérifier contre la production)
- Dépendances : US-068 (référentiel, livrée), US-070 (recalage — cette US en est le complément pour les plantations)
- Consommateurs : US-070 (CA7), US-178 (règle R5 « saison restante » pour l'action *plantation*)
- Point de vigilance : le libellé au bot doit lever l'ambiguïté avec `repiquage`, qui se lit « semis → plantation en place ». Proposition : « Plantation → première récolte », à valider avec le libellé de `LIBELLES_ETAPES`
- Point de vigilance : ne pas réouvrir l'adaptateur pour tomate et poivron en changeant ce qu'il fait pour la durée `recolte` — cette US **ajoute** une lecture, elle n'en corrige aucune

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Pré-remplissage depuis la source
  Given la source indique pour la tomate un délai jusqu'à la récolte compté depuis la plantation
  When le référentiel est importé
  Then la tomate porte une durée plantation → première récolte
  And cette durée n'est pas égale à la durée semis → récolte moins la durée de repiquage

Scénario: Plant acheté, récolte projetée
  Given une tomate plantée le 10 mai sans aucun semis chaîné
  And une durée plantation → première récolte de 60 à 80 jours
  When le jardinier consulte cette parcelle
  Then la première récolte attendue est affichée entre le 9 et le 29 juillet

Scénario: Semis connu, le semis reste la référence
  Given une tomate semée en godet le 15 mars puis plantée le 10 mai
  When le jardinier consulte cette parcelle
  Then la projection part du semis du 15 mars
  And la durée plantation → première récolte n'est pas utilisée

Scénario: Dictée sans confusion
  Given le jardinier dicte "délai entre la plantation et la récolte des tomates : 60 à 80 jours"
  When la commande est interprétée
  Then elle est reconnue comme la durée plantation → première récolte
  And non comme la durée de repiquage ni comme une fenêtre de plantation

Scénario: Durée absente, aucune projection empruntée
  Given un poireau planté le 3 juin sans durée plantation → première récolte renseignée
  When le jardinier consulte cette parcelle
  Then la récolte attendue est affichée en tiret
```

**Labels GitHub :** `us`, `backend`, `bot`, `cultures`
