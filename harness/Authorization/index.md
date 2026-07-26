---
okf_version: "0.1"
type: "Index"
title: "Authorization Knowledge Bundle"
description: "Two-gate access model (capability + row-level scope), roles, domain templates, and RBAC docs."
tags: [authorization, index, okf]
context_tier: 1
personas: [admin]
---

# Authorization

RBAC, Data Domain row-level scoping, roles, and domain templates for this project.

## Guides

- [Role-Based Access Control (Concepts)](rbac.md) — Django permission groups vs. house "roles".
- [Data Ownership and the Data Domain Primitive](data_ownership.md) — row-level scope and the Golden Rule.
- [Users and Administration (Concepts)](users.md) — how users, groups, and Data Domain assignments relate.
- [Roles — Concept](roles/concept.md) — the business concept of a role.
- [Roles — Design Decisions](roles/decisions.md) — why the role system is shaped the way it is.
- [Roles — Examples](Examples/roles_examples.md) — common role assignment scenarios.
- [Domain Templates — Concept](domain_templates/concept.md) — the domain template business concept.
- [Domain Templates — Models and Control-Layer Plan](domain_templates/models_plan.md) — architectural plan for domain templates.
- [Authorization Architecture — Design Decisions](architecture_decisions.md) — trade-offs in the two-gate system.
- [Authorization & Scope System — Complete Architecture](architecture_summary.md) — how permissions and scope work together.
- [Data Access Exceptions Log](data_access_exceptions.md) — every deviation from the Golden Rule.
- [Password Policy (OWASP-Compliant)](password_policy.md) — password requirements.

## Skeletons

- [RBAC / Permission / Domain Template — Skeleton Bundle](skeleton_instructions.md) — context-scan bundle for authorization changes.

## Sub-bundles

- `Examples/` — role assignment scenarios, domain template field/method/URL detail, session snapshot code.
