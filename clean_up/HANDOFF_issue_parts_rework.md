---
type: "Handoff"
title: "Issue-Parts Workspace Rework + Queue Buttons"
description: "Build state, verification gaps, and next steps for the issue-parts two-step rework and the session issuance/purchasing queues."
created: 2026-08-24
creator: CJB-2702 (c.jamesbissett@gmail.com)
updated: 2026-08-24
editor: CJB-2702
---

# Handoff — Issue-Parts rework + session queues

Plan this implements: `/home/cb/.claude/plans/giggly-bouncing-patterson.md`
(approved). Branch: `feature/shipment-graph-architecture`.

## Status

**Code complete, smoke-tested at the GET level only.** `python manage.py check`
is clean and all seven affected routes return 200 authenticated:

| Route | |
| :--- | :--- |
| `/inventory/issue-parts/` | 200 |
| `/procurement/demands/` | 200 |
| `/inventory/active-inventory/` | 200 |
| `/inventory/active-inventory/gui/` | 200 |
| `/procurement/purchase-orders/create/` | 200 |
| `/inventory/issuance-queue/panel/` | 200 |
| `/procurement/demands/purchasing-queue/panel/` | 200 |

**No POST path has been exercised yet.** That is the top of the next-steps list.

---

## What was built

### 1. Two shared session-queue modules

- **`app/inventory/presentation_layer/tools/issuance_draft.py`** (new) — the
  issuance draft, extracted out of `entrypoints/issues.py` because three
  surfaces now write to it. Keeps the original `issuance_draft_<user_pk>`
  session key so in-flight sessions are not orphaned.
  Carries **three line shapes**: `demand_id` set (real demand),
  `adhoc_demand` set (described, not yet created), neither (direct issue).
- **`app/procurement/presentation_layer/tools/purchasing_queue.py`** (new) —
  a plain list of demand ids under `purchasing_queue_<user_pk>`. Stores ids
  only; quantities and line grouping stay the PO wizard's business.

`issues.py` keeps thin `_draft` / `_save_draft` / `_enrich_draft` shims so
`issuance_location_portal` (the from-location portal) was not touched.

### 2. Topnav queue badges (visible from every page)

- `app/public_app/context_processors.py` (new) → `work_queues`, registered in
  `app/config/settings.py`. Two session `len()` calls, **no query**.
- Two badges in `app/public_app/templates/shared/topnav.html`, in
  `.app-topnav-right`. Each opens a `popover="auto"` panel whose body is
  htmx-loaded **on first click**, so page loads cost nothing.
- Panel bodies: `inventory/issues/components/_queue_panel.html` and
  `procurement/demands/components/_purchasing_queue_panel.html`. Both re-render
  whole (indexes shift on removal) and **OOB-swap their own badge** so the
  count cannot go stale.
- CSS added to `app/static/css/custom_css.css` (`.app-queue-btn`,
  `.queue-popover*`, `.bulk-bar`, `tr.is-bulk-selected`).

### 3. Bulk multi-select on both list pages

- `app/static/js/bulk_select.js` (new) — fully delegated off `document`, so
  htmx-swapped tables are live with no re-binding. Ids are injected as hidden
  inputs **at submit time**; the checkboxes are the only source of truth.
  Selection deliberately resets on filter change.
- Checkbox column + floating action bar added to
  `procurement/demands/_results_card.html` (Queue for Part Issuance / Queue
  for Purchasing) and `inventory/active_inventory/_results_card.html` +
  `gui.html` (Queue for Part Issuance).
- `_row.html` gained the checkbox cell — it is shared by the stock list, the
  locator, and the inline-edit fragment, so the locator got the same bulk
  affordance rather than a divergent row template. Colspans bumped 11→12.

### 4. The reworked workspace (`/inventory/issue-parts/`)

`create.html` rebuilt as **queue first, then Step 1, Step 2, Step 3** — the
thing being built sits above the tools that build it.

- **Step 1 (requirement)**: one generic box (`dq`) searching part number,
  demand id, event id, and PO number; full `demand_index` filter set behind
  `_demand_filters_popup.html`. Defaults to Required+Approved.
- **Step 2 (stock)**: generic box (`sq`) over part number/name/serial; full
  `active_inventory_index` filter set behind `_stock_filters_popup.html`.
  **Auto-filters to the part Step 1 is waiting on** (`_autofilter_part`), with
  `?s_all=1` as the escape hatch and staged-part chips in the card header.
