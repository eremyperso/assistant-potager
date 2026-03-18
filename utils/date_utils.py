"""
date_utils.py — Convertit la date extraite par Groq en objet datetime Python.
Gère : "2026-03-09" (ISO), None (→ aujourd'hui)
"""
from datetime import datetime, date


def parse_date(val) -> datetime:
    """
    Retourne un datetime exploitable pour PostgreSQL.
    - val = "2026-03-09" → datetime(2026, 3, 9)
    - val = None ou invalide → datetime.today() (sécurité)
    """
    if not val:
        return datetime.combine(date.today(), datetime.min.time())
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d")
    except ValueError:
        return datetime.combine(date.today(), datetime.min.time())
