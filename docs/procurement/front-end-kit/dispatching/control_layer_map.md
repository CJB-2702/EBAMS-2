---
okf_version: "0.1"
type: "Reference"
title: "Dispatch UI — Control-Layer Map"
description: "Every UI action mapped to its exact control-layer call and signature, the guard that can refuse it, and how the refusal must surface."
tags: [front-end-kit, dispatching, control-layer]
context_tier: 2
personas: [frontend, backend]
---

# Dispatch UI — Control-Layer Map

**The control layer for dispatches is finished.** No entrypoint in this kit may write to a
`DispatchingDetail`, a requirement row, a crew row, an expense, or a demand link directly. Every
write goes through one of the calls below. If a call seems to be missing, it is more likely the page
is doing something the design does not sanction — stop and say so.

Signatures below are copied from the built code; they are keyword-only where the source is.

---

## 1. Entry object

```python
from app.dispatching.control_layer.dispatch_context import DispatchContext

ctx = DispatchContext(dispatch_id, request.user)   # loads DispatchDetailStruct
ctx.dispatch                                       # the DispatchingDetail
ctx.struct                                         # the aggregated read model
ctx.refresh()                                      # re-load after an external write
```

Sub-managers are lazy properties on the context: `ctx.requirements`, `ctx.demands`, `ctx.crew`,
`ctx.expenses`, `ctx.rejection`, `ctx.cancellation`, `ctx.supersession`.

Every verb below narrates onto the dispatch's own event thread in the same transaction as the
change (`DispatchNarrator`), which is what makes the detail page's Timeline card worth having.
**Do not add your own comment after calling one** — you will double-narrate.

## 2. Creation

| UI action | Call |
| :--- | :--- |
| Create blank | `DispatchFactory.create(domain_id=, requested_for_id=, desired_start=, desired_end=, asset_class_id=, requested_by_id=None, asset_subclass_text="", headcount=None, names_free_text="", requested_assets="", dispatch_scope="", estimated_meter_usage=None, activity_location="", title="", description="", previous_dispatch_id=None, created_from_revision_id=None, actor=)` |
| Create from template | `DispatchFromTemplateFactory.instantiate(template_id=, requested_for_id=, desired_start=, desired_end=, requested_by_id=None, title="", description="", activity_location=None, actor=)` |

`instantiate` copies the head revision's pre-fill fields, all four catalogue requirement types, and
raises the template's material requirements as **real part demands** — all in one transaction. It
refuses a retired lineage and one with no head revision; surface both as form errors.

`create` raises `ValueError` when `desired_start >= desired_end`.

Both land `REQUESTED` after Phase 0.

## 3. Lifecycle

| UI action | Call | Refuses when |
| :--- | :--- | :--- |
| Take under review | `ctx.take_under_review()` | Not `requested` |
| Request fixes | `ctx.request_fixes(reason=)` | Not `under_review`; blank reason |
| Resubmit | `ctx.resubmit()` | Not `fixes_requested` |
| Mark completed | `ctx.mark_completed()` | Not `planned` / `alternate_resolution` |
| Reject | `ctx.rejection.reject(reason=, category=, alternative_suggestion="", can_resubmit=True, resubmit_after=None, actor=)` | Not `under_review`; blank reason; bad category |
| Cancel | `ctx.cancellation.cancel(reason=, actor=)` | Terminal state; blank reason |
| Supersede | `ctx.supersession.supersede(overrides={...}, actor=) -> DispatchingDetail` | Never — it only creates |

All refusals arrive as `ValueError` carrying a human-readable message from
`DispatchTransitionStateMachine`. Catch it, `messages.error(request, str(exc))`, redirect back.
**Do not pre-empt the state machine with your own `if` chain** — render buttons from the transition
table ([status_vocabulary.md](status_vocabulary.md) §2) and let the guard be the authority.

`cancel()` returns `{"cancelled_reservation_ids": [...], "demand_results": [...]}`. Each demand
result is `{"part_demand_id": int, "cancelled": bool, "reason": str}` — a refusal from the demand
hub **stands**, and the UI reports it verbatim rather than retrying or hiding it
([2_dispatch.md](../../dispatching_starter_kit/2_dispatch.md) §13).

`supersede()` does **not** touch the old dispatch. Cancelling or completing it is a separate,
explicit act by the user; the page must say so and offer it.

## 4. Intent

```python
ctx.update_intent(title=..., desired_start=..., asset_class_id=..., ...)
```

Runs `IntentLockPolicy.check_editable(dispatch=..., fields=set(...))` first: in a locked state it
raises unless every posted field is in `ALWAYS_EDITABLE_FIELDS`
(`title`, `description`, `priority`, `activity_location`, `names_free_text`). Post only the fields
the form actually rendered, so a locked-state save of the five allowed fields succeeds.

