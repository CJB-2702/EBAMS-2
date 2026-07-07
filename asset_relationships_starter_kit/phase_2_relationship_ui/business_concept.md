# Phase 2 — Business Concept

## What this phase delivers

The screens where people actually **see and shape** how assets are grouped — a place to look
at everything that lives under an asset, drill into the sub-groups, and add or remove members
without leaving the page.

Phase 1 made relationships real and auditable behind the scenes. This phase is where a user
opens an asset, sees its sub-assets laid out as a tree, opens deeper levels on demand, and —
when editing — searches the catalog and pulls assets into the group or lifts them out.

## Capabilities

- **Find it where you'd expect.** A new **Asset Relationships** entry under Configurations is
  the front door to managing how assets nest.
- **View a grouping.** A read-only page shows an asset with its children laid out as rows,
  each showing what it is and how many sub-assets it carries. Levels open one at a time on
  click, so a large structure stays scannable.
- **Edit a grouping.** The edit page shows the same tree, but each row can be **removed** from
  the group, and a **search bar** lets the user look up any asset and **attach** it as a new
  child — building the set incrementally.
- **Only sensible options offered.** The attach search hides the asset itself, things already
  in the group, and anything that would create an impossible loop, so a user can't pick a bad
  target.
- **Immediate, honest feedback.** Attaching or detaching updates the tree in place; an illegal
  action explains itself inline and changes nothing.

## Who uses it

- **Asset managers / technicians** assembling and rearranging equipment groupings.
- **Reviewers** who want to read a grouping top-down without editing it (the view page).

## User value

Relationship structure becomes something you can *see and manipulate directly* — not a hidden
database fact. The same picture serves both a quick read (view) and hands-on restructuring
(edit), and every change is the audited operation built in Phase 1.

## How a user moves through it

```
Configurations index
   └─▶ Asset Relationships
          └─▶ pick / land on an asset
                 ├─▶ children/view  — read the tree, expand levels on click
                 └─▶ children/edit  — expand, Detach a child, or Search → Attach
```

## Not in this phase

No new relationship rules or storage — every action calls the Phase 1 engine. Drag-and-drop
re-parenting is a future enhancement; this phase uses click-to-attach / click-to-detach.
