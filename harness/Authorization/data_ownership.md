---
type: "Authorization Guide"
title: "Data ownership and the Data Domain primitive"
description: "This document describes how **data domains**, **organizations**, and **divisions** control row-level access and how they are distinct from Django's permission system."
tags: [authorization, authorization-guide]
context_tier: 2
---

# Data ownership and the Data Domain primitive

This document describes how **data domains**, **organizations**, and **divisions** control row-level access and how they are distinct from Django's permission system. Structural definitions of core tables (foreign keys, must-have edges) are in [../../docs/core_domain/core_models.md](../../docs/core_domain/core_models.md). How users carry assignments in the database and session is in [users.md](users.md). For Django-permission concepts, see [rbac.md](rbac.md).

---

## 1. Terminology note — why "Domain" and not "Ownership Group"

The two access systems in this application both used the word **"group"** for different things:

- A Django **permission group** (`auth.Group`) is a bundle of **permissions** — "what actions a user may perform."
- A data **ownership group** was a scope tagged on each row — "which records a user may see."

The overlap caused confusion. To keep the two systems cleanly separated, the data-scope primitive is now called a **Data Domain** (or simply **domain**). Every database row for scoped data carries a single domain. "Permission group" keeps its Django-permission meaning exclusively.

---

## 2. The Golden Rule

> **Access is determined strictly by whether a user belongs to the required Data Domain.**

- A data row carries exactly one **domain** (foreign key).
- A user may belong to **many** domains (many-to-many via `UserDomain`).
- A row is visible to a user if and only if its `domain` appears in the user's assigned domains.

**Nothing else in this application's row-level access model grants data visibility.** Not division, not organization, not permission groups, not templates. Domain membership is the **sole** row-level gate.

Domains can be assigned to a user two ways:
- **Via domain template** (convenience) — a named bundle of domains assigned as a unit.
- **Via explicit `UserDomain` assignment** (ad-hoc) — a single domain assigned directly.

Both paths result in the same outcome: the domain appears in the user's domain set.

---

## 3. Domain templates — scope bundles

A **Domain Template** is a named, pre-configured bundle of domains representing a real-world **scope profile**. Examples:

- *Facility 1 Transportation* (transportation_domain + supply_domain)
- *Cross-site Auditor* (all facilities + headquarters)

Domain templates are a **convenience** for assigning related domains together, not a separate access gate. A user assigned the *Facility 1 Transportation* template ends up with the same domain set as if those domains were explicitly assigned one-by-one. The template is purely organizational.

**Key properties:**
- Zero or more active templates per user (templates are tools, not permissions).
- Historical audit trail: every addition/removal of a domain to/from a template is timestamped and soft-deleted.
- No effect on permissions — domain templates manage data scope only.

See [domain_templates/concept.md](domain_templates/concept.md) for detailed semantics.

---

## 4. Organizations and divisions — informational only

The **Division → Organization → Domain** hierarchy exists for:

- **Navigation and administration** — grouping domains into portfolios so operators can find them.
- **Auditing** — matching a user's domain grants against the organization or division a user is expected to work within.
- **Bulk assignment convenience** — "assign me to this organization" can expand into "assign me to all of its domains" as a UI convenience.

Organizations and divisions **do not grant access by themselves**. Assigning a user to an organization does **not** implicitly let them see that organization's rows — only the explicit `UserDomain` rows do.

### 4.1 Cross-organization and cross-division grants are allowed

> It is **expected and explicitly allowed** for a user to be granted domains outside of their organization and division.

Real-world reasons this happens:

- An IT technician owned by the IT organization needs read access to a Facilities domain to troubleshoot kiosks.
- A shared-service auditor needs domains across every division.
- A contractor is "on loan" from one organization to another for a project.

Rather than prohibiting these grants, the system **allows them** and **surfaces them visibly** so operators can see at a glance when access crosses an organization or division boundary (see §6).

---

## 5. Overlap is intentional

Domains can appear under more than one organization. A shared facility, a joint operation, or a canonical group used across organizational boundaries is modeled naturally — the domain is linked to each organization it belongs to, and users from any of those organizations may be assigned to it.

---

## 6. Admin warning system (visual audit)

When viewing a user's domain grants, the UI warns operators whenever a grant falls outside that user's assigned organization or division. This is an **audit aid**, not a block — the grant still works.

| Color | Condition |
| :--- | :--- |
| **Red** (critical) | The user holds a **domain whose organization** the user is not assigned to. |
| **Yellow** (warning) | The domain's organization matches the user's organization, but the **division** does not — or the division matches but the organization does not. |
| **Default** (no warning) | The domain's organization and division both match one of the user's organization/division assignments. |

The warning is computed on the fly by comparing `UserDomain` → domain → organization → division against the user's `UserOrganization` and `UserDivision` rows.

### 6.1 Exception log

When an intentional cross-boundary grant is needed, it should be explained. The system supports a free-text **notes** field on the user's template assignment for that justification. Routing rules that grant data access by any other path — for example, an endpoint that filters by organization instead of domain — must be documented in [data_access_exceptions.md](data_access_exceptions.md).

---

## 7. The access check — how the two systems combine

A typical enforced query looks like:

> *"Give me all assets where `asset.domain_id` is in my assigned domain ids **and** I have the Django permission to view assets at all."*

- **Domain filter** answers: "on which **rows**?" (from domain template + explicit `UserDomain` assignments).
- **Django permission** answers: "may I perform this **action class** at all?" (from permission group template).

Both must pass. Row-level scoping is not expressible through Django's `Group`/`Permission` tables and is deliberately not stuffed in there.

---

## 8. Summary rules

| Concern | Mechanism |
| :--- | :--- |
| "May this user see this row?" | `row.domain_id in user.assigned_domain_ids` |
| "May this user perform this action class at all?" | Django `Permission` via permission group membership |
| "How are domains assigned to a user?" | Via domain template (bulk) or explicit `UserDomain` (ad-hoc) |
| "Where does this domain belong, organizationally?" | Division → Organization → Domain (informational only) |
| "Is this grant unusual?" | Admin warning system — red/yellow compared to user's assigned org/division |
| Cross-org / cross-division grants | **Allowed**; visible as warnings; context preserved in template/assignment history |
