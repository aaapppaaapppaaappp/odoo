# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation

Official docs: <https://www.odoo.com/documentation/19.0/index.html>

## Repository Overview

Odoo 19.0 — a modular, open-source ERP/CRM platform written in Python. The codebase has two main parts: the **core framework** (`odoo/`) and **~610 addons** (`addons/`), each a self-contained business module.

## Common Commands

### Running the Server

```bash
./odoo-bin --addons-path=addons -d <database_name>
```

### Running Tests

```bash
# Run all tests for a specific module
./odoo-bin -d <database_name> --test-tags /module_name

# Run a specific test class
./odoo-bin -d <database_name> --test-tags /module_name:TestClassName

# Run a specific test method
./odoo-bin -d <database_name> --test-tags /module_name:TestClassName.test_method_name

# Run post_install tests (exclude at_install)
./odoo-bin -d <database_name> --test-tags post_install,-at_install -i module_name

# Update a module and run its tests
./odoo-bin -d <database_name> -u module_name --test-enable
```

`--test-tags` filter format: `[-][tag][/module][:class][.method]` — prefix with `-` to exclude. Default tags are `standard` and `at_install`. Use `--test-enable` to run all standard tests on module install/update.

### Linting

```bash
# Ruff is the primary linter (config in ruff.toml)
ruff check .
ruff check addons/my_module/
```

### Other CLI Commands

```bash
./odoo-bin shell -d <database_name>       # Interactive Python shell with Odoo env
./odoo-bin scaffold <module_name> addons/  # Generate new addon skeleton
./odoo-bin db <subcommand>                 # Database operations
```

## Architecture

### Core Framework (`odoo/`)

- **ORM** (`odoo/models/`, `odoo/orm/`, `odoo/fields/`): Active-record ORM. Models inherit from `models.Model`, use declarative field definitions, and operate on recordsets. Key subsystems: field types, domain expressions, registry, environments.
- **HTTP layer** (`odoo/http.py`): WSGI application with routing through `@route()` decorators on controller classes. Auth modes: `'public'`, `'user'`, `'none'`.
- **Module system** (`odoo/modules/`): Handles addon discovery, dependency resolution (DAG), loading, and migration.
- **Tools** (`odoo/tools/`): Shared utilities — config, safe_eval, SQL helpers, image processing, caching, translation, JS transpilation.
- **CLI** (`odoo/cli/`): Command dispatch via `Command` subclasses (server, shell, scaffold, db, module, etc.).
- **Test framework** (`odoo/tests/`): Extended unittest — provides `TransactionCase`, `HttpCase`, test tagging, query counting, and form simulation.

### Addon Structure

Every addon follows this layout:

```
addons/my_module/
├── __manifest__.py       # Metadata: name, version, depends, data files, assets
├── __init__.py
├── models/               # ORM model definitions (business logic)
├── views/                # XML view definitions (form, list, kanban, etc.)
├── controllers/          # HTTP route handlers
├── wizard/               # Transient models for multi-step dialogs
├── security/             # ir.model.access.csv + record rules XML
├── data/                 # Initial data loaded on install
├── demo/                 # Demo data
├── report/               # QWeb report templates
├── static/               # Frontend assets (JS, CSS, XML templates)
├── tests/                # Python test files
└── i18n/                 # Translation .po files
```

The `__manifest__.py` dict keys that matter most: `depends` (module dependencies), `data` (XML/CSV files loaded in order), `assets` (JS/CSS bundles by asset key), `installable`, `auto_install`, `post_init_hook`.

### Model Inheritance Patterns

- **Classical inheritance** (`_inherit = 'parent.model'` without `_name`): Extends an existing model in-place. This is the most common pattern — addons extend base models.
- **Prototype inheritance** (`_inherit = 'parent.model'` with a new `_name`): Creates a new model copying the parent.
- **Delegation inheritance** (`_inherits = {'parent.model': 'field_id'}`): Composition — the child has a Many2one to parent and auto-delegates field access.
- **Mixin classes** (`models.AbstractModel`): Provide reusable behavior (e.g., `mail.thread`, `mail.activity.mixin`).

### API Decorators (`odoo.api`)

- `@api.depends(*fields)` — computed field dependencies (supports dot-notation like `'partner_id.name'`)
- `@api.constrains(*fields)` — validation on create/write
- `@api.onchange(*fields)` — form UI reactivity (pseudo-records, not DB)
- `@api.ondelete(at_uninstall=False)` — unlink guard
- `@api.model` — method operates at model level, not on specific records
- `@api.model_create_multi` — `create()` accepts both single dict and list of dicts
- `@api.autovacuum` — called by daily cleanup cron
- `@api.readonly` — allows readonly cursor for RPC methods
- `@api.private` — blocks RPC/web-service access

### Record Commands (`odoo.fields.Command`)

For writing to One2many/Many2many fields in `create()`/`write()`:

- `Command.create(values)` — (0, 0, values)
- `Command.update(id, values)` — (1, id, values)
- `Command.delete(id)` — (2, id, 0)
- `Command.unlink(id)` — (3, id, 0)
- `Command.link(id)` — (4, id, 0)
- `Command.clear()` — (5, 0, 0)
- `Command.set(ids)` — (6, 0, ids)

### Test Classes

- **`TransactionCase`**: Each test method runs in a savepoint that is rolled back. Most common. Setup shared data in `setUpClass`.
- **`SingleTransactionCase`**: All methods share one transaction, rolled back at the end.
- **`HttpCase`**: Extends `TransactionCase` with `url_open()` for HTTP requests and Chrome headless browser support for JS testing.

Test tagging: `@tagged('post_install', '-at_install')` controls when tests run. Tests default to `standard` + `at_install`.

### Frontend Assets

JavaScript modules live in `addons/*/static/src/`. The asset bundling system uses keys like `web.assets_backend`, `web.assets_frontend`, `web.assets_tests`. Assets are declared in `__manifest__.py` under the `assets` key. Odoo uses its own JS module system (OWL framework for components).

### Security Model

- **Access rights**: `security/ir.model.access.csv` — CRUD permissions per model per group.
- **Record rules**: XML `<record model="ir.rule">` — domain-based row-level filtering.
- **Groups**: Defined in XML, referenced as `module.xml_id`.

### Import Conventions

Import order enforced by ruff (isort): stdlib → third-party → `odoo` (first-party) → `odoo.addons` (local-folder). In `__init__.py` files, unused imports (re-exports) are allowed (F401 suppressed).

## Key Conventions

- Model names use dot notation: `sale.order`, `account.move`. The corresponding Python class is typically CamelCase: `SaleOrder`, `AccountMove`.
- XML IDs follow `module.identifier` format and serve as stable external references for records.
- Views, actions, menus, and data records are defined in XML files listed in the manifest's `data` key — load order matters.
- Translation strings use `_("text")` from `odoo import _`. Use `_lt()` for lazy translation in class attributes.
- Database: PostgreSQL 13+. The ORM handles schema; avoid raw SQL unless necessary. When needed, use `self.env.cr.execute(SQL(...))` with the `SQL` helper to prevent injection.
- Python target: 3.10+ (no older-version compatibility needed).
