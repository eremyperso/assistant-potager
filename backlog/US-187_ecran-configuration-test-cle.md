**ID :** US-187
**Titre :** Configurer et tester sa clé personnelle depuis les paramètres du potager
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager disposant d'une clé chez un fournisseur compatible
Je veux saisir mon fournisseur, ma clé et mon modèle, les tester, et voir ce qui est enregistré sans jamais revoir ma clé
Afin d'activer mon propre service en confiance, en sachant exactement ce qui est supporté et ce qui l'est à mes risques

**Contexte fonctionnel :**
Quatrième US de l'ÉPIC 7 (document d'épic §3 « US-173 » dans sa numérotation initiale). Elle est l'interface du coffre (US-185) et de la résolution (US-186) : elle n'ajoute aucune règle métier, elle les rend saisissables. Une clé d'API est un engagement financier personnel : la confier au niveau du potager partagé, sans restriction de rôle, exposerait son propriétaire aux dépenses des autres membres — d'où le **propriétaire seul**.

Reprend tels quels les CA2, CA3, CA6 et CA9 d'US-143. Le consentement qui précède l'activation est porté par US-190 : cette US livre l'écran avec un emplacement pour lui, et **l'activation reste impossible tant qu'US-190 n'est pas livrée** (le bouton d'activation est présent, inactif, et le dit).

**Critères d'acceptance :**

*Accès*
- [ ] CA1 : La configuration se fait depuis l'écran de paramètres du potager (US-082) et n'est accessible **qu'au propriétaire** (rôles d'US-047). Un membre éditeur ou lecteur ne voit ni la section, ni les endpoints (refus explicite côté API)

*Saisie*
- [ ] CA2 : Le formulaire porte : fournisseur (liste fermée de fournisseurs connus + « autre, compatible OpenAI » avec adresse de base libre), clé, modèle, budget mensuel de référence en euros (US-189 — champ obligatoire à l'activation, déclaratif, non bloquant, et l'écran le dit)
- [ ] CA3 : Une liste de modèles **testés et supportés** est affichée, distincte des modèles utilisables **aux risques du potager**. Le choix reste libre, l'information est explicite
- [ ] CA4 : Un bouton « Tester la clé » effectue **l'appel réel le plus petit possible** sur la clé et le modèle saisis, et affiche le résultat en clair (succès avec le modèle réellement servi, ou la nature de l'échec : authentification, modèle inconnu, adresse injoignable, quota). Cet appel compte chez le fournisseur du potager, jamais chez la plateforme

*Activation*
- [ ] CA5 : Une clé qui échoue au test **n'est jamais enregistrée comme active** ; une clé validée renseigne la date de dernière validation. L'invariant est aussi tenu par la base (US-185 / CA2)
- [ ] CA6 : L'activation n'est possible qu'après le consentement d'US-190 ; tant qu'il n'est pas livré, l'écran l'annonce et n'active rien
- [ ] CA7 : Enregistrer une nouvelle clé remplace l'ancienne, qui est détruite (une configuration par potager, US-185 / CA4). Le remplacement prend effet à la requête suivante (US-186 / CA6)

*Non-exposition*
- [ ] CA8 : Après enregistrement, l'écran n'affiche jamais la clé complète : seuls les derniers caractères sont visibles, à titre de repère
- [ ] CA9 : **Aucune réponse d'API ne contient la clé**, ni en lecture de configuration, ni en écho de la saisie, ni dans un message d'erreur. Un test le vérifie sur chaque endpoint de l'US
- [ ] CA10 : La clé n'apparaît dans aucun journal, y compris sur le chemin du test de clé et sur ses erreurs (test d'US-185 / CA12, chemin « test de clé »)

*Information*
- [ ] CA11 : L'écran dit, en toutes lettres et sans renvoi : que la transcription vocale reste assurée par la plateforme ; que l'application ne bloque rien en cas de dépassement de budget ; que la clé doit être une clé **dédiée** (projet ou espace de travail séparé, budget propre, permissions minimales, jamais réutilisée ailleurs) — cette recommandation est une **condition d'activation**, pas un conseil
- [ ] CA12 : Le rendu correspond visuellement à la maquette de référence à 375px / 768px / desktop. Le composant naît avec `container-type: inline-size` sur son wrapper (règle du projet)

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (paramètres PWA) | interaction API
- Migration BDD requise : **non** (table créée par US-185)
- Dépendances : **US-185**, **US-186**, **US-082** (écran de paramètres, livrée), **US-047** (rôles, livrée). **US-190** conditionne l'activation, pas la livraison de l'écran
- Reprend d'US-143 : CA2, CA3, CA6, CA9
- Impact tokens : **un seul appel ajouté**, le test de clé, sur la clé du jardinier — jamais sur celle de la plateforme
- Conception : maquette à concevoir dans le projet Claude Design « potager 2026 » et à geler avant implémentation, même règle que l'écran Stocks
- Point de vigilance : « autre fournisseur » avec adresse de base libre est une surface d'erreur (adresse fausse, service non compatible). Le test de clé est ce qui la ferme : sans test réussi, pas d'activation

**Notes techniques (pour Persona Developer) :**
- Endpoints : lecture, écriture et suppression de la configuration du potager, plus un endpoint de test ; tous derrière la garde de rôle propriétaire
- Le test de clé passe par la passerelle (type d'appel dédié, `test_cle`), jamais par un client construit dans l'endpoint : l'audit AST d'US-092 l'interdirait, à raison
- La lecture de configuration renvoie l'empreinte, jamais les colonnes chiffrées

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Branchement d'une clé personnelle
  Given un propriétaire de potager disposant d'une clé chez un fournisseur compatible
  When il la saisit dans les paramètres de son potager et lance le test
  Then le test réussit et affiche le modèle réellement servi
  And la clé est enregistrée chiffrée avec sa date de validation

Scénario: Clé invalide refusée
  Given une clé erronée saisie dans les paramètres
  When le test est lancé
  Then l'échec est affiché avec sa nature
  And aucune configuration active n'est enregistrée

Scénario: Clé jamais exposée
  Given une configuration enregistrée
  When le propriétaire revient sur l'écran de paramètres
  Then seuls les derniers caractères de la clé sont visibles
  And aucune réponse d'API ne contient la clé

Scénario: Membre non propriétaire
  Given un membre éditeur d'un potager partagé
  When il ouvre les paramètres du potager
  Then la section de configuration de l'IA ne lui est pas accessible
  And l'API refuse ses appels sur ces endpoints

Scénario: Modèle hors liste supportée
  Given un modèle saisi qui n'est pas dans la liste testée
  When le propriétaire le sélectionne
  Then l'écran indique qu'il est utilisable aux risques du potager
  And le choix reste possible
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`, `pwa`
