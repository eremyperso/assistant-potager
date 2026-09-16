**ID :** US-190
**Titre :** Recueillir le consentement BYOK et livrer le corpus contractuel
**Épic :** ÉPIC 7 — BYOK : la clé et le modèle du jardinier

**Story :**
En tant que propriétaire d'un potager sur le point d'activer ma clé
Je veux lire, en français simple, ce que l'application fera de ma clé et de mes données, ce qu'elle garantit et ce qu'elle ne garantit pas, puis y consentir de façon horodatée et révocable
Afin de savoir exactement à quoi je m'engage, et de pouvoir le prouver ou le retirer

**Contexte fonctionnel :**
Septième US de l'ÉPIC 7 (document d'épic §2.D et §8 ; « US-176 » dans sa numérotation initiale). Elle étend considérablement le CA13 d'US-143. Cadre retenu : **B2C uniquement** — des jardiniers particuliers, en usage domestique. Pas de contrat de sous-traitance (article 28) en v1 ; si un potager venait à être exploité par une structure, la qualification changerait — hors périmètre, à inscrire au registre des risques produit.

🔶 **Point contre-intuitif à porter tel quel dans les textes :** le fait que le jardinier paie l'appel ne le rend pas responsable de traitement. C'est l'éditeur qui décide de la finalité et des moyens (quel prompt, quelles données jointes, quelle fonction déclenche l'appel) ; le jardinier ne choisit que le prestataire d'exécution. **Le BYOK change qui paie, pas qui décide.** Tant que l'application peut utiliser la clé, l'éditeur est responsable de la sécurité et de la loyauté de cette utilisation.

**Point de coordination :** le texte de consentement annonce la règle de cache asymétrique (US-186) *et* l'absence de plafond applicatif (US-189). Il ne se rédige pas avant que ces deux US soient stabilisées.

> ⚠️ Le document d'épic n'est pas un avis juridique. La clause de responsabilité et les textes contractuels doivent être **relus par un professionnel avant mise en ligne** : cette US ne se clôt pas sans cette relecture.

**Critères d'acceptance :**

*Consentement*
- [ ] CA1 : Le consentement est recueilli **avant** la première activation (US-187 / CA6), horodaté, versionné par l'identifiant du texte lu, et rattaché à l'utilisateur et au potager. Une table dédiée le porte, sous RLS, avec date de retrait nullable
- [ ] CA2 : Le texte de chaque version est conservé dans le dépôt et **jamais réécrit en place** : un consentement recueilli sur un texte qu'on ne peut plus reproduire ne prouve rien. Une nouvelle version de texte impose un nouveau consentement avant la prochaine activation
- [ ] CA3 : **L'adresse IP n'est pas enregistrée** : donnée personnelle à justifier, pour une valeur probatoire quasi nulle face à un utilisateur authentifié dont on horodate l'action
- [ ] CA4 : La désactivation de la configuration (US-192) vaut retrait du consentement, horodaté sur la même ligne

*Le texte — huit mentions, en français simple, sans renvoi en note*
- [ ] CA5 : Le fournisseur choisi, **nommé**, et que les données du potager lui seront transmises selon ses propres conditions
- [ ] CA6 : Que la transcription vocale reste assurée par la plateforme, même avec une clé branchée
- [ ] CA7 : La règle de cache, dans les deux sens : *« Les réponses obtenues avec votre clé ne sont jamais réutilisées pour un autre potager. Vous continuez en revanche à bénéficier des réponses déjà payées par la plateforme, ce qui réduit votre consommation. »*
- [ ] CA8 : Que l'application ne bloque rien en cas de dépassement — les alertes informent, seuls les plafonds du compte fournisseur arrêtent
- [ ] CA9 : La recommandation de la clé dédiée, en condition d'activation : clé créée pour cette application, dans un projet ou espace séparé, avec son propre budget, permissions minimales, jamais réutilisée ailleurs
- [ ] CA10 : Ce qui est garanti et prouvé par un test (périmètre, liaison au potager, non-propagation dans le cache, non-journalisation, visibilité, réversibilité, limitation) **et ce qui ne l'est pas**, sans marketing : *« Au moment de l'appel, le serveur de l'application détient votre clé en clair — c'est techniquement nécessaire pour l'utiliser. Le chiffrement protège contre une fuite de la base de données, pas contre l'éditeur lui-même. Les garanties ci-dessus reposent sur le code, les tests et l'engagement contractuel, pas sur une impossibilité technique. C'est pourquoi nous recommandons une clé dédiée à budget limité. »*
- [ ] CA11 : Qu'il peut désactiver à tout moment, ce qui détruit la clé et vaut retrait du consentement
- [ ] CA12 : Qu'il peut consulter et exporter ce que sa clé a servi
- [ ] CA13 : Un test vérifie la présence des huit mentions dans le texte de la version courante — c'est un test sur un texte, et il est voulu tel

