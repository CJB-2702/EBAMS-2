---
tier: 2
type: "Technical Decision"
title: "Template Builder: DB Tables to Session Memory Architectural Swap"
description: "Eliminating legacy database draft tables (TemplateBuilderMemory) in favor of zero-pollution Django Session Memory for maintenance procedure builders."
tags: [maintenance, events, templates, session-memory, architecture]
context_tier: 2
---

# Technical Decision: Replacing Legacy Template Builder DB Tables with Session Memory

This document details the architectural decision to eliminate database-backed template builder staging tables (`TemplateBuilderMemory` and `TemplateBuilderAttachmentReference`) in favor of **Django Session Memory** in EBAMS-2.

---

## 1. Context & Legacy Problem

In the legacy Flask/SQLAlchemy application (`asset_management`), building multi-step maintenance procedure templates relied on two SQL database tables:

1. **`TemplateBuilderMemory`**: Stored draft template steps, action names, sequences, tool requirements, and part demands as serialized JSON blobs across user form interactions.
2. **`TemplateBuilderAttachmentReference`**: Stored references to temporary file uploads staged during template creation.

### Issues with the Legacy Approach:
* **Database Pollution**: Navigating away or closing the browser left orphan draft rows in `TemplateBuilderMemory` that required background cleanup cron jobs.
* **Unnecessary I/O Overhead**: Every minor UI interaction (e.g., reordering an action step, editing a tool quantity) incurred database writes and transactions.
* **Schema Rigidity**: Modifying draft fields required schema migrations or complex JSON blob mutations on SQL tables.

---

## 2. The EBAMS-2 Solution: Session Memory Architecture

In EBAMS-2, **no database tables exist for in-progress draft templates**.

Instead, draft state is held entirely in Django session memory (`request.session['template_builder_draft']`) and managed by a dedicated Control Layer adapter (`TemplateBuilderSessionAdapter`).

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            User Browser (Wizard UI)                         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Interactive HTMX requests
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TemplateBuilderSessionAdapter                          │
│        (Reads / Mutates request.session['template_builder_draft'])          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ Explicit "Save Template" Commit
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Database Persistence (transaction.atomic)                  │
│  TemplateActionSet -> TemplateActionItem -> TemplateActionTool / Demand     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Session Draft Data Structure

The `TemplateBuilderSessionAdapter` operates on a strongly typed session dictionary:

```python
{
    "draft_id": "tpl_draft_982341",
    "task_name": "500-Hour Generator Service",
    "description": "Standard preventive maintenance procedure for diesel generators.",
    "asset_class_id": 4,
    "asset_model_id": 12,
    "domain_id": 1,
    "actions": [
        {
            "temp_id": "act_step_1",
            "sequence_order": 1,
            "action_name": "Inspect & Change Engine Oil Filter",
            "instructions": "Drain oil container into approved recovery tank. Replace filter element.",
            "estimated_duration_minutes": 45,
            "tools": [
                {
                    "temp_id": "tool_1",
                    "tool_id": 8,  # Optional pointer to parts.Tool
                    "tool_name": "Filter Strap Wrench 4-inch",
                    "quantity_required": 1,
                    "specifications": "Heavy duty"
                }
            ],
            "part_demands": [
                {
                    "temp_id": "demand_1",
                    "part_id": 104,  # FK to parts.Part
                    "quantity_required": 2,
                    "notes": "Primary Oil Filter Element"
                }
            ]
        }
    ],
    "attachments": []
}
```

---

## 4. Key Mechanics & Workflow

### 4.1 F5 Reload Safety & HTMX Integration
* **Full Page Reload (F5)**: The UI controller checks `request.session.get('template_builder_draft')`. If present, the builder page reconstructs its complete state directly from session memory without database queries.
* **HTMX Micro-Interactions**: Actions like `Add Action Step`, `Delete Tool Line`, `Reorder Sequence`, or `Stage Part Demand` send lightweight HTMX requests. The adapter mutates the session dictionary in memory and returns targeted HTML partials.

### 4.2 Atomic Persistence on Commit
Database records are created **only** when the user submits the final step by clicking **"Save Template"**:

1. `TemplateBuilderSessionAdapter.commit(user, domain)` is invoked.
2. Inside `with transaction.atomic():`:
   * `TemplateActionSet` is created.
   * `TemplateActionItem` rows are created for each action in `draft['actions']`.
   * `TemplateActionTool` rows are created for tools attached to each action.
   * `TemplatePartDemand` rows are created for part demands attached to each action.
3. Upon success, `request.session.pop('template_builder_draft', None)` purges the draft state.

### 4.3 Zero Cleanup on Cancellation
If the user clicks "Cancel" or abandons the page:
* `request.session.pop('template_builder_draft', None)` is called.
* Zero rows were written to the database, so zero database cleanup or tombstone management is required.

---

## 5. Architectural Benefits Summary

| Feature | Legacy Flask App | EBAMS-2 Implementation |
| :--- | :--- | :--- |
| **Draft Storage** | `TemplateBuilderMemory` SQL Table | `request.session['template_builder_draft']` |
| **File Staging** | `TemplateBuilderAttachmentReference` Table | Temporary Session Staging / `events.Attachment` |
| **Database Overhead** | Writes on every field blur/keystroke | Zero DB writes until explicit "Save Template" |
| **Orphan Data Cleanup** | Required background DB cleanup script | Automatic via Django session expiration / clear |
| **Transaction Safety** | Non-atomic partial DB commits | 100% Atomic via single `transaction.atomic()` |
