# Phase 2 — UI Features & Page Inventory

Page inventory for the asset-relationship surface. Classifications per
[`how_to_plan_ui_features`](../../docs/starter_kit_process/how_to_plan_ui_features.md):
**Navigation Page**, **User View**, **Work Portal**. Visual language per
[`UX_UI.md`](../../docs/UX_UI/UX_UI.md); the edit screen follows the
[Search Row Cards pattern](../../docs/UX_UI/Examples/search_row_cards_pattern.md);
sharp corners (`border-radius: 0`) throughout.

---

## HTTP path inventory

Canonical resource: `assets/<asset_id>/children/…`, where `<asset_id>` is the **parent** whose
children are being managed. Density rides `format=`; HTMX fragments use `format=htmx-*`; the
two are never combined in one request ([D6](../decisions.md)).

| # | Method | Path | Query / body | Purpose | Returns |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1 | GET | `/assets/assets/<id>/children/view` | `format=condensed\|medium\|large` | Read-only tree (subject + children, depth 2) | Full page |
| 2 | GET | `/assets/assets/<id>/children/edit` | `format=…` | Editable tree + search-to-attach bar | Full page |
| 3 | GET | `/assets/assets/<id>/children/expand` | `node=<child_id>&format=htmx-depth` | Load the next depth ring under a node | Card-stack fragment |
| 4 | GET | `/assets/assets/<id>/children/search` | `q=<text>&format=htmx-search-results` | Attachable-asset search for the attach bar | Candidate-card fragment |
| 5 | POST | `/assets/assets/<id>/children/attach` | body: `child_id` | Attach one asset as a child of `<id>` | Updated subtree fragment, or inline error |
| 6 | POST | `/assets/assets/<id>/children/detach` | body: `child_id` | Detach a child (→ its own root) | Updated subtree fragment, or inline error |

- Paths 5/6 keep the **parent** in the URL and carry the **child** in the POST body — the URL
  stays the single canonical parent resource.
- Path 1 doubles as "recenter": a child card's **View** links to that child's own
  `…/children/view`, walking down the tree.
- The **Asset Relationships** Configurations entry routes to a chooser, then to path 1 for the
  picked asset.
- All routes are authenticated; `AssetContext(<id>, request.user)` carries ownership scoping.

---

## Page inventory

| Page | Classification | Route | Goal |
| :--- | :--- | :--- | :--- |
| Asset Relationships hub | **Navigation Page** | Configurations index entry | Orient the user to relationship management; route to a chosen asset's children surface. |
| Children — View | **User View** | `assets/<id>/children/view` | Read an asset's sub-tree top-down; expand depth on demand. |
| Children — Edit | **Work Portal** | `assets/<id>/children/edit` | Restructure the group: detach children, search and attach new ones. |
| Depth ring (fragment) | *(HTMX fragment of View/Edit)* | `…/children/expand?node=<id>` | Load one more level under a node inline. |
| Attach search results (fragment) | *(HTMX fragment of Edit)* | `…/children/search?q=` | Return attachable assets as cards with an Attach action. |

---

## 1. Asset Relationships hub — Navigation Page

- A new card/link on the **Configurations index**
  ([`configurations.py`](../../app/assets/presentation_layer/entrypoints/configurations.py)),
  labelled **Asset Relationships**, matching the existing config-section styling.
- Lands the user on a chooser (reuse the asset list/search) → selecting an asset routes to its
  `children/view`. From a single asset's detail page, a "Manage relationships" action also
  deep-links here.
- **Goal:** make relationship management discoverable from the same hub as configurations and
  modifications.

---

## 2. Children — View (User View)

Read-only tree of the asset and its descendants.

**Layout**

- **Breadcrumb / ancestor strip** (from `AssetHierarchyStruct`): `Root › … › This Asset`, so
  the user knows where this node sits in the larger tree.
- **Subject header**: the current asset (name, class tag, serial, direct child count).
- **Tree body**: each child rendered as a **search row card**. Indentation/`depth_from_root`
  conveys nesting. Cards for nodes that have deeper children show an **Expand** control.
- **Density** via `format=` (`condensed` / `medium` / `large`).

**Row card anatomy** (read-only variant of the pattern):

```
+----------------------------------------------------------+----------+
| Pump-12  [Hydraulics]            depth 2 | 3 sub-assets   |  Expand  |
+----------------------------------------------------------+   (info) |
|  serial SN-4481 · status Active                          +----------+
+----------------------------------------------------------+   View   |
                                                            | (detail) |
                                                            +----------+
```

