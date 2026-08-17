# Django Asset Management (Gemini / Antigravity Edition)

Server-rendered Django project (Django 6.x) for managing assets, events, and part demands across an organizational hierarchy. Frontend is **Bulma + HTMX** (no SPA). Authorization combines Django's permission system with **row-level ownership-group scoping**.

## Run / dev workflow

```bash
python manage.py runserver        # or: ./run
python manage.py makemigrations
python manage.py migrate
python manage.py seed_dev         # dev users + sample org/division/ownership data
```

Full project reset (after schema changes — see "Migration strategy" below):
```bash
python refresh_project.py        # Clean and rebuild with seeding
python refresh_project.py --delete  # Clean only, no rebuild
```

Generate `.env`:
```bash
python dev_tools/generate_env.py
```

## Project layout

Documentation is split across two top-level folders with deliberately different audiences:

- **`harness/`** — instructions on how to build and do work: architecture, UX/UI law, authorization design, planning-process methodology, dev-tools reference. Durable, process-facing, rarely app-specific.
- **`docs/`** — specific items relating to the project: per-application knowledge (`docs/<app-name>/`, `docs/<app-name>.md`), context-loader bundles, and technical-decision history (per-app, plus a small cross-cutting bucket). Authorization is the one exception that stays in `harness/` rather than becoming a `docs/authorization/` app folder — every sub-app depends on it, so it's load-bearing enough to live at the top.

```
app/
  administration/       ← admin sub-app (RBAC, ownership groups, user assignments)
  events/               ← event tracking sub application for event standardization and file managment
  <applications>/       ← various core applications, documented per-app under docs/
  media/                ← built in django file storage location
  config/               ← settings, root urls
  public_app/           ← unauthenticated routes only (login, signup, etc.)
  static/
harness/
  Architecture/         ← layer rules, patterns, standards (source of truth)
  Authorization/        ← RBAC, data ownership, roles, users, password policy
  UX_UI/                ← visual language, component patterns, format contract
  Context_Scaling/       ← tiered context-loading model
  Development_Tools/    ← dev-tool reference docs
  starter_kit_process/  ← how to write each starter-kit document
  front_end_kit_process/ ← how to write each front-end-kit document
docs/
  <app-name>.md, <app-name>/   ← per-application knowledge (assets, events, core_domain, administration, parts, ...)
  context_bundles/      ← per-application quick context loaders
  technical_decisions/  ← cross-cutting decisions/tech debt + the master project_history.md index
dev_tools/              ← scripts (db rebuild, env gen, memory log)
.agents/
  personas/             ← persona sub-agents (Admin, Backend, Frontend, Business, Code Architect)
  skills/               ← slash commands (persona activators + ops)
  memory/               ← project decisions/memories
```

Each application under `docs/` carries its own technical-decision history in a standard shape:

