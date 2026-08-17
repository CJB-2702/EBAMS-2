# Starter Kit Questionnaire

**Status:** `COMPLETE`

---

## A. Goals

*What this is for. Answer these without naming a single table.*

### G1 — In one sentence, with no nouns from your schema: what does this let someone do that they cannot do today?

**Answer:**
Let operators physically receive incoming shipments, verify their contents by scanning or manual entry, auto-allocate items to expected lists, reject damaged goods (manually splitting a batch into good and rejected counts), quarantine unexpected items, and register them into inventory without assigning a storage location.

---

### G2 — What is this explicitly NOT? Name the adjacent system it will be mistaken for.

**Answer:**
- It is explicitly NOT the **Shipment tracking system** (owned by Procurement), which tracks vendor claims, carriers, and transits prior to physical custody.
- It is explicitly NOT the **Put-away/Storage location system** (a downstream Inventory feature), which assigns items to specific bins, racks, or rooms.
- It is explicitly NOT a **Purchase Order manager**.

---

### G3 — What is the single record everything else hangs off, and what is the *only* thing the rest of the app is allowed to know about it?

**Answer:**
The **Intake Session**. The rest of the application is only allowed to know its unique ID, its operational status (e.g., in-progress, reconciling, completed), and the physical items that were verified and registered during it.

---

### G4 — Which of this data is authoritative for us, and which mirrors a system we do not control?

**Answer:**
- **Authoritative:** The physical receiving allocations (the quantities counted, the serial numbers, conditions, and intake methods recorded during the session).
- **Mirroring:** The expected shipment manifest, purchase orders, and item SKU/serial masters, which are defined and controlled by Procurement/Engineering outside of this intake session.

---

## B. Personas

*Who uses this. Fill the matrix even where you are unsure — `?` cells are the point.*

### P1 — Name each persona and the one sentence they would use to describe their job here. Which is the highest-volume user?

**Answer:**
1. **Dock Operator (highest-volume user):** "I open boxes, scan barcodes, manually enter quantities, and physically inspect/split items as they arrive at the dock."
2. **Inventory Manager:** "I oversee the dock, resolve quarantined or discrepant items, and reconcile intake sessions that have deficits."

---

### P2 — For each persona, what do they do 50 times a day versus once a month?

**Answer:**
- **Dock Operator:**
  - *50 times a day:* Scan item barcodes, check/split quantities into good vs rejected, and manually key in quantities for bulk goods.
  - *Once a month:* Log a hardware issue with the scanner.
- **Inventory Manager:**
  - *5 times a day:* Reconcile intake sessions with missing items or quarantine mismatches.
  - *Once a month:* Adjust matching rules or inspect historical intake session logs.

---

### P3 — Fill in the capability × role matrix, including the cells you are unsure of.

**Answer:**

| Capability | Dock Operator | Inventory Manager |
| :--- | :---: | :---: |
| Start/Resume Intake Session | C / R | C / R / U |
| Scan Barcodes (1D/2D) | C / R | C / R |
| Manually Enter/Adjust Allocations | C / R / U | C / R / U |
| Split Items into Good vs Rejected | C / R / U | C / R / U |
| Reconcile Deficits / Shortages | R | C / R / U |
| Close & Commit Session | C / R | C / R / U |
| Hard Delete / Reset Session | — | U / D |

---

### P4 — Is any of this data restricted to a subset of users? Is restriction the default or the exception, and roughly what percentage?

**Answer:**
Restriction is the exception (less than 10%). Standard operators can perform almost all intake and scanning/splitting tasks. Only Inventory Managers have the restriction to override quarantine states, force-close deficient sessions, or delete sessions.

---

## C. Business relationships

*How the pieces connect and what happens when they change.*

### R1 — For every link: one-to-many or many-to-many? What breaks the day it becomes many-to-many?

**Answer:**
- **Intake Session to Shipment:** Many-to-many (via `ScanningSessionShipmentAssociation`). A session can receive from multiple shipments; a shipment can be partially received across multiple sessions.
- **Shipment to ShipmentLine:** One-to-many.
- **ShipmentLine to ItemAllocation:** One-to-many.
- **Intake Session to ItemAllocation:** One-to-many.

---

### R2 — When a record is created, what else must come into existence automatically? For each: if it fails, does the original creation fail too?

**Answer:**
- When an **Intake Session** is created, the session status header is initialized.
- When an **ItemAllocation** is created, the matching analysis links it to an expected `ShipmentLine` if possible, otherwise it stays unallocated (quarantined/unmanifested).
- If the database write for **ItemAllocation** fails, the transaction fails and blocks the intake step (triggering UI buzzer/error).

---

### R3 — When a record is deleted or deactivated, what happens to everything pointing at it? Soft or hard?

**Answer:**
- We do not allow hard deletion of intake sessions or allocations once they are active, to preserve audit trails.
- Soft delete is enforced using the project's standard `SoftDeleteMixin`. If an Intake Session is cancelled, all of its nested allocations must be deactivated or rolled back.

---

### R4 — When several constraints apply at once, must all pass or any pass? Write the truth table.

**Answer:**
For Serialized Item intake validation:
- Constraint A: `sn_expected` is true on the Part, or the user enters a Serial Number.
- Constraint B: Serial has not been scanned in current session for this Part.
- Constraint C: Serial does not already exist on an active (not checked out or scrapped) inventory item.

