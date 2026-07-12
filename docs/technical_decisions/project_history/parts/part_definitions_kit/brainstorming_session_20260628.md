# Brainstorming Session — 2026-06-28

> **Scope note.** 2026-06-28 had **two** chat sessions touch the kit. This doc records both, in the
> order they happened: **Session 1** (revision model + documents/comments + open-question sweep),
> then **Session 2** (supplier revision modeling → D13). Session 1 was reconstructed and prepended
> after the fact — it ran first but Session 2 created this file. Session 1 *establishes* the
> symmetric-supplier-revision assumption that Session 2 then *removes*, so they read in sequence.

---

## Session 1 — Revision model, documents & comments, open-question sweep

### Goal

Two things the kit hadn't pinned down: **how revisions are structured**, and **how documents (and
comments) attach to them**. Then clear the eight standing open questions so the kit could move
toward implementation.

### How the session ran

1. **Trigger.** The user wanted every revision — *and the Part, and the supplier items* — to be able
   to carry **documents and comments**, specifically to hang **technical drawings and change
   history** off each revision. That reverses the original spec's "documents only on revisions,
   never on parts/items."
2. **The "sub-revision" fork.** The word *sub-revision* contradicted the original spec (which had
   explicitly rejected sub-revision tables for a flat list). Rather than guess, surfaced the
   ambiguity with three structural options — two-tier hierarchy / flat-with-status /
   "sub-revision = the supplier track."
3. **User refined a hybrid in chat.** Landed on a **flat table with numeric major/minor as the
   source of truth and names as an optional feature.** Validated it against the user's own
   `A → B → redline-on-old-A` example before writing anything.
4. **Open-question sweep.** Resolved OQ1–OQ8 in one batch (answers, deferrals, and new docs).
5. Updated every affected doc in one pass.

### Key facts established

- Users follow **no reliable revision naming convention** (`A,B,C`, animals, fruit,
  `cobra-redline2`…) — so the **numbers** must be authoritative and names purely cosmetic.
- "Current" is **not** "most recent." A redline issued against an *older* major (e.g. fixing
  fielded units still at rev A, after rev B shipped) must **not** become the current revision.
- Documents are point-in-time, but the Part and supplier items *also* need a place for free-standing
  commentary/docs — so the attach point had to exist at **every** level, not just revisions.

### The idea progression (roads walked)

