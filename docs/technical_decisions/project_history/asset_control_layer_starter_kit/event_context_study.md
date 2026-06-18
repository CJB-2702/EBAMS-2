# Event Context Study

> The user named the event context **"the core of the application"** and asked
> that it always be considered. This document compares the old `EventContext`
> against the new `events` app and defines what the asset migration must add to
> it. Read before Phase 1.

## 1. What the old `EventContext` did

Old file: `app/business/core/event_context.py`. One class wrapping a single
`Event` and owning **two responsibilities**:

1. **Lifecycle events** — *other* contexts (`AssetContext`, `MakeModelContext`)
   created `Event` rows directly (`Event(event_type='Asset Created', asset_id=…,
   major_location_id=…)`). The `Event` model carried a direct `asset_id` and
   `major_location_id`.
2. **Comment & attachment threads** — `EventContext` itself handled:
   - `add_comment`, `add_comment_with_attachments`, `add_attachment`
   - `edit_comment` (creates a new comment linked via `previous_comment_id`,
     marks the old one `user_viewable='edit'`)
   - `delete_comment` (soft delete via `user_viewable='deleted'`)
   - edit-history traversal (`get_comment_edits`, `get_comment_edit_history`)
   - human-vs-machine filtering (`is_human_made`)

## 2. What the new `events` app already provides

The new app is **far richer** than the old `EventContext` and already
implements—in better-factored form—almost everything above:

| Old responsibility | New home (already built) |
| :--- | :--- |
| Create event | `control_layer/handlers/event_handler.py` → `EventHandler.create(post_data)` |
| Edit event + field-diff audit | `EventHandler.edit()` (shadow comment = full diff, soft-deleted; machine comment = visible state-change note) |
| Add comment / attachments | `handlers/comment_handler.py`, `handlers/file_handler.py`, `comment_context.py`, `file_context.py` |
| Edit/delete comment, revisions | `CommentHandler` + `Comment.revision` / `deleted_at` (replaces `user_viewable` string flags) |
| Human vs machine comments | `Comment.is_human_made` |
| Stateful per-event entry point | `control_layer/event_context.py` → `EventContext(event_id, actor)` with `edit/add_comment/add_attachment/delete` |
| Read aggregates | `domain_structs/event_super_struct.py`, `event_detail_struct.py`, `presentation_layer/search/event_search.py` |
| Authorization | `control_layer/policies/thread_policy.py`; `Event.objects.visible_to(user)` (domain-scoped) |

**Conclusion:** the old `EventContext` comment/attachment logic is **superseded**
— do **not** port it into `app/assets`. Asset code consumes the events app; it
does not reimplement threads.

## 3. The structural gap the migration must close

The old `Event` had a **direct `asset_id`**. The new `Event` is **generic and
domain-scoped**, and the asset linkage is *deliberately reserved for the assets
app*. Evidence — `app/events/models/details/asset_management.py`:

```python
class AssetManagementDetail(Event):
    """Detail table for event_type='asset_management'.
    Asset-specific fields will be added here once the assets module is built.
    The asset <-> event M2M table lives in app/assets — not here."""
```

So two things must be **added by this migration**:

### 3a. An asset ↔ event link (new model in `app/assets/models`)

The old one-event-one-asset FK becomes a join owned by the assets app. Proposed
shape (confirm during Phase 1 design):

```
AssetEvent (db_table = "asset_event")
  asset  FK → assets.Asset      (CASCADE, related_name="event_links")
  event  FK → events.Event      (PROTECT,  related_name="asset_links")
  role   CharField (optional: "lifecycle" | "maintenance" | …) — or omit at first
  audit fields
  UniqueConstraint(asset, event)
```

> This is a **schema addition** → triggers the full DB-reset migration workflow
> (`/db-rebuild`). It is the one model this kit adds that the new repo has not
> already built. Open design question for Phase 1: M2M vs. a nullable FK on
> `AssetManagementDetail`. The reserved comment implies the assets app owns it,
> which favors a join table in `app/assets`.

### 3b. A lifecycle-eventing seam (control layer, `app/assets`)

A small assets-side helper (e.g. `AssetEventNarrator` + a thin call into the
events app) that, inside the asset workflow's transaction:

1. builds an event payload (`domain_id` = asset's domain, `event_type =
   asset_management`, `title`/`description` narrated, `status = COMPLETE` for an
   already-happened lifecycle fact);
2. creates the event via the events app (`EventHandler.create` or a direct
   `Event.objects.create` if we want it inside the asset's atomic block);
3. creates the `AssetEvent` link.

Old lifecycle events to reproduce (now domain-scoped, asset-linked):

| Old `event_type` | Trigger | New `title` (narrated) |
| :--- | :--- | :--- |
| `Asset Created` | asset creation orchestrator | "Asset '{name}' ({serial}) created" |
| `Model Created` | model creation factory | "Model '{model_name}{ subtype}' created" |
| `Asset Key Details Change` | `AssetContext.edit` on name/serial/domain/model | diff narration |
| *(meter change)* | `update_meters` | "Meter {i} set to {value}" (optional event; MeterHistory always written) |

## 4. Decisions to confirm in Phase 1

1. **Link shape:** `AssetEvent` join table in `app/assets` (recommended) vs.
   field on `AssetManagementDetail`.
2. **Transaction boundary:** create lifecycle events *inside* the asset
   workflow's `atomic()` (recommended — all-or-nothing) vs. via
   `EventHandler.create` (its own atomic block, so nested).
3. **Which lifecycle events are worth emitting** (creation + key edits: yes;
   meter changes: optional, since `MeterHistory` already audits them).
4. **Does `EventHandler` need a new path** for "system-emitted, already-complete"
   events (no `PLANNED` default, allow `event_type=asset_management`)? If so,
   that is the one *change to the events app* this work requires.

## 5. Net guidance for implementers

- **Reuse** the events app for all comment/attachment/thread behavior.
- **Add** only the asset↔event link and a thin assets-side eventing seam.
- **Extend** the events app **only** if §4.4 proves necessary; keep changes
  minimal and behind the events app's own handlers.
