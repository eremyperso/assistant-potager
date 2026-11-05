"""Accès à la base de test : lire ce qu'un tour a écrit, semer l'état initial d'un scénario.

C'est le seul module du harnais qui importe `app` et `database` (donc exige un `.env.test`
complet). Il passe par les services de l'application pour créer compte, potager et
parcelles : le potager de test est semé comme le serait celui d'un vrai jardinier.
"""
from dataclasses import dataclass

from .assertions import Observation


class PotagerDeTestAbsent(Exception):
    pass


@dataclass(frozen=True)
class Instantane:
    evenement: int
    action: int
    echange: int


class BaseTest:
    def __init__(self, chat_id: int):
        # importés ici : `APP_ENV=test` est posé par `config` avant, et `--dry-run` n'arrive jamais ici
        from database.db import SessionLocal, tenant_scope
        from app.services import liaison_telegram, potager_actif
        self._SessionLocal, self._tenant_scope = SessionLocal, tenant_scope
        db = SessionLocal()
        try:
            user_id = liaison_telegram.resoudre_user_id_pour_chat(db, chat_id)
            if user_id is None:
                raise PotagerDeTestAbsent(
                    f"aucun compte lié au chat Telegram {chat_id} : lancer `python -m tests_conv seed`")
            self.ctx = potager_actif.resoudre_tenant_context(db, user_id)
        finally:
            db.close()

    # ── lecture ─────────────────────────────────────────────────────────────
    def _max_id(self, db, modele) -> int:
        from sqlalchemy import func
        return db.query(func.coalesce(func.max(modele.id), 0)).filter(
            modele.potager_id == self.ctx.potager_id).scalar()

    def instantane(self) -> Instantane:
        from database.models import ActionMenee, EchangeConversation, Evenement
        with self._tenant_scope(self.ctx.potager_id):
            db = self._SessionLocal()
            try:
                return Instantane(self._max_id(db, Evenement), self._max_id(db, ActionMenee),
                                  self._max_id(db, EchangeConversation))
            finally:
                db.close()

    def completer(self, obs: Observation, avant: Instantane) -> None:
        """Ajoute à `obs` ce que la base a vu apparaître depuis `avant`."""
        from database.models import ActionMenee, EchangeConversation, Evenement, Parcelle
        pid = self.ctx.potager_id
        with self._tenant_scope(pid):
            db = self._SessionLocal()
            try:
                for e in (db.query(Evenement).filter(Evenement.potager_id == pid, Evenement.id > avant.evenement)
                          .order_by(Evenement.id)):
                    parcelle = db.get(Parcelle, e.parcelle_id).nom if e.parcelle_id else None
                    obs.evenements.append({
                        "type_action": e.type_action, "culture": e.culture, "variete": e.variete,
                        "quantite": e.quantite, "unite": e.unite, "rang": e.rang, "parcelle": parcelle,
                    })
                obs.actions = (db.query(ActionMenee).filter(
                    ActionMenee.potager_id == pid, ActionMenee.id > avant.action,
                    ActionMenee.statut == "reussie").count())
                outils: list[str] = []
                for ech in (db.query(EchangeConversation).filter(
                        EchangeConversation.potager_id == pid, EchangeConversation.id > avant.echange)
                        .order_by(EchangeConversation.id)):
                    outils.extend(ech.outils or [])
                obs.outils = tuple(outils)
            finally:
                db.close()

    def jetons(self) -> dict[str, int]:
        """Somme des jetons consommés par ce potager (le rapport en donne la différence)."""
        from sqlalchemy import func
        from database.models import ConsoTokens
        with self._tenant_scope(self.ctx.potager_id):
            db = self._SessionLocal()
            try:
                e, s, c = db.query(func.coalesce(func.sum(ConsoTokens.tokens_in), 0),
                                   func.coalesce(func.sum(ConsoTokens.tokens_out), 0),
                                   func.coalesce(func.sum(ConsoTokens.tokens_cache), 0)
                                   ).filter(ConsoTokens.potager_id == self.ctx.potager_id).one()
                return {"entree": int(e), "sortie": int(s), "cache": int(c)}
            finally:
                db.close()

    # ── écriture ────────────────────────────────────────────────────────────
    def semer_parcelles(self, noms: tuple[str, ...]) -> None:
        from app.services import parcelles
        with self._tenant_scope(self.ctx.potager_id):
            db = self._SessionLocal()
            try:
                for nom in noms:
                    parcelles.creer_parcelle(db, self.ctx, nom)
            finally:
                db.close()


def creer_potager_de_test(chat_id: int, email: str = "conv-test@potager.invalid") -> str:
    """Crée (ou retrouve) le compte, le potager et la liaison du compte Telegram de test.

    Rend un message d'état. Idempotent : relancé, il constate et ne recrée rien."""
    import secrets
    from database.db import SessionLocal
    from database.models import User
    from app.services import auth, liaison_telegram, potager_actif, potagers
    db = SessionLocal()
    try:
        if liaison_telegram.resoudre_user_id_pour_chat(db, chat_id) is not None:
            return f"déjà en place : le chat {chat_id} est lié à un compte"
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = auth.inscrire_utilisateur(db, email, secrets.token_urlsafe(24), nom="Jardinier de test")
            user.email_verifie = True
            db.commit()
        if not potager_actif.lister_potagers_utilisateur(db, user.id):
            potagers.creer_potager(db, user.id, "Potager de test")
        code = liaison_telegram.creer_code_liaison(db, user.id).code
        liaison_telegram.lier_chat_id(db, code, chat_id)
        return f"créé : compte {email}, potager « Potager de test », chat {chat_id} lié"
    finally:
        db.close()
