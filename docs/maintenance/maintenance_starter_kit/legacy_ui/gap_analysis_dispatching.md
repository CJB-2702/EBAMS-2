# Dispatching gap analysis

Known differences between legacy Flask dispatching and EBAMS-2 Django port. Update this as you discover gaps during porting.

---

## Architecture changes (intentional divergences)

### No need to port
- **Debug/admin routes** (analytics dashboards, system stats) — if present in legacy but not in requirements, skip.
- **Deprecated endpoints** — routes marked as `# Legacy redirect` in code are stubs; the redirect target is the canonical page.

### Scope of work
This porting focuses on the **dispatcher workflow** and **user workflow**:
- Dispatcher view: request queue, dispatch creation, resource allocation
- User view: my requests, my checkouts, outcome assignment
- Alternative outcomes: contracts, reimbursements, rejects

Management features (skills, capabilities, etc.) are out of scope for phase 1 unless explicitly requested.

---

## Known missing features (phase 1)

### §1 Request Template Management

**Legacy page:** `/dispatching/requests/templates` (if present)  
**Status:** Deferred to phase 2

Pre-defined request templates with standard fields, asset types, personnel pools.

**Why deferred:** Requires UI for template builder; initial release accepts freeform requests only.

---

### §2 Calendar / Scheduling View

**Legacy page:** `/dispatching/calendar` or similar  
**Status:** Deferred to phase 2

Visual calendar/Gantt view of dispatches over time, with drag-and-drop rescheduling.

**Why deferred:** Requires calendar widget integration; list views with filter-by-date are sufficient for MVP.

---

### §3 Bulk Actions

**Legacy page:** Request list, select multiple + bulk status change  
**Status:** Deferred to phase 1 stretch

Multi-select checkboxes and "Reject all" / "Assign to dispatcher" actions on request list.

**Why deferred:** Complex workflow state validation; handle single-item actions first, then batch if time permits.

---

### §4 Advanced Reporting / Export

**Legacy page:** Any export-to-CSV, analytics dashboard  
**Status:** Out of scope for initial port

Reports on dispatch metrics, cost analysis, utilization rates.

**Why out of scope:** Analytics are secondary to operational workflow. Add if requested post-launch.

---

### §5 Mobile-optimized views

**Status:** Not planned; Bulma responsive grid is sufficient.

---

## Behavioral changes (intentional improvements)

### Double-booking policy enforcement
- **Legacy:** May have been advisory (warning only).
- **EBAMS-2:** Strict enforcement: cannot assign the same asset to overlapping time windows.
- **Impact:** Dispatch create/edit will fail and show a clear error if conflict is detected.

### Datetime handling
- **Legacy:** May use different timezone handling.
- **EBAMS-2:** All times stored in UTC; display converts to user's timezone (from profile).
- **Impact:** Datetimes in form inputs use `datetime-local`; backend interprets as user-local, stores as UTC.

### Outcome state machine
- **Legacy:** May allow any state transition.
- **EBAMS-2:** Strict state machine (Requested → Scheduled → Active → Completed).
- **Impact:** Buttons to move to next state are disabled if preconditions are not met; tooltip explains why.

### Permission model
- **Legacy:** May use Django groups; specific implementation unclear.
- **EBAMS-2:** Uses `dispatching_admin`, `dispatching_manager`, `dispatching_technician` groups.
  - Admins: full CRUD on all dispatches, outcomes, users.
  - Managers: create/edit dispatches, assign/manage outcomes for requests.
  - Technicians: view assigned dispatches, check out assets, update work status.
  - Requestors: view their own requests, see assigned dispatch details.

---

## Scope refinements (ask before porting)

### 1. Dispatch Scope parameter
Legacy may have "dispatch_scope" (e.g., "On-site", "Remote", "Mixed").
- **Decision:** Include in the model? Maps to what real-world concept?
- **Recommendation:** Keep it — low-effort filter, useful for categorizing requests.

### 2. Personnel Skills / Capability Matching
Legacy may auto-suggest or warn when assigning personnel lacking required skills.
- **Decision:** Enforce, warn, or ignore?
- **Recommendation:** Phase 1: warn only (skill lookup shows mismatch). Phase 2: enforce or suggest alternatives.

### 3. Request Approval Workflow
Legacy may require manager sign-off before dispatch creation.
- **Decision:** Is this required for EBAMS-2?
- **Recommendation:** Out of scope for MVP; direct dispatch creation from request is acceptable.

### 4. Outcome Cost Estimation
Legacy may show estimated vs. actual cost comparison.
- **Decision:** Track cost estimates on dispatch/contract/reimbursement?
- **Recommendation:** Out of scope for phase 1; add audit field if time permits.

---

## Testing gaps

### Manual testing checklist
- [ ] Create a request, assign to dispatcher
- [ ] Create a dispatch (happy path): assign asset + personnel, schedule
- [ ] Attempt double-booking: same asset, overlapping time → error
- [ ] Create alternative outcome (contract/reimbursement/reject)
- [ ] State transitions: request → dispatch → active → completed
- [ ] Cancel request mid-workflow
- [ ] View request/dispatch as technician vs. dispatcher (permission checks)
- [ ] Search and filter on each list view
- [ ] Pagination: navigate between pages

### Automated test coverage
- [ ] DispatchContext initialization from request
- [ ] DispatchStatusValidationPolicy: all state transitions
- [ ] DoubleBookingSpecification: overlapping asset assignments
- [ ] Control-layer verbs: create_dispatch, assign_person, etc.
- [ ] Guard functions: role checks, state guards

---

## Notes on porting process

1. **Start with the index and list views** — they have no complex state logic.
2. **Then detail/view pages** — read-only, easier to validate.
3. **Then create/edit forms** — state machine and policy enforcement.
4. **Finally, alternative outcomes** — share much of the dispatch scaffold.

Use the `DISPATCHING_PORT_PROMPT.md` template for each page porting task. One page per conversation to keep context focused.
