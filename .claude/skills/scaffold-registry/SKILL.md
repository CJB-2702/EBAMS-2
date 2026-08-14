---
name: scaffold-registry
description: Scaffold a "simple registry" entity for this project — a small lookup-table model (like PartManufacturer or procurement.Vendor) with its own uniqueness guard, create manager, form adaptor, list/create entrypoint with htmx search, two templates, and URL routes. Use when adding a standalone lookup/reference table that other models will FK to (vendors, categories, statuses-as-data, external registries) and that needs a lightweight admin UI of its own.
---

# Scaffold a simple registry entity

A "simple registry" is this codebase's standard shape for a small, mostly-flat
lookup table that: (a) other models FK to, (b) needs create + search but not a
full CRUD/wizard surface, and (c) has 2-5 scalar fields with no nested
relations. `parts.PartManufacturer` is the original; `procurement.Vendor` was
scaffolded from it on 2026-08-09 as a second, independent instance of the same
shape (see `procurement_starter_kit/decisions.md`, D45 reversal, for why they
are deliberately NOT the same table). Treat `procurement.Vendor` as the
canonical reference to copy from — it is newer and slightly more consistent
than `PartManufacturer`.

## When NOT to use this

- The entity needs nested/child rows a user populates in the same sitting →
  that's a multi-step-flow wizard (`harness/UX_UI/design_patterns/multi_step_flows.md`),
  not a registry.
- The entity is edited in place (not just created) with any complexity beyond
  a create form → still doable by extending this pattern with an edit view,
  but check whether it actually needs editing at all first (many registries
  are create-only with an `is_active` soft-disable, like both `Vendor` and
  `PartManufacturer`).

## Inputs to gather before starting

Ask (or infer from the request) if not already clear:
1. **Owning app** — which `app/<app>/` does this belong to?
2. **Model name** — PascalCase singular, e.g. `Vendor`, `ShippingCarrier`.
3. **Fields** — beyond `name` (always present, unique) and `is_active`
   (always present, default True), what else? Keep it flat/scalar — no FKs,
   no nested writes. `code` (unique, optional) and `website` are common but
   not mandatory; ask, don't assume every registry needs them.
4. Whether anything in the app already needs to pick this entity from a
   `<search-dropdown>` (this tells you whether the htmx search endpoint is
   load-bearing now or just future-proofing).

## The seven files (copy these from `app/procurement/` and adapt)

Canonical originals to read first, in this order:

1. `app/procurement/models/purchasing/vendor.py` — the model. Copy the shape:
   `AuditFieldsMixin`, `name` unique, `code` unique/nullable, `is_active`,
   `Meta.db_table` + `ordering = ["name"]`, `__str__` returns `name`.
2. `app/procurement/control_layer/guards/vendor_uniqueness_guard.py` — a
   `Validator`-suffixed guard class with one `check(*, name, code, exclude_*_id=None) -> list[str]` classmethod.
3. `app/procurement/control_layer/managers/vendor_manager.py` — a
   `Manager`-suffixed class with one `create(*, data: dict, actor) -> Model`
   classmethod, wrapped in `transaction.atomic()`, calling the guard first and
   raising a matching `*ValidationError(Exception)`.
4. `app/procurement/control_layer/adapters/vendor_create_adaptor.py` — a
   `*CreateAdaptor` with a `from_post(post) -> dict` staticmethod that trims
   strings and coerces the checkbox.
5. `app/procurement/presentation_layer/entrypoints/vendors.py` — two views:
   `*_index` (list + `?format=htmx-search-results` branch returning `<li data-value="{pk}">{name}</li>` rows, matching the `<search-dropdown>` web component's contract) and `*_create` (GET form / POST via the manager+adaptor).
6. `app/procurement/templates/procurement/vendors/list.html` and `form.html`
   — copy verbatim and rename; both extend the owning app's `base.html`.
7. URL registration — add two `path()` entries (`<plural>/`, `<plural>/create/`)
   to the app's URL conf, named `<model>_index` / `<model>_create`.

Then:
- **Wire it into a picker**, if step 4 above said something needs one: point
  the `<search-dropdown hx-get="...">` at `{% url '<model>_index' %}?format=htmx-search-results`
  and the "missing one? register it" link at `{% url '<model>_create' %}`.
  See `app/procurement/templates/procurement/purchase_orders/create.html`
  (the "Vendor & header" card) for a working example of both.
- **Add a sidebar nav link** in the owning app's `base.html` if the registry
  is a first-class portal a user browses to directly (it usually is).
- **Register in the app's `models/__init__.py`** (`__all__` too) and confirm
  no other app needs an import-path change.

## After scaffolding

This is a schema change — follow the project's standard migration strategy
(`.claude/CLAUDE.md` §"Migration strategy"): do NOT hand-write a migration.
Run the `refresh-project` skill (full DB reset + reseed) instead.

If the registry needs dev seed data, add it to the owning app's
`seed_<app>_dev.py` command — usually a handful of `get_or_create`d rows an
idempotent seed command can build once and every other seed helper can then
reference by id.

## Known trap

Don't let two registries drift back together. The entire reason
`procurement.Vendor` exists as a *second* table instead of reusing
`parts.PartManufacturer` is that superficially-similar lookup tables can
represent genuinely different domain concepts (a vendor is who you buy from;
a manufacturer is who made the part — see D45's reversal for the full story).
Before reusing an existing registry for a new purpose, check whether the two
concepts can actually diverge in the real world. If they can, scaffold a new
one — don't grow a shared table to serve two masters.
