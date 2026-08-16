---
okf_version: "0.1"
type: "Process Guide"
title: "Workflow — Create Demand"
description: "The one create path for a PartDemand: a simple form, the mandatory domain contract, the initializing journal rows, and the contract future consumer apps must honor."
tags: [process-guide, demand-and-purchasing, control-layer, workflow]
context_tier: 2
personas: [backend, business]
---

# Workflow — Create Demand

## `create_demand`

**Business goal.** A person records that they need material, so it can be reviewed and bought.
This is the only entry into the system for a need — every downstream axis starts from a row created
here.

**Actor.** Requester (D1). Later also a consumer app acting on a person's behalf.

**Frequency.** Daily, high (D44). It should be short.

---

### Why this is a form and not a wizard

Project convention says an entity with more than one reverse FK a user would populate in the same
sitting is a wizard. `PartDemand` has none: allocations are the Buyer's job, journal rows are
written by the system, and issuance belongs to a different app entirely. A Requester supplies a
part, a quantity, and a date. One card, one submit.

---

### Steps

1. **Adapt the payload.** `PartDemandCreateAdaptor` maps the form to a typed input struct:
   `part_id`, `quantity_requested`, `priority`, `needed_by`, `notes`,
   `serial_number_tracking_required`, `source_module`, `requested_by_id`, `domain_id`.

2. **Resolve the domain — never ask for it.** Exactly one domain, mandatory (D5). It is derived
   from the requester's own domain assignment, not chosen in a dropdown. If a requester holds more
   than one domain, that is the only case where the form asks.

3. **Determine the opening `demand_state`.** `Required` when a human is filling in the form —
   they are asking for something now. `Projected` only when a caller explicitly says so, which in
   this build means a consumer app forecasting future work. There is no UI path to `Projected`.

4. **Create the row.** `PartDemandFactory.create(...)`, keyword-only, `commit=False`. Sets the
   four axes to their defaults: the resolved `demand_state`, `purchasing_state = null`,
   `shipment_state = Request Not Sent`, `issuance_state = Not Issued`.

5. **Write the initializing journal rows.** `PartDemandStateManager` writes one
   `PartDemandUpdate` per axis with `previous_stage` blank (R2 — "the generic part demand should
   generate an initialized status request"). Four rows, not one. This is what makes the journal a
   complete account rather than a change log with an unexplained starting point.

6. **Commit.** One transaction. If any step fails, no demand exists.

---

### Classes touched

| Class | Role here |
| :--- | :--- |
| `PartDemandCreateAdaptor` | Form payload → typed input |
| `PartDemandFactory` | Creates the hub row |
| `PartDemandStateManager` | The four initializing journal rows |
| `PartDemandNarrator` | Text for those rows |

No guard runs at create. There is no illegal opening state to defend against, and D13's fail-open
principle means a guard that cannot decide would let it through anyway.

---

### The factory's contract with future consumer apps

`PartDemandFactory.create()` carries a docstring stating, explicitly, that **the caller owns
domain assignment** and **the caller owns its own link row**. Both are easy to forget when
Maintenance or Dispatching is added later, and both fail quietly rather than loudly:

- A demand created without the right domain is invisible to the people meant to fulfill it.
- A demand created without a consumer-side link row is an orphan — nothing can explain why it
  exists, because `source_module` is a display convenience and never a source of truth (D38).

The factory creates the hub row and nothing else. It does not create link rows, does not know what
a link row is, and never will (G3, D7).

---

### Deliberately not here

- **No PO creation.** A demand and a purchase order are peers (D14, R1). Creating one never
  creates the other.
- **No approval.** Approval is a separate act by a separate persona, and in practice usually
  arrives as a side effect of a Buyer's link instead (D42).
- **No duplicate detection.** Two people legitimately need the same part on the same day. Merging
  demands is not a concept in this model.
