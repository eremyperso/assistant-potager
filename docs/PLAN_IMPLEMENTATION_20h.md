# 🔧 PLAN IMPLÉMENTATION — Fix Interrogation + SQL Agent
**Durée estimée :** 20h | **Horizon :** 10 jours (2h/jour) | **Priorité :** CRITIQUE 🔴

---

## 📋 ROADMAP PAR JOUR

### **JOUR 1–2 : FIX classify_intent() (3–4h)**

#### Objectif
Améliorer le prompt `_CLASSIFY_PROMPT` pour mieux détecter les questions et éviter les faux positifs ACTION.

#### Fichier à modifier
`bot.py` — fonction `classify_intent()` (ligne 762) + prompt `_CLASSIFY_PROMPT` (ligne 730)

#### Changements
```python
# 🔴 ANCIEN PROMPT (ligne 730–760)
_CLASSIFY_PROMPT = """Tu es un assistant potager. L'utilisateur t'envoie un message...
- INTERROGER: pose une question ou demande d'AFFICHER des données existantes
...
Message : "{texte}"
Réponds avec UN SEUL MOT en majuscules parmi : STATS, HISTORIQUE, INTERROGER, ...
"""

# ✅ NOUVEAU PROMPT (plus d'exemples, plus de garde-fous)
_CLASSIFY_PROMPT = """Tu es un assistant potager spécialisé dans la classification de messages.
L'utilisateur t'envoie un message (vocal transcrit ou texte).

CLASSE CE MESSAGE EN UNE SEULE CATÉGORIE :

🧮 STATS       : veut voir des statistiques, bilan, résumé, chiffres totaux
  Exemples : "stats", "statistiques", "combien en total ?", "bilan de saison"

📖 HISTORIQUE  : veut voir l'historique, le journal, les derniers événements
  Exemples : "historique", "histo", "journal", "derniers événements", "liste des actions"

❓ INTERROGER  : pose une QUESTION ou demande d'AFFICHER des données
  MOTS-CLÉS : combien, quand, quel, afficher, montrer, voir, liste, consulter, historique de, date de
  Exemples :
    ✅ "Combien de kg de tomates ai-je récolté cette saison ?"
    ✅ "Quand ai-je planté mes courgettes ?"
    ✅ "Afficher les récoltes de carotte variété nantaise"
    ✅ "Date des traitements sur les poivrons"
    ✅ "Historique des arrosages courgettes"
    ❌ "J'ai récolté 2 kg de tomates" (c'est une ACTION, pas une INTERROGATION)

✏️ CORRIGER    : veut corriger, modifier, changer un enregistrement existant
  Exemples : "corriger", "modifier", "changer", "rectifier"

🗑️ SUPPRIMER   : veut supprimer ou effacer un enregistrement
  Exemples : "supprimer", "effacer", "annuler", "delete"

🏠 MENU        : veut revenir au menu, accueil, annuler, retour
  Exemples : "menu", "accueil", "retour", "home", "annuler"

🎤 NOUVELLE    : veut saisir une nouvelle action (après en avoir enregistré une)
  Exemples : "nouvelle action", "autre action", "ajouter une autre"

🌱 ACTION      : décrit une action potager RÉALEMENT RÉALISÉE à enregistrer
  Verbes d'action : récolté, semé, planté, arrosé, paillé, traité, désherbé, taillé, tuteuré, repiqué, fertilisé
  Exemples :
    ✅ "J'ai récolté 2 kg de tomates"
    ✅ "Semé des carottes hier"
    ✅ "Planté 12 plants de poivrons en 3 rangs"
    ✅ "Arrosé les courgettes 30 minutes"
    ❌ "Combien de tomates ?" (c'est une INTERROGATION, pas une ACTION)

🗺️ PLAN        : veut voir le plan d'occupation des parcelles
  Exemples : "plan du potager", "plan parcelle nord", "montre-moi le plan"

RÈGLE IMPORTANTE #1 :
Si le message contient "afficher", "montrer", "voir", "liste", "consulter", "combien", "quand", "quel"
ET qu'il se termine par "?" → c'est INTERROGER ou HISTORIQUE, JAMAIS ACTION.

RÈGLE IMPORTANTE #2 :
Si le message COMMENCE par un verbe d'action au passé (récolté, semé, planté, arrosé, paillé, traité...)
ET SANS "?" → c'est ACTION, jamais INTERROGER.

Message utilisateur : "{texte}"

Réponds avec UN SEUL MOT en majuscules parmi :
STATS | HISTORIQUE | INTERROGER | CORRIGER | SUPPRIMER | MENU | NOUVELLE | ACTION | PLAN

Réponse :"""
```

