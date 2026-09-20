**ID :** US-194
**Titre :** Calculer la phase du moment d'une culture en place — semée, en place, en récolte
**Épic :** ÉPIC 9 — Socle commun Plan, Cultures, Pépinière *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux voir, pour chaque culture de mes parcelles, si elle vient d'être semée, si elle est en place ou si elle est déjà en récolte
Afin de lire l'état de mon potager d'un coup d'œil, avec le même mot sur le Plan, sur l'écran Cultures et dans la fiche d'une culture

**Contexte fonctionnel :**
Les trois wireframes colorent chaque culture par sa **phase du moment** : *semé*, *en place*, *en récolte* (v1 : « phase déduite » ; v3 règle 5 : « Couleur = phase »). La Vue plan (US-200) en fait sa couleur, l'écran Cultures (US-205) sa pastille « en récolte · 2 parcelles », la fiche culture (US-207) la ligne de chaque variété cultivée.

Cette phase n'existe nulle part aujourd'hui. Ce qui existe : l'état d'une série recalée (US-070 : `a_venir`, `recolte_attendue`, `en_recolte`, `recolte_depassee`, `sans_recalage`), qui dépend du référentiel et disparaît quand la culture n'en a pas. La phase doit, elle, être **toujours** calculable : une plantation sans référentiel reste « en place », une récolte notée reste une récolte.

Cette US pose la règle **à un seul endroit, côté serveur**, l'expose dans `GET /plan`, et ajoute au design system la pastille qui l'affiche. Elle ne dessine aucun écran.

**Règle de calcul — à la date de référence, pour une ligne en place (parcelle × culture × variété) :**

