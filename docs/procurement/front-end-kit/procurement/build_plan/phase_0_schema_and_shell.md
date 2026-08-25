---
okf_version: "0.1"
type: "Process Guide"
title: "Phase 0 — Schema, Permissions, and Application Shell"
description: "The hard gate before any UI work: nine schema changes from decisions D71-D78, the five-permission vocabulary, the pre-declared URL contract that lets waves 1-3 run in parallel, the topnav shelf, and the /procurement hub page."
tags: [front-end-kit, procurement, build-plan, phase-0, schema, permissions]
context_tier: 2
personas: [backend, admin, frontend]
---

# Phase 0 — Schema, Permissions, and Application Shell

**Runs first, alone. Phases 1–3 are blocked until this is merged and migrated.**

## Goal

Land every model change the front-end kit's plan depends on, define the permission vocabulary the
entrypoints will enforce, and stand up the shell — routes, navigation, hub page — so three sector
waves can be built in parallel without colliding.

## Definition of done

- All nine schema changes applied; `python dev_tools/delete_database_rebuild_models.py --seed` runs
  clean and `python manage.py seed_procurement_dev` still passes end to end.
- Decisions D71–D78 written into `procurement_starter_kit/decisions.md`, and the affected
  `models/` and `control/` documents in that kit updated to match.
- Five permissions exist and are grantable through the existing administration app.
- `app/procurement/urls.py` plus three wave modules registered, every route name resolving.
- Topnav dropdown shelf and main-index card render and link correctly.
- `/procurement` hub page renders with live stat counts.

---

## 1. Context to load

### Decisions and rules

| Document | Why |
| :--- | :--- |
| [../../../procurement_starter_kit/decisions.md](../../../procurement_starter_kit/decisions.md) | D57 (audit snapshots), D59 (package never free-floating — **this phase reverses it**), D61 (PO domain), D62 (permissions deferred — **this phase ends that**), D64 (decimal quantities), D65 (blank-not-null enum default), D68 (`Package.event`), D69 (`Package.has_splits`), D70 (association graph) |
| [../../../procurement_starter_kit/part_demand_system.md](../../../procurement_starter_kit/part_demand_system.md) | The four-axis model — §"issuance" before touching `IssuanceState` |
| [../../../procurement_starter_kit/purchase_ordering_system.md](../../../procurement_starter_kit/purchase_ordering_system.md) | PO lifecycle the new approval axis sits beside |
| [../../../harness/Authorization/rbac.md](../../../harness/Authorization/rbac.md) | How permissions and group templates work in this project |
| [../../../harness/Authorization/data_ownership.md](../../../harness/Authorization/data_ownership.md) | The Data Domain primitive — the fence every list filters on |
| [../../../harness/Architecture/patterns/model_patterns.md](../../../harness/Architecture/patterns/model_patterns.md) | Model rules — no business logic on models, audit columns |

### Existing code to read before editing

| Path | Why |
| :--- | :--- |
| [../../../app/procurement/models/](../../../app/procurement/models/) | All eight tables — `purchasing/enums.py`, `demand/enums.py`, `packages/enums.py` especially |
| [../../../app/procurement/models/packages/package.py](../../../app/procurement/models/packages/package.py) | Target of five of the nine changes |
| [../../../app/procurement/models/purchasing/purchase_order.py](../../../app/procurement/models/purchasing/purchase_order.py) | Target of the approval axis and `vendor_po_id` |
| [../../../app/procurement/control_layer/factories/package_factory.py](../../../app/procurement/control_layer/factories/package_factory.py) | Must stop requiring a PO; must take a domain |
| [../../../app/procurement/control_layer/narrators/purchase_order_narrator.py](../../../app/procurement/control_layer/narrators/purchase_order_narrator.py) | The narrator pattern to copy for the new `PackageNarrator` |
| [../../../app/procurement/presentation_layer/tools/po_events/](../../../app/procurement/presentation_layer/tools/po_events/) | The typed event emitter (D48) — the PO-placed signal hangs off this |
| [../../../app/parts/urls.py](../../../app/parts/urls.py), [../../../app/parts/presentation_layer/entrypoints/](../../../app/parts/presentation_layer/entrypoints/) | The reference implementation for an app's URL module and entrypoint style |
| [../../../app/public_app/templates/shared/topnav.html](../../../app/public_app/templates/shared/topnav.html) | The `portal-dropdown` shelf pattern to extend |
| [../../../app/public_app/templates/pub_home.html](../../../app/public_app/templates/pub_home.html) | Main index — sidebar link and card grid |
| [../../../app/events/templates/events/fragments/event_card.html](../../../app/events/templates/events/fragments/event_card.html) | The composite card this phase must make available for `Package` |

