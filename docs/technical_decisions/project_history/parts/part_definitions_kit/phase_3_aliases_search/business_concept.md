# Phase 3 — Business Concept: Aliases & Unified Search

What this phase delivers, in user language. No tables, no class names.

## The idea

Out in the real world, the same part is called many different things: the official internal
number, an old in-house code from a legacy system, a government national stock number, and every
vendor's own catalogue number. This phase gives the organization **one search box that knows them
all** — type any of those numbers and the system lands you on the one definitive internal part,
no matter which alias you happened to know.

## Capabilities

### Capability 1 — One unified search index
Every identifier a part is known by lives in a single, fast-to-search index, each tagged with
what kind of identifier it is (internal, national stock number, legacy, vendor number). One
search behaves identically across all of them. *Used by everyone — especially technicians, who
mostly just need a number and an alias or two.*

### Capability 2 — Numbers index themselves
When a part is created, its official number is added to the index automatically. When a vendor's
purchasable item is recorded, that vendor's number is added automatically too. Nobody has to
remember to register a number for it to be findable — the index never falls behind reality.
*Benefits supply and engineers* whose entries become searchable the moment they're made.

### Capability 3 — Always resolves to the definitive part
Whatever number you search by, the answer is the **internal part**. If you searched a vendor's
number, the system quietly follows the trail from that vendor item back to the internal part it
fulfils, and shows you the part. You never have to know whether the number you typed was
"ours" or "theirs." *This is the payoff for the technician* who has only a number stamped on a
component and needs to know what it actually is.

## Who interacts with this phase

| Persona | What they get from Phase 3 |
| :--- | :--- |
| **Technician** | Types any number off a component and gets the right internal part — the core daily task. |
| **Supply** | Looks up a part by a vendor's number while quoting/ordering. |
| **Engineer** | Finds a part by a legacy code during interoperability work. |

## What it deliberately does **not** do yet

- It is the search *engine*, not the search *screen* — the actual lookup page is Phase 4.
- Identifiers are deliberately tied to the part/vendor-item, **not** to a specific revision: an
  identifier is meant to stay valid as the part evolves.
- It does not invent new numbers — it only indexes and resolves the ones the earlier phases
  produce.
