# Phase 4 — Data & Relational Plan: Parts UI

**No new tables.** Phase 4 is presentation-only. It reads and writes exclusively through the
control layer built in Phases 1–3:

| Surface | Reads via | Writes via |
| :--- | :--- | :--- |
| Search / lookup | `PartSearch` → `AliasResolver` → `PartStruct` | — |
| Part detail | `PartContext.struct()`, `.revisions()`, `.documents()`, `.supplier_items()` | — |
| Create / edit part | `PartStruct` | `PartFactory.create` |
| Revisions | `PartRevisionStruct` | `PartRevisionManager.append` / `.set_status` / `.attach_document` |
| Manufacturers | `PartManufacturerContext` | `PartManufacturerFactory.create` |
| Supplier items | `SupplierItemContext.struct()` | `SupplierItemFactory.create`, `SupplierVendorRevisionManager.record` |

The only new code touching persistence is the **adaptor** layer (HTTP payload → control-layer
input structs) described in [`control_layer_plan.md`](control_layer_plan.md) — and even that
writes nothing itself; it hands validated input to factories/managers.

See each prior phase's `data_relational_plan.md` for the tables these surfaces render.
