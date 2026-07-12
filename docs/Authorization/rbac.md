---
type: "Authorization Guide"
title: "Role-based access control (concepts)"
description: "This document describes concepts for capability access control in this application: what Django's built-in authorization covers, how roles (bundles of permission groups) relate to Django Group rows, and where enforcement belongs."
tags: [authorization, authorization-guide]
context_tier: 2
---

# Role-based access control (concepts)

This document describes **concepts** for capability access control in this application: what Django's built-in authorization covers, how **roles** (bundles of permission groups) relate to Django `Group` rows, and where enforcement belongs relative to **row-level** (domain) rules. For row-level data scoping, see [data_ownership.md](data_ownership.md).

For the authoritative role rules, see [roles/concept.md](roles/concept.md).

---

## 1. Terminology

| Term | Django-level concept | What it means here |
| :--- | :--- | :--- |
| **Permission** | `auth.Permission` | A single capability, tied to a model and action (e.g. `core.change_asset`). |
| **Permission group** | `auth.Group` | An atomic bundle of permissions tied to a **specific action or feature** (e.g. "Asset Lifecycle"). **Not** a social/organizational group. Assigned to users **only through roles**. |
| **Role** | *this project* | A named relationship between humans and a set of permission groups. Represents a real-world job profile or specialization. See [roles/concept.md](roles/concept.md). |
| **Data domain** | *this project* | Row-level access scope — separate system. See [data_ownership.md](data_ownership.md). |

---

## 2. Goals

- **Route and view access** — control who may hit which HTTP endpoints using Django's `has_perm`, group membership, or equivalent checks.
- **Model-level (table) gates** — control `add/change/delete/view` at the model level via `Permission`.
- **Operational convenience** — assign a **role** in one step so a user gets all the permission groups that match their job profile.
- **Clear storytelling** — a user's roles tell an audit-friendly story of who they are and what they're responsible for.
- **Clear boundary with row-level rules** — row-level scoping is **domain-based** (see [data_ownership.md](data_ownership.md)), not expressed through `Permission` rows per row.

---

## 3. Django built-ins — scope

### 3.1 Permission and permission group

- **`Permission`** — tied to models (and custom permissions).
- **Permission group (`auth.Group`)** — named collections of `Permission`. Users gain permissions by belonging to one or more groups.

These are the **only** built-in mechanisms used for:

- **Endpoint / route protection** — decorators, mixins, or middleware that consult `user.has_perm(...)` or group membership.
- **Full-model (table) gates** — whether a user may perform a class of action on a model.

### 3.2 What Django authorization is NOT used for

- **Row-level access** — for example "see only assets in domains I belong to." That is the **domain** filter, applied at query time (see [data_ownership.md](data_ownership.md)).
- **Dynamic scoping** — per-row rules based on business attributes belong in **managers, services, or policy objects**, not in `Permission` rows.

---

## 4. Roles

A **Role** is a named relationship between a user and a set of permission groups. It represents a real-world job profile (e.g., *Technician*, *Documentation Technician*, *Auditor*). Users can hold **multiple roles**; their effective permission groups are the **union** of all roles they hold.

**Key properties:**
- A user can hold zero or more roles.
- Permission groups are **only** assigned through roles (never directly).
- Roles can form a parent-child relationship for specialization, but only **one level deep**.
- No permission group overlap between a parent role and its child role.
- Removing a parent role cascades the deletion of dependent child roles.
- Each role assignment includes notes explaining why the user holds it.

For full details see [roles/concept.md](roles/concept.md), [roles/decisions.md](roles/decisions.md), and [Examples/roles_examples.md](Examples/roles_examples.md).

---

## 5. Roles and Data Domains are orthogonal

This application has **two independent systems** that work in parallel:

- **Roles** — bundles of permission groups (what you can *do*). Affects Django `has_perm` checks and route access.
- **Domain templates + UserDomain** — bundles of domains (what you can *see*). Affects row-level visibility filters.

Neither system affects the other. A user might be assigned the "Technician" role (granting specific capabilities) and the "Facility 1 Transportation" domain template (granting access to specific rows). Both are required; neither is derived from the other.

---

## 6. Summary rules

| Concern | Mechanism |
| :--- | :--- |
| Web routes / endpoints | Django auth + permission group membership / `has_perm` |
| Model-wide (table) capabilities | Django `Permission` on models; permission groups aggregate permissions |
| Bundling permission groups for a user | Roles + items → permission group membership (union across all active roles) |
| User's role assignment | Zero or more `UserRole` rows; each includes notes explaining why |
| Permission groups directly assigned | Not allowed; all groups come through roles |
| Role inheritance | Single-layer only: base roles (no parent) and specialized roles (one parent) |
| Cascade delete | Removing a parent role removes all child roles depending on it |
| Bundling domains for a user | Domain template + items → domain assignments |
| Per-row / scoped data access | **Domain** membership (via template or explicit `UserDomain`); see [data_ownership.md](data_ownership.md) |
| Two independent systems | Roles (what you can do) + domains (what you can see) are orthogonal |

---

## 7. Out of scope here

- Schema or field lists for roles — see [roles/concept.md](roles/concept.md) and related role files.
- Screen layouts, portal flows — see user-portal templates.
- Object-permission packages like `django-guardian` — not in use; stock `auth` only.
