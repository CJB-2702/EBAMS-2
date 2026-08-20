# Dispatching route inventory

Complete list of Flask routes in the legacy dispatching module. Maps legacy POST verbs, HTMX fragments, state transitions, and query parameters for reference during porting.

Source: `/home/cb/REPOS/asset_management/app/presentation/routes/dispatching/`

---

## Navigation & Portal Routes

### GET /dispatching/
- **Name:** `index()`
- **Template:** `dispatching/navigation/index.html`
- **Access:** login_required + dispatching module role
- **Purpose:** Landing page with links to dispatcher and user portals
- **Query params:** none
- **Returns:** HTML page

### GET /dispatching/my-requests
- **Name:** `my_requests()`
- **Template:** `dispatching/navigation/user_portal.html`
- **Access:** login_required
- **Purpose:** User's own dispatch requests (where `requested_for = current_user`)
- **Query params:**
  - `page` (int, default 1)
  - `status` (str, optional: filter by DispatchRequest.status)
  - `asset_class_id` (int, optional)
  - `dispatch_scope` (str, optional)
  - `outcome_type` (str, optional: dispatch/contract/reimbursement/reject/none)
  - `search` (str, optional: search notes, location, names, subclass)
- **Returns:** HTML page with paginated list of DispatchContext objects

### GET /dispatching/my-asset-checkouts
- **Name:** `my_asset_checkouts()`
- **Template:** `dispatching/navigation/my_asset_checkouts.html`
- **Access:** login_required
- **Purpose:** Dispatch assets the user is planned_for OR has checked out
- **Query params:**
  - `page` (int, default 1)
  - `status`, `dispatch_id`, filters similar to requests list
- **Returns:** HTML page with paginated DispatchAsset list

### GET /dispatching/dispatcher-portal
- **Name:** `dispatcher_portal()`
- **Template:** `dispatching/navigation/dispatcher_portal.html`
- **Access:** login_required + dispatching_admin or dispatching_manager role
- **Purpose:** Manager dashboard with queue, recent requests, upcoming dispatches
- **Query params:** none
- **Returns:** HTML page with:
  - `recent_requests` (last 10 requests)
  - `queue_items` (status='Requested', first 20)
  - `metrics` (30-day, 7-day, active counts)
  - `my_upcoming_dispatches` (next 5, created by current_user, ordered by start)

### GET /dispatching/user-portal (deprecated)
- **Name:** `user_portal()`
- **Purpose:** Legacy redirect to `/dispatching/my-requests`
- **Returns:** 302 redirect

---

## Request Management Routes

### GET /dispatching/requests
- **Name:** `requests_list()`
- **Template:** `dispatching/requests/list.html`
- **Access:** login_required + dispatching module role
- **Purpose:** Dispatcher view of all requests, filterable
- **Query params:** Same as `/dispatching/my-requests`
- **Returns:** HTML page with list of all DispatchRequest records and filter options

### GET /dispatching/requests/<request_id>
- **Name:** `requests_detail()` (inferred from patterns)
- **Template:** `dispatching/requests/detail.html` (or similar)
- **Access:** login_required
- **Purpose:** Full detail of a single dispatch request
- **Query params:** none
- **Returns:** HTML page with DispatchRequest details, active outcome, history

### POST /dispatching/requests (implied)
- **Purpose:** Create new dispatch request
- **Form fields:**
  - `requested_for` (user ID or autocomplete)
  - `asset_class_id`
  - `asset_subclass_text`
  - `activity_location`
  - `desired_start`, `desired_end` (datetime-local)
  - `dispatch_scope` (optional)
  - `notes`
- **Returns:** Redirect to request detail, or form with validation errors

### POST /dispatching/requests/<request_id> (implied)
- **Purpose:** Update request (edit notes, dates, etc.)
- **Form fields:** Subset of create fields
- **Returns:** Redirect to request detail or form errors

---

## Dispatch (StandardDispatch) Outcome Routes

### GET /dispatching/requests/<request_id>/outcome/dispatch
- **Name:** `dispatch_create()`
- **Template:** `dispatching/dispatch_manifest/dispatch_create.html` (or similar)
- **Access:** login_required + dispatcher role
- **Purpose:** Form to create a StandardDispatch outcome for a request
- **Query params:**
  - `edit` (implied, if existing dispatch is being edited)
