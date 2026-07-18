"""
main.py — Assistant Potager v2 (moteur Groq, gratuit)
─────────────────────────────────────────────────────
Endpoints :
  GET  /health      → vérifier que l'API tourne
  POST /parse       → dicter une commande vocale (JSON)
  POST /voice       → blob audio MediaRecorder → Whisper → intent → JSON (PWA iPhone)
  POST /ask         → poser une question analytique
  GET  /stats       → stats JSON instantanées (sans LLM)
  GET  /historique  → derniers événements avec filtres
"""
import json
import os
import tempfile
import uuid
from datetime import date
from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Version [US-008] ────────────────────────────────────────────────────────────
def _lire_version() -> str:
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_base, "VERSION"), encoding="utf-8") as _f:
            return _f.read().strip()
    except OSError:
        return "inconnue"

_APP_VERSION = _lire_version()

from database.db import Base, engine, SessionLocal, tenant_scope
import utils.stock as _stock_mod
from utils.observations import build_observations_index
from llm.groq_client import parse_commande, transcribe_audio, classify_intent_pwa
from llm.rag import add_to_rag
from app.services.context import default_context
from app.services import evenements as svc_evenements
from app.services import stats as svc_stats
from app.services import plan as svc_plan
from app.services import questions as svc_questions
from app.services import parcelles as svc_parcelles

# ── Initialisation ─────────────────────────────────────────────────────────────
app = FastAPI(title="Assistant Potager 🌿", version=_APP_VERSION)
Base.metadata.create_all(bind=engine)   # crée la table si elle n'existe pas

# ── CORS — autorise le frontend Netlify + dev local ────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",        # dev React local
        "http://localhost:5173",        # dev Vite local
        "https://*.netlify.app",        # frontend Netlify (prod)
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)


# [US-043] Arme app.potager_id (défense en profondeur RLS) pour toute la durée
# de traitement de chaque requête HTTP — à partir du TenantContext courant
# (toujours default_context() en attendant l'authentification US-110/112).
@app.middleware("http")
async def _tenant_context_middleware(request, call_next):
    with tenant_scope(default_context().potager_id):
        return await call_next(request)

# ── Sessions conversationnelles (in-memory, multi-tours) ──────────────────────
# { session_id: [{"role": "user"|"assistant", "content": str}, ...] }
_sessions: dict[str, list[dict]] = {}
_SESSION_MAX_TURNS = 5  # garder les 5 derniers échanges

# ── Mapping MIME type → extension fichier audio ────────────────────────────────
_MIME_EXT: dict[str, str] = {
    "audio/mp4"  : ".mp4",
    "audio/m4a"  : ".m4a",
    "audio/webm" : ".webm",
    "audio/ogg"  : ".ogg",
    "audio/wav"  : ".wav",
    "audio/mpeg" : ".mp3",
    "audio/aac"  : ".aac",
}

# ── Frontend React (prioritaire) ou PWA fallback ──────────────────────────────
_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")
_STATIC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

if os.path.isdir(_DIST):
    # Dashboard React buildé — servi en priorité
    _DIST_ASSETS = os.path.join(_DIST, "assets")
    if os.path.isdir(_DIST_ASSETS):
        app.mount("/assets", StaticFiles(directory=_DIST_ASSETS), name="assets")

    @app.get("/", include_in_schema=False)
    def serve_frontend():
        """Sert le dashboard React (frontend/dist/index.html)."""
        return FileResponse(os.path.join(_DIST, "index.html"))

