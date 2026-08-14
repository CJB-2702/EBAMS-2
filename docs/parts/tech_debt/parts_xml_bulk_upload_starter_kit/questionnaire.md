---
okf_version: "0.1"
type: "Process Guide"
title: "Starter Kit Questionnaire — Parts XML Bulk Upload"
description: "Pre-filled from initial_prompt.md. Fill in the rest, set Status: COMPLETE, then hand back."
tags: [starter-kit-process, process-guide, questionnaire, okf]
context_tier: 2
personas: [backend, business]
---

# Starter Kit Questionnaire — Parts XML Bulk Upload

**Status:** `DRAFT`

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
Lets someone import a whole batch of parts — each with its full manufacturer/supplier-item set, alias set (including alternate-part cross-references), and domain assignments — from one uploaded file, in one action, instead of creating each part through the wizard and then hand-adding its supplier items, aliases, and domains one at a time afterward.

---

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

*Why:* If the answer is "nothing," the scope isn't understood yet. Scope negations belong in the kit README and often in the UI itself.
*Caught late in:* asset relationships **DR7** — "this is not a BOM manager" had to be retrofitted as a disclaimer on two pages after the tool was built.

**Answer:**
It is not a replacement for the existing CSV/paste-grid bulk upload at `/parts/bulk-upload/` — that path stays for the flat, single-part-per-row, no-aliases-no-domains case; this is a second, richer path when a part's full shape (supplier items, extra aliases, domain assignments, alternate-part cross-references) needs to be expressed in one upload.

**It is not a BOM manager.** Per the developer's clarification (2026-08-08), "relationships" turned out to mean the part's own satellite data — supplier items, aliases, domains — not a new part-to-part composition/quantity concept. Where a part-to-part link is needed at all, it reuses the **existing** `Alias` model's `PART_TO_PART` association type (`AliasFactory.for_alternate_part`) already in the codebase — see R1. No new relationship table is being introduced by this kit.

_(still open)_ General PLM/ERP data-exchange integration vs. a one-time migration tool vs. a permanent feature — not yet answered (see G4).

---

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

*Why:* Naming the hub record and its narrow public contract early keeps satellites (revisions, mappings, documents) from leaking into every consumer.
*Caught late in:* parts **D3** — "the wider app references a Part solely by its base `Part.id`" turned out to be the most load-bearing rule in that kit.

**Answer:**
_(from initial prompt / existing codebase convention)_ `Part`, same as everywhere else in this app — parts **D3** ("the wider app references a Part solely by its base `Part.id`") already governs this and this kit inherits it rather than reopening it. Whatever "relationship" ends up meaning (R1), it is a relationship *between* `Part.id` values (or between a `Part` and some other existing hub record), not a new parallel hub.

---

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

*Why:* Data owned by an outside party should almost never get a schema that mirrors theirs — you inherit their maintenance burden and their churn. Flag it early and it becomes a log, a comment thread, or a denormalized range instead of tables.
*Caught late in:* parts **D13** — `SupplierItemRevision` plus its mapping table were both deleted on day 6 once "a production team cannot mirror a vendor's sovereign revision system" was said out loud.

**Answer:**
_(unanswered)_ Is the uploaded XML a one-time import of data that becomes ours to own and edit afterward (like the CSV path), or is it a recurring export from an external system (PLM/ERP/CAD BOM export) that this feature re-imports periodically — in which case the XML's shape is dictated by that external system, not by us, and re-imports need an update/reconcile story rather than just create?

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
_(unanswered — plausibly "once a month at most," this reads as a bulk/occasional import tool rather than a daily one, but confirm)_

---

### P3 — Fill in the capability × role matrix, including the cells you are unsure of.

*Why:* This becomes `functionality_and_roles.md`, the front-end kit's primary input. An undecided cell becomes an undesignable screen. Answer with C / R / U / D / — per cell, `?` where genuinely open.
*Caught late in:* parts — the matrix existed but was reviewed on day 6, and answering it generated **D14** as a side effect.

**Answer:**

| Capability | *(persona)* | *(persona)* | *(persona)* |
| :--- | :---: | :---: | :---: |
| | | | |

_(unanswered — depends on P1)_

---

### P4 — Is any of this data restricted to a subset of users? Is restriction the default or the exception, and roughly what percentage?

*Why:* "Default open or default closed, and how often" gets you a boolean flag plus a join table upfront instead of a retrofit across every read path.
*Caught late in:* parts **D14** — data-domain scoping arrived as a handwritten note at the bottom of a review document on day 6. Assets had it in §1 of the brief and paid nothing.

