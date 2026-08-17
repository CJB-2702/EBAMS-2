---
tier: 2
type: "Technical Specification"
title: "Defined Tools Model and CRUD Specification"
description: "Specification for the defined Tool model in app/parts and its associated presentation layer CRUD entrypoints."
tags: [parts, tools, models, crud, ux-ui]
context_tier: 2
---

# Defined Tools Specification (`app/parts`)

This document defines the schema, behavior, and presentation layer (CRUD) for the **`Tool`** catalog model within the `parts` application (`app/parts`).

---

## 1. Overview & Business Intent

In EBAMS-2, **`app/parts`** serves as the master engineering catalog hub. While physical inventory balances live in `app/inventory`, all defined equipment, cataloged parts, and tool definitions are registered within `app/parts`.

Defined tools (`Tool`) represent reusable catalog items (e.g. torque wrenches, multimeter models, custom extraction rigs, hydraulic jacks) that maintenance procedures (`app/maintenance`) and operational workflows require.

---

## 2. Schema Specification (`app/parts/models/core/tool.py`)

The `Tool` model inherits from `AuditFieldsMixin` for standard platform tracking (`created_at`, `updated_at`, `created_by`, `updated_by`).

```python
from django.db import models
from app.administration.models.auditable_mixin import AuditFieldsMixin


class Tool(AuditFieldsMixin):
    """
    Catalog definition of a tool or specialized equipment item.
    Used for maintenance action requirements, template specifications, and asset servicing.
    """
    name = models.CharField(max_length=200, db_index=True)
    tool_type = models.CharField(max_length=100, blank=True, help_text="e.g. Hand Tool, Power Tool, Measurement, Rigging")
    description = models.TextField(blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    
    manufacturer = models.ForeignKey(
        "parts.PartManufacturer",
        on_delete=models.SET_NULL,
        related_name="tools",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    # Domain Scoping (D14) — default False = visible across all authenticated domains
    is_domain_limited = models.BooleanField(default=False)

    class Meta:
        db_table = "tool"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["tool_type"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.model_number})" if self.model_number else self.name
```

---

## 3. CRUD Presentation Layer Specification

All routes follow EBAMS-2 UX/UI standards (Bulma styling, no rounded corners, HTMX F5-safe reloads, and `format=` query parameter density support).

### 3.1 Route Summary

| Method | Endpoint Path | Description | HTMX Supported |
| :--- | :--- | :--- | :--- |
| `GET` | `/parts/tools/` | Tools Directory (Search, filter, paginated list) | Yes (`htmx-list`) |
| `GET` | `/parts/tools/<int:pk>/` | Tool Detail Page (Specs, usage statistics, activity) | Yes (`htmx-detail`) |
| `GET` / `POST` | `/parts/tools/create/` | Create Tool Form / Submit | No (Full Page) |
| `GET` / `POST` | `/parts/tools/<int:pk>/edit/` | Edit Tool Form / Submit | No (Full Page) |
| `POST` | `/parts/tools/<int:pk>/delete/` | Toggle Active / Soft Delete | Yes (`htmx-row`) |

---

### 3.2 View & Screen Specifications

#### 1. Tool Directory Index (`/parts/tools/`)
* **Layout**: Full-width page with top search/filter header bar and high-density data panel.
* **Header Controls**:
  * Search input: Name, model number, description.
  * Dropdown filter: `tool_type` (Hand Tool, Measurement, Power Tool, etc.).
  * Checkbox filter: Show active only (default: `True`).
  * Action button: `+ New Tool Definition` (Primary button, top right).
* **Data Presentation**:
  * Respects `format=` query param (`condensed`, `medium`, `large`).
  * Columns: Tool Name, Type, Manufacturer, Model Number, Active Status, Usage Count (Action steps referencing tool), Actions.
* **Empty State**: Always renders card chrome with clear message `"No tools defined yet."` per Always-apply Rule #5.

#### 2. Tool Detail Page (`/parts/tools/<int:pk>/`)
* **Layout**: Two-column layout (Left: Specifications & Metadata card; Right: Procedure Usage & Linked Maintenance Templates).
* **Key Information**:
  * Header: Tool Name, Type badge, Model Number.
  * Manufacturer details (linked to `PartManufacturer` detail page if assigned).
  * Specifications & usage notes.
  * Linked `TemplateActionItem` and `ActionTool` references showing which maintenance procedures require this tool.
* **Actions**: Edit Tool, Archive/Deactivate Tool.

#### 3. Create & Edit Tool Forms (`/parts/tools/create/`, `/parts/tools/<int:pk>/edit/`)
* **Layout**: Single-card centered form layout adhering to `harness/UX_UI/form_style_guide.md`.
* **Form Controls**:
  * `name`: Required CharField.
  * `tool_type`: Typeahead / Select or CharField with suggestions.
  * `manufacturer`: `search-dropdown` component searching `PartManufacturer`.
  * `model_number`: CharField.
  * `description`: Multiline text area.
* **Action Buttons**: Standard bottom-right action bar: `Cancel` (flat secondary) and `Save Tool` (primary solid).

---

## 4. Maintenance Integration (`app/maintenance`)

Concrete maintenance tools (`ActionTool`), template steps (`TemplateActionTool`), and library items (`ProtoActionTool`) inherit from `AbstractActionTool`:

```python
class AbstractActionTool(models.Model):
    tool = models.ForeignKey(
        "parts.Tool",
        on_delete=models.SET_NULL,
        related_name="%(class)s_usages",
        null=True,
        blank=True,
        help_text="Optional catalog tool reference",
    )
    tool_name = models.CharField(max_length=200, help_text="Display or ad-hoc tool name")
    quantity_required = models.PositiveIntegerField(default=1)
    specifications = models.TextField(blank=True)

    class Meta:
        abstract = True
```
When selecting a tool in procedure template builders or maintenance action execution, picking a `parts.Tool` populates `tool_id` and defaults `tool_name` to `tool.name`.
