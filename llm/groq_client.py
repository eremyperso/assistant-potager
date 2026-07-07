"""
groq_client.py — LLM Groq pour parsing et questions
----------------------------------------------------
Corrections v2.1 :
  - Date réelle extraite (hier, avant-hier, lundi dernier...)
  - Détection phrases multiples → liste de JSONs
v2.24 :
  - transcribe_audio() — Whisper côté serveur pour la PWA
  - classify_intent_pwa() — ACTION vs INTERROGER (PWA /voice)
"""
import json
import os
import re
import tempfile
from datetime import date, timedelta
from groq import Groq
from config import GROQ_API_KEY, GROQ_MODEL, GROQ_WHISPER_MODEL, GROQ_REASONING_EFFORT

_client = Groq(api_key=GROQ_API_KEY)

# Passé aux appels chat.completions.create() — vide pour les modèles non-reasoning
# (ex: llama-3.3-70b-versatile), où l'API Groq rejette ce paramètre.
_REASONING_KWARGS = {"reasoning_effort": GROQ_REASONING_EFFORT} if GROQ_REASONING_EFFORT else {}

# ── Date du jour injectée dans le prompt ──────────────────────────────────────
def _today_context() -> str:
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    return (
        f"Aujourd'hui nous sommes le {today.strftime('%A %d %B %Y')} "
        f"({today.isoformat()}). "
        f"Hier = {yesterday.isoformat()}. "
        f"Avant-hier = {day_before.isoformat()}."
    )


INTENT_PROMPT = """Tu es un assistant potager spécialisé dans l'analyse de questions en langage naturel.
Donne uniquement du JSON sans texte additionnel, sans guillemets, avec ces champs:
{
  "action": "semis|plantation|arrosage|recolte|repiquage|traitement|desherbage|taille|paillage|observation|perte|null",
  "culture": string|null,
  "date_from": string|null,
  "query_type": "date|quantite|historique|stats"
}

Règles pour query_type :
- "date"      : question sur QUAND un événement a eu lieu (mots-clés : quand, à quelle date, date de, dernière fois)
- "quantite"  : question sur COMBIEN (mots-clés : combien, total, poids, kg, quantité)
- "historique": liste des événements d'une culture ou période (mots-clés : historique, liste, voir mes, afficher)
- "stats"     : classement ou bilan global sans culture précise (mots-clés : top, bilan, le plus, résumé)

Exemples :
"quels légumes ai-je le plus récoltés en kg ?" -> {"action":"recolte","culture":null,"date_from":null,"query_type":"stats"}
"arrosage courgettes cette semaine" -> {"action":"arrosage","culture":"courgette","date_from":"2026-03-19","query_type":"historique"}
"quand ai-je semé des carottes ?" -> {"action":"semis","culture":"carotte","date_from":null,"query_type":"date"}
"à quelle date la plantation de butternut ?" -> {"action":"plantation","culture":"butternut","date_from":null,"query_type":"date"}
"dernière récolte de blette ?" -> {"action":"recolte","culture":"blette","date_from":null,"query_type":"date"}
"combien de tomates ai-je récolté ?" -> {"action":"recolte","culture":"tomate","date_from":null,"query_type":"quantite"}
"mes récoltes de blette ce mois-ci" -> {"action":"recolte","culture":"blette","date_from":null,"query_type":"historique"}
""" 


def extract_intent_query(question: str) -> dict:
    """
    [US-012] Extrait l'intention d'une question analytique (~100 tokens Groq).

    Retourne {"action": ..., "culture": ..., "date_from": ...}.
    Alias orienté questions — utilise le même INTENT_PROMPT qu'extract_intent().
    """
    return extract_intent(question)


def extract_intent(question: str) -> dict:
    chat = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": INTENT_PROMPT},
            {"role": "user", "content": question}
        ],
        temperature=0.0,
        max_tokens=128,
        stream=False,
        **_REASONING_KWARGS
    )

    raw = chat.choices[0].message.content.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    try:
        parsed = json.loads(raw)
    except Exception as e:
        # fallback conservatif
        return {"action": None, "culture": None, "date_from": None}

    # normalisation des clés
    return {
        "action":     parsed.get("action"),
        "culture":    parsed.get("culture"),
        "date_from":  parsed.get("date_from"),
        "query_type": parsed.get("query_type", "quantite"),
    }

