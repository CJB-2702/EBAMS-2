# Parts refactoring — build brief

Consolidated hand-off for a **fresh chat** to execute. This folder's two companion docs hold the
detailed plans; this file is the orchestrator + the decisions made after they were written.

- [`struct_migration_plan.md`](struct_migration_plan.md) — the Part-oriented struct plan (eager/lazy analysis, PartDefinitionStruct).
- [`control_layer_refactor_plan.md`](control_layer_refactor_plan.md) — the small-file / duplication findings.

**Start by resolving §1. It gates everything in §4–§5.**

---

## 0. Already done (do NOT redo)

These landed in the design conversation and are on disk already:

- **Adapter dedup** — `control_layer/adapters/form_parsing.py` (`parse_checkbox`, `parse_int`) created; the 4 `*_adaptor.py` files now import it. (Refactor plan item 1 ✅)
- **Duplicate `PartValidationError` removed** — lifted to `control_layer/errors.py`; `part_factory.py` and `part_manager.py` import it; `entrypoints/parts.py` no longer aliases the import. (Refactor plan item 3 ✅)
- **ActivityThread docstring note** — `app/events/models/activity_thread_proxy.py` now documents that an owner-tied thread's inherited `domain` is NOT authoritative for access (see §2).
- Parts tests pass (`python manage.py test app.parts`, 4 tests).

The dead structs (`alias_struct.py`, `part_manufacturer_struct.py`) are **still present** — they get deleted in §4.

---

## 1. DECIDED — bootstrap domain = the thread's own class/type name

**The problem is mechanical, not semantic.** `ActivityThread.domain` (`app/events/models/event.py:160`)
is a **NOT NULL, PROTECT** FK. Creating any thread row requires a real `Domain`. There is **no default
domain** in the model or seeding; the parts seed currently grabs
`Domain.objects.order_by("id").first()` as a throwaway bootstrap value.

Machine comments (§5) force the Part's thread to be created **early**, inside `PartRevisionManager` /
`SupplierItemFactory` / alias orchestrators — flows that carry **no domain**. So we must supply the
value that goes into the required `domain` column at thread-creation time.

This is *separate* from access control: per §2, who may read a part's thread is governed by
`PartDomainAccessMapping`, never by `thread.domain`. This decision is only "what to physically write
into the NOT NULL column."

**Decision: one default `Domain` per functional Event variant, named after that variant's class/type.**
A thread bootstraps with the default domain matching **its own class/type** — the throwaway domain now
self-documents what kind of thread it is instead of being an opaque `SYSTEM` catch-all. Rule is
generic: `default domain = the thread's own class/type name`.

Current owner-tied variants (there are exactly two proxies + the base):

| Class | `thread_type` | Default domain name |
| :--- | :--- | :--- |
| `Event` (base) | `EVENT` | `Event` |
| `ActivityThread` (proxy) | `DOCUMENTATION` | `Activity Thread` |
| `FileSet` (proxy) | `PHOTO_GALLERY` | `File Set` |

Note: there is **no standalone comments-only proxy today** — "comments" and "activity thread" collapse
to `ActivityThread`. The generic rule auto-covers a comments-only variant if one is ever split out; do
not hardcode a "Comments" domain until such a class exists.

Rejected alternatives: single shared `SYSTEM` domain (less self-documenting); (b) capture a real
domain on create — contradicts the shared/multi-domain D14 model; (c) defer/skip machine comments when
no thread — inconsistent audit trail; (d) make `domain` nullable — a base-app schema change
(migrations + `visible()` querysets), too heavy for this build, revisit later.

**Action:** idempotent `get_or_create` of one default `Domain` per variant (seed); add a helper such as
`app/parts/control_layer/thread_domain.py::default_domain_id_for(thread_cls_or_type)` that maps a
thread class/type to its default domain; route `PartThreadManager` bootstrap through it (derive the
type from the thread being created). Because this adds seed rows, run the full DB reset (§6) after.

---

## 2. Guiding principle (context, not a task)

`ActivityThread` and its file collection inherit `Event`'s single, NOT-NULL `domain`. That
single-domain shape is **correct** for events with a physical single-domain counterpart (an asset lives
in one domain) — it is not an anti-pattern. But a **Part definition is a shared record** that can span
domains (optionally restricted via `is_domain_limited` + `PartDomainAccessMapping`). So when a thread
is **tied to another item**, it is subordinate to that item: visibility defers to the *owner's*
domain-access rules, and the thread's own `domain` is an incidental bootstrap value. This is already
captured in the `ActivityThread` docstring; keep read paths consistent with it (never gate part-thread
reads on `thread.domain`).