- **Pair vs Stage**: a stock row whose part matches a staged requirement still
  missing stock renders **Pair** (writes onto that line) instead of **Stage**
  (new loose line). `row.pair_index` is computed in `_stock_pool_context`.
- **Ad-hoc demand popup** (`_adhoc_demand_popup.html`): stages a described
  requirement; `PartDemandFactory.create(commit=False)` runs only at commit,
  inside the same `transaction.atomic()` as `commit_session`, so an abandoned
  draft leaves no orphan demand. Created as `DemandState.APPROVED` — the
  person issuing is the authorization event.
- **Session queue card** (`_staged_lines.html`): a CSS grid of readable rows,
  not a dense table, with one row per logical pairing (the old UI split one
  pairing across two half-tables). Status border-left + explicit
  Ready / Needs stock / Wrong part / Direct issue verdicts.
- Filter params are `d_`- and `s_`-prefixed so the two coexisting forms on one
  URL cannot read each other's values.

### 5. PO wizard integration

- `_wizard_render` now passes `queued_demands`.
- A "Queued for purchasing" card renders **above card 2** in
  `purchase_orders/create.html`, from the first render (before a vendor
  exists, where it says "pick a vendor to add these").
- "Add all to this order" posts `action=add_from_demands` + `from_queue=1` with
  the queue's ids — **the existing `_wizard_add_from_demands` handler,
  unchanged**. It already creates-or-grows one line per part and allocates each
  demand. Afterwards `_allocated_demand_ids(draft)` is intersected with the
  queue to drain only what actually landed; skipped demands stay queued.

### 6. Search-class additions (additive, non-breaking)

- `OpenDemandSearch.index_list` gained `generic_q` and `demand_states`.
- `ActiveInventorySearch.index_list` gained `generic_q`.

---

## Next steps

### A. Verify the POST paths (nothing here is tested yet)

1. Bulk queue from `/procurement/demands/` — both buttons; confirm badge
   increments and popover lists the rows.
2. Bulk queue from `/inventory/active-inventory/` and from the locator.
3. Step 1 Stage; Step 2 Pair and Stage; `set_quantity`; `auto_match`;
   `remove_line`; `cancel_draft`.
4. Ad-hoc popup → confirm the line shows **"New — not yet created"** and that
   `PartDemand.objects.count()` is unchanged until commit.
5. Commit → confirm the ad-hoc `PartDemand` now exists, the `PartIssue` points
   at it, draft clears, redirect lands on the session detail.
6. PO wizard "Add all to this order" → confirm one line per part with the right
   allocations, and that the queue drains only the consumed ids.
7. **F5 at every step** — both panes' filters must survive a plain reload.

### B. Seed data blocks the commit path

Seeded demands are on `PN-2001 / PN-2003 / PN-2007`; seeded `ActiveInventory`
holds `PN-1002 / PN-1003`. **No demand has matching stock**, so every staged
demand lands as "Needs stock" and the commit button — which I gate on
zero unpaired lines — stays disabled.

To exercise commit, either:
- add an `ActiveInventory` row for `PN-2001` (or whichever demand you stage), or
- use the **ad-hoc demand popup** picking a part that *does* have stock
  (`PN-1002`), which is also the cleanest way to test materialization, or
- consider making `seed_dev` overlap the two sets — arguably a seed bug
  independent of this work, since the pre-existing portal had the same
  dead end.

### C. Browser-only checks I could not do over curl

- **CSS anchor positioning** (`position-anchor` / `position-area`) on
  `.queue-popover` is Chrome/Edge 125+. Unsupported browsers fall back to the
  UA-centered popover — acceptable, but confirm it does not look broken. Same
  caveat already documented for `.info-popover-box`.
- `<dialog>` inside `<form>`: the filter popups rely on `showModal()` keeping
  DOM position so fields stay form-associated and htmx ships them. Verify a
  filter change inside the open dialog actually re-runs the search.
- `command="toggle-popover"` / `command="close"` are the invoker-commands API
  already used by `topnav.html` and `_left_heavy_linked_warning_dialog.html`,
  so this is consistent — but the badge combines `command` **and** `hx-get` on
  one button, which is the pattern from `_left_heavy_linked_warning_dialog.html`.
  Confirm both fire.
