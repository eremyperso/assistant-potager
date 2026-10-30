**ID :** US-279
**Titre :** Proposer de remplacer un calendrier personnalisé par la nouvelle version du référentiel
**Épic :** ÉPIC 8 — Confiance et personnalisation du calendrier *(numéro à valider, voir le plan de l'épic)*

**Story :**
En tant que jardinier dont le potager a un calendrier personnalisé pour une culture
Je veux être prévenu que le calendrier de référence de cette culture a évolué depuis ma copie, et pouvoir le remplacer par la nouvelle version, culture par culture ou pour toutes mes cultures d'un coup
Afin de bénéficier des mises à jour du référentiel sans que personne ne puisse écraser mes corrections à ma place

**Contexte fonctionnel :**
Retour du 28/10/2026, après le déploiement dev qui importe `wind_river_attributs.json` (US-254). Un bloc comme celui-ci est bien importé :

```json
{ "culture": "courgette", "itineraire": "standard",
  "durees": { "levee": "7-10", "recolte": null, "repiquage": null },
  "fenetres": { "oceanique": { "semis_pepiniere": "avril", "plantation": "mai", "recolte": "juillet-août" } } }
```

L'import met à jour l'itinéraire **partagé** (`potager_id` NULL). Mais la première correction d'un potager (`/calendrier fenetre …` ou `/calendrier duree …`) COPIE l'itinéraire partagé en itinéraire **personnalisé** qui le remplace pour ce potager (US-068 / CA11), et l'import ne lit ni n'écrit jamais un itinéraire personnalisé (US-068 / CA9). Conséquences :
- ce potager ne reçoit plus aucune mise à jour de la culture, même s'il ne la sème ni ne la plante plus : la copie reste en base ;
- rien ne l'en informe : il lit un calendrier périmé sans le savoir ;
- les mises à jour ne profitent qu'aux potagers qui n'ont jamais rien corrigé, ou aux itinéraires créés après.

Ce comportement est voulu (un calendrier est une préférence, pas un fait botanique) : l'import n'a pas à changer. Ce qui manque, c'est la décision du jardinier. Les attributs de conduite (`culture_config`, US-161) sont partagés sans copie par potager : ils sont déjà à jour et ne sont **pas** concernés.

**Décisions du 28/10/2026 :**
- **Remplacement pur**, jamais de fusion : si le jardinier accepte, sa copie est remplacée par la version de référence, ses corrections sur cet itinéraire disparaissent. Il n'y a donc ni conflit à arbitrer, ni ligne « vidée volontairement » à distinguer d'une nouveauté.
- **Par culture**, avec la possibilité de tout mettre à jour d'un coup quand plusieurs cultures sont concernées.
- **Pas de dictée** à ce stade (US-172 non étendue) : commande et boutons seulement.

**Principe retenu :**
- **Remplacer = supprimer la copie personnalisée** (itinéraire, fenêtres, durées) de ce potager pour cet itinéraire. La lecture retombe alors sur le partagé (`lire_calendrier`) : le potager suit à nouveau le référentiel, y compris pour ses prochaines mises à jour, jusqu'à une nouvelle correction qui recrée une copie à partir de la version courante.
- **Détecter l'évolution par une empreinte.** Sans trace de ce que le partagé valait au moment de la copie, on ne distingue pas « le référentiel a changé » de « mes propres corrections diffèrent du partagé » : le jardinier qui a corrigé serait alerté en permanence. La copie mémorise donc l'empreinte du partagé qu'elle a copié ; l'écart est « l'empreinte du partagé aujourd'hui ≠ l'empreinte mémorisée ».
- **Un itinéraire personnalisé sans homologue partagé** (créé de zéro, origine `saisie_manuelle`) n'a rien à quoi se comparer : il n'est jamais listé ni touché.

**Critères d'acceptance :**
- [ ] CA1 — Détection : une fonction de `calendrier_cultural` (lecture seule) liste, pour un potager, les cultures dont l'itinéraire personnalisé a un homologue partagé de même nom et dont l'empreinte du partagé actuel diffère de l'empreinte mémorisée. L'empreinte porte sur (zone, phase, mois de début et de fin) pour les fenêtres et (étape, jours ou mention) pour les durées. Un itinéraire sans homologue partagé n'est jamais listé. Les copies faites **avant** cette US n'ont pas d'empreinte (NULL) : elles sont listées si, et seulement si, leurs valeurs diffèrent de celles du partagé ; une copie identique au partagé n'est pas listée.
- [ ] CA2 — Mémorisation à la copie : `_itineraire_personnalise` enregistre l'empreinte du partagé copié sur l'itinéraire créé. Migration v62 : colonne nullable `itineraire_cultural.empreinte_reference`, `rollback_v62.sql`, aucun backfill (NULL = base inconnue, lue au CA1).
- [ ] CA3 — `/calendrier maj` : liste les cultures du CA1 avec, pour chacune, le nombre de valeurs qui diffèrent (zone du potager et durées), et un bouton par culture. À partir de deux cultures, un bouton « Tout mettre à jour (N) » s'ajoute. Sans écart, le bot répond que le calendrier du potager suit déjà le référentiel.
- [ ] CA4 — `/calendrier maj <culture>` : affiche l'avant/après de ce qui diffère pour la zone du potager et les durées, avec les boutons « ✅ Remplacer par le référentiel » et « 🔒 Garder ma version ». Le récapitulatif prévient que les corrections faites sur cet itinéraire seront perdues. Une culture sans écart répond pourquoi (suit déjà le référentiel, pas de calendrier personnalisé, culture inconnue).
- [ ] CA5 — Remplacement : après le clic sur ✅, la copie personnalisée de ce potager pour cet itinéraire est supprimée (fenêtres, durées, itinéraire) et `lire_calendrier` renvoie les valeurs du partagé avec `personnalise=False`. Rien n'est écrit avant la confirmation. Les autres itinéraires de la même culture (autre nom) et les autres potagers ne sont pas touchés. Toutes les zones sont remplacées, pas seulement celle du potager, puisque la copie entière disparaît.
- [ ] CA6 — Tout mettre à jour : une seule confirmation nomme les cultures concernées ; le remplacement est tout ou rien (une seule transaction) : si l'une échoue, aucune n'est remplacée et le bot le dit.
- [ ] CA7 — Garder ma version : mémorise l'empreinte actuelle du partagé sur la copie et ne la modifie pas autrement. Le bot ne repropose cette culture qu'à la prochaine évolution du référentiel.
- [ ] CA8 — Indice passif : `/calendrier <culture>` ajoute une ligne « Le référentiel a évolué depuis votre copie — `/calendrier maj <culture>` » quand le CA1 liste cette culture, et rien sinon. Aucun message n'est envoyé spontanément.
- [ ] CA9 — Après un remplacement, une nouvelle correction (`/calendrier fenetre …`) recrée une copie à partir de la version courante du référentiel, avec son empreinte (CA2).
- [ ] CA10 — Droits et isolation : le remplacement et « Garder ma version » passent par `_verifier_ecriture` (un lecteur est refusé) ; un test à deux potagers montre que ni la liste, ni l'indice, ni le remplacement ne voient ou ne touchent l'autre.
- [ ] CA11 — Journal : chaque remplacement écrit une ligne `[US-279]` (potager, culture, itinéraire, nombre de fenêtres et de durées supprimées), comme les corrections d'US-068.
- [ ] CA12 — Non-régression de l'import : un rejeu de `tools/importer_referentiel.py` après une copie laisse l'itinéraire personnalisé intact (CA9 d'US-068 reste vrai) ; US-254 et `tests/test_us005_deploiement.py` restent verts.
- [ ] CA13 — Documentation, dans la même livraison : `docs/domaines/calendrier-cultural.md` (la décision « CORRECTION » et une section dédiée), `docs/domaines/commandes-bot.md`, `docs/domaines/migrations.md`, l'aide de `/calendrier`, et `data/connaissance/doc_app/calendrier-et-zone-climatique.md` (« les mises à jour du calendrier général n'effacent jamais une correction » devient « … sauf si le jardinier demande lui-même le remplacement »). `pytest tests/test_us099_corpus_fonctionnement.py` reste vert.

**Hors périmètre :**
- La fusion entre la copie et la nouvelle version (conserver les corrections, remplacer le reste) : écartée par la décision du 28/10.
- La dictée (« mets à jour le calendrier de mes courgettes »), US-172.
- Un message spontané après déploiement : dépend d'US-267, non livrée. L'indice du CA8 le remplace.
- L'affichage de l'écart et le bouton de remplacement dans le frontend (fiche calendrier, Plan) : US ultérieure, qui pourra lire le CA1.
- Une valeur du partagé qui n'a pas été mise à jour parce que `_peut_ecrire` (US-166) préserve une valeur d'une autre origine : sujet distinct, à diagnostiquer à part.

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : calendrier cultural, commandes du bot
- Migration BDD requise : oui (v62 à confirmer : la v61 n'est pas encore commitée)
- Dépendances : **US-068 (origine : CA9 l'import n'écrit que du partagé, CA11 copie à la première correction, PIA-59)**, US-254 (import au déploiement, PIA-231, qui rend l'écart visible), US-166 (import, registre des sources), US-161 (manifeste Wind River). Pattern de confirmation par boutons ✅ / ❌ : voir US-278 / CA3. Aucune dépendance à une US non livrée.
- Code concerné : `app/services/calendrier_cultural.py` (détection, remplacement, mémorisation dans `_itineraire_personnalise`), `app/bot/commandes_calendrier.py` (sous-commande `maj`, boutons, indice), `database/models.py` (`ItineraireCultural.empreinte_reference`), `migrations/migration_v62.sql` et `rollback_v62.sql`. `app/services/import_referentiel.py` : aucun changement attendu.
- Production conseillée : **Opus 5.5, effort `high`**. La suppression est irréversible et l'isolation entre potagers est le cœur du risque (CA5, CA10).

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Given le potager A a corrigé la fenêtre de plantation des courgettes, ce qui a créé un calendrier personnalisé
And le référentiel partagé des courgettes a évolué depuis cette copie
When le jardinier écrit "/calendrier maj"
Then le bot liste "courgette" avec le nombre de valeurs qui diffèrent
And rien n'est modifié

When le jardinier ouvre "/calendrier maj courgette" puis clique "✅ Remplacer par le référentiel"
Then la copie personnalisée des courgettes du potager A est supprimée
And "/calendrier courgette" affiche les valeurs du référentiel
And le potager B, qui avait aussi corrigé les courgettes, garde sa copie

When le jardinier clique "🔒 Garder ma version" sur une autre culture
Then cette culture n'est plus proposée
Until le référentiel évolue de nouveau
```

**Labels GitHub :** `us`, `calendrier`, `referentiel`, `bot`
