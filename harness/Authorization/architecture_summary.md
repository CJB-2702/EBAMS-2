---
type: "Authorization Guide"
title: "Authorization & Scope System — Complete Architecture"
description: "This document summarizes the complete architecture of how **permissions** and **data scope** work together in this application."
tags: [authorization, authorization-guide]
context_tier: 2
---

# Authorization & Scope System — Complete Architecture

Serves as a validation checksum: if the system matches this description, the implementation is on track.

---

## The two gates

Every user action faces **two independent access gates**.

### Gate 1: Permission / Capability (what you can *do*)

```
User
  ↓
At most one active PermissionGroupTemplate
  ↓
Resolves to auth.Group membership
  ↓
Django `has_perm()` check
  ↓
Route access + model-level action (add/change/view/delete)
```

**Data structures:**
- `PermissionGroupTemplate` — named role profile (e.g., "IT Technician")
- `PermissionGroupTemplateItem` — through-table (template ↔ auth.Group)
- `UserPermissionGroupTemplate` — assignment (user ↔ template)
- `auth.Group` — Django native; bundles `auth.Permission` rows

**Enforcement:**
- Users resolve to a single permission group template (at most).
- Assigning a template updates `user.groups` to match the template's items (rebase default, additive optional).
- Drift between template and actual groups is tracked and visible but not blocking.
- Session carries resolved `user_permission_codenames` for fast checks.

### Gate 2: Scope / Domain (what you can *see*)

```
User
  ↓
UserDomain assignments (direct + template-derived)
  ↓
Union = user's complete domain set
  ↓
Row filter in every query
```

**Data structures:**
- `DomainTemplate` — named scope profile (e.g., "Facility 1 Transportation"); copied at assignment
- `DomainTemplateItem` — through-table (template ↔ domain); auditable with soft-delete; for audit trail only
- `UserDomainTemplate` — assignment (user ↔ template); tracks which templates have been assigned
- `UserDomain` — the single source of truth: direct assignment (user ↔ domain); may expire; may have been created by template assignment
- `Domain` — the row-level scope primitive; every scoped row has a domain FK
- `Organization`, `Division` — informational hierarchy only; do not grant access

**Enforcement:**
- Users can have zero or more active `UserDomainTemplate` assignments (templates are tools, not permissions).
- User's complete domain set = all `UserDomain` rows where `user=current_user` and `is_active=True`.
- Assigning a template **copies** all template domains to the user's `UserDomain` set (rebase default, additive optional).
- Template updates propagate: new domains added to a template are copied to all users with that template assigned.
- Template item removal checks all users: the domain is removed from a user's set only if no other active template assigned to that user contains it.
- Drift is allowed: admins can directly assign `UserDomain` rows with no template relationship.
- Session carries resolved `user_domain_ids` for fast domain filters on every query.
- Every scoped row is visible ⟺ `row.domain_id in user_domain_ids`.

---

## Session snapshot (performance critical)

At login (or after any template/domain change), the session is updated with `user_domain_ids` (all active domain ids) and `user_permission_codenames` (all resolved permission codenames). Every data-filtered query checks `user_domain_ids` to scope rows; every permission check uses Django's native `has_perm()` against `user.groups`. Per-request database lookups would be prohibitively slow; the session is updated only on assignment/revocation, not per request. Reference code: [Examples/session_snapshot_code.md](Examples/session_snapshot_code.md).

---

## Orthogonality

The two systems are **completely independent**:

