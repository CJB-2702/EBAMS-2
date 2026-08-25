# 01 — Issuing groups of demands, and the two new `PartDemand` columns

**Status:** decision pending
**Touches:** `app/procurement/models/demand/`, `app/inventory/`, `app/maintenance/`
**Schema change:** yes → full `python refresh_project.py`, not an incremental migration

---

## 1. The actual problem

Issuing one demand works. Issuing *the set of demands that belong to one job*
does not, because nothing in the inventory app can name that set.

Today the origin of a demand resolves only through the consumer app's own link
table — `maintenance.MaintenanceDemandLink` points inward at
`procurement.PartDemand`, and per **D7** there is never a pointer outward. That
rule is correct for authority: procurement must not depend on maintenance. But
it has a cost nobody priced in at the time: **the storekeeper's screen lives in
Inventory, and the grouping it needs to display lives in Maintenance.**

So the storekeeper who wants "give me everything for work order 412" forces one
of three bad outcomes:

- `inventory` imports `maintenance` (and later `dispatching`, and later
  whatever comes next) to walk the link tables — every consumer app becomes a
  dependency of the issuing screen;
- the user issues demands one at a time from inside the maintenance event
  screen, which means the storekeeper has to work inside an app that isn't
  theirs and has no stock context;
- or the grouping simply doesn't exist and the user reconstructs it by memory.

All three are what's happening now, in different corners.

## 2. What already exists (don't rebuild these)

- **`PartIssueSession`** (`app/inventory/models/issuance/part_issue_session.py`)
  — already the transaction header, already `DRAFT → COMMITTED / CANCELLED`.
  The "issue a group at once" verb is *already modelled*. What's missing is not
  the session; it's the **selector that fills it**.
- **`PartDemandIssuanceManager.record()`** — the inward seam. Takes a net
  quantity and a target stage as arguments, computes nothing. Group issuance
  loops this; it does not need a new seam.
- **`IssuanceState.ISSUED_WITHOUT_STOCK_ADJUSTMENT`** — the state added last
  pass. It works.
- **`PartDemand.source_module`** — and this is the important one. See §4.

## 3. The proposal: `source_activity` + `source_parent_identifier`

Add to `PartDemand`:

```python
# ── Origin and tracking flags (D38) ──────────────────────────────────────
source_module = models.CharField(...)          # EXISTING

# What kind of work produced this need — "maintenance_event",
# "dispatch_reservation", "manual_request". Denormalized display/grouping
# key only. NEVER a join key, NEVER authoritative. Origin detail still
# resolves through the consumer app's own link table (D7).
source_activity = models.CharField(max_length=40, blank=True, db_index=True)

# Which specific parent row. Deliberately a CharField, not an integer and
# not an FK — see the note below on why the type is the enforcement.
source_parent_identifier = models.CharField(max_length=64, blank=True, db_index=True)
```

The grouping key is the **triple** `(source_module, source_activity,
source_parent_identifier)`. Two columns alone are ambiguous — maintenance event
412 and dispatch reservation 412 would collide — but `source_module` is already
on the table, so the triple is free.

### Why `CharField` and not an integer FK

This is the whole safety mechanism, so it should be deliberate rather than
incidental. If `source_parent_identifier` is an integer, someone will
eventually write `.filter(source_parent_identifier=event.pk)` in a join, then
someone will add `select_related`, and within two passes it is a de-facto
foreign key with no referential integrity and no `on_delete` — the worst of
both designs. A string that reads `"412"` invites no such thing, survives a
consumer app that keys on a UUID or a work-order code rather than a PK, and
degrades honestly when the parent is deleted (it becomes a dangling label, not
a broken join).

Consider storing it pre-namespaced (`"maintenance_event:412"`) so even a
careless equality filter can't accidentally match across activities.

## 4. Is this an anti-pattern? — No, and the precedent is already in the file

The note said *"I may just give up on this and build in an anti-pattern."* That
framing is too hard on the idea. Read the docstring already sitting on
`DemandSourceModule`:

> *"A denormalized filter/display convenience only — never a source of truth
> for origin detail. That resolves through each consumer app's own link table."*

`source_module` is **exactly this design, already shipped, already documented,
already accepted.** The proposal doesn't introduce a new violation — it
finishes an existing one that stopped one level too shallow to be useful.
"Which app asked?" without "which job?" is a filter that can only ever narrow a
list to a few thousand rows.

