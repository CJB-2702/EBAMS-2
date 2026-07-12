---
type: Architecture Example
title: Sub-Application Folder Tree
description: The canonical folder tree every sub-application under app/ should follow.
tags: [architecture, layout, folder-structure, examples]
---

# Sub-application folder tree (canonical example)

This is the reference tree every sub-application under `app/` should follow. Comments describe role, not folder names.

```text
<sub-application>/
├── migrations/            # Auto-generated DB history (app root; do not relocate)
├── management/            # Custom manage.py commands
│   └── commands/
├── apps.py                # AppConfig; use ready() for wiring (e.g. signals)
├── admin.py               # Django Admin registration (thin; may call control_layer)
├── urls.py                # Maps paths to entrypoint callables (GET/POST/PUT/PATCH/DELETE)
├── presentation_layer/    # User-facing surfaces and read-side helpers used by those surfaces
│   ├── entrypoints/       # All HTTP endpoints: thin handlers; delegate to control_layer / search
│   ├── search/            # QuerySets: filter, exclude, annotate beyond one-liners
│   └── tools/             # Utilities, external APIs, shared helpers (e.g. signals)
├── control_layer/         # State changes and shared domain shaping for writes
│   ├── adapters/          # POST cleanup, DTOs, template-ready shaping (often before/after writes)
│   ├── domain_structs/    # Aggregates: related model data grouped for layers above ORM
│   └── …                  # Write orchestration modules (create/update/delete flows)
├── models/                # Schema and constraints (package, not a single file)
└── templates/
    ├── <prefix>_index.html            # Sub-app-level pages, short prefix derived from app label
    ├── <prefix>_dashboard.html
    └── <model_or_struct_namespace>/   # Micro-app slices keyed on the primary model or struct
        ├── add_<thing>_page.html
        ├── edit_<thing>_page.html
        └── fragments/                 # HTMX partials co-located with the model they describe
            └── <thing>_row.html
```

`control_layer/domain_structs/` holds typed bundles used by entrypoints, search, adapters, and write modules — not the ORM models themselves, but composites built from them.

`control_layer/` (excluding `adapters/` and `domain_structs/`) is where write orchestration lives: explicit modules that create, update, or delete persisted state. Individual Python modules sit beside `adapters/` and `domain_structs/`.

---

## Import flow for infrastructure files

| From | Typical imports |
| :--- | :--- |
| `admin.py` | `models/`, sometimes `control_layer/` |
| `management/commands/` | `presentation_layer/search`, `control_layer/` |
| `templatetags/` (if used) | `control_layer/adapters/` |
| `migrations/` | Generated from `models/`; do not hand-edit except in exceptional cases |
