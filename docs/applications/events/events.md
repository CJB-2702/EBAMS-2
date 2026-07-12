# Events Domain

This document is the authoritative source of truth for the `app/events` sub-application. It covers entity design, mixin strategy, behavioural rules (shadow history, soft delete), domain scoping, and permission groups.

> **Asset linkage is out of scope for this build phase.** Events carry no asset reference. A future many-to-many table (event ↔ asset) will be built in `app/assets` and will reference events from that side. No asset field, import, or mention belongs in `app/events`.

---

## 0. Architectural prerequisite — custom user model

The project currently uses Django's default `auth.User`. Adding a `slug` field to the user (for URL identity) **requires a custom user model**.

**Action required before building events:**
1. Create a custom user model (`app/administration/models/user.py`) extending `AbstractUser`.
2. Add a `slug` field (8-char, unique).
3. Set `AUTH_USER_MODEL = "administration.User"` in `settings.py`.
4. Run a full DB reset.

All existing `ForeignKey(..., to=settings.AUTH_USER_MODEL)` references across the project will automatically point to the new model with no other changes needed.

---

## 1. Identity and URL strategy

| Model | PK type | URL identity | Notes |
| :--- | :--- | :--- | :--- |
| `User` (custom) | `BigAutoField` | `slug` (8-char) | Never expose integer ID in UI or URLs |
| `Event` | `BigAutoField` | hashid of PK (8-char) | See [pk_hashing_migration.md](pk_hashing_migration.md). |
| `EventComment` | `BigAutoField` | hashid of PK (8-char) | See [pk_hashing_migration.md](pk_hashing_migration.md). |
| `EventFile` | UUID7 | UUID7 itself | No separate slug |
| `CommentAttachment` | UUID7 | UUID7 itself | No separate slug |

Slug generation for `User` is 8-character URL-safe base64 (`secrets.token_urlsafe(6)`), unique, immutable, generated in `save()` if empty.

---

## 2. Mixin strategy

All mixins live in `app/administration/models/`.

### 2.1 `AuditFieldsMixin`

System-level record-keeping. Applied to every events model.

| Column | Type | Behaviour |
| :--- | :--- | :--- |
| `created_at` | `DateTimeField(auto_now_add=True)` | Set once on insert. |
| `updated_at` | `DateTimeField(auto_now=True)` | Updated on every `.save()`. |
| `created_by` | FK → `settings.AUTH_USER_MODEL` | User who created the row. Nullable. |
| `updated_by` | FK → `settings.AUTH_USER_MODEL` | User who last saved the row. Nullable. |

These are **system audit** fields — immutable from any application UI path.

### 2.2 `SoftDeleteMixin`

| Column | Type | Behaviour |
| :--- | :--- | :--- |
| `deleted_at` | `DateTimeField(null=True, blank=True)` | `None` = active. Non-null = soft-deleted at that timestamp. |

Exposes `is_deleted` as a property; all default querysets filter `deleted_at__isnull=True`.

### 2.3 `TraceableHistoryMixin`

Extends `AuditFieldsMixin`. Applied to `EventComment` only.

| Column | Type | Behaviour |
| :--- | :--- | :--- |
| `origin_id` | FK → `self` | Previous revision. `None` on first version. |
| `deleted_at` | `DateTimeField` | Soft delete; previous revisions always have this set. |
| `revision` | `IntegerField(default=1)` | 1-based counter. Each edit increments. |

### 2.4 Mixin summary per model

| Model | Applied mixins |
| :--- | :--- |
| `Event` | `AuditFieldsMixin`, `SoftDeleteMixin` |
| `EventComment` | `TraceableHistoryMixin` |
| `EventFile` | `AuditFieldsMixin`, `SoftDeleteMixin` |
| `CommentAttachment` | `AuditFieldsMixin`, `SoftDeleteMixin` |

---

## 3. Entities

### 3.1 `Event`

`BigAutoField` PK; URL identity via hashid.

Key fields: `domain` (FK → `Domain`, PROTECT, required), `title`, `description`, `event_type`, `status`, `priority`, `event_start`, `event_end`, plus audit and soft-delete fields from mixins.

`event_type` choices: `generic`, `system`, `administration`, `asset_management`, `inventory`, `dispatching`, `maintenance`.

`status` choices: `planned`, `in_progress`, `complete`, `cancelled`, `failed`, `skipped`, `blocked`. Status transitions are **free** — any value may transition to any other. The control layer applies the priority-clearing side effect when status transitions to `complete`, `cancelled`, `failed`, or `skipped`.

`priority` choices: `low`, `medium`, `high`, `critical`. Default `null`. Cleared on the priority-clearing status transitions.

### 3.2 `EventComment`

Comments are **immutable once saved**. Editing creates a new revision; the old one is soft-deleted. See [comment_auditing.md](comment_auditing.md).

Key fields: `event` (FK, CASCADE), `content`, `is_human_made` (True for user comments, False for machine-generated shadow records), plus `TraceableHistoryMixin` fields (`origin_id`, `revision`, `deleted_at`, audit).

### 3.3 `EventFile`

UUID7 PK; no slug. Stores uploaded file metadata. Other sub-apps that need file attachments import from `app/events`.

