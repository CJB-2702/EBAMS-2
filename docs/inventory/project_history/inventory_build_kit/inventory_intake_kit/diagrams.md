# System Diagrams: Automated Intake & Blind Receiving

This document consolidates all visual architectures, process flows, decision trees, split workflows, and relational schemas for the automated intake receiving system.

---

## 1. System Process Flowchart
This flowchart maps the end-to-end lifecycle of an intake session, from initialization to closing the session.

```mermaid
flowchart TD
    A([Start Intake Session]) --> B[Initialize Header: Operator, Dock, Hardware]
    B --> C[Link Expected Shipments & Create Associations]
    C --> D[Operator Performs Blind Item Scan or Manual Input]
    
    D --> E{Input Type?}
    E -->|Manual Entry| F[Create ItemAllocation: method = MANUAL]
    E -->|Barcode Scan| G[Parse Barcode: SKU & Serial]
    
    F --> H[Enter Quantity Directly]
    G --> I{Is Serial Expected on Part?}
    
    I -->|Yes| J[UI: Show Enter Serial Number Popup - Skippable]
    I -->|No| K{Serial Entered or Skipped?}
    J --> K
    
    K -->|Skipped| L[Enforce Allocation Qty = qty_per_scan]
    K -->|Entered| M{Check DB for Composite SN: part_id + serial?}
    
    M -->|Duplicate Found| N[BUZZER: Reject Scan Event]
    M -->|Unique| O[Enforce Allocation Qty = 1]
    
    N --> D
    H --> P[Matching Engine Analysis]
    L --> P
    O --> P
    
    P -->|Unique Shipment Line| Q[Link: Create ItemAllocation linked to ShipmentLine]
    P -->|Multiple Open Shipment Lines| R[Stage: Create unassociated ItemAllocation in Session]
    P -->|SKU Not in Shipment| S[Quarantine: Create unassociated ItemAllocation]
    
    R --> T{Cumulative Staged >= Expected Threshold?}
    T -->|Yes| U[Auto-Allocate: Link staged allocations to ShipmentLines via FIFO]
    T -->|No| V[Retain Staged & Update UI Counts]
    
    Q --> W[Operator Reviews Line Items]
    U --> W
    V --> D
    S --> W
    
    W --> X{Flag as Damaged or Split?}
    X -->|Yes| Y[Split Allocation into Good and Rejected Rows]
    X -->|No| Z{Finish Session?}
    
    Y --> Z
    Z -->|Yes, with Deficits or Quarantine| AA[Open Drag-and-Drop Reconciliation Matrix]
    Z -->|Yes, All Match| AB[Close Session: Create InventoryItems location=None & Update ShipmentLines]
    
    AA --> AC[Manager Resolves Exceptions & Confirms Close]
    AC --> AB
    AB --> AD([Session Completed])
```

---

## 2. Scan & Allocation Evaluation Decision Tree
Detailing the logical rules applied by the matching engine (`IntakeMatchingManager`) upon receiving a scan event.

```mermaid
graph TD
    Start[Raw Scan Event Ingested] --> Parse[Parse Barcode payload]
    Parse --> CheckSerial{Is serial expected on Part or entered?}
    
    CheckSerial -->|Yes| Dedupe{Duplicate composite_sn: part_id + serial in Session or DB?}
    Dedupe -->|Yes| ErrorDup[REJECT: Duplicate Serial Buzz Tone]
    Dedupe -->|No| ForceQty[Enforce Allocation Qty = 1]
    
    CheckSerial -->|No| DefaultQty[Set Quantity = Part.qty_per_scan]
    
    ForceQty --> TargetEval{Query Open ShipmentLines for SKU}
    DefaultQty --> TargetEval
    
    TargetEval -->|Count == 0| Unmanifested[Create unassociated ItemAllocation - Quarantine]
    TargetEval -->|Count == 1| DirectLink[Create ItemAllocation linked to ShipmentLine]
    TargetEval -->|Count > 1| AmbiguousPool[Create unassociated ItemAllocation - Staged]
    
    DirectLink --> CheckLineFull{Line Satisfied?}
    CheckLineFull -->|Yes| MarkLineComplete[Mark ShipmentLine Received Qty Summary Complete]
    CheckLineFull -->|No| LinePartial[Mark ShipmentLine Received Qty Summary Partial]
    
    AmbiguousPool --> ThresholdCheck{Staged Count >= Total Expected?}
    ThresholdCheck -->|No| AwaitMoreScans[Retain staged allocation: Emit UI Double-Beep]
    ThresholdCheck -->|Yes| CascadeFIFO[Execute FIFO Allocation Cascade across ShipmentLines]
    
    CascadeFIFO --> UpdateAllLines[Update Status on Affected ShipmentLines]
```

