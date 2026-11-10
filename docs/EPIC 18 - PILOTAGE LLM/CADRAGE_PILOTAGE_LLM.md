# ÉPIC 18 — Pilotage LLM : mesure fiable, coût, tableau de bord d'administration, alertes

*Cadrage du 10/11/2026. Numéro d'épic à valider. US-306 à US-319 dans `backlog/`.*

## 1. Pourquoi cet épic

`conso_tokens` (US-092) mesure chaque appel passé par `llm/passerelle.py`. L'US-097
avait volontairement reporté l'écran : « l'écran viendra si ces chiffres sont consultés
régulièrement ». C'est le cas : une extraction CSV du 25/08 au 10/11/2026 (5 218 lignes,
base locale de dev) a été analysée à la main, et l'exercice a montré deux choses.

**La table ne permet pas aujourd'hui de conclure juste.** Constats sur l'extraction :

| Constat | Preuve dans l'extraction | Conséquence |
|---|---|---|
| Les campagnes de mesure sont confondues avec l'usage | Rafales d'appels `agent` espacés de 1 à 2 s sur le potager 1 / utilisateur 1 (21/10, 23/10, 27/10, 28/10, 30/10, 02/11, 03/11, 04/11) et séries sur trois modèles à la suite (01/11 23h54 → 02/11 00h14) : signature de `tools/evaluer_agent.py` et `tools/evaluer_dialogues.py` | Le « pic du 2 novembre » et la « baisse de 62 % » qui suit ne décrivent pas l'usage |
| Des appels simulés sont journalisés | Lignes à 0 jeton et 0 ms en `ok` (16/09, 17/09, 19/10, 28/10, 30/10) | Taux de succès et volumes faussés |
| Les unités sont mélangées | `tokens_in` porte des secondes pour `dictee`, des caractères pour `voix` (US-299) | Une somme de `tokens_in` additionne des jetons, des secondes et des caractères |
| Une valeur de configuration invalide est journalisée telle quelle | Modèle `mistral/voxtral-mini-tts-3-0            (voix : texte → MP3)` le 10/11 (commentaire de `.env` lu comme valeur), 5 erreurs | Ventilation par modèle polluée, panne non détectée |
| Aucun coût | Pas de tarif, pas de fournisseur | Impossible de piloter un budget ou de fixer un prix |
| Aucun lien entre appels | Un échange du compagnon produit 2 à 6 lignes indépendantes | Le coût d'une interaction complète est inconnu |
| Aucune version | — | Une dérive ne peut pas être rattachée à une livraison |

**Le signal utile existe pourtant.** Le prompt de l'agent est passé d'environ 1 000 jetons
d'entrée par appel (21/10) à 3 000 (21/10 après-midi), 4 500 (25/10), 6 000 (29/10) puis
8 000 à 9 000 (05/11). C'est exactement la dérive qu'un tableau de bord doit rendre visible
à chaque version, et qu'une alerte doit signaler.

## 2. Objectif

Donner à l'administrateur de la plateforme une application d'administration qui montre,
sans extraction manuelle, ce que l'assistant consomme, ce que cela coûte, si le service
tient, et ce qui dérive ; et qui le prévienne par Telegram et par e-mail quand un seuil
est franchi. L'ensemble doit servir la commercialisation : le coût par jardinier actif et
par échange est la donnée d'entrée d'un prix d'abonnement.

Hors périmètre : plafonner ou bloquer (US de quotas), relevé BYOK réconciliable avec la
facture d'un tiers (US-188), tableau de bord destiné au jardinier.

## 3. Décisions

