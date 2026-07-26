---
type: "Process Guide"
title: "How to Write a Key Workflow Document"
description: "You are acting as a Product/UX Agent. Give each critical multi-step workflow its own file so the developer can evaluate it in isolation."
tags: [front-end-kit-process, process-guide]
context_tier: 2
---

# How to Write a Key Workflow Document

**Role & Objective:**
You are acting as a Product/UX Agent. Write one file per critical workflow into `key-workflows/`, so the developer can read and evaluate a single workflow cleanly without the noise of the whole page inventory.

One file per workflow. Name it after the workflow, not the route: `key-workflows/part_creation.md`, `key-workflows/maintenance_activity_scheduling.md`.

---

## Which workflows get their own file

Promote a workflow from `workflows.md` when **any** of these hold:

- It is **central to why the application exists** — the thing users spend their day doing.
- It has **three or more cards**.
- It **crosses sub-applications** or touches tables owned by more than one domain.
- It has **branching** — the card sequence differs by role, type, or a choice made earlier in the flow.
- The developer **asks for it** to be pulled out for review.

Everything else stays as a card sketch inside `workflows.md`. Do not promote every wizard — the value of `key-workflows/` is that its contents are worth reading closely, and that value drops as the folder fills with routine forms.

---

## Instructions

1. **Open with the user's goal in one paragraph**, in domain language. What is the person trying to accomplish, and what does finishing it mean for the business? No class names, no table names — this paragraph is the sanity check that the workflow is worth building at all.

2. **State the preconditions.** What must exist before the user can start? Which role may start it? What state must the parent record be in?

3. **Lay out the cards in scroll order.** One subsection per card. For each:
   - **What it captures** and why it sits at this position in the sequence.
   - **Component** — cite the guide, don't describe markup.
   - **Enablement condition** — what must validate in earlier cards before this one activates. Remember gates are server-side.
   - **Empty state** — the literal string shown when its data is empty. Cards always render.
   - **Draft keys** — what this card writes into the namespaced session dict.

4. **Specify the commit.** What happens on final submit — which control-layer class runs, what is created in what order, and confirm it is **one transaction**. Then: what gets deleted from session, and where the user lands.

5. **Specify abandonment.** The developer needs to have decided this, not discover it: does the draft survive a browser close? Is there a visible discard action? Does an abandoned draft ever expire? Say it explicitly even if the answer is "the session draft persists until logout."

6. **Specify validation and failure.** Which validations are per-card and which only run at final submit. What the user sees when the commit fails after they've filled everything in — this is where wizards feel worst if unplanned.

7. **Handle branching explicitly.** If the card sequence varies, show each variant as its own ordered list. Do not describe branching in prose — it is unreadable and unreviewable.

8. **List the control-layer targets.** A short table mapping each card's write to its Context/Manager/Factory method. Mark anything that does not yet exist with `??` — that is the developer's build list.

---

## Document skeleton

```markdown
# <Workflow name>

**Route:** `/parts/create`
**Roles:** Planner, Engineer
**Cards:** 4
**Status:** draft | reviewed | built

## Goal
One paragraph in domain language.

## Preconditions
- ...

## Cards

### 1. Part identity
**Captures:** name, number, category, unit of measure.
**Component:** standard form card.
**Enabled when:** always — this is the first card.
**Empty state:** —
**Draft keys:** `part_draft.identity`

### 2. Manufacturers
**Captures:** which manufacturers supply this part, with their part numbers.
**Component:** left-heavy assignment card pair.
**Enabled when:** identity card validates (name and number present).
**Empty state:** "No manufacturers assigned yet."
**Draft keys:** `part_draft.manufacturer_ids`

...

## Commit
`PartCreationOrchestrator.create()` in one transaction: `Part` → `PartManufacturer` rows →
`PartRevision` → `Note`. On success `del request.session['part_draft']`, redirect to
`/parts/<id>`.

## Abandonment
Draft persists in session until logout. "Discard draft" button in the page hero clears the
namespaced key and returns to `/parts`.

## Validation and failure
Per-card: identity uniqueness, manufacturer part-number format.
At submit: cross-check that at least one manufacturer is assigned.
On commit failure: re-render the same route with the draft intact and an error banner —
never lose the draft.

## Control layer targets
| Card | Write | Target |
| :--- | :--- | :--- |
| Identity | `Part` | `PartFactory.create()` |
| Manufacturers | `PartManufacturer` | `PartManufacturerManager.set()` — `??` does not exist yet |

## Open questions
- ...
```

---

## Required Output Format

One markdown file per promoted workflow in `key-workflows/`, following the skeleton above.

Add a `key-workflows/index.md` listing every workflow file with its route, card count, and status, so the folder is scannable.
