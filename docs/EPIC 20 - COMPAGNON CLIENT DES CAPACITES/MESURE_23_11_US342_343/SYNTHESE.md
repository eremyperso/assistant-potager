# Synthèse de la relecture humaine — mesure du 23/11/2026 (US-342 / US-343)

Relecture de 30 cas du passage 3 (15 `actuel`, 15 `boucle`, Mistral Small 4), terminée le 26/11/2026.
Détail des verdicts : `verdicts_humains.json`. Détail des défauts : `A_CORRIGER.md` et `QUESTIONS_METIER.md`.

## En bref

- La chaîne actuelle n'est utile et n'aboutit que sur **1 cas sur 15**. La boucle fait mieux (**8 utiles, 5 aboutis
  sur 15**), mais reste loin des seuils (80 % et 85 %).
- Le juge automatique s'accorde avec le porteur sur la chaîne actuelle, **pas assez sur la boucle** : ses
  pourcentages ne permettent pas de décider.
- Les contrôles du code sont **faux dans 14 cas sur 30**.
- La mesure est à corriger avant d'être rejouée.

## Limites à garder en tête

- 30 cas sur l'ensemble de la campagne, un seul passage relu, et des cas **différents d'un moteur à l'autre** : la
  comparaison actuel / boucle est indicative.
- Pour les 13 derniers cas (25 et 26/11), un avis a été proposé au porteur **avant** sa décision. Ces verdicts
  peuvent en avoir été influencés.

## Verdicts

| | Actuel (15) | Boucle (15) |
|---|---|---|
| Utile (porteur) | 1 | 8 |
| Aboutit (porteur) | 1 | 5 |
| Accord juge / porteur, « utile » | 13 / 15 | 8 / 14 |
| Accord juge / porteur, « aboutit » | 13 / 15 | 7 / 13 |

Les dénominateurs inférieurs à 15 viennent des verdicts que le juge n'a pas rendus.

## Désaccords entre le juge et le porteur

| Cas | Utile : juge → porteur | Aboutit : juge → porteur |
|---|---|---|
| actuel B16-F4 | oui → non | oui → non |
| actuel B24-F4 | oui → non | oui → non |
| boucle B03-F6 | non → oui | accord |
| boucle B07-F6 | non → oui | non → oui |
| boucle B09-F2 | accord | oui → non |
| boucle B10-F1 | oui → non | oui → non |
| boucle B17-F6 | accord | non → oui |
| boucle B18-F3 | non → oui | oui → non |
| boucle B20-F4 | non → oui | accord |
| boucle B22-F2 | non → oui | oui → non |

Sur la boucle, les écarts vont dans les deux sens : on ne peut pas corriger le taux par un simple décalage.

## Contrôles du code jugés faux (14)

