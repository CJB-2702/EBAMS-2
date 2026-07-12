# Phase 4 — Business Concept: Parts UI

What this phase delivers, in user language. No tables, no class names.

## The idea

Give each kind of user a screen that fits how they actually work. The same underlying parts data
serves very different jobs: a technician glancing at a number on a component, an engineer
curating a design's history, a supply specialist lining up where to buy it. This phase turns the
engine built in the earlier phases into those day-to-day screens.

## Capabilities by persona

### Technician — find a part fast
A prominent search that accepts **any** number — internal, legacy, national stock number, or a
vendor's number — and immediately shows the one definitive part, with its current state and its
current approved documents. Minimal clicks; built for "I have a number, what is this?"

### Engineer — curate the part and its history
A workbench for a single part: see and add revisions, mark a revision's status (draft, released,
redline), and attach the right documents to the right revision. The engineer also sees which
supplier items are mapped to the part, to reason about interoperability — without their
engineering record being affected by vendor changes.

### Supply — map and maintain purchasable options
A surface to register manufacturers and record supplier items against a part, plus log supplier
revisions (datasheet updates, quotes) with their own documents. The moment a supplier item is
recorded, its vendor number becomes searchable for everyone.

## Page families

| Family | Classification | For |
| :--- | :--- | :--- |
| Parts hub & search | Navigation | Technician (primary), everyone |
| Part detail | User View | Everyone |
| Part / revision portals | Work Portal | Engineer |
| Manufacturer & supplier-item portals | Work Portal | Supply / sourcing |

## What it deliberately does **not** do

- No new data concepts — it only presents and drives what Phases 1–3 already model.
- No procurement/ordering execution — supply sees *what can be ordered*, not an order workflow.
- No permission walls between personas yet — the screens are shaped per persona, but anyone
  authenticated can reach them (gating can be added later without data changes).
