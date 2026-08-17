# Business Concept Definition: Automated Intake & Blind Receiving

This document describes the high-level business functionality, workflow goals, and user roles for the automated intake and blind receiving system. It focuses entirely on operational value and user interactions, leaving all technical database details out.

---

## 1. Primary User Personas

- **Dock Operator (Receiving Clerk):** The primary, high-volume user. They stand at the dock, open boxes, scan barcodes, manually enter quantities, and physically inspect/split items. Their priority is speed, minimal screen interaction, and immediate clear feedback (visual and auditory).
- **Inventory Manager:** The supervisor. They oversee the dock, resolve quarantined or discrepant items, review deficits, and sign off on completed intake sessions.

---

## 2. Core Capabilities & Features

### Capability 1: Intake Session Lifecycle
*   **Business Purpose:** Establishes a bounded workspace for a receiving run, linking the physical work to an operator, location, and device, ensuring full audit trails for everything received during that window.
*   **Workflow:**
    1. A **Dock Operator** starts a new intake session, selecting their dock bay location.
    2. They select the expected shipments to be processed in this session, which links those shipments to the session.
    3. The session remains active as the operator performs scans, allowing pausing and resuming.
    4. Upon completion or reconciliation, the session is locked and committed.

### Capability 2: Part-Level Configuration (Qty per Scan & Serial Expected)
*   **Business Purpose:** Streamlines receiving of bulk packages (e.g. screws in packs of 100) and configures serial tracking prompts on a per-part basis.
*   **Workflow:**
    1. Each part definition defines a **default quantity per scan** (defaults to 1, but can be set to 100, 50, etc.). When scanned, the system automatically registers that configured quantity.
    2. Each part definition defines whether a **serial number is expected**. If true, the system automatically pops up a "Enter Serial Number" prompt on the intake screen.
    3. The operator can skip the serial prompt if they wish. If they do input a serial number, the system verifies uniqueness. For most parts, this is false and no prompt occurs.

### Capability 3: Blind Receiving & Allocation
*   **Business Purpose:** Accelerates the ingestion process while reducing operator error. The operator does not need to look up which item belongs to which order line; they simply scan whatever physical item they hold, and the system dynamically routes it.
*   **Workflow:**
    1. The **Dock Operator** scans a barcode.
    2. The system parses the barcode to extract the part number and serial number (if provided).
    3. The system automatically creates an intake allocation entry:
        - **1-to-1 Match:** If only one open shipment line expects this part, the allocation is linked and marked received.
        - **N-to-M Ambiguous Match (FIFO):** If multiple shipment lines expect this part, allocations are staged in the session. Once the cumulative staged quantity matches the expected threshold, they are automatically allocated starting with the oldest shipment first.
        - **Unmanifested Quarantine:** If no shipment expects the part, the allocation is saved without a shipment line link (acting as quarantined).
    4. The intake allocation tracks whether it was logged via **scan** or **manual entry**.

### Capability 4: Quality Inspection & Split Workflow
*   **Business Purpose:** Isolates damaged goods immediately at the door, allowing the operator to split a single received batch into good and rejected quantities.
*   **Workflow:**
    1. After scanning or entering items, the operator can select an intake line.
    2. The operator manually splits the received quantity into a "good" quantity and a "rejected" quantity.
    3. The system records separate allocations (flagged as pristine vs. damaged). Damaged items are routed to an inspection/RMA queue upon session completion.

### Capability 5: Discrepancy Reconciliation & Procurement Hand-off
*   **Business Purpose:** Resolves mismatches between what was physically scanned and what was expected, and updates procurement paperwork.
*   **Workflow:**
    1. When scanning is complete, if there are unallocated items or unfilled expected quantities, the session enters a *Reconciling* state.
    2. The **Inventory Manager** can manually drag and drop unassigned allocations to target lines, override quantities, or accept short-shipments with notes.
    3. When the session is closed, the system writes the final accepted quantities directly to the Procurement shipment lines.
    4. If a user edits a shipment line directly in the Procurement UI (outside of an intake session), the main shipment line is flagged as **manually adjusted**; otherwise, it is assumed to be a summary of the linked intake session allocations.
    5. The received items are registered in the inventory system with **no location assigned** (ready for downstream put-away).
