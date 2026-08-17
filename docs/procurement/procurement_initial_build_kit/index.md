---
okf_version: "0.1"
type: "Index"
title: "Procurement Current-State Kit"
description: "A starter kit reverse-engineered from the built procurement application: what it does, who it serves, its domain model, the policies of each subsystem, the graph engine, and its page set."
tags: [starter-kit, procurement, current-state, index, okf]
context_tier: 1
personas: [backend, business, frontend]
---

# Procurement Current-State Kit

**This kit describes the procurement application as it actually exists in code, today.**

It is written backwards from the usual direction. A starter kit normally precedes a
build; this one was reconstructed from the build, because the accumulated planning
documents under `docs/procurement/` had been revised, superseded, and contradicted
often enough that no single document could be trusted to say how the system works.

## Provenance — what this was written from

**Sources used:**

- Every model, enum, guard, manager, handler, factory, policy, and entrypoint under
  [app/procurement/](../app/procurement/), read in full.
- The mirror surface at [app/inventory/presentation_layer/entrypoints/shipments.py](../app/inventory/presentation_layer/entrypoints/shipments.py).
- Live introspection of the Django models for the field lists and enum values.
- One historical document: `docs/procurement/history/demand_graph_kit_outdated/all_statuses_review.md`,
  used only as a cross-check against the code and corrected where it disagreed.

**Deliberately not used:** anything else under `docs/procurement/`.

Where a docstring in the code cites a decision id (`D42`, `D90`, …), that citation is
reproduced here as a pointer to intent, not as a claim that the referenced document is
still accurate. **The code is the authority in this kit.** Any statement here that
disagrees with `app/procurement/` is a bug in this kit.

## How to read it

| Document | Answers |
| :--- | :--- |
| [questionnaire.md](questionnaire.md) | The standard 20-question kit questionnaire, answered from the built system. The fastest way to absorb the whole application. |
| [business_concept_definition.md](business_concept_definition.md) | What the application does for people, in domain language, with no tables named. |
| [domain_model.md](domain_model.md) | Every table, every field that matters, every relationship, and the entity diagram. |
| [systems/demand_system.md](systems/demand_system.md) | The need side: four state axes, the journal, the three gates, completion. |
| [systems/purchasing_system.md](systems/purchasing_system.md) | The order side: two axes, allocation policy, propagation, line editing, cost. |
| [systems/shipment_system.md](systems/shipment_system.md) | The arrival side: what physically turned up, allocation to orders, acceptance. |
| [systems/pricing_system.md](systems/pricing_system.md) | Price observations: what a price is here, and why it is never a column on a part. |
| [systems/graph_system.md](systems/graph_system.md) | The GraphSummary engine: clusters, merge/split, the derived and human columns. |
| [status_reference.md](status_reference.md) | Every status axis in the application, in one place, verified against the enums. |
| [control_layer_map.md](control_layer_map.md) | Every control-layer class, what it owns, and what is the sole writer of what. |
| [page_set.md](page_set.md) | Every route, what each page is for, and what it is deliberately not for. |

## Scope of the application

**In:** part demands, purchase orders and their lines, demand↔order allocation,
shipments and arriving lines, arrival↔order allocation, acceptance/inspection,
vendors, price observations, and the graph clustering that ties all of it together.

**Out:** intake. Put-away, bins, storerooms, stock levels, and issuance mechanics
belong to the Inventory build. The last verb procurement owns is `accept`.
`ShipmentLine.quantity_accepted` is exactly where the line is drawn, and
`IssuanceState` is a surface procurement exposes for Inventory to write through
`PartDemandContext.record_issuance()` — procurement never computes it.
