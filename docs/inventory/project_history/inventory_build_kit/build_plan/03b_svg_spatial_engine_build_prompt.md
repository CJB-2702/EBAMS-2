# Build Prompt — Three-Tier SVG Spatial Engine (paste into a new session)

Copy everything below the line into a fresh Claude Code session in this repo to build the feature.
This file itself is a planning artifact (not the spec) — it exists so the decisions made in the
planning conversation aren't lost before the build session starts.

---

## Context

You're building the **Phase 3 SVG Spatial Engine** for the `ebams2` Inventory app — the piece that
lets a user click a shape on an uploaded storeroom map to navigate down to a physical storage
coordinate. This is a migration from a legacy Flask app (`~/REPOS/asset_management`) into this
Django/Bulma/HTMX codebase, plus a real architecture change beyond what the original migration kit
scoped. Read these first, in this order:

1. [`inventory_build_kit/build_plan/03_phase_svg_spatial_engine.md`](inventory_build_kit/build_plan/03_phase_svg_spatial_engine.md) — the current binding phase spec. **It is now out of date on scope (see "What changed" below) and needs rewriting as your first task, not just implementing as-is.**
2. [`inventory_build_kit/build_plan/03a_svg_spatial_engine_migration_review.md`](inventory_build_kit/build_plan/03a_svg_spatial_engine_migration_review.md) — full old-app source map, discrepancy notes, and a 19-item port/rework/drop checklist. Also needs its "item 15 dropped" line corrected (see below).
3. [`fable_decisions.md`](fable_decisions.md) — read FD-17, FD-22, FD-23, FD-24, FD-25 in full. **FD-22 and FD-24 are superseded by this build** — write a new FD entry (next number after the current highest) documenting the supersession; don't delete or silently rewrite the old FD-22/24 text, mark them superseded and point at the new entry, per this repo's decision-log convention.
4. [`inventory_build_kit/new_system/svg_gui_mapping_migration.md`](inventory_build_kit/new_system/svg_gui_mapping_migration.md) — original migration starting point (still useful for the sanitization/HTMX-injection mechanics, just not the single-tier scope).
5. [`inventory_build_kit/build_plan/09_ui_review_map.md`](inventory_build_kit/build_plan/09_ui_review_map.md) pages 1–4 — old-vs-new page-by-page UI verdicts for this area.
6. `harness/Architecture/patterns/model_patterns.md`, `harness/Architecture/patterns/oop_control_patterns.md` — this project's model/control-layer rules (no business logic on models, `Struct`/`Context`/`Factory`/`Manager`/`Guard` suffix vocabulary) apply to everything below.

Also read the docs on the events-app attachment system before writing any gallery code:
[`docs/events.md`](docs/events.md), and study `app/assets/models/core/asset.py` /
`app/assets/models/core/asset_model.py` for the `photo_gallery` (`events.FileSet`
`OneToOneField`) + `primary_image` (`events.Attachment` `FK`) pattern driven by
`app/events/control_layer/managers/gallery_manager.py::GalleryManager`. That is the pattern to reuse
here, not a bespoke attach/detach implementation.

## What changed from the original kit scope (decided in the planning conversation, not yet written up anywhere else)

The original kit (`svg_gui_mapping_migration.md`) and FD-22 scoped **one SVG tier**: a Room map where
shapes match a `StorageLocation.display_code` exactly, or a `major_coord` prefix (drawer lists the
matching rows as text). That's now superseded. The actual requirement is **three tiers of image-driven
selection**:

