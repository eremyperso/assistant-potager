# Étude — Piloter son potager depuis un assistant IA (serveur MCP)

> **Statut :** étude PO, en attente de validation des décisions D1 à D8 (§9)
> **Date :** 06/11/2026
> **Épic proposé :** ÉPIC 16 — Potager dans les assistants IA (MCP) *(numéro à valider)*
> **US :** US-290 à US-296 (§10)
> **Exemples :** [EXEMPLES_UTILISATION.md](EXEMPLES_UTILISATION.md)

---

## 0. L'essentiel

**L'idée.** Beaucoup de jardiniers passent déjà leur journée dans Claude, ChatGPT ou
Le Chat de Mistral. Plutôt que de leur demander d'ouvrir Telegram ou la PWA, on branche
leur potager **dans** leur assistant : un serveur MCP (Model Context Protocol) expose
le carnet, le plan, la pépinière, la météo et le savoir de l'application sous forme
d'outils que l'assistant appelle lui-même.

**Ce que MCP apporte.** Un **troisième canal**, à côté de Telegram et de la PWA : le
jardinier pose ses questions et dicte ses gestes dans l'outil qu'il utilise déjà, avec le
modèle qu'il paie déjà. Pour nous, aucun coût LLM sur ce canal.

**Ce que MCP n'apporte pas.** L'analyse du 01/11/2026
([ANALYSE_MESURE_AGENT_D_ABORD.md](../EPIC%20-%20COMPAGNON%20CONVERSATIONNEL/ANALYSE_MESURE_AGENT_D_ABORD.md) §0)
a écarté MCP **comme remède à la qualité du compagnon**. Cette conclusion tient toujours :
cette étude ne remplace pas le compagnon, elle ouvre un canal de plus. Le compagnon garde
l'initiative (veilleur, rappels), la voix Telegram et la qualité mesurée ; l'assistant
externe offre la souplesse d'un grand modèle, sans garantie de notre part.

**La règle centrale.** Le serveur MCP est une **projection** des registres existants
(`FORMES_DICTABLES`, catalogue d'outils, registre des lectures, exécuteurs de service,
propositions). Aucune règle métier nouvelle, aucune écriture qui ne passe par les services.
Toute écriture est une **proposition** à confirmer ; toute action destructrice reste au
**bouton seul**, dans la PWA ou Telegram.

---

## 1. Pour qui, pour quoi

| Persona | Besoin | Exemple |
|---|---|---|
| Jardinier « tout-IA » | Ne pas changer d'outil | « Claude, note que j'ai récolté 1,2 kg de haricots sur la planche sud » |
| Jardinier planificateur | Croiser son potager avec un raisonnement long | « Prépare-moi un plan de semis pour mars, en tenant compte de ma rotation et de ce que j'ai en stock » |
| Jardinier analyste | Analyser ses données avec les outils de l'assistant (tableaux, graphiques) | « Compare mon rendement tomates 2025 et 2026, fais-moi un graphique » |
| Potager partagé | Que chaque membre passe par son propre assistant | Un membre sur ChatGPT, l'autre sur Claude, même potager |

Les cas d'usage cibles, par ordre de valeur :

1. **Consulter et analyser** (lecture seule) : bilans, comparaisons, « qu'est-ce que je
   dois faire cette semaine », questions croisant météo, calendrier et carnet.
2. **Enregistrer des gestes** en langage libre : semis, plantation, récolte, perte, note.
3. **Planifier** : l'assistant propose un plan, le jardinier l'accepte geste par geste.
4. **Administrer** sans détruire : créer ou modifier une parcelle, programmer un rappel.

---

## 2. Rappel : ce qu'est MCP

MCP est un protocole ouvert qui permet à une application d'IA (le **client** : Claude,
ChatGPT, Le Chat…) d'appeler les **outils** d'un service tiers (le **serveur**), de lire
ses **ressources** et de proposer ses **prompts**.

- **Outils** : fonctions typées (schéma JSON) que le modèle décide d'appeler.
  Chaque outil porte des indications : lecture seule, destructeur, idempotent.
- **Ressources** : documents que le client peut charger en contexte (ex. le guide
  « comment parler à ce potager »).
