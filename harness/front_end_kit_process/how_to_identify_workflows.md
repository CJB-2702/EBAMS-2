---
type: "Process Guide"
title: "How to Identify Workflows"
description: "You are acting as a Product/UX Agent. Judge every create and edit page as simple form or multi-card wizard, with a written reason. This is a hard gate."
tags: [front-end-kit-process, process-guide, gate]
context_tier: 2
---

# How to Identify Workflows

**Role & Objective:**
You are acting as a Product/UX Agent. Produce `workflows.md` — an explicit, written verdict on **every** create and edit page in the route skeleton.

**This is a hard gate.** No create or edit page may be left unjudged. Silence is not "it's a simple form" — silence is an incomplete kit.

---

## Why this exists

The default failure mode of CRUD planning is treating "create a part" as a form because the *table* is one table. But a user creating a part is also assigning manufacturers, recording a revision, and attaching a note. Ship the naive form and the user creates a part, then hunts for three more screens to finish the job they thought they were doing.

Forcing a written verdict on every create page turns this from something you have to remember to notice into something the process catches.

---

## The trigger rule

> A create or edit page is a **multi-card wizard** when the entity has **more than one reverse foreign key** that a user would plausibly populate in the same sitting.

Read the reverse FKs off `model_diagram.md`. One reverse FK is a form with a section. Two or more is a wizard.

The qualifier *plausibly populated in the same sitting* is doing real work — apply it honestly:

| Reverse FK | Counts? | Why |
| :--- | :--- | :--- |
| `PartManufacturer → Part` | **Yes** | You know the manufacturers when you create the part. |
| `PartRevision → Part` | **Yes** | The initial revision is part of creating the part. |
| `Note → Part` | **Yes** | Users write the "why we stock this" note at creation. |
| `DemandLine → Part` | **No** | Demand accrues later, from a different workflow, by a different role. |
| `AuditLog → Part` | **No** | System-written. Never user-populated. |

Discount reverse FKs that are: system-written (audit, event log), populated by a different role in a different process, or accumulated over the record's life rather than set at creation.

### Secondary signals

These push a borderline page (exactly one qualifying reverse FK, or a large flat form) toward wizard:

- A **file upload** is involved.
- A **status or state** must be chosen at creation.
- A related record may need to be **created inline** ("this manufacturer isn't in the list yet").
- The form exceeds roughly **15 fields**, or spans clearly distinct conceptual groups.

### Edit pages

Apply the same rule. If creating an entity is a wizard, editing it is usually the same page with the cards pre-populated — not a stripped-down form. Say explicitly whether edit reuses the create layout or diverges, and why.

---

## What a wizard looks like here

The form is already settled by [../UX_UI/components/multi_step_flows.md](../UX_UI/components/multi_step_flows.md) — **apply it, do not redesign it**:

- **One route.** `…/create`, vertical scroll, every card on the same document. Not `/create/step-1`.
- **Progressive enablement.** Later cards visible but disabled until earlier ones validate — server-side, not JavaScript-only.
- **Session-backed draft** under a namespaced `request.session` key. Nothing commits until final submit.
- **Assignment relations get in-page cards** — left-heavy assignment card pair or dual listbox. **Never a modal.** See [../UX_UI/components/modals.md](../UX_UI/components/modals.md).
- **Card order follows dependency:** identity fields → relations that depend on them → attachments and notes.

Only two exceptions justify splitting across URLs: the user is expected to bookmark a deep step, or per-step server work is genuinely heavy. Document the exception if you claim one.

---

## Instructions

1. **List every create and edit route** from `route_skeleton.md`. Every one gets a row. None may be skipped.
2. **Record the reverse FKs** for each entity, marked qualifying or discounted, with the discount reason.
3. **State the verdict** — `Simple form` or `Multi-card wizard` — and the reason in one sentence.
4. **For each wizard, sketch the card list** in scroll order: card name, what it does, which component, whether it is an assignment card.
5. **Promote the critical ones.** Wizards that are central to the application's purpose, or that the developer wants to evaluate closely, get their own file in `key-workflows/` — see [how_to_write_a_key_workflow.md](how_to_write_a_key_workflow.md). This document keeps the summary row and links to it.
6. **Update `route_skeleton.md`** — any page judged a wizard must have its type changed from `Simple CRUD` to `Workflow`.

---

## Verdict table format

```markdown
| Route | Entity | Qualifying reverse FKs | Discounted | Verdict | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/parts/create` | `Part` | `PartManufacturer`, `PartRevision`, `Note` | `DemandLine` (accrues later), `AuditLog` (system) | **Multi-card wizard** → [key-workflows/part_creation.md](key-workflows/part_creation.md) | Three relations populated at creation. |
| `/categories/create` | `PartCategory` | — | `Part` (categories are created before parts exist) | **Simple form** | Two fields, no relations set at creation. |
```

---

## Gate report

```markdown
## Gate: workflow review

**Status:** PASS — 11 of 11 create/edit routes judged.

- Multi-card wizards: 4 (3 promoted to `key-workflows/`)
- Simple forms: 7
- Unjudged: 0
```

`Unjudged: 0` is the gate. Any other number is a FAIL.

---

## Required Output Format

A single markdown document, `workflows.md`, containing:

1. **Verdict table** — every create and edit route, no exceptions.
2. **Card sketch per wizard** — scroll-order list; brief for wizards promoted to `key-workflows/`, complete for those not promoted.
3. **Gate verdict** — counts, with `Unjudged: 0` required to pass.