# ─────────────────────────────────────────────────────────────────────────────
# PROMPT PARSING — retourne UN ou PLUSIEURS JSONs selon la phrase
# ─────────────────────────────────────────────────────────────────────────────
PARSE_PROMPT = """Tu es un extracteur de données pour un potager maraîcher français.
{date_context}

Analyse la phrase et retourne UNIQUEMENT un JSON avec les informations extraites.
Si une information n'est pas mentionnée, mets null. Ne jamais inventer.

Champs à extraire :
{{
  "action"           : string,   // recolte | semis | repiquage | arrosage | fertilisation | traitement | desherbage | taille | paillage | observation | plantation | tuteurage | perte | mise_en_godet | vendu | perte_godet
  "culture"          : string,   // légume au singulier minuscule ("tomates" → "tomate")
  "variete"          : string,   // variété ou couleur ("rouge", "nantaise"...)
  "quantite"         : number,   // quantité numérique (PAR RANG si rang mentionné)
  "unite"            : string,   // kg | g | l | plants | graines
  "parcelle"         : string,   // localisation (nord, sud, carré sud, serre...)
  "rang"             : number,   // NOMBRE de rangs (pas un identifiant). "3 rangs" → 3
  "duree_minutes"    : number,   // durée en minutes
  "traitement"       : string,   // produit utilisé (purin d ortie, compost...)
  "date"             : string,   // date ISO si mentionnée : "hier"→{yesterday}, "aujourd'hui"→{today_iso}, "avant-hier"→{day_before}
  "commentaire"      : string,   // toute autre observation utile
  "nb_graines_semees": number,   // pour mise_en_godet UNIQUEMENT : nb total de graines dans la barquette d'origine (optionnel, sert au taux de réussite)
  "nb_plants_godets" : number    // pour mise_en_godet UNIQUEMENT : nb de plantules/plants repiqués en godet (champ PRINCIPAL — jamais des graines)
}}

RÈGLE mise_en_godet : c'est le REPIQUAGE de plantules déjà levées (tige visible) vers un godet individuel.
On ne met JAMAIS des graines directement en godet. Si l'utilisateur dit "X graines en godet" → interpréter X comme des plants (nb_plants_godets=X, nb_graines_semees=null).
Différence clé : semis = graines dans barquette pour germer | mise_en_godet = plants levés vers godet.

RÈGLE récolte double quantité (pièces + poids) : si une récolte mentionne À LA FOIS un NOMBRE DE PIEDS/PLANTS ET un POIDS (ex : "2 betteraves pour 250 grammes", "récolté 3 salades, 600g au total"), NE JAMAIS additionner ces deux valeurs. Retourner DEUX objets recolte distincts dans un tableau :
- un avec quantite=nombre de pieds et unite="plants"
- un avec quantite=poids et unite="kg" ou "g"
Si seul un nombre de pieds OU seul un poids est mentionné (cas normal), un seul objet recolte suffit comme d'habitude.

Exemples :
"J'ai paillé les tomates hier"
→ {{"action":"paillage","culture":"tomate","date":"{yesterday}","quantite":null,"unite":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"variete":null,"commentaire":null}}

"récolté 2 kg de tomates hier parcelle nord"
→ {{"action":"recolte","culture":"tomate","quantite":2,"unite":"kg","date":"{yesterday}","parcelle":"nord","rang":null,"duree_minutes":null,"traitement":null,"variete":null,"commentaire":null}}

"arrosage carré sud pendant 20 minutes"
→ {{"action":"arrosage","culture":null,"quantite":null,"unite":null,"date":null,"parcelle":"carré sud","rang":null,"duree_minutes":20,"traitement":null,"variete":null,"commentaire":null}}

"planter 10 choux-fleurs sur 3 rangs parcelle nord"
→ {{"action":"plantation","culture":"chou-fleur","quantite":10,"unite":"plants","date":null,"parcelle":"nord","rang":3,"duree_minutes":null,"traitement":null,"variete":null,"commentaire":null}}

"traitement purin d'ortie sur les courgettes hier"
→ {{"action":"traitement","culture":"courgette","quantite":null,"unite":null,"date":"{yesterday}","parcelle":null,"rang":null,"duree_minutes":null,"traitement":"purin d ortie","variete":null,"commentaire":null}}

"semé des carottes nantaises parcelle est"
→ {{"action":"semis","culture":"carotte","quantite":null,"unite":null,"date":null,"parcelle":"est","rang":null,"duree_minutes":null,"traitement":null,"variete":"nantaise","commentaire":null}}

"J'ai perdu 3 plants de tomates à cause du gel"
→ {{"action":"perte","culture":"tomate","quantite":3,"unite":"plants","date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"variete":null,"commentaire":"gel"}}

"J'ai planté 15 oignons blancs et 10 radis hier"
→ [{{"action":"plantation","culture":"oignon","variete":"blanc","quantite":15,"unite":"plants","date":"{yesterday}","parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null}},{{"action":"plantation","culture":"radis","variete":null,"quantite":10,"unite":"plants","date":"{yesterday}","parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null}}]

"récolté 2 betteraves pour 250 grammes"
→ [{{"action":"recolte","culture":"betterave","variete":null,"quantite":2,"unite":"plants","date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null}},{{"action":"recolte","culture":"betterave","variete":null,"quantite":250,"unite":"g","date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null}}]

"Mis en godet 24 tomates cerise sur 30 graines semées"
→ {{"action":"mise_en_godet","culture":"tomate","variete":"cerise","quantite":null,"unite":null,"date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null,"nb_graines_semees":30,"nb_plants_godets":24}}

"mise en godet de 10 graines de courgette jaune"
→ {{"action":"mise_en_godet","culture":"courgette","variete":"jaune","quantite":null,"unite":null,"date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null,"nb_graines_semees":null,"nb_plants_godets":10}}

"repiquer 15 plants de poivron en godet"
→ {{"action":"mise_en_godet","culture":"poivron","variete":null,"quantite":null,"unite":null,"date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null,"nb_graines_semees":null,"nb_plants_godets":15}}

"vendu 5 tomates cerise à un ami"
→ {{"action":"vendu","culture":"tomate","variete":"cerise","quantite":5,"unite":"plants","date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null}}

"perdu 3 cornichons en godet"
→ {{"action":"perte_godet","culture":"cornichon","variete":null,"quantite":3,"unite":"plants","date":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"commentaire":null}}

Retourne UNIQUEMENT le JSON brut, sans texte ni backticks.
Si plusieurs cultures dans la même phrase → tableau de JSONs.
"""

