---
type: "Tooling Guide"
title: "Environment generation (`.env`)"
description: "The local .env is **generated, not hand-edited**."
tags: [development-tools, tooling-guide]
context_tier: 2
---

# Environment generation (`.env`)

The local `.env` is **generated, not hand-edited**. `dev_tools/generate_env.py` writes deterministic dev defaults and cryptographically random secrets each time it is run.

---

## Generating the file

```bash
python dev_tools/generate_env.py
```

This creates (or refreshes) the project-root `.env` file. Existing values are overwritten — the script is the source of truth for dev environments, not the file on disk.

---

## Keys written by the generator

| Key | Source | Notes |
| :--- | :--- | :--- |
| `DJANGO_SECRET_KEY` | `secrets.token_urlsafe(50)` | Used by Django for session signing, CSRF, etc. Regenerated on every run. |
| `DJANGO_SUPERUSER_PASSWORD` | Configured default; can be overridden | Sets the password for the seeded `super_admin` Django superuser. See [users_and_passwords.md](users_and_passwords.md). |
| `SEED_USER_PASSWORD` | Configured default (`changeme` if unset) | Sets the password for the three seeded portal users (`generic_user`, `generic_manager`, `generic_admin`). |
| `HASHIDS_SALT` | `secrets.token_urlsafe(32)` in prod-shaped envs, fixed dev sentinel in dev | Used by `app/utils/hashids.py` for URL PK encoding. See [../../docs/events/pk_hashing_migration.md](../../docs/events/pk_hashing_migration.md). |
| `DEBUG` | `True` for dev | Set to `False` for any prod-shaped env. |
| `DATABASE_URL` (if used) | SQLite path by default | Switch to Postgres by exporting before generation. |

---

## Production environments

`.env` is for **local development**. Production environment variables are managed outside this repo (CI secrets, container env, etc.). Do not check production `.env` files into the repository.

The generator is safe to run in production-shaped local environments (for example a staging-like docker compose) because it does not commit anything; it only writes the file in the working directory. But the *values* must be reviewed before deploying — dev defaults include a documented insecure hashids salt and a default superuser password.

---

## Regenerating after a secret leak

If a developer accidentally commits a secret or shares it externally, regenerate:

```bash
python dev_tools/generate_env.py
```

Then restart the dev server and re-run `seed_dev` so the new password defaults take effect.

For production secrets, follow the deployment platform's secret rotation process — do not rely on `generate_env.py`.

---

## What the generator does *not* do

- It does not write to the system environment. The `.env` file is read by Django at process start (via the project's env helper).
- It does not migrate the database. Run [db_rebuild.md](db_rebuild.md) separately if a fresh DB is needed.
- It does not configure `.claude/` or any AI tooling — that is repo state, not environment.
