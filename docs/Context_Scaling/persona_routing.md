---
type: "Context Scaling Spec"
title: "Persona-Driven Context Routing (Slash Commands)"
description: "To prevent context pollution, the system uses **Slash Commands** to switch between specialized development roles."
tags: [context-scaling, context-scaling-spec]
context_tier: 2
---

# Persona-Driven Context Routing (Slash Commands)

To prevent context pollution, the system uses **Slash Commands** to switch between specialized development roles. Each command configures the AI with explicit instructions regarding which Tier 2 files to load into context.

```text
[/backend-persona]   -> Activates Backend Engineer Persona
                     -> Loads: docs/Architecture/*
                     -> Focuses on: layered architecture, OOP control patterns, models, endpoints.

[/frontend-persona]  -> Activates Frontend Engineer Persona
                     -> Loads: docs/UX_UI/*
                     -> Focuses on: HTMX patterns, Bulma, format= contract, accessibility, components.

[/admin-persona]     -> Activates Admin Engineer Persona
                     -> Loads: docs/Authorization/*
                     -> Focuses on: RBAC, Data Domains, roles, templates, password policy.

[/code-architect-persona] -> Activates Code Architect Persona (review-only)
                          -> Loads: docs/Architecture/*, docs/UX_UI/* (read-only review)
                          -> Focuses on: smells, severities, design patterns.

[/business-persona]  -> Activates Business Architect Persona (no code)
                     -> Loads: docs/ApplicationGoals.md
                     -> Focuses on: user goals, workflows, priorities.
```

## Core Persona Rules

* **Context Isolation:** Invoking a persona command purges unrelated Tier 2 files from the immediate context window, maintaining strict token hygiene.
* **Dynamic Tier 3 Pulls:** When a persona is active and encounters a complex implementation task, it must look at the active Tier 2 document to identify and pull only the specific Tier 3 example files tied to that component.
* **Domain Skeleton Bundles:** Before beginning implementation work, the persona should load the relevant domain skeleton bundle and run the Tier 4 mapping script against the listed paths. See [domain_skeleton_bundles_spec.md](domain_skeleton_bundles_spec.md).
* **Persona definitions live in `.claude/agents/`.** The slash command files in `.claude/commands/` activate the persona; the agent profile is the source of truth for the persona's knowledge and tone.
