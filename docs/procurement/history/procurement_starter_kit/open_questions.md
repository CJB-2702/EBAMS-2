---
okf_version: "0.1"
type: "Process Guide"
title: "Open Questions — Part Demand + Purchasing"
description: "Remaining unknowns after the questionnaire and the 2026-08-08 review session. Each row is later resolved to a decision, deferred to tech debt, or explicitly dropped."
tags: [starter-kit-process, process-guide, open-questions, okf]
context_tier: 2
personas: [backend, business]
---

# Open Questions — Part Demand + Purchasing

One row per remaining unknown that still blocks or shapes this kit. See `decisions.md` for
everything already resolved. Items deferred to tech debt (the process-template/workflow engine,
the external PO integration API) have been relocated out of this kit entirely — see
`docs/procurement/tech_debt/` — and are not tracked here, since they no longer describe
work this kit is planning to do.

**No open items remain as of 2026-08-08.** The last remaining item (P2) is resolved below.

---

## 1. Per-persona volume (questionnaire P2) — Resolved 2026-08-08 (D44)

**Question:** For each persona (Requester, Approver, Buyer), what do they do 50 times a day versus
once a month?

**Resolution:** Requester and Buyer are both high-frequency/daily; Approver's explicit action is
comparatively rare since Purchasing often bypasses it (D42); shipping/stocking updates are very
high frequency and ideally machine-driven; `Partially Issued`/`Backordered` are common, not edge
cases; all cancellation types are rare. Full detail in `decisions.md` D44, and folded into
`part_demand_system.md` §7's persona behavior notes.
