# Porting & File Mapping Plan: Legacy Maintenance to EBAMS-2

This document establishes the comprehensive file mapping, structural migration strategy, and layer inversion plan for porting the **Maintenance** application from the legacy Flask/SQLAlchemy codebase (`/home/cb/REPOS/asset_management/`) into **EBAMS-2 Django 6.x** (`ebams2/app/maintenance/` and `ebams2/app/events/`).

---

## 1. Executive Summary & Core Architectural Rules

The migration follows the **App-First Layer Inversion** pattern (`app/maintenance/models/`, `app/maintenance/control_layer/`, `app/maintenance/presentation_layer/`).

### Architectural Invariants:
1. **Auditing & Soft Delete**: All concrete database models inherit from `AuditFieldsMixin` (`created_at`, `updated_at`, `created_by`, `updated_by`) and `SoftDeleteMixin` (`is_deleted`, `deleted_at`, `deleted_by`).
2. **Data Domain Scoping**: All operational tables carry a `domain` FK to `app.administration.models.data_ownership.domains.Domain` for row-level access control.
3. **Multi-Table Inheritance (MTI)**: `MaintenanceDetail` subclasses `events.Event` directly via Django MTI (located in `app/events/models/details/maintenance.py`).
4. **Virtual Classes to Abstract Mixins**: Legacy SQLAlchemy virtual base classes (`VirtualActionSet`, `VirtualActionItem`, `VirtualActionTool`, `VirtualPartDemand`) are converted to reusable Django abstract mixins (`AbstractActionSet`, `AbstractActionItem`, `AbstractActionTool`, `AbstractPartDemandRequirement`) in `app/maintenance/models/abstract_mixins.py`.
5. **D7 Inward Link Table Pattern**: `MaintenanceDemandLink` (`app/maintenance/models/demand_link.py`) acts as a lean link table pointing *inward* to `procurement.PartDemand`. Zero outward FKs exist on `PartDemand`.
6. **Session Memory Swap**: Legacy `TemplateBuilderMemory` and `TemplateBuilderAttachmentReference` SQL tables are **completely removed**. In-progress procedure templates stage in `request.session['template_builder_draft']` managed by `TemplateBuilderSessionAdapter`. Database rows are created atomically only upon explicit final save.
7. **Defined Tool Catalog Linkage**: `AbstractActionTool` connects directly to the catalog `parts.Tool` model via an optional FK (`tool`).

---

## 2. Models & Data Layer Mapping

