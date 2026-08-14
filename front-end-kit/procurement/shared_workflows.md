---
okf_version: "0.1"
type: "Process Guide"
title: "Shared Workflows — Front-End Plan"
description: "Cross-sector concerns for the procurement UI: the portal hub, the shared demand session display, permission enforcement (the one thing this build deferred), page-layout fraction conventions, and search components reused across sectors."
tags: [front-end-kit, procurement, shared, workflows]
context_tier: 2
personas: [frontend, business]
---

# Shared Workflows — Front-End Plan

Concerns that cut across [part_demand_workflows.md](part_demand_workflows.md),
[purchase_order_workflows.md](purchase_order_workflows.md), and
[package_workflows.md](package_workflows.md) rather than belonging to one of them. Read this file
once; the sector files link back into it instead of repeating it.

## Source documents

| Document | What it defines |
| :--- | :--- |
| [../../procurement_starter_kit/decisions.md](../../procurement_starter_kit/decisions.md) | D62 (permissions deferred) is the single most consequential fact for this whole front-end kit |
| [../../procurement_starter_kit/shared_demand_sessions.md](../../procurement_starter_kit/shared_demand_sessions.md) | The attribution rule behind §2 below |
| [../../harness/UX_UI/page_structure.md](../../harness/UX_UI/page_structure.md) | Page shell fractions — the source of the 3/4+1/4 vs. 2/3+1/3 distinction in §1 |
| [../../harness/UX_UI/search/list_management_patterns.md](../../harness/UX_UI/search/list_management_patterns.md) | The seven search-and-select patterns cited by name (§1–§7) across all three sector files |
| [../../harness/UX_UI/search/searchbars.md](../../harness/UX_UI/search/searchbars.md) | `<search-dropdown>` vs. plain HTMX list filter — the decision every FK-search row in the sector files applies |
| [../../procurement_starter_kit/control/index.md](../../procurement_starter_kit/control/index.md) | "Rules every workflow follows" — one transaction per workflow, domain verbs not CRUD verbs, guards fail open |

---

## 1. Layout fraction convention (read before the sector files' card tables)

Two different splits are both called "left/right" in this app, and the sector files use whichever
one actually applies per card — this section is where the distinction lives:

| Pattern | Split | Used for |
| :--- | :--- | :--- |
| **Work portal shell** (`page_structure.md`) | **3/4 main + 1/4 right rail** | The whole-page layout for every `<sector>/<id>` detail page — main details left, quick facts/status/activity right |
| **Left-heavy assignment card pair** (`list_management_patterns.md` §3) | **2/3 pool + 1/3 target** | A single assignment relationship *within* a page — e.g. the demand-allocation card on the PO wizard and PO detail pages |

When a sector file's card table says "Left, main column" or "Right, detail rail" for a whole page,
it means the 3/4+1/4 work-portal shell. When it says a card is itself a left-heavy pair (the
allocation cards in [purchase_order_workflows.md](purchase_order_workflows.md)), that pair is
2/3+1/3 *inside* whichever column it sits in. Don't conflate the two ratios when implementing.

---

## 2. Shared demand session display

