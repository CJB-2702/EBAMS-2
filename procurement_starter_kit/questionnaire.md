---
okf_version: "0.1"
type: "Process Guide"
title: "Starter Kit Questionnaire — Part Demand + Purchasing"
description: "Pre-filled from initial_prompt.md and the preceding design-review conversation. Fill in the rest, set Status: COMPLETE, then hand back."
tags: [starter-kit-process, process-guide, questionnaire, okf]
context_tier: 2
personas: [backend, business]
---

# Starter Kit Questionnaire — Part Demand + Purchasing

**Status:** `DRAFT` — see `decisions.md` and `open_questions.md` for the 2026-08-08 review session
that resolved most remaining unknowns below (Section F, R3–R6, P1/P3/P4, and the workflow-engine
scope). Individual answers below are annotated with pointers rather than rewritten in place.

---

## A. Goals

### G1 — In one sentence, with no nouns from your schema: what does this let someone do that they cannot do today?

_(from initial prompt)_
**Answer:** Let someone request material they need, have that request reviewed and approved, and have it turned into a purchase — with the whole path from ask to order tracked and auditable — before any physical warehouse system exists to receive or hand anything out.

---

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

_(from initial prompt, revised in review session 2026-08-02)_
**Answer:** Three adjacent systems, mostly out of scope — with one deliberate, temporary carve-out:
- **Not a full warehouse/inventory system — but a small Part Issuance CRUD lives here as a stopgap.** Receiving, physical stocking, storeroom/bin management, and general inventory movement are still a separate future application ("Inventory"). However, this kit **will** include a minimal `PartIssuance` CRUD (record that N units of a part were handed to a requester against a demand) so the Issue dimension has something real to write to before Inventory exists. This is explicitly temporary scaffolding, not a claim that this app owns physical fulfillment — when the Inventory app is built, this CRUD is expected to be retired/migrated, not maintained in parallel. Keep it deliberately small (no bins, no locations, no stock levels).
- **Not Maintenance or Dispatching.** Those originate demands (they decide *why* material is needed) but are separate future apps. This app never knows why a demand exists, and must not import from either.
- **Not a vendor/contract-management system.** Scope is placing and tracking purchase orders against demands — not vendor performance, contract terms, or a supplier catalog beyond what's needed to record and track an order.

---

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

_(from initial prompt)_
**Answer:** `PartDemand` is the hub. The rest of the app — and any future consumer app (Maintenance, Dispatching, a future Inventory app) — is only ever allowed to know `PartDemand.id`. This mirrors the existing `Part.id` rule (parts kit D3). Consumer apps own their own link row pointing *at* `PartDemand`; `PartDemand` never holds a reverse pointer to them and never imports their internals.

---

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

**Answer:** _(revised in review session 2026-08-02)_ Resolved into two decisions:

1. **`parts` app: manufacturer only, no vendor concept.** A part is *defined* by who makes it (`PartManufacturer`), full stop — "vendor" has no place in the parts-definition app. This is flagged as a naming cleanup, not a schema change: `parts.SupplierItem` already correctly FKs to `PartManufacturer`, but its docstring and `supplier_vendor_revision_manager.py` use "vendor" language that should be scrubbed to "manufacturer"/"supplier item" terminology when that app is next touched. Not part of this kit's build — a small follow-up cleanup item for `parts`, logged so it isn't lost (candidate for `docs/parts/tech_debt/`).
2. **Purchasing app: new `Vendor` entity, separate from `PartManufacturer`.** A `PurchaseOrder` has a `Part` (which carries its `PartManufacturer` by definition) *and* a `Vendor` — who actually supplies/sells it, which can differ from who makes it (distributor, reseller). `Vendor` is a new, lightweight entity owned by this app (name, contact info, active flag — not a full contract-management system, per the original G2 scope line). Old Flask system's denormalized `vendor_name` string is rejected in favor of a real table, consistent with this codebase's conventions.

This in turn surfaced a third, larger open question — a generic integration API so external systems/apps can drive PO status updates and notifications into this app — tracked separately, see the new "F. Integration API" discussion thread (in progress, not yet resolved) and [decisions_pending/part_demand_purchasing_inventory_boundaries.md](part_demand_purchasing_inventory_boundaries.md).

---

## B. Personas

### P1 — Name each persona and the one sentence they would use to describe their job here. Which is the highest-volume user?

