---
type: "Technical Decision"
title: "Initial Prompt"
description: "Captured verbatim (spelling preserved)."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-ui-plan-kit]
context_tier: 2
---

# Initial Prompt

Captured verbatim (spelling preserved). Source of truth for *intent*.

---

> make a plan to create pages to support this new infrastructure create a new kit
> for this based off of the structure of assets_ui_plan_kit,

(Context: "this new infrastructure" = the modification applicability control +
data layer just built from
[`../modification_applicability_starter_kit/`](../modification_applicability_starter_kit/)
— Phase 1 modifications built & verified, Phase 2 templates planned.)

---

## Path / reference interpretations (folder-correction rule applied)

- `assets_ui_plan_kit` → [`../assets_ui_plan_kit/`](../assets_ui_plan_kit/), the
  existing UI plan kit in the repo root. Its 8-document structure is the template
  this kit copies.
- "this new infrastructure" → the applicability engine: `ApplicabilityMode`,
  `ModificationAssetClass` / `ModificationModel`, `ApplicabilityPolicy`,
  `ApplicabilitySyncHandler`, `ModificationApplicabilityManager`,
  `ModificationApplicabilityValidator`, and the gate wired into
  `ModificationManager.add_actual_modification`.
- "pages" → screens under the **existing assets mock app**
  (`app/assets/presentation_layer/` + `app/assets/templates/assets/`), specifically
  the configuration pages (modifications, templates, asset configuration).

## Binding decisions from the request

1. **Plan first.** Produce this kit and pause for review of the page set + flow +
   the editor's mode states before building anything.
2. **Mirror `assets_ui_plan_kit`.** Same document set, same tone, same mock-first
   constraint, same "extends the events-app shell" styling.
3. **Mock-first, wire-ready.** Because the assets presentation is still a mock, the
   prototype renders hard-coded data — *but*, because the control layer is real, each
   page names the control call it will later replace its mock with. (If the user would
   rather skip the prototype and wire the real control layer directly, that is a
   one-line redirect — the page set and flow are identical; only `build_plan.md` and
   `mock_data_shapes.md` change.)
4. **Scope = applicability only.** This kit does **not** re-plan the modification or
   template CRUD pages (those exist); it adds the applicability *authoring*, *display*,
   and *enforcement* surfaces on top of them.

## Assumption surfaced for the reviewer

The single decision that changes the build (not the plan): **mock prototype** (matches
the current assets app, fastest to "feel") **vs. wire the real Phase-1 control layer**
(the engine already exists and is tested). This kit is written **mock-first** to stay
consistent with the surrounding app; the wire-points are documented so flipping to real
is mechanical. Flag a preference at the review checkpoint.