- The floating `.bulk-bar` is `position: fixed` and centered; check it does not
  collide with the sidebar on narrow viewports.

### D. Loose ends and judgement calls to review

- **`HX-Push-Url`**: the two pool fragments push the *canonical* URL via a
  response header rather than `hx-push-url="true"`, which would have put
  `?format=htmx-…` in the address bar and broken F5. **Note:** `demand_index`
  and `active_inventory_index` still do exactly that — a pre-existing F5
  violation I did not propagate but also did not fix. Worth a separate pass.
- **Pre-existing `part.part_name` bug** — `Part` has `name`, not `part_name`.
  The old issue-parts code filtered on `part__part_name__icontains` (would
  raise `FieldError`) and templates rendered `{{ part.part_name }}` (silently
  blank). I removed those from the rework, but two files still carry it:
  `inventory/issues/pending_adjustments.html:42` and
  `_pending_adjustments_results.html:23`. Both render blank today.
- **Cross-app import**: `procurement/entrypoints/demands.py` now imports
  `app.inventory.presentation_layer.tools.issuance_draft`. This is the reverse
  of the existing `inventory → procurement` direction and technically crosses
  the "presentation-layer code is app-internal" convention noted in
  `inventory_access.py`'s docstring. Justified because the queue being written
  *is* inventory's draft and a parallel copy would drift — but flag it if the
  architecture review disagrees; the alternative is moving both queue modules
  to a shared location.
- **Permission gating on the queue actions**: `demand_queue_for_issuance` and
  `active_inventory_queue_for_issue` currently gate nothing beyond login —
  queueing writes only to the user's own session, and `can_issue_parts` is
  enforced at the workspace before anything is committed. Confirm that is the
  intended boundary.
- `_back_to` / `_back_to_list` only honour same-site relative `next` values
  (open-redirect guard). Duplicated in two modules; could be shared.
- No tests were written. `harness/Architecture/tests.md` is the convention.

### E. Docs to update once verified

- `docs/inventory/` — the issuance workspace's shape changed materially.
- `dev_tools/memory.md` — one line, per the project convention.
- Consider a `docs/technical_decisions/` note on the session-queue pattern,
  since it is now a reusable primitive (two queues, one shape).

---

## Files touched

**New**
```
app/inventory/presentation_layer/tools/issuance_draft.py
app/procurement/presentation_layer/tools/purchasing_queue.py
app/public_app/context_processors.py
app/static/js/bulk_select.js
app/inventory/templates/inventory/issues/components/_queue_panel.html
app/inventory/templates/inventory/issues/components/_demand_pool_results.html
app/inventory/templates/inventory/issues/components/_demand_filters_popup.html
app/inventory/templates/inventory/issues/components/_stock_pool_results.html
app/inventory/templates/inventory/issues/components/_stock_filters_popup.html
app/inventory/templates/inventory/issues/components/_adhoc_demand_popup.html
app/inventory/templates/inventory/issues/components/_staged_lines.html
app/procurement/templates/procurement/demands/components/_purchasing_queue_panel.html
```

**Modified**
```
app/config/settings.py                                    (context processor)
app/inventory/urls.py                                     (3 routes)
app/procurement/urls_demands.py                           (3 routes)
app/inventory/presentation_layer/entrypoints/issues.py    (rewritten portal)
app/inventory/presentation_layer/search/active_inventory_search.py  (generic_q)
app/procurement/presentation_layer/search/open_demand_search.py     (generic_q, demand_states)
app/procurement/presentation_layer/entrypoints/demands.py (queue endpoints)
app/procurement/presentation_layer/entrypoints/purchase_orders.py   (queue banner + drain)
app/inventory/templates/inventory/issues/create.html      (rebuilt)
app/inventory/templates/inventory/active_inventory/_results_card.html
app/inventory/templates/inventory/active_inventory/_row.html
app/inventory/templates/inventory/active_inventory/index.html
app/inventory/templates/inventory/active_inventory/gui.html
app/procurement/templates/procurement/demands/_results_card.html
app/procurement/templates/procurement/demands/index.html
app/procurement/templates/procurement/purchase_orders/create.html
app/public_app/templates/shared/topnav.html
app/static/css/custom_css.css
```

Server is currently running (`./run.sh`, PID in `.server.pid`); `./stop.sh` to
stop it.
