# Phase 1 — Business Concept

## What this phase delivers

The ability to **say which assets are part of which** — to declare that one tracked asset
sits underneath another — and to have that fact recorded the moment it changes, on the
timelines of both assets involved.

Today the system can technically hold a parent for an asset, but nothing about *changing*
that relationship is visible or trustworthy: no record appears on either asset's activity
log, and moving an asset that has its own sub-assets can leave the grouping in a confused
state. This phase makes relationship changes deliberate, traceable, and structurally sound.

## Capabilities

- **Place an asset under another.** A user (through the Phase 2 screens, or any future tool)
  can attach an asset as a child of another — e.g. mounting a pump onto a skid, or grouping
  components under an assembly.
- **Remove an asset from its group.** Detaching an asset lifts it — and everything beneath
  it — back out as its own standalone grouping.
- **Move whole sub-groups intact.** When an asset that already has children is placed
  somewhere new, its entire sub-group travels with it and stays internally consistent.
- **A clear record on both sides.** Every attach or detach writes a plain-language entry —
  "Pump-12 attached under Skid-4" — that shows up on **both** the parent's and the child's
  history, so anyone reviewing either asset sees the change and who made it.
- **Protection against nonsense groupings.** The system refuses to place an asset inside its
  own sub-group (which would create an impossible loop) and explains why.

## Who uses it

- **Asset managers / technicians** structuring how physical equipment is assembled and
  grouped.
- **Auditors / reviewers** who need to see, on an asset's timeline, when it joined or left a
  grouping and who changed it.
- **Other parts of the system** (configuration, reporting) that need a reliable, correctly
  nested picture of which assets belong together.

## User value

Relationships become a first-class, auditable fact rather than a silent database pointer.
Groupings stay consistent when equipment is rearranged, and the history of "what was part of
what, and when" is always answerable from either asset.

## Not in this phase

No screens — this phase is the engine. The view/edit experience, the Configurations entry,
and search-to-attach arrive in Phase 2.
