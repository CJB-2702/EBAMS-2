# Users and administration (concepts)

This document describes how **users** participate in **administration**: dependency of audited models on a **user** table, **permission group template** metadata stored per user, **Django group (permission group) membership**, and **Data Domain** assignments used for row-level scope. For Django permission mechanics and templates, see [rbac.md](rbac.md). For the Data Domain primitive and its hierarchy, see [data_ownership.md](data_ownership.md).

---

## 1. Auditing and the user table

Core and downstream apps use **auditable** models (creator, timestamps, last updater). That pattern assumes a shared **user** model (or compatible FK target) for those references. See [../CoreDomain/core_models.md](../CoreDomain/core_models.md) for which domain models are auditable.

---

## 2. Permission group template assignment on the user

A user may have **at most one** active permission group template assignment at a time. The assignment row (`UserPermissionGroupTemplate`) records:

- The template id (which profile the user was given).
- The **notes** field — free-text justification captured at assignment time.
- Audit fields (created at/by, updated at/by).

The template assignment is **metadata**; authorization checks still rely on **resolved permission group membership** as Django defines. When the template changes, the user's permission group membership is synced (rebase by default, with an optional additive toggle).

---

## 3. Domain template assignment on the user

A user may have **zero or more** active domain template assignments. Each assignment row (`UserDomainTemplate`) records:

- The template id (which scope profile the user was given).
- Audit fields (created at/by, updated at/by).

The template assignment is **metadata**; the real access control happens through the **resolved domain set** — the union of domains from the template(s) and explicit `UserDomain` rows. When templates are added or removed, the user's domain set is resynced — see [architecture_summary.md](architecture_summary.md) for the propagation rules.

---

## 4. Data domain assignments

A user's **domain set** (the domains they can see) is the **union** of:

1. Domains from their active **domain template(s)** (if assigned).
2. Explicit **`UserDomain` rows** (ad-hoc assignments, may have expiration).

**Database source of truth** — `UserDomain` rows hold explicit assignments. The domain template merely defines a reusable bundle that feeds into these assignments.

**Session snapshot** — at login, the user's complete domain set (from both template + explicit assignments) is snapshotted into the session (`user_domain_ids`) so every route can enforce scope without re-resolving from the database on every request. This is critical for performance: every data-filtered query consults the session, not the DB.

Combining **Django permissions** with the **domain filter** is the standard pattern for "may this user do this action on **these** rows?" — not `Permission` rows per row.

### 4.1 Organization and division assignments

Users also have `UserOrganization` and `UserDivision` rows. These are **informational only** — they describe where the user "sits" in the organizational hierarchy. They do **not** grant row-level access. See [data_ownership.md](data_ownership.md) §4.

The admin warning system compares a user's data domain grants against their organization/division assignments to flag:

- **Red** — the user holds a domain whose organization is not among the user's assigned organizations.
- **Yellow** — organization matches but division does not (or vice versa).
