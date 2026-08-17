---
type: "Process Guide"
title: "How to Design Mermaid Diagrams"
description: "Guidelines on selecting, writing, and formatting Mermaid diagrams in starter kits."
tags: [starter-kit-process, process-guide]
context_tier: 2
---

# How to Design Mermaid Diagrams

**Role & Objective:**
You are acting as an Architectural Illustrator and Documentation Designer. Your goal is to represent the system's logic, models, and execution flows visually using Mermaid diagrams to make starter kits clear and easy to build from.

---

## 1. Diagram Types & Usage Rules

| Diagram Type | When to Use | Key Requirements |
| :--- | :--- | :--- |
| **State Diagram** (`stateDiagram-v2`) | Documenting record states, session lifecycles, and transition-gating rules. | Clearly demarcate start/end nodes, loopback flows, and conditional blockades. |
| **System Flowchart** (`flowchart TD` or `LR`) | High-level user workflows, physical processes, and operator-facing branch points. | Focus on the human actor's journey and manual vs. automated inputs. |
| **Decision Tree** (`graph TD` or `flowchart TD`) | Ingestion validation rules, logic engines, parsing steps, and barcode match routing. | Make conditions explicit. Use branch nodes to show exactly where error tones/buzzers/exceptions trigger. |
| **Sequence Diagram** (`sequenceDiagram`) | Server-side template rendering, frontend interactions, context method delegation, and database transaction scopes. | Label all participant lifelines clearly. Explicitly mark transactional boundaries (`BEGIN / COMMIT`). |
| **Entity-Relationship** (`erDiagram`) | Relational database schema, table keys, data types, indexes, and primary/foreign key connections. | Represent PKs, FKs, field types, and correct relational cardinality (e.g., `||--o{`). |

---

## 2. Formatting & Syntax Rules (Parser Safety)

To ensure diagrams render correctly in markdown viewers and developer editors:

1. **Explicit Language Tags**: Fenced markdown code blocks containing diagrams must always start with ` ```mermaid ` on the opening tag. Do **not** use the diagram type as the language identifier (e.g., avoid ` ```sequenceDiagram `).
2. **Label Quoting**: Any node labels containing special characters (parentheses, colons, brackets, or math operators) must be enclosed in double quotes (e.g., `id["Label (Extra Info)"]`) to prevent syntax parsing errors.
3. **No HTML in Labels**: Do not embed HTML tags inside node labels.
4. **Logical Separation**: Group static models (flowcharts, ER diagrams) into `diagrams.md` and keep dynamic timelines in `sequence_diagrams.md` to prevent single-file bloating.
