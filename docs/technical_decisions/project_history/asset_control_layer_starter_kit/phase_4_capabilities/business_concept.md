# Phase 4 — Business Concept

*Business value only — no schema.*

## Capability 1: Capability catalog
The organization maintains a catalog of **capabilities** — discrete things an
asset can do or provide (e.g. "4WD", "300A welding output", "potable water").
Each is named and coded for consistent reference across the fleet.

**Persona:** Capability/Fleet Administrator.

## Capability 2: Layered defaults (class → model → asset)
Capabilities are declared at the level where they make sense and **flow
downward**: a capability common to an entire **asset class** is declared once;
**models** of that class inherit it; individual **assets** inherit their model's
capabilities when registered. Administrators avoid re-declaring the same
capability on every unit.

**Persona:** Capability Administrator, Asset Administrator.

## Capability 3: Per-asset reality
An individual **asset** can have its capabilities tuned — adding, deactivating,
or annotating — to reflect its real, current state (a unit whose welder is
removed). The per-asset layer is the authoritative, **auditable** truth used by
downstream workflows (e.g. dispatching).

**Persona:** Field Technician, Maintenance Planner.

## Capability 4: Readiness at a glance
Each asset surfaces a **capability status** so users can quickly judge what a unit
is currently able to do without inspecting every individual capability record.

**Persona:** Dispatcher, Planner (read).
