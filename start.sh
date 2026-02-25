#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f "./odoo-bin" ]]; then
  echo "Error: odoo-bin not found in $ROOT_DIR" >&2
  exit 1
fi

CONDA_ENV_NAME="${CONDA_ENV_NAME:-odoo-env}"
CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"

if [[ ! -f "$CONDA_SH" ]] && command -v conda >/dev/null 2>&1; then
  CONDA_BASE="$(conda info --base 2>/dev/null || true)"
  if [[ -n "$CONDA_BASE" && -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
    CONDA_SH="$CONDA_BASE/etc/profile.d/conda.sh"
  fi
fi

if [[ ! -f "$CONDA_SH" ]]; then
  echo "Error: conda.sh not found. Set CONDA_SH or install Conda." >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$CONDA_SH"
conda activate "$CONDA_ENV_NAME"

ODOO_DB_NAME="${ODOO_DB_NAME:-odoo}"
ODOO_DB_USER="${ODOO_DB_USER:-odoo}"
ODOO_DB_PASSWORD="${ODOO_DB_PASSWORD:-odoo}"
ODOO_DB_PORT="${ODOO_DB_PORT:-5432}"
ODOO_POSTGRES_CONTAINER="${ODOO_POSTGRES_CONTAINER:-odoo-postgres}"

if [[ -z "${ODOO_DB_HOST:-}" ]] && command -v docker >/dev/null 2>&1; then
  if [[ "$(docker inspect -f '{{.State.Running}}' "$ODOO_POSTGRES_CONTAINER" 2>/dev/null || true)" == "true" ]]; then
    ODOO_DB_HOST="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$ODOO_POSTGRES_CONTAINER" 2>/dev/null || true)"
  fi
fi
ODOO_DB_HOST="${ODOO_DB_HOST:-172.17.0.2}"

ODOO_ADDONS_PATH="${ODOO_ADDONS_PATH:-addons}"
ODOO_HTTP_INTERFACE="${ODOO_HTTP_INTERFACE:-0.0.0.0}"
ODOO_HTTP_PORT="${ODOO_HTTP_PORT:-8069}"
ODOO_DB_FILTER="${ODOO_DB_FILTER:-^${ODOO_DB_NAME}$}"

echo "Starting Odoo with:"
echo "  conda env:      $CONDA_ENV_NAME"
echo "  db host:        $ODOO_DB_HOST"
echo "  db port:        $ODOO_DB_PORT"
echo "  db user:        $ODOO_DB_USER"
echo "  db name:        $ODOO_DB_NAME"
echo "  http interface: $ODOO_HTTP_INTERFACE"
echo "  http port:      $ODOO_HTTP_PORT"

exec ./odoo-bin \
  --addons-path="$ODOO_ADDONS_PATH" \
  --http-interface="$ODOO_HTTP_INTERFACE" \
  --http-port="$ODOO_HTTP_PORT" \
  --db_host="$ODOO_DB_HOST" \
  --db_port="$ODOO_DB_PORT" \
  --db_user="$ODOO_DB_USER" \
  --db_password="$ODOO_DB_PASSWORD" \
  --db-filter="$ODOO_DB_FILTER" \
  -d "$ODOO_DB_NAME" \
  "$@"
