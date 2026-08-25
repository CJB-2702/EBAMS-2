# Build Phase 2 — Control Layer

Every write verb, guard, and policy in the dispatching module. Built in full, including the
parts phase 3's screens do not touch.

---

## 0. The stance: rebuild, do not port

> **Write the control layer from the design documents. Use the legacy control layer as an
> inventory of operations, never as source to translate.**

This matters more here than in phase 1, because the legacy control layer *looks* portable. It
uses almost the same vocabulary — `Context`, `Manager`, `Handler`, `Factory`, `Struct`,
`Policy`, `StateMachine`, `Narrator`. That similarity is a trap. The names match; the concepts
underneath have changed.

**Of legacy's eight policies, three enforce rules that no longer exist:**

| Legacy policy | Fate |
| :--- | :--- |
| `active_pointer.py` | **DEAD.** There is no active-outcome pointer |
| `outcome_uniqueness.py` | **DEAD.** Multiple line items are the normal case |
| `parts_availability.py` | **DEAD.** Availability is the demand hub's business, not dispatching's |

Porting those would reintroduce the exact concepts documents 3 and 4 removed.

### 0.1 What legacy is still good for

| Use it for | Do not use it for |
| :--- | :--- |
| **Operation inventory** — what verbs a dispatcher needs. Legacy is a working system; its file list is a decent checklist | Any control flow |
| **The dual-track checkout semantics** — `checkout_manager.py` got this right | Its structure. Legacy instantiates it *from the model* |
| **Operational vocabulary** — condition values, personnel roles, rejection categories | State machines. All the states changed |
| **Search and calendar surface** — what dispatchers filter and view by | Query implementation. Different ORM, different scoping |

---

## 1. Reference material

### 1.1 Specification — the authority

| Document | Supplies |
| :--- | :--- |
| [2_dispatch.md](2_dispatch.md) | Lifecycle §8, intent lock §10, rejection §9, demands §7, cancellation §13 |
| [3_asset_reservations.md](3_asset_reservations.md) | Lifecycle §9, conflicts §10, handover §7.2, promotion §11.1 |
| [4_dispatch_line_items.md](4_dispatch_line_items.md) | Expense statuses §4, **narration §5** |
| [1_dispatch_templates.md](1_dispatch_templates.md) | Revision rules §3, copy §4, retirement §5, instantiation §7 |
| [5_roles_and_permissions.md](5_roles_and_permissions.md) | **§4.5** — the three rules permissions cannot express. Guards |
| [build_phase_1_models.md](build_phase_1_models.md) | What exists to operate on |
| [application_map.md](application_map.md) | Legacy route inventory — the operation checklist referenced in §0.1 |

### 1.2 Legacy — inventory only

Full paths under `/home/cb/REPOS/asset_management/app/business/dispatching/`:

