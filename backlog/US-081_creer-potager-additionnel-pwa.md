**ID :** US-081
**Titre :** Créer un potager additionnel depuis la PWA
**Épic :** ÉPIC 5 — Cycle de vie du potager

**Story :**
En tant que jardinier déjà membre d'au moins un potager
Je veux créer un second potager depuis l'interface web
Afin de suivre un autre jardin réel (résidence secondaire, jardin partagé, potager d'un proche) sans devoir passer par un autre compte

**Contexte fonctionnel :**
C'est **le trou fonctionnel principal** identifié par `docs/CONCEPTION_CYCLE_DE_VIE_POTAGER.md` §1.3 et
§5.2 (proposée sous le numéro provisoire US-151) : aujourd'hui, la création de potager n'existe que
dans l'assistant d'onboarding (`frontend/src/views/Onboarding.jsx`, US-058), déclenché par le
`PotagerGate` d'`App.jsx` **uniquement quand l'utilisateur n'a aucun potager**. Dès qu'il en a un, le
chemin de création disparaît définitivement : `PotagerMenu` (US-054) ne propose que « Rejoindre un
potager », « Tous mes potagers » et « Modifier le potager » (US-074). Un utilisateur qui déménage ou
qui aide un proche est bloqué.

Le back est déjà prêt : `POST /potagers` et `creer_potager()` (`app/services/potagers.py`) acceptent
déjà `nom`, `ville`, `latitude`, `longitude`, créent l'appartenance `owner` et positionnent le potager
comme actif. Il manque donc **le point d'entrée UI** et **le choix de ne pas basculer immédiatement**.

Personas visés (§3.1) : U2 propriétaire de deux résidences (~5 %), U3 membre d'un jardin partagé
(~5 %), U4 potagiste aidant un proche (~3 %), U5 en déménagement (~2 %). C'est une action **rare et
explicite**, pas un flux d'auto-service anodin : l'UI ne doit ni la mettre en avant, ni la banaliser.

**Anti-cas à décourager explicitement** (§3.2) : « un potager par saison ». La modale porte un
message court renvoyant vers la clôture de saison (`docs/EPIC_CALENDRIER_CULTURAL.md`), qui reste la
bonne réponse pour repartir à zéro sur le même jardin.

**Critères d'acceptance :**
- [ ] CA1 : `PotagerMenu` propose une entrée « + Créer un nouveau potager », placée après la liste des
      potagers et avant « Rejoindre un potager » / « Tous mes potagers », visible pour **tout**
      utilisateur connecté quel que soit son rôle sur le potager actif (créer son propre potager ne
      dépend d'aucun rôle)
- [ ] CA2 : Cette entrée ouvre une modale légère — champ `nom` (requis) + composant de recherche de
      ville réutilisé tel quel (`frontend/src/components/ui/VilleSearch.jsx`, US-074, facultatif) —
      **sans** étape parcelles ni cultures : l'utilisateur est déjà expérimenté et complétera dans les écrans dédiés
- [ ] CA3 : Une case à cocher « En faire mon potager actif dès maintenant » (cochée par défaut) pilote
      la bascule ; décochée, le potager est créé et l'utilisateur reste sur son potager courant
- [ ] CA4 : `creer_potager()` accepte un paramètre d'activation (défaut : activer, pour ne rien changer
      à l'onboarding US-058) ; le créateur est toujours inséré en `owner`, le potager naît à l'état
      `actif` (US-080) — **création atomique, pas d'état brouillon** (§5.1 du document de conception)
- [ ] CA5 : Après création avec bascule, l'application affiche les données du nouveau potager (même
      comportement de rechargement qu'US-046/US-054) ; sans bascule, le menu se ferme et le nouveau
      potager apparaît dans la liste au prochain affichage
- [ ] CA6 : La modale affiche un encart d'information court : « Tu veux repartir sur une nouvelle
      saison dans le même jardin ? Ce n'est pas un nouveau potager — utilise la clôture de saison. »
- [ ] CA7 : Un nom vide ou composé uniquement d'espaces est refusé côté client et côté API ; un nom
      identique à un potager existant de l'utilisateur est **autorisé** mais signalé par un avertissement non bloquant
- [ ] CA8 : Le même point d'entrée « + Créer un nouveau potager » est disponible dans la vue « Tous mes
      potagers » (`PotagerSelector`, US-048), en miroir du menu — deux chemins, un seul composant de modale
- [ ] CA type (US avec impact visuel/UI) : Le rendu de l'entrée de menu et de la modale est cohérent
      avec le design system (US-052) et les modales existantes (`ModalModifierPotager`) à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (création de potager) + consultation (menu)
- Migration BDD requise : non (US-080 pose déjà `etat`)
- Dépendances : US-080 (état `actif` à la création), US-054 (`PotagerMenu`), US-074 (`VilleSearch`, `POST /potagers` enrichi), US-048 (`creer_potager`)
- **Point ouvert assumé** : aucun quota n'est appliqué à ce stade. Le plafond freemium (recommandation §8.4 : *1 potager actif en gratuit, N en payant, les archivés ne comptent pas*) relève de l'US Stripe/freemium (`US-133` du plan initial, non encore rédigée sous la numérotation réelle). Le message d'erreur de quota devra s'insérer dans cette modale **sans la redessiner** : prévoir l'emplacement, pas la logique.
- Zéro token Groq

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `frontend/src/components/PotagerMenu.jsx`, `frontend/src/components/PotagerSelector.jsx`, nouvelle modale `ModalCreerPotager.jsx`, `app/services/potagers.py`, `main.py` (`POST /potagers`)
- Réutiliser `Modal`, `Field`, `Btn`, `VilleSearch` de `frontend/src/components/ui/` — ne pas recréer de formulaire ad hoc
- Le composant est destiné à deux contextes de layout (menu déroulant et vue « Tous mes potagers ») : appliquer la règle projet **container queries** (`@container`) et non des breakpoints Tailwind (cf. CLAUDE.md)
- `creer_potager()` ne doit pas perdre son comportement actuel pour US-058 : le paramètre d'activation est optionnel avec la valeur d'aujourd'hui par défaut

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Créer un second potager et basculer dessus
  Given un jardinier membre du potager "Jardin de Vitry"
  When il ouvre le menu potager, choisit "Créer un nouveau potager", saisit "Jardin de Bretagne",
       sélectionne la ville "Quimper" et laisse la case "en faire mon potager actif" cochée
  Then le potager "Jardin de Bretagne" est créé avec sa ville et ses coordonnées
  And il en est owner
  And ses saisies suivantes portent sur "Jardin de Bretagne"

Scénario: Créer un potager sans basculer dessus
  Given un jardinier sur son potager principal en pleine saison
  When il crée le potager "Jardin de mes parents" en décochant "en faire mon potager actif"
  Then le potager est créé
  And son potager actif reste son potager principal

Scénario: Création sans localisation
  Given la modale de création ouverte
  When il saisit uniquement un nom et valide
  Then le potager est créé sans ville ni coordonnées, et aucune valeur inventée n'est stockée

Scénario: Nom vide refusé
  Given la modale de création ouverte
  When il valide avec un nom vide
  Then la création est refusée avec un message clair et la modale reste ouverte

Scénario: Rappel saison vs potager
  Given la modale de création ouverte
  Then un encart rappelle que démarrer une nouvelle saison ne nécessite pas un nouveau potager
```

**Labels GitHub :** `us`, `sprint-cycle-vie-potager`, `frontend`, `backend`
