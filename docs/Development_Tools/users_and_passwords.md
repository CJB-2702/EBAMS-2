# Users and passwords (local reference)

This file is **gitignored** so it can hold environment-specific credentials. Do not commit real production passwords here.

## Seeded development users (`manage.py seed_dev`)

`seed_dev` creates **four** users: three portal accounts (`generic_*`) and the Django admin account `super_admin`.

The password for the three **portal** accounts is taken from the environment variable **`SEED_USER_PASSWORD`**. If unset, the command uses the default **`changeme`**.

| Username | Password (typical) | Role / notes |
| :--- | :--- | :--- |
| `generic_user` | `$SEED_USER_PASSWORD` or `changeme` | `generic_user` group only |
| `generic_manager` | same | `generic_manager` group; staff; North division / orgs / domains (sample scope) |
| `generic_admin` | same | `generic_admin` group; staff; full `auth.User` permissions on the group; all divisions / orgs / domains after seed |

Re-running `python manage.py seed_dev` **resets** the `generic_*` passwords to the current `SEED_USER_PASSWORD` / default.

## Django superuser (`/admin/` — Django admin)

`seed_dev` creates or updates **`super_admin`** for the **built-in Django admin** at `http://localhost:8000/admin/` (the custom `/administration/` portal uses the `generic_*` users above). You do not need to run `createsuperuser` unless you want an additional superuser.

| Field | Value |
| :--- | :--- |
| Username | `super_admin` |
| Password | `dev-admin-password-change-me` (default; override with **`DJANGO_SUPERUSER_PASSWORD`**) |

The default password matches **`DJANGO_SUPERUSER_PASSWORD`** in your project `.env` when set (see [env_generation.md](env_generation.md)). Re-running `seed_dev` resets `super_admin`'s password to the current env default.

## Other accounts

Any other one-off users (extra superusers, test accounts) are not listed here — add a row in this file if you need them.
