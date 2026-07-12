---
type: "Technical Decision"
title: "Dual listbox migration plan"
description: "Several detail templates in the administration sub-app still use the old form-submission + page-reload model for dual-listbox UI."
tags: [technical-decisions, technical-decision, tech-debt, resolved]
context_tier: 2
---

# Dual listbox migration plan

**Status:** Ready for implementation.
**Priority:** Medium (UX improvement + code consolidation).
**Date created:** 2026-05-18.

## What this debt is

Several detail templates in the administration sub-app still use the old form-submission + page-reload model for dual-listbox UI. The new HTMX-first light-DOM pattern is documented in [../../UX_UI/components/dual_listbox.md](../../UX_UI/components/dual_listbox.md) and [../history/2026-05-dual-listbox-htmx-light-dom.md](../history/2026-05-dual-listbox-htmx-light-dom.md). The user edit page (`users/edit.html` and its `_edit_information.html`, `_edit_data_access.html`) is already migrated and is the canonical reference.

## Why deferred

The user edit page covered the most common moves (roles, groups, permissions, organizations, divisions, domains). Migrating the remaining detail pages is mechanical but tedious and was deprioritised so other features could ship.

## What "fixed" looks like

All dual-listbox surfaces use the new pattern: HTMX move buttons, `<toast-alert>` feedback, `_<relationship>_dlb_only.html` fragment, `outerHTML swap:1s`. No `<form method="post">` + page-reload + Django messages anywhere.

## Templates known to still use the old pattern

| Template | Notes |
| :--- | :--- |
| `templates/organizational/organizations/detail.html` | Likely contains sub-division or role assignment listboxes. Review and migrate if present. |
| `templates/organizational/divisions/detail.html` | Same — review for sub-divisions or members. |
| `templates/data_access/domains/detail.html` | Template assignments / member orgs. |
| `templates/permissions/roles/detail.html` | Permission listbox. |
| `templates/permissions/permission_groups/detail.html` | Permission listbox. |
| All other `edit.html`/`new.html`/`detail.html` in administration | Audit for inline `class="dlb-alert"` or form-based move buttons. |
| `app/events/` | Audit. |
| `app/orgchart/` | Audit. |

## Migration steps (per template)

1. **Audit** — find old patterns: `grep -r "dlb-alert" app/*/templates/` and `grep -r "onclick.*move" app/*/templates/`.
2. **Backend endpoint** — add a `<entity>_move_<relationship>` view that accepts `item_ids` + `direction` and returns `<toast-alert>` + fragment.
3. **Fragment template** — create `_<relationship>_dlb_only.html` with no outer wrapper; root is the `<dual-list-box>` element.
4. **Template integration** — remove the old form markup and `{% include %}` the new fragment.
5. **Component loading** — ensure `list_box.js`, `dual_listbox.js`, `toast_alert.js` are loaded in `extra_head`.
6. **Test** — move buttons fire without page reload; toast appears; lists update; CSRF token present; permissions enforced.

## Known limitations of the new pattern

- Backend re-fetches full context per move (correct, inefficient at scale). Future: return delta only.
- Error responses are plain text 400. Future: structured JSON.
- Infinite scroll not wired (the component supports `list-box-scroll-end` but HTMX loading isn't connected).
- `swap:1s` is hardcoded; may be too fast on slow connections.
