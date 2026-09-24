"""Classification d'intention, questions analytiques (/ask), consultation des godets, retour du jardinier.

Module extrait de l'ancien bot.py monolithique (découpage 2026-09).
"""
import re
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database.db import SessionLocal
from llm import passerelle
from llm import routeur
from llm.passerelle import LLMIndisponibleError, MESSAGE_REPLI_IA
from utils.tts import send_voice_reply
from app.services.context import current_context
from app.services import evenements as svc_evenements
from app.services import retours as svc_retours
from .noyau import AFTER_RECORD_KEYBOARD, MENU_KEYBOARD, log, _decouper_en_blocs


_GODETS_KEYWORDS = (
    "liste des godets", "liste godets", "quels plants en godet",
    "quels plants sont en godet", "plants en godet", "godets en attente",
    "mes godets", "voir les godets", "mes plants en godet",
)


# [US-170 / CA9] Ce qui distingue une consultation des godets EN ATTENTE de
# plantation (liste, sans chiffre à produire — aucun équivalent catalogue) d'une
# question de PRODUCTION/rendement, que le catalogue sait désormais servir
# (famille `godets_produits`, chantier 3). Sans cette exclusion, « combien de
# godet de tomate produit cette saison ? » matchait ci-dessous ("godet" +
# "combien") et n'atteignait jamais le routeur : une réponse fausse d'apparence
# juste (un poids récolté présenté comme un nombre de godets), constatée le
# 30/08/2026. `_is_deplacer_request`/`_is_note_request`, eux, déclenchent des
# flux GUIDÉS de saisie (un geste, pas une question) sans équivalent catalogue
# possible : les déplacer après le routeur les ferait manquer sur toute phrase
# que le routeur classerait ACTION avant d'atteindre leur propre motif — ils
# restent donc, comme avant US-170, consultés avant lui.
_GODETS_EXCLUSION_PRODUCTION = re.compile(r"\bproduits?\b|\brendement\b|\brecolt")


def _is_requete_godets(texte: str) -> bool:
    """Retourne True si la phrase porte sur la consultation des godets en attente."""
    t = texte.lower().strip()
    if _GODETS_EXCLUSION_PRODUCTION.search(t):
        return False
    return any(kw in t for kw in _GODETS_KEYWORDS) or (
        "godet" in t and any(w in t for w in ("liste", "quels", "combien", "voir", "etat", "état"))
    )


# [US-007] _is_deplacer_request et _extract_culture_deplacer sont importées de utils/deplacer.py

# Mots-clés de navigation reconnus (avec ou sans émoji, insensible à la casse)
NAV_NOUVELLE = {"🎤 nouvelle action vocale", "➕ autre action", "autre action",
                "nouvelle action", "nouvelle", "action"}


NAV_INTERROGER = {"🔍 interroger", "🔍 interroger mes données", "interroger",
                  "interrogation", "question", "demander", "analyser",
                  "requête", "requete", "analyse", "recherche", "cherche"}


NAV_HISTORIQUE = {"📋 historique", "historique", "histo", "journal",
                  "historiques", "derniers", "dernier", "liste", "log"}


NAV_STATS      = {"📊 stats", "📊 statistiques", "stats", "statistiques", "stat",
                  "statistique", "chiffres", "résumé", "resume", "bilan",
                  "données", "donnees"}


NAV_MENU       = {"🏠 menu principal", "menu", "accueil", "home", "retour"}


NAV_CORRIGER   = {"✏️ corriger", "corriger", "modifier", "correction", "corriger le dernier",
                  "modifier le dernier", "annuler le dernier", "corriger une saisie",
                  "modifier une saisie", "/corriger",
                  "corrigé", "corrigée", "corrigés", "corrigées",
                  "modifié", "modifiée", "modifiés", "modifiées",
                  "une correction", "faire une correction", "une modification",
                  "je veux corriger", "je veux modifier"}


NAV_SUPPRIMER  = {"🗑 supprimer", "supprimer", "supprimer le dernier", "annuler",
                  "effacer", "effacer le dernier", "delete",
                  "supprimé", "supprimée", "supprimés", "effacé", "effacée"}


