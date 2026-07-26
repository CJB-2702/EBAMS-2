---
okf_version: "0.1"
type: "Process Guide"
title: "How to Run the Interrogation"
description: "Stage 2 of the Kit Builder process — reading the answered questionnaire and asking the 4-6 questions it revealed but could not ask."
tags: [starter-kit-process, process-guide, interrogation, okf]
context_tier: 2
personas: [backend, business]
---

# How to Run the Interrogation

**Role & Objective:** You are interrogating a developer who has just handed you an answered questionnaire. Your goal is to find what the questionnaire could not — contradictions between their own answers, decisions still phrased as shapes, consequences they have not priced, and the state of the codebase they are building into.

**When this runs:** Stage 2 of `/kit-builder`, after `questionnaire.md` is marked `COMPLETE` and before any phase is proposed. It never runs first. An interrogation without the questionnaire in hand is the unstructured scoping conversation this process was designed to replace.

---

## The shape of it

- **Read `questionnaire.md` in full first.** Then read whatever code it points at. Then ask.
- **4–6 questions, in a single message.** Do not pepper the developer one at a time.
- **Wait for answers before proceeding.** No phase proposals in the same message.
- Every question is **generated from what you just read.** There is no standing list — that job belongs to the questionnaire.

If you cannot find 4 questions worth asking, the questionnaire was probably answered thinly. Say so and name which sections read as placeholders, rather than padding with questions you already have answers to.

---

## Where the questions come from

In priority order. Spend your 4–6 slots from the top down.

### 1. Contradictions between two answers

The highest-value thing you can find, and the thing the questionnaire structurally cannot catch — it asks each question in isolation.

> *"G3 says the rest of the app only ever knows the base Part id, but R1 describes assets holding an FK straight to a revision row. Which one gives?"*

> *"P4 says restriction is the rare exception, but the P3 matrix has three of four personas blocked from most capabilities. Those describe different systems."*

### 2. Unknowns that block a phase boundary

Not every unknown needs resolving now. An unknown you can design around becomes a row in `open_questions.md`; an unknown that decides *what phase 1 even is* has to be settled here.

Sort the admitted unknowns into those two buckets and only ask about the blocking ones. Say plainly which ones you are deferring, so the developer can object.

### 3. Answers that describe a shape rather than a decision

*"Probably many-to-many."* *"Some kind of status field."* *"We'd want to track that somehow."* *"Standard soft delete."*

Press until it is a decision or an explicit deferral. Offer named options rather than asking them to invent one:

> *"'Some kind of status' — is that a lifecycle the control layer gates transitions on (`StateMachine`), or a display label? If it gates, name the states and who may move between them."*

### 4. The consequence they have not priced

The questionnaire asks what the developer wants. The interrogation asks what it costs. State the cost, then ask them to accept or reject it — do not ask them to guess at it.

> *"You want the compatibility range unconstrained — that means nothing stops `min > max` until someone hits it in the UI. Accept that for v1, or add the control-layer check now?"*

> *"Comments-only enforcement means the first RBAC pass has to find every seam by grep. Worth a `# RBAC:` marker convention so they're greppable?"*

### 5. Codebase reality the questionnaire cannot know

The developer answers the questionnaire from intent; you answer these from the repo. **Look before you ask** — never spend a slot on something `grep` would have told you.

Ask only where the code is genuinely ambiguous or the choice is theirs:

- *"The old app had `EventContext` for lifecycle events — does the new app already have event infrastructure, or does this phase need to build it?"*
- *"Is the control layer missing entirely, partially built, or does it exist in a different architectural style?"*
- *"Is there existing code to migrate, or is this net-new?"*
- *"Which parts already have models built, and which parts need new tables?"*
- *"Should creation of X fan out through an explicit orchestrator, or via a signal the other app subscribes to?"*

---

## What makes a question good

**Specific, and it forces a decision.** *"Tell me about permissions"* is not a question. *"Does releasing a revision lock it against further edits, or only against structural change?"* is — and it is the one that got answered *"do not lock"* in one word.

**Offers named options with their consequences.** The developer is deciding, not brainstorming. Two or three named alternatives with what each costs will get you a real answer; an open prompt will get you a shape.

**Answerable in a sentence.** If it needs an essay, it is a document, not an interrogation question — say so and open an `open_questions.md` row for it.

**Not already answered.** Re-asking something the questionnaire settled tells the developer their document was not read, and it burns the scarcest thing in this stage: their patience.

---

## What to do with the answers

1. **Write them back into `questionnaire.md`**, under the question they refine. That document stays the single record of what was established. If an answer materially reshapes an earlier one, correct it in place and note the correction — a questionnaire still saying what the developer believed before the interrogation is stale.
2. **Fold confirmed answers into `decisions.md`** as numbered decisions, each with the options considered and why one won. An answer recorded without its rejected alternatives cannot be re-evaluated later.
3. **Fold every remaining unknown into `open_questions.md`** — one row each. Each row is later resolved to a decision, deferred to tech debt, or explicitly dropped. Never silently.

---

## Calibration — what a good interrogation produced

The Part Definitions kit's interrogation (2026-06-23) captured eight clarifying decisions. Five of them held unchanged through every subsequent reversal:

| Captured at interrogation | Became | Held? |
| :--- | :--- | :--- |
| New sub-app `app/parts/`, not an extension of assets | D1 | ✅ |
| Part manufacturers split from asset manufacturers — *"asset lookups must stay fast"* | D2 | ✅ |
| The app only ever knows the base Part id | D3 | ✅ **the kit's most load-bearing rule** |
| Aliases auto-populate on supplier item create | D8 | ✅ |
| Four personas; authenticated-only for now | D11 | ✅ |
| Documents reuse the events file system | D5 | ⚠️ rewritten — *attach points* were wrong, not the reuse |
| Aliases are revision-agnostic | D9 | ⚠️ rewritten — FK shape was wrong, the principle held |

Note the pattern in the two that moved: the interrogation got the **principle** right and the **structure** wrong. That is the expected division of labour — the questionnaire's data-model section (M1–M6) is what now catches the structure, so the interrogation can spend its slots on principle, contradiction, and consequence.

What that interrogation *missed* entirely, and cost the most: data-domain scoping, which surfaced as a handwritten note six days later and became D14; and the supplier-revision assumption, which was never marked as an assumption and cost two planned tables when it was finally questioned (D13). Both are now fixed questions — **P4** and **G4**.
