---
okf_version: "0.1"
type: "Process Guide"
title: "Maintenance Application Starter Kit Questionnaire"
description: "Pre-filled 20-question questionnaire for importing and adapting the Maintenance module into EBAMS-2."
tags: [starter-kit, maintenance, questionnaire]
context_tier: 2
personas: [backend, business]
---

# Starter Kit Questionnaire — Maintenance Application

**Status:** `DRAFT`

---

## How this works

1. `/kit-builder` created the kit folder `maintenance_starter_kit/`, wrote `initial_prompt.md`, `data_model_translation.md`, and pre-filled every answer it could in this `questionnaire.md`.
2. Review `questionnaire.md` and fill in or adjust answers as best you can.
3. Change **Status: COMPLETE** at the top when ready.
4. The Kit Builder will then interrogate the answers and generate the remaining starter kit documents (`business_concept_definition.md`, `domain_model.md`, `control_layer_map.md`, `functionality_and_roles.md`, etc.).

---

## A. Goals

*What this is for. Answer these without naming a single table.*

### G1 — In one sentence, with no nouns from your schema: what does this let someone do that they cannot do today?

**Answer:**
Let teams define, schedule, track, and execute maintenance work items, tool requirements, material demands, and operational limitation records against organizational assets within their scope. _(from initial prompt)_

---

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

**Answer:**
This is explicitly NOT an inventory management or warehouse stock tracking system (which lives in Inventory), nor a vendor purchasing system (which lives in Procurement). Maintenance defines requirements and tracks execution, but physical stock issuance and purchasing are handled by Inventory and Procurement respectively. _(from initial prompt)_

---

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

**Answer:**
The central hub record is the **Maintenance Event** (subclassing `Event` as `MaintenanceDetail`). The rest of the application references it solely by its `Event.id` / `hashid`. _(from initial prompt)_

---

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

**Answer:**
Authoritative: maintenance procedure templates, maintenance plans, action execution steps, logged billable hours, blockers, and asset limitation records.
Mirrored/External: part availability and issuance status (mirrored from Procurement/Inventory), asset specs/meter readings (mirrored/recorded via Assets). _(from initial prompt)_

---

## B. Personas

### P1 — Name each persona and the one sentence they would use to describe their job here. Which is the highest-volume user?

**Answer:**
1. **Maintenance Technician** *(Highest Volume)*: "I log in to see my assigned work actions, track my time, request required parts/tools, and mark tasks finished or blocked."
2. **Maintenance Manager / Planner**: "I create procedure templates, schedule recurring maintenance plans, assign work to technicians, and resolve blockers."
3. **Fleet / Asset Manager**: "I monitor asset operational capability limitations, maintenance backlog, and overall fleet health." _(from initial prompt)_

---

### P2 — For each persona, what do they do 50 times a day versus once a month?

**Answer:**
- **Technician**: 50x/day: view action details, change action status (Not Started -> In Progress -> Complete), record notes/hours. 1x/month: review monthly work metrics.
- **Planner/Manager**: 50x/day: check event queue, assign technicians, review blockers. 1x/month: build or update master procedure templates and recurring maintenance plans.
- **Fleet Manager**: 50x/day: view asset capability status summary. 1x/month: conduct compliance audits. _(from initial prompt)_

---

### P3 — Fill in the capability × role matrix, including the cells you are unsure of.

**Answer:**

| Capability | Maintenance Technician | Maintenance Manager | Fleet Manager |
| :--- | :---: | :---: | :---: |
| Create / Edit Maintenance Event | R / U | C / R / U / D | R |
| Execute Actions & Log Hours | C / R / U | C / R / U | R |
| Raise Part Demands on Action | C / R | C / R / U / D | R |
| Track / Assign Action Tools | R / U | C / R / U / D | R |
| Log Work Blockers | C / R / U | C / R / U / D | R |
| Record Asset Capability Limitation | C / R / U | C / R / U / D | C / R / U |
| Build Procedure Templates | R | C / R / U / D | R |
| Manage Maintenance Plans | R | C / R / U / D | R |

