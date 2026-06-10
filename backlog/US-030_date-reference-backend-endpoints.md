**ID :** US-030  
**Titre :** Paramètre date de référence sur les endpoints et commandes Telegram

**Story :**  
En tant que jardinier  
Je veux pouvoir interroger l'état de mon potager à une date passée  
Afin de reconstituer ce que j'avais en stock, en godet ou en plan à n'importe quel moment de la saison

---

**Contexte métier :**

Toutes les vues (plan, stocks, pépinière, historique) sont aujourd'hui calculées "à aujourd'hui". Le calcul est event-sourced : on rejoue tous les événements depuis l'origine. L'objectif est de limiter cette fenêtre à `WHERE date <= date_ref`.

Par défaut `date_ref = date du jour` → comportement actuel inchangé.

---

**Critères d'acceptance :**

**Endpoints FastAPI :**
- [ ] CA1 : `GET /plan` accepte un query param optionnel `date_ref: date | None = None` (format ISO `YYYY-MM-DD`) — défaut = date du jour
- [ ] CA2 : `GET /stats` accepte `date_ref` — toutes les requêtes sous-jacentes (`calcul_stock_cultures`, section semis) filtrent `WHERE date <= date_ref`
- [ ] CA3 : `GET /godets` accepte `date_ref` — `calcul_godets_par_culture()` reçoit `date_ref` et filtre les événements en conséquence
- [ ] CA4 : `GET /historique` accepte `date_ref` — retourne les 10 derniers événements dont la date est `<= date_ref` (et non les 10 derniers absolus)
- [ ] CA5 : Quand `date_ref` est une date future, le backend la remplace silencieusement par la date du jour (pas d'erreur 400)
- [ ] CA6 : La réponse de chaque endpoint inclut un champ `date_ref_effective: str` (ISO) indiquant la date réellement utilisée — utile pour debug et affichage front

**Calcul de stock :**
- [ ] CA7 : `calcul_stock_cultures(db, date_ref)` — signature enrichie, filtre les événements `WHERE date <= date_ref` avant tout calcul
- [ ] CA8 : `calcul_godets_par_culture(db, date_ref)` — idem, tous les semis/mises en godet/plantations postérieurs à `date_ref` sont ignorés
- [ ] CA9 : La logique de déduction des stocks reste identique ; seule la fenêtre temporelle change — aucune régression sur les calculs "aujourd'hui"

**Bot Telegram :**
- [ ] CA10 : `/plan <date>` — `date` optionnel au format `YYYY-MM-DD` ou `JJ/MM/AAAA` ; si absent = aujourd'hui
  - Exemples : `/plan 2025-05-01` · `/plan 01/05/2025` · `/plan` (inchangé)
- [ ] CA11 : `/stats <date>` — stats globales à la date spécifiée
  - Exemples : `/stats 2025-05-01` · `/stats` (inchangé)
- [ ] CA12 : `/stats <culture> <date>` — stats d'une culture à la date spécifiée
  - Exemples : `/stats tomate 2025-05-01` · `/stats tomate` (inchangé)
- [ ] CA13 : Quand une date passée est utilisée via Telegram, le bot précise la date en tête du message : _"📅 État au 01/05/2025"_
- [ ] CA14 : Si la date fournie est mal formée (ex. `32/13/2025`), le bot répond avec un message d'erreur clair sans plantage

**Tests :**
- [ ] CA15 : Tests unitaires couvrant : stock à date antérieure, stock à date future (≡ aujourd'hui), stock date = date d'un événement (inclusion)
- [ ] CA16 : Tests Telegram couvrant : parse des deux formats de date, commande sans date (régression)

---

**Notes fonctionnelles :**
- Zone fonctionnelle concernée : API REST (`main.py`), calcul stock (`utils/stock.py`), commandes Telegram (`bot.py` — `cmd_plan`, `cmd_stats`)
- Migration BDD requise : **non** — aucun changement de schéma, uniquement du filtrage
- Dépendances : US-025, US-026, US-024 (les endpoints qu'ils consomment sont modifiés ici)
- Rétrocompatibilité : tous les appels sans `date_ref` continuent de fonctionner à l'identique

**Estimation :** 5 points

**Scénario Gherkin :**
```gherkin
Scenario: Consultation du plan à une date passée via API
  Given des événements de plantation entre le 01/04 et le 01/06
  When GET /plan?date_ref=2025-05-01
  Then seuls les événements antérieurs ou égaux au 01/05 sont pris en compte
  And le champ date_ref_effective vaut "2025-05-01"

Scenario: Défaut = aujourd'hui
  Given aucun paramètre date_ref dans la requête
  When GET /stats
  Then date_ref_effective vaut la date du jour

Scenario: Date future normalisée
  Given date_ref = 2099-01-01
  When GET /godets?date_ref=2099-01-01
  Then date_ref_effective vaut la date du jour
  And aucune erreur 400 n'est retournée

Scenario: Commande Telegram /plan avec date
  Given un utilisateur Telegram
  When l'utilisateur envoie "/plan 01/05/2025"
  Then le bot affiche "📅 État au 01/05/2025" en tête de réponse
  And le contenu reflète l'occupation des parcelles à cette date

Scenario: Date mal formée via Telegram
  Given un utilisateur Telegram
  When l'utilisateur envoie "/stats 32/13/2025"
  Then le bot répond "Format de date invalide — utilise JJ/MM/AAAA ou AAAA-MM-JJ"
```

**Labels GitHub :** `us`, `sprint-frontend`, `backend`, `date-reference`, `api`
