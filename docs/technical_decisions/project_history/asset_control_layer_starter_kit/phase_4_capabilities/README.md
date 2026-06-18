# Phase 4 — Capabilities

What an asset *can do*. A three-layer template/instance system (class → model →
asset) with a copy-on-create cascade. Built last because it carries the heaviest
creation fan-out and benefits from a settled orchestrator (P1), details (P2), and
eventing.

## Goal

Manage the capability catalog and the three assignment layers, and copy template
capabilities down to new models/assets at creation time via the Phase 1
orchestrator seam.

## Core concepts (4 tables, 3 layers + catalog)

- **`CapabilityDefinition`** — the catalog (coded, named capabilities).
- **`AssetClassCapability`** — template layer: capabilities available to a class.
- **`ModelCapability`** — capabilities for a model (was `MakeModelCapability`).
- **`AssetCapability`** — per-asset capabilities (the event-tracked, real ones),
  with `notes` and `is_active`.

## The copy-on-create cascade (old `CapabilityFactory`)

```
AssetClassCapability  ──copied to──▶  ModelCapability  ──copied to──▶  AssetCapability
   (class template)                      (on model create)               (on asset create)
```

When a model is created, it inherits its class's capabilities; when an asset is
created, it inherits its model's capabilities. This is the automated flow the old
`CapabilityFactory` owned — and it plugs into the P1 orchestrator's **P4
extension point**.

## In scope

- `CapabilityManager` — CRUD/query across all four tables.
- `CapabilityFactory` — the copy-on-create cascade.
- Wire model-create and asset-create extension points.
- `Asset.capability_status` maintenance (the cached string on Asset).

## Out of scope

Dispatching's consumption of capabilities (separate app/module).

## Dependencies

- **Phase 1** (orchestrator + model factory seams) — required.
- Phases 2–3 assumed present (ordering, not hard dependency).

## Exit criteria

- [ ] Creating a model copies its class's active capabilities to `ModelCapability`.
- [ ] Creating an asset copies its model's active capabilities to `AssetCapability`,
      inside the creation transaction.
- [ ] Capability CRUD across all four layers goes through the control layer.
- [ ] `Asset.capability_status` is recomputed when asset capabilities change.
- [ ] Capability changes on an asset are auditable (events via Phase 1 seam).