- **Documents-only on revisions** (original spec) → **comments + documents at every level.**
- **Sub-revision hierarchy / sub-revision tables** → rejected for a **flat** table.
- **`base_revision` / `previous_base` self-FK pointers** (an interim sketch to chain baselines and
  attach redlines) → **dropped** once the major/minor numbers proved enough to *derive* lineage (a
  redline's base = same major at minor 0; previous baseline = next-lower major at minor 0).

### Decisions reached

- **D4 — numeric major/minor revisions.** One flat table; `major_revision_number` /
  `minor_revision_number` (NOT NULL, default 0) are the source of truth;
  `major_revision_name` / `minor_revision_name` are optional/nullable; `sequence` aligns with
  `date_of_release`. **Current = highest `(major, minor)`, NOT highest `sequence`.** Lineage
  derived, not stored. Denormalized by choice (normalization → tech debt).
- **D5 — comments + documents at every level.** Part, each revision, and supplier items each own an
  `events.ActivityThread` (`thread_id`) carrying *both* comments and file attachments. **Closes
  OQ1** (its option (a), generalized from files-only `FileSet` to full threads).
- **OQ sweep:** OQ3 (base rev auto-created `1.0`), OQ5/OQ6 → new
  [`functionality_and_roles.md`](functionality_and_roles.md) role matrix (and the kit-builder agent
  updated to require one in every kit), OQ8 → seed plan (16 parts; 4 car-part drivers —
  alternator/engine/starter/AC compressor — fully exercised). OQ2/OQ4/OQ7 + parking lot → tech-debt
  file `20260624 Part definitions kit deferrals.md`.

### Ripple updates

`decisions.md` (D4, D5, D9, D11), Phase 1 & 2 `data_relational_plan` + `control_layer_plan`,
`open_questions.md`, root `README.md`, new `functionality_and_roles.md`, new tech-debt file,
`.claude/agents/kit-builder.md`, `STATUS.md`.

### Left open (the bridge to Session 2)

One **residual confirm**: the kit *assumed* `SupplierItemRevision` would mirror the Part major/minor
model, chosen for **symmetry rather than demonstrated need**. Flagged as residual confirm #1 — and
that is exactly the question Session 2 took up and closed.

---

## Session 2 — Supplier revision modeling (D13)

### Goal

Close the last open structural question in the Part Definitions kit: **should supplier items have
revisions, and how should our production team's revision reality relate to the vendor's?** This was
the lone "residual confirm" left in [`open_questions.md`](open_questions.md) (#1) — the kit had been
assuming `SupplierItemRevision` would mirror `PartRevision`'s major/minor model, chosen for symmetry
rather than need.

### How the session ran

Deliberately staged, at the user's direction:

1. **Read the current standing first.** Pulled the existing position out of `open_questions.md`,
   `decisions.md` (D4/D5), and the Phase 2 plans before proposing anything — confirmed the symmetric
   `SupplierItemRevision` was an unconfirmed assumption, not a decision.
2. **Business problems in chat only, no schema.** Enumerated the real-world frictions of integrating
   a vendor's sovereign revision system with ours. The user triaged them (keep / solve-lite /
   defer / drop) before any table was drawn.
3. **Iterated on data structures** across several concepts, narrowing as the user reacted.
4. **Confirmed, then updated the kit** in one pass across all affected docs.
5. Wrote a standalone decision walkthrough and (this) session record.

### Key facts established

- The firm, never-in-doubt principle: **vendor churn must never disturb the engineering record** — a
  datasheet update cannot create or perturb a Part revision. Everything else was negotiable.
- The user's actual pain (the reason the question kept reopening): **a vendor's "latest" is not our
  "approved."** You may deliberately keep buying an older vendor revision because the newer one isn't
  qualified.
- The two problems worth solving now: **(1)** which vendor changes matter vs. don't, and **(2)**
  interoperability is really *revision-to-revision*, not item-to-part.
- Decided to **carry only a flat log** of vendor history — not their full structured history.
- The ~98% case has **no** revision-level mapping between a vendor item and a part revision; whatever
  was built had to keep that common case free and leave the rare case possible later.

### The idea progression (roads walked)

- **A — Symmetric `SupplierItemRevision`** (the kit's old assumption). Rejected: maintenance burden
  of mirroring a system we don't control, to express a non-linearity vendors rarely have.
- **B — Flat log + `locked` flag + optional mapping table.** A flat counter (newest = latest), a
  `locked` boolean marking the approved revision (latest-vs-approved as two pointers), plus a
  normally-empty `SupplierItemRevision`→`PartRevision` mapping with a notes field for the rare case.
  Considered, then shelved to tech debt — still two extra tables and a revision concept to maintain.
- **C — Denormalized compatibility range, no revision table** *(chosen)*. A `SupplierItem` becomes
  "a procurement option valid across a *band* of our part's revisions."

### Decision reached — D13

Recorded as [**D13**](decisions.md) (resolves residual confirm #1). No `SupplierItemRevision` table
and no mapping table. Two cheap mechanisms instead:

- **Vendor history → comments.** One append-only `Comment` per vendor revision on the Supplier
  Item's `events.ActivityThread` (`is_human_made = True`), machine-formatted JSON body
  (`vendor_revision_id` + `note`) posted via a form. The thread *is* the flat history; datasheets and
  quotes attach to the same thread.
- **Interoperability → a compatibility range** on the item: four **nullable integer** bounds
  (`min`/`max` × `major`/`minor`), compared against `PartRevision.major/minor` at query time, **no
  FK** (revision-agnostic). All-null = valid for all revisions; set-major + null-minor = the whole
  major band. No `min ≤ max` constraint in v1.

Confirmed costs, knowingly accepted: vendor history is **not SQL-queryable** (JSON text in
`comment.content`), the range is unconstrained in v1, and there is no first-class model of the
vendor's own lineage. Rationale: *get the application moving, leave the harder infrastructure parked
but not foreclosed.*

### Ripple updates

- [`decisions.md`](decisions.md): D4 narrowed to Part revisions only; D5 reworded (no
  supplier-revision threads); **D13** added.
- [`open_questions.md`](open_questions.md): residual confirm #1 marked resolved.
- [`STATUS.md`](STATUS.md), [`functionality_and_roles.md`](functionality_and_roles.md).
- Phase 2 `README` / `data_relational_plan` / `control_layer_plan` — dropped the revision table +
  manager, added the compatibility range and `SupplierVendorRevisionManager`.
- Phase 4 `README` / `ui_features_plan` / control + data plans — supply portal sets the range and
  logs vendor revisions.
- Tech debt **item 6** (firm vendor revision tracking) added, carrying the shelved Option B sketch.
- Decision walkthrough archived:
  [`docs/technical_decisions/incident_history/2026-06-28_supplier_revision_modeling_decision.md`](../docs/technical_decisions/incident_history/2026-06-28_supplier_revision_modeling_decision.md).

### Status

Kit's last open structural question is now **closed**. Residual confirms #2 (`major_revision_name`
generation) and #3 (`functionality_and_roles.md` `?`-cell review) remain before implementation —
neither blocks the data model.
