# UI / Frontend — Skeleton Bundle

## Scan targets (run codebase mapping script)
Run the codebase mapping script against the target application to inspect presentation layer entries and templates:
```bash
python dev_tools/get_models_and_control.py --application <target_app>
```

## Load alongside scan
- [docs/UX_UI.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/UX_UI.md) — Visual language, layouts, and format query parameter contract.
- [docs/Architecture/htmx_patterns.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Architecture/htmx_patterns.md) — HTMX conventions, CSRF, and session drafts.
- [docs/UX_UI/form_style_guide.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/UX_UI/form_style_guide.md) — Card-footer geometry and primary/secondary button slot rules.

## Skip
- `control_layer/adapters/` or write modules unless updating DTO/portal payloads mapped by the views.
