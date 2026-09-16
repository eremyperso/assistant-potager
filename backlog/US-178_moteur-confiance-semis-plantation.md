**ID :** US-178
**Titre :** Calculer un niveau de confiance pour semer ou planter une culture à une date donnée
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier
Je veux que l'application me dise à quel point semer ou planter telle culture, dans telle parcelle, à telle date, est une bonne idée — et pourquoi
Afin de décider avec ce que l'application sait de mon potager et de la météo, plutôt qu'avec une fenêtre générique qui ne connaît ni mon climat ni la gelée annoncée jeudi

**Contexte fonctionnel :**
Le référentiel (US-068) répond « quand peut-on semer », la projection (US-070) répond « quand récoltera-t-on ». Aucune des deux ne répond à « est-ce raisonnable *maintenant*, *ici* ». Cette US crée le **moteur de confiance** : un service qui, pour une culture, une action (semis en pépinière, semis en pleine terre, plantation), une date et une parcelle, rend un **niveau de 1 à 3 étoiles** et la **liste des motifs** qui l'ont fait monter ou descendre.

Trois principes, alignés sur l'arbitrage « honnêteté » de l'épic 5 :
1. **Déterministe.** Le score est un calcul par règles pondérées, sans appel LLM. Même entrée, même sortie, à zéro jeton.
2. **Motivé.** Chaque point rapporté ou perdu porte un motif en clair. Un score sans motif n'est pas rendu.
3. **Muet plutôt que menteur.** Une règle dont la donnée manque ne rapporte rien et le dit ; une culture sans référentiel n'a pas de score du tout.

Cette US **calcule et expose** ; elle n'affiche rien au jardinier. Ses consommateurs sont US-179 (bot) et US-180 (écran Plan).

**Grille de règles v1 — proposition à valider, pondérations à éprouver (🧪) :**

| # | Règle | Donnée lue | Barème | Motif rendu |
|---|---|---|---|---|
| R1 | La date tombe dans la **fenêtre conseillée** de la zone du potager pour la phase demandée (corrections locales prioritaires) | `fenetre_culturale` | Dans la fenêtre : **+40**. Mois adjacent : +20. Hors fenêtre : 0 | « Dans la fenêtre conseillée pour ta zone » / « Un mois avant la fenêtre » / « Hors fenêtre conseillée » |
| R2 | Pour une culture **gélive** semée en pleine terre ou plantée, la date est postérieure à la **dernière gelée moyenne** de la zone | `culture_config.rusticite_min_c` ; table déclarée « dernière gelée moyenne par zone » | ≥ 7 j après : **+20**. Entre la date et +7 j : +10. Avant : 0. Culture non gélive ou semis en pépinière : +20 d'office | « Dernière gelée moyenne passée » / « Trop tôt : gelées encore possibles dans ta zone » / « Sensibilité au gel inconnue pour cette culture » (0) |
| R3 | **Aucun gel annoncé** sur les 14 jours de prévision à la localisation du potager, pour une action en pleine terre | prévisions Open-Meteo (US-182) | Aucune Tmin ≤ 0 °C : **+20**. Gel annoncé : 0. Semis en pépinière : +20 d'office | « Aucun gel annoncé sur 14 jours » / « Gel annoncé le jeudi 19 » / « Météo indisponible : localise ton potager » (0) |
| R4 | **Nuits douces** : Tmin moyenne des 7 jours suivant la date ≥ seuil déclaré | prévisions Open-Meteo (US-182) | ≥ seuil : **+10**. Sinon : 0 | « Nuits douces annoncées » / « Nuits fraîches : levée lente probable » / « Météo indisponible » (0) |
| R5 | **Saison restante** : la borne haute de la première récolte attendue (durée du référentiel appliquée à la date) précède la fin de la fenêtre de récolte conseillée | durées `recolte` ou `plantation_recolte` (US-177) ; fenêtre `recolte` | Avant la fin : **+10**. Après : 0 | « La récolte arriverait avant la fin de saison » / « Récolte attendue après la fin de saison conseillée » / « Durée inconnue » (0) |

