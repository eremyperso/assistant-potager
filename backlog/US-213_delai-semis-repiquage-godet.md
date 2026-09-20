**ID :** US-213
**Titre :** Ajouter au calendrier cultural le délai entre le semis et le repiquage en godet
**Épic :** ÉPIC 12 — Pépinière : le poste de travail sous abri *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux que l'application sache au bout de combien de jours on repique en godet un semis de choux ou de tomates, et pouvoir le corriger pour mon potager
Afin qu'elle me dise quand une barquette est à repiquer, et quand elle est en retard

**Contexte fonctionnel :**
La Pépinière de la v2 trie les lots « du plus urgent au plus calme », par « jours d'écart au repiquage attendu » : « Repiquage +6 j — attendu à 12 j · les plants filent ». Elle suppose que le référentiel connaît ce délai. **Il ne le connaît pas.**

Le calendrier cultural (US-068, US-177) porte quatre durées par itinéraire : levée, semis → première récolte, `repiquage` et plantation → première récolte. Mais `repiquage` y est le délai **semis → mise en place** (« délai avant plantation des tomates : 42 à 56 jours ») : le moment où l'on met en terre, pas celui où l'on passe de la barquette au godet. `docs/domaines/calendrier-cultural.md` le rappelle : « « plantation » SEUL reste l'alias de `repiquage` (semis → mise en place) ».

Cette US ajoute une cinquième étape, **semis → repiquage en godet**, sur le modèle exact d'US-177 : une étape de plus dans `duree_culturale`, corrigeable au bot, dictable, jamais déduite d'une autre durée.

**Critères d'acceptance :**
- [ ] CA1 : `duree_culturale` accepte l'étape **semis → godet**, en jours, en fourchette (« 10-15 ») ou « aucune ». Elle n'est portée que par un itinéraire qui a une fenêtre de semis en pépinière. Si la colonne d'étape est bien sans contrainte de vocabulaire, aucune migration (comme US-177) ; sinon, une migration l'ajoute
- [ ] CA2 : `/calendrier duree <culture> [itinéraire] semis-godet 10-15` la fixe pour le seul potager qui la corrige (US-068 / CA11) ; `aucune` la retire ; aucun rejeu d'import n'écrase une correction
- [ ] CA3 : Elle se dicte, par la grammaire déterministe : « délai de repiquage en godet des choux : 10 à 15 jours », « les tomates se mettent en godet 15 à 20 jours après le semis ». Le mot **godet** est exigé : « délai de repiquage des tomates : 42 à 56 jours » garde son sens actuel (délai avant plantation, US-068 / CA29). Le corpus de dictée porte les deux formes côte à côte
- [ ] CA4 : `/calendrier <culture>` l'affiche pour les cultures qui se sèment en pépinière, « non renseigné » s'il manque ; `GET /cultures/{culture}/calendrier` et `GET /plan/calendriers` l'exposent, sans retirer ni renommer aucun champ
- [ ] CA5 : **Jamais déduite** : ni de la levée, ni du délai avant plantation, ni d'une moyenne. Sans valeur, rien n'est projeté et l'écran le dit (RT2)
- [ ] CA6 : Le gabarit de rédaction interne (`calendrier_redaction_interne.json`) gagne l'étape, **livré vide** ; une valeur ne peut y être écrite que par un humain, jamais produite par un modèle de langage. Si la source ouverte en porte une, son adaptateur la lit ; sinon `SOURCE.md` dit qu'elle ne la porte pas
- [ ] CA7 : Aucun calcul existant ne change (frise, projections, confiance, stock) ; le consommateur est US-214
- [ ] CA8 : Les fiches `calendrier-et-zone-climatique.md` (les délais du calendrier) et le guide utilisateur (`/calendrier duree`) sont mis à jour (US-099 / CA9) ; `docs/domaines/calendrier-cultural.md` gagne la cinquième étape et sa règle de non-confusion
- [ ] CA9 : Des tests couvrent : fixation par commande, suppression, correction locale non écrasée par un rejeu, dictée avec et sans « godet », refus sur un itinéraire sans semis en pépinière, affichage « non renseigné », exposition dans les deux lectures

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : interaction Telegram, référentiel (calendrier cultural)
- Migration BDD requise : **non** a priori (précédent d'US-177 : « VARCHAR(20) sans CHECK »), à vérifier au démarrage
- Dépendances : US-068, US-177 (livrées)
- Consommateur : US-214 (échéance de repiquage d'un lot), US-206 (durées de la fiche culture)
- Impact tokens : zéro
- Point de vigilance : **le remplissage des valeurs est un chantier à part**, qui n'appartient pas à cette US. Tant que le délai n'est renseigné pour aucune culture, la Pépinière n'annonce aucune échéance de repiquage (US-214) ; il faut décider qui renseigne les cultures réellement semées en pépinière (plan des épics § 10, point 3)
- Point de vigilance : le délai est **commun à toutes les zones** (physiologie, pas latitude), comme les autres durées (US-068)

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Fixer le délai au bot
  When le jardinier tape "/calendrier duree chou semis-godet 10-15"
  Then le chou porte un délai semis → godet de 10 à 15 jours pour ce potager

Scénario: Dictée avec godet
  When le jardinier dicte "délai de repiquage en godet des tomates : 15 à 20 jours"
  Then le délai semis → godet de la tomate vaut 15 à 20 jours

Scénario: Sans godet, le sens actuel est gardé
  When le jardinier dicte "délai de repiquage des tomates : 42 à 56 jours"
  Then c'est le délai avant plantation de la tomate qui vaut 42 à 56 jours
  And le délai semis → godet de la tomate est inchangé

Scénario: Jamais déduit
  Given le poireau n'a pas de délai semis → godet
  And il a un délai de levée de 10 à 15 jours
  When j'affiche "/calendrier poireau"
  Then le délai semis → godet est "non renseigné"
```

**Labels GitHub :** `us`, `backend`, `bot`, `referentiel`, `pepiniere`
