#!/usr/bin/env bash
set -euo pipefail

ODOO_ADDONS_PATH="${ODOO_ADDONS_PATH:-/opt/odoo/addons}"
ODOO_HTTP_INTERFACE="${ODOO_HTTP_INTERFACE:-0.0.0.0}"
ODOO_HTTP_PORT="${ODOO_HTTP_PORT:-8069}"
ODOO_DB_HOST="${ODOO_DB_HOST:-db}"
ODOO_DB_PORT="${ODOO_DB_PORT:-5432}"
ODOO_DB_USER="${ODOO_DB_USER:-odoo}"
ODOO_DB_PASSWORD="${ODOO_DB_PASSWORD:-odoo}"
ODOO_DB_NAME="${ODOO_DB_NAME:-}"
ODOO_DB_FILTER="${ODOO_DB_FILTER:-}"

ODOO_ARGS=(
  "--addons-path=${ODOO_ADDONS_PATH}"
  "--http-interface=${ODOO_HTTP_INTERFACE}"
  "--http-port=${ODOO_HTTP_PORT}"
  "--db_host=${ODOO_DB_HOST}"
  "--db_port=${ODOO_DB_PORT}"
  "--db_user=${ODOO_DB_USER}"
  "--db_password=${ODOO_DB_PASSWORD}"
)

if [[ -n "${ODOO_DB_NAME}" ]]; then
  ODOO_ARGS+=("-d" "${ODOO_DB_NAME}")
  if [[ -z "${ODOO_DB_FILTER}" ]]; then
    ODOO_DB_FILTER="^${ODOO_DB_NAME}$"
  fi
fi

if [[ -n "${ODOO_DB_FILTER}" ]]; then
  ODOO_ARGS+=("--db-filter=${ODOO_DB_FILTER}")
fi

exec ./odoo-bin "${ODOO_ARGS[@]}" "$@"
