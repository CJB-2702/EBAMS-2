---
okf_version: "0.1"
type: "Explanation"
title: "Part Price Observation — Mini Kit"
description: "Scope, decisions, and reading order for the part price observation system: append-only price history, the parts-creation session breadcrumb, the bulk paste grid, and PO-line price suggestion."
tags: [explanation, procurement, pricing, mini-kit, index]
context_tier: 1
personas: [backend, frontend]
---

# Part Price Observation — Mini Kit

**Status: designed, not built (2026-08-09).** This is a *mini* kit deliberately — it adds one table,
two columns, one control-layer cluster, and a small page set to an application that already exists.
It does not follow the full `harness/starter_kit_process/` shape (no questionnaire, no phase
decomposition, no separate `open_questions.md`), because the problem is narrow and the surrounding
system is already designed in [../procurement_starter_kit/](../procurement_starter_kit/).

Decisions are numbered **D79–D92**, continuing from the procurement kit's D78. D87–D92 came out of a
business-architecture review on 2026-08-09 and partly supersede D84; read them before building
anything from the earlier ones.

---

## The problem

`PurchaseOrderLine.unit_cost` is a naked number. `12.50` on a line could be a vendor quote from this
morning, a price someone paid three years ago, or a guess someone typed to get past a required
field. Nothing in the schema distinguishes them, so nothing downstream can behave differently — and
that is why PO prices drift out of sync with reality without anyone noticing.

Two consequences follow:

1. **No autofill is possible** that isn't actively harmful. Filling a line from history makes a
   stale number look exactly as authoritative as a quoted one.
2. **A PO is sometimes just a shopping list.** Sometimes it genuinely is "tell this person to go buy
   these things," and pretending its totals are contractual is a fiction the system currently
   enforces.

The fix is not a better guess. It is making the number carry **where it came from and how old it
is**, and giving the system somewhere to accumulate real prices as a byproduct of work people
already do.

---

## Reading order

| Doc | What it covers |
| :--- | :--- |
| [models/part_price_observation.md](models/part_price_observation.md) | The new table, the two new `PurchaseOrderLine` columns, indexes, constraints |
| [parts_creation_smuggling.md](parts_creation_smuggling.md) | The session breadcrumb from part-create to pricing — the accepted anti-pattern, its containment rules, and the Django session mechanics that make it work |
| [bulk_observation_screen.md](bulk_observation_screen.md) | The paste grid: batch-level header, single cost column, three entry doors |
| [control_layer_architecture.md](control_layer_architecture.md) | Proposed classes, suffixes, layer placement, call graph — the backend persona's brief |
| [purchase_order_integration.md](purchase_order_integration.md) | How observations feed PO line creation, the suggestion ladder, the divergence prompt, and pricing basis |
| [page_set.md](page_set.md) | Recommended routes and templates |

---

## Decisions

### D79 — Price observations stay in `procurement`; the `parties/` extraction is deferred

`Vendor` currently lives in `app/procurement/models/purchasing/vendor.py`. By the "what is it
defined in terms of" test it does not belong there: `PurchaseOrder` cannot be described without
`Vendor`, but `Vendor` is fully described without ever mentioning a purchase order. Its own
docstring says so. It lives in procurement because procurement needed it first — build order, not
design.

The evidence that this is already leaking is in the repo:
[`app/detail_extensions/purchase_info/models.py`](../app/detail_extensions/purchase_info/models.py)
carries `vendor = CharField(200)` and `purchase_order_number = CharField(100)` — two procurement
concepts degraded to unjoinable free text, because assets could not reach a real `Vendor`.

The clean move is a low `app/parties/` app holding external commercial organizations (`Vendor`,
`PartManufacturer`, later Customer/Contractor), sitting below both `parts` and `procurement`.

**Deferred.** Appetite for a new app is not there right now, and the pricing work does not require
it. Everything in this kit stays inside `app/procurement/`. Log the extraction as procurement tech
debt with the `PurchaseInfo.vendor` CharField as the receipt: if a third application needs a vendor,
that is when the move stops being optional.

### D80 — The observation table is append-only; there is no "current price" column

`PartPriceObservation` rows are written and never updated. "The current price for this part from
this vendor" is **derived** — it is rung 1 of the resolution ladder, not a stored value.

