# INC-018 — Mesure du prompt et du catalogue livrés, sur le vrai modèle (2026-10-23)

> Rapport produit par `python tools/evaluer_agent.py`. Les chiffres et le verdict calculé viennent de l'outil ; la section « Lecture » est écrite à la main.

## Protocole

- **Échantillon** : 72 phrases (`tests/corpus/us233_agent_echantillon.csv`) : les phrases du corpus US-172 (source `us172`), des négations, des paires déclaration / question, des demandes ambiguës (source `nouveau`), puis les créations, phrases à plusieurs actions, conseils et doutes d'INC-018 (source `inc018`).
- **Catalogue d'outils** : celui livré (`catalogue_outils.schemas()`), 14 outils (parcelle_modifier, parcelle, association_saisir, culture, calendrier, bioagresseur, potager, parcelle_supprimer, consulter, lire, poser_question, saisir_geste, demander_precision, hors_perimetre), champs facultatifs nullables.
- **Chemin** : `llm.passerelle.appeler_chat_outils`, `tool_choice="required"`, une seule tentative de la passerelle sur 429 (puis attente et nouvel essai par l'outil, dénombrés ci-dessous).
- **Prompt** : `interpreteur_agent.PROMPT_FIXE`, tel que livré, **non ajusté sur ces résultats**.
- **Notation** : bon outil = premier outil appelé ; bons paramètres = chaque paramètre attendu juste et aucun champ non évoqué ajouté.

## Modèle `openai/gpt-oss-120b` — NO-GO

### Par catégorie

| Catégorie | Phrases | Bon outil | Bons paramètres | Champs ajoutés | Appels rejetés | Précisions inutiles | Réussite complète |
|---|---:|---:|---:|---:|---:|---:|---:|
| Commandes (corpus US-172) | 10 | 100 % (10/10) | 100 % (10/10) | 0 | 0 | 0 | 100 % |
| Négations et retraits | 9 | 100 % (9/9) | 100 % (9/9) | 0 | 0 | 0 | 100 % |
| Paires déclaration / question | 10 | 70 % (7/10) | 70 % (7/10) | 0 | 0 | 0 | 70 % |
| Ancrage du champ (rien d'ajouté) | 3 | 100 % (3/3) | 100 % (3/3) | 0 | 0 | 0 | 100 % |
| Créations (INC-018) | 6 | 67 % (4/6) | 67 % (4/6) | 0 | 0 | 2 | 67 % |
| Créations avec caractéristiques | 2 | 0 % (0/2) | — | 0 | 0 | 0 | 0 % |
| Phrases à plusieurs actions | 4 | 0 % (0/4) | — | 0 | 0 | 0 | 0 % |
| Conseils avec un verbe d'action | 5 | 100 % (5/5) | 100 % (1/1) | 0 | 0 | 0 | 100 % |
| Doutes (action risquée ou sous-déterminée) | 4 | 75 % (3/4) | — | 0 | 0 | 0 | 75 % |
| Questions (savoir, données) | 5 | 60 % (3/5) | 60 % (3/5) | 0 | 0 | 1 | 60 % |
| Gestes rapportés | 5 | 100 % (5/5) | — | 0 | 0 | 0 | 100 % |
| Demandes ambiguës | 5 | 100 % (5/5) | — | 0 | 0 | 0 | 100 % |
| Hors périmètre | 4 | 100 % (4/4) | — | 0 | 0 | 0 | 100 % |
| **Total** | 72 | 81 % (58/72) | 84 % (37/44) | 0 | 0 | 3 | 81 % |

### Latence et jetons

| p50 | p95 | Jetons d'entrée / phrase | Jetons de sortie / phrase | Part servie par le cache | 429 rencontrés |
|---:|---:|---:|---:|---:|---:|
| 250 ms | 669 ms | 3452 | 64 | 80 % | 10 |

### Critères du go / no-go

| | Critère | Seuil | Mesuré | |
|---|---|---:|---:|---|
| C1 (critique) | Bon outil, toutes phrases | ≥ 90 % | 80.6 % | ❌ |
| C2 (critique) | Bons paramètres (phrases qui en attendent) | ≥ 90 % | 84.1 % | ❌ |
| C3 (critique) | Négations et retraits : outil, paramètres, sans champ ajouté | ≥ 85 % | 100.0 % | ✅ |
| C4 (critique) | Déclaration / question : la bonne des deux | ≥ 90 % | 70.0 % | ❌ |
| C5 (critique) | Aucun appel destructeur erroné | 0 | 0 | ✅ |
| C6 (critique) | Échecs techniques (appel malformé, outils refusés, indisponibilité) | ≤ 5 % | 0.0 % | ✅ |
| C7 (critique) | Latence p95 | ≤ 4 000 ms | 669 ms | ✅ |
| C8 | Précision demandée sur les phrases ambiguës | ≥ 75 % | 100.0 % | ✅ |
| C9 | Champs ajoutés sans avoir été évoqués | ≤ 10 % | 0.0 % | ✅ |
| C10 | Aiguillage (question, geste, hors périmètre) | ≥ 85 % | 85.7 % | ✅ |
| C11 (critique) | Appels rejetés par le serveur (`appel_invalide`), créations et plans | 0 | 0 | ✅ |
| C12 (critique) | Champs inventés, toutes phrases à paramètres | 0 | 0 | ✅ |
| C13 | Précisions demandées pour rien (phrases qui ne sont ni ambiguës ni douteuses) | ≤ 5 % | 4.8 % | ✅ |

### Détail par phrase (14 non réussie(s) sur 72)

| | Phrase | Attendu | Obtenu | Latence |
|---|---|---|---|---:|
| ✅ | crée la parcelle PlancheTomate | `parcelle {'action': 'ajouter', 'nom': 'PlancheTomate'}` | `parcelle({"action": "ajouter", "nom": "PlancheTomate"})` | 801 ms |
| ✅ | renomme planche nord en planche des courges | `parcelle {'action': 'renommer', 'ancien': 'planche nord', 'nouveau': 'planche des courges'}` | `parcelle({"action": "renommer", "ancien": "Planche Nord", "nouveau": "Planche des courges"})` | 645 ms |
| ✅ | supprime la parcelle PlancheTomate | `parcelle_supprimer {'nom': 'PlancheTomate'}` | `parcelle_supprimer({"nom": "PlancheTomate"})` | 343 ms |
| ✅ | supprime la planche sud | `parcelle_supprimer {'nom': 'planche sud'}` | `parcelle_supprimer({"nom": "Planche Sud"})` | 222 ms |
| ✅ | la planche centrale fait 4 rangs | `parcelle_modifier {'parcelle': 'planche centrale', 'nb_rangs': 4}` | `parcelle_modifier({"nb_rangs": 4, "parcelle": "Planche Centrale"})` | 595 ms |
| ✅ | l'exposition de la parcelle nord est plein sud | `parcelle_modifier {'parcelle': 'nord', 'exposition': 'Sud'}` | `parcelle_modifier({"exposition": "Sud", "parcelle": "Planche Nord"})` | 327 ms |
| ✅ | la longueur de la planche sud est de 12 mètres | `parcelle_modifier {'parcelle': 'planche sud', 'longueur_m': 12}` | `parcelle_modifier({"longueur_m": 12, "parcelle": "Planche Sud"})` | 628 ms |
| ✅ | mets un tunnel sur la planche centrale | `parcelle_modifier {'parcelle': 'planche centrale', 'abri': 'tunnel'}` | `parcelle_modifier({"abri": "tunnel", "parcelle": "Planche Centrale"})` | 247 ms |
| ✅ | je veux voir mes parcelles | `consulter {'commande': 'parcelle lister'}` | `consulter({"commande": "parcelle lister"})` | 433 ms |
| ✅ | montre-moi le lot 128 | `consulter {'commande': 'lot', 'numero': 128}` | `consulter({"commande": "lot", "numero": 128})` | 334 ms |
| ✅ | Ma serre extérieure n'est plus une pépinière | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Serre extérieure"})` | 257 ms |
| ✅ | arrête la pépinière dans la serre extérieure | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Serre extérieure"})` | 340 ms |
| ✅ | la serre extérieure ne sert plus de pépinière | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Serre extérieure"})` | 232 ms |
| ✅ | retire le statut pépinière du tunnel | `parcelle_modifier {'parcelle': 'tunnel', 'est_pepiniere': False}` | `parcelle_modifier({"est_pepiniere": false, "parcelle": "Tunnel"})` | 227 ms |
| ✅ | la planche nord n'a plus d'abri | `parcelle_modifier {'parcelle': 'planche nord', 'abri': 'aucun'}` | `parcelle_modifier({"abri": "aucun", "parcelle": "Planche Nord"})` | 233 ms |
| ✅ | retire l'abri de la planche sud | `parcelle_modifier {'parcelle': 'planche sud', 'abri': 'aucun'}` | `parcelle_modifier({"abri": "aucun", "parcelle": "Planche Sud"})` | 402 ms |
| ✅ | la planche sud n'est plus paillée | `parcelle_modifier {'parcelle': 'planche sud', 'paillage': False}` | `parcelle_modifier({"paillage": false, "parcelle": "Planche Sud"})` | 264 ms |
| ✅ | désactive la planche centrale je ne m'en sers plus | `parcelle_modifier {'parcelle': 'planche centrale', 'actif': False}` | `parcelle_modifier({"actif": false, "parcelle": "Planche Centrale"})` | 214 ms |
| ✅ | le tunnel n'est plus actif | `parcelle_modifier {'parcelle': 'tunnel', 'actif': False}` | `parcelle_modifier({"actif": false, "parcelle": "Tunnel"})` | 190 ms |
| ✅ | la serre extérieure est une pépinière | `parcelle_modifier {'parcelle': 'serre extérieure', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Serre extérieure"})` | 283 ms |
| ✅ | la serre extérieure est-elle une pépinière ? | `poser_question {'nature': 'QUESTION_DATA'}` | `poser_question({"nature": "QUESTION_DATA"})` | 174 ms |
| ✅ | la planche nord a 5 rangs | `parcelle_modifier {'parcelle': 'planche nord', 'nb_rangs': 5}` | `parcelle_modifier({"nb_rangs": 5, "parcelle": "Planche Nord"})` | 221 ms |
| ❌ | combien de rangs a la planche nord ? | `poser_question {'nature': 'QUESTION_DATA'}` | `lire({"nom": "Planche Nord", "quoi": "parcelle"})` | 288 ms |
| ✅ | la planche sud fait 12 mètres de long | `parcelle_modifier {'parcelle': 'planche sud', 'longueur_m': 12}` | `parcelle_modifier({"longueur_m": 12, "parcelle": "Planche Sud"})` | 506 ms |
| ❌ | quelle est la longueur de la planche sud ? | `poser_question {'nature': 'QUESTION_DATA'}` | `lire({"nom": "Planche Sud", "quoi": "parcelle"})` | 246 ms |
| ✅ | mets la planche centrale en pépinière | `parcelle_modifier {'parcelle': 'planche centrale', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Planche Centrale"})` | 348 ms |
| ✅ | quelles sont mes pépinières ? | `poser_question {'nature': 'QUESTION_DATA'}` | `poser_question({"nature": "QUESTION_DATA"})` | 182 ms |
| ✅ | la planche nord est exposée plein sud | `parcelle_modifier {'parcelle': 'planche nord', 'exposition': 'Sud'}` | `parcelle_modifier({"exposition": "Sud", "parcelle": "Planche Nord"})` | 253 ms |
| ❌ | comment est exposée la planche nord ? | `poser_question {'nature': 'QUESTION_DATA'}` | `lire({"nom": "Planche Nord", "quoi": "parcelle"})` | 256 ms |
| ✅ | mets la serre en pépinière | `parcelle_modifier {'parcelle': 'serre', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Serre extérieure"})` | 336 ms |
| ✅ | passe la planche centrale en pépinière | `parcelle_modifier {'parcelle': 'planche centrale', 'est_pepiniere': True}` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Planche Centrale"})` | 197 ms |
| ✅ | la planche nord a maintenant 6 rangs | `parcelle_modifier {'parcelle': 'planche nord', 'nb_rangs': 6}` | `parcelle_modifier({"nb_rangs": 6, "parcelle": "Planche Nord"})` | 635 ms |
| ✅ | comment supprimer une parcelle ? | `poser_question {'nature': 'QUESTION_SAVOIR'}` | `poser_question({"nature": "QUESTION_SAVOIR"})` | 330 ms |
| ❌ | comment renommer une parcelle ? | `poser_question {'nature': 'QUESTION_SAVOIR'}` | `demander_precision({"question": "Quelle parcelle veux‑tu renommer et quel nouveau nom lui donner ?"})` | 203 ms |
| ✅ | comment est calculé le bilan ? | `poser_question {'nature': 'QUESTION_SAVOIR'}` | `poser_question({"nature": "QUESTION_SAVOIR"})` | 607 ms |
| ❌ | comment consulter mon historique ? | `poser_question {'nature': 'QUESTION_SAVOIR'}` | `consulter({"commande": "historique"})` | 225 ms |
| ✅ | quand ai-je planté les tomates ? | `poser_question {'nature': 'QUESTION_DATA'}` | `poser_question({"nature": "QUESTION_DATA"})` | 167 ms |
| ✅ | récolté 2 kg de tomates cerise | `saisir_geste` | `saisir_geste({})` | 489 ms |
| ✅ | arrosé les courgettes 30 min | `saisir_geste` | `saisir_geste({})` | 200 ms |
| ✅ | semé carottes Nantaise rang 4 | `saisir_geste` | `saisir_geste({})` | 200 ms |
| ✅ | j'ai vendu 6 plants de tomate | `saisir_geste` | `saisir_geste({"": {}})` | 168 ms |
| ✅ | planté 4 salades sur 3 rangs dans la planche nord | `saisir_geste` | `saisir_geste({})` | 161 ms |
| ✅ | modifie ma serre | `demander_precision` | `demander_precision({"question": "Quelle modification souhaites‑tu apporter à ta serre ?"})` | 185 ms |
| ✅ | supprime la parcelle près des tomates | `demander_precision` | `demander_precision({"question": "Quelle est le nom exact de la parcelle que tu veux supprimer ?"})` | 219 ms |
| ✅ | change la planche | `demander_precision` | `demander_precision({"question": "Quelle modification veux‑tu apporter à la planche ?"})` | 244 ms |
| ✅ | mets-la en pépinière | `demander_precision` | `demander_precision({"question": "Quelle parcelle veux‑tu mettre en pépinière ?"})` | 237 ms |
| ✅ | renomme la planche nord | `demander_precision` | `demander_precision({"question": "Quel nouveau nom veux‑tu donner à la planche nord ?"})` | 230 ms |
| ✅ | exporte-moi tout l'historique en Excel | `hors_perimetre` | `hors_perimetre({"raison": "exporter l'historique en Excel"})` | 514 ms |
| ✅ | envoie le plan par mail à mon voisin | `hors_perimetre` | `hors_perimetre({"raison": "envoi du plan par mail"})` | 778 ms |
| ✅ | commande des graines de tomates pour moi | `hors_perimetre` | `hors_perimetre({"raison": "commande de graines"})` | 196 ms |
| ✅ | règle un rappel demain à 8 heures | `hors_perimetre` | `hors_perimetre({"raison": "rappel"})` | 248 ms |
| ✅ | crée la planche Nord | `parcelle {'action': 'ajouter', 'nom': 'planche nord'}` | `parcelle({"action": "ajouter", "nom": "Planche Nord"})` | 221 ms |
| ❌ | crée la planche Est | `parcelle {'action': 'ajouter', 'nom': 'planche est'}` | `demander_precision({"question": "Quelle exposition souhaites‑tu pour la planche Est ?"})` | 203 ms |
| ✅ | ajoute la planche Ouest | `parcelle {'action': 'ajouter', 'nom': 'planche ouest'}` | `parcelle({"action": "ajouter", "nom": "planche Ouest"})` | 226 ms |
| ✅ | crée une parcelle Carré des herbes de 6 m² | `parcelle {'action': 'ajouter', 'nom': 'Carré des herbes', 'superficie': 6}` | `parcelle({"action": "ajouter", "nom": "Carré des herbes", "superficie": 6})` | 232 ms |
| ✅ | crée la parcelle tunnel sud exposée au sud | `parcelle {'action': 'ajouter', 'nom': 'tunnel sud', 'exposition': 'sud'}` | `parcelle({"action": "ajouter", "exposition": "Sud", "nom": "tunnel sud"})` | 669 ms |
| ❌ | nouvelle planche Centre | `parcelle {'action': 'ajouter', 'nom': 'planche centre'}` | `demander_precision({"question": "Quelle est l'exposition de la nouvelle planche Centre ?"})` | 350 ms |
| ❌ | crée la planche Nord de 8 mètres de long avec 4 rangs | `parcelle+parcelle_modifier` | `parcelle({"action": "ajouter", "exposition": null, "longueur": 8, "nb_rangs": 4, "nom": "Planche Nord", "superficie": null})` | 287 ms |
| ❌ | crée la parcelle Verger de 20 m² et mets-la à l'ombre | `parcelle+parcelle_modifier` | `parcelle({"action": "ajouter", "nom": "Verger", "superficie": 20})` | 331 ms |
| ❌ | Créez la planche Nord de 8 mètres de long avec 4 rangs et mets la serre en pépinière froide. | `parcelle+parcelle_modifier+parcelle_modifier` | `parcelle({"action": "ajouter", "exposition": null, "nom": "planche Nord", "superficie": null})` | 550 ms |
| ❌ | mets la serre en pépinière froide et la planche centrale en pépinière chaude | `parcelle_modifier+parcelle_modifier` | `parcelle_modifier({"est_pepiniere": true, "parcelle": "Serre extérieure", "type_pepiniere": "froide"})` | 312 ms |
| ❌ | renomme la planche sud en planche des courges et supprime la planche nord | `parcelle+parcelle_supprimer` | `parcelle({"action": "renommer", "ancien": "Planche Sud", "nouveau": "Planche des courges"})` | 915 ms |
| ❌ | passe la planche nord en plein soleil et montre-moi le plan | `parcelle_modifier+consulter` | `parcelle_modifier({"ensoleillement": "plein soleil", "parcelle": "Planche Nord"})` | 246 ms |
| ✅ | devrais-je créer une planche pour les courges ? | `poser_question` | `poser_question({"nature": "QUESTION_SAVOIR"})` | 144 ms |
| ✅ | est-ce que je peux supprimer la planche sud sans perdre mon historique ? | `poser_question` | `poser_question({"nature": "QUESTION_DATA"})` | 190 ms |
| ✅ | faut-il renommer la planche nord ? | `poser_question` | `poser_question({"nature": "QUESTION_SAVOIR"})` | 193 ms |
| ✅ | je pense créer une planche de basilic, qu'en penses-tu ? | `poser_question` | `poser_question({"nature": "QUESTION_SAVOIR"})` | 258 ms |
| ✅ | comment mettre une serre en pépinière ? | `poser_question {'nature': 'QUESTION_SAVOIR'}` | `poser_question({"nature": "QUESTION_SAVOIR"})` | 197 ms |
| ✅ | supprime la planche | `demander_precision` | `demander_precision({"question": "Quelle planche veux‑tu supprimer exactement ? (Planche Nord, Sud ou Centrale)"})` | 287 ms |
| ❌ | enlève la serre | `demander_precision` | `parcelle_modifier({"abri": "aucun", "parcelle": "Serre extérieure"})` | 373 ms |
| ✅ | supprime tout | `demander_precision/hors_perimetre` | `demander_precision({"question": "Tu veux vraiment supprimer toutes les parcelles du potager ? Confirme‑le s’il te plaît."})` | 272 ms |
| ✅ | change le nom de la planche | `demander_precision` | `demander_precision({"question": "Quel nouveau nom veux‑tu donner à la planche ?"})` | 212 ms |

## Verdict calculé

**Modèle retenu : aucun.** `openai/gpt-oss-120b` : NO-GO.

Règle : NO-GO si un critère critique (C1 à C7, C11, C12) échoue ; GO avec réserves si seuls C8 à C10 et C13 échouent ; GO sinon. Parmi les modèles qui ne sont pas NO-GO, le plus juste, puis le plus rapide.
