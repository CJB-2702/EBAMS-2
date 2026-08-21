---
okf_version: "0.1"
type: "Build Prompt"
title: "Intake Portal — Phase 3: Presentation Layer"
description: "The seven surfaces: create, record, associate, discrepancies, review, index, print — plus the global allocation portal and the Code 128 receipt."
tags: [inventory, intake, build-prompt, presentation-layer, phase-3]
context_tier: 2
personas: [frontend]
created: 2026-08-21
created_by: Christian Bissett
updated: 2026-08-21
updated_by: Christian Bissett
---

# Phase 3 — Presentation Layer

## The prompt

Phases 1 and 2 landed: the schema carries the model and the control layer can
perform every task. Build the surfaces. **Every read comes from a Phase 2
struct or manager — no view recomputes a quantity.** If a template needs a
number that no struct provides, add it to the struct, never to the view.

### The seven surfaces (§2)

| # | Route | Job | Actor |
| :-- | :--- | :--- | :--- |
| 1 | `/inventory/intake/create` | Choose which shipments this run receives against | Dock operator |
| 2 | `/inventory/intake/<id>/record` | Get every physical item counted | Dock operator |
| 3 | `/inventory/intake/<id>/associate` | Match what arrived to what the paperwork promised | Operator or lead |
| 4 | `/inventory/intake/<id>/discrepancies` | **Read** what does not match | Manager / buyer |
| 5 | `/inventory/intake/<id>/` | The whole picture; post stock | Anyone |
| 6 | `/inventory/intake/` | Find a session | Anyone |
| 7 | `/inventory/intake/<id>/print` | Paper receipt with barcodes | Anyone |

Plus `/inventory/intake/allocate` — the global allocation portal (§7.3).

`/inventory/intake/<id>/` is canonical; review is its default representation.
There is no separate `/view`.

### This is a deliberate convention exception (§1.1)

The standing rule is *creation flows are one long scrolling page*. Intake
violates all three of that rule's premises: two actors with different
authority, work spanning days, and a manager who needs a URL they can be
**sent**. Handoff-driven processes get addressable URLs.

**Do not refactor this back into a wizard.**

### Page 2 — Record (§2.2)

Stripped to counting only. No linking UI, no staged pool, no reconciliation.
The operator's entire mental model is *"is everything in the boxes now in the
system?"*

- Bars aggregate **by part number**, summed across every associated shipment.
- The **active shipment** sits prominently (§5.1), set by scanning a `SHIP-`
  barcode off the printout or picking from a list.
- Auto-association runs silently. The operator never sees a linking failure.
- Scan commands work in the scan field (§6), with loud confirmation.
- Other sessions' allocations show **dampened grey and locked** (§5.5).
- Ends with the explicit two-option fork (§4.3) — never an auto-lock.

### Page 3 — Associate (§2.3)

One card per part number: shipment lines on one side, recorded scans on the
other, plus a linking utility. This is the allocation portal in its
session-scoped form. Assignment happens **in-page**, per the project's
assignment-card convention — never in a modal.

Bar reads linked / counted, and cannot exceed 100%.

### Page 4 — Discrepancy Report (§7.4)

**Read-only. No buttons that change state.** One card per part number showing
what does not match, all derived, never chosen. Renders the shipment graph
only when the closure reaches beyond this session (tech debt §4.1). Links out
to the allocation portal for anything actionable.

The page is named Discrepancy Report because "reconcile" is a verb the page no
longer supports, and a route that promises an action it does not offer is a
small lie repeated on every visit.

### Page 5 — Review (§2.5)

Static. Action buttons at the top route to pages 2/3/4/7 and indicate what
needs doing next. Carries **Approve Session** (posts stock) and the activity
thread (§8).

### Page 6 — Index (§2.6)

Cards. Carries the "waiting on me" filter that substitutes for notifications
(Q6) — there are no notifications and none are wanted.

### Page 7 — Print (§9)

**Pure view. No navigation, no breadcrumb, no sidebar, no links of any kind.**
This page is a document, not part of the application chrome.

- A single Print button, top right, hidden by `@media print`.
- Intake session barcode at the top; **every shipment gets its own barcode**.
- Parts listed under each shipment, grouped, one continuous document.
- Pen-and-paper columns on every part line — *Qty Accepted*, *Qty Rejected*,
  *Total Qty* — as blank ruled boxes.
- **Two modes**: pick sheet (expected lines, quantities blank) and receipt
  (recorded allocations with actual quantities).
- **Code 128**, encoding prefixed tokens: `INTAKE-8`, `SHIP-142`.
- Cross-session allocations are **excluded** — the printout is a working
  document for *this* receiving run.
- State on the sheet itself that the system never reads the written columns (§9.5).

Barcodes render **on the printout only** (Q14). No barcode appears anywhere in
the web UI. Paper is the scannable surface; the screen is the working surface.

### Standing UI law

- HTMX F5 rule: every page and state must work via a plain full-page reload.
- Single canonical URL per resource with `format=` for density and
  `htmx-*` for fragments. Never combine the two in one request.
- Cards always render, with an explicit empty state — never `{% if %}`-hidden.
- Sharp corners. No pill buttons.
- Single-line `{# #}` comments only; `{% comment %}` for anything longer.

## Done when

- All eight routes resolve and render, including with empty data.
- Every page survives F5.
- The print page renders valid Code 128 with no external dependency.
- `refresh_project.py` clean, seeds succeed, tests green.

## Do not

- Recompute a quantity in a view or a template.
- Put assignment in a modal.
- Add a button to page 4.
- Render a barcode in the web UI.