| Legacy file | Verdict |
| :--- | :--- |
| `context.py` — `DispatchContext` | **DISCARD, rebuild.** Held request + event + outcomes. The shape it fronts no longer exists |
| `state_machine.py` | **DISCARD, rebuild.** Every state changed. Read once for the transition *idea*, then close it |
| `outcome_manager.py` | **DELETE. No replacement.** Picked and swapped the active outcome |
| `base_outcome_handler.py` | **DELETE. No replacement** |
| `alternative_outcomes/contract_handler.py` | **DISCARD.** Merges into one expense manager |
| `alternative_outcomes/reimbursement_handler.py` | **DISCARD.** Merges into the same |
| `alternative_outcomes/reject_handler.py` | **DELETE.** Rejection is a verb on the dispatch |
| `narrator.py` | **DISCARD, rebuild much larger.** Narration is a headline feature now, not a side effect |
| `full_request_struct.py` | **DISCARD, rebuild.** Useful as a checklist of what a detail page assembles |
| `errors.py` | **DISCARD.** House exception conventions apply |
| `dispatch_manifest/checkout_manager.py` | **DISCARD, rebuild — but READ IT FIRST.** The dual-track semantics are correct and subtle. Re-derive them at your peril |
| `dispatch_manifest/dispatch_handler.py` | **DISCARD.** Becomes reservation verbs |
| `dispatch_manifest/dispatch_manifest_struct.py` | **DISCARD** |
| `dispatch_manifest/dispatch_meter_read_service.py` | **DELETE.** Meter reads write to asset meter history now |
| `request_manifest/request_builder.py` | **DISCARD, rebuild** |
| `request_manifest/request_manager.py` | **DISCARD, rebuild** |
| `request_manifest/request_manifest_editor.py` | **DISCARD, rebuild.** Parts requirement becomes a demand link |
| `request_manifest/request_manifest_struct.py` | **DISCARD, rebuild** |
| `template_request/template_manager.py` | **DISCARD, rebuild** |
| `template_request/template_revision.py` | **DISCARD ENTIRELY.** Revisioning is redesigned from the ground up — lineage header plus revisions, session-held drafts. This file is the *problem*, not the pattern |
| `template_request/template_manifest_struct.py` | **DISCARD, rebuild** |
| `template_request_manifest/template_manifest_struct.py` | **IGNORE.** Duplicate of the above — legacy has both |
| `details_types/skills/skill_manager.py` | **DISCARD, rebuild.** Closest to a straight rebuild |
| `details_types/skills/dispatch_skill_factory.py` | **DISCARD, rebuild** |
| `details_types/skills/dispatch_user_skills_struct.py` | **DISCARD, rebuild** |
| `details_types/capabilities/*` — 3 files | **DELETE. No replacement.** Asset capabilities are owned by `assets` |
| `policies/double_booking.py` | **DISCARD, rebuild at reservation level.** Concept survives, scope changes |
| `policies/intent_lock.py` | **DISCARD, rebuild.** Concept survives, trigger states change |
| `policies/manifest_uniqueness.py` | **REPLACED BY A CONSTRAINT.** Phase 1 §5 |
| `policies/asset_dispatchability.py` | **DISCARD, rebuild** as availability |
| `policies/dispatch_status_validation.py` | **DISCARD, rebuild.** New states |
| `policies/active_pointer.py` | **DELETE. Concept removed** |
| `policies/outcome_uniqueness.py` | **DELETE. Concept removed** |
| `policies/parts_availability.py` | **DELETE.** The demand hub owns this |

Read-side, under `/home/cb/REPOS/asset_management/app/intermediate/dispatching/`:

| Legacy file | Verdict |
| :--- | :--- |
| `asset_calendar_service.py` | **DISCARD, rebuild** as a search tool. Now queries reservations directly |
| `dispatcher_calendar_service.py` | **DISCARD, rebuild** |
| `my_calendar_service.py` | **DISCARD, rebuild** |
| `dispatch_checkout_query_manager.py` | **DISCARD, rebuild** |
| `dispatch_filtered_list.py` | **DISCARD, rebuild.** Drop outcome-type and location filter dimensions |
| `dispatching_asset_service.py` | **DISCARD, rebuild** |
| `personnel_select_card.py` | **DISCARD, rebuild** |
| `template_search_tool.py` | **DISCARD, rebuild.** Head revisions only |

### 1.3 EBAMS-2 patterns to copy

| Pattern | Path |
| :--- | :--- |
| Context as the caller-facing façade | `app/maintenance/control_layer/maintenance_context.py` |
| Orchestrator spanning apps | `app/maintenance/control_layer/maintenance_orchestrator.py` |
| Guard | `app/maintenance/control_layer/guards/maintenance_completion_guard.py` |
| Read struct | `app/maintenance/control_layer/domain_structs/maintenance_detail_struct.py` |
| Demand hub interaction | `app/maintenance/control_layer/part_demand_manager.py` |
| **Session-backed draft** | `app/maintenance/control_layer/adapters/template_builder_session_adapter.py` |
| Layer rules | `harness/Architecture/layer_rules.md` |
| Suffix vocabulary | `harness/Architecture/patterns/oop_control_patterns.md` |

**The demand-hub boundary is the one to study.** Dispatching raises and cancels demands the same
way maintenance does, and never writes stock movements itself.

---

## 2. Build order

Dependency order, not importance. Each step is usable before the next exists.

### Step 1 — Skills

No dependencies. Smallest complete slice; a good place to settle house conventions.

