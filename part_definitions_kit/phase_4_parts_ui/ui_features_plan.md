# Phase 4 — UI Features & Page Inventory

Per the page-classification guide
([`how_to_plan_ui_features`](../../docs/starter_kit_process/how_to_plan_ui_features.md)): every
page is a **User View**, **Work Portal**, or **Navigation Page**. Bulma + HTMX, sharp corners,
canonical URL + `format=`, F5-safe ([D10](../decisions.md)). HTMX adds interactivity over a
server-rendered page that already works on reload.

---

## Page inventory

| Page | URL (canonical) | Classification | Persona | Goal |
| :--- | :--- | :--- | :--- | :--- |
| **Parts Hub & Search** | `/parts/` | Navigation | Technician (primary) | Front door: a prominent universal search box + recent/active parts; the "I have a number" entry. |
| **Live Search Results** | `/parts/search/?term=&format=htmx-results` | Navigation (fragment) | Technician | HTMX-incremental results; each row resolves to a Part and links to its detail. |
| **Part Detail** | `/parts/<id>/` | User View | Everyone | Identity (part number, name), **current revision** prominently, revision history, current documents, mapped supplier items. |
| **Create / Edit Part** | `/parts/new/`, `/parts/<id>/edit/` | Work Portal | Engineer | Form to establish/curate a part definition. |
| **Revision Workbench** | `/parts/<id>/revisions/` | Work Portal | Engineer | Append a revision, set status (draft/released/redline/obsolete), attach/detach documents to a specific revision. |
| **Revision Detail / Documents** | `/parts/<id>/revisions/<seq>/` | User View | Engineer, Technician | A single revision's full state + its document set (point-in-time). |
| **Manufacturer Registry** | `/parts/manufacturers/` | Navigation / Work Portal | Supply, Sourcing | List + create part manufacturers. |
| **Supplier Items for a Part** | `/parts/<id>/supplier-items/` | Work Portal | Supply | Map a new supplier item to the part; list existing options with their manufacturer + MPN. |
| **Supplier Item Detail** | `/parts/supplier-items/<id>/` | User View / Work Portal | Supply | Item identity, forward link to its internal Part, compatibility range, vendor revision history (JSON comments) + documents (datasheets, quotes) — [D13](../decisions.md). |

---

## Persona flows

- **Technician (find a part):** Hub → type any number → live results (HTMX) → Part Detail. One
  search box, all identifier types, always resolves to the internal Part (Phase 3).
- **Engineer (curate):** Part Detail → Revision Workbench → append revision / set status / attach
  document. Sees mapped supplier items read-only for interoperability context.
- **Supply (map & maintain):** Manufacturer Registry (ensure vendor exists) → Part Detail →
  Supplier Items → map item (MPN becomes searchable instantly, set compatibility range) → Supplier
  Item Detail → log a vendor revision (JSON comment) with datasheet/quote.

---

## HTMX contracts (examples)

| Interaction | Request | Response |
| :--- | :--- | :--- |
| Live search | `GET /parts/search/?term=…&format=htmx-results` | result-rows fragment |
| Append revision | `POST /parts/<id>/revisions/` (HTMX) | new revision row + updated "current" badge fragment |
| Attach document | `POST /parts/<id>/revisions/<seq>/documents/` (HTMX, multipart) | document chip fragment under that revision |
| Map supplier item | `POST /parts/<id>/supplier-items/` (HTMX) | supplier-item row fragment in the options list |

> Never combine a density value and an `htmx-*` value in one request (project rule). Each page
> renders fully on F5; the fragments above only swap a region of an already-valid page.

---

## Component reuse

- **Search bar:** `docs/UX_UI/component_library/searchbars` for the technician universal search.
- **Row cards / lists:** follow the assets list/detail patterns
  (`app/assets/templates/assets/...`) for revision rows and supplier-item options.
- **Document chips / file display:** reuse the events file-display components (the document data
  comes from the events system — [D5](../decisions.md)).
- **Forms / actions:** `docs/UX_UI/form_style_guide.md` for create/edit and revision portals.
- Sharp corners, no pill buttons, density via `format=` per `docs/UX_UI/UX_UI.md`.