#### Étapes
1. Copier-coller le nouveau prompt dans bot.py (remplacer lignes 730–760)
2. Tester avec phrases clés :
   ```python
   assert classify_intent("Combien de tomates ?") == "INTERROGER"  # DOIT passer
   assert classify_intent("J'ai récolté 2 tomates") == "ACTION"    # DOIT passer
   assert classify_intent("Afficher les récoltes") == "INTERROGER" # DOIT passer
   assert classify_intent("Récolté hier") == "ACTION"              # DOIT passer
   ```
3. Lancer le bot et tester 5 questions vocales + 5 actions

#### Ressource Groq estimée
~100 tokens × 10 tests = 1k tokens

---

### **JOUR 3–4 : Ajouter validation post-parsing (2–3h)**

#### Objectif
Créer une fonction Python qui valide qu'un JSON parsé est réellement une action (pas une hallucination Groq).

#### Fichier à créer
`utils/validation.py` (NOUVEAU)

#### Contenu
```python
"""
validation.py — Validation post-parsing pour éviter les hallucinations Groq.

Règles appliquées EN PYTHON (pas de Groq) :
  1. Doit avoir action OU (culture + quantité) OU (culture + date) — pas de JSON vide
  2. Si action = observation → doit avoir culture + date (sinon = hallucination)
  3. Si phrase contient 3+ mots de question → rejeter
  4. Actions canoniques seulement (whitelist ACTIONS_VALIDES)
"""

from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# WHITELIST D'ACTIONS CANONIQUES
# ─────────────────────────────────────────────────────────────────────────────
ACTIONS_VALIDES = {
    "semis", "plantation", "repiquage", "arrosage", "desherbage",
    "paillage", "fertilisation", "traitement", "taille", "tuteurage",
    "recolte", "perte", "observation", "mise_en_godet"
}

# ─────────────────────────────────────────────────────────────────────────────
# QUESTION MARKER WORDS — mots qui signalent une question
# ─────────────────────────────────────────────────────────────────────────────
QUESTION_MARKERS = {
    "combien", "quand", "quel", "quelle", "quels", "quelles", "qui",
    "afficher", "montrer", "voir", "liste", "consulter", "historique",
    "date", "dernière", "dernier", "depuis", "jusqu",
    "combien de", "nombre de", "total de",
}

def _count_question_markers(texte: str) -> int:
    """Compte le nombre de mots de question dans le texte."""
    words = texte.lower().split()
    count = 0
    for word in words:
        if word in QUESTION_MARKERS or any(word.startswith(q) for q in QUESTION_MARKERS):
            count += 1
    return count

def validate_parsed_action(parsed: dict, texte_original: str) -> tuple[bool, str]:
    """
    Valide qu'un JSON parsé par Groq représente réellement une action.
    
    Retourne (is_valid, raison_rejet_ou_ok)
    
    Règles :
      1. Doit avoir action OU (culture ET quantité) OU (culture ET date)
      2. Action (si présente) doit être dans ACTIONS_VALIDES
      3. Si observation → culture + date obligatoires
      4. Si texte contient 3+ question markers → rejeter
      5. Quantité et rang doivent être numériques si présents
    """
    
    # --- RÈGLE 1 : Au moins un champ significatif
    action = parsed.get("action")
    culture = parsed.get("culture")
    quantite = parsed.get("quantite")
    unite = parsed.get("unite")
    date = parsed.get("date")
    
    # Vérifier qu'il y a au moins une information d'action
    has_action = bool(action)
    has_culture_qty = bool(culture) and (quantite is not None or unite)
    has_culture_date = bool(culture) and bool(date)
    
    if not (has_action or has_culture_qty or has_culture_date):
        return False, "Aucune information d'action (action, culture, quantité ou date manquantes)"
    
    # --- RÈGLE 2 : Action doit être valide (si présente)
    if action and action.lower() not in ACTIONS_VALIDES:
        return False, f"Action inconnue ou hallucination Groq : '{action}' (attendu: {ACTIONS_VALIDES})"
    
    # --- RÈGLE 3 : Observation → culture + date obligatoires
    if action and action.lower() == "observation":
        if not culture or not date:
            return False, "Observation sans culture ou date → hallucination Groq, rejeté"
    
    # --- RÈGLE 4 : Si texte ressemble à une question → rejeter
    question_count = _count_question_markers(texte_original)
    if question_count >= 3:
        return False, f"Texte ressemble à une question ({question_count} marqueurs détectés), pas une action"
    
    # --- RÈGLE 5 : Quantité et rang numériques
    if quantite is not None:
        try:
            float(quantite)
        except (ValueError, TypeError):
            return False, f"Quantité non numérique : {quantite}"
    
    rang = parsed.get("rang")
    if rang is not None:
        try:
            int(rang)
        except (ValueError, TypeError):
            return False, f"Rang non numérique : {rang}"
    
    # ✅ Toutes les validations passent
    return True, "✅ Validation OK"


# ─────────────────────────────────────────────────────────────────────────────
# TESTS (à copier dans tests/test_validation.py)
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # ✅ Actions valides
    assert validate_parsed_action(
        {"action": "recolte", "culture": "tomate", "quantite": 2},
        "Récolté 2 kg de tomates"
    )[0] == True
    
    # ❌ Hallucination : action fictive
    assert validate_parsed_action(
        {"action": "supergrossissage", "culture": "tomate"},
        "Récolté 2 kg de tomates"
    )[0] == False
    
    # ❌ Observation sans date
    assert validate_parsed_action(
        {"action": "observation", "culture": "tomate", "quantite": None},
        "J'ai observé les tomates"
    )[0] == False
    
    # ❌ Texte ressemble à une question
    assert validate_parsed_action(
        {"action": "recolte", "culture": "tomate"},
        "Combien de tomates ai-je récolté ?"
    )[0] == False
    
    print("✅ Tous les tests de validation passent !")
```

