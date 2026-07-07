# House control-layer patterns

Definitions of **our own** class-suffix vocabulary, each anchored to a live file.
Canonical equivalents are in parentheses; see [crosswalk.md](crosswalk.md) for the
full mapping and [enterprise_patterns.md](enterprise_patterns.md) for the canonical
terms themselves. Authoritative suffix rules:
[oop_control_patterns.md](../oop_control_patterns.md).

---

### Struct  *(≈ Data Transfer Object / read model — Fowler)*
* **Summary:** An eager-loaded read aggregate shaped for one screen: ids resolved, related rows fetched in a known query count, `to_dict()` for rendering, **no mutations**. Built proactively — presentation need alone justifies one. Compose smaller Structs into a super-struct for whole-page reads.
* **Local Reference:** [app/events/control_layer/domain_structs/event_detail_struct.py](../../../app/events/control_layer/domain_structs/event_detail_struct.py) — event + comments + attachments in 3 queries.

### Context  *(≈ Facade + per-aggregate Service Layer — GoF / Fowler)*
* **Summary:** The single entry point for control logic around one aggregate id. It loads the relevant Struct, exposes **domain verbs** (`add_comment`), and routes every write through itself. `from_struct()` lets callers reuse an already-built Struct without re-querying.
* **Local Reference:** [app/events/control_layer/event_context.py](../../../app/events/control_layer/event_context.py)

### Factory / BulkFactory  *(≈ Factory Method — GoF)*
* **Summary:** Stateless creation of **root** objects (no parent), class-methods only, typically returning a Struct. **BulkFactory** is the batch form and returns only the highest-level created items, not nested child Structs.
* **Local Reference:** [app/assets/control_layer/capabilities/capability_factory.py](../../../app/assets/control_layer/capabilities/capability_factory.py). *(BulkFactory: reserved — no live example.)*

### Handler  *(≈ Command / Transaction Script — GoF / Fowler)*
* **Summary:** A single-task specialist owning one complex step or command (create, convert, approve) and usually returning a small `*Result`. Contexts delegate single-row and heavy operations to Handlers.
* **Local Reference:** [app/events/control_layer/handlers/event_handler.py](../../../app/events/control_layer/handlers/event_handler.py)

### Manager  *(≈ Service Layer, resource slice — Fowler)*
* **Summary:** A generalist for one sub-domain of an aggregate — a stable collaborator on the Context that performs many related operations over time (a lifecycle, a catalog). Prefer Managers as properties on the Context over `get_manager()` helpers.
* **Local Reference:** [app/assets/control_layer/configurations/configuration_manager.py](../../../app/assets/control_layer/configurations/configuration_manager.py)

### Guard family — Policy · Validator · StateMachine  *(≈ Strategy / Specification / State — GoF / Fowler)*
* **Summary:** The shared category for types that **constrain** control flow: **Policy** answers "may this actor act?" (authorization), **Validator** checks inputs and invariants at the boundary, **StateMachine** enforces legal status transitions. All live in `*_guard.py` files whose docstring states which guard type they are.
* **Local Reference:** [app/detail_extensions/control_layer/guards/enablement_assignment_guard.py](../../../app/detail_extensions/control_layer/guards/enablement_assignment_guard.py) — Policy + Validator together; Policy alone: [app/events/control_layer/policies/thread_policy.py](../../../app/events/control_layer/policies/thread_policy.py). *(StateMachine: reserved.)*

### Narrator  *(≈ Presenter / humanizer — no exact canonical)*
* **Summary:** Turns domain events into human-facing strings: audit lines, log text, UI comments. A read-only formatter — it owns wording, never state.
* **Local Reference:** [app/assets/control_layer/narrators/asset_event_narrator.py](../../../app/assets/control_layer/narrators/asset_event_narrator.py)

### Adaptor  *(≈ Adapter — GoF)*
* **Summary:** Maps an external payload (HTML form fields, portal JSON) into the **structured** types the control layer expects, isolating boundary-parsing from domain logic. Typical flow: thin route → Adaptor → Factory/Context.
* **Local Reference:** [app/detail_extensions/control_layer/adapters/enablement_assignment_adaptor.py](../../../app/detail_extensions/control_layer/adapters/enablement_assignment_adaptor.py) — parses a checkbox grid into typed toggles.

### Orchestrator  *(≈ Mediator / Saga / Process Manager — GoF / Fowler-adjacent)*
* **Summary:** Coordinates a multi-step workflow that spans **several aggregates or apps**, where a single Context would be the wrong scope. Often signal-driven and post-commit. Rare by design — reach for it only when no one Context owns the whole story.
* **Local Reference:** [app/detail_extensions/control_layer/detail_extension_creation_orchestrator.py](../../../app/detail_extensions/control_layer/detail_extension_creation_orchestrator.py) — listens to owner-creation signals, schedules provisioning.
