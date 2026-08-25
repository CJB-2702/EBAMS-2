# Data Model Translation Document: Legacy Maintenance to EBAMS-2

This document provides a comprehensive mapping and translation strategy for migrating the **Maintenance** application data layer from the legacy Flask/SQLAlchemy application (`/home/cb/REPOS/asset_management/app/data/maintenance/`) into the Django 6.x **EBAMS-2** architecture (`app/events/` and `app/maintenance/`).

---

## 1. Architectural Principles & Standard Mixins

In EBAMS-2, all database models conform to strict platform conventions:

1. **Primary Keys**: Integer `BigAutoField` PKs across all models. Hashid encoding (8-char string) is used exclusively at URL boundaries for external facing identifiers (e.g. `Event.id`).
2. **Auditability & Soft Delete**: Standard models inherit from:
   - `app.administration.models.auditable_mixin.AuditFieldsMixin` (`created_at`, `updated_at`, `created_by`, `updated_by`)
   - `app.administration.models.soft_delete_mixin.SoftDeleteMixin` (`is_deleted`, `deleted_at`, `deleted_by`)
3. **Data Domain Scoping**: Scoped operational entities require a `domain` FK to `app.administration.models.data_ownership.domains.Domain` for row-level access control.
4. **Abstract Base Mixins (Replacing Virtual Base Classes)**:
   Legacy SQLAlchemy Python virtual classes (`VirtualActionSet`, `VirtualActionItem`, `VirtualActionTool`, `VirtualPartDemand`) are replaced by Django abstract model mixins:
   - `AbstractActionSet` (common fields: `task_name`, `description`)
   - `AbstractActionItem` (common fields: `action_name`, `description`, `instructions`, `estimated_duration_minutes`)
   - `AbstractActionTool` (common fields: `tool_name`, `quantity_required`, `specifications`)
   - `AbstractPartDemandRequirement` (common fields: `quantity_required`, `notes`)

---

## 2. Complete Data Model Translation Matrix

| Legacy Model / Table (`asset_management`) | EBAMS-2 Model Class | EBAMS-2 Application Path | Translation & Structural Changes |
| :--- | :--- | :--- | :--- |
| `MaintenanceActionSet` | `MaintenanceDetail` | `app/events/models/details/maintenance.py` | Subclasses `events.Event` via Django Multi-Table Inheritance (MTI). Serves as the concrete maintenance event container. Extends existing `MaintenanceDetail` stub with execution, assignment, meter, and template FK fields. |
| `Action` | `Action` | `app/maintenance/models/action.py` | Subclasses `AbstractActionItem`, `AuditFieldsMixin`, `SoftDeleteMixin`. FK to `MaintenanceDetail` (`event_detail`), sequence ordering, execution tracking, assigned user FKs. |
| `ActionTool` | `ActionTool` | `app/maintenance/models/action_tool.py` | Subclasses `AbstractActionTool`, `AuditFieldsMixin`, `SoftDeleteMixin`. FK to `Action`. Tool requirements for an action execution step. FKs to `administration.User` for assignment tracking. |
| `MaintenanceDemandLink` | `MaintenanceDemandLink` | `app/maintenance/models/demand_link.py` | Lean link table connecting an `Action` to a hub `procurement.PartDemand` (D7 architectural pattern). Carries `action_id`, `part_demand_id`, `sequence_order`. |
| `MaintenanceBlocker` | `MaintenanceBlocker` | `app/maintenance/models/blocker.py` | Work pause/stoppage records logged against a `MaintenanceDetail`. Stores reason enum, notes, start/end dates, billable hours, and expected resolution. |
| `AssetLimitationRecord` | `AssetLimitationRecord` | `app/maintenance/models/asset_limitation.py` | Operational capability degradation history for an asset. FK to `MaintenanceDetail`, optional FK to `MaintenanceBlocker`, capability status enum, limitation description, and compensations. |
| `TemplateActionSet` | `TemplateActionSet` | `app/maintenance/models/templates/template_action_set.py` | Master maintenance procedure template. Scoped by `domain` FK. Optional FKs to `asset_class` or `asset_model`. |
| `TemplateActionItem` | `TemplateActionItem` | `app/maintenance/models/templates/template_action_item.py` | Individual action step within a procedure template. FK to `TemplateActionSet`. |
| `TemplateActionTool` | `TemplateActionTool` | `app/maintenance/models/templates/template_action_tool.py` | Tool requirement within a template action step. FK to `TemplateActionItem`. |
| `TemplatePartDemand` | `TemplatePartDemand` | `app/maintenance/models/templates/template_part_demand.py` | Part requirement within a template action step. FK to `TemplateActionItem`, FK to `parts.Part`. |
| `ProtoActionItem`, `ProtoActionTool`, `ProtoPartDemand` | `ProtoActionItem`, `ProtoActionTool`, `ProtoPartDemand` | `app/maintenance/models/proto_templates/` | Reusable standalone library items for populating procedure templates or live actions. |
| `MaintenancePlan` | `MaintenancePlan` | `app/maintenance/models/planning/maintenance_plan.py` | Recurring maintenance schedule rules (time-based or meter-based). FK to `assets.Asset` or `assets.AssetModel`, FK to `TemplateActionSet`. |
| `TemplateBuilderMemory` | **REMOVED** | N/A (Session Memory) | **ELIMINATED**. Replaced by Django Session Memory (`request.session['template_builder_draft']`). No database table created. |
| `TemplateBuilderAttachmentReference` | **REMOVED** | N/A (Session Memory + Events Attachment) | **ELIMINATED**. Direct file uploads stage in session or integrate directly with `events.Attachment` / `events.Comment`. |