| Serial Expected (A) | Session Duplicate (B) | DB Duplicate for Part (C) | Result |
| :--- | :--- | :--- | :--- |
| False | N/A | N/A | **ALLOW** (Qty defaults to `qty_per_scan`) |
| True | False (Not Dup) | False (Not Dup) | **ALLOW** (Qty = 1, serial registered) |
| True | True (Dup) | N/A | **REJECT** (Buzzer - Session Collision) |
| True | N/A | True (Dup) | **REJECT** (Buzzer - Active Stock Collision) |

---

### R5 — At what moment is each rule enforced — authoring time, assignment time, or execution time? What happens when the check cannot be decided?

**Answer:**
- Barcode validity & parsing: Execution time (on scan).
- Serial expected prompt: Execution time (on scan, if `sn_expected` is true, prompts enter serial screen - skippable).
- Serial deduplication: Execution time (on scan/manual serial input).
- N-to-M Ambiguous Matching: Execution time (FIFO cascade triggers only when cumulative threshold is satisfied).
- If matching cannot be decided (SKU not in associated shipments): The allocation remains unassociated (`shipment_line_id = null`), acting as quarantined.

---

### R6 — Which app owns this? Which apps must remain completely ignorant of it, and what are the permitted seams?

**Answer:**
- **Owner:** `inventory` app.
- **Ignorant:** `assets`, `administration`, and `public_app` remain ignorant.
- **Seams:**
  - Procurement's `ShipmentLine.quantity_accepted` gets updated directly at the end of the session.
  - Procurement's `ShipmentLine.is_manually_adjusted` flag is set to `True` if edited directly in the Procurement UI (outside of intake).
  - Inventory items are created/moved in the inventory system with `location = None` when the session is closed.
  - `parts.Part` defines `qty_per_scan` (default 1) and `sn_expected` (default False).

---

## D. Data model

*Only after the sections above are answered.*

### M1 — Glossary: list every domain noun. Mark any word that already means something else in this system, in Django, or in the business.

**Answer:**

| Noun | Means here | Collides with |
| :--- | :--- | :--- |
| **IntakeSession** | Tracks an operator's active receiving run. | — |
| **ScanningSessionShipmentAssociation** | Join table connecting intake session to expected shipments. | — |
| **ItemAllocation** | Tracks an individual physical scan or manual receipt, linked to a shipment line. | — |
| **Shipment** | Procurement model representing expected package(s). | Yes, maps to procurement's `Shipment`. |
| **ShipmentLine** | Procurement model representing expected SKU and quantity. | Yes, maps to procurement's `ShipmentLine`. |

---

## M2 — Where two concepts overlap, which is the concrete/primary one and which is the restricted view of it?

**Answer:**
`ItemAllocation` is the concrete, primary representation of physical reality (what was actually scanned or manually entered). The received quantities on the expected shipment are a derived summary of these allocations.

---

### M3 — Is this variation a type label, a set of capability flags, or a distinct class? Can a caller construct an invalid combination?

**Answer:**
- Intake Session Status (`DRAFT`, `ACTIVE`, `RECONCILING`, `CLOSED`), Condition (`good`, `rejected`), and Intake Method (`scan`, `manual`) are type labels / enums.
- Callers cannot construct invalid states because status transitions are gated by control-layer guards.

---

### M4 — Is this attribute intrinsic to what the thing *is*, or to *where it is used*?

**Answer:**
- The item's Serial Number and Condition are intrinsic to the physical item (`ItemAllocation`).
- The `qty_per_scan` and `sn_expected` are intrinsic to what the part *is* (`parts.Part`).
- The `is_manually_adjusted` flag is intrinsic to the procurement line (`ShipmentLine`), indicating direct human edits to the manifest rather than derived summaries of scan allocations.
- The `intake_method` (`scan` vs `manual`) is intrinsic to the receipt action (`ItemAllocation`).

---

### M5 — How do users version and identify this? Can you trust their naming convention? What exactly does "current" mean, and is it the same as "newest"?

**Answer:**
- Intake Sessions use system-generated ID keys.
- Shipments use carrier tracking numbers or shipment numbers. We cannot trust their uniqueness, so they are matched by system keys.
- "Current" session refers to the single active session for an operator/device combination.
- Composite Serial Number (`composite_sn`): Lookup key of `part_id` + `serial_number` to check active inventory duplicates.

---

### M6 — Which entities carry free-form human content — comments, documents, photos, notes? Assume the answer is "more than you think."

**Answer:**
- `IntakeSession` (session notes and reconciliation explanation).
- `ItemAllocation` (notes regarding manual overrides, damage, or quarantine disposition).

---

## E. Migration defaults

*Skip this section entirely for net-new work.*

### X1 — What is today's behavior, and does the new default reproduce it exactly? What are you doing with the old code — clean cut or shims?

**Answer:**
_(not applicable / net-new work)_

---

## Sign-off

- [x] Every question above is answered, or explicitly marked unknown.
- [x] Pre-filled `_(from initial prompt)_` answers have been reviewed and the markers removed.
- [x] **Status at the top of this file is set to `COMPLETE`.**
