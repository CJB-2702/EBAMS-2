---
okf_version: "0.1"
type: "Reference"
title: "Purchase Ordering System — POs, Vendors, and Demand Linking"
description: "Authoritative reference for PurchaseOrder/PurchaseOrderLine/Vendor, the PurchaseOrderDemandLink allocation join, the rules for linking a PartDemand to a PurchaseOrder, and the exact mechanics of partial fulfillment. Read part_demand_system.md alongside this for the four-axis state model."
tags: [reference, part-demand-purchasing, purchase-order, data-model]
context_tier: 2
personas: [backend, business]
---

# Purchase Ordering System — POs, Vendors, and Demand Linking

This is the reference for the purchasing side of the app: `PurchaseOrder`, `PurchaseOrderLine`,
`Vendor`, and the `PurchaseOrderDemandLink` join that connects a `PartDemand` to what's being bought for it.
For the four-axis state model on `PartDemand` itself (`demand_state`/`purchasing_state`/
`shipment_state`/`issuance_state`), see [part_demand_system.md](part_demand_system.md) — this
document explains the mechanics that *drive* `purchasing_state` and `shipment_state`, not the
enums themselves.

All decisions referenced below (`D#`) are recorded in [decisions.md](decisions.md).

> **Revision note (2026-08-08, build-scoping session).** Three things in this document are
> superseded and are kept only as reasoning history:
>
> - **`Vendor` no longer exists** (D45). A PO's vendor is an FK to `parts.PartManufacturer`;
>   `vendor_contact` is a plain string on the `PurchaseOrder`. See
>   [models/purchase_order.md](models/purchase_order.md).
> - **`PurchaseOrderDemandLink.quantity_received` no longer exists** (D55), so every receiving
>   mechanic in §3 and §4 below — including the worked example's `sum(quantity_received)` column —
>   is replaced. Arrival is recorded physically on `PackageLine.quantity_accepted`, and per-demand
>   arrival is **derived**: exact when a PO line serves one demand, a **shared demand session**
>   total when it serves several. See [shared_demand_sessions.md](shared_demand_sessions.md) and
>   [models/package.md](models/package.md).
> - **`DemandSetLine` is renamed `PurchaseOrderDemandLink`** (D50), applied throughout below.
>
> The §2 linking rules, the §3 PO status lifecycle, and D28's cap-with-explicit-choice all still
> hold unchanged.

---

## 1. The entities

- **`Vendor`** — who a PO is actually placed with. A new, lightweight entity this app owns (name,
  contact info, active flag) — not a full contract-management system. Distinct from
  `parts.PartManufacturer`: a part is *defined* by who makes it; a PO is placed with whoever
  *sells* it, which can differ (distributor, reseller) (G4). `vendor_contact` stays a plain string
  for this kit — a vendor having multiple category-specific contacts is a real problem but is
  logged as parts-app tech debt, not solved here (D41).
- **`PurchaseOrder`** (header) — a commercial order placed with a `Vendor`. Carries its own
  lifecycle `status`, independent of any linked demand's state axes (D27, §2). In-house/self
  fabrication is modeled as an ordinary PO placed against an internal vendor — there's no separate
  "manufactured onsite" path (D34).
- **`PurchaseOrderLine`** — one line item on a `PurchaseOrder`. One-to-many from `PurchaseOrder`.
- **`PurchaseOrderDemandLink`** (renamed from `PartDemandPurchaseOrderLink`, M1) — the many-to-many
  allocation row between a `PartDemand` and a `PurchaseOrderLine`. Read as "one line in this
  demand's fulfillment/procurement set." A **peer join row**, not a restricted view of either side
  — it carries its own meaningful attributes (`quantity_allocated`, `quantity_received`) that
  belong to the *pairing*, not to either side alone (M2).

---

## 2. Linking a demand to a purchase order — the rules

- **Many-to-many, deliberately.** A demand can be split across multiple POs (e.g. one vendor is
  backordered, the rest is sourced elsewhere), and a single PO line can serve multiple demands (or
  none at all). `PartDemand` and `PurchaseOrder` are peers — `PurchaseOrder` is never modeled as
  nested under `PartDemand` (D14, R1).
- **A `PurchaseOrder` can exist with zero linked demands.** Proactive/bulk restocking — buying more
  because stock is low, not because anyone specifically asked — is in scope (D14).
