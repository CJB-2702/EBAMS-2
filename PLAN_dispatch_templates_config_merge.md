# Dispatch templates: detail/draft-editor layout rework + configuration-template → model merge

## Context

The user reviewed the rendered `templates/1` detail page against a legacy screenshot and asked for
layout parity (a 2/3 pre-fill+manifest / 1/3 actions+meta grid) plus a redesigned draft editor
(one info card with a 3-column requirement row, a dedicated Model Requirements card, and a
left-heavy assignment layout for parts). While specifying the Model Requirements card they
surfaced a real domain-modeling correction: a configuration template only means something in the
context of a specific model (`ConfigurationTemplate.model` is already a mandatory FK), so it
should never be requested as a free-floating catalogue reference — it belongs as an optional
attribute of a model-requirement row instead ("1 F350 moving-truck configuration" vs "1 F350
towing configuration" are two rows for the same model, not a model row plus an unrelated
configuration-template row). They explicitly reject giving a full configuration without a model.

The exact same 5-requirement-kind shape (including a standalone configuration-template kind) is
mirrored on the dispatch-header side (`app/dispatching/models/requirements/`), which has no UI yet
(Pass 2) but shares identical tables built during the whole-module schema pass. Confirmed with the
user: fix both sides now, since the dispatch-header side is unused (zero data risk) and leaving it
inconsistent just means a future Pass-2 build rediscovers and re-fixes the same thing.

This is a schema change (drops two models, changes a uniqueness constraint), so it requires a full
`python refresh_project.py` per the project's migration-strategy rule — flagging before running it,
since it wipes the whole dev DB, not just dispatching.

## Key decision

`configuration_template` becomes a nullable FK **on** `AbstractModelRequirement` (the mixin shared
by `DispatchTemplateRequestedModel` and `DispatchRequestedModel`), validated (informally, at
add-time) to belong to the same model as the row. `AbstractConfigurationTemplateRequirement` and
both `*RequestedConfigurationTemplate` models are deleted. The uniqueness constraint on both
requested-model tables changes from `(revision/dispatch, model)` to
`(revision/dispatch, model, configuration_template)` — this is what allows two rows for the same
model differing only by configuration.

## 1. Schema

- `app/dispatching/models/abstract_mixins.py` — add `configuration_template` (FK to
  `assets.ConfigurationTemplate`, `on_delete=PROTECT`, `null=True, blank=True`, `related_name="+"`)
  to `AbstractModelRequirement`. Delete `AbstractConfigurationTemplateRequirement` (now unused).
- `app/dispatching/models/templates/template_requested_model.py` and
  `app/dispatching/models/requirements/requested_model.py` — widen the `UniqueConstraint` to
  `["revision"/"dispatch", "model", "configuration_template"]`.
- Delete `app/dispatching/models/templates/template_requested_configuration_template.py` and
  `app/dispatching/models/requirements/requested_configuration_template.py`.
- `app/dispatching/models/__init__.py` (and the two package `__init__.py`s under
  `models/templates/` and `models/requirements/` if they re-export individually) — drop the two
  deleted model imports/exports.

## 2. Control layer — templates

- `template_draft_session_adapter.py`: drop `"configuration_template"` from `_REQUIREMENT_KINDS`;
  `_requirement_row_from()` gains `configuration_template_id` under the existing
  `hasattr(row, "model_id")` branch; `_seed_from_head()`'s `related_name` map loses the
  `configuration_template` entry; `add_requirement()`'s field whitelist gains
  `configuration_template_id`.
- `template_revision_commit_manager.py`: drop the `"configuration_template"` entry from
  `_REQUIREMENT_MODELS`; when `kind == "model"`, pass `configuration_template_id` through to
  `create_kwargs` if present in the row.
- `template_views.py`: `_resolve_requirement_rows` drops the `configuration_template` lookup and
  resolves `configuration_template` objects onto the `model` rows instead (mirror the existing
  `objects_by_id` pattern, second lookup keyed by the model rows' `configuration_template_id`);
  `template_detail`'s `manifest` dict drops `"configuration_templates"`, and the `"models"` query
  gains `.select_related("model", "configuration_template")`; the `add_requirement` branch in
  `template_draft_update` reads an optional `configuration_template_id` POST field when
  `kind == "model"`; `template_draft_editor` — when `draft["template_id"]` is set, load that
  `DispatchTemplate` (`select_related("head_revision__created_by", "domain")`) into a new
  `editing_template` context var for the read-only info card (§6). Same for
  `draft["copied_from_revision_id"]` → `copied_from_revision` context var.

## 3. Control layer — dispatch header (mirrored fix, Pass 2, no UI yet)

- `requirement_manifest_editor.py`: drop `"configuration_template"` from `_REQUIREMENT_REGISTRY`;
  `add()` gains an optional `configuration_template_id` param passed through when `kind == "model"`.
- `dispatch_from_template_factory.py`: remove the `for config in
  revision.requested_configuration_templates.all(): ...` loop; the existing `for model_req in
  revision.requested_models.all(): ctx.requirements.add(kind="model", ...)` call passes
  `configuration_template_id=model_req.configuration_template_id` alongside.
- `dispatch_detail_struct.py`: drop the `requested_configuration_templates` field, its import, and
  its load-time query.

## 4. Search/pool views — cascading model → configuration picker

- `requirement_pool_search.py`: `search_configuration_templates(*, q="", model_id=None)` — filter
  by `model_id` when given.
- `requirement_pool_views.py`: `configuration_template_pool_search` reads an optional `model_id`
  GET param and passes it through.
- Draft editor's Model Requirements add-row: two `<search-dropdown>`s — model (existing, reused
  from `model_index`) and configuration (scoped via `hx-vals` reading the model dropdown's current
  value, following the existing `hx-vals` convention already used in
  `app/administration/templates/**/_*_dlb_only.html`). Empty/disabled state on the configuration
  picker until a model is chosen.

