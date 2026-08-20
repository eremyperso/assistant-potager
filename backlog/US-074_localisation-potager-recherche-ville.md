**ID :** US-074
**Titre :** Localiser un potager via une recherche de ville unifiée et réutilisable

**Story :**
En tant que jardinier propriétaire d'un potager
Je veux pouvoir rattacher mon potager à une ville réelle via une recherche unifiée
Afin que la météo et les futures fonctionnalités géolocalisées reposent sur un lieu réel, et non sur des coordonnées jamais renseignées

**Contexte fonctionnel :**
Première US du **Lot C** (`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.2, §7.1 — jusqu'ici « à
rédiger »), déclenchée pour préparer le widget météo de l'écran Vue d'ensemble (US-076).

Le terrain est en partie déjà préparé, mais jamais branché à une UI :
- `Potager.latitude`/`longitude` existent en base depuis le socle multi-tenant (US-040) et
  `POST /potagers` les accepte déjà en paramètres optionnels (`app/services/potagers.py::creer_potager`,
  dont le docstring anticipe explicitement : *« alimentera la météo par potager »*, référence à
  l'ancienne numérotation **US-124** du plan initial `docs/BACKLOG_US_MULTITENANT.md` — jamais
  livrée sous ce numéro, le chantier se poursuit ici sous la numérotation réelle du backlog,
  cf. `README.md` §mapping US-100→US-133 vs US-040→US-049).
- **Mais aucune UI ne les renseigne jamais** : le seul formulaire de création de potager
  (`frontend/src/views/AucunPotager.jsx`) ne capture qu'un `nom`. En pratique, `latitude`/`longitude`
  sont donc toujours `NULL` pour tous les potagers existants.
- Aucune colonne `ville` (libellé affichable) n'existe.
- Aucun moyen de modifier la localisation d'un potager **déjà créé** : pas d'endpoint `PATCH
  /potagers/{id}`. Sans lui, tout potager existant resterait sans localisation pour toujours.
- `docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.2 nomme ce composant « module de recherche de ville
  unifié », pensé pour être réutilisé par la création de potager (cette US) et par l'onboarding
  (US-058, non livrée, qui a posé une colonne `Potager.ville` provisoire en texte libre — cette
  US-074, si elle est livrée en premier, pose directement cette même colonne avec sa vraie
  sémantique ; sinon elle la réutilise telle quelle).

**Critères d'acceptance :**
- [ ] CA1 : Nouveau composant de recherche de ville réutilisable : à la saisie, interroge l'API
      de géocodage Open-Meteo (`https://geocoding-api.open-meteo.com/v1/search`, gratuite, sans
      clé — même fournisseur que `utils/meteo.py`), affiche une liste de résultats réels (nom de
      la commune, région/pays pour désambiguïser) et retient latitude/longitude/libellé au choix
      de l'utilisateur
- [ ] CA2 : Nouvelle colonne `Potager.ville` (string, nullable) — réutilise celle posée par
      US-058 si elle a été livrée en premier, sinon la crée
- [ ] CA3 : Le formulaire de création de potager (`AucunPotager.jsx`) intègre ce champ de
      recherche, à titre facultatif ; `POST /potagers` (déjà prêt à recevoir latitude/longitude)
      est complété du champ `ville`
- [ ] CA4 : Nouvel endpoint `PATCH /potagers/{id}` (nom, ville, latitude, longitude tous
      optionnels), réservé au rôle `owner` du potager ciblé (`require_role`, US-047) — seul moyen
      de localiser ou corriger un potager déjà créé
- [ ] CA5 : Nouvelle entrée « Modifier le potager » dans `PotagerMenu` (`frontend/src/components/PotagerMenu.jsx`),
      visible uniquement pour le owner du potager actif, ouvrant un petit formulaire (nom +
      recherche de ville) pré-rempli avec les valeurs actuelles
- [ ] CA6 : Un potager sans localisation n'affiche jamais de valeur inventée (jamais de
      « 0, 0 » par défaut) — le champ reste simplement absent tant qu'il n'a pas été renseigné
- [ ] CA7 : Une recherche vide ou en échec réseau affiche un message clair ; le formulaire de
      création/modification reste utilisable sans localisation dans tous les cas (rien n'est
      bloquant)
- [ ] CA type (US avec impact visuel/UI) : Le rendu du champ de recherche et du formulaire
      « Modifier le potager » est cohérent avec les composants du design system (US-052) à
      375px/768px/desktop — aucune maquette Claude Design dédiée n'existe pour ce formulaire
      précis à ce jour

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (création/modification potager), consultation (recherche de ville)
- Migration BDD requise : oui — `Potager.ville` (string, nullable), une seule migration (ex. `migration_v26.sql`, sous réserve de l'ordre réel de livraison face à US-058) ; `latitude`/`longitude` existent déjà, aucune migration nécessaire pour elles
- Dépendances : US-048 (`creer_potager`, `POST /potagers` déjà prêts à recevoir latitude/longitude), US-047 (`require_role`), US-052 (design system)
- Prépare : US-075 (endpoint météo web, consomme la localisation posée ici) ; réutilisable par la version future d'US-058 (onboarding)

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Localiser un potager à la création
  Given un utilisateur sans potager, sur l'écran de création
  When il saisit "Vitry" dans le champ de recherche de ville et choisit "Vitry-sur-Seine" dans les résultats
  And il valide la création du potager
  Then le potager est créé avec ville = "Vitry-sur-Seine" et les latitude/longitude correspondantes

Scénario: Localiser un potager existant, sans localisation
  Given un potager créé avant l'existence de cette fonctionnalité, sans ville ni coordonnées
  And l'utilisateur en est owner
  When il ouvre "Modifier le potager" depuis le menu Compte, recherche puis choisit une ville, et valide
  Then le potager est mis à jour avec cette ville et ses coordonnées, sans autre changement

Scénario: Un membre non-owner ne peut pas modifier la localisation
  Given un potager avec un membre au rôle "editor"
  When ce membre tente d'appeler PATCH /potagers/{id}
  Then la requête est refusée avec le message de permission standard (US-047)

Scénario: Recherche sans résultat
  Given le formulaire de recherche de ville ouvert
  When l'utilisateur saisit une chaîne qui ne correspond à aucune ville connue
  Then aucune liste de résultats n'apparaît, un message l'indique clairement, et le formulaire reste utilisable sans localisation
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `backend`, `lot-c`
