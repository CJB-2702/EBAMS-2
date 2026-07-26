---
type: "Technical Decision"
title: "Asset Management — Business Concept Definition"
description: "The Asset Management application is the operational backbone for tracking physical assets throughout their lifecycle — from initial registration, through active use and modification, to eventual decommissioning."
tags: [technical-decisions, technical-decision, project-history, assets-migration-project]
context_tier: 2
---

# Asset Management — Business Concept Definition

> This document is a non-technical functional overview. No database tables, service classes, or implementation details appear here.

---

## What This Application Does

The Asset Management application is the operational backbone for tracking physical assets throughout their lifecycle — from initial registration, through active use and modification, to eventual decommissioning. It gives teams a single, authoritative place to find out what assets exist, what condition they are in, who is responsible for them, and what work has been done to them.

---

## Core Capabilities

### 1. Asset Registry

Users can browse and search a catalog of all assets in the system. For each asset, they can view its identity, current status, assigned domain, and key specifications. The registry is scoped to the data domains the user is assigned to — users only see assets their team is responsible for.

**Primary users:** Fleet operators, maintenance coordinators, dispatchers, managers.

---

### 2. Asset Classification and Model Definitions

Assets are organized by class (the broad category, e.g. "Generator", "Vehicle", "Pump") and by model (the specific product definition, e.g. "Caterpillar 320 GC Excavator"). Models are structured so a base definition can have named revisions or variants, reflecting how real equipment evolves over time without losing the connection to the original product line.

Manufacturers are tracked as their own managed list, separate from models, so one manufacturer can supply many models and reporting by manufacturer is straightforward.

**Primary users:** Fleet managers, data stewards, procurement staff.

---

### 3. Domain Scoping — "Who Can See What"

Every asset belongs to exactly one data domain. Data domains represent operational scopes (a facility, a department, a project). Users are assigned to domains, and that assignment determines which assets they can see and work with.

Asset classes carry their own domain assignments so administrators can control which classes are visible or creatable within a given domain. When an asset class has its domain restriction enabled, assets of that class can only be placed inside domains the class is configured for.

**Primary users:** System administrators, domain owners.

---

### 4. Asset Hierarchy — Parent and Child Relationships

Assets can be organized into parent-child trees. A complex piece of equipment (a vehicle) may have attached assets (a trailer, a mounted generator, a tool rack). The system tracks the full lineage — root asset, direct parent, and depth in the tree — and records the history of how relationships changed over time.

**Primary users:** Fleet operators, dispatchers.

---

### 5. Meter and Usage Tracking

Assets support up to four meter channels (hours, kilometres, cycles, etc.). Users can record meter readings, and the system maintains a history of those readings so usage trends are visible over time. The model definition specifies what unit each meter channel represents for that type of equipment.

**Primary users:** Maintenance coordinators, operators.

---

### 6. Capability Tracking

A capability is a service or function an asset can perform (e.g. "Aerial Lift", "High-Pressure Wash", "Cold-Chain Transport"). Capabilities are defined at the class and model level as templates, then assigned to individual assets. Knowing an asset's capabilities allows dispatch and scheduling systems to match the right asset to the right job without manual lookups.

**Primary users:** Dispatchers, fleet planners.

---

### 7. Configuration Templates and Modifications

A configuration template describes the standard build specification for a given model — what modifications, attachments, or accessories are expected or required. Individual assets are then assessed against those templates to determine whether they are fully documented and compliant with their specification.

Modifications can be defined once as catalog entries (e.g. "Level 3 Hydraulic Upgrade") and then recorded as actually applied to specific assets, creating a traceable configuration history.

**Primary users:** Fleet managers, compliance officers, maintenance leads.

---

### 8. Extensible Detail Tables

Some asset classes and models carry specialized data that does not apply universally — vehicle registration, emissions records, warranty documentation, purchase receipts. The system supports configurable "detail tables" that are automatically provisioned for an asset when it is created, based on what class and model it belongs to.

This means the core asset profile stays clean and universal, while domain-specific information lives in its own structured space.

**Primary users:** Fleet managers, data stewards, compliance officers.

---

### 9. Asset Images

Users can attach images to an asset to document its physical appearance, condition, or identifying features. Images are managed through the same file attachment system used elsewhere in the platform.

**Primary users:** Field operators, maintenance technicians, insurance/compliance staff.

---

## What This Application Does Not Do

- **Maintenance work orders** — tracked in the Maintenance sub-application (uses Assets as a reference).
- **Dispatch and scheduling** — tracked in the Dispatching sub-application (uses Assets for capability matching).
- **Inventory and parts** — tracked in the Inventory sub-application (parts consumption is linked to assets indirectly through maintenance and dispatch events).
- **User management and permissions** — managed by the Administration sub-application.