**Answer:**
_(unanswered — the created `Part` rows go through ordinary domain scoping like any other part; whether the *upload action itself* needs a permission gate beyond ordinary part-creation permission is open)_

---

## C. Business relationships

*How the pieces connect and what happens when they change.*

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

*Why:* Ask it about every FK, including the ones that are "obviously" one-to-many. A join table kept for an anticipated many-to-many costs one hop; adding it later costs a migration and a rewrite of every read.
*Caught late in:* asset **D6** kept the `AssetEvent` join for an anticipated M2M — and relationships **D3** cashed that in six weeks later by adding `role="parent"` / `role="child"` to it. That one is the payoff, not the failure.

**Answer:**
**Resolved by developer clarification (2026-08-08).** The XML's per-`part` shape is:

```
part
├─ supplier_items[]        (each with a nested part_manufacturer — auto-created if not found by name)
├─ aliases[]                additional aliases beyond the auto-generated ones
└─ domains[]                domain assignment, same shape as the create-wizard's domain_ids
```

None of these are many-to-many joins between two `Part` rows in the BOM sense — they are the same one-to-many satellites the `/parts/new/` wizard already creates (`SupplierItem.internal_part`, `Alias.part`, the part↔`Domain` scoping join). The one genuine part-to-part link is an **alias of `association_type=PART_TO_PART`** (`Alias.alternate_part` FK, written via `AliasFactory.for_alternate_part`) — this already exists in the codebase (`app/parts/control_layer/factories/alias_factory.py`) and is not new. If the uploaded `aliases[]` list includes an alternate-part entry, ingestion resolves the target part and calls this existing factory method; nothing else changes shape based on it.

`part_manufacturer` is looked up by name and **auto-created if missing** — same behavior as the CSV bulk-upload's `PartBulkUploadFactory._resolve_manufacturer` (case-insensitive name match, create via `PartManufacturerManager` on miss). Confirmed to carry over unchanged.

_(still open, see M5)_ When an alias entry references another part (alternate-part alias, or any alias naturally resolving to an existing part), how is that other part identified — by `part_number`? And must it already exist in the database, or can it be a forward reference to another `<part>` defined later in the same upload document?

---

### R2 — When a record is created, what else must come into existence automatically? For each: if it fails, does the original creation fail too?

*Why:* The single most-reversed area in this project's history. The second half of the question is the one that matters — it decides orchestrator vs. signal, in-transaction vs. post-commit, and whether provisioning needs an idempotent marker.
*Caught late in:* asset **D1 → D8 → E3 → E7**. An explicit orchestrator was designed, built, and then dismantled once "a broken extension must never block creating an asset" was established. Also events **D-007**, parts **D8** and **OQ3**.

**Answer:**
Whatever a `Part` node in the XML produces, it inherits the rule established earlier this session: **a part cannot be created without at least one manufacturer + supplier item**, enforced in `PartCreationWizardFactory` and the CSV `PartBulkUploadFactory`. This kit's ingestion class raises the same validation rather than relaxing it.

Per developer instruction (2026-08-08): **each created `SupplierItem` must produce its MPN alias**, exactly like manual creation does. This does not need new code — `SupplierItemManager.create` *already* does this automatically (it calls `AliasFactory.for_vendor_item` internally; see `app/parts/control_layer/managers/supplier_item_manager.py`). The instruction to the kit is therefore: **the ingestion class must create supplier items through `SupplierItemManager.create` (or an equivalent call that preserves this side effect), not by writing `SupplierItem.objects.create` directly** — direct creation would silently skip the alias. The control-layer plan should call this out explicitly as a "do not bypass" note.

Manufacturer auto-create, per developer instruction: reuse the same resolve-or-create-by-name behavior as the CSV path (`PartBulkUploadFactory._resolve_manufacturer`).

_(still open)_ For a whole-document upload describing many parts, if one part fails validation (e.g. its supplier-item/manufacturer rule, or a bad alias), does the **entire document** roll back, or does ingestion proceed part-by-part the way the CSV path does (each `<part>` its own transaction, partial success reported per part)? This interacts directly with the M5 forward-reference question — if part B's alias references part A and part A failed, B's alias cannot succeed either.

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
_(unanswered — likely N/A until R1 defines what a "relationship" is; revisit once it does)_

---