- **Prompts** : gabarits proposés à l'utilisateur dans le client (ex. « Bilan de la semaine »).
- **Transport distant** : HTTP (« Streamable HTTP »), authentification **OAuth 2.1**.
  C'est ce mode qu'utilisent les connecteurs personnalisés des assistants grand public.

---

## 3. Compatibilité des assistants

> ⚠️ État connu en juin 2026, **à revérifier au démarrage d'US-290** : les offres et les
> plans évoluent vite.

| Client | Connexion d'un serveur distant | Écriture | Point d'attention |
|---|---|---|---|
| **Claude** (web, bureau, mobile) | Connecteur personnalisé (URL + OAuth) | Oui, avec approbation par outil | Plans éligibles et nombre de connecteurs à vérifier |
| **ChatGPT** | Connecteurs / mode développeur | Oui, avec confirmation des actions d'écriture | Réservé à certains plans payants, à vérifier |
| **Le Chat (Mistral)** | Connecteurs MCP personnalisés | Oui | Cohérent avec notre choix de Mistral côté compagnon |
| Claude Code, VS Code, Cursor, MCP Inspector | Natif | Oui | Recette et développement, pas la cible grand public |

Conséquence : le canal MCP est **une option pour jardiniers équipés**, pas un parcours
d'accueil. L'inscription, le premier potager et Telegram restent les portes d'entrée.

---

## 4. Principes d'architecture (niveau fonctionnel)

```
 Claude / ChatGPT / Le Chat                    Assistant Potager
 ┌─────────────────────┐   HTTPS + OAuth   ┌──────────────────────────────┐
 │ modèle du jardinier │ ───────────────▶  │ serveur MCP (/mcp)           │
 │ (payé par lui)      │   appels d'outils │   │ projection des registres │
 └─────────────────────┘ ◀───────────────  │   ▼                          │
                           JSON compact    │ app/services (TenantContext) │
                                           │   ▼                          │
                                           │ PostgreSQL (RLS)             │
                                           └──────────────────────────────┘
                                                 │ proposition créée
                                                 ▼
                                    carte aussi visible PWA + Telegram (US-272)
```

1. **Distant et hébergé par nous**, sur le même domaine que l'API. Pas de serveur local à
   installer : un jardinier colle une URL dans son assistant, se connecte, c'est tout.
2. **Authentification OAuth 2.1** avec son compte Assistant Potager. La page de
   consentement dit ce que l'assistant pourra lire et écrire, et sur quel potager.
3. **Contexte locataire** : chaque appel construit le `TenantContext` (utilisateur,
   potager, rôle) comme la PWA. RLS et rôles (US-113) s'appliquent sans exception.
4. **Pas de LLM chez nous** sur ce canal : les outils reçoivent des arguments déjà
   structurés par le modèle du client. Pas d'appel à `/parse` ni à l'agent interpréteur.
