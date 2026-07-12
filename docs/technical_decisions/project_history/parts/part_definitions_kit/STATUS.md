# Status — Part Definitions Kit

Quick "where am I" for returning to this kit. Newest state at top. Planning only — **no code or
migrations have been written.**

---

## TL;DR (as of 2026-06-29)

**All 4 phases implemented and verified.** `app/parts/` is built end to end: models, control
layer (Structs/Contexts/Factories/Managers/Handlers/Guards/Narrators/Orchestrators), the alias
search index, and the Bulma+HTMX UI. Seeded via `seed_parts_dev` (16 parts, 4 fully-exercised
drivers) and wired into `dev_tools/delete_database_rebuild_models.py --seed`. Verified headless
(Django shell — revision "current" rule, old-major redline, compatibility range, domain scoping)
and through the live dev server (part create → base revision → auto alias, all pages 200).

## Implementation complete — 2026-06-29

- **Phase 1** — `app/parts/models/core/{part,part_revision}.py`,
  `models/domain_scope/part_domain_access_mapping.py`; control layer: `PartStruct`,
  `PartRevisionStruct`, `PartContext`, `PartFactory`, `PartRevisionManager`,
  `PartThreadManager`, `PartDomainManager`, `PartDomainTemplateHandler`,
  `PartRevisionNarrator`, `PartValidator`.
- **Phase 2** — `models/supply/{part_manufacturer,supplier_item}.py`; `PartManufacturerFactory`,
  `SupplierItemStruct`/`Factory`/`Context`, `SupplierVendorRevisionManager`,
  `SupplierItemNarrator`, validators.
- **Phase 3** — `models/search/alias.py`; `AliasFactory`, `PartAliasOrchestrator`,
  `SupplierAliasOrchestrator` (wired into the Phase 1/2 factories' alias hooks, same
  transaction), `AliasResolver` + `PartSearch` (`presentation_layer/search/`).
- **Phase 4** — adaptors, entrypoints, `urls.py`, templates under `templates/parts/`
  (hub/search, part detail, revision workbench, manufacturer registry, supplier item
  mapping/detail). Global nav: `Parts` dropdown added to `shared/topnav.html`.
- **Seed** — `app/parts/management/commands/seed_parts_dev.py` builds all 16 parts through the
  real control layer (not raw fixtures), so every business rule fires during seeding. Wired into
  `dev_tools/delete_database_rebuild_models.py --seed`.
- **Implementation discoveries not in the original plan:**
  - `events.ActivityThread`/`Comment` rows live on the shared `event` table, whose `domain` FK is
    **NOT NULL** — even though Parts deliberately carry no single ownership domain (D14 uses
    `is_domain_limited` + a M2M instead). Resolved by having `PartThreadManager` accept
    `domain_id` only at the moment a thread is first lazily created (comment/document/vendor-rev
    forms each carry a domain selector), never persisted on the Part/Revision/SupplierItem itself.
  - The "resolver home" and "thin `PartManufacturerContext`" open points in
    `control_layer_diagram.md` were resolved as: `AliasResolver` lives in
    `presentation_layer/search/` (read-only, feeds `PartSearch`); manufacturer reads go through
    `PartManufacturerStruct` directly with no separate Context (too thin to warrant one).
  - `seed_dev` in this repo means JSON fixtures + `loaddata`, not a single command — the parts
    contribution is a management command instead (`SimpleUploadedFile` documents, real Factory
    calls) since the alias/thread/revision invariants are too intricate to hand-author as fixture
    JSON safely.

---

## Added 2026-06-29 — Part domain scoping ([D14](decisions.md))

- **`Part.is_domain_limited`** boolean (default `False` = not limited / visible to all) + a new
  **`PartDomainAccessMapping`** join table (Part ↔ existing `administration.Domain`, mirrors
  `UserDomain`). Only consulted when the flag is `True`; governs the Part *and its children*.
- **Issue domains from a `DomainTemplate`**: `PartDomainTemplateHandler.apply(template_id)` copies a
  template's domains into mapping rows (rebase on re-issue) — same pattern as the admin
  `DomainTemplate → UserDomain` flatten. Template is copied at apply time, not bound by FK.
