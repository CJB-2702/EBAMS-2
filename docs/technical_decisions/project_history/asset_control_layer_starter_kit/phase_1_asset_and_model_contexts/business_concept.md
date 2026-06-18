# Phase 1 — Business Concept

*Per [`docs/starter_kit_process/how_to_business_concept_definition_document.md`](../../docs/starter_kit_process/how_to_business_concept_definition_document.md).
User value and workflows only — no schema here.*

## Capability 1: Model Catalog
Asset managers maintain a catalog of **asset models** (the product definitions —
e.g. "CAT 320 Excavator, rev B"). Each model belongs to an **asset class**, is
attributed to one or more **manufacturers** (one primary), declares the units of
its meters, and may be a **revision** of a base model. Creating a model records
a "Model Created" event on the timeline.

**Persona:** Fleet/Asset Administrator.

## Capability 2: Asset Registration
Users register individual **assets** (physical units) against a model. Each asset
gets a unique serial number, an owning **data domain** (which governs who can see
it), a status, and — automatically — a **photo gallery** and a **documentation**
thread for images and files. Registration records an "Asset Created" event.

**Persona:** Asset Administrator, Field Technician (read).

## Capability 3: Asset Hierarchy
Assets can be assembled into **parent/child trees** (a generator mounted on a
trailer; components inside a machine). The system tracks each asset's parent,
its root, and its depth, and keeps an **audit trail** of every re-parenting.

**Persona:** Asset Administrator.

## Capability 4: Meter Tracking
Assets carry up to four **meters** (hours, miles, cycles…). Users record new
readings; the system keeps the current value on the asset and a full **reading
history** with timestamps and source.

**Persona:** Field Technician, Maintenance Planner.

## Capability 5: Lifecycle Timeline
Key changes to an asset — creation, and edits to its name, serial, owning domain,
or model — are written to the asset's **event timeline** so its history is
auditable over its lifespan. Meter changes are always captured as history.

**Persona:** All — this is the audit backbone ("the core of the application").

## Capability 6: Class Consistency
When an administrator changes which **class** a model belongs to, every asset of
that model is kept consistent automatically, so reporting and access rules that
depend on class never drift.

**Persona:** Asset Administrator (operation is usually invisible to end users).
