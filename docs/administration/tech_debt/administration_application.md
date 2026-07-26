---
type: "Technical Decision"
title: "Administration application — pending architecture work"
description: "Notes two pending architecture changes for the administration sub-app: a possible Departments model and related scoping work."
tags: [technical-decisions, technical-decision, tech-debt]
context_tier: 2
---

# Administration application — pending architecture work

## What

Two related pending changes for the administration sub-app:

1. **A `Departments` model is likely needed between organizations and domains.** The current hierarchy is `Division → Organization → Domain`. Several real-world use cases want a department-level grouping inside an organization (e.g. an Auditor that covers all departments of one organization but only one specific facility). Today this requires either an awkward custom domain or many manual `UserDomain` grants.
2. **Data-access exceptions should become a `.claude` rule.** Today the [data_access_exceptions log](../../Authorization/data_access_exceptions.md) is hand-maintained. As routes that deviate from the Golden Rule accumulate, the log should be enforced by an agent rule that flags any new route filtering by organization or division without a corresponding entry.

## Why deferred

- The departments layer needs design buy-in from operators first — adding a new entity to the hierarchy changes the admin UI shape and the assignment portals.
- The `.claude` rule needs at least one or two real exception entries to test against; right now the log is empty.

## What "fixed" looks like

- A `Department` model under `app/administration/models/organizational/`, with FKs from `Domain` (`department`, nullable until backfill) and from `Organization → Department` (one-to-many).
- A migration path: every existing domain gets a department, defaulting to a single "Default" department per organization.
- An updated admin UI showing the four-level hierarchy: Division → Organization → Department → Domain.
- A code-review rule, possibly enforced via `.claude/agents/admin-engineer.md`, that flags new routes filtering by org/division without an `data_access_exceptions.md` entry.
