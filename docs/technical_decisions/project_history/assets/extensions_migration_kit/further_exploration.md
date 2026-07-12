# Further Exploration — beyond the signal migration

Captured 2026-06-07 during Phase 2. These are the **north-star** ideas and open
questions that are explicitly *out of scope* for the current migration but should
steer its seams. Recorded so the work can be paused and resumed without re-deriving
the intent.

---

## The end goal: installable **packages**

The `detail_extensions` framework is the substrate for a higher-level concept: a
developer-authored **package** that can be created, installed, and scoped to an
**asset class or asset model**, living entirely under this application.

A package bundles, as one unit:

- a **set of extensions** (the atomic units that already exist today),
- the **enablement configuration** (which of its extensions switch on, for which
  class/model),
- its **pages / infrastructure / configuration** (URLs, templates, default data).

### Worked examples (from the owner)

| Package | Model-target extensions | Asset-target extensions | Notes |
| :--- | :--- | :--- | :--- |
| **Vehicles** | `emissions_info` (per make/model) | `smog_record` (history), `vehicle_registration`, `purchase_info` | The current five extensions are essentially this package, ungrouped. |
| **Computers** | hardware-spec defaults? | `hardware_spec` (CPU/RAM/…), `operating_system` (assigned + configured) | Not built. |

### Layering

```
PACKAGE  (installable bundle, scoped to an asset class / model)
  ├── EXTENSIONS        ← atomic units: descriptor + model + factory + manifest  (exist today)
  ├── ENABLEMENT        ← which extensions are on, per class/model  (DetailExtensionsBy* tables)
  └── PAGES / CONFIG    ← URLs, templates, default data  (E6 route grammar; bodies deferred)
```

Packages sit **above** extensions. Installing a package is what *populates* the
enablement tables (instead of an admin hand-toggling individual switches).

---

## Open question carried forward — what "install" means

Installing a package is likely **two moments**, mapping onto the two lifecycles the
framework already separates:

1. **Author / register the package's extension *types*** — code; happens at
   application start (the registry, validated in `apps.ready()`). A developer ships
   this.
2. **Install the package onto a specific class / model** — *data*; an admin action
   that writes the enablement rows (and, later, default configuration). This is the
   "install for an asset class or model" step.

> **Undecided:** whether package "install" is a single atomic admin act or the
> explicit two-step above. The current substrate supports either — registration is
> global, enablement is per-target — so this can be decided when packages are built.

Other deferred questions:

- **Package manifest.** Packages probably need their own manifest (a manifest of
  extension manifests + enablement defaults + page routes), analogous to the
  per-extension `ExtensionManifest` (E5). E5 was deliberately designed as the
  precondition for an extension to "graduate to its own app" — a package manifest is
  the next rung up.
- **Uninstall / versioning.** Not considered. What happens to provisioned rows and
  state-table keys when a package is removed or upgraded.
- **Package-level pages vs per-extension pages.** The E6 route grammar is
  per-extension; a package may want an aggregate landing/config surface of its own.

---

## How the Phase 2 design serves this (do not regress)

- **Single `DetailExtensionCreationOrchestrator`** listening to both `asset_created`
  and `asset_model_created` — a single fan-in point a package installer can reason
  about, mirroring the assets-side `AssetCreationOrchestrator`.
- **Provisioning reads enablement, not hard-coded keys** — so a package that writes
  enablement rows automatically drives provisioning with no orchestrator change.
- **Provisioning-state tables** (per owner, list of provisioned keys) — idempotent
  backfill is exactly what "install a new package onto an existing class, then
  backfill its assets" will need.

Keep naming **extension-centric** for now; do not bake the package layer in until it
is explicitly scheduled.
