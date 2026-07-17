**ID :** US-041
**Titre :** Extraire la couche `services/` partagée bot ⇄ PWA avec contexte tenant
**Épic :** ÉPIC 1 — Socle multi-tenant

**Story :**
En tant qu'administrateur de la plateforme
Je veux que toute la logique métier (événements, stats, stock, plan, questions) soit extraite dans une couche `app/services/` prenant obligatoirement un contexte tenant en paramètre
Afin que l'isolation par potager (à venir) soit codée une seule fois, au lieu d'être dupliquée — et donc potentiellement fausse — entre `bot.py` et `main.py`

**Contexte fonctionnel :**
Aujourd'hui, la logique métier est éclatée entre `bot.py` (~1300 lignes) et `main.py`, chacun exécutant ses propres requêtes SQLAlchemy. Le socle de données multi-tenant a été posé par US-040 (`users`, `potagers`, `potager_membres`, colonnes `potager_id` nullables). Cette US ne fait *pas* le scoping applicatif lui-même (réservé à une US ultérieure) : elle prépare le terrain en centralisant tous les accès aux données métier derrière des fonctions de service qui acceptent un contexte, afin que le scoping puisse ensuite être ajouté à un seul endroit par fonction plutôt qu'à chaque appel dispersé dans `bot.py`/`main.py`.

**Critères d'acceptance :**
- [ ] CA1 : Une classe/dataclass `TenantContext(user_id, potager_id, role)` existe dans `app/services/__init__.py` (ou module dédié `app/services/context.py`)
- [ ] CA2 : Pendant la transition, `TenantContext` peut être construit avec des valeurs fixes correspondant au potager #1 / user #1 issus du backfill US-040 (`potager_id=1`), documenté comme temporaire dans un commentaire renvoyant à l'US de scoping applicatif à venir
- [ ] CA3 : Module `app/services/evenements.py` créé — expose au minimum `enregistrer_evenement(ctx, data) -> Evenement`, `corriger_evenement(ctx, evenement_id, data) -> Evenement`, `supprimer_evenement(ctx, evenement_id) -> None`, `lister_evenements(ctx, filtres) -> list[Evenement]`
- [ ] CA4 : Module `app/services/stats.py` créé — expose la logique actuellement dans `/stats` (bot) et `GET /stats` (API), signature `calculer_stats(ctx, ...) -> StatsResult`
- [ ] CA5 : Module `app/services/stock.py` créé — encapsule `utils/stock.calcul_stock_cultures()` derrière une fonction acceptant `ctx`
- [ ] CA6 : Module `app/services/plan.py` créé — encapsule la logique de `/plan` (bot) et de l'endpoint plan occupation (API)
- [ ] CA7 : Module `app/services/questions.py` créé — encapsule `_ask_question()` (renommée/déplacée), signature `repondre_question(ctx, question: str) -> str`
- [ ] CA8 : Après refactor, `bot.py` et `main.py` ne contiennent plus aucun `db.query(Evenement)`, `db.query(Parcelle)` ni équivalent direct sur les tables métier hors des modules `services/` — ils appellent exclusivement les fonctions de service
- [ ] CA9 : Le logging structuré `HH:MM:SS │ LEVEL │ emoji MESSAGE` existant est conservé à l'identique dans les services (déplacé depuis `bot.py`/`main.py`, pas dupliqué)
- [ ] CA10 : SQLAlchemy 2.0 strict dans tout code nouveau ou déplacé : `db.get()`, jamais `db.query().get()`
- [ ] CA11 : Tests de non-régression sur les 12 actions canoniques (`recolte`, `semis`, `plantation`, `arrosage`, `desherbage`, `taille`, `paillage`, `tuteurage`, `fertilisation`, `observation`, `perte`, `mise_en_godet`) + flux de correction `corr_*` + mode `ask` passent sans modification de comportement observable côté utilisateur

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : enregistrement | analyse | consultation (aucun changement d'interaction Telegram ni PWA visible par l'utilisateur)
- Migration BDD requise : non (refactor de code applicatif uniquement)
- Dépendances : US-040 (socle de données tenant)
- Zéro impact tokens Groq : les appels LLM existants sont déplacés tels quels, pas modifiés
- Invariants projet : logging structuré conservé, prompts Groq toujours en `.replace()` jamais `.format()`, ordre critique des flux de conversation (`corr_*` > `ask` > NAV > question > action) inchangé côté `bot.py`

**Notes techniques (pour Persona Developer) :**
- Composants impactés : nouveaux modules `app/services/context.py`, `app/services/evenements.py`, `app/services/stats.py`, `app/services/stock.py`, `app/services/plan.py`, `app/services/questions.py` ; modifications dans `bot.py` et `main.py` (remplacement des accès directs par des appels de service)
- Recommandation : découper la mise en œuvre en sous-étapes par module (événements, puis stats, puis stock, puis plan, puis questions) pour limiter le risque de régression sur un refactor aussi large, chaque étape validée par les tests avant de passer à la suivante
- Les états `ctx.user_data` (Telegram) restent côté `bot.py` — ils ne migrent PAS dans `services/` (leur persistance sera traitée par une US Redis ultérieure, hors périmètre ici)
- `TenantContext` doit être conçu pour accueillir sans changement de signature les futures valeurs dynamiques (utilisateur authentifié, potager actif, rôle réel) issues des US d'authentification à venir

**Estimation :** 8 points

**Scénario Gherkin :**
```gherkin
Scénario: Enregistrement d'un événement via la couche services
  Given le refactor services/ est en place
  When le jardinier dicte "j'ai récolté 2 kg de tomates"
  Then bot.py appelle services.evenements.enregistrer_evenement(ctx, data)
  And l'événement est enregistré en base comme avant le refactor

Scénario: Aucune requête directe hors des services
  Given le code de bot.py et main.py après refactor
  When on recherche db.query(Evenement) ou équivalent direct sur les tables métier
  Then aucune occurrence n'est trouvée en dehors du dossier app/services/

Scénario: Non-régression du mode ask
  Given le refactor services/ est en place
  When le jardinier pose une question analytique via /ask
  Then services.questions.repondre_question(ctx, question) est appelée
  And la réponse est identique à celle produite avant le refactor

Scénario: Non-régression des flux de correction
  Given le refactor services/ est en place
  When le jardinier lance /corriger puis confirme une modification
  Then services.evenements.corriger_evenement(ctx, ...) est appelée
  And l'événement corrigé est identique à celui produit avant le refactor
```

**Labels GitHub :** `us`, `sprint-multi-tenant`, `refactor`, `multi-tenant`, `fondation`
