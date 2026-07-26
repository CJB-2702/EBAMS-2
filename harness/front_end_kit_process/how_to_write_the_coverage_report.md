---
type: "Process Guide"
title: "How to Write the Coverage Report"
description: "You are acting as a Product/UX Agent. Run the inverse checks — every table and every capability — and report the gaps. Advisory, not a gate."
tags: [front-end-kit-process, process-guide]
context_tier: 2
---

# How to Write the Coverage Report

**Role & Objective:**
You are acting as a Product/UX Agent. Produce `coverage_report.md` — the **inverse** checks on the route skeleton.

`route_skeleton.md` asks *"what does this page touch?"*. This document asks the opposite: *"for every table and every capability, which page handles it?"* Nothing else in the kit asks that question, and it is the only mechanical way to find a **missing** page.

**This is advisory, not a gate.** Report the gaps clearly and let the developer decide. Many gaps are correct — plenty of tables have no business having a page.

---

## Instructions

### 1. Table × CRUD matrix

Take every table from the starter kit's `model_diagram.md`. For each, name the route that provides Create, Read, Update, and Delete. Mark `—` where none exists.

```markdown
| Table | Create | Read | Update | Delete | Note |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Part` | `/parts/create` | `/parts/<id>` | `/parts/<id>/edit` | `/parts/<id>/archive` | |
| `PartRevision` | `/parts/create` (card 3) | `/parts/<id>` (card) | — | — | **Gap:** revisions cannot be corrected after creation. |
| `AuditLog` | — | — | — | — | Expected — system-written, no UI. |
```

Every `—` needs a note saying whether it is a gap or expected. An unexplained `—` is an unfinished report.

### 2. Role × capability matrix

Take every capability from `functionality_and_roles.md`. For each role permitted to perform it, name the route where they do so.

```markdown
| Capability | Role | Route | Status |
| :--- | :--- | :--- | :--- |
| Release a work order | Planner | `/work-orders/<id>` (action) | OK |
| Approve an over-budget order | Supervisor | — | **Gap:** permitted, no screen. |
```

A capability the business rules grant with no screen behind it is the highest-value finding this report produces — it means the backend was built to allow something the user cannot actually do.

### 3. Control-layer reachability

Cross-check the actions in `route_skeleton.md` against `control_layer_plan.md`. Two directions:

- **Action with no method** — a page promises something the control layer cannot do. Flag as a build item.
- **Method with no action** — the control layer can do something no page invokes. Often fine (internal helpers, orchestration steps); occasionally reveals a forgotten screen.

### 4. Code cross-check — only if the backend is built

If `app/<subapp>/models/` and `control_layer/` exist, compare them against the starter kit plans and report **disagreements between the kit and the code**.

Do **not** silently reconcile. If `model_diagram.md` shows a relation the code does not have, that is a finding for the developer — either the plan drifted or the build did, and only they know which. Report it and let them decide.

---

## Tone

Report, do not nag. Each gap gets one line and a suggested resolution, not a paragraph of advocacy. Group the findings by severity so the developer can skim:

- **Likely missing page** — a capability or table operation with no route at all.
- **Kit/code disagreement** — the plan and the build differ.
- **Expected absence** — confirmed intentional; listed so nobody re-checks it later.

---

## Example Scenario: Asset Management Application

*Concept:* Tracking vehicles and assignments.

*Expected findings:*

- **Likely missing page** — `VehicleDocument` has a create path inside the vehicle wizard but no update or delete route; a mis-uploaded document cannot be replaced.
- **Likely missing page** — `functionality_and_roles.md` grants Fleet Manager "retire a vehicle", but no route performs it.
- **Expected absence** — `VehicleTelemetry` has no UI; ingested by a scheduled job.

---

## Required Output Format

A single markdown document, `coverage_report.md`, containing:

1. **Findings summary** — grouped by the three severities above, one line each. Put this **first**; the matrices are the evidence, this is the answer.
2. **Table × CRUD matrix.**
3. **Role × capability matrix.**
4. **Control-layer reachability** — the two lists.
5. **Kit/code disagreements** — only when the backend exists.
