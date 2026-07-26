---
okf_version: "0.1"
type: "Index"
title: "Starter Kit Process Knowledge Bundle"
description: "How-to guides for each planning phase of the Kit Builder starter-kit methodology."
tags: [starter-kit-process, index, okf]
context_tier: 1
personas: [backend]
---

# Starter Kit Process

Per-phase how-to guides used by the Kit Builder agent (`/kit-builder`) when decomposing a problem into a starter kit.

The starter kit is **backend-only** — problem, business rules, domain data, control layer. It stops at *"the backend could theoretically perform these tasks."*

- [Starter Kit Questionnaire](kit_questionnaire_template.md) — **the blank master copy.** Copied into every new kit as `questionnaire.md` and answered by the developer *before* any other kit document is written. Each of its 20 questions was reverse-engineered from a decision that had to be reversed or retrofitted in a previous kit.
- [How to Run the Interrogation](interrogation.md) — Stage 2. Reading the answered questionnaire and asking the 4–6 questions it revealed but could not ask.
- [How to Write the Business Concept Definition Document](how_to_business_concept_definition_document.md) — Business Architect phase.
- [How to Plan Data and Relational Models](how_to_data_relational_planning_document.md) — Backend Data Architect phase.
- [How to Plan the Control Layer Architecture](how_to_plan_control_layer.md) — Backend Software Engineer phase.

## Front-end planning lives elsewhere

Routes, page inventories, navigation, and screen layout are **not** part of a starter kit. They are produced later by the Front-End Kit agent (`/front-end-kit`), which consumes a finished starter kit as its input. See [../front_end_kit_process/index.md](../front_end_kit_process/index.md).

The starter kit is **durable** and maintained; the front-end kit is **disposable** and deleted once the UI is built.