---

### P4 — Is any of this data restricted to a subset of users? Is restriction the default or the exception, and roughly what percentage?

**Answer:**
Restriction is default via EBAMS-2 **Data Domain** scoping (`Domain` FK). Users can only view and interact with maintenance events, templates, and demands within the Data Domains assigned to their user role. _(from initial prompt)_

---

## C. Business relationships

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

**Answer:**
- Event (1) <-> (1) MaintenanceDetail (1:1 MTI)
- MaintenanceDetail (1) <-> (M) Action (1:M)
- Action (1) <-> (M) ActionTool (1:M)
- Action (1) <-> (M) MaintenanceDemandLink <-> (1) PartDemand (1:M via link table)
- MaintenanceDetail (1) <-> (M) MaintenanceBlocker (1:M)
- MaintenanceDetail (1) <-> (M) AssetLimitationRecord (1:M)
- TemplateActionSet (1) <-> (M) TemplateActionItem (1:M)

If Action <-> MaintenanceDetail became M2M (an action shared across multiple maintenance events), sequence ordering and completion tracking would break. Keeping actions strictly owned by one event preserves clear execution state. _(from initial prompt)_

---

### R2 — When a record is created, what else must come into existence automatically? For each: if it fails, does the original creation fail too?

**Answer:**
When a Maintenance Event is created from a `TemplateActionSet`:
1. `MaintenanceDetail` event row is instantiated.
2. `TemplateActionItem` rows expand into concrete `Action` rows.
3. `TemplateActionTool` rows expand into `ActionTool` rows.
4. `TemplatePartDemand` rows expand into `PartDemand` (in Procurement) + `MaintenanceDemandLink` rows.

All must pass within a single atomic database transaction. If any step fails during template instantiation, the creation transaction rolls back completely. _(from initial prompt)_

---

### R3 — When a record is deleted or deactivated, what happens to everything pointing at it? Soft or hard?

**Answer:**
Soft delete throughout (`SoftDeleteMixin`). Soft-deleting a Maintenance Event cascades soft-delete to its child Actions, ActionTools, Blockers, and DemandLinks. Linked hub `PartDemand` records in Procurement remain intact but their maintenance link is soft-deleted. _(from initial prompt)_

---

### R4 — When several constraints apply at once, must all pass or any pass? Write the truth table.

**Answer:**
To mark a Maintenance Event **Complete**:
- All child `Action` rows must be in `Complete` or `Skipped` status (ALL must pass).
- All active `MaintenanceBlocker` rows must be resolved (`end_date` set).
- Any active `AssetLimitationRecord` must be closed or updated to final status. _(from initial prompt)_

---

### R5 — At what moment is each rule enforced — authoring time, assignment time, or execution time? What happens when the check cannot be decided?

**Answer:**
- **Authoring time**: Procedure template validation (valid parts, tools, sequences).
- **Assignment time**: Event creation & technician assignment (domain authorization, asset availability).
- **Execution time**: Action status transitions, billable hours capture, part demand creation, blocker logging, and event completion gates. _(from initial prompt)_

---

### R6 — Which app owns this? Which apps must remain completely ignorant of it, and what are the permitted seams?

**Answer:**
- **Owned by Maintenance**: procedure templates, maintenance plans, action execution, action tools, blockers, and asset limitation records.
- **Seams**:
  - `events`: `MaintenanceDetail` subclasses `events.Event`.
  - `procurement`: linked via `MaintenanceDemandLink` -> `procurement.PartDemand` (D7 pattern).
  - `assets`: referenced via `asset_id` on `Event`.
  - `administration`: scoped by `domain` and assigned users (`User`).
- **Ignorant**: Parts and Procurement apps have no direct FK pointing at Maintenance (D7 seam). _(from initial prompt)_

---

## D. Data model

