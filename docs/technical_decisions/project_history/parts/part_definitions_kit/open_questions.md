# Open Questions — resolution log

Updated **2026-06-24**. Most original questions are now resolved (decisions folded into
[`decisions.md`](decisions.md) or moved to the tech-debt file
`docs/technical_decisions/tech_debt/20260624 Part definitions kit deferrals.md`). Only the
**residual confirms** at the bottom remain before the kit is implementation-ready.

---

## Resolved

| ID | Question | Resolution |
| :--- | :--- | :--- |
| **OQ1** | How does a revision bind to its documents? | **Resolved → [D5](decisions.md).** Option (a) generalized: every attachable entity (Part, each Part revision, Supplier Item) owns an `events.ActivityThread` via `thread_id`, carrying **comments + documents**. *(Supplier items have no revision rows — [D13](decisions.md); vendor history lives on the item thread.)* |
| **OQ2** | Should aliases be revision-aware? | **Deferred — tech debt item 3.** Kept revision-agnostic ([D9](decisions.md)); "leave for later." |
| **OQ3** | First-revision rule / auto-create? | **Resolved → [D4](decisions.md).** Base revision auto-created on Part/Item create: `major=1, minor=0`, names null, `status=DRAFT`. `minor_revision_number` NOT NULL default 0. Numbers append-only; `sequence` follows `date_of_release`. |
| **OQ4** | Future of the two manufacturer tables | **Deferred — tech debt item 1.** Stays separate ([D2](decisions.md)); merge/pointer direction logged. |
| **OQ5** | Persona access / RBAC | **Resolved → [D11](decisions.md) + new [`functionality_and_roles.md`](functionality_and_roles.md).** Authenticated-only now; every kit now carries a functionality × role matrix for review. Kit-builder agent updated to require it. |
| **OQ6** | Released / redline semantics | **Folded into [`functionality_and_roles.md`](functionality_and_roles.md)** — to be decided in that matrix review. |
| **OQ7** | Search scope & ranking | **Deferred — tech debt item 4.** Important, but parts search stays minimal (exact/prefix) until a dedicated search manager + API is built. |
| **OQ8** | Seeding | **Resolved → see "Seed plan" below.** 16 parts; 4 car-part drivers fully exercised. |

## Seed plan (OQ8)

`seed_dev` contribution, built across the phases:

- **16 Parts total** — enough breadth to populate lists/search.
- **4 primary debugging drivers (car parts), fully exercised** across the whole model:
  **alternator, engine, starter, AC compressor**. For these four:
  - **Varied revision depth** — different numbers of major revisions and redlines each
    (e.g. alternator: A, B, B.1; engine: A, A.1, A.2, B, C; starter: A; AC compressor: A, B with
    a redline on the old A), so the `(major, minor)` "current" rule and old-major redlines are
    visibly testable.
  - **Multiple part manufacturers** and **supplier items with distinct MPNs** mapped to each
    driver, so forward resolution and many-suppliers-per-part are exercised.
  - A few **documents + comments** on selected revisions (drawings/change history) to exercise
    the events thread reuse.
  - Auto-generated **aliases** (internal + MPN) appear from the above; add a couple **manual**
    NSN/legacy aliases on the drivers.
- The other **12 parts** are lighter (1–2 revisions, 0–1 supplier items) for list density.

---

## Residual confirms — all resolved 2026-06-29

1. **Supplier revision model symmetry.** ✅ **Resolved 2026-06-28 → [D13](decisions.md).** Supplier
   items do **not** mirror Part revisions. The `SupplierItemRevision` table (and any
   vendor→part-revision mapping table) is **dropped**. Vendor revision history is structured comments
   on the Supplier Item's events thread; interoperability is a denormalized **compatibility range**
   (four nullable major/minor bounds) on the `SupplierItem`. Firm vendor revision tracking is
   deferred (tech debt item 6).
2. **`major_revision_name` generation.** ✅ **Resolved 2026-06-29.** Free-text (engineer types
   `A`/`Cobra`/anything) — confirmed. No auto-`A,B,C` assignment.
3. **`functionality_and_roles.md` review.** ✅ **Resolved 2026-06-29.** User answers recorded inline
   in that file: release does not lock the revision; redlines are engineer-only; comments allowed by
   any authenticated user; manual aliases allowed for any elevated non-base role; enforcement is
   **comments-only for now** (a later RBAC pass does the actual gating) except `is_domain_limited`
   data-domain blocking, which is modeled now per [D14](decisions.md).

**Kit is implementation-ready.** Proceeding to build Phases 1–4.