**Used by:** the demand detail page's purchasing and shipment axis cards
([part_demand_workflows.md](part_demand_workflows.md#24-procurementdemandsid--demand-detail)), the
PO detail page's line attribution badges
([purchase_order_workflows.md](purchase_order_workflows.md#22-procurementpurchase-ordersid--po-detail)),
and the package detail page's per-line arrival figures
([package_workflows.md](package_workflows.md#22-package-detail--procurementpackagesid)).

**The rule this component must never violate** (`shared_demand_sessions.md` §2): a PO line with
exactly one active demand link yields a real per-demand arrival number; a line with two or more
yields **only** a session total and member list — never a computed or estimated per-demand split,
not even labeled as an estimate.

**Component states:**

| `attribution_mode` | What renders |
| :--- | :--- |
| `unlinked` | "Proactive stock — not claimed by any demand." No number attributed to a demand. |
| `attributable` | A single number: "`N` of `M` requested has arrived for this demand." |
| `shared_session` | A sentence, not a number: "This demand is in a shared session of `session_allocated` units across `member_count` demands, of which `session_arrived` have arrived." Optionally expand to list the other member demands. |

A demand can show **both** an attributable figure (from one line) and one or more shared-session
entries (from other lines) simultaneously — `shared_demand_sessions.md` §3 gives the exact sentence
shape: *"12 units arrived for you, plus you're in a shared session of 40 with 25 arrived."* Build
the component to concatenate these, not to pick one.

**Data source:** `PurchaseOrderFulfillmentStruct`. Never compute this in a template or view function
by dividing a total — the absence of a per-demand field on the `shared_session` branch is
deliberate (D60); a caller defaulting it to zero would report a lie.

---

## 3. Permission enforcement — the one gap every page must close

D62 states plainly: **the backend currently has zero permission checks.** Every action listed in
every sector file's "Actions that need to exist" table can, as of the built backend, be called by
anyone reaching the entrypoint. This front-end kit's entrypoints are where each of these becomes
real for the first time:

| Rule | Where it must be enforced |
| :--- | :--- |
| D2 — `approve` and `buy` are independently grantable permissions | Gate PO create/edit routes on `buy`; gate the approve/reject action on `approve`. An Approver without `buy` must still be able to `place_purchase_order` (D2 explicitly allows this) |
| D3 — allocation is Buyer-only | Gate `allocate_demand_to_po_line` and de-link on `buy`, not on being merely logged in |
| D4 — a Buyer never cancels a demand | The demand detail page's Cancel button must not render (not just be disabled) for a user holding only `buy` without `approve`/requester standing |
| D5 — mandatory single domain scope | Every list/search page's queryset must filter to the user's domain access — `OpenDemandSearch` already accepts `domain_ids`, per D62's own note that "the data fence has its seam ready — nothing calls it yet" |

**Do not treat this as optional polish.** Building these pages without wiring domain scoping and
the permission gates above reproduces exactly the state D62 flagged as unsafe.

---

## 4. Reusable search/read services

These control-layer reads are each used from more than one page — build them once, not per-sector:

| Class | Used from | Notes |
| :--- | :--- | :--- |
| `OpenDemandSearch` | PO wizard's per-line allocation card; PO detail's allocation editor | Must annotate outstanding quantity in the query itself, ordered by `priority` then `needed_by`, scoped by `domain_ids` |
| `PurchaseOrderFulfillmentStruct` | PO detail; package detail; demand detail's arrival summary | The single source for every "how much arrived" figure across all three sectors — see §2 |
| `PurchaseOrderLineSearch` | Package line-splitting wizard | Scoped to one vendor's open POs, filtered by part |
| `PartDemandStruct` | Demand list (row annotations); demand edit (form values + history table) | Same struct at two different levels of completeness — don't build a second read path for the list view |
| `PartDemandDetailStruct` (proposed) | Demand detail — header, four-axis glance row, linked-PO summary, all four axis history cards, and the full journal | One aggregated read for the whole detail page (part_demand_workflows.md §2.4) — extends `PartDemandStruct`'s family rather than a page issuing its own per-card queries |

---

## 5. Portal hub — `/procurement`

**Page type:** Index/portal hub (`page_structure.md`) — centred hero, primary CTA, role-based
entry cards in a grid, summary stats bar at the bottom.

**Entry cards** (role/feature grid, ~3 across):

| Card | Links to | Primary for |
| :--- | :--- | :--- |
| Create a demand | [part_demand_workflows.md](part_demand_workflows.md) create page | Requester |
| Review demands | Demand list, filtered to `demand_state=Required` | Approver |
| Build a purchase order | [purchase_order_workflows.md](purchase_order_workflows.md) wizard | Buyer |
| Track packages | [package_workflows.md](package_workflows.md) list | Receiving staff, Buyer |
| Purchase orders | PO list | Buyer |

**Summary stats bar:** open demands, demands pending approval, draft POs, packages in transit,
drift-flagged packages (`mixed_po_assignments`).

---

## 6. Cross-app read composition (forward note, not a build item)

`decisions.md` D8 records a pattern for showing another app's data on this app's pages without
backend coupling — small HTMX fragment endpoints (e.g. a future
`/inventory/part-demand-status-card/<id>`). **Nothing in `app/inventory` exists yet to render this
way** (see [gap_analysis.md](gap_analysis.md) gap 4), so no page in this kit should call out to
such a fragment today. When the later Inventory kit ships an issuance/intake UI, the demand
detail page's "Issuance history" card
([part_demand_workflows.md](part_demand_workflows.md#24-procurementdemandsid--demand-detail)) is
the first candidate to convert from its current read-only static render into a fragment include —
noted here so that page isn't rebuilt from scratch when that day comes.