_(from initial prompt)_
**Answer:** Inferred from the conversation, not yet confirmed:
- **Requester** — "I need material for something I'm doing" (creates a demand). Likely the highest-volume persona, since a future Maintenance/Dispatching app will generate demands on their behalf frequently, but this app itself has no requester-facing volume yet without those apps existing.
- **Approver (Supply)** — "I decide whether this request is authorized."
- **Buyer / Procurement staff** — "I turn an approved request into an actual purchase order and track it to delivery."

Needs confirmation — including whether Approver and Buyer are ever the same person/role, and whether "Requester" is a real persona of *this* app at all before Maintenance/Dispatching exist (see M5-adjacent question below on where demands originate during this kit's phase).

**Resolved 2026-08-08 (D1, D2):** Requester is a real persona of this app now — it ships its own demand-creation UI. Approve and Buy are independent, separately-grantable permissions, usually co-held but not required.

---

### P2 — For each persona, what do they do 50 times a day versus once a month?

**Answer:**
_(unanswered)_

---

### P3 — Fill in the capability × role matrix, including the cells you are unsure of.

**Answer:** Draft only, from the conversation — needs review and the `?` cells resolved:

| Capability | Requester | Approver (Supply) | Buyer (Procurement) |
| :--- | :---: | :---: | :---: |
| Create a demand | C | — | — |
| View a demand | R | R | R |
| Approve / reject a demand | — | U | — |
| Create / edit a purchase order | — | U (approve-transition only) | CRU |
| Allocate a demand to a PO line | — | — | U |
| Cancel a demand | U | U | — (de-links instead, see D4) |
| View demand history / journal | R | R | R |

**Resolved 2026-08-08 (D2–D4):** all `?` cells settled. PO CRUD requires the Buy permission (Buyer column); an Approver may additionally transition a PO to Approved without needing Buy. Allocation is Buyer-only. Cancel is Requester/Approver only — see D10 for the gate blocking cancellation once a linked PO is Ordered; a Buyer de-links the demand from the PO instead of cancelling it.

_(review session 2026-08-02)_ Deliberate decision: **leave the process/workflow shape wide open for now.** The common path is simple — `requested → purchased` and `requested → issued → issued_to_requestor` (see M1) — but real-world variants (backorders, phantom/untracked consumption, rejections) exist and the intent at the time was to build a **generic logic framework** (process templates, workflows, stages) rather than hand-code every variant — **superseded 2026-08-08 (D21–D23): that framework is deferred to tech debt** (see `docs/procurement/tech_debt/20260808 process template workflow engine.md`); this kit instead hand-codes the three dimensions as fixed enums (D24) with a small hardcoded gate set (D9–D11). The capability matrix above should be revisited once process templates are designed, since role permissions may end up scoped per-workflow rather than globally per-persona.

---

### P4 — Is any of this data restricted to a subset of users? Is restriction the default or the exception, and roughly what percentage?

**Answer:** _(partially resolved in review session 2026-08-02)_ `PartDemand` uses this codebase's row-level ownership-group scoping (`is_domain_limited` + domain-access-mapping), and **domain assignment is automatic, not user-chosen**: whoever generates the demand (a consumer app, or a direct create in this app during this kit's phase) is responsible for auto-assigning the single domain that identifies who is actually meant to receive the part at the end of the process. This is a single-domain assignment, not multi-domain. Leave a note on the relevant factory/class (`PartDemandFactory` or equivalent) documenting this contract for future consumer-app authors, since it's easy to forget when a new demand-generating app is added later. What percentage of demands are domain-restricted vs. unrestricted is still unanswered.

**Resolved 2026-08-08 (D5):** not a percentage — every `PartDemand` requires exactly one domain assignment, mandatory in all cases.

---

## C. Business relationships

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

_(from initial prompt)_
**Answer:**
- `PartDemand` → `Part`: many-to-one (many demands can reference one part). Not expected to change.
- `PartDemand` → `PartDemandUpdate`: one-to-many (the append-only journal).
- `PartDemand` ↔ `PurchaseOrderLine`: **many-to-many**, explicitly — via `DemandSetLine` (renamed from `PartDemandPurchaseOrderLink`, see M1) with `quantity_allocated`. Chosen up front specifically because a demand can be split across multiple POs and a PO line can serve multiple demands (or none, for proactive restocking).
- `PurchaseOrder` (header) → `PurchaseOrderLine`: one-to-many. Standard PO shape, not deeply discussed — flagged for confirmation.
- Consumer app → `PartDemand` consumer apps will have their own relationship maps held within their sub applcaitions

---

### R2 — When a record is created, what else must come into existence automatically? For each: if it fails, does the original creation fail too?

