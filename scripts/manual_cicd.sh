#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.odoo.yml}"
COMPOSE_ENV_FILE="${COMPOSE_ENV_FILE:-}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-}"
IMAGE_NAME="${IMAGE_NAME:-odoo-local}"
IMAGE_TAG="${IMAGE_TAG:-dev}"
IMAGE_REF="${IMAGE_NAME}:${IMAGE_TAG}"
ODOO_SERVICE="${ODOO_SERVICE:-odoo}"
DOCKERFILE_PATH="${DOCKERFILE_PATH:-Dockerfile}"
BUILD_CONTEXT="${BUILD_CONTEXT:-.}"

PUSH_IMAGE=0
SYNC_DEPS=0
SKIP_DEP_CHECK=0
NO_BUILD=0
PULL_IMAGES=0

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
  --skip-deps  Skip addon dependency checks in ci/all
  --no-build   Skip docker build in ci and skip --build in cd
  --pull       Pull latest images before cd/all (enabled automatically with --no-build)
  --compose-file Override Docker Compose file path
  --env-file   Pass a Docker Compose env file
  --project    Set Docker Compose project name
  --dockerfile Override Dockerfile path for image build
  --context    Override docker build context
  -h, --help   Show this help

Environment overrides:
  COMPOSE_FILE         (default: docker-compose.odoo.yml)
  COMPOSE_ENV_FILE     (default: unset)
  COMPOSE_PROJECT_NAME (default: unset)
  IMAGE_NAME           (default: odoo-local)
  IMAGE_TAG            (default: dev)
  ODOO_SERVICE         (default: odoo)
  DOCKERFILE_PATH      (default: Dockerfile)
  BUILD_CONTEXT        (default: .)
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
  printf '+'
  for arg in "$@"; do
    printf ' %q' "$arg"
  done
  printf '\n'
  "$@"
}

compose() {
  local args=()
  if [[ -n "$COMPOSE_PROJECT_NAME" ]]; then
    args+=(--project-name "$COMPOSE_PROJECT_NAME")
  fi
  if [[ -n "$COMPOSE_ENV_FILE" ]]; then
    args+=(--env-file "$COMPOSE_ENV_FILE")
  fi
  args+=(-f "$COMPOSE_FILE")
  args+=("$@")
  run docker compose "${args[@]}"
}

run_dependency_gate() {
  if [[ "$SKIP_DEP_CHECK" -eq 1 ]]; then
    return
  fi
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
  compose config >/dev/null
  if [[ "$NO_BUILD" -eq 0 ]]; then
    run docker build -f "$DOCKERFILE_PATH" -t "$IMAGE_REF" "$BUILD_CONTEXT"
    run docker run --rm "$IMAGE_REF" --help >/dev/null
    if [[ "$PUSH_IMAGE" -eq 1 ]]; then
      run docker push "$IMAGE_REF"
    fi
  fi
}

run_cd() {
  require_cmd docker
  # Allow prod compose files to consume these refs without extra export steps.
  export ODOO_IMAGE_REF="${ODOO_IMAGE_REF:-$IMAGE_REF}"
  export ODOO_PROXY_IMAGE_REF="${ODOO_PROXY_IMAGE_REF:-$IMAGE_REF}"
  if [[ "$PULL_IMAGES" -eq 1 || "$NO_BUILD" -eq 1 ]]; then
    compose pull
  fi
  if [[ "$NO_BUILD" -eq 0 ]]; then
    compose up -d --build
  else
    compose up -d
  fi
  compose ps
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
    --skip-deps)
      SKIP_DEP_CHECK=1
      ;;
    --no-build)
      NO_BUILD=1
      ;;
    --pull)
      PULL_IMAGES=1
      ;;
    --compose-file)
      if [[ $# -lt 2 ]]; then
        echo "Error: --compose-file requires a value" >&2
        usage
        exit 1
      fi
      COMPOSE_FILE="$2"
      shift
      ;;
    --env-file)
      if [[ $# -lt 2 ]]; then
        echo "Error: --env-file requires a value" >&2
        usage
        exit 1
      fi
      COMPOSE_ENV_FILE="$2"
      shift
      ;;
    --project)
      if [[ $# -lt 2 ]]; then
        echo "Error: --project requires a value" >&2
        usage
        exit 1
      fi
      COMPOSE_PROJECT_NAME="$2"
      shift
      ;;
    --dockerfile)
      if [[ $# -lt 2 ]]; then
        echo "Error: --dockerfile requires a value" >&2
        usage
        exit 1
      fi
      DOCKERFILE_PATH="$2"
      shift
      ;;
    --context)
      if [[ $# -lt 2 ]]; then
        echo "Error: --context requires a value" >&2
        usage
        exit 1
      fi
      BUILD_CONTEXT="$2"
      shift
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
    compose ps
    ;;
  logs)
    require_cmd docker
    compose logs -f "$ODOO_SERVICE"
    ;;
  down)
    require_cmd docker
    compose down
    ;;
  *)
    echo "Error: unknown command: $ACTION" >&2
    usage
    exit 1
    ;;
esac
