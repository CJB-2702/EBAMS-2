---
type: "Skeleton Bundle"
title: "UI / front-end — skeleton bundle"
description: "For task types: build a new template, add an HTMX interaction, restyle a card, add a new searchbar, migrate a dual-listbox surface."
tags: [ux-ui, skeleton-bundle]
context_tier: 2
---

# UI / front-end — skeleton bundle

For task types: build a new template, add an HTMX interaction, restyle a card, add a new searchbar, migrate a dual-listbox surface.

## Scan targets

- `app/<target_app>/templates/` — the templates being changed and their fragments.
- `app/<target_app>/presentation_layer/entrypoints/` — view functions and class-based views that render those templates.
- `app/static/web_components/` — light-DOM components (`dual_listbox.js`, `list_box.js`, `toast_alert.js`, `search_dropdown.js`).
- `app/static/css/` — project CSS layer (`app.css`).

### Run codebase mapping script

Run the codebase mapping script against the target application:
```bash
python dev_tools/get_models_and_control.py --application <target_app>
```

## Load alongside scan

- `harness/UX_UI/visual_language.md` — tokens, sharp corners, dark-mode strategy.
- `harness/UX_UI/page_structure.md` — shell, hero, sidebars, page patterns.
- `harness/UX_UI/form_style_guide.md` — card-footer geometry.
- `harness/UX_UI/components/common_buttons.md` — master button table and icon-only rules.
- `harness/UX_UI/format_contract.md` — `format=` density / HTMX fragment contract.
- For dual-listbox work: `harness/UX_UI/components/dual_listbox.md` and `harness/UX_UI/Examples/dual_listbox_markup.md`.
- For searchbars: `harness/UX_UI/components/searchbars.md` and `harness/UX_UI/Examples/search_dropdown_component.md`.
- For tabs: `harness/UX_UI/components/tabs.md`.

## Skip

- `app/<target_app>/control_layer/` — write work belongs in a domain-service task, not a UI task. Touch only enough to wire the entrypoint to the existing context/handler.
- `app/<target_app>/models/` — schema is out of scope for UI work.
- `app/<target_app>/migrations/` — never relevant to a UI change.
