**ID :** US-202
**Titre :** Réordonner les parcelles depuis la Vue plan
**Épic :** ÉPIC 10 — Plan : l'occupation en rangs et le zoom d'information *(numéro à valider, voir le plan des épics 9 à 12)*

**Story :**
En tant que jardinier
Je veux ranger mes parcelles dans l'ordre où je les parcours au jardin
Afin que le Plan se lise comme je marche, du portail au fond du terrain

**Contexte fonctionnel :**
Le Plan n'a ni position ni forme : l'**ordre** des parcelles est la seule mise en page qui existe (v1 : « l'ordre d'affichage est déjà une donnée »). Il se règle aujourd'hui au bot, parcelle par parcelle (`/parcelle modifier <nom> ordre=N`), et gouverne déjà l'ordre des listes du bot (menu de parcelles d'US-021, trié par `Parcelle.ordre`).

La v3 met un bouton « Réordonner » dans la barre de la Vue plan : « seule action de mise en page, glisse l'ordre des parcelles. Rien d'autre n'est déplaçable » (règle 13). C'est **la seule écriture** que les wireframes ouvrent dans ces écrans (RT1) : un réglage d'affichage, pas une donnée du jardin.

**Critères d'acceptance :**
- [ ] CA1 : « Réordonner », dans la barre de la Vue plan, fait passer l'écran en **mode rangement** : chaque parcelle se réduit à une ligne (nom, poignée, boutons « monter » et « descendre »), pépinières comprises. « Terminer » enregistre, « Annuler » rend l'ordre précédent
- [ ] CA2 : L'ordre se change par glisser-déposer **et** par les boutons « monter / descendre », utilisables au clavier et au lecteur d'écran ; à 375 px, les boutons suffisent, le glisser n'y est pas exigé
- [ ] CA3 : L'enregistrement envoie **l'ordre complet en une requête**, appliqué d'un bloc (tout ou rien). Si la liste envoyée ne correspond plus aux parcelles du potager (une parcelle ajoutée ou supprimée entre-temps, par un autre membre ou au bot), la requête est refusée et l'écran propose de recharger, sans rien écrire
- [ ] CA4 : Seuls le propriétaire et l'éditeur voient « Réordonner » ; l'API refuse le membre en lecture seule (US-047) ; l'écriture est restreinte au potager consulté (US-042)
- [ ] CA5 : Le nouvel ordre vaut **partout** où l'ordre des parcelles s'applique : Vue plan, onglet Parcelles, listes et menus du bot (`/parcelle lister`, choix d'une parcelle à la confirmation d'un geste)
- [ ] CA6 : Réordonner n'écrit que l'ordre : aucun événement, aucun nom, aucune autre propriété de parcelle n'est touché, et rien n'apparaît au Journal
- [ ] CA7 : La commande du bot `/parcelle modifier <nom> ordre=N` continue de fonctionner, et les deux voies produisent un ordre cohérent (pas de doublon ni de trou visible à l'écran)
- [ ] CA8 : La fiche `parcelles-et-plan.md` dit comment ranger ses parcelles, depuis l'application ou au bot (US-099 / CA9)
- [ ] CA9 : Des tests couvrent : ordre complet appliqué, liste obsolète refusée sans écriture, lecteur refusé, parcelle d'un autre potager refusée, cohérence avec la commande du bot, logique « monter / descendre » (`npm test`)
- [ ] CA10 : Le mode rangement correspond à la maquette haute fidélité gelée à 375 px, 768 px et desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA), réglage de parcelle
- Migration BDD requise : **non** — `parcelles.ordre` existe
- Dépendances : **US-200** (Vue plan), US-047 (rôles, livrée)
- Impact tokens : zéro
- Point de vigilance : l'endpoint écrit un **ordre**, pas une position par parcelle ; renuméroter proprement de 1 à N à chaque enregistrement évite les doublons laissés par des saisies anciennes au bot
- Point de vigilance : aucun autre déplacement n'est permis (v3 règle 12) ; le mode rangement ne doit jamais laisser croire qu'on place des cultures
- Wireframe : v3 § 2 (barre de l'écran) et règle 13

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Ranger les parcelles
  Given la Vue plan affiche planche-centrale, planche-courges, planche-ombre
  When j'appuie sur "Réordonner"
  And je fais monter planche-ombre en première position
  And j'appuie sur "Terminer"
  Then la Vue plan affiche planche-ombre, planche-centrale, planche-courges
  And le bot liste les parcelles dans ce même ordre

Scénario: Au clavier
  Given le mode rangement est ouvert
  When je place le focus sur planche-courges et j'active "monter"
  Then planche-courges passe avant planche-centrale

Scénario: Liste devenue obsolète
  Given un autre membre a ajouté une parcelle pendant que je range les miennes
  When j'appuie sur "Terminer"
  Then l'ordre n'est pas enregistré
  And l'écran me propose de recharger les parcelles

Scénario: Lecture seule
  Given je suis membre du potager en lecture seule
  When j'ouvre la Vue plan
  Then le bouton "Réordonner" n'est pas affiché
```

**Labels GitHub :** `us`, `backend`, `frontend`, `pwa`, `plan`, `parcelles`
