---
okf_version: "0.1"
type: "Technical Debt"
title: "Configuration Section Extraction"
description: "Configuration Management presents as its own application section but all of its models, control layer, entrypoints, and routes still live in app/assets. Nav-only split shipped for a demo; the backend extraction is deferred with a measured blast radius."
tags: [assets, configuration, capabilities, refactor, tech-debt, deferred, presentation-shell]
context_tier: 2
personas: [backend, frontend, code-architect]
created: 2026-08-23
created_by: Christian Bissett
updated: 2026-08-23
updated_by: Christian Bissett
---

# Configuration Section Extraction

**Status:** acknowledged tech debt. **Deferred deliberately** under demo pressure
(2026-08-23, demo 2026-08-25). What shipped is a **navigation-only** split: the
Configuration Management section looks like its own application but is served
entirely by `app/assets`. This document records what was done, what was
deliberately *not* done, and the measured cost of finishing the job.

---

## 1. What shipped (nav-only)

A new Django app, `app/configuration`, exists as a **presentation shell**. It
contains no models, no control layer, and no migrations.

| Change | File(s) |
| :--- | :--- |
| New app registered | `app/config/settings.py` (`INSTALLED_APPS`), `app/configuration/apps.py` |
| Mounted at `/configuration/` | `app/config/urls.py` |
| Section shell (own sidebar, own `#configuration-main-content` HTMX target) | `app/configuration/templates/configuration/base.html` |
| Serialized-part placeholder routes + pages | `app/configuration/urls.py`, `app/configuration/presentation_layer/entrypoints/serialized_parts.py`, `app/configuration/templates/configuration/serialized_parts/{templates,history}.html` |
| New `Configuration` topnav tab; Capabilities + Configurations groups moved out of the `Assets` tab | `app/public_app/templates/shared/topnav.html` |
| Active-tab highlight for the new group | `app/static/css/custom_css.css` |
| Capabilities + Configurations sidebar groups removed; `Asset Relationships` regrouped under a `Relationships` label; cross-link to Configuration added | `app/assets/templates/assets/asset_base.html` |
| 19 templates repointed `{% extends %}` from `assets/asset_base.html` to `configuration/base.html` (one line each; no content changed) | `app/assets/templates/assets/{configurations,capabilities}/**` |

### The load-bearing accident that made this cheap

`app/assets/urls.py` declares **no `app_name`** and `app/config/urls.py` includes
it **without a namespace**, so every URL name is global. The Configuration
sidebar and topnav therefore reverse the *existing* `assets` URL names with no
changes to any view, and every `{% url %}` tag project-wide kept working. This
is also why the eventual route move is cheap — see §4.

### Deliberately left on the Assets shell

Four asset-scoped drilldowns still extend `assets/asset_base.html` and highlight
`nav_assets`, because they are reached *from* an asset and switching section
chrome mid-drilldown would be jarring:

- `capabilities/asset_capabilities_detail.html`, `capabilities/asset_capabilities_edit.html`
- `configurations/asset_configuration_detail.html`, `configurations/asset_configuration_edit.html`

Revisit this when the section is real; it is a UX call, not a technical constraint.

### Fixed in passing

`asset_base.html` defined the sidebar blocks `nav_templates` and `nav_mods`, but
eight templates override `nav_config_templates` and `nav_defined_modifications`.
Django silently discards overrides of blocks that do not exist, so those eight
pages had **no active sidebar item**. `configuration/base.html` defines the block
names the templates already use, which fixes the highlight.

---

## 2. What is still wrong

- `app/assets` is unchanged in size (~10,370 LOC Python excluding migrations,
  ~60 templates). Nothing was actually extracted.
- URLs read `/assets/configurations/...` and `/assets/capabilities/...` while the
  section presents as `/configuration/`. Deliberate — the demo did not need the
  path change and aliasing was declined to keep churn at zero.
