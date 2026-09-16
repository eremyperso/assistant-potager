**ID :** US-191
**Titre :** Échouer explicitement quand le fournisseur du potager échoue, sans repli silencieux sur la plateforme
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager ayant branché sa clé
Je veux, quand mon fournisseur ou mon modèle échoue, un message qui me dise que ma configuration en est la cause probable, depuis quand, et quoi faire
Afin de ne pas tenir la plateforme pour responsable de mon propre choix, et de ne jamais voir mes données partir vers un service auquel je n'ai pas consenti

**Contexte fonctionnel :**
Huitième US de l'ÉPIC 7 (document d'épic §7.2 ; « US-177 » dans sa numérotation initiale). Reprend tels quels les CA10 et CA15 d'US-143.

⚖️ **Arbitrage tranché — aucun repli silencieux.** Un repli invisible vers la clé de la plateforme ferait payer à la plateforme la panne du fournisseur choisi par l'utilisateur, et enverrait ses données à un service auquel il n'a pas consenti pour cet appel. L'échec explicite est à la fois plus honnête et moins coûteux.

🔶 **Ne pas désactiver automatiquement la configuration sur un échec d'authentification** : une coupure réseau du fournisseur produit parfois le même code, et une désactivation automatique ferait silencieusement repartir les appels sur la plateforme — exactement ce que cette US interdit.

**Critères d'acceptance :**

*Pas de repli*
- [ ] CA1 : Si le fournisseur du potager échoue ou refuse l'appel (authentification, quota, délai, réseau, modèle inconnu), **aucun appel n'est effectué sur la clé de la plateforme** pour cette requête. Un test le prouve sur chaque nature d'échec
- [ ] CA2 : Aucune désactivation automatique de la configuration, quelle que soit la nature ou la répétition de l'échec. Seul le propriétaire désactive

*Le message*
- [ ] CA3 : Le message servi au jardinier désigne **la configuration du potager comme cause probable**, nomme la nature de l'échec en clair, et propose deux issues : réessayer, ou désactiver la configuration (lien vers les paramètres depuis la PWA, rappel de la marche à suivre depuis Telegram)
- [ ] CA4 : Pour un échec d'authentification, le message dit **depuis quand** la configuration ne fonctionne plus : la date de dernière validation réussie (US-185) et la date du premier échec d'authentification observé depuis
- [ ] CA5 : Quand le modèle configuré produit une sortie **inexploitable** (JSON malformé, intention non reconnue de façon répétée), le message désigne la configuration comme cause probable et propose de revenir au modèle de la plateforme — sans quoi c'est la plateforme que le jardinier tiendra pour responsable du modèle qu'il a choisi lui-même
- [ ] CA6 : Le message est le même dans le bot et dans la PWA (même service, même texte, même garde de rôle : un membre non propriétaire voit l'échec sans le lien vers les paramètres)

*Mode dégradé*
- [ ] CA7 : Les fonctions déterministes continuent de fonctionner (commandes, catalogue SQL, cache, savoir), comme dans tout mode dégradé (US-092 / CA10). Un test le vérifie avec un fournisseur qui refuse tout
- [ ] CA8 : La transcription vocale, qui reste sur la plateforme (US-186 / CA8), continue de fonctionner quand le fournisseur du potager est en panne : un vocal est transcrit, puis la question échoue explicitement si elle exige le modèle

*Journal*
- [ ] CA9 : Chaque échec écrit sa ligne dans le journal d'imputation avec son issue classée (US-188 / CA4-5) ; la clé n'apparaît dans aucun journal sur ces chemins (US-185 / CA12)
- [ ] CA10 : Le propriétaire est prévenu par Telegram au **premier** échec d'authentification depuis la dernière validation réussie — une fois, pas à chaque échec — pour ne pas découvrir la panne au bout d'une semaine

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : transverse (passerelle LLM, messages bot et PWA)
- Migration BDD requise : **non**
- Dépendances : **US-186** (résolution), **US-188** (journal, pour le CA9 ; le reste de l'US n'en dépend pas), **US-185** (date de validation)
- Reprend d'US-143 : CA10, CA15
- Impact tokens : zéro — aucun appel ajouté, et **aucun appel plateforme** déclenché par un échec tiers
- Point de vigilance : « réessayer » ne doit pas être une boucle. Un seul essai à la demande du jardinier ; pas de nouvelle tentative automatique qui ferait payer trois appels pour une panne

**Notes techniques (pour Persona Developer) :**
- Les chemins d'erreur de la passerelle existent déjà (mode dégradé d'US-092) : cette US y ajoute la distinction « origine de la clé » dans le message, pas un second mécanisme
- La date du premier échec d'authentification observé se déduit du journal d'US-188 (première ligne d'issue « authentification » postérieure à la dernière validation) ; pas de colonne supplémentaire

**Estimation :** 3 points

**Scénario Gherkin :**
```gherkin
Scénario: Fournisseur du potager en panne
  Given un fournisseur configuré qui refuse tous les appels
  When le jardinier pose une question de raisonnement
  Then il reçoit un message désignant sa configuration comme cause probable
  And aucun appel n'est effectué sur la clé de la plateforme
  And ses commandes déterministes continuent de fonctionner

Scénario: Clé révoquée côté fournisseur
  Given une configuration validée le 3 septembre et une clé révoquée depuis
  When le jardinier pose une question
  Then le message indique un échec d'authentification depuis la première tentative échouée
  And rappelle que la dernière validation réussie date du 3 septembre
  And la configuration reste active jusqu'à décision du propriétaire

Scénario: Modèle non supporté produisant des sorties inexploitables
  Given un potager configuré sur un modèle hors liste supportée
  When ce modèle renvoie des sorties inexploitables de façon répétée
  Then le message désigne la configuration du potager comme cause probable
  And il propose de revenir au modèle de la plateforme

Scénario: Une seule notification Telegram
  Given un premier échec d'authentification ce matin
  When trois autres échecs suivent dans la journée
  Then le propriétaire a reçu une seule notification Telegram
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `security`