| # | Décision | Raison |
|---|---|---|
| D1 | **PWA d'administration séparée** (choix du 10/11) : une seconde application Vite dans `admin/`, son manifeste, son périmètre d'URL, servie par la même API FastAPI | Isolation nette de l'application du jardinier ; aucune ligne d'administration dans le paquet livré aux utilisateurs |
| D2 | Même authentification (JWT existant), accès par `require_admin_user` (`ADMIN_EMAIL`) | Rien à inventer ; le passage à un rôle « administrateur de plateforme » en base est un point ouvert (§7) |
| D3 | Chaque ligne porte sa **provenance** : `usage` \| `mesure` \| `test` \| `fond` ; l'existant est rejoué en `historique` | Sans elle, tout indicateur mélange usage réel et bancs d'essai. Nom distinct de l'« origine de la clé » d'US-188 (`plateforme` \| `potager`) |
| D4 | Chaque ligne porte un **identifiant d'échange**, un **canal** (`telegram` \| `pwa` \| `mcp` \| `fond` \| `outil`), la **version** de l'application et son **unité** (`jeton` \| `seconde` \| `caractere`) | Coût d'une interaction, comparaison par canal, dérive par version, sommes justes |
| D5 | Le coût est **figé à l'écriture**, en micro-euros entiers, d'après une grille tarifaire versionnée dans le dépôt | Reprise anticipée des CA1 à CA3 d'US-188 : même colonnes, même règle. US-188 garde la réconciliation BYOK |
| D6 | Le coût est calculé **au tarif public** même quand l'appel est servi par un palier gratuit | Ce qui compte pour un prix d'abonnement est le coût à l'échelle, pas la facture de la phase de développement |
| D7 | Agrégats **calculés à la demande** en SQL, percentiles en Python (`_p95` existant) ; pas de table d'agrégats | 5 000 lignes en dix semaines ; une table quotidienne se justifiera au-delà de quelques millions de lignes |
| D8 | « Temps réel » = rafraîchissement périodique (60 s) de la vue du jour ; pas de WebSocket | Suffisant à ce volume, sans infrastructure nouvelle |
| D9 | Les vues excluent par défaut `mesure`, `test` et `historique` ; un filtre les réintègre | La question par défaut est « que consomment les jardiniers ? » |
| D10 | Seuils en base, modifiables depuis la PWA d'administration ; alertes par **Telegram** (compte administrateur) et **e-mail** (Brevo, `app/services/email.py`) ; chaque déclenchement est journalisé | Choix du 10/11 ; le journal évite la répétition et servira un futur bandeau |
| D11 | Aucun appel de modèle pour produire un indicateur, une alerte ou un bilan | Même règle que US-097 / CA8 : l'observabilité ne consomme pas ce qu'elle mesure |
| D12 | Une vue dédiée **« Potagers et jardiniers »** lit aussi `potagers`, `potager_membres` et `users` ; elle affiche le nom du potager et l'adresse e-mail du jardinier, rien d'autre de personnel | Demande du 10/11 : savoir qui consomme quoi. Sans ces tables, un potager qui n'utilise jamais l'assistant est invisible. Traitement à inscrire au registre RGPD |

## 4. Indicateurs retenus

Tous filtrables par période, provenance, canal, modèle, type d'appel et potager.