The alternative was a mutable `PartVendorPrice` row keyed unique on `(part, vendor, domain)`. That
produces two sources of truth the moment any historical query exists, and it destroys the audit
trail that is the entire point: the value of this table is that it can say *"$12.50, invoiced,
Acme, 14 months ago"* rather than *"$12.50"*.

A materialized current-price row is a legitimate **later** optimization if the ladder's queries ever
show up in profiling. It is not a schema decision to make now.

### D81 — The parts → procurement session breadcrumb is an accepted `# DELIBERATE ANTI-PATTERN`

`app/parts` currently imports nothing from `app/procurement`; the dependency runs one way,
procurement → parts. The breadcrumb inverts it: part-creation entrypoints call a procurement module
to record what they just made.

Three alternatives were considered and rejected:

- **Move pricing into `parts`.** Moves the problem — `assets` would then depend on `parts` to name a
  vendor, for reasons unrelated to parts.
- **Extract `parties/`.** Correct (see D79), but out of appetite.
- **Cross-app HTTP handoff** — a button POSTing a JSON payload from the parts success page to a
  procurement seed endpoint. Architecturally cleanest (coupling reduces to a URL string in a
  template), but rejected in favour of the simpler session path.

The anti-pattern is accepted on the condition that it is **contained to three functions** in one
module. Nothing else in the codebase may touch the session key. See
[parts_creation_smuggling.md](parts_creation_smuggling.md).

### D82 — The breadcrumb appends, never replaces

There is exactly one session per user, shared across every browser tab (the `sessionid` cookie is
scoped to browser-profile + domain, not to tabs). A replace-semantics breadcrumb therefore has a
real multi-tab bug: tab B's batch silently destroys tab A's.

Appending dissolves it. There is no "current batch" for a second tab to be wrong about — just a
running list of parts created recently and not yet priced. The union is what the user wants to see
anyway.

Bounds: **100 parts maximum**, dedupe by `part_id` keeping the earliest timestamp, and a per-entry
TTL. The TTL *value* is deliberately left unset — `SESSION_COOKIE_AGE` is untouched at its Django
default and reducing it is scoped to a later app-hardening pass. The TTL is a named constant in the
module, filtered on read.

### D83 — Batch-level vendor, domain, and date; a single pasteable cost column

The realistic case is one quote, from one vendor, on one day, covering many parts. Putting vendor /
domain / `observed_at` in a header bar above the grid collapses the paste target to a single column
of numbers — which is exactly the shape of the data sitting in the user's spreadsheet.

Per-row override is explicitly **not** built in the first cut.

### D84 — Resolution is actor-scoped, and cross-vendor prices are never one click from a field

**Superseded in part by D91**, which replaces the three-rung ladder with a two-fact display rule.
What survives from D84, unchanged and load-bearing:

- Every read is filtered by the actor's visible domain set **before** anything is ordered. The
  domain filter is a **security boundary, not a ranking preference** — it lives in one
  `_visible_domain_ids(actor)` helper so it cannot be forgotten in one branch.
- Ordering within what remains is by recency.
- A price from a different vendor is never one click away from a cost field. Another vendor's price
  is not your price, and putting it behind a **Use this** button is the precise mechanism that
  produces the drift this kit exists to stop.

D91 keeps all three properties while removing the ranking logic. See it for the replacement rule.

### D85 — `unit_cost_source` and `unit_cost_asserted_at` on `PurchaseOrderLine`; divergence appends

A PO line records *why* its price is what it is. When a Buyer types a number that differs from the
shown suggestion, they are offered a prompt — and accepting it **appends a `MANUAL` observation**,
because per D80 there is no stored price to update. Same user-visible behaviour, no second source of
truth.

### D86 — The unpriced-parts filter is the correctness backstop, not a convenience

The session breadcrumb is a convenience path with three known failure modes: a cross-device gap
(parts created on desktop, grid opened on a laptop), a last-write-wins race between two concurrent
requests, and overflow past the 100-part cap.

All three degrade to the same harmless outcome — a part missing from the banner — **only because**
a standing "parts with no price observation" query exists and always finds it. That filter is
therefore load-bearing and ships in the same phase, not later.

### D87 — Domain is required on every observation; there is no global tier

Every price in this business was observed by someone, from a vendor, **for a place**. East Coast and
West Coast genuinely pay different prices for the same part, so the place is part of the fact, not
metadata about it.

