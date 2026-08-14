# Django Asset Management (Gemini / Antigravity Edition)

Server-rendered Django project (Django 6.x) for managing assets, events, and part demands across an organizational hierarchy. Frontend is **Bulma + HTMX** (no SPA). Authorization combines Django's permission system with **row-level ownership-group scoping**.

## Run / Dev Workflow

```bash
python manage.py runserver        # or: ./run
python manage.py makemigrations
python manage.py migrate
python manage.py seed_dev         # dev users + sample org/division/ownership data
```

Full DB reset (after schema changes — see "Migration strategy" below):
```bash
python dev_tools/delete_database_rebuild_models.py [--seed]
# or run the slash command: /db-rebuild
```

Generate `.env`:
```bash
python dev_tools/generate_env.py
```

## Project Layout

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
  Architecture/         ← layer rules, patterns, standards (source of truth)
  Authorization/        ← RBAC, data domains, users, password policy
  applications/         ← per-application docs (core_domain, events, assets, ...)
  dev_tools/            ← scripts (db rebuild, env gen, memory log)
.agents/
  personas/             ← persona sub-agents (Admin, Backend, Frontend, Business, Code Architect)
  skills/               ← slash commands (persona activators + ops)
  memory/               ← project decisions/memories
```

Each sub-app under `app/` follows the layered structure:
```
<sub-app>/
  presentation_layer/{entrypoints,search,tools}/
  control_layer/{adapters,domain_structs,<write modules>}/
  models/
  templates/
```

## Source-of-Truth Docs

Read these when in doubt — they are authoritative:

### Architecture
- [docs/Architecture.md](docs/Architecture.md) — Layered architecture summary
- [docs/Architecture/overview.md](docs/Architecture/overview.md) — folder layout and layer responsibilities
- [docs/Architecture/layer_rules.md](docs/Architecture/layer_rules.md) — reads vs writes
- [docs/Architecture/patterns/oop_control_patterns.md](docs/Architecture/patterns/oop_control_patterns.md) — class suffix vocabulary
- [docs/Architecture/patterns/model_patterns.md](docs/Architecture/patterns/model_patterns.md) — model rules
- [docs/Architecture/patterns/endpoint_patterns.md](docs/Architecture/patterns/endpoint_patterns.md) — OOP endpoint design
- [docs/Architecture/patterns/htmx_patterns.md](docs/Architecture/patterns/htmx_patterns.md) — HTMX conventions
- [docs/Architecture/standards.md](docs/Architecture/standards.md) — engineering principles
- [docs/Architecture/seeding.md](docs/Architecture/seeding.md) — dev seed strategy
- [docs/Architecture/tests.md](docs/Architecture/tests.md) — testing conventions

### UX / UI
- [docs/UX_UI.md](docs/UX_UI.md) — visual language, density (`format=`)
- [docs/UX_UI/form_style_guide.md](docs/UX_UI/form_style_guide.md) — action layout rules for forms and cards
- [docs/UX_UI/design_patterns/common_buttons.md](docs/UX_UI/design_patterns/common_buttons.md) — button library and semantic colors
- [docs/UX_UI/components/dual_listbox.md](docs/UX_UI/components/dual_listbox.md) — dual listbox many-to-many selection
- [docs/UX_UI/search/searchbars.md](docs/UX_UI/search/searchbars.md) — searchbars and autocomplete guides

### Domain
- [docs/Authorization/rbac.md](docs/Authorization/rbac.md) — Django permissions, groups, and templates
- [docs/Authorization/data_ownership.md](docs/Authorization/data_ownership.md) — Ownership groups and organizational hierarchy
- [docs/applications/core_domain/core_models.md](docs/applications/core_domain/core_models.md) — Core models dependency graph
- [docs/applications/events/events.md](docs/applications/events/events.md) — Events sub-application domain
- [docs/applications/core_domain/divisions.md](docs/applications/core_domain/divisions.md) — Divisions and organization hierarchy
- [docs/technical_decisions/index.md](docs/technical_decisions/index.md) — Technical debt and decision history


---

## Active Personas & Slash Commands

Adopt these roles or run these helper commands using their slash equivalents:

*   `/backend-persona` — Backend Engineer (layered architecture, OOP control patterns, models)
*   `/frontend-persona` — Frontend Engineer (HTMX, Bulma, F5 rule, `format=` query)
*   `/admin-persona` — Admin Engineer (Django auth, RBAC, ownership scoping, admin panels)
*   `/code-architect-persona` — Code Architect (review-only; smells, patterns, severities)
*   `/business-persona` — Business Architect (no-code; user value, workflows, priorities)
*   `/db-rebuild` — clears project migrations + DB, regenerates and applies migrations, optionally seeds.
*   `/dev-login` — logs into dev server and saves local cookies to `/tmp/dev_cookies.txt`.

---

## Project Memory

Confirmed architectural and design decisions are saved in `.agents/memory/` and should be referenced:
- [OWASP Password Policy](.agents/memory/password_policy.md) — 12-char minimum length enforcement.
- [Permissions & Scope System Architecture](.agents/memory/permissions_system_architecture.md) — Two orthogonal access gates, session snapshots, domain/group templates.

---

## Always-Apply Rules

These rules apply to **every** task in this repo, regardless of persona.

### 1. Migration Strategy (Development)
After **any change that adds/removes/renames a database column or table** (or otherwise alters schema: new model, field, `Meta.indexes`, constraints, etc.), use a **full reset**: clear all project-owned migration history, empty the database, regenerate migrations from current models, apply them, then re-seed.

Do **not** accumulate incremental migrations during active development.
**Workflow:** Run `python dev_tools/delete_database_rebuild_models.py [--seed]` or `/db-rebuild`.

### 2. Public Routes vs Login-By-Default
- **Unauthenticated (public) pages** belong **only** under `app/public_app/` (URLs, entrypoints, templates). Mark views with `login_not_required` so `LoginRequiredMiddleware` does not redirect guests.
- **Everything else** is authenticated-only by default.

### 3. Spelling and Intent Correction
Correct spelling silently to match intent before acting.
*   `buisness` → `business`
*   `archetecture` / `arcatecture` → `architecture`
*   `controler` → `controller`
*   `endpint` → `endpoint`
*   `templet` → `template`
*   `permision` → `permission`
*   `autherization` → `authorization`

### 4. Folder Path Assumption
If a requested path does not exist, find the closest matching real path and proceed, noting the correction.
*   `docs/DOMAIN/ARCHITECTURE` → `docs/ARCHITECTURE/`
*   `docs/admin/RBAC` → `docs/DOMAIN/admin/RBAC.md`
*   `skills/backend` → `.agents/personas/backend-engineer.md`

### 5. Project Conventions
- **Audit columns on every table:** `created_at`, `updated_at`, `created_by_id`, `updated_by_id`.
- **Default PK:** `BigAutoField` integer.
- **No business logic on models** — schema and constraints only. Mark intentional exceptions with `# DELIBERATE ANTI-PATTERN`.
- **Suffix vocabulary:** `Struct`, `Context`, `Factory`, `BulkFactory`, `Handler`, `Manager`, `Policy`, `Validator`, `StateMachine`, `Narrator`, `Adaptor`, `Orchestrator`. Guard files end in `_guard.py`.
- **Sharp corners everywhere:** Bulma border-radius variables set to `0`. No pill buttons, no rounded cards.
- **HTMX F5 rule:** every page/state must work via a plain full-page reload.
- **Single canonical URL per resource:** Use `format=` query parameter for density (`condensed`/`medium`/`large`) and HTMX fragments (`htmx-*`).