The D7 rule that matters is *procurement must not depend on maintenance* — no
imports, no FK, no `on_delete` coupling, no code in procurement that knows what
a maintenance event is. A namespaced string column violates none of that. It is
the same category of thing as `source_module`, and it stays honest as long as
the docstring is written the same way and enforced in review.

**The line to hold:** these columns may be used for *filtering, grouping, and
display*. Anything that needs origin *detail* — the event's name, its asset,
its status — still goes through the link table, in the consumer app, and gets
handed to the presentation layer as a struct. If a struct in `inventory` ever
imports from `maintenance`, the line was crossed.

## 5. Alternatives considered

| Option | Verdict |
| :-- | :-- |
| **Walk the link tables from inventory** (status quo) | Rejected. Makes every consumer app a hard dependency of the issuing screen, and gets worse with each new consumer. This is the thing being escaped. |
| **Generic FK** (`contenttypes` + `object_id`) | Rejected. Django-native, but it re-creates the outward pointer D7 forbids, drags `contenttypes` into procurement's dependency set, and makes the "display only" discipline unenforceable — a `GenericForeignKey` is designed to be dereferenced. |
| **Origin resolver registry** — consumer apps register a callable with procurement; inventory asks procurement to describe a demand's origin | Architecturally the cleanest and genuinely tempting. Rejected for now on cost: it needs a registry, an app-ready hook, a struct contract, and per-app resolvers, all to serve a grouped list view. Worth revisiting if a *third* consumer app appears, or if origin display needs get rich. Note it in `decisions_pending/`. |
| **Two denormalized columns** (the proposal) | **Recommended.** Cheap, precedented, one query, no cross-app import. |

## 6. What it buys — the workflow that becomes possible

1. Storekeeper opens the demand pool, filters by activity
   (`maintenance_event`) — or scans a work-order number straight into the
   identifier filter.
2. The list groups by the triple, one collapsible block per parent job, with a
   per-group **"stage all"** action.
3. Staging pushes lines into the existing **active `PartIssueSession`** draft.
   Nothing new is modelled — the draft queue already exists.
4. Commit runs the existing orchestrator once, decrementing stock and calling
   `PartDemandIssuanceManager.record()` per line.
5. Groups that can't be stock-fulfilled get committed at
   `ISSUED_WITHOUT_STOCK_ADJUSTMENT` instead — the state added last pass, now
   actually reachable in bulk.

Inventory never imports maintenance at any step.

**Writer discipline:** the columns are set exactly once, by the factory that
creates the demand, from arguments the consumer app passes in. They are never
recomputed, never backfilled from a join, and never updated after creation —
if a demand is re-parented, that is a new demand. Enforce this the way the
four state axes are enforced: a comment on the field saying who is allowed to
write it.

## 7. Flagged while reading — three overlapping issuance states

Not part of this change, but it surfaced and shouldn't be lost.
`IssuanceState` now carries three values that all mean roughly "material moved
but the books disagree":

- `ISSUED_PENDING_RECONCILIATION` — "out on loan, expected back"
- `ISSUED_RECONCILIATION_REQUIRED` — "movement happened, inventory hasn't
  recorded it" (D77)
- `ISSUED_WITHOUT_STOCK_ADJUSTMENT` — "acquired outside the formal process"

The enum docstring already works visibly hard to distinguish the first two. The
third arrived later and its boundary against the second is thin: *"technician
got it somewhere else"* and *"the books are behind reality"* are the same row
in a reconciliation report. Before building the group-issue UI, decide whether
these are two states or three — a bulk-issue screen has to pick one as its
default terminal stage, and picking it while the distinction is fuzzy bakes the
fuzziness into the workflow.

## 8. Next actions

- [ ] Decide: two-column denormalization vs. resolver registry (recommend the columns)
- [ ] Resolve the three-overlapping-issuance-states question in §7 first — it changes the commit default
- [ ] Add the two fields with the "display/grouping only, set once at creation" docstring
- [ ] Set them in `PartDemandFactory` / `PartDemandCreateAdaptor`; make the consumer apps pass them
- [ ] `python refresh_project.py`
- [ ] Add grouped-by-source filtering to `open_demand_search.py`
- [ ] Build the group-stage UI against the existing `PartIssueSession` draft
- [ ] Write the decision up under `docs/procurement/decisions_pending/` or promote to a numbered decision
