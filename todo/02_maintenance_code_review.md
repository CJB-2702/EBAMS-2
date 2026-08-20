# 02 — Maintenance application: functional code review

**Status:** not started
**Scope:** `app/maintenance/` — ~10,900 lines of Python, 31 routes, 52 templates, 10 test modules
**Goal:** find excessive paths, confirm the control layer roughly matches the legacy application's shape, confirm the real policy rules line up

---

## 1. Why this is worth doing before anything else lands on top

A lot was built here fast and none of it has been read back. The risk isn't
that something is broken — the tests suggest the happy paths work. The risk is
**shape drift**: that the same job is now doable through three routes, that
policy lives in two places that disagree, and that a rule the legacy app
enforced quietly was never carried across. None of that shows up as a failing
test. It shows up six months later as a bug that can't be reproduced.

## 2. What a first pass over the file listing already shows

These are structural observations from metrics only — file sizes, write-call
counts, layer mass. Each is a **lead to verify**, not a confirmed finding.

### 2.1 `work_views.py` is 1,074 lines — start here

It is nearly double the next-largest file in the app and 10% of the app's total
Python. An entrypoint module that size is almost always three modules that
never got separated. This is the single highest-value file to read first, and
the most likely home of the "excessive paths" the note is worried about.

### 2.2 The layer mass is inverted

```
presentation_layer/entrypoints/   ~3,800 lines
control_layer/                    ~1,800 lines
```

Entrypoints carry roughly **twice** the control layer. For an app whose stated
architecture is "entrypoints are thin, writes go through the control layer,"
that ratio is backwards and is the strongest single signal that logic leaked
upward. Compare against `procurement/`, which was built more deliberately and
should show the opposite ratio — if it does, that's the target shape.

### 2.3 Twelve direct write calls sit in entrypoints

`.save()` / `.objects.create()` / `.delete()` / `.update()` appear directly in:

| File | Count |
| :-- | :-- |
| `work_views.py` | 5 |
| `planning_views.py` | 5 |
| `create_assign_views.py` | 1 |
| `proto_views.py` | 1 |

`harness/Architecture/layer_rules.md` says writes go through the control layer,
never from the entrypoint. Some of these will be innocent (a single field flip
on an already-loaded object); some will be a business operation that quietly
lost its manager. **Audit all twelve individually** — the count matters less
than which ones carry a rule with them.

Supporting evidence that the control layer itself is sound: every write module
there (`action_factory`, `action_creation_manager`, `asset_limitation_manager`,
`maintenance_blocker_manager`, `part_demand_manager`, `maintenance_factory`,
`maintenance_orchestrator`, both contexts) uses `transaction.atomic`. The
discipline exists — the question is only what bypassed it.

### 2.4 There is no `Narrator` in this app

The project's suffix vocabulary includes `Narrator`, `procurement` has
`PartDemandNarrator`, and the **legacy app has
`app/business/maintenance/base/narrator.py`**. `app/maintenance/` has none.
Either the human-readable phrasing of maintenance state changes is inlined at
call sites (drift — the same event will get worded differently in two places),
or maintenance genuinely doesn't narrate anything, in which case its journal
entries and timeline text are worth checking for quality. Find out which.

### 2.5 Legacy control-layer shape, side by side

Legacy `app/business/maintenance/` → current `app/maintenance/control_layer/`:

