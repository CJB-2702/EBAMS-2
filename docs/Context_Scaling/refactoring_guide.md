# Context Refactoring Guide

**Refactoring order:** Always build or update the lowest tier content first — specific, concrete, detailed. Then rebuild and re-summarize the higher tier files that reference it. Never update a summary before the detail it summarizes exists.

---

## 1. Drift Smells — When to Refactor

Documentation degrades over time if it is not refactored with the same discipline applied to source code. Trigger a refactor when any of the following appear:

* **Bloat Smell:** A Tier 1 document surpasses two pages, or a Tier 2 document grows dense with implementation snippets.
* **Repetition Smell:** The same structural rule appears across multiple Tier 2 files. Fix: extract upward into the parent Tier 1 file and replace local instances with a reference pointer.
* **Code Leak Smell:** Code snippets in Tier 1 exceed 0 lines (Tier 1 must avoid code). Tier 2 snippets exceed 40 lines. Fix: push the code down to a Tier 3 Examples file.
* **Outdated Spec Smell:** A session results in a fundamental shift in data models, architectural boundaries, or UX flow, rendering existing specs inaccurate.

---

## 2. Refactoring Patterns

### De-escalation
Move concrete implementation details down the tier ladder. If a Tier 2 spec accumulates boilerplate or component structures, extract the code blocks into a dedicated Tier 3 Examples file and replace them with a reference pointer.

### Consolidation
When multiple Tier 2 files repeat the same structural rule, centralize it upward into the parent Tier 1 document. Replace all local copies with a single reference.

### Architectural Pruning
Delete historical implementation steps from specs. Documentation reflects the *current truth* and *immediate future* of the system. Preserve the *reasoning* for past decisions in `technical_decisions/history/` — but clear dead configuration instructions or superseded rules from the active spec tiers.

---

## 3. Post-Session Context Synthesis

Use this prompt at the end of a productive session to extract decisions into the tiered documentation system.

```text
You are an expert technical archivist. We have just completed a development session where explicit
technical decisions, architectural patterns, or feature specifications were established.

Analyze the conversation history and extract core decisions to update the tiered Context Management System.

### Execution Instructions

1. Identify fundamental architectural, technical, or design decisions made during the session.
2. Determine the correct target file using these rules:
   - Global identity, routing, or always-apply constraints   -> Tier 0 (Claude.md)
   - High-level concept rules or reference updates           -> Tier 1 (docs/*.md)
   - Deep functional requirements for a specific domain      -> Tier 2 (docs/[Concept]/*.md)
   - Code patterns, library choices, component shapes        -> Tier 3 (docs/[Concept]/Examples/)
   - Locked trade-off decisions and their rationale          -> technical_decisions/history/
   - Known shortcuts or deferred work                        -> technical_decisions/tech_debt/
3. Format output as clean Markdown snippets showing exactly what text to append, modify, or create.
4. Adhere to tier size limits: no code in Tier 1, max 40-line code blocks in Tier 2.
5. After writing low-tier updates, summarize upward — update the parent Tier 1 file last.

### Output Structure

For each update:
- **Target File:** [path/file.md]
- **Action:** [Create / Append / Replace]
- **Content:**
  [Precise documentation text]
```
