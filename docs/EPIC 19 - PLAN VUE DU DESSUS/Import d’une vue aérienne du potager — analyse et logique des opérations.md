# Import d’une vue aérienne du potager — analyse et logique des opérations

Nov 12, 2026 · @emmanuel

Le jardinier obtient le fond de son plan sans drone ni photo d’ensemble : il prend plusieurs photos guidées depuis le sol, l’application vérifie qu’elles suffisent, en tire une vue du dessus, la transforme en plan paysager simplifié, puis il la valide et y pose ses parcelles. Seul ce plan simplifié est conservé : c’est la solution RGPD.

## 1. Le besoin

> En tant que jardinier, je veux obtenir une vue du dessus de mon potager à partir de photos prises depuis le sol, afin de poser mes parcelles sur un plan qui ressemble à mon terrain (piste C du Plan, page « Plan · pistes »).

Point de départ : dans « Modifier le plan », le jardinier choisit **Fond du plan › Vue aérienne**. Cette option devient une fonction à part entière, avec son propre parcours.

| # | Exigence | Origine |
| --- | --- | --- |
| A1 | Capturer le potager en plusieurs prises (angles, parcelles, zones), sans drone ni point haut obligatoire | besoin |
| A2 | Détecter si les captures suffisent pour produire une vue unique, et dire ce qui manque | besoin |
| A3 | Projeter ou transformer les captures en une vue du dessus | besoin |
| A4 | Transformer cette vue en plan paysager simplifié, d’après le prompt fourni (géométrie simple, pastels, aucun élément inventé) | besoin |
| A5 | Passer par des API de traitement d’image (agent IA spécialisé ou autre) | besoin |
| A6 | Garantir les conditions RGPD par une solution unique | besoin |
| A7 | Deux niveaux de plan : structurel (sans végétal) et paysager (végétal géométrisé) | recommandation du prompt |
| A8 | Conserver l’organisation spatiale réelle, priorité absolue sur l’esthétique | prompt |

## 2. Contraintes et décisions

La contrainte qui décide de tout : un modèle d’image génératif sait dessiner une vue du dessus, mais il ne garantit ni les distances ni l’absence d’éléments inventés. La géométrie doit donc venir d’une mesure (les dimensions des parcelles déjà connues), et le modèle seulement l’habiller.

