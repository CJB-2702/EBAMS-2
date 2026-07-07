# Canonical patterns (GoF + Fowler PoEAA)

Precise industry terms the codebase **relies on but does not encode as a suffix**.
Use these names when planning so a kit reads against the wider literature. Each
card bridges back to a house term (see [crosswalk.md](crosswalk.md)).

---

### Service Layer  *(Fowler)*
* **Summary:** A boundary of operations defining the application's transactional use cases; callers talk to it, never to the ORM directly. Here it is split by scope: a **Context** is the per-aggregate service, a **Manager** is a resource slice of it.
* **Local Reference:** [app/assets/control_layer/asset_context.py](../../../app/assets/control_layer/asset_context.py)

### Domain Model vs. Transaction Script  *(Fowler)*
* **Summary:** Two ways to hold business logic. A **Transaction Script** runs one procedure per request (our **Handler**); a **Domain Model** spreads behavior across collaborating objects keyed to the domain (our **Context** + **Manager** mesh). This project favors the Domain Model and keeps models themselves logic-free.
* **Local Reference:** [app/events/control_layer/handlers/event_handler.py](../../../app/events/control_layer/handlers/event_handler.py) (script) vs. [app/events/control_layer/event_context.py](../../../app/events/control_layer/event_context.py) (model).

### Data Transfer Object / Value Object  *(Fowler / DDD)*
* **Summary:** A simple, behavior-light carrier of data across a boundary; a Value Object is additionally immutable and compared by value. Our **Structs** are read-side DTOs; small typed records like `*Result` and `AssignmentToggle` are value-style carriers.
* **Local Reference:** [app/detail_extensions/control_layer/adapters/enablement_assignment_adaptor.py](../../../app/detail_extensions/control_layer/adapters/enablement_assignment_adaptor.py) — `AssignmentToggle`.

### Aggregate / Aggregate Root  *(DDD)*
* **Summary:** A cluster of objects treated as one consistency boundary, addressed through a single **root** entity. Every house **Context** is keyed to exactly one aggregate root id — that is the unit a write transaction commits.
* **Local Reference:** [app/administration/control_layer/data_ownership/data_ownership_context.py](../../../app/administration/control_layer/data_ownership/data_ownership_context.py)

### Repository / Row Data Gateway  *(Fowler)*
* **Summary:** A mediator that hides query construction behind a collection-like read interface. This project **deliberately omits** a Repository layer: a **Struct** loads its own rows via `from_components()` and a **Context** consumes it via `from_struct()`, so reads stay explicit and screen-shaped rather than generic.
* **Local Reference:** [app/administration/control_layer/permissions/role_struct.py](../../../app/administration/control_layer/permissions/role_struct.py)

### Facade  *(GoF)*
* **Summary:** One simplified interface in front of a complex subsystem. A **Context** is a facade: callers get `context.add_comment(...)` instead of orchestrating handlers, guards, and querysets themselves.
* **Local Reference:** [app/events/control_layer/event_context.py](../../../app/events/control_layer/event_context.py)

### Command  *(GoF)*
* **Summary:** Encapsulates a request as an object with a single `run`/`create` entrypoint and a result, decoupling caller from execution. Our **Handlers** are commands; their `*Result` records carry the outcome.
* **Local Reference:** [app/events/control_layer/handlers/comment_handler.py](../../../app/events/control_layer/handlers/comment_handler.py)

### Strategy  *(GoF)*
* **Summary:** A family of interchangeable algorithms behind one interface, selected at runtime. The codebase favors **composition over inheritance**, using inheritance only for such strategy interfaces — the **Guard** family is the main example.
* **Local Reference:** [app/assets/control_layer/configurations/applicability/applicability_policy.py](../../../app/assets/control_layer/configurations/applicability/applicability_policy.py)

### Specification  *(Fowler)*
* **Summary:** A predicate object that answers "does this candidate satisfy the rule?", composable and reusable across check and selection. Our **Validators** and read-only **Policies** are specifications over a payload or aggregate.
* **Local Reference:** [app/detail_extensions/control_layer/guards/enablement_assignment_guard.py](../../../app/detail_extensions/control_layer/guards/enablement_assignment_guard.py) — `AssignmentValidator`.

### State  *(GoF)*
* **Summary:** Localizes status-dependent behavior so an object's legal transitions are explicit rather than scattered `if status ==` checks. The house **StateMachine** guard is the intended home for this; currently *reserved* — no live implementation.
* **Local Reference:** *reserved.*

### Observer / Domain Event  *(GoF / Fowler)*
* **Summary:** Publishers emit events; subscribers react without the publisher knowing them. Implemented with Django signals: a creation event fires, and an **Orchestrator** subscribed to it schedules follow-on work post-commit.
* **Local Reference:** [app/detail_extensions/control_layer/detail_extension_creation_orchestrator.py](../../../app/detail_extensions/control_layer/detail_extension_creation_orchestrator.py)

### Registry  *(Fowler)*
* **Summary:** A well-known object others use to find services or descriptors, avoiding hard-wired lookups. The extension system resolves string keys to descriptors and validates the registry's integrity through one such object.
* **Local Reference:** [app/detail_extensions/control_layer/guards/extension_registry_guard.py](../../../app/detail_extensions/control_layer/guards/extension_registry_guard.py) — `ExtensionRegistryValidator`.
