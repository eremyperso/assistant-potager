# Pilotage LLM — registre du traitement « consommation par potager et par jardinier »

**Produit par US-319 (CA12, ÉPIC 18). À intégrer par US-132 (RGPD & conformité) au registre des traitements.**

Cette fiche décrit le traitement que fait la vue « Potagers et jardiniers » de la PWA d'administration
(`/pilotage/`). Les autres vues de la PWA lisent la même table, sans la ventiler par personne.

## Fiche du traitement

| Rubrique | Contenu |
|---|---|
| **Nom** | Suivi de la consommation de l'assistant par potager et par jardinier |
| **Finalité** | Exploitation (repérer un usage anormal, dimensionner le service) et facturation (fonder un prix sur des profils d'usage mesurés). Aucune autre finalité : ni prospection, ni profilage commercial, ni décision automatisée sur un jardinier. |
| **Base légale** (à confirmer par US-132) | Intérêt légitime de l'exploitant à connaître le coût de son service ; exécution du contrat pour la facturation d'un abonnement. |
| **Personnes concernées** | Les jardiniers inscrits (compte web ou Telegram) et les membres des potagers. |
| **Données traitées** | Par appel au modèle, une ligne de `conso_tokens` : date, type d'appel, modèle, nombre de jetons (ou secondes d'audio, ou caractères), latence, issue, canal, provenance, coût estimé, version de l'application, identifiant du potager et du jardinier. La vue y joint le **nom du potager**, l'**adresse e-mail** du jardinier, son rôle dans un potager, le nombre de ses potagers et sa date d'inscription. |
| **Données jamais traitées par cette vue** | Le **contenu de message** (texte écrit, dictée, réponse du compagnon), les données de culture, le carnet, la localisation, le nom d'affichage du jardinier. Un compte sans adresse e-mail est désigné par son numéro. |
| **Destinataires** | L'administrateur de la plateforme seulement (compte désigné par `ADMIN_EMAIL`). Aucune transmission à un tiers. |
| **Accès** | Routes `/admin/pilotage/*` en lecture seule, protégées par `require_admin_user` (401 sans jeton, 403 pour tout autre compte). La PWA n'envoie aucune requête `/admin/...` à un compte non administrateur. |
| **Durée de conservation** | Les lignes de `conso_tokens` sont conservées tant qu'elles servent le suivi des coûts ; la durée précise de conservation est à fixer par US-132 et à appliquer par une purge. Le sort des lignes d'un compte supprimé n'est pas encore défini (voir ci-dessous). Les alertes et bilans (`alertes_pilotage`, `bilans_pilotage`) ne contiennent aucune donnée de jardinier. |
| **Sécurité** | Table sans contenu de message ; lecture de tous les potagers par un chemin explicite (`lecture_toute_la_plateforme`) qui refuse de s'exécuter si la table reçoit une politique RLS ; aucune écriture depuis cette vue ; la valeur d'un prix d'abonnement saisi dans la vue Coût reste sur l'appareil. |
| **Sous-traitants** | Aucun de plus : la vue ne lit que la base de l'application. Les fournisseurs de modèles sont déjà couverts par les fiches des fonctions qui les appellent. |

## Points à trancher (US-132)

- Durée de conservation de `conso_tokens` : aujourd'hui sans purge. À fixer, puis à appliquer.
- Sort des lignes de `conso_tokens` quand un compte est supprimé : à vérifier et à décider (détachement de l'identifiant ou suppression).
- Information des jardiniers : la politique de confidentialité doit dire que l'administrateur voit la
  consommation (appels, jetons, coût) rattachée à leur adresse e-mail, jamais le contenu de leurs messages.
- Un potager en clé personnelle (US-143, à venir) devra être distingué : son coût n'est pas porté par la plateforme.