5. **Les écritures sont des propositions** (mécanique d'US-259/US-260/US-272) : un canal
   de plus (`canal = "mcp"`), une seule écriture quel que soit l'endroit où l'on confirme.
6. **Réponses compactes** : listes paginées et bornées, unités explicites, dates ISO,
   pour ménager le contexte du modèle client.

---

## 5. Catalogue des outils (v1)

Seize outils, sous le plafond de ~20 au-delà duquel les modèles choisissent mal. Chaque
outil prend un argument facultatif `potager` (nom ou identifiant) ; à défaut, le potager actif.

### 5.1 Lecture (indication « lecture seule »)

| Outil | Ce qu'il rend | Source existante |
|---|---|---|
| `lister_potagers` | Potagers du compte, rôle, potager actif, zone climatique | `GET /potagers` |
| `voir_plan` | Parcelles, rangs, occupation, cultures en place, récolte attendue | `GET /plan`, `GET /cultures/vue` |
| `voir_pepiniere` | Lots (numéro, stade, emplacement, levée), échéances | `GET /pepiniere/lots` |
| `voir_stock` | Graines et plants par variété | `GET /stats/varietes`, stock |
| `consulter_carnet` | Gestes filtrés (période, culture, parcelle, type), paginés | `GET /historique` |
| `voir_statistiques` | Rendement (cumul saison pour les reproductrices), activité | `GET /stats/*` |
| `voir_meteo` | Prévisions et historique du potager | `GET /meteo`, `/meteo/history` |
| `voir_calendrier` | Fenêtres de la zone, niveau de confiance pour semer/planter à une date | `GET /cultures/{c}/calendrier`, `/confiance` |
| `voir_echeances` | À faire : lots à repiquer/endurcir, rappels, récoltes attendues dépassées | `echeances_lots`, rappels |
| `chercher_connaissance` | Passages du corpus (agronomie + mode d'emploi) avec leur source | `connaissance.rechercher` |

### 5.2 Écriture (toujours via proposition)

| Outil | Effet | Garde-fou |
|---|---|---|
| `proposer_geste` | Crée une proposition de geste (semis, mise en godet, plantation, récolte, perte, observation…) et rend son récapitulatif | Rien n'est écrit ; rôle `editor` requis |
| `proposer_commande` | Proposition d'une commande **non destructrice** à exécuteur de service (parcelle ajouter/modifier, rappel, carnet…) | Liste fermée, dépend d'US-289 CA7 |
| `proposer_correction` | « En fait c'était 3 rangs » sur un geste récent (US-262) | Avant → après dans le récapitulatif |
| `confirmer_proposition` | Exécute une proposition **non destructrice** | Sortie atomique, une seule écriture (US-259) |
| `abandonner_proposition` | Abandonne une proposition | Aucun effet en base |
| `ouvrir_dans_l_application` | Rend le lien de la carte dans la PWA | Pour les destructions (bouton seul) |

### 5.3 Ressources et prompts

- **Ressource `guide-du-potager`** : le mode d'emploi destiné au modèle — vocabulaire des
  gestes, différence végétatif / reproducteur, dates ISO, « ne jamais inventer une parcelle,
  demander », « une destruction se fait dans l'application ».
- **Ressource `resume-du-potager`** : une fiche courte (parcelles, cultures en place, zone)
  pour amorcer une conversation sans multiplier les appels.
- **Prompts** : « Bilan de la semaine », « Que semer ce mois-ci ? », « Préparer ma sortie
  au jardin », « Bilan de saison d'une culture ».

---

## 6. Règles métier que le canal MCP doit respecter

Le modèle externe ne connaît pas notre domaine ; le serveur **refuse ou demande**, il ne
devine jamais.

1. **Végétatif / reproducteur** (`type_organe_recolte`) :
   - une récolte de laitue, carotte, radis, poireau **consomme des pieds** : le
     récapitulatif dit combien de pieds sortent du stock ;
   - une récolte de haricot, petit pois, fève, tomate, courgette **ne consomme pas de
     pied** : elle s'ajoute au **rendement cumulé de la saison**, le nombre de pieds actifs
     ne bouge pas ;
   - seule une `perte` (ou un arrachage explicite) réduit les pieds d'une reproductrice.
2. **Parcelle inconnue** : jamais créée implicitement par un geste ; l'outil rend
   « parcelle introuvable » avec les noms proches.
3. **Quantité de pépinière obligatoire** (correctif du 14/10/2026) : une proposition sans
   quantité revient avec la question, elle n'est pas créée incomplète.
4. **Date** : passée ou du jour, jamais future ; « hier » est résolu par le modèle client,
   le serveur vérifie et rejette l'incohérent.
5. **Rôle** : un `lecteur` ne voit que les outils de lecture ; un appel d'écriture forcé
   est refusé avec « Tu es lecteur sur ce potager ».
6. **Destruction** : suppression de parcelle, mise hors service, annulation d'un geste,
   suppression de potager, gestion des membres → jamais par MCP (bouton seul, §8 L7).

---

## 7. Sécurité et données

| Sujet | Mesure |
|---|---|
| Authentification | OAuth 2.1 + PKCE, jetons courts, révocables depuis la PWA |
| Portée du consentement | Lecture seule **ou** lecture + écriture, choisie à la connexion ; un potager ou tous |
| Isolation | `TenantContext` + RLS à chaque appel ; aucun identifiant d'un autre potager accepté |
| Quotas | Plafond d'appels par minute et par jour, par jeton (cf. conception sécurisation API) |
| Injection de consigne | Les textes libres rendus (notes, noms de parcelles, observations d'un autre membre) sont marqués comme **données** ; aucune écriture sans confirmation |
| Minimisation | Pas d'e-mail ni de nom complet des autres membres ; « un membre » ou prénom choisi |
| Traçabilité | Journal des appels MCP (outil, potager, client, résultat), visible par le jardinier |
| RGPD | Ce que l'assistant lit **sort de notre périmètre** et suit la politique de l'éditeur de l'assistant : consentement explicite à la connexion, mention dans la politique de confidentialité (`docs/RGPD/`) |

---

## 8. Limitations

Ce que le canal MCP **ne fera pas**, ou fera moins bien que Telegram et la PWA. Chaque
limitation est assumée, documentée pour le jardinier (US-295) et vérifiée en recette (US-296).

### 8.1 Fonctionnelles

| # | Limitation | Pourquoi | Ce que le jardinier fait à la place |
|---|---|---|---|
| L1 | **Aucune initiative** : pas de message spontané, pas de rappel qui arrive tout seul | MCP est tiré par le client ; le serveur ne peut pas écrire dans la conversation | Veilleur et rappels restent sur Telegram / la PWA |
| L2 | **Pas de voix maison** : pas de Whisper ni de TTS de l'application | La voix dépend de l'assistant ; le mode vocal des assistants n'appelle pas toujours les outils | Vocal Telegram |
| L3 | **Pas de photo** en v1 (diagnostic, étiquette de sachet) | Le transfert de fichiers vers un serveur MCP n'est pas homogène entre clients | PWA / Telegram |
| L4 | **Pas de carnet du compagnon** ni de mémoire de conversation partagée | La mémoire est celle de l'assistant externe, hors de notre contrôle | `/carnet`, écran « Mon compagnon » |
| L5 | **Pas d'administration du compte** : inscription, invitations, rôles, BYOK, abonnement | Actions sensibles ou contractuelles | PWA |
| L6 | **Commandes limitées** aux formes qui ont un exécuteur de service | Les autres s'exécutent encore par un handler Telegram (US-289) | Telegram, en attendant US-289 CA7 |
| L7 | **Aucune destruction** : supprimer / mettre hors service une parcelle, annuler un geste, supprimer un potager | Un modèle externe peut enchaîner proposer + confirmer sans que le jardinier ait vraiment dit oui | Lien vers la carte, confirmée au bouton dans la PWA |

### 8.2 Qualité

| # | Limitation |
|---|---|
| L8 | **Qualité non garantie** : la compréhension dépend du modèle du client (version, réglages, mode « réflexion »). Nos mesures (US-256, US-280) ne s'appliquent pas à ce canal. |
| L9 | **Réponses agronomiques hors corpus** : l'assistant peut répondre de sa propre culture sans appeler `chercher_connaissance`. Le guide le lui demande ; on ne peut pas l'y obliger. |
| L10 | **Confirmation selon le client** : certains clients demandent l'accord avant chaque outil d'écriture, d'autres permettent « toujours autoriser ». Avec ce réglage, l'assistant peut confirmer seul une proposition non destructrice. D'où L7, la correction d'un geste récent (US-262) et le journal. |
| L11 | **Pas de « vas-y » partagé** : une proposition créée dans ChatGPT se confirme dans ChatGPT, dans la PWA ou dans Telegram ; mais la conversation ChatGPT n'apprend pas qu'elle a été confirmée ailleurs, sauf si elle relit l'état. |

### 8.3 Techniques et économiques

| # | Limitation |
|---|---|
| L12 | **Plans payants** : la plupart des assistants réservent les connecteurs personnalisés à leurs abonnements (à vérifier par client). |
| L13 | **Volume** : listes bornées (ex. 50 gestes par page, 12 mois d'historique par appel) ; une analyse pluriannuelle demande plusieurs appels. |
| L14 | **Quotas** : plafond d'appels par jeton ; un assistant qui boucle est coupé avec un message clair. |
| L15 | **Disponibilité** : en ligne seulement ; une panne de l'API coupe le canal. Pas de mode hors ligne. |
| L16 | **Évolution du protocole** : MCP et les connecteurs évoluent vite ; une recette par client est rejouée à chaque version majeure (US-296). |

### 8.4 Données et confidentialité

| # | Limitation |
|---|---|
| L17 | Les données lues partent chez l'éditeur de l'assistant (Anthropic, OpenAI, Mistral) et suivent **sa** politique de conservation et d'entraînement. Nous ne pouvons ni les effacer ni les contrôler. |
| L18 | Dans un potager partagé, un membre qui connecte son assistant fait sortir des données communes (gestes des autres membres, notes). Décision D6 : prévenir les autres membres. |

---

## 9. Décisions à valider

| # | Question | Recommandation PO |
|---|---|---|
| D1 | Serveur MCP dans l'API FastAPI (`/mcp`) ou processus séparé ? | Dans l'API pour la v1 (même auth, même déploiement) ; séparer si la charge le justifie |
| D2 | OAuth complet ou jeton personnel collé à la main ? | OAuth (exigé par les connecteurs grand public) ; jeton personnel en plus, réservé aux clients de développement |
| D3 | Portée par défaut à la connexion | Lecture seule cochée par défaut ; l'écriture est un choix explicite |
| D4 | Les propositions MCP apparaissent-elles aussi dans Telegram et la PWA ? | Oui, comme US-272 : une proposition, trois fenêtres, la première réponse l'emporte |
| D5 | Annuler un geste créé par MCP dans les 10 minutes depuis MCP ? | Non en v1 (bouton seul, L7) ; à rouvrir après la recette |
| D6 | Potager partagé : prévenir les autres membres qu'un assistant externe lit le potager ? | Oui, notification + mention dans « Membres » ; le propriétaire peut l'interdire pour son potager |
| D7 | Le canal MCP compte-t-il dans un futur abonnement ? | Hors v1 ; journal des appels gardé pour décider (ÉPIC 4) |
| D8 | Numéro d'épic | ÉPIC 16, à confirmer avec la numérotation des épics 13 à 15 « à valider » |

---

## 10. Découpage en US

| US | Titre | Points | Dépend de |
|---|---|---|---|
| [US-290](../../backlog/US-290_serveur-mcp-authentifie.md) | Connecter son assistant IA à son potager (serveur MCP authentifié) | 8 | US-110, US-113 |
| [US-291](../../backlog/US-291_consulter-potager-assistant-ia.md) | Consulter son potager depuis un assistant IA | 5 | US-290 |
| [US-292](../../backlog/US-292_enregistrer-geste-assistant-ia.md) | Enregistrer un geste depuis un assistant IA | 8 | US-290, US-259, US-272 |
| [US-293](../../backlog/US-293_commandes-non-destructives-mcp.md) | Gérer parcelles et rappels depuis un assistant IA, sans destruction | 5 | US-292, US-289 CA7 |
| [US-294](../../backlog/US-294_assistants-connectes-pwa.md) | Voir et révoquer les assistants connectés | 3 | US-290 |
| [US-295](../../backlog/US-295_guide-prompts-mcp.md) | Guider le modèle et le jardinier (ressources, prompts, mode d'emploi) | 3 | US-291 |
| [US-296](../../backlog/US-296_recette-trois-assistants-ia.md) | Recetter le canal MCP sur Claude, ChatGPT et Le Chat | 3 | US-291 à US-295 |

**Ordre de livraison conseillé** : US-290 → US-291 → US-294 → US-295 (lecture seule
livrable seule, déjà utile) → US-292 → US-293 → US-296. Le **lot lecture seule** (19 points
sur 35) livre l'essentiel de la valeur « analyser mon potager dans mon IA » avec un risque
quasi nul.

### 10.1 Modèle conseillé, effort et charge pour l'implémentation

La question porte sur le modèle utilisé **pour écrire le code** dans Claude Code, pas sur
le modèle du jardinier (celui de son assistant, hors de notre contrôle). L'**effort** est le
niveau de raisonnement réglé dans Claude Code (`low` / `medium` / `high` / `xhigh`). La
**charge** compte des sessions Claude Code, recette comprise (règle « une US = une session »
de `CLAUDE.md` ; une US de 8 points peut en demander plusieurs).

| US | Modèle conseillé | Effort | Charge estimée | Pourquoi |
|---|---|---|---|---|
| US-290 | **Opus 5.5** | `high` | 3 à 4 sessions, plus ~½ journée de branchement réel (connecteur Claude sur l'environnement de dev, URL publique requise) | La plus risquée de l'épic : un serveur d'autorisation OAuth 2.1 (PKCE, métadonnées, enregistrement des clients, révocation), un nouveau point d'entrée exposé sur Internet, et le `TenantContext` construit depuis un jeton tiers. Une faille d'isolation ou de portée ne se voit dans aucun test naïf. Le journal et les quotas peuvent être confiés à Sonnet une fois le socle posé |
| US-291 | **Sonnet 5.5** | `medium` | 1 à 2 sessions | Projection de lectures existantes, sans règle nouvelle ; les tests de parité avec la PWA (CA2) servent de filet. Le seul point fin est CA4 (pieds actifs contre cumul de saison), déjà calculé par les services |
| US-292 | **Opus 5.5** | `high` | 2 à 3 sessions | Porte la sécurité de l'écriture : sortie atomique d'une proposition, un nouveau canal dans un mécanisme partagé par Telegram et la PWA (US-259, US-272), récapitulatif végétatif / reproducteur, refus des destructions. Une erreur ici écrit deux fois ou écrit faux dans le carnet |
| US-293 | **Sonnet 5.5** (Opus si US-289 CA7 n'est pas livrée) | `medium` | 1 à 2 sessions | Si les exécuteurs de service existent, c'est une lecture du registre et un aiguillage. Sinon, il faut extraire des exécuteurs des handlers Telegram sans changer leur comportement : c'est le travail d'US-289 CA7, à faire d'abord, avec Opus |
| US-294 | **Sonnet 5.5** | `medium` | 1 à 2 sessions, plus la maquette dans Claude Design | Écran de liste et d'activité, une petite migration, une notification ; le risque est dans le rendu (375 px / 768 px / bureau), pas dans la logique. CA6 (interdiction par le propriétaire) se teste contre US-290 |
| US-295 | **Sonnet 5.5** | `medium` | 1 session | Rédaction (ressource du modèle, fiche du corpus, chapitre du guide) et ingestion. Le guide destiné au modèle demande du soin, pas de la puissance ; `test_us099` sert de filet |
| US-296 | **Sonnet 5.5** | `low` | 1 session, plus ~1 journée de recette manuelle sur les trois assistants | Écrire les scénarios et mettre en forme le rapport. L'essentiel du temps est humain et ne se compresse pas : jouer les scénarios dans Claude, ChatGPT et Le Chat |

**Total : 10 à 15 sessions Claude Code**, plus ~1,5 journée de travail manuel (branchement
réel d'US-290, recette d'US-296) et la maquette d'US-294.

En résumé : **Sonnet 5.5 suffit pour 5 US sur 7**. Opus 5.5 se justifie sur les deux US
qui portent la sécurité, l'accès (US-290) et l'écriture (US-292). Pratique économique
pour ces deux-là, comme pour l'épic Agent interpréteur : concevoir et écrire le cœur
(autorisation et contexte locataire, sortie atomique et refus) avec Opus en `high`, puis
laisser Sonnet en `medium` écrire les tests répétitifs, le journal et les fiches du corpus.

---

## 11. Risques

| Risque | Probabilité | Impact | Parade |
|---|---|---|---|
| Écritures fausses validées en « toujours autoriser » | Moyenne | Moyen | Récapitulatif explicite, correction US-262, journal, aucune destruction |
| Fuite de données via un autre membre | Faible | Élevé | D6, minimisation, consentement |
| Assistant qui boucle et martèle l'API | Moyenne | Faible | Quotas par jeton (L14) |
| Clients incompatibles ou qui changent | Élevée | Moyen | Recette par client (US-296), dépendre du seul protocole standard |
| Confusion « qui répond ? » (Gaston vs Claude) | Moyenne | Faible | Le mode d'emploi le dit : dans votre assistant, c'est votre assistant qui parle, avec les données du potager |
