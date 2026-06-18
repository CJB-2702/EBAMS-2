# Phase 3 — Configurations

Standard build specifications for asset models, and the tracking of how a given
asset actually conforms to (or deviates from) its expected configuration.

## Goal

Manage **configuration templates** (the expected build of a model — its expected
child assets and standardized modifications) and **asset configurations** (the
documented as-built state of a specific asset, with its actual modifications).

## Core concepts

- A **`ConfigurationTemplate`** belongs to an `AssetModel` and declares:
  - expected **child assets** (`TemplateChild` → by `child_model` + quantity), and
  - expected **modifications** (`TemplateModification` → `DefinedModification`).
- A **`DefinedModification`** is a reusable catalog entry; an
  **`ActualModification`** documents one really present on a specific asset.
- An **`AssetConfiguration`** links an asset to the template it's built to, with
  `is_current` and `documented_at`.

## In scope

- Assign / re-assign a configuration template to an asset (lifecycle of
  `AssetConfiguration`, `is_current` flipping, documentation status).
- Record actual modifications on an asset against defined modifications.
- Manage template contents (children, modifications) and the modification catalog.

## Out of scope

- Capabilities (P4).
- Auto-instantiating expected child assets — Phase 3 *tracks* expected vs actual;
  whether template assignment auto-creates child assets is an **open question**
  (see control plan). Default: no auto-creation; document only.

## Dependencies

- **Phase 1** (asset/model contexts; configuration templates hang off
  `AssetModel`). Phase 2 not strictly required but assumed present.

## Exit criteria

- [ ] A template can be assigned to an asset, producing an `AssetConfiguration`
      with correct `is_current` handling (only one current per asset).
- [ ] Actual modifications can be recorded/updated/retired against an asset.
- [ ] Template contents (children, modifications, catalog) are manageable through
      the control layer.
- [ ] Optional: a configuration lifecycle event is emitted via the events app
      (consistent with Phase 1 eventing).
