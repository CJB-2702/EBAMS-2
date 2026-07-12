---
type: "Skeleton Bundle"
title: "Events integration — skeleton bundle"
description: "For task types: integrate another sub-app with the events application (emit events, attach files via comments, consume BaseEventStruct, add a new event type)."
tags: [events, skeleton-bundle]
context_tier: 2
---

# Events integration — skeleton bundle

For task types: integrate another sub-app with the events application (emit events, attach files via comments, consume `BaseEventStruct`, add a new event type).

## Scan targets

- `app/events/control_layer/` — `event_context.py`, `comment_context.py`, handlers (`event_handler.py`, `comment_handler.py`, `file_handler.py`).
- `app/events/control_layer/domain_structs/` — `base_event_struct.py`, `comment_struct.py`, `base_event_super_struct.py`.
- `app/events/models/` — `Event`, `EventComment`, `EventFile`, `CommentAttachment`.
- `app/events/presentation_layer/entrypoints/` — entrypoint routing patterns.
- `app/utils/hashids.py` — the encoding utility that bridges integer PKs and URL hashes.
- `app/<target_app>/control_layer/` — where the calling code will live.

### Run codebase mapping script

Run the codebase mapping script against both `events` and the target application:
```bash
python dev_tools/get_models_and_control.py --application events
python dev_tools/get_models_and_control.py --application <target_app>
```

## Load alongside scan

- `docs/applications/events/events.md` — entity design, mixins, statuses, permissions.
- `docs/applications/events/event_context_design.md` — structs and contexts.
- `docs/applications/events/events_endpoints.md` — which endpoints use handlers vs contexts.
- `docs/applications/events/comment_auditing.md` — file/attachment lifecycle invariants.
- `docs/applications/events/pk_hashing_migration.md` — hashid boundary at the URL.
- `docs/Architecture/layer_rules.md` — calling-app boundary rules.

## Skip

- `app/events/templates/` — UI work is the UI bundle's job.
- `app/events/migrations/` — generated; do not hand-edit.

## Key reminders for events callers

- The control layer never sees hashids. Decoding is an entrypoint concern.
- Contexts coordinate cross-table writes (event delete → comment delete → orphan file check). Handlers own single-row writes.
- `EventContext` has no `create()` method — call `EventHandler.create()` first, then build a context from the returned row if further work is needed.
