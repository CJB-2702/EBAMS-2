# UI Test Plan: Scanning Non-Serialized Item (Qty=1) Workflow

## Success Criteria

1. [x] Operator can scan a standard item barcode.
2. [x] System automatically triggers POST scan request.
3. [x] Quantity for expected line is incremented by 1.
4. [x] UI flashes green screen indicator and plays confirmation chime.
5. [x] Line count correctly updates in the dashboard without full page reload (HTMX).