- **Returns:** HTML form with:
  - Scheduled start/end datetime inputs
  - Assigned person selector
  - Personnel roster (for availability check)
  - Asset requirements table
  - Consumables table
  - Dispatch notes
  - State action buttons (Save, Move to Active, Cancel)

### POST /dispatching/requests/<request_id>/outcome/dispatch
- **Purpose:** Save/create dispatch
- **Form fields:**
  - `scheduled_start`, `scheduled_end` (datetime-local)
  - `assigned_person_id`
  - `dispatch_notes`
  - (Implied) Asset/consumable line items via HTMX or form rows
- **Validation:**
  - scheduled_start < scheduled_end
  - DoubleBookingSpecification: check for overlapping assignments of same asset
  - assigned_person availability warning
- **Returns:** Redirect to dispatch detail, or re-render form with errors
- **State transitions:** Draft → Scheduled (or directly to Active if immediate)

### GET /dispatching/requests/<request_id>/outcome/dispatch/<dispatch_id>
- **Name:** `dispatch_detail()` (inferred)
- **Template:** `dispatching/dispatch_manifest/dispatch_detail.html`
- **Access:** login_required
- **Purpose:** View/edit existing dispatch
- **Returns:** HTML form same as GET `/outcome/dispatch` (create form, but pre-filled)

### POST /dispatching/requests/<request_id>/outcome/dispatch/<dispatch_id> (implied)
- **Purpose:** Update existing dispatch or trigger state transition
- **Action buttons:**
  - `save`: Update draft fields
  - `mark_active`: Move from Scheduled to Active (precondition: assigned_person, assets, scheduled_start reached)
  - `mark_completed`: Move from Active to Completed
  - `cancel`: Move to Cancelled (only from Scheduled/Active, not Completed)
- **Returns:** Redirect to dispatch detail or form errors

### GET /dispatching/dispatch-records
- **Name:** Inferred from file `dispatch_asset_records.py`
- **Purpose:** List of all DispatchAsset records (granular asset checkouts)
- **Returns:** Filtered list view

---

## Alternative Outcome Routes (Contracts, Reimbursements, Rejects)

### GET /dispatching/outcomes/contracts
- **Name:** `contracts()` (in `alternative_outcomes/contracts.py`)
- **Template:** `dispatching/outcomes/contracts_list.html`
- **Purpose:** List all contract outcomes
- **Query params:** Filters for request status, contract type, outcome status
- **Returns:** Paginated table of contracts

### GET /dispatching/outcomes/contracts/create
- **Purpose:** Form to create new contract outcome for a request
- **Form fields:**
  - `request_id` (or pre-filled from context)
  - `vendor_name`
  - `contract_type`
  - `cost`, `currency`
  - `terms`
  - `notes`
- **Returns:** HTML form

### POST /dispatching/outcomes/contracts/create
- **Purpose:** Save new contract
- **Returns:** Redirect to contract detail or form errors

### GET /dispatching/outcomes/contracts/<contract_id>
- **Purpose:** View/edit contract detail
- **Returns:** HTML form (detail view)

### POST /dispatching/outcomes/contracts/<contract_id>
- **Purpose:** Update contract or transition outcome status (Proposed → Accepted → Closed)
- **Returns:** Redirect to contract detail

### GET /dispatching/outcomes/reimbursements
- **Name:** `reimbursements()`
- **Template:** `dispatching/outcomes/reimbursements_list.html`
- **Purpose:** List all reimbursement outcomes
- **Returns:** Paginated table

### POST /dispatching/outcomes/reimbursements/create
- **Purpose:** Create new reimbursement
- **Form fields:**
  - `request_id`
  - `amount`, `currency`
  - `justification`
  - `notes`
- **Returns:** Redirect or form errors

### GET /dispatching/outcomes/rejects
- **Name:** `rejects()`
- **Template:** `dispatching/outcomes/rejects_list.html`
- **Purpose:** List all reject outcomes
- **Returns:** Paginated table

### POST /dispatching/outcomes/rejects/create
- **Purpose:** Create new reject outcome
- **Form fields:**
  - `request_id`
  - `rejection_reason`
  - `notes`
