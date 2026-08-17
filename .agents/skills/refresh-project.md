---
description: Clean and reset the project — clear cache, database, uploads, migrations, then rebuild with all dev fixtures and seed data. Preferred method for full project reset.
argument-hint: [--delete]
---

Run the project refresh script from the repository root. Pass `--delete` to only clean without rebuilding the database.

**Before running, stop the Django dev server** and anything else holding the DB open.

```bash
python refresh_project.py $ARGUMENTS
```

## Without `--delete` (default — clean + rebuild)

Clears everything and regenerates a fresh database:

1. **Stops the dev server** (if running via `./run`)
2. Removes all `__pycache__` directories and `.pyc` files
3. Deletes all database files (`*.sqlite3`, `*.sqlite`, `*.db`)
4. Clears all uploaded media from `app/media/`
5. Removes all migration files (except `__init__.py`)
6. Regenerates migrations with `makemigrations`
7. Applies migrations with `migrate`
8. Loads development fixtures:
   - **Administration** — auth groups, users, roles, ownership, user scopes
   - **Assets** — base asset models and asset instances
   - **Detail Extensions** — extension enablement
9. Runs seed commands:
   - `seed_parts_dev` — Parts and manufacturers
   - `seed_procurement_dev` — Procurement items

**Use this for schema changes or when you need a completely fresh development environment.**

## With `--delete` flag

Only clears data without rebuilding:

1. **Stops the dev server** (if running via `./run`)
2. Removes all `__pycache__` directories and `.pyc` files
3. Deletes all database files
4. Clears all uploaded media from `app/media/`
5. Removes all migration files (except `__init__.py`)

**Use this when you just want to clean up without resetting the database.**

---

## What gets seeded

**Administration (fixtures):**
- 3 auth groups (`generic_user`, `generic_manager`, `generic_admin`)
- 3 users (all with password `changeme`)
- 3 roles with permission assignments
- 2 divisions, 4 organizations with ownership hierarchy
- 13 domains across the hierarchy
- User scope assignments (manager → north scope; admin → full scope)

**Assets (fixtures):**
- 10 asset models (170 Montauk, 320, 35SA, etc.)
- Asset instances across models

**Detail Extensions (fixtures):**
- Extension enablement settings

**Parts (seed command):**
- 16 parts (PN-1001 through PN-2012) with manufacturers, revisions, and aliases
- Includes 4 fully-exercised driver parts (alternator, engine, starter, AC compressor)

**Procurement (seed command):**
- Procurement seed data

---

This aligns with the **migration strategy** in `AGENTS.md`: no incremental migrations during active development — always do a full reset on schema changes. Do **not** accumulate migration files; this workflow handles it all at once.

**Why this over `/db-rebuild`:** This script additionally clears Python cache and uploaded media, loads all development fixtures (not just database migrations), and runs seed commands — giving you a completely fresh and fully-seeded development environment.
