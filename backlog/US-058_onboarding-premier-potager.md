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
le même panneau de marque pour porter la progression. Cette US constitue le **Lot H**
(`docs/ANALYSE_REFONTE_UI_WEB_2026.md` §5.8, §7.1) — le seul lot de la refonte 2026
volontairement placé en fin de portefeuille, sans bloquer ni être bloqué par les autres lots.

**Mise à jour du 17/08/2026 (Lot C livré) :** à la première rédaction, trois champs de la
maquette n'avaient aucun équivalent backend. Ce n'est plus vrai que pour deux d'entre eux —
le Lot C (US-074 à US-077) a depuis livré la colonne `Potager.ville` et le composant de
recherche `VilleSearch` (autocomplete + géocodage Open-Meteo,
`frontend/src/components/ui/VilleSearch.jsx`), déjà réutilisés ailleurs
(`ModalModifierPotager`, `AucunPotager`) et acceptés tels quels par `POST /potagers`
(`ville`, `latitude`, `longitude`). L'étape "Votre potager" de cette US réutilise ce
composant sans rien ajouter ni géocoder elle-même. Restent traités avec un périmètre
volontairement réduit :
- le **type de sol** (étape 2) devient une colonne texte informative sur `Parcelle`,
  non exploitée par les calculs existants ;
- la **sélection de cultures** (étape 3) reste informative dans le récapitulatif, sans
  créer de fiche `CultureConfig` (son schéma dépend du Lot E — son seul écran a été
  absorbé par Stocks/US-073 depuis, le schéma horticole étendu reste, lui, non cadré).

Cette US reste **priorisée en dernier** dans le protocole de lotissement (§7.1) : elle ne
bloque et n'est bloquée par aucun autre lot, mais sa version pleinement fidèle à la maquette
dépend encore du Lot E (Lot C, lui, est désormais intégralement soldé).

**Critères d'acceptance :**
- [ ] CA1 : L'assistant se déclenche automatiquement pour un utilisateur qui vient de créer
      son compte et n'a encore aucun potager ; il reste également accessible à tout moment
      via l'action "Créer un potager" déjà existante (US-048/US-054)
- [ ] CA2 : Étape "Votre potager" — nom du potager (obligatoire) et commune (facultative,
      via le composant `VilleSearch` déjà livré par le Lot C : recherche avec autocomplete,
      géocodage Open-Meteo, retourne `{ ville, latitude, longitude }`), conservés en état
      local le temps de l'assistant (aucun appel API à cette étape) ; un encart permet de
      basculer vers la saisie d'un code d'invitation (réutilise le parcours existant de
      l'US-048 sans changement de logique) — si un code valide est saisi, l'utilisateur
      rejoint directement ce potager et le reste de l'assistant est ignoré
- [ ] CA3 : Étape "Première parcelle" — nature de l'espace (pleine terre / pépinière), nom,
      surface, exposition (choix parmi Plein sud / Est / Ouest / Nord / Mi-ombre, valeurs
      libres déjà supportées par la colonne texte `Parcelle.exposition`) et type de sol
      (nouvelle colonne informative `Parcelle.type_sol`, choix parmi Limoneux / Argileux /
      Sableux / Terreau / Je ne sais pas), également conservés en état local ; seul le nom
      du potager (CA2) est obligatoire pour terminer l'assistant, cette étape peut être passée
- [ ] CA4 : Étape "Cultures" — sélection multiple parmi un catalogue de 12 cultures courantes
      (Tomate, Courgette, Salade, Carotte, Haricot vert, Radis, Pomme de terre, Oignon,
      Fraise, Poireau, Concombre, Betterave — Tomate et Courgette pré-sélectionnées par
      défaut, comme dans la maquette), reprise dans le récapitulatif à titre indicatif
      uniquement ; aucune fiche `CultureConfig` ni événement n'est créé à partir de cette
      sélection
- [ ] CA5 : Étape "Récapitulatif" — relit les informations saisies aux étapes précédentes ;
      la validation finale ("Entrer dans mon potager") persiste tout en une fois : appel à
      `POST /potagers` (nom, `ville`/`latitude`/`longitude` si une commune a été retenue via
      CA2) puis, si une parcelle a été renseignée, au nouvel endpoint `POST /parcelles`
      (jusqu'ici réservé au bot Telegram via `utils/parcelles.create_parcelle`) — seul ce
      moment crée des données en base, puis l'utilisateur est redirigé vers l'écran d'accueil
      avec ce potager actif (comportement déjà garanti par `creer_potager`, US-048) ; comme
      dans la maquette, un encart informatif suggère de relier Telegram (US-045) en prochaine
      étape, sans lien fonctionnel ni action requise à ce stade
- [ ] CA6 : La navigation "Précédent" / "Passer" fonctionne comme dans la maquette :
      "Précédent" est actif dès l'étape 2 ; "Passer" n'apparaît que sur les étapes 2 et 3
      ("Première parcelle", "Cultures") — ni sur l'étape 1, dont le nom du potager est
      obligatoire, ni sur le récapitulatif, dont le seul bouton est "Entrer dans mon
      potager" ; fermer ou quitter l'assistant avant l'étape "Récapitulatif" ne crée ni
      potager ni parcelle en base, la persistance n'ayant lieu qu'à la validation finale (CA5)
- [ ] CA type (US avec impact visuel/UI) : Le rendu (4 étapes, panneau de progression
      desktop et barre d'étapes compacte mobile) correspond visuellement à la maquette de
      référence à 375px/768px/desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement (création potager + parcelle), consultation (récapitulatif)
- Migration BDD requise : oui — `Parcelle.type_sol` (string, nullable) seule ; `Potager.ville`
  existe déjà (`migration_v26.sql`, US-074) et n'est pas retouchée par cette US
- Dépendances : US-056 (écran de connexion — point d'entrée juste après l'inscription),
  US-048 (création de potager, invitations — logique réutilisée), US-046 (potager actif),
  US-052 (design system), US-074 (composant `VilleSearch` et colonne `Potager.ville`,
  Lot C — réutilisés tels quels par CA2)
- Points ouverts assumés (non bloquant pour cette US, à raccorder plus tard) : la sélection
  de cultures (CA4) ne crée aucune donnée persistée tant que le Lot E n'a pas défini le
  schéma `CultureConfig` étendu (§5.3) — son seul écran a été absorbé par Stocks (US-073),
  ce schéma horticole reste non cadré

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
  When il renseigne un nom de potager, sélectionne une commune via la recherche de ville, crée une première parcelle avec sa nature et son exposition, sélectionne quelques cultures, puis valide le récapitulatif
  Then un potager (avec sa localisation) et sa première parcelle sont créés, et il devient owner du potager, désormais actif

Scénario: Parcours minimal
  Given un utilisateur à l'étape "Votre potager"
  When il ne renseigne que le nom du potager et passe toutes les étapes suivantes
  Then le potager est créé sans parcelle ni culture, et l'assistant se termine normalement
```

**Labels GitHub :** `us`, `sprint-refonte-ui-2026`, `frontend`, `backend`, `onboarding`, `lot-h`