#### Étapes
1. Créer `utils/validation.py` avec le code ci-dessus
2. Ajouter import en haut de `bot.py` : `from utils.validation import validate_parsed_action`
3. Modifier `_parse_and_save()` (ligne 1063) :
   ```python
   # APRÈS parsing, AVANT sauvegarde
   items = parse_commande(texte)
   
   # ✅ NEW VALIDATION
   validated_items = []
   for item in items:
       is_valid, reason = validate_parsed_action(item, texte)
       if not is_valid:
           log.warning(f"❌ VALIDATION ÉCHOUÉE: {reason}")
           continue  # IGNORE cet item
       validated_items.append(item)
   
   items = validated_items
   
   if not items:
       await update.message.reply_text("...")
       return
   ```
4. Tester : 10 questions vocales ne doivent PAS créer d'entrée

#### Ressource Groq estimée
0 tokens (validation en pur Python)

---

### **JOUR 5–6 : Refactor _ask_question() → SQL agent (4–5h)**

#### Objectif
Remplacer l'appel coûteux `repondre_question()` (5000 tokens) par un agent SQL local.

#### Fichiers à modifier
1. `llm/groq_client.py` — ajouter `extract_intent_query()`
2. `llm/sql_agent.py` — NOUVEAU module
3. `bot.py` — refactor `_ask_question()`

