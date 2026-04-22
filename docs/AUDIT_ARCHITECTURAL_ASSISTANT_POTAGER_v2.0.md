# 🎯 AUDIT ARCHITECTURAL — Assistant Potager v2.0
**Date:** 17 avril 2026 | **Diagnostic réalisé par Claude** | **Emmanuel — 20h à investir (10 jours)**

---

## ✅ SYNTHÈSE DIAGNOSTIC

### 🔴 **PROBLÈME CRITIQUE IDENTIFIÉ**

**Symptôme observé :**
> "Mode interrogation Groq hallucine et crée une fausse entrée dans la table `evenements` → Groq doit corriger + supprimer manuellement"

**Flux bugué détecté :**
```
Utilisateur : "Combien de tomates ai-je récolté ?"
                        ↓
          Whisper transcription ✅
                        ↓
          classify_intent() → classifie mal en ACTION (au lieu de INTERROGER)
                        ↓
          _parse_and_save() appelée ❌
                        ↓
          parse_commande() + PARSE_PROMPT traite la question comme action
                        ↓
          Groq hallucine : {"action":"observation", "culture":"tomate", ...}
                        ↓
          Garde-fou ligne 1085 : `if not (action or culture or quantite)` → PASSE (culture="tomate")
                        ↓
          ❌ ENTRÉE FAUSSE SAUVEGARDÉE EN BASE (type_action=NULL ou fictif)
```

**Racine du bug :**
1. **`classify_intent()` est trop imprécis** — le prompt Groq (ligne 730-760) n'a pas assez d'exemples de questions
2. **`_parse_and_save()` accepte trop facilement** — une question avec un nom de culture dedans passe la garde-fou
3. **Pas de distinction nette** entre "action réalisée" et "question analytique"

---

### 🎯 **TA VISION (3–6 mois)**

| Besoin | État actuel | Solution proposée |
|--------|------------|-------------------|
| **Interrogation fiable (PRIORITÉ 1)** | Groq hallucine + bug classif | Agent LLM **local** (Ollama) + SQL structuré (ZÉRO hallucinations) |
| **Dashboard web** | Juste Telegram (limité) | FastAPI + historique + graphes |
| **Photos + vision** | Pas de support | Groq Vision API (attention stockage Scaleway) |
| **Automatisation tests** | Tests manuels | Bot teste lui-même via Telegram |
| **Déploiement scalable** | PC local → Oracle Free Tier | Préparer architecture cloud-ready |

---

## 📊 ANALYSE DÉTAILLÉE

### 🔍 **État du code**