---

## 3. Quality Inspection Split Workflow
This diagram illustrates the user-triggered split action where a clerk manually inspects a batch/line of items and divides them into good and rejected (damaged/defective) quantities.

```mermaid
flowchart TD
    A[Operator opens scanned ItemAllocation in UI] --> B[Click 'Inspect & Split']
    B --> C[Enter Good Quantity Qg]
    C --> D[Enter Rejected/Damaged Quantity Qr]
    
    D --> E{Total Qg + Qr == Scanned Quantity?}
    E -->|No| F[Show validation error: Quantities must balance]
    F --> B
    
    E -->|Yes| G[Submit Split (HTMX POST)]
    G --> H[Server: BEGIN TRANSACTION]
    
    H --> I[Update original ItemAllocation: set quantity = Qg, condition = GOOD]
    H --> J[Create new sibling ItemAllocation: set quantity = Qr, condition = REJECTED]
    
    J --> K[Server: COMMIT TRANSACTION]
    K --> L[Server: Render updated HTML rows showing split breakdown]
    L --> M[UI: Update display table and play confirm tone]
```

---

## 4. Relational Entity-Relationship (ER) Schema
Visualizes the structure of the relational tables and keys used to build the intake receiving models.

```mermaid
erDiagram
    INTAKE_SESSION ||--o{ SCANNING_SESSION_SHIPMENT_ASSOCIATION : associates
    INTAKE_SESSION ||--o{ ITEM_ALLOCATION : logs
    
    SCANNING_SESSION_SHIPMENT_ASSOCIATION }o--|| SHIPMENT : references
    
    PART ||--o{ ITEM_ALLOCATION : identifies
    SHIPMENT_LINE ||--o{ ITEM_ALLOCATION : receives
    SHIPMENT ||--|{ SHIPMENT_LINE : defines

    INTAKE_SESSION {
        bigint id PK
        bigint operator_id FK "administration.User"
        bigint dock_location_id FK "administration.Location"
        timestamp started_at
        timestamp closed_at
        varchar status "DRAFT, ACTIVE, RECONCILING, CLOSED"
        varchar hardware_device_id
    }
    
    SCANNING_SESSION_SHIPMENT_ASSOCIATION {
        bigint id PK
        bigint intake_session_id FK
        bigint shipment_id FK "procurement.Shipment"
    }

    ITEM_ALLOCATION {
        bigint id PK
        bigint intake_session_id FK
        bigint shipment_line_id FK "procurement.ShipmentLine (null=True)"
        bigint part_id FK "parts.Part"
        decimal quantity
        varchar serial_number "null=True"
        varchar composite_sn "Index (part_id + serial_number)"
        varchar condition "GOOD, REJECTED"
        varchar intake_method "SCAN, MANUAL"
        timestamp created_at
    }

    PART {
        bigint id PK
        varchar part_number
        decimal qty_per_scan "Default 1.000"
        boolean sn_expected "Default False"
    }

    SHIPMENT_LINE {
        bigint id PK
        bigint shipment_id FK
        bigint part_id FK
        decimal quantity
        decimal quantity_accepted "null=True"
        boolean is_manually_adjusted "Default False"
    }
```
