# Audit de la passerelle LLM unique — US-092

> *Le LLM est la ressource de dernier recours, pas le moteur central.*
> La passerelle `llm/passerelle.py` est l'endroit qui rend ce principe mesurable.

Ce document porte les deux livrables documentaires de l'US : l'**audit du point
de passage unique** (CA1) et le **relevé de consommation avant / après** (CA7).

---

## 1. Audit du point de passage unique (CA1)

### Comment il est exécuté

```bash
python tools/audit_appels_llm.py     # sortie 0 si conforme, 1 sinon
```

L'audit analyse l'**AST** de chaque fichier `.py` du code applicatif — pas son
texte : une mention de « Groq » dans un commentaire ou une chaîne n'est pas un
appel, et un audit qui crie au loup finit ignoré. Il relève quatre motifs :
import du SDK `groq`, instanciation `Groq(...)`, `chat.completions.create(...)`,
`audio.transcriptions.create(...)`.

Sont hors périmètre : `llm/passerelle.py` (le point de passage autorisé),
l'auditeur lui-même, `tests/` (y mocker le client est le comportement attendu),
`.venv/`, `frontend/` et les caches.

Le même audit est rejoué par
`tests/test_us092_passerelle_llm.py::TestCA1AuditPointDePassageUnique`, avec
quatre tests de garde : l'audit **détecte réellement** une infraction sur un
extrait de code fabriqué (il ne peut pas devenir tautologique), il ne produit
pas de faux positif sur de la prose, `bot.py` / `main.py` / `groq_client.py`
sont bien dans le périmètre analysé, et un fichier qu'il n'arrive pas à parser
est **signalé** plutôt que déclaré conforme par défaut.

> Ce dernier point n'est pas théorique : `bot.py` porte un BOM UTF-8 hérité.
> Lu en `utf-8` strict, il ne se parsait pas — l'audit le sautait en silence et
> restait vert en ignorant le plus gros fichier appelant du projet. L'auditeur
> lit donc en `utf-8-sig`, et une erreur de parsing est désormais une
> infraction à part entière.

### Résultat à la livraison

```
✅ [US-092 / CA1] Aucun appel direct au fournisseur de modèles hors de llm/passerelle.py.
```

### Ce qui a été déplacé

| Emplacement d'origine | Nature de l'appel | Type déclaré désormais |
|---|---|---|
| `llm/groq_client.py` — `extract_intent`, `extract_intent_query_mesuree` | client module-level `_client` | `question` |
| `llm/groq_client.py` — `parse_commande`, `parse_message`, `extract_note_fields` | client module-level `_client` | `parsing` |
| `llm/groq_client.py` — `repondre_question` | client module-level `_client` | `synthese` |
| `llm/groq_client.py` — `classify_intent_pwa` | client module-level `_client` | `classification` |
| `llm/groq_client.py` — `transcribe_audio` | client module-level `_client` (Whisper) | `transcription` |
| `bot.py` — `handle_voice` | client global `groq_client` (Whisper) | `transcription` |
| `bot.py` — `classify_intent` | `Groq(...)` instancié dans la fonction | `classification` |
| `bot.py` — `_find_candidates` | `Groq(...)` instancié dans la fonction | `parsing` |
| `bot.py` — `_corr_apply` | `Groq(...)` instancié dans la fonction | `parsing` |

Trois clients Groq distincts coexistaient donc, dont deux créés à chaque appel.
Le garde-fou `reasoning_effort` (correctif du bug id=357) n'existait que dans
deux d'entre eux ; il est désormais appliqué une seule fois, dans la passerelle.

---

## 2. Relevé de consommation avant / après (CA7)

### Méthode

