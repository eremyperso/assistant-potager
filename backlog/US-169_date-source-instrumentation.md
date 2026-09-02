**ID :** US-169  
**Titre :** Tracer l'origine de la date d'un évènement  
**Épic :** ÉPIC 6 — Référentiel de connaissance des cultures

**Story :**
En tant qu'administrateur
Je veux savoir, pour chaque évènement, si sa date a été dictée ou présumée
Afin de pouvoir mesurer un jour le taux d'erreur réel de la convention « pas de date dictée = aujourd'hui », au lieu de n'en connaître qu'une borne basse

**Critères d'acceptance :**

*La colonne*
- [ ] CA1 : `evenements` porte une colonne `date_source`, texte, **nullable**, sans valeur par défaut. Le type est textuel et non booléen : la taxonomie compte déjà trois valeurs et l'expérience d'US-094 en a révélé une quatrième (CA3). Un booléen imposerait de rouvrir la migration, ce que l'invariant « aucune migration ne rouvre une table modifiée par une autre US en vol » interdit
- [ ] CA2 : Migration séparée et idempotente, rollback documenté. Elle ne rouvre pas la migration d'US-094, livrée sur la même table
- [ ] CA3 : La taxonomie est arrêtée et écrite **avant** l'implémentation. Elle doit distinguer, au minimum : une date dictée en clair, une date relative résolue, une date jamais dictée. Elle ne doit **jamais** affirmer plus que le chemin d'écriture ne peut savoir — voir la note « ce que chaque chemin sait réellement » ci-dessous, qui est le vrai sujet de cette US
- [ ] CA4 : Les lignes antérieures restent à `NULL`. **Aucun backfill**, y compris pour les saisies récentes dont l'origine serait recalculable depuis le texte : une valeur reconstituée n'est pas une observation, et mélanger les deux dans la même colonne détruirait précisément la mesure qu'on cherche à faire

*Le renseignement, sur les deux chemins*
- [ ] CA5 : Le chemin déterministe renseigne la valeur exacte que sa grammaire d'ancrage temporel a déjà établie. Cette valeur est **déjà calculée** aujourd'hui et n'est propagée nulle part : l'US consiste à la faire descendre jusqu'à l'écriture, pas à la produire
- [ ] CA6 : Le chemin modèle renseigne la sienne au **site de repli existant** — celui qui pose déjà « aujourd'hui » faute de date. Aucun nouveau détecteur d'expression temporelle n'est écrit pour ce chemin : la grammaire d'ancrage existe déjà et appartient au chemin déterministe
- [ ] CA7 : Un évènement écrit par un chemin qui ne sait pas conclure reste à `NULL`. `NULL` signifie « inconnu », jamais « présumé » — les confondre rendrait la mesure fausse dans le sens qui arrange, ce qui est le pire des cas

*L'invariant : instrumentation seule*
- [ ] CA8 : `date_source` n'est **ni affichée au jardinier, ni lue par un gabarit de réponse, ni utilisée dans une condition métier**. Un évènement se comporte exactement pareil quelle que soit sa valeur
- [ ] CA9 : Un test échoue si un service d'analyse, un gabarit ou un message utilisateur lit cette colonne. C'est ce test, et non l'intention, qui maintient l'invariant — le même que celui déjà en place pour `origine_parsing` (US-094 / CA10)
- [ ] CA10 : La mention « date présumée » dans le message de confirmation est **explicitement hors périmètre** et le reste. Toute saisie sans ancrage retombe sur aujourd'hui : l'affichage serait systématique et n'informerait personne

*La mesure, qui est la seule raison d'être de cette US*
- [ ] CA11 : Une requête de croisement `date_source` × traces `[CORR]` est fournie dans `tools/`, en lecture seule, hors `migrations/`. Sans elle la colonne se remplit sans que personne ne sache l'interroger, et l'US n'a rien livré
- [ ] CA12 : Cette requête croise aussi `origine_parsing` (US-094). Les deux colonnes ensemble disent quel **chemin** se trompe sur les dates, pas seulement combien de fois — c'est cette ventilation qui désignera la règle à écrire, et elle est gratuite puisque les deux colonnes cohabitent déjà