---

## 3. Key Model Translation Details

### 3.1 Maintenance Event Container (`MaintenanceDetail`)

In EBAMS-2, `MaintenanceDetail` subclasses `events.Event` (`app/events/models/event.py`).

**Legacy Fields vs EBAMS-2 Fields:**
- `event_id`: In EBAMS-2 MTI, `Event` is the parent table. `MaintenanceDetail` inherits `id`, `domain_id`, `asset_id`, `title`, `description`, `status`, `priority`, `scheduled_start`, `actual_start`, `actual_end` directly from `Event`.
- `maintenance_type`: Enum (`scheduled`, `reactive`, `inspection`, `preventive`).
- `work_order_reference`: CharField(100).
- `maintenance_schedule`: CharField(255).
- `template_action_set`: FK to `TemplateActionSet` (null=True, blank=True).
- `maintenance_plan`: FK to `MaintenancePlan` (null=True, blank=True).
- `actual_billable_hours`: FloatField or DecimalField(6, 2).
- `assigned_user`: FK to `administration.User` (related_name="assigned_maintenance_events").
- `assigned_by`: FK to `administration.User` (related_name="assigned_maintenance_events_by_me").
- `completed_by`: FK to `administration.User` (related_name="completed_maintenance_events").
- `completion_notes`: TextField(blank=True).
- `blocker_notes`: TextField(blank=True).
- `meter_reading`: FK to `assets.MeterHistory` (null=True, blank=True).

### 3.2 Part Demand Link (`MaintenanceDemandLink`) & D7 Architecture Pattern

In EBAMS-2, `PartDemand` lives in `app.procurement.models.demand.part_demand.PartDemand`.

Per EBAMS-2 architectural rule **D7**:
> *"Consumer apps (Maintenance, Dispatching, Inventory) own their own link tables pointing inward at PartDemand; there is never a pointer outward from PartDemand to consumer apps."*

`MaintenanceDemandLink` acts as this lean join table:
```python
class MaintenanceDemandLink(AuditFieldsMixin, SoftDeleteMixin):
    action = models.ForeignKey(
        "maintenance.Action",
        on_delete=models.CASCADE,
        related_name="demand_links",
    )
    part_demand = models.ForeignKey(
        "procurement.PartDemand",
        on_delete=models.PROTECT,
        related_name="maintenance_links",
    )
    sequence_order = models.PositiveIntegerField(default=1)

    class Meta:
        db_table = "maintenance_demand_link"
        constraints = [
            models.UniqueConstraint(
                fields=["action", "part_demand"],
                name="uq_maintenance_action_part_demand",
            )
        ]
```

