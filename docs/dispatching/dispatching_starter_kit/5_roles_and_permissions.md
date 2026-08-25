# Roles and Permissions

Who does what in dispatching, and what each of them is allowed to reach.

---

## 0. The two systems, and why both are needed

This application separates **what you can do** from **what you can see**, and dispatching needs
both to be right.

| | **Roles** | **Data domains** |
| :--- | :--- | :--- |
| Answers | What actions may I perform? | Which records may I perform them on? |
| Built from | Permission groups, bundled into job profiles | Domain assignments |
| Example | "I may confirm reservations" | "…on Northern Depot assets" |

Neither derives from the other. A dispatcher with no domain assignment sees an empty queue; a
person with every domain but no dispatching role sees nothing at all.

**Every rule below is a role rule.** Wherever it says a dispatcher may confirm a booking, read
it as *"…on records within the domains they hold."*

---

## 1. Personas

Seven. Each is a real job someone does, not a permission bundle wearing a name.

### 1.1 Requester

*"I need a vehicle on Tuesday."*

Anyone in the organisation. The largest population by far, and the one whose experience decides
whether the module gets used or worked around.

| | |
| :--- | :--- |
| **Wants** | To state a need and find out whether it will be met |
| **Does** | Raises dispatches, states requirements, adds files and comments, tracks progress |
| **Never** | Confirms a booking, plans a job, records an expense, rejects anything |
| **Sees** | Their own dispatches, plus anything in their domains |
| **Friction to avoid** | Filling a long form to book a single vehicle. The light path exists for this person |

### 1.2 Self-service user

*"I'm picking up the truck now."*

A requester at the moment of handover. Not a separate person — a separate **situation**, and
worth naming because it is the one moment a casual user must not be blocked.

| | |
| :--- | :--- |
| **Wants** | To take and return an asset without finding a dispatcher |
| **Does** | Self-service checkout and return, records condition and notes, adds photos |
| **Never** | Verifies their own handover. That is the dispatcher track, and the whole point of keeping two |
| **Sees** | Bookings where they are the accountable person |

### 1.3 Dispatcher

*"I decide which asset goes where."*

The operational core. Everything else exists to feed this person good information.

| | |
| :--- | :--- |
| **Wants** | To clear the queue, meet needs, avoid double-booking |
| **Does** | Reviews and plans dispatches, creates and confirms bookings, assigns crew, records expenses, verifies handover and return, records meter readings, rejects what cannot be met |
| **Never** | Commits template revisions, edits the skills catalogue, deletes a booking that has been handed over |
| **Sees** | Everything in their domains |
| **Judgement calls they own** | Acknowledging a double-booking, deciding whether requirements are satisfied |

### 1.4 Dispatch manager

*"I decide how we do this kind of job."*

A dispatcher plus standard-setting. Not a supervisor — a **curator**.

| | |
| :--- | :--- |
| **Wants** | Consistency across jobs, and to improve the standard when something is learned |
| **Does** | Everything a dispatcher does, plus: edits working drafts and commits template revisions, copies and retires templates, manages the skills catalogue and per-person certifications |
| **Never** | Edits a committed template revision. Nobody can |
| **Sees** | Everything in their domains |

### 1.5 Shop lead

*"This truck is on a lift until Thursday."*

Maintenance-side. Their only interest in dispatching is taking assets out of circulation.

| | |
| :--- | :--- |
| **Wants** | An asset marked unavailable so nobody promises it |
| **Does** | Creates and confirms **maintenance-type** bookings, releases them when work finishes |
| **Never** | Touches dispatches, expenses, or non-maintenance bookings |
| **Sees** | Bookings on assets in their domains |
| **Note** | Nothing checks this against maintenance records, in either direction — [3_asset_reservations.md](3_asset_reservations.md) §6.1 |

### 1.6 Fleet manager

*"How much of our capacity went to rentals last quarter?"*

Read and report. Changes nothing.

| | |
| :--- | :--- |
| **Wants** | Utilisation, cost, and service-quality figures |
| **Does** | Reads everything, runs reports, exports |
| **Never** | Creates, edits, confirms, or cancels anything |
| **Sees** | Everything in their domains, including cancelled and rejected records |

### 1.7 Store keeper

Not a dispatching persona at all — listed because dispatching **feeds** them.

Material demands raised by a dispatch appear in the shared demand queue they already work from.
They need **no dispatching permission whatsoever**. If they do, the demand hub integration has
been built wrong.

---

## 2. Permission groups

Permission groups are **atomic bundles tied to one feature**, never to a job title. Roles bundle
them; users only ever receive them through a role.