| Phase | Condition, évaluée dans cet ordre |
|---|---|
| **en récolte** | au moins une récolte est rattachée à la série la plus ancienne encore ouverte de la ligne (rattachement d'US-070, `rattacher_recoltes`) |
| **en place** | la série a pour origine une **plantation** ; ou un **semis** dont la levée attendue (délai `levee` du référentiel) est atteinte |
| **semée** | la série a pour origine un semis dont la levée attendue n'est pas atteinte, **ou dont le délai de levée n'est pas connu** |

⚖️ Un semis sans délai de levée au référentiel reste « semé » jusqu'à sa première récolte : c'est le dernier geste connu, pas une supposition. La fiche d'aide le dit.
⚖️ Plusieurs séries sur la même ligne : la phase est celle de la **plus ancienne** encore ouverte, comme la frise recalée (US-070 / CA9) ; le nombre de séries est exposé à côté, jamais moyenné.

**Critères d'acceptance :**

*La règle*
- [ ] CA1 : La phase est calculée par **une seule fonction** du service de recalage (ou d'un module voisin qui en réutilise les séries), à la date de référence, selon la table ci-dessus. Aucun autre fichier — front compris — ne recalcule une phase
- [ ] CA2 : Une ligne sans référentiel ou en `sans_recalage` a quand même une phase : récolte notée → en récolte, plantation → en place, semis → semée
- [ ] CA3 : En végétatif, une récolte clôt sa série (US-070 / CA6) ; si la ligne reste en place grâce à une autre série ouverte, la phase est celle de cette série
- [ ] CA4 : Un semis en pépinière n'a jamais de phase : il n'est pas une culture en place (exclusion inchangée de `calcul_occupation_parcelles`)
- [ ] CA5 : La phase porte sa **date de début** : date de la première récolte, de la plantation, de la levée attendue (début de fourchette) ou du semis. Une levée attendue reste une date attendue, jamais présentée comme constatée

*L'exposition*
- [ ] CA6 : `GET /plan` ajoute à chaque culture d'une parcelle `phase` (`semee` | `en_place` | `en_recolte`), `phase_depuis` et `nb_series` ; aucun champ existant n'est retiré ni renommé. L'écran Parcelles actuel n'est pas modifié
- [ ] CA7 : La date de référence passée reconstitue la phase de ce jour-là : une récolte postérieure n'est pas vue (US-030 / US-070 / CA8)
- [ ] CA8 : Aucune écriture, aucun calcul de stock, de projection ni de confiance n'est modifié ; un test le vérifie sur les réponses de `GET /plan/calendriers`, `GET /godets` et `GET /stats`

*Le design system*
- [ ] CA9 : Un composant `PastillePhase` affiche le **mot** de la phase dans sa teinte ; une `LegendePhases` affiche les trois (plus « libre » en option). Les teintes sont des tokens sémantiques, cohérents avec la frise : *semée* reprend la famille de teinte du semis en pleine terre, *en place* celle réservée à « en croissance » (US-070 / CA7), *en récolte* celle de la récolte. Mode sombre compris
- [ ] CA10 : La correspondance phase → libellé → teinte est écrite **une fois**, dans une lib testée (`node --test`) ; la pastille est lisible en niveaux de gris grâce à son mot (RT4)

*Définition de terminé*
- [ ] CA11 : La fiche `parcelles-et-plan.md` (section « Savoir ce qui pousse et ce qui est libre ») dit ce que signifient les trois mots et le cas du semis sans délai de levée (US-099 / CA9)
- [ ] CA12 : Des tests couvrent : plantation sans récolte, semis avant et après la levée attendue, semis sans délai de levée, première récolte d'une reproductive puis N-ième récolte, récolte partielle d'une végétative avec une seconde série ouverte, date de référence antérieure à une récolte, ligne sans référentiel, parcelle pépinière

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (lecture), consultation
- Migration BDD requise : **non**
- Dépendances : US-070 (séries et rattachement des récoltes, livrée), US-177 (ancrage sur la plantation, livrée), US-052 (tokens du design system)
- Consommateurs : US-198 et US-200 (Vue plan), US-204 et US-205 (Cultures), US-206 et US-207 (fiche culture)
- Impact tokens : zéro
- Point de vigilance : **reproducteur vs végétatif**. Un haricot semé en place passe semée → en place → en récolte et y reste à chaque cueillette (le pied reste) ; une laitue passe en récolte à sa première récolte, qui clôt sa série. Les scénarios couvrent le semis initial, la première récolte, la N-ième récolte et la fin de vie du pied
- Point de vigilance : la phase n'est **pas** l'état de la frise recalée. Elle ne dit rien d'une récolte en retard (c'est le « reste à courir » d'US-070) ; les deux coexistent sans se contredire
- Wireframes : v1 « Données mobilisées », v3 § 1 et règle 5

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Haricot semé en place, avant la levée
  Given des haricots semés en place le 12 septembre dans la planche centrale
  And un délai de levée de 8 à 12 jours pour le haricot
  When je consulte le plan au 15 septembre
  Then la ligne haricot est en phase "semée" depuis le 12 septembre

Scénario: Haricot après la levée, puis cueillettes successives
  Given les mêmes haricots
  When je consulte le plan au 25 septembre
  Then la ligne haricot est "en place"
  When je note une première récolte de haricots le 20 octobre
  Then la ligne haricot est "en récolte" depuis le 20 octobre
  When je note une deuxième récolte le 27 octobre
  Then la ligne reste "en récolte" depuis le 20 octobre

Scénario: Plantation sans référentiel
  Given un pied de verveine planté sans calendrier connu
  When je consulte le plan
  Then la ligne verveine est "en place"

Scénario: Semis sans délai de levée connu
  Given de la mâche semée en place le 1er août, sans délai de levée au référentiel
  When je consulte le plan au 1er octobre
  Then la ligne mâche est "semée"

Scénario: Date de référence antérieure à la récolte
  Given des courgettes plantées le 20 mai et récoltées pour la première fois le 16 juillet
  When je consulte le plan au 10 juillet
  Then la ligne courgette est "en place"
```

**Labels GitHub :** `us`, `backend`, `design-system`, `plan`, `cultures`
