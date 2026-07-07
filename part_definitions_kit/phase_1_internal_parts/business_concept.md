# Phase 1 — Business Concept: Internal Parts

What this phase delivers, in the language of the people who use it. No tables, no class names.

## The idea

Every component the organization engineers gets **one definitive internal record** — its part
definition. This record is the single source of truth: it carries the official internal part
number and is the thing every other part of the business points back to when it says "that
part." The rest of the system, now and in the future, only ever needs to know this one
internal identity — never the messy details of who sells it or which datasheet is current.

## Capabilities

### Capability 1 — A definitive internal part record
A part has a stable internal identity and an official part number. Once it exists, it can be
referenced by anything in the business that deals with parts. *Used by everyone* — but it is
the engineer who establishes and curates it.

### Capability 2 — A traceable revision history
Each part carries a straight, ordered history of its engineering changes — like a logbook where
every entry is the next line down. The newest entry is the current state of the part; older
entries are preserved exactly as they were. Each entry has a status — for example a working
*draft*, an approved *released* version, or a marked-up *redline*. *Used by engineers* tracking
design changes and coordinating interoperability with the supply side.

### Capability 3 — Point-in-time documentation
Engineering documents — drawings, specifications, approval PDFs — attach to a **specific entry**
in the part's history, not to the part as a whole. This guarantees that the documents you see
always match the exact version you're looking at: a newer revision's drawing can never mislead
someone reading an older, superseded one. *Used by engineers* (authoring/approving) and
*technicians* (reading the current approved set).

## Who interacts with this phase

| Persona | What they get from Phase 1 |
| :--- | :--- |
| **Engineer** | Creates and curates parts; adds revisions; attaches the right documents to the right revision. |
| **Technician** | Reads a part's current state and its current approved documents (full lookup-by-number arrives in later phases). |
| **Supply** | Has a stable internal part to map purchasable items against (the mapping itself is Phase 2). |

## What it deliberately does **not** do yet

- It says nothing about *who sells* the part — no manufacturers, no vendor catalogues (Phase 2).
- It does not yet let you find a part by an old number, a national stock number, or a vendor's
  number — that unified search arrives in Phase 3.
- There is no screen yet; this phase is the dependable engine the later screens sit on.