---

## 2. Two collisions found in the existing code — resolve these first

**Read this section before writing any migration.**

### 2.1 `IssuanceState.ISSUED_PENDING_RECONCILIATION` already exists and means something else

`app/procurement/models/demand/enums.py` already carries:

```python
ISSUED_PENDING_RECONCILIATION = ("issued_pending_reconciliation", "Issued Pending Reconciliation")
```

Its docstring defines it as **the active borrow/return state** — material is out on loan,
`issued_qty` reflects the full amount currently out, and a return nets it down with a negative
`PartIssue` row (D39).

The newly requested state — *"Part Issued — Inventory Reconciliation Required"* — means something
different: **a physical movement happened and the inventory system has not recorded it yet.** One is
"this is out and expected back," the other is "the books are behind reality."

**Resolution required.** Recommended: add a distinct value rather than overload the existing one,
because they answer different questions and a later Inventory kit will need to tell them apart:

```python
ISSUED_RECONCILIATION_REQUIRED = (
    "issued_reconciliation_required",
    "Part Issued — Inventory Reconciliation Required",
)
```

Confirm with the requester before choosing. If they intend to *replace* the existing value, say so
in D77 explicitly — silently repurposing an enum member with a live docstring is exactly the kind of
contradiction D63 had to clean up.

### 2.2 `po_number` and `package_number` are already unique CharFields

Both exist as `CharField(max_length=100, unique=True, db_index=True)` with no generator. The
requirement is a **system-generated** identifier plus a **separate buyer-entered string**. Keep the
existing columns as the generated identifier and add the generator — do not add a third column.

---

## 3. Schema changes (D71–D78)

Apply all nine, then full-reset the database per `.claude/CLAUDE.md` always-apply rule 1.

| # | Change | Model | Notes |
| :--- | :--- | :--- | :--- |
| 1 | `event` → `OneToOneField(events.Event, PROTECT, null=True)` | `Package` | Same shape as `PurchaseOrder.event`. D68. |
| 2 | `has_splits` → `BooleanField(default=False)` | `Package` | Maintained by `PackageLineSplitHandler`; set `True` only on an actual split (a full-quantity reassignment does not set it). D69. |
| 3 | `purchase_order` → **nullable** | `Package` | **Reverses D59.** A package can be received before its PO exists. |
| 4 | `domain` → `ForeignKey(administration.Domain)`, **required** | `Package` | Consequence of #3 — D68's "no column needed" reasoning falls with its premise. Copied from the PO when one is supplied; chosen by the receiver otherwise. |
| 5 | `tracking_number` → **renamed** `shipment_id`, `CharField(max_length=200, blank=True)`, indexed, **not unique** | `Package` | Stays a string deliberately: an integer column would eat leading zeros. |
| 6 | `approval_state` → new `CharField` axis beside `status` | `PurchaseOrder` | New enum, see §4. Blank-is-a-real-value per D65's precedent. |
| 7 | `vendor_po_id` → `CharField(max_length=200, blank=True)`, indexed, **not unique** | `PurchaseOrder` | Buyer-entered, externally sourced. Non-unique on purpose — vendors reuse and mistype numbers. |
| 8 | New `IssuanceState` value | `PartDemand` | See §2.1 — resolve the collision first. Backwards `Issued → Pending` transition becomes legal. |
| 9 | Auto-generation for `po_number` and `package_number` | both | Generated in the respective `Factory`, never on the model (no business logic on models). |

### Control-layer follow-through, not optional

- **`PackageFactory.create`** — `purchase_order_id` becomes optional; `domain` becomes a required
  argument; the Event row is created and its domain set from the PO when present, from the passed
  domain otherwise.
- **`PackageContext.attach_purchase_order(po_id, actor)`** (new) — attaching a PO later
  **auto-links every unlinked `PackageLine` to the PO line whose part matches.** No match, *or more
  than one matching active line*, leaves that line unlinked. Safe failure: never guess.
  Same rule `create_package` already applies for copy-on-create.
- **`PackageContext.delete(actor, reason)`** (new) — soft delete, and it must explicitly soft-delete
  every active line, because `PackageLine.package`'s `CASCADE` is a hard-delete cascade and does
  nothing for a soft delete.
- **`PackageNarrator`** (new) — mirrors `PurchaseOrderNarrator`. All package-lifecycle machine
  comments move from the PO's Event to the package's own (D68). A split landing on a **different**
  PO's line still additionally narrates on that other PO's Event.
