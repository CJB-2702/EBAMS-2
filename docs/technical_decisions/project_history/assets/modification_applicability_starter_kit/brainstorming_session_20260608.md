---
type: "Technical Decision"
title: "Brainstorming Session — Modification Applicability"
description: "Give modifications and configuration templates their own rules about *where* they may be."
tags: [technical-decisions, technical-decision, project-history, modification-applicability-starter-kit]
context_tier: 2
---

# Brainstorming Session — Modification Applicability

**Date:** 2026-06-08
**Mode:** Kit Builder — models + control layer only (no UI this pass).

## Goal

Give modifications and configuration templates their own rules about *where* they may be
applied, so the system can refuse nonsensical applications — the running example being
"don't let an engine modification be put on a laptop."

## How the session ran

1. **Grounding.** Read the existing `assets` models and control layer:
   `DefinedModification`, `ConfigurationTemplate`, `ActualModification`,
   `AssetConfiguration`, the junction precedents (`AssetClassCapability`, `ModelDomain`),
   and the existing configuration control layer (`ModificationManager`,
   `ConfigurationManager`, `TemplateModificationManager`,
   `ConfigurationAssignmentValidator`). This located the exact seams where enforcement
   must attach.
2. **Interrogation.** Established the combine rule, the meaning of each toggle
   combination, the enforcement points, and the desire to guard as early as possible.
3. **A reversal worth recording.** The combine rule was first read as **OR**, then
   corrected by the user's own four-row truth table to **AND**. This reshaped the whole
   control-layer design, so it was caught before any document was written.
4. **Decomposition.** Two phases — modifications first (builds the shared engine),
   templates second (reuses it, adds the cross-entity early guard).

## Key facts established

- Every `AssetModel` has exactly **one** mandatory parent `AssetClass`. This single fact
  drives the auto-derive decision (D3) and the dead-model guard (D4): the model list
  always implies its classes.
- `DefinedModification` has **no** existing class/model link — net-new.
- `ConfigurationTemplate` **already** binds to one `model` and the assignment validator
  already enforces exact-model match. The new system generalizes that gate (D7).
- The three live seams are `ModificationManager.add_actual_modification`,
  `ConfigurationManager.assign` (→ `ConfigurationAssignmentValidator`), and
  `TemplateModificationManager.add_modification`.

## Decisions reached

- **AND**, not OR (D1).
- One **`applicability_mode` enum** — `STRICT` / `CLASS_ONLY` / `MODEL_SET` /
  `UNRESTRICTED` — replacing the two booleans (D2).
- Class set **auto-derived** in `MODEL_SET` mode (D3); **dead-model guard** in `STRICT`
  (D4).
- One **shared `ApplicabilityPolicy` + `ApplicabilitySyncHandler`**; concrete tables per
  entity (D5).
- **Four checkpoints**, earliest-first, documented in a standalone guard map (D6).
- `ConfigurationTemplate.model` **kept** as authored-for anchor; assignment gate
  generalized; safe defaults preserve current behavior (D7).
- Table names normalized to singular house convention (D8).
- Scope: **models + control layer only** (D9).
- Template↔modification compatibility blocks **provable** conflicts only (D10).

## Open questions carried into implementation

- **`STRICT` value, in practice.** `STRICT` collapses toward `MODEL_SET` whenever the
  class list ⊇ the models' parents; its only distinct use is *intersection*. Kept for UX
  clarity, but watch whether real configs ever use it — if not, it is a candidate for
  removal later.
- **Compatibility guard depth.** D10 blocks only provable conflicts. The exact set of
  "decidable" cases (matrix §7) is the implementation's discretion; err toward allowing
  on ambiguity, since Checkpoint 3 is the guarantee.
- **Default-seeding a template's own model.** D7 seeds `MODEL_SET` with the template's
  `model`. Confirm this seeding happens in the template factory/manager at create time so
  the default gate matches today's behavior from row one.
- **Suggestion lists in non-binding modes.** The non-enforced list is retained as a
  search hint; the Struct exposes it as `suggested_*`. UX for surfacing suggestions is
  out of scope here but the read model already carries the data.
