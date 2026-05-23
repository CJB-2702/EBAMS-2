# UI / front-end — skeleton bundle

For task types: build a new template, add an HTMX interaction, restyle a card, add a new searchbar, migrate a dual-listbox surface.

## Scan targets

- `app/<target_app>/templates/` — the templates being changed and their fragments.
- `app/<target_app>/presentation_layer/entrypoints/` — view functions and class-based views that render those templates.
- `app/static/web_components/` — light-DOM components (`dual_listbox.js`, `list_box.js`, `toast_alert.js`, `search_dropdown.js`).
- `app/static/css/` — project CSS layer (`app.css`).

## Load alongside scan

- `docs/UX_UI/visual_language.md` — tokens, sharp corners, dark-mode strategy.
- `docs/UX_UI/page_structure.md` — shell, hero, sidebars, page patterns.
- `docs/UX_UI/form_style_guide.md` — card-footer geometry.
- `docs/UX_UI/common_buttons.md` — master button table and icon-only rules.
- `docs/UX_UI/format_contract.md` — `format=` density / HTMX fragment contract.
- For dual-listbox work: `docs/UX_UI/dual_listbox.md` and `docs/UX_UI/Examples/dual_listbox_markup.md`.
- For searchbars: `docs/UX_UI/searchbars.md` and `docs/UX_UI/Examples/search_dropdown_component.md`.
- For tabs: `docs/UX_UI/tabs.md`.

## Skip

- `app/<target_app>/control_layer/` — write work belongs in a domain-service task, not a UI task. Touch only enough to wire the entrypoint to the existing context/handler.
- `app/<target_app>/models/` — schema is out of scope for UI work.
- `app/<target_app>/migrations/` — never relevant to a UI change.
