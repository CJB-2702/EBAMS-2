---
type: "Authorization Guide"
title: "Domain Templates — Model Fields, Policy Signatures, and URL Map"
description: "Field-by-field model detail, exact policy method signatures, and the literal URL map for domain templates. Detail layer under [../domain_templates/models_plan.md](../domain_templates/models_plan.md)."
tags: [authorization, authorization-guide, example]
context_tier: 3
---

# Domain Templates — Model Fields, Policy Signatures, and URL Map

Concrete field lists and signatures supporting [../domain_templates/models_plan.md](../domain_templates/models_plan.md). Read that file first for the shape and boundaries; this file is reference detail, not orientation.

---

## Model layer field detail

Three models, all under `app/administration/models/data_ownership/`. All three use `AuditFieldsMixin`.

### `DomainTemplate`

- Fields: `name` (unique, human-readable), `slug` (unique for URLs), `description` (long text, optional), `is_active` (boolean — inactive templates hidden from assignment dropdowns but kept for history).
- `Meta`: `db_table = "core_domaintemplate"`, `ordering = ["name"]`, unique constraint on `slug`.

### `DomainTemplateItem`

- Through-table linking a template to `Domain` rows.
- Fields: `template` (FK, `related_name="items"`), `domain` (FK, `related_name="+"`), audit fields, `is_active` (soft-delete flag).
- `Meta`: `db_table = "core_domaintemplate_item"`. Unique constraint on `(template, domain)` where `is_active=True` (allows soft-deleted duplicates for history).

### `UserDomainTemplate`

- Records which domain template(s) are actively assigned to a user.
- Fields: `user` (FK to `AUTH_USER_MODEL`), `template` (FK), `is_active`, audit fields.
- Managers: `objects = ActiveUserAssignmentManager()`, `all_objects = models.Manager()`.
- `Meta`: `db_table = "core_userdomaintemplate"`. No uniqueness constraint on `(user,)` — users may hold multiple active templates simultaneously (see [../domain_templates/concept.md](../domain_templates/concept.md)).

---

## `DomainAssignmentPolicy` method signatures

- `assert_actor_may_assign_template(actor, template)` — admins always pass; others must have access to all domains in the template.
- `assert_actor_may_edit_template(actor)` — admins-only by default.
- `assert_actor_may_assign_domains(actor, domains)` — actor may only assign domains from their own domain template.

---

## URL map (after this change)

```
/administration/domain-templates/                    (new — list)
/administration/domain-templates/<slug>/             (new — detail + edit)
POST /administration/user-portal/<user_id>/domains/  (new — assign/remove/etc.)
/administration/domains/<id>/                        (existing — domain detail)
```
