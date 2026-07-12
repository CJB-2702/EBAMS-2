---
type: Vocabulary Reference
title: Vocabulary Cross-Walk
description: One-row-per-term mapping between house suffixes and canonical pattern names.
tags: [architecture, vocabulary, patterns, crosswalk]
---

# Cross-walk: house suffix ↔ canonical pattern

One row per term. **House** = our class-suffix vocabulary. **Canonical** = the
nearest Gang-of-Four (Refactoring Guru) or Fowler PoEAA name. Use this to
translate in either direction; cards with fuller definitions live in
[control_layer_patterns.md](control_layer_patterns.md) and
[enterprise_patterns.md](enterprise_patterns.md).

| House suffix | Canonical pattern | Source | One-line intent | Local reference |
| :--- | :--- | :--- | :--- | :--- |
| **Struct** | Data Transfer Object / read model | Fowler | Eager-loaded, screen-shaped read aggregate; no writes. | [event_detail_struct.py](../../../app/events/control_layer/domain_structs/event_detail_struct.py) |
| **Context** | Facade + Service Layer (per aggregate) | GoF + Fowler | Single id-keyed entry point for every write on one aggregate. | [event_context.py](../../../app/events/control_layer/event_context.py) |
| **Factory** | Factory Method | GoF | Stateless creation of *root* objects (no parent). | [capability_factory.py](../../../app/assets/control_layer/capabilities/capability_factory.py) |
| **BulkFactory** | Factory Method (batch) | GoF | Batch create; returns only top-level items. | *reserved* (bulk-read analog: [event_super_struct.py](../../../app/events/control_layer/domain_structs/event_super_struct.py)) |
| **Handler** | Command / Transaction Script | GoF + Fowler | One state-changing task or heavy step. | [event_handler.py](../../../app/events/control_layer/handlers/event_handler.py) |
| **Manager** | Service Layer (resource slice) | Fowler | Stable sub-domain of a Context; many ops over time. | [configuration_manager.py](../../../app/assets/control_layer/configurations/configuration_manager.py) |
| **Policy** (Guard) | Strategy / Specification | GoF + Fowler | Authorization gate: "may this actor do this?" | [thread_policy.py](../../../app/events/control_layer/policies/thread_policy.py) |
| **Validator** (Guard) | Specification | Fowler | Input & invariant checks at the boundary. | [enablement_assignment_guard.py](../../../app/detail_extensions/control_layer/guards/enablement_assignment_guard.py) |
| **StateMachine** (Guard) | State | GoF | Legal status transitions for an entity. | *reserved* (no live example) |
| **Narrator** | Presenter (humanizer) | (no exact GoF/Fowler) | Renders audit / human-facing text for logs & UI. | [asset_event_narrator.py](../../../app/assets/control_layer/narrators/asset_event_narrator.py) |
| **Adaptor** | Adapter | GoF | Maps external payloads (forms, JSON) → structured inputs. | [asset_create_adaptor.py](../../../app/assets/control_layer/adapters/asset_create_adaptor.py) |
| **Orchestrator** | Mediator / Saga (Process Manager) | GoF + Fowler-adjacent | Coordinates steps across boundaries when a Context is wrong scope. | [detail_extension_creation_orchestrator.py](../../../app/detail_extensions/control_layer/detail_extension_creation_orchestrator.py) |

**Reading the boundary:** a request enters a thin route → an **Adaptor** structures
the payload → a **Factory** (create) or **Context** (mutate) takes over → it leans
on **Managers**/**Handlers**, gated by **Guards**, narrated by a **Narrator**, with
read data supplied by **Structs**. Cross-aggregate fan-out escalates to an
**Orchestrator**.
