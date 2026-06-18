# Phase 1 — Business Concept

## What this phase delivers

Nothing visibly changes for an end user in this phase — it is a structural move. But it
delivers a foundational capability for the *product's* future:

**Capability: Extensions become a first-class, self-contained part of the system.**
The reusable "extra detail" units that attach to equipment and equipment-models —
purchase information, registration, smog history, emissions, model specs — are lifted
out of the core equipment area into their own dedicated home. Each becomes a tidy,
self-describing package that declares everything it owns.

## Why it matters (user value, told plainly)

- **Adding a new kind of detail gets cheaper and safer.** Because each extension now
  lives in its own package that lists its own parts, a builder can add "tire pressure
  log" or "warranty terms" without touching the core equipment code. Fewer accidental
  breakages when the catalog of details grows.
- **The core equipment area gets simpler.** The equipment records stop carrying a
  hard-coded awareness of every possible detail type. That keeps the heart of the
  system focused on equipment itself.
- **It sets up independence.** This move is the groundwork for letting the details
  system run on its own (the next phase), so a problem in one detail type can never
  block creating a piece of equipment.

## Who interacts with it

- **Developers / builders** — the direct beneficiaries this phase. They gain a clear,
  predictable place to add and find detail types.
- **No change** for fleet managers, technicians, or administrators yet — their screens
  and workflows behave exactly as before.

## What stays the same

When a new piece of equipment or a new equipment-model is created, it still
automatically gains the detail records its category calls for — identical behavior,
just produced by code that now lives in a new home.
