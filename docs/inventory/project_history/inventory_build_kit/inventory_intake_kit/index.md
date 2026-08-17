# Automated Intake & Blind Receiving Starter Kit

This starter kit contains the planning and architectural design files for the Automated Intake & Blind Receiving system under the `inventory` application. 

The system enables blind receiving at dock locations, automated algorithmic matches (including 1-to-1 direct linking and N-to-M FIFO cascades using database-backed session tables), strict serial number verification (composite uniqueness on part + serial number), manual override reconciliation, quality inspections (specifically manual splits into good and rejected quantities), and direct hand-off integration with Procurement and Inventory.

---

## 1. Kit Documents

| Document | Purpose |
| :--- | :--- |
| **[questionnaire.md](questionnaire.md)** | The standard 20-question pre-kit questionnaire, completed and reviewed. Serves as the load-bearing business constraints baseline. |
| **[business_concept_definition.md](business_concept_definition.md)** | High-level capabilities, workflows, and user personas described in domain language (no database schema). |
| **[part_reconciliation_workflow.md](part_reconciliation_workflow.md)** | Dedicated document detailing the isolated part-by-part reconciliation sub-session engine, status gates, and manager resolution actions. |
| **[overages_and_shortages_guide.md](overages_and_shortages_guide.md)** | Operational guide explaining the Reconciliation Hub, shortage sign-offs, overage quarantines, and the HTMX allocation reassignment widget. |
| **[diagrams.md](diagrams.md)** | Consolidates all system process flowcharts, scan decision trees, quality inspection split workflows, and relational ER schemas. |
| **[sequence_diagrams.md](sequence_diagrams.md)** | Dedicated document containing 8 detailed user-perspective sequence diagrams showing HTMX fragment swaps, Django Views, and Control Layer interactions. |
| **[domain_model.md](domain_model.md)** | Database table schemas, field specifications, indexes, validation constraints, and the relational ER diagram (Mermaid). |
| **[control_layer_map.md](control_layer_map.md)** | Control layer architecture mapping out DTO Structs, primary Context entrypoints, dedicated sub-Managers, and sequence flow diagrams. |

---

## 2. Scope & Boundaries

### In-Scope
- **Intake Session Lifecycle:** Start, pause, resume, and commit sessions.
- **GS1-128 & 1D/2D Barcode Ingestion:** Scanning and parsing SKU/Part, serial number, condition.
- **Matching Engine:** Automated 1-to-1 linking, N-to-M FIFO cascade allocation, and quarantine routing for unmanifested arrivals.
- **Validation Constraints:** Composite part + serial uniqueness checks and quantity restrictions on serialized parts.
- **Part-Level Reconciliation Sessions:** Isolated task workflows per discrepant part number, locking the session until all part discrepancies are resolved.
- **Allocation Reassignment:** Shifting `ItemAllocation` links across expected shipment lines in the session using HTMX updates.
- **Manual Adjustment Mode:** Overriding lines (setting `is_manually_adjusted = True` on `ShipmentLine`), drag-and-drop allocations, and deficit/shortage logging.
- **Quality Inspection & Splits:** Manual split after scanning to divide a received line/count into good (pristine) and rejected (damaged/defective) quantities.
- **Procurement Integration:** Direct transactional update to Procurement's `ShipmentLine.quantity_accepted` on session close.
- **Inventory Injection:** Creating stock/inventory records with unassigned location (`location = None`) on session close.

### Out-of-Scope (Deferred to Downstream Builds)
- **Put-away & Bin Assignment:** Moving items from unassigned location (`None`) into specific rooms, aisles, shelves, or bins.
- **Cycle Counts & Warehouse Movements:** Inter-bin transfers, stock adjustments, and inventory reconciliation sheets.
- **Reservations & Issuance:** Gating inventory items for specific work orders or demands (except for the existing `PartIssue` model).