---

## 3. Base-app reuse (evaluation → task)

`events` and `administration` are foundational apps every other app may import directly. Finding:
`PartThreadManager` (`control_layer/managers/part_thread_manager.py`) **reimplements** comment/file
row-creation that `events` already owns (`CommentHandler.add`, and it already correctly reuses
`FileHandler` for uploads). `events` also already writes machine comments the exact way we need —
`EventHandler._apply_machine_comment` (`event_handler.py:155`) does
`Comment.objects.create(activity_thread=…, is_human_made=False, …)`.

**Task:** delegate the *row creation* in `PartThreadManager` to the `events` handlers where it reduces
duplication, but **keep `PartThreadManager` as the thin thread-lifecycle adapter** — the nullable-thread
+ bootstrap-domain concern (§1) is parts-specific and must NOT leak into `events`. Net goal: one owner
of thread creation, less duplicated comment/dict code.

---

## 4. Struct migration (full detail in `struct_migration_plan.md`)

Build order (each isolated):

1. `PartRevisionHistoryStruct.from_id(part_id, *, eager_thread=False)` → wire `part_revisions`
   entrypoint (replaces the manual per-revision loop, revisions.py:44-59).
2. `PartSourcingStruct.from_id(part_id, *, eager_thread=False)` — one pass over `SupplierItem`,
   exposes `.supplier_items` **and** deduped `.manufacturers` → wire `part_supplier_items` (drops its
   direct `PartThreadManager` use).
3. `PartAliasIndexStruct.from_id(part_id, *, eager_supplier_items=False)` — net-new, no caller to
   migrate.
4. `PartDefinitionStruct.from_id(part_id)` — composes 1–3 + `PartStruct` (row lists eager, aliases /
   domains lazy per the usage analysis) → wire `part_detail`.
5. Delete `domain_structs/alias_struct.py` and `domain_structs/part_manufacturer_struct.py`.

Eager/lazy defaults are usage-derived — see the table in `struct_migration_plan.md §3`; do not
re-decide them.

---

## 5. Reverse structs + machine comments (the feature)

**Reverse-perspective structs** — resolve *up* from a child to the Part and gather threads. These are
what the write flows consume to find the Part + its thread:

- `RevisionActivityStruct` — from a `PartRevision`: its own thread items + base `Part` + the Part's
  thread.
- `SupplierItemActivityStruct` — from a `SupplierItem`: its own thread + `PartManufacturer` + base
  `Part` + base event/thread.

**Machine-comment behavior** (replaces the 4 dead narrator calls; earlier plan item 2):

- On **revision add** (`release_major` / `redline`), on **status change** (`set_status`), on
  **supplier item add**, and on **alias add** → write a machine comment (`is_human_made=False`) onto
  the **base Part's** activity thread (NOT onto the child's thread, NOT onto an Event).
- The narrator strings (`PartRevisionNarrator`, `SupplierItemNarrator`) become the comment bodies —
  finally giving them a real sink. `SupplierItemNarrator.vendor_revision_recorded` is currently
  never called; wire or drop it deliberately.
- The write flow resolves the Part + Part-thread via the reverse struct, then posts through
  `PartThreadManager` (bootstrap domain per §1). Mirror `EventHandler._apply_machine_comment`.

Result: the Part's timeline becomes the single audit feed for everything that happens to it and its
children.

---

## 6. Verification

- `python manage.py test app.parts` after each of §4's steps and after §5.
- Manual: create a part → confirm a machine comment appears on the Part thread; add a revision, a
  supplier item, an alias → each leaves a machine comment on the **Part** thread.
- `python dev_tools/delete_database_rebuild_models.py --seed` after adding the §1 per-variant default
  domains (seed-shape change → full reset per repo migration policy).

---

## 7. Suggested sequence

1. §1 per-variant default domains — seed + `thread_domain.py` helper + `PartThreadManager` bootstrap
   (decided; build it first, everything below depends on it).
2. §5 machine-comment sink + reverse structs (delivers the feature you asked for) — depends on §1.
3. §4 struct migration + dead-struct deletion (cleanup + PartDefinitionStruct).
4. §3 base-app delegation (opportunistic dedup, lowest risk to defer).
