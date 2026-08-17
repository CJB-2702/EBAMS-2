---
okf_version: "0.1"
type: "Index"
title: "Reallocation Resolution Kit"
description: "Phases and build plan for the Reallocation Resolution Portal policy, built from a chat-planning session rather than the full Kit Builder questionnaire/interrogation process."
tags: [starter-kit, procurement, reallocation, index, okf]
context_tier: 1
personas: [backend, business, frontend]
---

# Reallocation Resolution Kit

**This kit skips the standard `/kit-builder` questionnaire and interrogation stages.**
The business rules were worked out directly in a chat planning session with the
Business Architect persona and are considered final. This kit exists only to turn that
finished policy into an ordered, buildable phase plan — it is not a from-scratch
starter kit.

## Source of truth

[`reallocation_resolution_portal.md`](../reallocation_resolution_portal.md) (repo root)
is the **business rule contract**. Every phase below implements specific numbered
sections/rules from that document and must not contradict it. If a build decision here
seems to disagree with that document, the document wins — fix this kit, not the other
way around.

Read it first. This kit does not repeat the rules, only sequences the work.

## Scope

**In:** the Demand↔PO Domain (Buying) and the Package↔PO Domain (Receiving)
reallocation-resolution mechanics — shrinking-source resolution, the Reallocation
Portal, cross-domain claim visibility, and cross-order over-allocation refusal, exactly
as specified in `reallocation_resolution_portal.md`.

**Out:** anything about pricing, vendor management, the graph/`GraphSummary` engine
(unrelated system, explicitly not what this kit means by "domain"), or UI outside the
linkage and Reallocation Portal screens.

## How to read it

| Document | Answers |
| :--- | :--- |
| [build_plan.md](build_plan.md) | The phase order, dependencies between phases, and overall checkpoints. |
| [phase_1_core_capacity_rules/README.md](phase_1_core_capacity_rules/README.md) | Foundational data + validation: locked floor, silent auto-update paths, the demand-requeue rule. Demand↔PO Domain. |
| [phase_2_reallocation_portal/README.md](phase_2_reallocation_portal/README.md) | The Reallocation Portal itself: LOCKED/OPEN split, auto-allocate waterfall, manual entry, the two-popup unlock sequence. Demand↔PO Domain. |
| [phase_3_cross_domain_visibility/README.md](phase_3_cross_domain_visibility/README.md) | Inline "claimed elsewhere" hints and the Portal's external-locked claims display. Demand↔PO Domain only. |
| [phase_4_cross_order_refusal/README.md](phase_4_cross_order_refusal/README.md) | The hard-stop guard for a demand double-claiming across two orders. Demand↔PO Domain only. |
| [phase_5_package_po_mirror/README.md](phase_5_package_po_mirror/README.md) | The same shrinking-source mechanics and Portal, mirrored onto the Package↔PO Domain — no cross-domain visibility or cross-order refusal needed there. |

## Provenance

Written from a single chat planning session between the user and the Business
Architect persona, 2026-08-16, covering: quantity-tracking additions to the demand/PO
and package/PO link tables, the shrinking-source resolution policy, locking, the
one-to-one silent-update shortcut, cross-domain claim visibility, and cross-order
over-allocation refusal. See `reallocation_resolution_portal.md` for the full
reasoning, diagrams, and acceptance scenarios behind every phase in this kit.