| # | Contrainte | Conséquence |
| --- | --- | --- |
| C1 | Une vraie orthophoto par photogrammétrie demande des vues proches de la verticale et 70 à 80 % de recouvrement entre prises ([OpenDroneMap](https://docs.opendronemap.org/flying)) | Depuis le sol, elle n’est fiable que si le jardinier dispose d’un point haut (étage, escabeau). Elle ne peut pas être le chemin principal |
| C2 | Les modèles d’édition d’image acceptent plusieurs photos de référence (8 à 16 selon le fournisseur) mais composent librement ([comparatif mai 2026](https://techstackups.com/comparisons/gemini-vs-openai-vs-flux-vs-runway-character-consistency-may-2026/)) | Risque d’éléments déplacés ou inventés, contraire à l’exigence A8. Un contrôle de fidélité et une validation par le jardinier sont obligatoires |
| C3 | Ce qu’aucune photo ne voit (derrière la serre, sous un arbre) est inconnu | La zone reste neutre sur le plan, jamais « complétée » |
| C4 | Une photo ne porte aucune échelle | L’échelle vient des parcelles connues (longueur, largeur de la fiche parcelle) et de deux ou trois points touchés par le jardinier |
| C5 | La boussole du téléphone est imprécise (plusieurs degrés, davantage près du métal) ; iOS demande l’accès aux capteurs après un geste | Le cap sert d’indice d’orientation ; le nord se confirme sur la rose des vents de l’éditeur |
| C6 | Les photos montrent la maison, parfois des personnes, des voisins, des véhicules | Données personnelles envoyées à un tiers : floutage avant envoi et suppression rapide (§ 8) |
| C7 | Coût de quelques centimes à environ 0,20 $ par image générée, délai de plusieurs dizaines de secondes, plusieurs essais possibles | Traitement en tâche de fond, plafond par potager (§ 9) |
| C8 | La génération d’image de Mistral (outil d’agent) produit des images ; l’édition à partir de photos n’y est pas documentée ([doc Mistral](https://docs.mistral.ai/agents/connectors/image_generation)) | Mistral convient pour l’analyse des photos (vision), pas pour la transformation ; il faut un fournisseur d’édition d’image en plus |
| C9 | La caméra d’une PWA demande HTTPS, comme le micro | Même règle que la dictée : prod et dev en HTTPS |

Décisions à prendre (recommandation en premier) :

| # | Question | Options | Recommandation |
| --- | --- | --- | --- |
| D1 | D’où vient la géométrie de la vue du dessus ? | a) modèle génératif seul ; b) redressement géométrique à partir des parcelles connues, puis habillage génératif ; c) photogrammétrie serveur | **b**, avec **c** en bonus quand les prises le permettent ; **a** jamais seul |
| D2 | Quel fournisseur pour la transformation en plan ? | Black Forest Labs (FLUX.2), Google (Gemini image), OpenAI (gpt-image) | Choisir après un essai comparatif (US d’essai, comme US-298) ; critères : fidélité, hébergement, non-réutilisation des données, prix |
| D3 | Flouter avant l’envoi au fournisseur ? | oui / non | **Oui** : personnes, plaques, fenêtres de la maison |
| D4 | Combien de temps garder les photos brutes ? | jusqu’à validation / 7 jours / jamais | **Jusqu’à validation, 7 jours au plus** ; seul le plan stylisé reste |
| D5 | Quels niveaux produire ? | paysager seul / structurel seul / les deux | **Les deux** : le structurel sert de fond par défaut, le paysager en option |
| D6 | Validation par le jardinier ? | obligatoire / facultative | **Obligatoire** : comparaison côte à côte avant d’utiliser le plan |
| D7 | Sur quel appareil ? | tout mobile / capture mobile, pose ordinateur | **Capture et validation sur mobile, pose des parcelles sur ordinateur** (cohérent avec « pas de modification du plan sur mobile ») |
| D8 | Combien de générations ? | libre / plafond | **3 essais par session, 2 sessions par potager et par mois** (configurables) |

## 3. Vue d’ensemble

&#91;embedded content: pipeline · 11 étapes, 2 contrôles\]

Le jardinier capture et valide ; le serveur vérifie, floute et calcule l’esquisse qui fait foi ; le fournisseur d’image ne reçoit que des photos floutées et l’esquisse, et ne fait qu’habiller. À la validation, « Reprendre des photos » ramène à la prise guidée.

## 4. Logique détaillée des opérations

Onze étapes, de l’option choisie au plan posé. Les étapes 2 à 4 se jouent sur le téléphone ; les étapes 5 à 8 sur le serveur, en tâche de fond.

1. **Lancement.** Déclenché par « Fond du plan › Vue aérienne » dans Modifier le plan.
   - Prérequis : au moins deux parcelles avec longueur et largeur renseignées (elles donnent l’échelle). Sinon, la fonction propose de les compléter d’abord.
   - Plafond vérifié (D8) ; information RGPD courte et consentement explicite (case à cocher), écrits avec la session.
   - Depuis un ordinateur : QR code et lien « Continuer sur votre téléphone » ; la session est la même.
   - Sortie : une session au statut `capture`.
2. **Plan de capture.** L’application construit la liste des prises à partir des parcelles connues.
   - Vues d’ensemble : une depuis chaque côté accessible du terrain, appareil tenu le plus haut possible (bras levé, escabeau, fenêtre).
   - Par parcelle : une vue dans l’axe des rangs et une vue en biais montrant au moins deux coins.
   - Facultatif : une vue haute (étage) ; elle ouvre le chemin photogrammétrie (D1 c).
   - Une liste à cocher montre l’avancement, parcelle par parcelle.
3. **Prise de vue guidée.** Pour chaque prise :
   - Viseur avec repères : inclinaison conseillée vers le bas, « reculez pour voir les quatre coins ».
   - Capteurs lus : cap de la boussole, inclinaison, heure. La position GPS n’est pas lue.
   - Contrôle immédiat sur l’appareil : flou, exposition, résolution minimale, inclinaison hors plage. Échec : « à reprendre », la photo n’est pas envoyée.
   - Repères : sur une vue de parcelle, le jardinier touche les coins visibles de la parcelle désignée. C’est ce geste qui fournit la géométrie (D1 b).
   - Envoi dès la prise, après ré-encodage sur l’appareil (métadonnées EXIF supprimées).
4. **Évaluation de suffisance.** Recalculée à chaque envoi et sur « J’ai terminé ».
   - Couverture : chaque parcelle vue sur au moins deux photos, ses coins désignés sur au moins une.
   - Liaison : chaque photo partage assez de points communs avec une autre (appariement de points d’intérêt) ; le graphe des photos est d’un seul tenant.
   - Emprise : limites du terrain visibles sur au moins trois côtés (analyse par un modèle de vision).
   - Qualité : aucune photo floue retenue.
   - Sortie : « suffisant », ou la liste des manques en clair (« il manque une vue de la planche est montrant ses coins »). Le jardinier complète, puis la session repasse en `analyse`.
5. **Prétraitement RGPD.** Avant tout envoi à un fournisseur d’image :
   - Détection et floutage des personnes, visages, plaques d’immatriculation, fenêtres et intérieurs visibles (D3).
   - Réduction à une taille de travail (par exemple 2 048 px sur le grand côté).
   - Les originaux non floutés sont supprimés dès le floutage fait.
6. **Esquisse d’implantation à l’échelle.** Le calcul géométrique, sans modèle génératif :
   - Chaque parcelle dont les coins sont désignés est redressée en vue du dessus (homographie du plan du sol) à ses dimensions connues ; on en tire l’échelle en mètres par pixel.
   - Les positions relatives des parcelles et des limites sont déduites des vues d’ensemble (points communs et analyse de vision), puis composées en une esquisse : rectangles des parcelles, limites, zones non vues en gris.
   - Si une vue haute et un recouvrement suffisant existent, une orthophoto par photogrammétrie remplace l’esquisse (D1 c).
   - Sortie : l’esquisse, qui fait foi pour la géométrie.
7. **Composition de la vue du dessus.** Premier appel au fournisseur d’image.
   - Entrées : l’esquisse (contrainte géométrique) et les photos floutées (références d’apparence : allées, haies, arbres, serre).
   - Consigne : vue orthographique, implantation de l’esquisse respectée strictement, rien d’inventé, zones non vues laissées neutres.
   - Sortie : la vue aérienne reconstituée, intermédiaire, jamais conservée après la session.
8. **Transformation en plan paysager.** Deuxième appel, avec le prompt fourni, versionné dans un fichier (jamais en dur dans le code).
   - Niveau 2, paysager : végétaux en formes géométriques, palette pastel.
   - Niveau 1, structurel : dérivé du niveau 2 par un troisième appel (« retirer le végétal, garder murs, allées, terrasses, limites, carrés potagers »).
   - Sortie : deux images PNG à l’échelle de l’esquisse.
9. **Contrôle de fidélité automatique.**
   - Géométrique : les parcelles détectées sur le plan sont comparées à l’esquisse ; écart de position ou de taille au-delà d’un seuil (par exemple 5 % de la diagonale) : échec.
   - Sémantique : un modèle de vision compare plan et photos et signale tout élément présent sur le plan et absent des photos.
   - Échec : nouvel essai avec consigne renforcée, dans la limite de D8. Au-delà : l’esquisse seule est proposée comme fond structurel minimal.
10. **Validation par le jardinier** (D6), sur téléphone ou ordinateur.
    - Comparaison côte à côte avec curseur (esquisse ou photo d’ensemble ↔ plan), bascule niveau 1 / niveau 2.
    - « Signaler une erreur ici » : toucher une zone et dire ce qui est faux ; regénération de cette zone seulement, dans la limite de D8.
    - Choix : Valider, Reprendre des photos, Abandonner.
11. **Pose et clôture.**
    - Le plan validé devient le fond du potager : échelle, angle et emprise connus ; le nord vient du cap médian, confirmé sur la rose des vents.
    - Les parcelles sont déjà placées d’après l’esquisse : l’éditeur s’ouvre pour les ajuster (ordinateur).
    - Photos, esquisse et vue intermédiaire sont supprimées (D4). Restent les deux niveaux de plan, la date de prise et les paramètres de recalage.
    - « Refaire la vue aérienne » ouvre une nouvelle session ; l’ancien plan reste actif jusqu’à la validation du nouveau.

## 5. États de la session

&#91;embedded content: états de la session · 6 ouverts, 3 finaux\]

Le statut de `plan_fond_sessions` suit ce schéma. « Abandonner » est possible depuis tout état ouvert, pas seulement à la validation ; l’expiration aussi, 7 jours après le début de la session. Les trois états finaux déclenchent la purge des photos.

## 6. Architecture

Un service `app/services/plan_fond/` porte toute la logique ; les routes ne font que transmettre, et tout appel de modèle passe par `llm.passerelle` (mesure, journal, indisponibilité typée), comme pour la voix.

| Couche | Élément | Rôle |
| --- | --- | --- |
| PWA | `lib/captureVue.js` (+ tests `node --test`) | Logique pure : plan de capture, contrôles de qualité sur l’appareil, états de l’écran |
| PWA | `hooks/useCamera.js`, `hooks/useCapteurs.js` | Caméra (getUserMedia, repli sur la prise de photo du système), cap et inclinaison |
| PWA | `CaptureVueAerienne.jsx`, `ValidationPlanFond.jsx` | Parcours de capture, liste à cocher, désignation des coins ; comparaison et validation |
| API | `POST /plan/fond/sessions` ; `POST …/{id}/photos` ; `GET …/{id}` ; `POST …/{id}/terminer`, `/valider`, `/signaler`, `/abandonner` ; `GET /potagers/{id}/plan-fond` | Aucune logique : création, envoi d’une photo avec ses métadonnées et ses coins, état et manques, décisions, lecture du plan |
| Service | `capture.py`, `suffisance.py`, `rgpd.py`, `geometrie.py`, `generation.py`, `fidelite.py`, `cycle_vie.py` | Session et stockage temporaire ; critères de suffisance ; floutage ; homographies et esquisse ; appels d’image ; contrôles ; purge |
| Passerelle | types `vision` et `image` (variables `GROQ_MODEL_VISION`, `GROQ_MODEL_IMAGE`) | Analyse des photos ; édition d’image. Même mesure dans `conso_tokens`, même mode dégradé |
| Tâche de fond | file de tâches en table PostgreSQL + service systemd `potager-*-worker` | Les étapes 5 à 9 durent de quelques dizaines de secondes à quelques minutes : hors requête HTTP. Pas de nouvelle infrastructure |
| Stockage | répertoire temporaire chiffré avec date d’expiration ; plans validés en stockage de fichiers sauvegardé | Photos et intermédiaires : effacés par `cycle_vie.py` ; plans : conservés avec le potager |

Traitements candidats, à trancher par un essai (D2) :

| Traitement | Candidat | Remarque |
| --- | --- | --- |
| Analyse des photos (limites, parcelles, contrôle sémantique) | Mistral, modèle avec vision | Déjà sous-traitant ; photos reçues seulement après floutage |
| Floutage (personnes, plaques, fenêtres) | Détecteur exécuté sur le serveur | Doit tourner **avant** tout envoi à un tiers ; capacité du serveur actuel (CX23) à vérifier |
| Géométrie (homographie, points communs) | OpenCV, sur le serveur | Calcul déterministe, gratuit |
| Composition et transformation en plan | FLUX.2 (Black Forest Labs, Allemagne), Gemini 3.1 Flash image (Google), gpt-image-2 (OpenAI) | Jusqu’à 8, 14 et 16 images de référence ; de quelques centimes à environ 0,20 $ par image ([comparatif mai 2026](https://techstackups.com/comparisons/gemini-vs-openai-vs-flux-vs-runway-character-consistency-may-2026/), à vérifier auprès des fournisseurs) |
| Photogrammétrie (D1 c) | OpenDroneMap, exécuté à la demande | Gourmand en calcul : hors du serveur actuel ; à écarter en v1 |

## 7. Données et migrations

Quatre tables nouvelles, dont trois temporaires par nature ; seule `plans_fond` dure. Numéros après v72 (compagnon vocal), à recaler.

| Table | Champs principaux | Durée de vie |
| --- | --- | --- |
| `plan_fond_sessions` | `id`, `potager_id`, `user_id`, `statut`, `consentement_le`, `essais_restants`, `manques` (JSON), `erreur`, `cree_le`, `expire_le` | Jusqu’à validation ou abandon, 7 jours au plus ; seule une trace sans photo reste (statut, dates, coût) |
| `plan_fond_photos` | `id`, `session_id`, `role` (ensemble, parcelle, haute), `parcelle_id`, `cap_deg`, `inclinaison_deg`, `prise_le`, `coins` (JSON, en pixels), `qualite` (JSON), `chemin_temp`, `floutee`, `expire_le` | Supprimée avec son fichier à la clôture de la session |
| `plans_fond` | `id`, `potager_id`, `version`, `niveau` (structurel, paysager), `chemin`, `largeur_px`, `hauteur_px`, `m_par_px`, `angle_deg`, `nord_deg`, `emprise` (JSON), `date_prise`, `fournisseur`, `modele`, `prompt_version`, `actif`, `cree_le` | Tant que le potager existe ; supprimée avec lui |
| `taches` (file de travail) | `id`, `type`, `session_id`, `statut`, `tentatives`, `debut`, `fin`, `erreur` | Purgée après 30 jours |

- `parcelles` reçoit les champs de position du Plan (forme, x, y, longueur, largeur, rotation, sens des rangs) ; ils appartiennent à l’épic du Plan et sont remplis ici à l’étape 11.
- `conso_tokens` reçoit les types `vision` et `image` ; pour `image`, on compte les images produites et leur taille.
- Le prompt fourni est stocké dans `app/services/plan_fond/prompts/plan_paysager_v1.md` ; `prompt_version` dit avec quel prompt chaque plan a été produit.

## 8. RGPD : la solution unique

La transformation elle-même est la protection : on ne conserve qu’un plan géométrique pastel, sans visage, sans façade, sans plaque ni détail identifiant. Les photos ne servent que le temps de le produire.

- **Minimisation à la source** : pas de GPS lu ; métadonnées EXIF supprimées sur le téléphone, avant envoi.
- **Floutage avant tout tiers** : personnes, visages, plaques, fenêtres et intérieurs floutés sur notre serveur ; les originaux non floutés sont supprimés aussitôt.
- **Durée courte** : photos, esquisse et vue intermédiaire supprimées à la validation, et au plus tard 7 jours après le début de la session, validée ou non.
- **Seul le plan stylisé reste**, rattaché au potager ; il est supprimé avec le potager ou le compte.
- **Consentement et information** : une case à l’entrée de la fonction, qui dit quels sous-traitants reçoivent les photos floutées et pour combien de temps ; trace datée dans la session.
- **Sous-traitants** : Mistral AI (déjà inscrit) et le fournisseur d’édition d’image retenu. Pour ce dernier, à vérifier avant le choix : lieu d’hébergement, durée de conservation des requêtes, absence de réutilisation pour l’entraînement.
- **Registre** : nouveau traitement inscrit (finalité, données, durées, sous-traitants). Une analyse d’impact ne paraît pas requise (pas de traitement à grande échelle ni de données sensibles), à confirmer.

## 9. Coûts, limites, modes dégradés

Une session coûte entre 0,15 $ et 2 $ environ : 3 images produites par essai (composition, plan paysager, plan structurel), 1 à 3 essais, de 0,05 à 0,20 $ l’image selon le fournisseur et la taille, plus quelques centimes d’analyse de vision. Chiffres à recaler après l’essai D2.

Plafonds configurables : `PLAN_FOND_ESSAIS_SESSION` (3), `PLAN_FOND_SESSIONS_MOIS` (2 par potager), `PLAN_FOND_PHOTOS_MAX` (40 par session), `PLAN_FOND_RETENTION_JOURS` (7).

| Situation | Comportement |
| --- | --- |
| Caméra refusée ou absente | Import de photos déjà prises depuis la galerie ; même contrôle de qualité, sans cap |
| Capteurs refusés (iOS) | Capture sans cap ; le nord se fixe sur la rose des vents à l’étape 11 |
| Réseau coupé pendant la capture | Photos gardées sur le téléphone, envoyées au retour du réseau, puis effacées de l’appareil |
| Captures insuffisantes | Liste des manques en clair ; pas de lancement du traitement |
| Fournisseur d’image indisponible | Session « en attente », 3 reprises automatiques espacées ; ensuite, l’esquisse seule est proposée |
| Contrôle de fidélité en échec au dernier essai | L’esquisse seule est proposée comme fond structurel minimal |
| Plafond atteint | « Nouvelle vue aérienne possible le … » ; le fond actuel reste |
| Session expirée (7 jours) | Photos purgées ; « Votre capture a expiré, recommencez quand vous voulez » |
| Aucun fond validé | Le Plan reste en « Fond masqué » (grille, piste A) |

## 10. Découpage et points à valider

Onze US, 55 points, à livrer dans l’ordre du tableau ; l’essai des fournisseurs ouvre la marche, comme US-298 pour la voix. Numéros d’épic et d’US à recaler.

| US | Titre | Dépend de | Points |
| --- | --- | --- | --- |
| US-306 | Essayer trois fournisseurs d’image sur trois potagers réels (D2) | — | 3 |
| US-307 | Vision et édition d’image dans la passerelle | US-306 | 5 |
| US-308 | Session de capture, stockage temporaire, file de tâches et purge | US-307 | 5 |
| US-309 | Capturer son potager pas à pas (caméra, capteurs, qualité, coins) | US-308 | 8 |
| US-310 | Savoir si les captures suffisent, et ce qui manque | US-309 | 5 |
| US-311 | Flouter avant tout envoi à un tiers | US-308 | 3 |
| US-312 | Esquisse d’implantation à l’échelle | US-310 | 8 |
| US-313 | Composer la vue du dessus et produire les deux niveaux de plan | US-311, US-312 | 5 |
| US-314 | Contrôler la fidélité du plan | US-313 | 5 |
| US-315 | Valider et corriger le plan | US-314 | 5 |
| US-316 | Retrouver ses parcelles posées sur le plan validé | US-315 ; éditeur du Plan | 3 |

US-309, US-310 et US-315 ont un rendu à l’écran : maquettes à produire avant leur développement.

Points à valider :

- [ ] D1 : géométrie par redressement des parcelles connues, modèle génératif pour l’habillage seulement
- [ ] D2 : fournisseur d’édition d’image, après l’essai US-306
- [ ] D3 à D5 : floutage, conservation 7 jours au plus, deux niveaux de plan
- [ ] D6 et D7 : validation obligatoire ; capture sur mobile, pose sur ordinateur
- [ ] D8 : plafonds par session et par mois
- [ ] Capacité du serveur actuel pour le floutage et la géométrie, ou machine de calcul à la demande
- [ ] Texte d’information RGPD et inscription au registre

## Sources

- [OpenDroneMap, conseils de prise de vue](https://docs.opendronemap.org/flying) : recouvrement et angles pour une orthophoto
- [Mistral, génération d’images (outil d’agent)](https://docs.mistral.ai/agents/connectors/image_generation)
- [Comparatif Gemini, OpenAI, FLUX, Runway, mai 2026](https://techstackups.com/comparisons/gemini-vs-openai-vs-flux-vs-runway-character-consistency-may-2026/) : modèles, nombre d’images de référence, prix indicatifs (à confirmer auprès des fournisseurs)
- Prompt de transformation fourni par le jardinier (pièce jointe du 12/11/2026)
