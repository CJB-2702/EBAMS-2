# Django Asset Management

Server-rendered Django project (Django 6.x) for managing assets, events, and part demands across an organizational hierarchy. Frontend is **Bulma + HTMX** (no SPA). Authorization combines Django's permission system with **row-level ownership-group scoping**.

## Run / dev workflow

```bash
python manage.py runserver        # or: ./run
python manage.py makemigrations
python manage.py migrate
python manage.py seed_dev         # dev users + sample org/division/ownership data
```

Full DB reset (after schema changes — see "Migration strategy" below):
```bash
python dev_tools/delete_database_rebuild_models.py [--seed]
```

Generate `.env`:
```bash
python dev_tools/generate_env.py
```

## Project layout

```
app/
  administration/       ← admin sub-app (RBAC, ownership groups, user assignments)
  events/               ← event tracking sub application for event standardization and file managment
  <applications>/       ← various core applications see domain folder for descriptions
  media/                ← built in django file storage location
  config/               ← settings, root urls
  public_app/           ← unauthenticated routes only (login, signup, etc.)
  static/
docs/
  ARCHITECTURE/         ← layer rules, patterns, standards (source of truth)
  DOMAIN/admin/         ← RBAC, DATA_OWNERSHIP, USERS
  DOMAIN/core/          ← CORE_MODELS
dev_tools/              ← scripts (db rebuild, env gen, memory log)
.claude/
  agents/               ← persona sub-agents (Admin, Backend, Frontend, Business, Code Architect)
  commands/             ← slash commands (persona activators + ops)
```

Each sub-app under `app/` follows the layered structure:
```
<sub-app>/
  presentation_layer/{entrypoints,search,tools}/
  control_layer/{adapters,domain_structs,<write modules>}/
  models/
  templates/
```

## Source-of-truth docs

Read these when in doubt — they are authoritative:

### Architecture

- [docs/ARCHITECTURE/ARCHITECTURE.md](docs/ARCHITECTURE/ARCHITECTURE.md) — folder layout and layer responsibilities
- [docs/ARCHITECTURE/LAYER_RULES.md](docs/ARCHITECTURE/LAYER_RULES.md) — reads vs writes
- [docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md](docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md) — class suffix vocabulary
- [docs/ARCHITECTURE/MODEL_PATTERNS.md](docs/ARCHITECTURE/MODEL_PATTERNS.md) — model rules
- [docs/ARCHITECTURE/ENDPOINT_PATTERNS.md](docs/ARCHITECTURE/ENDPOINT_PATTERNS.md) — OOP endpoint design
- [docs/ARCHITECTURE/HTMX_PATTERNS.md](docs/ARCHITECTURE/HTMX_PATTERNS.md) — HTMX conventions
- [docs/ARCHITECTURE/STANDARDS.md](docs/ARCHITECTURE/STANDARDS.md) — engineering principles
- [docs/ARCHITECTURE/COMMON_UI_COMPONENTS.md](docs/ARCHITECTURE/COMMON_UI_COMPONENTS.md) — shared UI component patterns
- [docs/ARCHITECTURE/SEEDING.md](docs/ARCHITECTURE/SEEDING.md) — dev seed strategy
- [docs/ARCHITECTURE/TESTS.md](docs/ARCHITECTURE/TESTS.md) — testing conventions

### UX / UI

- [docs/UX_UI/UX_UI.md](docs/UX_UI/UX_UI.md) — visual language, density (`format=`)
- [docs/UX_UI/form_style_guide.md](docs/UX_UI/form_style_guide.md) — action layout rules for forms and cards
- [docs/UX_UI/component_library/](docs/UX_UI/component_library/) — component guides: `common_buttons`, `dual_listbox_guide`, `image carosel`, `modals_dialogs_usage`, `searchbars`

### Domain

- [docs/DOMAIN/admin/](docs/DOMAIN/admin/) — RBAC, data ownership, users, roles, domain templates, password policy
  - [docs/DOMAIN/admin/RBAC.md](docs/DOMAIN/admin/RBAC.md) — Django permission system, group templates
- [docs/DOMAIN/core/](docs/DOMAIN/core/) — core entity dependency graph
- [docs/DOMAIN/events/](docs/DOMAIN/events/) — events domain
- [docs/DOMAIN/orgchart/](docs/DOMAIN/orgchart/) — divisions, org hierarchy
- [docs/DOMAIN/tech_debt/](docs/DOMAIN/tech_debt/) — known tech debt notes

## Personas (slash commands)

Activate a focused persona with one of these slash commands. Each loads the corresponding agent profile under [.claude/agents/](.claude/agents/) and adopts it for the rest of the conversation:

- `/backend-persona` — Backend Engineer (layered architecture, OOP control patterns, models)
- `/frontend-persona` — Frontend Engineer (HTMX, Bulma, F5 rule, `format=` query)
- `/admin-persona` — Admin Engineer (Django auth, RBAC, ownership scoping, admin panels)
- `/code-architect-persona` — Code Architect (review-only; smells, patterns, severities)
- `/business-persona` — Business Architect (no-code; user value, workflows, priorities)

