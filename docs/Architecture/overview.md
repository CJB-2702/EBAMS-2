---
type: Architecture Guide
title: Architecture Overview
description: The layered sub-application layout and the responsibilities of each layer.
tags: [architecture, layout, layers, overview]
---

# Sub-application layout and layer responsibilities

This document defines the "Extra-Explicit" layout for Django apps in this project. HTTP handling, business logic, data access, and presentation-oriented shaping are split into dedicated layers so behavior stays easy to find and change.

The end state is **six major sub-applications** (Django apps), each owning roughly **six micro-applications** — cohesive feature slices that usually center on a **model** or **domain struct** and live *inside* one sub-application's codebase and template tree, not as separate `INSTALLED_APPS` unless you deliberately split them.

Standard Django files (`migrations/`, `apps.py`, `admin.py`, `management/commands/`, optional `templatetags/`) are treated as **configuration** or **infrastructure** and kept separate from the business/logic layers below.

For the verbatim folder tree, see [Examples/sub_application_tree.md](Examples/sub_application_tree.md).

---

## Layer responsibilities

| Layer | Primary goal | Allowed imports |
| :--- | :--- | :--- |
| **Presentation / entrypoints** | All HTTP methods (GET, POST, PUT, PATCH, DELETE): parse requests, call search or control layer, return responses. | `control_layer`, `presentation_layer/search`, `presentation_layer/tools`, `models` |
| **Presentation / search** | Encapsulate complex read/query logic; often assemble `domain_structs` from querysets. | `models`, `control_layer/domain_structs` |
| **Presentation / tools** | Cross-cutting helpers (signals, integrations) used by entrypoints or app startup. | `models`, `control_layer`, `presentation_layer/search` (sparingly; avoid cycles) |
| **Control / adapters** | Transform data for UI or downstream use; clean input before writes. | `models`, `presentation_layer/search`, `control_layer/domain_structs` |
| **Control layer (writes)** | Orchestrate writes (create/update/delete flows). | `models`, `presentation_layer/search`, `control_layer/domain_structs` |
| **Control / domain structs** | Typed aggregates of related model data (graphs, nested bundles). | `models` |
| **Models** | Schema and integrity rules. | None above the ORM/base layer |

**Golden rule:** Dependencies flow *downward*. A model must not import the control layer or a domain struct. Search must not import an entrypoint.

---

## Template layout

Within `<sub-app>/templates/`, distinguish **sub-application** (whole Django app) surfaces from **micro-application** (feature slice) surfaces.

**Sub-application templates** — pages and partials that belong to the sub-app as a whole. Name with a short prefix derived from the sub-application label, an underscore, then the template role. Example: `events-application/templates/ea_dashboard.html` for a prefix `ea`.

**Micro-application templates** — feature slices and their fragments are usually tied to a specific model or domain struct. Name the subdirectory after that primary type so the template namespace matches the data it represents. Example: `events-application/templates/comment/add_comment_page.html`.

When rendering, use the path relative to `templates/` (e.g. `ea_dashboard.html`, `comment/add_comment_page.html`).

Optional: `templatetags/` only if unavoidable; prefer preparing data in entrypoints, `presentation_layer/search`, or `control_layer/adapters` before render.

---

## Implementation patterns

### Adapter pattern
Code in `control_layer/adapters/` cleans `request.POST` (or similar) before a write runs, or shapes model instances into template contexts.

### Search pattern
Any `.filter()`, `.exclude()`, or `.annotate()` chain longer than one line belongs in `presentation_layer/search/` so entrypoints stay thin "traffic controllers."

### Domain structs pattern
Keep aggregate **types** (plain classes, dataclasses, `NamedTuple`, or similar) in `control_layer/domain_structs/`. Prefer constructing instances in `presentation_layer/search` or in control-layer write modules so `domain_structs/` stays mostly declarative and does not need to import `presentation_layer/search` (avoids cycles).

A struct's job is to turn **one id into a cluster of related data** — never a bare filtered list from a single table with nothing composed around it (that belongs in `presentation_layer/search/` as a plain queryset function instead). Example: an asset struct accepts an asset id, then gathers its model, manufacturer, and asset class — one id in, a small graph of related data out.

Base "identity" structs (guarantee one row exists, `select_related` its immediate FKs) are the exception that proves the rule — they exist specifically to be composed into aggregate structs, not to stand alone. See [patterns/domain_structs_cont.md](patterns/domain_structs_cont.md) for construction conventions, composition examples, and a checklist, grounded in the real structs already in this codebase (`AssetStruct`, `AssetThreeSixtyStruct`, `EventDetailStruct`, `PartContext`).

### Writes vs reads
- **Control layer** changes system state (writes) and holds adapters plus domain aggregates used by those flows.
- **Presentation / search** answers questions about state (reads).

If a flow needs both, the entrypoint calls search then the control layer (or the reverse), instead of mixing read and write in one place.

### HTMX fragments
Templates used only as HTMX responses (table rows, modals, inline form errors) sit in `templates/<model_or_struct_namespace>/fragments/` so partials stay next to the full pages for that slice. See [patterns/htmx_patterns.md](patterns/htmx_patterns.md) for request/response conventions.

---

## Django "plumbing" files

| File / folder | Role |
| :--- | :--- |
| `migrations/` | Schema history; stays at the app root. `makemigrations` expects it there. Do not move manually. |
| `apps.py` | `AppConfig` plus app startup. Import signals from `presentation_layer/tools/signals.py` inside `ready()`. |
| `admin.py` | Registers models with Django Admin. Treat like a specialized surface — import from `models/` and, for actions, `control_layer`. |
| `management/commands/` | Custom CLI. Parse args, then delegate to control layer or search — same discipline as HTTP entrypoints. |
| `templatetags/` | Avoid when possible. If unavoidable, keep thin and call into `control_layer/adapters/`. |

---

## Adding a new application

1. `python manage.py startapp [app_name]`.
2. Remove the default `views.py` and `models.py`.
3. Create the directory tree (see [Examples/sub_application_tree.md](Examples/sub_application_tree.md)).
4. Add `__init__.py` files so packages resolve.
5. Register the app in `config/settings.py`.
6. Add the app's `urls.py`: import HTTP handlers from `presentation_layer.entrypoints` and wire `urlpatterns`.
7. Include the app's URLs from the project `urls.py`.