**Answer:**
Part demand generators will generally handl this on their own
in this scenario the generic part demand should generate an initialized status request

---

### R3 — When a record is deleted or deactivated, what happens to everything pointing at it? Soft or hard?

**Answer:**
_(unanswered)_. Prior art only, not a decision: the old Flask system blocked hard deletion of a `PartDemand` if any PO links, part issues, or consumer links existed, by checking each related table's row count before allowing delete. Whether this kit uses soft-delete/deactivation instead, and what the check looks like without importing consumer-app internals (the old system's check itself violated the "stay ignorant of consumer apps" rule from R6), needs deciding.

**Resolved 2026-08-08 (D6, D7):** hard delete allowed only while a demand is untouched (zero related rows); otherwise soft-delete/deactivate. The guard checks only this app's own tables — consumer apps own their own join tables FKing to `PartDemand.id`, so `on_delete=PROTECT` on their side blocks deletion for free, no cross-app import needed.

---

### R4 — When several constraints apply at once, must all pass or any pass? Write the truth table.

**Answer:** _(mechanism resolved in review session 2026-08-02, full truth table still open)_ A general `required_dimension_states` mechanism was designed (a target stage can require specific stages in *other* dimensions to currently hold, checked at transition time — set-membership, not a rank/threshold, since the workflow graph branches and loops) but that whole engine is now deferred to tech debt, see
`docs/procurement/tech_debt/20260808 process template workflow engine.md`. The one established example (Order dimension must not leave `Not Ordered` until the Approval/`workflow_state` dimension reaches `Approved`) is an instance of this. The full enumeration — every gate that should exist across all three dimensions (e.g. can a demand be `Cancelled` after it's `Ordered`? does that require unwinding a PO allocation?) — is still not worked out as a truth table.

**Resolved 2026-08-08 (D9–D11, D21–D23):** the general `required_dimension_states` mechanism this section anticipated is deferred to tech debt along with the rest of the process-template engine (see `open_questions.md` #3). In its place, the complete gate set for this kit phase is three hardcoded checks: (1) `order_state` can't leave Not Ordered until `workflow_state` reaches Approved; (2) a demand can't be Cancelled while its PO's `order_state` is Ordered — the PO must be Cancelled first; (3) `issue_state` may advance independently of `order_state` (issuing from stock without a PO tied to this demand is allowed).

---

### R5 — At what moment is each rule enforced — authoring time, assignment time, or execution time? What happens when the check cannot be decided?

**Answer:**
_(unanswered)_ — not discussed in depth. The general shape (a guard enforces legal transitions at the moment of the transition, i.e. execution time) was implied but not worked through, and the "undecidable case" question wasn't addressed at all.

**Resolved 2026-08-08 (D13, D22–D23):** execution-time enforcement confirmed, via the hardcoded checks in D9–D11 rather than a runtime-interpreted template engine. When a check can't be determined, it fails open — the transition is allowed through and flagged/logged for human review rather than blocked.

---

### R6 — Which app owns this? Which apps must remain completely ignorant of it, and what are the permitted seams?

_(from initial prompt)_
**Answer:** This new app (working name: Part Demand + Purchasing) owns `PartDemand`, `PartDemandUpdate`, `PurchaseOrder`/`PurchaseOrderLine`, and `PartDemandPurchaseOrderLink`.

- **Must remain completely ignorant of this app's internals:** Maintenance, Dispatching, and any future Inventory app. Permitted seam: a plain FK from their own tables pointing at `PartDemand.id` (and, for a future Inventory app, at `PurchaseOrderLine.id`) — nothing else. No shared registry, no plugin interface (explicitly rejected as overkill — see initial prompt), no imports of this app's control-layer classes.
- **This app must remain completely ignorant of:** Maintenance and Dispatching internals, in both directions — unlike the old Flask system's `DemandOriginResolver`, which reached into `maintenance`/`dispatching` model internals with `try/except ImportError` guards. That pattern is explicitly called out as something to avoid, not replicate.
- **Open seam, not yet decided:** how a future Inventory app advances the Order and Issue dimensions on an existing demand (e.g. when goods are received or issued). Likely a direct call into this app's control layer (Inventory depends on this app, consistent with the one-directional dependency already established), but the exact mechanism — a manager method call vs. some other seam — was raised but not settled. Flagged for interrogation.

**Resolved 2026-08-08 (D12):** direct control-layer manager call (e.g. `PartDemandManager.record_issuance(...)`). The call itself is the truth — auto-transitions state, no separate confirmation step. A related pattern also settled this session: consumer apps expose small HTMX fragment endpoints (e.g. `/inventory/part-demand-status-card/<id>`) so this app's templates can embed their data without backend coupling (D8).

---

## D. Data model

### M1 — Glossary: list every domain noun. Mark any word that already means something else in this system, in Django, or in the business.

_(from initial prompt, revised in review session 2026-08-02)_

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| Part Demand | The hub record — a material need moving through approval and fulfillment | — |
| Demand Update | One append-only journal row recording a transition on any of the three dimensions | Generic English word "update" — consider a more specific name |
| Workflow (dimension) | Whether/how the demand is authorized — renamed from "Approval" (see M3) | — |
| Order (dimension) | Purchasing/procurement progress on the demand | Still called `order_state` (confirmed fixed per M3) — the collision with `PurchaseOrder` the entity is resolved not by renaming the dimension but by renaming the join entity below to `DemandSetLine`, removing "Order" from its name. |
| Issue (dimension) | Physical fulfillment/hand-off progress on the demand | Still called `issue_state` (confirmed fixed per M3). Its terminal "issued" status value is renamed `issued_to_requestor` for clarity — long, explicit column/value names are fine in this project. |
| Purchase Order (header) | A commercial order placed with a vendor | Same "Order" word as the dimension, accepted as-is |
| Purchase Order Line | One line item on a purchase order | — |
| Demand Set Line | **Renamed from "Part Demand Purchase Order Link."** The many-to-many allocation row between a demand and a PO line — read as "one line in this demand's fulfillment/procurement set." | Removes the "Order" collision from the old name |
| Requester | The persona who creates a demand | — |
| Approver / Supply | The persona who approves or rejects a demand | — |
| Buyer / Procurement | The persona who manages purchase orders | — |
| Vendor | Who a PO is actually placed with — distinct from `PartManufacturer` | New entity, this app owns it — see G4 |

**Answer:** Two renames confirmed in review session 2026-08-02: (1) `PartDemandPurchaseOrderLink` → **`DemandSetLine`** — resolves the M1-flagged "Order" collision by taking the word out of the join entity's name rather than renaming the `order_state` dimension itself (which M3 confirms stays fixed). (2) The issue-dimension's "issued" terminal status value → **`issued_to_requestor`**, both readable as a specific, unambiguous status label. Read back for confirmation: this interprets "change order to demand_set_line" as renaming the join table, not the `order_state` dimension column — flag if that's not what was meant.

---

### M2 — Where two concepts overlap, which is the concrete/primary one and which is the restricted view of it?

**Answer:** _(confirmed in review session 2026-08-02)_ Confirmed: the join row between a `PartDemand` and a `PurchaseOrderLine` (renamed `DemandSetLine`, see M1) is a **peer join row**, not a restricted view of `PurchaseOrderLine` — it carries its own meaningful attribute (`quantity_allocated`) that belongs to the pairing, not to either side alone. No overlapping-concept pair requiring a concrete/view split was found elsewhere in this kit.

---

### M3 — Is this variation a type label, a set of capability flags, or a distinct class? Can a caller construct an invalid combination?

_(from initial prompt, revised in review session 2026-08-02)_
**Answer:** The three dimensions are a small, fixed, closed set — not open-ended, not user-configurable — modeled as an enum value on each `PartDemandUpdate` row, not as three separate classes or a bag of boolean flags. **Naming revision:** `order_state` and `issue_state` are confirmed as the two fixed, always-present dimension columns. The former "Approval" dimension is renamed **`workflow_state`** — this is deliberate, not just a collision fix: per the P1/P3 discussion, "approval" was too narrow once process templates (maintenance approval, dispatch-borrow, dispatch-consume, etc. — a design later deferred to tech debt, see `docs/procurement/tech_debt/20260808 process template workflow engine.md`) entered the picture. `workflow_state` is the generic third dimension that a demand's assigned process drives; `order_state` and `issue_state` stay fixed regardless of which process template is assigned. The construction-safety question remains the crux of the design: a caller *can* construct an invalid combination if nothing stops it — preventing that is the job of a guard/state-machine, not caller discipline. Not yet decided: exact transition tables per dimension, and whether the guard is one class covering all three dimensions or one per dimension.

**Resolved 2026-08-08 (D21–D23):** the templated/per-workflow direction is deferred to tech debt. All three dimensions are fixed, hardcoded `TextChoices` enums, identical for every demand regardless of process. One guard covers all three, enforcing only the three hardcoded gates (D9–D11) plus D13's fail-open behavior — not a generalized rules engine. Exact enum values per dimension are still open, see `open_questions.md` #5.

---

### M4 — Is this attribute intrinsic to what the thing *is*, or to *where it is used*?

_(from initial prompt)_
**Answer:** Checked against the model discussed and found consistent: `quantity_allocated` lives on the join row (`PartDemandPurchaseOrderLink`) because it's specific to *that* demand-PO pairing, not intrinsic to the demand or the PO line alone. `priority` and `needed_by` live directly on `PartDemand` because they describe the need itself, not where it's referenced from.

---

### M5 — How do users version and identify this? Can you trust their naming convention? What exactly does "current" mean, and is it the same as "newest"?

**Answer:** _(resolved in review session 2026-08-02)_ Not applicable in the `PartRevision` sense. The open rejection-retry question is now decided: **no close/reopen concept — the full history of rows is enough.** A rejected demand loops its `workflow_state` (see M3) back within the *same* `PartDemand` row; there is no separate "reopen" action and no new `PartDemand` row created on retry. The append-only `PartDemandUpdate` journal is the record of that full lifecycle — "current" is simply the demand's live snapshot columns, "history" is every journal row, and there is no versioning concept beyond that.

---

### M6 — Which entities carry free-form human content — comments, documents, photos, notes? Assume the answer is "more than you think."

**Answer:** _(partially resolved in review session 2026-08-02)_ `PartDemand` has a `notes` field and `PartDemandUpdate` has an optional per-transition `notes` field. **New decision: `PurchaseOrder` gets its own `events.ActivityThread`-backed event trail** (same infrastructure `Part`/`SupplierItem` already use — see M6 note under "F. Integration API" below), tying into the integration API so external status updates/notifications land as real events, not silent column mutations. **Corrected 2026-08-08 (D17–D20):** `Event` (the surface class carrying status/comments/attachments), not `ActivityThread` (which strips the event columns) — one `Event` row per PO for its whole lifetime, status updates post as machine comments on it, no separate `PurchaseOrderUpdate` table, document library rides the same Event's attachment support, and a Django signal fires per status-update comment as an unbuilt future extension point. **Deliberate scope choice: no equivalent thread/comment infrastructure for `PartDemand` in this kit** — the two `notes` fields are considered sufficient for now, an explicit reversal of the "give it a thread" lean from the parts kit precedent (D5). Flag for revisit if real usage shows the `notes` fields aren't enough.

---

## F. Integration API — resolved 2026-08-08

Raised off the back of G4: purchasing processes vary a lot company to company, so this app needs
some seam letting another application — or, eventually, a real external system (vendor portal,
ERP) — push status updates and notifications for a purchase order into this app, without this app
needing to know anything about the caller.

**Resolved — see `decisions.md` D12, D17–D20.** The internal-caller seam (a direct
`PurchaseOrderManager`-style manager call) and the PO event/status-tracking shape (one `Event` row
per PO, status updates posted as machine comments, no separate journal table, a Django signal
firing on each status update as an unbuilt extension point) are settled and built. The genuinely
external HTTP surface — payload contract, status vocabulary, auth model — has no concrete caller
today and is deferred to tech debt:
`docs/procurement/tech_debt/20260808 external purchase order integration api.md`.

---

## E. Migration defaults

### X1 — What is today's behavior, and does the new default reproduce it exactly? What are you doing with the old code — clean cut or shims?

_(from initial prompt)_
**Answer:** Not applicable in the usual sense — this is net-new to this codebase; nothing in `ebams2` currently handles part demands or purchasing. The sibling Flask project (`/home/cb/REPOS/asset_management/app/data/part_demands/`, `app/business/part_demands/`, `app/data/inventory/purchasing/`) is **reference material for ideas only** — a different framework, not code to port or shim. No dual-behavior or backward-compatibility concern applies. The relevant question isn't "reproduce old behavior" but "which parts of the old design to keep vs. deliberately drop" — already captured in `part_demand_purchasing_inventory_boundaries.md` in this kit (What doesn't fit this project's conventions section).

---

## Sign-off

- [ ] Every question above is answered, or explicitly marked unknown.
- [ ] Pre-filled `_(from initial prompt)_` answers have been reviewed and the markers removed.
- [ ] **Status at the top of this file is set to `COMPLETE`.**

Unknowns carry forward into the kit's `open_questions.md`; confirmed answers carry forward into `decisions.md`.