These same agents are also spawnable via the Task/Agent tool when you want to delegate a single task in isolation.

## Operational slash commands

- `/db-rebuild` — clears project migrations + DB, regenerates and applies migrations, optionally seeds.

---

# Always-apply rules

These rules apply to **every** task in this repo, regardless of persona.

## 1. Migration strategy (development)

After **any change that adds/removes/renames a database column or table** (or otherwise alters schema: new model, field, `Meta.indexes`, constraints, etc.), use a **full reset**: clear all project-owned migration history, empty the database, regenerate migrations from current models, apply them, then re-seed.

Do **not** accumulate incremental migrations during active development.

**Workflow** — from the project root, with the dev server stopped:

- **Preferred:** `python dev_tools/delete_database_rebuild_models.py [--seed]` (or use the `/db-rebuild` slash command).
- **Manual equivalent:** for each `app/<application>/migrations/`, delete every file except `__init__.py` and remove `__pycache__`. Clear the DB (delete `db.sqlite3`, or `DROP SCHEMA public CASCADE` on Postgres). Then `makemigrations`, `migrate`, optionally `seed_dev`.

**Do not** add legacy-data cleanup helpers to seed commands (`_remove_legacy_*`, one-off slug renames, etc.). Schema/seed-shape changes are handled by wiping the DB. Idempotent `get_or_create` for the **current** seed is fine; tombstone cleanup is not.

## 2. Public routes vs login-by-default

- **Unauthenticated (public) pages** belong **only** under `app/public_app/` (URLs, entrypoints, templates). Mark their views with `login_not_required` so `LoginRequiredMiddleware` does not redirect guests.
- **Everything else** is authenticated-only by default. Do **not** add parallel "public" routes outside `public_app` without an exceptional, documented reason.

## 3. Spelling and intent correction

The user frequently misspells words. **Silently correct spelling to best match intent before acting.** Do not halt to ask about obvious misspellings — fix and proceed.

| User types | Correct term |
| :--- | :--- |
| `buisness` | `business` |
| `archetecture`, `arcatecture`, `architecure` | `architecture` |
| `archetect`, `arcatect` | `architect` |
| `personae`, `parsona` | `persona` |
| `controler` | `controller` |
| `endpint`, `endponit` | `endpoint` |
| `templet`, `templat` | `template` |
| `permision`, `premission` | `permission` |
| `autherization`, `authoirzation` | `authorization` |
| `inheritence` | `inheritance` |
| `seperatation` | `separation` |

If correcting changes meaning significantly, briefly note it (_"Interpreted 'buisness archetect' as 'business architect'."_). Otherwise just proceed.

## 4. Folder path assumption

The user often gets folder paths wrong — wrong order, wrong casing, partial names, or invented paths that almost match a real one. **Be suspicious that any path is slightly wrong.**

Before acting on a path:
1. Check if the exact path exists.
2. If not, find the closest matching real path by comparing segments (in any order) against the project tree.
3. Proceed with the corrected path; briefly note the assumption (_"Treating `docs/DOMAIN/ARCHITECTURE` as `docs/ARCHITECTURE` — closest match."_).

Common mistakes:
- `docs/DOMAIN/ARCHITECTURE` → `docs/ARCHITECTURE/`
- `docs/admin/RBAC` → `docs/DOMAIN/admin/RBAC.md`
- `ARCHITECTURE/UX` → `docs/UX_UI/UX_UI.md`
- `skills/backend` → `.claude/agents/backend-engineer.md`

---

## Project conventions worth knowing

- **Audit columns on every table:** `created_at`, `updated_at`, `created_by_id`, `updated_by_id`.
- **Default PK:** `BigAutoField` integer; UUID7 only for cross-table polymorphic uniqueness.
- **No business logic on models** — schema and constraints only. Mark intentional exceptions with `# DELIBERATE ANTI-PATTERN`.
- **Suffix vocabulary** (see OOP_CONTROL_PATTERNS): `Struct`, `Context`, `Factory`, `BulkFactory`, `Handler`, `Manager`, `Policy`, `Validator`, `StateMachine`, `Narrator`, `Adaptor`, `Orchestrator`. Guard files end in `_guard.py`.
- **Sharp corners everywhere** — Bulma radius variables set to `0`. No pill buttons, no rounded cards.
- **HTMX F5 rule** — every page/state must work via a plain full-page reload; HTMX layers interactivity on top.
- **Single canonical URL per resource** with a `format=` query parameter for density (`condensed`/`medium`/`large`) and HTMX fragments (`htmx-*`). Never combine density and `htmx-*` in one request.

## Optional: lightweight work log

There is a project-local convention of appending one short line per substantive change to [dev_tools/memory.md](dev_tools/memory.md) (newest last, plain text). Use it on request — Claude Code's own memory system handles cross-session recall, so this file is purely a human-scannable paper trail.
