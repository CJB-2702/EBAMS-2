---
okf_version: "0.1"
type: "Kit Document"
title: "Open Questions — Demand Graph Surfaces"
description: "Every unresolved question in this kit, with its owner and how it resolves. Nothing is dropped silently."
tags: [starter-kit, open-questions, procurement, graphs]
context_tier: 2
---

# Open Questions — Demand Graph Surfaces

Each row resolves to a decision, defers to tech debt, or is explicitly dropped — never silently.

---

## Blocking — must be answered inside the phase named

| # | Question | Blocks | Resolution path |
| :--- | :--- | :--- | :--- |
| OQ1 | Is the part-match rule hardened to a database constraint, or does it stay a validator rule with an updated docstring? | Phase 1 | D3. Decide in phase 1's control-layer plan after looking at migration cost against existing seed data. |
| OQ2 | Does setting `resolution_state` / `is_flagged` / `priority` need its own permission codename, or does it ride on an existing procurement permission? | Phase 3 | D22 left this open. Needs an admin-persona look at the existing group fixtures before phase 3 is built. |
| OQ3 | Does `GraphResolutionManager` write to the members' activity trail directly, or emit something the existing Narrators consume? | Phase 3 | D15 requires the write; the seam is a control-layer choice. |

---

## Non-blocking — resolve when convenient

| # | Question | Notes |
| :--- | :--- | :--- |
| OQ4 | Is `OVER_DELIVERED` correctly ranked above `UNDER_ALLOCATED` in the precedence chain? | Flagged in the imbalance study §4 as the ordering most likely to be wrong. Over-delivery is a *present* problem (material on the floor); under-allocation is a *future* one (stockout risk). Cheap to reverse — it is one ordering in one function. |
| OQ5 | Should the worklist's default sort be imbalance precedence, priority, or quantity gap? | Not decided. Affects phase 4 only, and is a one-line change. |
| OQ6 | Does the unresolved-count-by-domain rollup need its own query, or is it the list query with a `GROUP BY`? | Phase 4 implementation detail. |

---

## Deferred out of kit scope

| # | Question | Where it goes |
| :--- | :--- | :--- |
| OQ7 | Should `quantity_received` exist as a figure distinct from `quantity_accepted`? | **Explicitly deferred by the developer** ("update to accepted, will be resolved later"). This kit reads `quantity_accepted` as the arrival figure throughout (G4). Revisit when intake is built — it is the same question `intake_qty_recorded` is waiting on (D47). |
| OQ8 | Should `PartDemand` gain an event/activity thread so all three node types are uniform? | Considered and declined for this kit (D16). Arguably overdue independent of graphs; belongs to a demand-side pass. |
| OQ9 | Staleness / age-based imbalance | Declined for v1 with the consequence accepted (D11). Reopening means reversing questionnaire M5 and paying for last-activity columns. Should be reopened only when someone has felt the absence. |

---

## Logged as tech debt

Both need a file under `docs/procurement/tech_debt/` when the kit is executed.

| # | Item | Why it is debt rather than a bug |
| :--- | :--- | :--- |
| TD1 | `primary_domain` is a lossy single-FK summary of genuinely multi-domain membership | A graph's members can legitimately span domains; one FK cannot represent that. Accepted in questionnaire R1/P4 to keep the hot search path a single indexed column. Real multi-domain scoping is a future pass. |
| TD2 | A graph can be reachable by click-through but absent from its own search results | Follows directly from TD1 — search filters on `primary_domain` while the detail view admits on *any* member domain (D4/D6). Accepted on the reasoning that whoever linked the items holds both domains. **First thing to revisit if users report "I know that graph exists but I cannot find it."** |

---

## Resolved during this kit — recorded so the reasoning is not re-litigated

| Question | Outcome |
| :--- | :--- |
| Should imbalance compare demand against ordered or allocated quantities? | **Allocated** (D7). Ordered-based comparison flags every bulk restock. This was the kit's central correction. |
| Is there an over-ordered / over-allocated state? | **No** (D8). Already guarded by `AllocationCapExceeded`; a state that never fires misleads. |
| Enum or booleans for imbalance? | **One precedence-ordered enum** (D9). Decides questionnaire M3 by example. |
| Is the demand-less condition a flag or an enum value? | **An enum value**, `UNATTACHED`, at highest precedence (D9, formation study §5). |
| Read-only, or are there human-editable columns? | **Three human columns** (D13) — reversing questionnaire M6's initial position, on the worklist-noise consequence. |
| What survives a merge or split? | **The survival principle** (D14): configuration-derived state clears, human judgment propagates. |
| One merged activity feed or three? | **Three separate** (D16), because the underlying infrastructure is genuinely asymmetric. |
| The candidate umbrella name floated at the outset | **Withdrawn by the developer**, who asked that the vocabulary not be carried forward, so that if it is the right word it re-emerges on its own merits rather than by anchoring. The substantive decision it was attached to — graph status is a plain label, not a weighted score — survives unchanged in D81. Git history preserves the original wording. |
