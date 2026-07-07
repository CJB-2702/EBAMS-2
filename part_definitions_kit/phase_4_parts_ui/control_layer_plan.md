# Phase 4 — Control Layer Plan: Parts UI (adaptors & entrypoints)

Phase 4 adds **no domain logic** — only the presentation-layer glue that turns HTTP/HTMX
requests into control-layer calls. Suffix vocabulary per
[`OOP_CONTROL_PATTERNS`](../../docs/ARCHITECTURE/OOP_CONTROL_PATTERNS.md) and endpoint design per
[`ENDPOINT_PATTERNS`](../../docs/ARCHITECTURE/ENDPOINT_PATTERNS.md).

Home: `app/parts/presentation_layer/{entrypoints,search,adapters}/`.

---

## Adaptors — payload → input struct ([Adaptor] suffix)

`presentation_layer/adapters/`. Each maps a request's POST/HTMX payload to the validated input a
factory/manager expects. They **parse and shape only** — no DB writes, no business rules (those
live in the validators/factories).

```
PartCreateAdaptor.from_request(request) -> PartCreateInput
RevisionAppendAdaptor.from_request(request) -> RevisionAppendInput
SupplierItemCreateAdaptor.from_request(request) -> SupplierItemCreateInput
ManufacturerCreateAdaptor.from_request(request) -> ManufacturerCreateInput
```

Mirrors the existing `app/assets/control_layer/adapters/asset_create_adaptor.py` pattern.

---

## Entrypoints — OOP class-based views

`presentation_layer/entrypoints/`. One module per resource; canonical URL per resource with
`format=` density and `htmx-*` fragments ([D10](../decisions.md)). Each entrypoint:

- **reads** through a Context/Struct or `PartSearch`,
- **writes** by handing an adaptor's input to a Factory/Manager,
- never touches a model or the ORM directly (exit criterion).

| Entrypoint | Resource | Key actions |
| :--- | :--- | :--- |
| `parts.py` | `/parts/` hub, `/parts/<id>/` detail | list/search, detail render |
| `part_search.py` | `/parts/search/` | HTMX live search (`format=htmx-results`) |
| `revisions.py` | `/parts/<id>/revisions/` | append revision, set status, attach/detach doc |
| `manufacturers.py` | `/parts/manufacturers/` | list, create |
| `supplier_items.py` | `/parts/<id>/supplier-items/`, `/parts/supplier-items/<id>/` | map item (+ compatibility range), list, log vendor revisions (JSON comments) |

`urls.py` registers all routes under `parts/`. No `public_app` routes — authenticated-only
([D11](../decisions.md)).

---

## Delegation flow (representative)

```
POST /parts/<id>/revisions/  (engineer appends a revision)
  entrypoint
    └▶ RevisionAppendAdaptor.from_request(request) -> RevisionAppendInput
    └▶ PartContext(part_id, actor).revisions_manager.append(input...)   (control layer)
    └▶ render the revision fragment (format=htmx-...) or full detail (F5)

GET /parts/search/?term=MPN-1234&format=htmx-results  (technician)
  entrypoint
    └▶ PartSearch.query("MPN-1234") -> [PartStruct]    (Phase 3 resolver)
    └▶ render search-result rows (each links to /parts/<resolved_id>/)
```

No new Structs/Managers are introduced here — Phase 4 consumes the ones from Phases 1–3. The
only additions are Adaptors and Entrypoints (plus templates, covered in
[`ui_features_plan.md`](ui_features_plan.md)).