- **Expand** (info): HTMX `GET …/children/expand?node=<id>` → swaps the next ring of child
  cards in beneath this card; toggles to "Collapse". Default render depth = 2 (OQ1).
- **View** (navigation): link to that child's own `children/view` (recenter the tree on it)
  or to the asset detail page.

**F5 rule:** a plain reload renders the tree to the default depth server-side; Expand only
adds deeper rings.

---

## 3. Children — Edit (Work Portal)

Everything in View, plus mutation. This is the screen the prompt specified.

**Layout (top → bottom)**

1. Breadcrumb + subject header (as View).
2. **Editable tree** — each child is a search row card whose right action pane has:
   - **Expand** (info) — same HTMX depth load as View.
   - **Detach** (danger) — `POST …/children/detach`, confirm dialog
     ("Remove Pump-12 and its sub-assets from this group?"). On success the card (and its
     subtree) leaves the tree and the Phase 1 Event is written.
3. **Search-to-attach bar** (below the tree) — the "add to my current set" requirement:
   - A search input (`hx-get …/children/search`, `hx-trigger="keyup changed delay:300ms"`,
     `format=htmx-search-results`) renders results into a results panel.
   - Each result is a row card with an **Attach** action (success) →
     `POST …/children/attach` with `child_id`. On success the new child appears in the tree
     and the result disappears from the candidate list.
   - Results already exclude self / existing children / ancestors (search read).

**Edit row card anatomy** (full pattern — flush full-height action pane):

```
+----------------------------------------------------------+----------+
| Pump-12  [Hydraulics]            depth 2 | 3 sub-assets   |  Expand  |
+----------------------------------------------------------+  (info)  |
|  serial SN-4481 · status Active                          +----------+
|                                                          |  Detach  |
|                                                          | (danger) |
+----------------------------------------------------------+----------+
```

Attach-candidate card (in the search results panel):

```
+----------------------------------------------------------+----------+
| Valve-7  [Hydraulics]            no parent | 0 sub        |  Attach  |
+----------------------------------------------------------+(success) |
|  serial SN-9001 · status Active                          +----------+
+----------------------------------------------------------+----------+
```

**Error feedback:** an illegal attach/detach (self-parent or cycle per `RelationshipPolicy`)
swaps the manager's message into an inline error slot near the action; the tree is unchanged.
Cross-domain / cross-class attach is permitted and needs no warning.

---

## 4. Depth ring — HTMX fragment

- Trigger: **Expand** on any card.
- `GET assets/<id>/children/expand?node=<child_id>&format=htmx-depth` →
  `AssetTreeStruct.from_id(child_id, max_depth=1).level(1)` rendered as a stack of child
  cards, swapped in beneath the expanded card (`hx-target` the card's child slot,
  `hx-swap="innerHTML"`).
- Re-clicking collapses (client-side toggle or empty-swap). Nodes with further children inside
  the loaded ring carry their own Expand control → unbounded drill-down, one ring at a time.

---

## 5. Attach search results — HTMX fragment

- Trigger: typing in the search-to-attach input.
- `GET assets/<id>/children/search?q=…&format=htmx-search-results` →
  `relationship_search(...)` → candidate cards with **Attach**.
- Empty `q` → empty/hint panel. No density value on this request ([D6](../decisions.md)).

---

## HTMX contract summary (per [HTMX_PATTERNS](../../docs/ARCHITECTURE/HTMX_PATTERNS.md))

| Interaction | Verb + route | `format=` | Target / swap |
| :--- | :--- | :--- | :--- |
| Expand a node | GET `…/children/expand?node=` | `htmx-depth` | card child-slot / innerHTML |
| Search candidates | GET `…/children/search?q=` | `htmx-search-results` | results panel / innerHTML |
| Attach | POST `…/children/attach` | — | updated subtree + remove candidate |
| Detach | POST `…/children/detach` | — | updated subtree (remove card) |

Never combine a density value and an `htmx-*` value in one request. Every page renders fully
on a hard reload; HTMX only layers expansion, search, and in-place updates on top.

---

## Resolved

- **OQ1** Default render depth = **2** (confirmed). A single expand may paginate only if a node
  has a very large direct-child count; otherwise load the whole ring.
- **OQ5** **Replace, don't salvage** — delete `hierarchy_edit.html` and build the relationship
  templates fresh for a coherent system.
