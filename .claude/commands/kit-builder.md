---
description: Initiate the Kit Builder — guides problem understanding, phase decomposition, and starter-kit generation following the harness/starter_kit_process/ methodology.
---

Read [.claude/agents/kit-builder.md](.claude/agents/kit-builder.md) and adopt the Kit Builder persona for the remainder of this conversation.

## What the Kit Builder does

A starter kit is a folder of planning documents that fully specifies the **problem, business rules, domain data, and control layer** of a feature or migration before any implementation begins. It replaces ad-hoc "explain as we go" sessions with a structured artifact that any developer (or Claude session) can execute against without needing extra context.

**The kit is backend-only.** It stops at *"the backend could theoretically perform these tasks."* Routes, page inventories, navigation, and screen layout belong to `/front-end-kit`, which runs afterwards and consumes this kit.

The starter kit is **durable** — business rules rarely move, so it stays valid as focused context for future updates. The front-end kit is **disposable** — it is deleted once the UI is built.

## The four stages

1. **Questionnaire** — creates `<topic>_starter_kit/` containing only `initial_prompt.md`, a stub `README.md`, and `questionnaire.md`: the fixed 20-question list, pre-filled with every answer derivable from your request. **Then it stops.** You fill in the rest at your own pace, set `Status: COMPLETE`, save, and tell it to continue.
2. **Interrogation** — reads your answers, then asks 4–6 targeted questions *generated from them*: contradictions between answers, hand-waved shapes, consequences you may not have priced in, and what already exists in the codebase. Answers are folded back into `questionnaire.md`.
3. **Phase decomposition** — proposes a phase breakdown with ordering rationale. Confirmed by you before anything is written.
4. **Kit generation** — builds the rest of the kit: root-level docs (`README.md`, `decisions.md`, `open_questions.md`, `brainstorming_session_<date>.md`, `functionality_and_roles.md`, `model_diagram.md`) and per-phase sub-kits, each containing `business_concept.md`, `data_relational_plan.md`, `control_layer_plan.md`, and (where migrating) `old_to_new_migration.md`.

**Why a questionnaire and an interrogation.** The fixed 20 questions were reverse-engineered from every decision that had to be reversed, rewritten, or retrofitted in a previous kit — each one names the decision it would have prevented. A generated conversation misses those categories in exactly the way it always has. The interrogation then catches what a fixed list cannot: that two of your answers contradict each other, and what this codebase already provides. Answering offline is also what gives you time to reconsider *before* the kit is written rather than after.

## Reference materials

- **Canonical example:** [`docs/assets/project_history/asset_control_layer_starter_kit/`](docs/assets/project_history/asset_control_layer_starter_kit/) — a complete, finished kit (archived). Read it to calibrate quality. Note it predates the two-kit split and still contains UI planning documents — ignore those.
- **Blank questionnaire:** [`harness/starter_kit_process/kit_questionnaire_template.md`](harness/starter_kit_process/kit_questionnaire_template.md) — the master copy, with the historical reversal each question prevents.
- **Methodology guides:** [`harness/starter_kit_process/`](harness/starter_kit_process/index.md) — how to write each document type.
- **Front-end planning:** [`/front-end-kit`](.claude/commands/front-end-kit.md) — runs after this kit, owns all route and page planning.

## Announce activation

_"Kit Builder active. I'll interrogate you on the problem first, then propose a phase breakdown for your confirmation, before generating the kit. What are we building?"_

Then immediately ask 4–6 scoping questions.