1. **Warehouse → Room** — image grid of room thumbnails (each room's own map SVG, scaled). No schema
   change needed here — this already matches FD-24's "reuse the sanitized `svg_layout` inline" idea,
   just renamed to the gallery's current-attachment image instead of a raw `svg_layout` string.
2. **Room SVG → XY location** — click a shape on the room map → **exact match** to a `RoomLocation`
   (a new model, not currently in the schema — see below). No prefix-matching; every shape maps to
   exactly one `RoomLocation`.
3. **RoomLocation SVG → Z coordinate** — click a shape on *that XY location's own* picker image →
   **exact match** to a `StorageLocation`'s `atomic_coord`. This is the old app's dropped second SVG
   tier (`Location.bin_layout_svg` / `_bin_viewer.html` in the legacy app), explicitly un-deferred.

This means: **exact-match shape resolution at every tier**, not prefix-match-with-text-drawer-fallback.
The "drawer lists all locations under a rack prefix" idea from FD-22 is gone — replaced by a second
image.

## New/changed schema

**`app/inventory/models/topography/room.py`** (existing, already migrated — Phase 1/2 are built and
seeded in dev):
- Remove `svg_layout = models.TextField(blank=True)`.
- Add `photo_gallery` (`OneToOneField → events.FileSet`, nullable, lazily created) and
  `current_layout` (`ForeignKey → events.Attachment`, nullable) — mirror `Asset.photo_gallery` /
  `Asset.primary_image` field shape and naming convention, but name them for layout semantics
  (`current_layout` rather than `primary_image` reads better here — use your judgment, just be
  internally consistent with `RoomLocation` below).

**New `app/inventory/models/topography/room_location.py`** (`RoomLocation`):
- `room` FK (`CASCADE`), `major_coord`, `minor_coord` (same zero-pad convention as today's
  `StorageLocation` fields), `display_code` (XY only, e.g. `"0005-0002"`), `is_active`.
- Same gallery pattern as Room: `photo_gallery` (`events.FileSet`) + `current_layout`
  (`events.Attachment`) for its own Z-picker SVG.
- Unique constraint on `(room, major_coord, minor_coord)`.
- Needs `AuditFieldsMixin` like the other topography models.

**`app/inventory/models/topography/storage_location.py`** (existing, already migrated):
- Replace the direct `room` FK + `major_coord`/`minor_coord` fields with a single `room_location` FK
  (`CASCADE`, `related_name="storage_locations"`).
- Keep `atomic_coord` and the full `display_code` (now `"<RoomLocation.display_code>-<atomic_coord>"`,
  i.e. still the 3-segment `major-minor-atomic` string end users see — only the *storage* of
  major/minor moves up a level, the display format is unchanged).
- Decide whether to keep a `room` convenience property (`self.room_location.room`) — check call sites
  before removing direct `.room` access; several already-built files reference
  `StorageLocation.major_coord`/`.minor_coord` directly (grep confirmed): `topography_manager.py`,
  `topography_context.py`, `topography_guard.py`, `storage_location_factory.py`,
  `storage_location_struct.py`, `room_struct.py`, `active_inventory.py`,
  `app/inventory/tests/test_topography.py`. All of these need updating for the new shape, not just the
  model file.

**`app/inventory/control_layer/adapters/coordinate_adaptor.py`**:
- `build_display_code(major_coord, minor_coord, atomic_coord)` currently builds the full 3-segment
  code in one call. Split into an XY-only builder (`RoomLocation.display_code`) and keep (or wrap) the
  full 3-segment builder for `StorageLocation.display_code`, so both tiers use the same zero-pad rule
  (`format_xyz_coordinate`) without duplicating it.

## New control-layer work

- `app/inventory/control_layer/adapters/room_svg_adapter.py` (does not exist yet): two shape-matching
  entrypoints — one resolving Room-SVG shape codes to `RoomLocation.display_code` (exact match), one
  resolving RoomLocation-SVG shape codes to `StorageLocation.atomic_coord` within that RoomLocation
  (exact match). Reuse `03_phase_svg_spatial_engine.md`'s sanitization spec (strip `<script>`,
  `<foreignObject>`, `on*` attrs, external `href`/`xlink:href`, reject >2MB) at **both** tiers — every
  uploaded SVG goes through the same sanitizer regardless of which tier it belongs to.
- `TopographyContext` (or a new `RoomLocationContext`, follow existing `Struct`/`Context`/`Factory`
  naming) needs an `upload_room_layout` (Room tier) and an equivalent for the RoomLocation tier —
  both produce a reconciliation struct (matched/unmatched/orphaned) per FD-23's existing spec, just
  applied once per tier instead of once total.
- `GalleryManager` reuse for attach/replace/history on both `Room.photo_gallery` and
  `RoomLocation.photo_gallery` — don't hand-roll attach/detach logic.
- Existing Phase 1 control-layer files listed above (`topography_manager.py`, etc.) need their
  `major_coord`/`minor_coord` access rewritten to go through `RoomLocation` instead of directly on
  `StorageLocation`.

## Frontend work

Three template/route layers matching the three tiers:
1. Warehouse detail room-cards grid — thumbnail = each Room's `current_layout` attachment, rendered
   inline (sanitized SVG, CSS-scaled), not a separate raster endpoint (still true per FD-24's original
   reasoning even though FD-24 itself is superseded on the "why" — the "no separate preview endpoint"
   conclusion still holds).
2. Room detail / spatial map page — click a RoomLocation shape → drawer shows that XY's info (or
   drills into tier 3 if it has a Z-picker image; if a RoomLocation has only one `StorageLocation`
   under it, skip straight to the stock drawer instead of forcing a pointless third click — use your
   judgment on this UX shortcut, it's not specified elsewhere).
3. RoomLocation Z-picker view (new — no old-app page name maps directly since it's essentially the
   old `_bin_viewer.html` promoted from a modal-less card to its own image tier) → click a Z shape →
   `StorageLocation` stock drawer.
All three follow the project's F5 rule, HTMX `format=` contract (FD-17: canonical URL +
`format=htmx-*`, no bespoke drawer routes), sharp corners, and "cards always render even when empty"
rule (see root `CLAUDE.md`).

