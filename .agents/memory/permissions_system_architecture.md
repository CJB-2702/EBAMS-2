---
name: Permissions & Scope System Architecture (Confirmed)
description: Complete design of two-gate access control (permission templates + domain templates), session snapshots, expiration model, and audit trail
type: project
---

## Confirmed Design Decisions

**Date: 2026-04-26**

### Two Orthogonal Access Gates
- **Permission Gate** (what you can do): Permission group templates → auth.Group membership → Django `has_perm()`
- **Scope Gate** (what you can see): Domain templates + explicit UserDomain → domain set → row filter
- Both gates must pass; neither implies the other

### Session Snapshot (Performance-Critical)
- `user_domain_ids` — computed from domain template + explicit assignments; used in every query filter
- `user_permission_codenames` — computed from resolved auth.Group membership; used in every permission check
- Snapshot updated only on assignment/swap/revocation, not per-request

### Domain Templates (Full Model, Auditable)
- `DomainTemplate` — named bundles of domains (e.g., "Facility 1 Transportation")
- `DomainTemplateItem` — through-table with full audit fields; removed items soft-deleted (is_active=False) for historical trail
- `UserDomainTemplate` — assignment (one active max per user); can rebase or be additive
- Users can only grant domains from their own domain template (hardcoded in policy)

### Permission Group Templates (Existing Model, Drift-Tracked)
- `PermissionGroupTemplate` — named bundles of auth.Group rows
- `PermissionGroupTemplateItem` — through-table with audit fields
- `UserPermissionGroupTemplate` — assignment (one active max per user); can rebase or be additive
- Drift (actual vs. template groups) is visible, not blocking; explained via notes

### Expiration (Soft-Delete, Startup Check Only)
- Optional `expires_at` on: Permission, Group, DomainTemplate, UserDomain, UserOrganization, UserDivision
- Checked once at system startup; expired rows marked `is_active=False`
- No per-request expiration checks (performance constraint)
- Audit trail remains complete: operators see when/why access expired

### Hard-Coded Sensitive Groups (No Self-Propagation)
- Cannot grant: `administration_can_grant_and_remove_owned_permissions`, `administration_can_grant_and_remove_owned_domains`, `administration_can_crud_*_templates`, `system_admin`
- Enforced in `TemplateAssignmentPolicy` (hardcoded list, not data-driven)

### Audit History Depth
- Permission template changes tracked via audit fields + notes (draft visible, history partial)
- Domain template changes fully auditable: each item add/remove is timestamped, soft-deleted, and linked to actor

## How to Apply

Use this when implementing the control layer, models, and enforcement policy classes. Refer to docs/DOMAIN/admin/ARCHITECTURE_SUMMARY.md as the authoritative checklist against this implementation.
