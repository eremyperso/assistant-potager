# 📑 INDEX DOCUMENTS — Guide de lecture (2h/jour pendant 10 jours)

**Temps total à investir :** 20h (implémenter) + 2h (lire docs) = 22h

---

## 🚦 GUIDE RAPIDE PAR SITUATION

### 🔴 "Je viens juste de lire ta réflexion, je suis lost"
**Lire :** `RESUME_EXECUTIF_1PAGE.md` (5 min)
→ Comprendre le bug et la solution en 1 page
→ Décider OUI ou NON

### 🟠 "OK je veux implémenter, par où je commence ?"
**Lire :** `PLAN_IMPLEMENTATION_20h.md` — Section "JOUR 1–2" (30 min)
→ Fichiers à modifier, prompts exacts, étapes
→ Commencer par `bot.py` ligne 730

### 🟡 "Je veux comprendre l'architecture en détail"
**Lire :** 
1. `SCHEMAS_ARCHITECTURE_ASCII.md` (10 min) — diagrammes V1 vs V2.1
2. `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` (30 min) — contexte complet

### 🟢 "Je code, j'ai besoin du code exact"
**Lire :** `PLAN_IMPLEMENTATION_20h.md` — Section correspondante
→ Copier-coller directement dans IDE
→ Code commenté, sans ambiguïté

### 🔵 "Je dois lancer un test rapidement"
**Lire :** `SCHEMAS_ARCHITECTURE_ASCII.md` → "TEST MATRIX"
→ Cas de test exact, ce qui doit passer/échouer
→ Vérifier via Telegram bot

---

## 📋 DOCUMENTS FOURNIS

| Document | Durée | Contenu | Format | Pour qui |
|----------|-------|---------|--------|----------|
| **RESUME_EXECUTIF_1PAGE.md** | 5 min | Synthèse bug + solution | Markdown | ✅ Emmanuel (décision rapide) |
| **PLAN_IMPLEMENTATION_20h.md** | 2h | Code exact + étapes | Markdown + code | ✅ Emmanuel (implémentation) |
| **AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md** | 45 min | Diagnostic complet + roadmap | Markdown | ✅ Consultants/juniors |
| **SCHEMAS_ARCHITECTURE_ASCII.md** | 15 min | Diagrammes visuels | ASCII art | ✅ Visuels |
| **CETTE INDEX** | 10 min | Navigation docs | Markdown | ✅ Emmanuel |

---

## 🗓️ PROGRAMME LECTURE — 10 jours (2h/jour)

### **Jour 1 (avant de coder)**
- [ ] 15 min : `RESUME_EXECUTIF_1PAGE.md` (comprendre)
- [ ] 30 min : `SCHEMAS_ARCHITECTURE_ASCII.md` (visualiser)
- [ ] 30 min : `PLAN_IMPLEMENTATION_20h.md` — Jour 1–2 section
- [ ] 15 min : Créer branch `git checkout -b fix/interrogation-hallucination`

### **Jour 2–3 (code classify_intent)**
- [ ] 30 min : `PLAN_IMPLEMENTATION_20h.md` — Jour 1–2 section (relire code)
- [ ] 1h 30 : Coder + tester (voir `PLAN_IMPLEMENTATION_20h.md` exact)

### **Jour 4–5 (code validation.py)**
- [ ] 15 min : `PLAN_IMPLEMENTATION_20h.md` — Jour 3–4 section
- [ ] 1h 45 : Coder + tester

