# UI Test Plan: Auto Intake Workflow

## Success Criteria

1. [x] Operator can select dock location and hardware device.
2. [x] Operator can search and select an unfulfilled shipment.
3. [x] Lines for selected shipment correctly expand and display current allocations.
4. [x] Monotonic floor constraint enforced (cannot reduce accepted/rejected below existing).
5. [x] Quantity cap enforced (sum of target accepted and rejected cannot exceed line shipped quantity).
6. [x] Form submission generates precise incremental deltas for accepted and rejected items.
7. [x] Error messages are displayed properly for invalid quantities.
