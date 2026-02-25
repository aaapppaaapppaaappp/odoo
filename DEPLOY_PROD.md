# Production Deploy (GHCR Pull Model)

## 1) Build and publish to GHCR via GitHub Actions

Workflow: `.github/workflows/ghcr-images.yml`

It pushes both images on every `main` push (and `v*` tag):
- `ghcr.io/<org>/odoo:sha-<git-sha>`
- `ghcr.io/<org>/odoo-proxy:sha-<git-sha>`
- branch/tag refs (for example `main`)
- `latest` on default branch

Use the immutable `sha-<git-sha>` tag in production env files.

## 2) On the server, login to GHCR if packages are private

If your GHCR packages are private, create a token with package read access
and login once:

```bash
echo "$GHCR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
```

If packages are public, this step is not required.

## 3) Prepare server env files once

```bash
cp env.odoo.prod.example .env.odoo.prod
cp env.odoo-proxy.prod.example .env.odoo-proxy.prod
```

Set at least:
- `ODOO_IMAGE_REF` and `ODOO_PROXY_IMAGE_REF` to `ghcr.io/<org>/<image>:sha-<git-sha>`
- database password and API secrets

## 4) Deploy Odoo stack (pull only)

```bash
scripts/manual_cicd.sh cd \
  --no-build \
  --pull \
  --env-file .env.odoo.prod \
  --project odoo-prod \
  --compose-file docker-compose.odoo.prod.yml
```

## 5) Deploy Odoo proxy (pull only)

```bash
scripts/manual_cicd.sh cd \
  --no-build \
  --pull \
  --env-file .env.odoo-proxy.prod \
  --project odoo-proxy-prod \
  --compose-file docker-compose.odoo-proxy.prod.yml
```

## 6) Rollback

Change `ODOO_IMAGE_REF` / `ODOO_PROXY_IMAGE_REF` in env files to an older `sha-*` tag, then rerun the same deploy commands.
