# Events Integration — Skeleton Bundle

## Scan targets (run codebase mapping script)
Run the codebase mapping script against both `events` and the target application:
```bash
python dev_tools/get_models_and_control.py --application events
python dev_tools/get_models_and_control.py --application <target_app>
```

## Load alongside scan
- [docs/Events.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Events.md) — Events sub-application spec.
- [docs/Events/events.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Events/events.md) — Event models, mixins, comments, and shadow history.
- [docs/Events/event_context_design.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Events/event_context_design.md) — Event context structs and design layout.

## Skip
- Non-related domain apps (e.g. `administration` unless permissions or ownership scope changes).
