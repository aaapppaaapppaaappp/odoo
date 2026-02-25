.PHONY: check-addon-deps sync-addon-deps build-odoo-image

PYTHON ?= python3
DOCKER ?= docker

check-addon-deps:
	$(PYTHON) scripts/check_external_dependencies.py \
		--addons-dir addons \
		--requirements-core requirements.txt \
		--requirements-local requirements-local.txt

sync-addon-deps:
	$(PYTHON) scripts/check_external_dependencies.py \
		--addons-dir addons \
		--requirements-core requirements.txt \
		--requirements-local requirements-local.txt \
		--sync

build-odoo-image: check-addon-deps
	$(DOCKER) build -f Dockerfile -t odoo-local:dev .
