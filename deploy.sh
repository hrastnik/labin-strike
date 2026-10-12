#!/usr/bin/env bash
# Builds locally, rsyncs the project to the VPS and restarts the game server there.
#   ./deploy.sh              build + sync + install prod deps (if the lockfile changed) + restart
#   SKIP_BUILD=1 ./deploy.sh reuse the existing dist/
# The target comes from DEPLOY_HOST / DEPLOY_DIR, either in the environment or in a gitignored
# .deploy.env next to this script, e.g.
#   DEPLOY_HOST=user@example.com
#   DEPLOY_DIR=/srv/labin-strike
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"
[[ -f .deploy.env ]] && source .deploy.env
: "${DEPLOY_HOST:?set DEPLOY_HOST (env or .deploy.env)}"
: "${DEPLOY_DIR:?set DEPLOY_DIR (env or .deploy.env)}"

step() { printf '\033[1;33m==> %s\033[0m\n' "$*"; }

# The VPS is memory constrained, so the client is always built here and shipped as dist/.
if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
  step "Building client"
  npm run build
fi
[[ -f dist/index.html ]] || { echo "dist/ is missing - run npm run build" >&2; exit 1; }

step "Syncing to ${DEPLOY_HOST}:${DEPLOY_DIR}"
ssh "$DEPLOY_HOST" "mkdir -p '$DEPLOY_DIR'"
# excluded paths are also protected from --delete, so the remote pid/log files survive
rsync -az --delete \
  --exclude node_modules \
  --exclude .git \
  --exclude server.pid \
  --exclude server.log \
  --exclude .DS_Store \
  --exclude .deploy.env \
  --exclude 'tools/blender/*.blend1' \
  --exclude tools/blender/textures/ph \
  --exclude tools/sky_src \
  ./ "${DEPLOY_HOST}:${DEPLOY_DIR}/"

step "Installing production dependencies and restarting"
ssh "$DEPLOY_HOST" "bash -s" -- "$DEPLOY_DIR" <<'REMOTE'
set -euo pipefail
cd "$1"
lock_hash="$(sha256sum package-lock.json | cut -d' ' -f1)"
if [[ ! -d node_modules || "$(cat node_modules/.deploy-lock-hash 2>/dev/null)" != "$lock_hash" ]]; then
  echo "package-lock.json changed: npm ci --omit=dev"
  npm ci --omit=dev --no-audit --no-fund
  echo "$lock_hash" > node_modules/.deploy-lock-hash
else
  echo "Dependencies unchanged"
fi
chmod +x server.sh
./server.sh restart
sleep 1
./server.sh status
curl -fsS "http://127.0.0.1:7344/healthz" && echo
REMOTE

step "Deployed: http://${DEPLOY_HOST}:7344"