| Famille | Indicateur | Lecture |
|---|---|---|
| Volume | Appels, jetons d'entrée, de sortie, en cache par jour ; secondes d'audio et caractères à part | Activité |
| Efficacité | Taux de cache (jetons en cache / jetons d'entrée) ; part des questions résolues sans modèle (déjà dans `metriques_routage`) | Ce qui est économisé |
| Dérive | Médiane et P95 des jetons d'entrée par appel, par type et par **version** ; nombre d'appels par échange | Ce qui grossit d'une version à l'autre |
| Coût | Coût par jour, par modèle, par type, par canal ; projection de fin de mois | Budget |
| Rentabilité | Coût par jardinier actif et par mois, coût par potager, coût médian et P95 d'un échange, 10 potagers les plus coûteux | Entrée du prix d'abonnement |
| Fiabilité | Répartition des issues (`ok`, `quota`, `delai`, `erreur`, autres) par jour et par modèle | Ce que le jardinier subit |
| Performance | Latence P50 et P95 par type d'appel et par modèle | Confort d'usage |
| Saturation | Appels en `quota` par modèle et par heure | Premier signe qu'un palier ne suffit plus |
| Utilisateurs | Potagers existants et actifs, jardiniers inscrits et actifs ; par potager et par jardinier : appels, échanges, coût, canaux, taux d'échec, dernier appel ; concentration du coût ; usage élevé | Qui consomme quoi, adoption, profils pour un prix |

## 5. Architecture cible

```
llm/passerelle.py ──écrit──▶ conso_tokens (+ provenance, echange_ref, canal, version_app,
                                            unite, fournisseur, cout_micro_eur, tarif_version)
data/tarifs/tarifs_llm.json ──lu au démarrage──▶ app/services/pilotage/tarifs.py
app/services/pilotage/agregats.py ──▶ GET /admin/pilotage/*   (require_admin_user)
app/services/pilotage/seuils.py   ──▶ alertes Telegram + e-mail, journal alertes_pilotage
app/services/pilotage/bilan.py    ──▶ bilan quotidien et hebdomadaire
admin/ (Vite + React, PWA)        ──▶ servie sous /pilotage/ par la même API
```

Les routes `/admin/routage/*` et `/admin/savoir/*` existantes ne bougent pas ; la PWA
d'administration pourra les afficher dans une vue ultérieure.

## 6. Découpage

| Lot | US | Titre | Points | Modèle | Effort |
|---|---|---|---:|---|---|
| 1 — Mesure fiable | US-306 | Marquer la provenance de chaque appel | 3 | Sonnet 5.5 | `medium` |
| | US-307 | Relier les appels d'un même échange, avec canal, version et unité | 5 | Sonnet 5.5 | `high` |
| | US-308 | Refuser un nom de modèle invalide au démarrage | 2 | Haiku 5.5 | `medium` |
| 2 — Coût | US-309 | Chiffrer chaque appel d'après une grille tarifaire versionnée | 5 | Sonnet 5.5 | `high` |
| 3 — Tableau de bord | US-318 | Maquetter la PWA d'administration (coquille + Consommation, Seuils) | 2 | Claude Design | — |
| | US-310 | Exposer les agrégats de pilotage à l'administrateur | 5 | Sonnet 5.5 | `high` |
| | US-311 | Ouvrir la PWA d'administration | 5 | Sonnet 5.5 | `high` |
| | US-312 | Suivre la consommation jour par jour | 5 | Sonnet 5.5 | `medium` |
| | US-313 | Suivre le coût et la rentabilité | 3 | Sonnet 5.5 | `medium` |
| | US-314 | Suivre la qualité de service | 3 | Sonnet 5.5 | `medium` |
| | US-315 | Repérer une dérive d'une version à l'autre | 3 | Sonnet 5.5 | `medium` |
| | US-319 | Suivre la consommation par potager et par jardinier | 5 | Sonnet 5.5 | `medium` |
| 4 — Alertes | US-316 | Être alerté quand un seuil est franchi | 5 | Sonnet 5.5 | `high` |
| | US-317 | Recevoir un bilan périodique | 3 | Sonnet 5.5 | `medium` |

54 points. Ordre imposé : lot 1 avant tout (sinon les vues affichent les bancs d'essai),
US-309 avant US-313, US-310 et US-311 avant les vues, US-310 avant le lot 4. Les vues
US-312, US-314 et US-315 n'attendent pas le coût.

**Maquette.** US-318 se mène en parallèle des lots 1 et 2 et doit être validée avant
US-311. Elle ne couvre que deux écrans de référence (brief :
`BRIEF_MAQUETTE_PWA_ADMINISTRATION.md`) ; les vues US-313 à US-315 et US-319 réutilisent les
composants de la vue Consommation et n'ont pas de maquette propre.

### 6.1 Synthèse de production

| Profil | US | Points |
|---|---|---:|
| **Sonnet 5.5 · `high`** | US-307, US-309, US-310, US-311, US-316 | 25 |
| **Sonnet 5.5 · `medium`** | US-306, US-312, US-313, US-314, US-315, US-317, US-319 | 25 |
| **Haiku 5.5 · `medium`** | US-308 | 2 |
| Claude Design (hors Claude Code) | US-318 | 2 |

**Ni Fable 5 ni Opus 5.5 ne sont requis.** Cet épic ne contient ni boucle d'agent, ni
chemin d'écriture métier, ni refactorisation du bot : c'est de la mesure, de l'agrégation
SQL et des écrans, sur des motifs déjà présents dans le dépôt (`cumul_mesure_cascade`
pour le contexte, `metriques_routage` pour les agrégats, `require_admin_user` pour l'accès).

Ce qui justifie `high` plutôt que `medium` sur cinq US :

| US | Risque qui demande l'effort `high` |
|---|---|
| US-307 | Transversal : un identifiant porté par le contexte à travers le bot, l'API et le MCP, en asynchrone ; une fuite de contexte relie deux échanges sans rapport |
| US-309 | De l'argent : arithmétique entière, tarif du cache, coût figé ; une erreur fausse durablement toutes les séries |
| US-310 | Lecture de tous les potagers hors périmètre RLS (US-043) ; percentiles portables SQLite / PostgreSQL ; tenue en charge |
| US-311 | Seconde application, service worker limité à `/pilotage/`, deux chaînes de déploiement et `test_us005_deploiement.py` |
| US-316 | Machine à états des alertes (ouverte, résolue, rappel), anti-répétition, planification en production |

**Seule réserve.** Si, à l'analyse d'US-310, la lecture hors RLS impose de toucher à
`database.db.tenant_scope` plutôt que d'emprunter un chemin d'administration déjà
existant, concevoir ce seul point avec Opus 5.5 `high`, puis revenir à Sonnet 5.5.

**Pratique économique.** Sur une US `high`, écrire le cœur (propagation du contexte,
calcul du coût, service d'agrégats, évaluation des seuils) à l'effort `high`, puis passer
en `medium` pour les tests répétitifs et les vues. Confier à Haiku 5.5 `medium` la
rédaction de `PATCH_NOTES`, les fiches `doc_app`, la mise à jour de `SETUP.md` et du
runbook, et le suivi Jira. La recette visuelle (chrome-devtools) reste en Sonnet 5.5
`medium`.

## 7. Points ouverts

1. **Rôle d'administrateur** : `ADMIN_EMAIL` désigne une seule personne. Pour une
   commercialisation avec plusieurs opérateurs, un rôle en base sera nécessaire. Non
   traité ici ; `require_admin_user` reste le seul point à changer.
2. **Adresse de la PWA d'administration** : chemin `/pilotage/` sur le même hôte
   (proposé, aucun changement nginx ni DNS) ou sous-domaine dédié. À trancher en US-311.
3. **Planification des alertes et du bilan** : même mécanisme que le veilleur du
   compagnon (US-266) ou unité systemd avec minuteur dans `infra/`. À trancher à
   l'analyse d'US-316 ; dans les deux cas `tests/test_us005_deploiement.py` doit suivre.
4. **Tarifs** : la grille initiale est à relever sur les pages publiques de Groq et de
   Mistral à la date de l'US-309 et à dater ; aucun tarif n'est écrit de mémoire.
5. **Rétention** : `metriques_routage.RETENTION_JOURS` vaut 365 jours pour le routage ;
   la même durée est proposée pour `conso_tokens`, la purge restant à écrire.
6. **RGPD** : `conso_tokens` porte `user_id` et `potager_id`, et la vue « Potagers et
   jardiniers » (US-319) affiche nom de potager et adresse e-mail. Donnée d'exploitation,
   à inscrire au registre (`docs/RGPD/`) ; c'est le CA12 d'US-319.
7. **Numéros de migration** : v73 et suivantes, à confirmer au moment de coder.
