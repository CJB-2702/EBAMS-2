---
type: "Technical Decision"
title: "Tech Debt: External Purchase Order Integration API — deferred"
description: "Deferred design for a genuine external (non-Django) HTTP surface letting outside systems report PurchaseOrder status. Kept for the actual problem it was solving, not just the shape it took."
tags: [technical-decisions, technical-decision, tech-debt, part-demand-purchasing, integration-api]
context_tier: 2
---

# Tech Debt: External Purchase Order Integration API — deferred

**Logged:** 2026-08-08
**Source:** `procurement_starter_kit/` — relocated from that kit's
`purchase_order_procurement_interface_concept.md` and questionnaire Section F ("Integration API").
The PO event/status-tracking shape this discussion produced was resolved and kept — see
`decisions.md` D16–D20 in the starter kit; only the genuinely external HTTP surface is deferred
here.

## The problem this was trying to solve

Every company's purchasing process is different — different vendor integrations, different
definitions of "backordered" or "partially received," different systems of record. This app
(`Part Demand + Purchasing`) can't hard-code one true purchasing process or vocabulary. The
question was whether it needs a **stable, narrow seam** letting something else — another internal
app, or a genuinely external system (a vendor's own portal, an ERP, an EDI feed) — report status
changes and trigger notifications for a `PurchaseOrder`, without this app needing to understand
that caller's internals.

Two callers were identified as materially different asks: **another Django app in this codebase**
(cheap — a direct control-layer manager call, no HTTP, no new auth) vs. **a genuinely external
system outside the Django process** (expensive — needs a real HTTP endpoint, a payload contract,
and its own service-account/API-credential auth scheme, since the row-level ownership-group
scoping used elsewhere isn't the right fit for a machine caller).

A related sub-problem: what should a status update from such a caller be allowed to say? A fixed
enum this app defines is safe to query against but presumes this app can anticipate every
purchasing process's vocabulary — which cuts against the stated motivation. Free text is maximally
flexible but means this app can't reason about PO state at all. A middle ground (this app's own
small fixed set of coarse states, plus an open-text detail field for the caller's own vocabulary)
was floated but not built.

A third sub-problem, separate from the inbound write path: does this app need to **emit** something
outward when a PO changes state (so a vendor integration, Slack, or email can react), or is
in-app viewing sufficient for now? These are different mechanisms — an outbound webhook/signal
dispatch vs. nothing beyond normal page rendering.

## What was resolved and kept (not deferred — see `decisions.md`)

- **D12** (internal seam): a future Inventory app (or any internal Django app) calls this app's
  control layer directly, e.g. `PartDemandManager.record_issuance(...)`. Consistent with the
  established one-directional dependency rule. No HTTP, no new auth.
- **D17–D19** (where the record lands): `PurchaseOrder` gets one `Event` row (the `Event` surface
  class carrying status/comments/attachments — not `ActivityThread`, which strips the event
  columns) for its whole lifetime. Status updates post as machine comments on that Event's
  existing comment stream — no separate `PurchaseOrderUpdate` journal table. The document library
  need rides the same Event's existing attachment support.
- **D20** (extension point): a Django signal fires on each status-update comment. No listener is
  implemented — this is a stable seam a future webhook/email plugin (or the deferred external API
  below) can hook into later without changing the write path.

## What's deferred here

The actual external HTTP surface: an endpoint, a payload contract, and a service-account/API-key
(or similar) auth scheme distinct from normal user login. Also deferred: the fixed-enum vs.
free-text vs. hybrid status-vocabulary decision (only matters once a real external caller's
vocabulary is known), and whether outbound webhook dispatch is actually needed by a real consumer
(vs. purely inbound recording, which is what's built).

## Why it was deferred

No concrete external (non-Django) caller exists today. Building an HTTP endpoint + auth scheme
ahead of a confirmed need was judged not worth it — a clean manager method (already built, D12) is
easy to wrap in a thin API view later; retrofitting a manager method out of an ad-hoc API endpoint
built too early is the harder direction.

## When to revisit

When a concrete external caller (vendor portal, ERP, EDI feed) is identified. At that point: decide
the status-vocabulary shape (fixed enum / free text / hybrid — the hybrid option above is the
strongest starting candidate, since `order_state` already gives this app a small fixed vocabulary
to key off of), design the payload contract, and pick an auth model. The D20 signal extension point
means the inbound write path itself won't need to change — only a new caller and payload schema on
top of it.
