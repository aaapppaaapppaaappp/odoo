FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    ODOO_ADDONS_PATH=/opt/odoo/addons \
    ODOO_HTTP_INTERFACE=0.0.0.0 \
    ODOO_HTTP_PORT=8069 \
    ODOO_DB_HOST=db \
    ODOO_DB_PORT=5432 \
    ODOO_DB_USER=odoo

WORKDIR /opt/odoo

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    fonts-dejavu-core \
    fonts-font-awesome \
    fonts-inconsolata \
    fonts-roboto-unhinted \
    libffi-dev \
    libjpeg-dev \
    libldap2-dev \
    libmagic1 \
    libpq-dev \
    libsasl2-dev \
    libssl-dev \
    libxml2-dev \
    libxslt1-dev \
    pkg-config \
    postgresql-client \
    wkhtmltopdf \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

COPY . .

COPY docker/entrypoint.sh /usr/local/bin/odoo-entrypoint
RUN chmod +x /usr/local/bin/odoo-entrypoint \
 && addgroup --system odoo \
 && adduser --system --ingroup odoo --home /var/lib/odoo --no-create-home odoo \
 && mkdir -p /var/lib/odoo /var/log/odoo \
 && chown -R odoo:odoo /opt/odoo /var/lib/odoo /var/log/odoo

USER odoo

VOLUME ["/var/lib/odoo"]
EXPOSE 8069 8072

ENTRYPOINT ["/usr/local/bin/odoo-entrypoint"]