## Dev fixture data (original task, now slotting into the 3-tier build)

Two real Inkscape SVGs exist in the legacy app's dev-seed data, already used by its own seed script
(`~/REPOS/asset_management/app/_debug/add_inventory_debugging_data.py`, look for
`LosAngelesMainStoreroom.svg` / `bin_layout_example.svg` around line 200):

- `~/REPOS/asset_management/app/_debug/data/LosAngelesMainStoreroom.svg` — Room-tier map. 7 shapes in
  a `<g inkscape:label="locations">` layer labeled `5-2`, `2-1`, `1-1`, `5-1`, `4-1`, `3-1`, `1-2`
  (major-minor, no zero-padding).
- `~/REPOS/asset_management/app/_debug/data/bin_layout_example.svg` — RoomLocation-tier Z-picker.
  9 shapes in a `<g inkscape:label="bins">` layer labeled `3-3`, `3-2`, `3-1`, `2-3`, `2-2`, `2-1`,
  `1-3`, `1-2`, `1-1`.

Tasks:
- Relabel every `inkscape:label` in both files to the new zero-padded convention
  (`format_xyz_coordinate` rule — 4-digit zero-pad numeric values) before committing them, e.g.
  `LosAngelesMainStoreroom.svg`'s `"5-2"` → `RoomLocation.display_code` `"0005-0002"`; pick **one**
  of the 7 room shapes to be the RoomLocation that actually has a Z-picker wired up (the others can be
  single-`StorageLocation` XYs with no second-tier image, to exercise the "skip tier 3" UX case above),
  and relabel `bin_layout_example.svg`'s 9 shapes to `atomic_coord` values (`"0001"`…`"0009"`, or
  reuse its existing `1-1`/`2-3`-style labels zero-padded per segment if you want the Z shapes to
  retain a 2-part sub-structure — your call, just be consistent with whatever `StorageLocation.
  atomic_coord` format the rest of Phase 1 already uses).
- Commit both relabeled files under `app/inventory/tests/fixtures/` (per `03_phase_svg_spatial_engine.
  md`'s existing test spec: "commit a small Inkscape fixture under app/inventory/tests/fixtures/") —
  used by the adapter/reconciliation tests.
- Wire one copy into `app/inventory/management/commands/seed_inventory_dev.py`: upload through the
  real `GalleryManager`/`TopographyContext` write path (not raw ORM `FileField` assignment — this repo's
  seeding convention, see that file's own docstring: "Everything is built through the real control
  layer... never raw ORM inserts") so a dev-seeded Room actually has a working spatial map end to end.

## Migration / reset

This is a schema change to already-migrated Phase 1 models (`StorageLocation`, `Room`). Per root
`CLAUDE.md`'s migration strategy: **do not** write an incremental migration — clear all
`app/inventory/migrations/` (and any other app whose migrations reference these FKs, check
`app/events` if a new relation is added there), run `python refresh_project.py`, reseed. No real dev
data is at risk.

## Docs to update as part of this build (not optional cleanup — part of the task)

- `fable_decisions.md` — new FD entry per "What changed" above.
- `03_phase_svg_spatial_engine.md` — rewrite the three-tier architecture in (it's the starter kit;
  corrected in place per this repo's two-kit convention, not left stale).
- `03a_svg_spatial_engine_migration_review.md` — checklist item 15 currently reads "**D**rop —
  Tech debt per FD-22"; change to reflect it's now in scope (tier 3), and update the FD-22/24
  references throughout to point at the new superseding FD entry.

## Acceptance checklist (extend `03_phase_svg_spatial_engine.md`'s existing one, don't replace it)

- [ ] Warehouse detail room-cards grid renders each room's thumbnail from its gallery `current_layout`, no separate preview endpoint.
- [ ] Room detail: clicking a shape resolves to exactly one `RoomLocation` (no prefix/multi-match ambiguity).
- [ ] RoomLocation with a Z-picker image: clicking a shape resolves to exactly one `StorageLocation`.
- [ ] RoomLocation with no Z-picker image and exactly one child `StorageLocation`: drawer shows stock directly, no dead-end third click.
- [ ] Sanitization (FD-25's spec) applies identically to Room-tier and RoomLocation-tier uploads.
- [ ] Upload-then-reconcile screen exists at both tiers, matching FD-23's existing spec (matched/unmatched/orphaned).
- [ ] `refresh_project.py` run cleanly; `seed_inventory_dev.py` produces a Room with a real, working two-image spatial map.
- [ ] Old Phase 1 tests (`test_topography.py`) updated and green against the new `RoomLocation` shape.
- [ ] New adapter/reconciliation tests using the two relabeled fixture SVGs.
- [ ] `dev_tools/memory.md` line added per repo convention.