## 5. Requirements — the four catalogue kinds

```python
ctx.requirements.add(kind=, target_id=, is_required=True, notes="", quantity=None,
                     minimum_level=None, configuration_template_id=None, actor=)
ctx.requirements.remove(kind=, requirement_id=, actor=)
ctx.requirements.set_required_flag(kind=, requirement_id=, is_required=, actor=)
```

`kind` is one of `"capability" | "skill" | "model" | "modification"`. `quantity` applies to skill and
model; `minimum_level` (1–5) to skill; `configuration_template_id` to model only — a configuration
is an attribute of a model row, never a fifth kind.

Every call is gated by `IntentLockPolicy`. Uniqueness is enforced by database constraints — a repeat
raises `IntegrityError`; catch it and say *"That requirement is already on this dispatch."*

## 6. Material — real demands, not a wish list

```python
ctx.demands.raise_demand(part_id=, quantity_requested=Decimal, notes="",
                         expected_cost=None, priority=None, actor=)
```

Creates a `procurement.PartDemand` in the shared hub **and** a `DispatchDemandLink`. It is issuable
the moment it exists and visible to store keepers who hold no dispatching permission at all.

There is no per-row remove on the manager. To cancel one demand, go through the hub:

```python
from app.procurement.control_layer.part_demand_context import PartDemandContext
PartDemandContext(link.part_demand_id).cancel(actor=request.user, notes=reason)
```

which raises `procurement.control_layer.errors.TransitionRefused` when the hub says no (partly
issued, stock reserved, open PO). **Report the refusal; never override it.**
`ctx.demands.cancel_all_unissued(actor=, reason=)` does the same in bulk and is what dispatch
cancellation uses.

## 7. Crew

```python
ctx.crew.add(user_id=, role=PersonnelRole.PASSENGER, notes="", actor=)
ctx.crew.remove(crew_id=, actor=)
```

`PersonnelRole`: `driver`, `passenger`, `operator`, `crew_chief`, `observer`, `other`. A duplicate
person raises `ValueError`. Crew belongs to the dispatch, never to a reservation — three people and
two vehicles belong to neither vehicle.

## 8. Expenses

```python
ctx.expenses.add(expense_type=, reason=, amount=Decimal, counterparty_vendor_id=None,
                 counterparty_name="", payee_id=None, external_reference="",
                 notes="", account_codes="", actor=)
ctx.expenses.commit(expense_id=, actor=)
ctx.expenses.complete(expense_id=, actor=)
ctx.expenses.cancel(expense_id=, reason=, actor=)
ctx.expenses.update_fields(expense_id=, actor=, **fields)
```

`expense_type` is `contract` or `reimbursement` — one record kind, distinguished by type. `reason` is
required ("why this was needed instead of our own assets"); a blank one raises. Cancellation is a
status, never a deletion: cancelled lines stay on the page.

Every transition re-runs `DispatchStateDeriver`, so adding the first live expense to a dispatch with
no reservations flips it to Alternate resolution on its own.

## 9. Reservations

Dispatching never creates a reservation from a dispatch page ([D7](decisions.md)). Two actions only:

| UI action | Mechanism |
| :--- | :--- |
| Book an asset for this dispatch | Link out to `dispatching_reservation_create` with URL parameters — [phase_5](build_plan/phase_5_reservation_handoff.md) |
| Attach an existing booking | `ReservationPromotionManager.promote(reservation_id=, dispatch_id=, actor=)` |

`promote` refuses a reservation already attached to another dispatch (`ValueError`), writes a
`ReservationUpdate` audit row, and narrates on **both** timelines.

## 10. Read models

```python
DispatchDetailStruct.load(dispatch_id=)   # header, 4 requirement lists, demand_links,
                                          # reservations, expenses, crew — fixed query count
    .live_reservations   .live_expenses   .to_dict()

DispatchCostStruct.load(dispatch_id=)     # money only
    .total_planned  .total_committed_or_complete  .total_by_type  .live_expenses
```

`DispatchContext` already holds a `DispatchDetailStruct` as `ctx.struct` — the detail page should
use that rather than loading a second one. `DispatchCostStruct` is a separate load; the detail page
needs both.

## 11. Timeline

```python
from app.events.presentation_layer.tools.generic_cards import build_activity_card
context["activity"] = build_activity_card(ctx.dispatch, request.user)
```

Renders through `events/fragments/comments_card.html`. Every narrator sentence written by the calls
above lands here, which is what makes the dispatch's history readable without a bespoke change log.
