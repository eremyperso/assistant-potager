**ID :** US-058
**Titre :** Guider la création du premier potager par un assistant en 4 étapes
**Épic :** ÉPIC 2 — Identité & accès

**Story :**
En tant qu'utilisateur qui vient de créer son compte
Je veux être guidé pour créer mon premier potager et sa première parcelle
Afin d'entrer dans une application déjà utile, plutôt que sur un potager vide sans mode d'emploi

**Contexte fonctionnel :**
Aujourd'hui, un compte sans potager reçoit une liste vide (`GET /potagers`, US-046 CA5) sans
parcours dédié — c'est au frontend de proposer la création. La maquette Claude Design
"potager 2026" introduit un module `onboarding-screens.jsx` (fichier focal
`Potager - Premier potager.html`) : un assistant en 4 étapes (Potager → Parcelle →
Cultures → Récapitulatif), affiché juste après l'écran de connexion (US-056), qui reprend
le même panneau de marque pour porter la progression. Voir `docs/ANALYSE_REFONTE_UI_WEB_2026.md`
§5.8.

**Trois champs de la maquette n'ont pas d'équivalent backend aujourd'hui** et sont traités
avec un périmètre volontairement réduit dans cette US (voir §5.8 pour le détail) :
- la **Commune** (étape 1) devient une simple colonne texte (`Potager.ville`), sans
  géocodage — la recherche/autocomplete réelle est le périmètre du Lot C ;
- le **type de sol** (étape 2) devient une colonne texte informative sur `Parcelle`,
  non exploitée par les calculs existants ;
- la **sélection de cultures** (étape 3) reste informative dans le récapitulatif, sans
  créer de fiche `CultureConfig` (son schéma dépend du Lot E, non cadré).

Cette US est **priorisée en dernier** dans le protocole de lotissement (§7.1) : elle ne
bloque et n'est bloquée par aucun autre lot, mais sa version pleinement fidèle à la maquette
dépend de travaux non encore cadrés (Lots C et E).

**Critères d'acceptance :**
- [ ] CA1 : L'assistant se déclenche automatiquement pour un utilisateur qui vient de créer
      son compte et n'a encore aucun potager ; il reste également accessible à tout moment
      via l'action "Créer un potager" déjà existante (US-048/US-054)
- [ ] CA2 : Étape "Votre potager" — nom du potager (obligatoire) et commune (facultative,
      nouvelle colonne `Potager.ville`), conservés en état local le temps de l'assistant
      (aucun appel API à cette étape) ; un encart permet de basculer vers la saisie d'un
      code d'invitation (réutilise le parcours existant de l'US-048 sans changement de
      logique) — si un code valide est saisi, l'utilisateur rejoint directement ce potager
      et le reste de l'assistant est ignoré
- [ ] CA3 : Étape "Première parcelle" — nature de l'espace (pleine terre / pépinière), nom,
      surface, exposition (valeurs déjà supportées) et type de sol (nouvelle colonne
      informative `Parcelle.type_sol`), également conservés en état local ; seul le nom du
      potager (CA2) est obligatoire pour terminer l'assistant, cette étape peut être passée
- [ ] CA4 : Étape "Cultures" — sélection multiple parmi une liste de cultures courantes,
      reprise dans le récapitulatif à titre indicatif uniquement ; aucune fiche
      `CultureConfig` ni événement n'est créé à partir de cette sélection
- [ ] CA5 : Étape "Récapitulatif" — relit les informations saisies aux étapes précédentes ;
      la validation finale ("Entrer dans mon potager") persiste tout en une fois : appel à
      `POST /potagers` (potager + commune) puis, si une parcelle a été renseignée, au
      nouvel endpoint `POST /parcelles` (jusqu'ici réservé au bot Telegram via
      `utils/parcelles.create_parcelle`) — seul ce moment crée des données en base,
      puis l'utilisateur est redirigé vers l'écran d'accueil avec ce potager actif
      (comportement déjà garanti par `creer_potager`, US-048)
- [ ] CA6 : La navigation "Précédent" et "Passer" (étapes 2 à 4) fonctionne comme dans la
      maquette ; fermer ou quitter l'assistant avant l'étape "Récapitulatif" ne crée ni
      potager ni parcelle en base, la persistance n'ayant lieu qu'à la validation finale (CA5)
- [ ] CA type (US avec impact visuel/UI) : Le rendu (4 étapes, panneau de progression
      desktop et barre d'étapes compacte mobile) correspond visuellement à la maquette de
      référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (création potager + parcelle), consultation (récapitulatif)
- Migration BDD requise : oui — `Potager.ville` (string, nullable) et `Parcelle.type_sol` (string, nullable), une seule migration (ex. migration_v26.sql)
- Dépendances : US-056 (écran de connexion — point d'entrée juste après l'inscription), US-048 (création de potager, invitations — logique réutilisée), US-046 (potager actif), US-052 (design system)
- Points ouverts assumés (non bloquants pour cette US, à raccorder plus tard) : le champ Commune sera complété par le module de recherche de ville + lat/long du Lot C (§5.2, même colonne réutilisée) ; la sélection de cultures ne crée aucune donnée persistée tant que le Lot E n'a pas défini le schéma `CultureConfig` étendu (§5.3)

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Déclenchement automatique après inscription
  Given un utilisateur vient de créer son compte et n'a aucun potager
  When il se connecte pour la première fois
  Then l'assistant de création du premier potager démarre à l'étape "Votre potager"

Scénario: Rejoindre un potager existant depuis l'assistant
  Given un utilisateur au démarrage de l'assistant
  When il saisit un code d'invitation valide dans l'encart dédié
  Then il devient membre du potager correspondant et entre directement dans l'application, sans terminer les étapes restantes

Scénario: Parcours complet
  Given un utilisateur à l'étape "Votre potager"
  When il renseigne un nom de potager, une commune, crée une première parcelle avec sa nature et son exposition, sélectionne quelques cultures, puis valide le récapitulatif
  Then un potager et sa première parcelle sont créés, et il devient owner du potager, désormais actif

Scénario: Parcours minimal
  Given un utilisateur à l'étape "Votre potager"
  When il ne renseigne que le nom du potager et passe toutes les étapes suivantes
  Then le potager est créé sans parcelle ni culture, et l'assistant se termine normalement
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `backend`, `onboarding`
