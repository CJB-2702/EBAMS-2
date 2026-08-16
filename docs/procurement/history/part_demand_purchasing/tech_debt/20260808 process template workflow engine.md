---
type: "Technical Decision"
title: "Tech Debt: Process Template / Workflow Engine — deferred"
description: "Deferred design for a per-organization templated workflow engine driving PartDemand's three status dimensions. Kept for the actual problem it was solving, not just the shape it took."
tags: [technical-decisions, technical-decision, tech-debt, part-demand-purchasing, workflow-engine]
context_tier: 2
---

# Tech Debt: Process Template / Workflow Engine — deferred

**Logged:** 2026-08-08
**Source:** `procurement_starter_kit/` — relocated from that kit's
`process_template_workflow_engine_concept.md` (superseded by `decisions.md` D21–D23) and
`open_questions.md` #2, #3, #6 in the same kit.

## The problem this was trying to solve

Every organization's approval/purchasing/issuance process is different — different approval
chains, different definitions of "backordered," different numbers of steps between "someone asked
for a part" and "someone got it." `PartDemand` tracks three independent status dimensions
(`workflow_state` = approval progress, `order_state` = purchasing progress, `issue_state` =
physical hand-off progress), and the question was: does this app hard-code *one* process shape
for each dimension, or does it need to let each organization define its own stage graph — without
turning into a full workflow-builder product?

A second, related problem: today only `workflow_state` was assumed to vary by process (e.g. a
maintenance-approval flow differs from a dispatch-borrow flow). But once `order_state` was also
found to vary (purchasing steps differ by company, see the integration-API tech debt item below),
the same question applied there too — and it wasn't obvious whether `issue_state` (physical
handoff) varies independently of purchasing, or always in lockstep with it, or not at all.

A related, still-unresolved sub-question worth preserving if this is revisited: **does issuance
vary by organization the way purchasing does, or is "hand someone a part" essentially universal?**
If it varies, does it vary along the same axis as `order_state` (one template governs both) or
independently (a custom purchasing process with a universal issuance flow, or vice versa)? This
determines whether templates should stay scoped per-dimension or need a coarser/finer grouping.

## The design that was worked out (not built)

A `StageTemplate` table, keyed by `(template_name, dimension)`, holding a flat JSON shape per
stage: allowable outgoing transitions, required permissions, and — the interesting part — a
`required_dimension_states` cross-dimension gate (e.g. "`order_state` can't leave 'Not Ordered'
until `workflow_state` reaches 'Approved'"), expressed as **set membership, not a rank/threshold**,
specifically because the workflow graph branches (different templates don't share one linear
order) and loops (a rejection sends `workflow_state` back to an earlier stage).

Guard architecture was resolved to one generic runtime interpreter reading `StageTemplate` rows —
no per-workflow Python class, no plugin interface (explicitly rejected elsewhere in this codebase
as overkill) — the same three-step check regardless of dimension or template. A read-only mermaid
`stateDiagram-v2` view generated from the same data was designed as the review mechanism (never
author mermaid text by hand — the table is the source of truth). A future visual template-builder
application (drag-and-connect stage/transition editor) was sketched as the eventual authoring UI,
explicitly out of scope even within this already-deferred design.

Two implementation questions were still open when this was shelved: whether a demand snapshots its
assigned template at assignment time (safer for auditability) or holds a live FK (edits propagate
immediately) — leaning snapshot, not decided; and whether `allowable_state_transitions` JSON gets
save-time validation against existing stage names, or is left to human review — leaning human
review, not decided.

## Why it was deferred

Too complex for what this kit actually needs right now. Building a generalized per-organization
rules engine before a single real organization's variant process is in hand is speculative
generality — the concrete need (one working purchasing/approval/issuance flow) doesn't require it
yet.

## What was built instead

`decisions.md` D21–D23 in the starter kit: each of the three dimensions is one fixed, hardcoded
Django `TextChoices` enum, identical for every demand regardless of organization. Transitions are
unrestricted except three specific hardcoded gates (D9–D11), checked in a plain guard/manager
method, with a single glanceable Python dict per dimension in code — a readability aid, not the
seed of a generalized engine. Enum values themselves are pinned down in D24.

## When to revisit

If a real organization needs a genuinely different purchasing or issuance flow the fixed enums
can't express — not before. When revisited, start from the `required_dimension_states` mechanism
above (already resolved) rather than re-deriving it, and settle the issuance-variance question
first, since it decides whether templates need per-dimension or coarser scoping.
