---
type: "Authorization Guide"
title: "Domain Templates — Concept"
description: "This document describes the **business concept** of a domain template, the rules it enforces, and how it interacts with row-level access control."
tags: [authorization, authorization-guide]
context_tier: 2
---

# Domain Templates — Concept

This document describes the **business concept** of a domain template, the rules it enforces, and how it interacts with row-level access control. It is the source of truth for *what* domain templates are and *why* they exist. For *how* they are built in code, see [models_plan.md](models_plan.md).

---

## 1. What a domain template is

A **Domain Template** is a named, pre-configured bundle of Data **domains**. It represents a real-world **data scope profile** — the domains a person in a certain role or position is expected to have access to.

Examples:

- *Facility 1 Transportation* (transportation_domain + supply_domain)
- *Warehouse Operations* (warehouse_receiving + warehouse_inventory)
- *Cross-site Auditor* (all_facilities + headquarters)
- *IT Support — Field* (field_locations + it_assets)

Assigning a domain template to a user means: **"This user should have access to every domain the template bundles together."**

A domain template is **not** a permission type. It does not participate in Django's `has_perm` checks or the permission system. It is a **shortcut** for assigning related domains together and an **audit artifact** saying "this user's data scope was established via the *Facility 1 Transportation* template."

---

## 2. Why domain templates exist

Three concrete problems:

1. **Manually assigning many domains per user is error-prone.** A Warehouse Operator might belong to five domains. Onboarding twenty by hand means 100 opportunities to mis-assign.
2. **Domains are stable but scope evolves.** Operators need a single place to say "everyone who holds the *Facility 1 Transportation* template should now also get access to *maintenance_domain*." Update the template; future onboards and re-baselines get it automatically.
3. **Auditors need to see intent.** Looking at a user's raw `UserDomain` list does not tell you *why* they hold those domains. Seeing "User assigned: *Facility 1 Transportation* template" tells you both the scope and the business context in one glance.

---

## 3. The rules

### Rule 1 — Zero or more active templates per user

Multiple domain templates can be assigned to one user simultaneously. The user's domain set is the union of all template-derived domains plus any explicit `UserDomain` rows. See [../architecture_summary.md](../architecture_summary.md) for the propagation logic.

### Rule 2 — Reference, not copy

Templates point at `Domain` rows. The domain itself is not duplicated; updates to a domain's metadata (name, organization) are immediately reflected wherever the template is assigned.

### Rule 3 — Domain templates do not grant capabilities

Domain templates manage **data scope** (which rows you see). They have **zero** effect on **permission groups** (what actions you can perform). A user with the *Facility 1 Transportation* template still cannot perform actions unless they hold the required permission groups. The two systems stay separate on purpose — see [../data_ownership.md](../data_ownership.md) and [../rbac.md](../rbac.md).

### Rule 4 — Template changes are auditable and historical

Every add/remove of a domain to/from a template is tracked:

- `DomainTemplateItem` rows are timestamped and carry audit fields (`created_by`, `updated_by`).
- When an item is removed from a template, the row is soft-deleted (`is_active=False`) rather than permanently deleted.
- Historical views show the full audit trail: what domains a template contained at any given time, who made the change, and when.

---

## 4. The full access picture

When a user interacts with the application, **two gates** must pass:

1. **Template / Data Domain gate** — "Does the row I'm about to touch live in a Domain I'm assigned to (via template or explicit assignment)?"
2. **Permission / Capability gate** — "Do I hold the required permission groups for this action?"

Domain templates **only** affect gate 1.

---

## 5. Admin scope visibility

The system exposes domain template changes on the user-portal edit screen as a small panel listing:

- The user's active templates.
- The domains the templates bundle (grouped, labelled `[Template]`).
- Explicit `UserDomain` assignments outside any template (labelled `[Manual]`).
- An expiration countdown for explicit assignments.

Operators can re-sync (rebase to a specific template), accept mixed state as-is, or add/remove templates. The session is updated on every change so the user's next request sees the new scope.

---

## 6. Governance (informal)

- **Who creates and edits templates** — members of the `generic_admin` group.
- **When a template is reviewed** — whenever a domain is added/removed or when organizational structure changes.
- **How existing users are notified** — template changes propagate to all users who hold the template the next time their session is refreshed (login, explicit re-sync, or operator action). The propagation is not silent — it's surfaced in audit history.

These rules are not technically enforced but are encoded in the UI (only admins can edit templates).

---

## 7. Summary

| Rule | Statement |
| :--- | :--- |
| **Multiple per user** | Zero or more active template assignments per user. |
| **Reference, not copy** | Templates point at `Domain` rows; domain state is not duplicated. |
| **No effect on capabilities** | Templates manage data scope only; permission groups are the separate system. |
| **Changes are auditable** | Every add/remove is timestamped, soft-deleted, and visible in audit history. |
| **Distinct from permissions** | Domain templates and permission groups / roles are orthogonal systems. |
