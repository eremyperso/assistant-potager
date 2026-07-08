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
from sqlalchemy import func
from sqlalchemy.orm import joinedload

# ── Version [US-008] ────────────────────────────────────────────────────────────
def _lire_version() -> str:
    try:
        _base = os.path.dirname(os.path.abspath(__file__))
        with open(os.path.join(_base, "VERSION"), encoding="utf-8") as _f:
            return _f.read().strip()
    except OSError:
        return "inconnue"

_APP_VERSION = _lire_version()

from database.db import Base, engine, SessionLocal
from database.models import Evenement, CultureConfig, Parcelle
from utils.actions import normalize_action
from utils.parcelles import resolve_parcelle
from utils.stock import calcul_stock_cultures, format_stock_stats_json
from llm.groq_client import parse_commande, repondre_question, transcribe_audio, classify_intent_pwa
from utils.date_utils import parse_date
from llm.rag import add_to_rag

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
    nb = db.query(Evenement).count()
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
        cultures = db.query(CultureConfig).order_by(CultureConfig.nom).all()
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
    saved = []
    try:
        for parsed in items:
            nom_parcelle = parsed.get("parcelle")
            parcelle_obj = resolve_parcelle(db, nom_parcelle) if nom_parcelle else None
            event = Evenement(
                type_action       = normalize_action(parsed.get("action")),
                culture           = parsed.get("culture"),
                variete           = parsed.get("variete"),
                quantite          = _to_float(parsed.get("quantite")),
                unite             = parsed.get("unite"),
                parcelle_id       = parcelle_obj.id if parcelle_obj else None,
                rang              = parsed.get("rang"),
                duree             = _to_int(parsed.get("duree_minutes")),
                traitement        = parsed.get("traitement"),
                commentaire       = parsed.get("commentaire"),
                texte_original    = req.texte,
                date              = parse_date(parsed.get("date")),
                nb_graines_semees = _to_int(parsed.get("nb_graines_semees")),
                nb_plants_godets  = _to_int(parsed.get("nb_plants_godets")),
            )
            
            # Héritage automatique du type d'organe récolté depuis culture_config
            if event.culture:
                config = db.query(CultureConfig).filter(CultureConfig.nom == event.culture).first()
                if config:
                    event.type_organe_recolte = config.type_organe_recolte
            
            # [US-001] Héritage automatique du type d'organe récolté
            if event.culture:
                cfg = db.query(CultureConfig).filter(CultureConfig.nom == event.culture).first()
                if cfg:
                    event.type_organe_recolte = cfg.type_organe_recolte
            db.add(event)
            db.commit()
            db.refresh(event)
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
        db = SessionLocal()
        try:
            events = db.query(Evenement).order_by(Evenement.date).all()
            if not events:
                reponse = "Aucune donnée enregistrée pour l'instant. Commencez par dicter quelques actions !"
            else:
                data = [
                    {
                        "id"         : e.id,
                        "date"       : str(e.date)[:10] if e.date else None,
                        "action"     : e.type_action,
                        "culture"    : e.culture,
                        "variete"    : e.variete,
                        "quantite"   : e.quantite,
                        "unite"      : e.unite,
                        "parcelle"   : e.parcelle,
                        "rang"       : e.rang,
                        "duree_min"  : e.duree,
                        "traitement" : e.traitement,
                        "commentaire": e.commentaire,
                    }
                    for e in events
                ]
                try:
                    reponse = repondre_question(texte, json.dumps(data, ensure_ascii=False))
                except Exception as e:
                    raise HTTPException(status_code=502, detail=f"Erreur Groq : {e}")
        finally:
            db.close()

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
        saved_parsed: list[dict] = []
        try:
            for parsed in items:
                nom_parcelle = parsed.get("parcelle")
                parcelle_obj = resolve_parcelle(db, nom_parcelle) if nom_parcelle else None
                event = Evenement(
                    type_action       = normalize_action(parsed.get("action")),
                    culture           = parsed.get("culture"),
                    variete           = parsed.get("variete"),
                    quantite          = _to_float(parsed.get("quantite")),
                    unite             = parsed.get("unite"),
                    parcelle_id       = parcelle_obj.id if parcelle_obj else None,
                    rang              = parsed.get("rang"),
                    duree             = _to_int(parsed.get("duree_minutes")),
                    traitement        = parsed.get("traitement"),
                    commentaire       = parsed.get("commentaire"),
                    texte_original    = texte,
                    date              = parse_date(parsed.get("date")),
                    nb_graines_semees = _to_int(parsed.get("nb_graines_semees")),
                    nb_plants_godets  = _to_int(parsed.get("nb_plants_godets")),
                )
                if event.culture:
                    cfg = db.query(CultureConfig).filter(CultureConfig.nom == event.culture).first()
                    if cfg:
                        event.type_organe_recolte = cfg.type_organe_recolte
                db.add(event)
                db.commit()
                db.refresh(event)
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
    db = SessionLocal()
    try:
        events = db.query(Evenement).order_by(Evenement.date).all()
        if not events:
            return {"reponse": "Aucune donnée enregistrée pour l'instant. Commencez par dicter quelques actions !"}

        # Sérialiser l'historique pour le contexte LLM
        data = [
            {
                "id"         : e.id,
                "date"       : str(e.date)[:10] if e.date else None,
                "action"     : e.type_action,
                "culture"    : e.culture,
                "variete"    : e.variete,
                "quantite"   : e.quantite,
                "unite"      : e.unite,
                "parcelle"   : e.parcelle,
                "rang"       : e.rang,
                "duree_min"  : e.duree,
                "traitement" : e.traitement,
                "commentaire": e.commentaire,
            }
            for e in events
        ]
        contexte = json.dumps(data, ensure_ascii=False)

        try:
            reponse = repondre_question(req.texte, contexte)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Erreur Groq API : {e}")

        return {
            "reponse"               : reponse,
            "nb_evenements_analyses": len(events)
        }
    finally:
        db.close()