### M1 — Glossary: list every domain noun. Mark any word that already means something else in this system, in Django, or in the business.

**Answer:**

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| `MaintenanceDetail` | Event detail record for a maintenance event | Existing stub in `app/events/models/details/maintenance.py` |
| `Action` | Single task step within a maintenance event | Django admin actions, HTML form actions |
| `ActionTool` | Tool requirement for an action step | Generic dev tools |
| `MaintenanceDemandLink` | Join record connecting Action to PartDemand | Legacy `maintenance_demand_link` |
| `MaintenanceBlocker` | Work pause/stoppage record on an event | General process blockers |
| `AssetLimitationRecord` | Capability degradation history on an asset | General asset status |
| `TemplateActionSet` | Master procedure template container | N/A |
| `TemplateActionItem` | Template task step | N/A |
| `TemplateActionTool` | Template tool requirement | N/A |
| `TemplatePartDemand` | Template part demand requirement | N/A |
| `MaintenancePlan` | Recurring maintenance schedule rule | N/A |
| `TemplateBuilderSession` | Session-backed draft state for building templates | Replaces legacy `TemplateBuilderMemory` table |

---

### M2 — Where two concepts overlap, which is the concrete/primary one and which is the restricted view of it?

**Answer:**
`events.Event` is the primary concrete base entity for all events. `MaintenanceDetail` is the maintenance-specific detail table extending `Event` via Multi-Table Inheritance (MTI). _(from initial prompt)_

---

### M3 — Is this variation a type label, a set of capability flags, or a distinct class? Can a caller construct an invalid combination?

**Answer:**
- Maintenance Type: Enum (`Scheduled`, `Reactive`, `Inspection`, `Preventive`).
- Action Status: Enum (`Not Started`, `In Progress`, `Complete`, `Skipped`, `Failed`, `Blocked`).
- Maintenance Event Status: Enum (`Planned`, `In Progress`, `Complete`, `Cancelled`, `Failed`, `Skipped`, `Blocked`).
- Capability Status: Enum (`Non Capable`, `Partially Capable - Functional Limitations`, `Partially Capable - Temporary Compensation`, `Fully Capable - Temporary Compensation`). _(from initial prompt)_

---

### M4 — Is this attribute intrinsic to what the thing *is*, or to *where it is used*?

**Answer:**
Part demands and tool requirements on template actions describe *where it is used* (in that specific procedure step), while `Part` definitions and `Tool` definitions describe *what the thing is*. _(from initial prompt)_

---

### M5 — How do users version and identify this? Can you trust their naming convention? What exactly does "current" mean, and is it the same as "newest"?

**Answer:**
Templates carry a `version` field or status (`Draft`, `Active`, `Archived`). "Active" is the single operational template used for instantiating new events. _(from initial prompt)_

---

### M6 — Which entities carry free-form human content — comments, documents, photos, notes? Assume the answer is "more than you think."

**Answer:**
Comments and file attachments attach directly to the underlying `Event` via `events.Comment` and `events.Attachment`. `Action` and `MaintenanceBlocker` also carry completion and blocker notes. _(from initial prompt)_

---

## E. Migration defaults *(optional — only if this kit changes existing behavior)*

### X1 — What is today's behavior, and does the new default reproduce it exactly? What are you doing with the old code — clean cut or shims?

**Answer:**
- **Clean cut migration**: Legacy SQLAlchemy models in `asset_management` are mapped to Django 6.x models in `ebams2`.
- **Template Builder Memory**: `TemplateBuilderMemory` DB table is completely ELIMINATED and replaced by session memory (`request.session['template_builder_draft']`).
- **Database Reset**: Development database is regenerated via `python refresh_project.py`. _(from initial prompt)_

---

## Sign-off

- [x] Every question above is answered, or explicitly marked unknown.
- [x] Pre-filled `_(from initial prompt)_` answers have been reviewed.
- [ ] **Status at the top of this file is set to `COMPLETE`.**