def parse_commande(texte: str) -> list[dict]:
    """
    Parse une commande vocale.
    Retourne TOUJOURS une liste de dicts (1 élément ou plusieurs).
    """
    today      = date.today()
    yesterday  = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    prompt = PARSE_PROMPT.format(
        date_context = _today_context(),
        today_iso    = today.isoformat(),
        yesterday    = yesterday.isoformat(),
        day_before   = day_before.isoformat(),
    )

    chat = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user",   "content": texte}
        ],
        temperature=0.0,
        max_tokens=1024,
        stream=False,
        **_REASONING_KWARGS
    )
    raw = chat.choices[0].message.content.strip()

    # Nettoyage backticks éventuels
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

    parsed = json.loads(raw.strip())

    # Normaliser : toujours retourner une liste
    if isinstance(parsed, dict):
        return [parsed]
    elif isinstance(parsed, list):
        return parsed
    else:
        return [parsed]


# ─────────────────────────────────────────────────────────────────────────────
# PROMPT ANALYTIQUE
# ─────────────────────────────────────────────────────────────────────────────
QUERY_PROMPT = """Tu es l'assistant potager d'un jardinier. Aujourd'hui : {today_iso}.

REGLE ABSOLUE - REPONSE DIRECTE UNIQUEMENT :
Donne SEULEMENT le resultat final. Pas de raisonnement, pas de calculs intermediaires,
pas d'introduction, pas de conclusion. Une ou deux phrases maximum.

EXEMPLES DE BONNES REPONSES :
Q: "Combien de plants de tomates en tout ?"
R: "42 plants de tomates au total (30 coeur de boeuf + 12 classiques)."

Q: "Quel legume a le plus produit en kg ?"
R: "La tomate avec 15 kg, suivie de la courgette avec 8 kg."

Q: "Quand ai-je arrose les courgettes pour la derniere fois ?"
R: "Dernier arrosage courgettes : 9 mars 2026."

Q: "Historique des traitements ?"
R: "2 traitements : savon noir sur courgettes (5 mars), bouillie bordelaise sur tomates (10 mars)."

Si une liste est necessaire : tirets courts uniquement, pas de paragraphes.
Si donnee absente : "Pas de donnees enregistrees pour cela."
Ne jamais inventer de donnees. Utilise UNIQUEMENT les donnees fournies.

REGLE CALCUL PLANTATIONS :
- Quantite totale = quantite x rang (si rang present), sinon quantite seule.
- Afficher UNIQUEMENT le total final, jamais les calculs intermediaires entre parentheses.
- Exemple correct  : "- tomate : 42 plants"
- Exemple INTERDIT : "- tomate : 42 plants (10 x 3 + 4 x 3)"

REGLE CALCUL STOCK REEL :
- Stock reel = plantations totales - pertes totales - récoltes totales pour chaque culture.
- Afficher : "culture : X plants (plante Y, perdu Z, récolté W)"
- Si pas de pertes ou récoltes : ajuster l'affichage en conséquence.
- Exemple : "salade : 19 plants (planté 25, perdu 4, récolté 2)"
"""

