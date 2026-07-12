---
type: "Technical Decision"
title: "Tech Debt: Control-layer pattern alignment (capability + event)"
description: "app/assets/control_layer/capabilities/capability_manager.py (398 lines)."
tags: [technical-decisions, technical-decision, tech-debt]
context_tier: 2
---

# Tech Debt: Control-layer pattern alignment (capability + event)

**Logged:** 2026-06-29
**Source:** architecture-vocabulary kit review (`docs/Architecture/vocabulary/`) — naming/pattern pass over the control layers. Deferred, none blocking.

## 1. `CapabilityManager` spans all four capability layers — decomposition candidate

`app/assets/control_layer/capabilities/capability_manager.py` (398 lines). Its own
docstring: *"day-to-day CRUD across all four capability layers"* — catalog, class,
model, asset — plus two set-reconcile editors. The suffix vocabulary defines a
**Manager** as a sub-area of one Context; four layers in one Manager is broad.

There is a natural seam: **asset-layer** mutations are event-tracked (emit `Event` +
`AssetEvent` via `AssetEventNarrator`), while **class/model** mutations are
administrative and emit nothing.

**Direction (not now):** introduce a `CapabilityContext` entry point delegating to
thin per-layer collaborators (catalog / class / model / asset), or at minimum split
the event-emitting asset-layer concern from the administrative class/model CRUD. No
behavior change intended.

**Minor residue:** `CapabilityManager.define()` validates inline (raises `ValueError`
for required name/code + duplicate checks, ~L53–62) instead of delegating to the
existing `CapabilityAssignmentValidator`
(`app/assets/control_layer/guards/capability_assignment_guard.py`) that the
`add_to_*` paths already use. Move the catalog-definition checks into a definition
guard for symmetry. *(Correction to the review's first pass: assets does **not** lack
a guard layer — `app/assets/control_layer/guards/` has 9 guards; this is the only
inline-validation hold-out.)*

## 2. Event lifecycle has no `StateMachine` — reserved guard with an obvious home

The `StateMachine` guard suffix exists in the vocabulary but is unimplemented
project-wide (marked *reserved* in `docs/Architecture/vocabulary/crosswalk.md`).
`Event` is status-driven (`EventStatus`), yet transition logic currently lives split
across `EventHandler` (*"all state-changing operations"*,
`app/events/control_layer/handlers/event_handler.py`) and `ThreadPolicy` (*"inspects
thread flags, answers capability questions"*,
`app/events/control_layer/policies/thread_policy.py`).

**Direction (fine to defer):** when `Event` gains non-trivial guarded transitions
(open → complete → reopened/cancelled), extract them into
`app/events/control_layer/guards/event_state_machine.py` as the project's first
`StateMachine`. Until then, the handler + policy split is acceptable as-is.
