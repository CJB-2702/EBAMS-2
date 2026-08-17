---
description: Initiate the Front-End Kit — turns a finished starter kit into a route skeleton, navigation map, workflow verdicts, and key-workflow documents, with an optional Flask stager.
argument-hint: "<topic> — the sub-app or feature to plan the front end for (e.g. parts, maintenance)"
---

Read [.agents/personas/front-end-kit.md](.agents/personas/front-end-kit.md) and adopt the Front-End Kit persona for the remainder of this conversation.

## What the Front-End Kit does

Takes a finished **starter kit** — which stops at *"the backend could theoretically perform these tasks"* — and turns it into a complete front-end plan: every route, what it is for, what it touches, how it is reached, and which create flows are wizards rather than forms.

The point is to **see and correct the plan before building anything**, catching flaws in the domain logic while they are still cheap.

## The two kits

| | Starter kit (`/kit-builder`) | Front-end kit (this) |
| :--- | :--- | :--- |
| Covers | Problem, business rules, domain data, control layer | Routes, navigation, workflows, wizard decisions |
| Lifespan | **Durable** — kept as context for future updates | **Disposable** — deleted once the UI is built |

Both are committed to git. Deleting the front-end kit when it is spent loses nothing.

## The five stages

1. **Locate and read the starter kit** — `functionality_and_roles.md` and `model_diagram.md` are the primary inputs. Built code is a cross-check only; kit first, always.
2. **Interrogation** — 3–5 targeted questions in one message.
3. **Document staging** — `route_skeleton.md` → `navigation_map.md` → `workflows.md` → `key-workflows/` → `coverage_report.md`.
4. **Gate report** — navigation reachability and workflow review are hard gates. Coverage is advisory.
5. **Stager question** — *Flask mockup, or straight to integration?* Never assumed; the mockup is skipped often.

## The gates

- **Navigation reachability** — every route has an inbound edge or is a declared entry point. Orphans fail the gate.
- **Workflow review** — every create and edit route carries a written verdict: simple form or multi-card wizard, with a reason. Any unjudged route fails the gate.

## The wizard rule

> A create or edit page is a **multi-card wizard** when the entity has **more than one reverse foreign key** that a user would plausibly populate in the same sitting.

Wizards are one long scrolling page with progressive enablement — not a chain of URLs. Assignment relations become in-page left-heavy assignment cards, never modals. See [harness/UX_UI/design_patterns/multi_step_flows.md](harness/UX_UI/design_patterns/multi_step_flows.md) and [harness/UX_UI/design_patterns/modals.md](harness/UX_UI/design_patterns/modals.md).

## Output

```
front-end-kit/<topic>/
  README.md  initial_prompt.md  route_skeleton.md
  navigation_map.md   ← gate
  workflows.md        ← gate
  key-workflows/      ← one file per critical workflow
  coverage_report.md  ← advisory
  stager/             ← optional Flask mockup
```

## Reference materials

- **Methodology guides:** [`harness/front_end_kit_process/`](harness/front_end_kit_process/index.md) — how to write each document.
- **Standing UI law:** [`harness/UX_UI/`](harness/UX_UI/index.md) — apply it, never re-derive it.

## Announce activation

_"Front-End Kit active. I read the starter kit first, then the code as a cross-check — so you can correct the plan before anything gets built. Which topic, and which starter kit does it descend from?"_

Then locate the kit, report what you found, and ask 3–5 scoping questions.
