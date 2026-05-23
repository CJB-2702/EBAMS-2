# Domain Service / Maintenance — Skeleton Bundle

## Scan targets (run codebase mapping script)
Run the codebase mapping script against the target application to extract models and control layer class context:
```bash
python dev_tools/get_models_and_control.py --application <target_app>
```
*(If event integration is needed, also run for `events`: `python dev_tools/get_models_and_control.py --application events`)*

## Load alongside scan
- [docs/Architecture/layer_rules.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Architecture/layer_rules.md) — Read/write boundaries before touching control layer.
- [docs/Architecture/oop_control_patterns.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Architecture/oop_control_patterns.md) — Suffix vocabulary for new classes.

## Skip
- `presentation_layer/templates/` — UI templates not relevant to domain service/backend logic.
