# Phase 1 — Control Layer Plan: Internal Parts

Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../harness/Architecture/OOP_CONTROL_PATTERNS.md). Home:
`app/parts/control_layer/`. Revision model per [D4](../decisions.md); comments + documents reuse
the `events` thread system per [D5](../decisions.md) (events `Comment`/`Attachment`/`FileHandler`).

---

## `PartStruct` — aggregated read model

`domain_structs/part_struct.py`. Read-only; `to_dict()`. The shape any consumer gets from a base
Part id alone (proves [D3](../decisions.md)).

```
PartStruct(part, current_revision, revision_count)
  .from_id(part_id) -> "PartStruct | None"
  .to_dict() -> {id, part_number, name, description, part_type, is_active,
                 current_revision: {major, minor, major_name, minor_name, status,
                                    date_of_release}, revision_count}
```

- `current_revision` loaded via `ORDER BY major_revision_number DESC, minor_revision_number DESC`
  `.first()` ([D4](../decisions.md)) — **not** `max(sequence)`.

## `PartRevisionStruct` — single-revision read model

`domain_structs/part_revision_struct.py`. Read-only. Exposes the revision plus its thread's
comments and documents.

```
PartRevisionStruct(revision, comments, documents)
  .from_id(revision_id) -> "PartRevisionStruct | None"
  .to_dict() -> {sequence, major, minor, major_name, minor_name, status, date_of_release,
                 summary, notes,
                 documents:[{file_id, filename, icon, caption}],
                 comments:[{author, body, created_at}]}
```

---

## `PartContext` — entry point for one part

`part_context.py`. Stateful control object around a single base Part id.

```
PartContext(part_id, actor)
  # reads
  .struct() -> PartStruct
  .current_revision() -> PartRevision        # (major desc, minor desc).first()
  .revisions() -> list[PartRevision]         # ordered (major desc, minor desc)
  .documents(revision=None) -> list          # default: current revision's docs
  .comments(revision=None) -> list
  # writes (delegate to managers)
  @property revisions_manager -> PartRevisionManager
  @property thread -> PartThreadManager       # Part-level comments/docs
```

Delegates all writes to managers; never mutates models inline.

## `PartFactory` — stateless part creation

`factories/part_factory.py`. Class methods only.

```
PartFactory.create(data: PartCreateInput, actor) -> Part
```

Flow (one `transaction.atomic()`):
1. `PartValidator.check(...)` — `part_number` present + unique.
2. Create the `Part`.
3. **Auto-create the base revision** via `PartRevisionManager.release_major(...)`:
   `major_revision_number = 1`, `minor_revision_number = 0`, names null, `sequence` next,
   `date_of_release` = supplied/today, `status = DRAFT` (OQ3 → resolved: base rev always exists,
   `minor` NOT NULL default 0).
4. *(Phase 3 wires an orchestrator here to mirror `part_number` into an `INTERNAL` alias.)*

## `PartValidator`

`guards/part_validator.py`. `part_number` presence + uniqueness; field invariants. Single source
of truth so factory, seed, and future import agree.

---

## `PartRevisionManager` — the revision write path ([D4](../decisions.md))

`managers/part_revision_manager.py`. The **only** writer of revisions. Owns the numeric
allocation rules so the major/minor source-of-truth can never be set by hand inconsistently.

```
PartRevisionManager(part, actor)
  .release_major(*, summary, major_name=None, date_of_release=None, status=DRAFT) -> PartRevision
  .redline(*, major_number=None, minor_name=None, summary, date_of_release=None) -> PartRevision
  .set_status(revision_id, status) -> PartRevision
```

### `release_major(...)` flow
1. Inside the transaction: `next_major = (max major for part) + 1` (or `1` if none);
   `minor = 0`; `sequence = (max sequence for part) + 1`.
2. Create the `PartRevision` row (numbers are authoritative; `major_name` optional).
3. Narrator audit string (`PartRevisionNarrator.major_released`).

### `redline(major_number=None, ...)` flow
1. Default `major_number` = the **current** major (highest). Allows redlining an *older* major
   explicitly by passing its number.
2. `minor = (max minor for that major) + 1`; `sequence = max sequence + 1`;
   `status = REDLINE`.
3. Create row; narrator string (`PartRevisionNarrator.redline_issued`).

