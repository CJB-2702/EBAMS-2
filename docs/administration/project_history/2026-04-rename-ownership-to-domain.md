---
type: "Technical Decision"
title: "Renamed \"ownership group\" → \"Data Domain\""
description: "The data-scope primitive is renamed from **\"ownership group\"** to **\"Data Domain\"** (or simply **\"Domain\"**)."
tags: [technical-decisions, technical-decision, history]
context_tier: 2
---

# Renamed "ownership group" → "Data Domain"

- **Date:** 2026-04
- **Context / feature:** Authorization system, data-ownership primitive.

## Decision

The data-scope primitive is renamed from **"ownership group"** to **"Data Domain"** (or simply **"Domain"**). Every database column, model, manager, template, URL, and doc that previously referenced "ownership group" has been migrated to "domain". The Django permission concept retains the name **"permission group"** exclusively.

## Rationale

The two access systems both used the word "group" for different things:

- A Django **permission group** (`auth.Group`) is a bundle of **permissions** — *what actions a user may perform*.
- A data **ownership group** was a scope tagged on each row — *which records a user may see*.

The overlap caused regular confusion in code reviews, in the admin UI, and in conversations with operators. Renaming the data-scope primitive eliminates the ambiguity at the cost of a one-time rename pass.

## What changed

- Model: `OwnershipGroup` → `Domain`. Through-tables renamed accordingly (`UserOwnershipGroup` → `UserDomain`, etc.).
- Control-layer family: `control_layer/ownership/` → `control_layer/data_ownership/`.
- Templates: `templates/ownership_portal/` → `templates/data_ownership_portal/`.
- URLs: `/administration/ownership-groups/` → `/administration/domains/`.
- Session key: `user_ownership_group_ids` → `user_domain_ids`.
- Docs: all references updated.

## Implications

- New developers reading the code do not have to disambiguate "group" each time.
- Audit conversations can use "domain" without further qualification.
- The rename is a hard break; downstream branches that predate it require a manual merge.
