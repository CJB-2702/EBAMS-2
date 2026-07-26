---
type: "Technical Decision"
title: "Dual Listbox Template Fragment Attempt"
description: "A single reusable Django template fragment, shared/dual_listbox.html, that every dual-list-box partial would call via {% include %} with keyword args like dlb_id, left_id, right_label, hx_post_url, param_name, available_items,."
tags: [technical-decisions, technical-decision, incident-history]
context_tier: 2
---

# Dual Listbox Template Fragment Attempt

- **Date:** 2026-05
- **Affected area:** Every `_*_dlb_only.html` partial under `app/administration/templates/` that renders a dual-list-box (users, divisions, organizations, domains, roles, permission groups, permissions, domain templates).
- **Outcome:** Attempt abandoned. Reverted to inline per-page dual-list-box markup. The shared `app/public_app/templates/shared/dual_listbox.html` is retained as a **structural reference only** and is no longer included anywhere.

## What was tried

A single reusable Django template fragment, `shared/dual_listbox.html`, that every dual-list-box partial would call via `{% include %}` with keyword args like `dlb_id`, `left_id`, `right_label`, `hx_post_url`, `param_name`, `available_items`, `assigned_items`, etc. The goal was to delete ~30 lines of near-identical markup from each of the 16 `_*_dlb_only.html` partials and centralize the dual-list-box shape in one place.

To make the fragment generic, every item in `available_items` / `assigned_items` had to expose `.pk` and `.display_label`. A new `app/administration/presentation_layer/dlb_helpers.py` module was added with adapter functions (`as_name_items`, `as_user_items`, `as_permission_items`, `as_organization_items`, `as_role_items`) that wrapped each queryset in `SimpleNamespace` shells carrying only those two fields. Every entrypoint that rendered a dual-list-box was rewritten to pipe its querysets through these adapters before stuffing them into the context.

## Why it was abandoned

1. **The adapter layer was the cost.** To unify a presentation shape, the control layer had to ship objects in a shape the template demanded. That is presentation concern leaking into entrypoints — exactly the layering this project tries to avoid. Every queryset got rewrapped in `SimpleNamespace(pk=..., display_label=...)` just to satisfy the include.
2. **The callsite got longer, not shorter.** The `{% include "shared/dual_listbox.html" with dlb_id="..." left_id="..." left_label="..." right_id="..." right_label="..." hx_post_url=... param_name="..." available_items=... assigned_items=... add_title="..." remove_title="..." %}` line was wider and harder to read than the 30-line inline block it replaced. Nothing was actually compressed; the complexity was just moved into a hard-to-scan keyword pile.
3. **It hid the `{% url %}` site.** Page-specific routes ended up as `{% url '...' as hx_post_url %}` aliases instead of appearing in the obvious place next to the button that posts to them. Reading any individual partial no longer told you which endpoint it actually called without chasing through the fragment.
4. **Per-page divergence killed the abstraction anyway.** Several pages needed different label fields (`username` vs `name` vs `app | model | name` for permissions vs `name — division` for organizations), different button titles, and a `data_perm_check_url` only some pages set. The fragment grew optional knobs to absorb each case, which is the early warning sign of a leaky abstraction.
5. **Template-namespace collision compounded the pain.** Resolving `shared/dual_listbox.html` was not stable across apps due to multiple `templates/shared/` folders colliding in the Django template namespace — see [multiple_templates_shared.md](multiple_templates_shared.md). This made the failure modes hard to debug and eroded confidence that the include was even resolving the file the author thought it was.

Combined, the abstraction cost more than the duplication it removed.

## What changed

- All 16 `_*_dlb_only.html` partials reverted to inline `<dual-list-box>` markup with their real field names and `{% url %}` tags written directly into the buttons.
- All 4 entrypoint modules (`organizational/divisions.py`, `organizational/organizations.py`, `permissions/roles.py`, `users/users.py`) reverted to passing model querysets directly into context — no `SimpleNamespace` adapter step.
- `app/administration/presentation_layer/dlb_helpers.py` deleted.
- `app/public_app/templates/shared/dual_listbox.html` kept on disk but marked at the top with a do-not-include comment. It now functions purely as a structural reference: copy the markup shape into the new partial and bind real fields inline.

## Rule going forward

**Do not `{% include %}` `shared/dual_listbox.html`.** When adding a new dual-list-box, copy the structure from that file into a new `_*_dlb_only.html` partial in the relevant page's template directory and bind the real field names, `{% url %}` tag, and `param_name` directly. Keep presentation shape concerns out of the control layer.

## Why this is in the decision system

The shape of this dual-list-box is a strong attractor for the "extract a shared template" instinct, and the duplication across 16 partials reads as obvious tech debt at a glance. Recording this attempt prevents the next engineer (human or AI) from re-walking the same path, building the same adapter layer, and re-discovering the same costs. The duplication is **deliberate** — the cost of unifying it is higher than the cost of keeping the markup inline and per-page.
