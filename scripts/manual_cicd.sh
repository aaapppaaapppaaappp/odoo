#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.odoo.yml}"
IMAGE_NAME="${IMAGE_NAME:-odoo-local}"
IMAGE_TAG="${IMAGE_TAG:-dev}"
IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
ODOO_SERVICE="${ODOO_SERVICE:-odoo}"

PUSH_IMAGE=0
SYNC_DEPS=0
NO_BUILD=0

usage() {
  cat <<'EOF'
Manual CI/CD helper for Odoo.

Usage:
  scripts/manual_cicd.sh [ci|cd|all|status|logs|down] [options]

Commands:
  ci      Run dependency checks and build image
  cd      Deploy stack with docker compose
  all     Run ci then cd (default)
  status  Show docker compose service status
  logs    Tail logs from odoo service
  down    Stop and remove compose services

Options:
  --push       Push built image (used with ci/all)
  --sync-deps  Auto-sync missing addon dependencies before checks
  --no-build   Skip docker build in ci and skip --build in cd
  -h, --help   Show this help

Environment overrides:
  COMPOSE_FILE  (default: docker-compose.odoo.yml)
  IMAGE_NAME    (default: odoo-local)
  IMAGE_TAG     (default: dev)
  ODOO_SERVICE  (default: odoo)
EOF
}

command_exists() {
  command -v "$1" >/dev/null 2>&1
}

require_cmd() {
  if ! command_exists "$1"; then
    echo "Error: required command not found: $1" >&2
    exit 1
  fi
}

run() {
  echo "+ $*"
  "$@"
}

run_dependency_gate() {
  require_cmd python3
  if [[ "$SYNC_DEPS" -eq 1 ]]; then
    run python3 scripts/check_external_dependencies.py \
      --addons-dir addons \
      --requirements-core requirements.txt \
      --requirements-local requirements-local.txt \
      --sync
  fi
  run python3 scripts/check_external_dependencies.py \
    --addons-dir addons \
    --requirements-core requirements.txt \
    --requirements-local requirements-local.txt
}

run_ci() {
  require_cmd docker
  run_dependency_gate
  run docker compose -f "$COMPOSE_FILE" config >/dev/null
  if [[ "$NO_BUILD" -eq 0 ]]; then
    run docker build -f Dockerfile -t "$IMAGE_REF" .
    run docker run --rm "$IMAGE_REF" --help >/dev/null
    if [[ "$PUSH_IMAGE" -eq 1 ]]; then
      run docker push "$IMAGE_REF"
    fi
  fi
}

run_cd() {
  require_cmd docker
  if [[ "$NO_BUILD" -eq 0 ]]; then
    run docker compose -f "$COMPOSE_FILE" up -d --build
  else
    run docker compose -f "$COMPOSE_FILE" up -d
  fi
  run docker compose -f "$COMPOSE_FILE" ps
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

ACTION="${1:-all}"
if [[ $# -gt 0 ]]; then
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push)
      PUSH_IMAGE=1
      ;;
    --sync-deps)
      SYNC_DEPS=1
      ;;
    --no-build)
      NO_BUILD=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Error: unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
  shift
done

case "$ACTION" in
  ci)
    run_ci
    ;;
  cd)
    run_cd
    ;;
  all)
    run_ci
    run_cd
    ;;
  status)
    require_cmd docker
    run docker compose -f "$COMPOSE_FILE" ps
    ;;
  logs)
    require_cmd docker
    run docker compose -f "$COMPOSE_FILE" logs -f "$ODOO_SERVICE"
    ;;
  down)
    require_cmd docker
    run docker compose -f "$COMPOSE_FILE" down
    ;;
  *)
    echo "Error: unknown command: $ACTION" >&2
    usage
    exit 1
    ;;
esac
