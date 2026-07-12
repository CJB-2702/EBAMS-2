---
type: "Concept Anchor"
title: "Application Goals — Tier 1 Anchor"
description: "This file is the **concept anchor** for product intent: what the application is for, who uses it, and the user-centric outcomes that shape every other decision."
tags: [overview, concept-anchor]
context_tier: 1
---

# Application Goals — Tier 1 Anchor

Product intent: what the application is for, who uses it, and the user-centric outcomes that shape every other decision. There are no Tier 2 sub-specifications yet — goals stay at this level until a specific roadmap document needs its own dedicated folder.

---

## Vision

Create an internal application to **manage assets and locations**, **track usage and assignments**, and **enforce role-based access** to both application capabilities and the underlying data. The application is server-rendered, multi-tenant by data domain, and used primarily by operations staff working across multiple facilities and organizations.

---

## Primary users

- **Field technicians** — record events, attach evidence (photos, documents), update asset status, and submit part demands.
- **Auditors and compliance reviewers** — read across domains they have been explicitly granted, review the full revision history of comments and events, and confirm cross-boundary grants are justified.
- **Operations administrators** — manage users, assign roles and domain templates, curate the domain → organization → division hierarchy, and review the data-access exception log.
- **System administrators** — manage the Django admin, rotate secrets, run database rebuilds during active development, and review incidents and tech-debt entries.

---

## User-centric outcomes the system is designed for

- **One coherent product, not a constellation of micro-apps.** A user moves between portals (Events, Administration, Assets, Maintenance, Inventory) without losing context. Breadcrumbs always return to a single application root.
- **The F5 rule is a user promise.** Any page can be refreshed at any time and the user lands in the same step, with the same draft data, on the same record. This is what makes "server-rendered with HTMX layered on top" a reliability claim, not just a stack choice.
- **Audit is a first-class output, not a side effect.** Every action the system performs — every comment edited, every domain granted, every cascade delete — leaves a record an auditor can later follow without engineering help.
- **The two-gate access model is explicit.** Users see, in plain language, why they hold the access they hold (which roles, which domain template, which manual grants). Operators see warnings — not blocks — when access crosses an organisational boundary.
- **Operations staff are the primary audience for admin tooling.** Admin interfaces are not "advanced settings hidden in a corner." They are first-class portals with the same visual language and density rules as the rest of the application.

---

## What this application is *not*

- **Not a public-facing SaaS.** Only `app/public_app/` exposes unauthenticated routes (login, signup); everything else is authenticated by default. Parallel "public" mirrors elsewhere are an anti-pattern.
- **Not a generic CMS.** Content models are domain-specific (events, assets, part demands), and the role system is built around real-world job profiles, not abstract permission registries.
- **Not a real-time collaboration tool.** Updates propagate via standard request/response cycles, with HTMX as the interactivity layer. There is no websocket/CRDT layer.

---

## Reference directionality

This anchor stands alone at Tier 1. Locked product decisions and historical context move to [technical_decisions.md](technical_decisions.md) once they are finalised; in-progress feature plans live in the relevant domain anchor's Tier 2 area (for example a future *maintenance* roadmap would live under a new `Maintenance/roadmap.md` rather than expanding this file).