def repondre_question(question: str, contexte_json: str) -> str:
    """Repond a une question analytique sur l'historique."""
    chat = _client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {
                "role": "system",
                "content": QUERY_PROMPT.format(today_iso=date.today().isoformat())
                           + f"\n\nHistorique potager :\n{contexte_json}"
            },
            {"role": "user", "content": question}
        ],
        temperature=0.0,
        max_tokens=200,
        stream=False,
        **_REASONING_KWARGS
    )
    return chat.choices[0].message.content.strip()


# ── Transcription Whisper (PWA /voice) ────────────────────────────────────────

def transcribe_audio(audio_path: str, ext: str = ".webm") -> str:
    """
    Transcrit un fichier audio via Groq Whisper.
    Supporte mp4 (iOS), webm (Android/Chrome), ogg, wav, mp3.
    Retourne le texte transcrit ou '' si silence/échec.
    """
    with open(audio_path, "rb") as f:
        tr = _client.audio.transcriptions.create(
            file=(f"audio{ext}", f),
            model=GROQ_WHISPER_MODEL,
            language="fr",
            response_format="text",
        )
    return (tr or "").strip()


# ── Classificateur d'intention pour la PWA ────────────────────────────────────

_PWA_CLASSIFY_PROMPT = """Tu es un classificateur pour un assistant potager.
Réponds UNIQUEMENT par un seul mot : ACTION ou INTERROGER

ACTION = description d'une action réalisée (récolte, semis, arrosage, plantation, traitement, paillage, désherbage, observation, perte, mise en godet...)
INTERROGER = question ou demande d'affichage de données (quand, combien, historique, liste, bilan, stats, total, montre...)

Exemples :
"j'ai récolté 2 kg de tomates" → ACTION
"semé des carottes hier" → ACTION
"arrosage courgettes 20 minutes" → ACTION
"planté 10 salades parcelle nord" → ACTION
"perdu 3 plants de tomates" → ACTION
"mis en godet 15 poivrons" → ACTION
"combien de kg de tomates cette saison ?" → INTERROGER
"quand ai-je semé les carottes ?" → INTERROGER
"montre moi l'historique" → INTERROGER
"bilan de la semaine" → INTERROGER
"historique des traitements" → INTERROGER
"stats courgettes" → INTERROGER
"total des récoltes" → INTERROGER
"""


# ─────────────────────────────────────────────────────────────────────────────
# PARSE UNIFIÉ — intent + parsing en un seul appel LLM
# ─────────────────────────────────────────────────────────────────────────────