*Corpus contractuel*
- [ ] CA14 : Les CGU / CGV portent : le jardinier fournit sa clé et reste titulaire de son compte fournisseur ; la facturation lui est directement imputée par ce fournisseur ; l'éditeur ne revend pas de tokens ; les fonctions susceptibles d'appeler sa clé, énumérées ; l'absence de plafond applicatif et l'obligation de clé dédiée ; les limites de responsabilité ; la procédure en cas de consommation indue ; les modalités de remboursement en cas d'erreur imputable à l'application
- [ ] CA15 : La clause de responsabilité retient le principe suivant, à faire relire : l'éditeur demeure responsable des consommations indues résultant d'une défaillance de l'application, d'un usage non autorisé ou d'une insuffisance de sécurité qui lui est imputable. Une exclusion totale serait fragile et contre-productive sur un produit dont l'argument est le cloisonnement
- [ ] CA16 : La politique de confidentialité porte : le fournisseur LLM comme destinataire ; les finalités ; les durées de conservation (configuration, relevé, consentements) ; les transferts hors EEE ; le sort des prompts et réponses
- [ ] CA17 : La liste des sous-traitants porte : hébergeur, fournisseur LLM par défaut de la plateforme, fournisseurs LLM tiers en BYOK, supervision et journaux, Telegram. Le registre des traitements gagne une entrée « configuration LLM utilisateur » et une entrée « relevé de consommation »
- [ ] CA18 : Relecture par un juriste consignée (date, portée) avant clôture de l'US

*Corpus de connaissance*
- [ ] CA19 : Une fiche `doc_app` explique au jardinier, dans les mots de l'écran, le BYOK et ses garanties ; elle entre dans la table de relecture du corpus et `/help` la référence (US-099 / CA9). Le rendu de l'écran de consentement correspond à la maquette à 375px / 768px / desktop

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : consultation (PWA) | juridique (`docs/RGPD/`)
- Migration BDD requise : **oui** — table de consentement, numéro suivant disponible à l'implémentation (v51 si v48 à v50 sont prises par US-185, US-186 et US-188), sous RLS, purgée avec le potager (US-192)
- Dépendances : **US-187** (l'écran qui appelle le consentement), **US-186** et **US-189** (les règles annoncées). Rattachement RGPD : l'US RGPD du plan initial (US-132)
- Reprend d'US-143 : CA12 (mention), CA13 (étendu)
- Impact tokens : zéro
- Point de vigilance : le rôle propriétaire de la base n'est pas soumis à la RLS — ne pas laisser l'écran suggérer que l'éditeur ne peut pas lire la base. Le CA10 le dit déjà ; aucune autre phrase ne doit le contredire

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Consentement obligatoire avant activation
  Given une clé testée avec succès et aucun consentement enregistré
  When le propriétaire tente d'activer la configuration
  Then l'écran de consentement s'affiche avec le fournisseur nommé
  And l'activation n'a lieu qu'après son accord horodaté

Scénario: Le texte dit le cache dans les deux sens
  Given un propriétaire sur l'écran de consentement
  When il lit le texte
  Then il y est écrit que ses réponses ne servent à aucun autre potager
  And qu'il bénéficie des réponses déjà payées par la plateforme

Scénario: Le texte dit ce qui n'est pas garanti
  Given un propriétaire sur l'écran de consentement
  When il lit le texte
  Then il y est écrit que le serveur détient la clé en clair au moment de l'appel
  And que le chiffrement protège contre une fuite de base, pas contre l'éditeur

Scénario: Nouvelle version du texte
  Given un consentement donné sur la version 1 du texte
  When la version 2 est publiée et le propriétaire réactive sa configuration
  Then un nouveau consentement sur la version 2 est exigé
  And le texte de la version 1 reste consultable dans le dépôt

Scénario: Désactivation vaut retrait
  Given une configuration active avec consentement
  When le propriétaire désactive sa configuration
  Then la date de retrait est renseignée sur le consentement
```

**Labels GitHub :** `us`, `sprint-byok`, `llm`, `rgpd`, `pwa`
