---
type: Architecture Example
title: Polymorphic attachment tables — worked example
description: Concrete worked example of the "multiple concrete tables over one overloaded table" rule in [../patterns/model_patterns.md](../patterns/model_patterns.md).
tags: [architecture, models, example]
context_tier: 3
---

# Polymorphic attachment tables — worked example

Supports [../patterns/model_patterns.md](../patterns/model_patterns.md) §5 (Polymorphic data and "view together" scenarios).

When **separate tables** share a structural idea (e.g. "attachment link to some parent") but **different foreign-key targets** or **type defaults**, prefer **multiple concrete tables** over one overloaded table when integrity matters:

- **comment attachments** vs **maintenance attachments**
  - `comment_attachments`: `linked_to_id` FK → comment; `linked_to_type` default `"comment"`.
  - `maintenance_attachments`: `linked_to_id` FK → maintenance event; `linked_to_type` default `"maintenance"`.

For rows that must be **unioned or searched in one stream**, use **UUID7** on the link or attachment entity so a union does not require a hand-rolled sequence generator shared across tables.
