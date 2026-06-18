# Events & Activity Thread Usage

How the assets domain attaches **comments and files** to its rows, and which
rows get an **event timeline** vs. a lightweight **activity thread**.

## 1. The concept

`ActivityThread` is a way to give any model **comments and/or attachments**
without paying for a full `Event` row's columns or semantics. Physically there is
**one table** (`event`); `thread_type` discriminates, and two boolean flags gate
capability. Before this, attaching photos to an asset meant bespoke file→asset
rows or abusing the comment/attachment structure; now a model points to a thread.

## 2. The capability gradient (flags, not classes)

All three tiers are the **same physical row**, differing only by `thread_type` +
two flags. `ThreadPolicy` enforces the flags (`can_add_comment`,
`can_attach_directly`) — no per-tier class is needed.

| Tier | `thread_type` | `allow_comments` | `allow_direct_attachments` | Holds |
| :--- | :--- | :---: | :---: | :--- |
| **Event** | `event` | ✓ | ✓ | event columns + comments + attachments |
| **Activity Thread** | `documentation` | ✓ | ✓ | comments + attachments |
| **File Set / Gallery** | `photo_gallery`, `file_set` | ✗ | ✓ | attachments only |

> **Decision (D2): "FileSet" is a role, not a new proxy class.** A `FileSet`
> alias would save no DB weight (same row) and add no enforcement (`ThreadPolicy`
> already blocks comments when `allow_comments=False`). Express attachments-only
> as an `ActivityThread` with `allow_comments=False`, optionally under a new
> `FILE_SET` `thread_type` value for naming clarity. See
> [`decisions.md`](decisions.md) D2. To reverse: add a `FileSet(Event)` proxy
> mirroring `activity_thread_proxy.py` with its own manager + a save-time
> `allow_comments=False` invariant.

## 3. How a model "has" a thread

A One-to-One (or FK) from the model to `ActivityThread`, created **before** the
owner row, inside the owner's creation transaction (as `Asset` already does):

```python
gallery = ActivityThread.objects.create(
    thread_type=ActivityThreadType.PHOTO_GALLERY,   # or FILE_SET
    allow_comments=False, allow_direct_attachments=True,
    domain_id=owner_domain_id, created_by=actor, updated_by=actor,
)
# owner.<thread_field> = gallery
```

Each new O2O thread field is a **schema change** → `/db-rebuild`.

## 4. Per-model outline

**Legend** — *Event*: actions on the row emit events on the asset timeline (via
the Phase-1 `AssetEvent` link); *Thread*: comments+attachments;
*FileSet*: attachments-only; *—*: none.

### Core
| Model | Event timeline? | Thread / FileSet | Rationale |
| :--- | :--- | :--- | :--- |
| **Asset** | **Yes** (created, key edits — `AssetEvent`) | **FileSet** `photo_gallery` (built) + **Thread** `documentation` (built) | Photos need no discussion; docs do. Both O2O already on the model. |
| **AssetModel** | creation event | **Thread** `documentation` (datasheets/manuals) + optional **FileSet** product photos | Shared product definition; spec docs benefit from notes. |
| **AssetClass** | — | optional **Thread** (class standards/policies) | Low priority; only if class-level docs are real. |
| **Manufacturer** | — | optional **FileSet** (catalogs/logos) | Reference media only. |
| **MeterHistory** | optional event on change | **—** | It *is* a history row; don't attach a thread. |
| **AssetImage** | — | **— (see §5 overlap)** | Likely superseded by the Asset photo-gallery FileSet. |

### Details
| Model | Event? | Thread / FileSet | Rationale |
| :--- | :--- | :--- | :--- |
| **PurchaseInfo** | — | optional **FileSet** (receipts, PO scans) | Documents attach; no discussion. |
| **VehicleRegistration** | — | optional **FileSet** (registration scan) | Document evidence. |
| **SmogRecord** | — | optional **FileSet** (certificate scan) | Document evidence. |
| **ModelInfo** | — | — (covered by AssetModel doc thread) | Avoid per-detail thread sprawl. |
| **EmissionsInfo** | — | optional **FileSet** (certification docs) | Compliance evidence. |

### Configurations
| Model | Event? | Thread / FileSet | Rationale |
| :--- | :--- | :--- | :--- |
| **ConfigurationTemplate** | creation event | **Thread** (build instructions, diagrams) | Engineering discussion + drawings. |
| **DefinedModification** | — | **Thread** (catalog-level standard procedure/refs) | Reusable reference docs + notes. |
| **ActualModification** | event on apply (asset timeline) | **Thread** (comments + attachments) | **User's example:** record key documentation and notes about the modification on a specific asset. |
| **AssetConfiguration** | event on assign/document | optional **FileSet** (sign-off evidence) | Lifecycle is the event; evidence is files. |
| **TemplateChild / TemplateModification** | — | **—** | Pure junctions. |

### Capabilities
| Model | Event? | Thread / FileSet | Rationale |
| :--- | :--- | :--- | :--- |
| **CapabilityDefinition** | — | optional **Thread** (how it's verified) | Catalog reference. |
| **AssetClassCapability / ModelCapability** | — | **—** | Template junctions. |
| **AssetCapability** | event on change | optional **FileSet** (proof photos) + has `notes` | Per-asset truth; evidence photos if verification matters. |

## 5. Known overlap to resolve (flag, not decide here)

`Asset` carries **both** a `photo_gallery` ActivityThread **and** the
`AssetImage` model (which FKs `events.File` directly). With the FileSet concept,
the gallery thread's attachments **are** the asset's images, making `AssetImage`
largely redundant. **Resolve during Phase 1/2:** either (a) drop/repurpose
`AssetImage` and read images from the gallery thread, or (b) keep `AssetImage`
purely as an ordering/primary-flag overlay over the thread's files. Don't build
both write paths.

## 6. Guidance for implementers

- Default to the **lightest** tier that fits: FileSet unless users genuinely need
  to discuss the item, then Thread; reserve Event for things that belong on the
  asset's timeline.
- Create threads **inside** the owner's creation transaction; never lazily.
- Gate all comment/attachment writes through `ThreadPolicy` — never assume a
  thread allows comments.
- Adding any new thread O2O/FK is a schema change → `/db-rebuild`.
- Prefer **one** thread per concern; avoid giving every detail row its own thread
  unless documents truly attach there (keeps the `event` table lean).
