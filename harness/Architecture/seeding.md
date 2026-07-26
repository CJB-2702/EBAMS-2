---
type: Architecture Guide
title: Seeding Plan
description: Where fixtures live, how to author them, and the rules for seeding dev data.
tags: [architecture, seeding, fixtures, dev-data]
---

# Seeding plan: Django fixtures

This document defines **where fixture files live**, **how to author them**, and **rules** that stay consistent with [patterns/model_patterns.md](patterns/model_patterns.md), [layer_rules.md](layer_rules.md), and [overview.md](overview.md). It applies to **JSON/YAML/XML fixtures** loaded with `manage.py loaddata`.

## 1. Purpose and scope

| Use case | Fixtures appropriate? | Notes |
| :--- | :--- | :--- |
| **Local dev / demo** | Yes | Repeatable baseline data (roles, reference lists, sample rows). |
| **Automated tests** | Often yes | Small, stable datasets; prefer minimal fixtures or factories where speed matters. |
| **Production** | Rarely | Prefer migrations (`RunPython`), one-off ops, or ETL — not checked-in dumps of real data. |

**Fixtures are data snapshots**, not business logic. They **do not** replace the control layer for user-driven writes; they **bootstrap** the database to a known state.

## 2. Where fixtures live

Django discovers fixtures under each app's `fixtures/` directory (app root, sibling to `models/`, `migrations/`, `management/`).

**Rules:**

- **Co-locate with ownership:** put a fixture in the **same Django app** that owns the models it serializes. Cross-app FKs are fine in one file, but avoid one giant project-wide dump unless intentionally maintained.
- **Not in `control_layer/` or `presentation_layer/`:** seed files are infrastructure, like `migrations/`.
- **Optional project-level bundle:** if a single command must load everything, add a management command that loads named fixtures **in order**.

## 3. File naming and granularity

- Use **lowercase snake_case** with a clear intent: `rbac_groups_permissions.json`, `asset_categories.json`, `demo_work_orders.json`.
- Prefer **several smaller fixtures** over one monolith.
- If order matters, encode it in **documentation** (fixture `README` or this file) and/or a management command that runs `loaddata` in sequence.

## 4. Authoring rules

### 4.1 Primary keys and stability

- **Prefer natural keys** when models define `Meta.unique_together` / `natural_key()`. Export with `dumpdata --natural-foreign --natural-primary`.
- **Integer PKs** are acceptable for throwaway dev DBs; they are fragile when mixed with auto-increment state.
- **Never hand-edit** sequences in PostgreSQL/SQLite to "fix" a fixture; regenerate from a clean DB or switch to natural keys.

### 4.2 Foreign keys and load order

- Rows must appear **before** dependents: parents before children.
- For **circular** dependencies, split into two fixtures loaded in order, or use natural keys.
- **Swappable user model:** load auth-related data after user rows exist, or load users first in the same file.

### 4.3 Audit and trace fields

Models with `created_at` / `updated_at` / `created_by_id` / `updated_by_id` should be seeded with explicit values:

- Use **fixed timestamps** for reproducibility (ISO 8601).
- Point `created_by_id` / `updated_by_id` at real user PKs that exist earlier in the same fixture or in a prerequisite fixture.

Do not rely on `auto_now_add` alone — serialized rows should include the fields your schema expects.

### 4.4 Permissions and RBAC

- Prefer loading `auth.Group`, `auth.Permission`, and group-permission links via fixtures **owned by the app that defines the custom permissions**.
- Keep permission codenames aligned with migration definitions.

### 4.5 Content types and generic relations

Fixtures referencing `ContentType` are brittle across DBs if IDs differ. Prefer:
- avoiding generic FKs in seed data, or
- loading contenttypes in a known order, or
- using natural keys for contenttypes.

### 4.6 Secrets and PII

- **No secrets** (API keys, tokens) in committed fixtures.
- **No real PII**; use obvious placeholders.

## 5. Workflow: create, review, load

**Generate from truth (recommended):**

1. Migrate a clean database.
2. Create rows via Django shell, admin, or control-layer helpers (respects invariants).
3. `python manage.py dumpdata <app.Model> --natural-foreign --natural-primary -o app/fixtures/name.json`
4. Review the diff; strip noise; keep files small.

**Load:** `python manage.py loaddata reference_data demo_maintenance` (labels without `.json`).

## 6. Management commands

Use `management/commands/` only to orchestrate loading:

- Parse arguments, print intent, call `call_command("loaddata", ...)` in order.
- **Do not** embed large imperative seed logic that duplicates the control layer. If business rules matter, prefer `RunPython` migrations or a dedicated `seed_demo` command that calls control-layer functions, and use fixtures only for static reference data.

## 7. Testing

- `TransactionTestCase` / fixtures: suitable when DB reset per test class is needed; can be slow.
- Prefer `pytest-django` with `django_db` and small fixtures, or `factory_boy` for per-test variation.
- Keep test-only fixture files under the same app `fixtures/` but name them clearly (`test_users.json`).

## 8. Checklist before merging a new fixture

- [ ] Lives under the owning app's `fixtures/`.
- [ ] Load order documented if dependencies span files or apps.
- [ ] Audit/user FK fields populated per [patterns/model_patterns.md](patterns/model_patterns.md).
- [ ] No secrets or real PII.
- [ ] Regenerated or validated against current migrations.
- [ ] `loaddata` succeeds on empty DB after `migrate`.