- **`PurchaseOrderContext`** — new verbs `submit_for_approval`, `approve_order`, `deny_order`;
  `place()` gains a guard refusing to run unless `approval_state == APPROVED`.
- **`PurchaseOrderNarrator`** — when the approving actor is the PO's own creator, post a machine
  comment recording the self-approval. Permitted, but recorded.
- **`PartDemandIssuanceManager`** — allow the new state, and allow the backwards
  `Issued → Pending Reconciliation` transition.
- **PO placed signal** — emit through the existing typed emitter in
  `presentation_layer/tools/po_events/`. Nothing listens yet; that is intended.

### `mixed_po_assignments` on a PO-less package

Stays `False`. There is no header PO to be mixed against.

---

## 4. The PO approval axis

A **separate axis from `status`**, for the same reason `PartDemand` has four: "has a manager blessed
this" and "where is this order in the world" are different questions.

```
Unsubmitted  →  Pending Approval  →  Approved
     ↓                 ↓
   Denied / Cancelled (reachable directly from either non-terminal state, at any time)
```

`Approved` is **not** revocable through this axis — an approved order is cancelled through `status`.

| Action | Verb | Permission | Effect |
| :--- | :--- | :--- | :--- |
| Submit for approval | `PurchaseOrderContext.submit_for_approval` | `buy` | `Unsubmitted → Pending Approval` |
| Approve | `PurchaseOrderContext.approve_order` | `purchase_approve` | `→ Approved` |
| Deny | `PurchaseOrderContext.deny_order` | `purchase_approve` | `→ Denied` |
| Place | `PurchaseOrderContext.place` | `buy` | `status: Draft → Placed`, **blocked unless `approval_state == Approved`** |

**Self-approval is legal.** One person may hold both `buy` and `purchase_approve` and approve their
own order — small organizations run this way. It is recorded, never blocked (see the narrator note
in §3).

**No cost thresholds in this build.** Submitting for approval is always available and never
automatic. Threshold-driven approval is per-organization policy, which belongs to the
process-template engine already deferred to
[../../../docs/part_demand_purchasing/tech_debt/](../../../docs/part_demand_purchasing/tech_debt/)
(note: the starter kit's `README.md` points at a `docs/procurement/tech_debt/` path that does not
exist — the real folder is `docs/part_demand_purchasing/`. Fix that reference while writing D71–D78).

**D2's clause is retired.** D2 previously allowed an Approver holding only `approve` to place a
purchase order. With a real purchasing-manager gate that is wrong: placing is the Buyer's act,
approval is the manager's. Record the retirement in D71.

---

## 5. Permission vocabulary

Five permissions, grantable independently through the existing administration app.

| Permission | Holder | Grants |
| :--- | :--- | :--- |
| `request` | Requester | Create and edit demands. **Viewing a demand does not require it** — anyone with domain access can read. |
| `demand_manage` | Floor manager | Transition `demand_state` and `issuance_state` on **any** demand in their domain, not only their own |
| `buy` | Buyer | PO create/edit, line editing, demand allocation and de-linking (D3), submit for approval, place |
| `purchase_approve` | Purchasing manager | Approve or deny a PO pre-purchase |
| `receive` | Receiving staff | Create packages, advance package status, inspect and accept lines |

**Retained rules:**
- **D3** — allocation is Buyer-only.
- **D4** — a Buyer never cancels a demand. Cancellation belongs to the requester or the demand
  manager. The Cancel button must **not render** for a `buy`-only holder, not merely be disabled.
- **D5** — every list and search queryset filters to the user's domain access. `OpenDemandSearch`
  already accepts `domain_ids`; nothing calls it yet.

**Cross-domain rule:** a record outside the user's domain renders as **exposed data in plain text**
on a page they already have access to, with **no link through** to its own detail page. Applies to
PO references on demand pages and package references anywhere.

---

## 6. URL contract — the thing that makes waves 1–3 parallel

Create `app/procurement/urls.py` as a parent including three wave-owned modules, and register it in
[../../../app/config/urls.py](../../../app/config/urls.py) as `path('procurement/', include('app.procurement.urls'))`.

Populate **all three modules now** with the complete route and name inventory, every route pointing
at a shared `NotBuiltYetView` placeholder that renders a simple "not built yet" page. Each wave then
edits only its own module.

### `urls_demands.py` — Phase 1