A null "global" domain was considered and rejected. A price with no domain is a price nobody
negotiated — no owner, no story, nobody to ask about it — and because it matches at every rung for
every actor, the laziest entry silently outranks the carefully recorded one. That is the drift
mechanism this kit exists to stop, reintroduced through the back door.

**Visibility does the job global was pretending to do.** A buyer purchasing for shops A and B sees
both domains, so B's price reaches them with its origin intact — *"East Coast paid $12.50 to Acme,
March"* — rather than laundered into a placeless number. They get the same information plus one
extra fact: whose price it is.

This makes `vendor` and `domain` symmetrical: an observation always answers **who quoted it** and
**who it was for**.

Two consequences:

- A true company-wide contract rate is **not an observation**. It is a contract — with a term, a
  signer, and an expiry — and if it is ever needed it gets its own concept rather than being
  smuggled in as an observation with the "where" left blank. Until then, recording it once per
  domain costs a few rows and stays honest.
- **"Unpriced" becomes viewer-relative.** A part priced only for East Coast is unpriced for a
  West-only buyer. This is correct — a price you cannot see cannot help you — but the D86 queue and
  its badge count now differ per person, and someone will ask why.

### D88 — A confidence band on every asserted price; pricing basis is derived, not declared

The goal is not exactness. Humans are messy, and a system that demands precision it cannot get will
be fed fiction. Give people the tools to record the truth — including the truth that they are
guessing — and let the chips fall.

Every asserted price carries a coarse confidence band, chosen by the person asserting it:

| Band | Means |
| :--- | :--- |
| `QUOTED` | I have paper. This is the number |
| `P10` | Within about 10% |
| `P50` | Within about half |
| `P100` | Could be double |
| `UNKNOWN` | No idea — placeholder |

**Coarse buckets, not a free-entry percentage.** Nobody can calibrate "37%." Five choices, one
click, and the top one means "I have paper."

**Called confidence, not variance**, because it states how much the asserter trusts themselves — a
different thing from the receipt-versus-order variance check in
[purchase_order_integration.md](purchase_order_integration.md) §5.

It lives on **both** the observation and the PO line, independently: the observation records how
sure the observer was, the line records how sure the buyer is about *this* order. Copying a
confident 14-month-old price into today's line is legitimately less certain than the original was —
but only the buyer may make that downgrade. The system never downgrades silently; that is an
opinion a machine has no standing to hold.

**This replaces the `FIRM` / `ESTIMATED` header field** proposed in
[purchase_order_integration.md](purchase_order_integration.md) §3. Pricing basis stops being
something a human sets and forgets, and becomes something derived from the lines: an order whose
lines are all `QUOTED` is firm; one carrying a `P100` line is a shopping list and says so without
anyone declaring it. A total renders as *"$4,210 — could be $3,400 to $5,600"*, which an approver
can actually reason about.

It also dissolves the cold-start problem: the first PO for a new part records *"$40, no idea,"* a
legitimate and useful entry rather than a blocking gap.

### D89 — Three authority levels: use, record, establish

Two acts the kit previously treated as one:

| Act | Blast radius |
| :--- | :--- |
| Put a number on my own order line | This PO only. Wrong = one bad order |
| Assert what a part costs | Everyone who prices that part afterwards is shown it |

**Anyone can be wrong on their own order. Not everyone can be wrong on everyone else's.**

| Level | Can |
| :--- | :--- |
| **Use** | Accept what is shown; enter a price only where none exists |
| **Record** | Type any number on their own lines; log observations, which are **unverified** |
| **Establish** | Verify a price, making it what everyone else is shown |

**Unverified records are ranked, not blocked.** Gating recording outright would throw away the one
thing this kit exists to capture — a buyer holding a quote, noticing the system is wrong, at the
moment they know the truth. Instead the observation is written and permanent; it simply does not
outrank a verified one, and surfaces as *"a buyer recorded $14.20 last week — unverified."*

This buys three things for the cost of a rank rule: no knowledge is lost; the establishing actor
needs no approval inbox, because their queue is a filter over rows that already exist (unverified
assertions disagreeing with the established price); and append-only survives intact — **verifying
appends a verified row rather than editing an existing one**, so the disagreement stays on the
record.

