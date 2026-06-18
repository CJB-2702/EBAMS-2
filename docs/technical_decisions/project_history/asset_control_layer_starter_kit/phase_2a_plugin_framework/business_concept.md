# Phase 2a — Business Concept

*Business value only — no schema, no class names.*

## Capability 1: Pluggable asset information modules
Different kinds of assets need different structured information. A light vehicle
needs a registration and a smog record; a generator needs neither. Rather than
baking every possible information type into the asset itself, the system supports
**information modules ("plugins")** that can be switched on for the kinds of assets
that need them. Each module is a self-contained unit with its own set of fields.

**Persona:** Asset Administrator (decides which modules exist and where they apply).

## Capability 2: Configure modules per asset class and per model
Administrators declare, **per asset class**, which modules every asset of that
class should carry — and **per model**, any extra modules specific to that model.
Model-level technical modules (specs, emissions) are declared **per asset class**
of the model. When an asset or model is registered, exactly those modules appear,
pre-created and ready to fill in. No bespoke setup per individual unit.

**Persona:** Asset Administrator (configures), Field Technician (fills in).

## Capability 3: Modules appear automatically at registration
The moment an asset (or model) is created, the system looks up which modules are
enabled for it and provisions them in one atomic step alongside the asset itself.
If creation fails, nothing is left half-provisioned. If a module is enabled later,
the same provisioning can safely backfill it without creating duplicates.

**Persona:** All creators of assets/models.

## Capability 4: Single-record vs. history modules
Some modules hold a **single current record** (the current registration); others
accumulate a **history** (every smog test over the years). Whether a module is
single or repeating is a fixed property of the module itself, so it behaves the
same everywhere it is enabled.

**Persona:** Asset Administrator.

## Capability 5: One gathered view of an asset's modules
A user looking at an asset (or model) can retrieve **all** of its module records
gathered together, regardless of how many different module types it carries —
without the system needing a separate screen per module type.

**Persona:** All viewers. *(The visual card for each module is a later phase; this
phase delivers the gathered data, not the UI.)*

## Capability 6: New modules without disturbing existing assets
A new kind of module can be introduced and enabled for a class or model without
reworking how assets themselves are defined. The asset does not have to "know
about" every module type in advance — it simply carries whichever modules are
enabled for it.

**Persona:** Asset Administrator, and the engineering team extending the system.