- **Allocating is Buyer-only.** No other persona writes a `PurchaseOrderDemandLink` row (D3).
- **A demand must be `Approved` before any allocation can push its `purchasing_state` past
  `null`.** Gate 1 from `part_demand_system.md` §3 (D9) — allocation itself isn't blocked by
  `demand_state`, but the demand's `purchasing_state` cannot progress until approval lands. **In
  practice, a Buyer's link auto-clears this by default:** linking a demand to a PO line
  auto-promotes `demand_state → Approved` as a side effect unless the Buyer checks an explicit
  opt-out box first (D42) — real usage has Purchasing routinely acting before an Approver
  explicitly signs off, so the strict block would otherwise get in the way daily.
- **An allocation is capped at the demand's outstanding requested quantity — but the Buyer can
  choose to raise the request instead of being blocked (D28).** `quantity_requested - purchased_qty`
  is what's left to buy; a new `PurchaseOrderDemandLink.quantity_allocated` that would push `purchased_qty`
  above `quantity_requested` triggers an explicit choice rather than a flat rejection: increase
  `PartDemand.quantity_requested` to cover it (with a strong warning that this is only appropriate if
  the task that originated the demand genuinely needs that much), or leave the excess unallocated.
  This is enforced per-demand,
  not per-PO-line — a PO line is always free to carry quantity beyond what's allocated to any one
  demand, available to link to another demand later or to stand as genuinely proactive/bulk stock
  (extends the zero-linked-demand case above to partially-linked lines too).
- **De-linking is Buyer-only, and stands in for cancellation.** A Buyer removes a `PurchaseOrderDemandLink`
  allocation rather than cancelling the demand itself; cancelling the demand is a
  Requester/Approver action (D4), gated by the rule below.
- **Cancelling a demand with an in-flight PO requires cancelling the PO first.** Gate 2 from
  `part_demand_system.md` §3 (D10): a demand's `demand_state` cannot move to `Cancelled` while any
  linked PO's `purchasing_state` is `Approved`/`Purchased` and the PO itself is not cancelled.
  Every linked PO must reach its own `Cancelled` status first.

---

## 3. `PurchaseOrder.status` — the PO's own lifecycle (D27)

Separate from, but the thing that *drives*, each linked demand's `purchasing_state` and
`shipment_state` (D40):

```
Draft → Placed → Partially Received → Received
Draft → Cancelled
Placed → Cancelled
```

- **`Draft`** — created, not yet sent to the vendor. No demand's `purchasing_state` can leave
  `null` while its only linked PO is `Draft`.
- **`Placed`** — sent to the vendor. This is the PO-level counterpart to gate 1 in
  `part_demand_system.md` §3 — a demand's `purchasing_state` only reaches `Purchased` once its PO
  is actually `Placed`, not merely drafted. `shipment_state` starts advancing from here too
  (defaults to `Request Received by Vendor`, then may be manually advanced as vendor updates come
  in — see §4).
- **`Partially Received`** — reflects the sum of `quantity_received` across the PO's lines being
  greater than zero but not yet closed out (see §4 for how that rolls up to individual demands).
- **`Received`** — an explicit Buyer close-out action, not an automatic quantity match (D29) — sets
  linked demands' `shipment_state` to `Delivered to Local Receiving Location` (§4).
- **`Cancelled`** — terminal, reachable from `Draft` or `Placed`. Sets linked demands'
  `purchasing_state` to `Cancelled`.

Status changes post as machine comments on the PO's `Event` (one `Event` row per PO, created
alongside it — not one row per status change), which also carries the PO's document library via
its built-in attachment support (D17–D19). A Django signal fires on each status-update comment as
an unbuilt extension point for a future webhook/email plugin (D20).

---

## 4. Partial fulfillment — the exact mechanics

This is the part that needs to be explicit, because a demand can be split across multiple PO lines
*and* a PO line can be shared by multiple demands — fulfillment can't be tracked as a single "is it
done yet" flag anywhere.

### The two quantity columns that make it work

- **`PurchaseOrderDemandLink.quantity_allocated`** — how much of this specific PO line is claimed by this
  specific demand. Set at allocation time by the Buyer, capped by D28.