When creating a part demand from a maintenance action:
1. `PartDemandManager` creates a `PartDemand` row in `procurement.PartDemand` with `source_module=DemandSourceModule.MAINTENANCE` and the event's `domain`.
2. `MaintenanceDemandLink` creates the lean join pointing `action_id` -> `part_demand_id`.

### 3.3 Replacement of Template Builder DB Tables with Session Memory

In the legacy application:
- `TemplateBuilderMemory` stored draft JSON templates in SQL database tables during multi-step creation.
- `TemplateBuilderAttachmentReference` stored draft file uploads attached to in-progress templates.

**In EBAMS-2:**
- **Zero Database Pollution**: Draft state is stored purely in Django session memory (`request.session['template_builder_draft']`).
- **Session Struct**: A typed dictionary / session adapter (`TemplateBuilderSessionAdapter`) manages the draft payload structure in memory:
  ```python
  draft = {
      "task_name": "500-Hour Generator Service",
      "description": "Standard 500-hour service procedure",
      "asset_class_id": 4,
      "actions": [
          {
              "temp_id": "act_1",
              "action_name": "Change Engine Oil",
              "sequence_order": 1,
              "estimated_duration_minutes": 45,
              "tools": [{"tool_name": "Filter Wrench", "quantity_required": 1}],
              "part_demands": [{"part_id": 12, "quantity_required": 2, "notes": "Oil Filter"}]
          }
      ],
      "attachments": []
  }
  ```
- **F5 Reload Safety**: The UI renders directly from session state.
- **Atomic Persistence**: Database rows (`TemplateActionSet`, `TemplateActionItem`, `TemplateActionTool`, `TemplatePartDemand`) are only created when the user explicitly clicks "Save Template". Canceling or navigating away clears the session key cleanly without orphan database records.

---

## 4. Summary of Foreign Key Cross-App Dependencies

```
┌─────────────────────────────────────────────────────────────┐
│                    administration.Domain                    │
└──────┬──────────────────────┬───────────────────────┬───────┘
       │ (scoping)            │ (scoping)             │ (scoping)
       ▼                      ▼                       ▼
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│ assets.Asset │       │ events.Event │       │ parts.Part   │
└──────┬───────┘       └──────┬───────┘       └──────┬───────┘
       │                      │                      │
       │ (1:1 MTI)            │                      │
       ▼                      ▼                      │
┌─────────────────────────────────────┐              │
│     events.MaintenanceDetail        │              │
└──────┬──────────────────────┬───────┘              │
       │                      │                      │
       ▼                      ▼                      │
┌──────────────┐       ┌──────────────┐              │
│    Action    │       │   Blocker    │              │
└──────┬───────┘       └──────────────┘              │
       │                                             │
       ├───────────────────────┐                     │
       ▼                       ▼                     ▼
┌──────────────┐       ┌──────────────────────────────┐
│  ActionTool  │       │    MaintenanceDemandLink     │
└──────────────┘       └──────────────┬───────────────┘
                                      │ (points inward)
                                      ▼
                       ┌──────────────────────────────┐
                       │    procurement.PartDemand    │
                       └──────────────────────────────┘
```

---

## 5. Verification Plan & Next Steps

1. **Questionnaire Confirmation**: User reviews and completes `questionnaire.md`.
2. **Schema Draft Validation**: Verify all field types, constraints, and audit mixins match EBAMS-2 model standards.
3. **Control Layer Planning**: Design the OOP Control Layer (`MaintenanceContext`, `ActionContext`, `TemplateBuilderSessionAdapter`, `PartDemandManager`) following `harness/Architecture/patterns/oop_control_patterns.md`.
