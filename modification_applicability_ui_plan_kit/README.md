# Modification Applicability UI Plan Kit
Created 2026/06/09

A **UI prototyping kit** for the pages that let a person *author* and *see*
**modification applicability** — the mode + class/model allow-lists that decide
where a `DefinedModification` (and, in Phase 2, a `ConfigurationTemplate`) may be
applied. It is the screen layer on top of the control engine built by the
[`../modification_applicability_starter_kit/`](../modification_applicability_starter_kit/).

**This kit is the plan to review before building.** It answers the ask:

> *Make a plan to create the pages that support this new applicability
> infrastructure.*

Structure deliberately mirrors [`../assets_ui_plan_kit/`](../assets_ui_plan_kit/)
— same document set, same mock-first philosophy — so the two read alike and build
in the same idiom.

## Companion kits

| Kit | Role |
| :--- | :--- |
| [`../modification_applicability_starter_kit/`](../modification_applicability_starter_kit/) | The **control + data** plan. Phase 1 (modifications) is already **built and verified**; Phase 2 (templates) is planned. This UI kit is the screens for it. |
| [`../assets_ui_plan_kit/`](../assets_ui_plan_kit/) | The assets **mock UI**, now built under `app/assets/presentation_layer/`. Every page below **extends a page that already exists there.** |

> **Read the matrix first.** Every mode-dependent UI state traces directly to
> [`../modification_applicability_starter_kit/modification_class_and_model_matrix_behaviors.md`](../modification_applicability_starter_kit/modification_class_and_model_matrix_behaviors.md).
> The four modes (`STRICT` / `CLASS_ONLY` / `MODEL_SET` / `UNRESTRICTED`) drive the
> centerpiece **Applicability Editor** — keep that doc open.

## What "mock" means here (binding constraints)

The assets app is currently a **mock** (`app/assets/presentation_layer/mock_data.py`
+ entrypoints that `render()` hard-coded namespaces; forms POST to a dummy success).
This kit stays in that idiom so the new screens can be *felt* and reviewed before any
wiring:

1. **No real backend in the prototype.** New entrypoints render hard-coded dicts
   shaped like the *real* applicability tables. No `Model.objects`, no calls into the
   control layer **yet**.
2. **But the control layer is real** (unlike the assets kit, which had none). So every
   mock page below names its **wire-point** — the exact `ModificationApplicabilityManager`
   / `ModificationApplicabilityValidator` / `ApplicabilityPolicy` call it will replace
   its mock with when the assets app goes real. See `route_map.md`'s "Wire-point" column.
3. **New model shape.** Mock data extends the existing `DEFINED_MODIFICATIONS` /
   `CONFIGURATION_TEMPLATES` dicts with `applicability_mode` + `applicable_classes` /
   `applicable_models`, mirroring the real fields added in Phase 1. See
   `mock_data_shapes.md`.
4. **Forms are visual only.** The editor flips visual state and POSTs to a dummy
   success; the matrix preview is computed by a pure mock helper, not the ORM.
5. **F5 rule holds.** Every page and every mode state renders on a plain full reload;
   HTMX only layers the live mode-switch and dual-listbox interactions on top.

## The core idea in one paragraph

A modification carries an **applicability mode** and two allow-lists (asset **classes**,
asset **models**). The UI's job is to make the *mode* the primary control and then show
each list in its mode-correct role — **binding gate**, **system-derived (read-only)**, or
**non-binding suggestion**. The same editor authors a template's applicability in Phase 2.
Downstream, the asset apply-modification screen turns the runtime gate into UX: an
incompatible modification (the *engine-mod-on-a-laptop* case) is shown disabled with the
policy's own reason, instead of failing on submit.

## Key concept → UI mapping

| Concept (from the matrix) | UI expression |
| :--- | :--- |
| `applicability_mode` | A 4-way **segmented selector** at the top of the editor; a **mode tag** on lists/cards |
| Binding list | Editable dual-listbox panel, "Required" styling |
| Suggestion list (`CLASS_ONLY` models, `UNRESTRICTED` both) | Same panel, muted, labelled "Search hints — not enforced" |
| Derived class set (`MODEL_SET`) | **Read-only** chips, "Auto-derived from models" |
| Dead-model guard (`STRICT`) | Inline rejection when adding a model whose class isn't allowed |
| `ApplicabilityPolicy.is_allowed` | The live **"Applies to" preview** + the gated picker's enabled/disabled rows |
| `explain(...)` denial reason | The disabled row's tooltip / helptext on the apply screen |

## Documents in this kit

| Doc | Purpose |
| :--- | :--- |
| [initial_prompt.md](initial_prompt.md) | Verbatim request + interpretations + binding decisions |
| [page_inventory.md](page_inventory.md) | Every page/fragment, classified (Nav / User View / Work Portal) + goal |
| [route_map.md](route_map.md) | **Headline** — new/extended route ↔ existing mock page ↔ real control wire-point ↔ phase |
| [navigation_flow.md](navigation_flow.md) | Where applicability surfaces, the click-flows, and the **4-mode Applicability Editor anatomy** (centerpiece) |
| [mock_data_shapes.md](mock_data_shapes.md) | Extended modification/template fixture dicts + the matrix mock helper |
| [search_pages.md](search_pages.md) | List filter/column additions + the gated modification picker |
| [build_plan.md](build_plan.md) | Phased build order, mirroring the control kit's two phases |

## Review checkpoint

**Nothing is built yet.** Review `route_map.md` + `navigation_flow.md` +
`page_inventory.md` first. Once the page set, the editor's four mode states, and the
gated-apply flow are approved, building proceeds per `build_plan.md`.