1. Permission group template changes do not affect domain assignments.
2. Domain template changes do not affect permission group membership.
3. A user can have:
   - Permission template + one or more domain templates (complete access)
   - Permission template + no domain templates (can act, but sees nothing)
   - No permission template + one or more domain templates (sees data, but can't act)
   - Neither (no access)

Both gates must pass for an operation to succeed. Neither implies the other.

The domain system is also orthogonal to itself: templates are tools for bulk assignment but do not gate access — only `UserDomain` rows determine visibility.

---

## Audit & history

**Permission Group Templates:** changes to name/description/status are tracked via audit fields. Adding/removing items is tracked via `PermissionGroupTemplateItem` audit fields. User assignment changes carry a `notes` field for justification. Drift (difference between template and actual groups) is visible in UI but not stored separately.

**Domain Templates:** changes to name/description/status are tracked via audit fields. Adding/removing domains to/from a template is fully auditable: each `DomainTemplateItem` row has audit fields, and removed items are soft-deleted rather than purged. Historical view shows what domains a template contained at any time and who made changes. User assignment changes are tracked with timestamps; explicit `UserDomain` assignments are tracked with expiration and audit fields.

---

## Expiration

Checked once at system startup (not per-request). Expired `Permission`, `Group`, `UserDomain`, `UserOrganization`, `UserDivision`, `DomainTemplate`, and `PermissionGroupTemplate` rows are soft-deleted (`is_active=False`) — never removed. All queries filter `is_active=True` by default.

---

## Control-layer families

### Permission granting (`control_layer/permissions/`)
- `PermissionGroupTemplateContext` — load/edit templates, add/remove items.
- `UserTemplateAssignmentContext` — assign/swap/disable permission templates.
- `TemplateRebaseHandler` — sync user's `auth.Group` membership.
- `TemplateDriftStruct` — read-only view of expected vs. actual groups.
- `TemplateAssignmentPolicy` — guard; who may assign/edit templates.

### Domain granting (`control_layer/data_ownership/`)
- `DomainTemplateContext` — load/edit domain templates, add/remove domains.
- `UserDomainAssignmentContext` — assign/remove domain templates; manage explicit `UserDomain` assignments.
- `UserDomainSyncHandler` — copy/remove domains from user's `UserDomain` set; update session.
- `UserDomainStruct` — read-only view of user's active domains (source of truth for access).
- `DomainAssignmentPolicy` — guard; who may assign/revoke domains + expiration rules.

---

## Constraints & rules

### Rule 1 — Templates are tools; `UserDomain` is the source of truth
- Templates do **not** grant access themselves; they are assignment convenience tools.
- Only `UserDomain` rows determine what a user can see.
- When a template is assigned, all its domains are copied to the user's `UserDomain` set.
- Admins can directly assign `UserDomain` rows with no template relationship (drift is allowed).
- Deleting a template does not delete the domains it created; the user keeps those domains.

### Rule 2 — Multiple templates per user; synchronised assignment and removal
- Users can have **zero or more** active `UserDomainTemplate` assignments simultaneously.
- Assigning a template copies all its domains to the user's `UserDomain` rows (unless already present).
- Template item removal checks all users: if the domain is in multiple template assignments for that user, keep it; if only in the removed template, remove it from `UserDomain`; if directly assigned (drift), keep it.

### Hard-coded in policy
- Sensitive groups cannot be self-propagated (hardcoded list in `TemplateAssignmentPolicy`):
  - `administration_can_grant_and_remove_owned_permissions`
  - `administration_can_grant_and_remove_owned_domains`
  - `administration_can_crud_group_templates`
  - `administration_can_crud_domain_templates`
  - `system_admin`

### Soft constraints (UI enforcement)
- One active permission template per user (enforced by DB unique index on `(user,)` where `is_active=True`).
- Admins only: create/edit templates; rebase is explicit, never silent.
- Permissions use Django's native `auth.Group` and `auth.Permission` framework.

---

## Summary table

| Aspect | Permission system | Scope system |
| :--- | :--- | :--- |
| **Primitive** | `auth.Permission` (Django native) | `Domain` (project custom) |
| **Bundle** | `auth.Group` (Django native) | *None; domains are individual* |
| **Template** | `PermissionGroupTemplate` | `DomainTemplate` (copied at assignment) |
| **User assignment** | `UserPermissionGroupTemplate` (one active max) | `UserDomainTemplate` (zero or more active) |
| **Source of truth** | `auth.Group` membership (via template) | `UserDomain` rows (template-derived + drift) |
| **Session key** | `user_permission_codenames` | `user_domain_ids` |
| **Enforcement** | Django `has_perm()` | Row filter: `row.domain_id in user_domain_ids` |
| **Audit trail** | Template items + user assignments | Template items (soft-delete history) + assignments |
| **Drift** | Visible in UI; tracked but not blocking | Allowed; admins can directly assign `UserDomain` |
| **Expiration** | Optional on `Permission`, `Group` | Optional on `UserDomain` |
| **Template-update propagation** | Changes do not auto-propagate to users | New domains copied to all users with template assigned |
| **Template-item removal** | Removes from `auth.Group` per policy | Removes from `UserDomain` if no other active template contains it |
