---
type: "Technical Decision"
title: "Navigation & Flow"
description: "How the applicability surfaces connect, where they live in the existing assets shell,."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-ui-plan-kit]
context_tier: 2
---

# Navigation & Flow

How the applicability surfaces connect, where they live in the existing assets shell,
the click-flows, and the anatomy of the centerpiece **Applicability Editor** and its
four mode states. This is the document to review for **flow + page structure**.

## Where it lives in the shell

No new sidebar section. Applicability rides on the **existing** Configurations area of the
assets mock (`asset_base.html` shell, cloned from the events app):

```
CONFIGURATIONS                       ← existing sidebar group
  ▸ Templates                 /assets/configurations/templates/
  ▸ Defined Modifications     /assets/configurations/modifications/
```

- The **editor** is reached *from* a modification (or template) detail page, never from
  the sidebar — it is an attribute of an item, not a destination.
- Every page extends `asset_base.html` and obeys the F5 rule; HTMX layers the
  mode-switch and dual-listbox interactions on top.

## Primary click-flows

### Flow 1 — Author a modification's applicability (the main loop) · P1
```
Defined Modifications List
   │  (Mode tag column shows current restriction at a glance)
   ▼
Modification Detail ──▶ Applicability Card (read)
   │                       │
   │                       ├─▶ Mode quick-set (flip mode inline, HTMX)
   │                       └─▶ [Edit applicability] ──▶ Applicability Editor
   ▼                                                        │
Applicability Editor (mode selector + 2 panels + preview)   │
   │   pick mode → panels reshape → author lists            │
   │   "Applies to" preview updates live                    │
   └──────────────── Save (mock success) ──────────────────▶ back to Detail
```

### Flow 2 — Apply a gated modification to an asset · P1
```
Asset-360 ──▶ Asset Configuration ──▶ Asset Configuration Edit
                                          │
                                          ▼
                              Gated Modification Picker
                                ├─ permitted mods → add
                                └─ forbidden mods → disabled row + reason
                                     ("Engine Swap: asset model 'ThinkPad'
                                       not in permitted model set")
```

### Flow 3 — Author a template's applicability & guard its members · P2
```
Config Template Detail ──▶ Template Applicability Card
   │                          └─▶ [Edit applicability] ──▶ Applicability Editor (template)
   ▼
Config Template Builder
   │  add modification ──▶ Compatibility guard runs
   │       provable conflict → blocked + reason
   │       undecidable        → added + warning chip
   └─ per-mod compatibility strip reflects results
```

## Applicability Editor anatomy

The single most important screen — the applicability analog of the Asset-360 page.
It is **one template** reused for modifications (P1) and templates (P2), parameterized by
entity. Layout uses the repo's `body-grid has-rail`, `pc` cards, sharp corners,
Material Icons, and the **dual-listbox** component
([`harness/UX_UI/dual_listbox.md`](../harness/UX_UI/components/dual_listbox.md)).

```
page-hero:  [tune icon] Applicability — {item.name}        [Save] [Cancel]
            {item.code} · current mode tag

┌─ MODE SELECTOR (segmented, full width) ─────────────────────────────────────┐
│  ( ) Unrestricted   ( ) Class only   ( ) Model set   (•) Strict             │
│  helptext: one line describing the selected mode's rule (from the matrix)    │
└──────────────────────────────────────────────────────────────────────────────┘

body-grid (has-rail)
┌─ MAIN (3fr) ───────────────────────────────────┐ ┌─ RAIL (1fr) ──────────────┐
│ ▸ Asset Classes panel   (dual-listbox)          │ │ ▸ "Applies to" preview    │
│     available │ selected                        │ │   sample assets, each ✓/✗ │
│                                                 │ │   with the policy reason  │
│ ▸ Asset Models panel    (dual-listbox)          │ │                           │
│     available │ selected                        │ │ ▸ Combine rule reminder   │
│     [inline error slot for dead-model guard]    │ │   (AND, from the matrix)  │
└──────────────────────────────────────────────────┘ └───────────────────────────┘
```

### The four mode states (each is the same two panels, reshaped)

The mode selector is the master control. Switching it HTMX-swaps both panels into their
mode-correct form and re-runs the preview. Each state below traces to
[`modification_class_and_model_matrix_behaviors.md`](../modification_applicability_starter_kit/modification_class_and_model_matrix_behaviors.md).

| Mode | Classes panel | Models panel | Preview rule | Special UX |
| :--- | :--- | :--- | :--- | :--- |
| **UNRESTRICTED** | muted, "Suggestions only — not enforced" | muted, "Suggestions only — not enforced" | everything passes | Green banner: "Applies to any asset." Lists collapsed by default. |
| **CLASS_ONLY** | **editable, binding** ("Required: asset must be in one of these classes") | muted, "Suggested models (search hints)" | `class ∈ classes` | — |
| **MODEL_SET** | **read-only derived** chips, "Auto-derived from the selected models" + count | **editable, binding** ("Required: asset must be one of these models") | `model ∈ models` | Classes panel has no add/remove controls; re-renders when models change. |
| **STRICT** | **editable, binding** | **editable, binding** | `class ∈ classes` AND `model ∈ models` | **Dead-model guard:** trying to add a model whose parent class ∉ classes shows an inline error and refuses the add. |

### Mode-transition feedback (matches the Manager's `set_mode`)

When the user switches mode, mirror the control layer's normalization with a small
confirm/notice so nothing silently changes shape:

- **→ MODEL_SET:** "Class list will be auto-derived from your models." Classes panel
  becomes read-only; derived chips populate.
- **→ STRICT:** if any existing model is a "dead model" (parent class absent), show a
  blocking notice listing them — "Resolve these before switching: …" (mirrors
  `_assert_no_dead_models`).
- **→ CLASS_ONLY / UNRESTRICTED:** "Your model list is kept as suggestions." Non-destructive.

### The "Applies to" preview (the policy made visible)

A rail card running the mock equivalent of `ApplicabilityPolicy.is_allowed` over a small
fixed set of sample assets (one per class + a couple of cross-class models, enough to
show every mode's behavior — including the headline *engine-mod-on-a-laptop* ✗). Each row:

```
✓  FL-North-014    Forklift · 8FGCU25
✗  EX-Eng-002      Excavator · 320 GX      — class not in permitted set
```

This is the same data the **gated picker** (Flow 2) uses, so authoring and enforcement
visibly agree.

## Gated Modification Picker anatomy (Flow 2)

Inside the existing `asset_configuration_edit` page, the "available modifications" column
of its dual-listbox is filtered through applicability for *this* asset:

```
Available modifications (for FL-North-014 · Forklift · 8FGCU25)
  ▸ Side Shifter        [Add]
  ▸ Cold Cab            [Add]
  ▸ Engine Swap         (disabled)  ⓘ not permitted: model not in {320 GX}
```

- Permitted rows behave normally.
- Forbidden rows are disabled with the `explain(...)` reason as tooltip/helptext — the
  refusal happens **before** submit, not as a post-POST error.

## Density & format

Follows the repo `format=` contract
([`harness/UX_UI/format_contract.md`](../harness/UX_UI/format_contract.md)). The editor builds at
**medium**; list mode-tags use the existing `_status_tag.html` pattern for consistency.
Never combine a `format=` density with an `htmx-*` fragment request (project rule).
