FROM odoo:19.0-20260217

USER root

COPY requirements-local.txt /tmp/
# Bypass the PEP 668 "externally managed" error
ENV PIP_BREAK_SYSTEM_PACKAGES=1

# Just install your requirements directly
RUN pip install --ignore-installed -r /tmp/requirements-local.txt

USER odoo