```
docs/<app-name>/
  incidents/            ← postmortems for bugs and failed approaches
  project_history/      ← archived starter kits and major work initiatives for this app
  tech_debt/            ← known deferred work items
  decisions_pending/    ← not-yet-resolved decisions
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

### Architecture (harness)

- [harness/Architecture.md](harness/Architecture.md) — router into layer rules, patterns, standards
- [harness/Architecture/overview.md](harness/Architecture/overview.md) — folder layout and layer responsibilities
- [harness/Architecture/layer_rules.md](harness/Architecture/layer_rules.md) — reads vs writes
- [harness/Architecture/patterns/oop_control_patterns.md](harness/Architecture/patterns/oop_control_patterns.md) — class suffix vocabulary
- [harness/Architecture/patterns/model_patterns.md](harness/Architecture/patterns/model_patterns.md) — model rules
- [harness/Architecture/patterns/endpoint_patterns.md](harness/Architecture/patterns/endpoint_patterns.md) — OOP endpoint design
- [harness/Architecture/patterns/htmx_patterns.md](harness/Architecture/patterns/htmx_patterns.md) — HTMX conventions
- [harness/Architecture/standards.md](harness/Architecture/standards.md) — engineering principles
- [harness/Architecture/seeding.md](harness/Architecture/seeding.md) — dev seed strategy
- [harness/Architecture/tests.md](harness/Architecture/tests.md) — testing conventions

### UX / UI (harness)

- [harness/UX_UI.md](harness/UX_UI.md) — visual language, density (`format=`)
- [harness/UX_UI/form_style_guide.md](harness/UX_UI/form_style_guide.md) — action layout rules for forms and cards
- [harness/UX_UI/components/](harness/UX_UI/components/) — literal web-component guides: `dual_listbox`, `file_upload`, `file_browser`, `search_dropdown`
- [harness/UX_UI/design_patterns/](harness/UX_UI/design_patterns/), [harness/UX_UI/navigation/](harness/UX_UI/navigation/), [harness/UX_UI/search/](harness/UX_UI/search/), [harness/UX_UI/file_management/](harness/UX_UI/file_management/) — non-component UX guides: `common_buttons`, `modals`, `chamfers`, `multi_step_flows`, `tabs`, `pagination`, `searchbars`, and related markup examples
- [harness/UX_UI/design_patterns/multi_step_flows.md](harness/UX_UI/design_patterns/multi_step_flows.md) — the multi-card wizard trigger rule and session-draft pattern
- [harness/UX_UI/design_patterns/modals.md](harness/UX_UI/design_patterns/modals.md) — when a modal is appropriate, and why assignment never goes in one

### Planning process (harness)

- [harness/starter_kit_process/](harness/starter_kit_process/index.md) — how to write each starter-kit document (backend only)
- [harness/front_end_kit_process/](harness/front_end_kit_process/index.md) — how to write each front-end-kit document (routes, navigation, workflows, stager)

### Authorization (harness)

- [harness/Authorization.md](harness/Authorization.md) — router into RBAC, ownership, roles, users, password policy
  - [harness/Authorization/rbac.md](harness/Authorization/rbac.md) — Django permission system, group templates
  - [harness/Authorization/data_ownership.md](harness/Authorization/data_ownership.md) — the Data Domain primitive
  - [harness/Authorization/roles/](harness/Authorization/roles/) — role concept and decisions
  - [harness/Authorization/domain_templates/](harness/Authorization/domain_templates/) — domain template concept and plan

### Applications and domain (docs)

- [docs/index.md](docs/index.md) — per-application knowledge index (assets, events, core_domain, administration, parts)
- [docs/core_domain.md](docs/core_domain.md) — core entity dependency graph
- [docs/events.md](docs/events.md) — events domain
- [docs/assets.md](docs/assets.md) — assets domain
- [docs/technical_decisions/index.md](docs/technical_decisions/index.md) — cross-cutting tech debt notes and the master project-history index

## Personas (slash commands)

Activate a focused persona with one of these slash commands. Each loads the corresponding agent profile under [.agents/personas/](.agents/personas/) and adopts it for the rest of the conversation:

- `/backend-persona` — Backend Engineer (layered architecture, OOP control patterns, models)
- `/frontend-persona` — Frontend Engineer (HTMX, Bulma, F5 rule, `format=` query)
- `/admin-persona` — Admin Engineer (Django auth, RBAC, ownership scoping, admin panels)
- `/code-architect-persona` — Code Architect (review-only; smells, patterns, severities)
- `/business-persona` — Business Architect (no-code; user value, workflows, priorities)
- `/porting-persona` — Porting Engineer (Flask to Django migration, layer inversion, ORM mapping, session memory swap)

These same agents are also spawnable via the Task/Agent tool when you want to delegate a single task in isolation.

## Exploring the codebase

Before doing a broad `grep`/`Glob` sweep or a string of speculative file
reads across a sub-app you haven't already loaded context for this session,
use the **`codebase-map`** skill first (`.agents/skills_custom/codebase-map/SKILL.md`).
It generates a compact file-tree + class-name + docstring summary of the
target app/directory for a fraction of the token cost, and tells you which
file to open next instead of guessing from filenames. Use plain grep for
literal string/usage searches (e.g. "who calls X") — the map shows what
exists, not who references it. Once the map points at a file, Read it in
full before editing.

## Operational slash commands

- `/refresh-project` — **Preferred:** clears pycache, database, uploads, and migrations, then optionally rebuilds from scratch. Pass `--delete` to only clean without rebuilding.
- `/db-rebuild` — alternative method: clears project migrations + DB, regenerates and applies migrations, optionally seeds (does not clear pycache or uploads).
- `/kit-builder` — initiates the Kit Builder agent: seeds `<topic>_starter_kit/` with a pre-filled [20-question questionnaire](harness/starter_kit_process/kit_questionnaire_template.md) and **stops** until you answer it, then interrogates the answers, proposes a phase breakdown, and generates the kit following the `harness/starter_kit_process/` methodology.
- `/front-end-kit <topic>` — initiates the Front-End Kit agent: turns a finished starter kit into a `front-end-kit/<topic>/` folder — route skeleton, navigation map, workflow verdicts, key workflows — following `harness/front_end_kit_process/`.
- `/front-end-kit-build <topic>` — builds the optional throwaway Flask stager for an already-staged front-end kit.
- `/kit-complete <app-name> <kit-name> "<summary>"` — archives a completed **starter** kit to `docs/<app-name>/project_history/` and logs it with a completion date and summary in the shared `docs/technical_decisions/project_history.md` index.

## The two-kit split

Planning is split across two kits with deliberately different lifespans. Do not merge them, and do not let either take the other's job.

| | **Starter kit** — `<topic>_starter_kit/` | **Front-end kit** — `front-end-kit/<topic>/` |
| :--- | :--- | :--- |
| Command | `/kit-builder` | `/front-end-kit` |
| Covers | Problem, business rules, domain data, control layer | Routes, page goals, navigation, workflows, wizard decisions |
| Stops at | "The backend could theoretically perform these tasks" | The UI exists |
| Lifespan | **Durable** — maintained as focused context for future updates | **Disposable** — deleted once the UI is built |
| Drift | Business-rule changes are corrected here and back-propagated | Never resynced; after first build the application is the truth |
| End of life | `/kit-complete` archives it to project history | Deleted; git history preserves it |
| Process guides | `harness/starter_kit_process/` | `harness/front_end_kit_process/` |

**Why:** business rules and domain relationships barely move, so the starter kit stays valid long after the build. UI does not — the developer reshapes it by taste once it is visible, and maintaining a parallel UI spec is not worth the hassle. The front-end kit is scaffolding: committed to git so it can be reviewed and diffed, then thrown away.

**Consequences:**

- A starter kit contains **no** page inventory, route list, or UI plan. If one appears, it is in the wrong kit.
- `functionality_and_roles.md` and `model_diagram.md` are the front-end kit's primary inputs — vague capabilities there become undesignable screens.
- The front-end kit reads the **starter kit first, code second**, so the plan can be corrected before anything is built.
- `/kit-complete` archives starter kits only. Never archive a front-end kit — archiving something declared disposable is a contradiction.

## Project History Convention

Completed starter kits and major work initiatives are archived under the owning application's own `docs/<app-name>/project_history/` using the `/kit-complete` command. This provides a traceable record of what has been built, when, and for what purpose. [docs/technical_decisions/project_history.md](docs/technical_decisions/project_history.md) is the master chronological index across every app.

---

# Always-apply rules

These rules apply to **every** task in this repo, regardless of persona.

## 1. Migration strategy (development)

After **any change that adds/removes/renames a database column or table** (or otherwise alters schema: new model, field, `Meta.indexes`, constraints, etc.), use a **full reset**: clear all project-owned migration history, empty the database, regenerate migrations from current models, apply them, then re-seed.

Do **not** accumulate incremental migrations during active development.

**Workflow** — from the project root, with the dev server stopped:

- **Preferred:** `python refresh_project.py` (or use the `/refresh-project` slash command). This clears migrations, database, cache, and uploaded files, then rebuilds from scratch with seeding.
- **Alternative:** `python dev_tools/delete_database_rebuild_models.py [--seed]` (older method, does not clear cache or uploads).
- **Manual equivalent:** for each `app/<application>/migrations/`, delete every file except `__init__.py`. Clear pycache directories. Clear `app/media/` uploads. Delete `db.sqlite3` (or `DROP SCHEMA public CASCADE` on Postgres). Then `makemigrations`, `migrate`, then run available seed commands.

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
3. Proceed with the corrected path; briefly note the assumption (_"Treating `docs/ARCHITECTURE` as `harness/Architecture` — closest match."_).

Common mistakes:
- `docs/ARCHITECTURE`, `docs/DOMAIN/ARCHITECTURE` → `harness/Architecture/`
- `docs/admin/RBAC`, `docs/DOMAIN/admin/RBAC` → `harness/Authorization/rbac.md`
- `ARCHITECTURE/UX`, `docs/UX_UI` → `harness/UX_UI.md`
- `skills/backend` → `.agents/personas/backend-engineer.md`
- Any `docs/Architecture`, `docs/Authorization`, `docs/UX_UI`, `docs/Context_Scaling`, `docs/starter_kit_process`, `docs/front_end_kit_process` → same path under `harness/` instead — these moved wholesale in the harness/docs split.

## 5. UI cards render even when empty

A `pc` card (or any similarly self-contained UI section — panel, gallery, list block) must **always render**, never be conditionally hidden because its backing data is empty. Show the card with its header/chrome and an explicit empty state (e.g. `"None."`, `"No documents yet."`) instead of wrapping the whole card in `{% if data %}`.

Do **not** write:
```django
{% if documents %}
<div class="pc">...</div>
{% endif %}
```
Do write:
```django
<div class="pc">
  {% if documents %}...{% else %}<p class="has-text-grey is-size-7">None.</p>{% endif %}
