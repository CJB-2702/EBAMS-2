# Dispatching page catalog

Card-by-card reference guide for porting dispatching pages from the legacy Flask app to EBAMS-2 Django.

**Source of truth:** the screenshot is authoritative. If prose and PNG disagree, the PNG wins — fix the prose.

---

## §1 Dispatching Index / Landing Page

**Route:** `/dispatching/`  
**Screenshot:** `00_dispatching_index.png`  
**Access:** Requires login + dispatching module role

The main entry point for the dispatching module. Displays navigation to dispatcher and user workflows.

### Cards
- Navigation portal links (Dispatcher Portal, My Requests, My Checkouts, etc.)
- Module-level documentation or quick-start guidance (if present)

### Actions
- Click-through links to dispatcher portal, user portals
- No form submissions on this page

---

## §2 My Requests

**Route:** `/dispatching/my-requests`  
**Screenshot:** `01_dispatching_my_requests.png`  
**Access:** Requires login

User view of their own dispatch requests (where `requested_for = current_user`).

### Cards
- **Filter bar:** Status, asset class, dispatch scope, outcome type, free-text search
- **Request list:** Paginated table/card grid showing:
  - Request ID, description, notes
  - Asset/subclass, location
  - Desired start/end, current status
  - Assigned person (if any)
  - Active outcome type (Dispatch/Contract/Reimbursement/Reject, if any)
- **Pagination:** Previous/next buttons

### Actions
- Click a request row to view details
- Filter/search to narrow list
- Pagination navigation

---

## §3 My Asset Checkouts

**Route:** `/dispatching/my-asset-checkouts`  
**Screenshot:** `02_dispatching_my_asset_checkouts.png`  
**Access:** Requires login

User view of dispatch assets they are planned for or have checked out.

### Cards
- **Filter bar:** Similar to My Requests (status, dispatch, etc.)
- **Checkout list:** Paginated list of dispatch assets where:
  - User is `planned_for` OR has checked the asset out
- **Pagination**

### Actions
- Click asset row to view details
- Checkout/return actions (if applicable)
- Filter/search

---

## §4 Dispatcher Portal (Dashboard)

**Route:** `/dispatching/dispatcher-portal`  
**Screenshot:** `03_dispatching_dispatcher_portal.png`  
**Access:** Requires login + dispatcher/manager role

Manager/dispatcher view with overview metrics and recent activity.

### Cards
- **Statistics/Metrics card:** 30-day, 7-day, currently active dispatch counts
- **Request Queue:** Pending (Requested status) requests awaiting initial review
  - List shows newest first (or by priority)
  - Limited to 20 items
- **Recent Requests:** Latest 10 requests (across all statuses)
- **My Upcoming Dispatches:** Next 5 dispatches created by current user,
  ordered by scheduled_start

### Actions
- Click request/dispatch to navigate to details
- Review/assign/create outcome workflow

---

## §5 Requests List

**Route:** `/dispatching/requests`  
**Screenshot:** `04_dispatching_requests_list.png`  
**Access:** Requires login

Dispatcher view: all dispatch requests, filterable.

### Cards
- **Filter bar:** Status, requested_for, asset class, dispatch scope, outcome type, search
- **Request table/cards:** Paginated list with same fields as My Requests
- **Pagination**

### Actions
- Click request row to view/edit
- Filter/search
- Bulk actions (if any)
- Create new request button

---

## §6 Request Detail View

**Route:** `/dispatching/requests/<request_id>`  
**Screenshot:** `05_dispatching_request_1_view.png`  
**Access:** Requires login

Full detail of a single dispatch request.

### Cards
- **Request header:** ID, status, dates, requester, requested_for person
- **Location and Asset info:** Where, what asset class/subclass
- **Description/Notes:** Freeform text, any special instructions
- **Active Outcome card:** Shows current active outcome (Dispatch/Contract/etc),
  or empty state with "No active outcome. Create one below."
- **Outcome history:** Cancelled/closed outcomes (if any)
- **Actions panel:** 
  - Create Dispatch button
  - Create Contract (alternative outcome)
  - Create Reimbursement
  - Create Reject
  - Cancel request (if state permits)

---

## §7 Dispatch Create / Edit