Key fields: `file` (`FileField`, upload path `events/files/%Y/%m/`), `original_filename`, `file_size`, `mime_type`, `description`, `tags` (`JSONField`), `is_technical_library` (placeholder — no logic yet), plus audit and soft-delete fields.

**Allowed extensions** (enforced in control layer, not model):

| Category | Extensions |
| :--- | :--- |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.webp`, `.svg` |
| Documents | `.pdf`, `.doc`, `.docx`, `.xls`, `.xlsx`, `.ppt`, `.pptx`, `.rtf` |
| Archives | `.zip`, `.rar`, `.7z`, `.tar`, `.gz` |
| Data / text | `.csv`, `.json`, `.xml`, `.sql`, `.html`, `.txt`, `.log`, `.data` |
| Code | `.cpp`, `.py`, `.java`, `.js`, `.css`, `.php` |

Maximum file size: 100 MB.

### 3.4 `CommentAttachment`

Join table linking `EventComment` to `EventFile`. UUID7 PK.

Key fields: `comment` (FK, CASCADE), `file` (FK, PROTECT), `attachment_type` (`image`/`document`/`video`), `caption`, `display_order`, plus audit and `deleted_at` (it is soft-deletable; see [comment_auditing.md](comment_auditing.md)).

> Files attach to comments only in this phase. Events have no direct file attachment. To attach a file to an event, the user adds a comment and attaches the file to that comment.

---

## 4. Behavioural rules

### 4.1 Soft delete — events

1. Set `deleted_at` on the `Event` row.
2. Do **not** cascade soft-delete to child comments — historical record is preserved.
3. Standard querysets filter `deleted_at__isnull=True`.
4. Users with `can_view_deleted_comments_events_attachments` may call a dedicated manager method to include soft-deleted rows.

### 4.2 Shadow history — event field edits

When any content field on `Event` is changed (title, description, event_type, status, priority, event_start, event_end), two operations run atomically:

1. Create an `EventComment` with `is_human_made=False`, `content`= JSON field diff payload, `deleted_at`=now (hidden by default), `revision=1`, `origin_id=None`.
2. Update the `Event` row with the new field values.

Additionally, when `status`, `event_start`, or `event_end` change, a **visible** machine comment is created in the timeline.

### 4.3 Comment edit model

Comments are never modified in place. Editing atomically:

1. Old comment: `deleted_at` set (soft-deleted).
2. New comment created: same `event`, `origin_id` = old id, `revision` += 1, `content` = new text, `is_human_made=True`, `deleted_at=None`, new slug.
3. Attachments carry forward: all `CommentAttachment` rows are duplicated onto the new comment; old links remain on the soft-deleted revision.

The active version in a revision chain is the one with `deleted_at=None`.

### 4.4 File soft delete

Deleting a file soft-deletes the `EventFile` row. Disk data is not immediately removed.

**Permission:** anyone who can edit the comment the file is attached to may delete that file.

**Effect on attachment links:** `CommentAttachment` rows referencing a soft-deleted file are treated as broken by the control layer and excluded from normal display.

---

## 5. Domain scoping

| Condition | Can see the event? |
| :--- | :--- |
| User's domain set includes the event's `domain` | Yes |
| User is the `created_by` of the event | Yes — regardless of domain membership |
| Neither | No |

All event querysets enforce this filter via an `EventQuerySet` manager method `visible_to(user)`:

`Q(domain__in=user_domains) | Q(created_by=user)`

Deleted events are excluded from standard querysets. Users with `can_view_deleted_comments_events_attachments` may request them via a separate manager method.

---

## 6. Permissions and access control

### 6.1 Default behaviour — all authenticated users

| Action | Condition |
| :--- | :--- |
| Create an event | Authenticated + belongs to the target domain |
| View events | Authenticated + domain membership (or creator) |
| Add a comment | Authenticated + can see the event |
| Add attachment to own comment | Authenticated + owns the comment |
| Edit own event (triggers shadow history) | `created_by == request.user` |
| Edit own comment (revision chain) | `created_by == request.user` |
| Delete a file on own comment | `created_by == request.user` on the comment |
| Delete own event | `created_by == request.user` + no human comments (`is_human_made=True`) from other users |

### 6.2 Permission groups

| Group | Grants |
| :--- | :--- |
| `default_event_permissions` | Codifies §6.1 as explicit Django permissions. |
| `can_edit_others_events` | Edit content fields on events not created by them, within their accessible domains. |
| `can_delete_any_event` | Soft-delete any event within their domain. |
| `can_edit_others_comments` | Edit comments not created by them. |
| `can_view_deleted_comments_events_attachments` | Query soft-deleted events, comments, attachments, and files. |

### 6.3 What permission groups do NOT do

Permission groups control **action gates** only — not data visibility. A user with `can_edit_others_events` may edit events in domains they belong to, not in domains they have no membership in. The domain filter is always enforced on top of any permission group check.

---

## 7. Out of scope for this phase

| Item | Deferred to |
| :--- | :--- |
| Asset ↔ Event many-to-many | `app/assets` (future) |
| Reply threading on comments | Future iteration |
| Audio / video file types | Left as a future implementation note |
| `is_technical_library` routing logic | Placeholder column only |
| Physical file purge on soft delete | Deferred — soft delete preserves data |
