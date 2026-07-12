---
type: "Skeleton Bundle"
title: "RBAC / permission / domain template — skeleton bundle"
description: "For task types: add a role, add or edit a permission group, change the domain template models, change how a route checks permission groups or domain membership."
tags: [authorization, skeleton-bundle]
context_tier: 2
---

# RBAC / permission / domain template — skeleton bundle

For task types: add a role, add or edit a permission group, change the domain template models, change how a route checks permission groups or domain membership.

## Scan targets

- `app/administration/models/` — `roles/`, `permissions/`, `data_ownership/` packages.
- `app/administration/control_layer/permissions/` — permission group + role + template contexts, handlers, guards.
- `app/administration/control_layer/data_ownership/` — domain + domain template contexts, handlers, guards.
- `app/administration/presentation_layer/entrypoints/permissions/` and `app/administration/presentation_layer/entrypoints/data_ownership/`.
- `app/administration/templates/permissions/` and `app/administration/templates/data_ownership_portal/`.

### Run codebase mapping script

Run the codebase mapping script against `administration` and the target application:
```bash
python dev_tools/get_models_and_control.py --application administration
python dev_tools/get_models_and_control.py --application <target_app> --models_only
```

## Load alongside scan

- `docs/Authorization/architecture_summary.md` — the two-gate model.
- `docs/Authorization/architecture_decisions.md` — trade-offs (urgent revocation, additive templates, cascade delete, exception tracking).
- `docs/Authorization/rbac.md` — Django permissions, permission groups, roles.
- `docs/Authorization/data_ownership.md` — the Data Domain primitive, the Golden Rule.
- `docs/Authorization/roles/concept.md` and `docs/Authorization/roles/decisions.md` — for role-system changes.
- `docs/Authorization/domain_templates/concept.md` and `docs/Authorization/domain_templates/models_plan.md` — for domain template changes.
- `docs/Authorization/data_access_exceptions.md` — read before adding any new route that filters by org/division.

## Skip

- `app/events/`, `app/assets/`, other sub-apps — unless the task is explicitly about how those apps consume the RBAC system.
- `app/administration/templates/users/` — touched only when changing the user portal's display of roles/domains; load the UI bundle alongside this one in that case.