| Legacy SQLAlchemy Path (`asset_management/app/data/maintenance/`) | EBAMS-2 Django Target Path | Model Class(es) | Role & Architectural Changes |
| :--- | :--- | :--- | :--- |
| `virtual_action_set.py` | `app/maintenance/models/abstract_mixins.py` | `AbstractActionSet` | Abstract Django model (`abstract = True`). Defines common task fields (`task_name`, `description`). Replaces virtual base class. |
| `virtual_action_item.py` | `app/maintenance/models/abstract_mixins.py` | `AbstractActionItem` | Abstract Django model (`abstract = True`). Defines action step fields (`action_name`, `description`, `instructions`, `estimated_duration_minutes`). |
| `virtual_action_tool.py` | `app/maintenance/models/abstract_mixins.py` | `AbstractActionTool` | Abstract Django model (`abstract = True`). Defines tool requirements. **Adds optional FK `tool` pointing to catalog `parts.Tool`**. |
| `virtual_part_demand.py` | `app/maintenance/models/abstract_mixins.py` | `AbstractPartDemandRequirement` | Abstract Django model (`abstract = True`). Defines part requirement quantity and notes. |
| `base/maintenance_action_sets.py` | `app/events/models/details/maintenance.py` | `MaintenanceDetail` | **MTI Inheritance**: Subclasses `events.Event`. Inherits PK `id`, `domain`, `asset`, `title`, `description`, `status`, `scheduled_start`, etc. Extends with maintenance type, work order ref, meter reading FK, completion fields. |
| `base/actions.py` | `app/maintenance/models/action.py` | `Action` | Subclasses `AbstractActionItem`, `AuditFieldsMixin`, `SoftDeleteMixin`. FK `event_detail` to `MaintenanceDetail`, sequence order, status, assignee. |
| `base/action_tools.py` | `app/maintenance/models/action_tool.py` | `ActionTool` | Subclasses `AbstractActionTool`, `AuditFieldsMixin`, `SoftDeleteMixin`. FK to `Action`. Connects execution step to required tool / catalog `parts.Tool`. |
| `base/maintenance_demand_link.py` | `app/maintenance/models/demand_link.py` | `MaintenanceDemandLink` | **D7 Rule**: Lean link table with FK `action` -> `Action` and FK `part_demand` -> `procurement.PartDemand`. No DB fields on `PartDemand`. |
| `base/maintenance_blockers.py` | `app/maintenance/models/blocker.py` | `MaintenanceBlocker` | Subclasses `AuditFieldsMixin`, `SoftDeleteMixin`. Work stoppage records attached to `MaintenanceDetail`. Reason enum, start/end dates, billable hours impact. |
| `base/asset_limitation_records.py` | `app/maintenance/models/asset_limitation.py` | `AssetLimitationRecord` | Subclasses `AuditFieldsMixin`, `SoftDeleteMixin`. Degraded asset capabilities linked to `MaintenanceDetail` and optional `MaintenanceBlocker`. |
| `templates/template_action_sets.py` | `app/maintenance/models/templates/template_action_set.py` | `TemplateActionSet` | Master procedure template header. Scoped by `Domain` FK, optional `AssetClass`/`AssetModel` FKs. Subclasses `AbstractActionSet`, `AuditFieldsMixin`, `SoftDeleteMixin`. |
| `templates/template_actions.py` | `app/maintenance/models/templates/template_action_item.py` | `TemplateActionItem` | Template action step. FK to `TemplateActionSet`. Subclasses `AbstractActionItem`, `AuditFieldsMixin`, `SoftDeleteMixin`. |
| `templates/template_action_tools.py` | `app/maintenance/models/templates/template_action_tool.py` | `TemplateActionTool` | Template tool requirement step. FK to `TemplateActionItem`. Subclasses `AbstractActionTool`, `AuditFieldsMixin`, `SoftDeleteMixin`. |
| `templates/template_part_demands.py` | `app/maintenance/models/templates/template_part_demand.py` | `TemplatePartDemand` | Template part requirement step. FK to `TemplateActionItem`, FK to `parts.Part`. Subclasses `AbstractPartDemandRequirement`, `AuditFieldsMixin`, `SoftDeleteMixin`. |
| `proto_templates/proto_actions.py` | `app/maintenance/models/proto_templates/proto_action_item.py` | `ProtoActionItem` | Reusable library action step. Subclasses `AbstractActionItem`, `AuditFieldsMixin`, `SoftDeleteMixin`. Scoped by `Domain`. |
| `proto_templates/proto_action_tools.py` | `app/maintenance/models/proto_templates/proto_action_tool.py` | `ProtoActionTool` | Reusable library tool step. FK to `ProtoActionItem`. Subclasses `AbstractActionTool`, `AuditFieldsMixin`, `SoftDeleteMixin`. |
| `proto_templates/proto_part_demands.py` | `app/maintenance/models/proto_templates/proto_part_demand.py` | `ProtoPartDemand` | Reusable library part demand step. FK to `ProtoActionItem`, FK to `parts.Part`. Subclasses `AbstractPartDemandRequirement`, `AuditFieldsMixin`, `SoftDeleteMixin`. |
| `planning/maintenance_plans.py` | `app/maintenance/models/planning/maintenance_plan.py` | `MaintenancePlan` | Recurring schedule rules (calendar/meter-based). FK to `TemplateActionSet`, FK to `assets.Asset`/`AssetModel`. |
| `builders/template_builder_memory.py` | **REMOVED** | N/A (Session Memory) | **DELETED**. Replaced by Django session dict (`request.session['template_builder_draft']`). Zero DB tables created. |
| `builders/template_builder_attachment_reference.py` | **REMOVED** | N/A (Session Memory) | **DELETED**. Staged in session dictionary; converts directly to `events.Attachment` upon commit. |

---

## 3. Business & Control Layer Mapping

