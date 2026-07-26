---
type: "Concept Anchor"
title: "Development Tools — Tier 1 Anchor"
description: "This file is the **concept anchor** for the local development workflow: the database rebuild loop, environment generation, seeded users and credentials, and the helper scripts under dev_tools/."
tags: [overview, concept-anchor]
context_tier: 1
---

# Development Tools — Tier 1 Anchor

The local development workflow: the database rebuild loop, environment generation, seeded users and credentials, and the helper scripts under `dev_tools/`. Detail lives in the Tier 2 files below.

---

## Core ideas

- **Migrations are wiped, not accumulated, during active development.** Any schema change — new field, removed column, altered constraint — is followed by a full reset: delete all project-owned migrations, drop the database, regenerate, apply, and re-seed. Incremental migrations only return once a schema is "frozen" for production.
- **Seeding is for known baseline state.** `seed_dev` creates three portal users and one Django superuser, plus sample divisions, organizations, and domains. Re-running it resets passwords from environment variables; it never silently mutates an existing record outside that baseline.
- **The `.env` file is generated, not hand-edited.** `dev_tools/generate_env.py` produces a `.env` with deterministic dev defaults and cryptographically random secrets (Django secret, hashids salt). Production environment variables are managed outside the repo.
- **Personas and slash commands live alongside the docs.** `/backend-persona`, `/frontend-persona`, `/admin-persona`, etc. activate scoped agent profiles. `/db-rebuild` runs the full migration reset. See [Context_Scaling/persona_routing.md](Context_Scaling/persona_routing.md) for how persona context loading works.
- **No legacy-data cleanup in seed commands.** Schema-shape changes are handled by wiping the DB, not by adding one-off cleanup helpers. `get_or_create` for the *current* seed is fine; tombstones are not.

---

## Sub-specifications

See [Development_Tools/index.md](Development_Tools/index.md) for the full, machine-routable index of Tier 2 guides (DB rebuild, `.env` generation, seed users, `seed_dev`).

---

## Reference directionality

This anchor references **only** files inside `Development_Tools/`. Fixture conventions are described in [Architecture.md](Architecture.md) (seeding section); operational decisions about migration strategy that affect every task are restated in the project-root `Claude.md`. Persona configuration files live in `.claude/` and are referenced through [Context_Scaling.md](Context_Scaling.md), not this anchor.
