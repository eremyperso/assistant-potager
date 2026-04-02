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
echo "==> [1/5] Synchronisation du code..."
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
echo "==> [2/5] Installation des dépendances Python..."
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  cd ${REMOTE_DIR}
  python3 -m pip install --quiet --upgrade pip
  python3 -m pip install --quiet -r requirements.txt
"

# ── 3. Application des migrations SQL ──────────────────────────────────────────
echo "==> [3/5] Application des migrations SQL..."
ssh "${DEPLOY_HOST}" "
  set -euo pipefail
  cd ${REMOTE_DIR}
  export APP_ENV=prod
  set -a && source .env.prod && set +a
  for migration in migrations/migration_v*.sql; do
    echo \"    Applying \${migration}...\"
    psql \"\${DATABASE_URL}\" -f \"\${migration}\" 2>/dev/null || true
  done
"

# ── 4. Redémarrage du service systemd ──────────────────────────────────────────
echo "==> [4/5] Redémarrage du service systemd..."
ssh "${DEPLOY_HOST}" "sudo systemctl restart potager.service"

# ── 5. Smoke test ──────────────────────────────────────────────────────────────
echo "==> [5/5] Smoke test (attente 10s démarrage)..."
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
