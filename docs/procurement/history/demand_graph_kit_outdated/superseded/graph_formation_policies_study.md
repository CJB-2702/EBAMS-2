---
okf_version: "0.1"
type: "Study"
title: "Graph Formation Policies — Study"
description: "How a graph acquires its part and primary domain, what happens when purchasing runs ahead of demand, when a graph is deleted, and what survives a merge or a split."
tags: [starter-kit, study, procurement, graphs]
context_tier: 2
---

# Graph Formation Policies — Study

**Resolves questionnaire R3, P4's derivation sub-cases, and the merge/split problem M6 reopened.** Written
to a strong recommended position throughout, at the developer's instruction.

The through-line: a graph is **not a thing anyone creates**. It forms, merges, splits, and dies as a side
effect of writes to other entities, and none of that is visible to the user doing the writing. Every policy
below follows from taking that seriously.

---

## 1. The part

Settled in questionnaire M4: `GraphSummary.part` is a **non-nullable FK**, and a graph may never contain
members for more than one part.

This is safe today. All three member types — `PartDemand`, `PurchaseOrderLine`, `ShipmentLine` — already
carry their own `part` FK, so a graph has a part from the instant its first node exists. Node-init sets it;
merge inherits it; split copies it.

> **Recommendation 1.** `recalculate()` sets `part` from any member, and **asserts** that every member
> agrees. A disagreement is not a data condition to tolerate with a nullable column — it is a bug in the
> guard chain, and it should fail loudly at the point of writing rather than silently mislabel a graph and
> file it under the wrong part in every search from then on.

### The consequence to hold onto

`PurchaseOrderDemandLinkValidator` enforces part-matching as a **soft validator rule**, deliberately kept
out of the database so it could be relaxed later — for kits, substitutes, or vendor cross-references. That
door is now closed by M4, and the constraint has become load-bearing for a stored column rather than merely
for correctness of one allocation.

> **Recommendation 2.** Harden the part-match check to a database-level guarantee, or — if that is too
> invasive for this pass — record in the validator's own docstring that a `GraphSummary.part` column now
> depends on it, so the next person who considers relaxing it sees the cost. The current docstring
> advertises the rule as cheap to relax, and that is no longer true.

---

## 2. The primary domain

Settled in questionnaire P4: `primary_domain` is the scoping guard for **search**, derived as the most
common domain **by purchase-order-line count**.

The rule as stated does not cover the most common graph in the system. Every newly created `PartDemand` is a
single-member graph with **zero** PO lines, so "most common by PO line count" is undefined for what will be
the majority of rows.

> **Recommendation 3 — the fallback chain.** Evaluate in order, first rule that yields a domain wins:
>
> 1. Most common domain across member **PO lines** (via `PurchaseOrderLine → PurchaseOrder.domain`).
> 2. Most common domain across member **demands** (`PartDemand.domain`).
> 3. Most common domain across member **shipment lines** (via `ShipmentLine → Shipment.domain`).
> 4. *(unreachable — a graph with no members is deleted; see §3)*
>
> **Ties broken by lowest `domain_id`.** Deterministic and frankly arbitrary, matching the existing
> precedent in `GraphSummaryManager.merge`, where an equal-membership tie is broken by "the lower
> `graph_id` survives" for the same reason: something must be picked, and the choice must not vary between
> runs.

Determinism is not a nicety here. `recalculate()` fires constantly, and a `primary_domain` that flapped
between two equally-common domains would make graphs **appear and disappear from people's search results**
with no user-visible cause.

### The known gap, restated because it will surprise someone

A graph whose `primary_domain` is not yours, but which contains your member, is **reachable by clicking
through from your own entity yet absent from your search**. Accepted in P4 on the reasoning that whoever
linked the two items should hold both domains anyway. This is logged as tech debt, and it is the first thing
to revisit if users report "I know that graph exists but I cannot find it."

### Scoping rules, restated for implementers

| Surface | Rule |
| :--- | :--- |
| Search / list | `WHERE primary_domain IN <user's domains>` — one indexed column, which is the entire point |
| Detail view | Compute the domain set across all members; admit if the user holds **at least one** |

On the detail view, out-of-domain members are **displayed** as plain text with no link through. This is
knowingly more permissive than row-level scoping elsewhere in the app.

> **Recommendation 4.** Mark it in the code with `# DELIBERATE ANTI-PATTERN`, per the project's convention
> for intentional exceptions, and state the reasoning inline: a graph you can only half-see is not legible,
> and every member is already reachable through the entity that links to it. The developer has accepted this
> leakage explicitly; the comment exists so a future reviewer knows it was a decision rather than an
> oversight.

---

## 3. Death

> **Recommendation 5.** A `GraphSummary` with **zero** members is deleted, not left as an empty row.

Already implied by the merge path, and stated here so it is a rule with a home rather than emergent
behaviour. The reachable causes are: every member soft-deleted, or a merge absorbing the last of them.

