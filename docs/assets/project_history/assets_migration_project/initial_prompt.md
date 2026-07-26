---
type: "Technical Decision"
title: "Asset Management Application — Migration Brief"
description: "A new assets sub-application at app/assets/ inside the Django Starter Kit project."
tags: [technical-decisions, technical-decision, project-history, assets-migration-project]
context_tier: 2
---

# Asset Management Application — Migration Brief

## Referenced in Initial Query

**Slash commands:**
- `/backend-persona`

**Process guide:**
- [harness/starter_kit_process/index.md](../harness/starter_kit_process/index.md)

**New project architecture:**
- [harness/Architecture/layer_rules.md](../harness/Architecture/layer_rules.md)

**Old application source:**
- [/home/cb/REPOS/asset_management/app](/home/cb/REPOS/asset_management/app) — full old app root
- [/home/cb/REPOS/asset_management/Design/LayeredArchitecture.md](/home/cb/REPOS/asset_management/Design/LayeredArchitecture.md) — old layered architecture doc
- [/home/cb/REPOS/asset_management/Design/modules/core_structure.md](/home/cb/REPOS/asset_management/Design/modules/core_structure.md) — old core module structure
- [/home/cb/REPOS/asset_management/Design/modules/assets_structure.md](/home/cb/REPOS/asset_management/Design/modules/assets_structure.md) — old assets module structure

---

## What We Are Building

A new `assets` sub-application at `app/assets/` inside the Django Starter Kit project. It consolidates everything previously split across two separate Flask repos into one Django application following the project's layered architecture.

---

## Source of Truth (Old App)

Old application: `/home/cb/REPOS/asset_management/`

| Old Layer | Old Path |
| :--- | :--- |
| Core entity models (asset, class, make/model) | `app/data/core/asset_info/` |
| Asset sub-module models (details, caps, configs) | `app/data/assets/` |
| Business logic / context managers | `app/business/core/` and `app/business/assets/` |
| Read queries / intermediate layer | `app/intermediate/assets/` |

Old architecture (Flask / SQLAlchemy):
- Data Layer → Business Layer → Presentation Layer → Services Layer
- Access control was location-based: every asset and related row carried a `major_location_id`

---

## Target (New App)

New application: `app/assets/` in this Django Starter Kit project.

New architecture: standard project layered structure:
```
app/assets/
├── models/
├── control_layer/   (adapters/, domain_structs/, write modules)
└── presentation_layer/  (entrypoints/, search/, tools/)
```

---

## Structural Mapping

| Old | New |
| :--- | :--- |
| `app/data/core/asset_info/` | `app/assets/models/core/` |
| `app/data/assets/*` | `app/assets/models/*` |
| `app/business/core/` (asset-related) | `app/assets/control_layer/` |
| `app/business/assets/` | `app/assets/control_layer/` |
| `app/intermediate/assets/` | `app/assets/presentation_layer/search/` |

---

## Key Design Changes

### 1. Access Control — Location → Data Domain

Old: every asset had a `major_location_id` FK to `MajorLocation`.
New: every asset has a `domain_id` FK to `Domain` (from `administration` app).

The "Golden Rule" applies: a row is visible if and only if its `domain_id` is in the user's assigned domain set.

Additional domain scoping rules:
- **`Asset`** → one `domain_id` (single domain, FK)
- **`AssetModel`** → own `domain_set` (M2M to Domain)
- **`AssetClass`** → own `domain_set` (M2M to Domain, must have at least one), plus `restrict_to_domain_set` boolean (default False)
- Associated sub-application data (maintenance, dispatch, inventory) inherits access from the parent asset — if you cannot see the asset, you cannot see its records

### 2. Model Definition — Make/Model → AssetModel with Revisions

Old: `MakeModel` had separate `make` and `model` string fields, flat structure.
New: `AssetModel` is restructured with:
- `model_name` — primary name (replaces combined make+model)
- `subtype_name` — optional variant/subtype designation
- `revision` — string revision identifier
- `is_base_model` — boolean, True for canonical base; False for revision/variant
- `base_model_id` — self-referential FK to the base model this revision derives from
- `manufacturers` — M2M to new `Manufacturer` entity (extracted from old flat `make` field)

Revision hierarchy:
```
BaseAssetModel  (is_base_model=True, base_model_id=NULL)
  └── RevisionVariant  (is_base_model=False, base_model_id → base)
```

### 3. Permission Model

Page-level access and action permissions are managed through Django permission groups (RBAC system already in the starter kit). This replaces the old role/module system.

---

## Sub-Application Scope

The `app/assets/` application absorbs:
1. Core asset identity and hierarchy (asset, asset class, model, manufacturer)
2. Asset capabilities
3. Asset configurations (templates and modifications)
4. Asset detail tables (extensible per-class and per-model extra fields)
5. Meter history
6. Asset images (linking to `events` app's attachment/file system)

Sub-applications for maintenance, dispatching, and inventory are **out of scope** for this phase — they will be separate Django apps that reference `app/assets/` models.

---

## Phase Focus

This starter kit is focused on **models and control layer only**. Templates, routes, and URLs are explicitly excluded from this planning phase.

---

## Planning Documents in This Folder

| File | Purpose |
| :--- | :--- |
| `initial_prompt.md` | This brief — migration intent and key decisions |
| `01_business_concept.md` | Non-technical feature capabilities document |
| `02_data_relational_plan.md` | Full table inventory and relational diagram |
| `03_control_layer_plan.md` | Structs, Contexts, Managers, Handlers, Factories |
| `04_model_migration_map.md` | File-by-file mapping: old path → new path + notes |
