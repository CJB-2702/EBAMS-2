# Design Drift

**The legacy application is the reference for screens, not for concepts.**

Its pages, layouts, and workflow sequence are being kept deliberately. Its data model is not.
This document lists every place the two now disagree, so that opening a legacy screen does not
quietly reintroduce a concept that has been removed.

**Use it like this:** before porting a legacy page, scan §2 for anything on that screen. If a
field, tab, or button appears there, the legacy version is wrong and the entry says what replaces
it.

---

## 1. Vocabulary

Terms whose meaning changed. The legacy word on the left will appear all over the old UI, its
routes, and its templates.

| Legacy term | Now | Note |
| :--- | :--- | :--- |
| Dispatch **request** | **Dispatch** | Same record. "Request" was a lifecycle stage wearing a second name |
| Dispatch *(the outcome record)* | **Asset reservation** | The word "dispatch" moved up to mean the whole job |
| Outcome | **Line item** | And there is no "selected" one — see §2.2 |
| Standard dispatch | **Asset reservation** | |
| Dispatch asset *(the per-asset line)* | **Asset reservation** | The two merged. One booking = one asset |
| Contract / Reimbursement *(two records)* | **Expense** *(one record, two types)* | |
| Reject *(an outcome record)* | Fields on the dispatch itself | |
| Requested part | **Material demand** | A real, issuable demand |
| Major location | **Data domain** | |
| Make/model | **Asset model** | Manufacturer is now separate |
| Resolved *(state)* | **Alternate Resolution** | And it means something narrower — §2.6 |
| Closed *(state)* | **Completed** | |

---

## 2. Structural drift

Each entry: what the legacy UI shows, what is true now, and what to do when porting.

### 2.1 A request and a dispatch are one record

**Legacy UI shows:** a request page and a separate dispatch page, with a "create dispatch from
request" action between them. Two IDs, two URLs, two headers for one job.

**Now:** one record, one page, one URL. What the legacy called "converting" is just attaching a
line item.

**When porting:** merge the two pages. Anything on the legacy dispatch page that describes the
*job* belongs on the dispatch; anything describing *an asset going out* belongs on that asset's
reservation. There is no conversion button.

→ [2_dispatch.md](2_dispatch.md) §1

---

### 2.2 Outcomes are gone

**Legacy UI shows:** an outcome selector — pick dispatch, contract, reimbursement, or reject —
and an "active outcome" panel showing the one chosen.

**Now:** a dispatch is a header with **line items**. Reservations and expenses are children. A
job can have two of our trucks *and* a hired flatbed at the same time. Nothing is selected.

**When porting:** delete the outcome selector. Replace the active-outcome panel with two lists —
reservations, and expenses. Both may be empty; both may be populated at once.

**Watch for:** the legacy "active outcome type / active outcome row" pointer appears in filters,
badges, and list columns across several screens. Every one of those needs rethinking as "what
line items does this job have", not "which outcome was picked".

→ [4_dispatch_line_items.md](4_dispatch_line_items.md) §2

---

### 2.3 A reservation is not an outcome, and it stands alone

**Legacy UI shows:** reservations only ever reachable through a request. No way to book an asset
without filing one.

**Now:** a reservation is a first-class booking — one asset, one window, one accountable person,
its own page, its own event, its own status. The dispatch link is **optional**.

**When porting:** this is the largest *addition*, and the legacy UI offers no model for it.
Booking screens reachable from the asset and from the calendar have no legacy equivalent and
must be designed fresh.

**The rule that decides which path a screen serves:**

> Just need the asset? → a reservation. Need a crew, material, or money spent? → a dispatch.

→ [3_asset_reservations.md](3_asset_reservations.md) §2

---

### 2.4 One booking covers exactly one asset

**Legacy UI shows:** a dispatch with an assigned asset field *and* a separate "dispatch assets"
list underneath — two places recording overlapping facts.

**Now:** one reservation per asset. A truck and trailer is two bookings. The singular
"assigned asset" field is gone; the per-asset list is the reservation list.

**When porting:** the legacy condition, checkout, and return fields that lived on the per-asset
line now live on the reservation itself. The dual dispatcher/user handover tracks are kept
exactly as legacy had them — that part was right.

→ [3_asset_reservations.md](3_asset_reservations.md) §4

---

### 2.5 Rejection moved onto the dispatch

**Legacy UI shows:** a rejection as one of four outcome records, with its own detail page.

**Now:** rejection reason, category, alternative suggestion, and resubmission fields are on the
dispatch itself. It is terminal.

**When porting:** the rejection screen becomes a dialog that sets fields on the dispatch. There
is no rejection record to open. Resubmission raises a **new** dispatch linked to the rejected
one — the legacy in-place resubmit is gone.

→ [2_dispatch.md](2_dispatch.md) §9

---

### 2.6 Status vocabulary

**Legacy UI shows:** `Requested`, `Submitted`, `UnderReview`, `FixesRequested`, `Planned`,
`Resolved`, `Cancelled` — plus a second, parallel `status` field that duplicates the first.

