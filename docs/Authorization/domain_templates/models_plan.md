---
type: "Authorization Guide"
title: "Domain Templates — Models and Control-Layer Plan"
description: "This is the **architectural plan** for adding domain templates to the administration app."
tags: [authorization, authorization-guide]
context_tier: 2
---

# Domain Templates — Models and Control-Layer Plan

This is the **architectural plan** for adding domain templates to the administration app. It describes the **shape** of the new models, the **boundaries** between layers, and the **classes** that need to exist — but not every method signature. For business rules and intent, see [concept.md](concept.md). For field-by-field model detail, exact policy signatures, and the URL map, see [../Examples/domain_templates_model_detail.md](../Examples/domain_templates_model_detail.md).

---

## 1. Placement

Domain template code lives under the existing `data_ownership` family:

```
app/administration/
  models/
    data_ownership/
      domains.py                                ← existing
      domain_templates.py                       ← new: DomainTemplate model
      domain_template_items.py                  ← new: DomainTemplateItem (template ↔ domain)
      user_assignments/
        user_domains.py                         ← existing
        user_domain_templates.py                ← new: UserDomainTemplate
      group_relationships/
        organization_domains.py                 ← existing
  control_layer/
    data_ownership/
      domain_template_context.py                ← new: DomainTemplateContext (template edits)
      user_domain_assignment_context.py         ← existing/extended: assignment + sync
      template_rebase_handler.py                ← new: TemplateDomainRebaseHandler
      template_domain_struct.py                 ← new: TemplateDomainStruct
      domain_assignment_policy.py               ← existing; updated with template rules
  presentation_layer/
    entrypoints/
      data_ownership/
        domain_template_portal.py               ← new: list + detail + edit for templates
        user_domain_assignment.py               ← new: POST routes from the user portal
    search/
      domain_templates.py                       ← new: loaders / querysets for template lists
      user_access.py                            ← new/existing: domain warning helpers
  templates/
    data_ownership_portal/
      domain_templates/
        index.html
        detail.html
        _template_row.html
        _items_panel.html
        _assigned_users_panel.html
    user_portal/
      _domain_template_block.html               ← new include: shows current templates + domains
```

---

## 2. Model layer

Three models, all under `app/administration/models/data_ownership/`, all using `AuditFieldsMixin`: `DomainTemplate` (name/slug/description/is_active), `DomainTemplateItem` (through-table, template ↔ domain, soft-delete), `UserDomainTemplate` (assignment, user ↔ template, multiple active per user allowed). Field-by-field detail: [../Examples/domain_templates_model_detail.md](../Examples/domain_templates_model_detail.md).

---

## 3. Control layer

Control-layer classes follow the project's [../../Architecture.md](../../Architecture.md) class-suffix vocabulary.

### 3.1 `DomainTemplateContext`

- **Context** for edits to a single domain template (id-keyed or slug-keyed).
- Loads a read struct describing the template, its items, and historical changes.
- Adds / removes domains (delegating policy checks to `DomainAssignmentPolicy`).
- Activates / deactivates the template.
- Exposes the historical audit trail of item additions/removals.
- Does **not** directly mutate `UserDomain` rows.

### 3.2 `UserDomainAssignmentContext`

- **Context** for a user's domain template assignments.
- Assign a domain template to the user (creates/reactivates `UserDomainTemplate`).
- Remove a template assignment (triggers smart removal — see Rule 2 in [../architecture_summary.md](../architecture_summary.md)).
- Add/remove explicit `UserDomain` assignments (outside any template footprint).
- Delegates the "update actual `UserDomain` set" step to `TemplateDomainRebaseHandler`.

### 3.3 `TemplateDomainRebaseHandler`

- **Handler** for the single complex step — the domain membership sync.
- On template **assignment**: copy all template domains to user's `UserDomain` (if not already present).
- On template **removal**: for each domain in the removed template, check the user's other active templates; remove the domain only if no other active template still supplies it.
- Update the session snapshot (`user_domain_ids`) after changes.
- Operates inside an existing transaction; does not open its own.

### 3.4 `TemplateDomainStruct`

- **Struct** — read-only aggregate for display and audit.
- Fields: `user_id`, `templates` (list of active assigned templates), `expected_domain_ids` (from templates' items), `actual_domain_ids` (from user's `UserDomain` rows), `manual_domain_ids` (domains the user holds explicitly outside any template).
- Exposes `to_dict()` for template rendering.

### 3.5 `DomainAssignmentPolicy`

- **Guard → Policy**, existing class updated with template rules: who may assign/edit templates, and who may assign domains outside their own template. Exact method signatures: [../Examples/domain_templates_model_detail.md](../Examples/domain_templates_model_detail.md).

---

## 4. Presentation layer

### 4.1 Entrypoints

- **`domain_template_portal`**: GET list at `/administration/domain-templates/`; GET detail + edit at `/administration/domain-templates/<slug>/`; POST actions for create / rename / deactivate / add-remove items.
- **`user_domain_assignment`**: POST from the user-portal edit screen. Actions: `assign_domain_template`, `remove_domain_template`, `assign_manual_domain`, `revoke_manual_domain`.

### 4.2 Search / loaders

- `presentation_layer/search/domain_templates.py` — `list_templates(user, *, include_inactive=False)`, `load_user_domain_template_struct(user_id)`.
- `presentation_layer/search/user_access.py` — `compute_domain_warnings(user)` for the audit warning colors.

### 4.3 Templates (HTML)

Under `app/administration/templates/data_ownership_portal/domain_templates/`: `index.html`, `detail.html`, plus HTMX panel partials. Under `app/administration/templates/user_portal/`: `_domain_template_block.html` shown on the user edit screen.

---

## 5. Session

The existing `auth_session.refresh_auth_in_session` snapshot continues to store `user_domain_ids` (all domain ids the user can access, computed fresh at login or explicit rebase) and `user_permission_codenames`. No domain template information is stored in the session — the snapshot is pure capability and domain state.

Every route that filters by domain queries against the session snapshot `user_domain_ids`, not the database. Permission checks query `user_permission_codenames`.

---

## 6. Seed data

`seed_dev` gains a small block creating 2–3 domain templates and assigning matching templates to seeded users so developer environments demonstrate the full flow.

---

## 7. URL map

New routes for domain templates and user-portal assignment actions. Full map: [../Examples/domain_templates_model_detail.md](../Examples/domain_templates_model_detail.md).

---

## 8. Out of scope for this document

- Exact method signatures, line-by-line code, or test plans.
- UI copy and exact Bulma class choices.
- Object-permission packages (django-guardian etc.) — not used.
- Per-route decorators — those are picked up from the existing `domain_assignment_policy` conventions.
