---
type: "Tooling Guide"
title: "Database rebuild workflow"
description: "The full DB reset is the canonical way to apply schema changes during active development."
tags: [development-tools, tooling-guide]
context_tier: 2
---

# Database rebuild workflow

The full DB reset is the canonical way to apply schema changes during active development. It avoids accumulating incremental migrations whose only purpose is to bridge intermediate dev states.

---

## When to use it

Use a full rebuild after **any change that adds, removes, or renames a database column or table** (or otherwise alters schema: new model, field, `Meta.indexes`, constraints). Examples that trigger a rebuild:

- New field on an existing model.
- Renamed FK target.
- New `Meta.unique_together` or constraint.
- Mixin change that adds an audit column to every consumer.
- Custom user model change.

If a change is **purely data** (e.g. updating seed records that already match the schema), `seed_dev` alone is enough.

---

## Preferred path

From the project root, with the dev server stopped:

```bash
python dev_tools/delete_database_rebuild_models.py [--seed]
```

The script:

1. Walks each `app/<application>/migrations/` and deletes every file except `__init__.py`. Removes `__pycache__/`.
2. Clears the database (deletes `db.sqlite3`, or `DROP SCHEMA public CASCADE` on Postgres).
3. Runs `makemigrations` and `migrate`.
4. If `--seed` is passed, runs `seed_dev`.

A slash command wraps the same operation: `/db-rebuild`.

---

## Manual equivalent

If the script is unavailable or you want to run the steps individually:

```bash
# 1. Clear migrations for each app
for app in administration events assets public_app; do
    rm app/$app/migrations/0*.py
    rm -rf app/$app/migrations/__pycache__
done

# 2. Clear the database
rm db.sqlite3   # SQLite
# or: psql -c 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;'

# 3. Regenerate and apply
python manage.py makemigrations
python manage.py migrate

# 4. Optional seed
python manage.py seed_dev
```

---

## What *not* to do

- **Do not** add legacy-data cleanup helpers to seed commands (`_remove_legacy_*`, one-off slug renames, etc.). Schema/seed-shape changes are handled by wiping the DB. Idempotent `get_or_create` for the **current** seed is fine; tombstone cleanup is not.
- **Do not** accumulate incremental migrations during active development. Every commit should leave the project with one clean migration per app reflecting the current model state.
- **Do not** run the rebuild against a production database. The script intentionally targets the local SQLite/Postgres dev DB.

---

## After the rebuild

- Verify the dev server starts: `python manage.py runserver` (or `./run`).
- Log in as `super_admin` (Django admin) or one of the seeded portal users — see [users_and_passwords.md](users_and_passwords.md).
- Smoke-test the portal you were working on.

If `migrate` fails because of an FK ordering issue, the cause is almost always a missing `__init__.py` in one of the migration folders or a model that references a swappable user model that has not yet been registered. Fix the missing file and re-run the rebuild.
