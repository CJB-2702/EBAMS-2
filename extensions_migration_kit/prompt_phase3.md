# Execution Prompt — Phase 3: configuration UI + extension route-pattern contract

**Recommended agent:** `/frontend-persona` (primary) + `/admin-persona` (for the
assignment Policy/RBAC) · **Model:** Sonnet 4.6
*(Bounded full-stack. Escalate the router's key/target/enablement dispatch to Opus only
if the `<asset|model>` vs `<extension-key>` URL disambiguation gets hairy.)*

---

## Paste this to start the phase

> `/frontend-persona`
>
> Execute **Phase 3** of the extensions migration kit: build the real assignment/
> configuration UI and define the per-extension route grammar as a contract. **Do not**
> build any individual extension's page body — only the config UI, the router, and the
> aggregate panel.
>
> **Prerequisite:** Phase 2 is complete (signal-driven provisioning; assets ignorant;
> state in `detail_extensions`).
>
> **Read first, in order:**
> - `extensions_migration_kit/decisions.md` (E6 = UI scope + the normalized URL grammar)
> - `extensions_migration_kit/phase_3_configuration_ui/README.md` (scope + exit criteria)
> - `extensions_migration_kit/phase_3_configuration_ui/ui_features_plan.md` (page inventory + built-vs-slot)
> - `extensions_migration_kit/phase_3_configuration_ui/control_layer_plan.md` (manager/adaptor/guard + router)
> - `extensions_migration_kit/phase_3_configuration_ui/data_relational_plan.md`
> - `extensions_migration_kit/phase_3_configuration_ui/old_to_new_migration.md` (the checklist)
> - House UI rules: `docs/UX_UI/UX_UI.md`, `docs/UX_UI/form_style_guide.md`,
>   `docs/ARCHITECTURE/HTMX_PATTERNS.md`, `docs/ARCHITECTURE/ENDPOINT_PATTERNS.md`
>
> **Do:** build the enablement CRUD (`EnablementManager` + `AssignmentValidator` +
> `AssignmentAdaptor`, thin entrypoints) under `/detail_extensions/configuration/`,
> replacing the **mock**; build the `extension_router` (validate `<extension-key>`,
> derive `asset|model` / `assets|models` from the descriptor `target`, check enablement,
> dispatch to the manifest entrypoint **or** a shared placeholder); build the aggregate
> `?format=htmx-panel`; wire `detail_extensions/urls.py` into `config/urls.py`; **delete**
> the mock `entrypoints/plugins.py`, the plugin parts of `mock_data.py`, and the plugin
> routes/templates in `assets`; add real idempotent enablement seed data. Follow the
> `format=` density rule (never combine density + `htmx-*`) and the F5 rule.
>
> **Switch to `/admin-persona`** when implementing `AssignmentPolicy` — it must follow
> project RBAC + ownership scoping (`docs/DOMAIN/admin/RBAC.md`).
>
> **Do NOT:** implement any single extension's real summary/search/detail/row page — the
> placeholder + routing is the deliverable for those slots (E6).
>
> **Finish:** full DB rebuild + seed. Verify the exit criteria, especially: an admin can
> assign/unassign in the UI (persisted, no mock); a new assignment is picked up by
> provisioning; per-extension slot URLs validate key+target+enablement and 404 correctly;
> the panel renders a card per enabled extension and survives F5.

---

## Reviewer pass (optional)

`/code-architect-persona` + `/code-review medium` — focus on thin-entrypoint compliance
(no writes in views), the router disambiguation guard, and template adherence to the
component library.