| Permission group | Grants |
| :--- | :--- |
| **Dispatch — Raise** | Create a dispatch, edit own while editable, submit, cancel own, comment, attach files |
| **Dispatch — Plan** | View the queue, take a dispatch under review, request fixes, set priority, move it through planning |
| **Dispatch — Reject** | Formally refuse a dispatch with a reason |
| **Dispatch — Complete** | Mark a dispatch completed; cancel any dispatch |
| **Reservation — Book** | Create tentative bookings, cancel own tentative bookings |
| **Reservation — Confirm** | Promote tentative to confirmed, cancel confirmed bookings, acknowledge conflicts |
| **Reservation — Self Service** | Checkout and return as the accountable person |
| **Reservation — Verify** | Dispatcher-side handover and return verification, condition and meter recording |
| **Reservation — Maintenance Hold** | Create and release maintenance-type bookings only |
| **Expense — Record** | Add, edit, commit, complete, and cancel expenses; attach files and comment |
| **Template — Author** | Open and edit a working draft, discard it, copy a template into a new lineage |
| **Template — Commit** | Commit a working draft as a new revision; retire and reinstate a lineage |
| **Skills — Catalogue** | Manage the skills catalogue |
| **Skills — Certify** | Record and revoke a person's skill certifications |
| **Dispatching — Read** | Read-only access to every dispatching record |

### 2.1 Two splits worth defending

**Book and Confirm are separate.** This is what makes the light path safe to hand to everyone.
Placing a tentative claim is low-stakes and reversible; confirming commits capacity and can
override a conflict. Merging them would force a choice between a light path nobody can use and
one anybody can abuse.

**Author and Commit are separate.** A working draft lives in one person's session and affects
nobody. Committing changes what everyone in the domain is offered from that moment on. Different
levels of trust, even when the same person usually holds both.

---

## 3. Roles

| Role | Permission groups |
| :--- | :--- |
| **Requester** | Dispatch — Raise · Reservation — Book · Reservation — Self Service |
| **Dispatcher** | Dispatch — Plan · Dispatch — Reject · Dispatch — Complete · Reservation — Confirm · Reservation — Verify · Expense — Record · Dispatching — Read |
| **Dispatch Manager** *(child of Dispatcher)* | Template — Author · Template — Commit · Skills — Catalogue · Skills — Certify |
| **Shop Lead** | Reservation — Maintenance Hold |
| **Fleet Manager** | Dispatching — Read |

Conventions this follows: a user may hold several roles and receives the union; permission groups
reach users only through roles; a child role adds to its parent and shares no group with it —
which is why Dispatch Manager lists only the four groups Dispatcher does not already carry.

**Everyone gets Requester.** It should be part of whatever baseline every employee receives.
A dispatching module only reachable by dispatchers has failed.

**Dispatcher does not include Requester.** Dispatchers raise dispatches too, so in practice they
hold both roles. Keeping them separate means "can plan" and "can raise" stay independently
assignable — a fleet manager who occasionally raises a dispatch should not inherit planning
rights to get it.

---

## 4. Endpoint scoping

Each screen declares what it requires. Two kinds of check, and both apply:

1. **The permission gate** — does this user hold the required permission group?
2. **The domain filter** — is this record inside a domain they hold?

Passing the first and failing the second is a **404, not a 403**. A user who may not see a
record should not learn it exists.

### 4.1 Dispatch screens

| Screen | Requires | Notes |
| :--- | :--- | :--- |
| My dispatches | Dispatch — Raise | Own records only, regardless of domain breadth |
| Create / edit dispatch | Dispatch — Raise | Edit blocked once intent is locked |
| Submit | Dispatch — Raise | Own record only |
| Dispatcher queue | Dispatch — Plan | Domain-filtered |
| Review and plan | Dispatch — Plan | |
| Request fixes | Dispatch — Plan | |
| Reject | Dispatch — Reject | Reason required |
| Mark completed | Dispatch — Complete | |
| Cancel own dispatch | Dispatch — Raise | Only before planning starts |
| Cancel any dispatch | Dispatch — Complete | Cascades to bookings and unissued demands |
| Comment, attach files | Dispatch — Raise **or** Dispatch — Plan | Anyone who can see it can discuss it |

### 4.2 Reservation screens

| Screen | Requires | Notes |
| :--- | :--- | :--- |
| Asset calendar | Dispatching — Read **or** Reservation — Book | Availability must be widely visible or nobody can self-serve |
| Create booking | Reservation — Book | Always lands tentative |
| Confirm booking | Reservation — Confirm | |
| Acknowledge a conflict | Reservation — Confirm | Recorded with the acknowledger's name |
| Cancel tentative | Reservation — Book | Own bookings only |
| Cancel confirmed | Reservation — Confirm | Reason required |
| Self-service checkout / return | Reservation — Self Service | **Accountable person only** — §4.5 |
| Verify handover / return | Reservation — Verify | Never the same person as the self-service actor |
| Record meter readings | Reservation — Verify | |
| Create maintenance hold | Reservation — Maintenance Hold **or** Reservation — Confirm | Type forced to maintenance for the former |
| Release maintenance hold | Reservation — Maintenance Hold **or** Reservation — Confirm | |
| Delete booking | Reservation — Confirm | Only before any handover |