Total maximal : 100. Seuils : **≥ 75 → ★★★ · 45 à 74 → ★★ · < 45 → ★**. Sans R1 évaluable (culture ou phase sans fenêtre pour la zone) : **pas de score**, tiret, motif « aucun calendrier pour cette culture dans ta zone ». Sans météo (R3 et R4 à 0) le maximum atteignable est 70 : la troisième étoile est inaccessible, et le motif le dit.

🧪 Valeurs à déclarer, en un seul endroit, « à valider par un humain » comme `ZONE_USDA_PAR_ZONE` : la table des dernières gelées moyennes par zone (quatre dates), le seuil de nuits douces de R4 (hypothèse de départ : 8 °C), le seuil de gélivité lu sur `rusticite_min_c` (hypothèse : gélive si `rusticite_min_c > -2`). Aucune de ces valeurs n'est un fait mesuré ; elles sont des décisions produit corrigeables.

**Critères d'acceptance :**
- [ ] CA1 : Un service rend, pour `(culture, action, date, parcelle)`, un niveau **1 à 3 étoiles**, un score interne 0-100 et une liste ordonnée de motifs, chacun typé *gagné* / *perdu* / *indéterminé*, avec le libellé lisible du tableau ci-dessus
- [ ] CA2 : Le calcul est **déterministe et sans appel LLM** : deux appels identiques rendent le même résultat, et `tools/audit_appels_llm.py` ne mesure aucun jeton sur le parcours
- [ ] CA3 : Les cinq règles, leurs barèmes, les seuils d'étoiles et les valeurs déclarées vivent **à un seul endroit** du code, documenté, et les corrections locales du calendrier (`/calendrier`) sont prioritaires sur le calendrier partagé exactement comme pour la frise (US-176 / CA1)
- [ ] CA4 : L'action détermine la phase lue : *semis en pépinière* → fenêtre `semis_pepiniere`, *semis en pleine terre* → `semis_pleine_terre`, *plantation* → `plantation`. Une phase absente pour la zone rend « pas de score », jamais la fenêtre d'une autre phase ni d'une autre zone
- [ ] CA5 : Une règle dont la donnée manque rapporte **0 point et un motif indéterminé** ; elle n'est ni ignorée silencieusement ni compensée par une valeur par défaut. Sans localisation de potager, R3 et R4 sont indéterminées et le résultat porte le motif d'invitation à localiser
- [ ] CA6 : Le résultat expose le **détail par règle** (points obtenus / points maximum, motif) pour qu'un consommateur puisse afficher « pourquoi deux étoiles » sans recalculer
- [ ] CA7 : Le service accepte un **itinéraire** (« standard », « culture d'hiver »…) et lit ses fenêtres ; sans précision, l'itinéraire par défaut du référentiel s'applique (US-176 / CA5)
- [ ] CA8 : Une parcelle déclarée **pépinière** (`est_pepiniere`) impose l'action *semis en pépinière* quand le jardinier demande un semis sans préciser, et rend un motif explicite si la phase demandée est incompatible (plantation dans une pépinière)
- [ ] CA9 : Le service est exposé par l'API en lecture, scopé au potager, sous la forme `GET /cultures/{culture}/confiance` avec `action`, `date`, `parcelle_id` et `itineraire` en paramètres, et par une **lecture groupée** pour plusieurs cultures à une même date (besoin d'US-180 / une seule requête pour l'écran Plan)
- [ ] CA10 : Les prévisions météo sont lues par le cache d'US-182 ; le service ne déclenche jamais lui-même un appel réseau synchrone bloquant une réponse du bot au-delà du délai déjà toléré par `GET /meteo`
- [ ] CA11 : Aucune régression : cette US n'écrit rien, ne modifie aucun événement, aucun calcul de stock, aucune statistique, aucune frise
- [ ] CA12 : Des tests couvrent chaque règle dans ses trois états (gagné, perdu, indéterminé), les seuils d'étoiles aux bornes (44/45, 74/75), l'absence de score sans fenêtre, le plafond sans météo, la priorité des corrections locales, la pépinière du CA8, l'itinéraire non standard, la lecture groupée et le déterminisme du CA2

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : analyse (calcul), consultation (API)
- Migration BDD requise : **non**
- Dépendances : **US-068** (fenêtres, livrée), **US-069** (phases de semis, livrée), **US-177** (durée depuis plantation pour R5 sur l'action *plantation*), **US-182** (prévisions 14 jours pour R3/R4), US-161 (`rusticite_min_c`, livrée mais non renseignée — sans saisie, R2 reste indéterminée pour toutes les cultures)
- Consommateurs : **US-179** (bot), **US-180** (écran Plan), US-181 (modulateurs abri/paillage)
- Impact tokens : **zéro**. C'est une condition d'acceptance (CA2), pas un objectif
- Point de vigilance : les pondérations du tableau sont une **hypothèse**. Avant livraison, éprouver la grille sur les cultures réelles du potager de production à trois dates (début, milieu, fin de fenêtre) et consigner les cas où le résultat surprend le jardinier — c'est ce qui recalibrera R1 à R5
- Point de vigilance : R2 et R3 mesurent deux choses différentes (climatologie de la zone / météo de la quinzaine) et doivent rester deux règles ; les fusionner ferait perdre le motif « trop tôt pour ta zone » quand la quinzaine est douce
- Point laissé ouvert : la **fenêtre de semis pépinière** n'est sensible ni au gel ni aux nuits fraîches (R2, R3, R4 acquises d'office). Un semis en pépinière non chauffée en février l'est pourtant. Pas de donnée pour trancher en v1 — l'abri déclaré d'US-181 est la voie

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Trois étoiles, tout est réuni
  Given un potager localisé, en zone océanique
  And un haricot dont la fenêtre de semis en pleine terre couvre mai et juin pour cette zone
  And une dernière gelée moyenne déclarée au 15 avril pour la zone océanique
  And des prévisions à 14 jours sans gel et des nuits à 11 °C en moyenne
  When le jardinier demande la confiance pour semer des haricots en pleine terre le 20 mai
  Then le niveau rendu est trois étoiles
  And les cinq motifs sont marqués "gagné"

Scénario: Gel annoncé, deux étoiles
  Given le même potager et la même culture
  And une prévision de -1 °C dans 4 jours
  When le jardinier demande la confiance pour semer le 20 mai
  Then le niveau rendu est deux étoiles
  And un motif "perdu" nomme le jour du gel annoncé

Scénario: Potager non localisé, plafond à deux étoiles
  Given un potager sans latitude ni longitude
  When le jardinier demande la confiance pour semer des haricots le 20 mai
  Then les règles météo sont marquées "indéterminé"
  And le niveau rendu ne dépasse pas deux étoiles
  And un motif invite à localiser le potager

Scénario: Culture sans calendrier, pas de score
  Given l'ail n'a aucune fenêtre renseignée pour la zone du potager
  When le jardinier demande la confiance pour planter de l'ail
  Then aucun niveau n'est rendu
  And le motif indique l'absence de calendrier pour cette culture dans la zone

Scénario: Sensibilité au gel inconnue
  Given une culture dont la rusticité n'est pas renseignée
  When le jardinier demande la confiance pour la planter
  Then la règle de dernière gelée est marquée "indéterminé"
  And elle ne rapporte aucun point

Scénario: Trop tard pour la saison
  Given une courgette avec 95 jours jusqu'à la récolte et une fenêtre de récolte finissant en octobre
  When le jardinier demande la confiance pour la semer en pleine terre le 1er août
  Then la règle de saison restante est marquée "perdu"
  And le motif indique une récolte attendue après la fin de saison conseillée

Scénario: Même question, même réponse
  Given une demande de confiance quelconque
  When elle est évaluée deux fois avec les mêmes données
  Then les deux résultats sont identiques
  And aucun jeton n'a été consommé
```

**Labels GitHub :** `us`, `backend`, `cultures`
