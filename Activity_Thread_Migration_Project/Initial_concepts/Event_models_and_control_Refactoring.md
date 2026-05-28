# Event Models and Control Layer Refactoring

## Problem Statement

The current file, attachment, and event system has grown organically and is now misaligned — names don't match responsibilities, the base file model is domain-scoped when it should be shared, and there is no unified way to attach files or comments to core entities outside of the events domain.

---

## Current State (What Exists)

### `app/events/models/file.py` — `EventFile`
Raw uploaded file record. UUID7 primary key, `FileField`, mime type, soft-delete. Technically a generic file store but named after the events domain. Already referenced from `assets/` (via `AssetImage`), so it is de facto shared.

### `app/events/models/attachment.py` — `CommentAttachment`
**Misnamed file.** The module is called `attachment.py` but the class is `CommentAttachment`. It is not a generic attachment base — it is a join table that links `EventComment` to `EventFile`. Nothing else can use it.

### `app/assets/models/core/asset_image.py` — `AssetImage`
A primitive workaround. Links an `Asset` to an `EventFile` with an `is_primary` flag. It does not belong to the events system conceptually, yet it depends on `EventFile`. There is no equivalent for other asset-domain entities (e.g. `DefinedModification`, `CapabilityDefinition`).

### `app/events/models/comment.py` — `EventComment`
Immutable revision-tracked comment model. Edits produce new rows with `origin_id` pointing to the predecessor. Currently only attachable to an `Event`. There is no way to comment on an `Asset`, `DefinedModification`, or any other non-event entity.

## Changes to make
Make file names general for new items

No event file just file, no comment attachment just attachment no event comment just comment

All comments attachments and files are all now managed via the activity thread.

In my other documentation for this session I renamed events to event headers.
DO Not change the name of the events table to event headers just keep it as event
the event class now points to an activity feed.
Its critical that the event ID has the same ID as the activity feed and the activity feed is always created before an Event as the event now has a FK to an Activity feed. AI has a tendency to accidentally pick one or the other and I want it to be a feature that they both share a PK so in case of an accident its always possible to grab both


the asset class will now have multiple activity feeds with different goals
photo_gallery: holds a set of photos to display, only has machine comments to track photo history

Documentation: holds a set of files with documentation, comments are allowed, comments with attachments are allowed





---

## Files Affected (Known Blast Radius)

| File | Change |
|---|---|
| `app/events/models/file.py` | Rename class `EventFile` → `File` |
| `app/events/models/__init__.py` | Update exports |
| `app/events/models/attachment.py` | Rename file → `comment_attachment.py` |
| `app/assets/models/core/asset_image.py` | Replace with new `AssetAttachment` model |
| `app/events/control_layer/handlers/file_handler.py` | Update class references |
| `app/events/control_layer/file_context.py` | Update class references |
| `app/events/control_layer/domain_structs/` (3 files) | Update type annotations |
| `app/events/presentation_layer/entrypoints/files.py` | Update references |
| `app/events/admin.py` | Update registration |
| `app/assets/models/core/asset.py` | Add `anchor_event` FK |
| `app/assets/models/configurations/defined_modification.py` | Add `anchor_event` FK |
| `app/assets/models/capabilities/capability_definition.py` | Add `anchor_event` FK |
| `app/assets/models/configurations/configuration_template.py` | Add `anchor_event` FK |
| 8 docs files under `docs/Events/` | Update `EventFile` references |