**Now:**

| Legacy | Now | Meaning changed? |
| :--- | :--- | :--- |
| Requested | **Draft** | Clearer — it is not yet in anyone's queue |
| Submitted, UnderReview, FixesRequested | unchanged | No |
| Planned | **Planned** | Narrowed: *at least one live reservation* |
| Resolved | **Alternate Resolution** | **Yes** — now means resolved *without* our assets |
| — | **Rejected** | New as a dispatch state |
| Closed | **Completed** | Terminal success |

**When porting:** the duplicate `status` field on requests is deleted; use the workflow state
alone. Status badges, filters, and queue groupings all need remapping — this is the drift most
likely to be ported by accident because the words look familiar.

→ [2_dispatch.md](2_dispatch.md) §8

---

### 2.7 Requested parts became real demands

**Legacy UI shows:** a "requested parts" list on the request, and a separate "consumables" list
on the dispatch, with a manual step between them.

**Now:** a dispatch raises **material demands** directly into the shared demand queue. They are
issuable the moment the dispatch is filed. There is no dispatching-private parts list.

**When porting:** the two legacy lists collapse into one, and it is a demand list, not a wish
list. Issuing goes through the shared issuance path — dispatching never records a stock movement
itself.

**Also:** cancelling a dispatch cancels its unissued demands, delegating to the demand side to
decide what that means.

→ [2_dispatch.md](2_dispatch.md) §7, §13

---

### 2.8 Requested asset became requested assets, and is informational

**Legacy UI shows:** a single "requested asset" picker that behaves like a real reference.

**Now:** a free-form list, **written once at request time and never updated**. It records what
was asked for. The reservations are the only authority on what is committed.

**When porting:** it renders as history — *"what was asked for"* — never as a live reflection of
what is booked. On submission the system takes tentative holds on the ones actually free and
skips the contested ones.

> **This is the field most likely to be "fixed" into a sync by a future contributor.** The stored
> field carries an explicit warning; do not remove it.

→ [2_dispatch.md](2_dispatch.md) §4

---

### 2.9 Major location became data domain

**Legacy UI shows:** a required major-location picker on requests and templates, and a location
dimension in filters and reports.

**Now:** no such record. Ownership scoping does the "whose / which part of the organisation"
job. Free-text location fields survive: activity location on the dispatch, origin and destination
on the reservation.

**When porting:** the picker disappears. Location-based filters become domain-based ones. Note
the legacy origin/destination fields are named as though they were references but were always
free text — they keep the behaviour and lose the misleading naming.

→ [models_review.md](models_review.md) §0.4

---

### 2.10 Contracts and reimbursements are one record

**Legacy UI shows:** two separate creation flows and two detail pages.

**Now:** one expense record with a type. Same fields, different payee.

**When porting:** one flow with a type toggle. The legacy contract page has a currency field and
the reimbursement page does not — **neither should**, see §2.11.

Expenses also gain their own activity thread: file uploads for invoices and claim forms, comments
for the narrative. History is tracked through comments, not a structured change log.

→ [4_dispatch_line_items.md](4_dispatch_line_items.md) §3

---

### 2.11 Cut features

Four things the legacy UI shows that are **deliberately not being built**. Porting any of them is
a mistake, not a completion.

| Cut | Legacy UI evidence | Why |
| :--- | :--- | :--- |
| **Multi-currency** | Currency field on the contract page | Nothing converts, reports on, or reconciles a second currency. The contract record was over-built, and the missing reimbursement currency was the honest one |
| **Asset capability expiry** | Certification and expiry dates on asset capability records; a "requires expiry" flag on the catalogue | Asset capabilities are has-or-has-not. **User skill expiry is unaffected and retained** — a lapsed CDL is a real fact |
| **Approval workflows** | — *(never existed in legacy either)* | Expenses record what happened; they are not requests for permission. Listed because it is the most likely thing to be "helpfully" added |
| **Overdue return handling** | — *(never existed)* | A booking past its end date does nothing. Explicitly a non-feature |

Also not built: sub-reservations, recurring bookings, crew or material on a reservation, and a
counterparty on rental and customer bookings.

→ [4_dispatch_line_items.md](4_dispatch_line_items.md) §7,
[3_asset_reservations.md](3_asset_reservations.md) §13

---

### 2.12 Meter readings belong to the asset

**Legacy UI shows:** meter fields stored on the dispatch's meter-read records, keyed by dispatch
and asset separately.

**Now:** meter history belongs to the asset and is written by anything that reads a meter. A
reservation holds **two references** — the reading at handover and the reading at return.

**When porting:** the meter capture form still appears at checkout and return, but it writes to
the asset's meter history and the reservation points at the result. Usage is the difference
between two readings that already exist, never a stored number.

→ [3_asset_reservations.md](3_asset_reservations.md) §7.3

---

### 2.13 Crew and consumables belong to the dispatch

