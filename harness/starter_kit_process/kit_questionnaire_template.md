---
okf_version: "0.1"
type: "Process Guide"
title: "Starter Kit Questionnaire (blank template)"
description: "The 20-question pre-kit questionnaire. Copied into every new starter kit as questionnaire.md and filled in by the developer before the kit is built."
tags: [starter-kit-process, process-guide, questionnaire, okf]
context_tier: 2
personas: [backend, business]
---

# Starter Kit Questionnaire

**Status:** `DRAFT` → change to `COMPLETE` when you are done. The Kit Builder will not build the kit until this says `COMPLETE`.

---

## How this works

1. `/kit-builder` creates the kit folder, writes `initial_prompt.md`, copies this template in as `questionnaire.md`, and **pre-fills every answer it can** from what you already said. Then it stops.
2. You open `questionnaire.md` and fill in the rest **as best you can**, correcting anything the agent got wrong. Take as long as you like — that is the point.
3. You set **Status: COMPLETE**, save, and tell the agent to continue.
4. The agent then **interrogates your answers** — 4–6 questions generated from what you wrote: contradictions between answers, hand-waves, consequences you may not have priced in, and what already exists in the codebase. Those answers get folded back into this document.
5. Only then are phases proposed and the rest of the kit built.

The interrogation is not a substitute for this document and this document is not a substitute for the interrogation. The fixed list catches the categories that have gone missing kit after kit; the conversation catches the things a fixed list cannot see.

**Rules for filling it in:**

- **"I don't know" is a valid answer.** Write it. Unanswered and unknown questions become rows in the kit's `open_questions.md` — they are tracked, not lost. A wrong confident answer costs more than an admitted gap.
- **Answer in prose, not schema.** If you find yourself writing column names in the Goals or Personas sections, you are answering the wrong question.
- **Correct the pre-filled answers.** Anything the agent inferred from your initial prompt is a guess until you confirm it. Confirmed answers are binding and become entries in `decisions.md`.
- Answers marked `_(from initial prompt)_` were inferred. Delete that marker once you have reviewed the answer.

**Why these 20 questions:** each one was derived from a decision that had to be reversed, rewritten, or retrofitted in a previous kit (administration → events → assets → parts). The *"Caught late in"* line on each question names the actual decision it would have prevented.

---

## A. Goals

*What this is for. Answer these without naming a single table.*

### G1 — In one sentence, with no nouns from your schema: what does this let someone do that they cannot do today?

*Why:* Goals stated this way are the only part of a kit that survives every later reversal. Everything below them changes.
*Caught late in:* nothing — this is the part that has always worked. Keep it.

**Answer:**
_(unanswered)_

---

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

*Why:* If the answer is "nothing," the scope isn't understood yet. Scope negations belong in the kit README and often in the UI itself.
*Caught late in:* asset relationships **DR7** — "this is not a BOM manager" had to be retrofitted as a disclaimer on two pages after the tool was built.

**Answer:**
_(unanswered)_

---

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

*Why:* Naming the hub record and its narrow public contract early keeps satellites (revisions, mappings, documents) from leaking into every consumer.
*Caught late in:* parts **D3** — "the wider app references a Part solely by its base `Part.id`" turned out to be the most load-bearing rule in that kit.

**Answer:**
_(unanswered)_

---

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

*Why:* Data owned by an outside party should almost never get a schema that mirrors theirs — you inherit their maintenance burden and their churn. Flag it early and it becomes a log, a comment thread, or a denormalized range instead of tables.
*Caught late in:* parts **D13** — `SupplierItemRevision` plus its mapping table were both deleted on day 6 once "a production team cannot mirror a vendor's sovereign revision system" was said out loud.

**Answer:**
_(unanswered)_

---

## B. Personas

*Who uses this. Fill the matrix even where you are unsure — `?` cells are the point.*

### P1 — Name each persona and the one sentence they would use to describe their job here. Which is the highest-volume user?

*Why:* Persona names shape the vocabulary of the whole kit. The volume answer decides which read path has to stay fast.
*Caught late in:* parts got this right at interrogation (technician / engineer / supply / sourcing) and it held through every other reversal.

**Answer:**
_(unanswered)_

---

### P2 — For each persona, what do they do 50 times a day versus once a month?

