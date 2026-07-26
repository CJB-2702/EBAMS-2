---
type: Architecture Guide
title: Engineering Standards
description: Core engineering principles and defaults for building in this project.
tags: [architecture, standards, principles, conventions]
---

# Engineering standards

## Engineering principles

- Prefer **Django built-in** APIs and `django.contrib` packages; avoid new dependencies unless justified by a locked decision (see [../technical_decisions.md](../technical_decisions.md)).
- Prefer **server-rendered HTML** with **Bulma** for layout and styling (vendored under `bulma-1.0.4/`).
- Use **HTMX** for dynamic interactions; prefer HTMX over ad-hoc JavaScript for partial updates.
- Long, explicit, **keyword-only** signatures over compact positional ones in the control layer.
- **Composition over inheritance.** Inheritance is reserved for strategy interfaces, not for sharing implementation.
- **Convention over configuration.** Naming conventions replace frameworks; disciplined imports and import-time registries only where needed.
- **Domain verbs over CRUD verbs.** Methods are named after business actions, not database operations.
- **Tech debt is greppable.** Undesired shortcuts use `# DELIBERATE ANTI-PATTERN` blocks with context.

## What "good" looks like in a PR

| Layer | Question to answer in review |
| :--- | :--- |
| Models | Does this row carry the audit FKs? Are constraints declared at the DB level? Any logic on the class needs a `# DELIBERATE ANTI-PATTERN` comment. |
| Control layer | Does the new class use a vocabulary suffix from [patterns/oop_control_patterns.md](patterns/oop_control_patterns.md)? Is the transaction boundary clear? |
| Search | Are filters longer than one line lifted out of the entrypoint? |
| Entrypoint | Does it create, update, or delete a row? If so, that work belongs in the control layer (see [layer_rules.md](layer_rules.md)). |
| Templates | Does it follow the `format=` contract and use the canonical card-footer pattern? |

## Stack pinning

- Django 6.x.
- Bulma 1.0.x, vendored.
- HTMX as the only AJAX layer.
- No SPA framework. No client-side router. No GraphQL.

Adding anything outside this list requires a locked decision recorded in [../technical_decisions.md](../technical_decisions.md).
