# UI Test Plan: Scanning N-to-M Ambiguous Staging & FIFO Cascade Workflow

## Success Criteria

1. [x] Operator scans bulk item expected across multiple open shipment lines.
2. [x] Item is initially staged and not immediately allocated to a line.
3. [x] Staged badge counter increments and UI plays double-beep.
4. [x] When sum of staged items matches threshold, FIFO cascade automatically links them to expected lines.
5. [x] UI marks corresponding lines as COMPLETE and plays triumph chime.
