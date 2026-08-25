---
okf_version: "0.1"
type: "Reference"
title: "Dispatch Status Vocabulary"
description: "The seven workflow states after the Draft removal — meaning, legal transitions, who moves each one, tag rendering, banner copy, and the derived Planned/Alternate axis."
tags: [front-end-kit, dispatching, states]
context_tier: 2
personas: [frontend, backend]
---

# Dispatch Status Vocabulary

Post-[D1](decisions.md). Every page in this kit renders these; render them the same way everywhere.

---

## 1. The states

| State | Value | Meaning | Intent editable? | Who moves it |
| :--- | :--- | :--- | :--- | :--- |
| **Requested** | `requested` | Raised and waiting. In the dispatcher's working set from the moment it exists | **Yes** | Created here |
| **Under review** | `under_review` | A dispatcher has claimed it | **Yes** | `Dispatch — Plan` |
| **Fixes requested** | `fixes_requested` | Sent back with questions. Reason recorded on the timeline | **Yes** | `Dispatch — Plan` |
| **Planned** | `planned` | At least one live reservation. The normal resolved state | **No** | *Derived* — never chosen |
| **Alternate resolution** | `alternate_resolution` | Resolved with no live reservation but a live expense — contracted out or reimbursed | **No** | *Derived* — never chosen |
| **Rejected** | `rejected` | Formally refused with a reason. Terminal | **No** | `Dispatch — Reject` |
| **Completed** | `completed` | Work done, assets back, material reconciled. Terminal | **No** | `Dispatch — Complete` |
| **Cancelled** | `cancelled` | Abandoned from any non-terminal state. Terminal | **No** | Raiser (own) or `Dispatch — Complete` (any) |

`draft` and `submitted` no longer exist. Any string literal of either in the tree is a bug.

## 2. Legal transitions

This is the table Phase 0 writes into `DISPATCH_STATE_TRANSITIONS`
([`dispatch_state_guard.py`](../../app/dispatching/control_layer/guards/dispatch_state_guard.py)).

| From | May move to |
| :--- | :--- |
| `requested` | `under_review`, `planned`*, `alternate_resolution`*, `cancelled` |
| `under_review` | `fixes_requested`, `planned`, `alternate_resolution`, `rejected`, `cancelled` |
| `fixes_requested` | `requested`, `cancelled` |
| `planned` | `alternate_resolution`, `under_review`*, `completed`, `cancelled` |
| `alternate_resolution` | `planned`, `under_review`*, `completed`, `cancelled` |
| `rejected` | — terminal |
| `completed` | — terminal |
| `cancelled` | — terminal |

`*` reachable **only** through `DispatchStateDeriver`, never through a button. The two from
`requested` are new in this kit ([D2](decisions.md)); the two back to `under_review` already existed —
they are the fall-back when a resolved dispatch loses its last reservation with no expense behind it.

## 3. The derived axis — never a button

`Planned` and `Alternate resolution` are recomputed by
`DispatchStateDeriver.apply(dispatch_id=..., actor=...)` after every reservation or expense change,
as a pure function of live line items:

```
live reservation?           -> planned
no reservation, live expense -> alternate_resolution
neither                      -> under_review
```

It is already wired into `ReservationFactory.create` (when given a `dispatch_id`),
`ReservationContext`, and every `ExpenseManager` transition. **The UI must never offer these two as
actions**, and every Actions card carries one grey line saying why:

> Planned and Alternate Resolution are derived from live reservations and expenses — they are not
> set by hand.

Live reservation statuses: `tentative`, `confirmed`, `user_checked_out`, `checked_out`,
`user_returned`. Live expense statuses: `planned`, `committed`, `complete`. Both frozensets are
exported from `dispatch_state_guard.py`; import them, do not retype them.

## 4. Rendering — `_status_tag.html`

Phase 0 creates `app/dispatching/templates/dispatching/dispatches/_status_tag.html`, included with
`{% include "dispatching/dispatches/_status_tag.html" with status=dispatch.workflow_status %}`.
Every list row, hero, and card header uses it. Nothing hand-rolls a Bulma tag for a dispatch state.

| State | Tag classes | Icon (Material) |
| :--- | :--- | :--- |
| `requested` | `tag is-info is-light` | `outbox` |
| `under_review` | `tag is-link is-light` | `pending_actions` |
| `fixes_requested` | `tag is-warning is-light` | `error_outline` |
| `planned` | `tag is-success is-light` | `event_available` |
| `alternate_resolution` | `tag is-success is-light` + `has-text-weight-normal` | `alt_route` |
| `rejected` | `tag is-danger is-light` | `block` |
| `completed` | `tag is-dark is-light` | `task_alt` |
| `cancelled` | `tag is-light` | `cancel` |

Sharp corners are already global (Bulma radius variables are `0`); do not add rounding.

## 5. Banner copy

The state banner sits where `templates/draft_editor.html` puts its "Unsaved draft" warning, and on
the detail page directly under the hero. One banner, state-driven:

| State | Class | Copy |
| :--- | :--- | :--- |
| `requested` | `is-info is-light` | **Requested.** This dispatch is in the dispatcher's working set. You can still change what you asked for. |
| `under_review` | `is-link is-light` | **Under review.** A dispatcher has picked this up. Intent is still editable while they work. |
| `fixes_requested` | `is-warning is-light` | **Fixes requested.** A dispatcher sent this back — see the timeline for what they asked. Make the changes, then resubmit. |
| `planned` | `is-success is-light` | **Planned.** Assets are committed to this job. Intent is locked; only title, description, priority, activity location, and names remain editable. |
| `alternate_resolution` | `is-success is-light` | **Alternate resolution.** This need was met without our assets. Intent is locked. |
| `rejected` | `is-danger is-light` | **Rejected.** This is terminal — see the rejection card. To try again, raise a follow-up dispatch. |
| `completed` | `is-dark is-light` | **Completed.** Work done, assets returned, material reconciled. Read-only. |
| `cancelled` | `is-light` | **Cancelled.** Live reservations and unissued material demands were cancelled with it. Read-only. |

For the three locked states the banner also carries the **Raise a superseding dispatch** action —
that is the only legitimate way to change frozen intent
([2_dispatch.md](../../dispatching_starter_kit/2_dispatch.md) §10, R11).

## 6. The intent lock

`IntentLockPolicy`
([`intent_lock_guard.py`](../../app/dispatching/control_layer/guards/intent_lock_guard.py)) freezes
intent in `planned`, `alternate_resolution`, and `rejected`. Always editable regardless:

```
title · description · priority · activity_location · names_free_text
```

The UI must reflect this rather than discover it: in a locked state, render frozen inputs
`disabled` with a lock icon and the reason, keep the five above live, and never show the
requirement add-forms at all. A locked dispatch that lets a user fill in a form only to eat a
`ValueError` on POST is a worse experience than one that shows the lock up front.