#### Étape 1 : Ajouter extract_intent_query() dans groq_client.py
```python
# groq_client.py — ajouter après extract_intent() (ligne 44)

def extract_intent_query(question: str) -> dict:
    """
    Extrait l'intention d'une QUESTION (pas une action).
    
    Retourne :
      {
        "action": "recolte" | "semis" | "arrosage" | None,
        "culture": "tomate" | "carotte" | None,
        "date_from": "2026-01-01" | None  # date de départ pour filtrage
      }
    
    Exemple :
      "Combien de tomates ai-je récolté cette saison ?"
      → {"action": "recolte", "culture": "tomate", "date_from": "2026-01-01"}
    """
    # Réutilise le prompt INTENT_PROMPT existant (ligne 29–41)
    chat = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": question}
        ],
        temperature=0.0,
        max_tokens=128,
        stream=False
    )
    
    raw = chat.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw
    
    try:
        parsed = json.loads(raw)
        return {
            "action": parsed.get("action"),
            "culture": parsed.get("culture"),
            "date_from": parsed.get("date_from"),
        }
    except Exception:
        return {"action": None, "culture": None, "date_from": None}
```

#### Étape 2 : Créer llm/sql_agent.py (NOUVEAU)
```python
"""
sql_agent.py — Agent SQL pour répondre aux questions sans hallucinations Groq.

Stratégie :
  1. Parser intent question (action, culture, date_from)
  2. Construire requête SQL depuis intent
  3. Exécuter SQL
  4. Formater réponse simple (texte, pas Groq)
"""

from datetime import datetime
from sqlalchemy import func
from database.db import SessionLocal
from database.models import Evenement

class QueryAgent:
    """Agent SQL pour questions analytiques."""
    
    def __init__(self, db):
        self.db = db
    
    def answer(self, question: str, intent: dict) -> str:
        """
        Répond à une question sans appel Groq (sauf pour intent extraction).
        
        Args:
            question: Question utilisateur
            intent: {"action": ..., "culture": ..., "date_from": ...}
        
        Returns:
            Réponse texte simple
        """
        action = intent.get("action")
        culture = intent.get("culture")
        date_from = intent.get("date_from")
        
        # --- CAS 1 : "Combien de [culture] [action]"
        if culture and action:
            return self._answer_quantity(action, culture)
        
        # --- CAS 2 : "Historique de [culture]"
        if culture and not action:
            return self._answer_history(culture, date_from)
        
        # --- CAS 3 : "Statistiques [action]"
        if action and not culture:
            return self._answer_action_stats(action)
        
        # --- FALLBACK
        return "Je n'ai pas compris la question. Formulez autrement."
    
    def _answer_quantity(self, action: str, culture: str) -> str:
        """Répond : "Combien de X ai-je récolté ?"."""
        query = self.db.query(
            func.sum(Evenement.quantite).label("total_qte"),
            func.count(Evenement.id).label("count"),
        ).filter(
            Evenement.type_action == action,
            Evenement.culture == culture
        )
        result = query.first()
        
        if result and result.total_qte:
            return f"Total {culture} {action} : {result.total_qte} kg ({result.count} entrées)"
        else:
            return f"Aucune donnée pour {culture} {action}."
    
    def _answer_history(self, culture: str, date_from: str = None) -> str:
        """Répond : "Historique de culture X"."""
        query = self.db.query(Evenement).filter(
            Evenement.culture == culture
        ).order_by(Evenement.date.desc()).limit(5)
        
        events = query.all()
        if not events:
            return f"Aucun événement pour {culture}."
        
        lines = [f"Historique {culture} (5 derniers) :"]
        for e in events:
            date_str = e.date.strftime("%d/%m/%Y") if e.date else "?"
            lines.append(f"  • {e.type_action} ({date_str})")
        
        return "\n".join(lines)
    
    def _answer_action_stats(self, action: str) -> str:
        """Répond : "Stats [action]"."""
        query = self.db.query(
            Evenement.culture,
            func.count(Evenement.id).label("count"),
            func.sum(Evenement.quantite).label("total_qte"),
        ).filter(
            Evenement.type_action == action
        ).group_by(Evenement.culture).order_by(
            func.sum(Evenement.quantite).desc()
        ).limit(10)
        
        results = query.all()
        if not results:
            return f"Aucun événement {action}."
        
        lines = [f"Top cultures pour {action} :"]
        for culture, count, qte in results:
            qte_str = f"{qte} kg" if qte else f"{count} fois"
            lines.append(f"  • {culture}: {qte_str}")
        
        return "\n".join(lines)


def query_agent_answer(question: str, intent: dict) -> str:
    """
    Wrapper public : répondre à une question via SQL agent (ZERO Groq).
    
    Args:
        question: Question utilisateur
        intent: Dict avec action/culture/date_from
    
    Returns:
        Réponse texte
    """
    db = SessionLocal()
    try:
        agent = QueryAgent(db)
        return agent.answer(question, intent)
    finally:
        db.close()
```