### **Jour 6–7 (code SQL agent + refactor _ask_question)**
- [ ] 30 min : `PLAN_IMPLEMENTATION_20h.md` — Jour 5–6 section
- [ ] 1h 30 : Coder + tester (code fourni, pas d'ambiguïté)

### **Jour 8 (tests + déploiement)**
- [ ] 15 min : `SCHEMAS_ARCHITECTURE_ASCII.md` — TEST MATRIX
- [ ] 1h 45 : Tests manuels via Telegram + PR/merge

### **Jour 9–10 (bonus : Dashboard MVP)**
- [ ] Lire `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` — Pilier 3
- [ ] 7h : Implémenter FastAPI dashboard (optionnel, sprint futur)

---

## 🧩 ORGANISATION DOCUMENTS PAR THÈME

### **Question : "C'est quoi le bug exactement ?"**
Lire → `RESUME_EXECUTIF_1PAGE.md` → section "TON VRAI PROBLÈME"  
Puis → `SCHEMAS_ARCHITECTURE_ASCII.md` → "V1 (ACTUELLE) — Les bugs"

### **Question : "Pourquoi c'est arrivé ?"**
Lire → `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` → "PROBLÈME CRITIQUE IDENTIFIÉ"  
Code ref → `bot.py` ligne 762 + 1283 + 1063

### **Question : "Comment je fixe ?"**
Lire → `PLAN_IMPLEMENTATION_20h.md` → section correspondante au jour  
Code exact → copier-coller, pas d'interprétation nécessaire

### **Question : "Ça va casser mon bot ?"**
Lire → `SCHEMAS_ARCHITECTURE_ASCII.md` → "TEST MATRIX"  
Puis → `RESUME_EXECUTIF_1PAGE.md` → "VALIDATION AVANT/APRÈS"

### **Question : "Ça vaut vraiment le coup ?"**
Lire → `RESUME_EXECUTIF_1PAGE.md` → "📊 AVANT vs APRÈS"  
Calcul → 56% tokens économisés, 0 bugs = oui 🎉

### **Question : "Et après ? Roadmap ?"**
Lire → `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` → "FEUILLE DE ROUTE : 20h"  
Puis → "BACKLOG FUTUR (Mois 2–3)" pour vision long-terme

---

## 🔍 INDEX FICHIERS À MODIFIER / CRÉER

### **Fichiers à MODIFIER**
- `bot.py` — 2 endroits
  - Ligne 730–760 : `_CLASSIFY_PROMPT` (améliorer prompt)
  - Ligne 1283–1316 : `_ask_question()` (refactor)
  - Voir → `PLAN_IMPLEMENTATION_20h.md` → "Jour 5–6"

- `llm/groq_client.py` — 1 fonction à ajouter
  - Après ligne 44 : ajouter `extract_intent_query()`
  - Voir → `PLAN_IMPLEMENTATION_20h.md` → "Étape 1"

### **Fichiers à CRÉER**
- `utils/validation.py` (NOUVEAU)
  - Code complet fourni dans `PLAN_IMPLEMENTATION_20h.md` → "Jour 3–4"
  - ~200 lignes, copy-paste direct

- `llm/sql_agent.py` (NOUVEAU)
  - Code complet fourni dans `PLAN_IMPLEMENTATION_20h.md` → "Étape 2"
  - ~150 lignes, copy-paste direct

- `tests/test_validation.py` (NOUVEAU)
  - Tests unitaires (optionnel mais recommandé)
  - ~50 lignes

---

## 💡 TIPS DE LECTURE

### ✅ Façon optimale
1. **Jour 1 matin :** Lire `RESUME_EXECUTIF_1PAGE.md` + `SCHEMAS_ARCHITECTURE_ASCII.md`
2. **Jour 1 après-midi :** Lire section JOUR 1–2 de `PLAN_IMPLEMENTATION_20h.md`
3. **Jours 2–8 :** Lancer code, revenir au `PLAN_IMPLEMENTATION_20h.md` ligne par ligne
4. **Si bloqué :** Lire `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` pour contexte

### ❌ À ÉVITER
- ❌ Lire AUDIT en premier (trop détaillé pour découvrir)
- ❌ Essayer de coder sans lire PLAN_IMPLEMENTATION (ambiguïté inutile)
- ❌ Lire tous les docs = perte de temps (prioritariser par besoin)

### 💾 Bookmark utiles (pour copy-paste rapide)
- `PLAN_IMPLEMENTATION_20h.md` → "Étape 1 : Ajouter extract_intent_query()"
- `PLAN_IMPLEMENTATION_20h.md` → "Étape 2 : Créer llm/sql_agent.py"
- `PLAN_IMPLEMENTATION_20h.md` → "Étape 3 : Refactor _ask_question()"

---

## 🎯 CHECKPOINTS JOUR PAR JOUR

| Jour | Checkpoint | Document ref | Status |
|------|-----------|--------------|--------|
| **1** | Décision: OUI/NON au plan | RESUME_EXECUTIF | 🟠 TODO |
| **2–3** | Commit v1: improve classify_intent() | PLAN_IMPLEMENTATION → Jour 1–2 | 🟠 TODO |
| **4–5** | Commit v2: validation.py | PLAN_IMPLEMENTATION → Jour 3–4 | 🟠 TODO |
| **6–7** | Commit v3: sql_agent.py + refactor | PLAN_IMPLEMENTATION → Jour 5–6 | 🟠 TODO |
| **8** | PR merged, 0 bug en prod | SCHEMAS_ARCHITECTURE → TEST MATRIX | 🟠 TODO |

---

## 📞 SI TU STUCKS

| Problème | Solution | Consulter |
|----------|----------|-----------|
| "Code ne compile pas" | Copiez exactement, pas d'interprétation | `PLAN_IMPLEMENTATION_20h.md` ligne exacte |
| "Test échoue" | Vérifier cas dans TEST MATRIX | `SCHEMAS_ARCHITECTURE_ASCII.md` → TEST MATRIX |
| "J'ai oublié pourquoi on fait ça" | Relire le bug | `RESUME_EXECUTIF_1PAGE.md` → TON VRAI PROBLÈME |
| "Effet de bord sur autre feature" | Vérifier architecture | `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` |
| "Les tokens Groq pas réduits" | Mesurer avant/après | `RESUME_EXECUTIF_1PAGE.md` → TOKENS GROQ |

---

## 🎁 LIVRABLES FINAL (JOUR 8)

Après avoir lu/codé tous les docs :
- ✅ Branch mergée `fix/interrogation-hallucination`
- ✅ 0 fausse entrée
- ✅ Tokens Groq -50%
- ✅ Tous les tests du "TEST MATRIX" passent
- ✅ Patch notes documentées (voir `PLAN_IMPLEMENTATION_20h.md` → "Documentation")

---

## 🚀 NEXT STEPS (Après Jour 8)

- **Jour 9–10 :** Optionnel — Dashboard FastAPI MVP
  - Lire `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` → Pilier 3
  - Lire `PLAN_IMPLEMENTATION_20h.md` → Jour 9 section

- **Mois 2–3 :** Ollama local + Photos + Tests auto
  - Lire `AUDIT_ARCHITECTURAL_ASSISTANT_POTAGER_v2.0.md` → BACKLOG FUTUR

---

## 📊 TEMPS DE LECTURE TOTAL

```
JOUR 1     : 1h 30 min lecture + 30 min setup
JOURS 2–8  : 30 min lect/jour (reference PLAN_IMPLEMENTATION) + 1h 30 code/jour
JOUR 9–10  : 2h lect (optionnel) + 5h code (optionnel)

LECTURE TOTALE = 6–7h
CODE TOTAL = 20h
─────────
EFFORT TOTAL = 26–27h (pour fix critique + dashboard bonus)
```

**Note :** Si tu SKIPS dashboard (optionnel) → 20h exactement

---

## 📎 RÉSUMÉ ONE-LINER PAR DOC

| Doc | One-liner |
|-----|-----------|
| **RESUME_EXECUTIF** | "Groq hallucine sur questions → créé fausses entrées → fix séparer ACTION/INTERROGATION → 0 bugs + -50% tokens" |
| **PLAN_IMPLEMENTATION_20h** | "Jour par jour, code exact à copier-coller, pas d'interprétation" |
| **AUDIT_ARCHITECTURAL** | "Contexte complet, pourquoi ça s'est passé, vision 3-6 mois" |
| **SCHEMAS_ARCHITECTURE_ASCII** | "Diagrammes avant/après, test cases, tokens comptabilité" |
| **CETTE INDEX** | "Navigation docs, programme lecture 10j, checkpoints" |

---

**Rédigé par :** Claude  
**Pour :** Emmanuel  
**Status :** 🟢 NAVIGATION COMPLÈTE  

**Conseil final :** Commence par RESUME_EXECUTIF (5 min) + SCHEMAS (10 min). Décide en 15 min. Puis PLAN_IMPLEMENTATION jour par jour. Audit = référence si doutes.

Bon courage ! 🚀