_PARSE_MESSAGE_PROMPT = """{date_context}

Tu es un assistant potager. Analyse ce message et retourne UNIQUEMENT un JSON.

=== CHAMP OBLIGATOIRE : "intent" ===
Choisis UNE valeur parmi :
- "ACTION"     : action réalisée à enregistrer (récolté, semé, planté, arrosé, paillé, traité...)
- "HISTORIQUE" : consulter l'historique / le journal des événements passés
- "STATS"      : voir des statistiques, bilan, résumé chiffré
- "INTERROGER" : question analytique (combien, quand, quel total, date de...)
- "PLAN"       : voir le plan d'occupation des parcelles
- "DEPLACER"   : réassocier / déplacer une culture vers une autre parcelle
- "CORRIGER"   : corriger ou modifier un enregistrement existant
- "SUPPRIMER"  : supprimer / effacer un enregistrement
- "MENU"       : revenir au menu / accueil / annuler
- "NOUVELLE"   : saisir une nouvelle action (après une confirmation)

=== RÈGLE DE CLASSIFICATION ===
- Message qui COMMENCE par un verbe au passé (récolté, semé, planté, arrosé...) SANS "?" → ACTION
- "historique", "histo", "journal", "liste des", "mes [action]s" → HISTORIQUE
- "stats", "bilan", "résumé", "chiffres", "total" → STATS
- "combien", "quand", "quel", "affiche", "montre", "consulter" → INTERROGER
- "plan", "plan du potager", "occupation" → PLAN

=== FORMAT DE RÉPONSE ===
Retourne TOUJOURS ce JSON (sans backticks, sans texte autour) :
{{
  "intent": "ACTION|HISTORIQUE|STATS|INTERROGER|PLAN|DEPLACER|CORRIGER|SUPPRIMER|MENU|NOUVELLE",
  "culture": string|null,
  "parcelle": string|null,
  "action_filtre": string|null,
  "items": null
}}

Si intent == "ACTION", remplace "items" par une liste de dicts (un par culture/action) :
{{
  "intent": "ACTION",
  "culture": null,
  "parcelle": null,
  "action_filtre": null,
  "items": [
    {{
      "action": "recolte|semis|plantation|arrosage|traitement|desherbage|taille|paillage|observation|perte|mise_en_godet|repiquage|fertilisation|tuteurage",
      "culture": string|null,
      "variete": string|null,
      "quantite": number|null,
      "unite": "kg|g|l|plants|graines"|null,
      "parcelle": string|null,
      "rang": number|null,
      "duree_minutes": number|null,
      "traitement": string|null,
      "date": "ISO date"|null,
      "commentaire": string|null,
      "nb_graines_semees": number|null,
      "nb_plants_godets": number|null
    }}
  ]
}}

=== EXEMPLES ===
"récolté 800g de tomates en A1"
→ {{"intent":"ACTION","culture":null,"parcelle":null,"action_filtre":null,"items":[{{"action":"recolte","culture":"tomate","variete":null,"quantite":800,"unite":"g","parcelle":"A1","rang":null,"duree_minutes":null,"traitement":null,"date":null,"commentaire":null,"nb_graines_semees":null,"nb_plants_godets":null}}]}}

"historique récolte"
→ {{"intent":"HISTORIQUE","culture":null,"parcelle":null,"action_filtre":"recolte","items":null}}

"historique récoltes cornichon"
→ {{"intent":"HISTORIQUE","culture":"cornichon","parcelle":null,"action_filtre":"recolte","items":null}}

"mes récoltes du mois de mars"
→ {{"intent":"HISTORIQUE","culture":null,"parcelle":null,"action_filtre":"recolte","items":null}}

"stats courgettes"
→ {{"intent":"STATS","culture":"courgette","parcelle":null,"action_filtre":null,"items":null}}

"plan parcelle nord"
→ {{"intent":"PLAN","culture":null,"parcelle":"nord","action_filtre":null,"items":null}}

"combien de kg de tomates cette saison ?"
→ {{"intent":"INTERROGER","culture":"tomate","parcelle":null,"action_filtre":"recolte","items":null}}

"planté 15 oignons blancs et 10 radis hier"
→ {{"intent":"ACTION","culture":null,"parcelle":null,"action_filtre":null,"items":[{{"action":"plantation","culture":"oignon","variete":"blanc","quantite":15,"unite":"plants","parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"date":"{yesterday}","commentaire":null,"nb_graines_semees":null,"nb_plants_godets":null}},{{"action":"plantation","culture":"radis","variete":null,"quantite":10,"unite":"plants","parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"date":"{yesterday}","commentaire":null,"nb_graines_semees":null,"nb_plants_godets":null}}]}}

"Mis en godet 24 tomates cerise sur 30 graines semées"
→ {{"intent":"ACTION","culture":null,"parcelle":null,"action_filtre":null,"items":[{{"action":"mise_en_godet","culture":"tomate","variete":"cerise","quantite":null,"unite":null,"parcelle":null,"rang":null,"duree_minutes":null,"traitement":null,"date":null,"commentaire":null,"nb_graines_semees":30,"nb_plants_godets":24}}]}}

"historique"
→ {{"intent":"HISTORIQUE","culture":null,"parcelle":null,"action_filtre":null,"items":null}}

"stats"
→ {{"intent":"STATS","culture":null,"parcelle":null,"action_filtre":null,"items":null}}
"""

