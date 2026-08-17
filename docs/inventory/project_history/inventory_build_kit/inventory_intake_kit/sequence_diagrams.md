# User-Perspective Sequence Diagrams: Automated Intake & Blind Receiving

This document details the step-by-step interactive sequences for all primary user workflows in the automated intake receiving system. Each diagram illustrates how the Operator/Manager interacts with the HTMX frontend, and how it delegates to Django Views, the Control Layer (`IntakeContext`), and Postgres.

---

## Workflow 1: Start/Resume Intake Session
The operator starts a receiving run at the dock, selecting expected shipments.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant UI as Browser (Intake HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant DB as Postgres DB

    Operator->>UI: Clicks "New Intake Session"
    UI->>Views: GET /inventory/intake/new/
    Views-->>UI: Render Dock Location & Shipment selection template
    
    Operator->>UI: Selects Dock Bay & enters tracking numbers
    UI->>Views: POST /inventory/intake/start/ (Form submission)
    Views->>Context: start_session(operator_id, shipment_ids, dock_location_id)
    Context->>DB: INSERT INTO intake_session (status='draft', ...)
    Context->>DB: INSERT INTO scanning_session_shipment_associations
    DB-->>Context: Saved session & associations
    Context-->>Views: Returns IntakeSessionStruct
    Views-->>UI: Redirect (302) to active intake dashboard (/inventory/intake/session/{id}/)
    UI-->>Operator: Shows active dashboard: "Ready for scan..."
```

---

## Workflow 2: Happy Path A — Scanning Non-Serialized Item (Quantity = 1)
*This is the default receiving behavior.* The operator scans a standard item that does not track serial numbers, expecting a quantity increment of 1.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant UI as Browser (Dashboard HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant DB as Postgres DB

    Operator->>UI: Scans barcode (SKU: OIL-FLTR)
    Note over UI: Scanner triggers input field change & automatic HTMX POST
    UI->>Views: POST /inventory/intake/session/{id}/scan/ [payload: "OIL-FLTR"]
    Views->>Context: process_scan(session_id, raw_payload="OIL-FLTR")
    Note over Context: Part config: sn_expected = False, qty_per_scan = 1.0
    Context->>DB: Query associated ShipmentLines expecting SKU "OIL-FLTR"
    DB-->>Context: Found 1 matching line (L1: expected 10, received 2)
    Context->>DB: INSERT INTO item_allocation (shipment_line_id=L1, qty=1.000, condition='good', method='scan', serial_number=null)
    DB-->>Context: Allocation created
    Context-->>Views: Returns ItemAllocationStruct
    Views-->>UI: Render HTML Fragment: updated line L1 count (3/10) & flash status
    UI-->>Operator: Flash green screen indicator & play confirmation chime
```

---

## Workflow 3: Happy Path B — Scanning Bulk Non-Serialized Item (Quantity = qty_per_scan)
The operator scans a bulk package (e.g. box of screws) where the part definition has a default quantity multiplier (e.g., 100) and does not track serial numbers.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant UI as Browser (Dashboard HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant DB as Postgres DB

    Operator->>UI: Scans bulk barcode (SKU: SCREW-M4)
    UI->>Views: POST /inventory/intake/session/{id}/scan/ [payload: "SCREW-M4"]
    Views->>Context: process_scan(session_id, raw_payload="SCREW-M4")
    Note over Context: Part config: sn_expected = False, qty_per_scan = 100.0
    Context->>DB: Query associated ShipmentLines expecting SKU "SCREW-M4"
    DB-->>Context: Found 1 matching line (L2: expected 500, received 100)
    Context->>DB: INSERT INTO item_allocation (shipment_line_id=L2, qty=100.000, condition='good', method='scan', serial_number=null)
    DB-->>Context: Allocation created
    Context-->>Views: Returns ItemAllocationStruct
    Views-->>UI: Render HTML Fragment: updated line L2 count (200/500)
    UI-->>Operator: Flash green screen indicator & play confirmation chime
```

---

## Workflow 4: Barcode Scanning with Serial Number Prompt (Skipped or Entered)
Scanning a part configured with `sn_expected = True`.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant UI as Browser (Dashboard HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant DB as Postgres DB

    Operator->>UI: Scans barcode (SKU: EXP-ENGINE)
    UI->>Views: POST /inventory/intake/session/{id}/scan/ [payload: "EXP-ENGINE"]
    Views->>Context: process_scan(session_id, raw_payload="EXP-ENGINE")
    Note over Context: Part definition has sn_expected = True
    Context-->>Views: Returns ScanResult (requires serial number)
    Views-->>UI: Render HTML Fragment: Pop-up dialog "Enter Serial Number"

    alt Case A: Operator inputs Serial Number
        Operator->>UI: Types or scans serial number "SN-8809"
        UI->>Views: POST /inventory/intake/session/{id}/allocate-serial/ [serial: "SN-8809"]
        Views->>Context: process_scan(session_id, raw_payload="EXP-ENGINE", serial="SN-8809")
        Context->>DB: Query active DB for composite duplicate "EXP-ENGINE:SN-8809"
        DB-->>Context: No duplicates found
        Context->>DB: INSERT INTO item_allocation (qty=1, serial="SN-8809")
        DB-->>Context: Saved
        Context-->>Views: Returns ItemAllocationStruct
        Views-->>UI: Close popup, render HTML Fragment updating line count & flash green
        UI-->>Operator: Play confirm chime
    else Case B: Operator skips Serial Number
        Operator->>UI: Clicks "Skip Serial Input"
        UI->>Views: POST /inventory/intake/session/{id}/allocate-serial/ [serial: null]
        Views->>Context: process_scan(session_id, raw_payload="EXP-ENGINE", serial=None)
        Context->>DB: INSERT INTO item_allocation (qty=1, serial=null)
        DB-->>Context: Saved
        Context-->>Views: Returns ItemAllocationStruct
        Views-->>UI: Close popup, render HTML Fragment updating line count & flash amber
        UI-->>Operator: Play generic scan beep
    end
```

---

## Workflow 5: Barcode Scanning with N-to-M Ambiguous Staging & FIFO Cascade
Scanning bulk items expected on multiple associated shipment lines.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant UI as Browser (Dashboard HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant Matching as IntakeMatchingManager
    participant DB as Postgres DB

    Operator->>UI: Scans Bulk Screw (SKU: SCREW-M4)
    UI->>Views: POST /inventory/intake/session/{id}/scan/ [payload: "SCREW-M4"]
    Views->>Context: process_scan(session_id, raw_payload="SCREW-M4")
    Context->>Matching: find_target_line(session_id, part_id)
    Matching->>DB: Query open expected lines
    DB-->>Matching: Returns 2 matches (L1 expected: 5, L2 expected: 5)
    Note over Matching: Ambiguous match -> creates unassociated ItemAllocation
    Context->>DB: INSERT INTO item_allocation (shipment_line=null, qty=1, method='scan')
    
    Context->>DB: Query sum of unallocated allocations for SCREW-M4
    DB-->>Context: Sum = 9 (Below expected total of 10)
    Context-->>Views: Returns Staged Allocation status
    Views-->>UI: Render HTML Fragment updating staged badge counter (9/10 staged)
    UI-->>Operator: Play double-beep & increment counter badge
    
    Note over Operator: Operator scans the 10th Bulk Screw
    Operator->>UI: Scans Bulk Screw (SKU: SCREW-M4)
    UI->>Views: POST /inventory/intake/session/{id}/scan/ [payload: "SCREW-M4"]
    Views->>Context: process_scan(session_id)
    Context->>DB: INSERT INTO item_allocation (shipment_line=null, qty=1)
    Context->>DB: Query unallocated sum -> Returns 10 (Threshold met!)
    
    Context->>DB: BEGIN TRANSACTION
    Context->>Matching: execute_fifo_cascade(session_id, part_id)
    Matching->>DB: UPDATE item_allocation: link first 5 rows to L1
    Matching->>DB: UPDATE item_allocation: link next 5 rows to L2
    Context->>DB: COMMIT TRANSACTION
    
    Context-->>Views: Returns Cascade Allocation summary
    Views-->>UI: Render HTML Fragment: lines L1 and L2 marked COMPLETE
    UI-->>Operator: Play triumph chime
```

---

## Workflow 6: Quality Inspection & Split Allocation
The operator splits a scanned line/allocation into good and rejected quantities in the UI.

```mermaid
sequenceDiagram
    autonumber
    actor Operator
    participant UI as Browser (Dashboard HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant DB as Postgres DB

    Operator->>UI: Click "Inspect & Split" on line
    UI-->>Operator: Displays numeric split inputs
    
    Operator->>UI: Inputs Good: 8, Rejected: 2 (Total scanned was 10)
    UI->>Views: POST /inventory/intake/session/{id}/split/ [allocation_id=X, good=8, rejected=2]
    Views->>Context: split_allocation(allocation_id=X, good_qty=8, rejected_qty=2)
    
    Context->>DB: BEGIN TRANSACTION
    Context->>DB: UPDATE item_allocation (id=X) SET quantity=8, condition='good'
    Context->>DB: INSERT INTO item_allocation (session_id, qty=2, condition='rejected')
    Context->>DB: COMMIT TRANSACTION
    DB-->>Context: Changes saved
    
    Context-->>Views: Returns list of updated allocations
    Views-->>UI: Render HTML Fragment displaying split rows (8 Good, 2 Rejected)
    UI-->>Operator: Plays confirm split notification tone
```

---

## Workflow 7: Session Reconciliation & Deficit Review (Manual Adjustments)
The manager reconciles unsatisfied lines, short-shipments, or quarantined items.

```mermaid
sequenceDiagram
    autonumber
    actor Manager
    participant UI as Browser (Reconciliation HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant DB as Postgres DB

    Manager->>UI: Accesses session reconciliation page
    UI->>Views: GET /inventory/intake/session/{id}/reconcile/
    Views->>DB: Query unsatisfied shipment lines & unallocated items
    DB-->>Views: Return data
    Views-->>UI: Render split-screen reconciliation matrix template

    alt Case A: Manager manually adjusts/overrides a line count
        Manager->>UI: Inputs manual count "5" on unsatisfied line L3
        UI->>Views: POST /inventory/intake/session/{id}/override/ [line_id=L3, quantity=5]
        Views->>Context: create_manual_allocation(session_id, shipment_line_id=L3, quantity=5)
        Context->>DB: INSERT INTO item_allocation (shipment_line_id=L3, qty=5, method='manual')
        DB-->>Context: Saved
        Context-->>Views: Returns updated allocation
        Views-->>UI: Render HTML Fragment: line L3 updated to 5 & flagged manual
    else Case B: Manager resolves unmanifested quarantine item
        Manager->>UI: Selects quarantined item & maps it to Shipment line L4
        UI->>Views: POST /inventory/intake/session/{id}/map-quarantine/ [allocation_id=Y, target_line=L4]
        Views->>DB: UPDATE item_allocation SET shipment_line_id=L4 WHERE id=Y
        DB-->>Views: Updated
        Views-->>UI: Render HTML Fragment: remove from quarantine list & add to line count
    end
```

---

## Workflow 8: Session Close & Committing to Inventory
The manager locks the session, executing physical stock injection and procurement hand-off.

```mermaid
sequenceDiagram
    autonumber
    actor Manager
    participant UI as Browser (Reconciliation HTML)
    participant Views as Django Views (HTMX)
    participant Context as IntakeContext
    participant Reg as InventoryRegistrationManager
    participant DB as Postgres DB

    Manager->>UI: Clicks "Close & Commit Session"
    UI->>Views: POST /inventory/intake/session/{id}/close/
    Views->>Context: close_session(session_id, notes)
    
    Context->>DB: BEGIN TRANSACTION
    Context->>DB: UPDATE intake_session SET status='closed', closed_at=now()
    
    Context->>Reg: register_received_items(session_id)
    Note over Reg, DB: Inserts items into warehouse stock with location = None
    Reg->>DB: INSERT INTO inventory_item (part_id, serial_number, quantity, location_id=null)
    
    Context->>Reg: update_procurement_shipments(session_id)
    Note over Reg, DB: Writes received counts to procurement ShipmentLines
    Reg->>DB: UPDATE shipment_line SET quantity_accepted = X WHERE id = Y
    
    Context->>DB: COMMIT TRANSACTION
    DB-->>Context: Transaction committed
    
    Context-->>Views: Returns final session summary DTO
    Views-->>UI: Redirect (302) or render final receipt template
    UI-->>Manager: Displays success message: "Session closed. Stock updated."
```
