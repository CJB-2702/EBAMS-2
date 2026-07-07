# Build Plan

Order of construction **after** the route map / flow / editor states are approved.
Mirrors the control kit's two phases so UI and control stay aligned. Each step is
visually verifiable at `localhost/assets`. Default track is **mock-first** (see the
README's binding constraints); the "Wire real" note at each step is the swap to do when
the assets app goes real.

## Wiring (once, before any page)

1. Extend the modification + template fixtures in
   [`app/assets/presentation_layer/mock_data.py`](../app/assets/presentation_layer/mock_data.py)
   with `applicability_mode` + `applicable_classes` / `applicable_models`, and add
   `mock_is_allowed`, `mock_derive_classes`, `PREVIEW_ASSETS` (see
   [mock_data_shapes.md](mock_data_shapes.md)).
2. Add the two new sub-routes to [`app/assets/urls.py`](../app/assets/urls.py):
   `modification_applicability_edit`, `template_applicability_edit` (+ the HTMX fragment
   names from [route_map.md](route_map.md)).
3. New partial templates under
   `app/assets/templates/assets/configurations/applicability/` — one editor template
   reused by both entities.

> Entrypoints stay plain functions returning `render(...)` with fixture data + the mock
> helper. No `@login_not_required` (inside the authed app).

## Step 0 — Mode tag + read card *(smallest visible slice)*
- Mode tag column on the **Defined Modifications list**; the read-only **Applicability
  card** on modification detail.
- **Checkpoint:** every modification shows its mode and "Applies to" summary on a plain
  reload. No editing yet.
- **Wire real:** card reads `ModificationApplicabilityManager.struct(mod)`.

## Step 1 — The Applicability Editor (Modification) · P1 *(the centerpiece)*
- Build the one reusable editor: mode selector → the four panel states → dead-model inline
  guard → the live "Applies to" preview (via `mock_is_allowed`).
- Mode quick-set on the detail page.
- **Checkpoint:** Flow 1 clicks end-to-end; switching modes reshapes both panels and
  re-runs the preview; STRICT refuses a dead model; MODEL_SET shows derived read-only
  classes. This is the bulk of the "feel" and the main review target.
- **Wire real:** the five panel actions → `ModificationApplicabilityManager.set_mode /
  add_class / remove_class / add_model / remove_model`; preview → `ApplicabilityPolicy`.

## Step 2 — Gated apply flow · P1
- Make the `asset_configuration_edit` available-mods column applicability-aware: disabled
  rows + `explain(...)` reason; permitted-badge on the configuration detail.
- **Checkpoint:** Flow 2 — an engine mod is visibly un-addable to a forklift, with the
  reason, *before* submit; a permitted mod adds normally.
- **Wire real:** per-candidate `ModificationApplicabilityValidator.check(asset, mod)`.

> **End of Phase 1 UI** — fully reviewable against the already-built Phase-1 control layer.
> If wiring real, Steps 0–2 can attach to the live engine immediately (it exists & is
> tested); only the surrounding assets pages remain mock.

## Step 3 — Template applicability · P2 *(reuse)*
- Bind the **same editor** to templates (`template_applicability_edit`); default
  `MODEL_SET` seeded from the template's model. Mode tag + card on template list/detail.
- Builder applicability section.
- **Checkpoint:** Flow 3 (first half) — a template's applicability authors with the same
  component the modification used.
- **Wire real:** `TemplateApplicabilityManager.*` (built in Phase 2 control), reusing the
  shared `ApplicabilityPolicy` / `ApplicabilitySyncHandler`.

## Step 4 — Template ↔ modification compatibility · P2
- In the builder, run the compatibility check when a mod is added: block provable
  conflicts with the reason, allow-but-warn the undecidable; per-mod compatibility strip
  on template detail.
- **Checkpoint:** Flow 3 (second half) — adding an incompatible mod to a template is
  blocked with an explanation; an undecidable one is added with a warning chip.
- **Wire real:** `ApplicabilityCompatibilityPolicy.can_add(template, mod)` (Phase 2
  control deliverable).

## Done = reviewable

When Steps 0–2 render, the prototype conveys the full modification-applicability
experience against a real, tested engine. Steps 3–4 extend it to templates once Phase 2
control lands. Feedback feeds the real wiring (flip each "Wire real" note).

## Guardrails

- **One editor component** for both entities — do not fork it per entity (the control
  layer is shared; the UI must be too).
- **Mock helper mirrors the real policy line-for-line** so authoring and enforcement agree
  and the wire-up is a drop-in.
- **Match the assets/events app** for shell, `pc` cards, dual-listbox, buttons, tags,
  sharp corners, Material Icons.
- **F5 rule** on every page and every mode state; HTMX only enhances.
- Don't touch real `app/assets/models/` or migrations — this is presentation only. (The
  models already carry the real fields from Phase 1.)