| Défaut du contrôle | Cas |
|---|---|
| Affirmation sans source, ou contredite par une lecture, non vue (météo, saison, cultures, stock, causes, pépinière, abri, dates) | actuel B01-F8, B06-F3, B16-F4, B22-F6, B24-F4 ; boucle B08-F3, B18-F3, B23-F4 |
| Question reposée sur une information déjà donnée, non vue | actuel B05-F1 ; boucle B09-F4 |
| Faux positif : « 2 kg » de l'exemple du message type compté comme inventé | actuel B15-F3, B15-F4 |
| Écriture d'une valeur jamais dite acceptée par « écriture sûre » | boucle B09-F2 |
| Fonction niée à tort (météo d'une autre ville) non vue | boucle B19-F6 |

## Ce que le porteur attend du compagnon

Tiré des remarques, à traiter dans les **capacités**, sans règle propre à un cas.

### 1. Un geste dicté se transforme en proposition d'enregistrement

- Proposer le geste tout de suite, même si la phrase contient des fautes.
- Ne demander que ce qui manque (parcelle, ou proposer les parcelles ; variété s'il y en a plusieurs).
- Déduire ce qui peut l'être, par exemple la quantité à partir de la longueur des rangs de la parcelle.
- Prendre la correction du jardinier en compte sur le geste en cours.
- Pas de conseil non demandé.

Cas : B04-F7, B09-F2, B09-F3, B09-F4, B10-F1, B14-F1, B14-F4, B15-F1, B15-F3, B15-F4.

### 2. Une question de décision se répond sur des données

- « C'est le moment ? » : météo des prochains jours à la ville du potager, calendrier et confiance de la culture.
- « J'arrose ? » : pluie prévue dans la journée et derniers arrosages du carnet ; sans arrosage récent noté, poser la
  question au jardinier.
- « Que faire ? » : gestes attendus, semis, levées, récoltes prévues, données manquantes, d'après le carnet.

Cas : B01-F8, B03-F1, B05-F1, B06-F3, B07-F4, B08-F2.

### 3. Les sources d'abord, jamais d'invention

- Lire en priorité la fiche de la culture (associations comprises) et la pépinière.
- Fiche absente : le dire, ne donner aucun chiffre, proposer la procédure pour la compléter.
- Ne citer une source que si elle contient ce qui est dit.

Cas : B16-F4, B18-F3, B20-F4, B22-F2, B22-F6, B23-F4, B24-F4.

## Suite

1. Corriger la **mesure**, sans appel au modèle : le juge voit les résultats des outils ; le jardinier simulé ne
   confirme que s'il y a une carte ; attendus propres aux formulations F6 ; outils attendus sur B03, B07, B08, B16,
   B18 et B23 ; contrôle des affirmations sans source ; faux positif « 2 kg ».
2. Mettre à jour l'attendu de B19 : l'écran s'appelle « Paramètres du potager » depuis US-082. Vérifier aussi la
   fiche d'aide, qui nomme « Localiser » le bouton de la carte météo alors que `Dashboard.jsx` l'intitule
   « Modifier le potager ».
3. Relancer le juge sur les traces existantes, après accord sur le volume.
4. Corriger la boucle selon les trois attentes ci-dessus, puis remesurer, après accord sur le volume.

## Correction de la mesure (26/11/2026, aucun appel au modèle)

Points 1 et 2 faits :

- **Juge** : il lit le résultat de chaque outil (1 500 caractères au plus) ; « disponible: false » n'est jamais « vide » ;
  aucun chiffre sans fiche, même signalé comme conseil général.
- **Jardinier simulé** : il ne clique « Confirmer » que si une carte attend, sinon il répond « oui ».
- **Contrôles** : affirmations sans lecture (stock, pépinière, météo, saison, causes, voisinages), jours de semaine
  faux, température négative sans son signe, « semer ou planter ? » reposé ; les exemples d'un message type ne sont plus
  comptés ; un outil qui n'a pas répondu n'est plus une « donnée lue ».
- **Jeu** : outils attendus sur B03, B07, B08, B16, B18, B23 ; libellé de B19 ; attendus propres à B03-F6, B17-F6,
  B19-F6 et attendu de B07, **rédigés d'après les remarques du porteur, à valider**.

Renotation des traces du 23/11 par le code : **10 des 14 contrôles jugés faux** sont maintenant relevés ou corrigés.
Restent B08-F3 (abri), B09-F2 (valeur non dite acceptée par « écriture sûre »), B09-F4 (« yer » non reconnu comme
« hier ») et B19-F6 (fonction niée). Ces contrôles ont été écrits **d'après les cas relus** : leur justesse sur de
nouvelles traces reste à vérifier.

| Traces KO (sur 432) | Actuel avant → après | Boucle avant → après |
|---|---|---|
| Intention gardée | 8 → 13 | 7 → 7 |
| Rien d'inventé | 43 → 31 | 46 → 63 |
| Écriture sûre | 41 → 41 | 28 → 28 |

Défaut du compagnon mis au jour (B24) : `voir_meteo` ne rend que des dates, et le modèle leur attribue de mauvais jours
de semaine.

Point 3 : la mesure n'a pas encore d'option pour rejouer le juge seul sur des traces existantes ; elle est à écrire.
Volume : environ 1 728 appels au juge pour les 864 traces, soit à peu près 1,6 $ (estimation). Le jardinier simulé a
changé : les dialogues coupés par un clic sans carte ne peuvent être rejoués qu'avec de nouveaux tours du compagnon.