| Component | Does |
| :--- | :--- |
| `DispatchSkillManager` | Create, edit, deactivate catalogue entries |
| `UserSkillManager` | Certify, update, revoke |
| `SkillUniquenessGuard` | One record per person per skill |
| `UserSkillsStruct` | Read struct for a person's certifications |
| `SkillSearchTool` | Typeahead for requirement pickers |

Expiry is retained. Lapsed certifications are surfaced, never auto-revoked — a lapsed CDL is a
fact to display, not a record to destroy.

### Step 2 — Reservations

The only operational part that works alone. Build it fully before dispatch exists.

| Component | Does |
| :--- | :--- |
| `ReservationContext` | Caller-facing façade for one booking |
| `ReservationFactory` | Create tentative — standalone or attached |
| `ReservationStateMachine` | Tentative → Confirmed → CheckedOut → Returned, plus Cancelled and NoShow |
| `DoubleBookingPolicy` | Overlap query. Tentative warns, confirmed blocks unless acknowledged |
| `AssetAvailabilityPolicy` | Is this asset free in this window — **includes maintenance-type bookings automatically** |
| `CheckoutManager` | Both handover tracks. Read the legacy file first |
| `MeterReadRecorder` | Writes to asset meter history, stores the two references back |
| `ReservationUpdateNarrator` | Writes the typed change log |
| `ReservationPromotionManager` | Attach a standalone booking to a dispatch |
| `AccountablePersonGuard` | Self-service requires being the accountable person |
| `VerifierDistinctGuard` | Verifier must not be the self-service actor |
| `ReservationDeletionGuard` | Deletion only before any handover |
| `AssetCalendarSearch` | Availability over a window |

### Step 3 — Dispatch

| Component | Does |
| :--- | :--- |
| `DispatchContext` | Façade: header, requirements, line items |
| `DispatchFactory` | Create, blank or template-seeded |
| `DispatchStateMachine` | Draft → Submitted → UnderReview → Planned / AlternateResolution / Rejected → Completed |
| `DispatchStateDeriver` | **Planned iff a live reservation exists; AlternateResolution iff resolved with none.** Derived, never set by hand |
| `IntentLockGuard` | Blocks intent edits from Planned, AlternateResolution, Rejected |
| `RequirementManifestEditor` | Add, remove, and re-flag the five requirement types |
| `DispatchDemandManager` | Raise demands on material requirements; delegate cancellation |
| `RequestedAssetAutoReserver` | Tentatively hold the free ones, skip the contested — doc 2 §4.2 |
| `DispatchRejectionManager` | Record rejection on the header. Reason required |
| `DispatchCancellationOrchestrator` | Cancel bookings, ask the demand side to cancel unissued demands |
| `CrewRosterManager` | Personnel on the dispatch |
| `DispatchSupersessionManager` | New dispatch linked to the old |
| `DispatchQueueSearch` | The dispatcher queue |
| `DispatchDetailStruct` | Everything one page needs |

### Step 4 — Line items and narration

| Component | Does |
| :--- | :--- |
| `ExpenseManager` | Add, edit, commit, complete — contract and reimbursement in one |
| `ExpenseCancellationManager` | Reason required, record retained |
| `DispatchNarrator` | **The headline feature.** Milestones from every line item onto the dispatch timeline |
| `DispatchCostStruct` | What did this job cost |

**Narration is a first-class component, not a side effect.** Every line item verb calls it in
the same transaction as the change. Rules in doc 4 §5.2: automatic, plain language,
distinguishable from human comments, never the audit trail.

### Step 5 — Templates

Last, because instantiation needs a dispatch to instantiate into.

| Component | Does |
| :--- | :--- |
| `TemplateContext` | Façade for one lineage and its revisions |
| **`TemplateDraftSessionAdapter`** | **The centre of this step.** Holds the working draft in the session — load from head, mutate pre-fill values and all six requirement lists, discard. **Writes nothing to the database.** Copy `app/maintenance/control_layer/adapters/template_builder_session_adapter.py` |
| `TemplateRevisionCommitManager` | One transaction: create the revision, write its whole manifest, move the head, supersede the previous. Change note required |
| **`TemplateHeadDriftGuard`** | Refuses a commit when the head moved while the draft was open. Doc 1 §3.3 — without it the second committer silently discards the first's work |
| `TemplateImmutabilityGuard` | **A revision is never writable, ever.** No admin override, no exceptions |
| `TemplateCopyManager` | Seeds a working draft from a source revision into a **new lineage**; provenance recorded on commit |
| `TemplateRetirementManager` | Lineage-wide, reason required, reversible |
| `DispatchFromTemplateFactory` | One transaction: resolve the head, copy pre-fill, copy manifest, raise material demands, record the revision |
| `TemplateSearchTool` | Head revisions only, domain-filtered |

