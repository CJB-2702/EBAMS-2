# Phase 2 — Business Concept

## What this phase delivers

**Capability: The details system runs on its own.** The core equipment area stops
"reaching out" to create detail records. Instead, when a new piece of equipment or an
equipment-model is created, the system simply **announces** that it happened; the
details system hears the announcement and does its own work, on its own schedule, a
moment later.

## Why it matters (user value, told plainly)

- **A broken detail type can never block creating equipment.** Previously, if one
  detail type misbehaved during creation, it could stop the whole equipment record from
  being saved. Now the equipment is saved first, guaranteed; the details follow. The
  person entering equipment is never held hostage by an unrelated detail bug.
- **The two systems can evolve independently.** Because the core equipment area no
  longer knows the details system exists, each can change without risking the other.
  This is the structural payoff of the whole migration.
- **Self-healing.** If details don't get created for some reason (a transient error),
  the system can safely re-run the work later and fill exactly the gaps, without
  creating duplicates.

## The trade-off, stated honestly

There is a brief window — typically imperceptible — where a freshly created piece of
equipment exists but its detail records have not yet been created. The system is built
to expect this: any screen that reads details tolerates "not ready yet," and the
fill-in is automatic and safe to repeat. This is a deliberate choice favoring *the
equipment record always succeeds* over *everything appears in the same instant*.

## Who interacts with it

- **People creating equipment / equipment-models** — benefit from creation that always
  succeeds, immune to detail-side problems.
- **Developers** — gain two systems that no longer depend on each other.
- **No screen changes yet** — provisioning behavior is the same from a user's point of
  view, minus the failure coupling.