# [US-038] Déclencheurs du flux guidé de note/observation
NAV_NOTE       = {"📝 note", "note", "notes", "une note", "ajouter une note",
                  "prendre une note", "/note"}


# ── Intent classification via Groq ─────────────────────────────────────────
# Intents possibles retournés par classify_intent()
INTENTS = {
    "STATS",        # statistiques, bilan, résumé
    "HISTORIQUE",   # journal, historique, derniers événements
    "INTERROGER",   # question, analyser, demander
    "CORRIGER",     # corriger, modifier, changer un enregistrement
    "SUPPRIMER",    # supprimer, effacer, annuler le dernier
    "MENU",         # retour accueil, menu
    "NOUVELLE",     # nouvelle action, autre chose
    "ACTION",       # action potager à enregistrer (récolte, semis, arrosage...)
    "PLAN",         # [US_Plan_occupation_parcelles / CA9] plan d'occupation parcelles
    "DEPLACER",     # [US-007] réassocier une culture à une nouvelle parcelle
}


_CLASSIFY_PROMPT_FIXE = """Tu es un assistant potager spécialisé dans la classification de messages.
L'utilisateur t'envoie un message (vocal transcrit ou texte).

CLASSE CE MESSAGE EN UNE SEULE CATÉGORIE :

🧮 STATS       : veut voir des statistiques, bilan, résumé, chiffres totaux, OU demande le détail d'une culture
  MOTS-CLÉS : stats, statistiques, bilan, résumé, détail, affiche le détail, montre le détail, infos sur
  Exemples :
    ✅ "stats", "statistiques", "bilan de saison"
    ✅ "affiche le détail de la culture courgette"
    ✅ "affiche moi le détail de la courgette"
    ✅ "montre le détail sur les tomates"
    ✅ "détail courgette"
    ✅ "infos sur mes poivrons"
    ✅ "donne moi les stats de la tomate"

📖 HISTORIQUE  : veut voir l'historique, le journal, les derniers événements
  Exemples : "historique", "histo", "journal", "derniers événements", "liste des actions"

❓ INTERROGER  : pose une QUESTION ou demande d'AFFICHER/MONTRER des données
  MOTS-CLÉS : combien, quand, quel, affiche, afficher, montre, montrer, voir, liste, consulter, détail, detail, historique de, date de
  PRONOMS DE POSSESSION : "mes X", "mon X", "ma X", "les X de", "la X de" → INTERROGER car l'utilisateur demande à VOIR ses données
  Exemples :
    ✅ "Combien de kg de tomates ai-je récolté cette saison ?"
    ✅ "Quand ai-je planté mes courgettes ?"
    ✅ "Afficher les récoltes de carotte variété nantaise"
    ✅ "Affiche le détail sur la culture courgette"
    ✅ "Montre-moi les semis de radis"
    ✅ "Date des traitements sur les poivrons"
    ✅ "Historique des arrosages courgettes"
    ✅ "Montrer mes semis de radis"
    ✅ "Voir les dernières récoltes"
    ✅ "Quel est le total de mes semis ?"
    ✅ "Consulter les pertes de cette saison"
    ✅ "Liste des plantations de mai"
    ✅ "Combien ai-je perdu de plants ?"
    ✅ "Quels légumes ai-je arrosés cette semaine ?"
    ✅ "Détail des récoltes de courgettes"
    ✅ "Donne-moi les infos sur mes tomates"
    ✅ "mes récoltes de blette" (pronom possessif → c'est une INTERROGATION)
    ✅ "mes plantations de ce mois" (pronom possessif → INTERROGATION)
    ✅ "récolte de blette ce mois-ci" ("récolte" est un NOM ici, pas un verbe → INTERROGATION)
    ✅ "dernière récolte de blette" ("dernière" indique une consultation → INTERROGATION)
    ✅ "dernière plantation de tomates ?" (demande d'info → INTERROGATION)
    ✅ "semis de radis cette semaine" ("semis" est un NOM → INTERROGATION si pas de verbe d'action)
    ❌ "J'ai récolté 2 kg de tomates" (c'est une ACTION, pas une INTERROGATION)
    ❌ "Semé des carottes hier" (c'est une ACTION)

✏️ CORRIGER    : veut corriger, modifier, changer un enregistrement existant
  Exemples : "corriger", "modifier", "changer", "rectifier"

🗑️ SUPPRIMER   : veut supprimer ou effacer un enregistrement
  Exemples : "supprimer", "effacer", "annuler", "delete"

🏠 MENU        : veut revenir au menu, accueil, annuler, retour
  Exemples : "menu", "accueil", "retour", "home", "annuler"

🎤 NOUVELLE    : veut saisir une nouvelle action (après en avoir enregistré une)
  Exemples : "nouvelle action", "autre action", "ajouter une autre"

🌱 ACTION      : décrit une action potager RÉELLEMENT RÉALISÉE à enregistrer
  Verbes d'action : récolté, semé, planté, arrosé, paillé, traité, désherbé, taillé, tuteuré, repiqué, fertilisé, perdu
  Exemples :
    ✅ "J'ai récolté 2 kg de tomates"
    ✅ "Semé des carottes hier"
    ✅ "Planté 12 plants de poivrons en 3 rangs"
    ✅ "Arrosé les courgettes 30 minutes"
    ✅ "Récolte 500g de carotte nantaise"
    ✅ "Paillé la parcelle nord"
    ✅ "Repiqué 20 plants de laitue"
    ✅ "Traité les tomates contre le mildiou"
    ✅ "Tuteuré les haricots"
    ✅ "Perdu 5 plants de courgettes au gel"
    ❌ "Combien de tomates ?" (c'est une INTERROGATION, pas une ACTION)
    ❌ "Afficher mes récoltes" (c'est une INTERROGATION)

🗺️ PLAN        : veut voir le plan d'occupation des parcelles
  Exemples : "plan du potager", "plan parcelle nord", "montre-moi le plan"

🔀 DEPLACER    : veut réassocier une culture à une nouvelle parcelle (associer, déplacer, changer de parcelle)
  MOTS-CLÉS : associer, déplacer, changer de parcelle, rattacher, affecter, réassocier, déménager
  Exemples :
    ✅ "j'ai besoin d'associer ma zone tomate sur une nouvelle parcelle"
    ✅ "déplacer mes carottes sur la parcelle nord"
    ✅ "changer la parcelle de mes courgettes"
    ✅ "réassocier mes tomates cerise à la parcelle serre"
    ✅ "affecter mes poivrons à une autre parcelle"
    ✅ "rattacher mes aubergines à la parcelle est"
    ✅ "déménager mes salades vers la parcelle sud"
    ❌ "planté des tomates dans la parcelle nord" (c'est une ACTION, pas un déplacement)
    ❌ "j'ai déplacé un pot" (pas une culture de parcelle)

RÈGLE IMPORTANTE #1 :
Si le message contient "affiche", "afficher", "montre", "montrer", "voir", "liste", "consulter", "détail", "combien", "quand", "quel"
→ c'est INTERROGER ou HISTORIQUE, JAMAIS ACTION (même sans "?" en fin de phrase).

RÈGLE IMPORTANTE #2 :
Si le message COMMENCE par un verbe d'action au PASSÉ COMPOSÉ (récolté, semé, planté, arrosé, paillé, traité...)
ET SANS "?" → c'est ACTION, jamais INTERROGER.
ATTENTION : "récolte" (sans accent final, forme nominale) ≠ "récolté" (participe passé).
"récolte de blette" = NOM → INTERROGER. "récolté des blettes" = VERBE PASSÉ → ACTION.

RÈGLE IMPORTANTE #3 :
Si le message COMMENCE par un pronom possessif (mes, mon, ma, les, nos, leurs, des...)
suivi d'un nom de culture ou d'action → c'est INTERROGER (l'utilisateur consulte ses données).
Exemples : "mes récoltes de blette" → INTERROGER, "mes plantations" → INTERROGER.

RÈGLE IMPORTANTE #4 :
Si le message contient "dernière", "dernier", "première", "premier", "ce mois-ci", "cette semaine"
SANS verbe d'action au passé → c'est INTERROGER (consultation de données existantes).

"""


