# Object-oriented control layer patterns

This document describes **common shapes** in the control layer so that:

- A new contributor can **predict the role of a class from its filename** before opening it.
- A new feature has a **near-mechanical playbook**: define a **Struct**, add **Context** methods, register a **Handler** or **Manager** when needed, gate with a **Guard** (a **Policy**, **Validator**, or **StateMachine**), narrate with **Narrator**, expose through **Adaptor**, and call from a **thin route**.

**Naming:** Prefer **class suffix vocabulary** (see below) and **long, explicit class and file names** that state what something is. **Do not use acronyms** in type or module names.

For verbatim class shapes and module skeletons see [Examples/control_layer_class_skeletons.md](Examples/control_layer_class_skeletons.md).

**Add-on-demand (Tier 3):** for canonical GoF / Fowler-PoEAA names behind these suffixes, load [vocabulary/](vocabulary/README.md) — a thin cross-walk reference, never scanned by default.

---

## 1. Class suffix vocabulary as a navigational aid

Class names follow a fixed suffix vocabulary. Reading a filename tells you the shape and role of the class inside before you open the file.

| Suffix | Typical role |
| :--- | :--- |
| **Struct** | Aggregated read model for one context: ids resolved, data loaded, `to_dict()` (or similar) for rendering. No business mutations. |
| **Context** | Entry point for control logic around one aggregate id (or key): loads a Struct, delegates to Managers and Handlers, owns the "story" of a workflow. |
| **Factory** | Stateless creation of **root** items (no parent); class methods; often returns a Struct or model instance. |
| **BulkFactory** | Batch creation; returns **only the highest-level created items** (not nested Structs). |
| **Handler** | Single-task specialist: one complex workflow step or command. |
| **Manager** | Domain or resource generalist: a stable sub-area of a Context (lifecycle, grouping of related operations). |
| **FactoryHandler** | Optional: when creation logic is heavy, group it behind one handler invoked from Context. |
| **Policy** | **Guard** subtype — authorization or rule gate: "may this happen?" |
| **Validator** | **Guard** subtype — input or invariant checks at boundaries. |
| **Narrator** | Human-facing explanation, audit text, or comment text for logs and UI. |
| **Builder** | Stepwise construction for polymorphic children or workflows. |
| **StateMachine** | **Guard** subtype — explicit transitions for status-driven entities. |
| **Service** | Cross-cutting or integration operations (use sparingly; prefer Context + Manager). |
| **Adaptor** | Maps portal JSON, forms, or external payloads into **structured** types the control layer understands. |
| **Orchestrator** | Coordinates multiple steps across boundaries when a Context would be the wrong scope (rare). |

### Guard classes (Policy, Validator, StateMachine)

**Guard** is the shared **category** for types that **constrain** control flow: who may act (**Policy**), whether inputs and invariants hold (**Validator**), and which status transitions are legal (**StateMachine**). All three remain distinct **class suffixes** in code; the **Guard** name is how you group them in folders, reviews, and filenames.

**File naming:** `<class_name_stem>_guard.py` — the stem is the long, explicit snake_case name of the guard (usually aligned with the class name without the `Policy`, `Validator`, or `StateMachine` suffix). Example: `maintenance_event_close_guard.py` for a class such as `MaintenanceEventClosePolicy`.

**Docstring (required):** The **module docstring** or the **primary class docstring** must state:

1. **Which guard type** this is — Policy, Validator, or StateMachine.
2. **What** it guards (subject, aggregate, or transition), in one or two short sentences.

---

## 2. Pattern summaries

### Struct
**File naming:** `<item_name>_struct.py`. **Purpose:** Always loads the base row, validates it exists, optionally eager-loads related slices via `eager=True` or lazy loaders. Provides `to_dict()`. **Does not perform actions** — collects data only.