- **Modeling only** — enforcement (queryset filtering) deferred to the later RBAC pass ([D11](decisions.md)).
- **Assets section scaffolding (code, not just plan):** empty placeholder pages + sidebar nav under
  Assets — **Part-Model Associations** and **Part-Class Associations** — staking out the future
  association framework where Part definitions will live.

## Resolved this session (2026-06-24)

- **Revision model finalized → [D4](decisions.md).** Flat table, but **numeric major/minor is the
  source of truth, names are an optional feature** (users use unreliable names like `Cobra`).
  Columns: `sequence` (aligned to `date_of_release`), `major_revision_number`,
  `minor_revision_number` (NOT NULL default 0), `major_revision_name`/`minor_revision_name`
  (nullable). **Current = highest `(major, minor)`, NOT highest sequence** — so a redline on an
  old major doesn't become current. Lineage is derived from the numbers (the earlier self-FK
  pointers were dropped). Denormalized by choice (normalization → tech debt).
- **Comments + documents at every level → [D5](decisions.md), closes OQ1.** Part, each Part revision,
  and Supplier Item own an `events.ActivityThread` (`thread_id`) carrying **both** comments and file
  attachments. Manufacturers get no thread. (Supplier items have no revision rows — [D13](decisions.md).)
- **Supplier revisions dropped → [D13](decisions.md), resolves residual confirm #1 (2026-06-28).**
  No `SupplierItemRevision` table. Vendor history = structured JSON comments on the item thread;
  interoperability = a denormalized **compatibility range** (four nullable major/minor bounds) on
  `SupplierItem`. Firm vendor revision tracking → tech debt item 6.
- **All 8 original open questions dispositioned** (see [open_questions.md](open_questions.md)):
  OQ1/OQ3/OQ5/OQ6/OQ8 resolved; OQ2/OQ4/OQ7 + parking lot → tech debt
  (`docs/technical_decisions/tech_debt/20260624 Part definitions kit deferrals.md`).
- **New required doc → [functionality_and_roles.md](functionality_and_roles.md).** A
  functionality × role matrix (technician/engineer/supply/sourcing) for you to review; release/
  redline permission semantics (OQ6) live there. **The kit-builder agent was updated** to require
  this file in every future kit.
- **Seed plan set (OQ8):** 16 parts; 4 car-part drivers — **alternator, engine, starter, AC
  compressor** — fully exercised with varied revision depth, multiple manufacturers, supplier
  items with distinct MPNs, some docs/comments, and manual NSN/legacy aliases.

## Docs updated this session

`decisions.md` (D4, D5, D9, D11 reworked) · `phase_1_internal_parts/{README,data_relational_plan,
control_layer_plan}.md` · `phase_2_supplier_mapping/{README,data_relational_plan,
control_layer_plan}.md` · `phase_3_aliases_search/README.md` · `open_questions.md` ·
`README.md` · new `functionality_and_roles.md` · new tech-debt file · `.claude/agents/kit-builder.md`.

## Work to do

1. **Confirm 3 residuals** ([open_questions.md](open_questions.md) bottom):
   1. Supplier Item revisions use the **same** major/minor model as Part revisions? (assumed yes)
   2. `major_revision_name` is **free-text** (no auto `A,B,C`)? (assumed yes)
   3. Fill the `?` cells in [functionality_and_roles.md](functionality_and_roles.md) when ready to
      gate access.
2. **Implement Phase 1** (`phase_1_internal_parts/`) — the Part hub + revisions + threads. It's
   the only phase the rest of the app references; build/test it headless first.
3. Then Phase 2 → 3 → 4 in order.

## Reference

- Kit overview & phase order: [README.md](README.md)
- Why each decision: [decisions.md](decisions.md)
- What's reused from the codebase: [existing_seams_audit.md](existing_seams_audit.md)
- Deferred work: `docs/technical_decisions/tech_debt/20260624 Part definitions kit deferrals.md`
