**ID :** US-066
**Titre :** Réclamer le nombre de graines d'origine lors d'une mise en godet

**Story :**
En tant que jardinier utilisant le bot Telegram
Je veux que le bot me demande sur combien de graines j'ai repiqué mes plants quand il ne peut pas le déduire
Afin que mon taux de germination et l'avancement de mes lots restent justes, au lieu d'être faussés par une information que j'étais seul à connaître au moment de la saisie

**Contexte fonctionnel :**
Aujourd'hui, `nb_graines_semees` — le « sur N graines » d'une mise en godet — est traité comme un champ **optionnel** au parsing (`bot.py`, « graines d'origine dans la barquette (optionnel) »). Si le jardinier dicte « j'ai mis 5 tomates en godet » sans préciser l'origine, l'information est perdue au moment précis où il est le seul à pouvoir la donner : quelques semaines plus tard, plus personne ne saura combien de graines ont réellement été consommées.

Cette perte a une conséquence directe, mesurée au cadrage d'US-065 : sans nombre de graines déclaré, le système ne peut pas savoir quand la germination d'un lot est terminée. Un lot de 10 graines ayant donné 7 plants, tous mis en terre, affiche alors « Terre 70 % » au lieu de 100 % et n'atteint jamais 100 %, tandis que son état de germination reste indéterminé à vie.

C'est le seul garde-fou qui traite la **cause** plutôt que le symptôme : aucun traitement à l'affichage ne reconstituera une donnée qui n'a jamais été saisie. US-065 rend la lacune visible ; cette US-ci l'empêche de se produire.

**Critères d'acceptance :**
- [ ] CA1 : Lorsqu'une mise en godet est enregistrée sans nombre de graines d'origine **et** qu'il existe pour ce couple culture + variété un semis en pépinière dont toutes les graines ne sont pas encore soldées, le bot demande sur combien de graines le repiquage a été fait, avant de confirmer l'enregistrement
- [ ] CA2 : La question rappelle le contexte utile au jardinier — la culture, la variété, et le nombre de graines encore non soldées sur le semis concerné — plutôt que d'être posée à l'aveugle
- [ ] CA3 : La réponse est facultative : le jardinier peut passer outre en une action explicite, l'événement est alors enregistré sans nombre de graines et l'état de germination du lot reste « indéterminée » conformément à US-065 — le bot n'impose jamais une valeur par défaut inventée
- [ ] CA4 : La question n'est **pas** posée quand elle n'a pas lieu d'être : nombre de graines déjà fourni dans la dictée, aucun semis en pépinière rattachable, ou semis déjà entièrement soldé
- [ ] CA5 : La valeur saisie respecte le garde-fou existant interdisant qu'un lot déclare plus de plants que de graines (`app/services/evenements.py`) ; une réponse incohérente est signalée et redemandée plutôt qu'enregistrée
- [ ] CA6 : Le flux reste utilisable en saisie vocale comme en saisie texte, sans rompre le parcours de confirmation d'action existant (US-021)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram et enregistrement
- Migration BDD requise : non — la colonne `nb_graines_semees` existe déjà, seule sa complétude s'améliore
- Dépendances : complète US-065 (qui expose l'état « indéterminée » que cette US vise à faire disparaître) ; s'appuie sur US-016 et US-020 (sémantique de la mise en godet et traçabilité du lot) et sur le flux de confirmation d'US-021
- Portée : cette US ne corrige pas l'historique — les mises en godet déjà enregistrées sans nombre de graines restent en état indéterminé ; seule la saisie future est améliorée

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Le bot réclame l'information manquante
  Given un semis de 10 graines de tomate en pépinière, dont aucune graine n'est encore soldée
  When le jardinier dicte "j'ai mis 5 tomates en godet" sans préciser le nombre de graines
  Then le bot demande sur combien de graines ce repiquage a été fait
  And il rappelle qu'il reste 10 graines non soldées sur ce semis

Scénario: Question non posée quand l'information est déjà là
  Given le même semis
  When le jardinier dicte "j'ai mis 5 tomates en godet sur 6 graines"
  Then l'événement est enregistré directement, sans question supplémentaire

Scénario: Question non posée sans semis rattachable
  Given aucun semis de courgette en pépinière
  When le jardinier dicte "j'ai mis 4 courgettes en godet"
  Then l'événement est enregistré directement, sans question supplémentaire

Scénario: Le jardinier ne sait pas répondre
  Given le bot a demandé le nombre de graines d'origine
  When le jardinier choisit de ne pas répondre
  Then l'événement est enregistré sans nombre de graines
  And l'état de germination du lot est "indéterminée"

Scénario: Réponse incohérente refusée
  Given le bot a demandé le nombre de graines pour un repiquage de 5 plants
  When le jardinier répond "3 graines"
  Then le bot signale l'incohérence et redemande la valeur
```

**Labels GitHub :** `us`, `telegram`, `enregistrement`, `pepiniere`