_INTENTS_VALIDES = {
    "ACTION", "HISTORIQUE", "STATS", "INTERROGER", "PLAN",
    "DEPLACER", "CORRIGER", "SUPPRIMER", "MENU", "NOUVELLE",
}


def parse_message(texte: str) -> dict:
    """
    Single-pass : classifie l'intention ET parse les champs en un seul appel LLM.

    Retourne toujours un dict avec au minimum :
      {intent, culture, parcelle, action_filtre, items}

    'items' est une liste de dicts action si intent == 'ACTION', sinon None.
    En cas d'erreur → fallback {"intent": "ACTION", "items": None} pour déclencher
    le chemin de parse_commande() existant.
    """
    import logging as _log
    _logger = _log.getLogger("potager")

    today      = date.today()
    yesterday  = today - timedelta(days=1)
    day_before = today - timedelta(days=2)

    prompt = _PARSE_MESSAGE_PROMPT.format(
        date_context = _today_context(),
        today_iso    = today.isoformat(),
        yesterday    = yesterday.isoformat(),
        day_before   = day_before.isoformat(),
    )

    try:
        chat = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user",   "content": texte},
            ],
            temperature=0.0,
            max_tokens=1024,
            stream=False,
            **_REASONING_KWARGS
        )
        raw = chat.choices[0].message.content.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1]) if len(lines) > 2 else raw

        result = json.loads(raw.strip())

        intent = str(result.get("intent", "ACTION")).strip().upper()
        if intent not in _INTENTS_VALIDES:
            _logger.warning("[parse_message] intent inconnu '%s' → ACTION", intent)
            intent = "ACTION"
        result["intent"] = intent

        # Garantir la présence des clés attendues
        result.setdefault("culture", None)
        result.setdefault("parcelle", None)
        result.setdefault("action_filtre", None)
        result.setdefault("items", None)

        # items doit être une liste si présent
        if result["items"] is not None and isinstance(result["items"], dict):
            result["items"] = [result["items"]]

        _logger.info("[parse_message] intent='%s' culture='%s' action_filtre='%s' items=%s",
                     intent, result["culture"], result["action_filtre"],
                     len(result["items"]) if result["items"] else 0)
        return result

    except Exception as e:
        _logger.error("[parse_message] erreur → fallback ACTION : %s", e)
        return {"intent": "ACTION", "culture": None, "parcelle": None,
                "action_filtre": None, "items": None}


def classify_intent_pwa(texte: str) -> str:
    """
    Classifie l'intention d'un message vocal (PWA).
    Retourne 'ACTION' ou 'INTERROGER'.
    Utilise Groq LLM (~150 tokens, très rapide).
    """
    try:
        chat = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": _PWA_CLASSIFY_PROMPT},
                {"role": "user",   "content": texte},
            ],
            temperature=0.0,
            max_tokens=100,
            stream=False,
            **_REASONING_KWARGS
        )
        result = chat.choices[0].message.content.strip().upper()
        return "INTERROGER" if "INTERROGER" in result else "ACTION"
    except Exception:
        return "ACTION"  # fallback conservatif
