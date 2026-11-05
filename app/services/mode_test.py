"""[US-288] Mode test conversationnel : remise à zéro d'un potager de test.

Le harnais `tests_conv/` joue des scénarios depuis un vrai compte Telegram. Entre deux
passages, il faut repartir d'un potager vide : c'est ce que fait `remettre_a_zero`,
déclenchée par la commande `/reset_test` du bot (qui vide en plus les états en attente
gardés en mémoire du processus, hors de portée du harnais).

Trois verrous, parce que cette fonction supprime des données :

* `APP_ENV` doit valoir `test` ;
* la base visée doit avoir « test » dans son nom (ou être SQLite) : un `.env.test` qui
  pointerait par erreur sur la base de dev est refusé ;
* seules les lignes du potager passé en argument sont touchées, jamais le compte, le
  potager lui-même ni ses membres.
"""
import logging
from urllib.parse import urlparse

from sqlalchemy import delete
from sqlalchemy.schema import sort_tables
from sqlalchemy.orm import Session

from app.config import APP_ENV, DATABASE_URL
from database.db import Base

log = logging.getLogger("potager")

#: Tables qui portent un `potager_id` mais ne se vident pas : le potager de test lui-même,
#: ses membres, et la consommation de jetons que le rapport relit après coup.
TABLES_CONSERVEES = frozenset({"potagers", "potager_membres", "conso_tokens"})


class ModeTestInactifError(Exception):
    """La remise à zéro est refusée hors du mode test."""


def base_de_test(url: str = DATABASE_URL) -> bool:
    """Vrai si l'URL vise SQLite ou une base dont le nom contient « test »."""
    if url.startswith("sqlite"):
        return True
    return "test" in urlparse(url).path.lower()


def actif() -> bool:
    return APP_ENV == "test" and base_de_test()


def remettre_a_zero(db: Session, potager_id: int) -> dict[str, int]:
    """Supprime les données du potager `potager_id`, table par table, enfants d'abord.

    Rend `{table: lignes supprimées}` pour les tables touchées. Une table qui refuse la
    suppression (clé étrangère d'une table sans `potager_id`) est journalisée et rendue
    avec -1 : la remise à zéro continue, le harnais voit l'anomalie dans la réponse."""
    if not actif():
        raise ModeTestInactifError(
            f"remise à zéro refusée : APP_ENV={APP_ENV!r}, base de test : {base_de_test()}"
        )
    # `users` et `potagers` se référencent l'un l'autre : on les écarte du tri (ils ne se vident pas)
    tables = [t for t in Base.metadata.tables.values() if t.name not in {"users", "potagers"}]
    bilan: dict[str, int] = {}
    for table in reversed(sort_tables(tables)):
        if table.name in TABLES_CONSERVEES or "potager_id" not in table.c:
            continue
        try:
            with db.begin_nested():
                n = db.execute(delete(table).where(table.c.potager_id == potager_id)).rowcount
        except Exception:  # noqa: BLE001 — on continue, on signale
            log.exception("[US-288] Remise à zéro : %s non vidée", table.name)
            bilan[table.name] = -1
            continue
        if n:
            bilan[table.name] = n
    db.commit()
    return bilan
