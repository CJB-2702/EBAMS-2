# Roles — Concept

This document describes the **business concept** of a role, the rules it enforces, and how it interacts with the rest of the access system. It is the source of truth for *what* roles are and *why* they exist. For the unique design decisions made, see [roles_decisions.md](roles_decisions.md). For common scenarios, see [roles_examples.md](roles_examples.md).

---

## 1. Definitions

### 1.1 Permission group

A **Permission Group** is an atomic bundle of Django permissions (`auth.Permission` rows) tied to a **specific action or feature**. It answers the question: "What permissions does a person need to do **this one thing**?"

Examples:
- *Asset Lifecycle* — permissions to add, change, delete, view assets
- *Supply Management* — permissions to manage supply requests and inventory
- *Audit Report Generation* — permissions to generate and export compliance reports
- *User Administration* — permissions to add, edit, disable users and assign roles

Permission groups **do not** describe groups that people belong to. They are **not** organizational units or teams. They are **atomic capability bundles** — indivisible sets of permissions needed to complete a specific job function or feature interaction.

### 1.2 Role

A **Role** is a named relationship between **humans** and a **set of permission groups**. It represents a real-world **job profile or specialization** — the aggregated capability set and responsibilities a person holds.

Examples of roles a user might hold:
- *Technician* — base field technician role
- *Documentation Technician* — specialization of Technician; adds documentation responsibilities
- *Facilities Auditor* — audit and reporting across facilities
- *IT Manager* — IT team leadership and escalation oversight
- *Cross-site Supply Coordinator* — supply chain across multiple locations

A role bundles many permission groups together so that **assigning a role to a user means: "This user should be able to do everything this role requires."**

---

## 2. Why roles exist (and why they're different from permission groups)

Three concrete problems:

1. **Direct permission group assignment is fragile.** A real job function requires multiple permission groups (e.g., a Technician might need Asset Lifecycle, Supply Management, and Equipment Tracking groups). Assigning twenty users to five permission groups each means 100 error-prone clicks. Roles reduce that to 20 clicks.

2. **Roles tell the story of who someone is.** When an administrator views a user, seeing raw permission groups tells them *what* the user can do. Seeing roles (`Technician > Documentation Technician`, `Auditor`) tells them *who* the person is and what their **responsibilities** are. This storytelling is critical for audit, access review, and avoiding silent permission creep.

3. **Roles are stable; permissions evolve.** When a new feature ships and requires permissions, an operator updates the permission group once. Every user who holds a role that includes that group automatically gains the permission.

---

## 3. The relationship between roles and domains

**Roles and Data Domains are orthogonal systems.**

- **Roles** determine what **actions** a user can perform (`has_perm` checks).
- **Data Domains** determine what **rows** a user can see (row-level visibility filters).

See [data_ownership.md](data_ownership.md) for the domain system.

---

## 4. Core rules

### Rule 1 — Multiple roles per user

A user can hold **zero or more** roles at the same time. When a user holds multiple roles, their **effective permission groups are the union of all roles' permission groups**.

### Rule 2 — Single-layer role inheritance

Roles can form a **parent-child relationship**, but only **one level deep**. A role specializes on a parent role, extending its permission groups.

- **Base role** — has no parent. Example: *Technician*.
- **Specialized role** — has exactly one parent. Example: *Documentation Technician* (parent: *Technician*).

**Constraint:** A specialized role cannot itself be a parent. The role hierarchy is a forest of shallow trees, max depth 2.

### Rule 3 — No overlap between parent and child

A specialized role **cannot include the same permission groups as its parent**. The parent groups come automatically; the child adds *new* groups.

When a user holds a specialized role, they get:
- All permission groups from the **parent role**
- All permission groups from the **specialized role**
- But no duplicates

### Rule 4 — Cascade delete on role removal

When a role is removed from the system, all roles that depend on it are also removed. The system warns of all dependent roles before confirming deletion.

**Important distinction:** removing a role from a **user** is different from deleting a role from the **system**.
- Removing a role from a user: just that role disappears from the user.
- Deleting a role from the system: triggers cascade deletion of dependent roles, affects all users who held that role.

### Rule 5 — Role relationship types

Each role assignment to a user has a **relationship** that contextualizes why they hold that role:

- **primary** — the user's main job title.
- **specialty** — a secondary, specialized role.
- **side_job** — occasional duties outside the main role.
- **for_fun** — training, temporary coverage, or learning role.

These are **labels only**, not technically enforced. They help administrators understand the user's responsibilities at a glance.

### Rule 6 — Assignment notes

Each user's role assignment has a **notes** field for free-text justification. This explains *why* the user holds their roles — especially for non-primary or unusual assignments.

### Rule 7 — Permission groups are never directly assigned

Permission groups are **only** assigned through roles. A user cannot hold a permission group unless it comes from a role they hold. This keeps the "story" clear: when an auditor asks "why does Jane have the Asset Lifecycle permission group?", the answer is always "because she holds the Technician role."

**Exception:** drift detection. If a permission group is removed from a role, but a user still holds it (because another role they hold includes it), that is tracked as a valid state, not an error.

### Rule 8 — Roles do not grant data access

Roles manage **permission groups** (capability access). They have **zero** effect on **Data Domain** assignments (row-level access). A user with the *Technician* role still sees no rows until they have a domain template assignment or explicit `UserDomain` rows.

---

## 5. The full access picture

When a user interacts with the application, **two gates** must pass:

1. **Capability Gate** — "Does my effective permission group set (from all my roles) include the permission Django needs for this action?"
2. **Scope Gate** — "Does the row I'm about to touch live in a Data Domain I'm assigned to?" (see [data_ownership.md](data_ownership.md)).

Roles **only** affect gate 1. They have **zero** effect on gate 2.

---

## 6. Summary

| Concern | Mechanism |
| :--- | :--- |
| "What can this user do?" | Union of all permission groups from all roles they hold. |
| "Why does the user hold this role?" | Role relationship type (primary/specialty/side_job/for_fun) + assignment notes. |
| "Who holds a particular role?" | Query: User → UserRole → Role. |
| "If I delete this role, what breaks?" | All dependent (child) roles; system shows transitive tree before confirming. |
| "If I remove a role from a user, do they lose all permissions?" | No — only permissions **unique to that role** are removed. |
| "How are roles and domains related?" | Orthogonal. Roles grant actions; domains grant row visibility. Both required for access. |
| "Can permission groups be assigned directly?" | No — only through roles. |