# [US-092 / CA6] Suffixe variable — le seul morceau qui change d'un appel à
# l'autre. Il est concaténé APRÈS _CLASSIFY_PROMPT_FIXE par la passerelle, de
# sorte que tout le préfixe reste identique et donc éligible au cache de prompt.
_CLASSIFY_SUFFIXE = """
Message utilisateur : "{texte}"

Réponds avec UN SEUL MOT en majuscules parmi :
STATS | HISTORIQUE | INTERROGER | CORRIGER | SUPPRIMER | MENU | NOUVELLE | ACTION | PLAN | DEPLACER

Réponse :"""


def classify_intent(texte: str) -> str:
    """Classe l'intention du message en un intent canonique, via la passerelle.

    [US-092 / CA6] Le message de l'utilisateur, seule partie variable, part en
    fin de prompt — la consigne de classification reste un préfixe stable.
    """
    try:
        reponse = passerelle.appeler_chat(
            appel_type=passerelle.TYPE_CLASSIFICATION,
            ctx=current_context(),
            prompt_fixe=_CLASSIFY_PROMPT_FIXE,
            prompt_variable=_CLASSIFY_SUFFIXE.format(texte=texte),
            max_tokens=10,
            reasoning=False,   # comportement constant : cet appel n'en passait pas
            role_prompt="user",
        )
        intent = reponse.texte.upper().rstrip(".!? ")
        if intent not in INTENTS:
            log.warning(f"⚠️ INTENT INCONNU  : '{intent}' → fallback ACTION")
            intent = "ACTION"
        log.info(f"🧭 INTENT          : '{texte}' → {intent}")
        return intent
    except Exception as e:
        log.error(f"Erreur classify_intent : {e}")
        return "ACTION"  # fallback sûr


