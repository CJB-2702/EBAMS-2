---
okf_version: "0.1"
type: "Build Prompt"
title: "Intake Portal — Phase 2: Control Layer"
description: "The write verbs and derived reads: the over-allocation ban, the auto-association policy, the lock/post lifecycle, scan commands, and the shipment-line truth read model."
tags: [inventory, intake, build-prompt, control-layer, phase-2]
context_tier: 2
personas: [backend]
created: 2026-08-21
created_by: Christian Bissett
updated: 2026-08-21
updated_by: Christian Bissett
---

# Phase 2 — Control Layer

## The prompt

Read `docs/inventory/intake_portal_workflow.md` in full. Phase 1 landed the
schema; the columns exist and are empty of behavior. Build the control layer
that gives them meaning. **No templates, no routes, no view logic** — Phase 3
owns those. When this phase is done the backend can perform every task the
spec describes, and nothing can see it yet.

### 1. The over-allocation ban — `AllocationLinkManager` (§7.2, §12.6)

The single most important thing in this phase. Everything else depends on it.

```
for any ShipmentLine L:  sum(live allocations linked to L) <= L.quantity
```

- Enforced on **every** write path that sets `ItemAllocation.shipment_line`:
  auto-association, manual linking, the allocation portal. One method, called
  by all of them — do not let a second linking path grow.
- The line must be **locked for update** (`select_for_update`) while the sum
  is checked and the write applied, inside one transaction.
- "Live allocations" means every non-soft-deleted allocation from every
  non-cancelled session. **Not this session's.** (§5.5)
- Enforced at **write time**, not as a standing invariant. If procurement
  later reduces a line's quantity below what is already allocated, the
  existing rows stand — that is a report, not a violation to repair.
- When a line is full, the caller gets an **explanation, not an error**:
  *"This line is fully allocated (50/50). The remaining 5 units stay unlinked
  as excess."*

### 2. The auto-association policy — `AutoAssociationPolicy` (§5.2, §5.3)

Implement the flowchart exactly. Order matters:

1. Record the allocation. **This always succeeds.** Linking never blocks a count.
2. Does the part number appear on exactly ONE line in the entire session
   manifest? → link, `link_source = auto_single_match`.
3. Else, is an active shipment set AND the part on one of its lines AND that
   line not yet full **across all sessions**? → link,
   `link_source = auto_active_package`.
4. Else → leave unlinked, `link_source = unlinked`.

**Silent non-association is the default and correct outcome.** The operator is
never shown a linking failure, never blocked, never asked to resolve ambiguity
while holding a box. Everything unlinked flows to the allocation portal.

Retire `IntakeMatchingManager.find_target_line` and `execute_fifo_cascade` —
the FIFO cascade is a different, older policy that predates the active
shipment and the over-allocation cap. Keep `parse_barcode`.

### 3. Shipment-line truth — `ShipmentLineTruthStruct` (§5.5, §11.2)

The read model everything else derives from. For a shipment line, compute
from **all live allocations across every non-cancelled session**:

- expected (`line.quantity`), linked good, linked rejected, remaining capacity
- the split between *this session's* rows and *other sessions'* rows, so the
  UI can dampen and lock the latter without a second query
- shortage / unlinked-excess / rejected figures, **derived on every read,
  never stored**

Also provide a part-number rollup for the record page's bars, summed across
every associated shipment (Part A on three shipments is one bar, §2.2).

**Two different bars, and conflating them is what made the old page
unreadable (§3):**

| Bar | Numerator / denominator | Question |
| :--- | :--- | :--- |
| Record | counted / expected | *Did it all show up?* |
| Associate | linked / counted | *Did I file it all?* |

The Associate bar cannot exceed 100%, by construction of the ban.

### 4. Lifecycle verbs (§4.2, §4.3)

Two independent axes, each an event stamp, not an enum position:

- `lock_recording(actor)` — sets `recording_locked_at/_by`. Only when a user
  explicitly says so. Nothing auto-locks. Idempotent-safe: re-locking is a
  no-op or a clear refusal, never a crash.
- `post_stock(actor)` — the irreversible act. All-or-nothing. Refuses if
  already posted. This is the existing `IntakeCommitOrchestrator.close`,
  renamed to what it actually does and stamping both fields.
- The fork at end of recording is two calls, not a mode flag: option 1 is
  `lock_recording` + `post_stock`; option 2 is `lock_recording` alone.

Recording-locked sessions refuse new allocations and all scan commands.

### 5. Scan-field commands — `ScanCommandHandler` (§6)

| Payload | Action |
| :--- | :--- |
| `CMDXDELETE` | Soft-delete the last recorded allocation. Repeatable, walks backwards. |
| `CMDXSERIAL` | Capture a serial onto the last allocation. **Forces quantity to 1.** |
| `CMDXQTY1` | Always **add** 1 |
| `CMDXQTY10` | If quantity is 1, **set** to 10; else **add** 10 |
| `CMDXQTY100` | If quantity is 1, **set** to 100; else **add** 100 |

- `CMDX` is a **reserved namespace**: exact, whole-payload, case-sensitive
  match. A real barcode merely *containing* `CMDX` is never a command.
- All `CMDXQTY*` are **refused on a serialised allocation** (§6.2) — this is a
  data-corruption path, not a preference.
- `CMDXSERIAL` on an allocation whose quantity is already >1 is **refused**,
  not silently resolved.
- Commands are ignored on a locked session, like any other input.
- Every command produces loud confirmation text — the one place in the record
  flow where silence would be dangerous.

Quantity changes re-run association: growing a quantity may no longer fit
under the line's cap.

### 6. Barcode tokens (§9.4)

`INTAKE-<id>` and `SHIP-<id>`, Code 128. Parse them in the scan handler so a
token scanned into the wrong field is **recognised and explained**, not
silently mis-recorded as a SKU. A `SHIP-` token in the record field sets the
active shipment (§5.1, §9.6).

### 7. Active shipment + continuation (§5.1, §7.5)

- `set_active_shipment(shipment_id)` — must be one of the session's associated
  shipments. Stored, so it survives F5.
- `set_continues_session(session_id)` — **display-only.** Nothing reads it,
  aggregates across it, or validates against it. Do not build logic on it.

### 8. Activity thread + narrator (§8, §7.6)

- Wire `events.ActivityThreadManager` with `thread_attr="activity_thread"` and
  the inventory `thread_domain` resolver. Nullable, lazily created.
- Machine comments go on the thread via `IntakeNarrator`.
- **Rejection reasons have no column.** Marking an item rejected writes a
  narrator comment prefixed with the line identifier as plain text. Nothing
  parses that prefix.

### 9. Graph closure — read-only (tech debt §4)

`ShipmentGraphManager.closure_for(session)`: the connected component over
shared shipments. Returns the component's sessions and shipments plus whether
it reaches beyond the current session. **No writes, no schema.** Phase 3
renders it only when the closure is wider than the session itself.

### 10. Allocation portal — write side (§7.3)

`link_allocation` / `unlink_allocation`, both through the ban in §1. Two
scopes, one code path: session-scoped and global. Building two linking engines
would be the mistake this section exists to prevent.

## Done when

- Every verb above exists and is exercised by tests.
- The ban is proven by a test that tries to over-allocate concurrently.
- `refresh_project.py` runs clean; seeds succeed.
- Inventory tests green; report anything red and why.

## Do not

- Build any template, route, or view.
- Re-add a reconciliation table, a resolution type, or any notion of sign-off.
- Scope any quantity calculation to a single session.