La passerelle journalise chaque appel — type, modèle, potager, jetons entrants,
sortants, jetons de cache, latence, issue — et écrit la même mesure dans
`conso_tokens`. Le relevé ci-dessous compare les budgets **avant** (appels
directs, mesure inexistante hors du compteur ponctuel d'US-042) et **après**
(passerelle), à comportement constant.

### Ordre de grandeur, par type d'appel

| Type | Appel | Budget `max_tokens` avant | Après | Écart |
|---|---|---|---|---|
| `classification` | `classify_intent_pwa` | 100 | 100 | néant |
| `classification` | `classify_intent` (bot) | 10 | 10 | néant |
| `parsing` | `parse_commande` | 1024 | 1024 | néant |
| `parsing` | `parse_message` | 1024 | 1024 | néant |
| `parsing` | `extract_note_fields` | 256 | 256 | néant |
| `parsing` | `_find_candidates` | 200 | 200 | néant |
| `parsing` | `_corr_apply` | 300 | 300 | néant |
| `question` | `extract_intent_query_mesuree` | 128 | 128 | néant |
| `synthese` | `repondre_question` | 200 | 200 | néant |
| `transcription` | Whisper (bot + PWA) | s.o. (facturé à la seconde d'audio) | s.o. | néant |

**Conclusion : l'écart nominal est nul, et c'est le résultat attendu.** L'US
est une réorganisation à comportement constant — mêmes prompts, mêmes modèles,
mêmes budgets. Ce qui change n'est pas la consommation, c'est le fait qu'elle
soit désormais *connue* : avant cette US, la seule mesure existante était le
compteur ponctuel d'US-042 sur `repondre_question` (cible < 1500 jetons/appel),
et rien n'était imputé à un potager.

### Le vrai levier : le cache de prompt (CA6)

Le gain de capacité ne vient pas d'une réduction des prompts mais du cache du
fournisseur, rendu applicable par l'ordre d'assemblage imposé par la passerelle
(partie fixe en tête, variables en fin, message utilisateur en dernier).

Trois prompts ont été réordonnés pour cela, sans changer leur contenu :

* `_NOTE_FIELDS_PROMPT` — la catégorie de note, qui change à chaque appel,
  passait au milieu de la consigne ; elle est déplacée en fin de consigne ;
* `_find_candidates` — la description dictée était enchâssée en tête du prompt ;
  elle devient le message utilisateur, en dernier ;
* `_corr_apply` — l'événement à corriger et la demande de l'utilisateur
  ouvraient le prompt ; ils le ferment désormais.

Les prompts `PARSE_PROMPT`, `_PARSE_MESSAGE_PROMPT` et `INTENT_PROMPT` gardent
leur bloc de dates relatives (« hier », « avant-hier ») en tête : ces valeurs ne
changent qu'une fois par jour, très au-delà de la durée de vie du cache du
fournisseur, donc le préfixe reste stable à l'échelle où le cache opère.

Les jetons servis depuis ce cache sont stockés à part (`conso_tokens.tokens_cache`)
dès que le fournisseur les expose, ce qui rendra le gain lisible sans nouvelle
instrumentation.

---

## 3. Ce que cette US ne fait pas

* **Aucun plafond, aucun budget, aucun blocage.** La table `conso_tokens` mesure ;
  les quotas par potager et le message d'incitation à l'abonnement relèvent de
  l'US de quotas, qui disposera ainsi d'un mois de données réelles avant qu'un
  prix soit fixé.
* **Aucun repli d'un modèle vers un autre.** En cas de 429 on dégrade
  fonctionnellement (CA9) ; rejouer l'appel en douce sur un autre modèle
  masquerait précisément la saturation que cette US existe pour rendre visible.
* **Aucun BYOK.** `_resoudre_client()` est le point d'extension prévu (US-143) ;
  il retourne aujourd'hui toujours le client plateforme.

---

## 4. Exploitation de la mesure

```sql
-- Consommation d'un potager sur le mois courant, par type d'appel
SELECT appel_type, modele,
       SUM(tokens_in)  AS jetons_entrants,
       SUM(tokens_out) AS jetons_sortants,
       SUM(tokens_cache) AS jetons_caches,
       COUNT(*) FILTER (WHERE issue <> 'ok') AS echecs
FROM conso_tokens
WHERE potager_id = :potager_id
  AND date >= date_trunc('month', CURRENT_DATE)
GROUP BY appel_type, modele
ORDER BY jetons_entrants DESC;

-- Saturation : quel type d'appel encaisse les 429 ?
SELECT date, appel_type, modele, COUNT(*) AS nb_429
FROM conso_tokens
WHERE issue = 'quota'
GROUP BY date, appel_type, modele
ORDER BY date DESC;
```