- Templates for a section owned by `app/configuration` live under
  `app/assets/templates/assets/`. Anyone navigating from URL to code takes an
  extra hop.
- **The growth trap:** the three planned features (serialized part tracking,
  serialized part templates per model, serialized part history) are *models*. If
  they land in `app/assets/models/`, the app this split was meant to shrink gets
  bigger and this debt compounds.

---

## 3. Standing rule until this is resolved

> **New configuration-domain models go in `app/configuration/models/`, not
> `app/assets/models/`.** Legacy configuration and capability models stay in
> `app/assets` until the §4 extraction happens.

Cross-app FKs cost nothing — use lazy string references
(`"assets.AssetModel"`, `"assets.Asset"`, `"parts.Part"`), exactly as
`app/dispatching/models/abstract_mixins.py` already references
`"assets.ConfigurationTemplate"`. This keeps the split *directional*: new weight
accrues to the new app without paying the app-label, fixture, and dispatching
bill up front.

The serialized-part models are also the first place `parts` and `assets` meet —
`app/assets` currently has **zero** `app.parts` imports — so a third app owning
that junction is correct regardless of what happens to the legacy models.

---

## 4. Blast radius of the full extraction

Measured 2026-08-23 by grep/scan across `app/`. The models in scope are the 9
under `app/assets/models/configurations/` and the 4 under
`app/assets/models/capabilities/`.

### 4.1 What makes it tractable

- **FKs run one direction only.** Configuration and capability models point *at*
  core (`Asset`, `AssetClass`, `AssetModel`, `events.Event`). Nothing in
  `models/core/` or `models/domain_junctions/` points back. No circular FK.
- **No migrations to author.** Per `.claude/CLAUDE.md`, schema changes use a full
  reset via `refresh_project.py`.
- **URL names are global** (no `app_name`, no namespace), so moving `path()`
  entries while keeping names identical breaks **zero** `{% url %}` tags.
- **Slice size:** ~2,580 LOC Python and ~5,320 LOC templates — roughly a quarter
  of the app's Python and a third of its templates.

### 4.2 Tier 1 — cross-app fallout (small)

Only `app/dispatching` references these models. Six files:

| File | Change needed |
| :--- | :--- |
| `models/abstract_mixins.py` (L27, L71, L88) | FK strings `"assets.CapabilityDefinition"`, `"assets.ConfigurationTemplate"`, `"assets.DefinedModification"` → new app label |
| `presentation_layer/entrypoints/dispatch_views.py` (L266, L483) | `from app.assets.models import …` |
| `presentation_layer/entrypoints/template_views.py` (L44, L337) | same |
| `presentation_layer/search/requirement_pool_search.py` (L12) | same |
| `management/commands/seed_dispatching_dev.py` (L47–52) | same |
| `tests/base.py` (L13) | `CapabilityDefinition` import |

Plus **47 of 105 rows** in `app/assets/fixtures/dev_assets_base.json` need their
`"model": "assets.<x>"` label rewritten (mechanical).

`detail_extensions`, `maintenance`, `inventory`, `events`, and `procurement`
reference **only** `Asset`, `AssetClass`, `AssetModel`, `Manufacturer`, and
`MeterHistory` — entirely out of scope.

### 4.3 Tier 2 — intra-assets seams (the real work)

Each of these is a place asset *core* reaches into configuration or capability,
and each becomes a back-edge from `app/assets` into `app/configuration`:

1. **`AssetThreeSixtyStruct`** — `control_layer/domain_structs/asset_three_sixty_struct.py:72-73`
   composes `AssetCapabilityStruct` + `AssetConfigurationStruct`. Backs the asset
   detail 360 page.
2. **`build_asset_display`** — `presentation_layer/search/asset_search.py:133,144`
   pulls both structs into the asset detail/list bundle.