| Legacy Business Path (`asset_management/app/business/maintenance/`) | EBAMS-2 Django Control Target Path | Class / Module | Role & Key Refactoring |
| :--- | :--- | :--- | :--- |
| `base/maintenance_context.py` | `app/maintenance/control_layer/maintenance_context.py` | `MaintenanceContext` | OOP Control Context for a single maintenance event. Coordinates status changes, completion workflows, and blocker creation. |
| `base/action_managment/action_context.py` | `app/maintenance/control_layer/action_context.py` | `ActionContext` | OOP Control Context for single action steps. Manages action state transitions (pending, in_progress, completed, blocked). |
| `base/action_managment/part_demand_manager.py` | `app/maintenance/control_layer/part_demand_manager.py` | `PartDemandManager` | Orchestrates creation of `procurement.PartDemand` rows and links them via `MaintenanceDemandLink` (D7 pattern). |
| `base/action_managment/action_tool_creation_manager.py` | `app/maintenance/control_layer/action_tool_manager.py` | `ActionToolManager` | Manages creation and assignment of tools for action steps, supporting catalog lookup via `parts.Tool`. |
| `base/action_managment/maintenance_action_creation_manager.py` | `app/maintenance/control_layer/action_creation_manager.py` | `ActionCreationManager` | Sub-manager handling instantiation and step re-ordering of maintenance actions. |
| `base/action_managment/maintenance_action_orchestrator.py` | `app/maintenance/control_layer/maintenance_orchestrator.py` | `MaintenanceOrchestrator` | Coordinates complex multi-action operational workflows across events, actions, and part demands. |
| `base/billable_hours_manager.py` | `app/maintenance/control_layer/billable_hours_manager.py` | `BillableHoursManager` | Computes billable labor hours and updates `MaintenanceDetail` totals. |
| `base/maintenance_assignment_manager.py` | `app/maintenance/control_layer/maintenance_assignment_manager.py` | `MaintenanceAssignmentManager` | Handles user and team assignments for maintenance events and action steps. |
| `base/capablities_and_blockers/maintenance_blocker_manager.py` | `app/maintenance/control_layer/maintenance_blocker_manager.py` | `MaintenanceBlockerManager` | Controls work stoppage creation, updates, and resolution logging. |
| `base/capablities_and_blockers/asset_limitation_manager.py` | `app/maintenance/control_layer/asset_limitation_manager.py` | `AssetLimitationManager` | Manages asset degradation records, connecting blockers to asset operational states. |
| `builders/template_builder_context.py` | `app/maintenance/control_layer/adapters/template_builder_session_adapter.py` | `TemplateBuilderSessionAdapter` | **SESSION MEMORY SWAP**: Replaces SQL builder memory. Mutates `request.session['template_builder_draft']` in-memory. Atomic DB commit on save. |
| `factories/maintenance_factory.py` | `app/maintenance/control_layer/maintenance_factory.py` | `MaintenanceFactory` | Instantiates `MaintenanceDetail` and underlying `events.Event` parent rows. |
| `factories/action_factory.py` | `app/maintenance/control_layer/action_factory.py` | `ActionFactory` | Instantiates live `Action` steps from procedure templates or proto-templates. |
| `planning/maintenance_planner.py` | `app/maintenance/control_layer/planning/maintenance_planner.py` | `MaintenancePlanner` | Evaluates maintenance plan schedules and triggers event generation. |
| `planning/maintenance_plan_context.py` | `app/maintenance/control_layer/planning/maintenance_plan_context.py` | `MaintenancePlanContext` | OOP Control Context for managing individual recurring maintenance plans. |
| `templates/template_maintenance_context.py` | `app/maintenance/control_layer/template_maintenance_context.py` | `TemplateMaintenanceContext` | OOP Control Context for procedure template operations and lifecycle management. |

---

## 4. Presentation & Route Layer Mapping

> **This table is incomplete.** It collapses six legacy portals into six rows and
> omits the part-demand approval portal, part-demand detail, create-&-assign
> portal, unassigned queue, build-templates hub, proto-action detail, action
> creator portal, plan edit, plan due-asset worklist, event work portal, event
> edit portal, and technician dashboard. See
> [legacy_ui/gap_analysis.md](legacy_ui/gap_analysis.md) for the verified
> 19-surface gap list, [legacy_ui/route_inventory.md](legacy_ui/route_inventory.md)
> for the full legacy HTTP surface, and
> [legacy_ui/page_catalog.md](legacy_ui/page_catalog.md) for screenshot-backed
> page anatomy. Correct this table from those documents before building.

