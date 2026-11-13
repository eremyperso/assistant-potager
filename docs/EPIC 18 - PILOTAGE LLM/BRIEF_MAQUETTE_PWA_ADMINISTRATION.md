# Brief de maquette — PWA d'administration « Pilotage »

*Brief pour Claude Design, US-318. Deux écrans à produire, chacun en trois largeurs.*

## 1. Ce qu'est cette application

Assistant Potager est un carnet de potager pour jardiniers amateurs : un bot Telegram
et une application web où le jardinier dicte ses gestes et pose ses questions à un
assistant. Chaque réponse de l'assistant coûte des appels à un modèle de langage.

L'application à maquetter n'est **pas** celle du jardinier. C'est un outil d'exploitation,
réservé à l'administrateur de la plateforme, installable sur téléphone. Il y regarde ce que
l'assistant consomme, ce que cela coûte, si le service tient, et ce qui dérive d'une version
à l'autre. Il l'ouvre quelques minutes, souvent sur son téléphone, le plus souvent après
avoir reçu une alerte ou après une livraison.

## 2. Ce qui est attendu

| Écran | Largeurs | Thèmes |
|---|---|---|
| A. Coquille + vue **Consommation** | 375px, 768px, 1280px | clair et sombre |
| B. Vue **Seuils** | 375px, 768px, 1280px | clair (sombre si le temps le permet) |

Les quatre autres vues (Coût, Fiabilité, Dérives, Potagers et jardiniers) ne sont pas à maquetter : elles
réutiliseront les composants de l'écran A. Ces composants doivent donc être réguliers et
nommés.

## 3. Contraintes

- **Identité existante.** Reprendre les couleurs, la typographie et les espacements de
  l'identité visuelle d'Assistant Potager (dossier `docs/identite-visuelle`, à joindre).
  Pas de nouvelle marque. Le ton peut être plus sobre et plus dense que l'application du
  jardinier : c'est un outil de travail.
- **Mobile d'abord.** À 375px, tout doit rester lisible sans défilement horizontal. Un
  tableau trop large se transforme en liste de cartes ou ne garde que ses colonnes
  essentielles.
- **Le chiffre avant le graphique.** L'administrateur doit lire l'essentiel dans le
  bandeau de chiffres clés, sans interpréter une courbe.
- **Jamais la couleur seule.** Un écart défavorable, une alerte ouverte ou un seuil
  inactif se lisent aussi par un libellé ou une icône.
- **Séries distinguables** en thème clair, en thème sombre et pour une vision des couleurs
  altérée. Au plus six séries affichées ; au-delà, regroupement « autres ».
- **Chiffres français** : espace comme séparateur de milliers, virgule décimale, euro
  après le montant (« 1 204 », « 68,4 % », « 0,042 € »).
- Tout le texte est en français.

## 4. Écran A — Coquille et vue Consommation

### 4.1 Coquille (commune à toutes les vues)

- Nom de l'application : « Pilotage ». Mention de l'environnement (dev ou prod).
- Navigation entre six vues : **Consommation**, **Coût**, **Fiabilité**, **Dérives**,
  **Potagers**, **Seuils**. Barre en bas sur téléphone, latérale ou en haut sur bureau.
- Sélecteur de période : Aujourd'hui, 7 jours, 30 jours, 90 jours, Personnalisée.
- Filtres : provenance, canal, modèle. Repliés sur téléphone, avec le nombre de filtres actifs.
- Heure de dernière mise à jour (« mis à jour à 14 h 32 ») et bouton de rafraîchissement.
- Pastille sur l'entrée « Seuils » quand une alerte est ouverte.

### 4.2 Contenu de la vue Consommation, de haut en bas

1. **Rappel de périmètre** (discret, toujours visible) : « Usage réel uniquement — mesures
   et tests masqués », avec un lien « Afficher ».
2. **Bandeau de cinq chiffres clés**, chacun avec son écart à la période précédente :
   appels, jetons d'entrée, jetons de sortie, taux de cache, jetons d'entrée médians par appel.
3. **Graphique par jour** : jetons d'entrée, la part servie par le cache étant distinguée.
   Un sélecteur ventile la série par modèle, type d'appel ou canal. Sur « Aujourd'hui », le
   pas est l'heure.
4. **Tableau par type d'appel** : appels, jetons d'entrée, jetons de sortie, part du total,
   jetons d'entrée médians par appel.
5. **Tableau par modèle** : mêmes colonnes.
6. **Bloc audio**, séparé : secondes de dictée, caractères de synthèse vocale. Ce ne sont
   pas des jetons et ils ne s'additionnent pas au reste.

### 4.3 États à montrer

- **Données présentes** (état principal, données du §6).
- **Journée sans appel** : chiffres à zéro, graphique vide avec un message, pas d'erreur.
- **API indisponible** : dernières valeurs connues, grisées, avec « données de 14 h 32 ».

## 5. Écran B — Vue Seuils

L'administrateur y règle ce qui déclenche une alerte par Telegram et par e-mail.

1. **Alertes ouvertes**, en tête : indicateur, valeur mesurée, seuil, depuis quand, lien
   vers la vue concernée. Bloc absent quand il n'y en a aucune (montrer les deux cas).
