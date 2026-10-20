**ID :** INC-012
**Titre :** Impossible de corriger le nombre de plants d'une mise en godet : la correction écrit dans « quantité » et laisse nb_plants_godets inchangé
**Type :** Incident
**Priorité :** Majeur

**Signalé le :** 2026-10-09

**Reproduction (jeu de test réalisé) :**
Potager 26, bot Telegram, parcours « corriger ». La mise en godet n° 496 (tomate cœur de bœuf, « mise en pot 10 tomate le 15/04 ») porte 10 plants en godet.
1. « corriger », puis « mise en godet tomate le 15/04 » : l'événement 496 est trouvé.
2. « quantité 5 », puis, après plusieurs « ✏️ Modifier autre chose » : « modifier 5 plants », « nombre de plant godet 5 », « nb_plants_godets = 5 ».
3. « ✅ Confirmer ».

**Résultat obtenu :**
Chaque formulation est analysée en `CORRECTIONS : {'quantite': 5}`, jamais en nombre de plants en godet. La trace dit « quantité: — → 5 » et l'événement #496 est enregistré avec `quantite = 5.0`, alors que `nb_plants_godets` reste à 10 (export de la base joint : ligne 496, quantite 5.0, nb_graines_semees 10, nb_plants_godets 10). Le récapitulatif du bot affiche pourtant la mise en godet avec 5. Aucun message ne dit que le nombre de plants n'a pas changé. Les stocks et la lecture par lot (qui lisent `nb_plants_godets`) restent donc inchangés.

**Résultat attendu (ou : ce qui ne devrait pas se produire) :**
Corriger « 5 plants » sur une mise en godet modifie le nombre de plants repiqués (`nb_plants_godets`), et si besoin le nombre de graines d'origine (`nb_graines_semees`). La valeur corrigée est celle que lisent le stock et le lot. Le champ `quantite`, qui n'est pas celui d'une mise en godet, ne doit pas être le seul modifié sans que le jardinier le sache.

**Analyse grosse maille (premier niveau — pas un diagnostic) :**
- Zone(s) impactée(s) : Bot Telegram (parcours de correction), API/Backend (service de correction d'événement).
- Nature probable : régression logique — le parcours de correction semble ne connaître ni `nb_plants_godets` ni `nb_graines_semees` ; à investiguer.
- Fichiers probablement concernés : `app/bot/correction.py` (consigne d'analyse des corrections et table des champs corrigeables), `app/services/evenements.py` (`corriger_evenement`).
- Corpus de connaissance concerné : oui — à relire si la correction évolue : `data/connaissance/doc_app/enregistrer-un-geste.md` et `semis-godet-plantation.md`.

**Labels :** incident, bot, backend, pepiniere
