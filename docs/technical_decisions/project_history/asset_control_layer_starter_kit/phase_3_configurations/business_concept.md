---
type: "Technical Decision"
title: "Phase 3 — Business Concept"
description: "Engineering defines, for each **model**, one or more **standard configurations** —."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit, phase-3-configurations]
context_tier: 2
---

# Phase 3 — Business Concept

*Business value only — no schema.*

## Capability 1: Standard build templates
Engineering defines, for each **model**, one or more **standard configurations** —
the expected build: which sub-components (child assets) it should include and
which **standardized modifications** should be applied. This captures "what a
correctly-built unit looks like."

**Persona:** Engineering / Configuration Manager.

## Capability 2: As-built documentation
For a specific **asset**, a user documents which standard configuration it was
built to, and **when** it was documented. The system tracks the asset's
**current** configuration distinctly from historical ones.

**Persona:** Build Technician, Asset Administrator.

## Capability 3: Modification catalog & actuals
The organization maintains a **catalog of defined modifications** (reusable,
coded, categorized). On an individual asset, users record the **actual
modifications** present, referencing the catalog, with when they were applied and
notes — so each unit's real deviations from standard are auditable.

**Persona:** Maintenance Planner, Build Technician.

## Capability 4: Expected vs actual
Because templates declare *expected* children and modifications while assets carry
*actual* ones, the system can show where a unit **conforms to** or **deviates
from** its standard build.

**Persona:** Quality / Compliance, Maintenance Planner.
