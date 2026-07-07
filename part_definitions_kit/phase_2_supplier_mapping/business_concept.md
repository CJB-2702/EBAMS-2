# Phase 2 — Business Concept: Supplier Mapping

What this phase delivers, in user language. No tables, no class names.

## The idea

A single internally-defined part can usually be bought from more than one place, under more than
one vendor's name and number. This phase records that external reality — **who sells what, and
which of their items satisfies which of our parts** — without letting any of that supply-chain
noise leak into the clean engineering record. The internal part stays singular and stable;
purchasing gets as many options as the market offers.

## Capabilities

### Capability 1 — A registry of part manufacturers
A list of the external companies that make purchasable items. It is kept separate from the
company's *asset* manufacturer list on purpose, because the parts world will have far more
vendors and must not slow down asset lookups. *Maintained by supply / sourcing.*

### Capability 2 — Supplier items mapped to internal parts
For each internal part, the business can record one or more **supplier items** — the actual
purchasable products, each belonging to a manufacturer and carrying that manufacturer's own part
number. Each supplier item points at the single internal part it fulfils. This is the bridge
between "what we designed" and "what we can buy." *Used by supply* (to know what can be ordered)
and *engineers* (to confirm interoperability of options).

### Capability 3 — Supplier-side history and documents, kept separate
Supplier items have their own straight-line history — datasheet updates, quotes, vendor
revisions — with documents attached to each entry, exactly like internal part revisions but on a
completely separate track. A vendor refreshing a datasheet never creates or disturbs an
engineering revision. *Used by supply* (tracking quotes/datasheets) and *sourcing*.

## Who interacts with this phase

| Persona | What they get from Phase 2 |
| :--- | :--- |
| **Supply** | Sees every purchasable option for a part; records supplier items, quotes, datasheets. |
| **Sourcing** (potential) | Curates the manufacturer registry and supplier relationships. |
| **Engineer** | Confirms which supplier items are interoperable with a part, without their engineering record being touched by vendor changes. |
| **Technician** | Indirect benefit: a part now resolves to real, orderable items. |

## What it deliberately does **not** do yet

- It does not yet make a vendor's part number **searchable** — that is the alias index in
  Phase 3 (though this phase is what *produces* those numbers).
- It does not change anything about how internal parts work; supplier items only ever point
  *inward* at a part.
- No ordering/procurement workflow is built — only the mapping the supply persona needs to know
  *what* can be ordered.