**Legacy UI shows:** personnel and consumables as children of the dispatch-outcome record, which
is now the reservation.

**Now:** crew and material belong to the **dispatch**. A reservation carries exactly one
accountable person and nothing else. Three people and two vehicles belong to neither vehicle.

**When porting:** these panels move up to the dispatch page. A standalone reservation has no crew
panel and no material panel at all — needing either is the signal to raise a dispatch.

→ [3_asset_reservations.md](3_asset_reservations.md) §11

---

### 2.14 Template locking became real revisioning

**Legacy UI shows:** one template record, edited in place, locking read-only on first use. A
revision field almost nobody set, and bare `revision` / `copy` / `deprecated` POST actions with
no screens behind them.

**Now, three changes at once:**

| | |
| :--- | :--- |
| **A lineage, plus revision rows** | Two records. The lineage carries identity, ownership, retirement, and which revision is current. Each revision carries the title, pre-fill values, and the whole requirement manifest — and is **immutable** |
| **Editing happens in a session working draft** | Nothing reaches the database until commit. Four edits produce **one** revision, not four |
| **No locking** | Immutability makes it unnecessary. A template is never single-use |

**A dispatch points at a revision**, not at the lineage. That reference is permanent, because
that revision will never change.

**When porting:** the legacy template edit page becomes a **session-backed draft editor**. Its
save button is not a commit. Requesters only ever see head revisions.

**New screens:** the working-draft editor with unsaved state, commit-with-change-note, revision
history, and retire/reinstate with a reason. Copy-to-new-template has a legacy route already.

→ [1_dispatch_templates.md](1_dispatch_templates.md) §2, §3

---

### 2.15 Narration is new

**Legacy UI shows:** child records changing silently. Understanding a job means opening every
child and reconstructing the order.

**Now:** every meaningful line item change writes a plain-language note onto the dispatch's
timeline, automatically. Reservation **milestones** go up; reservation **detail** stays on the
reservation.

**When porting:** the dispatch page needs a timeline panel the legacy page does not have. It is
the highest-value single addition in the module.

→ [4_dispatch_line_items.md](4_dispatch_line_items.md) §5

---

## 3. What did not change

Equally load-bearing. Porting these faithfully is the goal.

| Kept | Note |
| :--- | :--- |
| **Page inventory and workflow sequence** | The dispatcher's habits carry over. The old interface is the specification |
| **The dual handover tracks** | Dispatcher-recorded vs user-reported, both kept, neither overwriting the other. Legacy got this right |
| **Real-world time vs paperwork time** | When the asset physically left is not when the form was submitted |
| **The requirement manifest** | Capabilities, skills, models, modifications — same four, same required/preferred flag. Configuration template is kept as a fact, but reattached: an optional attribute of a model requirement row, not a fifth standalone kind (see [1_dispatch_templates.md](1_dispatch_templates.md) §6.4) |
| **User skills and certifications** | Catalogue, per-person records, levels, certification numbers, **and expiry** |
| **Dispatch scope** | Now a fixed list: on-site, local, regional, national, international |
| **Template pre-fill fields and manifest** | Field-for-field unchanged. Only where they live — on a revision — and how they are edited is new |
| **Supersession by follow-up** | A changed need means a new record linked to the old one |

---

## 4. Traps

Ranked by how easily each slips through unnoticed.

| # | Trap | Guard |
| :--- | :--- | :--- |
| 1 | **Familiar status words with changed meanings.** `Resolved` → `Alternate Resolution` is a *narrowing*, not a rename | §2.6 |
| 2 | **Syncing requested assets from reservations.** Looks like an obvious bug fix. It destroys the field's purpose | §2.8 |
| 3 | **Porting the outcome selector** because every legacy screen has one | §2.2 |
| 4 | **Rebuilding the parts wish list** rather than raising demands | §2.7 |
| 5 | **Adding currency back** because the legacy contract page has one | §2.11 |
| 6 | **Adding capability expiry** because the legacy asset capability page has the fields | §2.11 |
| 7 | **Keeping the duplicate `status` field** because it is in every legacy list view | §2.6 |
| 8 | **Treating "dispatch" as the outcome record** when reading legacy routes and templates | §1 |
| 9 | **Putting crew or material on a reservation** because that is where legacy had them | §2.13 |
| 10 | **Building an approval step** because expenses commit money | §2.11 |
| 11 | **Persisting template drafts** because legacy edited rows directly. Four edits must produce one revision | §2.14 |

---

## 5. Where this leaves the legacy UI as a reference

| Use it for | Do not use it for |
| :--- | :--- |
| Page inventory — what screens exist | What a record contains |
| Layout, density, field ordering | Which fields exist |
| Workflow sequence and navigation | State names and transitions |
| What a dispatcher does in what order | Which table anything lives in |
| Filters, list columns, sort defaults | Filter *dimensions* — location and outcome type are gone |

**Rule of thumb:** trust the legacy UI on **shape**, never on **substance**.
