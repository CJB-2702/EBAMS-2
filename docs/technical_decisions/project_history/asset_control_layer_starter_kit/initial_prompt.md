---
type: "Technical Decision"
title: "Initial Prompt"
description: "This kit originates from the following request (captured verbatim, spelling."
tags: [technical-decisions, technical-decision, project-history, asset-control-layer-starter-kit]
context_tier: 2
---

# Initial Prompt

This kit originates from the following request (captured verbatim, spelling
preserved). It is the source of truth for *intent*; the planning docs translate
it into this project's architecture.

---

> migrate control logic from
> /home/cb/REPOS/asset_management/app/business/core
> /home/cb/REPOS/asset_management/app/business/assets
> into
> /home/cb/REPOS/Django-Starter-Kit/app/assets/control_layer
>
> contrast archetectures between the asset management application and this
> application before building to get a better understanding of the changes from
> /home/cb/REPOS/asset_management/Design
> to
> /home/cb/REPOS/Django-Starter-Kit/docs
> build according to this repos archetecture
>
> Key changes to take note of
> the previous application used the concept of Major location for data access
> controls this application uses data domains
>
> In the previous application asset class make model and asset were a part of core
> in this application asset class, model and asset were transitioned into the
> assets application
>
> pull all relevant files into context and interrogate me about the changes
> /backend-persona

---

## Clarifying decisions captured during interrogation

These answers refined the scope and are now binding inputs to the kit:

1. **Core scope.** Migrate `AssetContext` and `MakeModelContext` logic into
   `app/assets/control_layer`. Additionally, compare and contrast this app's
   event-context tooling against the old app's `EventContext`, and update the
   new event tooling as needed. *The event context is the core of the
   application and must always be considered.* → see
   [`event_context_study.md`](event_context_study.md).

2. **Creation flow.** Use an **explicit orchestrator**, not the old pluggable
   post-create pipeline. → see [`decisions.md`](decisions.md) (D1) and the
   project-root [`optional_detail_hooking.md`](../optional_detail_hooking.md).

3. **Lifecycle eventing.** Wire eventing into the new `events` app
   infrastructure, extending that app as needed (rather than stubbing it).

4. **Breadth.** This is a multi-phase project. Build this starter kit with one
   sub-kit per phase. Chosen order:
   **P1 asset+model contexts → P2 details → P3 configurations → P4 capabilities**
   (rationale in [`README.md`](README.md)).

---

## Phase 2 reframe — details become a plugin framework (2026-06-04)

A later session recast Phase 2. Captured verbatim intent:

> reconsider the details system as an asset plugin management system, rename it
> from details to plugins. for now first party only plugins that will be directly
> coded in. the goal is to make the framework for plugins that can be configured
> on asset class and model in a similar way as the old repository. each plugin has
> its own card on the asset page, its own set of details and rules within its
> internal app. scrap the initial plan of asset and model details being hard
> linked — the goal is an extendable system.

Clarifying decisions captured during this interrogation (now binding):

1. **Plugin home.** Plugins are packages under `app/assets/plugins/<plugin_name>/`
   — modules, **not** separate Django apps.
2. **Plugin data.** Each plugin owns its **own concrete typed table**, provisioned
   through a **factory interface** (the extension seam). Today the factory creates
   one primary row; later it may create a cluster around that primary table.
3. **Minimum contract.** target (asset vs. model) + cardinality (one-to-one vs.
   one-to-many). Rules / derived status are deferred — "keep it simple, enhance
   later."
4. **Lifecycle.** **On-create hook only** for now.
5. **Enablement tables renamed** to `asset_plugins_by_asset_class`,
   `asset_plugins_by_model`, `model_plugins_by_asset_class`; model plugins are
   enabled **by asset class**.
6. **Kit boundary.** **Rewrite Phase 2** in place (split into 2a framework /
   2b ported plugins). **UI is out of scope** — control layer + framework interface
   only. P3 / P4 untouched.

See [`decisions.md`](decisions.md) D4/D5 and
[`brainstorming_session_20260604.md`](brainstorming_session_20260604.md).