**Establish authority is per-domain**, which follows from D87 — East Coast's price authority is not
West Coast's. The "only one person in the whole organization" case is just the configuration where
one person holds every domain, which this gives for free without hard-coding it as the only shape.

How these express in the role and permission system is an admin-engineering question, not a
business one. This kit defines them at the capability level; hand the mapping to `/admin-persona`.

### D90 — Soft lock on line price override

Some filers should not be able to adjust the price they are shown. A **hard** lock — they may set no
price at all — creates a dead end exactly where it hurts most: a part with no price on record blocks
them from filing, and the parts with no price are the new and unusual ones, which is when someone is
most likely to be in a hurry.

**Soft lock:** a `Use`-level actor may enter a price where none is suggested, but may not override
one that exists. No dead ends, and the control that was actually wanted is still there.

### D91 — The chip shows two facts and a doorway; ranking is display, not decision

Replaces the D84 ladder for display purposes:

> **$14.20** — recorded by J. Alvarez, 2 days ago
> **$12.50** — verified, East Coast, 12 Mar 2026 · `[ Use this ]`
> *4 prices on record for this part* →

- **Most recent recorded** and **most recent verified**, both scoped to the **PO's vendor**. Since
  you are buying from Acme, both numbers are Acme's — which is what keeps **Use this** always safe
  to click. With nothing from that vendor the chip says so and offers the doorway instead: *"No
  price from Acme — 4 prices from other vendors →"*.
- **Collapse when they agree.** If the most recent record *is* the verified one, show one line. A
  chip that always shows two numbers trains people to stop reading it.
- **The disagreement is the signal.** A gap between recorded and verified means someone in the field
  is seeing something the official price does not reflect. That is the drift, made visible at a
  glance instead of buried in a ranking function.

The system stops guessing which price is most relevant — it cannot know whether this order is like
the last one — and shows two dated facts a human resolves in half a second. Cross-vendor prices are
not ranked into oblivion; they are one deliberate click away, where they cannot land in a field by
accident.

Consequence: the part history page is **promoted to first-cut and load-bearing**. It is the pressure
valve absorbing the display complexity removed from the chip, and it ships with the chip.

### D92 — The price picker is a condensed fragment of the history resource, and returns a naked value

The doorway from D91 opens a **modal picker**, not a one-way link. A read-only detour would mean the
buyer reads a number, goes back, and retypes it — quietly reintroducing the naked price this kit
exists to abolish. So: pick a row, get the value, stay on the line.

This does not violate the project's *assignment never lives in a modal* rule. Nothing is being
attached to the record under edit; this is **read-only browsing plus a single-value capture**, which
is what modals are for.

Shape: same canonical URL as the full history page, served as an HTMX fragment variant. Client-side
searchable over vendor and domain, **capped at 50 rows, sorted most-recent-first with verified rows
badged** — recency is what a buyer scans for, and the badge carries authority without reordering.
Be honest about the cap (*"Showing 50 of 128 — open full history →"*); a truncated list that hides
its truncation teaches people the data is missing. It opens **unfiltered** — the chip already gave
them the vendor's number, so filtering back down to that vendor would make the button pointless.

**Picking a row returns a value, not a provenance chain.** This is deliberate. The chip's **Use
this** is vendor-scoped, so stamping *"last paid to Acme"* there is true; the picker is explicitly
cross-vendor and cross-domain, and a buyer may well take Grainger's number for an Acme order.
Stamping that would produce a line asserting a relationship that never existed, and **a false
provenance is worse than none**.

The line still records an owner, though — the buyer's own confidence band, today's date, and a
source reading as manual. Not a chain, just accountability, so the value is never
indistinguishable from a pre-existing row.

---

## Out of scope

- The `parties/` app extraction (D79) — tech debt.
- Currency handling beyond a single `currency` column. No FX, no conversion.
- Vendor price-list / catalog import with effective dates. Unless vendors send machine-readable
  price files, a hand-maintained catalog rots worse than PO lines do, because nothing forces anyone
  to touch it. Observations are self-maintaining — they exist only because something happened.
- Quantity-break pricing as a *rule*. `quantity` is recorded on the observation so a suggestion can
  say "at qty 500", but no tier resolution is built.
- Receipt/invoice reconciliation writing `INVOICED` observations. Designed for in
  [purchase_order_integration.md](purchase_order_integration.md) as a later phase; it depends on the
  package-receipt UI, which does not exist yet.