### R5 — At what moment is each rule enforced — authoring time, assignment time, or execution time? What happens when the check cannot be decided?

*Why:* Enforcement is a chain, not a gate: guard as early as possible, keep the later gates as backstops. The undecidable case needs its own answer — blocking everything unprovable obstructs legitimate work.
*Caught late in:* modification applicability **D6** (four checkpoints, earliest wins) and **D10** (block only *provable* conflicts; indeterminate cases fall through to the runtime backstop).

**Answer:**
_(unanswered)_ Candidate checkpoints for an XML upload specifically: schema/shape validation (is this even valid XML matching the documented structure) → per-node business validation (does this part/relationship satisfy the same rules as manual creation) → whole-document consistency (do all relationship references resolve to a part that exists somewhere in this document or already in the database). Which of these block the upload outright vs. produce a per-row/per-node error report is open.

---

### R6 — Which app owns this? Which apps must remain completely ignorant of it, and what are the permitted seams?

*Why:* Dependency direction decided late means relocating an app. Name the seams explicitly — a signal, a URL string, an FK — and anything not on the list is a violation.
*Caught late in:* asset **D7 / E4 / E7** — the framework moved out of `assets/` into its own app, provisioning left the orchestrator, and provisioning state moved off two asset tables. Also events **D-001**.

**Answer:**
_(from initial prompt)_ Owned by `parts` — this is a second ingestion path into the same app that already owns `Part`, `PartManufacturer`, and `SupplierItem`, requested as a sibling to the existing `/parts/bulk-upload/` CSV path. No other app should need to know an XML ingestion path exists; it produces ordinary `Part`/`PartManufacturer`/`SupplierItem` rows (and whatever relationship record R1 defines) through the same control-layer surface other `parts` entrypoints already use.

---

## D. Data model

*Only after the sections above are answered.*

### M1 — Glossary: list every domain noun. Mark any word that already means something else in this system, in Django, or in the business.

*Why:* The highest-frequency failure in this project's history — five of six kits shipped a rename. Include the house conventions check in the same pass: singular `db_table`, the `Struct` / `Context` / `Manager` suffix vocabulary, `*_guard.py`.
*Caught late in:* `OwnershipGroup` → `Domain` (admin, whole-codebase rename); `plugin` → `extension` (**D7**, a 16-row rename table in **E8**); `asset_extensions` → `detail_extensions` (**E1**); plural → singular tables (**D8**); "Products" → "Supplier Items".

**Answer:**

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| Part | The existing hub record (identity + base revision) | — established, do not rename |
| PartManufacturer | Existing external-manufacturer registry | — established |
| SupplierItem | Existing manufacturer-part/vendor-item record | — established |
| Bulk Upload | Already the name of the existing CSV/paste-grid path at `/parts/bulk-upload/` | naming the XML path also "Bulk Upload" needs a qualifier (e.g. "XML Bulk Upload") so the two are never ambiguous in code, URLs, or conversation |
| Alias | Existing model (`app/parts/models/search/alias.py`) — a searchable identifier row anchored to a `Part`, with three association shapes: `PART_TO_STRING`, `PART_TO_VENDOR_ITEM`, `PART_TO_PART` | **resolved, not new** — "relationships" in this kit's XML resolves to Alias rows, specifically `PART_TO_PART` (`alternate_part` FK) for genuine part-to-part links. No new relationship table. |
| Domain | Existing model — a part can be scoped to one or more domains, same mechanism the create-wizard's "2. Domains" card already uses (`PartDomainManager.add_domain`) | established, reused as-is |
| Ingestion (class) | The requested control-layer component that parses + validates + creates from the XML document | not an existing suffix in this app's vocabulary (`Struct`/`Context`/`Factory`/`Manager`/... per `oop_control_patterns.md`) — needs to be mapped onto the existing suffix vocabulary. Given it *orchestrates* several existing factories/managers (`PartFactory`, `PartManufacturerManager`, `SupplierItemManager`, `AliasFactory`, `PartDomainManager`) per part rather than owning a table of its own, `Orchestrator` (already an established suffix, see `PartDomainTemplateHandler`'s neighbors) reads like the right fit — confirm in interrogation rather than deciding here. |

---

### M2 — Where two concepts overlap, which is the concrete/primary one and which is the restricted view of it?