### 4.3 Expense screens

| Screen | Requires |
| :--- | :--- |
| Add, edit, commit, complete expense | Expense — Record |
| Cancel expense | Expense — Record — reason required |
| Attach files, comment | Expense — Record |
| View expenses | Dispatching — Read **or** Expense — Record |

### 4.4 Template and skills screens

| Screen | Requires | Notes |
| :--- | :--- | :--- |
| Template picker, when raising a dispatch | Dispatch — Raise | Head revisions only, domain-filtered |
| Template list and detail | Template — Author **or** Dispatching — Read | Head revisions by default |
| Revision history | Template — Author **or** Dispatching — Read | |
| Open and edit a working draft | Template — Author | Session-held. Writes nothing |
| Discard a working draft | Template — Author | Clears the session |
| Copy to new template | Template — Author | Seeds a draft into a new lineage |
| **Commit a revision** | **Template — Commit** | Change note required. Refused on a stale head |
| Retire / reinstate lineage | **Template — Commit** | Reason required |
| Skills catalogue | Skills — Catalogue | |
| Person's certifications | Skills — Certify | |
| My own certifications | *authenticated* | Everyone may see their own |

### 4.5 Rules the permission system cannot express

Three constraints that are not about *who you are* but about *your relationship to this
particular record*. They belong in the control layer, checked on every write.

| Rule | Why |
| :--- | :--- |
| Self-service checkout and return require being the **accountable person** on that booking — *or* a **dispatch manager** acting on their behalf | Holding the permission is not enough. It is a statement about this asset and this person. See §4.6 for the one exception |
| The verifier must not be the self-service actor | Two-track handover exists to catch discrepancies. One person doing both defeats it |
| Intent edits are blocked once a dispatch is planned, alternately resolved, or rejected | [2_dispatch.md](2_dispatch.md) §10. Time-based, not identity-based |

### 4.6 The manager override on the user track

**Amended during the reservation UI build.** The original rule was
accountable-person-only, with no exception. It is relaxed to: *the accountable
person, or a dispatch manager recording on their behalf.*

**Why.** A manager standing at the gate with a driver who has no phone must be able to
record what that driver reported. Under the strict rule the only ways through were to
reassign the booking or to log in as the driver — the first falsifies who was
accountable, the second is worse. Neither is better than an honest attributed entry.

**What still holds.** The entry is written under the *manager's* user id, not the
driver's, so the record says who typed it. And `VerifierDistinctPolicy` is unchanged:
having filed the user side, that manager may no longer verify it. The constraint the
two-track design actually depends on — that two different people sign the two tracks —
survives intact. The accountable-person rule was protecting attribution, and attribution
is what the override preserves.

**Where it lives.** `AccountablePersonPolicy.check(..., on_behalf=True)`. The guard only
honours the flag; the presentation layer decides who qualifies, via
`dispatching_access.can_self_service_for()`.

> **Dispatch Manager has no permission of its own.** It is defined in §3 purely as a
> bundle, so the code identifies it by **Template — Commit** — the one group no other
> role holds. That is a marker, not a meaning. If a dedicated *Reservation — Administer*
> permission is ever added, point `is_dispatch_manager()` at it and delete the note.

Enforcing these through permissions would mean per-row permission entries — which this
application deliberately does not do.

---

## 5. Business rules

| # | Rule |
| :--- | :--- |
| R1 | Permission groups reach users only through roles |
| R2 | Every rule here is bounded by the domains the user holds |
| R3 | Permission granted but domain denied is a 404, not a 403 |
| R4 | Booking and confirming are separate permissions |
| R5 | Authoring a draft and committing a revision are separate permissions |
| R6 | Self-service handover requires being the accountable person on that booking |
| R7 | The handover verifier must not be the person who performed self-service |
| R8 | Rejection requires the reject permission and a stated reason |
| R9 | Store keepers need no dispatching permission — demands reach them through the shared queue |
| R10 | Requester belongs in the baseline every employee receives |

---

## 6. Open questions

1. **Should a shop lead see dispatches at all?** Currently no. Knowing *why* an asset is wanted
   might help them prioritise a repair — but it widens a narrow, clean role.
2. **Read access for requesters beyond their own dispatches.** Seeing the depot calendar helps
   people self-serve sensibly. Seeing every dispatch in their domain may be more than they need.
3. **Does the self-service population need naming?** Today anyone with Requester can self-serve
   on their own bookings. If some assets require training to operate, that is a skill check on
   checkout — a real feature, not a permission.
