# Odoo Applicant Proxy

Thin adapter for Chatwoot custom tools:
- `POST /api/applicants/lookup`
- `POST /api/applicants/create`

It accepts simple JSON and translates to Odoo `json/2` model methods for `hr.applicant`.

## Environment Variables

- `ODOO_BASE_URL` (required) e.g. `http://host.docker.internal:8069`
- `ODOO_DATABASE` (required) target Odoo DB name
- `ODOO_API_KEY` (required) Odoo API key (scope: RPC)
- `ODOO_TIMEOUT_SECONDS` (optional, default `20`)
- `PROXY_BEARER_TOKEN` (optional) if set, incoming requests must include:
  - `Authorization: Bearer <PROXY_BEARER_TOKEN>`

## Run with Docker Compose

At repo root:

```bash
cp services/odoo_proxy/.env.example .env.odoo-proxy
# edit .env.odoo-proxy values
set -a && source .env.odoo-proxy && set +a
docker compose -f docker-compose.odoo-proxy.yml up -d --build
```

## Health Check

```bash
curl -sS http://localhost:8088/health
```

## Lookup API

`POST /api/applicants/lookup`

Request example:

```json
{
  "partner_name": "John",
  "email_from": "john@example.com",
  "partner_phone": "415",
  "job_id": 3,
  "limit": 5
}
```

Response example:

```json
{
  "count": 1,
  "items": [
    {
      "id": 42,
      "partner_name": "John Doe"
    }
  ]
}
```

## Create API

`POST /api/applicants/create`

Request example:

```json
{
  "partner_name": "Jane Doe",
  "email_from": "jane@example.com",
  "partner_phone": "+14155550123",
  "job_id": 3,
  "applicant_notes": "Created via Chatwoot tool",
  "categ_ids": [1, 4]
}
```

Response example:

```json
{
  "id": 57,
  "record": {
    "id": 57,
    "partner_name": "Jane Doe"
  }
}
```

## Chatwoot Custom Tool Setup

Create two tools that call this proxy instead of Odoo directly.

### 1) Applicant Lookup Tool
- Method: `POST`
- URL: `http://<proxy-host>:8088/api/applicants/lookup`
- Auth: Bearer token (use `PROXY_BEARER_TOKEN` if you enabled it)

Body template:

```json
{
  "partner_name": "{{ partner_name }}",
  "email_from": "{{ email_from }}",
  "partner_phone": "{{ partner_phone }}",
  "limit": 5
}
```

If you need position-specific filtering, add `"job_id": 123` explicitly.

### 2) Applicant Create Tool
- Method: `POST`
- URL: `http://<proxy-host>:8088/api/applicants/create`
- Auth: Bearer token (use `PROXY_BEARER_TOKEN` if you enabled it)

Body template:

```json
{
  "partner_name": "{{ partner_name }}",
  "email_from": "{{ email_from }}",
  "partner_phone": "{{ partner_phone }}",
  "applicant_notes": "{{ applicant_notes }}"
}
```

Add `"job_id": 123` only when the tool has a guaranteed numeric value.