2. **Liste des seuils**. Pour chacun : indicateur surveillé, règle lisible en une phrase
   (« plus de 20 % au-dessus de la moyenne des 7 derniers jours »), gravité, interrupteur
   actif / inactif, état courant (dans la norme, franchi, pas assez de données).
3. **Modification d'un seuil** : valeur, type de comparaison (valeur fixe ou écart à la
   moyenne des 7 jours), fenêtre, gravité. Panneau latéral sur bureau, feuille montante
   sur téléphone.
4. **Envois périodiques** : deux interrupteurs, « résumé quotidien (Telegram) » et
   « bilan hebdomadaire (e-mail) ».
5. **Historique** des dernières alertes : date, indicateur, valeur, durée, canaux notifiés.

Seuils à faire figurer dans la liste :

| Indicateur | Règle | Gravité | État |
|---|---|---|---|
| Jetons d'entrée médians par appel de l'agent | plus de 20 % au-dessus des 7 derniers jours | haute | **franchi** (8 900, +48 %) |
| Taux de quota atteint | plus de 5 % sur 1 heure | haute | dans la norme (0,8 %) |
| Taux d'erreur | plus de 3 % sur 1 heure | moyenne | dans la norme (1,2 %) |
| Latence P95 de l'agent | plus de 3 000 ms sur 1 heure | moyenne | dans la norme (1 480 ms) |
| Coût du jour | plus de 0,50 € | moyenne | inactif |
| Nombre d'appels par échange | médiane supérieure à 4 | basse | pas assez de données |

## 6. Données d'exemple pour l'écran A

Données **illustratives**, à l'échelle de l'usage actuel (quelques jardiniers). Elles
servent à remplir la maquette, pas à décrire la production.

Période : 7 jours. Rappel affiché : usage réel uniquement.

| Chiffre clé | Valeur | Écart |
|---|---:|---|
| Appels | 412 | +12 % |
| Jetons d'entrée | 2,31 M | +38 % (défavorable) |
| Jetons de sortie | 14 820 | +9 % |
| Taux de cache | 58 % | −4 points (défavorable) |
| Jetons d'entrée médians par appel | 8 140 | +31 % (défavorable) |

Série par jour (jetons d'entrée, dont cache) :

| Jour | Appels | Jetons d'entrée | dont cache |
|---|---:|---:|---:|
| lundi | 38 | 198 000 | 121 000 |
| mardi | 96 | 512 000 | 318 000 |
| mercredi | 71 | 402 000 | 229 000 |
| jeudi | 104 | 615 000 | 344 000 |
| vendredi | 44 | 261 000 | 148 000 |
| samedi | 0 | 0 | 0 |
| dimanche | 59 | 322 000 | 180 000 |

Par type d'appel :

| Type | Appels | Jetons d'entrée | Jetons de sortie | Part | Médiane par appel |
|---|---:|---:|---:|---:|---:|
| agent | 268 | 2 180 000 | 9 100 | 94,4 % | 8 140 |
| question | 52 | 41 000 | 3 300 | 1,8 % | 525 |
| parsing | 21 | 72 000 | 2 100 | 3,1 % | 3 494 |
| classification | 18 | 8 700 | 220 | 0,4 % | 480 |
| analyse | 9 | 21 000 | 2 400 | 0,9 % | 2 353 |
| compagnon_signal | 6 | 2 400 | 260 | 0,1 % | 414 |

Par modèle : `mistral/mistral-small-2603` (283 appels, 2,20 M), `mistral/ministral-8b-latest`
(97 appels, 0,12 M), autres (32 appels).

Bloc audio : 38 dictées, 214 secondes ; 22 lectures à voix haute, 2 860 caractères.

Séries du graphique en ventilation par canal : `pwa`, `telegram`, `mcp`, `fond`.

## 7. Vocabulaire

| Terme | Sens |
|---|---|
| Appel | Une requête à un modèle de langage |
| Jeton | Unité de texte facturée par le fournisseur (entrée : ce qu'on envoie ; sortie : ce qu'il répond) |
| Cache | Part des jetons d'entrée déjà connue du fournisseur, facturée moins cher |
| Type d'appel | Rôle de l'appel : `agent` (le compagnon qui répond), `question`, `parsing`, `classification`, `analyse`, `dictee`, `voix`… |
| Provenance | `usage` (un jardinier), `fond` (tâche automatique), `mesure` (banc d'essai), `test` |
| Canal | Par où la demande est arrivée : `telegram`, `pwa`, `mcp` |
| Échange | Une demande du jardinier et sa réponse ; il regroupe plusieurs appels |
| P95 | Valeur sous laquelle se trouvent 95 % des mesures |

## 8. Livrable

Pour chaque écran et chaque largeur : la maquette, et une planche des composants communs
nommés (navigation, sélecteur de période, filtres, chiffre clé avec écart, graphique en
série, tableau de ventilation, rappel de périmètre, état vide, état « données anciennes »,
ligne de seuil, panneau de modification). Signaler tout jeton de couleur ou d'espacement
ajouté à l'identité existante.