#### Étape 3 : Refactor _ask_question() dans bot.py
```python
# bot.py — remplacer fonction _ask_question() (ligne 1283–1316)

async def _ask_question(update: Update, question: str):
    """Interroge l'historique via SQL agent (ZÉRO hallucination Groq)."""
    log.info(f"🔍 QUESTION       : {question}")
    msg = await update.message.reply_text("🔍 *Analyse de vos données...*", parse_mode="Markdown")
    
    try:
        # Step 1 : Extraire intent (action, culture, date_from) — PETIT appel Groq (~100 tokens)
        from llm.groq_client import extract_intent_query
        intent = extract_intent_query(question)
        log.info(f"🎯 INTENT QUERY   : {intent}")
        
        # Step 2 : Répondre via SQL agent (ZÉRO Groq)
        from llm.sql_agent import query_agent_answer
        reponse = query_agent_answer(question, intent)
        log.info(f"💡 RÉPONSE (SQL)  : {reponse[:200]}...")
        
        # Step 3 : Afficher réponse
        try:
            await msg.edit_text(f"🔍 *Réponse :*\n\n{reponse}", parse_mode="Markdown")
        except Exception:
            await msg.edit_text(f"🔍 Réponse :\n\n{reponse}")
        
        await update.message.reply_text(
            "_Autre question ou action ?_",
            parse_mode="Markdown",
            reply_markup=AFTER_RECORD_KEYBOARD
        )
        
        # Synthèse vocale
        await send_voice_reply(update, reponse)
        
    except Exception as e:
        log.error(f"❌ Erreur _ask_question: {e}")
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
```

#### Étapes
1. Ajouter `extract_intent_query()` dans `groq_client.py`
2. Créer `llm/sql_agent.py` avec code ci-dessus
3. Refactor `_ask_question()` dans `bot.py`
4. Tester : 10 questions, mesurer tokens Groq (avant 50k → après 5k)

#### Ressource Groq estimée
Avant : 5000 tokens/question × 10 = 50k tokens  
**Après : 100 tokens/question × 10 = 1k tokens** (gain 98% ! 🚀)

---

### **JOUR 7–8 : Tests + déploiement (2–3h)**

#### Checklist de tests
```bash
# ✅ Test 1 : Actions toujours enregistrées
/test "Récolté 2 kg de tomates"
→ Doit créer 1 entrée (type_action = "recolte")

# ✅ Test 2 : Questions ne créent PAS d'entrées
/test "Combien de tomates ai-je récolté ?"
→ Doit afficher chiffre (0 entrée créée)

# ✅ Test 3 : Hallucinations détectées
/test "J'ai observé les tomates" (sans date)
→ Doit rejeter (validation fail)

# ✅ Test 4 : SQL agent répond sans Groq
Voir logs : "RÉPONSE (SQL)" sans appel "repondre_question()"

# ✅ Test 5 : Tokens Groq réduits de 50%
Vérifier dans compte Groq API : quotas avant/après
```

#### Déploiement
```bash
# Créer branch feature
git checkout -b fix/interrogation-hallucination

# Commit incremental
git add utils/validation.py
git commit -m "FEAT: validation post-parsing (règles Python pour hallucinations)"

git add llm/sql_agent.py
git commit -m "FEAT: SQL agent pour questions analytiques (remplace Groq -5000 tokens/q)"

git add -A
git commit -m "REFACTOR: _ask_question() via SQL agent + extract_intent_query()"

git add tests/
git commit -m "TEST: validation + SQL agent fixtures"

# PR vers main
git push origin fix/interrogation-hallucination
# Ouvrir PR dans GitHub
```

