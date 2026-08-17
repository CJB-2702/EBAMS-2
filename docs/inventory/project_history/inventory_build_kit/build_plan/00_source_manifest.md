# Source Manifest — OLD vs NEW System Documents

Read this before any other build-plan document. It classifies every planning source so old-system
process logic cannot leak into the build as if it were decided. Rule of thumb: **OLD sources may
inspire layout and interaction feel; they may never decide a workflow, a model, or a rule.**

## NEW system — authoritative (workflows and models are decided here)

| Source | Role |
| :--- | :--- |
| `inventory_build_kit/inventory_build_kit_review.md` | **Binding decision record.** Its 9 confirmed decisions override every other kit document. |
| `inventory_build_kit/new_system/new_system_architecture_overview.md` | Target architecture: procurement/inventory split, Warehouse→Room→StorageLocation topography, intake room rules. |
| `inventory_build_kit/new_system/part_movements.md` | Movement types, XYZ formatting rule, `PartMovement` model, domain checks. |
| `inventory_build_kit/new_system/part_issues.md` | Issuance flows and gates (model superseded in part by FD-5 — extend existing `PartIssue`). |
| `inventory_build_kit/new_system/intake_engine_integration.md` | Intake engine wiring into warehouse topography (table names corrected per FD-11). |
| `inventory_build_kit/new_system/unaccounted_inventory_discrepancies_problem_statement.md` | Problem framing for auditing (background). |
| `inventory_build_kit/new_system/unaccounted_inventory_discrepancies_solution.md` | Audit sessions / inline edit blueprint (types corrected per FD-8, layering per FD-15). |
| `inventory_build_kit/new_system/svg_gui_mapping_migration.md` | SVG spatial engine migration plan — **starting point**, with gaps closed by FD-22…FD-25. |
| `inventory_build_kit/serialized_inventory_tracking.md` | Serial-number grain across the whole pipeline (binding via review Decision 5). |
| `inventory_build_kit/shipment_and_intake_design_review.md` | Open questions record — all answered by the intake kit; historical. |
| `inventory_build_kit/migrations/shipment_to_inventory_gap.md` | The inventory-creation boundary (session commit) and dual entry points (entry-point split refined by FD-13). |
| `inventory_build_kit/migrations/model_migration_plan.md` | **Conceptual field mapping only** (FD-7). Its Django snippets are drafts; FKs corrected per FD-1…FD-4. No data ETL. |
| `inventory_build_kit/inventory_intake_kit/*` | Intake starter kit: questionnaire, business concept, domain model, control-layer map, reconciliation specs, diagrams. Authoritative for intake behavior **except** where the review supersedes (reconciliation grain FD-9, session fields FD-10, auto-intake FD-13). |

## OLD system — reference / inspiration only (workflows not trusted)

| Source | What it is good for | What it must NOT decide |
| :--- | :--- | :--- |
| `inventory_build_kit/old_system/old_system_architecture_review.md` | Understanding legacy schema and its pain points. Carries its own SUPERSEDED warning banner. | Any model shape, any receiving workflow. `ArrivalHeader`/`ArrivalLine`/`package_headers` do not exist in the new system. |
| `/home/cb/REPOS/asset_management` (whole repo; templates under `app/presentation/templates/`) | **UI/UX reference** — kept deliberately for the SVG storeroom GUI look-and-feel: click-a-shape location picking, card-grid drill-downs, the issue queue feel. The UI Review Map (07) is built from it. | Process logic. Its arrivals portal, modal-based moves, and dual-linkage tables were never fully thought through. It is also a different stack (Flask/SQLAlchemy/Bootstrap) — no code or markup is ported verbatim. |

## Repo guidance consumed by this plan (not part of the kit)

- `.claude/agents/backend-engineer.md`, `.claude/agents/frontend-engineer.md`
- `harness/Architecture/` (layer rules, OOP control patterns, model patterns, endpoint + HTMX patterns, seeding, tests)
- `harness/UX_UI/` (form style, modals law, multi-step flows, format contract, sharp corners)
- Existing code: `app/procurement/control_layer/shipment_context.py` (`accept_line`),
  `app/inventory/models/issuance/part_issue.py` (+ `PartIssuanceOrchestrator`),
  `app/administration/models/data_ownership/` (`Domain`, `Division`), `app/parts/models/core/part.py`.

## Conflict resolutions

All conflicts between the rows above are resolved in [`/fable_decisions.md`](../../fable_decisions.md)
(FD-1 … FD-28). Implementation agents cite FD numbers; they do not re-litigate them.
