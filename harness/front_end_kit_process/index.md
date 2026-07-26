---
okf_version: "0.1"
type: "Index"
title: "Front-End Kit Process Knowledge Bundle"
description: "How-to guides for each stage of the Front-End Kit methodology — routes, navigation, workflows, and the optional Flask stager."
tags: [front-end-kit-process, index, okf]
context_tier: 1
personas: [frontend]
---

# Front-End Kit Process

Per-stage how-to guides used by the Front-End Kit agent (`/front-end-kit`) when turning a finished starter kit into a front-end plan.

- [How to Write the Route Skeleton](how_to_write_the_route_skeleton.md) — the page spine.
- [How to Map Navigation](how_to_map_navigation.md) — reachability gate.
- [How to Identify Workflows](how_to_identify_workflows.md) — workflow review gate.
- [How to Write a Key Workflow Document](how_to_write_a_key_workflow.md) — one file per critical workflow.
- [How to Write the Coverage Report](how_to_write_the_coverage_report.md) — advisory gap analysis.
- [How to Build the Flask Stager](how_to_build_the_flask_stager.md) — optional clickable mockup.

---

## The two-kit split

| | Starter kit (`<topic>_starter_kit/`) | Front-end kit (`front-end-kit/<topic>/`) |
| :--- | :--- | :--- |
| **Covers** | Problem, business rules, domain data, control layer | Routes, page goals, navigation, workflows, wizard decisions |
| **Stops at** | "The backend could theoretically perform these tasks" | The UI exists |
| **Lifespan** | **Durable** — stays valid as focused context for future updates | **Disposable** — deleted once the UI is built |
| **Drift** | Business-rule changes are corrected here and back-propagated | Never resynced; the real UI is the truth after first build |
| **Process guides** | [../starter_kit_process/index.md](../starter_kit_process/index.md) | this bundle |

The starter kit is worth maintaining because business rules barely move. The front-end kit is not, because the developer reshapes the UI by taste the moment they can see it. It is scaffolding — committed to git so it can be reviewed and diffed, then deleted when spent.

---

## Input order: kit first, code second

The front-end kit reads the **starter kit** as its primary source of truth, and the **built code** as a cross-check.

This ordering is deliberate. The point of the front-end kit is to let the developer see and correct the plan *before* anything is built — catching flaws in the domain logic while they are still cheap. A front-end kit that derives itself from existing code can only ratify what is already there.

| Source | Role | Where |
| :--- | :--- | :--- |
| `functionality_and_roles.md` | What capabilities exist and who may perform them → drives the page list | Starter kit root |
| `model_diagram.md` | Tables and **reverse FKs** → drives the wizard decision | Starter kit root |
| `control_layer_plan.md` | Contexts, Managers, Handlers → what each page action calls | Starter kit phase folders |
| `business_concept.md` | Domain language for page goals and copy | Starter kit phase folders |
| `app/<subapp>/models/` | Cross-check: does the plan match what was built? | Repo, if built |
| `app/<subapp>/control_layer/` | Cross-check: does a method exist for each action? | Repo, if built |

When the kit and the code disagree, **say so and stop** — that is a finding for the developer, not something to silently reconcile.

---

## Gates

Two checks are **hard gates**. The kit is not finished until both pass, or the developer explicitly waives one in writing:

1. **Navigation reachability** — every route has at least one inbound edge from another route or a named entry point. No orphans.
2. **Workflow review** — every create and edit page carries a written verdict: simple form or multi-card wizard, with a stated reason.

Coverage analysis (table × CRUD, role × capability) is **advisory**. Report the gaps; do not block on them.

---

## Standing UI law — consume, never re-derive

The front-end kit **applies** the project's visual and interaction rules. It does not invent them. Cite these rather than restating them:

- [../UX_UI/components/multi_step_flows.md](../UX_UI/components/multi_step_flows.md) — one route, vertical scroll, progressive enablement, session drafts; the multi-card wizard trigger rule.
- [../UX_UI/components/modals.md](../UX_UI/components/modals.md) — when a modal is appropriate, and why assignment never goes in one.
- [../UX_UI/Examples/left_heavy_assignment_card_pair.md](../UX_UI/Examples/left_heavy_assignment_card_pair.md) — the in-page assignment pattern.
- [../UX_UI/components/dual_listbox.md](../UX_UI/components/dual_listbox.md) — the auditable many-to-many control.
- [../UX_UI/format_contract.md](../UX_UI/format_contract.md) — the `format=` density and HTMX-fragment contract.
- [../UX_UI/page_structure.md](../UX_UI/page_structure.md) — page shell, hero, sidebars.
- [../Architecture/patterns/endpoint_patterns.md](../Architecture/patterns/endpoint_patterns.md) — OOP endpoint design.
- [../Architecture/patterns/htmx_patterns.md](../Architecture/patterns/htmx_patterns.md) — the F5 rule.

If a page seems to need a pattern none of these cover, flag it as an open question rather than inventing a component.