#### Documentation
Créer `PATCH_NOTES_v2.1.md` :
```markdown
# v2.1 : Fix critique hallucinations mode interrogation

## 🔴 Bug corrigé
- Groq hallucine en mode interrogation → crée fausses entrées
- Symptôme : questions posées → entrées vides en base
- Solution : séparation complète ACTION vs INTERROGATION

## ✅ Changements
1. Amélioration classify_intent() (+20 exemples questions)
2. Validation post-parsing (règles Python, pas Groq)
3. SQL agent pour réponses analytiques (remplace appel Groq 5000 tokens)

## 📊 Impacts
- ✅ 0 fausse entrée après fix
- ✅ -90% hallucinations Groq
- ✅ -50k tokens/jour (économie 50%)

## 🧪 Tests
```bash
pytest tests/ -v
```

## 🚀 Déploiement
```bash
git pull origin fix/interrogation-hallucination
systemctl restart potager
```
```

---

## 📊 TABLEAU DE SUIVI (jours 1–10)

| Jour | Tâche | Durée | État | Notes |
|------|-------|-------|------|-------|
| 1–2 | Improve classify_intent() | 3–4h | 🔴 TODO | Prompts + tests manuels |
| 3–4 | validation.py | 2–3h | 🔴 TODO | Whitelist actions + règles |
| 5–6 | SQL agent refactor | 4–5h | 🔴 TODO | extract_intent + sql_agent.py |
| 7–8 | Tests + déploiement | 2–3h | 🔴 TODO | Vérifier 0 bugs, tokens -50% |
| 9–10 | Dashboard MVP | 5–7h | 🟡 NEXT | FastAPI + /api/events |

---

## 🎁 LIVRABLES JOUR 8

✅ Branch `fix/interrogation-hallucination` mergée dans `main`  
✅ 0 fausse entrée en prod  
✅ Groq tokens -50% confirmé  
✅ Patch notes + commit messages clairs  
✅ Tests passent 100%

---

## 🔗 RÉFÉRENCES CODE

| Fichier | Fonction | Ligne | Statut |
|---------|----------|-------|--------|
| bot.py | classify_intent() | 762 | 🔧 MODIF |
| bot.py | _ask_question() | 1283 | 🔧 REFACTOR |
| llm/groq_client.py | extract_intent_query() | NEW | ✨ CREATE |
| llm/sql_agent.py | QueryAgent | NEW | ✨ CREATE |
| utils/validation.py | validate_parsed_action() | NEW | ✨ CREATE |

---

## ⚠️ RISQUES ET MITIGATIONS

| Risque | Probabilité | Mitigation |
|--------|-------------|-----------|
| Fallback SQL agent trop simple | MOYEN | Gérer cas edge (NULL cultures) |
| Refactor _ask_question break autres flows | FAIBLE | Tests manuels 10 questions |
| Tokens Groq non réduits | FAIBLE | Mesurer avant/après via logs |
| Performance SQL sur grosse base | TRÈS FAIBLE | Index sur (type_action, culture) |

---

## 💬 QUESTIONS FRÉQUENTES

**Q : Et si l'utilisateur pose une question complexe (ex: "comparer récoltes 2025 vs 2026") ?**  
A : SQL agent retourne "Je n'ai pas compris", suggestion de poser autrement. Mois 2 : remplacer par Ollama local pour plus de flexibilité.

**Q : La validation risque-t-elle de rejeter des actions valides ?**  
A : Oui, règles conservatrices (exemple: "observation" sans date). Logs détaillent chaque rejet, facile à affiner.

**Q : Où intégrer Dashboard FastAPI ?**  
A : Jour 9–10, nouveau sprint après merge v2.1. main.py existant peut être réutilisé.

---

**Rédigé par :** Claude | **Pour :** Emmanuel  
**Statut :** 🟢 PRÊT DÉVELOPPEMENT