- **Returns:** Redirect or form errors

---

## Management Routes (Phase 2)

### GET/POST /dispatching/management/skills
- **Name:** `skills` (in `management/skills.py`)
- **Purpose:** Manage dispatch personnel skills and qualifications
- **Status:** Out of scope for initial MVP port

### GET/POST /dispatching/management/routes
- **Name:** `routes` (in `management/routes.py`)
- **Purpose:** Manage dispatch route templates or capability definitions
- **Status:** Out of scope for initial MVP port

---

## API / Fragment Routes (HTMX support)

### GET /dispatching/api/* (inferred from `api.py`)
- **Purpose:** JSON endpoints for dynamic data loading, autocomplete, validation
- **Likely endpoints:**
  - `/dispatching/api/personnel-availability?start=...&end=...` (check availability)
  - `/dispatching/api/asset-capabilities?asset_id=...` (list required capabilities)
  - `/dispatching/api/user-autocomplete?q=...` (search for users to assign)
- **Returns:** JSON

### GET /dispatching/searchbars/* (inferred from `searchbars.py`)
- **Purpose:** HTMX endpoint fragments for search/filter components
- **Returns:** HTML fragment (table rows, filter widgets, etc.)

### GET /dispatching/widgets/* (inferred from `widgets.py`)
- **Purpose:** Reusable HTMX widget fragments
- **Likely widgets:**
  - Personnel roster table (for dispatch create/edit)
  - Asset requirements table
  - Consumables table
- **Returns:** HTML fragment

### GET /dispatching/event-stubs/* (from `event_stubs.py`)
- **Purpose:** Event/event-component integration for dispatching workflow
- **Returns:** HTML or JSON (out of scope for phase 1)

---

## State Transitions & Policies

### DispatchRequest Status Values
- `Requested` — Initial state, awaiting dispatcher review
- `Assigned` — Dispatcher assigned; awaiting outcome
- `Active` — Outcome is active (dispatch underway)
- `Completed` — Outcome completed successfully
- `Cancelled` — Request cancelled

### StandardDispatch Status Values
- `Draft` — Being created, not yet scheduled
- `Scheduled` — Start date in future, resources allocated
- `Active` — Underway (actual_start <= now)
- `Completed` — Finished (actual_end set)
- `Cancelled` — Cancelled (can happen from Scheduled or Active)

### Alternative Outcome Status Values (Generic)
- `Proposed` — Initial
- `Accepted` — Approved by requester or manager
- `Closed` — Completed or finalized
- `Cancelled` — Rejected or withdrawn

### Policy Enforcement (Control Layer)
- **DoubleBookingSpecification:** Cannot assign same asset to two dispatches with overlapping time windows. Checked on dispatch save.
- **DispatchStatusValidationPolicy:** Validates allowed state transitions (e.g., can only mark Active if start_time <= now, can only mark Completed if end_time <= now).
- **Role guards:** Only dispatching_admin/manager can create/edit dispatches; only assigned technician or admin can mark complete.

---

## Query Parameters Summary

### Common filters across list routes
- `page` (int, default 1)
- `status` (str, optional)
- `search` (str, optional, searches multiple fields)
- `asset_class_id` (int, optional)
- `dispatch_scope` (str, optional: On-site, Remote, Mixed)
- `outcome_type` (str, optional: dispatch, contract, reimbursement, reject, none)
- `requested_for` (user ID, optional, dispatcher view only)

### Date/time inputs
- All datetime inputs use HTML `datetime-local` type (format: `YYYY-MM-DDTHH:MM`)
- Stored in database as UTC; display converts to user timezone

---

## Notes for porting

1. **One outcome at a time:** A DispatchRequest can have only one active outcome. Creating a new outcome for a request with an active outcome requires canceling the old one first.
2. **Cascade:** Canceling a request cancels its active outcome (if any).
3. **Audit columns:** All resources should have `created_at`, `updated_at`, `created_by_id`, `updated_by_id`.
4. **F5 rule:** All URLs and state must survive a full-page reload (HTMX fragments are on top, not required for F5).
5. **No parallel fragment routes:** A single canonical URL per resource; use `?format=htmx-<name>` for fragment requests, not separate `/xyz-fragment` routes.
