# Phase 4 — Parts UI (persona-driven)

## Goal

Put a **thin Bulma + HTMX UI** over the now-correct control layer (Phases 1–3), shaped around
the four personas: a fast **technician lookup**, an **engineer** part/revision workbench, and a
**supply** mapping/ordering surface. No new domain tables — UI only.

## In scope

- A parts **hub / search** landing page (the technician's front door).
- Part **detail** view: identity, current revision, revision history, current documents, mapped
  supplier items.
- Engineer **work portals**: create part, append revision, set status, attach documents.
- Supply **work portals**: register manufacturer, map supplier item (with compatibility range), log a vendor revision (JSON comment).
- Presentation-layer **adaptors** (HTTP payload → control-layer input structs).
- Canonical URLs with `format=` density + `htmx-*` fragments, F5-safe ([D10](../decisions.md)).

## Out of scope

- Any data-model change (all done in 1–3).
- RBAC permission gates (personas = distinct views, not gates, this cut — [D11](../decisions.md), OQ5).
- The BOM and configuration-allowability tools (separate future kits — they consume Part id).

## Dependencies

- Phases 1–3 control layer + `PartSearch`. UI calls Contexts/Search only — never models directly.

## Deliverables

- [ ] `app/parts/urls.py` + `presentation_layer/entrypoints/` for parts, revisions, supplier
      items, manufacturers, search.
- [ ] `presentation_layer/adapters/` mapping form/HTMX payloads to `PartCreateInput` /
      `SupplierItemCreateInput` / revision inputs.
- [ ] Templates under `templates/parts/` following Bulma sharp-corner + `format=` conventions.
- [ ] Technician live-search (HTMX) resolving any number → Part.
- [ ] Engineer revision workbench (append/status/documents) over `PartRevisionManager`.
- [ ] Supply mapping portal over `SupplierItemFactory` / `SupplierVendorRevisionManager`.

## Exit criteria

- [ ] Every page renders correctly under a **plain full-page reload** (F5 rule); HTMX only adds
      interactivity on top.
- [ ] A technician can type any alias (internal/NSN/legacy/MPN) into the search and land on the
      resolved Part detail — end to end through `PartSearch`.
- [ ] An engineer can create a part, append a revision, change its status, and attach a document
      to a specific revision, entirely through the UI (which calls only the control layer).
- [ ] A supply user can register a manufacturer and map a supplier item to a part; the MPN
      becomes searchable immediately (Phase 3 auto-alias).
- [ ] No template or entrypoint imports a model or writes the DB directly — all writes go through
      a Context/Factory/Manager.