| Legacy Route Path (`asset_management/app/presentation/routes/maintenance/`) | EBAMS-2 Target Path | View Entrypoint / Search Module | UX/UI & HTMX Conventions |
| :--- | :--- | :--- | :--- |
| `main.py` | `app/maintenance/presentation_layer/entrypoints/event_views.py` | `maintenance_index`, `maintenance_detail`, `maintenance_create` | Full page reload support + HTMX table filtering (`format=` density support). |
| `search_utils.py` | `app/maintenance/presentation_layer/search/maintenance_search.py` | `MaintenanceSearch` | Scoped QuerySet filters (domain, status, asset, priority, work order). |
| `action_creator_portal.py` | `app/maintenance/presentation_layer/entrypoints/action_views.py` | `action_create`, `action_status_update`, `action_reorder` | HTMX partial updates for action step inline editing and sequence modification. |
| `template_portal.py` | `app/maintenance/presentation_layer/entrypoints/template_views.py` | `template_builder_view`, `template_step_update`, `template_commit` | **Session-Backed Builder**: Reads/mutates `request.session['template_builder_draft']`. Atomic POST commit. |
| `proto_action_portal.py` | `app/maintenance/presentation_layer/entrypoints/proto_views.py` | `proto_action_index`, `proto_action_create` | Library entrypoints for standard reusable steps. |
| `planning/` | `app/maintenance/presentation_layer/entrypoints/planning_views.py` | `plan_index`, `plan_detail`, `plan_create` | Management of calendar/meter-based recurring plans. |

---

## 5. Template & UI Layer Mapping

| Legacy Template Path (`asset_management/app/presentation/templates/maintenance/`) | EBAMS-2 Target Template Path | Description & UI Style Standard |
| :--- | :--- | :--- |
| `index.html` | `app/maintenance/templates/maintenance/index.html` | Maintenance Hub Index: High-density event ledger, status filters, card chrome (Rule #5 compliant). |
| `details_portal.html` | `app/maintenance/templates/maintenance/detail.html` | Maintenance Event Detail: Parent event info, action step list, blocker section, part demand status. |
| `builder/` | `app/maintenance/templates/maintenance/template_builder.html` | Multi-card single-page builder wizard. Driven by `request.session['template_builder_draft']` and HTMX. |
| `event_components/` | `app/maintenance/templates/maintenance/components/` | Reusable HTMX partials (`_action_row.html`, `_blocker_card.html`, `_part_demand_card.html`). |
| `planning/` | `app/maintenance/templates/maintenance/planning/` | Recurring maintenance plan list and schedule creation cards. |

---

## 6. Implementation Sequence

1. **Step 1: Abstract Mixins & Core Models**
   - Implement `app/maintenance/models/abstract_mixins.py` (`AbstractActionSet`, `AbstractActionItem`, `AbstractActionTool`, `AbstractPartDemandRequirement`).
   - Implement `app/events/models/details/maintenance.py` (`MaintenanceDetail` via MTI subclassing `events.Event`).
   - Implement concrete models: `app/maintenance/models/action.py`, `action_tool.py`, `demand_link.py`, `blocker.py`, `asset_limitation.py`.
   - Implement template models: `app/maintenance/models/templates/` and `proto_templates/`.
   - Implement planning model: `app/maintenance/models/planning/maintenance_plan.py`.

2. **Step 2: Database Reset & Migration Verification**
   - Run `python refresh_project.py` to regenerate Django migrations, rebuild SQLite DB, and verify clean schema instantiation.

3. **Step 3: Control Layer Porting & Session Adapter**
   - Implement `TemplateBuilderSessionAdapter` in `app/maintenance/control_layer/adapters/`.
   - Implement OOP Contexts (`MaintenanceContext`, `ActionContext`, `TemplateMaintenanceContext`) and Managers (`PartDemandManager`, `MaintenanceBlockerManager`, `BillableHoursManager`).

4. **Step 4: Presentation Layer & HTMX Templates**
   - Implement QuerySet search handlers in `presentation_layer/search/`.
   - Implement view entrypoints in `presentation_layer/entrypoints/`.
   - Port Bulma templates to `app/maintenance/templates/maintenance/` ensuring sharp corners (zero border-radius), F5 reload safety, and `format=` query parameter density support.

5. **Step 5: Seeding & Verification**
   - Update dev seed commands (`seed_dev`) to populate sample maintenance events, action steps, procedure templates, and tool linkages.