## 5. `detail.html` rework — 2/3 + 1/3 grid

Header simplifies to title + Live/Retired badge + breadcrumb (actions move into the right rail,
matching the legacy "Locked" badge + sidebar-actions shape).

**Left (2/3):**
- Pre-fill Fields card: Asset Class, Asset Subclass, Dispatch Scope, Activity Location, Estimated
  Meter Usage, Expected Number of People, Notes. (Domain stays where it already is — the header
  subtitle — since it's a lineage-level fact, not a revision pre-fill field; not duplicated here.)
- Required Skills table (Skill, Min Level, Count, Priority, Notes)
- Required Capabilities table (Capability, Priority, Notes)
- Required Models table (Model, **Configuration**, Quantity, Priority, Notes) — configuration is
  now a column here, not its own card.
- Modification Requirements table (kept — not in the legacy screenshot but real in this domain)
- Required Parts/Supplies table (Part, Quantity, Usage Notes) — **no** "Return Expected" column;
  that's a legacy rental-tracking concept this domain deliberately cut (materials raise real
  demands, not rental bookings), flagging rather than inventing a field that doesn't exist here.

**Right (1/3), top to bottom:**
- Template Info card: Template ID, Revision #, Created, Created By, Status badge
- Actions card: Edit — New Revision, Copy to New Template, and Retire/Reinstate (consolidated here
  from the current separate bottom card)
- Summary card: counts for Skills, Capabilities, Models, Modifications, Parts (no separate
  Configuration Templates count — merged into Models)

## 6. `draft_editor.html` rework

- If `editing_template` is set (draft edits an existing lineage) or `copied_from_revision` is set:
  a read-only "Template Info" card near the top — Template ID, Domain, revision being edited from,
  its created-by/at — clearly labeled as reference, not part of the editable draft. Skipped
  entirely for a brand-new template (nothing to show).
- One larger "Template Information" card: the existing pre-fill form, unchanged, **plus** below it
  in the same card a 3-column (`is-4/is-4/is-4`) row: Capability Requirements | Skill Requirements
  | Modification Requirements — same add-forms and lists as today, laid out side by side instead of
  stacked full-width cards.
- Separate "Model Requirements" card: add-row gains the configuration `<search-dropdown>` (§4);
  list rows show model, configuration (if any), qty, required/preferred tag, remove.
- Separate "Material Requirements" card, rebuilt as a left-heavy assignment layout: 2/3-width
  column holds the existing search+qty+notes add form, 1/3-width column lists added materials as
  small removable row-cards. This borrows the **visual shape** of
  `harness/UX_UI/search/list_management_patterns.md` §3 (Left-Heavy Assignment Card Pair), not its
  client-side-JS multi-select mechanics — this editor is session-authoritative and every other
  panel already uses the established POST → redirect → GET round trip; switching only this panel
  to pure client JS would break that consistency and the F5 rule.
- Commit card unchanged at the bottom.

## 7. Docs

- `dispatching_starter_kit/1_dispatch_templates.md`: correct wherever it describes
  configuration-template as its own requirement kind; record the new decision (nullable attribute
  of a model-requirement row; uniqueness is `(revision, model, configuration_template)`, not
  `(revision, model)`; rejected standalone configuration requirements because a configuration is
  meaningless without a model as its subject).
- Same correction, cross-referenced, in `2_dispatch.md` and/or `4_dispatch_line_items.md` wherever
  the mirrored dispatch-header requirement kinds are described (scope now covers both sides).
- `abstract_mixins.py` docstrings: document the new field on `AbstractModelRequirement`; remove the
  deleted mixin's docstring.
- Check `HANDOFF.md`'s decision table (row 7, templates) for a configuration-template-specific
  claim that needs correcting — update only if one exists.

## 8. Seed data

`seed_dispatching_dev.py` currently adds a standalone `configuration_template` requirement in the
Forklift template's second revision — that requirement kind is gone, so this **must** change, not
just optionally improve. Update it to attach the configuration template to the existing Forklift
model requirement row instead (once a model requirement exists on that template — currently it
doesn't, so add one first: an `8FGCU25` model row, then its second-revision edit attaches
`Standard Forklift Build` as that row's configuration). This keeps the seed demonstrating the new
shape end to end.

## 9. Rebuild and verification

- `./venv/bin/python manage.py check`
- Grep `app/dispatching/tests/*.py` for `configuration_template` usage before running the suite (a
  quick check turned up none currently, but re-verify after the model changes land) — run
  `./venv/bin/python manage.py test app.dispatching` and fix any fallout.
- Confirm with the user, then run `python refresh_project.py` — proves migrations regenerate
  cleanly from a wiped DB and `seed_dispatching_dev` runs end to end with the new shape.
- Playwright re-screenshot `templates`, `templates/<pk>`, and the draft-editor new/edit flows
  (scratchpad script already exists from the prior session — extend it) to confirm the new layouts
  render, and do one functional round trip: add a model requirement with a scoped configuration,
  commit, confirm the detail page's Models table shows model + configuration on one row.
