# Architecture — Tier 1 Anchor

This file is the **concept anchor** for project architecture. It states the rules of engagement for backend code: how sub-applications are laid out, how layers depend on one another, where state changes are allowed, and the naming vocabulary that lets a reader predict a class's role from its filename. Detail lives in the Tier 2 files below.

---

## Core ideas

- **Sub-applications are layered.** Every Django app under `app/` is split into a presentation layer (entrypoints, search, tools), a control layer (writes, adapters, domain structs), models, and templates. The shape is identical across apps so a developer can find anything by analogy.
- **Dependencies flow downward.** Presentation may import from control; control may import from models; models import from nothing above the ORM. Lateral and upward imports are bugs, not preferences.
- **Reads vs writes are not symmetric.** Simple reads (≤ 2 tables) may live in entrypoints. **Every write — create, update, delete, m2m mutate — flows through the control layer.** There is no "small write that's fine inline."
- **Class shape is encoded in the suffix.** Struct, Context, Factory, Handler, Manager, Policy, Validator, StateMachine, Narrator, Adaptor, Orchestrator. The suffix is a contract; reading a filename should tell you what the class does before you open it.
- **Models hold schema, never logic.** Constraints, indexes, mixins, declarative metadata only. Workflow rules belong in handlers, contexts, and guards.
- **Endpoints are thin.** Their job is to parse the request, call search or the control layer, and return a response. Templates choose density and HTMX variants via a single `format=` query parameter — never via parallel URLs.
- **Read models (Structs) are built proactively.** A `*Struct` that clusters related rows for a screen is worth creating on **presentation need alone** — even when no control-layer or domain-layer code consumes it yet. Prefer a dedicated read model (and aggregate structs composed of smaller ones) over query soup in a view. See [Architecture/oop_control_patterns.md](Architecture/oop_control_patterns.md).

---

## Sub-specifications

| Topic | File |
| :--- | :--- |
| Sub-app folder layout and layer responsibilities | [Architecture/overview.md](Architecture/overview.md) |
| Reads vs writes; what may run in an entrypoint | [Architecture/layer_rules.md](Architecture/layer_rules.md) |
| Class-suffix vocabulary and the new-feature playbook | [Architecture/oop_control_patterns.md](Architecture/oop_control_patterns.md) |
| Model naming, audit columns, abstract bases, PK choice | [Architecture/model_patterns.md](Architecture/model_patterns.md) |
| OOP endpoint design, collection vs detail, `format=` contract | [Architecture/endpoint_patterns.md](Architecture/endpoint_patterns.md) |
| HTMX conventions, F5 rule, CSRF, `hx-select` defaults, session drafts | [Architecture/htmx_patterns.md](Architecture/htmx_patterns.md) |
| Fixture placement, audit-field handling, prod policy | [Architecture/seeding.md](Architecture/seeding.md) |
| Engineering principles and stack choices | [Architecture/standards.md](Architecture/standards.md) |
| Testing conventions | [Architecture/tests.md](Architecture/tests.md) |

---

## Reference directionality

This anchor references **only** files inside `Architecture/`. Tier 2 files inside that folder may reference each other and Tier 3 examples within `Architecture/Examples/`, but never back upward. The persona slash commands (see [Context_Scaling.md](Context_Scaling.md)) load this anchor plus the appropriate Tier 2 subset; a developer should never have to read this file *and* a peer-tier anchor (e.g. `UX_UI.md`) for one task — the relevant cross-cutting rules are summarised here.
