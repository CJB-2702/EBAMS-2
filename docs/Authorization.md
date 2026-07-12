---
type: "Concept Anchor"
title: "Authorization — Tier 1 Anchor"
description: "This file is the **concept anchor** for identity, capability, and row-level access."
tags: [overview, concept-anchor]
context_tier: 1
---

# Authorization — Tier 1 Anchor

The two-gate model that every request passes through, the vocabulary that keeps the systems distinct, and the rules that govern templates, roles, and audit. Detail lives in the Tier 2 files below.

---

## Core ideas

- **Two gates, fully orthogonal.** Every action faces a **capability gate** (Django permissions, via permission groups bundled by roles) and a **scope gate** (the Data Domain primitive, assigned via templates or explicit rows). Both must pass; neither implies the other.
- **The Golden Rule for data scope.** A row is visible to a user if and only if its `domain` is in the user's assigned domain set. Not division, not organization, not permission group. The domain membership is the **sole** row-level gate; deviations are logged.
- **Permission groups are Django `auth.Group` rows, never social groups.** A permission group bundles capabilities for one feature ("Asset Lifecycle", "Audit Reports"). Users never hold permission groups directly — every group arrives via a role.
- **Roles tell the story.** A role is a real-world job profile (Technician, Auditor, Supply Coordinator). Users hold zero or more; the effective permission group set is the union. Role inheritance is one level deep, parent → child, no overlap between parent and child.
- **Domain templates are scope bundles.** A domain template names a set of domains for a job profile (Facility 1 Transportation, Cross-site Auditor). Assigning a template *copies* its domains into the user's `UserDomain` rows — those rows are the source of truth, not the template.
- **Organizations and divisions are informational.** They group domains for navigation and audit; they do not grant access. Cross-organization and cross-division grants are allowed and surfaced as red/yellow warnings, not blocked.
- **Sessions are the runtime snapshot.** At login, `user_domain_ids` and `user_permission_codenames` are stored in the session. Every request checks the session, not the database. Revocations trigger an explicit refresh.

---

## Sub-specifications

See [Authorization/index.md](Authorization/index.md) for the full, machine-routable index of Tier 2 guides, skeletons, and sub-bundles (RBAC, data ownership, users, roles, domain templates, password policy, data access exceptions).

---

## Reference directionality

This anchor references **only** files inside `Authorization/`. The two-gate model interacts with [applications/core_domain.md](applications/core_domain.md) (Data Domain is a core entity) and with the layer rules in [Architecture.md](Architecture.md) (policies are guards, contexts own writes); the relevant cross-cutting lines are summarised here so a request review never requires reading more than one Tier 1 file plus its Tier 2 children.