- **`PurchaseOrderDemandLink.quantity_received`** — how much of *that claim* has actually arrived from the
  vendor (D26). Recorded against the **allocation row**, not the PO line — deliberately, because
  when a PO line shared by three demands gets a partial delivery, the receiving process must be
  able to say which demand's claim that delivery satisfies, not just "some of the line arrived."
  `quantity_received` can never exceed `quantity_allocated` on the same row.

### How a receipt gets attributed

When goods arrive against a `PurchaseOrderLine`, the receiving process (manual entry in this kit's
temporary scaffolding — see G2's `PartIssuance`-style stopgap note — or a future Inventory app via
the direct manager-call seam, D12) records the received amount and attributes it down to the
specific `PurchaseOrderDemandLink` row(s) sharing that line. For a line linked to only one demand this is
trivial (the whole receipt goes to that one allocation). For a line shared by several demands, the
receiving actor chooses the attribution explicitly — this app does not guess a proportional split
automatically, since a real warehouse receipt might deliberately satisfy one waiting demand before
another (e.g. by priority or `needed_by`, see `PartDemand.priority`/`needed_by`, M4) rather than
spreading evenly. **Receiving stays human-only for this kit phase** — no automated/system-driven
receipt.

### How that rolls up to `PartDemand`

1. **`purchased_qty`** (on `PartDemand`) = sum of `quantity_allocated` across every active
   `PurchaseOrderDemandLink` for that demand (D25), capped at `quantity_requested` unless the Buyer explicitly
   raises the request (D28).
2. **`purchasing_state`** (D34) is driven by `PurchaseOrder.status` reaching `Placed`/`Cancelled` —
   see §3. It does not track receiving progress at all; that's `shipment_state`'s job.