elif os.path.isdir(_STATIC):
    # Fallback : ancienne PWA si le dist React n'est pas buildé
    app.mount("/static", StaticFiles(directory=_STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def serve_pwa():
        return FileResponse(os.path.join(_STATIC, "index.html"))


# ── Modèle de requête ──────────────────────────────────────────────────────────
class TexteRequest(BaseModel):
    texte: str


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health():
    """Vérification que le serveur est opérationnel."""
    db = SessionLocal()
    nb = svc_evenements.compter_evenements(db, default_context())
    db.close()
    return {
        "status"          : "ok",
        "version"         : _APP_VERSION,
        "moteur_llm"      : "Groq (gratuit)",
        "date"            : str(date.today()),
        "evenements_total": nb
    }


@app.get("/cultures")
def get_cultures():
    """
    Retourne la liste des cultures configurées avec leur type d'organe récolté.
    Utile pour l'interface PWA et la validation des saisies.
    """
    db = SessionLocal()
    try:
        cultures = svc_parcelles.lister_cultures_config(db, default_context())
        result = [
            {
                "nom": c.nom,
                "type_organe_recolte": c.type_organe_recolte,
                "description_agronomique": c.description_agronomique
            }
            for c in cultures
        ]
        return {"cultures": result, "total": len(result)}
    finally:
        db.close()


@app.post("/parse")
def parse(req: TexteRequest):
    """
    Reçoit une phrase dictée → parse via Groq → sauvegarde en base.
    Gère les phrases multiples (ex: tomates ET courgettes → 2 événements).
    La date réelle (hier, lundi...) est stockée correctement.
    """
    if not req.texte or len(req.texte.strip()) < 3:
        raise HTTPException(status_code=400, detail="Texte trop court")

    # ── 1. Parsing LLM → liste d'événements ──────────────────────────────────
    try:
        items = parse_commande(req.texte)   # toujours une liste
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"JSON invalide retourné par Groq : {e}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur Groq API : {e}")

    # ── 2. Sauvegarde PostgreSQL ──────────────────────────────────────────────
    db = SessionLocal()
    ctx = default_context()
    saved = []
    try:
        for parsed in items:
            event = svc_evenements.creer_evenement_depuis_parse(db, ctx, parsed, req.texte)
            add_to_rag(event.id, parsed)
            saved.append({"event_id": event.id, "parsed": parsed})

        return {
            "success"        : True,
            "nb_evenements"  : len(saved),
            "evenements"     : saved,
            "event_id"       : saved[0]["event_id"] if saved else None,
            "parsed"         : saved[0]["parsed"]   if saved else None,
            "texte_original" : req.texte,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur base de données : {e}")
    finally:
        db.close()


@app.post("/voice")
async def voice(
    audio: UploadFile = File(...),
    session_id: str   = Form(default=""),
):
    """
    [PWA iPhone] Reçoit un blob audio MediaRecorder →
      1. Groq Whisper → texte transcrit
      2. classify_intent_pwa() → ACTION | INTERROGER
      3. parse_commande() ou repondre_question()
      4. Retourne { reponse, intent, texte, recap, session_id }
    """
    # 1. Écrire le blob audio dans un fichier temporaire
    ct  = (audio.content_type or "audio/webm").split(";")[0].strip()
    ext = _MIME_EXT.get(ct, ".webm")

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
        tmp.write(await audio.read())

    # 2. Transcription Whisper
    try:
        texte = transcribe_audio(tmp_path, ext)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur Whisper : {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if not texte:
        return {
            "reponse"    : "Je n'ai pas compris. Parlez plus distinctement et réessayez.",
            "intent"     : "ERREUR",
            "texte"      : "",
            "recap"      : None,
            "session_id" : session_id or str(uuid.uuid4()),
        }

    # 3. Session
    if not session_id:
        session_id = str(uuid.uuid4())
    history = _sessions.get(session_id, [])

    # 4. Classification de l'intention
    intent = classify_intent_pwa(texte)

    # 5a. INTERROGER — question analytique sur l'historique
    if intent == "INTERROGER":
        try:
            reponse = svc_questions.repondre_question(default_context(), texte)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erreur agent SQL : {e}")

        result = {
            "reponse"    : reponse,
            "intent"     : "INTERROGER",
            "texte"      : texte,
            "recap"      : None,
            "session_id" : session_id,
        }

    # 5b. ACTION — enregistrement d'un événement potager
    else:
        try:
            items = parse_commande(texte)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=502, detail=f"JSON invalide Groq : {e}")
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erreur parsing : {e}")

        db = SessionLocal()
        ctx = default_context()
        saved_parsed: list[dict] = []
        try:
            for parsed in items:
                event = svc_evenements.creer_evenement_depuis_parse(db, ctx, parsed, texte)
                add_to_rag(event.id, parsed)
                saved_parsed.append(parsed)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Erreur base : {e}")
        finally:
            db.close()

        recap = saved_parsed[0] if saved_parsed else None

        # Réponse vocale synthétique
        if recap:
            parts = [
                recap.get("action"),
                (recap.get("culture") or "") + (f" {recap['variete']}" if recap.get("variete") else ""),
                f"{recap['quantite']} {recap.get('unite', '')}".strip() if recap.get("quantite") is not None else None,
                f"parcelle {recap['parcelle']}" if recap.get("parcelle") else None,
            ]
            resume = ", ".join(p for p in parts if p)
            reponse = f"C'est noté ! J'ai enregistré : {resume}."
            if len(saved_parsed) > 1:
                reponse = f"C'est noté ! J'ai enregistré {len(saved_parsed)} actions."
        else:
            reponse = "Action enregistrée."

        result = {
            "reponse"       : reponse,
            "intent"        : "ACTION",
            "texte"         : texte,
            "recap"         : recap,
            "session_id"    : session_id,
            "nb_evenements" : len(saved_parsed),
        }

    # 6. Mettre à jour la session (historique multi-tours)
    history.append({"role": "user",      "content": texte})
    history.append({"role": "assistant", "content": result["reponse"]})
    _sessions[session_id] = history[-(  _SESSION_MAX_TURNS * 2):]

    return result


@app.post("/ask")
def ask(req: TexteRequest):
    """
    Répond en langage naturel à une question sur l'historique du potager.
    Exemples : 'Combien de kg de tomates ?', 'Historique traitements courgettes'
    """
    try:
        reponse = svc_questions.repondre_question(default_context(), req.texte)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erreur agent SQL : {e}")

    return {"reponse": reponse}


@app.get("/stats")
def stats(date_ref: date = Query(default=None)):
    """[US-002/CA4] Statistiques JSON avec stock agronomique différencié.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée."""
    db = SessionLocal()
    try:
        ctx = default_context()
        result = svc_stats.calculer_stats(db, ctx, date_ref)
        date_ref_effective = result.date_ref_effective
        total = result.total_evenements
        stocks = result.stocks
        godets = result.godets
        traitements = result.traitements
        cultures_avec_godet = result.cultures_avec_godet

        # [US-026 / semis pleine terre] Semis directement associés à une parcelle
        semis_data = result.semis
        cultures_semis_pt = {c.lower() for c, s in semis_data.items() if s.get("parcelles_pleine_terre")}
        semis_pleine_terre = [
            {
                "culture":    c,
                "total_seme": int(s["total_seme"]),
                "unite":      s["unite"],
                "type_organe": s["type_organe"],
                "parcelles":  s["parcelles_pleine_terre"],
            }
            for c, s in semis_data.items()
            if s.get("parcelles_pleine_terre")
        ]

        # [US-039 / CA2, CA6] Indicateur d'observations agrégées par culture (Stocks)
        obs_index = build_observations_index(db)

        stock_enrichi = _stock_mod.format_stock_stats_json(stocks)
        for entry in stock_enrichi:
            nom = (entry.get("culture") or "").lower()
            if nom in cultures_avec_godet:
                entry["origine"] = "pépinière"
            elif nom in cultures_semis_pt:
                entry["origine"] = "semis_pleine_terre"
            else:
                entry["origine"] = "pied_acheté"
            nb_obs = len(obs_index["stocks"].get(nom, []))
            entry["has_observations"] = nb_obs > 0
            entry["nb_observations"]  = nb_obs

        return {
            "date_ref_effective" : date_ref_effective.isoformat(),
            "total_evenements"   : total,
            "stock_par_culture"  : stock_enrichi,
            "godets"             : [
                {
                    "culture":           v["culture"],
                    "variete":           v["variete"],
                    "nb_plants_godets":  v["nb_plants_godets"],
                    "nb_graines_semees": v["nb_graines_semees"],
                    "nb_vendus":         v.get("nb_vendus", 0),
                    "nb_pertes_godet":   v.get("nb_pertes_godet", 0),
                    "stock_residuel_godet": v["stock_residuel_godet"],
                    "taux_reussite":     v["taux_reussite"],
                }
                for v in godets.values()
            ],
            "semis_pleine_terre" : semis_pleine_terre,
            "traitements"        : [{"produit": t or "?", "nb_applications": n} for t, n in traitements],
        }
    finally:
        db.close()


@app.get("/stats/rendement")
def get_rendement(annee: int = Query(default=None), date_ref: date = Query(default=None)):
    """[US_Stats_rendement_timeline] Timeline mensuelle des récoltes par culture.
    [US-030] date_ref optionnel (YYYY-MM-DD) : plafonne la borne haute à cette date."""
    from utils.stock import calcul_rendement_mensuel
    from app.services.context import default_context
    today = date.today()
    annee_eff = annee or today.year
    dr = min(date_ref, today) if date_ref else None
    db = SessionLocal()
    try:
        data = calcul_rendement_mensuel(db, annee_eff, dr, potager_id=default_context().potager_id)
        return {"annee": annee_eff, **data}
    finally:
        db.close()


@app.get("/stats/activite")
def get_activite(annee: int = Query(default=None), date_ref: date = Query(default=None)):
    """[US_Stats_activite_potager] Heatmap d'activité quotidienne (nb événements/jour).
    [US-030] date_ref optionnel (YYYY-MM-DD) : plafonne la borne haute à cette date."""
    from utils.stock import calcul_activite_quotidienne
    from app.services.context import default_context
    today = date.today()
    annee_eff = annee or today.year
    dr = min(date_ref, today) if date_ref else None
    db = SessionLocal()
    try:
        jours = calcul_activite_quotidienne(db, annee_eff, dr, potager_id=default_context().potager_id)
        return {
            "annee":         annee_eff,
            "jours":         jours,
            "total_actions": sum(jours.values()),
            "jours_actifs":  len(jours),
        }
    finally:
        db.close()


@app.get("/plan")
def get_plan(date_ref: date = Query(default=None)):
    """
    [US-024] Plan d'occupation des parcelles pour le dashboard frontend.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.

    Retourne la liste des parcelles actives avec leurs cultures en cours.
    Les parcelles sans culture sont incluses avec cultures=[].
    """
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        ctx = default_context()
        parcelles     = svc_plan.get_parcelles(db, ctx)
        occupation    = svc_plan.get_occupation(db, ctx, dr)

        # Index surface_m2 par nom de culture (insensible à la casse)
        surface_par_culture = svc_plan.surface_par_culture(db, ctx)

        # [US-039 / CA1, CA5] Indicateur d'observations par parcelle / ligne de culture
        obs_index = build_observations_index(db)

        result = []
        for p in parcelles:
            cultures_raw = occupation.get(p.nom, [])
            cultures = [
                {
                    "culture":    c.get("culture", ""),
                    "variete":    c.get("variete"),
                    # [US-037 / CA10] Une surface m² est fractionnable (ex: 1.5 m²) —
                    # ne jamais tronquer en int comme pour un nombre de plants/graines.
                    "nb_plants":  (c.get("nb_plants") or 0) if c.get("unite") == "m²" else int(c.get("nb_plants") or 0),
                    "unite":      c.get("unite") or "plants",
                    "type_organe": c.get("type_organe") or "végétatif",
                    "surface_m2_par_plant": surface_par_culture.get(
                        (c.get("culture") or "").lower(), None
                    ),
                    "nb_observations": (
                        len(obs_index["culture_row"].get((p.id, c["culture"].lower(), c["variete"]), []))
                        if c.get("variete") and c.get("culture") else 0
                    ),
                }
                for c in cultures_raw
            ]
            for c in cultures:
                c["has_observations"] = c["nb_observations"] > 0

            # [US-037 / CA10] Calcul occupation réel : une culture semée en m² occupe
            # directement cette surface (aucune conversion via une empreinte au pied) ;
            # les autres unités (graines, pieds, plants) restent multipliées par
            # surface_m2_par_plant comme avant.
            occupation_pct = None
            if p.superficie_m2:
                surface_utilisee = sum(
                    c["nb_plants"] if c["unite"] == "m²"
                    else c["nb_plants"] * c["surface_m2_par_plant"]
                    for c in cultures
                    if c["unite"] == "m²" or c["surface_m2_par_plant"]
                )
                if surface_utilisee > 0:
                    occupation_pct = min(100, round(surface_utilisee / p.superficie_m2 * 100))

            nb_obs_parcelle = len(obs_index["parcelle"].get(p.id, []))
            result.append({
                "id":            p.id,
                "nom":           p.nom,
                "exposition":    p.exposition,
                "superficie_m2": p.superficie_m2,
                "cultures":      cultures,
                "occupation_pct": occupation_pct,
                "has_observations": nb_obs_parcelle > 0,
                "nb_observations":  nb_obs_parcelle,
            })

        return {"parcelles": result, "total": len(result), "date_ref_effective": date_ref_effective.isoformat()}
    finally:
        db.close()


@app.get("/observations")
def get_observations(
    parcelle_id: int = Query(default=None),
    culture: str = Query(default=None),
    variete: str = Query(default=None),
):
    """
    [US-039 / CA3] Détail des observations pour un point d'accès du dashboard :
      - parcelle_id + culture + variete → ligne de culture précise (Plan)
      - parcelle_id seul                → carte parcelle (Plan)
      - culture seule                   → agrégat culture (Stocks)
    """
    db = SessionLocal()
    try:
        index = build_observations_index(db)
        if parcelle_id is not None and culture and variete:
            items = index["culture_row"].get((parcelle_id, culture.lower(), variete), [])
        elif parcelle_id is not None:
            items = index["parcelle"].get(parcelle_id, [])
        elif culture:
            items = index["stocks"].get(culture.lower(), [])
        else:
            items = []
        return {"items": items}
    finally:
        db.close()


@app.get("/godets")
def get_godets(date_ref: date = Query(default=None)):
    """
    [US-026] État de la pépinière : godets en attente de plantation + cultures tout plantées.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée.

    Utilise calcul_godets() pour un stock agrégé par (culture, variété) avec déduction
    des plantations. Retourne deux listes :
    - en_attente  : cultures avec stock_residuel_godet > 0
    - tout_plante : cultures entièrement plantées (stock = 0), listées dans l'encart "Tout planté"
    """
    from utils.stock import calcul_godets
    from app.services.context import default_context
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        tous = calcul_godets(db, include_epuises=True, date_ref=dr, potager_id=default_context().potager_id)
        en_attente  = [v for v in tous.values() if v["stock_residuel_godet"] > 0 or v.get("graines_en_germination", 0) > 0]
        tout_plante = [v for v in tous.values() if v["stock_residuel_godet"] == 0 and not v.get("graines_en_germination")]
        return {
            "en_attente": en_attente,
            "tout_plante": tout_plante,
            "total": len(en_attente),
            "date_ref_effective": date_ref_effective.isoformat(),
        }
    finally:
        db.close()



@app.get("/godets/detail")
def get_godet_detail(culture: str = Query(...), variete: str = Query(default=None)):
    """
    [US-029] Cycle de vie complet semis → godets → plantations pour une (culture, variété).
    Utilisé par le panneau de détail de la pépinière frontend.
    """
    db = SessionLocal()
    try:
        cycle = svc_evenements.cycle_vie_culture(db, default_context(), culture, variete)
        semis_events        = cycle["semis"]
        godet_events        = cycle["godets"]
        linked_plantations  = cycle["plantations"]
        vendu_events        = cycle["ventes"]
        perte_events        = cycle["pertes_godet"]
        taux                = cycle["taux_germination"]

        return {
            "culture": culture,
            "variete": variete,
            "semis": [
                {
                    "id":        s.id,
                    "date":      str(s.date)[:10],
                    "nb_graines": int(s.quantite or 0),
                    "unite":     s.unite or "graines",
                    "parcelle":  s.parcelle_rel.nom if s.parcelle_rel else None,
                }
                for s in semis_events
            ],
            "godets": [
                {
                    "id":              g.id,
                    "date":            str(g.date)[:10],
                    "nb_plants":       int(g.nb_plants_godets or 0),
                    "nb_graines_lot":  int(g.nb_graines_semees) if g.nb_graines_semees else None,
                    "origine_semis_id": g.origine_graines_id,
                }
                for g in godet_events
            ],
            "plantations": [
                {
                    "id":              p.id,
                    "date":            str(p.date)[:10],
                    "quantite":        int(p.quantite or 0),
                    "parcelle":        p.parcelle_rel.nom if p.parcelle_rel else None,
                    "source_godet_ids": p.source_evenement_ids.split(";") if p.source_evenement_ids else [],
                }
                for p in linked_plantations
            ],
            "ventes": [
                {
                    "id":       v.id,
                    "date":     str(v.date)[:10],
                    "quantite": int(v.quantite or 0),
                }
                for v in vendu_events
            ],
            "pertes_godet": [
                {
                    "id":       p.id,
                    "date":     str(p.date)[:10],
                    "quantite": int(p.quantite or 0),
                }
                for p in perte_events
            ],
            "taux_germination": taux,
        }
    finally:
        db.close()


@app.get("/meteo/history")
def meteo_history(
    days    : int   = Query(default=30, ge=7, le=365, description="Nombre de jours d'historique"),
    lat     : float = Query(default=None, description="Latitude GPS (défaut : potager configuré)"),
    lon     : float = Query(default=None, description="Longitude GPS (défaut : potager configuré)"),
    timezone: str   = Query(default=None, description="Fuseau IANA (défaut : Europe/Paris)"),
):
    """
    Historique météo journalier (températures min/max + précipitations) depuis Open-Meteo Archive.
    Gratuit, sans authentification, zéro token Groq.

    Paramètres optionnels lat/lon permettent d'interroger n'importe quel potager.
    Retourne : { jours: [...], meta: { lat, lon, timezone, days, start_date, end_date } }
    """
    from utils.meteo import fetch_meteo_history, METEO_LATITUDE, METEO_LONGITUDE, METEO_TIMEZONE

    eff_lat = lat      if lat      is not None else METEO_LATITUDE
    eff_lon = lon      if lon      is not None else METEO_LONGITUDE
    eff_tz  = timezone if timezone is not None else METEO_TIMEZONE

    jours = fetch_meteo_history(lat=eff_lat, lon=eff_lon, days=days, timezone=eff_tz)

    if jours is None:
        raise HTTPException(status_code=502, detail="Impossible de récupérer les données Open-Meteo Archive")

    return {
        "jours": jours,
        "meta": {
            "lat"       : eff_lat,
            "lon"       : eff_lon,
            "timezone"  : eff_tz,
            "days"      : days,
            "start_date": jours[0]["date"]  if jours else None,
            "end_date"  : jours[-1]["date"] if jours else None,
        },
    }


@app.get("/historique")
def historique(
    limit     : int  = Query(default=20, le=100),
    offset    : int  = Query(default=0, ge=0),
    action    : str  = Query(default=None),
    culture   : str  = Query(default=None),
    parcelle  : str  = Query(default=None),
    from_date : str  = Query(default=None, alias="from"),
    to_date   : str  = Query(default=None, alias="to"),
    date_ref  : date = Query(default=None),
):
    """
    [US-027] Retourne les événements paginés avec filtres optionnels.
    [US-030] date_ref optionnel (YYYY-MM-DD) : borne haute, prioritaire sur to_date.
    Ex: /historique?culture=tomate&action=recolte&from=2026-05-01&to=2026-05-31&offset=20
    Retourne : { total: int, evenements: [...], date_ref_effective: str }
    """
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    # date_ref prend priorité sur to_date
    effective_to = dr.isoformat() if dr else to_date
    db = SessionLocal()
    try:
        total, events = svc_evenements.lister_evenements(
            db, default_context(),
            limit=limit, offset=offset, action=action, culture=culture,
            parcelle=parcelle, from_date=from_date, to_date=effective_to,
        )
        return {
            "total": total,
            "date_ref_effective": date_ref_effective.isoformat(),
            "evenements": [
                {
                    "id"         : e.id,
                    "date"       : str(e.date)[:10] if e.date else None,
                    "type_action": e.type_action,
                    "culture"    : e.culture,
                    "variete"    : e.variete,
                    "quantite"   : e.quantite,
                    "unite"      : e.unite,
                    "parcelle"   : e.parcelle,
                    "traitement" : e.traitement,
                }
                for e in events
            ],
        }
    finally:
        db.close()
