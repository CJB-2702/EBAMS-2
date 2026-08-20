# Dispatching documentation — ready for porting

All reference materials for porting dispatching pages from legacy Flask to EBAMS-2 Django have been created.

---

## What's been prepared

### 1. Port Prompt Template
📄 **[DISPATCHING_PORT_PROMPT.md](DISPATCHING_PORT_PROMPT.md)**

Copy-paste template for starting a fresh conversation to port one dispatching page at a time. Includes:
- Dispatching-specific constraints (state machine, policy enforcement)
- Definition of done with dispatch-workflow checklist
- Example filled-in template
- References to all supporting materials

**Use this instead of the maintenance PORT_PROMPT when porting dispatching pages.**

### 2. Page Catalog
📄 **[page_catalog_dispatching.md](page_catalog_dispatching.md)**

Card-by-card reference guide for all 10 main dispatching pages:

1. **Dispatching Index** — Landing page with module navigation
2. **My Requests** — User's own dispatch requests with filters
3. **My Asset Checkouts** — User's assigned/checked-out assets
4. **Dispatcher Portal** — Manager dashboard with queue & metrics
5. **Requests List** — All requests, dispatcher view, filterable
6. **Request Detail** — Single request with active outcome
7. **Dispatch Create/Edit** — Form to allocate resources and schedule
8. **Contract Outcomes List** — Alternative outcome type
9. **Reimbursement List** — Alternative outcome type
10. **Reject List** — Alternative outcome type

Each entry describes:
- Route, template name, access control
- Card structure and fields
- Actions and user interactions
- Empty states and validation

---

### 3. Gap Analysis
📄 **[gap_analysis_dispatching.md](gap_analysis_dispatching.md)**

Known differences and scope decisions:

- **Architecture changes:** What's intentionally different from legacy
- **Known missing features (phase 1):** Templates, calendar view, bulk actions — deferred with reasons
- **Behavioral improvements:** Double-booking enforcement, timezone handling, state machine
- **Permission model:** Three roles (admin, manager, technician) vs legacy groups
- **Scope refinements:** Decisions needed on dispatch_scope, skills matching, approvals, cost tracking

---

### 4. Route Inventory
📄 **[route_inventory_dispatching.md](route_inventory_dispatching.md)**

Complete reference of all Flask routes, endpoints, verbs, query parameters:

**Navigation & Portals:**
- `/dispatching/` — index
- `/dispatching/my-requests` — user portal
- `/dispatching/my-asset-checkouts` — checkout tracking
- `/dispatching/dispatcher-portal` — manager dashboard

**Request Management:**
- `/dispatching/requests` — list all (dispatcher view)
- `/dispatching/requests/<id>` — detail view
- `/dispatching/requests/<id>/outcome/dispatch` — create/edit dispatch

**Alternative Outcomes:**
- `/dispatching/outcomes/contracts` — list, create, detail, update
- `/dispatching/outcomes/reimbursements` — list, create, detail, update
- `/dispatching/outcomes/rejects` — list, create, detail, update

**Management (Phase 2):**
- Skills, routes/capabilities — out of scope for MVP

**API/HTMX Fragments:**
- `/dispatching/api/*` — JSON endpoints (availability, autocomplete)
- `/dispatching/searchbars/*` — filter/search widgets
- `/dispatching/widgets/*` — reusable components

Each route includes:
- HTTP verb (GET/POST)
- Template name
- Access control requirements
- Query parameters and form fields
- Validation rules and policy enforcement
- State transitions and possible outcomes

---

### 5. Screenshots
📄 **[screenshots/_manifest_dispatching.json](screenshots/_manifest_dispatching.json)**

List of all screenshots to be captured (currently pending due to Flask login automation issues).

**What you need to do:**
1. Back up the legacy DB
2. Start the Flask app: `cd ~/REPOS/asset_management && nohup ./venv/bin/python3 app.py > /tmp/oldapp.log 2>&1 &`
3. Log in as `admin` / `admin987654321!`
4. Navigate to each URL in the manifest
5. Take full-page screenshots with playwright (see `capture_screenshots.py` for reference)
6. Save with filenames: `00_dispatching_index.png`, etc.

Once captured, update the manifest to mark them as complete.

---

## How to use this

### Starting a page port

1. Pick a page from **page_catalog_dispatching.md** (e.g., "My Requests")
2. Start a fresh conversation
3. Copy-paste the **DISPATCHING_PORT_PROMPT.md** template
4. Fill in the legacy URL (from page catalog) and new EBAMS-2 URL (current or 404)
5. Reference the corresponding screenshot and route details as you build

### Example flow

```
Port one page faithfully from the legacy dispatching app.

  NEW (EBAMS-2):  http://localhost:8000/dispatching/my-requests
  OLD (legacy):   http://127.0.0.1:5000/dispatching/my-requests

## Reference material

1. page_catalog_dispatching.md §2 — describes the My Requests page
2. screenshots/01_dispatching_my_requests.png — shows the actual layout
3. gap_analysis_dispatching.md — lists what's known to be missing
4. route_inventory_dispatching.md — lists all the GET/POST verbs and query params
```

Then follow the prompt template's checklist.

---

## Recommended porting order

1. **Navigation/Index** — lowest complexity, no state
2. **List views** — read-only, pagination only
3. **Detail views** — still read-only, but more fields
4. **Create/Edit forms** — introduces state machine and policy enforcement
5. **Alternative outcomes** — reuse dispatch scaffold

## Key constraints (always-apply)

From DISPATCHING_PORT_PROMPT.md and `.claude/CLAUDE.md`:

- **State machine first:** Understand valid transitions before building UI
- **Policy enforcement:** Double-booking, role permissions, status guards
- **F5 rule:** Every state survives a full-page reload
- **No modals for assignment:** Use in-page cards or dual listbox
- **One canonical URL per resource:** Use `?format=` for density/HTMX fragments
- **Cards render even when empty:** Always show the container with explicit empty state
- **Writes through control layer:** Never inline in entrypoint

---

## Next steps

- [ ] Capture missing screenshots (see `screenshots/_manifest_dispatching.json`)
- [ ] Port first page using DISPATCHING_PORT_PROMPT.md template
- [ ] Archive completed page to `docs/dispatching/project_history/`
- [ ] Update this summary with completed page count

---

## Files in this kit

```
maintenance_starter_kit/legacy_ui/
├── DISPATCHING_PORT_PROMPT.md         ← Start here for each page
├── page_catalog_dispatching.md         ← Page-by-page reference
├── gap_analysis_dispatching.md         ← Known gaps & decisions
├── route_inventory_dispatching.md      ← Route/endpoint reference
├── DISPATCHING_DOCUMENTATION_SUMMARY.md (this file)
├── screenshots/
│   ├── 00_dispatching_index.png       (pending)
│   ├── 01_dispatching_my_requests.png (pending)
│   ├── ... (8 more)
│   └── _manifest_dispatching.json     ← Update after capturing

Also updated:
├── portprompt.md                       ← Now points to DISPATCHING_PORT_PROMPT.md
```

---

**Questions or blockers?** Check DISPATCHING_PORT_PROMPT.md "Constraints" and gap_analysis_dispatching.md "Scope refinements" first. If a decision is needed, it's documented there with a recommendation.
