**ID :** US-049
**Titre :** Validation centrale et non contournable avant toute écriture d'un Evenement
**Épic :** Qualité des données / Fiabilité

**Story :**
En tant que jardinier utilisateur du bot
Je veux qu'aucun événement incohérent (culture jamais plantée, variété absente de la parcelle citée, parcelle inexistante...) ne puisse jamais être écrit en base, quel que soit le chemin emprunté pour l'enregistrer
Afin de ne plus jamais retrouver de récoltes fantômes dans mon historique, même quand Groq segmente ma phrase en plusieurs événements ou que je passe par un flux de correction/callback plutôt que la confirmation standard

**Contexte fonctionnel :**
Deux garde-fous ont été ajoutés dans `bot.py::_parse_and_save` (branche `fix/telegram-recolte-validation`) suite à des bugs terrain :
1. incohérence culture/variété ↔ parcelle citée (ex : "tomate cerise" enregistrée sur une parcelle où seules "coeur de boeuf" et "noire de crimée" ont été plantées) ;
2. culture jamais semée/plantée/mise en godet dans le potager (ex : récolte de "mangue" acceptée sans qu'aucun semis n'existe).

Ces deux contrôles se sont révélés contournables : le second était conditionné à `len(items) == 1`, et Groq segmente régulièrement une phrase multi-culture ("cueilli 2 kilos de cerise, tomates, nord") en plusieurs items dans la même réponse JSON — le contrôle ne s'exécutait alors sur aucun des deux items, et les deux récoltes fantômes ont été enregistrées (`id=337` culture=cerise, `id=338` culture=tomate, tous deux rattachés à `parcelle=1001` sans qu'aucune des deux cultures n'y ait d'historique).

Le problème est structurel, pas ponctuel : `app/services/evenements.py` expose au moins six fonctions qui construisent et persistent un `Evenement` de façon indépendante (`creer_evenement_depuis_parse`, `creer_evenement_ligne`, `creer_evenement_confirme`, `creer_evenement_godet`, `creer_evenement_observation`, `creer_evenement_perte`), plus `corriger_evenement` qui mute un événement existant et `deplacer_evenements` qui réassigne culture/parcelle sur des lignes déjà en base. Un contrôle ajouté dans `bot.py` (couche Telegram, en amont de la confirmation) ne protège qu'**un seul** de ces chemins pour **un seul** type d'appel. Tant que la validation vit dans la couche d'orchestration Telegram plutôt que dans la couche de persistance, chaque nouveau flux (callback, correction, note, futur endpoint API PWA) est un contournement potentiel — comme l'a démontré ce bug en quelques jours d'usage réel.