| Route | Name |
| :--- | :--- |
| `demands/` | `demand_index` |
| `demands/create/` | `demand_create` |
| `demands/<int:pk>/` | `demand_detail` |
| `demands/<int:pk>/edit/` | `demand_edit` |

### `urls_purchase_orders.py` — Phase 2

| Route | Name |
| :--- | :--- |
| `purchase-orders/` | `purchase_order_index` |
| `purchase-orders/create/` | `purchase_order_create` |
| `purchase-orders/<int:pk>/` | `purchase_order_detail` |
| `purchase-orders/<int:pk>/edit/` | `purchase_order_edit` |
| `purchase-orders/<int:pk>/basic-package-manager/` | `basic_package_manager` *(built in Phase 3, declared here because it is PO-scoped)* |

### `urls_packages.py` — Phase 3

| Route | Name |
| :--- | :--- |
| `packages/` | `package_index` |
| `packages/create/` | `package_create` |
| `packages/receive/` | `package_receive` *(the PO-less reactive entry point)* |
| `packages/<int:pk>/` | `package_detail` |
| `packages/<int:pk>/edit/` | `package_edit` |

### Hub and diagnostics — owned by this phase

| Route | Name | Phase |
| :--- | :--- | :--- |
| `` (hub) | `procurement_hub` | 0 |
| `graph-association-visualizer/` | `procurement_graph_visualizer` | declared here, built in Phase 4 |

**No route in this app takes a density and an `htmx-*` value in the same request.** One canonical
URL per resource, `format=` for density. See
[../../../harness/UX_UI/format_contract.md](../../../harness/UX_UI/format_contract.md).

---

## 7. Navigation and the hub

### Topnav shelf

Extend [../../../app/public_app/templates/shared/topnav.html](../../../app/public_app/templates/shared/topnav.html)
with a `portal-procurement` dropdown, following the existing `portal-parts` / `portal-assets`
structure exactly — `portal-dropdown-group` blocks, `portal-sublink` anchors, Material icons.

| Group | Links |
| :--- | :--- |
| Demands | Hub & Search (`demand_index`), New Demand (`demand_create`) |
| Purchasing | Purchase Orders (`purchase_order_index`), New Purchase Order (`purchase_order_create`) |
| Receiving | Packages (`package_index`), Receive a Shipment (`package_receive`) |

### Main index card

Add a Procurement card to the card grid in
[../../../app/public_app/templates/pub_home.html](../../../app/public_app/templates/pub_home.html),
plus the matching sidebar link, both pointing at `procurement_hub`. Match the existing Parts card's
markup.

### `/procurement` hub page

Index/portal hub shell per [../../../harness/UX_UI/page_structure.md](../../../harness/UX_UI/page_structure.md)
— centred hero, entry-card grid, stat bar at the bottom. Full spec in
[../shared_workflows.md](../shared_workflows.md) §5.

**Entry cards:** Create a demand · Review demands (filtered `demand_state=Required`) · Build a
purchase order · Track packages · Purchase orders · **Receive a shipment** (new — the PO-less path).

**Stat bar:** open demands · demands pending approval · **POs pending approval** (new) · draft POs ·
packages in transit · drift-flagged packages (`mixed_po_assignments`).

Every count is domain-scoped and computed in **one** query, not one per tile.

---

## 8. Task order

1. Resolve the two collisions in §2 with the requester.
2. Write D71–D78 into `procurement_starter_kit/decisions.md`; update that kit's
   `models/package.md`, `models/purchase_order.md`, `models/part_demand.md`, `control/index.md`,
   and `control/package_lifecycle.md` to match.
3. Apply the nine schema changes (§3) and the new/changed enums (§4, §2.1).
4. Control-layer follow-through (§3) — factory, contexts, narrator, managers, guards.
5. Permissions (§5) — declare them and make them grantable through the administration app.
6. Full DB reset + reseed; confirm `seed_procurement_dev` still passes.
7. URL contract (§6) — parent module, three wave modules, `NotBuiltYetView`, config registration.
8. Navigation (§7) — topnav shelf, index card, sidebar link.
9. Hub page (§7).

---

## 9. Out of scope

- Any sector page. Phases 1–3 own every list, form, detail, and portal.
- The graph visualizer page (Phase 4) — its route name is declared here, nothing more.
- Cost-threshold approval rules — deferred tech debt, see §4.
- Intake: storeroom, bin, location, put-away, stock levels. A separate later kit.
- The Inventory Issuance Portal's **write** path. This phase only adds the enum surface.
- Tests. Not built this pass, consistent with the backend build.
</content>
