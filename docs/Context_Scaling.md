---
type: "Concept Anchor"
title: "Technical Specification: Context Scaling Framework"
description: "As development environments grow, unmanaged context injection degrades LLM performance, introduces hallucinations, and wastes token allocations."
tags: [overview, concept-anchor]
context_tier: 1
---

# Technical Specification: Context Scaling Framework

## 1. Core Philosophy

As development environments grow, unmanaged context injection degrades LLM performance, introduces hallucinations, and wastes token allocations. **Context Scaling** solves this by establishing a strictly tiered, hierarchical information architecture governed by **Work Personas**. High-level rules route to deeper specifications, ensuring an AI agent only ingests the exact depth of context required for a given task.

---

## 2. Hierarchical Context Tiers

| Tier | File / Location | Scope & Target Length | Injection Mechanic & Rules |
| :--- | :--- | :--- | :--- |
| **Tier 0** | `Claude.md` (Root) | Main router & core identity. Max 3 pages. | **Global:** Always included. Code permitted only when truly essential (e.g., critical run commands). |
| **Tier 1** | `docs/*` (Root docs) | Concept anchors & file references. 1–2 pages. | **Global:** Always included. **Must avoid code** — pure concept and routing documents. |
| **Tier 2** | `docs/[Concept]/*.md` | Full feature specs & requirements. Few pages. | **On-Demand:** Loaded via Persona Slash Commands or dynamic domain triggers. Code ≤ 40 lines. |
| **Tier 3** | `docs/[Concept]/Examples/*` | Implementation guides, patterns, usage. | **Targeted:** Never scanned by default. Injected manually when writing active code. |
| **Tier 4** | Automated Overviews | Structural maps, class maps, module boundaries. | **Automated:** Programmatically generated. Must run before reading source files. Low context cost. |
| **Tier 5** | Base Codebase | The actual repository files and active code. | **Execution:** Live implementation logic. Raw fallback only. |

For complete per-tier descriptions, Key Files inventories, and inclusion rules see [Context_Scaling/tier_reference.md](Context_Scaling/tier_reference.md).

---

## 3. Reference Directionality

All cross-file references are **strictly one-directional: parent → child only.**

- Tier 0 may reference Tier 1 files.
- Tier 1 may reference Tier 2 files within its own concept folder.
- Tier 2 may reference Tier 3 examples within its own concept folder.
- **No file may reference a file at the same tier or a higher tier.**

**Why:** Upward or lateral references create circular discovery paths and force re-ingestion of already-loaded context. One-directional flow means reading top-down is always sufficient.

**Path hygiene:** A file path is written exactly once — in its immediate parent's reference list. Duplication across files signals the concept belongs at a different tier or should be consolidated.

---

## Sub-specifications

See [Context_Scaling/index.md](Context_Scaling/index.md) for the full, machine-routable index of Tier 2 guides (tier reference, persona routing, skeleton specs, technical decisions system, refactoring guide).