**Critères d'acceptance :**
- [ ] CA1 : Une fonction unique de validation (ex. `valider_evenement(db, ctx, culture, variete, parcelle_obj, action) -> None`, lève une exception métier explicite si invalide) est appelée systématiquement à l'intérieur de **chacune** des fonctions de `app/services/evenements.py` qui écrivent un `Evenement`, jamais dans `bot.py` ou `main.py`
- [ ] CA2 : La validation regroupe au minimum les règles déjà identifiées : (a) culture jamais introduite via semis/plantation/mise_en_godet pour les actions qui présupposent une culture existante ; (b) incohérence culture/variété ↔ parcelle citée quand une parcelle est fournie ; (c) parcelle inconnue (règle déjà existante, à faire migrer vers ce point unique plutôt que dupliquée dans `_do_save_items`)
- [ ] CA3 : Aucune des règles ne dépend du nombre d'items traités dans un même appel Telegram — la validation s'applique item par item, indépendamment de tout `len(items) == 1` côté appelant
- [ ] CA4 : Un test d'intégration reproduit exactement le bug rapporté (phrase multi-culture segmentée par Groq en plusieurs items dans la même réponse) et prouve qu'aucun des deux événements incohérents n'est écrit
- [ ] CA5 : Un test générique parcourt automatiquement toutes les fonctions de `app/services/evenements.py` qui construisent un `Evenement` (par introspection ou liste explicite documentée) et vérifie qu'aucune ne permet d'écrire une culture jamais plantée — pour empêcher qu'une future fonction d'écriture oublie d'appeler la validation
- [ ] CA6 : Le comportement observable pour l'utilisateur reste celui déjà livré sur `fix/telegram-recolte-validation` (parcelle incohérente traitée comme non-saisie, culture inconnue bloquée avec message explicite) — cette US est un refactor de robustesse, pas un changement de comportement fonctionnel
- [ ] CA7 : `deplacer_evenements` (réassociation culture/parcelle a posteriori) et `corriger_evenement` (flux de correction conversationnel) passent par la même validation avant toute mise à jour, pas seulement les créations

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : cœur métier (`app/services/evenements.py`), tous canaux (Telegram, corrections, notes, et futur usage PWA/API)
- Migration BDD requise : non
- Dépendances : reprend et généralise les correctifs de `fix/telegram-recolte-validation` (garde-fous culture/parcelle déjà écrits côté `bot.py`, à faire migrer plutôt qu'à dupliquer)
- Zéro impact tokens Groq (validation 100 % Python/SQL, aucun appel LLM)
- Invariants projet : même philosophie que US-043 (RLS PostgreSQL) — défense en profondeur au point de persistance plutôt que confiance placée dans chaque appelant

**Notes techniques (pour Persona Developer) :**
- Composants impactés : `app/services/evenements.py` (nouvelle fonction de validation + appel dans les 6 fonctions de création + `corriger_evenement` + `deplacer_evenements`), `bot.py` (retrait des garde-fous dupliqués une fois la validation centrale en place, remplacés par la gestion de l'exception levée)
- Fonctions de création d'`Evenement` recensées à date (à réviser au moment de l'implémentation, la liste peut évoluer) : `creer_evenement_depuis_parse` (l.294), `creer_evenement_ligne` (l.335), `creer_evenement_confirme` (l.363), `creer_evenement_godet` (l.424), `creer_evenement_observation` (l.473), `creer_evenement_perte` (l.501)
- La validation doit lever une exception dédiée (ex. `EvenementInvalideError`) plutôt que retourner un booléen, pour qu'un oubli de vérifier le retour ne puisse pas silencieusement laisser passer un événement invalide — chaque appelant Telegram traduit l'exception en message utilisateur
- Attention à ne pas bloquer les actions "source" (semis, plantation, mise_en_godet, vendu, perte_godet — cf. `_ACTIONS_SOURCE` dans `bot.py`) : ce sont elles qui introduisent légitimement une nouvelle culture, la validation ne doit s'appliquer qu'aux actions qui présupposent une culture déjà en place
- CA5 (test qui parcourt toutes les fonctions d'écriture) est le point le plus important de cette US : c'est lui qui transforme "on a pensé à ajouter le contrôle partout" en "il est structurellement impossible d'oublier de l'ajouter quelque part" — à concevoir avant le reste de l'implémentation, pas en dernier

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scénario: Bug rapporté — phrase multi-culture segmentée par Groq
  Given aucune culture "cerise" ni "mangue" n'a jamais été plantée dans le potager
  When le jardinier dicte "cueilli 2 kilos de cerise, tomates, nord"
  And Groq segmente la phrase en deux items ["cerise", "tomate"] dans la même réponse
  Then aucun des deux événements n'est écrit en base
  And un message explicite indique quelle(s) culture(s) posent problème

Scénario: Validation appliquée quel que soit le chemin d'écriture
  Given une culture jamais plantée dans le potager
  When un événement est créé via n'importe laquelle des fonctions de creer_evenement_* de app/services/evenements.py
  Then la création est refusée par la même règle, sans exception de chemin

Scénario: Non-régression — culture réellement plantée
  Given "tomate" a été semée dans le potager
  When le jardinier dicte "récolté 2 kg de tomates"
  Then l'événement est enregistré normalement, sans friction supplémentaire

Scénario: Actions source non bloquées
  Given aucune trace de "mangue" dans le potager
  When le jardinier dicte "semé des graines de mangue"
  Then l'événement de semis est enregistré normalement — c'est cette action qui introduit la culture
```

**Labels GitHub :** `us`, `qualite-donnees`, `architecture`, `bug`, `evenements`