**Build structs proactively — presentation need alone justifies one.** A Struct does **not** require a control-layer (write or domain) consumer to earn its place. Whenever the presentation layer has an obvious need to **cluster related rows for a screen** — a detail page, a panel, a timeline, a breadcrumb tree — prefer creating a dedicated `*Struct` read model over assembling ad-hoc queries inside the view, **even if nothing in the control layer calls it yet**. Read models are cheap, testable, and keep views thin; we would rather one already exist than have a view grow its own query soup. Prefer **composing** smaller structs into an aggregate (e.g. an `AssetThreeSixtyStruct` that gathers the capability, configuration, hierarchy, and timeline structs) for whole-page reads. When a struct must stay ignorant of another app (a one-way dependency, e.g. assets ↔ extensions), it composes only its own app's structs and leaves the foreign slice to an HTMX panel URL rather than importing across the boundary.

### Context
**Purpose:** All control logic flows through a Context tied to a natural key (usually an id). Accepts an id and an optional `eager` flag. Loads the appropriate Struct as the single source of structured data for the session. Prefer domain verbs (`MaintenanceEventContext(id).add_comment(data)`) over raw ORM in callers. Contexts expose `from_struct()` so callers who already built the Struct can skip the usual init path and avoid duplicate queries.

### Handlers versus Managers

| | **Handler** | **Manager** |
| :--- | :--- | :--- |
| **Scope** | **Single task** or complex step (one command, one conversion, one approval flow). | **Broader sub-domain** of the same aggregate (e.g. "everything about actions" for one event). |
| **Lifecycle** | Often created per call or used as a **named class** with a `create` / `run` entrypoint. | **Stable** collaborator on the Context: same aggregate, many operations over time. |
| **Analogy** | Specialist | Generalist for one resource slice |

**Context Managers** (sub-managers on Context): when a Context grows too large, group related operations and delegate to a sub-manager that receives the Context's Struct (or the Context itself). Prefer Managers as properties on the Context over `get_manager()`-style functions.

### Factory and BulkFactory
**Factory:** stateless, class methods only, used for creating complex **root** items that have no parent. Often returns Structs, not loose dicts. Typical flow: entrypoint → Adaptor → Factory.

**BulkFactory:** batch creation; returns **only a list of the highest-level items** created (e.g. events), not nested Structs for every child.

---

## 3. Engineering principles (control layer)

- **Readability over brevity.** Long, explicit, **keyword-only** signatures over compact positional ones.
- **Composition over inheritance.** Inheritance is for **strategy interfaces**, not for reusing implementation details.
- **Convention over configuration.** Naming conventions replace frameworks; disciplined imports and import-time registries only where needed.
- **Explicit over magical.** No metaclass tricks, no implicit transactions, no hidden side effects on attribute setters.
- **Decomposition over consolidation.** Many small files over few large ones. When in doubt, **split**.
- **Read models are first-class and proactive.** Build a **Struct** whenever a screen needs clustered rows, even with **no** write-side or domain-layer caller. A presentation-layer use case alone justifies a read model — don't wait for a control-layer consumer to materialize first.
- **Domain verbs over CRUD verbs.** Methods are named after **business actions**, not database operations.
- **Tech debt is greppable.** Undesired shortcuts use **`# DELIBERATE ANTI-PATTERN`** blocks (with context), not silent acceptance.
- **One transaction per workflow.** Outer composition decides; inner calls cooperate with **`commit=False`** when appropriate.
- **No magic strings.** Status names, outcome types, and locked fields live in **class-level constants** and **frozen sets**.
- **Defensive at the edges, trusting in the middle.** Routes sanitize input and catch domain exceptions; once data is inside a **Context**, it is **trusted** for that operation.

---

## 4. Playbook for a new feature (checklist)

1. **Struct** — Define `<thing>_struct.py` with base row guaranteed, optional eager/lazy slices, `to_dict()`.
2. **Context** — Wire id + `from_struct()`, route all mutations through domain verbs.
3. **Manager** or **Handler** — Add a Manager for a sub-area of behavior; add a Handler for one heavy step.
4. **Guard** — Add a **Policy**, **Validator**, or **StateMachine** in `<name>_guard.py`; gate mutations and sensitive reads.
5. **Narrator** — Audit and user-visible strings where needed.
6. **Adaptor** — Map HTTP/portal payloads to structured constructor inputs at the boundary.
7. **Thin route** — Parse request, call Context, return response; **no writes** outside the control layer (see [layer_rules.md](layer_rules.md)).