def _extract_stats_culture(texte: str) -> str | None:
    """
    [US_Stats_detail_par_variete / CA8]
    Extrait la culture depuis une phrase vocale type 'stats tomate' ou
    'affiche le détail de la culture courgette'.

    Exemples reconnus :
      "stats tomate"                              → "tomate"
      "statistiques de la tomate"                → "tomate"
      "affiche le détail de la culture courgette" → "courgette"
      "affiche moi le détail de la courgette"    → "courgette"
      "montre le détail sur les tomates"         → "tomates"
      "détail courgette"                         → "courgette"
      "infos sur mes poivrons"                   → "poivrons"
      "stats" seul                               → None
    """
    import re
    t = texte.lower().strip()

    # Pattern 1 — "stats/statistiques [de [la/les/du]] <culture>"
    m = re.match(
        r'^(?:stats?|statistiques?)\s+(?:de\s+(?:la\s+|les?\s+|des?\s+)?|du\s+)?(\w+)$',
        t,
    )
    if m:
        return m.group(1)

    # Pattern 2 — "affiche/montre [moi] le détail [de [la culture/les/du]] <culture>"
    m = re.search(
        r'(?:affiche?(?:r)?|montre?(?:r)?)\s+(?:moi\s+)?(?:le\s+)?d[eé]tail\s+'
        r'(?:de\s+(?:la\s+culture\s+|la\s+|les?\s+|des?\s+|du\s+)?'
        r'|sur\s+(?:la\s+culture\s+|les?\s+cultures?\s+|la\s+|les?\s+)?)?(\w+)',
        t,
    )
    if m:
        return m.group(1)

    # Pattern 3 — "détail <culture>" ou "détail de [la] <culture>"
    m = re.match(
        r'^d[eé]tail\s+(?:de\s+(?:la\s+|les?\s+|des?\s+|du\s+)?)?(\w+)$',
        t,
    )
    if m:
        return m.group(1)

    # Pattern 4 — "infos sur [mes/les/la] <culture>"
    m = re.search(r'infos?\s+sur\s+(?:mes?\s+|les?\s+|la\s+)?(\w+)', t)
    if m:
        return m.group(1)

    # Pattern 5 — "donne moi les stats de [la] <culture>"
    m = re.search(
        r'(?:donne(?:r)?(?:\s+moi)?)\s+(?:les?\s+)?stats?\s+(?:de\s+(?:la\s+|les?\s+|des?\s+)?)?(\w+)',
        t,
    )
    if m:
        return m.group(1)

    return None