*Why:* Separates the hot read path from the authoring path, which is where indexing and denormalization decisions come from — for free, before any table exists.
*Caught late in:* parts **D2** — part manufacturers were split from asset manufacturers only after realizing "asset lookups must stay fast."

**Answer:**
_(unanswered)_

---

### P3 — Fill in the capability × role matrix, including the cells you are unsure of.

*Why:* This becomes `functionality_and_roles.md`, the front-end kit's primary input. An undecided cell becomes an undesignable screen. Answer with C / R / U / D / — per cell, `?` where genuinely open.
*Caught late in:* parts — the matrix existed but was reviewed on day 6, and answering it generated **D14** as a side effect.

**Answer:**

| Capability | *(persona)* | *(persona)* | *(persona)* |
| :--- | :---: | :---: | :---: |
| | | | |

---

### P4 — Is any of this data restricted to a subset of users? Is restriction the default or the exception, and roughly what percentage?

*Why:* "Default open or default closed, and how often" gets you a boolean flag plus a join table upfront instead of a retrofit across every read path.
*Caught late in:* parts **D14** — data-domain scoping arrived as a handwritten note at the bottom of a review document on day 6. Assets had it in §1 of the brief and paid nothing.

**Answer:**
_(unanswered)_

---

## C. Business relationships

*How the pieces connect and what happens when they change.*

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

*Why:* Ask it about every FK, including the ones that are "obviously" one-to-many. A join table kept for an anticipated many-to-many costs one hop; adding it later costs a migration and a rewrite of every read.
*Caught late in:* asset **D6** kept the `AssetEvent` join for an anticipated M2M — and relationships **D3** cashed that in six weeks later by adding `role="parent"` / `role="child"` to it. That one is the payoff, not the failure.

**Answer:**
_(unanswered)_

---

### R2 — When a record is created, what else must come into existence automatically? For each: if it fails, does the original creation fail too?

*Why:* The single most-reversed area in this project's history. The second half of the question is the one that matters — it decides orchestrator vs. signal, in-transaction vs. post-commit, and whether provisioning needs an idempotent marker.
*Caught late in:* asset **D1 → D8 → E3 → E7**. An explicit orchestrator was designed, built, and then dismantled once "a broken extension must never block creating an asset" was established. Also events **D-007**, parts **D8** and **OQ3**.

**Answer:**
_(unanswered)_

---

### R3 — When a record is deleted or deactivated, what happens to everything pointing at it? Soft or hard?

*Why:* Deletion semantics are almost never in the original spec and are always wrong when guessed.
*Caught late in:* events **D-003** specified demote-to-thread-level, then **D-013** superseded it with cascade soft-delete. Asset relationships **D5** shipped as a live bug where reparenting did not cascade to the subtree.

**Answer:**
_(unanswered)_

---

### R4 — When several constraints apply at once, must all pass or any pass? Write the truth table.

*Why:* Write the actual table, not the sentence. The sentence reads like OR ("any Light Vehicle **plus** these three truck models"); the table resolves to AND. The table also tends to reveal that your combinations are four named behaviors, i.e. an enum rather than two booleans.
*Caught late in:* modification applicability **D1** — OR was briefly adopted, then reversed by the user's own truth table. **D2** (two booleans → one `ApplicabilityMode` enum) fell out of the same table.

**Answer:**
_(unanswered)_

---

### R5 — At what moment is each rule enforced — authoring time, assignment time, or execution time? What happens when the check cannot be decided?

*Why:* Enforcement is a chain, not a gate: guard as early as possible, keep the later gates as backstops. The undecidable case needs its own answer — blocking everything unprovable obstructs legitimate work.
*Caught late in:* modification applicability **D6** (four checkpoints, earliest wins) and **D10** (block only *provable* conflicts; indeterminate cases fall through to the runtime backstop).

**Answer:**
_(unanswered)_

---

### R6 — Which app owns this? Which apps must remain completely ignorant of it, and what are the permitted seams?

*Why:* Dependency direction decided late means relocating an app. Name the seams explicitly — a signal, a URL string, an FK — and anything not on the list is a violation.
*Caught late in:* asset **D7 / E4 / E7** — the framework moved out of `assets/` into its own app, provisioning left the orchestrator, and provisioning state moved off two asset tables. Also events **D-001**.

**Answer:**
_(unanswered)_

---

## D. Data model

*Only after the sections above are answered.*

### M1 — Glossary: list every domain noun. Mark any word that already means something else in this system, in Django, or in the business.

