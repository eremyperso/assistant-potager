# 05 — Besoins attendus : ce dont j'ai besoin de vous

Classés par moment : ce qui **bloque tout de suite**, ce qui bloque **un lot**, ce qui peut attendre. « Je » = Claude Code qui
développe et mesure ; « vous » = le porteur du produit.

## 1. Maintenant (porte G0)

| # | Besoin | Pourquoi | Bloque |
|---|---|---|---|
| 1 | **Régler le numéro US-336** : Jira porte déjà « US-336 : Étudier l'itinéraire de saison » (PIA-319, 16/11). Dites-moi quelle US change de numéro | Le ticket de l'US du jeu d'évaluation n'existe pas encore ; PIA-319 a été passé en « Revue en cours » par erreur de ma part et doit retrouver son statut d'origine | Le suivi Jira de tout l'épic |
| 2 | **Accord sur le volume de la ligne de base** : `python tools/evaluer_compagnon.py --dry-run --moteur actuel` annonce le chiffre ; vous répondez par l'accord (`--accord <volume>`) | CA8 d'US-337 ; **rien ne démarre au-delà du lot 0 sans elle** | G0, donc tous les lots |
| 3 | **Clé de mesure** `MISTRAL_API_KEY_MESURE` (distincte de celle du bot) dans l'environnement de dev | Le lanceur refuse de tourner sans elle, ou si elle est identique à celle du bot | La mesure réelle |
| 4 | **Un potager neuf dans une base de test à jour** : jouer les migrations en retard sur `potager_test` (la colonne `potagers.assistants_externes_interdits` y manque ; v79 et v80 ne sont jouées nulle part), puis `python tools/creer_potager_test_neuf.py` en `APP_ENV=test` | Le jeu « potager neuf » n'a jamais été joué sur PostgreSQL ; le script refuse une base qui n'a pas « test » dans son nom | La mesure sur le potager neuf |
| 5 | **Accès en lecture au potager 33** (utilisateur 2) dans la base visée | Le jeu « potager rempli » le lit sans rien écrire | La mesure sur le potager rempli |
| 6 | **Seuils du §7.2** à confirmer : utile ≥ 80 %, aboutit ≥ 85 %, latence p95 ≤ 4 s, 100 % sur les quatre critères de sûreté, 0 hors-sujet | « À confirmer avec le porteur du produit » (arbitrage d'US-336) | Toutes les portes |
| 7 | **Le modèle du juge** : Large 3 par défaut (plus fort que Small 4) ; tarif à confirmer (le lanceur utilise une estimation) | Le coût annoncé en dépend | Le chiffrage de chaque mesure |

## 2. Avant le lot 1 (US-338)

| # | Besoin | Pourquoi |
|---|---|---|
| 8 | **Commiter ou fusionner les US-290 à US-297** (serveur MCP, lectures, écritures, commandes) sur la branche de travail, ou me dire laquelle prime (`mcp-server` ou `refonte-architecture-agent`) | US-338 extrait le registre de ce code ; je ne le déplace pas sans base stable ni commit propre |
| 9 | **Une décision sur le commit de l'existant** : l'épic 20 arrive dans une copie qui porte déjà de nombreuses US non commitées | Les portes comparent « avant » et « après » ; sans commit, « avant » n'est pas reproductible. Je ne commite jamais sans votre demande |

## 3. Avant le lot 2 (US-342, US-343)

| # | Besoin | Pourquoi |
|---|---|---|
| 10 | **Arbitrages A2, A3, A4** : conseil général hors corpus (signalé), durée du fil (12 tours, compaction), Small 4 comme modèle de référence | La boucle et le fil les codent |
| 11 | **Cadrage technique d'US-343 : colonne `messages` (JSON) sur `echanges_conversation` ou table dédiée** | Détermine la migration v81 et son rollback ; à trancher avant d'écrire |
| 12 | **Un jeu de données de dev pour la PWA** et une recette visuelle à 375 px (serveurs 3000 / 8000 à vous : j'utilise 8011 / 5173 en SQLite jetable) | La recette de l'interrupteur `COMPAGNON_MOTEUR` |
| 13 | **Accord de mesure à la porte G2** (même protocole que G0) | Condition de passage du lot 2 |

## 4. Avant le lot 4 (US-346)

| # | Besoin | Pourquoi |
|---|---|---|
| 14 | **Un compte Telegram de test, un bot de test, une base de test et la session Telethon** (harnais d'US-288, jamais joué sur Telegram réel) | G4 rejoue le jeu sur Telegram |
| 15 | **Arbitrage A6** : PWA d'abord, Telegram ensuite — confirmé ? | Ordre des canaux |

## 5. Avant le lot 5 (US-347)

| # | Besoin | Pourquoi |
|---|---|---|
| 16 | **Arbitrages A1, A5, A7** : le §12 de l'ancien document est-il remplacé ? le parseur de gestes reste-t-il devant la boucle (seulement s'il bat la boucle à la mesure) ? que fait-on des US-281 à US-287 non commitées (les terminer ou les geler) ? | Le retrait supprime du code que ces arbitrages protègent |
| 17 | **Une fenêtre de déploiement** : la suppression et la migration de nettoyage éventuelle ne se jouent pas en production sans votre décision | Retour arrière par le dépôt |

## 6. En parallèle, sans bloquer le chemin critique

| # | Besoin | US | Pourquoi |
|---|---|---|---|
| 18 | **Relecture agronomique** des fiches (conduite et problèmes de salade, laitue, mâche, radis, épinard, poireau, oignon, pomme de terre, fraise, petit pois, betterave) | US-348 | Un contenu de jardinage faux est pire qu'un contenu absent ; la relecture est la vôtre |
| 19 | **Sources** pour compléter le référentiel (plantation de la salade, exposition, besoin en eau) : où les prendre (labonnegraine, autre) | US-349 | Chaque donnée porte sa source |
| 20 | **Accord pour un appel réel court par fournisseur** (Large 3, Large 4) | US-350 | Vérifier que `top_p` et le contenu en liste passent |
| 21 | **Option : clé `ANTHROPIC_API_KEY_MESURE`** et `pip install anthropic` | US-337, configuration D | Rejouer Claude + MCP sur le même potager que les autres configurations. Sans elle, la configuration D reste celle du 14/11, sur un autre potager |
| 22 | **Relecture de l'échantillon de 10 %** à chaque porte (une quinzaine de cas, avec leurs traces) | US-337 | Le juge est un modèle : un humain contrôle ce qu'il note |

## 7. Ce que je m'engage à faire de mon côté

- Annoncer le volume et le coût **avant** tout appel au vrai modèle, et attendre votre accord.
- Ne jamais présenter un résultat obtenu sur un modèle simulé comme une mesure.
- Ne pas baliser un scénario : un échec du compagnon se traite par une capacité, l'état structuré, la connaissance ou la mesure,
  jamais par une règle propre à « planter des salades ».
- Ne rien commiter, ne rien déployer et ne rien migrer en production sans votre demande.
- Vous signaler, à chaque US, ce qui reste (comme CA8 aujourd'hui) plutôt que de la déclarer « livrée ».
