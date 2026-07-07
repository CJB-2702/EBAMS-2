# Existing Seams Audit

What already exists in the codebase that this kit must reuse or stay clear of. Audited
2026-06-23. This kit is **mostly greenfield**, but two existing systems are load-bearing for
its design.

---

## 1. Asset Manufacturers — `app/assets/models/core/manufacturer.py`

```python
class Manufacturer(AuditFieldsMixin):
    """Company that produces asset models. Extracted from old MakeModel.make."""
    name = CharField(max_length=200, unique=True)
    code = CharField(max_length=50, unique=True, null=True, blank=True)
    website = URLField(null=True, unique=True, blank=True)
    is_active = BooleanField(default=True)
    class Meta: db_table = "manufacturer"
```

- This is the **asset** manufacturer registry — referenced by asset models, on the hot path of
  asset lookups, and expected to stay **small**.
- **Decision ([D2](decisions.md)):** do **not** reuse this for supplier items. Create a
  separate `parts.PartManufacturer`. The future option of merging or pointing one at the other
  is deferred (OQ4).
- The new `PartManufacturer` mirrors this shape (`name`, `code`, `website`, `is_active`) so a
  future merge is mechanically easy.

---

## 2. Events file-management system — `app/events/`

The events app already provides everything the kit needs for "Documents", so no parts-local
file table is created ([D5](decisions.md)).

### `events.File` — `app/events/models/file.py`
- UUID7 PK, Django `FileField` (`upload_to="events/files/%Y/%m/"`), `original_filename`,
  `file_size`, `mime_type`, `description`, `tags` (JSON), soft-delete.
- Extension allow-list (`documents`, `images`, `archives`, `data`, `code`), icon mapping,
  `is_image()` / `is_text_preview()` / `get_icon_class()` helpers. 100 MB cap.
- Created via a `FileHandler` (not on the model); `FileContext` owns the delete cascade.

### `events.Attachment` — `app/events/models/attachment.py`
- Links a `File` to a **thread** (`events.ActivityThread`, on_delete CASCADE), optionally to a
  `Comment` (SET_NULL), `file` FK is PROTECT.
- `attachment_type` ∈ {`image`, `document`, `video`}, `caption`, `display_order`.
- `AttachmentManager.active()` filters soft-deleted.

### `events.FileSet` proxy — `app/events/models/file_set_proxy.py`
- A proxy over the shared `event` table representing a **bag of files that is not a real
  event** — exactly the "document registry with no lifecycle of its own" need.

### Control layer — `app/events/control_layer/`
- `file_context.py`, `handlers/file_handler.py`, `adapters/`, `policies/` already exist.

**How the kit uses it.** Each revision row (Part or Supplier Item) owns a `FileSet` thread;
its documents are `Attachment` rows on that thread, pointing at `events.File` records. The
revision exposes "its documents" by reading the active attachments of its FileSet. Because the
revision is point-in-time, freezing the revision freezes its document set.

> **Caveat / open seam (OQ1).** `Attachment.thread` is a hard FK to `ActivityThread`. Binding
> a revision to a FileSet can be done as (a) a direct FK `PartRevision.file_set →
> events.ActivityThread`, (b) a thin parts-side join, or (c) attaching via a content reference.
> The data plans assume **(a)** for clarity; confirm during review before building Phase 1's
> document step.

---

## 3. Layered structure to follow

The new `app/parts/` mirrors existing sub-apps (e.g. `app/assets/`):

```
app/parts/
  presentation_layer/{entrypoints,search,tools}/
  control_layer/{adapters,domain_structs,factories,managers,handlers,guards,narrators,orchestrators}/
  models/{core,revisions,...}/
  templates/parts/
  urls.py
```

Control patterns and the suffix vocabulary are defined in
[`docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md`](../docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md).
The `app/assets/control_layer/` tree is the closest working reference for Contexts, Structs,
Factories, Adapters, and Narrators.