3. **`shipment_state`**'s early stages are computed or manually advanced; its kit-owned terminal
   stage is a human decision (D29, D35, D40):
   - `Request Not Sent` — the only linked PO is still `Draft`.
   - `Request Received by Vendor` — default once a linked PO reaches `Placed`.
   - `Production in Progress` / `Vendor Prepared to Ship` / `Shipped` — manually advanced as vendor
     updates come in; no auto-computation for this middle stretch in this kit.
   - `Backordered` / `Lost` — manually set off `Shipped` if the vendor reports either.
   - `Delivered to Local Receiving Location` — the Buyer explicitly marks it done once receiving is
     effectively complete for this kit's purposes. **Not** `sum(quantity_received) >=
     purchased_qty` — a buyer can close out a demand that only ever received 6 of a purchased 10,
     because that's what actually happened and further deliveries aren't coming.
   - `In Stock` and beyond — out of scope for this kit; owned by the future Inventory build kit
     (§1 scope note in `part_demand_system.md`).
4. **`PurchaseOrder.status`** rolls up the same way at the PO's own level — `Partially Received`
   reflects the sum of `quantity_received` across *all* the PO's lines and allocations being
   greater than zero; `Received` is likewise an explicit Buyer close-out, not an automatic match.

**Why the shipment close-out isn't computed:** business processes are messy — short shipments,
backorders a buyer decides to write off, deliveries accepted as final even though the paperwork
says more was coming. `purchased_qty` and `quantity_received` stay informational inputs to the
Buyer's decision, never a gate blocking it. See `decisions.md` D29/D40 for the full reasoning.

### Worked example

A demand requests **5 gallons**. The Buyer needs to buy in a larger unit and orders **10 gallons**
— above the request — then only 4 gallons ever actually get issued to the requester.

| Step | What happens | `demand_state` | `quantity_requested` | `purchased_qty` | `sum(quantity_received)` | `purchasing_state` | `shipment_state` | `issued_qty` | `issuance_state` |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :--- | :---: | :--- |
| 1. Buyer tries to allocate 10 gal to a demand that only requested 5, still `Required` | System intercepts: raise the request, or allocate only 5 and leave 5 gal unallocated on the PO line (D28) | `Required` | 5 (or 10, if raised) | up to 5 (or 10) | 0 | `null` (PO still Draft) | `Request Not Sent` | 0 | `Not Issued` |
| 2. Buyer raises the request to 10 gal and allocates the full 10 — the link itself auto-promotes the demand | Auto-approve on link (D42) | `Approved` | 10 | 10 | 0 | `null` (PO still Draft) | `Request Not Sent` | 0 | `Not Issued` |
| 3. PO placed with vendor | — | `Approved` | 10 | 10 | 0 | `Purchased` | `Request Received by Vendor` | 0 | `Not Issued` |
| 4. Vendor delivers all 10 gal; Buyer closes it out | `quantity_received=10` on the allocation | `Approved` | 10 | 10 | 10 | `Purchased` | `Delivered to Local Receiving Location` (explicit Buyer action) | 0 | `Not Issued` |
| 5. Requester is issued 4 gal (that's all the job needs); issuer marks it done | `PartIssuance` row for 4 — auto-completes the demand (D43) | `Completed` | 10 | 10 | 10 | `Purchased` | `Delivered to Local Receiving Location` | 4 | `Issued` (explicit human action) |

Note `issuance_state` reaches `Issued` at `issued_qty = 4`, six short of `purchased_qty` — because
that transition is a human decision (D30), not a quantity comparison. `issued_qty` stays the honest
record of what actually went out the door; nothing about the state machine forces it to match
`purchased_qty` or the original `quantity_requested`. Also note `demand_state` reaches `Completed`
in step 5 purely because `purchasing_state` and `issuance_state` both cleared — `shipment_state`
sitting at `Delivered to Local Receiving Location` (rather than the further `In Stock`, which this
kit doesn't drive to) never blocks it (D43).

**If instead the requester needed to return unused material** — say 4 gal are issued but only 3
actually get consumed — the demand would sit in `issuance_state = Issued Pending Reconciliation`
with `issued_qty = 4` while the job is in progress, then a second, negative `PartIssuance`-style row
for 1 gal is recorded on return, netting `issued_qty` down to `3` and resolving `issuance_state` to
`Issued` (D36, D39). `issued_qty = 0` is valid if everything issued is eventually returned.

### If a PO is cancelled mid-flight

If a PO is cancelled after partially delivering (say 6 of an allocated 10 arrived, then the
remaining 4 gets cancelled instead of shipped), the allocation's outstanding (unreceived) portion is
released — `purchased_qty` drops to reflect only what's still validly on order or already received,
and the Buyer may re-allocate the now-unfulfilled remainder to a new PO line. `quantity_received`
already recorded is never reversed by a cancellation — units that physically arrived stay received
regardless of what happens to the PO administratively afterward. Whether the demand's
`shipment_state` is then closed out at `Delivered to Local Receiving Location` (accepting the 6 as
final) or left mid-chain pending a new PO for the remaining 4 is, per D29/D40, the Buyer's call —
not automatic either way. `purchasing_state` itself moves to `Cancelled` once the PO is cancelled.

---

## 5. What this app deliberately does not do

- No automatic proportional-split attribution when a shared PO line receives a partial delivery —
  the receiving actor chooses attribution explicitly (§4).
- No `Manufactured Onsite` purchasing outcome — in-house fabrication is a PO placed against an
  internal vendor, going through the regular `Approved → Purchased` path (D34).
- No automatic completion of `shipment_state → Delivered to Local Receiving Location` or
  `issuance_state → Issued` from a quantity match — both are explicit human close-out actions (D29,
  D30, D40). The quantity columns (`purchased_qty`, `issued_qty`, `quantity_received`) are there to
  inform that call, not replace it.
- No cap on `issued_qty` relative to `purchased_qty` in either direction — under- and over-issuing
  are both just recorded as what happened (D30).
- No dedicated return/reconciliation table or "was this returned" boolean — a return is a second,
  negative `PartIssuance`-style row against the same demand; `issued_qty` is always the net (D39).
- No design of `shipment_state`'s mechanics past `Delivered to Local Receiving Location`, or of the
  general package-intake/receiving workflow — owned by the future Inventory build kit (D35).
- No `PurchaseOrderUpdate` journal table separate from the PO's `Event` comment stream — status
  updates are machine comments, not a second structured table (D18).
- No category-aware vendor contact model — `Vendor.vendor_contact` stays a plain string; the
  multi-contact-per-category problem is logged as parts-app tech debt (D41), not solved here.
- No external (non-Django) integration surface for a vendor/ERP system to report receipts directly
  — deferred to tech debt, see
  `docs/procurement/tech_debt/20260808 external purchase order integration api.md`
  (D16).
