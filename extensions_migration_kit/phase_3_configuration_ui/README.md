# Phase 3 — Configuration UI + extension route-pattern contract

Make the assignment of extensions to asset classes and models a **real** UI (replacing
the current mock), and define the **interface/route grammar** every extension's pages
must follow — without building any individual extension's page bodies.

## Goal

An administrator can switch an extension on/off for an asset class or model through
`/detail_extensions/configuration/`, and that choice drives provisioning. The
per-extension URL grammar and the aggregate 360-panel exist as a **documented contract +
base routing scaffolding** that resolves `target`-derived paths; the page *bodies* for
each extension are explicitly deferred.

## In scope

- Real enablement CRUD UI under `/detail_extensions/configuration/` — over the three
  enablement tables. **Replaces** the mock `entrypoints/plugins.py` + `mock_data.py`.
- `detail_extensions/urls.py` + include in `config/urls.py`.
- The per-extension route grammar ([E6](../decisions.md)) implemented as a **base
  router** (`extension_router`) that validates `<extension-key>`, checks enablement, and
  derives the `<asset|model>` / `<assets|models>` segments from the descriptor's
  `target` — then dispatches to the extension's declared entrypoint (from its manifest).
- The aggregate 360-panel route `/detail_extensions/<asset|model>/<id>/?format=htmx-panel`
  as a contract + a working panel that lists enabled extensions as cards (each card
  links into the per-extension grammar).
- Real persisted **seed** enablement data for the new tables.

## Out of scope

- **Every per-extension page body** — the summary/search/detail/row pages for
  `purchase_info`, `smog_record`, etc. The kit defines the *slots and routing*; filling
  them is follow-on work per extension.
- New extension behavior, rules, or derived status.

## Dependencies

- **Phase 2 complete** — provisioning is signal-driven, state lives in
  `detail_extensions`, and assets is ignorant. The UI reads/writes only
  `detail_extensions` models + `assets` (read-only, for class/model pickers).

## Deliverables

- Config entrypoints + templates under `detail_extensions/presentation_layer/` +
  `detail_extensions/templates/`.
- `extension_router` base dispatch + the aggregate panel entrypoint.
- `detail_extensions/urls.py`; `config/urls.py` include.
- Deletion of the mock plugin entrypoints/urls/templates from `assets`.
- Seed enablement data.

## Exit criteria

- [ ] An admin can assign/unassign an extension to an asset class and to a model via
      `/detail_extensions/configuration/`, persisted to the enablement tables (no mock).
- [ ] A newly-assigned extension is picked up by provisioning (new assets get it;
      backfill fills existing ones).
- [ ] `/detail_extensions/<extension-key>/...` resolves with `target`-derived segments
      and 404s an unknown or not-enabled `<extension-key>`; the route grammar matches
      [E6](../decisions.md).
- [ ] `/detail_extensions/<asset|model>/<id>/?format=htmx-panel` renders a card per
      enabled extension for that owner; F5 (full reload) works.
- [ ] The mock `entrypoints/plugins.py`, `mock_data.py` (plugin parts), and the
      `assets/urls.py` plugin routes are gone.
- [ ] `seed_dev` creates real enablement rows; a rebuild reproduces the assignment set.
