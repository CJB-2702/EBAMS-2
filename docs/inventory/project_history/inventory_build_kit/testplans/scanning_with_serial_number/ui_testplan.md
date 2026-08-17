# UI Test Plan: Scanning with Serial Number Prompt Workflow

## Success Criteria

1. [x] Operator scans a part configured to expect serial numbers.
2. [x] UI displays a pop-up dialog 'Enter Serial Number'.
3. [x] If serial is entered, system validates for duplicates.
4. [x] If serial is valid, allocation is created with serial attached, pop-up closes, flashes green.
5. [x] If skipped, allocation is created without serial, UI flashes amber, plays generic beep.