@app.get("/stats")
def stats(date_ref: date = Query(default=None)):
    """[US-002/CA4] Statistiques JSON avec stock agronomique différencié.
    [US-030] date_ref optionnel (YYYY-MM-DD) : reconstitue l'état à une date passée."""
    from utils.stock import calcul_stock_cultures, format_stock_stats_json, calcul_godets, calcul_semis
    today = date.today()
    dr = min(date_ref, today) if date_ref else None   # None = pas de filtre = comportement par défaut
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        total_q = db.query(func.count(Evenement.id))
        if dr:
            from datetime import datetime as _dt
            total_q = total_q.filter(Evenement.date <= _dt(dr.year, dr.month, dr.day, 23, 59, 59))
        total  = total_q.scalar() or 0
        stocks = calcul_stock_cultures(db, dr)
        godets = calcul_godets(db, date_ref=dr)
        traitements = (
            db.query(Evenement.traitement, func.count(Evenement.id))
            .filter(Evenement.type_action == "traitement")
            .group_by(Evenement.traitement).all()
        )
        # Origine par culture : "pépinière" si mise_en_godet existe, sinon "pied_acheté"
        cultures_avec_godet = {
            row[0].lower() for row in
            db.query(Evenement.culture)
            .filter(Evenement.type_action == "mise_en_godet")
            .filter(Evenement.culture.isnot(None))
            .distinct().all()
        }

        # [US-026 / semis pleine terre] Semis directement associés à une parcelle
        semis_data = calcul_semis(db, dr)
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

        stock_enrichi = format_stock_stats_json(stocks)
        for entry in stock_enrichi:
            nom = (entry.get("culture") or "").lower()
            if nom in cultures_avec_godet:
                entry["origine"] = "pépinière"
            elif nom in cultures_semis_pt:
                entry["origine"] = "semis_pleine_terre"
            else:
                entry["origine"] = "pied_acheté"

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
    today = date.today()
    annee_eff = annee or today.year
    dr = min(date_ref, today) if date_ref else None
    db = SessionLocal()
    try:
        data = calcul_rendement_mensuel(db, annee_eff, dr)
        return {"annee": annee_eff, **data}
    finally:
        db.close()


