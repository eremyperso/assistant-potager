# US-233 — Mesure du modèle de l'agent interpréteur (2026-10-21)

> Rapport produit par `python tools/evaluer_agent.py`. Les chiffres et le verdict calculé viennent de l'outil ; la section « Lecture » est écrite à la main.

## Protocole

- **Échantillon** : 51 phrases (`tests/corpus/us233_agent_echantillon.csv`), dont les phrases du corpus US-172 (source `us172`) enrichies de négations, de paires déclaration / question et de demandes ambiguës.
- **Catalogue d'outils** : provisoire, 10 outils (parcelle_modifier, parcelle_ajouter, parcelle_renommer, parcelle_supprimer, parcelle_lister, lot_consulter, poser_question, saisir_geste, demander_precision, hors_perimetre). Plus petit que le catalogue visé (une quinzaine) : latence et jetons sont un plancher.
- **Chemin** : `llm.passerelle.appeler_chat_outils`, `tool_choice="required"`, une seule tentative de la passerelle sur 429 (puis attente et nouvel essai par l'outil, dénombrés ci-dessous).
- **Prompt** : huit consignes stables écrites une fois, **non ajustées sur les résultats**.
- **Notation** : bon outil = premier outil appelé ; bons paramètres = chaque paramètre attendu juste et aucun champ non évoqué ajouté.

## Modèle `openai/gpt-oss-120b` — NO-GO

### Par catégorie

| Catégorie | Phrases | Bon outil | Bons paramètres | Champs ajoutés | Réussite complète |
|---|---:|---:|---:|---:|---:|
| Commandes (corpus US-172) | 10 | 80 % (8/10) | 89 % (8/9) | 0 | 80 % |
| Négations et retraits | 9 | 100 % (9/9) | 100 % (9/9) | 0 | 100 % |
| Paires déclaration / question | 10 | 90 % (9/10) | 90 % (9/10) | 0 | 90 % |
| Ancrage du champ (rien d'ajouté) | 3 | 100 % (3/3) | 100 % (3/3) | 0 | 100 % |
| Questions (savoir, données) | 5 | 100 % (5/5) | 60 % (3/5) | 0 | 60 % |
| Gestes rapportés | 5 | 80 % (4/5) | — | 0 | 80 % |
| Demandes ambiguës | 5 | 80 % (4/5) | — | 0 | 80 % |
| Hors périmètre | 4 | 100 % (4/4) | — | 0 | 100 % |
| **Total** | 51 | 90 % (46/51) | 89 % (32/36) | 0 | 86 % |

### Latence et jetons

| p50 | p95 | Jetons d'entrée / phrase | Jetons de sortie / phrase | Part servie par le cache | 429 rencontrés |
|---:|---:|---:|---:|---:|---:|
| 426 ms | 1263 ms | 977 | 52 | 34 % | 7 |

### Critères du go / no-go

| | Critère | Seuil | Mesuré | |
|---|---|---:|---:|---|
| C1 (critique) | Bon outil, toutes phrases | ≥ 90 % | 90.2 % | ✅ |
| C2 (critique) | Bons paramètres (phrases qui en attendent) | ≥ 90 % | 88.9 % | ❌ |
| C3 (critique) | Négations et retraits : outil, paramètres, sans champ ajouté | ≥ 85 % | 100.0 % | ✅ |
| C4 (critique) | Déclaration / question : la bonne des deux | ≥ 90 % | 90.0 % | ✅ |
| C5 (critique) | Aucun appel destructeur erroné | 0 | 0 | ✅ |
| C6 (critique) | Échecs techniques (appel malformé, outils refusés, indisponibilité) | ≤ 5 % | 2.0 % | ✅ |
| C7 (critique) | Latence p95 | ≤ 4 000 ms | 1263 ms | ✅ |
| C8 | Précision demandée sur les phrases ambiguës | ≥ 75 % | 80.0 % | ✅ |
| C9 | Champs ajoutés sans avoir été évoqués | ≤ 10 % | 0.0 % | ✅ |
| C10 | Aiguillage (question, geste, hors périmètre) | ≥ 85 % | 78.6 % | ❌ |

### Détail par phrase (7 non réussie(s) sur 51)

| | Phrase | Attendu | Obtenu | Latence |
|---|---|---|---|---:|
| ✅ | crée la parcelle PlancheTomate | `parcelle_ajouter {'nom': 'PlancheTomate'}` | `parcelle_ajouter({"nom": "PlancheTomate"})` | 641 ms |
| ✅ | renomme planche nord en planche des courges | `parcelle_renommer {'ancien_nom': 'planche nord', 'nouveau_nom': 'planche des courges'}` | `parcelle_renommer({"ancien_nom": "Planche Nord", "nouveau_nom": "Planche des courges"})` | 965 ms |
| ✅ | supprime la parcelle PlancheTomate | `parcelle_supprimer {'parcelle': 'PlancheTomate'}` | `parcelle_supprimer({"parcelle": "PlancheTomate"})` | 487 ms |
| ✅ | supprime la planche sud | `parcelle_supprimer {'parcelle': 'planche sud'}` | `parcelle_supprimer({"parcelle": "Planche Sud"})` | 521 ms |
| ✅ | la planche centrale fait 4 rangs | `parcelle_modifier {'parcelle': 'planche centrale', 'nb_rangs': 4}` | `parcelle_modifier({"nb_rangs": 4, "parcelle": "Planche Centrale"})` | 327 ms |
| ✅ | l'exposition de la parcelle nord est plein sud | `parcelle_modifier {'parcelle': 'nord', 'exposition': 'plein sud'}` | `parcelle_modifier({"exposition": "plein sud", "parcelle": "parcelle nord"})` | 447 ms |
| ✅ | la longueur de la planche sud est de 12 mètres | `parcelle_modifier {'parcelle': 'planche sud', 'longueur_m': 12}` | `parcelle_modifier({"longueur_m": 12, "parcelle": "Planche Sud"})` | 513 ms |
| ✅ | mets un tunnel sur la planche centrale | `parcelle_modifier {'parcelle': 'planche centrale', 'abri': 'tunnel'}` | `parcelle_modifier({"abri": "tunnel", "parcelle": "Planche Centrale"})` | 526 ms |
| ❌ | je veux voir mes parcelles | `parcelle_lister` | `poser_question({"nature": "DATA"})` | 474 ms |
| ❌ | montre-moi le lot 128 | `lot_consulter {'numero': 128}` | `poser_question({"nature": "DATA"})` | 322 ms |
| ✅ | Ma serre extérieure n'est plus une pépinière | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Serre extérieure"})` | 530 ms |
| ✅ | arrête la pépinière dans la serre extérieure | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Serre extérieure"})` | 541 ms |
| ✅ | la serre extérieure ne sert plus de pépinière | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Serre extérieure"})` | 869 ms |
| ✅ | retire le statut pépinière du tunnel | `parcelle_modifier {'parcelle': 'tunnel', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Tunnel"})` | 389 ms |
| ✅ | la planche nord n'a plus d'abri | `parcelle_modifier {'parcelle': 'planche nord', 'abri': 'aucun'}` | `parcelle_modifier({"abri": "aucun", "parcelle": "Planche Nord"})` | 426 ms |
| ✅ | retire l'abri de la planche sud | `parcelle_modifier {'parcelle': 'planche sud', 'abri': 'aucun'}` | `parcelle_modifier({"abri": "aucun", "parcelle": "Planche Sud"})` | 264 ms |
| ✅ | la planche sud n'est plus paillée | `parcelle_modifier {'parcelle': 'planche sud', 'paillage': False}` | `parcelle_modifier({"paillage": false, "parcelle": "Planche Sud"})` | 418 ms |
| ✅ | désactive la planche centrale je ne m'en sers plus | `parcelle_modifier {'parcelle': 'planche centrale', 'actif': False}` | `parcelle_modifier({"actif": false, "parcelle": "Planche Centrale"})` | 398 ms |
| ✅ | le tunnel n'est plus actif | `parcelle_modifier {'parcelle': 'tunnel', 'actif': False}` | `parcelle_modifier({"actif": false, "parcelle": "Tunnel"})` | 853 ms |
| ✅ | la serre extérieure est une pépinière | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Serre extérieure"})` | 2565 ms |
| ✅ | la serre extérieure est-elle une pépinière ? | `poser_question {'nature': 'DATA'}` | `poser_question({"nature": "DATA"})` | 1394 ms |
| ✅ | la planche nord a 5 rangs | `parcelle_modifier {'parcelle': 'planche nord', 'nb_rangs': 5}` | `parcelle_modifier({"nb_rangs": 5, "parcelle": "Planche Nord"})` | 554 ms |
| ❌ | combien de rangs a la planche nord ? | `poser_question {'nature': 'DATA'}` | `[appel_invalide]` | 518 ms |
| ✅ | la planche sud fait 12 mètres de long | `parcelle_modifier {'parcelle': 'planche sud', 'longueur_m': 12}` | `parcelle_modifier({"longueur_m": 12, "parcelle": "Planche Sud"})` | 366 ms |
| ✅ | quelle est la longueur de la planche sud ? | `poser_question {'nature': 'DATA'}` | `poser_question({"nature": "DATA"})` | 402 ms |
| ✅ | mets la planche centrale en pépinière | `parcelle_modifier {'parcelle': 'planche centrale', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Planche Centrale"})` | 653 ms |
| ✅ | quelles sont mes pépinières ? | `poser_question {'nature': 'DATA'}` | `poser_question({"nature": "DATA"})` | 606 ms |
| ✅ | la planche nord est exposée plein sud | `parcelle_modifier {'parcelle': 'planche nord', 'exposition': 'plein sud'}` | `parcelle_modifier({"exposition": "plein sud", "parcelle": "Planche Nord"})` | 398 ms |
| ✅ | comment est exposée la planche nord ? | `poser_question {'nature': 'DATA'}` | `poser_question({"nature": "DATA"})` | 215 ms |
| ✅ | mets la serre en pépinière | `parcelle_modifier {'parcelle': 'serre', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Serre extérieure"})` | 415 ms |
| ✅ | passe la planche centrale en pépinière | `parcelle_modifier {'parcelle': 'planche centrale', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Planche Centrale"})` | 446 ms |
| ✅ | la planche nord a maintenant 6 rangs | `parcelle_modifier {'parcelle': 'planche nord', 'nb_rangs': 6}` | `parcelle_modifier({"nb_rangs": 6, "parcelle": "Planche Nord"})` | 247 ms |
| ✅ | comment supprimer une parcelle ? | `poser_question {'nature': 'SAVOIR'}` | `poser_question({"nature": "SAVOIR"})` | 301 ms |
| ✅ | comment renommer une parcelle ? | `poser_question {'nature': 'SAVOIR'}` | `poser_question({"nature": "SAVOIR"})` | 439 ms |
| ❌ | comment est calculé le bilan ? | `poser_question {'nature': 'SAVOIR'}` | `poser_question({"nature": "DATA"})` | 193 ms |
| ❌ | comment consulter mon historique ? | `poser_question {'nature': 'SAVOIR'}` | `poser_question({"nature": "DATA"})` | 328 ms |
| ✅ | quand ai-je planté les tomates ? | `poser_question {'nature': 'DATA'}` | `poser_question({"nature": "DATA"})` | 388 ms |
| ✅ | récolté 2 kg de tomates cerise | `saisir_geste` | `saisir_geste({"": {}})` | 199 ms |
| ✅ | arrosé les courgettes 30 min | `saisir_geste` | `saisir_geste({"": {}})` | 379 ms |
| ❌ | semé carottes Nantaise rang 4 | `saisir_geste` | `demander_precision({"question": "Sur quelle parcelle souhaitez‑vous semer les carottes Nantaise au rang 4 ?"})` | 507 ms |
| ✅ | j'ai vendu 6 plants de tomate | `saisir_geste` | `saisir_geste({})` | 321 ms |
| ✅ | planté 4 salades sur 3 rangs dans la planche nord | `saisir_geste` | `saisir_geste({"": {}})` | 250 ms |
| ✅ | modifie ma serre | `demander_precision` | `demander_precision({"question": "Quelle caractéristique de la serre souhaitez‑vous modifier (abri, actif, ensoleillement, etc.) ?"})` | 626 ms |
| ✅ | supprime la parcelle près des tomates | `demander_precision` | `demander_precision({"question": "Quelle est le nom exact de la parcelle que vous souhaitez supprimer ?"})` | 345 ms |
| ✅ | change la planche | `demander_precision` | `demander_precision({"question": "Quelle modification souhaitez‑vous apporter à la planche ? (ex. abri, superficie, type de sol, etc.)"})` | 226 ms |
| ✅ | mets-la en pépinière | `demander_precision` | `demander_precision({"question": "Quelle parcelle souhaitez-vous mettre en pépinière ?"})` | 222 ms |
| ❌ | renomme la planche nord | `demander_precision` | `parcelle_renommer({"ancien_nom": "Planche Nord", "nouveau_nom": "Planche Nord"})` | 506 ms |
| ✅ | exporte-moi tout l'historique en Excel | `hors_perimetre` | `hors_perimetre({"raison": "exporter l'historique en Excel"})` | 481 ms |
| ✅ | envoie le plan par mail à mon voisin | `hors_perimetre` | `hors_perimetre({"raison": "envoi du plan par mail"})` | 1263 ms |
| ✅ | commande des graines de tomates pour moi | `hors_perimetre` | `hors_perimetre({"raison": "commande de graines"})` | 216 ms |
| ✅ | règle un rappel demain à 8 heures | `hors_perimetre` | `hors_perimetre({"raison": "rappel"})` | 226 ms |

## Verdict calculé

**Modèle retenu : aucun.** `openai/gpt-oss-120b` : NO-GO.

Règle : NO-GO si un critère critique (C1 à C7) échoue ; GO avec réserves si seuls C8 à C10 échouent ; GO sinon. Parmi les modèles qui ne sont pas NO-GO, le plus juste, puis le plus rapide.

## Lecture et décision

*Écrite à la main le 21/10/2026, après deux passages complets du même modèle (voir « Répétition »). Les seuils C1 à C10 sont fixés dans l'outil depuis avant la première mesure ; ils n'ont pas bougé.*

### Décision

**NO-GO au sens strict du protocole**, pour `openai/gpt-oss-120b` : C2 (bons paramètres) à 88,9 % pour 90 % attendus, et C10 (aiguillage) à 78,6 % pour 85 %. Les deux passages donnent exactement les mêmes taux : l'écart est reproductible, ce n'est pas du bruit.

**Modèle retenu : aucun à ce stade.** `openai/gpt-oss-120b` est le seul modèle qui ait pu être mesuré (voir « Limites »).

**Recommandation** : ne pas arrêter l'épic. Lancer US-235 en `AGENT_MODE=ombre` uniquement, avec les exigences du tableau ci-dessous, puis refaire cette mesure sur les phrases que l'agent voit réellement avant tout passage en `actif`. Le mode `ombre` n'affiche rien au jardinier : il ne coûte que des appels. La décision de lancer US-235 appartient au responsable du produit ; ce rapport ne la prend pas à sa place.

### Ce que la mesure établit

- **La thèse centrale de l'architecture tient.** Les 9 négations et retraits sont réussis aux deux passages, y compris « Ma serre extérieure n'est plus une pépinière » → `parcelle_modifier(parcelle="Serre extérieure", est_pepiniere=false)`. Aucune règle n'a été écrite : le booléen typé porte le sens.
- **Aucun champ ajouté sans avoir été évoqué** (0 sur 36 phrases à paramètres, dont 3/3 sur les phrases d'ancrage comme « mets la serre en pépinière », sans `type_pepiniere` inventé). Le risque que la règle 9 du validateur devait couvrir ne s'est pas présenté.
- **Aucun appel destructeur erroné.**
- **Latence** : p50 426 à 446 ms, p95 888 à 1 263 ms, très en dessous du seuil de 4 s.
- **Jetons** : 977 en entrée et 52 en sortie par phrase pour un catalogue de 10 outils. L'architecture (§3.8) tablait sur 2 à 3 000 jetons de préfixe pour le catalogue complet : l'ordre de grandeur était surestimé. Part servie par le cache : 34 % au premier passage, 65 % au second (le cache se réchauffe).

### Ce qui échoue, et ce que cela change

| Phrase(s) | Obtenu | Gravité | À faire |
|---|---|---|---|
| « je veux voir mes parcelles », « montre-moi le lot 128 » | `poser_question(DATA)` au lieu de `parcelle_lister` / `lot_consulter` | Faible. La cascade des questions y répond, et les règles de commande reconnaissent déjà ces deux phrases : elles n'atteindront pas l'agent | Rien |
| « comment est calculé le bilan ? », « comment consulter mon historique ? » | `poser_question(DATA)` au lieu de `SAVOIR` | Faible mais systématique : le modèle voit bien une question, il se trompe sur sa nature | US-236 : ne retenir de l'agent que « c'est une question » et laisser le routeur existant fixer la nature (ou retirer `nature` du schéma) |
| « semé carottes Nantaise rang 4 » | `demander_precision` (« sur quelle parcelle ? ») au lieu de `saisir_geste` | Faible : le filtre « geste annoncé » et le parseur passent avant l'agent. Mais la consigne 6 (information manquante → précision) se déclenche trop | US-235 : surveiller cette consigne en `ombre` ; ne jamais soumettre un geste à l'agent (A6) |
| « renomme la planche nord » | `parcelle_renommer(ancien_nom="Planche Nord", nouveau_nom="Planche Nord")` au lieu de demander le nouveau nom | **La seule qui compte.** Le modèle comble l'argument obligatoire manquant en recopiant l'ancien nom. Les deux noms figurent dans la phrase : l'ancrage par nature (§2.3) l'accepterait, et seul le récapitulatif (« Planche Nord → Planche Nord ») l'arrêterait | US-235 : le validateur rejette un renommage vers le même nom et le traite comme un argument manquant. Plus généralement, un argument obligatoire qui n'est qu'une copie d'un autre argument est suspect. À mesurer à nouveau |
| « combien de rangs a la planche nord ? » (passage 1), « quelle est la longueur de la planche sud ? » (passage 2) | `appel_invalide` : le fournisseur rejette l'appel d'outil que le modèle a mal formé (`tool_use_failed`) | Aléatoire : 1 phrase sur 51 à chaque passage, pas la même d'un passage à l'autre. 2 % d'échecs techniques, sous le seuil de 5 % | Rien : la passerelle rend un statut, pas une exception, et l'appelant retombe sur l'ancien chemin (règles puis routeur) |

### Lecture sur la population réelle (a posteriori)

⚠️ Ce calcul est fait après avoir vu les chiffres : il éclaire le verdict, il ne le remplace pas.

Trois des phrases en échec n'atteindront jamais l'agent en production : les deux commandes de consultation (reconnues par les règles, 100 % sur le corpus US-172) et le geste (écarté avant tout appel au modèle par `llm.routeur.annonce_un_geste`, que `interpreter()` consulte déjà). « renomme la planche nord », elle, atteindrait bien l'agent : aucune règle ne la reconnaît et ce n'est pas un geste. Sans les trois phrases écartées :

- C1 passerait à 95,8 % (46/48) et C2 à 91,4 % (32/35), donc au-dessus des seuils ;
- C10 serait à 84,6 % (11/13) avec la nature de la question comptée, à 0,4 point du seuil, et à 13/13 si l'on ne retient que « c'est une question ».

On ne choisit pas la population après avoir vu les résultats : c'est la raison de recommander une nouvelle mesure sur les phrases réellement soumises à l'agent (journal `routage_logs`, issues `refusee` et `abandonnee`) plutôt que de conclure sur ce calcul.

### Répétition

| | Passage 1 (rapport ci-dessus) | Passage 2 |
|---|---:|---:|
| Bon outil | 90,2 % | 90,2 % |
| Bons paramètres | 88,9 % | 88,9 % |
| Négations et retraits | 100 % | 100 % |
| Déclaration / question | 90 % | 90 % |
| Aiguillage (C10) | 78,6 % | 78,6 % |
| Latence p50 / p95 | 426 / 1 263 ms | 446 / 888 ms |
| Part servie par le cache | 34 % | 65 % |
| 429 rencontrés (attendus puis rejoués) | 7 | 2 |
| Phrases en échec | les 6 ci-dessus + 1 appel malformé | les mêmes 6 + 1 appel malformé, sur une autre phrase |

### Limites

- **Un seul modèle mesuré.** Pour cette clé, `openai/gpt-oss-20b` et `qwen/qwen3.8-27b` sont listés mais **bloqués au niveau de l'organisation Groq** (403 `model_permission_blocked_org`), `llama-3.3-70b-versatile` n'existe pas (404) et `moonshotai/kimi-k2-instruct-0905` n'est pas listé. Pour comparer, un administrateur doit activer les modèles dans https://console.groq.com/settings/limits, puis relancer `python tools/evaluer_agent.py --modeles openai/gpt-oss-120b,openai/gpt-oss-20b` (ajouter `--sans-raisonnement <modèle>` pour un modèle qui refuse `reasoning_effort`).
- **Catalogue provisoire de 10 outils**, contre une quinzaine visés : latence et jetons sont un plancher.
- **Échantillon de 51 phrases dont 36 attendent des paramètres** : une phrase pèse 2,8 points sur C2, et il en aurait fallu une de plus pour franchir 90 %. Une partie des phrases sont celles que les règles reconnaissent déjà.
- **Prompt non ajusté** : huit consignes écrites une fois. Un prompt retouché améliorerait peut-être les cas 2 et 3 ; rien n'a été tenté, pour ne pas mesurer le prompt à la place du modèle.
- **Clé de la plateforme uniquement** : le comportement d'un modèle BYOK sans outils est couvert par la détection de la passerelle (tests unitaires), pas par cette mesure.
- **Écritures en base** : la mesure a écrit environ 120 lignes `conso_tokens` (`appel_type = 'agent'`, potager 1) dans la base de `.env.dev`. C'est la preuve que l'appel passe par le chemin réel de la passerelle.

### Relancer la mesure

```bash
python tools/evaluer_agent.py --dry-run                    # le plan, sans dépenser un jeton
python tools/evaluer_agent.py --detail                     # le modèle de GROQ_MODEL_AGENT
python tools/evaluer_agent.py --modeles openai/gpt-oss-120b,openai/gpt-oss-20b
```