> Numbers are **append-only** — never reused or reordered. `sequence` follows
> `date_of_release`. Races on the `(part, major, minor)` / `(part, sequence)` allocation are
> guarded by `select_for_update` on the part's revisions plus the DB unique constraints (D4).

## Documents & comments — `PartThreadManager`

`managers/part_thread_manager.py`. A thin shared helper that fronts the events thread for **any**
parts entity (Part, PartRevision — and reused by Phase 2 for SupplierItem/its revisions). Lazily
creates the `events.ActivityThread`, then delegates to the events handlers.

```
PartThreadManager(owner, actor)        # owner = Part or PartRevision (has thread_id)
  .attach_document(uploaded_file, caption="") -> Attachment   # via events FileHandler + Attachment
  .detach_document(file_id) -> None
  .add_comment(body) -> Comment                                # via events Comment path
  .documents() -> list
  .comments() -> list
```

- `attach_document`: ensure `owner.thread` (create `ActivityThread` if null), create the
  `events.File` through the events **`FileHandler`**, then the `Attachment`
  (`attachment_type='document'`) on that thread.
- Keeps all parts↔events file/comment plumbing in **one** place.

## Domain access — `PartDomainManager` + `PartDomainTemplateHandler` ([D14](../decisions.md))

`managers/part_domain_manager.py`. The **only** writer of `PartDomainAccessMapping` rows and of
`Part.is_domain_limited`. Reuses the existing `administration.Domain` model — adds no domain table.

```
PartDomainManager(part, actor)
  .set_limited(flag: bool) -> Part                  # toggles is_domain_limited
  .add_domain(domain_id) -> PartDomainAccessMapping  # idempotent; reactivates if soft-removed
  .remove_domain(domain_id) -> None                  # soft-remove (is_active=False)
  .domains() -> list[Domain]                         # active mapped domains
```

`handlers/part_domain_template_handler.py`. Issues/copies a **whole domain set from a
`DomainTemplate`** onto the Part ([D14](../decisions.md) c) — mirrors the admin app's
`DomainTemplate → UserDomain` rebase.

```
PartDomainTemplateHandler(part, actor)
  .apply(template_id) -> list[PartDomainAccessMapping]
     # expand template's active DomainTemplateItem domains, reconcile the Part's
     # active mapping rows (add missing, soft-deactivate removed). Re-issuing re-bases.
     # Copies at apply time — no stored FK to the template (D14).
```

> **Modeling only.** Per [D11](../decisions.md)/[D14](../decisions.md), neither manager wires the
> read-side queryset *enforcement* (filtering Parts a user may not see) — that's the later RBAC pass.
> Read seams in `PartContext`/search carry a `# DOMAIN-SCOPE TODO (D14)` comment marking where the
> filter attaches.

## `PartRevisionNarrator`

`narrators/part_revision_narrator.py`. Human-readable strings, no writes.

```
major_released(part, rev) -> f"{part.part_number} rev {rev.major_revision_number} released"
redline_issued(part, rev) -> f"{part.part_number} rev {rev.major_revision_number}.{rev.minor_revision_number} redlined"
status_changed(part, rev, old, new) -> f"{part.part_number} rev {rev.major_revision_number}.{rev.minor_revision_number}: {old} → {new}"
```

---

## Delegation summary

```
create a part   ─▶ PartFactory.create(input, actor)
                     └▶ PartValidator.check()
                     └▶ transaction:
                          Part.objects.create()                    (the hub)
                          PartRevisionManager.release_major(major=1, minor=0, DRAFT)  (base rev)

new major rev   ─▶ PartContext(id).revisions_manager.release_major(summary, major_name="B")
                     └▶ next_major=max+1, minor=0, sequence=max+1   (numbers authoritative — D4)

a redline       ─▶ PartContext(id).revisions_manager.redline(major_number=1, minor_name="2")
                     └▶ minor=max_minor_for_major+1, status=REDLINE (current stays on higher major)

attach drawing  ─▶ PartContext(id).revisions_manager … then PartThreadManager(revision).attach_document(file)
                     └▶ ensure ActivityThread → events.FileHandler → Attachment   (D5)

comment on part ─▶ PartContext(id).thread.add_comment("...")        (Part-level thread — D5)

read a part     ─▶ PartContext(id).struct().to_dict()               (base id → full view;
                                                                      current rev by major/minor — D4)
```