Merged graphs also die — settled in questionnaire M5. The absorbed row is **hard-deleted**, with no
tombstone and no redirect. A bookmarked URL to an absorbed graph **404s**, and that is accepted.

> **Recommendation 6.** Since a 404 on a previously-valid graph URL is a *normal* outcome rather than an
> error condition, the detail view's 404 should not read as "this never existed." A graph id that no longer
> resolves has very likely been absorbed into another. The view cannot know which one — the row is gone —
> but the message can say so, which converts a confusing dead end into an explicable one. Cheap, and it
> costs nothing to specify now.

---

## 4. What survives a merge or a split

Reopened by questionnaire M6 giving graphs three human-editable columns. Before that reversal the question
did not exist, and it is the sharpest edge the write path introduces: merges and splits fire as a **side
effect of an allocation**, so a Buyer who marks a graph resolved has no way to know that tomorrow's
unrelated allocation will restructure it.

Four arbitrary cases would be a bad answer. One principle produces all four:

> **Recommendation 7 — the survival principle.**
>
> **Anything derived from a graph's *configuration* clears when the configuration changes. Anything
> expressing *human judgment about importance* propagates.**

`resolution_state` is a statement about a specific set of nodes: *"I looked at this and it is finished."*
When nodes join or leave, the thing that was looked at no longer exists, and the statement no longer has a
referent. Priority and flagging are about the underlying **work** — the part, the urgency, the fact that
somebody wants eyes on it — which restructuring does not invalidate.

| Event | `resolution_state` | `is_flagged` | `priority` |
| :--- | :--- | :--- | :--- |
| **Merge** (A absorbed into B) | Reset survivor to `OPEN` | `True` if **either** was flagged | The **more urgent** of the two |
| **Split** (A becomes A + new B) | Reset **both** to `OPEN` | **Copy** to both | **Copy** to both |

### Why "reset on merge" and not "keep the survivor's"

Keeping the survivor's value would mean a resolved graph silently absorbing an unresolved one and staying
resolved — the absorbed graph's problem vanishes from the worklist without anyone addressing it. That is a
correctness failure disguised as a convenience, and it is exactly the class of silent loss this whole
section exists to prevent.

The cost is real and worth stating: a Buyer who resolves a graph may find it `OPEN` again after an unrelated
allocation, with no explanation. **That is the correct behaviour** — the graph genuinely changed — but it
will feel arbitrary from the outside.

> **Recommendation 8.** When `recalculate()` resets a `resolution_state` because of a merge or split, write
> a line to the surviving members' existing activity trail saying so. The graph itself carries no activity
> thread (M5/M6), but its PO and shipment members do, and a Buyer who sees *"resolution cleared: this graph
> merged with another"* is being told the truth rather than left to conclude the system lost their input.

---

## 5. When purchasing runs ahead of demand

The developer flagged this explicitly as un-thought-through and asked that it not be improvised. Two
distinct situations, both real, both already permitted by the schema:

- **A PO raised early**, before anyone recorded a demand for the material. Ordinary in practice — a Buyer
  acting on a verbal request, a known seasonal need, or a price window.
- **A shipment received reactively**, with no PO on file. Explicitly enabled by D71/D73, which reversed
  D59's "never free-floating" rule for exactly this reason.

Both produce a graph with `demand_qty = 0`.

> **Recommendation 9.** Both resolve to the single `UNATTACHED` state defined in
> [`imbalance_and_resolution_study.md`](imbalance_and_resolution_study.md) §4 — **not** to two separate
> states, and **not** to a standalone boolean.

They are the same operational situation (*material is moving with nothing requesting it*) with the same
resolution (*attach a demand, or raise one*). Splitting them into `PO_WITHOUT_DEMAND` and
`SHIPMENT_WITHOUT_DEMAND` would give the user two rows to learn where the action is identical, and the
distinction is visible anyway from the node list on the detail page.

**Why this must take precedence over everything else** (and does, at position 1): a graph with
`demand_qty = 0` makes every other comparison degenerate. The moment anything is accepted against it,
`qty_accepted > demand_qty` is trivially true and it would report as `OVER_DELIVERED` — technically accurate
arithmetic, completely wrong story. It is not over-delivered; nobody asked for it in the first place.

### The transition out

When a demand is finally attached, `merge` fires, `recalculate()` runs, `demand_qty` becomes non-zero, and
the graph re-evaluates to whatever it genuinely is. **No special-case cleanup is needed** — the existing
machinery handles it, which is a good sign the state is modelled at the right level.

---

## 6. Open items this study does not close

| Item | Why it is left open |
| :--- | :--- |
| Hardening part-match to a DB constraint (§1) | Needs a look at migration cost against the existing seed data; belongs to phase 1's control-layer plan, not to a policy study. |
| Whether `primary_domain` should ever be recomputed *less* often than every `recalculate()` | Only matters at a table size nobody has hit. Premature. |
| Multi-domain graphs deserving real multi-domain scoping | Acknowledged as a lossy simplification in questionnaire R1 and logged as tech debt. A genuine future pass, not a gap in this one. |
