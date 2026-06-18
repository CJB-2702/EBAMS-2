# Entitlement Sets: Concept Note (Future Work)

Managing what users can do and what data they can see can quickly become complex. This document captures the **Entitlement Set** concept as a future simplification of the two-layer permission system already in place — it is not yet built.

---

## The Two Layers Already in the System

The current `administration` app already enforces two distinct permission dimensions independently:

### Layer 1 — Action Permissions ("What can they do?")

Implemented via `Role` + `RoleItem` + `UserRole`.

- **`Role`** — a named bundle of `auth.Group`s representing a job profile (e.g., "Field Worker", "Regional Manager"). Has `name`, `slug`, `description`, `is_active`, and an optional `parent_role` for hierarchy.
- **`RoleItem`** — through table linking a `Role` to one or more Django `auth.Group`s, which carry the actual `Permission` objects.
- **`UserRole`** — assigns a `Role` to a user with a `relationship_type` (`primary`, `specialty`, `side_job`, `for_fun`), optional `notes`, and `is_active`.

A user can hold multiple `UserRole` assignments simultaneously.

### Layer 2 — Data Access Permissions ("What data can they see?")

Implemented via `Domain` + `DomainTemplate` + `DomainTemplateItem` + `UserDomainTemplate` / `UserDomain`.

- **`Domain`** — the atomic row-level access scope. Every scoped data row in the system carries exactly one `Domain` foreign key (e.g., "San Diego", "Los Angeles").
- **`Organization`** — groups `Domain`s for navigation and reporting (via `OrganizationDomain` through table). Belongs to a `Division`.
- **`DomainTemplate`** — a named bundle of `Domain`s representing a scope profile (e.g., "SoCal Region"). Has `name`, `slug`, `description`, `is_active`.
- **`DomainTemplateItem`** — through table linking a `DomainTemplate` to individual `Domain`s. Soft-deletable via `is_active`.
- **`UserDomainTemplate`** — assigns a `DomainTemplate` to a user. The unique constraint `uniq_active_user_domain_template` enforces that a user has **at most one active template** at a time.
- **`UserDomain`** — direct user-to-`Domain` membership, bypassing templates. Used for one-off or supplemental access.

---

## The Problem This Concept Solves

Currently, action permissions (Role) and data permissions (DomainTemplate) are assigned independently. This means an admin must perform two separate operations to give a user a coherent access profile, and there is no auditable record of an *intended pairing*.

**Permission creep risk:** A user could hold a `Role` granting elevated actions without an appropriate data scope, or vice versa — both assignments exist but were never reviewed as a unit.

---

## The Entitlement Set Concept

An **EntitlementSet** would be a model that explicitly pairs a `Role` with a `DomainTemplate` into a single named bundle representing a complete job profile.

```
EntitlementSet
  name           — e.g. "San Diego Field Worker", "SoCal Regional Manager"
  slug
  description
  role           → Role
  domain_template → DomainTemplate
  is_active
```

A `UserEntitlementSet` assignment would then replace (or sit alongside) separate `UserRole` + `UserDomainTemplate` assignments:

```
UserEntitlementSet
  user           → User
  entitlement_set → EntitlementSet
  relationship_type  (mirrors UserRole.RelationshipType)
  notes
  is_active
```

### Concrete examples using current models

| Entitlement Set Name | Role | DomainTemplate |
| --- | --- | --- |
| `san_diego_worker` | Field Worker | San Diego Office |
| `socal_regional_manager` | Regional Manager | SoCal (SD + LA) |
| `enterprise_auditor` | Auditor | All Domains |

---

## Design Notes for Future Implementation

- The unique constraint on `UserDomainTemplate` (one active template per user) would need to be relaxed or migrated — `UserEntitlementSet` would own the data scope, so standalone `UserDomainTemplate` becomes a supplemental escape hatch only.
- `UserRole` with `relationship_type=specialty` or `for_fun` is a natural fit for assignments that *don't* need a data scope pairing; those could remain as direct `UserRole` records alongside the primary `UserEntitlementSet`.
- The `role_rebase_handler.py` and `template_domain_rebase_handler.py` in `control_layer/` would need `EntitlementSet`-aware rebase logic so that changing a template or role propagates correctly to affected users.
- Admin UI: the natural surface is a user detail page showing their `EntitlementSet` assignments as a primary card, with `UserDomain` and standalone `UserRole` as secondary expansion panels.
- Guard layer (`domain_assignment_policy_guard.py`, `permission_grant_guard.py`) would gain an `EntitlementSetGrantGuard` that validates the pairing is coherent before assignment.

---

## Status

**Concept only — not built.** The two independent assignment mechanisms (`UserRole` + `UserDomainTemplate`) remain in place. This document records the intended future consolidation.