| Legacy | Current | Note |
| :-- | :-- | :-- |
| `base/maintenance_context.py` | `maintenance_context.py` | ✅ present |
| `base/maintenance_assignment_manager.py` | `maintenance_assignment_manager.py` | ✅ present |
| `base/billable_hours_manager.py` | `billable_hours_manager.py` | ✅ present |
| `base/action_managment/` | `action_context / action_factory / action_creation_manager / action_tool_manager` | ✅ present, reshaped — check nothing dropped in the split |
| `base/capablities_and_blockers/` | `maintenance_blocker_manager.py`, `asset_limitation_manager.py` | ⚠️ **verify** — blockers carried over; did *capabilities* come with them, or is "capability requirement" now only a dispatching concept? Cross-check against [03](03_dispatching_reservation_first.md) |
| `base/narrator.py` | — | ❌ **missing**, see §2.4 |
| `base/structs/` | `domain_structs/` | ✅ present |
| `builders/` (4 builders + context) | `adapters/template_builder_session_adapter.py` | ⚠️ five legacy modules collapsed into one 407-line adapter — verify all four build paths survived |
| `factories/` (3) | `maintenance_factory / action_factory` | ⚠️ `maintenance_action_set_factory` has no obvious counterpart — where did action-set creation go? |
| `templates/`, `proto_templates/`, `planning/` | same names present | ✅ present |

The shape matches better than the note feared. The three ⚠️ rows are the real
questions.

## 3. Review plan — four passes, in this order

Do them in order; each pass narrows what the next has to read.

**Pass 1 — Route inventory vs. reality (half a day).**
Read `urls.py` (31 routes) against
`maintenance_starter_kit/legacy_ui/route_inventory.md`. Produce three lists:
routes that exist in both, routes invented for this build, and legacy routes
with no counterpart. *Excessive paths declare themselves here* — two routes
reaching the same page state, or a route that survives only because a template
still links to it. Cheapest pass, highest yield.

**Pass 2 — Split `work_views.py`.**
Read it whole, map every view to the verb it performs and the control-layer
call it should be making. Expect to find inline logic that belongs in a manager
and two or three near-duplicate views differing only in filter defaults. Don't
refactor during this pass — write the map, decide after.

**Pass 3 — The twelve direct writes.**
Each one: is a business rule attached to it? If yes it needs a control-layer
verb (add to the owning app's control layer, not inline). If no, note it as
sanctioned and move on. Produce a short table of verdicts so the decision isn't
re-litigated later.

**Pass 4 — Policy line-up.**
The one that actually needs care. For each policy the legacy app enforced —
completion guards, assignment rules, blocker rules, asset limitations,
billable-hours rules — find its current home and confirm it fires on *every*
path, not just the one the test covers. `maintenance_completion_guard.py` has
a test; the others' coverage is unclear. Legacy enforcement often lives inside
a route rather than a policy class, so grep the legacy routes too, not just its
business layer.

## 4. Existing test coverage — what's already guarded

```
test_action_status_verbs.py       test_part_demand_queue.py
test_event_create.py              test_technician_dashboard.py
test_event_edit_portal.py         test_technician_issue.py
test_maintenance_completion_guard.py
test_template_builder.py          test_template_detail.py
```

Well covered: action status verbs, the completion guard, the demand queue,
template building and detail, the technician surfaces.

Visibly **not** covered: `planning/` (`maintenance_planner`,
`maintenance_plan_context`), `asset_limitation_manager`,
`maintenance_blocker_manager`, `billable_hours_manager`,
`maintenance_assignment_manager`, `maintenance_orchestrator`. Every one of
those is a policy holder. Pass 4 should leave a test behind for each rule it
confirms.

## 5. Deliverable

A findings document under `docs/maintenance/` with, per finding: what it is,
severity, and whether it's fix-now or `tech_debt/`. Anything that turns out to
be a genuine failed approach rather than a slip goes in
`docs/maintenance/incidents/`.

Run this as the **code-architect persona** (review-only, no implementation) so
the pass doesn't turn into an unplanned refactor halfway through.

## 6. Side note — a harness doc that no longer describes the code

`harness/Architecture/patterns/endpoint_patterns.md` specifies **OOP endpoint
design**. In reality *no* application uses class-based entrypoints —
maintenance, inventory, assets and events have zero entrypoint classes,
procurement has one. This is project-wide, not a maintenance problem, and the
function-based reality is working fine. But the harness is meant to be the
source of truth, and right now it describes a pattern nothing follows. Either
correct the doc or drop the standard — don't leave it ambiguous, because it
will generate false review findings every time someone reads it literally.