def _extract_plan_parcelle(texte: str) -> str | None:
    """
    [US_Plan_occupation_parcelles / CA9]
    Extrait le nom de parcelle depuis une phrase vocale type 'plan parcelle nord'.

    Exemples reconnus :
      "plan du potager"     → None  (vue globale)
      "plan parcelle nord"  → "nord"
      "plan nord"           → "nord"
    """
    m = re.search(
        r'plan\s+(?:parcelle\s+)?(\w+)',
        texte.lower().strip(),
    )
    if m:
        mot = m.group(1)
        # Ignorer les mots génériques qui ne sont pas des noms de parcelle
        if mot in {"du", "des", "le", "la", "les", "potager", "jardin"}:
            return None
        return mot
    return None


# ── QUESTION ANALYTIQUE ─────────────────────────────────────────────────────────
async def _ask_question(update: Update, question: str):
    """
    [US-012 / US-093 / US-097] Interroge l'historique via SQL agent, ou bascule
    vers le savoir/raisonnement selon l'aiguillage du routeur — zéro
    hallucination sur l'étage data, zéro appel modèle sur la frange non
    ambiguë (règles/cache).

    Flux : routeur.classer_demande() [0 token la plupart du temps] →
    étage data (SQL, 0 token) ou raisonnement, avec au plus une remontée de
    cascade si l'étage data ne trouve rien d'exploitable (US-093 / CA6).
    Chaque cascade menée à son terme est journalisée (US-097 / CA1) ; les
    réponses de savoir/raisonnement proposent en plus un retour 👍/👎
    (US-097 / CA9).
    """
    log.info(f"🔍 QUESTION       : {question}")
    msg = await update.message.reply_text("🔍 *Analyse de vos données...*", parse_mode="Markdown")
    try:
        resultat = routeur.repondre_avec_cascade(current_context(), question)
        reponse = resultat.texte
        log.info(f"💡 RÉPONSE        : {reponse[:200]}{'...' if len(reponse) > 200 else ''}")

        # [INC-010] Une réponse de savoir peut recopier un fragment tel quel
        # (CA7 : zéro reformulation) au-delà des 4096 caractères que Telegram
        # accepte sur un edit_text/reply_text — découpage nécessaire pour ne
        # pas perdre la réponse trouvée derrière un Message_too_long.
        blocs = _decouper_en_blocs(f"🔍 *Réponse :*\n\n{reponse}")
        try:
            await msg.edit_text(blocs[0], parse_mode="Markdown")
        except Exception:
            await msg.edit_text(blocs[0].replace("*", "").replace("_", ""))
        for bloc in blocs[1:]:
            try:
                await update.message.reply_text(bloc, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(bloc.replace("*", "").replace("_", ""))

        # [US-097 / CA9] Retour 👍/👎 uniquement pour les réponses de savoir ou
        # de raisonnement (étages 2 et 3) — jamais pour une donnée du potager,
        # qui n'est pas un avis à recueillir. Rien à proposer si le journal
        # n'a pas pu être écrit (routage_log_id absent) : il n'y aurait rien
        # à rattacher (CA10).
        if resultat.routage_log_id is not None and resultat.etage_resolveur in (
            routeur.ETAGE_SAVOIR, routeur.ETAGE_RAISONNEMENT,
        ):
            boutons = [[
                InlineKeyboardButton("👍", callback_data=f"retour_routage:positif:{resultat.routage_log_id}"),
                InlineKeyboardButton("👎", callback_data=f"retour_routage:negatif:{resultat.routage_log_id}"),
            ]]
            await update.message.reply_text(
                "_Cette réponse t'a aidé ?_",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(boutons),
            )

        await update.message.reply_text(
            "_Autre question ou action ?_",
            parse_mode="Markdown",
            reply_markup=AFTER_RECORD_KEYBOARD
        )
        await send_voice_reply(update, reponse)
    except LLMIndisponibleError:
        # [US-092 / CA9, CA10] L'extraction d'intention est indisponible, mais
        # les consultations déterministes, elles, ne consomment aucun appel LLM.
        log.warning("⏳ QUESTION        : IA indisponible → orientation consultations déterministes")
        await msg.edit_text(
            f"⏳ {MESSAGE_REPLI_IA}.\n\n"
            "/stats, /plan, /historique et /meteo restent disponibles."
        )
    except Exception as e:
        log.error(f"❌ Erreur _ask_question: {e}")
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)


