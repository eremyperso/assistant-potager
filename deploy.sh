#!/usr/bin/env bash
# deploy.sh — Déploiement de l'Assistant Potager sur Scaleway
# Usage : ./deploy.sh [user@host]
# Les secrets NE SONT PAS transmis ici — ils sont déjà sur le serveur dans /opt/potager/.env.prod
#
# Prérequis locaux :
#   - SSH configuré (clé publique déposée sur le serveur)
#   - Variables d'environnement : DEPLOY_HOST (ou argument $1)
#
# Prérequis serveur :
#   - Python 3.11+, pip, git installés
#   - Fichier /opt/potager/.env.prod créé manuellement
#   - Service systemd potager.service installé (voir infra/potager.service)

set -euo pipefail

# ── Configuration ──────────────────────────────────────────────────────────────
DEPLOY_HOST="${1:-${DEPLOY_HOST:?'Variable DEPLOY_HOST non définie. Usage: ./deploy.sh user@host'}}"
REMOTE_DIR="/opt/potager"
BRANCH="${DEPLOY_BRANCH:-main}"

echo "==> Déploiement sur ${DEPLOY_HOST} (branche: ${BRANCH})"

# ── 1. Synchronisation du code ─────────────────────────────────────────────────
echo "==> [1/6] Synchronisation du code..."
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  if [ ! -d '${REMOTE_DIR}/.git' ]; then
    git clone https://github.com/\$(git -C ~ config user.name 2>/dev/null || echo 'owner')/sandbox-potager.git ${REMOTE_DIR}
  fi
  cd ${REMOTE_DIR}
  git fetch origin
  git checkout ${BRANCH}
  git pull origin ${BRANCH}
"

# ── 2. Installation des dépendances ────────────────────────────────────────────
echo "==> [2/6] Installation des dépendances Python..."
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  cd ${REMOTE_DIR}
  python3 -m pip install --quiet --upgrade pip
  python3 -m pip install --quiet -r requirements.txt
"

# ── 3. Application des migrations SQL ──────────────────────────────────────────
echo "==> [3/6] Application des migrations SQL..."
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  cd ${REMOTE_DIR}
  export APP_ENV=prod
  set -a && source .env.prod && set +a
  for migration in \$(ls migrations/migration_v*.sql | sort -t v -k2 -n); do
    echo \"    Applying \${migration}...\"
    psql \"\${DATABASE_URL}\" -v ON_ERROR_STOP=1 -f \"\${migration}\"
  done
"

# ── 4. Corpus de connaissance ──────────────────────────────────────────────────
# [US-099 / CA10] Le corpus se déploie comme une migration : il fait partie de
# la livraison, pas d'une opération manuelle à côté. Une fiche corrigée dans le
# dépôt mais jamais réingérée resterait fausse en production — c'est exactement
# ce que le CA9 interdit.
#
# Deux propriétés le rendent sûr à jouer à chaque déploiement : l'ingestion est
# IDEMPOTENTE (empreinte SHA-256 par fichier — même contenu, aucune écriture,
# pas même un UPDATE), et le contrôle de cohérence qui la précède échoue avant
# d'avoir rien écrit.
#
# ATTENTION RLS : une fiche GLOBALE (potager_id NULL) ne s'écrit qu'avec le rôle
# PROPRIÉTAIRE de la base. On réutilise donc le même DATABASE_URL que les
# migrations ci-dessus, jamais un rôle applicatif.
#
# ATTENTION Premiere mise en service de l'étage : le seuil de confiance doit être
# étalonné contre PostgreSQL AVANT d'ouvrir l'étage — procédure complète dans
# docs/RUNBOOK_ALIMENTATION_SOCLE_CONNAISSANCE.md §5. Ce pas de déploiement
# entretient un corpus déjà en service, il ne remplace pas cette mise en route.
echo "==> [4/6] Contrôle et ingestion du corpus de connaissance..."
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  cd ${REMOTE_DIR}
  export APP_ENV=prod
  set -a && source .env.prod && set +a
  python3 tools/controler_aide_corpus.py
  python3 tools/ingerer_connaissance.py --strict --elaguer
"

# ── 5. Redémarrage du service systemd ──────────────────────────────────────────
echo "==> [5/6] Redémarrage du service systemd..."
ssh "${DEPLOY_HOST}" "sudo systemctl restart potager.service"

# ── 6. Smoke test ──────────────────────────────────────────────────────────────
echo "==> [6/6] Smoke test (attente 10s démarrage)..."
sleep 10
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  status=\$(systemctl is-active potager.service)
  if [ \"\${status}\" != 'active' ]; then
    echo 'ERREUR: Le service potager.service n est pas actif (\${status})'
    systemctl status potager.service --no-pager
    exit 1
  fi
  echo 'Service potager.service: actif'
  # Vérification du endpoint /health
  export APP_ENV=prod
  set -a && source /opt/potager/.env.prod && set +a
  curl --fail --silent --max-time 10 http://localhost:8000/health | grep -q 'ok' && echo 'Health check: OK' || (echo 'ERREUR: health check échoué'; exit 1)
"

echo ""
echo "==> Déploiement terminé avec succès ! Bot @AssistantPotagerBot actif."