3. **Class and model editing writes capability rows** —
   `control_layer/asset_class_context.py:84` (`set_capabilities`),
   `control_layer/asset_model_context.py:140` (`set_capabilities`), both adaptors
   parsing `assigned_capabilities` from POST, and the dual-listbox UI in
   `templates/assets/classes/form.html` and `templates/assets/models/form.html`.
4. **Creation cascade** — `control_layer/factories/asset_model_factory.py:72`
   (`CapabilityFactory.copy_class_to_model`) and
   `control_layer/orchestrators/asset_creation_orchestrator.py:41`
   (`CapabilityFactory.copy_model_to_asset`).
5. **`AssetEventNarrator`** — `control_layer/narrators/asset_event_narrator.py:53-63`
   owns the modification add/remove event copy.
6. **Section chrome** — the four asset-scoped drilldowns listed in §1 and the
   configuration/capability cards in `templates/assets/assets/detail.html`.

**Recommended approach for 1 and 2:** do not create a back-import. Convert the
configuration and capability cards on the asset detail page into HTMX fragment
endpoints owned by `app/configuration`, `hx-get`-loaded by the asset detail
template. `asset_configuration_detail` and `asset_capabilities_detail` already
exist as full pages, so the F5 rule is satisfied without extra work.

**For 3 and 4:** use function-local lazy imports, already the prevailing idiom
across `app/dispatching`.

### 4.4 Non-issues (verified, do not re-litigate)

- **HTMX target mismatch across sections.** `hx-boost="true"` is scoped to the
  `<nav>` element in every section base, never `<body>`. Content-area links —
  including the Configuration/Capabilities buttons in
  `templates/assets/assets/detail.html:30,96,120` — are plain full-page loads.
  No `hx-boost="false"` guards and no target-id reconciliation needed.
- **Template block contract.** The 19 repointed templates use only `title`,
  `content`, `breadcrumb`, `extra_head`, `extra_css`, `body_scripts`, and `nav_*`.
  `configuration/base.html` defines all of them. No template references
  `#asset-main-content` directly.

---

## 5. Outline of the work, in order

1. **Decide the capabilities question.** Move capabilities with configurations,
   or leave it. Recommended: move it. Same shape of problem (definition catalog
   assigned at class/model/asset with cascade), `dispatching` couples to it
   identically, and leaving it behind removes ~15% of the app instead of ~25%.
   Cost: it deepens Tier 2 items 3 and 4, the messiest seams. The lower-risk
   variant is configurations first, capabilities in a second pass.
2. **Move routes.** Relocate the ~20 configuration/capability `path()` entries
   from `app/assets/urls.py` into `app/configuration/urls.py`, **keeping URL
   names byte-identical**. Zero template edits. URLs become `/configuration/…`.
3. **Move presentation.** `entrypoints/configurations.py`,
   `entrypoints/capabilities.py`, `search/configuration_search.py`,
   `search/capability_search.py`, and the two template directories into
   `app/configuration`. Repoint `{% extends %}` and `render()` paths.
4. **Move the control layer.** `control_layer/configurations/`,
   `control_layer/capabilities/`, the four config/capability guards, the three
   config/capability domain structs, and the two adaptors.
5. **Move the models,** then resolve the six Tier 2 seams (§4.3) — the 360-page
   fragment conversion is the only piece needing real design.
6. **Relabel Tier 1:** six `dispatching` files, 47 fixture rows.
7. **Reset:** `python refresh_project.py`, then re-run the page probe in §6.
8. **Reconsider** whether the four asset-scoped drilldowns should follow.

---

## 6. Verification used for the nav-only change

All 23 affected pages were probed for HTTP 200, correct shell
(`#configuration-main-content` vs `#asset-main-content`), correct
`data-current-application-group`, and correct sidebar `is-active` entry. All
passed. `python manage.py check` clean; `makemigrations --dry-run` reports no
changes, confirming zero schema impact.

Re-run the same probe after each step in §5 — it is the cheapest regression
signal available for this refactor.