async def _consulter_godets(update) -> None:
    """[US_mise_en_godet] Affiche les plants en godet sans plantation postérieure."""
    db = SessionLocal()
    try:
        en_attente = svc_evenements.godets_en_attente(db, current_context())

        if not en_attente:
            await update.message.reply_text(
                "🪴 *Aucun plant en godet actuellement.*\n\n"
                "Enregistrez une mise en godet :\n"
                "_\"mise en godet 20 tomates Saint-Pierre\"_",
                parse_mode="Markdown",
                reply_markup=AFTER_RECORD_KEYBOARD,
            )
            return

        lines = ["🪴 *Plants actuellement en godet :*\n"]
        for g in en_attente:
            cult = g.culture or "?"
            var  = f" ({g.variete})" if g.variete else ""
            nb   = f" — *{g.nb_plants_godets} plants*" if g.nb_plants_godets else ""
            date_str = f" _{g.date.strftime('%d/%m/%Y')}_" if g.date else ""
            lines.append(f"• 🌱 {cult}{var}{nb}{date_str}")

        lines.append("\n💡 _Plantez-les avec : \"planté X tomates en A1\"_")
        await update.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=AFTER_RECORD_KEYBOARD,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}", reply_markup=MENU_KEYBOARD)
    finally:
        db.close()


# ── [US-097] CALLBACK RETOUR SUR RÉPONSE (savoir/raisonnement) ──────────────────

async def _retour_routage_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """[US-097 / CA9-CA13] Callback inline — avis 👍/👎 sur une réponse de
    savoir/raisonnement. Point d'écriture pur : aucun avis, positif ou
    négatif, ne déclenche de nouvel appel modèle (CA13)."""
    query = update.callback_query
    await query.answer()

    # retour_routage:<positif|negatif>:<routage_log_id>
    try:
        _, avis, routage_log_id_str = query.data.split(":")
        routage_log_id = int(routage_log_id_str)
    except (ValueError, IndexError):
        await query.edit_message_text("❌ Données invalides.", reply_markup=None)
        return

    db = SessionLocal()
    try:
        svc_retours.enregistrer_retour(db, current_context().potager_id, routage_log_id, avis)
        emoji = "👍" if avis == svc_retours.AVIS_POSITIF else "👎"
        await query.edit_message_text(f"{emoji} Merci, ton avis est enregistré.", reply_markup=None)
    except svc_retours.RetourDejaEnregistreError:
        # [CA11] Jamais redemandé — un second clic (double-tap) ne casse rien.
        await query.edit_message_text("Un avis a déjà été enregistré pour cette réponse.", reply_markup=None)
    except svc_retours.RoutageLogIntrouvableError:
        await query.edit_message_text("❌ Cette réponse n'est plus disponible.", reply_markup=None)
    except Exception as e:
        log.error(f"❌ Erreur retour routage : {e}")
        await query.edit_message_text("❌ Erreur lors de l'enregistrement de l'avis.", reply_markup=None)
    finally:
        db.close()