*Why:* The highest-frequency failure in this project's history — five of six kits shipped a rename. Include the house conventions check in the same pass: singular `db_table`, the `Struct` / `Context` / `Manager` suffix vocabulary, `*_guard.py`.
*Caught late in:* `OwnershipGroup` → `Domain` (admin, whole-codebase rename); `plugin` → `extension` (**D7**, a 16-row rename table in **E8**); `asset_extensions` → `detail_extensions` (**E1**); plural → singular tables (**D8**); "Products" → "Supplier Items".

**Answer:**

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| | | |

---

### M2 — Where two concepts overlap, which is the concrete/primary one and which is the restricted view of it?

*Why:* Getting the direction backwards is a full model redesign, and it propagates — the same inversion shows up again in the context hierarchy and the structs.
*Caught late in:* events **D-009 → D-012**. Multi-table inheritance was designed and rejected because it made `ActivityThread` the parent when *"Event is the primary entity; ActivityThread is a restricted view of it."* Fixed again in **D-011** (context inheritance) and **D-010** (struct aliasing).

**Answer:**
_(unanswered)_

---

### M3 — Is this variation a type label, a set of capability flags, or a distinct class? Can a caller construct an invalid combination?

*Why:* The construction-safety half of the question is what does the work. If a typo produces a silently wrong object, the behavior belongs on the class, not in caller-passed flags.
*Caught late in:* asset **D2 → D3**, reversed inside 24 hours on exactly this argument — *"a typo silently produces a commentable gallery."* Also events **D-002** (flags, not derived from the enum) and modification applicability **D2** (enum makes half-configured states unrepresentable).

**Answer:**
_(unanswered)_

---

### M4 — Is this attribute intrinsic to what the thing *is*, or to *where it is used*?

*Why:* Applies to every column you are tempted to put on a join or enablement table. If it describes the thing, it belongs on the thing's descriptor, and the join row becomes a pure on/off switch.
*Caught late in:* asset **D5** — cardinality moved off the enablement row onto the plugin descriptor so a plugin cannot be single in one place and repeating in another.

**Answer:**
_(unanswered)_

---

### M5 — How do users version and identify this? Can you trust their naming convention? What exactly does "current" mean, and is it the same as "newest"?

*Why:* Two separate landmines. Users name things `A`, `Cobra`, `cobra-redline2` — so names cannot be authoritative, numbers must be. And "current" is frequently *not* the highest sequence or the latest date.
*Caught late in:* parts **D4**, rewritten. The original spec said `ORDER BY sequence DESC` and was simply wrong: a redline against an older major has a later date but must not become current. The real rule is highest `(major, minor)`.

**Answer:**
_(unanswered)_

---

### M6 — Which entities carry free-form human content — comments, documents, photos, notes? Assume the answer is "more than you think."

*Why:* `events.ActivityThread` already exists and carries both comments and attachments, so this is cheap to answer upfront and expensive to skip. The instinct to restrict attachment points is usually wrong.
*Caught late in:* parts **D5**, rewritten from the spec's "documents attach only to revisions, never to parts" to *every* attachable entity owning a thread. Also asset **D2 / D3** for galleries.

**Answer:**
_(unanswered)_

---

## E. Migration defaults *(optional — only if this kit changes existing behavior)*

*Skip this section entirely for net-new work.*

### X1 — What is today's behavior, and does the new default reproduce it exactly? What are you doing with the old code — clean cut or shims?

*Why:* A new capability should be opt-in from an unchanged baseline, so widening a rule is a conscious act rather than a silent regression. And the disposal of old code needs a stated rule, not case-by-case improvisation.
*Caught late in:* modification applicability **D7** — new templates default to `MODEL_SET` with their own model auto-included, exactly reproducing the old hard exact-model gate, with the behavior change flagged explicitly. Extensions **E2** chose a clean cut with no shims, justified by "nothing outside the app imports them and dev does a full DB rebuild."

**Answer:**
_(unanswered / not applicable)_

---

## Sign-off

- [ ] Every question above is answered, or explicitly marked unknown.
- [ ] Pre-filled `_(from initial prompt)_` answers have been reviewed and the markers removed.
- [ ] **Status at the top of this file is set to `COMPLETE`.**

Unknowns carry forward into the kit's `open_questions.md`; confirmed answers carry forward into `decisions.md`.