</div>
```

This keeps page layout stable and signals to the user that the section was checked and is simply empty, rather than looking broken or missing. Only omit a card entirely when the *feature itself* doesn't apply to that object (not when it applies but has zero rows).

## 6. Route template inspection over browser snapshots/HTML

When investigating or working on a page with a known route/URL, trace the route to its endpoint view in the codebase and read all related template files (including layout inheritance and `{% include %}` components) directly from source code. Prefer source code inspection over capturing browser screenshots or dumping rendered page HTML.

---

## Project conventions worth knowing

- **Audit columns on every table:** `created_at`, `updated_at`, `created_by_id`, `updated_by_id`.
- **Default PK:** `BigAutoField` integer; UUID7 only for cross-table polymorphic uniqueness.
- **No business logic on models** — schema and constraints only. Mark intentional exceptions with `# DELIBERATE ANTI-PATTERN`.
- **Suffix vocabulary** (see OOP_CONTROL_PATTERNS): `Struct`, `Context`, `Factory`, `BulkFactory`, `Handler`, `Manager`, `Policy`, `Validator`, `StateMachine`, `Narrator`, `Adaptor`, `Orchestrator`. Guard files end in `_guard.py`.
- **Sharp corners everywhere** — Bulma radius variables set to `0`. No pill buttons, no rounded cards.
- **Assignment never lives in a modal** — attaching items from a pool to the record being edited uses an in-page left-heavy assignment card pair or a dual listbox. Modals are for destructive confirmations, read-only browsing, and single-field captures. See [harness/UX_UI/design_patterns/modals.md](harness/UX_UI/design_patterns/modals.md).
- **Creation flows are one long scrolling page** — a multi-card wizard on a single route with progressive enablement and a session-backed draft, not a chain of `/step-1`, `/step-2` URLs. An entity with more than one reverse FK a user would populate in the same sitting is a wizard, not a form. See [harness/UX_UI/design_patterns/multi_step_flows.md](harness/UX_UI/design_patterns/multi_step_flows.md).
- **HTMX F5 rule** — every page/state must work via a plain full-page reload; HTMX layers interactivity on top.
- **Single canonical URL per resource** with a `format=` query parameter for density (`condensed`/`medium`/`large`) and HTMX fragments (`htmx-*`). Never combine density and `htmx-*` in one request.

## Optional: lightweight work log

There is a project-local convention of appending one short line per substantive change to [dev_tools/memory.md](dev_tools/memory.md) (newest last, plain text). Use it on request — Claude Code's own memory system handles cross-session recall, so this file is purely a human-scannable paper trail.
