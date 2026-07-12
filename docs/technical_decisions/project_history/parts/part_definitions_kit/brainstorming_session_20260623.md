# Brainstorming Session — 2026-06-23

## Goal

Turn a detailed written system specification ("Engineering Asset & Supply Chain Registry") into
a phased, buildable starter kit for a new `app/parts/` sub-app. The spec already settled the
*target* schema and rationale; the session's job was to resolve how that target lands inside
*this* codebase and in what order to build it.

## How the session ran

The user supplied a complete specification up front (preserved verbatim in
[`initial_prompt.md`](initial_prompt.md)), so interrogation focused not on re-deriving the
domain but on the **seams** the spec was silent about: where it lives, what it reuses, who uses
it, and the phase order. A short codebase audit ran in parallel
([`existing_seams_audit.md`](existing_seams_audit.md)) and surfaced the two facts that shaped
every later decision: an existing **asset `Manufacturer`** table, and a complete **events
file-management system** (`File` / `Attachment` / `FileSet`).

## Key facts established

- This is **mostly greenfield**. The legacy system had only flat part definitions.
- The overriding design principle: the wider application (assets, future BOM, future
  configuration-allowability) must reference a part **only by its base Part id** — never reach
  into supplier items, revisions, or documents. The Part id is the stable hub; everything else
  is a satellite. ([D3](decisions.md))
- There is an existing asset `Manufacturer` table that must stay small and fast. Part
  manufacturers will be numerous. So they are kept as **separate tables** now, with a clean
  future merge path left open. ([D2](decisions.md), OQ4)
- The events app already does file management properly, so **documents reuse it** rather than
  growing a parts-local file table. The interesting wrinkle: `Attachment` binds to a *thread*,
  and a `FileSet` proxy exists precisely for "a bag of files with no lifecycle" — a natural home
  for revision documents. ([D5](decisions.md), OQ1)
- Four personas: technicians (fast number/alias lookup), engineers (revisions + interop with
  supply), supply (ordering from maintenance demand), and a potential sourcing role. Addressed
  by distinct **views**, not permission gates, in this first cut. ([D11](decisions.md), OQ5)
- Aliases **auto-populate** from supplier MPNs (and internal numbers) and stay
  **revision-agnostic** — an identifier should remain interoperable across revisions.
  ([D8](decisions.md), [D9](decisions.md))

## Decisions reached

Twelve decisions, D1–D12, recorded in [`decisions.md`](decisions.md). The load-bearing ones:
new `app/parts/` sub-app (D1); separate part-manufacturer table (D2); base-Part-id-only
contract (D3); flat `sequence`+`status` revisions (D4); documents via the events FileSet (D5);
supplier items map forward to one Part, many per Part (D6); aliases auto-populated and
two-nullable-FK targeted (D8/D9).

## Phase shape

Four phases, control-layer-first, each independently testable:

1. **internal_parts** — Part hub + flat revisions + revision documents. Built and made
   referenceable in isolation, honoring D3 before any satellite exists.
2. **supplier_mapping** — part manufacturers, supplier items (→ Part), supplier item revisions.
3. **aliases_search** — the unified index + resolver; its auto-population orchestrator hooks
   Phase 2's create path, so it must come after both number sources exist.
4. **parts_ui** — persona-driven thin UI over the now-correct control layer.

## Open questions carried into implementation

Eight, captured in [`open_questions.md`](open_questions.md). The one that actually blocks code
is **OQ1** — the precise revision↔FileSet binding. The rest (first-revision rule, release
semantics, alias revision-awareness, RBAC, search ranking, seeding, manufacturer-merge
direction) have provisional defaults baked into the plans and can be confirmed or overridden at
review without reshaping the kit.

## Status

Kit drafted, **not yet reviewed**. User reviews 2026-06-24 and continues. Start the review at
[`open_questions.md`](open_questions.md).
