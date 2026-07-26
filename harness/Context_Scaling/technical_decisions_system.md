---
type: "Context Scaling Spec"
title: "Technical Decisions System"
description: "Architectural drift happens when an AI suggests a patterns-compliant alternative that conflicts with locked engineering decisions, or when known debt and past incidents are forgotten between sessions."
tags: [context-scaling, context-scaling-spec]
context_tier: 2
---

# Technical Decisions System

Architectural drift happens when an AI suggests a patterns-compliant alternative that conflicts with locked engineering decisions, or when known debt and past incidents are forgotten between sessions. This system prevents that.

---

## Base File: `harness/technical_decisions.md` (Tier 1)

A short summary — 1–2 pages maximum. Synthesizes the current state of the three sub-folders below. Contains no raw event entries; only distilled takeaways and the most critical active constraints.

* **Core Rule:** Once a design pattern, aesthetic direction, or library choice is locked after a trade-off discussion, it is recorded here. The AI must treat locked decisions as hard constraints, not suggestions to revisit.
* **Update cadence:** Summarize new entries from the sub-folders whenever a decision, debt item, or incident is added.

---

## Sub-folder: `technical_decisions/history/`

Event summaries for significant design decisions. One file per decision event.

**Structure per file:**
* **Context/Feature:** What area of the system does this touch?
* **Decision:** What specific approach was selected?
* **Rationale:** Why was this chosen over the alternatives?
* **Date:** When was this decided?

---

## Sub-folder: `technical_decisions/tech_debt/`

Known debt items: shortcuts taken, deferred work, architectural compromises. One file per item.

**Structure per file:**
* What the debt is.
* Why it was deferred.
* What the eventual correct fix looks like.

---

## Sub-folder: `technical_decisions/incident_history/`

Post-mortems and notable bugs. One file per incident.

**Structure per file:**
* What failed.
* Root cause.
* What changed as a result.

When an incident produced a lasting constraint, that constraint must be surfaced in the base `technical_decisions.md` summary so it is always in context.
