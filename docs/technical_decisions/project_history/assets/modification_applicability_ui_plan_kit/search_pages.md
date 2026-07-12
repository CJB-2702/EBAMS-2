---
type: "Technical Decision"
title: "Search / List Page Updates"
description: "Applicability adds **columns and filters** to two existing list pages and changes the."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-ui-plan-kit]
context_tier: 2
---

# Search / List Page Updates

Applicability adds **columns and filters** to two existing list pages and changes the
behavior of one picker. This document specifies only the **deltas** — the base columns are
defined in [`../assets_ui_plan_kit/search_pages.md`](../assets_ui_plan_kit/search_pages.md).

---

## 1. Defined Modifications List (`/assets/configurations/modifications/`) · P1

*Existing page* (`defined_modification_index`). Add applicability visibility.

**New filters:**
*   **Applicability Mode:** Unrestricted · Class only · Model set · Class + model
*   **Restricts Asset Class:** multi-select — modifications whose binding/derived class
    set includes a chosen class (answers "what mods can a Forklift take?")
*   **Restricts Asset Model:** multi-select — same, by model

**New / changed columns:**
1.  Name *(existing — link to detail)*
2.  Code *(existing, monospace)*
3.  Category *(existing)*
4.  **Mode** *(new — mode tag, colour per `mock_data_shapes.md`)*
5.  **Applies To** *(new — compact summary: "Class only · Forklift", "Model set · 1 model",
    "Unrestricted", "Strict · 1 class + 1 model")*
6.  Template Uses *(existing rollup)*
7.  Active *(existing)*
8.  Actions: View · **Edit Applicability** *(new quick link → the editor)*

---

## 2. Config Templates List (`/assets/configurations/templates/`) · P2

*Existing page* (`config_template_index`). Same treatment as modifications.

**New filters:**
*   **Applicability Mode**
*   **Restricts Asset Class / Model** (as above)

**New / changed columns:**
1.  Template Name *(existing)*
2.  Revision *(existing)*
3.  Target Asset Model *(existing)*
4.  **Mode** *(new — mode tag)*
5.  **Applies To** *(new — summary)*
6.  Child Assets Required *(existing rollup)*
7.  Active *(existing)*
8.  Actions: View · **Edit Applicability** *(new)*

---

## 3. Gated Modification Picker (within `asset_configuration_edit`) · P1

Not a standalone list — the "available modifications" column of the asset configuration
editor's dual-listbox, now **applicability-aware** for the specific asset.

**Context:** the asset's `asset_class` + `model` (e.g. *Forklift / 8FGCU25*).

**Row treatment:**
| Verdict | Row state | Affordance |
| :--- | :--- | :--- |
| Permitted | normal, enabled | `[Add]` moves it to "assigned" |
| Forbidden | disabled, muted | ⓘ tooltip = `explain(...)` reason; no `[Add]` |

**Optional filter toggle:** "Hide modifications that can't be applied here" (default off, so
users still *see* why something is unavailable — discoverability over tidiness).

**Columns:**
1.  Name
2.  Code *(monospace)*
3.  Mode *(mode tag — explains *why* a row may be blocked)*
4.  Status *(✓ Permitted / ✗ reason)*
5.  Action *([Add] or disabled)*

---

## Notes

- All three reuse the repo searchbar + dropdown idiom
  ([`docs/UX_UI/searchbars.md`](../docs/UX_UI/components/searchbars.md)) and the dual-listbox
  ([`docs/UX_UI/dual_listbox.md`](../docs/UX_UI/components/dual_listbox.md)).
- In the **mock**, filtering and verdicts run off the fixtures + `mock_is_allowed` from
  [mock_data_shapes.md](mock_data_shapes.md); the real build swaps these for control-layer
  queries and `ApplicabilityValidator` per candidate.
- The "Restricts Asset Class/Model" filters intentionally read the **binding-or-derived**
  set (not raw suggestion lists) so the answer matches what the gate would actually allow.
