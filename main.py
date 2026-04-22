"""
main.py — Assistant Potager v2 (moteur Groq, gratuit)
─────────────────────────────────────────────────────
Endpoints :
  GET  /health      → vérifier que l'API tourne
  POST /parse       → dicter une commande vocale
  POST /ask         → poser une question analytique
  GET  /stats       → stats JSON instantanées (sans LLM)
  GET  /historique  → derniers événements avec filtres
"""
import json
import subprocess
from datetime import date
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func
import os

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
from llm.groq_client import parse_commande, repondre_question
from utils.date_utils import parse_date
from llm.rag import add_to_rag

# ── Initialisation ─────────────────────────────────────────────────────────────
app = FastAPI(title="Assistant Potager 🌿", version=_APP_VERSION)
Base.metadata.create_all(bind=engine)   # crée la table si elle n'existe pas

# ── Fichiers statiques PWA ─────────────────────────────────────────────────────
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

    @app.get("/")
    def serve_pwa():
        return FileResponse("static/index.html")


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
def stats():
    """[US-002/CA4] Statistiques JSON avec stock agronomique différencié."""
    from utils.stock import calcul_stock_cultures, format_stock_stats_json, calcul_godets
    db = SessionLocal()
    try:
        total  = db.query(Evenement).count()
        stocks = calcul_stock_cultures(db)
        godets = calcul_godets(db)
        arrosages = (
            db.query(func.count(Evenement.id), func.sum(Evenement.duree))
            .filter(Evenement.type_action == "arrosage").first()
        )
        traitements = (
            db.query(Evenement.traitement, func.count(Evenement.id))
            .filter(Evenement.type_action == "traitement")
            .group_by(Evenement.traitement).all()
        )
        return {
            "total_evenements"  : total,
            "stock_par_culture" : format_stock_stats_json(stocks),
            "godets"            : [
                {
                    "culture":           v["culture"],
                    "variete":           v["variete"],
                    "nb_plants_godets":  v["nb_plants_godets"],
                    "nb_graines_semees": v["nb_graines_semees"],
                    "taux_reussite":     v["taux_reussite"],
                }
                for v in godets.values()
            ],
            "arrosages"         : {"nb": arrosages[0] or 0, "duree_totale_min": arrosages[1] or 0},
            "traitements"       : [{"produit": t or "?", "nb_applications": n} for t, n in traitements],
        }
    finally:
        db.close()


@app.get("/godets")
def get_godets():
    """
    [US_mise_en_godet] Retourne les plants actuellement en godet sans plantation postérieure.

    Un godet est considéré "en attente" si aucune plantation de la même culture
    n'a été enregistrée après la date de mise en godet.
    """
    db = SessionLocal()
    try:
        godets_all = (
            db.query(Evenement)
            .filter(Evenement.type_action == "mise_en_godet")
            .order_by(Evenement.date.desc())
            .all()
        )
        en_attente = []
        for g in godets_all:
            date_ref = g.date
            plantation = (
                db.query(Evenement)
                .filter(
                    Evenement.type_action == "plantation",
                    Evenement.culture == g.culture,
                )
            )
            if date_ref:
                plantation = plantation.filter(Evenement.date >= date_ref)
            if not plantation.first():
                en_attente.append({
                    "id":               g.id,
                    "culture":          g.culture,
                    "variete":          g.variete,
                    "nb_graines_semees": g.nb_graines_semees,
                    "nb_plants_godets": g.nb_plants_godets,
                    "date":             str(g.date)[:10] if g.date else None,
                    "commentaire":      g.commentaire,
                })
        return {"godets_en_attente": en_attente, "total": len(en_attente)}
    finally:
        db.close()



@app.get("/historique")
def historique(
    limit   : int = Query(default=20, le=100),
    action  : str = Query(default=None),
    culture : str = Query(default=None),
    parcelle: str = Query(default=None),
):
    """
    Retourne les derniers événements avec filtres optionnels.
    Ex: /historique?culture=tomate&action=recolte
    """
    db = SessionLocal()
    try:
        q = db.query(Evenement).order_by(Evenement.date.desc())
        if action:
            q = q.filter(Evenement.type_action == action)
        if culture:
            q = q.filter(Evenement.culture.ilike(f"%{culture}%"))
        if parcelle:
            q = q.join(Parcelle, Evenement.parcelle_id == Parcelle.id, isouter=True).filter(
                Parcelle.nom.ilike(f"%{parcelle}%")
            )

        events = q.limit(limit).all()
        return [
            {
                "id"        : e.id,
                "date"      : str(e.date)[:10] if e.date else None,
                "action"    : e.type_action,
                "culture"   : e.culture,
                "variete"   : e.variete,
                "quantite"  : e.quantite,
                "unite"     : e.unite,
                "parcelle"  : e.parcelle,
                "traitement": e.traitement,
                "texte"     : e.texte_original,
            }
            for e in events
        ]
    finally:
        db.close()


# ── Helpers ────────────────────────────────────────────────────────────────────
def _to_float(v):
    try:    return float(v) if v is not None else None
    except: return None

def _to_int(v):
    try:    return int(float(v)) if v is not None else None
    except: return None