**Route:** `/dispatching/requests/<request_id>/outcome/dispatch`  
**Screenshot:** `06_dispatching_dispatch_create.png`  
**Access:** Requires login + dispatcher role

Form to create or edit a StandardDispatch outcome for a request.

### Cards
- **Dispatch header:** Request reference, status
- **Schedule card:** 
  - Scheduled start (datetime-local)
  - Scheduled end (datetime-local)
  - Actual start / actual end (if underway)
  - Duration computed display
- **Resource allocation card:**
  - Assigned person selector
  - Personnel roster (table): name, role/skills, availability
  - Assets needed (table): asset, capability, quantity
  - Consumables needed (table): part, quantity, unit cost
- **Metadata:**
  - Dispatch notes/instructions
  - Dispatch scope (if applicable)
- **State transitions / Actions:**
  - Save (update draft)
  - Move to next state (depends on current status: Scheduled → Active → Completed)
  - Cancel dispatch

### Actions & Validation
- Datetime input validation (start < end)
- Double-booking check (same asset, overlapping times)
- Availability warning for assigned person
- Required fields validation (scheduled_start, assigned_person, etc.)

---

## §8 Contract Outcomes List

**Route:** `/dispatching/outcomes/contracts`  
**Screenshot:** `07_dispatching_contract_list.png`  
**Access:** Requires login + dispatcher role

Alternative outcome type: requests resolved via a third-party contract.

### Cards
- **Filter bar:** Request status, contract type, outcome status
- **Contract list:** Paginated table showing:
  - Contract ID, request reference
  - Vendor/contractor name
  - Cost, terms
  - Outcome status (Proposed/Accepted/Closed)
- **Pagination**

### Actions
- Click contract to view/edit details
- Create new contract button
- Cancel/close contract

---

## §9 Reimbursement Outcomes List

**Route:** `/dispatching/outcomes/reimbursements`  
**Screenshot:** `08_dispatching_reimbursement_list.png`  
**Access:** Requires login + dispatcher role

Alternative outcome type: direct reimbursement to requestor.

### Cards
- **Filter bar:** Request status, reimbursement amount range, outcome status
- **Reimbursement list:** Paginated table showing:
  - Reimbursement ID, request reference
  - Amount, currency
  - Justification
  - Outcome status
- **Pagination**

### Actions
- Click to view/edit details
- Create new reimbursement
- Approve/deny/close reimbursement

---

## §10 Reject Outcomes List

**Route:** `/dispatching/outcomes/rejects`  
**Screenshot:** `09_dispatching_reject_list.png`  
**Access:** Requires login + dispatcher role

Alternative outcome type: request cannot be fulfilled; rejected with reason.

### Cards
- **Filter bar:** Request status, reject reason, outcome status
- **Reject list:** Paginated table showing:
  - Reject ID, request reference
  - Rejection reason
  - Notes
  - Outcome status
- **Pagination**

### Actions
- Click to view/edit details
- Create new reject
- Reopen request (reverse rejection)

---

## Shared patterns

### Empty states
- When a list has no items: "No [thing] yet." with a button to create one (if applicable).
- When a detail section is empty: "None." or "[Section name] not yet defined."

### Filters
- Always render even if empty; show "All" or default when no filter applied.
- Search box always present with placeholder "Search by [field list]…"
- Filter tags/chips show active filters; click to clear individual filters.

### Pagination
- Show current page, total count: "Page 2 of 5 (47 total)"
- Previous/Next buttons; disable if at boundary.
- Per-page selector (10, 20, 50) if applicable.

### State guards and validation
- When state transition is disallowed: show disabled button + tooltip explaining why.
- All datetime inputs use `datetime-local` format with browser parsing.
- Cost/amount fields use currency formatter (USD default).

### Responsive behavior
- On narrow viewport: stack filter bar vertically, collapse optional columns.
- Table text truncation with full-text in hover tooltips.

---

## Notes on porting

- The legacy app uses Flask templates with Jinja2; EBAMS-2 uses Django templates.
- Request/Dispatch/Outcome relationships are strict: one request → one active outcome at a time.
- State machine enforces valid transitions (see `docs/dispatching/state_machine.md`).
- All datetime inputs stored in UTC internally; display in user's timezone.
- Role-based access: dispatchers can create/edit dispatches; requestors can only view their own.
