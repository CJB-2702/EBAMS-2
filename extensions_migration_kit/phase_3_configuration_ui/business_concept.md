# Phase 3 — Business Concept

## What this phase delivers

**Capability: Administrators decide which details apply to which equipment.** A real
configuration screen lets an administrator turn a detail type on or off for a whole
category of equipment, or for a specific equipment-model. Turn on "smog history" for the
"On-road Vehicle" category and every vehicle gains a smog-history detail; turn on
"engine specs" for a model and that model carries it.

**Capability: A consistent way to reach any detail.** Every detail type — present and
future — is reachable through the same predictable address pattern: a summary for the
detail type, a searchable list across all equipment, a page for one piece of equipment,
and (for details that keep a history) a page for one entry. This consistency is defined
now as a contract so future detail types slot in without inventing new navigation.

## Why it matters (user value, told plainly)

- **Self-service configuration.** Deciding which details apply is an administrator
  action in the UI, not a developer task. The current screen is a mock that doesn't
  save — this makes it real.
- **Predictable navigation.** Users and builders always know where a detail lives. A new
  detail type automatically appears in the right places with the right address shape.
- **At-a-glance details on equipment.** A compact panel on an equipment page shows all
  the details that apply to it as cards, each linking to its own area.

## What is intentionally *not* built yet

The **inside** of each detail type's pages — the actual fields, forms, and history
tables for purchase info, smog records, and the rest — is **not** part of this phase.
This phase builds the *configuration* and the *navigation contract*; each detail type's
own screens are filled in afterward, one at a time, into the slots this phase defines.

## Who interacts with it

- **Administrators / fleet managers** — assign detail types to categories and models;
  the primary new users this phase.
- **All users** — gain consistent navigation and the equipment-page detail panel.
- **Builders** — get a fixed contract to implement each detail type's pages against.
