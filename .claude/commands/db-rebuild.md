---
description: Reset Django dev DB — clear project migrations, drop the database, regenerate migrations, apply, and optionally seed.
argument-hint: [--seed]
---

Run the project's full DB rebuild script from the repository root. Pass `--seed` if the user provided it as an argument (or if they asked for fresh dev data).

Before running, **stop the Django dev server** and anything else holding the DB open.

```bash
python dev_tools/delete_database_rebuild_models.py $ARGUMENTS
```

What this does:
1. Walks each `app/<application>/migrations/` directory and deletes every file except `__init__.py` (and removes `__pycache__`).
2. Clears the database — deletes `db.sqlite3` for SQLite, or `DROP SCHEMA public CASCADE; CREATE SCHEMA public;` for PostgreSQL via `DATABASE_URL`.
3. Runs `python manage.py makemigrations` then `python manage.py migrate`.
4. With `--seed`: runs `python manage.py seed_dev` (dev users + sample division/org/ownership data; see `harness/Development_Tools/users_and_passwords.md` and `SEED_USER_PASSWORD`).

After completion, report:
- Which migration directories were cleared
- Whether the DB was reset
- Whether seeding ran (and what the dev user password is, if relevant)

This matches the `migration-strategy` rule in `CLAUDE.md`: no incremental migrations during active dev — always do a full reset on schema changes. Do **not** add legacy-row cleanup helpers in seed commands; rely on this workflow instead.
