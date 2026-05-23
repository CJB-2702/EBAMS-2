# `seed_dev` — local seed strategy

`seed_dev` is a management command that bootstraps the development database to a known baseline state. It is **not** a fixture loader — it is an imperative command that uses control-layer factories where business invariants matter and `get_or_create` for static reference data.

For static fixture mechanics, see [../Architecture/seeding.md](../Architecture/seeding.md). For the four users it creates, see [users_and_passwords.md](users_and_passwords.md).

---

## Running it

```bash
python manage.py seed_dev
```

Idempotent: running it twice produces the same state as running it once (with the caveat that user passwords are reset from environment variables on every run).

---

## What it creates

- **Users:** `super_admin`, `generic_user`, `generic_manager`, `generic_admin`. Passwords come from `DJANGO_SUPERUSER_PASSWORD` and `SEED_USER_PASSWORD`.
- **Org chart:** two divisions (`north`, `south`), each with two organizations.
- **Domains:** sample domains under each organization, with one shared cross-org domain to demonstrate overlap.
- **Domain templates:** 2–3 templates (e.g. `facility_1`, `cross_site`) once the domain template feature is in.
- **Permission groups and roles:** the default `default_event_permissions` group; a `generic_user` / `generic_manager` / `generic_admin` role assignment for each seeded user that maps to the matching Django auth group.
- **A handful of demo events** under `generic_manager`'s domain so the events portal is non-empty after a rebuild.

---

## What it does *not* do

- It does not create production data. The command is gated by a check that refuses to run when `DEBUG=False` (or an explicit `--allow-prod` flag, which is not provided).
- It does not insert legacy-data cleanup helpers. Schema-shape changes are handled by [db_rebuild.md](db_rebuild.md), not by `seed_dev`.
- It does not modify migrations. Migrations are regenerated from current models during a rebuild.

---

## Imperative seed vs. fixtures

`seed_dev` uses control-layer factories (e.g. `EventFactory.create_event(...)`) for entities where invariants matter — for example, creating an event with the correct `domain` FK, audit fields, and required permissions. For static reference data (permission codenames, group names), `get_or_create` is sufficient.

This split matches the guidance in [../Architecture/seeding.md](../Architecture/seeding.md): use fixtures for static reference data; use control-layer commands when business rules matter.

---

## Common tweaks

- **Adding a new seeded entity** — extend `seed_dev` with a call to the relevant control-layer factory or `get_or_create`. Keep the addition idempotent.
- **Adjusting the demo dataset shape** — edit the explicit `create_event(...)` calls in `seed_dev` rather than adding a new fixture file.
- **Adding a new seeded user** — add a row to [users_and_passwords.md](users_and_passwords.md) at the same time. The doc is the developer-facing reference for what to log in as.