**There is no draft manager, because there are no draft rows.** The session adapter *is* the
draft. Every editing verb mutates session state; only `TemplateRevisionCommitManager` touches
the database, and it does so exactly once per commit however many edits preceded it.

Precedent to follow: the maintenance app eliminated its own persisted template-builder draft
tables in favour of session memory. Same problem, same answer.

---

## 3. Cross-app boundaries

Three seams. Get them wrong and the damage is silent.

| Boundary | Rule |
| :--- | :--- |
| **Demand hub** | Dispatching raises and asks to cancel demands. It never writes stock movements, and never decides what cancelling means. Doc 2 §7, §13 |
| **Asset meter history** | Dispatching writes readings through the assets-owned path and stores references. It never stores meter values on its own tables. Doc 3 §7.3 |
| **Maintenance** | **No coupling in either direction.** A maintenance-type booking is checked against nothing. Doc 3 §6.1 |

---

## 4. Guards

The three rules permissions structurally cannot express (doc 5 §4.5), plus the state-derived
ones. Every one is checked on write, in the control layer, never in an entrypoint.

| Guard | Enforces |
| :--- | :--- |
| `AccountablePersonGuard` | Self-service handover requires being the accountable person on *that* booking |
| `VerifierDistinctGuard` | The verifier is not the self-service actor |
| `IntentLockGuard` | Intent frozen at Planned, AlternateResolution, Rejected |
| `TemplateImmutabilityGuard` | A revision never changes once written |
| `TemplateHeadDriftGuard` | A commit is refused if the head moved while the draft was open |
| `DoubleBookingPolicy` | Confirmed overlap blocked without acknowledgement |
| `ReservationDeletionGuard` | No deletion after handover |
| `DemandCancellationGuard` | Issued demands are never cancelled |

---

## 5. Traps

| Trap | Guard |
| :--- | :--- |
| Building an outcome manager because legacy has one | §0. The concept is gone |
| Building an active-outcome pointer | design_drift §2.2 |
| Setting dispatch state by hand instead of deriving it | doc 2 §8.1 |
| Writing `PartIssue` rows directly | Doc 2 §7 |
| Storing meter values on a dispatching table | Doc 3 §7.3 |
| Checking maintenance records from a maintenance booking | Doc 3 §6.1 |
| Narration as an afterthought | Doc 4 §5 — same transaction as the change |
| Re-deriving the dual-track handover instead of reading legacy's | §1.2 |
| Writes from an entrypoint | `harness/Architecture/layer_rules.md` |
| A `*Service` suffix | Not in the house vocabulary. Legacy uses it; we do not |
| Persisting a template draft to the database | Phase 1 D4. Four edits must produce one revision |
| Letting a commit through when the head has moved | Doc 1 §3.3 |

---

## 6. Done when

- [ ] All five steps built, in order
- [ ] No component in §1.2 marked DELETE has a counterpart
- [ ] Every §4 guard exists and has tests
- [ ] Dispatch state is derived from live line items, never assigned
- [ ] Every line item verb narrates in the same transaction
- [ ] Demand raise and cancel go through the hub; no direct stock writes
- [ ] Meter readings write to asset meter history; reservations hold references only
- [ ] Nothing in dispatching reads or enforces against maintenance records
- [ ] Tests for every verb, guard, and state transition
- [ ] Reservation lifecycle works end to end with **no dispatch in the database**
- [ ] Template edit → commit → instantiate → deviate works end to end
- [ ] Several edits in one session produce exactly **one** revision
- [ ] A commit against a stale head is refused, with a message naming the newer revision
- [ ] `./venv/bin/python manage.py check` passes
