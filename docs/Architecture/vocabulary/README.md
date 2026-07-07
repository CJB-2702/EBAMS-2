# Architecture Vocabulary — Tier 3 (add-on-demand)

A thin cross-walk between **this project's house vocabulary** (the class-suffix
naming in [oop_control_patterns.md](../oop_control_patterns.md)) and the
**canonical pattern names** used by *Refactoring Guru* (Gang of Four) and Martin
Fowler's *Patterns of Enterprise Application Architecture* (PoEAA).

It exists to do two jobs:

1. **Expand planning vocabulary** — name a shape precisely before building a kit.
2. **Feed a Pattern-Suggestion Agent** — crisp, low-noise, ingestible cards.

---

## Tier & loading rule

This folder is **Tier 3 (Targeted)** per [Context_Scaling.md](../../Context_Scaling.md):
**never scanned by default, injected on demand** when planning or naming new
control-layer code. It is a reference shelf, not a routed spec. Keep it thin —
when in doubt, link out to the Tier 2 spec instead of re-explaining it.

## How to read it

| File | Use it when you want… |
| :--- | :--- |
| [crosswalk.md](crosswalk.md) | The one-screen table: house suffix ↔ canonical name ↔ local file. Start here. |
| [control_layer_patterns.md](control_layer_patterns.md) | Definitions of **our** suffixes (Struct, Context, Factory, Handler, Manager, Guard family, Narrator, Adaptor, Orchestrator). |
| [enterprise_patterns.md](enterprise_patterns.md) | Definitions of **canonical** GoF / PoEAA terms the codebase leans on but does not suffix (Service Layer, Domain Model, DTO, Aggregate Root, Repository, Facade, Command, Strategy, Specification, State, Observer, Registry). |

## Card format

Every term uses the same shape so an agent can parse it:

> ### Term
> * **Summary:** 2–3 sentence definition.
> * **Local Reference:** `path/to/file.py` — closest demonstration in this repo.

## Sources

- Refactoring Guru — design-pattern catalog: <https://refactoring.guru/design-patterns/catalog>
- Martin Fowler — *Patterns of Enterprise Application Architecture*.

## Maintenance

Local references are sampled from the live control layers. Re-confirm a path with
the project's own context tool before trusting it:

```bash
python3 dev_tools/get_classes_and_descriptions.py --path app/<app>/control_layer
```

A term with **no** live example is marked *reserved* — the vocabulary exists, the
implementation does not yet.
