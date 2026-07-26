# Phase 3 — Old → New Porting Checklist

Mostly additive (UI) + deletion of the mock. The seed change is the only schema-data
touch; a rebuild applies it.

## 1. Build real configuration CRUD

- [ ] `detail_extensions/control_layer/enablement_manager.py` → `EnablementManager`
      with `assign_to_class / unassign_from_class / assign_to_model / unassign_from_model`.
- [ ] `detail_extensions/control_layer/guards/enablement_assignment_guard.py` →
      `AssignmentPolicy` + `AssignmentValidator`.
- [ ] `detail_extensions/control_layer/adapters/enablement_assignment_adaptor.py` →
      `AssignmentAdaptor`.
- [ ] `presentation_layer/entrypoints/configuration.py` → thin `landing` + `assign_editor`.
- [ ] `presentation_layer/search/enablement_search.py` → "which extension assigned where".
- [ ] Templates under `templates/detail_extensions/configuration/`.

## 2. Build the route grammar + router

- [ ] `presentation_layer/entrypoints/extension_router.py` → key validation,
      target-derived segment resolution, enablement check, dispatch to manifest
      `entrypoints_module` **or** a shared placeholder view.
- [ ] `presentation_layer/entrypoints/aggregate_panel.py` → `panel` (card strip).
- [ ] `detail_extensions/urls.py` → wire all E6 routes; include in `config/urls.py`.

## 3. Delete the mock (clean cut)

- [ ] Delete `assets/presentation_layer/entrypoints/plugins.py`.
- [ ] Delete the plugin parts of `assets/presentation_layer/mock_data.py` (remove file
      if nothing else uses it).
- [ ] Remove the three plugin routes + imports from `assets/urls.py`.
- [ ] Move/replace `assets/templates/assets/plugins/*` under
      `detail_extensions/templates/` (or delete if superseded).

## 4. Real seed

- [ ] Add idempotent (`get_or_create`) enablement seed rows for the dev classes/models,
      reproducing the previously-mock assignment set against the new tables.

## 5. Rebuild + verify

- [ ] `python dev_tools/delete_database_rebuild_models.py --seed`.
- [ ] Assign an extension to a class in the UI → row persists; create a new asset of
      that class → it gets provisioned (Phase 2 flow); backfill an existing asset → gets it.
- [ ] Hit each per-extension slot URL → router validates key + target + enablement;
      placeholder renders; unknown/disabled key 404s.
- [ ] Load an asset's `?format=htmx-panel` → a card per enabled extension; full-page
      reload (F5) also works.

## Notes / gotchas

- **Router vs body split.** Resist implementing any single extension's real page here —
  that violates E6 scope. The placeholder is the deliverable for the slots.
- **`<asset|model>` vs `<extension-key>` collision.** The aggregate panel route's first
  segment is an owner-type word (`asset`/`model`); per-extension routes lead with
  `<extension-key>`. Reserve `asset`/`assets`/`model`/`models` as non-assignable
  extension keys (validate in the registry guard) so the URL resolver never ambiguates.
- **Permissions.** `AssignmentPolicy` must follow project RBAC + ownership scoping —
  consult the Admin Engineer persona / `harness/Authorization/rbac.md` when implementing.