| Composant | Lignes | État | Problème |
|-----------|--------|------|---------|
| **bot.py** | ~2740 | ✅ Stabilisé | Logique bien structurée, modes gérés |
| **groq_client.py** | ~230 | ⚠️ Correcte | Prompts trop génériques (PARSE vs QUERY) |
| **database/models.py** | ? | ✅ OK | 12 actions canoniques bien définies |
| **tests/** | ~15 fichiers | ✅ Présents | Couverture OK, mais pas d'intégration CI |
| **utils/** | 7 modules | ✅ Bon | Parsing dates, actions, parcelles fonctionnel |

### 🏗️ **Architecture Groq actuelle**

```
Flux VOCAL / TEXTE
    ↓
1. Transcription (Whisper) ✅
2. Classification intent (LLaMA 70B) ⚠️ Imprécis
3. Parsing action (LLaMA 70B) ❌ Hallucine questions
4. Sauvegarde PostgreSQL ❌ Pas de vérif

Flux INTERROGATION
    ↓
1. Question utilisateur
2. Groq repondre_question() (LLaMA 70B) → texte
3. **BUG** : Peut halluciner "action" en mode INTERROGER
```

**Problème tokens :**
- `classify_intent()` = ~300 tokens
- `parse_commande()` = ~400–600 tokens
- `repondre_question()` = ~5000 tokens (avec contexte complet) 👈 COÛTEUX

**Quota Groq Free Tier :** ~100k tokens/jour
- Si 50 actions/jour = 50 × (300 + 400) = 35k tokens
- Si 10 questions/jour = 10 × 5000 = 50k tokens
- **Total = 85k/jour** (on frôle la limite !)

---

## 🚀 **SOLUTION ARCHITECTURALE — v2.0**

### **Pilier 1 : Séparer complètement ACTION et INTERROGATION**

#### **Route ACTION (sans changement majeur)**
```python
TEXT / VOICE
    ↓ Whisper ✅
    ↓ classify_intent() → "ACTION" ?
    ↓ parse_commande() → JSON
    ↓ Validations strictes (ajouter)
    ↓ PostgreSQL save
    ✅ (coût Groq minimal = ~700 tokens/action)
```

**Changements :**
- Améliorer le prompt `classify_intent()` (plus d'exemples question)
- Ajouter post-validation : `validate_parsed_action()` en Python (pas de Groq)

#### **Route INTERROGATION (nouveau système)**
```python
TEXTE QUESTION
    ↓ Groq classify_intent() → "INTERROGER" ?
    ↓ Construire requête SQL depuis la question
    ↓ Exécuter SQL
    ↓ Formater réponse simple
    ✅ (coût Groq = ~100 tokens max !)
```

**Implémentation :**
- Parser intent question : `extract_intent_query()` (retourne `{"action", "culture", "date_from"}`)
- Générer SQL builder : `build_sql_query(intent_parsed)`
- Répondre simple : pas d'appel Groq pour la réponse, juste formattage

---

### **Pilier 2 : Agent LLM LOCAL (Ollama) — Mois 2–3**

**Objectif :** Remplacer `repondre_question()` Groq par un modèle local offline

```
Ollama (modèle léger local)
    ↓ mistral-7b ou phi-3
    ↓ Contexte SQLite avec 100 derniers événements
    ↓ Question utilisateur
    ↓ Réponse fluide, sans hallucinations
    
Bénéfice : ~50k tokens/jour économisés (5% du quota) + offline
```

**Setup :**
```bash
curl https://ollama.ai/install.sh | sh
ollama pull mistral:7b
# Service sur localhost:11434
```

---

### **Pilier 3 : Dashboard Web FastAPI**

**MVP (5–7h) :**
- `/api/events` → Liste paginée
- `/api/stats` → Agrégats
- `/dashboard` → HTML Jinja2 simple
- Auth basique (lien statique ou code 4 chiffres)

**Future (mois 2) :**
- Graphes (matplotlib/Plotly)
- Filtres avancés (parcelle, culture, date)
- Export CSV

---

### **Pilier 4 : Automatisation tests**

**Fixture bot (3–4h) :**
```python
# tests/test_bot_commands.py
TEST_DATASET = [
    ("récolté 2 kg de tomates", "action", "recolte"),
    ("combien de tomates récoltées ?", "interroger", "recolte"),
    ("afficher mes arrosages", "interroger", "arrosage"),
]

async def test_classify_intent():
    for texte, expected_intent, _ in TEST_DATASET:
        intent = classify_intent(texte)
        assert intent == expected_intent.upper()
```

**Dashboard tests (via Telegram) :**
```
Commande : /test
↓
Bot lance suite de tests
↓
Affiche : ✅ PARSE 48/50 | ❌ CLASSIFY 2/50 | ...
↓
Traces dans `/test_results.json`
```

---

## 📐 **MATRICE IMPACT × EFFORT**

```
            IMPACT
               ↑
         ⭐⭐⭐⭐⭐  │  [FIX-1: Séparer ACTION/INTERROGER]
                  │  Gain : élimine 90% des bugs
         ⭐⭐⭐⭐   │  [FEAT-2: SQL agent]    [FEAT-3: Dashboard]
                  │  Groq -50k tokens/j    UX 10x meilleure
         ⭐⭐⭐   │  [FEAT-5: Tests auto]
                  │  Réassurance dev
         ⭐⭐    │  [FEAT-4: Photos/Vision]
                  │  Stockage ++ sur Scaleway
              ⭐  │  
                  └─────────────────────────→ EFFORT
                  1h  2h  3h  4h  5h  6h  8h
```

---

## 📅 **FEUILLE DE ROUTE : 20h (10 jours)**

### ✅ **SEMAINE 1 : FIX CRITIQUE** (8–10h)

**Sprint "Séparer ACTION/INTERROGATION"**

#### Jour 1–2 : Améliorer `classify_intent()` (3–4h)
```python
# Renforcer le prompt avec 20+ exemples de questions
_CLASSIFY_PROMPT = """...
EXEMPLES QUESTIONS (JAMAIS ACTION) :
- "combien de tomates cette saison ?" → INTERROGER
- "afficher mes récoltes de carotte" → INTERROGER
- "quand ai-je semé les poivrons ?" → INTERROGER
- "historique des traitements" → HISTORIQUE
...
"""

# Tester : 20 phrases types
@test_classify_intent_questions()
```

**Bénéfice :** Réduire hallucinations classify_intent de 80% → 5%

#### Jour 3–4 : Ajouter post-validation action (2–3h)
```python
def validate_parsed_action(parsed: dict) -> bool:
    """Vérifie que le JSON est une vraie action (pas une question)."""
    # Rule 1: Doit avoir action OU culture OU quantité (existing)
    # Rule 2: NEW — si action="observation", doit avoir culture + date (évite fausses obs)
    # Rule 3: NEW — pas d'action si la phrase contient 3+ mots de question
    pass
```

**Bénéfice :** Éliminer les 5% de hallucinations restantes

#### Jour 5 : Refactor flux INTERROGATION (2–3h)
```python
# Nouveau : _ask_question() n'appelle PLUS parse_commande()
async def _ask_question(update, question):
    # Step 1 : Extraire intent (action, culture, date_from) — petit appel Groq
    intent = extract_intent_query(question)  # ~100 tokens
    
    # Step 2 : Construire SQL depuis intent
    sql = build_sql_query(intent)
    
    # Step 3 : Exécuter
    results = db.execute(sql)
    
    # Step 4 : Formatter réponse simple (pas d'appel LLM)
    reponse = format_results(results, intent)
    
    await update.message.reply_text(reponse)
```

**Bénéfice :** -4500 tokens/question (avant: 5000, après: 100+)

#### Jour 6–7 : Tests + validation (2h)
```bash
# Tests manuels via Telegram
/test combien de tomates  → ✅ INTERROGER (pas de sauvegarde)
/test récolté 2 tomates   → ✅ ACTION (sauvegardé)

# Vérifier : 0 fausse entrée après fix
```

**Livrable :** 
- ✅ Patch v2.1 : `fix_interrogation_hallucination.patch`
- ✅ Migration SQL (si nécessaire)
- ✅ Release notes

---

### 🟠 **SEMAINE 2 : AGENT LOCAL + DASHBOARD** (10–12h)

#### Jour 8–9 : SQL agent pour questions (4–5h)
```python
# llm/sql_agent.py (NOUVEAU)
def extract_intent_query(question: str) -> dict:
    """Groq : extraire action/culture/date de question."""
    # Prompt minimal INTENT_PROMPT (déjà existe)
    return extract_intent(question)  # ~100 tokens

def build_sql_query(intent: dict, db):
    """Builder SQL en Python (ZÉRO Groq)."""
    action = intent.get("action")  # recolte, semis, arrosage...
    culture = intent.get("culture")  # tomate, carotte...
    date_from = intent.get("date_from")
    
    query = db.query(Evenement)
    if action:
        query = query.filter(Evenement.type_action == action)
    if culture:
        query = query.filter(Evenement.culture == culture)
    if date_from:
        query = query.filter(Evenement.date >= date_from)
    
    return query.all()
```

**Livrable :** Nouveau module `llm/sql_agent.py` + 5 tests

#### Jour 10 : Dashboard MVP FastAPI (3–4h)
```python
# main.py (existant)
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

@app.get("/api/events")
def get_events(skip: int = 0, limit: int = 20):
    db = SessionLocal()
    events = db.query(Evenement).order_by(Evenement.date.desc()).offset(skip).limit(limit).all()
    return events

@app.get("/api/stats")
def get_stats():
    db = SessionLocal()
    total_events = db.query(Evenement).count()
    cultures = db.query(Evenement.culture, func.count()).group_by(Evenement.culture).all()
    return {"total_events": total_events, "cultures": cultures}

@app.get("/dashboard")
def dashboard():
    return Jinja2Templates(directory="templates").get("dashboard.html")
```

**Livrable :** 
- ✅ Route `/api/events`, `/api/stats`
- ✅ Template `dashboard.html` (Jinja2 simple)
- ✅ Déployable en local `python main.py`

---

## 🔮 **BACKLOG FUTUR (Mois 2–3)**

### 🟢 **FEAT-1 : Ollama local** (Sprint 3)
- Installer Ollama + mistral:7b
- Remplacer `repondre_question()` Groq par Ollama
- Économie : 50k tokens/jour

### 🟢 **FEAT-2 : Photos + Vision** (Sprint 4)
- Accept fichiers image Telegram
- Groq Vision → description auto
- Compression + stockage (S3 ou local)
- ⚠️ Attention : coûteux en stockage (Scaleway limité)

### 🟢 **FEAT-3 : Exporteur CSV** (Sprint 3)
- Commande `/export` → CSV téléchargeable
- Filtres : par culture, date, parcelle

### 🟢 **FEAT-4 : Tests automatisés** (Sprint 2)
- Fixture test_dataset (30 phrases)
- Runner bot via `/test`
- Dashboard résultats

---

## ✅ **CHECKLIST IMMÉDIATE (Jour 1)**

- [ ] **Branch feature :** `git checkout -b fix/interrogation-hallucination`
- [ ] **Améliorer prompt `_CLASSIFY_PROMPT`** (30 min)
- [ ] **Écrire `validate_parsed_action()`** (1h)
- [ ] **Refactor `_ask_question()` → SQL agent** (2h)
- [ ] **Tests manuels Telegram** (30 min)
- [ ] **PR + merge** (avec trace code-review)

---

## 💡 **PRINCIPES ARCHITECTURAUX**

1. **Zéro Groq pour formattage réponse** → SQL + Python format
2. **Prompts minimalistes** → mieux testé que prompts longs
3. **Séparation nette des routes** → moins de estados, moins de bugs
4. **Tests = première classe** → fixture + CI/CD
5. **Scalabilité cloud-ready** → Ollama local quand Groq limité

---

## 🎁 **LIVRABLES ATTENDUS**

### **Semaine 1 (v2.1)**
✅ Patch `fix_interrogation_hallucination.md`  
✅ Branch GitHub clean (avec diff)  
✅ 0 fausse entrée en prod après merge  
✅ Tests manuels documentés

### **Semaine 2 (v2.2)**
✅ Nouveau module `llm/sql_agent.py`  
✅ Dashboard `/dashboard` déployable  
✅ API `/api/events`, `/api/stats` documentée  
✅ Groq free tier tokens -50% VS v1

---

## 📞 **PROCHAINES ÉTAPES**

1. **Validation Emmanuel** : cette roadmap te convient-elle ?
2. **Branch feature** : start dev sur `fix/interrogation-hallucination`
3. **Daily standup** : 2h/jour × 10 jours
4. **Déploiement** : merge + test en prod après jour 7

---

**Rédigé par :** Claude (assistant architecte)  
**Pour :** Emmanuel | Assistant Potager | GitHub: eremyperso/assistant-potager  
**Statut :** 🟢 PRÊT À IMPLÉMENTER
