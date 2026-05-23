# RBAC / Authorization / Domain Scope — Skeleton Bundle

## Scan targets (run codebase mapping script)
Run the codebase mapping script against `administration` and the target application:
```bash
python dev_tools/get_models_and_control.py --application administration
python dev_tools/get_models_and_control.py --application <target_app> --models_only
```

## Load alongside scan
- [docs/Authorization/rbac.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Authorization/rbac.md) — Django permission groups, assignments, and template synchronization.
- [docs/Authorization/data_ownership.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Authorization/data_ownership.md) — The Data Domain primitive, row-level scope, and ownership groups.
- [docs/Authorization/architecture_summary.md](file:///home/cb/REPOS/Django-Starter-Kit/docs/Authorization/architecture_summary.md) — Two-gate access model (capabilities vs. scope).

## Skip
- UI templates, styles, and presentation layer scripts unless editing the access control forms.