**Notes fonctionnelles :**

- Zone fonctionnelle concernée : enregistrement (instrumentation à l'écriture)
- Migration BDD requise : **oui** — ajout d'une colonne nullable, sans backfill
- Dépendances :
  - **US-094** (parseur déterministe, livrée) — fournit la grammaire d'ancrage temporel et la colonne voisine `origine_parsing`
  - **US-168** (référentiel d'actions unifié et unités normalisées, **livrée**) — insertion 1 de la même vague, sans couplage technique avec celle-ci
  - Ne bloque rien. N'est bloquée par rien.
- Source : insertion 2 de la vague 2 / piste A (`docs/decisions-prerequis-vague2-piste-a.md` §4)
- Numérotation : la bande de l'ÉPIC 6 annoncée à `US-160 → US-167` est déjà dépassée par US-168 ; cette US la prolonge à 169. L'épic retenu est celui de sa jumelle US-168, pour que les deux insertions de la vague 2 restent lisibles ensemble dans Jira — même si le consommateur final de la mesure est l'Épic 5

*Ce que la vague 2 a livré depuis la rédaction du document de décisions*

Les deux insertions étaient à faire **avant** US-096, puis US-094. L'ordre réel a été : US-096 (26/08), US-168 (28/08), **US-094 (28/08)**. Cette US est donc la dernière de la séquence au lieu d'en être la deuxième. Deux conséquences, une bonne et une mauvaise :

- **Le travail de détection est déjà fait.** US-094 a livré une grammaire d'ancrage temporel qui distingue explicitement une date dictée en clair, une date relative résolue, une absence d'ancrage, et — cas non prévu par le document de décisions — une expression temporelle *présente mais non résoluble*. Elle expose déjà la valeur attendue par cette US. Elle ne la transmet à personne.
- **Le trou dans la mesure s'est creusé.** L'argument « écrire la colonne maintenant, sinon elle laisse un trou sur exactement la période qui intéresse » vaut toujours, et il vaut plus qu'au 27/08.

*Ce que chaque chemin sait réellement — le point à trancher*

La taxonomie du document de décisions a été conçue quand un seul chemin d'écriture existait. Il y en a deux depuis US-094, et ils ne savent pas la même chose :

| Chemin | Ce qu'il peut affirmer | Ce qu'il ne peut pas savoir |
|---|---|---|
| Déterministe | date dictée en clair / relative résolue / aucun ancrage / ancrage vu mais illisible | rien : sa grammaire est la source |
| Modèle | « le modèle a rendu une date » / « le modèle n'en a rendu aucune » | **si cette date était dictée en clair ou déduite d'un « hier »** — le modèle résout l'ancrage lui-même et ne dit pas ce qu'il a lu |

Écrire « date dictée en clair » sur le chemin modèle serait donc une affirmation que rien ne fonde. C'est exactement le défaut que cette US existe pour mesurer, reproduit dans l'instrument de mesure. **La taxonomie doit donc porter l'incertitude du chemin**, d'une façon ou d'une autre, et c'est la décision à écrire au titre du CA3.

Une piste, non imposée : une valeur distincte pour « date rendue par le modèle, origine non connaissable ». Elle a le mérite de rendre la ventilation par chemin (CA12) exploitable au lieu de la rendre trompeuse.

*Le cas « ancrage vu mais illisible » — un gisement que le document ne prévoyait pas*

Quand la grammaire déterministe repère du vocabulaire temporel qu'elle ne sait pas dater (« il y a une semaine », « en juin 2023 »), elle renvoie la phrase entière au modèle plutôt que de présumer. Ces saisies sont, par construction, celles où le jardinier **a** donné un ancrage. Elles sont donc les plus susceptibles de porter une date fausse si le modèle se trompe, et ce sont aussi celles qui désignent la prochaine règle à ajouter à la grammaire.

Les distinguer coûte une valeur de plus dans la taxonomie. Point ouvert, à arbitrer avec le CA3 : cette information n'est aujourd'hui disponible qu'au moment du parsing et se perd ensuite définitivement.

*Ce que la mesure vaut, et ce qu'elle ne vaudra pas*

La convention n'est pas vérifiable ligne par ligne. Après coup, une ligne non corrigée est soit exacte, soit fausse et jamais remarquée. Les 35 traces `[CORR]` de production mesurent ce qui a été *remarqué* : une borne basse, jamais le taux d'erreur réel. `date_source` ne lève pas cette limite — elle donne le **dénominateur** qui manque aujourd'hui, ce qui est déjà tout ce qui sépare « 11 corrections de date » d'un taux.

Le périmètre où l'erreur mord vraiment est celui des **durées calculées** (Épic 5). Le biais est asymétrique : une plantation saisie 14 jours après le geste et une récolte saisie le jour même produisent un cycle raccourci de 14 jours. Un référentiel phénologique recalé sur ces données serait systématiquement trop court, sans qu'aucune donnée ne permette de s'en apercevoir. C'est le second usage prévu de la colonne : permettre à l'Épic 5 d'écarter les lignes douteuses.

*Pourquoi maintenant, et pas « quand on en aura besoin »*

Aujourd'hui la convention tient parce que le développeur est le seul utilisateur et qu'il la connaît. À l'ouverture beta, elle devient une hypothèse sur le comportement d'inconnus qui ne l'ont jamais lue. La colonne écrite maintenant est renseignée dès leur première saisie ; ajoutée après, elle laisse un trou sur exactement la période qui intéresse — et le CA4 interdit de le combler après coup.

*Ce qui reste explicitement hors périmètre*

- Toute modification du message de confirmation (CA10)
- Tout nouveau détecteur d'expression temporelle sur le chemin modèle (CA6)
- Tout tour de dialogue « demander plutôt que présumer » : écarté, il imposerait un état supplémentaire dans la conversation, donc un risque sur l'ordre critique des flux de `handle_text` — l'invariant le plus fragile du projet
- Tout enrichissement de la grammaire d'ancrage d'US-094 : elle est livrée, et l'élargir relève de sa maintenance normale, alimentée par la mesure que cette US rend possible

**Estimation :** 2 points

*Le document de décisions annonçait 1 point, avant que le second chemin d'écriture n'existe. La détection est certes acquise, mais l'arbitrage de taxonomie (CA3), le double site de renseignement (CA5/CA6) et la requête de croisement (CA11/CA12) ne l'étaient pas.*

**Scénario Gherkin :**
```gherkin
Scénario: une date dictée en clair est tracée comme telle
  Given je dicte "récolte 2 kg de tomates le 25 mai"
  When l'évènement est enregistré
  Then sa date est le 25 mai
    And date_source indique que la date a été dictée en clair

Scénario: une absence d'ancrage est tracée comme présumée
  Given je dicte "récolte 2 kg de tomates", sans aucune mention de temps
  When l'évènement est enregistré
  Then sa date est celle du jour, conformément à la convention du projet
    And date_source indique que la date a été présumée
    And aucun message ne m'annonce que la date a été présumée

Scénario: le chemin modèle n'affirme jamais ce qu'il ne sait pas
  Given une saisie que la grammaire déterministe ne sait pas lire
    And le modèle rend une date
  When l'évènement est enregistré
  Then date_source ne prétend pas que cette date a été dictée en clair

Scénario: la colonne reste une instrumentation
  Given des évènements portant chacune des valeurs de date_source
  When je consulte mes stocks, mes récoltes et mon historique
  Then aucune réponse ne diffère
    And aucune réponse ne mentionne l'origine de la date

Scénario: l'historique n'est jamais reconstitué
  Given des évènements enregistrés avant cette US
  When la migration est appliquée
  Then leur date_source vaut NULL
    And aucun traitement ne tente de la déduire de leur texte original
```

**Labels GitHub :** `us`, `epic-6`, `enregistrement`, `instrumentation`
