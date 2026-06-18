# Phase 2b — Business Concept

*Business value only — no schema, no class names.*

## Capability 1: Vehicle registration module
Road-going assets carry a **registration** module: plate number, registration
expiry, jurisdiction, and VIN. Enabled for the vehicle asset classes, it appears
automatically when such an asset is registered, ready for a technician to fill in.

**Persona:** Field Technician (fills in), Asset Administrator (enables it).

## Capability 2: Smog test history module
Emissions-tested assets accumulate a **history of smog tests** — each with its test
date, result, station, certificate, and expiry. Unlike a single current
registration, this module keeps **every** record over the asset's life, so the
compliance history is preserved.

**Persona:** Field Technician, Compliance Reviewer.

## Capability 3: Model emissions module
A model carries an **emissions specification** — standard, tier, CO₂ rating,
certified year — entered once on the model and inherited by every asset of that
model, avoiding re-entry per unit.

**Persona:** Asset Administrator, Maintenance Planner.

## Capability 4: The full detail set runs on the plugin framework
With these three added to the purchase-info and model-spec modules from the
framework phase, **all** the original structured-detail types are now delivered as
interchangeable modules. An administrator enabling or introducing a module never
touches how assets themselves are defined — the value proven here is that the
catalog of modules grows independently of the asset.

**Persona:** Asset Administrator, engineering team.
