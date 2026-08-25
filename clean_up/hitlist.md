# Hand-rolled UI hitlist — gallery / comments / files

Companion to the thread-component inventory artifact. Each row below is a
**divergent, hand-rolled implementation** of a pattern that already exists
once, canonically, in `events` (`gallery_card.html`, `comments_card.html` +
`comment_row.html`, `files_card.html` / `direct_attachments_card.html`).
Canonical fragments and the one other properly-reused component
(`parts/_library_section.html`, which already uses `<file-browser>`) are
**not** listed — nothing to fix there.

Pick a real id from your seeded data first (e.g. open `/assets/assets/` or
`/parts/` and click into any row) — the routes below use `<id>` as a
placeholder.

---

## Gallery

### 1. Asset detail — inline carousel copy
- **Component:** image gallery block inside the asset detail page
- **File:** [app/assets/templates/assets/assets/detail.html:71-89](app/assets/templates/assets/assets/detail.html#L71-L89)
- **Summary:** Copy-pastes the same `<image-carousel>` + `<carousel-preview-items>` markup the canonical `gallery_card.html` fragment already provides, instead of including it. Read-only; links out to the images-management page (#2) to edit.
- **Route:** `GET /assets/assets/<id>/`

### 2. Asset images — bespoke grid, no shared components
- **Component:** full image-management page for an asset
- **File:** [app/assets/templates/assets/assets/images.html](app/assets/templates/assets/assets/images.html)
- **Summary:** Biggest outlier. Doesn't use `<image-carousel>` or `<file-browser>` at all — hand-rolled Bulma `columns is-multiline` grid with its own primary-image star button and per-tile delete form. Backed by a real `AssetImageManager`, so only the view diverges, not the data layer.
- **Route:** `GET /assets/assets/<id>/images/`

### 3. Part detail — inline carousel + custom primary/remove list
- **Component:** gallery card on the part detail page
- **File:** [app/parts/templates/parts/detail.html:66-105](app/parts/templates/parts/detail.html#L66-L105)
- **Summary:** Same `<image-carousel>` component, hand-copied again, plus a fourth distinct primary/remove UI pattern (a list of filename rows with star/delete buttons below the thumbstrip). Add-image flow uses a `<dialog>` modal.
- **Route:** `GET /parts/<id>/`

### 4. Supplier item — per-item carousel (repeated in a loop)
- **Component:** gallery block nested inside each supplier-item card
- **File:** [app/parts/templates/parts/supplier_items/by_part.html:47-66](app/parts/templates/parts/supplier_items/by_part.html#L47-L66)
- **Summary:** Same carousel markup a third time, this time inside a `<details>` disclosure per supplier item, looped over every item mapped to the part.
- **Route:** `GET /parts/<id>/supplier-items/`

### 5. Revision workbench — per-revision carousel (repeated in a loop)
- **Component:** gallery block nested inside each revision card
- **File:** [app/parts/templates/parts/revisions/workbench.html:52-65](app/parts/templates/parts/revisions/workbench.html#L52-L65)
- **Summary:** Same carousel markup a fourth time, looped over every revision of the part.
- **Route:** `GET /parts/<id>/revisions/`

---

## Comments / threads

### 6. Part detail — plain-form comments
- **Component:** comment thread on the part detail page
- **File:** [app/parts/templates/parts/detail.html:107-119](app/parts/templates/parts/detail.html#L107-L119)
- **Summary:** Real `events.Comment` rows via `part_thread_manager.py`, but rendered as a bare `<p>` loop with a plain full-page-POST `<form>`. No HTMX, no Human/All/Machine filter, no edit/delete, no per-comment attachments — all of which the canonical `comments_card.html` + `comment_row.html` already provide.
- **Route:** `GET /parts/<id>/` · form posts to `POST /parts/<id>/comments/`

### 7. Supplier item — plain-form comments (repeated in a loop)
- **Component:** comment thread nested inside each supplier-item card
- **File:** [app/parts/templates/parts/supplier_items/by_part.html:68-116](app/parts/templates/parts/supplier_items/by_part.html#L68-L116)
- **Summary:** Same pattern as #6, duplicated inside the per-item `<details>` block.
- **Route:** `GET /parts/<id>/supplier-items/` · form posts to `POST /parts/supplier-items/<item_id>/comments/`

### 8. Revision workbench — plain-form comments (repeated in a loop)
- **Component:** comment thread nested inside each revision card
- **File:** [app/parts/templates/parts/revisions/workbench.html:67-109](app/parts/templates/parts/revisions/workbench.html#L67-L109)
- **Summary:** Same pattern as #6/#7 a third time, looped over revisions.
- **Route:** `GET /parts/<id>/revisions/` · form posts to `POST /parts/<id>/revisions/<revision_id>/comments/`

---

## File management (non-image documents)

### 9. Part detail — base/revision document link lists
- **Component:** "Base Part Documents" and "Current Revision Documents" rail cards
- **File:** [app/parts/templates/parts/detail.html:123-153](app/parts/templates/parts/detail.html#L123-L153)
- **Summary:** No `<file-browser>` — just bare `<a href="{% url 'file_download' %}">` rows with a Material icon, no thumbnails, no tiles/list toggle, no upload UI in this particular card (upload lives on the separate Library page, item #`_library_section.html` — not hand-rolled, excluded above).
- **Route:** `GET /parts/<id>/`

### 10. Supplier item — document link list (repeated in a loop)
- **Component:** "Files" rail card nested inside each supplier-item card
- **File:** [app/parts/templates/parts/supplier_items/by_part.html:119-131](app/parts/templates/parts/supplier_items/by_part.html#L119-L131)
- **Summary:** Same bare link-list pattern as #9, duplicated per supplier item.
- **Route:** `GET /parts/<id>/supplier-items/`

### 11. Revision workbench — document link list (repeated in a loop)
- **Component:** "Files" rail card nested inside each revision card
- **File:** [app/parts/templates/parts/revisions/workbench.html:112-124](app/parts/templates/parts/revisions/workbench.html#L112-L124)
- **Summary:** Same bare link-list pattern as #9/#10 a third time, looped over revisions.
- **Route:** `GET /parts/<id>/revisions/`

---

## Reference — what "correct" looks like

| Family | Canonical fragment | Where it's demoed |
| :--- | :--- | :--- |
| Gallery | `events/fragments/gallery_card.html` | `/events/kitchen-sink/` §3 |
| Comments | `events/fragments/comments_card.html` + `comment_row.html` | `/events/kitchen-sink/` §2 |
| Files | `events/fragments/files_card.html`, `direct_attachments_card.html` | `/events/kitchen-sink/` §4 |
| Files (already reused correctly) | `parts/_library_section.html` (wraps `<file-browser>`) | `GET /parts/<id>/library/` |