*Why:* Getting the direction backwards is a full model redesign, and it propagates — the same inversion shows up again in the context hierarchy and the structs.
*Caught late in:* events **D-009 → D-012**. Multi-table inheritance was designed and rejected because it made `ActivityThread` the parent when *"Event is the primary entity; ActivityThread is a restricted view of it."* Fixed again in **D-011** (context inheritance) and **D-010** (struct aliasing).

**Answer:**
Largely moot now that R1 resolved to "reuse existing models as-is" — this kit does not introduce a new concept that overlaps with an existing one. The one shape worth naming explicitly: an `<alias>` entry in the XML is a *restricted view* of the existing `Alias` model, not a new concept — the XML element only needs to supply enough to pick one of the three existing `association_type` shapes (see M3).

---

### M3 — Is this variation a type label, a set of capability flags, or a distinct class? Can a caller construct an invalid combination?

*Why:* The construction-safety half of the question is what does the work. If a typo produces a silently wrong object, the behavior belongs on the class, not in caller-passed flags.
*Caught late in:* asset **D2 → D3**, reversed inside 24 hours on exactly this argument — *"a typo silently produces a commentable gallery."* Also events **D-002** (flags, not derived from the enum) and modification applicability **D2** (enum makes half-configured states unrepresentable).

**Answer:**
`Alias.association_type` is already an existing type-label enum (`PART_TO_STRING` / `PART_TO_VENDOR_ITEM` / `PART_TO_PART`) with a DB check constraint enforcing the correct secondary FK per value (see the model's `Meta.constraints`) — the model already makes an invalid combination unconstructable at the database level. The open sub-question is only at the **XML parsing boundary**: does the `<alias>` element carry an explicit `type="alternate_part"` attribute, or does the ingestion class *infer* the association type from which optional child/attribute is present (e.g. a `target_part_number` present ⇒ `PART_TO_PART`)? Either is safe given the DB constraint as backstop, but the explicit-attribute form fails faster (schema validation at parse time) rather than a valid-XML-but-wrong-shape document failing on save. Recommend explicit — confirm in interrogation.

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
_(unanswered — this is now the single largest remaining open question)_ There is no ambiguous "current revision" question here (each `<part>` still gets its ordinary auto-created base revision, same as every other creation path — no override requested). What *is* open: inside one XML document, how does an alternate-part alias (or any alias that targets another part) identify that other part — the real `part_number` is the only trustworthy candidate (names are not authoritative anywhere else in this app, per the house rule this question exists to catch). Given `part_number`: must the target already exist in the database at upload time, or can it be a forward reference to another `<part>` defined later in the *same* document? The second option requires either a two-pass ingestion (create all parts first, then all aliases/relationships) or deferred/queued alias creation — a real control-layer decision, not a detail.

---

### M6 — Which entities carry free-form human content — comments, documents, photos, notes? Assume the answer is "more than you think."

*Why:* `events.ActivityThread` already exists and carries both comments and attachments, so this is cheap to answer upfront and expensive to skip. The instinct to restrict attachment points is usually wrong.
*Caught late in:* parts **D5**, rewritten from the spec's "documents attach only to revisions, never to parts" to *every* attachable entity owning a thread. Also asset **D2 / D3** for galleries.

**Answer:**
_(unanswered — presumably none beyond what a `Part`/`SupplierItem` already carries (description, comments thread), but confirm nothing new is being asked for here, e.g. notes on the relationship itself)_

---

## E. Migration defaults *(optional — only if this kit changes existing behavior)*

*Skip this section entirely for net-new work.*

### X1 — What is today's behavior, and does the new default reproduce it exactly? What are you doing with the old code — clean cut or shims?

*Why:* A new capability should be opt-in from an unchanged baseline, so widening a rule is a conscious act rather than a silent regression. And the disposal of old code needs a stated rule, not case-by-case improvisation.
*Caught late in:* modification applicability **D7** — new templates default to `MODEL_SET` with their own model auto-included, exactly reproducing the old hard exact-model gate, with the behavior change flagged explicitly. Extensions **E2** chose a clean cut with no shims, justified by "nothing outside the app imports them and dev does a full DB rebuild."

**Answer:**
_(not applicable — this is net-new, additive to the existing CSV bulk-upload path, not a replacement for it, per G2)_

---

## Sign-off

- [ ] Every question above is answered, or explicitly marked unknown.
- [ ] Pre-filled `_(from initial prompt)_` answers have been reviewed and the markers removed.
- [ ] **Status at the top of this file is set to `COMPLETE`.**

Unknowns carry forward into the kit's `open_questions.md`; confirmed answers carry forward into `decisions.md`.