@app.get("/stats/activite")
def get_activite(annee: int = Query(default=None), date_ref: date = Query(default=None)):
    """[US_Stats_activite_potager] Heatmap d'activité quotidienne (nb événements/jour).
    [US-030] date_ref optionnel (YYYY-MM-DD) : plafonne la borne haute à cette date."""
    from utils.stock import calcul_activite_quotidienne
    today = date.today()
    annee_eff = annee or today.year
    dr = min(date_ref, today) if date_ref else None
    db = SessionLocal()
    try:
        jours = calcul_activite_quotidienne(db, annee_eff, dr)
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
    from utils.parcelles import calcul_occupation_parcelles, get_all_parcelles

    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        parcelles     = get_all_parcelles(db)
        occupation    = calcul_occupation_parcelles(db, dr)

        # Index surface_m2 par nom de culture (insensible à la casse)
        configs = db.query(CultureConfig).all()
        surface_par_culture = {
            c.nom.lower(): (c.surface_m2 or 0.0) for c in configs
        }

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
                }
                for c in cultures_raw
            ]

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

            result.append({
                "nom":           p.nom,
                "exposition":    p.exposition,
                "superficie_m2": p.superficie_m2,
                "cultures":      cultures,
                "occupation_pct": occupation_pct,
            })

        return {"parcelles": result, "total": len(result), "date_ref_effective": date_ref_effective.isoformat()}
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
    today = date.today()
    dr = min(date_ref, today) if date_ref else None
    date_ref_effective = dr or today
    db = SessionLocal()
    try:
        tous = calcul_godets(db, include_epuises=True, date_ref=dr)
        en_attente  = [v for v in tous.values() if v["stock_residuel_godet"] > 0]
        tout_plante = [v for v in tous.values() if v["stock_residuel_godet"] == 0]
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
        culture_lower = culture.lower()

        # 1. Godets pour cette culture/variété
        godet_q = (
            db.query(Evenement)
            .filter(Evenement.type_action == "mise_en_godet")
            .filter(func.lower(Evenement.culture) == culture_lower)
        )
        if variete:
            godet_q = godet_q.filter(func.lower(Evenement.variete) == variete.lower())
        else:
            godet_q = godet_q.filter(Evenement.variete.is_(None))
        godet_events = godet_q.order_by(Evenement.date.asc()).all()

        godet_ids = {str(g.id) for g in godet_events}

        # 2. Semis parents distincts via origine_graines_id
        semis_ids = {g.origine_graines_id for g in godet_events if g.origine_graines_id}
        semis_events = []
        if semis_ids:
            semis_events = (
                db.query(Evenement)
                .options(joinedload(Evenement.parcelle_rel))
                .filter(Evenement.id.in_(semis_ids))
                .order_by(Evenement.date.asc())
                .all()
            )

        # 3. Plantations liées via source_evenement_ids
        plantation_candidates = (
            db.query(Evenement)
            .options(joinedload(Evenement.parcelle_rel))
            .filter(Evenement.type_action == "plantation")
            .filter(func.lower(Evenement.culture) == culture_lower)
            .filter(Evenement.source_evenement_ids.isnot(None))
            .order_by(Evenement.date.asc())
            .all()
        )
        linked_plantations = [
            p for p in plantation_candidates
            if godet_ids & set(p.source_evenement_ids.split(";"))
        ]

        # 4. Ventes (vendu) pour cette culture/variété
        vendu_q = (
            db.query(Evenement)
            .filter(Evenement.type_action == "vendu")
            .filter(func.lower(Evenement.culture) == culture_lower)
        )
        if variete:
            vendu_q = vendu_q.filter(func.lower(Evenement.variete) == variete.lower())
        else:
            vendu_q = vendu_q.filter(Evenement.variete.is_(None))
        vendu_events = vendu_q.order_by(Evenement.date.asc()).all()

        # 5. Pertes godet (perte_godet) pour cette culture/variété
        perte_q = (
            db.query(Evenement)
            .filter(Evenement.type_action == "perte_godet")
            .filter(func.lower(Evenement.culture) == culture_lower)
        )
        if variete:
            perte_q = perte_q.filter(func.lower(Evenement.variete) == variete.lower())
        else:
            perte_q = perte_q.filter(Evenement.variete.is_(None))
        perte_events = perte_q.order_by(Evenement.date.asc()).all()

        # 6. Taux de germination (plants godets / graines semis parents)
        total_plants  = sum(g.nb_plants_godets or 0 for g in godet_events)
        total_graines = sum(int(s.quantite or 0) for s in semis_events)
        taux = round(total_plants / total_graines * 100) if total_graines and total_plants else None

        return {
            "culture": culture,
            "variete": variete,
            "semis": [
                {
                    "id":        s.id,
                    "date":      str(s.date)[:10],
                    "nb_graines": int(s.quantite or 0),
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
        q = (
            db.query(Evenement)
            .options(joinedload(Evenement.parcelle_rel))
            .order_by(Evenement.date.desc())
        )
        if action:
            q = q.filter(Evenement.type_action == action)
        if culture:
            q = q.filter(Evenement.culture.ilike(f"%{culture}%"))
        if parcelle:
            q = q.join(Parcelle, Evenement.parcelle_id == Parcelle.id, isouter=True).filter(
                Parcelle.nom.ilike(f"%{parcelle}%")
            )
        if from_date:
            q = q.filter(Evenement.date >= from_date)
        if effective_to:
            q = q.filter(Evenement.date <= effective_to + " 23:59:59")

        total  = q.count()
        events = q.offset(offset).limit(limit).all()
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


# ── Helpers ────────────────────────────────────────────────────────────────────
def _to_float(v):
    try:    return float(v) if v is not None else None
    except: return None

def _to_int(v):
    try:    return int(float(v)) if v is not None else None
    except: return None
